"""Tests for coverage_baseline.py - Coverage regression gate and skip rate monitoring.

TDD Red Phase: These tests define the expected behavior before implementation.
"""

import json
import sys
from pathlib import Path

import pytest

# Add library to path
sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "plugins" / "autonomous-dev" / "lib"))

from coverage_baseline import (
    check_coverage_regression,
    check_skip_rate,
    get_default_baseline_path,
    load_baseline,
    save_baseline,
)


class TestLoadBaseline:
    """Tests for load_baseline()."""

    def test_no_file_returns_empty_dict(self, tmp_path: Path) -> None:
        result = load_baseline(tmp_path / "nonexistent.json")
        assert result == {}

    def test_valid_json_returns_dict(self, tmp_path: Path) -> None:
        baseline_file = tmp_path / "baseline.json"
        data = {
            "total_coverage": 85.0,
            "skip_count": 3,
            "total_tests": 100,
            "timestamp": "2026-02-14T00:00:00",
        }
        baseline_file.write_text(json.dumps(data))

        result = load_baseline(baseline_file)
        assert result["total_coverage"] == 85.0
        assert result["skip_count"] == 3
        assert result["total_tests"] == 100
        assert "timestamp" in result

    def test_corrupted_json_returns_empty_dict(self, tmp_path: Path) -> None:
        baseline_file = tmp_path / "baseline.json"
        baseline_file.write_text("{invalid json content!!!")

        result = load_baseline(baseline_file)
        assert result == {}

    def test_custom_path_works(self, tmp_path: Path) -> None:
        custom = tmp_path / "sub" / "dir" / "custom.json"
        custom.parent.mkdir(parents=True)
        custom.write_text(json.dumps({"total_coverage": 90.0}))

        result = load_baseline(custom)
        assert result["total_coverage"] == 90.0


class TestSaveBaseline:
    """Tests for save_baseline()."""

    def test_creates_file_with_correct_structure(self, tmp_path: Path) -> None:
        baseline_file = tmp_path / "baseline.json"
        save_baseline(85.0, 3, 100, baseline_file)

        assert baseline_file.exists()
        data = json.loads(baseline_file.read_text())
        assert data["total_coverage"] == 85.0
        assert data["skip_count"] == 3
        assert data["total_tests"] == 100
        assert "timestamp" in data

    def test_creates_parent_directories(self, tmp_path: Path) -> None:
        baseline_file = tmp_path / "a" / "b" / "c" / "baseline.json"
        save_baseline(90.0, 0, 50, baseline_file)

        assert baseline_file.exists()

    def test_round_trip(self, tmp_path: Path) -> None:
        baseline_file = tmp_path / "baseline.json"
        save_baseline(87.5, 5, 200, baseline_file)

        result = load_baseline(baseline_file)
        assert result["total_coverage"] == 87.5
        assert result["skip_count"] == 5
        assert result["total_tests"] == 200


class TestCheckCoverageRegression:
    """Tests for check_coverage_regression()."""

    def test_no_baseline_establishes_new(self, tmp_path: Path, monkeypatch) -> None:
        monkeypatch.setattr(
            "coverage_baseline.get_default_baseline_path",
            lambda: tmp_path / "baseline.json",
        )
        passed, message = check_coverage_regression(85.0)
        assert passed is True
        assert "baseline" in message.lower() or "established" in message.lower()

    def test_current_above_baseline_passes(self, tmp_path: Path, monkeypatch) -> None:
        baseline_file = tmp_path / "baseline.json"
        save_baseline(80.0, 0, 100, baseline_file)
        monkeypatch.setattr(
            "coverage_baseline.get_default_baseline_path",
            lambda: baseline_file,
        )

        passed, message = check_coverage_regression(85.0)
        assert passed is True

    def test_current_below_tolerance_fails(self, tmp_path: Path, monkeypatch) -> None:
        baseline_file = tmp_path / "baseline.json"
        save_baseline(80.0, 0, 100, baseline_file)
        monkeypatch.setattr(
            "coverage_baseline.get_default_baseline_path",
            lambda: baseline_file,
        )

        passed, message = check_coverage_regression(78.0, tolerance=0.5)
        assert passed is False
        assert "regression" in message.lower()

    def test_within_tolerance_passes(self, tmp_path: Path, monkeypatch) -> None:
        baseline_file = tmp_path / "baseline.json"
        save_baseline(80.0, 0, 100, baseline_file)
        monkeypatch.setattr(
            "coverage_baseline.get_default_baseline_path",
            lambda: baseline_file,
        )

        passed, message = check_coverage_regression(79.8, tolerance=0.5)
        assert passed is True

    def test_exact_boundary_passes(self, tmp_path: Path, monkeypatch) -> None:
        baseline_file = tmp_path / "baseline.json"
        save_baseline(80.0, 0, 100, baseline_file)
        monkeypatch.setattr(
            "coverage_baseline.get_default_baseline_path",
            lambda: baseline_file,
        )

        # current == baseline - tolerance => should pass
        passed, _ = check_coverage_regression(79.5, tolerance=0.5)
        assert passed is True


class TestCheckSkipRate:
    """Tests for check_skip_rate()."""

    def test_zero_skipped_is_ok(self) -> None:
        status, message = check_skip_rate(0, 100)
        assert status == "ok"

    def test_five_percent_is_ok(self) -> None:
        status, message = check_skip_rate(5, 100)
        assert status == "ok"

    def test_seven_percent_is_warn(self) -> None:
        status, message = check_skip_rate(7, 100)
        assert status == "warn"

    def test_twelve_percent_is_block(self) -> None:
        status, message = check_skip_rate(12, 100)
        assert status == "block"


class TestGetDefaultBaselinePath:
    """Tests for get_default_baseline_path()."""

    def test_returns_path_object(self) -> None:
        result = get_default_baseline_path()
        assert isinstance(result, Path)

    def test_path_contains_coverage_baseline(self) -> None:
        result = get_default_baseline_path()
        assert "coverage_baseline.json" in str(result)
