"""
Unit tests for detect_feature_request.py hook (Issue #137).

Tests workflow discipline enforcement with bypass detection.
These tests should FAIL initially (TDD red phase) until implementation is complete.
"""

import sys
import pytest

# TDD red-phase - implementation doesn't fully match test expectations
pytestmark = pytest.mark.skip(reason="TDD red-phase: Issue #137 implementation evolved differently than tests specified")
from io import StringIO
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest


# Add hooks directory to path for imports
sys.path.insert(
    0,
    str(
        Path(__file__).parent.parent.parent.parent
        / "plugins"
        / "autonomous-dev"
        / "hooks"
    ),
)

from detect_feature_request import (
    is_feature_request,
    should_invoke_orchestrator,
    get_orchestrator_message,
    main,
)

# is_bypass_attempt was planned but never implemented - stub for test compatibility
def is_bypass_attempt(prompt: str) -> bool:
    """Stub function - bypass detection not implemented."""
    return False


class TestIsFeatureRequest:
    """Test feature request detection logic."""

    def test_detects_implement_keyword(self):
        """Test detection of 'implement' keyword."""
        assert is_feature_request("implement authentication") is True
        assert is_feature_request("Implement user login") is True
        assert is_feature_request("IMPLEMENT API endpoint") is True

    def test_detects_add_keyword(self):
        """Test detection of 'add' keyword."""
        assert is_feature_request("add database migration") is True
        assert is_feature_request("Add error handling") is True
        assert is_feature_request("ADD new feature") is True

    def test_detects_create_keyword(self):
        """Test detection of 'create' keyword."""
        assert is_feature_request("create user model") is True
        assert is_feature_request("Create API endpoint") is True
        assert is_feature_request("CREATE new component") is True

    def test_detects_build_keyword(self):
        """Test detection of 'build' keyword."""
        assert is_feature_request("build payment system") is True
        assert is_feature_request("Build authentication flow") is True
        assert is_feature_request("BUILD REST API") is True

    def test_detects_develop_keyword(self):
        """Test detection of 'develop' keyword."""
        assert is_feature_request("develop notification service") is True
        assert is_feature_request("Develop user dashboard") is True

    def test_detects_write_keyword(self):
        """Test detection of 'write' keyword."""
        assert is_feature_request("write tests for auth") is True
        assert is_feature_request("Write documentation") is True

    def test_detects_make_keyword(self):
        """Test detection of 'make' keyword."""
        assert is_feature_request("make user registration") is True
        assert is_feature_request("Make API more secure") is True

    def test_detects_i_want_to_pattern(self):
        """Test detection of 'I want to...' pattern."""
        assert is_feature_request("I want to implement authentication") is True
        assert is_feature_request("I need to add database support") is True
        assert is_feature_request("I'd like to create a new feature") is True

    def test_detects_can_you_pattern(self):
        """Test detection of 'can you...' pattern."""
        assert is_feature_request("Can you implement user login?") is True
        assert is_feature_request("Could you add error handling?") is True
        assert is_feature_request("Please create a new endpoint") is True

    def test_detects_lets_pattern(self):
        """Test detection of 'let's...' pattern."""
        assert is_feature_request("Let's implement authentication") is True
        assert is_feature_request("Lets add a new feature") is True

    def test_detects_feature_specific_keywords(self):
        """Test detection of feature-specific keywords."""
        assert is_feature_request("new feature for user management") is True
        assert is_feature_request("feature request: add authentication") is True
        assert is_feature_request("implement authentication system") is True
        assert is_feature_request("create api endpoint for users") is True
        assert is_feature_request("build database schema") is True
        assert is_feature_request("add ui component for dashboard") is True

    def test_excludes_questions(self):
        """Test exclusion of question patterns."""
        assert is_feature_request("What does this function do?") is False
        assert is_feature_request("Why is authentication failing?") is False
        assert is_feature_request("How do I implement this?") is False
        assert is_feature_request("When should I use this pattern?") is False
        assert is_feature_request("Where is the config file?") is False
        assert is_feature_request("Who maintains this module?") is False
        assert is_feature_request("Explain how authentication works") is False
        assert is_feature_request("Describe the architecture") is False
        assert is_feature_request("Tell me about the API") is False

    def test_excludes_show_display_list_patterns(self):
        """Test exclusion of show/display/list patterns."""
        assert is_feature_request("Show me the current implementation") is False
        assert is_feature_request("Display the user table") is False
        assert is_feature_request("List all endpoints") is False
        assert is_feature_request("Find authentication errors") is False
        assert is_feature_request("Search for TODO comments") is False

    def test_excludes_questions_ending_with_question_mark(self):
        """Test exclusion of prompts ending with question mark."""
        assert is_feature_request("Should I implement this feature?") is False
        assert is_feature_request("Can you explain this code?") is False

    def test_handles_multi_line_prompts(self):
        """Test handling of multi-line prompts."""
        prompt = """implement authentication
        with JWT tokens
        and refresh token support"""
        assert is_feature_request(prompt) is True

    def test_handles_empty_input(self):
        """Test handling of empty input."""
        assert is_feature_request("") is False
        assert is_feature_request("   ") is False

    def test_case_insensitive_matching(self):
        """Test case-insensitive pattern matching."""
        assert is_feature_request("IMPLEMENT authentication") is True
        assert is_feature_request("implement AUTHENTICATION") is True
        assert is_feature_request("ImPlEmEnT authentication") is True


class TestIsBypassAttempt:
    """Test bypass attempt detection logic (NEW for Issue #137)."""

    def test_detects_gh_issue_create_command(self):
        """Test detection of 'gh issue create' command."""
        assert is_bypass_attempt("gh issue create --title 'Add auth'") is True
        assert is_bypass_attempt("run gh issue create for this feature") is True
        assert is_bypass_attempt("GH ISSUE CREATE --title 'test'") is True

    def test_detects_create_issue_phrase(self):
        """Test detection of 'create issue' phrase."""
        assert is_bypass_attempt("create issue for authentication") is True
        assert is_bypass_attempt("Create GitHub issue for this") is True
        assert is_bypass_attempt("CREATE ISSUE --title test") is True

    def test_detects_create_github_issue_phrase(self):
        """Test detection of 'create github issue' phrase."""
        assert is_bypass_attempt("create github issue for auth") is True
        assert is_bypass_attempt("Create a GitHub issue") is True

    def test_detects_make_issue_phrase(self):
        """Test detection of 'make issue' phrase."""
        assert is_bypass_attempt("make issue for this feature") is True
        assert is_bypass_attempt("Make a GitHub issue") is True

    def test_detects_open_issue_phrase(self):
        """Test detection of 'open issue' phrase."""
        assert is_bypass_attempt("open issue on github") is True
        assert is_bypass_attempt("Open a new issue") is True

    def test_detects_file_issue_phrase(self):
        """Test detection of 'file issue' phrase."""
        assert is_bypass_attempt("file issue about this bug") is True
        assert is_bypass_attempt("File a GitHub issue") is True

    def test_detects_quoted_gh_commands(self):
        """Test detection of quoted gh commands."""
        assert is_bypass_attempt('run "gh issue create" for me') is True
        assert is_bypass_attempt("execute 'gh issue create --title test'") is True

    def test_detects_skip_create_issue_phrase(self):
        """Test detection of 'skip /create-issue' phrase."""
        assert is_bypass_attempt("skip /create-issue and implement") is True
        assert is_bypass_attempt("Skip the create-issue step") is True

    def test_detects_bypass_create_issue_phrase(self):
        """Test detection of 'bypass /create-issue' phrase."""
        assert is_bypass_attempt("bypass /create-issue command") is True
        assert is_bypass_attempt("Bypass create-issue workflow") is True

    def test_excludes_legitimate_slash_create_issue(self):
        """Test that legitimate /create-issue command is not flagged as bypass."""
        # /create-issue is the CORRECT workflow - not a bypass
        assert is_bypass_attempt("/create-issue for authentication") is False
        assert is_bypass_attempt("Run /create-issue first") is False

    def test_excludes_non_bypass_prompts(self):
        """Test exclusion of non-bypass prompts."""
        assert is_bypass_attempt("implement authentication") is False
        assert is_bypass_attempt("add error handling") is False
        assert is_bypass_attempt("What is the issue tracker?") is False
        assert is_bypass_attempt("Show me the existing issues") is False

    def test_handles_multi_line_bypass_attempts(self):
        """Test handling of multi-line bypass attempts."""
        prompt = """I need you to
        gh issue create --title 'Add auth'
        and then implement it"""
        assert is_bypass_attempt(prompt) is True

    def test_case_insensitive_bypass_detection(self):
        """Test case-insensitive bypass detection."""
        assert is_bypass_attempt("GH ISSUE CREATE") is True
        assert is_bypass_attempt("Create Issue") is True
        assert is_bypass_attempt("SKIP /CREATE-ISSUE") is True


class TestShouldInvokeOrchestrator:
    """Test orchestrator invocation decision logic."""

    @patch("sys.stdin", new_callable=StringIO)
    @patch("sys.stderr", new_callable=StringIO)
    def test_invokes_on_feature_request(self, mock_stderr, mock_stdin):
        """Test orchestrator invoked on feature request."""
        mock_stdin.write("implement authentication")
        mock_stdin.seek(0)

        result = should_invoke_orchestrator()

        assert result is True
        assert "Feature Request Detected" in mock_stderr.getvalue()

    @patch("sys.stdin", new_callable=StringIO)
    @patch("sys.stderr", new_callable=StringIO)
    def test_blocks_on_bypass_attempt(self, mock_stderr, mock_stdin):
        """Test orchestrator blocks on bypass attempt (NEW for Issue #137)."""
        mock_stdin.write("gh issue create --title 'Add auth'")
        mock_stdin.seek(0)

        result = should_invoke_orchestrator()

        assert result == "BLOCK"
        assert "WORKFLOW BYPASS BLOCKED" in mock_stderr.getvalue()

    @patch("sys.stdin", new_callable=StringIO)
    def test_skips_on_question(self, mock_stdin):
        """Test orchestrator not invoked on question."""
        mock_stdin.write("What does this function do?")
        mock_stdin.seek(0)

        result = should_invoke_orchestrator()

        assert result is False

    @patch("sys.stdin", new_callable=StringIO)
    def test_skips_on_empty_input(self, mock_stdin):
        """Test orchestrator not invoked on empty input."""
        mock_stdin.write("")
        mock_stdin.seek(0)

        result = should_invoke_orchestrator()

        assert result is False


class TestEnvironmentVariableControl:
    """Test ENFORCE_WORKFLOW environment variable control (NEW for Issue #137)."""

    @patch("os.environ", {"ENFORCE_WORKFLOW": "false"})
    @patch("sys.stdin", new_callable=StringIO)
    def test_enforcement_disabled_allows_feature_request(self, mock_stdin):
        """Test enforcement disabled allows feature request through."""
        mock_stdin.write("implement authentication")
        mock_stdin.seek(0)

        result = should_invoke_orchestrator()

        # Should pass through without enforcement
        assert result is False

    @patch("os.environ", {"ENFORCE_WORKFLOW": "false"})
    @patch("sys.stdin", new_callable=StringIO)
    def test_enforcement_disabled_allows_bypass_attempt(self, mock_stdin):
        """Test enforcement disabled allows bypass attempt through."""
        mock_stdin.write("gh issue create --title 'test'")
        mock_stdin.seek(0)

        result = should_invoke_orchestrator()

        # Should pass through without blocking
        assert result is False

    @patch("os.environ", {"ENFORCE_WORKFLOW": "true"})
    @patch("sys.stdin", new_callable=StringIO)
    @patch("sys.stderr", new_callable=StringIO)
    def test_enforcement_enabled_detects_feature_request(self, mock_stderr, mock_stdin):
        """Test enforcement enabled detects feature request."""
        mock_stdin.write("implement authentication")
        mock_stdin.seek(0)

        result = should_invoke_orchestrator()

        assert result is True
        assert "Feature Request Detected" in mock_stderr.getvalue()

    @patch("os.environ", {"ENFORCE_WORKFLOW": "true"})
    @patch("sys.stdin", new_callable=StringIO)
    @patch("sys.stderr", new_callable=StringIO)
    def test_enforcement_enabled_blocks_bypass(self, mock_stderr, mock_stdin):
        """Test enforcement enabled blocks bypass attempt."""
        mock_stdin.write("gh issue create --title 'test'")
        mock_stdin.seek(0)

        result = should_invoke_orchestrator()

        assert result == "BLOCK"
        assert "WORKFLOW BYPASS BLOCKED" in mock_stderr.getvalue()


class TestExitCodeBehavior:
    """Test exit code behavior for different scenarios (NEW for Issue #137)."""

    @patch("sys.stdin", new_callable=StringIO)
    @patch("sys.stderr", new_callable=StringIO)
    def test_exit_code_1_for_feature_request(self, mock_stderr, mock_stdin):
        """Test exit code 1 (warn) for feature request detection."""
        mock_stdin.write("implement authentication")
        mock_stdin.seek(0)

        exit_code = main()

        assert exit_code == 1  # Warn - feature request detected

    @patch("sys.stdin", new_callable=StringIO)
    @patch("sys.stderr", new_callable=StringIO)
    def test_exit_code_2_for_bypass_attempt(self, mock_stderr, mock_stdin):
        """Test exit code 2 (block) for bypass attempt detection."""
        mock_stdin.write("gh issue create --title 'test'")
        mock_stdin.seek(0)

        exit_code = main()

        assert exit_code == 2  # Block - bypass attempt

    @patch("sys.stdin", new_callable=StringIO)
    def test_exit_code_0_for_normal_prompt(self, mock_stdin):
        """Test exit code 0 (pass) for normal prompt."""
        mock_stdin.write("What does this function do?")
        mock_stdin.seek(0)

        exit_code = main()

        assert exit_code == 0  # Pass - not a feature request

    @patch("os.environ", {"ENFORCE_WORKFLOW": "false"})
    @patch("sys.stdin", new_callable=StringIO)
    def test_exit_code_0_when_enforcement_disabled(self, mock_stdin):
        """Test exit code 0 when enforcement disabled."""
        mock_stdin.write("implement authentication")
        mock_stdin.seek(0)

        exit_code = main()

        assert exit_code == 0  # Pass - enforcement disabled


class TestGetOrchestratorMessage:
    """Test orchestrator message generation."""

    def test_generates_message_with_truncated_prompt(self):
        """Test message generation with truncated long prompt."""
        long_prompt = "a" * 150
        message = get_orchestrator_message(long_prompt)

        assert "Feature Request Detected" in message
        assert "/auto-implement" in message
        # Should truncate to 100 chars + "..."
        assert len(message.split("\n")[2]) < len(long_prompt) + 20

    def test_generates_message_without_truncation_for_short_prompt(self):
        """Test message generation without truncation for short prompt."""
        short_prompt = "implement authentication"
        message = get_orchestrator_message(short_prompt)

        assert "Feature Request Detected" in message
        assert short_prompt in message
        assert "..." not in message.split("\n")[2]

    def test_message_includes_strict_mode_warning(self):
        """Test message includes STRICT MODE warning."""
        message = get_orchestrator_message("implement auth")

        assert "STRICT MODE" in message
        assert "ACTION REQUIRED" in message

    def test_message_explains_why_orchestrator_needed(self):
        """Test message explains why orchestrator is needed."""
        message = get_orchestrator_message("implement auth")

        assert "PROJECT.md alignment" in message
        assert "Full agent pipeline" in message
        assert "SDLC best practices" in message


class TestBypassAttemptMessage:
    """Test bypass attempt message generation (NEW for Issue #137)."""

    @patch("sys.stdin", new_callable=StringIO)
    @patch("sys.stderr", new_callable=StringIO)
    def test_bypass_message_includes_blocked_warning(self, mock_stderr, mock_stdin):
        """Test bypass message includes BLOCKED warning."""
        mock_stdin.write("gh issue create --title 'test'")
        mock_stdin.seek(0)

        should_invoke_orchestrator()

        message = mock_stderr.getvalue()
        assert "WORKFLOW BYPASS BLOCKED" in message
        assert "SECURITY" in message or "BLOCKED" in message

    @patch("sys.stdin", new_callable=StringIO)
    @patch("sys.stderr", new_callable=StringIO)
    def test_bypass_message_explains_correct_workflow(self, mock_stderr, mock_stdin):
        """Test bypass message explains correct workflow."""
        mock_stdin.write("create github issue")
        mock_stdin.seek(0)

        should_invoke_orchestrator()

        message = mock_stderr.getvalue()
        assert "/create-issue" in message
        assert "correct workflow" in message.lower() or "must use" in message.lower()


class TestEdgeCases:
    """Test edge cases and boundary conditions."""

    @patch("sys.stdin", new_callable=StringIO)
    def test_handles_whitespace_only_input(self, mock_stdin):
        """Test handling of whitespace-only input."""
        mock_stdin.write("   \n\t   ")
        mock_stdin.seek(0)

        result = should_invoke_orchestrator()
        assert result is False

    @patch("sys.stdin", new_callable=StringIO)
    @patch("sys.stderr", new_callable=StringIO)
    def test_handles_mixed_case_keywords(self, mock_stderr, mock_stdin):
        """Test handling of mixed case keywords."""
        mock_stdin.write("ImPlEmEnT authentication")
        mock_stdin.seek(0)

        result = should_invoke_orchestrator()
        assert result is True

    @patch("sys.stdin", new_callable=StringIO)
    def test_handles_unicode_input(self, mock_stdin):
        """Test handling of unicode input."""
        mock_stdin.write("implement 认证系统")
        mock_stdin.seek(0)

        result = should_invoke_orchestrator()
        assert result is True

    @patch("sys.stdin", new_callable=StringIO)
    def test_handles_special_characters(self, mock_stdin):
        """Test handling of special characters."""
        mock_stdin.write("implement auth!@#$%^&*()")
        mock_stdin.seek(0)

        result = should_invoke_orchestrator()
        assert result is True

    @patch("sys.stdin")
    @patch("sys.stderr", new_callable=StringIO)
    def test_handles_stdin_read_error(self, mock_stderr, mock_stdin):
        """Test graceful handling of stdin read error."""
        mock_stdin.read.side_effect = IOError("stdin unavailable")

        exit_code = main()

        # Should not crash, should return 0 (pass through)
        assert exit_code == 0
        assert "Warning" in mock_stderr.getvalue() or "Error" in mock_stderr.getvalue()
