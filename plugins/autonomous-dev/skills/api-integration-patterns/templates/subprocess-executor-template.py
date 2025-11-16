#!/usr/bin/env python3
"""Safe subprocess execution template with CWE-78 prevention.

See: skills/api-integration-patterns/docs/subprocess-safety.md
"""

import subprocess
from typing import List, Optional


class SecurityError(Exception):
    """Raised when security validation fails."""
    pass


def safe_subprocess(
    command: List[str],
    *,
    allowed_commands: Optional[List[str]] = None,
    timeout: int = 30
) -> subprocess.CompletedProcess:
    """Execute subprocess with command injection prevention.

    Args:
        command: Command and arguments as list (NOT string!)
        allowed_commands: Whitelist of allowed commands (default: None)
        timeout: Maximum execution time in seconds (default: 30)

    Returns:
        Completed subprocess result

    Raises:
        SecurityError: If command not in whitelist
        subprocess.TimeoutExpired: If command exceeds timeout
        subprocess.CalledProcessError: If command fails

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


# Example usage
if __name__ == "__main__":
    # ✅ SAFE: Argument array
    result = safe_subprocess(
        ["echo", "hello", "world"],
        allowed_commands=["echo", "ls", "cat"]
    )
    print(result.stdout)

    # ❌ This would raise SecurityError
    try:
        safe_subprocess(
            ["rm", "-rf", "/"],
            allowed_commands=["echo", "ls"]
        )
    except SecurityError as e:
        print(f"Blocked: {e}")
