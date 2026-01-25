#!/usr/bin/env python3
"""
Centralized Exception Hierarchy for autonomous-dev plugin.

This module provides a unified exception hierarchy for all plugin operations.
Exceptions are organized in a 3-level hierarchy:
  Base -> Category -> Specific

Hierarchy:
    Exception
    └── AutonomousDevError (base for all plugin exceptions)
        ├── StateError (state management errors)
        └── APIError (category for API-related errors)
            └── GitHubAPIError (GitHub-specific API errors)
                ├── IssueNotFoundError (GitHub issue not found - 404)
                └── IssueAlreadyClosedError (GitHub issue already closed)

Usage:
    from exceptions import GitHubAPIError, IssueNotFoundError

    try:
        close_issue(issue_number)
    except IssueNotFoundError:
        print(f"Issue {issue_number} not found")
    except GitHubAPIError as e:
        print(f"GitHub API error: {e}")

Issue: #219 (Centralize 41+ exceptions into exceptions.py)
Date: 2026-01-09
"""


class AutonomousDevError(Exception):
    """Base exception for all autonomous-dev plugin errors.

    All plugin-specific exceptions should inherit from this class
    to enable broad exception catching when needed.
    """
    pass


class StateError(AutonomousDevError):
    """Base exception for state management errors.

    Raised when state operations fail (load, save, cleanup, validation).
    All state managers should raise this or subclasses for state-related errors.

    Issue: #220 (Extract StateManager ABC from 4 state managers)
    """
    pass


class APIError(AutonomousDevError):
    """Base exception for API-related errors.

    Inherit from this for errors related to external API calls
    (GitHub, Slack, etc.).
    """
    pass


class GitHubAPIError(APIError):
    """Exception for GitHub API errors.

    Raised when GitHub API operations fail (network errors,
    authentication issues, rate limiting, etc.).
    """
    pass


class IssueNotFoundError(GitHubAPIError):
    """Exception raised when a GitHub issue is not found.

    Raised when attempting to access a GitHub issue that doesn't
    exist (HTTP 404).
    """
    pass


class IssueAlreadyClosedError(GitHubAPIError):
    """Exception raised when trying to close an already closed issue.

    Raised when attempting to close a GitHub issue that is already
    in the closed state.
    """
    pass


class ResourceError(AutonomousDevError):
    """Base exception for resource management errors.

    Raised when resource allocation, tracking, or limit enforcement fails.
    All resource-related errors should inherit from this class.

    Issue: #259 (System-wide resource management)
    """
    pass


class SessionLimitExceededError(ResourceError):
    """Exception raised when max sessions already active.

    Raised when attempting to create a new session but the maximum
    number of concurrent sessions is already active.
    """
    pass


class ProcessLimitExceededError(ResourceError):
    """Exception raised when system process count exceeds hard limit.

    Raised when system process count exceeds the configured hard limit,
    preventing new operations from starting.
    """
    pass


class ResourceLockError(ResourceError):
    """Exception raised when lockfile operations fail.

    Raised when file locking operations fail (lock acquisition,
    lock release, corrupted lockfile, etc.).
    """
    pass
