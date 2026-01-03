#!/usr/bin/env python3
"""
Test Coverage Analyzer - AST-based test coverage analysis.

This module provides AST-based test coverage analysis for Python projects:
- Find testable items (public functions and classes)
- Detect test layers (unit, integration, e2e)
- Parse pytest output for skipped/xfail tests
- Calculate coverage percentages
- Generate coverage reports with gaps

Security Features:
- Path traversal prevention (CWE-22)
- Secret sanitization in skip reasons
- No shell=True in subprocess calls
- Path validation against project root

Usage:
    from test_coverage_analyzer import TestCoverageAnalyzer

    # Analyze coverage
    analyzer = TestCoverageAnalyzer(project_root="/path/to/project")
    report = analyzer.analyze_coverage()

    # Check coverage
    print(f"Coverage: {report.coverage_percentage}%")
    print(f"Gaps: {len(report.coverage_gaps)}")
    print(f"Skipped: {len(report.skipped_tests)}")

Date: 2026-01-03
Agent: implementer
Phase: TDD Green (making tests pass)

Design Patterns:
    See library-design-patterns skill for standardized design patterns.
"""

import ast
import re
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Dict, Optional, Set


# =============================================================================
# Data Classes
# =============================================================================

@dataclass
class CoverageGap:
    """Represents an item missing test coverage.

    Attributes:
        item_name: Name of the untested function/class
        item_type: Type ("function" or "class")
        file_path: Path to source file containing the item
        layer: Test layer where coverage is missing
    """
    item_name: str
    item_type: str
    file_path: str
    layer: str


@dataclass
class SkippedTest:
    """Represents a skipped or xfailed test.

    Attributes:
        test_name: Full test identifier (e.g., "test_file.py::test_func")
        reason: Reason for skip/xfail
        skip_type: Type of skip ("SKIPPED" or "XFAIL")
    """
    test_name: str
    reason: str
    skip_type: str = "SKIPPED"


@dataclass
class LayerCoverage:
    """Coverage statistics for a specific test layer.

    Attributes:
        layer_name: Name of the layer ("unit", "integration", "e2e")
        total_tests: Total number of tests in this layer
        passed_tests: Number of passed tests
        skipped_tests: Number of skipped tests
        coverage_percentage: Coverage percentage for this layer
    """
    layer_name: str
    total_tests: int = 0
    passed_tests: int = 0
    skipped_tests: int = 0
    coverage_percentage: float = 0.0


@dataclass
class CoverageReport:
    """Complete coverage analysis report.

    Attributes:
        total_testable: Total number of testable items (functions/classes)
        total_covered: Number of items with test coverage
        coverage_percentage: Overall coverage percentage
        coverage_gaps: List of items missing coverage
        skipped_tests: List of skipped/xfailed tests
        layer_coverage: Per-layer coverage statistics
        warnings: List of warnings generated during analysis
        total_tests: Total number of tests executed
        skip_rate: Percentage of tests that are skipped
    """
    total_testable: int = 0
    total_covered: int = 0
    coverage_percentage: float = 0.0
    coverage_gaps: List[CoverageGap] = field(default_factory=list)
    skipped_tests: List[SkippedTest] = field(default_factory=list)
    layer_coverage: List[LayerCoverage] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    total_tests: int = 0
    skip_rate: float = 0.0


# =============================================================================
# Test Coverage Analyzer
# =============================================================================

class TestCoverageAnalyzer:
    """Analyzes test coverage using AST and pytest execution.

    This class performs static analysis of source code to find testable items
    and dynamic analysis of test execution to determine coverage.

    Attributes:
        project_root: Root directory of the project
        layer_filter: Optional filter for specific test layer
        include_skipped: Whether to include skipped tests in report
        warnings: List of accumulated warnings
    """

    # Secret patterns to redact from skip reasons
    SECRET_PATTERNS = [
        r"(?i)(api[_-]?key|token|password|secret)[=:\s]+[^\s,)]+",
        r"sk_test_[a-zA-Z0-9]+",
        r"Bearer\s+[a-zA-Z0-9_\-\.]+",
    ]

    def __init__(
        self,
        project_root: Path,
        layer_filter: Optional[str] = None,
        include_skipped: bool = True
    ):
        """Initialize the test coverage analyzer.

        Args:
            project_root: Root directory of the project
            layer_filter: Optional filter for specific test layer ("unit", "integration", "e2e")
            include_skipped: Whether to include skipped tests in report
        """
        self.project_root = Path(project_root).resolve()
        self.layer_filter = layer_filter
        self.include_skipped = include_skipped
        self.warnings: List[str] = []
        self._skipped_tests: List[SkippedTest] = []  # Track skipped tests

    def find_testable_items(self, source_file: Path) -> List[Dict[str, str]]:
        """Find testable items (public functions and classes) in a source file.

        Uses AST parsing to identify public functions and classes. Excludes:
        - Private functions (starting with _)
        - Dunder methods (__init__, etc.)

        Args:
            source_file: Path to Python source file

        Returns:
            List of dicts with keys: name, type, file_path

        Security:
            - Validates path is within project root
            - Handles syntax errors gracefully
            - No code execution, only AST parsing
        """
        # Validate path is within project root
        try:
            resolved_path = source_file.resolve()
            resolved_path.relative_to(self.project_root)
        except (ValueError, OSError):
            self.warnings.append(
                f"Security: Path outside project root rejected: {source_file}"
            )
            return []

        # Read and parse file
        try:
            content = source_file.read_text(encoding="utf-8")
            tree = ast.parse(content, filename=str(source_file))
        except SyntaxError as e:
            self.warnings.append(
                f"Syntax error in {source_file.name}: {e.msg} at line {e.lineno}"
            )
            return []
        except Exception as e:
            self.warnings.append(
                f"Failed to parse {source_file.name}: {e}"
            )
            return []

        items = []

        # Only find top-level functions and classes (not nested ones)
        for node in tree.body:
            if isinstance(node, ast.FunctionDef):
                # Skip private functions
                if not node.name.startswith("_"):
                    items.append({
                        "name": node.name,
                        "type": "function",
                        "file_path": str(source_file)
                    })
            elif isinstance(node, ast.ClassDef):
                # Include all classes (even if they start with _)
                items.append({
                    "name": node.name,
                    "type": "class",
                    "file_path": str(source_file)
                })

        return items

    def detect_layer(self, file_path: Path) -> str:
        """Detect test layer from directory structure.

        Looks for layer indicators in the path:
        - tests/unit/ -> "unit"
        - tests/integration/ -> "integration"
        - tests/e2e/ -> "e2e"

        Args:
            file_path: Path to test file

        Returns:
            Layer name ("unit", "integration", "e2e") or "unit" as default

        Generates warning if layer cannot be determined.
        """
        parts = file_path.parts

        # Look for layer indicators
        if "unit" in parts:
            return "unit"
        elif "integration" in parts:
            return "integration"
        elif "e2e" in parts:
            return "e2e"
        else:
            # Generate warning for unknown layer
            self.warnings.append(
                f"Unknown test layer for {file_path.name}, defaulting to 'unit'"
            )
            return "unit"

    def find_skipped_tests(self, pytest_output: str) -> List[SkippedTest]:
        """Parse pytest output for skipped and xfailed tests.

        Extracts test names and reasons from pytest output lines like:
        - "test_file.py::test_func SKIPPED (reason)"
        - "test_file.py::test_func XFAIL (reason)"

        Args:
            pytest_output: Raw pytest stdout/stderr

        Returns:
            List of SkippedTest objects

        Security:
            - Sanitizes skip reasons to remove secrets
            - Generates warning for skips without reasons
        """
        skipped = []

        # Pattern: test_file.py::test_name SKIPPED (reason) or XFAIL (reason)
        skip_pattern = r"([\w/\.]+::\w+)\s+(SKIPPED|XFAIL)(?:\s+\(([^)]+)\))?"

        for match in re.finditer(skip_pattern, pytest_output):
            test_name = match.group(1)
            skip_type = match.group(2)
            reason = match.group(3) if match.group(3) else "No reason provided"

            # Sanitize reason
            sanitized_reason = self._sanitize_skip_reason(reason)

            # Warn if no reason provided
            if reason == "No reason provided":
                self.warnings.append(
                    f"Test {test_name} skipped without reason"
                )

            skipped.append(SkippedTest(
                test_name=test_name,
                reason=sanitized_reason,
                skip_type=skip_type
            ))

        # Store skipped tests for later use
        self._skipped_tests = skipped

        return skipped

    def _sanitize_skip_reason(self, reason: str) -> str:
        """Sanitize skip reason to remove secrets.

        Args:
            reason: Original skip reason

        Returns:
            Sanitized reason with secrets redacted
        """
        sanitized = reason

        for pattern in self.SECRET_PATTERNS:
            sanitized = re.sub(pattern, "***REDACTED***", sanitized)

        return sanitized

    def run_pytest_coverage(self) -> Optional[str]:
        """Run pytest with coverage.

        Tries to run pytest with --cov flag. Falls back to basic pytest
        if pytest-cov is not installed.

        Returns:
            pytest output (stdout) or None on failure

        Security:
            - Uses shell=False
            - No user input in command
            - Timeout protection (60s)
        """
        # Try with pytest-cov first
        try:
            result = subprocess.run(
                ["pytest", str(self.project_root), "--cov", "-v"],
                capture_output=True,
                text=True,
                timeout=60,
                cwd=str(self.project_root)
            )
            # Check for failure
            if result.returncode != 0 and not result.stdout and not result.stderr:
                self.warnings.append(
                    f"pytest execution failed with exit code {result.returncode}"
                )
            elif result.returncode != 0 and result.stderr:
                self.warnings.append(
                    f"pytest execution error: {result.stderr[:100]}"
                )
            return result.stdout + "\n" + result.stderr
        except FileNotFoundError:
            # pytest-cov not installed, try fallback
            try:
                result = subprocess.run(
                    ["pytest", str(self.project_root), "-v"],
                    capture_output=True,
                    text=True,
                    timeout=60,
                    cwd=str(self.project_root)
                )
                # Check for failure
                if result.returncode != 0 and not result.stdout and not result.stderr:
                    self.warnings.append(
                        f"pytest execution failed with exit code {result.returncode}"
                    )
                elif result.returncode != 0 and result.stderr:
                    self.warnings.append(
                        f"pytest execution error: {result.stderr[:100]}"
                    )
                return result.stdout + "\n" + result.stderr
            except FileNotFoundError:
                self.warnings.append(
                    "pytest not installed - only static analysis available"
                )
                return None
            except subprocess.TimeoutExpired:
                self.warnings.append("pytest execution timeout after 60s")
                return None
        except subprocess.TimeoutExpired:
            self.warnings.append("pytest execution timeout after 60s")
            return None
        except Exception as e:
            self.warnings.append(f"pytest execution failed: {e}")
            return None

    def calculate_coverage(self, testable: int, covered: int) -> float:
        """Calculate coverage percentage.

        Args:
            testable: Total number of testable items
            covered: Number of items with coverage

        Returns:
            Coverage percentage (0.0-100.0)

        Edge Cases:
            - Zero testable items: Returns 100.0 (empty project is fully covered)
        """
        if testable == 0:
            return 100.0

        return (covered / testable) * 100.0

    def calculate_skip_rate(self, total_tests: int, skipped_count: Optional[int] = None) -> float:
        """Calculate skip rate and generate warning if high.

        Args:
            total_tests: Total number of tests
            skipped_count: Number of skipped tests (if None, uses stored skipped tests)

        Returns:
            Skip rate percentage (0.0-100.0)

        Generates warning if skip rate > 10%
        """
        if total_tests == 0:
            return 0.0

        # Use provided count or fall back to stored skipped tests
        if skipped_count is None:
            skipped_count = len(self._skipped_tests)

        skip_rate = (skipped_count / total_tests) * 100.0

        # Warn if skip rate > 10%
        if skip_rate > 10.0:
            self.warnings.append(
                f"High skip rate: {skip_rate:.1f}% of tests are skipped"
            )

        return skip_rate

    def get_warnings(self) -> List[str]:
        """Get accumulated warnings.

        Returns:
            List of warning messages
        """
        return self.warnings

    def analyze_coverage(self) -> CoverageReport:
        """Perform complete coverage analysis.

        This is the main entry point for coverage analysis. It:
        1. Finds all testable items in source files
        2. Runs pytest to find test coverage
        3. Parses pytest output for skipped tests
        4. Calculates coverage gaps
        5. Generates coverage report

        Returns:
            CoverageReport with complete analysis

        Implementation:
            This is a basic implementation that demonstrates the structure.
            A production implementation would:
            - Map test files to source files
            - Parse pytest coverage output
            - Track per-layer coverage
            - Identify specific coverage gaps
        """
        report = CoverageReport()

        # Find all Python source files
        src_dirs = [
            self.project_root / "src",
            self.project_root / "lib",
            self.project_root / "plugins"
        ]

        testable_items = []
        for src_dir in src_dirs:
            if src_dir.exists():
                for py_file in src_dir.rglob("*.py"):
                    if py_file.name != "__init__.py":
                        items = self.find_testable_items(py_file)
                        testable_items.extend(items)

        report.total_testable = len(testable_items)

        # Run pytest
        pytest_output = self.run_pytest_coverage()

        if pytest_output:
            # Parse skipped tests
            if self.include_skipped:
                report.skipped_tests = self.find_skipped_tests(pytest_output)

            # Count total tests (simple parsing)
            passed_count = len(re.findall(r"PASSED", pytest_output))
            skipped_count = len(re.findall(r"SKIPPED", pytest_output))
            xfail_count = len(re.findall(r"XFAIL", pytest_output))
            report.total_tests = passed_count + skipped_count + xfail_count

            # Calculate skip rate
            report.skip_rate = self.calculate_skip_rate(
                report.total_tests,
                skipped_count=len(report.skipped_tests)
            )

        # For basic implementation, assume coverage = 0 if we have testable items
        # A full implementation would parse pytest coverage output
        report.total_covered = 0

        # Generate coverage gaps for all testable items (simplified)
        for item in testable_items:
            report.coverage_gaps.append(CoverageGap(
                item_name=item["name"],
                item_type=item["type"],
                file_path=item["file_path"],
                layer="unit"  # Default layer
            ))

        # Calculate coverage percentage
        report.coverage_percentage = self.calculate_coverage(
            report.total_testable,
            report.total_covered
        )

        # Detect test layers
        tests_dir = self.project_root / "tests"
        if tests_dir.exists():
            layer_stats = {}

            for test_file in tests_dir.rglob("test_*.py"):
                layer = self.detect_layer(test_file)

                # Apply layer filter if set
                if self.layer_filter and layer != self.layer_filter:
                    continue

                if layer not in layer_stats:
                    layer_stats[layer] = LayerCoverage(layer_name=layer)

                # Count tests in this file (simplified)
                # Use re.escape() to prevent ReDoS attacks (CWE-1333)
                if pytest_output:
                    file_tests = len(re.findall(
                        rf"{re.escape(test_file.name)}::\w+\s+PASSED",
                        pytest_output
                    ))
                    layer_stats[layer].total_tests += file_tests
                    layer_stats[layer].passed_tests += file_tests

            # Convert to list
            report.layer_coverage = list(layer_stats.values())

        # Add warnings to report
        report.warnings = self.warnings.copy()

        return report


# =============================================================================
# Command-line interface (for testing)
# =============================================================================

if __name__ == "__main__":
    import sys

    if len(sys.argv) > 1:
        project_root = Path(sys.argv[1])
    else:
        project_root = Path.cwd()

    analyzer = TestCoverageAnalyzer(project_root=project_root)
    report = analyzer.analyze_coverage()

    print(f"Total testable items: {report.total_testable}")
    print(f"Total covered: {report.total_covered}")
    print(f"Coverage: {report.coverage_percentage:.1f}%")
    print(f"Coverage gaps: {len(report.coverage_gaps)}")
    print(f"Skipped tests: {len(report.skipped_tests)}")
    print(f"Warnings: {len(report.warnings)}")
