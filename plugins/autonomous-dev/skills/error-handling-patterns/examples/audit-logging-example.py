#!/usr/bin/env python3
"""
Security Audit Logging Example

This example demonstrates integration with security_utils.audit_log_security_event()
for logging security-relevant errors and events.

See error-handling-patterns skill for audit logging patterns.
"""

import json
from pathlib import Path
from typing import Any
from datetime import datetime


# ============================================================================
# Mock security_utils (for demonstration)
# In production, use: from plugins.autonomous_dev.lib.security_utils import audit_log_security_event
# ============================================================================

def audit_log_security_event(
    event_type: str,
    severity: str,
    details: dict
) -> None:
    """Log security event to audit log (mock implementation).

    Args:
        event_type: Type of security event (e.g., "path_validation_failure")
        severity: Severity level (HIGH/MEDIUM/LOW)
        details: Event details (sanitized, no sensitive data)

    See error-handling-patterns skill for audit logging patterns.
    """
    # In production, this writes to logs/security_audit.log
    log_entry = {
        "timestamp": datetime.now().isoformat(),
        "event_type": event_type,
        "severity": severity,
        "details": details
    }
    print(f"[SECURITY AUDIT] {json.dumps(log_entry, indent=2)}")


# ============================================================================
# Security Error Classes (simplified)
# ============================================================================

class SecurityError(Exception):
    """Base security error."""
    pass


class PathTraversalError(SecurityError):
    """Path traversal attempt detected (CWE-22)."""
    pass


class InvalidPathError(SecurityError):
    """Invalid path format (CWE-59)."""
    pass


# ============================================================================
# Example: Path Validation with Audit Logging
# ============================================================================

def validate_path_whitelist(path: Path, whitelist: list[Path]) -> None:
    """Validate path is in whitelist with security audit logging.

    Args:
        path: Path to validate
        whitelist: List of allowed paths

    Raises:
        PathTraversalError: If path is outside whitelist

    See error-handling-patterns skill for path validation pattern.
    """
    try:
        # Check if path is in whitelist
        is_allowed = any(
            path.is_relative_to(allowed)
            for allowed in whitelist
        )

        if not is_allowed:
            raise PathTraversalError(
                f"Path validation failed: {path}\n"
                f"Expected: Path must be in whitelist {whitelist}\n"
                f"Got: Path '{path}' is outside allowed directories\n"
                f"See: docs/SECURITY.md#path-validation (CWE-22)"
            )

    except PathTraversalError as e:
        # Log security event to audit log
        audit_log_security_event(
            event_type="path_validation_failure",
            severity="HIGH",
            details={
                "category": "path_traversal_attempt",
                "cwe": "CWE-22",
                "attempted_path": str(path),  # Safe to log (sanitized)
                "whitelist": [str(p) for p in whitelist],
                "action": "blocked"
            }
        )
        raise  # Re-raise after logging


# ============================================================================
# Example: Git Operation with Audit Logging
# ============================================================================

def validate_git_credentials() -> bool:
    """Validate git credentials with security audit logging.

    Returns:
        True if credentials are valid, False otherwise

    See error-handling-patterns skill for git validation pattern.
    """
    # Check if git credentials are configured
    credentials_valid = False  # Mock check

    if not credentials_valid:
        # Log security event (NOT credentials, just event)
        audit_log_security_event(
            event_type="git_credentials_validation_failure",
            severity="MEDIUM",
            details={
                "category": "authentication",
                "service": "git",
                "reason": "credentials_not_configured",
                "action": "blocked",
                # ❌ NEVER LOG: "api_key", "password", "token"
                # ✅ ALWAYS: Generic event without sensitive data
            }
        )
        return False

    return True


# ============================================================================
# Example: Input Validation with Audit Logging
# ============================================================================

def validate_user_input(user_input: str) -> str:
    """Validate and sanitize user input with audit logging.

    Args:
        user_input: Raw user input

    Returns:
        Sanitized user input

    Raises:
        SecurityError: If input contains malicious patterns

    See error-handling-patterns skill for input validation pattern.
    """
    # Check for suspicious patterns
    malicious_patterns = ['../', '../', '../../', '/etc/', '/var/', 'rm -rf']

    for pattern in malicious_patterns:
        if pattern in user_input.lower():
            # Log security event
            audit_log_security_event(
                event_type="malicious_input_detected",
                severity="HIGH",
                details={
                    "category": "input_validation",
                    "pattern_detected": pattern,
                    "input_length": len(user_input),
                    "action": "blocked",
                    # ✅ GOOD: Log pattern and length, not full input
                    # ❌ BAD: "user_input": user_input (could expose sensitive data)
                }
            )

            raise SecurityError(
                f"Malicious pattern detected in user input\n"
                f"Expected: Safe input without directory traversal patterns\n"
                f"Got: Input contains suspicious pattern '{pattern}'\n"
                f"See: docs/SECURITY.md#input-validation"
            )

    # Sanitize input (remove control characters)
    sanitized = user_input.replace('\n', ' ').replace('\r', '')
    return sanitized


# ============================================================================
# Example: Agent Invocation with Audit Logging
# ============================================================================

def invoke_agent_with_audit(agent_name: str, context: dict) -> Any:
    """Invoke agent with security audit logging for failures.

    Args:
        agent_name: Name of agent to invoke
        context: Agent execution context

    Returns:
        Agent output

    See error-handling-patterns skill for agent invocation pattern.
    """
    try:
        # Mock agent invocation
        if agent_name == "malicious-agent":
            raise SecurityError("Suspicious agent name detected")

        # Agent execution would happen here
        return {"status": "success", "agent": agent_name}

    except SecurityError as e:
        # Log security event for suspicious agent invocation
        audit_log_security_event(
            event_type="suspicious_agent_invocation",
            severity="MEDIUM",
            details={
                "category": "agent_security",
                "agent_name": agent_name,  # Safe to log (validated)
                "reason": "suspicious_name_pattern",
                "action": "blocked"
            }
        )
        raise


# ============================================================================
# Best Practices Summary
# ============================================================================

def audit_logging_best_practices():
    """Summary of audit logging best practices.

    See error-handling-patterns skill for complete guidance.
    """
    return {
        "always_log": [
            "Path validation failures (CWE-22, CWE-59)",
            "Authentication/authorization failures",
            "Input validation failures with security implications",
            "Suspicious patterns (directory traversal, SQL injection attempts)",
            "Agent invocation failures with security implications"
        ],
        "never_log": [
            "Passwords, API keys, tokens, secrets",
            "User credentials",
            "Session tokens",
            "Personal identifiable information (PII)",
            "Full user input (only patterns and metadata)"
        ],
        "log_format": {
            "structured": "Use JSON format for machine readability",
            "sanitized": "Sanitize all logged data (remove control characters)",
            "contextual": "Include enough context for investigation",
            "actionable": "Log action taken (blocked, allowed, degraded)"
        },
        "cwe_prevention": [
            "CWE-117: Log injection (sanitize all logged data)",
            "CWE-532: Information exposure through logs (no credentials)",
            "CWE-778: Insufficient logging (log all security events)"
        ]
    }


# ============================================================================
# Usage Examples
# ============================================================================

if __name__ == "__main__":
    print("=" * 80)
    print("SECURITY AUDIT LOGGING EXAMPLES")
    print("=" * 80)
    print()

    # Example 1: Path validation with audit logging
    print("1. Path Validation Failure (logged to audit):")
    print("-" * 80)
    try:
        validate_path_whitelist(
            Path("/etc/passwd"),
            [Path("/plugins"), Path("/lib"), Path("/agents")]
        )
    except PathTraversalError as e:
        print(f"Exception: {e.__class__.__name__}")
        print(f"Message: {str(e).split(chr(10))[0]}...")  # First line only
    print()

    # Example 2: Git credentials validation
    print("2. Git Credentials Validation (logged to audit):")
    print("-" * 80)
    result = validate_git_credentials()
    print(f"Validation result: {result}")
    print()

    # Example 3: Malicious input detection
    print("3. Malicious Input Detection (logged to audit):")
    print("-" * 80)
    try:
        validate_user_input("../../etc/passwd")
    except SecurityError as e:
        print(f"Exception: {e.__class__.__name__}")
        print(f"Message: {str(e).split(chr(10))[0]}...")
    print()

    # Example 4: Suspicious agent invocation
    print("4. Suspicious Agent Invocation (logged to audit):")
    print("-" * 80)
    try:
        invoke_agent_with_audit("malicious-agent", {})
    except SecurityError as e:
        print(f"Exception: {e.__class__.__name__}")
        print(f"Message: {e}")
    print()

    # Example 5: Best practices summary
    print("5. Audit Logging Best Practices:")
    print("-" * 80)
    practices = audit_logging_best_practices()
    print(json.dumps(practices, indent=2))
