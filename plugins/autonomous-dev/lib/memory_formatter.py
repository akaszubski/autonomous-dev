#!/usr/bin/env python3
"""
Memory Formatter - Format memories with token budget constraints.

Provides token counting, memory block formatting, and budget-aware formatting
for cross-session memory injection. Ensures injected memories stay within
token budget to prevent context bloat.

Problem (Issue #192):
- Need to format memories for injection into prompts
- Must respect token budget to prevent context bloat
- Need markdown formatting for readability
- Prioritize high-relevance memories when budget constrained

Solution:
- Token counting using character-based estimation
- Markdown formatting with structure and metadata
- Budget-aware truncation (prioritize high-relevance)
- Graceful degradation when budget exceeded

Usage:
    from memory_formatter import count_tokens, format_memory_block, format_memories_with_budget

    # Count tokens
    tokens = count_tokens("Hello world")
    # -> 2

    # Format single memory
    formatted = format_memory_block({
        "content": "Implemented JWT authentication",
        "timestamp": "2026-01-02T10:00:00",
        "relevance_score": 0.85
    })
    # -> "**Relevance: 0.85** | 2026-01-02\nImplemented JWT authentication"

    # Format with budget
    formatted = format_memories_with_budget(
        memories=[...],
        max_tokens=500
    )
    # -> "## Relevant Context from Previous Sessions\n\n..."

Date: 2026-01-02
Issue: GitHub #192 (Auto-inject memory layer at SessionStart)
Agent: implementer
Phase: GREEN (making tests pass)

Design Patterns:
    See library-design-patterns skill for formatting patterns.
    See python-standards skill for coding conventions.
"""

import re
from datetime import datetime
from typing import List, Dict, Any


# ============================================================================
# CONSTANTS
# ============================================================================

# Token estimation: ~4 characters per token (conservative estimate)
CHARS_PER_TOKEN = 4

# Default token budget for memory injection
DEFAULT_TOKEN_BUDGET = 500


# ============================================================================
# TOKEN COUNTING
# ============================================================================


def count_tokens(text: str) -> int:
    """Count tokens in text using character-based estimation.

    Uses conservative estimate: ~4 characters per token
    This approximation is faster than tiktoken and sufficient for budgeting.

    Args:
        text: Input text to count tokens

    Returns:
        Estimated token count

    Example:
        >>> count_tokens("Hello world")
        3  # "Hello world" = 11 chars / 4 = ~3 tokens
    """
    if not text or not isinstance(text, str):
        return 0

    # Character-based estimation
    char_count = len(text)
    token_count = (char_count + CHARS_PER_TOKEN - 1) // CHARS_PER_TOKEN  # Round up

    return token_count


# ============================================================================
# MEMORY BLOCK FORMATTING
# ============================================================================


def format_memory_block(memory: Dict[str, Any]) -> str:
    """Format a single memory block with metadata.

    Creates markdown-formatted memory block with:
    - Relevance score (if present)
    - Timestamp (formatted for readability)
    - Memory content

    Args:
        memory: Memory dict with "content" and optional metadata

    Returns:
        Formatted markdown string

    Example:
        >>> format_memory_block({
        ...     "content": "Implemented JWT authentication",
        ...     "timestamp": "2026-01-02T10:00:00",
        ...     "relevance_score": 0.85
        ... })
        "**Relevance: 0.85** | 2026-01-02 10:00\nImplemented JWT authentication"
    """
    # Extract fields
    content = memory.get("content", "")
    timestamp = memory.get("timestamp", "")
    relevance_score = memory.get("relevance_score")

    # Format timestamp (convert ISO 8601 to readable format)
    formatted_time = ""
    if timestamp:
        try:
            if isinstance(timestamp, str):
                dt = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
                formatted_time = dt.strftime("%Y-%m-%d %H:%M")
            else:
                formatted_time = str(timestamp)
        except (ValueError, AttributeError):
            formatted_time = str(timestamp)

    # Build metadata line
    metadata_parts = []
    if relevance_score is not None:
        metadata_parts.append(f"**Relevance: {relevance_score:.2f}**")
    if formatted_time:
        metadata_parts.append(formatted_time)

    # Build formatted block
    if metadata_parts:
        metadata_line = " | ".join(metadata_parts)
        formatted = f"{metadata_line}\n{content}"
    else:
        formatted = content

    return formatted


# ============================================================================
# BUDGET-AWARE FORMATTING
# ============================================================================


def format_memories_with_budget(
    memories: List[Dict[str, Any]],
    max_tokens: int = DEFAULT_TOKEN_BUDGET
) -> str:
    """Format memories within token budget.

    Includes header, prioritizes high-relevance memories, and truncates
    gracefully when budget exceeded.

    Args:
        memories: List of memory dicts (sorted by relevance)
        max_tokens: Maximum token budget (default: 500)

    Returns:
        Formatted markdown string with header and memories

    Example:
        >>> format_memories_with_budget(
        ...     [{"content": "Memory 1", "relevance_score": 0.9}],
        ...     max_tokens=100
        ... )
        "## Relevant Context from Previous Sessions\n\nMemory 1"
    """
    # Handle empty inputs
    if not memories or max_tokens <= 0:
        return ""

    # Header
    header = "## Relevant Context from Previous Sessions\n\n"
    header_tokens = count_tokens(header)

    # Calculate available budget for memories
    available_tokens = max_tokens - header_tokens

    # Handle case where header exceeds budget
    if available_tokens <= 0:
        return ""

    # Format memories within budget
    formatted_memories = []
    total_tokens = 0

    for memory in memories:
        # Format memory block
        formatted_block = format_memory_block(memory)

        # Add separator between memories
        if formatted_memories:
            formatted_block = "\n\n" + formatted_block

        # Count tokens
        block_tokens = count_tokens(formatted_block)

        # Check if adding this memory would exceed budget
        if total_tokens + block_tokens > available_tokens:
            # Try to include at least one memory (truncate if needed)
            if not formatted_memories:
                # Truncate content to fit budget
                max_chars = available_tokens * CHARS_PER_TOKEN
                if len(formatted_block) > max_chars and max_chars > 3:
                    formatted_block = formatted_block[:max_chars - 3] + "..."
                    formatted_memories.append(formatted_block)
                # If even truncated doesn't fit, return empty
                # (budget too small for any meaningful content)
            break

        # Add memory to output
        formatted_memories.append(formatted_block)
        total_tokens += block_tokens

    # Handle case where no memories fit
    if not formatted_memories:
        return ""

    # Build final output
    result = header + "".join(formatted_memories)

    # Final safety check: ensure result is within budget
    result_tokens = count_tokens(result)
    if result_tokens > max_tokens:
        # Budget too small - return empty
        return ""

    return result


# ============================================================================
# MODULE EXPORTS
# ============================================================================

__all__ = [
    "count_tokens",
    "format_memory_block",
    "format_memories_with_budget",
    "DEFAULT_TOKEN_BUDGET",
]
