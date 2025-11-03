#!/usr/bin/env python3
"""
Agent Pipeline Tracker - Structured logging for agent invocations

Tracks which agents ran, when, and their status to enable:
- Pipeline verification (were all expected agents invoked?)
- Debugging (what happened during execution?)
- Metrics (agent usage patterns, timing)
- Compliance (proof that SDLC steps were followed)

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
import sys
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


class AgentTracker:
    def __init__(self):
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
        """Save session data to file"""
        self.session_file.write_text(json.dumps(self.session_data, indent=2))

    def start_agent(self, agent_name: str, message: str):
        """Log agent start"""
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
        """Log agent completion"""
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
        """Log agent failure"""
        # Find the most recent entry for this agent
        for entry in reversed(self.session_data["agents"]):
            if entry["agent"] == agent_name and entry["status"] == "started":
                entry["status"] = "failed"
                entry["failed_at"] = datetime.now().isoformat()
                entry["error"] = message

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
            "error": message
        }
        self.session_data["agents"].append(entry)
        self._save()

        print(f"❌ Failed: {agent_name} - {message}")
        print(f"📄 Session: {self.session_file.name}")

    def set_github_issue(self, issue_number: int):
        """Link GitHub issue to this session."""
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
        issue_number = int(sys.argv[2])
        tracker.set_github_issue(issue_number)

    elif command == "status":
        tracker.show_status()

    else:
        print(f"Unknown command: {command}")
        print("Valid commands: start, complete, fail, set-github-issue, status")
        sys.exit(1)


if __name__ == "__main__":
    main()
