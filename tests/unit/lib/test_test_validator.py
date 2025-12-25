"""
Unit tests for test_validator.py

Tests validate that the test validator can execute tests, parse results,
and enforce TDD red phase validation before implementation.

These tests follow TDD - they should FAIL until implementation is complete.

Run with: pytest tests/unit/lib/test_test_validator.py --tb=line -q
"""

import subprocess
from pathlib import Path
from typing import Dict, List
from unittest.mock import Mock, patch, MagicMock

import pytest


class TestTestValidator:
    """Test suite for test validation and execution."""

    # =============================================================================
    # Test Execution Tests
    # =============================================================================

    def test_run_tests_success(self, tmp_path):
        """
        GIVEN: Test directory with passing tests
        WHEN: Running pytest
        THEN: Returns success result with pass count
        """
        from autonomous_dev.lib.test_validator import run_tests

        # Arrange
        test_file = tmp_path / "test_example.py"
        test_file.write_text("def test_example():\n    assert True\n")

        # Mock subprocess.run
        with patch('subprocess.run') as mock_run:
            mock_run.return_value = Mock(
                returncode=0,
                stdout="collected 1 item\ntest_example.py . [100%]\n1 passed in 0.01s",
                stderr=""
            )

            # Act
            result = run_tests(tmp_path)

            # Assert
            assert result["success"] is True
            assert result["passed"] == 1
            assert result["failed"] == 0
            assert result["errors"] == 0
            assert "pytest" in mock_run.call_args[0][0]

    def test_run_tests_failures(self, tmp_path):
        """
        GIVEN: Test directory with failing tests
        WHEN: Running pytest
        THEN: Returns failure result with fail count
        """
        from autonomous_dev.lib.test_validator import run_tests

        # Arrange
        test_file = tmp_path / "test_example.py"
        test_file.write_text("def test_example():\n    assert False\n")

        # Mock subprocess.run - pytest returns 1 for failures
        with patch('subprocess.run') as mock_run:
            mock_run.return_value = Mock(
                returncode=1,
                stdout="collected 1 item\ntest_example.py F [100%]\n1 failed in 0.01s",
                stderr=""
            )

            # Act
            result = run_tests(tmp_path)

            # Assert
            assert result["success"] is False
            assert result["passed"] == 0
            assert result["failed"] == 1
            assert result["errors"] == 0

    def test_run_tests_timeout(self, tmp_path):
        """
        GIVEN: Long-running test suite
        WHEN: Running pytest with 5-minute timeout
        THEN: Raises TimeoutError after timeout
        """
        from autonomous_dev.lib.test_validator import run_tests

        # Arrange
        test_file = tmp_path / "test_example.py"
        test_file.write_text("def test_example():\n    assert True\n")

        # Mock subprocess.run to raise TimeoutExpired
        with patch('subprocess.run') as mock_run:
            mock_run.side_effect = subprocess.TimeoutExpired(
                cmd="pytest",
                timeout=300
            )

            # Act & Assert
            with pytest.raises(TimeoutError, match="5 minutes"):
                run_tests(tmp_path, timeout=300)

    def test_run_tests_with_custom_args(self, tmp_path):
        """
        GIVEN: Custom pytest arguments
        WHEN: Running tests
        THEN: Passes custom args to pytest
        """
        from autonomous_dev.lib.test_validator import run_tests

        # Arrange
        test_file = tmp_path / "test_example.py"
        test_file.write_text("def test_example():\n    assert True\n")

        # Mock subprocess.run
        with patch('subprocess.run') as mock_run:
            mock_run.return_value = Mock(
                returncode=0,
                stdout="1 passed",
                stderr=""
            )

            # Act
            run_tests(tmp_path, pytest_args=["--tb=line", "-q"])

            # Assert
            args = mock_run.call_args[0][0]
            assert "--tb=line" in args
            assert "-q" in args

    def test_run_tests_minimal_verbosity(self, tmp_path):
        """
        GIVEN: Test directory
        WHEN: Running tests with minimal verbosity (Issue #90)
        THEN: Uses --tb=line -q flags
        """
        from autonomous_dev.lib.test_validator import run_tests

        # Arrange
        test_file = tmp_path / "test_example.py"
        test_file.write_text("def test_example():\n    assert True\n")

        # Mock subprocess.run
        with patch('subprocess.run') as mock_run:
            mock_run.return_value = Mock(
                returncode=0,
                stdout="1 passed",
                stderr=""
            )

            # Act
            run_tests(tmp_path)  # Should use minimal verbosity by default

            # Assert
            args = mock_run.call_args[0][0]
            assert "--tb=line" in args
            assert "-q" in args

    # =============================================================================
    # Test Result Parsing
    # =============================================================================

    def test_parse_pytest_output_counts(self):
        """
        GIVEN: pytest output with test counts
        WHEN: Parsing output
        THEN: Extracts pass/fail/error counts correctly
        """
        from autonomous_dev.lib.test_validator import parse_pytest_output

        # Arrange
        pytest_output = """
collected 42 items

test_example.py ........F..E.....                                   [100%]

=========================== short test summary info ============================
FAILED test_example.py::test_failure - AssertionError: expected 1, got 2
ERROR test_example.py::test_error - ImportError: module not found

========================= 35 passed, 1 failed, 1 error in 2.34s =================
"""

        # Act
        result = parse_pytest_output(pytest_output)

        # Assert
        assert result["passed"] == 35
        assert result["failed"] == 1
        assert result["errors"] == 1
        assert result["total"] == 42

    def test_parse_pytest_output_no_tests(self):
        """
        GIVEN: pytest output with no tests collected
        WHEN: Parsing output
        THEN: Returns zero counts
        """
        from autonomous_dev.lib.test_validator import parse_pytest_output

        # Arrange
        pytest_output = "collected 0 items\n\nno tests ran in 0.01s"

        # Act
        result = parse_pytest_output(pytest_output)

        # Assert
        assert result["passed"] == 0
        assert result["failed"] == 0
        assert result["errors"] == 0
        assert result["total"] == 0

    def test_parse_pytest_output_skipped_tests(self):
        """
        GIVEN: pytest output with skipped tests
        WHEN: Parsing output
        THEN: Extracts skipped count
        """
        from autonomous_dev.lib.test_validator import parse_pytest_output

        # Arrange
        pytest_output = "10 passed, 2 skipped in 1.23s"

        # Act
        result = parse_pytest_output(pytest_output)

        # Assert
        assert result["passed"] == 10
        assert result["skipped"] == 2

    # =============================================================================
    # TDD Red Phase Validation
    # =============================================================================

    def test_validate_red_phase_expects_failures(self, tmp_path):
        """
        GIVEN: Test suite with all passing tests
        WHEN: Validating red phase (no implementation yet)
        THEN: Blocks workflow and raises error (tests should fail first)
        """
        from autonomous_dev.lib.test_validator import validate_red_phase

        # Arrange - All tests pass (BAD in red phase)
        test_result = {
            "success": True,
            "passed": 10,
            "failed": 0,
            "errors": 0
        }

        # Act & Assert
        with pytest.raises(ValueError, match="TDD red phase violation"):
            validate_red_phase(test_result)

    def test_validate_red_phase_blocks_green(self):
        """
        GIVEN: Tests passing prematurely (implementation doesn't exist)
        WHEN: Validating red phase
        THEN: Blocks workflow with clear error message
        """
        from autonomous_dev.lib.test_validator import validate_red_phase

        # Arrange
        test_result = {
            "success": True,
            "passed": 5,
            "failed": 0,
            "errors": 0
        }

        # Act & Assert
        with pytest.raises(ValueError) as exc_info:
            validate_red_phase(test_result)

        error_msg = str(exc_info.value)
        assert "red phase" in error_msg.lower()
        assert "fail" in error_msg.lower()
        assert "implementation" in error_msg.lower()

    def test_validate_red_phase_accepts_import_errors(self):
        """
        GIVEN: Tests with import errors (module doesn't exist yet)
        WHEN: Validating red phase
        THEN: Accepts as valid red phase (expected in TDD)
        """
        from autonomous_dev.lib.test_validator import validate_red_phase

        # Arrange - Import errors are good in red phase
        test_result = {
            "success": False,
            "passed": 0,
            "failed": 0,
            "errors": 10
        }

        # Act - Should not raise
        validate_red_phase(test_result)

        # Assert - If we get here, validation passed

    def test_validate_red_phase_accepts_assertion_failures(self):
        """
        GIVEN: Tests with assertion failures
        WHEN: Validating red phase
        THEN: Accepts as valid red phase
        """
        from autonomous_dev.lib.test_validator import validate_red_phase

        # Arrange
        test_result = {
            "success": False,
            "passed": 0,
            "failed": 10,
            "errors": 0
        }

        # Act - Should not raise
        validate_red_phase(test_result)

        # Assert - If we get here, validation passed

    def test_validate_red_phase_allows_partial_failures(self):
        """
        GIVEN: Some tests pass, some fail (mixed state)
        WHEN: Validating red phase
        THEN: Accepts as valid (some failures exist)
        """
        from autonomous_dev.lib.test_validator import validate_red_phase

        # Arrange - Mixed results are acceptable
        test_result = {
            "success": False,
            "passed": 3,
            "failed": 7,
            "errors": 0
        }

        # Act - Should not raise
        validate_red_phase(test_result)

        # Assert - Passed validation

    # =============================================================================
    # Syntax Error Detection
    # =============================================================================

    def test_detect_syntax_errors(self):
        """
        GIVEN: pytest output with syntax errors
        WHEN: Detecting syntax errors
        THEN: Identifies syntax errors and returns details
        """
        from autonomous_dev.lib.test_validator import detect_syntax_errors

        # Arrange
        pytest_output = """
collected 0 items / 1 error

================================== ERRORS ===================================
_______________ ERROR collecting test_example.py ________________
test_example.py:5: SyntaxError: invalid syntax
"""

        # Act
        has_errors, details = detect_syntax_errors(pytest_output)

        # Assert
        assert has_errors is True
        assert len(details) > 0
        assert any("SyntaxError" in d for d in details)

    def test_detect_syntax_errors_import_errors(self):
        """
        GIVEN: pytest output with import errors
        WHEN: Detecting syntax errors
        THEN: Identifies import errors
        """
        from autonomous_dev.lib.test_validator import detect_syntax_errors

        # Arrange
        pytest_output = """
ERROR collecting test_example.py
ImportError: cannot import name 'NonExistentModule' from 'module'
"""

        # Act
        has_errors, details = detect_syntax_errors(pytest_output)

        # Assert
        assert has_errors is True
        assert any("ImportError" in d for d in details)

    def test_detect_syntax_errors_blocks_workflow(self):
        """
        GIVEN: Tests with syntax errors
        WHEN: Validating tests
        THEN: Blocks workflow with clear error message
        """
        from autonomous_dev.lib.test_validator import validate_test_syntax

        # Arrange
        test_result = {
            "success": False,
            "passed": 0,
            "failed": 0,
            "errors": 5,
            "stderr": "SyntaxError: invalid syntax on line 10"
        }

        # Act & Assert
        with pytest.raises(SyntaxError, match="Test files contain syntax errors"):
            validate_test_syntax(test_result)

    def test_detect_syntax_errors_differentiates_from_runtime_errors(self):
        """
        GIVEN: pytest output with runtime errors (not syntax)
        WHEN: Detecting syntax errors
        THEN: Does not flag runtime errors as syntax errors
        """
        from autonomous_dev.lib.test_validator import detect_syntax_errors

        # Arrange - Runtime error, not syntax
        pytest_output = """
FAILED test_example.py::test_division - ZeroDivisionError: division by zero
"""

        # Act
        has_errors, details = detect_syntax_errors(pytest_output)

        # Assert
        assert has_errors is False  # Runtime errors are not syntax errors

    # =============================================================================
    # Validation Gate Integration
    # =============================================================================

    def test_validation_gate_runs_before_reviewer(self, tmp_path):
        """
        GIVEN: Implementation complete
        WHEN: Running validation gate
        THEN: Executes tests before reviewer agent
        """
        from autonomous_dev.lib.test_validator import run_validation_gate

        # Arrange
        test_dir = tmp_path / "tests"
        test_dir.mkdir()
        (test_dir / "test_example.py").write_text("def test_ex(): assert True")

        # Mock subprocess.run
        with patch('subprocess.run') as mock_run:
            mock_run.return_value = Mock(
                returncode=0,
                stdout="1 passed in 0.01s",
                stderr=""
            )

            # Act
            result = run_validation_gate(test_dir)

            # Assert
            assert result["gate_passed"] is True
            assert result["all_tests_passed"] is True

    def test_validation_gate_blocks_on_failures(self, tmp_path):
        """
        GIVEN: Tests that fail
        WHEN: Running validation gate
        THEN: Blocks commit and returns failure
        """
        from autonomous_dev.lib.test_validator import run_validation_gate

        # Arrange
        test_dir = tmp_path / "tests"
        test_dir.mkdir()
        (test_dir / "test_example.py").write_text("def test_ex(): assert False")

        # Mock subprocess.run
        with patch('subprocess.run') as mock_run:
            mock_run.return_value = Mock(
                returncode=1,
                stdout="1 failed in 0.01s",
                stderr=""
            )

            # Act
            result = run_validation_gate(test_dir)

            # Assert
            assert result["gate_passed"] is False
            assert result["all_tests_passed"] is False
            assert "block_commit" in result
            assert result["block_commit"] is True

    def test_validation_gate_returns_detailed_results(self, tmp_path):
        """
        GIVEN: Test suite with mixed results
        WHEN: Running validation gate
        THEN: Returns detailed breakdown of results
        """
        from autonomous_dev.lib.test_validator import run_validation_gate

        # Arrange
        test_dir = tmp_path / "tests"
        test_dir.mkdir()

        # Mock subprocess.run
        with patch('subprocess.run') as mock_run:
            mock_run.return_value = Mock(
                returncode=1,
                stdout="10 passed, 2 failed, 1 error in 2.34s",
                stderr=""
            )

            # Act
            result = run_validation_gate(test_dir)

            # Assert
            assert "passed" in result
            assert "failed" in result
            assert "errors" in result
            assert result["passed"] == 10
            assert result["failed"] == 2
            assert result["errors"] == 1

    # =============================================================================
    # Test Coverage Validation
    # =============================================================================

    def test_validate_coverage_threshold(self, tmp_path):
        """
        GIVEN: Test suite with coverage report
        WHEN: Validating coverage threshold
        THEN: Blocks if coverage below 80%
        """
        from autonomous_dev.lib.test_validator import validate_coverage

        # Arrange - Mock coverage output
        coverage_output = """
Name                     Stmts   Miss  Cover
--------------------------------------------
module.py                  100     25    75%
--------------------------------------------
TOTAL                      100     25    75%
"""

        # Act & Assert
        with pytest.raises(ValueError, match="Coverage below 80%"):
            validate_coverage(coverage_output, threshold=80)

    def test_validate_coverage_passes_above_threshold(self):
        """
        GIVEN: Test suite with 85% coverage
        WHEN: Validating coverage threshold
        THEN: Passes validation
        """
        from autonomous_dev.lib.test_validator import validate_coverage

        # Arrange
        coverage_output = """
Name                     Stmts   Miss  Cover
--------------------------------------------
module.py                  100     15    85%
--------------------------------------------
TOTAL                      100     15    85%
"""

        # Act - Should not raise
        validate_coverage(coverage_output, threshold=80)

        # Assert - Passed if we get here

    # =============================================================================
    # Error Handling
    # =============================================================================

    def test_run_tests_handles_pytest_not_installed(self, tmp_path):
        """
        GIVEN: pytest not installed
        WHEN: Running tests
        THEN: Raises RuntimeError with installation guidance
        """
        from autonomous_dev.lib.test_validator import run_tests

        # Arrange
        with patch('subprocess.run') as mock_run:
            mock_run.side_effect = FileNotFoundError("pytest: command not found")

            # Act & Assert
            with pytest.raises(RuntimeError, match="pytest not installed"):
                run_tests(tmp_path)

    def test_run_tests_handles_no_tests_found(self, tmp_path):
        """
        GIVEN: Empty test directory
        WHEN: Running tests
        THEN: Returns result with zero tests
        """
        from autonomous_dev.lib.test_validator import run_tests

        # Arrange - Empty directory
        test_dir = tmp_path / "tests"
        test_dir.mkdir()

        # Mock subprocess.run
        with patch('subprocess.run') as mock_run:
            mock_run.return_value = Mock(
                returncode=5,  # pytest returns 5 for no tests collected
                stdout="collected 0 items\n",
                stderr=""
            )

            # Act
            result = run_tests(test_dir)

            # Assert
            assert result["total"] == 0
            assert "no_tests_collected" in result
            assert result["no_tests_collected"] is True

    def test_validate_red_phase_handles_zero_tests(self):
        """
        GIVEN: No tests collected
        WHEN: Validating red phase
        THEN: Raises error (need tests for TDD)
        """
        from autonomous_dev.lib.test_validator import validate_red_phase

        # Arrange
        test_result = {
            "success": False,
            "passed": 0,
            "failed": 0,
            "errors": 0,
            "total": 0
        }

        # Act & Assert
        with pytest.raises(ValueError, match="No tests found"):
            validate_red_phase(test_result)

    def test_parse_pytest_output_handles_malformed_output(self):
        """
        GIVEN: Malformed pytest output
        WHEN: Parsing output
        THEN: Returns default values without crashing
        """
        from autonomous_dev.lib.test_validator import parse_pytest_output

        # Arrange
        malformed_output = "garbage output\nno valid pytest format\n"

        # Act
        result = parse_pytest_output(malformed_output)

        # Assert
        assert isinstance(result, dict)
        assert "passed" in result
        assert "failed" in result
        # Should default to safe values
        assert result["passed"] >= 0
        assert result["failed"] >= 0
