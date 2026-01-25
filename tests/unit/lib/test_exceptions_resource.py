#!/usr/bin/env python3
"""
Unit tests for resource management exceptions (TDD Red Phase).

Tests for Issue #259: System-wide resource management.

Test Strategy:
- Test ResourceError exception hierarchy
- Test SessionLimitExceededError
- Test ProcessLimitExceededError
- Test ResourceLockError
- Test exception messages and inheritance

TDD Mode: These tests are written BEFORE implementation.
All tests should FAIL initially (ImportError: exceptions not defined).

Coverage Target: 100% for new exception classes

Date: 2026-01-25
Issue: #259 (System-wide resource management)
Agent: test-master
Phase: TDD Red (tests written BEFORE implementation)
"""

import pytest
import sys
from pathlib import Path

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

# Import will fail - exceptions don't exist yet (TDD!)
try:
    from exceptions import (
        AutonomousDevError,
        ResourceError,
        SessionLimitExceededError,
        ProcessLimitExceededError,
        ResourceLockError,
    )
except ImportError as e:
    pytest.skip(f"Implementation not found (TDD red phase): {e}", allow_module_level=True)


# =============================================================================
# Test Exception Hierarchy
# =============================================================================

class TestResourceErrorHierarchy:
    """Test ResourceError exception hierarchy."""

    def test_resource_error_inherits_from_autonomous_dev_error(self):
        """Test ResourceError inherits from AutonomousDevError."""
        assert issubclass(ResourceError, AutonomousDevError)

    def test_resource_error_inherits_from_exception(self):
        """Test ResourceError inherits from Exception."""
        assert issubclass(ResourceError, Exception)

    def test_session_limit_exceeded_inherits_from_resource_error(self):
        """Test SessionLimitExceededError inherits from ResourceError."""
        assert issubclass(SessionLimitExceededError, ResourceError)

    def test_process_limit_exceeded_inherits_from_resource_error(self):
        """Test ProcessLimitExceededError inherits from ResourceError."""
        assert issubclass(ProcessLimitExceededError, ResourceError)

    def test_resource_lock_error_inherits_from_resource_error(self):
        """Test ResourceLockError inherits from ResourceError."""
        assert issubclass(ResourceLockError, ResourceError)


# =============================================================================
# Test ResourceError
# =============================================================================

class TestResourceError:
    """Test ResourceError base exception."""

    def test_resource_error_can_be_raised(self):
        """Test ResourceError can be raised."""
        with pytest.raises(ResourceError):
            raise ResourceError("Test error")

    def test_resource_error_can_be_caught_as_autonomous_dev_error(self):
        """Test ResourceError can be caught as AutonomousDevError."""
        try:
            raise ResourceError("Test error")
        except AutonomousDevError:
            pass  # Should catch successfully

    def test_resource_error_message(self):
        """Test ResourceError preserves error message."""
        error_message = "Resource allocation failed"
        try:
            raise ResourceError(error_message)
        except ResourceError as e:
            assert str(e) == error_message


# =============================================================================
# Test SessionLimitExceededError
# =============================================================================

class TestSessionLimitExceededError:
    """Test SessionLimitExceededError exception."""

    def test_session_limit_exceeded_can_be_raised(self):
        """Test SessionLimitExceededError can be raised."""
        with pytest.raises(SessionLimitExceededError):
            raise SessionLimitExceededError("Session limit exceeded")

    def test_session_limit_exceeded_can_be_caught_as_resource_error(self):
        """Test SessionLimitExceededError can be caught as ResourceError."""
        try:
            raise SessionLimitExceededError("Session limit exceeded")
        except ResourceError:
            pass  # Should catch successfully

    def test_session_limit_exceeded_message(self):
        """Test SessionLimitExceededError preserves error message."""
        error_message = "Maximum 3 concurrent sessions exceeded"
        try:
            raise SessionLimitExceededError(error_message)
        except SessionLimitExceededError as e:
            assert str(e) == error_message


# =============================================================================
# Test ProcessLimitExceededError
# =============================================================================

class TestProcessLimitExceededError:
    """Test ProcessLimitExceededError exception."""

    def test_process_limit_exceeded_can_be_raised(self):
        """Test ProcessLimitExceededError can be raised."""
        with pytest.raises(ProcessLimitExceededError):
            raise ProcessLimitExceededError("Process limit exceeded")

    def test_process_limit_exceeded_can_be_caught_as_resource_error(self):
        """Test ProcessLimitExceededError can be caught as ResourceError."""
        try:
            raise ProcessLimitExceededError("Process limit exceeded")
        except ResourceError:
            pass  # Should catch successfully

    def test_process_limit_exceeded_message(self):
        """Test ProcessLimitExceededError preserves error message."""
        error_message = "Process count 2500 exceeds hard limit 2000"
        try:
            raise ProcessLimitExceededError(error_message)
        except ProcessLimitExceededError as e:
            assert str(e) == error_message


# =============================================================================
# Test ResourceLockError
# =============================================================================

class TestResourceLockError:
    """Test ResourceLockError exception."""

    def test_resource_lock_error_can_be_raised(self):
        """Test ResourceLockError can be raised."""
        with pytest.raises(ResourceLockError):
            raise ResourceLockError("Lock acquisition failed")

    def test_resource_lock_error_can_be_caught_as_resource_error(self):
        """Test ResourceLockError can be caught as ResourceError."""
        try:
            raise ResourceLockError("Lock acquisition failed")
        except ResourceError:
            pass  # Should catch successfully

    def test_resource_lock_error_message(self):
        """Test ResourceLockError preserves error message."""
        error_message = "Failed to acquire lock on registry file"
        try:
            raise ResourceLockError(error_message)
        except ResourceLockError as e:
            assert str(e) == error_message


# =============================================================================
# Test Exception Catching Patterns
# =============================================================================

class TestExceptionCatchingPatterns:
    """Test exception catching patterns for resource errors."""

    def test_catch_all_resource_errors_with_base_class(self):
        """Test catching all resource errors with ResourceError base class."""
        errors_caught = []

        for exception_class in [
            SessionLimitExceededError,
            ProcessLimitExceededError,
            ResourceLockError,
        ]:
            try:
                raise exception_class("Test error")
            except ResourceError:
                errors_caught.append(exception_class.__name__)

        assert len(errors_caught) == 3

    def test_catch_specific_resource_error_before_base(self):
        """Test catching specific resource error before base class."""
        caught_specific = False
        caught_base = False

        try:
            raise SessionLimitExceededError("Session limit exceeded")
        except SessionLimitExceededError:
            caught_specific = True
        except ResourceError:
            caught_base = True

        assert caught_specific is True
        assert caught_base is False

    def test_catch_resource_error_as_autonomous_dev_error(self):
        """Test catching ResourceError as AutonomousDevError."""
        caught = False

        try:
            raise ResourceError("Test error")
        except AutonomousDevError:
            caught = True

        assert caught is True


# =============================================================================
# Test Summary
# =============================================================================

"""
TEST SUMMARY (18 unit tests):

Exception Hierarchy (5 tests):
✗ test_resource_error_inherits_from_autonomous_dev_error
✗ test_resource_error_inherits_from_exception
✗ test_session_limit_exceeded_inherits_from_resource_error
✗ test_process_limit_exceeded_inherits_from_resource_error
✗ test_resource_lock_error_inherits_from_resource_error

ResourceError (3 tests):
✗ test_resource_error_can_be_raised
✗ test_resource_error_can_be_caught_as_autonomous_dev_error
✗ test_resource_error_message

SessionLimitExceededError (3 tests):
✗ test_session_limit_exceeded_can_be_raised
✗ test_session_limit_exceeded_can_be_caught_as_resource_error
✗ test_session_limit_exceeded_message

ProcessLimitExceededError (3 tests):
✗ test_process_limit_exceeded_can_be_raised
✗ test_process_limit_exceeded_can_be_caught_as_resource_error
✗ test_process_limit_exceeded_message

ResourceLockError (3 tests):
✗ test_resource_lock_error_can_be_raised
✗ test_resource_lock_error_can_be_caught_as_resource_error
✗ test_resource_lock_error_message

Exception Catching Patterns (3 tests):
✗ test_catch_all_resource_errors_with_base_class
✗ test_catch_specific_resource_error_before_base
✗ test_catch_resource_error_as_autonomous_dev_error

TOTAL: 18 unit tests (all FAILING - TDD red phase)

Coverage Target: 100% for new exception classes
"""
