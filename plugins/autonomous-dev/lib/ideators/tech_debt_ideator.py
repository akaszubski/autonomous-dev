#!/usr/bin/env python3
"""
Tech Debt Ideator - Technical debt pattern detection

This module wraps the TechDebtDetector to provide ideation results
for technical debt patterns. Converts TechDebtIssue to IdeationResult.

Usage:
    from tech_debt_ideator import TechDebtIdeator

    ideator = TechDebtIdeator(project_root="/path/to/project")
    results = ideator.analyze()

Date: 2026-01-02
Issue: GitHub #186 (Proactive ideation system)
Agent: implementer
Phase: TDD Green (making tests pass)
"""

from pathlib import Path
from typing import List
import logging

from autonomous_dev.lib.ideation_engine import (
    IdeationCategory,
    IdeationSeverity,
    IdeationResult,
)
from autonomous_dev.lib.tech_debt_detector import (
    TechDebtDetector,
    Severity as TechDebtSeverity,
)

logger = logging.getLogger(__name__)


class TechDebtIdeator:
    """Technical debt analyzer using TechDebtDetector.

    Wraps existing TechDebtDetector and converts results to IdeationResult format.

    Attributes:
        project_root: Path to project root directory
    """

    def __init__(self, project_root: Path):
        """Initialize tech debt ideator.

        Args:
            project_root: Path to project root directory
        """
        self.project_root = Path(project_root)
        self.detector = TechDebtDetector(project_root=project_root)

    def analyze(self) -> List[IdeationResult]:
        """Analyze project for technical debt.

        Returns:
            List of IdeationResult objects for detected issues
        """
        results = []

        # Run tech debt detection
        report = self.detector.analyze()

        # Convert TechDebtIssue to IdeationResult
        for issue in report.issues:
            ideation_result = self._convert_to_ideation_result(issue)
            results.append(ideation_result)

        # Also check for TODO/FIXME/HACK markers
        results.extend(self._detect_todo_markers())

        return results

    def _detect_todo_markers(self) -> List[IdeationResult]:
        """Detect TODO, FIXME, HACK markers in code.

        Returns:
            List of IdeationResult objects for detected markers
        """
        results = []

        # Find all Python files
        python_files = list(self.project_root.rglob("*.py"))

        for file_path in python_files:
            # Skip test files and virtual environments
            if self._should_skip_file(file_path):
                continue

            try:
                content = file_path.read_text(encoding='utf-8')
                lines = content.split('\n')

                for i, line in enumerate(lines, 1):
                    # Check for TODO
                    if 'TODO' in line and '#' in line:
                        relative_path = file_path.relative_to(self.project_root)
                        result = IdeationResult(
                            category=IdeationCategory.TECH_DEBT,
                            severity=IdeationSeverity.LOW,
                            location=f"{relative_path}:{i}",
                            title="TODO Comment Found",
                            description=f"TODO comment indicates incomplete work: {line.strip()}",
                            suggested_fix="Complete the TODO or create a tracking issue.",
                            confidence=0.95,
                            impact="LOW - Future work item",
                            effort="VARIES - Depends on scope",
                            references=[]
                        )
                        results.append(result)

                    # Check for FIXME
                    if 'FIXME' in line and '#' in line:
                        relative_path = file_path.relative_to(self.project_root)
                        result = IdeationResult(
                            category=IdeationCategory.TECH_DEBT,
                            severity=IdeationSeverity.MEDIUM,
                            location=f"{relative_path}:{i}",
                            title="FIXME Comment Found",
                            description=f"FIXME comment indicates broken code: {line.strip()}",
                            suggested_fix="Fix the issue or create a bug report.",
                            confidence=0.95,
                            impact="MEDIUM - Known issue needs fixing",
                            effort="VARIES - Depends on issue",
                            references=[]
                        )
                        results.append(result)

                    # Check for HACK
                    if 'HACK' in line and '#' in line:
                        relative_path = file_path.relative_to(self.project_root)
                        result = IdeationResult(
                            category=IdeationCategory.TECH_DEBT,
                            severity=IdeationSeverity.MEDIUM,
                            location=f"{relative_path}:{i}",
                            title="HACK Comment Found",
                            description=f"HACK comment indicates temporary workaround: {line.strip()}",
                            suggested_fix="Replace hack with proper solution.",
                            confidence=0.95,
                            impact="MEDIUM - Technical debt accumulation",
                            effort="MEDIUM - Refactoring needed",
                            references=[]
                        )
                        results.append(result)

            except Exception as e:
                logger.warning(f"Error analyzing {file_path}: {e}")
                continue

        return results

    def _should_skip_file(self, file_path: Path) -> bool:
        """Check if file should be skipped during analysis.

        Args:
            file_path: Path to file

        Returns:
            True if file should be skipped
        """
        # Skip test files
        if 'test_' in file_path.name or file_path.name.startswith('test'):
            return True

        # Skip virtual environments
        path_parts = file_path.parts
        if any(part in ['venv', '.venv', 'env', 'virtualenv', 'site-packages'] for part in path_parts):
            return True

        return False

    def _convert_to_ideation_result(self, tech_debt_issue) -> IdeationResult:
        """Convert TechDebtIssue to IdeationResult.

        Args:
            tech_debt_issue: TechDebtIssue from detector

        Returns:
            IdeationResult with converted data
        """
        # Map TechDebtSeverity to IdeationSeverity
        severity_map = {
            TechDebtSeverity.CRITICAL: IdeationSeverity.CRITICAL,
            TechDebtSeverity.HIGH: IdeationSeverity.HIGH,
            TechDebtSeverity.MEDIUM: IdeationSeverity.MEDIUM,
            TechDebtSeverity.LOW: IdeationSeverity.LOW,
        }

        # Map category to impact/effort
        impact_map = {
            "large_file": "MEDIUM - Difficult to maintain and review",
            "circular_import": "HIGH - Can cause import errors",
            "dead_code": "LOW - Clutters codebase",
            "complexity": "MEDIUM - Hard to understand and test",
        }

        effort_map = {
            "large_file": "HIGH - Requires refactoring into modules",
            "circular_import": "MEDIUM - Requires restructuring",
            "dead_code": "LOW - Simple removal",
            "complexity": "MEDIUM - Requires refactoring",
        }

        # Determine confidence based on category
        confidence_map = {
            "large_file": 0.95,  # High confidence - objective metric
            "circular_import": 0.90,
            "dead_code": 0.70,
            "complexity": 0.85,
        }

        return IdeationResult(
            category=IdeationCategory.TECH_DEBT,
            severity=severity_map.get(tech_debt_issue.severity, IdeationSeverity.MEDIUM),
            location=tech_debt_issue.file_path,
            title=tech_debt_issue.message,
            description=f"{tech_debt_issue.category.replace('_', ' ').title()}: {tech_debt_issue.message}",
            suggested_fix=tech_debt_issue.recommendation,
            confidence=confidence_map.get(tech_debt_issue.category, 0.75),
            impact=impact_map.get(tech_debt_issue.category, "MEDIUM"),
            effort=effort_map.get(tech_debt_issue.category, "MEDIUM"),
            references=[]
        )
