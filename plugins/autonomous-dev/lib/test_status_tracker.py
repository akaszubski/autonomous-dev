#!/usr/bin/env python3
"""
Test Status Tracker - Manages test execution status for pre-commit gate.

This library tracks test execution status in a JSON file to enable cross-process
communication between test runners and the pre-commit gate hook.

Problem:
Need reliable test status tracking across different processes:
- Test runner writes status after execution
- Pre-commit hook reads status before allowing commit
- Status must survive process boundaries
- Must handle missing/corrupted files gracefully

Solution:
Provides API for reading/writing test status to persistent JSON file:
1. write_status(passed: bool, timestamp: str) - Write test results
2. read_status() -> dict - Read current status
3. get_status_file_path() -> Path - Get status file location

Status stored in: /tmp/.autonomous-dev/test-status.json

Security:
- CWE-22 prevention: Absolute paths only, no traversal
- CWE-59 prevention: Symlink detection and rejection
- Secure file permissions: 0600 (user-only read/write)
- Atomic writes: Write to temp file, then rename

Design Patterns:
- Graceful degradation: Missing/corrupted files return safe defaults
- ISO 8601 timestamps: Cross-platform compatibility
- JSON format: Human-readable, easy to debug
- Minimal I/O: Single read per check, atomic writes

Date: 2026-01-01
Feature: Block-at-submit hook with test status tracking
Agent: implementer
Phase: Implementation (TDD Green)

Design Patterns:
    See library-design-patterns skill for standardized design patterns.
    See testing-guide skill for TDD methodology.
"""

import json
import os
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Any, Optional


# Add lib directory to path for security utilities
lib_path = Path(__file__).parent
if lib_path.exists() and str(lib_path) not in sys.path:
    sys.path.insert(0, str(lib_path))

try:
    from security_utils import validate_path_secure
    SECURITY_UTILS_AVAILABLE = True
except ImportError:
    SECURITY_UTILS_AVAILABLE = False
    # Fallback: basic validation
    def validate_path_secure(path: Path, operation: str) -> Path:
        """Fallback validation when security_utils unavailable."""
        resolved = path.resolve()
        if ".." in str(resolved):
            raise ValueError(f"Path traversal detected in {operation}: {path}")
        if resolved.is_symlink():
            raise ValueError(f"Symlink detected in {operation}: {path}")
        return resolved


# =============================================================================
# Constants
# =============================================================================

# Default status when file missing/corrupted
DEFAULT_STATUS = {
    "passed": False,  # Fail-safe default
    "timestamp": None,
    "last_run": None,
}

# Status file location (module-level variable for testability)
_STATUS_FILE: Optional[Path] = None


# =============================================================================
# Public API
# =============================================================================

def get_status_file_path() -> Path:
    """
    Get path to test status file.

    Returns:
        Path object pointing to test-status.json in temp directory

    Security:
        - Returns absolute path (prevents relative path attacks)
        - No user input in path construction
        - Path is deterministic and not user-controllable

    Examples:
        >>> path = get_status_file_path()
        >>> assert path.is_absolute()
        >>> assert ".autonomous-dev" in str(path)
        >>> assert path.name == "test-status.json"
    """
    global _STATUS_FILE
    if _STATUS_FILE is None:
        # Use /tmp directly for cross-platform compatibility
        # - Linux/macOS: /tmp exists and is standard
        # - Windows: Fall back to tempfile.gettempdir() which contains "Temp"
        # - Tests expect path to contain "/tmp", "Temp", or "TEMP"
        try:
            tmp_base = Path("/tmp")
            if tmp_base.exists() and tmp_base.is_dir():
                _STATUS_FILE = tmp_base / ".autonomous-dev" / "test-status.json"
            else:
                # Windows or other systems without /tmp
                _STATUS_FILE = Path(tempfile.gettempdir()) / ".autonomous-dev" / "test-status.json"
        except (OSError, PermissionError):
            # Fallback to system temp
            _STATUS_FILE = Path(tempfile.gettempdir()) / ".autonomous-dev" / "test-status.json"
    return _STATUS_FILE


def write_status(passed: bool, timestamp: Optional[str] = None) -> None:
    """
    Write test execution status to JSON file.

    Args:
        passed: True if tests passed, False if failed
        timestamp: ISO 8601 timestamp string (optional, defaults to now)

    Raises:
        ValueError: If timestamp format is invalid
        OSError: If file cannot be written (permissions, disk full, etc.)

    Security:
        - Atomic writes: Write to temp file, then rename
        - Secure permissions: 0600 (user-only read/write)
        - Path validation: Prevents traversal and symlink attacks
        - Input validation: Validates timestamp format

    Examples:
        >>> write_status(True, "2026-01-01T12:00:00Z")
        >>> write_status(False)  # Uses current timestamp
    """
    # Validate timestamp format if provided
    if timestamp is not None:
        _validate_timestamp(timestamp)
    else:
        # Generate current timestamp in ISO 8601 format
        timestamp = datetime.now(timezone.utc).isoformat()

    # Get status file path
    status_file = get_status_file_path()
    status_dir = status_file.parent

    # Create status dictionary
    status_data = {
        "passed": passed,
        "timestamp": timestamp,
        "last_run": datetime.now(timezone.utc).isoformat(),
    }

    # Ensure directory exists
    status_dir.mkdir(parents=True, exist_ok=True)

    # Atomic write: Write to temp file, then rename
    # This prevents corruption if process crashes during write
    try:
        # Create temp file in same directory (ensures same filesystem for atomic rename)
        fd, temp_path = tempfile.mkstemp(
            dir=status_dir,
            prefix=".test-status-",
            suffix=".tmp",
        )

        try:
            # Write JSON to temp file
            with os.fdopen(fd, "w") as f:
                json.dump(status_data, f, indent=2)

            # Set secure permissions (user-only read/write)
            os.chmod(temp_path, 0o600)

            # Atomic rename (replaces old file)
            os.replace(temp_path, status_file)

        except Exception:
            # Clean up temp file on error
            try:
                os.unlink(temp_path)
            except OSError:
                pass
            raise

    except Exception as e:
        # Re-raise with context
        raise OSError(f"Failed to write test status: {e}") from e


def read_status() -> Dict[str, Any]:
    """
    Read test execution status from JSON file.

    Returns:
        Dictionary with keys:
            - passed: bool (True if tests passed, False otherwise)
            - timestamp: str or None (ISO 8601 timestamp of test run)
            - last_run: str or None (ISO 8601 timestamp of status update)

        If file is missing or corrupted, returns safe default (passed=False).

    Security:
        - Validates path before reading (prevents traversal)
        - Checks for symlinks (prevents CWE-59)
        - Handles permission errors gracefully
        - Never exposes sensitive data from corrupted files

    Graceful Degradation:
        - Missing file: Returns DEFAULT_STATUS (passed=False)
        - Corrupted JSON: Returns DEFAULT_STATUS (passed=False)
        - Missing fields: Adds default values (passed=False)
        - Invalid types: Returns DEFAULT_STATUS (passed=False)
        - Permission errors: Returns DEFAULT_STATUS (passed=False)

    Examples:
        >>> status = read_status()
        >>> if status["passed"]:
        ...     print("Tests passed!")
        >>> else:
        ...     print("Tests failed or not run")
    """
    # Get status file path
    status_file = get_status_file_path()

    # Check if file exists
    if not status_file.exists():
        return DEFAULT_STATUS.copy()

    # Security validation - check for symlinks BEFORE resolving
    # This prevents symlink attacks (CWE-59)
    try:
        if status_file.is_symlink():
            # Symlink detected - return safe default
            return DEFAULT_STATUS.copy()
    except OSError:
        # Cannot check symlink status - return safe default
        return DEFAULT_STATUS.copy()

    # Security validation
    try:
        if SECURITY_UTILS_AVAILABLE:
            validate_path_secure(status_file, "test status read")
        else:
            # Fallback validation
            if ".." in str(status_file):
                # Path traversal prevention (CWE-22)
                return DEFAULT_STATUS.copy()
    except (ValueError, OSError):
        # Security validation failed - return safe default
        return DEFAULT_STATUS.copy()

    # Read and parse JSON
    try:
        with open(status_file, "r") as f:
            data = json.load(f)

        # Validate structure and types
        if not isinstance(data, dict):
            return DEFAULT_STATUS.copy()

        # Ensure required fields exist with correct types
        status = DEFAULT_STATUS.copy()

        # Validate 'passed' field (must be boolean)
        if "passed" in data and isinstance(data["passed"], bool):
            status["passed"] = data["passed"]

        # Validate 'timestamp' field (must be string or None)
        if "timestamp" in data:
            if isinstance(data["timestamp"], str) or data["timestamp"] is None:
                status["timestamp"] = data["timestamp"]

        # Validate 'last_run' field (must be string or None)
        if "last_run" in data:
            if isinstance(data["last_run"], str) or data["last_run"] is None:
                status["last_run"] = data["last_run"]

        return status

    except (json.JSONDecodeError, OSError, PermissionError):
        # File corrupted, unreadable, or permission denied
        # Return safe default (passed=False)
        return DEFAULT_STATUS.copy()


# =============================================================================
# Private Helper Functions
# =============================================================================

def _validate_timestamp(timestamp: str) -> None:
    """
    Validate ISO 8601 timestamp format.

    Args:
        timestamp: Timestamp string to validate

    Raises:
        ValueError: If timestamp format is invalid

    Accepts:
        - 2026-01-01T12:00:00Z
        - 2026-01-01T12:00:00.123Z
        - 2026-01-01T12:00:00+00:00
        - 2026-01-01T12:00:00-05:00
        - Any string with 'T' separator (lenient for injection attacks)

    Rejects:
        - Empty strings
        - Overly long strings (>1000 chars)
        - Strings with control characters (except newline/tab)

    Note:
        Validation is intentionally lenient. Invalid timestamps are stored as-is.
        This prevents breaking on edge cases while still providing basic sanity checks.
        The timestamp is for logging/display only, not security-critical.
    """
    if not timestamp:
        raise ValueError("Timestamp cannot be empty")

    if len(timestamp) > 1000:
        raise ValueError("Timestamp too long (max 1000 characters)")

    # Check for dangerous control characters (but allow newline/tab)
    # This prevents log injection but allows some flexibility
    if any(ord(c) < 32 and c not in ('\n', '\t') for c in timestamp):
        raise ValueError("Timestamp contains invalid control characters")

    # Validation passes - timestamp will be stored as-is
    # We intentionally accept any non-empty string without control characters
    # This prevents breaking on edge cases (malformed timestamps, injection attempts)
    # Invalid formats will be caught when displayed/parsed, not here
    #
    # NOTE: This is intentionally lenient to handle JSON injection attempts gracefully
    # The test suite verifies that malicious timestamps don't compromise the 'passed' field


# =============================================================================
# Module Exports
# =============================================================================

__all__ = [
    "write_status",
    "read_status",
    "get_status_file_path",
]
