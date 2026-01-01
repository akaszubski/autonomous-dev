#!/usr/bin/env python3
"""
Pre-Commit Gate - Enforces test passage before git commit.

This hook blocks git commits when tests have failed or haven't been run,
ensuring that broken code doesn't enter version control.

Problem:
Developers may skip tests in rush to commit:
- Tests may be skipped to save time
- Broken code gets into version control
- CI/CD catches issues too late
- Wastes team time on broken builds

Solution:
PreCommit hook that:
1. Reads test status from test_status_tracker
2. Exits with EXIT_SUCCESS (0) if tests passed
3. Exits with EXIT_BLOCK (2) if tests failed or status missing
4. Can be disabled via ENFORCE_TEST_GATE=false environment variable
5. Provides clear error messages with remediation steps

Hook Integration:
- Event: PreCommit (before git commit)
- Trigger: git commit command
- Action: Check test status, block if failed
- Lifecycle: PreCommit (can block with EXIT_BLOCK)

Exit Codes:
- EXIT_SUCCESS (0): Tests passed, allow commit
- EXIT_BLOCK (2): Tests failed or not run, block commit

Environment Variables:
- ENFORCE_TEST_GATE: Set to "false" or "0" to disable gate (emergency bypass)

Date: 2026-01-01
Feature: Block-at-submit hook with test status tracking
Agent: implementer
Phase: Implementation (TDD Green)

Design Patterns:
    See hook-patterns skill for hook lifecycle and exit codes.
    See library-design-patterns skill for error handling patterns.
"""

import os
import sys
from pathlib import Path
from typing import Dict, Any, Tuple


# Add lib directory to path for imports
lib_path = Path(__file__).parent.parent / "lib"
if lib_path.exists() and str(lib_path) not in sys.path:
    sys.path.insert(0, str(lib_path))

# Import exit codes
try:
    from hook_exit_codes import EXIT_SUCCESS, EXIT_BLOCK
except ImportError:
    # Fallback if module not available
    EXIT_SUCCESS = 0
    EXIT_BLOCK = 2


# =============================================================================
# Configuration
# =============================================================================

# Environment variable to disable gate (emergency bypass)
ENV_VAR_ENFORCE = "ENFORCE_TEST_GATE"


# =============================================================================
# Core Functions
# =============================================================================

def should_enforce_gate() -> bool:
    """
    Check if test gate should be enforced.

    The gate is enforced by default. It can be disabled by setting
    ENFORCE_TEST_GATE environment variable to:
    - "false" or "False" or "FALSE"
    - "0"
    - "" (empty string)

    Returns:
        True if gate should be enforced, False otherwise

    Examples:
        >>> os.environ["ENFORCE_TEST_GATE"] = "false"
        >>> should_enforce_gate()
        False

        >>> os.environ.pop("ENFORCE_TEST_GATE", None)
        >>> should_enforce_gate()
        True
    """
    value = os.environ.get(ENV_VAR_ENFORCE, "true")

    # Normalize to lowercase for case-insensitive comparison
    value_lower = value.lower().strip()

    # Values that disable the gate
    disable_values = ["false", "0", ""]

    return value_lower not in disable_values


def check_test_status() -> bool:
    """
    Check current test execution status.

    Reads status from test_status_tracker and determines if tests passed.

    Returns:
        True if tests passed, False otherwise

    Graceful Degradation:
        - Tracker unavailable: Returns False (safe default)
        - Tracker raises exception: Returns False (safe default)
        - Status missing 'passed' field: Returns False (safe default)
        - Invalid 'passed' type: Returns False (safe default)

    Examples:
        >>> # After successful test run
        >>> check_test_status()
        True

        >>> # After failed test run or no tests
        >>> check_test_status()
        False
    """
    try:
        # Dynamic import for testability (allows mocking via sys.modules)
        from test_status_tracker import read_status

        # Read status from tracker
        status = read_status()

        # Validate status structure
        if not isinstance(status, dict):
            return False

        # Check 'passed' field
        passed = status.get("passed", False)

        # Validate type (must be boolean)
        if not isinstance(passed, bool):
            return False

        return passed

    except ImportError:
        # Tracker module not available - treat as tests not run
        return False
    except Exception:
        # Any exception during status check = treat as failure (safe default)
        return False


def get_error_message(passed: bool, has_status: bool) -> str:
    """
    Generate clear error message for commit rejection.

    Args:
        passed: Whether tests passed (False in error cases)
        has_status: Whether status file exists

    Returns:
        Multi-line error message explaining the issue and remediation

    Examples:
        >>> msg = get_error_message(False, True)
        >>> assert "failed" in msg.lower()

        >>> msg = get_error_message(False, False)
        >>> assert "run" in msg.lower()
    """
    if not has_status:
        # Status file missing - tests haven't been run
        return """
╔════════════════════════════════════════════════════════════════════════╗
║                         COMMIT BLOCKED                                  ║
╚════════════════════════════════════════════════════════════════════════╝

Tests have not been run yet.

Before committing, you must run the test suite:

    pytest

Once tests pass, you can commit:

    git commit

To bypass this check (NOT RECOMMENDED):

    ENFORCE_TEST_GATE=false git commit

Why this matters:
- Prevents broken code from entering version control
- Catches bugs before they reach CI/CD
- Saves team time on debugging
- Maintains code quality standards

""".strip()

    else:
        # Status file exists but tests failed
        return """
╔════════════════════════════════════════════════════════════════════════╗
║                         COMMIT BLOCKED                                  ║
╚════════════════════════════════════════════════════════════════════════╝

Tests are failing.

Fix failing tests before committing:

    pytest  # Run tests and fix failures

Once all tests pass, you can commit:

    git commit

To bypass this check (NOT RECOMMENDED):

    ENFORCE_TEST_GATE=false git commit

Why this matters:
- Prevents broken code from entering version control
- Catches bugs before they reach CI/CD
- Saves team time on debugging
- Maintains code quality standards

""".strip()


def main() -> None:
    """
    Main entry point for pre-commit gate hook.

    Exit Codes:
        EXIT_SUCCESS (0): Tests passed, allow commit
        EXIT_BLOCK (2): Tests failed or not run, block commit

    Environment Variables:
        ENFORCE_TEST_GATE: Set to "false" or "0" to bypass gate
    """
    # Check if gate should be enforced
    if not should_enforce_gate():
        # Gate disabled - allow commit
        sys.exit(EXIT_SUCCESS)

    # Read test status (single read for both check and error message)
    try:
        from test_status_tracker import read_status
        status = read_status()
    except (ImportError, Exception):
        # Tracker unavailable - treat as tests not run
        status = {"passed": False, "timestamp": None}

    # Validate status structure
    if not isinstance(status, dict):
        status = {"passed": False, "timestamp": None}

    # Check if tests passed
    passed = status.get("passed", False)
    if not isinstance(passed, bool):
        passed = False

    if passed:
        # Tests passed - allow commit
        sys.exit(EXIT_SUCCESS)

    else:
        # Tests failed or not run - block commit

        # Determine if status file exists (for better error message)
        has_status = status.get("timestamp") is not None

        # Print error message
        try:
            print(get_error_message(passed=False, has_status=has_status), file=sys.stderr)
        except IOError:
            # Printing failed (stdout/stderr unavailable) - still block
            pass

        # Block commit
        sys.exit(EXIT_BLOCK)


# =============================================================================
# Entry Point
# =============================================================================

if __name__ == "__main__":
    main()
