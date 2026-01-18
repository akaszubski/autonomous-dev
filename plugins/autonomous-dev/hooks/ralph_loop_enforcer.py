#!/usr/bin/env -S uv run --script --quiet --no-project
# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""
SubagentStop hook: Ralph Loop Pattern enforcer.

Purpose:
Enforce self-correcting agent execution with validation strategies.
Blocks subagent exit if validation fails and retry is allowed.

Problem Solved:
- Agents sometimes exit before task completion
- Manual retry coordination is error-prone
- No automated validation of agent success

Solution:
SubagentStop hook that:
1. Validates agent output using configured strategy
2. Checks if retry allowed (max iterations, circuit breaker, token limit)
3. Blocks exit if validation fails and retry allowed
4. Allows exit if validation passes or retry blocked
5. Provides graceful degradation on errors

Hook Integration:
- Type: SubagentStop
- Trigger: When subagent attempts to exit
- Action: Validate output, allow/deny exit based on validation + retry logic
- Lifecycle: SubagentStop (blocking - can prevent exit)

Exit Codes:
- EXIT_SUCCESS (0): Always - hook never crashes
- Returns JSON response: {"allow": true/false, "message": "..."}

Environment Variables:
- RALPH_LOOP_DISABLED: Set to "true" to disable (default: enabled, opt-out)

Validation Strategies:
- pytest: Run tests and check pass/fail
- safe_word: Search for completion marker in output
- file_existence: Verify expected files exist
- regex: Extract and validate data from output
- json: Extract data via JSONPath

Author: implementer agent
Date: 2026-01-02
Feature: Issue #189 - Ralph Loop Pattern for Self-Correcting Agent Execution
Version: 1.0.0
"""

import json
import os
import sys
from pathlib import Path
from typing import Dict, Any, Optional

# Import exit codes with fallback
def is_running_under_uv() -> bool:
    """Detect if script is running under UV."""
    return "UV_PROJECT_ENVIRONMENT" in os.environ

# Fallback for non-UV environments
if not is_running_under_uv():
    from pathlib import Path
    import sys
    hook_dir = Path(__file__).parent
    lib_path = hook_dir.parent / "lib"
    if lib_path.exists():
        sys.path.insert(0, str(lib_path))

try:
    from hook_exit_codes import EXIT_SUCCESS
except ImportError:
    EXIT_SUCCESS = 0


def is_ralph_loop_enabled() -> bool:
    """
    Check if Ralph Loop is enabled.

    Returns:
        bool: True if enabled (default), False if explicitly disabled

    Environment Variables:
        RALPH_LOOP_DISABLED: Set to "true" to disable (opt-out)
        RALPH_LOOP_ENABLED: Legacy support - "false" disables (backward compat)
    """
    # Check opt-out first (new pattern)
    disabled = os.environ.get("RALPH_LOOP_DISABLED", "").strip().lower()
    if disabled == "true":
        return False

    # Backward compatibility: support RALPH_LOOP_ENABLED="false" to disable
    enabled = os.environ.get("RALPH_LOOP_ENABLED", "").strip().lower()
    if enabled == "false":
        return False

    # Default: enabled
    return True


def allow_exit(message: str = "") -> None:
    """
    Allow subagent to exit.

    Args:
        message: Optional message explaining why exit is allowed
    """
    response = {
        "allow": True,
        "message": message or "Validation passed or retry not allowed"
    }
    print(json.dumps(response))
    sys.exit(EXIT_SUCCESS)


def deny_exit(message: str = "") -> None:
    """
    Deny subagent exit (trigger retry).

    Args:
        message: Optional message explaining why exit is denied
    """
    response = {
        "allow": False,
        "message": message or "Validation failed - retry required"
    }
    print(json.dumps(response))
    sys.exit(EXIT_SUCCESS)


def main() -> None:
    """Main hook entry point."""
    # Check if Ralph Loop is enabled
    if not is_ralph_loop_enabled():
        allow_exit("Ralph Loop disabled")
        return

    # Read hook input
    try:
        hook_input_raw = sys.stdin.read()
        hook_input = json.loads(hook_input_raw)
    except json.JSONDecodeError:
        # Graceful degradation: allow exit on parse error
        allow_exit("Hook input parse error - allowing exit")
        return
    except Exception:
        # Graceful degradation: allow exit on read error
        allow_exit("Hook input read error - allowing exit")
        return

    # Extract fields
    agent_name = hook_input.get("agent_name", "unknown")
    agent_output = hook_input.get("agent_output", "")
    session_id = hook_input.get("session_id", "session-unknown")
    validation_config = hook_input.get("validation_config", {})

    # If no validation config, allow exit (no validation required)
    if not validation_config:
        allow_exit("No validation config - allowing exit")
        return

    # Import libraries (lazy import for graceful degradation)
    try:
        from ralph_loop_manager import RalphLoopManager, MAX_ITERATIONS
        from success_criteria_validator import validate_success
    except ImportError as e:
        # Graceful degradation: allow exit if libraries missing
        allow_exit(f"Ralph Loop libraries not found - allowing exit: {e}")
        return

    # Create or load manager
    try:
        manager = RalphLoopManager(session_id)
    except Exception as e:
        # Graceful degradation: allow exit if manager creation fails
        allow_exit(f"Manager creation failed - allowing exit: {e}")
        return

    # Extract validation strategy
    strategy = validation_config.get("strategy", "safe_word")

    # Validate agent output
    try:
        success, message = validate_success(strategy, agent_output, validation_config)
    except Exception as e:
        # Graceful degradation: allow exit if validation fails
        allow_exit(f"Validation error - allowing exit: {e}")
        return

    # If validation passed, record success and allow exit
    if success:
        manager.record_success()
        manager.save_state()
        allow_exit(f"Validation passed: {message}")
        return

    # Validation failed - check if should retry
    if manager.should_retry():
        # Record failure (increments consecutive failures)
        manager.record_failure(message)
        manager.save_state()

        # Deny exit (trigger retry)
        deny_exit(f"Validation failed, retry allowed: {message}")
    else:
        # Cannot retry (max iterations, circuit breaker, or token limit)
        reason = ""
        if manager.current_iteration >= MAX_ITERATIONS:
            reason = f"Max iterations reached ({MAX_ITERATIONS})"
        elif manager.is_circuit_breaker_open():
            reason = "Circuit breaker open (too many failures)"
        elif manager.tokens_used >= manager.token_limit:
            reason = f"Token limit exceeded ({manager.token_limit})"
        else:
            reason = "Retry not allowed"

        # Allow exit (cannot retry)
        allow_exit(f"Validation failed but retry not allowed: {reason}")


if __name__ == "__main__":
    main()
