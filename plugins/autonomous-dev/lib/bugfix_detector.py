"""Shared library for detecting whether a feature or commit is a bug fix.

Used by:
- Pre-commit hook (enforce_regression_test.py) to block fix commits without tests
- Pipeline HARD GATE in implement.md to enforce regression test requirement

Issue #737: Enforce regression tests on all behavior fixes.
"""

import re
from collections.abc import Sequence
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
# Issue #1601: match both sync `def test_` and `async def test_` — the previous
# sync-only pattern under-counted by ~60% in async-heavy test suites (e.g.,
# IBKR/trading), silently weakening the regression-test HARD GATE in
# enforce_regression_test.py that consumes get_test_count().
_TEST_FUNCTION_PATTERN = re.compile(r"^\s*(async\s+)?def\s+test_", re.MULTILINE)

#: The canonical directory scope for the regression-test HARD GATE's test count.
#:
#: The three directories are ``tests/unit``, ``tests/integration`` and
#: ``tests/regression``.
#:
#: ``tests/regression`` is included because ``docs/TESTING-STRATEGY.md``
#: (lines 54-55 and 133) designates ``tests/regression/`` as the home for
#: regression tests — so a gate blind to it reads a correctly-placed
#: regression test as zero new tests and BLOCKS a correct change. Both the
#: baseline capture (implement.md STEP 1) and the gate evaluation
#: (implement.md STEP 8) MUST use this same constant; a scope mismatch between
#: the two makes the gate structurally unable to refuse.
#:
#: This is NOT ``pipeline_state.CANONICAL_BASELINE_CMD`` and the two MUST NOT
#: be merged or derived from one another. That one is a *pytest execution*
#: scope whose contents are load-bearing for ``__COLLECTION_ERROR__``
#: detection (``pipeline_state.py`` lines 1113-1119); this one is a *counting*
#: scope. Deriving this list from that one would add a
#: ``bugfix_detector -> pipeline_state`` import edge into a module loaded by
#: the pre-commit hook ``enforce_regression_test.py``, and would let a CI
#: performance change to the pytest scope silently alter what the gate
#: refuses. The drift risk is closed by a cross-check test instead
#: (``tests/regression/test_regression_test_count_scope_consistency.py``).
CANONICAL_TEST_COUNT_DIRS: list[str] = [
    "tests/unit",
    "tests/integration",
    "tests/regression",
]


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


def evaluate_regression_test_gate(
    baseline_count: int | None,
    current_count: int,
    project_root: Path | None = None,
    dirs: Sequence[str] | None = None,
) -> tuple[str, str]:
    """Decide the regression-test HARD GATE verdict for a bug fix.

    The gate is tri-state on purpose. A two-state gate has to choose between
    failing open (never refusing when the baseline is missing) and failing
    closed (refusing in every repo without a ``tests/unit`` layout). The third
    verdict, ``UNMEASURED``, names the case where the gate has no basis for an
    opinion so the caller can proceed *and say why*.

    Decision order is load-bearing — it is what keeps the arms
    distinguishable:

    1. ``baseline_count is None`` -> ``UNMEASURED``. The baseline was never
       captured (e.g. the shell variable did not survive into a fresh
       process), so no comparison is possible.
    2. No directory in ``dirs`` exists under ``project_root`` ->
       ``UNMEASURED``. This is a consumer repo with a different test layout;
       the counter cannot see its tests at all.
    3. ``current_count > baseline_count`` -> ``PASS``. At least one new test
       was added.
    4. Otherwise -> ``BLOCK``.

    Step 2 keys on **directory presence, not** ``count == 0``. A repo with a
    canonical layout whose directories exist but hold zero tests still reaches
    step 4 and BLOCKS — "you have the standard layout and added nothing" is a
    refusal, not an absence of measurement.

    Args:
        baseline_count: Test count captured before the change, or ``None`` if
            it was never captured.
        current_count: Test count measured after the change.
        project_root: Root used to resolve ``dirs``. Defaults to ``Path(".")``.
        dirs: Directories the count covers. Defaults to
            :data:`CANONICAL_TEST_COUNT_DIRS`.

    A fourth verdict, ``ERROR``, exists in the *caller's* vocabulary but is
    never returned here — the caller emits it when this function could not be
    reached at all (a stale deployed library, a missing symbol), which by
    definition no code inside this function can catch. ``ERROR`` fails closed;
    ``UNMEASURED`` fails open. See the
    ``# BEGIN REGRESSION-TEST-COUNT-GATE`` block in ``commands/implement.md``.

    Returns:
        A ``(verdict, reason)`` tuple where verdict is one of ``"BLOCK"``,
        ``"PASS"`` or ``"UNMEASURED"``, and reason is a human-readable
        explanation suitable for printing verbatim. ``"ERROR"`` is never
        returned; it is emitted by the caller when this function could not
        run.
    """
    if project_root is None:
        project_root = Path(".")
    if dirs is None:
        dirs = CANONICAL_TEST_COUNT_DIRS

    if baseline_count is None:
        return (
            "UNMEASURED",
            "baseline count was never captured, so no before/after comparison "
            "is possible; the regression-test gate has no basis to refuse.",
        )

    existing = [rel_dir for rel_dir in dirs if (project_root / rel_dir).is_dir()]
    if not existing:
        return (
            "UNMEASURED",
            "none of the canonical test directories exist under "
            f"{project_root} (looked for: {', '.join(dirs)}); this repo uses a "
            "different test layout, so the test count cannot be interpreted.",
        )

    if current_count > baseline_count:
        return (
            "PASS",
            f"test count rose from {baseline_count} to {current_count} across "
            f"{', '.join(existing)}.",
        )

    return (
        "BLOCK",
        f"test count did not rise (before: {baseline_count}, after: "
        f"{current_count}) across {', '.join(existing)}; a bug fix must add at "
        "least one new test.",
    )
