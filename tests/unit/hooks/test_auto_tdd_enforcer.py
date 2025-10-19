"""Unit tests for auto_tdd_enforcer.py hook"""

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# Add hooks directory to path for imports
sys.path.insert(
    0,
    str(
        Path(__file__).parent.parent.parent.parent
        / "plugins"
        / "autonomous-dev"
        / "hooks"
    ),
)

from auto_tdd_enforcer import (
    get_test_file_for_module,
    tests_exist,
    run_tests,
    should_skip_tdd,
    is_implementation,
)


class TestGetTestFileForModule:
    """Test test file path determination."""

    def test_maps_module_to_test_file(self):
        """Test mapping of module to test file."""
        module_path = Path("src/[project_name]/authentication.py")

        test_file = get_test_file_for_module(module_path)

        assert "test_authentication.py" in str(test_file)
        assert "unit" in str(test_file)

    def test_uses_module_stem(self):
        """Test that module stem is used for test name."""
        module_path = Path("src/[project_name]/user_manager.py")

        test_file = get_test_file_for_module(module_path)

        assert "test_user_manager.py" in str(test_file)

    def test_handles_nested_modules(self):
        """Test handling of nested module paths."""
        module_path = Path("src/[project_name]/core/adapter.py")

        test_file = get_test_file_for_module(module_path)

        # Should map to tests/unit/test_adapter.py
        assert "test_adapter.py" in str(test_file)


class TestTestsExist:
    """Test checking for test file existence."""

    def test_returns_true_when_file_exists(self, tmp_path):
        """Test returns True when test file exists."""
        test_file = tmp_path / "test_module.py"
        test_file.touch()

        assert tests_exist(test_file) is True

    def test_returns_false_when_file_missing(self, tmp_path):
        """Test returns False when test file doesn't exist."""
        test_file = tmp_path / "test_nonexistent.py"

        assert tests_exist(test_file) is False


class TestRunTests:
    """Test test execution."""

    @patch("subprocess.run")
    def test_returns_passing_for_successful_tests(self, mock_run, tmp_path):
        """Test returns (True, output) when tests pass."""
        # Create test file
        test_file = tmp_path / "test_module.py"
        test_file.touch()

        mock_run.return_value = MagicMock(
            returncode=0,
            stdout="All tests passed",
            stderr=""
        )

        passing, output = run_tests(test_file)

        assert passing is True
        assert "All tests passed" in output

    @patch("subprocess.run")
    def test_returns_failing_for_failed_tests(self, mock_run, tmp_path):
        """Test returns (False, output) when tests fail."""
        # Create test file
        test_file = tmp_path / "test_module.py"
        test_file.touch()

        mock_run.return_value = MagicMock(
            returncode=1,
            stdout="Tests failed",
            stderr="Error details"
        )

        passing, output = run_tests(test_file)

        assert passing is False
        assert "Tests failed" in output

    def test_returns_false_for_nonexistent_file(self):
        """Test returns (False, message) when test file doesn't exist."""
        test_file = Path("nonexistent_test.py")

        passing, output = run_tests(test_file)

        assert passing is False
        assert "does not exist" in output

    @patch("subprocess.run")
    def test_handles_timeout(self, mock_run, tmp_path):
        """Test handling of test timeout."""
        import subprocess

        # Create test file
        test_file = tmp_path / "test_module.py"
        test_file.touch()

        mock_run.side_effect = subprocess.TimeoutExpired("pytest", 30)

        passing, output = run_tests(test_file)

        assert passing is False
        assert "timeout" in output.lower() or "timed out" in output.lower()

    @patch("subprocess.run")
    def test_handles_exception(self, mock_run, tmp_path):
        """Test handling of test execution exception."""
        # Create test file
        test_file = tmp_path / "test_module.py"
        test_file.touch()

        mock_run.side_effect = Exception("Test error")

        passing, output = run_tests(test_file)

        assert passing is False
        assert "Error running tests" in output


class TestShouldSkipTDD:
    """Test TDD enforcement skip logic."""

    def test_skips_refactor(self):
        """Test skips TDD for refactoring."""
        assert should_skip_tdd("refactor the authentication module") is True

    def test_skips_rename(self):
        """Test skips TDD for renaming."""
        assert should_skip_tdd("rename function to calculateTotal") is True

    def test_skips_format(self):
        """Test skips TDD for formatting."""
        assert should_skip_tdd("format code with black") is True

    def test_skips_typo(self):
        """Test skips TDD for typo fixes."""
        assert should_skip_tdd("fix typo in docstring") is True

    def test_skips_comment(self):
        """Test skips TDD for comment updates."""
        assert should_skip_tdd("add comment explaining logic") is True

    def test_skips_docstring(self):
        """Test skips TDD for docstring updates."""
        assert should_skip_tdd("update docstring for clarity") is True

    def test_skips_bug_fix(self):
        """Test skips TDD for bug fixes (tests can come after)."""
        assert should_skip_tdd("fix bug in login flow") is True

    def test_skips_update_docs(self):
        """Test skips TDD for documentation updates."""
        assert should_skip_tdd("update docs for API changes") is True

    def test_does_not_skip_implementation(self):
        """Test does not skip TDD for new implementation."""
        assert should_skip_tdd("implement user authentication") is False
        assert should_skip_tdd("add feature for payments") is False

    def test_case_insensitive_matching(self):
        """Test that keyword matching is case insensitive."""
        assert should_skip_tdd("REFACTOR the module") is True
        assert should_skip_tdd("Fix Typo in name") is True


class TestIsImplementation:
    """Test implementation detection logic."""

    def test_detects_implement_keyword(self):
        """Test detection of 'implement' keyword."""
        assert is_implementation("implement user login") is True

    def test_detects_add_feature_keyword(self):
        """Test detection of 'add feature' keyword."""
        assert is_implementation("add feature for search") is True

    def test_detects_create_new_keyword(self):
        """Test detection of 'create new' keyword."""
        assert is_implementation("create new API endpoint") is True

    def test_case_insensitive_detection(self):
        """Test that detection is case insensitive."""
        assert is_implementation("IMPLEMENT new feature") is True
        assert is_implementation("Add Feature for users") is True

    def test_does_not_detect_non_implementation(self):
        """Test that non-implementation tasks are not detected."""
        # These should be caught by should_skip_tdd instead
        assert is_implementation("refactor existing code") is False
        assert is_implementation("rename variable") is False
