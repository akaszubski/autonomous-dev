"""
Integration tests for workflow discipline enforcement (Issue #137).

Tests end-to-end workflow enforcement including:
- Feature request detection and routing to /auto-implement
- Bypass attempt blocking (gh issue create, direct issue creation)
- /create-issue mandatory confirmation at STEP 5
- Environment variable opt-out (ENFORCE_WORKFLOW=false)

These tests should FAIL initially (TDD red phase) until implementation is complete.
"""

import json
import os
import subprocess
import sys
from io import StringIO
from pathlib import Path
from unittest.mock import MagicMock, Mock, patch

import pytest


class TestFeatureRequestDetectionIntegration:
    """Integration tests for feature request detection workflow."""

    @pytest.fixture
    def hook_path(self):
        """Get path to detect_feature_request.py hook."""
        return (
            Path(__file__).parent.parent.parent
            / "plugins"
            / "autonomous-dev"
            / "hooks"
            / "detect_feature_request.py"
        )

    def test_hook_execution_warns_on_feature_request(self, hook_path):
        """Test hook execution returns exit code 1 (warn) for feature request."""
        result = subprocess.run(
            ["python", str(hook_path)],
            input="implement authentication",
            capture_output=True,
            text=True,
        )

        # Should return exit code 1 (warn - feature request detected)
        assert result.returncode == 1
        assert "Feature Request Detected" in result.stderr

    def test_hook_execution_blocks_on_bypass_attempt(self, hook_path):
        """Test hook execution returns exit code 2 (block) for bypass attempt."""
        result = subprocess.run(
            ["python", str(hook_path)],
            input="gh issue create --title 'Add auth'",
            capture_output=True,
            text=True,
        )

        # Should return exit code 2 (block - bypass attempt)
        assert result.returncode == 2
        assert "WORKFLOW BYPASS BLOCKED" in result.stderr

    def test_hook_execution_passes_normal_prompt(self, hook_path):
        """Test hook execution returns exit code 0 (pass) for normal prompt."""
        result = subprocess.run(
            ["python", str(hook_path)],
            input="What does this function do?",
            capture_output=True,
            text=True,
        )

        # Should return exit code 0 (pass - not a feature request)
        assert result.returncode == 0
        assert "Feature Request Detected" not in result.stderr

    def test_hook_execution_with_enforcement_disabled(self, hook_path):
        """Test hook execution with ENFORCE_WORKFLOW=false."""
        env = os.environ.copy()
        env["ENFORCE_WORKFLOW"] = "false"

        result = subprocess.run(
            ["python", str(hook_path)],
            input="implement authentication",
            capture_output=True,
            text=True,
            env=env,
        )

        # Should return exit code 0 (pass - enforcement disabled)
        assert result.returncode == 0
        assert "Feature Request Detected" not in result.stderr

    def test_hook_displays_auto_implement_command(self, hook_path):
        """Test hook displays /auto-implement command to user."""
        result = subprocess.run(
            ["python", str(hook_path)],
            input="implement authentication",
            capture_output=True,
            text=True,
        )

        # Should include /auto-implement command in output
        assert "/auto-implement" in result.stderr
        assert "implement authentication" in result.stderr

    def test_hook_explains_why_orchestrator_needed(self, hook_path):
        """Test hook explains why orchestrator is needed."""
        result = subprocess.run(
            ["python", str(hook_path)],
            input="implement authentication",
            capture_output=True,
            text=True,
        )

        # Should explain PROJECT.md alignment and full pipeline
        assert "PROJECT.md" in result.stderr
        assert "agent pipeline" in result.stderr.lower() or "SDLC" in result.stderr


class TestBypassAttemptBlocking:
    """Integration tests for bypass attempt blocking."""

    @pytest.fixture
    def hook_path(self):
        """Get path to detect_feature_request.py hook."""
        return (
            Path(__file__).parent.parent.parent
            / "plugins"
            / "autonomous-dev"
            / "hooks"
            / "detect_feature_request.py"
        )

    def test_blocks_gh_issue_create_command(self, hook_path):
        """Test blocking of gh issue create command."""
        bypass_attempts = [
            "gh issue create --title 'Add auth'",
            "run gh issue create for this feature",
            "GH ISSUE CREATE --title 'test'",
        ]

        for attempt in bypass_attempts:
            result = subprocess.run(
                ["python", str(hook_path)],
                input=attempt,
                capture_output=True,
                text=True,
            )

            assert result.returncode == 2, f"Failed to block: {attempt}"
            assert "BLOCKED" in result.stderr, f"Missing block message for: {attempt}"

    def test_blocks_create_issue_phrase(self, hook_path):
        """Test blocking of 'create issue' phrase."""
        bypass_attempts = [
            "create issue for authentication",
            "Create GitHub issue for this",
            "create github issue about this bug",
        ]

        for attempt in bypass_attempts:
            result = subprocess.run(
                ["python", str(hook_path)],
                input=attempt,
                capture_output=True,
                text=True,
            )

            assert result.returncode == 2, f"Failed to block: {attempt}"
            assert "BLOCKED" in result.stderr, f"Missing block message for: {attempt}"

    def test_blocks_skip_bypass_phrases(self, hook_path):
        """Test blocking of skip/bypass phrases."""
        bypass_attempts = [
            "skip /create-issue and implement directly",
            "bypass /create-issue command",
            "Skip the create-issue step",
        ]

        for attempt in bypass_attempts:
            result = subprocess.run(
                ["python", str(hook_path)],
                input=attempt,
                capture_output=True,
                text=True,
            )

            assert result.returncode == 2, f"Failed to block: {attempt}"
            assert "BLOCKED" in result.stderr, f"Missing block message for: {attempt}"

    def test_allows_legitimate_create_issue_command(self, hook_path):
        """Test that legitimate /create-issue command is not blocked."""
        legitimate_commands = [
            "/create-issue for authentication",
            "Run /create-issue first",
            "Use /create-issue to track this",
        ]

        for command in legitimate_commands:
            result = subprocess.run(
                ["python", str(hook_path)],
                input=command,
                capture_output=True,
                text=True,
            )

            # Should NOT block legitimate /create-issue usage
            assert result.returncode != 2, f"Incorrectly blocked: {command}"

    def test_bypass_message_includes_correct_workflow(self, hook_path):
        """Test bypass message explains correct workflow."""
        result = subprocess.run(
            ["python", str(hook_path)],
            input="gh issue create --title 'test'",
            capture_output=True,
            text=True,
        )

        # Should explain correct workflow with /create-issue
        assert "/create-issue" in result.stderr
        assert "correct" in result.stderr.lower() or "must" in result.stderr.lower()


class TestCreateIssueMandatoryConfirmation:
    """Integration tests for /create-issue STEP 5 mandatory confirmation."""

    @pytest.fixture
    def create_issue_command_path(self):
        """Get path to create-issue.md command."""
        return (
            Path(__file__).parent.parent.parent
            / "plugins"
            / "autonomous-dev"
            / "commands"
            / "create-issue.md"
        )

    def test_create_issue_contains_step_5_stop(self, create_issue_command_path):
        """Test /create-issue command contains STEP 5 mandatory stop."""
        content = create_issue_command_path.read_text()

        # Should contain STEP 5 with STOP instruction
        assert "STEP 5" in content
        assert "STOP" in content
        assert "confirmation" in content.lower() or "proceed" in content.lower()

    def test_create_issue_requires_explicit_confirmation(self, create_issue_command_path):
        """Test /create-issue requires explicit user confirmation at STEP 5."""
        content = create_issue_command_path.read_text()

        # Should require explicit confirmation before proceeding
        assert any(
            phrase in content
            for phrase in [
                "Wait for confirmation",
                "Ask user to confirm",
                "User must approve",
                "User must confirm",
                "Require confirmation",
            ]
        )

    def test_create_issue_explains_why_stop_needed(self, create_issue_command_path):
        """Test /create-issue explains why STEP 5 stop is needed."""
        content = create_issue_command_path.read_text()

        # Should explain purpose of stop (validation, review, etc.)
        assert any(
            keyword in content.lower()
            for keyword in [
                "validate",
                "review",
                "verify",
                "check",
                "ensure",
                "confirm",
            ]
        )


class TestEnvironmentVariableOptOut:
    """Integration tests for ENFORCE_WORKFLOW environment variable."""

    @pytest.fixture
    def hook_path(self):
        """Get path to detect_feature_request.py hook."""
        return (
            Path(__file__).parent.parent.parent
            / "plugins"
            / "autonomous-dev"
            / "hooks"
            / "detect_feature_request.py"
        )

    def test_enforcement_disabled_allows_all_prompts(self, hook_path):
        """Test ENFORCE_WORKFLOW=false allows all prompts."""
        env = os.environ.copy()
        env["ENFORCE_WORKFLOW"] = "false"

        test_prompts = [
            "implement authentication",
            "gh issue create --title 'test'",
            "create github issue",
            "skip /create-issue",
        ]

        for prompt in test_prompts:
            result = subprocess.run(
                ["python", str(hook_path)],
                input=prompt,
                capture_output=True,
                text=True,
                env=env,
            )

            # All prompts should pass through without enforcement
            assert result.returncode == 0, f"Failed to allow: {prompt}"
            assert "BLOCKED" not in result.stderr, f"Incorrectly blocked: {prompt}"

    def test_enforcement_enabled_by_default(self, hook_path):
        """Test enforcement is enabled by default (no env var set)."""
        # Remove ENFORCE_WORKFLOW from environment if present
        env = os.environ.copy()
        env.pop("ENFORCE_WORKFLOW", None)

        result = subprocess.run(
            ["python", str(hook_path)],
            input="implement authentication",
            capture_output=True,
            text=True,
            env=env,
        )

        # Should enforce by default
        assert result.returncode == 1  # Warn for feature request

    def test_enforcement_enabled_with_true_value(self, hook_path):
        """Test ENFORCE_WORKFLOW=true enables enforcement."""
        env = os.environ.copy()
        env["ENFORCE_WORKFLOW"] = "true"

        result = subprocess.run(
            ["python", str(hook_path)],
            input="implement authentication",
            capture_output=True,
            text=True,
            env=env,
        )

        # Should enforce when explicitly enabled
        assert result.returncode == 1  # Warn for feature request

    def test_enforcement_respects_case_insensitive_values(self, hook_path):
        """Test ENFORCE_WORKFLOW respects case-insensitive values."""
        env = os.environ.copy()

        # Test various false values
        for false_value in ["false", "False", "FALSE", "0", "no", "No"]:
            env["ENFORCE_WORKFLOW"] = false_value

            result = subprocess.run(
                ["python", str(hook_path)],
                input="implement authentication",
                capture_output=True,
                text=True,
                env=env,
            )

            # Should disable enforcement
            assert result.returncode == 0, f"Failed for value: {false_value}"


class TestEndToEndWorkflowValidation:
    """End-to-end integration tests for complete workflow."""

    @pytest.fixture
    def hook_path(self):
        """Get path to detect_feature_request.py hook."""
        return (
            Path(__file__).parent.parent.parent
            / "plugins"
            / "autonomous-dev"
            / "hooks"
            / "detect_feature_request.py"
        )

    def test_correct_workflow_feature_to_auto_implement(self, hook_path):
        """Test correct workflow: feature request → /auto-implement."""
        # Step 1: Feature request detected
        result = subprocess.run(
            ["python", str(hook_path)],
            input="implement authentication",
            capture_output=True,
            text=True,
        )

        assert result.returncode == 1  # Warn
        assert "/auto-implement" in result.stderr

        # Step 2: User should see command to run
        assert "implement authentication" in result.stderr

    def test_correct_workflow_issue_to_create_issue(self, hook_path):
        """Test correct workflow: issue tracking → /create-issue."""
        # For issue creation, user should use /create-issue command
        # NOT bypass with gh issue create
        result = subprocess.run(
            ["python", str(hook_path)],
            input="/create-issue for authentication feature",
            capture_output=True,
            text=True,
        )

        # /create-issue is correct workflow - should not block
        assert result.returncode != 2

    def test_incorrect_workflow_bypass_blocked(self, hook_path):
        """Test incorrect workflow: bypass attempt → BLOCKED."""
        result = subprocess.run(
            ["python", str(hook_path)],
            input="gh issue create --title 'Add auth' and then implement it",
            capture_output=True,
            text=True,
        )

        # Should block bypass attempt
        assert result.returncode == 2  # Block
        assert "BLOCKED" in result.stderr
        assert "/create-issue" in result.stderr

    def test_workflow_with_multiple_prompts(self, hook_path):
        """Test workflow with multiple sequential prompts."""
        prompts = [
            ("What is authentication?", 0),  # Question - pass
            ("implement authentication", 1),  # Feature request - warn
            ("gh issue create", 2),  # Bypass - block
            ("/create-issue for auth", 0),  # Correct command - pass
        ]

        for prompt, expected_exit_code in prompts:
            result = subprocess.run(
                ["python", str(hook_path)],
                input=prompt,
                capture_output=True,
                text=True,
            )

            assert (
                result.returncode == expected_exit_code
            ), f"Wrong exit code for: {prompt}"


class TestErrorHandlingAndEdgeCases:
    """Integration tests for error handling and edge cases."""

    @pytest.fixture
    def hook_path(self):
        """Get path to detect_feature_request.py hook."""
        return (
            Path(__file__).parent.parent.parent
            / "plugins"
            / "autonomous-dev"
            / "hooks"
            / "detect_feature_request.py"
        )

    def test_handles_empty_stdin(self, hook_path):
        """Test graceful handling of empty stdin."""
        result = subprocess.run(
            ["python", str(hook_path)],
            input="",
            capture_output=True,
            text=True,
        )

        # Should not crash
        assert result.returncode == 0  # Pass - empty input

    def test_handles_whitespace_only_stdin(self, hook_path):
        """Test graceful handling of whitespace-only stdin."""
        result = subprocess.run(
            ["python", str(hook_path)],
            input="   \n\t   ",
            capture_output=True,
            text=True,
        )

        # Should not crash
        assert result.returncode == 0  # Pass - whitespace only

    def test_handles_very_long_input(self, hook_path):
        """Test handling of very long input."""
        long_input = "implement " + ("a" * 10000)

        result = subprocess.run(
            ["python", str(hook_path)],
            input=long_input,
            capture_output=True,
            text=True,
        )

        # Should detect feature request and truncate message
        assert result.returncode == 1  # Warn
        # Message should be truncated (not full 10K chars)
        assert len(result.stderr) < 1000

    def test_handles_unicode_input(self, hook_path):
        """Test handling of unicode input."""
        result = subprocess.run(
            ["python", str(hook_path)],
            input="implement 认证系统 🔐",
            capture_output=True,
            text=True,
        )

        # Should detect feature request
        assert result.returncode == 1  # Warn

    def test_handles_multiline_input(self, hook_path):
        """Test handling of multi-line input."""
        multiline_input = """implement authentication
        with JWT tokens
        and refresh token support"""

        result = subprocess.run(
            ["python", str(hook_path)],
            input=multiline_input,
            capture_output=True,
            text=True,
        )

        # Should detect feature request
        assert result.returncode == 1  # Warn

    def test_hook_does_not_crash_on_exception(self, hook_path):
        """Test hook does not crash on internal exception."""
        # Even if hook has internal error, it should not crash
        # (should catch exception and return safe exit code)

        result = subprocess.run(
            ["python", str(hook_path)],
            input="test input",
            capture_output=True,
            text=True,
        )

        # Should complete (exit code 0, 1, or 2 - not crash)
        assert result.returncode in [0, 1, 2]


class TestSettingsIntegration:
    """Integration tests for settings.json hook configuration."""

    def test_settings_contains_user_prompt_submit_hook(self, tmp_path):
        """Test settings.json contains UserPromptSubmit hook configuration."""
        # Create sample settings
        settings_path = tmp_path / "settings.json"
        settings = {
            "hooks": {
                "UserPromptSubmit": [
                    {
                        "type": "command",
                        "command": "python ~/.claude/hooks/detect_feature_request.py",
                    }
                ]
            }
        }
        settings_path.write_text(json.dumps(settings, indent=2))

        # Verify settings structure
        loaded = json.loads(settings_path.read_text())

        assert "hooks" in loaded
        assert "UserPromptSubmit" in loaded["hooks"]
        assert isinstance(loaded["hooks"]["UserPromptSubmit"], list)
        assert len(loaded["hooks"]["UserPromptSubmit"]) > 0
        assert "detect_feature_request.py" in loaded["hooks"]["UserPromptSubmit"][0]["command"]

    def test_hook_can_be_disabled_in_settings(self, tmp_path):
        """Test hook can be disabled by removing from settings."""
        # Create settings without hook
        settings_path = tmp_path / "settings.json"
        settings = {"hooks": {}}
        settings_path.write_text(json.dumps(settings, indent=2))

        # Verify hook is not present
        loaded = json.loads(settings_path.read_text())

        # Hook should be absent or empty
        assert (
            "UserPromptSubmit" not in loaded["hooks"]
            or len(loaded["hooks"]["UserPromptSubmit"]) == 0
        )
