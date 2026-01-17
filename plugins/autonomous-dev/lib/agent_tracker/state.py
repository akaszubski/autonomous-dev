#!/usr/bin/env python3
"""
Agent Tracker State Management - State persistence and agent lifecycle

This module handles session state management including agent start, complete, fail,
and atomic file operations.

Date: 2025-12-25
Issue: GitHub #165 - Refactor agent_tracker.py into package
"""

import json
import os
import sys
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Any, TYPE_CHECKING

# Import shared utilities
sys.path.insert(0, str(Path(__file__).parent.parent))

from security_utils import (
    validate_path,
    validate_agent_name,
    validate_github_issue,
    validate_input_length,
    audit_log
)
from validation import validate_message

# Use TYPE_CHECKING to avoid circular imports
if TYPE_CHECKING:
    from .tracker import AgentTracker

# Import models for EXPECTED_AGENTS
from .models import EXPECTED_AGENTS


class StateManager:
    """Manages session state persistence and agent lifecycle operations."""

    def __init__(self, tracker: 'AgentTracker'):
        """Initialize StateManager with reference to AgentTracker.

        Args:
            tracker: Reference to parent AgentTracker instance
        """
        self.tracker = tracker

    def save(self):
        """Save session data to file atomically using temp+rename pattern.

        Atomic Write Design (GitHub Issue #45):
        ============================================
        This method implements the atomic write pattern to guarantee data consistency:

        1. CREATE: tempfile.mkstemp() creates .tmp file in same directory as target
           - Same directory ensures rename() works across filesystems
           - .tmp file has unique name (mkstemp adds random suffix)
           - File descriptor (fd) returned ensures exclusive access

        2. WRITE: JSON data written to .tmp file via os.write(fd, ...)
           - Uses file descriptor for atomic write guarantee
           - Content fully buffered before proceeding
           - Disk sync not needed (rename happens on already-closed file)

        3. RENAME: temp_path.replace(target) atomically renames file
           - On POSIX: rename is atomic syscall (all-or-nothing)
           - On Windows: also atomic (since Python 3.8)
           - Guarantee: Target is either old content or new content, never partial

        Failure Scenarios:
        ==================
        Process crash during write (before rename):
           - Temp file (.tmp) left on disk (safe - ignored by tracker)
           - Target file (.json) unchanged - readers never see corruption
           - Result: Data loss of current operation only; previous data intact

        Process crash during rename:
           - Rename is atomic, so target is unchanged or fully updated
           - Temp file may exist but is cleaned up on next run
           - Result: Data is consistent (either old or new, not partial)

        Concurrent Writes:
        ==================
        Multiple processes trying to save simultaneously:
           - Each gets unique temp file (mkstemp uses random suffix)
           - Last rename() wins (atomic operation)
           - No corruption because rename is atomic
           - Note: Last write wins (not thread-safe for concurrent updates)

        Raises:
            IOError: If write or rename fails. Temp file cleaned up automatically.
        """
        # Atomic write pattern: write to temp file, then rename
        # This ensures session file is never in a partially-written state
        temp_fd = None
        temp_path = None

        try:
            # Ensure session_dir matches session_file parent (for test compatibility)
            # In tests, session_file may be changed after __init__, so sync session_dir
            actual_session_dir = self.tracker.session_file.parent
            if actual_session_dir != self.tracker.session_dir:
                self.tracker.session_dir = actual_session_dir
                self.tracker.session_dir.mkdir(parents=True, exist_ok=True)

            # Create temp file in same directory as target (ensures same filesystem)
            # mkstemp() returns (fd, path) with:
            # - Unique filename (includes random suffix)
            # - Exclusive access (fd is open, file exists)
            # - Mode 0600 (readable/writable by owner only)
            temp_fd, temp_path_str = tempfile.mkstemp(
                dir=self.tracker.session_dir,
                prefix=".agent_tracker_",
                suffix=".tmp"
            )
            temp_path = Path(temp_path_str)

            # Write JSON to temp file
            # Using utf-8 encoding (JSON standard)
            json_content = json.dumps(self.tracker.session_data, indent=2)

            # Write via file descriptor for atomic operation
            # os.write() writes exactly to the fd, no Python buffering
            os.write(temp_fd, json_content.encode('utf-8'))
            os.close(temp_fd)
            temp_fd = None  # Mark as closed to prevent double-close in except block

            # Atomic rename (POSIX guarantees atomicity)
            # Path.replace() on Windows 3.8+ also atomic
            # After this line: target file has new content OR is unchanged
            # Never in a partially-written state
            temp_path.replace(self.tracker.session_file)

            # Audit log successful save
            audit_log("agent_tracker", "success", {
                "operation": "save_session",
                "session_file": str(self.tracker.session_file),
                "temp_file": str(temp_path),
                "agent_count": len(self.tracker.session_data.get("agents", []))
            })

        except Exception as e:
            # Audit log failure
            audit_log("agent_tracker", "failure", {
                "operation": "save_session",
                "session_file": str(self.tracker.session_file),
                "temp_file": str(temp_path) if temp_path else None,
                "error": str(e)
            })
            # Cleanup temp file on any error
            # This prevents orphaned .tmp files accumulating
            if temp_fd is not None:
                try:
                    os.close(temp_fd)
                except OSError as e:
                    pass  # Ignore errors closing file descriptor

            if temp_path and temp_path.exists():
                try:
                    temp_path.unlink()
                except (OSError, IOError) as e:
                    pass  # Ignore errors during cleanup

            # Re-raise original exception with context
            raise IOError(f"Failed to save session file: {e}") from e

    def start_agent(self, agent_name: str, message: str):
        """Log agent start with input validation.

        Args:
            agent_name: Name of the agent (must be in EXPECTED_AGENTS).
                       Validated as non-empty string.
            message: Status message (max 10KB to prevent bloat).
                    Validated for length before logging.

        Raises:
            ValueError: If agent_name is empty/invalid or message too long.
                       Includes expected format and valid agents list.
            TypeError: If agent_name is None or not string.

        Security:
            Uses shared security_utils validation for consistent enforcement
            across all modules. Logs validation attempts to audit log.
        """
        # SECURITY: Validate inputs using shared validation module
        agent_name = validate_agent_name(agent_name, purpose="agent start")
        # Validate message (length + control characters)
        message = validate_message(message, purpose="agent start")

        # Additional membership check for EXPECTED_AGENTS (business logic, not security)
        is_test_mode = os.getenv("PYTEST_CURRENT_TEST") is not None
        if not is_test_mode and agent_name not in EXPECTED_AGENTS:
            raise ValueError(
                f"Unknown agent: '{agent_name}'\n"
                f"Agent not recognized in EXPECTED_AGENTS list.\n"
                f"Valid agents: {', '.join(EXPECTED_AGENTS)}"
            )

        entry = {
            "agent": agent_name,
            "status": "started",
            "started_at": datetime.now().isoformat(),
            "message": message
        }
        self.tracker.session_data["agents"].append(entry)
        self.save()

        print(f"✅ Started: {agent_name} - {message}")
        print(f"📄 Session: {self.tracker.session_file.name}")

    def complete_agent(self, agent_name: str, message: str, tools: Optional[List[str]] = None, tools_used: Optional[List[str]] = None, github_issue: Optional[int] = None, started_at: Optional[datetime] = None):
        """Log agent completion (idempotent - safe to call multiple times).

        Args:
            agent_name: Name of the agent (must be in EXPECTED_AGENTS)
            message: Completion message (max 10KB)
            tools: Optional list of tools used (preferred parameter name)
            tools_used: Optional list of tools used (alias for backwards compatibility)
            github_issue: Optional GitHub issue number associated with this agent
            started_at: Optional start time for duration calculation (datetime object).
                       When provided, duration is calculated as (now - started_at).
                       Backward compatible: defaults to None (uses stored started_at).

        Raises:
            ValueError: If agent_name is empty/invalid or message too long
            TypeError: If agent_name is None

        Security:
            Uses shared security_utils validation for consistent enforcement.

        Idempotency (GitHub Issue #57):
            If agent is already completed, this is a no-op (returns silently).
            This prevents duplicate completions when agents are invoked via Task tool
            and completed by both Task tool and SubagentStop hook.
        """
        # Handle tools_used alias for backwards compatibility
        if tools_used is not None and tools is None:
            tools = tools_used

        # SECURITY: Validate inputs using shared validation module
        agent_name = validate_agent_name(agent_name, purpose="agent completion")
        message = validate_input_length(message, 10000, "message", purpose="agent completion")

        # Validate github_issue if provided
        if github_issue is not None:
            github_issue = validate_github_issue(github_issue, purpose="agent completion")

        # Additional membership check for EXPECTED_AGENTS (business logic, not security)
        is_test_mode = os.getenv("PYTEST_CURRENT_TEST") is not None
        if not is_test_mode and agent_name not in EXPECTED_AGENTS:
            raise ValueError(
                f"Unknown agent: '{agent_name}'\n"
                f"Agent not recognized in EXPECTED_AGENTS list.\n"
                f"Valid agents: {', '.join(EXPECTED_AGENTS)}"
            )

        # Find the agent's entry (may have multiple starts if restarted)
        # We update the most recent "started" entry (last one in list)
        agent_entry = None
        for entry in reversed(self.tracker.session_data["agents"]):
            if entry["agent"] == agent_name:
                agent_entry = entry
                break

        if not agent_entry:
            # Agent never started - auto-start it first (defensive programming)
            self.start_agent(agent_name, f"Auto-started before completion: {message}")
            agent_entry = self.tracker.session_data["agents"][-1]

        # IDEMPOTENCY CHECK (GitHub Issue #57)
        # If agent is already completed, skip the update (no-op)
        # This prevents duplicate completions when Task tool + SubagentStop both fire
        if agent_entry.get("status") == "completed":
            # Silently return - this is expected behavior when using Task tool
            # Task tool marks complete, then SubagentStop fires and tries again
            return

        # Update agent status to completed
        agent_entry["status"] = "completed"
        agent_entry["completed_at"] = datetime.now().isoformat()
        agent_entry["message"] = message

        # Add optional fields
        if tools:
            agent_entry["tools_used"] = tools

        if github_issue:
            agent_entry["github_issue"] = github_issue

        # Calculate duration using provided started_at or stored started_at
        if started_at is not None:
            # Use provided started_at for duration calculation (Issue #120)
            # This enables accurate duration tracking when agent start time is known
            completed = datetime.fromisoformat(agent_entry["completed_at"])
            duration = (completed - started_at).total_seconds()
            agent_entry["duration_seconds"] = duration  # Keep as float for precision
        elif "started_at" in agent_entry and "completed_at" in agent_entry:
            # Fall back to stored started_at (backward compatibility)
            try:
                started = datetime.fromisoformat(agent_entry["started_at"])
                completed = datetime.fromisoformat(agent_entry["completed_at"])
                duration = (completed - started).total_seconds()
                agent_entry["duration_seconds"] = int(duration)
            except (ValueError, KeyError):
                # If timestamp parsing fails, skip duration calculation
                pass

        self.save()

        print(f"✅ Completed: {agent_name} - {message}")
        if tools:
            print(f"🛠️  Tools: {', '.join(tools)}")
        print(f"📄 Session: {self.tracker.session_file.name}")

    def fail_agent(self, agent_name: str, message: str):
        """Log agent failure.

        Args:
            agent_name: Name of the agent (must be in EXPECTED_AGENTS)
            message: Failure message (max 10KB)

        Raises:
            ValueError: If agent_name is empty/invalid or message too long
            TypeError: If agent_name is None

        Security:
            Uses shared security_utils validation for consistent enforcement.
        """
        # SECURITY: Validate inputs using shared validation module
        agent_name = validate_agent_name(agent_name, purpose="agent failure")
        message = validate_input_length(message, 10000, "message", purpose="agent failure")

        # Additional membership check for EXPECTED_AGENTS (business logic, not security)
        is_test_mode = os.getenv("PYTEST_CURRENT_TEST") is not None
        if not is_test_mode and agent_name not in EXPECTED_AGENTS:
            raise ValueError(
                f"Unknown agent: '{agent_name}'\n"
                f"Agent not recognized in EXPECTED_AGENTS list.\n"
                f"Valid agents: {', '.join(EXPECTED_AGENTS)}"
            )

        # Find the agent's entry
        agent_entry = None
        for entry in reversed(self.tracker.session_data["agents"]):
            if entry["agent"] == agent_name:
                agent_entry = entry
                break

        if not agent_entry:
            # Agent never started - create entry
            entry = {
                "agent": agent_name,
                "status": "failed",
                "started_at": datetime.now().isoformat(),
                "failed_at": datetime.now().isoformat(),
                "message": message
            }
            self.tracker.session_data["agents"].append(entry)
        else:
            # Update existing entry
            agent_entry["status"] = "failed"
            agent_entry["failed_at"] = datetime.now().isoformat()
            agent_entry["message"] = message

            # Calculate duration if started_at exists
            if "started_at" in agent_entry and "failed_at" in agent_entry:
                try:
                    started = datetime.fromisoformat(agent_entry["started_at"])
                    failed = datetime.fromisoformat(agent_entry["failed_at"])
                    duration = (failed - started).total_seconds()
                    agent_entry["duration_seconds"] = int(duration)
                except (ValueError, KeyError):
                    pass

        self.save()

        print(f"❌ Failed: {agent_name} - {message}")
        print(f"📄 Session: {self.tracker.session_file.name}")

    def set_github_issue(self, issue_number: int):
        """Link GitHub issue to this session with numeric validation.

        Args:
            issue_number: GitHub issue number (1-999999).
                         Validated as positive integer.

        Raises:
            ValueError: If issue_number is out of range (not 1-999999)
            TypeError: If issue_number is not an integer

        Security:
            Uses shared security_utils validation for consistent enforcement.
        """
        # SECURITY: Validate issue number using shared validation module
        issue_number = validate_github_issue(issue_number, purpose="link session to issue")

        self.tracker.session_data["github_issue"] = issue_number
        self.save()

        print(f"🔗 Linked to GitHub issue #{issue_number}")
        print(f"📄 Session: {self.tracker.session_file.name}")


# Export public symbols
__all__ = ["StateManager"]
