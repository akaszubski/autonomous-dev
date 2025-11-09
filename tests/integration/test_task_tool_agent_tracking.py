#!/usr/bin/env python3
"""
Integration Tests for Task Tool Agent Tracking (FAILING - Red Phase)

This module contains FAILING integration tests for Issue #57 - Agent tracker
doesn't detect Task tool agent execution. Tests verify end-to-end workflows
where agents are invoked via Task tool and tracked automatically.

Test Scenarios:
1. Parallel exploration (researcher + planner via Task tool)
2. Parallel validation (reviewer + security-auditor + doc-master via Task tool)
3. Full /auto-implement workflow with Task tool agents
4. Mixed tracking methods (some Task tool, some manual)
5. Session file consistency across multiple Task tool invocations

Integration Test Strategy:
- Simulate real /auto-implement workflows
- Test parallel agent invocations (Task tool strength)
- Verify session file accuracy
- Test interaction with SubagentStop hook
- Validate performance (no duplicate tracking overhead)

Test Coverage Target: End-to-end Task tool detection workflows

Following TDD principles:
- Write tests FIRST (red phase)
- Tests describe real-world usage
- Tests should FAIL until implementation is complete
- Each test validates ONE workflow scenario

Author: test-master agent
Date: 2025-11-09
Issue: #57
"""

import json
import os
import sys
import tempfile
from datetime import datetime
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock, call
from typing import List, Dict

import pytest

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from scripts.agent_tracker import AgentTracker

# Import hook module
sys.path.insert(0, str(Path(__file__).parent.parent.parent / ".claude" / "hooks"))


class TestParallelExplorationTaskTool:
    """Test parallel exploration phase (researcher + planner via Task tool).

    In /auto-implement, researcher and planner can run in parallel via Task tool.
    This tests that both agents are auto-detected and tracked correctly.
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
            "session_id": "test-20251109-120000",
            "started": "2025-11-09T12:00:00",
            "agents": []
        }
        session_file.write_text(json.dumps(session_data, indent=2))
        return session_file

    def test_parallel_exploration_both_agents_tracked(self, session_file):
        """Test both researcher and planner tracked when invoked via Task tool.

        Workflow:
        1. /auto-implement starts
        2. Claude invokes researcher + planner in parallel via Task tool
        3. CLAUDE_AGENT_NAME set for each invocation
        4. SubagentStop hook detects both agents
        5. Both agents appear in session file

        Expected: Session has 2 agents (researcher, planner) both completed.
        """
        tracker = AgentTracker(session_file=str(session_file))

        # Simulate researcher Task tool invocation
        with patch.dict(os.environ, {"CLAUDE_AGENT_NAME": "researcher"}):
            tracked_researcher = tracker.auto_track_from_environment(
                message="Researching JWT authentication patterns"
            )
            assert tracked_researcher is True

        # Simulate planner Task tool invocation (parallel)
        with patch.dict(os.environ, {"CLAUDE_AGENT_NAME": "planner"}):
            tracked_planner = tracker.auto_track_from_environment(
                message="Creating architecture plan for JWT auth"
            )
            assert tracked_planner is True

        # Verify both agents in session
        session_data = json.loads(session_file.read_text())
        agents = session_data.get("agents", [])
        assert len(agents) == 2

        agent_names = {a["agent"] for a in agents}
        assert "researcher" in agent_names
        assert "planner" in agent_names

        # All should be in 'started' status
        for agent in agents:
            assert agent["status"] == "started"

    def test_parallel_exploration_agents_completed(self, session_file):
        """Test parallel agents can be completed after tracking.

        Workflow:
        1. Both agents auto-tracked via Task tool
        2. Both agents complete their work
        3. complete_agent() called for each
        4. Session reflects both completions

        Expected: Both agents have 'completed' status.
        """
        tracker = AgentTracker(session_file=str(session_file))

        # Auto-track both
        with patch.dict(os.environ, {"CLAUDE_AGENT_NAME": "researcher"}):
            tracker.auto_track_from_environment(message="Research started")

        with patch.dict(os.environ, {"CLAUDE_AGENT_NAME": "planner"}):
            tracker.auto_track_from_environment(message="Planning started")

        # Complete both
        tracker.complete_agent("researcher", "Found 5 patterns")
        tracker.complete_agent("planner", "Architecture designed")

        # Verify completions
        session_data = json.loads(session_file.read_text())
        agents = session_data.get("agents", [])

        researcher = next(a for a in agents if a["agent"] == "researcher")
        planner = next(a for a in agents if a["agent"] == "planner")

        assert researcher["status"] == "completed"
        assert researcher["message"] == "Found 5 patterns"
        assert "completed_at" in researcher
        assert "duration_seconds" in researcher

        assert planner["status"] == "completed"
        assert planner["message"] == "Architecture designed"
        assert "completed_at" in planner
        assert "duration_seconds" in planner

    def test_parallel_exploration_no_duplicates_if_completed_twice(self, session_file):
        """Test idempotent completion prevents duplicates in parallel scenario.

        Workflow:
        1. Both agents auto-tracked
        2. complete_agent() called for each
        3. complete_agent() called AGAIN (simulating duplicate hook calls)
        4. No duplicate entries created

        Expected: Still only 2 agents in session (no duplicates).
        """
        tracker = AgentTracker(session_file=str(session_file))

        # Auto-track
        with patch.dict(os.environ, {"CLAUDE_AGENT_NAME": "researcher"}):
            tracker.auto_track_from_environment(message="Research")

        with patch.dict(os.environ, {"CLAUDE_AGENT_NAME": "planner"}):
            tracker.auto_track_from_environment(message="Planning")

        # Complete both (first time)
        tracker.complete_agent("researcher", "Complete 1")
        tracker.complete_agent("planner", "Complete 1")

        # Complete both AGAIN (second time)
        tracker.complete_agent("researcher", "Complete 2")
        tracker.complete_agent("planner", "Complete 2")

        # Verify no duplicates
        session_data = json.loads(session_file.read_text())
        agents = session_data.get("agents", [])
        assert len(agents) == 2

        # Verify original messages preserved (not overwritten)
        researcher = next(a for a in agents if a["agent"] == "researcher")
        planner = next(a for a in agents if a["agent"] == "planner")

        assert researcher["message"] == "Complete 1"
        assert planner["message"] == "Complete 1"


class TestParallelValidationTaskTool:
    """Test parallel validation phase (3 validators via Task tool).

    In /auto-implement, reviewer + security-auditor + doc-master run in parallel
    via Task tool. This is the most complex parallel scenario (3 agents).
    """

    @pytest.fixture
    def temp_session_dir(self, tmp_path):
        """Create temporary session directory."""
        session_dir = tmp_path / "docs" / "sessions"
        session_dir.mkdir(parents=True)
        return session_dir

    @pytest.fixture
    def session_file(self, temp_session_dir):
        """Create session with prior agents."""
        session_file = temp_session_dir / "test-session.json"
        session_data = {
            "session_id": "test-20251109-120000",
            "started": "2025-11-09T12:00:00",
            "agents": [
                {
                    "agent": "researcher",
                    "status": "completed",
                    "started_at": "2025-11-09T12:01:00",
                    "completed_at": "2025-11-09T12:05:00",
                    "duration_seconds": 240,
                    "message": "Research complete"
                },
                {
                    "agent": "planner",
                    "status": "completed",
                    "started_at": "2025-11-09T12:06:00",
                    "completed_at": "2025-11-09T12:10:00",
                    "duration_seconds": 240,
                    "message": "Plan complete"
                },
                {
                    "agent": "test-master",
                    "status": "completed",
                    "started_at": "2025-11-09T12:11:00",
                    "completed_at": "2025-11-09T12:15:00",
                    "duration_seconds": 240,
                    "message": "Tests written"
                },
                {
                    "agent": "implementer",
                    "status": "completed",
                    "started_at": "2025-11-09T12:16:00",
                    "completed_at": "2025-11-09T12:25:00",
                    "duration_seconds": 540,
                    "message": "Implementation complete"
                }
            ]
        }
        session_file.write_text(json.dumps(session_data, indent=2))
        return session_file

    def test_parallel_validation_all_three_agents_tracked(self, session_file):
        """Test all 3 validators tracked when invoked in parallel via Task tool.

        Workflow:
        1. First 4 agents already complete (researcher, planner, test-master, implementer)
        2. Claude invokes 3 validators in parallel via Task tool
        3. All 3 auto-detected via CLAUDE_AGENT_NAME
        4. All 3 appear in session

        Expected: Session has 7 agents total (4 prior + 3 validators).
        """
        tracker = AgentTracker(session_file=str(session_file))

        # Simulate 3 parallel Task tool invocations
        with patch.dict(os.environ, {"CLAUDE_AGENT_NAME": "reviewer"}):
            tracker.auto_track_from_environment(message="Code review started")

        with patch.dict(os.environ, {"CLAUDE_AGENT_NAME": "security-auditor"}):
            tracker.auto_track_from_environment(message="Security scan started")

        with patch.dict(os.environ, {"CLAUDE_AGENT_NAME": "doc-master"}):
            tracker.auto_track_from_environment(message="Documentation update started")

        # Verify all 7 agents in session
        session_data = json.loads(session_file.read_text())
        agents = session_data.get("agents", [])
        assert len(agents) == 7

        agent_names = {a["agent"] for a in agents}
        assert "reviewer" in agent_names
        assert "security-auditor" in agent_names
        assert "doc-master" in agent_names

    def test_parallel_validation_detect_parallel_execution(self, session_file):
        """Test verify_parallel_validation() detects 3 validators running in parallel.

        Workflow:
        1. All 3 validators auto-tracked within 5-second window
        2. verify_parallel_validation() method called
        3. Parallel execution detected

        Expected: Parallel validation detected (efficiency metrics calculated).

        NOTE: This test requires verify_parallel_validation() method from Issue #46 Phase 7.
        """
        tracker = AgentTracker(session_file=str(session_file))

        # Auto-track all 3 validators (simulating parallel start)
        with patch.dict(os.environ, {"CLAUDE_AGENT_NAME": "reviewer"}):
            tracker.auto_track_from_environment(message="Review")

        with patch.dict(os.environ, {"CLAUDE_AGENT_NAME": "security-auditor"}):
            tracker.auto_track_from_environment(message="Security")

        with patch.dict(os.environ, {"CLAUDE_AGENT_NAME": "doc-master"}):
            tracker.auto_track_from_environment(message="Docs")

        # Complete all 3
        tracker.complete_agent("reviewer", "Review complete", tools_used=["Read", "Grep"])
        tracker.complete_agent("security-auditor", "Security scan complete", tools_used=["Grep"])
        tracker.complete_agent("doc-master", "Docs updated", tools_used=["Read", "Edit"])

        # Verify parallel validation (requires verify_parallel_validation method)
        success = tracker.verify_parallel_validation()
        assert success is True, "Parallel validation should succeed with 3 agents"

        # Get detailed metrics (optional - for debugging)
        result = tracker.get_parallel_validation_metrics()
        assert result["parallel_detected"] is True
        assert result["agents_validated"] == ["reviewer", "security-auditor", "doc-master"]
        assert "efficiency_percent" in result
        assert result["efficiency_percent"] >= 0  # May be 0 for instant completion in tests


class TestFullAutoImplementWorkflow:
    """Test full /auto-implement workflow with Task tool agents.

    This tests the complete 7-agent pipeline with mixed invocation methods:
    - Some agents via Task tool (parallel)
    - Some agents manual (sequential)
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
            "session_id": "test-20251109-120000",
            "started": "2025-11-09T12:00:00",
            "agents": []
        }
        session_file.write_text(json.dumps(session_data, indent=2))
        return session_file

    def test_full_workflow_all_seven_agents_tracked(self, session_file):
        """Test complete /auto-implement workflow with Task tool detection.

        Workflow:
        1. researcher + planner (Task tool, parallel)
        2. test-master (manual)
        3. implementer (manual)
        4. reviewer + security-auditor + doc-master (Task tool, parallel)

        Expected: All 7 agents tracked correctly.
        """
        tracker = AgentTracker(session_file=str(session_file))

        # Phase 1: Parallel exploration (Task tool)
        with patch.dict(os.environ, {"CLAUDE_AGENT_NAME": "researcher"}):
            tracker.auto_track_from_environment(message="Research")
        with patch.dict(os.environ, {"CLAUDE_AGENT_NAME": "planner"}):
            tracker.auto_track_from_environment(message="Planning")

        # Complete phase 1
        tracker.complete_agent("researcher", "Complete")
        tracker.complete_agent("planner", "Complete")

        # Phase 2: Sequential TDD (manual tracking)
        tracker.start_agent("test-master", "Writing tests")
        tracker.complete_agent("test-master", "Tests written")

        tracker.start_agent("implementer", "Implementing")
        tracker.complete_agent("implementer", "Implementation complete")

        # Phase 3: Parallel validation (Task tool)
        with patch.dict(os.environ, {"CLAUDE_AGENT_NAME": "reviewer"}):
            tracker.auto_track_from_environment(message="Review")
        with patch.dict(os.environ, {"CLAUDE_AGENT_NAME": "security-auditor"}):
            tracker.auto_track_from_environment(message="Security")
        with patch.dict(os.environ, {"CLAUDE_AGENT_NAME": "doc-master"}):
            tracker.auto_track_from_environment(message="Docs")

        # Complete phase 3
        tracker.complete_agent("reviewer", "Review complete")
        tracker.complete_agent("security-auditor", "Security complete")
        tracker.complete_agent("doc-master", "Docs complete")

        # Verify all 7 agents tracked
        session_data = json.loads(session_file.read_text())
        agents = session_data.get("agents", [])
        assert len(agents) == 7

        expected_agents = [
            "researcher", "planner", "test-master", "implementer",
            "reviewer", "security-auditor", "doc-master"
        ]
        agent_names = [a["agent"] for a in agents]
        assert sorted(agent_names) == sorted(expected_agents)

        # All should be completed
        for agent in agents:
            assert agent["status"] == "completed"

    def test_full_workflow_pipeline_complete_check_passes(self, session_file):
        """Test check_pipeline_complete() returns True after all 7 agents.

        Expected: Pipeline validation hook passes.
        """
        from auto_update_project_progress import check_pipeline_complete

        tracker = AgentTracker(session_file=str(session_file))

        # Track all 7 agents (mixed Task tool + manual)
        with patch.dict(os.environ, {"CLAUDE_AGENT_NAME": "researcher"}):
            tracker.auto_track_from_environment(message="Research")
        tracker.complete_agent("researcher", "Complete")

        with patch.dict(os.environ, {"CLAUDE_AGENT_NAME": "planner"}):
            tracker.auto_track_from_environment(message="Planning")
        tracker.complete_agent("planner", "Complete")

        tracker.start_agent("test-master", "Tests")
        tracker.complete_agent("test-master", "Complete")

        tracker.start_agent("implementer", "Implement")
        tracker.complete_agent("implementer", "Complete")

        with patch.dict(os.environ, {"CLAUDE_AGENT_NAME": "reviewer"}):
            tracker.auto_track_from_environment(message="Review")
        tracker.complete_agent("reviewer", "Complete")

        with patch.dict(os.environ, {"CLAUDE_AGENT_NAME": "security-auditor"}):
            tracker.auto_track_from_environment(message="Security")
        tracker.complete_agent("security-auditor", "Complete")

        with patch.dict(os.environ, {"CLAUDE_AGENT_NAME": "doc-master"}):
            tracker.auto_track_from_environment(message="Docs")
        tracker.complete_agent("doc-master", "Complete")

        # Check pipeline complete
        assert check_pipeline_complete(session_file) is True


class TestMixedTrackingMethods:
    """Test workflows mixing Task tool and manual tracking.

    Real /auto-implement uses both methods. This ensures they work together.
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
            "session_id": "test-20251109-120000",
            "started": "2025-11-09T12:00:00",
            "agents": []
        }
        session_file.write_text(json.dumps(session_data, indent=2))
        return session_file

    def test_manual_start_then_task_tool_completion_blocked(self, session_file):
        """Test manual start + Task tool completion doesn't duplicate.

        Workflow:
        1. Agent started manually (start_agent)
        2. Agent invoked via Task tool (auto_track_from_environment)
        3. auto_track_from_environment returns False (already tracked)
        4. No duplicate entry created

        Expected: Only 1 entry in session.
        """
        tracker = AgentTracker(session_file=str(session_file))

        # Manual start
        tracker.start_agent("researcher", "Manual start")

        # Task tool tries to auto-track (should be blocked)
        with patch.dict(os.environ, {"CLAUDE_AGENT_NAME": "researcher"}):
            result = tracker.auto_track_from_environment(message="Task tool start")

        # Should return False (already tracked)
        assert result is False

        # Verify only 1 entry
        session_data = json.loads(session_file.read_text())
        agents = session_data.get("agents", [])
        assert len(agents) == 1
        assert agents[0]["message"] == "Manual start"  # Original preserved

    def test_task_tool_start_then_manual_completion_works(self, session_file):
        """Test Task tool start + manual completion works.

        Workflow:
        1. Agent started via Task tool (auto_track_from_environment)
        2. Agent completed manually (complete_agent)
        3. Completion succeeds

        Expected: Agent marked completed.
        """
        tracker = AgentTracker(session_file=str(session_file))

        # Task tool start
        with patch.dict(os.environ, {"CLAUDE_AGENT_NAME": "planner"}):
            result = tracker.auto_track_from_environment(message="Task tool start")
        assert result is True

        # Manual completion
        tracker.complete_agent("planner", "Manual completion")

        # Verify completed
        session_data = json.loads(session_file.read_text())
        agents = session_data.get("agents", [])
        assert len(agents) == 1
        assert agents[0]["status"] == "completed"
        assert agents[0]["message"] == "Manual completion"

    def test_mixed_methods_preserve_chronological_order(self, session_file):
        """Test agents appear in chronological order regardless of tracking method.

        Workflow:
        1. Manual start (researcher)
        2. Task tool start (planner)
        3. Manual start (test-master)
        4. Task tool start (implementer)

        Expected: Agents in session match chronological order.
        """
        tracker = AgentTracker(session_file=str(session_file))

        # Mixed invocations
        tracker.start_agent("researcher", "Manual 1")

        with patch.dict(os.environ, {"CLAUDE_AGENT_NAME": "planner"}):
            tracker.auto_track_from_environment(message="Task tool 1")

        tracker.start_agent("test-master", "Manual 2")

        with patch.dict(os.environ, {"CLAUDE_AGENT_NAME": "implementer"}):
            tracker.auto_track_from_environment(message="Task tool 2")

        # Verify order
        session_data = json.loads(session_file.read_text())
        agents = session_data.get("agents", [])
        assert len(agents) == 4

        agent_names = [a["agent"] for a in agents]
        assert agent_names == ["researcher", "planner", "test-master", "implementer"]


class TestSessionFileConsistency:
    """Test session file remains consistent across Task tool invocations.

    Focus on data integrity, race conditions, atomic writes.
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
            "session_id": "test-20251109-120000",
            "started": "2025-11-09T12:00:00",
            "agents": []
        }
        session_file.write_text(json.dumps(session_data, indent=2))
        return session_file

    def test_session_file_valid_json_after_auto_tracking(self, session_file):
        """Test session file remains valid JSON after auto-tracking.

        Expected: File can be parsed as JSON after each operation.
        """
        tracker = AgentTracker(session_file=str(session_file))

        # Multiple auto-track operations
        for agent_name in ["researcher", "planner", "test-master"]:
            with patch.dict(os.environ, {"CLAUDE_AGENT_NAME": agent_name}):
                tracker.auto_track_from_environment(message=f"Tracking {agent_name}")

            # Verify JSON valid after each operation
            session_data = json.loads(session_file.read_text())
            assert "agents" in session_data

    def test_session_file_preserves_existing_data_on_auto_track(self, session_file):
        """Test auto-tracking doesn't corrupt existing session data.

        Expected: Prior agents preserved when new agent auto-tracked.
        """
        tracker = AgentTracker(session_file=str(session_file))

        # Add first agent manually
        tracker.start_agent("researcher", "Manual start")
        tracker.complete_agent("researcher", "Manual complete")

        # Auto-track second agent via Task tool
        with patch.dict(os.environ, {"CLAUDE_AGENT_NAME": "planner"}):
            tracker.auto_track_from_environment(message="Task tool start")

        # Verify first agent data preserved
        session_data = json.loads(session_file.read_text())
        agents = session_data.get("agents", [])
        assert len(agents) == 2

        researcher = next(a for a in agents if a["agent"] == "researcher")
        assert researcher["status"] == "completed"
        assert researcher["message"] == "Manual complete"

    def test_session_metadata_preserved_during_auto_tracking(self, session_file):
        """Test session metadata (session_id, started) preserved.

        Expected: Metadata unchanged after auto-tracking.
        """
        # Read original metadata
        original_data = json.loads(session_file.read_text())
        original_session_id = original_data["session_id"]
        original_started = original_data["started"]

        tracker = AgentTracker(session_file=str(session_file))

        # Auto-track multiple agents
        for agent in ["researcher", "planner", "test-master"]:
            with patch.dict(os.environ, {"CLAUDE_AGENT_NAME": agent}):
                tracker.auto_track_from_environment(message="Tracking")

        # Verify metadata unchanged
        session_data = json.loads(session_file.read_text())
        assert session_data["session_id"] == original_session_id
        assert session_data["started"] == original_started


# Run tests if executed directly
if __name__ == "__main__":
    pytest.main([__file__, "-v"])
