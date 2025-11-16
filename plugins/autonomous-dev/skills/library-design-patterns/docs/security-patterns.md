# Security-First Design Patterns

**Pattern Type**: Security Architecture
**Skill**: library-design-patterns
**Version**: 1.0.0

---

## Overview

Security-first design builds security validation, input sanitization, and audit logging into library architecture from the start, rather than adding it later as an afterthought.

**Core Principle**: Security is not a feature you add; it's a property of the architecture.

---

## Security Layers

### Layer 1: Input Validation

**Purpose**: Validate all user input before processing

**Principles**:
- Validate type, format, and range
- Reject invalid input early
- Provide clear error messages
- Never trust user input

**Example**:
```python
def process_config(config_path: str, *, max_size_mb: int = 10) -> Config:
    """Load and validate configuration file.

    Args:
        config_path: Path to config file
        max_size_mb: Maximum file size in MB (default: 10)

    Raises:
        ValueError: If input invalid
        FileNotFoundError: If file doesn't exist
        SecurityError: If file too large (potential DoS)
    """
    # Type validation
    if not isinstance(config_path, (str, Path)):
        raise TypeError(f"config_path must be str or Path, got {type(config_path)}")

    # Path validation
    path = Path(config_path)
    if not path.exists():
        raise FileNotFoundError(f"Config file not found: {path}")

    # Size validation (DoS prevention)
    size_mb = path.stat().st_size / (1024 * 1024)
    if size_mb > max_size_mb:
        raise SecurityError(
            f"Config file too large: {size_mb:.1f}MB (max: {max_size_mb}MB)\n"
            f"This may indicate a security issue or misconfiguration."
        )

    # Extension validation
    if path.suffix not in {'.json', '.yaml', '.yml'}:
        raise ValueError(
            f"Invalid config format: {path.suffix}\n"
            f"Expected: .json, .yaml, or .yml"
        )

    return _load_config(path)
```

---

### Layer 2: Path Traversal Prevention (CWE-22)

**Purpose**: Prevent attackers from accessing files outside allowed directories

**Techniques**:
- Whitelist allowed directories
- Resolve symlinks before validation
- Check path boundaries
- Reject .. and absolute paths from user input

**Example**:
```python
from pathlib import Path
from typing import List

class SecurityError(Exception):
    """Raised when security validation fails."""
    pass

def validate_path(
    user_path: str,
    *,
    allowed_dirs: List[Path],
    must_exist: bool = True
) -> Path:
    """Validate path against whitelist to prevent CWE-22 path traversal.

    Args:
        user_path: User-provided path (untrusted input)
        allowed_dirs: Whitelist of allowed directories
        must_exist: Whether path must exist

    Returns:
        Validated Path object

    Raises:
        SecurityError: If path outside allowed directories
        FileNotFoundError: If must_exist=True and path doesn't exist

    Security:
        - CWE-22 Prevention: Whitelist validation
        - Symlink Resolution: Prevents symlink attacks
        - Boundary Checking: Ensures path within allowed dirs
    """
    # Convert to Path object
    path = Path(user_path)

    # Resolve symlinks to prevent symlink attacks (CWE-59)
    try:
        resolved_path = path.resolve(strict=must_exist)
    except (OSError, RuntimeError) as e:
        raise SecurityError(f"Cannot resolve path: {e}")

    # Whitelist validation (CWE-22 prevention)
    is_allowed = any(
        resolved_path.is_relative_to(allowed_dir.resolve())
        for allowed_dir in allowed_dirs
    )

    if not is_allowed:
        # Security-safe error message (don't leak full path)
        raise SecurityError(
            f"Access denied: Path outside allowed directories\n"
            f"Allowed directories: {', '.join(str(d) for d in allowed_dirs)}"
        )

    return resolved_path
```

**Usage**:
```python
# Define whitelist
ALLOWED_DIRS = [
    Path("/home/user/project"),
    Path("/tmp/project-temp")
]

# Validate user input
user_input = request.get("file_path")  # Untrusted input
safe_path = validate_path(user_input, allowed_dirs=ALLOWED_DIRS)

# Now safe to use
with safe_path.open('r') as f:
    data = f.read()
```

---

### Layer 3: Command Injection Prevention (CWE-78)

**Purpose**: Prevent attackers from injecting malicious commands

**Techniques**:
- Use subprocess with argument arrays (not shell strings)
- Never use shell=True with user input
- Validate command arguments
- Use whitelist of allowed commands

**Example**:
```python
import subprocess
from typing import List, Optional

def safe_subprocess(
    command: List[str],
    *,
    allowed_commands: Optional[List[str]] = None,
    timeout: int = 30
) -> subprocess.CompletedProcess:
    """Execute subprocess with command injection prevention.

    Args:
        command: Command and arguments as list (NOT string!)
        allowed_commands: Whitelist of allowed commands (optional)
        timeout: Maximum execution time in seconds

    Returns:
        Completed subprocess result

    Raises:
        SecurityError: If command not in whitelist
        subprocess.TimeoutExpired: If command exceeds timeout

    Security:
        - CWE-78 Prevention: Argument array (no shell injection)
        - Command Whitelist: Only approved commands allowed
        - Timeout: Prevents DoS via long-running commands

    Example:
        >>> result = safe_subprocess(
        ...     ["gh", "issue", "create", "--title", user_title],
        ...     allowed_commands=["gh"]
        ... )
    """
    # Command whitelist validation
    if allowed_commands is not None:
        base_command = command[0]
        if base_command not in allowed_commands:
            raise SecurityError(
                f"Command not allowed: {base_command}\n"
                f"Allowed: {', '.join(allowed_commands)}"
            )

    # Execute with argument array (CWE-78 prevention)
    # NEVER use shell=True with user input!
    try:
        result = subprocess.run(
            command,  # List of arguments (safe)
            capture_output=True,
            text=True,
            timeout=timeout,
            check=True,
            shell=False  # CRITICAL: Never True with user input
        )
        return result
    except subprocess.TimeoutExpired:
        raise TimeoutError(f"Command timed out after {timeout}s: {command[0]}")
```

**Anti-Pattern (DANGEROUS)**:
```python
# ❌ NEVER DO THIS - Vulnerable to command injection!
user_input = request.get("filename")
command = f"cat {user_input}"  # User can inject: "file.txt; rm -rf /"
subprocess.run(command, shell=True)  # DANGEROUS!
```

**Correct Pattern**:
```python
# ✅ Safe - Uses argument array
user_input = request.get("filename")
safe_path = validate_path(user_input, allowed_dirs=[DATA_DIR])
subprocess.run(
    ["cat", str(safe_path)],  # Argument array
    shell=False  # Safe
)
```

---

### Layer 4: Log Injection Prevention (CWE-117)

**Purpose**: Prevent attackers from injecting malicious content into logs

**Techniques**:
- Sanitize all log messages
- Escape newlines and special characters
- Use structured logging
- Never log raw user input

**Example**:
```python
import re
from pathlib import Path

def sanitize_for_logging(value: str, *, max_length: int = 200) -> str:
    """Sanitize value for safe logging (CWE-117 prevention).

    Args:
        value: Value to sanitize
        max_length: Maximum length (default: 200)

    Returns:
        Sanitized string safe for logging

    Security:
        - CWE-117 Prevention: Escape newlines, control characters
        - Length Limiting: Prevent log flooding
        - Character Filtering: Remove dangerous characters
    """
    # Remove/escape control characters
    sanitized = re.sub(r'[\r\n\t]', ' ', value)
    sanitized = re.sub(r'[^\x20-\x7E]', '?', sanitized)  # Non-printable → ?

    # Limit length to prevent log flooding
    if len(sanitized) > max_length:
        sanitized = sanitized[:max_length] + "..."

    return sanitized


def audit_log(event: str, **kwargs) -> None:
    """Log security-relevant event with sanitization.

    Args:
        event: Event type (e.g., 'file_accessed', 'command_executed')
        **kwargs: Event details (will be sanitized)

    Security:
        - CWE-117 Prevention: Sanitizes all logged values
        - Structured Logging: Prevents log injection
        - Audit Trail: Security events logged to security_audit.log
    """
    # Sanitize all values
    sanitized_kwargs = {
        key: sanitize_for_logging(str(value))
        for key, value in kwargs.items()
    }

    # Write to audit log
    log_path = Path("logs/security_audit.log")
    log_path.parent.mkdir(parents=True, exist_ok=True)

    with log_path.open('a') as f:
        timestamp = datetime.now().isoformat()
        log_entry = f"{timestamp} | {event} | {sanitized_kwargs}\n"
        f.write(log_entry)
```

**Usage**:
```python
# Safe logging with sanitization
user_input = request.get("filename")  # May contain newlines, control chars
audit_log(
    "file_accessed",
    user=username,
    path=user_input  # Automatically sanitized
)

# Output: "2025-11-16T10:30:00 | file_accessed | {'user': 'alice', 'path': 'data.txt'}"
# Even if user_input was "data.txt\n[ADMIN] Security disabled", it gets sanitized
```

---

### Layer 5: Audit Logging

**Purpose**: Record security-relevant operations for forensics and compliance

**What to Log**:
- File access (reads, writes, deletes)
- Command execution
- Authentication events
- Authorization failures
- Configuration changes
- Security errors

**Example**:
```python
from datetime import datetime
from pathlib import Path
from typing import Optional

def audit_log(
    event: str,
    *,
    user: Optional[str] = None,
    **details
) -> None:
    """Log security event to audit trail.

    Args:
        event: Event type (e.g., 'file_accessed', 'command_executed')
        user: Username (if available)
        **details: Additional event details

    Security:
        - CWE-117 Prevention: Sanitizes all logged values
        - Audit Trail: Immutable log for forensics
        - Compliance: Meets audit requirements
    """
    log_dir = Path("logs")
    log_dir.mkdir(exist_ok=True)

    audit_file = log_dir / "security_audit.log"

    # Build log entry
    timestamp = datetime.now().isoformat()
    user_str = f" user={user}" if user else ""
    details_str = " ".join(f"{k}={sanitize_for_logging(str(v))}" for k, v in details.items())

    log_entry = f"{timestamp} | {event}{user_str} | {details_str}\n"

    # Append to audit log (append-only)
    with audit_file.open('a') as f:
        f.write(log_entry)
```

**Usage**:
```python
# Log file access
audit_log("file_accessed", user=current_user, path=filepath, operation="read")

# Log command execution
audit_log("command_executed", user=current_user, command="gh issue create", args=args)

# Log security error
audit_log("security_error", user=current_user, error="path_traversal_attempt", path=user_path)
```

---

## Complete Example: Secure File Processor

```python
from pathlib import Path
from typing import List, Optional
import subprocess

class SecurityError(Exception):
    """Raised when security validation fails."""
    pass


def process_user_file(
    filepath: str,
    *,
    allowed_dirs: List[Path],
    max_size_mb: int = 10,
    user: Optional[str] = None
) -> str:
    """Process user-provided file with comprehensive security.

    Demonstrates all 5 security layers:
    1. Input validation
    2. Path traversal prevention (CWE-22)
    3. Command injection prevention (CWE-78)
    4. Log injection prevention (CWE-117)
    5. Audit logging

    Args:
        filepath: User-provided file path (untrusted)
        allowed_dirs: Whitelist of allowed directories
        max_size_mb: Maximum file size in MB
        user: Current username for audit trail

    Returns:
        Processing result

    Raises:
        SecurityError: If security validation fails
        ValueError: If input invalid

    Security:
        - CWE-22: Path traversal prevention via whitelist
        - CWE-78: Command injection prevention via argument arrays
        - CWE-117: Log injection prevention via sanitization
        - Audit Trail: All operations logged
    """
    # Layer 1: Input validation
    if not isinstance(filepath, str):
        raise TypeError(f"filepath must be string, got {type(filepath)}")

    # Layer 2: Path traversal prevention (CWE-22)
    try:
        safe_path = validate_path(filepath, allowed_dirs=allowed_dirs, must_exist=True)
    except SecurityError as e:
        # Layer 5: Audit security failure
        audit_log("security_error", user=user, error="path_traversal_attempt", path=filepath)
        raise

    # Additional validation: file size (DoS prevention)
    size_mb = safe_path.stat().st_size / (1024 * 1024)
    if size_mb > max_size_mb:
        audit_log("security_error", user=user, error="file_too_large", path=str(safe_path), size_mb=size_mb)
        raise SecurityError(f"File too large: {size_mb:.1f}MB (max: {max_size_mb}MB)")

    # Layer 5: Audit file access
    audit_log("file_accessed", user=user, path=str(safe_path), operation="process")

    # Process file (example: count lines with wc)
    # Layer 3: Command injection prevention (CWE-78)
    result = subprocess.run(
        ["wc", "-l", str(safe_path)],  # Argument array (safe)
        capture_output=True,
        text=True,
        timeout=30,
        shell=False  # Never True with user input!
    )

    # Layer 5: Audit command execution
    audit_log("command_executed", user=user, command="wc", args=str(safe_path))

    return result.stdout.strip()
```

---

## Security Checklist

When designing security-sensitive libraries:

- [ ] **Input Validation**
  - [ ] Validate all user input (type, format, range)
  - [ ] Reject invalid input with clear errors
  - [ ] Never trust user input

- [ ] **Path Security (CWE-22)**
  - [ ] Use whitelist of allowed directories
  - [ ] Resolve symlinks before validation
  - [ ] Check path boundaries
  - [ ] Reject .. and absolute paths from user

- [ ] **Command Security (CWE-78)**
  - [ ] Use subprocess with argument arrays
  - [ ] Never use shell=True with user input
  - [ ] Whitelist allowed commands
  - [ ] Set timeouts on subprocess calls

- [ ] **Log Security (CWE-117)**
  - [ ] Sanitize all logged values
  - [ ] Escape newlines and control characters
  - [ ] Use structured logging
  - [ ] Limit log entry length

- [ ] **Audit Trail**
  - [ ] Log security-relevant operations
  - [ ] Include timestamp, user, operation
  - [ ] Write to append-only log file
  - [ ] Sanitize audit log entries

- [ ] **Documentation**
  - [ ] Document security properties
  - [ ] Include CWE references
  - [ ] Provide secure usage examples
  - [ ] Warn about dangerous patterns

---

## References

- **CWE-22**: Path Traversal - https://cwe.mitre.org/data/definitions/22.html
- **CWE-59**: Improper Link Resolution - https://cwe.mitre.org/data/definitions/59.html
- **CWE-78**: Command Injection - https://cwe.mitre.org/data/definitions/78.html
- **CWE-117**: Log Injection - https://cwe.mitre.org/data/definitions/117.html
- **Template**: `templates/library-template.py`
- **Example**: `examples/security-validation-example.py`
- **Cross-Reference**: security-patterns skill (comprehensive OWASP guide)
