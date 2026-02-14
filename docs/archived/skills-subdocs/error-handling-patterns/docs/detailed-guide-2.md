# Error Handling Patterns - Detailed Guide

## Security Audit Logging

All security-relevant errors must be logged to the security audit log.

### Integration with security_utils

```python
from plugins.autonomous_dev.lib.security_utils import audit_log_security_event

def validate_operation(path: str, operation: str):
    """Validate security-sensitive operation.

    See error-handling-patterns skill for audit logging integration.
    """
    try:
        # Perform validation
        if not is_safe_path(path):
            raise SecurityError(f"Unsafe path detected: {path}")
    except SecurityError as e:
        # Log security event to audit log
        audit_log_security_event(
            event_type="path_validation_failure",
            severity="HIGH",
            details={
                "path": path,
                "operation": operation,
                "cwe": "CWE-22"
            }
        )
        raise  # Re-raise after logging
```

### What to Log

**Always log**:
- Path validation failures (CWE-22, CWE-59)
- Authentication/authorization failures
- Input validation failures with security implications
- Suspicious patterns (directory traversal attempts, SQL injection, etc.)

**Never log**:
- Passwords, API keys, tokens, secrets
- User credentials
- Session tokens
- Personal identifiable information (PII)

### Log Format

Audit logs should use structured format:

```python
audit_log_security_event(
    event_type="security_validation_failure",  # Type of security event
    severity="HIGH",  # HIGH/MEDIUM/LOW
    details={
        "category": "path_validation",
        "cwe": "CWE-22",
        "attempted_path": sanitized_path,  # Sanitized, no sensitive data
        "valid_paths": whitelist_summary,
        "action": "blocked"
    }
)
```

### CWE Prevention

This logging pattern prevents:
- **CWE-117**: Log injection (sanitized input)
- **CWE-532**: Information exposure through log files (no credentials)
- **CWE-778**: Insufficient logging (comprehensive security events)

### Example

See `examples/audit-logging-example.py` for complete implementation.

---

## Graceful Degradation

Non-blocking features should fail gracefully and provide manual fallback instructions.

### Pattern

```python
def optional_automation(required_data: dict) -> tuple[bool, str]:
    """Attempt automation with graceful degradation.

    Returns:
        tuple: (success: bool, message: str)

    See error-handling-patterns skill for graceful degradation patterns.
    """
    try:
        # Attempt automation
        result = perform_automation(required_data)
        return True, "Automation completed successfully"

    except AutomationError as e:
        # Log but don't fail feature
        logger.warning(f"Automation failed, manual steps required: {e}")

        # Provide manual fallback instructions
        manual_steps = generate_manual_instructions(required_data)
        return False, f"Automation unavailable. Manual steps:\n{manual_steps}"
```

### Guidelines

**Graceful degradation applies to**:
- Git automation (commit, push, PR creation)
- Optional validations (coverage checks, linting)
- Enhancement features (auto-formatting, auto-docs)

**Core features should NOT degrade**:
- Path validation (security requirement)
- PROJECT.md alignment (correctness requirement)
- Test execution (quality requirement)

### Example: Git Automation

```python
def auto_commit_and_push(changes: list[str]) -> tuple[bool, str]:
    """Attempt automatic git commit and push with graceful degradation.

    If git is not available or credentials missing, provides manual instructions.
    Core feature (code implementation) succeeds regardless of git automation.
    """
    # Check prerequisites
    if not check_git_available():
        return False, (
            "Git not available. Manual steps:\n"
            "1. Stage changes: git add .\n"
            "2. Commit: git commit -m 'your message'\n"
            "3. Push: git push origin branch-name"
        )

    if not check_git_credentials():
        return False, (
            "Git credentials not configured. Manual steps:\n"
            "1. Configure git: git config user.name 'Your Name'\n"
            "2. Configure git: git config user.email 'your@email.com'\n"
            "3. Retry git operations"
        )

    # Attempt automation
    try:
        git_commit(changes)
        git_push()
        return True, "Changes committed and pushed successfully"
    except GitError as e:
        return False, f"Git automation failed: {e}\nManual steps: [instructions]"
```

---

## Validation Error Patterns
