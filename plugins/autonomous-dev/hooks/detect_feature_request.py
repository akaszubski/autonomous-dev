#!/usr/bin/env python3
"""
Feature Request Detection Hook - Auto-Orchestration Engine

This hook runs on UserPromptSubmit to detect when the user is requesting
a feature implementation via natural language ("vibe coding").

When detected, it automatically invokes the orchestrator agent which:
1. Checks PROJECT.md alignment FIRST
2. Blocks work if feature not in SCOPE
3. Triggers full agent pipeline if aligned

Issue #137: Enhanced with workflow bypass detection to enforce proper
pipelines and prevent shortcuts that skip validation steps.

Relevant Skills:
- project-alignment-validation: Semantic validation approach for request understanding

Usage:
    Add to .claude/settings.local.json:
    {
      "hooks": {
        "UserPromptSubmit": [
          {
            "type": "command",
            "command": "python .claude/hooks/detect_feature_request.py"
          }
        ]
      }
    }

Exit codes:
- 0: Pass - Not a feature request (proceed normally)
- 1: Warn - Feature request detected (suggest /auto-implement)
- 2: Block - Bypass attempt detected (enforce /create-issue workflow)

Environment Variables:
- ENFORCE_WORKFLOW: Enable/disable enforcement (default: true)
  Set to "false" to disable all workflow enforcement
"""

import os
import sys
import re
from pathlib import Path


def is_feature_request(user_input: str) -> bool:
    """
    Detect if user input is requesting feature implementation.

    Triggers on keywords like:
    - "implement X"
    - "add X"
    - "create X"
    - "build X"
    - "develop X"
    - "write X"
    - "make X"

    Returns:
        True if feature request detected, False otherwise
    """
    # Convert to lowercase for matching
    text = user_input.lower()

    # Feature request patterns (check BEFORE exclusions)
    # These are strong indicators of feature requests
    strong_patterns = [
        # "Can you implement/add..." (even with question mark, this is a request)
        r'\b(can\s+you|could\s+you|please)\s+(implement|add|create|build|write|make)',

        # "I want/need to..."
        r'\b(i\s+want|i\s+need|i\'d\s+like)\s+to\s+(implement|add|create|build)',
    ]

    for pattern in strong_patterns:
        if re.search(pattern, text, re.IGNORECASE):
            return True

    # Exclude questions and queries (these shouldn't trigger)
    exclusion_patterns = [
        r'^\s*(what|why|how|when|where|who|explain|describe|tell\s+me)',
        r'^\s*(show|display|list|find|search)',
        r'\?$',  # Ends with question mark
    ]

    for pattern in exclusion_patterns:
        if re.search(pattern, text, re.IGNORECASE):
            return False

    # Regular feature request patterns
    patterns = [
        # Direct implementation requests
        r'\b(implement|add|create|build|develop|write|make)\s+',

        # "Let's implement/add..."
        r'\b(let\'s|lets)\s+(implement|add|create|build|write|make)',

        # Feature-specific keywords
        r'\b(new\s+feature|feature\s+request)',
        r'\b(authentication|authorization|user\s+management)',
        r'\b(api\s+endpoint|rest\s+api|graphql)',
        r'\b(database|model|schema)',
        r'\b(ui\s+component|frontend|backend)',
    ]

    # Check if any pattern matches
    for pattern in patterns:
        if re.search(pattern, text, re.IGNORECASE):
            return True

    return False


def is_bypass_attempt(user_input: str) -> bool:
    """
    Detect if user input is attempting to bypass proper workflow.

    Triggers on patterns that try to skip /create-issue pipeline:
    - "gh issue create" (direct gh CLI usage)
    - "create issue" / "create github issue" (asking Claude to bypass)
    - "make issue" / "open issue" / "file issue" (similar bypass attempts)
    - "skip /create-issue" / "bypass /create-issue" (explicit bypass)

    Does NOT trigger on:
    - "/create-issue" command itself (that's the CORRECT workflow)

    Returns:
        True if bypass attempt detected, False otherwise
    """
    # Convert to lowercase for matching
    text = user_input.lower()

    # Explicit bypass language (skip/bypass) - check FIRST
    # "skip /create-issue" or "bypass /create-issue" are ALWAYS bypass attempts
    if re.search(r'\b(skip|bypass)\s+', text, re.IGNORECASE):
        return True

    # Check for legitimate /create-issue command (without skip/bypass)
    # This is the CORRECT workflow and should not be blocked
    if re.search(r'/create[\s-]issue', text, re.IGNORECASE):
        return False

    # Bypass attempt patterns
    bypass_patterns = [
        # Direct gh CLI usage
        r'\bgh\s+issue\s+create\b',

        # Asking Claude to create issue (bypass /create-issue workflow)
        r'\b(create|make|open|file)\s+(a\s+)?(new\s+)?(github\s+)?issue\b',
    ]

    # Check if any bypass pattern matches
    for pattern in bypass_patterns:
        if re.search(pattern, text, re.IGNORECASE):
            return True

    return False


def get_bypass_message(user_input: str) -> str:
    """
    Generate blocking message when bypass attempt is detected.

    Returns:
        Formatted message explaining why bypass is blocked and correct workflow
    """
    return f"""
🚫 **WORKFLOW BYPASS BLOCKED**

**Detected Pattern**: {user_input[:100]}{'...' if len(user_input) > 100 else ''}

**SECURITY: You MUST use the correct workflow**:
  /create-issue {user_input[:60]}{'...' if len(user_input) > 60 else ''}

**Why This Is Blocked**:
- ❌ Direct issue creation bypasses validation
- ❌ Skips duplicate detection
- ❌ Skips research integration
- ❌ No cache for /auto-implement reuse

**Correct Workflow**:
1. Run: /create-issue "feature description"
2. Command validates + researches + creates issue
3. Optionally run: /auto-implement "#123"

**To Disable** (not recommended):
  Set ENFORCE_WORKFLOW=false in .env file

**DO NOT attempt to bypass this workflow** - Use the /create-issue command above.
"""


def get_orchestrator_message(user_input: str) -> str:
    """
    Generate message to display when feature request is detected.

    Returns:
        Formatted message reminding Claude to invoke /auto-implement
    """
    return f"""
🎯 **STRICT MODE: Feature Request Detected**

**User Request**: {user_input[:100]}{'...' if len(user_input) > 100 else ''}

**ACTION REQUIRED**: You MUST run /auto-implement command now:
  /auto-implement "{user_input[:80]}{'...' if len(user_input) > 80 else ''}"

**Why**: Strict mode requires orchestrator to validate PROJECT.md alignment
before any implementation work begins. This ensures:
- ✅ Feature aligns with PROJECT.md (GOALS, SCOPE, CONSTRAINTS)
- ✅ Full agent pipeline executes (researcher → planner → test-master → implementer → reviewer → security-auditor → doc-master)
- ✅ SDLC best practices enforced automatically
- ✅ Background validation via PreCommit hooks

**DO NOT respond conversationally** - Run the command above to trigger the autonomous workflow.
"""


def should_invoke_orchestrator():
    """
    Determine if orchestrator should be invoked based on user input.

    Reads from stdin (user's message) and applies feature detection.

    Returns:
        True if orchestrator should be invoked (feature request)
        "BLOCK" if bypass attempt detected (workflow violation)
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

    # PRIORITY 1: Check for bypass attempts (BLOCK immediately)
    if is_bypass_attempt(user_input):
        # Print blocking message to stderr (visible to user)
        print(get_bypass_message(user_input), file=sys.stderr)
        return "BLOCK"

    # PRIORITY 2: Check if this is a feature request (WARN)
    if is_feature_request(user_input):
        # Print orchestrator message to stderr (visible to user)
        print(get_orchestrator_message(user_input), file=sys.stderr)
        return True

    # Normal prompt - proceed
    return False


def main() -> int:
    """
    Main entry point for feature detection hook.

    Returns:
        0 - Pass: Not a feature request (proceed normally)
        1 - Warn: Feature request detected (suggest /auto-implement)
        2 - Block: Bypass attempt detected (enforce /create-issue workflow)
    """
    try:
        result = should_invoke_orchestrator()

        if result == "BLOCK":
            # Bypass attempt - BLOCK the prompt
            return 2
        elif result is True:
            # Feature request detected - WARN user to use /auto-implement
            return 1
        else:
            # Normal prompt - PASS through
            return 0

    except Exception as e:
        # On error, don't block - proceed normally
        print(f"Warning: Feature detection error: {e}", file=sys.stderr)
        return 0


if __name__ == "__main__":
    sys.exit(main())
