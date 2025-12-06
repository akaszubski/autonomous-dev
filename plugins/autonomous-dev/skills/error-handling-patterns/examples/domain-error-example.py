#!/usr/bin/env python3
"""
Domain-Specific Error Classes Example

This example demonstrates domain-specific error classes that inherit from the
base AutonomousDevError class. Each domain (Security, Validation, Git, Agent)
has its own base error, with specific errors inheriting from the domain base.

See error-handling-patterns skill for complete exception hierarchy and usage.
"""

from typing import Optional


class AutonomousDevError(Exception):
    """Base exception for autonomous-dev plugin.

    See error-handling-patterns skill for exception hierarchy.
    """

    def __init__(self, message: str, context: dict = None):
        super().__init__(message)
        self.context = context or {}

    def __str__(self):
        if self.context:
            context_str = "\n".join(f"  {k}: {v}" for k, v in self.context.items())
            return f"{super().__str__()}\nContext:\n{context_str}"
        return super().__str__()


# ============================================================================
# Security Domain Errors
# ============================================================================

class SecurityError(AutonomousDevError):
    """Base exception for security-related errors.

    All security errors inherit from this to enable security-specific handling
    and audit logging.

    See error-handling-patterns skill for security error patterns.
    """
    pass


class PathTraversalError(SecurityError):
    """Path traversal attempt detected (CWE-22).

    Raised when a path validation fails due to directory traversal attempt.

    Example:
        >>> raise PathTraversalError(
        ...     "Path validation failed: /etc/passwd\\n"
        ...     "Expected: Path must be in whitelist [/plugins, /lib]\\n"
        ...     "Got: Path '/etc/passwd' outside whitelist\\n"
        ...     "See: docs/SECURITY.md#path-validation"
        ... )
    """
    pass


class InvalidPathError(SecurityError):
    """Invalid path format or link resolution (CWE-59).

    Raised when a path has invalid format or resolves to unexpected location.

    Example:
        >>> raise InvalidPathError(
        ...     "Path validation failed: ../../../../etc/passwd\\n"
        ...     "Expected: Relative path within project root\\n"
        ...     "Got: Path escapes project boundary\\n"
        ...     "See: docs/SECURITY.md#path-validation"
        ... )
    """
    pass


class LogInjectionError(SecurityError):
    """Log injection attempt detected (CWE-117).

    Raised when unsanitized input would be logged.

    Example:
        >>> raise LogInjectionError(
        ...     "Log injection detected: input contains control characters\\n"
        ...     "Expected: Sanitized input (no newlines or control chars)\\n"
        ...     "Got: Input contains '\\n' and '\\r' characters\\n"
        ...     "See: docs/SECURITY.md#log-injection"
        ... )
    """
    pass


# ============================================================================
# Validation Domain Errors
# ============================================================================

class ValidationError(AutonomousDevError):
    """Base exception for validation failures.

    All validation errors inherit from this to enable validation-specific handling.

    See error-handling-patterns skill for validation error patterns.
    """
    pass


class InvalidFormatError(ValidationError):
    """Invalid format detected during validation.

    Raised when data doesn't match expected format.

    Example:
        >>> raise InvalidFormatError(
        ...     "Pytest output validation failed\\n"
        ...     "Expected: JSON with fields [tests_run, tests_passed, tests_failed]\\n"
        ...     "Got: Missing fields [tests_passed, tests_failed]\\n"
        ...     "See: docs/TESTING.md#pytest-format"
        ... )
    """
    pass


class ParseError(ValidationError):
    """Parsing failure during data processing.

    Raised when data cannot be parsed (JSON, YAML, etc.).

    Example:
        >>> raise ParseError(
        ...     "JSON parsing failed: Unexpected token at position 42\\n"
        ...     "Expected: Valid JSON format\\n"
        ...     "Got: Malformed JSON (missing closing brace)\\n"
        ...     "See: docs/DATA-FORMATS.md#json"
        ... )
    """
    pass


class ProjectAlignmentError(ValidationError):
    """PROJECT.md alignment validation failed.

    Raised when feature doesn't align with PROJECT.md goals/scope/constraints.

    Example:
        >>> raise ProjectAlignmentError(
        ...     "Feature alignment validation failed\\n"
        ...     "Expected: Feature must serve PROJECT.md GOALS\\n"
        ...     "Got: Feature 'automatic deployments' not in scope\\n"
        ...     "See: .claude/PROJECT.md"
        ... )
    """
    pass


# ============================================================================
# Git Domain Errors
# ============================================================================

class GitError(AutonomousDevError):
    """Base exception for Git operation failures.

    All Git errors inherit from this to enable Git-specific handling and
    graceful degradation to manual workflows.

    See error-handling-patterns skill for Git error patterns.
    """
    pass


class GitNotAvailableError(GitError):
    """Git is not installed or not in PATH.

    Raised when Git command is not available.

    Example:
        >>> raise GitNotAvailableError(
        ...     "Git operations unavailable\\n"
        ...     "Expected: Git must be installed and in PATH\\n"
        ...     "Got: Git command not found\\n"
        ...     "See: docs/SETUP.md#git-installation"
        ... )
    """
    pass


class MergeConflictError(GitError):
    """Git repository has unresolved merge conflicts.

    Raised when attempting operations with active merge conflicts.

    Example:
        >>> raise MergeConflictError(
        ...     "Git repository has merge conflicts\\n"
        ...     "Expected: Clean working directory\\n"
        ...     "Got: Unresolved conflicts in 3 files\\n"
        ...     "See: docs/GIT-WORKFLOW.md#resolving-conflicts"
        ... )
    """
    pass


class GitCredentialsError(GitError):
    """Git credentials not configured or invalid.

    Raised when Git authentication fails.

    Example:
        >>> raise GitCredentialsError(
        ...     "Git authentication failed\\n"
        ...     "Expected: Valid git credentials (user.name, user.email)\\n"
        ...     "Got: Git config missing user.email\\n"
        ...     "See: docs/GIT-SETUP.md#credentials"
        ... )
    """
    pass


# ============================================================================
# Agent Domain Errors
# ============================================================================

class AgentError(AutonomousDevError):
    """Base exception for agent invocation failures.

    All agent errors inherit from this to enable agent-specific handling.

    See error-handling-patterns skill for agent error patterns.
    """
    pass


class AgentInvocationError(AgentError):
    """Agent invocation failed.

    Raised when agent cannot be invoked or execution fails.

    Example:
        >>> raise AgentInvocationError(
        ...     "Agent invocation failed: researcher\\n"
        ...     "Expected: Agent file must exist at plugins/autonomous-dev/agents/researcher.md\\n"
        ...     "Got: File not found\\n"
        ...     "See: docs/AGENTS.md#troubleshooting"
        ... )
    """
    pass


class AgentTimeoutError(AgentError):
    """Agent execution exceeded timeout.

    Raised when agent takes too long to complete.

    Example:
        >>> raise AgentTimeoutError(
        ...     "Agent timeout: researcher exceeded 600s limit\\n"
        ...     "Expected: Agent completion within 600 seconds\\n"
        ...     "Got: Agent still running after 650 seconds\\n"
        ...     "See: docs/AGENTS.md#timeouts"
        ... )
    """
    pass


class AgentOutputError(AgentError):
    """Agent produced invalid output.

    Raised when agent output doesn't match expected format.

    Example:
        >>> raise AgentOutputError(
        ...     "Agent output validation failed: planner\\n"
        ...     "Expected: Output with sections [Feature Summary, Architecture, Implementation Plan]\\n"
        ...     "Got: Missing section 'Implementation Plan'\\n"
        ...     "See: skills/agent-output-formats/SKILL.md"
        ... )
    """
    pass


# ============================================================================
# Example Usage
# ============================================================================

if __name__ == "__main__":
    # Security error example
    try:
        raise PathTraversalError(
            "Path validation failed: /etc/passwd\n"
            "Expected: Path must be in whitelist [/plugins, /lib]\n"
            "Got: Path '/etc/passwd' outside whitelist\n"
            "See: docs/SECURITY.md#path-validation"
        )
    except SecurityError as e:
        print(f"Caught security error:\n{e}\n")

    # Validation error example
    try:
        raise ProjectAlignmentError(
            "Feature alignment validation failed\n"
            "Expected: Feature must serve PROJECT.md GOALS\n"
            "Got: Feature 'automatic deployments' not in scope\n"
            "See: .claude/PROJECT.md"
        )
    except ValidationError as e:
        print(f"Caught validation error:\n{e}\n")

    # Git error example
    try:
        raise GitNotAvailableError(
            "Git operations unavailable\n"
            "Expected: Git must be installed and in PATH\n"
            "Got: Git command not found\n"
            "See: docs/SETUP.md#git-installation"
        )
    except GitError as e:
        print(f"Caught git error:\n{e}\n")

    # Agent error example
    try:
        raise AgentOutputError(
            "Agent output validation failed: planner\n"
            "Expected: Output with sections [Feature Summary, Architecture]\n"
            "Got: Missing section 'Architecture'\n"
            "See: skills/agent-output-formats/SKILL.md"
        )
    except AgentError as e:
        print(f"Caught agent error:\n{e}\n")
