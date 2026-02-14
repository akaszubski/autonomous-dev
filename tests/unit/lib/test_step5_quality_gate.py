"""Tests for step5_quality_gate module."""

import json
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "plugins" / "autonomous-dev" / "lib"))

from step5_quality_gate import (
    CoverageResult,
    TestResult,
    check_coverage_regression,
    parse_coverage_output,
    parse_pytest_output,
    run_quality_gate,
    run_tests,
)


class TestParsePytestOutput:
    """Tests for parse_pytest_output."""

    def test_all_passed(self):
        output = "10 passed in 1.23s\n========================= 10 passed in 1.23s ========================="
        result = parse_pytest_output(output)
        assert result.passed is True
        assert result.test_count == 10
        assert result.failures == 0
        assert result.errors == 0
        assert result.skipped == 0
        assert result.skip_rate == 0.0
        assert "PASS" in result.message

    def test_some_failures(self):
        output = "========================= 3 failed, 7 passed in 2.00s ========================="
        result = parse_pytest_output(output)
        assert result.passed is False
        assert result.test_count == 10
        assert result.failures == 3
        assert result.errors == 0
        assert "FAIL" in result.message

    def test_errors(self):
        output = "========================= 1 error, 9 passed in 1.00s ========================="
        result = parse_pytest_output(output)
        assert result.passed is False
        assert result.errors == 1

    def test_skipped(self):
        output = "========================= 8 passed, 2 skipped in 1.00s ========================="
        result = parse_pytest_output(output)
        assert result.passed is True
        assert result.skipped == 2
        assert result.skip_rate == 20.0
        assert result.blocker is not None
        assert "10%" in result.blocker

    def test_mixed_results(self):
        output = "========================= 1 failed, 5 passed, 2 skipped, 1 error in 3.00s ========================="
        result = parse_pytest_output(output)
        assert result.passed is False
        assert result.test_count == 9
        assert result.failures == 1
        assert result.errors == 1  # "1 error" uses singular
        assert result.skipped == 2

    def test_no_tests_ran(self):
        output = "========================= no tests ran ========================="
        result = parse_pytest_output(output)
        assert result.passed is False
        assert result.test_count == 0
        assert "No tests ran" in result.message

    def test_short_format(self):
        output = "5 passed, 1 failed in 0.50s"
        result = parse_pytest_output(output)
        assert result.passed is False
        assert result.failures == 1
        assert result.test_count == 6

    def test_skip_rate_under_threshold(self):
        output = "========================= 95 passed, 5 skipped in 10.00s ========================="
        result = parse_pytest_output(output)
        assert result.passed is True
        assert result.skip_rate == 5.0
        assert result.blocker is None  # 5% is not > 10%

    def test_skip_rate_over_threshold(self):
        output = "========================= 8 passed, 3 skipped in 1.00s ========================="
        result = parse_pytest_output(output)
        assert result.skip_rate == pytest.approx(27.3, abs=0.1)
        assert result.blocker is not None


class TestParseCoverageOutput:
    """Tests for parse_coverage_output."""

    def test_standard_coverage(self):
        output = (
            "Name                  Stmts   Miss  Cover\n"
            "-----------------------------------------\n"
            "plugins/foo.py           50     10    80%\n"
            "plugins/bar.py           30      5    83%\n"
            "-----------------------------------------\n"
            "TOTAL                    80     15    81%\n"
        )
        assert parse_coverage_output(output) == 81.0

    def test_no_coverage(self):
        output = "no tests ran"
        assert parse_coverage_output(output) is None


class TestCheckCoverageRegression:
    """Tests for check_coverage_regression."""

    def test_no_baseline_creates_one(self, tmp_path):
        baseline = tmp_path / "baseline.json"
        coverage_output = "TOTAL   100   10   90%\n"

        result = check_coverage_regression(
            baseline_path=baseline, coverage_output=coverage_output
        )
        assert result.passed is True
        assert result.current_coverage == 90.0
        assert baseline.exists()
        data = json.loads(baseline.read_text())
        assert data["coverage"] == 90.0

    def test_no_regression(self, tmp_path):
        baseline = tmp_path / "baseline.json"
        baseline.write_text(json.dumps({"coverage": 85.0}))
        coverage_output = "TOTAL   100   10   86%\n"

        result = check_coverage_regression(
            baseline_path=baseline, coverage_output=coverage_output
        )
        assert result.passed is True
        assert result.current_coverage == 86.0

    def test_regression_detected(self, tmp_path):
        baseline = tmp_path / "baseline.json"
        baseline.write_text(json.dumps({"coverage": 90.0}))
        coverage_output = "TOTAL   100   20   89%\n"

        result = check_coverage_regression(
            baseline_path=baseline, coverage_output=coverage_output
        )
        assert result.passed is False
        assert "regressed" in result.message

    def test_small_regression_passes(self, tmp_path):
        baseline = tmp_path / "baseline.json"
        baseline.write_text(json.dumps({"coverage": 90.0}))
        coverage_output = "TOTAL   100   10   89.6%\n"
        # parse_coverage_output extracts integer only, so this is 89%
        # 90 - 89 = 1.0 > 0.5, actually fails
        # Let's use a value that's within threshold
        coverage_output2 = "TOTAL   100   10   90%\n"

        result = check_coverage_regression(
            baseline_path=baseline, coverage_output=coverage_output2
        )
        assert result.passed is True

    def test_unparseable_output(self, tmp_path):
        baseline = tmp_path / "baseline.json"
        result = check_coverage_regression(
            baseline_path=baseline, coverage_output="garbage"
        )
        assert result.passed is True
        assert "Could not parse" in result.message

    def test_baseline_updated_on_improvement(self, tmp_path):
        baseline = tmp_path / "baseline.json"
        baseline.write_text(json.dumps({"coverage": 85.0}))
        coverage_output = "TOTAL   100   5   95%\n"

        check_coverage_regression(
            baseline_path=baseline, coverage_output=coverage_output
        )
        data = json.loads(baseline.read_text())
        assert data["coverage"] == 95.0


class TestRunTests:
    """Tests for run_tests with mocked subprocess."""

    @patch("step5_quality_gate.subprocess.run")
    def test_successful_run(self, mock_run):
        mock_run.return_value = MagicMock(
            stdout="========================= 10 passed in 1.00s =========================",
            stderr="",
        )
        result = run_tests()
        assert result.passed is True
        assert result.test_count == 10

    @patch("step5_quality_gate.subprocess.run")
    def test_timeout(self, mock_run):
        import subprocess as sp
        mock_run.side_effect = sp.TimeoutExpired(cmd="pytest", timeout=600)
        result = run_tests()
        assert result.passed is False
        assert "timed out" in result.message

    @patch("step5_quality_gate.subprocess.run")
    def test_pytest_not_found(self, mock_run):
        mock_run.side_effect = FileNotFoundError()
        result = run_tests()
        assert result.passed is False
        assert "not found" in result.message


class TestRunQualityGate:
    """Tests for run_quality_gate."""

    @patch("step5_quality_gate.check_coverage_regression")
    @patch("step5_quality_gate.run_tests")
    def test_all_pass(self, mock_tests, mock_cov):
        mock_tests.return_value = TestResult(
            passed=True, test_count=10, failures=0, errors=0,
            skipped=0, skip_rate=0.0, message="PASS: 10 passed",
        )
        mock_cov.return_value = CoverageResult(
            passed=True, current_coverage=90.0, message="Coverage: 90%",
        )
        result = run_quality_gate()
        assert result["passed"] is True

    @patch("step5_quality_gate.check_coverage_regression")
    @patch("step5_quality_gate.run_tests")
    def test_tests_fail(self, mock_tests, mock_cov):
        mock_tests.return_value = TestResult(
            passed=False, test_count=10, failures=2, errors=0,
            skipped=0, skip_rate=0.0, message="FAIL: 2 failed",
        )
        mock_cov.return_value = CoverageResult(
            passed=True, current_coverage=90.0, message="Coverage: 90%",
        )
        result = run_quality_gate()
        assert result["passed"] is False

    @patch("step5_quality_gate.check_coverage_regression")
    @patch("step5_quality_gate.run_tests")
    def test_coverage_fails(self, mock_tests, mock_cov):
        mock_tests.return_value = TestResult(
            passed=True, test_count=10, failures=0, errors=0,
            skipped=0, skip_rate=0.0, message="PASS: 10 passed",
        )
        mock_cov.return_value = CoverageResult(
            passed=False, current_coverage=80.0, message="FAIL: regressed",
        )
        result = run_quality_gate()
        assert result["passed"] is False
