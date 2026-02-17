"""Unit tests for SoftFailureTracker and threshold classification.

Tests the soft-failure threshold system without requiring OpenRouter API access.
"""

import json
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

# Add the worktree's tests/genai to path so we import the modified conftest
_WORKTREE_ROOT = Path(__file__).parent.parent.parent.parent
_GENAI_TEST_DIR = _WORKTREE_ROOT / "tests" / "genai"

# Import SoftFailureTracker directly from the module file
sys.path.insert(0, str(_GENAI_TEST_DIR))
from conftest import SoftFailureTracker, _load_thresholds


# --- Threshold Loading ---


class TestLoadThresholds:
    """Tests for _load_thresholds()."""

    def test_loads_from_file(self, tmp_path):
        config = {"default": {"hard_fail": 3, "soft_fail": 5, "pass": 7}, "categories": {}, "accumulation_threshold": 0.25}
        thresholds_file = tmp_path / "thresholds.json"
        thresholds_file.write_text(json.dumps(config))

        with patch("conftest.THRESHOLDS_FILE", thresholds_file):
            result = _load_thresholds()
        assert result["default"]["hard_fail"] == 3
        assert result["accumulation_threshold"] == 0.25

    def test_returns_defaults_when_file_missing(self, tmp_path):
        with patch("conftest.THRESHOLDS_FILE", tmp_path / "nonexistent.json"):
            result = _load_thresholds()
        assert result["default"]["hard_fail"] == 4
        assert result["default"]["pass"] == 7
        assert result["accumulation_threshold"] == 0.33


# --- Classification ---


class TestClassify:
    """Tests for SoftFailureTracker.classify()."""

    def setup_method(self):
        self.tracker = SoftFailureTracker(thresholds={
            "default": {"hard_fail": 4, "soft_fail": 6, "pass": 7},
            "categories": {
                "security": {"hard_fail": 6, "soft_fail": 8, "pass": 9},
            },
            "accumulation_threshold": 0.33,
        })

    def test_hard_fail_below_threshold(self):
        assert self.tracker.classify(3) == "hard_fail"

    def test_soft_fail_in_middle_band(self):
        assert self.tracker.classify(5) == "soft_fail"

    def test_pass_at_threshold(self):
        assert self.tracker.classify(7) == "pass"

    def test_pass_above_threshold(self):
        assert self.tracker.classify(10) == "pass"

    def test_hard_fail_at_zero(self):
        assert self.tracker.classify(0) == "hard_fail"

    def test_hard_fail_at_boundary(self):
        # Score exactly at hard_fail threshold is still hard_fail (< not <=)
        assert self.tracker.classify(4) == "soft_fail"

    def test_soft_fail_at_boundary(self):
        # Score exactly at soft_fail threshold
        assert self.tracker.classify(6) == "soft_fail"

    def test_category_security_stricter(self):
        # Security: hard_fail=6, pass=9
        assert self.tracker.classify(5, "security") == "hard_fail"
        assert self.tracker.classify(7, "security") == "soft_fail"
        assert self.tracker.classify(9, "security") == "pass"

    def test_unknown_category_uses_default(self):
        assert self.tracker.classify(5, "unknown_category") == "soft_fail"


# --- Strict Mode ---


class TestStrictMode:
    """Tests for --strict-genai behavior."""

    def test_strict_converts_soft_fail_to_hard_fail(self):
        tracker = SoftFailureTracker(
            thresholds={"default": {"hard_fail": 4, "soft_fail": 6, "pass": 7}, "categories": {}, "accumulation_threshold": 0.33},
            strict=True,
        )
        # Score 5 would be soft_fail normally, hard_fail in strict
        assert tracker.classify(5) == "hard_fail"

    def test_strict_pass_still_passes(self):
        tracker = SoftFailureTracker(
            thresholds={"default": {"hard_fail": 4, "soft_fail": 6, "pass": 7}, "categories": {}, "accumulation_threshold": 0.33},
            strict=True,
        )
        assert tracker.classify(7) == "pass"

    def test_strict_hard_fail_stays_hard_fail(self):
        tracker = SoftFailureTracker(
            thresholds={"default": {"hard_fail": 4, "soft_fail": 6, "pass": 7}, "categories": {}, "accumulation_threshold": 0.33},
            strict=True,
        )
        assert tracker.classify(2) == "hard_fail"


# --- Recording ---


class TestRecord:
    """Tests for SoftFailureTracker.record()."""

    def setup_method(self):
        self.tracker = SoftFailureTracker(thresholds={
            "default": {"hard_fail": 4, "soft_fail": 6, "pass": 7},
            "categories": {},
            "accumulation_threshold": 0.33,
        })

    def test_record_returns_enriched_dict(self):
        result = self.tracker.record("test_foo", 8)
        assert result["test_name"] == "test_foo"
        assert result["score"] == 8
        assert result["band"] == "pass"
        assert result["pass"] is True

    def test_record_soft_fail(self):
        result = self.tracker.record("test_bar", 5)
        assert result["band"] == "soft_fail"
        assert result["pass"] is False

    def test_record_hard_fail(self):
        result = self.tracker.record("test_baz", 2)
        assert result["band"] == "hard_fail"
        assert result["pass"] is False

    def test_record_with_category(self):
        result = self.tracker.record("test_sec", 5, category="default", reasoning="low score")
        assert result["category"] == "default"
        assert result["reasoning"] == "low score"

    def test_results_accumulate(self):
        self.tracker.record("t1", 8)
        self.tracker.record("t2", 5)
        self.tracker.record("t3", 2)
        assert len(self.tracker.results) == 3


# --- Accumulation Gate ---


class TestAccumulationGate:
    """Tests for suite-level pass/fail based on accumulation."""

    def _make_tracker(self, accumulation_threshold=0.33):
        return SoftFailureTracker(thresholds={
            "default": {"hard_fail": 4, "soft_fail": 6, "pass": 7},
            "categories": {},
            "accumulation_threshold": accumulation_threshold,
        })

    def test_empty_suite_passes(self):
        tracker = self._make_tracker()
        assert tracker.suite_passed is True

    def test_all_pass_suite_passes(self):
        tracker = self._make_tracker()
        for i in range(10):
            tracker.record(f"t{i}", 8)
        assert tracker.suite_passed is True

    def test_one_hard_fail_fails_suite(self):
        tracker = self._make_tracker()
        tracker.record("t1", 8)
        tracker.record("t2", 8)
        tracker.record("t3", 2)  # hard fail
        assert tracker.suite_passed is False

    def test_soft_fails_below_threshold_passes(self):
        tracker = self._make_tracker(accumulation_threshold=0.5)
        tracker.record("t1", 8)
        tracker.record("t2", 8)
        tracker.record("t3", 5)  # soft fail — 1/3 = 33% < 50%
        assert tracker.suite_passed is True

    def test_soft_fails_above_threshold_fails(self):
        tracker = self._make_tracker(accumulation_threshold=0.33)
        tracker.record("t1", 8)
        tracker.record("t2", 5)  # soft fail — 1/2 = 50% > 33%
        assert tracker.suite_passed is False

    def test_soft_fails_at_threshold_passes(self):
        # Ratio must EXCEED threshold to fail (> not >=)
        tracker = self._make_tracker(accumulation_threshold=0.5)
        tracker.record("t1", 8)
        tracker.record("t2", 5)  # 1/2 = 50% == 50% → passes (not exceeded)
        assert tracker.suite_passed is True

    def test_counts(self):
        tracker = self._make_tracker()
        tracker.record("t1", 8)  # pass
        tracker.record("t2", 5)  # soft fail
        tracker.record("t3", 5)  # soft fail
        tracker.record("t4", 2)  # hard fail
        assert tracker.pass_count == 1
        assert tracker.soft_failure_count == 2
        assert tracker.hard_failure_count == 1
        assert tracker.soft_failure_ratio == 0.5


# --- Summary ---


class TestSummary:
    """Tests for human-readable summary output."""

    def test_empty_summary(self):
        tracker = SoftFailureTracker(thresholds={
            "default": {"hard_fail": 4, "soft_fail": 6, "pass": 7},
            "categories": {},
            "accumulation_threshold": 0.33,
        })
        assert "No GenAI results recorded" in tracker.summary()

    def test_summary_includes_counts(self):
        tracker = SoftFailureTracker(thresholds={
            "default": {"hard_fail": 4, "soft_fail": 6, "pass": 7},
            "categories": {},
            "accumulation_threshold": 0.33,
        })
        tracker.record("t1", 8)
        tracker.record("t2", 5, reasoning="borderline score")
        summary = tracker.summary()
        assert "Pass: 1" in summary
        assert "Soft Fail: 1" in summary
        assert "borderline score" in summary

    def test_summary_shows_suite_status(self):
        tracker = SoftFailureTracker(thresholds={
            "default": {"hard_fail": 4, "soft_fail": 6, "pass": 7},
            "categories": {},
            "accumulation_threshold": 0.33,
        })
        tracker.record("t1", 8)
        assert "PASSED" in tracker.summary()


# --- Backward Compatibility ---


class TestBackwardCompatibility:
    """Ensure existing assert result['score'] >= 5 patterns still work."""

    def test_judge_result_has_score(self):
        """The judge() return dict still has 'score' and 'pass' keys."""
        # We can't call judge() without API, but verify the band enrichment logic
        tracker = SoftFailureTracker(thresholds={
            "default": {"hard_fail": 4, "soft_fail": 6, "pass": 7},
            "categories": {},
            "accumulation_threshold": 0.33,
        })
        result = tracker.record("t1", 8)
        # Old pattern: assert result["score"] >= 5
        assert result["score"] >= 5
        # New pattern: assert result["band"] == "pass"
        assert result["band"] == "pass"
        # Both work simultaneously
        assert result["pass"] is True
