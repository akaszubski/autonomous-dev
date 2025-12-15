#!/usr/bin/env python3
"""
Agent Authorization Hook - Authorizes Pipeline Agents for Code Changes

This PreToolUse hook authorizes agents that are part of the /auto-implement
pipeline to make code changes. It's primarily used for agent context
detection, not enforcement.

Issue #141: Removed "significant change" detection (doesn't work - Claude
makes multiple small edits to bypass line count thresholds).

What this hook does:
- ALLOWS: implementer, test-master, and other pipeline agents
- ALLOWS: All non-code files (configs, docs, etc.)
- ALLOWS: All changes (intent detection removed)

What was removed (Issue #141):
- Line count threshold (>10 lines) - easily bypassed with small edits
- "Significant additions" detection - Claude breaks changes into chunks
- Blocking messages for autonomous implementation

Philosophy: Hooks cannot detect intent (Claude rephrases, uses alternative
tools, or makes many small edits). Instead of blocking, we:
1. Keep deterministic blocks (dangerous ops in other hooks)
2. Add persuasion to CLAUDE.md (data-driven)
3. Make /auto-implement faster (convenience)
4. Let skills guide agents (knowledge)

This hook remains for:
1. Agent context detection (CLAUDE_AGENT_NAME environment variable)
2. Future use in audit logging
3. Graceful integration with the PreToolUse hook chain

Input (stdin):
{
  "tool_name": "Edit",
  "tool_input": {
    "file_path": "/path/to/file.py",
    "old_string": "...",
    "new_string": "..."
  }
}

Output (stdout):
{
  "hookSpecificOutput": {
    "hookEventName": "PreToolUse",
    "permissionDecision": "allow",
    "permissionDecisionReason": "reason"
  }
}

Exit code: 0 (always - let Claude Code process the decision)

Environment Variables:
- ENFORCE_IMPLEMENTATION_WORKFLOW: Enable/disable hook (default: true)
- CLAUDE_AGENT_NAME: Identifies current agent context
"""

import json
import sys
import os
from pathlib import Path


# Agents that are part of the /auto-implement pipeline
# These agents are explicitly authorized for code changes
PIPELINE_AGENTS = [
    'implementer',
    'test-master',
    'brownfield-analyzer',
    'setup-wizard',
    'project-bootstrapper',
]


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
            pass


def output_decision(decision: str, reason: str):
    """Output the hook decision in required format."""
    print(json.dumps({
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": decision,
            "permissionDecisionReason": reason
        }
    }))


def main():
    """Main entry point."""
    try:
        # Load environment
        load_env()

        # Check if hook is enabled (default: true)
        enabled = os.getenv("ENFORCE_IMPLEMENTATION_WORKFLOW", "true").lower() == "true"
        if not enabled:
            output_decision("allow", "Implementation workflow hook disabled")
            sys.exit(0)

        # Check if running inside a pipeline agent
        agent_name = os.getenv("CLAUDE_AGENT_NAME", "").strip().lower()
        if agent_name in PIPELINE_AGENTS:
            output_decision("allow", f"Pipeline agent '{agent_name}' authorized for code changes")
            sys.exit(0)

        # Read input from stdin (for compatibility with hook chain)
        try:
            input_data = json.load(sys.stdin)
            tool_name = input_data.get("tool_name", "unknown")
        except json.JSONDecodeError:
            tool_name = "unknown"

        # Issue #141: Intent detection removed
        # Previously this hook would analyze changes and block "significant" additions.
        # This doesn't work because:
        # - Claude makes multiple small edits (each under threshold)
        # - Claude uses Bash heredoc instead of Edit tool
        # - Claude rephrases requests to avoid detection
        #
        # Now we allow all changes and rely on:
        # - CLAUDE.md persuasion (data-driven)
        # - /auto-implement convenience (faster than manual)
        # - Skills for agent guidance (knowledge)
        # - Deterministic hooks (dangerous ops) in other hooks

        output_decision("allow", f"Tool '{tool_name}' allowed (intent detection removed per Issue #141)")

    except Exception as e:
        # Error - allow (don't block on hook errors)
        output_decision("allow", f"Hook error: {e}")

    sys.exit(0)


if __name__ == "__main__":
    main()
