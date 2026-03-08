#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# ///
"""
Pre-commit hook to block print statements in production code.

Enforces using proper logging instead of print statements to ensure:
- Centralized log management
- Proper log levels (debug, info, warning, error)
- Production debugging capability
- Audit trail compliance

Exit codes:
  0: No print statements found (or enforcement disabled)
  2: Print statements found (blocks commit)

Environment Variables:
  ENFORCE_LOGGING_ONLY: Enable enforcement (default: false)
    Values: "true", "yes", "1" enable; anything else disables
  ALLOW_PRINT_IN_CLI: Allow print in CLI tools (default: true)
    CLI files detected by: argparse, click, typer, if __name__
  ALLOW_PRINT_IN_TESTS: Allow print in tests/ directory (default: true)

Usage:
  # Run manually
  python hooks/enforce_logging_only.py

  # Pre-commit hook (auto via settings.json)
  git commit -m "message"

  # Enable enforcement
  ENFORCE_LOGGING_ONLY=true git commit -m "message"

Security:
  - CWE-117 prevention: Proper logging prevents log injection
  - No shell=True usage
  - Read-only file operations

Author: implementer agent
Date: 2026-01-18
Related: Issue #236 - Logging enforcement hook
"""

import os
import re
import sys
from pathlib import Path
from typing import List, Tuple


# Print statement pattern - matches print( at start of line (with optional whitespace)
PRINT_PATTERN = re.compile(r"^\s*print\s*\(", re.MULTILINE)

# Directories to exclude from checking
EXCLUDED_DIRS = {".venv", "__pycache__", "node_modules", ".git", "archived"}

# CLI indicators - files containing these are CLI tools and can use print
CLI_INDICATORS = {"argparse", "click", "typer", 'if __name__ == "__main__"', "if __name__ == '__main__'"}

# Allowed print patterns (logging-like prints, debug prints, etc.)
ALLOWED_PATTERNS = [
    re.compile(r"^\s*print\s*\(\s*f?['\"].DEBUG"),       # [DEBUG] prefix
    re.compile(r"^\s*print\s*\(\s*f?['\"].INFO"),        # [INFO] prefix
    re.compile(r"^\s*print\s*\(\s*f?['\"].WARN"),        # [WARN] prefix
    re.compile(r"^\s*print\s*\(\s*f?['\"].ERROR"),       # [ERROR] prefix
    re.compile(r"^\s*#.*print"),                          # Commented out print
]


def _is_enabled() -> bool:
    """Check if enforcement is enabled via environment variable.

    Returns:
        True if ENFORCE_LOGGING_ONLY is set to true/yes/1 (case-insensitive)
    """
    env_value = os.getenv("ENFORCE_LOGGING_ONLY", "").strip().lower()
    return env_value in ("true", "yes", "1")


def _allow_print_in_cli() -> bool:
    """Check if print is allowed in CLI tools.

    Returns:
        True if ALLOW_PRINT_IN_CLI is true (default) or not set
    """
    env_value = os.getenv("ALLOW_PRINT_IN_CLI", "true").strip().lower()
    return env_value in ("true", "yes", "1")


def _allow_print_in_tests() -> bool:
    """Check if print is allowed in test files.

    Returns:
        True if ALLOW_PRINT_IN_TESTS is true (default) or not set
    """
    env_value = os.getenv("ALLOW_PRINT_IN_TESTS", "true").strip().lower()
    return env_value in ("true", "yes", "1")


def _is_excluded_path(filepath: Path) -> bool:
    """Check if file path is in excluded directory.

    Args:
        filepath: Path to check

    Returns:
        True if path contains any excluded directory
    """
    parts = filepath.parts
    return any(excluded in parts for excluded in EXCLUDED_DIRS)


def _is_test_file(filepath: Path) -> bool:
    """Check if file is a test file.

    Args:
        filepath: Path to check

    Returns:
        True if file is in tests/ directory or named test_*.py
    """
    parts = filepath.parts
    return "tests" in parts or filepath.name.startswith("test_")


def _is_cli_file(content: str) -> bool:
    """Check if file content indicates a CLI tool.

    Args:
        content: File content to check

    Returns:
        True if file contains CLI indicators (argparse, click, typer, main guard)
    """
    return any(indicator in content for indicator in CLI_INDICATORS)


def _is_allowed_print(line: str) -> bool:
    """Check if print statement matches allowed patterns.

    Args:
        line: Line to check

    Returns:
        True if print matches an allowed pattern (commented, has log prefix, etc.)
    """
    return any(pattern.match(line) for pattern in ALLOWED_PATTERNS)


def check_file(filepath: Path) -> List[Tuple[str, int, str]]:
    """Check file for print statements.

    Args:
        filepath: Path to Python file to check

    Returns:
        List of (filepath, line_number, line_content) tuples for violations

    Examples:
        >>> issues = check_file(Path("lib/example.py"))
        >>> if issues:
        ...     print(f"Found {len(issues)} print statements")
    """
    try:
        content = filepath.read_text(encoding="utf-8")
    except (IOError, OSError, UnicodeDecodeError):
        return []

    # Allow prints in CLI tools
    if _allow_print_in_cli() and _is_cli_file(content):
        return []

    issues: List[Tuple[str, int, str]] = []
    lines = content.split("\n")

    for i, line in enumerate(lines, 1):
        # Check if line has print statement
        if PRINT_PATTERN.match(line):
            # Skip allowed patterns
            if not _is_allowed_print(line):
                issues.append((str(filepath), i, line.strip()))

    return issues


def scan_directory(directory: Path) -> List[Tuple[str, int, str]]:
    """Scan directory for Python files with print statements.

    Args:
        directory: Root directory to scan

    Returns:
        List of all violations found
    """
    all_issues: List[Tuple[str, int, str]] = []

    if not directory.exists():
        return all_issues

    for py_file in directory.rglob("*.py"):
        # Skip excluded directories
        if _is_excluded_path(py_file):
            continue

        # Skip test files if allowed
        if _allow_print_in_tests() and _is_test_file(py_file):
            continue

        issues = check_file(py_file)
        all_issues.extend(issues)

    return all_issues


def main() -> int:
    """Main entry point for pre-commit hook.

    Returns:
        0 if no issues or enforcement disabled
        2 if print statements found (blocks commit)
    """
    # Check if enforcement is enabled
    if not _is_enabled():
        return 0

    # Find project root
    project_root = Path.cwd()
    for _ in range(10):
        if (project_root / ".git").exists() or (project_root / ".claude").exists():
            break
        if project_root.parent == project_root:
            break
        project_root = project_root.parent

    # Directories to scan for print statements
    scan_dirs = [
        project_root / "plugins" / "autonomous-dev" / "lib",
        project_root / "plugins" / "autonomous-dev" / "hooks",
        project_root / ".claude" / "lib",
        project_root / ".claude" / "hooks",
    ]

    all_issues: List[Tuple[str, int, str]] = []

    for scan_dir in scan_dirs:
        issues = scan_directory(scan_dir)
        all_issues.extend(issues)

    if all_issues:
        print("ERROR: Print statements found in production code:")
        print()

        # Show first 10 issues
        for filepath, line_num, line_content in all_issues[:10]:
            # Make path relative to project root
            try:
                rel_path = Path(filepath).relative_to(project_root)
            except ValueError:
                rel_path = Path(filepath)
            print(f"  {rel_path}:{line_num}: {line_content[:60]}...")

        if len(all_issues) > 10:
            print(f"\n  ... and {len(all_issues) - 10} more")

        print("\nFix: Use logging_utils.WorkflowLogger instead of print()")
        print("     from logging_utils import get_logger")
        print("     logger = get_logger(__name__)")
        print("     logger.info('message')  # instead of print('message')")
        print()
        print("To disable: ENFORCE_LOGGING_ONLY=false")

        return 2

    return 0


if __name__ == "__main__":
    sys.exit(main())
