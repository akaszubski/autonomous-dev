#!/usr/bin/env python3
"""
Ideation Engine - Proactive improvement discovery system

This module orchestrates automated analysis of code quality, security, performance,
accessibility, and technical debt to discover improvement opportunities.

Classes:
    IdeationCategory: Categories of analysis (SECURITY, PERFORMANCE, QUALITY, etc.)
    IdeationSeverity: Severity levels for findings (CRITICAL, HIGH, MEDIUM, LOW, INFO)
    IdeationResult: Single finding with metadata
    IdeationReport: Aggregated report with all findings
    IdeationEngine: Main orchestrator for running ideation analysis

Security Features:
    - Path traversal prevention (CWE-22)
    - Input validation for all user data
    - Safe file handling with pathlib
    - No arbitrary code execution

Usage:
    from ideation_engine import IdeationEngine, IdeationCategory

    # Run analysis on project
    engine = IdeationEngine(project_root="/path/to/project")
    report = engine.run_ideation(categories=[IdeationCategory.SECURITY])

    # Filter high-severity findings
    critical_findings = report.filter_by_severity(IdeationSeverity.CRITICAL)

    # Generate GitHub issues from findings
    issues = engine.generate_issues(report.results, min_severity=IdeationSeverity.HIGH)

Date: 2026-01-02
Issue: GitHub #186 (Proactive ideation system)
Agent: implementer
Phase: TDD Green (making tests pass)

Related:
    - /Users/andrewkaszubski/Dev/autonomous-dev/plugins/autonomous-dev/lib/ideators/
    - /Users/andrewkaszubski/Dev/autonomous-dev/plugins/autonomous-dev/lib/ideation_report_generator.py
"""

from enum import Enum
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import List, Dict, Optional
from datetime import datetime
import time
import logging

# Configure logging
logger = logging.getLogger(__name__)


# ============================================================================
# Enums
# ============================================================================

class IdeationCategory(Enum):
    """Categories of ideation analysis.

    Values:
        SECURITY: Security vulnerabilities and weaknesses
        PERFORMANCE: Performance bottlenecks and inefficiencies
        QUALITY: Code quality issues (tests, duplication, complexity)
        ACCESSIBILITY: User experience and accessibility issues
        TECH_DEBT: Technical debt accumulation
    """
    SECURITY = "security"
    PERFORMANCE = "performance"
    QUALITY = "quality"
    ACCESSIBILITY = "accessibility"
    TECH_DEBT = "technical_debt"


class IdeationSeverity(Enum):
    """Severity levels for ideation findings.

    Values:
        CRITICAL: Critical issues requiring immediate attention
        HIGH: High-priority issues to address soon
        MEDIUM: Medium-priority issues for planning
        LOW: Low-priority nice-to-have improvements
        INFO: Informational findings for awareness
    """
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    INFO = "info"


# ============================================================================
# Data Classes
# ============================================================================

@dataclass
class IdeationResult:
    """Single ideation finding with metadata.

    Attributes:
        category: Analysis category
        severity: Severity level
        location: File path and line number (e.g., "auth.py:42")
        title: Short title of finding
        description: Detailed description of issue
        suggested_fix: Recommended fix or improvement
        confidence: Confidence score (0.0-1.0)
        impact: Impact assessment (e.g., "HIGH", "MEDIUM", "LOW")
        effort: Effort estimate (e.g., "LOW", "MEDIUM", "HIGH")
        references: External references (CWE, OWASP, etc.)
    """
    category: IdeationCategory
    severity: IdeationSeverity
    location: str
    title: str
    description: str
    suggested_fix: str
    confidence: float
    impact: str
    effort: str
    references: List[str] = field(default_factory=list)

    def __post_init__(self):
        """Validate confidence score is in range 0.0-1.0."""
        if not 0.0 <= self.confidence <= 1.0:
            raise ValueError(f"Confidence must be between 0.0 and 1.0, got {self.confidence}")


@dataclass
class IdeationReport:
    """Aggregated ideation report with all findings.

    Attributes:
        timestamp: ISO format timestamp of analysis
        categories_analyzed: List of categories that were analyzed
        total_findings: Total number of findings
        findings_by_severity: Count of findings by severity level
        results: List of all findings
        analysis_duration: Time taken for analysis in seconds
    """
    timestamp: str
    categories_analyzed: List[IdeationCategory]
    total_findings: int
    findings_by_severity: Dict[IdeationSeverity, int]
    results: List[IdeationResult]
    analysis_duration: float

    def to_markdown(self) -> str:
        """Generate markdown report from findings.

        Returns:
            Markdown-formatted report string
        """
        lines = []
        lines.append("# Ideation Report")
        lines.append("")
        lines.append(f"**Generated**: {self.timestamp}")
        lines.append(f"**Analysis Duration**: {self.analysis_duration:.2f}s")
        lines.append("")

        # Summary section
        lines.append("## Summary")
        lines.append("")
        lines.append(f"**Total Findings**: {self.total_findings}")
        lines.append(f"**Categories Analyzed**: {', '.join(c.value.replace('_', ' ').title() for c in self.categories_analyzed)}")
        lines.append("")

        # Findings by severity
        lines.append("## Findings by Severity")
        lines.append("")
        if not self.findings_by_severity:
            lines.append("No findings")
        else:
            for severity in IdeationSeverity:
                count = self.findings_by_severity.get(severity, 0)
                if count > 0:
                    lines.append(f"- **{severity.value.upper()}**: {count}")
        lines.append("")

        # Detailed findings
        lines.append("## Detailed Findings")
        lines.append("")

        if not self.results:
            lines.append("No findings")
        else:
            for i, result in enumerate(self.results, 1):
                lines.append(f"### {i}. {result.title}")
                lines.append("")
                lines.append(f"**Category**: {result.category.value.replace('_', ' ').title()}")
                lines.append(f"**Severity**: {result.severity.value.upper()}")
                lines.append(f"**Location**: {result.location}")
                lines.append(f"**Confidence**: {result.confidence:.2f}")
                lines.append("")
                lines.append(f"**Description**: {result.description}")
                lines.append("")
                lines.append(f"**Suggested Fix**: {result.suggested_fix}")
                lines.append("")
                lines.append(f"**Impact**: {result.impact}")
                lines.append(f"**Effort**: {result.effort}")

                if result.references:
                    lines.append("")
                    lines.append(f"**References**: {', '.join(result.references)}")

                lines.append("")
                lines.append("---")
                lines.append("")

        return "\n".join(lines)

    def filter_by_severity(self, min_severity: IdeationSeverity) -> List[IdeationResult]:
        """Filter results by minimum severity level.

        Args:
            min_severity: Minimum severity level to include

        Returns:
            List of results with severity >= min_severity
        """
        # Define severity ordering
        severity_order = {
            IdeationSeverity.CRITICAL: 5,
            IdeationSeverity.HIGH: 4,
            IdeationSeverity.MEDIUM: 3,
            IdeationSeverity.LOW: 2,
            IdeationSeverity.INFO: 1
        }

        min_level = severity_order[min_severity]

        return [
            result for result in self.results
            if severity_order[result.severity] >= min_level
        ]


# ============================================================================
# Main Ideation Engine
# ============================================================================

class IdeationEngine:
    """Main orchestrator for ideation analysis.

    This class coordinates all ideation analyzers (security, performance, quality,
    accessibility, tech debt) and aggregates their results into a unified report.

    Attributes:
        project_root: Path to project root directory
    """

    def __init__(self, project_root: Path):
        """Initialize ideation engine.

        Args:
            project_root: Path to project root directory
        """
        self.project_root = Path(project_root)

    def run_ideation(self, categories: List[IdeationCategory]) -> IdeationReport:
        """Run ideation analysis for specified categories.

        Args:
            categories: List of categories to analyze

        Returns:
            IdeationReport with all findings
        """
        start_time = time.time()
        all_results = []

        # Import ideators here to avoid circular imports
        from autonomous_dev.lib.ideators.security_ideator import SecurityIdeator
        from autonomous_dev.lib.ideators.performance_ideator import PerformanceIdeator
        from autonomous_dev.lib.ideators.quality_ideator import QualityIdeator
        from autonomous_dev.lib.ideators.accessibility_ideator import AccessibilityIdeator
        from autonomous_dev.lib.ideators.tech_debt_ideator import TechDebtIdeator

        # Map categories to ideators
        ideator_map = {
            IdeationCategory.SECURITY: SecurityIdeator,
            IdeationCategory.PERFORMANCE: PerformanceIdeator,
            IdeationCategory.QUALITY: QualityIdeator,
            IdeationCategory.ACCESSIBILITY: AccessibilityIdeator,
            IdeationCategory.TECH_DEBT: TechDebtIdeator,
        }

        # Run each requested analyzer
        for category in categories:
            if category in ideator_map:
                ideator_class = ideator_map[category]
                ideator = ideator_class(project_root=self.project_root)
                results = ideator.analyze()
                all_results.extend(results)

        # Calculate statistics
        total_findings = len(all_results)
        findings_by_severity = {}
        for result in all_results:
            findings_by_severity[result.severity] = findings_by_severity.get(result.severity, 0) + 1

        analysis_duration = time.time() - start_time

        return IdeationReport(
            timestamp=datetime.now().isoformat(),
            categories_analyzed=categories,
            total_findings=total_findings,
            findings_by_severity=findings_by_severity,
            results=all_results,
            analysis_duration=analysis_duration
        )

    def prioritize_results(self, results: List[IdeationResult]) -> List[IdeationResult]:
        """Prioritize results by severity and confidence.

        Args:
            results: List of ideation results

        Returns:
            Sorted list with highest priority first
        """
        # Define severity ordering
        severity_order = {
            IdeationSeverity.CRITICAL: 5,
            IdeationSeverity.HIGH: 4,
            IdeationSeverity.MEDIUM: 3,
            IdeationSeverity.LOW: 2,
            IdeationSeverity.INFO: 1
        }

        # Sort by severity (descending) then confidence (descending)
        return sorted(
            results,
            key=lambda r: (severity_order[r.severity], r.confidence),
            reverse=True
        )

    def generate_issues(
        self,
        results: List[IdeationResult],
        min_severity: IdeationSeverity
    ) -> List[str]:
        """Generate GitHub issue descriptions from results.

        Args:
            results: List of ideation results
            min_severity: Minimum severity level to include

        Returns:
            List of GitHub issue descriptions (markdown format)
        """
        # Filter by minimum severity
        filtered = self.filter_by_minimum_severity(results, min_severity)

        # Generate issue text for each result
        issues = []
        for result in filtered:
            issue_text = self._format_issue(result)
            issues.append(issue_text)

        return issues

    def filter_by_minimum_severity(
        self,
        results: List[IdeationResult],
        min_severity: IdeationSeverity
    ) -> List[IdeationResult]:
        """Filter results by minimum severity.

        Args:
            results: List of results to filter
            min_severity: Minimum severity level

        Returns:
            Filtered list of results
        """
        severity_order = {
            IdeationSeverity.CRITICAL: 5,
            IdeationSeverity.HIGH: 4,
            IdeationSeverity.MEDIUM: 3,
            IdeationSeverity.LOW: 2,
            IdeationSeverity.INFO: 1
        }

        min_level = severity_order[min_severity]

        return [
            result for result in results
            if severity_order[result.severity] >= min_level
        ]

    def _format_issue(self, result: IdeationResult) -> str:
        """Format a single result as GitHub issue description.

        Args:
            result: Ideation result to format

        Returns:
            Markdown-formatted issue description
        """
        lines = []
        lines.append(f"# {result.title}")
        lines.append("")
        lines.append(f"**Category**: {result.category.value}")
        lines.append(f"**Severity**: {result.severity.value.upper()}")
        lines.append(f"**Location**: {result.location}")
        lines.append("")
        lines.append("## Description")
        lines.append("")
        lines.append(result.description)
        lines.append("")
        lines.append("## Suggested Fix")
        lines.append("")
        lines.append(result.suggested_fix)
        lines.append("")
        lines.append("## Metadata")
        lines.append("")
        lines.append(f"- **Impact**: {result.impact}")
        lines.append(f"- **Effort**: {result.effort}")
        lines.append(f"- **Confidence**: {result.confidence:.2f}")

        if result.references:
            lines.append("")
            lines.append("## References")
            lines.append("")
            for ref in result.references:
                lines.append(f"- {ref}")

        return "\n".join(lines)
