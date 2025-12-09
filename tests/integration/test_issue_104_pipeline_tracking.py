#!/usr/bin/env python3
"""
Integration Tests for Issue #104 - Pipeline Tracking Accuracy

This module contains FAILING integration tests that verify end-to-end pipeline
tracking accuracy after the Issue #104 fix. Tests ensure /pipeline-status
shows correct "7 of 7 agents" completion after /auto-implement.

Problem:
    /pipeline-status shows "4 of 7 agents" even when all agents ran because
    Task tool agents bypass SubagentStop hook tracking.

Solution Validation:
    - Phase 1: SubagentStop hook enhancement (auto_track_from_environment)
    - Phase 2: Explicit checkpoint tracking in /auto-implement
    - End Result: /pipeline-status shows accurate agent counts

Test Strategy:
    - End-to-end /auto-implement workflow simulation
    - Verify all 7 agents tracked correctly
    - Test session file persistence
    - Validate checkpoint tracking integration
    - Test /pipeline-status accuracy

Test Coverage Target: End-to-end pipeline tracking workflows

Following TDD principles:
    - Write tests FIRST (red phase)
    - Tests describe real-world usage after fix
    - Tests should FAIL until implementation complete
    - Each test validates ONE workflow scenario

Author: test-master agent
Date: 2025-12-09
Issue: #104
"""

import json
import os
import sys
import tempfile
from datetime import datetime
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock

import pytest

# Add project root to path for imports
project_root = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(project_root / "scripts"))

from agent_tracker import AgentTracker


class TestFullWorkflowPipelineTracking:
    """Test full /auto-implement workflow with accurate pipeline tracking.

    This validates the complete fix across all 7 agents:
    1. researcher (explicit tracking + hook)
    2. planner (explicit tracking + hook)
    3. test-master (standard start_agent + hook)
    4. implementer (standard start_agent + hook)
    5. reviewer (Task tool + hook enhancement)
    6. security-auditor (Task tool + hook enhancement)
    7. doc-master (Task tool + hook enhancement)
    """

    @pytest.fixture
    def temp_session_dir(self, tmp_path):
        """Create temporary session directory."""
        session_dir = tmp_path / "docs" / "sessions"
        session_dir.mkdir(parents=True)
        return session_dir

    @pytest.fixture
    def session_file(self, temp_session_dir):
        """Create empty session file for workflow."""
        session_file = temp_session_dir / "test-pipeline.json"
        session_data = {
            "session_id": "test-20251209-120000",
            "started": "2025-12-09T12:00:00",
            "agents": []
        }
        session_file.write_text(json.dumps(session_data, indent=2))
        return session_file

    def test_pipeline_status_shows_7_of_7_after_auto_implement(self, session_file):
        """Test /pipeline-status shows accurate '7 of 7 agents' after /auto-implement.

        Full Workflow Simulation:
        1. CHECKPOINT 1: Alignment validation (quality-validator)
        2. CHECKPOINT 1.5: Parallel exploration (researcher + planner via Task tool)
        3. CHECKPOINT 2: TDD test generation (test-master)
        4. CHECKPOINT 3: Implementation (implementer)
        5. CHECKPOINT 4.1: Parallel validation (reviewer + security + docs via Task tool)
        6. CHECKPOINT 5: Final quality gate (quality-validator)

        Expected: Session file has 7 unique agents, all completed.

        CURRENTLY FAILS: Task tool agents (researcher, planner, reviewer, security, docs)
        not tracked correctly without hook enhancement.
        """
        tracker = AgentTracker(session_file=str(session_file))

        # CHECKPOINT 1: Alignment validation
        tracker.start_agent("quality-validator", "Initial alignment check")
        tracker.complete_agent("quality-validator", "Alignment validated")

        # CHECKPOINT 1.5: Parallel exploration (researcher + planner via Task tool)
        # After fix: Checkpoint explicitly tracks these before Task tool invocation
        with patch.dict(os.environ, {"CLAUDE_AGENT_NAME": "researcher"}):
            tracker.auto_track_from_environment(message="Researching patterns")

        with patch.dict(os.environ, {"CLAUDE_AGENT_NAME": "planner"}):
            tracker.auto_track_from_environment(message="Creating plan")

        # Simulate Task tool completion (SubagentStop hook fires)
        with patch.dict(os.environ, {"CLAUDE_AGENT_NAME": "researcher"}):
            tracker.auto_track_from_environment(message="Completing research")
            tracker.complete_agent("researcher", "Research complete")

        with patch.dict(os.environ, {"CLAUDE_AGENT_NAME": "planner"}):
            tracker.auto_track_from_environment(message="Completing plan")
            tracker.complete_agent("planner", "Plan created")

        # CHECKPOINT 2: TDD test generation
        tracker.start_agent("test-master", "Writing tests")
        tracker.complete_agent("test-master", "Tests written")

        # CHECKPOINT 3: Implementation
        tracker.start_agent("implementer", "Implementing feature")
        tracker.complete_agent("implementer", "Implementation complete")

        # CHECKPOINT 4.1: Parallel validation (reviewer + security + docs via Task tool)
        # After fix: Checkpoint explicitly tracks these before Task tool invocation
        validation_agents = ["reviewer", "security-auditor", "doc-master"]

        for agent_name in validation_agents:
            with patch.dict(os.environ, {"CLAUDE_AGENT_NAME": agent_name}):
                tracker.auto_track_from_environment(message=f"Starting {agent_name}")

        # Simulate Task tool completion (SubagentStop hook fires for each)
        for agent_name in validation_agents:
            with patch.dict(os.environ, {"CLAUDE_AGENT_NAME": agent_name}):
                tracker.auto_track_from_environment(message=f"Completing {agent_name}")
                tracker.complete_agent(agent_name, f"{agent_name} validation passed")

        # Verify all 7 agents tracked
        session_data = json.loads(session_file.read_text())
        agents = session_data.get("agents", [])

        # Should have 7 unique agents (excluding duplicate quality-validator from checkpoint 1 and 5)
        unique_agents = {a["agent"] for a in agents}
        expected_agents = {
            "quality-validator",
            "researcher",
            "planner",
            "test-master",
            "implementer",
            "reviewer",
            "security-auditor",
            "doc-master"
        }

        # Note: quality-validator appears in checkpoint 1 and 5, so we have 8 entries total
        # but 7 unique workflow agents (quality-validator counted once)
        assert unique_agents == expected_agents, (
            f"Expected {expected_agents}, got {unique_agents}"
        )

        # All agents should be completed
        for agent in agents:
            assert agent["status"] == "completed", (
                f"Agent {agent['agent']} not completed"
            )

        # Simulate /pipeline-status calculation
        workflow_agents = [
            "quality-validator",
            "researcher",
            "planner",
            "test-master",
            "implementer",
            "reviewer",
            "security-auditor",
            "doc-master"
        ]

        completed_count = sum(
            1 for agent in agents
            if agent["agent"] in workflow_agents and agent["status"] == "completed"
        )

        # Should show "8 of 8" (quality-validator runs twice, but counts as 1 unique agent in display)
        # Or "7 of 7" if we deduplicate quality-validator
        assert completed_count >= 7, (
            f"/pipeline-status would show '{completed_count} of 7 agents' "
            f"(expected 7 or 8 depending on deduplication)"
        )

    def test_task_tool_agents_appear_in_session_file(self, session_file):
        """Test Task tool agents properly persisted to session file.

        Validates that Task tool agents (researcher, planner, reviewer, security, docs)
        are written to session file with correct metadata.

        Expected: Each agent has start time, completion time, duration, status.

        CURRENTLY FAILS: Task tool agents may be missing start entries.
        """
        tracker = AgentTracker(session_file=str(session_file))

        # Simulate Task tool invocations with hook enhancement
        task_agents = [
            "researcher",
            "planner",
            "reviewer",
            "security-auditor",
            "doc-master"
        ]

        for agent_name in task_agents:
            with patch.dict(os.environ, {"CLAUDE_AGENT_NAME": agent_name}):
                # Explicit tracking (checkpoint)
                tracker.auto_track_from_environment(message=f"Starting {agent_name}")

                # SubagentStop hook (enhanced)
                tracker.auto_track_from_environment(message=f"Completing {agent_name}")
                tracker.complete_agent(agent_name, f"{agent_name} complete")

        # Verify session file structure
        session_data = json.loads(session_file.read_text())
        agents = session_data.get("agents", [])

        assert len(agents) == 5, f"Expected 5 agents, got {len(agents)}"

        for agent in agents:
            # Required fields for completed agents
            assert "agent" in agent
            assert "status" in agent
            assert agent["status"] == "completed"
            assert "started_at" in agent, f"Missing started_at for {agent['agent']}"
            assert "completed_at" in agent, f"Missing completed_at for {agent['agent']}"
            assert "duration_seconds" in agent, f"Missing duration for {agent['agent']}"
            assert "message" in agent

    def test_explicit_tracking_works_from_auto_implement_checkpoints(self, session_file):
        """Test explicit checkpoint tracking integrates with hook enhancement.

        Workflow:
        1. /auto-implement checkpoint explicitly tracks Task tool agent
        2. Agent executes via Task tool
        3. SubagentStop hook fires, calls auto_track_from_environment() again
        4. Hook's auto_track returns False (already tracked)
        5. Hook completes agent successfully
        6. No duplicate entries

        Expected: Single agent entry per agent, all completed.

        CURRENTLY FAILS: Need checkpoint modifications to explicitly track Task tool agents.
        """
        tracker = AgentTracker(session_file=str(session_file))

        # Simulate checkpoint 1.5 (parallel exploration)
        with patch.dict(os.environ, {"CLAUDE_AGENT_NAME": "researcher"}):
            # Explicit checkpoint tracking
            result1 = tracker.auto_track_from_environment(
                message="Checkpoint: Starting researcher"
            )
            assert result1 is True, "Checkpoint should track new agent"

        # Simulate SubagentStop hook firing
        with patch.dict(os.environ, {"CLAUDE_AGENT_NAME": "researcher"}):
            # Hook's auto_track (should be idempotent)
            result2 = tracker.auto_track_from_environment(
                message="Hook: Researcher completing"
            )
            assert result2 is False, "Hook should detect agent already tracked"

            # Hook completes agent
            tracker.complete_agent("researcher", "Research complete")

        # Verify single entry
        session_data = json.loads(session_file.read_text())
        agents = session_data.get("agents", [])
        assert len(agents) == 1, f"Expected 1 agent, got {len(agents)} (duplicate!)"
        assert agents[0]["agent"] == "researcher"
        assert agents[0]["status"] == "completed"


class TestPipelineStatusAccuracy:
    """Test /pipeline-status command accuracy after Issue #104 fix.

    Validates that the pipeline status calculation correctly counts all agents
    including those invoked via Task tool.
    """

    @pytest.fixture
    def temp_session_dir(self, tmp_path):
        """Create temporary session directory."""
        session_dir = tmp_path / "docs" / "sessions"
        session_dir.mkdir(parents=True)
        return session_dir

    @pytest.fixture
    def session_file(self, temp_session_dir):
        """Create session file with sample pipeline data."""
        session_file = temp_session_dir / "pipeline-status.json"
        session_data = {
            "session_id": "test-20251209-140000",
            "started": "2025-12-09T14:00:00",
            "agents": []
        }
        session_file.write_text(json.dumps(session_data, indent=2))
        return session_file

    def test_pipeline_status_counts_all_task_tool_agents(self, session_file):
        """Test /pipeline-status correctly counts Task tool agents.

        Before Fix: Shows "4 of 7" (missing 3 Task tool agents)
        After Fix: Shows "7 of 7" (all agents tracked)

        CURRENTLY FAILS: Task tool agents not tracked without hook enhancement.
        """
        tracker = AgentTracker(session_file=str(session_file))

        # Simulate full workflow with Task tool agents
        all_agents = [
            "quality-validator",
            "researcher",  # Task tool
            "planner",  # Task tool
            "test-master",
            "implementer",
            "reviewer",  # Task tool
            "security-auditor",  # Task tool
            "doc-master"  # Task tool
        ]

        task_tool_agents = {
            "researcher",
            "planner",
            "reviewer",
            "security-auditor",
            "doc-master"
        }

        for agent_name in all_agents:
            if agent_name in task_tool_agents:
                # Task tool agents use enhanced hook tracking
                with patch.dict(os.environ, {"CLAUDE_AGENT_NAME": agent_name}):
                    tracker.auto_track_from_environment(message=f"Starting {agent_name}")
                    tracker.complete_agent(agent_name, f"{agent_name} complete")
            else:
                # Standard agents use start_agent + complete_agent
                tracker.start_agent(agent_name, f"Starting {agent_name}")
                tracker.complete_agent(agent_name, f"{agent_name} complete")

        # Verify count
        session_data = json.loads(session_file.read_text())
        agents = session_data.get("agents", [])

        # Should have all 8 agents (quality-validator + 7 workflow agents)
        unique_agents = {a["agent"] for a in agents}
        assert len(unique_agents) == 8, (
            f"Expected 8 unique agents, got {len(unique_agents)}: {unique_agents}"
        )

        # All should be completed
        completed = [a for a in agents if a["status"] == "completed"]
        assert len(completed) == len(agents), (
            f"Expected all agents completed, got {len(completed)} of {len(agents)}"
        )

    def test_pipeline_status_shows_correct_progress_percentage(self, session_file):
        """Test /pipeline-status shows correct progress percentage with Task tool agents.

        Expected: With 7 of 7 agents complete, progress should be 100%.

        CURRENTLY FAILS: With Task tool agents missing, shows ~57% (4 of 7).
        """
        tracker = AgentTracker(session_file=str(session_file))

        # Complete all 7 workflow agents (excluding quality-validator duplicates)
        workflow_agents = [
            "researcher",
            "planner",
            "test-master",
            "implementer",
            "reviewer",
            "security-auditor",
            "doc-master"
        ]

        for agent_name in workflow_agents:
            with patch.dict(os.environ, {"CLAUDE_AGENT_NAME": agent_name}):
                tracker.auto_track_from_environment(message=f"Starting {agent_name}")
                tracker.complete_agent(agent_name, f"{agent_name} complete")

        # Calculate progress (simulate /pipeline-status logic)
        session_data = json.loads(session_file.read_text())
        agents = session_data.get("agents", [])

        completed_count = len([a for a in agents if a["status"] == "completed"])
        total_count = len(workflow_agents)

        progress_percentage = (completed_count / total_count) * 100

        assert progress_percentage == 100.0, (
            f"Expected 100% progress, got {progress_percentage}% "
            f"({completed_count} of {total_count} agents)"
        )

    def test_pipeline_status_handles_partial_completion(self, session_file):
        """Test /pipeline-status accurately shows partial completion with Task tool agents.

        Scenario: researcher + planner complete, rest pending
        Expected: Shows "2 of 7 agents" (28.6%)

        CURRENTLY FAILS: May miss Task tool agents in count.
        """
        tracker = AgentTracker(session_file=str(session_file))

        # Complete only researcher and planner (Task tool agents)
        completed_agents = ["researcher", "planner"]

        for agent_name in completed_agents:
            with patch.dict(os.environ, {"CLAUDE_AGENT_NAME": agent_name}):
                tracker.auto_track_from_environment(message=f"Starting {agent_name}")
                tracker.complete_agent(agent_name, f"{agent_name} complete")

        # Verify partial completion
        session_data = json.loads(session_file.read_text())
        agents = session_data.get("agents", [])

        completed = [a for a in agents if a["status"] == "completed"]
        assert len(completed) == 2, (
            f"Expected 2 completed agents, got {len(completed)}"
        )


class TestCheckpointVerification:
    """Test checkpoint verification after Issue #104 fix.

    Validates that checkpoint verification correctly detects Task tool agents
    and doesn't incorrectly report missing agents.
    """

    @pytest.fixture
    def temp_session_dir(self, tmp_path):
        """Create temporary session directory."""
        session_dir = tmp_path / "docs" / "sessions"
        session_dir.mkdir(parents=True)
        return session_dir

    @pytest.fixture
    def session_file(self, temp_session_dir):
        """Create session file for checkpoint verification."""
        session_file = temp_session_dir / "checkpoint-verify.json"
        session_data = {
            "session_id": "test-20251209-150000",
            "started": "2025-12-09T15:00:00",
            "agents": []
        }
        session_file.write_text(json.dumps(session_data, indent=2))
        return session_file

    def test_checkpoint_verification_detects_parallel_task_tool_agents(self, session_file):
        """Test checkpoint verification correctly detects parallel Task tool agents.

        Checkpoint 4.1 verification should detect all 3 parallel validation agents:
        - reviewer
        - security-auditor
        - doc-master

        Expected: Verification passes when all 3 agents tracked and completed.

        CURRENTLY FAILS: Verification may not detect Task tool agents without hook enhancement.
        """
        tracker = AgentTracker(session_file=str(session_file))

        # Simulate parallel validation agents
        validation_agents = ["reviewer", "security-auditor", "doc-master"]

        for agent_name in validation_agents:
            with patch.dict(os.environ, {"CLAUDE_AGENT_NAME": agent_name}):
                tracker.auto_track_from_environment(message=f"Starting {agent_name}")
                tracker.complete_agent(agent_name, f"{agent_name} complete")

        # Verify all tracked
        session_data = json.loads(session_file.read_text())
        agents = session_data.get("agents", [])

        tracked_names = {a["agent"] for a in agents}
        assert tracked_names == {"reviewer", "security-auditor", "doc-master"}

        # All should be completed
        for agent in agents:
            assert agent["status"] == "completed"

        # Checkpoint verification logic: Check if all required agents are tracked
        required_agents = {"reviewer", "security-auditor", "doc-master"}
        tracked_completed = {
            a["agent"] for a in agents
            if a["status"] == "completed" and a["agent"] in required_agents
        }

        verification_passed = tracked_completed == required_agents
        assert verification_passed is True, (
            f"Checkpoint verification failed: expected {required_agents}, "
            f"got {tracked_completed}"
        )


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
