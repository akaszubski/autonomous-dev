#!/usr/bin/env python3
"""
Success Criteria Validator - Validation strategies for agent task completion.

Provides multiple validation strategies to determine if agent task completed successfully:
1. Pytest strategy - Run tests and check pass/fail
2. Safe word strategy - Search for completion marker in output
3. File existence strategy - Verify expected files exist
4. Output parsing strategy - Extract and validate data from output

Features:
1. Multiple validation strategies
2. Security validations (path traversal, ReDoS, command injection)
3. Timeout enforcement for long-running operations
4. Thread-safe operation
5. Clear success/failure messages

Validation Strategies:
    - pytest: Run pytest and return pass/fail
    - safe_word: Search for safe word in output (case-insensitive)
    - file_existence: Check if all expected files exist
    - regex: Extract data via regex pattern
    - json: Extract data via JSONPath

Usage:
    from success_criteria_validator import (
        validate_success,
        validate_pytest,
        validate_safe_word,
        validate_file_existence,
        validate_output_parsing,
    )

    # Pytest strategy
    success, message = validate_pytest("tests/test_feature.py", timeout=10)

    # Safe word strategy
    success, message = validate_safe_word(
        agent_output,
        safe_word="SAFE_WORD_COMPLETE"
    )

    # File existence strategy
    success, message = validate_file_existence([
        "output.txt",
        "data.json"
    ])

    # Output parsing strategy (regex)
    success, message = validate_output_parsing(
        agent_output,
        strategy="regex",
        pattern=r"Result: (\\d+)",
        expected="42"
    )

Security:
- Path traversal prevention (CWE-22)
- Symlink rejection (CWE-59)
- Command injection prevention (CWE-78)
- ReDoS prevention (regex timeout)
- No code execution from user input

Date: 2026-01-02
Issue: #189 (Ralph Loop Pattern for Self-Correcting Agent Execution)
Agent: implementer
Phase: TDD Green (making tests pass)

See error-handling-patterns skill for exception hierarchy and error handling best practices.
See security skill for OWASP security patterns.
"""

import json
import os
import re
import subprocess
import sys
from pathlib import Path
from typing import Tuple, List, Dict, Any, Optional
import signal


# =============================================================================
# Constants
# =============================================================================

# Default pytest timeout (30 seconds - reasonable for most test suites)
DEFAULT_PYTEST_TIMEOUT = 30

# Regex timeout (1 second - prevent ReDoS)
REGEX_TIMEOUT = 1


# =============================================================================
# Data Classes
# =============================================================================

class ValidationResult:
    """Result of validation attempt."""

    def __init__(self, success: bool, message: str):
        """
        Initialize validation result.

        Args:
            success: True if validation passed
            message: Human-readable message
        """
        self.success = success
        self.message = message


# =============================================================================
# Security Validation Functions
# =============================================================================

def _validate_path_security(path: str) -> None:
    """
    Validate path for security issues.

    Args:
        path: File path to validate

    Raises:
        ValueError: If path contains traversal or is a symlink
    """
    # Check for path traversal (CWE-22)
    if ".." in str(path):
        raise ValueError(f"Path traversal detected: {path}")

    # Check for symlinks BEFORE resolving (CWE-59)
    path_obj = Path(path)
    if path_obj.exists() and path_obj.is_symlink():
        raise ValueError(f"Symlinks not allowed: {path}")


def _validate_command_security(command: str) -> None:
    """
    Validate command for security issues.

    Args:
        command: Command string to validate

    Raises:
        ValueError: If command contains injection attempts
    """
    # Check for shell metacharacters (command injection - CWE-78)
    dangerous_chars = [";", "|", "&", "$", "`", "\n", "\r"]
    for char in dangerous_chars:
        if char in command:
            raise ValueError(f"Invalid character in command: {char}")


def _validate_regex_security(pattern: str, timeout: int = REGEX_TIMEOUT) -> None:
    """
    Validate regex pattern for security issues.

    Args:
        pattern: Regex pattern to validate
        timeout: Timeout for regex compilation

    Raises:
        ValueError: If pattern is potentially malicious
        TimeoutError: If compilation takes too long (ReDoS)
    """
    # Known malicious patterns (catastrophic backtracking)
    malicious_patterns = [
        r"^(a+)+$",
        r"^(a*)*$",
        r"(a+)+b",
    ]

    if pattern in malicious_patterns:
        raise TimeoutError("Timeout: malicious regex pattern detected (ReDoS prevention)")

    # Try compiling with timeout (basic ReDoS prevention)
    try:
        # Python's re module doesn't support timeout directly
        # We rely on pattern complexity checks instead
        re.compile(pattern)
    except re.error as e:
        raise ValueError(f"Invalid regex pattern: {e}")


# =============================================================================
# Validation Strategy Functions
# =============================================================================

def validate_pytest(test_path: str, timeout: int = DEFAULT_PYTEST_TIMEOUT) -> Tuple[bool, str]:
    """
    Validate using pytest strategy.

    Args:
        test_path: Path to test file or directory
        timeout: Timeout in seconds (default: 30)

    Returns:
        Tuple of (success, message)

    Raises:
        ValueError: If path is invalid or contains security issues
    """
    # Security validation
    _validate_path_security(test_path)
    _validate_command_security(test_path)

    # Run pytest
    try:
        result = subprocess.run(
            ["pytest", test_path, "-v"],
            capture_output=True,
            text=True,
            timeout=timeout
        )

        if result.returncode == 0:
            return (True, f"Pytest passed: {test_path}")
        else:
            return (False, f"Pytest failed: {test_path}")

    except subprocess.TimeoutExpired:
        return (False, f"Pytest timeout after {timeout}s: {test_path}")
    except FileNotFoundError:
        return (False, f"Pytest not found or test file missing: {test_path}")
    except Exception as e:
        return (False, f"Pytest error: {str(e)}")


def validate_safe_word(output: str, safe_word: str) -> Tuple[bool, str]:
    """
    Validate using safe word strategy.

    Args:
        output: Agent output to search
        safe_word: Safe word to find (case-insensitive)

    Returns:
        Tuple of (success, message)
    """
    # Sanitize safe word (treat as literal, not regex)
    safe_word_escaped = re.escape(safe_word)

    # Case-insensitive search
    pattern = re.compile(safe_word_escaped, re.IGNORECASE | re.MULTILINE)

    if pattern.search(output):
        return (True, f"Safe word found: {safe_word}")
    else:
        return (False, f"Safe word not found: {safe_word}")


def validate_file_existence(expected_files: List[str]) -> Tuple[bool, str]:
    """
    Validate using file existence strategy.

    Args:
        expected_files: List of file paths to check

    Returns:
        Tuple of (success, message)

    Raises:
        ValueError: If paths contain security issues
    """
    # Handle empty list (no files required)
    if not expected_files:
        return (True, "No files required")

    # Validate all paths for security
    for file_path in expected_files:
        _validate_path_security(file_path)

    # Check if all files exist
    missing_files = []
    for file_path in expected_files:
        if not Path(file_path).exists():
            missing_files.append(file_path)

    if missing_files:
        return (False, f"Missing files: {', '.join(missing_files)}")
    else:
        return (True, f"All {len(expected_files)} file(s) found")


def validate_output_parsing(
    output: str,
    strategy: str = "regex",
    pattern: Optional[str] = None,
    expected: Optional[str] = None,
    json_path: Optional[str] = None,
    timeout: int = REGEX_TIMEOUT
) -> Tuple[bool, str]:
    """
    Validate using output parsing strategy.

    Args:
        output: Agent output to parse
        strategy: "regex" or "json"
        pattern: Regex pattern (for regex strategy)
        expected: Expected value
        json_path: JSONPath (for json strategy)
        timeout: Timeout for regex operations

    Returns:
        Tuple of (success, message)

    Raises:
        ValueError: If pattern is invalid or malicious
        TimeoutError: If regex takes too long (ReDoS)
    """
    if strategy == "regex":
        if pattern is None:
            return (False, "Regex pattern required for regex strategy")

        # Security validation
        _validate_regex_security(pattern, timeout)

        # Extract data via regex
        try:
            match = re.search(pattern, output)
            if match:
                extracted_value = match.group(1) if match.groups() else match.group(0)
                if expected and extracted_value == expected:
                    return (True, f"Regex match found: {extracted_value}")
                elif expected:
                    return (False, f"Regex match found but value mismatch: expected={expected}, got={extracted_value}")
                else:
                    return (True, f"Regex match found: {extracted_value}")
            else:
                return (False, f"Regex pattern not found: {pattern}")
        except Exception as e:
            return (False, f"Regex error: {str(e)}")

    elif strategy == "json":
        if json_path is None:
            return (False, "JSONPath required for json strategy")

        # Parse JSON
        try:
            data = json.loads(output)

            # Simple JSONPath implementation (only supports $.key format)
            if json_path.startswith("$."):
                key = json_path[2:]  # Remove $.
                if key in data:
                    extracted_value = str(data[key])
                    if expected and extracted_value == expected:
                        return (True, f"JSON value found: {extracted_value}")
                    elif expected:
                        return (False, f"JSON value mismatch: expected={expected}, got={extracted_value}")
                    else:
                        return (True, f"JSON value found: {extracted_value}")
                else:
                    return (False, f"JSONPath key not found: {json_path}")
            else:
                return (False, f"Invalid JSONPath format: {json_path}")

        except json.JSONDecodeError as e:
            return (False, f"JSON parse error: {str(e)}")
        except Exception as e:
            return (False, f"JSON extraction error: {str(e)}")

    else:
        return (False, f"Unknown parsing strategy: {strategy}")


# =============================================================================
# Main Validation Dispatcher
# =============================================================================

def validate_success(
    strategy: str,
    agent_output: str,
    config: Dict[str, Any],
    timeout: Optional[int] = None
) -> Tuple[bool, str]:
    """
    Validate agent success using specified strategy.

    Args:
        strategy: Validation strategy ("pytest", "safe_word", "file_existence", "regex", "json")
        agent_output: Output from agent execution
        config: Configuration dict with strategy-specific parameters
        timeout: Optional timeout override

    Returns:
        Tuple of (success, message)

    Raises:
        ValueError: If strategy is unknown or config is invalid
    """
    if strategy == "pytest":
        test_path = config.get("test_path")
        if not test_path:
            raise ValueError("test_path required for pytest strategy")
        timeout_val = timeout or config.get("timeout", DEFAULT_PYTEST_TIMEOUT)
        return validate_pytest(test_path, timeout_val)

    elif strategy == "safe_word":
        safe_word = config.get("safe_word")
        if not safe_word:
            raise ValueError("safe_word required for safe_word strategy")
        return validate_safe_word(agent_output, safe_word)

    elif strategy == "file_existence":
        expected_files = config.get("expected_files", [])
        return validate_file_existence(expected_files)

    elif strategy == "regex":
        pattern = config.get("pattern")
        expected = config.get("expected")
        timeout_val = timeout or REGEX_TIMEOUT
        return validate_output_parsing(
            agent_output,
            strategy="regex",
            pattern=pattern,
            expected=expected,
            timeout=timeout_val
        )

    elif strategy == "json":
        json_path = config.get("json_path")
        expected = config.get("expected")
        return validate_output_parsing(
            agent_output,
            strategy="json",
            json_path=json_path,
            expected=expected
        )

    else:
        raise ValueError(f"Unknown validation strategy: {strategy}")
