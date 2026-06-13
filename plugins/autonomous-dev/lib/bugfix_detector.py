"""Shared library for detecting whether a feature or commit is a bug fix.

Used by:
- Pre-commit hook (enforce_regression_test.py) to block fix commits without tests
- Pipeline HARD GATE in implement.md to enforce regression test requirement

Issue #737: Enforce regression tests on all behavior fixes.
"""

import re
from pathlib import Path

# Word-boundary patterns for bug-fix keywords in feature descriptions.
# Uses \b to avoid false positives like "prefix" matching "fix".
_BUGFIX_KEYWORDS_PATTERN = re.compile(
    r"\b(fix|bug|broken|regression|crash|dedup|duplicate)\b",
    re.IGNORECASE,
)

# Labels that indicate a bug fix.
_BUGFIX_LABELS = frozenset({"bug", "fix", "bugfix", "regression", "hotfix"})

# Commit message prefixes that indicate a bug fix.
# Matches: "fix:", "bugfix:", "hotfix:", "fix(scope):"
_BUGFIX_COMMIT_PATTERN = re.compile(
    r"^(fix|bugfix|hotfix)(\([^)]*\))?:",
    re.IGNORECASE,
)

# Pattern for counting test functions in Python files.
_TEST_FUNCTION_PATTERN = re.compile(r"^\s*def\s+test_", re.MULTILINE)


def is_bugfix_feature(description: str, labels: list[str] | None = None) -> bool:
    """Check if a feature description or its labels indicate a bug fix.

    Args:
        description: Feature description text (e.g., issue title or body).
        labels: Optional list of issue labels (e.g., ["bug", "urgent"]).

    Returns:
        True if the description or labels indicate a bug fix.
    """
    if _BUGFIX_KEYWORDS_PATTERN.search(description):
        return True

    if labels:
        normalized_labels = {label.lower().strip() for label in labels}
        if normalized_labels & _BUGFIX_LABELS:
            return True

    return False


def is_bugfix_commit(message: str) -> bool:
    """Check if a commit message indicates a bug fix.

    Args:
        message: Git commit message (first line is checked).

    Returns:
        True if the commit message starts with a fix prefix.
    """
    first_line = message.strip().split("\n")[0] if message.strip() else ""
    return bool(_BUGFIX_COMMIT_PATTERN.match(first_line))


def get_test_count_for_dirs(dirs: list[str], project_root: Path | None = None) -> int:
    """Count test functions in the specified test subdirectories.

    Mirrors get_test_count() but restricts the scan to only the given
    relative subdirectories (e.g. ["tests/unit", "tests/integration"]).
    Used for baseline_count that must match CANONICAL_BASELINE_CMD scope.

    Args:
        dirs: Relative directory paths (e.g. ["tests/unit", "tests/integration"]).
            Resolved against project_root. Non-existent dirs are silently skipped.
        project_root: Root for relative path resolution. Defaults to Path(".").

    Returns:
        Total count of def test_* functions found in any .py file under the dirs.
    """
    if project_root is None:
        project_root = Path(".")

    count = 0
    for rel_dir in dirs:
        target_dir = project_root / rel_dir
        if not target_dir.is_dir():
            continue
        for py_file in target_dir.rglob("*.py"):
            try:
                content = py_file.read_text(encoding="utf-8", errors="ignore")
                count += len(_TEST_FUNCTION_PATTERN.findall(content))
            except OSError:
                continue

    return count


def get_test_count(project_root: Path) -> int:
    """Count test functions by scanning the tests/ directory.

    Scans all .py files under project_root/tests/ for lines matching
    ``def test_*`` and returns the total count.

    Args:
        project_root: Path to the project root directory.

    Returns:
        Number of test functions found.
    """
    tests_dir = project_root / "tests"
    if not tests_dir.is_dir():
        return 0

    count = 0
    for py_file in tests_dir.rglob("*.py"):
        try:
            content = py_file.read_text(encoding="utf-8", errors="ignore")
            count += len(_TEST_FUNCTION_PATTERN.findall(content))
        except OSError:
            continue

    return count
