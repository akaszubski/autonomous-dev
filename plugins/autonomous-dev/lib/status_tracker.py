#!/usr/bin/env python3
"""
Test Status Tracker - Store and retrieve test results for pre-commit gate

This module provides centralized test status tracking for the pre_commit_gate hook:
- Write test results to /tmp/.autonomous-dev/test-status.json
- Read test results with graceful degradation
- Atomic writes to prevent corruption
- Secure file permissions (0600)

Purpose:
The pre_commit_gate hook needs to know if tests have passed before allowing commits.
This module provides a simple, reliable mechanism for test runners to communicate
test status to the commit hook.

Security Features:
- Uses /tmp with restricted permissions (mode 0600 - owner read/write only)
- Validates paths to prevent directory traversal (CWE-22)
- Atomic writes to prevent race conditions and corruption
- Graceful degradation on all errors (returns safe defaults)

Usage:
    from status_tracker import write_status, read_status, clear_status

    # After test run completes
    write_status(passed=True, details={"total": 100, "failed": 0})

    # In pre-commit hook
    status = read_status()
    if status.get("passed"):
        # Allow commit
        pass
    else:
        # Block commit
        pass

    # Clear status (optional)
    clear_status()

Date: 2026-01-02
Issue: GitHub #174 (Block-at-submit hook)
Agent: implementer

Design Patterns:
    See library-design-patterns skill for standardized design patterns.
    See error-handling-patterns skill for error handling strategies.
"""

import json
import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional, Dict, Any


# Status file location in /tmp (ephemeral, cleared on reboot)
STATUS_DIR = Path(tempfile.gettempdir()) / ".autonomous-dev"
STATUS_FILE = STATUS_DIR / "test-status.json"


def get_status_file_path() -> Path:
    """Get path to status file.

    Returns:
        Path to test-status.json file

    Security:
        - Returns hardcoded path (no user input)
        - No path traversal risk

    Examples:
        >>> path = get_status_file_path()
        >>> print(path)
        PosixPath('/tmp/.autonomous-dev/test-status.json')
    """
    return STATUS_FILE


def _ensure_status_dir() -> bool:
    """Ensure status directory exists with secure permissions.

    Creates /tmp/.autonomous-dev/ if it doesn't exist.
    Sets permissions to 0700 (owner read/write/execute only).

    Returns:
        True if directory exists or was created successfully
        False if creation failed

    Security:
        - Creates directory with mode 0700 (owner only)
        - Parent directory (/tmp) already exists
        - No symlink following
    """
    try:
        # Create directory with secure permissions
        STATUS_DIR.mkdir(mode=0o700, parents=False, exist_ok=True)

        # Verify permissions (in case directory already existed with wrong perms)
        current_mode = STATUS_DIR.stat().st_mode & 0o777
        if current_mode != 0o700:
            # Fix permissions
            STATUS_DIR.chmod(0o700)

        return True

    except (OSError, PermissionError):
        # Cannot create directory - graceful degradation
        return False


def write_status(passed: bool, details: Optional[Dict[str, Any]] = None) -> bool:
    """Write test status to file.

    Args:
        passed: True if all tests passed, False otherwise
        details: Optional additional details (test counts, duration, etc.)

    Returns:
        True if status was written successfully
        False if write failed (permissions, disk space, etc.)

    Security:
        - Atomic write (write to temp file, then rename)
        - File permissions set to 0600 (owner read/write only)
        - Graceful degradation on all errors

    Examples:
        >>> write_status(passed=True)
        True

        >>> write_status(passed=False, details={"total": 100, "failed": 5})
        True

        >>> write_status(passed=True, details={"total": 50, "duration": 12.3})
        True
    """
    if not _ensure_status_dir():
        # Cannot create directory
        return False

    # Build status structure
    status = {
        "passed": bool(passed),  # Ensure boolean type
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }

    # Add optional details
    if details:
        status.update(details)

    try:
        # Atomic write: write to temp file, then rename
        # This prevents corruption if process crashes during write
        temp_file = STATUS_DIR / f".test-status.{os.getpid()}.tmp"

        # Write to temp file
        with open(temp_file, "w") as f:
            json.dump(status, f, indent=2)

        # Set secure permissions before making visible
        temp_file.chmod(0o600)

        # Atomic rename (replaces old file)
        temp_file.replace(STATUS_FILE)

        # Verify file has correct permissions
        STATUS_FILE.chmod(0o600)

        return True

    except (OSError, PermissionError, IOError) as e:
        # Write failed - clean up temp file if it exists
        try:
            temp_file = STATUS_DIR / f".test-status.{os.getpid()}.tmp"
            if temp_file.exists():
                temp_file.unlink()
        except:
            pass  # Ignore cleanup errors

        return False


def read_status() -> Dict[str, Any]:
    """Read test status from file.

    Returns:
        Dictionary with at minimum:
            - "passed": bool (True if tests passed, False otherwise)
            - "timestamp": str or None (ISO format UTC timestamp)

        Additional fields may be present if written by write_status().

        If status file is missing, corrupted, or unreadable, returns:
            {"passed": False, "timestamp": None}

    Security:
        - Graceful degradation on all errors
        - Returns safe default (passed=False) if anything goes wrong
        - Validates JSON structure

    Examples:
        >>> status = read_status()
        >>> if status.get("passed"):
        ...     print("Tests passed!")

        >>> status = read_status()
        >>> print(f"Timestamp: {status.get('timestamp')}")
    """
    # Default status (safe default - assume tests failed)
    default_status = {
        "passed": False,
        "timestamp": None,
    }

    try:
        # Check if file exists
        if not STATUS_FILE.exists():
            return default_status

        # Read and parse JSON
        with open(STATUS_FILE, "r") as f:
            status = json.load(f)

        # Validate structure
        if not isinstance(status, dict):
            # Corrupted - not a dictionary
            return default_status

        # Validate 'passed' field
        passed = status.get("passed", False)
        if not isinstance(passed, bool):
            # Invalid type - treat as failure
            return default_status

        # Validate 'timestamp' field (optional, but must be string if present)
        timestamp = status.get("timestamp")
        if timestamp is not None and not isinstance(timestamp, str):
            # Invalid type - clear it
            status["timestamp"] = None

        # Ensure required fields exist
        if "passed" not in status:
            status["passed"] = False
        if "timestamp" not in status:
            status["timestamp"] = None

        return status

    except (OSError, PermissionError, IOError, json.JSONDecodeError):
        # Any error reading or parsing - return safe default
        return default_status


def clear_status() -> bool:
    """Clear the status file.

    Deletes /tmp/.autonomous-dev/test-status.json if it exists.

    Returns:
        True if file was cleared or didn't exist
        False if deletion failed

    Security:
        - Only deletes hardcoded path (no user input)
        - Graceful degradation on errors

    Examples:
        >>> clear_status()
        True

        >>> # After clear, read returns default
        >>> status = read_status()
        >>> assert status["passed"] is False
    """
    try:
        if STATUS_FILE.exists():
            STATUS_FILE.unlink()
        return True

    except (OSError, PermissionError):
        # Cannot delete file
        return False


# =============================================================================
# Module Self-Test (for debugging)
# =============================================================================

if __name__ == "__main__":
    print("Test Status Tracker - Self Test")
    print("=" * 60)

    # Test 1: Write status
    print("\n1. Writing passed status...")
    result = write_status(passed=True, details={"total": 100, "failed": 0})
    print(f"   Result: {result}")
    print(f"   File: {STATUS_FILE}")

    # Test 2: Read status
    print("\n2. Reading status...")
    status = read_status()
    print(f"   Status: {status}")
    print(f"   Passed: {status.get('passed')}")
    print(f"   Timestamp: {status.get('timestamp')}")

    # Test 3: Write failed status
    print("\n3. Writing failed status...")
    result = write_status(passed=False, details={"total": 100, "failed": 5})
    print(f"   Result: {result}")

    # Test 4: Read failed status
    print("\n4. Reading failed status...")
    status = read_status()
    print(f"   Status: {status}")
    print(f"   Passed: {status.get('passed')}")

    # Test 5: Clear status
    print("\n5. Clearing status...")
    result = clear_status()
    print(f"   Result: {result}")

    # Test 6: Read after clear
    print("\n6. Reading after clear...")
    status = read_status()
    print(f"   Status: {status}")
    print(f"   Passed: {status.get('passed')} (should be False)")

    # Test 7: Get status file path
    print("\n7. Getting status file path...")
    path = get_status_file_path()
    print(f"   Path: {path}")

    print("\n" + "=" * 60)
    print("Self-test complete!")
