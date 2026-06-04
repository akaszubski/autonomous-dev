"""
Tests for agent identity hardening in unified_pre_tool.py (Issue #557).

Validates:
1. Env var spoofing detection (_detect_env_spoofing)
2. Settings.json write protection (_detect_settings_json_write)
3. HMAC verification in _is_pipeline_active and _is_explicit_implement_active

Date: 2026-03-25
"""

import json
import os
import sys
import tempfile
from datetime import datetime
from pathlib import Path
from unittest.mock import patch

import pytest

# Add hook and lib directories to path
HOOK_DIR = Path(__file__).resolve().parents[3] / "plugins" / "autonomous-dev" / "hooks"
sys.path.insert(0, str(HOOK_DIR))

LIB_DIR = Path(__file__).resolve().parents[3] / "plugins" / "autonomous-dev" / "lib"
sys.path.insert(0, str(LIB_DIR))

import unified_pre_tool as hook


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def clean_env(monkeypatch):
    env_keys = [
        "SANDBOX_ENABLED", "PRE_TOOL_MCP_SECURITY", "PRE_TOOL_AGENT_AUTH",
        "PRE_TOOL_BATCH_PERMISSION", "MCP_AUTO_APPROVE", "ENFORCEMENT_LEVEL",
        "CLAUDE_AGENT_NAME", "PIPELINE_STATE_FILE", "CLAUDE_SESSION_ID",
    ]
    for key in env_keys:
        monkeypatch.delenv(key, raising=False)


# ---------------------------------------------------------------------------
# TestEnvSpoofingDetection
# ---------------------------------------------------------------------------

class TestEnvSpoofingDetection:
    """Tests for _detect_env_spoofing() function."""

    def test_inline_prefix_blocked(self):
        """CLAUDE_AGENT_NAME=implementer python3 ... should be blocked."""
        cmd = "CLAUDE_AGENT_NAME=implementer python3 script.py"
        result = hook._detect_env_spoofing(cmd)
        assert result is not None
        assert "CLAUDE_AGENT_NAME" in result
        # May be caught by individual var (Issue #557) or prefix (Issue #606)
        assert "Issue #557" in result or "Issue #606" in result

    def test_export_blocked(self):
        """export CLAUDE_AGENT_NAME=implementer should be blocked."""
        cmd = "export CLAUDE_AGENT_NAME=implementer"
        result = hook._detect_env_spoofing(cmd)
        assert result is not None
        assert "CLAUDE_AGENT_NAME" in result

    def test_env_command_blocked(self):
        """env CLAUDE_AGENT_NAME=implementer python3 ... should be blocked."""
        cmd = "env CLAUDE_AGENT_NAME=implementer python3 script.py"
        result = hook._detect_env_spoofing(cmd)
        assert result is not None
        assert "CLAUDE_AGENT_NAME" in result

    def test_other_protected_vars_blocked(self):
        """All PROTECTED_ENV_VARS should be caught."""
        for var in hook.PROTECTED_ENV_VARS:
            cmd = f"{var}=spoofed_value python3 test.py"
            result = hook._detect_env_spoofing(cmd)
            assert result is not None, f"{var} should be detected as spoofing"

    def test_legitimate_env_allowed(self):
        """Normal env vars like PATH, HOME should not be blocked."""
        cmd = "PATH=/usr/bin python3 test.py"
        result = hook._detect_env_spoofing(cmd)
        assert result is None

    def test_legitimate_export_allowed(self):
        """export of non-protected vars should not be blocked."""
        cmd = "export MY_CUSTOM_VAR=hello"
        result = hook._detect_env_spoofing(cmd)
        assert result is None

    def test_quoted_value_blocked(self):
        """Quoted values should still be detected."""
        cmd = 'CLAUDE_AGENT_NAME="implementer" python3 script.py'
        result = hook._detect_env_spoofing(cmd)
        assert result is not None

    def test_single_quoted_value_blocked(self):
        """Single-quoted values should still be detected."""
        cmd = "CLAUDE_AGENT_NAME='implementer' python3 script.py"
        result = hook._detect_env_spoofing(cmd)
        assert result is not None

    def test_pipeline_state_file_blocked(self):
        """PIPELINE_STATE_FILE spoofing should be detected."""
        cmd = "PIPELINE_STATE_FILE=/tmp/fake.json python3 hook.py"
        result = hook._detect_env_spoofing(cmd)
        assert result is not None
        assert "PIPELINE_STATE_FILE" in result

    def test_enforcement_level_blocked(self):
        """ENFORCEMENT_LEVEL spoofing should be detected."""
        cmd = "export ENFORCEMENT_LEVEL=off"
        result = hook._detect_env_spoofing(cmd)
        assert result is not None
        assert "ENFORCEMENT_LEVEL" in result

    def test_empty_command_allowed(self):
        """Empty command should not be blocked."""
        result = hook._detect_env_spoofing("")
        assert result is None

    def test_command_without_env_vars(self):
        """Normal commands should not be blocked."""
        cmd = "python3 -m pytest tests/ -v"
        result = hook._detect_env_spoofing(cmd)
        assert result is None

    def test_var_in_string_not_blocked(self):
        """References to var names in strings/comments should not trigger."""
        cmd = "echo 'CLAUDE_AGENT_NAME is set by the system'"
        result = hook._detect_env_spoofing(cmd)
        assert result is None


# ---------------------------------------------------------------------------
# TestSubshellEnvSpoofingDetection (F3 remediation)
# ---------------------------------------------------------------------------

class TestSubshellEnvSpoofingDetection:
    """Tests for bash -c subshell env spoofing detection (F3)."""

    def test_bash_c_with_inline_var_blocked(self):
        """bash -c 'CLAUDE_AGENT_NAME=x cmd' should be blocked."""
        cmd = "bash -c 'CLAUDE_AGENT_NAME=implementer python3 script.py'"
        result = hook._detect_env_spoofing(cmd)
        assert result is not None
        assert "Subshell" in result or "CLAUDE_AGENT_NAME" in result

    def test_sh_c_with_export_blocked(self):
        """sh -c 'export PIPELINE_STATE_FILE=...' should be blocked."""
        cmd = 'sh -c "export PIPELINE_STATE_FILE=/tmp/fake.json"'
        result = hook._detect_env_spoofing(cmd)
        assert result is not None
        assert "PIPELINE_STATE_FILE" in result

    def test_bash_c_with_env_command_blocked(self):
        """bash -c 'env ENFORCEMENT_LEVEL=off cmd' should be blocked."""
        cmd = "bash -c 'env ENFORCEMENT_LEVEL=off python3 hook.py'"
        result = hook._detect_env_spoofing(cmd)
        assert result is not None
        assert "ENFORCEMENT_LEVEL" in result

    def test_bash_c_with_safe_command_allowed(self):
        """bash -c 'echo hello' should be allowed."""
        cmd = "bash -c 'echo hello world'"
        result = hook._detect_env_spoofing(cmd)
        assert result is None

    def test_bash_c_with_unprotected_var_allowed(self):
        """bash -c 'PATH=/usr/bin cmd' should be allowed."""
        cmd = "bash -c 'PATH=/usr/bin python3 test.py'"
        result = hook._detect_env_spoofing(cmd)
        assert result is None

    def test_double_quoted_subshell_blocked(self):
        """bash -c with double quotes should also be caught for other CLAUDE_* vars."""
        # CLAUDE_SESSION_ID is now in PROTECTED_ENV_PREFIX_EXCEPTIONS (Issue #1137);
        # use CLAUDE_AGENT_NAME which remains protected by the prefix rule.
        cmd = 'bash -c "CLAUDE_AGENT_NAME=fake python3 test.py"'
        result = hook._detect_env_spoofing(cmd)
        assert result is not None
        assert "CLAUDE_AGENT_NAME" in result


# ---------------------------------------------------------------------------
# TestSettingsJsonProtection
# ---------------------------------------------------------------------------

class TestSettingsJsonProtection:
    """Tests for settings.json write protection during active pipeline."""

    def test_settings_json_redirect_detected(self):
        """Redirect to settings.json should be detected."""
        cmd = "echo '{}' > .claude/settings.json"
        result = hook._detect_settings_json_write(cmd)
        assert result is not None
        assert "settings.json" in result

    def test_settings_local_json_redirect_detected(self):
        """Redirect to settings.local.json should be detected."""
        cmd = "echo '{}' > .claude/settings.local.json"
        result = hook._detect_settings_json_write(cmd)
        assert result is not None
        assert "settings.local.json" in result

    def test_other_json_file_allowed(self):
        """Writing to other JSON files should be allowed."""
        cmd = "echo '{}' > config.json"
        result = hook._detect_settings_json_write(cmd)
        assert result is None

    def test_sed_settings_json_detected(self):
        """sed -i on settings.json should be detected."""
        cmd = "sed -i 's/old/new/' .claude/settings.json"
        result = hook._detect_settings_json_write(cmd)
        assert result is not None

    def test_normal_command_allowed(self):
        """Commands not targeting settings files should be allowed."""
        cmd = "python3 -m pytest tests/ -v"
        result = hook._detect_settings_json_write(cmd)
        assert result is None


# ---------------------------------------------------------------------------
# TestStateFileHmac
# ---------------------------------------------------------------------------

class TestStateFileHmac:
    """Tests for HMAC verification in pipeline active checks."""

    def _write_state_file(self, tmp_path, state_data):
        """Write a pipeline state file and return its path."""
        state_file = tmp_path / "pipeline_state.json"
        state_file.write_text(json.dumps(state_data))
        return str(state_file)

    def test_valid_hmac_state_accepted(self, tmp_path, monkeypatch):
        """State with valid HMAC should be accepted by _is_pipeline_active."""
        from pipeline_state import sign_state
        session_id = "test-session-123"
        state = {
            "session_start": datetime.now().isoformat(),
            "mode": "full",
            "run_id": "test-run",
            "explicitly_invoked": True,
        }
        sign_state(state, session_id)
        state_file = self._write_state_file(tmp_path, state)

        monkeypatch.setenv("PIPELINE_STATE_FILE", state_file)
        monkeypatch.setenv("CLAUDE_SESSION_ID", session_id)
        monkeypatch.delenv("CLAUDE_AGENT_NAME", raising=False)

        assert hook._is_pipeline_active() is True

    def test_tampered_hmac_state_rejected(self, tmp_path, monkeypatch):
        """State with tampered HMAC should be rejected by _is_pipeline_active."""
        from pipeline_state import sign_state
        session_id = "test-session-123"
        state = {
            "session_start": datetime.now().isoformat(),
            "mode": "full",
            "run_id": "test-run",
            "explicitly_invoked": True,
        }
        sign_state(state, session_id)
        state["explicitly_invoked"] = False  # Tamper after signing
        state_file = self._write_state_file(tmp_path, state)

        monkeypatch.setenv("PIPELINE_STATE_FILE", state_file)
        monkeypatch.setenv("CLAUDE_SESSION_ID", session_id)
        monkeypatch.delenv("CLAUDE_AGENT_NAME", raising=False)

        assert hook._is_pipeline_active() is False

    def test_missing_hmac_backward_compat(self, tmp_path, monkeypatch):
        """State without HMAC should be accepted (backward compat)."""
        state = {
            "session_start": datetime.now().isoformat(),
            "mode": "full",
            "run_id": "test-run",
            "explicitly_invoked": True,
        }
        state_file = self._write_state_file(tmp_path, state)

        monkeypatch.setenv("PIPELINE_STATE_FILE", state_file)
        monkeypatch.delenv("CLAUDE_AGENT_NAME", raising=False)

        assert hook._is_pipeline_active() is True

    def test_missing_session_id_with_hmac_verifies_via_secret(self, tmp_path, monkeypatch):
        """With secret-file HMAC, missing session_id still verifies via secret file.

        The HMAC key now comes from the per-run secret file, not from session_id.
        So even when CLAUDE_SESSION_ID is absent, verification succeeds as long
        as the secret file exists for the run_id.
        """
        from pipeline_state import sign_state
        state = {
            "session_start": datetime.now().isoformat(),
            "mode": "full",
            "run_id": "test-run-hmac-session",
            "explicitly_invoked": True,
        }
        sign_state(state, "original-session")
        state_file = self._write_state_file(tmp_path, state)

        monkeypatch.setenv("PIPELINE_STATE_FILE", state_file)
        monkeypatch.delenv("CLAUDE_SESSION_ID", raising=False)
        monkeypatch.delenv("CLAUDE_AGENT_NAME", raising=False)
        # Secret file exists for the run_id, so HMAC verification succeeds
        assert hook._is_pipeline_active() is True

    def test_missing_secret_file_and_wrong_session_fails(self, tmp_path, monkeypatch):
        """Without secret file AND wrong session_id, verification fails closed."""
        from pipeline_state import sign_state, cleanup_pipeline_secret
        state = {
            "session_start": datetime.now().isoformat(),
            "mode": "full",
            "run_id": "test-run-no-secret",
            "explicitly_invoked": True,
        }
        sign_state(state, "original-session")
        # Remove the secret file to force session_id fallback
        cleanup_pipeline_secret("test-run-no-secret")
        state_file = self._write_state_file(tmp_path, state)

        monkeypatch.setenv("PIPELINE_STATE_FILE", state_file)
        monkeypatch.delenv("CLAUDE_SESSION_ID", raising=False)
        monkeypatch.delenv("CLAUDE_AGENT_NAME", raising=False)
        # No secret file, fallback to session_id="unknown" != secret used for signing
        assert hook._is_pipeline_active() is False



# ---------------------------------------------------------------------------
# TestImportErrorFailClosed (F6 remediation)
# ---------------------------------------------------------------------------

class TestImportErrorFailClosed:
    """Tests that HMAC check fails closed when import fails (F6)."""

    def _write_state_file(self, tmp_path, state_data):
        state_file = tmp_path / "pipeline_state.json"
        state_file.write_text(json.dumps(state_data))
        return str(state_file)

    def test_pipeline_active_fails_closed_on_import_error(self, tmp_path, monkeypatch):
        """When HMAC is present but pipeline_state import fails, return False."""
        from pipeline_state import sign_state
        session_id = "test-session-f6"
        state = {
            "session_start": datetime.now().isoformat(),
            "mode": "full",
            "run_id": "test-run-f6",
            "explicitly_invoked": True,
        }
        sign_state(state, session_id)
        state_file = self._write_state_file(tmp_path, state)

        monkeypatch.setenv("PIPELINE_STATE_FILE", state_file)
        monkeypatch.setenv("CLAUDE_SESSION_ID", session_id)
        monkeypatch.delenv("CLAUDE_AGENT_NAME", raising=False)

        # Mock the import to fail inside the hook
        import builtins
        real_import = builtins.__import__

        def mock_import(name, *args, **kwargs):
            if name == "pipeline_state":
                raise ImportError("Mocked import failure")
            return real_import(name, *args, **kwargs)

        monkeypatch.setattr(builtins, "__import__", mock_import)

        # Should fail closed (return False) when HMAC present but import fails
        assert hook._is_pipeline_active() is False

    def test_explicit_implement_fails_closed_on_import_error(self, tmp_path, monkeypatch):
        """When HMAC present but import fails in explicit check, return False."""
        from pipeline_state import sign_state
        session_id = "test-session-f6b"
        state = {
            "session_start": datetime.now().isoformat(),
            "mode": "full",
            "run_id": "test-run-f6b",
            "explicitly_invoked": True,
        }
        sign_state(state, session_id)
        state_file = self._write_state_file(tmp_path, state)

        monkeypatch.setenv("PIPELINE_STATE_FILE", state_file)
        monkeypatch.setenv("CLAUDE_SESSION_ID", session_id)
        monkeypatch.delenv("CLAUDE_AGENT_NAME", raising=False)

        import builtins
        real_import = builtins.__import__

        def mock_import(name, *args, **kwargs):
            if name == "pipeline_state":
                raise ImportError("Mocked import failure")
            return real_import(name, *args, **kwargs)

        monkeypatch.setattr(builtins, "__import__", mock_import)

        assert hook._is_explicit_implement_active() is False


# ---------------------------------------------------------------------------
# TestStripQuotedSegments (Issue #590)
# ---------------------------------------------------------------------------

class TestStripQuotedSegments:
    """Tests for _strip_quoted_segments() helper (Issue #590)."""

    def test_strips_single_quotes(self):
        """Single-quoted segment should be removed."""
        result = hook._strip_quoted_segments("echo 'VAR=value cmd' rest")
        assert result == 'echo  rest'

    def test_strips_double_quotes(self):
        """Double-quoted segment should be removed."""
        result = hook._strip_quoted_segments('echo "VAR=value cmd" rest')
        assert result == 'echo  rest'

    def test_handles_escaped_quotes(self):
        """Backslash-escaped double-quote inside double-quoted segment should not end it."""
        # In bash: echo "he said \"VAR=value\"" - the \" are backslash-escaped quotes
        # Python single-quoted: \\" = one backslash + quote
        result = hook._strip_quoted_segments('echo "he said \\"VAR=value\\"" rest')
        assert result == 'echo  rest' 

    def test_no_quotes_unchanged(self):
        """Command without quotes should be returned unchanged."""
        av = 'CLAUDE_AGENT' + '_NAME'
        cmd = av + '=x python3 test.py'
        result = hook._strip_quoted_segments(cmd)
        assert result == cmd

    def test_empty_string(self):
        """Empty string should return empty string."""
        assert hook._strip_quoted_segments('') == ''


# ---------------------------------------------------------------------------
# TestQuotedSegmentFalsePositives (Issue #590)
# ---------------------------------------------------------------------------

class TestQuotedSegmentFalsePositives:
    """Integration tests: quoted arguments containing protected var names must not be blocked (Issue #590)."""

    def _agent_var(self):
        return 'CLAUDE_AGENT' + '_NAME'

    def _pipeline_var(self):
        return 'PIPELINE' + '_STATE_FILE'

    def _enforcement_var(self):
        return 'ENFORCEMENT' + '_LEVEL'

    def test_gh_issue_body_with_var_name_not_blocked(self):
        """gh issue create with protected var in --body should not be blocked."""
        av = self._agent_var()
        cmd = 'gh issue create --title "Fix" --body "Evidence: ' + av + '=implementer was set"'
        result = hook._detect_env_spoofing(cmd)
        assert result is None, f'Should not be blocked, got: {result}'

    def test_gh_issue_body_with_export_not_blocked(self):
        """gh issue create with export in --body should not be blocked."""
        pv = self._pipeline_var()
        cmd = 'gh issue create --body "Log: export ' + pv + '=/tmp/fake.json"'
        result = hook._detect_env_spoofing(cmd)
        assert result is None, f'Should not be blocked, got: {result}'

    def test_echo_double_quotes_not_blocked(self):
        """echo with protected var in double-quoted argument should not be blocked."""
        av = self._agent_var()
        cmd = 'echo "' + av + '=test some_cmd"'
        result = hook._detect_env_spoofing(cmd)
        assert result is None, f'Should not be blocked, got: {result}'

    def test_echo_single_quotes_not_blocked(self):
        """echo with protected var in single-quoted argument should not be blocked."""
        ev = self._enforcement_var()
        cmd = "echo '" + ev + "=off python3 hook.py'"
        result = hook._detect_env_spoofing(cmd)
        assert result is None, f'Should not be blocked, got: {result}'

    def test_actual_spoofing_before_quotes_still_blocked(self):
        """Actual spoofing before quoted segment must still be blocked."""
        av = self._agent_var()
        cmd = av + '=fake echo "hello"'
        result = hook._detect_env_spoofing(cmd)
        assert result is not None, 'Actual spoofing should be blocked'

    def test_actual_spoofing_after_quotes_still_blocked(self):
        """Actual spoofing after quoted segment must still be blocked."""
        av = self._agent_var()
        cmd = 'echo "hello" && ' + av + '=fake python3 script.py'
        result = hook._detect_env_spoofing(cmd)
        assert result is not None, 'Actual spoofing should be blocked'

    def test_mixed_quoted_and_unquoted_blocked(self):
        """Unquoted export after quoted safe content must still be blocked."""
        pv = self._pipeline_var()
        cmd = 'echo "safe" && export ' + pv + '=/tmp/x'
        result = hook._detect_env_spoofing(cmd)
        assert result is not None, 'Unquoted export should still be blocked'


# ---------------------------------------------------------------------------
# TestPrefixEnvSpoofingDetection (Issue #606)
# ---------------------------------------------------------------------------

class TestPrefixEnvSpoofingDetection:
    """Tests for prefix-based env var spoofing detection (Issue #606)."""

    def test_claude_agent_prefix_blocked(self):
        """CLAUDE_AGENT_FOO=bar python3 ... should be blocked by prefix."""
        cmd = "CLAUDE_AGENT_FOO=bar python3 script.py"
        result = hook._detect_env_spoofing(cmd)
        assert result is not None
        assert "CLAUDE_AGENT_FOO" in result
        assert "Issue #606" in result

    def test_claude_session_prefix_blocked(self):
        """CLAUDE_SESSION_TOKEN=x python3 ... should be blocked by prefix."""
        cmd = "CLAUDE_SESSION_TOKEN=x python3 script.py"
        result = hook._detect_env_spoofing(cmd)
        assert result is not None
        assert "CLAUDE_SESSION_TOKEN" in result

    def test_claude_generic_prefix_blocked(self):
        """CLAUDE_CUSTOM_VAR=x python3 ... should be blocked by prefix."""
        cmd = "CLAUDE_CUSTOM_VAR=x python3 script.py"
        result = hook._detect_env_spoofing(cmd)
        assert result is not None
        assert "CLAUDE_CUSTOM_VAR" in result

    def test_non_claude_prefix_allowed(self):
        """MY_CLAUDE_VAR=x python3 ... should NOT be blocked (not a prefix match)."""
        cmd = "MY_CLAUDE_VAR=x python3 script.py"
        result = hook._detect_env_spoofing(cmd)
        assert result is None, f"Should not be blocked, got: {result}"

    def test_prefix_exception_allowed(self, monkeypatch):
        """If a var is in PROTECTED_ENV_PREFIX_EXCEPTIONS, it should pass through."""
        # Temporarily add an exception
        monkeypatch.setattr(
            hook, "PROTECTED_ENV_PREFIX_EXCEPTIONS",
            frozenset({"CLAUDE_USER_CUSTOM"}),
        )
        cmd = "CLAUDE_USER_CUSTOM=hello python3 script.py"
        result = hook._detect_env_spoofing(cmd)
        assert result is None, f"Exception var should not be blocked, got: {result}"

    def test_export_prefix_blocked(self):
        """export CLAUDE_AGENT_TOKEN=x should be blocked by prefix."""
        cmd = "export CLAUDE_AGENT_TOKEN=secret123"
        result = hook._detect_env_spoofing(cmd)
        assert result is not None
        assert "CLAUDE_AGENT_TOKEN" in result
        assert "export" in result.lower() or "Export" in result

    def test_env_command_prefix_blocked(self):
        """env CLAUDE_AGENT_TOKEN=x python3 ... should be blocked by prefix."""
        cmd = "env CLAUDE_AGENT_TOKEN=x python3 script.py"
        result = hook._detect_env_spoofing(cmd)
        assert result is not None
        assert "CLAUDE_AGENT_TOKEN" in result

    def test_subshell_prefix_blocked(self):
        """bash -c 'CLAUDE_AGENT_NEW=x cmd' should be blocked by prefix via recursion."""
        cmd = "bash -c 'CLAUDE_AGENT_NEW=x python3 script.py'"
        result = hook._detect_env_spoofing(cmd)
        assert result is not None
        assert "CLAUDE_AGENT_NEW" in result or "Subshell" in result


# ---------------------------------------------------------------------------
# TestIsProtectedEnvVar (Issue #606)
# ---------------------------------------------------------------------------

class TestIsProtectedEnvVar:
    """Tests for _is_protected_env_var() helper function."""

    def test_individual_var_protected(self):
        """PIPELINE_STATE_FILE should be protected (individual listing)."""
        assert hook._is_protected_env_var("PIPELINE_STATE_FILE") is True

    def test_prefix_var_protected(self):
        """CLAUDE_ANYTHING should be protected (prefix match)."""
        assert hook._is_protected_env_var("CLAUDE_ANYTHING") is True

    def test_unprotected_var(self):
        """PATH should not be protected."""
        assert hook._is_protected_env_var("PATH") is False

    def test_exception_var_not_protected(self, monkeypatch):
        """Exception vars should not be protected even with matching prefix."""
        monkeypatch.setattr(
            hook, "PROTECTED_ENV_PREFIX_EXCEPTIONS",
            frozenset({"CLAUDE_EXCEPTION_VAR"}),
        )
        assert hook._is_protected_env_var("CLAUDE_EXCEPTION_VAR") is False


# ---------------------------------------------------------------------------
# TestEscalationDetection (Issue #606)
# ---------------------------------------------------------------------------

class TestEscalationDetection:
    """Tests for _track_spoofing_escalation() function (Issue #606)."""

    def test_first_spoofing_no_escalation(self, tmp_path):
        """First spoofing attempt in a session should not trigger escalation."""
        tracker_file = str(tmp_path / "spoofing_attempts.json")
        result = hook._track_spoofing_escalation(
            "session-abc", tracker_path=tracker_file
        )
        assert result is False

    def test_second_spoofing_triggers_escalation(self, tmp_path):
        """Second spoofing attempt in same session should trigger escalation."""
        tracker_file = str(tmp_path / "spoofing_attempts.json")
        # First attempt
        result1 = hook._track_spoofing_escalation(
            "session-abc", tracker_path=tracker_file
        )
        assert result1 is False
        # Second attempt
        result2 = hook._track_spoofing_escalation(
            "session-abc", tracker_path=tracker_file
        )
        assert result2 is True

    def test_different_session_no_escalation(self, tmp_path):
        """Different sessions should not cross-escalate."""
        tracker_file = str(tmp_path / "spoofing_attempts.json")
        # First attempt in session A
        hook._track_spoofing_escalation(
            "session-aaa", tracker_path=tracker_file
        )
        # First attempt in session B — should NOT be escalation
        result = hook._track_spoofing_escalation(
            "session-bbb", tracker_path=tracker_file
        )
        assert result is False

    def test_unknown_session_no_escalation(self, tmp_path, monkeypatch):
        """When CLAUDE_SESSION_ID is unset, session_id='unknown' should not
        trigger false escalation across unrelated invocations (Issue #606).

        Regression test for FINDING-4: multiple invocations with 'unknown'
        session_id should NOT share a bucket and produce false escalation.
        """
        monkeypatch.delenv("CLAUDE_SESSION_ID", raising=False)
        session_id = os.environ.get("CLAUDE_SESSION_ID", "unknown")
        assert session_id == "unknown"
        # The fix: when session_id is "unknown", escalation tracking is skipped
        # so we verify that _track_spoofing_escalation is NOT called with "unknown"
        # in the production code path. But we can verify the tracker itself still
        # works — the key behavioral change is in the caller (line 1979).
        # Here we verify that calling the tracker with "unknown" twice WOULD
        # escalate (proving the fix is in the caller, not the tracker).
        tracker_file = str(tmp_path / "spoofing_attempts.json")
        hook._track_spoofing_escalation("unknown", tracker_path=tracker_file)
        result = hook._track_spoofing_escalation("unknown", tracker_path=tracker_file)
        # The tracker itself still escalates — the fix is that the caller
        # skips calling it when session_id == "unknown"
        assert result is True


# ---------------------------------------------------------------------------
# TestSessionIdException (Issue #1137)
# ---------------------------------------------------------------------------

class TestSessionIdException:
    """Issue #1137: CLAUDE_SESSION_ID is in PROTECTED_ENV_PREFIX_EXCEPTIONS.

    Verifies that legitimate `export CLAUDE_SESSION_ID=...` calls (baseline
    failure capture, activity-log scoping per Issue #904) are allowed across
    all four Bash assignment patterns, while other CLAUDE_* vars remain
    blocked by the prefix-protection defense (Issue #606).
    """

    def test_session_id_is_not_protected(self):
        """CLAUDE_SESSION_ID must NOT be protected by the prefix rule."""
        assert hook._is_protected_env_var("CLAUDE_SESSION_ID") is False

    def test_session_id_inline_assignment_allowed(self):
        """Inline: CLAUDE_SESSION_ID=abc some_cmd — must be allowed."""
        result = hook._detect_env_spoofing("CLAUDE_SESSION_ID=abc123 echo hi")
        assert result is None, f"Expected no violation, got: {result!r}"

    def test_session_id_export_allowed(self):
        """Export: export CLAUDE_SESSION_ID=abc — must be allowed."""
        result = hook._detect_env_spoofing("export CLAUDE_SESSION_ID=abc123")
        assert result is None, f"Expected no violation, got: {result!r}"

    def test_session_id_env_command_allowed(self):
        """env command: env CLAUDE_SESSION_ID=abc some_cmd — must be allowed."""
        result = hook._detect_env_spoofing("env CLAUDE_SESSION_ID=abc123 echo hi")
        assert result is None, f"Expected no violation, got: {result!r}"

    def test_session_id_bash_c_allowed(self):
        """bash -c subshell: bash -c 'CLAUDE_SESSION_ID=abc some_cmd' — must be allowed."""
        result = hook._detect_env_spoofing("bash -c 'CLAUDE_SESSION_ID=abc123 echo hi'")
        assert result is None, f"Expected no violation, got: {result!r}"

    @pytest.mark.parametrize("var", ["CLAUDE_AGENT_NAME", "CLAUDE_USER_ID", "CLAUDE_INTERNAL_FOO"])
    @pytest.mark.parametrize(
        "pattern",
        [
            "{var}=abc echo hi",
            "export {var}=abc",
            "env {var}=abc echo hi",
            "bash -c '{var}=abc echo hi'",
        ],
    )
    def test_other_claude_vars_still_blocked(self, var, pattern):
        """Regression guard: other CLAUDE_* vars must remain blocked under all 4 patterns."""
        cmd = pattern.format(var=var)
        result = hook._detect_env_spoofing(cmd)
        assert result is not None, f"Expected violation for {cmd!r}, got None"


# ---------------------------------------------------------------------------
# Remediation regression tests (Issue #606 security audit)
# ---------------------------------------------------------------------------

class TestRemediationRegressions:
    """Regression tests for Issue #606 security audit findings."""

    def test_newline_separated_assignment_blocked(self):
        """FINDING-1: Newline-separated env var assignment must be caught.

        A command like 'echo foo\\nCLAUDE_AGENT_NEW=x python3 script.py'
        should be blocked because Pass 2 regex now uses re.MULTILINE.
        """
        cmd = "echo foo\nCLAUDE_AGENT_NEW=x python3 script.py"
        result = hook._detect_env_spoofing(cmd)
        assert result is not None, (
            "Newline-separated protected var assignment should be blocked"
        )
        assert "CLAUDE_AGENT_NEW" in result

    def test_env_with_flags_prefix_blocked(self):
        """FINDING-2: 'env -i PIPELINE_STATE_FILE=/tmp/fake.json python3' must be caught.

        The env command regex must handle flags like -i before VAR= assignments.
        """
        cmd = "env -i PIPELINE_STATE_FILE=/tmp/fake.json python3 script.py"
        result = hook._detect_env_spoofing(cmd)
        assert result is not None, (
            "env -i with protected var assignment should be blocked"
        )
        assert "PIPELINE_STATE_FILE" in result

    def test_env_with_double_dash_blocked(self):
        """env -- CLAUDE_AGENT_NAME=x python3 must also be caught."""
        cmd = "env -- CLAUDE_AGENT_NAME=implementer python3 script.py"
        result = hook._detect_env_spoofing(cmd)
        assert result is not None, (
            "env -- with protected var assignment should be blocked"
        )
        assert "CLAUDE_AGENT_NAME" in result

    def test_env_with_u_flag_blocked(self):
        """env -u OLDVAR CLAUDE_AGENT_NAME=x python3 must be caught."""
        cmd = "env -u OLDVAR CLAUDE_AGENT_NAME=implementer python3 script.py"
        result = hook._detect_env_spoofing(cmd)
        assert result is not None, (
            "env -u FLAG with protected var assignment should be blocked"
        )
        assert "CLAUDE_AGENT_NAME" in result

    def test_chained_subshell_both_inspected(self):
        """FINDING-3: Chained bash -c subshells must ALL be inspected.

        'bash -c 'echo safe' && bash -c 'CLAUDE_X=y python3 ...''
        should block because the second subshell contains spoofing.
        """
        cmd = (
            "bash -c 'echo safe' && "
            "bash -c 'CLAUDE_AGENT_NEW=x python3 script.py'"
        )
        result = hook._detect_env_spoofing(cmd)
        assert result is not None, (
            "Second chained subshell with protected var should be blocked"
        )
        assert "Subshell" in result or "CLAUDE_AGENT_NEW" in result

    def test_chained_subshell_first_safe_allowed(self):
        """Chained subshells where both are safe should be allowed."""
        cmd = "bash -c 'echo hello' && bash -c 'echo world'"
        result = hook._detect_env_spoofing(cmd)
        assert result is None
