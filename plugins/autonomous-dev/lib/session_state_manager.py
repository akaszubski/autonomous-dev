#!/usr/bin/env python3
"""
Session State Manager - Session state persistence in .claude/local/ directory.

Manages persistent state for user sessions. Enables session context persistence,
workflow tracking, and repository-specific knowledge across /clear operations.

Key Features:
1. Session state storage (.claude/local/SESSION_STATE.json)
2. Session context tracking (conventions, tasks, important files)
3. Workflow state tracking (last /implement, todos, recent files)
4. Atomic writes with file locking
5. Security validations (CWE-22 path traversal, CWE-59 symlinks)
6. Survives /clear operations

State Structure:
    {
        "schema_version": "1.0",
        "last_updated": "2026-01-19T12:00:00Z",
        "last_session_id": "20260119-120000",
        "session_context": {
            "key_conventions": [],
            "active_tasks": [],
            "important_files": {},
            "repo_specific": {}
        },
        "workflow_state": {
            "last_implement": {
                "feature": "",
                "completed_at": "",
                "agents_completed": []
            },
            "pending_todos": [],
            "recent_files": []
        }
    }

Workflow:
    1. Initialize SessionStateManager()
    2. load_state() loads existing state or returns default
    3. update_context() adds session context
    4. record_implement_completion() tracks /implement workflow
    5. save_state() persists changes
    6. cleanup_state() removes state file (optional)

Usage:
    from session_state_manager import SessionStateManager
    from pathlib import Path

    # Create manager
    manager = SessionStateManager()

    # Load state
    state = manager.load_state()

    # Update context
    manager.update_context(
        key_conventions=["Use snake_case for functions"],
        active_tasks=["Implement feature X"]
    )

    # Record workflow
    manager.record_implement_completion(
        feature="Add user authentication",
        agents_completed=["researcher", "planner", "implementer"]
    )

    # Get summary
    summary = manager.get_session_summary()
    print(summary)

Date: 2026-01-19
Issue: #247 (Session state persistence in .claude/local/)
Agent: implementer
Phase: TDD Green (making tests pass)

See error-handling-patterns skill for exception hierarchy and error handling best practices.
See state-management-patterns skill for standardized design patterns.
"""

import json
import os
import sys
import tempfile
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

# Import security utilities for path validation
sys.path.insert(0, str(Path(__file__).parent))
from security_utils import validate_path, audit_log
from abstract_state_manager import StateManager
from exceptions import StateError

# Import path utilities for project root detection
try:
    from path_utils import get_project_root
except ImportError:
    # Fallback for tests
    def get_project_root(use_cache: bool = True) -> Path:
        """Fallback project root detection."""
        current = Path.cwd()
        while current != current.parent:
            if (current / ".git").exists() or (current / ".claude").exists():
                return current
            current = current.parent
        return Path.cwd()


# =============================================================================
# Constants
# =============================================================================

# Default state file location
DEFAULT_STATE_FILE = ".claude/local/SESSION_STATE.json"

# Active work markdown file (human-readable summary)
ACTIVE_WORK_FILE = ".claude/local/ACTIVE_WORK.md"

# Default schema version
SCHEMA_VERSION = "1.0"

# Thread-safe file locks
_file_locks: Dict[str, threading.RLock] = {}
_locks_lock = threading.Lock()


# =============================================================================
# Helper Functions
# =============================================================================


def _get_file_lock(file_path: Path) -> threading.RLock:
    """Get or create thread-safe reentrant lock for file.

    Args:
        file_path: Path to file

    Returns:
        Threading reentrant lock for file (allows same thread to acquire multiple times)
    """
    file_key = str(file_path.resolve())
    with _locks_lock:
        if file_key not in _file_locks:
            _file_locks[file_key] = threading.RLock()
        return _file_locks[file_key]


def _get_default_schema() -> Dict[str, Any]:
    """Get default SESSION_STATE.json schema.

    Returns:
        Default schema with all required fields
    """
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    return {
        "schema_version": SCHEMA_VERSION,
        "last_updated": now,
        "last_session_id": datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S"),
        "session_context": {
            "key_conventions": [],
            "active_tasks": [],
            "important_files": {},
            "repo_specific": {}
        },
        "workflow_state": {
            "last_implement": {
                "feature": "",
                "completed_at": "",
                "agents_completed": []
            },
            "pending_todos": [],
            "recent_files": []
        }
    }


def _merge_with_defaults(loaded_state: Dict[str, Any]) -> Dict[str, Any]:
    """Merge loaded state with default schema to ensure all fields exist.

    Args:
        loaded_state: State loaded from file

    Returns:
        State with all required fields (adds defaults for missing fields)
    """
    default = _get_default_schema()

    # Preserve loaded data, add defaults for missing fields
    result = default.copy()
    result.update(loaded_state)

    # Ensure nested structures exist
    if "session_context" not in result or not isinstance(result["session_context"], dict):
        result["session_context"] = default["session_context"]
    else:
        # Merge session_context fields
        for key in default["session_context"]:
            if key not in result["session_context"]:
                result["session_context"][key] = default["session_context"][key]

    if "workflow_state" not in result or not isinstance(result["workflow_state"], dict):
        result["workflow_state"] = default["workflow_state"]
    else:
        # Merge workflow_state fields
        for key in default["workflow_state"]:
            if key not in result["workflow_state"]:
                result["workflow_state"][key] = default["workflow_state"][key]

        # Ensure last_implement structure
        if "last_implement" not in result["workflow_state"] or not isinstance(result["workflow_state"]["last_implement"], dict):
            result["workflow_state"]["last_implement"] = default["workflow_state"]["last_implement"]

    return result


# =============================================================================
# SessionStateManager Class
# =============================================================================


class SessionStateManager(StateManager[Dict[str, Any]]):
    """Session state manager for .claude/local/SESSION_STATE.json.

    Inherits from StateManager ABC to provide standardized state management
    interface while implementing session-specific functionality.

    Attributes:
        state_file: Path to SESSION_STATE.json file

    Examples:
        >>> manager = SessionStateManager()
        >>> state = manager.load_state()
        >>> manager.update_context(key_conventions=["Use snake_case"])
        >>> manager.save_state(state)
    """

    def __init__(self, state_file: Optional[Path | str] = None):
        """Initialize SessionStateManager.

        Args:
            state_file: Optional custom path for state file.
                       If None, uses default (.claude/local/SESSION_STATE.json)
                       Path is validated for security (CWE-22, CWE-59)

        Raises:
            StateError: If state_file contains path traversal or symlink
        """
        if state_file is None:
            # Default: .claude/local/SESSION_STATE.json relative to project root
            project_root = get_project_root()
            self.state_file = project_root / DEFAULT_STATE_FILE
        else:
            self.state_file = Path(state_file)

        # Validate path (security - CWE-22, CWE-59)
        # Validate even if file doesn't exist to catch path traversal early
        try:
            # Check for path traversal in string form (CWE-22)
            path_str = str(self.state_file)
            if ".." in path_str:
                raise StateError(
                    f"Invalid path: path traversal detected in {path_str}\n"
                    f"Paths with '..' are not allowed for security (CWE-22)"
                )

            # If file exists, do full validation including symlink check
            if self.state_file.exists():
                self.state_file = self._validate_state_path(self.state_file)
        except StateError as e:
            # Re-raise with more context
            raise StateError(
                f"Invalid session state file path: {e}\n"
                f"Path: {self.state_file}"
            )

        # Create parent directory if it doesn't exist
        self.state_file.parent.mkdir(parents=True, exist_ok=True)

    def load_state(self) -> Dict[str, Any]:
        """Load session state from file.

        Returns default schema if file doesn't exist or is corrupted.

        Returns:
            Session state dictionary

        Raises:
            StateError: If load fails due to permission error

        Security:
            - Validates path (CWE-22, CWE-59)
            - Graceful degradation on corrupted JSON
            - Audit logging
        """
        # Acquire file lock
        lock = _get_file_lock(self.state_file)
        with lock:
            try:
                # Check if file exists
                if not self.state_file.exists():
                    # Return default schema
                    return _get_default_schema()

                # Validate path (security - CWE-22, CWE-59)
                try:
                    validated_path = validate_path(self.state_file, "session state file", allow_missing=False)
                except ValueError as e:
                    audit_log("session_state_load", "error", {
                        "error": str(e),
                        "path": str(self.state_file),
                    })
                    raise StateError(str(e))

                # Read JSON
                with open(validated_path, 'r') as f:
                    loaded_data = json.load(f)

                # Merge with defaults to ensure all fields exist
                state = _merge_with_defaults(loaded_data)

                # Audit log
                audit_log("session_state_load", "success", {
                    "path": str(validated_path),
                })

                return state

            except json.JSONDecodeError as e:
                # Corrupted JSON - return default schema
                audit_log("session_state_load", "warning", {
                    "error": f"Corrupted JSON: {e}",
                    "path": str(self.state_file),
                })
                return _get_default_schema()

            except PermissionError as e:
                audit_log("session_state_load", "error", {
                    "error": str(e),
                    "path": str(self.state_file),
                })
                raise StateError(f"Permission error while loading session state: {e}")

            except OSError as e:
                # Other OS errors - log and return default schema
                audit_log("session_state_load", "warning", {
                    "error": str(e),
                    "path": str(self.state_file),
                })
                return _get_default_schema()

    def save_state(self, state: Dict[str, Any]) -> None:
        """Save session state to file (atomic write).

        Uses atomic write pattern (temp file + rename) to prevent corruption.
        File permissions set to 0o600 (owner read/write only).

        Args:
            state: Session state to save

        Raises:
            StateError: If save fails

        Security:
            - Validates path (CWE-22, CWE-59)
            - Atomic write (temp file + rename)
            - File permissions 0o600 (owner only)
            - Audit logging
        """
        # Update timestamp
        state["last_updated"] = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

        # Validate path (security - CWE-22, CWE-59)
        try:
            validated_path = validate_path(self.state_file, "session state file", allow_missing=True)
        except ValueError as e:
            audit_log("session_state_save", "error", {
                "error": str(e),
                "path": str(self.state_file),
            })
            raise StateError(str(e))

        # Acquire file lock
        lock = _get_file_lock(validated_path)
        with lock:
            try:
                # Ensure parent directory exists
                validated_path.parent.mkdir(parents=True, exist_ok=True)

                # Atomic write: temp file + rename
                temp_fd, temp_path_str = tempfile.mkstemp(
                    dir=validated_path.parent,
                    prefix=".SESSION_STATE_",
                    suffix=".tmp"
                )
                temp_path = Path(temp_path_str)

                try:
                    # Write JSON to temp file
                    json_data = json.dumps(state, indent=2)
                    os.write(temp_fd, json_data.encode('utf-8'))
                    os.close(temp_fd)

                    # Set permissions (owner read/write only)
                    temp_path.chmod(0o600)

                    # Atomic rename
                    temp_path.replace(validated_path)

                    # Audit log
                    audit_log("session_state_save", "success", {
                        "path": str(validated_path),
                    })

                    # Update ACTIVE_WORK.md (human-readable summary)
                    # Non-blocking - errors logged but don't fail save
                    try:
                        self.update_active_work_md()
                    except Exception as md_error:
                        audit_log("session_state_save", "warning", {
                            "message": "Failed to update ACTIVE_WORK.md",
                            "error": str(md_error),
                        })

                except Exception as e:
                    # Cleanup temp file on error
                    try:
                        os.close(temp_fd)
                    except OSError:
                        pass  # Ignore errors closing file descriptor
                    try:
                        temp_path.unlink()
                    except (OSError, IOError):
                        pass  # Ignore errors during cleanup
                    raise

            except OSError as e:
                audit_log("session_state_save", "error", {
                    "error": str(e),
                    "path": str(validated_path),
                })
                # Provide more specific error messages
                error_msg = str(e).lower()
                if "space" in error_msg or "disk full" in error_msg:
                    raise StateError(f"Disk space error while saving session state: {e}")
                elif "permission" in error_msg:
                    raise StateError(f"Permission error while saving session state: {e}")
                else:
                    raise StateError(f"Failed to save session state: {e}")

    def cleanup_state(self) -> None:
        """Remove session state file safely.

        Raises:
            StateError: If cleanup fails
        """
        # Validate path (security)
        try:
            validated_path = validate_path(self.state_file, "session state file", allow_missing=True)
        except ValueError as e:
            audit_log("session_state_cleanup", "error", {
                "error": str(e),
                "path": str(self.state_file),
            })
            raise StateError(str(e))

        # Acquire file lock
        lock = _get_file_lock(validated_path)
        with lock:
            try:
                if validated_path.exists():
                    validated_path.unlink()
                    audit_log("session_state_cleanup", "success", {
                        "path": str(validated_path),
                    })
            except OSError as e:
                audit_log("session_state_cleanup", "error", {
                    "error": str(e),
                    "path": str(validated_path),
                })
                raise StateError(f"Failed to cleanup session state: {e}")

    def update_context(
        self,
        key_conventions: Optional[List[str]] = None,
        active_tasks: Optional[List[str]] = None,
        important_files: Optional[Dict[str, str]] = None,
        repo_specific: Optional[Dict[str, Any]] = None
    ) -> None:
        """Update session context.

        Merges new context with existing data (additive).

        Args:
            key_conventions: List of coding conventions to add
            active_tasks: List of active tasks to add
            important_files: Dict of important files to add {path: description}
            repo_specific: Dict of repo-specific data to add

        Examples:
            >>> manager.update_context(
            ...     key_conventions=["Use snake_case for functions"],
            ...     active_tasks=["Implement feature X"]
            ... )
        """
        # Load current state
        state = self.load_state()

        # Update session context (merge)
        if key_conventions:
            for convention in key_conventions:
                if convention not in state["session_context"]["key_conventions"]:
                    state["session_context"]["key_conventions"].append(convention)

        if active_tasks:
            for task in active_tasks:
                if task not in state["session_context"]["active_tasks"]:
                    state["session_context"]["active_tasks"].append(task)

        if important_files:
            state["session_context"]["important_files"].update(important_files)

        if repo_specific:
            state["session_context"]["repo_specific"].update(repo_specific)

        # Save updated state
        self.save_state(state)

    def record_implement_completion(
        self,
        feature: str,
        agents_completed: List[str],
        files_modified: Optional[List[str]] = None
    ) -> None:
        """Record /implement completion.

        Args:
            feature: Feature description
            agents_completed: List of agents that completed
            files_modified: Optional list of files modified

        Examples:
            >>> manager.record_implement_completion(
            ...     feature="Add user authentication",
            ...     agents_completed=["researcher", "planner", "implementer"],
            ...     files_modified=["main.py", "test_main.py"]
            ... )
        """
        # Load current state
        state = self.load_state()

        # Update last_implement
        now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        state["workflow_state"]["last_implement"] = {
            "feature": feature,
            "completed_at": now,
            "agents_completed": agents_completed
        }

        # Add files to recent_files (if provided)
        if files_modified:
            for file_path in files_modified:
                if file_path not in state["workflow_state"]["recent_files"]:
                    state["workflow_state"]["recent_files"].append(file_path)

        # Save updated state
        self.save_state(state)

    def get_session_summary(self) -> str:
        """Get human-readable session summary.

        Returns:
            Formatted summary string

        Examples:
            >>> summary = manager.get_session_summary()
            >>> print(summary)
        """
        state = self.load_state()

        lines = [
            "SESSION STATE SUMMARY",
            "=" * 60,
            f"Last Updated: {state.get('last_updated', 'Unknown')}",
            f"Session ID: {state.get('last_session_id', 'Unknown')}",
            "",
            "SESSION CONTEXT:",
        ]

        # Key conventions
        conventions = state["session_context"]["key_conventions"]
        if conventions:
            lines.append(f"  Conventions: {len(conventions)}")
            for conv in conventions[:5]:  # Show first 5
                lines.append(f"    - {conv}")
            if len(conventions) > 5:
                lines.append(f"    ... and {len(conventions) - 5} more")
        else:
            lines.append("  Conventions: None")

        # Active tasks
        tasks = state["session_context"]["active_tasks"]
        if tasks:
            lines.append(f"  Active Tasks: {len(tasks)}")
            for task in tasks[:5]:  # Show first 5
                lines.append(f"    - {task}")
            if len(tasks) > 5:
                lines.append(f"    ... and {len(tasks) - 5} more")
        else:
            lines.append("  Active Tasks: None")

        # Important files
        files = state["session_context"]["important_files"]
        if files:
            lines.append(f"  Important Files: {len(files)}")
            for path, desc in list(files.items())[:5]:  # Show first 5
                lines.append(f"    - {path}: {desc}")
            if len(files) > 5:
                lines.append(f"    ... and {len(files) - 5} more")
        else:
            lines.append("  Important Files: None")

        lines.append("")
        lines.append("WORKFLOW STATE:")

        # Last implement
        last_impl = state["workflow_state"]["last_implement"]
        if last_impl.get("feature"):
            lines.append(f"  Last /implement: {last_impl['feature']}")
            lines.append(f"    Completed: {last_impl.get('completed_at', 'Unknown')}")
            agents = last_impl.get('agents_completed', [])
            if agents:
                lines.append(f"    Agents: {', '.join(agents)}")
        else:
            lines.append("  Last /implement: None")

        # Recent files
        recent = state["workflow_state"]["recent_files"]
        if recent:
            lines.append(f"  Recent Files: {len(recent)}")
            for path in recent[:5]:  # Show first 5
                lines.append(f"    - {path}")
            if len(recent) > 5:
                lines.append(f"    ... and {len(recent) - 5} more")
        else:
            lines.append("  Recent Files: None")

        lines.append("=" * 60)
        return "\n".join(lines)

    def update_active_work_md(self) -> None:
        """Update ACTIVE_WORK.md with human-readable session summary.

        Creates or updates the ACTIVE_WORK.md file alongside SESSION_STATE.json.
        This provides a human-readable view of the current session state.

        Note:
            This method is called automatically by save_state() to keep
            ACTIVE_WORK.md in sync with SESSION_STATE.json.
        """
        state = self.load_state()

        # Build ACTIVE_WORK.md content
        now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

        lines = [
            "# Active Work",
            "",
            f"Last updated: {now}",
            "",
        ]

        # Current task section
        lines.append("## Current Task")
        lines.append("")

        active_tasks = state["session_context"]["active_tasks"]
        if active_tasks:
            for task in active_tasks[:3]:  # Show top 3 tasks
                lines.append(f"- {task}")
        else:
            lines.append("(No active task)")
        lines.append("")

        # Recent context section
        lines.append("## Recent Context")
        lines.append("")

        last_impl = state["workflow_state"]["last_implement"]
        if last_impl.get("feature"):
            lines.append(f"- Last /implement: {last_impl['feature']}")
            if last_impl.get("completed_at"):
                lines.append(f"- Completed: {last_impl['completed_at']}")
            if last_impl.get("agents_completed"):
                lines.append(f"- Agents: {', '.join(last_impl['agents_completed'])}")
        else:
            lines.append("- No recent /implement completion")

        recent_files = state["workflow_state"]["recent_files"]
        if recent_files:
            lines.append(f"- Recent files: {len(recent_files)} modified")
            for f in recent_files[:5]:
                lines.append(f"  - {f}")
        lines.append("")

        # Conventions section
        conventions = state["session_context"]["key_conventions"]
        if conventions:
            lines.append("## Key Conventions")
            lines.append("")
            for conv in conventions[:5]:
                lines.append(f"- {conv}")
            lines.append("")

        # Resume instructions
        lines.append("## Resume Instructions")
        lines.append("")
        lines.append("1. Read `.claude/local/SESSION_STATE.json` for full context")
        lines.append("2. Check active tasks and their next steps")
        lines.append("3. Continue with pending work or ask what's next")
        lines.append("")

        content = "\n".join(lines)

        # Write to ACTIVE_WORK.md
        active_work_path = self.state_file.parent / "ACTIVE_WORK.md"
        try:
            active_work_path.write_text(content)
            audit_log("session_state_active_work", "success", {
                "path": str(active_work_path),
            })
        except (OSError, IOError) as e:
            # Non-critical - log but don't raise
            audit_log("session_state_active_work", "warning", {
                "error": str(e),
                "path": str(active_work_path),
            })
