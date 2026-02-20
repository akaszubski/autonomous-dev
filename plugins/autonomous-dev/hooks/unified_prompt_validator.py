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
            r'integration|bug|test)\b',
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
