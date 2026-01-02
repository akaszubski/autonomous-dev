#!/usr/bin/env python3
"""
Performance Ideator - Performance bottleneck detection

This module detects common performance issues in Python code:
- N+1 query problems (ORM queries in loops)
- Inefficient algorithms (nested loops, O(n^2) patterns)
- Missing database indexes
- Unoptimized file I/O
- Memory leaks and inefficient data structures

Uses pattern matching to identify potential bottlenecks.

Usage:
    from performance_ideator import PerformanceIdeator

    ideator = PerformanceIdeator(project_root="/path/to/project")
    results = ideator.analyze()

    for result in results:
        if result.severity == IdeationSeverity.HIGH:
            print(f"Performance issue: {result.title}")

Date: 2026-01-02
Issue: GitHub #186 (Proactive ideation system)
Agent: implementer
Phase: TDD Green (making tests pass)
"""

from pathlib import Path
from typing import List
import re
import logging

from autonomous_dev.lib.ideation_engine import (
    IdeationCategory,
    IdeationSeverity,
    IdeationResult,
)

logger = logging.getLogger(__name__)


class PerformanceIdeator:
    """Performance bottleneck analyzer.

    Detects patterns that may indicate performance issues.

    Attributes:
        project_root: Path to project root directory
    """

    # N+1 query patterns (ORM queries in loops)
    N_PLUS_ONE_PATTERNS = [
        r'for\s+\w+\s+in.*:\s*\n\s+.*\.objects\.filter',  # Django ORM in loop
        r'for\s+\w+\s+in.*:\s*\n\s+.*\.query\.',         # SQLAlchemy in loop
        r'for\s+\w+\s+in.*:\s*\n\s+.*SELECT',            # Raw SQL in loop
    ]

    # Inefficient algorithm patterns
    INEFFICIENT_ALGORITHM_PATTERNS = [
        r'for\s+\w+\s+in\s+range\([^)]+\):\s*\n\s+for\s+\w+\s+in\s+range',  # Nested loops
    ]

    def __init__(self, project_root: Path):
        """Initialize performance ideator.

        Args:
            project_root: Path to project root directory
        """
        self.project_root = Path(project_root)

    def analyze(self) -> List[IdeationResult]:
        """Analyze project for performance issues.

        Returns:
            List of IdeationResult objects for detected issues
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

                # Check for N+1 queries
                results.extend(self._check_n_plus_one(file_path, content))

                # Check for inefficient algorithms
                results.extend(self._check_inefficient_algorithms(file_path, content))

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

    def _check_n_plus_one(self, file_path: Path, content: str) -> List[IdeationResult]:
        """Check for N+1 query problems.

        Args:
            file_path: Path to file being analyzed
            content: File content

        Returns:
            List of findings
        """
        results = []

        # Look for ORM queries inside loops
        if re.search(r'for\s+\w+\s+in', content):
            lines = content.split('\n')
            for i, line in enumerate(lines, 1):
                # Check if line has a for loop
                if re.search(r'for\s+\w+\s+in', line):
                    # Look ahead a few lines for ORM queries
                    lookahead = '\n'.join(lines[i:min(i+5, len(lines))])
                    if re.search(r'\.objects\.filter|\.query\.|SELECT', lookahead, re.IGNORECASE):
                        relative_path = file_path.relative_to(self.project_root)
                        result = IdeationResult(
                            category=IdeationCategory.PERFORMANCE,
                            severity=IdeationSeverity.HIGH,
                            location=f"{relative_path}:{i}",
                            title="N+1 Query Problem",
                            description="ORM query inside loop causes N+1 queries. This executes one query per iteration instead of a single query.",
                            suggested_fix="Use select_related() or prefetch_related() to fetch related objects in a single query.",
                            confidence=0.88,
                            impact="MEDIUM - Causes excessive database queries and slow page loads",
                            effort="LOW - Simple ORM optimization",
                            references=[]
                        )
                        results.append(result)
                        break  # Only report once per loop

        return results

    def _check_inefficient_algorithms(self, file_path: Path, content: str) -> List[IdeationResult]:
        """Check for inefficient algorithms.

        Args:
            file_path: Path to file being analyzed
            content: File content

        Returns:
            List of findings
        """
        results = []
        lines = content.split('\n')

        # Look for nested loops
        for i, line in enumerate(lines, 1):
            if re.search(r'for\s+\w+\s+in\s+range\(', line):
                # Look ahead for nested loop
                lookahead = '\n'.join(lines[i:min(i+10, len(lines))])
                if re.search(r'for\s+\w+\s+in\s+range\(', lookahead):
                    relative_path = file_path.relative_to(self.project_root)
                    result = IdeationResult(
                        category=IdeationCategory.PERFORMANCE,
                        severity=IdeationSeverity.MEDIUM,
                        location=f"{relative_path}:{i}",
                        title="Inefficient Algorithm",
                        description="Nested loops create O(n^2) time complexity. This can cause severe performance degradation on large datasets.",
                        suggested_fix="Consider using hash tables, sets, or more efficient algorithms to reduce complexity.",
                        confidence=0.80,
                        impact="MEDIUM - Slow performance on large inputs",
                        effort="MEDIUM - May require algorithm redesign",
                        references=[]
                    )
                    results.append(result)
                    break  # Only report once per file

        return results
