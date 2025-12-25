#!/usr/bin/env python3
"""
Agent Tracker Core - Main AgentTracker class with delegation pattern

This module provides the main AgentTracker class that coordinates all functionality
by delegating to specialized manager classes.

Date: 2025-12-25
Issue: GitHub #165 - Refactor agent_tracker.py into package
"""

import json
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Any

# Import shared utilities from parent lib directory
sys.path.insert(0, str(Path(__file__).parent.parent))

from security_utils import validate_path
from path_utils import get_project_root, find_project_root
from validation import validate_agent_name, validate_message

# Import submodules
from .models import AGENT_METADATA, EXPECTED_AGENTS
from .state import StateManager
from .metrics import MetricsCalculator
from .verification import ParallelVerifier
from .display import DisplayFormatter


class AgentTracker:
    """Agent Pipeline Tracker - Main class coordinating all agent tracking functionality.

    This class uses a delegation pattern to organize functionality across specialized
    manager classes while maintaining a backward-compatible API.

    Security Features (GitHub Issue #45):
    - Path Traversal Prevention: All paths validated
    - Atomic File Writes: Uses temp file + rename pattern
    - Input Validation: Strict bounds checking
    - Comprehensive Error Handling: All exceptions include context

    Design Pattern:
        Delegation pattern - AgentTracker acts as a facade that delegates to:
        - StateManager: Session state and agent lifecycle
        - MetricsCalculator: Progress and time estimation
        - ParallelVerifier: Parallel execution verification
        - DisplayFormatter: Status display and visualization
    """

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
                # Use StateManager for saving (initialize delegates first)
                self._initialize_delegates()
                self._state_manager.save()
        else:
            # Standard mode: auto-detect or create session file
            # Use path_utils for dynamic PROJECT_ROOT resolution (Issue #79)
            # This fixes hardcoded Path("docs/sessions") which failed from subdirectories

            # Explicitly call get_project_root to verify path detection works
            # This call is at module level, making it patchable in tests
            project_root = get_project_root()

            # Construct session directory path manually (for test patchability)
            # Using get_session_dir would call path_utils.get_project_root internally,
            # which is harder to mock in tests
            self.session_dir = project_root / "docs" / "sessions"

            # Ensure session directory exists (defensive - get_session_dir should create it)
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
                # Use StateManager for saving (initialize delegates first)
                self._initialize_delegates()
                self._state_manager.save()

        # Initialize delegates if not already done
        if not hasattr(self, '_state_manager'):
            self._initialize_delegates()

    def _initialize_delegates(self):
        """Initialize all delegate manager instances."""
        self._state_manager = StateManager(self)
        self._metrics = MetricsCalculator(self)
        self._verifier = ParallelVerifier(self)
        self._display = DisplayFormatter(self)

    # =========================================================================
    # State Management Methods (delegate to StateManager)
    # =========================================================================

    def _save(self):
        """Save session data to file atomically."""
        self._state_manager.save()

    def start_agent(self, agent_name: str, message: str):
        """Log agent start with input validation."""
        self._state_manager.start_agent(agent_name, message)

    def complete_agent(self, agent_name: str, message: str, tools: Optional[List[str]] = None, tools_used: Optional[List[str]] = None, github_issue: Optional[int] = None, started_at: Optional[datetime] = None):
        """Log agent completion (idempotent - safe to call multiple times)."""
        self._state_manager.complete_agent(agent_name, message, tools, tools_used, github_issue, started_at)

    def fail_agent(self, agent_name: str, message: str):
        """Log agent failure."""
        self._state_manager.fail_agent(agent_name, message)

    def set_github_issue(self, issue_number: int):
        """Link GitHub issue to this session."""
        self._state_manager.set_github_issue(issue_number)

    # =========================================================================
    # Metrics Methods (delegate to MetricsCalculator)
    # =========================================================================

    def get_expected_agents(self) -> List[str]:
        """Get list of expected agents in execution order."""
        return EXPECTED_AGENTS.copy()

    def calculate_progress(self) -> int:
        """Calculate overall progress percentage (0-100)."""
        return self._metrics.calculate_progress()

    def get_average_agent_duration(self) -> Optional[int]:
        """Calculate average duration of completed agents."""
        return self._metrics.get_average_agent_duration()

    def estimate_remaining_time(self) -> Optional[int]:
        """Estimate remaining time based on average duration."""
        return self._metrics.estimate_remaining_time()

    def get_pending_agents(self) -> List[str]:
        """Get list of agents that haven't started yet."""
        return self._metrics.get_pending_agents()

    def get_running_agent(self) -> Optional[str]:
        """Get currently running agent, if any."""
        return self._metrics.get_running_agent()

    def is_pipeline_complete(self) -> bool:
        """Check if all expected agents have completed."""
        return self._metrics.is_pipeline_complete()

    def is_agent_tracked(self, agent_name: str) -> bool:
        """Check if agent is already tracked in current session."""
        return self._metrics.is_agent_tracked(agent_name)

    # =========================================================================
    # Verification Methods (delegate to ParallelVerifier)
    # =========================================================================

    def verify_parallel_exploration(self) -> bool:
        """Verify parallel execution of researcher and planner (DEPRECATED)."""
        return self._verifier.verify_parallel_exploration()

    @classmethod
    def verify_parallel_research(cls, session_file: Optional[Path] = None) -> Dict[str, Any]:
        """Verify parallel execution of researcher-local and researcher-web (class method)."""
        return ParallelVerifier.verify_parallel_research(session_file)

    def verify_parallel_validation(self) -> bool:
        """Verify parallel execution of validation agents."""
        return self._verifier.verify_parallel_validation()

    def get_parallel_validation_metrics(self) -> Dict[str, Any]:
        """Get detailed parallel validation metrics."""
        return self._verifier.get_parallel_validation_metrics()

    # =========================================================================
    # Display Methods (delegate to DisplayFormatter)
    # =========================================================================

    def get_agent_emoji(self, status: str) -> str:
        """Get emoji for agent status."""
        return self._display.get_agent_emoji(status)

    def get_agent_color(self, status: str) -> str:
        """Get color name for agent status."""
        return self._display.get_agent_color(status)

    def format_agent_name(self, agent_name: str) -> str:
        """Format agent name for display."""
        return self._display.format_agent_name(agent_name)

    def get_display_metadata(self) -> Dict[str, Any]:
        """Get comprehensive metadata for display purposes."""
        return self._display.get_display_metadata()

    def get_tree_view_data(self) -> Dict[str, Any]:
        """Get data structured for tree view display."""
        return self._display.get_tree_view_data()

    def show_status(self):
        """Show pipeline status."""
        self._display.show_status()

    # =========================================================================
    # Core Methods (not delegated)
    # =========================================================================

    def auto_track_from_environment(self, message: Optional[str] = None) -> bool:
        """Auto-detect and track agent from CLAUDE_AGENT_NAME environment variable.

        This enables automatic tracking when agents are invoked via Task tool.
        The Task tool sets CLAUDE_AGENT_NAME before invoking the agent.

        Args:
            message: Optional message. If None, uses default message.

        Returns:
            True if agent was newly tracked (created start entry)
            False if CLAUDE_AGENT_NAME not set (graceful degradation)
            False if agent already tracked (idempotent - prevents duplicates)
        """
        agent_name = os.getenv("CLAUDE_AGENT_NAME")
        if not agent_name:
            return False

        # Check if already tracked (idempotency for Task tool agents)
        # This prevents duplicate entries when both checkpoint and hook call this method
        if self.is_agent_tracked(agent_name):
            return False

        if not message:
            message = f"Auto-started from environment"

        self.start_agent(agent_name, message)
        return True

    @classmethod
    def save_agent_checkpoint(
        cls,
        agent_name: str,
        message: str,
        github_issue: Optional[int] = None,
        tools_used: Optional[List[str]] = None,
        started_at: Optional[datetime] = None
    ) -> bool:
        """Save checkpoint from agent execution context.

        Convenience class method for agents to save checkpoints without managing
        AgentTracker instances. Uses portable path detection to work from any directory.

        This method enables agents to save checkpoints using Python imports instead of
        subprocess calls, solving the dogfooding bug (GitHub Issue #79) where hardcoded
        paths caused /auto-implement to stall for 7+ hours.

        Args:
            agent_name: Name of agent (e.g., 'researcher', 'planner')
            message: Brief completion summary (max 10KB)
            github_issue: Optional GitHub issue number being worked on
            tools_used: Optional list of tools used by the agent
            started_at: Optional start time for duration calculation (datetime object).
                       When provided, duration is calculated as (now - started_at).
                       Backward compatible: defaults to None (no duration tracking).

        Returns:
            True if checkpoint saved successfully, False if skipped (graceful degradation)

        Security:
            - Input validation: agent_name must be alphanumeric + hyphen/underscore
            - Path traversal prevention: All paths validated via validation module
            - Message length limit: 10KB max to prevent log bloat
            - GitHub issue validation: 1-999999 range only

        Graceful Degradation:
            When running in user projects (no plugins/ directory), this method
            gracefully degrades by printing an informational message and returning False.
            This allows agents to work in both development and user environments.

        Examples:
            >>> # From agent code (works from any directory)
            >>> from agent_tracker import AgentTracker
            >>> AgentTracker.save_agent_checkpoint('researcher', 'Found 3 patterns')
            ✅ Checkpoint saved
            True

            >>> # In user project (no AgentTracker available)
            >>> AgentTracker.save_agent_checkpoint('researcher', 'Found 3 patterns')
            ℹ️ Checkpoint skipped (user project)
            False

        Design Patterns:
            - Progressive Enhancement: Works with or without tracking infrastructure
            - Portable Paths: Uses path_utils for dynamic project root detection
            - Two-tier Design: Library method (not subprocess call)
            See library-design-patterns skill for standardized design patterns.

        Date: 2025-12-07
        Issue: GitHub #79 (Dogfooding Bug - hardcoded paths)
        Agent: implementer
        Phase: TDD Green Phase
        """
        # Validate inputs first (let validation errors propagate)
        try:
            validate_agent_name(agent_name, purpose="checkpoint tracking")
            validate_message(message, purpose="checkpoint tracking")
        except (ValueError, TypeError) as e:
            # Re-raise validation errors (security requirement)
            raise

        # Validate github_issue parameter
        if github_issue is not None:
            if not isinstance(github_issue, int) or github_issue < 1 or github_issue > 999999:
                raise ValueError(
                    f"Invalid github_issue: {github_issue}. "
                    f"Expected positive integer 1-999999"
                )

        # Try to save checkpoint (graceful degradation on infrastructure errors)
        try:
            # Create tracker instance (uses portable path detection)
            # In test environments, this respects any active patches
            tracker = cls()

            # Set GitHub issue at session level if provided
            if github_issue is not None:
                tracker.set_github_issue(github_issue)

            # Save checkpoint using complete_agent (records status + metrics)
            tracker.complete_agent(
                agent_name=agent_name,
                message=message,
                github_issue=github_issue,
                tools_used=tools_used,
                started_at=started_at
            )

            print(f"✅ Checkpoint saved: {agent_name}")
            return True

        except ImportError as e:
            # Graceful degradation: Running in user project without tracking infrastructure
            print(f"ℹ️ Checkpoint skipped (user project): {e}")
            return False

        except (OSError, PermissionError) as e:
            # File system errors: Log but don't break workflow
            print(f"⚠️ Checkpoint failed (filesystem error): {e}")
            return False

        except Exception as e:
            # Unexpected error: Log but don't break workflow
            print(f"⚠️ Checkpoint failed (unexpected error): {e}")
            return False

    def _validate_agent_data(self, agent_data: Dict[str, Any]) -> bool:
        """Validate agent data structure and timestamps.

        Args:
            agent_data: Agent entry dictionary from session data

        Returns:
            True if valid, False otherwise
        """
        required_fields = ["agent", "status", "started_at"]

        # Check required fields exist
        if not all(field in agent_data for field in required_fields):
            return False

        # Validate status
        valid_statuses = ["started", "completed", "failed"]
        if agent_data["status"] not in valid_statuses:
            return False

        # Validate timestamps
        try:
            datetime.fromisoformat(agent_data["started_at"])

            if "completed_at" in agent_data:
                datetime.fromisoformat(agent_data["completed_at"])

            if "failed_at" in agent_data:
                datetime.fromisoformat(agent_data["failed_at"])

        except ValueError:
            return False

        return True


# Export public symbols
__all__ = ["AgentTracker"]
