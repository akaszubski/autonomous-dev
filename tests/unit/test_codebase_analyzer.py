"""
Unit tests for codebase_analyzer.py - Phase 1: Codebase analysis.

TDD RED PHASE - These tests WILL FAIL until implementation exists.

Tests cover:
- Tech stack detection (Python, JS, multi-language)
- File organization analysis
- Metrics calculation (LOC, file counts)
- Mock brownfield-analyzer agent responses
- Report generation format
- Edge case: Empty project
"""

from pathlib import Path
from unittest.mock import Mock, patch

import pytest

# THESE IMPORTS WILL FAIL - Implementation doesn't exist yet
from plugins.autonomous_dev.lib.codebase_analyzer import (
    AnalysisReport,
    CodebaseAnalyzer,
    TechStack,
)


class TestTechStackDetection:
    """Test technology stack detection."""

    @pytest.fixture
    def temp_project(self, tmp_path):
        """Create temporary project directory."""
        return tmp_path

    def test_detect_python_project(self, temp_project):
        """Test detecting Python project."""
        # Create Python indicators
        (temp_project / "requirements.txt").write_text("pytest==7.4.0\n")
        (temp_project / "setup.py").write_text("from setuptools import setup\n")
        (temp_project / "main.py").write_text("print('hello')\n")

        analyzer = CodebaseAnalyzer(project_root=temp_project)
        report = analyzer.analyze()

        assert TechStack.PYTHON in report.tech_stacks
        assert "requirements.txt" in report.detected_files
        assert report.primary_language == "python"

    def test_detect_javascript_project(self, temp_project):
        """Test detecting JavaScript/Node.js project."""
        # Create JS indicators
        (temp_project / "package.json").write_text('{"name": "test"}\n')
        (temp_project / "index.js").write_text("console.log('hello');\n")

        analyzer = CodebaseAnalyzer(project_root=temp_project)
        report = analyzer.analyze()

        assert TechStack.JAVASCRIPT in report.tech_stacks
        assert "package.json" in report.detected_files
        assert report.primary_language == "javascript"

    def test_detect_multi_language_project(self, temp_project):
        """Test detecting project with multiple languages."""
        # Create Python + JS indicators
        (temp_project / "requirements.txt").write_text("pytest\n")
        (temp_project / "package.json").write_text('{"name": "test"}\n')
        (temp_project / "main.py").write_text("print('hello')\n")
        (temp_project / "index.js").write_text("console.log('hello');\n")

        analyzer = CodebaseAnalyzer(project_root=temp_project)
        report = analyzer.analyze()

        assert TechStack.PYTHON in report.tech_stacks
        assert TechStack.JAVASCRIPT in report.tech_stacks
        assert len(report.tech_stacks) == 2

    def test_detect_testing_frameworks(self, temp_project):
        """Test detecting testing frameworks."""
        (temp_project / "pytest.ini").write_text("[pytest]\n")
        (temp_project / "jest.config.js").write_text("module.exports = {};\n")

        analyzer = CodebaseAnalyzer(project_root=temp_project)
        report = analyzer.analyze()

        assert "pytest" in report.testing_frameworks
        assert "jest" in report.testing_frameworks

    def test_detect_ci_cd_config(self, temp_project):
        """Test detecting CI/CD configuration."""
        github_dir = temp_project / ".github" / "workflows"
        github_dir.mkdir(parents=True)
        (github_dir / "ci.yml").write_text("name: CI\n")

        analyzer = CodebaseAnalyzer(project_root=temp_project)
        report = analyzer.analyze()

        assert report.has_ci_cd is True
        assert "github_actions" in report.ci_cd_providers

    def test_empty_project_handling(self, temp_project):
        """Test handling empty project directory."""
        analyzer = CodebaseAnalyzer(project_root=temp_project)
        report = analyzer.analyze()

        assert report.tech_stacks == []
        assert report.total_files == 0
        assert report.total_lines == 0
        assert report.primary_language is None


class TestFileOrganizationAnalysis:
    """Test file organization analysis."""

    @pytest.fixture
    def python_project(self, tmp_path):
        """Create sample Python project structure."""
        project = tmp_path
        (project / "src").mkdir()
        (project / "tests").mkdir()
        (project / "docs").mkdir()
        (project / "src" / "main.py").write_text("def main():\n    pass\n")
        (project / "tests" / "test_main.py").write_text("def test_main():\n    assert True\n")
        (project / "README.md").write_text("# Project\n")
        return project

    def test_detect_source_directory(self, python_project):
        """Test detecting source code directory."""
        analyzer = CodebaseAnalyzer(project_root=python_project)
        report = analyzer.analyze()

        assert "src" in report.directory_structure
        assert report.has_source_directory is True

    def test_detect_test_directory(self, python_project):
        """Test detecting test directory."""
        analyzer = CodebaseAnalyzer(project_root=python_project)
        report = analyzer.analyze()

        assert "tests" in report.directory_structure
        assert report.has_test_directory is True

    def test_detect_documentation_directory(self, python_project):
        """Test detecting documentation directory."""
        analyzer = CodebaseAnalyzer(project_root=python_project)
        report = analyzer.analyze()

        assert "docs" in report.directory_structure
        assert report.has_docs_directory is True

    def test_analyze_file_distribution(self, python_project):
        """Test analyzing file distribution across directories."""
        analyzer = CodebaseAnalyzer(project_root=python_project)
        report = analyzer.analyze()

        assert report.file_distribution["src"] >= 1
        assert report.file_distribution["tests"] >= 1
        assert report.file_distribution["root"] >= 1  # README.md

    def test_detect_flat_structure(self, tmp_path):
        """Test detecting flat (non-organized) structure."""
        # Create files in root without organization
        (tmp_path / "main.py").write_text("print('hello')\n")
        (tmp_path / "utils.py").write_text("def util(): pass\n")
        (tmp_path / "test.py").write_text("def test(): assert True\n")

        analyzer = CodebaseAnalyzer(project_root=tmp_path)
        report = analyzer.analyze()

        assert report.structure_type == "flat"
        assert not report.has_source_directory


class TestMetricsCalculation:
    """Test code metrics calculation."""

    @pytest.fixture
    def sample_project(self, tmp_path):
        """Create sample project with known metrics."""
        project = tmp_path
        (project / "main.py").write_text("# Line 1\nprint('hello')\n# Line 3\n")
        (project / "utils.py").write_text("def func():\n    return 42\n")
        return project

    def test_count_total_files(self, sample_project):
        """Test counting total files."""
        analyzer = CodebaseAnalyzer(project_root=sample_project)
        report = analyzer.analyze()

        assert report.total_files == 2

    def test_count_total_lines(self, sample_project):
        """Test counting total lines of code."""
        analyzer = CodebaseAnalyzer(project_root=sample_project)
        report = analyzer.analyze()

        assert report.total_lines == 5  # 3 + 2

    def test_count_by_language(self, sample_project):
        """Test counting lines by language."""
        analyzer = CodebaseAnalyzer(project_root=sample_project)
        report = analyzer.analyze()

        assert report.lines_by_language["python"] == 5

    def test_calculate_test_coverage_estimate(self, tmp_path):
        """Test estimating test coverage from file counts."""
        # Create source and test files
        src_dir = tmp_path / "src"
        test_dir = tmp_path / "tests"
        src_dir.mkdir()
        test_dir.mkdir()

        (src_dir / "main.py").write_text("def main(): pass\n")
        (src_dir / "utils.py").write_text("def util(): pass\n")
        (test_dir / "test_main.py").write_text("def test_main(): assert True\n")

        analyzer = CodebaseAnalyzer(project_root=tmp_path)
        report = analyzer.analyze()

        # 1 test file for 2 source files = 50% coverage estimate
        assert report.estimated_test_coverage == 50.0

    def test_exclude_hidden_files(self, tmp_path):
        """Test hidden files are excluded from metrics."""
        (tmp_path / ".gitignore").write_text("*.pyc\n")
        (tmp_path / "main.py").write_text("print('hello')\n")

        analyzer = CodebaseAnalyzer(project_root=tmp_path)
        report = analyzer.analyze()

        assert report.total_files == 1  # Only main.py
        assert ".gitignore" not in report.detected_files


class TestAgentInvocation:
    """Test brownfield-analyzer agent invocation."""

    @pytest.fixture
    def analyzer(self, tmp_path):
        """Create CodebaseAnalyzer instance."""
        return CodebaseAnalyzer(project_root=tmp_path)

    @patch("plugins.autonomous_dev.lib.codebase_analyzer.invoke_agent")
    def test_invoke_brownfield_analyzer_agent(self, mock_invoke, analyzer, tmp_path):
        """Test invoking brownfield-analyzer agent."""
        mock_invoke.return_value = {
            "success": True,
            "analysis": {
                "patterns_found": ["flask_app", "pytest_tests"],
                "recommendations": ["Add CI/CD", "Improve docs"],
            },
        }

        report = analyzer.analyze()

        mock_invoke.assert_called_once_with(
            agent_name="brownfield-analyzer",
            task="Analyze codebase structure and patterns",
            context={"project_root": str(tmp_path)},
        )
        assert "flask_app" in report.patterns_found

    @patch("plugins.autonomous_dev.lib.codebase_analyzer.invoke_agent")
    def test_handle_agent_failure_gracefully(self, mock_invoke, analyzer):
        """Test handling agent invocation failure."""
        mock_invoke.return_value = {"success": False, "error": "Agent failed"}

        report = analyzer.analyze()

        # Should still return report with basic analysis
        assert report is not None
        assert report.agent_analysis is None
        assert "Agent failed" in report.warnings

    @patch("plugins.autonomous_dev.lib.codebase_analyzer.invoke_agent")
    def test_enrich_analysis_with_agent_insights(self, mock_invoke, analyzer):
        """Test enriching analysis with agent insights."""
        mock_invoke.return_value = {
            "success": True,
            "analysis": {
                "architecture_style": "monolithic",
                "design_patterns": ["factory", "singleton"],
                "quality_indicators": {"maintainability": "medium"},
            },
        }

        report = analyzer.analyze()

        assert report.architecture_style == "monolithic"
        assert "factory" in report.design_patterns
        assert report.quality_indicators["maintainability"] == "medium"


class TestReportGeneration:
    """Test analysis report generation."""

    @pytest.fixture
    def sample_report_data(self):
        """Create sample report data."""
        return {
            "tech_stacks": [TechStack.PYTHON],
            "primary_language": "python",
            "total_files": 50,
            "total_lines": 2500,
            "has_tests": True,
            "has_ci_cd": False,
            "structure_type": "organized",
        }

    def test_generate_report_summary(self, sample_report_data):
        """Test generating report summary."""
        report = AnalysisReport(**sample_report_data)
        summary = report.generate_summary()

        assert "Python" in summary
        assert "50 files" in summary
        assert "2500 lines" in summary

    def test_report_to_dict(self, sample_report_data):
        """Test converting report to dictionary."""
        report = AnalysisReport(**sample_report_data)
        data = report.to_dict()

        assert isinstance(data, dict)
        assert data["total_files"] == 50
        assert data["primary_language"] == "python"

    def test_report_to_json(self, sample_report_data):
        """Test converting report to JSON."""
        report = AnalysisReport(**sample_report_data)
        json_str = report.to_json()

        assert isinstance(json_str, str)
        assert "python" in json_str
        assert "50" in json_str

    def test_report_includes_recommendations(self, sample_report_data):
        """Test report includes actionable recommendations."""
        report = AnalysisReport(**sample_report_data)

        assert len(report.recommendations) > 0
        # No CI/CD detected, should recommend adding it
        assert any("CI/CD" in rec for rec in report.recommendations)

    def test_report_includes_warnings(self):
        """Test report includes warnings for issues."""
        report = AnalysisReport(
            tech_stacks=[TechStack.PYTHON],
            primary_language="python",
            total_files=10,
            total_lines=500,
            has_tests=False,  # Missing tests
            has_ci_cd=False,
            structure_type="flat",  # Poor organization
        )

        assert len(report.warnings) > 0
        assert any("test" in w.lower() for w in report.warnings)
        assert any("structure" in w.lower() for w in report.warnings)


class TestErrorHandling:
    """Test error handling in codebase analysis."""

    def test_invalid_project_root(self):
        """Test handling invalid project root path."""
        with pytest.raises(ValueError, match="Invalid project root"):
            CodebaseAnalyzer(project_root="/nonexistent/path")

    def test_permission_denied_handling(self, tmp_path):
        """Test handling permission denied errors."""
        protected_dir = tmp_path / "protected"
        protected_dir.mkdir()
        protected_dir.chmod(0o000)

        try:
            analyzer = CodebaseAnalyzer(project_root=tmp_path)
            report = analyzer.analyze()

            # Should log warning but continue
            assert len(report.warnings) > 0
        finally:
            protected_dir.chmod(0o755)  # Cleanup

    def test_binary_file_handling(self, tmp_path):
        """Test handling binary files during analysis."""
        binary_file = tmp_path / "image.png"
        binary_file.write_bytes(b"\x89PNG\r\n\x1a\n")

        analyzer = CodebaseAnalyzer(project_root=tmp_path)
        report = analyzer.analyze()

        # Should not crash, binary files excluded from line counts
        assert report.total_lines == 0

    def test_large_file_handling(self, tmp_path):
        """Test handling very large files."""
        large_file = tmp_path / "large.py"
        large_content = "# Line\n" * 100000  # 100k lines
        large_file.write_text(large_content)

        analyzer = CodebaseAnalyzer(project_root=tmp_path)
        report = analyzer.analyze()

        # Should handle without memory issues
        assert report.total_lines == 100000
