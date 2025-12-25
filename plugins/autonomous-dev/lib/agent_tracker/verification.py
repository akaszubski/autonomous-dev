#!/usr/bin/env python3
"""
Agent Tracker Verification - Parallel execution verification

This module provides verification methods for parallel agent execution patterns.

Date: 2025-12-25
Issue: GitHub #165 - Refactor agent_tracker.py into package
"""

from datetime import datetime
from pathlib import Path
from typing import Dict, Any, Optional, TYPE_CHECKING

# Use TYPE_CHECKING to avoid circular imports
if TYPE_CHECKING:
    from .tracker import AgentTracker


class ParallelVerifier:
    """Verifies parallel execution patterns in agent pipeline."""

    def __init__(self, tracker: 'AgentTracker'):
        """Initialize ParallelVerifier with reference to AgentTracker.

        Args:
            tracker: Reference to parent AgentTracker instance
        """
        self.tracker = tracker

    def verify_parallel_exploration(self) -> bool:
        """Verify parallel execution of researcher and planner agents.

        DEPRECATED: Use verify_parallel_research() for new split-researcher workflow.

        Returns:
            True if researcher and planner executed in parallel (overlapping time windows),
            False otherwise.

        Design:
            This verifies the optimization in /auto-implement where researcher and planner
            run simultaneously via two Task tool calls in a single Claude response.
        """
        researcher_entry = None
        planner_entry = None

        for entry in self.tracker.session_data["agents"]:
            if entry["agent"] == "researcher":
                researcher_entry = entry
            elif entry["agent"] == "planner":
                planner_entry = entry

        if not researcher_entry or not planner_entry:
            return False

        # Check if both have start times
        if "started_at" not in researcher_entry or "started_at" not in planner_entry:
            return False

        # Parse timestamps
        try:
            researcher_start = datetime.fromisoformat(researcher_entry["started_at"])
            planner_start = datetime.fromisoformat(planner_entry["started_at"])

            # Check if start times are within 5 seconds of each other
            # (parallel execution means they start nearly simultaneously)
            time_diff = abs((researcher_start - planner_start).total_seconds())
            return time_diff <= 5

        except (ValueError, KeyError):
            return False

    @classmethod
    def verify_parallel_research(cls, session_file: Optional[Path] = None) -> Dict[str, Any]:
        """Verify parallel execution of researcher-local and researcher-web agents (class method).

        This is a convenience class method that allows verification without creating an instance first.
        Use this in checkpoints where you want to verify parallel research without tracking state.

        Args:
            session_file: Optional path to session file. If None, uses most recent session.

        Returns:
            Dict with verification results:
            {
                "parallel": bool,  # True if executed in parallel
                "found_agents": List[str],  # Names of agents found
                "time_difference": float,  # Seconds between start times (if found)
                "reason": str  # Explanation if verification failed
            }

        Design:
            This enables stateless verification from checkpoints in /auto-implement (Issue #128).
            Creates temporary tracker instance to read session file and check timestamps.
            This replaces verify_parallel_exploration for split-researcher workflow.
        """
        # Import here to avoid circular imports at module level
        from .tracker import AgentTracker

        # Create tracker instance (either with explicit session file or auto-detect)
        if session_file:
            tracker = AgentTracker(session_file=str(session_file))
        else:
            tracker = AgentTracker()

        # Find researcher entries
        local_entry = None
        web_entry = None
        for entry in tracker.session_data["agents"]:
            if entry["agent"] == "researcher-local":
                local_entry = entry
            elif entry["agent"] == "researcher-web":
                web_entry = entry

        found_agents = [
            entry["agent"] for entry in tracker.session_data["agents"]
            if entry["agent"] in ["researcher-local", "researcher-web"]
        ]

        result = {
            "parallel_execution": False,  # Default to False (renamed for test compatibility)
            "found_agents": found_agents
        }

        if not local_entry or not web_entry:
            result["reason"] = "Missing researcher agents"
            return result

        if "started_at" not in local_entry or "started_at" not in web_entry:
            result["reason"] = "Missing start times"
            return result

        # Parse timestamps and check if parallel
        try:
            local_start = datetime.fromisoformat(local_entry["started_at"])
            web_start = datetime.fromisoformat(web_entry["started_at"])
            time_diff = abs((local_start - web_start).total_seconds())

            result["time_difference"] = time_diff

            # Check if start times are within 90 seconds of each other
            # (parallel execution means they start within a reasonable window)
            # Note: Increased from 5s to 90s to account for sequential task spawning
            if time_diff <= 90:
                result["parallel_execution"] = True
            else:
                result["reason"] = f"Research agents not executed in parallel (time diff: {time_diff}s)"

        except (ValueError, KeyError) as e:
            result["reason"] = f"Timestamp parsing error: {e}"

        return result

    def verify_parallel_validation(self) -> bool:
        """Verify parallel execution of reviewer, security-auditor, and doc-master agents.

        Returns:
            True if all three validation agents executed in parallel (overlapping time windows),
            False otherwise.

        Design:
            This verifies the optimization in /auto-implement where reviewer, security-auditor,
            and doc-master run simultaneously via three Task tool calls in a single response.
        """
        reviewer_entry = None
        security_entry = None
        doc_entry = None

        for entry in self.tracker.session_data["agents"]:
            if entry["agent"] == "reviewer":
                reviewer_entry = entry
            elif entry["agent"] == "security-auditor":
                security_entry = entry
            elif entry["agent"] == "doc-master":
                doc_entry = entry

        if not all([reviewer_entry, security_entry, doc_entry]):
            return False

        # Check if all have start times
        if not all([
            "started_at" in reviewer_entry,
            "started_at" in security_entry,
            "started_at" in doc_entry
        ]):
            return False

        # Parse timestamps
        try:
            reviewer_start = datetime.fromisoformat(reviewer_entry["started_at"])
            security_start = datetime.fromisoformat(security_entry["started_at"])
            doc_start = datetime.fromisoformat(doc_entry["started_at"])

            # Check if all start times are within 10 seconds of each other
            # (parallel execution means they start nearly simultaneously)
            timestamps = [reviewer_start, security_start, doc_start]
            min_time = min(timestamps)
            max_time = max(timestamps)
            time_span = (max_time - min_time).total_seconds()

            return time_span <= 10

        except (ValueError, KeyError):
            return False

    def get_parallel_validation_metrics(self) -> Dict[str, Any]:
        """Get detailed parallel validation metrics.

        Returns dictionary with:
        - is_parallel: Whether validation agents ran in parallel
        - time_span: Time span between first and last start (seconds)
        - agents_started: List of validation agents that started
        - agents_completed: List of validation agents that completed
        - total_duration: Total wall-clock time for validation phase
        - sequential_duration: Estimated time if run sequentially (sum of individual durations)
        - time_saved: Estimated time saved by parallelization
        """
        reviewer_entry = None
        security_entry = None
        doc_entry = None

        for entry in self.tracker.session_data["agents"]:
            if entry["agent"] == "reviewer":
                reviewer_entry = entry
            elif entry["agent"] == "security-auditor":
                security_entry = entry
            elif entry["agent"] == "doc-master":
                doc_entry = entry

        agents_started = []
        agents_completed = []

        if reviewer_entry:
            agents_started.append("reviewer")
            if reviewer_entry.get("status") == "completed":
                agents_completed.append("reviewer")

        if security_entry:
            agents_started.append("security-auditor")
            if security_entry.get("status") == "completed":
                agents_completed.append("security-auditor")

        if doc_entry:
            agents_started.append("doc-master")
            if doc_entry.get("status") == "completed":
                agents_completed.append("doc-master")

        # Calculate time metrics
        is_parallel = False
        time_span = None
        total_duration = None
        sequential_duration = None
        time_saved = None

        if all([reviewer_entry, security_entry, doc_entry]):
            try:
                # Get start times
                reviewer_start = datetime.fromisoformat(reviewer_entry["started_at"])
                security_start = datetime.fromisoformat(security_entry["started_at"])
                doc_start = datetime.fromisoformat(doc_entry["started_at"])

                # Calculate time span between starts
                timestamps = [reviewer_start, security_start, doc_start]
                min_time = min(timestamps)
                max_time = max(timestamps)
                time_span = (max_time - min_time).total_seconds()
                is_parallel = time_span <= 10

                # Calculate total duration (wall-clock time from first start to last completion)
                if all([
                    reviewer_entry.get("status") == "completed",
                    security_entry.get("status") == "completed",
                    doc_entry.get("status") == "completed"
                ]):
                    reviewer_complete = datetime.fromisoformat(reviewer_entry["completed_at"])
                    security_complete = datetime.fromisoformat(security_entry["completed_at"])
                    doc_complete = datetime.fromisoformat(doc_entry["completed_at"])

                    completion_times = [reviewer_complete, security_complete, doc_complete]
                    last_completion = max(completion_times)
                    first_start = min_time

                    total_duration = (last_completion - first_start).total_seconds()

                    # Calculate sequential duration (sum of individual durations)
                    sequential_duration = sum([
                        reviewer_entry.get("duration_seconds", 0),
                        security_entry.get("duration_seconds", 0),
                        doc_entry.get("duration_seconds", 0)
                    ])

                    # Calculate time saved
                    if sequential_duration > 0 and total_duration > 0:
                        time_saved = sequential_duration - total_duration

            except (ValueError, KeyError):
                pass

        return {
            "is_parallel": is_parallel,
            "time_span": time_span,
            "agents_started": agents_started,
            "agents_completed": agents_completed,
            "total_duration": total_duration,
            "sequential_duration": sequential_duration,
            "time_saved": time_saved
        }


# Export public symbols
__all__ = ["ParallelVerifier"]
