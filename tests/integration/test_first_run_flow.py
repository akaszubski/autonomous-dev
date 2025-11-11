#!/usr/bin/env python3
"""
Integration tests for first-run flow (TDD Red Phase).

Tests end-to-end first-run warning flow for Issue #61.

TDD Mode: These tests are written BEFORE implementation.
All tests should FAIL initially (ImportError: modules not found).

Test Strategy:
- Test complete first-run flow from start to finish
- Test warning display → user input → state persistence → env var integration
- Test subsequent runs skip warning
- Test accept/reject paths produce correct outcomes
- Test state file persistence across sessions
- Test env var priority over state file

Date: 2025-11-11
Issue: #61 (Enable Zero Manual Git Operations by Default)
Agent: test-master
Phase: TDD Red (tests written BEFORE implementation)
"""

import json
import os
import sys
import pytest
import tempfile
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock, call
from io import StringIO

# Add lib directory to path for imports
sys.path.insert(
    0,
    str(
        Path(__file__).parent.parent.parent
        / "plugins"
        / "autonomous-dev"
        / "lib"
    ),
)

# Import will fail - modules don't exist yet (TDD!)
try:
    from first_run_warning import show_first_run_warning, should_show_warning
    from user_state_manager import (
        UserStateManager,
        is_first_run,
        get_user_preference,
        DEFAULT_STATE_FILE,
    )
    from auto_implement_git_integration import check_consent_via_env
except ImportError as e:
    pytest.skip(f"Implementation not found (TDD red phase): {e}", allow_module_level=True)


class TestFirstRunFlowAccept:
    """Test complete first-run flow when user accepts."""

    @pytest.fixture
    def temp_state_file(self, tmp_path):
        """Create temporary state file."""
        return tmp_path / "user_state.json"

    def test_first_run_shows_warning(self, temp_state_file):
        """Test first run shows warning to user."""
        # Simulate first run
        assert is_first_run(temp_state_file) is True

        with patch("first_run_warning.is_interactive_session", return_value=True):
            with patch("builtins.input", return_value="yes"):
                with patch("sys.stdout", new_callable=StringIO) as mock_stdout:
                    result = show_first_run_warning(temp_state_file)

                    # Should have displayed warning
                    output = mock_stdout.getvalue()
                    assert len(output) > 0

    def test_first_run_accept_records_preference(self, temp_state_file):
        """Test accepting first-run warning records preference."""
        with patch("builtins.input", return_value="yes"):
            result = show_first_run_warning(temp_state_file)

            # Should have accepted
            assert result is True

            # Should have recorded preference
            pref = get_user_preference("auto_git_enabled", temp_state_file)
            assert pref is True

    def test_first_run_accept_marks_complete(self, temp_state_file):
        """Test accepting first-run warning marks first run complete."""
        with patch("builtins.input", return_value="yes"):
            show_first_run_warning(temp_state_file)

            # Should have marked first run complete
            assert is_first_run(temp_state_file) is False

    def test_subsequent_run_skips_warning(self, temp_state_file):
        """Test subsequent runs skip warning after first run."""
        # Complete first run
        with patch("builtins.input", return_value="yes"):
            show_first_run_warning(temp_state_file)

        # Second run should not show warning
        assert should_show_warning(temp_state_file) is False

    def test_first_run_accept_enables_git_operations(self, temp_state_file):
        """Test accepting enables git operations by default."""
        with patch("builtins.input", return_value="yes"):
            show_first_run_warning(temp_state_file)

        # Git operations should be enabled
        pref = get_user_preference("auto_git_enabled", temp_state_file)
        assert pref is True


class TestFirstRunFlowReject:
    """Test complete first-run flow when user rejects."""

    @pytest.fixture
    def temp_state_file(self, tmp_path):
        """Create temporary state file."""
        return tmp_path / "user_state.json"

    def test_first_run_reject_records_preference(self, temp_state_file):
        """Test rejecting first-run warning records preference."""
        with patch("first_run_warning.is_interactive_session", return_value=True):
            with patch("builtins.input", return_value="no"):
                result = show_first_run_warning(temp_state_file)

                # Should have rejected
                assert result is False

                # Should have recorded preference
                pref = get_user_preference("auto_git_enabled", temp_state_file)
                assert pref is False

    def test_first_run_reject_marks_complete(self, temp_state_file):
        """Test rejecting first-run warning marks first run complete."""
        with patch("builtins.input", return_value="no"):
            show_first_run_warning(temp_state_file)

            # Should have marked first run complete
            assert is_first_run(temp_state_file) is False

    def test_first_run_reject_disables_git_operations(self, temp_state_file):
        """Test rejecting disables git operations."""
        with patch("first_run_warning.is_interactive_session", return_value=True):
            with patch("builtins.input", return_value="no"):
                show_first_run_warning(temp_state_file)

        # Git operations should be disabled
        pref = get_user_preference("auto_git_enabled", temp_state_file)
        assert pref is False


class TestStateFilePersistence:
    """Test state file persists across sessions."""

    @pytest.fixture
    def temp_state_file(self, tmp_path):
        """Create temporary state file."""
        return tmp_path / "user_state.json"

    def test_state_persists_across_manager_instances(self, temp_state_file):
        """Test state persists when loading new manager instance."""
        # First manager: Accept and save
        with patch("builtins.input", return_value="yes"):
            show_first_run_warning(temp_state_file)

        # Second manager: Load state
        manager = UserStateManager(temp_state_file)
        assert manager.is_first_run() is False
        assert manager.get_preference("auto_git_enabled") is True

    def test_state_file_format_is_valid_json(self, temp_state_file):
        """Test state file is valid JSON."""
        with patch("builtins.input", return_value="yes"):
            show_first_run_warning(temp_state_file)

        # Verify file is valid JSON
        with open(temp_state_file) as f:
            state = json.load(f)

        assert "first_run_complete" in state
        assert "preferences" in state
        assert "version" in state

    def test_state_file_survives_process_restart(self, temp_state_file):
        """Test state file survives simulated process restart."""
        # Simulate first process
        with patch("first_run_warning.is_interactive_session", return_value=True):
            with patch("builtins.input", return_value="no"):
                show_first_run_warning(temp_state_file)

        # Simulate new process (reload state)
        # Clear any cached state
        manager = UserStateManager(temp_state_file)

        # Should load persisted state
        assert manager.is_first_run() is False
        assert manager.get_preference("auto_git_enabled") is False


class TestEnvVarPriority:
    """Test environment variable takes priority over state file."""

    @pytest.fixture
    def temp_state_file(self, tmp_path):
        """Create temporary state file."""
        return tmp_path / "user_state.json"

    def test_env_var_overrides_state_file_preference(self, temp_state_file):
        """Test explicit env var overrides state file preference."""
        # User rejected in state file
        with patch("builtins.input", return_value="no"):
            show_first_run_warning(temp_state_file)

        # But env var explicitly enables
        with patch.dict(os.environ, {"AUTO_GIT_ENABLED": "true"}):
            consent = check_consent_via_env()

            # Env var should win
            assert consent["enabled"] is True

    def test_env_var_false_overrides_state_file_accept(self, temp_state_file):
        """Test env var false overrides state file accept."""
        # User accepted in state file
        with patch("builtins.input", return_value="yes"):
            show_first_run_warning(temp_state_file)

        # But env var explicitly disables
        with patch.dict(os.environ, {"AUTO_GIT_ENABLED": "false"}):
            consent = check_consent_via_env()

            # Env var should win
            assert consent["enabled"] is False

    def test_env_var_set_skips_warning(self, temp_state_file):
        """Test env var set skips first-run warning."""
        # If env var is already set, don't show warning
        with patch.dict(os.environ, {"AUTO_GIT_ENABLED": "true"}):
            assert should_show_warning(temp_state_file) is False

    def test_no_env_var_uses_state_file_preference(self, temp_state_file):
        """Test no env var uses state file preference."""
        # User rejected in state file
        with patch("first_run_warning.is_interactive_session", return_value=True):
            with patch("builtins.input", return_value="no"):
                show_first_run_warning(temp_state_file)

        # No env var set
        with patch.dict(os.environ, {}, clear=True):
            # Should use state file preference
            pref = get_user_preference("auto_git_enabled", temp_state_file)
            assert pref is False


class TestFirstRunFlowEdgeCases:
    """Test edge cases in first-run flow."""

    @pytest.fixture
    def temp_state_file(self, tmp_path):
        """Create temporary state file."""
        return tmp_path / "user_state.json"

    def test_empty_input_defaults_to_accept(self, temp_state_file):
        """Test empty input (pressing Enter) defaults to accept."""
        with patch("builtins.input", return_value=""):
            result = show_first_run_warning(temp_state_file)

            assert result is True
            pref = get_user_preference("auto_git_enabled", temp_state_file)
            assert pref is True

    def test_whitespace_input_defaults_to_accept(self, temp_state_file):
        """Test whitespace input defaults to accept."""
        with patch("builtins.input", return_value="  "):
            result = show_first_run_warning(temp_state_file)

            assert result is True

    def test_invalid_input_retries(self, temp_state_file):
        """Test invalid input prompts retry."""
        # First input invalid, second valid
        with patch("builtins.input", side_effect=["invalid", "yes"]):
            result = show_first_run_warning(temp_state_file)

            assert result is True

    def test_case_insensitive_input(self, temp_state_file):
        """Test input is case-insensitive."""
        with patch("builtins.input", return_value="YES"):
            result = show_first_run_warning(temp_state_file)

            assert result is True

    def test_non_interactive_session_skips_warning(self, temp_state_file):
        """Test non-interactive session skips warning and defaults to accept."""
        with patch("sys.stdin.isatty", return_value=False):
            # Should skip warning and default to True
            if should_show_warning(temp_state_file):
                result = show_first_run_warning(temp_state_file)
            else:
                result = True  # Default

            assert result is True


class TestFirstRunFlowIntegrationWithAutoImplement:
    """Test first-run flow integration with /auto-implement workflow."""

    @pytest.fixture
    def temp_state_file(self, tmp_path):
        """Create temporary state file."""
        return tmp_path / "user_state.json"

    def test_auto_implement_checks_first_run(self, temp_state_file):
        """Test /auto-implement checks if first run."""
        # Simulate /auto-implement checking first run
        is_first = is_first_run(temp_state_file)
        assert is_first is True

    def test_auto_implement_shows_warning_on_first_run(self, temp_state_file):
        """Test /auto-implement shows warning on first run."""
        if should_show_warning(temp_state_file):
            with patch("builtins.input", return_value="yes"):
                result = show_first_run_warning(temp_state_file)
                assert result is True

    def test_auto_implement_respects_user_choice(self, temp_state_file):
        """Test /auto-implement respects user choice from first run."""
        # User rejects
        with patch("first_run_warning.is_interactive_session", return_value=True):
            with patch("builtins.input", return_value="no"):
                show_first_run_warning(temp_state_file)

        # /auto-implement should respect this
        with patch.dict(os.environ, {}, clear=True):
            pref = get_user_preference("auto_git_enabled", temp_state_file)
            assert pref is False

    def test_auto_implement_skips_warning_after_first_run(self, temp_state_file):
        """Test /auto-implement skips warning after first run complete."""
        # Complete first run
        with patch("builtins.input", return_value="yes"):
            show_first_run_warning(temp_state_file)

        # Second /auto-implement should skip warning
        assert should_show_warning(temp_state_file) is False


class TestDefaultBehaviorWithoutStateFile:
    """Test default behavior when state file doesn't exist yet."""

    @pytest.fixture
    def nonexistent_state_file(self, tmp_path):
        """Return path to nonexistent state file."""
        return tmp_path / "nonexistent" / "user_state.json"

    def test_missing_state_file_triggers_first_run(self, nonexistent_state_file):
        """Test missing state file triggers first-run flow."""
        assert is_first_run(nonexistent_state_file) is True

    def test_missing_state_file_shows_warning(self, nonexistent_state_file):
        """Test missing state file shows warning."""
        with patch("first_run_warning.is_interactive_session", return_value=True):
            assert should_show_warning(nonexistent_state_file) is True

    def test_missing_state_file_creates_on_save(self, nonexistent_state_file):
        """Test missing state file is created on save."""
        with patch("builtins.input", return_value="yes"):
            show_first_run_warning(nonexistent_state_file)

        # State file should now exist
        assert nonexistent_state_file.exists()

    def test_default_consent_without_state_or_env(self, nonexistent_state_file):
        """Test default consent when no state file or env var exists."""
        # Clear env vars
        with patch.dict(os.environ, {}, clear=True):
            # No state file exists
            # check_consent_via_env should default to True
            consent = check_consent_via_env()

            assert consent["enabled"] is True
            assert consent["push"] is True
            assert consent["pr"] is True
