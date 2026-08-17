"""Unit tests for the capture-failure detection added in Issue #1533.

`detect_capture_failure` decides whether a pytest capture measured anything.
Its parsing helper `count_executed_tests` reads the summary line, so the
summary-line shapes pytest actually emits are the interesting edge cases.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

LIB_DIR = Path(__file__).resolve().parents[3] / "plugins" / "autonomous-dev" / "lib"
sys.path.insert(0, str(LIB_DIR))

from fix_forward import (  # noqa: E402
    COLLECTION_ERROR_SENTINEL,
    TIMEOUT_SENTINEL,
    count_executed_tests,
    count_reported_failures,
    detect_capture_failure,
    is_capture_failure_sentinel,
)


class TestCountExecutedTests:
    """Summary-line parsing across the shapes pytest emits."""

    @pytest.mark.parametrize(
        "output,expected",
        [
            ("======= 11324 passed, 4 skipped in 182.10s =======\n", 11328),
            ("= 2 failed in 0.5s =\n", 2),
            ("2 failed, 3 passed in 1.20s\n", 5),
            ("=== 10 skipped, 12 warnings, 1 error in 3.73s ===\n", 10),
            ("=== 1 passed, 2 xfailed, 1 xpassed in 0.10 seconds ===\n", 4),
            ("==================== no tests ran in 0.01s ====================\n", None),
        ],
    )
    def test_summary_shapes(self, output: str, expected: int | None) -> None:
        assert count_executed_tests(output) == expected

    def test_warnings_are_not_counted_as_tests(self) -> None:
        assert count_executed_tests("=== 12 warnings in 1.00s ===\n") is None

    def test_last_summary_line_wins(self) -> None:
        """Two runs in one buffer: the final summary is the operative one."""
        output = "= 3 passed in 0.10s =\n= 7 passed in 0.20s =\n"
        assert count_executed_tests(output) == 7

    def test_no_summary_line_returns_none(self) -> None:
        assert count_executed_tests("tests/unit/test_a.py::test_one FAILED\n") is None

    def test_empty_output_returns_none(self) -> None:
        assert count_executed_tests("") is None


class TestDetectCaptureFailure:
    """The invariant: zero executed tests is a measurement failure."""

    def test_measured_pass_is_not_a_failure(self) -> None:
        assert detect_capture_failure("= 5 passed in 1.0s =\n", returncode=0) is None

    def test_measured_failure_is_not_a_capture_failure(self) -> None:
        """Exit code 1 means tests ran and some failed — a real measurement."""
        output = "tests/unit/test_a.py::test_one FAILED\n= 1 failed, 4 passed in 1.0s =\n"
        assert detect_capture_failure(output, returncode=1) is None

    @pytest.mark.parametrize(
        "marker",
        [
            "!!!! Interrupted: 1 error during collection !!!!",
            "!!!! Interrupted: 3 errors during collection !!!!",
            "INTERNALERROR> Traceback (most recent call last):",
            "==== no tests ran in 0.01s ====",
        ],
    )
    def test_abort_markers_detected_without_exit_code(self, marker: str) -> None:
        failure = detect_capture_failure(marker + "\n= 5 passed in 1.0s =\n")
        assert failure is not None
        assert failure.sentinel == COLLECTION_ERROR_SENTINEL

    def test_failure_carries_a_reason(self) -> None:
        failure = detect_capture_failure("", returncode=None)
        assert failure is not None
        assert failure.reason, "operator-facing warning must explain what failed"

    def test_returncode_none_falls_through_to_output_signals(self) -> None:
        """No exit code available must not make everything look healthy."""
        assert detect_capture_failure("= 5 passed in 1.0s =\n", returncode=None) is None
        assert detect_capture_failure("garbage output", returncode=None) is not None


class TestCountReportedFailures:
    """The number pytest STATES it failed, used as an instrument self-check."""

    def test_reads_failed_count(self) -> None:
        assert count_reported_failures("= 3 failed, 5 passed in 1.0s =\n") == 3

    def test_zero_when_nothing_failed(self) -> None:
        assert count_reported_failures("= 5 passed in 1.0s =\n") == 0

    def test_none_without_summary(self) -> None:
        assert count_reported_failures("no summary here\n") is None

    def test_reported_failures_with_zero_parsed_ids_is_a_failure(self) -> None:
        output = "something unparseable\n= 4 failed, 1 passed in 1.0s =\n"
        failure = detect_capture_failure(output, returncode=1)
        assert failure is not None
        assert "no test IDs could" in failure.reason

    def test_reported_failures_with_parsed_ids_is_fine(self) -> None:
        output = (
            "FAILED tests/unit/test_a.py::test_one - assert False\n"
            "= 1 failed, 1 passed in 1.0s =\n"
        )
        assert detect_capture_failure(output, returncode=1) is None


class TestSentinelHelper:
    """`is_capture_failure_sentinel` covers both unknown-baseline sentinels."""

    @pytest.mark.parametrize("sentinel", [TIMEOUT_SENTINEL, COLLECTION_ERROR_SENTINEL])
    def test_sentinels_recognised(self, sentinel: str) -> None:
        assert is_capture_failure_sentinel(f"\n{sentinel}\n")

    def test_test_ids_are_not_sentinels(self) -> None:
        assert not is_capture_failure_sentinel("tests/unit/test_a.py::test_one")

    def test_empty_baseline_is_not_a_sentinel(self) -> None:
        """A measured zero is a baseline, not an unknown."""
        assert not is_capture_failure_sentinel("")
        assert not is_capture_failure_sentinel("   \n")
