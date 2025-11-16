#!/usr/bin/env python3
"""Safe subprocess execution examples demonstrating CWE-78 prevention.

See: skills/api-integration-patterns/docs/subprocess-safety.md
"""

import subprocess
from typing import List


def unsafe_example_do_not_use(user_input: str):
    """❌ DANGEROUS - Command injection vulnerability!

    DO NOT USE THIS PATTERN!

    Args:
        user_input: User-provided input (UNTRUSTED)
    """
    # ❌ VULNERABLE: Shell=True with user input
    command = f"cat {user_input}"
    subprocess.run(command, shell=True)

    # What if user_input is: "file.txt; rm -rf /"
    # Command becomes: "cat file.txt; rm -rf /"
    # This deletes everything!


def safe_example(filepath: str):
    """✅ SAFE - Uses argument array to prevent injection.

    Args:
        filepath: File path to read
    """
    # ✅ SAFE: Argument array, no shell
    result = subprocess.run(
        ["cat", filepath],  # List of arguments
        capture_output=True,
        text=True,
        timeout=10,
        check=True,
        shell=False  # CRITICAL
    )

    return result.stdout


def safe_example_with_whitelist(command: List[str]):
    """✅ SAFE - Argument array + command whitelist.

    Args:
        command: Command and arguments as list

    Raises:
        SecurityError: If command not in whitelist
    """
    # Whitelist of allowed commands
    ALLOWED_COMMANDS = ["gh", "git", "cat", "ls"]

    # Validate command
    base_command = command[0]
    if base_command not in ALLOWED_COMMANDS:
        raise SecurityError(f"Command not allowed: {base_command}")

    # Execute safely
    result = subprocess.run(
        command,
        capture_output=True,
        text=True,
        timeout=30,
        check=True,
        shell=False
    )

    return result.stdout


# Demonstration
if __name__ == "__main__":
    print("Safe Subprocess Examples")
    print("=" * 60)

    # Example 1: Safe file read
    try:
        content = safe_example("/etc/hosts")
        print(f"File content (first 100 chars):\n{content[:100]}...")
    except subprocess.CalledProcessError as e:
        print(f"Error: {e}")

    # Example 2: Safe GitHub CLI call
    try:
        result = safe_example_with_whitelist(
            ["gh", "auth", "status"]
        )
        print(f"\nGitHub auth status:\n{result}")
    except Exception as e:
        print(f"Error: {e}")

    # Example 3: Blocked dangerous command
    try:
        safe_example_with_whitelist(["rm", "-rf", "/"])
    except SecurityError as e:
        print(f"\n✅ Blocked dangerous command: {e}")
