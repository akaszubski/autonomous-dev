#!/usr/bin/env python3
"""
SubagentStop hook for completion verification with loop-back.

Triggers after doc-master completes to verify all 8 pipeline agents ran.
Creates loop-back checkpoint if agents are missing (for retry).

Hook Type: SubagentStop
Trigger: After doc-master agent completes (last parallel validation agent)
Condition: Verify all 8 agents completed, create loop-back checkpoint if incomplete
Lifecycle: SubagentStop (cannot block - always exits with EXIT_SUCCESS)

Expected 8 agents:
1. researcher-local
2. researcher-web
3. planner
4. test-master
5. implementer
6. reviewer
7. security-auditor
8. doc-master

Features:
- Circuit breaker (opens after 3 consecutive failures)
- Exponential backoff (100ms → 200ms → 400ms → 800ms → 1600ms)
- Max 5 retry attempts
- Graceful degradation (always exit EXIT_SUCCESS)
- Audit logging for all verification attempts

Security:
- Path validation (CWE-22: path traversal)
- Audit logging for all retry attempts
- Always exit EXIT_SUCCESS (non-blocking hook)

Exit Codes:
- EXIT_SUCCESS (0): Always (SubagentStop hooks cannot block)

Date: 2026-01-01
Feature: Completion verification hook with loop-back for incomplete work
Agent: implementer
"""

import json
import logging
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Add lib directory to path for imports
lib_path = Path(__file__).parent.parent / "lib"
if lib_path.exists():
    sys.path.insert(0, str(lib_path))

try:
    from hook_exit_codes import EXIT_SUCCESS
except ImportError:
    # Fallback if module not available
    EXIT_SUCCESS = 0

try:
    from completion_verifier import (
        CompletionVerifier,
        LoopBackState,
        VerificationResult,
        should_retry,
        create_loop_back_checkpoint,
    )
except ImportError as e:
    logger.error(f"Failed to import completion_verifier: {e}")
    # Graceful degradation - exit without blocking
    sys.exit(EXIT_SUCCESS)


# =============================================================================
# Hook Functions
# =============================================================================

def should_trigger_verification(agent_name: str) -> bool:
    """
    Check if hook should trigger verification.

    Only triggers on doc-master completion (last parallel validation agent).

    Args:
        agent_name: Name of completed agent

    Returns:
        True if should trigger, False otherwise
    """
    return agent_name == "doc-master"


def get_session_id_from_context(context: Dict) -> Optional[str]:
    """
    Extract session ID from hook context.

    Args:
        context: Hook context dict

    Returns:
        Session ID or None if not found
    """
    return context.get("session_id")


def verify_and_create_checkpoint(
    session_id: str,
    state_dir: Optional[Path] = None
) -> bool:
    """
    Verify pipeline completion and create checkpoint if incomplete.

    Args:
        session_id: Session identifier
        state_dir: Optional state directory

    Returns:
        True if verification succeeded (regardless of completeness)
    """
    try:
        # Initialize verifier
        verifier = CompletionVerifier(session_id, state_dir=state_dir)

        # Verify pipeline completion
        result = verifier.verify()

        # Log verification result
        log_verification_result(result, session_id)

        # If complete, clear state and exit
        if result.complete:
            verifier.clear_state_on_success()
            logger.info(f"Pipeline complete for session {session_id}")
            return True

        # Get or initialize retry state
        state = verifier.get_retry_state()
        if state is None or not isinstance(state, LoopBackState):
            state = LoopBackState(
                session_id=session_id,
                last_attempt_timestamp=datetime.now().isoformat()
            )

        # Check if should retry
        if not should_retry(state):
            if state.circuit_breaker_open:
                logger.warning(
                    f"Circuit breaker open for session {session_id} - "
                    f"no checkpoint created"
                )
            elif state.attempt_count >= state.max_attempts:
                logger.warning(
                    f"Max attempts ({state.max_attempts}) reached for session "
                    f"{session_id} - no checkpoint created"
                )
            return True

        # Update state on failure
        state.consecutive_failures += 1
        state.attempt_count += 1
        state.last_attempt_timestamp = datetime.now().isoformat()
        state.missing_agents = result.missing_agents

        # Save updated state
        verifier.update_retry_state(state)

        # Create checkpoint for retry
        create_loop_back_checkpoint(
            session_id=session_id,
            missing_agents=result.missing_agents,
            state_dir=state_dir,
            attempt=state.attempt_count
        )

        logger.info(
            f"Created checkpoint for session {session_id} - "
            f"attempt {state.attempt_count}/{state.max_attempts}, "
            f"missing {len(result.missing_agents)} agents"
        )

        return True

    except Exception as e:
        logger.error(f"Verification failed: {e}")
        # Graceful degradation
        return True


def log_verification_result(result: VerificationResult, session_id: str) -> None:
    """
    Log verification result with details.

    Args:
        result: Verification result
        session_id: Session identifier
    """
    if result.complete:
        logger.info(
            f"Verification complete for session {session_id} - "
            f"all 8 agents found ({result.verification_time_ms:.1f}ms)"
        )
    else:
        logger.info(
            f"Verification incomplete for session {session_id} - "
            f"{len(result.missing_agents)} agents missing "
            f"({result.verification_time_ms:.1f}ms)"
        )
        logger.info(f"Missing agents: {', '.join(result.missing_agents)}")


def run_hook(session_id: str, state_dir: Optional[Path] = None) -> int:
    """
    Run hook verification logic.

    Args:
        session_id: Session identifier
        state_dir: Optional state directory

    Returns:
        EXIT_SUCCESS (always - SubagentStop hooks cannot block)
    """
    try:
        verify_and_create_checkpoint(session_id, state_dir=state_dir)
        return EXIT_SUCCESS

    except Exception as e:
        logger.error(f"Hook execution failed: {e}")
        # Always exit EXIT_SUCCESS for graceful degradation
        return EXIT_SUCCESS


def main():
    """Main entry point for hook execution."""
    try:
        # Get agent name from environment
        agent_name = os.environ.get("CLAUDE_AGENT_NAME", "")

        # Only trigger on doc-master completion
        if not should_trigger_verification(agent_name):
            logger.debug(f"Skipping verification for agent: {agent_name}")
            sys.exit(EXIT_SUCCESS)

        # Get session ID from environment
        session_id = os.environ.get("CLAUDE_SESSION_ID", "")
        if not session_id:
            logger.warning("No session ID found in environment")
            sys.exit(EXIT_SUCCESS)

        # Run verification
        exit_code = run_hook(session_id)
        sys.exit(exit_code)

    except Exception as e:
        logger.error(f"Hook failed: {e}")
        # Always exit EXIT_SUCCESS for graceful degradation
        sys.exit(EXIT_SUCCESS)


if __name__ == "__main__":
    main()
