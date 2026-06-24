"""Unit tests for test_lifecycle_manager.py

Tests validate the TestLifecycleManager composition layer that orchestrates
existing analyzers (TestIssueTracer, TestPruningAnalyzer, tier_registry,
coverage_baseline) into a unified health dashboard.

Issue: #673
Run with: pytest tests/unit/lib/test_test_lifecycle_manager.py --tb=short -v
"""

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# Ensure lib is importable
sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "plugins" / "autonomous-dev" / "lib"))

from test_lifecycle_manager import (
    TestHealthReport,
    TestHealthSummary,
    TestLifecycleManager,
    check_issue_tracing,
)
from test_issue_tracer import TracingCategory, TracingFinding, TracingReport
from test_pruning_analyzer import PruningCategory, PruningFinding, PruningReport, Severity


class TestAnalyzeReturnsHealthReport:
    """Test that analyze() returns a properly populated TestHealthReport."""

    def test_analyze_returns_health_report(self, tmp_path: Path) -> None:
        """analyze() returns a TestHealthReport instance with all sections."""
        (tmp_path / "tests").mkdir()
        (tmp_path / "tests" / "test_sample.py").write_text("def test_one(): assert True\n")

        manager = TestLifecycleManager(tmp_path)

        with patch.object(manager, "_collect_test_paths", return_value=[]):
            report = manager.analyze()

        assert isinstance(report, TestHealthReport)
        assert isinstance(report.summary, TestHealthSummary)
        assert report.scan_duration_ms > 0

    def test_analyze_populates_tracing(self, tmp_path: Path) -> None:
        """analyze() populates the tracing section from TestIssueTracer."""
        (tmp_path / "tests").mkdir()
        manager = TestLifecycleManager(tmp_path)

        mock_tracing = TracingReport(
            findings=[
                TracingFinding(
                    category=TracingCategory.UNTRACED_TEST,
                    severity="info",
                    description="Test file has no issue references",
                    file_path="tests/test_foo.py",
                ),
            ],
            references=[],
            scan_duration_ms=10.0,
            issues_scanned=0,
            tests_scanned=1,
        )

        with patch(
            "test_lifecycle_manager.TestIssueTracer"
        ) as MockTracer:
            MockTracer.return_value.analyze.return_value = mock_tracing
            report = manager.analyze()

        assert report.tracing is not None
        assert len(report.tracing.findings) == 1
        assert report.tracing.findings[0].category == TracingCategory.UNTRACED_TEST

    def test_analyze_populates_pruning(self, tmp_path: Path) -> None:
        """analyze() populates the pruning section from TestPruningAnalyzer."""
        (tmp_path / "tests").mkdir()
        manager = TestLifecycleManager(tmp_path)

        mock_pruning = PruningReport(
            findings=[
                PruningFinding(
                    file_path="tests/unit/test_old.py",
                    line=1,
                    category=PruningCategory.ZERO_ASSERTION,
                    severity=Severity.HIGH,
                    description="Test has no assertions",
                    suggestion="Add assertions",
                    prunable=True,
                ),
            ],
            scan_duration_ms=5.0,
            files_scanned=1,
        )

        with patch(
            "test_lifecycle_manager.TestPruningAnalyzer"
        ) as MockPruner:
            MockPruner.return_value.analyze.return_value = mock_pruning
            report = manager.analyze()

        assert report.pruning is not None
        assert len(report.pruning.findings) == 1


class TestSummaryCounts:
    """Test that summary correctly aggregates counts from sub-reports."""

    def test_summary_counts_tracing_findings(self, tmp_path: Path) -> None:
        """Summary correctly counts untraced, orphaned, and untested from tracing."""
        manager = TestLifecycleManager(tmp_path)

        tracing = TracingReport(
            findings=[
                TracingFinding(
                    category=TracingCategory.UNTRACED_TEST,
                    severity="info",
                    description="untraced",
                ),
                TracingFinding(
                    category=TracingCategory.UNTRACED_TEST,
                    severity="info",
                    description="untraced 2",
                ),
                TracingFinding(
                    category=TracingCategory.ORPHANED_PAIR,
                    severity="info",
                    description="orphaned",
                    issue_number=42,
                ),
                TracingFinding(
                    category=TracingCategory.UNTESTED_ISSUE,
                    severity="info",
                    description="untested",
                    issue_number=99,
                ),
            ],
        )

        report = TestHealthReport(tracing=tracing)
        summary = manager._compute_summary(report)

        assert summary.untraced_test_count == 2
        assert summary.orphaned_pair_count == 1
        assert summary.untested_issue_count == 1
        assert summary.total_findings == 4

    def test_summary_counts_prunable(self, tmp_path: Path) -> None:
        """Summary correctly counts prunable findings from pruning report."""
        manager = TestLifecycleManager(tmp_path)

        pruning = PruningReport(
            findings=[
                PruningFinding(
                    file_path="tests/unit/test_a.py", line=1,
                    category=PruningCategory.DEAD_IMPORT, severity=Severity.HIGH,
                    description="dead", suggestion="remove", prunable=True,
                ),
                PruningFinding(
                    file_path="tests/integration/test_b.py", line=1,
                    category=PruningCategory.DEAD_IMPORT, severity=Severity.HIGH,
                    description="dead", suggestion="remove", prunable=False,
                ),
            ],
        )

        report = TestHealthReport(pruning=pruning)
        summary = manager._compute_summary(report)

        assert summary.prunable_count == 1
        assert summary.total_findings == 2


class TestTierBalance:
    """Test tier_balance assessment logic."""

    def test_healthy_balance(self, tmp_path: Path) -> None:
        """Mixed distribution across tiers is 'healthy'."""
        manager = TestLifecycleManager(tmp_path)
        dist = {"T0": 5, "T1": 10, "T2": 15, "T3": 20}
        assert manager._assess_tier_balance(dist) == "healthy"

    def test_bottom_heavy(self, tmp_path: Path) -> None:
        """Almost all tests in T2+T3 with <10% in T0+T1 is 'bottom-heavy'."""
        manager = TestLifecycleManager(tmp_path)
        dist = {"T0": 0, "T1": 1, "T2": 30, "T3": 70}
        assert manager._assess_tier_balance(dist) == "bottom-heavy"

    def test_top_heavy(self, tmp_path: Path) -> None:
        """>80% in T0+T1 is 'top-heavy'."""
        manager = TestLifecycleManager(tmp_path)
        dist = {"T0": 50, "T1": 40, "T2": 5, "T3": 5}
        assert manager._assess_tier_balance(dist) == "top-heavy"

    def test_empty_distribution(self, tmp_path: Path) -> None:
        """Empty distribution returns 'unknown'."""
        manager = TestLifecycleManager(tmp_path)
        assert manager._assess_tier_balance({}) == "unknown"

    def test_zero_total(self, tmp_path: Path) -> None:
        """All-zero distribution returns 'unknown'."""
        manager = TestLifecycleManager(tmp_path)
        dist = {"T0": 0, "T1": 0, "T2": 0, "T3": 0}
        assert manager._assess_tier_balance(dist) == "unknown"


class TestFormatDashboard:
    """Test dashboard markdown formatting."""

    def test_dashboard_contains_key_sections(self, tmp_path: Path) -> None:
        """Dashboard includes summary, tier distribution, and coverage sections."""
        manager = TestLifecycleManager(tmp_path)
        report = TestHealthReport(
            tier_distribution={"T0": 3, "T3": 10},
            coverage_baseline={"total_coverage": 82.5, "skip_count": 4, "total_tests": 200},
            summary=TestHealthSummary(
                total_findings=5,
                prunable_count=2,
                untraced_test_count=3,
                tier_balance="healthy",
            ),
            scan_duration_ms=42.0,
        )

        dashboard = manager.format_dashboard(report)

        assert "# Test Health Dashboard" in dashboard
        assert "## Summary" in dashboard
        assert "Total findings: 5" in dashboard
        assert "Prunable candidates: 2" in dashboard
        assert "Tier balance: healthy" in dashboard
        assert "## Tier Distribution" in dashboard
        assert "T0: 3 tests" in dashboard
        assert "T3: 10 tests" in dashboard
        assert "## Coverage Baseline" in dashboard
        assert "Coverage: 82.5%" in dashboard
        assert "Skipped: 4" in dashboard

    def test_dashboard_shows_errors(self, tmp_path: Path) -> None:
        """Dashboard includes error section when analyzers fail."""
        manager = TestLifecycleManager(tmp_path)
        report = TestHealthReport(
            errors=["TestIssueTracer failed: gh not found"],
            scan_duration_ms=1.0,
        )

        dashboard = manager.format_dashboard(report)

        assert "## Errors" in dashboard
        assert "TestIssueTracer failed: gh not found" in dashboard


class TestCheckIssueTracing:
    """Test the check_issue_tracing convenience function."""

    def test_returns_warning_for_untraced_issue(self, tmp_path: Path) -> None:
        """Returns a warning string when issue has no test references."""
        (tmp_path / "tests").mkdir()

        with patch(
            "test_lifecycle_manager.TestIssueTracer"
        ) as MockTracer:
            MockTracer.return_value.check_issue_has_test.return_value = False
            result = check_issue_tracing(tmp_path, 42)

        assert "WARNING" in result
        assert "#42" in result

    def test_returns_empty_for_traced_issue(self, tmp_path: Path) -> None:
        """Returns empty string when issue has test references."""
        with patch(
            "test_lifecycle_manager.TestIssueTracer"
        ) as MockTracer:
            MockTracer.return_value.check_issue_has_test.return_value = True
            result = check_issue_tracing(tmp_path, 42)

        assert result == ""

    def test_returns_empty_for_zero_issue(self, tmp_path: Path) -> None:
        """Returns empty string for issue number <= 0."""
        result = check_issue_tracing(tmp_path, 0)
        assert result == ""

    def test_returns_empty_on_exception(self, tmp_path: Path) -> None:
        """Returns empty string if tracer raises an exception."""
        with patch(
            "test_lifecycle_manager.TestIssueTracer"
        ) as MockTracer:
            MockTracer.return_value.check_issue_has_test.side_effect = RuntimeError("boom")
            result = check_issue_tracing(tmp_path, 42)

        assert result == ""


class TestAnalyzerFailureIsolation:
    """Test that individual analyzer failures produce partial reports."""

    def test_tracing_failure_yields_partial_report(self, tmp_path: Path) -> None:
        """When TestIssueTracer fails, report has tracing=None and error logged."""
        manager = TestLifecycleManager(tmp_path)

        with patch(
            "test_lifecycle_manager.TestIssueTracer"
        ) as MockTracer:
            MockTracer.return_value.analyze.side_effect = RuntimeError("tracer broken")
            report = manager.analyze()

        assert report.tracing is None
        assert any("TestIssueTracer failed" in e for e in report.errors)
        # Other sections should still be attempted
        assert isinstance(report.summary, TestHealthSummary)

    def test_pruning_failure_yields_partial_report(self, tmp_path: Path) -> None:
        """When TestPruningAnalyzer fails, report has pruning=None and error logged."""
        manager = TestLifecycleManager(tmp_path)

        with patch(
            "test_lifecycle_manager.TestPruningAnalyzer"
        ) as MockPruner:
            MockPruner.return_value.analyze.side_effect = RuntimeError("pruner broken")
            report = manager.analyze()

        assert report.pruning is None
        assert any("TestPruningAnalyzer failed" in e for e in report.errors)


class TestEmptyProject:
    """Test behavior with an empty project directory."""

    def test_empty_project_returns_valid_report(self, tmp_path: Path) -> None:
        """An empty project produces a valid but empty report."""
        manager = TestLifecycleManager(tmp_path)
        report = manager.analyze()

        assert isinstance(report, TestHealthReport)
        assert report.summary.total_findings == 0
        assert report.summary.tier_balance == "unknown"
        assert report.scan_duration_ms > 0


class TestTierDistributionGate:
    """Test the tier distribution gate warning logic."""

    def test_healthy_distribution_passes(self) -> None:
        """A healthy 5:2:2:1 distribution passes with no warning."""
        from test_lifecycle_manager import check_tier_distribution

        tier_dist = {"T0": 10, "T1": 20, "T2": 20, "T3": 50}
        passed, msg = check_tier_distribution(tier_dist)

        assert passed is True
        assert msg == "OK"

    def test_bottom_heavy_distribution_warns(self) -> None:
        """A distribution with T3=900 and tiny others warns as bottom-heavy."""
        from test_lifecycle_manager import check_tier_distribution

        tier_dist = {"T0": 10, "T1": 10, "T2": 10, "T3": 900}
        passed, msg = check_tier_distribution(tier_dist)

        assert passed is False
        assert "too bottom-heavy" in msg
        # Should mention the actual percentage
        assert "3.2%" in msg or "3.1%" in msg  # (10+10+10)/930 = ~3.2%

    def test_empty_distribution_passes(self) -> None:
        """An empty distribution passes without division by zero."""
        from test_lifecycle_manager import check_tier_distribution

        # Empty dict
        passed, msg = check_tier_distribution({})
        assert passed is True
        assert msg == "OK"

        # All zeros
        tier_dist = {"T0": 0, "T1": 0, "T2": 0, "T3": 0}
        passed, msg = check_tier_distribution(tier_dist)
        assert passed is True
        assert msg == "OK"

    def test_missing_t0_entirely_warns(self) -> None:
        """Missing T0 tier entirely causes drift warning."""
        from test_lifecycle_manager import check_tier_distribution

        # T0 missing entirely (0%) when target is 10%
        tier_dist = {"T1": 20, "T2": 20, "T3": 60}
        passed, msg = check_tier_distribution(tier_dist)

        assert passed is False
        # T0 at 0% drifts 100% from target 10%
        assert "T0" in msg
        assert "drift" in msg

    def test_exactly_25_percent_upper_tiers_passes(self) -> None:
        """Boundary case: T0+T1+T2 == exactly 25% passes."""
        from test_lifecycle_manager import check_tier_distribution

        # 25% in upper tiers (25/100), 75% in T3
        tier_dist = {"T0": 5, "T1": 10, "T2": 10, "T3": 75}
        passed, msg = check_tier_distribution(tier_dist)

        assert passed is True
        assert msg == "OK"

    def test_tier_balance_gate_in_dashboard(self, tmp_path: Path) -> None:
        """Tier Balance Gate line appears in dashboard output."""
        from test_lifecycle_manager import TestLifecycleManager, TestHealthReport

        manager = TestLifecycleManager(tmp_path)
        report = TestHealthReport()
        report.tier_distribution = {"T0": 5, "T1": 5, "T2": 5, "T3": 85}

        dashboard = manager.format_dashboard(report)

        assert "Tier Balance Gate:" in dashboard
        # Should show warning for bottom-heavy distribution
        assert "WARNING" in dashboard
        assert "too bottom-heavy" in dashboard
