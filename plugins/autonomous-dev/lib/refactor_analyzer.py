#!/usr/bin/env python3
"""Refactor Analyzer -- unified code, docs, and test optimization.

Provides deeper analysis than SweepAnalyzer: test shape analysis (Quality Diamond),
test waste detection, doc redundancy detection, dead code cross-file analysis, and
unused library detection. Composes SweepAnalyzer for quick sweep mode.

Usage:
    from refactor_analyzer import RefactorAnalyzer
    from pathlib import Path

    analyzer = RefactorAnalyzer(Path("."))
    report = analyzer.full_analysis(["tests", "docs", "code"])
    print(report.format_report())

Date: 2026-03-20
"""

import ast
import difflib
import re
import time
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple

# Import SweepAnalyzer with fallback pattern
try:
    from plugins.autonomous_dev.lib.sweep_analyzer import (
        SweepAnalyzer,
        SweepFinding,
        SweepReport,
        SweepSeverity,
    )
except ImportError:
    from sweep_analyzer import (  # type: ignore[no-redef]
        SweepAnalyzer,
        SweepFinding,
        SweepReport,
        SweepSeverity,
    )

# Import doc_drift_detector with fallback pattern (Issue #1098)
try:
    from plugins.autonomous_dev.lib.doc_drift_detector import (
        DocDriftFinding,
        detect_doc_drift,
    )
except ImportError:
    try:
        from doc_drift_detector import (  # type: ignore[no-redef]
            DocDriftFinding,
            detect_doc_drift,
        )
    except ImportError:
        DocDriftFinding = None  # type: ignore[misc,assignment]
        detect_doc_drift = None  # type: ignore[assignment]


# =============================================================================
# Data Classes
# =============================================================================


class RefactorCategory(str, Enum):
    """Category of refactor finding."""

    TEST_SHAPE = "test_shape"
    TEST_WASTE = "test_waste"
    DOC_REDUNDANCY = "doc_redundancy"
    DEAD_CODE = "dead_code"
    UNUSED_LIB = "unused_lib"
    COMPLEXITY = "complexity"
    HYGIENE = "hygiene"


class OptimizationType(str, Enum):
    """Whether the finding is hygiene (cleanup) or optimization (improvement)."""

    HYGIENE = "hygiene"
    OPTIMIZATION = "optimization"


class ConfidenceLevel(str, Enum):
    """Confidence level of a refactor finding."""

    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


@dataclass
class RefactorFinding:
    """A single refactoring finding.

    Attributes:
        category: Category of the finding.
        severity: Severity level (reuses SweepSeverity).
        file_path: Path to the affected file.
        description: Human-readable description of the issue.
        suggestion: Recommended action to resolve the issue.
        optimization_type: Whether this is hygiene or optimization.
        line: Optional line number where the issue was found.
    """

    category: RefactorCategory
    severity: SweepSeverity
    file_path: str
    description: str
    suggestion: str
    optimization_type: OptimizationType = OptimizationType.OPTIMIZATION
    line: Optional[int] = None
    confidence: ConfidenceLevel = ConfidenceLevel.HIGH

    def format(self) -> str:
        """Format the finding as a single-line summary.

        Returns:
            Formatted string like '[HIGH] path/to/file.py:42: description'.
            Appends confidence tag for non-HIGH confidence levels.
        """
        loc = f":{self.line}" if self.line else ""
        base = f"[{self.severity.value.upper()}] {self.file_path}{loc}: {self.description}"
        if self.confidence != ConfidenceLevel.HIGH:
            base += f" [confidence:{self.confidence.value}]"
        return base


@dataclass
class RefactorReport:
    """Aggregated report of all refactor findings.

    Attributes:
        findings: List of all detected findings.
        scan_duration_ms: Total scan duration in milliseconds.
        modes_run: List of analysis modes that were executed.
        test_shape: Optional test shape distribution data.
    """

    findings: List[RefactorFinding] = field(default_factory=list)
    scan_duration_ms: int = 0
    modes_run: List[str] = field(default_factory=list)
    test_shape: Optional[Dict[str, int]] = None

    @property
    def has_findings(self) -> bool:
        """Whether any findings were detected."""
        return len(self.findings) > 0

    @property
    def summary(self) -> Dict[str, int]:
        """Count of findings grouped by category.

        Returns:
            Dictionary mapping category names to finding counts.
        """
        counts: Dict[str, int] = {}
        for f in self.findings:
            counts[f.category.value] = counts.get(f.category.value, 0) + 1
        return counts

    def format_report(self) -> str:
        """Format the full report as a readable multi-line string.

        Groups findings by category, sorts by severity within each group,
        and includes a summary header with optional test shape table.

        Returns:
            Formatted report string.
        """
        if not self.findings:
            return "Clean refactor analysis -- no optimization opportunities found."

        severity_order = {
            SweepSeverity.CRITICAL: 0,
            SweepSeverity.HIGH: 1,
            SweepSeverity.MEDIUM: 2,
            SweepSeverity.LOW: 3,
        }

        lines: List[str] = []
        lines.append(
            f"Refactor Report ({len(self.findings)} findings, {self.scan_duration_ms}ms)"
        )
        lines.append("=" * 60)

        # Include test shape table if available
        if self.test_shape:
            lines.append("")
            lines.append("## Test Shape Distribution")
            lines.append("-" * 40)
            targets = {
                "unit": 60,
                "integration": 25,
                "property": 5,
                "genai": 10,
            }
            total_tests = sum(self.test_shape.values()) or 1
            lines.append(f"  {'Type':<15} {'Count':>6} {'Actual%':>8} {'Target%':>8}")
            for test_type in ["unit", "integration", "property", "genai"]:
                count = self.test_shape.get(test_type, 0)
                actual_pct = (count / total_tests) * 100
                target_pct = targets.get(test_type, 0)
                lines.append(
                    f"  {test_type:<15} {count:>6} {actual_pct:>7.1f}% {target_pct:>7d}%"
                )

        # Group by category
        by_category: Dict[RefactorCategory, List[RefactorFinding]] = {}
        for f in self.findings:
            by_category.setdefault(f.category, []).append(f)

        # Display order
        display_order = [
            RefactorCategory.TEST_SHAPE,
            RefactorCategory.TEST_WASTE,
            RefactorCategory.DOC_REDUNDANCY,
            RefactorCategory.DEAD_CODE,
            RefactorCategory.UNUSED_LIB,
            RefactorCategory.COMPLEXITY,
            RefactorCategory.HYGIENE,
        ]

        for cat in display_order:
            if cat not in by_category:
                continue
            cat_findings = sorted(
                by_category[cat], key=lambda f: severity_order.get(f.severity, 9)
            )
            lines.append("")
            lines.append(f"## {cat.value.upper()} ({len(cat_findings)} issues)")
            lines.append("-" * 40)
            for f in cat_findings:
                lines.append(f"  {f.format()}")
                lines.append(f"    Suggestion: {f.suggestion}")

        lines.append("")
        lines.append(f"Modes run: {', '.join(self.modes_run)}")
        return "\n".join(lines)

    def to_dict(self) -> Dict:
        """Serialize to dictionary for JSON output.

        Returns:
            Dictionary with findings, summary, shape, and duration.
        """
        return {
            "findings": [
                {
                    "file": f.file_path,
                    "line": f.line,
                    "category": f.category.value,
                    "severity": f.severity.value,
                    "description": f.description,
                    "suggestion": f.suggestion,
                    "optimization_type": f.optimization_type.value,
                    "confidence": f.confidence.value,
                }
                for f in self.findings
            ],
            "summary": self.summary,
            "test_shape": self.test_shape,
            "duration_ms": self.scan_duration_ms,
            "modes_run": self.modes_run,
        }


# =============================================================================
# Refactor Analyzer
# =============================================================================


class RefactorAnalyzer:
    """Orchestrates deep refactoring analysis across tests, docs, and code.

    Provides deeper optimization analysis than SweepAnalyzer, including test
    shape analysis (Quality Diamond), test waste detection, doc redundancy
    detection via SequenceMatcher, dead code cross-file analysis, and unused
    library detection. Composes SweepAnalyzer for quick sweep mode.

    Args:
        project_root: Root directory of the project to analyze.

    Example:
        >>> analyzer = RefactorAnalyzer(Path("."))
        >>> report = analyzer.full_analysis(["tests", "docs", "code"])
        >>> if report.has_findings:
        ...     print(report.format_report())
    """

    # Quality Diamond targets (percentages)
    QUALITY_DIAMOND_TARGETS: Dict[str, int] = {
        "unit": 60,
        "integration": 25,
        "property": 5,
        "genai": 10,
    }

    # Decorators that indicate a function/class is used externally
    DECORATOR_WHITELIST: Set[str] = {
        "pytest.fixture",
        "pytest.mark",
        "property",
        "staticmethod",
        "classmethod",
        "abstractmethod",
        "dataclass",
        "app.route",
        "router.get",
        "router.post",
        "click.command",
        "click.group",
    }

    DEFAULT_EXCLUDE_DIRS: Set[str] = {
        ".git", ".svn", ".hg",                  # Version control
        "node_modules",                           # Node.js
        "venv", ".venv", "env",                  # Virtual environments
        "__pycache__", ".pytest_cache",           # Python cache
        ".mypy_cache", ".ruff_cache",             # Linter caches
        "build", "dist", "egg-info",             # Build artifacts
        ".tox", ".nox",                           # Test runners
        "site-packages",                          # Installed packages
        ".idea", ".vscode",                       # IDE configs
        "coverage", "htmlcov",                    # Coverage reports
        ".claude",                                # Install target (duplicate of plugins/)
        ".worktrees",                             # Git worktrees (full repo copies)
        "sessions",                               # Session logs
        "archived",                               # Archived files
    }

    def __init__(self, project_root: "str | Path", *, exclude_dirs: Optional[Set[str]] = None):
        self.project_root = Path(project_root).resolve()
        self.exclude_dirs = exclude_dirs if exclude_dirs is not None else self.DEFAULT_EXCLUDE_DIRS
        self._sweep_analyzer = SweepAnalyzer(self.project_root)

    def _should_skip_path(self, path: Path) -> bool:
        """Check if path should be skipped based on exclude_dirs.

        Args:
            path: Path to check against excluded directory names.

        Returns:
            True if any part of the path matches an excluded directory name.
        """
        for part in path.parts:
            if part in self.exclude_dirs:
                return True
        return False

    def analyze_tests(self) -> List[RefactorFinding]:
        """Analyze test suite for shape imbalance and waste.

        Performs test shape analysis (Quality Diamond comparison) and
        test waste detection (mocked-everything, trivial, duplicate).

        Returns:
            List of test-related refactor findings.
        """
        findings: List[RefactorFinding] = []

        try:
            shape_findings, shape_data = self._analyze_test_shape()
            findings.extend(shape_findings)
            self._last_test_shape = shape_data
        except Exception:
            self._last_test_shape = {}

        try:
            findings.extend(self._detect_test_waste())
        except Exception:
            pass

        return findings

    def analyze_docs(self) -> List[RefactorFinding]:
        """Analyze documentation for redundancy.

        Uses difflib.SequenceMatcher to detect pairs of .md files with
        similarity ratio > 0.85.

        Returns:
            List of doc-related refactor findings.
        """
        findings: List[RefactorFinding] = []

        try:
            findings.extend(self._detect_doc_redundancy())
        except Exception:
            pass

        return findings

    def analyze_doc_drift(self) -> List[RefactorFinding]:
        """Run narrative-doc drift sweep (Issue #1098).

        Sweeps every doc with ``covers:`` frontmatter against actual
        code/component state. Detects count drift (e.g. "216 libraries" vs
        actual 219 files) and enumeration drift (list items with no matching
        source artifact). Idempotent and deterministic.

        Returns:
            List of doc-drift refactor findings with category="docs".
        """
        findings: List[RefactorFinding] = []

        try:
            if detect_doc_drift is None:
                return findings
            drift_findings = detect_doc_drift(self.project_root)
            for df in drift_findings:
                # Map severity string to SweepSeverity
                sev_map = {
                    "low": SweepSeverity.LOW,
                    "medium": SweepSeverity.MEDIUM,
                    "high": SweepSeverity.HIGH,
                }
                severity = sev_map.get(df.severity, SweepSeverity.MEDIUM)
                findings.append(
                    RefactorFinding(
                        category=RefactorCategory.DOC_REDUNDANCY,
                        severity=severity,
                        file_path=df.doc_path,
                        description=df.description,
                        suggestion=(
                            "Update the documented count/enumeration to match actual"
                            " source artifacts."
                        ),
                        optimization_type=OptimizationType.HYGIENE,
                        line=df.line_number,
                    )
                )
        except Exception:
            pass

        return findings

    def analyze_code(self) -> List[RefactorFinding]:
        """Analyze code for dead code and unused libraries.

        Performs cross-file dead code detection via AST and unused lib/
        module detection.

        Returns:
            List of code-related refactor findings.
        """
        findings: List[RefactorFinding] = []

        try:
            findings.extend(self._detect_dead_code_cross_file())
        except Exception:
            pass

        try:
            findings.extend(self._detect_unused_libs())
        except Exception:
            pass

        return findings

    def quick_sweep(self) -> RefactorReport:
        """Run a quick hygiene sweep by delegating to SweepAnalyzer.

        Returns:
            RefactorReport wrapping SweepAnalyzer's findings as HYGIENE category.
        """
        start = time.time()

        try:
            sweep_report = self._sweep_analyzer.full_sweep()
        except Exception:
            elapsed_ms = int((time.time() - start) * 1000)
            return RefactorReport(
                findings=[],
                scan_duration_ms=elapsed_ms,
                modes_run=["quick"],
            )

        # Convert SweepFindings to RefactorFindings
        refactor_findings: List[RefactorFinding] = []
        for sf in sweep_report.findings:
            refactor_findings.append(
                RefactorFinding(
                    category=RefactorCategory.HYGIENE,
                    severity=sf.severity,
                    file_path=sf.file_path,
                    description=sf.description,
                    suggestion=sf.suggested_fix,
                    optimization_type=OptimizationType.HYGIENE,
                    line=sf.line,
                )
            )

        elapsed_ms = int((time.time() - start) * 1000)
        return RefactorReport(
            findings=refactor_findings,
            scan_duration_ms=elapsed_ms,
            modes_run=["quick"],
        )

    def full_analysis(self, modes: Optional[List[str]] = None) -> RefactorReport:
        """Run specified analysis modes and return aggregated report.

        Args:
            modes: List of modes to run. Valid values: "tests", "docs", "code".
                   If None or empty, runs all three modes.

        Returns:
            RefactorReport aggregating findings from specified modes.
        """
        if not modes:
            modes = ["tests", "docs", "code"]

        start = time.time()
        all_findings: List[RefactorFinding] = []
        self._last_test_shape: Dict[str, int] = {}
        modes_run: List[str] = []

        mode_map = {
            "tests": self.analyze_tests,
            "docs": self.analyze_doc_drift,         # NEW — drift detection (Issue #1098)
            "docs_redundancy": self.analyze_docs,   # RENAMED — preserves existing redundancy behavior
            "code": self.analyze_code,
        }

        for mode_name in modes:
            analyze_fn = mode_map.get(mode_name)
            if analyze_fn:
                all_findings.extend(analyze_fn())
                modes_run.append(mode_name)

        elapsed_ms = int((time.time() - start) * 1000)
        return RefactorReport(
            findings=all_findings,
            scan_duration_ms=elapsed_ms,
            modes_run=modes_run,
            test_shape=self._last_test_shape if self._last_test_shape else None,
        )

    # =========================================================================
    # Private Helpers
    # =========================================================================

    def _analyze_test_shape(self) -> Tuple[List[RefactorFinding], Dict[str, int]]:
        """Classify tests by type and compare to Quality Diamond targets.

        Returns:
            Tuple of (findings about shape imbalance, shape distribution dict).
        """
        findings: List[RefactorFinding] = []
        shape: Dict[str, int] = {
            "unit": 0,
            "integration": 0,
            "property": 0,
            "genai": 0,
        }

        test_dirs = [
            self.project_root / "tests",
            self.project_root / "test",
        ]

        for test_dir in test_dirs:
            if not test_dir.is_dir():
                continue
            for py_file in test_dir.rglob("*.py"):
                if py_file.name.startswith("__"):
                    continue
                try:
                    source = py_file.read_text(encoding="utf-8")
                    tree = ast.parse(source, filename=str(py_file))
                except (SyntaxError, UnicodeDecodeError, OSError):
                    continue

                test_type = self._classify_test_file(py_file, source, tree)
                shape[test_type] = shape.get(test_type, 0) + 1

        total = sum(shape.values())
        if total == 0:
            return findings, shape

        # Compare to Quality Diamond targets
        for test_type, target_pct in self.QUALITY_DIAMOND_TARGETS.items():
            actual_pct = (shape.get(test_type, 0) / total) * 100
            deviation = actual_pct - target_pct

            if abs(deviation) > 20:
                severity = SweepSeverity.HIGH
            elif abs(deviation) > 10:
                severity = SweepSeverity.MEDIUM
            else:
                continue  # Within acceptable range

            direction = "over-represented" if deviation > 0 else "under-represented"
            findings.append(
                RefactorFinding(
                    category=RefactorCategory.TEST_SHAPE,
                    severity=severity,
                    file_path="tests/",
                    description=(
                        f"{test_type} tests {direction}: "
                        f"{actual_pct:.0f}% actual vs {target_pct}% target"
                    ),
                    suggestion=(
                        f"{'Reduce' if deviation > 0 else 'Add more'} {test_type} tests "
                        f"to align with Quality Diamond"
                    ),
                    optimization_type=OptimizationType.OPTIMIZATION,
                )
            )

        return findings, shape

    def _classify_test_file(
        self, file_path: Path, source: str, tree: ast.AST
    ) -> str:
        """Classify a test file as unit, integration, property, or genai.

        Args:
            file_path: Path to the test file.
            source: Source code of the file.
            tree: Parsed AST of the file.

        Returns:
            Test type string: "unit", "integration", "property", or "genai".
        """
        path_str = str(file_path).lower()

        # Path-based classification
        if "/genai/" in path_str or "genai" in file_path.name.lower():
            return "genai"
        if "/integration/" in path_str or "integration" in file_path.name.lower():
            return "integration"
        if "/property/" in path_str or "property" in file_path.name.lower():
            return "property"

        # Marker-based classification from source
        for node in ast.walk(tree):
            if isinstance(node, ast.Attribute):
                if isinstance(node.value, ast.Attribute):
                    if (
                        hasattr(node.value, "attr")
                        and node.value.attr == "mark"
                        and hasattr(node, "attr")
                    ):
                        marker = node.attr
                        if marker == "genai":
                            return "genai"
                        if marker == "integration":
                            return "integration"
                        if marker in ("property", "hypothesis"):
                            return "property"

        # Import-based classification
        if "hypothesis" in source:
            return "property"
        if "genai" in source and ("judge" in source or "llm" in source.lower()):
            return "genai"

        # Fixture-based: heavy fixture usage suggests integration
        fixture_count = source.count("@pytest.fixture")
        if fixture_count >= 3:
            return "integration"

        # Default to unit
        return "unit"

    def _detect_test_waste(self) -> List[RefactorFinding]:
        """Detect wasteful test patterns: mocked-everything, trivial, duplicate.

        Returns:
            List of test waste findings.
        """
        findings: List[RefactorFinding] = []

        test_dirs = [
            self.project_root / "tests",
            self.project_root / "test",
        ]

        test_bodies: List[Tuple[str, str, int]] = []  # (normalized_body, file_path, lineno)

        for test_dir in test_dirs:
            if not test_dir.is_dir():
                continue
            for py_file in test_dir.rglob("*.py"):
                if py_file.name.startswith("__"):
                    continue
                try:
                    source = py_file.read_text(encoding="utf-8")
                    tree = ast.parse(source, filename=str(py_file))
                except (SyntaxError, UnicodeDecodeError, OSError):
                    continue

                rel_path = str(py_file.relative_to(self.project_root))

                for node in ast.walk(tree):
                    if not isinstance(node, ast.FunctionDef):
                        continue
                    if not node.name.startswith("test_"):
                        continue

                    # Check for trivial tests (body is just assert True/None/pass)
                    if self._is_trivial_test(node):
                        findings.append(
                            RefactorFinding(
                                category=RefactorCategory.TEST_WASTE,
                                severity=SweepSeverity.MEDIUM,
                                file_path=rel_path,
                                description=f"Trivial test: {node.name} (body has no meaningful assertions)",
                                suggestion="Add meaningful assertions or remove the test",
                                optimization_type=OptimizationType.HYGIENE,
                                line=node.lineno,
                            )
                        )

                    # Check for mocked-everything tests
                    if self._is_mocked_everything(node, source):
                        findings.append(
                            RefactorFinding(
                                category=RefactorCategory.TEST_WASTE,
                                severity=SweepSeverity.LOW,
                                file_path=rel_path,
                                description=f"Over-mocked test: {node.name}",
                                suggestion="Reduce mocking -- test real behavior where possible",
                                optimization_type=OptimizationType.OPTIMIZATION,
                                line=node.lineno,
                            )
                        )

                    # Collect body for duplicate detection
                    body_str = ast.dump(ast.Module(body=node.body, type_ignores=[]))
                    test_bodies.append((body_str, rel_path, node.lineno))

        # Detect duplicate test bodies
        seen_bodies: Dict[str, Tuple[str, int]] = {}
        for body_str, file_path, lineno in test_bodies:
            if body_str in seen_bodies:
                orig_file, orig_line = seen_bodies[body_str]
                findings.append(
                    RefactorFinding(
                        category=RefactorCategory.TEST_WASTE,
                        severity=SweepSeverity.LOW,
                        file_path=file_path,
                        description=(
                            f"Duplicate test body at line {lineno} "
                            f"(same as {orig_file}:{orig_line})"
                        ),
                        suggestion="Consider parameterizing or removing the duplicate",
                        optimization_type=OptimizationType.HYGIENE,
                        line=lineno,
                    )
                )
            else:
                seen_bodies[body_str] = (file_path, lineno)

        return findings

    def _is_trivial_test(self, func_node: ast.FunctionDef) -> bool:
        """Check if a test function has a trivial body.

        A trivial test has only: pass, assert True, assert None, or just
        a docstring with no real assertions.

        Args:
            func_node: AST FunctionDef node for the test function.

        Returns:
            True if the test body is trivial.
        """
        body = func_node.body

        # Filter out docstrings
        meaningful = []
        for stmt in body:
            if isinstance(stmt, ast.Expr) and isinstance(stmt.value, (ast.Constant, ast.Str)):
                continue  # docstring
            meaningful.append(stmt)

        if not meaningful:
            return True  # Only docstring or empty

        if len(meaningful) == 1:
            stmt = meaningful[0]
            # pass statement
            if isinstance(stmt, ast.Pass):
                return True
            # assert True / assert None
            if isinstance(stmt, ast.Assert):
                if isinstance(stmt.test, ast.Constant):
                    if stmt.test.value is True or stmt.test.value is None:
                        return True
                # assert True (NameConstant in older Python)
                if isinstance(stmt.test, ast.NameConstant):
                    if stmt.test.value is True or stmt.test.value is None:
                        return True

        return False

    def _is_mocked_everything(self, func_node: ast.FunctionDef, source: str) -> bool:
        """Check if a test function has excessive mocking.

        Heuristic: more @patch decorators than assert statements.

        Args:
            func_node: AST FunctionDef node for the test function.
            source: Full source code of the file.

        Returns:
            True if the test appears to mock everything.
        """
        # Count @patch decorators
        patch_count = 0
        for dec in func_node.decorator_list:
            dec_str = ast.dump(dec)
            if "patch" in dec_str.lower():
                patch_count += 1

        if patch_count == 0:
            return False

        # Count assert statements in body
        assert_count = 0
        for node in ast.walk(ast.Module(body=func_node.body, type_ignores=[])):
            if isinstance(node, ast.Assert):
                assert_count += 1
            # Also count pytest-style assert calls (assert_called, etc.)
            if isinstance(node, ast.Attribute) and isinstance(node.attr, str):
                if node.attr.startswith("assert_"):
                    assert_count += 1

        # Over-mocked: 3+ patches with fewer assertions than patches
        return patch_count >= 3 and assert_count < patch_count

    def _detect_doc_redundancy(self) -> List[RefactorFinding]:
        """Detect pairs of .md files with high content similarity.

        Uses difflib.SequenceMatcher with ratio > 0.85 threshold.

        Returns:
            List of doc redundancy findings.
        """
        findings: List[RefactorFinding] = []

        # Collect .md files, skipping excluded directories
        md_files: List[Path] = []

        for md_file in self.project_root.rglob("*.md"):
            # Skip excluded directories
            if self._should_skip_path(md_file):
                continue
            # Skip very large files (>100KB) to avoid slow comparisons
            try:
                if md_file.stat().st_size > 100_000:
                    continue
            except OSError:
                continue
            md_files.append(md_file)

        # Read file contents
        file_contents: Dict[Path, str] = {}
        for md_file in md_files:
            try:
                file_contents[md_file] = md_file.read_text(encoding="utf-8")
            except (OSError, UnicodeDecodeError):
                continue

        # Pairwise comparison with size pre-filter
        # Files with very different sizes cannot have >85% similarity,
        # so skip pairs where the smaller file is less than 70% of the larger.
        # This eliminates most comparisons without missing real duplicates.
        compared: Set[Tuple[Path, Path]] = set()
        for file_a in file_contents:
            len_a = len(file_contents[file_a])
            for file_b in file_contents:
                if file_a >= file_b:
                    continue
                pair = (file_a, file_b)
                if pair in compared:
                    continue
                compared.add(pair)

                # Size pre-filter: skip if sizes are too different
                len_b = len(file_contents[file_b])
                if len_a > 0 and len_b > 0:
                    size_ratio = min(len_a, len_b) / max(len_a, len_b)
                    if size_ratio < 0.70:
                        continue

                matcher = difflib.SequenceMatcher(
                    None,
                    file_contents[file_a],
                    file_contents[file_b],
                )
                # Use quick_ratio() as fast upper bound; skip if below threshold
                if matcher.quick_ratio() <= 0.85:
                    continue
                ratio = matcher.ratio()

                if ratio > 0.85:
                    rel_a = str(file_a.relative_to(self.project_root))
                    rel_b = str(file_b.relative_to(self.project_root))
                    findings.append(
                        RefactorFinding(
                            category=RefactorCategory.DOC_REDUNDANCY,
                            severity=SweepSeverity.MEDIUM,
                            file_path=rel_a,
                            description=(
                                f"High similarity ({ratio:.0%}) between "
                                f"{rel_a} and {rel_b}"
                            ),
                            suggestion="Consider merging or deduplicating these documents",
                            optimization_type=OptimizationType.OPTIMIZATION,
                        )
                    )

        return findings

    def _detect_dead_code_cross_file(self) -> List[RefactorFinding]:
        """Detect functions and classes defined but never referenced across files.

        Scans Python files in lib/ and src/ directories, builds a definition
        map, then checks for references across all project Python files.

        Returns:
            List of dead code findings.
        """
        findings: List[RefactorFinding] = []

        # Directories to scan for definitions
        def_dirs = [
            self.project_root / "plugins" / "autonomous-dev" / "lib",
            self.project_root / "src",
        ]

        # Collect definitions: name -> (file_path, lineno, type)
        definitions: Dict[str, Tuple[str, int, str]] = {}

        for def_dir in def_dirs:
            if not def_dir.is_dir():
                continue
            for py_file in def_dir.rglob("*.py"):
                if py_file.name.startswith("__"):
                    continue
                if self._should_skip_path(py_file):
                    continue
                try:
                    source = py_file.read_text(encoding="utf-8")
                    tree = ast.parse(source, filename=str(py_file))
                except (SyntaxError, UnicodeDecodeError, OSError):
                    continue

                rel_path = str(py_file.relative_to(self.project_root))
                for node in ast.iter_child_nodes(tree):
                    if isinstance(node, ast.FunctionDef):
                        if node.name.startswith("_"):
                            continue  # Skip private functions
                        if self._has_whitelisted_decorator(node):
                            continue
                        definitions[node.name] = (rel_path, node.lineno, "function")
                    elif isinstance(node, ast.ClassDef):
                        if node.name.startswith("_"):
                            continue
                        if self._has_whitelisted_decorator(node):
                            continue
                        definitions[node.name] = (rel_path, node.lineno, "class")

        if not definitions:
            return findings

        # Scan all Python files for references
        referenced_names: Set[str] = set()
        for py_file in self.project_root.rglob("*.py"):
            if self._should_skip_path(py_file):
                continue
            try:
                source = py_file.read_text(encoding="utf-8")
            except (OSError, UnicodeDecodeError):
                continue

            for name in definitions:
                # Check if name appears in source (beyond its definition file)
                # Use word-boundary regex to avoid substring false positives
                def_file = definitions[name][0]
                rel_file = str(py_file.relative_to(self.project_root))
                pattern = r"\b" + re.escape(name) + r"\b"
                if rel_file == def_file:
                    # In definition file: need 2+ occurrences (definition + usage)
                    if len(re.findall(pattern, source)) >= 2:
                        referenced_names.add(name)
                else:
                    if re.search(pattern, source):
                        referenced_names.add(name)

        # Report unreferenced definitions
        for name, (file_path, lineno, def_type) in definitions.items():
            if name not in referenced_names:
                findings.append(
                    RefactorFinding(
                        category=RefactorCategory.DEAD_CODE,
                        severity=SweepSeverity.MEDIUM,
                        file_path=file_path,
                        description=f"Potentially dead {def_type}: {name}",
                        suggestion=f"Remove {def_type} '{name}' if no longer needed",
                        optimization_type=OptimizationType.HYGIENE,
                        line=lineno,
                        confidence=ConfidenceLevel.MEDIUM,
                    )
                )

        return findings

    def _has_whitelisted_decorator(
        self, node: ast.FunctionDef | ast.ClassDef
    ) -> bool:
        """Check if a function/class has a whitelisted decorator.

        Args:
            node: AST node to check.

        Returns:
            True if the node has a decorator in the whitelist.
        """
        for dec in node.decorator_list:
            dec_str = ast.dump(dec)
            for whitelist_entry in self.DECORATOR_WHITELIST:
                if whitelist_entry in dec_str:
                    return True
        return False

    def _detect_unused_libs(self) -> List[RefactorFinding]:
        """Detect lib/ modules that are never imported by non-test, non-archived files.

        Returns:
            List of unused lib findings.
        """
        findings: List[RefactorFinding] = []

        lib_dir = self.project_root / "plugins" / "autonomous-dev" / "lib"
        if not lib_dir.is_dir():
            return findings

        # Get all lib module names
        lib_modules: Dict[str, Path] = {}
        for py_file in lib_dir.glob("*.py"):
            if py_file.name.startswith("__"):
                continue
            module_name = py_file.stem
            lib_modules[module_name] = py_file

        if not lib_modules:
            return findings

        # Scan non-test, non-archived Python files for imports
        # Also exclude "tests" and "test" directories (method-specific, not class-level)
        test_dirs = {"tests", "test"}

        imported_modules: Set[str] = set()
        for py_file in self.project_root.rglob("*.py"):
            if self._should_skip_path(py_file):
                continue
            if any(part in test_dirs for part in py_file.parts):
                continue
            # Skip the lib file itself
            if py_file.parent == lib_dir:
                continue
            try:
                source = py_file.read_text(encoding="utf-8")
            except (OSError, UnicodeDecodeError):
                continue

            for module_name in lib_modules:
                if re.search(r"\b" + re.escape(module_name) + r"\b", source):
                    imported_modules.add(module_name)

        # Scan .md files (command/agent markdown files may reference libs)
        for md_file in self.project_root.rglob("*.md"):
            if self._should_skip_path(md_file):
                continue
            if any(part in test_dirs for part in md_file.parts):
                continue
            try:
                source = md_file.read_text(encoding="utf-8")
            except (OSError, UnicodeDecodeError):
                continue

            for module_name in lib_modules:
                if re.search(r"\b" + re.escape(module_name) + r"\b", source):
                    imported_modules.add(module_name)

        # Scan .sh files (shell scripts may reference libs)
        for sh_file in self.project_root.rglob("*.sh"):
            if self._should_skip_path(sh_file):
                continue
            if any(part in test_dirs for part in sh_file.parts):
                continue
            try:
                source = sh_file.read_text(encoding="utf-8")
            except (OSError, UnicodeDecodeError):
                continue

            for module_name in lib_modules:
                if re.search(r"\b" + re.escape(module_name) + r"\b", source):
                    imported_modules.add(module_name)

        # Report modules never referenced
        for module_name, module_path in lib_modules.items():
            if module_name not in imported_modules:
                rel_path = str(module_path.relative_to(self.project_root))
                findings.append(
                    RefactorFinding(
                        category=RefactorCategory.UNUSED_LIB,
                        severity=SweepSeverity.LOW,
                        file_path=rel_path,
                        description=f"Lib module '{module_name}' not imported outside tests",
                        suggestion=f"Archive or remove '{module_name}.py' if no longer needed",
                        optimization_type=OptimizationType.HYGIENE,
                        confidence=ConfidenceLevel.MEDIUM,
                    )
                )

        return findings
