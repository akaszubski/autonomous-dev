"""Opportunistic fix-forward classification for pre-existing test failures.

Provides utilities to parse pytest output for failing tests, classify them
against a known baseline, and format issue bodies for auto-filing.

Used by:
- Pipeline STEP 1 (implement.md) to capture baseline failing tests
- Pipeline STEP 8 (implement.md) to classify failures as pre-existing vs new
- Implementer agent to decide whether to fix or document failures

Issue #860: Opportunistic fix-forward — agents should fix pre-existing failures within reach.
Issue #1094: a capture that timed out writes ``__TIMEOUT__`` instead of a traceback.
Issue #1533: a capture that executed zero tests writes ``__COLLECTION_ERROR__`` instead of
looking like a legitimate empty baseline.
"""

from __future__ import annotations

import re
from typing import NamedTuple, Optional


# Pattern matching pytest's VERBOSE per-test line: "path/to/test.py::test_name FAILED"
_FAILED_LINE_PATTERN = re.compile(r"^(.+?)\s+FAILED\s*$", re.MULTILINE)

# Pattern matching pytest's SHORT TEST SUMMARY line, which is emitted by default
# (`-r fE`) at any verbosity: "FAILED path/to/test.py::test_name - AssertionError".
# Issue #1533: without this, a `-q` run — the pipeline's own baseline invocation —
# yields zero parsed IDs even when pytest reported failures, silently zeroing the
# baseline the same way a collection error does.
#
# The ID is "non-space run, optionally followed by one bracketed parametrize
# block". Splitting on the first " - " instead would truncate
# `test_bar[a - b] - AssertionError` to `test_bar[a`, since a parametrize value
# may contain the same separator pytest uses before the failure reason.
_SHORT_SUMMARY_FAILED_PATTERN = re.compile(r"^FAILED\s+(\S+?(?:\[[^\]]*\])?)(?:\s+-\s+.*)?$")

# Pattern matching pytest summary lines like "= 5 failed in 2.3s ="
_SUMMARY_LINE_PATTERN = re.compile(r"^=+\s+.*\s+=+$")

# ---------------------------------------------------------------------------
# Capture-failure detection (Issue #1533)
# ---------------------------------------------------------------------------
#
# THE INVARIANT: a capture that executed zero tests is a measurement failure,
# never a baseline.
#
# Before this, a baseline capture that aborted during collection (e.g. a test
# module importing a module that no longer exists) produced no ``FAILED`` lines,
# so ``parse_failing_tests`` returned an empty set and STEP 1 printed
# "Baseline failing tests: 0". That empty set is indistinguishable from a
# genuinely green tree, so STEP 8 later classified every real failure as NEW.
# The timeout route (Issue #1094) was already handled by a sentinel; every other
# route to "zero tests executed" was silently rounded down to a legitimate zero.

#: Sentinel written when the pytest capture exceeded its timeout (Issue #1094).
TIMEOUT_SENTINEL = "__TIMEOUT__"

#: Sentinel written when the pytest capture produced no trustworthy measurement
#: (collection error, internal error, usage error, or zero tests executed).
COLLECTION_ERROR_SENTINEL = "__COLLECTION_ERROR__"

#: All sentinels that mean "the baseline is UNKNOWN — do not classify against it".
CAPTURE_FAILURE_SENTINELS = (TIMEOUT_SENTINEL, COLLECTION_ERROR_SENTINEL)

#: pytest exit codes that mean "no trustworthy measurement was produced".
#: 0 = all passed, 1 = tests failed (both are real measurements). 2 = interrupted
#: (this is what a collection error produces), 3 = internal error, 4 = usage
#: error, 5 = no tests collected.
_MEASUREMENT_FAILURE_EXIT_CODES = frozenset({2, 3, 4, 5})

#: Banners pytest prints when a run aborted rather than measured, as
#: ``(name, line-anchored pattern)`` pairs.
#:
#: These are matched per LINE, anchored to the shape of pytest's actual banner —
#: never as a substring of the whole output blob. A blob-wide substring search
#: collides with real test IDs: this repo defines
#: ``class TestGateInternalErrorsFailClosed``, whose short-summary line lowercases
#: to a string containing ``internalerror``, so ANY measured failure in that class
#: was misread as a collection error and its real signal discarded. That is the
#: Issue #1533 defect itself — a real measurement silently rounded down to
#: "unknown" — reached by a different route. Matching is case-SENSITIVE because
#: pytest's banners have fixed casing (``Interrupted:``, ``INTERNALERROR>``,
#: ``no tests ran``), which removes one more way for prose to collide.
_ABORT_LINE_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    # "!!!!!! Interrupted: 1 error during collection !!!!!!" — the session
    # interruption banner, always bang-delimited and line-initial. This is also
    # the only shape in which "error(s) during collection" reaches the output on
    # an aborted run.
    ("Interrupted:", re.compile(r"^!+\s*Interrupted:")),
    # Any bang/equals-decorated banner naming collection errors, for pytest
    # versions that word the interruption differently. Requiring decoration on
    # BOTH ends is what a test ID or assertion message can never satisfy.
    (
        "error during collection",
        re.compile(r"^[!=]+.*\berrors?\s+during\s+collection\b.*[!=]+$", re.IGNORECASE),
    ),
    # "INTERNALERROR> Traceback (most recent call last):" — pytest's crash
    # banner. Always uppercase, always line-initial, always followed by ">".
    ("INTERNALERROR>", re.compile(r"^INTERNALERROR>")),
    # "==== no tests ran in 0.01s ====", or bare "no tests ran in 0.01s" under -q.
    ("no tests ran", re.compile(r"^=*\s*no tests ran\b")),
)

#: Outcome words counted as "a test was collected and processed". "error" is
#: deliberately excluded — an error is not an executed test.
_OUTCOME_COUNT_PATTERN = re.compile(
    r"(\d+)\s+(passed|failed|skipped|xfailed|xpassed)\b", re.IGNORECASE
)

#: pytest terminates its summary line with "in 1.23s" / "in 1.23 seconds".
_SUMMARY_TAIL_PATTERN = re.compile(r"\bin\s+[\d.]+\s*s(?:econds)?\b", re.IGNORECASE)


def _find_abort_banner(pytest_output: str) -> Optional[str]:
    """Find a pytest abort banner, ignoring lines that report a failing test.

    Args:
        pytest_output: Combined stdout+stderr from a pytest run.

    Returns:
        The name of the first abort banner found, or None when the output
        contains no banner. A marker word occurring inside a test ID, class
        name, or assertion message is NOT a banner.
    """
    for raw_line in pytest_output.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        # A line reporting a failing test is a MEASUREMENT, never a banner —
        # skip it before any marker is considered.
        if _FAILED_LINE_PATTERN.match(line) or _SHORT_SUMMARY_FAILED_PATTERN.match(line):
            continue
        for name, pattern in _ABORT_LINE_PATTERNS:
            if pattern.match(line):
                return name
    return None


class CaptureFailure(NamedTuple):
    """A pytest capture that did not produce a trustworthy measurement.

    Attributes:
        sentinel: The sentinel line to write in place of test IDs.
        reason: Human-readable explanation, for the operator-facing warning.
    """

    sentinel: str
    reason: str


def count_executed_tests(pytest_output: str) -> Optional[int]:
    """Count tests pytest reports as collected and processed.

    Reads the LAST pytest summary line (the one ending in ``in <n>s``) and sums
    the passed/failed/skipped/xfailed/xpassed counts on it.

    Args:
        pytest_output: Raw stdout/stderr from a pytest run.

    Returns:
        The number of tests processed, or None when no pytest summary line is
        present (which itself means the output cannot be trusted).
    """
    total: Optional[int] = None
    for line in pytest_output.splitlines():
        stripped = line.strip().strip("=").strip()
        if not stripped or not _SUMMARY_TAIL_PATTERN.search(stripped):
            continue
        counts = _OUTCOME_COUNT_PATTERN.findall(stripped)
        if not counts:
            continue
        total = sum(int(n) for n, _outcome in counts)
    return total


def count_reported_failures(pytest_output: str) -> Optional[int]:
    """Read the failure count pytest states in its summary line.

    Args:
        pytest_output: Raw stdout/stderr from a pytest run.

    Returns:
        The number pytest reported as failed, or None when no summary line is
        present.
    """
    reported: Optional[int] = None
    for line in pytest_output.splitlines():
        stripped = line.strip().strip("=").strip()
        if not stripped or not _SUMMARY_TAIL_PATTERN.search(stripped):
            continue
        counts = _OUTCOME_COUNT_PATTERN.findall(stripped)
        if not counts:
            continue
        reported = sum(int(n) for n, outcome in counts if outcome.lower() == "failed")
    return reported


def detect_capture_failure(
    pytest_output: str,
    returncode: Optional[int] = None,
) -> Optional[CaptureFailure]:
    """Decide whether a pytest capture measured anything at all.

    Encodes the Issue #1533 invariant: a capture that executed zero tests is a
    measurement failure, never a baseline. Three independent signals are checked
    so that routes not yet identified are still caught:

    1. pytest exit code in {2, 3, 4, 5} — interrupted, internal error, usage
       error, or nothing collected.
    2. An abort BANNER on its own line (``!!! Interrupted: ... !!!``,
       ``INTERNALERROR>``, ``no tests ran in ...``). Anchored per line and
       checked only on lines that do not report a failing test, so a marker word
       inside a test ID or assertion message is never mistaken for a banner.
    3. Zero tests processed according to the summary line — or no summary line
       at all.

    Args:
        pytest_output: Combined stdout+stderr from the pytest run.
        returncode: pytest's exit code, when available. None skips signal 1.

    Returns:
        A CaptureFailure when the capture is untrustworthy, else None. None
        means "this measurement is real" — including a real measured zero.
    """
    if returncode is not None and returncode in _MEASUREMENT_FAILURE_EXIT_CODES:
        return CaptureFailure(
            COLLECTION_ERROR_SENTINEL,
            f"pytest exited {returncode} (no trustworthy measurement produced)",
        )

    banner = _find_abort_banner(pytest_output)
    if banner is not None:
        return CaptureFailure(
            COLLECTION_ERROR_SENTINEL,
            f"pytest output contains abort banner {banner!r}",
        )

    executed = count_executed_tests(pytest_output)
    if executed is None:
        return CaptureFailure(
            COLLECTION_ERROR_SENTINEL,
            "no pytest summary line found — capture output is unparseable",
        )
    if executed == 0:
        return CaptureFailure(
            COLLECTION_ERROR_SENTINEL,
            "pytest executed 0 tests — a zero-test capture is never a baseline",
        )

    # Instrument self-check: pytest said N tests failed but no test ID could be
    # parsed out. That means the output shape is not one this parser understands,
    # and an empty result would be silently mistaken for a green baseline — the
    # same failure mode as a collection error, by a different route.
    reported_failures = count_reported_failures(pytest_output)
    if reported_failures and not parse_failing_tests(pytest_output):
        return CaptureFailure(
            COLLECTION_ERROR_SENTINEL,
            f"pytest reported {reported_failures} failure(s) but no test IDs could "
            "be parsed — capture output format is not understood",
        )
    return None


def is_capture_failure_sentinel(baseline_contents: str) -> bool:
    """Return True when baseline file contents are a capture-failure sentinel.

    Args:
        baseline_contents: Raw contents of the baseline failing-tests file.

    Returns:
        True when the baseline is UNKNOWN (timeout or collection error) and
        fix-forward classification must be skipped.
    """
    stripped = baseline_contents.strip()
    return any(stripped.startswith(s) for s in CAPTURE_FAILURE_SENTINELS)


def parse_failing_tests(pytest_output: str) -> set[str]:
    """Parse failing test IDs from pytest output.

    Handles both shapes pytest emits:

    - verbose per-test lines — ``path/to/test.py::test_name FAILED``
    - short test summary lines — ``FAILED path/to/test.py::test_name - reason``
      (emitted by default at any verbosity, and the ONLY shape a ``-q`` run
      produces — Issue #1533)

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
        match = _FAILED_LINE_PATTERN.match(line) or _SHORT_SUMMARY_FAILED_PATTERN.match(line)
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
