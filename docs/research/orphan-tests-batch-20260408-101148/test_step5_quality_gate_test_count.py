"""Integration tests for test count regression wiring in step5_quality_gate.

Verifies that check_test_count_regression() is properly integrated into
run_quality_gate() and affects the overall pass/fail decision.
"""

import json
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT / "plugins/autonomous-dev/lib"))

from step5_quality_gate import (
    CoverageResult,
    TestResult,
    run_quality_gate,
)
import coverage_baseline


def _make_passing_test_result(test_count: int = 50) -> TestResult:
    """Create a TestResult that passes all checks."""
    return TestResult(
        passed=True,
        test_count=test_count,
        failures=0,
        errors=0,
        skipped=0,
        skip_rate=0.0,
        message=f"PASS: {test_count} passed",
    )


class TestQualityGateTestCountRegression:
    """Tests for test count regression wiring in run_quality_gate()."""

    @patch("step5_quality_gate.run_tests_routed")
    @patch("step5_quality_gate.check_coverage_regression")
    def test_gate_fails_on_test_count_regression(
        self, mock_coverage, mock_routed, tmp_path: Path
    ) -> None:
        """Quality gate fails when test count drops significantly."""
        # Setup: baseline with 100 tests, current run has 70
        baseline_file = tmp_path / "coverage_baseline.json"
        baseline_file.write_text(json.dumps({"total_tests": 100, "skip_count": 0}))

        mock_routed.return_value = {
            "test_result": _make_passing_test_result(test_count=70),
            "routing": None,
        }
        mock_coverage.return_value = CoverageResult(
            passed=True, current_coverage=85.0, message="Coverage: 85%"
        )

        with patch.object(
            coverage_baseline, "get_default_baseline_path", return_value=baseline_file
        ):
            result = run_quality_gate()

        assert result["passed"] is False
        assert result["test_count_regression"]["passed"] is False

    @patch("step5_quality_gate.run_tests_routed")
    @patch("step5_quality_gate.check_coverage_regression")
    def test_gate_passes_on_stable_count(
        self, mock_coverage, mock_routed, tmp_path: Path
    ) -> None:
        """Quality gate passes when test count is stable."""
        baseline_file = tmp_path / "coverage_baseline.json"
        baseline_file.write_text(json.dumps({"total_tests": 50, "skip_count": 0}))

        mock_routed.return_value = {
            "test_result": _make_passing_test_result(test_count=50),
            "routing": None,
        }
        mock_coverage.return_value = CoverageResult(
            passed=True, current_coverage=85.0, message="Coverage: 85%"
        )

        with patch.object(
            coverage_baseline, "get_default_baseline_path", return_value=baseline_file
        ):
            result = run_quality_gate()

        assert result["passed"] is True
        assert result["test_count_regression"]["passed"] is True

    @patch("step5_quality_gate.run_tests_routed")
    @patch("step5_quality_gate.check_coverage_regression")
    def test_summary_includes_test_count_message(
        self, mock_coverage, mock_routed, tmp_path: Path
    ) -> None:
        """Summary string includes the test count regression message."""
        baseline_file = tmp_path / "coverage_baseline.json"
        baseline_file.write_text(json.dumps({"total_tests": 50, "skip_count": 0}))

        mock_routed.return_value = {
            "test_result": _make_passing_test_result(test_count=50),
            "routing": None,
        }
        mock_coverage.return_value = CoverageResult(
            passed=True, current_coverage=85.0, message="Coverage: 85%"
        )

        with patch.object(
            coverage_baseline, "get_default_baseline_path", return_value=baseline_file
        ):
            result = run_quality_gate()

        assert "Test count OK" in result["summary"]

    @patch("step5_quality_gate.run_tests_routed")
    @patch("step5_quality_gate.check_coverage_regression")
    def test_result_dict_has_test_count_regression_key(
        self, mock_coverage, mock_routed, tmp_path: Path
    ) -> None:
        """Result dict includes test_count_regression with passed and message."""
        baseline_file = tmp_path / "coverage_baseline.json"
        baseline_file.write_text(json.dumps({"total_tests": 50, "skip_count": 0}))

        mock_routed.return_value = {
            "test_result": _make_passing_test_result(test_count=50),
            "routing": None,
        }
        mock_coverage.return_value = CoverageResult(
            passed=True, current_coverage=85.0, message="Coverage: 85%"
        )

        with patch.object(
            coverage_baseline, "get_default_baseline_path", return_value=baseline_file
        ):
            result = run_quality_gate()

        assert "test_count_regression" in result
        assert "passed" in result["test_count_regression"]
        assert "message" in result["test_count_regression"]
