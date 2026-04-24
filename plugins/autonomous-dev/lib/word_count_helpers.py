"""Shared word-count helper for Claude Code message-content payloads.

Handles both the legacy flat-string shape and the modern list-of-text-blocks
shape used by Anthropic Task/Agent toolUseResult payloads.

Issue #925: created to fix _add_result_word_count false-positive root cause.
"""


def count_words_in_content(content) -> int:
    """Count words in a Claude Code message-content payload.

    Handles str, list of {'type':'text','text':...} blocks, or None.
    Returns 0 for any other shape. Never raises.

    Args:
        content: A string, list of content blocks, or None.

    Returns:
        Total word count, or 0 for unrecognised shapes.
    """
    try:
        if content is None:
            return 0
        if isinstance(content, str):
            return len(content.split())
        if isinstance(content, list):
            total = 0
            for block in content:
                if isinstance(block, dict) and block.get("type") == "text":
                    total += len(block.get("text", "").split())
            return total
        return 0
    except Exception:
        return 0
