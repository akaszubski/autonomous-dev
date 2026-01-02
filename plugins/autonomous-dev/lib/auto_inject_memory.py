#!/usr/bin/env python3
"""
Auto Inject Memory - Memory injection logic for SessionStart hook.

Provides memory injection functionality for SessionStart hook, enabling
cross-session context continuity. Loads, ranks, and formats relevant memories
from storage and injects them into the prompt.

Problem (Issue #192):
- Need to inject relevant memories at SessionStart
- Must respect token budget constraints
- Graceful degradation when memory system unavailable
- Environment variable control for enablement

Solution:
- Load memories from .claude/memories/session_memories.json
- Rank by relevance using memory_relevance library
- Format with token budget using memory_formatter library
- Inject into prompt with markdown structure
- Environment variable: MEMORY_INJECTION_ENABLED (default: false)

Usage:
    from auto_inject_memory import inject_memories_into_prompt

    # Inject memories (respects MEMORY_INJECTION_ENABLED env var)
    enhanced_prompt = inject_memories_into_prompt(
        original_prompt="Implement JWT authentication",
        project_root=Path("/path/to/project"),
        max_tokens=500
    )

    # Check if injection enabled
    if should_inject_memories():
        # ... do injection ...

    # Load relevant memories
    memories = load_relevant_memories(
        query="JWT authentication",
        project_root=Path("/path/to/project"),
        threshold=0.7
    )

Date: 2026-01-02
Issue: GitHub #192 (Auto-inject memory layer at SessionStart)
Agent: implementer
Phase: GREEN (making tests pass)

Design Patterns:
    See library-design-patterns skill for graceful degradation patterns.
    See error-handling-patterns skill for error handling.
    See python-standards skill for coding conventions.
"""

import json
import os
from pathlib import Path
from typing import List, Dict, Any, Optional

# Import dependencies (with graceful degradation)
try:
    # Try absolute imports first (for pytest)
    try:
        from autonomous_dev.lib import memory_relevance, memory_formatter
        from autonomous_dev.lib.path_utils import get_project_root
        from autonomous_dev.lib.security_utils import audit_log
    except ImportError:
        # Fall back to relative imports (for direct execution)
        import memory_relevance
        import memory_formatter
        from path_utils import get_project_root
        from security_utils import audit_log

    DEFAULT_TOKEN_BUDGET = memory_formatter.DEFAULT_TOKEN_BUDGET
except ImportError:
    # Graceful degradation for testing/development
    memory_relevance = None
    memory_formatter = None
    DEFAULT_TOKEN_BUDGET = 500
    get_project_root = None
    audit_log = None


# ============================================================================
# CONSTANTS
# ============================================================================

MEMORY_FILE_PATH = ".claude/memories/session_memories.json"
DEFAULT_RELEVANCE_THRESHOLD = 0.0  # Include all memories by default, let token budget control what's shown


# ============================================================================
# ENVIRONMENT VARIABLE CONTROL
# ============================================================================


def should_inject_memories() -> bool:
    """Check if memory injection is enabled via environment variable.

    Environment variable: MEMORY_INJECTION_ENABLED
    - "true" / "TRUE" / "1" -> enabled
    - "false" / "FALSE" / "0" -> disabled
    - Not set -> disabled (default)

    Returns:
        True if memory injection enabled, False otherwise
    """
    env_value = os.environ.get("MEMORY_INJECTION_ENABLED", "false").lower()
    return env_value in ("true", "1", "yes")


# ============================================================================
# MEMORY LOADING
# ============================================================================


def load_relevant_memories(
    query: str,
    project_root: Optional[Path] = None,
    threshold: float = DEFAULT_RELEVANCE_THRESHOLD
) -> List[Dict[str, Any]]:
    """Load and rank memories by relevance to query.

    Loads memories from .claude/memories/session_memories.json,
    ranks by relevance using TF-IDF scoring, and filters by threshold.

    Args:
        query: Query text (e.g., "implement JWT authentication")
        project_root: Project root directory (default: auto-detect)
        threshold: Minimum relevance score (default: 0.7)

    Returns:
        List of ranked memories (sorted by relevance, descending)

    Example:
        >>> memories = load_relevant_memories(
        ...     "JWT authentication",
        ...     project_root=Path("/path/to/project")
        ... )
        [{"content": "...", "relevance_score": 0.85, ...}, ...]
    """
    # Auto-detect project root if not provided
    if project_root is None:
        if get_project_root:
            project_root = get_project_root()
        else:
            project_root = Path.cwd()

    # Build memory file path
    memory_file = project_root / MEMORY_FILE_PATH

    # Check if memory file exists
    if not memory_file.exists():
        return []

    try:
        # Load memories from file
        with memory_file.open("r") as f:
            memories_data = json.load(f)

        # Handle different data formats
        if isinstance(memories_data, list):
            memories = memories_data
        elif isinstance(memories_data, dict) and "memories" in memories_data:
            memories = memories_data["memories"]
        else:
            return []

        # Rank memories by relevance
        if memory_relevance:
            try:
                ranked = memory_relevance.rank_memories(query, memories, threshold=threshold)
            except Exception as e:
                # Graceful degradation if ranking fails
                if audit_log:
                    audit_log("memory_injection", "error", f"Ranking failed: {e}")
                # Return empty to prevent bad data from being injected
                return []
        else:
            # Fallback: return all memories without ranking
            ranked = memories

        return ranked

    except (json.JSONDecodeError, IOError, PermissionError) as e:
        # Graceful degradation on errors
        if audit_log:
            audit_log("memory_injection", "warning", f"Failed to load memories: {e}")
        return []

    except Exception as e:
        # Catch-all for unexpected errors
        if audit_log:
            audit_log("memory_injection", "error", f"Unexpected error loading memories: {e}")
        return []


# ============================================================================
# PROMPT INJECTION
# ============================================================================


def inject_memories_into_prompt(
    original_prompt: str,
    project_root: Optional[Path] = None,
    max_tokens: int = DEFAULT_TOKEN_BUDGET
) -> str:
    """Inject relevant memories into prompt.

    Checks if injection enabled, loads relevant memories, formats within
    token budget, and injects into prompt.

    Args:
        original_prompt: Original user prompt
        project_root: Project root directory (default: auto-detect)
        max_tokens: Maximum token budget for memories (default: 500)

    Returns:
        Enhanced prompt with memories injected (or original if disabled/no memories)

    Example:
        >>> inject_memories_into_prompt(
        ...     "Implement JWT authentication",
        ...     max_tokens=500
        ... )
        "## Relevant Context from Previous Sessions\n\n...\n\nImplement JWT authentication"
    """
    # Check if injection enabled
    if not should_inject_memories():
        return original_prompt

    # Graceful degradation if dependencies unavailable
    if not (memory_relevance and memory_formatter):
        return original_prompt

    try:
        # Load relevant memories
        memories = load_relevant_memories(
            query=original_prompt,
            project_root=project_root,
            threshold=DEFAULT_RELEVANCE_THRESHOLD
        )

        # If no memories found, return original prompt
        if not memories:
            return original_prompt

        # Format memories within token budget
        formatted_memories = memory_formatter.format_memories_with_budget(memories, max_tokens)

        # If formatting failed or empty, return original prompt
        if not formatted_memories:
            return original_prompt

        # Inject memories before original prompt
        enhanced_prompt = f"{formatted_memories}\n\n{original_prompt}"

        return enhanced_prompt

    except Exception as e:
        # Graceful degradation on errors
        if audit_log:
            audit_log("memory_injection", "error", f"Failed to inject memories: {e}")
        return original_prompt


# ============================================================================
# MODULE EXPORTS
# ============================================================================

__all__ = [
    "should_inject_memories",
    "load_relevant_memories",
    "inject_memories_into_prompt",
]
