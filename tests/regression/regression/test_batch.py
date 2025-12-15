#!/usr/bin/env python3
"""
Consolidated Batch Processing Tests (TDD Red Phase)

Tests for batch processing features (Issues #76, #89):
- State management (BatchState, persistence)
- Retry logic (per-feature, circuit breaker)
- Progress tracking
- Concurrent access safety

Date: 2025-11-16 (consolidated 2025-12-16)
Issues: #76 (State-based Auto-Clearing), #89 (Automatic Failure Recovery)
"""

import json
import sys
import pytest
import time
import threading
from dataclasses import asdict
from pathlib import Path
from unittest.mock import patch

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

# Import batch_state_manager - skip if not available
try:
    from batch_state_manager import (
        BatchState, create_batch_state, load_batch_state, save_batch_state,
        update_batch_progress, record_auto_clear_event, should_auto_clear,
        cleanup_batch_state, get_next_pending_feature, BatchStateError,
        DEFAULT_STATE_FILE, CONTEXT_THRESHOLD,
    )
    STATE_MANAGER_AVAILABLE = True
except ImportError:
    STATE_MANAGER_AVAILABLE = False

# Import batch_retry_manager - skip if not available
try:
    from batch_retry_manager import (
        BatchRetryManager, should_retry_feature, record_retry_attempt,
        check_circuit_breaker, get_retry_count, reset_circuit_breaker,
        MAX_RETRIES_PER_FEATURE, MAX_TOTAL_RETRIES, CIRCUIT_BREAKER_THRESHOLD,
        RetryDecision, CircuitBreakerError,
    )
    from failure_classifier import FailureType
    RETRY_MANAGER_AVAILABLE = True
except ImportError:
    RETRY_MANAGER_AVAILABLE = False


# =============================================================================
# Fixtures
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
# State Creation Tests
# =============================================================================

@pytest.mark.skipif(not STATE_MANAGER_AVAILABLE, reason="batch_state_manager not available")
class TestBatchStateCreation:
    """Test BatchState dataclass creation and validation."""

    def test_create_batch_state_with_valid_features(self, sample_features):
        """Test creating BatchState with valid feature list."""
        state = create_batch_state("/path/to/features.txt", sample_features)
        assert state.total_features == len(sample_features)
        assert state.features == sample_features
        assert state.current_index == 0
        assert state.status == "in_progress"
        assert state.batch_id.startswith("batch-")

    def test_create_batch_state_with_empty_features_raises_error(self):
        """Test that creating BatchState with empty feature list raises error."""
        with pytest.raises(BatchStateError) as exc_info:
            create_batch_state("/path/to/features.txt", [])
        assert "no features" in str(exc_info.value).lower()

    def test_batch_state_dataclass_fields(self, sample_batch_state):
        """Test that BatchState has all required fields."""
        state_dict = asdict(sample_batch_state)
        required_fields = [
            "batch_id", "features_file", "total_features", "features",
            "current_index", "completed_features", "failed_features",
            "context_token_estimate", "auto_clear_count", "auto_clear_events",
            "created_at", "updated_at", "status",
        ]
        for field in required_fields:
            assert field in state_dict


# =============================================================================
# State Persistence Tests
# =============================================================================

@pytest.mark.skipif(not STATE_MANAGER_AVAILABLE, reason="batch_state_manager not available")
class TestBatchStatePersistence:
    """Test state save/load operations with JSON."""

    def test_save_batch_state_creates_json_file(self, state_file, sample_batch_state):
        """Test that save_batch_state creates valid JSON file."""
        assert not state_file.exists()
        save_batch_state(state_file, sample_batch_state)
        assert state_file.exists()
        data = json.loads(state_file.read_text())
        assert data["batch_id"] == sample_batch_state.batch_id

    def test_load_batch_state_reads_valid_json(self, state_file, sample_batch_state):
        """Test that load_batch_state reads and deserializes JSON correctly."""
        save_batch_state(state_file, sample_batch_state)
        loaded_state = load_batch_state(state_file)
        assert loaded_state.batch_id == sample_batch_state.batch_id
        assert loaded_state.total_features == sample_batch_state.total_features

    def test_load_batch_state_with_missing_file_raises_error(self, state_file):
        """Test that load_batch_state raises error when file doesn't exist."""
        with pytest.raises(BatchStateError) as exc_info:
            load_batch_state(state_file)
        assert "not found" in str(exc_info.value).lower()

    def test_load_batch_state_with_corrupted_json_raises_error(self, state_file):
        """Test that load_batch_state raises error with corrupted JSON."""
        state_file.write_text("{invalid json content")
        with pytest.raises(BatchStateError):
            load_batch_state(state_file)


# =============================================================================
# State Update Tests
# =============================================================================

@pytest.mark.skipif(not STATE_MANAGER_AVAILABLE, reason="batch_state_manager not available")
class TestBatchStateUpdates:
    """Test state update operations."""

    def test_update_batch_progress_increments_current_index(self, state_file, sample_batch_state):
        """Test that update_batch_progress increments current_index."""
        save_batch_state(state_file, sample_batch_state)
        update_batch_progress(state_file, feature_index=0, status="completed", context_token_delta=5000)
        updated_state = load_batch_state(state_file)
        assert updated_state.current_index == 1
        assert len(updated_state.completed_features) == 1

    def test_update_batch_progress_tracks_failed_features(self, state_file, sample_batch_state):
        """Test that update_batch_progress tracks failed features."""
        save_batch_state(state_file, sample_batch_state)
        update_batch_progress(state_file, feature_index=0, status="failed", error_message="Test failed", context_token_delta=2000)
        updated_state = load_batch_state(state_file)
        assert len(updated_state.failed_features) == 1

    def test_should_auto_clear_returns_true_when_threshold_exceeded(self, sample_batch_state):
        """Test that should_auto_clear returns True when context exceeds threshold."""
        sample_batch_state.context_token_estimate = 160000
        assert should_auto_clear(sample_batch_state) is True

    def test_should_auto_clear_returns_false_below_threshold(self, sample_batch_state):
        """Test that should_auto_clear returns False when context below threshold."""
        sample_batch_state.context_token_estimate = 100000
        assert should_auto_clear(sample_batch_state) is False


# =============================================================================
# Concurrent Access Tests
# =============================================================================

@pytest.mark.skipif(not STATE_MANAGER_AVAILABLE, reason="batch_state_manager not available")
class TestBatchStateConcurrency:
    """Test concurrent access safety."""

    def test_concurrent_updates_are_serialized(self, state_file, sample_batch_state):
        """Test that concurrent updates don't corrupt state file."""
        save_batch_state(state_file, sample_batch_state)
        results = []

        def update_worker(feature_index):
            try:
                update_batch_progress(state_file, feature_index=feature_index, status="completed", context_token_delta=1000)
                results.append("success")
            except Exception as e:
                results.append(f"error: {e}")

        threads = [threading.Thread(target=update_worker, args=(i,)) for i in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(results) == 5
        assert all(r == "success" for r in results)
        final_state = load_batch_state(state_file)
        assert len(final_state.completed_features) == 5


# =============================================================================
# Security Tests
# =============================================================================

@pytest.mark.skipif(not STATE_MANAGER_AVAILABLE, reason="batch_state_manager not available")
class TestBatchStateSecurity:
    """Test security validations (CWE-22, CWE-59)."""

    def test_save_batch_state_validates_path_traversal(self, sample_batch_state):
        """Test that save_batch_state blocks path traversal attacks."""
        malicious_path = Path("/tmp/../../etc/passwd")
        with pytest.raises(BatchStateError):
            save_batch_state(malicious_path, sample_batch_state)

    def test_load_batch_state_validates_path_traversal(self):
        """Test that load_batch_state blocks path traversal attacks."""
        malicious_path = Path("/tmp/../../etc/passwd")
        with pytest.raises(BatchStateError):
            load_batch_state(malicious_path)

    def test_save_batch_state_rejects_symlinks(self, sample_batch_state, tmp_path):
        """Test that save_batch_state rejects symlinks."""
        symlink_path = tmp_path / "malicious_link.json"
        try:
            symlink_path.symlink_to(Path("/etc/passwd"))
        except OSError:
            pytest.skip("Cannot create symlinks on this system")

        with pytest.raises(BatchStateError):
            save_batch_state(symlink_path, sample_batch_state)


# =============================================================================
# Retry Manager Tests
# =============================================================================

@pytest.mark.skipif(not RETRY_MANAGER_AVAILABLE, reason="batch_retry_manager not available")
class TestRetryCountTracking:
    """Test retry count tracking per feature."""

    @pytest.fixture
    def retry_manager(self, temp_state_dir):
        return BatchRetryManager("batch-20251118-123456", state_dir=temp_state_dir)

    def test_get_retry_count_returns_zero_initially(self, retry_manager):
        """Test that retry count starts at 0 for new feature."""
        assert retry_manager.get_retry_count(0) == 0

    def test_record_retry_attempt_increments_count(self, retry_manager):
        """Test that recording retry increments count."""
        retry_manager.record_retry_attempt(0, "ConnectionError: Failed")
        assert retry_manager.get_retry_count(0) == 1

    def test_retry_count_tracked_independently_per_feature(self, retry_manager):
        """Test that retry counts are tracked separately per feature."""
        retry_manager.record_retry_attempt(0, "Error")
        retry_manager.record_retry_attempt(0, "Error")
        retry_manager.record_retry_attempt(1, "Error")
        assert retry_manager.get_retry_count(0) == 2
        assert retry_manager.get_retry_count(1) == 1


@pytest.mark.skipif(not RETRY_MANAGER_AVAILABLE, reason="batch_retry_manager not available")
class TestCircuitBreaker:
    """Test circuit breaker after 5 consecutive failures."""

    @pytest.fixture
    def retry_manager(self, temp_state_dir):
        return BatchRetryManager("batch-20251118-123456", state_dir=temp_state_dir)

    def test_circuit_breaker_not_triggered_with_few_failures(self, retry_manager):
        """Test that circuit breaker doesn't trigger with < 5 failures."""
        for i in range(4):
            retry_manager.record_retry_attempt(i, "Error")
        assert retry_manager.check_circuit_breaker() is False

    def test_circuit_breaker_triggers_after_five_consecutive_failures(self, retry_manager):
        """Test that circuit breaker triggers after 5 consecutive failures."""
        for i in range(5):
            retry_manager.record_retry_attempt(i, "Error")
        assert retry_manager.check_circuit_breaker() is True

    def test_circuit_breaker_threshold_is_five(self):
        """Test that CIRCUIT_BREAKER_THRESHOLD is set to 5."""
        assert CIRCUIT_BREAKER_THRESHOLD == 5


@pytest.mark.skipif(not RETRY_MANAGER_AVAILABLE, reason="batch_retry_manager not available")
class TestMaxRetryLimit:
    """Test max retry limit enforcement."""

    @pytest.fixture
    def retry_manager(self, temp_state_dir):
        return BatchRetryManager("batch-20251118-123456", state_dir=temp_state_dir)

    def test_should_retry_returns_true_under_limit(self, retry_manager):
        """Test that retry is allowed when under max limit."""
        retry_manager.record_retry_attempt(0, "Error 1")
        retry_manager.record_retry_attempt(0, "Error 2")
        decision = retry_manager.should_retry_feature(0, FailureType.TRANSIENT)
        assert decision.should_retry is True

    def test_should_retry_returns_false_at_limit(self, retry_manager):
        """Test that retry is blocked when at max limit."""
        for i in range(MAX_RETRIES_PER_FEATURE):
            retry_manager.record_retry_attempt(0, f"Error {i}")
        decision = retry_manager.should_retry_feature(0, FailureType.TRANSIENT)
        assert decision.should_retry is False

    def test_max_retries_per_feature_constant_is_three(self):
        """Test that MAX_RETRIES_PER_FEATURE is set to 3."""
        assert MAX_RETRIES_PER_FEATURE == 3


# =============================================================================
# Utility Function Tests
# =============================================================================

@pytest.mark.skipif(not STATE_MANAGER_AVAILABLE, reason="batch_state_manager not available")
class TestBatchStateUtilities:
    """Test utility functions for batch processing."""

    def test_get_next_pending_feature_returns_current_feature(self, sample_batch_state):
        """Test that get_next_pending_feature returns the next feature."""
        sample_batch_state.current_index = 2
        next_feature = get_next_pending_feature(sample_batch_state)
        assert next_feature == sample_batch_state.features[2]

    def test_get_next_pending_feature_returns_none_when_complete(self, sample_batch_state):
        """Test that get_next_pending_feature returns None when done."""
        sample_batch_state.current_index = len(sample_batch_state.features)
        assert get_next_pending_feature(sample_batch_state) is None

    def test_cleanup_batch_state_removes_file_safely(self, state_file, sample_batch_state):
        """Test that cleanup_batch_state removes state file."""
        save_batch_state(state_file, sample_batch_state)
        cleanup_batch_state(state_file)
        assert not state_file.exists()


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=line", "-q"])
