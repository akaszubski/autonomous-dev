#!/usr/bin/env python3
"""
Unit tests for block_git_bypass.py hook (TDD Red Phase).

Tests PreCommit hook that blocks git commit --no-verify to enforce workflow.

TDD Mode: These tests are written BEFORE implementation.
All tests should FAIL initially (ImportError: module not found).

Test Strategy:
- Test --no-verify detection in git commands
- Test ALLOW_GIT_BYPASS environment variable bypass
- Test exit codes (EXIT_SUCCESS=0 vs EXIT_BLOCK=2)
- Test violation logging integration
- Test helpful error messages

Hook Purpose:
- Prevents bypassing pre-commit hooks with --no-verify
- Logs violations to workflow_violation_logger
- Provides clear guidance on proper workflow
- Can be bypassed with ALLOW_GIT_BYPASS=true for emergencies

Test Coverage Target: 95%+

Author: test-master agent
Date: 2026-01-19
Issue: #250 (Enforce /implement workflow)
Phase: TDD Red (tests written BEFORE implementation)
"""

import json
import os
import sys
import subprocess
from pathlib import Path
from unittest.mock import MagicMock, mock_open, patch, call
from io import StringIO

import pytest


# Add hooks directory to path for imports
sys.path.insert(
    0,
    str(
        Path(__file__).parent.parent.parent.parent / ".claude" / "hooks"
    ),
)

# Import will fail - module doesn't exist yet (TDD!)
try:
    from block_git_bypass import (
        main,
        detect_git_bypass,
        is_bypass_allowed,
        output_error,
        EXIT_SUCCESS,
        EXIT_BLOCK,
    )
except ImportError as e:
    pytest.skip(f"Implementation not found (TDD red phase): {e}", allow_module_level=True)


class TestGitBypassDetection:
    """Test detection of --no-verify flag in git commands."""

    def test_detects_no_verify_flag(self):
        """Test detection of --no-verify flag."""
        command = "git commit --no-verify -m 'bypass hooks'"

        is_bypass, reason = detect_git_bypass(command)

        assert is_bypass is True
        assert "--no-verify" in reason

    def test_detects_no_verify_short_form(self):
        """Test detection of -n short form."""
        command = "git commit -n -m 'bypass hooks'"

        is_bypass, reason = detect_git_bypass(command)

        assert is_bypass is True
        assert "-n" in reason or "no-verify" in reason.lower()

    def test_detects_no_verify_with_equals(self):
        """Test detection of --no-verify=true form."""
        command = "git commit --no-verify=true -m 'bypass'"

        is_bypass, reason = detect_git_bypass(command)

        assert is_bypass is True

    def test_allows_normal_git_commit(self):
        """Test normal git commit is allowed."""
        command = "git commit -m 'normal commit'"

        is_bypass, reason = detect_git_bypass(command)

        assert is_bypass is False
        assert reason == ""

    def test_allows_non_commit_commands(self):
        """Test non-commit git commands are allowed."""
        command = "git status"

        is_bypass, reason = detect_git_bypass(command)

        assert is_bypass is False

    def test_detects_bypass_in_complex_command(self):
        """Test detection in complex command with multiple flags."""
        command = "git commit -a --no-verify -m 'message' --author='user@example.com'"

        is_bypass, reason = detect_git_bypass(command)

        assert is_bypass is True

    def test_case_insensitive_detection(self):
        """Test detection is case-insensitive."""
        command = "git commit --NO-VERIFY -m 'bypass'"

        is_bypass, reason = detect_git_bypass(command)

        assert is_bypass is True


class TestBypassAllowedCheck:
    """Test ALLOW_GIT_BYPASS environment variable."""

    def test_bypass_allowed_when_env_true(self, monkeypatch):
        """Test bypass is allowed when ALLOW_GIT_BYPASS=true."""
        monkeypatch.setenv("ALLOW_GIT_BYPASS", "true")

        assert is_bypass_allowed() is True

    def test_bypass_allowed_case_insensitive(self, monkeypatch):
        """Test ALLOW_GIT_BYPASS is case-insensitive."""
        monkeypatch.setenv("ALLOW_GIT_BYPASS", "TRUE")

        assert is_bypass_allowed() is True

    def test_bypass_not_allowed_when_env_false(self, monkeypatch):
        """Test bypass is not allowed when ALLOW_GIT_BYPASS=false."""
        monkeypatch.setenv("ALLOW_GIT_BYPASS", "false")

        assert is_bypass_allowed() is False

    def test_bypass_not_allowed_when_env_unset(self, monkeypatch):
        """Test bypass is not allowed when ALLOW_GIT_BYPASS is unset."""
        monkeypatch.delenv("ALLOW_GIT_BYPASS", raising=False)

        assert is_bypass_allowed() is False

    def test_bypass_not_allowed_when_env_invalid(self, monkeypatch):
        """Test bypass is not allowed with invalid value."""
        monkeypatch.setenv("ALLOW_GIT_BYPASS", "maybe")

        assert is_bypass_allowed() is False


class TestExitCodes:
    """Test exit codes (EXIT_SUCCESS=0 vs EXIT_BLOCK=2)."""

    @patch("sys.argv", ["block_git_bypass.py", "git", "commit", "-m", "message"])
    @patch("sys.stderr", new_callable=StringIO)
    def test_normal_commit_exits_success(self, mock_stderr):
        """Test normal commit exits with EXIT_SUCCESS (0)."""
        with pytest.raises(SystemExit) as exc_info:
            main()

        assert exc_info.value.code == EXIT_SUCCESS

    @patch("sys.argv", ["block_git_bypass.py", "git", "commit", "--no-verify", "-m", "bypass"])
    @patch("sys.stderr", new_callable=StringIO)
    @patch.dict("os.environ", {}, clear=True)
    def test_bypass_attempt_exits_block(self, mock_stderr):
        """Test bypass attempt exits with EXIT_BLOCK (2)."""
        with pytest.raises(SystemExit) as exc_info:
            main()

        assert exc_info.value.code == EXIT_BLOCK

    @patch("sys.argv", ["block_git_bypass.py", "git", "commit", "--no-verify", "-m", "bypass"])
    @patch("sys.stderr", new_callable=StringIO)
    @patch.dict("os.environ", {"ALLOW_GIT_BYPASS": "true"})
    def test_allowed_bypass_exits_success(self, mock_stderr):
        """Test allowed bypass exits with EXIT_SUCCESS (0)."""
        with pytest.raises(SystemExit) as exc_info:
            main()

        assert exc_info.value.code == EXIT_SUCCESS


class TestViolationLogging:
    """Test integration with workflow_violation_logger."""

    @patch("sys.argv", ["block_git_bypass.py", "git", "commit", "--no-verify", "-m", "bypass"])
    @patch("sys.stderr", new_callable=StringIO)
    @patch.dict("os.environ", {}, clear=True)
    @patch("block_git_bypass.WorkflowViolationLogger")
    def test_logs_violation_when_blocking(self, mock_logger_class, mock_stderr):
        """Test violation is logged when blocking bypass attempt."""
        mock_logger = MagicMock()
        mock_logger_class.return_value = mock_logger

        with pytest.raises(SystemExit) as exc_info:
            main()

        # Should have logged the violation
        mock_logger.log_git_bypass_attempt.assert_called_once()
        call_args = mock_logger.log_git_bypass_attempt.call_args
        assert "git commit --no-verify" in call_args[1]["command"]
        assert "--no-verify" in call_args[1]["reason"]

    @patch("sys.argv", ["block_git_bypass.py", "git", "commit", "-m", "normal"])
    @patch("sys.stderr", new_callable=StringIO)
    @patch("block_git_bypass.WorkflowViolationLogger")
    def test_no_logging_for_normal_commits(self, mock_logger_class, mock_stderr):
        """Test no violation logged for normal commits."""
        mock_logger = MagicMock()
        mock_logger_class.return_value = mock_logger

        with pytest.raises(SystemExit) as exc_info:
            main()

        # Should NOT have logged a violation
        mock_logger.log_git_bypass_attempt.assert_not_called()

    @patch("sys.argv", ["block_git_bypass.py", "git", "commit", "--no-verify", "-m", "bypass"])
    @patch("sys.stderr", new_callable=StringIO)
    @patch.dict("os.environ", {"ALLOW_GIT_BYPASS": "true"})
    @patch("block_git_bypass.WorkflowViolationLogger")
    def test_no_logging_when_bypass_allowed(self, mock_logger_class, mock_stderr):
        """Test no violation logged when bypass is explicitly allowed."""
        mock_logger = MagicMock()
        mock_logger_class.return_value = mock_logger

        with pytest.raises(SystemExit) as exc_info:
            main()

        # Should NOT have logged a violation (bypass was allowed)
        mock_logger.log_git_bypass_attempt.assert_not_called()

    @patch("sys.argv", ["block_git_bypass.py", "git", "commit", "--no-verify", "-m", "bypass"])
    @patch("sys.stderr", new_callable=StringIO)
    @patch.dict("os.environ", {"CLAUDE_AGENT_NAME": "researcher"})
    @patch("block_git_bypass.WorkflowViolationLogger")
    def test_logs_agent_name_if_available(self, mock_logger_class, mock_stderr):
        """Test violation includes agent name if CLAUDE_AGENT_NAME is set."""
        mock_logger = MagicMock()
        mock_logger_class.return_value = mock_logger

        with pytest.raises(SystemExit) as exc_info:
            main()

        # Should have logged with agent name
        call_args = mock_logger.log_git_bypass_attempt.call_args
        assert call_args[1]["agent_name"] == "researcher"


class TestErrorMessages:
    """Test helpful error messages."""

    @patch("sys.argv", ["block_git_bypass.py", "git", "commit", "--no-verify", "-m", "bypass"])
    @patch("sys.stderr", new_callable=StringIO)
    @patch.dict("os.environ", {}, clear=True)
    def test_error_message_explains_why_blocked(self, mock_stderr):
        """Test error message explains why commit was blocked."""
        with pytest.raises(SystemExit) as exc_info:
            main()

        error_output = mock_stderr.getvalue()

        assert "--no-verify" in error_output
        assert "blocked" in error_output.lower() or "denied" in error_output.lower()

    @patch("sys.argv", ["block_git_bypass.py", "git", "commit", "--no-verify", "-m", "bypass"])
    @patch("sys.stderr", new_callable=StringIO)
    @patch.dict("os.environ", {}, clear=True)
    def test_error_message_includes_workflow_guidance(self, mock_stderr):
        """Test error message includes workflow guidance."""
        with pytest.raises(SystemExit) as exc_info:
            main()

        error_output = mock_stderr.getvalue()

        # Should mention /implement or proper workflow
        assert "/implement" in error_output or "workflow" in error_output.lower()

    @patch("sys.argv", ["block_git_bypass.py", "git", "commit", "--no-verify", "-m", "bypass"])
    @patch("sys.stderr", new_callable=StringIO)
    @patch.dict("os.environ", {}, clear=True)
    def test_error_message_includes_bypass_instructions(self, mock_stderr):
        """Test error message includes instructions to bypass in emergencies."""
        with pytest.raises(SystemExit) as exc_info:
            main()

        error_output = mock_stderr.getvalue()

        # Should mention ALLOW_GIT_BYPASS for emergencies
        assert "ALLOW_GIT_BYPASS" in error_output


class TestOutputError:
    """Test output_error function."""

    @patch("sys.stderr", new_callable=StringIO)
    def test_output_error_writes_to_stderr(self, mock_stderr):
        """Test output_error writes to stderr."""
        output_error("Test error message")

        assert "Test error message" in mock_stderr.getvalue()

    @patch("sys.stderr", new_callable=StringIO)
    def test_output_error_includes_formatting(self, mock_stderr):
        """Test output_error includes formatting for visibility."""
        output_error("Blocked")

        output = mock_stderr.getvalue()
        # Should have some visual formatting (like ERROR:, ===, etc.)
        assert any(marker in output for marker in ["ERROR", "===", "***", "BLOCKED"])


class TestGracefulDegradation:
    """Test error handling and graceful degradation."""

    @patch("sys.argv", ["block_git_bypass.py"])
    @patch("sys.stderr", new_callable=StringIO)
    def test_handles_missing_git_command(self, mock_stderr):
        """Test handles missing git command gracefully."""
        with pytest.raises(SystemExit) as exc_info:
            main()

        # Should exit successfully (allow by default on errors)
        assert exc_info.value.code == EXIT_SUCCESS

    @patch("sys.argv", ["block_git_bypass.py", "git", "commit", "--no-verify"])
    @patch("sys.stderr", new_callable=StringIO)
    @patch.dict("os.environ", {}, clear=True)
    @patch("block_git_bypass.WorkflowViolationLogger", side_effect=Exception("Logger error"))
    def test_continues_if_logging_fails(self, mock_logger_class, mock_stderr):
        """Test hook continues even if logging fails."""
        with pytest.raises(SystemExit) as exc_info:
            main()

        # Should still block the commit (logging failure shouldn't affect enforcement)
        assert exc_info.value.code == EXIT_BLOCK

    @patch("sys.argv", ["block_git_bypass.py", "git", "commit", "-m", "test"])
    @patch("sys.stderr", new_callable=StringIO)
    @patch("block_git_bypass.detect_git_bypass", side_effect=Exception("Detection error"))
    def test_allows_on_detection_error(self, mock_detect, mock_stderr):
        """Test allows commit if detection logic fails (fail open)."""
        with pytest.raises(SystemExit) as exc_info:
            main()

        # Should allow on error (fail open, don't block user)
        assert exc_info.value.code == EXIT_SUCCESS


class TestIntegrationScenarios:
    """Test complete workflow scenarios."""

    @patch("sys.argv", ["block_git_bypass.py", "git", "commit", "-m", "feat: add auth"])
    @patch("sys.stderr", new_callable=StringIO)
    @patch("block_git_bypass.WorkflowViolationLogger")
    def test_scenario_normal_commit_allowed(self, mock_logger_class, mock_stderr):
        """Test scenario: Developer commits normally through /implement workflow."""
        mock_logger = MagicMock()
        mock_logger_class.return_value = mock_logger

        with pytest.raises(SystemExit) as exc_info:
            main()

        assert exc_info.value.code == EXIT_SUCCESS
        mock_logger.log_git_bypass_attempt.assert_not_called()

    @patch("sys.argv", ["block_git_bypass.py", "git", "commit", "--no-verify", "-m", "quick fix"])
    @patch("sys.stderr", new_callable=StringIO)
    @patch.dict("os.environ", {}, clear=True)
    @patch("block_git_bypass.WorkflowViolationLogger")
    def test_scenario_bypass_attempt_blocked(self, mock_logger_class, mock_stderr):
        """Test scenario: Claude tries to bypass hooks autonomously."""
        mock_logger = MagicMock()
        mock_logger_class.return_value = mock_logger

        with pytest.raises(SystemExit) as exc_info:
            main()

        assert exc_info.value.code == EXIT_BLOCK
        mock_logger.log_git_bypass_attempt.assert_called_once()
        assert "blocked" in mock_stderr.getvalue().lower() or "denied" in mock_stderr.getvalue().lower()

    @patch("sys.argv", ["block_git_bypass.py", "git", "commit", "--no-verify", "-m", "emergency fix"])
    @patch("sys.stderr", new_callable=StringIO)
    @patch.dict("os.environ", {"ALLOW_GIT_BYPASS": "true"})
    @patch("block_git_bypass.WorkflowViolationLogger")
    def test_scenario_emergency_bypass_allowed(self, mock_logger_class, mock_stderr):
        """Test scenario: User explicitly allows bypass for emergency."""
        mock_logger = MagicMock()
        mock_logger_class.return_value = mock_logger

        with pytest.raises(SystemExit) as exc_info:
            main()

        assert exc_info.value.code == EXIT_SUCCESS
        mock_logger.log_git_bypass_attempt.assert_not_called()


class TestCommandLineArguments:
    """Test command-line argument parsing."""

    @patch("sys.argv", ["block_git_bypass.py", "git", "commit", "-m", "message", "--no-verify"])
    @patch("sys.stderr", new_callable=StringIO)
    @patch.dict("os.environ", {}, clear=True)
    def test_detects_no_verify_anywhere_in_args(self, mock_stderr):
        """Test detection works regardless of flag position."""
        with pytest.raises(SystemExit) as exc_info:
            main()

        assert exc_info.value.code == EXIT_BLOCK

    @patch("sys.argv", ["block_git_bypass.py", "git", "commit", "-am", "message"])
    @patch("sys.stderr", new_callable=StringIO)
    def test_allows_combined_short_flags_without_n(self, mock_stderr):
        """Test allows combined short flags that don't include -n."""
        with pytest.raises(SystemExit) as exc_info:
            main()

        assert exc_info.value.code == EXIT_SUCCESS

    @patch("sys.argv", ["block_git_bypass.py", "git", "commit", "-anm", "message"])
    @patch("sys.stderr", new_callable=StringIO)
    @patch.dict("os.environ", {}, clear=True)
    def test_detects_n_in_combined_short_flags(self, mock_stderr):
        """Test detects -n even in combined short flags."""
        with pytest.raises(SystemExit) as exc_info:
            main()

        assert exc_info.value.code == EXIT_BLOCK


if __name__ == "__main__":
    # Run tests with minimal verbosity (Issue #90 - prevent subprocess deadlock)
    pytest.main([__file__, "--tb=line", "-q"])
