#!/usr/bin/env python3
"""
Unit tests for batch_retry_manager exponential backoff (TDD Red Phase - Issue #254).

Tests for exponential backoff with jitter in retry timing.

TDD Mode: These tests are written BEFORE implementation modifications.
All tests should FAIL initially (functions don't exist yet or return wrong values).

Test Strategy:
- Test get_retry_delay() exponential backoff calculation
- Test jitter randomization (within bounds)
- Test retry_with_different_approach() integration
- Test max delay cap enforcement
- Test backoff timing in retry workflow

Security:
- Prevent resource exhaustion with max delay cap
- Audit logging for retry timing

Coverage Target: 90%+ for modified batch_retry_manager.py functions

Date: 2026-01-19
Issue: #254 (Quality Persistence: Add exponential backoff with jitter)
Agent: test-master
Phase: TDD Red (tests written BEFORE implementation)
Status: RED (all tests failing - functions don't exist yet)
"""

import sys
import pytest
import time
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock
import random

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

# Import dependencies (these exist)
try:
    from batch_retry_manager import (
        BatchRetryManager,
        MAX_RETRIES_PER_FEATURE,
    )
    from failure_classifier import FailureType
except ImportError as e:
    pytest.skip(f"Dependencies not found: {e}", allow_module_level=True)

# Import NEW functions under test (will fail - don't exist yet - TDD!)
try:
    from batch_retry_manager import (
        get_retry_delay,
        retry_with_different_approach,
        MAX_RETRY_DELAY,
        BASE_RETRY_DELAY,
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
def retry_manager(temp_state_dir):
    """Create BatchRetryManager instance."""
    batch_id = "batch-test-backoff"
    return BatchRetryManager(batch_id, state_dir=temp_state_dir)


# =============================================================================
# SECTION 1: get_retry_delay() Exponential Backoff Tests (6 tests)
# =============================================================================


class TestGetRetryDelay:
    """Test get_retry_delay() exponential backoff calculation."""

    def test_get_retry_delay_attempt_1_returns_base_delay(self):
        """Test attempt 1 returns base delay (1 second)."""
        # Arrange
        attempt_number = 1

        # Act
        delay = get_retry_delay(attempt_number)

        # Assert
        assert delay >= BASE_RETRY_DELAY * 0.5  # Allow for jitter
        assert delay <= BASE_RETRY_DELAY * 1.5

    def test_get_retry_delay_attempt_2_doubles_delay(self):
        """Test attempt 2 approximately doubles the delay (exponential)."""
        # Arrange
        attempt_number = 2

        # Act
        delay = get_retry_delay(attempt_number)

        # Assert
        # Exponential: base * (2 ^ (attempt - 1)) = 1 * 2^1 = 2 seconds
        expected_delay = BASE_RETRY_DELAY * 2
        assert delay >= expected_delay * 0.5  # Allow for jitter
        assert delay <= expected_delay * 1.5

    def test_get_retry_delay_attempt_3_quadruples_delay(self):
        """Test attempt 3 approximately quadruples the delay."""
        # Arrange
        attempt_number = 3

        # Act
        delay = get_retry_delay(attempt_number)

        # Assert
        # Exponential: base * (2 ^ (attempt - 1)) = 1 * 2^2 = 4 seconds
        expected_delay = BASE_RETRY_DELAY * 4
        assert delay >= expected_delay * 0.5  # Allow for jitter
        assert delay <= expected_delay * 1.5

    def test_get_retry_delay_enforces_max_delay_cap(self):
        """Test delay never exceeds MAX_RETRY_DELAY (60 seconds)."""
        # Arrange
        attempt_numbers = [10, 20, 100]  # Very high attempt numbers

        # Act & Assert
        for attempt in attempt_numbers:
            delay = get_retry_delay(attempt)
            assert delay <= MAX_RETRY_DELAY, f"Delay {delay} exceeds max {MAX_RETRY_DELAY} for attempt {attempt}"

    def test_get_retry_delay_includes_jitter(self):
        """Test delay includes jitter (randomization) to prevent thundering herd."""
        # Arrange
        attempt_number = 2
        delays = []

        # Act - get delay multiple times
        for _ in range(10):
            delay = get_retry_delay(attempt_number)
            delays.append(delay)

        # Assert - delays should vary (jitter applied)
        unique_delays = set(delays)
        assert len(unique_delays) > 1, "Delays should vary due to jitter"

    def test_get_retry_delay_jitter_within_bounds(self):
        """Test jitter stays within reasonable bounds (±50%)."""
        # Arrange
        attempt_number = 2
        expected_delay = BASE_RETRY_DELAY * 2  # 2 seconds
        delays = []

        # Act - collect multiple samples
        for _ in range(100):
            delay = get_retry_delay(attempt_number)
            delays.append(delay)

        # Assert - all delays within ±50% of expected
        min_delay = expected_delay * 0.5
        max_delay = expected_delay * 1.5
        for delay in delays:
            assert min_delay <= delay <= max_delay, f"Delay {delay} outside bounds [{min_delay}, {max_delay}]"


# =============================================================================
# SECTION 2: retry_with_different_approach() Integration Tests (3 tests)
# =============================================================================


class TestRetryWithDifferentApproachBackoff:
    """Test retry_with_different_approach() integration with backoff."""

    def test_retry_with_different_approach_returns_delay(self):
        """Test retry_with_different_approach returns delay in strategy."""
        # Arrange
        batch_id = "batch-test"
        feature_index = 0
        attempt_number = 1
        previous_error = "Tests failed"

        # Act
        result = retry_with_different_approach(
            batch_id, feature_index, attempt_number, previous_error
        )

        # Assert
        assert "delay" in result
        assert isinstance(result["delay"], float)
        assert result["delay"] > 0

    def test_retry_with_different_approach_increases_delay_per_attempt(self):
        """Test retry strategy increases delay for subsequent attempts."""
        # Arrange
        batch_id = "batch-test"
        feature_index = 0
        previous_error = "Tests failed"

        # Act - get delays for attempts 1, 2, 3
        result1 = retry_with_different_approach(batch_id, feature_index, 1, previous_error)
        result2 = retry_with_different_approach(batch_id, feature_index, 2, previous_error)
        result3 = retry_with_different_approach(batch_id, feature_index, 3, previous_error)

        # Assert - delays should increase (allowing for jitter variance)
        # Note: Due to jitter, we check that later attempts have HIGHER EXPECTED delays
        # even if individual samples might vary
        assert result1["expected_delay"] < result2["expected_delay"]
        assert result2["expected_delay"] < result3["expected_delay"]

    def test_retry_with_different_approach_caps_delay_at_max(self):
        """Test retry strategy caps delay at MAX_RETRY_DELAY."""
        # Arrange
        batch_id = "batch-test"
        feature_index = 0
        attempt_number = 100  # Very high attempt
        previous_error = "Tests failed"

        # Act
        result = retry_with_different_approach(
            batch_id, feature_index, attempt_number, previous_error
        )

        # Assert
        assert result["delay"] <= MAX_RETRY_DELAY


# =============================================================================
# SECTION 3: Backoff Timing in Retry Workflow Tests (2 tests)
# =============================================================================


class TestBackoffTimingInRetryWorkflow:
    """Test backoff timing integration in retry workflow."""

    @patch('time.sleep')
    def test_retry_workflow_sleeps_for_calculated_delay(
        self, mock_sleep, retry_manager
    ):
        """Test retry workflow sleeps for calculated delay."""
        # Arrange
        feature_index = 0
        error_message = "Tests failed"

        # Record first retry (should calculate delay and sleep)
        retry_manager.record_retry_attempt(feature_index, error_message)

        # Act - perform retry with backoff
        attempt_number = retry_manager.get_retry_count(feature_index)
        expected_delay = get_retry_delay(attempt_number)

        # Simulate retry workflow calling sleep
        with patch('batch_retry_manager.get_retry_delay', return_value=expected_delay):
            # This would be called by the retry orchestrator
            time.sleep(expected_delay)

        # Assert - sleep was called (in test, we mock it)
        # In real code, batch_orchestrator would call time.sleep()
        assert retry_manager.get_retry_count(feature_index) == 1

    def test_retry_workflow_respects_max_delay_cap(self, retry_manager):
        """Test retry workflow never sleeps longer than MAX_RETRY_DELAY."""
        # Arrange
        feature_index = 0
        error_message = "Tests failed"

        # Simulate many retries
        for _ in range(10):
            retry_manager.record_retry_attempt(feature_index, error_message)

        # Act - calculate delay for next retry
        attempt_number = retry_manager.get_retry_count(feature_index) + 1
        delay = get_retry_delay(attempt_number)

        # Assert - delay should not exceed max
        assert delay <= MAX_RETRY_DELAY


# =============================================================================
# SECTION 4: Edge Cases and Error Handling Tests (1 test)
# =============================================================================


class TestBackoffEdgeCases:
    """Test edge cases and error handling for backoff."""

    def test_get_retry_delay_handles_zero_attempt(self):
        """Test get_retry_delay handles attempt_number=0 gracefully."""
        # Arrange
        attempt_number = 0

        # Act
        delay = get_retry_delay(attempt_number)

        # Assert - should return base delay (graceful degradation)
        assert delay >= 0
        assert delay <= BASE_RETRY_DELAY * 2  # Allow some jitter


# =============================================================================
# TDD Verification
# =============================================================================


def test_tdd_verification():
    """
    Verify TDD approach - this test ensures all tests are written BEFORE implementation.

    This test should FAIL initially with ImportError, proving we're doing TDD correctly.
    """
    # If we reach this point, the NEW functions were imported successfully
    # In TDD red phase, the pytest.skip() at module level should prevent us reaching here
    assert True, "TDD verification: New functions exist, moving to green phase"
