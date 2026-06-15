"""Opportunistic fix-forward classification for pre-existing test failures.

Provides utilities to parse pytest output for failing tests, classify them
against a known baseline, and format issue bodies for auto-filing.

Used by:
- Pipeline STEP 1 (implement.md) to capture baseline failing tests
- Pipeline STEP 8 (implement.md) to classify failures as pre-existing vs new
- Implementer agent to decide whether to fix or document failures

Issue #860: Opportunistic fix-forward — agents should fix pre-existing failures within reach.
"""

import re


# Pattern matching pytest FAILED lines: "path/to/test.py::test_name FAILED"
_FAILED_LINE_PATTERN = re.compile(r"^(.+?)\s+FAILED\s*$", re.MULTILINE)

# Pattern matching pytest summary lines like "= 5 failed in 2.3s ="
_SUMMARY_LINE_PATTERN = re.compile(r"^=+\s+.*\s+=+$")


def parse_failing_tests(pytest_output: str) -> set[str]:
    """Parse test IDs from pytest --tb=no -q output.

    Looks for lines containing 'FAILED' and extracts the test ID
    (everything before ' FAILED').

    Args:
        pytest_output: Raw stdout/stderr from a pytest run.

    Returns:
        Set of failing test IDs (e.g., {"tests/unit/test_foo.py::test_bar"}).
    """
    failing: set[str] = set()
    for line in pytest_output.splitlines():
        line = line.strip()
        # Skip empty lines and summary lines (e.g., "= 5 failed in 2.3s =")
        if not line or _SUMMARY_LINE_PATTERN.match(line):
            continue
        match = _FAILED_LINE_PATTERN.match(line)
        if match:
            test_id = match.group(1).strip()
            if test_id:
                failing.add(test_id)
    return failing


def classify_failures(
    baseline: set[str],
    current: set[str],
    known_flaky_tests: set[str] | None = None,
) -> dict[str, set[str]]:
    """Classify failures into three categories.

    Args:
        baseline: Set of test IDs that were failing before the implementer ran.
        current: Set of test IDs that are failing after the implementer ran.
        known_flaky_tests: Optional set of test IDs known to be flaky. When
            provided, these IDs are excluded from new_failures (Issue #983).

    Returns:
        Dictionary with three keys:
        - "fixed": in baseline but not in current (was failing, now passes).
        - "pre_existing_remaining": in both baseline and current (still failing).
        - "new_failures": in current but not in baseline, EXCLUDING known-flaky IDs.
    """
    new_failures = current - baseline
    if known_flaky_tests is not None:
        new_failures = new_failures - known_flaky_tests
    return {
        "fixed": baseline - current,
        "pre_existing_remaining": baseline & current,
        "new_failures": new_failures,
    }


def format_issue_body(test_id: str, context: str = "") -> str:
    """Format GitHub issue body for auto-filing pre-existing failures.

    Args:
        test_id: Fully qualified test ID (e.g., "tests/unit/test_foo.py::test_bar").
        context: Optional context description (e.g., "Discovered during pipeline run X").

    Returns:
        Formatted Markdown issue body suitable for ``gh issue create --body``.
    """
    lines = [
        "## Pre-Existing Test Failure",
        "",
        f"**Test ID**: `{test_id}`",
        "",
    ]

    if context:
        lines.extend([
            f"**Context**: {context}",
            "",
        ])

    lines.extend([
        "## Details",
        "",
        "This test was already failing before the implementer ran. It was not introduced",
        "by the current changeset and has been filed for separate resolution.",
        "",
        "## Suggested Actions",
        "",
        "1. Run the test locally: `pytest {test_id} -xvs`".format(test_id=test_id),
        "2. Diagnose the root cause",
        "3. Fix or remove the test if it is no longer relevant",
        "",
        "## Labels",
        "",
        "Suggested label: `pre-existing-failure`",
    ])

    return "\n".join(lines)
