#!/usr/bin/env python3
"""
Agent Tracker Display - Formatting and visualization

This module provides display formatting methods for agent status visualization.

Date: 2025-12-25
Issue: GitHub #165 - Refactor agent_tracker.py into package
"""

from typing import Dict, Any, TYPE_CHECKING

# Use TYPE_CHECKING to avoid circular imports
if TYPE_CHECKING:
    from .tracker import AgentTracker

# Import models for AGENT_METADATA and EXPECTED_AGENTS
from .models import AGENT_METADATA, EXPECTED_AGENTS


class DisplayFormatter:
    """Formats agent data for display and visualization."""

    def __init__(self, tracker: 'AgentTracker'):
        """Initialize DisplayFormatter with reference to AgentTracker.

        Args:
            tracker: Reference to parent AgentTracker instance
        """
        self.tracker = tracker

    def get_agent_emoji(self, status: str) -> str:
        """Get emoji for agent status."""
        emoji_map = {
            "started": "🔄",
            "completed": "✅",
            "failed": "❌",
            "pending": "⏳"
        }
        return emoji_map.get(status, "❓")

    def get_agent_color(self, status: str) -> str:
        """Get color name for agent status."""
        color_map = {
            "started": "yellow",
            "completed": "green",
            "failed": "red",
            "pending": "gray"
        }
        return color_map.get(status, "white")

    def format_agent_name(self, agent_name: str) -> str:
        """Format agent name for display (e.g., test-master -> Test Master)."""
        return " ".join(word.capitalize() for word in agent_name.split("-"))

    def get_display_metadata(self) -> Dict[str, Any]:
        """Get comprehensive metadata for display purposes.

        Returns dictionary with:
        - session_id: Unique session identifier
        - started: Session start timestamp
        - github_issue: Linked GitHub issue (if any)
        - progress_percent: Overall progress (0-100)
        - agents_completed: Count of completed agents
        - agents_total: Total expected agents
        - running_agent: Currently running agent (if any)
        - pending_agents: List of pending agents
        - average_duration: Average agent duration in seconds
        - estimated_remaining: Estimated remaining time in seconds
        """
        return {
            "session_id": self.tracker.session_data.get("session_id"),
            "started": self.tracker.session_data.get("started"),
            "github_issue": self.tracker.session_data.get("github_issue"),
            "progress_percent": self.tracker._metrics.calculate_progress(),
            "agents_completed": sum(
                1 for e in self.tracker.session_data["agents"]
                if e.get("status") == "completed"
            ),
            "agents_total": len(EXPECTED_AGENTS),
            "running_agent": self.tracker._metrics.get_running_agent(),
            "pending_agents": self.tracker._metrics.get_pending_agents(),
            "average_duration": self.tracker._metrics.get_average_agent_duration(),
            "estimated_remaining": self.tracker._metrics.estimate_remaining_time()
        }

    def get_tree_view_data(self) -> Dict[str, Any]:
        """Get data structured for tree view display.

        Returns dictionary with agents array, each containing:
        - name: Agent name
        - status: Current status (started/completed/failed/pending)
        - message: Status message
        - duration: Duration in seconds (if available)
        - tools_used: List of tools used (if available)
        - emoji: Status emoji
        - color: Status color
        """
        agents_data = []

        # First, add all tracked agents
        for entry in self.tracker.session_data["agents"]:
            agent_name = entry["agent"]
            metadata = AGENT_METADATA.get(agent_name, {})

            agents_data.append({
                "name": agent_name,
                "display_name": self.format_agent_name(agent_name),
                "status": entry.get("status", "unknown"),
                "message": entry.get("message", ""),
                "duration": entry.get("duration_seconds"),
                "tools_used": entry.get("tools_used", []),
                "emoji": self.get_agent_emoji(entry.get("status", "unknown")),
                "color": self.get_agent_color(entry.get("status", "unknown")),
                "description": metadata.get("description", ""),
                "agent_emoji": metadata.get("emoji", "")
            })

        # Then add pending agents
        for agent_name in self.tracker._metrics.get_pending_agents():
            metadata = AGENT_METADATA.get(agent_name, {})

            agents_data.append({
                "name": agent_name,
                "display_name": self.format_agent_name(agent_name),
                "status": "pending",
                "message": "Not started yet",
                "duration": None,
                "tools_used": [],
                "emoji": self.get_agent_emoji("pending"),
                "color": self.get_agent_color("pending"),
                "description": metadata.get("description", ""),
                "agent_emoji": metadata.get("emoji", "")
            })

        return {
            "session": self.get_display_metadata(),
            "agents": agents_data
        }

    def show_status(self):
        """Show pipeline status"""
        print(f"\n📊 Agent Pipeline Status ({self.tracker.session_data['session_id']})\n")
        print("=" * 60)

        # Show linked GitHub issue if present
        if self.tracker.session_data.get("github_issue"):
            print(f"🔗 GitHub Issue: #{self.tracker.session_data['github_issue']}\n")

        # Show progress
        progress = self.tracker._metrics.calculate_progress()
        print(f"Progress: {progress}% complete\n")

        # Show agents
        for agent in EXPECTED_AGENTS:
            # Find agent's entry
            entry = None
            for e in self.tracker.session_data["agents"]:
                if e["agent"] == agent:
                    entry = e
                    break

            if entry:
                status = entry.get("status", "unknown")
                message = entry.get("message", "")
                emoji = self.get_agent_emoji(status)

                # Show duration if available
                duration_str = ""
                if "duration_seconds" in entry:
                    duration = entry["duration_seconds"]
                    duration_str = f" ({duration}s)"

                print(f"{emoji} {agent}: {status}{duration_str}")
                if message:
                    print(f"   └─ {message}")

                # Show tools if available
                if "tools_used" in entry:
                    tools = entry["tools_used"]
                    print(f"   └─ Tools: {', '.join(tools)}")
            else:
                print(f"⏳ {agent}: pending")

        print("\n" + "=" * 60)

        # Show time estimates
        avg_duration = self.tracker._metrics.get_average_agent_duration()
        if avg_duration:
            print(f"⏱️  Average agent duration: {avg_duration}s")

        remaining_time = self.tracker._metrics.estimate_remaining_time()
        if remaining_time:
            print(f"⏱️  Estimated remaining time: {remaining_time}s")

        print()


# Export public symbols
__all__ = ["DisplayFormatter"]
