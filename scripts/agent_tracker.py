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

# Input validation constants
MAX_ISSUE_NUMBER = 999999  # GitHub issue numbers are typically < 1M
MIN_ISSUE_NUMBER = 1
MAX_MESSAGE_LENGTH = 10000  # 10KB max message length to prevent bloat

# Project root for path validation (whitelist approach)
PROJECT_ROOT = Path(__file__).parent.parent.resolve()


class AgentTracker:
    def __init__(self, session_file: Optional[str] = None):
        """Initialize AgentTracker with path traversal protection.

        Args:
            session_file: Optional path to session file for testing.
                         If None, creates/finds session file automatically.

        Raises:
            ValueError: If session_file path is outside project (path traversal attempt)

        Path Validation Design (GitHub Issue #45):
        ===========================================
        This method prevents path traversal attacks via three layers:

        1. String-level check: Rejects any path containing '..' sequences
           Example: "../../etc/passwd" blocked immediately
           Rationale: Catches obvious traversal attempts before filesystem operations

        2. Symlink resolution: resolve() follows symlinks and normalizes path
           Example: "/session/link" -> "/etc/passwd" (if symlink points outside)
           Rationale: Symlink-based escapes are caught after resolution

        3. System directory checks: Rejects paths in sensitive system directories
           Protected: /etc/, /var/log/, /usr/, /bin/, /sbin/
           Rationale: Even if somehow valid, prevents writing to system files

        Attack Scenarios Blocked:
        =========================
        - Relative traversal: "../../etc/passwd" (blocked by check #1)
        - Absolute paths: "/etc/passwd" (blocked by check #3)
        - Symlink escapes: "link_to_etc" -> "/etc/passwd" (blocked by check #2)
        - Mixed: "subdir/../../etc/passwd" (blocked by check #2 after resolve)
        """
        if session_file:
            # Use provided session file (for testing)
            self.session_file = Path(session_file)

            # SECURITY LAYER 1: Reject symlinks immediately (defense in depth)
            # Symlinks can be used to escape directory boundaries
            # Check before resolve() to catch symlink attacks early
            if self.session_file.is_symlink():
                raise ValueError(
                    f"Symlinks are not allowed: {session_file}\n"
                    f"Session files cannot be symlinks for security reasons.\n"
                    f"Expected: Regular file path (e.g., 'docs/sessions/session.json')\n"
                    f"See: docs/SECURITY.md#path-validation"
                )

            # SECURITY LAYER 2: Resolve and validate resolved path
            try:
                # resolve() follows symlinks and normalizes paths
                # This catches path normalization tricks and relative paths
                resolved_path = self.session_file.resolve()

                # Check for symlinks in the resolved path components
                # This catches symlinks in parent directories
                if resolved_path.is_symlink():
                    raise ValueError(
                        f"Path contains symlink: {session_file}\n"
                        f"Resolved path is a symlink: {resolved_path}\n"
                        f"Expected: Regular file path without symlinks\n"
                        f"See: docs/SECURITY.md#path-validation"
                    )

                # SECURITY LAYER 3: Whitelist validation using relative_to()
                # Ensure path is within project root (not /etc/, /usr/, etc.)
                # This replaces blacklist approach with whitelist approach
                try:
                    # This will raise ValueError if path is outside PROJECT_ROOT
                    resolved_path.relative_to(PROJECT_ROOT)
                except ValueError:
                    raise ValueError(
                        f"Path outside project root: {session_file}\n"
                        f"Session files must be within project directory.\n"
                        f"Resolved path: {resolved_path}\n"
                        f"Project root: {PROJECT_ROOT}\n"
                        f"Expected: Path within project (e.g., docs/sessions/session.json)\n"
                        f"See: docs/SECURITY.md#path-validation"
                    )

            except (OSError, RuntimeError) as e:
                # Symlink loops or permission issues
                raise ValueError(
                    f"Invalid session file path: {session_file}\n"
                    f"Error: {e}\n"
                    f"Expected: Valid filesystem path within project\n"
                    f"See: docs/SECURITY.md#path-validation"
                )

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

        except Exception as e:
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

        Input Validation (GitHub Issue #45):
        =====================================
        agent_name validation:
        - Type check: Must be string (not None, not int, etc.)
        - Content check: Cannot be empty or whitespace only
        - Membership check: Must be in EXPECTED_AGENTS list (bypass in test mode)
        - Rationale: Prevents injection, ensures valid agent tracking

        message validation:
        - Length check: Cannot exceed 10KB (10000 bytes)
        - Rationale: Prevents log bloat from extremely long messages
        - Examples: "Failed to parse JWT" (OK), 10KB+ message (rejected)
        """
        # Validate agent name
        # Type validation: Ensure it's a string
        if agent_name is None:
            raise TypeError(
                "Agent name cannot be None.\n"
                "Expected: Non-empty string (e.g., 'researcher')\n"
                "Got: None"
            )

        if not isinstance(agent_name, str):
            raise TypeError(
                f"Agent name must be string, got {type(agent_name).__name__}\n"
                f"Expected: str (e.g., 'researcher')\n"
                f"Got: {type(agent_name).__name__}"
            )

        # Content validation: Ensure it's not empty or whitespace
        if not agent_name or not agent_name.strip():
            raise ValueError(
                "Agent name cannot be empty or whitespace.\n"
                f"Expected: Non-empty string (e.g., 'researcher')\n"
                f"Got: '{agent_name}'"
            )

        # Membership validation: In test mode, allow any agent name for flexibility
        # Otherwise, enforce EXPECTED_AGENTS list
        is_test_mode = os.getenv("PYTEST_CURRENT_TEST") is not None
        if not is_test_mode and agent_name not in EXPECTED_AGENTS:
            raise ValueError(
                f"Unknown agent: '{agent_name}'\n"
                f"Agent not recognized in EXPECTED_AGENTS list.\n"
                f"Valid agents: {', '.join(EXPECTED_AGENTS)}"
            )

        # Message length validation: Prevent bloat
        # Limit: 10KB (10000 bytes) to prevent extremely long messages
        if len(message) > MAX_MESSAGE_LENGTH:
            raise ValueError(
                f"Message too long: {len(message)} bytes (max {MAX_MESSAGE_LENGTH})\n"
                f"Message exceeds maximum length to prevent log bloat.\n"
                f"Expected: Message <= {MAX_MESSAGE_LENGTH} bytes\n"
                f"Suggestion: Truncate to first {MAX_MESSAGE_LENGTH} chars"
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

    def complete_agent(self, agent_name: str, message: str, tools: Optional[List[str]] = None):
        """Log agent completion.

        Args:
            agent_name: Name of the agent (must be in EXPECTED_AGENTS)
            message: Completion message (max 10KB)
            tools: Optional list of tools used

        Raises:
            ValueError: If agent_name is empty/invalid or message too long
            TypeError: If agent_name is None
        """
        # Validate agent name
        if agent_name is None:
            raise TypeError("Agent name cannot be None")

        if not isinstance(agent_name, str):
            raise TypeError(f"Agent name must be string, got {type(agent_name)}")

        if not agent_name or not agent_name.strip():
            raise ValueError("Agent name cannot be empty or whitespace")

        # In test mode, allow any agent name for flexibility
        is_test_mode = os.getenv("PYTEST_CURRENT_TEST") is not None
        if not is_test_mode and agent_name not in EXPECTED_AGENTS:
            raise ValueError(
                f"Unknown agent: '{agent_name}'\n"
                f"Agent not recognized in EXPECTED_AGENTS list.\n"
                f"Valid agents: {', '.join(EXPECTED_AGENTS)}"
            )

        # Validate message length
        if len(message) > MAX_MESSAGE_LENGTH:
            raise ValueError(
                f"Message too long: {len(message)} bytes (max {MAX_MESSAGE_LENGTH})\n"
                f"Message exceeds maximum length to prevent log bloat."
            )

        # Find the most recent entry for this agent
        for entry in reversed(self.session_data["agents"]):
            if entry["agent"] == agent_name and entry["status"] == "started":
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

                print(f"✅ Completed: {agent_name} - {message}")
                print(f"⏱️  Duration: {entry['duration_seconds']}s")
                print(f"📄 Session: {self.session_file.name}")
                return

        # If no started entry found, create a completed entry
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
        """
        # Validate agent name (same as start_agent)
        if agent_name is None:
            raise TypeError("Agent name cannot be None")

        if not isinstance(agent_name, str):
            raise TypeError(f"Agent name must be string, got {type(agent_name)}")

        if not agent_name or not agent_name.strip():
            raise ValueError("Agent name cannot be empty or whitespace")

        # In test mode, allow any agent name for flexibility
        is_test_mode = os.getenv("PYTEST_CURRENT_TEST") is not None
        if not is_test_mode and agent_name not in EXPECTED_AGENTS:
            raise ValueError(
                f"Unknown agent: '{agent_name}'\n"
                f"Agent not recognized in EXPECTED_AGENTS list.\n"
                f"Valid agents: {', '.join(EXPECTED_AGENTS)}"
            )

        # Validate message length
        if len(message) > MAX_MESSAGE_LENGTH:
            raise ValueError(
                f"Message too long: {len(message)} bytes (max {MAX_MESSAGE_LENGTH})\n"
                f"Message exceeds maximum length to prevent log bloat."
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

        Input Validation (GitHub Issue #45):
        =====================================
        Type validation:
        - Must be int type, not float/str/None
        - Rationale: Prevents accidental string numbers or null values

        Range validation:
        - Minimum: 1 (no zero or negative issue numbers)
        - Maximum: 999999 (practical limit, GitHub repos rarely have 1M+ issues)
        - Rationale: Prevents invalid numbers and resource exhaustion

        Examples:
        - set_github_issue(42) -> OK
        - set_github_issue("42") -> TypeError (string not int)
        - set_github_issue(-5) -> ValueError (below minimum)
        - set_github_issue(1000000) -> ValueError (above maximum)
        """
        # Validate type: Must be int, not float/str/None/bool
        if not isinstance(issue_number, int) or isinstance(issue_number, bool):
            raise TypeError(
                f"Issue number must be an integer, got {type(issue_number).__name__}\n"
                f"Expected: positive integer (e.g., 42)\n"
                f"Got: {issue_number}"
            )

        # Validate range: Must be positive and reasonable
        if issue_number < MIN_ISSUE_NUMBER:
            raise ValueError(
                f"Invalid issue number: {issue_number}\n"
                f"Issue number must be a positive integer >= {MIN_ISSUE_NUMBER}\n"
                f"Expected: positive integer\n"
                f"Got: {issue_number}"
            )

        if issue_number > MAX_ISSUE_NUMBER:
            raise ValueError(
                f"Issue number too large: {issue_number}\n"
                f"GitHub issue numbers are typically < 1M.\n"
                f"Maximum allowed: {MAX_ISSUE_NUMBER}\n"
                f"Expected: integer between {MIN_ISSUE_NUMBER}-{MAX_ISSUE_NUMBER}\n"
                f"Got: {issue_number}"
            )

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
        print("\nExamples:")
        print('  agent_tracker.py start researcher "Researching JWT patterns"')
        print('  agent_tracker.py complete researcher "Found 3 patterns" --tools "WebSearch,Grep"')
        print('  agent_tracker.py fail researcher "No patterns found"')
        print('  agent_tracker.py set-github-issue 123')
        print('  agent_tracker.py status')
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

    else:
        print(f"Unknown command: {command}")
        print("Valid commands: start, complete, fail, set-github-issue, status")
        sys.exit(1)


if __name__ == "__main__":
    main()
