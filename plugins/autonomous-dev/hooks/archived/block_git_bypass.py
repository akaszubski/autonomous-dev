#!/usr/bin/env python3
"""
Block Git Bypass Hook - Prevent bypassing pre-commit hooks with --no-verify.

This PreCommit hook detects and blocks attempts to use git commit --no-verify,
which would bypass pre-commit hooks. This is part of workflow enforcement to
ensure all code goes through proper validation.

Hook Purpose:
- Prevents bypassing pre-commit hooks with --no-verify or -n flags
- Logs violations to workflow_violation_logger
- Provides clear guidance on proper workflow
- Can be bypassed with ALLOW_GIT_BYPASS=true for emergencies

Exit Codes:
- EXIT_SUCCESS (0): Commit allowed
- EXIT_BLOCK (2): Commit blocked (bypass attempt detected)

Environment Variables:
- ALLOW_GIT_BYPASS: Set to "true" to allow bypass in emergencies
- CLAUDE_AGENT_NAME: If set, included in violation logs

Usage:
    This hook is automatically invoked by git during pre-commit phase.
    It receives git command via sys.argv.

Date: 2026-01-19
Issue: #250 (Enforce /implement workflow)
Agent: implementer
Phase: TDD Green (making tests pass)
"""

import os
import sys
from pathlib import Path
from typing import Tuple


# Add lib directory to path for imports
sys.path.insert(
    0,
    str(Path(__file__).parent.parent.parent / "plugins" / "autonomous-dev" / "lib"),
)

# Exit codes
EXIT_SUCCESS = 0
EXIT_BLOCK = 2

# Import workflow violation logger (will fail gracefully if not available)
try:
    from workflow_violation_logger import WorkflowViolationLogger
    _logger_available = True
except ImportError:
    _logger_available = False


def detect_git_bypass(command: str) -> Tuple[bool, str]:
    """Detect --no-verify flag in git command.

    Args:
        command: Full git command string

    Returns:
        Tuple of (is_bypass, reason)
        - is_bypass: True if bypass attempt detected
        - reason: Human-readable explanation
    """
    if not command:
        return False, ""

    command_lower = command.lower()

    # Check for --no-verify flag
    if "--no-verify" in command_lower:
        return True, "--no-verify flag detected in git command"

    # Check for -n short form (only as standalone flag, not in combined flags)
    # Need to check word boundaries to avoid false positives
    words = command.split()
    for word in words:
        # Check for standalone -n
        if word == "-n":
            return True, "-n (no-verify) flag detected in git command"
        # Check for combined short flags containing 'n'
        if word.startswith("-") and not word.startswith("--") and "n" in word[1:]:
            return True, "-n (no-verify) flag detected in combined flags"

    return False, ""


def is_bypass_allowed() -> bool:
    """Check if git bypass is explicitly allowed.

    Returns:
        True if ALLOW_GIT_BYPASS=true, False otherwise
    """
    allow_bypass = os.getenv("ALLOW_GIT_BYPASS", "false").strip().lower()
    return allow_bypass == "true"


def output_error(message: str) -> None:
    """Output error message to stderr with formatting.

    Args:
        message: Error message to display
    """
    sys.stderr.write("\n")
    sys.stderr.write("=" * 80 + "\n")
    sys.stderr.write("ERROR: Git Hook Enforcement\n")
    sys.stderr.write("=" * 80 + "\n")
    sys.stderr.write(message)
    sys.stderr.write("\n")
    sys.stderr.write("=" * 80 + "\n")
    sys.stderr.write("\n")


def main() -> None:
    """Main entry point for block_git_bypass hook."""
    try:
        # Get git command from sys.argv
        if len(sys.argv) < 2:
            # No command provided - allow (graceful degradation)
            sys.exit(EXIT_SUCCESS)

        # Reconstruct full command from argv
        command = " ".join(sys.argv[1:])

        # Check for bypass attempt
        is_bypass, reason = detect_git_bypass(command)

        if not is_bypass:
            # Normal commit - allow
            sys.exit(EXIT_SUCCESS)

        # Bypass attempt detected
        # Check if bypass is explicitly allowed
        if is_bypass_allowed():
            # Bypass is allowed - allow commit
            sys.exit(EXIT_SUCCESS)

        # Bypass is not allowed - log and block
        agent_name = os.getenv("CLAUDE_AGENT_NAME", "unknown").strip()

        # Log violation (if logger available)
        if _logger_available:
            try:
                logger = WorkflowViolationLogger()
                logger.log_git_bypass_attempt(
                    command=command,
                    agent_name=agent_name,
                    reason=reason,
                )
            except Exception:
                # Don't let logging failure block enforcement
                pass

        # Output helpful error message
        error_message = f"""
Git commit with --no-verify is blocked.

Reason: {reason}

The --no-verify flag bypasses pre-commit hooks, which can skip important
validation checks (tests, linting, security scans).

RECOMMENDED: Use /implement workflow for proper validation

The /implement pipeline ensures:
- Tests pass before committing
- Code is properly formatted
- Security scans are run
- Documentation is updated

HOW TO COMMIT:

1. Use /implement workflow:
   /implement "description of your change"

2. Or remove --no-verify flag:
   git commit -m "your message"

EMERGENCY BYPASS:

If you absolutely must bypass hooks (production emergency):
   ALLOW_GIT_BYPASS=true git commit --no-verify -m "emergency fix"

See docs/WORKFLOW-DISCIPLINE.md for more information.
"""
        output_error(error_message)

        # Block commit
        sys.exit(EXIT_BLOCK)

    except Exception as e:
        # On any error, allow commit (fail open to not block user)
        # This ensures the hook doesn't break git if there's an implementation bug
        sys.stderr.write(f"Warning: Git hook error: {e}\n")
        sys.exit(EXIT_SUCCESS)


if __name__ == "__main__":
    main()
