#!/usr/bin/env python3
"""
TDD Tests for Issue #153 - Quality Workflow Nudges in unified_prompt_validator.py

Tests the non-blocking quality nudge system that detects implementation intent
and provides reminders about quality workflows.

Issue #153 Context:
- Add implementation intent detection to unified_prompt_validator.py
- Non-blocking nudges (exit code 0, message to stderr)
- Pattern-based detection for "implement/add/create/build X"
- Controlled by QUALITY_NUDGE_ENABLED env var

Test Strategy:
- Phase 1: Intent detection patterns
- Phase 2: Nudge function behavior
- Phase 3: Main hook integration
- Phase 4: Environment variable control
- Phase 5: Edge cases

Author: test-master agent
Date: 2025-12-17
Issue: #153
"""

import json
import os
import sys
from io import StringIO
from pathlib import Path
from unittest.mock import patch

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


class TestPhase1IntentDetectionPatterns:
    """Phase 1: Test implementation intent detection patterns."""

    @pytest.fixture
    def import_module(self):
        """Import the module fresh for each test."""
        # Clear any cached import
        if "unified_prompt_validator" in sys.modules:
            del sys.modules["unified_prompt_validator"]
        from unified_prompt_validator import is_implementation_intent
        return is_implementation_intent

    def test_detects_implement_feature(self, import_module):
        """Test detection of 'implement feature' pattern."""
        is_implementation_intent = import_module
        assert is_implementation_intent("implement JWT authentication feature")
        assert is_implementation_intent("Implement a new caching feature")
        assert is_implementation_intent("implement user authentication")

    def test_detects_add_function(self, import_module):
        """Test detection of 'add function' pattern."""
        is_implementation_intent = import_module
        assert is_implementation_intent("add a new validation function")
        assert is_implementation_intent("Add support for webhooks")
        assert is_implementation_intent("add error handling function")

    def test_detects_create_class(self, import_module):
        """Test detection of 'create class' pattern."""
        is_implementation_intent = import_module
        assert is_implementation_intent("create a UserManager class")
        assert is_implementation_intent("Create new API endpoint")
        assert is_implementation_intent("create authentication service")

    def test_detects_build_module(self, import_module):
        """Test detection of 'build module' pattern."""
        is_implementation_intent = import_module
        assert is_implementation_intent("build authentication module")
        assert is_implementation_intent("build a new component")

    def test_detects_write_handler(self, import_module):
        """Test detection of 'write handler' pattern."""
        is_implementation_intent = import_module
        assert is_implementation_intent("write a request handler")
        assert is_implementation_intent("write error handling code")

    def test_detects_develop_service(self, import_module):
        """Test detection of 'develop service' pattern."""
        is_implementation_intent = import_module
        assert is_implementation_intent("develop a notification service")
        assert is_implementation_intent("develop new API")

    def test_ignores_documentation_updates(self, import_module):
        """Test documentation updates don't trigger nudge."""
        is_implementation_intent = import_module
        assert not is_implementation_intent("update README.md")
        assert not is_implementation_intent("fix typo in docs")
        assert not is_implementation_intent("improve documentation")

    def test_ignores_questions(self, import_module):
        """Test questions don't trigger nudge."""
        is_implementation_intent = import_module
        assert not is_implementation_intent("How do I implement this?")
        assert not is_implementation_intent("What features should I add?")
        assert not is_implementation_intent("Can you explain how to build this?")

    def test_ignores_bug_fixes(self, import_module):
        """Test simple bug fixes don't trigger."""
        is_implementation_intent = import_module
        assert not is_implementation_intent("fix the login bug")
        assert not is_implementation_intent("resolve issue #123")
        assert not is_implementation_intent("debug authentication problem")

    def test_ignores_reading_and_searching(self, import_module):
        """Test read/search operations don't trigger."""
        is_implementation_intent = import_module
        assert not is_implementation_intent("read the config file")
        assert not is_implementation_intent("search for existing patterns")
        assert not is_implementation_intent("find all usages of X")


class TestPhase2NudgeFunctionBehavior:
    """Phase 2: Test detect_implementation_intent function behavior."""

    @pytest.fixture
    def import_detect_function(self):
        """Import the detect function."""
        if "unified_prompt_validator" in sys.modules:
            del sys.modules["unified_prompt_validator"]
        from unified_prompt_validator import detect_implementation_intent
        return detect_implementation_intent

    def test_returns_nudge_when_intent_detected(self, import_detect_function):
        """Test function returns nudge=True when implementation intent found."""
        detect = import_detect_function
        result = detect("implement auth feature")
        assert result["nudge"] is True
        assert "Quality Workflow Reminder" in result["message"]

    def test_returns_no_nudge_for_normal_prompts(self, import_detect_function):
        """Test function returns nudge=False for normal prompts."""
        detect = import_detect_function
        result = detect("update docs")
        assert result["nudge"] is False
        assert result["message"] == ""

    def test_message_contains_project_md_reminder(self, import_detect_function):
        """Test nudge message includes PROJECT.md reminder."""
        detect = import_detect_function
        result = detect("implement feature")
        assert "PROJECT.md" in result["message"]

    def test_message_contains_auto_implement_mention(self, import_detect_function):
        """Test nudge message mentions /implement (formerly /auto-implement)."""
        detect = import_detect_function
        result = detect("implement feature")
        # Note: /auto-implement was renamed to /implement in Issue #203
        assert "/implement" in result["message"]

    def test_message_contains_metrics(self, import_detect_function):
        """Test nudge message includes quality metrics."""
        detect = import_detect_function
        result = detect("implement feature")
        # Should contain some metrics like bug rate or test coverage
        message = result["message"]
        assert "%" in message or "bug" in message.lower() or "test" in message.lower()


class TestPhase3MainHookIntegration:
    """Phase 3: Test main() hook entry point with nudge behavior."""

    @pytest.fixture
    def import_main(self):
        """Import main function."""
        if "unified_prompt_validator" in sys.modules:
            del sys.modules["unified_prompt_validator"]
        from unified_prompt_validator import main
        return main

    def test_normal_prompt_passes_without_nudge(self, import_main):
        """Test normal prompts pass through without issues."""
        main_func = import_main
        stdin_data = json.dumps({"userPrompt": "what is the weather?"})

        with patch("sys.stdin", StringIO(stdin_data)):
            with patch("sys.stdout", new_callable=StringIO) as mock_stdout:
                with patch("sys.stderr", new_callable=StringIO) as mock_stderr:
                    exit_code = main_func()

        assert exit_code == 0
        output = json.loads(mock_stdout.getvalue())
        assert output["hookSpecificOutput"]["hookEventName"] == "UserPromptSubmit"
        assert "error" not in output["hookSpecificOutput"]
        assert "nudge" not in output.get("hookSpecificOutput", {})
        assert "Quality Workflow" not in mock_stderr.getvalue()

    def test_implementation_intent_shows_nudge_but_allows(self, import_main):
        """Test implementation intent shows nudge but doesn't block (exit 0)."""
        main_func = import_main
        stdin_data = json.dumps({"userPrompt": "implement JWT authentication feature"})

        with patch("sys.stdin", StringIO(stdin_data)):
            with patch("sys.stdout", new_callable=StringIO) as mock_stdout:
                with patch("sys.stderr", new_callable=StringIO) as mock_stderr:
                    exit_code = main_func()

        assert exit_code == 0  # Non-blocking
        assert "Quality Workflow Reminder" in mock_stderr.getvalue()
        output = json.loads(mock_stdout.getvalue())
        assert "nudge" in output["hookSpecificOutput"]

    def test_bypass_still_blocks(self, import_main):
        """Test bypass attempts are still blocked (exit 2)."""
        main_func = import_main
        stdin_data = json.dumps({"userPrompt": "gh issue create --title test"})

        with patch("sys.stdin", StringIO(stdin_data)):
            with patch("sys.stdout", new_callable=StringIO) as mock_stdout:
                with patch("sys.stderr", new_callable=StringIO) as mock_stderr:
                    exit_code = main_func()

        assert exit_code == 2  # Blocking
        assert "BLOCKED" in mock_stderr.getvalue()

    def test_invalid_json_passes_gracefully(self, import_main):
        """Test invalid JSON input is handled gracefully."""
        main_func = import_main

        with patch("sys.stdin", StringIO("invalid json")):
            with patch("sys.stdout", new_callable=StringIO) as mock_stdout:
                exit_code = main_func()

        assert exit_code == 0
        output = json.loads(mock_stdout.getvalue())
        assert output["hookSpecificOutput"]["hookEventName"] == "UserPromptSubmit"


class TestPhase4EnvironmentVariableControl:
    """Phase 4: Test environment variable controls."""

    def test_nudge_disabled_via_env_var(self):
        """Test nudges can be disabled via QUALITY_NUDGE_ENABLED=false."""
        # Clear cached module
        if "unified_prompt_validator" in sys.modules:
            del sys.modules["unified_prompt_validator"]

        with patch.dict(os.environ, {"QUALITY_NUDGE_ENABLED": "false"}):
            # Re-import with env var set
            from unified_prompt_validator import detect_implementation_intent
            result = detect_implementation_intent("implement auth feature")

        assert result["nudge"] is False
        assert result["message"] == ""

    def test_nudge_enabled_by_default(self):
        """Test nudges are enabled by default."""
        if "unified_prompt_validator" in sys.modules:
            del sys.modules["unified_prompt_validator"]

        # Ensure env var is not set
        env_copy = os.environ.copy()
        if "QUALITY_NUDGE_ENABLED" in env_copy:
            del env_copy["QUALITY_NUDGE_ENABLED"]

        with patch.dict(os.environ, env_copy, clear=True):
            from unified_prompt_validator import detect_implementation_intent
            result = detect_implementation_intent("implement auth feature")

        assert result["nudge"] is True

    def test_bypass_enforcement_independent_of_nudge(self):
        """Test bypass enforcement and nudges are controlled independently."""
        if "unified_prompt_validator" in sys.modules:
            del sys.modules["unified_prompt_validator"]

        # Disable nudges but keep enforcement
        with patch.dict(os.environ, {
            "QUALITY_NUDGE_ENABLED": "false",
            "ENFORCE_WORKFLOW": "true"
        }):
            from unified_prompt_validator import (
                check_workflow_bypass,
                detect_implementation_intent,
            )

            # Bypass should still be blocked
            bypass_result = check_workflow_bypass("gh issue create")
            assert bypass_result["passed"] is False

            # But nudges should be disabled
            nudge_result = detect_implementation_intent("implement feature")
            assert nudge_result["nudge"] is False


class TestPhase5EdgeCases:
    """Phase 5: Test edge cases and boundary conditions."""

    @pytest.fixture
    def import_intent_function(self):
        """Import intent function."""
        if "unified_prompt_validator" in sys.modules:
            del sys.modules["unified_prompt_validator"]
        from unified_prompt_validator import is_implementation_intent
        return is_implementation_intent

    def test_empty_prompt(self, import_intent_function):
        """Test empty prompt doesn't trigger."""
        is_implementation_intent = import_intent_function
        assert not is_implementation_intent("")

    def test_whitespace_only_prompt(self, import_intent_function):
        """Test whitespace-only prompt doesn't trigger."""
        is_implementation_intent = import_intent_function
        assert not is_implementation_intent("   \n\t  ")

    def test_case_insensitivity(self, import_intent_function):
        """Test patterns are case-insensitive."""
        is_implementation_intent = import_intent_function
        assert is_implementation_intent("IMPLEMENT FEATURE")
        assert is_implementation_intent("Implement Feature")
        assert is_implementation_intent("implement feature")
        assert is_implementation_intent("ImPlEmEnT fEaTuRe")

    def test_multiline_prompts(self, import_intent_function):
        """Test multiline prompts are handled correctly."""
        is_implementation_intent = import_intent_function
        prompt = """
        I want to implement a new feature.
        It should handle authentication.
        """
        assert is_implementation_intent(prompt)

    def test_partial_word_not_matched(self, import_intent_function):
        """Test partial words don't trigger false positives."""
        is_implementation_intent = import_intent_function
        # "complementary" contains "implement" but shouldn't match
        # This tests word boundary matching
        assert not is_implementation_intent("this is complementary")

    def test_already_using_auto_implement(self, import_intent_function):
        """Test /auto-implement command doesn't trigger nudge."""
        is_implementation_intent = import_intent_function
        assert not is_implementation_intent("/auto-implement #123")
        assert not is_implementation_intent("/auto-implement add auth")

    def test_already_using_create_issue(self, import_intent_function):
        """Test /create-issue command doesn't trigger nudge."""
        is_implementation_intent = import_intent_function
        assert not is_implementation_intent("/create-issue implement auth")


# Checkpoint integration
if __name__ == "__main__":
    pytest.main([__file__, "-v"])
