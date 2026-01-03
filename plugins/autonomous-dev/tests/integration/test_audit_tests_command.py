"""
Integration tests for /audit-tests command.

Tests end-to-end workflow: command invocation, coverage analysis,
report generation, filtering, and error handling.

These tests should FAIL initially (TDD red phase).
"""

import json
import subprocess
from pathlib import Path
from unittest.mock import MagicMock, Mock, patch

import pytest


class TestAuditTestsFullReport:
    """Test full coverage report generation."""

    @pytest.fixture
    def sample_project(self, tmp_path):
        """Create sample project with source and tests."""
        # Create source files
        src_dir = tmp_path / "src"
        src_dir.mkdir()

        (src_dir / "user_service.py").write_text(
            """
def create_user(name):
    return {"name": name}

def delete_user(user_id):
    pass

def _internal_validate():
    pass
"""
        )

        (src_dir / "payment_service.py").write_text(
            """
class PaymentProcessor:
    def charge(self, amount):
        pass

    def refund(self, transaction_id):
        pass
"""
        )

        # Create test files
        tests_dir = tmp_path / "tests" / "unit"
        tests_dir.mkdir(parents=True)

        (tests_dir / "test_user_service.py").write_text(
            """
def test_create_user():
    assert True

def test_delete_user():
    assert True
"""
        )

        integration_dir = tmp_path / "tests" / "integration"
        integration_dir.mkdir(parents=True)

        (integration_dir / "test_payment_api.py").write_text(
            """
def test_payment_flow():
    assert True
"""
        )

        return tmp_path

    @patch("subprocess.run")
    def test_audit_tests_full_report(self, mock_run, sample_project):
        """Test full coverage report with all sections."""
        from test_coverage_analyzer import TestCoverageAnalyzer

        # Mock pytest execution
        mock_run.return_value = Mock(
            returncode=0,
            stdout="""
test_user_service.py::test_create_user PASSED
test_user_service.py::test_delete_user PASSED
test_payment_api.py::test_payment_flow PASSED
""",
            stderr="",
        )

        analyzer = TestCoverageAnalyzer(project_root=sample_project)
        report = analyzer.analyze_coverage()

        # Should generate complete report
        assert report.total_testable > 0
        assert report.total_covered >= 0
        assert 0 <= report.coverage_percentage <= 100

        # Should have coverage gaps
        assert len(report.coverage_gaps) > 0

        # Should detect layers
        layer_names = {layer.layer_name for layer in report.layer_coverage}
        assert "unit" in layer_names
        assert "integration" in layer_names

    @patch("subprocess.run")
    def test_audit_tests_coverage_gaps(self, mock_run, sample_project):
        """Test coverage gap detection."""
        from test_coverage_analyzer import TestCoverageAnalyzer

        mock_run.return_value = Mock(
            returncode=0,
            stdout="""
test_user_service.py::test_create_user PASSED
""",
            stderr="",
        )

        analyzer = TestCoverageAnalyzer(project_root=sample_project)
        report = analyzer.analyze_coverage()

        # Should identify untested items
        gap_names = {gap.item_name for gap in report.coverage_gaps}

        # delete_user should be in gaps (not tested)
        assert any("delete_user" in name for name in gap_names)

        # PaymentProcessor.charge should be in gaps (not tested)
        assert any("charge" in name or "PaymentProcessor" in name for name in gap_names)

    @patch("subprocess.run")
    def test_audit_tests_skipped_tests(self, mock_run, sample_project):
        """Test skipped test detection."""
        from test_coverage_analyzer import TestCoverageAnalyzer

        mock_run.return_value = Mock(
            returncode=0,
            stdout="""
test_user_service.py::test_create_user PASSED
test_user_service.py::test_delete_user SKIPPED (Flaky test)
test_payment_api.py::test_payment_flow XFAIL (Known issue #42)
""",
            stderr="",
        )

        analyzer = TestCoverageAnalyzer(project_root=sample_project)
        report = analyzer.analyze_coverage()

        # Should find skipped tests
        assert len(report.skipped_tests) == 2

        skip_names = {skip.test_name for skip in report.skipped_tests}
        assert any("test_delete_user" in name for name in skip_names)
        assert any("test_payment_flow" in name for name in skip_names)

        # Should capture reasons
        skip_reasons = {skip.reason for skip in report.skipped_tests}
        assert any("Flaky test" in reason for reason in skip_reasons)
        assert any("Known issue #42" in reason for reason in skip_reasons)


class TestAuditTestsLayerFilter:
    """Test layer filtering (--layer flag)."""

    @pytest.fixture
    def multilayer_project(self, tmp_path):
        """Create project with multiple test layers."""
        # Create test directories
        (tmp_path / "tests" / "unit").mkdir(parents=True)
        (tmp_path / "tests" / "integration").mkdir(parents=True)
        (tmp_path / "tests" / "e2e").mkdir(parents=True)

        # Create test files
        (tmp_path / "tests" / "unit" / "test_unit.py").write_text(
            "def test_unit(): pass"
        )
        (tmp_path / "tests" / "integration" / "test_integration.py").write_text(
            "def test_integration(): pass"
        )
        (tmp_path / "tests" / "e2e" / "test_e2e.py").write_text("def test_e2e(): pass")

        return tmp_path

    @patch("subprocess.run")
    def test_audit_tests_layer_filter_unit(self, mock_run, multilayer_project):
        """Test filtering for unit tests only."""
        from test_coverage_analyzer import TestCoverageAnalyzer

        mock_run.return_value = Mock(
            returncode=0,
            stdout="""
test_unit.py::test_unit PASSED
test_integration.py::test_integration PASSED
test_e2e.py::test_e2e PASSED
""",
            stderr="",
        )

        analyzer = TestCoverageAnalyzer(
            project_root=multilayer_project, layer_filter="unit"
        )
        report = analyzer.analyze_coverage()

        # Should only include unit layer
        layer_names = {layer.layer_name for layer in report.layer_coverage}
        assert "unit" in layer_names
        assert "integration" not in layer_names
        assert "e2e" not in layer_names

    @patch("subprocess.run")
    def test_audit_tests_layer_filter_integration(self, mock_run, multilayer_project):
        """Test filtering for integration tests only."""
        from test_coverage_analyzer import TestCoverageAnalyzer

        mock_run.return_value = Mock(
            returncode=0,
            stdout="""
test_unit.py::test_unit PASSED
test_integration.py::test_integration PASSED
test_e2e.py::test_e2e PASSED
""",
            stderr="",
        )

        analyzer = TestCoverageAnalyzer(
            project_root=multilayer_project, layer_filter="integration"
        )
        report = analyzer.analyze_coverage()

        # Should only include integration layer
        layer_names = {layer.layer_name for layer in report.layer_coverage}
        assert "integration" in layer_names
        assert "unit" not in layer_names
        assert "e2e" not in layer_names

    @patch("subprocess.run")
    def test_audit_tests_no_layer_filter(self, mock_run, multilayer_project):
        """Test no layer filter shows all layers."""
        from test_coverage_analyzer import TestCoverageAnalyzer

        mock_run.return_value = Mock(
            returncode=0,
            stdout="""
test_unit.py::test_unit PASSED
test_integration.py::test_integration PASSED
test_e2e.py::test_e2e PASSED
""",
            stderr="",
        )

        analyzer = TestCoverageAnalyzer(project_root=multilayer_project)
        report = analyzer.analyze_coverage()

        # Should include all layers
        layer_names = {layer.layer_name for layer in report.layer_coverage}
        assert "unit" in layer_names
        assert "integration" in layer_names
        assert "e2e" in layer_names


class TestAuditTestsNoSkipFlag:
    """Test --no-skip flag to omit skipped tests section."""

    @pytest.fixture
    def project_with_skips(self, tmp_path):
        """Create project with skipped tests."""
        tests_dir = tmp_path / "tests"
        tests_dir.mkdir()

        (tests_dir / "test_suite.py").write_text(
            """
def test_passing():
    assert True

def test_skipped():
    pytest.skip("Not ready")
"""
        )

        return tmp_path

    @patch("subprocess.run")
    def test_audit_tests_no_skip_flag(self, mock_run, project_with_skips):
        """Test --no-skip omits skipped tests section."""
        from test_coverage_analyzer import TestCoverageAnalyzer

        mock_run.return_value = Mock(
            returncode=0,
            stdout="""
test_suite.py::test_passing PASSED
test_suite.py::test_skipped SKIPPED (Not ready)
""",
            stderr="",
        )

        analyzer = TestCoverageAnalyzer(
            project_root=project_with_skips, include_skipped=False
        )
        report = analyzer.analyze_coverage()

        # Should not include skipped tests
        assert len(report.skipped_tests) == 0

    @patch("subprocess.run")
    def test_audit_tests_with_skip_default(self, mock_run, project_with_skips):
        """Test skipped tests included by default."""
        from test_coverage_analyzer import TestCoverageAnalyzer

        mock_run.return_value = Mock(
            returncode=0,
            stdout="""
test_suite.py::test_passing PASSED
test_suite.py::test_skipped SKIPPED (Not ready)
""",
            stderr="",
        )

        analyzer = TestCoverageAnalyzer(project_root=project_with_skips)
        report = analyzer.analyze_coverage()

        # Should include skipped tests by default
        assert len(report.skipped_tests) == 1
        assert "test_skipped" in report.skipped_tests[0].test_name


class TestPytestNotInstalled:
    """Test graceful handling when pytest not installed."""

    @pytest.fixture
    def project_without_pytest(self, tmp_path):
        """Create project without pytest."""
        src_dir = tmp_path / "src"
        src_dir.mkdir()

        (src_dir / "module.py").write_text("def func(): pass")

        return tmp_path

    @patch("subprocess.run")
    def test_pytest_not_installed(self, mock_run, project_without_pytest):
        """Test graceful message when pytest not installed."""
        from test_coverage_analyzer import TestCoverageAnalyzer

        # Mock pytest not found
        mock_run.side_effect = FileNotFoundError("pytest not found")

        analyzer = TestCoverageAnalyzer(project_root=project_without_pytest)
        report = analyzer.analyze_coverage()

        # Should still analyze static coverage (AST)
        assert report.total_testable >= 0

        # Should generate warning about pytest
        warnings = analyzer.get_warnings()
        assert any("pytest" in w.lower() for w in warnings)

    @patch("subprocess.run")
    def test_pytest_execution_failure(self, mock_run, project_without_pytest):
        """Test handling pytest execution failure."""
        from test_coverage_analyzer import TestCoverageAnalyzer

        # Mock pytest fails
        mock_run.return_value = Mock(
            returncode=1,
            stdout="",
            stderr="Collection error",
        )

        analyzer = TestCoverageAnalyzer(project_root=project_without_pytest)
        report = analyzer.analyze_coverage()

        # Should handle gracefully
        assert report is not None

        # Should generate warning
        warnings = analyzer.get_warnings()
        assert any("failed" in w.lower() or "error" in w.lower() for w in warnings)


class TestPytestCovFallback:
    """Test fallback when pytest-cov not installed."""

    @pytest.fixture
    def project_without_cov(self, tmp_path):
        """Create project without pytest-cov."""
        tests_dir = tmp_path / "tests"
        tests_dir.mkdir()

        (tests_dir / "test_basic.py").write_text("def test_basic(): pass")

        return tmp_path

    @patch("subprocess.run")
    def test_pytest_cov_fallback(self, mock_run, project_without_cov):
        """Test fallback to basic pytest when pytest-cov missing."""
        from test_coverage_analyzer import TestCoverageAnalyzer

        call_count = [0]

        def side_effect(*args, **kwargs):
            call_count[0] += 1
            if call_count[0] == 1:
                # First call with --cov fails
                raise FileNotFoundError("pytest-cov not installed")
            else:
                # Second call without --cov succeeds
                return Mock(
                    returncode=0,
                    stdout="test_basic.py::test_basic PASSED",
                    stderr="",
                )

        mock_run.side_effect = side_effect

        analyzer = TestCoverageAnalyzer(project_root=project_without_cov)
        report = analyzer.analyze_coverage()

        # Should fall back and succeed
        assert report is not None
        assert mock_run.call_count == 2

        # First call should have --cov
        first_call_args = mock_run.call_args_list[0][0][0]
        assert "--cov" in first_call_args

        # Second call should NOT have --cov
        second_call_args = mock_run.call_args_list[1][0][0]
        assert "--cov" not in second_call_args

    @patch("subprocess.run")
    def test_pytest_cov_basic_output_parsing(self, mock_run, project_without_cov):
        """Test parsing basic pytest output (no coverage plugin)."""
        from test_coverage_analyzer import TestCoverageAnalyzer

        mock_run.return_value = Mock(
            returncode=0,
            stdout="""
collected 5 items

test_basic.py::test_one PASSED
test_basic.py::test_two PASSED
test_basic.py::test_three SKIPPED (reason)
test_basic.py::test_four PASSED
test_basic.py::test_five XFAIL (known bug)

===== 3 passed, 1 skipped, 1 xfailed in 0.45s =====
""",
            stderr="",
        )

        analyzer = TestCoverageAnalyzer(project_root=project_without_cov)
        report = analyzer.analyze_coverage()

        # Should parse test counts from basic output
        assert report.total_tests >= 3  # At least 3 passed

        # Should find skipped tests
        assert len(report.skipped_tests) >= 1


class TestAuditTestsCommandIntegration:
    """Test /audit-tests command integration."""

    @pytest.fixture
    def mock_command_env(self, tmp_path, monkeypatch):
        """Mock command execution environment."""
        # Set working directory
        monkeypatch.chdir(tmp_path)

        # Create basic project structure
        (tmp_path / "src").mkdir()
        (tmp_path / "tests").mkdir()

        (tmp_path / "src" / "app.py").write_text(
            """
def main():
    pass

def helper():
    pass
"""
        )

        (tmp_path / "tests" / "test_app.py").write_text(
            """
def test_main():
    assert True
"""
        )

        return tmp_path

    @patch("subprocess.run")
    def test_command_execution_success(self, mock_run, mock_command_env):
        """Test successful command execution."""
        mock_run.return_value = Mock(
            returncode=0,
            stdout="test_app.py::test_main PASSED",
            stderr="",
        )

        # Simulate command invocation
        from test_coverage_analyzer import TestCoverageAnalyzer

        analyzer = TestCoverageAnalyzer(project_root=mock_command_env)
        report = analyzer.analyze_coverage()

        # Should complete without errors
        assert report is not None
        assert report.coverage_percentage >= 0

    @patch("subprocess.run")
    def test_command_with_json_output(self, mock_run, mock_command_env):
        """Test command with --json flag for machine-readable output."""
        mock_run.return_value = Mock(
            returncode=0,
            stdout="test_app.py::test_main PASSED",
            stderr="",
        )

        from test_coverage_analyzer import TestCoverageAnalyzer

        analyzer = TestCoverageAnalyzer(project_root=mock_command_env)
        report = analyzer.analyze_coverage()

        # Should be serializable to JSON
        json_output = {
            "total_testable": report.total_testable,
            "total_covered": report.total_covered,
            "coverage_percentage": report.coverage_percentage,
            "coverage_gaps": [
                {"name": gap.item_name, "type": gap.item_type, "file": gap.file_path}
                for gap in report.coverage_gaps
            ],
            "skipped_tests": [
                {"name": skip.test_name, "reason": skip.reason}
                for skip in report.skipped_tests
            ],
        }

        # Should be valid JSON
        json_str = json.dumps(json_output)
        assert json_str is not None
        assert isinstance(json.loads(json_str), dict)


class TestEdgeCases:
    """Test edge cases and error conditions."""

    @pytest.fixture
    def edge_case_project(self, tmp_path):
        """Create project with edge cases."""
        return tmp_path

    def test_no_tests_directory(self, edge_case_project):
        """Test project with no tests directory."""
        from test_coverage_analyzer import TestCoverageAnalyzer

        # Create source but no tests
        (edge_case_project / "src").mkdir()
        (edge_case_project / "src" / "app.py").write_text("def func(): pass")

        analyzer = TestCoverageAnalyzer(project_root=edge_case_project)
        report = analyzer.analyze_coverage()

        # Should complete with 0% coverage
        assert report.coverage_percentage == 0.0
        assert len(report.coverage_gaps) > 0

    def test_no_source_files(self, edge_case_project):
        """Test project with tests but no source."""
        from test_coverage_analyzer import TestCoverageAnalyzer

        # Create tests but no source
        (edge_case_project / "tests").mkdir()
        (edge_case_project / "tests" / "test_nothing.py").write_text(
            "def test_nothing(): pass"
        )

        analyzer = TestCoverageAnalyzer(project_root=edge_case_project)
        report = analyzer.analyze_coverage()

        # Should complete with 100% coverage (no source to cover)
        assert report.total_testable == 0
        assert report.coverage_percentage == 100.0

    def test_mixed_coverage_layers(self, edge_case_project):
        """Test project with mixed coverage across layers."""
        from test_coverage_analyzer import TestCoverageAnalyzer

        # Create source
        (edge_case_project / "src").mkdir()
        (edge_case_project / "src" / "app.py").write_text(
            """
def func1(): pass
def func2(): pass
def func3(): pass
"""
        )

        # Create partial unit tests
        unit_dir = edge_case_project / "tests" / "unit"
        unit_dir.mkdir(parents=True)
        (unit_dir / "test_app.py").write_text("def test_func1(): pass")

        # Create partial integration tests
        integration_dir = edge_case_project / "tests" / "integration"
        integration_dir.mkdir(parents=True)
        (integration_dir / "test_integration.py").write_text("def test_func2(): pass")

        analyzer = TestCoverageAnalyzer(project_root=edge_case_project)
        report = analyzer.analyze_coverage()

        # Should track coverage per layer
        assert len(report.layer_coverage) >= 2

        # Should have gaps (func3 not tested)
        gap_names = {gap.item_name for gap in report.coverage_gaps}
        assert "func3" in gap_names

    @patch("subprocess.run")
    def test_timeout_handling(self, mock_run, edge_case_project):
        """Test handling of test suite timeout."""
        from test_coverage_analyzer import TestCoverageAnalyzer

        mock_run.side_effect = subprocess.TimeoutExpired(cmd="pytest", timeout=60)

        (edge_case_project / "src").mkdir()
        (edge_case_project / "src" / "app.py").write_text("def func(): pass")

        analyzer = TestCoverageAnalyzer(project_root=edge_case_project)
        report = analyzer.analyze_coverage()

        # Should handle timeout gracefully
        assert report is not None

        # Should generate warning
        warnings = analyzer.get_warnings()
        assert any("timeout" in w.lower() for w in warnings)
