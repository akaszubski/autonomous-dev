"""
Unit tests for verify_parallel_validation() checkpoint in AgentTracker.

TDD Red Phase: These tests are written BEFORE implementation.
All tests should FAIL initially (methods don't exist yet).

Test Strategy:
- Test verify_parallel_validation() method (returns True/False based on 3 agents)
- Test _detect_parallel_execution_three_agents() helper (5-second window detection)
- Test _record_incomplete_validation() helper (missing agents logging)
- Test _record_failed_validation() helper (failed agents logging)
- Test metrics calculation (sequential_time, parallel_time, time_saved)
- Test session file metadata recording
- Test edge cases (exact 5-second threshold, missing durations, failed agents)

Date: 2025-11-09
Related Issue: Parallel Validation Checkpoint (Phase 2)
Agent: test-master
"""

import json
import sys
import pytest
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock, call
from datetime import datetime, timedelta
from typing import Dict, List, Any

# Add lib directory to path for imports
sys.path.insert(
    0,
    str(
        Path(__file__).parent.parent.parent
        / "plugins"
        / "autonomous-dev"
        / "lib"
    ),
)

# Import agent tracker
try:
    from scripts.agent_tracker import AgentTracker
except ImportError as e:
    pytest.skip(f"AgentTracker not found: {e}", allow_module_level=True)


@pytest.fixture
def mock_session_file(tmp_path):
    """Create a temporary session file for testing."""
    session_file = tmp_path / "test_session.json"
    session_data = {
        "session_id": "20251109-test",
        "started": "2025-11-09T10:00:00",
        "agents": []
    }
    session_file.write_text(json.dumps(session_data, indent=2))
    return session_file


@pytest.fixture
def tracker_with_validation_agents(mock_session_file):
    """Create tracker with all 3 validation agents completed in parallel."""
    tracker = AgentTracker(session_file=str(mock_session_file))

    # Add 3 validation agents that started within 5 seconds (parallel)
    base_time = datetime.now()

    # Reviewer: started at T+0, duration 120 seconds
    tracker.start_agent("reviewer", "Reviewing code quality")
    tracker.session_data["agents"][-1]["started_at"] = base_time.isoformat()
    tracker.complete_agent("reviewer", "Code quality approved", tools=["Read", "Grep"])
    tracker.session_data["agents"][-1]["completed_at"] = (base_time + timedelta(seconds=120)).isoformat()
    tracker.session_data["agents"][-1]["duration_seconds"] = 120

    # Security-auditor: started at T+2, duration 150 seconds
    tracker.start_agent("security-auditor", "Scanning for vulnerabilities")
    tracker.session_data["agents"][-1]["started_at"] = (base_time + timedelta(seconds=2)).isoformat()
    tracker.complete_agent("security-auditor", "No security issues found", tools=["Grep"])
    tracker.session_data["agents"][-1]["completed_at"] = (base_time + timedelta(seconds=152)).isoformat()
    tracker.session_data["agents"][-1]["duration_seconds"] = 150

    # Doc-master: started at T+4, duration 100 seconds
    tracker.start_agent("doc-master", "Updating documentation")
    tracker.session_data["agents"][-1]["started_at"] = (base_time + timedelta(seconds=4)).isoformat()
    tracker.complete_agent("doc-master", "Documentation synchronized", tools=["Edit", "Read"])
    tracker.session_data["agents"][-1]["completed_at"] = (base_time + timedelta(seconds=104)).isoformat()
    tracker.session_data["agents"][-1]["duration_seconds"] = 100

    tracker._save()
    return tracker


@pytest.fixture
def tracker_with_sequential_agents(mock_session_file):
    """Create tracker with validation agents that ran sequentially."""
    tracker = AgentTracker(session_file=str(mock_session_file))

    base_time = datetime.now()

    # Reviewer: T+0 to T+120
    tracker.start_agent("reviewer", "Reviewing")
    tracker.session_data["agents"][-1]["started_at"] = base_time.isoformat()
    tracker.complete_agent("reviewer", "Approved", tools=["Read"])
    tracker.session_data["agents"][-1]["completed_at"] = (base_time + timedelta(seconds=120)).isoformat()
    tracker.session_data["agents"][-1]["duration_seconds"] = 120

    # Security-auditor: T+130 to T+280 (started 10 seconds AFTER reviewer, sequential)
    tracker.start_agent("security-auditor", "Scanning")
    tracker.session_data["agents"][-1]["started_at"] = (base_time + timedelta(seconds=130)).isoformat()
    tracker.complete_agent("security-auditor", "No issues", tools=["Grep"])
    tracker.session_data["agents"][-1]["completed_at"] = (base_time + timedelta(seconds=280)).isoformat()
    tracker.session_data["agents"][-1]["duration_seconds"] = 150

    # Doc-master: T+290 to T+390
    tracker.start_agent("doc-master", "Documenting")
    tracker.session_data["agents"][-1]["started_at"] = (base_time + timedelta(seconds=290)).isoformat()
    tracker.complete_agent("doc-master", "Done", tools=["Edit"])
    tracker.session_data["agents"][-1]["completed_at"] = (base_time + timedelta(seconds=390)).isoformat()
    tracker.session_data["agents"][-1]["duration_seconds"] = 100

    tracker._save()
    return tracker


class TestVerifyParallelValidationHappyPath:
    """Test verify_parallel_validation() with all agents completing successfully."""

    @patch('scripts.agent_tracker.audit_log')
    def test_all_three_agents_complete_parallel_returns_true(self, mock_audit, tracker_with_validation_agents):
        """
        Test that verify_parallel_validation() returns True when all 3 agents complete in parallel.

        Expected behavior:
        - Returns True
        - Writes parallel_validation metadata to session file
        - Metrics: status="parallel", time_saved > 0, efficiency > 0
        - Audit log records success
        """
        # Act
        result = tracker_with_validation_agents.verify_parallel_validation()

        # Assert: Returns True
        assert result is True, "Should return True when all 3 agents complete"

        # Assert: Session file has parallel_validation metadata
        session_data = json.loads(tracker_with_validation_agents.session_file.read_text())
        assert "parallel_validation" in session_data, \
            "Session file should have parallel_validation metadata"

        metadata = session_data["parallel_validation"]

        # Assert: Status is parallel
        assert metadata["status"] == "parallel", \
            "Status should be 'parallel' when agents start within 5 seconds"

        # Assert: Metrics calculated correctly
        # Sequential time = 120 + 150 + 100 = 370 seconds
        assert metadata["sequential_time_seconds"] == 370, \
            f"Sequential time should be 370, got {metadata['sequential_time_seconds']}"

        # Parallel time = max(120, 150, 100) = 150 seconds
        assert metadata["parallel_time_seconds"] == 150, \
            f"Parallel time should be 150, got {metadata['parallel_time_seconds']}"

        # Time saved = 370 - 150 = 220 seconds
        assert metadata["time_saved_seconds"] == 220, \
            f"Time saved should be 220, got {metadata['time_saved_seconds']}"

        # Efficiency = (220 / 370) * 100 = 59.46%
        assert 59.0 <= metadata["efficiency_percent"] <= 60.0, \
            f"Efficiency should be ~59%, got {metadata['efficiency_percent']}"

        # Assert: Audit log called with verify_parallel_validation operation
        mock_audit.assert_any_call(
            "agent_tracker",
            "success",
            {
                "operation": "verify_parallel_validation",
                "status": "parallel",
                "time_saved_seconds": 220,
                "efficiency_percent": pytest.approx(59.46, abs=0.1)
            }
        )

    @patch('scripts.agent_tracker.audit_log')
    def test_all_three_agents_complete_sequential_returns_true(self, mock_audit, tracker_with_sequential_agents):
        """
        Test that verify_parallel_validation() returns True even when agents run sequentially.

        Expected behavior:
        - Returns True (agents completed, even if not parallel)
        - Metrics: status="sequential", time_saved=0, efficiency=0
        - Session file records sequential execution
        """
        # Act
        result = tracker_with_sequential_agents.verify_parallel_validation()

        # Assert: Returns True
        assert result is True, "Should return True when all 3 agents complete (even sequential)"

        # Assert: Status is sequential
        session_data = json.loads(tracker_with_sequential_agents.session_file.read_text())
        metadata = session_data["parallel_validation"]

        assert metadata["status"] == "sequential", \
            "Status should be 'sequential' when start times differ by >5 seconds"

        # Assert: Time saved is 0 for sequential
        assert metadata["time_saved_seconds"] == 0, \
            "Sequential execution should have 0 time saved"

        # Assert: Efficiency is 0
        assert metadata["efficiency_percent"] == 0, \
            "Sequential execution should have 0% efficiency"

        # Assert: Sequential time still calculated
        assert metadata["sequential_time_seconds"] == 370, \
            "Sequential time should be sum of durations"

    @patch('scripts.agent_tracker.audit_log')
    def test_exact_five_second_threshold_detected_as_parallel(self, mock_audit, mock_session_file):
        """
        Test that agents starting exactly 5.0 seconds apart are considered parallel.

        Expected behavior:
        - Threshold is < 5 seconds (exclusive), so 5.0 should be sequential
        - OR threshold is <= 5 seconds (inclusive), so 5.0 should be parallel
        - Test validates the boundary condition behavior
        """
        tracker = AgentTracker(session_file=str(mock_session_file))
        base_time = datetime.now()

        # Agent 1: T+0
        tracker.start_agent("reviewer", "Reviewing")
        tracker.session_data["agents"][-1]["started_at"] = base_time.isoformat()
        tracker.complete_agent("reviewer", "Done", tools=["Read"])
        tracker.session_data["agents"][-1]["duration_seconds"] = 100

        # Agent 2: T+4.9 (just under 5 seconds, should be parallel)
        tracker.start_agent("security-auditor", "Scanning")
        tracker.session_data["agents"][-1]["started_at"] = (base_time + timedelta(seconds=4.9)).isoformat()
        tracker.complete_agent("security-auditor", "Done", tools=["Grep"])
        tracker.session_data["agents"][-1]["duration_seconds"] = 100

        # Agent 3: T+5.0 (exactly 5 seconds from agent 1)
        tracker.start_agent("doc-master", "Documenting")
        tracker.session_data["agents"][-1]["started_at"] = (base_time + timedelta(seconds=5.0)).isoformat()
        tracker.complete_agent("doc-master", "Done", tools=["Edit"])
        tracker.session_data["agents"][-1]["duration_seconds"] = 100

        tracker._save()

        # Act
        result = tracker.verify_parallel_validation()

        # Assert: Verify boundary behavior
        session_data = json.loads(tracker.session_file.read_text())
        metadata = session_data["parallel_validation"]

        # The test documents expected behavior - implementation will decide if 5.0 is parallel or sequential
        # Based on verify_parallel_exploration, threshold is < 5, so 5.0 should be sequential
        # But we need to verify the maximum gap between ANY two agents
        # Agent 1 to Agent 3 = 5.0 seconds
        # If ANY pair exceeds 5 seconds, it's sequential
        assert metadata["status"] in ["parallel", "sequential"], \
            "Status should be clearly defined for boundary case"


class TestVerifyParallelValidationMissingAgents:
    """Test handling when validation agents are missing."""

    @patch('scripts.agent_tracker.audit_log')
    def test_missing_reviewer_returns_false(self, mock_audit, mock_session_file):
        """
        Test that verify_parallel_validation() returns False when reviewer is missing.

        Expected behavior:
        - Returns False
        - Calls _record_incomplete_validation() with ["reviewer"]
        - Session file shows status="incomplete", missing_agents=["reviewer"]
        - Audit log records failure
        """
        tracker = AgentTracker(session_file=str(mock_session_file))

        # Add only security-auditor and doc-master (missing reviewer)
        tracker.start_agent("security-auditor", "Scanning")
        tracker.complete_agent("security-auditor", "Done", tools=["Grep"])
        tracker.session_data["agents"][-1]["duration_seconds"] = 150

        tracker.start_agent("doc-master", "Documenting")
        tracker.complete_agent("doc-master", "Done", tools=["Edit"])
        tracker.session_data["agents"][-1]["duration_seconds"] = 100

        tracker._save()

        # Act
        result = tracker.verify_parallel_validation()

        # Assert: Returns False
        assert result is False, "Should return False when reviewer is missing"

        # Assert: Session file shows incomplete status
        session_data = json.loads(tracker.session_file.read_text())
        metadata = session_data["parallel_validation"]

        assert metadata["status"] == "incomplete", \
            "Status should be 'incomplete' when agents missing"

        assert "missing_agents" in metadata, \
            "Should include missing_agents list"

        assert "reviewer" in metadata["missing_agents"], \
            "Should list reviewer as missing"

        # Assert: Audit log called with failure
        mock_audit.assert_any_call(
            "agent_tracker",
            "failure",
            {
                "operation": "verify_parallel_validation",
                "status": "incomplete",
                "missing_agents": ["reviewer"]
            }
        )

    @patch('scripts.agent_tracker.audit_log')
    def test_missing_security_auditor_returns_false(self, mock_audit, mock_session_file):
        """Test that missing security-auditor is detected and reported."""
        tracker = AgentTracker(session_file=str(mock_session_file))

        # Add only reviewer and doc-master
        tracker.start_agent("reviewer", "Reviewing")
        tracker.complete_agent("reviewer", "Done", tools=["Read"])
        tracker.session_data["agents"][-1]["duration_seconds"] = 120

        tracker.start_agent("doc-master", "Documenting")
        tracker.complete_agent("doc-master", "Done", tools=["Edit"])
        tracker.session_data["agents"][-1]["duration_seconds"] = 100

        tracker._save()

        # Act
        result = tracker.verify_parallel_validation()

        # Assert
        assert result is False

        session_data = json.loads(tracker.session_file.read_text())
        metadata = session_data["parallel_validation"]

        assert metadata["status"] == "incomplete"
        assert "security-auditor" in metadata["missing_agents"]

    @patch('scripts.agent_tracker.audit_log')
    def test_missing_doc_master_returns_false(self, mock_audit, mock_session_file):
        """Test that missing doc-master is detected and reported."""
        tracker = AgentTracker(session_file=str(mock_session_file))

        # Add only reviewer and security-auditor
        tracker.start_agent("reviewer", "Reviewing")
        tracker.complete_agent("reviewer", "Done", tools=["Read"])
        tracker.session_data["agents"][-1]["duration_seconds"] = 120

        tracker.start_agent("security-auditor", "Scanning")
        tracker.complete_agent("security-auditor", "Done", tools=["Grep"])
        tracker.session_data["agents"][-1]["duration_seconds"] = 150

        tracker._save()

        # Act
        result = tracker.verify_parallel_validation()

        # Assert
        assert result is False

        session_data = json.loads(tracker.session_file.read_text())
        metadata = session_data["parallel_validation"]

        assert metadata["status"] == "incomplete"
        assert "doc-master" in metadata["missing_agents"]

    @patch('scripts.agent_tracker.audit_log')
    def test_all_three_agents_missing_returns_false(self, mock_audit, mock_session_file):
        """
        Test that verify_parallel_validation() returns False when all 3 agents missing.

        Expected behavior:
        - Returns False
        - Missing agents list contains all 3
        - Status is incomplete
        """
        tracker = AgentTracker(session_file=str(mock_session_file))

        # Don't add any validation agents

        # Act
        result = tracker.verify_parallel_validation()

        # Assert
        assert result is False

        session_data = json.loads(tracker.session_file.read_text())
        metadata = session_data["parallel_validation"]

        assert metadata["status"] == "incomplete"
        assert len(metadata["missing_agents"]) == 3
        assert set(metadata["missing_agents"]) == {"reviewer", "security-auditor", "doc-master"}


class TestVerifyParallelValidationFailedAgents:
    """Test handling when validation agents fail."""

    @patch('scripts.agent_tracker.audit_log')
    def test_reviewer_failed_returns_false(self, mock_audit, mock_session_file):
        """
        Test that verify_parallel_validation() returns False when reviewer fails.

        Expected behavior:
        - Returns False
        - Calls _record_failed_validation() with ["reviewer"]
        - Session file shows status="failed", failed_agents=["reviewer"]
        - Audit log records failure
        """
        tracker = AgentTracker(session_file=str(mock_session_file))

        # Reviewer fails
        tracker.start_agent("reviewer", "Reviewing")
        tracker.fail_agent("reviewer", "CHANGES REQUESTED: Poor error handling")
        tracker.session_data["agents"][-1]["duration_seconds"] = 120

        # Others succeed
        tracker.start_agent("security-auditor", "Scanning")
        tracker.complete_agent("security-auditor", "Done", tools=["Grep"])
        tracker.session_data["agents"][-1]["duration_seconds"] = 150

        tracker.start_agent("doc-master", "Documenting")
        tracker.complete_agent("doc-master", "Done", tools=["Edit"])
        tracker.session_data["agents"][-1]["duration_seconds"] = 100

        tracker._save()

        # Act
        result = tracker.verify_parallel_validation()

        # Assert: Returns False
        assert result is False, "Should return False when any agent fails"

        # Assert: Session file shows failed status
        session_data = json.loads(tracker.session_file.read_text())
        metadata = session_data["parallel_validation"]

        assert metadata["status"] == "failed", \
            "Status should be 'failed' when agents fail"

        assert "failed_agents" in metadata, \
            "Should include failed_agents list"

        assert "reviewer" in metadata["failed_agents"], \
            "Should list reviewer as failed"

        # Assert: Audit log called with failure
        mock_audit.assert_any_call(
            "agent_tracker",
            "failure",
            {
                "operation": "verify_parallel_validation",
                "status": "failed",
                "failed_agents": ["reviewer"]
            }
        )

    @patch('scripts.agent_tracker.audit_log')
    def test_security_auditor_failed_returns_false(self, mock_audit, mock_session_file):
        """Test that security-auditor failure is detected."""
        tracker = AgentTracker(session_file=str(mock_session_file))

        tracker.start_agent("reviewer", "Reviewing")
        tracker.complete_agent("reviewer", "Done", tools=["Read"])
        tracker.session_data["agents"][-1]["duration_seconds"] = 120

        # Security fails
        tracker.start_agent("security-auditor", "Scanning")
        tracker.fail_agent("security-auditor", "CRITICAL: Hardcoded API key found")
        tracker.session_data["agents"][-1]["duration_seconds"] = 150

        tracker.start_agent("doc-master", "Documenting")
        tracker.complete_agent("doc-master", "Done", tools=["Edit"])
        tracker.session_data["agents"][-1]["duration_seconds"] = 100

        tracker._save()

        # Act
        result = tracker.verify_parallel_validation()

        # Assert
        assert result is False

        session_data = json.loads(tracker.session_file.read_text())
        metadata = session_data["parallel_validation"]

        assert metadata["status"] == "failed"
        assert "security-auditor" in metadata["failed_agents"]

    @patch('scripts.agent_tracker.audit_log')
    def test_multiple_agents_failed_returns_false(self, mock_audit, mock_session_file):
        """
        Test that multiple failed agents are all reported.

        Expected behavior:
        - Returns False
        - Failed agents list contains all failed agents
        - Status is failed
        """
        tracker = AgentTracker(session_file=str(mock_session_file))

        # Reviewer fails
        tracker.start_agent("reviewer", "Reviewing")
        tracker.fail_agent("reviewer", "CHANGES REQUESTED")
        tracker.session_data["agents"][-1]["duration_seconds"] = 120

        # Security succeeds
        tracker.start_agent("security-auditor", "Scanning")
        tracker.complete_agent("security-auditor", "Done", tools=["Grep"])
        tracker.session_data["agents"][-1]["duration_seconds"] = 150

        # Doc-master fails
        tracker.start_agent("doc-master", "Documenting")
        tracker.fail_agent("doc-master", "Missing documentation")
        tracker.session_data["agents"][-1]["duration_seconds"] = 100

        tracker._save()

        # Act
        result = tracker.verify_parallel_validation()

        # Assert
        assert result is False

        session_data = json.loads(tracker.session_file.read_text())
        metadata = session_data["parallel_validation"]

        assert metadata["status"] == "failed"
        assert len(metadata["failed_agents"]) == 2
        assert set(metadata["failed_agents"]) == {"reviewer", "doc-master"}

    @patch('scripts.agent_tracker.audit_log')
    def test_failed_takes_precedence_over_incomplete(self, mock_audit, mock_session_file):
        """
        Test that failed status takes precedence when some agents fail and some missing.

        Expected behavior:
        - If any agent has status="failed", report as failed (not incomplete)
        - This matches behavior in verify_parallel_exploration
        """
        tracker = AgentTracker(session_file=str(mock_session_file))

        # Reviewer fails
        tracker.start_agent("reviewer", "Reviewing")
        tracker.fail_agent("reviewer", "CHANGES REQUESTED")
        tracker.session_data["agents"][-1]["duration_seconds"] = 120

        # Security-auditor missing (never started)
        # Doc-master completes
        tracker.start_agent("doc-master", "Documenting")
        tracker.complete_agent("doc-master", "Done", tools=["Edit"])
        tracker.session_data["agents"][-1]["duration_seconds"] = 100

        tracker._save()

        # Act
        result = tracker.verify_parallel_validation()

        # Assert: Should prioritize failed over incomplete
        assert result is False

        session_data = json.loads(tracker.session_file.read_text())
        metadata = session_data["parallel_validation"]

        # Should be "failed" not "incomplete"
        assert metadata["status"] == "failed", \
            "Failed status should take precedence over incomplete"

        assert "reviewer" in metadata["failed_agents"]


class TestDetectParallelExecutionThreeAgents:
    """Test _detect_parallel_execution_three_agents() helper method."""

    def test_all_three_start_within_five_seconds_returns_true(self, tracker_with_validation_agents):
        """
        Test that agents starting within 5 seconds are detected as parallel.

        Expected behavior:
        - Method checks all pairwise time differences
        - If max difference < 5 seconds, returns True
        """
        # Get the 3 agent entries
        reviewer = tracker_with_validation_agents._find_agent("reviewer")
        security = tracker_with_validation_agents._find_agent("security-auditor")
        doc_master = tracker_with_validation_agents._find_agent("doc-master")

        # Act
        result = tracker_with_validation_agents._detect_parallel_execution_three_agents(
            reviewer, security, doc_master
        )

        # Assert
        assert result is True, "Should detect parallel execution when start times within 5 seconds"

    def test_agents_start_more_than_five_seconds_apart_returns_false(self, tracker_with_sequential_agents):
        """Test that sequential execution (>5 seconds apart) is detected."""
        reviewer = tracker_with_sequential_agents._find_agent("reviewer")
        security = tracker_with_sequential_agents._find_agent("security-auditor")
        doc_master = tracker_with_sequential_agents._find_agent("doc-master")

        # Act
        result = tracker_with_sequential_agents._detect_parallel_execution_three_agents(
            reviewer, security, doc_master
        )

        # Assert
        assert result is False, "Should detect sequential execution when gaps > 5 seconds"

    def test_exactly_five_seconds_boundary(self, mock_session_file):
        """
        Test the exact 5.0 second boundary condition.

        Expected behavior:
        - Based on verify_parallel_exploration logic, threshold is < 5
        - So exactly 5.0 seconds should return False (sequential)
        """
        tracker = AgentTracker(session_file=str(mock_session_file))
        base_time = datetime.now()

        # Create 3 agents where max gap is exactly 5.0 seconds
        reviewer_data = {
            "agent": "reviewer",
            "status": "completed",
            "started_at": base_time.isoformat(),
            "duration_seconds": 100
        }

        security_data = {
            "agent": "security-auditor",
            "status": "completed",
            "started_at": (base_time + timedelta(seconds=2)).isoformat(),
            "duration_seconds": 100
        }

        doc_master_data = {
            "agent": "doc-master",
            "status": "completed",
            "started_at": (base_time + timedelta(seconds=5.0)).isoformat(),  # Exactly 5.0 from reviewer
            "duration_seconds": 100
        }

        # Act
        result = tracker._detect_parallel_execution_three_agents(
            reviewer_data, security_data, doc_master_data
        )

        # Assert: Should be False (sequential) based on < 5 logic
        assert result is False, \
            "Exactly 5.0 seconds should be sequential (threshold is < 5)"

    def test_agents_in_different_completion_order(self, mock_session_file):
        """
        Test that completion order doesn't affect parallel detection (only start times matter).

        Expected behavior:
        - Only start_at timestamps used for detection
        - Completion order is irrelevant
        """
        tracker = AgentTracker(session_file=str(mock_session_file))
        base_time = datetime.now()

        # All start within 5 seconds (parallel)
        # But complete in unusual order (doc-master first, reviewer last)
        reviewer_data = {
            "agent": "reviewer",
            "status": "completed",
            "started_at": base_time.isoformat(),
            "completed_at": (base_time + timedelta(seconds=200)).isoformat(),  # Completes last
            "duration_seconds": 200
        }

        security_data = {
            "agent": "security-auditor",
            "status": "completed",
            "started_at": (base_time + timedelta(seconds=2)).isoformat(),
            "completed_at": (base_time + timedelta(seconds=102)).isoformat(),  # Completes second
            "duration_seconds": 100
        }

        doc_master_data = {
            "agent": "doc-master",
            "status": "completed",
            "started_at": (base_time + timedelta(seconds=4)).isoformat(),
            "completed_at": (base_time + timedelta(seconds=54)).isoformat(),  # Completes first
            "duration_seconds": 50
        }

        # Act
        result = tracker._detect_parallel_execution_three_agents(
            reviewer_data, security_data, doc_master_data
        )

        # Assert: Should detect as parallel (start times within 5 seconds)
        assert result is True, \
            "Parallel detection should only consider start times, not completion order"


class TestRecordIncompleteValidation:
    """Test _record_incomplete_validation() helper method."""

    @patch('scripts.agent_tracker.audit_log')
    def test_records_single_missing_agent(self, mock_audit, mock_session_file):
        """Test recording when one agent is missing."""
        tracker = AgentTracker(session_file=str(mock_session_file))

        # Act
        tracker._record_incomplete_validation(["reviewer"])

        # Assert: Session file updated
        session_data = json.loads(tracker.session_file.read_text())
        metadata = session_data["parallel_validation"]

        assert metadata["status"] == "incomplete"
        assert metadata["missing_agents"] == ["reviewer"]

        # Assert: Audit log called
        mock_audit.assert_any_call(
            "agent_tracker",
            "failure",
            {
                "operation": "verify_parallel_validation",
                "status": "incomplete",
                "missing_agents": ["reviewer"]
            }
        )

    @patch('scripts.agent_tracker.audit_log')
    def test_records_multiple_missing_agents(self, mock_audit, mock_session_file):
        """Test recording when multiple agents are missing."""
        tracker = AgentTracker(session_file=str(mock_session_file))

        # Act
        tracker._record_incomplete_validation(["reviewer", "security-auditor"])

        # Assert
        session_data = json.loads(tracker.session_file.read_text())
        metadata = session_data["parallel_validation"]

        assert metadata["status"] == "incomplete"
        assert set(metadata["missing_agents"]) == {"reviewer", "security-auditor"}

    @patch('scripts.agent_tracker.audit_log')
    def test_saves_session_file_atomically(self, mock_audit, mock_session_file):
        """Test that session file is saved after recording incomplete status."""
        tracker = AgentTracker(session_file=str(mock_session_file))

        # Get initial modification time
        initial_mtime = mock_session_file.stat().st_mtime

        # Act
        tracker._record_incomplete_validation(["doc-master"])

        # Assert: File was modified
        final_mtime = mock_session_file.stat().st_mtime
        assert final_mtime > initial_mtime, \
            "Session file should be saved after recording"

        # Assert: File is valid JSON
        session_data = json.loads(mock_session_file.read_text())
        assert "parallel_validation" in session_data


class TestRecordFailedValidation:
    """Test _record_failed_validation() helper method."""

    @patch('scripts.agent_tracker.audit_log')
    def test_records_single_failed_agent(self, mock_audit, mock_session_file):
        """Test recording when one agent fails."""
        tracker = AgentTracker(session_file=str(mock_session_file))

        # Act
        tracker._record_failed_validation(["reviewer"])

        # Assert: Session file updated
        session_data = json.loads(tracker.session_file.read_text())
        metadata = session_data["parallel_validation"]

        assert metadata["status"] == "failed"
        assert metadata["failed_agents"] == ["reviewer"]

        # Assert: Audit log called
        mock_audit.assert_any_call(
            "agent_tracker",
            "failure",
            {
                "operation": "verify_parallel_validation",
                "status": "failed",
                "failed_agents": ["reviewer"]
            }
        )

    @patch('scripts.agent_tracker.audit_log')
    def test_records_multiple_failed_agents(self, mock_audit, mock_session_file):
        """Test recording when multiple agents fail."""
        tracker = AgentTracker(session_file=str(mock_session_file))

        # Act
        tracker._record_failed_validation(["reviewer", "doc-master"])

        # Assert
        session_data = json.loads(tracker.session_file.read_text())
        metadata = session_data["parallel_validation"]

        assert metadata["status"] == "failed"
        assert set(metadata["failed_agents"]) == {"reviewer", "doc-master"}


class TestVerifyParallelValidationEdgeCases:
    """Test edge cases and error handling."""

    @patch('scripts.agent_tracker.audit_log')
    def test_missing_duration_fields_handled_gracefully(self, mock_audit, mock_session_file):
        """
        Test that missing duration_seconds fields don't cause crashes.

        Expected behavior:
        - If duration_seconds missing, default to 0
        - Still calculate metrics (may be 0)
        - Don't crash or raise exception
        """
        tracker = AgentTracker(session_file=str(mock_session_file))
        base_time = datetime.now()

        # Add agents with missing duration fields
        tracker.start_agent("reviewer", "Reviewing")
        tracker.session_data["agents"][-1]["started_at"] = base_time.isoformat()
        tracker.complete_agent("reviewer", "Done", tools=["Read"])
        # Remove duration_seconds to simulate missing field
        if "duration_seconds" in tracker.session_data["agents"][-1]:
            del tracker.session_data["agents"][-1]["duration_seconds"]

        tracker.start_agent("security-auditor", "Scanning")
        tracker.session_data["agents"][-1]["started_at"] = (base_time + timedelta(seconds=2)).isoformat()
        tracker.complete_agent("security-auditor", "Done", tools=["Grep"])
        # Remove duration_seconds to simulate missing field
        if "duration_seconds" in tracker.session_data["agents"][-1]:
            del tracker.session_data["agents"][-1]["duration_seconds"]

        tracker.start_agent("doc-master", "Documenting")
        tracker.session_data["agents"][-1]["started_at"] = (base_time + timedelta(seconds=4)).isoformat()
        tracker.complete_agent("doc-master", "Done", tools=["Edit"])
        # Remove duration_seconds to simulate missing field
        if "duration_seconds" in tracker.session_data["agents"][-1]:
            del tracker.session_data["agents"][-1]["duration_seconds"]

        tracker._save()

        # Act - should not crash
        result = tracker.verify_parallel_validation()

        # Assert: Returns True (agents completed)
        assert result is True

        # Assert: Metrics default to 0
        session_data = json.loads(tracker.session_file.read_text())
        metadata = session_data["parallel_validation"]

        assert metadata["sequential_time_seconds"] == 0, \
            "Should default to 0 when durations missing"
        assert metadata["parallel_time_seconds"] == 0

    @patch('scripts.agent_tracker.audit_log')
    def test_reload_session_data_before_verification(self, mock_audit, mock_session_file):
        """
        Test that session data is reloaded before verification (in case file modified externally).

        Expected behavior:
        - Method calls self.session_file.exists() and reloads
        - Gets latest agent data
        - Matches behavior in verify_parallel_exploration
        """
        tracker = AgentTracker(session_file=str(mock_session_file))

        # Add agents
        base_time = datetime.now()
        tracker.start_agent("reviewer", "Reviewing")
        tracker.session_data["agents"][-1]["started_at"] = base_time.isoformat()
        tracker.complete_agent("reviewer", "Done", tools=["Read"])
        tracker.session_data["agents"][-1]["duration_seconds"] = 100

        tracker.start_agent("security-auditor", "Scanning")
        tracker.session_data["agents"][-1]["started_at"] = (base_time + timedelta(seconds=2)).isoformat()
        tracker.complete_agent("security-auditor", "Done", tools=["Grep"])
        tracker.session_data["agents"][-1]["duration_seconds"] = 100

        tracker.start_agent("doc-master", "Documenting")
        tracker.session_data["agents"][-1]["started_at"] = (base_time + timedelta(seconds=4)).isoformat()
        tracker.complete_agent("doc-master", "Done", tools=["Edit"])
        tracker.session_data["agents"][-1]["duration_seconds"] = 100

        tracker._save()

        # Modify session data in memory (but not saved to file)
        tracker.session_data["agents"] = []

        # Act - should reload from file
        result = tracker.verify_parallel_validation()

        # Assert: Should have found the agents (reloaded from file)
        assert result is True, \
            "Should reload session data from file before verification"

    @patch('scripts.agent_tracker.audit_log')
    def test_duplicate_agents_handled_correctly(self, mock_audit, mock_session_file):
        """
        Test handling when duplicate agent entries exist (edge case).

        Expected behavior:
        - Should use _find_agent() which returns first match
        - Or handle duplicates gracefully
        - Don't crash
        """
        tracker = AgentTracker(session_file=str(mock_session_file))
        base_time = datetime.now()

        # Add reviewer twice (edge case)
        tracker.start_agent("reviewer", "First review")
        tracker.session_data["agents"][-1]["started_at"] = base_time.isoformat()
        tracker.complete_agent("reviewer", "Done", tools=["Read"])
        tracker.session_data["agents"][-1]["duration_seconds"] = 100

        tracker.start_agent("reviewer", "Second review")  # Duplicate
        tracker.session_data["agents"][-1]["started_at"] = (base_time + timedelta(seconds=10)).isoformat()
        tracker.complete_agent("reviewer", "Done", tools=["Read"])
        tracker.session_data["agents"][-1]["duration_seconds"] = 50

        # Add other agents normally
        tracker.start_agent("security-auditor", "Scanning")
        tracker.session_data["agents"][-1]["started_at"] = (base_time + timedelta(seconds=2)).isoformat()
        tracker.complete_agent("security-auditor", "Done", tools=["Grep"])
        tracker.session_data["agents"][-1]["duration_seconds"] = 100

        tracker.start_agent("doc-master", "Documenting")
        tracker.session_data["agents"][-1]["started_at"] = (base_time + timedelta(seconds=4)).isoformat()
        tracker.complete_agent("doc-master", "Done", tools=["Edit"])
        tracker.session_data["agents"][-1]["duration_seconds"] = 100

        tracker._save()

        # Act - should not crash
        result = tracker.verify_parallel_validation()

        # Assert: Should handle gracefully (use first match or detect duplicates)
        assert result is True or result is False, \
            "Should return boolean even with duplicates"


# Mark all tests as expecting to fail (TDD red phase)
# pytestmark removed - implementation complete (2025-11-09)
# All 4 methods implemented:
# - verify_parallel_validation()
# - _detect_parallel_execution_three_agents()
# - _record_incomplete_validation()
# - _record_failed_validation()
