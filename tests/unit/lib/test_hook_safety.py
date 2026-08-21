"""Unit tests for plugins/autonomous-dev/lib/hook_safety.py.

Covers safe_main (hook-failure swallowing, Issue #953), command_registered
(slash command precondition probing, #953), and the HookDecision output
channel (#1588). The first two are critical to "hooks must never block Claude
Code due to their own infrastructure failure"; the third is critical to
"a hook cannot refuse without the refusal being recorded".
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT / "plugins" / "autonomous-dev" / "lib"))

import hook_safety  # noqa: E402  (sys.path manipulation must precede import)
import hook_telemetry  # noqa: E402
from hook_safety import (  # noqa: E402
    PRE_TOOL_USE,
    USER_PROMPT_SUBMIT,
    HookDecision,
    command_registered,
    safe_main,
)


# ---------------------------------------------------------------------------
# safe_main tests
# ---------------------------------------------------------------------------


class TestSafeMain:
    """Tests for the safe_main() outer wrap."""

    def test_safe_main_passes_through_normal_completion(self, capsys):
        """A function that returns None exits 0 with no warning."""
        with pytest.raises(SystemExit) as excinfo:
            safe_main(lambda: None)
        assert excinfo.value.code == 0
        captured = capsys.readouterr()
        assert "[hook warning]" not in captured.err

    def test_safe_main_swallows_exception_and_exits_zero(self, capsys):
        """An unhandled exception is converted to exit 0 + stderr warning."""
        def crashing():
            raise RuntimeError("simulated hook bug")

        with pytest.raises(SystemExit) as excinfo:
            safe_main(crashing)
        assert excinfo.value.code == 0
        captured = capsys.readouterr()
        assert captured.err.startswith("[hook warning]")
        assert "RuntimeError" in captured.err
        assert "simulated hook bug" in captured.err

    def test_safe_main_propagates_keyboardinterrupt(self):
        """Ctrl+C MUST NOT be swallowed (debugging UX)."""
        def interrupted():
            raise KeyboardInterrupt

        with pytest.raises(KeyboardInterrupt):
            safe_main(interrupted)

    def test_safe_main_propagates_systemexit(self):
        """Explicit SystemExit (e.g. sys.exit(2)) MUST pass through unchanged."""
        def exiting():
            raise SystemExit(2)

        with pytest.raises(SystemExit) as excinfo:
            safe_main(exiting)
        assert excinfo.value.code == 2

    def test_safe_main_propagates_systemexit_zero(self):
        """sys.exit(0) MUST pass through (not be caught as 'normal' return)."""
        def exiting():
            sys.exit(0)

        with pytest.raises(SystemExit) as excinfo:
            safe_main(exiting)
        assert excinfo.value.code == 0

    def test_safe_main_preserves_int_return(self):
        """An int return value MUST be the exit code (preserves block/warn)."""
        with pytest.raises(SystemExit) as excinfo:
            safe_main(lambda: 2)
        assert excinfo.value.code == 2

    def test_safe_main_preserves_int_return_one(self):
        """Return-1 (warning convention) MUST exit 1."""
        with pytest.raises(SystemExit) as excinfo:
            safe_main(lambda: 1)
        assert excinfo.value.code == 1

    def test_safe_main_swallows_importerror(self, capsys):
        """Broken imports inside main MUST NOT block."""
        def broken_import():
            import nonexistent_module_xyz_953  # noqa: F401

        with pytest.raises(SystemExit) as excinfo:
            safe_main(broken_import)
        assert excinfo.value.code == 0
        captured = capsys.readouterr()
        assert "[hook warning]" in captured.err
        # ModuleNotFoundError is a subclass of ImportError; either name is fine
        assert ("ImportError" in captured.err
                or "ModuleNotFoundError" in captured.err)

    def test_safe_main_warning_includes_hook_name(self, capsys):
        """Warning line MUST include the calling file name for diagnosis."""
        def crashing():
            raise ValueError("boom")

        with pytest.raises(SystemExit):
            safe_main(crashing)
        captured = capsys.readouterr()
        # The caller is this test file; safe_main walks one frame up.
        assert "test_hook_safety.py" in captured.err


# ---------------------------------------------------------------------------
# HookDecision output-channel tests (Issue #1588)
# ---------------------------------------------------------------------------


@pytest.fixture
def recorded_rows(monkeypatch):
    """Capture ``log_block_event`` calls instead of writing to the real log."""
    rows: list[dict] = []
    monkeypatch.setattr(
        hook_telemetry, "log_block_event", lambda **kw: rows.append(kw)
    )
    return rows


def _emitted(capsys) -> dict | None:
    """Parse the JSON payload safe_main wrote to stdout, or None if silent."""
    out = capsys.readouterr().out.strip()
    return json.loads(out) if out else None


class TestHookDecisionProtocols:
    """The two hook protocols are different and must not be collapsed."""

    def test_pre_tool_use_deny_payload_shape(self):
        """PreToolUse refuses via hookSpecificOutput.permissionDecision."""
        payload = HookDecision.deny(
            hook_name="h.py", reason="no", system_message="user msg"
        ).to_payload()
        assert payload == {
            "hookSpecificOutput": {
                "hookEventName": "PreToolUse",
                "permissionDecision": "deny",
                "permissionDecisionReason": "no",
            },
            "systemMessage": "user msg",
        }

    def test_user_prompt_submit_refusal_uses_a_different_field(self):
        """UserPromptSubmit has NO permissionDecision — it carries `error`.

        Emitting a permissionDecision on this event would be silently ignored
        by Claude Code, downgrading a refusal to an allow. The two shapes are
        asserted to be structurally distinct, not merely different strings.
        """
        payload = HookDecision(
            decision="block", reason="no", protocol=USER_PROMPT_SUBMIT
        ).to_payload()
        assert payload == {
            "hookSpecificOutput": {
                "hookEventName": "UserPromptSubmit",
                "error": "no",
            }
        }
        assert "permissionDecision" not in payload["hookSpecificOutput"]

    def test_pre_tool_use_vocabulary_rejects_user_prompt_submit_values(self):
        """`block` is not a PreToolUse decision. Collapsing is refused loudly."""
        with pytest.raises(ValueError, match="not valid for protocol"):
            HookDecision(decision="block", protocol=PRE_TOOL_USE)

    def test_user_prompt_submit_vocabulary_rejects_pre_tool_use_values(self):
        """And the converse arm: `deny` is not a UserPromptSubmit decision."""
        with pytest.raises(ValueError, match="not valid for protocol"):
            HookDecision(decision="deny", protocol=USER_PROMPT_SUBMIT)

    def test_unknown_protocol_is_rejected(self):
        """An unrecognised protocol must raise, never emit a guessed shape."""
        with pytest.raises(ValueError, match="Unknown hook protocol"):
            HookDecision(decision="deny", protocol="SessionStart")

    def test_allow_emits_no_payload(self):
        """Absence of an envelope IS the allow contract for standalone hooks."""
        assert HookDecision(decision="allow").to_payload() is None

    def test_exit_codes_are_protocol_specific(self):
        """PreToolUse signals via stdout (exit 0); UserPromptSubmit via exit 2."""
        assert HookDecision.deny(hook_name="h.py", reason="n").exit_code() == 0
        assert (
            HookDecision(
                decision="block", protocol=USER_PROMPT_SUBMIT
            ).exit_code()
            == 2
        )
        assert (
            HookDecision(decision="allow", protocol=USER_PROMPT_SUBMIT).exit_code()
            == 0
        )


class TestSafeMainEmitsAndRecords:
    """The channel-level fusion: one act, no branch that half-performs it."""

    def test_returned_refusal_is_emitted_and_recorded(self, capsys, recorded_rows):
        """Both arms of the fusion, in one call. This is the core guarantee."""
        with pytest.raises(SystemExit) as excinfo:
            safe_main(
                lambda: HookDecision.deny(
                    hook_name="h.py", reason="nope", metadata={"k": "v"}
                )
            )
        assert excinfo.value.code == 0

        payload = _emitted(capsys)
        assert payload["hookSpecificOutput"]["permissionDecision"] == "deny"
        assert payload["hookSpecificOutput"]["permissionDecisionReason"] == "nope"

        assert len(recorded_rows) == 1
        assert recorded_rows[0]["hook_name"] == "h.py"
        assert recorded_rows[0]["decision_shape"] == "dict"
        assert recorded_rows[0]["metadata"] == {"k": "v"}

    def test_returned_allow_emits_nothing_and_records_nothing(
        self, capsys, recorded_rows
    ):
        """The PERMITTING arm. A channel that always emits is not a channel."""
        with pytest.raises(SystemExit) as excinfo:
            safe_main(lambda: HookDecision(decision="allow", hook_name="h.py"))
        assert excinfo.value.code == 0
        assert _emitted(capsys) is None
        assert recorded_rows == []

    def test_recording_failure_still_emits_the_refusal(self, capsys, monkeypatch):
        """A logging bug MUST NOT convert a block into an allow.

        This is the single most important failure mode of the whole change:
        invisible enforcement is bad, absent enforcement is far worse.
        """
        def exploding(**_kwargs):
            raise RuntimeError("recorder is broken")

        monkeypatch.setattr(hook_telemetry, "log_block_event", exploding)

        with pytest.raises(SystemExit) as excinfo:
            safe_main(lambda: HookDecision.deny(hook_name="h.py", reason="nope"))
        assert excinfo.value.code == 0
        payload = _emitted(capsys)
        assert payload["hookSpecificOutput"]["permissionDecision"] == "deny", (
            "the refusal was lost when the recorder raised"
        )

    def test_sink_failure_falls_back_to_the_inline_envelope(
        self, capsys, monkeypatch
    ):
        """Even if the SINK itself raises, the refusal is still emitted."""
        def exploding(**_kwargs):
            raise RuntimeError("sink is broken")

        monkeypatch.setattr(hook_telemetry, "deny_and_record", exploding)

        with pytest.raises(SystemExit):
            safe_main(lambda: HookDecision.deny(hook_name="h.py", reason="nope"))
        payload = _emitted(capsys)
        assert payload["hookSpecificOutput"]["permissionDecision"] == "deny"

    def test_user_prompt_submit_refusal_exits_two_and_records(
        self, capsys, recorded_rows
    ):
        """The second protocol travels its own path, not the PreToolUse one."""
        with pytest.raises(SystemExit) as excinfo:
            safe_main(
                lambda: HookDecision(
                    decision="block",
                    reason="wrong command",
                    hook_name="p.py",
                    protocol=USER_PROMPT_SUBMIT,
                )
            )
        assert excinfo.value.code == 2
        assert _emitted(capsys)["hookSpecificOutput"]["error"] == "wrong command"
        assert len(recorded_rows) == 1
        assert recorded_rows[0]["hook_name"] == "p.py"

    def test_hook_name_defaults_to_the_calling_file(self, capsys, recorded_rows):
        """An unattributed refusal is recorded against its calling file."""
        with pytest.raises(SystemExit):
            safe_main(lambda: HookDecision.deny(hook_name="", reason="nope"))
        assert recorded_rows[0]["hook_name"] == "test_hook_safety.py"

    def test_a_refusal_is_recorded_exactly_once(self, capsys, recorded_rows):
        """No double-record: the sink path and the fallback are exclusive."""
        with pytest.raises(SystemExit):
            safe_main(lambda: HookDecision.deny(hook_name="h.py", reason="nope"))
        assert len(recorded_rows) == 1


class TestFailurePathsOnTheEmissionChannel:
    """Issue #1588 remediation: what happens when the ONE path goes wrong.

    Every migrated refusal now travels a single channel. That makes the
    channel's failure modes the failure modes of every guard in the repo, so
    each one is driven here rather than reasoned about.

    The defect these lock: recording happens BEFORE emission, so a failure on
    the emission side leaves a ``hook-blocks.jsonl`` row asserting a refusal
    that never reached Claude Code. Exit 0 with empty stdout is the established
    allow contract, so the write proceeds AND the audit log claims it was
    blocked — forged evidence, which is strictly worse than the unknowable zero
    the whole change exists to eliminate.
    """

    class _BrokenStdout:
        """A stdout whose ``write`` fails the way a closed pipe does."""

        def write(self, _text: str) -> int:
            raise OSError("stdout is closed")

        def flush(self) -> None:
            pass

    def test_unserialisable_reason_still_emits_a_deny_envelope(
        self, capsys, recorded_rows
    ):
        """THE BLOCKING-1 REPRODUCER, driven through the real ``safe_main``.

        ``reason: str`` is an annotation, not enforcement — nothing stops a
        hook passing a ``Path``, an exception object, or a dict. That value
        reaches ``json.dumps`` unmodified, which raises ``TypeError``, which
        was swallowed. The refusal must survive the coercion, not be dropped.
        """
        with pytest.raises(SystemExit):
            safe_main(
                lambda: HookDecision.deny(
                    hook_name="h.py", reason=Path("/not/a/string")
                )
            )

        payload = _emitted(capsys)
        assert payload is not None, (
            "a refusal with a non-serialisable reason produced EMPTY stdout. "
            "Exit 0 + empty stdout is the allow contract, so the guard did not "
            "fire while a hook-blocks.jsonl row says it did."
        )
        assert payload["hookSpecificOutput"]["permissionDecision"] == "deny"
        assert "/not/a/string" in payload["hookSpecificOutput"][
            "permissionDecisionReason"
        ], "the reason was dropped rather than coerced"

    def test_a_recorded_row_never_outlives_the_emission_it_describes(
        self, capsys, recorded_rows
    ):
        """The forgery invariant, stated directly rather than by proxy.

        The block log is the evidence base this whole changeset exists to
        establish. A row for a refusal that did not ship makes every count
        drawn from it an over-count of enforcement.
        """
        with pytest.raises(SystemExit):
            safe_main(
                lambda: HookDecision.deny(
                    hook_name="h.py", reason=Path("/not/a/string")
                )
            )
        emitted = bool(capsys.readouterr().out.strip())
        assert not (recorded_rows and not emitted), (
            f"{len(recorded_rows)} row(s) recorded for a refusal that emitted "
            f"nothing. The block log is forged."
        )

    def test_control_a_serialisable_reason_is_emitted_unchanged(
        self, capsys, recorded_rows
    ):
        """PERMITTING ARM: the normal refusal must be untouched by the fix.

        The coercion path must be reachable ONLY on failure — a fix that
        routed every payload through ``default=str`` would pass the test above
        while quietly changing every refusal in the repo.
        """
        with pytest.raises(SystemExit) as excinfo:
            safe_main(
                lambda: HookDecision.deny(
                    hook_name="h.py", reason="plain string", system_message="msg"
                )
            )
        assert excinfo.value.code == 0
        assert _emitted(capsys) == {
            "hookSpecificOutput": {
                "hookEventName": "PreToolUse",
                "permissionDecision": "deny",
                "permissionDecisionReason": "plain string",
            },
            "systemMessage": "msg",
        }
        assert len(recorded_rows) == 1

    def test_stdout_failure_is_loud_and_does_not_exit_zero(
        self, capsys, recorded_rows, monkeypatch
    ):
        """An unwritable stdout is unrecoverable — it MUST NOT be silent.

        Distinct from the serialisation fault above: that one is recoverable
        by coercion, this one is not. The refusal genuinely does not reach
        Claude Code, a row already exists, and the only honest response is to
        say so on stderr and refuse to exit 0 as if nothing happened.
        """
        monkeypatch.setattr(sys, "stdout", self._BrokenStdout())

        with pytest.raises(SystemExit) as excinfo:
            safe_main(lambda: HookDecision.deny(hook_name="h.py", reason="nope"))

        err = capsys.readouterr().err
        assert "[hook error]" in err, (
            "a refusal was decided but not emitted, and nothing was written to "
            "stderr. The guard silently failed open."
        )
        assert "h.py" in err, "the stderr line does not name the hook"
        assert "hook-blocks.jsonl" in err, (
            "the stderr line does not warn that a row exists for a block that "
            "did not ship, so the over-count is undiscoverable"
        )
        assert excinfo.value.code != 0, (
            "exit 0 with empty stdout IS the allow contract — a refusal that "
            "could not be emitted must not exit that way"
        )

    def test_control_a_working_stdout_still_exits_zero(self, capsys, recorded_rows):
        """PERMITTING ARM for the exit-code change: normal denies exit 0.

        A PreToolUse refusal signals through stdout JSON, not through the exit
        status. If the fix above raised the exit code on the healthy path it
        would turn every block into a hook error.
        """
        with pytest.raises(SystemExit) as excinfo:
            safe_main(lambda: HookDecision.deny(hook_name="h.py", reason="nope"))
        assert excinfo.value.code == 0
        assert _emitted(capsys)["hookSpecificOutput"]["permissionDecision"] == "deny"

    def test_sink_payload_without_a_decision_is_rebuilt_before_emission(
        self, capsys, monkeypatch
    ):
        """Same forged-evidence outcome, through a different door.

        ``emit_decision`` branched only on ``payload is None``. A sink that
        returns any other dict — ``{}`` from a regression, a patched double —
        was written to stdout verbatim. An envelope with no
        ``permissionDecision`` reads as an ALLOW, while the row is recorded.
        """
        monkeypatch.setattr(hook_telemetry, "deny_and_record", lambda **_kw: {})

        with pytest.raises(SystemExit):
            safe_main(lambda: HookDecision.deny(hook_name="h.py", reason="nope"))

        payload = _emitted(capsys)
        assert payload is not None, "nothing was emitted at all"
        assert payload.get("hookSpecificOutput", {}).get("permissionDecision") == (
            "deny"
        ), (
            f"emitted {payload!r} — an envelope without permissionDecision is "
            f"read as an allow by Claude Code while the row says 'blocked'"
        )

    def test_control_a_wellformed_sink_payload_is_emitted_verbatim(
        self, capsys, monkeypatch
    ):
        """PERMITTING ARM: the post-condition must not rewrite good payloads.

        The sink is the canonical envelope builder. A post-condition that
        always rebuilt would silently discard whatever the sink adds.
        """
        marker = {
            "hookSpecificOutput": {
                "hookEventName": "PreToolUse",
                "permissionDecision": "deny",
                "permissionDecisionReason": "from the sink",
            },
            "systemMessage": "sink-owned",
        }
        monkeypatch.setattr(hook_telemetry, "deny_and_record", lambda **_kw: marker)

        with pytest.raises(SystemExit):
            safe_main(lambda: HookDecision.deny(hook_name="h.py", reason="ignored"))

        assert _emitted(capsys) == marker, (
            "the sink's envelope was rebuilt even though it carried the "
            "decision — the post-condition is too aggressive"
        )

    def test_unimportable_telemetry_is_not_silent(self, capsys, monkeypatch):
        """Zero rows and empty stderr is the unknowable zero, reintroduced.

        Enforcement holds here — the refusal is still emitted — so this is not
        fail-open. But the audit trail can silently reach zero, which is the
        exact condition Issue #1588 exists to eliminate. ``log_block_event``
        is already loud on ``OSError``; these two handlers must match it.
        """
        monkeypatch.setitem(sys.modules, "hook_telemetry", None)

        with pytest.raises(SystemExit):
            safe_main(lambda: HookDecision.deny(hook_name="h.py", reason="nope"))

        captured = capsys.readouterr()
        assert json.loads(captured.out)["hookSpecificOutput"][
            "permissionDecision"
        ] == "deny", "enforcement was lost, not just the row"
        assert "[hook-telemetry]" in captured.err, (
            "the recorder was unreachable and NOTHING was said. Zero rows with "
            "no stderr is indistinguishable from a guard that never fired."
        )

    def test_control_reachable_telemetry_says_nothing(self, capsys, recorded_rows):
        """PERMITTING ARM: the healthy path must stay quiet.

        A warning that fires on every refusal is noise nobody reads, and would
        make the assertion above pass for the wrong reason.
        """
        with pytest.raises(SystemExit):
            safe_main(lambda: HookDecision.deny(hook_name="h.py", reason="nope"))
        assert "[hook-telemetry]" not in capsys.readouterr().err
        assert len(recorded_rows) == 1

    def test_unrecordable_non_deny_refusal_is_not_silent(self, capsys, monkeypatch):
        """The ``ask``/``UserPromptSubmit`` arm records through a second path.

        ``_record_refusal`` had the same silent ``except BaseException``, so
        this arm needs its own control — the deny arm's coverage says nothing
        about it.
        """
        def exploding(**_kwargs):
            raise RuntimeError("recorder is broken")

        monkeypatch.setattr(hook_telemetry, "log_block_event", exploding)

        with pytest.raises(SystemExit):
            safe_main(
                lambda: HookDecision(decision="ask", hook_name="h.py", reason="hmm")
            )

        captured = capsys.readouterr()
        assert json.loads(captured.out)["hookSpecificOutput"][
            "permissionDecision"
        ] == "ask"
        assert "[hook-telemetry]" in captured.err, (
            "an 'ask' refusal failed to record and said nothing"
        )

    def test_deny_sink_handler_does_not_swallow_keyboard_interrupt(self, monkeypatch):
        """``except BaseException`` contradicted ``safe_main`` in its own module.

        ``safe_main`` deliberately re-raises ``KeyboardInterrupt``; the two
        telemetry handlers caught it. ``except Exception`` satisfies the stated
        intent that telemetry never outranks enforcement.
        """
        def interrupted(**_kwargs):
            raise KeyboardInterrupt

        monkeypatch.setattr(hook_telemetry, "deny_and_record", interrupted)

        with pytest.raises(KeyboardInterrupt):
            safe_main(lambda: HookDecision.deny(hook_name="h.py", reason="nope"))

    def test_record_refusal_handler_does_not_swallow_keyboard_interrupt(
        self, monkeypatch
    ):
        """The second handler, driven independently of the first."""
        def interrupted(**_kwargs):
            raise KeyboardInterrupt

        monkeypatch.setattr(hook_telemetry, "log_block_event", interrupted)

        with pytest.raises(KeyboardInterrupt):
            safe_main(
                lambda: HookDecision(decision="ask", hook_name="h.py", reason="hmm")
            )

    def test_control_ordinary_recorder_failure_is_still_swallowed(
        self, capsys, monkeypatch
    ):
        """PERMITTING ARM for the narrowed handler: ``Exception`` still caught.

        Narrowing ``BaseException`` to ``Exception`` must not turn a recorder
        bug into a hook crash — telemetry still never outranks enforcement.
        """
        def exploding(**_kwargs):
            raise RuntimeError("recorder is broken")

        monkeypatch.setattr(hook_telemetry, "deny_and_record", exploding)

        with pytest.raises(SystemExit) as excinfo:
            safe_main(lambda: HookDecision.deny(hook_name="h.py", reason="nope"))
        assert excinfo.value.code == 0
        assert _emitted(capsys)["hookSpecificOutput"]["permissionDecision"] == "deny"

    def test_emit_decision_docstring_does_not_claim_unconditional_emission(self):
        """A false safety claim in a docstring is how a live defect ships.

        ``emit_decision`` documented "There is no branch on which a refusal is
        decided and nothing is emitted" while three such branches existed. That
        sentence let the defect past two review rounds.
        """
        doc = " ".join((hook_safety.emit_decision.__doc__ or "").split())
        assert (
            "There is no branch on which a refusal is decided and nothing is "
            "emitted" not in doc
        ), (
            "emit_decision still claims unconditional emission. State the "
            "actual failure modes instead."
        )


class TestUserPromptSubmitRefusalReachesTheUser:
    """FINDING-5. On a ``UserPromptSubmit`` refusal, stderr IS the user channel.

    ``UserPromptSubmit`` signals refusal by exit 2, and on exit 2 the stdout
    JSON is not surfaced to the user — stderr is. A hook migrating onto
    ``HookDecision`` therefore has to write the human message to stderr, or it
    refuses with the message nowhere.

    The premise is READ FROM THE LIVE REFUSER rather than restated here. The
    previous test for this path mirrored the implementation (build a payload,
    assert the payload), which is why it stayed green while the channel the
    user actually reads was empty.
    """

    _LIVE_REFUSER = (
        REPO_ROOT
        / "plugins"
        / "autonomous-dev"
        / "hooks"
        / "unified_prompt_validator.py"
    )

    def test_premise_the_live_refuser_uses_all_three_channels(self):
        """The shape a migrated hook has to preserve, taken from the hook itself.

        If this premise breaks, the behavioural test below is asserting a
        convention that no longer exists and should be re-derived rather than
        kept passing.
        """
        src = self._LIVE_REFUSER.read_text(encoding="utf-8")
        assert "print(message, file=sys.stderr)" in src, (
            f"{self._LIVE_REFUSER.name} no longer writes its block message to "
            f"stderr. The premise that stderr is the UserPromptSubmit user "
            f"channel came from this hook; re-derive it before trusting the "
            f"test below."
        )
        assert '"hookEventName": "UserPromptSubmit"' in src, (
            "premise: this hook is a UserPromptSubmit refuser"
        )
        assert "return 2" in src, "premise: it signals its refusal by exit 2"

    def test_user_prompt_submit_refusal_writes_the_message_to_stderr(
        self, capsys, recorded_rows
    ):
        """THE REPRODUCER. Measured through the real ``safe_main``, not a payload.

        Before the fix this produced ``exit=2 rows=1 stdout={...} stderr=''`` —
        a refusal with no message on the only channel the user sees.
        """
        with pytest.raises(SystemExit) as excinfo:
            safe_main(
                lambda: HookDecision(
                    decision="block",
                    reason="Use /implement for production code",
                    hook_name="p.py",
                    protocol=USER_PROMPT_SUBMIT,
                )
            )
        captured = capsys.readouterr()

        assert excinfo.value.code == 2, "premise: UserPromptSubmit refuses by exit 2"
        assert "Use /implement for production code" in captured.err, (
            f"a UserPromptSubmit refusal exited 2 with stderr={captured.err!r}. "
            f"On exit 2 the stdout envelope is not surfaced, so the user is "
            f"refused with no message anywhere. Write the reason to stderr "
            f"before the stdout write, as unified_prompt_validator.py does."
        )
        assert json.loads(captured.out.strip())["hookSpecificOutput"]["error"] == (
            "Use /implement for production code"
        ), "the stdout envelope must still be emitted — stderr is additive"
        assert len(recorded_rows) == 1, "and the row is still written"

    def test_system_message_is_preferred_on_stderr_when_present(
        self, capsys, recorded_rows
    ):
        """``system_message`` is the user-facing text when a hook supplies one.

        ``reason`` is model-visible; ``system_message`` is written for the
        human. When both exist the human's copy is the one to surface.
        """
        with pytest.raises(SystemExit):
            safe_main(
                lambda: HookDecision(
                    decision="block",
                    reason="model-visible reason",
                    system_message="HUMAN: run /implement instead",
                    hook_name="p.py",
                    protocol=USER_PROMPT_SUBMIT,
                )
            )
        err = capsys.readouterr().err
        assert "HUMAN: run /implement instead" in err, (
            f"system_message was not surfaced to the user (stderr={err!r})"
        )

    def test_control_a_user_prompt_submit_allow_writes_no_stderr_noise(
        self, capsys, recorded_rows
    ):
        """PERMITTING ARM. The stderr write must be on the REFUSAL branch only.

        A fix that wrote unconditionally would pass the reproducer above while
        making every permitted prompt print to stderr — noise that trains
        operators to ignore the channel the refusal depends on.
        """
        with pytest.raises(SystemExit) as excinfo:
            safe_main(
                lambda: HookDecision(
                    decision="allow",
                    reason="fine",
                    hook_name="p.py",
                    protocol=USER_PROMPT_SUBMIT,
                )
            )
        captured = capsys.readouterr()
        assert excinfo.value.code == 0
        assert captured.err == "", (
            f"an ALLOWED prompt wrote {captured.err!r} to stderr. The refusal "
            f"channel must stay quiet on the permitting path."
        )
        assert captured.out.strip() == "", "an allow emits no envelope"
        assert recorded_rows == []

    def test_control_pre_tool_use_deny_is_unaffected(self, capsys, recorded_rows):
        """PERMITTING ARM, other protocol. PreToolUse exits 0 and stdout IS read.

        Its stderr is reserved for genuine hook faults (``[hook error] ...``),
        so a deny must not start printing there.
        """
        with pytest.raises(SystemExit) as excinfo:
            safe_main(
                lambda: HookDecision.deny(hook_name="h.py", reason="blocked here")
            )
        captured = capsys.readouterr()
        assert excinfo.value.code == 0
        assert captured.err == "", (
            f"a PreToolUse deny wrote {captured.err!r} to stderr. The stderr "
            f"write is a UserPromptSubmit-only affordance; PreToolUse "
            f"communicates entirely on stdout."
        )
        assert json.loads(captured.out.strip())["hookSpecificOutput"][
            "permissionDecision"
        ] == "deny"


class TestRenderDegradesWithoutEscaping:
    """The ``_render`` fallback chain must not raise out of the module.

    ``_render`` is reached by every migrated refusal in the repo, and
    ``emit_decision`` calls it OUTSIDE ``safe_main``'s own ``try``. Anything
    that escapes here is an uncaught traceback on a path whose entire purpose
    is to keep a refusal alive when the message is broken.
    """

    class _HostileStr:
        """A reason object whose ``__str__`` raises — the case tier 3 names."""

        def __str__(self) -> str:
            raise RuntimeError("__str__ is hostile")

        __repr__ = __str__

    def test_a_reason_whose_str_raises_still_emits_a_refusal(
        self, capsys, recorded_rows
    ):
        """THE REPRODUCER. ``default=str`` invokes the hostile ``__str__`` itself.

        Tier 2 caught only ``(TypeError, ValueError)``, so a ``RuntimeError``
        from ``__str__`` escaped ``_render`` -> ``emit_decision`` -> ``safe_main``
        (which calls it outside its own ``try``) and became an uncaught
        traceback with EMPTY stdout — the allow contract, from the fallback
        chain built to prevent exactly that.

        Tier 3 at ``hook_safety.py`` anticipates this case in a comment ("a
        ``__str__`` that raises must not win") and could never execute, because
        tier 2 reached the same ``__str__`` unguarded. Nothing in the suite
        drove it.
        """
        with pytest.raises(SystemExit) as excinfo:
            safe_main(
                lambda: HookDecision.deny(
                    hook_name="h.py", reason=self._HostileStr()
                )
            )
        assert excinfo.value.code == 0, (
            "a hostile __str__ escaped as a crash instead of degrading"
        )

        payload = _emitted(capsys)
        assert payload is not None, (
            "a refusal whose reason cannot be rendered produced EMPTY stdout. "
            "Exit 0 + empty stdout is the ALLOW contract, so the guard did not "
            "fire while a hook-blocks.jsonl row says it did."
        )
        assert payload["hookSpecificOutput"]["permissionDecision"] == "deny", (
            "the decision was degraded along with the message; only the "
            "message may degrade"
        )

    def test_the_tier_three_last_resort_is_watched_working(self):
        """Drive ``_render`` directly so the last-resort text is OBSERVED.

        The test above proves a deny still ships. This proves WHICH branch
        produced it: the hand-rebuilt minimal envelope, whose reason is the
        constant substituted when ``str(reason)`` raises. A guard that names
        the case it handles but is never reached is the same shape as a
        docstring claiming an enforcement the code does not implement.
        """
        decision = HookDecision.deny(hook_name="h.py", reason=self._HostileStr())
        rendered = json.loads(
            hook_safety._render({"reason": decision.reason}, decision)
        )
        assert rendered["hookSpecificOutput"]["permissionDecisionReason"] == (
            "(refusal reason could not be rendered)"
        ), (
            f"tier 3 was not the branch that produced {rendered!r}. If tier 2 "
            f"rendered this payload it did so by calling the hostile __str__, "
            f"which raises — so tier 3 remains unreachable and its guard is "
            f"decorative."
        )
        assert rendered["hookSpecificOutput"]["permissionDecision"] == "deny"

    def test_control_an_ordinary_payload_is_unchanged_by_the_broadening(self):
        """PERMITTING ARM. Widening tier 2 must not alter the normal render.

        Tier 1 handles every serialisable payload and must keep doing so —
        byte-for-byte, including key order — or the broadening has quietly
        rerouted every refusal in the repo through a degradation path.
        """
        decision = HookDecision.deny(hook_name="h.py", reason="plain string")
        payload = decision.to_payload()
        assert hook_safety._render(payload, decision) == json.dumps(payload)

    def test_control_a_merely_unserialisable_reason_still_uses_tier_two(self):
        """PERMITTING ARM. A ``Path`` reason must still be COERCED, not blanked.

        The distinction the broadening must preserve: ``default=str`` works on
        a ``Path`` and the real text survives. Only a ``__str__`` that raises
        falls through to the constant. A tier 2 that swallowed too much would
        pass the reproducer above by degrading everything.
        """
        decision = HookDecision.deny(hook_name="h.py", reason=Path("/not/a/string"))
        rendered = json.loads(
            hook_safety._render({"reason": decision.reason}, decision)
        )
        assert rendered == {"reason": "/not/a/string"}, (
            f"a Path reason no longer coerces through tier 2 (got {rendered!r}); "
            f"the message was blanked when it did not need to be"
        )


class TestSafeMainBackwardCompatibility:
    """The 26 hooks that do NOT return a decision must be untouched.

    Twenty hooks never emit at all and six emitters are not migrated by
    #1588. Their contract is asserted here as a SET of behaviours rather than
    assumed, because a regression in this wrapper reaches every hook at once.
    """

    def test_none_return_still_exits_zero(self, capsys, recorded_rows):
        with pytest.raises(SystemExit) as excinfo:
            safe_main(lambda: None)
        assert excinfo.value.code == 0
        assert _emitted(capsys) is None
        assert recorded_rows == []

    @pytest.mark.parametrize("code", [0, 1, 2, 3])
    def test_int_return_still_becomes_the_exit_code(
        self, code, capsys, recorded_rows
    ):
        with pytest.raises(SystemExit) as excinfo:
            safe_main(lambda: code)
        assert excinfo.value.code == code
        assert _emitted(capsys) is None, (
            "safe_main emitted a payload for an int-returning hook — the "
            "unmigrated hooks print for themselves and would now double-emit"
        )
        assert recorded_rows == []

    def test_a_hook_that_prints_for_itself_is_not_interfered_with(self, capsys):
        """The six unmigrated emitters print then return an int. Unchanged."""
        def self_printing():
            print(json.dumps({"hookSpecificOutput": {"permissionDecision": "deny"}}))
            return 0

        with pytest.raises(SystemExit) as excinfo:
            safe_main(self_printing)
        assert excinfo.value.code == 0
        assert capsys.readouterr().out.count("permissionDecision") == 1, (
            "the payload was emitted more than once"
        )

    def test_crash_still_degrades_to_exit_zero(self, capsys, recorded_rows):
        with pytest.raises(SystemExit) as excinfo:
            safe_main(lambda: (_ for _ in ()).throw(RuntimeError("boom")))
        assert excinfo.value.code == 0
        assert "[hook warning]" in capsys.readouterr().err
        assert recorded_rows == []


# ---------------------------------------------------------------------------
# command_registered tests
# ---------------------------------------------------------------------------


class TestCommandRegistered:
    """Tests for command_registered() slash-command lookup."""

    def test_command_registered_finds_user_global_command(
        self, tmp_path, monkeypatch
    ):
        """A command file under ~/.claude/commands/ MUST be discovered."""
        fake_home = tmp_path / "home"
        (fake_home / ".claude" / "commands").mkdir(parents=True)
        (fake_home / ".claude" / "commands" / "create-issue.md").write_text(
            "# create-issue\n"
        )
        # Move cwd somewhere with no .claude/commands so only home matches.
        empty_cwd = tmp_path / "elsewhere"
        empty_cwd.mkdir()
        monkeypatch.setenv("HOME", str(fake_home))
        monkeypatch.chdir(empty_cwd)

        assert command_registered("create-issue") is True

    def test_command_registered_finds_project_command(
        self, tmp_path, monkeypatch
    ):
        """A command file under ./.claude/commands/ MUST be discovered."""
        project = tmp_path / "project"
        (project / ".claude" / "commands").mkdir(parents=True)
        (project / ".claude" / "commands" / "my-cmd.md").write_text("# my-cmd\n")
        # Empty fake home so the project-local lookup is the only hit.
        fake_home = tmp_path / "home"
        fake_home.mkdir()
        monkeypatch.setenv("HOME", str(fake_home))
        monkeypatch.chdir(project)

        assert command_registered("my-cmd") is True

    def test_command_registered_finds_installed_plugin_command(
        self, tmp_path, monkeypatch
    ):
        """An entry in installed_plugins.json MUST be discovered."""
        fake_home = tmp_path / "home"
        (fake_home / ".claude").mkdir(parents=True)
        manifest = fake_home / ".claude" / "installed_plugins.json"
        manifest.write_text(json.dumps({
            "commands": [{"name": "from-manifest"}],
        }))
        empty_cwd = tmp_path / "elsewhere"
        empty_cwd.mkdir()
        monkeypatch.setenv("HOME", str(fake_home))
        monkeypatch.chdir(empty_cwd)

        assert command_registered("from-manifest") is True

    def test_command_registered_finds_plugins_subdir_manifest(
        self, tmp_path, monkeypatch
    ):
        """Manifest at ~/.claude/plugins/installed_plugins.json MUST work."""
        fake_home = tmp_path / "home"
        (fake_home / ".claude" / "plugins").mkdir(parents=True)
        manifest = fake_home / ".claude" / "plugins" / "installed_plugins.json"
        manifest.write_text(json.dumps({
            "installed_plugins": {
                "autonomous-dev": {"commands": [{"name": "deep-cmd"}]},
            },
        }))
        empty_cwd = tmp_path / "elsewhere"
        empty_cwd.mkdir()
        monkeypatch.setenv("HOME", str(fake_home))
        monkeypatch.chdir(empty_cwd)

        assert command_registered("deep-cmd") is True

    def test_command_registered_returns_false_when_truly_missing(
        self, tmp_path, monkeypatch
    ):
        """No command anywhere → False (the only fail-OPEN signal)."""
        fake_home = tmp_path / "home"
        fake_home.mkdir()
        empty_cwd = tmp_path / "elsewhere"
        empty_cwd.mkdir()
        monkeypatch.setenv("HOME", str(fake_home))
        monkeypatch.chdir(empty_cwd)

        assert command_registered("does-not-exist-953") is False

    def test_command_registered_strips_leading_slash(
        self, tmp_path, monkeypatch
    ):
        """Both 'foo' and '/foo' MUST resolve to the same lookup."""
        fake_home = tmp_path / "home"
        (fake_home / ".claude" / "commands").mkdir(parents=True)
        (fake_home / ".claude" / "commands" / "foo.md").write_text("# foo\n")
        empty_cwd = tmp_path / "elsewhere"
        empty_cwd.mkdir()
        monkeypatch.setenv("HOME", str(fake_home))
        monkeypatch.chdir(empty_cwd)

        assert command_registered("foo") is True
        assert command_registered("/foo") is True

    def test_command_registered_handles_bad_json_gracefully(
        self, tmp_path, monkeypatch
    ):
        """Malformed installed_plugins.json MUST NOT crash the lookup."""
        fake_home = tmp_path / "home"
        (fake_home / ".claude").mkdir(parents=True)
        manifest = fake_home / ".claude" / "installed_plugins.json"
        manifest.write_text("{this is not valid json")
        # Provide a real command file in the project dir so we get a
        # deterministic True (proves the bad-JSON path didn't blow up).
        project = tmp_path / "project"
        (project / ".claude" / "commands").mkdir(parents=True)
        (project / ".claude" / "commands" / "lookup-me.md").write_text("# x\n")
        monkeypatch.setenv("HOME", str(fake_home))
        monkeypatch.chdir(project)

        # Should not raise — bad JSON is treated as "no info".
        assert command_registered("lookup-me") is True
        # And a missing command should still resolve to False (not crash).
        assert command_registered("nope-953") is False

    def test_command_registered_empty_name_returns_true(
        self, tmp_path, monkeypatch
    ):
        """An empty name is fail-CLOSED (we cannot say it's missing)."""
        fake_home = tmp_path / "home"
        fake_home.mkdir()
        empty_cwd = tmp_path / "elsewhere"
        empty_cwd.mkdir()
        monkeypatch.setenv("HOME", str(fake_home))
        monkeypatch.chdir(empty_cwd)

        # Empty/whitespace names are not actionable — fail-CLOSED.
        assert command_registered("") is True
        assert command_registered("/") is True

    def test_command_registered_fail_closed_on_unexpected_error(
        self, monkeypatch
    ):
        """If lookup raises unexpectedly, return True (fail-CLOSED).

        This protects the security barrier: a programming bug or unexpected
        runtime failure MUST NOT silently downgrade a deny path to allow.
        We simulate the unexpected error by patching the leading-slash
        helper to raise — that runs early in command_registered() before
        the per-step try/except blocks would catch it.
        """
        def boom(_name):
            raise RuntimeError("simulated unexpected lookup failure")

        monkeypatch.setattr(hook_safety, "_strip_leading_slash", boom)

        # Even with the lookup unexpectedly broken, fail-CLOSED → True.
        assert command_registered("anything") is True

    def test_command_registered_string_command_entries(
        self, tmp_path, monkeypatch
    ):
        """Manifest entries that are strings (not dicts) MUST also work."""
        fake_home = tmp_path / "home"
        (fake_home / ".claude").mkdir(parents=True)
        manifest = fake_home / ".claude" / "installed_plugins.json"
        manifest.write_text(json.dumps({
            "commands": ["string-style-cmd"],
        }))
        empty_cwd = tmp_path / "elsewhere"
        empty_cwd.mkdir()
        monkeypatch.setenv("HOME", str(fake_home))
        monkeypatch.chdir(empty_cwd)

        assert command_registered("string-style-cmd") is True
