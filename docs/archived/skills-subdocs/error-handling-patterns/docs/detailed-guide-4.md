# Error Handling Patterns - Detailed Guide

## Security Best Practices

### Safe Error Messages

Always sanitize user input in error messages:

```python
def safe_error_message(user_input: str, context: str) -> str:
    """Create safe error message without injection risks.

    Prevents CWE-117 (log injection) by sanitizing user input.
    """
    # Remove newlines and control characters
    sanitized = user_input.replace('\n', ' ').replace('\r', '')
    return f"{context}: {sanitized}"
```

### No Credential Logging

Never include credentials in error messages or logs:

```python
# ❌ BAD: Exposes API key in logs
raise GitError(f"Authentication failed with key: {api_key}")

# ✅ GOOD: Generic message, no sensitive data
raise GitCredentialsError(
    "Authentication failed. Check git credentials.\n"
    "See: docs/GIT-SETUP.md#credentials"
)
```

### Structured Logging

Use structured logging for machine-readable audit logs:

```python
# ✅ GOOD: Structured, sanitized, no sensitive data
audit_log_security_event(
    event_type="authentication_failure",
    severity="MEDIUM",
    details={
        "service": "github",
        "reason": "invalid_credentials",
        "action": "blocked"
    }
)
```

---

## Related Skills

This skill complements:

- **security-patterns**: CWE references and security guidance
- **python-standards**: Code style for exception classes
- **observability**: Logging and monitoring integration
- **agent-output-formats**: Error reporting in agent outputs
