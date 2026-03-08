#!/usr/bin/env python3
"""
Enforce Pipeline Order Hook - Prevents Skipping Steps in /implement

This PreToolUse hook intercepts Task tool calls and ensures that when running
/implement, agents are spawned in the correct order. Specifically, it BLOCKS
the implementer agent from running unless research, planner, and test-master
have already been invoked.

Problem this solves (Issue #246):
Claude sometimes skips the research → plan → test → implement pipeline and
jumps straight to the implementer agent. This hook enforces the order.

How it works:
1. Tracks Task tool calls with subagent_type in a session state file
2. When implementer is invoked, checks that prerequisites ran first
3. BLOCKS implementer if prerequisites are missing
4. Resets state when a new /implement session starts

Input (stdin):
{
  "tool_name": "Task",
  "tool_input": {
    "subagent_type": "implementer",
    "prompt": "...",
    ...
  }
}

Output (stdout):
{
  "hookSpecificOutput": {
    "hookEventName": "PreToolUse",
    "permissionDecision": "deny",  # or "allow"
    "permissionDecisionReason": "reason"
  }
}

Exit code: 0 (always - let Claude Code process the decision)

Environment Variables:
- ENFORCE_PIPELINE_ORDER: Enable enforcement (default: true)
- PIPELINE_STATE_FILE: Path to state file (default: /tmp/implement_pipeline_state.json)
"""

import json
import sys
import os
from pathlib import Path
from datetime import datetime
import fcntl

# Pipeline order: these must run BEFORE implementer
PREREQUISITE_AGENTS = [
    "researcher-local",
    "researcher-web",  # or general-purpose with web research
    "planner",
    "test-master",
]

# Agents that count as "web research" (general-purpose is used for web research)
WEB_RESEARCH_AGENTS = ["researcher-web", "general-purpose"]

# The agent we're protecting - can't run without prerequisites
PROTECTED_AGENT = "implementer"

# Minimum required prerequisites (must have at least these before implementer)
# We require: local research, web research, planner, test-master
MINIMUM_PREREQUISITES = {
    "local_research": False,   # researcher-local
    "web_research": False,     # researcher-web or general-purpose
    "planner": False,          # planner
    "test_master": False,      # test-master
}

# State file location
DEFAULT_STATE_FILE = "/tmp/implement_pipeline_state.json"


def get_state_file_path() -> Path:
    """Get the state file path from env or default."""
    return Path(os.environ.get("PIPELINE_STATE_FILE", DEFAULT_STATE_FILE))


def load_state() -> dict:
    """Load pipeline state from file with file locking."""
    state_file = get_state_file_path()

    if not state_file.exists():
        return {
            "session_start": None,
            "agents_invoked": [],
            "prerequisites_met": dict(MINIMUM_PREREQUISITES),
        }

    try:
        with open(state_file, "r") as f:
            fcntl.flock(f.fileno(), fcntl.LOCK_SH)
            try:
                return json.load(f)
            finally:
                fcntl.flock(f.fileno(), fcntl.LOCK_UN)
    except (json.JSONDecodeError, IOError):
        return {
            "session_start": None,
            "agents_invoked": [],
            "prerequisites_met": dict(MINIMUM_PREREQUISITES),
        }


def save_state(state: dict):
    """Save pipeline state to file with atomic write."""
    state_file = get_state_file_path()

    # Atomic write: write to temp file, then rename
    tmp_file = state_file.with_suffix(".tmp")

    try:
        with open(tmp_file, "w") as f:
            fcntl.flock(f.fileno(), fcntl.LOCK_EX)
            try:
                json.dump(state, f, indent=2)
            finally:
                fcntl.flock(f.fileno(), fcntl.LOCK_UN)

        tmp_file.rename(state_file)
    except IOError:
        pass


def reset_state():
    """Reset state for a new /implement session."""
    state = {
        "session_start": datetime.now().isoformat(),
        "agents_invoked": [],
        "prerequisites_met": dict(MINIMUM_PREREQUISITES),
    }
    save_state(state)
    return state


def record_agent_invocation(state: dict, agent_type: str) -> dict:
    """Record that an agent was invoked and update prerequisites."""
    if agent_type not in state["agents_invoked"]:
        state["agents_invoked"].append(agent_type)

    # Update prerequisites
    if agent_type == "researcher-local":
        state["prerequisites_met"]["local_research"] = True
    elif agent_type in WEB_RESEARCH_AGENTS:
        state["prerequisites_met"]["web_research"] = True
    elif agent_type == "planner":
        state["prerequisites_met"]["planner"] = True
    elif agent_type == "test-master":
        state["prerequisites_met"]["test_master"] = True

    save_state(state)
    return state


def check_prerequisites_met(state: dict) -> tuple:
    """
    Check if all prerequisites are met for implementer.

    Returns:
        (all_met: bool, missing: list[str])
    """
    prereqs = state.get("prerequisites_met", MINIMUM_PREREQUISITES)
    missing = []

    if not prereqs.get("local_research"):
        missing.append("researcher-local (codebase analysis)")
    if not prereqs.get("web_research"):
        missing.append("researcher-web (best practices research)")
    if not prereqs.get("planner"):
        missing.append("planner (implementation plan)")
    if not prereqs.get("test_master"):
        missing.append("test-master (TDD tests)")

    return len(missing) == 0, missing


def output_decision(decision: str, reason: str):
    """Output the hook decision in required format."""
    print(json.dumps({
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": decision,
            "permissionDecisionReason": reason
        }
    }))


def main():
    """Main entry point."""
    try:
        # Check if enforcement is enabled (default: true)
        enforce = os.environ.get("ENFORCE_PIPELINE_ORDER", "true").lower()
        if enforce == "false":
            output_decision("allow", "Pipeline order enforcement disabled")
            sys.exit(0)

        # Read input from stdin
        input_data = json.load(sys.stdin)
        tool_name = input_data.get("tool_name", "")
        tool_input = input_data.get("tool_input", {})

        # Only check Task tool calls
        if tool_name != "Task":
            output_decision("allow", f"Tool '{tool_name}' not subject to pipeline order enforcement")
            sys.exit(0)

        # Get the subagent type
        subagent_type = tool_input.get("subagent_type", "").lower()

        if not subagent_type:
            output_decision("allow", "No subagent_type specified, allowing")
            sys.exit(0)

        # Load current state
        state = load_state()

        # Check if this is a new session (state is old or empty)
        # A session is considered "new" if it's been more than 2 hours since last activity
        # or if there's no session_start
        session_start = state.get("session_start")
        if session_start:
            try:
                start_time = datetime.fromisoformat(session_start)
                hours_elapsed = (datetime.now() - start_time).total_seconds() / 3600
                if hours_elapsed > 2:
                    state = reset_state()
            except ValueError:
                state = reset_state()
        else:
            state = reset_state()

        # If this is a prerequisite agent, record it and allow
        if subagent_type in PREREQUISITE_AGENTS or subagent_type in WEB_RESEARCH_AGENTS:
            state = record_agent_invocation(state, subagent_type)
            output_decision("allow", f"Prerequisite agent '{subagent_type}' recorded and allowed")
            sys.exit(0)

        # If this is the implementer agent, check prerequisites
        if subagent_type == PROTECTED_AGENT:
            all_met, missing = check_prerequisites_met(state)

            if all_met:
                # All prerequisites met - allow implementer
                state = record_agent_invocation(state, subagent_type)
                output_decision("allow", "All prerequisites met, implementer allowed")
            else:
                # Prerequisites missing - BLOCK implementer
                missing_list = "\n".join(f"  - {m}" for m in missing)
                agents_so_far = ", ".join(state["agents_invoked"]) or "(none)"

                output_decision("deny", f"""
⛔ PIPELINE ORDER VIOLATION - IMPLEMENTER BLOCKED

You are attempting to invoke the implementer agent, but required prerequisite
agents have not been run yet.

MISSING PREREQUISITES:
{missing_list}

AGENTS INVOKED SO FAR: {agents_so_far}

REQUIRED PIPELINE ORDER:
1. researcher-local (codebase patterns)
2. researcher-web / general-purpose (web best practices)
3. planner (implementation plan)
4. test-master (TDD tests)
5. implementer (production code) ← YOU ARE HERE

⚠️ DO NOT SKIP STEPS. Go back and invoke the missing agents first.

This is enforced by the enforce_pipeline_order hook. The user expects all 8 agents
to run as part of /implement. Skipping steps is a bug.

To disable this enforcement (not recommended):
  export ENFORCE_PIPELINE_ORDER=false
""")
            sys.exit(0)

        # For other agents (reviewer, security-auditor, doc-master), just record and allow
        state = record_agent_invocation(state, subagent_type)
        output_decision("allow", f"Agent '{subagent_type}' recorded and allowed")

    except json.JSONDecodeError as e:
        output_decision("allow", f"Input parse error: {e}")
    except Exception as e:
        output_decision("allow", f"Hook error: {e}")

    sys.exit(0)


if __name__ == "__main__":
    main()
