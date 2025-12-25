#!/usr/bin/env python3
"""
Agent Tracker CLI - Command-line interface

This module provides the CLI interface for the agent_tracker package.

Date: 2025-12-25
Issue: GitHub #165 - Refactor agent_tracker.py into package
"""

import sys
from typing import NoReturn


def main() -> NoReturn:
    """CLI interface for agent tracker.

    This function provides the command-line interface for the AgentTracker library.
    It should be called from wrapper scripts, not directly.

    Usage:
        python -m agent_tracker start <agent_name> <message>
        python -m agent_tracker complete <agent_name> <message> [--tools tool1,tool2]
        python -m agent_tracker fail <agent_name> <message>
        python -m agent_tracker status
    """
    # Import here to avoid circular imports at module level
    from .tracker import AgentTracker

    if len(sys.argv) < 2:
        print("Usage:")
        print("  agent_tracker.py start <agent_name> <message>")
        print("  agent_tracker.py complete <agent_name> <message> [--tools tool1,tool2]")
        print("  agent_tracker.py fail <agent_name> <message>")
        print("  agent_tracker.py status")
        print("\nExamples:")
        print('  agent_tracker.py start researcher "Researching JWT patterns"')
        print('  agent_tracker.py complete researcher "Found 3 patterns" --tools WebSearch,Grep')
        print('  agent_tracker.py fail researcher "No patterns found"')
        print('  agent_tracker.py status')
        sys.exit(1)

    command = sys.argv[1]
    tracker = AgentTracker()

    if command == "start":
        if len(sys.argv) < 4:
            print("Error: start requires <agent_name> <message>")
            sys.exit(1)
        agent_name = sys.argv[2]
        message = " ".join(sys.argv[3:])
        tracker.start_agent(agent_name, message)

    elif command == "complete":
        if len(sys.argv) < 4:
            print("Error: complete requires <agent_name> <message>")
            sys.exit(1)

        agent_name = sys.argv[2]

        # Parse --tools flag if present
        tools = None
        message_parts = []
        i = 3
        while i < len(sys.argv):
            if sys.argv[i] == "--tools":
                if i + 1 < len(sys.argv):
                    tools = sys.argv[i + 1].split(",")
                    i += 2
                else:
                    print("Error: --tools requires a value")
                    sys.exit(1)
            else:
                message_parts.append(sys.argv[i])
                i += 1

        message = " ".join(message_parts)
        tracker.complete_agent(agent_name, message, tools=tools)

    elif command == "fail":
        if len(sys.argv) < 4:
            print("Error: fail requires <agent_name> <message>")
            sys.exit(1)
        agent_name = sys.argv[2]
        message = " ".join(sys.argv[3:])
        tracker.fail_agent(agent_name, message)

    elif command == "status":
        tracker.show_status()

    else:
        print(f"Error: Unknown command '{command}'")
        print("Valid commands: start, complete, fail, status")
        sys.exit(1)


# Export public symbols
__all__ = ["main"]
