"""Tests for intent-to-command routing in unified_prompt_validator.py and deviation logging in unified_pre_tool.py."""

import json
import os
import sys
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest

# Add hooks directory to path for direct import
HOOKS_DIR = Path(__file__).parent.parent.parent.parent / "plugins" / "autonomous-dev" / "hooks"
sys.path.insert(0, str(HOOKS_DIR))

from unified_prompt_validator import (
    COMMAND_ROUTES,
    detect_command_intent,
    _format_nudge,
    _format_block,
    main,
)


# ============================================================================
# Route Detection Tests
# ============================================================================

class TestImplementRouteDetection:
    """Test /implement route triggers correctly."""

    @pytest.mark.parametrize("prompt", [
        "implement JWT authentication feature",
        "add a new login function",
        "create user registration endpoint",
        "build the payment integration",
        "fix the authentication bug",
        "refactor the validation logic",
        "write a caching module",
        "update the API endpoint code",
        "modify the handler class",
        "develop a new service component",
        "patch the auth system",
    ])
    def test_implementation_prompts_route_to_implement(self, prompt: str):
        result = detect_command_intent(prompt)
        assert result is not None
        assert result["command"] == "/implement"

    def test_question_skipped(self):
        """Questions (ending with ?) should not trigger routing."""
        result = detect_command_intent("How do I implement authentication?")
        assert result is None

    def test_already_using_command_skipped(self):
        """Prompts starting with / should not trigger."""
        result = detect_command_intent("/implement add auth feature")
        assert result is None

    def test_empty_input(self):
        assert detect_command_intent("") is None
        assert detect_command_intent("   ") is None
        assert detect_command_intent(None) is None


class TestCreateIssueRouteDetection:
    """Test /create-issue route triggers correctly."""

    def test_gh_issue_create_detected(self):
        result = detect_command_intent("gh issue create --title 'bug'")
        assert result is not None
        assert result["command"] == "/create-issue"
        assert result["block"] is True

    def test_file_issue_detected(self):
        result = detect_command_intent("file a new github issue for this bug")
        assert result is not None
        assert result["command"] == "/create-issue"

    def test_open_issue_detected(self):
        result = detect_command_intent("open an issue for the login problem")
        assert result is not None
        assert result["command"] == "/create-issue"

    def test_create_issue_command_skipped(self):
        result = detect_command_intent("/create-issue add auth")
        assert result is None


class TestAuditRouteDetection:
    """Test /audit route triggers correctly."""

    def test_run_tests_detected(self):
        result = detect_command_intent("run the tests")
        assert result is not None
        assert result["command"] == "/audit"

    def test_check_security_detected(self):
        result = detect_command_intent("check security")
        assert result is not None
        assert result["command"] == "/audit"

    def test_verify_coverage_detected(self):
        result = detect_command_intent("verify test coverage")
        assert result is not None
        assert result["command"] == "/audit"

    def test_pytest_detected(self):
        result = detect_command_intent("pytest tests/unit")
        assert result is not None
        assert result["command"] == "/audit"

    def test_audit_command_skipped(self):
        result = detect_command_intent("/audit --security")
        assert result is None


class TestAlignRouteDetection:
    """Test /align route triggers correctly."""

    def test_check_alignment_detected(self):
        result = detect_command_intent("check project alignment")
        assert result is not None
        assert result["command"] == "/align"

    def test_project_md_align_detected(self):
        result = detect_command_intent("check PROJECT.md alignment with code")
        assert result is not None
        assert result["command"] == "/align"

    def test_project_md_update_detected(self):
        result = detect_command_intent("PROJECT.md needs to be updated and synced")
        assert result is not None
        assert result["command"] == "/align"

    def test_align_command_skipped(self):
        result = detect_command_intent("/align --project")
        assert result is None


class TestDocsRouteDetection:
    """Test /align --docs route triggers correctly."""

    def test_update_docs_detected(self):
        result = detect_command_intent("update the documentation")
        assert result is not None
        assert result["command"] == "/align --docs"

    def test_fix_readme_detected(self):
        result = detect_command_intent("fix the README")
        assert result is not None
        assert result["command"] == "/align --docs"

    def test_sync_docs_detected(self):
        result = detect_command_intent("sync the docs with code")
        assert result is not None
        assert result["command"] == "/align --docs"

    def test_align_docs_command_skipped(self):
        result = detect_command_intent("/align --docs")
        assert result is None


class TestNoRouteMatch:
    """Test prompts that should NOT match any route."""

    @pytest.mark.parametrize("prompt", [
        "hello",
        "what is this project about",
        "show me the file structure",
        "read the README",
        "explain this code",
        "git status",
        "ls -la",
    ])
    def test_no_match(self, prompt: str):
        assert detect_command_intent(prompt) is None


# ============================================================================
# Nudge Format Tests
# ============================================================================

class TestNudgeFormat:
    """Test nudge message formatting."""

    def test_nudge_includes_command(self):
        msg = _format_nudge("/implement", "handles testing")
        assert "/implement" in msg

    def test_nudge_includes_reason(self):
        msg = _format_nudge("/implement", "handles testing")
        assert "handles testing" in msg

    def test_nudge_is_concise(self):
        msg = _format_nudge("/implement", "handles testing")
        lines = msg.strip().split("\n")
        assert len(lines) <= 4

    def test_nudge_mentions_direct_ok(self):
        msg = _format_nudge("/implement", "reason")
        assert "small changes" in msg.lower() or "proceeding directly" in msg.lower()

    def test_block_includes_command(self):
        msg = _format_block("/create-issue", "reason", "gh issue create --title foo")
        assert "/create-issue" in msg
        assert "BLOCKED" in msg


# ============================================================================
# Enforcement Level Tests (unified_pre_tool.py)
# ============================================================================

class TestEnforcementLevel:
    """Test enforcement level defaults and behavior."""

    def test_default_enforcement_is_suggest(self):
        """Default ENFORCEMENT_LEVEL should be 'suggest', not 'block'."""
        # Import fresh to check default
        pre_tool_path = HOOKS_DIR / "unified_pre_tool.py"
        content = pre_tool_path.read_text()
        assert 'ENFORCEMENT_LEVEL", "suggest"' in content

    def test_no_line_count_in_significant_message(self):
        """Significant change messages should not include line counts."""
        pre_tool_path = HOOKS_DIR / "unified_pre_tool.py"
        content = pre_tool_path.read_text()
        # The old format "Significant addition ({added} new lines)" should be gone
        assert "Significant addition (" not in content
        assert "Significant code change detected" in content

    def test_tip_format_in_suggest(self):
        """Suggest messages should use short tip format."""
        pre_tool_path = HOOKS_DIR / "unified_pre_tool.py"
        content = pre_tool_path.read_text()
        assert 'Tip: /implement handles testing, review, and docs automatically.' in content

    def test_block_available_via_env(self):
        """ENFORCEMENT_LEVEL=block should still be supported."""
        pre_tool_path = HOOKS_DIR / "unified_pre_tool.py"
        content = pre_tool_path.read_text()
        assert 'level == "block"' in content

    def test_off_available_via_env(self):
        """ENFORCEMENT_LEVEL=off should still be supported."""
        pre_tool_path = HOOKS_DIR / "unified_pre_tool.py"
        content = pre_tool_path.read_text()
        assert 'level == "off"' in content


# ============================================================================
# Deviation Logging Tests
# ============================================================================

class TestDeviationLogging:
    """Test deviation logging to .claude/logs/deviations.jsonl."""

    def test_log_deviation_creates_entry(self):
        """_log_deviation should write JSONL entry."""
        sys.path.insert(0, str(HOOKS_DIR))
        from unified_pre_tool import _log_deviation

        with tempfile.TemporaryDirectory() as tmpdir:
            with patch.dict(os.environ, {"CLAUDE_SESSION_ID": "test-session"}):
                with patch("os.getcwd", return_value=tmpdir):
                    _log_deviation("test.py", "Edit", "New function detected")

            log_file = Path(tmpdir) / ".claude" / "logs" / "deviations.jsonl"
            assert log_file.exists()

            entry = json.loads(log_file.read_text().strip())
            assert entry["file"] == "test.py"
            assert entry["tool"] == "Edit"
            assert entry["reason"] == "New function detected"
            assert entry["session_id"] == "test-session"
            assert "timestamp" in entry

    def test_log_deviation_appends(self):
        """Multiple deviations should append, not overwrite."""
        from unified_pre_tool import _log_deviation

        with tempfile.TemporaryDirectory() as tmpdir:
            with patch("os.getcwd", return_value=tmpdir):
                _log_deviation("a.py", "Edit", "reason1")
                _log_deviation("b.py", "Write", "reason2")

            log_file = Path(tmpdir) / ".claude" / "logs" / "deviations.jsonl"
            lines = log_file.read_text().strip().split("\n")
            assert len(lines) == 2

    def test_log_deviation_never_fails(self):
        """Logging should never raise exceptions."""
        from unified_pre_tool import _log_deviation

        with patch("os.getcwd", return_value="/nonexistent/path"):
            # Should not raise
            _log_deviation("test.py", "Edit", "reason")

    def test_log_deviation_jsonl_format(self):
        """Each line should be valid JSON."""
        from unified_pre_tool import _log_deviation

        with tempfile.TemporaryDirectory() as tmpdir:
            with patch("os.getcwd", return_value=tmpdir):
                _log_deviation("test.py", "Edit", "reason")

            log_file = Path(tmpdir) / ".claude" / "logs" / "deviations.jsonl"
            for line in log_file.read_text().strip().split("\n"):
                parsed = json.loads(line)  # Should not raise
                assert isinstance(parsed, dict)

    def test_not_logged_when_in_pipeline(self):
        """Deviation logging function exists but pipeline agents skip enforcement entirely."""
        # This tests that the code path for pipeline agents returns before reaching _log_deviation
        pre_tool_path = HOOKS_DIR / "unified_pre_tool.py"
        content = pre_tool_path.read_text()
        # Pipeline agents return "allow" before reaching significance checks
        assert "Pipeline agent" in content
        assert "authorized" in content


# ============================================================================
# Main Hook Integration Tests
# ============================================================================

class TestMainHookIntegration:
    """Test the main() function end-to-end."""

    def _run_main(self, user_prompt: str, env_overrides: dict | None = None) -> int:
        """Helper to run main() with given prompt and env."""
        import importlib
        env = {"ENFORCE_WORKFLOW": "true", "QUALITY_NUDGE_ENABLED": "true"}
        if env_overrides:
            env.update(env_overrides)
        with patch.dict(os.environ, env, clear=False):
            import unified_prompt_validator as upv
            importlib.reload(upv)
            input_data = json.dumps({"userPrompt": user_prompt})
            with patch("sys.stdin") as mock_stdin:
                mock_stdin.read.return_value = input_data
                return upv.main()

    def test_blocking_bypass_returns_2(self):
        """gh issue create should return exit code 2."""
        assert self._run_main("gh issue create --title test") == 2

    def test_nudge_returns_0(self):
        """Implementation intent should return exit code 0 (non-blocking)."""
        assert self._run_main("implement JWT authentication feature") == 0

    def test_no_match_returns_0(self):
        """Non-matching prompt should return exit code 0."""
        assert self._run_main("hello world") == 0
