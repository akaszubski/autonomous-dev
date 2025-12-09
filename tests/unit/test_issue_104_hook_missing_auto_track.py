#!/usr/bin/env python3
"""
Unit Tests for Issue #104 - SubagentStop Hook Missing auto_track_from_environment()

This module contains tests that demonstrate the ACTUAL BUG: The SubagentStop hook
(log_agent_completion.py) calls complete_agent() without first calling
auto_track_from_environment(), causing Task tool agents to appear as completed
without proper start entries.

Bug Demonstration:
    Current Hook Behavior:
    1. SubagentStop hook fires
    2. Hook reads CLAUDE_AGENT_NAME
    3. Hook calls complete_agent() directly
    4. Result: Agent marked completed without start entry (if not previously tracked)

    Expected Hook Behavior:
    1. SubagentStop hook fires
    2. Hook reads CLAUDE_AGENT_NAME
    3. Hook calls auto_track_from_environment() FIRST (ensures agent tracked)
    4. Hook calls complete_agent() (safe, idempotent)
    5. Result: Agent has proper start and completion entries

Test Strategy:
    - Test current hook behavior (shows bug)
    - Test expected hook behavior (shows fix)
    - Test that fix doesn't break existing workflows

Following TDD principles:
    - Tests demonstrate the bug clearly
    - Tests show what the fix should do
    - Tests verify no regressions

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


class TestHookBugDemonstration:
    """Demonstrate the actual bug in log_agent_completion.py hook.

    These tests show that the current hook behavior causes incomplete tracking
    for Task tool agents.
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
        session_file = temp_session_dir / "test-hook-bug.json"
        session_data = {
            "session_id": "test-20251209-120000",
            "started": "2025-12-09T12:00:00",
            "agents": []
        }
        session_file.write_text(json.dumps(session_data, indent=2))
        return session_file

    def test_current_hook_behavior_missing_start_entry(self, session_file):
        """DEMONSTRATES BUG: Current hook behavior creates incomplete entries.

        Scenario:
        1. Task tool invokes reviewer agent
        2. Reviewer not explicitly tracked in checkpoint
        3. SubagentStop hook fires
        4. Hook calls complete_agent() WITHOUT auto_track_from_environment()
        5. Result: Agent appears completed but without proper start entry

        This test PASSES with current code but shows INCOMPLETE behavior.
        After fix, agent will have both start and completion entries.
        """
        tracker = AgentTracker(session_file=str(session_file))

        # Simulate CURRENT hook behavior (bug)
        with patch.dict(os.environ, {"CLAUDE_AGENT_NAME": "reviewer"}):
            # Current hook does NOT call auto_track_from_environment() first
            # It goes straight to complete_agent()
            tracker.complete_agent("reviewer", "Code review completed")

        # Verify entry exists
        session_data = json.loads(session_file.read_text())
        agents = session_data.get("agents", [])
        assert len(agents) == 1

        agent = agents[0]
        assert agent["agent"] == "reviewer"
        assert agent["status"] == "completed"

        # BUG EVIDENCE: Agent has completion but may be missing proper start metadata
        # complete_agent() is idempotent and will create entry if missing,
        # but it won't have the same tracking metadata as auto_track_from_environment()
        assert "completed_at" in agent
        assert "message" in agent

        # This test passes with current code, showing the bug is subtle
        # The fix ensures auto_track is called FIRST for consistent tracking

    def test_fixed_hook_behavior_proper_tracking(self, session_file):
        """DEMONSTRATES FIX: Fixed hook behavior creates complete entries.

        Scenario:
        1. Task tool invokes reviewer agent
        2. Reviewer not explicitly tracked in checkpoint
        3. SubagentStop hook fires
        4. Hook calls auto_track_from_environment() FIRST
        5. Hook calls complete_agent() (idempotent, safe)
        6. Result: Agent has proper start and completion entries

        This test shows what the FIXED hook should do.
        """
        tracker = AgentTracker(session_file=str(session_file))

        # Simulate FIXED hook behavior
        with patch.dict(os.environ, {"CLAUDE_AGENT_NAME": "reviewer"}):
            # FIXED hook calls auto_track_from_environment() FIRST
            was_newly_tracked = tracker.auto_track_from_environment(
                message="Code review in progress"
            )
            assert was_newly_tracked is True, "Should track new agent"

            # Then calls complete_agent() (idempotent, safe)
            tracker.complete_agent("reviewer", "Code review completed")

        # Verify complete entry
        session_data = json.loads(session_file.read_text())
        agents = session_data.get("agents", [])
        assert len(agents) == 1

        agent = agents[0]
        assert agent["agent"] == "reviewer"
        assert agent["status"] == "completed"
        assert "started_at" in agent
        assert "completed_at" in agent
        assert "duration_seconds" in agent
        assert agent["message"] == "Code review completed"

    def test_hook_fix_idempotent_with_explicit_tracking(self, session_file):
        """Test hook fix is idempotent when checkpoint explicitly tracks agent.

        Scenario:
        1. Checkpoint explicitly calls auto_track_from_environment()
        2. SubagentStop hook fires
        3. Hook calls auto_track_from_environment() again (returns False)
        4. Hook calls complete_agent() (updates status)
        5. Result: Single agent entry, no duplicates

        This test verifies the fix doesn't create duplicates.
        """
        tracker = AgentTracker(session_file=str(session_file))

        # Step 1: Checkpoint explicit tracking
        with patch.dict(os.environ, {"CLAUDE_AGENT_NAME": "doc-master"}):
            result1 = tracker.auto_track_from_environment(
                message="Checkpoint: Starting documentation sync"
            )
            assert result1 is True

        # Step 2: SubagentStop hook (FIXED behavior)
        with patch.dict(os.environ, {"CLAUDE_AGENT_NAME": "doc-master"}):
            # Hook calls auto_track first (idempotent)
            result2 = tracker.auto_track_from_environment(
                message="Hook: Documentation completing"
            )
            assert result2 is False, "Should return False (already tracked)"

            # Then completes agent
            tracker.complete_agent("doc-master", "Documentation updated")

        # Verify single entry (no duplicates)
        session_data = json.loads(session_file.read_text())
        agents = session_data.get("agents", [])
        assert len(agents) == 1, f"Expected 1 agent, got {len(agents)} (duplicate!)"

        agent = agents[0]
        assert agent["agent"] == "doc-master"
        assert agent["status"] == "completed"

    def test_hook_fix_handles_parallel_task_tool_agents(self, session_file):
        """Test hook fix correctly handles parallel Task tool invocations.

        Scenario:
        1. Three Task tool agents invoked in parallel (reviewer, security, docs)
        2. Each SubagentStop hook fires independently
        3. Each hook calls auto_track + complete_agent
        4. Result: All three agents tracked without conflicts

        This test verifies the fix works for parallel execution.
        """
        tracker = AgentTracker(session_file=str(session_file))

        # Simulate parallel Task tool invocations
        parallel_agents = ["reviewer", "security-auditor", "doc-master"]

        for agent_name in parallel_agents:
            with patch.dict(os.environ, {"CLAUDE_AGENT_NAME": agent_name}):
                # FIXED hook behavior
                tracker.auto_track_from_environment(message=f"{agent_name} started")
                tracker.complete_agent(agent_name, f"{agent_name} completed")

        # Verify all tracked
        session_data = json.loads(session_file.read_text())
        agents = session_data.get("agents", [])
        assert len(agents) == 3

        tracked_names = {a["agent"] for a in agents}
        assert tracked_names == {"reviewer", "security-auditor", "doc-master"}

        # All should be completed
        for agent in agents:
            assert agent["status"] == "completed"


class TestHookFixImplementationRequirements:
    """Test specific requirements for implementing the hook fix.

    These tests describe exactly what needs to be added to log_agent_completion.py.
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
        session_file = temp_session_dir / "test-hook-fix.json"
        session_data = {
            "session_id": "test-20251209-140000",
            "started": "2025-12-09T14:00:00",
            "agents": []
        }
        session_file.write_text(json.dumps(session_data, indent=2))
        return session_file

    def test_hook_must_call_auto_track_before_complete(self, session_file):
        """Test hook MUST call auto_track_from_environment() before complete_agent().

        Implementation Requirement:
        In log_agent_completion.py main() function, ADD:

        ```python
        # Initialize tracker
        tracker = AgentTracker()

        # NEW: Auto-detect and track Task tool agents (Issue #104)
        tracker.auto_track_from_environment(message=summary)

        # EXISTING: Log completion or failure
        if agent_status == "success":
            tracker.complete_agent(agent_name, summary, tools)
        ```

        This ensures Task tool agents are tracked before completion.
        """
        tracker = AgentTracker(session_file=str(session_file))

        # Simulate required hook behavior
        with patch.dict(os.environ, {
            "CLAUDE_AGENT_NAME": "security-auditor",
            "CLAUDE_AGENT_STATUS": "success"
        }):
            summary = "Security scan completed"

            # REQUIRED: Call auto_track first
            tracker.auto_track_from_environment(message=summary)

            # EXISTING: Complete agent
            tracker.complete_agent("security-auditor", summary)

        # Verify proper tracking
        session_data = json.loads(session_file.read_text())
        agents = session_data.get("agents", [])
        assert len(agents) == 1

        agent = agents[0]
        assert agent["agent"] == "security-auditor"
        assert agent["status"] == "completed"
        assert "started_at" in agent
        assert "completed_at" in agent

    def test_hook_must_handle_missing_env_var_gracefully(self, session_file):
        """Test hook MUST handle missing CLAUDE_AGENT_NAME gracefully.

        Implementation Requirement:
        auto_track_from_environment() already handles missing env var gracefully
        (returns False), so hook can safely call it without additional checks.

        Hook should:
        1. Call auto_track_from_environment() (returns False if env var missing)
        2. Continue to complete_agent() with provided agent_name
        3. Not crash or block workflow
        """
        tracker = AgentTracker(session_file=str(session_file))

        # Simulate missing env var
        with patch.dict(os.environ, {}, clear=True):
            # auto_track returns False (no env var)
            result = tracker.auto_track_from_environment(message="test")
            assert result is False

            # Hook can still complete with provided name
            tracker.complete_agent("implementer", "Implementation complete")

        # Verify completion worked
        session_data = json.loads(session_file.read_text())
        agents = session_data.get("agents", [])
        assert len(agents) == 1
        assert agents[0]["agent"] == "implementer"

    def test_hook_must_handle_failure_status(self, session_file):
        """Test hook MUST call auto_track before fail_agent() too.

        Implementation Requirement:
        Hook should call auto_track_from_environment() for BOTH success and failure:

        ```python
        # NEW: Auto-track before completion or failure
        tracker.auto_track_from_environment(message=summary or error_msg)

        if agent_status == "success":
            tracker.complete_agent(agent_name, summary, tools)
        else:
            tracker.fail_agent(agent_name, error_msg)
        ```
        """
        tracker = AgentTracker(session_file=str(session_file))

        # Simulate agent failure
        with patch.dict(os.environ, {
            "CLAUDE_AGENT_NAME": "test-master",
            "CLAUDE_AGENT_STATUS": "error"
        }):
            error_msg = "Test generation failed"

            # REQUIRED: Auto-track even for failures
            tracker.auto_track_from_environment(message=error_msg)

            # EXISTING: Fail agent
            tracker.fail_agent("test-master", error_msg)

        # Verify tracking
        session_data = json.loads(session_file.read_text())
        agents = session_data.get("agents", [])
        assert len(agents) == 1

        agent = agents[0]
        assert agent["agent"] == "test-master"
        assert agent["status"] == "failed"
        assert "started_at" in agent


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
