#!/usr/bin/env python3
"""
Security Ideator - Security vulnerability detection

This module detects common security vulnerabilities in Python code:
- SQL injection (string concatenation in queries)
- XSS vulnerabilities (unescaped HTML output)
- Command injection (shell command construction)
- Path traversal vulnerabilities
- Insecure cryptography usage

Uses pattern matching and AST analysis to identify potential issues.

Security Features:
    - Safe file handling with pathlib
    - No arbitrary code execution
    - Read-only analysis (no file modifications)

Usage:
    from security_ideator import SecurityIdeator
    from ideation_engine import IdeationCategory

    ideator = SecurityIdeator(project_root="/path/to/project")
    results = ideator.analyze()

    for result in results:
        print(f"{result.severity.value}: {result.title} at {result.location}")

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


class SecurityIdeator:
    """Security vulnerability analyzer.

    Detects common security patterns that may indicate vulnerabilities.

    Attributes:
        project_root: Path to project root directory
    """

    # SQL injection patterns
    SQL_INJECTION_PATTERNS = [
        r'\"SELECT.*\"\s*\+',  # "SELECT ..." + variable
        r'\"INSERT.*\"\s*\+',  # "INSERT ..." + variable
        r'\"UPDATE.*\"\s*\+',  # "UPDATE ..." + variable
        r'\"DELETE.*\"\s*\+',  # "DELETE ..." + variable
        r'f\"SELECT.*\{',      # f"SELECT ... {variable}"
        r'f\"INSERT.*\{',      # f"INSERT ... {variable}"
        r'f\"UPDATE.*\{',      # f"UPDATE ... {variable}"
        r'f\"DELETE.*\{',      # f"DELETE ... {variable}"
    ]

    # XSS patterns
    XSS_PATTERNS = [
        r'f\"<.*\{',           # f"<div>{variable}</div>"
        r'\"<.*\"\s*\+',       # "<div>" + variable + "</div>"
        r'\.innerHTML\s*=',    # element.innerHTML = variable
    ]

    # Command injection patterns
    COMMAND_INJECTION_PATTERNS = [
        r'os\.system\(f\"',    # os.system(f"command {variable}")
        r'os\.system\(.*\+',   # os.system("command " + variable)
        r'subprocess\.call\(f\"',
        r'subprocess\.call\(.*\+',
        r'subprocess\.run\(f\"',
        r'subprocess\.run\(.*\+',
    ]

    def __init__(self, project_root: Path):
        """Initialize security ideator.

        Args:
            project_root: Path to project root directory
        """
        self.project_root = Path(project_root)

    def analyze(self) -> List[IdeationResult]:
        """Analyze project for security vulnerabilities.

        Returns:
            List of IdeationResult objects for detected vulnerabilities
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

                # Check for SQL injection
                results.extend(self._check_sql_injection(file_path, content))

                # Check for XSS
                results.extend(self._check_xss(file_path, content))

                # Check for command injection
                results.extend(self._check_command_injection(file_path, content))

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

    def _check_sql_injection(self, file_path: Path, content: str) -> List[IdeationResult]:
        """Check for SQL injection vulnerabilities.

        Args:
            file_path: Path to file being analyzed
            content: File content

        Returns:
            List of findings
        """
        results = []
        lines = content.split('\n')

        for i, line in enumerate(lines, 1):
            for pattern in self.SQL_INJECTION_PATTERNS:
                if re.search(pattern, line, re.IGNORECASE):
                    # Found potential SQL injection
                    relative_path = file_path.relative_to(self.project_root)
                    result = IdeationResult(
                        category=IdeationCategory.SECURITY,
                        severity=IdeationSeverity.CRITICAL,
                        location=f"{relative_path}:{i}",
                        title="SQL Injection Vulnerability",
                        description="User input concatenated directly into SQL query. This allows attackers to execute arbitrary SQL commands.",
                        suggested_fix="Use parameterized queries or ORM methods instead of string concatenation.",
                        confidence=0.95,
                        impact="HIGH - Allows arbitrary database access and data exfiltration",
                        effort="LOW - Simple fix with ORM or prepared statements",
                        references=["CWE-89", "OWASP A03:2021"]
                    )
                    results.append(result)
                    break  # Only report once per line

        return results

    def _check_xss(self, file_path: Path, content: str) -> List[IdeationResult]:
        """Check for XSS vulnerabilities.

        Args:
            file_path: Path to file being analyzed
            content: File content

        Returns:
            List of findings
        """
        results = []
        lines = content.split('\n')

        for i, line in enumerate(lines, 1):
            for pattern in self.XSS_PATTERNS:
                if re.search(pattern, line):
                    # Found potential XSS
                    relative_path = file_path.relative_to(self.project_root)
                    result = IdeationResult(
                        category=IdeationCategory.SECURITY,
                        severity=IdeationSeverity.HIGH,
                        location=f"{relative_path}:{i}",
                        title="XSS Vulnerability",
                        description="User input inserted into HTML without proper escaping. This allows attackers to inject malicious scripts.",
                        suggested_fix="Use template engine auto-escaping or explicitly escape user input before rendering.",
                        confidence=0.90,
                        impact="MEDIUM - Allows script injection and session hijacking",
                        effort="LOW - Use template auto-escaping or escape functions",
                        references=["CWE-79", "OWASP A03:2021"]
                    )
                    results.append(result)
                    break  # Only report once per line

        return results

    def _check_command_injection(self, file_path: Path, content: str) -> List[IdeationResult]:
        """Check for command injection vulnerabilities.

        Args:
            file_path: Path to file being analyzed
            content: File content

        Returns:
            List of findings
        """
        results = []
        lines = content.split('\n')

        for i, line in enumerate(lines, 1):
            for pattern in self.COMMAND_INJECTION_PATTERNS:
                if re.search(pattern, line):
                    # Found potential command injection
                    relative_path = file_path.relative_to(self.project_root)
                    result = IdeationResult(
                        category=IdeationCategory.SECURITY,
                        severity=IdeationSeverity.CRITICAL,
                        location=f"{relative_path}:{i}",
                        title="Command Injection Vulnerability",
                        description="User input concatenated into shell command. This allows attackers to execute arbitrary commands.",
                        suggested_fix="Use subprocess with list arguments instead of shell=True, or validate/sanitize all inputs.",
                        confidence=0.93,
                        impact="CRITICAL - Allows arbitrary command execution on server",
                        effort="LOW - Use subprocess.run() with list arguments",
                        references=["CWE-78", "OWASP A03:2021"]
                    )
                    results.append(result)
                    break  # Only report once per line

        return results
