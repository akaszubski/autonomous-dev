#!/usr/bin/env python3
"""
Unit tests for batch_retry_manager module (TDD Red Phase - Issue #89).

Tests for orchestrating retry logic in /batch-implement workflows.

TDD Mode: These tests are written BEFORE implementation.
All tests should FAIL initially (ImportError: module not found).

Test Strategy:
- Test retry count tracking per feature
- Test max retry limit enforcement (3 retries)
- Test circuit breaker (5 consecutive failures)
- Test global retry limit across batch
- Test transient vs permanent failure handling
- Test retry state persistence

Security:
- Audit logging for retry attempts
- Global limits prevent resource exhaustion
- Circuit breaker prevents infinite loops

Coverage Target: 95%+ for batch_retry_manager.py

Date: 2025-11-18
Issue: #89 (Automatic Failure Recovery for /batch-implement)
Agent: test-master
Phase: TDD Red (tests written BEFORE implementation)
Status: RED (all tests failing - module doesn't exist yet)
"""

import sys
import pytest
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock

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
    from batch_retry_manager import (
        BatchRetryManager,
        should_retry_feature,
        record_retry_attempt,
        check_circuit_breaker,
        get_retry_count,
        reset_circuit_breaker,
        MAX_RETRIES_PER_FEATURE,
        MAX_TOTAL_RETRIES,
        CIRCUIT_BREAKER_THRESHOLD,
        RetryDecision,
        CircuitBreakerError,
    )
    from failure_classifier import FailureType
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
def retry_manager(temp_state_dir):
    """Create BatchRetryManager instance."""
    batch_id = "batch-20251118-123456"
    return BatchRetryManager(batch_id, state_dir=temp_state_dir)


@pytest.fixture
def sample_error():
    """Sample error message for testing."""
    return "ConnectionError: Failed to connect to API"


# =============================================================================
# SECTION 1: Retry Count Tracking Tests (4 tests)
# =============================================================================

class TestRetryCountTracking:
    """Test retry count tracking per feature."""

    def test_get_retry_count_returns_zero_initially(self, retry_manager):
        """Test that retry count starts at 0 for new feature."""
        # Arrange
        feature_index = 0

        # Act
        retry_count = retry_manager.get_retry_count(feature_index)

        # Assert
        assert retry_count == 0

    def test_record_retry_attempt_increments_count(self, retry_manager):
        """Test that recording retry increments count."""
        # Arrange
        feature_index = 0
        error_message = "ConnectionError: Failed"

        # Act
        retry_manager.record_retry_attempt(feature_index, error_message)

        # Assert
        retry_count = retry_manager.get_retry_count(feature_index)
        assert retry_count == 1

    def test_retry_count_tracked_independently_per_feature(self, retry_manager):
        """Test that retry counts are tracked separately per feature."""
        # Arrange
        feature1 = 0
        feature2 = 1
        error = "ConnectionError: Failed"

        # Act - retry feature1 twice, feature2 once
        retry_manager.record_retry_attempt(feature1, error)
        retry_manager.record_retry_attempt(feature1, error)
        retry_manager.record_retry_attempt(feature2, error)

        # Assert
        assert retry_manager.get_retry_count(feature1) == 2
        assert retry_manager.get_retry_count(feature2) == 1

    def test_retry_count_persists_across_manager_instances(self, temp_state_dir):
        """Test that retry counts persist when manager is recreated."""
        # Arrange
        batch_id = "batch-test-123"
        manager1 = BatchRetryManager(batch_id, state_dir=temp_state_dir)

        # Record retry with first manager
        manager1.record_retry_attempt(0, "ConnectionError: Failed")

        # Act - create new manager with same batch_id
        manager2 = BatchRetryManager(batch_id, state_dir=temp_state_dir)

        # Assert - retry count persisted
        assert manager2.get_retry_count(0) == 1


# =============================================================================
# SECTION 2: Max Retry Limit Tests (5 tests)
# =============================================================================

class TestMaxRetryLimit:
    """Test max retry limit enforcement (3 retries per feature)."""

    def test_should_retry_returns_true_under_limit(self, retry_manager):
        """Test that retry is allowed when under max limit."""
        # Arrange
        feature_index = 0
        failure_type = FailureType.TRANSIENT

        # Record 2 retries (under limit of 3)
        retry_manager.record_retry_attempt(feature_index, "Error 1")
        retry_manager.record_retry_attempt(feature_index, "Error 2")

        # Act
        decision = retry_manager.should_retry_feature(feature_index, failure_type)

        # Assert
        assert decision.should_retry is True
        assert decision.reason == "under_retry_limit"

    def test_should_retry_returns_false_at_limit(self, retry_manager):
        """Test that retry is blocked when at max limit."""
        # Arrange
        feature_index = 0
        failure_type = FailureType.TRANSIENT

        # Record 3 retries (at limit)
        for i in range(MAX_RETRIES_PER_FEATURE):
            retry_manager.record_retry_attempt(feature_index, f"Error {i}")

        # Act
        decision = retry_manager.should_retry_feature(feature_index, failure_type)

        # Assert
        assert decision.should_retry is False
        assert decision.reason == "max_retries_reached"

    def test_max_retries_per_feature_constant_is_three(self):
        """Test that MAX_RETRIES_PER_FEATURE is set to 3."""
        # Arrange & Act & Assert
        assert MAX_RETRIES_PER_FEATURE == 3

    def test_should_retry_rejects_permanent_failures(self, retry_manager):
        """Test that permanent failures are never retried."""
        # Arrange
        feature_index = 0
        failure_type = FailureType.PERMANENT

        # Act
        decision = retry_manager.should_retry_feature(feature_index, failure_type)

        # Assert
        assert decision.should_retry is False
        assert decision.reason == "permanent_failure"

    def test_retry_decision_includes_retry_count(self, retry_manager):
        """Test that RetryDecision includes current retry count."""
        # Arrange
        feature_index = 0
        failure_type = FailureType.TRANSIENT
        retry_manager.record_retry_attempt(feature_index, "Error 1")

        # Act
        decision = retry_manager.should_retry_feature(feature_index, failure_type)

        # Assert
        assert hasattr(decision, "retry_count")
        assert decision.retry_count == 1


# =============================================================================
# SECTION 3: Circuit Breaker Tests (6 tests)
# =============================================================================

class TestCircuitBreaker:
    """Test circuit breaker after 5 consecutive failures."""

    def test_circuit_breaker_not_triggered_with_few_failures(self, retry_manager):
        """Test that circuit breaker doesn't trigger with < 5 consecutive failures."""
        # Arrange - record 4 consecutive failures
        for i in range(4):
            retry_manager.record_retry_attempt(i, "ConnectionError")

        # Act
        is_open = retry_manager.check_circuit_breaker()

        # Assert
        assert is_open is False

    def test_circuit_breaker_triggers_after_five_consecutive_failures(self, retry_manager):
        """Test that circuit breaker triggers after 5 consecutive failures."""
        # Arrange - record 5 consecutive failures
        for i in range(5):
            retry_manager.record_retry_attempt(i, "ConnectionError")

        # Act
        is_open = retry_manager.check_circuit_breaker()

        # Assert
        assert is_open is True

    def test_circuit_breaker_resets_after_success(self, retry_manager):
        """Test that circuit breaker resets after a successful feature."""
        # Arrange - record 3 failures, then success
        for i in range(3):
            retry_manager.record_retry_attempt(i, "ConnectionError")

        # Record success
        retry_manager.record_success(3)

        # Act
        is_open = retry_manager.check_circuit_breaker()

        # Assert - consecutive failure count reset
        assert is_open is False

    def test_circuit_breaker_threshold_is_five(self):
        """Test that CIRCUIT_BREAKER_THRESHOLD is set to 5."""
        # Arrange & Act & Assert
        assert CIRCUIT_BREAKER_THRESHOLD == 5

    def test_should_retry_blocked_when_circuit_open(self, retry_manager):
        """Test that retry is blocked when circuit breaker is open."""
        # Arrange - trigger circuit breaker
        for i in range(5):
            retry_manager.record_retry_attempt(i, "ConnectionError")

        # Act
        feature_index = 5
        failure_type = FailureType.TRANSIENT
        decision = retry_manager.should_retry_feature(feature_index, failure_type)

        # Assert
        assert decision.should_retry is False
        assert decision.reason == "circuit_breaker_open"

    def test_reset_circuit_breaker_allows_retries_again(self, retry_manager):
        """Test that manually resetting circuit breaker allows retries."""
        # Arrange - trigger circuit breaker
        for i in range(5):
            retry_manager.record_retry_attempt(i, "ConnectionError")

        assert retry_manager.check_circuit_breaker() is True

        # Act - reset circuit breaker
        retry_manager.reset_circuit_breaker()

        # Assert
        assert retry_manager.check_circuit_breaker() is False


# =============================================================================
# SECTION 4: Global Retry Limit Tests (4 tests)
# =============================================================================

class TestGlobalRetryLimit:
    """Test global retry limit across entire batch."""

    def test_global_retry_count_tracks_all_retries(self, retry_manager):
        """Test that global count tracks retries across all features."""
        # Arrange & Act - retry 3 different features
        retry_manager.record_retry_attempt(0, "Error 1")
        retry_manager.record_retry_attempt(1, "Error 2")
        retry_manager.record_retry_attempt(2, "Error 3")

        # Assert
        global_count = retry_manager.get_global_retry_count()
        assert global_count == 3

    def test_should_retry_blocked_when_global_limit_reached(self, retry_manager):
        """Test that retry blocked when global limit reached."""
        # Arrange - simulate many retries across features
        for i in range(MAX_TOTAL_RETRIES):
            feature_index = i % 10  # Spread across 10 features
            retry_manager.record_retry_attempt(feature_index, f"Error {i}")

        # Act
        decision = retry_manager.should_retry_feature(0, FailureType.TRANSIENT)

        # Assert
        assert decision.should_retry is False
        assert decision.reason == "global_retry_limit_reached"

    def test_max_total_retries_is_reasonable_limit(self):
        """Test that MAX_TOTAL_RETRIES is set to reasonable value."""
        # Arrange & Act & Assert
        # Should be high enough for large batches (e.g., 50 features)
        # but low enough to prevent infinite loops
        assert MAX_TOTAL_RETRIES >= 20
        assert MAX_TOTAL_RETRIES <= 100

    def test_global_retry_limit_persists_across_instances(self, temp_state_dir):
        """Test that global retry count persists across manager instances."""
        # Arrange
        batch_id = "batch-test-123"
        manager1 = BatchRetryManager(batch_id, state_dir=temp_state_dir)

        # Record retries with first manager
        manager1.record_retry_attempt(0, "Error 1")
        manager1.record_retry_attempt(1, "Error 2")

        # Act - create new manager
        manager2 = BatchRetryManager(batch_id, state_dir=temp_state_dir)

        # Assert
        assert manager2.get_global_retry_count() == 2


# =============================================================================
# SECTION 5: Retry State Persistence Tests (4 tests)
# =============================================================================

class TestRetryStatePersistence:
    """Test retry state persistence across restarts."""

    def test_retry_state_saved_to_file(self, retry_manager, temp_state_dir):
        """Test that retry state is saved to JSON file."""
        # Arrange
        retry_manager.record_retry_attempt(0, "ConnectionError")

        # Act
        retry_state_file = temp_state_dir / f"{retry_manager.batch_id}_retry_state.json"

        # Assert
        assert retry_state_file.exists()

    def test_retry_state_loaded_from_file(self, temp_state_dir):
        """Test that retry state is loaded from existing file."""
        # Arrange - create manager and record retry
        batch_id = "batch-test-123"
        manager1 = BatchRetryManager(batch_id, state_dir=temp_state_dir)
        manager1.record_retry_attempt(0, "Error 1")
        manager1.record_retry_attempt(1, "Error 2")

        # Act - create new manager (should load from file)
        manager2 = BatchRetryManager(batch_id, state_dir=temp_state_dir)

        # Assert
        assert manager2.get_retry_count(0) == 1
        assert manager2.get_retry_count(1) == 1
        assert manager2.get_global_retry_count() == 2

    def test_retry_state_atomic_write(self, retry_manager):
        """Test that retry state uses atomic write (temp + rename)."""
        # Arrange & Act
        with patch("tempfile.mkstemp") as mock_mkstemp, \
             patch("os.write") as mock_write, \
             patch("os.close") as mock_close, \
             patch("pathlib.Path.replace") as mock_replace:

            mock_mkstemp.return_value = (999, "/tmp/.retry_state_abc.tmp")

            # Record retry (should trigger atomic write)
            retry_manager.record_retry_attempt(0, "Error")

            # Assert - atomic write pattern used
            mock_mkstemp.assert_called()
            mock_write.assert_called()
            mock_close.assert_called()
            mock_replace.assert_called()

    def test_retry_state_handles_corrupted_file(self, temp_state_dir):
        """Test that manager handles corrupted retry state file gracefully."""
        # Arrange - create corrupted state file
        batch_id = "batch-test-123"
        retry_state_file = temp_state_dir / f"{batch_id}_retry_state.json"
        retry_state_file.write_text("{invalid json")

        # Act - should start with fresh state (not crash)
        manager = BatchRetryManager(batch_id, state_dir=temp_state_dir)

        # Assert - initialized with clean state
        assert manager.get_global_retry_count() == 0


# =============================================================================
# SECTION 6: Audit Logging Tests (3 tests)
# =============================================================================

class TestAuditLogging:
    """Test audit logging for retry attempts."""

    def test_record_retry_logs_to_audit_file(self, retry_manager):
        """Test that retry attempts are logged to audit file."""
        # Arrange
        feature_index = 0
        error_message = "ConnectionError: Failed"

        # Act
        with patch("batch_retry_manager.log_audit_event") as mock_log:
            retry_manager.record_retry_attempt(feature_index, error_message)

            # Assert
            mock_log.assert_called_once()
            call_args = mock_log.call_args[0]
            assert "retry_attempt" in str(call_args).lower()

    def test_circuit_breaker_trigger_logged(self, retry_manager):
        """Test that circuit breaker trigger is logged."""
        # Arrange & Act
        with patch("batch_retry_manager.log_audit_event") as mock_log:
            # Trigger circuit breaker
            for i in range(5):
                retry_manager.record_retry_attempt(i, "Error")

            # Assert
            logged_calls = [str(call) for call in mock_log.call_args_list]
            assert any("circuit_breaker" in call.lower() for call in logged_calls)

    def test_audit_log_includes_batch_id(self, retry_manager):
        """Test that audit logs include batch_id for tracking."""
        # Arrange & Act
        with patch("batch_retry_manager.log_audit_event") as mock_log:
            retry_manager.record_retry_attempt(0, "Error")

            # Assert
            call_args = mock_log.call_args[1] if mock_log.call_args[1] else mock_log.call_args[0]
            assert retry_manager.batch_id in str(call_args)


# =============================================================================
# Test Summary
# =============================================================================

"""
TEST SUMMARY (26 unit tests for batch_retry_manager.py):

SECTION 1: Retry Count Tracking (4 tests)
✗ test_get_retry_count_returns_zero_initially
✗ test_record_retry_attempt_increments_count
✗ test_retry_count_tracked_independently_per_feature
✗ test_retry_count_persists_across_manager_instances

SECTION 2: Max Retry Limit (5 tests)
✗ test_should_retry_returns_true_under_limit
✗ test_should_retry_returns_false_at_limit
✗ test_max_retries_per_feature_constant_is_three
✗ test_should_retry_rejects_permanent_failures
✗ test_retry_decision_includes_retry_count

SECTION 3: Circuit Breaker (6 tests)
✗ test_circuit_breaker_not_triggered_with_few_failures
✗ test_circuit_breaker_triggers_after_five_consecutive_failures
✗ test_circuit_breaker_resets_after_success
✗ test_circuit_breaker_threshold_is_five
✗ test_should_retry_blocked_when_circuit_open
✗ test_reset_circuit_breaker_allows_retries_again

SECTION 4: Global Retry Limit (4 tests)
✗ test_global_retry_count_tracks_all_retries
✗ test_should_retry_blocked_when_global_limit_reached
✗ test_max_total_retries_is_reasonable_limit
✗ test_global_retry_limit_persists_across_instances

SECTION 5: Retry State Persistence (4 tests)
✗ test_retry_state_saved_to_file
✗ test_retry_state_loaded_from_file
✗ test_retry_state_atomic_write
✗ test_retry_state_handles_corrupted_file

SECTION 6: Audit Logging (3 tests)
✗ test_record_retry_logs_to_audit_file
✗ test_circuit_breaker_trigger_logged
✗ test_audit_log_includes_batch_id

TOTAL: 26 unit tests (all FAILING - TDD red phase)

Security Coverage:
- Audit logging for all retry attempts
- Global limits prevent resource exhaustion
- Circuit breaker prevents infinite retry loops
- State file validation and atomic writes

Implementation Guidance:
- Use JSON file for retry state persistence
- Track per-feature and global retry counts
- Implement circuit breaker with consecutive failure tracking
- Log all retry attempts to audit file
- Use atomic writes for state file updates
"""
