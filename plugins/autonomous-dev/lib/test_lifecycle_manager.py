"""Test Lifecycle Manager -- orchestrates existing test analyzers into a unified health report.

Composes TestIssueTracer, TestPruningAnalyzer, tier_registry, and coverage_baseline
into a single dashboard. This is a composition layer -- all analysis logic lives in
the underlying analyzers.

Usage:
    from test_lifecycle_manager import TestLifecycleManager
    from pathlib import Path

    manager = TestLifecycleManager(Path("."))
    report = manager.analyze()
    print(manager.format_dashboard(report))

Issue: #673
Date: 2026-04-07
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)

# Maximum number of prunable findings before the gate fails.
# Run `/sweep --tests --prune` to reduce the count.
PRUNABLE_THRESHOLD = 100

# Target tier distribution (ratio out of 10)
# T0: acceptance tests, T1: unit tests, T2: integration tests, T3: regression tests
TIER_DISTRIBUTION_TARGETS = {"T0": 1, "T1": 2, "T2": 2, "T3": 5}

# Import existing analyzers with fallback for both installed and dev paths
try:
    from test_issue_tracer import TestIssueTracer, TracingReport
except ImportError:
    from plugins.autonomous_dev.lib.test_issue_tracer import TestIssueTracer, TracingReport

try:
    from test_pruning_analyzer import TestPruningAnalyzer, PruningReport
except ImportError:
    from plugins.autonomous_dev.lib.test_pruning_analyzer import TestPruningAnalyzer, PruningReport

try:
    from tier_registry import get_all_tiers, get_tier_distribution
except ImportError:
    from plugins.autonomous_dev.lib.tier_registry import get_all_tiers, get_tier_distribution

try:
    from coverage_baseline import load_baseline
except ImportError:
    from plugins.autonomous_dev.lib.coverage_baseline import load_baseline


@dataclass
class TestHealthSummary:
    """Aggregated summary metrics from all analyzers.

    Args:
        total_findings: Combined finding count across all analyzers.
        prunable_count: Number of prunable test findings.
        untraced_test_count: Test files with no issue references.
        orphaned_pair_count: Tests referencing closed issues.
        untested_issue_count: Open issues with no test references.
        tier_balance: Overall tier balance assessment.
    """

    total_findings: int = 0
    prunable_count: int = 0
    untraced_test_count: int = 0
    orphaned_pair_count: int = 0
    untested_issue_count: int = 0
    tier_balance: str = "unknown"


@dataclass
class TestHealthReport:
    """Complete test health report combining all analyzer outputs.

    Args:
        tracing: TracingReport from TestIssueTracer, or None on failure.
        pruning: PruningReport from TestPruningAnalyzer, or None on failure.
        tier_distribution: Mapping of tier_id to test count.
        coverage_baseline: Coverage baseline dict, or None on failure.
        summary: Aggregated summary metrics.
        scan_duration_ms: Total scan time in milliseconds.
        errors: List of error messages from failed analyzers.
    """

    tracing: Optional[TracingReport] = None
    pruning: Optional[PruningReport] = None
    tier_distribution: Dict[str, int] = field(default_factory=dict)
    coverage_baseline: Optional[dict] = None
    summary: TestHealthSummary = field(default_factory=TestHealthSummary)
    scan_duration_ms: float = 0.0
    errors: List[str] = field(default_factory=list)


class TestLifecycleManager:
    """Orchestrates existing test analyzers into a unified health dashboard.

    This is a composition layer. All analysis logic lives in the underlying
    analyzers (TestIssueTracer, TestPruningAnalyzer, tier_registry, coverage_baseline).
    Each analyzer is called in isolation with error boundaries so a single
    failure does not block the entire report.

    Args:
        project_root: Root directory of the project to analyze.
    """

    def __init__(self, project_root: Path) -> None:
        self.project_root = project_root

    def analyze(self) -> TestHealthReport:
        """Run all analyzers with error isolation and return a unified report.

        Each analyzer is wrapped in a try/except so a single failure produces
        a partial report with error details rather than a crash.

        Returns:
            TestHealthReport with all available sections populated.
        """
        start = time.monotonic()
        report = TestHealthReport()

        # 1. Issue tracing
        try:
            tracer = TestIssueTracer(self.project_root)
            report.tracing = tracer.analyze()
        except Exception as e:
            report.errors.append(f"TestIssueTracer failed: {e}")
            logger.warning("TestIssueTracer failed: %s", e)

        # 2. Pruning analysis
        try:
            pruner = TestPruningAnalyzer(self.project_root)
            report.pruning = pruner.analyze()
        except Exception as e:
            report.errors.append(f"TestPruningAnalyzer failed: {e}")
            logger.warning("TestPruningAnalyzer failed: %s", e)

        # 3. Tier distribution
        try:
            test_paths = self._collect_test_paths()
            report.tier_distribution = get_tier_distribution(test_paths)
        except Exception as e:
            report.errors.append(f"Tier distribution failed: {e}")
            logger.warning("Tier distribution failed: %s", e)

        # 4. Coverage baseline
        try:
            baseline = load_baseline()
            if baseline:
                report.coverage_baseline = baseline
        except Exception as e:
            report.errors.append(f"Coverage baseline failed: {e}")
            logger.warning("Coverage baseline failed: %s", e)

        # Compute summary
        report.summary = self._compute_summary(report)
        report.scan_duration_ms = (time.monotonic() - start) * 1000

        return report

    def format_dashboard(self, report: TestHealthReport) -> str:
        """Format a TestHealthReport as a markdown dashboard.

        Args:
            report: The health report to format.

        Returns:
            Markdown-formatted dashboard string.
        """
        lines: List[str] = []
        lines.append("# Test Health Dashboard")
        lines.append("")
        lines.append(f"Scan duration: {report.scan_duration_ms:.0f}ms")
        lines.append("")

        # Gate status
        passed, gate_msg = check_prunable_threshold(report)
        gate_label = "PASS" if passed else "FAIL"
        gate_line = (
            f"Gate Status: {gate_label} "
            f"({report.summary.prunable_count} prunable, "
            f"threshold: {PRUNABLE_THRESHOLD})"
        )
        if not passed:
            gate_line += " — run /sweep --tests --prune"
        lines.append(gate_line)
        lines.append("")
        # Tier balance gate
        tier_passed, tier_msg = check_tier_distribution(report.tier_distribution)
        tier_status = "OK" if tier_passed else f"WARNING ({tier_msg})"
        lines.append(f"Tier Balance Gate: {tier_status}")
        lines.append("")

        # Summary section
        s = report.summary
        lines.append("## Summary")
        lines.append("")
        lines.append(f"- Total findings: {s.total_findings}")
        lines.append(f"- Prunable candidates: {s.prunable_count}")
        lines.append(f"- Untraced tests: {s.untraced_test_count}")
        lines.append(f"- Orphaned pairs: {s.orphaned_pair_count}")
        lines.append(f"- Untested issues: {s.untested_issue_count}")
        lines.append(f"- Tier balance: {s.tier_balance}")
        lines.append("")

        # Tier distribution
        if report.tier_distribution:
            lines.append("## Tier Distribution")
            lines.append("")
            for tier_id in sorted(report.tier_distribution.keys()):
                count = report.tier_distribution[tier_id]
                lines.append(f"- {tier_id}: {count} tests")
            lines.append("")

        # Coverage baseline
        if report.coverage_baseline:
            lines.append("## Coverage Baseline")
            lines.append("")
            cb = report.coverage_baseline
            if "total_coverage" in cb:
                lines.append(f"- Coverage: {cb['total_coverage']:.1f}%")
            if "skip_count" in cb:
                lines.append(f"- Skipped: {cb['skip_count']}")
            if "total_tests" in cb:
                lines.append(f"- Total tests: {cb['total_tests']}")
            lines.append("")

        # Errors
        if report.errors:
            lines.append("## Errors")
            lines.append("")
            for error in report.errors:
                lines.append(f"- {error}")
            lines.append("")

        return "\n".join(lines)

    def _collect_test_paths(self) -> List[str]:
        """Collect relative paths of all test files under tests/.

        Returns:
            List of relative path strings for test files.
        """
        tests_dir = self.project_root / "tests"
        if not tests_dir.exists():
            return []

        paths: List[str] = []
        for test_file in tests_dir.rglob("test_*.py"):
            if ".worktrees" in test_file.parts:
                continue
            try:
                rel = str(test_file.relative_to(self.project_root))
                paths.append(rel)
            except ValueError:
                continue
        return sorted(paths)

    def _compute_summary(self, report: TestHealthReport) -> TestHealthSummary:
        """Compute aggregated summary metrics from sub-reports.

        Args:
            report: The partially populated health report.

        Returns:
            TestHealthSummary with computed metrics.
        """
        summary = TestHealthSummary()

        # Tracing metrics
        if report.tracing is not None:
            for finding in report.tracing.findings:
                summary.total_findings += 1
                if finding.category.value == "untraced_test":
                    summary.untraced_test_count += 1
                elif finding.category.value == "orphaned_pair":
                    summary.orphaned_pair_count += 1
                elif finding.category.value == "untested_issue":
                    summary.untested_issue_count += 1

        # Pruning metrics
        if report.pruning is not None:
            for finding in report.pruning.findings:
                summary.total_findings += 1
                if finding.prunable:
                    summary.prunable_count += 1

        # Tier balance assessment
        summary.tier_balance = self._assess_tier_balance(report.tier_distribution)

        return summary

    def _assess_tier_balance(self, distribution: Dict[str, int]) -> str:
        """Assess whether the tier distribution is healthy.

        A healthy distribution has tests at multiple tiers with T0/T1
        representing at least some fraction of the total.

        Args:
            distribution: Mapping of tier_id to count.

        Returns:
            One of "healthy", "bottom-heavy", "top-heavy", or "unknown".
        """
        if not distribution:
            return "unknown"

        total = sum(distribution.values())
        if total == 0:
            return "unknown"

        upper_count = distribution.get("T0", 0) + distribution.get("T1", 0)
        lower_count = distribution.get("T2", 0) + distribution.get("T3", 0)
        upper_ratio = upper_count / total

        # bottom-heavy: >80% in T2+T3 with almost nothing in T0+T1
        if upper_ratio < 0.1 and lower_count > 0:
            return "bottom-heavy"

        # top-heavy: >80% in T0+T1
        if upper_ratio > 0.8:
            return "top-heavy"

        return "healthy"


def check_issue_tracing(project_root: Path, issue_number: int) -> str:
    """Check if an issue has test references.

    Convenience function for pipeline integration. Returns a warning
    string if the issue has no test references, or an empty string
    if tracing is satisfied.

    Args:
        project_root: Root directory of the project.
        issue_number: The GitHub issue number to check.

    Returns:
        Warning message if issue is untraced, empty string otherwise.
    """
    if issue_number <= 0:
        return ""

    try:
        tracer = TestIssueTracer(project_root)
        if not tracer.check_issue_has_test(issue_number):
            return (
                f"WARNING: Issue #{issue_number} has no corresponding test. "
                f"Consider adding a regression test."
            )
    except Exception as e:
        logger.debug("check_issue_tracing failed: %s", e)

    return ""
def check_tier_distribution(tier_distribution: dict) -> tuple[bool, str]:
    """Check whether tier distribution is balanced according to targets.

    Warning triggers when:
    - (T0+T1+T2) / total < 0.25 (too bottom-heavy with T3 tests)
    - Any tier ratio drifts > 50% from target ratio

    Args:
        tier_distribution: Mapping of tier_id to test count.

    Returns:
        Tuple of (passed: bool, warning_msg: str).
    """
    if not tier_distribution:
        return (True, "OK")

    total = sum(tier_distribution.values())
    if total == 0:
        return (True, "OK")

    # Check if too bottom-heavy (T0+T1+T2 < 25% of total)
    upper_tiers = tier_distribution.get("T0", 0) + tier_distribution.get("T1", 0) + tier_distribution.get("T2", 0)
    upper_ratio = upper_tiers / total
    if upper_ratio < 0.25:
        return (False, f"too bottom-heavy: T0+T1+T2 only {upper_ratio:.1%} of tests")

    # Check if any tier drifts > 50% from target
    target_total = sum(TIER_DISTRIBUTION_TARGETS.values())
    for tier_id, target_count in TIER_DISTRIBUTION_TARGETS.items():
        target_ratio = target_count / target_total
        actual_count = tier_distribution.get(tier_id, 0)
        actual_ratio = actual_count / total

        if target_ratio > 0:
            drift = abs(actual_ratio - target_ratio) / target_ratio
            if drift > 0.5:
                return (False, f"{tier_id} ratio {actual_ratio:.1%} drifts >50% from target {target_ratio:.1%}")

    return (True, "OK")




def check_prunable_threshold(
    report: TestHealthReport,
    *,
    threshold: Optional[int] = None,
) -> tuple:
    """Check whether prunable findings exceed the allowed threshold.

    Args:
        report: A TestHealthReport (from TestLifecycleManager.analyze()).
        threshold: Maximum allowed prunable count. Defaults to PRUNABLE_THRESHOLD.

    Returns:
        Tuple of (passed: bool, message: str).
    """
    if threshold is None:
        threshold = PRUNABLE_THRESHOLD

    prunable_count = report.summary.prunable_count

    if prunable_count <= threshold:
        return (
            True,
            f"Prunable count {prunable_count} within threshold {threshold}",
        )
    else:
        return (
            False,
            f"Prunable count {prunable_count} exceeds threshold {threshold}. "
            f"Run /sweep --tests --prune",
        )
