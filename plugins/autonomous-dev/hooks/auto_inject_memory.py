#!/usr/bin/env python3
"""
Auto Inject Memory Hook - SessionStart hook for memory injection.

Triggers at SessionStart lifecycle event to inject relevant memories from
previous sessions into the current prompt, enabling cross-session context
continuity.

Problem (Issue #192):
- No persistent context across sessions
- Agents forget architectural decisions, patterns, blockers
- Manual context recovery is slow and error-prone

Solution:
- SessionStart hook triggers on new session/conversation
- Loads memories from .claude/memories/session_memories.json
- Ranks by relevance using TF-IDF scoring
- Formats within token budget (default: 500 tokens)
- Injects into prompt as markdown context block

Hook Lifecycle:
    SessionStart -> load_memories -> rank -> format -> inject -> modified_prompt

Environment Variables:
    - MEMORY_INJECTION_ENABLED: Enable/disable injection (default: false)
    - MEMORY_INJECTION_TOKEN_BUDGET: Max tokens for memories (default: 500)
    - MEMORY_RELEVANCE_THRESHOLD: Min relevance score (default: 0.7)

Usage:
    # Hook is automatically triggered by Claude Code at SessionStart
    # No manual invocation needed

    # To enable memory injection:
    export MEMORY_INJECTION_ENABLED=true

    # To customize token budget:
    export MEMORY_INJECTION_TOKEN_BUDGET=1000

    # To customize relevance threshold:
    export MEMORY_RELEVANCE_THRESHOLD=0.5

Date: 2026-01-02
Issue: GitHub #192 (Auto-inject memory layer at SessionStart)
Agent: implementer
Phase: GREEN (making tests pass)

Design Patterns:
    See hook-design-patterns skill for SessionStart hook patterns.
    See error-handling-patterns skill for graceful degradation.
    See python-standards skill for coding conventions.
"""

import os
import sys
from pathlib import Path

# Add lib to path for imports (portable path detection)
current = Path.cwd()
while current != current.parent:
    if (current / ".git").exists() or (current / ".claude").exists():
        project_root = current
        break
    current = current.parent
else:
    project_root = Path.cwd()

lib_path = project_root / "plugins/autonomous-dev/lib"
if lib_path.exists():
    sys.path.insert(0, str(lib_path))


# Import dependencies (with graceful degradation)
try:
    from auto_inject_memory import inject_memories_into_prompt, should_inject_memories
    from security_utils import audit_log
except ImportError:
    # Graceful degradation
    inject_memories_into_prompt = None
    should_inject_memories = None
    audit_log = None


# ============================================================================
# HOOK HANDLER
# ============================================================================


def handle_session_start(event: dict) -> dict:
    """Handle SessionStart lifecycle event.

    Called by Claude Code when a new session/conversation starts.
    Injects relevant memories into the initial prompt.

    Args:
        event: SessionStart event dict with:
            - "prompt": Initial user prompt
            - "session_id": Session identifier
            - "timestamp": Session start timestamp

    Returns:
        Modified event dict with enhanced prompt (or original if disabled/error)

    Example:
        >>> event = {"prompt": "Implement JWT authentication", "session_id": "abc123"}
        >>> modified = handle_session_start(event)
        >>> print(modified["prompt"])
        ## Relevant Context from Previous Sessions
        ...
        Implement JWT authentication
    """
    # Graceful degradation if dependencies unavailable
    if not (inject_memories_into_prompt and should_inject_memories):
        return event

    # Check if injection enabled
    if not should_inject_memories():
        return event

    try:
        # Extract original prompt
        original_prompt = event.get("prompt", "")

        # Get token budget from environment (default: 500)
        max_tokens = int(os.environ.get("MEMORY_INJECTION_TOKEN_BUDGET", "500"))

        # Inject memories into prompt
        enhanced_prompt = inject_memories_into_prompt(
            original_prompt=original_prompt,
            project_root=project_root,
            max_tokens=max_tokens
        )

        # Update event with enhanced prompt
        event["prompt"] = enhanced_prompt

        # Audit log
        if audit_log:
            audit_log(
                "session_start_hook",
                "info",
                f"Injected memories into session {event.get('session_id', 'unknown')}"
            )

    except Exception as e:
        # Graceful degradation on errors
        if audit_log:
            audit_log(
                "session_start_hook",
                "error",
                f"Failed to inject memories: {e}"
            )
        # Return original event unchanged

    return event


# ============================================================================
# HOOK ENTRY POINT
# ============================================================================

def main(event: dict) -> dict:
    """Main entry point for SessionStart hook.

    Args:
        event: SessionStart event dict

    Returns:
        Modified event dict with enhanced prompt
    """
    return handle_session_start(event)


if __name__ == "__main__":
    # Test hook execution
    test_event = {
        "prompt": "Implement JWT authentication",
        "session_id": "test_session",
        "timestamp": "2026-01-02T15:30:00Z"
    }

    result = main(test_event)
    print(f"Original prompt: {test_event['prompt']}")
    print(f"Enhanced prompt: {result['prompt']}")
