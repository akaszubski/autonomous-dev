#!/usr/bin/env python3
"""
PostToolUse Error Capture Hook - Captures tool failures for analysis.

Hooks into PostToolUse lifecycle to capture all tool failures (non-zero exit codes,
stderr errors) and log them to .claude/logs/errors/{date}.jsonl for analysis.

Input (stdin):
{
  "tool_name": "Bash",
  "tool_input": {"command": "pytest tests/"},
  "tool_result": {
    "exit_code": 1,
    "stdout": "...",
    "stderr": "Error: test failed"
  }
}

Output (stdout):
{
  "hookSpecificOutput": {
    "hookEventName": "PostToolUse"
  }
}

Exit code: 0 (always - non-blocking hook)

Security:
- CWE-117: Log injection prevention via sanitization
- CWE-532: Secret redaction for API keys, tokens
- CWE-22: Path validation via validation.py
- CWE-400: Resource limits (max message length)

Date: 2025-12-13
Issue: #124 (Automated error capture and analysis)
Agent: implementer
"""

import json
import sys
from pathlib import Path


def find_lib_directory(hook_path: Path) -> Path | None:
    """
    Find lib directory dynamically.

    Checks multiple locations in order:
    1. Development: plugins/autonomous-dev/lib (relative to hook)
    2. Local install: ~/.claude/lib
    3. Marketplace: ~/.claude/plugins/autonomous-dev/lib

    Args:
        hook_path: Path to this hook script

    Returns:
        Path to lib directory if found, None otherwise (graceful failure)
    """
    # Try development location first
    dev_lib = hook_path.parent.parent / "lib"
    if dev_lib.exists() and dev_lib.is_dir():
        return dev_lib

    # Try local install
    home = Path.home()
    local_lib = home / ".claude" / "lib"
    if local_lib.exists() and local_lib.is_dir():
        return local_lib

    # Try marketplace location
    marketplace_lib = home / ".claude" / "plugins" / "autonomous-dev" / "lib"
    if marketplace_lib.exists() and marketplace_lib.is_dir():
        return marketplace_lib

    return None


# Add lib directory to path dynamically
LIB_DIR = find_lib_directory(Path(__file__))
if LIB_DIR:
    sys.path.insert(0, str(LIB_DIR))


# Error patterns to detect in stderr
ERROR_PATTERNS = [
    r"error:",
    r"Error:",
    r"ERROR:",
    r"failed",
    r"Failed",
    r"FAILED",
    r"exception",
    r"Exception",
    r"EXCEPTION",
    r"traceback",
    r"Traceback",
]


def is_tool_failure(tool_result: dict) -> bool:
    """
    Determine if a tool result represents a failure.

    Args:
        tool_result: Tool result dictionary

    Returns:
        True if failure detected, False otherwise
    """
    # Check exit code
    exit_code = tool_result.get("exit_code")
    if exit_code is not None and exit_code != 0:
        return True

    # Check stderr for error patterns
    stderr = tool_result.get("stderr", "")
    if stderr:
        import re
        for pattern in ERROR_PATTERNS:
            if re.search(pattern, stderr, re.IGNORECASE):
                return True

    # Check for error field in result
    if tool_result.get("error"):
        return True

    return False


def extract_error_message(tool_result: dict) -> str:
    """
    Extract error message from tool result.

    Args:
        tool_result: Tool result dictionary

    Returns:
        Error message string
    """
    # Priority: error field > stderr > stdout truncated
    if tool_result.get("error"):
        return str(tool_result["error"])

    stderr = tool_result.get("stderr", "")
    if stderr:
        return stderr[:1000]  # Cap at 1000 chars

    stdout = tool_result.get("stdout", "")
    if stdout:
        return stdout[:500]  # Less for stdout

    return "Unknown error (no details in tool result)"


def capture_error(tool_name: str, tool_input: dict, tool_result: dict) -> bool:
    """
    Capture error to registry.

    Args:
        tool_name: Name of the tool that failed
        tool_input: Tool input parameters
        tool_result: Tool result with error

    Returns:
        True if captured successfully, False otherwise
    """
    try:
        from error_analyzer import write_error_to_registry
    except ImportError:
        # Library not available - graceful degradation
        return False

    error_message = extract_error_message(tool_result)
    exit_code = tool_result.get("exit_code")

    # Build context (sanitized)
    context = {
        "tool_input_keys": list(tool_input.keys()) if tool_input else [],
    }

    # Add command for Bash (sanitized - no secrets)
    if tool_name == "Bash" and "command" in tool_input:
        cmd = str(tool_input["command"])
        # Only capture first 100 chars of command
        context["command_preview"] = cmd[:100] + "..." if len(cmd) > 100 else cmd

    return write_error_to_registry(
        tool_name=tool_name,
        exit_code=exit_code,
        error_message=error_message,
        context=context,
    )


def main():
    """Main hook function."""
    # Read input from stdin
    try:
        input_data = json.loads(sys.stdin.read())
    except json.JSONDecodeError:
        # Invalid input - allow tool to proceed
        output = {
            "hookSpecificOutput": {
                "hookEventName": "PostToolUse"
            }
        }
        print(json.dumps(output))
        sys.exit(0)

    # Extract tool info
    tool_name = input_data.get("tool_name", "unknown")
    tool_input = input_data.get("tool_input", {})
    tool_result = input_data.get("tool_result", {})

    # Check if this is a failure
    if is_tool_failure(tool_result):
        # Non-blocking capture - failures here don't interrupt workflow
        try:
            capture_error(tool_name, tool_input, tool_result)
        except Exception:
            pass  # Graceful degradation

    # Always allow tool to proceed (PostToolUse is informational)
    output = {
        "hookSpecificOutput": {
            "hookEventName": "PostToolUse"
        }
    }
    print(json.dumps(output))
    sys.exit(0)


if __name__ == "__main__":
    main()
