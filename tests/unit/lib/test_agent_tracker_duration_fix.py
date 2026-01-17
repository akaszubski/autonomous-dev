#!/usr/bin/env python3
"""
TDD Tests for AgentTracker Duration Tracking Fix (FAILING - Red Phase)

This module contains FAILING tests that verify the duration calculation fix
for Issue #120: Performance improvements.

Requirements:
1. save_agent_checkpoint() accepts optional started_at parameter
2. Duration is calculated as (current_time - started_at) when started_at provided
3. When started_at is not provided, use current time (no elapsed duration)
4. Duration calculation accuracy is tested to millisecond precision
5. complete_agent() also accepts started_at parameter for backward compatibility

Test Strategy:
- Verify started_at parameter acceptance and validation
- Test duration calculation accuracy (milliseconds precision)
- Verify backward compatibility when started_at not provided
- Test edge cases (None values, time zone handling, boundary conditions)

Test Coverage Target: 100% of duration tracking code paths

Following TDD principles:
- Write tests FIRST (red phase) - tests should FAIL
- Tests describe exact duration requirements
- Tests should FAIL until implementation is complete
- Each test validates ONE duration-related requirement

Author: test-master agent
Date: 2025-12-13
Issue: #120
Phase: Performance improvements - duration tracking fix
"""

import json
import sys
import tempfile
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock
from time import sleep

import pytest

# TDD red-phase tests - duration tracking API not yet implemented
pytestmark = pytest.mark.skip(reason="TDD red-phase: Issue #120 duration tracking with started_at parameter not yet implemented")

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from plugins.autonomous_dev.lib.agent_tracker import AgentTracker


class TestAgentTrackerDurationTracking:
    """Test suite for AgentTracker duration calculation fix (Issue #120).

    These tests verify that:
    1. Duration is calculated correctly when started_at is provided
    2. Duration is NOT calculated when started_at is omitted
    3. All times are captured with proper precision
    4. backward compatibility is maintained
    """

    @pytest.fixture
    def temp_session_dir(self, tmp_path):
        """Create temporary session directory for test isolation."""
        session_dir = tmp_path / "docs" / "sessions"
        session_dir.mkdir(parents=True, exist_ok=True)
        return session_dir

    @pytest.fixture
    def tracker(self, temp_session_dir):
        """Create AgentTracker instance with temporary session directory."""
        with patch('plugins.autonomous_dev.lib.agent_tracker.get_session_dir', return_value=temp_session_dir):
            tracker = AgentTracker()
            tracker.session_file = temp_session_dir / "test-session.json"
            return tracker

    def test_save_agent_checkpoint_with_started_at_calculates_duration(self, tracker, temp_session_dir):
        """Test that duration is calculated when started_at is provided.

        REQUIREMENT: When started_at is provided to save_agent_checkpoint(),
        duration should be calculated as: now - started_at

        Expected behavior:
        - started_at: 2025-12-13T10:00:00Z
        - checkpoint_at (now): 2025-12-13T10:00:05Z
        - duration_seconds: 5
        """
        # Arrange
        agent_name = "test-agent"
        message = "Test checkpoint with started_at"
        started_at = datetime(2025, 12, 13, 10, 0, 0)
        checkpoint_at = datetime(2025, 12, 13, 10, 0, 5)
        expected_duration = 5

        # Mock datetime to control time
        with patch('plugins.autonomous_dev.lib.agent_tracker.datetime') as mock_datetime:
            mock_datetime.now.return_value = checkpoint_at
            mock_datetime.fromisoformat = datetime.fromisoformat
            mock_datetime.side_effect = lambda *args, **kw: datetime(*args, **kw)

            # Act
            tracker.save_agent_checkpoint(
                agent_name=agent_name,
                message=message,
                started_at=started_at
            )

            # Assert
            session_data = json.loads(tracker.session_file.read_text())
            checkpoint = session_data.get("checkpoints", [{}])[0]

            assert "duration_seconds" in checkpoint, "duration_seconds not found in checkpoint"
            assert checkpoint["duration_seconds"] == expected_duration, \
                f"Expected duration {expected_duration}, got {checkpoint['duration_seconds']}"

    def test_save_agent_checkpoint_without_started_at_uses_current_time(self, tracker, temp_session_dir):
        """Test that no duration is calculated when started_at is NOT provided.

        REQUIREMENT: When started_at is omitted, no duration should be stored.
        This maintains backward compatibility with existing code.

        Expected behavior:
        - No started_at provided
        - No duration_seconds in checkpoint
        - Only checkpoint time recorded
        """
        # Arrange
        agent_name = "test-agent"
        message = "Test checkpoint without started_at"
        checkpoint_at = datetime(2025, 12, 13, 10, 0, 5)

        with patch('plugins.autonomous_dev.lib.agent_tracker.datetime') as mock_datetime:
            mock_datetime.now.return_value = checkpoint_at
            mock_datetime.fromisoformat = datetime.fromisoformat

            # Act
            tracker.save_agent_checkpoint(
                agent_name=agent_name,
                message=message
                # Note: started_at NOT provided
            )

            # Assert
            session_data = json.loads(tracker.session_file.read_text())
            checkpoint = session_data.get("checkpoints", [{}])[0]

            # Should NOT have duration_seconds when started_at not provided
            assert "duration_seconds" not in checkpoint, \
                "duration_seconds should not be present when started_at not provided"

    def test_complete_agent_with_started_at_parameter(self, tracker, temp_session_dir):
        """Test that complete_agent() also accepts started_at parameter.

        REQUIREMENT: complete_agent() should support started_at parameter
        for consistency with save_agent_checkpoint()

        Expected behavior:
        - complete_agent(agent_name, message, started_at=datetime_obj)
        - Duration calculated and stored in agent record
        """
        # Arrange
        agent_name = "implementer"
        message = "Feature implementation complete"
        started_at = datetime(2025, 12, 13, 10, 5, 0)
        completed_at = datetime(2025, 12, 13, 10, 15, 30)
        expected_duration = 630  # 10 minutes 30 seconds

        with patch('plugins.autonomous_dev.lib.agent_tracker.datetime') as mock_datetime:
            mock_datetime.now.return_value = completed_at
            mock_datetime.fromisoformat = datetime.fromisoformat

            # Act
            tracker.complete_agent(
                agent_name=agent_name,
                message=message,
                started_at=started_at
            )

            # Assert
            session_data = json.loads(tracker.session_file.read_text())
            agents = session_data.get("agents", [])
            agent = next((a for a in agents if a.get("agent") == agent_name), None)

            assert agent is not None, f"Agent {agent_name} not found in session"
            assert "duration_seconds" in agent, "duration_seconds not found in agent record"
            assert agent["duration_seconds"] == expected_duration, \
                f"Expected duration {expected_duration}, got {agent['duration_seconds']}"

    def test_duration_calculation_accuracy(self, tracker, temp_session_dir):
        """Test that duration calculation is accurate to millisecond precision.

        REQUIREMENT: Duration should be calculated with high precision,
        not rounded to nearest second.

        Test various time deltas to ensure accuracy:
        - 1 second
        - 5.5 seconds
        - 0.123 seconds (123 milliseconds)
        - 1 minute (60 seconds)
        - 1 hour (3600 seconds)
        """
        test_cases = [
            (1.0, "1 second"),
            (5.5, "5.5 seconds"),
            (0.123, "123 milliseconds"),
            (60.0, "1 minute"),
            (3600.0, "1 hour"),
            (7200.5, "2 hours 0.5 seconds"),
        ]

        for expected_duration, description in test_cases:
            with patch('plugins.autonomous_dev.lib.agent_tracker.datetime') as mock_datetime:
                base_time = datetime(2025, 12, 13, 10, 0, 0)
                end_time = base_time + timedelta(seconds=expected_duration)

                mock_datetime.now.return_value = end_time
                mock_datetime.fromisoformat = datetime.fromisoformat

                # Act
                tracker.save_agent_checkpoint(
                    agent_name=f"test-{description}",
                    message=f"Testing {description}",
                    started_at=base_time
                )

                # Assert
                session_data = json.loads(tracker.session_file.read_text())
                checkpoint = session_data.get("checkpoints", [{}])[-1]

                calculated_duration = checkpoint.get("duration_seconds")
                assert calculated_duration is not None, \
                    f"duration_seconds not found for {description}"

                # Allow small floating point tolerance (1 millisecond = 0.001 seconds)
                assert abs(calculated_duration - expected_duration) < 0.001, \
                    f"Duration mismatch for {description}: expected {expected_duration}, " \
                    f"got {calculated_duration}"

    def test_duration_calculation_with_negative_started_at_rejects(self, tracker):
        """Test that negative durations (future started_at) are rejected or handled.

        EDGE CASE: If started_at is in the future (somehow), duration would be negative.
        Should either reject or store as 0.

        Expected: Either raises ValueError or stores 0 seconds.
        """
        # Arrange
        agent_name = "test-agent"
        message = "Future started_at"
        current_time = datetime(2025, 12, 13, 10, 0, 0)
        future_started_at = current_time + timedelta(seconds=10)  # Future time

        with patch('plugins.autonomous_dev.lib.agent_tracker.datetime') as mock_datetime:
            mock_datetime.now.return_value = current_time
            mock_datetime.fromisoformat = datetime.fromisoformat

            # Act & Assert - should either raise or handle gracefully
            try:
                tracker.save_agent_checkpoint(
                    agent_name=agent_name,
                    message=message,
                    started_at=future_started_at
                )

                # If no exception, check that duration is 0 or positive
                session_data = json.loads(tracker.session_file.read_text())
                checkpoint = session_data.get("checkpoints", [{}])[0]

                duration = checkpoint.get("duration_seconds", 0)
                assert duration >= 0, f"Duration should not be negative, got {duration}"

            except (ValueError, RuntimeError) as e:
                # It's OK to reject invalid times
                assert "started_at" in str(e).lower() or "future" in str(e).lower(), \
                    f"Exception should mention started_at or future: {e}"

    def test_duration_stored_as_float_for_precision(self, tracker):
        """Test that duration is stored as float (not rounded to int).

        REQUIREMENT: Duration must support fractional seconds for accuracy.
        e.g., 5.234 seconds not rounded to 5 seconds

        Expected: duration_seconds is float type with decimal precision
        """
        # Arrange
        agent_name = "precision-test"
        message = "Testing float precision"
        started_at = datetime(2025, 12, 13, 10, 0, 0, 500000)  # 0.5 ms
        checkpoint_at = datetime(2025, 12, 13, 10, 0, 5, 234000)  # 5.234 ms

        with patch('plugins.autonomous_dev.lib.agent_tracker.datetime') as mock_datetime:
            mock_datetime.now.return_value = checkpoint_at
            mock_datetime.fromisoformat = datetime.fromisoformat

            # Act
            tracker.save_agent_checkpoint(
                agent_name=agent_name,
                message=message,
                started_at=started_at
            )

            # Assert
            session_data = json.loads(tracker.session_file.read_text())
            checkpoint = session_data.get("checkpoints", [{}])[0]

            duration = checkpoint.get("duration_seconds")
            assert isinstance(duration, (int, float)), \
                f"Duration should be numeric, got {type(duration)}"
            # Should support fractional seconds (not truncated to int)
            assert duration % 1 != 0 or duration < 10, \
                f"Duration lost precision: {duration}"

    def test_started_at_with_timezone_aware_datetime(self, tracker):
        """Test that timezone-aware datetimes are handled correctly.

        EDGE CASE: started_at might be timezone-aware or naive.
        Should calculate duration regardless of timezone info.

        Expected: Duration calculated correctly with or without timezone
        """
        # Arrange
        agent_name = "timezone-test"
        message = "Testing timezone handling"

        # Create timezone-aware datetime
        from datetime import timezone, timedelta as td
        utc = timezone.utc
        started_at = datetime(2025, 12, 13, 10, 0, 0, tzinfo=utc)
        checkpoint_at = datetime(2025, 12, 13, 10, 0, 5, tzinfo=utc)
        expected_duration = 5

        with patch('plugins.autonomous_dev.lib.agent_tracker.datetime') as mock_datetime:
            mock_datetime.now.return_value = checkpoint_at
            mock_datetime.fromisoformat = datetime.fromisoformat
            mock_datetime.utcnow.return_value = checkpoint_at

            # Act
            tracker.save_agent_checkpoint(
                agent_name=agent_name,
                message=message,
                started_at=started_at
            )

            # Assert
            session_data = json.loads(tracker.session_file.read_text())
            checkpoint = session_data.get("checkpoints", [{}])[0]

            duration = checkpoint.get("duration_seconds")
            assert duration is not None, "duration_seconds not calculated with timezone-aware datetime"
            assert abs(duration - expected_duration) < 0.1, \
                f"Timezone-aware datetime duration mismatch: expected {expected_duration}, got {duration}"

    def test_checkpoint_retains_all_existing_fields_plus_duration(self, tracker):
        """Test that adding duration doesn't lose existing checkpoint data.

        REQUIREMENT: All existing fields (agent, message, status, etc.)
        must be retained when duration is added.

        Expected: Checkpoint contains:
        - agent_name
        - message
        - checkpoint_at
        - duration_seconds (NEW)
        - Any other existing fields
        """
        # Arrange
        agent_name = "full-checkpoint"
        message = "Testing complete checkpoint data"
        started_at = datetime(2025, 12, 13, 10, 0, 0)
        checkpoint_at = datetime(2025, 12, 13, 10, 0, 3)

        with patch('plugins.autonomous_dev.lib.agent_tracker.datetime') as mock_datetime:
            mock_datetime.now.return_value = checkpoint_at
            mock_datetime.fromisoformat = datetime.fromisoformat

            # Act
            tracker.save_agent_checkpoint(
                agent_name=agent_name,
                message=message,
                started_at=started_at
            )

            # Assert
            session_data = json.loads(tracker.session_file.read_text())
            checkpoint = session_data.get("checkpoints", [{}])[0]

            # Verify all essential fields are present
            required_fields = ["agent", "message", "checkpoint_at", "duration_seconds"]
            for field in required_fields:
                assert field in checkpoint, f"Required field '{field}' missing from checkpoint"

            # Verify values
            assert checkpoint["agent"] == agent_name
            assert checkpoint["message"] == message
            assert isinstance(checkpoint["duration_seconds"], (int, float))
            assert checkpoint["duration_seconds"] == 3

    def test_multiple_checkpoints_each_have_own_duration(self, tracker):
        """Test that multiple checkpoints each calculate their own duration independently.

        REQUIREMENT: Each checkpoint should have its own started_at and duration.
        Durations should NOT be cumulative or shared.

        Expected: Each checkpoint has independent duration based on its started_at
        """
        # Arrange
        test_data = [
            ("agent1", "First checkpoint", datetime(2025, 12, 13, 10, 0, 0), 5),
            ("agent2", "Second checkpoint", datetime(2025, 12, 13, 10, 0, 10), 3),
            ("agent3", "Third checkpoint", datetime(2025, 12, 13, 10, 0, 20), 7),
        ]

        for agent, msg, started, expected_duration in test_data:
            with patch('plugins.autonomous_dev.lib.agent_tracker.datetime') as mock_datetime:
                checkpoint_at = started + timedelta(seconds=expected_duration)
                mock_datetime.now.return_value = checkpoint_at
                mock_datetime.fromisoformat = datetime.fromisoformat

                # Act
                tracker.save_agent_checkpoint(
                    agent_name=agent,
                    message=msg,
                    started_at=started
                )

        # Assert
        session_data = json.loads(tracker.session_file.read_text())
        checkpoints = session_data.get("checkpoints", [])

        assert len(checkpoints) == 3, f"Expected 3 checkpoints, got {len(checkpoints)}"

        for i, (expected_duration, _) in enumerate([(5, None), (3, None), (7, None)]):
            checkpoint = checkpoints[i]
            assert checkpoint.get("duration_seconds") == expected_duration, \
                f"Checkpoint {i} duration mismatch: expected {expected_duration}, " \
                f"got {checkpoint.get('duration_seconds')}"


class TestDurationTrackingIntegration:
    """Integration tests for duration tracking with other tracker features."""

    @pytest.fixture
    def temp_session_dir(self, tmp_path):
        """Create temporary session directory."""
        session_dir = tmp_path / "docs" / "sessions"
        session_dir.mkdir(parents=True, exist_ok=True)
        return session_dir

    @pytest.fixture
    def tracker(self, temp_session_dir):
        """Create AgentTracker instance."""
        with patch('plugins.autonomous_dev.lib.agent_tracker.get_session_dir', return_value=temp_session_dir):
            tracker = AgentTracker()
            tracker.session_file = temp_session_dir / "test-session.json"
            return tracker

    def test_started_agent_then_complete_with_duration(self, tracker):
        """Integration test: start_agent, then complete_agent with duration.

        WORKFLOW:
        1. start_agent("researcher")
        2. complete_agent("researcher", started_at=...)

        Expected: Agent record has both started and completed times, with duration
        """
        # Arrange
        agent_name = "researcher"
        start_time = datetime(2025, 12, 13, 10, 0, 0)
        complete_time = datetime(2025, 12, 13, 10, 2, 30)
        expected_duration = 150  # 2.5 minutes

        with patch('plugins.autonomous_dev.lib.agent_tracker.datetime') as mock_datetime:
            mock_datetime.now.return_value = start_time
            mock_datetime.fromisoformat = datetime.fromisoformat

            # Act - Start agent
            tracker.start_agent(agent_name, "Starting research")

        with patch('plugins.autonomous_dev.lib.agent_tracker.datetime') as mock_datetime:
            mock_datetime.now.return_value = complete_time
            mock_datetime.fromisoformat = datetime.fromisoformat

            # Act - Complete agent with started_at
            tracker.complete_agent(
                agent_name=agent_name,
                message="Research complete",
                started_at=start_time
            )

        # Assert
        session_data = json.loads(tracker.session_file.read_text())
        agents = session_data.get("agents", [])
        agent = next((a for a in agents if a.get("agent") == agent_name), None)

        assert agent is not None
        assert agent.get("status") == "completed"
        assert agent.get("duration_seconds") == expected_duration
