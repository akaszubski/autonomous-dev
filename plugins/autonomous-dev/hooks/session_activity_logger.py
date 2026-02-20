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
    ACTIVITY_LOGGING=true/false/debug (default: true)
        true  = compact summaries (file paths, content_length, truncated commands)
        debug = full raw stdin (complete tool_input + tool_output from Claude Code)
        false = disabled
    CLAUDE_SESSION_ID - Session identifier (provided by Claude Code)

Exit codes:
    0: Always (non-blocking hook)
"""

import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

import time


def main():
    """Log tool call activity to structured JSONL."""
    # Opt-out check: false=off, true=summary, debug=full raw stdin
    log_level = os.environ.get("ACTIVITY_LOGGING", "true").lower()
    if log_level == "false":
        sys.exit(0)

    try:
        _start = time.monotonic()
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

        if log_level == "debug":
            # Debug mode: log full raw stdin (tool_input + tool_output)
            entry = {
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "tool": tool_name,
                "tool_input": tool_input,
                "tool_output": tool_output if isinstance(tool_output, dict) else {"raw": str(tool_output)[:5000]},
                "session_id": os.environ.get("CLAUDE_SESSION_ID", "unknown"),
                "agent": os.environ.get("CLAUDE_AGENT_NAME", "main"),
                "duration_ms": round((time.monotonic() - _start) * 1000),
                "debug": True,
            }
        else:
            # Normal mode: compact summaries only
            input_summary = _summarize_input(tool_name, tool_input)
            output_summary = _summarize_output(tool_output)
            entry = {
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "tool": tool_name,
                "input_summary": input_summary,
                "output_summary": output_summary,
                "session_id": os.environ.get("CLAUDE_SESSION_ID", "unknown"),
                "agent": os.environ.get("CLAUDE_AGENT_NAME", "main"),
                "duration_ms": round((time.monotonic() - _start) * 1000),
                "success": output_summary.get("success", True),
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
        # Detect pipeline terminal actions
        if "git push" in cmd:
            summary["pipeline_action"] = "git_push"
        elif "gh issue close" in cmd:
            summary["pipeline_action"] = "issue_close"
        elif "git commit" in cmd:
            summary["pipeline_action"] = "git_commit"
        elif "pytest" in cmd:
            summary["pipeline_action"] = "test_run"
        elif "implement_pipeline_state" in cmd:
            summary["pipeline_action"] = "pipeline_state"
    elif tool_name in ("Glob", "Grep"):
        summary["pattern"] = tool_input.get("pattern", "")
        summary["path"] = tool_input.get("path", "")
    elif tool_name == "Task":
        summary["description"] = tool_input.get("description", "")
        summary["subagent_type"] = tool_input.get("subagent_type", "")
        # Track agent invocations for pipeline completeness
        summary["pipeline_action"] = "agent_invocation"
    else:
        # Generic: include keys but not values
        summary["keys"] = list(tool_input.keys())[:5]

    return summary


def _summarize_output(tool_output: dict) -> dict:
    """Create a compact summary of tool output including errors."""
    if isinstance(tool_output, str):
        # Check if it looks like an error
        is_error = any(w in tool_output.lower() for w in ["error", "traceback", "failed", "exception"])
        summary = {"length": len(tool_output), "success": not is_error}
        if is_error:
            summary["error_preview"] = tool_output[:500]
        return summary

    if isinstance(tool_output, dict):
        has_error = tool_output.get("error", False)
        summary = {
            "success": not has_error,
            "has_output": bool(tool_output.get("output", "")),
        }
        if has_error:
            # Capture error details
            err = tool_output.get("error", "")
            if isinstance(err, str):
                summary["error_preview"] = err[:500]
            output_text = tool_output.get("output", "")
            if isinstance(output_text, str) and output_text:
                summary["output_preview"] = output_text[:500]
        return summary

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
