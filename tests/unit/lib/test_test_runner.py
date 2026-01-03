#!/usr/bin/env python3
"""
TDD Tests for Test Runner Library (FAILING - Red Phase)

This module contains FAILING tests for test_runner.py which autonomously
executes pytest and returns structured results.

Requirements:
1. Execute pytest and return structured TestResult
2. Run single test file or function
3. Verify all tests pass (boolean check)
4. Handle pytest not found gracefully
5. Handle timeout gracefully
6. Handle test failures gracefully
7. Return proper TestResult with pass_count, fail_count, error_count, output, duration

Test Coverage Target: 95%+ of test execution logic

Following TDD principles:
- Write tests FIRST (red phase)
- Tests describe test execution requirements
- Tests should FAIL until test_runner.py is implemented
- Each test validates ONE execution requirement

Author: test-master agent
Date: 2026-01-03
Related: Issue #200 - Debug-first enforcement and self-test requirements
"""

import json
import os
import sys
from dataclasses import dataclass
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock, call
from subprocess import CalledProcessError, TimeoutExpired

import pytest

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

# This import will FAIL until test_runner.py is created
from plugins.autonomous_dev.lib.test_runner import (
    TestResult,
    TestRunner,
    run_tests,
    run_single_test,
    verify_all_tests_pass,
)


class TestTestResultDataClass:
    """Test TestResult dataclass structure."""

    def test_test_result_creation(self):
        """Test TestResult can be created with all fields.

        REQUIREMENT: TestResult dataclass with proper fields.
        Expected: TestResult created with passed, counts, output, duration.
        """
        result = TestResult(
            passed=True,
            pass_count=10,
            fail_count=0,
            error_count=0,
            output="===== 10 passed in 2.5s =====",
            duration_seconds=2.5
        )

        assert result.passed is True
        assert result.pass_count == 10
        assert result.fail_count == 0
        assert result.error_count == 0
        assert result.output == "===== 10 passed in 2.5s ====="
        assert result.duration_seconds == 2.5

    def test_test_result_failed_state(self):
        """Test TestResult represents failed test run.

        REQUIREMENT: TestResult tracks failures.
        Expected: TestResult with passed=False and fail_count > 0.
        """
        result = TestResult(
            passed=False,
            pass_count=8,
            fail_count=2,
            error_count=0,
            output="===== 8 passed, 2 failed in 3.0s =====",
            duration_seconds=3.0
        )

        assert result.passed is False
        assert result.fail_count == 2

    def test_test_result_error_state(self):
        """Test TestResult represents test run with errors.

        REQUIREMENT: TestResult tracks errors separately.
        Expected: TestResult with error_count > 0.
        """
        result = TestResult(
            passed=False,
            pass_count=5,
            fail_count=0,
            error_count=3,
            output="===== 5 passed, 3 errors in 1.2s =====",
            duration_seconds=1.2
        )

        assert result.error_count == 3
        assert result.passed is False


class TestRunTests:
    """Test run_tests() function for executing pytest."""

    @patch('subprocess.run')
    def test_run_tests_all_pass(self, mock_run):
        """Test running all tests when they pass.

        REQUIREMENT: Execute pytest and return structured results.
        Expected: TestResult with passed=True, counts parsed from output.
        """
        mock_run.return_value = Mock(
            returncode=0,
            stdout="===== 42 passed in 5.3s =====",
            stderr=""
        )

        result = run_tests()

        assert result.passed is True
        assert result.pass_count == 42
        assert result.fail_count == 0
        assert result.error_count == 0
        assert result.duration_seconds == 5.3
        assert "42 passed" in result.output

        # Verify pytest was called with correct args
        mock_run.assert_called_once()
        args = mock_run.call_args[0][0]
        assert args[0] == 'pytest'
        assert '--tb=line' in args
        assert '-q' in args

    @patch('subprocess.run')
    def test_run_tests_with_failures(self, mock_run):
        """Test running tests when some fail.

        REQUIREMENT: Handle test failures gracefully.
        Expected: TestResult with passed=False, fail_count parsed.
        """
        mock_run.return_value = Mock(
            returncode=1,
            stdout="===== 38 passed, 4 failed in 6.1s =====",
            stderr=""
        )

        result = run_tests()

        assert result.passed is False
        assert result.pass_count == 38
        assert result.fail_count == 4
        assert result.error_count == 0
        assert result.duration_seconds == 6.1

    @patch('subprocess.run')
    def test_run_tests_with_errors(self, mock_run):
        """Test running tests when some error out.

        REQUIREMENT: Handle test errors gracefully.
        Expected: TestResult with error_count parsed.
        """
        mock_run.return_value = Mock(
            returncode=1,
            stdout="===== 35 passed, 2 failed, 3 errors in 4.8s =====",
            stderr=""
        )

        result = run_tests()

        assert result.passed is False
        assert result.pass_count == 35
        assert result.fail_count == 2
        assert result.error_count == 3

    @patch('subprocess.run')
    def test_run_tests_custom_directory(self, mock_run):
        """Test running tests in custom directory.

        REQUIREMENT: Support custom test directories.
        Expected: pytest called with custom path.
        """
        mock_run.return_value = Mock(
            returncode=0,
            stdout="===== 10 passed in 2.0s =====",
            stderr=""
        )

        result = run_tests(test_dir="/custom/tests")

        args = mock_run.call_args[0][0]
        assert '/custom/tests' in args

    @patch('subprocess.run')
    def test_run_tests_pytest_not_found(self, mock_run):
        """Test handling pytest not installed.

        REQUIREMENT: Handle pytest not found gracefully.
        Expected: TestResult with passed=False, error message in output.
        """
        mock_run.side_effect = FileNotFoundError("pytest not found")

        result = run_tests()

        assert result.passed is False
        assert result.pass_count == 0
        assert result.fail_count == 0
        assert result.error_count == 1
        assert "pytest not found" in result.output.lower()

    @patch('subprocess.run')
    def test_run_tests_timeout(self, mock_run):
        """Test handling pytest timeout.

        REQUIREMENT: Handle timeout gracefully.
        Expected: TestResult with passed=False, timeout message in output.
        """
        mock_run.side_effect = TimeoutExpired(cmd='pytest', timeout=60)

        result = run_tests(timeout=60)

        assert result.passed is False
        assert "timeout" in result.output.lower()

    @patch('subprocess.run')
    def test_run_tests_with_verbosity(self, mock_run):
        """Test running tests with custom verbosity.

        REQUIREMENT: Support verbosity control.
        Expected: pytest called with verbosity flags.
        """
        mock_run.return_value = Mock(
            returncode=0,
            stdout="===== 10 passed in 2.0s =====",
            stderr=""
        )

        result = run_tests(verbose=True)

        args = mock_run.call_args[0][0]
        # Should use -v instead of -q for verbose mode
        assert '-v' in args or '-vv' in args

    @patch('subprocess.run')
    def test_run_tests_parses_summary_line(self, mock_run):
        """Test parsing pytest summary line correctly.

        REQUIREMENT: Parse pytest output for counts.
        Expected: Counts extracted from various summary formats.
        """
        # Test various pytest output formats
        test_cases = [
            ("===== 10 passed in 1.23s =====", 10, 0, 0),
            ("===== 5 passed, 2 failed in 2.34s =====", 5, 2, 0),
            ("===== 3 passed, 1 failed, 1 error in 3.45s =====", 3, 1, 1),
            ("===== 1 error in 0.12s =====", 0, 0, 1),
        ]

        for output, expected_pass, expected_fail, expected_error in test_cases:
            mock_run.return_value = Mock(
                returncode=0 if expected_fail == 0 and expected_error == 0 else 1,
                stdout=output,
                stderr=""
            )

            result = run_tests()

            assert result.pass_count == expected_pass, f"Failed for: {output}"
            assert result.fail_count == expected_fail, f"Failed for: {output}"
            assert result.error_count == expected_error, f"Failed for: {output}"


class TestRunSingleTest:
    """Test run_single_test() function for executing single test file/function."""

    @patch('subprocess.run')
    def test_run_single_test_file(self, mock_run):
        """Test running single test file.

        REQUIREMENT: Run single test file.
        Expected: pytest called with specific file path.
        """
        mock_run.return_value = Mock(
            returncode=0,
            stdout="===== 5 passed in 1.0s =====",
            stderr=""
        )

        result = run_single_test("tests/unit/test_example.py")

        args = mock_run.call_args[0][0]
        assert "tests/unit/test_example.py" in args
        assert result.passed is True
        assert result.pass_count == 5

    @patch('subprocess.run')
    def test_run_single_test_function(self, mock_run):
        """Test running single test function.

        REQUIREMENT: Run single test function.
        Expected: pytest called with file::function syntax.
        """
        mock_run.return_value = Mock(
            returncode=0,
            stdout="===== 1 passed in 0.5s =====",
            stderr=""
        )

        result = run_single_test("tests/unit/test_example.py::test_feature")

        args = mock_run.call_args[0][0]
        assert "tests/unit/test_example.py::test_feature" in args
        assert result.pass_count == 1

    @patch('subprocess.run')
    def test_run_single_test_class_method(self, mock_run):
        """Test running single test class method.

        REQUIREMENT: Run single test class method.
        Expected: pytest called with file::class::method syntax.
        """
        mock_run.return_value = Mock(
            returncode=0,
            stdout="===== 1 passed in 0.3s =====",
            stderr=""
        )

        result = run_single_test("tests/unit/test_example.py::TestClass::test_method")

        args = mock_run.call_args[0][0]
        assert "tests/unit/test_example.py::TestClass::test_method" in args

    @patch('subprocess.run')
    def test_run_single_test_file_not_found(self, mock_run):
        """Test running non-existent test file.

        REQUIREMENT: Handle test file not found gracefully.
        Expected: TestResult with passed=False, error in output.
        """
        mock_run.return_value = Mock(
            returncode=4,  # pytest exit code for collection error
            stdout="",
            stderr="ERROR: file not found: tests/nonexistent.py"
        )

        result = run_single_test("tests/nonexistent.py")

        assert result.passed is False
        assert "not found" in result.output.lower()


class TestVerifyAllTestsPass:
    """Test verify_all_tests_pass() convenience function."""

    @patch('subprocess.run')
    def test_verify_all_tests_pass_success(self, mock_run):
        """Test verify returns True when all tests pass.

        REQUIREMENT: Boolean check if all tests pass.
        Expected: Returns True for successful test run.
        """
        mock_run.return_value = Mock(
            returncode=0,
            stdout="===== 42 passed in 5.0s =====",
            stderr=""
        )

        result = verify_all_tests_pass()

        assert result is True

    @patch('subprocess.run')
    def test_verify_all_tests_pass_failure(self, mock_run):
        """Test verify returns False when tests fail.

        REQUIREMENT: Boolean check if all tests pass.
        Expected: Returns False for failed test run.
        """
        mock_run.return_value = Mock(
            returncode=1,
            stdout="===== 40 passed, 2 failed in 5.0s =====",
            stderr=""
        )

        result = verify_all_tests_pass()

        assert result is False

    @patch('subprocess.run')
    def test_verify_all_tests_pass_error(self, mock_run):
        """Test verify returns False when tests error.

        REQUIREMENT: Boolean check if all tests pass.
        Expected: Returns False for error in test run.
        """
        mock_run.side_effect = FileNotFoundError("pytest not found")

        result = verify_all_tests_pass()

        assert result is False


class TestTestRunnerClass:
    """Test TestRunner class for stateful test execution."""

    def test_test_runner_initialization(self):
        """Test TestRunner initializes with default settings.

        REQUIREMENT: TestRunner class for stateful execution.
        Expected: TestRunner created with default settings.
        """
        runner = TestRunner()

        assert runner.timeout == 300  # 5 minutes default
        assert runner.verbose is False

    def test_test_runner_custom_settings(self):
        """Test TestRunner initializes with custom settings.

        REQUIREMENT: TestRunner supports custom settings.
        Expected: TestRunner created with custom timeout and verbosity.
        """
        runner = TestRunner(timeout=60, verbose=True)

        assert runner.timeout == 60
        assert runner.verbose is True

    @patch('subprocess.run')
    def test_test_runner_run_method(self, mock_run):
        """Test TestRunner.run() executes tests.

        REQUIREMENT: TestRunner.run() method.
        Expected: Executes pytest and returns TestResult.
        """
        mock_run.return_value = Mock(
            returncode=0,
            stdout="===== 10 passed in 2.0s =====",
            stderr=""
        )

        runner = TestRunner()
        result = runner.run()

        assert result.passed is True
        assert result.pass_count == 10

    @patch('subprocess.run')
    def test_test_runner_run_single_method(self, mock_run):
        """Test TestRunner.run_single() executes single test.

        REQUIREMENT: TestRunner.run_single() method.
        Expected: Executes single test and returns TestResult.
        """
        mock_run.return_value = Mock(
            returncode=0,
            stdout="===== 1 passed in 0.5s =====",
            stderr=""
        )

        runner = TestRunner()
        result = runner.run_single("tests/unit/test_example.py::test_feature")

        assert result.passed is True
        assert result.pass_count == 1

    @patch('subprocess.run')
    def test_test_runner_verify_method(self, mock_run):
        """Test TestRunner.verify() checks if tests pass.

        REQUIREMENT: TestRunner.verify() boolean method.
        Expected: Returns True/False based on test results.
        """
        mock_run.return_value = Mock(
            returncode=0,
            stdout="===== 10 passed in 2.0s =====",
            stderr=""
        )

        runner = TestRunner()
        result = runner.verify()

        assert result is True


class TestEdgeCases:
    """Test edge cases and error handling."""

    @patch('subprocess.run')
    def test_empty_test_output(self, mock_run):
        """Test handling empty pytest output.

        REQUIREMENT: Handle edge cases gracefully.
        Expected: TestResult with zero counts, passed=False.
        """
        mock_run.return_value = Mock(
            returncode=5,  # pytest exit code for no tests collected
            stdout="",
            stderr="ERROR: no tests collected"
        )

        result = run_tests()

        assert result.passed is False
        assert result.pass_count == 0
        assert result.fail_count == 0

    @patch('subprocess.run')
    def test_malformed_pytest_output(self, mock_run):
        """Test handling malformed pytest output.

        REQUIREMENT: Handle malformed output gracefully.
        Expected: TestResult with best-effort parsing, zero counts if unparseable.
        """
        mock_run.return_value = Mock(
            returncode=0,
            stdout="some random output without summary",
            stderr=""
        )

        result = run_tests()

        # Should not crash, should have some result
        assert isinstance(result, TestResult)
        assert result.output == "some random output without summary"

    @patch('subprocess.run')
    def test_pytest_with_warnings(self, mock_run):
        """Test handling pytest with warnings.

        REQUIREMENT: Parse pytest output with warnings.
        Expected: Warnings included in output but don't affect pass/fail.
        """
        mock_run.return_value = Mock(
            returncode=0,
            stdout="===== 10 passed, 3 warnings in 2.0s =====",
            stderr=""
        )

        result = run_tests()

        assert result.passed is True
        assert result.pass_count == 10
        assert "warnings" in result.output.lower()

    @patch('subprocess.run')
    def test_pytest_keyboard_interrupt(self, mock_run):
        """Test handling pytest keyboard interrupt.

        REQUIREMENT: Handle interruption gracefully.
        Expected: TestResult with passed=False, interruption noted.
        """
        mock_run.side_effect = KeyboardInterrupt()

        result = run_tests()

        assert result.passed is False
        assert "interrupt" in result.output.lower()

    @patch('subprocess.run')
    def test_pytest_with_coverage(self, mock_run):
        """Test running pytest with coverage flags.

        REQUIREMENT: Support pytest with coverage.
        Expected: Coverage flags passed to pytest.
        """
        mock_run.return_value = Mock(
            returncode=0,
            stdout="===== 10 passed in 2.0s =====\nCoverage: 85%",
            stderr=""
        )

        result = run_tests(coverage=True)

        args = mock_run.call_args[0][0]
        assert '--cov' in args or 'coverage' in ' '.join(args)

    @patch('subprocess.run')
    def test_duration_parsing_edge_cases(self, mock_run):
        """Test duration parsing for various time formats.

        REQUIREMENT: Parse duration from various formats.
        Expected: Duration correctly parsed from different time units.
        """
        test_cases = [
            ("===== 10 passed in 0.12s =====", 0.12),
            ("===== 10 passed in 1.23s =====", 1.23),
            ("===== 10 passed in 12.34s =====", 12.34),
            ("===== 10 passed in 123.45s =====", 123.45),
        ]

        for output, expected_duration in test_cases:
            mock_run.return_value = Mock(
                returncode=0,
                stdout=output,
                stderr=""
            )

            result = run_tests()

            assert abs(result.duration_seconds - expected_duration) < 0.01, \
                f"Failed for: {output}, got {result.duration_seconds}"
