"""Unit tests for verdict-aware alignment enforcement in unified_pre_tool.py.

Issue #1467 extends the Issue #585 alignment gate from a boolean
(``alignment_passed``) to a signed 4-value verdict (``alignment_verdict``).
The hook must:

1. Accept only verdicts in ``ALLOWED_VERDICTS`` (``auto_pass``,
   ``user_approved``) — Amendment 2: membership only, no per-value branching.
2. Deny when the verdict is present but disallowed, EVEN for pipeline agents
   (anti-bypass — the pre-check runs BEFORE the PIPELINE_AGENTS early-return).
3. Degrade gracefully to legacy boolean behavior when the verdict field is
   absent (zero blast radius for pre-#1467 states and consumer repos).
4. Fail closed on tampering, missing files, and HMAC failures.

Style mirrors ``tests/unit/hooks/test_alignment_gate_enforcement.py`` (#585)
and the fail-closed assertions of Issue #1471.

GitHub Issue: #1467
"""

import json
import sys
from datetime import datetime
from pathlib import Path

import pytest

HOOK_DIR = Path(__file__).resolve().parents[3] / "plugins" / "autonomous-dev" / "hooks"
LIB_DIR = Path(__file__).resolve().parents[3] / "plugins" / "autonomous-dev" / "lib"
for _p in (str(HOOK_DIR), str(LIB_DIR)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import pipeline_state  # noqa: E402
import unified_pre_tool as hook  # noqa: E402
from pipeline_state import sign_state  # noqa: E402


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def clean_env(monkeypatch):
    """Reset relevant env vars for each test."""
    for key in (
        "SANDBOX_ENABLED", "PRE_TOOL_MCP_SECURITY", "PRE_TOOL_AGENT_AUTH",
        "PRE_TOOL_BATCH_PERMISSION", "MCP_AUTO_APPROVE", "ENFORCEMENT_LEVEL",
        "CLAUDE_AGENT_NAME", "PIPELINE_STATE_FILE",
    ):
        monkeypatch.delenv(key, raising=False)
    monkeypatch.setenv("PRE_TOOL_MCP_SECURITY", "true")
    monkeypatch.setenv("PRE_TOOL_AGENT_AUTH", "true")


@pytest.fixture(autouse=True)
def isolate_stale_state_failopen(tmp_path, monkeypatch):
    """Neutralize the Issue #753 stale-state fail-open for tamper assertions.

    ``verify_state_hmac`` deliberately fails OPEN when the legacy sentinel
    (``<repo>/.claude/local/implement_pipeline_state.json``) is more than an
    hour old. In a developer worktree that file exists and ages, so a tamper
    test would pass or fail depending on wall-clock time rather than on the
    HMAC. Point the staleness probe at a freshly written tmp sentinel so these
    tests measure signature verification only (Issue #1184 isolation rule).
    """
    sentinel = tmp_path / "legacy_sentinel.json"
    sentinel.write_text("{}")
    monkeypatch.setattr(pipeline_state, "get_legacy_sentinel_path", lambda: sentinel)


@pytest.fixture
def make_state(tmp_path, monkeypatch):
    """Write a signed pipeline state and point PIPELINE_STATE_FILE at it."""

    def _make(**fields) -> str:
        state = {
            "session_start": datetime.now().isoformat(),
            "mode": "full",
            "run_id": "test-verdict-1467",
            "explicitly_invoked": True,
        }
        state.update(fields)
        signed = sign_state(state, "test-session")
        path = tmp_path / "implement_pipeline_state.json"
        path.write_text(json.dumps(signed))
        monkeypatch.setenv("PIPELINE_STATE_FILE", str(path))
        return str(path)

    return _make


# ---------------------------------------------------------------------------
# 1. _has_alignment_passed is verdict-aware
# ---------------------------------------------------------------------------


class TestHasAlignmentPassedVerdictAware:
    """The gate reads the verdict when present, the boolean when it is not."""

    @pytest.mark.parametrize("verdict", ["auto_pass", "user_approved"])
    def test_allowed_verdicts_pass(self, make_state, verdict):
        make_state(alignment_passed=True, alignment_verdict=verdict)
        assert hook._has_alignment_passed() is True

    @pytest.mark.parametrize("verdict", ["escalate", "block", "", "in_scope", "unknown"])
    def test_disallowed_verdicts_fail(self, make_state, verdict):
        """Anything outside ALLOWED_VERDICTS is 'not passed' — including typos."""
        make_state(alignment_passed=True, alignment_verdict=verdict)
        assert hook._has_alignment_passed() is False

    def test_allowed_verdict_with_false_boolean_fails(self, make_state):
        """Both signals must agree — a pass verdict cannot resurrect a False flag."""
        make_state(alignment_passed=False, alignment_verdict="auto_pass")
        assert hook._has_alignment_passed() is False

    def test_legacy_state_without_verdict_uses_boolean(self, make_state):
        """Zero blast radius: pre-#1467 states behave exactly as before."""
        make_state(alignment_passed=True)
        assert hook._has_alignment_passed() is True

    def test_legacy_state_false_boolean_still_fails(self, make_state):
        make_state(alignment_passed=False)
        assert hook._has_alignment_passed() is False

    def test_missing_state_file_fails_closed(self, monkeypatch, tmp_path):
        monkeypatch.setenv("PIPELINE_STATE_FILE", str(tmp_path / "nope.json"))
        assert hook._has_alignment_passed() is False

    def test_tampered_verdict_fails_closed(self, make_state, tmp_path):
        """Flip escalate -> auto_pass without re-signing: HMAC catches it."""
        path = make_state(alignment_passed=False, alignment_verdict="escalate")
        state = json.loads(Path(path).read_text())
        state["alignment_verdict"] = "auto_pass"
        state["alignment_passed"] = True
        Path(path).write_text(json.dumps(state))
        assert hook._has_alignment_passed() is False

    def test_malformed_json_fails_closed(self, monkeypatch, tmp_path):
        path = tmp_path / "broken.json"
        path.write_text("{not json")
        monkeypatch.setenv("PIPELINE_STATE_FILE", str(path))
        assert hook._has_alignment_passed() is False


# ---------------------------------------------------------------------------
# 2. Graceful degradation when the strict library is unavailable
# ---------------------------------------------------------------------------


class TestGracefulDegradation:
    """Consumer installs without alignment_classifier.py keep working."""

    def test_strict_availability_probe_exists(self):
        assert hasattr(hook, "_alignment_strict_available")
        assert callable(hook._alignment_strict_available)

    def test_probe_returns_true_in_this_repo(self):
        """The library ships here, so strict mode is available."""
        assert hook._alignment_strict_available() is True

    def test_degrades_to_boolean_when_library_missing(self, make_state, monkeypatch):
        """With the library absent, a legacy True boolean still passes."""
        monkeypatch.setattr(hook, "_alignment_strict_available", lambda: False)
        make_state(alignment_passed=True, alignment_verdict="escalate")
        assert hook._has_alignment_passed() is True

    def test_degraded_mode_still_honors_false_boolean(self, make_state, monkeypatch):
        """Degradation relaxes the verdict check, never the boolean check."""
        monkeypatch.setattr(hook, "_alignment_strict_available", lambda: False)
        make_state(alignment_passed=False, alignment_verdict="auto_pass")
        assert hook._has_alignment_passed() is False

    def test_strict_available_logs_deviation_on_import_failure(self, monkeypatch):
        """A broken (not merely absent) import must be recorded, not swallowed silently.

        Reproduces Issue #1467 reviewer FINDING-1: distinguishing "library
        legitimately absent" from "library present but broken" requires a
        deviation-log entry in the except branch.
        """
        real_import = __import__

        def _raising_import(name, *args, **kwargs):
            if name == "alignment_classifier":
                raise RuntimeError("simulated broken deploy")
            return real_import(name, *args, **kwargs)

        monkeypatch.setattr("builtins.__import__", _raising_import)
        calls = []
        monkeypatch.setattr(hook, "_log_deviation", lambda *a, **kw: calls.append((a, kw)))

        assert hook._alignment_strict_available() is False
        assert len(calls) == 1
        args, _kwargs = calls[0]
        assert args == ("alignment_classifier_import", "hook", "alignment_strict_unavailable")

    def test_allowed_verdicts_logs_deviation_on_import_failure(self, monkeypatch):
        """Same reviewer finding, second function: the frozenset fallback path."""
        real_import = __import__

        def _raising_import(name, *args, **kwargs):
            if name == "alignment_classifier":
                raise RuntimeError("simulated broken deploy")
            return real_import(name, *args, **kwargs)

        monkeypatch.setattr("builtins.__import__", _raising_import)
        calls = []
        monkeypatch.setattr(hook, "_log_deviation", lambda *a, **kw: calls.append((a, kw)))

        result = hook._allowed_alignment_verdicts()
        assert result == frozenset({"auto_pass", "user_approved"})
        assert len(calls) == 1
        args, _kwargs = calls[0]
        assert args == ("alignment_classifier_import", "hook", "allowed_verdicts_fallback")


# ---------------------------------------------------------------------------
# 3. Anti-bypass: pipeline agents do not skip a disallowed verdict
# ---------------------------------------------------------------------------


class TestPipelineAgentAntiBypass:
    """The verdict pre-check runs BEFORE the PIPELINE_AGENTS early-return."""

    def test_pipeline_agent_denied_on_escalate_verdict(self, make_state, monkeypatch):
        monkeypatch.setenv("CLAUDE_AGENT_NAME", "implementer")
        make_state(alignment_passed=False, alignment_verdict="escalate")
        decision, reason = hook.validate_agent_authorization(
            "Write", {"file_path": "/tmp/app.py", "content": "x = 1"}
        )
        assert decision == "deny"
        assert "ALIGNMENT" in reason.upper()

    def test_pipeline_agent_denied_on_block_verdict(self, make_state, monkeypatch):
        monkeypatch.setenv("CLAUDE_AGENT_NAME", "implementer")
        make_state(alignment_passed=False, alignment_verdict="block")
        decision, reason = hook.validate_agent_authorization(
            "Edit", {"file_path": "/tmp/app.py", "old_string": "a", "new_string": "b"}
        )
        assert decision == "deny"
        assert "ALIGNMENT" in reason.upper()

    def test_pipeline_agent_allowed_on_auto_pass_verdict(self, make_state, monkeypatch):
        monkeypatch.setenv("CLAUDE_AGENT_NAME", "implementer")
        make_state(alignment_passed=True, alignment_verdict="auto_pass")
        decision, reason = hook.validate_agent_authorization(
            "Write", {"file_path": "/tmp/app.py", "content": "x = 1"}
        )
        assert decision == "allow"

    def test_pipeline_agent_allowed_on_user_approved_verdict(self, make_state, monkeypatch):
        monkeypatch.setenv("CLAUDE_AGENT_NAME", "implementer")
        make_state(alignment_passed=True, alignment_verdict="user_approved")
        decision, reason = hook.validate_agent_authorization(
            "Write", {"file_path": "/tmp/app.py", "content": "x = 1"}
        )
        assert decision == "allow"

    def test_pipeline_agent_allowed_on_legacy_state(self, make_state, monkeypatch):
        """No verdict field at all — pre-#1467 behavior is preserved exactly."""
        monkeypatch.setenv("CLAUDE_AGENT_NAME", "implementer")
        make_state(alignment_passed=True)
        decision, reason = hook.validate_agent_authorization(
            "Write", {"file_path": "/tmp/app.py", "content": "x = 1"}
        )
        assert decision == "allow"

    def test_read_tools_are_unaffected_by_disallowed_verdict(self, make_state, monkeypatch):
        """Read-only tools must never be gated — agents must be able to inspect."""
        monkeypatch.setenv("CLAUDE_AGENT_NAME", "implementer")
        make_state(alignment_passed=False, alignment_verdict="escalate")
        decision, _reason = hook.validate_agent_authorization(
            "Read", {"file_path": "/tmp/app.py"}
        )
        assert decision == "allow"


# ---------------------------------------------------------------------------
# 4. ALLOWED_VERDICTS contract is shared, not duplicated
# ---------------------------------------------------------------------------


class TestAllowedVerdictsContract:
    """The hook must consume the library constant, not a hand-copied literal."""

    def test_library_exposes_allowed_verdicts(self):
        from alignment_classifier import ALLOWED_VERDICTS

        assert ALLOWED_VERDICTS == frozenset({"auto_pass", "user_approved"})

    def test_hook_agrees_with_library(self):
        """Cross-validate the two sources rather than hardcoding a third copy."""
        from alignment_classifier import ALLOWED_VERDICTS

        hook_source = (HOOK_DIR / "unified_pre_tool.py").read_text()
        for verdict in ALLOWED_VERDICTS:
            assert verdict in hook_source, (
                f"Allowed verdict {verdict!r} is not referenced in unified_pre_tool.py"
            )


# ---------------------------------------------------------------------------
# 5. The approval env var cannot be inline-spoofed
# ---------------------------------------------------------------------------


class TestApprovalEnvVarProtection:
    """``ALIGNMENT_USER_APPROVED`` decides whether an escalation is approved.

    Security-audit finding: the variable was readable by the STEP 2c snippet
    but absent from ``PROTECTED_ENV_VARS``, so the hook's inline-spoofing
    detector did not cover it — ``ALIGNMENT_USER_APPROVED=1 python3 -c ...``
    faked a human approval.
    """

    def test_variable_is_in_protected_env_vars(self):
        assert "ALIGNMENT_USER_APPROVED" in hook.PROTECTED_ENV_VARS

    def test_inline_prefix_spoofing_is_detected(self):
        result = hook._detect_env_spoofing(
            "ALIGNMENT_USER_APPROVED=1 python3 -c 'print(1)'"
        )
        assert result is not None
        assert "ALIGNMENT_USER_APPROVED" in result

    def test_export_spoofing_is_detected(self):
        result = hook._detect_env_spoofing("export ALIGNMENT_USER_APPROVED=1")
        assert result is not None
        assert "ALIGNMENT_USER_APPROVED" in result

    def test_env_command_spoofing_is_detected(self):
        result = hook._detect_env_spoofing(
            "env ALIGNMENT_USER_APPROVED=1 python3 script.py"
        )
        assert result is not None
        assert "ALIGNMENT_USER_APPROVED" in result

    def test_unrelated_variable_is_still_allowed(self):
        """The addition must not broaden protection to ordinary variables."""
        assert hook._detect_env_spoofing("ALIGNMENT_NOTES=hello python3 x.py") is None


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
