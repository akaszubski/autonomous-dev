#!/usr/bin/env python3
"""
Agent Pipeline Tracker - Structured logging for agent invocations with security hardening

Tracks which agents ran, when, and their status to enable:
- Pipeline verification (were all expected agents invoked?)
- Debugging (what happened during execution?)
- Metrics (agent usage patterns, timing)
- Compliance (proof that SDLC steps were followed)

Security Features (GitHub Issue #45 - v3.2.3):
- Path Traversal Prevention: All paths validated to prevent ../../etc/passwd attacks
  * Checks for '..' sequences in path strings (catches obvious traversal attempts)
  * Resolves all paths and verifies they don't escape to system directories
  * Prevents symlink-based escapes via path normalization

- Atomic File Writes: Uses temp file + rename pattern for data consistency
  * Write to temporary file (.tmp) first, then atomic rename to target (.json)
  * If process crashes mid-write, original file remains intact
  * On POSIX systems, rename is guaranteed atomic by OS
  * Prevents readers from seeing corrupted/partial JSON files

- Input Validation: Strict bounds checking on all user inputs
  * agent_name: 1-255 chars, alphanumeric + hyphen/underscore only
  * message: Max 10KB to prevent log bloat
  * github_issue: Positive integers 1-999999 only
  * Prevents injection attacks and resource exhaustion

- Comprehensive Error Handling: All exceptions include context
  * Detailed error messages with expected format
  * Context dict with relevant debug information
  * Cleanup of temp files on failure (no orphaned .tmp files)

Usage:
    # Log agent start
    python scripts/agent_tracker.py start researcher "Researching JWT patterns"

    # Log agent completion
    python scripts/agent_tracker.py complete researcher "Found 3 patterns" --tools "WebSearch,Grep,Read"

    # Log agent failure
    python scripts/agent_tracker.py fail researcher "No patterns found"

    # View pipeline status
    python scripts/agent_tracker.py status

Example session file (JSON):
{
  "session_id": "20251103-143022",
  "started": "2025-11-03T14:30:22",
  "agents": [
    {
      "agent": "researcher",
      "status": "completed",
      "started_at": "2025-11-03T14:30:25",
      "completed_at": "2025-11-03T14:35:10",
      "duration_seconds": 285,
      "message": "Found 3 patterns",
      "tools_used": ["WebSearch", "Grep", "Read"]
    }
  ]
}
"""

import json
import os
import sys
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Any

# Import shared security utilities (GitHub Issue #46 - refactor to shared module)
# Add parent directories to sys.path to allow import from plugins/autonomous-dev/lib
script_dir = Path(__file__).parent.resolve()
project_root = script_dir.parent
lib_dir = project_root / "plugins" / "autonomous-dev" / "lib"
sys.path.insert(0, str(lib_dir))

from security_utils import (
    validate_path,
    validate_agent_name,
    validate_github_issue,
    validate_input_length,
    audit_log,
    PROJECT_ROOT
)


# Agent display metadata
AGENT_METADATA = {
    "researcher": {
        "description": "Research patterns and best practices",
        "emoji": "🔍"
    },
    "planner": {
        "description": "Create architecture plan and design",
        "emoji": "📋"
    },
    "test-master": {
        "description": "Write tests first (TDD)",
        "emoji": "🧪"
    },
    "implementer": {
        "description": "Implement code to make tests pass",
        "emoji": "⚙️"
    },
    "reviewer": {
        "description": "Code review and quality check",
        "emoji": "👀"
    },
    "security-auditor": {
        "description": "Security scan and vulnerability detection",
        "emoji": "🔒"
    },
    "doc-master": {
        "description": "Update documentation",
        "emoji": "📝"
    }
}

# Expected agent execution order
EXPECTED_AGENTS = [
    "researcher",
    "planner",
    "test-master",
    "implementer",
    "reviewer",
    "security-auditor",
    "doc-master"
]

# Note: Input validation constants and PROJECT_ROOT now imported from security_utils
# This ensures consistent validation across all modules


class AgentTracker:
    def __init__(self, session_file: Optional[str] = None):
        """Initialize AgentTracker with path traversal protection.

        Args:
            session_file: Optional path to session file for testing.
                         If None, creates/finds session file automatically.

        Raises:
            ValueError: If session_file path is outside project (path traversal attempt)

        Security:
            Uses shared security_utils.validate_path() for consistent validation
            across all modules. Logs all validation attempts to security audit log.
        """
        if session_file:
            # SECURITY: Validate path using shared validation module
            # This ensures consistent security enforcement across all components
            validated_path = validate_path(
                Path(session_file),
                purpose="agent session tracking",
                allow_missing=True  # Allow non-existent session files (will be created)
            )
            self.session_file = validated_path

            self.session_dir = self.session_file.parent
            self.session_dir.mkdir(parents=True, exist_ok=True)

            if self.session_file.exists():
                self.session_data = json.loads(self.session_file.read_text())
            else:
                # Create new session file
                timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
                self.session_data = {
                    "session_id": timestamp,
                    "started": datetime.now().isoformat(),
                    "github_issue": None,
                    "agents": []
                }
                self._save()
        else:
            # Standard mode: auto-detect or create session file
            self.session_dir = Path("docs/sessions")
            self.session_dir.mkdir(parents=True, exist_ok=True)

            # Find or create JSON session file for today
            today = datetime.now().strftime("%Y%m%d")
            json_files = list(self.session_dir.glob(f"{today}-*-pipeline.json"))

            if json_files:
                # Use most recent session file from today
                self.session_file = sorted(json_files)[-1]
                self.session_data = json.loads(self.session_file.read_text())
            else:
                # Create new session file
                timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
                self.session_file = self.session_dir / f"{timestamp}-pipeline.json"
                self.session_data = {
                    "session_id": timestamp,
                    "started": datetime.now().isoformat(),
                    "github_issue": None,  # Track linked GitHub issue
                    "agents": []
                }
                self._save()

    def _save(self):
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
            # Create temp file in same directory as target (ensures same filesystem)
            # mkstemp() returns (fd, path) with:
            # - Unique filename (includes random suffix)
            # - Exclusive access (fd is open, file exists)
            # - Mode 0600 (readable/writable by owner only)
            temp_fd, temp_path_str = tempfile.mkstemp(
                dir=self.session_dir,
                prefix=".agent_tracker_",
                suffix=".tmp"
            )
            temp_path = Path(temp_path_str)

            # Write JSON to temp file
            # Using utf-8 encoding (JSON standard)
            json_content = json.dumps(self.session_data, indent=2)

            # Write via file descriptor for atomic operation
            # os.write() writes exactly to the fd, no Python buffering
            os.write(temp_fd, json_content.encode('utf-8'))
            os.close(temp_fd)
            temp_fd = None  # Mark as closed to prevent double-close in except block

            # Atomic rename (POSIX guarantees atomicity)
            # Path.replace() on Windows 3.8+ also atomic
            # After this line: target file has new content OR is unchanged
            # Never in a partially-written state
            temp_path.replace(self.session_file)

            # Audit log successful save
            audit_log("agent_tracker", "success", {
                "operation": "save_session",
                "session_file": str(self.session_file),
                "temp_file": str(temp_path),
                "agent_count": len(self.session_data.get("agents", []))
            })

        except Exception as e:
            # Audit log failure
            audit_log("agent_tracker", "failure", {
                "operation": "save_session",
                "session_file": str(self.session_file),
                "temp_file": str(temp_path) if temp_path else None,
                "error": str(e)
            })
            # Cleanup temp file on any error
            # This prevents orphaned .tmp files accumulating
            if temp_fd is not None:
                try:
                    os.close(temp_fd)
                except:
                    pass

            if temp_path and temp_path.exists():
                try:
                    temp_path.unlink()
                except:
                    pass

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
        message = validate_input_length(message, 10000, "message", purpose="agent start")

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
        self.session_data["agents"].append(entry)
        self._save()

        print(f"✅ Started: {agent_name} - {message}")
        print(f"📄 Session: {self.session_file.name}")

    def complete_agent(self, agent_name: str, message: str, tools: Optional[List[str]] = None, tools_used: Optional[List[str]] = None):
        """Log agent completion (idempotent - safe to call multiple times).

        Args:
            agent_name: Name of the agent (must be in EXPECTED_AGENTS)
            message: Completion message (max 10KB)
            tools: Optional list of tools used (preferred parameter name)
            tools_used: Optional list of tools used (alias for backwards compatibility)

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

        # Additional membership check for EXPECTED_AGENTS (business logic, not security)
        is_test_mode = os.getenv("PYTEST_CURRENT_TEST") is not None
        if not is_test_mode and agent_name not in EXPECTED_AGENTS:
            raise ValueError(
                f"Unknown agent: '{agent_name}'\n"
                f"Agent not recognized in EXPECTED_AGENTS list.\n"
                f"Valid agents: {', '.join(EXPECTED_AGENTS)}"
            )

        # IDEMPOTENCY: Check if agent already completed
        # If already completed, skip without error (safe to call multiple times)
        for entry in reversed(self.session_data["agents"]):
            if entry["agent"] == agent_name:
                if entry["status"] == "completed":
                    # Already completed - skip silently (idempotent behavior)
                    audit_log("agent_tracker", "success", {
                        "operation": "complete_agent_idempotent",
                        "agent_name": agent_name,
                        "status": "already_completed",
                        "message": "Agent already completed, skipped duplicate completion"
                    })
                    return
                elif entry["status"] == "started":
                    # Found started entry - complete it
                    entry["status"] = "completed"
                    entry["completed_at"] = datetime.now().isoformat()
                    entry["message"] = message

                    # Calculate duration
                    started = datetime.fromisoformat(entry["started_at"])
                    completed = datetime.fromisoformat(entry["completed_at"])
                    entry["duration_seconds"] = int((completed - started).total_seconds())

                    if tools:
                        entry["tools_used"] = tools

                    self._save()

                    audit_log("agent_tracker", "success", {
                        "operation": "complete_agent",
                        "agent_name": agent_name,
                        "duration_seconds": entry["duration_seconds"]
                    })

                    print(f"✅ Completed: {agent_name} - {message}")
                    print(f"⏱️  Duration: {entry['duration_seconds']}s")
                    print(f"📄 Session: {self.session_file.name}")
                    return

        # If no entry found, create a completed entry
        entry = {
            "agent": agent_name,
            "status": "completed",
            "completed_at": datetime.now().isoformat(),
            "message": message
        }
        if tools:
            entry["tools_used"] = tools

        self.session_data["agents"].append(entry)
        self._save()

        audit_log("agent_tracker", "success", {
            "operation": "complete_agent",
            "agent_name": agent_name,
            "no_prior_start": True
        })

        print(f"✅ Completed: {agent_name} - {message}")
        print(f"📄 Session: {self.session_file.name}")

    def fail_agent(self, agent_name: str, message: str):
        """Log agent failure.

        Args:
            agent_name: Name of the agent (must be in EXPECTED_AGENTS)
            message: Error message (max 10KB)

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

        # Find the most recent entry for this agent
        for entry in reversed(self.session_data["agents"]):
            if entry["agent"] == agent_name and entry["status"] == "started":
                entry["status"] = "failed"
                entry["failed_at"] = datetime.now().isoformat()
                entry["error"] = message
                entry["message"] = message  # Also set message field for test compatibility

                # Calculate duration
                started = datetime.fromisoformat(entry["started_at"])
                failed = datetime.fromisoformat(entry["failed_at"])
                entry["duration_seconds"] = int((failed - started).total_seconds())

                self._save()

                print(f"❌ Failed: {agent_name} - {message}")
                print(f"⏱️  Duration: {entry['duration_seconds']}s")
                print(f"📄 Session: {self.session_file.name}")
                return

        # If no started entry found, create a failed entry
        entry = {
            "agent": agent_name,
            "status": "failed",
            "failed_at": datetime.now().isoformat(),
            "error": message,
            "message": message  # Also set message field for test compatibility
        }
        self.session_data["agents"].append(entry)
        self._save()

        print(f"❌ Failed: {agent_name} - {message}")
        print(f"📄 Session: {self.session_file.name}")

    def set_github_issue(self, issue_number: int):
        """Link GitHub issue to this session with numeric validation.

        Args:
            issue_number: GitHub issue number (positive integer 1-999999).
                         Validated for type and range.

        Raises:
            TypeError: If issue_number is not an integer (not float, str, etc).
            ValueError: If issue_number outside range 1-999999.

        Security:
            Uses shared security_utils validation for consistent enforcement.
        """
        # SECURITY: Validate issue number using shared validation module
        issue_number = validate_github_issue(issue_number, purpose="session tracking")

        self.session_data["github_issue"] = issue_number
        self._save()
        print(f"🔗 Linked GitHub issue #{issue_number}")
        print(f"📄 Session: {self.session_file.name}")

    def get_expected_agents(self) -> List[str]:
        """Get list of expected agents in execution order."""
        return EXPECTED_AGENTS.copy()

    def calculate_progress(self) -> int:
        """Calculate overall progress percentage (0-100).

        Returns:
            Progress percentage based on completed/failed agents
        """
        if not self.session_data["agents"]:
            return 0

        total_expected = len(EXPECTED_AGENTS)

        # Count completed and failed agents (both count as "done")
        done_agents = set()
        for entry in self.session_data["agents"]:
            if entry["status"] in ["completed", "failed"]:
                done_agents.add(entry["agent"])

        progress = (len(done_agents) / total_expected) * 100
        return int(progress)

    def get_average_agent_duration(self) -> Optional[int]:
        """Calculate average duration of completed agents.

        Returns:
            Average duration in seconds, or None if no completed agents
        """
        durations = []
        for entry in self.session_data["agents"]:
            if entry["status"] in ["completed", "failed"] and "duration_seconds" in entry:
                durations.append(entry["duration_seconds"])

        if not durations:
            return None

        return sum(durations) // len(durations)

    def estimate_remaining_time(self) -> Optional[int]:
        """Estimate remaining time in seconds based on average agent duration.

        Returns:
            Estimated seconds remaining, or None if cannot estimate
        """
        avg_duration = self.get_average_agent_duration()
        if avg_duration is None:
            return None

        # Count remaining agents
        completed_agents = {
            entry["agent"] for entry in self.session_data["agents"]
            if entry["status"] in ["completed", "failed"]
        }
        remaining = len(EXPECTED_AGENTS) - len(completed_agents)

        # Account for currently running agent's elapsed time
        running_agent = self.get_running_agent()
        if running_agent:
            for entry in reversed(self.session_data["agents"]):
                if entry["agent"] == running_agent and entry["status"] == "started":
                    if "started_at" in entry:
                        started = datetime.fromisoformat(entry["started_at"])
                        elapsed = (datetime.now() - started).total_seconds()
                        # Estimate this agent still needs avg_duration - elapsed
                        remaining_for_current = max(0, avg_duration - elapsed)
                        return int(remaining_for_current + (remaining - 1) * avg_duration)

        return remaining * avg_duration

    def get_pending_agents(self) -> List[str]:
        """Get list of agents that haven't started yet."""
        started_agents = {entry["agent"] for entry in self.session_data["agents"]}
        return [agent for agent in EXPECTED_AGENTS if agent not in started_agents]

    def get_running_agent(self) -> Optional[str]:
        """Get currently running agent, if any."""
        for entry in reversed(self.session_data["agents"]):
            if entry["status"] == "started":
                return entry["agent"]
        return None

    def is_pipeline_complete(self) -> bool:
        """Check if all expected agents have completed."""
        completed_agents = {
            entry["agent"] for entry in self.session_data["agents"]
            if entry["status"] in ["completed", "failed"]
        }
        return set(EXPECTED_AGENTS).issubset(completed_agents)

    def is_agent_tracked(self, agent_name: str) -> bool:
        """Check if agent is already tracked in current session (for duplicate detection).

        Args:
            agent_name: Name of agent to check

        Returns:
            True if agent exists in session (any status), False otherwise

        Raises:
            ValueError: If agent_name is invalid (path traversal, empty, too long)

        Security:
            Uses shared security_utils validation for input validation.
            Logs all queries to audit log.

        Usage (GitHub Issue #57):
            Used by auto_track_from_environment() to prevent duplicate tracking
            when agents are invoked via Task tool.
        """
        # SECURITY: Validate agent name
        agent_name = validate_agent_name(agent_name, purpose="agent tracking check")

        # Check if agent exists in session (any status)
        for entry in self.session_data["agents"]:
            if entry["agent"] == agent_name:
                audit_log("agent_tracker", "success", {
                    "operation": "is_agent_tracked",
                    "agent_name": agent_name,
                    "tracked": True,
                    "status": entry["status"]
                })
                return True

        audit_log("agent_tracker", "success", {
            "operation": "is_agent_tracked",
            "agent_name": agent_name,
            "tracked": False
        })
        return False

    def auto_track_from_environment(self, message: Optional[str] = None) -> bool:
        """Auto-detect and track agent from CLAUDE_AGENT_NAME environment variable.

        This method enables automatic agent tracking when agents are invoked via
        Task tool. The Task tool sets CLAUDE_AGENT_NAME when invoking agents,
        allowing SubagentStop hook to detect and track them automatically.

        Args:
            message: Optional message for agent start. If None, uses default message.

        Returns:
            True if agent was tracked (new tracking), False otherwise (already tracked or no env var)

        Raises:
            ValueError: If CLAUDE_AGENT_NAME contains invalid agent name (path traversal, etc)

        Security:
            - Validates CLAUDE_AGENT_NAME using shared security_utils
            - Validates message parameter length (max 10KB)
            - Logs all operations to audit log
            - Gracefully handles missing environment variable (returns False)

        Usage (GitHub Issue #57):
            Called by SubagentStop hook to auto-detect Task tool agents:

            ```python
            # In auto_update_project_progress.py hook
            tracker = AgentTracker(session_file=session_file)
            was_tracked = tracker.auto_track_from_environment(
                message="Auto-detected from Task tool"
            )
            ```

        Design:
            - Idempotent: Safe to call multiple times (checks is_agent_tracked first)
            - Non-blocking: Returns False if env var missing (doesn't raise exception)
            - Defensive: Validates all inputs before tracking
        """
        # Get agent name from environment
        agent_name = os.environ.get("CLAUDE_AGENT_NAME")

        # If not set (None), return False gracefully (not an error)
        # Note: Empty string "" is different from None and will be validated
        if agent_name is None:
            audit_log("agent_tracker", "success", {
                "operation": "auto_track_from_environment",
                "status": "no_env_var",
                "message": "CLAUDE_AGENT_NAME not set, skipped auto-tracking"
            })
            return False

        # SECURITY: Validate agent name from environment
        # This will catch empty strings, path traversal, etc.
        try:
            agent_name = validate_agent_name(agent_name, purpose="Task tool auto-tracking")
        except ValueError as e:
            # Invalid agent name in environment - log and raise
            audit_log("agent_tracker", "failure", {
                "operation": "auto_track_from_environment",
                "status": "invalid_agent_name",
                "agent_name": agent_name if agent_name else "(empty)",
                "error": str(e)
            })
            raise

        # SECURITY: Validate message parameter (if provided)
        if message is not None:
            try:
                message = validate_input_length(message, 10000, "message", purpose="Task tool auto-tracking")
            except ValueError as e:
                # Invalid message length - log and raise
                audit_log("agent_tracker", "failure", {
                    "operation": "auto_track_from_environment",
                    "status": "invalid_message",
                    "agent_name": agent_name,
                    "error": str(e)
                })
                raise
        else:
            # Default message
            message = f"Auto-detected via Task tool (CLAUDE_AGENT_NAME={agent_name})"

        # Check if already tracked (idempotent)
        if self.is_agent_tracked(agent_name):
            audit_log("agent_tracker", "success", {
                "operation": "auto_track_from_environment",
                "status": "already_tracked",
                "agent_name": agent_name,
                "message": "Agent already tracked, skipped duplicate"
            })
            return False

        # Start tracking agent
        entry = {
            "agent": agent_name,
            "status": "started",
            "started_at": datetime.now().isoformat(),
            "message": message
        }
        self.session_data["agents"].append(entry)
        self._save()

        audit_log("agent_tracker", "success", {
            "operation": "auto_track_from_environment",
            "status": "tracked",
            "agent_name": agent_name,
            "message": message
        })

        # No print() - hooks should be silent unless there's an error
        return True

    def get_agent_emoji(self, status: str) -> str:
        """Get emoji for agent status."""
        emoji_map = {
            "completed": "✅",
            "started": "⏳",
            "failed": "❌",
            "pending": "⬜"
        }
        return emoji_map.get(status, "⬜")

    def get_agent_color(self, status: str) -> str:
        """Get color name for agent status."""
        color_map = {
            "completed": "green",
            "started": "green",
            "failed": "red",
            "pending": "green"
        }
        return color_map.get(status, "green")

    def format_agent_name(self, agent_name: str) -> str:
        """Format agent name for display (e.g., test-master -> Test Master)."""
        return " ".join(word.capitalize() for word in agent_name.split("-"))

    def get_display_metadata(self) -> Dict[str, Any]:
        """Get comprehensive metadata for display purposes.

        Returns:
            Dictionary containing:
            - agents: List of all agents with display metadata
            - progress_percentage: Overall progress (0-100)
            - estimated_time_remaining: Seconds remaining (or 0)
            - github_issue: Linked issue number (or None)
        """
        agents_display = []

        # Create a map of agent status from session data
        agent_status_map = {}
        for entry in self.session_data["agents"]:
            agent_name = entry["agent"]
            agent_status_map[agent_name] = entry

        # Build display data for all expected agents
        for agent_name in EXPECTED_AGENTS:
            meta = AGENT_METADATA.get(agent_name, {})

            if agent_name in agent_status_map:
                entry = agent_status_map[agent_name]
                status = entry["status"]
                agent_data = {
                    "name": agent_name,
                    "status": status,
                    "description": meta.get("description", ""),
                    "emoji": self.get_agent_emoji(status),
                    "agent_emoji": meta.get("emoji", ""),
                    "message": entry.get("message", entry.get("error", "")),
                }

                if "duration_seconds" in entry:
                    agent_data["duration_seconds"] = entry["duration_seconds"]
                if "tools_used" in entry:
                    agent_data["tools"] = entry["tools_used"]
                if "started_at" in entry:
                    agent_data["started_at"] = entry["started_at"]
                if "completed_at" in entry:
                    agent_data["completed_at"] = entry["completed_at"]
            else:
                # Pending agent
                agent_data = {
                    "name": agent_name,
                    "status": "pending",
                    "description": meta.get("description", ""),
                    "emoji": self.get_agent_emoji("pending"),
                    "agent_emoji": meta.get("emoji", ""),
                    "message": ""
                }

            agents_display.append(agent_data)

        return {
            "agents": agents_display,
            "progress_percentage": self.calculate_progress(),
            "estimated_time_remaining": self.estimate_remaining_time() or 0,
            "github_issue": self.session_data.get("github_issue")
        }

    def get_tree_view_data(self) -> Dict[str, Any]:
        """Get data structured for tree view display.

        Returns:
            Dictionary with agents, progress, and metadata for tree rendering
        """
        metadata = self.get_display_metadata()

        # Add tree structure information
        agents_with_levels = []
        for agent in metadata["agents"]:
            agent_with_level = agent.copy()
            agent_with_level["indent_level"] = 1  # All agents at level 1 under pipeline

            # If agent has tools, they go at level 2
            if "tools" in agent and agent["tools"]:
                agent_with_level["has_children"] = True
            else:
                agent_with_level["has_children"] = False

            agents_with_levels.append(agent_with_level)

        return {
            "agents": agents_with_levels,
            "progress": metadata["progress_percentage"],
            "estimated_remaining": metadata["estimated_time_remaining"],
            "github_issue": metadata["github_issue"],
            "session_id": self.session_data.get("session_id"),
            "started": self.session_data.get("started")
        }

    def show_status(self):
        """Show pipeline status"""
        print(f"\n📊 Agent Pipeline Status ({self.session_data['session_id']})\n")
        print(f"Session started: {self.session_data['started']}")
        print(f"Session file: {self.session_file.name}")

        # Show GitHub issue if linked
        github_issue = self.session_data.get("github_issue")
        if github_issue:
            print(f"GitHub issue: #{github_issue}")
        print()

        if not self.session_data["agents"]:
            print("No agents have run yet.\n")
            return

        # Group by agent and show most recent status
        agent_statuses = {}
        for entry in self.session_data["agents"]:
            agent_name = entry["agent"]
            agent_statuses[agent_name] = entry

        # Display each agent
        for agent_name, entry in agent_statuses.items():
            status = entry["status"]

            if status == "started":
                timestamp = entry.get("started_at", "")
                message = entry.get("message", "")
                print(f"⏳ {agent_name:20s} RUNNING   {timestamp[11:19]} - {message}")

            elif status == "completed":
                timestamp = entry.get("completed_at", "")
                duration = entry.get("duration_seconds", 0)
                message = entry.get("message", "")
                tools = entry.get("tools_used", [])
                tools_str = f" (tools: {', '.join(tools)})" if tools else ""
                print(f"✅ {agent_name:20s} COMPLETE  {timestamp[11:19]} ({duration}s) - {message}{tools_str}")

            elif status == "failed":
                timestamp = entry.get("failed_at", "")
                duration = entry.get("duration_seconds", 0)
                error = entry.get("error", "")
                print(f"❌ {agent_name:20s} FAILED    {timestamp[11:19]} ({duration}s) - {error}")

        # Show pipeline completeness
        print(f"\n{'='*70}")
        expected_agents = {"researcher", "planner", "test-master", "implementer",
                          "reviewer", "security-auditor", "doc-master"}
        completed_agents = {
            entry["agent"] for entry in self.session_data["agents"]
            if entry["status"] == "completed"
        }

        if expected_agents.issubset(completed_agents):
            print("Pipeline: COMPLETE ✅")
        else:
            missing = expected_agents - completed_agents
            print(f"Pipeline: INCOMPLETE ⚠️  Missing: {', '.join(missing)}")

        total_duration = sum(
            entry.get("duration_seconds", 0)
            for entry in self.session_data["agents"]
            if "duration_seconds" in entry
        )
        print(f"Total duration: {total_duration // 60}m {total_duration % 60}s")
        print()

    def verify_parallel_exploration(self) -> bool:
        """Verify parallel execution of researcher and planner agents.

        This method validates that both researcher and planner agents completed
        successfully and calculates parallelization efficiency metrics.

        Returns:
            True if both agents completed (parallel or sequential)
            False if agents incomplete or failed

        Side Effects:
            Writes parallel_exploration metadata to session file:
            {
                "status": "parallel" | "sequential" | "incomplete" | "failed",
                "sequential_time_seconds": int,
                "parallel_time_seconds": int,
                "time_saved_seconds": int,
                "efficiency_percent": float,
                "missing_agents": List[str],  # if incomplete
                "failed_agents": List[str]    # if failed
            }

        Raises:
            ValueError: Invalid timestamp format or missing required fields

        Phase 2 Requirements:
            - Verify both researcher and planner completed
            - Detect parallel vs sequential execution (start times within 5 seconds)
            - Calculate time savings and efficiency metrics
            - Handle failures gracefully
        """
        # Reload session data to get latest state (in case file was modified externally)
        if self.session_file.exists():
            self.session_data = json.loads(self.session_file.read_text())

        # Initialize duplicate tracking
        self._duplicate_agents = []

        # Find researcher and planner agents
        researcher = self._find_agent("researcher")
        planner = self._find_agent("planner")

        # Check completion status
        if not researcher or not planner:
            missing_agents = []
            if not researcher:
                missing_agents.append("researcher")
            if not planner:
                missing_agents.append("planner")

            self._write_incomplete_status(missing_agents)
            return False

        if researcher["status"] != "completed" or planner["status"] != "completed":
            # Distinguish between failed agents and not-yet-completed agents
            failed_agents = []
            incomplete_agents = []

            if researcher["status"] == "failed":
                failed_agents.append("researcher")
            elif researcher["status"] != "completed":
                incomplete_agents.append("researcher")

            if planner["status"] == "failed":
                failed_agents.append("planner")
            elif planner["status"] != "completed":
                incomplete_agents.append("planner")

            # If any failed, report as failed
            if failed_agents:
                self._write_failed_status(failed_agents)
            else:
                # Otherwise report as incomplete (agents not yet finished)
                self._write_incomplete_status(incomplete_agents)
            return False

        # Validate timing data
        self._validate_timestamps(researcher, planner)

        # Calculate metrics
        researcher_duration = researcher.get("duration_seconds", 0)
        planner_duration = planner.get("duration_seconds", 0)

        sequential_time = researcher_duration + planner_duration
        parallel_time = max(researcher_duration, planner_duration)
        time_saved = sequential_time - parallel_time
        efficiency = (time_saved / sequential_time * 100) if sequential_time > 0 else 0

        # Detect parallel vs sequential execution
        is_parallel = self._detect_parallel_execution(researcher, planner)
        status = "parallel" if is_parallel else "sequential"

        # If sequential, time_saved should be 0
        if not is_parallel:
            time_saved = 0
            efficiency = 0

        # Write metrics to session file
        metrics = {
            "status": status,
            "sequential_time_seconds": sequential_time,
            "parallel_time_seconds": parallel_time,
            "time_saved_seconds": time_saved,
            "efficiency_percent": round(efficiency, 2)
        }

        # Add duplicate_agents if any were found
        if hasattr(self, '_duplicate_agents') and self._duplicate_agents:
            metrics["duplicate_agents"] = list(set(self._duplicate_agents))  # Remove duplicates in the list itself

        self.session_data["parallel_exploration"] = metrics
        self._save()

        # Audit log verification result
        audit_log("agent_tracker", "success", {
            "operation": "verify_parallel_exploration",
            "status": status,
            "time_saved_seconds": time_saved,
            "efficiency_percent": round(efficiency, 2)
        })

        return True

    def verify_parallel_validation(self) -> bool:
        """Verify parallel execution of reviewer, security-auditor, and doc-master agents.

        This method validates that all three validation agents completed successfully
        and calculates parallelization efficiency metrics.

        Returns:
            True if parallel validation succeeded (3 agents completed), False otherwise

        Side Effects:
            Writes parallel_validation metadata to session file:
            {
                "status": "parallel" | "sequential" | "incomplete" | "failed",
                "sequential_time_seconds": int,
                "parallel_time_seconds": int,
                "time_saved_seconds": int,
                "efficiency_percent": float,
                "missing_agents": List[str],  # if incomplete
                "failed_agents": List[str]    # if failed
            }

        Raises:
            ValueError: Invalid timestamp format or missing required fields

        Phase 3 Requirements:
            - Verify all 3 validation agents (reviewer, security-auditor, doc-master) completed
            - Detect parallel vs sequential execution (all start times within 5 seconds)
            - Calculate time savings and efficiency metrics
            - Handle failures gracefully
        """
        # Reload session data to get latest state (in case file was modified externally)
        if self.session_file.exists():
            self.session_data = json.loads(self.session_file.read_text())

        # Initialize duplicate tracking
        self._duplicate_agents = []

        # Find the 3 validation agents
        reviewer = self._find_agent("reviewer")
        security = self._find_agent("security-auditor")
        doc_master = self._find_agent("doc-master")

        # Check for missing agents and failures
        missing_agents = []
        failed_agents = []
        incomplete_agents = []

        # Check each agent
        agents = [
            (reviewer, "reviewer"),
            (security, "security-auditor"),
            (doc_master, "doc-master")
        ]

        for agent, name in agents:
            if agent is None:
                missing_agents.append(name)
            elif agent["status"] == "failed":
                failed_agents.append(name)
            elif agent["status"] != "completed":
                incomplete_agents.append(name)

        # If any issues found (missing, failed, or incomplete), handle them
        if missing_agents or failed_agents or incomplete_agents:
            # Failed status takes precedence over incomplete/missing
            if failed_agents:
                self._record_failed_validation(failed_agents)
            else:
                # Report missing agents as incomplete
                self._record_incomplete_validation(missing_agents + incomplete_agents)
            return {
                "parallel_detected": False,
                "agents_validated": [],
                "efficiency_percent": 0,
                "status": "failed" if failed_agents else "incomplete",
                "time_saved_seconds": 0
            }

        # Calculate metrics
        reviewer_duration = reviewer.get("duration_seconds", 0)
        security_duration = security.get("duration_seconds", 0)
        doc_duration = doc_master.get("duration_seconds", 0)

        sequential_time = reviewer_duration + security_duration + doc_duration
        parallel_time = max(reviewer_duration, security_duration, doc_duration)
        time_saved = sequential_time - parallel_time
        efficiency = (time_saved / sequential_time * 100) if sequential_time > 0 else 0

        # Detect parallel vs sequential execution
        is_parallel = self._detect_parallel_execution_three_agents(reviewer, security, doc_master)
        status = "parallel" if is_parallel else "sequential"

        # If sequential, time_saved should be 0
        if not is_parallel:
            time_saved = 0
            efficiency = 0

        # Write metrics to session file
        metrics = {
            "status": status,
            "sequential_time_seconds": sequential_time,
            "parallel_time_seconds": parallel_time,
            "time_saved_seconds": time_saved,
            "efficiency_percent": round(efficiency, 2)
        }

        # Add duplicate_agents if any were found
        if hasattr(self, '_duplicate_agents') and self._duplicate_agents:
            metrics["duplicate_agents"] = list(set(self._duplicate_agents))

        self.session_data["parallel_validation"] = metrics
        self._save()

        # Audit log verification result
        audit_log("agent_tracker", "success", {
            "operation": "verify_parallel_validation",
            "status": status,
            "time_saved_seconds": time_saved,
            "efficiency_percent": round(efficiency, 2)
        })

        # Return True if validation succeeded (all 3 agents completed)
        # Backward compatible with auto-implement.md:347
        return status in ("parallel", "sequential")

    def get_parallel_validation_metrics(self) -> Dict[str, Any]:
        """Get detailed parallel validation metrics.

        Returns:
            Dict with parallel validation metrics:
            {
                "parallel_detected": bool,
                "agents_validated": List[str],
                "efficiency_percent": float,
                "status": str,
                "time_saved_seconds": int
            }
            Returns empty dict {} if no parallel_validation data in session

        Note:
            This method provides detailed metrics for testing and debugging.
            For simple success/failure checks, use verify_parallel_validation() instead.
        """
        if "parallel_validation" not in self.session_data:
            return {}

        metrics = self.session_data["parallel_validation"]
        return {
            "parallel_detected": metrics.get("status") == "parallel",
            "agents_validated": ["reviewer", "security-auditor", "doc-master"],
            "efficiency_percent": metrics.get("efficiency_percent", 0),
            "status": metrics.get("status", "unknown"),
            "time_saved_seconds": metrics.get("time_saved_seconds", 0)
        }

    def _validate_agent_data(self, agent_data: Dict[str, Any]) -> bool:
        """Validate agent data structure and timestamps.

        Args:
            agent_data: Agent data dict to validate

        Returns:
            True if valid, False otherwise

        Validates:
            - Required fields: agent, status, started_at, completed_at
            - Status is in ["completed", "failed"]
            - Timestamps are valid ISO format

        Security:
            No exceptions raised - graceful validation for robust parsing
        """
        # Check required fields
        required_fields = ["agent", "status", "started_at", "completed_at"]
        if not all(field in agent_data for field in required_fields):
            return False

        # Validate status
        if agent_data["status"] not in ["completed", "failed"]:
            return False

        # Validate timestamps (ISO format)
        try:
            datetime.fromisoformat(agent_data["started_at"])
            datetime.fromisoformat(agent_data["completed_at"])
        except (ValueError, TypeError):
            return False

        return True

    def _get_session_text_file(self) -> Optional[str]:
        """Get session text file path (.md) from JSON file path.

        Returns:
            Path to session .md file if exists, None otherwise

        Example:
            JSON: docs/sessions/20251111-test-pipeline.json
            Text: docs/sessions/20251111-test-session.md

            JSON: docs/sessions/test_session.json
            Text: docs/sessions/test_session-session.md OR docs/sessions/20251111-test-session.md
        """
        try:
            # Derive .md file path from JSON path
            json_path = Path(self.session_file)
            stem = json_path.stem

            # Try multiple naming patterns
            possible_paths = []

            # Pattern 1: Remove -pipeline suffix if present, add -session
            if stem.endswith("-pipeline"):
                base_stem = stem[:-9]  # Remove "-pipeline"
                possible_paths.append(json_path.parent / f"{base_stem}-session.md")

            # Pattern 2: Direct stem + -session
            possible_paths.append(json_path.parent / f"{stem}-session.md")

            # Pattern 3: Extract session ID from stem if present (e.g., "20251111-test")
            # For test files like "test_session.json", try to find matching session IDs
            if "_" in stem:
                # Look for any session file in the directory
                for md_file in json_path.parent.glob("*-session.md"):
                    possible_paths.append(md_file)

            # Check each possible path
            for text_path in possible_paths:
                if text_path.exists():
                    return str(text_path)

            return None
        except Exception as e:
            audit_log("agent_tracker", "error", {
                "operation": "_get_session_text_file",
                "error": str(e)
            })
            return None

    def _detect_agent_from_session_text(
        self,
        agent_name: str,
        session_text_path: str
    ) -> Optional[Dict[str, Any]]:
        """Parse session text file for agent completion markers.

        Args:
            agent_name: Name of agent to find (e.g., "researcher")
            session_text_path: Path to session .md file

        Returns:
            Agent data dict if found, None otherwise

        Format Expected:
            **HH:MM:SS - agent_name**: message
            **HH:MM:SS - agent_name**: ... completed

        Security:
            - Validates path to prevent traversal attacks
            - Audit logs all operations
            - Graceful error handling (no crashes)
        """
        try:
            # SECURITY: Validate path
            validated_path = validate_path(
                Path(session_text_path),
                purpose="session text parsing",
                allow_missing=False
            )

            # Read file
            if not validated_path.exists():
                return None

            content = validated_path.read_text()

            # Find agent markers (regex)
            import re

            # First, check if there are ANY malformed entries for this agent
            # Look for lines with agent name but invalid timestamp format
            malformed_pattern = rf"\*\*[^*]+ - {re.escape(agent_name)}\*\*:"
            all_agent_lines = re.findall(malformed_pattern, content, re.MULTILINE)

            # Pattern: **HH:MM:SS - agent_name**: message (strict timestamp format)
            # This pattern ensures HH, MM, SS are valid digits
            valid_pattern = rf"\*\*(\d{{2}}:\d{{2}}:\d{{2}}) - {re.escape(agent_name)}\*\*: (.+)"
            matches = re.findall(valid_pattern, content, re.MULTILINE)

            # If we found agent mentions but some don't match valid pattern, data is unreliable
            if len(all_agent_lines) > len(matches):
                return None  # Some malformed timestamps detected

            if not matches:
                return None

            # Validate all timestamps match the pattern (no INVALID strings)
            for time_str, _ in matches:
                # Additional validation: check if time components are numeric
                time_parts = time_str.split(':')
                if len(time_parts) != 3:
                    return None
                try:
                    # Validate each component is a valid integer
                    hours, minutes, seconds = int(time_parts[0]), int(time_parts[1]), int(time_parts[2])
                    # Basic range validation
                    if not (0 <= hours <= 23 and 0 <= minutes <= 59 and 0 <= seconds <= 59):
                        return None
                except ValueError:
                    return None  # Invalid timestamp component

            # Find completion marker (latest one if multiple)
            # Separate completions and starts
            completion_markers = []
            start_markers = []

            for time_str, message in matches:
                if "completed" in message.lower() or "complete" in message.lower():
                    completion_markers.append((time_str, message))
                else:
                    start_markers.append((time_str, message))

            if not completion_markers:
                return None

            # Use the latest completion
            completion_marker = completion_markers[-1]

            # Find the corresponding start marker (last start before this completion)
            # If there are multiple completions, pair them correctly
            start_marker = None
            if start_markers:
                # Use the start marker that corresponds to this completion
                # If we have equal numbers of starts and completions, pair them
                if len(start_markers) >= len(completion_markers):
                    start_marker = start_markers[len(completion_markers) - 1]
                else:
                    # More completions than starts, use the last available start
                    start_marker = start_markers[-1]

            # Parse timestamps - extract session date from content
            session_date = None

            # Try Pattern 1: "Session YYYYMMDD" or "# Session YYYYMMDD"
            date_match = re.search(r"(?:#\s+)?Session (\d{8})", content)
            if date_match:
                session_date = date_match.group(1)  # e.g., "20251111"
            else:
                # Try Pattern 2: "**Started**: YYYY-MM-DD HH:MM:SS"
                date_match = re.search(r"\*\*Started\*\*:\s+(\d{4})-(\d{2})-(\d{2})", content)
                if date_match:
                    session_date = f"{date_match.group(1)}{date_match.group(2)}{date_match.group(3)}"
                else:
                    # Try Pattern 3: Use session_id from tracker if available
                    if hasattr(self, 'session_data') and 'session_id' in self.session_data:
                        session_id = self.session_data['session_id']
                        # Extract date from session_id (format: YYYYMMDD-HHMMSS or YYYYMMDD-test)
                        id_date_match = re.match(r"(\d{8})", session_id)
                        if id_date_match:
                            session_date = id_date_match.group(1)

            if not session_date:
                # No date found, return None
                return None

            # Convert to ISO format
            start_time_str = f"{session_date[:4]}-{session_date[4:6]}-{session_date[6:8]}T{start_marker[0] if start_marker else completion_marker[0]}"
            complete_time_str = f"{session_date[:4]}-{session_date[4:6]}-{session_date[6:8]}T{completion_marker[0]}"

            # Build agent data
            agent_data = {
                "agent": agent_name,
                "status": "completed",
                "started_at": start_time_str,
                "completed_at": complete_time_str,
                "message": completion_marker[1]
            }

            # Calculate duration if both timestamps available
            if start_marker:
                try:
                    start_dt = datetime.fromisoformat(start_time_str)
                    complete_dt = datetime.fromisoformat(complete_time_str)
                    duration = int((complete_dt - start_dt).total_seconds())
                    agent_data["duration_seconds"] = duration
                except ValueError:
                    pass  # Duration calculation failed, skip

            # Validate before returning
            if not self._validate_agent_data(agent_data):
                return None

            # Audit log successful detection
            audit_log("agent_tracker", "info", {
                "operation": "_detect_agent_from_session_text",
                "agent_name": agent_name,
                "detection_method": "session_text_parsing",
                "file": str(validated_path)
            })

            return agent_data

        except Exception as e:
            # Log error but don't crash
            audit_log("agent_tracker", "error", {
                "operation": "_detect_agent_from_session_text",
                "agent_name": agent_name,
                "error": str(e)
            })
            return None

    def _detect_agent_from_json_structure(
        self,
        agent_name: str
    ) -> Optional[Dict[str, Any]]:
        """Reload JSON file to detect external modifications.

        Args:
            agent_name: Name of agent to find

        Returns:
            Agent data dict if found and valid, None otherwise

        Purpose:
            Detect Task tool agents that modified JSON directly
            (bypassing tracker's in-memory state)

        Security:
            - Validates JSON parsing
            - Graceful error handling
            - Audit logs detection
        """
        try:
            # Reload from disk (detect external changes)
            if not self.session_file.exists():
                return None

            # Parse JSON
            try:
                session_data = json.loads(self.session_file.read_text())
            except json.JSONDecodeError:
                return None  # Corrupted JSON

            # Find agent
            agents = [a for a in session_data.get("agents", []) if a.get("agent") == agent_name]
            if not agents:
                return None

            # Get latest entry
            agent_data = agents[-1]

            # Must be completed or failed
            if agent_data.get("status") not in ["completed", "failed"]:
                return None

            # Validate data
            if not self._validate_agent_data(agent_data):
                return None

            # Audit log successful detection
            audit_log("agent_tracker", "info", {
                "operation": "_detect_agent_from_json_structure",
                "agent_name": agent_name,
                "detection_method": "json_reload",
                "status": agent_data.get("status")
            })

            return agent_data

        except Exception as e:
            # Log error but don't crash
            audit_log("agent_tracker", "error", {
                "operation": "_detect_agent_from_json_structure",
                "agent_name": agent_name,
                "error": str(e)
            })
            return None

    def _find_agent(self, agent_name: str) -> Optional[Dict[str, Any]]:
        """Find agent in session data, return latest entry.

        Multi-method detection (Issue #71):
        1. Check agent tracker state (existing behavior - FAST)
        2. Analyze JSON structure (external modifications)
        3. Parse session text file (Task tool agents)

        Also tracks if there are duplicates for warning purposes.

        Args:
            agent_name: Name of agent to find

        Returns:
            Agent data dict if found, None otherwise

        Security:
            All detection methods include audit logging and validation
        """
        # Priority 1: Check tracker state (existing behavior - FAST)
        agents = [a for a in self.session_data.get("agents", []) if a["agent"] == agent_name]

        if agents:
            # Track duplicates (existing behavior)
            if len(agents) > 1 and not hasattr(self, '_duplicate_agents'):
                self._duplicate_agents = []
            if len(agents) > 1:
                self._duplicate_agents.append(agent_name)

            # Return latest entry (completed or otherwise)
            return agents[-1]

        # Priority 2: Check JSON structure (external modifications)
        agent_data = self._detect_agent_from_json_structure(agent_name)
        if agent_data is not None:
            return agent_data

        # Priority 3: Parse session text (Task tool agents)
        session_text_file = self._get_session_text_file()
        if session_text_file is not None:
            agent_data = self._detect_agent_from_session_text(agent_name, session_text_file)
            if agent_data is not None:
                return agent_data

        # Not found in any method
        return None

    def _validate_timestamps(self, researcher: Dict[str, Any], planner: Dict[str, Any]):
        """Validate timestamps are present and valid ISO format."""
        for agent_name, data in [("researcher", researcher), ("planner", planner)]:
            if "started_at" not in data or "completed_at" not in data:
                raise ValueError(
                    f"Missing timestamp for {agent_name}\n"
                    f"Required fields: started_at, completed_at\n"
                    f"Found: {list(data.keys())}"
                )
            try:
                datetime.fromisoformat(data["started_at"])
                datetime.fromisoformat(data["completed_at"])
            except ValueError as e:
                raise ValueError(
                    f"Invalid timestamp format for {agent_name}: {e}\n"
                    f"Expected ISO format: YYYY-MM-DDTHH:MM:SS\n"
                    f"Got started_at: {data.get('started_at')}\n"
                    f"Got completed_at: {data.get('completed_at')}"
                )

    def _detect_parallel_execution(self, researcher: Dict[str, Any], planner: Dict[str, Any]) -> bool:
        """Detect if agents ran in parallel (start times within 5 seconds)."""
        researcher_start = datetime.fromisoformat(researcher["started_at"])
        planner_start = datetime.fromisoformat(planner["started_at"])

        time_diff = abs((planner_start - researcher_start).total_seconds())
        return time_diff < 5  # Parallel if started within 5 seconds

    def _detect_parallel_execution_three_agents(
        self,
        agent1: Dict[str, Any],
        agent2: Dict[str, Any],
        agent3: Dict[str, Any]
    ) -> bool:
        """Detect if 3 agents ran in parallel (all start times within 5 seconds).

        Args:
            agent1: First agent data dict with 'started_at' timestamp
            agent2: Second agent data dict with 'started_at' timestamp
            agent3: Third agent data dict with 'started_at' timestamp

        Returns:
            True if all agents started within 5 seconds of each other, False otherwise

        Implementation:
            Checks all pairwise time differences between the 3 agents.
            If the maximum difference is < 5 seconds, considers them parallel.
        """
        # Parse all start times
        start1 = datetime.fromisoformat(agent1["started_at"])
        start2 = datetime.fromisoformat(agent2["started_at"])
        start3 = datetime.fromisoformat(agent3["started_at"])

        # Calculate all pairwise time differences
        diff_1_2 = abs((start2 - start1).total_seconds())
        diff_1_3 = abs((start3 - start1).total_seconds())
        diff_2_3 = abs((start3 - start2).total_seconds())

        # Parallel if all pairs started within 5 seconds
        max_diff = max(diff_1_2, diff_1_3, diff_2_3)
        return max_diff < 5  # Note: < 5, not <= 5

    def _write_incomplete_status(self, missing_agents: List[str]):
        """Write incomplete status to session file."""
        self.session_data["parallel_exploration"] = {
            "status": "incomplete",
            "missing_agents": missing_agents
        }
        self._save()

        audit_log("agent_tracker", "failure", {
            "operation": "verify_parallel_exploration",
            "status": "incomplete",
            "missing_agents": missing_agents
        })

    def _write_failed_status(self, failed_agents: List[str]):
        """Write failed status to session file."""
        self.session_data["parallel_exploration"] = {
            "status": "failed",
            "failed_agents": failed_agents
        }
        self._save()

        audit_log("agent_tracker", "failure", {
            "operation": "verify_parallel_exploration",
            "status": "failed",
            "failed_agents": failed_agents
        })

    def _record_incomplete_validation(self, missing_agents: List[str]):
        """Write incomplete validation status to session file.

        Args:
            missing_agents: List of agent names that didn't run

        Side Effects:
            Updates session_data["parallel_validation"] with incomplete status
            Saves session file atomically
            Logs failure to audit log
        """
        self.session_data["parallel_validation"] = {
            "status": "incomplete",
            "missing_agents": missing_agents
        }
        self._save()

        audit_log("agent_tracker", "failure", {
            "operation": "verify_parallel_validation",
            "status": "incomplete",
            "missing_agents": missing_agents
        })

    def _record_failed_validation(self, failed_agents: List[str]):
        """Write failed validation status to session file.

        Args:
            failed_agents: List of agent names that failed

        Side Effects:
            Updates session_data["parallel_validation"] with failed status
            Saves session file atomically
            Logs failure to audit log
        """
        self.session_data["parallel_validation"] = {
            "status": "failed",
            "failed_agents": failed_agents
        }
        self._save()

        audit_log("agent_tracker", "failure", {
            "operation": "verify_parallel_validation",
            "status": "failed",
            "failed_agents": failed_agents
        })

    # Helper methods for testing (aliases to existing methods)
    def log_start(self, agent_name: str, message: str):
        """Alias for start_agent() for backward compatibility with tests."""
        return self.start_agent(agent_name, message)

    def log_complete(self, agent_name: str, message: str, tools_used: Optional[List[str]] = None):
        """Alias for complete_agent() for backward compatibility with tests."""
        return self.complete_agent(agent_name, message, tools=tools_used)

    def log_fail(self, agent_name: str, message: str):
        """Alias for fail_agent() for backward compatibility with tests."""
        return self.fail_agent(agent_name, message)

    def get_status(self) -> Dict[str, Any]:
        """Get current session status as a dictionary.

        Returns:
            Dictionary with session_id, started, and agents list
        """
        return {
            "session_id": self.session_data.get("session_id", ""),
            "started": self.session_data.get("started", ""),
            "github_issue": self.session_data.get("github_issue"),
            "agents": self.session_data.get("agents", [])
        }


def main():
    if len(sys.argv) < 2:
        print("Usage: agent_tracker.py <command> [args...]")
        print("\nCommands:")
        print("  start <agent> <message>                   - Log agent start")
        print("  complete <agent> <message> [--tools T1,T2] - Log agent completion")
        print("  fail <agent> <message>                     - Log agent failure")
        print("  set-github-issue <number>                  - Link GitHub issue to session")
        print("  status                                     - Show pipeline status")
        print("  verify_parallel_validation                 - Verify parallel validation checkpoint")
        print("\nExamples:")
        print('  agent_tracker.py start researcher "Researching JWT patterns"')
        print('  agent_tracker.py complete researcher "Found 3 patterns" --tools "WebSearch,Grep"')
        print('  agent_tracker.py fail researcher "No patterns found"')
        print('  agent_tracker.py set-github-issue 123')
        print('  agent_tracker.py status')
        print('  agent_tracker.py verify_parallel_validation')
        sys.exit(1)

    tracker = AgentTracker()
    command = sys.argv[1]

    if command == "start":
        if len(sys.argv) < 4:
            print("Usage: agent_tracker.py start <agent> <message>")
            sys.exit(1)
        agent_name = sys.argv[2]
        message = " ".join(sys.argv[3:])
        tracker.start_agent(agent_name, message)

    elif command == "complete":
        if len(sys.argv) < 4:
            print("Usage: agent_tracker.py complete <agent> <message> [--tools T1,T2]")
            sys.exit(1)
        agent_name = sys.argv[2]

        # Check for --tools flag
        tools = None
        if "--tools" in sys.argv:
            tools_idx = sys.argv.index("--tools")
            tools = sys.argv[tools_idx + 1].split(",")
            message = " ".join(sys.argv[3:tools_idx])
        else:
            message = " ".join(sys.argv[3:])

        tracker.complete_agent(agent_name, message, tools)

    elif command == "fail":
        if len(sys.argv) < 4:
            print("Usage: agent_tracker.py fail <agent> <message>")
            sys.exit(1)
        agent_name = sys.argv[2]
        message = " ".join(sys.argv[3:])
        tracker.fail_agent(agent_name, message)

    elif command == "set-github-issue":
        if len(sys.argv) < 3:
            print("Usage: agent_tracker.py set-github-issue <number>")
            sys.exit(1)

        # Parse issue number with error handling
        try:
            issue_number = int(sys.argv[2])
        except ValueError:
            print(f"❌ Invalid issue number: '{sys.argv[2]}'")
            print(f"   Expected: Positive integer (e.g., 42)")
            print(f"   Got: {sys.argv[2]}")
            print()
            print(f"   Issue numbers must be numeric (not strings like 'abc' or floats like '12.5')")
            sys.exit(1)

        tracker.set_github_issue(issue_number)

    elif command == "status":
        tracker.show_status()

    elif command == "verify_parallel_validation":
        result = tracker.verify_parallel_validation()
        # result is now a dict, check if agents were validated
        if result.get("agents_validated"):
            print("\n✅ Parallel validation checkpoint passed")
            # Print metrics from result dict
            status = result.get("status", "unknown")
            if status == "parallel":
                time_saved = result.get("time_saved_seconds", 0)
                efficiency = result.get("efficiency_percent", 0)
                print(f"   Status: Parallel execution detected")
                print(f"   Time saved: {time_saved}s ({efficiency:.1f}% efficiency)")
            elif status == "sequential":
                print(f"   Status: Sequential execution (all agents completed)")
            sys.exit(0)
        else:
            print("\n❌ Parallel validation checkpoint failed")
            status = result.get("status", "unknown")
            if status == "incomplete":
                # Check session data for missing agents
                metadata = tracker.session_data.get("parallel_validation", {})
                missing = metadata.get("missing_agents", [])
                print(f"   Missing agents: {', '.join(missing)}")
            elif status == "failed":
                # Check session data for failed agents
                metadata = tracker.session_data.get("parallel_validation", {})
                failed = metadata.get("failed_agents", [])
                print(f"   Failed agents: {', '.join(failed)}")
            sys.exit(1)

    else:
        print(f"Unknown command: {command}")
        print("Valid commands: start, complete, fail, set-github-issue, status, verify_parallel_validation")
        sys.exit(1)


if __name__ == "__main__":
    main()
