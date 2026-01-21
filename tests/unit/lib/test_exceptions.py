#!/usr/bin/env python3
"""
Unit tests for centralized exception hierarchy.

Tests the exception classes in plugins/autonomous-dev/lib/exceptions.py
ensuring proper inheritance and behavior.

Issue: #234 (Test coverage improvement)
"""

import pytest
import sys
from pathlib import Path

# Add lib to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent / "plugins/autonomous-dev/lib"))

from exceptions import (
    AutonomousDevError,
    StateError,
    APIError,
    GitHubAPIError,
    IssueNotFoundError,
    IssueAlreadyClosedError,
)


class TestExceptionHierarchy:
    """Test exception class hierarchy."""

    def test_autonomous_dev_error_is_base_exception(self):
        """AutonomousDevError should inherit from Exception."""
        assert issubclass(AutonomousDevError, Exception)

    def test_state_error_inherits_from_base(self):
        """StateError should inherit from AutonomousDevError."""
        assert issubclass(StateError, AutonomousDevError)
        assert issubclass(StateError, Exception)

    def test_api_error_inherits_from_base(self):
        """APIError should inherit from AutonomousDevError."""
        assert issubclass(APIError, AutonomousDevError)
        assert issubclass(APIError, Exception)

    def test_github_api_error_inherits_from_api_error(self):
        """GitHubAPIError should inherit from APIError."""
        assert issubclass(GitHubAPIError, APIError)
        assert issubclass(GitHubAPIError, AutonomousDevError)

    def test_issue_not_found_error_inherits_from_github_api_error(self):
        """IssueNotFoundError should inherit from GitHubAPIError."""
        assert issubclass(IssueNotFoundError, GitHubAPIError)
        assert issubclass(IssueNotFoundError, APIError)
        assert issubclass(IssueNotFoundError, AutonomousDevError)

    def test_issue_already_closed_error_inherits_from_github_api_error(self):
        """IssueAlreadyClosedError should inherit from GitHubAPIError."""
        assert issubclass(IssueAlreadyClosedError, GitHubAPIError)
        assert issubclass(IssueAlreadyClosedError, APIError)
        assert issubclass(IssueAlreadyClosedError, AutonomousDevError)


class TestExceptionRaising:
    """Test that exceptions can be raised and caught properly."""

    def test_raise_autonomous_dev_error(self):
        """Should be able to raise and catch AutonomousDevError."""
        with pytest.raises(AutonomousDevError) as exc_info:
            raise AutonomousDevError("test error")
        assert str(exc_info.value) == "test error"

    def test_raise_state_error(self):
        """Should be able to raise and catch StateError."""
        with pytest.raises(StateError) as exc_info:
            raise StateError("state error")
        assert str(exc_info.value) == "state error"

    def test_raise_api_error(self):
        """Should be able to raise and catch APIError."""
        with pytest.raises(APIError) as exc_info:
            raise APIError("api error")
        assert str(exc_info.value) == "api error"

    def test_raise_github_api_error(self):
        """Should be able to raise and catch GitHubAPIError."""
        with pytest.raises(GitHubAPIError) as exc_info:
            raise GitHubAPIError("github error")
        assert str(exc_info.value) == "github error"

    def test_raise_issue_not_found_error(self):
        """Should be able to raise and catch IssueNotFoundError."""
        with pytest.raises(IssueNotFoundError) as exc_info:
            raise IssueNotFoundError("Issue #123 not found")
        assert "Issue #123" in str(exc_info.value)

    def test_raise_issue_already_closed_error(self):
        """Should be able to raise and catch IssueAlreadyClosedError."""
        with pytest.raises(IssueAlreadyClosedError) as exc_info:
            raise IssueAlreadyClosedError("Issue #456 already closed")
        assert "Issue #456" in str(exc_info.value)


class TestExceptionCatching:
    """Test catching exceptions at different hierarchy levels."""

    def test_catch_github_error_with_api_error(self):
        """GitHubAPIError should be catchable as APIError."""
        with pytest.raises(APIError):
            raise GitHubAPIError("github error")

    def test_catch_github_error_with_base_error(self):
        """GitHubAPIError should be catchable as AutonomousDevError."""
        with pytest.raises(AutonomousDevError):
            raise GitHubAPIError("github error")

    def test_catch_issue_not_found_with_github_error(self):
        """IssueNotFoundError should be catchable as GitHubAPIError."""
        with pytest.raises(GitHubAPIError):
            raise IssueNotFoundError("not found")

    def test_catch_issue_not_found_with_api_error(self):
        """IssueNotFoundError should be catchable as APIError."""
        with pytest.raises(APIError):
            raise IssueNotFoundError("not found")

    def test_catch_state_error_with_base_error(self):
        """StateError should be catchable as AutonomousDevError."""
        with pytest.raises(AutonomousDevError):
            raise StateError("state error")

    def test_state_error_not_api_error(self):
        """StateError should NOT be catchable as APIError."""
        with pytest.raises(StateError):
            try:
                raise StateError("state error")
            except APIError:
                pytest.fail("StateError should not be caught as APIError")
            raise  # Re-raise for outer pytest.raises

    def test_api_error_not_state_error(self):
        """APIError should NOT be catchable as StateError."""
        with pytest.raises(APIError):
            try:
                raise APIError("api error")
            except StateError:
                pytest.fail("APIError should not be caught as StateError")
            raise  # Re-raise for outer pytest.raises


class TestExceptionMessages:
    """Test exception message handling."""

    def test_exception_with_empty_message(self):
        """Exceptions should work with empty messages."""
        exc = AutonomousDevError()
        assert str(exc) == ""

    def test_exception_with_multiline_message(self):
        """Exceptions should preserve multiline messages."""
        message = "Line 1\nLine 2\nLine 3"
        exc = GitHubAPIError(message)
        assert str(exc) == message

    def test_exception_with_unicode_message(self):
        """Exceptions should handle unicode characters."""
        message = "Error: 文件未找到 🔍"
        exc = IssueNotFoundError(message)
        assert str(exc) == message


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
