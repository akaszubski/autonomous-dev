#!/usr/bin/env python3
"""Test Pruning Analyzer -- detects orphaned, stale, and redundant tests.

AST-based analyzer that scans test files for dead imports, archived references,
zero-assertion tests, duplicate coverage, and stale regression tests. Default
output is informational. The ``prune_tests()`` method can delete fully-flagged
files with safety guards (dry_run default, security exclusion, tier protection,
whole-file-only deletion).

Usage:
    from test_pruning_analyzer import TestPruningAnalyzer
    from pathlib import Path

    analyzer = TestPruningAnalyzer(Path("."))
    report = analyzer.analyze()
    print(report.format_table())

    # Pruning (dry run by default):
    result = analyzer.prune_tests()  # dry_run=True, shows candidates
    result = analyzer.prune_tests(dry_run=False)  # actually deletes

Date: 2026-04-06
"""

from __future__ import annotations

import ast
import importlib.util
import logging
import re
import time
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple

try:
    from plugins.autonomous_dev.lib.tier_registry import get_tier_for_path, is_prunable
except ImportError:
    from tier_registry import get_tier_for_path, is_prunable

logger = logging.getLogger(__name__)


class PruningCategory(str, Enum):
    """Categories of pruning findings."""

    DEAD_IMPORT = "dead_import"
    ARCHIVED_REF = "archived_ref"
    ZERO_ASSERTION = "zero_assertion"
    DUPLICATE_COVERAGE = "duplicate_coverage"
    STALE_REGRESSION = "stale_regression"


class Severity(str, Enum):
    """Severity levels for findings."""

    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


@dataclass
class PruningFinding:
    """A single pruning finding.

    Args:
        file_path: Path to the test file containing the finding.
        line: Line number where the finding occurs.
        category: Type of pruning issue detected.
        severity: How important this finding is.
        description: Human-readable description of the issue.
        suggestion: Recommended action.
        prunable: Whether the file can be safely pruned (based on tier).
    """

    file_path: str
    line: int
    category: PruningCategory
    severity: Severity
    description: str
    suggestion: str
    prunable: bool


@dataclass
class PruningReport:
    """Aggregated pruning analysis results.

    Args:
        findings: All pruning findings across scanned files.
        scan_duration_ms: Total scan time in milliseconds.
        files_scanned: Number of test files scanned.
    """

    findings: List[PruningFinding] = field(default_factory=list)
    scan_duration_ms: float = 0.0
    files_scanned: int = 0

    def format_table(self) -> str:
        """Format findings as a markdown table.

        Returns:
            Markdown-formatted table string.
        """
        lines = [
            f"## Test Pruning Report",
            f"",
            f"**Files scanned**: {self.files_scanned} | "
            f"**Findings**: {len(self.findings)} | "
            f"**Duration**: {self.scan_duration_ms:.0f}ms",
            f"",
        ]

        if not self.findings:
            lines.append("No pruning candidates found.")
            return "\n".join(lines)

        lines.append(
            "| File | Line | Category | Severity | Prunable | Description |"
        )
        lines.append(
            "|------|------|----------|----------|----------|-------------|"
        )

        for f in sorted(self.findings, key=lambda x: (x.severity.value, x.file_path)):
            prunable_marker = "yes" if f.prunable else "no"
            lines.append(
                f"| {f.file_path} | {f.line} | {f.category.value} | "
                f"{f.severity.value} | {prunable_marker} | {f.description} |"
            )

        return "\n".join(lines)


@dataclass
class PruneResult:
    """Result of a prune_tests() operation.

    Args:
        deleted_files: List of Path objects that were deleted.
        skipped_files: List of (Path, reason) tuples for files that were skipped.
        dry_run: Whether this was a dry-run (no files actually deleted).
        error_messages: List of error strings from failed deletions.
    """

    deleted_files: List[Path] = field(default_factory=list)
    skipped_files: List[Tuple[Path, str]] = field(default_factory=list)
    dry_run: bool = True
    error_messages: List[str] = field(default_factory=list)


class TestPruningAnalyzer:
    """AST-based analyzer for orphaned, stale, and redundant tests.

    Args:
        project_root: Root directory of the project to analyze.
    """

    # Directories to skip during file discovery
    SKIP_DIRS = {"__pycache__", ".git", ".worktrees", "archived", "node_modules", ".tox", ".venv", "venv"}

    def __init__(self, project_root: Path) -> None:
        self.project_root = project_root.resolve()

    def analyze(self) -> PruningReport:
        """Run all pruning detectors and return a consolidated report.

        Returns:
            PruningReport with all findings, timing, and file count.
        """
        start_time = time.monotonic()
        test_files = self._discover_test_files()
        findings: List[PruningFinding] = []

        detectors = [
            self._detect_dead_imports,
            self._detect_archived_references,
            self._detect_zero_assertion_tests,
            self._detect_duplicate_coverage,
            self._detect_stale_regressions,
        ]

        for detector in detectors:
            try:
                findings.extend(detector(test_files))
            except Exception as e:
                logger.warning("Detector %s failed: %s", detector.__name__, e)

        elapsed_ms = (time.monotonic() - start_time) * 1000

        return PruningReport(
            findings=findings,
            scan_duration_ms=elapsed_ms,
            files_scanned=len(test_files),
        )

    # Default safe categories for auto-pruning (exclude duplicate_coverage and
    # stale_regression which require human judgment)
    SAFE_PRUNE_CATEGORIES: Set[str] = {
        PruningCategory.DEAD_IMPORT.value,
        PruningCategory.ARCHIVED_REF.value,
        PruningCategory.ZERO_ASSERTION.value,
    }

    # Default directories to exclude from pruning (OWASP: never auto-prune security tests)
    DEFAULT_EXCLUDE_DIRS: Set[str] = {"tests/security"}

    def prune_tests(
        self,
        *,
        dry_run: bool = True,
        categories: Optional[Set[str]] = None,
        exclude_dirs: Optional[Set[str]] = None,
    ) -> PruneResult:
        """Prune test files that are fully flagged by safe detectors.

        Safety guards:
        - dry_run=True by default (no files deleted unless explicitly requested)
        - Security tests excluded by default (tests/security/)
        - Only safe categories pruned (dead_import, archived_ref, zero_assertion)
        - Only files where ALL test functions are flagged are deleted (whole-file-only)
        - Respects tier protection (T0/T1 files are never deleted)

        Args:
            dry_run: If True, return candidates without deleting. Defaults to True.
            categories: Set of category values to consider for pruning.
                Defaults to SAFE_PRUNE_CATEGORIES.
            exclude_dirs: Set of directory prefixes to exclude.
                Defaults to DEFAULT_EXCLUDE_DIRS.

        Returns:
            PruneResult with lists of deleted, skipped, and error messages.
        """
        if categories is None:
            categories = self.SAFE_PRUNE_CATEGORIES
        if exclude_dirs is None:
            exclude_dirs = self.DEFAULT_EXCLUDE_DIRS

        report = self.analyze()
        result = PruneResult(dry_run=dry_run)

        if not report.findings:
            return result

        # Filter findings to only safe categories with prunable=True
        eligible_findings: List[PruningFinding] = [
            f for f in report.findings
            if f.category.value in categories and f.prunable
        ]

        if not eligible_findings:
            return result

        # Group eligible findings by file path
        findings_by_file: Dict[str, List[PruningFinding]] = {}
        for finding in eligible_findings:
            findings_by_file.setdefault(finding.file_path, []).append(finding)

        # For whole-file-only deletion, we need to know ALL test functions per file.
        # Count test functions per file from the AST.
        test_files = self._discover_test_files()
        test_count_by_rel_path: Dict[str, int] = {}
        for tf in test_files:
            rel = self._relative_path(tf)
            tree = self._parse_file(tf)
            if tree is None:
                continue
            count = 0
            for node in ast.walk(tree):
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    if node.name.startswith("test_"):
                        count += 1
            test_count_by_rel_path[rel] = count

        # Map relative paths back to absolute paths
        abs_path_map: Dict[str, Path] = {}
        for tf in test_files:
            abs_path_map[self._relative_path(tf)] = tf

        for rel_path, findings in findings_by_file.items():
            abs_path = abs_path_map.get(rel_path)
            if abs_path is None:
                # Try to resolve from project root
                abs_path = self.project_root / rel_path
                if not abs_path.exists():
                    continue

            # Check exclude_dirs
            if any(rel_path.startswith(ed) for ed in exclude_dirs):
                result.skipped_files.append(
                    (abs_path, f"Excluded directory: matches {[ed for ed in exclude_dirs if rel_path.startswith(ed)][0]}")
                )
                continue

            # Whole-file-only: only delete if ALL test functions in the file are flagged
            total_tests = test_count_by_rel_path.get(rel_path, 0)
            flagged_count = len(findings)

            if total_tests > 0 and flagged_count < total_tests:
                result.skipped_files.append(
                    (abs_path, f"Partially flagged: {flagged_count}/{total_tests} test functions")
                )
                continue

            # Prune (or report as candidate)
            if dry_run:
                result.deleted_files.append(abs_path)
            else:
                try:
                    abs_path.unlink()
                    result.deleted_files.append(abs_path)
                except OSError as e:
                    result.error_messages.append(
                        f"Failed to delete {rel_path}: {e}"
                    )

        return result

    def _discover_test_files(self) -> List[Path]:
        """Find all test files under the project root.

        Searches for test_*.py and *_test.py files, excluding
        directories in SKIP_DIRS.

        Returns:
            Sorted list of test file paths.
        """
        test_files: List[Path] = []

        for pattern in ("test_*.py", "*_test.py"):
            for path in self.project_root.rglob(pattern):
                # Validate path is within project root
                try:
                    path.relative_to(self.project_root)
                except ValueError:
                    continue

                # Skip excluded directories
                if any(skip in path.parts for skip in self.SKIP_DIRS):
                    continue

                if path.is_file():
                    test_files.append(path)

        # Deduplicate and sort
        return sorted(set(test_files))

    def _parse_file(self, path: Path) -> Optional[ast.Module]:
        """Parse a Python file into an AST, returning None on failure.

        Args:
            path: Path to the Python file.

        Returns:
            Parsed AST module or None if parsing fails.
        """
        try:
            source = path.read_text(encoding="utf-8")
            return ast.parse(source, filename=str(path))
        except (SyntaxError, UnicodeDecodeError, OSError) as e:
            logger.debug("Skipping unparseable file %s: %s", path, e)
            return None

    def _relative_path(self, path: Path) -> str:
        """Get path relative to project root as a string.

        Args:
            path: Absolute path to convert.

        Returns:
            Relative path string with forward slashes.
        """
        try:
            return str(path.relative_to(self.project_root))
        except ValueError:
            return str(path)

    def _is_prunable(self, path: Path) -> bool:
        """Check if a test file is prunable based on its tier.

        Args:
            path: Path to the test file.

        Returns:
            True if the file's tier allows pruning.
        """
        return is_prunable(self._relative_path(path))

    # ---------------------------------------------------------------
    # Detector 1: Dead Imports
    # ---------------------------------------------------------------

    def _detect_dead_imports(self, test_files: List[Path]) -> List[PruningFinding]:
        """Detect imports of modules/functions that no longer exist in source.

        Args:
            test_files: List of test file paths to analyze.

        Returns:
            List of findings for dead imports.
        """
        findings: List[PruningFinding] = []
        source_modules = self._collect_source_modules()

        for path in test_files:
            tree = self._parse_file(path)
            if tree is None:
                continue

            try:
                for node in ast.walk(tree):
                    if isinstance(node, ast.ImportFrom) and node.module:
                        module_name = node.module
                        # Only check project-local imports (not stdlib/third-party)
                        if not self._is_local_import(module_name):
                            continue

                        # Check if the module itself exists
                        if not self._module_exists(module_name, source_modules):
                            for alias in node.names:
                                findings.append(PruningFinding(
                                    file_path=self._relative_path(path),
                                    line=node.lineno,
                                    category=PruningCategory.DEAD_IMPORT,
                                    severity=Severity.HIGH,
                                    description=(
                                        f"Import from '{module_name}' - "
                                        f"module not found in source"
                                    ),
                                    suggestion="Remove test or update import",
                                    prunable=self._is_prunable(path),
                                ))
            except Exception as e:
                logger.debug("Dead import scan failed for %s: %s", path, e)

        return findings

    def _collect_source_modules(self) -> Set[str]:
        """Collect names of all Python modules in the project source.

        Returns:
            Set of dotted module names found in the project.
        """
        modules: Set[str] = set()
        lib_dir = self.project_root / "plugins" / "autonomous-dev" / "lib"
        src_dirs = [lib_dir]

        # Also check src/ if it exists
        src_dir = self.project_root / "src"
        if src_dir.is_dir():
            src_dirs.append(src_dir)

        for base_dir in src_dirs:
            if not base_dir.is_dir():
                continue
            for py_file in base_dir.rglob("*.py"):
                if ".worktrees" in py_file.parts:
                    continue
                if py_file.name == "__init__.py":
                    continue
                # Convert path to module name
                module_name = py_file.stem
                modules.add(module_name)

        return modules

    def _is_local_import(self, module_name: str) -> bool:
        """Check if an import is likely local to this project.

        Args:
            module_name: Dotted module path.

        Returns:
            True if the import appears to be project-local.
        """
        # Check common local module patterns
        first_part = module_name.split(".")[0]
        local_prefixes = {
            "plugins", "tier_registry", "sweep_analyzer", "test_pruning_analyzer",
            "pipeline_state", "tech_debt_detector", "hybrid_validator",
        }

        # If it starts with a known local prefix, it's local
        if first_part in local_prefixes:
            return True

        # If we can find the module in source, it's local
        source_modules = self._collect_source_modules()
        base_name = module_name.split(".")[-1]
        if base_name in source_modules:
            return True

        return False

    def _module_exists(self, module_name: str, source_modules: Set[str]) -> bool:
        """Check if a module exists either in source or as an importable package.

        Args:
            module_name: Dotted module name.
            source_modules: Set of known source module names.

        Returns:
            True if the module can be found.
        """
        # Check in our collected source modules
        base_name = module_name.split(".")[-1]
        if base_name in source_modules:
            return True

        # Check full dotted path components
        parts = module_name.split(".")
        for i in range(len(parts)):
            partial = ".".join(parts[: i + 1])
            if partial in source_modules:
                return True

        # Try importlib as last resort (for installed packages)
        try:
            spec = importlib.util.find_spec(module_name)
            return spec is not None
        except (ModuleNotFoundError, ValueError):
            return False

    # ---------------------------------------------------------------
    # Detector 2: Archived References
    # ---------------------------------------------------------------

    def _detect_archived_references(self, test_files: List[Path]) -> List[PruningFinding]:
        """Detect imports that reference archived modules or directories.

        Args:
            test_files: List of test file paths to analyze.

        Returns:
            List of findings for archived references.
        """
        findings: List[PruningFinding] = []
        archive_patterns = {"archived", "archive"}

        for path in test_files:
            tree = self._parse_file(path)
            if tree is None:
                continue

            try:
                for node in ast.walk(tree):
                    if isinstance(node, ast.ImportFrom) and node.module:
                        module_parts = node.module.split(".")
                        for part in module_parts:
                            if part.lower() in archive_patterns:
                                findings.append(PruningFinding(
                                    file_path=self._relative_path(path),
                                    line=node.lineno,
                                    category=PruningCategory.ARCHIVED_REF,
                                    severity=Severity.MEDIUM,
                                    description=(
                                        f"Import from archived module: "
                                        f"'{node.module}'"
                                    ),
                                    suggestion="Remove test for archived code",
                                    prunable=self._is_prunable(path),
                                ))
                                break
                    elif isinstance(node, ast.Import):
                        for alias in node.names:
                            module_parts = alias.name.split(".")
                            for part in module_parts:
                                if part.lower() in archive_patterns:
                                    findings.append(PruningFinding(
                                        file_path=self._relative_path(path),
                                        line=node.lineno,
                                        category=PruningCategory.ARCHIVED_REF,
                                        severity=Severity.MEDIUM,
                                        description=(
                                            f"Import from archived module: "
                                            f"'{alias.name}'"
                                        ),
                                        suggestion="Remove test for archived code",
                                        prunable=self._is_prunable(path),
                                    ))
                                    break
            except Exception as e:
                logger.debug("Archived ref scan failed for %s: %s", path, e)

        return findings

    # ---------------------------------------------------------------
    # Detector 3: Zero-Assertion Tests
    # ---------------------------------------------------------------

    def _detect_zero_assertion_tests(self, test_files: List[Path]) -> List[PruningFinding]:
        """Detect test functions that have no meaningful assertions.

        Flags tests with:
        - No assert statements, pytest.raises, or mock.assert_* calls
        - Only `pass` in the body
        - Only `assert True` or `assert None` placeholders

        Args:
            test_files: List of test file paths to analyze.

        Returns:
            List of findings for zero-assertion tests.
        """
        findings: List[PruningFinding] = []

        for path in test_files:
            tree = self._parse_file(path)
            if tree is None:
                continue

            try:
                for node in ast.walk(tree):
                    if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                        continue
                    if not node.name.startswith("test_"):
                        continue

                    finding = self._check_test_assertions(node, path)
                    if finding is not None:
                        findings.append(finding)
            except Exception as e:
                # DECISION (2026-08-25): this stays at DEBUG for this change.
                # KNOWN GAP, stated rather than hidden: a scan that silently
                # abandons a file mid-walk still reports success to its caller.
                # That is exactly how the ``ast.NameConstant`` crash below hid
                # for months (1,016 of 1,023 files abandoned, zero visible
                # signal). Raising the level or returning a partial-scan flag
                # is a separate, wider change to the report contract; it was
                # not bundled here. Until then, treat a zero-finding scan as an
                # upper bound, not a total.
                logger.debug("Zero-assertion scan failed for %s: %s", path, e)

        return findings

    def _check_test_assertions(
        self, node: ast.FunctionDef, path: Path
    ) -> Optional[PruningFinding]:
        """Check a single test function for meaningful assertions.

        Args:
            node: AST function definition node.
            path: Path to the file containing the function.

        Returns:
            PruningFinding if the test lacks assertions, else None.
        """
        body = node.body

        # Check for pass-only body (skip docstrings)
        non_docstring_body = [
            stmt for stmt in body
            if not (isinstance(stmt, ast.Expr) and isinstance(stmt.value, ast.Constant)
                    and isinstance(stmt.value.value, str))
        ]

        if len(non_docstring_body) == 0 or (
            len(non_docstring_body) == 1 and isinstance(non_docstring_body[0], ast.Pass)
        ):
            return PruningFinding(
                file_path=self._relative_path(path),
                line=node.lineno,
                category=PruningCategory.ZERO_ASSERTION,
                severity=Severity.HIGH,
                description=f"Test '{node.name}' has pass-only body",
                suggestion="Add assertions or remove test",
                prunable=self._is_prunable(path),
            )

        # Check for placeholder assertions (assert True, assert None)
        if self._has_only_placeholder_asserts(body):
            return PruningFinding(
                file_path=self._relative_path(path),
                line=node.lineno,
                category=PruningCategory.ZERO_ASSERTION,
                severity=Severity.MEDIUM,
                description=f"Test '{node.name}' has only placeholder assertions",
                suggestion="Replace placeholder with real assertions",
                prunable=self._is_prunable(path),
            )

        # Count real assertions
        assertion_count = self._count_assertions(body)
        if assertion_count == 0:
            return PruningFinding(
                file_path=self._relative_path(path),
                line=node.lineno,
                category=PruningCategory.ZERO_ASSERTION,
                severity=Severity.HIGH,
                description=f"Test '{node.name}' has no assertions",
                suggestion="Add assertions or remove test",
                prunable=self._is_prunable(path),
            )

        return None

    def _has_only_placeholder_asserts(self, body: List[ast.stmt]) -> bool:
        """Check if a function body contains only placeholder assertions.

        Placeholder assertions are: assert True, assert None, assert 1.

        Args:
            body: List of AST statement nodes.

        Returns:
            True if all assertions are placeholders.
        """
        has_assert = False
        for node in ast.walk(ast.Module(body=body, type_ignores=[])):
            if isinstance(node, ast.Assert):
                has_assert = True
                test = node.test
                # Check for assert True, assert None, assert 1
                if isinstance(test, ast.Constant):
                    if test.value not in (True, None, 1):
                        return False
                else:
                    return False  # Non-constant assert = real assertion

        return has_assert

    def _count_assertions(self, body: List[ast.stmt]) -> int:
        """Count meaningful assertions in a function body.

        Counts: assert statements, pytest.raises calls, mock.assert_* calls.

        Args:
            body: List of AST statement nodes.

        Returns:
            Number of assertions found.
        """
        count = 0
        wrapper = ast.Module(body=body, type_ignores=[])

        for node in ast.walk(wrapper):
            # Standard assert statements
            if isinstance(node, ast.Assert):
                count += 1
                continue

            # pytest.raises and similar context managers
            if isinstance(node, ast.With):
                for item in node.items:
                    if self._is_pytest_assertion(item.context_expr):
                        count += 1

            # mock.assert_called, mock.assert_called_once, etc.
            if isinstance(node, ast.Call):
                if self._is_mock_assertion(node):
                    count += 1

            # Attribute calls like .assert_called_with()
            if isinstance(node, ast.Expr) and isinstance(node.value, ast.Call):
                if self._is_mock_assertion(node.value):
                    count += 1

        return count

    def _is_pytest_assertion(self, node: ast.expr) -> bool:
        """Check if an expression is a pytest assertion (e.g., pytest.raises).

        Args:
            node: AST expression node.

        Returns:
            True if the node is a pytest assertion.
        """
        if isinstance(node, ast.Call):
            func = node.func
            if isinstance(func, ast.Attribute):
                if func.attr in ("raises", "warns", "deprecated_call"):
                    return True
        return False

    def _is_mock_assertion(self, node: ast.Call) -> bool:
        """Check if a call is a mock assertion (e.g., mock.assert_called_once).

        Args:
            node: AST Call node.

        Returns:
            True if the node is a mock assertion call.
        """
        func = node.func
        if isinstance(func, ast.Attribute):
            attr_name = func.attr
            if attr_name.startswith("assert_") and any(
                kw in attr_name for kw in ("called", "any_call", "has_calls")
            ):
                return True
        return False

    # ---------------------------------------------------------------
    # Detector 4: Duplicate Coverage
    # ---------------------------------------------------------------

    def _detect_duplicate_coverage(self, test_files: List[Path]) -> List[PruningFinding]:
        """Detect tests that cover the same function with the same arguments.

        For each test file, collects (function_name, normalized_args) tuples
        and flags duplicates.

        Args:
            test_files: List of test file paths to analyze.

        Returns:
            List of findings for duplicate test coverage.
        """
        findings: List[PruningFinding] = []

        for path in test_files:
            tree = self._parse_file(path)
            if tree is None:
                continue

            try:
                # Collect all tested function signatures per test function
                test_sigs: Dict[str, Tuple[int, set]] = {}

                for node in ast.walk(tree):
                    if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                        continue
                    if not node.name.startswith("test_"):
                        continue

                    sigs = set(self._extract_call_signatures(node))
                    if sigs:  # Only track tests with actual call signatures
                        test_sigs[node.name] = (node.lineno, sigs)

                # Flag tests whose entire signature set is a subset of another test
                for test_name, (lineno, sigs) in test_sigs.items():
                    if not sigs:
                        continue
                    for other_name, (other_lineno, other_sigs) in test_sigs.items():
                        if other_name == test_name:
                            continue
                        # Subset or equal — flag the later test (by line number)
                        if sigs <= other_sigs and lineno > other_lineno:
                            findings.append(PruningFinding(
                                file_path=self._relative_path(path),
                                line=lineno,
                                category=PruningCategory.DUPLICATE_COVERAGE,
                                severity=Severity.LOW,
                                description=(
                                    f"Test '{test_name}' coverage is a subset "
                                    f"of '{other_name}' ({len(sigs)} of "
                                    f"{len(other_sigs)} signatures)"
                                ),
                                suggestion="Consolidate or differentiate test cases",
                                prunable=self._is_prunable(path),
                            ))
                            break  # Only flag once per test
            except Exception as e:
                logger.debug("Duplicate coverage scan failed for %s: %s", path, e)

        return findings

    def _extract_call_signatures(self, node: ast.FunctionDef) -> List[str]:
        """Extract function call signatures from a test function body.

        Args:
            node: AST function definition node.

        Returns:
            List of normalized call signature strings.
        """
        signatures: List[str] = []

        for child in ast.walk(node):
            if not isinstance(child, ast.Call):
                continue

            func_name = self._get_call_name(child)
            if func_name is None:
                continue

            # Skip common non-target calls
            if func_name in (
                "print", "len", "str", "int", "float", "list", "dict",
                "set", "tuple", "isinstance", "type", "range", "enumerate",
                "sorted", "reversed", "zip", "map", "filter",
                # Test framework utilities — not coverage targets
                "assert_called", "assert_called_once", "assert_called_with",
                "assert_called_once_with", "assert_not_called", "assert_has_calls",
                "assertEqual", "assertRaises", "assertTrue", "assertFalse",
                "assertIn", "assertNotIn", "assertIsNone", "assertIsNotNone",
                "patch", "Mock", "MagicMock", "PropertyMock",
                "fixture", "mark", "raises", "warns", "skip", "parametrize",
                "append", "extend", "update", "copy", "deepcopy",
                "join", "format", "replace", "strip", "split",
                "keys", "values", "items", "get", "pop",
                "open", "close", "read", "write", "exists", "mkdir",
                "Path", "dumps", "loads",
            ):
                continue

            # Normalize arguments to a string
            args_str = self._normalize_args(child)
            signatures.append(f"{func_name}({args_str})")

        return signatures

    def _get_call_name(self, node: ast.Call) -> Optional[str]:
        """Get the name of a function call from its AST node.

        Args:
            node: AST Call node.

        Returns:
            Function name string or None.
        """
        func = node.func
        if isinstance(func, ast.Name):
            return func.id
        elif isinstance(func, ast.Attribute):
            return func.attr
        return None

    def _normalize_args(self, node: ast.Call) -> str:
        """Normalize call arguments to a string for comparison.

        Args:
            node: AST Call node.

        Returns:
            Normalized argument string.
        """
        parts: List[str] = []

        for arg in node.args:
            parts.append(ast.dump(arg))

        for kw in node.keywords:
            parts.append(f"{kw.arg}={ast.dump(kw.value)}")

        return ", ".join(parts)

    # ---------------------------------------------------------------
    # Detector 5: Stale Regressions
    # ---------------------------------------------------------------

    def _detect_stale_regressions(self, test_files: List[Path]) -> List[PruningFinding]:
        """Detect regression tests referencing specific issues (TestIssueNNN).

        Finds patterns like TestIssue123 or test_issue_123 that may reference
        fixed bugs whose tests could be stale.

        Args:
            test_files: List of test file paths to analyze.

        Returns:
            List of findings for stale regression tests.
        """
        findings: List[PruningFinding] = []
        issue_pattern = re.compile(r"(?:TestIssue|test_issue_)(\d+)", re.IGNORECASE)

        for path in test_files:
            tree = self._parse_file(path)
            if tree is None:
                continue

            try:
                source = path.read_text(encoding="utf-8")
                for match in issue_pattern.finditer(source):
                    issue_num = match.group(1)
                    # Find the line number
                    line_num = source[: match.start()].count("\n") + 1

                    findings.append(PruningFinding(
                        file_path=self._relative_path(path),
                        line=line_num,
                        category=PruningCategory.STALE_REGRESSION,
                        severity=Severity.LOW,
                        description=(
                            f"Regression test references issue #{issue_num} "
                            f"- verify issue is still relevant"
                        ),
                        suggestion="Check if the referenced issue fix is still needed",
                        prunable=self._is_prunable(path),
                    ))
            except (OSError, UnicodeDecodeError) as e:
                logger.debug("Stale regression scan failed for %s: %s", path, e)

        return findings


@dataclass(frozen=True)
class VacuousTestFinding:
    """A test function whose assertions can never fail.

    Attributes:
        name: The test function's name.
        line: 1-based line number of the ``def``.
        reason: Short, human-readable explanation of why it is vacuous.
    """

    name: str
    line: int
    reason: str


def find_vacuous_tests(source: str, filename: str = "<string>") -> List[VacuousTestFinding]:
    """Find ``test_*`` functions whose assertions are all placeholders.

    A placeholder assertion is ``assert True``, ``assert None`` or ``assert 1``
    — a constant that can never fail. Detection REUSES
    ``TestPruningAnalyzer._has_only_placeholder_asserts`` rather than
    reimplementing it; a second copy of the rule inside a reader is the defect,
    not the fix.

    DIVERGENCE (do not reconcile): this flags ``assert True, "message"``
    because ``_has_only_placeholder_asserts`` reads ``node.test`` and never
    ``node.msg``, whereas ``tests/regression/smoke/test_tautological_assertions.py``
    lines 52-54 DELIBERATELY exempt that shape — the two mechanisms disagree on
    purpose and their allowlists must never be merged.

    INV-1 ASYMMETRY (known gap, not a coverage claim): this detector SHIPS
    (``install_manifest.json`` line 371) but the ratchet built on it lives in
    ``tests/`` and does not, since the manifest holds zero ``tests/`` paths
    (measured 2026-08-25) — consumers get the detector without the gate.

    KNOWN LIMIT (#1667 shape 2, NOT closed): a self-referential literal built
    and consumed in one body — ``checklist = ["/sync-dev", ...]`` then
    ``assert "/sync-dev" in checklist`` — is invisible here, because the
    assertion count exceeds zero and the assertion is not a constant, yet it is
    unfalsifiable.

    KNOWN GAP (#1147, deliberately not mechanized): the parametrize
    self-membership rule stays PROSE-only at ``agents/spec-validator.md`` lines
    95-113 on measured grounds — zero instances of ``assert x == x`` in the
    live corpus (the only 2 in the tree are under ``tests/archived/``), and
    none of its 356 parametrize call sites confirmed to be that shape.

    Args:
        source: Python source text to scan.
        filename: Name used for AST error reporting only; never read from disk.

    Returns:
        One ``VacuousTestFinding`` per vacuous ``test_*`` function, in AST walk
        order. Returns an empty list when ``source`` does not parse.
    """
    try:
        tree = ast.parse(source, filename=filename)
    except SyntaxError:
        # A file that does not parse is not evidence of zero vacuous tests.
        # The caller decides what to do about unparseable input; this function
        # refuses to guess.
        return []

    # ``_has_only_placeholder_asserts`` is an instance method that reads no
    # instance state, so a throwaway analyzer is enough to reach it. Reusing it
    # is the point: the rule has exactly one definition.
    analyzer = TestPruningAnalyzer(Path("."))

    findings: List[VacuousTestFinding] = []
    for node in ast.walk(tree):
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        if not node.name.startswith("test_"):
            continue
        if analyzer._has_only_placeholder_asserts(node.body):
            findings.append(
                VacuousTestFinding(
                    name=node.name,
                    line=node.lineno,
                    reason=(
                        "all assertions are constant placeholders "
                        "(assert True / assert None / assert 1) and can never fail"
                    ),
                )
            )

    return findings
