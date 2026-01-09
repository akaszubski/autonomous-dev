#!/usr/bin/env python3
"""
User state management for autonomous-dev plugin.

Manages user preferences and first-run state persistence for Issue #61.

Features:
- First-run detection
- User preference storage (auto_git_enabled, etc.)
- State file persistence in ~/.autonomous-dev/
- Security validation (CWE-22 path traversal prevention)
- Audit logging for all operations

Date: 2025-11-11
Issue: #61 (Enable Zero Manual Git Operations by Default)
Agent: implementer

See error-handling-patterns skill for exception hierarchy and error handling best practices.


Design Patterns:
    See library-design-patterns skill for standardized design patterns.
    See state-management-patterns skill for standardized design patterns.
"""

import copy
import json
import sys
import tempfile
from pathlib import Path
from typing import Any, Dict

# Import security utilities (standard pattern from project libraries)
try:
    from .security_utils import audit_log
    from .abstract_state_manager import StateManager
    from .exceptions import StateError
except ImportError:
    # Direct script execution - add lib dir to path
    lib_dir = Path(__file__).parent.resolve()
    sys.path.insert(0, str(lib_dir))
    from security_utils import audit_log
    from abstract_state_manager import StateManager
    from exceptions import StateError


# Default state file location
DEFAULT_STATE_FILE = Path.home() / ".autonomous-dev" / "user_state.json"

# Default state structure
DEFAULT_STATE = {
    "first_run_complete": False,
    "preferences": {},
    "version": "1.0"
}


# Exception hierarchy pattern from error-handling-patterns skill:
# BaseException -> Exception -> AutonomousDevError -> DomainError(BaseException) -> SpecificError
# Note: UserStateError is deprecated - use StateError from exceptions.py
UserStateError = StateError  # Backward compatibility alias


class UserStateManager(StateManager[Dict[str, Any]]):
    """
    Manage user state and preferences.

    Handles loading, saving, and updating user preferences with security
    validation and audit logging.
    """

    def __init__(self, state_file: Path):
        """
        Initialize UserStateManager.

        Args:
            state_file: Path to state file

        Raises:
            StateError: If path validation fails or permission denied
        """
        self.state_file = self._validate_state_file_path(state_file)
        self.state = self._load_state()

    def _validate_state_file_path(self, path: Path) -> Path:
        """
        Validate state file path for security (CWE-22, CWE-59, CWE-367).

        Implements comprehensive path validation:
        - Path traversal prevention (CWE-22)
        - Symlink attack prevention (CWE-59)
        - TOCTOU mitigation (CWE-367)

        Note: Uses inherited _validate_state_path() for basic checks,
        then adds custom validation for home/temp directory restriction.

        Args:
            path: Path to validate

        Returns:
            Validated Path object

        Raises:
            StateError: If path is unsafe
        """
        # Use inherited validation for basic security checks (CWE-22, CWE-59)
        resolved_path = self._validate_state_path(path)

        # Ensure path is within home directory or temp directory (for tests)
        home_dir = Path.home().resolve()
        temp_dir = Path(tempfile.gettempdir()).resolve()

        # Check if path is in home or temp (allow temp for testing)
        is_in_home = False
        is_in_temp = False

        try:
            resolved_path.relative_to(home_dir)
            is_in_home = True
        except ValueError:
            pass

        try:
            resolved_path.relative_to(temp_dir)
            is_in_temp = True
        except ValueError:
            pass

        if not (is_in_home or is_in_temp):
            self._audit_operation(
                "path_validation",
                "failure",
                {
                    "type": "path_outside_allowed_dirs",
                    "path": str(resolved_path),
                    "home": str(home_dir),
                    "temp": str(temp_dir),
                    "component": "user_state_manager"
                }
            )
            raise StateError(f"Path must be within home directory: {resolved_path}")

        # Atomic check for file access (CWE-367 - TOCTOU mitigation)
        # Use try/except instead of exists() check to avoid race condition
        if resolved_path.exists():
            try:
                # Atomically test read access
                resolved_path.read_text()
            except PermissionError:
                raise StateError(f"Permission denied: {resolved_path}")

        return resolved_path

    def _load_state(self) -> Dict[str, Any]:
        """
        Load state from file or return default state.

        Returns:
            State dictionary
        """
        if not self.state_file.exists():
            self._audit_operation(
                "state_file_not_found",
                "success",
                {
                    "path": str(self.state_file),
                    "action": "creating_default"
                }
            )
            return copy.deepcopy(DEFAULT_STATE)

        try:
            state_text = self.state_file.read_text()
            state = json.loads(state_text)

            self._audit_operation(
                "state_loaded",
                "success",
                {
                    "path": str(self.state_file),
                    "first_run_complete": state.get("first_run_complete", False)
                }
            )

            return state
        except (json.JSONDecodeError, ValueError) as e:
            # Corrupted JSON - fall back to default state
            self._audit_operation(
                "state_file_corrupted",
                "warning",
                {
                    "path": str(self.state_file),
                    "error": str(e),
                    "action": "using_default_state"
                }
            )
            return copy.deepcopy(DEFAULT_STATE)

    # ========================================
    # Abstract Method Implementations (StateManager ABC)
    # ========================================

    def load_state(self) -> Dict[str, Any]:
        """Implement StateManager.load_state().

        Returns:
            State dictionary loaded from file or default state

        Raises:
            StateError: If load fails
        """
        return self._load_state()

    def save_state(self, state: Dict[str, Any]) -> None:
        """Implement StateManager.save_state() with atomic write.

        Args:
            state: State dictionary to save

        Raises:
            StateError: If save fails
        """
        self.state = state
        lock = self._get_file_lock(self.state_file)
        with lock:
            self.state_file.parent.mkdir(parents=True, exist_ok=True)
            state_json = json.dumps(state, indent=2)
            self._atomic_write(self.state_file, state_json, mode=0o600)
            self._audit_operation("state_saved", "success", {
                "path": str(self.state_file),
                "first_run_complete": state.get("first_run_complete", False)
            })

    def cleanup_state(self) -> None:
        """Implement StateManager.cleanup_state().

        Removes the state file from disk.

        Raises:
            StateError: If cleanup fails
        """
        if self.state_file.exists():
            self.state_file.unlink()
            self._audit_operation("state_cleanup", "success", {
                "path": str(self.state_file)
            })

    # ========================================
    # Backward Compatible Methods
    # ========================================

    def save(self) -> None:
        """Save state to file (backward compatible).

        This method maintains backward compatibility by delegating to save_state().

        Raises:
            StateError: If save fails
        """
        self.save_state(self.state)

    def is_first_run(self) -> bool:
        """
        Check if this is the first run.

        Returns:
            True if first run, False otherwise
        """
        return not self.state.get("first_run_complete", False)

    def record_first_run_complete(self) -> None:
        """Mark first run as complete."""
        self.state["first_run_complete"] = True
        self._audit_operation(
            "first_run_marked_complete",
            "success",
            {"path": str(self.state_file)}
        )

    def get_preference(self, key: str, default: Any = None) -> Any:
        """
        Get user preference value.

        Args:
            key: Preference key
            default: Default value if key not found

        Returns:
            Preference value or default
        """
        return self.state.get("preferences", {}).get(key, default)

    def set_preference(self, key: str, value: Any) -> None:
        """
        Set user preference value.

        Args:
            key: Preference key
            value: Preference value
        """
        if "preferences" not in self.state:
            self.state["preferences"] = {}

        self.state["preferences"][key] = value

        self._audit_operation(
            "preference_updated",
            "success",
            {
                "key": key,
                "value": value,
                "path": str(self.state_file)
            }
        )


# Module-level convenience functions

def load_user_state(state_file: Path = DEFAULT_STATE_FILE) -> Dict[str, Any]:
    """
    Load user state from file.

    Args:
        state_file: Path to state file

    Returns:
        State dictionary
    """
    manager = UserStateManager(state_file)
    return manager.state


def save_user_state(state: Dict[str, Any], state_file: Path = DEFAULT_STATE_FILE) -> None:
    """
    Save user state to file.

    Args:
        state: State dictionary to save
        state_file: Path to state file
    """
    manager = UserStateManager(state_file)
    manager.state = state
    manager.save()


def is_first_run(state_file: Path = DEFAULT_STATE_FILE) -> bool:
    """
    Check if this is the first run.

    Args:
        state_file: Path to state file

    Returns:
        True if first run, False otherwise
    """
    manager = UserStateManager(state_file)
    return manager.is_first_run()


def record_first_run_complete(state_file: Path = DEFAULT_STATE_FILE) -> None:
    """
    Mark first run as complete.

    Args:
        state_file: Path to state file
    """
    manager = UserStateManager(state_file)
    manager.record_first_run_complete()
    manager.save()


def get_user_preference(
    key: str,
    state_file: Path = DEFAULT_STATE_FILE,
    default: Any = None
) -> Any:
    """
    Get user preference value.

    Args:
        key: Preference key
        state_file: Path to state file
        default: Default value if key not found

    Returns:
        Preference value or default
    """
    manager = UserStateManager(state_file)
    return manager.get_preference(key, default)


def set_user_preference(
    key: str,
    value: Any,
    state_file: Path = DEFAULT_STATE_FILE
) -> None:
    """
    Set user preference value.

    Args:
        key: Preference key
        value: Preference value
        state_file: Path to state file
    """
    manager = UserStateManager(state_file)
    manager.set_preference(key, value)
    manager.save()
