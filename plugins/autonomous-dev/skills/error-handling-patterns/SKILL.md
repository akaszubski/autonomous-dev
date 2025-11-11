---
name: error-handling-patterns
type: knowledge
description: Standardized error handling patterns including exception hierarchy, error message formatting, security audit logging, and graceful degradation. Use when raising exceptions, handling errors, or implementing validation.
keywords: error, exception, validation, raise, try, catch, except, audit, logging, graceful degradation, error handling
auto_activate: true
---

# Error Handling Patterns Skill

Standardized error handling patterns for all libraries to ensure consistent error reporting, security audit logging, and graceful degradation across the autonomous development system.

## When This Skill Activates

- Raising custom exceptions
- Handling errors and validation failures
- Implementing security audit logging
- Designing graceful degradation
- Formatting error messages
- Creating exception hierarchies
- Keywords: "error", "exception", "validation", "raise", "try", "catch", "audit"

---

## Exception Hierarchy

All custom exceptions should follow a domain-specific hierarchy pattern.

### Pattern

```
BaseException (Python built-in)
└── Exception (Python built-in)
    └── AutonomousDevError (Project base error)
        ├── SecurityError (Domain: Security)
        │   ├── PathTraversalError (Specific: CWE-22)
        │   ├── InvalidPathError (Specific: CWE-59)
        │   └── LogInjectionError (Specific: CWE-117)
        ├── ValidationError (Domain: Validation)
        │   ├── InvalidFormatError (Specific: Format validation)
        │   ├── ParseError (Specific: Parsing failures)
        │   └── ProjectAlignmentError (Specific: PROJECT.md validation)
        ├── GitError (Domain: Git operations)
        │   ├── GitNotAvailableError (Specific: Git not installed)
        │   ├── MergeConflictError (Specific: Merge conflicts)
        │   └── GitCredentialsError (Specific: Authentication)
        └── AgentError (Domain: Agent operations)
            ├── AgentInvocationError (Specific: Agent failures)
            ├── AgentTimeoutError (Specific: Timeout)
            └── AgentOutputError (Specific: Invalid output)
```

### Base Error Class

All project errors should inherit from a common base:

```python
class AutonomousDevError(Exception):
    """Base exception for autonomous-dev plugin.

    All custom exceptions should inherit from this base class to enable
    consistent error handling and logging across the system.

    See error-handling-patterns skill for exception hierarchy and usage.
    """

    def __init__(self, message: str, context: dict = None):
        """Initialize error with message and optional context.

        Args:
            message: Human-readable error description
            context: Optional dict with error context (paths, values, etc.)
        """
        super().__init__(message)
        self.context = context or {}

    def __str__(self):
        """Format error with context if available."""
        if self.context:
            context_str = "\n".join(f"  {k}: {v}" for k, v in self.context.items())
            return f"{super().__str__()}\nContext:\n{context_str}"
        return super().__str__()
```

### Example: Domain-Specific Errors

See `examples/domain-error-example.py` for complete implementations.

---

## Error Message Format

All error messages should follow a standardized format for clarity and consistency.

### Template

```
<CONTEXT>: What failed and where
Expected: What should have happened
Got: What actually happened
See: Link to documentation or solution

Example:
Feature validation failed in quality-validator agent
Expected: All 7 agents must run (researcher, planner, test-master, implementer, reviewer, security-auditor, doc-master)
Got: Only 5 agents ran (missing: implementer, doc-master)
See: docs/DEVELOPMENT.md#validation-checkpoints
```

### Components

1. **Context**: Where and what failed
   - Include: Function name, file path, operation
   - Example: "Path validation failed in security_utils.validate_path_whitelist()"

2. **Expected**: What should have happened
   - Include: Valid format, required values, success criteria
   - Example: "Expected: Path must be in whitelist [/plugins, /lib, /agents]"

3. **Got**: What actually happened
   - Include: Actual value, error state
   - Example: "Got: Path '/etc/passwd' outside whitelist"

4. **See**: Where to learn more
   - Include: Docs link, CWE reference, remediation guide
   - Example: "See: docs/SECURITY.md#path-validation (CWE-22 prevention)"

### Python Implementation

```python
def format_error_message(
    context: str,
    expected: str,
    got: str,
    docs_link: str = None
) -> str:
    """Format standardized error message.

    Args:
        context: What failed and where
        expected: What should have happened
        got: What actually happened
        docs_link: Optional documentation reference

    Returns:
        Formatted error message string
    """
    message = f"{context}\nExpected: {expected}\nGot: {got}"
    if docs_link:
        message += f"\nSee: {docs_link}"
    return message

# Usage
raise ValidationError(
    format_error_message(
        context="PROJECT.md alignment validation failed",
        expected="All features must align with GOALS section",
        got="Feature 'automatic deployments' not in scope",
        docs_link="docs/PROJECT-ALIGNMENT.md"
    )
)
```

### Example

See `examples/error-message-example.py` for complete examples.

---

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

Common validation patterns with standardized error handling.

### Path Validation

```python
def validate_path_whitelist(path: Path, whitelist: list[Path]) -> None:
    """Validate path is in whitelist (CWE-22, CWE-59 prevention).

    See error-handling-patterns skill for validation patterns.
    """
    if not any(path.is_relative_to(allowed) for allowed in whitelist):
        raise PathTraversalError(
            format_error_message(
                context=f"Path validation failed: {path}",
                expected=f"Path must be in whitelist {whitelist}",
                got=f"Path '{path}' is outside allowed directories",
                docs_link="docs/SECURITY.md#path-validation"
            )
        )
```

### Format Validation

```python
def validate_pytest_output(output: str) -> dict:
    """Validate pytest output format.

    See error-handling-patterns skill for validation patterns.
    """
    try:
        data = json.loads(output)
        required_fields = ["tests_run", "tests_passed", "tests_failed"]

        missing = [f for f in required_fields if f not in data]
        if missing:
            raise InvalidFormatError(
                format_error_message(
                    context="Pytest output validation failed",
                    expected=f"Output must contain fields: {required_fields}",
                    got=f"Missing fields: {missing}",
                    docs_link="docs/TESTING.md#pytest-format"
                )
            )
        return data

    except json.JSONDecodeError as e:
        raise ParseError(f"Invalid JSON in pytest output: {e}")
```

### Git Operation Validation

```python
def validate_git_state() -> None:
    """Validate git repository state before operations.

    See error-handling-patterns skill for validation patterns.
    """
    if not check_git_available():
        raise GitNotAvailableError(
            format_error_message(
                context="Git operations unavailable",
                expected="Git must be installed and in PATH",
                got="Git command not found",
                docs_link="docs/SETUP.md#git-installation"
            )
        )

    if has_merge_conflicts():
        raise MergeConflictError(
            format_error_message(
                context="Git repository has merge conflicts",
                expected="Clean working directory",
                got="Unresolved merge conflicts detected",
                docs_link="docs/GIT-WORKFLOW.md#resolving-conflicts"
            )
        )
```

---

## Usage Guidelines

### For Library Authors

When creating or updating libraries:

1. **Reference this skill** in the module docstring
2. **Inherit from domain-specific base errors** (not generic Exception)
3. **Use formatted error messages** (context + expected + got + docs)
4. **Log security events** to audit log
5. **Implement graceful degradation** for optional features

### For Claude

When implementing error handling:

1. **Load this skill** when keywords match ("error", "exception", "validation")
2. **Follow exception hierarchy** for custom errors
3. **Format error messages** using the standard template
4. **Log security events** for security-relevant errors
5. **Degrade gracefully** for non-blocking features

### Token Savings

By centralizing error patterns in this skill:

- **Before**: ~400-500 tokens per library for error classes + docstrings
- **After**: ~50-100 tokens for skill reference + custom logic
- **Savings**: ~300-400 tokens per library
- **Total**: ~7,000-8,000 tokens across 22 libraries (10-15% reduction)

---

## Progressive Disclosure

This skill uses Claude Code 2.0+ progressive disclosure architecture:

- **Metadata** (frontmatter): Always loaded (~200 tokens)
- **Full content**: Loaded only when keywords match
- **Result**: Efficient context usage, scales to 100+ skills

When you use terms like "error handling", "exception", "validation", or "raise", Claude Code automatically loads the full skill content to provide detailed guidance.

---

## Examples

Complete example implementations are available in the `examples/` directory:

- `base-error-example.py`: Base error class with context
- `domain-error-example.py`: Domain-specific error hierarchy
- `error-message-example.py`: Error message formatting
- `audit-logging-example.py`: Security audit logging integration

Refer to these examples when implementing error handling to ensure consistency and security compliance.

---

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
