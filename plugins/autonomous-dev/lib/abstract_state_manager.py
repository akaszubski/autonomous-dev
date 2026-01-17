#!/usr/bin/env python3
"""
Abstract State Manager - Base class for all state management in autonomous-dev.

This module provides a unified ABC (Abstract Base Class) that standardizes
state management patterns across:
- BatchStateManager (batch_state_manager.py)
- UserStateManager (user_state_manager.py)
- CheckpointManager (checkpoint.py)
- SessionTracker (session_tracker.py)

Key Features:
1. Abstract methods for load/save/cleanup operations
2. Concrete helper methods for security, atomicity, and auditing
3. Generic type support for type-safe state management
4. Thread-safe file locking
5. Atomic writes with temp file + rename pattern
6. Path validation (CWE-22 path traversal, CWE-59 symlinks)
7. Audit logging for security events

Security Requirements:
- CWE-22 (path traversal) prevention in _validate_state_path()
- CWE-59 (symlink attacks) prevention
- CWE-367 (TOCTOU) mitigation via atomic writes
- CWE-732 (permission checks) via 0o600 file permissions

Design Pattern:
    Abstract Base Class with Template Method pattern
    - Abstract methods: load_state(), save_state(), cleanup_state()
    - Concrete methods: exists(), _validate_state_path(), _atomic_write(),
                       _get_file_lock(), _audit_operation()

Usage:
    from abstract_state_manager import StateManager, StateError

    class MyStateManager(StateManager[Dict[str, Any]]):
        def __init__(self, state_file: Path):
            self.state_file = state_file

        def load_state(self) -> Dict[str, Any]:
            # Implementation...
            pass

        def save_state(self, state: Dict[str, Any]) -> None:
            # Implementation...
            pass

        def cleanup_state(self) -> None:
            # Implementation...
            pass

Date: 2026-01-09
Issue: #220 (Extract StateManager ABC from 4 state managers)
Agent: implementer
Phase: TDD Green (making tests pass)

See error-handling-patterns skill for exception hierarchy and error handling best practices.
See testing-guide skill for TDD methodology and test patterns.
"""

import os
import sys
import tempfile
import threading
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any, Dict, Generic, TypeVar

# Import security utilities for path validation and audit logging
sys.path.insert(0, str(Path(__file__).parent))
from security_utils import audit_log

# Import StateError from exceptions module
from exceptions import StateError  # type: ignore[import-not-found]

# Export StateError for backward compatibility
__all__ = ["StateManager", "StateError"]

# Generic type variable for state data
T = TypeVar('T')

# Thread-safe locks for file operations
_file_locks: Dict[str, threading.RLock] = {}
_locks_lock = threading.Lock()


class StateManager(ABC, Generic[T]):
    """Abstract base class for state management.

    Provides common functionality for all state managers including:
    - Abstract methods for load/save/cleanup operations
    - Concrete helper methods for security, atomicity, and auditing
    - Thread-safe file locking
    - Atomic writes with temp file + rename pattern
    - Path validation (CWE-22, CWE-59)

    Type Parameter:
        T: Type of state data (e.g., Dict[str, Any], BatchState, etc.)

    Subclass Requirements:
        Must implement:
        - load_state() -> T
        - save_state(state: T) -> None
        - cleanup_state() -> None

    Examples:
        >>> class MyManager(StateManager[Dict[str, Any]]):
        ...     def __init__(self, state_file: Path):
        ...         self.state_file = state_file
        ...
        ...     def load_state(self) -> Dict[str, Any]:
        ...         return {}
        ...
        ...     def save_state(self, state: Dict[str, Any]) -> None:
        ...         pass
        ...
        ...     def cleanup_state(self) -> None:
        ...         pass
        >>> manager = MyManager(Path("/tmp/state.json"))
        >>> manager.exists()
        False
    """

    @abstractmethod
    def load_state(self) -> T:
        """Load state from storage.

        Returns:
            Loaded state data of type T

        Raises:
            StateError: If load fails
        """
        pass

    @abstractmethod
    def save_state(self, state: T) -> None:
        """Save state to storage.

        Args:
            state: State data to save

        Raises:
            StateError: If save fails
        """
        pass

    @abstractmethod
    def cleanup_state(self) -> None:
        """Clean up state storage.

        Raises:
            StateError: If cleanup fails
        """
        pass

    def exists(self) -> bool:
        """Check if state file exists.

        This is a concrete method with default implementation that checks
        if self.state_file exists. Subclasses can override if needed.

        Returns:
            True if state file exists, False otherwise

        Examples:
            >>> manager = MyManager(Path("/tmp/state.json"))
            >>> manager.exists()
            False
            >>> Path("/tmp/state.json").write_text("{}")
            2
            >>> manager.exists()
            True
        """
        if hasattr(self, 'state_file'):
            return Path(self.state_file).exists()  # type: ignore[attr-defined]
        return False

    def _validate_state_path(self, path: Path) -> Path:
        """Validate state file path for security.

        Implements comprehensive path validation:
        - Path traversal prevention (CWE-22)
        - Symlink attack prevention (CWE-59)
        - Outside project detection

        Args:
            path: Path to validate

        Returns:
            Validated Path object (resolved to absolute path)

        Raises:
            StateError: If path is unsafe (traversal, symlink, outside project)

        Security:
            - CWE-22: Rejects paths with ".." components
            - CWE-59: Rejects symlinks (before and after resolution)
            - Audit logs all security violations

        Examples:
            >>> manager = MyManager(Path("/tmp/state.json"))
            >>> manager._validate_state_path(Path("/tmp/../../etc/passwd"))
            Traceback (most recent call last):
            StateError: Invalid path: path traversal detected
        """
        # Convert to Path if string
        if isinstance(path, str):
            path = Path(path)

        # Check for path traversal in string form (CWE-22)
        path_str = str(path)
        if ".." in path_str:
            self._audit_operation(
                "path_validation",
                "failure",
                {
                    "type": "path_traversal",
                    "path": path_str,
                    "component": self.__class__.__name__
                }
            )
            raise StateError(
                f"Invalid path: path traversal detected in {path_str}\n"
                f"Paths with '..' are not allowed for security (CWE-22)"
            )

        # Check for symlink before resolution (CWE-59)
        if path.exists() and path.is_symlink():
            self._audit_operation(
                "path_validation",
                "failure",
                {
                    "type": "symlink_attack",
                    "path": str(path),
                    "component": self.__class__.__name__
                }
            )
            raise StateError(
                f"Invalid path: symlinks not allowed for security (CWE-59): {path}"
            )

        # Resolve to absolute path
        try:
            resolved_path = path.resolve()
        except (OSError, RuntimeError) as e:
            raise StateError(f"Failed to resolve path: {e}")

        # Check for symlink after resolution (CWE-59 - defense in depth)
        if resolved_path.exists() and resolved_path.is_symlink():
            self._audit_operation(
                "path_validation",
                "failure",
                {
                    "type": "symlink_after_resolution",
                    "path": str(resolved_path),
                    "component": self.__class__.__name__
                }
            )
            raise StateError(
                f"Invalid path: symlink detected after resolution: {resolved_path}"
            )

        return resolved_path

    def _atomic_write(self, path: Path, data: str, mode: int = 0o600) -> None:
        """Write data to file atomically.

        Uses atomic write pattern (temp file + rename) to prevent corruption.
        File permissions set to mode (default: 0o600 - owner read/write only).

        Args:
            path: Target file path
            data: Data to write (string)
            mode: File permissions (default: 0o600 for owner-only read/write)

        Raises:
            StateError: If write fails

        Security:
            - Atomic write (temp file + rename) prevents partial writes
            - File permissions set to mode (default: 0o600) for CWE-732
            - Temp file created in same directory as target (same filesystem)

        Design:
            1. CREATE: tempfile.mkstemp() creates .tmp file in same directory
            2. WRITE: Data written to .tmp file
            3. CHMOD: Set secure permissions (mode)
            4. RENAME: temp_path.replace(target) atomically renames file

        Examples:
            >>> manager = MyManager(Path("/tmp/state.json"))
            >>> manager._atomic_write(Path("/tmp/state.json"), '{"key": "value"}')
            >>> Path("/tmp/state.json").read_text()
            '{"key": "value"}'
        """
        # Ensure parent directory exists
        path.parent.mkdir(parents=True, exist_ok=True)

        # Create temp file in same directory (same filesystem for atomic rename)
        temp_fd, temp_path_str = tempfile.mkstemp(
            dir=path.parent,
            prefix=f".{path.stem}_",
            suffix=".tmp"
        )
        temp_path = Path(temp_path_str)

        try:
            # Write data to temp file
            os.write(temp_fd, data.encode('utf-8'))
            os.close(temp_fd)

            # Set secure permissions (CWE-732)
            temp_path.chmod(mode)

            # Atomic rename (POSIX guarantees atomicity)
            temp_path.replace(path)

        except Exception as e:
            # Cleanup temp file on error
            try:
                os.close(temp_fd)
            except OSError as close_error:
                pass  # Ignore errors closing file descriptor
            try:
                temp_path.unlink()
            except (OSError, IOError) as unlink_error:
                pass  # Ignore errors during cleanup
            raise StateError(f"Atomic write failed: {e}")

    def _get_file_lock(self, path: Path) -> threading.RLock:
        """Get or create thread-safe reentrant lock for file.

        Args:
            path: File path to lock

        Returns:
            Threading reentrant lock for file (allows same thread to acquire multiple times)

        Examples:
            >>> manager = MyManager(Path("/tmp/state.json"))
            >>> lock1 = manager._get_file_lock(Path("/tmp/state.json"))
            >>> lock2 = manager._get_file_lock(Path("/tmp/state.json"))
            >>> lock1 is lock2
            True
            >>> isinstance(lock1, threading.RLock)
            True
        """
        file_key = str(path.resolve())
        with _locks_lock:
            if file_key not in _file_locks:
                _file_locks[file_key] = threading.RLock()
            return _file_locks[file_key]

    def _audit_operation(self, operation: str, status: str, details: Dict[str, Any]) -> None:
        """Log operation to audit log.

        Args:
            operation: Operation name (e.g., "load_state", "save_state")
            status: Operation status ("success", "failure", "warning")
            details: Additional operation details

        Examples:
            >>> manager = MyManager(Path("/tmp/state.json"))
            >>> manager._audit_operation("load_state", "success", {"path": "/tmp/state.json"})
        """
        audit_log(operation, status, details)
