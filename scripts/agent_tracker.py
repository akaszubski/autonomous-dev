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
from typing import List, Optional


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
