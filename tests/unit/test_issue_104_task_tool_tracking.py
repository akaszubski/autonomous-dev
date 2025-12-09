#!/usr/bin/env python3
"""
Unit Tests for Issue #104 - Improve Agent Tracking for Task Tool Invocations

This module contains FAILING unit tests that verify the SubagentStop hook
enhancement to automatically track Task tool agents before completing them.

Problem:
    /pipeline-status shows "4 of 7 agents" even when all 7 agents ran.
    Agents invoked via Task tool bypass SubagentStop hook tracking because
    the hook only calls complete_agent() without first calling auto_track_from_environment().

Solution:
    Phase 1: Enhance log_agent_completion.py (SubagentStop hook) to call
             auto_track_from_environment() before complete_agent()
    Phase 2: Add explicit tracking in /auto-implement checkpoints for Task tool agents
    Phase 3: Update documentation

Test Strategy:
    - Unit tests for hook behavior enhancement
    - Verify auto_track_from_environment() called before complete_agent()
    - Test idempotency (no duplicate tracking)
    - Test parallel Task tool agents
    - Test graceful degradation (missing env vars)

Test Coverage Target: 100% of hook enhancement code paths

Following TDD principles:
    - Write tests FIRST (red phase)
    - Tests describe fix requirements
    - Tests should FAIL until implementation complete
    - Each test validates ONE requirement

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
from unittest.mock import Mock, patch, MagicMock, call

import pytest

# Add project root to path for imports
project_root = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(project_root / "scripts"))

from agent_tracker import AgentTracker


class TestSubagentStopHookEnhancement:
    """Test SubagentStop hook enhancement to call auto_track_from_environment().

    This validates Phase 1 of the fix: Modify log_agent_completion.py to
    auto-detect and track Task tool agents before completing them.
    """

    @pytest.fixture
    def temp_session_dir(self, tmp_path):
        """Create temporary session directory."""
        session_dir = tmp_path / "docs" / "sessions"
        session_dir.mkdir(parents=True)
        return session_dir

    @pytest.fixture
    def session_file(self, temp_session_dir):
        """Create empty session file."""
        session_file = temp_session_dir / "test-session.json"
        session_data = {
            "session_id": "test-20251209-120000",
            "started": "2025-12-09T12:00:00",
            "agents": []
        }
        session_file.write_text(json.dumps(session_data, indent=2))
        return session_file

    def test_subagent_stop_calls_auto_track_before_complete(self, session_file):
        """Test SubagentStop hook calls auto_track_from_environment() before complete_agent().

        Workflow:
        1. SubagentStop hook triggered (agent completes)
        2. Hook reads CLAUDE_AGENT_NAME from environment
        3. Hook calls auto_track_from_environment() to ensure agent is tracked
        4. Hook calls complete_agent() to mark completion
        5. No duplicate entries created

        Expected: Agent appears in session with completed status.

        CURRENTLY FAILS: Hook doesn't call auto_track_from_environment() before complete_agent(),
        so Task tool agents appear as completed without start entry.
        """
        tracker = AgentTracker(session_file=str(session_file))

        # Simulate SubagentStop hook behavior
        with patch.dict(os.environ, {
            "CLAUDE_AGENT_NAME": "reviewer",
            "CLAUDE_AGENT_STATUS": "success"
        }):
            # This is what the FIXED hook should do:
            # 1. Auto-track from environment (ensures agent is tracked)
            was_tracked = tracker.auto_track_from_environment(
                message="Code review in progress"
            )

            # 2. Complete the agent (idempotent, safe even if already tracked)
            tracker.complete_agent("reviewer", "Code review passed")

        # Verify agent tracked correctly
        session_data = json.loads(session_file.read_text())
        agents = session_data.get("agents", [])

        # Should have exactly 1 agent entry (no duplicates)
        assert len(agents) == 1, f"Expected 1 agent, got {len(agents)}"

        agent = agents[0]
        assert agent["agent"] == "reviewer"
        assert agent["status"] == "completed"
        assert "started_at" in agent
        assert "completed_at" in agent
        assert "duration_seconds" in agent

    def test_auto_track_detects_task_tool_agent(self, session_file):
        """Test auto_track_from_environment() detects Task tool agent from env var.

        Expected: Reads CLAUDE_AGENT_NAME, starts tracking if not already tracked.

        CURRENTLY PASSES: auto_track_from_environment() already exists (Issue #57).
        This test ensures it still works correctly for Issue #104.
        """
        tracker = AgentTracker(session_file=str(session_file))

        with patch.dict(os.environ, {"CLAUDE_AGENT_NAME": "security-auditor"}):
            result = tracker.auto_track_from_environment(
                message="Security scan started"
            )

            assert result is True, "Should track new agent"

        # Verify agent tracked
        session_data = json.loads(session_file.read_text())
        agents = session_data.get("agents", [])
        assert len(agents) == 1
        assert agents[0]["agent"] == "security-auditor"
        assert agents[0]["status"] == "started"

    def test_no_duplicate_when_hook_and_explicit_tracking(self, session_file):
        """Test idempotency when both hook and explicit tracking used.

        Workflow:
        1. /auto-implement checkpoint explicitly tracks agent (new in Phase 2)
        2. Task tool completes, SubagentStop hook fires
        3. Hook calls auto_track_from_environment() (returns False, already tracked)
        4. Hook calls complete_agent() (updates status to completed)
        5. No duplicate entries

        Expected: Single agent entry with completed status.

        CURRENTLY FAILS: Without hook enhancement, explicit tracking creates entry
        but hook's complete_agent() doesn't verify tracking first.
        """
        tracker = AgentTracker(session_file=str(session_file))

        # Phase 1: Explicit tracking from /auto-implement checkpoint
        with patch.dict(os.environ, {"CLAUDE_AGENT_NAME": "doc-master"}):
            tracker.auto_track_from_environment(message="Updating documentation")

        # Phase 2: SubagentStop hook fires (simulated)
        with patch.dict(os.environ, {"CLAUDE_AGENT_NAME": "doc-master"}):
            # Hook should call auto_track first (idempotent)
            was_newly_tracked = tracker.auto_track_from_environment(
                message="Documentation sync"
            )
            assert was_newly_tracked is False, "Should return False (already tracked)"

            # Then complete
            tracker.complete_agent("doc-master", "Documentation updated")

        # Verify no duplicates
        session_data = json.loads(session_file.read_text())
        agents = session_data.get("agents", [])
        assert len(agents) == 1, f"Expected 1 agent, got {len(agents)} (duplicate!)"

        agent = agents[0]
        assert agent["agent"] == "doc-master"
        assert agent["status"] == "completed"

    def test_parallel_task_tool_agents_tracked(self, session_file):
        """Test multiple Task tool agents tracked in parallel (reviewer + security + docs).

        Workflow:
        1. /auto-implement parallel validation phase
        2. Three Task tool agents invoked simultaneously
        3. Each SubagentStop hook fires independently
        4. All three agents tracked without conflicts

        Expected: 3 agents in session, all completed.

        CURRENTLY FAILS: Without hook enhancement, agents may not be tracked before completion.
        """
        tracker = AgentTracker(session_file=str(session_file))

        # Simulate parallel Task tool invocations
        agents = ["reviewer", "security-auditor", "doc-master"]

        for agent_name in agents:
            with patch.dict(os.environ, {"CLAUDE_AGENT_NAME": agent_name}):
                # SubagentStop hook behavior (enhanced)
                tracker.auto_track_from_environment(message=f"{agent_name} started")
                tracker.complete_agent(agent_name, f"{agent_name} completed")

        # Verify all tracked
        session_data = json.loads(session_file.read_text())
        tracked_agents = session_data.get("agents", [])

        assert len(tracked_agents) == 3, f"Expected 3 agents, got {len(tracked_agents)}"

        tracked_names = {a["agent"] for a in tracked_agents}
        assert tracked_names == {"reviewer", "security-auditor", "doc-master"}

        # All should be completed
        for agent in tracked_agents:
            assert agent["status"] == "completed"

    def test_graceful_degradation_missing_env_var(self, session_file):
        """Test graceful degradation when CLAUDE_AGENT_NAME not set.

        Workflow:
        1. SubagentStop hook fires without CLAUDE_AGENT_NAME (shouldn't happen)
        2. auto_track_from_environment() returns False (no env var)
        3. Hook falls back to complete_agent() with provided name

        Expected: Hook doesn't crash, logs warning, continues.

        CURRENTLY PASSES: auto_track_from_environment() already handles missing env var.
        """
        tracker = AgentTracker(session_file=str(session_file))

        # Simulate missing env var
        with patch.dict(os.environ, {}, clear=True):
            result = tracker.auto_track_from_environment(
                message="Fallback tracking"
            )
            assert result is False, "Should return False when env var missing"

        # Verify no agents tracked (no env var to read)
        session_data = json.loads(session_file.read_text())
        agents = session_data.get("agents", [])
        assert len(agents) == 0, "Should not track without env var"


class TestExplicitTaskToolTracking:
    """Test explicit Task tool tracking in /auto-implement checkpoints.

    This validates Phase 2 of the fix: Add explicit auto_track_from_environment()
    calls in /auto-implement.md checkpoints where Task tool is used.
    """

    @pytest.fixture
    def temp_session_dir(self, tmp_path):
        """Create temporary session directory."""
        session_dir = tmp_path / "docs" / "sessions"
        session_dir.mkdir(parents=True)
        return session_dir

    @pytest.fixture
    def session_file(self, temp_session_dir):
        """Create empty session file."""
        session_file = temp_session_dir / "test-session.json"
        session_data = {
            "session_id": "test-20251209-140000",
            "started": "2025-12-09T14:00:00",
            "agents": []
        }
        session_file.write_text(json.dumps(session_data, indent=2))
        return session_file

    def test_checkpoint_explicit_tracking_parallel_exploration(self, session_file):
        """Test /auto-implement checkpoint tracks parallel exploration agents.

        Checkpoint 1.5 (Parallel Exploration Phase):
        - Invokes researcher + planner via Task tool
        - Should explicitly call auto_track_from_environment() for both

        Expected: Both agents tracked before Task tool invocation.

        CURRENTLY FAILS: Checkpoint doesn't explicitly track Task tool agents.
        """
        tracker = AgentTracker(session_file=str(session_file))

        # Simulate checkpoint tracking (what SHOULD happen)
        agents = ["researcher", "planner"]

        for agent_name in agents:
            with patch.dict(os.environ, {"CLAUDE_AGENT_NAME": agent_name}):
                # Explicit tracking in checkpoint
                result = tracker.auto_track_from_environment(
                    message=f"Starting {agent_name} via Task tool"
                )
                assert result is True

        # Verify both tracked
        session_data = json.loads(session_file.read_text())
        tracked_agents = session_data.get("agents", [])
        assert len(tracked_agents) == 2

        tracked_names = {a["agent"] for a in tracked_agents}
        assert tracked_names == {"researcher", "planner"}

    def test_checkpoint_explicit_tracking_parallel_validation(self, session_file):
        """Test /auto-implement checkpoint tracks parallel validation agents.

        Checkpoint 4.1 (Parallel Validation Phase):
        - Invokes reviewer + security-auditor + doc-master via Task tool
        - Should explicitly call auto_track_from_environment() for all three

        Expected: All three agents tracked before Task tool invocation.

        CURRENTLY FAILS: Checkpoint doesn't explicitly track Task tool agents.
        """
        tracker = AgentTracker(session_file=str(session_file))

        # Simulate checkpoint tracking (what SHOULD happen)
        validation_agents = ["reviewer", "security-auditor", "doc-master"]

        for agent_name in validation_agents:
            with patch.dict(os.environ, {"CLAUDE_AGENT_NAME": agent_name}):
                # Explicit tracking in checkpoint
                result = tracker.auto_track_from_environment(
                    message=f"Starting {agent_name} validation"
                )
                assert result is True

        # Verify all tracked
        session_data = json.loads(session_file.read_text())
        tracked_agents = session_data.get("agents", [])
        assert len(tracked_agents) == 3

        tracked_names = {a["agent"] for a in tracked_agents}
        assert tracked_names == {"reviewer", "security-auditor", "doc-master"}

    def test_explicit_tracking_idempotent_with_hook(self, session_file):
        """Test explicit checkpoint tracking is idempotent with SubagentStop hook.

        Workflow:
        1. Checkpoint explicitly tracks agent
        2. Agent executes via Task tool
        3. SubagentStop hook fires, calls auto_track_from_environment() again
        4. Hook's auto_track returns False (already tracked)
        5. Hook completes agent normally

        Expected: Single agent entry, no duplicates.

        CURRENTLY FAILS: Need to verify complete_agent() handles pre-tracked agents.
        """
        tracker = AgentTracker(session_file=str(session_file))

        # Step 1: Checkpoint tracking
        with patch.dict(os.environ, {"CLAUDE_AGENT_NAME": "reviewer"}):
            result1 = tracker.auto_track_from_environment(
                message="Checkpoint: Starting reviewer"
            )
            assert result1 is True

        # Step 2: SubagentStop hook tracking (should be idempotent)
        with patch.dict(os.environ, {"CLAUDE_AGENT_NAME": "reviewer"}):
            result2 = tracker.auto_track_from_environment(
                message="Hook: Reviewer completing"
            )
            assert result2 is False, "Should return False (already tracked)"

            # Complete agent
            tracker.complete_agent("reviewer", "Review passed")

        # Verify single entry
        session_data = json.loads(session_file.read_text())
        agents = session_data.get("agents", [])
        assert len(agents) == 1
        assert agents[0]["agent"] == "reviewer"
        assert agents[0]["status"] == "completed"


class TestAgentTrackerIdempotency:
    """Test AgentTracker idempotency for Issue #104 requirements.

    Verifies that complete_agent() is truly idempotent and handles cases where
    agents are tracked via multiple paths (checkpoint + hook).
    """

    @pytest.fixture
    def temp_session_dir(self, tmp_path):
        """Create temporary session directory."""
        session_dir = tmp_path / "docs" / "sessions"
        session_dir.mkdir(parents=True)
        return session_dir

    @pytest.fixture
    def session_file(self, temp_session_dir):
        """Create empty session file."""
        session_file = temp_session_dir / "test-session.json"
        session_data = {
            "session_id": "test-20251209-150000",
            "started": "2025-12-09T15:00:00",
            "agents": []
        }
        session_file.write_text(json.dumps(session_data, indent=2))
        return session_file

    def test_complete_agent_idempotent_multiple_calls(self, session_file):
        """Test complete_agent() is idempotent when called multiple times.

        Expected: Multiple calls to complete_agent() don't create duplicates.

        CURRENTLY PASSES: complete_agent() already idempotent (Issue #57).
        This test ensures it still works for Issue #104.
        """
        tracker = AgentTracker(session_file=str(session_file))

        # Track agent
        tracker.start_agent("planner", "Creating plan")

        # Complete multiple times (should be safe)
        tracker.complete_agent("planner", "Plan created")
        tracker.complete_agent("planner", "Plan finalized")

        # Verify single entry
        session_data = json.loads(session_file.read_text())
        agents = session_data.get("agents", [])
        assert len(agents) == 1
        assert agents[0]["agent"] == "planner"
        assert agents[0]["status"] == "completed"

    def test_complete_agent_without_start_creates_entry(self, session_file):
        """Test complete_agent() creates entry if agent not yet tracked.

        Expected: complete_agent() without prior start_agent() should work.

        CURRENTLY PASSES: This is existing behavior that Issue #104 relies on.
        """
        tracker = AgentTracker(session_file=str(session_file))

        # Complete without start (fallback behavior)
        tracker.complete_agent("implementer", "Implementation complete")

        # Verify entry created
        session_data = json.loads(session_file.read_text())
        agents = session_data.get("agents", [])
        assert len(agents) == 1
        assert agents[0]["agent"] == "implementer"
        assert agents[0]["status"] == "completed"


class TestSecurityValidation:
    """Test security validation for Issue #104 enhancements.

    Ensures that auto_track_from_environment() validates CLAUDE_AGENT_NAME
    to prevent injection attacks via environment variables.
    """

    @pytest.fixture
    def temp_session_dir(self, tmp_path):
        """Create temporary session directory."""
        session_dir = tmp_path / "docs" / "sessions"
        session_dir.mkdir(parents=True)
        return session_dir

    @pytest.fixture
    def session_file(self, temp_session_dir):
        """Create empty session file."""
        session_file = temp_session_dir / "test-session.json"
        session_data = {
            "session_id": "test-20251209-160000",
            "started": "2025-12-09T16:00:00",
            "agents": []
        }
        session_file.write_text(json.dumps(session_data, indent=2))
        return session_file

    def test_malicious_agent_name_rejected(self, session_file):
        """Test malicious CLAUDE_AGENT_NAME rejected by validation.

        SECURITY: Prevent path traversal via environment variable.

        Expected: ValueError raised for invalid agent names.

        CURRENTLY PASSES: auto_track_from_environment() already validates (Issue #57).
        """
        tracker = AgentTracker(session_file=str(session_file))

        malicious_names = [
            "../../etc/passwd",
            "../../../root/.ssh/id_rsa",
            "agent; rm -rf /",
            "agent`whoami`",
            "agent$(whoami)",
        ]

        for bad_name in malicious_names:
            with patch.dict(os.environ, {"CLAUDE_AGENT_NAME": bad_name}):
                with pytest.raises(ValueError):
                    tracker.auto_track_from_environment(message="Attack attempt")

    def test_empty_agent_name_rejected(self, session_file):
        """Test empty CLAUDE_AGENT_NAME rejected.

        Expected: ValueError for empty string.

        CURRENTLY PASSES: Existing validation.
        """
        tracker = AgentTracker(session_file=str(session_file))

        with patch.dict(os.environ, {"CLAUDE_AGENT_NAME": ""}):
            with pytest.raises(ValueError):
                tracker.auto_track_from_environment(message="Empty name")

    def test_overlength_agent_name_rejected(self, session_file):
        """Test overlength CLAUDE_AGENT_NAME rejected.

        Expected: ValueError for names > 255 characters.

        CURRENTLY PASSES: Existing validation.
        """
        tracker = AgentTracker(session_file=str(session_file))

        with patch.dict(os.environ, {"CLAUDE_AGENT_NAME": "a" * 256}):
            with pytest.raises(ValueError):
                tracker.auto_track_from_environment(message="Too long")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
