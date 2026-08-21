"""Hook safety helpers — graceful degradation for hook failures.

This module formalises a pattern that has accreted ad-hoc across the hook
suite: "never let the hook itself become the reason Claude Code is blocked."
See ``unified_session_tracker.py`` (>20 ``try``/``except`` blocks wrapping
non-critical work) and ``enforce_prunable_threshold.py`` (lib-path resolver
with installed-location fallback at lines 23-45) for the prior art that this
module formalises.

Two failure modes motivate this module (Issue #953, supersedes #946 + #947):

1. **Hook script missing or its imports broken.** Python raises out of the
   hook process; Claude Code surfaces the traceback as a hook-block message
   like ``UserPromptSubmit operation blocked by hook: [Errno 2] No such file
   or directory``. There is no in-product recovery path for the user.

2. **Hook tells the user to run a slash command that is not registered.**
   The user is in a deadlock between a hook demanding command X and command
   X not existing on disk.

Mode 1 is addressed by :func:`safe_main`, which wraps a hook's ``main()``
function and converts any unhandled exception into ``SystemExit(0)`` plus a
``[hook warning] ...`` line on stderr. The hook's success path (including
explicit ``int`` return values and explicit ``SystemExit``) is preserved
verbatim — the wrap is a pure outer safety net.

Because that conversion makes a crash exit indistinguishable from a healthy
``sys.exit(0)``, the synthesised ``SystemExit`` is stamped with
:data:`CRASH_EXIT_ATTR` (and mirrored into ``hook_timing``'s process-global
crash flag). Per-invocation timing telemetry consults the marker so it can
exempt genuine ``sys.exit(0)`` successes from the ``"exception"`` bucket
without also whitewashing real crashes.

Mode 2 is addressed by :func:`command_registered`, which probes the standard
slash-command lookup paths. Hooks that would otherwise issue a
``deny`` decision telling the user to run ``/foo`` MUST first call
``command_registered("foo")`` and downgrade the deny to a soft warning when
the command is missing — otherwise the user is wedged.

Mode 3 (Issue #1588) is a *different* class and is addressed by
:class:`HookDecision` plus the decision-returning branch of :func:`safe_main`.
A hook can refuse correctly and record nothing, and the result is
indistinguishable from a hook that never fires. Every prior attempt to close
this by *detecting* unrecorded refusals failed, because "is this payload a
refusal?" is an open question — there are unbounded ways to construct a JSON
object. "Does this file write to stdout?" is a *closed* question, so the fix
moves the constraint from what a hook emits to whether it may emit at all:
a hook that ``return``\\ s a :class:`HookDecision` instead of printing hands
the output channel to this module, and emitting and recording become one
indivisible act that no caller can half-perform.

``safe_main`` does not own a second copy of the deny envelope. For the
``PreToolUse``/``deny`` case it DELEGATES to
``hook_telemetry.deny_and_record`` — the existing sanctioned sink, which
already fuses the record to the payload — and merely writes the returned
envelope to stdout. The wrapper therefore *composes* with the existing
sinks rather than superseding them: ``deny_and_record`` fuses recording to
the payload (content-level), and ``safe_main`` fuses emission to both
(channel-level).

Shebang note: this fix also requires every hook to use
``#!/usr/bin/env python3`` rather than ``#!/usr/bin/env -S uv run --script``.
A pinned interpreter (``uv``) is itself a deadlock cause: if ``uv`` is not on
PATH, the hook never reaches the safe_main wrap. The standard
``python3`` shebang falls over to whatever interpreter PATH provides.
"""

from __future__ import annotations

import json
import os
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Dict, Optional, Union


# Attribute stamped onto the ``SystemExit`` that :func:`safe_main` synthesises
# from an unhandled crash, so per-invocation timing telemetry can still tell a
# converted crash apart from a genuine ``sys.exit(0)`` success. The canonical
# definition lives in ``hook_timing.CRASH_EXIT_ATTR``; this literal is the
# fallback for the case where ``hook_timing`` is not importable. A
# cross-validation test asserts the two spellings agree.
CRASH_EXIT_ATTR: str = "_hook_safety_crash"


def _mark_crash_exit(exit_exc: SystemExit) -> SystemExit:
    """Stamp ``exit_exc`` as crash-converted for timing telemetry.

    ``safe_main`` turns an unhandled crash into ``SystemExit(0)`` so a broken
    hook never blocks Claude Code. Without a marker that exit is byte-for-byte
    identical to the ``sys.exit(0)`` a healthy hook uses to finish, and any
    timing consumer that (correctly) stops treating ``SystemExit`` as a crash
    would silently relabel real failures as successes.

    Best-effort in the strictest sense: this is the safety net's own crash
    path, so every failure mode here is swallowed. Telemetry NEVER takes
    precedence over exiting cleanly.

    Args:
        exit_exc: The ``SystemExit`` about to be raised in place of the crash.

    Returns:
        The same ``exit_exc``, for call-site chaining.
    """
    try:
        import hook_timing  # noqa: PLC0415 — lazy: hook_safety must not hard-depend

        hook_timing.mark_crash_exit(exit_exc)
    except BaseException:  # noqa: BLE001 — telemetry must never break the exit
        # ``hook_timing`` unavailable (missing, broken import, sys.path not
        # set up). Fall back to the raw attribute so a timer that IS
        # importable in the same process can still read the marker.
        try:
            setattr(exit_exc, CRASH_EXIT_ATTR, True)
        except BaseException:  # noqa: BLE001
            pass
    return exit_exc


# ---------------------------------------------------------------------------
# Issue #1588 — the decision object and the output channel it owns
# ---------------------------------------------------------------------------

#: Claude Code hook protocols this module can emit for. Two genuinely
#: different payload shapes exist and MUST NOT be collapsed into one: a
#: ``PreToolUse`` refusal is ``hookSpecificOutput.permissionDecision`` with an
#: ``allow|deny|ask`` vocabulary, while a ``UserPromptSubmit`` refusal has no
#: ``permissionDecision`` at all — it carries ``hookSpecificOutput.error`` and
#: signals refusal through exit status 2.
PRE_TOOL_USE: str = "PreToolUse"
USER_PROMPT_SUBMIT: str = "UserPromptSubmit"

#: Per-protocol decision vocabulary. Enforced at construction so a
#: ``PreToolUse``-only value (``"deny"``) cannot be smuggled into a
#: ``UserPromptSubmit`` payload, or vice versa.
PROTOCOL_DECISIONS: Dict[str, frozenset] = {
    PRE_TOOL_USE: frozenset({"allow", "deny", "ask"}),
    USER_PROMPT_SUBMIT: frozenset({"allow", "block"}),
}

#: Decision values that constitute a refusal — i.e. anything that is not a
#: plain ``allow``. Every refusal emitted through :func:`safe_main` is
#: recorded; allows are not (matching the pre-existing telemetry baseline,
#: where ``hook_timing`` owns the allow shape).
REFUSAL_DECISIONS: frozenset = frozenset({"deny", "ask", "block"})


@dataclass(frozen=True)
class HookDecision:
    """A hook's decision as a *returned value* rather than a printed payload.

    Returning one of these from ``main()`` transfers ownership of stdout to
    :func:`safe_main`, which emits the payload and records the refusal in one
    indivisible act. That is the whole point (Issue #1588): a hook that never
    touches stdout cannot refuse without recording, so the guarantee holds by
    construction rather than by a convention someone has to remember.

    The object carries its ``protocol`` because the two Claude Code hook
    protocols have genuinely different payload shapes. Collapsing them would
    silently emit a ``permissionDecision`` on a ``UserPromptSubmit`` event,
    where the field does not exist and would be ignored — an invisible
    downgrade of a refusal to an allow.

    Attributes:
        decision: Protocol-appropriate decision value. ``allow``/``deny``/
            ``ask`` for ``PreToolUse``; ``allow``/``block`` for
            ``UserPromptSubmit``.
        reason: Model-visible reason. Should carry a REQUIRED NEXT ACTION
            directive on refusals (stick+carrot pattern).
        hook_name: Filename the refusal is attributed to in telemetry. When
            empty, :func:`safe_main` substitutes the calling hook's filename.
        protocol: ``PRE_TOOL_USE`` (default) or ``USER_PROMPT_SUBMIT``.
        system_message: Optional user-visible message. ``PreToolUse`` only.
        metadata: Optional JSON-serialisable telemetry metadata.
        session_id: Session id for telemetry; defaults to ``CLAUDE_SESSION_ID``.
        start_dir: Anchor for ``.claude/logs/hook-blocks.jsonl``. Pass the repo
            root so the row lands there regardless of the hook's cwd.
        decision_shape: Telemetry shape label. ``"dict"`` (a printed JSON
            envelope) is correct for every payload this class emits.

    Raises:
        ValueError: If ``protocol`` is unknown, or ``decision`` is not in that
            protocol's vocabulary. Deliberately loud: a mismatch here is a
            programming error, and silently emitting an unrecognised payload
            is how a refusal becomes an invisible allow.
    """

    decision: str
    reason: str = ""
    hook_name: str = ""
    protocol: str = PRE_TOOL_USE
    system_message: str = ""
    metadata: Optional[Dict[str, Any]] = None
    session_id: Optional[str] = None
    start_dir: Optional[Path] = None
    decision_shape: str = "dict"

    def __post_init__(self) -> None:
        """Validate the protocol/decision pairing at construction time."""
        allowed = PROTOCOL_DECISIONS.get(self.protocol)
        if allowed is None:
            raise ValueError(
                f"Unknown hook protocol {self.protocol!r}\n"
                f"Expected one of: {sorted(PROTOCOL_DECISIONS)}\n"
                f"See: plugins/autonomous-dev/lib/hook_safety.py"
            )
        if self.decision not in allowed:
            raise ValueError(
                f"Decision {self.decision!r} is not valid for protocol "
                f"{self.protocol!r}\n"
                f"Expected one of: {sorted(allowed)}\n"
                f"See: plugins/autonomous-dev/lib/hook_safety.py"
            )

    @classmethod
    def deny(
        cls,
        *,
        hook_name: str,
        reason: str,
        system_message: str = "",
        metadata: Optional[Dict[str, Any]] = None,
        session_id: Optional[str] = None,
        start_dir: Optional[Path] = None,
    ) -> "HookDecision":
        """Build a ``PreToolUse`` refusal. The common case, named explicitly.

        Args:
            hook_name: Filename to attribute the refusal to in telemetry.
            reason: Model-visible ``permissionDecisionReason``.
            system_message: Optional user-visible ``systemMessage``.
            metadata: Optional structured telemetry metadata.
            session_id: Optional session id.
            start_dir: Anchor for the telemetry log.

        Returns:
            A ``PreToolUse``/``deny`` decision, not yet emitted or recorded —
            :func:`safe_main` does both when the hook returns it.
        """
        return cls(
            decision="deny",
            reason=reason,
            hook_name=hook_name,
            protocol=PRE_TOOL_USE,
            system_message=system_message,
            metadata=metadata,
            session_id=session_id,
            start_dir=start_dir,
        )

    def is_refusal(self) -> bool:
        """Return True iff this decision refuses (anything but a plain allow)."""
        return self.decision in REFUSAL_DECISIONS

    def exit_code(self) -> int:
        """Return the process exit status this decision implies.

        ``PreToolUse`` always exits 0 — the decision travels via stdout JSON.
        ``UserPromptSubmit`` has no ``permissionDecision`` field, so its
        refusal is signalled by exit status 2.
        """
        if self.protocol == USER_PROMPT_SUBMIT and self.is_refusal():
            return 2
        return 0

    def to_payload(self) -> Optional[Dict[str, Any]]:
        """Build the protocol-correct stdout payload, or None to emit nothing.

        Pure: builds, never records. This is the fallback and non-``deny``
        path — for a ``PreToolUse``/``deny`` decision :func:`safe_main`
        prefers the envelope returned by ``hook_telemetry.deny_and_record``
        so that exactly one canonical deny-envelope builder is in play. This
        branch is reached only when that sink is unavailable (stale install),
        where refusing unrecorded still beats not refusing.

        Returns:
            The payload dict, or ``None`` when the decision is a plain allow
            (absence of an envelope is the established "allow" contract for
            standalone hooks).
        """
        if not self.is_refusal():
            return None

        if self.protocol == USER_PROMPT_SUBMIT:
            return {
                "hookSpecificOutput": {
                    "hookEventName": USER_PROMPT_SUBMIT,
                    "error": self.reason,
                }
            }

        payload: Dict[str, Any] = {
            "hookSpecificOutput": {
                "hookEventName": self.protocol,
                "permissionDecision": self.decision,
                "permissionDecisionReason": self.reason,
            }
        }
        if self.system_message:
            payload["systemMessage"] = self.system_message
        return payload


def _stderr(message: str) -> None:
    """Write ``message`` to stderr, swallowing any failure to do so.

    The last link in every degradation chain in this module. If stderr itself
    is unusable there is nowhere left to report, and raising here would defeat
    the safety net that called us.

    Args:
        message: Text to write. A trailing newline is added when absent.
    """
    try:
        sys.stderr.write(message if message.endswith("\n") else message + "\n")
        sys.stderr.flush()
    except Exception:  # noqa: BLE001 — nowhere left to report
        pass


def _telemetry_failed(decision: HookDecision, recorder: str, exc: BaseException) -> None:
    """Report that a refusal was NOT recorded, without failing the refusal.

    Swallowing the exception is correct — telemetry must never outrank
    enforcement — but swallowing it *silently* recreates the unknowable zero
    that Issue #1588 exists to eliminate: zero rows with no stderr is
    indistinguishable from a guard that never fired. ``log_block_event``
    already reports its own ``OSError`` this way; this matches that prefix so
    both surface in the same grep.

    Args:
        decision: The refusal whose row was lost.
        recorder: Dotted name of the recorder that failed.
        exc: The failure.
    """
    _stderr(
        f"[hook-telemetry] refusal NOT recorded: "
        f"hook_name={decision.hook_name or '<unattributed>'} "
        f"decision={decision.decision} protocol={decision.protocol} "
        f"({recorder} failed: {type(exc).__name__}: {exc})"
    )


def _sink_envelope(decision: HookDecision) -> Optional[Dict[str, Any]]:
    """Delegate a ``PreToolUse``/``deny`` to the existing sanctioned sink.

    ``hook_telemetry.deny_and_record`` returns the deny envelope AND appends
    the ``hook-blocks.jsonl`` row in one call. Delegating rather than
    re-implementing keeps exactly one canonical deny-envelope builder in the
    repo, and inherits that function's own guarantee that a telemetry failure
    degrades to "block, unrecorded" and never to "allow".

    Args:
        decision: The refusal to record and render.

    Returns:
        The deny envelope, or ``None`` when the sink is unavailable or itself
        failed — in which case the caller falls back to
        :meth:`HookDecision.to_payload` so the refusal is still emitted. The
        failure is reported on stderr; it is swallowed, not hidden.

    Raises:
        KeyboardInterrupt: Propagated deliberately. ``safe_main`` re-raises
            ``Ctrl+C`` and this handler must not contradict it from inside the
            same module.
        SystemExit: Propagated for the same reason.
    """
    try:
        from hook_telemetry import deny_and_record  # noqa: PLC0415 — lazy by design

        return deny_and_record(
            hook_name=decision.hook_name,
            reason=decision.reason,
            system_message=decision.system_message,
            decision_shape=decision.decision_shape,
            hook_event_name=decision.protocol,
            metadata=decision.metadata,
            session_id=decision.session_id,
            start_dir=decision.start_dir,
        )
    except Exception as exc:  # noqa: BLE001 — telemetry NEVER outranks enforcement
        _telemetry_failed(decision, "hook_telemetry.deny_and_record", exc)
        return None


def _record_refusal(decision: HookDecision) -> None:
    """Record a refusal that did not travel through :func:`_sink_envelope`.

    Covers the ``ask`` and ``UserPromptSubmit``/``block`` shapes, for which
    ``deny_and_record`` has no envelope to offer. Every failure is swallowed,
    because a recording bug converting a block into an allow would be far
    worse than the missing row — but the loss is reported on stderr, because a
    silent zero is exactly the unknowable state this module exists to remove.

    Args:
        decision: The refusal to record.

    Raises:
        KeyboardInterrupt: Propagated deliberately, matching ``safe_main``.
        SystemExit: Propagated for the same reason.
    """
    try:
        from hook_telemetry import log_block_event  # noqa: PLC0415 — lazy by design

        log_block_event(
            hook_name=decision.hook_name,
            decision_shape=decision.decision_shape,
            reason=decision.reason,
            metadata=decision.metadata,
            session_id=decision.session_id,
            start_dir=decision.start_dir,
        )
    except Exception as exc:  # noqa: BLE001 — telemetry NEVER outranks enforcement
        _telemetry_failed(decision, "hook_telemetry.log_block_event", exc)


def _payload_carries_decision(
    payload: Optional[Dict[str, Any]], decision: HookDecision
) -> bool:
    """Return True iff ``payload`` still expresses ``decision``'s refusal.

    The post-condition on everything about to reach stdout. ``emit_decision``
    hands the envelope off to an external sink, and an envelope that has lost
    its ``permissionDecision`` field is read by Claude Code as an **allow** —
    while the telemetry row, already written, asserts a block. That pairing is
    forged evidence, so the field is verified rather than assumed.

    Args:
        payload: Candidate stdout payload.
        decision: The decision it is supposed to express.

    Returns:
        True when the payload carries the protocol's refusal field with the
        decided value.
    """
    if not isinstance(payload, dict):
        return False
    hook_specific = payload.get("hookSpecificOutput")
    if not isinstance(hook_specific, dict):
        return False
    if decision.protocol == USER_PROMPT_SUBMIT:
        return "error" in hook_specific
    return hook_specific.get("permissionDecision") == decision.decision


def _render(payload: Dict[str, Any], decision: HookDecision) -> str:
    """Serialise ``payload``, coercing rather than dropping the refusal.

    ``HookDecision.reason`` is annotated ``str`` but nothing enforces it, so a
    hook may pass a ``Path``, an exception, or a dict and reach ``json.dumps``
    with a value it cannot encode. Dropping the refusal there is a fail-OPEN
    on the one path every migrated guard travels, so each fallback degrades
    the *message* and never the decision.

    Args:
        payload: The payload to render.
        decision: Source decision, used to rebuild a minimal envelope if the
            payload cannot be rendered at all.

    Returns:
        A JSON string. Always — the last resort is built entirely from
        ``str()``-coerced values.
    """
    try:
        return json.dumps(payload)
    except (TypeError, ValueError) as exc:
        _stderr(
            f"[hook warning] {decision.hook_name or '<unattributed>'}: refusal "
            f"payload is not JSON-serialisable ({type(exc).__name__}: {exc}); "
            f"coercing non-serialisable values to text. Fix the caller — "
            f"HookDecision.reason must be a str."
        )

    try:
        return json.dumps(payload, default=str, skipkeys=True)
    except Exception:  # noqa: BLE001 — see below; narrowing this re-opens a crash
        # NOT ``(TypeError, ValueError)``. ``default=str`` INVOKES the value's
        # own ``__str__``, so this call runs caller-supplied code and can raise
        # anything it likes. A ``RuntimeError`` from a hostile ``__str__`` used
        # to escape here -> ``emit_decision`` -> ``safe_main`` (which calls
        # ``emit_decision`` outside its own ``try``) and surfaced as an uncaught
        # traceback with EMPTY stdout — the allow contract, produced by the
        # fallback chain that exists to prevent exactly that. It also made the
        # tier below unreachable, so its "a ``__str__`` that raises must not
        # win" comment named a case it could never handle.
        pass

    # Last resort: rebuild from scratch with every field coerced by hand. The
    # message may be degraded; the decision never is.
    try:
        reason = str(decision.reason)
    except Exception:  # noqa: BLE001 — a __str__ that raises must not win
        reason = "(refusal reason could not be rendered)"
    if decision.protocol == USER_PROMPT_SUBMIT:
        minimal: Dict[str, Any] = {
            "hookSpecificOutput": {
                "hookEventName": USER_PROMPT_SUBMIT,
                "error": reason,
            }
        }
    else:
        minimal = {
            "hookSpecificOutput": {
                "hookEventName": str(decision.protocol),
                "permissionDecision": str(decision.decision),
                "permissionDecisionReason": reason,
            }
        }
    try:
        return json.dumps(minimal)
    except (TypeError, ValueError):
        # Nothing derived from the decision can be trusted. Emit a constant
        # refusal rather than nothing at all.
        return json.dumps(
            {
                "hookSpecificOutput": {
                    "hookEventName": PRE_TOOL_USE,
                    "permissionDecision": "deny",
                    "permissionDecisionReason": (
                        "A hook refused this operation but its reason could "
                        "not be rendered. REQUIRED NEXT ACTION: inspect "
                        ".claude/logs/hook-blocks.jsonl for the recorded row."
                    ),
                }
            }
        )


def emit_decision(decision: HookDecision, *, hook_name: str = "") -> bool:
    """Write ``decision`` to stdout and record it, as one indivisible act.

    Ordering is load-bearing, and it is the source of this function's only
    unrecoverable failure mode. Recording happens first because the sanctioned
    sink returns the envelope and the row together, so a fault on the emission
    side leaves a row describing a refusal that never shipped.

    The failure modes are handled separately because they are different
    faults:

    * **Recording fails** — swallowed, reported on stderr, and the refusal is
      rebuilt from :meth:`HookDecision.to_payload` and emitted anyway.
    * **The sink returns a payload that does not carry the decision** —
      rejected by :func:`_payload_carries_decision` and rebuilt, because an
      envelope without ``permissionDecision`` is an allow.
    * **Serialisation fails** — recoverable. :func:`_render` coerces the
      message; the decision is never dropped.
    * **stdout is unwritable** — NOT recoverable. The refusal does not reach
      Claude Code, a row already exists for it, and the caller is told so it
      can avoid exiting 0 as if the operation had been permitted.

    A ``UserPromptSubmit`` refusal additionally writes its message to stderr
    before the stdout write, because that protocol signals refusal by exit 2
    and on exit 2 stderr is the channel the user sees. Refusals on the other
    protocol do not, and a permitted prompt writes nothing.

    Args:
        decision: The decision returned by the hook's ``main()``.
        hook_name: Filename to attribute telemetry to when the decision does
            not carry one.

    Returns:
        True when the payload reached stdout, or when there was nothing to
        emit (a plain allow). False only when a refusal was decided and could
        not be emitted — the caller MUST NOT then exit 0 silently.
    """
    if not decision.hook_name and hook_name:
        decision = dataclass_replace(decision, hook_name=hook_name)

    payload: Optional[Dict[str, Any]] = None
    if decision.is_refusal():
        if decision.protocol == PRE_TOOL_USE and decision.decision == "deny":
            payload = _sink_envelope(decision)
        else:
            _record_refusal(decision)

        if payload is not None and not _payload_carries_decision(payload, decision):
            _stderr(
                f"[hook error] {decision.hook_name or '<unattributed>'}: the "
                f"refusal sink returned a payload that does not carry the "
                f"decision ({payload!r}). Claude Code reads that as an ALLOW. "
                f"Rebuilding the envelope from the HookDecision."
            )
            payload = None

    if payload is None:
        payload = decision.to_payload()

    if payload is None:
        return True

    line = _render(payload, decision)

    if decision.protocol == USER_PROMPT_SUBMIT and decision.is_refusal():
        # On a UserPromptSubmit refusal the process exits 2, and on exit 2 the
        # stdout envelope is NOT surfaced to the user — stderr is. Emitting
        # only the envelope would refuse the prompt with the message nowhere a
        # human can read it. The live refuser (unified_prompt_validator.py)
        # already prints its message to stderr before the JSON; a hook
        # migrating onto HookDecision must inherit that, not lose it.
        # ``system_message`` is the human's copy when a hook supplies one;
        # ``reason`` is otherwise the only text there is.
        _stderr(decision.system_message or decision.reason)

    try:
        sys.stdout.write(line + "\n")
        sys.stdout.flush()
    except (OSError, ValueError):
        # A closed or broken stdout is not something a hook can recover from,
        # and it MUST NOT become a traceback that blocks Claude Code. But it
        # MUST NOT be silent either: the refusal did not ship, and the block
        # log already claims it did.
        if decision.is_refusal():
            _stderr(
                f"[hook error] {decision.hook_name or '<unattributed>'}: a "
                f"refusal was DECIDED but NOT EMITTED (stdout unusable). "
                f"Claude Code received no decision, so the operation was "
                f"ALLOWED.\n"
                f"[hook error] A .claude/logs/hook-blocks.jsonl row exists for "
                f"a block that did not ship — block counts drawn from that log "
                f"are OVER-counts."
            )
            return False
    return True


def dataclass_replace(decision: HookDecision, **changes: Any) -> HookDecision:
    """Return a copy of ``decision`` with ``changes`` applied.

    Thin wrapper over ``dataclasses.replace`` kept local so this module has no
    import-time dependency beyond ``dataclass`` itself.

    Args:
        decision: The decision to copy.
        **changes: Field overrides.

    Returns:
        A new :class:`HookDecision`.
    """
    import dataclasses  # noqa: PLC0415 — lazy: keeps module import surface small

    return dataclasses.replace(decision, **changes)


# Hooks that issue deny decisions referencing a slash command MUST consult
# this module to ensure the command exists. The fail-mode for the lookup
# itself is *fail-CLOSED* (return True): if we cannot decide whether the
# command is registered, assume it IS registered so the existing security
# barrier still fires. This avoids a downgrade-via-error attack where a
# malformed plugins manifest causes the deny path to be silently disabled.


def safe_main(fn: Callable[[], Union[None, int, HookDecision]]) -> None:
    """Run a hook's ``main()`` function with a graceful-failure outer wrap.

    Behaviour:

    * **Success path preserved.** If ``fn`` returns ``None`` the process exits
      with status 0. If ``fn`` returns an ``int`` the process exits with that
      status (preserves block/warn semantics for hooks that already use
      ``return 1``/``return 2`` patterns).
    * **A returned** :class:`HookDecision` **is emitted and recorded** (Issue
      #1588). The wrapper writes the protocol-correct payload to stdout and
      records the refusal in one act, then exits with the status the protocol
      implies (0 for ``PreToolUse``, 2 for a ``UserPromptSubmit`` refusal).
      If the refusal was decided but could NOT be emitted, the implied 0 is
      raised to 1 — a non-blocking hook error — because exit 0 with empty
      stdout is indistinguishable from a permission. This is purely additive:
      hooks that print for themselves and return ``None``/``int`` are
      completely unaffected.
    * **Explicit ``SystemExit`` propagates.** If ``fn`` raises ``SystemExit``
      it passes through unchanged — this is a deliberate exit, not a crash.
    * **``KeyboardInterrupt`` propagates.** ``Ctrl+C`` MUST NOT be silently
      swallowed (debugging UX).
    * **Other exceptions are converted to exit 0 + stderr warning.** This is
      the core of the safety net: a missing import, a typo, or a runtime
      bug in the hook itself MUST NOT block Claude Code. A warning line of
      the form ``[hook warning] <hook_name>: <ExceptionType>: <message>`` is
      written to stderr so operators can detect failures. The synthesised
      ``SystemExit(0)`` is stamped via :func:`_mark_crash_exit` so timing
      telemetry can still distinguish it from a healthy ``sys.exit(0)``.

    Args:
        fn: The hook's ``main`` function. Conventionally takes no arguments
            and returns either ``None`` or an ``int`` exit code.

    Raises:
        SystemExit: Always raised at exit (caught by the Python runtime).

    Example::

        def main() -> int:
            ...
            return 0

        if __name__ == "__main__":
            safe_main(main)
    """
    # Identify the calling hook for the warning message. We walk one frame
    # up so the warning names the hook file, not this library.
    try:
        caller_file = sys._getframe(1).f_globals.get("__file__", "<unknown>")
        hook_name = Path(caller_file).name
    except Exception:
        hook_name = "<unknown hook>"

    try:
        result = fn()
    except SystemExit:
        # Explicit SystemExit (including from sys.exit(N)) is not a crash —
        # the hook chose its exit code deliberately. Preserve it.
        raise
    except KeyboardInterrupt:
        # Never swallow Ctrl+C. Operators interrupting a hook deserve to
        # see the interrupt propagate.
        raise
    except BaseException as exc:  # noqa: BLE001 — deliberately broad for safety net
        # Convert any other failure into a warning + exit 0. The hook MUST
        # NOT become the reason Claude Code is blocked.
        warning = (
            f"[hook warning] {hook_name}: "
            f"{type(exc).__name__}: {exc}\n"
            f"[hook warning] Hook failed but did not block. "
            f"See plugins/autonomous-dev/lib/hook_safety.py for rationale."
        )
        print(warning, file=sys.stderr)
        # Equivalent to ``sys.exit(0)`` (which is just ``raise SystemExit(0)``)
        # except that the exception carries a crash marker, so per-invocation
        # timing telemetry does not mistake this for a healthy exit.
        raise _mark_crash_exit(SystemExit(0)) from exc

    # Issue #1588: the hook handed us its decision instead of printing it.
    # Emitting and recording happen here, together, in one act the hook has
    # no way to half-perform.
    if isinstance(result, HookDecision):
        emitted = emit_decision(result, hook_name=hook_name)
        exit_code = result.exit_code()
        if result.is_refusal() and not emitted and exit_code == 0:
            # Exit 0 with empty stdout IS the allow contract for a standalone
            # PreToolUse hook, so exiting 0 here would silently convert the
            # refusal into a permission. Exit 1 is a non-blocking hook error:
            # it does not block the tool, but it surfaces the stderr lines
            # emit_decision just wrote instead of vanishing.
            exit_code = 1
        sys.exit(exit_code)

    # Preserve int return semantics (return 1 / return 2 patterns).
    if isinstance(result, int):
        sys.exit(result)
    sys.exit(0)


def _strip_leading_slash(name: str) -> str:
    """Return ``name`` without a leading ``/``."""
    return name[1:] if name.startswith("/") else name


def _check_command_dir(directory: Path, command_name: str) -> bool:
    """Return True iff ``directory`` contains ``<command_name>.md``.

    Defense-in-depth (Issue #954, M-01): ``command_name`` is a slash-command
    identifier, never a path. Reject any input containing path separators or
    ``..`` traversal segments outright, then use ``Path.resolve()`` as a
    backstop against symlink-based escapes. Without these guards a caller
    that ever passes user-controlled input could read arbitrary files
    relative to ``directory`` (e.g. ``"../../../etc/passwd"`` would resolve
    to ``/etc/passwd.md`` and ``.is_file()`` would happily report on it).
    """
    # Primary guard: slash-command names MUST NOT contain path components.
    if "/" in command_name or "\\" in command_name or ".." in command_name:
        return False
    try:
        if not directory.exists() or not directory.is_dir():
            return False
        candidate = directory / f"{command_name}.md"
        # Backstop: symlinks inside ``directory`` could still escape. Resolve
        # both paths (non-strict so non-existent files don't raise) and verify
        # the candidate remains inside ``directory``.
        try:
            candidate_resolved = candidate.resolve(strict=False)
            dir_resolved = directory.resolve(strict=False)
        except (OSError, RuntimeError):
            # Resolution failure (e.g. symlink loop) — treat as unknown.
            return False
        dir_prefix = str(dir_resolved) + os.sep
        if (
            not str(candidate_resolved).startswith(dir_prefix)
            and candidate_resolved != dir_resolved
        ):
            return False
        return candidate.is_file()
    except OSError:
        # Permission denied, broken symlink, etc. Treat as "unknown" — the
        # caller is responsible for its own fail-CLOSED policy via the outer
        # try/except in command_registered.
        return False


def _check_installed_plugins(plugins_manifest: Path, command_name: str) -> bool:
    """Return True iff ``plugins_manifest`` declares ``command_name``.

    The manifest format is the standard Claude Code installed-plugins JSON:
    a top-level dict with a ``commands`` array of entries that have a
    ``name`` field. Bad JSON or missing keys return False (caller's outer
    handler will fail-CLOSED on a true exception).
    """
    if not plugins_manifest.is_file():
        return False
    try:
        data = json.loads(plugins_manifest.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError, UnicodeDecodeError):
        # Corrupt manifest is treated as "no info" rather than crashing. The
        # outer try/except in command_registered() will fail-CLOSED.
        return False

    # Search a few plausible shapes — the spec is loose about manifest format.
    if isinstance(data, dict):
        commands = data.get("commands", [])
        if isinstance(commands, list):
            for entry in commands:
                if isinstance(entry, dict) and entry.get("name") == command_name:
                    return True
                if isinstance(entry, str) and entry == command_name:
                    return True
        # Some manifests may store commands under an installed_plugins map.
        installed = data.get("installed_plugins") or data.get("plugins") or {}
        if isinstance(installed, dict):
            for plugin_data in installed.values():
                if not isinstance(plugin_data, dict):
                    continue
                plugin_commands = plugin_data.get("commands", [])
                if not isinstance(plugin_commands, list):
                    continue
                for entry in plugin_commands:
                    if isinstance(entry, dict) and entry.get("name") == command_name:
                        return True
                    if isinstance(entry, str) and entry == command_name:
                        return True
    return False


def command_registered(name: str) -> bool:
    """Return True iff slash command ``name`` is registered on this machine.

    Lookup order (first match wins):

    1. **Project-local commands**: ``./.claude/commands/<name>.md`` relative
       to ``os.getcwd()``.
    2. **User-global commands**: ``~/.claude/commands/<name>.md``.
    3. **Installed plugins manifest**: ``~/.claude/installed_plugins.json``,
       ``~/.claude/plugins/installed_plugins.json`` — entries are searched
       under ``commands``, ``installed_plugins``, or ``plugins`` keys.

    The leading ``/`` on ``name`` is optional — ``"create-issue"`` and
    ``"/create-issue"`` are equivalent.

    **Fail-mode is CLOSED.** If any unexpected exception bubbles out of the
    lookup, this function returns ``True`` (assume the command IS registered).
    Rationale: callers use this to decide whether to issue a ``deny``
    decision. Returning ``True`` on lookup error preserves the existing
    security barrier rather than letting a malformed manifest silently
    disable the deny path. See module docstring.

    Args:
        name: Slash command name, with or without a leading ``/``.

    Returns:
        ``True`` if the command is registered (or if the lookup itself
        failed); ``False`` only when we are confident the command is
        genuinely missing.
    """
    try:
        command_name = _strip_leading_slash(name)
        if not command_name:
            return True  # Empty name → can't say it's missing.

        # Defense-in-depth chokepoint (Issue #954, M-01): slash-command names
        # are NEVER paths. Reject any name containing path separators or
        # ``..`` traversal segments before *any* filesystem or manifest
        # lookup. This is fail-OPEN (returning False) on purpose — the
        # caller asked about an obviously invalid command name, so we are
        # confident it does not exist as a real registered command.
        if "/" in command_name or "\\" in command_name or ".." in command_name:
            return False

        # 1. Project-local commands.
        try:
            cwd = Path(os.getcwd())
        except (FileNotFoundError, OSError):
            cwd = None
        if cwd is not None:
            project_dir = cwd / ".claude" / "commands"
            if _check_command_dir(project_dir, command_name):
                return True

        # 2. User-global commands.
        try:
            home = Path.home()
        except (RuntimeError, OSError):
            home = None
        if home is not None:
            global_dir = home / ".claude" / "commands"
            if _check_command_dir(global_dir, command_name):
                return True

            # 3. Installed plugins manifest — try standard locations.
            for manifest_path in (
                home / ".claude" / "installed_plugins.json",
                home / ".claude" / "plugins" / "installed_plugins.json",
            ):
                if _check_installed_plugins(manifest_path, command_name):
                    return True

        return False
    except BaseException:  # noqa: BLE001 — fail-CLOSED on any unexpected error
        # Fail-CLOSED: assume command IS registered so the deny path fires.
        return True
