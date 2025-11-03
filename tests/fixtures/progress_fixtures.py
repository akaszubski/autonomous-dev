#!/usr/bin/env python3
"""
Shared fixtures and helper functions for progress indicator tests

This module provides reusable test data and utilities for testing
the progress indicator system.

Usage:
    from tests.fixtures.progress_fixtures import (
        create_mock_pipeline_state,
        create_agent_entry,
        simulate_agent_completion
    )
"""

import json
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional


# ========================================
# MOCK DATA GENERATORS
# ========================================

def create_mock_pipeline_state(
    session_id: str = "20251104-120000",
    github_issue: Optional[int] = None,
    agents: Optional[List[Dict]] = None
) -> Dict:
    """
    Create mock pipeline state for testing.

    Args:
        session_id: Session identifier
        github_issue: Optional GitHub issue number
        agents: List of agent entries (or None for empty)

    Returns:
        Dictionary with pipeline state
    """
    return {
        "session_id": session_id,
        "started": datetime.now().isoformat(),
        "github_issue": github_issue,
        "agents": agents or []
    }


def create_agent_entry(
    agent_name: str,
    status: str = "completed",
    message: str = "Task completed",
    duration: int = 100,
    tools: Optional[List[str]] = None,
    error: Optional[str] = None
) -> Dict:
    """
    Create mock agent entry for testing.

    Args:
        agent_name: Name of the agent
        status: Agent status (started, completed, failed)
        message: Status message
        duration: Duration in seconds
        tools: Optional list of tools used
        error: Optional error message (for failed status)

    Returns:
        Dictionary with agent entry data
    """
    now = datetime.now()
    started = now - timedelta(seconds=duration)

    entry = {
        "agent": agent_name,
        "status": status,
    }

    if status == "started":
        entry.update({
            "started_at": started.isoformat(),
            "message": message
        })

    elif status == "completed":
        entry.update({
            "started_at": started.isoformat(),
            "completed_at": now.isoformat(),
            "duration_seconds": duration,
            "message": message
        })
        if tools:
            entry["tools_used"] = tools

    elif status == "failed":
        entry.update({
            "started_at": started.isoformat(),
            "failed_at": now.isoformat(),
            "duration_seconds": duration,
            "error": error or message
        })

    return entry


def create_complete_pipeline(github_issue: Optional[int] = None) -> Dict:
    """
    Create mock pipeline with all agents completed.

    Args:
        github_issue: Optional GitHub issue number

    Returns:
        Complete pipeline state
    """
    agents = [
        create_agent_entry("researcher", message="Found 5 patterns", duration=295, tools=["WebSearch", "Grep"]),
        create_agent_entry("planner", message="Architecture plan created", duration=200),
        create_agent_entry("test-master", message="Wrote 25 tests", duration=180),
        create_agent_entry("implementer", message="Implementation complete", duration=450),
        create_agent_entry("reviewer", message="Code review passed", duration=120),
        create_agent_entry("security-auditor", message="No vulnerabilities", duration=90),
        create_agent_entry("doc-master", message="Documentation updated", duration=75)
    ]

    return create_mock_pipeline_state(
        github_issue=github_issue,
        agents=agents
    )


def create_partial_pipeline(completed_agents: int = 3) -> Dict:
    """
    Create mock pipeline with some agents completed.

    Args:
        completed_agents: Number of agents to mark as completed (1-7)

    Returns:
        Partial pipeline state
    """
    all_agents = [
        "researcher", "planner", "test-master", "implementer",
        "reviewer", "security-auditor", "doc-master"
    ]

    agents = []
    for i, agent_name in enumerate(all_agents[:completed_agents]):
        agents.append(create_agent_entry(
            agent_name,
            message=f"{agent_name} completed",
            duration=100 + i * 20
        ))

    # Add one running agent if not all completed
    if completed_agents < len(all_agents):
        agents.append(create_agent_entry(
            all_agents[completed_agents],
            status="started",
            message="In progress",
            duration=0
        ))

    return create_mock_pipeline_state(agents=agents)


def create_failed_pipeline(failed_agent: str = "planner", failure_message: str = "Planning failed") -> Dict:
    """
    Create mock pipeline with a failed agent.

    Args:
        failed_agent: Name of agent that failed
        failure_message: Failure error message

    Returns:
        Pipeline state with failure
    """
    agents = [
        create_agent_entry("researcher", message="Research completed", duration=295),
        create_agent_entry(failed_agent, status="failed", error=failure_message, duration=100)
    ]

    return create_mock_pipeline_state(agents=agents)


# ========================================
# FILE HELPERS
# ========================================

def write_pipeline_state(session_file: Path, state: Dict) -> None:
    """
    Write pipeline state to session file.

    Args:
        session_file: Path to session file
        state: Pipeline state dictionary
    """
    session_file.write_text(json.dumps(state, indent=2))


def read_pipeline_state(session_file: Path) -> Dict:
    """
    Read pipeline state from session file.

    Args:
        session_file: Path to session file

    Returns:
        Pipeline state dictionary
    """
    return json.loads(session_file.read_text())


def update_agent_status(
    session_file: Path,
    agent_name: str,
    status: str,
    message: str = "",
    duration: int = 100
) -> None:
    """
    Update agent status in session file.

    Args:
        session_file: Path to session file
        agent_name: Name of agent to update
        status: New status (started, completed, failed)
        message: Status message
        duration: Duration in seconds
    """
    state = read_pipeline_state(session_file)

    # Find and update agent, or add new entry
    found = False
    for agent in state["agents"]:
        if agent["agent"] == agent_name:
            agent["status"] = status
            if status == "completed":
                agent["completed_at"] = datetime.now().isoformat()
                agent["duration_seconds"] = duration
                agent["message"] = message
            elif status == "failed":
                agent["failed_at"] = datetime.now().isoformat()
                agent["error"] = message
            found = True
            break

    if not found:
        state["agents"].append(
            create_agent_entry(agent_name, status, message, duration)
        )

    write_pipeline_state(session_file, state)


# ========================================
# SIMULATION HELPERS
# ========================================

def simulate_agent_completion(
    session_file: Path,
    agent_name: str,
    message: str = "Completed",
    duration: int = 100,
    tools: Optional[List[str]] = None
) -> None:
    """
    Simulate agent completing work.

    Args:
        session_file: Path to session file
        agent_name: Name of agent
        message: Completion message
        duration: Duration in seconds
        tools: Optional tools used
    """
    state = read_pipeline_state(session_file)

    agent_entry = create_agent_entry(
        agent_name,
        status="completed",
        message=message,
        duration=duration,
        tools=tools
    )

    state["agents"].append(agent_entry)
    write_pipeline_state(session_file, state)


def simulate_agent_failure(
    session_file: Path,
    agent_name: str,
    error: str = "Agent failed",
    duration: int = 50
) -> None:
    """
    Simulate agent failing.

    Args:
        session_file: Path to session file
        agent_name: Name of agent
        error: Error message
        duration: Duration before failure
    """
    state = read_pipeline_state(session_file)

    agent_entry = create_agent_entry(
        agent_name,
        status="failed",
        error=error,
        duration=duration
    )

    state["agents"].append(agent_entry)
    write_pipeline_state(session_file, state)


def simulate_full_pipeline(
    session_file: Path,
    include_failure: bool = False,
    failed_agent: str = "planner"
) -> None:
    """
    Simulate complete pipeline execution.

    Args:
        session_file: Path to session file
        include_failure: Whether to include a failed agent
        failed_agent: Which agent should fail (if include_failure=True)
    """
    agents = [
        "researcher", "planner", "test-master", "implementer",
        "reviewer", "security-auditor", "doc-master"
    ]

    state = read_pipeline_state(session_file)

    for agent in agents:
        if include_failure and agent == failed_agent:
            agent_entry = create_agent_entry(
                agent,
                status="failed",
                error=f"{agent} encountered error",
                duration=100
            )
        else:
            agent_entry = create_agent_entry(
                agent,
                message=f"{agent} completed successfully",
                duration=100
            )

        state["agents"].append(agent_entry)

    write_pipeline_state(session_file, state)


# ========================================
# ASSERTION HELPERS
# ========================================

def assert_agent_status(state: Dict, agent_name: str, expected_status: str) -> None:
    """
    Assert that agent has expected status.

    Args:
        state: Pipeline state
        agent_name: Agent to check
        expected_status: Expected status

    Raises:
        AssertionError: If status doesn't match
    """
    for agent in state["agents"]:
        if agent["agent"] == agent_name:
            assert agent["status"] == expected_status, \
                f"Agent {agent_name} has status {agent['status']}, expected {expected_status}"
            return

    raise AssertionError(f"Agent {agent_name} not found in state")


def assert_pipeline_complete(state: Dict) -> None:
    """
    Assert that pipeline is complete (all 7 agents completed).

    Args:
        state: Pipeline state

    Raises:
        AssertionError: If pipeline is not complete
    """
    required_agents = {
        "researcher", "planner", "test-master", "implementer",
        "reviewer", "security-auditor", "doc-master"
    }

    completed_agents = {
        agent["agent"] for agent in state["agents"]
        if agent["status"] == "completed"
    }

    assert required_agents.issubset(completed_agents), \
        f"Missing agents: {required_agents - completed_agents}"


def assert_no_failures(state: Dict) -> None:
    """
    Assert that no agents have failed.

    Args:
        state: Pipeline state

    Raises:
        AssertionError: If any agent failed
    """
    failed = [
        agent["agent"] for agent in state["agents"]
        if agent["status"] == "failed"
    ]

    assert len(failed) == 0, f"Failed agents: {failed}"


def get_agent_count_by_status(state: Dict) -> Dict[str, int]:
    """
    Get count of agents by status.

    Args:
        state: Pipeline state

    Returns:
        Dictionary with counts per status
    """
    counts = {"started": 0, "completed": 0, "failed": 0}

    for agent in state["agents"]:
        status = agent.get("status", "unknown")
        if status in counts:
            counts[status] += 1

    return counts


def get_total_duration(state: Dict) -> int:
    """
    Get total duration of all agents.

    Args:
        state: Pipeline state

    Returns:
        Total duration in seconds
    """
    total = 0
    for agent in state["agents"]:
        total += agent.get("duration_seconds", 0)
    return total


# ========================================
# EXPECTED VALUES
# ========================================

# Standard agent execution order
EXPECTED_AGENT_ORDER = [
    "researcher",
    "planner",
    "test-master",
    "implementer",
    "reviewer",
    "security-auditor",
    "doc-master"
]

# Expected agent count for complete pipeline
EXPECTED_AGENT_COUNT = 7

# Status emojis used in display
STATUS_EMOJIS = {
    "completed": "✅",
    "started": "⏳",
    "failed": "❌",
    "pending": "⏸️"
}

# Minimum durations (in seconds) for performance tests
MIN_DURATIONS = {
    "render": 1.0,  # Max time to render display
    "poll": 0.05,   # Min polling interval
    "startup": 2.0  # Max time to start display process
}
