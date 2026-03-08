#!/usr/bin/env python3
"""
Workflow Bypass Detection Hook - Blocks Explicit Pipeline Bypass Attempts

This hook runs on UserPromptSubmit to detect when the user is explicitly
trying to bypass the /create-issue workflow (e.g., "gh issue create").

Issue #141: Removed intent detection (doesn't work - Claude rephrases).
Now focuses only on BLOCKING explicit bypass attempts.

What this hook does:
- BLOCKS: "gh issue create" (direct gh CLI bypass)
- BLOCKS: "skip /create-issue" (explicit bypass language)
- PASSES: Everything else (intent detection removed)

What was removed (Issue #141):
- Feature request detection (Claude rephrases to avoid patterns)
- "implement X", "add X" patterns (easily bypassed)
- Warning messages suggesting /auto-implement

Philosophy: Hooks cannot detect intent. Instead of trying to detect
"did Claude mean to implement?", we:
1. Keep deterministic blocks (explicit bypasses)
2. Add persuasion to CLAUDE.md (data-driven)
3. Make /auto-implement faster (convenience)
4. Let skills guide agents (knowledge)

Exit codes:
- 0: Pass - Not a bypass attempt (proceed normally)
- 2: Block - Bypass attempt detected (enforce /create-issue workflow)

Environment Variables:
- ENFORCE_WORKFLOW: Enable/disable enforcement (default: true)
  Set to "false" to disable bypass detection
"""

import os
import sys
import re


def is_bypass_attempt(user_input: str) -> bool:
    """
    Detect if user input is attempting to bypass proper workflow.

    Triggers on patterns that try to skip /create-issue pipeline:
    - "gh issue create" (direct gh CLI usage)
    - "skip /create-issue" / "bypass /create-issue" (explicit bypass)

    Does NOT trigger on:
    - "/create-issue" command itself (that's the CORRECT workflow)
    - Feature requests like "implement X" (moved to persuasion, not enforcement)

    Returns:
        True if bypass attempt detected, False otherwise
    """
    # Convert to lowercase for matching
    text = user_input.lower()

    # Explicit bypass language (skip/bypass) - check FIRST
    # "skip /create-issue" or "bypass /create-issue" are ALWAYS bypass attempts
    if re.search(r'\b(skip|bypass)\s+/?(create-issue|auto-implement)', text, re.IGNORECASE):
        return True

    # Check for legitimate /create-issue command (without skip/bypass)
    # This is the CORRECT workflow and should not be blocked
    if re.search(r'/create[\s-]issue', text, re.IGNORECASE):
        return False

    # Direct gh CLI usage to create issues (bypasses research, validation)
    if re.search(r'\bgh\s+issue\s+create\b', text, re.IGNORECASE):
        return True

    return False


def get_bypass_message(user_input: str) -> str:
    """
    Generate blocking message when bypass attempt is detected.

    Returns:
        Formatted message explaining why bypass is blocked and correct workflow
    """
    return f"""
WORKFLOW BYPASS BLOCKED

Detected Pattern: {user_input[:100]}{'...' if len(user_input) > 100 else ''}

You MUST use the correct workflow:
  /create-issue "description"

Why This Is Blocked:
- Direct issue creation bypasses duplicate detection
- Skips research integration (cached for /auto-implement)
- No PROJECT.md alignment validation

Correct Workflow:
1. Run: /create-issue "feature description"
2. Command validates + researches + creates issue
3. Optionally run: /auto-implement "#123"

To Disable (not recommended):
  Set ENFORCE_WORKFLOW=false in .env file
"""


def should_block():
    """
    Determine if the prompt should be blocked.

    Reads from stdin (user's message) and checks for bypass attempts.

    Returns:
        True if bypass attempt detected (should block)
        False if normal prompt (proceed normally)
    """
    # Check if enforcement is enabled (default: true)
    enforce_workflow = os.getenv("ENFORCE_WORKFLOW", "true").lower() == "true"

    # If enforcement disabled, pass through all prompts
    if not enforce_workflow:
        return False

    # Read user input from stdin
    user_input = sys.stdin.read().strip()

    # Skip if empty
    if not user_input:
        return False

    # Check for bypass attempts (BLOCK)
    if is_bypass_attempt(user_input):
        # Print blocking message to stderr (visible to user)
        print(get_bypass_message(user_input), file=sys.stderr)
        return True

    # Normal prompt - proceed
    return False


def main() -> int:
    """
    Main entry point for bypass detection hook.

    Returns:
        0 - Pass: Not a bypass attempt (proceed normally)
        2 - Block: Bypass attempt detected (enforce /create-issue workflow)
    """
    try:
        if should_block():
            # Bypass attempt - BLOCK the prompt
            return 2
        else:
            # Normal prompt - PASS through
            return 0

    except Exception as e:
        # On error, don't block - proceed normally
        print(f"Warning: Bypass detection error: {e}", file=sys.stderr)
        return 0


if __name__ == "__main__":
    sys.exit(main())
