"""
Unit tests for test_coverage_analyzer.py library.

Tests AST-based test coverage analysis, layer detection, skip analysis,
and edge cases (syntax errors, path traversal, empty projects).

These tests should FAIL initially (TDD red phase).
"""

import ast
import subprocess
from pathlib import Path
from unittest.mock import MagicMock, Mock, patch

import pytest


class TestFindTestableItems:
    """Test AST scanning for functions and classes."""

    @pytest.fixture
    def analyzer(self, tmp_path):
        """Create TestCoverageAnalyzer instance."""
        from test_coverage_analyzer import TestCoverageAnalyzer

        return TestCoverageAnalyzer(project_root=tmp_path)

    def test_find_testable_items_functions(self, analyzer, tmp_path):
        """Test finding public functions (excludes private)."""
        source_file = tmp_path / "module.py"
        source_file.write_text(
            """
def public_func_1():
    pass

def public_func_2():
    pass

def public_func_3():
    pass

def _private_func_1():
    pass

def _private_func_2():
    pass
"""
        )

        items = analyzer.find_testable_items(source_file)

        # Should find 3 public functions, exclude 2 private
        assert len(items) == 3
        assert all(item["type"] == "function" for item in items)
        assert {item["name"] for item in items} == {
            "public_func_1",
            "public_func_2",
            "public_func_3",
        }
        assert all("_private" not in item["name"] for item in items)

    def test_find_testable_items_classes(self, analyzer, tmp_path):
        """Test finding classes."""
        source_file = tmp_path / "module.py"
        source_file.write_text(
            """
class UserService:
    def create_user(self):
        pass

class PaymentProcessor:
    def process_payment(self):
        pass
"""
        )

        items = analyzer.find_testable_items(source_file)

        # Should find 2 classes
        assert len(items) == 2
        assert all(item["type"] == "class" for item in items)
        assert {item["name"] for item in items} == {"UserService", "PaymentProcessor"}

    def test_find_testable_items_mixed(self, analyzer, tmp_path):
        """Test finding mix of functions and classes."""
        source_file = tmp_path / "module.py"
        source_file.write_text(
            """
def calculate_total():
    pass

class ShoppingCart:
    def add_item(self):
        pass

def validate_email():
    pass
"""
        )

        items = analyzer.find_testable_items(source_file)

        # Should find 1 class + 2 functions
        assert len(items) == 3
        function_items = [item for item in items if item["type"] == "function"]
        class_items = [item for item in items if item["type"] == "class"]

        assert len(function_items) == 2
        assert len(class_items) == 1
        assert class_items[0]["name"] == "ShoppingCart"

    def test_private_function_filtering(self, analyzer, tmp_path):
        """Test private functions are excluded."""
        source_file = tmp_path / "module.py"
        source_file.write_text(
            """
def public_func():
    pass

def _private_func():
    pass

def __dunder_func__():
    pass
"""
        )

        items = analyzer.find_testable_items(source_file)

        # Should only find public_func
        assert len(items) == 1
        assert items[0]["name"] == "public_func"

    def test_syntax_error_handling(self, analyzer, tmp_path):
        """Test graceful handling of syntax errors."""
        source_file = tmp_path / "broken.py"
        source_file.write_text(
            """
def broken_function(
    # Missing closing parenthesis
    pass
"""
        )

        # Should return empty list and not crash
        items = analyzer.find_testable_items(source_file)
        assert items == []

        # Should generate warning
        warnings = analyzer.get_warnings()
        assert any("syntax error" in w.lower() for w in warnings)
        assert any("broken.py" in w for w in warnings)

    def test_empty_file(self, analyzer, tmp_path):
        """Test empty Python file."""
        source_file = tmp_path / "empty.py"
        source_file.write_text("")

        items = analyzer.find_testable_items(source_file)
        assert items == []


class TestDetectLayer:
    """Test layer detection from directory structure."""

    @pytest.fixture
    def analyzer(self, tmp_path):
        """Create TestCoverageAnalyzer instance."""
        from test_coverage_analyzer import TestCoverageAnalyzer

        return TestCoverageAnalyzer(project_root=tmp_path)

    def test_detect_layer_unit(self, analyzer, tmp_path):
        """Test unit layer detection."""
        test_file = tmp_path / "tests" / "unit" / "test_foo.py"
        test_file.parent.mkdir(parents=True)
        test_file.write_text("# test file")

        layer = analyzer.detect_layer(test_file)
        assert layer == "unit"

    def test_detect_layer_integration(self, analyzer, tmp_path):
        """Test integration layer detection."""
        test_file = tmp_path / "tests" / "integration" / "test_api.py"
        test_file.parent.mkdir(parents=True)
        test_file.write_text("# test file")

        layer = analyzer.detect_layer(test_file)
        assert layer == "integration"

    def test_detect_layer_e2e(self, analyzer, tmp_path):
        """Test e2e layer detection."""
        test_file = tmp_path / "tests" / "e2e" / "test_flow.py"
        test_file.parent.mkdir(parents=True)
        test_file.write_text("# test file")

        layer = analyzer.detect_layer(test_file)
        assert layer == "e2e"

    def test_detect_layer_unknown(self, analyzer, tmp_path):
        """Test unknown layer defaults to unit with warning."""
        test_file = tmp_path / "tests" / "test_other.py"
        test_file.parent.mkdir(parents=True)
        test_file.write_text("# test file")

        layer = analyzer.detect_layer(test_file)
        assert layer == "unit"  # Default fallback

        # Should generate warning
        warnings = analyzer.get_warnings()
        assert any("unknown test layer" in w.lower() for w in warnings)
        assert any("test_other.py" in w for w in warnings)

    def test_detect_layer_nested_path(self, analyzer, tmp_path):
        """Test layer detection in deeply nested path."""
        test_file = tmp_path / "tests" / "unit" / "services" / "auth" / "test_login.py"
        test_file.parent.mkdir(parents=True)
        test_file.write_text("# test file")

        layer = analyzer.detect_layer(test_file)
        assert layer == "unit"


class TestFindSkippedTests:
    """Test parsing pytest output for skipped/xfail tests."""

    @pytest.fixture
    def analyzer(self, tmp_path):
        """Create TestCoverageAnalyzer instance."""
        from test_coverage_analyzer import TestCoverageAnalyzer

        return TestCoverageAnalyzer(project_root=tmp_path)

    def test_find_skipped_tests_with_reason(self, analyzer):
        """Test finding skipped tests with reason."""
        pytest_output = """
test_api.py::test_login SKIPPED (Flaky test, requires investigation)
test_api.py::test_logout PASSED
test_api.py::test_refresh SKIPPED (External dependency unavailable)
"""

        skipped = analyzer.find_skipped_tests(pytest_output)

        assert len(skipped) == 2
        assert skipped[0].test_name == "test_api.py::test_login"
        assert skipped[0].reason == "Flaky test, requires investigation"
        assert skipped[1].test_name == "test_api.py::test_refresh"
        assert skipped[1].reason == "External dependency unavailable"

    def test_find_skipped_tests_without_reason(self, analyzer):
        """Test skipped tests without reason generate warning."""
        pytest_output = """
test_api.py::test_login SKIPPED
test_api.py::test_logout PASSED
"""

        skipped = analyzer.find_skipped_tests(pytest_output)

        assert len(skipped) == 1
        assert skipped[0].test_name == "test_api.py::test_login"
        assert skipped[0].reason == "No reason provided"

        # Should generate warning
        warnings = analyzer.get_warnings()
        assert any("skipped without reason" in w.lower() for w in warnings)

    def test_find_xfail_tests(self, analyzer):
        """Test finding expected failures (xfail)."""
        pytest_output = """
test_api.py::test_login XFAIL (Known bug #123)
test_api.py::test_logout PASSED
test_api.py::test_refresh XFAIL (Waiting for upstream fix)
"""

        xfails = analyzer.find_skipped_tests(pytest_output)

        assert len(xfails) == 2
        assert xfails[0].test_name == "test_api.py::test_login"
        assert xfails[0].reason == "Known bug #123"
        assert xfails[1].test_name == "test_api.py::test_refresh"
        assert xfails[1].reason == "Waiting for upstream fix"

    def test_skip_reason_sanitization(self, analyzer):
        """Test skip reasons with secrets are redacted."""
        pytest_output = """
test_api.py::test_login SKIPPED (API_KEY=sk_test_12345 not available)
"""

        skipped = analyzer.find_skipped_tests(pytest_output)

        assert len(skipped) == 1
        # Should redact sensitive data
        assert "sk_test_12345" not in skipped[0].reason
        assert "***REDACTED***" in skipped[0].reason or "not available" in skipped[0].reason


class TestGenerateWarnings:
    """Test warning generation for test quality issues."""

    @pytest.fixture
    def analyzer(self, tmp_path):
        """Create TestCoverageAnalyzer instance."""
        from test_coverage_analyzer import TestCoverageAnalyzer

        return TestCoverageAnalyzer(project_root=tmp_path)

    def test_generate_warnings_high_skip_rate(self, analyzer):
        """Test warning for high skip rate (>10%)."""
        # Mock 15 skipped out of 100 total tests
        pytest_output = """
""" + "\n".join(
            [f"test_file.py::test_{i} SKIPPED (reason)" for i in range(15)]
        ) + "\n" + "\n".join(
            [f"test_file.py::test_{i} PASSED" for i in range(85)]
        )

        analyzer.find_skipped_tests(pytest_output)
        analyzer.calculate_skip_rate(total_tests=100)

        warnings = analyzer.get_warnings()
        assert any("high skip rate" in w.lower() for w in warnings)
        assert any("15%" in w or "15.0%" in w for w in warnings)

    def test_no_warning_acceptable_skip_rate(self, analyzer):
        """Test no warning for acceptable skip rate (<10%)."""
        # Mock 5 skipped out of 100 total tests
        pytest_output = """
""" + "\n".join(
            [f"test_file.py::test_{i} SKIPPED (reason)" for i in range(5)]
        ) + "\n" + "\n".join(
            [f"test_file.py::test_{i} PASSED" for i in range(95)]
        )

        analyzer.find_skipped_tests(pytest_output)
        analyzer.calculate_skip_rate(total_tests=100)

        warnings = analyzer.get_warnings()
        assert not any("high skip rate" in w.lower() for w in warnings)


class TestCoverageCalculation:
    """Test coverage percentage calculation."""

    @pytest.fixture
    def analyzer(self, tmp_path):
        """Create TestCoverageAnalyzer instance."""
        from test_coverage_analyzer import TestCoverageAnalyzer

        return TestCoverageAnalyzer(project_root=tmp_path)

    def test_coverage_calculation(self, analyzer):
        """Test coverage calculation formula."""
        coverage = analyzer.calculate_coverage(testable=100, covered=85)

        assert coverage == 85.0

    def test_coverage_calculation_zero_testable(self, analyzer):
        """Test coverage with zero testable items."""
        coverage = analyzer.calculate_coverage(testable=0, covered=0)

        assert coverage == 100.0  # Empty project is 100% covered

    def test_coverage_calculation_perfect(self, analyzer):
        """Test 100% coverage."""
        coverage = analyzer.calculate_coverage(testable=50, covered=50)

        assert coverage == 100.0

    def test_coverage_calculation_zero_coverage(self, analyzer):
        """Test 0% coverage."""
        coverage = analyzer.calculate_coverage(testable=100, covered=0)

        assert coverage == 0.0


class TestPathTraversalPrevention:
    """Test security - prevent path traversal attacks."""

    @pytest.fixture
    def analyzer(self, tmp_path):
        """Create TestCoverageAnalyzer instance."""
        from test_coverage_analyzer import TestCoverageAnalyzer

        return TestCoverageAnalyzer(project_root=tmp_path)

    def test_path_traversal_prevention(self, analyzer, tmp_path):
        """Test analyzer rejects path traversal attempts."""
        # Attempt to access file outside project root
        malicious_path = tmp_path / ".." / ".." / "etc" / "passwd"

        # Should reject or skip file outside project root
        items = analyzer.find_testable_items(malicious_path)
        assert items == []

        # Should generate security warning
        warnings = analyzer.get_warnings()
        assert any(
            "outside project root" in w.lower() or "path traversal" in w.lower()
            for w in warnings
        )

    def test_symlink_prevention(self, analyzer, tmp_path):
        """Test analyzer handles symlinks safely."""
        # Create symlink to /etc/passwd
        source_file = tmp_path / "safe.py"
        source_file.write_text("def test(): pass")

        symlink_file = tmp_path / "evil_symlink.py"
        try:
            symlink_file.symlink_to("/etc/passwd")
        except OSError:
            pytest.skip("Cannot create symlinks on this system")

        # Should handle safely (either reject or process as broken file)
        items = analyzer.find_testable_items(symlink_file)
        assert items == []


class TestEmptyProject:
    """Test handling of empty projects."""

    @pytest.fixture
    def analyzer(self, tmp_path):
        """Create TestCoverageAnalyzer instance."""
        from test_coverage_analyzer import TestCoverageAnalyzer

        return TestCoverageAnalyzer(project_root=tmp_path)

    def test_empty_project(self, analyzer, tmp_path):
        """Test empty project generates empty report."""
        # Create empty project directory
        (tmp_path / "src").mkdir()
        (tmp_path / "tests").mkdir()

        report = analyzer.analyze_coverage()

        assert report.total_testable == 0
        assert report.total_covered == 0
        assert report.coverage_percentage == 100.0  # Empty = 100%
        assert len(report.coverage_gaps) == 0
        assert len(report.skipped_tests) == 0


class TestRunPytestCoverage:
    """Test pytest execution with coverage."""

    @pytest.fixture
    def analyzer(self, tmp_path):
        """Create TestCoverageAnalyzer instance."""
        from test_coverage_analyzer import TestCoverageAnalyzer

        return TestCoverageAnalyzer(project_root=tmp_path)

    @patch("subprocess.run")
    def test_run_pytest_with_coverage(self, mock_run, analyzer, tmp_path):
        """Test pytest execution with pytest-cov."""
        # Mock pytest-cov available
        mock_run.return_value = Mock(
            returncode=0,
            stdout="coverage: 85.0%",
            stderr="",
        )

        result = analyzer.run_pytest_coverage()

        # Should use pytest --cov
        mock_run.assert_called_once()
        call_args = mock_run.call_args[0][0]
        assert "pytest" in call_args
        assert "--cov" in call_args

    @patch("subprocess.run")
    def test_run_pytest_fallback_without_cov(self, mock_run, analyzer, tmp_path):
        """Test pytest fallback when pytest-cov not installed."""
        # Mock pytest-cov NOT available (ModuleNotFoundError)
        def side_effect(*args, **kwargs):
            if "--cov" in args[0]:
                raise FileNotFoundError("pytest-cov not found")
            return Mock(returncode=0, stdout="5 passed", stderr="")

        mock_run.side_effect = side_effect

        result = analyzer.run_pytest_coverage()

        # Should fall back to basic pytest
        assert mock_run.call_count == 2  # First fails, second succeeds
        fallback_call = mock_run.call_args[0][0]
        assert "pytest" in fallback_call
        assert "--cov" not in fallback_call

    @patch("subprocess.run")
    def test_run_pytest_timeout(self, mock_run, analyzer, tmp_path):
        """Test pytest timeout handling."""
        mock_run.side_effect = subprocess.TimeoutExpired(cmd="pytest", timeout=60)

        result = analyzer.run_pytest_coverage()

        # Should handle timeout gracefully
        assert result is None or "timeout" in str(result).lower()

        warnings = analyzer.get_warnings()
        assert any("timeout" in w.lower() for w in warnings)


class TestLayerCoverage:
    """Test per-layer coverage tracking."""

    @pytest.fixture
    def analyzer(self, tmp_path):
        """Create TestCoverageAnalyzer instance."""
        from test_coverage_analyzer import TestCoverageAnalyzer

        # Create test structure
        unit_dir = tmp_path / "tests" / "unit"
        integration_dir = tmp_path / "tests" / "integration"
        unit_dir.mkdir(parents=True)
        integration_dir.mkdir(parents=True)

        # Create test files
        (unit_dir / "test_foo.py").write_text("def test_foo(): pass")
        (integration_dir / "test_api.py").write_text("def test_api(): pass")

        return TestCoverageAnalyzer(project_root=tmp_path)

    def test_layer_coverage_separation(self, analyzer):
        """Test coverage is tracked separately per layer."""
        report = analyzer.analyze_coverage()

        # Should have separate layer coverage
        assert "unit" in {layer.layer_name for layer in report.layer_coverage}
        assert "integration" in {layer.layer_name for layer in report.layer_coverage}

        unit_layer = next(
            layer for layer in report.layer_coverage if layer.layer_name == "unit"
        )
        integration_layer = next(
            layer for layer in report.layer_coverage if layer.layer_name == "integration"
        )

        assert unit_layer.total_tests >= 0
        assert integration_layer.total_tests >= 0


@pytest.mark.parametrize(
    "file_content,expected_count",
    [
        ("def func1(): pass\ndef func2(): pass", 2),
        ("class MyClass:\n    pass", 1),
        ("def _private(): pass", 0),
        ("", 0),
    ],
)
def test_find_testable_items_parametrized(tmp_path, file_content, expected_count):
    """Test finding testable items with various file contents."""
    from test_coverage_analyzer import TestCoverageAnalyzer

    analyzer = TestCoverageAnalyzer(project_root=tmp_path)

    source_file = tmp_path / "test.py"
    source_file.write_text(file_content)

    items = analyzer.find_testable_items(source_file)
    assert len(items) == expected_count
