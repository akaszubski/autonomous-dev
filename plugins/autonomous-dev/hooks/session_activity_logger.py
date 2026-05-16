#!/usr/bin/env python3
"""
Session Activity Logger - Structured tool call logging for continuous improvement.

Logs every tool call as structured JSONL for post-session analysis by the
continuous-improvement-analyst agent.

Hooks: PostToolUse (after every tool call), Stop (after assistant response)

Captures:
    - Tool name and input summary (NOT full content)
    - Output status (success/error)
    - Active agent context (pipeline step)
    - Assistant text output (truncated summary)
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
import re
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

# In-process cache for session date (avoids repeated file reads within same invocation)
_SESSION_DATE_CACHE: dict = {}

# ============================================================================
# Subagent Invocation Cache helpers (Issue #1087)
# ============================================================================
#
# Claude Code's SubagentStop hook payload sometimes omits the agent_type
# and always reports duration_ms=0. We work around this by caching
# subagent invocations at PreToolUse time and popping them at
# SubagentStop. The cache lives in plugins/autonomous-dev/lib/
# subagent_invocation_cache.py so both this hook (PreToolUse writer) and
# unified_session_tracker.py (SubagentStop reader) can share it.

try:
    from subagent_invocation_cache import cache_invocation as _sic_cache_invocation
except ImportError:
    # Fallback: silently disable the cache so this hook still loads if
    # the lib is missing. SubagentStop instrumentation degrades to the
    # pre-#1087 behavior (empty subagent_type, duration_ms=0) — no crash.
    def _sic_cache_invocation(*_args, **_kwargs):
        return False


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

        # Detect hook type from input fields
        hook_event = hook_input.get("hook_event_name", "")

        if hook_event == "Stop":
            # Stop hook: capture assistant text output
            message = hook_input.get("last_assistant_message", "")
            if not message:
                sys.exit(0)
            if log_level == "debug":
                entry = {
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "hook": "Stop",
                    "message": message[:10000],
                    "message_length": len(message),
                    "session_id": os.environ.get("CLAUDE_SESSION_ID", hook_input.get("session_id", "unknown")),
                    "agent": os.environ.get("CLAUDE_AGENT_NAME", "main"),
                    "stop_hook_active": hook_input.get("stop_hook_active", False),
                    "debug": True,
                }
            else:
                entry = {
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "hook": "Stop",
                    "message_preview": message[:1000],
                    "message_length": len(message),
                    "session_id": os.environ.get("CLAUDE_SESSION_ID", hook_input.get("session_id", "unknown")),
                    "agent": os.environ.get("CLAUDE_AGENT_NAME", "main"),
                    "stop_hook_active": hook_input.get("stop_hook_active", False),
                }

            log_dir = _find_log_dir()
            log_dir.mkdir(parents=True, exist_ok=True)
            session_id = os.environ.get("CLAUDE_SESSION_ID", hook_input.get("session_id", "unknown"))
            date_str = _get_session_date(session_id)
            log_file = log_dir / f"{date_str}.jsonl"
            with open(log_file, "a") as f:
                f.write(json.dumps(entry, separators=(",", ":")) + "\n")
            sys.exit(0)

        # UserPromptSubmit: capture user prompt activity
        if hook_event == "UserPromptSubmit":
            user_prompt = hook_input.get("user_prompt", "")
            if not user_prompt:
                sys.exit(0)

            session_id = os.environ.get("CLAUDE_SESSION_ID", hook_input.get("session_id", "unknown"))
            entry = {
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "hook": "UserPromptSubmit",
                "prompt_preview": user_prompt[:500],
                "prompt_length": len(user_prompt),
                "session_id": session_id,
                "agent": os.environ.get("CLAUDE_AGENT_NAME", "main"),
            }

            log_dir = _find_log_dir()
            log_dir.mkdir(parents=True, exist_ok=True)
            date_str = _get_session_date(session_id)
            log_file = log_dir / f"{date_str}.jsonl"
            with open(log_file, "a") as f:
                f.write(json.dumps(entry, separators=(",", ":")) + "\n")
            sys.exit(0)

        # PreToolUse: cache subagent invocation data for SubagentStop correlation (Issue #1087).
        # Only Task/Agent invocations get cached — every other tool call is ignored at this branch
        # so we don't double-log PostToolUse later in main().
        if hook_event == "PreToolUse":
            pre_tool_name = hook_input.get("tool_name", "")
            if pre_tool_name in ("Task", "Agent"):
                pre_tool_input = hook_input.get("tool_input", {}) or {}
                pre_session_id = (
                    os.environ.get("CLAUDE_SESSION_ID")
                    or hook_input.get("session_id", "unknown")
                )
                pre_subagent_type = (pre_tool_input.get("subagent_type", "") or "").strip()
                if pre_subagent_type:
                    _sic_cache_invocation(
                        pre_session_id,
                        pre_subagent_type,
                        start_time=time.time(),
                        description=pre_tool_input.get("description", ""),
                    )
            # Always exit on PreToolUse — we don't write a log entry from this hook
            # (unified_pre_tool.py owns PreToolUse activity logging).
            sys.exit(0)

        # PostToolUse: capture tool call activity
        tool_name = hook_input.get("tool_name", "unknown")
        tool_input = hook_input.get("tool_input", {})
        tool_output = hook_input.get("tool_output", {})

        # Session ID: prefer env var, fall back to hook stdin JSON
        session_id = os.environ.get("CLAUDE_SESSION_ID") or hook_input.get("session_id", "unknown")

        if log_level == "debug":
            # Debug mode: log full raw stdin (tool_input + tool_output)
            entry = {
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "hook": "PostToolUse",
                "tool": tool_name,
                "tool_input": tool_input,
                "tool_output": tool_output if isinstance(tool_output, dict) else {"raw": str(tool_output)[:5000]},
                "session_id": session_id,
                "agent": os.environ.get("CLAUDE_AGENT_NAME", "main"),
                "duration_ms": round((time.monotonic() - _start) * 1000),
                "debug": True,
            }
        else:
            # Normal mode: compact summaries only
            input_summary = _summarize_input(tool_name, tool_input)
            output_summary = _summarize_output(tool_output)
            output_summary = _add_result_word_count(tool_name, tool_output, output_summary)
            entry = {
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "hook": "PostToolUse",
                "tool": tool_name,
                "input_summary": input_summary,
                "output_summary": output_summary,
                "session_id": session_id,
                "agent": os.environ.get("CLAUDE_AGENT_NAME", "main"),
                "duration_ms": round((time.monotonic() - _start) * 1000),
                "success": output_summary.get("success", True),
            }
            # Enhanced Agent event tracking (Issue #526)
            # Agent events are critical for pipeline completeness validation
            # Log them with elevated priority to ensure they're captured
            if tool_name in ("Task", "Agent"):
                entry["priority"] = "high"
                entry["agent_event"] = True

        # Write to log file
        log_dir = _find_log_dir()
        log_dir.mkdir(parents=True, exist_ok=True)

        date_str = _get_session_date(session_id)
        log_file = log_dir / f"{date_str}.jsonl"

        with open(log_file, "a") as f:
            f.write(json.dumps(entry, separators=(",", ":")) + "\n")

        # Heartbeat check for batch session monitoring (Issue #526)
        _check_and_log_heartbeat(session_id, log_dir, date_str)

        # Budget check for Agent/Task completions (Issue #705 — non-blocking soft gate)
        if tool_name in ("Task", "Agent") and log_level != "debug":
            try:
                agent_duration_ms = output_summary.get("agent_duration_ms")
                agent_type = input_summary.get("subagent_type")
                if agent_type and agent_duration_ms and agent_duration_ms > 0:
                    _check_and_log_budget(
                        agent_type=agent_type,
                        duration_ms=agent_duration_ms,
                        session_id=session_id,
                        log_file=log_file,
                    )
            except Exception:
                # Non-blocking: budget check errors must never crash the hook
                pass

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
    elif tool_name in ("Task", "Agent"):
        summary["description"] = tool_input.get("description", "")
        summary["subagent_type"] = tool_input.get("subagent_type", "")
        # Track agent invocations for pipeline completeness
        summary["pipeline_action"] = "agent_invocation"
        # Issue #906 / #882: detect background agent launch so the validator can
        # skip step_ordering checks for asynchronous agents (e.g., doc-master).
        # Only add the field when true; omitting it keeps legacy log format clean
        # and the parser defaults to False for backward compatibility.
        if tool_input.get("run_in_background"):
            summary["is_background"] = True
        # Word count for intent validation (Issue #367)
        prompt_text = tool_input.get("prompt", "")
        summary["prompt_word_count"] = len(prompt_text.split()) if isinstance(prompt_text, str) else 0
        # Batch context detection (Issue #526)
        if isinstance(prompt_text, str) and "BATCH CONTEXT" in prompt_text:
            summary["batch_mode"] = True
            # Prefer structured field from BATCH CONTEXT block (Issue #808),
            # fall back to inline Issue #N for backward compatibility
            issue_match = re.search(r'Issue Number:\s*(\d+)', prompt_text)
            if not issue_match:
                issue_match = re.search(r'Issue #(\d+)', prompt_text)
            if issue_match:
                summary["batch_issue_number"] = int(issue_match.group(1))
    elif tool_name == "Skill":
        summary["skill"] = tool_input.get("skill", "")
        args = tool_input.get("args", "")
        summary["args"] = str(args)[:200] if args else ""
        summary["pipeline_action"] = "skill_load"
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


def _extract_usage_from_result(tool_output: str) -> dict:
    """Extract token usage data from Agent tool result text.

    Parses the ``<usage>`` block returned by the Agent tool, e.g.::

        <usage>total_tokens: 27169
        tool_uses: 2
        duration_ms: 18677</usage>

    Args:
        tool_output: Raw output text from the Agent/Task tool.

    Returns:
        Dict with ``total_tokens``, ``tool_uses``, and ``duration_ms`` keys
        (int values) for any fields found, or empty dict if no usage block.
    """
    if not tool_output or not isinstance(tool_output, str):
        return {}

    match = re.search(r"<usage>(.*?)</usage>", tool_output, re.DOTALL)
    if not match:
        return {}

    usage_text = match.group(1)
    result: dict = {}

    for key in ("total_tokens", "tool_uses", "duration_ms"):
        field_match = re.search(rf"{key}:\s*(\d+)", usage_text)
        if field_match:
            result[key] = int(field_match.group(1))

    return result


def _add_result_word_count(tool_name: str, tool_output: dict, summary: dict) -> dict:
    """Add result_word_count and token usage for Task/Agent tool outputs (Issue #367, #704, #925)."""
    if tool_name in ("Task", "Agent"):
        # Lazy import shared helper (Issue #925)
        import sys as _sys_wch
        _lib_dir_wch = str(Path(__file__).parent.parent / "lib")
        if _lib_dir_wch not in _sys_wch.path:
            _sys_wch.path.insert(0, _lib_dir_wch)
        from word_count_helpers import count_words_in_content

        # Modern Anthropic schema: toolUseResult uses "content" as list-of-text-blocks (Issue #925)
        content = tool_output.get("content") if isinstance(tool_output, dict) else None
        word_count = count_words_in_content(content)

        # Fall back to legacy flat "output" string if content is absent or yields 0 words
        output_text = ""
        if content is None or word_count == 0:
            if isinstance(tool_output, dict):
                output_text = str(tool_output.get("output", ""))
            elif isinstance(tool_output, str):
                output_text = tool_output
            word_count = len(output_text.split()) if output_text else 0

        summary["result_word_count"] = word_count

        # Build output_text for usage extraction (Issue #704)
        # Prefer the flat-string path; if content is a list-of-blocks, concatenate text blocks.
        if not output_text and isinstance(content, list):
            output_text = "\n".join(
                b["text"] for b in content if isinstance(b, dict) and b.get("type") == "text"
            )

        # Extract token usage from <usage> block (Issue #704)
        usage = _extract_usage_from_result(output_text)
        summary["total_tokens"] = usage.get("total_tokens", 0)
        summary["tool_uses"] = usage.get("tool_uses", 0)
        summary["agent_duration_ms"] = usage.get("duration_ms", 0)
    return summary


def _get_session_date(session_id: str) -> str:
    """Get the pinned date for a session, preventing cross-midnight mislabeling.

    Each session gets a date pinned on first activity. If the session spans
    midnight, all entries still use the original date so they land in the
    same log file.

    Uses a small file for persistence across subprocess invocations, with
    an in-process cache to avoid repeated file reads.

    Args:
        session_id: The Claude session identifier.

    Returns:
        Date string in YYYY-MM-DD format.
    """
    # Check in-process cache first
    if session_id in _SESSION_DATE_CACHE:
        return _SESSION_DATE_CACHE[session_id]

    # Check for session date file
    log_dir = _find_log_dir()
    log_dir.mkdir(parents=True, exist_ok=True)
    date_file = log_dir / f".session_date_{session_id}"

    try:
        if date_file.exists():
            stored_date = date_file.read_text().strip()
            # Validate freshness: if file is older than 24 hours, start fresh
            file_age_seconds = time.time() - date_file.stat().st_mtime
            if file_age_seconds < 86400 and stored_date:
                _SESSION_DATE_CACHE[session_id] = stored_date
                return stored_date
    except Exception:
        pass

    # Fall back to current date and persist it
    date_str = datetime.now().strftime("%Y-%m-%d")
    try:
        date_file.write_text(date_str)
    except Exception:
        pass
    _SESSION_DATE_CACHE[session_id] = date_str
    return date_str


def _find_log_dir() -> Path:
    """Find the .claude/logs/activity directory.

    When running in a git worktree, resolves to the PARENT repo's .claude
    directory so all events (worktree and main) end up in the same log file.
    This prevents the split-log problem where downstream agents' events
    are written to the worktree's log and missed by post-session analysis.
    Issue #755.
    """
    cwd = Path.cwd()

    # Worktree detection: if CWD is inside a .worktrees/ directory,
    # resolve to the parent repo's .claude directory via git.
    cwd_str = str(cwd)
    if "/.worktrees/" in cwd_str or "\\.worktrees\\" in cwd_str:
        try:
            import subprocess
            result = subprocess.run(
                ["git", "rev-parse", "--path-format=absolute", "--git-common-dir"],
                capture_output=True, text=True, timeout=5, cwd=str(cwd)
            )
            if result.returncode == 0:
                common_dir = Path(result.stdout.strip())
                # common_dir is the .git directory of the parent repo
                parent_repo = common_dir.parent if common_dir.name == ".git" else common_dir
                claude_dir = parent_repo / ".claude"
                if claude_dir.exists():
                    return claude_dir / "logs" / "activity"
        except Exception:
            pass  # Fall through to normal resolution

    # Normal resolution: walk up to find .claude directory
    for parent in [cwd] + list(cwd.parents):
        claude_dir = parent / ".claude"
        if claude_dir.exists():
            return claude_dir / "logs" / "activity"

    # Fallback to cwd
    return cwd / ".claude" / "logs" / "activity"


def _check_and_log_budget(
    agent_type: str,
    duration_ms: int | float,
    session_id: str,
    log_file: Path,
) -> None:
    """Check agent duration against time budget and log a BudgetWarning entry if needed.

    This is a soft gate — never blocks. Writes an additional JSONL entry tagged
    "BudgetWarning" when an agent uses >= warning_pct of its budget or exceeds it.

    Args:
        agent_type: The pipeline agent type (e.g. "implementer").
        duration_ms: Agent wall-clock duration in milliseconds.
        session_id: Current Claude session identifier.
        log_file: Path to the active JSONL log file for writing.
    """
    try:
        # Lazy import so that the hook still works even if the library is unavailable
        import sys as _sys
        _lib_dir = str(Path(__file__).parent.parent / "lib")
        if _lib_dir not in _sys.path:
            _sys.path.insert(0, _lib_dir)
        from pipeline_timing_analyzer import check_budget_violation, format_budget_warning

        duration_seconds = duration_ms / 1000.0
        violation = check_budget_violation(agent_type, duration_seconds)
        if violation is None:
            return

        warning_text = format_budget_warning(violation)
        entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "hook": "BudgetWarning",
            "agent_type": agent_type,
            "level": violation["level"],
            "duration_seconds": violation["duration"],
            "budget_seconds": violation["budget"],
            "pct_used": round(violation["pct_used"], 3),
            "session_id": session_id,
            "message": warning_text,
        }
        with open(log_file, "a") as _f:
            _f.write(json.dumps(entry, separators=(",", ":")) + "\n")
    except Exception:
        pass  # Non-blocking: never crash the hook


def _check_and_log_heartbeat(session_id: str, log_dir: Path, date_str: str):
    """Write a heartbeat entry if >5 minutes since last log for this session.

    Helps detect when the logger stops receiving events in batch mode (Issue #526).

    Args:
        session_id: The Claude session identifier.
        log_dir: Directory where log files are written.
        date_str: Date string for the log file name (YYYY-MM-DD).
    """
    try:
        heartbeat_file = log_dir / f".heartbeat_{session_id}"
        now = time.time()

        if heartbeat_file.exists():
            last_beat = float(heartbeat_file.read_text().strip())
            if now - last_beat < 300:  # 5 minutes
                return

        # Write heartbeat
        heartbeat_file.write_text(str(now))

        entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "hook": "Heartbeat",
            "session_id": session_id,
            "agent": os.environ.get("CLAUDE_AGENT_NAME", "main"),
            "message": "Logger heartbeat - still receiving events",
        }
        log_file = log_dir / f"{date_str}.jsonl"
        with open(log_file, "a") as f:
            f.write(json.dumps(entry, separators=(",", ":")) + "\n")
    except Exception:
        pass  # Non-blocking



# Issue #1012 (W0): Per-hook timing telemetry. Best-effort, never raises.
# Records duration + decision_shape to ~/.claude/logs/hook_timings_YYYY-MM-DD.jsonl.
try:
    from hook_timing import HookTimer  # type: ignore[import-not-found]
except ImportError:
    # Fallback: no-op stub so hooks keep working if hook_timing is missing.
    class HookTimer:  # type: ignore[no-redef]
        def __init__(self, *_, **__): pass
        def __enter__(self): return self
        def __exit__(self, *_): pass
        def set_decision_shape(self, _): pass

_HOOK_TIMER_NAME = _Path_953(__file__).name


def _timed_main():  # type: ignore[no-redef]
    with HookTimer(_HOOK_TIMER_NAME):
        return main()

if __name__ == "__main__":
    _safe_main_953(_timed_main)
