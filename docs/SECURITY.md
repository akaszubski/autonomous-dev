# Security Guide

**Last Updated**: 2025-11-07
**Status**: Production-ready security framework for path validation and input sanitization

This document describes the security architecture, vulnerabilities fixed, and best practices for using the security utilities.

## Table of Contents

1. [Overview](#overview)
2. [Security Module: security_utils.py](#security-module-security_utilspy)
3. [Path Validation](#path-validation)
4. [Input Validation](#input-validation)
5. [Audit Logging](#audit-logging)
6. [Test Mode Security](#test-mode-security)
7. [Vulnerability Fixes (v3.4.1 - v3.4.3)](#vulnerability-fixes)
8. [Best Practices](#best-practices)
9. [API Reference](#api-reference)

## Overview

The autonomous-dev plugin implements a **centralized security framework** to prevent common vulnerabilities:

- **CWE-22**: Path Traversal (prevent ../ style attacks)
- **CWE-59**: Improper Link Resolution (detect and block symlinks)
- **CWE-117**: Improper Output Neutralization (secure audit logging)
- **CWE-400**: Uncontrolled Resource Consumption (length validation)
- **CWE-95**: Improper Neutralization of Directives (input validation)

All security-sensitive operations use the centralized `security_utils.py` module to ensure consistent enforcement.

## Security Module: security_utils.py

**Location**: `plugins/autonomous-dev/lib/security_utils.py` (628 lines)

**Purpose**: Shared security validation and audit logging for path validation, input sanitization, and event auditing.

**Core Functions**:

| Function | Purpose | Returns |
|----------|---------|---------|
| `validate_path()` | Whitelist-based path validation | Resolved Path object |
| `validate_pytest_path()` | Pytest format validation | Validated path string |
| `validate_input_length()` | String length enforcement | Validated string |
| `validate_agent_name()` | Agent name format validation | Validated name |
| `validate_github_issue()` | GitHub issue number validation | Validated number |
| `audit_log()` | Structured security event logging | None (logs to file) |

**Key Features**:

- **4-layer path validation**: String-level checks, symlink detection, path resolution, whitelist validation
- **Whitelist approach**: Only allow known-safe locations instead of blacklisting bad patterns
- **Test mode support**: Allows system temp directory during pytest execution, blocks system directories
- **Thread-safe audit logging**: Rotating log file (10MB max) with JSON format for analysis
- **Clear error messages**: Include what went wrong, what's expected, and documentation links

## Path Validation

### Overview

Path validation is the most critical security function, preventing attackers from writing files outside the project directory.

### Function: `validate_path()`

```python
from plugins.autonomous_dev.lib.security_utils import validate_path
from pathlib import Path

# Validate a session file path
try:
    safe_path = validate_path(
        Path("docs/sessions/20251107-session.json"),
        purpose="session file validation"
    )
    # safe_path is now guaranteed to be within PROJECT_ROOT
except ValueError as e:
    print(f"Security violation: {e}")
```

### Validation Layers

1. **String-level checks**
   - Reject paths containing `..` (path traversal attempt)
   - Reject paths longer than 4096 characters (POSIX PATH_MAX)

2. **Symlink detection**
   - Detect symlinks BEFORE path resolution
   - Reject symlinks that point outside PROJECT_ROOT
   - Catch symlinks in parent directories after resolution

3. **Path resolution**
   - Normalize path to absolute form
   - Handle `.` and `..` sequences
   - Resolve symlinks (but reject them if found)

4. **Whitelist validation**
   - Verify path is within PROJECT_ROOT
   - In test mode, also allow system temp directory
   - Block all other locations

### Attack Scenarios Blocked

| Attack | Example | Layer Blocked |
|--------|---------|---------------|
| Relative traversal | `../../etc/passwd` | Layer 1 (..) check |
| Absolute system path | `/etc/passwd` | Layer 4 (whitelist) |
| Symlink escape | `link -> /etc/passwd` | Layer 2 (symlink detection) |
| Mixed traversal | `subdir/../../etc` | Layer 3 (after resolve) |
| Compressed traversal | `docs/sessions/../../lib/` | Layer 4 (whitelist) |

### Allowed Directories

In production mode, paths must be within:
- `PROJECT_ROOT` - Project root directory
- `docs/sessions/` - Session logs
- `.claude/` - Claude configuration
- `plugins/autonomous-dev/lib/` - Library files
- `scripts/` - Scripts
- `tests/` - Test files

In test mode, additionally allowed:
- System temp directory (e.g., `/tmp` on Linux, `%TEMP%` on Windows)

### Parameters

```python
validate_path(
    path: Path | str,
    purpose: str,
    allow_missing: bool = False,
    test_mode: Optional[bool] = None
) -> Path
```

- **path**: Path to validate (string or Path object)
- **purpose**: Human-readable description (e.g., "session file", "project config")
  - Used in error messages and audit logs
  - Replaced with underscores in log entries
- **allow_missing**: If True, path doesn't need to exist on filesystem
  - Used for paths being created (e.g., new session files)
  - Still validates against whitelist
- **test_mode**: Override test mode detection
  - None (default): Auto-detect via PYTEST_CURRENT_TEST env var
  - True: Force test mode (allow system temp)
  - False: Force production mode (no system temp)

### Return Value

Returns a resolved `pathlib.Path` object guaranteed to be:
- Within PROJECT_ROOT (or system temp in test mode)
- Not containing symlinks
- Not containing path traversal sequences
- Normalized to absolute form

### Example Usage

```python
from plugins.autonomous_dev.lib.security_utils import validate_path
from pathlib import Path

# Validate session file (production)
try:
    session_path = validate_path(
        Path("docs/sessions/20251107.json"),
        purpose="session file",
        allow_missing=False  # File must exist
    )
    with open(session_path) as f:
        session_data = json.load(f)
except ValueError as e:
    print(f"Invalid path: {e}")
    sys.exit(1)

# Validate new config file (test mode)
try:
    config_path = validate_path(
        Path(".claude/config.json"),
        purpose="config file",
        allow_missing=True,  # OK if doesn't exist yet
        test_mode=True
    )
    config_path.write_text(json.dumps(config))
except ValueError as e:
    print(f"Invalid path: {e}")
    sys.exit(1)
```

## Pytest Path Validation

### Function: `validate_pytest_path()`

```python
from plugins.autonomous_dev.lib.security_utils import validate_pytest_path

# Validate pytest path
try:
    safe_pytest = validate_pytest_path(
        "tests/unit/test_security_utils.py::TestPathValidation::test_traversal_blocked",
        purpose="test execution"
    )
    # safe_pytest can be safely passed to subprocess/pytest
except ValueError as e:
    print(f"Invalid pytest path: {e}")
```

### Valid Formats

All of these are valid pytest paths:

```
tests/test_security.py
tests/test_security.py::test_path_validation
tests/unit/test_security.py::TestPathValidation::test_traversal_blocked
tests/test_security.py::test_validation[param1,param2]
```

### Format Validation

Pytest paths are validated against the regex pattern:

```regex
^[\w/.-]+\.py(?:::[\w\[\],_-]+)?$
```

- `[\w/.-]+` - File path (alphanumeric, slash, dot, hyphen)
- `\.py` - Must be Python file
- `(?:::[\w\[\],_-]+)?` - Optional test specifier (test name + parameters)

### Attack Scenarios Blocked

| Attack | Example | Result |
|--------|---------|--------|
| Shell injection | `test.py; rm -rf /` | Blocked by regex |
| Code injection | `test.py::os.system('evil')` | Blocked by regex |
| Path traversal | `../../etc/test.py` | Blocked by .. check |
| Command substitution | `test.py$(whoami)` | Blocked by regex |

### Parameters

```python
validate_pytest_path(
    pytest_path: str,
    purpose: str = "pytest execution"
) -> str
```

- **pytest_path**: Pytest path to validate
- **purpose**: Human-readable description

### Return Value

Returns the validated pytest path string (same format as input, if valid).

## Input Validation

### Function: `validate_input_length()`

Validates string length to prevent resource exhaustion (DoS).

```python
from plugins.autonomous_dev.lib.security_utils import validate_input_length

# Validate user message
try:
    message = validate_input_length(
        user_input,
        max_length=10000,
        field_name="user_message",
        purpose="agent tracking"
    )
except ValueError as e:
    print(f"Input too long: {e}")
```

**Prevents**:
- Memory exhaustion (OOM kills)
- Log file bloat (disk exhaustion)
- Processing delays (DoS)

### Function: `validate_agent_name()`

Validates agent name format.

```python
from plugins.autonomous_dev.lib.security_utils import validate_agent_name

# Validate agent name
try:
    name = validate_agent_name("test-master", purpose="agent tracking")
except ValueError as e:
    print(f"Invalid agent name: {e}")
```

**Valid format**:
- 1-255 characters
- Alphanumeric, hyphen, underscore only
- Examples: `researcher`, `test-master`, `doc_master`

**Invalid format**:
- Spaces: `test master`
- Special characters: `test@master`
- Shell metacharacters: `test;rm`

### Function: `validate_github_issue()`

Validates GitHub issue number.

```python
from plugins.autonomous_dev.lib.security_utils import validate_github_issue

# Validate issue number
try:
    issue = validate_github_issue(46, purpose="security fix")
except ValueError as e:
    print(f"Invalid issue number: {e}")
```

**Valid range**: 1 to 999999

**Prevents**:
- Negative issue numbers
- Integer overflow
- Out-of-range values

## Audit Logging

### Function: `audit_log()`

Records all security events to a structured JSON audit log.

```python
from plugins.autonomous_dev.lib.security_utils import audit_log

# Log security event
audit_log(
    event_type="path_validation",
    status="success",
    context={
        "operation": "validate_session_file",
        "path": "/absolute/path/to/file",
        "user": os.getenv("USER")
    }
)
```

### Audit Log Location

Logs are written to: `logs/security_audit.log`

### Log Format

Each entry is a JSON object:

```json
{
  "timestamp": "2025-11-07T15:30:45.123456Z",
  "event_type": "path_validation",
  "status": "success",
  "context": {
    "operation": "validate_session_file",
    "path": "/project/docs/sessions/20251107.json",
    "resolved": "/absolute/path/docs/sessions/20251107.json",
    "test_mode": false
  }
}
```

### Log Rotation

- **Max size**: 10MB per file
- **Backup count**: 5 files (50MB total history)
- **Format**: UTF-8 JSON, one event per line
- **Thread-safe**: Uses locks for concurrent access

### Monitoring Security Events

Parse the audit log to find security violations:

```bash
# Find all failures
grep '"status": "failure"' logs/security_audit.log

# Find path validation failures
grep 'path_validation.*failure' logs/security_audit.log

# Find validation attempts in last hour
jq 'select(.timestamp > "2025-11-07T14:30:00Z")' logs/security_audit.log

# Count failures by type
jq '.event_type' logs/security_audit.log | sort | uniq -c
```

## Test Mode Security

### Problem: Pytest Temp Directories

When pytest runs, it creates temporary directories outside PROJECT_ROOT:

```
/tmp/pytest-of-user/pytest-123/test_0/  # macOS/Linux
C:\Users\user\AppData\Local\Temp\...     # Windows
```

Tests need to write to these directories, but the security whitelist normally blocks them.

### Solution: Controlled Test Mode

Test mode is **automatically detected** by checking the `PYTEST_CURRENT_TEST` environment variable:

```python
import os

# Pytest sets this during test execution
test_mode = os.getenv("PYTEST_CURRENT_TEST") is not None
```

### Test Mode Behavior

In test mode, `validate_path()` allows:

1. **PROJECT_ROOT and subdirectories** (same as production)
2. **System temp directory** (NEW in test mode)
   - `/tmp` on macOS/Linux
   - `%TEMP%` on Windows
3. **Whitelisted project directories**
   - `docs/sessions/`
   - `.claude/`
   - `tests/`

### Test Mode BLOCKS

Critically, test mode still blocks:

- `/etc/` - System configuration
- `/usr/` - System binaries
- `/bin/` - System binaries
- `/sbin/` - System administration
- `/var/log/` - System logs
- Any absolute path outside whitelist

### Example: Test Mode in Action

```python
import tempfile
from pathlib import Path
from plugins.autonomous_dev.lib.security_utils import validate_path

# In pytest execution:
def test_session_logging():
    # Create temp file in system temp
    with tempfile.NamedTemporaryFile(delete=False) as f:
        temp_path = Path(f.name)

    # This is ALLOWED in test mode (PYTEST_CURRENT_TEST set)
    validated = validate_path(
        temp_path,
        "test session file",
        allow_missing=False,
        test_mode=None  # Auto-detect - will be True during pytest
    )

    # Can safely write to validated path
    validated.write_text("test data")

    temp_path.unlink()  # Cleanup
```

### Override Test Mode

You can explicitly control test mode detection:

```python
# Force test mode (for testing security module itself)
validate_path(some_path, "test", test_mode=True)

# Force production mode (for manual testing)
validate_path(some_path, "test", test_mode=False)
```

## Vulnerability Fixes

This section documents the critical security vulnerabilities fixed in v3.4.1, v3.4.2, and v3.4.3.

### v3.4.1: Race Condition in Atomic Writes (HIGH - CVSS 8.7)

**Vulnerability**: Path `project_md_updater.py` used predictable PID-based temp filenames

**Attack**: Symlink race condition enabling arbitrary file writes

**Example**:
```python
# VULNERABLE (PID-based)
temp_file = f".PROJECT_{os.getpid()}.tmp"
# Process ID observable via /proc/[pid] or ps
# Attacker creates symlink: ln -s /etc/passwd .PROJECT_12345.tmp
# Process writes to symlink target
```

**Fix**: Use `tempfile.mkstemp()` for cryptographic random filenames

```python
# FIXED (cryptographic random)
fd, temp_file = tempfile.mkstemp(
    dir=str(temp_dir),
    prefix='.PROJECT.',
    suffix='.tmp',
    text=False
)
# mkstemp() atomically creates file with mode 0600 (owner-only)
# Filename has 128+ bits of entropy (random)
# O_EXCL flag prevents race conditions
```

**Impact**: Fixes privilege escalation vulnerability in project goal tracking

**Status**: APPROVED FOR PRODUCTION (see `docs/sessions/SECURITY_AUDIT_project_md_updater_20251105.md`)

### v3.4.2: XSS in Regression Tests (MEDIUM - CVSS 5.4)

**Vulnerability**: Unsafe f-string interpolation in `auto_add_to_regression.py`

**Attack**: Code injection via user prompts or file paths

**Example**:
```python
# VULNERABLE (f-string)
test_code = f"""
def test_feature():
    description = '{user_input}'  # User can inject code
    assert True
"""
# User input: ' + malicious_code + '''
# Generated: def test_feature(): description = '' + malicious_code + ''; assert True
```

**Fix**: Three-layer defense:

1. **Input Validation**: Reject dangerous keywords/builtins
2. **Input Sanitization**: HTML entity escaping, control character removal
3. **Safe Substitution**: `string.Template` instead of f-strings

```python
# FIXED (safe template)
import string

template = string.Template("""
def test_feature():
    description = '$description'
    assert True
""")

test_code = template.safe_substitute(description=sanitized_input)
# Template.safe_substitute() never evaluates expressions
```

**Impact**: Fixes code injection vulnerability in regression test generation

**Status**: APPROVED FOR PRODUCTION (see `docs/sessions/SECURITY_AUDIT_AUTO_ADD_REGRESSION_20251105.md`)

### v3.4.3: Path Traversal in Test Mode (CRITICAL - CVSS 9.8)

**Vulnerability**: Blacklist approach allowed /var/log/ and system directories in test mode

**Attack**: Write arbitrary files to system directories during test execution

**Example**:
```python
# VULNERABLE (blacklist approach)
blocked_paths = ["/etc", "/usr", "/root"]
if path.startswith(blocked_dirs):
    raise ValueError("blocked")
# But /var/log/ not in list, so it's allowed
# Attacker can write to /var/log/sensitive_file
```

**Fix**: Whitelist approach - only allow known-safe locations

```python
# FIXED (whitelist approach)
allowed_dirs = [PROJECT_ROOT, SYSTEM_TEMP]  # Only 2 locations
is_allowed = any(path.is_relative_to(d) for d in allowed_dirs)
if not is_allowed:
    raise ValueError("path outside whitelist")
```

**Impact**: Fixes critical path traversal vulnerability in test mode

**Status**: APPROVED FOR PRODUCTION (see commit c4005fe)

## Best Practices

### 1. Always Validate User Input

```python
# GOOD: Validate all paths
from plugins.autonomous_dev.lib.security_utils import validate_path

user_path = request.json["path"]  # From API request
try:
    safe_path = validate_path(user_path, "user-provided path")
    process_file(safe_path)
except ValueError as e:
    return {"error": str(e)}, 400
```

### 2. Use Appropriate Validation Function

```python
from plugins.autonomous_dev.lib.security_utils import (
    validate_path,
    validate_pytest_path,
    validate_agent_name,
    validate_input_length
)

# For file paths
safe_file = validate_path(file_path, "config file")

# For pytest invocations
safe_pytest = validate_pytest_path(pytest_path, "test execution")

# For agent names
safe_agent = validate_agent_name(agent_name, "agent tracking")

# For message length
safe_message = validate_input_length(
    message, 10000, "message", "log entry"
)
```

### 3. Check Audit Logs Regularly

```bash
# Weekly security review
tail -1000 logs/security_audit.log | grep '"status": "failure"' | jq '.context'

# Alert on suspicious patterns
grep 'path_traversal\|symlink' logs/security_audit.log
```

### 4. Clear Error Messages

Validation errors include:
- What went wrong (specific error)
- What's expected (valid format)
- Where to learn more (documentation link)

```python
# BAD: Vague error
raise ValueError("Bad path")

# GOOD: Clear context
raise ValueError(
    f"Path outside allowed directories: {path}\n"
    f"Purpose: {purpose}\n"
    f"Resolved path: {resolved_path}\n"
    f"Allowed locations:\n"
    f"  - Project root: {PROJECT_ROOT}\n"
    f"See: docs/SECURITY.md#path-validation"
)
```

### 5. Symlink Verification

Always validate paths before following symlinks:

```python
from plugins.autonomous_dev.lib.security_utils import validate_path

# GOOD: Validate before following
safe_path = validate_path(user_path, "config file")
if safe_path.is_symlink():
    raise ValueError("Symlinks not allowed")

# validate_path() already does this, so just:
safe_path = validate_path(user_path, "config file")
# Symlinks are already rejected
```

### 6. Test Mode Awareness

Remember that test mode allows system temp:

```python
def validate_session_file(path_str):
    # Auto-detects test mode
    # In pytest: allows /tmp (temporary test files)
    # In production: blocks /tmp
    return validate_path(path_str, "session file")

# For unit tests that need to verify security:
def test_production_blocks_system_temp():
    temp_path = Path("/tmp/evil.json")
    with pytest.raises(ValueError):
        validate_path(temp_path, "test", test_mode=False)
```

## API Reference

### Module: `plugins/autonomous-dev/lib/security_utils.py`

#### Constants

```python
PROJECT_ROOT: Path                    # Project root directory
SYSTEM_TEMP: Path                     # System temp directory
MAX_MESSAGE_LENGTH: int = 10000       # 10KB limit
MAX_PATH_LENGTH: int = 4096           # POSIX limit
PYTEST_PATH_PATTERN: re.Pattern       # Pytest format regex
```

#### Functions

**validate_path()**
```python
def validate_path(
    path: Path | str,
    purpose: str,
    allow_missing: bool = False,
    test_mode: Optional[bool] = None
) -> Path:
    """Validate path is within project boundaries.

    Raises:
        ValueError: If path is invalid/outside whitelist
    """
```

**validate_pytest_path()**
```python
def validate_pytest_path(
    pytest_path: str,
    purpose: str = "pytest execution"
) -> str:
    """Validate pytest path format.

    Raises:
        ValueError: If format invalid
    """
```

**validate_input_length()**
```python
def validate_input_length(
    value: str,
    max_length: int,
    field_name: str,
    purpose: str = "input validation"
) -> str:
    """Validate string length.

    Raises:
        ValueError: If exceeds max_length
    """
```

**validate_agent_name()**
```python
def validate_agent_name(
    agent_name: str,
    purpose: str = "agent tracking"
) -> str:
    """Validate agent name format.

    Raises:
        ValueError: If format invalid
    """
```

**validate_github_issue()**
```python
def validate_github_issue(
    issue_number: int,
    purpose: str = "issue tracking"
) -> int:
    """Validate GitHub issue number.

    Raises:
        ValueError: If number out of range
    """
```

**audit_log()**
```python
def audit_log(
    event_type: str,
    status: str,
    context: Dict[str, Any]
) -> None:
    """Log security event to audit log."""
```

#### Exported Names

```python
__all__ = [
    "validate_path",
    "validate_pytest_path",
    "validate_input_length",
    "validate_agent_name",
    "validate_github_issue",
    "audit_log",
    "PROJECT_ROOT",
    "SYSTEM_TEMP",
]
```

## See Also

- **CHANGELOG.md** - Version history including security fixes
- **README.md** - Installation and usage guide
- **docs/sessions/** - Security audit reports and findings
- **plugins/autonomous-dev/lib/security_utils.py** - Source code with inline comments
