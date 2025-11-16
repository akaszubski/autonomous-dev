#!/usr/bin/env python3
"""Security validation example demonstrating security-first design.

This example shows how to build comprehensive security validation
into library architecture from the start, covering all major CWE
vulnerabilities in the OWASP Top 10.

See:
    - plugins/autonomous-dev/lib/security_utils.py (actual implementation)
    - skills/library-design-patterns/docs/security-patterns.md
    - skills/security-patterns (comprehensive OWASP guidance)
"""

from pathlib import Path
from typing import List, Optional, Dict, Any
import subprocess
import re
from datetime import datetime


class SecurityError(Exception):
    """Raised when security validation fails."""
    pass


# ============================================================================
# Layer 1: Input Validation
# ============================================================================

def validate_input(
    value: str,
    *,
    max_length: int = 1000,
    allowed_chars: Optional[str] = None
) -> str:
    """Validate user input against constraints.

    Args:
        value: Input to validate
        max_length: Maximum allowed length (default: 1000)
        allowed_chars: Regex pattern for allowed characters (default: None)

    Returns:
        Validated input string

    Raises:
        ValueError: If input fails validation

    Security:
        - Input Length: Prevents DoS via oversized input
        - Character Filtering: Prevents injection attacks

    Example:
        >>> validate_input("hello123", max_length=100)
        'hello123'
        >>> validate_input("a" * 2000, max_length=1000)
        ValueError: Input too long
    """
    # Length validation (DoS prevention)
    if len(value) > max_length:
        raise ValueError(
            f"Input too long: {len(value)} chars (max: {max_length})\n"
            f"This may indicate a security issue or misconfiguration."
        )

    # Character validation (injection prevention)
    if allowed_chars and not re.match(allowed_chars, value):
        raise ValueError(
            f"Input contains invalid characters\n"
            f"Allowed pattern: {allowed_chars}"
        )

    return value


# ============================================================================
# Layer 2: Path Traversal Prevention (CWE-22)
# ============================================================================

def validate_path_secure(
    path_input: str,
    *,
    allowed_dirs: List[Path]
) -> Path:
    """Validate path against whitelist to prevent CWE-22 path traversal.

    Args:
        path_input: User-provided path (untrusted)
        allowed_dirs: Whitelist of allowed directories

    Returns:
        Validated and resolved Path object

    Raises:
        SecurityError: If path outside allowed directories
        ValueError: If path is invalid

    Security:
        - CWE-22 Prevention: Whitelist validation
        - CWE-59 Prevention: Symlink resolution
        - Boundary Checking: Ensures path within allowed dirs

    Example:
        >>> SAFE_DIRS = [Path("/tmp"), Path("/var/tmp")]
        >>> path = validate_path_secure("/tmp/data.txt", allowed_dirs=SAFE_DIRS)
        >>> # Safe to use path now
    """
    # Convert to Path
    path = Path(path_input)

    # Resolve symlinks (CWE-59 prevention)
    try:
        resolved_path = path.resolve(strict=False)
    except (OSError, RuntimeError) as e:
        raise SecurityError(f"Cannot resolve path: {e}")

    # Whitelist validation (CWE-22 prevention)
    is_allowed = any(
        resolved_path.is_relative_to(allowed_dir.resolve())
        for allowed_dir in allowed_dirs
    )

    if not is_allowed:
        # Security-safe error (don't leak full path)
        raise SecurityError(
            f"Access denied: Path outside allowed directories\n"
            f"Allowed directories: {', '.join(str(d) for d in allowed_dirs)}"
        )

    return resolved_path


# ============================================================================
# Layer 3: Command Injection Prevention (CWE-78)
# ============================================================================

def safe_subprocess(
    command: List[str],
    *,
    allowed_commands: List[str],
    timeout: int = 30
) -> subprocess.CompletedProcess:
    """Execute subprocess with command injection prevention.

    Args:
        command: Command and arguments as list (NOT string!)
        allowed_commands: Whitelist of allowed commands
        timeout: Maximum execution time in seconds (default: 30)

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
        ...     ["gh", "issue", "create", "--title", "My Issue"],
        ...     allowed_commands=["gh", "git"]
        ... )
    """
    # Command whitelist validation
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
        raise SecurityError(f"Command timed out after {timeout}s: {base_command}")


# ============================================================================
# Layer 4: Log Injection Prevention (CWE-117)
# ============================================================================

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

    Example:
        >>> sanitize_for_logging("normal text")
        'normal text'
        >>> sanitize_for_logging("text\\nwith\\nnewlines")
        'text with newlines'
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

    Example:
        >>> audit_log("file_accessed", user="alice", path="/tmp/data.txt")
        # Logs: "2025-11-16T10:30:00 | file_accessed | user=alice path=/tmp/data.txt"
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
        details = " ".join(f"{k}={v}" for k, v in sanitized_kwargs.items())
        log_entry = f"{timestamp} | {event} | {details}\n"
        f.write(log_entry)


# ============================================================================
# COMPLETE EXAMPLE: Secure File Processor
# ============================================================================

def process_user_file_secure(
    filepath: str,
    *,
    allowed_dirs: List[Path],
    max_size_mb: int = 10,
    user: str
) -> str:
    """Process user file with comprehensive security (all 5 layers).

    Demonstrates:
    1. Input validation
    2. Path traversal prevention (CWE-22)
    3. Command injection prevention (CWE-78)
    4. Log injection prevention (CWE-117)
    5. Audit logging

    Args:
        filepath: User-provided file path (untrusted)
        allowed_dirs: Whitelist of allowed directories
        max_size_mb: Maximum file size in MB (default: 10)
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

    Example:
        >>> SAFE_DIRS = [Path("/tmp"), Path("/home/user/data")]
        >>> result = process_user_file_secure(
        ...     "/tmp/data.txt",
        ...     allowed_dirs=SAFE_DIRS,
        ...     user="alice"
        ... )
    """
    # Layer 1: Input validation
    filepath = validate_input(filepath, max_length=500)

    # Layer 2: Path traversal prevention (CWE-22)
    try:
        safe_path = validate_path_secure(filepath, allowed_dirs=allowed_dirs)
    except SecurityError as e:
        # Layer 5: Audit security failure
        audit_log(
            "security_error",
            user=user,
            error="path_traversal_attempt",
            path=filepath
        )
        raise

    # Validate file size (DoS prevention)
    if not safe_path.exists():
        raise FileNotFoundError(f"File not found: {safe_path}")

    size_mb = safe_path.stat().st_size / (1024 * 1024)
    if size_mb > max_size_mb:
        audit_log(
            "security_error",
            user=user,
            error="file_too_large",
            path=str(safe_path),
            size_mb=f"{size_mb:.1f}"
        )
        raise SecurityError(f"File too large: {size_mb:.1f}MB (max: {max_size_mb}MB)")

    # Layer 5: Audit file access
    audit_log("file_accessed", user=user, path=str(safe_path), operation="process")

    # Process file (example: count lines with wc)
    # Layer 3: Command injection prevention (CWE-78)
    result = safe_subprocess(
        ["wc", "-l", str(safe_path)],
        allowed_commands=["wc", "cat", "head", "tail"]
    )

    # Layer 5: Audit command execution
    audit_log("command_executed", user=user, command="wc", file=str(safe_path))

    return result.stdout.strip()


# ============================================================================
# USAGE EXAMPLES
# ============================================================================

def example_usage():
    """Demonstrate security validation in action."""

    # Define security context
    SAFE_DIRS = [
        Path("/tmp"),
        Path("/var/tmp"),
        Path.home() / "project"
    ]

    CURRENT_USER = "alice"

    # Example 1: Valid file (all security checks pass)
    try:
        result = process_user_file_secure(
            "/tmp/data.txt",
            allowed_dirs=SAFE_DIRS,
            user=CURRENT_USER
        )
        print(f"✅ Processed: {result}")
    except (SecurityError, FileNotFoundError) as e:
        print(f"❌ Error: {e}")

    # Example 2: Path traversal attempt (blocked by CWE-22 prevention)
    try:
        result = process_user_file_secure(
            "/etc/passwd",  # Outside allowed directories!
            allowed_dirs=SAFE_DIRS,
            user=CURRENT_USER
        )
    except SecurityError as e:
        print(f"✅ Blocked path traversal: {e}")

    # Example 3: File too large (blocked by DoS prevention)
    try:
        result = process_user_file_secure(
            "/tmp/huge_file.bin",
            allowed_dirs=SAFE_DIRS,
            max_size_mb=1,  # Small limit
            user=CURRENT_USER
        )
    except SecurityError as e:
        print(f"✅ Blocked oversized file: {e}")

    # Check audit log
    audit_path = Path("logs/security_audit.log")
    if audit_path.exists():
        print("\n📋 Audit Log:")
        print(audit_path.read_text())


if __name__ == "__main__":
    print("Security Validation Example")
    print("=" * 60)
    example_usage()
