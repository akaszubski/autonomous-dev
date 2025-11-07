# Security Utils - Quick Reference

**Module**: `plugins/autonomous-dev/lib/security_utils.py`
**Purpose**: Shared security validation and audit logging
**Date**: 2025-11-07

---

## Quick Start

```python
from security_utils import (
    validate_path,
    validate_agent_name,
    validate_github_issue,
    validate_input_length,
    audit_log
)
from pathlib import Path

# Validate file path (whitelist-based)
safe_path = validate_path(
    Path("docs/sessions/session.json"),
    purpose="session tracking",
    allow_missing=True  # Optional: allow non-existent files
)

# Validate agent name (alphanumeric + hyphen/underscore)
safe_name = validate_agent_name("researcher", purpose="agent start")

# Validate GitHub issue number (1-999999)
safe_issue = validate_github_issue(42, purpose="issue tracking")

# Validate input length (prevent resource exhaustion)
safe_message = validate_input_length(
    "Hello world",
    max_length=10000,
    field_name="message",
    purpose="logging"
)

# Log security event to audit log
audit_log("operation_name", "success", {
    "operation": "validate_path",
    "path": str(safe_path),
    "user": os.getenv("USER")
})
```

---

## When to Use

### ✅ Always Use `validate_path()` For:

- Any user-provided file paths
- Configuration file paths
- Session file paths
- Log file paths
- Backup file paths
- Any path that could be influenced by external input

### ✅ Always Use `validate_agent_name()` For:

- Agent names from command-line arguments
- Agent names from API requests
- Agent names from configuration files
- Any string used to identify agents

### ✅ Always Use `validate_github_issue()` For:

- GitHub issue numbers from CLI
- Issue numbers from API requests
- Issue numbers from user input

### ✅ Always Use `validate_input_length()` For:

- User messages
- Log messages
- Descriptions
- Any string that could be unbounded

### ✅ Always Use `audit_log()` For:

- All security validation events (success and failure)
- Authentication/authorization events
- File access events
- Configuration changes
- Any security-relevant operation

---

## Error Handling

All validation functions raise `ValueError` with descriptive messages:

```python
try:
    safe_path = validate_path(user_path, "user upload")
except ValueError as e:
    # Error message includes:
    # - What went wrong
    # - What was expected
    # - Current value
    # - Link to documentation
    print(f"Security violation: {e}")
    # Example output:
    # Security violation: Path traversal attempt detected: ../../etc/passwd
    # Purpose: user upload
    # Paths containing '..' are not allowed.
    # Expected: Path within project or allowed directories
    # See: docs/SECURITY.md#path-validation
```

---

## Test Mode Support

The module auto-detects pytest test mode and relaxes validation:

```python
# Production mode: Only PROJECT_ROOT allowed
validate_path(Path("/tmp/test.json"), "test")
# Raises: ValueError (outside project root)

# Test mode (pytest detected): PROJECT_ROOT + system temp allowed
os.environ["PYTEST_CURRENT_TEST"] = "test::test_case"
validate_path(Path("/tmp/test.json"), "test")
# Success: Returns validated path
```

**Auto-detection**: Checks `os.getenv("PYTEST_CURRENT_TEST")`

---

## Common Patterns

### Pattern 1: File Operation with Validation

```python
from security_utils import validate_path, audit_log
from pathlib import Path

def read_config(config_path: str) -> dict:
    """Read configuration file with security validation."""
    try:
        # Validate path
        safe_path = validate_path(
            Path(config_path),
            purpose="config read",
            allow_missing=False
        )

        # Perform operation
        content = safe_path.read_text()

        # Log success
        audit_log("config_read", "success", {
            "operation": "read_config",
            "path": str(safe_path)
        })

        return json.loads(content)

    except ValueError as e:
        # Log security violation
        audit_log("config_read", "failure", {
            "operation": "read_config",
            "path": config_path,
            "error": str(e)
        })
        raise
```

### Pattern 2: User Input Validation

```python
from security_utils import validate_agent_name, validate_input_length

def log_agent_event(agent_name: str, message: str):
    """Log agent event with input validation."""
    # Validate all inputs
    safe_name = validate_agent_name(agent_name, purpose="event logging")
    safe_message = validate_input_length(
        message,
        max_length=10000,
        field_name="message",
        purpose="event logging"
    )

    # Safe to use validated inputs
    print(f"[{safe_name}] {safe_message}")
```

### Pattern 3: Class Initialization with Validation

```python
from security_utils import validate_path, audit_log
from pathlib import Path

class FileProcessor:
    def __init__(self, file_path: Path):
        """Initialize with security validation."""
        # Validate path
        self.file_path = validate_path(
            file_path,
            purpose="file processing",
            allow_missing=False
        )

        # Log initialization
        audit_log("file_processor", "initialized", {
            "operation": "init",
            "file_path": str(self.file_path)
        })
```

---

## Security Best Practices

### 1. Validate Early

```python
# ✅ GOOD: Validate immediately
def process_file(path: str):
    safe_path = validate_path(Path(path), "file processing")
    # Rest of function uses safe_path

# ❌ BAD: Validate late (path used before validation)
def process_file(path: str):
    if Path(path).exists():  # Unsafe check first
        safe_path = validate_path(Path(path), "file processing")
```

### 2. Validate All Inputs

```python
# ✅ GOOD: Validate all user inputs
def create_session(agent: str, message: str, issue: int):
    safe_agent = validate_agent_name(agent, "session")
    safe_message = validate_input_length(message, 10000, "message", "session")
    safe_issue = validate_github_issue(issue, "session")
    # ... use validated inputs ...

# ❌ BAD: Only validate some inputs
def create_session(agent: str, message: str, issue: int):
    safe_agent = validate_agent_name(agent, "session")
    # message and issue used without validation (vulnerable!)
```

### 3. Log All Security Events

```python
# ✅ GOOD: Log both success and failure
try:
    safe_path = validate_path(path, "upload")
    audit_log("upload", "success", {"path": str(safe_path)})
except ValueError as e:
    audit_log("upload", "failure", {"path": path, "error": str(e)})
    raise

# ❌ BAD: Only log failures (no visibility into successful operations)
try:
    safe_path = validate_path(path, "upload")
    # No success logging
except ValueError as e:
    audit_log("upload", "failure", {"path": path, "error": str(e)})
    raise
```

### 4. Use Descriptive Purpose Strings

```python
# ✅ GOOD: Clear, specific purpose
validate_path(path, "user profile image upload")
validate_path(path, "session backup restoration")

# ❌ BAD: Generic purpose (harder to audit)
validate_path(path, "file operation")
validate_path(path, "processing")
```

---

## Audit Log Format

All security events are logged to `logs/security_audit.log` in JSON format:

```json
{
  "timestamp": "2025-11-07T10:52:27.300505Z",
  "event_type": "path_validation",
  "status": "success",
  "context": {
    "operation": "validate_agent_session_tracking",
    "path": "docs/sessions/session.json",
    "resolved": "/Users/user/project/docs/sessions/session.json",
    "test_mode": false
  }
}
```

### Parsing Audit Logs

```bash
# View recent events
tail -100 logs/security_audit.log | jq -r '"\(.timestamp) [\(.status)] \(.event_type)"'

# Filter by event type
cat logs/security_audit.log | jq 'select(.event_type == "path_validation")'

# Filter by status
cat logs/security_audit.log | jq 'select(.status == "failure")'

# Count events by type
cat logs/security_audit.log | jq -r '.event_type' | sort | uniq -c
```

---

## Troubleshooting

### Issue: "Path outside project root"

**Cause**: Path validation rejected path outside PROJECT_ROOT

**Solution**: Ensure path is within project, or use test mode for temp files

```python
# Option 1: Use path within project
validate_path(Path("docs/sessions/test.json"), "test")

# Option 2: Enable test mode (for tests only)
os.environ["PYTEST_CURRENT_TEST"] = "test"
validate_path(Path("/tmp/test.json"), "test")
```

### Issue: "Symlinks are not allowed"

**Cause**: Path is a symlink (security violation)

**Solution**: Use the actual file path, not a symlink

```bash
# Find real path
$ readlink -f symlink_path

# Use real path in code
validate_path(Path("/real/path/to/file"), "operation")
```

### Issue: "Invalid agent name"

**Cause**: Agent name contains invalid characters

**Solution**: Use only alphanumeric, hyphen, underscore

```python
# ✅ Valid agent names
validate_agent_name("researcher", "test")
validate_agent_name("test-master", "test")
validate_agent_name("doc_master", "test")

# ❌ Invalid agent names
validate_agent_name("researcher; rm -rf /", "test")  # Semicolon
validate_agent_name("test master", "test")  # Space
validate_agent_name("doc@master", "test")  # At sign
```

---

## Performance

- **validate_path()**: ~0.5ms per call
- **validate_agent_name()**: ~0.1ms per call
- **validate_github_issue()**: ~0.05ms per call
- **validate_input_length()**: ~0.05ms per call
- **audit_log()**: ~1ms per call (async-friendly)

**Overhead**: Negligible for typical use cases (< 1% of operation time)

---

## Related Documentation

- [SECURITY_UTILS_IMPLEMENTATION.md](../../../docs/SECURITY_UTILS_IMPLEMENTATION.md) - Implementation details
- [SECURITY.md](../../../docs/SECURITY.md) - General security guidelines
- [OWASP Top 10](https://owasp.org/Top10/) - Security best practices

---

**Questions?** See full implementation docs or check audit logs for examples.
