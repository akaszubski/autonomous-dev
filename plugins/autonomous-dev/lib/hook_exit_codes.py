#!/usr/bin/env python3
"""
Hook Exit Codes - Standardized exit code constants for all hooks.

This module defines standardized exit codes used across all hooks to ensure
consistent behavior and clear semantics throughout the hook system.

Exit Code Semantics:
    EXIT_SUCCESS (0): Operation succeeded, workflow continues normally
    EXIT_WARNING (1): Non-critical issue detected, workflow continues with warning
    EXIT_BLOCK (2): Critical issue detected, block workflow immediately

Lifecycle Constraints:
    Different hook lifecycles have different exit code restrictions:

    - PreToolUse hooks: MUST always exit 0 (cannot block tool execution)
      Example: unified_pre_tool.py, mcp_security_enforcer.py
      Rationale: Tool execution has already been approved by user

    - SubagentStop hooks: MUST always exit 0 (cannot block agent completion)
      Example: auto_git_workflow.py, log_agent_workflow.py
      Rationale: Agent has already completed, work is done

    - PreSubagent hooks: CAN exit 2 to block agent spawn
      Example: auto_tdd_enforcer.py, enforce_bloat_prevention.py
      Rationale: Agent hasn't spawned yet, can prevent invalid work

Usage:
    from hook_exit_codes import EXIT_SUCCESS, EXIT_WARNING, EXIT_BLOCK

    # Success case
    if all_checks_pass:
        sys.exit(EXIT_SUCCESS)

    # Warning case (non-critical)
    if minor_issue_detected:
        print("Warning: Minor issue detected")
        sys.exit(EXIT_WARNING)

    # Block case (critical issue)
    if critical_issue_detected:
        print("Error: Critical issue detected")
        sys.exit(EXIT_BLOCK)

    # Lifecycle constraint check
    from hook_exit_codes import LIFECYCLE_CONSTRAINTS

    if not LIFECYCLE_CONSTRAINTS["PreToolUse"]["can_block"]:
        # PreToolUse hooks cannot block, only warn
        sys.exit(EXIT_WARNING)

Benefits of Symbolic Constants:
    1. Semantic clarity: EXIT_BLOCK is clearer than sys.exit(2)
    2. Self-documenting: Code explains intent, not just mechanism
    3. Prevents inversion bugs: Harder to accidentally swap exit codes
    4. Centralized definition: Single source of truth for all hooks
    5. Type safety: Import errors caught early vs runtime bugs

Date: 2026-01-01
Feature: Standardized exit codes across all hooks
Issue: GitHub TBD
Agent: implementer
Phase: Implementation (TDD Green)

Design Patterns:
    See library-design-patterns skill for standardized design patterns.
"""

from typing import Dict, List, Any


# =============================================================================
# Exit Code Constants
# =============================================================================

EXIT_SUCCESS = 0  # Operation succeeded, continue workflow
EXIT_WARNING = 1  # Non-critical issue, continue with warning
EXIT_BLOCK = 2    # Critical issue, block workflow


# =============================================================================
# Lifecycle Constraints
# =============================================================================

LIFECYCLE_CONSTRAINTS: Dict[str, Dict[str, Any]] = {
    "PreToolUse": {
        "allowed_exits": [EXIT_SUCCESS],
        "can_block": False,
        "description": (
            "PreToolUse hooks run before tool execution. They MUST always exit 0 "
            "because the tool execution has already been approved by the user. "
            "These hooks can only log warnings but cannot block workflow. "
            "Examples: unified_pre_tool.py, mcp_security_enforcer.py"
        )
    },
    "SubagentStop": {
        "allowed_exits": [EXIT_SUCCESS],
        "can_block": False,
        "description": (
            "SubagentStop hooks run after agent completes. They MUST always exit 0 "
            "because the agent has already finished its work. These hooks perform "
            "post-processing tasks (git automation, logging) but cannot block. "
            "Examples: auto_git_workflow.py, log_agent_workflow.py, verify_completion.py"
        )
    },
    "PreSubagent": {
        "allowed_exits": [EXIT_SUCCESS, EXIT_WARNING, EXIT_BLOCK],
        "can_block": True,
        "description": (
            "PreSubagent hooks run before agent spawn. They CAN exit 2 to block "
            "agent spawn if critical issues are detected (missing tests, bloat risks). "
            "These hooks enforce quality gates before work begins. "
            "Examples: auto_tdd_enforcer.py, enforce_bloat_prevention.py"
        )
    }
}


# =============================================================================
# Helper Functions (Optional - for advanced usage)
# =============================================================================

def can_lifecycle_block(lifecycle: str) -> bool:
    """
    Check if a given lifecycle can block workflow.

    Args:
        lifecycle: Hook lifecycle name (PreToolUse, SubagentStop, PreSubagent)

    Returns:
        True if lifecycle can exit with EXIT_BLOCK, False otherwise

    Raises:
        KeyError: If lifecycle is not defined in LIFECYCLE_CONSTRAINTS

    Examples:
        >>> can_lifecycle_block("PreToolUse")
        False
        >>> can_lifecycle_block("PreSubagent")
        True
    """
    return LIFECYCLE_CONSTRAINTS[lifecycle]["can_block"]


def is_exit_allowed(lifecycle: str, exit_code: int) -> bool:
    """
    Check if an exit code is allowed for a given lifecycle.

    Args:
        lifecycle: Hook lifecycle name (PreToolUse, SubagentStop, PreSubagent)
        exit_code: Exit code to check (0, 1, or 2)

    Returns:
        True if exit code is allowed for lifecycle, False otherwise

    Raises:
        KeyError: If lifecycle is not defined in LIFECYCLE_CONSTRAINTS

    Examples:
        >>> is_exit_allowed("PreToolUse", EXIT_BLOCK)
        False
        >>> is_exit_allowed("PreSubagent", EXIT_BLOCK)
        True
    """
    return exit_code in LIFECYCLE_CONSTRAINTS[lifecycle]["allowed_exits"]


def get_lifecycle_description(lifecycle: str) -> str:
    """
    Get description of lifecycle constraints.

    Args:
        lifecycle: Hook lifecycle name (PreToolUse, SubagentStop, PreSubagent)

    Returns:
        Description string explaining lifecycle constraints

    Raises:
        KeyError: If lifecycle is not defined in LIFECYCLE_CONSTRAINTS

    Examples:
        >>> desc = get_lifecycle_description("PreToolUse")
        >>> print(desc)
        PreToolUse hooks run before tool execution...
    """
    return LIFECYCLE_CONSTRAINTS[lifecycle]["description"]


# =============================================================================
# Module Exports
# =============================================================================

__all__ = [
    "EXIT_SUCCESS",
    "EXIT_WARNING",
    "EXIT_BLOCK",
    "LIFECYCLE_CONSTRAINTS",
    "can_lifecycle_block",
    "is_exit_allowed",
    "get_lifecycle_description",
]
