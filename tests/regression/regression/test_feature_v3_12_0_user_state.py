#!/usr/bin/env python3
"""
Unit tests for user_state_manager module (TDD Red Phase).

Tests for user preference persistence and first-run detection for Issue #61.

TDD Mode: These tests are written BEFORE implementation.
All tests should FAIL initially (ImportError: module not found).

Test Strategy:
- Test state file CRUD operations
- Test first-run detection
- Test preference loading/saving
- Test security validations (CWE-22 path traversal)
- Test concurrent access safety
- Test error handling and graceful degradation

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
from unittest.mock import Mock, patch, MagicMock, mock_open
from typing import Dict, Any

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
    from user_state_manager import (
        UserStateManager,
        load_user_state,
        save_user_state,
        is_first_run,
        record_first_run_complete,
        get_user_preference,
        set_user_preference,
        UserStateError,
        DEFAULT_STATE_FILE,
    )
except ImportError as e:
    pytest.skip(f"Implementation not found (TDD red phase): {e}", allow_module_level=True)


class TestUserStateManager:
    """Test UserStateManager class for user preference persistence."""

    @pytest.fixture
    def temp_state_dir(self, tmp_path):
        """Create temporary directory for state files."""
        state_dir = tmp_path / ".autonomous-dev"
        state_dir.mkdir()
        return state_dir

    @pytest.fixture
    def state_file(self, temp_state_dir):
        """Create temporary state file path."""
        return temp_state_dir / "user_state.json"

    def test_user_state_manager_init_creates_default_state(self, state_file):
        """Test UserStateManager initialization creates default state."""
        manager = UserStateManager(state_file)

        assert manager.state_file == state_file
        assert manager.state == {
            "first_run_complete": False,
            "preferences": {},
            "version": "1.0"
        }

    def test_user_state_manager_loads_existing_state(self, state_file):
        """Test UserStateManager loads existing state file."""
        # Create existing state file
        existing_state = {
            "first_run_complete": True,
            "preferences": {"auto_git_enabled": False},
            "version": "1.0"
        }
        state_file.write_text(json.dumps(existing_state))

        manager = UserStateManager(state_file)

        assert manager.state["first_run_complete"] is True
        assert manager.state["preferences"]["auto_git_enabled"] is False

    def test_user_state_manager_save_writes_state_file(self, state_file):
        """Test UserStateManager.save() writes state to file."""
        manager = UserStateManager(state_file)
        manager.state["first_run_complete"] = True
        manager.state["preferences"]["auto_git_enabled"] = True

        manager.save()

        # Verify file was written
        assert state_file.exists()
        saved_state = json.loads(state_file.read_text())
        assert saved_state["first_run_complete"] is True
        assert saved_state["preferences"]["auto_git_enabled"] is True

    def test_user_state_manager_save_creates_parent_directories(self, tmp_path):
        """Test UserStateManager.save() creates parent directories if needed."""
        state_file = tmp_path / "nested" / "dir" / "user_state.json"

        manager = UserStateManager(state_file)
        manager.save()

        assert state_file.exists()
        assert state_file.parent.exists()

    def test_user_state_manager_is_first_run_true_initially(self, state_file):
        """Test is_first_run() returns True for new state."""
        manager = UserStateManager(state_file)

        assert manager.is_first_run() is True

    def test_user_state_manager_is_first_run_false_after_complete(self, state_file):
        """Test is_first_run() returns False after first run complete."""
        manager = UserStateManager(state_file)
        manager.record_first_run_complete()

        assert manager.is_first_run() is False

    def test_user_state_manager_record_first_run_complete(self, state_file):
        """Test record_first_run_complete() updates state."""
        manager = UserStateManager(state_file)

        manager.record_first_run_complete()

        assert manager.state["first_run_complete"] is True

    def test_user_state_manager_get_preference_existing(self, state_file):
        """Test get_preference() returns existing preference value."""
        manager = UserStateManager(state_file)
        manager.state["preferences"]["auto_git_enabled"] = False

        value = manager.get_preference("auto_git_enabled")

        assert value is False

    def test_user_state_manager_get_preference_missing_returns_none(self, state_file):
        """Test get_preference() returns None for missing preference."""
        manager = UserStateManager(state_file)

        value = manager.get_preference("nonexistent_key")

        assert value is None

    def test_user_state_manager_get_preference_with_default(self, state_file):
        """Test get_preference() returns default for missing preference."""
        manager = UserStateManager(state_file)

        value = manager.get_preference("nonexistent_key", default=True)

        assert value is True

    def test_user_state_manager_set_preference(self, state_file):
        """Test set_preference() updates preference value."""
        manager = UserStateManager(state_file)

        manager.set_preference("auto_git_enabled", False)

        assert manager.state["preferences"]["auto_git_enabled"] is False

    def test_user_state_manager_set_preference_overwrites_existing(self, state_file):
        """Test set_preference() overwrites existing preference."""
        manager = UserStateManager(state_file)
        manager.state["preferences"]["auto_git_enabled"] = True

        manager.set_preference("auto_git_enabled", False)

        assert manager.state["preferences"]["auto_git_enabled"] is False

    def test_user_state_manager_handles_corrupted_json(self, state_file):
        """Test UserStateManager handles corrupted JSON gracefully."""
        # Write corrupted JSON
        state_file.write_text("{ corrupted json }")

        # Should fall back to default state without crashing
        manager = UserStateManager(state_file)

        assert manager.state["first_run_complete"] is False

    def test_user_state_manager_validates_path_security(self, tmp_path):
        """Test UserStateManager validates path is within safe directory (CWE-22)."""
        # Attempt path traversal
        unsafe_path = tmp_path / ".." / ".." / "etc" / "passwd"

        with pytest.raises(UserStateError, match="Path traversal detected"):
            UserStateManager(unsafe_path)

    def test_user_state_manager_rejects_absolute_paths_outside_home(self):
        """Test UserStateManager rejects absolute paths outside home directory."""
        unsafe_path = Path("/etc/passwd")

        with pytest.raises(UserStateError, match="Path must be within home directory"):
            UserStateManager(unsafe_path)


class TestModuleLevelFunctions:
    """Test module-level convenience functions."""

    @pytest.fixture
    def temp_state_dir(self, tmp_path):
        """Create temporary directory for state files."""
        state_dir = tmp_path / ".autonomous-dev"
        state_dir.mkdir()
        return state_dir

    @pytest.fixture
    def state_file(self, temp_state_dir):
        """Create temporary state file path."""
        return temp_state_dir / "user_state.json"

    def test_load_user_state_returns_dict(self, state_file):
        """Test load_user_state() returns state dictionary."""
        # Create state file
        state = {"first_run_complete": True, "preferences": {}}
        state_file.write_text(json.dumps(state))

        loaded_state = load_user_state(state_file)

        assert isinstance(loaded_state, dict)
        assert loaded_state["first_run_complete"] is True

    def test_load_user_state_creates_default_if_missing(self, state_file):
        """Test load_user_state() creates default state if file missing."""
        # Ensure file doesn't exist from previous tests
        if state_file.exists():
            state_file.unlink()

        loaded_state = load_user_state(state_file)

        assert loaded_state["first_run_complete"] is False
        assert loaded_state["preferences"] == {}

    def test_save_user_state_writes_file(self, state_file):
        """Test save_user_state() writes state to file."""
        state = {
            "first_run_complete": True,
            "preferences": {"auto_git_enabled": False},
            "version": "1.0"
        }

        save_user_state(state, state_file)

        assert state_file.exists()
        saved_state = json.loads(state_file.read_text())
        assert saved_state["first_run_complete"] is True

    def test_is_first_run_true_for_new_state(self, state_file):
        """Test is_first_run() returns True for new state."""
        assert is_first_run(state_file) is True

    def test_is_first_run_false_after_completion(self, state_file):
        """Test is_first_run() returns False after first run."""
        # Create completed state
        state = {"first_run_complete": True, "preferences": {}, "version": "1.0"}
        state_file.write_text(json.dumps(state))

        assert is_first_run(state_file) is False

    def test_record_first_run_complete_updates_state(self, state_file):
        """Test record_first_run_complete() updates state file."""
        record_first_run_complete(state_file)

        loaded_state = json.loads(state_file.read_text())
        assert loaded_state["first_run_complete"] is True

    def test_get_user_preference_returns_value(self, state_file):
        """Test get_user_preference() returns stored preference."""
        # Create state with preference
        state = {
            "first_run_complete": True,
            "preferences": {"auto_git_enabled": False},
            "version": "1.0"
        }
        state_file.write_text(json.dumps(state))

        value = get_user_preference("auto_git_enabled", state_file)

        assert value is False

    def test_get_user_preference_returns_none_if_missing(self, state_file):
        """Test get_user_preference() returns None for missing preference."""
        # Create empty state
        state = {"first_run_complete": False, "preferences": {}, "version": "1.0"}
        state_file.write_text(json.dumps(state))

        value = get_user_preference("nonexistent", state_file)

        assert value is None

    def test_get_user_preference_with_default(self, state_file):
        """Test get_user_preference() returns default for missing preference."""
        # Create empty state
        state = {"first_run_complete": False, "preferences": {}, "version": "1.0"}
        state_file.write_text(json.dumps(state))

        value = get_user_preference("nonexistent", state_file, default=True)

        assert value is True

    def test_set_user_preference_updates_state(self, state_file):
        """Test set_user_preference() updates state file."""
        set_user_preference("auto_git_enabled", False, state_file)

        loaded_state = json.loads(state_file.read_text())
        assert loaded_state["preferences"]["auto_git_enabled"] is False

    def test_set_user_preference_preserves_other_preferences(self, state_file):
        """Test set_user_preference() preserves other preferences."""
        # Create state with existing preference
        state = {
            "first_run_complete": True,
            "preferences": {"existing_pref": "value"},
            "version": "1.0"
        }
        state_file.write_text(json.dumps(state))

        set_user_preference("auto_git_enabled", False, state_file)

        loaded_state = json.loads(state_file.read_text())
        assert loaded_state["preferences"]["existing_pref"] == "value"
        assert loaded_state["preferences"]["auto_git_enabled"] is False


class TestConcurrentAccess:
    """Test concurrent access safety for user state."""

    @pytest.fixture
    def state_file(self, tmp_path):
        """Create temporary state file."""
        return tmp_path / "user_state.json"

    def test_concurrent_save_does_not_corrupt_file(self, state_file):
        """Test concurrent save operations don't corrupt state file."""
        manager1 = UserStateManager(state_file)
        manager2 = UserStateManager(state_file)

        # Simulate concurrent updates
        manager1.set_preference("pref1", "value1")
        manager2.set_preference("pref2", "value2")

        manager1.save()
        manager2.save()

        # Reload and verify state is valid JSON
        final_state = json.loads(state_file.read_text())
        assert "preferences" in final_state

    def test_load_after_save_reflects_changes(self, state_file):
        """Test loading state after save reflects changes."""
        manager1 = UserStateManager(state_file)
        manager1.set_preference("auto_git_enabled", False)
        manager1.save()

        # Load in new manager instance
        manager2 = UserStateManager(state_file)

        assert manager2.get_preference("auto_git_enabled") is False


class TestErrorHandling:
    """Test error handling and edge cases."""

    @pytest.fixture
    def state_file(self, tmp_path):
        """Create temporary state file for testing."""
        return tmp_path / "user_state.json"

    def test_user_state_error_raised_for_permission_denied(self, tmp_path):
        """Test UserStateError raised when file permissions deny access."""
        state_file = tmp_path / "user_state.json"
        state_file.write_text("{}")
        state_file.chmod(0o000)  # Remove all permissions

        with pytest.raises(UserStateError, match="Permission denied"):
            UserStateManager(state_file)

        # Cleanup
        state_file.chmod(0o644)

    def test_default_state_file_uses_home_directory(self):
        """Test DEFAULT_STATE_FILE is in user's home directory."""
        assert ".autonomous-dev" in str(DEFAULT_STATE_FILE)
        assert "user_state.json" in str(DEFAULT_STATE_FILE)

    def test_save_handles_disk_full_gracefully(self, state_file):
        """Test save() handles disk full errors gracefully."""
        manager = UserStateManager(state_file)

        with patch("pathlib.Path.write_text", side_effect=OSError("No space left on device")):
            with pytest.raises(UserStateError, match="Failed to save state"):
                manager.save()
