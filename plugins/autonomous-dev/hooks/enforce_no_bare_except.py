#!/usr/bin/env -S uv run --script --quiet --no-project
# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""
Enforce No Bare Except Clauses - Pre-commit Hook

Prevents bare `except:` clauses from being committed to version control.

Problem:
Bare except clauses catch ALL exceptions, including system exits, keyboard interrupts,
and memory errors. This can mask bugs and make debugging difficult.

Bad Pattern:
    try:
        risky_operation()
    except:  # Catches EVERYTHING, including SystemExit
        handle_error()

Good Patterns:
    try:
        risky_operation()
    except Exception as e:  # Catches most errors, but not system exceptions
        handle_error(e)

    try:
        risky_operation()
    except ValueError as e:  # Specific exception handling
        handle_error(e)

Solution:
PreCommit hook that:
1. Scans all staged Python files for bare `except:` clauses
2. Exits with EXIT_SUCCESS (0) if none found
3. Exits with EXIT_BLOCK (2) if found (blocks commit)
4. Shows file:line for each occurrence
5. Excludes common directories (.venv, __pycache__, etc.)
6. Can be disabled via ENFORCE_NO_BARE_EXCEPT=false environment variable

Hook Integration:
- Event: PreCommit (before git commit)
- Trigger: git commit command
- Action: Check Python files for bare except clauses
- Lifecycle: PreCommit (can block with EXIT_BLOCK)

Exit Codes:
- EXIT_SUCCESS (0): No bare except clauses found, allow commit
- EXIT_BLOCK (2): Bare except clauses found, block commit

Environment Variables:
- ENFORCE_NO_BARE_EXCEPT: Set to "false" or "0" to disable check

Date: 2026-01-17
Feature: Prevent bare except clauses in committed code
Phase: Implementation (TDD Green)

Design Patterns:
    See hook-patterns skill for hook lifecycle and exit codes.
    See python-standards skill for exception handling best practices.
"""

import ast
import os
import re
import subprocess
import sys
from pathlib import Path
from typing import List, Tuple


# Add lib directory to path for imports
def is_running_under_uv() -> bool:
    """Detect if script is running under UV."""
    return "UV_PROJECT_ENVIRONMENT" in os.environ


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

# Environment variable to disable check
ENV_VAR_ENFORCE = "ENFORCE_NO_BARE_EXCEPT"

# Directories to exclude from scanning
EXCLUDED_DIRS = {
    ".venv",
    "venv",
    "__pycache__",
    ".git",
    ".tox",
    "node_modules",
    "build",
    "dist",
    ".eggs",
    "*.egg-info",
}


# =============================================================================
# Core Functions
# =============================================================================


def should_enforce_check() -> bool:
    """
    Check if bare except check should be enforced.

    The check is enforced by default. It can be disabled by setting
    ENFORCE_NO_BARE_EXCEPT environment variable to:
    - "false" or "False" or "FALSE"
    - "0"
    - "" (empty string)

    Returns:
        True if check should be enforced, False otherwise

    Examples:
        >>> os.environ["ENFORCE_NO_BARE_EXCEPT"] = "false"
        >>> should_enforce_check()
        False

        >>> os.environ.pop("ENFORCE_NO_BARE_EXCEPT", None)
        >>> should_enforce_check()
        True
    """
    value = os.environ.get(ENV_VAR_ENFORCE, "true")

    # Normalize to lowercase for case-insensitive comparison
    value_lower = value.lower().strip()

    # Values that disable the check
    disable_values = ["false", "0", ""]

    return value_lower not in disable_values


def get_staged_python_files() -> List[Path]:
    """
    Get list of staged Python files from git.

    Returns:
        List of Path objects for staged .py files

    Raises:
        subprocess.CalledProcessError: If git command fails
    """
    try:
        # Get list of staged files
        result = subprocess.run(
            ["git", "diff", "--cached", "--name-only", "--diff-filter=ACM"],
            capture_output=True,
            text=True,
            check=True,
        )

        # Filter for Python files and create Path objects
        staged_files = []
        for line in result.stdout.strip().split("\n"):
            if line and line.endswith(".py"):
                file_path = Path(line)
                # Exclude files in excluded directories
                if not any(excluded in file_path.parts for excluded in EXCLUDED_DIRS):
                    if file_path.exists():
                        staged_files.append(file_path)

        return staged_files

    except subprocess.CalledProcessError:
        # Git command failed - assume no staged files
        return []


def find_bare_except_clauses(file_path: Path) -> List[int]:
    """
    Find line numbers of bare except clauses in a Python file using AST.

    A bare except clause is an except statement with no exception type specified.

    Args:
        file_path: Path to Python file to check

    Returns:
        List of line numbers where bare except clauses are found

    Examples:
        >>> # File with bare except at line 10
        >>> lines = find_bare_except_clauses(Path("example.py"))
        >>> assert 10 in lines
    """
    bare_except_lines = []

    try:
        source = file_path.read_text(encoding="utf-8")
        tree = ast.parse(source, filename=str(file_path))

        # Walk the AST to find ExceptHandler nodes
        for node in ast.walk(tree):
            if isinstance(node, ast.ExceptHandler):
                # Bare except has no type specified
                if node.type is None:
                    bare_except_lines.append(node.lineno)

    except SyntaxError:
        # Syntax error in file - skip (will be caught by other tools)
        pass
    except Exception:
        # Any other exception - skip gracefully
        pass

    return bare_except_lines


def check_all_staged_files() -> Tuple[bool, List[Tuple[Path, int]]]:
    """
    Check all staged Python files for bare except clauses.

    Returns:
        Tuple of (success, violations) where:
        - success: True if no violations found, False otherwise
        - violations: List of (file_path, line_number) tuples
    """
    staged_files = get_staged_python_files()
    violations = []

    for file_path in staged_files:
        bare_except_lines = find_bare_except_clauses(file_path)
        for line_num in bare_except_lines:
            violations.append((file_path, line_num))

    return len(violations) == 0, violations


def format_error_message(violations: List[Tuple[Path, int]]) -> str:
    """
    Generate clear error message for commit rejection.

    Args:
        violations: List of (file_path, line_number) tuples

    Returns:
        Multi-line error message explaining the issue and remediation
    """
    message = """
╔════════════════════════════════════════════════════════════════════════╗
║                         COMMIT BLOCKED                                  ║
╚════════════════════════════════════════════════════════════════════════╝

Bare except clauses detected in staged files.

Violations found:
"""

    # Add each violation
    for file_path, line_num in sorted(violations):
        message += f"  - {file_path}:{line_num}\n"

    message += """
Why this matters:
- Bare except clauses catch ALL exceptions, including SystemExit
- This can mask critical bugs and make debugging difficult
- Specific exception handling improves code quality

How to fix:
Replace bare except clauses with specific exception types:

  Bad:
    try:
        risky_operation()
    except:  # Catches EVERYTHING
        handle_error()

  Good:
    try:
        risky_operation()
    except Exception as e:  # Catches most errors, not system exceptions
        handle_error(e)

  Better:
    try:
        risky_operation()
    except ValueError as e:  # Specific exception handling
        handle_error(e)

To bypass this check (NOT RECOMMENDED):

    ENFORCE_NO_BARE_EXCEPT=false git commit

For more information, see:
- Python PEP 8: https://pep8.org/#programming-recommendations
- docs/python-standards.md (Exception Handling section)
"""

    return message.strip()


def main() -> None:
    """
    Main entry point for enforce_no_bare_except hook.

    Exit Codes:
        EXIT_SUCCESS (0): No bare except clauses found, allow commit
        EXIT_BLOCK (2): Bare except clauses found, block commit

    Environment Variables:
        ENFORCE_NO_BARE_EXCEPT: Set to "false" or "0" to bypass check
    """
    # Check if enforcement is enabled
    if not should_enforce_check():
        # Check disabled - allow commit
        sys.exit(EXIT_SUCCESS)

    # Check all staged Python files
    success, violations = check_all_staged_files()

    if success:
        # No violations found - allow commit
        sys.exit(EXIT_SUCCESS)
    else:
        # Violations found - block commit

        # Print error message
        try:
            print(format_error_message(violations), file=sys.stderr)
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
