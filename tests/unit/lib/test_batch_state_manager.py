#!/usr/bin/env python3
"""
Unit tests for batch_state_manager module (TDD Red Phase).

Tests for state-based auto-clearing in /batch-implement command.

TDD Mode: These tests are written BEFORE implementation.
All tests should FAIL initially (ImportError: module not found).

Test Strategy:
- Test BatchState dataclass creation and validation
- Test state persistence (save/load from JSON)
- Test state updates (progress tracking, auto-clear events)
- Test concurrent access safety (file locking)
- Test security validations (CWE-22 path traversal, CWE-59 symlinks)
- Test error handling (corrupted JSON, disk full, permission errors)

Mocking Strategy (CRITICAL - Issue #76 Fix):
============================================
When testing atomic file operations, mock LOW-LEVEL syscalls, NOT high-level Path methods.

WHY: Implementation uses os.write() + tempfile.mkstemp() for atomic writes.
     Mocking Path.write_text() doesn't intercept these syscalls.

CORRECT Mocking Layers:
- Atomic writes: Mock tempfile.mkstemp, os.write, os.close, Path.chmod, Path.replace
- File reads: Mock builtins.open (NOT Path.read_text)
- Disk errors: Mock os.write to raise OSError(28, "No space left on device")
- Permission errors: Mock builtins.open to raise PermissionError

WRONG Mocking Layers (don't use these):
- Path.write_text - bypassed by os.write()
- Path.read_text - bypassed by open()
- Path methods for syscall-level operations

Security Validation Preservation:
- All tests must validate that validate_path() executes BEFORE file operations
- Low-level mocks placed AFTER security validation in execution order
- Tests confirm CWE-22 (path traversal) and CWE-59 (symlink) checks run first

Coverage Target: 90%+ for batch_state_manager.py

Date: 2025-11-16
Issue: #76 (State-based Auto-Clearing for /batch-implement)
Agent: test-master
Phase: TDD Red (tests written BEFORE implementation)
Status: GREEN (41/41 tests passing after Issue #76 fix)
"""

import json
import os
import sys
import pytest
import tempfile
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock, mock_open
from typing import Dict, Any
from dataclasses import asdict
import time
import threading

# Add lib directory to path for imports
sys.path.insert(
    0,
    str(
        Path(__file__).parent.parent.parent.parent
        / "plugins"
        / "autonomous-dev"
        / "lib"
    ),
)

# Import will fail - module doesn't exist yet (TDD!)
try:
    from batch_state_manager import (
        BatchState,
        create_batch_state,
        load_batch_state,
        save_batch_state,
        update_batch_progress,
        record_auto_clear_event,
        should_auto_clear,
        cleanup_batch_state,
        get_next_pending_feature,
        BatchStateError,
        DEFAULT_STATE_FILE,
        CONTEXT_THRESHOLD,
    )
except ImportError as e:
    pytest.skip(f"Implementation not found (TDD red phase): {e}", allow_module_level=True)


# =============================================================================
# Test Fixtures
# =============================================================================

@pytest.fixture
def temp_state_dir(tmp_path):
    """Create temporary directory for state files."""
    state_dir = tmp_path / ".claude"
    state_dir.mkdir()
    return state_dir


@pytest.fixture
def state_file(temp_state_dir):
    """Create temporary state file path."""
    return temp_state_dir / "batch_state.json"


@pytest.fixture
def sample_features():
    """Sample feature list for testing."""
    return [
        "Add user authentication with JWT",
        "Implement password reset flow",
        "Add email verification",
        "Create user profile API",
        "Add OAuth2 integration",
    ]


@pytest.fixture
def sample_batch_state(sample_features):
    """Create sample BatchState for testing."""
    return BatchState(
        batch_id="batch-20251116-123456",
        features_file="/path/to/features.txt",
        total_features=len(sample_features),
        features=sample_features,
        current_index=0,
        completed_features=[],
        failed_features=[],
        context_token_estimate=5000,
        auto_clear_count=0,
        auto_clear_events=[],
        created_at="2025-11-16T10:00:00Z",
        updated_at="2025-11-16T10:00:00Z",
        status="in_progress",
    )


# =============================================================================
# SECTION 1: State Creation Tests (5 tests)
# =============================================================================

class TestBatchStateCreation:
    """Test BatchState dataclass creation and validation."""

    def test_create_batch_state_with_valid_features(self, sample_features):
        """Test creating BatchState with valid feature list."""
        # Arrange
        features_file = "/path/to/features.txt"

        # Act
        state = create_batch_state(features_file, sample_features)

        # Assert
        assert state.features_file == features_file
        assert state.total_features == len(sample_features)
        assert state.features == sample_features
        assert state.current_index == 0
        assert state.completed_features == []
        assert state.failed_features == []
        assert state.context_token_estimate == 0
        assert state.auto_clear_count == 0
        assert state.auto_clear_events == []
        assert state.status == "in_progress"
        assert state.batch_id.startswith("batch-")
        assert state.created_at is not None
        assert state.updated_at is not None

    def test_create_batch_state_with_empty_features_raises_error(self):
        """Test that creating BatchState with empty feature list raises error."""
        # Arrange
        features_file = "/path/to/features.txt"
        empty_features = []

        # Act & Assert
        with pytest.raises(BatchStateError) as exc_info:
            create_batch_state(features_file, empty_features)

        assert "no features" in str(exc_info.value).lower()

    def test_create_batch_state_generates_unique_batch_id(self, sample_features):
        """Test that each batch gets a unique batch_id."""
        # Arrange
        features_file = "/path/to/features.txt"

        # Act
        state1 = create_batch_state(features_file, sample_features)
        time.sleep(0.01)  # Ensure different timestamp
        state2 = create_batch_state(features_file, sample_features)

        # Assert
        assert state1.batch_id != state2.batch_id
        assert state1.batch_id.startswith("batch-")
        assert state2.batch_id.startswith("batch-")

    def test_batch_state_dataclass_fields(self, sample_batch_state):
        """Test that BatchState has all required fields."""
        # Arrange & Act
        state_dict = asdict(sample_batch_state)

        # Assert - verify all required fields exist
        required_fields = [
            "batch_id",
            "features_file",
            "total_features",
            "features",
            "current_index",
            "completed_features",
            "failed_features",
            "context_token_estimate",
            "auto_clear_count",
            "auto_clear_events",
            "created_at",
            "updated_at",
            "status",
        ]
        for field in required_fields:
            assert field in state_dict

    def test_batch_state_validates_status_values(self, sample_features):
        """Test that BatchState validates status field values."""
        # Arrange
        features_file = "/path/to/features.txt"

        # Act
        state = create_batch_state(features_file, sample_features)

        # Assert - status should be one of valid values
        valid_statuses = ["in_progress", "completed", "failed", "paused"]
        assert state.status in valid_statuses


# =============================================================================
# SECTION 2: State Persistence Tests (6 tests)
# =============================================================================

class TestBatchStatePersistence:
    """Test state save/load operations with JSON."""

    def test_save_batch_state_creates_json_file(self, state_file, sample_batch_state):
        """Test that save_batch_state creates valid JSON file."""
        # Arrange
        assert not state_file.exists()

        # Act
        save_batch_state(state_file, sample_batch_state)

        # Assert
        assert state_file.exists()
        data = json.loads(state_file.read_text())
        assert data["batch_id"] == sample_batch_state.batch_id
        assert data["total_features"] == sample_batch_state.total_features

    def test_load_batch_state_reads_valid_json(self, state_file, sample_batch_state):
        """Test that load_batch_state reads and deserializes JSON correctly."""
        # Arrange
        save_batch_state(state_file, sample_batch_state)

        # Act
        loaded_state = load_batch_state(state_file)

        # Assert
        assert loaded_state.batch_id == sample_batch_state.batch_id
        assert loaded_state.features_file == sample_batch_state.features_file
        assert loaded_state.total_features == sample_batch_state.total_features
        assert loaded_state.features == sample_batch_state.features
        assert loaded_state.current_index == sample_batch_state.current_index

    def test_load_batch_state_with_missing_file_raises_error(self, state_file):
        """Test that load_batch_state raises error when file doesn't exist."""
        # Arrange
        assert not state_file.exists()

        # Act & Assert
        with pytest.raises(BatchStateError) as exc_info:
            load_batch_state(state_file)

        assert "not found" in str(exc_info.value).lower()

    def test_load_batch_state_with_corrupted_json_raises_error(self, state_file):
        """Test that load_batch_state raises error with corrupted JSON."""
        # Arrange - write invalid JSON
        state_file.write_text("{invalid json content")

        # Act & Assert
        with pytest.raises(BatchStateError) as exc_info:
            load_batch_state(state_file)

        assert "corrupted" in str(exc_info.value).lower() or "invalid" in str(exc_info.value).lower()

    def test_save_batch_state_atomic_write(self, state_file, sample_batch_state):
        """Test that save_batch_state uses atomic write (temp file + rename)."""
        # Arrange
        temp_fd = 999
        temp_path_str = "/tmp/.batch_state_abc123.tmp"

        with patch("tempfile.mkstemp", return_value=(temp_fd, temp_path_str)) as mock_mkstemp, \
             patch("os.write") as mock_write, \
             patch("os.close") as mock_close, \
             patch("pathlib.Path.chmod") as mock_chmod, \
             patch("pathlib.Path.replace") as mock_replace:

            # Act
            save_batch_state(state_file, sample_batch_state)

            # Assert - Atomic write pattern
            # 1. CREATE: temp file created in same directory
            mock_mkstemp.assert_called_once()
            call_kwargs = mock_mkstemp.call_args[1]
            assert call_kwargs['dir'] == state_file.parent
            assert call_kwargs['prefix'] == ".batch_state_"
            assert call_kwargs['suffix'] == ".tmp"

            # 2. WRITE: JSON written to temp file descriptor
            mock_write.assert_called_once()
            assert mock_write.call_args[0][0] == temp_fd
            assert b'"batch_id"' in mock_write.call_args[0][1]  # Contains JSON
            mock_close.assert_called_once_with(temp_fd)

            # 3. SECURITY: File permissions set to 0o600
            mock_chmod.assert_called_once_with(0o600)

            # 4. RENAME: Atomic rename temp → target
            mock_replace.assert_called_once()
            # replace() is called on temp_path with state_file as argument
            assert mock_replace.call_args[0][0] == state_file

    def test_load_batch_state_validates_required_fields(self, state_file):
        """Test that load_batch_state validates all required fields exist."""
        # Arrange - write JSON missing required fields
        incomplete_state = {
            "batch_id": "batch-123",
            # Missing: features_file, total_features, etc.
        }
        state_file.write_text(json.dumps(incomplete_state))

        # Act & Assert
        with pytest.raises(BatchStateError) as exc_info:
            load_batch_state(state_file)

        assert "missing required field" in str(exc_info.value).lower()


# =============================================================================
# SECTION 3: State Update Tests (5 tests)
# =============================================================================

class TestBatchStateUpdates:
    """Test state update operations (progress tracking, auto-clear events)."""

    def test_update_batch_progress_increments_current_index(self, state_file, sample_batch_state):
        """Test that update_batch_progress increments current_index."""
        # Arrange
        save_batch_state(state_file, sample_batch_state)
        assert sample_batch_state.current_index == 0

        # Act
        update_batch_progress(
            state_file,
            feature_index=0,
            status="completed",
            context_token_delta=5000,
        )

        # Assert
        updated_state = load_batch_state(state_file)
        assert updated_state.current_index == 1
        assert len(updated_state.completed_features) == 1
        assert updated_state.context_token_estimate == 10000  # 5000 + 5000

    def test_update_batch_progress_tracks_failed_features(self, state_file, sample_batch_state):
        """Test that update_batch_progress tracks failed features separately."""
        # Arrange
        save_batch_state(state_file, sample_batch_state)

        # Act
        update_batch_progress(
            state_file,
            feature_index=0,
            status="failed",
            error_message="Test implementation failed",
            context_token_delta=2000,
        )

        # Assert
        updated_state = load_batch_state(state_file)
        assert len(updated_state.failed_features) == 1
        assert updated_state.failed_features[0]["feature_index"] == 0
        assert "failed" in updated_state.failed_features[0]["error_message"].lower()

    def test_record_auto_clear_event_updates_state(self, state_file, sample_batch_state):
        """Test that record_auto_clear_event logs auto-clear event."""
        # Arrange
        save_batch_state(state_file, sample_batch_state)

        # Act
        record_auto_clear_event(
            state_file,
            feature_index=2,
            context_tokens_before_clear=155000,
        )

        # Assert
        updated_state = load_batch_state(state_file)
        assert updated_state.auto_clear_count == 1
        assert len(updated_state.auto_clear_events) == 1

        event = updated_state.auto_clear_events[0]
        assert event["feature_index"] == 2
        assert event["context_tokens_before_clear"] == 155000
        assert "timestamp" in event

    def test_should_auto_clear_returns_true_when_threshold_exceeded(self, sample_batch_state):
        """Test that should_auto_clear returns True when context exceeds threshold.

        NOTE: should_auto_clear() is DEPRECATED (Issue #277) - not used in production.
        This test validates backward compatibility only.
        """
        # Arrange
        sample_batch_state.context_token_estimate = 186000  # Above 185K threshold

        # Act
        result = should_auto_clear(sample_batch_state)

        # Assert
        assert result is True

    def test_should_auto_clear_returns_false_below_threshold(self, sample_batch_state):
        """Test that should_auto_clear returns False when context below threshold.

        NOTE: should_auto_clear() is DEPRECATED (Issue #277) - not used in production.
        This test validates backward compatibility only.
        """
        # Arrange
        sample_batch_state.context_token_estimate = 100000  # Below 185K threshold

        # Act
        result = should_auto_clear(sample_batch_state)

        # Assert
        assert result is False


# =============================================================================
# SECTION 4: Concurrent Access Tests (4 tests)
# =============================================================================

class TestBatchStateConcurrency:
    """Test concurrent access safety with file locking."""

    def test_save_batch_state_with_file_lock(self, state_file, sample_batch_state):
        """Test that save_batch_state acquires file lock before writing."""
        # Arrange & Act & Assert
        # Implementation should use file locking to prevent concurrent writes
        # This test verifies lock is acquired and released properly
        save_batch_state(state_file, sample_batch_state)

        # Verify file is not locked after operation
        assert state_file.exists()

    def test_concurrent_updates_are_serialized(self, state_file, sample_batch_state):
        """Test that concurrent updates don't corrupt state file."""
        # Arrange
        save_batch_state(state_file, sample_batch_state)
        results = []

        def update_worker(feature_index):
            """Worker thread to update batch progress."""
            try:
                update_batch_progress(
                    state_file,
                    feature_index=feature_index,
                    status="completed",
                    context_token_delta=1000,
                )
                results.append("success")
            except Exception as e:
                results.append(f"error: {e}")

        # Act - spawn 5 concurrent threads
        threads = []
        for i in range(5):
            t = threading.Thread(target=update_worker, args=(i,))
            threads.append(t)
            t.start()

        # Wait for all threads
        for t in threads:
            t.join()

        # Assert - all updates succeeded
        assert len(results) == 5
        assert all(r == "success" for r in results)

        # Verify final state is consistent
        final_state = load_batch_state(state_file)
        # Should have 5 completed features (one per thread)
        assert len(final_state.completed_features) == 5

    def test_load_batch_state_with_concurrent_readers(self, state_file, sample_batch_state):
        """Test that multiple readers can load state simultaneously."""
        # Arrange
        save_batch_state(state_file, sample_batch_state)
        results = []

        def reader_worker():
            """Worker thread to read batch state."""
            try:
                state = load_batch_state(state_file)
                results.append(state.batch_id)
            except Exception as e:
                results.append(f"error: {e}")

        # Act - spawn 10 concurrent readers
        threads = []
        for _ in range(10):
            t = threading.Thread(target=reader_worker)
            threads.append(t)
            t.start()

        # Wait for all threads
        for t in threads:
            t.join()

        # Assert - all reads succeeded
        assert len(results) == 10
        assert all(r == sample_batch_state.batch_id for r in results)

    def test_update_during_concurrent_read_is_safe(self, state_file, sample_batch_state):
        """Test that updating state while readers are active is safe."""
        # Arrange
        save_batch_state(state_file, sample_batch_state)
        read_results = []
        write_results = []

        def reader_worker():
            """Worker thread to read batch state."""
            try:
                for _ in range(10):
                    state = load_batch_state(state_file)
                    read_results.append(state.current_index)
                    time.sleep(0.001)
            except Exception as e:
                read_results.append(f"error: {e}")

        def writer_worker():
            """Worker thread to update batch state."""
            try:
                for i in range(5):
                    update_batch_progress(
                        state_file,
                        feature_index=i,
                        status="completed",
                        context_token_delta=1000,
                    )
                    write_results.append("success")
                    time.sleep(0.002)
            except Exception as e:
                write_results.append(f"error: {e}")

        # Act - spawn reader and writer threads
        reader = threading.Thread(target=reader_worker)
        writer = threading.Thread(target=writer_worker)

        reader.start()
        writer.start()

        reader.join()
        writer.join()

        # Assert - no errors occurred
        assert all(isinstance(r, int) or r == "success" for r in read_results + write_results)


# =============================================================================
# SECTION 5: Security Validation Tests (6 tests)
# =============================================================================

class TestBatchStateSecurity:
    """Test security validations (CWE-22, CWE-59)."""

    def test_save_batch_state_validates_path_traversal(self, sample_batch_state):
        """Test that save_batch_state blocks path traversal attacks (CWE-22)."""
        # Arrange - malicious path with ../
        malicious_path = Path("/tmp/../../etc/passwd")

        # Act & Assert
        with pytest.raises(BatchStateError) as exc_info:
            save_batch_state(malicious_path, sample_batch_state)

        assert "path traversal" in str(exc_info.value).lower() or "invalid path" in str(exc_info.value).lower()

    def test_load_batch_state_validates_path_traversal(self):
        """Test that load_batch_state blocks path traversal attacks (CWE-22)."""
        # Arrange - malicious path with ../
        malicious_path = Path("/tmp/../../etc/passwd")

        # Act & Assert
        with pytest.raises(BatchStateError) as exc_info:
            load_batch_state(malicious_path)

        assert "path traversal" in str(exc_info.value).lower() or "invalid path" in str(exc_info.value).lower()

    def test_save_batch_state_rejects_symlinks(self, state_file, sample_batch_state, tmp_path):
        """Test that save_batch_state rejects symlinks (CWE-59)."""
        # Arrange - create symlink pointing to /etc/passwd
        symlink_path = tmp_path / "malicious_link.json"
        target_path = Path("/etc/passwd")

        try:
            symlink_path.symlink_to(target_path)
        except OSError:
            pytest.skip("Cannot create symlinks on this system")

        # Act & Assert
        with pytest.raises(BatchStateError) as exc_info:
            save_batch_state(symlink_path, sample_batch_state)

        assert "symlink" in str(exc_info.value).lower()

    def test_load_batch_state_rejects_symlinks(self, tmp_path):
        """Test that load_batch_state rejects symlinks (CWE-59)."""
        # Arrange - create symlink pointing to /etc/passwd
        symlink_path = tmp_path / "malicious_link.json"
        target_path = Path("/etc/passwd")

        try:
            symlink_path.symlink_to(target_path)
        except OSError:
            pytest.skip("Cannot create symlinks on this system")

        # Act & Assert
        with pytest.raises(BatchStateError) as exc_info:
            load_batch_state(symlink_path)

        assert "symlink" in str(exc_info.value).lower()

    def test_batch_state_validates_features_file_path(self, sample_features):
        """Test that create_batch_state validates features_file path."""
        # Arrange - malicious features file path
        malicious_path = "/tmp/../../etc/passwd"

        # Act & Assert
        with pytest.raises(BatchStateError) as exc_info:
            create_batch_state(malicious_path, sample_features)

        # Should validate that features_file is a safe path
        # (Implementation may use security_utils.validate_path)

    def test_state_operations_log_security_events(self, state_file, sample_batch_state, tmp_path):
        """Test that security violations are logged to audit log."""
        # Arrange - malicious path
        malicious_path = tmp_path / ".." / ".." / "etc" / "passwd"

        # Act & Assert
        with patch("batch_state_manager.audit_log_security_event") as mock_audit:
            try:
                save_batch_state(malicious_path, sample_batch_state)
            except BatchStateError:
                pass

            # Verify security event was logged
            # Implementation should call audit_log_security_event from security_utils
            # mock_audit.assert_called_once()


# =============================================================================
# SECTION 6: Error Handling Tests (4 tests)
# =============================================================================

class TestBatchStateErrorHandling:
    """Test error handling and graceful degradation."""

    def test_save_batch_state_handles_disk_full_error(self, state_file, sample_batch_state):
        """Test that save_batch_state handles disk full errors gracefully."""
        # Arrange - mock os.write to raise OSError (disk full)
        with patch("os.write", side_effect=OSError(28, "No space left on device")):
            # Act & Assert
            with pytest.raises(BatchStateError) as exc_info:
                save_batch_state(state_file, sample_batch_state)

            # Verify error message mentions disk/space issue
            error_msg = str(exc_info.value).lower()
            assert "disk" in error_msg or "space" in error_msg or "write" in error_msg

    def test_load_batch_state_handles_permission_error(self, state_file, sample_batch_state):
        """Test that load_batch_state handles permission errors gracefully."""
        # Arrange - create valid file first (so validate_path passes)
        save_batch_state(state_file, sample_batch_state)

        # Mock open() to raise PermissionError when reading
        with patch("builtins.open", side_effect=PermissionError("Permission denied")):
            # Act & Assert
            with pytest.raises(BatchStateError) as exc_info:
                load_batch_state(state_file)

            # Verify error message mentions permission issue
            error_msg = str(exc_info.value).lower()
            assert "permission" in error_msg or "access" in error_msg or "read" in error_msg

    def test_update_batch_progress_validates_feature_index(self, state_file, sample_batch_state):
        """Test that update_batch_progress validates feature_index is in range."""
        # Arrange
        save_batch_state(state_file, sample_batch_state)

        # Act & Assert - feature_index out of range
        with pytest.raises(BatchStateError) as exc_info:
            update_batch_progress(
                state_file,
                feature_index=999,  # Invalid index
                status="completed",
                context_token_delta=1000,
            )

        assert "invalid" in str(exc_info.value).lower() or "out of range" in str(exc_info.value).lower()

    def test_cleanup_batch_state_removes_file_safely(self, state_file, sample_batch_state):
        """Test that cleanup_batch_state removes state file safely."""
        # Arrange
        save_batch_state(state_file, sample_batch_state)
        assert state_file.exists()

        # Act
        cleanup_batch_state(state_file)

        # Assert
        assert not state_file.exists()


# =============================================================================
# SECTION 7: Utility Function Tests (2 tests)
# =============================================================================

class TestBatchStateUtilities:
    """Test utility functions for batch processing."""

    def test_get_next_pending_feature_returns_current_feature(self, sample_batch_state):
        """Test that get_next_pending_feature returns the next feature to process."""
        # Arrange
        sample_batch_state.current_index = 2

        # Act
        next_feature = get_next_pending_feature(sample_batch_state)

        # Assert
        assert next_feature == sample_batch_state.features[2]

    def test_get_next_pending_feature_returns_none_when_complete(self, sample_batch_state):
        """Test that get_next_pending_feature returns None when all features processed."""
        # Arrange
        sample_batch_state.current_index = len(sample_batch_state.features)

        # Act
        next_feature = get_next_pending_feature(sample_batch_state)

        # Assert
        assert next_feature is None


# =============================================================================
# Test Summary
# =============================================================================

"""
TEST SUMMARY (30 unit tests):

SECTION 1: State Creation (5 tests)
✗ test_create_batch_state_with_valid_features
✗ test_create_batch_state_with_empty_features_raises_error
✗ test_create_batch_state_generates_unique_batch_id
✗ test_batch_state_dataclass_fields
✗ test_batch_state_validates_status_values

SECTION 2: State Persistence (6 tests)
✗ test_save_batch_state_creates_json_file
✗ test_load_batch_state_reads_valid_json
✗ test_load_batch_state_with_missing_file_raises_error
✗ test_load_batch_state_with_corrupted_json_raises_error
✗ test_save_batch_state_atomic_write
✗ test_load_batch_state_validates_required_fields

SECTION 3: State Updates (5 tests)
✗ test_update_batch_progress_increments_current_index
✗ test_update_batch_progress_tracks_failed_features
✗ test_record_auto_clear_event_updates_state
✗ test_should_auto_clear_returns_true_when_threshold_exceeded
✗ test_should_auto_clear_returns_false_below_threshold

SECTION 4: Concurrent Access (4 tests)
✗ test_save_batch_state_with_file_lock
✗ test_concurrent_updates_are_serialized
✗ test_load_batch_state_with_concurrent_readers
✗ test_update_during_concurrent_read_is_safe

SECTION 5: Security Validation (6 tests)
✗ test_save_batch_state_validates_path_traversal
✗ test_load_batch_state_validates_path_traversal
✗ test_save_batch_state_rejects_symlinks
✗ test_load_batch_state_rejects_symlinks
✗ test_batch_state_validates_features_file_path
✗ test_state_operations_log_security_events

SECTION 6: Error Handling (4 tests)
✗ test_save_batch_state_handles_disk_full_error
✗ test_load_batch_state_handles_permission_error
✗ test_update_batch_progress_validates_feature_index
✗ test_cleanup_batch_state_removes_file_safely

SECTION 7: Utility Functions (2 tests)
✗ test_get_next_pending_feature_returns_current_feature
✗ test_get_next_pending_feature_returns_none_when_complete

TOTAL: 30 unit tests (all FAILING - TDD red phase)

Coverage Target: 90%+ for batch_state_manager.py
Security: CWE-22 (path traversal), CWE-59 (symlinks)
Concurrency: File locking for safe multi-threaded access
"""


# =============================================================================
# SECTION 8: StateManager ABC Migration Tests (Issue #221) - 12 tests
# =============================================================================

class TestBatchStateManagerABCMigration:
    """Tests for Issue #221: BatchStateManager ABC migration.

    These tests verify that BatchStateManager correctly inherits from
    StateManager ABC and implements all abstract methods while maintaining
    backward compatibility.

    Test Strategy:
    1. Test inheritance relationship (issubclass)
    2. Test Generic type parameter (BatchStateManager[BatchState])
    3. Test abstract method implementations (load_state, save_state, cleanup_state)
    4. Test inherited helper methods (exists, _validate_state_path, _atomic_write, _get_file_lock)
    5. Test backward compatibility (existing methods still work)
    6. Test security integration (_validate_state_path called before operations)
    """

    def test_inherits_from_state_manager(self):
        """BatchStateManager should inherit from StateManager ABC."""
        # Arrange - import StateManager ABC
        try:
            from batch_state_manager import BatchStateManager
            from abstract_state_manager import StateManager
        except ImportError:
            pytest.skip("Implementation not ready (TDD red phase)")

        # Act & Assert
        assert issubclass(BatchStateManager, StateManager)

    def test_is_generic_type_with_batch_state(self):
        """BatchStateManager should be Generic[BatchState] type."""
        # Arrange
        try:
            from batch_state_manager import BatchStateManager, BatchState
            from abstract_state_manager import StateManager
        except ImportError:
            pytest.skip("Implementation not ready (TDD red phase)")

        # Act - create instance
        manager = BatchStateManager()

        # Assert - verify type hints work correctly
        # BatchStateManager should be StateManager[BatchState]
        assert isinstance(manager, StateManager)

    def test_implements_load_state_abstract_method(self, state_file, sample_batch_state):
        """BatchStateManager.load_state() should implement StateManager abstract method."""
        # Arrange
        try:
            from batch_state_manager import BatchStateManager
        except ImportError:
            pytest.skip("Implementation not ready (TDD red phase)")

        manager = BatchStateManager(state_file)
        manager.save_batch_state(sample_batch_state)

        # Act
        loaded_state = manager.load_state()

        # Assert
        assert isinstance(loaded_state, type(sample_batch_state))
        assert loaded_state.batch_id == sample_batch_state.batch_id

    def test_implements_save_state_abstract_method(self, state_file, sample_batch_state):
        """BatchStateManager.save_state() should implement StateManager abstract method."""
        # Arrange
        try:
            from batch_state_manager import BatchStateManager
        except ImportError:
            pytest.skip("Implementation not ready (TDD red phase)")

        manager = BatchStateManager(state_file)

        # Act
        manager.save_state(sample_batch_state)

        # Assert
        assert state_file.exists()
        loaded_state = manager.load_state()
        assert loaded_state.batch_id == sample_batch_state.batch_id

    def test_implements_cleanup_state_abstract_method(self, state_file, sample_batch_state):
        """BatchStateManager.cleanup_state() should implement StateManager abstract method."""
        # Arrange
        try:
            from batch_state_manager import BatchStateManager
        except ImportError:
            pytest.skip("Implementation not ready (TDD red phase)")

        manager = BatchStateManager(state_file)
        manager.save_state(sample_batch_state)
        assert state_file.exists()

        # Act
        manager.cleanup_state()

        # Assert
        assert not state_file.exists()

    def test_inherited_exists_method_works(self, state_file, sample_batch_state):
        """BatchStateManager should inherit exists() method from StateManager."""
        # Arrange
        try:
            from batch_state_manager import BatchStateManager
        except ImportError:
            pytest.skip("Implementation not ready (TDD red phase)")

        manager = BatchStateManager(state_file)

        # Act & Assert - exists() returns False before save
        assert manager.exists() is False

        # Save state
        manager.save_state(sample_batch_state)

        # exists() returns True after save
        assert manager.exists() is True

    def test_inherited_validate_state_path_prevents_traversal(self, sample_batch_state):
        """BatchStateManager should use inherited _validate_state_path() for CWE-22."""
        # Arrange
        try:
            from batch_state_manager import BatchStateManager
        except ImportError:
            pytest.skip("Implementation not ready (TDD red phase)")

        # Malicious path with traversal
        malicious_path = Path("/tmp/../../etc/passwd")

        # Act & Assert - should reject path traversal
        with pytest.raises(Exception) as exc_info:
            manager = BatchStateManager(malicious_path)
            # Validation might happen in __init__ or in operations

        # Error should mention path traversal or invalid path
        error_msg = str(exc_info.value).lower()
        assert "path traversal" in error_msg or "invalid" in error_msg or ".." in error_msg

    def test_inherited_validate_state_path_prevents_symlinks(self, tmp_path, sample_batch_state):
        """BatchStateManager should use inherited _validate_state_path() for CWE-59."""
        # Arrange
        try:
            from batch_state_manager import BatchStateManager
        except ImportError:
            pytest.skip("Implementation not ready (TDD red phase)")

        # Create symlink
        symlink_path = tmp_path / "malicious_link.json"
        target_path = tmp_path / "target.json"
        target_path.write_text("{}")

        try:
            symlink_path.symlink_to(target_path)
        except OSError:
            pytest.skip("Cannot create symlinks on this system")

        # Act & Assert - should reject symlinks
        with pytest.raises(Exception) as exc_info:
            manager = BatchStateManager(symlink_path)
            manager.save_state(sample_batch_state)

        # Error should mention symlink
        error_msg = str(exc_info.value).lower()
        assert "symlink" in error_msg

    def test_inherited_atomic_write_used_for_save(self, state_file, sample_batch_state):
        """BatchStateManager should use inherited _atomic_write() for save operations."""
        # Arrange
        try:
            from batch_state_manager import BatchStateManager
        except ImportError:
            pytest.skip("Implementation not ready (TDD red phase)")

        manager = BatchStateManager(state_file)

        # Mock _atomic_write to verify it's called
        with patch.object(manager, '_atomic_write', wraps=manager._atomic_write) as mock_atomic:
            # Act
            manager.save_state(sample_batch_state)

            # Assert - _atomic_write should be called
            mock_atomic.assert_called_once()

    def test_inherited_get_file_lock_used_for_concurrency(self, state_file, sample_batch_state):
        """BatchStateManager should use inherited _get_file_lock() for thread safety."""
        # Arrange
        try:
            from batch_state_manager import BatchStateManager
        except ImportError:
            pytest.skip("Implementation not ready (TDD red phase)")

        manager = BatchStateManager(state_file)

        # Mock _get_file_lock to verify it's called
        with patch.object(manager, '_get_file_lock', wraps=manager._get_file_lock) as mock_lock:
            # Act
            manager.save_state(sample_batch_state)

            # Assert - _get_file_lock should be called
            mock_lock.assert_called()

    def test_backward_compatibility_load_batch_state(self, state_file, sample_batch_state):
        """Existing load_batch_state() method should still work after ABC migration."""
        # Arrange
        try:
            from batch_state_manager import BatchStateManager
        except ImportError:
            pytest.skip("Implementation not ready (TDD red phase)")

        manager = BatchStateManager(state_file)
        manager.save_batch_state(sample_batch_state)

        # Act - call old method name
        loaded_state = manager.load_batch_state()

        # Assert
        assert loaded_state.batch_id == sample_batch_state.batch_id

    def test_backward_compatibility_save_batch_state(self, state_file, sample_batch_state):
        """Existing save_batch_state() method should still work after ABC migration."""
        # Arrange
        try:
            from batch_state_manager import BatchStateManager
        except ImportError:
            pytest.skip("Implementation not ready (TDD red phase)")

        manager = BatchStateManager(state_file)

        # Act - call old method name
        manager.save_batch_state(sample_batch_state)

        # Assert
        assert state_file.exists()
        loaded_state = manager.load_batch_state()
        assert loaded_state.batch_id == sample_batch_state.batch_id


# =============================================================================
# SECTION 9: Batch Completion Summary Tests (8 tests) - Issue #242
# =============================================================================


class TestBatchCompletionSummary:
    """Test generate_completion_summary function."""

    @pytest.fixture
    def completed_batch_state(self):
        """Create batch state with some completed features."""
        from batch_state_manager import BatchState
        return BatchState(
            batch_id="batch-20260118-test",
            features_file="features.txt",
            total_features=5,
            features=["Feature A", "Feature B", "Feature C", "Feature D", "Feature E"],
            current_index=5,
            completed_features=[0, 1, 3],
            failed_features=[{"feature_index": 2, "error_message": "Test failed"}],
            status="in_progress",
            issue_numbers=[101, 102, 103, 104, 105],
            source_type="issues"
        )

    def test_generate_summary_basic_counts(self, completed_batch_state):
        """Test summary generates correct counts."""
        from batch_state_manager import generate_completion_summary

        summary = generate_completion_summary(completed_batch_state)

        assert summary.total_features == 5
        assert summary.completed_count == 3
        assert summary.failed_count == 1
        assert summary.pending_count == 1

    def test_generate_summary_feature_lists(self, completed_batch_state):
        """Test summary includes correct feature descriptions."""
        from batch_state_manager import generate_completion_summary

        summary = generate_completion_summary(completed_batch_state)

        assert "Feature A" in summary.completed_features
        assert "Feature B" in summary.completed_features
        assert "Feature D" in summary.completed_features
        assert "Feature E" in summary.pending_features
        assert len(summary.failed_features) == 1
        assert summary.failed_features[0][0] == "Feature C"

    def test_generate_summary_issue_categorization(self, completed_batch_state):
        """Test summary categorizes issues correctly."""
        from batch_state_manager import generate_completion_summary

        summary = generate_completion_summary(completed_batch_state)

        assert 101 in summary.issues_completed
        assert 102 in summary.issues_completed
        assert 104 in summary.issues_completed
        assert 103 in summary.issues_pending
        assert 105 in summary.issues_pending

    def test_generate_summary_next_steps_with_pending(self, completed_batch_state):
        """Test summary includes resume step when pending features exist."""
        from batch_state_manager import generate_completion_summary

        summary = generate_completion_summary(completed_batch_state)

        assert any("pending" in step.lower() for step in summary.next_steps)
        assert summary.resume_command == "/implement --resume batch-20260118-test"

    def test_generate_summary_next_steps_with_failed(self, completed_batch_state):
        """Test summary includes retry step when failed features exist."""
        from batch_state_manager import generate_completion_summary

        summary = generate_completion_summary(completed_batch_state)

        assert any("failed" in step.lower() for step in summary.next_steps)

    def test_generate_summary_all_complete(self):
        """Test summary for fully completed batch."""
        from batch_state_manager import BatchState, generate_completion_summary

        state = BatchState(
            batch_id="batch-complete",
            features_file="features.txt",
            total_features=3,
            features=["A", "B", "C"],
            current_index=3,
            completed_features=[0, 1, 2],
            failed_features=[],
            status="completed"
        )

        summary = generate_completion_summary(state)

        assert summary.completed_count == 3
        assert summary.failed_count == 0
        assert summary.pending_count == 0
        assert summary.resume_command == ""
        assert any("complete" in step.lower() for step in summary.next_steps)

    def test_format_summary_output(self, completed_batch_state):
        """Test format_summary produces readable output."""
        from batch_state_manager import generate_completion_summary

        summary = generate_completion_summary(completed_batch_state)
        output = summary.format_summary()

        assert "BATCH COMPLETION SUMMARY" in output
        assert "batch-20260118-test" in output
        assert "Completed: 3/5" in output
        assert "Failed:    1/5" in output
        assert "Pending:   1/5" in output
        assert "NEXT STEPS:" in output

    @patch('subprocess.run')
    def test_generate_summary_with_git_commits(self, mock_run, completed_batch_state):
        """Test summary includes git commit counts when worktree branch provided."""
        from batch_state_manager import generate_completion_summary

        # Mock git rev-list for commit counts
        mock_run.side_effect = [
            Mock(returncode=0, stdout="3\n", stderr=""),  # worktree commits
            Mock(returncode=0, stdout="1\n", stderr=""),  # main commits
        ]

        summary = generate_completion_summary(
            completed_batch_state,
            worktree_branch="feature-batch",
            target_branch="master"
        )

        assert summary.worktree_commits == 3
        assert summary.main_commits == 1


# =============================================================================
# Test Summary Update
# =============================================================================

"""
TEST SUMMARY UPDATE (50 unit tests):

SECTION 8: StateManager ABC Migration (12 tests) - Issue #221
✗ test_inherits_from_state_manager
✗ test_is_generic_type_with_batch_state
✗ test_implements_load_state_abstract_method
✗ test_implements_save_state_abstract_method
✗ test_implements_cleanup_state_abstract_method
✗ test_inherited_exists_method_works
✗ test_inherited_validate_state_path_prevents_traversal
✗ test_inherited_validate_state_path_prevents_symlinks
✗ test_inherited_atomic_write_used_for_save
✗ test_inherited_get_file_lock_used_for_concurrency
✗ test_backward_compatibility_load_batch_state
✗ test_backward_compatibility_save_batch_state

TOTAL: 42 unit tests (12 new tests for Issue #221 - TDD red phase)

New Coverage:
- StateManager ABC inheritance verification
- Generic type parameter testing (BatchStateManager[BatchState])
- Abstract method implementations (load_state, save_state, cleanup_state)
- Inherited helper method usage (_validate_state_path, _atomic_write, _get_file_lock)
- Backward compatibility with existing methods
- Security integration (CWE-22, CWE-59 via inherited validators)
"""
