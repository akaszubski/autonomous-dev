#!/usr/bin/env python3
"""
PreToolUse Hook - Simple Standalone Script for Claude Code

Reads tool call from stdin, validates it, outputs decision to stdout.

Input (stdin):
{
  "tool_name": "Bash",
  "tool_input": {"command": "pytest tests/"}
}

Output (stdout):
{
  "hookSpecificOutput": {
    "hookEventName": "PreToolUse",
    "permissionDecision": "allow",  # or "deny"
    "permissionDecisionReason": "reason"
  }
}

Exit code: 0 (always - let Claude Code process the decision)
"""

import json
import sys
import os
from pathlib import Path


def find_lib_directory(hook_path: Path) -> Path | None:
    """
    Find lib directory dynamically (Issue #113).

    Checks multiple locations in order:
    1. Development: plugins/autonomous-dev/lib (relative to hook)
    2. Local install: ~/.claude/lib
    3. Marketplace: ~/.claude/plugins/autonomous-dev/lib

    Args:
        hook_path: Path to this hook script

    Returns:
        Path to lib directory if found, None otherwise (graceful failure)
    """
    # Try development location first (plugins/autonomous-dev/hooks/pre_tool_use.py)
    dev_lib = hook_path.parent.parent / "lib"
    if dev_lib.exists() and dev_lib.is_dir():
        return dev_lib

    # Try local install (~/.claude/lib)
    home = Path.home()
    local_lib = home / ".claude" / "lib"
    if local_lib.exists() and local_lib.is_dir():
        return local_lib

    # Try marketplace location (~/.claude/plugins/autonomous-dev/lib)
    marketplace_lib = home / ".claude" / "plugins" / "autonomous-dev" / "lib"
    if marketplace_lib.exists() and marketplace_lib.is_dir():
        return marketplace_lib

    # Not found - graceful failure
    return None


# Add lib directory to path dynamically
LIB_DIR = find_lib_directory(Path(__file__))
if LIB_DIR:
    sys.path.insert(0, str(LIB_DIR))

# Load .env file if available
def load_env():
    """Load .env file from project root if it exists."""
    env_file = Path(os.getcwd()) / ".env"
    if env_file.exists():
        try:
            with open(env_file, 'r') as f:
                for line in f:
                    line = line.strip()
                    if not line or line.startswith('#'):
                        continue
                    if '=' in line:
                        key, value = line.split('=', 1)
                        key = key.strip()
                        value = value.strip().strip('"').strip("'")
                        if key not in os.environ:
                            os.environ[key] = value
        except Exception:
            pass  # Silently skip

load_env()

def main():
    """Main entry point."""
    try:
        # Read input from stdin
        input_data = json.load(sys.stdin)

        # Extract tool info
        tool_name = input_data.get("tool_name", "")
        tool_input = input_data.get("tool_input", {})

        # Get agent name from environment
        agent_name = os.getenv("CLAUDE_AGENT_NAME", "").strip() or None

        # Import and run validation (graceful failure if lib not found)
        try:
            if LIB_DIR is None:
                # Lib directory not found - graceful degradation
                permission_decision = "ask"
                reason = "Lib directory not found, MCP security disabled (ask user)"
            else:
                from auto_approval_engine import should_auto_approve
                from tool_validator import ToolValidator

                approved, reason = should_auto_approve(tool_name, tool_input, agent_name)

                # Determine three-state decision:
                # 1. approved=True → "allow" (auto-approve)
                # 2. blacklisted/security_risk → "deny" (block entirely)
                # 3. not whitelisted → "ask" (fall back to user)
                if approved:
                    permission_decision = "allow"
                elif "blacklist" in reason.lower() or "injection" in reason.lower() or "security" in reason.lower() or "circuit breaker" in reason.lower():
                    permission_decision = "deny"
                else:
                    # Not whitelisted but not dangerous - ask user
                    permission_decision = "ask"

        except Exception as e:
            # Graceful degradation - ask user on error (don't block)
            permission_decision = "ask"
            reason = f"Auto-approval error: {e}"

        # Output decision
        decision = {
            "hookSpecificOutput": {
                "hookEventName": "PreToolUse",
                "permissionDecision": permission_decision,
                "permissionDecisionReason": reason
            }
        }

        print(json.dumps(decision))

    except Exception as e:
        # Error - ask user (don't block on hook errors)
        decision = {
            "hookSpecificOutput": {
                "hookEventName": "PreToolUse",
                "permissionDecision": "ask",
                "permissionDecisionReason": f"Hook error: {e}"
            }
        }
        print(json.dumps(decision))

    # Always exit 0 - let Claude Code process the decision
    sys.exit(0)

if __name__ == "__main__":
    main()
