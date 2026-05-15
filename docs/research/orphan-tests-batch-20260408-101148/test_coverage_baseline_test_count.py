"""Unit tests for check_test_count_regression() in coverage_baseline.py.

Tests the test count regression detection that prevents gaming where
behavioral tests are deleted and replaced with fewer structural checks.
"""

import json
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT / "plugins/autonomous-dev/lib"))

from coverage_baseline import check_test_count_regression


class TestCheckTestCountRegression:
    """Tests for check_test_count_regression()."""

    def test_no_baseline_passes(self, tmp_path: Path) -> None:
        """When no baseline file exists, the check passes."""
        passed, msg = check_test_count_regression(
            100, baseline_path=tmp_path / "nonexistent.json"
        )
        assert passed is True
        assert "No baseline" in msg

    def test_missing_total_tests_key_passes(self, tmp_path: Path) -> None:
        """When baseline exists but lacks total_tests key, the check passes."""
        baseline_file = tmp_path / "baseline.json"
        baseline_file.write_text(json.dumps({"coverage_pct": 85.0}))
        passed, msg = check_test_count_regression(100, baseline_path=baseline_file)
        assert passed is True
        assert "No baseline" in msg

    def test_above_baseline_passes(self, tmp_path: Path) -> None:
        """When current count is above baseline, the check passes."""
        baseline_file = tmp_path / "baseline.json"
        baseline_file.write_text(json.dumps({"total_tests": 100}))
        passed, msg = check_test_count_regression(110, baseline_path=baseline_file)
        assert passed is True
        assert "Test count OK" in msg

    def test_at_baseline_passes(self, tmp_path: Path) -> None:
        """When current count equals baseline, the check passes."""
        baseline_file = tmp_path / "baseline.json"
        baseline_file.write_text(json.dumps({"total_tests": 100}))
        passed, msg = check_test_count_regression(100, baseline_path=baseline_file)
        assert passed is True

    def test_within_tolerance_passes(self, tmp_path: Path) -> None:
        """When drop is within tolerance, the check passes."""
        baseline_file = tmp_path / "baseline.json"
        baseline_file.write_text(json.dumps({"total_tests": 100}))
        # Default tolerance: min(10%, 20) = 10 tests for baseline of 100
        passed, msg = check_test_count_regression(91, baseline_path=baseline_file)
        assert passed is True

    def test_beyond_tolerance_pct_fails(self, tmp_path: Path) -> None:
        """When drop exceeds percentage tolerance, the check blocks."""
        baseline_file = tmp_path / "baseline.json"
        baseline_file.write_text(json.dumps({"total_tests": 100}))
        # Drop of 11 tests > min(10%, 20) = 10 for baseline of 100
        passed, msg = check_test_count_regression(89, baseline_path=baseline_file)
        assert passed is False
        assert "regression" in msg.lower()

    def test_beyond_tolerance_abs_fails(self, tmp_path: Path) -> None:
        """When drop exceeds absolute tolerance, the check blocks."""
        baseline_file = tmp_path / "baseline.json"
        # With 500 tests: pct tolerance = 50, abs tolerance = 20
        # min(50, 20) = 20, so abs is the binding constraint
        baseline_file.write_text(json.dumps({"total_tests": 500}))
        passed, msg = check_test_count_regression(479, baseline_path=baseline_file)
        assert passed is False
        assert "regression" in msg.lower()

    def test_uses_min_of_pct_and_abs(self, tmp_path: Path) -> None:
        """Verify min(tolerance_pct%, tolerance_abs) logic.

        For baseline=500: pct_drop_allowed=50, abs_drop_allowed=20.
        min(50, 20) = 20. So dropping 20 is OK, dropping 21 is not.
        """
        baseline_file = tmp_path / "baseline.json"
        baseline_file.write_text(json.dumps({"total_tests": 500}))

        # Drop of exactly 20 (at boundary) should pass
        passed, _ = check_test_count_regression(480, baseline_path=baseline_file)
        assert passed is True

        # Drop of 21 should fail
        passed, _ = check_test_count_regression(479, baseline_path=baseline_file)
        assert passed is False

    def test_baseline_zero_total_tests_passes(self, tmp_path: Path) -> None:
        """When baseline has 0 total_tests, any count is fine (division guard)."""
        baseline_file = tmp_path / "baseline.json"
        baseline_file.write_text(json.dumps({"total_tests": 0}))
        passed, msg = check_test_count_regression(50, baseline_path=baseline_file)
        assert passed is True
        assert "baseline was 0" in msg

    def test_corrupted_baseline_passes_gracefully(self, tmp_path: Path) -> None:
        """When baseline file is corrupted JSON, the check passes."""
        baseline_file = tmp_path / "baseline.json"
        baseline_file.write_text("not valid json {{{")
        passed, msg = check_test_count_regression(100, baseline_path=baseline_file)
        assert passed is True

    def test_custom_tolerance_pct(self, tmp_path: Path) -> None:
        """Custom tolerance_pct is respected."""
        baseline_file = tmp_path / "baseline.json"
        baseline_file.write_text(json.dumps({"total_tests": 100}))
        # With tolerance_pct=5, tolerance_abs=20: min(5, 20) = 5
        passed, _ = check_test_count_regression(
            94, tolerance_pct=5.0, tolerance_abs=20, baseline_path=baseline_file
        )
        assert passed is False

    def test_custom_tolerance_abs(self, tmp_path: Path) -> None:
        """Custom tolerance_abs is respected."""
        baseline_file = tmp_path / "baseline.json"
        baseline_file.write_text(json.dumps({"total_tests": 100}))
        # With tolerance_pct=10, tolerance_abs=5: min(10, 5) = 5
        passed, _ = check_test_count_regression(
            94, tolerance_pct=10.0, tolerance_abs=5, baseline_path=baseline_file
        )
        assert passed is False

    def test_message_includes_drop_details(self, tmp_path: Path) -> None:
        """Failure message includes test count details."""
        baseline_file = tmp_path / "baseline.json"
        baseline_file.write_text(json.dumps({"total_tests": 100}))
        passed, msg = check_test_count_regression(70, baseline_path=baseline_file)
        assert passed is False
        assert "70" in msg
        assert "100" in msg
        assert "30" in msg  # dropped count
