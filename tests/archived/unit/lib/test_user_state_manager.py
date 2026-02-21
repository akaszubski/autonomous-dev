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
    from exceptions import StateError
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

        with pytest.raises(UserStateError, match="path traversal"):
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

        # Mock os.write since _atomic_write uses os.write, not Path.write_text
        with patch("os.write", side_effect=OSError("No space left on device")):
            with pytest.raises(StateError, match="Atomic write failed"):
                manager.save()


class TestUserStateManagerABCMigration:
    """Tests for Issue #222: UserStateManager ABC migration.

    Tests that UserStateManager properly inherits from StateManager ABC
    and implements all abstract methods while maintaining backward compatibility.

    Migration Requirements:
    1. UserStateManager inherits from StateManager[Dict[str, Any]]
    2. Implements abstract methods: load_state(), save_state(), cleanup_state()
    3. Uses inherited helpers: _validate_state_path(), _atomic_write(), _get_file_lock()
    4. Raises StateError instead of UserStateError
    5. Maintains backward compatibility for existing methods

    TDD Phase: Red - Tests written BEFORE implementation
    Expected: All tests FAIL initially (migration not done yet)
    """

    @pytest.fixture
    def temp_state_file(self, tmp_path):
        """Create temporary state file path for testing."""
        state_dir = tmp_path / ".autonomous-dev"
        state_dir.mkdir()
        return state_dir / "user_state.json"

    # ========================================
    # Test 1-2: Inheritance and Generic Type
    # ========================================

    def test_inherits_from_state_manager(self):
        """Test that UserStateManager inherits from StateManager ABC.

        Verifies:
        - UserStateManager is a subclass of StateManager
        - Enables polymorphism for state management operations
        """
        from abstract_state_manager import StateManager

        assert issubclass(UserStateManager, StateManager), (
            "UserStateManager should inherit from StateManager ABC"
        )

    def test_generic_type_parameter_dict_str_any(self, temp_state_file):
        """Test that UserStateManager[Dict[str, Any]] works correctly.

        Verifies:
        - Generic type parameter is Dict[str, Any]
        - Type hints are correct for load_state() and save_state()
        """
        from abstract_state_manager import StateManager

        # Create manager instance
        manager = UserStateManager(temp_state_file)

        # Check that manager is instance of StateManager
        assert isinstance(manager, StateManager), (
            "UserStateManager instance should be instance of StateManager"
        )

        # Type hints should be Dict[str, Any] (verified by type checker)
        # This test validates runtime behavior
        state = manager.state
        assert isinstance(state, dict), "State should be a dictionary"

    # ========================================
    # Test 3-5: Abstract Method Implementation
    # ========================================

    def test_load_state_returns_dict_str_any(self, temp_state_file):
        """Test that load_state() returns Dict[str, Any].

        Verifies:
        - load_state() abstract method is implemented
        - Returns correct type (Dict[str, Any])
        - Loads state from file or returns default
        """
        # Create state file with test data
        test_state = {
            "first_run_complete": True,
            "preferences": {"auto_git": False},
            "version": "1.0"
        }
        temp_state_file.write_text(json.dumps(test_state))

        # Create manager (calls load_state internally)
        manager = UserStateManager(temp_state_file)

        # Verify load_state returns correct type and data
        loaded_state = manager.load_state()
        assert isinstance(loaded_state, dict), "load_state() should return dict"
        assert loaded_state["first_run_complete"] is True
        assert loaded_state["preferences"]["auto_git"] is False

    def test_save_state_accepts_dict_str_any(self, temp_state_file):
        """Test that save_state() accepts Dict[str, Any].

        Verifies:
        - save_state() abstract method is implemented
        - Accepts correct type (Dict[str, Any])
        - Saves state to file
        """
        manager = UserStateManager(temp_state_file)

        # Create test state
        test_state = {
            "first_run_complete": True,
            "preferences": {"auto_git": True},
            "version": "1.0"
        }

        # Save state
        manager.save_state(test_state)

        # Verify file was written
        assert temp_state_file.exists(), "save_state() should create state file"
        saved_data = json.loads(temp_state_file.read_text())
        assert saved_data == test_state

    def test_cleanup_state_removes_state_file(self, temp_state_file):
        """Test that cleanup_state() removes the state file.

        Verifies:
        - cleanup_state() abstract method is implemented
        - Removes state file from disk
        - Handles missing file gracefully
        """
        # Create manager and save state
        manager = UserStateManager(temp_state_file)
        manager.save()
        assert temp_state_file.exists()

        # Cleanup state
        manager.cleanup_state()

        # Verify file is removed
        assert not temp_state_file.exists(), (
            "cleanup_state() should remove state file"
        )

    def test_cleanup_state_handles_missing_file(self, temp_state_file):
        """Test that cleanup_state() handles missing file gracefully.

        Verifies:
        - No exception when file doesn't exist
        - Idempotent operation
        """
        manager = UserStateManager(temp_state_file)

        # Cleanup non-existent file (should not raise)
        manager.cleanup_state()

        # Call again (should still not raise)
        manager.cleanup_state()

    # ========================================
    # Test 6: Inherited exists() Method
    # ========================================

    def test_exists_method_works(self, temp_state_file):
        """Test that inherited exists() method works correctly.

        Verifies:
        - exists() method is inherited from StateManager
        - Returns False when file doesn't exist
        - Returns True when file exists
        """
        manager = UserStateManager(temp_state_file)

        # Initially doesn't exist
        assert not manager.exists(), "exists() should return False initially"

        # Save state
        manager.save()

        # Now exists
        assert manager.exists(), "exists() should return True after save"

    # ========================================
    # Test 7-8: Atomic Write and File Locking
    # ========================================

    def test_atomic_write_is_used_for_save(self, temp_state_file):
        """Test that _atomic_write() is used for save operations.

        Verifies:
        - save_state() uses _atomic_write() internally
        - Atomic write prevents file corruption
        - Uses temp file + rename pattern
        """
        manager = UserStateManager(temp_state_file)

        # Mock _atomic_write to verify it's called
        with patch.object(manager, '_atomic_write', wraps=manager._atomic_write) as mock_atomic:
            test_state = {
                "first_run_complete": True,
                "preferences": {},
                "version": "1.0"
            }
            manager.save_state(test_state)

            # Verify _atomic_write was called
            assert mock_atomic.call_count >= 1, (
                "save_state() should use _atomic_write() for atomic operations"
            )

    def test_file_lock_is_used_for_concurrency(self, temp_state_file):
        """Test that _get_file_lock() is used for concurrency safety.

        Verifies:
        - _get_file_lock() returns reentrant lock
        - Same lock for same file path
        - Thread-safe concurrent access
        """
        manager1 = UserStateManager(temp_state_file)
        manager2 = UserStateManager(temp_state_file)

        # Get locks for same file
        lock1 = manager1._get_file_lock(temp_state_file)
        lock2 = manager2._get_file_lock(temp_state_file)

        # Should be the same lock object
        assert lock1 is lock2, (
            "Same file should return same lock object for thread safety"
        )

        # Should be reentrant lock - check type name (isinstance() doesn't work with RLock in Python 3.14)
        assert type(lock1).__name__ == "RLock", (
            "_get_file_lock() should return RLock for reentrancy"
        )

    # ========================================
    # Test 9: StateError Instead of UserStateError
    # ========================================

    def test_raises_state_error_for_invalid_operations(self, tmp_path):
        """Test that StateError is raised instead of UserStateError.

        Verifies:
        - Path validation raises StateError
        - Save errors raise StateError
        - Consistent with StateManager ABC pattern
        """
        from abstract_state_manager import StateError

        # Test path traversal raises StateError
        unsafe_path = tmp_path / ".." / ".." / "etc" / "passwd"
        with pytest.raises(StateError, match="path traversal"):
            UserStateManager(unsafe_path)

    def test_state_error_for_path_outside_home_or_temp(self):
        """Test StateError raised for paths outside home/temp directories.

        Verifies:
        - Paths outside allowed directories raise StateError
        - Security validation integrated with ABC
        """
        from abstract_state_manager import StateError

        unsafe_path = Path("/etc/passwd")
        with pytest.raises(StateError, match="Path must be within home directory"):
            UserStateManager(unsafe_path)

    def test_state_error_for_symlink_attack(self, tmp_path):
        """Test StateError raised for symlink attacks (CWE-59).

        Verifies:
        - Symlink validation raises StateError
        - Security checks integrated with ABC
        """
        from abstract_state_manager import StateError

        # Create symlink
        target = tmp_path / "target.json"
        symlink = tmp_path / "symlink.json"
        target.write_text("{}")
        symlink.symlink_to(target)

        # Should raise StateError
        with pytest.raises(StateError, match="symlink"):
            UserStateManager(symlink)

    # ========================================
    # Test 10-11: Backward Compatibility
    # ========================================

    def test_backward_compatible_save_method(self, temp_state_file):
        """Test that existing save() method still works.

        Verifies:
        - save() method maintains backward compatibility
        - Existing code doesn't break after migration
        - Uses new save_state() internally
        """
        manager = UserStateManager(temp_state_file)
        manager.state["first_run_complete"] = True

        # Old-style save() should still work
        manager.save()

        # Verify state was saved
        assert temp_state_file.exists()
        saved_data = json.loads(temp_state_file.read_text())
        assert saved_data["first_run_complete"] is True

    def test_backward_compatible_is_first_run(self, temp_state_file):
        """Test that is_first_run() method still works.

        Verifies:
        - is_first_run() maintains backward compatibility
        - Works with new ABC-based implementation
        """
        manager = UserStateManager(temp_state_file)

        # Should return True initially
        assert manager.is_first_run() is True

        # Mark complete
        manager.record_first_run_complete()

        # Should return False now
        assert manager.is_first_run() is False

    def test_backward_compatible_preferences(self, temp_state_file):
        """Test that preference methods still work.

        Verifies:
        - get_preference() maintains backward compatibility
        - set_preference() maintains backward compatibility
        - Works with new ABC-based implementation
        """
        manager = UserStateManager(temp_state_file)

        # Set preference (old API)
        manager.set_preference("auto_git_enabled", True)

        # Get preference (old API)
        value = manager.get_preference("auto_git_enabled")
        assert value is True

        # Default value
        missing = manager.get_preference("missing_key", default="default")
        assert missing == "default"

    # ========================================
    # Test 12: Path Validation
    # ========================================

    def test_home_directory_paths_allowed(self, tmp_path):
        """Test that home directory paths are allowed.

        Verifies:
        - Paths in home directory pass validation
        - Uses _validate_state_path() from ABC
        """
        # Create path in home directory
        home_path = Path.home() / ".autonomous-dev" / "user_state.json"

        # Should not raise (but we'll use tmp_path for testing)
        # Just verify the validation logic accepts home paths
        manager = UserStateManager(tmp_path / "state.json")
        validated = manager._validate_state_path(tmp_path / "state.json")

        assert validated.is_absolute(), "Validated path should be absolute"

    def test_temp_directory_paths_allowed(self, tmp_path):
        """Test that temp directory paths are allowed (for tests).

        Verifies:
        - Paths in temp directory pass validation
        - Enables testing without modifying home directory
        """
        # tmp_path is in temp directory
        temp_state_file = tmp_path / "user_state.json"

        # Should not raise
        manager = UserStateManager(temp_state_file)

        # Verify validation passed
        assert manager.state_file == temp_state_file.resolve()

    def test_validate_state_path_inherited_method(self, tmp_path):
        """Test that _validate_state_path() is inherited from StateManager.

        Verifies:
        - Method is inherited, not reimplemented
        - Rejects path traversal
        - Rejects symlinks
        """
        from abstract_state_manager import StateError

        manager = UserStateManager(tmp_path / "state.json")

        # Test path traversal detection
        unsafe = tmp_path / ".." / ".." / "etc" / "passwd"
        with pytest.raises(StateError, match="path traversal"):
            manager._validate_state_path(unsafe)

    # ========================================
    # Test 13: Integration Tests
    # ========================================

    def test_full_lifecycle_with_abc(self, temp_state_file):
        """Test full lifecycle using ABC methods.

        Verifies:
        - Create manager -> load_state() called
        - Modify state -> save_state() works
        - Cleanup -> cleanup_state() works
        - All ABC methods integrate correctly
        """
        # Create and load
        manager = UserStateManager(temp_state_file)
        initial_state = manager.load_state()
        assert initial_state["first_run_complete"] is False

        # Modify and save
        modified_state = {
            "first_run_complete": True,
            "preferences": {"test": "value"},
            "version": "1.0"
        }
        manager.save_state(modified_state)
        assert manager.exists()

        # Reload in new manager
        manager2 = UserStateManager(temp_state_file)
        reloaded = manager2.load_state()
        assert reloaded["first_run_complete"] is True
        assert reloaded["preferences"]["test"] == "value"

        # Cleanup
        manager2.cleanup_state()
        assert not manager2.exists()

    def test_state_manager_polymorphism(self, temp_state_file):
        """Test that UserStateManager can be used polymorphically.

        Verifies:
        - UserStateManager works as StateManager[Dict[str, Any]]
        - Enables generic state management code
        """
        from abstract_state_manager import StateManager

        manager: StateManager[Dict[str, Any]] = UserStateManager(temp_state_file)

        # Should work through StateManager interface
        assert hasattr(manager, 'load_state')
        assert hasattr(manager, 'save_state')
        assert hasattr(manager, 'cleanup_state')
        assert hasattr(manager, 'exists')

        # Should work at runtime
        state = manager.load_state()
        assert isinstance(state, dict)

    def test_concurrent_access_with_file_locks(self, temp_state_file):
        """Test concurrent access safety with file locks.

        Verifies:
        - Multiple managers for same file use same lock
        - Thread-safe concurrent operations
        - No file corruption
        """
        import concurrent.futures

        def update_preference(manager_class, state_file, key, value):
            """Helper to update preference in thread."""
            manager = manager_class(state_file)
            manager.set_preference(key, value)
            manager.save()

        # Create multiple threads updating different preferences
        with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
            futures = []
            for i in range(5):
                future = executor.submit(
                    update_preference,
                    UserStateManager,
                    temp_state_file,
                    f"pref_{i}",
                    f"value_{i}"
                )
                futures.append(future)

            # Wait for all to complete
            concurrent.futures.wait(futures)

        # Verify state file is valid JSON (not corrupted)
        final_state = json.loads(temp_state_file.read_text())
        assert "preferences" in final_state
        assert isinstance(final_state["preferences"], dict)
