#!/usr/bin/env python3
"""
Agent Tracker Metrics - Progress calculation and time estimation

This module provides metrics calculation for agent pipeline progress tracking.

Date: 2025-12-25
Issue: GitHub #165 - Refactor agent_tracker.py into package
"""

from typing import List, Optional, TYPE_CHECKING

# Use TYPE_CHECKING to avoid circular imports
if TYPE_CHECKING:
    from .tracker import AgentTracker

# Import models for EXPECTED_AGENTS
from .models import EXPECTED_AGENTS


class MetricsCalculator:
    """Calculates metrics for agent pipeline progress and timing."""

    def __init__(self, tracker: 'AgentTracker'):
        """Initialize MetricsCalculator with reference to AgentTracker.

        Args:
            tracker: Reference to parent AgentTracker instance
        """
        self.tracker = tracker

    def calculate_progress(self) -> int:
        """Calculate overall progress percentage (0-100).

        Returns:
            Progress percentage based on completed agents vs expected agents.
            Returns 0 if no agents expected, 100 if all completed.
        """
        if not EXPECTED_AGENTS:
            return 100

        completed = sum(
            1 for entry in self.tracker.session_data["agents"]
            if entry.get("status") == "completed"
        )

        return int((completed / len(EXPECTED_AGENTS)) * 100)

    def get_average_agent_duration(self) -> Optional[int]:
        """Calculate average duration of completed agents.

        Returns:
            Average duration in seconds, or None if no completed agents.
        """
        durations = [
            entry.get("duration_seconds", 0)
            for entry in self.tracker.session_data["agents"]
            if entry.get("status") == "completed" and "duration_seconds" in entry
        ]

        if not durations:
            return None

        return int(sum(durations) / len(durations))

    def estimate_remaining_time(self) -> Optional[int]:
        """Estimate remaining time in seconds based on average agent duration.

        Returns:
            Estimated remaining time in seconds, or None if cannot estimate.
        """
        avg_duration = self.get_average_agent_duration()
        if avg_duration is None:
            return None

        pending = len(self.get_pending_agents())
        return pending * avg_duration

    def get_pending_agents(self) -> List[str]:
        """Get list of agents that haven't started yet."""
        started_agents = {entry["agent"] for entry in self.tracker.session_data["agents"]}
        return [agent for agent in EXPECTED_AGENTS if agent not in started_agents]

    def get_running_agent(self) -> Optional[str]:
        """Get currently running agent, if any."""
        for entry in reversed(self.tracker.session_data["agents"]):
            if entry.get("status") == "started":
                return entry["agent"]
        return None

    def is_pipeline_complete(self) -> bool:
        """Check if all expected agents have completed."""
        completed_agents = {
            entry["agent"]
            for entry in self.tracker.session_data["agents"]
            if entry.get("status") == "completed"
        }
        return set(EXPECTED_AGENTS).issubset(completed_agents)

    def is_agent_tracked(self, agent_name: str) -> bool:
        """Check if agent is already tracked in current session (for duplicate detection).

        Args:
            agent_name: Name of the agent to check

        Returns:
            True if agent has any entry in session, False otherwise
        """
        return any(
            entry["agent"] == agent_name
            for entry in self.tracker.session_data["agents"]
        )


# Export public symbols
__all__ = ["MetricsCalculator"]
