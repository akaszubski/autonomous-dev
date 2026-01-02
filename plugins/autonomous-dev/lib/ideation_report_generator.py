#!/usr/bin/env python3
"""
Ideation Report Generator - Markdown report generation for ideation findings

This module generates formatted markdown reports from ideation analysis results.
Provides multiple output formats and filtering options.

Classes:
    IdeationReportGenerator: Main report generation class

Usage:
    from ideation_report_generator import IdeationReportGenerator
    from ideation_engine import IdeationEngine, IdeationCategory

    # Run analysis
    engine = IdeationEngine(project_root="/path/to/project")
    report = engine.run_ideation(categories=[IdeationCategory.SECURITY])

    # Generate report
    generator = IdeationReportGenerator()
    markdown = generator.generate_markdown_report(report)
    print(markdown)

Date: 2026-01-02
Issue: GitHub #186 (Proactive ideation system)
Agent: implementer
Phase: TDD Green (making tests pass)
"""

from typing import List, Optional
import logging

from autonomous_dev.lib.ideation_engine import (
    IdeationReport,
    IdeationResult,
    IdeationSeverity,
    IdeationCategory,
)

logger = logging.getLogger(__name__)


class IdeationReportGenerator:
    """Generate formatted reports from ideation results.

    Provides markdown generation with various formatting options.
    """

    def generate(self, report: IdeationReport) -> str:
        """Generate markdown report from ideation results.

        This is the main entry point for report generation.
        Delegates to generate_markdown_report for actual formatting.

        Args:
            report: IdeationReport to format

        Returns:
            Markdown-formatted report string
        """
        return self.generate_markdown_report(report)

    def generate_markdown_report(
        self,
        report: IdeationReport,
        include_summary: bool = True,
        include_statistics: bool = True,
        include_details: bool = True,
        min_severity: Optional[IdeationSeverity] = None
    ) -> str:
        """Generate markdown report from ideation results.

        Args:
            report: IdeationReport to format
            include_summary: Include summary section
            include_statistics: Include statistics section
            include_details: Include detailed findings
            min_severity: Minimum severity to include (None = all)

        Returns:
            Markdown-formatted report string
        """
        # Use the built-in to_markdown() method from IdeationReport
        # This ensures consistency with the dataclass implementation
        markdown = report.to_markdown()

        # Apply filtering if min_severity specified
        if min_severity is not None:
            filtered_results = report.filter_by_severity(min_severity)

            # Regenerate report with filtered results
            filtered_report = IdeationReport(
                timestamp=report.timestamp,
                categories_analyzed=report.categories_analyzed,
                total_findings=len(filtered_results),
                findings_by_severity=self._calculate_severity_counts(filtered_results),
                results=filtered_results,
                analysis_duration=report.analysis_duration
            )
            markdown = filtered_report.to_markdown()

        return markdown

    def generate_summary_report(self, report: IdeationReport) -> str:
        """Generate summary-only report (no detailed findings).

        Args:
            report: IdeationReport to summarize

        Returns:
            Markdown summary string
        """
        lines = []
        lines.append("# Ideation Summary")
        lines.append("")
        lines.append(f"**Generated**: {report.timestamp}")
        lines.append(f"**Analysis Duration**: {report.analysis_duration:.2f}s")
        lines.append(f"**Total Findings**: {report.total_findings}")
        lines.append("")

        # Severity breakdown
        lines.append("## Findings by Severity")
        lines.append("")
        for severity in IdeationSeverity:
            count = report.findings_by_severity.get(severity, 0)
            if count > 0:
                lines.append(f"- **{severity.value.upper()}**: {count}")
        lines.append("")

        # Category breakdown
        category_counts = self._calculate_category_counts(report.results)
        lines.append("## Findings by Category")
        lines.append("")
        for category in IdeationCategory:
            count = category_counts.get(category, 0)
            if count > 0:
                lines.append(f"- **{category.value}**: {count}")

        return "\n".join(lines)

    def generate_findings_by_category(
        self,
        report: IdeationReport,
        category: IdeationCategory
    ) -> str:
        """Generate report for specific category only.

        Args:
            report: IdeationReport to filter
            category: Category to include

        Returns:
            Markdown report for category
        """
        # Filter results by category
        filtered_results = [r for r in report.results if r.category == category]

        # Create filtered report
        filtered_report = IdeationReport(
            timestamp=report.timestamp,
            categories_analyzed=[category],
            total_findings=len(filtered_results),
            findings_by_severity=self._calculate_severity_counts(filtered_results),
            results=filtered_results,
            analysis_duration=report.analysis_duration
        )

        return filtered_report.to_markdown()

    def generate_critical_findings_report(self, report: IdeationReport) -> str:
        """Generate report of critical findings only.

        Args:
            report: IdeationReport to filter

        Returns:
            Markdown report of critical findings
        """
        critical_results = report.filter_by_severity(IdeationSeverity.CRITICAL)

        lines = []
        lines.append("# Critical Findings")
        lines.append("")
        lines.append(f"**Total Critical Issues**: {len(critical_results)}")
        lines.append("")

        if not critical_results:
            lines.append("No critical findings detected.")
        else:
            for i, result in enumerate(critical_results, 1):
                lines.append(f"## {i}. {result.title}")
                lines.append("")
                lines.append(f"**Location**: {result.location}")
                lines.append(f"**Category**: {result.category.value}")
                lines.append("")
                lines.append(f"**Description**: {result.description}")
                lines.append("")
                lines.append(f"**Suggested Fix**: {result.suggested_fix}")
                lines.append("")
                lines.append("---")
                lines.append("")

        return "\n".join(lines)

    def _calculate_severity_counts(self, results: List[IdeationResult]) -> dict:
        """Calculate count of results by severity.

        Args:
            results: List of results to count

        Returns:
            Dict mapping severity to count
        """
        counts = {}
        for result in results:
            counts[result.severity] = counts.get(result.severity, 0) + 1
        return counts

    def _calculate_category_counts(self, results: List[IdeationResult]) -> dict:
        """Calculate count of results by category.

        Args:
            results: List of results to count

        Returns:
            Dict mapping category to count
        """
        counts = {}
        for result in results:
            counts[result.category] = counts.get(result.category, 0) + 1
        return counts
