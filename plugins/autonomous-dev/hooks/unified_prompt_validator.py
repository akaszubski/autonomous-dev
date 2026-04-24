#!/usr/bin/env -S uv run --script --quiet --no-project
# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""
Unified Prompt Validator Hook - Intent-to-Command Routing

Consolidates UserPromptSubmit hooks:
- Command routing: Detects intent and suggests the right command
- Bypass blocking: Blocks explicit workflow bypass attempts (gh issue create, skip /create-issue)

Hook: UserPromptSubmit (runs when user submits a prompt)

Environment Variables (opt-in/opt-out):
    ENFORCE_WORKFLOW=true/false (default: true) - Controls bypass blocking
    QUALITY_NUDGE_ENABLED=true/false (default: true) - Controls command routing nudges

Exit codes:
    0: Pass - No issues detected OR nudge shown (non-blocking)
    2: Block - Workflow bypass detected

Usage:
    # As UserPromptSubmit hook (automatic)
    echo '{"userPrompt": "gh issue create"}' | python unified_prompt_validator.py

    # Test command routing
    echo '{"userPrompt": "implement auth feature"}' | python unified_prompt_validator.py

    # Disable nudges
    echo '{"userPrompt": "implement auth"}' | QUALITY_NUDGE_ENABLED=false python unified_prompt_validator.py
"""

import json
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional


# ============================================================================
# Dynamic Library Discovery
# ============================================================================

def is_running_under_uv() -> bool:
    """Detect if script is running under UV."""
    return "UV_PROJECT_ENVIRONMENT" in os.environ

def find_lib_dir() -> Optional[Path]:
    """
    Find the lib directory dynamically.

    Searches:
    1. Relative to this file: ../lib
    2. In project root: plugins/autonomous-dev/lib
    3. In global install: ~/.autonomous-dev/lib

    Returns:
        Path to lib directory or None if not found
    """
    candidates = [
        Path(__file__).parent.parent / "lib",  # Relative to hooks/
        Path.cwd() / "plugins" / "autonomous-dev" / "lib",  # Project root
        Path.home() / ".autonomous-dev" / "lib",  # Global install
    ]

    for candidate in candidates:
        if candidate.exists():
            return candidate

    return None


# Add lib to path
LIB_DIR = find_lib_dir()
if LIB_DIR:
    if not is_running_under_uv():
        sys.path.insert(0, str(LIB_DIR))


# ============================================================================
# Configuration
# ============================================================================

# Check configuration from environment
ENFORCE_WORKFLOW = os.environ.get("ENFORCE_WORKFLOW", "true").lower() == "true"
QUALITY_NUDGE_ENABLED = os.environ.get("QUALITY_NUDGE_ENABLED", "true").lower() == "true"

# Plan mode enforcement (Issue #358)
PLAN_MODE_EXIT_MARKER = ".claude/plan_mode_exit.json"
PLAN_MODE_STALE_MINUTES = 30


# ============================================================================
# Intent-to-Command Routing Table
# ============================================================================

COMMAND_ROUTES: List[Dict] = [
    # NOTE: Order matters! More specific routes must come before general ones.
    # /create-issue before /implement (since "create issue" would match implement's "create" verb).
    {
        "intent": [
            r'\bgh\s+issue\s+create\b',
            r'\b(file|open|create|submit)\s+(?:a\s+)?(?:an\s+)?(?:new\s+)?(?:github\s+)?issue\b',
        ],
        "skip": [r'^/create-issue'],
        "command": "/create-issue",
        "reason": "includes duplicate detection, research, and PROJECT.md alignment",
        "block": True,  # gh issue create is blocked, not just suggested
    },
    {
        "intent": [
            r'\b(check|run|verify)\s+(?:the\s+)?(?:tests?|security|coverage|audit)\b',
            r'\bpytest\b',
        ],
        "skip": [r'^/audit', r'^/test'],
        "command": "/audit",
        "reason": "runs comprehensive quality checks (tests, security, coverage, docs)",
    },
    {
        "intent": [
            r'\b(check|verify|validate)\s+(?:project\s+)?alignment\b',
            r'PROJECT\.md.*\b(align|check|updat|sync)',
            r'\balign.*PROJECT\.md',
            r'\b(check|validate|verify).*PROJECT\.md',
        ],
        "skip": [r'^/align'],
        "command": "/align",
        "reason": "validates against PROJECT.md goals, scope, and constraints",
    },
    {
        "intent": [
            r'\b(update|sync|write|fix)\s+(?:the\s+)?(?:docs|documentation|README|CLAUDE)\b',
        ],
        "skip": [r'^/align', r'^/update-docs'],
        "command": "/align --docs",
        "reason": "synchronizes documentation with codebase automatically",
    },
    {
        "intent": [
            r'\b(implement|create|add|build|write|develop|fix|patch|refactor|update|modify)\b'
            r'.*\b(feature|function|class|method|module|component|api|endpoint|service|handler|'
            r'controller|model|interface|code|authentication|system|logic|workflow|validation|'
            r'integration|bug|test|app|application|tool|project|product|ui|frontend|backend|'
            r'page|screen|view|dashboard|wizard|dialog|widget|library|framework|database|'
            r'schema|migration|script)\b',
            r"(?:let'?s|we should|how do we|can we|I want to|I need to|we need to|we could)\s+"
            r"\b(implement|create|add|build|write|develop|fix|patch|refactor|update|modify)\b",
        ],
        "skip": [r'^/', r'\?$'],
        "command": "/implement",
        "reason": "handles testing, security review, and docs automatically",
    },
]


def detect_command_intent(user_input: str) -> Optional[Dict]:
    """
    Check user input against the command routing table.

    Returns the first matching route, or None if no match.

    Args:
        user_input: User prompt text

    Returns:
        Dict with 'command', 'reason', and optionally 'block', or None

    Example:
        >>> detect_command_intent("implement JWT authentication feature")
        {'command': '/implement', 'reason': '...', 'block': False}
        >>> detect_command_intent("/implement #123")
        None
        >>> detect_command_intent("How do I implement this?")
        None
    """
    if not user_input or not user_input.strip():
        return None

    text = user_input.strip()

    for route in COMMAND_ROUTES:
        # Check skip patterns first
        skip = False
        for skip_pattern in route["skip"]:
            if re.search(skip_pattern, text, re.IGNORECASE):
                skip = True
                break
        if skip:
            continue

        # Check intent patterns
        for intent_pattern in route["intent"]:
            if re.search(intent_pattern, text, re.IGNORECASE):
                return {
                    "command": route["command"],
                    "reason": route["reason"],
                    "block": route.get("block", False),
                }

    return None


def _format_nudge(command: str, reason: str) -> str:
    """Format a concise command suggestion nudge."""
    return (
        f'This looks like it needs {command} \u2014 {reason}.\n'
        f'  {command} "description"\n'
        f'Proceeding directly is fine for small changes.'
    )


def _format_block(command: str, reason: str, user_input: str) -> str:
    """Format a blocking message for bypass attempts."""
    preview = user_input[:100] + '...' if len(user_input) > 100 else user_input
    return (
        f'WORKFLOW BYPASS BLOCKED\n\n'
        f'Detected: {preview}\n\n'
        f'Use {command} instead \u2014 {reason}.\n'
        f'  {command} "description"\n\n'
        f'Set ENFORCE_WORKFLOW=false to disable this check.'
    )


# ============================================================================
# Activity Logging
# ============================================================================

def _log_activity(event: str, details: dict) -> None:
    """Append to shared activity log for full observability."""
    try:
        from datetime import datetime, timezone
        log_dir = Path(os.getcwd()) / ".claude" / "logs" / "activity"
        log_dir.mkdir(parents=True, exist_ok=True)
        date_str = datetime.now().strftime("%Y-%m-%d")
        entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "hook": "UserPromptSubmit",
            "event": event,
            "session_id": os.environ.get("CLAUDE_SESSION_ID", "unknown"),
            **details,
        }
        with open(log_dir / f"{date_str}.jsonl", "a") as f:
            f.write(json.dumps(entry, separators=(",", ":")) + "\n")
    except Exception:
        pass


# ============================================================================
# Plan Mode Enforcement (Issue #358)
# ============================================================================


def _extract_wrapped_command(text: str) -> Optional[tuple[str, str]]:
    """Parse Claude Code's XML-wrapped slash-command form.

    Claude Code wraps slash-commands before delivering them to UserPromptSubmit
    hooks as: <command-name>/cmd</command-name><command-args>...</command-args>.
    This helper extracts the command name (slash optional) and args string.

    Returns (command_name_without_slash, args_str) if the wrapped form is
    present, otherwise None. Issue #922.
    """
    name_match = re.search(r"<command-name>/?([\w-]+)</command-name>", text)
    if not name_match:
        return None
    args_match = re.search(r"<command-args>(.*?)</command-args>", text, re.DOTALL)
    args = args_match.group(1) if args_match else ""
    return name_match.group(1), args


def _check_plan_mode_enforcement(user_prompt: str) -> Optional[int]:
    """
    Enforce staged plan-exit pipeline after plan mode exit.

    Two-stage enforcement:
    - plan_exited: Plan-critic hasn't run yet. Block everything except
      questions and /implement --skip-review.
    - critique_done: Plan-critic completed. Allow /implement, /create-issue,
      /plan-to-issues (consume marker). Block everything else.

    Old markers without a stage field are treated as critique_done for
    backward compatibility. Unknown stage values are treated as plan_exited
    for safety.

    Args:
        user_prompt: The user's submitted prompt text

    Returns:
        None if no enforcement needed (pass through)
        0 if marker consumed by allowed command (pass through after cleanup)
        2 if prompt is blocked
    """
    try:
        marker_path = Path(os.getcwd()) / PLAN_MODE_EXIT_MARKER
        if not marker_path.exists():
            return None

        # Read marker to check staleness and stage
        try:
            marker_data = json.loads(marker_path.read_text())
            marker_ts = datetime.fromisoformat(marker_data.get("timestamp", ""))
            age_minutes = (datetime.now(timezone.utc) - marker_ts).total_seconds() / 60.0
            if age_minutes > PLAN_MODE_STALE_MINUTES:
                marker_path.unlink(missing_ok=True)
                return None
        except (json.JSONDecodeError, ValueError, KeyError):
            # Corrupted marker -- delete and pass through
            marker_path.unlink(missing_ok=True)
            return None

        # Determine stage (backward compat: missing stage = critique_done)
        raw_stage = marker_data.get("stage")
        if raw_stage is None:
            stage = "critique_done"
        elif raw_stage in ("plan_exited", "critique_done"):
            stage = raw_stage
        else:
            # Unknown stage value — treat as plan_exited for safety
            stage = "plan_exited"

        text = user_prompt.strip()

        # Allow questions through at any stage
        if text.endswith("?"):
            return None

        # /implement --skip-review consumes marker at any stage (escape hatch)
        # Handles both bare string form (programmatic / direct) and Claude Code's
        # XML-wrapped form (normal user path). Issue #922.
        wrapped = _extract_wrapped_command(text)
        is_skip_review = (
            re.match(r"^/implement\b.*--skip-review\b", text)
            or (wrapped is not None
                and wrapped[0] == "implement"
                and "--skip-review" in wrapped[1].split())
        )
        if is_skip_review:
            marker_path.unlink(missing_ok=True)
            return 0

        if stage == "plan_exited":
            # Block everything except questions (handled above) and --skip-review
            message = (
                "PLAN MODE EXIT DETECTED — Plan critique required\n\n"
                "You just exited plan mode. Before proceeding, you MUST run the "
                "plan-critic agent on your plan.\n\n"
                "After plan-critic completes with PROCEED verdict, the stage will "
                "automatically advance and you can use:\n"
                "  /implement \"description\"  -- to execute the plan\n"
                "  /create-issue \"description\"  -- to file an issue for later\n"
                "  /plan-to-issues  -- to convert plan into multiple issues\n\n"
                "Escape hatch: /implement --skip-review\n\n"
                "REQUIRED NEXT ACTION: Invoke the plan-critic agent."
            )
            print(message, file=sys.stderr)
            output = {
                "hookSpecificOutput": {
                    "hookEventName": "UserPromptSubmit",
                    "error": message,
                }
            }
            print(json.dumps(output))
            return 2

        # stage == "critique_done"
        # Allow /implement, /create-issue, /plan-to-issues (both bare and wrapped)
        # Issue #922: wrapped-form support added so normal post-plan-critic flow works.
        allowed = {"implement", "create-issue", "plan-to-issues"}
        is_allowed_command = (
            re.match(r"^/(implement|create-issue|plan-to-issues)\b", text)
            or (wrapped is not None and wrapped[0] in allowed)
        )
        if is_allowed_command:
            marker_path.unlink(missing_ok=True)
            return 0

        # Block everything else
        message = (
            "PLAN MODE EXIT DETECTED\n\n"
            "You just exited plan mode. Your next action must use one of:\n"
            "  /implement \"description\"  -- to execute the plan\n"
            "  /create-issue \"description\"  -- to file an issue for later\n"
            "  /plan-to-issues  -- to convert plan into multiple issues\n\n"
            "Direct editing after plan mode bypasses testing, security review, and docs.\n"
            "See: CLAUDE.md Critical Rules"
        )
        print(message, file=sys.stderr)
        output = {
            "hookSpecificOutput": {
                "hookEventName": "UserPromptSubmit",
                "error": message,
            }
        }
        print(json.dumps(output))
        return 2

    except Exception:
        # Never block on enforcement errors
        return None


# ============================================================================
# Compaction Recovery
# ============================================================================

COMPACTION_RECOVERY_MARKER = ".claude/compaction_recovery.json"


def _check_compaction_recovery() -> None:
    """
    Check for and process compaction recovery marker.

    If `.claude/compaction_recovery.json` exists, reads it, formats batch
    and/or pipeline context for stderr output, and deletes the marker.
    This re-injects state after context compaction.

    This function never raises exceptions and never blocks.
    """
    try:
        marker_path = Path(os.getcwd()) / COMPACTION_RECOVERY_MARKER
        if not marker_path.exists():
            return

        marker_data = json.loads(marker_path.read_text())

        all_lines: list = []

        # ----- Batch recovery section -----
        batch_id = marker_data.get("batch_id")
        if batch_id:
            current_index = marker_data.get("current_index", 0)
            total_features = marker_data.get("total_features", 0)
            features = marker_data.get("features", [])
            compact_summary = marker_data.get("compact_summary", "")
            checkpoint = marker_data.get("checkpoint", {})

            next_feature_num = current_index + 1

            # Get next feature description
            next_feature_desc = f"Feature {next_feature_num}"
            if features and current_index < len(features):
                feat = features[current_index]
                if isinstance(feat, str):
                    next_feature_desc = feat
                elif isinstance(feat, dict):
                    next_feature_desc = feat.get("description", feat.get("title", next_feature_desc))

            # Get completed/failed counts from checkpoint
            completed_count = len(checkpoint.get("completed_features", []))
            failed_count = len(checkpoint.get("failed_features", []))

            # Format recovery context
            all_lines.extend([
                "",
                "**BATCH STATE RECOVERED AFTER COMPACTION**",
                "",
                f"Batch ID: {batch_id}",
                f"Progress: Feature {next_feature_num} of {total_features}",
                f"Completed: {completed_count} | Failed: {failed_count}",
                "",
                f"Next Feature:",
                f"  {next_feature_desc}",
                "",
            ])

            if compact_summary:
                all_lines.extend([
                    "Compaction Summary:",
                    f"  {compact_summary}",
                    "",
                ])

            all_lines.extend([
                "CRITICAL WORKFLOW REQUIREMENT:",
                "- Use /implement for EACH remaining feature",
                "- NEVER implement directly (skips research, TDD, security audit, docs)",
                "- Check .claude/batch_state.json for current feature",
                "",
            ])

        # ----- Pipeline recovery section -----
        pipeline = marker_data.get("pipeline")
        if pipeline and isinstance(pipeline, dict):
            import time as _time

            # Validate staleness (>900s = discard)
            try:
                saved_at_str = pipeline.get("saved_at", "")
                if saved_at_str:
                    from datetime import datetime as _dt, timezone as _tz

                    saved_at = _dt.fromisoformat(saved_at_str.replace("Z", "+00:00"))
                    age_seconds = (_dt.now(_tz.utc) - saved_at).total_seconds()
                    if age_seconds > 900:
                        pipeline = None
            except (ValueError, TypeError):
                pipeline = None

            # Validate cwd match
            if pipeline:
                pipeline_cwd = pipeline.get("cwd", "")
                if pipeline_cwd and pipeline_cwd != os.getcwd():
                    pipeline = None

        if pipeline and isinstance(pipeline, dict):
            run_id = pipeline.get("run_id", "unknown")
            feature = pipeline.get("feature", "unknown")
            mode = pipeline.get("mode", "full")
            current_step = pipeline.get("current_step", "unknown")
            steps_completed = pipeline.get("steps_completed", 0)
            steps_remaining = pipeline.get("steps_remaining", 0)
            modified_files = pipeline.get("modified_files", [])

            all_lines.extend([
                "",
                "**PIPELINE STATE RECOVERED AFTER COMPACTION**",
                "",
                f"Run ID: {run_id}",
                f"Feature: {feature}",
                f"Mode: {mode}",
                f"Current Step: {current_step}",
                f"Steps Completed: {steps_completed} | Steps Remaining: {steps_remaining}",
                "",
            ])

            if modified_files:
                all_lines.append("Modified Files:")
                for f in modified_files:
                    all_lines.append(f"  - {f}")
                all_lines.append("")

            all_lines.extend([
                "CRITICAL: Resume /implement at current step",
                "",
            ])

        if all_lines:
            print("\n".join(all_lines), file=sys.stderr)

        # Delete marker after processing
        marker_path.unlink(missing_ok=True)

    except Exception:
        # Never block on recovery errors - silently continue
        try:
            marker_path = Path(os.getcwd()) / COMPACTION_RECOVERY_MARKER
            marker_path.unlink(missing_ok=True)
        except Exception:
            pass


# ============================================================================
# Main Hook Entry Point
# ============================================================================

def main() -> int:
    """
    Main hook entry point.

    Reads stdin for hook input, dispatches checks, outputs result.
    Handles both blocking checks (workflow bypass) and non-blocking
    nudges (command routing suggestions).

    Returns:
        0 if all checks pass or nudge detected (non-blocking)
        2 if workflow bypass detected (blocking)
    """
    # Check for compaction recovery before processing prompt
    _check_compaction_recovery()

    # Read input from stdin
    try:
        input_data = json.loads(sys.stdin.read())
    except json.JSONDecodeError:
        # Invalid input - allow to proceed
        output = {
            "hookSpecificOutput": {
                "hookEventName": "UserPromptSubmit"
            }
        }
        print(json.dumps(output))
        return 0

    # Extract user prompt
    user_prompt = input_data.get('userPrompt', '')
    prompt_preview = user_prompt[:200] if user_prompt else ''

    # Check plan mode enforcement (Issue #358)
    plan_mode_result = _check_plan_mode_enforcement(user_prompt)
    if plan_mode_result is not None:
        if plan_mode_result == 2:
            _log_activity("block", {
                "prompt": prompt_preview,
                "reason": "plan_mode_exit_enforcement",
                "decision": "block",
            })
            return 2
        # plan_mode_result == 0: marker consumed, continue normally

    # Detect command intent via routing table
    route = detect_command_intent(user_prompt)

    if route and route.get("block") and ENFORCE_WORKFLOW:
        _log_activity("block", {
            "prompt": prompt_preview,
            "suggested_command": route["command"],
            "reason": route["reason"],
            "decision": "block",
        })
        message = _format_block(route["command"], route["reason"], user_prompt)
        print(message, file=sys.stderr)
        output = {
            "hookSpecificOutput": {
                "hookEventName": "UserPromptSubmit",
                "error": message,
            }
        }
        print(json.dumps(output))
        return 2

    if route and QUALITY_NUDGE_ENABLED:
        _log_activity("nudge", {
            "prompt": prompt_preview,
            "suggested_command": route["command"],
            "reason": route["reason"],
            "decision": "nudge",
        })
        message = _format_nudge(route["command"], route["reason"])
        print(message, file=sys.stderr)
        output = {
            "hookSpecificOutput": {
                "hookEventName": "UserPromptSubmit",
                "nudge": message,
            }
        }
        print(json.dumps(output))
        return 0

    # Pass: no routing match
    _log_activity("pass", {
        "prompt": prompt_preview,
        "decision": "pass",
        "route_matched": False,
    })
    output = {
        "hookSpecificOutput": {
            "hookEventName": "UserPromptSubmit"
        }
    }
    print(json.dumps(output))
    return 0


if __name__ == "__main__":
    sys.exit(main())
