"""Integration tests for auto_add_to_regression.py workflow.

These tests verify the complete workflow of the regression test generation:
- Detecting commit types from user prompts
- Checking test pass/fail status
- Integration with subprocess calls

Goal: Increase coverage from 47.3% to 75-80%
Target: Helper functions and main execution logic
"""

import subprocess
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# Add hooks directory to path for imports
sys.path.insert(
    0,
    str(
        Path(__file__).parent.parent.parent
        / "plugins"
        / "autonomous-dev"
        / "hooks"
    ),
)

from auto_add_to_regression import (
    check_tests_passing,
    detect_commit_type,
    run_regression_test,
)


class TestDetectCommitTypeIntegration:
    """Integration tests for commit type detection with real-world scenarios."""

    def test_detect_commit_type_feature(self):
        """Test detection of feature commits with various phrasings."""
        test_cases = [
            "implement new user authentication system",
            "add feature for email notifications",
            "create API endpoint for data export",
            "implement oauth2 login",
            "add new dashboard widget",
        ]

        for prompt in test_cases:
            result = detect_commit_type(prompt)
            assert result == "feature", f"Failed to detect feature in: {prompt}"

    def test_detect_commit_type_bugfix(self):
        """Test detection of bugfix commits with various keywords."""
        test_cases = [
            "fix bug in login validation",
            "bug fix for memory leak",
            "resolve issue with database connection",
            "fix error in parsing logic",
            "fix crash on empty input",
            "repair broken authentication",
        ]

        for prompt in test_cases:
            result = detect_commit_type(prompt)
            assert result == "bugfix", f"Failed to detect bugfix in: {prompt}"

    def test_detect_commit_type_optimization(self):
        """Test detection of optimization commits."""
        test_cases = [
            "optimize database query performance",
            "improve performance of search algorithm",
            "make API calls faster",
            "speed up data processing",
            "optimize memory usage",
        ]

        for prompt in test_cases:
            result = detect_commit_type(prompt)
            assert result == "optimization", f"Failed to detect optimization in: {prompt}"

    def test_detect_commit_type_priority_bugfix_over_feature(self):
        """Test that bugfix keywords take priority when multiple types present."""
        # This tests the implicit priority in the keyword matching
        prompt = "implement new feature to fix bug in authentication"
        result = detect_commit_type(prompt)
        # Bugfix keywords are checked first, so should return bugfix
        assert result == "bugfix"

    def test_detect_commit_type_unknown(self):
        """Test that ambiguous commits return unknown."""
        test_cases = [
            "update documentation",
            "refactor code structure",
            "clean up imports",
            "update dependencies",
            "merge branch",
        ]

        for prompt in test_cases:
            result = detect_commit_type(prompt)
            assert result == "unknown", f"Should return unknown for: {prompt}"


class TestCheckTestsPassingIntegration:
    """Integration tests for check_tests_passing with subprocess interaction."""

    @patch("subprocess.run")
    def test_check_tests_passing_when_tests_exist(self, mock_run, tmp_path, monkeypatch):
        """Test check_tests_passing when tests exist and pass."""
        # Setup test environment
        tests_dir = tmp_path / "tests" / "unit"
        tests_dir.mkdir(parents=True)
        test_file = tests_dir / "test_example.py"
        test_file.write_text("def test_example(): assert True")

        monkeypatch.setattr("auto_add_to_regression.TESTS_DIR", tmp_path / "tests")

        # Mock successful test run
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout="test_example.py::test_example PASSED",
            stderr=""
        )

        file_path = Path("src/example.py")
        passing, message = check_tests_passing(file_path)

        assert passing is True
        assert "passing" in message.lower()

        # Verify subprocess was called correctly
        mock_run.assert_called_once()
        call_args = mock_run.call_args
        assert "pytest" in str(call_args)
        assert str(test_file) in str(call_args)
        assert call_args.kwargs["timeout"] == 60
        assert call_args.kwargs["capture_output"] is True

    @patch("subprocess.run")
    def test_check_tests_passing_when_tests_fail(self, mock_run, tmp_path, monkeypatch):
        """Test check_tests_passing when tests exist but fail."""
        # Setup test environment
        tests_dir = tmp_path / "tests" / "unit"
        tests_dir.mkdir(parents=True)
        test_file = tests_dir / "test_failing.py"
        test_file.write_text("def test_failing(): assert False")

        monkeypatch.setattr("auto_add_to_regression.TESTS_DIR", tmp_path / "tests")

        # Mock failing test run
        mock_run.return_value = MagicMock(
            returncode=1,
            stdout="test_failing.py::test_failing FAILED\nAssertionError",
            stderr=""
        )

        file_path = Path("src/failing.py")
        passing, message = check_tests_passing(file_path)

        assert passing is False
        assert "failing" in message.lower()
        assert "AssertionError" in message

    def test_check_tests_passing_when_no_tests(self, tmp_path, monkeypatch):
        """Test check_tests_passing when no tests exist for module."""
        # Setup test environment with no test file
        tests_dir = tmp_path / "tests" / "unit"
        tests_dir.mkdir(parents=True)

        monkeypatch.setattr("auto_add_to_regression.TESTS_DIR", tmp_path / "tests")

        file_path = Path("src/notest.py")
        passing, message = check_tests_passing(file_path)

        assert passing is False
        assert "No tests exist" in message

    @patch("subprocess.run")
    def test_check_tests_passing_timeout_error(self, mock_run, tmp_path, monkeypatch):
        """Test check_tests_passing handles timeout gracefully."""
        # Setup test environment
        tests_dir = tmp_path / "tests" / "unit"
        tests_dir.mkdir(parents=True)
        test_file = tests_dir / "test_timeout.py"
        test_file.write_text("def test_timeout(): pass")

        monkeypatch.setattr("auto_add_to_regression.TESTS_DIR", tmp_path / "tests")

        # Mock timeout exception
        mock_run.side_effect = subprocess.TimeoutExpired("pytest", 60)

        file_path = Path("src/timeout.py")
        passing, message = check_tests_passing(file_path)

        assert passing is False
        assert "Error running tests" in message
        assert "TimeoutExpired" in message

    @patch("subprocess.run")
    def test_check_tests_passing_file_not_found(self, mock_run, tmp_path, monkeypatch):
        """Test check_tests_passing handles FileNotFoundError."""
        # Setup test environment
        tests_dir = tmp_path / "tests" / "unit"
        tests_dir.mkdir(parents=True)
        test_file = tests_dir / "test_notfound.py"
        test_file.write_text("def test_notfound(): pass")

        monkeypatch.setattr("auto_add_to_regression.TESTS_DIR", tmp_path / "tests")

        # Mock FileNotFoundError (e.g., pytest not installed)
        mock_run.side_effect = FileNotFoundError("pytest not found")

        file_path = Path("src/notfound.py")
        passing, message = check_tests_passing(file_path)

        assert passing is False
        assert "Error running tests" in message
        assert "not found" in message.lower()

    @patch("subprocess.run")
    def test_check_tests_passing_called_process_error(self, mock_run, tmp_path, monkeypatch):
        """Test check_tests_passing handles CalledProcessError."""
        # Setup test environment
        tests_dir = tmp_path / "tests" / "unit"
        tests_dir.mkdir(parents=True)
        test_file = tests_dir / "test_error.py"
        test_file.write_text("def test_error(): pass")

        monkeypatch.setattr("auto_add_to_regression.TESTS_DIR", tmp_path / "tests")

        # Mock CalledProcessError
        mock_run.side_effect = subprocess.CalledProcessError(2, "pytest", "error output")

        file_path = Path("src/error.py")
        passing, message = check_tests_passing(file_path)

        assert passing is False
        assert "Error running tests" in message
        assert "CalledProcessError" in message


class TestRunRegressionTestIntegration:
    """Integration tests for run_regression_test function."""

    @patch("subprocess.run")
    def test_run_regression_test_success(self, mock_run, tmp_path):
        """Test run_regression_test when test passes."""
        test_file = tmp_path / "test_regression.py"
        test_file.write_text("def test_regression(): assert True")

        # Mock successful test run
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout="test_regression.py::test_regression PASSED",
            stderr=""
        )

        passing, output = run_regression_test(test_file)

        assert passing is True
        assert "PASSED" in output

        # Verify subprocess call
        mock_run.assert_called_once()
        call_args = mock_run.call_args
        assert "pytest" in str(call_args)
        assert str(test_file) in str(call_args)

    @patch("subprocess.run")
    def test_run_regression_test_failure(self, mock_run, tmp_path):
        """Test run_regression_test when test fails."""
        test_file = tmp_path / "test_regression_fail.py"
        test_file.write_text("def test_regression(): assert False")

        # Mock failing test run
        mock_run.return_value = MagicMock(
            returncode=1,
            stdout="test_regression_fail.py::test_regression FAILED",
            stderr="AssertionError: assert False"
        )

        passing, output = run_regression_test(test_file)

        assert passing is False
        assert "FAILED" in output
        assert "AssertionError" in output

    @patch("subprocess.run")
    def test_run_regression_test_timeout(self, mock_run, tmp_path):
        """Test run_regression_test handles timeout."""
        test_file = tmp_path / "test_regression_timeout.py"
        test_file.write_text("def test_regression(): pass")

        # Mock timeout
        mock_run.side_effect = subprocess.TimeoutExpired("pytest", 60)

        passing, output = run_regression_test(test_file)

        assert passing is False
        assert "Error running regression test" in output
        assert "TimeoutExpired" in output

    @patch("subprocess.run")
    def test_run_regression_test_file_not_found(self, mock_run, tmp_path):
        """Test run_regression_test handles FileNotFoundError."""
        test_file = tmp_path / "test_regression_notfound.py"
        test_file.write_text("def test_regression(): pass")

        # Mock FileNotFoundError
        mock_run.side_effect = FileNotFoundError("pytest not found")

        passing, output = run_regression_test(test_file)

        assert passing is False
        assert "Error running regression test" in output
        assert "not found" in output.lower()


class TestCreateRegressionTestIntegration:
    """Integration tests for create_regression_test function."""

    @patch("auto_add_to_regression.generate_feature_regression_test")
    def test_create_regression_test_feature(self, mock_generate, tmp_path, monkeypatch):
        """Test create_regression_test creates feature regression test."""
        from auto_add_to_regression import create_regression_test

        # Setup test environment
        regression_dir = tmp_path / "tests" / "regression"
        progression_dir = tmp_path / "tests" / "progression"

        monkeypatch.setattr("auto_add_to_regression.REGRESSION_DIR", regression_dir)
        monkeypatch.setattr("auto_add_to_regression.PROGRESSION_DIR", progression_dir)

        test_file = regression_dir / "test_feature_example.py"
        test_content = "def test_feature(): pass"

        mock_generate.return_value = (test_file, test_content)

        file_path = Path("src/example.py")
        result = create_regression_test("feature", file_path, "implement new feature")

        # Verify directories were created
        assert regression_dir.exists()
        assert progression_dir.exists()

        # Verify generate function was called
        mock_generate.assert_called_once_with(file_path, "implement new feature")

        # Verify test file was written
        assert result == test_file

    @patch("auto_add_to_regression.generate_bugfix_regression_test")
    def test_create_regression_test_bugfix(self, mock_generate, tmp_path, monkeypatch):
        """Test create_regression_test creates bugfix regression test."""
        from auto_add_to_regression import create_regression_test

        # Setup test environment
        regression_dir = tmp_path / "tests" / "regression"
        progression_dir = tmp_path / "tests" / "progression"

        monkeypatch.setattr("auto_add_to_regression.REGRESSION_DIR", regression_dir)
        monkeypatch.setattr("auto_add_to_regression.PROGRESSION_DIR", progression_dir)

        test_file = regression_dir / "test_bugfix_example.py"
        test_content = "def test_bugfix(): pass"

        mock_generate.return_value = (test_file, test_content)

        file_path = Path("src/example.py")
        result = create_regression_test("bugfix", file_path, "fix bug in login")

        # Verify generate function was called
        mock_generate.assert_called_once_with(file_path, "fix bug in login")
        assert result == test_file

    @patch("auto_add_to_regression.generate_performance_baseline_test")
    def test_create_regression_test_optimization(self, mock_generate, tmp_path, monkeypatch):
        """Test create_regression_test creates optimization regression test."""
        from auto_add_to_regression import create_regression_test

        # Setup test environment
        regression_dir = tmp_path / "tests" / "regression"
        progression_dir = tmp_path / "tests" / "progression"

        monkeypatch.setattr("auto_add_to_regression.REGRESSION_DIR", regression_dir)
        monkeypatch.setattr("auto_add_to_regression.PROGRESSION_DIR", progression_dir)

        test_file = progression_dir / "test_perf_example.py"
        test_content = "def test_performance(): pass"

        mock_generate.return_value = (test_file, test_content)

        file_path = Path("src/example.py")
        result = create_regression_test("optimization", file_path, "optimize database query")

        # Verify generate function was called
        mock_generate.assert_called_once_with(file_path, "optimize database query")
        assert result == test_file

    def test_create_regression_test_unknown_type(self, tmp_path, monkeypatch):
        """Test create_regression_test returns None for unknown type."""
        from auto_add_to_regression import create_regression_test

        # Setup test environment
        regression_dir = tmp_path / "tests" / "regression"
        progression_dir = tmp_path / "tests" / "progression"

        monkeypatch.setattr("auto_add_to_regression.REGRESSION_DIR", regression_dir)
        monkeypatch.setattr("auto_add_to_regression.PROGRESSION_DIR", progression_dir)

        file_path = Path("src/example.py")
        result = create_regression_test("unknown", file_path, "update docs")

        # Should return None for unknown type
        assert result is None


class TestMainExecutionLogic:
    """Integration tests for main execution logic scenarios."""

    @patch("auto_add_to_regression.create_regression_test")
    @patch("auto_add_to_regression.run_regression_test")
    @patch("auto_add_to_regression.check_tests_passing")
    @patch("sys.argv", ["auto_add_to_regression.py", "--dry-run"])
    def test_dry_run_mode(self, mock_check, mock_run, mock_create):
        """Test --dry-run mode outputs template without creating files."""
        from auto_add_to_regression import main

        # Capture stdout
        with patch("sys.stdout") as mock_stdout:
            with pytest.raises(SystemExit) as exc_info:
                main()

            # Should exit with 0
            assert exc_info.value.code == 0

        # Should not call actual functions
        mock_check.assert_not_called()
        mock_run.assert_not_called()
        mock_create.assert_not_called()

    @patch("auto_add_to_regression.create_regression_test")
    @patch("auto_add_to_regression.run_regression_test")
    @patch("auto_add_to_regression.check_tests_passing")
    @patch("sys.argv", ["auto_add_to_regression.py", "--dry-run", "--tier=smoke"])
    def test_dry_run_with_tier(self, mock_check, mock_run, mock_create):
        """Test --dry-run mode with --tier argument."""
        from auto_add_to_regression import main

        with patch("sys.stdout") as mock_stdout:
            with pytest.raises(SystemExit) as exc_info:
                main()

            assert exc_info.value.code == 0

    @patch("auto_add_to_regression.detect_commit_type")
    @patch("sys.argv", ["auto_add_to_regression.py", "tests/test_file.py", "update docs"])
    def test_skip_non_source_files(self, mock_detect):
        """Test that non-source files are skipped."""
        from auto_add_to_regression import main

        with pytest.raises(SystemExit) as exc_info:
            main()

        # Should exit early without detecting commit type
        mock_detect.assert_not_called()
        assert exc_info.value.code == 0

    @patch("auto_add_to_regression.detect_commit_type")
    @patch("sys.argv", ["auto_add_to_regression.py", "src/__init__.py", "add init"])
    def test_skip_init_files(self, mock_detect):
        """Test that __init__.py files are skipped."""
        from auto_add_to_regression import main

        with pytest.raises(SystemExit) as exc_info:
            main()

        # Should exit early without detecting commit type
        mock_detect.assert_not_called()
        assert exc_info.value.code == 0

    @patch("auto_add_to_regression.check_tests_passing")
    @patch("auto_add_to_regression.detect_commit_type")
    @patch("sys.argv", ["auto_add_to_regression.py", "src/feature.py", "update documentation"])
    def test_skip_unknown_commit_type(self, mock_detect, mock_check):
        """Test that unknown commit types are skipped."""
        from auto_add_to_regression import main

        mock_detect.return_value = "unknown"

        with pytest.raises(SystemExit) as exc_info:
            main()

        # Should detect commit type but not check tests
        mock_detect.assert_called_once()
        mock_check.assert_not_called()
        assert exc_info.value.code == 0

    @patch("auto_add_to_regression.create_regression_test")
    @patch("auto_add_to_regression.check_tests_passing")
    @patch("auto_add_to_regression.detect_commit_type")
    @patch("sys.argv", ["auto_add_to_regression.py", "src/bugfix.py", "fix bug in login"])
    def test_skip_when_tests_not_passing(self, mock_detect, mock_check, mock_create):
        """Test that regression tests are not created when tests fail."""
        from auto_add_to_regression import main

        mock_detect.return_value = "bugfix"
        mock_check.return_value = (False, "Tests failing")

        with pytest.raises(SystemExit) as exc_info:
            main()

        # Should detect and check but not create
        mock_detect.assert_called_once()
        mock_check.assert_called_once()
        mock_create.assert_not_called()
        assert exc_info.value.code == 0

    @patch("auto_add_to_regression.run_regression_test")
    @patch("auto_add_to_regression.create_regression_test")
    @patch("auto_add_to_regression.check_tests_passing")
    @patch("auto_add_to_regression.detect_commit_type")
    @patch("sys.argv", ["auto_add_to_regression.py", "src/feature.py", "implement new feature"])
    def test_full_workflow_success(self, mock_detect, mock_check, mock_create, mock_run, tmp_path):
        """Test complete workflow when everything succeeds."""
        from auto_add_to_regression import main

        test_file = tmp_path / "test_regression.py"

        mock_detect.return_value = "feature"
        mock_check.return_value = (True, "All tests passing")
        mock_create.return_value = test_file
        mock_run.return_value = (True, "Regression test PASSED")

        # main() doesn't raise SystemExit on success, just returns
        main()

        # Verify full workflow executed
        mock_detect.assert_called_once()
        mock_check.assert_called_once()
        mock_create.assert_called_once()
        mock_run.assert_called_once_with(test_file)

    @patch("auto_add_to_regression.run_regression_test")
    @patch("auto_add_to_regression.create_regression_test")
    @patch("auto_add_to_regression.check_tests_passing")
    @patch("auto_add_to_regression.detect_commit_type")
    @patch("sys.argv", ["auto_add_to_regression.py", "src/feature.py", "implement new feature"])
    def test_workflow_with_failing_regression_test(self, mock_detect, mock_check, mock_create, mock_run, tmp_path):
        """Test workflow when regression test fails."""
        from auto_add_to_regression import main

        test_file = tmp_path / "test_regression.py"

        mock_detect.return_value = "feature"
        mock_check.return_value = (True, "All tests passing")
        mock_create.return_value = test_file
        mock_run.return_value = (False, "Regression test FAILED")

        # main() doesn't raise SystemExit on success, just returns
        main()

        # Verify full workflow executed even with failing regression test
        mock_detect.assert_called_once()
        mock_check.assert_called_once()
        mock_create.assert_called_once()
        mock_run.assert_called_once_with(test_file)

    @patch("auto_add_to_regression.create_regression_test")
    @patch("auto_add_to_regression.check_tests_passing")
    @patch("auto_add_to_regression.detect_commit_type")
    @patch("sys.argv", ["auto_add_to_regression.py", "src/feature.py", "implement new feature"])
    def test_workflow_when_create_returns_none(self, mock_detect, mock_check, mock_create):
        """Test workflow when create_regression_test returns None."""
        from auto_add_to_regression import main

        mock_detect.return_value = "feature"
        mock_check.return_value = (True, "All tests passing")
        mock_create.return_value = None  # Skipped creation

        with pytest.raises(SystemExit) as exc_info:
            main()

        # Verify workflow stopped after create returned None
        mock_detect.assert_called_once()
        mock_check.assert_called_once()
        mock_create.assert_called_once()
        assert exc_info.value.code == 0
