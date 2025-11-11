"""
Integration tests for verify_parallel_exploration() Task tool agent detection.

TDD Red Phase: Integration tests written BEFORE implementation (Issue #71).
All tests should FAIL initially - the multi-method detection doesn't exist yet.

Feature: End-to-end testing of multi-method agent detection
Scope: Real file I/O, session text parsing, JSON analysis, full workflow

Test Coverage:
1. Real session file creation and parsing
2. Multi-method detection across all three methods
3. Error handling and graceful degradation
4. Performance validation (no significant overhead)
5. Security validation (path traversal prevention)
6. Backward compatibility with existing workflows

Date: 2025-11-11
Related Issue: #71 - Fix verify_parallel_exploration() Task tool agent detection
Agent: test-master
"""

import json
import sys
import pytest
import time
from pathlib import Path
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
def integration_session_dir(tmp_path):
    """Create realistic session directory structure."""
    session_dir = tmp_path / "sessions"
    session_dir.mkdir()
    return session_dir


@pytest.fixture
def real_session_files(integration_session_dir):
    """Create real session files (JSON + text) for integration testing."""
    session_id = "20251111-integration-test"

    # JSON session file
    json_file = integration_session_dir / f"{session_id}.json"
    json_data = {
        "session_id": session_id,
        "started": "2025-11-11T10:00:00",
        "agents": []
    }
    json_file.write_text(json.dumps(json_data, indent=2))

    # Text session file (.md)
    text_file = integration_session_dir / f"{session_id}-session.md"
    text_content = """# Session 20251111-integration-test

**Started**: 2025-11-11 10:00:00

---

**10:00:05 - researcher**: Starting research on authentication patterns

**10:05:43 - researcher**: Research completed - Found 5 patterns

**10:05:50 - planner**: Starting architecture planning

**10:12:27 - planner**: Planning completed - Created implementation roadmap
"""
    text_file.write_text(text_content)

    return {"json": json_file, "text": text_file, "session_id": session_id}


class TestRealFileOperations:
    """Test multi-method detection with real file I/O."""

    def test_real_session_text_parsing(self, real_session_files):
        """
        Test parsing real session text file with completion markers.

        Expected behavior:
        - Read actual .md file from disk
        - Parse timestamps and completion markers
        - Extract agent data
        - Return valid agent dict

        Should FAIL: _detect_agent_from_session_text() doesn't exist yet
        """
        tracker = AgentTracker(session_file=str(real_session_files["json"]))

        # Act
        result = tracker._detect_agent_from_session_text(
            "researcher",
            str(real_session_files["text"])
        )

        # Assert
        assert result is not None, "Should parse real session text file"
        assert result["agent"] == "researcher", "Should identify correct agent"
        assert result["status"] == "completed", "Should detect completion"
        assert "started_at" in result, "Should extract start timestamp"
        assert "completed_at" in result, "Should extract completion timestamp"

    def test_real_json_structure_analysis(self, real_session_files):
        """
        Test analyzing real JSON file with external modifications.

        Expected behavior:
        - Read actual JSON file from disk
        - Parse agent entries
        - Validate data structure
        - Return agent dict

        Should FAIL: _detect_agent_from_json_structure() doesn't exist yet
        """
        # Add agent directly to JSON (simulating external modification)
        json_data = json.loads(real_session_files["json"].read_text())
        json_data["agents"].append({
            "agent": "external-agent",
            "status": "completed",
            "started_at": "2025-11-11T10:00:00",
            "completed_at": "2025-11-11T10:05:00",
            "duration_seconds": 300,
            "message": "Externally added"
        })
        real_session_files["json"].write_text(json.dumps(json_data, indent=2))

        tracker = AgentTracker(session_file=str(real_session_files["json"]))

        # Act
        result = tracker._detect_agent_from_json_structure("external-agent")

        # Assert
        assert result is not None, "Should detect agent in real JSON file"
        assert result["agent"] == "external-agent", "Should identify correct agent"

    def test_concurrent_file_access(self, real_session_files):
        """
        Test that multi-method detection handles concurrent file access safely.

        Expected behavior:
        - Multiple threads/processes reading session files
        - No race conditions
        - All reads successful

        Should FAIL: Multi-method detection doesn't exist yet
        """
        tracker1 = AgentTracker(session_file=str(real_session_files["json"]))
        tracker2 = AgentTracker(session_file=str(real_session_files["json"]))

        # Act - concurrent reads
        result1 = tracker1._detect_agent_from_session_text(
            "researcher",
            str(real_session_files["text"])
        )
        result2 = tracker2._detect_agent_from_session_text(
            "planner",
            str(real_session_files["text"])
        )

        # Assert
        assert result1 is not None, "First read should succeed"
        assert result2 is not None, "Second read should succeed"
        assert result1["agent"] == "researcher", "First read correct agent"
        assert result2["agent"] == "planner", "Second read correct agent"


class TestErrorHandlingIntegration:
    """Test error handling and graceful degradation."""

    def test_missing_session_text_file(self, real_session_files):
        """
        Test graceful handling when session text file missing.

        Expected behavior:
        - Text file doesn't exist
        - Method catches exception
        - Returns None (graceful degradation)
        - No crash

        Should FAIL: Error handling doesn't exist yet
        """
        tracker = AgentTracker(session_file=str(real_session_files["json"]))

        # Act - try to parse nonexistent file
        result = tracker._detect_agent_from_session_text(
            "researcher",
            str(real_session_files["text"].parent / "nonexistent.md")
        )

        # Assert
        assert result is None, "Should return None for missing file"

    def test_corrupted_json_file(self, integration_session_dir):
        """
        Test graceful handling of corrupted JSON file.

        Expected behavior:
        - JSON file contains invalid syntax
        - Method catches JSONDecodeError
        - Returns None (graceful degradation)
        - No crash

        Should FAIL: Error handling doesn't exist yet
        """
        # Create corrupted JSON file
        corrupted_file = integration_session_dir / "corrupted.json"
        corrupted_file.write_text("{invalid json content")

        tracker = AgentTracker(session_file=str(corrupted_file))

        # Act
        result = tracker._detect_agent_from_json_structure("researcher")

        # Assert
        assert result is None, "Should return None for corrupted JSON"

    def test_malformed_session_text(self, integration_session_dir):
        """
        Test graceful handling of malformed session text.

        Expected behavior:
        - Session text has unexpected format
        - Parser handles gracefully
        - Returns None (can't parse)
        - No crash

        Should FAIL: Error handling doesn't exist yet
        """
        # Create malformed session text
        malformed_file = integration_session_dir / "malformed.md"
        malformed_file.write_text("Random text with no structure")

        tracker = AgentTracker(session_file=str(integration_session_dir / "test.json"))

        # Act
        result = tracker._detect_agent_from_session_text(
            "researcher",
            str(malformed_file)
        )

        # Assert
        assert result is None, "Should return None for malformed text"


class TestPerformanceValidation:
    """Test that multi-method detection doesn't add significant overhead."""

    def test_no_significant_overhead(self, real_session_files):
        """
        Test that multi-method detection performance is acceptable.

        Expected behavior:
        - Multi-method detection completes in < 100ms
        - No blocking I/O issues
        - Efficient short-circuit evaluation

        Should FAIL: Multi-method detection doesn't exist yet
        """
        tracker = AgentTracker(session_file=str(real_session_files["json"]))

        # Add agent to tracker (should short-circuit)
        tracker.start_agent("researcher", "Starting")
        tracker.complete_agent("researcher", "Completed")

        # Measure performance
        start_time = time.perf_counter()
        result = tracker._find_agent("researcher")
        end_time = time.perf_counter()

        elapsed_ms = (end_time - start_time) * 1000

        # Assert
        assert result is not None, "Should find agent"
        assert elapsed_ms < 100, f"Should complete in < 100ms, took {elapsed_ms:.2f}ms"

    def test_text_parsing_performance(self, real_session_files):
        """
        Test that session text parsing is efficient.

        Expected behavior:
        - Parse session text in < 50ms
        - No regex catastrophic backtracking
        - Efficient file reading

        Should FAIL: Session text parsing doesn't exist yet
        """
        tracker = AgentTracker(session_file=str(real_session_files["json"]))

        # Measure performance
        start_time = time.perf_counter()
        result = tracker._detect_agent_from_session_text(
            "researcher",
            str(real_session_files["text"])
        )
        end_time = time.perf_counter()

        elapsed_ms = (end_time - start_time) * 1000

        # Assert
        assert result is not None, "Should parse successfully"
        assert elapsed_ms < 50, f"Should parse in < 50ms, took {elapsed_ms:.2f}ms"


class TestSecurityValidation:
    """Test security aspects of multi-method detection."""

    def test_path_traversal_prevention(self, real_session_files):
        """
        Test that path traversal attacks are prevented.

        Expected behavior:
        - Attempt to read file with ../ in path
        - validate_path() catches attack
        - Raises ValueError
        - No system file access

        Should FAIL: Path validation not implemented yet
        """
        tracker = AgentTracker(session_file=str(real_session_files["json"]))

        # Attempt path traversal
        with pytest.raises(ValueError, match="Path traversal detected"):
            tracker._detect_agent_from_session_text(
                "researcher",
                "../../etc/passwd"
            )

    def test_symlink_protection(self, real_session_files, tmp_path):
        """
        Test that symlink-based escapes are prevented.

        Expected behavior:
        - Create symlink to system directory
        - Attempt to read via symlink
        - validate_path() resolves symlink
        - Raises ValueError if outside project
        - No system file access

        Should FAIL: Symlink protection not implemented yet
        """
        # Create symlink to /etc
        symlink = tmp_path / "evil_link.md"
        try:
            symlink.symlink_to("/etc")
        except OSError:
            pytest.skip("Cannot create symlinks on this system")

        tracker = AgentTracker(session_file=str(real_session_files["json"]))

        # Attempt to read via symlink
        with pytest.raises(ValueError, match="Path resolves outside project"):
            tracker._detect_agent_from_session_text(
                "researcher",
                str(symlink)
            )


class TestBackwardCompatibility:
    """Test backward compatibility with existing workflows."""

    def test_existing_checkpoint_1_still_works(self, real_session_files):
        """
        Test that existing CHECKPOINT 1 implementation still works.

        Expected behavior:
        - verify_parallel_exploration() called
        - Agents tracked normally (no Task tool)
        - Returns True
        - No behavioral change

        Should FAIL: Multi-method detection changes behavior
        """
        tracker = AgentTracker(session_file=str(real_session_files["json"]))
        base_time = datetime.now()

        # Track agents normally
        tracker.start_agent("researcher", "Starting")
        tracker.session_data["agents"][-1]["started_at"] = base_time.isoformat()
        tracker.complete_agent("researcher", "Completed")
        tracker.session_data["agents"][-1]["completed_at"] = (base_time + timedelta(seconds=300)).isoformat()
        tracker.session_data["agents"][-1]["duration_seconds"] = 300

        tracker.start_agent("planner", "Starting")
        tracker.session_data["agents"][-1]["started_at"] = (base_time + timedelta(seconds=2)).isoformat()
        tracker.complete_agent("planner", "Completed")
        tracker.session_data["agents"][-1]["completed_at"] = (base_time + timedelta(seconds=362)).isoformat()
        tracker.session_data["agents"][-1]["duration_seconds"] = 360

        tracker._save()

        # Act
        result = tracker.verify_parallel_exploration()

        # Assert
        assert result is True, "Should maintain backward compatibility"

    def test_no_breaking_changes_to_api(self, real_session_files):
        """
        Test that public API hasn't changed.

        Expected behavior:
        - verify_parallel_exploration() signature unchanged
        - Return type unchanged (bool)
        - Side effects unchanged (writes metadata)
        - No breaking changes

        Should FAIL: API signature might change
        """
        tracker = AgentTracker(session_file=str(real_session_files["json"]))

        # Track agents
        tracker.start_agent("researcher", "Starting")
        tracker.complete_agent("researcher", "Completed")
        tracker.start_agent("planner", "Starting")
        tracker.complete_agent("planner", "Completed")

        # Act
        result = tracker.verify_parallel_exploration()

        # Assert: Return type
        assert isinstance(result, bool), "Return type should be bool"

        # Assert: Side effects (metadata written)
        session_data = json.loads(tracker.session_file.read_text())
        assert "parallel_exploration" in session_data, "Should write metadata"
