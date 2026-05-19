#!/usr/bin/env python3
"""Unit tests for refactor_analyzer module.

Tests the RefactorFinding, RefactorReport, and RefactorAnalyzer classes including
test shape analysis, test waste detection, doc redundancy, dead code detection,
unused lib detection, quick sweep delegation, and error handling.
"""

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# Ensure lib is importable
sys.path.insert(
    0,
    str(
        Path(__file__).parent.parent.parent.parent
        / "plugins"
        / "autonomous-dev"
        / "lib"
    ),
)

from refactor_analyzer import (
    ConfidenceLevel,
    OptimizationType,
    RefactorAnalyzer,
    RefactorCategory,
    RefactorFinding,
    RefactorReport,
)
from sweep_analyzer import SweepSeverity


# =============================================================================
# RefactorFinding Tests
# =============================================================================


class TestRefactorFinding:
    """Tests for RefactorFinding dataclass."""

    def test_creation_basic(self):
        """Test basic RefactorFinding creation."""
        finding = RefactorFinding(
            category=RefactorCategory.DEAD_CODE,
            severity=SweepSeverity.HIGH,
            file_path="src/foo.py",
            description="Unused function",
            suggestion="Remove it",
        )
        assert finding.file_path == "src/foo.py"
        assert finding.category == RefactorCategory.DEAD_CODE
        assert finding.severity == SweepSeverity.HIGH
        assert finding.optimization_type == OptimizationType.OPTIMIZATION
        assert finding.line is None
        assert finding.confidence == ConfidenceLevel.HIGH

    def test_creation_with_all_fields(self):
        """Test RefactorFinding creation with all fields."""
        finding = RefactorFinding(
            category=RefactorCategory.TEST_WASTE,
            severity=SweepSeverity.MEDIUM,
            file_path="tests/test_foo.py",
            description="Trivial test",
            suggestion="Add assertions",
            optimization_type=OptimizationType.HYGIENE,
            line=42,
        )
        assert finding.line == 42
        assert finding.optimization_type == OptimizationType.HYGIENE

    def test_format_without_line(self):
        """Test format() output without line number."""
        finding = RefactorFinding(
            category=RefactorCategory.DEAD_CODE,
            severity=SweepSeverity.HIGH,
            file_path="src/foo.py",
            description="Dead function",
            suggestion="Remove",
        )
        result = finding.format()
        assert result == "[HIGH] src/foo.py: Dead function"

    def test_format_with_line(self):
        """Test format() output with line number."""
        finding = RefactorFinding(
            category=RefactorCategory.DEAD_CODE,
            severity=SweepSeverity.CRITICAL,
            file_path="src/foo.py",
            description="Circular import",
            suggestion="Refactor",
            line=10,
        )
        result = finding.format()
        assert result == "[CRITICAL] src/foo.py:10: Circular import"

    def test_category_values(self):
        """Test RefactorCategory enum values."""
        assert RefactorCategory.TEST_SHAPE.value == "test_shape"
        assert RefactorCategory.TEST_WASTE.value == "test_waste"
        assert RefactorCategory.DOC_REDUNDANCY.value == "doc_redundancy"
        assert RefactorCategory.DEAD_CODE.value == "dead_code"
        assert RefactorCategory.UNUSED_LIB.value == "unused_lib"
        assert RefactorCategory.COMPLEXITY.value == "complexity"
        assert RefactorCategory.HYGIENE.value == "hygiene"

    def test_optimization_type_values(self):
        """Test OptimizationType enum values."""
        assert OptimizationType.HYGIENE.value == "hygiene"
        assert OptimizationType.OPTIMIZATION.value == "optimization"


# =============================================================================
# RefactorReport Tests
# =============================================================================


class TestRefactorReport:
    """Tests for RefactorReport dataclass."""

    def test_empty_report(self):
        """Test empty report properties."""
        report = RefactorReport()
        assert not report.has_findings
        assert report.summary == {}
        assert report.scan_duration_ms == 0
        assert report.modes_run == []
        assert report.test_shape is None

    def test_has_findings(self):
        """Test has_findings property with findings present."""
        report = RefactorReport(
            findings=[
                RefactorFinding(
                    category=RefactorCategory.DEAD_CODE,
                    severity=SweepSeverity.LOW,
                    file_path="x.py",
                    description="test",
                    suggestion="fix",
                )
            ]
        )
        assert report.has_findings

    def test_summary_counts(self):
        """Test summary counts findings by category."""
        report = RefactorReport(
            findings=[
                RefactorFinding(
                    RefactorCategory.TEST_SHAPE, SweepSeverity.HIGH, "a.py", "d1", "s1"
                ),
                RefactorFinding(
                    RefactorCategory.TEST_SHAPE, SweepSeverity.LOW, "b.py", "d2", "s2"
                ),
                RefactorFinding(
                    RefactorCategory.DEAD_CODE, SweepSeverity.MEDIUM, "c.py", "d3", "s3"
                ),
            ]
        )
        assert report.summary == {"test_shape": 2, "dead_code": 1}

    def test_format_report_empty(self):
        """Test format_report with no findings."""
        report = RefactorReport()
        assert "Clean refactor analysis" in report.format_report()

    def test_format_report_with_findings(self):
        """Test format_report with findings groups by category."""
        report = RefactorReport(
            findings=[
                RefactorFinding(
                    RefactorCategory.TEST_WASTE,
                    SweepSeverity.HIGH,
                    "a.py",
                    "trivial",
                    "fix1",
                ),
                RefactorFinding(
                    RefactorCategory.DEAD_CODE,
                    SweepSeverity.LOW,
                    "b.py",
                    "dead",
                    "remove",
                ),
                RefactorFinding(
                    RefactorCategory.TEST_WASTE,
                    SweepSeverity.CRITICAL,
                    "c.py",
                    "duplicate",
                    "fix2",
                ),
            ],
            scan_duration_ms=150,
            modes_run=["tests", "code"],
        )
        output = report.format_report()
        assert "3 findings" in output
        assert "150ms" in output
        assert "TEST_WASTE (2 issues)" in output
        assert "DEAD_CODE (1 issues)" in output
        # CRITICAL should appear before HIGH
        waste_start = output.index("TEST_WASTE")
        critical_pos = output.index("CRITICAL", waste_start)
        high_pos = output.index("HIGH", waste_start)
        assert critical_pos < high_pos

    def test_format_report_includes_suggestion(self):
        """Test that format_report includes suggestions."""
        report = RefactorReport(
            findings=[
                RefactorFinding(
                    RefactorCategory.DOC_REDUNDANCY,
                    SweepSeverity.MEDIUM,
                    "a.md",
                    "redundant",
                    "merge docs",
                ),
            ],
            modes_run=["docs"],
        )
        output = report.format_report()
        assert "Suggestion: merge docs" in output

    def test_format_report_with_test_shape(self):
        """Test format_report includes test shape table when available."""
        report = RefactorReport(
            findings=[
                RefactorFinding(
                    RefactorCategory.TEST_SHAPE,
                    SweepSeverity.MEDIUM,
                    "tests/",
                    "imbalance",
                    "fix it",
                ),
            ],
            test_shape={"unit": 50, "integration": 10, "property": 0, "genai": 2},
            modes_run=["tests"],
        )
        output = report.format_report()
        assert "Test Shape Distribution" in output
        assert "unit" in output
        assert "integration" in output

    def test_to_dict(self):
        """Test to_dict serialization."""
        report = RefactorReport(
            findings=[
                RefactorFinding(
                    RefactorCategory.TEST_WASTE,
                    SweepSeverity.HIGH,
                    "a.py",
                    "trivial",
                    "fix",
                    OptimizationType.HYGIENE,
                    line=5,
                ),
            ],
            scan_duration_ms=100,
            modes_run=["tests"],
            test_shape={"unit": 10, "integration": 5, "property": 0, "genai": 1},
        )
        d = report.to_dict()
        assert d["duration_ms"] == 100
        assert d["modes_run"] == ["tests"]
        assert len(d["findings"]) == 1
        assert d["findings"][0]["file"] == "a.py"
        assert d["findings"][0]["line"] == 5
        assert d["findings"][0]["category"] == "test_waste"
        assert d["findings"][0]["severity"] == "high"
        assert d["findings"][0]["optimization_type"] == "hygiene"
        assert d["summary"] == {"test_waste": 1}
        assert d["test_shape"]["unit"] == 10


# =============================================================================
# RefactorAnalyzer Test Shape Tests
# =============================================================================


class TestRefactorAnalyzerTestShape:
    """Tests for RefactorAnalyzer test shape analysis."""

    def test_classifies_unit_tests(self, tmp_path):
        """Test that tests in tests/unit/ are classified as unit."""
        test_dir = tmp_path / "tests" / "unit"
        test_dir.mkdir(parents=True)
        test_file = test_dir / "test_basic.py"
        test_file.write_text("def test_add():\n    assert 1 + 1 == 2\n")

        analyzer = RefactorAnalyzer(tmp_path)
        findings, shape = analyzer._analyze_test_shape()
        assert shape["unit"] >= 1

    def test_classifies_genai_tests(self, tmp_path):
        """Test that tests in tests/genai/ are classified as genai."""
        test_dir = tmp_path / "tests" / "genai"
        test_dir.mkdir(parents=True)
        test_file = test_dir / "test_llm.py"
        test_file.write_text("def test_judge():\n    pass\n")

        analyzer = RefactorAnalyzer(tmp_path)
        findings, shape = analyzer._analyze_test_shape()
        assert shape["genai"] >= 1

    def test_classifies_integration_tests(self, tmp_path):
        """Test that tests in tests/integration/ are classified as integration."""
        test_dir = tmp_path / "tests" / "integration"
        test_dir.mkdir(parents=True)
        test_file = test_dir / "test_workflow.py"
        test_file.write_text("def test_pipeline():\n    pass\n")

        analyzer = RefactorAnalyzer(tmp_path)
        findings, shape = analyzer._analyze_test_shape()
        assert shape["integration"] >= 1

    def test_detects_shape_imbalance(self, tmp_path):
        """Test that significant deviation from Quality Diamond targets is detected."""
        # Create only unit tests (100% unit, 0% everything else)
        test_dir = tmp_path / "tests" / "unit"
        test_dir.mkdir(parents=True)
        for i in range(10):
            (test_dir / f"test_{i}.py").write_text(f"def test_{i}():\n    assert True\n")

        analyzer = RefactorAnalyzer(tmp_path)
        findings, shape = analyzer._analyze_test_shape()
        # Should detect that unit is over-represented and others under-represented
        assert len(findings) > 0
        shape_findings = [
            f for f in findings if f.category == RefactorCategory.TEST_SHAPE
        ]
        assert len(shape_findings) > 0

    def test_no_findings_when_no_tests(self, tmp_path):
        """Test graceful handling when no test files exist."""
        analyzer = RefactorAnalyzer(tmp_path)
        findings, shape = analyzer._analyze_test_shape()
        assert findings == []
        assert sum(shape.values()) == 0


# =============================================================================
# RefactorAnalyzer Test Waste Tests
# =============================================================================


class TestRefactorAnalyzerTestWaste:
    """Tests for RefactorAnalyzer test waste detection."""

    def test_detects_trivial_test_pass(self, tmp_path):
        """Test detection of trivial test with only pass."""
        test_dir = tmp_path / "tests"
        test_dir.mkdir()
        test_file = test_dir / "test_trivial.py"
        test_file.write_text('def test_placeholder():\n    pass\n')

        analyzer = RefactorAnalyzer(tmp_path)
        findings = analyzer._detect_test_waste()
        trivial = [f for f in findings if "Trivial test" in f.description]
        assert len(trivial) >= 1

    def test_detects_trivial_test_assert_true(self, tmp_path):
        """Test detection of trivial test with assert True."""
        test_dir = tmp_path / "tests"
        test_dir.mkdir()
        test_file = test_dir / "test_trivial.py"
        test_file.write_text("def test_nothing():\n    assert True\n")

        analyzer = RefactorAnalyzer(tmp_path)
        findings = analyzer._detect_test_waste()
        trivial = [f for f in findings if "Trivial test" in f.description]
        assert len(trivial) >= 1

    def test_detects_duplicate_bodies(self, tmp_path):
        """Test detection of tests with identical bodies."""
        test_dir = tmp_path / "tests"
        test_dir.mkdir()
        test_file = test_dir / "test_dup.py"
        test_file.write_text(
            "def test_alpha():\n    x = 1\n    assert x == 1\n\n"
            "def test_beta():\n    x = 1\n    assert x == 1\n"
        )

        analyzer = RefactorAnalyzer(tmp_path)
        findings = analyzer._detect_test_waste()
        dup = [f for f in findings if "Duplicate test body" in f.description]
        assert len(dup) >= 1

    def test_does_not_flag_normal_tests(self, tmp_path):
        """Test that meaningful tests are not flagged as waste."""
        test_dir = tmp_path / "tests"
        test_dir.mkdir()
        test_file = test_dir / "test_real.py"
        test_file.write_text(
            "def test_addition():\n    result = 1 + 2\n    assert result == 3\n\n"
            "def test_subtraction():\n    result = 5 - 2\n    assert result == 3\n"
        )

        analyzer = RefactorAnalyzer(tmp_path)
        findings = analyzer._detect_test_waste()
        trivial = [f for f in findings if "Trivial test" in f.description]
        assert len(trivial) == 0


# =============================================================================
# RefactorAnalyzer Doc Redundancy Tests
# =============================================================================


class TestRefactorAnalyzerDocRedundancy:
    """Tests for RefactorAnalyzer doc redundancy detection."""

    def test_detects_highly_similar_docs(self, tmp_path):
        """Test detection of .md files with >85% similarity."""
        doc_a = tmp_path / "README.md"
        doc_b = tmp_path / "GUIDE.md"
        content = "# My Guide\n\n" + "This is detailed content. " * 50
        doc_a.write_text(content)
        doc_b.write_text(content)  # Identical content

        analyzer = RefactorAnalyzer(tmp_path)
        findings = analyzer._detect_doc_redundancy()
        assert len(findings) >= 1
        assert findings[0].category == RefactorCategory.DOC_REDUNDANCY

    def test_ignores_different_docs(self, tmp_path):
        """Test that dissimilar docs are not flagged."""
        doc_a = tmp_path / "README.md"
        doc_b = tmp_path / "CONTRIBUTING.md"
        doc_a.write_text("# Project\n\nThis is about the project setup.\n" * 10)
        doc_b.write_text("# Contributing\n\nHow to contribute code.\n" * 10)

        analyzer = RefactorAnalyzer(tmp_path)
        findings = analyzer._detect_doc_redundancy()
        assert len(findings) == 0

    def test_skips_excluded_dirs(self, tmp_path):
        """Test that .git/ docs are excluded."""
        git_dir = tmp_path / ".git" / "docs"
        git_dir.mkdir(parents=True)
        (git_dir / "internal.md").write_text("internal stuff")
        (tmp_path / "README.md").write_text("internal stuff")

        analyzer = RefactorAnalyzer(tmp_path)
        findings = analyzer._detect_doc_redundancy()
        # .git should be excluded, so no comparison
        assert len(findings) == 0


# =============================================================================
# RefactorAnalyzer Dead Code Tests
# =============================================================================


class TestRefactorAnalyzerDeadCode:
    """Tests for RefactorAnalyzer dead code detection."""

    def test_detects_unreferenced_function(self, tmp_path):
        """Test detection of functions never referenced in any file."""
        lib_dir = tmp_path / "plugins" / "autonomous-dev" / "lib"
        lib_dir.mkdir(parents=True)
        lib_file = lib_dir / "utils.py"
        lib_file.write_text(
            "def used_function():\n    return 1\n\n"
            "def never_called_anywhere_xyz():\n    return 2\n"
        )

        # Create a file that uses one function but not the other
        cmd_dir = tmp_path / "plugins" / "autonomous-dev" / "commands"
        cmd_dir.mkdir(parents=True)
        cmd_file = cmd_dir / "runner.py"
        cmd_file.write_text("from utils import used_function\nused_function()\n")

        analyzer = RefactorAnalyzer(tmp_path)
        findings = analyzer._detect_dead_code_cross_file()
        dead = [f for f in findings if "never_called_anywhere_xyz" in f.description]
        assert len(dead) == 1
        assert dead[0].category == RefactorCategory.DEAD_CODE

    def test_ignores_private_functions(self, tmp_path):
        """Test that private functions (starting with _) are not flagged."""
        lib_dir = tmp_path / "plugins" / "autonomous-dev" / "lib"
        lib_dir.mkdir(parents=True)
        lib_file = lib_dir / "utils.py"
        lib_file.write_text("def _private_helper():\n    return 1\n")

        analyzer = RefactorAnalyzer(tmp_path)
        findings = analyzer._detect_dead_code_cross_file()
        private = [f for f in findings if "_private_helper" in f.description]
        assert len(private) == 0

    def test_ignores_decorated_functions(self, tmp_path):
        """Test that functions with whitelisted decorators are not flagged."""
        lib_dir = tmp_path / "plugins" / "autonomous-dev" / "lib"
        lib_dir.mkdir(parents=True)
        lib_file = lib_dir / "utils.py"
        lib_file.write_text(
            "from dataclasses import dataclass\n\n"
            "@dataclass\n"
            "class MyConfig:\n    name: str = 'test'\n"
        )

        analyzer = RefactorAnalyzer(tmp_path)
        findings = analyzer._detect_dead_code_cross_file()
        config = [f for f in findings if "MyConfig" in f.description]
        assert len(config) == 0


# =============================================================================
# RefactorAnalyzer Unused Libs Tests
# =============================================================================


class TestRefactorAnalyzerUnusedLibs:
    """Tests for RefactorAnalyzer unused lib detection."""

    def test_detects_unused_lib_module(self, tmp_path):
        """Test detection of lib modules never imported outside tests."""
        lib_dir = tmp_path / "plugins" / "autonomous-dev" / "lib"
        lib_dir.mkdir(parents=True)
        (lib_dir / "used_lib.py").write_text("def helper(): pass\n")
        (lib_dir / "unused_lib_xyz.py").write_text("def dead(): pass\n")

        # Create a non-test file that uses one lib
        cmd_dir = tmp_path / "plugins" / "autonomous-dev" / "commands"
        cmd_dir.mkdir(parents=True)
        (cmd_dir / "main.py").write_text("import used_lib\nused_lib.helper()\n")

        analyzer = RefactorAnalyzer(tmp_path)
        findings = analyzer._detect_unused_libs()
        unused = [f for f in findings if "unused_lib_xyz" in f.description]
        assert len(unused) == 1
        assert unused[0].category == RefactorCategory.UNUSED_LIB

    def test_does_not_flag_referenced_libs(self, tmp_path):
        """Test that libs referenced outside tests are not flagged."""
        lib_dir = tmp_path / "plugins" / "autonomous-dev" / "lib"
        lib_dir.mkdir(parents=True)
        (lib_dir / "active_lib.py").write_text("def run(): pass\n")

        cmd_dir = tmp_path / "plugins" / "autonomous-dev" / "commands"
        cmd_dir.mkdir(parents=True)
        (cmd_dir / "cmd.py").write_text("from active_lib import run\nrun()\n")

        analyzer = RefactorAnalyzer(tmp_path)
        findings = analyzer._detect_unused_libs()
        active = [f for f in findings if "active_lib" in f.description]
        assert len(active) == 0

    def test_handles_no_lib_dir(self, tmp_path):
        """Test graceful handling when no lib directory exists."""
        analyzer = RefactorAnalyzer(tmp_path)
        findings = analyzer._detect_unused_libs()
        assert findings == []


# =============================================================================
# Quick Sweep Delegation Tests
# =============================================================================


class TestRefactorAnalyzerQuickSweep:
    """Tests for RefactorAnalyzer.quick_sweep() delegation to SweepAnalyzer."""

    def test_delegates_to_sweep_analyzer(self, tmp_path):
        """Test that quick_sweep delegates to SweepAnalyzer.full_sweep."""
        from sweep_analyzer import SweepCategory, SweepFinding, SweepReport

        mock_sweep_report = SweepReport(
            findings=[
                SweepFinding(
                    "a.py", SweepCategory.TEST, SweepSeverity.HIGH, "fail", "fix"
                ),
            ],
            scan_duration_ms=50,
            modes_run=["tests", "docs", "code"],
        )

        analyzer = RefactorAnalyzer(tmp_path)
        analyzer._sweep_analyzer = MagicMock()
        analyzer._sweep_analyzer.full_sweep.return_value = mock_sweep_report

        report = analyzer.quick_sweep()

        analyzer._sweep_analyzer.full_sweep.assert_called_once()
        assert len(report.findings) == 1
        assert report.findings[0].category == RefactorCategory.HYGIENE
        assert report.findings[0].severity == SweepSeverity.HIGH
        assert report.findings[0].optimization_type == OptimizationType.HYGIENE
        assert "quick" in report.modes_run

    def test_quick_sweep_handles_exception(self, tmp_path):
        """Test that quick_sweep handles SweepAnalyzer exceptions gracefully."""
        analyzer = RefactorAnalyzer(tmp_path)
        analyzer._sweep_analyzer = MagicMock()
        analyzer._sweep_analyzer.full_sweep.side_effect = RuntimeError("boom")

        report = analyzer.quick_sweep()
        assert report.findings == []
        assert "quick" in report.modes_run


# =============================================================================
# Full Analysis Tests
# =============================================================================


class TestRefactorAnalyzerFullAnalysis:
    """Tests for RefactorAnalyzer.full_analysis()."""

    def test_runs_all_modes_by_default(self, tmp_path):
        """Test that full_analysis runs all modes when none specified."""
        analyzer = RefactorAnalyzer(tmp_path)
        analyzer.analyze_tests = MagicMock(return_value=[])
        # "docs" now routes to analyze_doc_drift (Issue #1098)
        analyzer.analyze_doc_drift = MagicMock(return_value=[])
        analyzer.analyze_code = MagicMock(return_value=[])

        report = analyzer.full_analysis()

        analyzer.analyze_tests.assert_called_once()
        analyzer.analyze_doc_drift.assert_called_once()
        analyzer.analyze_code.assert_called_once()
        assert report.modes_run == ["tests", "docs", "code"]

    def test_runs_specific_modes(self, tmp_path):
        """Test that full_analysis runs only specified modes."""
        analyzer = RefactorAnalyzer(tmp_path)
        analyzer.analyze_tests = MagicMock(
            return_value=[
                RefactorFinding(
                    RefactorCategory.TEST_WASTE,
                    SweepSeverity.LOW,
                    "t.py",
                    "d",
                    "s",
                )
            ]
        )
        analyzer.analyze_docs = MagicMock(return_value=[])
        analyzer.analyze_code = MagicMock(return_value=[])

        report = analyzer.full_analysis(["tests"])

        analyzer.analyze_tests.assert_called_once()
        analyzer.analyze_docs.assert_not_called()
        analyzer.analyze_code.assert_not_called()
        assert report.modes_run == ["tests"]
        assert len(report.findings) == 1

    def test_aggregates_findings(self, tmp_path):
        """Test that full_analysis aggregates findings from all modes."""
        analyzer = RefactorAnalyzer(tmp_path)
        tf = RefactorFinding(
            RefactorCategory.TEST_SHAPE, SweepSeverity.HIGH, "t.py", "tf", "s"
        )
        df = RefactorFinding(
            RefactorCategory.DOC_REDUNDANCY, SweepSeverity.MEDIUM, "d.md", "df", "s"
        )
        cf = RefactorFinding(
            RefactorCategory.DEAD_CODE, SweepSeverity.LOW, "c.py", "cf", "s"
        )
        analyzer.analyze_tests = MagicMock(return_value=[tf])
        # "docs" now routes to analyze_doc_drift (Issue #1098)
        analyzer.analyze_doc_drift = MagicMock(return_value=[df])
        analyzer.analyze_code = MagicMock(return_value=[cf])

        report = analyzer.full_analysis()
        assert len(report.findings) == 3
        assert report.has_findings
        assert report.scan_duration_ms >= 0

    def test_records_duration(self, tmp_path):
        """Test that scan_duration_ms is recorded."""
        analyzer = RefactorAnalyzer(tmp_path)
        analyzer.analyze_tests = MagicMock(return_value=[])
        analyzer.analyze_docs = MagicMock(return_value=[])
        analyzer.analyze_code = MagicMock(return_value=[])

        report = analyzer.full_analysis()
        assert report.scan_duration_ms >= 0


# =============================================================================
# Error Handling Tests
# =============================================================================


class TestRefactorAnalyzerErrorHandling:
    """Tests for RefactorAnalyzer graceful degradation."""

    def test_analyze_tests_handles_shape_error(self, tmp_path):
        """Test that analyze_tests continues when shape analysis fails."""
        analyzer = RefactorAnalyzer(tmp_path)
        analyzer._analyze_test_shape = MagicMock(side_effect=RuntimeError("boom"))
        analyzer._detect_test_waste = MagicMock(return_value=[])

        # Should not raise
        findings = analyzer.analyze_tests()
        assert isinstance(findings, list)

    def test_analyze_tests_handles_waste_error(self, tmp_path):
        """Test that analyze_tests continues when waste detection fails."""
        analyzer = RefactorAnalyzer(tmp_path)
        analyzer._analyze_test_shape = MagicMock(return_value=([], {}))
        analyzer._detect_test_waste = MagicMock(side_effect=RuntimeError("boom"))

        findings = analyzer.analyze_tests()
        assert isinstance(findings, list)

    def test_analyze_docs_handles_error(self, tmp_path):
        """Test that analyze_docs continues when redundancy detection fails."""
        analyzer = RefactorAnalyzer(tmp_path)
        analyzer._detect_doc_redundancy = MagicMock(side_effect=RuntimeError("boom"))

        findings = analyzer.analyze_docs()
        assert isinstance(findings, list)
        assert findings == []

    def test_analyze_code_handles_dead_code_error(self, tmp_path):
        """Test that analyze_code continues when dead code detection fails."""
        analyzer = RefactorAnalyzer(tmp_path)
        analyzer._detect_dead_code_cross_file = MagicMock(
            side_effect=RuntimeError("boom")
        )
        analyzer._detect_unused_libs = MagicMock(return_value=[])

        findings = analyzer.analyze_code()
        assert isinstance(findings, list)

    def test_analyze_code_handles_unused_libs_error(self, tmp_path):
        """Test that analyze_code continues when unused lib detection fails."""
        analyzer = RefactorAnalyzer(tmp_path)
        analyzer._detect_dead_code_cross_file = MagicMock(return_value=[])
        analyzer._detect_unused_libs = MagicMock(side_effect=RuntimeError("boom"))

        findings = analyzer.analyze_code()
        assert isinstance(findings, list)

    def test_refactor_analyzer_composes_sweep_analyzer(self, tmp_path):
        """Test that RefactorAnalyzer creates a SweepAnalyzer instance."""
        analyzer = RefactorAnalyzer(tmp_path)
        assert hasattr(analyzer, "_sweep_analyzer")
        from sweep_analyzer import SweepAnalyzer

        assert isinstance(analyzer._sweep_analyzer, SweepAnalyzer)


# =============================================================================
# Exclude Dirs Tests (Issue #514)
# =============================================================================


class TestRefactorAnalyzerExcludeDirs:
    """Tests for DEFAULT_EXCLUDE_DIRS constant, custom override, and _should_skip_path."""

    def test_default_exclude_dirs_constant(self):
        """Verify the class constant exists and contains required directories."""
        assert hasattr(RefactorAnalyzer, "DEFAULT_EXCLUDE_DIRS")
        required = {".git", ".worktrees", ".claude", "sessions", "archived", "node_modules"}
        for d in required:
            assert d in RefactorAnalyzer.DEFAULT_EXCLUDE_DIRS, (
                f"Expected '{d}' in DEFAULT_EXCLUDE_DIRS"
            )

    def test_custom_exclude_dirs_override(self, tmp_path):
        """Verify __init__ exclude_dirs parameter overrides the class default."""
        custom = {"custom_excluded_dir", ".git"}
        analyzer = RefactorAnalyzer(tmp_path, exclude_dirs=custom)
        assert analyzer.exclude_dirs == custom
        assert "node_modules" not in analyzer.exclude_dirs  # Not in custom set

    def test_default_exclude_dirs_used_when_none(self, tmp_path):
        """Verify DEFAULT_EXCLUDE_DIRS is used when exclude_dirs is not provided."""
        analyzer = RefactorAnalyzer(tmp_path)
        assert analyzer.exclude_dirs is RefactorAnalyzer.DEFAULT_EXCLUDE_DIRS

    def test_should_skip_path_excluded_dir(self, tmp_path):
        """Verify _should_skip_path returns True for paths with excluded dir components."""
        analyzer = RefactorAnalyzer(tmp_path)
        worktrees_path = tmp_path / ".worktrees" / "feature-branch" / "lib" / "foo.py"
        assert analyzer._should_skip_path(worktrees_path) is True

    def test_should_skip_path_non_excluded(self, tmp_path):
        """Verify _should_skip_path returns False for normal paths."""
        analyzer = RefactorAnalyzer(tmp_path)
        normal_path = tmp_path / "plugins" / "autonomous-dev" / "lib" / "foo.py"
        assert analyzer._should_skip_path(normal_path) is False

    def test_should_skip_path_nested_excluded(self, tmp_path):
        """Verify _should_skip_path works for deeply nested excluded dirs."""
        analyzer = RefactorAnalyzer(tmp_path)
        nested = tmp_path / "a" / "b" / ".claude" / "c" / "file.md"
        assert analyzer._should_skip_path(nested) is True

    def test_skips_worktrees_dir_in_doc_redundancy(self, tmp_path):
        """Files under .worktrees/ are excluded from doc redundancy scanning."""
        content = "# Same content\n\nThis is identical text.\n" * 20
        (tmp_path / "README.md").write_text(content)
        worktree_dir = tmp_path / ".worktrees" / "some-branch"
        worktree_dir.mkdir(parents=True)
        (worktree_dir / "README.md").write_text(content)

        analyzer = RefactorAnalyzer(tmp_path)
        findings = analyzer._detect_doc_redundancy()
        # No pair should be found because .worktrees/ doc is excluded
        assert len(findings) == 0

    def test_skips_claude_dir_in_doc_redundancy(self, tmp_path):
        """Files under .claude/ are excluded from doc redundancy scanning."""
        content = "# Same content\n\nThis is identical text.\n" * 20
        (tmp_path / "README.md").write_text(content)
        claude_dir = tmp_path / ".claude" / "docs"
        claude_dir.mkdir(parents=True)
        (claude_dir / "README.md").write_text(content)

        analyzer = RefactorAnalyzer(tmp_path)
        findings = analyzer._detect_doc_redundancy()
        assert len(findings) == 0

    def test_skips_sessions_dir_in_doc_redundancy(self, tmp_path):
        """Files under sessions/ are excluded from doc redundancy scanning."""
        content = "# Same content\n\nThis is identical text.\n" * 20
        (tmp_path / "README.md").write_text(content)
        sessions_dir = tmp_path / "sessions" / "2026-01"
        sessions_dir.mkdir(parents=True)
        (sessions_dir / "session.md").write_text(content)

        analyzer = RefactorAnalyzer(tmp_path)
        findings = analyzer._detect_doc_redundancy()
        assert len(findings) == 0

    def test_skips_claude_dir_in_dead_code_detection(self, tmp_path):
        """Files under .claude/ are excluded from dead code scanning."""
        claude_lib_dir = tmp_path / ".claude" / "lib"
        claude_lib_dir.mkdir(parents=True)
        (claude_lib_dir / "utils.py").write_text(
            "def orphaned_claude_func_xyz():\n    return 1\n"
        )

        lib_dir = tmp_path / "plugins" / "autonomous-dev" / "lib"
        lib_dir.mkdir(parents=True)
        (lib_dir / "real_lib.py").write_text(
            "def active_func():\n    return 2\n"
        )
        cmd_dir = tmp_path / "plugins" / "autonomous-dev" / "commands"
        cmd_dir.mkdir(parents=True)
        (cmd_dir / "cmd.py").write_text("from real_lib import active_func\nactive_func()\n")

        analyzer = RefactorAnalyzer(tmp_path)
        findings = analyzer._detect_dead_code_cross_file()
        claude_findings = [
            f for f in findings if "orphaned_claude_func_xyz" in f.description
        ]
        assert len(claude_findings) == 0

    @pytest.mark.parametrize("excluded_dir", [
        ".git", ".worktrees", ".claude", "sessions", "archived",
        "node_modules", "__pycache__", ".venv", "venv",
    ])
    def test_skips_various_excluded_dirs_in_doc_redundancy(self, tmp_path, excluded_dir):
        """Parametrized: various excluded dirs are all skipped in doc redundancy."""
        content = "# Same\n\nIdentical content.\n" * 20
        (tmp_path / "README.md").write_text(content)
        excluded_path = tmp_path / excluded_dir / "sub"
        excluded_path.mkdir(parents=True)
        (excluded_path / "copy.md").write_text(content)

        analyzer = RefactorAnalyzer(tmp_path)
        findings = analyzer._detect_doc_redundancy()
        assert len(findings) == 0, (
            f"Expected no findings but got {len(findings)} for excluded dir '{excluded_dir}'"
        )


# =============================================================================
# ConfidenceLevel Tests
# =============================================================================


class TestRefactorFindingConfidence:
    """Tests for ConfidenceLevel enum and confidence field on RefactorFinding."""

    def test_default_confidence_is_high(self):
        """Test that default confidence is HIGH."""
        finding = RefactorFinding(
            category=RefactorCategory.DEAD_CODE,
            severity=SweepSeverity.MEDIUM,
            file_path="x.py",
            description="test",
            suggestion="fix",
        )
        assert finding.confidence == ConfidenceLevel.HIGH

    def test_confidence_in_format_medium(self):
        """Test that format includes [confidence:medium] for MEDIUM confidence."""
        finding = RefactorFinding(
            category=RefactorCategory.DEAD_CODE,
            severity=SweepSeverity.MEDIUM,
            file_path="x.py",
            description="dead func",
            suggestion="remove",
            confidence=ConfidenceLevel.MEDIUM,
        )
        formatted = finding.format()
        assert "[confidence:medium]" in formatted

    def test_confidence_not_in_format_high(self):
        """Test that format does NOT include confidence tag for HIGH confidence."""
        finding = RefactorFinding(
            category=RefactorCategory.DEAD_CODE,
            severity=SweepSeverity.MEDIUM,
            file_path="x.py",
            description="dead func",
            suggestion="remove",
            confidence=ConfidenceLevel.HIGH,
        )
        formatted = finding.format()
        assert "[confidence:" not in formatted

    def test_confidence_in_to_dict(self):
        """Test that to_dict() includes 'confidence' key."""
        report = RefactorReport(
            findings=[
                RefactorFinding(
                    RefactorCategory.DEAD_CODE,
                    SweepSeverity.MEDIUM,
                    "x.py",
                    "dead",
                    "remove",
                    confidence=ConfidenceLevel.MEDIUM,
                ),
            ],
            modes_run=["code"],
        )
        d = report.to_dict()
        assert d["findings"][0]["confidence"] == "medium"

    def test_confidence_level_enum_values(self):
        """Test ConfidenceLevel enum values."""
        assert ConfidenceLevel.HIGH.value == "high"
        assert ConfidenceLevel.MEDIUM.value == "medium"
        assert ConfidenceLevel.LOW.value == "low"


# =============================================================================
# Dead Code Word Boundary Tests
# =============================================================================


class TestDeadCodeWordBoundary:
    """Tests for word-boundary matching in dead code detection."""

    def test_does_not_match_substring(self, tmp_path):
        """Function create_manager should be flagged when only create_manager_factory exists."""
        lib_dir = tmp_path / "plugins" / "autonomous-dev" / "lib"
        lib_dir.mkdir(parents=True)
        lib_file = lib_dir / "utils.py"
        lib_file.write_text(
            "def create_manager():\n    return 1\n"
        )

        # Consumer only has create_manager_factory (substring, not exact match)
        cmd_dir = tmp_path / "plugins" / "autonomous-dev" / "commands"
        cmd_dir.mkdir(parents=True)
        (cmd_dir / "runner.py").write_text(
            "def create_manager_factory():\n    return 2\n"
        )

        analyzer = RefactorAnalyzer(tmp_path)
        findings = analyzer._detect_dead_code_cross_file()
        dead = [f for f in findings if "create_manager" in f.description]
        # create_manager IS dead because create_manager_factory is not an exact match
        assert len(dead) == 1

    def test_matches_exact_word(self, tmp_path):
        """Function process_data should NOT be flagged when consumer has process_data()."""
        lib_dir = tmp_path / "plugins" / "autonomous-dev" / "lib"
        lib_dir.mkdir(parents=True)
        lib_file = lib_dir / "utils.py"
        lib_file.write_text(
            "def process_data():\n    return 1\n"
        )

        cmd_dir = tmp_path / "plugins" / "autonomous-dev" / "commands"
        cmd_dir.mkdir(parents=True)
        (cmd_dir / "runner.py").write_text(
            "from utils import process_data\nprocess_data()\n"
        )

        analyzer = RefactorAnalyzer(tmp_path)
        findings = analyzer._detect_dead_code_cross_file()
        dead = [f for f in findings if "process_data" in f.description]
        assert len(dead) == 0

    def test_dead_code_findings_have_medium_confidence(self, tmp_path):
        """Dead code findings should have MEDIUM confidence."""
        lib_dir = tmp_path / "plugins" / "autonomous-dev" / "lib"
        lib_dir.mkdir(parents=True)
        lib_file = lib_dir / "utils.py"
        lib_file.write_text(
            "def orphan_func_xyz():\n    return 1\n"
        )

        analyzer = RefactorAnalyzer(tmp_path)
        findings = analyzer._detect_dead_code_cross_file()
        dead = [f for f in findings if "orphan_func_xyz" in f.description]
        assert len(dead) == 1
        assert dead[0].confidence == ConfidenceLevel.MEDIUM


# =============================================================================
# Unused Lib Extended Scan Tests
# =============================================================================


class TestUnusedLibExtendedScan:
    """Tests for extended .md/.sh scanning in unused lib detection."""

    def test_detects_lib_used_in_md_file(self, tmp_path):
        """Lib referenced in .md file should NOT be flagged as unused."""
        lib_dir = tmp_path / "plugins" / "autonomous-dev" / "lib"
        lib_dir.mkdir(parents=True)
        (lib_dir / "my_special_lib.py").write_text("def helper(): pass\n")

        # No .py file references it, but a .md file does
        cmd_dir = tmp_path / "plugins" / "autonomous-dev" / "commands"
        cmd_dir.mkdir(parents=True)
        (cmd_dir / "implement.md").write_text(
            "# Implement\n\nUses my_special_lib for processing.\n"
        )

        analyzer = RefactorAnalyzer(tmp_path)
        findings = analyzer._detect_unused_libs()
        unused = [f for f in findings if "my_special_lib" in f.description]
        assert len(unused) == 0

    def test_detects_lib_used_in_sh_file(self, tmp_path):
        """Lib referenced in .sh file should NOT be flagged as unused."""
        lib_dir = tmp_path / "plugins" / "autonomous-dev" / "lib"
        lib_dir.mkdir(parents=True)
        (lib_dir / "deploy_helper.py").write_text("def run(): pass\n")

        # Only referenced in a .sh file
        scripts_dir = tmp_path / "scripts"
        scripts_dir.mkdir(parents=True)
        (scripts_dir / "deploy.sh").write_text(
            "#!/bin/bash\npython3 -c 'from deploy_helper import run; run()'\n"
        )

        analyzer = RefactorAnalyzer(tmp_path)
        findings = analyzer._detect_unused_libs()
        unused = [f for f in findings if "deploy_helper" in f.description]
        assert len(unused) == 0

    def test_not_confused_by_partial_match_in_md(self, tmp_path):
        """agent_tracker appearing only as old_agent_tracker_backup should still be flagged."""
        lib_dir = tmp_path / "plugins" / "autonomous-dev" / "lib"
        lib_dir.mkdir(parents=True)
        (lib_dir / "agent_tracker.py").write_text("def track(): pass\n")

        # .md file has only a partial match (substring, not word boundary)
        cmd_dir = tmp_path / "plugins" / "autonomous-dev" / "commands"
        cmd_dir.mkdir(parents=True)
        (cmd_dir / "notes.md").write_text(
            "# Notes\n\nRefer to old_agent_tracker_backup for history.\n"
        )

        analyzer = RefactorAnalyzer(tmp_path)
        findings = analyzer._detect_unused_libs()
        unused = [f for f in findings if "agent_tracker" in f.description]
        assert len(unused) == 1

    def test_unused_lib_findings_have_medium_confidence(self, tmp_path):
        """Unused lib findings should have MEDIUM confidence."""
        lib_dir = tmp_path / "plugins" / "autonomous-dev" / "lib"
        lib_dir.mkdir(parents=True)
        (lib_dir / "orphan_lib_xyz.py").write_text("def dead(): pass\n")

        analyzer = RefactorAnalyzer(tmp_path)
        findings = analyzer._detect_unused_libs()
        unused = [f for f in findings if "orphan_lib_xyz" in f.description]
        assert len(unused) == 1
        assert unused[0].confidence == ConfidenceLevel.MEDIUM
