"""
Unit Tests for RALPH Loop Checkpoint/Resume Mechanism (Issue #276)

Tests checkpoint persistence and resume functionality for batch processing.
Ensures batches can survive context clears and resume from checkpoints.

Test Organization:
1. Checkpoint Persistence (7 tests) - Core checkpoint save/load
2. Resume from Checkpoint (6 tests) - Resume logic and state recovery
3. Checkpoint Coordination (5 tests) - Integration with batch auto-clear
4. Security Tests (4 tests) - Path validation and serialization safety
5. Edge Case Tests (5 tests) - Corruption, missing files, concurrent access

TDD Phase: RED (tests written BEFORE implementation)
Expected: All tests should FAIL initially - checkpoint functionality doesn't exist yet

Date: 2026-01-28
Issue: #276 (RALPH Loop Checkpoint/Resume for Batch Processing Persistence)
Agent: test-master
Status: RED (TDD red phase - no implementation yet)
"""

import json
import os
import sys
import tempfile
import threading
import time
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

# Add lib directory to path for imports
project_root = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(project_root / "plugins" / "autonomous-dev" / "lib"))

# Import existing modules
try:
    from ralph_loop_manager import (
        RalphLoopManager,
        RalphLoopState,
        MAX_ITERATIONS,
    )
    from batch_state_manager import (
        BatchState,
        create_batch_state,
        load_batch_state,
        save_batch_state,
        should_auto_clear,
        CONTEXT_THRESHOLD,
    )
except ImportError as e:
    pytest.skip(f"Required modules not found: {e}", allow_module_level=True)


# =============================================================================
# Test Fixtures
# =============================================================================

@pytest.fixture
def temp_checkpoint_dir(tmp_path):
    """Create temporary directory for checkpoint files."""
    checkpoint_dir = tmp_path / ".ralph-checkpoints"
    checkpoint_dir.mkdir()
    return checkpoint_dir


@pytest.fixture
def temp_batch_dir(tmp_path):
    """Create temporary directory for batch state."""
    batch_dir = tmp_path / ".claude"
    batch_dir.mkdir()
    return batch_dir


@pytest.fixture
def batch_id():
    """Sample batch ID for testing."""
    return "batch-20260128-123456"


@pytest.fixture
def sample_batch_features():
    """Sample feature list for batch processing."""
    return [
        "Feature 1: Add user authentication",
        "Feature 2: Implement API endpoints",
        "Feature 3: Add database migration",
        "Feature 4: Write integration tests",
        "Feature 5: Update documentation",
    ]


@pytest.fixture
def sample_batch_state(batch_id, sample_batch_features, temp_batch_dir):
    """Create sample BatchState for testing."""
    state = create_batch_state(
        features=sample_batch_features,
        batch_id=batch_id,
        state_file=str(temp_batch_dir / "batch_state.json")
    )
    return state


@pytest.fixture
def ralph_manager(temp_checkpoint_dir, batch_id):
    """Create RalphLoopManager instance for testing."""
    session_id = f"ralph-{batch_id}"
    return RalphLoopManager(session_id, state_dir=temp_checkpoint_dir)


# =============================================================================
# SECTION 1: Checkpoint Persistence Tests (7 tests)
# =============================================================================

class TestCheckpointPersistence:
    """Test checkpoint save and load functionality."""

    def test_checkpoint_saves_ralph_state_to_file(self, ralph_manager, temp_checkpoint_dir, batch_id):
        """
        Test Scenario 1: Checkpoint After Each Feature
        Verify checkpoint file is created with RALPH state.
        """
        # Arrange
        ralph_manager.record_attempt(tokens_used=5000)
        ralph_manager.record_attempt(tokens_used=3000)
        checkpoint_file = temp_checkpoint_dir / f"ralph-{batch_id}_checkpoint.json"

        # Act
        ralph_manager.checkpoint()

        # Assert - checkpoint file created
        assert checkpoint_file.exists()

        # Assert - checkpoint contains RALPH state
        data = json.loads(checkpoint_file.read_text())
        assert data["session_id"] == f"ralph-{batch_id}"
        assert data["current_iteration"] == 2
        assert data["tokens_used"] == 8000

    def test_checkpoint_saves_batch_context(self, ralph_manager, sample_batch_state, temp_checkpoint_dir, batch_id):
        """
        Test that checkpoint includes batch context (batch_id, current_index, completed features).
        """
        # Arrange
        sample_batch_state.current_index = 3
        sample_batch_state.completed_features = [0, 1, 2]
        sample_batch_state.failed_features = []

        # Act
        ralph_manager.checkpoint(batch_state=sample_batch_state)

        # Assert
        checkpoint_file = temp_checkpoint_dir / f"ralph-{batch_id}_checkpoint.json"
        data = json.loads(checkpoint_file.read_text())

        assert data["batch_id"] == batch_id
        assert data["current_feature_index"] == 3
        assert data["completed_features"] == [0, 1, 2]
        assert data["failed_features"] == []

    def test_checkpoint_includes_skipped_features(self, ralph_manager, sample_batch_state, temp_checkpoint_dir, batch_id):
        """
        Test that checkpoint includes skipped features for proper resume.
        """
        # Arrange
        sample_batch_state.current_index = 4
        sample_batch_state.completed_features = [0, 2]
        sample_batch_state.failed_features = [{"feature_index": 1, "error_message": "Failed"}]
        sample_batch_state.skipped_features = [{"feature_index": 3, "reason": "Quality gate"}]

        # Act
        ralph_manager.checkpoint(batch_state=sample_batch_state)

        # Assert
        checkpoint_file = temp_checkpoint_dir / f"ralph-{batch_id}_checkpoint.json"
        data = json.loads(checkpoint_file.read_text())

        assert data["skipped_features"] == [{"feature_index": 3, "reason": "Quality gate"}]

    def test_checkpoint_uses_atomic_write(self, ralph_manager, temp_checkpoint_dir):
        """
        Test that checkpoint uses atomic write pattern (temp + rename).
        Security requirement for data integrity.
        """
        # Arrange & Act
        with patch("tempfile.mkstemp") as mock_mkstemp, \
             patch("os.write") as mock_write, \
             patch("os.close") as mock_close, \
             patch("pathlib.Path.replace") as mock_replace:

            mock_mkstemp.return_value = (999, "/tmp/.checkpoint_abc.tmp")

            # Trigger checkpoint
            ralph_manager.checkpoint()

            # Assert - atomic write pattern used
            mock_mkstemp.assert_called()
            mock_write.assert_called()
            mock_close.assert_called()
            mock_replace.assert_called()

    def test_checkpoint_file_has_secure_permissions(self, ralph_manager, temp_checkpoint_dir, batch_id):
        """
        Security Test: Verify checkpoint file has 0600 permissions (owner only).
        Prevents unauthorized access to batch state.
        """
        # Arrange & Act
        ralph_manager.checkpoint()

        # Assert
        checkpoint_file = temp_checkpoint_dir / f"ralph-{batch_id}_checkpoint.json"
        file_mode = checkpoint_file.stat().st_mode & 0o777
        assert file_mode == 0o600, f"Expected 0o600, got {oct(file_mode)}"

    def test_checkpoint_saves_timestamp(self, ralph_manager, temp_checkpoint_dir, batch_id):
        """
        Test that checkpoint includes creation timestamp for tracking.
        """
        # Arrange & Act
        ralph_manager.checkpoint()

        # Assert
        checkpoint_file = temp_checkpoint_dir / f"ralph-{batch_id}_checkpoint.json"
        data = json.loads(checkpoint_file.read_text())

        assert "checkpoint_created_at" in data
        # Verify timestamp is ISO 8601 format
        assert "T" in data["checkpoint_created_at"]
        assert "Z" in data["checkpoint_created_at"]

    def test_checkpoint_survives_multiple_saves(self, ralph_manager, sample_batch_state, temp_checkpoint_dir, batch_id):
        """
        Test that checkpoints can be overwritten safely (atomic write ensures no corruption).
        """
        # Arrange
        sample_batch_state.current_index = 2
        ralph_manager.checkpoint(batch_state=sample_batch_state)

        # Act - update and checkpoint again
        sample_batch_state.current_index = 3
        ralph_manager.checkpoint(batch_state=sample_batch_state)

        # Assert - latest checkpoint persisted
        checkpoint_file = temp_checkpoint_dir / f"ralph-{batch_id}_checkpoint.json"
        data = json.loads(checkpoint_file.read_text())
        assert data["current_feature_index"] == 3


# =============================================================================
# SECTION 2: Resume from Checkpoint Tests (6 tests)
# =============================================================================

class TestResumeFromCheckpoint:
    """Test resume functionality from saved checkpoints."""

    def test_resume_batch_loads_checkpoint(self, temp_checkpoint_dir, batch_id, sample_batch_features):
        """
        Test Scenario 2: Resume From Checkpoint
        Verify resume_batch() loads checkpoint and returns state.
        """
        # Arrange - create checkpoint
        checkpoint_file = temp_checkpoint_dir / f"ralph-{batch_id}_checkpoint.json"
        checkpoint_data = {
            "session_id": f"ralph-{batch_id}",
            "batch_id": batch_id,
            "current_feature_index": 3,
            "completed_features": [0, 1, 2],
            "failed_features": [],
            "skipped_features": [],
            "total_features": 5,
            "features": sample_batch_features,
            "current_iteration": 2,
            "tokens_used": 10000,
            "checkpoint_created_at": "2026-01-28T10:00:00Z",
        }
        checkpoint_file.write_text(json.dumps(checkpoint_data, indent=2))
        checkpoint_file.chmod(0o600)

        # Act
        manager = RalphLoopManager.resume_batch(batch_id, state_dir=temp_checkpoint_dir)

        # Assert
        assert manager.session_id == f"ralph-{batch_id}"
        assert manager.current_iteration == 2
        assert manager.tokens_used == 10000

    def test_resume_batch_starts_at_next_feature(self, temp_checkpoint_dir, batch_id, sample_batch_features):
        """
        Test Scenario 2: Resume From Checkpoint
        Verify processing resumes at feature 4 after checkpoint at feature 3.
        """
        # Arrange - checkpoint at feature 3
        checkpoint_file = temp_checkpoint_dir / f"ralph-{batch_id}_checkpoint.json"
        checkpoint_data = {
            "session_id": f"ralph-{batch_id}",
            "batch_id": batch_id,
            "current_feature_index": 3,
            "completed_features": [0, 1, 2],
            "failed_features": [],
            "skipped_features": [],
            "total_features": 5,
            "features": sample_batch_features,
            "checkpoint_created_at": "2026-01-28T10:00:00Z",
        }
        checkpoint_file.write_text(json.dumps(checkpoint_data, indent=2))
        checkpoint_file.chmod(0o600)

        # Act
        manager = RalphLoopManager.resume_batch(batch_id, state_dir=temp_checkpoint_dir)
        batch_state = manager.get_batch_state()

        # Assert - next feature to process is index 3 (feature 4)
        assert batch_state.current_index == 3
        next_feature = batch_state.features[batch_state.current_index]
        assert next_feature == "Feature 4: Write integration tests"

    def test_resume_batch_skips_failed_features(self, temp_checkpoint_dir, batch_id, sample_batch_features):
        """
        Test Scenario 4: Failed Feature Doesn't Block Resume
        Verify resume skips feature 3 (failed) and processes features 4-5.
        """
        # Arrange - feature 3 failed, features 4-5 pending
        checkpoint_file = temp_checkpoint_dir / f"ralph-{batch_id}_checkpoint.json"
        checkpoint_data = {
            "session_id": f"ralph-{batch_id}",
            "batch_id": batch_id,
            "current_feature_index": 3,
            "completed_features": [0, 1],
            "failed_features": [{"feature_index": 2, "error_message": "Tests failed"}],
            "skipped_features": [],
            "total_features": 5,
            "features": sample_batch_features,
            "checkpoint_created_at": "2026-01-28T10:00:00Z",
        }
        checkpoint_file.write_text(json.dumps(checkpoint_data, indent=2))
        checkpoint_file.chmod(0o600)

        # Act
        manager = RalphLoopManager.resume_batch(batch_id, state_dir=temp_checkpoint_dir)
        batch_state = manager.get_batch_state()

        # Assert - failed feature 2 is skipped
        assert 2 in [f["feature_index"] for f in batch_state.failed_features]
        assert batch_state.current_index == 3  # Resume at feature 4

    def test_list_checkpoints_returns_all_checkpoints(self, temp_checkpoint_dir):
        """
        Test that list_checkpoints() returns all available checkpoint batch IDs.
        Enables rollback capability.
        """
        # Arrange - create multiple checkpoints
        batch_ids = ["batch-001", "batch-002", "batch-003"]
        for bid in batch_ids:
            checkpoint_file = temp_checkpoint_dir / f"ralph-{bid}_checkpoint.json"
            checkpoint_file.write_text(json.dumps({"batch_id": bid}))
            checkpoint_file.chmod(0o600)

        # Act
        checkpoints = RalphLoopManager.list_checkpoints(state_dir=temp_checkpoint_dir)

        # Assert
        assert len(checkpoints) == 3
        assert all(bid in checkpoints for bid in batch_ids)

    def test_rollback_to_checkpoint_restores_previous_state(self, temp_checkpoint_dir, batch_id, sample_batch_features):
        """
        Test Scenario 7: Rollback to Previous Checkpoint
        Verify rollback restores state to checkpoint (features 1-5 complete, 6 not started).
        """
        # Arrange - create checkpoint with 5 completed features
        checkpoint_file = temp_checkpoint_dir / f"ralph-{batch_id}_checkpoint.json"
        checkpoint_data = {
            "session_id": f"ralph-{batch_id}",
            "batch_id": batch_id,
            "current_feature_index": 5,
            "completed_features": [0, 1, 2, 3, 4],
            "failed_features": [],
            "skipped_features": [],
            "total_features": 10,
            "features": sample_batch_features + ["Feature 6", "Feature 7", "Feature 8", "Feature 9", "Feature 10"],
            "checkpoint_created_at": "2026-01-28T10:00:00Z",
        }
        checkpoint_file.write_text(json.dumps(checkpoint_data, indent=2))
        checkpoint_file.chmod(0o600)

        # Simulate current state with feature 6 started (error occurred)
        current_manager = RalphLoopManager(f"ralph-{batch_id}", state_dir=temp_checkpoint_dir)
        current_manager.record_attempt(tokens_used=5000)
        current_manager.record_failure("Feature 6 error")

        # Act - rollback to checkpoint
        rolled_back_manager = RalphLoopManager.rollback_to_checkpoint(batch_id, state_dir=temp_checkpoint_dir)
        batch_state = rolled_back_manager.get_batch_state()

        # Assert - state restored to checkpoint
        assert batch_state.current_index == 5
        assert batch_state.completed_features == [0, 1, 2, 3, 4]
        assert len(batch_state.failed_features) == 0  # Feature 6 error cleared

    def test_resume_batch_raises_error_if_checkpoint_missing(self, temp_checkpoint_dir):
        """
        Test that resume_batch() raises clear error if checkpoint doesn't exist.
        """
        # Arrange
        missing_batch_id = "batch-nonexistent"

        # Act & Assert
        with pytest.raises(FileNotFoundError, match="Checkpoint not found"):
            RalphLoopManager.resume_batch(missing_batch_id, state_dir=temp_checkpoint_dir)


# =============================================================================
# SECTION 3: Checkpoint Coordination Tests (5 tests)
# =============================================================================

class TestCheckpointCoordination:
    """Test coordination between checkpoint and batch auto-clear."""

    def test_should_auto_clear_triggers_checkpoint(self, ralph_manager, sample_batch_state, temp_checkpoint_dir):
        """
        Test Scenario 3: Context Limit Checkpoint
        Verify checkpoint is created before context clear when approaching 185K tokens.
        """
        # Arrange - set context to 184K tokens (just under new threshold)
        sample_batch_state.context_token_estimate = 184000
        checkpoint_callback_called = False

        def checkpoint_callback():
            nonlocal checkpoint_callback_called
            checkpoint_callback_called = True
            ralph_manager.checkpoint(batch_state=sample_batch_state)

        # Act - check if auto-clear needed with checkpoint callback
        needs_clear = should_auto_clear(sample_batch_state, checkpoint_callback=checkpoint_callback)

        # Assert
        assert needs_clear is False  # Not quite at threshold yet

        # Now exceed threshold
        sample_batch_state.context_token_estimate = 186000
        needs_clear = should_auto_clear(sample_batch_state, checkpoint_callback=checkpoint_callback)

        assert needs_clear is True
        assert checkpoint_callback_called is True  # Checkpoint triggered

    def test_context_threshold_increased_to_185k(self):
        """
        Test that CONTEXT_THRESHOLD is increased from 150K to 185K tokens.
        Implementation Plan Phase 3 requirement.
        """
        # Assert
        assert CONTEXT_THRESHOLD == 185000, f"Expected 185000, got {CONTEXT_THRESHOLD}"

    def test_checkpoint_before_context_clear_preserves_state(self, ralph_manager, sample_batch_state, temp_checkpoint_dir, batch_id):
        """
        Test that checkpoint before context clear preserves all state for resume.
        """
        # Arrange - simulate state before context clear
        sample_batch_state.current_index = 3
        sample_batch_state.completed_features = [0, 1, 2]
        sample_batch_state.context_token_estimate = 186000

        # Act - checkpoint before clear
        ralph_manager.checkpoint(batch_state=sample_batch_state)

        # Simulate context clear (reset token estimate)
        sample_batch_state.context_token_estimate = 0

        # Resume from checkpoint
        resumed_manager = RalphLoopManager.resume_batch(batch_id, state_dir=temp_checkpoint_dir)
        resumed_batch_state = resumed_manager.get_batch_state()

        # Assert - state preserved
        assert resumed_batch_state.current_index == 3
        assert resumed_batch_state.completed_features == [0, 1, 2]

    def test_multiple_resume_cycles_accumulate_progress(self, temp_checkpoint_dir, batch_id, sample_batch_features):
        """
        Test Scenario 5: Multiple Resume Cycles
        Verify batch processes features 1-10 across 3 resume cycles.
        """
        # Arrange - create 10-feature batch
        all_features = sample_batch_features + [f"Feature {i}" for i in range(6, 11)]

        # Cycle 1: Process features 1-3, checkpoint, resume
        checkpoint_1 = {
            "session_id": f"ralph-{batch_id}",
            "batch_id": batch_id,
            "current_feature_index": 3,
            "completed_features": [0, 1, 2],
            "failed_features": [],
            "skipped_features": [],
            "total_features": 10,
            "features": all_features,
            "checkpoint_created_at": "2026-01-28T10:00:00Z",
        }
        checkpoint_file = temp_checkpoint_dir / f"ralph-{batch_id}_checkpoint.json"
        checkpoint_file.write_text(json.dumps(checkpoint_1, indent=2))
        checkpoint_file.chmod(0o600)

        manager_1 = RalphLoopManager.resume_batch(batch_id, state_dir=temp_checkpoint_dir)
        batch_state_1 = manager_1.get_batch_state()
        assert batch_state_1.current_index == 3  # Resume at feature 4

        # Cycle 2: Process features 4-6, checkpoint, resume
        checkpoint_2 = {
            "session_id": f"ralph-{batch_id}",
            "batch_id": batch_id,
            "current_feature_index": 6,
            "completed_features": [0, 1, 2, 3, 4, 5],
            "failed_features": [],
            "skipped_features": [],
            "total_features": 10,
            "features": all_features,
            "checkpoint_created_at": "2026-01-28T11:00:00Z",
        }
        checkpoint_file.write_text(json.dumps(checkpoint_2, indent=2))

        manager_2 = RalphLoopManager.resume_batch(batch_id, state_dir=temp_checkpoint_dir)
        batch_state_2 = manager_2.get_batch_state()
        assert batch_state_2.current_index == 6  # Resume at feature 7

        # Cycle 3: Complete features 7-10
        checkpoint_3 = {
            "session_id": f"ralph-{batch_id}",
            "batch_id": batch_id,
            "current_feature_index": 10,
            "completed_features": [0, 1, 2, 3, 4, 5, 6, 7, 8, 9],
            "failed_features": [],
            "skipped_features": [],
            "total_features": 10,
            "features": all_features,
            "checkpoint_created_at": "2026-01-28T12:00:00Z",
        }
        checkpoint_file.write_text(json.dumps(checkpoint_3, indent=2))

        manager_3 = RalphLoopManager.resume_batch(batch_id, state_dir=temp_checkpoint_dir)
        batch_state_3 = manager_3.get_batch_state()

        # Assert - all 10 features completed across 3 cycles
        assert len(batch_state_3.completed_features) == 10
        assert batch_state_3.current_index == 10

    def test_checkpoint_callback_parameter_added_to_should_auto_clear(self):
        """
        Test that should_auto_clear() accepts checkpoint_callback parameter.
        Implementation Plan Phase 3 requirement.
        """
        # Arrange
        sample_state = BatchState(
            batch_id="test-batch",
            features_file="",
            total_features=5,
            features=["f1", "f2", "f3", "f4", "f5"],
            context_token_estimate=186000
        )
        callback_executed = False

        def test_callback():
            nonlocal callback_executed
            callback_executed = True

        # Act
        result = should_auto_clear(sample_state, checkpoint_callback=test_callback)

        # Assert - callback executed when threshold exceeded
        assert result is True
        assert callback_executed is True


# =============================================================================
# SECTION 4: Security Tests (4 tests)
# =============================================================================

class TestCheckpointSecurity:
    """Test security validations for checkpoint mechanism."""

    def test_checkpoint_path_validation_prevents_traversal(self, ralph_manager):
        """
        Security Test: CWE-22 Path Traversal Prevention
        Verify checkpoint paths are validated to prevent directory traversal.
        """
        # Arrange - attempt to checkpoint to dangerous path
        malicious_batch_id = "../../../etc/passwd"

        # Act & Assert
        with pytest.raises(ValueError, match="path traversal"):
            ralph_manager.checkpoint(batch_id=malicious_batch_id)

    def test_checkpoint_rejects_absolute_paths(self, ralph_manager):
        """
        Security Test: Reject absolute paths for batch_id
        Verify batch_id must be relative identifier, not absolute path.
        """
        # Arrange
        malicious_batch_id = "/tmp/malicious/checkpoint"

        # Act & Assert
        with pytest.raises(ValueError, match="absolute path"):
            ralph_manager.checkpoint(batch_id=malicious_batch_id)

    def test_checkpoint_uses_json_only_serialization(self, ralph_manager, temp_checkpoint_dir, batch_id):
        """
        Security Test: CWE-502 Deserialization of Untrusted Data
        Verify checkpoint uses JSON-only serialization (no pickle/exec).
        """
        # Arrange & Act
        ralph_manager.checkpoint()

        checkpoint_file = temp_checkpoint_dir / f"ralph-{batch_id}_checkpoint.json"
        content = checkpoint_file.read_text()

        # Assert - file is valid JSON (not pickle)
        data = json.loads(content)  # Will raise if not JSON
        assert isinstance(data, dict)

        # Verify no Python code execution markers
        assert "pickle" not in content
        assert "exec" not in content
        assert "__import__" not in content

    def test_resume_validates_checkpoint_file_permissions(self, temp_checkpoint_dir, batch_id):
        """
        Security Test: Verify resume rejects world-readable checkpoint files.
        """
        # Arrange - create checkpoint with insecure permissions
        checkpoint_file = temp_checkpoint_dir / f"ralph-{batch_id}_checkpoint.json"
        checkpoint_data = {
            "session_id": f"ralph-{batch_id}",
            "batch_id": batch_id,
            "current_feature_index": 0,
            "completed_features": [],
            "failed_features": [],
            "skipped_features": [],
            "total_features": 5,
            "features": ["f1", "f2", "f3", "f4", "f5"],
        }
        checkpoint_file.write_text(json.dumps(checkpoint_data, indent=2))
        checkpoint_file.chmod(0o644)  # World-readable (insecure)

        # Act & Assert
        with pytest.raises(PermissionError, match="insecure permissions"):
            RalphLoopManager.resume_batch(batch_id, state_dir=temp_checkpoint_dir)


# =============================================================================
# SECTION 5: Edge Case Tests (5 tests)
# =============================================================================

class TestCheckpointEdgeCases:
    """Test edge cases and error handling for checkpoints."""

    def test_checkpoint_corruption_recovery_uses_fallback(self, temp_checkpoint_dir, batch_id):
        """
        Test Scenario 6: Checkpoint Corruption Recovery
        Verify corrupted checkpoint falls back to previous checkpoint.
        """
        # Arrange - create valid checkpoint (version 1)
        checkpoint_file = temp_checkpoint_dir / f"ralph-{batch_id}_checkpoint.json"
        checkpoint_v1 = {
            "session_id": f"ralph-{batch_id}",
            "batch_id": batch_id,
            "current_feature_index": 2,
            "completed_features": [0, 1],
            "version": 1,
        }
        checkpoint_file.write_text(json.dumps(checkpoint_v1, indent=2))
        checkpoint_file.chmod(0o600)

        # Create backup checkpoint
        backup_file = temp_checkpoint_dir / f"ralph-{batch_id}_checkpoint.json.bak"
        backup_file.write_text(json.dumps(checkpoint_v1, indent=2))
        backup_file.chmod(0o600)

        # Corrupt current checkpoint
        checkpoint_file.write_text("{invalid json")

        # Act - attempt resume (should fall back to backup)
        manager = RalphLoopManager.resume_batch(batch_id, state_dir=temp_checkpoint_dir)
        batch_state = manager.get_batch_state()

        # Assert - recovered from backup
        assert batch_state.current_index == 2
        assert batch_state.completed_features == [0, 1]

    def test_concurrent_checkpoint_writes_are_thread_safe(self, ralph_manager, sample_batch_state, temp_checkpoint_dir):
        """
        Test that concurrent checkpoint writes don't corrupt state.
        """
        # Arrange
        num_threads = 5
        results = []

        def checkpoint_worker(feature_index):
            try:
                sample_batch_state.current_index = feature_index
                ralph_manager.checkpoint(batch_state=sample_batch_state)
                results.append("success")
            except Exception as e:
                results.append(f"error: {e}")

        # Act - spawn concurrent checkpoint threads
        threads = [threading.Thread(target=checkpoint_worker, args=(i,)) for i in range(num_threads)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        # Assert - all threads succeeded
        assert len(results) == num_threads
        assert all(r == "success" for r in results)

    def test_checkpoint_with_missing_batch_state_creates_minimal_checkpoint(self, ralph_manager, temp_checkpoint_dir, batch_id):
        """
        Test that checkpoint without batch_state creates minimal RALPH-only checkpoint.
        """
        # Arrange & Act
        ralph_manager.record_attempt(tokens_used=1000)
        ralph_manager.checkpoint()  # No batch_state parameter

        # Assert
        checkpoint_file = temp_checkpoint_dir / f"ralph-{batch_id}_checkpoint.json"
        data = json.loads(checkpoint_file.read_text())

        # Minimal checkpoint has RALPH state but no batch context
        assert "session_id" in data
        assert "current_iteration" in data
        assert "batch_id" not in data  # No batch context

    def test_resume_with_version_mismatch_handles_gracefully(self, temp_checkpoint_dir, batch_id):
        """
        Test that resume handles checkpoint version mismatch gracefully.
        """
        # Arrange - create checkpoint with future version
        checkpoint_file = temp_checkpoint_dir / f"ralph-{batch_id}_checkpoint.json"
        checkpoint_data = {
            "session_id": f"ralph-{batch_id}",
            "batch_id": batch_id,
            "current_feature_index": 2,
            "completed_features": [0, 1],
            "checkpoint_version": "99.0.0",  # Future version
            "total_features": 5,
            "features": ["f1", "f2", "f3", "f4", "f5"],
        }
        checkpoint_file.write_text(json.dumps(checkpoint_data, indent=2))
        checkpoint_file.chmod(0o600)

        # Act - attempt resume (should warn but continue)
        with pytest.warns(UserWarning, match="checkpoint version"):
            manager = RalphLoopManager.resume_batch(batch_id, state_dir=temp_checkpoint_dir)
            batch_state = manager.get_batch_state()

        # Assert - resume succeeded with warning
        assert batch_state.current_index == 2

    def test_checkpoint_cleanup_removes_old_checkpoints(self, temp_checkpoint_dir, batch_id):
        """
        Test that checkpoint cleanup removes old checkpoints to save space.
        """
        # Arrange - create multiple checkpoints
        for i in range(5):
            checkpoint_file = temp_checkpoint_dir / f"ralph-batch-00{i}_checkpoint.json"
            checkpoint_file.write_text(json.dumps({"batch_id": f"batch-00{i}"}))
            checkpoint_file.chmod(0o600)
            time.sleep(0.01)  # Ensure different timestamps

        # Act - cleanup old checkpoints (keep only 3 most recent)
        RalphLoopManager.cleanup_old_checkpoints(state_dir=temp_checkpoint_dir, keep_count=3)

        # Assert - only 3 checkpoints remain
        remaining_checkpoints = list(temp_checkpoint_dir.glob("ralph-*_checkpoint.json"))
        assert len(remaining_checkpoints) == 3


# =============================================================================
# Test Summary
# =============================================================================

"""
TEST SUMMARY (27 unit tests for RALPH Loop Checkpoint/Resume):

SECTION 1: Checkpoint Persistence (7 tests)
✗ test_checkpoint_saves_ralph_state_to_file
✗ test_checkpoint_saves_batch_context
✗ test_checkpoint_includes_skipped_features
✗ test_checkpoint_uses_atomic_write
✗ test_checkpoint_file_has_secure_permissions
✗ test_checkpoint_saves_timestamp
✗ test_checkpoint_survives_multiple_saves

SECTION 2: Resume from Checkpoint (6 tests)
✗ test_resume_batch_loads_checkpoint
✗ test_resume_batch_starts_at_next_feature
✗ test_resume_batch_skips_failed_features
✗ test_list_checkpoints_returns_all_checkpoints
✗ test_rollback_to_checkpoint_restores_previous_state
✗ test_resume_batch_raises_error_if_checkpoint_missing

SECTION 3: Checkpoint Coordination (5 tests)
✗ test_should_auto_clear_triggers_checkpoint
✗ test_context_threshold_increased_to_185k
✗ test_checkpoint_before_context_clear_preserves_state
✗ test_multiple_resume_cycles_accumulate_progress
✗ test_checkpoint_callback_parameter_added_to_should_auto_clear

SECTION 4: Security Tests (4 tests)
✗ test_checkpoint_path_validation_prevents_traversal
✗ test_checkpoint_rejects_absolute_paths
✗ test_checkpoint_uses_json_only_serialization
✗ test_resume_validates_checkpoint_file_permissions

SECTION 5: Edge Case Tests (5 tests)
✗ test_checkpoint_corruption_recovery_uses_fallback
✗ test_concurrent_checkpoint_writes_are_thread_safe
✗ test_checkpoint_with_missing_batch_state_creates_minimal_checkpoint
✗ test_resume_with_version_mismatch_handles_gracefully
✗ test_checkpoint_cleanup_removes_old_checkpoints

Expected Status: ALL TESTS FAILING (RED phase - implementation doesn't exist yet)
Next Step: Implement checkpoint/resume methods in ralph_loop_manager.py (GREEN phase)

Coverage Target: 80%+ for checkpoint functionality
"""
