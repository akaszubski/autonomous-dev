#!/usr/bin/env python3
"""
Ralph Loop Manager - Self-correcting agent execution with retry loop pattern.

Manages retry loops for agents with validation strategies, circuit breaker,
and cost tracking to prevent infinite loops.

Features:
1. Iteration tracking (max 5 iterations per session)
2. Circuit breaker (3 consecutive failures → block)
3. Token usage tracking (prevent cost overruns)
4. Thread-safe state operations
5. Atomic state persistence

Retry Decision Logic:
    1. Check max iterations (5 iterations → block)
    2. Check circuit breaker (3 consecutive failures → block)
    3. Check token limit (exceeded → block)
    4. If all checks pass → allow retry

Usage:
    from ralph_loop_manager import (
        RalphLoopManager,
        RalphLoopState,
        MAX_ITERATIONS,
        CIRCUIT_BREAKER_THRESHOLD,
        DEFAULT_TOKEN_LIMIT,
    )

    # Create manager
    manager = RalphLoopManager("session-123", token_limit=50000)

    # Record attempt
    manager.record_attempt(tokens_used=5000)

    # Check if should retry
    if manager.should_retry():
        # Retry agent execution
        pass
    else:
        # Stop (max iterations, circuit breaker, or token limit)
        pass

    # Record success/failure
    if success:
        manager.record_success()
    else:
        manager.record_failure("Error message")

Security:
- Atomic state file writes (temp + rename)
- Thread-safe operations with locks
- Graceful degradation for corrupted state files
- No code execution

Date: 2026-01-02
Issue: #189 (Ralph Loop Pattern for Self-Correcting Agent Execution)
Agent: implementer
Phase: TDD Green (making tests pass)

See error-handling-patterns skill for exception hierarchy and error handling best practices.
See state-management-patterns skill for state persistence patterns.
"""

import json
import os
import sys
import tempfile
import threading
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Optional


# =============================================================================
# Constants
# =============================================================================

# Max iterations per session (5 attempts)
MAX_ITERATIONS = 5

# Circuit breaker threshold (3 consecutive failures)
CIRCUIT_BREAKER_THRESHOLD = 3

# Default token limit (50,000 tokens - reasonable for most loops)
DEFAULT_TOKEN_LIMIT = 50000


# =============================================================================
# Data Classes
# =============================================================================

@dataclass
class RalphLoopState:
    """Persistent state for Ralph Loop pattern."""
    session_id: str
    current_iteration: int = 0
    total_attempts: int = 0
    consecutive_failures: int = 0
    circuit_breaker_open: bool = False
    tokens_used: int = 0
    token_limit: int = DEFAULT_TOKEN_LIMIT
    created_at: str = field(default_factory=lambda: datetime.utcnow().isoformat() + "Z")
    updated_at: str = field(default_factory=lambda: datetime.utcnow().isoformat() + "Z")


# =============================================================================
# Ralph Loop Manager Class
# =============================================================================

class RalphLoopManager:
    """Manage retry loops for self-correcting agent execution."""

    def __init__(
        self,
        session_id: str,
        state_dir: Optional[Path] = None,
        token_limit: int = DEFAULT_TOKEN_LIMIT
    ):
        """
        Initialize Ralph Loop Manager.

        Args:
            session_id: Unique session identifier
            state_dir: Directory for state files (default: ~/.autonomous-dev)
            token_limit: Maximum tokens allowed for session
        """
        self.session_id = session_id
        self.token_limit = token_limit
        self._lock = threading.Lock()

        # Determine state directory
        if state_dir is None:
            home = Path.home()
            state_dir = home / ".autonomous-dev"
            state_dir.mkdir(exist_ok=True)

        self.state_dir = Path(state_dir)
        self.state_file = self.state_dir / f"{session_id}_loop_state.json"

        # Load existing state or initialize fresh
        self._load_or_initialize_state()

    def _load_or_initialize_state(self) -> None:
        """Load existing state from file or initialize fresh state."""
        if self.state_file.exists():
            try:
                data = json.loads(self.state_file.read_text())
                self.current_iteration = data.get("current_iteration", 0)
                self.total_attempts = data.get("total_attempts", 0)
                self.consecutive_failures = data.get("consecutive_failures", 0)
                self.circuit_breaker_open = data.get("circuit_breaker_open", False)
                self.tokens_used = data.get("tokens_used", 0)
                # Use loaded token_limit if available, otherwise use constructor value
                self.token_limit = data.get("token_limit", self.token_limit)
            except (json.JSONDecodeError, KeyError):
                # Corrupted file - start fresh
                self._initialize_fresh_state()
        else:
            self._initialize_fresh_state()

    def _initialize_fresh_state(self) -> None:
        """Initialize fresh state."""
        self.current_iteration = 0
        self.total_attempts = 0
        self.consecutive_failures = 0
        self.circuit_breaker_open = False
        self.tokens_used = 0

    def record_attempt(self, tokens_used: int = 0) -> None:
        """
        Record an attempt in the retry loop.

        Args:
            tokens_used: Number of tokens consumed in this attempt
        """
        with self._lock:
            self.current_iteration += 1
            self.total_attempts += 1
            self.tokens_used += tokens_used

    def record_failure(self, error_message: str) -> None:
        """
        Record a failed attempt.

        Args:
            error_message: Error message from failed attempt
        """
        with self._lock:
            self.consecutive_failures += 1

            # Trip circuit breaker if threshold reached
            if self.consecutive_failures >= CIRCUIT_BREAKER_THRESHOLD:
                self.circuit_breaker_open = True

    def record_success(self) -> None:
        """Record a successful attempt (resets consecutive failures)."""
        with self._lock:
            self.consecutive_failures = 0
            self.circuit_breaker_open = False

    def should_retry(self) -> bool:
        """
        Check if retry should be attempted.

        Returns:
            bool: True if retry allowed, False if blocked

        Blocks retry if:
        - Max iterations reached (5)
        - Circuit breaker open (3 consecutive failures)
        - Token limit exceeded
        """
        with self._lock:
            # Check max iterations
            if self.current_iteration >= MAX_ITERATIONS:
                return False

            # Check circuit breaker
            if self.circuit_breaker_open:
                return False

            # Check token limit
            if self.tokens_used >= self.token_limit:
                return False

            return True

    def is_circuit_breaker_open(self) -> bool:
        """
        Check if circuit breaker is open.

        Returns:
            bool: True if circuit breaker is open
        """
        with self._lock:
            return self.circuit_breaker_open

    def save_state(self) -> None:
        """
        Save state to file atomically.

        Uses atomic write pattern (temp + rename) for safety.
        """
        with self._lock:
            state_data = {
                "session_id": self.session_id,
                "current_iteration": self.current_iteration,
                "total_attempts": self.total_attempts,
                "consecutive_failures": self.consecutive_failures,
                "circuit_breaker_open": self.circuit_breaker_open,
                "tokens_used": self.tokens_used,
                "token_limit": self.token_limit,
                "created_at": getattr(self, 'created_at', datetime.utcnow().isoformat() + "Z"),
                "updated_at": datetime.utcnow().isoformat() + "Z",
            }

            # Atomic write: temp file + rename
            fd, temp_path = tempfile.mkstemp(
                dir=self.state_dir,
                prefix=".loop_state_",
                suffix=".tmp"
            )

            try:
                # Write to temp file
                os.write(fd, json.dumps(state_data, indent=2).encode())
                os.close(fd)

                # Atomic rename
                Path(temp_path).replace(self.state_file)
            except Exception:
                # Cleanup temp file on error
                os.close(fd)
                if Path(temp_path).exists():
                    Path(temp_path).unlink()
                raise

    def load_state(self) -> None:
        """Load state from file (alias for initialization)."""
        self._load_or_initialize_state()


# =============================================================================
# Module-Level Functions (Convenience)
# =============================================================================

def create_manager(
    session_id: str,
    state_dir: Optional[Path] = None,
    token_limit: int = DEFAULT_TOKEN_LIMIT
) -> RalphLoopManager:
    """
    Create RalphLoopManager instance.

    Args:
        session_id: Unique session identifier
        state_dir: Directory for state files
        token_limit: Maximum tokens allowed

    Returns:
        RalphLoopManager: Configured manager instance
    """
    return RalphLoopManager(session_id, state_dir, token_limit)
