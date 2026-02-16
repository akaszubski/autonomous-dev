#!/usr/bin/env -S uv run --script --quiet --no-project
# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""
Session Activity Logger - Structured tool call logging for continuous improvement.

Logs every tool call as structured JSONL for post-session analysis by the
continuous-improvement-analyst agent.

Hook: PostToolUse (runs after every tool call)

Captures:
    - Tool name and input summary (NOT full content)
    - Output status (success/error)
    - Active agent context (pipeline step)
    - Timestamp and session ID

Log location: .claude/logs/activity/{date}.jsonl
Logs are gitignored (local-only).

Environment Variables:
    ACTIVITY_LOGGING=true/false (default: true)
    CLAUDE_SESSION_ID - Session identifier (provided by Claude Code)

Exit codes:
    0: Always (non-blocking hook)
"""

import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path


def main():
    """Log tool call activity to structured JSONL."""
    # Opt-out check
    if os.environ.get("ACTIVITY_LOGGING", "true").lower() == "false":
        sys.exit(0)

    try:
        # Read hook input from stdin
        raw = sys.stdin.read().strip()
        if not raw:
            sys.exit(0)

        try:
            hook_input = json.loads(raw)
        except json.JSONDecodeError:
            sys.exit(0)

        tool_name = hook_input.get("tool_name", "unknown")
        tool_input = hook_input.get("tool_input", {})
        tool_output = hook_input.get("tool_output", {})

        # Build compact input summary (never log full file content)
        input_summary = _summarize_input(tool_name, tool_input)

        # Build output summary
        output_summary = _summarize_output(tool_output)

        # Build log entry
        entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "tool": tool_name,
            "input_summary": input_summary,
            "output_summary": output_summary,
            "session_id": os.environ.get("CLAUDE_SESSION_ID", "unknown"),
            "agent": os.environ.get("CLAUDE_AGENT_NAME", "main"),
        }

        # Write to log file
        log_dir = _find_log_dir()
        log_dir.mkdir(parents=True, exist_ok=True)

        date_str = datetime.now().strftime("%Y-%m-%d")
        log_file = log_dir / f"{date_str}.jsonl"

        with open(log_file, "a") as f:
            f.write(json.dumps(entry, separators=(",", ":")) + "\n")

    except Exception:
        # Non-blocking: never crash Claude Code
        pass

    sys.exit(0)


def _summarize_input(tool_name: str, tool_input: dict) -> dict:
    """Create a compact summary of tool input (no full content)."""
    summary = {}

    if tool_name in ("Write", "Edit"):
        summary["file_path"] = tool_input.get("file_path", "")
        content = tool_input.get("content", tool_input.get("new_string", ""))
        summary["content_length"] = len(content) if isinstance(content, str) else 0
    elif tool_name == "Read":
        summary["file_path"] = tool_input.get("file_path", "")
    elif tool_name == "Bash":
        cmd = tool_input.get("command", "")
        # Truncate long commands
        summary["command"] = cmd[:200] if len(cmd) > 200 else cmd
    elif tool_name in ("Glob", "Grep"):
        summary["pattern"] = tool_input.get("pattern", "")
        summary["path"] = tool_input.get("path", "")
    elif tool_name == "Task":
        summary["description"] = tool_input.get("description", "")
        summary["subagent_type"] = tool_input.get("subagent_type", "")
    else:
        # Generic: include keys but not values
        summary["keys"] = list(tool_input.keys())[:5]

    return summary


def _summarize_output(tool_output: dict) -> dict:
    """Create a compact summary of tool output."""
    if isinstance(tool_output, str):
        return {"length": len(tool_output), "success": True}

    if isinstance(tool_output, dict):
        return {
            "success": not tool_output.get("error", False),
            "has_output": bool(tool_output.get("output", "")),
        }

    return {"success": True}


def _find_log_dir() -> Path:
    """Find the .claude/logs/activity directory."""
    # Walk up to find .claude directory
    cwd = Path.cwd()
    for parent in [cwd] + list(cwd.parents):
        claude_dir = parent / ".claude"
        if claude_dir.exists():
            return claude_dir / "logs" / "activity"

    # Fallback to cwd
    return cwd / ".claude" / "logs" / "activity"


if __name__ == "__main__":
    main()
