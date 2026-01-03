#!/usr/bin/env python3
"""
Test Runner Library - Autonomous test execution with structured results.

This library autonomously executes pytest and returns structured TestResult
objects with pass/fail counts, output, and duration.

Features:
- Execute pytest and return structured TestResult
- Run single test file or function
- Verify all tests pass (boolean check)
- Handle pytest not found gracefully
- Handle timeout gracefully
- Handle test failures gracefully
- Parse pytest output for counts and duration

Usage:
    from test_runner import run_tests, verify_all_tests_pass, TestRunner

    # Run all tests
    result = run_tests()
    if result.passed:
        print(f"All {result.pass_count} tests passed!")

    # Run single test
    result = run_single_test("tests/unit/test_example.py::test_feature")

    # Quick boolean check
    if verify_all_tests_pass():
        print("All tests pass!")

    # Stateful execution
    runner = TestRunner(timeout=60, verbose=True)
    result = runner.run()

Author: implementer agent
Date: 2026-01-03
Related: Issue #200 - Debug-first enforcement and self-test requirements
"""

import re
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from subprocess import TimeoutExpired
from typing import Optional


@dataclass
class TestResult:
    """
    Structured test execution result.

    Attributes:
        passed: True if all tests passed (no failures or errors)
        pass_count: Number of tests that passed
        fail_count: Number of tests that failed
        error_count: Number of tests that errored
        output: Raw pytest output
        duration_seconds: Test execution time in seconds
    """

    passed: bool
    pass_count: int
    fail_count: int
    error_count: int
    output: str
    duration_seconds: float


def _parse_pytest_output(stdout: str, stderr: str, returncode: int) -> TestResult:
    """
    Parse pytest output to extract test counts and duration.

    Args:
        stdout: pytest stdout output
        stderr: pytest stderr output
        returncode: pytest exit code

    Returns:
        TestResult with parsed counts and duration
    """
    output = stdout + stderr

    # Parse counts from pytest summary line
    # Examples:
    # "===== 10 passed in 1.23s ====="
    # "===== 5 passed, 2 failed in 2.34s ====="
    # "===== 3 passed, 1 failed, 1 error in 3.45s ====="
    # "===== 1 error in 0.12s ====="

    pass_count = 0
    fail_count = 0
    error_count = 0
    duration_seconds = 0.0

    # Extract passed count
    pass_match = re.search(r'(\d+)\s+passed', stdout)
    if pass_match:
        pass_count = int(pass_match.group(1))

    # Extract failed count
    fail_match = re.search(r'(\d+)\s+failed', stdout)
    if fail_match:
        fail_count = int(fail_match.group(1))

    # Extract error count
    error_match = re.search(r'(\d+)\s+error', stdout)
    if error_match:
        error_count = int(error_match.group(1))

    # Extract duration
    duration_match = re.search(r'in\s+([\d.]+)s', stdout)
    if duration_match:
        duration_seconds = float(duration_match.group(1))

    # Determine if all tests passed
    passed = returncode == 0 and fail_count == 0 and error_count == 0

    return TestResult(
        passed=passed,
        pass_count=pass_count,
        fail_count=fail_count,
        error_count=error_count,
        output=output,
        duration_seconds=duration_seconds,
    )


def run_tests(
    test_dir: Optional[str] = None,
    pattern: Optional[str] = None,
    verbose: bool = False,
    coverage: bool = False,
    timeout: int = 300,
) -> TestResult:
    """
    Run pytest and return structured results.

    Args:
        test_dir: Directory to run tests in (default: current directory)
        pattern: Test file pattern to match (e.g., "test_*.py")
        verbose: Use verbose output (-v) instead of quiet (-q)
        coverage: Run with coverage (--cov)
        timeout: Timeout in seconds (default: 300)

    Returns:
        TestResult with test execution results

    Examples:
        >>> result = run_tests()
        >>> if result.passed:
        ...     print(f"All {result.pass_count} tests passed!")

        >>> result = run_tests(test_dir="tests/unit", verbose=True)
        >>> print(f"{result.pass_count} passed, {result.fail_count} failed")
    """
    # Build pytest command
    cmd = ["pytest"]

    # Add test directory or current directory
    if test_dir:
        cmd.append(test_dir)

    # Add pattern if provided
    if pattern:
        cmd.extend(["-k", pattern])

    # Add verbosity flags
    if verbose:
        cmd.append("-v")
    else:
        cmd.append("-q")

    # Add coverage if requested
    if coverage:
        cmd.extend(["--cov"])

    # Always use line traceback for consistent output
    cmd.append("--tb=line")

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
        )

        return _parse_pytest_output(result.stdout, result.stderr, result.returncode)

    except FileNotFoundError:
        # pytest not installed
        return TestResult(
            passed=False,
            pass_count=0,
            fail_count=0,
            error_count=1,
            output="Error: pytest not found. Please install pytest.",
            duration_seconds=0.0,
        )

    except TimeoutExpired:
        # Test execution timeout
        return TestResult(
            passed=False,
            pass_count=0,
            fail_count=0,
            error_count=1,
            output=f"Error: Test execution timeout after {timeout} seconds.",
            duration_seconds=float(timeout),
        )

    except KeyboardInterrupt:
        # User interrupted test execution
        return TestResult(
            passed=False,
            pass_count=0,
            fail_count=0,
            error_count=1,
            output="Error: Test execution interrupted by user.",
            duration_seconds=0.0,
        )

    except Exception as e:
        # Unexpected error
        return TestResult(
            passed=False,
            pass_count=0,
            fail_count=0,
            error_count=1,
            output=f"Error: Unexpected error during test execution: {e}",
            duration_seconds=0.0,
        )


def run_single_test(test_path: str, timeout: int = 300) -> TestResult:
    """
    Run a single test file or function.

    Args:
        test_path: Path to test file or function (e.g., "tests/unit/test_example.py::test_feature")
        timeout: Timeout in seconds (default: 300)

    Returns:
        TestResult with test execution results

    Examples:
        >>> result = run_single_test("tests/unit/test_example.py")
        >>> result = run_single_test("tests/unit/test_example.py::test_feature")
        >>> result = run_single_test("tests/unit/test_example.py::TestClass::test_method")
    """
    # Build pytest command
    cmd = ["pytest", test_path, "-q", "--tb=line"]

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
        )

        return _parse_pytest_output(result.stdout, result.stderr, result.returncode)

    except FileNotFoundError:
        return TestResult(
            passed=False,
            pass_count=0,
            fail_count=0,
            error_count=1,
            output="Error: pytest not found. Please install pytest.",
            duration_seconds=0.0,
        )

    except TimeoutExpired:
        return TestResult(
            passed=False,
            pass_count=0,
            fail_count=0,
            error_count=1,
            output=f"Error: Test execution timeout after {timeout} seconds.",
            duration_seconds=float(timeout),
        )

    except Exception as e:
        return TestResult(
            passed=False,
            pass_count=0,
            fail_count=0,
            error_count=1,
            output=f"Error: {e}",
            duration_seconds=0.0,
        )


def verify_all_tests_pass(test_dir: Optional[str] = None, timeout: int = 300) -> bool:
    """
    Quick boolean check if all tests pass.

    Args:
        test_dir: Directory to run tests in (default: current directory)
        timeout: Timeout in seconds (default: 300)

    Returns:
        True if all tests passed, False otherwise

    Examples:
        >>> if verify_all_tests_pass():
        ...     print("All tests pass!")
        >>> if verify_all_tests_pass(test_dir="tests/unit"):
        ...     print("All unit tests pass!")
    """
    result = run_tests(test_dir=test_dir, timeout=timeout)
    return result.passed


class TestRunner:
    """
    Stateful test runner for repeated test execution.

    Attributes:
        timeout: Timeout in seconds (default: 300)
        verbose: Use verbose output (default: False)

    Examples:
        >>> runner = TestRunner(timeout=60, verbose=True)
        >>> result = runner.run()
        >>> if result.passed:
        ...     print("All tests passed!")

        >>> runner = TestRunner()
        >>> if runner.verify():
        ...     print("All tests pass!")
    """

    def __init__(self, timeout: int = 300, verbose: bool = False):
        """
        Initialize TestRunner.

        Args:
            timeout: Timeout in seconds (default: 300)
            verbose: Use verbose output (default: False)
        """
        self.timeout = timeout
        self.verbose = verbose

    def run(
        self,
        test_dir: Optional[str] = None,
        pattern: Optional[str] = None,
        coverage: bool = False,
    ) -> TestResult:
        """
        Run tests with configured settings.

        Args:
            test_dir: Directory to run tests in (default: current directory)
            pattern: Test file pattern to match
            coverage: Run with coverage

        Returns:
            TestResult with test execution results
        """
        return run_tests(
            test_dir=test_dir,
            pattern=pattern,
            verbose=self.verbose,
            coverage=coverage,
            timeout=self.timeout,
        )

    def run_single(self, test_path: str) -> TestResult:
        """
        Run a single test file or function.

        Args:
            test_path: Path to test file or function

        Returns:
            TestResult with test execution results
        """
        return run_single_test(test_path, timeout=self.timeout)

    def verify(self, test_dir: Optional[str] = None) -> bool:
        """
        Quick boolean check if all tests pass.

        Args:
            test_dir: Directory to run tests in (default: current directory)

        Returns:
            True if all tests passed, False otherwise
        """
        return verify_all_tests_pass(test_dir=test_dir, timeout=self.timeout)
