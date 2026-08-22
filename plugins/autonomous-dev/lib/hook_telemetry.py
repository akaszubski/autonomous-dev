"""Unified hook block telemetry (Issue #972, #942-D capstone).

Single canonical surface for recording every "deny" decision a hook makes,
across all three deny shapes used in the harness:

- ``("deny", reason)`` tuple shape (used by ``unified_pre_tool.py`` via
  ``output_decision``).
- ``{"decision": "block", ...}`` dict shape (used by
  ``unified_prompt_validator.py``).
- ``sys.exit(2)`` shape (used by ``enforce_orchestrator.py`` and similar
  pre-commit hooks).

Each block emits one JSONL row to ``.claude/logs/hook-blocks.jsonl``. The
schema is stable: ``{ts, hook_name, decision_shape, reason, metadata,
session_id, cwd}``. The ``scripts/hook_block_summary.py`` triage script
reads this file (and the legacy ``hook-recovery.jsonl`` for one release
cycle) to produce per-hook block counts, category breakdowns, and
bypass-usage rates without grepping individual session transcripts.

Design constraints (mirrored from ``hook_bypass.py`` and ``hook_recovery.py``):

- Telemetry must NEVER raise. A logging or filesystem failure must NEVER
  block the underlying hook decision — the hook decision is the load-bearing
  path, telemetry is best-effort.
- Read-only filesystem fallback writes the JSON line to stderr instead.
- ``HOOK_TELEMETRY_DISABLED=<truthy>`` env var is the rollback switch.
- ``HOOK_RECOVERY_DISABLED=<truthy>`` is honored as a deprecation alias so
  existing rollback procedures keep working.
- The exemption registry is parsed defensively — malformed JSON is treated
  as "no exemptions".

Note on rotation: rotation is deferred to a follow-up. Line-level integrity
under concurrent writes is guaranteed via ``fcntl.flock(LOCK_EX)`` (POSIX
advisory lock) wrapped around the ``write`` call. This works for events of
any size — the previous reliance on ``PIPE_BUF`` atomic-append guarantees
(4096B Linux, 512B macOS) is too small for ``MAX_REASON_LENGTH=8000``
events and could produce torn lines on macOS even for typical events
(Issue #992). The lock adds ~1ms per write — negligible relative to hook
runtime — and preserves the 8000B reason headroom that triage relies on
for debugging context. On non-POSIX platforms (e.g. Windows), ``fcntl`` is
unavailable and we fall back to the bare append; concurrent writes on
Windows are vanishingly rare for this telemetry surface and acceptable as
a known limitation.
"""

from __future__ import annotations

import functools
import json
import os
import sys
import warnings
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Dict, Optional

# ``fcntl`` is POSIX-only. On Windows it is absent; we degrade gracefully
# to a bare append (no advisory locking). The advisory lock guards against
# torn JSONL lines when multiple processes concurrently append events
# larger than PIPE_BUF (4096B Linux, 512B macOS) — see Issue #992.
try:
    import fcntl  # type: ignore[import-not-found]
except ImportError:  # pragma: no cover - Windows fallback
    fcntl = None  # type: ignore[assignment]

# ---------------------------------------------------------------------------
# Module constants
# ---------------------------------------------------------------------------

LOG_FILE_RELATIVE: Path = Path(".claude") / "logs" / "hook-blocks.jsonl"
EXEMPTION_REGISTRY_PATH: Path = (
    Path(".claude") / "config" / "hook_telemetry_exemptions.json"
)
LEGACY_EXEMPTION_PATH: Path = (
    Path(".claude") / "config" / "hook_recovery_exemptions.json"
)

DISABLE_ENV_VAR: str = "HOOK_TELEMETRY_DISABLED"
LEGACY_DISABLE_ENV_VAR: str = "HOOK_RECOVERY_DISABLED"

MAX_REASON_LENGTH: int = 8000

VALID_DECISION_SHAPES = frozenset(
    {"tuple", "dict", "exit2", "legacy_recovery", "mode_skip", "allow"}
)

# ---------------------------------------------------------------------------
# The refusal vocabulary (Issue #1611) — exported ONCE, beside the writer.
# ---------------------------------------------------------------------------
#
# ``.claude/logs/hook-blocks.jsonl`` does not contain only blocks. Rows are
# appended by ``log_block_event`` for the Phase-E ``mode_skip`` path too —
# enforcement *skipped*, the opposite of a refusal — and 5.3% of the live log
# is that shape. This constant previously existed in exactly ONE reader
# (``scripts/hook_perf_report.py:39``); the other two readers omitted it and
# silently over-counted. A convention that two of three consumers ignore is
# not a mechanism, so the vocabulary now lives here, next to the only writer,
# and every reader imports it.
#
# ``BLOCK_SHAPES`` is the set of decision shapes that constitute a genuine
# refusal. Anything else — ``mode_skip``, ``allow``, or a shape invented
# tomorrow — is a NON-refusal event. Unknown shapes are deliberately treated
# as non-refusals and are still reported by the readers rather than dropped:
# fail visible, not closed.
BLOCK_SHAPES: "frozenset[str]" = frozenset(
    {"tuple", "dict", "exit2", "legacy_recovery"}
)

# Shapes known to be non-refusals. Documentation-only: ``is_refusal_shape``
# tests membership of ``BLOCK_SHAPES``, so an unknown shape is a non-refusal
# without needing to be enumerated here.
NON_REFUSAL_SHAPES: "frozenset[str]" = frozenset({"mode_skip", "allow"})

# Name of the explicit refusal boolean written into every row from #1611
# onward. Readers SHOULD prefer it over re-deriving from the shape; rows
# written before #1611 lack it and ``is_refusal_row`` falls back to the shape
# so historical rows classify identically.
REFUSED_FIELD: str = "refused"

# Event types written THROUGH the refusal recorder that are NOT refusals.
#
# ``unified_pre_tool.py`` appends ``prompt_integrity_recovery`` rows after its
# deny branch has already exited — on the ALLOW path — using the same recorder
# as the block. They therefore inherit ``decision_shape: "dict"`` and, from
# #1611 onward, a structural ``refused: true``. Measured on the live log: 57
# such rows, 57 of them classified as refusals. They are allows wearing a
# refusal label.
#
# The carve-out lives HERE, in the one classifier, rather than in each reader.
# ``pipeline_timing_analyzer`` already treated these rows as a distinct class
# while ``hook_block_summary`` did not — two readers of the same file, edited in
# the same changeset, disagreeing about the same 57 rows. A rule applied by one
# of two consumers is the defect this issue exists to remove, not the fix.
#
# It takes precedence over the explicit ``refused`` boolean, which is the one
# place that boolean is NOT authoritative: the writer derives it from the shape,
# and the shape is what is wrong for these rows. Repairing the writer is
# ``unified_pre_tool.py``'s to make and will not reclassify the rows already on
# disk; this will.
NON_REFUSAL_EVENT_TYPES: "frozenset[str]" = frozenset(
    {"prompt_integrity_recovery"}
)

# Decision VALUES that ``block_event_decorator`` treats as a refusal by
# default. Kept at exactly ``{"deny"}`` — the pre-#1611 behaviour — so that
# widening it is an explicit, per-call-site act. See the ``refusal_values``
# argument of ``block_event_decorator``.
DEFAULT_REFUSAL_DECISION_VALUES: "frozenset[str]" = frozenset({"deny"})

# ``mode_skip`` (Issue #999, Phase E) is emitted ONLY on the skip path of the
# session-mode enforcement gate. The enforce path stays silent — preserving
# the pre-Phase-E baseline where non-block hook outcomes produced no
# telemetry. ``mode_skip`` is intentionally NOT paired with a ``mode_enforce``
# shape: a single label ("we relaxed a check") is what triage cares about.
# ``allow`` (Issue #1012, W0) is emitted by ``hook_timing.HookTimer`` for
# every hook invocation that did NOT raise an exception and did NOT set a
# more specific decision shape. The constant is documentation-only — this
# module's ``log_block_event`` does not validate against the frozenset.

_FALSY_ENV_VALUES = frozenset({"", "0", "false", "no", "off"})

# Module-level guard so the legacy-env-var deprecation warning fires at most
# once per process. The hook decision path runs many times per session, and
# an unbounded warning stream would quickly drown the activity log.
_legacy_env_warned: bool = False


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def is_telemetry_disabled() -> bool:
    """Return True iff the telemetry surface is disabled via env var.

    Checks ``HOOK_TELEMETRY_DISABLED`` first; if unset, falls back to
    ``HOOK_RECOVERY_DISABLED`` (the rollback switch shipped with #970).
    The legacy alias emits a single stderr warning per process so users
    know to update to the new variable name.

    Truthy: any non-empty string NOT in ``{"0", "false", "no", "off"}``.
    """
    raw = os.environ.get(DISABLE_ENV_VAR)
    if raw is not None:
        return raw.strip().lower() not in _FALSY_ENV_VALUES

    legacy = os.environ.get(LEGACY_DISABLE_ENV_VAR)
    if legacy is None:
        return False

    if legacy.strip().lower() in _FALSY_ENV_VALUES:
        return False

    global _legacy_env_warned
    if not _legacy_env_warned:
        try:
            sys.stderr.write(
                "[hook-telemetry] DEPRECATED: HOOK_RECOVERY_DISABLED is "
                "honored as an alias for HOOK_TELEMETRY_DISABLED; please "
                "update.\n"
            )
        except Exception:
            pass
        _legacy_env_warned = True
    return True


def is_refusal_shape(decision_shape: Any) -> bool:
    """Return True iff ``decision_shape`` denotes a genuine refusal.

    The single authority on the question "is this row a block?". Unknown or
    non-string shapes are NON-refusals — a shape invented tomorrow must not
    be silently promoted into the refusal count.

    Args:
        decision_shape: The ``decision_shape`` field of a telemetry row.

    Returns:
        True when the shape is in :data:`BLOCK_SHAPES`.
    """
    return isinstance(decision_shape, str) and decision_shape in BLOCK_SHAPES


def row_event_type(row: Dict[str, Any]) -> str:
    """Return a row's ``metadata.event_type``, or ``""`` when absent.

    Args:
        row: A parsed ``hook-blocks.jsonl`` row.

    Returns:
        The event type string; ``""`` for any row without a well-formed one.
    """
    if not isinstance(row, dict):
        return ""
    metadata = row.get("metadata")
    if not isinstance(metadata, dict):
        return ""
    event_type = metadata.get("event_type")
    return event_type if isinstance(event_type, str) else ""


def is_non_refusal_event_type(row: Dict[str, Any]) -> bool:
    """Return True iff the row's event type is a known NON-refusal.

    See :data:`NON_REFUSAL_EVENT_TYPES` for why an event type can override
    both the shape and the explicit boolean.

    Args:
        row: A parsed ``hook-blocks.jsonl`` row.

    Returns:
        True when the row is one of the recorder-written allows.
    """
    return row_event_type(row) in NON_REFUSAL_EVENT_TYPES


def is_refusal_row(row: Dict[str, Any]) -> bool:
    """Return True iff a telemetry ``row`` records a genuine refusal.

    Three tests, in this order:

    1. A row whose ``metadata.event_type`` is in
       :data:`NON_REFUSAL_EVENT_TYPES` is NOT a refusal, whatever its shape or
       boolean says. These rows are written through the refusal recorder on an
       ALLOW path and inherit a refusal label they did not earn.
    2. Otherwise, the explicit :data:`REFUSED_FIELD` boolean written by
       :func:`log_block_event` from #1611 onward.
    3. Otherwise, the shape. Rows written before #1611 lack the boolean
       entirely, and the shape yields the identical answer because the boolean
       is derived from it.

    A non-bool value in the field is ignored (a hand-edited or corrupted row
    must not be able to assert its own refusal status) and the shape decides.

    Args:
        row: A parsed ``hook-blocks.jsonl`` row.

    Returns:
        True when the row records a refusal.
    """
    if not isinstance(row, dict):
        return False
    if is_non_refusal_event_type(row):
        return False
    explicit = row.get(REFUSED_FIELD)
    if isinstance(explicit, bool):
        return explicit
    return is_refusal_shape(row.get("decision_shape"))


def log_block_event(
    *,
    hook_name: str,
    decision_shape: str,
    reason: str,
    metadata: Optional[Dict[str, Any]] = None,
    session_id: Optional[str] = None,
    start_dir: Optional[Path] = None,
) -> None:
    """Append one JSONL line recording a hook deny decision.

    Writes to ``.claude/logs/hook-blocks.jsonl`` relative to ``start_dir``
    (or cwd). Auto-creates the ``.claude/logs/`` directory if missing. On
    any OSError (read-only FS, permission denied), falls back to writing
    the JSON line to stderr prefixed with ``[hook-telemetry]``.

    This function NEVER raises. Telemetry must never block hook decisions.

    Args:
        hook_name: Filename of the hook emitting the block (e.g.
            ``"unified_pre_tool.py"``).
        decision_shape: One of ``"tuple"``, ``"dict"``, ``"exit2"``,
            ``"legacy_recovery"`` (the last is for the back-compat shim),
            or ``"mode_skip"``. ``"allow"`` is emitted by
            ``hook_timing.HookTimer`` (sibling module, separate file).
            Unknown values are logged as-is — readers MUST treat the field
            as opaque.
        reason: Human-readable reason the hook denied. Capped at
            ``MAX_REASON_LENGTH`` characters.
        metadata: Optional structured metadata (tool_name, recovery_hint,
            etc). Must be JSON-serialisable; serialisation failure
            downgrades to ``{}``.
        session_id: Optional session id (defaults to ``CLAUDE_SESSION_ID``).
        start_dir: Project root anchor. Defaults to cwd.
    """
    if is_telemetry_disabled():
        return

    if session_id is None:
        session_id = os.environ.get("CLAUDE_SESSION_ID", "")

    safe_reason = ""
    try:
        safe_reason = str(reason)[:MAX_REASON_LENGTH]
    except Exception:
        safe_reason = ""

    safe_metadata: Dict[str, Any] = {}
    if metadata is not None:
        try:
            # Round-trip through JSON to drop non-serialisable values.
            safe_metadata = json.loads(json.dumps(metadata, default=str))
            if not isinstance(safe_metadata, dict):
                safe_metadata = {}
        except Exception:
            safe_metadata = {}

    try:
        cwd_str = str(Path.cwd())
    except (OSError, FileNotFoundError):
        cwd_str = ""

    event: Dict[str, Any] = {
        "ts": datetime.now(timezone.utc).isoformat(),
        "hook_name": hook_name,
        "decision_shape": decision_shape,
        # Issue #1611: the refusal status is STRUCTURAL, not a filter each
        # reader has to remember. A reader that ignores this field is making
        # a visible choice; one that omits a shape filter was making an
        # invisible omission — which is how two of three readers came to
        # report Phase-E skips as blocks.
        REFUSED_FIELD: is_refusal_shape(decision_shape),
        "reason": safe_reason,
        "metadata": safe_metadata,
        "session_id": session_id,
        "cwd": cwd_str,
    }

    try:
        line = json.dumps(event, ensure_ascii=False)
    except (TypeError, ValueError):
        line = json.dumps(
            {"ts": event["ts"], "hook_name": hook_name, "reason": safe_reason}
        )

    try:
        log_path = _resolve_log_path(start_dir)
        log_path.parent.mkdir(parents=True, exist_ok=True)
        with log_path.open("a", encoding="utf-8") as fh:
            # Hold an exclusive advisory lock for the duration of the
            # write. On POSIX this prevents concurrent appenders from
            # interleaving bytes within a single line — required because
            # ``MAX_REASON_LENGTH=8000`` exceeds PIPE_BUF on every
            # mainstream platform (Issue #992). On non-POSIX (fcntl=None)
            # we fall through to a bare append; this is the same
            # behavior as before the fix and is acceptable because
            # concurrent writes on Windows are not a realistic threat
            # for this telemetry surface.
            if fcntl is not None:
                try:
                    fcntl.flock(fh.fileno(), fcntl.LOCK_EX)
                except OSError:
                    # NFS or unsupported FS may refuse flock; degrade
                    # to bare append rather than raise. Telemetry must
                    # never break the hook decision path.
                    pass
                try:
                    fh.write(line + "\n")
                finally:
                    try:
                        fcntl.flock(fh.fileno(), fcntl.LOCK_UN)
                    except OSError:
                        pass
            else:
                fh.write(line + "\n")
        return
    except OSError as exc:
        try:
            sys.stderr.write(
                f"[hook-telemetry] {line} (log_write_failed: {exc})\n"
            )
        except Exception:
            pass
    except Exception as exc:  # pragma: no cover - last-resort guard
        try:
            sys.stderr.write(
                f"[hook-telemetry] {line} (unexpected_error: {exc})\n"
            )
        except Exception:
            pass


def deny_and_record(
    *,
    hook_name: str,
    reason: str,
    system_message: str = "",
    decision_shape: str = "dict",
    hook_event_name: str = "PreToolUse",
    metadata: Optional[Dict[str, Any]] = None,
    session_id: Optional[str] = None,
    start_dir: Optional[Path] = None,
) -> Dict[str, Any]:
    """Build a ``permissionDecision: "deny"`` envelope AND record it, as one act.

    This is the canonical way for a standalone hook to refuse. Refusing and
    recording the refusal are fused into a single call so that a caller
    **cannot obtain a deny payload without the telemetry row happening**.
    The defect class this closes (Issue #1587): hooks that call a payload
    builder and then, separately, are supposed to remember to call
    ``log_block_event``. Three of four pre-existing refusal paths deviated
    from that convention precisely because it was two acts. A convention is
    not a mechanism; this function is the mechanism.

    Telemetry is strictly subordinate to enforcement. If ``log_block_event``
    raises for any reason (unwritable log, patched-to-raise recorder, disk
    full), the exception is swallowed and the deny envelope is still
    returned. A telemetry failure converting a block into an allow would be
    far worse than the missing row.

    Args:
        hook_name: Filename of the hook emitting the refusal (e.g.
            ``"enforce_file_organization.py"``).
        reason: Model-visible ``permissionDecisionReason``. Should include a
            REQUIRED NEXT ACTION directive (stick+carrot pattern).
        system_message: Optional user-visible ``systemMessage``. Omitted
            from the envelope when empty.
        decision_shape: Telemetry label for the refusal shape. Defaults to
            ``"dict"`` — the shape of a printed JSON envelope, and a member
            of :data:`BLOCK_SHAPES`, so the row is counted as a refusal by
            every reader of the log. Callers that
            refuse via a different shape should pass ``"tuple"`` or
            ``"exit2"`` instead.
        hook_event_name: ``hookEventName`` for the envelope. Defaults to
            ``"PreToolUse"``.
        metadata: Optional structured metadata (tool_name, file_path, ...).
        session_id: Optional session id (defaults to ``CLAUDE_SESSION_ID``).
        start_dir: Anchor for ``.claude/logs/hook-blocks.jsonl``. Defaults
            to cwd. Pass the repo root so the row lands at the repo root
            regardless of the hook's cwd — and so tests can redirect the
            log away from the real one.

    Returns:
        The deny envelope, ready for ``json.dumps`` and printing to stdout.
    """
    hook_specific: Dict[str, Any] = {
        "hookEventName": hook_event_name,
        "permissionDecision": "deny",
        "permissionDecisionReason": reason,
    }
    envelope: Dict[str, Any] = {"hookSpecificOutput": hook_specific}
    if system_message:
        envelope["systemMessage"] = system_message

    try:
        log_block_event(
            hook_name=hook_name,
            decision_shape=decision_shape,
            reason=reason,
            metadata=metadata,
            session_id=session_id,
            start_dir=start_dir,
        )
    except Exception:
        # NEVER let telemetry break the refusal. log_block_event is
        # documented never to raise, but this guard is load-bearing: a
        # recorder regression must degrade to "block, unrecorded", never
        # to "allow".
        pass

    return envelope


def block_event_decorator(
    hook_name: str,
    *,
    decision_shape: str = "tuple",
    refusal_values: Optional["frozenset[str]"] = None,
    metadata: Optional[Dict[str, Any]] = None,
) -> Callable:
    """Decorator factory that emits a telemetry row on refusal decisions.

    Wraps a function whose first positional argument is the decision string
    (typically ``"allow"``, ``"deny"``, or ``"ask"``). When the decision is
    one of ``refusal_values``, a ``log_block_event`` row is appended with the
    second positional argument used as ``reason``.

    This is one of the sanctioned fusing sinks: the hook's SOLE refusal
    emitter is wrapped, so every refusal that travels through it records by
    construction. There is no second act to forget.

    The decorator is idempotent: re-wrapping a function that has already
    been wrapped is a no-op. This protects against accidental double-decor
    during defensive imports. Idempotency is only safe when the second
    decoration asks for the SAME configuration — a re-decoration with a
    different ``decision_shape``, ``refusal_values`` or ``metadata`` would be
    silently discarded, and the caller would believe a configuration was in
    effect that is not. That case now emits a one-line stderr warning naming
    both configurations rather than passing quietly; it does not raise, because
    telemetry must never break a decision path.

    Example::

        @block_event_decorator("unified_pre_tool.py")
        def output_decision(decision, reason, *, system_message=""):
            ...

    Args:
        hook_name: Filename of the hook to attribute blocks to.
        decision_shape: Telemetry shape label for the recorded row. Defaults
            to ``"tuple"`` (the ``("deny", reason)`` return shape). A hook
            whose emitter PRINTS a JSON envelope should pass ``"dict"`` so
            the row describes what actually crossed the wire.
        refusal_values: Decision values this emitter treats as a refusal.
            Defaults to :data:`DEFAULT_REFUSAL_DECISION_VALUES` — exactly
            ``{"deny"}``, the pre-#1611 behaviour — so no existing caller
            changes. It is a PARAMETER rather than a fixed set because the
            hook suite does not share one decision vocabulary: ``plan_gate.py``
            emits ``permissionDecision: "block"`` on a ``PreToolUse`` event,
            which is out of that protocol's ``allow|deny|ask`` enum. Issue
            #1589 owns resolving that divergence; #1611 only has to stop the
            refusal going unrecorded, and hard-coding ``{"deny"}`` here would
            have meant silently dropping every one of plan_gate's refusals.

            MUST be a set-like container of strings, not a bare string. A
            string is iterable and supports ``in``, so passing ``"block"``
            would silently turn the membership test into a SUBSTRING test and
            a decision of ``"loc"`` would record as a refusal. Validated
            below rather than documented and hoped for.
        metadata: Optional constant structured metadata stamped onto every
            recorded row. Use it to record what the row alone cannot say —
            most importantly, WHICH decision value this emitter actually put on
            the wire. A row carries ``hook_name``, ``decision_shape``,
            ``reason`` and ``refused``, and none of those distinguish
            ``plan_gate``'s out-of-enum ``permissionDecision: "block"`` from a
            genuine honoured ``deny``: the two are byte-comparable. Until
            #1589 resolves whether the client honours the out-of-enum value,
            recording it is what keeps the claim SEPARABLE in the log instead
            of merging an unverified refusal into the verified ones.

    Returns:
        A decorator that wraps a function with telemetry emission.

    Raises:
        TypeError: If ``refusal_values`` is a ``str``/``bytes`` rather than a
            collection of them.
    """
    if isinstance(refusal_values, (str, bytes)):
        raise TypeError(
            f"refusal_values must be a set of decision strings, not "
            f"{type(refusal_values).__name__} {refusal_values!r}.\n"
            f"Expected: frozenset({{{refusal_values!r}}})\n"
            f"A bare string makes `decision in values` a SUBSTRING test, so a "
            f"decision that merely contains the value would record as a "
            f"refusal.\n"
            f"See: plugins/autonomous-dev/lib/hook_telemetry.py"
        )
    values = (
        DEFAULT_REFUSAL_DECISION_VALUES if refusal_values is None else refusal_values
    )
    config = {
        "decision_shape": decision_shape,
        "refusal_values": frozenset(values),
        "metadata": metadata,
    }

    def decorator(fn: Callable) -> Callable:
        existing = getattr(fn, "_telemetry_config", None)
        if getattr(fn, "_telemetry_wrapped", False):
            if existing != config:
                # Loud, not fatal. Discarding a DIFFERENT configuration in
                # silence leaves the caller believing settings are in effect
                # that are not — the same invisible-omission class this module
                # exists to remove.
                try:
                    sys.stderr.write(
                        f"[hook-telemetry] WARNING: {fn.__name__!r} is already "
                        f"wrapped for {hook_name!r} with {existing!r}; the "
                        f"re-decoration requesting {config!r} was DISCARDED. "
                        f"Decorate once, or make the two call sites agree.\n"
                    )
                except Exception:
                    pass
            return fn

        @functools.wraps(fn)
        def wrapper(*args, **kwargs):
            decision = args[0] if args else kwargs.get("decision", "")
            result = fn(*args, **kwargs)
            try:
                if decision in values:
                    if len(args) > 1:
                        reason = args[1]
                    else:
                        reason = kwargs.get("reason", "")
                    log_block_event(
                        hook_name=hook_name,
                        decision_shape=decision_shape,
                        reason=str(reason),
                        metadata=metadata,
                    )
            except Exception:
                # NEVER raise from the wrapper — telemetry must not break
                # the underlying hook decision path.
                pass
            return result

        wrapper._telemetry_wrapped = True  # type: ignore[attr-defined]
        wrapper._telemetry_config = config  # type: ignore[attr-defined]
        return wrapper

    return decorator


def can_user_recover(*, hook_name: str, block_reason: str) -> bool:
    """Return True if a documented recovery path exists for this block.

    Reads the exemption registry. Tries the new path
    ``.claude/config/hook_telemetry_exemptions.json`` first, falls back to
    the legacy ``.claude/config/hook_recovery_exemptions.json`` shipped
    with #970. Both share the same schema: ``{exemptions: [{hook_name,
    block_reason_contains}]}``.

    Args:
        hook_name: Filename of the hook that is about to deny.
        block_reason: The reason string the hook would output.

    Returns:
        True iff a matching exemption is found in either registry. False
        on any parse error, missing file, or no match.
    """
    try:
        for registry_path in _resolve_registry_paths():
            if not registry_path.exists():
                continue
            try:
                data = json.loads(registry_path.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, ValueError, OSError):
                continue
            exemptions = data.get("exemptions") if isinstance(data, dict) else None
            if not isinstance(exemptions, list):
                continue
            for entry in exemptions:
                if not isinstance(entry, dict):
                    continue
                if entry.get("hook_name") != hook_name:
                    continue
                reason_match = entry.get("block_reason_contains", "")
                if not isinstance(reason_match, str):
                    continue
                if reason_match and reason_match in block_reason:
                    return True
        return False
    except Exception:
        # NEVER raise — recovery checks must not break hook decisions.
        return False


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _resolve_log_path(start_dir: Optional[Path] = None) -> Path:
    """Resolve absolute path to ``.claude/logs/hook-blocks.jsonl``."""
    if start_dir is None:
        try:
            start_dir = Path.cwd()
        except (OSError, FileNotFoundError):
            start_dir = Path(".")
    return start_dir / LOG_FILE_RELATIVE


def _resolve_registry_paths(start_dir: Optional[Path] = None) -> list[Path]:
    """Resolve registry candidates in priority order: new, then legacy.

    First checks the in-repo plugins paths (development), then falls back
    to the cwd-relative ``.claude/config/`` paths.
    """
    here = Path(__file__).resolve().parent
    plugin_new = here.parent / "config" / "hook_telemetry_exemptions.json"
    plugin_legacy = here.parent / "config" / "hook_recovery_exemptions.json"

    if start_dir is None:
        try:
            start_dir = Path.cwd()
        except (OSError, FileNotFoundError):
            start_dir = Path(".")

    candidates: list[Path] = []
    if plugin_new.exists():
        candidates.append(plugin_new)
    candidates.append(start_dir / EXEMPTION_REGISTRY_PATH)
    if plugin_legacy.exists():
        candidates.append(plugin_legacy)
    candidates.append(start_dir / LEGACY_EXEMPTION_PATH)
    return candidates
