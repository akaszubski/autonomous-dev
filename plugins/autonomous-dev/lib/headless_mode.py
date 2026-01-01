#!/usr/bin/env python3
"""
Headless Mode - CI/CD integration support for autonomous development

Issue: GitHub #176 (Headless mode for CI/CD integration)

This module provides utilities for running autonomous development workflows
in headless/CI environments without interactive prompts.

Features:
- Detect headless mode via --headless flag or CI environment
- Skip interactive prompts in headless mode
- Format JSON output for machine parsing
- Map statuses to exit codes for CI/CD pipelines
- Auto-configure git automation for headless environments

Exit Codes:
- 0: success
- 1: generic error
- 2: alignment_failed
- 3: tests_failed
- 4: security_failed
- 5: timeout

Example:
    >>> from headless_mode import is_headless_mode, format_json_output
    >>> if is_headless_mode():
    ...     print(format_json_output("success", {"feature": "implemented"}))
    {"status": "success", "feature": "implemented"}
"""

import json
import os
import sys
from typing import Optional, Dict, Any


def detect_headless_flag() -> bool:
    """
    Detect if --headless flag is present in sys.argv.

    Returns:
        bool: True if --headless flag is present (case-sensitive, exact match)

    Example:
        >>> import sys
        >>> sys.argv = ["script.py", "--headless"]
        >>> detect_headless_flag()
        True
        >>> sys.argv = ["script.py", "--Headless"]  # Case-sensitive
        >>> detect_headless_flag()
        False
    """
    return "--headless" in sys.argv


def detect_ci_environment() -> bool:
    """
    Detect if running in a CI/CD environment.

    Checks for common CI environment variables:
    - CI=true (case-insensitive)
    - GITHUB_ACTIONS=true (case-insensitive)
    - GITLAB_CI=true (case-insensitive)
    - CIRCLECI=true (case-insensitive)
    - TRAVIS=true (case-insensitive)
    - JENKINS_HOME=/path (any non-empty value)

    Returns:
        bool: True if any CI environment variable is detected

    Example:
        >>> import os
        >>> os.environ["CI"] = "true"
        >>> detect_ci_environment()
        True
    """
    ci_vars = ["CI", "GITHUB_ACTIONS", "GITLAB_CI", "CIRCLECI", "TRAVIS"]

    # Check for truthy values (case-insensitive)
    for var in ci_vars:
        value = os.environ.get(var, "").lower()
        if value in ("true", "1"):
            return True

    # Check JENKINS_HOME (any non-empty value)
    if os.environ.get("JENKINS_HOME"):
        return True

    return False


def is_headless_mode() -> bool:
    """
    Determine if running in headless mode.

    Headless mode is enabled if:
    1. --headless flag is present, OR
    2. CI environment detected AND not TTY, OR
    3. Not TTY (stdin is not a terminal)

    Returns:
        bool: True if headless mode is active

    Example:
        >>> import sys
        >>> sys.argv = ["script.py", "--headless"]
        >>> is_headless_mode()
        True
    """
    # Check for explicit --headless flag
    if detect_headless_flag():
        return True

    # Check if stdin is a TTY
    is_tty = sys.stdin.isatty()

    # CI environment AND not TTY
    if detect_ci_environment() and not is_tty:
        return True

    # Not TTY (regardless of CI)
    if not is_tty:
        return True

    return False


def should_skip_prompts() -> bool:
    """
    Determine if interactive prompts should be skipped.

    Returns:
        bool: True if prompts should be skipped (same as is_headless_mode())

    Example:
        >>> import sys
        >>> sys.argv = ["script.py", "--headless"]
        >>> should_skip_prompts()
        True
    """
    return is_headless_mode()


def format_json_output(
    status: str, data: Optional[Dict[str, Any]] = None, error: Optional[str] = None
) -> str:
    """
    Format output as JSON for machine parsing.

    Args:
        status: Status string ("success" or "error")
        data: Optional data dictionary to include in output
        error: Optional error message (only for error status)

    Returns:
        str: JSON-formatted string

    Example:
        >>> format_json_output("success", {"feature": "implemented"})
        '{"status": "success", "feature": "implemented"}'
        >>> format_json_output("error", error="Tests failed")
        '{"status": "error", "error": "Tests failed"}'
    """
    output = {"status": status}

    if data:
        output.update(data)

    if error:
        output["error"] = error

    return json.dumps(output)


def get_exit_code(status: str, error_type: Optional[str] = None) -> int:
    """
    Map status/error_type to exit code for CI/CD pipelines.

    Exit Codes:
    - 0: success
    - 1: generic error
    - 2: alignment_failed
    - 3: tests_failed
    - 4: security_failed
    - 5: timeout

    Args:
        status: Status string ("success" or "error")
        error_type: Optional error type for specific exit codes

    Returns:
        int: Exit code (0-5)

    Example:
        >>> get_exit_code("success")
        0
        >>> get_exit_code("error", "tests_failed")
        3
        >>> get_exit_code("error")
        1
    """
    if status == "success":
        return 0

    # Map error types to exit codes
    error_codes = {
        "alignment_failed": 2,
        "tests_failed": 3,
        "security_failed": 4,
        "timeout": 5,
    }

    return error_codes.get(error_type, 1)  # Default to 1 for generic errors


def configure_auto_git_for_headless() -> Dict[str, str]:
    """
    Configure AUTO_GIT environment variables for headless mode.

    Sets environment variables if not already set:
    - AUTO_GIT_ENABLED: "true" (enable git automation)
    - AUTO_GIT_PUSH: "true" (auto-push commits)
    - AUTO_GIT_PR: "false" (no auto-PR, requires manual review)

    Does NOT override existing values.

    Returns:
        dict: Dictionary of configured values

    Example:
        >>> import os
        >>> os.environ.pop("AUTO_GIT_ENABLED", None)
        >>> config = configure_auto_git_for_headless()
        >>> config["AUTO_GIT_ENABLED"]
        'true'
        >>> os.environ["AUTO_GIT_ENABLED"]
        'true'
    """
    config = {}

    # Set AUTO_GIT_ENABLED if not already set
    if "AUTO_GIT_ENABLED" not in os.environ:
        os.environ["AUTO_GIT_ENABLED"] = "true"
        config["AUTO_GIT_ENABLED"] = "true"
    else:
        config["AUTO_GIT_ENABLED"] = os.environ["AUTO_GIT_ENABLED"]

    # Set AUTO_GIT_PUSH if not already set
    if "AUTO_GIT_PUSH" not in os.environ:
        os.environ["AUTO_GIT_PUSH"] = "true"
        config["AUTO_GIT_PUSH"] = "true"
    else:
        config["AUTO_GIT_PUSH"] = os.environ["AUTO_GIT_PUSH"]

    # Set AUTO_GIT_PR if not already set
    if "AUTO_GIT_PR" not in os.environ:
        os.environ["AUTO_GIT_PR"] = "false"
        config["AUTO_GIT_PR"] = "false"
    else:
        config["AUTO_GIT_PR"] = os.environ["AUTO_GIT_PR"]

    return config
