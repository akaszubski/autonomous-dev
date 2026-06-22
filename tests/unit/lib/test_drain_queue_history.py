"""Unit tests for DrainHistory metrics round-trip and _empty_metrics sentinel.

Tests for Phase C metrics capture (Issue #1290). All tests are pure data-layer
tests using tmp_path — no subprocess calls.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

_LIB = Path(__file__).resolve().parents[3] / "plugins" / "autonomous-dev" / "lib"
if str(_LIB) not in sys.path:
    sys.path.insert(0, str(_LIB))

from drain_queue_state import DrainHistory, _empty_metrics  # noqa: E402


# =============================================================================
# Tests
# =============================================================================


class TestAppendWithMetricsRoundTrip:
    """Write + read back records with new before/after metrics fields."""

    def test_append_with_metrics_round_trip(self, tmp_path: Path) -> None:
        """Records written with before_metrics/after_metrics survive read_all."""
        history = DrainHistory.load(tmp_path)
        before = {"test_count": 42, "failing_tests": 0, "coverage_pct": None, "error": None}
        after = {"test_count": 45, "failing_tests": 0, "coverage_pct": None, "error": None}
        history.append({
            "outcome": "success",
            "cluster_id": "CI#1",
            "issue_numbers": [100, 101],
            "wall_seconds": 120.5,
            "before_metrics": before,
            "after_metrics": after,
        })
        records = history.read_all()
        assert len(records) == 1
        rec = records[0]
        assert rec["outcome"] == "success"
        assert rec["cluster_id"] == "CI#1"
        assert rec["before_metrics"] == before
        assert rec["after_metrics"] == after

    def test_before_after_metrics_are_preserved_verbatim(self, tmp_path: Path) -> None:
        """Metrics dicts are stored as-is (no key mangling or coercion)."""
        history = DrainHistory.load(tmp_path)
        metrics = {"test_count": 7, "failing_tests": 2, "coverage_pct": None, "error": None}
        history.append({"outcome": "success", "cluster_id": "X#0", "before_metrics": metrics})
        rec = history.read_all()[0]
        assert rec["before_metrics"]["test_count"] == 7
        assert rec["before_metrics"]["failing_tests"] == 2
        assert rec["before_metrics"]["coverage_pct"] is None
        assert rec["before_metrics"]["error"] is None


class TestAppendWithoutMetricsBackwardCompat:
    """Write without metrics keys — existing records must not be corrupted."""

    def test_append_without_metrics_backward_compat(self, tmp_path: Path) -> None:
        """Records without before/after metrics keys are readable without error."""
        history = DrainHistory.load(tmp_path)
        # Legacy record without any metrics keys.
        history.append({
            "outcome": "success",
            "cluster_id": "OLD#1",
            "issue_numbers": [9, 10],
            "wall_seconds": 60.0,
        })
        records = history.read_all()
        assert len(records) == 1
        rec = records[0]
        assert rec["outcome"] == "success"
        assert rec["cluster_id"] == "OLD#1"
        # Keys absent — consumers MUST check before accessing.
        assert "before_metrics" not in rec
        assert "after_metrics" not in rec


class TestEmptyMetricsStructure:
    """_empty_metrics() returns the expected shape."""

    def test_empty_metrics_structure(self) -> None:
        """Sentinel dict has all four expected keys, all None."""
        m = _empty_metrics()
        assert isinstance(m, dict)
        assert set(m.keys()) == {"test_count", "failing_tests", "coverage_pct", "error"}
        assert m["test_count"] is None
        assert m["failing_tests"] is None
        assert m["coverage_pct"] is None
        assert m["error"] is None

    def test_empty_metrics_returns_new_dict_each_call(self) -> None:
        """Each call returns an independent dict (not a shared singleton)."""
        a = _empty_metrics()
        b = _empty_metrics()
        a["error"] = "mutated"
        assert b["error"] is None


class TestMetricsDeltaPositive:
    """After drain, test count increases (sanity check on delta logic)."""

    def test_metrics_delta_positive(self, tmp_path: Path) -> None:
        """Drain adds tests: after.test_count > before.test_count."""
        history = DrainHistory.load(tmp_path)
        before = {"test_count": 30, "failing_tests": 0, "coverage_pct": None, "error": None}
        after = {"test_count": 35, "failing_tests": 0, "coverage_pct": None, "error": None}
        history.append({
            "outcome": "success",
            "cluster_id": "PERF#2",
            "before_metrics": before,
            "after_metrics": after,
        })
        rec = history.read_all()[0]
        delta = rec["after_metrics"]["test_count"] - rec["before_metrics"]["test_count"]
        assert delta > 0, f"Expected positive delta, got {delta}"


class TestMetricsDeltaNewFailing:
    """Drain introduces a regression: after has failing_tests=1, before=0."""

    def test_metrics_delta_new_failing(self, tmp_path: Path) -> None:
        """Records where after.failing_tests > before.failing_tests are readable."""
        history = DrainHistory.load(tmp_path)
        before = {"test_count": 20, "failing_tests": 0, "coverage_pct": None, "error": None}
        after = {"test_count": 21, "failing_tests": 1, "coverage_pct": None, "error": None}
        history.append({
            "outcome": "success",
            "cluster_id": "BUG#5",
            "before_metrics": before,
            "after_metrics": after,
        })
        rec = history.read_all()[0]
        assert rec["after_metrics"]["failing_tests"] == 1
        assert rec["before_metrics"]["failing_tests"] == 0
        regression = rec["after_metrics"]["failing_tests"] - rec["before_metrics"]["failing_tests"]
        assert regression == 1


class TestMetricsDeltaCoverageDrop:
    """Coverage dropped from 80 to 75 — delta captured correctly."""

    def test_metrics_delta_coverage_drop(self, tmp_path: Path) -> None:
        """Coverage drop is stored and readable from history."""
        history = DrainHistory.load(tmp_path)
        before = {"test_count": 50, "failing_tests": 0, "coverage_pct": 80.0, "error": None}
        after = {"test_count": 50, "failing_tests": 0, "coverage_pct": 75.0, "error": None}
        history.append({
            "outcome": "success",
            "cluster_id": "COV#3",
            "before_metrics": before,
            "after_metrics": after,
        })
        rec = history.read_all()[0]
        assert rec["before_metrics"]["coverage_pct"] == 80.0
        assert rec["after_metrics"]["coverage_pct"] == 75.0
        drop = rec["before_metrics"]["coverage_pct"] - rec["after_metrics"]["coverage_pct"]
        assert drop == pytest.approx(5.0)


class TestFileIsJsonlParseable:
    """Mixed-schema appends (legacy + new metrics) remain JSON-parseable per line."""

    def test_file_is_jsonl_parseable(self, tmp_path: Path) -> None:
        """Every line in the JSONL file parses as valid JSON regardless of schema."""
        history = DrainHistory.load(tmp_path)

        # Legacy record (no metrics keys).
        history.append({
            "outcome": "success",
            "cluster_id": "LEGACY#1",
            "wall_seconds": 30.0,
        })

        # New-style record with empty metrics sentinel.
        sentinel = _empty_metrics()
        sentinel["error"] = "pytest_not_found"
        history.append({
            "outcome": "success",
            "cluster_id": "NEW#2",
            "wall_seconds": 45.0,
            "before_metrics": sentinel,
            "after_metrics": _empty_metrics(),
        })

        # Full metrics record.
        history.append({
            "outcome": "success",
            "cluster_id": "NEW#3",
            "wall_seconds": 90.0,
            "before_metrics": {"test_count": 10, "failing_tests": 0, "coverage_pct": None, "error": None},
            "after_metrics": {"test_count": 12, "failing_tests": 0, "coverage_pct": None, "error": None},
        })

        # Read the raw JSONL file and parse each line independently.
        log_path = tmp_path / ".claude" / "local" / "drain_log.jsonl"
        assert log_path.exists(), "JSONL file was not created"
        lines = log_path.read_text(encoding="utf-8").strip().splitlines()
        assert len(lines) == 3, f"Expected 3 lines, got {len(lines)}"
        for i, line in enumerate(lines):
            parsed = json.loads(line)  # Must not raise
            assert isinstance(parsed, dict), f"Line {i} is not a JSON object"
            assert "cluster_id" in parsed, f"Line {i} missing cluster_id"
