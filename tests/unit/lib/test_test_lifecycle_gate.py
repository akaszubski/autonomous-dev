"""Unit tests for check_prunable_threshold() and PRUNABLE_THRESHOLD gate.

Tests the CI gate tooling added in Issue #736.
Updated in Issue #1317 to test deletable_file_count instead of raw prunable_count.
"""

import sys
from pathlib import Path

import pytest

# Path setup: tests/unit/lib/ -> parents[3] = repo root
REPO_ROOT = Path(__file__).resolve().parents[3]
LIB_PATH = REPO_ROOT / "plugins" / "autonomous-dev" / "lib"
sys.path.insert(0, str(LIB_PATH))

from test_lifecycle_manager import (
    PRUNABLE_THRESHOLD,
    TestHealthReport,
    TestHealthSummary,
    TestLifecycleManager,
    check_prunable_threshold,
)


def _make_report(
    *, 
    prunable_count: int = 0, 
    deletable_file_count: int = 0
) -> TestHealthReport:
    """Helper to create a TestHealthReport with given counts.
    
    Args:
        prunable_count: Number of prunable findings (for backward compat).
        deletable_file_count: Number of deletable files (what gate now uses).
    """
    report = TestHealthReport()
    report.summary = TestHealthSummary(
        prunable_count=prunable_count,
        deletable_file_count=deletable_file_count
    )
    return report


class TestCheckPrunableThreshold:
    """Tests for check_prunable_threshold()."""

    def test_threshold_passes_when_below_limit(self) -> None:
        """Deletable file count below threshold should pass."""
        report = _make_report(deletable_file_count=50)
        passed, msg = check_prunable_threshold(report)
        assert passed is True
        assert "within threshold" in msg

    def test_threshold_fails_when_above_limit(self) -> None:
        """Deletable file count above threshold should fail."""
        report = _make_report(deletable_file_count=150)
        passed, msg = check_prunable_threshold(report)
        assert passed is False
        assert "exceeds threshold" in msg
        assert "/sweep --tests --prune" in msg

    def test_threshold_custom_value(self) -> None:
        """Custom threshold value should be respected."""
        report = _make_report(deletable_file_count=20)
        # Should pass with threshold 50
        passed, msg = check_prunable_threshold(report, threshold=50)
        assert passed is True

        # Should fail with threshold 10
        passed, msg = check_prunable_threshold(report, threshold=10)
        assert passed is False

    def test_threshold_zero_deletable_passes(self) -> None:
        """Zero deletable files should always pass."""
        report = _make_report(deletable_file_count=0)
        passed, msg = check_prunable_threshold(report)
        assert passed is True
        assert "0" in msg

    def test_threshold_default_is_100(self) -> None:
        """Default PRUNABLE_THRESHOLD constant should be 100."""
        assert PRUNABLE_THRESHOLD == 100

    def test_threshold_at_exact_limit_passes(self) -> None:
        """Deletable file count exactly at threshold should pass (<=, not <)."""
        report = _make_report(deletable_file_count=100)
        passed, msg = check_prunable_threshold(report, threshold=100)
        assert passed is True
    
    def test_regression_issue_1317_known_counts(self) -> None:
        """Regression test for Issue #1317: known production counts should not trigger gate.
        
        Production has ~3913 findings, ~2394 prunable, but only 1 deletable file.
        The gate should PASS with 1 deletable file (not fail due to 2394 findings).
        """
        report = _make_report(
            prunable_count=2394,  # High raw finding count
            deletable_file_count=1  # But only 1 file can actually be deleted
        )
        passed, msg = check_prunable_threshold(report)
        assert passed is True, (
            f"Gate should pass with 1 deletable file, even with {report.summary.prunable_count} findings. "
            f"Got: {msg}"
        )
        assert "Deletable file count 1 within threshold" in msg
    
    def test_gate_still_fails_above_threshold(self) -> None:
        """Gate should still FAIL when deletable_file_count > 100."""
        report = _make_report(
            prunable_count=500,  # Some arbitrary high number
            deletable_file_count=101  # Just above threshold
        )
        passed, msg = check_prunable_threshold(report)
        assert passed is False
        assert "Deletable file count 101 exceeds threshold 100" in msg
        assert "/sweep --tests --prune" in msg
    
    def test_backward_compat_prunable_count_still_computed(self) -> None:
        """Backward compat: prunable_count should still be present in summary."""
        report = _make_report(
            prunable_count=42,
            deletable_file_count=5
        )
        # The field should exist and be accessible
        assert report.summary.prunable_count == 42
        # But the gate should use deletable_file_count
        passed, msg = check_prunable_threshold(report)
        assert passed is True
        assert "Deletable file count 5" in msg


class TestDashboardGateStatus:
    """Tests for gate status in format_dashboard output."""

    def test_dashboard_includes_gate_status_pass(self) -> None:
        """Dashboard should include Gate Status: PASS when below threshold."""
        report = _make_report(deletable_file_count=50)
        manager = TestLifecycleManager(REPO_ROOT)
        dashboard = manager.format_dashboard(report)
        assert "Gate Status: PASS" in dashboard
        assert "50 deletable files" in dashboard

    def test_dashboard_includes_gate_status_fail(self) -> None:
        """Dashboard should include Gate Status: FAIL when above threshold."""
        report = _make_report(deletable_file_count=200)
        manager = TestLifecycleManager(REPO_ROOT)
        dashboard = manager.format_dashboard(report)
        assert "Gate Status: FAIL" in dashboard
        assert "200 deletable files" in dashboard
        assert "/sweep --tests --prune" in dashboard
    
    def test_dashboard_shows_both_counts(self) -> None:
        """Dashboard should show both prunable candidates and deletable files."""
        report = _make_report(
            prunable_count=2394,
            deletable_file_count=1
        )
        # Set total_findings so it appears in summary
        report.summary.total_findings = 3913
        
        manager = TestLifecycleManager(REPO_ROOT)
        dashboard = manager.format_dashboard(report)
        
        # Check that dashboard includes both metrics
        assert "Prunable candidates: 2394" in dashboard
        assert "Deletable files: 1" in dashboard
        assert "Total findings: 3913" in dashboard
        
        # And the gate uses deletable files
        assert "Gate Status: PASS" in dashboard
        assert "1 deletable files" in dashboard
