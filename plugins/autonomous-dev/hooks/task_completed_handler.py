#!/usr/bin/env python3
"""
TaskCompleted Handler - Logs task completion events for pipeline observability.

Hook: TaskCompleted (runs when a task completes)

This is a PREPARATION handler. TaskCompleted does not currently fire in the
autonomous-dev pipeline (which uses the Agent tool, not TaskUpdate). This hook
registers the event and provides minimal logging so that when TaskCompleted
events become available, the infrastructure is ready.

Input: JSON via stdin (provided by Claude Code TaskCompleted hook).
Expected fields: task_id, task_subject, task_description, teammate_name, team_name

Log location: .claude/logs/activity/{date}.jsonl

Exit codes:
    0: Always (non-blocking hook)
"""

# Issue #953: Hook safety — wrap main() with safe_main so hook crashes never
# block Claude Code. The wrap is purely an outer safety net; success-path
# return codes are preserved (int return → exit code, sys.exit → propagated).
import sys as _sys_953  # alias to avoid colliding with hook-local sys imports
from pathlib import Path as _Path_953

_hook_dir_953 = _Path_953(__file__).resolve().parent
for _candidate_lib_953 in (
    _hook_dir_953.parent / "lib",                    # plugins/autonomous-dev/lib (dev)
    _hook_dir_953.parent.parent / "lib",             # ~/.claude/lib (installed)
    _Path_953.home() / ".claude" / "plugins" / "autonomous-dev" / "lib",  # marketplace
):
    if _candidate_lib_953.exists() and str(_candidate_lib_953) not in _sys_953.path:
        _sys_953.path.insert(0, str(_candidate_lib_953))

try:
    from hook_safety import safe_main as _safe_main_953
except ImportError:
    # Fallback: no-op wrapper so hooks still load if hook_safety is missing.
    def _safe_main_953(_fn):
        _result = _fn()
        if isinstance(_result, int):
            _sys_953.exit(_result)
        _sys_953.exit(0)


import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path


def _find_project_root() -> Path:
    """Find project root by walking up from cwd looking for .git or .claude."""
    current = Path.cwd()
    while current != current.parent:
        if (current / ".git").exists() or (current / ".claude").exists():
            return current
        current = current.parent
    return Path.cwd()


def _get_log_dir() -> Path:
    """Get the activity log directory, creating it if needed."""
    root = _find_project_root()
    log_dir = root / ".claude" / "logs" / "activity"
    log_dir.mkdir(parents=True, exist_ok=True)
    return log_dir


def _build_log_entry(payload: dict) -> dict:
    """Build a structured log entry from the TaskCompleted payload.

    Args:
        payload: Parsed JSON from stdin containing task completion data.

    Returns:
        Structured dict ready for JSONL logging.
    """
    now = datetime.now(timezone.utc)
    return {
        "timestamp": now.isoformat(),
        "hook": "TaskCompleted",
        "task_id": payload.get("task_id", "unknown"),
        "task_subject": payload.get("task_subject", ""),
        "task_description": payload.get("task_description", ""),
        "teammate_name": payload.get("teammate_name", ""),
        "team_name": payload.get("team_name", ""),
        "session_id": os.environ.get(
            "CLAUDE_SESSION_ID", payload.get("session_id", "unknown")
        ),
    }


def _write_log_entry(entry: dict) -> None:
    """Append a log entry to the daily JSONL file.

    Args:
        entry: Structured dict to write as a single JSONL line.
    """
    log_dir = _get_log_dir()
    date_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    log_file = log_dir / f"{date_str}.jsonl"
    with open(log_file, "a") as f:
        f.write(json.dumps(entry) + "\n")


def main() -> None:
    """Process TaskCompleted hook event and log to activity JSONL."""
    try:
        raw = sys.stdin.read().strip()
        if not raw:
            sys.exit(0)

        try:
            payload = json.loads(raw)
        except json.JSONDecodeError:
            sys.exit(0)

        entry = _build_log_entry(payload)
        _write_log_entry(entry)

    except Exception:
        # Non-blocking hook: never fail
        pass

    sys.exit(0)


if __name__ == "__main__":
    _safe_main_953(main)
