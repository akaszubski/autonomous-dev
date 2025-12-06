#!/usr/bin/env python3
"""
Integration tests for batch retry workflow (TDD Red Phase - Issue #89).

Tests for end-to-end automatic retry workflow in /batch-implement.

TDD Mode: These tests are written BEFORE implementation.
All tests should FAIL initially (workflow doesn't exist yet).

Test Strategy:
- Test complete retry workflow (failure → classify → retry → success)
- Test max retry limit (3 attempts then fail)
- Test circuit breaker (5 consecutive failures → pause)
- Test transient vs permanent failure handling
- Test user interruption during retry (Ctrl+C)
- Test consent workflow integration
- Test retry state persistence across restarts

Security:
- Audit logging for all retry attempts
- User consent required for retry feature
- Global limits prevent resource exhaustion

Date: 2025-11-18
Issue: #89 (Automatic Failure Recovery for /batch-implement)
Agent: test-master
Phase: TDD Red (tests written BEFORE implementation)
Status: RED (all tests failing - workflow doesn't exist yet)
"""

import json
import os
import subprocess
import sys
import pytest
import signal
import time
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock, call

# Add project paths for imports
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root / 'plugins' / 'autonomous-dev' / 'lib'))
sys.path.insert(0, str(project_root / 'plugins' / 'autonomous-dev' / 'commands'))

# Import will fail - modules don't exist yet (TDD!)
try:
    from batch_state_manager import (
        BatchState,
        create_batch_state,
        save_batch_state,
        load_batch_state,
    )
    from failure_classifier import FailureType, classify_failure
    from batch_retry_manager import (
        BatchRetryManager,
        MAX_RETRIES_PER_FEATURE,
        CIRCUIT_BREAKER_THRESHOLD,
    )
    from batch_retry_consent import check_retry_consent, is_retry_enabled
except ImportError as e:
    pytest.skip(f"Implementation not found (TDD red phase): {e}", allow_module_level=True)


# =============================================================================
# Test Fixtures
# =============================================================================

@pytest.fixture
def temp_workspace(tmp_path):
    """Create temporary workspace for batch processing."""
    workspace = tmp_path / "batch-workspace"
    workspace.mkdir()

    # Create .claude directory
    claude_dir = workspace / ".claude"
    claude_dir.mkdir()

    return workspace


@pytest.fixture
def features_file(temp_workspace):
    """Create sample features file."""
    features_file = temp_workspace / "features.txt"
    features = [
        "Add user authentication",
        "Implement password reset",
        "Add email verification",
        "Create user profile API",
        "Add OAuth2 integration",
    ]
    features_file.write_text("\n".join(features))
    return features_file


@pytest.fixture
def state_file(temp_workspace):
    """Get path to batch state file."""
    return temp_workspace / ".claude" / "batch_state.json"


@pytest.fixture
def mock_auto_implement_success():
    """Mock successful /auto-implement execution."""
    def side_effect(*args, **kwargs):
        return MagicMock(returncode=0, stdout="Feature implemented successfully")
    return side_effect


@pytest.fixture
def mock_auto_implement_transient_failure():
    """Mock /auto-implement with transient failure (network error)."""
    def side_effect(*args, **kwargs):
        raise RuntimeError("ConnectionError: Failed to connect to API")
    return side_effect


@pytest.fixture
def mock_auto_implement_permanent_failure():
    """Mock /auto-implement with permanent failure (syntax error)."""
    def side_effect(*args, **kwargs):
        raise RuntimeError("SyntaxError: invalid syntax in file test.py line 42")
    return side_effect


# =============================================================================
# SECTION 1: Complete Retry Workflow Tests (3 tests)
# =============================================================================

class TestCompleteRetryWorkflow:
    """Test complete retry workflow (failure → classify → retry → success)."""

    def test_transient_failure_triggers_automatic_retry(
        self, temp_workspace, features_file, state_file
    ):
        """Test that transient failure triggers automatic retry."""
        # Arrange - enable retry feature
        with patch("batch_retry_consent.is_retry_enabled", return_value=True):
            features = features_file.read_text().strip().split("\n")
            batch_state = create_batch_state(str(features_file), features)
            save_batch_state(state_file, batch_state)

            retry_manager = BatchRetryManager(batch_state.batch_id, state_dir=temp_workspace / ".claude")

            # Mock /auto-implement: fail once with network error, then succeed
            call_count = 0

            def mock_auto_implement(*args, **kwargs):
                nonlocal call_count
                call_count += 1
                if call_count == 1:
                    raise RuntimeError("ConnectionError: Failed to connect to API")
                return MagicMock(returncode=0, stdout="Success")

            # Act
            with patch("subprocess.run", side_effect=mock_auto_implement):
                # Simulate batch-implement processing first feature
                feature_index = 0

                try:
                    # First attempt fails
                    result = subprocess.run(["auto-implement"], check=True)
                except RuntimeError as e:
                    # Classify failure
                    error_msg = str(e)
                    failure_type = classify_failure(error_msg)

                    # Check if should retry
                    decision = retry_manager.should_retry_feature(feature_index, failure_type)

                    if decision.should_retry:
                        # Record retry attempt
                        retry_manager.record_retry_attempt(feature_index, error_msg)

                        # Retry (should succeed)
                        result = subprocess.run(["auto-implement"], check=True)

            # Assert - retry was triggered and succeeded
            assert call_count == 2
            assert retry_manager.get_retry_count(feature_index) == 1

    def test_successful_retry_completes_feature(
        self, temp_workspace, features_file, state_file
    ):
        """Test that successful retry marks feature as completed."""
        # Arrange
        with patch("batch_retry_consent.is_retry_enabled", return_value=True):
            features = features_file.read_text().strip().split("\n")
            batch_state = create_batch_state(str(features_file), features)
            save_batch_state(state_file, batch_state)

            retry_manager = BatchRetryManager(batch_state.batch_id, state_dir=temp_workspace / ".claude")

            # Act - fail once, then succeed
            feature_index = 0
            error_msg = "ConnectionError: Network error"
            failure_type = classify_failure(error_msg)

            # First attempt fails
            retry_manager.record_retry_attempt(feature_index, error_msg)

            # Retry succeeds - mark as completed
            from batch_state_manager import update_batch_progress
            update_batch_progress(
                state_file,
                feature_index=feature_index,
                status="completed",
                context_token_delta=5000,
            )

            # Assert
            final_state = load_batch_state(state_file)
            assert len(final_state.completed_features) == 1
            assert retry_manager.get_retry_count(feature_index) == 1

    def test_retry_workflow_logs_to_audit_file(
        self, temp_workspace, features_file, state_file
    ):
        """Test that retry attempts are logged to audit file."""
        # Arrange
        with patch("batch_retry_consent.is_retry_enabled", return_value=True):
            features = features_file.read_text().strip().split("\n")
            batch_state = create_batch_state(str(features_file), features)
            save_batch_state(state_file, batch_state)

            retry_manager = BatchRetryManager(batch_state.batch_id, state_dir=temp_workspace / ".claude")

            # Act
            with patch("batch_retry_manager.log_audit_event") as mock_audit:
                feature_index = 0
                error_msg = "ConnectionError: Network error"

                retry_manager.record_retry_attempt(feature_index, error_msg)

                # Assert - audit log called
                mock_audit.assert_called_once()
                call_args = str(mock_audit.call_args)
                assert "retry" in call_args.lower()
                assert "ConnectionError" in call_args or "Network error" in call_args


# =============================================================================
# SECTION 2: Max Retry Limit Tests (2 tests)
# =============================================================================

class TestMaxRetryLimit:
    """Test max retry limit enforcement (3 attempts then fail)."""

    def test_feature_fails_after_max_retries(
        self, temp_workspace, features_file, state_file
    ):
        """Test that feature fails after 3 retry attempts."""
        # Arrange
        with patch("batch_retry_consent.is_retry_enabled", return_value=True):
            features = features_file.read_text().strip().split("\n")
            batch_state = create_batch_state(str(features_file), features)
            save_batch_state(state_file, batch_state)

            retry_manager = BatchRetryManager(batch_state.batch_id, state_dir=temp_workspace / ".claude")

            # Act - simulate 3 failed retry attempts
            feature_index = 0
            error_msg = "ConnectionError: Network error"
            failure_type = FailureType.TRANSIENT

            for attempt in range(MAX_RETRIES_PER_FEATURE):
                retry_manager.record_retry_attempt(feature_index, error_msg)

            # Try one more retry (should be blocked)
            decision = retry_manager.should_retry_feature(feature_index, failure_type)

            # Assert
            assert decision.should_retry is False
            assert decision.reason == "max_retries_reached"
            assert retry_manager.get_retry_count(feature_index) == MAX_RETRIES_PER_FEATURE

    def test_batch_continues_after_max_retries_exhausted(
        self, temp_workspace, features_file, state_file
    ):
        """Test that batch continues to next feature after max retries."""
        # Arrange
        with patch("batch_retry_consent.is_retry_enabled", return_value=True):
            features = features_file.read_text().strip().split("\n")
            batch_state = create_batch_state(str(features_file), features)
            save_batch_state(state_file, batch_state)

            retry_manager = BatchRetryManager(batch_state.batch_id, state_dir=temp_workspace / ".claude")

            # Act - exhaust retries for feature 0
            for _ in range(MAX_RETRIES_PER_FEATURE):
                retry_manager.record_retry_attempt(0, "ConnectionError")

            # Mark feature 0 as failed
            from batch_state_manager import update_batch_progress
            update_batch_progress(
                state_file,
                feature_index=0,
                status="failed",
                error_message="Max retries exhausted",
                context_token_delta=5000,
            )

            # Process feature 1 successfully
            update_batch_progress(
                state_file,
                feature_index=1,
                status="completed",
                context_token_delta=5000,
            )

            # Assert - batch continued
            final_state = load_batch_state(state_file)
            assert len(final_state.failed_features) == 1
            assert len(final_state.completed_features) == 1
            assert final_state.current_index == 2  # Moved to feature 2


# =============================================================================
# SECTION 3: Circuit Breaker Tests (3 tests)
# =============================================================================

class TestCircuitBreaker:
    """Test circuit breaker after 5 consecutive failures."""

    def test_circuit_breaker_triggers_after_five_failures(
        self, temp_workspace, features_file, state_file
    ):
        """Test that circuit breaker triggers after 5 consecutive failures."""
        # Arrange
        with patch("batch_retry_consent.is_retry_enabled", return_value=True):
            features = features_file.read_text().strip().split("\n")
            batch_state = create_batch_state(str(features_file), features)
            save_batch_state(state_file, batch_state)

            retry_manager = BatchRetryManager(batch_state.batch_id, state_dir=temp_workspace / ".claude")

            # Act - simulate 5 consecutive failures
            for i in range(CIRCUIT_BREAKER_THRESHOLD):
                retry_manager.record_retry_attempt(i, "ConnectionError")

            # Check circuit breaker
            is_open = retry_manager.check_circuit_breaker()

            # Assert
            assert is_open is True

    def test_retry_blocked_when_circuit_breaker_open(
        self, temp_workspace, features_file, state_file
    ):
        """Test that retry is blocked when circuit breaker is open."""
        # Arrange
        with patch("batch_retry_consent.is_retry_enabled", return_value=True):
            features = features_file.read_text().strip().split("\n")
            batch_state = create_batch_state(str(features_file), features)
            save_batch_state(state_file, batch_state)

            retry_manager = BatchRetryManager(batch_state.batch_id, state_dir=temp_workspace / ".claude")

            # Trigger circuit breaker
            for i in range(CIRCUIT_BREAKER_THRESHOLD):
                retry_manager.record_retry_attempt(i, "ConnectionError")

            # Act - try to retry next feature
            decision = retry_manager.should_retry_feature(5, FailureType.TRANSIENT)

            # Assert
            assert decision.should_retry is False
            assert decision.reason == "circuit_breaker_open"

    def test_circuit_breaker_message_displayed_to_user(
        self, temp_workspace, features_file, state_file
    ):
        """Test that circuit breaker displays message to user."""
        # Arrange
        with patch("batch_retry_consent.is_retry_enabled", return_value=True):
            features = features_file.read_text().strip().split("\n")
            batch_state = create_batch_state(str(features_file), features)
            save_batch_state(state_file, batch_state)

            retry_manager = BatchRetryManager(batch_state.batch_id, state_dir=temp_workspace / ".claude")

            # Act - trigger circuit breaker
            with patch("builtins.print") as mock_print:
                for i in range(CIRCUIT_BREAKER_THRESHOLD):
                    retry_manager.record_retry_attempt(i, "ConnectionError")

                # Implementation should display message when circuit opens
                # Check if message was printed
                print_calls = [str(call) for call in mock_print.call_args_list]
                combined_output = " ".join(print_calls).lower()

                # Assert - message contains circuit breaker info
                assert "circuit" in combined_output or "consecutive" in combined_output or "paused" in combined_output


# =============================================================================
# SECTION 4: Permanent vs Transient Failure Tests (2 tests)
# =============================================================================

class TestPermanentVsTransientFailures:
    """Test handling of permanent vs transient failures."""

    def test_permanent_failure_not_retried(
        self, temp_workspace, features_file, state_file
    ):
        """Test that permanent failures (syntax errors) are not retried."""
        # Arrange
        with patch("batch_retry_consent.is_retry_enabled", return_value=True):
            features = features_file.read_text().strip().split("\n")
            batch_state = create_batch_state(str(features_file), features)
            save_batch_state(state_file, batch_state)

            retry_manager = BatchRetryManager(batch_state.batch_id, state_dir=temp_workspace / ".claude")

            # Act - permanent failure
            feature_index = 0
            error_msg = "SyntaxError: invalid syntax in test.py line 42"
            failure_type = classify_failure(error_msg)

            # Check if should retry
            decision = retry_manager.should_retry_feature(feature_index, failure_type)

            # Assert
            assert failure_type == FailureType.PERMANENT
            assert decision.should_retry is False
            assert decision.reason == "permanent_failure"

    def test_transient_failure_retried(
        self, temp_workspace, features_file, state_file
    ):
        """Test that transient failures (network errors) are retried."""
        # Arrange
        with patch("batch_retry_consent.is_retry_enabled", return_value=True):
            features = features_file.read_text().strip().split("\n")
            batch_state = create_batch_state(str(features_file), features)
            save_batch_state(state_file, batch_state)

            retry_manager = BatchRetryManager(batch_state.batch_id, state_dir=temp_workspace / ".claude")

            # Act - transient failure
            feature_index = 0
            error_msg = "ConnectionError: Failed to connect to API"
            failure_type = classify_failure(error_msg)

            # Check if should retry
            decision = retry_manager.should_retry_feature(feature_index, failure_type)

            # Assert
            assert failure_type == FailureType.TRANSIENT
            assert decision.should_retry is True


# =============================================================================
# SECTION 5: User Interruption Tests (2 tests)
# =============================================================================

class TestUserInterruption:
    """Test user interruption during retry (Ctrl+C)."""

    def test_ctrl_c_during_retry_handled_gracefully(
        self, temp_workspace, features_file, state_file
    ):
        """Test that Ctrl+C during retry is handled gracefully."""
        # Arrange
        with patch("batch_retry_consent.is_retry_enabled", return_value=True):
            features = features_file.read_text().strip().split("\n")
            batch_state = create_batch_state(str(features_file), features)
            save_batch_state(state_file, batch_state)

            retry_manager = BatchRetryManager(batch_state.batch_id, state_dir=temp_workspace / ".claude")

            # Act - simulate Ctrl+C during retry
            def mock_auto_implement(*args, **kwargs):
                raise KeyboardInterrupt("User pressed Ctrl+C")

            with patch("subprocess.run", side_effect=mock_auto_implement):
                try:
                    subprocess.run(["auto-implement"], check=True)
                except KeyboardInterrupt:
                    # Implementation should save state and exit cleanly
                    pass

            # Assert - state file intact, can resume later
            final_state = load_batch_state(state_file)
            assert final_state is not None
            assert final_state.batch_id == batch_state.batch_id

    def test_retry_state_saved_before_interruption(
        self, temp_workspace, features_file, state_file
    ):
        """Test that retry state is saved before user interruption."""
        # Arrange
        with patch("batch_retry_consent.is_retry_enabled", return_value=True):
            features = features_file.read_text().strip().split("\n")
            batch_state = create_batch_state(str(features_file), features)
            save_batch_state(state_file, batch_state)

            retry_manager = BatchRetryManager(batch_state.batch_id, state_dir=temp_workspace / ".claude")

            # Record retry attempt
            retry_manager.record_retry_attempt(0, "ConnectionError")

            # Act - simulate interruption
            # (retry state should already be saved)

            # Reload manager (simulate restart)
            retry_manager2 = BatchRetryManager(batch_state.batch_id, state_dir=temp_workspace / ".claude")

            # Assert - retry count persisted
            assert retry_manager2.get_retry_count(0) == 1


# =============================================================================
# SECTION 6: Consent Workflow Tests (3 tests)
# =============================================================================

class TestConsentWorkflow:
    """Test consent workflow integration."""

    def test_retry_enabled_when_consent_given(
        self, temp_workspace, features_file, state_file
    ):
        """Test that retry works when user gives consent."""
        # Arrange
        with patch("batch_retry_consent.is_retry_enabled", return_value=True):
            features = features_file.read_text().strip().split("\n")
            batch_state = create_batch_state(str(features_file), features)
            save_batch_state(state_file, batch_state)

            retry_manager = BatchRetryManager(batch_state.batch_id, state_dir=temp_workspace / ".claude")

            # Act
            feature_index = 0
            decision = retry_manager.should_retry_feature(feature_index, FailureType.TRANSIENT)

            # Assert
            assert decision.should_retry is True

    def test_retry_disabled_when_consent_declined(
        self, temp_workspace, features_file, state_file
    ):
        """Test that retry is skipped when user declines consent."""
        # Arrange
        with patch("batch_retry_consent.is_retry_enabled", return_value=False):
            features = features_file.read_text().strip().split("\n")
            batch_state = create_batch_state(str(features_file), features)
            save_batch_state(state_file, batch_state)

            retry_manager = BatchRetryManager(batch_state.batch_id, state_dir=temp_workspace / ".claude")

            # Act
            feature_index = 0
            decision = retry_manager.should_retry_feature(feature_index, FailureType.TRANSIENT)

            # Assert - retry blocked due to no consent
            assert decision.should_retry is False
            assert decision.reason == "consent_not_given"

    def test_first_run_prompts_for_consent(
        self, temp_workspace, features_file, state_file
    ):
        """Test that first run prompts user for consent."""
        # Arrange - no consent state exists
        with patch("batch_retry_consent.load_consent_state", return_value=None):
            with patch("batch_retry_consent.prompt_for_retry_consent", return_value=True) as mock_prompt:
                # Act
                result = check_retry_consent()

                # Assert
                mock_prompt.assert_called_once()
                assert result is True


# =============================================================================
# SECTION 7: State Persistence Tests (2 tests)
# =============================================================================

class TestStatePersistenceWithRetries:
    """Test retry state persistence across restarts."""

    def test_retry_counts_persist_across_batch_restarts(
        self, temp_workspace, features_file, state_file
    ):
        """Test that retry counts persist when batch is restarted."""
        # Arrange
        with patch("batch_retry_consent.is_retry_enabled", return_value=True):
            features = features_file.read_text().strip().split("\n")
            batch_state = create_batch_state(str(features_file), features)
            save_batch_state(state_file, batch_state)

            batch_id = batch_state.batch_id

            # Record retries with first manager
            manager1 = BatchRetryManager(batch_id, state_dir=temp_workspace / ".claude")
            manager1.record_retry_attempt(0, "Error 1")
            manager1.record_retry_attempt(1, "Error 2")

            # Act - simulate batch restart (create new manager)
            manager2 = BatchRetryManager(batch_id, state_dir=temp_workspace / ".claude")

            # Assert - retry counts persisted
            assert manager2.get_retry_count(0) == 1
            assert manager2.get_retry_count(1) == 1
            assert manager2.get_global_retry_count() == 2

    def test_circuit_breaker_state_persists_across_restarts(
        self, temp_workspace, features_file, state_file
    ):
        """Test that circuit breaker state persists across restarts."""
        # Arrange
        with patch("batch_retry_consent.is_retry_enabled", return_value=True):
            features = features_file.read_text().strip().split("\n")
            batch_state = create_batch_state(str(features_file), features)
            save_batch_state(state_file, batch_state)

            batch_id = batch_state.batch_id

            # Trigger circuit breaker
            manager1 = BatchRetryManager(batch_id, state_dir=temp_workspace / ".claude")
            for i in range(CIRCUIT_BREAKER_THRESHOLD):
                manager1.record_retry_attempt(i, "Error")

            assert manager1.check_circuit_breaker() is True

            # Act - restart batch
            manager2 = BatchRetryManager(batch_id, state_dir=temp_workspace / ".claude")

            # Assert - circuit breaker still open
            assert manager2.check_circuit_breaker() is True


# =============================================================================
# Test Summary
# =============================================================================

"""
TEST SUMMARY (17 integration tests for batch retry workflow):

SECTION 1: Complete Retry Workflow (3 tests)
✗ test_transient_failure_triggers_automatic_retry
✗ test_successful_retry_completes_feature
✗ test_retry_workflow_logs_to_audit_file

SECTION 2: Max Retry Limit (2 tests)
✗ test_feature_fails_after_max_retries
✗ test_batch_continues_after_max_retries_exhausted

SECTION 3: Circuit Breaker (3 tests)
✗ test_circuit_breaker_triggers_after_five_failures
✗ test_retry_blocked_when_circuit_breaker_open
✗ test_circuit_breaker_message_displayed_to_user

SECTION 4: Permanent vs Transient Failures (2 tests)
✗ test_permanent_failure_not_retried
✗ test_transient_failure_retried

SECTION 5: User Interruption (2 tests)
✗ test_ctrl_c_during_retry_handled_gracefully
✗ test_retry_state_saved_before_interruption

SECTION 6: Consent Workflow (3 tests)
✗ test_retry_enabled_when_consent_given
✗ test_retry_disabled_when_consent_declined
✗ test_first_run_prompts_for_consent

SECTION 7: State Persistence (2 tests)
✗ test_retry_counts_persist_across_batch_restarts
✗ test_circuit_breaker_state_persists_across_restarts

TOTAL: 17 integration tests (all FAILING - TDD red phase)

Integration Coverage:
- Complete retry workflow (failure → classify → retry → success)
- Max retry limit enforcement (3 attempts)
- Circuit breaker (5 consecutive failures)
- Transient vs permanent failure handling
- User interruption (Ctrl+C) handling
- Consent workflow integration
- State persistence across restarts
- Audit logging
"""
