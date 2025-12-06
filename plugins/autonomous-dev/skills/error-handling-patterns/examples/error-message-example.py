#!/usr/bin/env python3
"""
Error Message Formatting Example

This example demonstrates the standardized error message format:
- Context: What failed and where
- Expected: What should have happened
- Got: What actually happened
- See: Link to documentation or solution

See error-handling-patterns skill for complete error message patterns.
"""

from typing import Optional


def format_error_message(
    context: str,
    expected: str,
    got: str,
    docs_link: Optional[str] = None
) -> str:
    """Format standardized error message.

    Args:
        context: What failed and where
        expected: What should have happened
        got: What actually happened
        docs_link: Optional documentation reference

    Returns:
        Formatted error message string

    Example:
        >>> msg = format_error_message(
        ...     context="Path validation failed in security_utils.validate_path()",
        ...     expected="Path must be in whitelist [/plugins, /lib]",
        ...     got="Path '/etc/passwd' outside whitelist",
        ...     docs_link="docs/SECURITY.md#path-validation"
        ... )
        >>> print(msg)
        Path validation failed in security_utils.validate_path()
        Expected: Path must be in whitelist [/plugins, /lib]
        Got: Path '/etc/passwd' outside whitelist
        See: docs/SECURITY.md#path-validation

    See error-handling-patterns skill for error message patterns.
    """
    message = f"{context}\nExpected: {expected}\nGot: {got}"
    if docs_link:
        message += f"\nSee: {docs_link}"
    return message


# ============================================================================
# Example Error Messages
# ============================================================================

def example_path_validation_error():
    """Example: Path validation error with CWE reference."""
    return format_error_message(
        context="Path validation failed in security_utils.validate_path_whitelist()",
        expected="Path must be in whitelist [/plugins, /lib, /agents, /skills]",
        got="Path '/etc/passwd' is outside allowed directories",
        docs_link="docs/SECURITY.md#path-validation (CWE-22 prevention)"
    )


def example_format_validation_error():
    """Example: Format validation error with specific fields."""
    return format_error_message(
        context="Pytest output validation failed in validate_pytest_output()",
        expected="JSON output must contain fields: [tests_run, tests_passed, tests_failed, duration]",
        got="Missing fields: [tests_passed, tests_failed]",
        docs_link="docs/TESTING.md#pytest-format"
    )


def example_git_operation_error():
    """Example: Git operation error with manual fallback."""
    return format_error_message(
        context="Git push operation failed in auto_implement_git_integration.push_changes()",
        expected="Git remote 'origin' must be configured and accessible",
        got="Remote 'origin' not found. Run 'git remote -v' to check configuration",
        docs_link="docs/GIT-SETUP.md#remote-configuration"
    )


def example_agent_validation_error():
    """Example: Agent validation error with workflow context."""
    return format_error_message(
        context="Feature validation failed in quality-validator agent (STEP 6)",
        expected="All 7 agents must run successfully: researcher, planner, test-master, implementer, reviewer, security-auditor, doc-master",
        got="Only 5 agents completed. Missing agents: [implementer, doc-master]. Check session logs for errors.",
        docs_link="docs/DEVELOPMENT.md#validation-checkpoints"
    )


def example_project_alignment_error():
    """Example: PROJECT.md alignment error with scope guidance."""
    return format_error_message(
        context="Feature alignment validation failed in alignment-validator agent",
        expected="Feature must serve PROJECT.md GOALS and be within SCOPE",
        got="Feature 'automatic deployment to production' is outside defined scope. PROJECT.md scope focuses on autonomous development workflows, not deployment automation.",
        docs_link=".claude/PROJECT.md (see GOALS and SCOPE sections)"
    )


def example_security_audit_error():
    """Example: Security error with CWE classification."""
    return format_error_message(
        context="Security validation failed: potential SQL injection detected in user_query parameter",
        expected="All user inputs must be parameterized or sanitized before database queries",
        got="Raw user input concatenated into SQL query string: SELECT * FROM users WHERE name = '{user_query}'",
        docs_link="docs/SECURITY.md#sql-injection (CWE-89 prevention)"
    )


def example_graceful_degradation_message():
    """Example: Graceful degradation with manual fallback."""
    return format_error_message(
        context="Git automation unavailable: GitHub CLI (gh) not installed",
        expected="GitHub CLI must be installed for automatic PR creation",
        got="Command 'gh' not found in PATH. Feature implementation succeeded, but automatic PR creation skipped.",
        docs_link="docs/GIT-AUTOMATION.md#github-cli-setup\n\nManual steps:\n1. Install gh: brew install gh\n2. Authenticate: gh auth login\n3. Create PR: gh pr create --title 'your title' --body 'description'"
    )


# ============================================================================
# Usage Examples
# ============================================================================

if __name__ == "__main__":
    print("=" * 80)
    print("ERROR MESSAGE FORMATTING EXAMPLES")
    print("=" * 80)
    print()

    print("1. Path Validation Error (CWE-22):")
    print("-" * 80)
    print(example_path_validation_error())
    print()

    print("2. Format Validation Error:")
    print("-" * 80)
    print(example_format_validation_error())
    print()

    print("3. Git Operation Error:")
    print("-" * 80)
    print(example_git_operation_error())
    print()

    print("4. Agent Validation Error:")
    print("-" * 80)
    print(example_agent_validation_error())
    print()

    print("5. PROJECT.md Alignment Error:")
    print("-" * 80)
    print(example_project_alignment_error())
    print()

    print("6. Security Audit Error (CWE-89):")
    print("-" * 80)
    print(example_security_audit_error())
    print()

    print("7. Graceful Degradation Message:")
    print("-" * 80)
    print(example_graceful_degradation_message())
    print()

    # Example of using in exception
    print("=" * 80)
    print("USAGE IN EXCEPTION")
    print("=" * 80)
    print()

    try:
        class ValidationError(Exception):
            pass

        raise ValidationError(
            format_error_message(
                context="Feature validation failed",
                expected="All required agents completed",
                got="Missing 2 agents",
                docs_link="docs/DEVELOPMENT.md"
            )
        )
    except ValidationError as e:
        print(f"Caught ValidationError:\n{e}")
