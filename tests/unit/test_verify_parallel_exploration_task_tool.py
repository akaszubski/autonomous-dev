"""
Unit tests for verify_parallel_exploration() Task tool agent detection.

TDD Red Phase: These tests are written BEFORE implementation (Issue #71).
All tests should FAIL initially - the multi-method detection doesn't exist yet.

Feature: Fix verify_parallel_exploration() to detect Task tool agents
Problem: Task tool agents may not be recorded in agent_tracker, causing false "incomplete" status
Solution: Multi-method detection (tracker → JSON → session text parsing)

Test Coverage:
1. Session text parser (_detect_agent_from_session_text)
2. JSON structure analyzer (_detect_agent_from_json_structure)
3. Enhanced _find_agent() with multi-method detection
4. Data validation (_validate_agent_data)
5. Integration with verify_parallel_exploration()

Date: 2025-11-11
Related Issue: #71 - Fix verify_parallel_exploration() Task tool agent detection
Agent: test-master
"""

import json
import sys
import pytest
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock
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
        "session_id": "20251111-test",
        "started": "2025-11-11T10:00:00",
        "agents": []
    }
    session_file.write_text(json.dumps(session_data, indent=2))
    return session_file


@pytest.fixture
def mock_session_text_file(tmp_path):
    """Create a temporary session text file (.md) for parsing."""
    session_text = tmp_path / "20251111-test-session.md"
    content = """# Session 20251111-test

**Started**: 2025-11-11 10:00:00

---

**10:00:05 - researcher**: Starting research on JWT authentication patterns

**10:05:43 - researcher**: Research completed - Found 3 relevant patterns

**10:05:50 - planner**: Starting architecture planning for JWT implementation

**10:12:27 - planner**: Planning completed - Created 5-phase implementation plan
"""
    session_text.write_text(content)
    return session_text


class TestSessionTextParser:
    """Test _detect_agent_from_session_text() method for Task tool agent detection."""

    def test_valid_completion_marker_returns_agent_data(self, mock_session_file, mock_session_text_file):
        """
        Test that _detect_agent_from_session_text() detects valid completion markers.

        Expected behavior:
        - Parse session text file (.md format)
        - Find completion marker (e.g., "researcher completed")
        - Extract start/end timestamps
        - Return agent data dict with status="completed"

        Should FAIL: Method doesn't exist yet
        """
        tracker = AgentTracker(session_file=str(mock_session_file))

        # Act
        result = tracker._detect_agent_from_session_text("researcher", str(mock_session_text_file))

        # Assert
        assert result is not None, "Should return agent data for valid completion marker"
        assert result["agent"] == "researcher", "Should identify correct agent"
        assert result["status"] == "completed", "Should mark as completed"
        assert "started_at" in result, "Should have start timestamp"
        assert "completed_at" in result, "Should have completion timestamp"
        assert result["started_at"] == "2025-11-11T10:00:05", "Should parse start time correctly"
        assert result["completed_at"] == "2025-11-11T10:05:43", "Should parse completion time correctly"

    def test_missing_completion_marker_returns_none(self, mock_session_file, mock_session_text_file):
        """
        Test that missing completion marker returns None.

        Expected behavior:
        - Search for agent in session text
        - Find start marker but no completion marker
        - Return None (agent didn't complete)

        Should FAIL: Method doesn't exist yet
        """
        tracker = AgentTracker(session_file=str(mock_session_file))

        # Act
        result = tracker._detect_agent_from_session_text("test-master", str(mock_session_text_file))

        # Assert
        assert result is None, "Should return None when completion marker missing"

    def test_invalid_timestamp_format_returns_none(self, mock_session_file, tmp_path):
        """
        Test that invalid timestamp format returns None gracefully.

        Expected behavior:
        - Encounter malformed timestamp
        - Handle gracefully (no crash)
        - Return None (can't parse timestamps)

        Should FAIL: Method doesn't exist yet
        """
        # Create session text with invalid timestamp
        session_text = tmp_path / "invalid_session.md"
        content = """# Session test

**10:00:INVALID - researcher**: Starting research

**10:05:43 - researcher**: Research completed
"""
        session_text.write_text(content)

        tracker = AgentTracker(session_file=str(mock_session_file))

        # Act
        result = tracker._detect_agent_from_session_text("researcher", str(session_text))

        # Assert
        assert result is None, "Should return None for invalid timestamp format"

    def test_multiple_agents_returns_latest(self, mock_session_file, tmp_path):
        """
        Test that multiple agent entries return the latest one.

        Expected behavior:
        - Find multiple entries for same agent
        - Return the latest (chronologically last) entry
        - Track duplicates for warning

        Should FAIL: Method doesn't exist yet
        """
        # Create session text with duplicate agents
        session_text = tmp_path / "duplicate_session.md"
        content = """# Session test

**10:00:00 - researcher**: Starting research (first run)

**10:05:00 - researcher**: Research completed (first run)

**10:10:00 - researcher**: Starting research (second run)

**10:15:00 - researcher**: Research completed (second run)
"""
        session_text.write_text(content)

        tracker = AgentTracker(session_file=str(mock_session_file))

        # Act
        result = tracker._detect_agent_from_session_text("researcher", str(session_text))

        # Assert
        assert result is not None, "Should return latest entry"
        assert result["completed_at"] == "2025-11-11T10:15:00", "Should return second (latest) completion"


class TestJSONStructureAnalyzer:
    """Test _detect_agent_from_json_structure() method for external JSON modifications."""

    def test_valid_json_entry_returns_agent_data(self, mock_session_file):
        """
        Test that _detect_agent_from_json_structure() detects valid JSON entries.

        Expected behavior:
        - Read JSON session file
        - Find agent with status="completed"
        - Return agent data dict

        Should FAIL: Method doesn't exist yet
        """
        # Add agent directly to JSON (simulating external modification)
        tracker = AgentTracker(session_file=str(mock_session_file))
        session_data = json.loads(mock_session_file.read_text())
        session_data["agents"].append({
            "agent": "researcher",
            "status": "completed",
            "started_at": "2025-11-11T10:00:00",
            "completed_at": "2025-11-11T10:05:00",
            "duration_seconds": 300,
            "message": "Research completed"
        })
        mock_session_file.write_text(json.dumps(session_data, indent=2))

        # Act
        result = tracker._detect_agent_from_json_structure("researcher")

        # Assert
        assert result is not None, "Should detect agent in JSON"
        assert result["agent"] == "researcher", "Should identify correct agent"
        assert result["status"] == "completed", "Should have completed status"

    def test_incomplete_agent_returns_none(self, mock_session_file):
        """
        Test that incomplete agent (status="started") returns None.

        Expected behavior:
        - Find agent with status="started" (not completed)
        - Return None (agent hasn't finished)

        Should FAIL: Method doesn't exist yet
        """
        # Add incomplete agent to JSON
        tracker = AgentTracker(session_file=str(mock_session_file))
        session_data = json.loads(mock_session_file.read_text())
        session_data["agents"].append({
            "agent": "researcher",
            "status": "started",
            "started_at": "2025-11-11T10:00:00"
        })
        mock_session_file.write_text(json.dumps(session_data, indent=2))

        # Act
        result = tracker._detect_agent_from_json_structure("researcher")

        # Assert
        assert result is None, "Should return None for incomplete agent"

    def test_invalid_timestamps_returns_none(self, mock_session_file):
        """
        Test that invalid timestamps return None gracefully.

        Expected behavior:
        - Encounter invalid timestamp format
        - Handle gracefully (no crash)
        - Return None (can't validate timestamps)

        Should FAIL: Method doesn't exist yet
        """
        # Add agent with invalid timestamps
        tracker = AgentTracker(session_file=str(mock_session_file))
        session_data = json.loads(mock_session_file.read_text())
        session_data["agents"].append({
            "agent": "researcher",
            "status": "completed",
            "started_at": "INVALID_TIMESTAMP",
            "completed_at": "2025-11-11T10:05:00",
            "duration_seconds": 300
        })
        mock_session_file.write_text(json.dumps(session_data, indent=2))

        # Act
        result = tracker._detect_agent_from_json_structure("researcher")

        # Assert
        assert result is None, "Should return None for invalid timestamps"

    def test_external_json_modification_detected(self, mock_session_file):
        """
        Test that external JSON modifications are detected.

        Expected behavior:
        - Agent added directly to JSON (bypassing tracker)
        - JSON analyzer detects it
        - Returns valid agent data

        Should FAIL: Method doesn't exist yet
        """
        # Simulate external modification (direct JSON write)
        session_data = json.loads(mock_session_file.read_text())
        session_data["agents"].append({
            "agent": "external-agent",
            "status": "completed",
            "started_at": "2025-11-11T10:00:00",
            "completed_at": "2025-11-11T10:05:00",
            "duration_seconds": 300,
            "source": "external_modification"
        })
        mock_session_file.write_text(json.dumps(session_data, indent=2))

        # Create tracker AFTER external modification
        tracker = AgentTracker(session_file=str(mock_session_file))

        # Act
        result = tracker._detect_agent_from_json_structure("external-agent")

        # Assert
        assert result is not None, "Should detect externally-added agent"
        assert result["agent"] == "external-agent", "Should identify correct agent"


class TestEnhancedFindAgent:
    """Test enhanced _find_agent() with multi-method detection priority."""

    def test_priority_order_tracker_first(self, mock_session_file):
        """
        Test that _find_agent() checks tracker first (priority 1).

        Expected behavior:
        - Agent exists in tracker (via .start_agent())
        - Method returns immediately without checking JSON/text
        - Short-circuit evaluation for performance

        Should FAIL: Multi-method detection doesn't exist yet
        """
        tracker = AgentTracker(session_file=str(mock_session_file))
        tracker.start_agent("researcher", "Starting research")
        tracker.complete_agent("researcher", "Research completed")

        # Mock other methods to ensure they're NOT called
        with patch.object(tracker, '_detect_agent_from_json_structure') as mock_json, \
             patch.object(tracker, '_detect_agent_from_session_text') as mock_text:

            # Act
            result = tracker._find_agent("researcher")

            # Assert
            assert result is not None, "Should find agent from tracker"
            mock_json.assert_not_called()
            mock_text.assert_not_called()

    def test_priority_order_json_second(self, mock_session_file):
        """
        Test that _find_agent() checks JSON second (priority 2).

        Expected behavior:
        - Agent NOT in tracker
        - Agent exists in JSON (external modification)
        - Method checks JSON, returns result
        - Session text parser NOT called (short-circuit)

        Should FAIL: Multi-method detection doesn't exist yet
        """
        # Add agent directly to JSON
        session_data = json.loads(mock_session_file.read_text())
        session_data["agents"].append({
            "agent": "researcher",
            "status": "completed",
            "started_at": "2025-11-11T10:00:00",
            "completed_at": "2025-11-11T10:05:00",
            "duration_seconds": 300
        })
        mock_session_file.write_text(json.dumps(session_data, indent=2))

        tracker = AgentTracker(session_file=str(mock_session_file))
        # Clear tracker's in-memory agents to simulate "not tracked"
        tracker.session_data["agents"] = []

        # Mock session text parser to ensure it's NOT called
        with patch.object(tracker, '_detect_agent_from_session_text') as mock_text:

            # Act
            result = tracker._find_agent("researcher")

            # Assert
            assert result is not None, "Should find agent from JSON"
            assert result["agent"] == "researcher", "Should identify correct agent"
            mock_text.assert_not_called()

    def test_priority_order_text_third(self, mock_session_file, mock_session_text_file):
        """
        Test that _find_agent() checks session text last (priority 3).

        Expected behavior:
        - Agent NOT in tracker
        - Agent NOT in JSON
        - Agent exists in session text (.md file)
        - Method falls back to text parsing

        Should FAIL: Multi-method detection doesn't exist yet
        """
        tracker = AgentTracker(session_file=str(mock_session_file))
        # Clear all agents from tracker and JSON
        tracker.session_data["agents"] = []
        tracker._save()

        # Mock to provide session text file path
        with patch.object(tracker, '_get_session_text_file', return_value=str(mock_session_text_file)):

            # Act
            result = tracker._find_agent("researcher")

            # Assert
            assert result is not None, "Should find agent from session text"
            assert result["agent"] == "researcher", "Should identify correct agent"
            assert result["status"] == "completed", "Should parse completion status"

    def test_all_methods_fail_returns_none(self, mock_session_file):
        """
        Test that _find_agent() returns None when all methods fail.

        Expected behavior:
        - Agent NOT in tracker
        - Agent NOT in JSON
        - Agent NOT in session text
        - Method returns None (agent truly doesn't exist)

        Should FAIL: Multi-method detection doesn't exist yet
        """
        tracker = AgentTracker(session_file=str(mock_session_file))
        tracker.session_data["agents"] = []
        tracker._save()

        # Mock session text file to return None
        with patch.object(tracker, '_get_session_text_file', return_value=None):

            # Act
            result = tracker._find_agent("nonexistent-agent")

            # Assert
            assert result is None, "Should return None when agent doesn't exist anywhere"

    def test_duplicate_tracking_preserved(self, mock_session_file):
        """
        Test that duplicate agent tracking still works with multi-method detection.

        Expected behavior:
        - Multiple entries for same agent
        - Method tracks duplicates (for warning)
        - Returns latest entry

        Should FAIL: Multi-method detection doesn't exist yet
        """
        tracker = AgentTracker(session_file=str(mock_session_file))
        # Add duplicate agents
        tracker.start_agent("researcher", "First run")
        tracker.complete_agent("researcher", "First completed")
        tracker.start_agent("researcher", "Second run")
        tracker.complete_agent("researcher", "Second completed")

        # Act
        result = tracker._find_agent("researcher")

        # Assert
        assert result is not None, "Should find latest agent"
        assert hasattr(tracker, '_duplicate_agents'), "Should track duplicates"
        assert "researcher" in tracker._duplicate_agents, "Should flag researcher as duplicate"


class TestDataValidation:
    """Test _validate_agent_data() method for data integrity checks."""

    def test_valid_data_returns_true(self, mock_session_file):
        """
        Test that valid agent data passes validation.

        Expected behavior:
        - All required fields present
        - Valid status
        - Valid timestamps
        - Returns True

        Should FAIL: Method doesn't exist yet
        """
        tracker = AgentTracker(session_file=str(mock_session_file))

        valid_data = {
            "agent": "researcher",
            "status": "completed",
            "started_at": "2025-11-11T10:00:00",
            "completed_at": "2025-11-11T10:05:00",
            "duration_seconds": 300
        }

        # Act
        result = tracker._validate_agent_data(valid_data)

        # Assert
        assert result is True, "Should return True for valid data"

    def test_missing_fields_returns_false(self, mock_session_file):
        """
        Test that missing required fields fail validation.

        Expected behavior:
        - Missing "completed_at" field
        - Returns False

        Should FAIL: Method doesn't exist yet
        """
        tracker = AgentTracker(session_file=str(mock_session_file))

        invalid_data = {
            "agent": "researcher",
            "status": "completed",
            "started_at": "2025-11-11T10:00:00"
            # Missing completed_at
        }

        # Act
        result = tracker._validate_agent_data(invalid_data)

        # Assert
        assert result is False, "Should return False for missing fields"

    def test_invalid_status_returns_false(self, mock_session_file):
        """
        Test that invalid status values fail validation.

        Expected behavior:
        - status="unknown" (not in allowed values)
        - Returns False

        Should FAIL: Method doesn't exist yet
        """
        tracker = AgentTracker(session_file=str(mock_session_file))

        invalid_data = {
            "agent": "researcher",
            "status": "unknown",  # Invalid status
            "started_at": "2025-11-11T10:00:00",
            "completed_at": "2025-11-11T10:05:00"
        }

        # Act
        result = tracker._validate_agent_data(invalid_data)

        # Assert
        assert result is False, "Should return False for invalid status"

    def test_invalid_timestamps_returns_false(self, mock_session_file):
        """
        Test that invalid timestamp format fails validation.

        Expected behavior:
        - Malformed ISO timestamp
        - Returns False

        Should FAIL: Method doesn't exist yet
        """
        tracker = AgentTracker(session_file=str(mock_session_file))

        invalid_data = {
            "agent": "researcher",
            "status": "completed",
            "started_at": "INVALID_TIMESTAMP",
            "completed_at": "2025-11-11T10:05:00"
        }

        # Act
        result = tracker._validate_agent_data(invalid_data)

        # Assert
        assert result is False, "Should return False for invalid timestamps"


class TestEndToEndIntegration:
    """Test end-to-end integration with verify_parallel_exploration()."""

    @patch('scripts.agent_tracker.audit_log')
    def test_checkpoint_1_success_with_task_tool_agents(self, mock_audit, mock_session_file, mock_session_text_file):
        """
        Test CHECKPOINT 1 success when agents are Task tool invocations.

        Scenario:
        - Researcher and planner invoked via Task tool (not agent_tracker)
        - Agent completion logged to session text only
        - Multi-method detection finds them
        - verify_parallel_exploration() returns True

        Expected behavior:
        - _find_agent() falls back to session text parsing
        - Detects both agents completed
        - Calculates parallel vs sequential metrics
        - Returns True

        Should FAIL: Multi-method detection doesn't exist yet
        """
        tracker = AgentTracker(session_file=str(mock_session_file))
        # Clear agents from tracker (simulating Task tool usage)
        tracker.session_data["agents"] = []
        tracker._save()

        # Mock to provide session text file
        with patch.object(tracker, '_get_session_text_file', return_value=str(mock_session_text_file)):

            # Act
            result = tracker.verify_parallel_exploration()

            # Assert
            assert result is True, "Should return True when Task tool agents detected"

            # Check session file has parallel_exploration metadata
            session_data = json.loads(tracker.session_file.read_text())
            assert "parallel_exploration" in session_data, "Should write parallel_exploration metadata"

            metadata = session_data["parallel_exploration"]
            assert metadata["status"] == "parallel", "Should detect parallel execution"
            assert "time_saved_seconds" in metadata, "Should calculate time saved"

    @patch('scripts.agent_tracker.audit_log')
    def test_mixed_detection_methods(self, mock_audit, mock_session_file, mock_session_text_file):
        """
        Test mixed detection methods (one agent tracked, one from text).

        Scenario:
        - Researcher tracked via agent_tracker (normal)
        - Planner invoked via Task tool (session text only)
        - Multi-method detection handles both

        Expected behavior:
        - _find_agent("researcher") uses tracker
        - _find_agent("planner") falls back to text
        - Both detected successfully
        - Returns True

        Should FAIL: Multi-method detection doesn't exist yet
        """
        tracker = AgentTracker(session_file=str(mock_session_file))
        # Track researcher normally
        tracker.start_agent("researcher", "Starting research")
        tracker.complete_agent("researcher", "Research completed")
        # Planner only in session text (mock_session_text_file)

        # Mock to provide session text file
        with patch.object(tracker, '_get_session_text_file', return_value=str(mock_session_text_file)):

            # Act
            result = tracker.verify_parallel_exploration()

            # Assert
            assert result is True, "Should handle mixed detection methods"

    @patch('scripts.agent_tracker.audit_log')
    def test_backward_compatibility(self, mock_audit, mock_session_file):
        """
        Test backward compatibility with existing agent_tracker usage.

        Scenario:
        - Both agents tracked normally (via agent_tracker)
        - No session text parsing needed
        - Existing behavior preserved

        Expected behavior:
        - Multi-method detection short-circuits to tracker
        - Returns True (no behavioral change)

        Should FAIL: Multi-method detection doesn't exist yet
        """
        tracker = AgentTracker(session_file=str(mock_session_file))
        base_time = datetime.now()

        # Track both agents normally
        tracker.start_agent("researcher", "Starting research")
        tracker.session_data["agents"][-1]["started_at"] = base_time.isoformat()
        tracker.complete_agent("researcher", "Research completed")
        tracker.session_data["agents"][-1]["completed_at"] = (base_time + timedelta(seconds=300)).isoformat()
        tracker.session_data["agents"][-1]["duration_seconds"] = 300

        tracker.start_agent("planner", "Starting planning")
        tracker.session_data["agents"][-1]["started_at"] = (base_time + timedelta(seconds=2)).isoformat()
        tracker.complete_agent("planner", "Planning completed")
        tracker.session_data["agents"][-1]["completed_at"] = (base_time + timedelta(seconds=362)).isoformat()
        tracker.session_data["agents"][-1]["duration_seconds"] = 360

        tracker._save()

        # Act
        result = tracker.verify_parallel_exploration()

        # Assert
        assert result is True, "Should maintain backward compatibility"

        # Verify session text parsing was NOT used (short-circuit)
        session_data = json.loads(tracker.session_file.read_text())
        assert "parallel_exploration" in session_data, "Should write metadata"
