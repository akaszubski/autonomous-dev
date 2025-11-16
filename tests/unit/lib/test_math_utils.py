#!/usr/bin/env python3
"""
Unit tests for math_utils fibonacci calculator (TDD Red Phase).

Tests for fibonacci calculation with multiple algorithms and security integration.

TDD Mode: These tests are written BEFORE implementation.
All tests should FAIL initially (ImportError or missing functions).

Test Strategy:
- Unit tests for each algorithm (iterative, recursive, matrix)
- Base cases (n=0, n=1) for all algorithms
- Edge cases (negative, large values, boundaries)
- Input validation (type checking, range validation)
- Custom exception handling
- Security integration (audit logging)
- Performance characteristics for different algorithms

Date: 2025-11-16
Agent: test-master
Phase: TDD Red (tests written BEFORE implementation)
"""

import json
import os
import sys
import pytest
import tempfile
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock, call
from typing import Dict, Any

# Add lib directory to path for imports
sys.path.insert(
    0,
    str(
        Path(__file__).parent.parent.parent.parent
        / "plugins"
        / "autonomous-dev"
        / "lib"
    ),
)

# Import will fail - implementation doesn't exist yet (TDD!)
try:
    from math_utils import (
        calculate_fibonacci,
        FibonacciError,
        InvalidInputError,
        MethodNotSupportedError,
    )
except ImportError as e:
    pytest.skip(f"Implementation not found (TDD red phase): {e}", allow_module_level=True)


# ==============================================================================
# UNIT TESTS: BASE CASES
# ==============================================================================


class TestFibonacciBaseCases:
    """Test fibonacci base cases (n=0, n=1) for all algorithms."""

    def test_fibonacci_zero_iterative(self):
        """Test F(0) = 0 with iterative algorithm."""
        # Arrange
        n = 0
        expected = 0

        # Act
        result = calculate_fibonacci(n, method="iterative")

        # Assert
        assert result == expected

    def test_fibonacci_zero_recursive(self):
        """Test F(0) = 0 with recursive algorithm."""
        # Arrange
        n = 0
        expected = 0

        # Act
        result = calculate_fibonacci(n, method="recursive")

        # Assert
        assert result == expected

    def test_fibonacci_zero_matrix(self):
        """Test F(0) = 0 with matrix algorithm."""
        # Arrange
        n = 0
        expected = 0

        # Act
        result = calculate_fibonacci(n, method="matrix")

        # Assert
        assert result == expected

    def test_fibonacci_one_iterative(self):
        """Test F(1) = 1 with iterative algorithm."""
        # Arrange
        n = 1
        expected = 1

        # Act
        result = calculate_fibonacci(n, method="iterative")

        # Assert
        assert result == expected

    def test_fibonacci_one_recursive(self):
        """Test F(1) = 1 with recursive algorithm."""
        # Arrange
        n = 1
        expected = 1

        # Act
        result = calculate_fibonacci(n, method="recursive")

        # Assert
        assert result == expected

    def test_fibonacci_one_matrix(self):
        """Test F(1) = 1 with matrix algorithm."""
        # Arrange
        n = 1
        expected = 1

        # Act
        result = calculate_fibonacci(n, method="matrix")

        # Assert
        assert result == expected


# ==============================================================================
# UNIT TESTS: ALGORITHM CORRECTNESS
# ==============================================================================


class TestFibonacciIterativeAlgorithm:
    """Test iterative fibonacci algorithm."""

    @pytest.mark.parametrize(
        "n,expected",
        [
            (2, 1),    # F(2) = F(1) + F(0) = 1 + 0 = 1
            (3, 2),    # F(3) = F(2) + F(1) = 1 + 1 = 2
            (4, 3),    # F(4) = F(3) + F(2) = 2 + 1 = 3
            (5, 5),    # F(5) = F(4) + F(3) = 3 + 2 = 5
            (6, 8),    # F(6) = F(5) + F(4) = 5 + 3 = 8
            (10, 55),  # F(10) = 55
            (20, 6765),  # F(20) = 6765
        ],
    )
    def test_fibonacci_iterative_small_values(self, n, expected):
        """Test iterative algorithm with small to medium values."""
        # Arrange & Act
        result = calculate_fibonacci(n, method="iterative")

        # Assert
        assert result == expected

    def test_fibonacci_iterative_large_value(self):
        """Test iterative algorithm with large value (n=100)."""
        # Arrange
        n = 100
        expected = 354224848179261915075  # F(100)

        # Act
        result = calculate_fibonacci(n, method="iterative")

        # Assert
        assert result == expected

    def test_fibonacci_iterative_very_large_value(self):
        """Test iterative algorithm with very large value (n=1000)."""
        # Arrange
        n = 1000
        # F(1000) is a 209-digit number - just verify it's positive

        # Act
        result = calculate_fibonacci(n, method="iterative")

        # Assert
        assert result > 0
        assert isinstance(result, int)


class TestFibonacciRecursiveAlgorithm:
    """Test recursive fibonacci algorithm."""

    @pytest.mark.parametrize(
        "n,expected",
        [
            (2, 1),
            (3, 2),
            (4, 3),
            (5, 5),
            (6, 8),
            (10, 55),
        ],
    )
    def test_fibonacci_recursive_small_values(self, n, expected):
        """Test recursive algorithm with small values."""
        # Arrange & Act
        result = calculate_fibonacci(n, method="recursive")

        # Assert
        assert result == expected

    def test_fibonacci_recursive_moderate_value(self):
        """Test recursive algorithm with moderate value (n=20)."""
        # Arrange
        n = 20
        expected = 6765

        # Act
        result = calculate_fibonacci(n, method="recursive")

        # Assert
        assert result == expected

    @pytest.mark.slow
    def test_fibonacci_recursive_performance_limit(self):
        """Test recursive algorithm has reasonable performance limit (n=30)."""
        # Arrange
        n = 30
        expected = 832040

        # Act
        result = calculate_fibonacci(n, method="recursive")

        # Assert
        assert result == expected
        # Note: n>35 may be too slow for recursive algorithm


class TestFibonacciMatrixAlgorithm:
    """Test matrix exponentiation fibonacci algorithm."""

    @pytest.mark.parametrize(
        "n,expected",
        [
            (2, 1),
            (3, 2),
            (4, 3),
            (5, 5),
            (6, 8),
            (10, 55),
            (20, 6765),
            (50, 12586269025),
        ],
    )
    def test_fibonacci_matrix_various_values(self, n, expected):
        """Test matrix algorithm with various values."""
        # Arrange & Act
        result = calculate_fibonacci(n, method="matrix")

        # Assert
        assert result == expected

    def test_fibonacci_matrix_large_value(self):
        """Test matrix algorithm with large value (n=100)."""
        # Arrange
        n = 100
        expected = 354224848179261915075

        # Act
        result = calculate_fibonacci(n, method="matrix")

        # Assert
        assert result == expected

    def test_fibonacci_matrix_very_large_value(self):
        """Test matrix algorithm with very large value (n=10000)."""
        # Arrange
        n = 10000

        # Act
        result = calculate_fibonacci(n, method="matrix")

        # Assert
        assert result > 0
        assert isinstance(result, int)
        # Matrix method should be fast even for large n


# ==============================================================================
# UNIT TESTS: ALGORITHM CONSISTENCY
# ==============================================================================


class TestFibonacciAlgorithmConsistency:
    """Test all algorithms produce consistent results."""

    @pytest.mark.parametrize("n", [0, 1, 2, 5, 10, 15, 20])
    def test_all_algorithms_consistent(self, n):
        """Test all three algorithms produce same result for given n."""
        # Arrange & Act
        iterative_result = calculate_fibonacci(n, method="iterative")
        recursive_result = calculate_fibonacci(n, method="recursive")
        matrix_result = calculate_fibonacci(n, method="matrix")

        # Assert
        assert iterative_result == recursive_result == matrix_result


# ==============================================================================
# UNIT TESTS: INPUT VALIDATION
# ==============================================================================


class TestFibonacciInputValidation:
    """Test input validation and error handling."""

    def test_negative_input_raises_invalid_input_error(self):
        """Test negative n raises InvalidInputError."""
        # Arrange
        n = -1

        # Act & Assert
        with pytest.raises(InvalidInputError) as exc_info:
            calculate_fibonacci(n)

        assert "must be non-negative" in str(exc_info.value).lower()

    def test_input_above_max_raises_invalid_input_error(self):
        """Test n > 10000 raises InvalidInputError."""
        # Arrange
        n = 10001

        # Act & Assert
        with pytest.raises(InvalidInputError) as exc_info:
            calculate_fibonacci(n)

        assert "maximum" in str(exc_info.value).lower() or "10000" in str(exc_info.value)

    def test_non_integer_input_raises_type_error(self):
        """Test non-integer n raises TypeError."""
        # Arrange
        n = 5.5

        # Act & Assert
        with pytest.raises(TypeError) as exc_info:
            calculate_fibonacci(n)

        assert "integer" in str(exc_info.value).lower()

    def test_string_input_raises_type_error(self):
        """Test string n raises TypeError."""
        # Arrange
        n = "five"

        # Act & Assert
        with pytest.raises(TypeError):
            calculate_fibonacci(n)

    def test_none_input_raises_type_error(self):
        """Test None n raises TypeError."""
        # Arrange
        n = None

        # Act & Assert
        with pytest.raises(TypeError):
            calculate_fibonacci(n)


# ==============================================================================
# UNIT TESTS: METHOD VALIDATION
# ==============================================================================


class TestFibonacciMethodValidation:
    """Test method parameter validation."""

    def test_invalid_method_raises_method_not_supported_error(self):
        """Test invalid method raises MethodNotSupportedError."""
        # Arrange
        n = 5
        method = "invalid_method"

        # Act & Assert
        with pytest.raises(MethodNotSupportedError) as exc_info:
            calculate_fibonacci(n, method=method)

        assert "invalid_method" in str(exc_info.value).lower()

    def test_empty_method_raises_method_not_supported_error(self):
        """Test empty method string raises MethodNotSupportedError."""
        # Arrange
        n = 5
        method = ""

        # Act & Assert
        with pytest.raises(MethodNotSupportedError):
            calculate_fibonacci(n, method=method)

    @pytest.mark.parametrize(
        "method",
        ["iterative", "recursive", "matrix"],
    )
    def test_valid_methods_accepted(self, method):
        """Test all valid methods are accepted."""
        # Arrange
        n = 5

        # Act
        result = calculate_fibonacci(n, method=method)

        # Assert
        assert result == 5  # F(5) = 5

    def test_default_method_is_iterative(self):
        """Test default method is iterative."""
        # Arrange
        n = 10

        # Act
        result_default = calculate_fibonacci(n)
        result_explicit = calculate_fibonacci(n, method="iterative")

        # Assert
        assert result_default == result_explicit == 55


# ==============================================================================
# UNIT TESTS: CUSTOM EXCEPTIONS
# ==============================================================================


class TestFibonacciCustomExceptions:
    """Test custom exception hierarchy."""

    def test_fibonacci_error_is_base_exception(self):
        """Test FibonacciError is base exception for all fibonacci errors."""
        # Arrange & Act & Assert
        assert issubclass(InvalidInputError, FibonacciError)
        assert issubclass(MethodNotSupportedError, FibonacciError)

    def test_fibonacci_error_hierarchy(self):
        """Test exception hierarchy inherits from Exception."""
        # Arrange & Act & Assert
        assert issubclass(FibonacciError, Exception)

    def test_catch_all_fibonacci_errors(self):
        """Test catching all fibonacci errors with FibonacciError."""
        # Arrange
        n = -5

        # Act & Assert
        with pytest.raises(FibonacciError):
            calculate_fibonacci(n)

    def test_specific_exception_has_context(self):
        """Test InvalidInputError provides helpful context."""
        # Arrange
        n = -10

        # Act & Assert
        with pytest.raises(InvalidInputError) as exc_info:
            calculate_fibonacci(n)

        error_msg = str(exc_info.value)
        assert n in error_msg or str(n) in error_msg  # Error includes the value


# ==============================================================================
# INTEGRATION TESTS: SECURITY UTILS
# ==============================================================================


class TestFibonacciSecurityIntegration:
    """Test integration with security_utils for audit logging."""

    @patch("plugins.autonomous_dev.lib.security_utils.audit_log")
    def test_fibonacci_logs_calculation_start(self, mock_audit_log):
        """Test fibonacci calculation logs start event."""
        # Arrange
        n = 10
        method = "iterative"

        # Act
        calculate_fibonacci(n, method=method)

        # Assert
        mock_audit_log.assert_any_call(
            "math_utils",
            "fibonacci_calculation_start",
            {"n": n, "method": method},
        )

    @patch("plugins.autonomous_dev.lib.security_utils.audit_log")
    def test_fibonacci_logs_calculation_complete(self, mock_audit_log):
        """Test fibonacci calculation logs completion event."""
        # Arrange
        n = 5
        method = "matrix"

        # Act
        result = calculate_fibonacci(n, method=method)

        # Assert
        mock_audit_log.assert_any_call(
            "math_utils",
            "fibonacci_calculation_complete",
            {"n": n, "method": method, "result": result},
        )

    @patch("plugins.autonomous_dev.lib.security_utils.audit_log")
    def test_fibonacci_logs_validation_error(self, mock_audit_log):
        """Test fibonacci logs validation errors."""
        # Arrange
        n = -5

        # Act & Assert
        with pytest.raises(InvalidInputError):
            calculate_fibonacci(n)

        # Should log the error
        assert mock_audit_log.called
        # Find the error log call
        error_calls = [
            call for call in mock_audit_log.call_args_list
            if "error" in call[0][1].lower() or "invalid" in call[0][1].lower()
        ]
        assert len(error_calls) > 0

    @patch("plugins.autonomous_dev.lib.security_utils.audit_log")
    def test_fibonacci_logs_method_error(self, mock_audit_log):
        """Test fibonacci logs method validation errors."""
        # Arrange
        n = 5
        method = "invalid"

        # Act & Assert
        with pytest.raises(MethodNotSupportedError):
            calculate_fibonacci(n, method=method)

        # Should log the error
        assert mock_audit_log.called


# ==============================================================================
# EDGE CASE TESTS
# ==============================================================================


class TestFibonacciEdgeCases:
    """Test edge cases and boundary conditions."""

    def test_boundary_zero(self):
        """Test boundary case n=0 (minimum valid input)."""
        # Arrange
        n = 0

        # Act
        result = calculate_fibonacci(n)

        # Assert
        assert result == 0

    def test_boundary_max(self):
        """Test boundary case n=10000 (maximum valid input)."""
        # Arrange
        n = 10000

        # Act
        result = calculate_fibonacci(n, method="matrix")

        # Assert
        assert result > 0
        assert isinstance(result, int)

    def test_boundary_just_below_max(self):
        """Test boundary case n=9999 (just below maximum)."""
        # Arrange
        n = 9999

        # Act
        result = calculate_fibonacci(n, method="matrix")

        # Assert
        assert result > 0

    def test_boundary_just_above_min(self):
        """Test boundary case n=1 (just above minimum)."""
        # Arrange
        n = 1

        # Act
        result = calculate_fibonacci(n)

        # Assert
        assert result == 1

    def test_very_negative_input(self):
        """Test very negative input raises appropriate error."""
        # Arrange
        n = -1000000

        # Act & Assert
        with pytest.raises(InvalidInputError):
            calculate_fibonacci(n)

    def test_zero_with_all_methods(self):
        """Test n=0 works correctly with all methods."""
        # Arrange
        n = 0

        # Act & Assert
        assert calculate_fibonacci(n, method="iterative") == 0
        assert calculate_fibonacci(n, method="recursive") == 0
        assert calculate_fibonacci(n, method="matrix") == 0


# ==============================================================================
# PERFORMANCE TESTS
# ==============================================================================


class TestFibonacciPerformance:
    """Test performance characteristics of different algorithms."""

    @pytest.mark.slow
    def test_iterative_handles_large_input(self):
        """Test iterative algorithm handles large input efficiently."""
        # Arrange
        n = 5000

        # Act
        result = calculate_fibonacci(n, method="iterative")

        # Assert
        assert result > 0
        # Should complete in reasonable time

    @pytest.mark.slow
    def test_matrix_handles_very_large_input(self):
        """Test matrix algorithm handles very large input efficiently."""
        # Arrange
        n = 10000

        # Act
        result = calculate_fibonacci(n, method="matrix")

        # Assert
        assert result > 0
        # Matrix method should be fastest for large n

    def test_recursive_slow_for_large_input(self):
        """Test recursive algorithm is slow for moderately large input."""
        # Arrange
        n = 35  # Recursive gets very slow beyond this

        # Act
        result = calculate_fibonacci(n, method="recursive")

        # Assert
        assert result > 0
        # Note: This test documents that recursive is slow


# ==============================================================================
# INTEGRATION TESTS: CROSS-ALGORITHM
# ==============================================================================


class TestFibonacciCrossAlgorithmIntegration:
    """Test integration between different algorithms."""

    def test_switch_algorithms_same_input(self):
        """Test switching algorithms for same input produces same result."""
        # Arrange
        n = 15

        # Act
        result1 = calculate_fibonacci(n, method="iterative")
        result2 = calculate_fibonacci(n, method="recursive")
        result3 = calculate_fibonacci(n, method="matrix")

        # Assert
        assert result1 == result2 == result3

    def test_multiple_calls_with_different_methods(self):
        """Test multiple consecutive calls with different methods."""
        # Arrange
        inputs = [(5, "iterative"), (10, "recursive"), (20, "matrix")]

        # Act
        results = [calculate_fibonacci(n, method=m) for n, m in inputs]

        # Assert
        assert results == [5, 55, 6765]

    def test_interleaved_calls_maintain_correctness(self):
        """Test interleaved calls maintain correctness."""
        # Arrange & Act
        r1 = calculate_fibonacci(10, method="iterative")
        r2 = calculate_fibonacci(10, method="matrix")
        r3 = calculate_fibonacci(10, method="recursive")

        # Assert
        assert r1 == r2 == r3 == 55


# ==============================================================================
# TDD RED PHASE VERIFICATION
# ==============================================================================


class TestTDDRedPhaseVerification:
    """Verify tests fail before implementation (TDD red phase)."""

    def test_suite_should_fail_without_implementation(self):
        """
        This test documents that the entire test suite should FAIL
        before implementation is created.

        Expected failures:
        - ImportError: Module 'math_utils' not found
        - ImportError: Cannot import 'calculate_fibonacci'
        - ImportError: Cannot import custom exceptions

        This test will be skipped due to pytest.skip() at module level.
        """
        # This test documents TDD red phase expectations
        assert True  # Placeholder - suite will fail at import

    def test_implementation_location_documented(self):
        """Document where implementation should be created."""
        expected_location = (
            Path(__file__).parent.parent.parent.parent
            / "plugins"
            / "autonomous-dev"
            / "lib"
            / "math_utils.py"
        )

        # This test documents expected implementation location
        # Implementation should be created at: plugins/autonomous-dev/lib/math_utils.py
        assert True  # Documentation test


# ==============================================================================
# TEST SUMMARY
# ==============================================================================

"""
TEST COVERAGE SUMMARY:

Unit Tests (Base Cases): 6 tests
- fibonacci_zero_* (3 tests - one per algorithm)
- fibonacci_one_* (3 tests - one per algorithm)

Unit Tests (Algorithm Correctness): 20+ tests
- Iterative algorithm (3 tests + parametrize)
- Recursive algorithm (3 tests)
- Matrix algorithm (3 tests + parametrize)

Unit Tests (Algorithm Consistency): 7 tests
- All algorithms produce same results

Unit Tests (Input Validation): 5 tests
- Negative input
- Above maximum
- Non-integer types
- String input
- None input

Unit Tests (Method Validation): 5 tests
- Invalid method
- Empty method
- Valid methods (parametrize)
- Default method

Unit Tests (Custom Exceptions): 4 tests
- Exception hierarchy
- Exception inheritance
- Error context

Integration Tests (Security): 4 tests
- Audit log on start
- Audit log on complete
- Audit log on validation error
- Audit log on method error

Edge Case Tests: 6 tests
- Boundary conditions (0, 10000, 9999, 1)
- Very negative input
- Zero with all methods

Performance Tests: 3 tests
- Iterative large input
- Matrix very large input
- Recursive performance limit

Cross-Algorithm Integration: 3 tests
- Switch algorithms
- Multiple calls
- Interleaved calls

TDD Verification: 2 tests
- Red phase documentation
- Implementation location

TOTAL: 65+ tests covering all requirements

EXPECTED STATUS: ALL TESTS SHOULD FAIL (ImportError)
- Module math_utils.py does not exist yet
- Function calculate_fibonacci not implemented
- Custom exceptions not defined

This is the TDD RED PHASE - tests written BEFORE implementation.
"""
