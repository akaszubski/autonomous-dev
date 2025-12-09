# Security Guide

**Last Updated**: 2025-12-09
**Status**: Production-ready security framework for path validation and input sanitization

This document describes the security architecture, vulnerabilities fixed, and best practices for using the security utilities.

## Table of Contents

1. [Overview](#overview)
2. [Security Module: security_utils.py](#security-module-security_utilspy)
3. [Path Validation](#path-validation)
4. [Input Validation](#input-validation)
5. [Audit Logging](#audit-logging)
6. [Test Mode Security](#test-mode-security)
7. [Performance Profiler Security](#performance-profiler-security)
8. [User State Manager Security](#user-state-manager-security)
9. [Vulnerability Fixes (v3.4.1 - v3.4.3)](#vulnerability-fixes)
10. [Best Practices](#best-practices)
11. [API Reference](#api-reference)

## Overview

The autonomous-dev plugin implements a **centralized security framework** to prevent common vulnerabilities:

- **CWE-20**: Improper Input Validation (format and length checking)
- **CWE-22**: Path Traversal (prevent ../ style attacks)
- **CWE-59**: Improper Link Resolution (detect and block symlinks)
- **CWE-117**: Improper Output Neutralization (secure audit logging, log injection prevention)
- **CWE-400**: Uncontrolled Resource Consumption (length validation)
- **CWE-95**: Improper Neutralization of Directives (input validation)

All security-sensitive operations use the centralized `security_utils.py` module to ensure consistent enforcement. New library modules like `performance_profiler.py` integrate security validation into their initialization to prevent abuse.

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

## Performance Profiler Security

**Location**: `plugins/autonomous-dev/lib/performance_profiler.py` (539 lines, v3.6.0+)

**Purpose**: Prevent abuse of the performance timing library through input validation and audit logging.

The performance profiler accepts user inputs (agent_name, feature, log_path) that could be exploited if not properly validated. Three CWE vulnerabilities are specifically addressed:

### CWE-20: Improper Input Validation (agent_name parameter)

**Vulnerability**: Attacker could pass arbitrary strings as agent_name, potentially containing shell metacharacters or control characters that could cause injection attacks in log files or downstream processing.

**Mitigation**:
- Pattern validation: `^[a-zA-Z0-9_-]+$` (alphanumeric, hyphen, underscore only)
- Maximum length: 256 characters
- Automatic normalization: Whitespace stripped, lowercased
- Error handling: Raises `ValueError` with detailed message on invalid input

**Attack Scenarios Blocked**:
```python
# All of these are blocked:
PerformanceTimer("../../../etc/passwd", "feature")  # Path traversal attempt
PerformanceTimer("researcher; rm -rf /", "feature")  # Shell metacharacters
PerformanceTimer("researcher\necho hacked", "feature")  # Control characters
PerformanceTimer("x" * 300, "feature")  # Oversized input (max 256)
```

**Valid Examples**:
```python
# All of these are allowed:
PerformanceTimer("researcher", "feature")
PerformanceTimer("test-agent", "feature")
PerformanceTimer("test_agent_123", "feature")
```

### CWE-22: Path Traversal (log_path parameter)

**Vulnerability**: Attacker could specify log_path as `../../../../etc/passwd` or symlink targets outside the project directory, allowing arbitrary file write access.

**Mitigation**: 4-layer defense-in-depth validation:

1. **Layer 1 (String Checks)**:
   - Rejects ".." in path (prevents relative traversal)
   - Rejects absolute paths (requires relative)
   - Rejects null bytes (prevents truncation attacks)

2. **Layer 2 (Symlink Detection - Pre-Resolution)**:
   - Checks if path itself is a symlink
   - Rejects if symlink detected

3. **Layer 3 (Path Resolution & Post-Resolution Check)**:
   - Resolves path to canonical form with `.resolve()`
   - Checks if resolved path is still a symlink (resolves to another symlink)
   - Validates against path components

4. **Layer 4 (Whitelist Validation)**:
   - Restricts to `logs/` directory only (relative to PROJECT_ROOT)
   - Auto-creates `logs/` directory if needed
   - Validates path is a directory

**Attack Scenarios Blocked**:
```python
# All of these are blocked:
PerformanceTimer("agent", "feature", "/etc/passwd")  # Absolute path
PerformanceTimer("agent", "feature", "../../etc/passwd")  # Traversal
PerformanceTimer("agent", "feature", "/etc")  # Outside logs/
PerformanceTimer("agent", "feature", "/symlink_to_etc")  # Symlink outside project
PerformanceTimer("agent", "feature", "logs/../../../etc/passwd")  # Complex traversal
PerformanceTimer("agent", "feature", Path("/etc/passwd"))  # Path object attack
```

**Valid Examples**:
```python
# All of these are allowed:
PerformanceTimer("agent", "feature", Path("logs/metrics.json"))
PerformanceTimer("agent", "feature")  # Uses default logs/performance_metrics.json
with PerformanceTimer("agent", "feature", log_to_file=True):
    pass
```

### CWE-117: Log Injection (feature parameter)

**Vulnerability**: Attacker could pass feature strings with newlines, allowing injection of fake log entries:
```
Feature: Add auth
Internal log parsed here - attacker can insert lines
Next real log entry
```

**Mitigation**:
- Control character filtering: Rejects `\n`, `\r`, `\t`, `\x00-\x1f`, `\x7f`
- Maximum length: 10,000 characters (prevents log bloat attacks)
- Audit logging: All validation failures logged with CWE reference

**Attack Scenarios Blocked**:
```python
# All of these are blocked:
PerformanceTimer("agent", "Feature\nFAKE_LOG_ENTRY")  # Newline injection
PerformanceTimer("agent", "Feature\rCarriage return")  # CR injection
PerformanceTimer("agent", "Feature\t\t\t")  # Tab injection
PerformanceTimer("agent", "x" * 10001)  # Oversized input
PerformanceTimer("agent", "Feature\x1bReset")  # Control character (ESC)
```

**Valid Examples**:
```python
# All of these are allowed:
PerformanceTimer("agent", "Add user authentication")
PerformanceTimer("agent", "Feature with spaces and-hyphens_ok")
PerformanceTimer("agent", "Feature: Long (255 char) description")
```

### Validation Functions

All three validators are called automatically in `PerformanceTimer.__init__()`:

```python
from performance_profiler import PerformanceTimer

try:
    # Validation happens here in __init__()
    with PerformanceTimer("../../../etc/passwd", "feature\ninjection", log_to_file=True):
        pass
except ValueError as e:
    # Gets detailed error: "agent_name invalid: ... See docs/SECURITY.md"
    print(e)
```

### Audit Logging

All validation failures are logged via `security_utils.audit_log()`:

```python
{
    "timestamp": "2025-11-08T14:30:45.123456Z",
    "component": "performance_profiler",
    "action": "validation_failure",
    "details": {
        "parameter": "agent_name",
        "error": "agent_name invalid: contains invalid characters (CWE-20)",
        "input_length": 15,
        "attempted_value": "invalid..chars"
    }
}
```

**Log Location**: `logs/security_audit.log` (10MB rotation, 5 backups)

### Test Coverage

**92 security tests** in `tests/unit/lib/test_performance_profiler.py`:

| CWE | Test Category | Count | Status |
|-----|---------------|-------|--------|
| CWE-20 | agent_name validation | 28 tests | PASS |
| CWE-22 | log_path validation | 45 tests | PASS |
| CWE-117 | feature validation | 19 tests | PASS |
| **Total** | | **92 tests** | **100% PASS** |

**Coverage Areas**:
- Boundary conditions (empty strings, max length)
- Attack patterns (symlinks, traversal, injection)
- Error handling (graceful ValueError messages)
- Integration (validation in PerformanceTimer.__init__)

### Best Practices

**1. Let Validation Handle Errors**
```python
# GOOD: Let validator raise ValueError
try:
    timer = PerformanceTimer(untrusted_agent_name, untrusted_feature)
except ValueError as e:
    logger.error(f"Invalid input: {e}")
```

**2. Use Default Log Path When Possible**
```python
# GOOD: Uses default logs/performance_metrics.json
with PerformanceTimer("agent", "feature", log_to_file=True):
    do_work()

# LESS GOOD: Custom path requires validation
with PerformanceTimer("agent", "feature", Path("logs/custom.json"), log_to_file=True):
    do_work()
```

**3. Check Audit Logs After Suspicious Activity**
```bash
# View recent validation failures
tail -f logs/security_audit.log | grep validation_failure
```

## User State Manager Security

**Location**: `plugins/autonomous-dev/lib/user_state_manager.py` (415 lines, v3.12.0+)

**Purpose**: Secure user preference persistence with comprehensive path validation for state files stored outside the project directory (in `~/.autonomous-dev/`).

The user state manager stores first-run consent and user preferences in a JSON file at `~/.autonomous-dev/user_state.json`. Since this file is outside PROJECT_ROOT, it cannot use the standard `security_utils.validate_path()` function (which enforces project-relative paths). Instead, it implements a **custom three-layer security validation** specifically designed for user home directory files.

### CWE-22: Path Traversal Prevention

**Vulnerability**: Attacker could specify paths like `../../../../etc/passwd` to write state files to arbitrary system locations.

**Mitigation**: String-level detection before path resolution:

```python
# Layer 1: Detect ".." in string form (before resolution)
path_str = str(path)
if ".." in path_str:
    audit_log("security_violation", "failure", {
        "type": "path_traversal",
        "path": path_str,
        "component": "user_state_manager"
    })
    raise UserStateError(f"Path traversal detected: {path_str}")
```

**Attack Scenarios Blocked**:
```python
# All of these are blocked:
UserStateManager(Path("../../etc/passwd"))  # Relative traversal
UserStateManager(Path("~/.autonomous-dev/../../../etc/passwd"))  # Complex traversal
UserStateManager(Path("/tmp/../etc/passwd"))  # Absolute with traversal
```

### CWE-59: Symlink Attack Prevention (Two-Layer Defense)

**Vulnerability**: Attacker could create symlinks pointing to sensitive system files, causing the application to write state data to `/etc/passwd`, `/root/.ssh/authorized_keys`, or other critical files.

**Mitigation**: Two-layer symlink detection (before AND after path resolution):

**Layer 1: Pre-Resolution Check**
```python
# Check for symlink BEFORE resolution (user_state_manager.py:114)
if path.exists() and path.is_symlink():
    audit_log("security_violation", "failure", {
        "type": "symlink_attack",
        "path": str(path),
        "component": "user_state_manager"
    })
    raise UserStateError(f"Symlinks not allowed: {path}")
```

**Layer 2: Post-Resolution Check (Defense in Depth)**
```python
# Resolve path to absolute form
resolved_path = path.resolve()

# Check for symlink AFTER resolution (user_state_manager.py:133)
if resolved_path.is_symlink():
    audit_log("security_violation", "failure", {
        "type": "symlink_after_resolution",
        "path": str(resolved_path),
        "component": "user_state_manager"
    })
    raise UserStateError(f"Symlink detected after resolution: {resolved_path}")
```

**Why Two Layers?**:
- **Layer 1** catches direct symlinks: `~/.autonomous-dev/user_state.json` is itself a symlink
- **Layer 2** catches parent directory symlinks: `~/.autonomous-dev/` is a symlink to `/etc/`
- Defense in depth ensures no symlink escapes detection

**Attack Scenarios Blocked**:
```bash
# All of these are blocked:

# Direct symlink to system file
ln -s /etc/passwd ~/.autonomous-dev/user_state.json
# Layer 1 blocks: path.is_symlink() returns True

# Symlink directory escape
ln -s /etc ~/.autonomous-dev
# Layer 2 blocks: resolved_path still points to /etc/user_state.json

# Nested symlink chains
ln -s /tmp/evil ~/.autonomous-dev/user_state.json
ln -s /etc/passwd /tmp/evil
# Both layers catch this: Layer 1 detects first symlink, Layer 2 catches resolved target
```

### CWE-367: TOCTOU (Time-of-Check-Time-of-Use) Mitigation

**Vulnerability**: Race condition between checking file existence and reading file permissions. Attacker could exploit the time gap to change file permissions or replace the file with a symlink.

**Classic TOCTOU Attack**:
```python
# VULNERABLE CODE (DO NOT USE)
if path.exists():  # Check (time T1)
    if os.access(path, os.R_OK):  # Another check (time T2)
        data = path.read_text()  # Use (time T3)
# Attacker can modify file between T1 and T3
```

**Mitigation**: Atomic file access check using try/except pattern:

```python
# SECURE CODE (user_state_manager.py:181)
# Atomic check - no time gap between check and use
if resolved_path.exists():
    try:
        # Atomically test read access (EAFP pattern)
        resolved_path.read_text()
    except PermissionError:
        raise UserStateError(f"Permission denied: {resolved_path}")
```

**Why Atomic?**:
- `read_text()` performs **both** permission check AND read operation in single syscall
- No time gap for attacker to exploit
- If permissions change, the read itself fails (not the check)
- EAFP (Easier to Ask Forgiveness than Permission) pattern is race-condition safe

**Attack Scenario Blocked**:
```bash
# Attacker attempt:
# T1: Application checks: path.exists() → True
# T2: Attacker: chmod 000 ~/.autonomous-dev/user_state.json
# T3: Application reads: Would fail with "Permission denied"
# Result: Application never reads unintended file, raises clean error
```

### Directory Whitelist Validation

In addition to the three CWE mitigations, user_state_manager enforces directory whitelist validation:

```python
# Ensure path is within home directory or temp directory (for tests)
home_dir = Path.home().resolve()
temp_dir = Path(tempfile.gettempdir()).resolve()

try:
    resolved_path.relative_to(home_dir)
    is_in_home = True
except ValueError:
    pass

try:
    resolved_path.relative_to(temp_dir)
    is_in_temp = True
except ValueError:
    pass

if not (is_in_home or is_in_temp):
    audit_log("security_violation", "failure", {
        "type": "path_outside_allowed_dirs",
        "path": str(resolved_path),
        "home": str(home_dir),
        "temp": str(temp_dir),
        "component": "user_state_manager"
    })
    raise UserStateError(f"Path must be within home directory: {resolved_path}")
```

**Allowed Locations**:
- User home directory: `~/.autonomous-dev/` (production use)
- System temp directory: `/tmp` or `%TEMP%` (test mode only)

**Blocked Locations**:
- System directories: `/etc`, `/usr`, `/var`
- Other users' home directories: `/home/other_user/`
- Network mounts: `/mnt`, `/media`

### Audit Logging

All security violations are logged to `logs/security_audit.log`:

```json
{
  "timestamp": "2025-11-11T10:30:45.123456Z",
  "event_type": "security_violation",
  "status": "failure",
  "context": {
    "type": "symlink_attack",
    "path": "/home/user/.autonomous-dev/user_state.json",
    "component": "user_state_manager"
  }
}
```

**Log Rotation**: 10MB max size, 5 backups (50MB total history)

### Test Coverage

**123 comprehensive tests** validate all security layers:

| Test Category | Count | Coverage |
|---------------|-------|----------|
| Path validation (CWE-22) | 41 tests | Path traversal, absolute paths, malformed paths |
| Symlink detection (CWE-59) | 28 tests | Direct symlinks, parent symlinks, nested chains |
| Permission handling (CWE-367) | 15 tests | Permission denied, atomic checks, race conditions |
| Corrupted state recovery | 12 tests | Invalid JSON, missing fields, file corruption |
| Edge cases | 27 tests | Empty strings, concurrent access, disk full |
| **Total** | **123 tests** | **100% pass rate** |

### Why Not security_utils.validate_path()?

The standard `security_utils.validate_path()` function enforces project-relative paths (must be within PROJECT_ROOT). However, user state files are stored in `~/.autonomous-dev/` (outside the project) for legitimate reasons:

1. **User-specific data**: Different users on same system need separate state files
2. **Project-independent**: State persists across different project directories
3. **System convention**: User config files belong in home directory (~/.config/, ~/.local/, etc.)

Therefore, user_state_manager implements **custom validation** specifically for home directory paths, maintaining the same security rigor (CWE-22, CWE-59, CWE-367 prevention) but with a different whitelist (home directory instead of project directory).

### Best Practices

**1. Trust the Validation**
```python
# GOOD: Let user_state_manager handle security
from plugins.autonomous_dev.lib.user_state_manager import UserStateManager

try:
    manager = UserStateManager(user_provided_path)
except UserStateError as e:
    logger.error(f"Invalid state file path: {e}")
```

**2. Use Default Path When Possible**
```python
# GOOD: Uses default ~/.autonomous-dev/user_state.json
from plugins.autonomous_dev.lib.user_state_manager import (
    DEFAULT_STATE_FILE, UserStateManager
)

manager = UserStateManager(DEFAULT_STATE_FILE)
```

**3. Monitor Audit Logs for Attacks**
```bash
# Check for symlink attacks
grep "symlink_attack" logs/security_audit.log

# Check for path traversal attempts
grep "path_traversal" logs/security_audit.log

# View all security violations
grep "security_violation" logs/security_audit.log | jq .
```

### Example Usage

```python
from pathlib import Path
from plugins.autonomous_dev.lib.user_state_manager import (
    UserStateManager, DEFAULT_STATE_FILE, UserStateError
)

# Safe usage with default path
try:
    manager = UserStateManager(DEFAULT_STATE_FILE)

    # Check first run
    if manager.is_first_run():
        print("First run detected")
        manager.record_first_run_complete()

    # Set preference
    manager.set_preference("auto_git_enabled", True)
    manager.save()

except UserStateError as e:
    # Validation failed - path is unsafe
    print(f"Security violation: {e}")
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
