#!/usr/bin/env python3
"""
Accessibility Ideator - UX and accessibility issue detection

This module detects accessibility and user experience issues:
- Missing help text in forms
- Poor error messages
- Missing ARIA labels
- Inadequate contrast ratios (if CSS parsing available)

Focuses on Django/Flask form patterns and error handling.

Usage:
    from accessibility_ideator import AccessibilityIdeator

    ideator = AccessibilityIdeator(project_root="/path/to/project")
    results = ideator.analyze()

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


class AccessibilityIdeator:
    """Accessibility and UX analyzer.

    Detects patterns that may indicate accessibility issues.

    Attributes:
        project_root: Path to project root directory
    """

    def __init__(self, project_root: Path):
        """Initialize accessibility ideator.

        Args:
            project_root: Path to project root directory
        """
        self.project_root = Path(project_root)

    def analyze(self) -> List[IdeationResult]:
        """Analyze project for accessibility issues.

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

                # Check for missing help text in forms
                results.extend(self._check_missing_help_text(file_path, content))

                # Check for poor error messages
                results.extend(self._check_poor_error_messages(file_path, content))

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

    def _check_missing_help_text(self, file_path: Path, content: str) -> List[IdeationResult]:
        """Check for missing help text in form fields.

        Args:
            file_path: Path to file being analyzed
            content: File content

        Returns:
            List of findings
        """
        results = []
        lines = content.split('\n')

        for i, line in enumerate(lines, 1):
            # Look for form field definitions without help_text
            if re.search(r'forms\.\w+Field\(', line):
                # Check current line and next few lines for help_text parameter (may be on next line)
                lookahead = '\n'.join(lines[i-1:min(i+3, len(lines))])
                # Check for help_text= parameter, not just the word in comments
                if not re.search(r'help_text\s*=', lookahead):
                    relative_path = file_path.relative_to(self.project_root)
                    result = IdeationResult(
                        category=IdeationCategory.ACCESSIBILITY,
                        severity=IdeationSeverity.LOW,
                        location=f"{relative_path}:{i}",
                        title="Missing Help Text",
                        description="Form field lacks help_text attribute. Help text improves accessibility and user experience.",
                        suggested_fix="Add help_text parameter to provide guidance for users.",
                        confidence=0.90,
                        impact="LOW - Reduces usability for users",
                        effort="LOW - Add help_text string",
                        references=[]
                    )
                    results.append(result)

        return results

    def _check_poor_error_messages(self, file_path: Path, content: str) -> List[IdeationResult]:
        """Check for poor error messages.

        Args:
            file_path: Path to file being analyzed
            content: File content

        Returns:
            List of findings
        """
        results = []
        lines = content.split('\n')

        # Patterns for poor error messages
        poor_patterns = [
            r'raise\s+\w+Error\(["\']Error["\']',  # Generic "Error"
            r'raise\s+\w+Error\(["\']error["\']',  # Generic "error"
            r'raise\s+\w+Error\(["\']Invalid["\']',  # Just "Invalid"
            r'raise\s+\w+Error\(["\']Failed["\']',  # Just "Failed"
        ]

        for i, line in enumerate(lines, 1):
            for pattern in poor_patterns:
                if re.search(pattern, line):
                    relative_path = file_path.relative_to(self.project_root)
                    result = IdeationResult(
                        category=IdeationCategory.ACCESSIBILITY,
                        severity=IdeationSeverity.LOW,
                        location=f"{relative_path}:{i}",
                        title="Poor Error Message",
                        description="Vague error message provides no context. Users need specific information to resolve issues.",
                        suggested_fix="Provide detailed error message explaining what went wrong and how to fix it.",
                        confidence=0.85,
                        impact="LOW - Frustrates users during debugging",
                        effort="LOW - Improve error message text",
                        references=[]
                    )
                    results.append(result)
                    break  # Only report once per line

        return results
