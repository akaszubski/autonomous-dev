#!/usr/bin/env python3
"""
Unit tests for first_run_warning module (TDD Red Phase).

Tests for interactive first-run warning system for Issue #61.

TDD Mode: These tests are written BEFORE implementation.
All tests should FAIL initially (ImportError: module not found).

Test Strategy:
- Test warning rendering
- Test user input parsing (Y/n/yes/no/empty)
- Test state recording after user choice
- Test opt-out flow
- Test graceful handling of non-interactive environments
- Test error handling

Date: 2025-11-11
Issue: #61 (Enable Zero Manual Git Operations by Default)
Agent: test-master
Phase: TDD Red (tests written BEFORE implementation)
"""

import os
import sys
import pytest
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock, call
from io import StringIO

# Add lib directory to path for imports
sys.path.insert(
    0,
    str(
        Path(__file__).parent.parent.parent.parent
        / "plugins"
        / "autonomous-dev"
        / "lib"
    ),
)

# Import will fail - module doesn't exist yet (TDD!)
try:
    from first_run_warning import (
        render_warning,
        parse_user_input,
        show_first_run_warning,
        record_user_choice,
        should_show_warning,
        is_interactive_session,
        FirstRunWarningError,
    )
except ImportError as e:
    pytest.skip(f"Implementation not found (TDD red phase): {e}", allow_module_level=True)


class TestWarningRendering:
    """Test warning message rendering."""

    def test_render_warning_contains_key_information(self):
        """Test render_warning() includes all key information."""
        warning = render_warning()

        # Should contain key information
        assert "Zero Manual Git Operations" in warning
        assert "automatic git operations" in warning.lower()
        assert "commit" in warning.lower()
        assert "push" in warning.lower()
        assert "PR" in warning or "pull request" in warning.lower()

    def test_render_warning_includes_opt_out_instructions(self):
        """Test render_warning() includes opt-out instructions."""
        warning = render_warning()

        # Should explain how to opt out
        assert "opt out" in warning.lower() or "disable" in warning.lower()
        assert ".env" in warning

    def test_render_warning_includes_user_prompt(self):
        """Test render_warning() includes user prompt."""
        warning = render_warning()

        # Should ask for user confirmation
        assert "?" in warning  # Question mark for prompt
        assert "Y" in warning or "yes" in warning.lower()
        assert "n" in warning or "no" in warning.lower()

    def test_render_warning_is_readable(self):
        """Test render_warning() produces readable output."""
        warning = render_warning()

        # Should be reasonable length (not too short, not too long)
        assert 100 < len(warning) < 2000
        # Should have multiple lines
        assert "\n" in warning


class TestUserInputParsing:
    """Test parsing user input for consent."""

    def test_parse_user_input_empty_defaults_to_yes(self):
        """Test parse_user_input('') defaults to True (yes)."""
        assert parse_user_input("") is True

    def test_parse_user_input_whitespace_defaults_to_yes(self):
        """Test parse_user_input with whitespace defaults to True."""
        assert parse_user_input("  ") is True
        assert parse_user_input("\n") is True
        assert parse_user_input("\t") is True

    def test_parse_user_input_yes_lowercase(self):
        """Test parse_user_input('yes') returns True."""
        assert parse_user_input("yes") is True

    def test_parse_user_input_yes_uppercase(self):
        """Test parse_user_input('YES') returns True."""
        assert parse_user_input("YES") is True

    def test_parse_user_input_yes_mixed_case(self):
        """Test parse_user_input('Yes') returns True."""
        assert parse_user_input("Yes") is True

    def test_parse_user_input_y_lowercase(self):
        """Test parse_user_input('y') returns True."""
        assert parse_user_input("y") is True

    def test_parse_user_input_y_uppercase(self):
        """Test parse_user_input('Y') returns True."""
        assert parse_user_input("Y") is True

    def test_parse_user_input_no_lowercase(self):
        """Test parse_user_input('no') returns False."""
        assert parse_user_input("no") is False

    def test_parse_user_input_no_uppercase(self):
        """Test parse_user_input('NO') returns False."""
        assert parse_user_input("NO") is False

    def test_parse_user_input_n_lowercase(self):
        """Test parse_user_input('n') returns False."""
        assert parse_user_input("n") is False

    def test_parse_user_input_n_uppercase(self):
        """Test parse_user_input('N') returns False."""
        assert parse_user_input("N") is False

    def test_parse_user_input_strips_whitespace(self):
        """Test parse_user_input strips leading/trailing whitespace."""
        assert parse_user_input("  yes  ") is True
        assert parse_user_input("  no  ") is False

    def test_parse_user_input_invalid_raises_error(self):
        """Test parse_user_input with invalid input raises error."""
        with pytest.raises(FirstRunWarningError, match="Invalid input"):
            parse_user_input("maybe")

        with pytest.raises(FirstRunWarningError, match="Invalid input"):
            parse_user_input("1")

        with pytest.raises(FirstRunWarningError, match="Invalid input"):
            parse_user_input("true")


class TestFirstRunWarningDisplay:
    """Test showing first-run warning to user."""

    @pytest.fixture
    def temp_state_file(self, tmp_path):
        """Create temporary state file."""
        return tmp_path / "user_state.json"

    def test_show_first_run_warning_displays_message(self, temp_state_file):
        """Test show_first_run_warning() displays warning message."""
        with patch("first_run_warning.is_interactive_session", return_value=True):
            with patch("builtins.input", return_value="yes"):
                with patch("sys.stdout", new_callable=StringIO) as mock_stdout:
                    result = show_first_run_warning(temp_state_file)

                    output = mock_stdout.getvalue()
                    assert len(output) > 0  # Should display something

    def test_show_first_run_warning_accepts_yes(self, temp_state_file):
        """Test show_first_run_warning() accepts 'yes' input."""
        with patch("builtins.input", return_value="yes"):
            result = show_first_run_warning(temp_state_file)

            assert result is True

    def test_show_first_run_warning_accepts_no(self, temp_state_file):
        """Test show_first_run_warning() accepts 'no' input."""
        with patch("first_run_warning.is_interactive_session", return_value=True):
            with patch("builtins.input", return_value="no"):
                result = show_first_run_warning(temp_state_file)

            assert result is False

    def test_show_first_run_warning_accepts_empty_as_yes(self, temp_state_file):
        """Test show_first_run_warning() accepts empty input as yes."""
        with patch("builtins.input", return_value=""):
            result = show_first_run_warning(temp_state_file)

            assert result is True

    def test_show_first_run_warning_retries_on_invalid_input(self, temp_state_file):
        """Test show_first_run_warning() retries on invalid input."""
        # First input invalid, second valid
        with patch("builtins.input", side_effect=["maybe", "yes"]):
            result = show_first_run_warning(temp_state_file)

            assert result is True

    def test_show_first_run_warning_max_retries(self, temp_state_file):
        """Test show_first_run_warning() gives up after max retries."""
        # All inputs invalid
        with patch("first_run_warning.is_interactive_session", return_value=True):
            with patch("builtins.input", return_value="invalid"):
                with pytest.raises(FirstRunWarningError, match="Maximum retries exceeded"):
                    show_first_run_warning(temp_state_file, max_retries=3)

    def test_show_first_run_warning_records_user_choice(self, temp_state_file):
        """Test show_first_run_warning() records user choice in state."""
        with patch("builtins.input", return_value="no"):
            result = show_first_run_warning(temp_state_file)

            # Verify state was recorded
            from user_state_manager import load_user_state
            state = load_user_state(temp_state_file)
            assert state["first_run_complete"] is True

    def test_show_first_run_warning_skips_if_non_interactive(self, temp_state_file):
        """Test show_first_run_warning() skips in non-interactive environment."""
        with patch("first_run_warning.is_interactive_session", return_value=False):
            result = show_first_run_warning(temp_state_file)

            # Should default to True without prompting
            assert result is True


class TestUserChoiceRecording:
    """Test recording user choice in state."""

    @pytest.fixture
    def temp_state_file(self, tmp_path):
        """Create temporary state file."""
        return tmp_path / "user_state.json"

    def test_record_user_choice_saves_to_state(self, temp_state_file):
        """Test record_user_choice() saves choice to state file."""
        record_user_choice(accepted=False, state_file=temp_state_file)

        from user_state_manager import load_user_state
        state = load_user_state(temp_state_file)
        assert state["preferences"]["auto_git_enabled"] is False

    def test_record_user_choice_marks_first_run_complete(self, temp_state_file):
        """Test record_user_choice() marks first run as complete."""
        record_user_choice(accepted=True, state_file=temp_state_file)

        from user_state_manager import load_user_state
        state = load_user_state(temp_state_file)
        assert state["first_run_complete"] is True

    def test_record_user_choice_accepted_saves_true(self, temp_state_file):
        """Test record_user_choice with accepted=True saves preference."""
        record_user_choice(accepted=True, state_file=temp_state_file)

        from user_state_manager import get_user_preference
        pref = get_user_preference("auto_git_enabled", temp_state_file)
        assert pref is True

    def test_record_user_choice_rejected_saves_false(self, temp_state_file):
        """Test record_user_choice with accepted=False saves preference."""
        record_user_choice(accepted=False, state_file=temp_state_file)

        from user_state_manager import get_user_preference
        pref = get_user_preference("auto_git_enabled", temp_state_file)
        assert pref is False


class TestShouldShowWarning:
    """Test logic for determining whether to show warning."""

    @pytest.fixture
    def temp_state_file(self, tmp_path):
        """Create temporary state file."""
        return tmp_path / "user_state.json"

    def test_should_show_warning_true_for_first_run(self, temp_state_file):
        """Test should_show_warning() returns True for first run."""
        with patch("first_run_warning.is_interactive_session", return_value=True):
            assert should_show_warning(temp_state_file) is True

    def test_should_show_warning_false_after_first_run(self, temp_state_file):
        """Test should_show_warning() returns False after first run."""
        from user_state_manager import record_first_run_complete
        record_first_run_complete(temp_state_file)

        assert should_show_warning(temp_state_file) is False

    def test_should_show_warning_false_if_env_var_set(self, temp_state_file):
        """Test should_show_warning() returns False if AUTO_GIT_ENABLED env var is set."""
        with patch.dict(os.environ, {"AUTO_GIT_ENABLED": "true"}):
            assert should_show_warning(temp_state_file) is False

    def test_should_show_warning_false_in_non_interactive(self, temp_state_file):
        """Test should_show_warning() returns False in non-interactive session."""
        with patch("first_run_warning.is_interactive_session", return_value=False):
            # Should skip warning in non-interactive mode
            assert should_show_warning(temp_state_file) is False


class TestInteractiveSessionDetection:
    """Test detection of interactive vs non-interactive sessions."""

    def test_is_interactive_session_true_for_tty(self):
        """Test is_interactive_session() returns True when stdin is a TTY."""
        with patch("sys.stdin.isatty", return_value=True):
            assert is_interactive_session() is True

    def test_is_interactive_session_false_for_non_tty(self):
        """Test is_interactive_session() returns False when stdin is not a TTY."""
        with patch("sys.stdin.isatty", return_value=False):
            assert is_interactive_session() is False

    def test_is_interactive_session_false_in_ci(self):
        """Test is_interactive_session() returns False in CI environment."""
        with patch.dict(os.environ, {"CI": "true"}):
            assert is_interactive_session() is False

    def test_is_interactive_session_false_if_no_display(self):
        """Test is_interactive_session() returns False if DISPLAY not set."""
        with patch.dict(os.environ, {}, clear=True):  # Clear DISPLAY
            with patch("sys.stdin.isatty", return_value=False):
                assert is_interactive_session() is False


class TestErrorHandling:
    """Test error handling and edge cases."""

    @pytest.fixture
    def temp_state_file(self, tmp_path):
        """Create temporary state file."""
        return tmp_path / "user_state.json"

    def test_show_first_run_warning_handles_keyboard_interrupt(self, temp_state_file):
        """Test show_first_run_warning() handles KeyboardInterrupt gracefully."""
        with patch("first_run_warning.is_interactive_session", return_value=True):
            with patch("builtins.input", side_effect=KeyboardInterrupt):
                with pytest.raises(FirstRunWarningError, match="Interrupted by user"):
                    show_first_run_warning(temp_state_file)

    def test_show_first_run_warning_handles_eof_error(self, temp_state_file):
        """Test show_first_run_warning() handles EOFError gracefully."""
        with patch("builtins.input", side_effect=EOFError):
            # Should default to True (yes) on EOF
            result = show_first_run_warning(temp_state_file)
            assert result is True

    def test_record_user_choice_handles_save_error(self, temp_state_file):
        """Test record_user_choice() handles save errors gracefully."""
        with patch("first_run_warning.UserStateManager.save", side_effect=Exception("Disk full")):
            with pytest.raises(FirstRunWarningError, match="Failed to record user choice"):
                record_user_choice(accepted=True, state_file=temp_state_file)
