#!/usr/bin/env python3
"""
TDD Tests for Parallel Exploration Logic (Issue #46 Phase 2)

This module contains FAILING tests (TDD red phase) for parallel research+planning:
- verify_parallel_exploration() function in agent_tracker.py
- Parallelization efficiency calculations
- Sequential fallback detection
- Timing validation and edge cases

These tests WILL FAIL until the implementation is complete.

Phase 2 Requirements:
1. Parallelize researcher + planner agents (STEP 1-2)
2. Verify both completed in verify_parallel_exploration()
3. Calculate parallelization efficiency (time saved)
4. Graceful fallback to sequential if parallel fails
5. Target: 3-8 minute savings (from 6-13 minute sequential)

Test Coverage Target: 100% of verify_parallel_exploration() code paths

Date: 2025-11-07
Workflow: phase2_parallel_exploration
Agent: test-master
"""

import json
import os
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock, call
import pytest

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from scripts.agent_tracker import AgentTracker


class TestVerifyParallelExplorationBasics:
    """Test basic verify_parallel_exploration() functionality."""

    @pytest.fixture
    def temp_session_dir(self, tmp_path):
        """Create temporary session directory."""
        session_dir = tmp_path / "docs" / "sessions"
        session_dir.mkdir(parents=True)
        return session_dir

    @pytest.fixture
    def mock_session_file(self, temp_session_dir):
        """Create a mock session file with base data."""
        session_file = temp_session_dir / "session_test.json"
        session_data = {
            "session_id": "20251107-phase2-test",
            "started": "2025-11-07T10:00:00",
            "agents": []
        }
        session_file.write_text(json.dumps(session_data, indent=2))
        return session_file

    def test_verify_parallel_exploration_both_completed(self, mock_session_file):
        """
        Test verify_parallel_exploration() when both researcher and planner completed in parallel.

        Given: Session file with researcher and planner both completed
        And: Start times within 5 seconds of each other (parallel execution)
        When: verify_parallel_exploration() is called
        Then: Returns True (parallel execution verified)
        And: Logs parallelization efficiency metrics

        Protects: Phase 2 core verification logic
        """
        # Arrange: Create session with parallel execution
        tracker = AgentTracker(session_file=str(mock_session_file))

        base_time = datetime.now()

        # Researcher starts at T+0
        tracker.log_start("researcher", "Research starting")
        researcher_start = datetime.now()

        # Planner starts at T+2 (within 5 second window = parallel)
        time.sleep(0.01)  # Small delay to ensure different timestamps
        tracker.log_start("planner", "Planning starting")
        planner_start = datetime.now()

        # Both complete
        tracker.log_complete("researcher", "Research complete", tools_used=["WebSearch", "Grep"])
        tracker.log_complete("planner", "Planning complete", tools_used=["Read", "Edit"])

        # Act: Verify parallel exploration
        # NOTE: This WILL FAIL - function doesn't exist yet
        result = tracker.verify_parallel_exploration()

        # Assert: Parallel execution verified
        assert result is True, "Expected verify_parallel_exploration to return True for parallel execution"

        # Verify metrics were calculated
        session_data = json.loads(mock_session_file.read_text())
        assert "parallel_exploration" in session_data, "Expected parallel_exploration metrics in session"
        assert session_data["parallel_exploration"]["status"] == "parallel"
        # Note: time_saved can be 0 if both agents complete instantly (test environment)
        assert session_data["parallel_exploration"]["time_saved_seconds"] >= 0

    def test_verify_parallel_exploration_missing_researcher(self, mock_session_file):
        """
        Test verify_parallel_exploration() when researcher is missing.

        Given: Session file with only planner completed
        When: verify_parallel_exploration() is called
        Then: Returns False (incomplete exploration)
        And: Logs warning about missing researcher

        Protects: Phase 2 validation completeness
        """
        # Arrange: Only planner completed
        tracker = AgentTracker(session_file=str(mock_session_file))
        tracker.log_start("planner", "Planning starting")
        tracker.log_complete("planner", "Planning complete", tools_used=["Read"])

        # Act: Verify parallel exploration
        # NOTE: This WILL FAIL - function doesn't exist yet
        result = tracker.verify_parallel_exploration()

        # Assert: Incomplete exploration detected
        assert result is False, "Expected verify_parallel_exploration to return False when researcher missing"

        # Verify error logged
        session_data = json.loads(mock_session_file.read_text())
        assert "parallel_exploration" in session_data
        assert session_data["parallel_exploration"]["status"] == "incomplete"
        assert "researcher" in session_data["parallel_exploration"]["missing_agents"]

    def test_verify_parallel_exploration_missing_planner(self, mock_session_file):
        """
        Test verify_parallel_exploration() when planner is missing.

        Given: Session file with only researcher completed
        When: verify_parallel_exploration() is called
        Then: Returns False (incomplete exploration)
        And: Logs warning about missing planner

        Protects: Phase 2 validation completeness
        """
        # Arrange: Only researcher completed
        tracker = AgentTracker(session_file=str(mock_session_file))
        tracker.log_start("researcher", "Research starting")
        tracker.log_complete("researcher", "Research complete", tools_used=["WebSearch"])

        # Act: Verify parallel exploration
        # NOTE: This WILL FAIL - function doesn't exist yet
        result = tracker.verify_parallel_exploration()

        # Assert: Incomplete exploration detected
        assert result is False, "Expected verify_parallel_exploration to return False when planner missing"

        # Verify error logged
        session_data = json.loads(mock_session_file.read_text())
        assert "parallel_exploration" in session_data
        assert session_data["parallel_exploration"]["status"] == "incomplete"
        assert "planner" in session_data["parallel_exploration"]["missing_agents"]

    def test_parallelization_efficiency_calculation(self, mock_session_file):
        """
        Test parallelization efficiency calculation.

        Given: Researcher took 6 minutes, planner took 7 minutes
        And: Both ran in parallel (max 7 minutes total)
        When: verify_parallel_exploration() calculates efficiency
        Then: Time saved = 6 minutes (13 min sequential - 7 min parallel)
        And: Efficiency = 46% ((6/13) * 100)

        Protects: Phase 2 metrics accuracy
        """
        # Arrange: Create session with known durations
        tracker = AgentTracker(session_file=str(mock_session_file))

        # Researcher: 6 minutes
        tracker.log_start("researcher", "Research starting")
        time.sleep(0.01)
        session_data = json.loads(mock_session_file.read_text())
        researcher_idx = len(session_data["agents"]) - 1

        # Planner: 7 minutes (starts at same time)
        tracker.log_start("planner", "Planning starting")

        # Manually set durations for testing
        session_data = json.loads(mock_session_file.read_text())
        base_time = datetime.now()
        session_data["agents"][researcher_idx]["started_at"] = base_time.isoformat()
        session_data["agents"][researcher_idx]["completed_at"] = (base_time + timedelta(minutes=6)).isoformat()
        session_data["agents"][researcher_idx]["duration_seconds"] = 360
        session_data["agents"][researcher_idx]["status"] = "completed"

        planner_idx = researcher_idx + 1
        session_data["agents"][planner_idx]["started_at"] = base_time.isoformat()
        session_data["agents"][planner_idx]["completed_at"] = (base_time + timedelta(minutes=7)).isoformat()
        session_data["agents"][planner_idx]["duration_seconds"] = 420
        session_data["agents"][planner_idx]["status"] = "completed"

        mock_session_file.write_text(json.dumps(session_data, indent=2))

        # Act: Verify parallel exploration
        # NOTE: This WILL FAIL - function doesn't exist yet
        result = tracker.verify_parallel_exploration()

        # Assert: Efficiency calculated correctly
        session_data = json.loads(mock_session_file.read_text())
        parallel_data = session_data["parallel_exploration"]

        assert parallel_data["sequential_time_seconds"] == 780  # 6 + 7 minutes = 780 seconds
        assert parallel_data["parallel_time_seconds"] == 420  # max(6, 7) = 7 minutes = 420 seconds
        assert parallel_data["time_saved_seconds"] == 360  # 780 - 420 = 360 seconds (6 minutes)
        assert parallel_data["efficiency_percent"] == pytest.approx(46.15, rel=1e-2)  # (360/780) * 100

    def test_sequential_execution_detected(self, mock_session_file):
        """
        Test detection of sequential (not parallel) execution.

        Given: Researcher completes at T+6min, planner starts at T+6min
        And: Start times differ by > 5 seconds (sequential execution)
        When: verify_parallel_exploration() is called
        Then: Returns True (both completed) but logs sequential execution
        And: time_saved_seconds = 0 (no parallelization benefit)

        Protects: Phase 2 accurate detection of sequential fallback
        """
        # Arrange: Create session with sequential execution
        tracker = AgentTracker(session_file=str(mock_session_file))

        base_time = datetime.now()

        # Researcher completes first
        tracker.log_start("researcher", "Research starting")
        session_data = json.loads(mock_session_file.read_text())
        researcher_idx = len(session_data["agents"]) - 1
        session_data["agents"][researcher_idx]["started_at"] = base_time.isoformat()
        session_data["agents"][researcher_idx]["completed_at"] = (base_time + timedelta(minutes=6)).isoformat()
        session_data["agents"][researcher_idx]["duration_seconds"] = 360
        session_data["agents"][researcher_idx]["status"] = "completed"
        mock_session_file.write_text(json.dumps(session_data, indent=2))

        # Planner starts AFTER researcher completes (sequential)
        time.sleep(0.02)  # Simulate delay
        tracker.log_start("planner", "Planning starting")
        session_data = json.loads(mock_session_file.read_text())

        # Fix: log_start("planner") overwrote researcher to "started", so restore it
        researcher_idx = 0
        session_data["agents"][researcher_idx]["started_at"] = base_time.isoformat()
        session_data["agents"][researcher_idx]["completed_at"] = (base_time + timedelta(minutes=6)).isoformat()
        session_data["agents"][researcher_idx]["duration_seconds"] = 360
        session_data["agents"][researcher_idx]["status"] = "completed"

        planner_idx = len(session_data["agents"]) - 1
        session_data["agents"][planner_idx]["started_at"] = (base_time + timedelta(minutes=6, seconds=10)).isoformat()
        session_data["agents"][planner_idx]["completed_at"] = (base_time + timedelta(minutes=13)).isoformat()
        session_data["agents"][planner_idx]["duration_seconds"] = 420
        session_data["agents"][planner_idx]["status"] = "completed"
        mock_session_file.write_text(json.dumps(session_data, indent=2))

        # Act: Verify parallel exploration
        # NOTE: This WILL FAIL - function doesn't exist yet
        result = tracker.verify_parallel_exploration()

        # Assert: Sequential execution detected
        assert result is True, "Both agents completed, should return True"

        session_data = json.loads(mock_session_file.read_text())
        parallel_data = session_data["parallel_exploration"]

        assert parallel_data["status"] == "sequential", "Expected sequential execution status"
        assert parallel_data["time_saved_seconds"] == 0, "No time saved in sequential execution"


class TestVerifyParallelExplorationEdgeCases:
    """Test edge cases and error conditions."""

    @pytest.fixture
    def temp_session_dir(self, tmp_path):
        """Create temporary session directory."""
        session_dir = tmp_path / "docs" / "sessions"
        session_dir.mkdir(parents=True)
        return session_dir

    @pytest.fixture
    def mock_session_file(self, temp_session_dir):
        """Create a mock session file with base data."""
        session_file = temp_session_dir / "session_test.json"
        session_data = {
            "session_id": "20251107-phase2-test",
            "started": "2025-11-07T10:00:00",
            "agents": []
        }
        session_file.write_text(json.dumps(session_data, indent=2))
        return session_file

    def test_verify_parallel_exploration_with_failed_researcher(self, mock_session_file):
        """
        Test verify_parallel_exploration() when researcher failed.

        Given: Researcher failed, planner completed
        When: verify_parallel_exploration() is called
        Then: Returns False (incomplete exploration)
        And: Logs failure reason

        Protects: Phase 2 failure handling
        """
        # Arrange: Researcher failed
        tracker = AgentTracker(session_file=str(mock_session_file))
        tracker.log_start("researcher", "Research starting")
        tracker.log_fail("researcher", "Research failed: API timeout")
        tracker.log_start("planner", "Planning starting")
        tracker.log_complete("planner", "Planning complete", tools_used=["Read"])

        # Act: Verify parallel exploration
        # NOTE: This WILL FAIL - function doesn't exist yet
        result = tracker.verify_parallel_exploration()

        # Assert: Failure detected
        assert result is False, "Expected False when researcher failed"

        session_data = json.loads(mock_session_file.read_text())
        assert session_data["parallel_exploration"]["status"] == "failed"
        assert "researcher" in session_data["parallel_exploration"]["failed_agents"]

    def test_verify_parallel_exploration_with_failed_planner(self, mock_session_file):
        """
        Test verify_parallel_exploration() when planner failed.

        Given: Researcher completed, planner failed
        When: verify_parallel_exploration() is called
        Then: Returns False (incomplete exploration)
        And: Logs failure reason

        Protects: Phase 2 failure handling
        """
        # Arrange: Planner failed
        tracker = AgentTracker(session_file=str(mock_session_file))
        tracker.log_start("researcher", "Research starting")
        tracker.log_complete("researcher", "Research complete", tools_used=["WebSearch"])
        tracker.log_start("planner", "Planning starting")
        tracker.log_fail("planner", "Planning failed: Invalid architecture")

        # Act: Verify parallel exploration
        # NOTE: This WILL FAIL - function doesn't exist yet
        result = tracker.verify_parallel_exploration()

        # Assert: Failure detected
        assert result is False, "Expected False when planner failed"

        session_data = json.loads(mock_session_file.read_text())
        assert session_data["parallel_exploration"]["status"] == "failed"
        assert "planner" in session_data["parallel_exploration"]["failed_agents"]

    def test_verify_parallel_exploration_with_invalid_timestamps(self, mock_session_file):
        """
        Test verify_parallel_exploration() with invalid timestamp formats.

        Given: Session file with malformed timestamp data
        When: verify_parallel_exploration() is called
        Then: Raises ValueError with clear error message
        And: Logs security audit entry

        Protects: Phase 2 input validation
        """
        # Arrange: Create session with invalid timestamps
        tracker = AgentTracker(session_file=str(mock_session_file))
        session_data = json.loads(mock_session_file.read_text())
        session_data["agents"] = [
            {
                "agent": "researcher",
                "status": "completed",
                "started_at": "INVALID_TIMESTAMP",
                "completed_at": "2025-11-07T10:05:00"
            },
            {
                "agent": "planner",
                "status": "completed",
                "started_at": "2025-11-07T10:00:00",
                "completed_at": "2025-11-07T10:07:00"
            }
        ]
        mock_session_file.write_text(json.dumps(session_data, indent=2))

        # Act & Assert: Expect ValueError
        # NOTE: This WILL FAIL - function doesn't exist yet
        with pytest.raises(ValueError, match="Invalid timestamp format"):
            tracker.verify_parallel_exploration()

    def test_verify_parallel_exploration_with_missing_timestamps(self, mock_session_file):
        """
        Test verify_parallel_exploration() with missing timestamp fields.

        Given: Session file missing started_at or completed_at fields
        When: verify_parallel_exploration() is called
        Then: Raises ValueError with clear error message

        Protects: Phase 2 data validation
        """
        # Arrange: Create session with missing timestamps
        tracker = AgentTracker(session_file=str(mock_session_file))
        session_data = json.loads(mock_session_file.read_text())
        session_data["agents"] = [
            {
                "agent": "researcher",
                "status": "completed",
                # Missing started_at
                "completed_at": "2025-11-07T10:05:00"
            },
            {
                "agent": "planner",
                "status": "completed",
                "started_at": "2025-11-07T10:00:00",
                "completed_at": "2025-11-07T10:07:00"
            }
        ]
        mock_session_file.write_text(json.dumps(session_data, indent=2))

        # Act & Assert: Expect ValueError
        # NOTE: This WILL FAIL - function doesn't exist yet
        with pytest.raises(ValueError, match="Missing timestamp"):
            tracker.verify_parallel_exploration()

    def test_verify_parallel_exploration_empty_session(self, mock_session_file):
        """
        Test verify_parallel_exploration() with empty session file.

        Given: Session file with no agents
        When: verify_parallel_exploration() is called
        Then: Returns False (no agents completed)

        Protects: Phase 2 empty state handling
        """
        # Arrange: Empty session
        tracker = AgentTracker(session_file=str(mock_session_file))

        # Act: Verify parallel exploration
        # NOTE: This WILL FAIL - function doesn't exist yet
        result = tracker.verify_parallel_exploration()

        # Assert: Empty session detected
        assert result is False, "Expected False for empty session"

        session_data = json.loads(mock_session_file.read_text())
        assert session_data["parallel_exploration"]["status"] == "incomplete"

    def test_verify_parallel_exploration_duplicate_agents(self, mock_session_file):
        """
        Test verify_parallel_exploration() with duplicate agent entries.

        Given: Session file has multiple researcher entries
        When: verify_parallel_exploration() is called
        Then: Uses the latest completed entry
        And: Logs warning about duplicates

        Protects: Phase 2 duplicate handling
        """
        # Arrange: Create session with duplicate researchers
        tracker = AgentTracker(session_file=str(mock_session_file))

        base_time = datetime.now()

        # First researcher (failed)
        tracker.log_start("researcher", "Research starting")
        tracker.log_fail("researcher", "First attempt failed")

        # Second researcher (succeeded)
        tracker.log_start("researcher", "Research restarting")
        session_data = json.loads(mock_session_file.read_text())
        researcher_idx = len(session_data["agents"]) - 1
        session_data["agents"][researcher_idx]["started_at"] = base_time.isoformat()
        session_data["agents"][researcher_idx]["completed_at"] = (base_time + timedelta(minutes=5)).isoformat()
        session_data["agents"][researcher_idx]["duration_seconds"] = 300
        session_data["agents"][researcher_idx]["status"] = "completed"

        # Planner
        session_data["agents"].append({
            "agent": "planner",
            "status": "completed",
            "started_at": base_time.isoformat(),
            "completed_at": (base_time + timedelta(minutes=6)).isoformat(),
            "duration_seconds": 360
        })

        mock_session_file.write_text(json.dumps(session_data, indent=2))

        # Act: Verify parallel exploration
        # NOTE: This WILL FAIL - function doesn't exist yet
        result = tracker.verify_parallel_exploration()

        # Assert: Uses latest completed entry
        assert result is True, "Should use latest completed researcher"

        session_data = json.loads(mock_session_file.read_text())
        parallel_data = session_data["parallel_exploration"]
        assert "duplicate_agents" in parallel_data
        assert "researcher" in parallel_data["duplicate_agents"]

    def test_verify_parallel_exploration_extreme_parallelism(self, mock_session_file):
        """
        Test verify_parallel_exploration() with very tight parallelism (< 1 second).

        Given: Researcher and planner start within 0.5 seconds
        When: verify_parallel_exploration() calculates efficiency
        Then: Correctly identifies as parallel execution
        And: Efficiency close to 50% (2 agents in time of 1)

        Protects: Phase 2 tight timing accuracy
        """
        # Arrange: Create session with tight parallel timing
        tracker = AgentTracker(session_file=str(mock_session_file))

        base_time = datetime.now()

        session_data = json.loads(mock_session_file.read_text())
        session_data["agents"] = [
            {
                "agent": "researcher",
                "status": "completed",
                "started_at": base_time.isoformat(),
                "completed_at": (base_time + timedelta(minutes=5)).isoformat(),
                "duration_seconds": 300
            },
            {
                "agent": "planner",
                "status": "completed",
                "started_at": (base_time + timedelta(seconds=0.5)).isoformat(),
                "completed_at": (base_time + timedelta(minutes=5, seconds=0.5)).isoformat(),
                "duration_seconds": 300
            }
        ]
        mock_session_file.write_text(json.dumps(session_data, indent=2))

        # Act: Verify parallel exploration
        # NOTE: This WILL FAIL - function doesn't exist yet
        result = tracker.verify_parallel_exploration()

        # Assert: Tight parallelism detected
        assert result is True

        session_data = json.loads(mock_session_file.read_text())
        parallel_data = session_data["parallel_exploration"]
        assert parallel_data["status"] == "parallel"
        assert parallel_data["efficiency_percent"] > 45  # Close to 50% efficiency

    def test_verify_parallel_exploration_with_extreme_durations(self, mock_session_file):
        """
        Test verify_parallel_exploration() with extreme duration differences.

        Given: Researcher takes 15 minutes, planner takes 2 minutes
        When: verify_parallel_exploration() calculates efficiency
        Then: Parallel time = 15 minutes (max), sequential = 17 minutes
        And: Time saved = 2 minutes

        Protects: Phase 2 unbalanced duration handling
        """
        # Arrange: Create session with unbalanced durations
        tracker = AgentTracker(session_file=str(mock_session_file))

        base_time = datetime.now()

        session_data = json.loads(mock_session_file.read_text())
        session_data["agents"] = [
            {
                "agent": "researcher",
                "status": "completed",
                "started_at": base_time.isoformat(),
                "completed_at": (base_time + timedelta(minutes=15)).isoformat(),
                "duration_seconds": 900
            },
            {
                "agent": "planner",
                "status": "completed",
                "started_at": base_time.isoformat(),
                "completed_at": (base_time + timedelta(minutes=2)).isoformat(),
                "duration_seconds": 120
            }
        ]
        mock_session_file.write_text(json.dumps(session_data, indent=2))

        # Act: Verify parallel exploration
        # NOTE: This WILL FAIL - function doesn't exist yet
        result = tracker.verify_parallel_exploration()

        # Assert: Unbalanced durations handled correctly
        session_data = json.loads(mock_session_file.read_text())
        parallel_data = session_data["parallel_exploration"]

        assert parallel_data["sequential_time_seconds"] == 1020  # 900 + 120
        assert parallel_data["parallel_time_seconds"] == 900  # max(900, 120)
        assert parallel_data["time_saved_seconds"] == 120  # 1020 - 900
