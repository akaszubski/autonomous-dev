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
from typing import Optional, List, Dict, Any


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
    retry_history: List[Dict[str, Any]] = field(default_factory=list)  # Issue #256: Track retry attempts

    # Issue #276: Batch checkpoint context
    batch_id: Optional[str] = None
    current_feature_index: int = 0
    completed_features: List[int] = field(default_factory=list)
    failed_features: List[Dict[str, Any]] = field(default_factory=list)
    skipped_features: List[Dict[str, Any]] = field(default_factory=list)
    total_features: int = 0
    features: List[str] = field(default_factory=list)


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
                self.retry_history = data.get("retry_history", [])
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
        self.retry_history = []

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

            # Record in retry history (Issue #256)
            self.retry_history.append({
                "iteration": self.current_iteration,
                "error_message": error_message,
                "timestamp": datetime.utcnow().isoformat() + "Z",
            })

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
                "retry_history": self.retry_history,
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
    # Checkpoint/Resume Methods (Issue #276)
    # =============================================================================

    def checkpoint(
        self,
        batch_state: Optional[Any] = None,
        batch_id: Optional[str] = None
    ) -> Path:
        """
        Create checkpoint for batch processing persistence.

        Saves RALPH loop state + batch context to enable resume after context clear
        or interruption. Uses atomic write pattern for data integrity.

        Args:
            batch_state: Optional BatchState object with batch context
            batch_id: Optional batch ID (for path validation override)

        Returns:
            Path to checkpoint file

        Raises:
            ValueError: If batch_id contains path traversal or absolute path

        Security:
            - Validates batch_id for path traversal (CWE-22)
            - Rejects absolute paths
            - Atomic write (temp + rename)
            - File permissions 0o600

        Example:
            >>> manager = RalphLoopManager("session-123")
            >>> manager.record_attempt(tokens_used=5000)
            >>> checkpoint_file = manager.checkpoint(batch_state=batch_state)
        """
        with self._lock:
            # Validate batch_id if provided (security)
            checkpoint_batch_id = batch_id or (batch_state.batch_id if batch_state else None)
            if checkpoint_batch_id:
                # Reject absolute paths first (more specific error)
                if checkpoint_batch_id.startswith("/") or (len(checkpoint_batch_id) > 1 and checkpoint_batch_id[1] == ":"):
                    raise ValueError(
                        f"Invalid batch_id for checkpoint: absolute path not allowed. "
                        f"batch_id must be a relative identifier."
                    )

                # CWE-22: Prevent path traversal
                if ".." in checkpoint_batch_id or "/" in checkpoint_batch_id or "\\" in checkpoint_batch_id:
                    raise ValueError(
                        f"Invalid batch_id for checkpoint: path traversal detected. "
                        f"batch_id must be a simple identifier without path separators."
                    )

            # Build checkpoint data
            checkpoint_data = {
                "session_id": self.session_id,
                "current_iteration": self.current_iteration,
                "total_attempts": self.total_attempts,
                "consecutive_failures": self.consecutive_failures,
                "circuit_breaker_open": self.circuit_breaker_open,
                "tokens_used": self.tokens_used,
                "token_limit": self.token_limit,
                "retry_history": self.retry_history,
                "created_at": getattr(self, 'created_at', datetime.utcnow().isoformat() + "Z"),
                "updated_at": datetime.utcnow().isoformat() + "Z",
                "checkpoint_created_at": datetime.utcnow().isoformat() + "Z",
            }

            # Add batch context if provided
            if batch_state:
                checkpoint_data["batch_id"] = batch_state.batch_id
                checkpoint_data["current_feature_index"] = batch_state.current_index
                checkpoint_data["completed_features"] = batch_state.completed_features
                checkpoint_data["failed_features"] = batch_state.failed_features
                checkpoint_data["skipped_features"] = batch_state.skipped_features
                checkpoint_data["total_features"] = batch_state.total_features
                checkpoint_data["features"] = batch_state.features

            # Determine checkpoint file path
            checkpoint_file = self.state_dir / f"{self.session_id}_checkpoint.json"

            # Atomic write: temp file + rename
            fd, temp_path = tempfile.mkstemp(
                dir=self.state_dir,
                prefix=".checkpoint_",
                suffix=".tmp"
            )

            try:
                # Write to temp file
                os.write(fd, json.dumps(checkpoint_data, indent=2).encode())
                os.close(fd)

                # Set permissions (owner read/write only)
                temp_path_obj = Path(temp_path)
                if temp_path_obj.exists():
                    temp_path_obj.chmod(0o600)

                # Create backup of existing checkpoint
                if checkpoint_file.exists():
                    backup_file = Path(str(checkpoint_file) + ".bak")
                    checkpoint_file.replace(backup_file)

                # Atomic rename
                temp_path_obj.replace(checkpoint_file)

            except Exception:
                # Cleanup temp file on error
                try:
                    os.close(fd)
                except OSError:
                    pass
                temp_path_obj = Path(temp_path)
                if temp_path_obj.exists():
                    temp_path_obj.unlink()
                raise

            return checkpoint_file

    def checkpoint_after_feature(
        self,
        batch_state: Any,
        feature_index: int,
        success: bool
    ) -> Path:
        """
        Convenience method to checkpoint after feature completion.

        Updates batch state and creates checkpoint in one operation.

        Args:
            batch_state: BatchState object
            feature_index: Index of completed feature
            success: True if feature succeeded, False if failed

        Returns:
            Path to checkpoint file

        Example:
            >>> manager = RalphLoopManager("session-123")
            >>> manager.checkpoint_after_feature(batch_state, 2, success=True)
        """
        with self._lock:
            if success:
                if feature_index not in batch_state.completed_features:
                    batch_state.completed_features.append(feature_index)
            # No need to update failed_features here - that's done elsewhere

            return self.checkpoint(batch_state=batch_state)

    @classmethod
    def resume_batch(
        cls,
        batch_id: str,
        state_dir: Optional[Path] = None
    ) -> "RalphLoopManager":
        """
        Resume batch processing from checkpoint.

        Loads checkpoint and restores RALPH loop state + batch context.

        Args:
            batch_id: Batch identifier
            state_dir: Directory for checkpoint files (default: ~/.autonomous-dev)

        Returns:
            RalphLoopManager with restored state

        Raises:
            FileNotFoundError: If checkpoint not found
            ValueError: If checkpoint corrupted or invalid
            PermissionError: If checkpoint has insecure permissions

        Security:
            - Validates checkpoint file permissions (must be 0o600)
            - Falls back to .bak file if main checkpoint corrupted
            - Validates required fields
            - Warns on version mismatch

        Example:
            >>> manager = RalphLoopManager.resume_batch("batch-123")
            >>> batch_state = manager.get_batch_state()
        """
        # Determine state directory
        if state_dir is None:
            home = Path.home()
            state_dir = home / ".autonomous-dev"

        state_dir = Path(state_dir)

        # Determine checkpoint file path
        session_id = f"ralph-{batch_id}"
        checkpoint_file = state_dir / f"{session_id}_checkpoint.json"

        # Check if checkpoint exists
        if not checkpoint_file.exists():
            raise FileNotFoundError(
                f"Checkpoint not found for batch: {batch_id}\n"
                f"Expected: {checkpoint_file}\n"
                f"Use list_checkpoints() to see available checkpoints."
            )

        # Validate file permissions (security)
        file_mode = checkpoint_file.stat().st_mode & 0o777
        if file_mode != 0o600:
            raise PermissionError(
                f"Checkpoint file has insecure permissions: {oct(file_mode)}\n"
                f"Expected: 0o600 (owner read/write only)\n"
                f"File: {checkpoint_file}"
            )

        # Load checkpoint with corruption recovery
        checkpoint_data = None
        try:
            checkpoint_data = json.loads(checkpoint_file.read_text())
        except json.JSONDecodeError:
            # Try backup file
            backup_file = Path(str(checkpoint_file) + ".bak")
            if backup_file.exists():
                try:
                    checkpoint_data = json.loads(backup_file.read_text())
                except json.JSONDecodeError:
                    raise ValueError(
                        f"Both checkpoint and backup are corrupted for batch: {batch_id}\n"
                        f"Checkpoint: {checkpoint_file}\n"
                        f"Backup: {backup_file}"
                    )
            else:
                raise ValueError(
                    f"Checkpoint corrupted and no backup found for batch: {batch_id}\n"
                    f"Checkpoint: {checkpoint_file}"
                )

        # Validate required fields (session_id is minimum requirement)
        if "session_id" not in checkpoint_data:
            raise ValueError(
                f"Checkpoint missing session_id field\n"
                f"Checkpoint: {checkpoint_file}"
            )

        # Warn on version mismatch
        if "checkpoint_version" in checkpoint_data:
            checkpoint_version = checkpoint_data["checkpoint_version"]
            if checkpoint_version != "1.0.0":
                import warnings
                warnings.warn(
                    f"checkpoint version mismatch: {checkpoint_version} (current: 1.0.0). "
                    f"Resume may fail if schema changed.",
                    UserWarning
                )

        # Create manager and restore state
        manager = cls(session_id, state_dir=state_dir)
        manager.current_iteration = checkpoint_data.get("current_iteration", 0)
        manager.total_attempts = checkpoint_data.get("total_attempts", 0)
        manager.consecutive_failures = checkpoint_data.get("consecutive_failures", 0)
        manager.circuit_breaker_open = checkpoint_data.get("circuit_breaker_open", False)
        manager.tokens_used = checkpoint_data.get("tokens_used", 0)
        manager.token_limit = checkpoint_data.get("token_limit", DEFAULT_TOKEN_LIMIT)
        manager.retry_history = checkpoint_data.get("retry_history", [])
        manager.created_at = checkpoint_data.get("created_at", datetime.utcnow().isoformat() + "Z")

        # Store batch context
        manager._batch_context = {
            "batch_id": checkpoint_data.get("batch_id"),
            "current_feature_index": checkpoint_data.get("current_feature_index", 0),
            "completed_features": checkpoint_data.get("completed_features", []),
            "failed_features": checkpoint_data.get("failed_features", []),
            "skipped_features": checkpoint_data.get("skipped_features", []),
            "total_features": checkpoint_data.get("total_features", 0),
            "features": checkpoint_data.get("features", []),
        }

        return manager

    def get_batch_state(self) -> Any:
        """
        Get batch state from checkpoint context.

        Returns:
            BatchState object reconstructed from checkpoint

        Raises:
            ValueError: If no batch context available

        Example:
            >>> manager = RalphLoopManager.resume_batch("batch-123")
            >>> batch_state = manager.get_batch_state()
        """
        if not hasattr(self, '_batch_context') or not self._batch_context:
            raise ValueError("No batch context available. Use resume_batch() to load checkpoint.")

        # Import BatchState (lazy to avoid circular dependency)
        from batch_state_manager import BatchState

        # Reconstruct BatchState from checkpoint context
        return BatchState(
            batch_id=self._batch_context["batch_id"],
            features_file="",  # Not stored in checkpoint
            total_features=self._batch_context["total_features"],
            features=self._batch_context["features"],
            current_index=self._batch_context["current_feature_index"],
            completed_features=self._batch_context["completed_features"],
            failed_features=self._batch_context["failed_features"],
            skipped_features=self._batch_context.get("skipped_features", []),
        )

    @classmethod
    def list_checkpoints(cls, state_dir: Optional[Path] = None) -> List[str]:
        """
        List all available checkpoint batch IDs.

        Args:
            state_dir: Directory for checkpoint files (default: ~/.autonomous-dev)

        Returns:
            List of batch IDs with checkpoints

        Example:
            >>> checkpoints = RalphLoopManager.list_checkpoints()
            >>> for batch_id in checkpoints:
            ...     print(f"Available: {batch_id}")
        """
        # Determine state directory
        if state_dir is None:
            home = Path.home()
            state_dir = home / ".autonomous-dev"

        state_dir = Path(state_dir)

        if not state_dir.exists():
            return []

        # Find all checkpoint files
        checkpoint_files = state_dir.glob("ralph-*_checkpoint.json")

        # Extract batch IDs
        batch_ids = []
        for checkpoint_file in checkpoint_files:
            # Extract batch ID from filename: ralph-{batch_id}_checkpoint.json
            filename = checkpoint_file.stem  # Remove .json
            if filename.endswith("_checkpoint"):
                session_id = filename[:-len("_checkpoint")]
                if session_id.startswith("ralph-"):
                    batch_id = session_id[len("ralph-"):]
                    batch_ids.append(batch_id)

        return sorted(batch_ids)

    @classmethod
    def rollback_to_checkpoint(
        cls,
        batch_id: str,
        state_dir: Optional[Path] = None
    ) -> "RalphLoopManager":
        """
        Rollback to checkpoint, discarding any state changes after checkpoint.

        This is an alias for resume_batch() with clearer intent for rollback scenarios.

        Args:
            batch_id: Batch identifier
            state_dir: Directory for checkpoint files

        Returns:
            RalphLoopManager with state rolled back to checkpoint

        Raises:
            FileNotFoundError: If checkpoint not found
            ValueError: If checkpoint corrupted

        Example:
            >>> manager = RalphLoopManager.rollback_to_checkpoint("batch-123")
        """
        return cls.resume_batch(batch_id, state_dir=state_dir)

    @classmethod
    def cleanup_old_checkpoints(
        cls,
        state_dir: Optional[Path] = None,
        keep_count: int = 10
    ) -> int:
        """
        Remove old checkpoint files to save space.

        Keeps the N most recent checkpoints, removes older ones.

        Args:
            state_dir: Directory for checkpoint files (default: ~/.autonomous-dev)
            keep_count: Number of recent checkpoints to keep (default: 10)

        Returns:
            Number of checkpoints removed

        Example:
            >>> removed = RalphLoopManager.cleanup_old_checkpoints(keep_count=5)
            >>> print(f"Removed {removed} old checkpoints")
        """
        # Determine state directory
        if state_dir is None:
            home = Path.home()
            state_dir = home / ".autonomous-dev"

        state_dir = Path(state_dir)

        if not state_dir.exists():
            return 0

        # Find all checkpoint files with their modification times
        checkpoint_files = []
        for checkpoint_file in state_dir.glob("ralph-*_checkpoint.json"):
            mtime = checkpoint_file.stat().st_mtime
            checkpoint_files.append((mtime, checkpoint_file))

        # Sort by modification time (newest first)
        checkpoint_files.sort(reverse=True)

        # Remove old checkpoints
        removed_count = 0
        for _, checkpoint_file in checkpoint_files[keep_count:]:
            try:
                checkpoint_file.unlink()
                # Also remove backup if it exists
                backup_file = Path(str(checkpoint_file) + ".bak")
                if backup_file.exists():
                    backup_file.unlink()
                removed_count += 1
            except OSError:
                # Ignore errors during cleanup
                pass

        return removed_count


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
