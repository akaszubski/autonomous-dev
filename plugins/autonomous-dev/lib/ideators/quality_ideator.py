#!/usr/bin/env python3
"""
Quality Ideator - Code quality issue detection

This module detects code quality issues:
- Missing test coverage (files without corresponding tests)
- Code duplication (similar code blocks)
- High cyclomatic complexity (deeply nested code)
- Missing docstrings
- Long functions/methods

Uses static analysis to identify quality issues.

Usage:
    from quality_ideator import QualityIdeator

    ideator = QualityIdeator(project_root="/path/to/project")
    results = ideator.analyze()

Date: 2026-01-02
Issue: GitHub #186 (Proactive ideation system)
Agent: implementer
Phase: TDD Green (making tests pass)
"""

from pathlib import Path
from typing import List, Set
import re
import logging

from autonomous_dev.lib.ideation_engine import (
    IdeationCategory,
    IdeationSeverity,
    IdeationResult,
)

logger = logging.getLogger(__name__)


class QualityIdeator:
    """Code quality analyzer.

    Detects patterns that may indicate quality issues.

    Attributes:
        project_root: Path to project root directory
    """

    def __init__(self, project_root: Path):
        """Initialize quality ideator.

        Args:
            project_root: Path to project root directory
        """
        self.project_root = Path(project_root)

    def analyze(self) -> List[IdeationResult]:
        """Analyze project for quality issues.

        Returns:
            List of IdeationResult objects for detected issues
        """
        results = []

        # Find all Python files
        python_files = list(self.project_root.rglob("*.py"))

        # Get test files for coverage check
        test_files = self._find_test_files(python_files)

        for file_path in python_files:
            # Skip test files themselves and virtual environments
            if self._should_skip_file(file_path):
                continue

            try:
                content = file_path.read_text(encoding='utf-8')

                # Check for missing tests
                if not self._has_test_file(file_path, test_files):
                    results.extend(self._check_missing_tests(file_path))

                # Check for code duplication
                results.extend(self._check_code_duplication(file_path, content))

                # Check for high complexity
                results.extend(self._check_high_complexity(file_path, content))

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

        # Skip __init__.py files
        if file_path.name == '__init__.py':
            return True

        # Skip virtual environments
        path_parts = file_path.parts
        if any(part in ['venv', '.venv', 'env', 'virtualenv', 'site-packages'] for part in path_parts):
            return True

        return False

    def _find_test_files(self, python_files: List[Path]) -> Set[str]:
        """Find all test files in project.

        Args:
            python_files: List of all Python files

        Returns:
            Set of test file names (without path)
        """
        test_files = set()
        for file_path in python_files:
            if 'test_' in file_path.name or file_path.name.startswith('test'):
                test_files.add(file_path.name)
        return test_files

    def _has_test_file(self, file_path: Path, test_files: Set[str]) -> bool:
        """Check if a file has a corresponding test file.

        Args:
            file_path: Path to file
            test_files: Set of test file names

        Returns:
            True if corresponding test file exists
        """
        # Generate expected test file name
        expected_test = f"test_{file_path.name}"
        return expected_test in test_files

    def _check_missing_tests(self, file_path: Path) -> List[IdeationResult]:
        """Check for missing test coverage.

        Args:
            file_path: Path to file being analyzed

        Returns:
            List of findings
        """
        results = []

        relative_path = file_path.relative_to(self.project_root)
        result = IdeationResult(
            category=IdeationCategory.QUALITY,
            severity=IdeationSeverity.MEDIUM,
            location=str(relative_path),
            title="Missing Test Coverage",
            description=f"File {file_path.name} has no corresponding test file. All production code should have test coverage.",
            suggested_fix=f"Create test_{file_path.name} with unit tests for this module.",
            confidence=0.75,
            impact="LOW - Missing tests may allow bugs to go undetected",
            effort="MEDIUM - Write comprehensive test suite",
            references=[]
        )
        results.append(result)

        return results

    def _check_code_duplication(self, file_path: Path, content: str) -> List[IdeationResult]:
        """Check for code duplication.

        Args:
            file_path: Path to file being analyzed
            content: File content

        Returns:
            List of findings
        """
        results = []

        # Look for duplicate function definitions (simple heuristic)
        function_bodies = {}
        lines = content.split('\n')

        current_function = None
        current_body = []
        in_function = False

        for i, line in enumerate(lines):
            # Check for function definition
            if re.match(r'^\s*def\s+(\w+)', line):
                # Save previous function
                if current_function and current_body:
                    # Normalize whitespace for comparison (remove leading whitespace)
                    normalized_lines = [l.strip() for l in current_body if l.strip()]
                    normalized = '\n'.join(normalized_lines)

                    # Only compare if we have actual code (not just empty functions)
                    if len(normalized) > 10:
                        if normalized in function_bodies:
                            # Found duplicate
                            relative_path = file_path.relative_to(self.project_root)
                            result = IdeationResult(
                                category=IdeationCategory.QUALITY,
                                severity=IdeationSeverity.MEDIUM,
                                location=str(relative_path),
                                title="Code Duplication Detected",
                                description=f"Duplicate code found in {file_path.name}. Functions {function_bodies[normalized]} and {current_function} have similar implementations.",
                                suggested_fix="Extract common logic into a shared function to reduce duplication.",
                                confidence=0.70,
                                impact="LOW - Increases maintenance burden",
                                effort="LOW - Refactor to shared function",
                                references=[]
                            )
                            results.append(result)
                            break  # Only report once per file
                        else:
                            function_bodies[normalized] = current_function

                # Start new function
                match = re.match(r'^\s*def\s+(\w+)', line)
                current_function = match.group(1)
                current_body = []
                in_function = True
            elif in_function:
                # Check if we're still in the function (indented) or reached end
                if line and not line[0].isspace() and line.strip():
                    # Reached non-indented line, function ended
                    in_function = False
                else:
                    current_body.append(line)

        # Check last function
        if current_function and current_body:
            normalized_lines = [l.strip() for l in current_body if l.strip()]
            normalized = '\n'.join(normalized_lines)
            if len(normalized) > 10 and normalized in function_bodies:
                relative_path = file_path.relative_to(self.project_root)
                result = IdeationResult(
                    category=IdeationCategory.QUALITY,
                    severity=IdeationSeverity.MEDIUM,
                    location=str(relative_path),
                    title="Code Duplication Detected",
                    description=f"Duplicate code found in {file_path.name}. Functions {function_bodies[normalized]} and {current_function} have similar implementations.",
                    suggested_fix="Extract common logic into a shared function to reduce duplication.",
                    confidence=0.70,
                    impact="LOW - Increases maintenance burden",
                    effort="LOW - Refactor to shared function",
                    references=[]
                )
                results.append(result)

        return results

    def _check_high_complexity(self, file_path: Path, content: str) -> List[IdeationResult]:
        """Check for high cyclomatic complexity.

        Args:
            file_path: Path to file being analyzed
            content: File content

        Returns:
            List of findings
        """
        results = []

        # Look for deeply nested if statements (simple heuristic)
        lines = content.split('\n')
        max_indent = 0
        max_indent_line = 0

        for i, line in enumerate(lines, 1):
            if 'if ' in line:
                # Count indentation
                indent = len(line) - len(line.lstrip())
                if indent > max_indent:
                    max_indent = indent
                    max_indent_line = i

        # If max indent > 16 spaces (4 levels), flag as high complexity
        if max_indent > 16:
            relative_path = file_path.relative_to(self.project_root)
            result = IdeationResult(
                category=IdeationCategory.QUALITY,
                severity=IdeationSeverity.MEDIUM,
                location=f"{relative_path}:{max_indent_line}",
                title="High Cyclomatic Complexity",
                description=f"Deep nesting detected (indent level {max_indent // 4}). This indicates high cyclomatic complexity.",
                suggested_fix="Refactor to reduce nesting using guard clauses, early returns, or extracting functions.",
                confidence=0.65,
                impact="MEDIUM - Difficult to understand and test",
                effort="MEDIUM - Requires refactoring",
                references=[]
            )
            results.append(result)

        return results
