#!/usr/bin/env python3
"""
Unit tests for failure_classifier module (TDD Red Phase - Issue #89).

Tests for classifying /auto-implement failures as transient vs permanent.

TDD Mode: These tests are written BEFORE implementation.
All tests should FAIL initially (ImportError: module not found).

Test Strategy:
- Test transient error classification (network, timeout, API rate limit)
- Test permanent error classification (syntax, import, type errors)
- Test unknown error classification (default to permanent for safety)
- Test error message sanitization (log injection prevention)
- Test error context extraction (feature name, timestamp, stack trace)

Security:
- CWE-117: Log injection prevention via sanitization
- Error messages sanitized before logging

Coverage Target: 95%+ for failure_classifier.py

Date: 2025-11-18
Issue: #89 (Automatic Failure Recovery for /batch-implement)
Agent: test-master
Phase: TDD Red (tests written BEFORE implementation)
Status: RED (all tests failing - module doesn't exist yet)
"""

import sys
import pytest
from pathlib import Path
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

# Import will fail - module doesn't exist yet (TDD!)
try:
    from failure_classifier import (
        classify_failure,
        is_transient_error,
        is_permanent_error,
        sanitize_error_message,
        extract_error_context,
        FailureType,
        TRANSIENT_ERROR_PATTERNS,
        PERMANENT_ERROR_PATTERNS,
    )
except ImportError as e:
    pytest.skip(f"Implementation not found (TDD red phase): {e}", allow_module_level=True)


# =============================================================================
# Test Fixtures
# =============================================================================

@pytest.fixture
def network_error():
    """Sample network error message."""
    return "ConnectionError: Failed to connect to Claude API at https://api.anthropic.com"


@pytest.fixture
def timeout_error():
    """Sample timeout error message."""
    return "TimeoutError: Request timed out after 30 seconds"


@pytest.fixture
def rate_limit_error():
    """Sample API rate limit error."""
    return "RateLimitError: API rate limit exceeded. Retry after 60 seconds."


@pytest.fixture
def syntax_error():
    """Sample syntax error message."""
    return "SyntaxError: invalid syntax in file test.py line 42"


@pytest.fixture
def import_error():
    """Sample import error message."""
    return "ImportError: cannot import name 'NonExistentModule' from 'mypackage'"


@pytest.fixture
def type_error():
    """Sample type error message."""
    return "TypeError: unsupported operand type(s) for +: 'int' and 'str'"


@pytest.fixture
def unknown_error():
    """Sample unknown error message."""
    return "WeirdUnexpectedError: Something really unexpected happened"


# =============================================================================
# SECTION 1: Transient Error Classification Tests (5 tests)
# =============================================================================

class TestTransientErrorClassification:
    """Test classification of transient (retriable) errors."""

    def test_classify_network_error_as_transient(self, network_error):
        """Test that network errors are classified as transient."""
        # Arrange & Act
        result = classify_failure(network_error)

        # Assert
        assert result == FailureType.TRANSIENT
        assert is_transient_error(network_error) is True
        assert is_permanent_error(network_error) is False

    def test_classify_timeout_error_as_transient(self, timeout_error):
        """Test that timeout errors are classified as transient."""
        # Arrange & Act
        result = classify_failure(timeout_error)

        # Assert
        assert result == FailureType.TRANSIENT
        assert is_transient_error(timeout_error) is True
        assert is_permanent_error(timeout_error) is False

    def test_classify_rate_limit_error_as_transient(self, rate_limit_error):
        """Test that API rate limit errors are classified as transient."""
        # Arrange & Act
        result = classify_failure(rate_limit_error)

        # Assert
        assert result == FailureType.TRANSIENT
        assert is_transient_error(rate_limit_error) is True
        assert is_permanent_error(rate_limit_error) is False

    def test_transient_patterns_case_insensitive(self):
        """Test that transient error detection is case-insensitive."""
        # Arrange
        error_variations = [
            "ConnectionError: failed to connect",
            "connectionerror: FAILED TO CONNECT",
            "CONNECTIONError: Failed To Connect",
        ]

        # Act & Assert
        for error in error_variations:
            assert is_transient_error(error) is True

    def test_transient_error_patterns_comprehensive(self):
        """Test that all common transient errors are detected."""
        # Arrange
        transient_errors = [
            "ConnectionError: Connection refused",
            "TimeoutError: Operation timed out",
            "RateLimitError: Too many requests",
            "NetworkError: Network unreachable",
            "HTTPError: 503 Service Unavailable",
            "HTTPError: 502 Bad Gateway",
            "HTTPError: 504 Gateway Timeout",
            "TemporaryFailure: Service temporarily unavailable",
        ]

        # Act & Assert
        for error in transient_errors:
            result = classify_failure(error)
            assert result == FailureType.TRANSIENT, f"Expected TRANSIENT for: {error}"


# =============================================================================
# SECTION 2: Permanent Error Classification Tests (5 tests)
# =============================================================================

class TestPermanentErrorClassification:
    """Test classification of permanent (non-retriable) errors."""

    def test_classify_syntax_error_as_permanent(self, syntax_error):
        """Test that syntax errors are classified as permanent."""
        # Arrange & Act
        result = classify_failure(syntax_error)

        # Assert
        assert result == FailureType.PERMANENT
        assert is_permanent_error(syntax_error) is True
        assert is_transient_error(syntax_error) is False

    def test_classify_import_error_as_permanent(self, import_error):
        """Test that import errors are classified as permanent."""
        # Arrange & Act
        result = classify_failure(import_error)

        # Assert
        assert result == FailureType.PERMANENT
        assert is_permanent_error(import_error) is True
        assert is_transient_error(import_error) is False

    def test_classify_type_error_as_permanent(self, type_error):
        """Test that type errors are classified as permanent."""
        # Arrange & Act
        result = classify_failure(type_error)

        # Assert
        assert result == FailureType.PERMANENT
        assert is_permanent_error(type_error) is True
        assert is_transient_error(type_error) is False

    def test_permanent_patterns_case_insensitive(self):
        """Test that permanent error detection is case-insensitive."""
        # Arrange
        error_variations = [
            "SyntaxError: invalid syntax",
            "syntaxerror: INVALID SYNTAX",
            "SYNTAXError: Invalid Syntax",
        ]

        # Act & Assert
        for error in error_variations:
            assert is_permanent_error(error) is True

    def test_permanent_error_patterns_comprehensive(self):
        """Test that all common permanent errors are detected."""
        # Arrange
        permanent_errors = [
            "SyntaxError: invalid syntax",
            "ImportError: No module named 'foo'",
            "TypeError: unsupported operand type",
            "NameError: name 'x' is not defined",
            "AttributeError: 'NoneType' has no attribute 'foo'",
            "ValueError: invalid literal for int()",
            "IndentationError: unexpected indent",
            "KeyError: 'missing_key'",
            "IndexError: list index out of range",
            "AssertionError: test failed",
        ]

        # Act & Assert
        for error in permanent_errors:
            result = classify_failure(error)
            assert result == FailureType.PERMANENT, f"Expected PERMANENT for: {error}"


# =============================================================================
# SECTION 3: Unknown Error Classification Tests (3 tests)
# =============================================================================

class TestUnknownErrorClassification:
    """Test classification of unknown errors (default to permanent for safety)."""

    def test_classify_unknown_error_as_permanent(self, unknown_error):
        """Test that unknown errors default to permanent (safe default)."""
        # Arrange & Act
        result = classify_failure(unknown_error)

        # Assert - default to permanent for safety (don't retry unknown errors)
        assert result == FailureType.PERMANENT

    def test_classify_empty_error_message_as_permanent(self):
        """Test that empty error messages default to permanent."""
        # Arrange
        empty_error = ""

        # Act
        result = classify_failure(empty_error)

        # Assert
        assert result == FailureType.PERMANENT

    def test_classify_none_error_message_as_permanent(self):
        """Test that None error messages default to permanent."""
        # Arrange
        none_error = None

        # Act
        result = classify_failure(none_error)

        # Assert
        assert result == FailureType.PERMANENT


# =============================================================================
# SECTION 4: Error Message Sanitization Tests (4 tests)
# =============================================================================

class TestErrorMessageSanitization:
    """Test error message sanitization for log injection prevention (CWE-117)."""

    def test_sanitize_removes_newlines(self):
        """Test that sanitization removes newlines to prevent log injection."""
        # Arrange
        malicious_error = "Error\nFAKE LOG: Admin access granted\nReal error continues"

        # Act
        sanitized = sanitize_error_message(malicious_error)

        # Assert
        assert "\n" not in sanitized
        assert "FAKE LOG" in sanitized  # Content preserved, just no newlines

    def test_sanitize_removes_carriage_returns(self):
        """Test that sanitization removes carriage returns."""
        # Arrange
        malicious_error = "Error\rFAKE LOG: Security disabled\rReal error"

        # Act
        sanitized = sanitize_error_message(malicious_error)

        # Assert
        assert "\r" not in sanitized

    def test_sanitize_truncates_long_messages(self):
        """Test that sanitization truncates excessively long error messages."""
        # Arrange
        long_error = "Error: " + ("X" * 10000)

        # Act
        sanitized = sanitize_error_message(long_error)

        # Assert
        assert len(sanitized) <= 1000  # Reasonable max length
        assert sanitized.endswith("...") or sanitized.endswith("[truncated]")

    def test_sanitize_preserves_safe_error_messages(self):
        """Test that sanitization preserves normal safe error messages."""
        # Arrange
        safe_error = "ConnectionError: Failed to connect to API"

        # Act
        sanitized = sanitize_error_message(safe_error)

        # Assert
        assert sanitized == safe_error  # No changes needed


# =============================================================================
# SECTION 5: Error Context Extraction Tests (5 tests)
# =============================================================================

class TestErrorContextExtraction:
    """Test extraction of error context for debugging."""

    def test_extract_context_includes_error_type(self, syntax_error):
        """Test that context extraction identifies error type."""
        # Arrange
        feature_name = "Add user authentication"

        # Act
        context = extract_error_context(syntax_error, feature_name)

        # Assert
        assert "error_type" in context
        assert "SyntaxError" in context["error_type"]

    def test_extract_context_includes_feature_name(self, syntax_error):
        """Test that context includes the feature being processed."""
        # Arrange
        feature_name = "Add user authentication"

        # Act
        context = extract_error_context(syntax_error, feature_name)

        # Assert
        assert "feature_name" in context
        assert context["feature_name"] == feature_name

    def test_extract_context_includes_timestamp(self, syntax_error):
        """Test that context includes timestamp of failure."""
        # Arrange
        feature_name = "Add user authentication"

        # Act
        context = extract_error_context(syntax_error, feature_name)

        # Assert
        assert "timestamp" in context
        assert context["timestamp"] is not None

    def test_extract_context_includes_sanitized_message(self, syntax_error):
        """Test that context includes sanitized error message."""
        # Arrange
        feature_name = "Add user authentication"
        malicious_error = "SyntaxError\nFAKE LOG: Malicious injection"

        # Act
        context = extract_error_context(malicious_error, feature_name)

        # Assert
        assert "error_message" in context
        assert "\n" not in context["error_message"]

    def test_extract_context_includes_classification(self, syntax_error):
        """Test that context includes failure classification."""
        # Arrange
        feature_name = "Add user authentication"

        # Act
        context = extract_error_context(syntax_error, feature_name)

        # Assert
        assert "failure_type" in context
        assert context["failure_type"] in ["transient", "permanent"]


# =============================================================================
# Test Summary
# =============================================================================

"""
TEST SUMMARY (22 unit tests for failure_classifier.py):

SECTION 1: Transient Error Classification (5 tests)
✗ test_classify_network_error_as_transient
✗ test_classify_timeout_error_as_transient
✗ test_classify_rate_limit_error_as_transient
✗ test_transient_patterns_case_insensitive
✗ test_transient_error_patterns_comprehensive

SECTION 2: Permanent Error Classification (5 tests)
✗ test_classify_syntax_error_as_permanent
✗ test_classify_import_error_as_permanent
✗ test_classify_type_error_as_permanent
✗ test_permanent_patterns_case_insensitive
✗ test_permanent_error_patterns_comprehensive

SECTION 3: Unknown Error Classification (3 tests)
✗ test_classify_unknown_error_as_permanent
✗ test_classify_empty_error_message_as_permanent
✗ test_classify_none_error_message_as_permanent

SECTION 4: Error Message Sanitization (4 tests)
✗ test_sanitize_removes_newlines
✗ test_sanitize_removes_carriage_returns
✗ test_sanitize_truncates_long_messages
✗ test_sanitize_preserves_safe_error_messages

SECTION 5: Error Context Extraction (5 tests)
✗ test_extract_context_includes_error_type
✗ test_extract_context_includes_feature_name
✗ test_extract_context_includes_timestamp
✗ test_extract_context_includes_sanitized_message
✗ test_extract_context_includes_classification

TOTAL: 22 unit tests (all FAILING - TDD red phase)

Security Coverage:
- CWE-117: Log injection prevention via sanitization
- Newline/carriage return removal
- Message length limits
- Safe error message handling

Implementation Guidance:
- Use regex patterns for error classification
- Default to permanent for safety (don't retry unknown errors)
- Sanitize before logging (prevent log injection)
- Extract rich context for debugging
- Case-insensitive pattern matching
"""
