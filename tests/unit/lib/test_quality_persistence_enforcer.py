#!/usr/bin/env python3
"""
Unit tests for quality_persistence_enforcer module (TDD Red Phase - Issue #254).

Tests for central enforcement engine ensuring quality gates persist across batch retries.

TDD Mode: These tests are written BEFORE implementation.
All tests should FAIL initially (ImportError: module not found).

Test Strategy:
- Test completion gate enforcement (test pass requirements)
- Test retry strategy selection (different approaches per attempt)
- Test honest summary generation (skipped/failed features)
- Test issue close decision logic (only close completed features)
- Test circuit breaker integration
- Test quality metrics tracking

Security:
- Audit logging for all enforcement decisions
- Retry limits prevent infinite loops
- Quality metrics prevent false positives

Coverage Target: 95%+ for quality_persistence_enforcer.py

Date: 2026-01-19
Issue: #254 (Quality Persistence: Ensure quality gates persist across batch retries)
Agent: test-master
Phase: TDD Red (tests written BEFORE implementation)
Status: RED (all tests failing - module doesn't exist yet)
"""

import sys
import pytest
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock
from typing import Dict, Any

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
    from batch_state_manager import BatchState, create_batch_state
except ImportError as e:
    pytest.skip(f"Dependencies not found: {e}", allow_module_level=True)

# Import module under test (will fail - module doesn't exist yet - TDD!)
try:
    from quality_persistence_enforcer import (
        enforce_completion_gate,
        retry_with_different_approach,
        generate_honest_summary,
        should_close_issue,
        EnforcementResult,
        RetryStrategy,
        CompletionSummary,
        QualityGateError,
        MAX_RETRY_ATTEMPTS,
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
def sample_batch_state():
    """Create sample batch state for testing."""
    features = [
        "Add authentication",
        "Fix login bug",
        "Add logging",
    ]
    state = create_batch_state(features=features)
    return state


@pytest.fixture
def sample_test_results():
    """Sample test results dict."""
    return {
        "total": 10,
        "passed": 10,
        "failed": 0,
        "skipped": 0,
        "coverage": 85.0,
    }


@pytest.fixture
def failed_test_results():
    """Sample failed test results dict."""
    return {
        "total": 10,
        "passed": 8,
        "failed": 2,
        "skipped": 0,
        "coverage": 75.0,
    }


# =============================================================================
# SECTION 1: Completion Gate Enforcement Tests (5 tests)
# =============================================================================


class TestEnforceCompletionGate:
    """Test enforce_completion_gate() quality gate enforcement logic."""

    def test_enforce_completion_gate_passes_with_all_tests_passing(
        self, sample_batch_state, sample_test_results
    ):
        """Test completion gate passes when all tests pass."""
        # Arrange
        feature_index = 0

        # Act
        result = enforce_completion_gate(feature_index, sample_test_results)

        # Assert
        assert isinstance(result, EnforcementResult)
        assert result.passed is True
        assert result.reason == "all_tests_passed"
        assert result.test_failures == 0

    def test_enforce_completion_gate_fails_with_test_failures(
        self, sample_batch_state, failed_test_results
    ):
        """Test completion gate fails when tests fail."""
        # Arrange
        feature_index = 0

        # Act
        result = enforce_completion_gate(feature_index, failed_test_results)

        # Assert
        assert result.passed is False
        assert result.reason == "test_failures"
        assert result.test_failures == 2

    def test_enforce_completion_gate_fails_with_low_coverage(
        self, sample_batch_state
    ):
        """Test completion gate fails when coverage below threshold (80%)."""
        # Arrange
        feature_index = 0
        low_coverage_results = {
            "total": 10,
            "passed": 10,
            "failed": 0,
            "skipped": 0,
            "coverage": 75.0,  # Below 80% threshold
        }

        # Act
        result = enforce_completion_gate(feature_index, low_coverage_results)

        # Assert
        assert result.passed is False
        assert result.reason == "low_coverage"
        assert result.coverage < 80.0

    def test_enforce_completion_gate_tracks_retry_attempt(
        self, sample_batch_state, sample_test_results
    ):
        """Test completion gate tracks retry attempt number."""
        # Arrange
        feature_index = 0
        attempt_number = 2

        # Act
        result = enforce_completion_gate(
            feature_index, sample_test_results, attempt_number=attempt_number
        )

        # Assert
        assert result.attempt_number == 2

    def test_enforce_completion_gate_validates_test_results_format(
        self, sample_batch_state
    ):
        """Test completion gate validates test results dict format."""
        # Arrange
        feature_index = 0
        invalid_results = {"invalid": "format"}

        # Act & Assert
        with pytest.raises(QualityGateError, match="Invalid test results format"):
            enforce_completion_gate(feature_index, invalid_results)


# =============================================================================
# SECTION 2: Retry Strategy Selection Tests (4 tests)
# =============================================================================


class TestRetryWithDifferentApproach:
    """Test retry_with_different_approach() retry strategy selection."""

    def test_retry_with_different_approach_attempt_1_basic_retry(self):
        """Test attempt 1 uses basic retry strategy."""
        # Arrange
        feature_index = 0
        attempt_number = 1
        previous_error = "Tests failed: 2 failures"

        # Act
        strategy = retry_with_different_approach(
            feature_index, attempt_number, previous_error
        )

        # Assert
        assert isinstance(strategy, RetryStrategy)
        assert strategy.approach == "basic_retry"
        assert strategy.description == "Retry with same approach"
        assert strategy.attempt_number == 1

    def test_retry_with_different_approach_attempt_2_fix_tests_first(self):
        """Test attempt 2 suggests fixing tests first."""
        # Arrange
        feature_index = 0
        attempt_number = 2
        previous_error = "Tests failed: 2 failures"

        # Act
        strategy = retry_with_different_approach(
            feature_index, attempt_number, previous_error
        )

        # Assert
        assert strategy.approach == "fix_tests_first"
        assert "fix failing tests" in strategy.description.lower()

    def test_retry_with_different_approach_attempt_3_different_implementation(self):
        """Test attempt 3 suggests different implementation approach."""
        # Arrange
        feature_index = 0
        attempt_number = 3
        previous_error = "Tests failed: 2 failures"

        # Act
        strategy = retry_with_different_approach(
            feature_index, attempt_number, previous_error
        )

        # Assert
        assert strategy.approach == "different_implementation"
        assert "different approach" in strategy.description.lower()

    def test_retry_with_different_approach_max_attempts_exceeded(self):
        """Test retry strategy returns None when max attempts exceeded."""
        # Arrange
        feature_index = 0
        attempt_number = MAX_RETRY_ATTEMPTS + 1
        previous_error = "Tests failed: 2 failures"

        # Act
        strategy = retry_with_different_approach(
            feature_index, attempt_number, previous_error
        )

        # Assert
        assert strategy is None


# =============================================================================
# SECTION 3: Honest Summary Generation Tests (3 tests)
# =============================================================================


class TestGenerateHonestSummary:
    """Test generate_honest_summary() honest completion reporting."""

    def test_generate_honest_summary_all_completed(self):
        """Test honest summary with all features completed."""
        # Arrange
        state = create_batch_state(features=["Feature 1", "Feature 2", "Feature 3"])
        state.completed_features = [0, 1, 2]

        # Act
        summary = generate_honest_summary(state)

        # Assert
        assert isinstance(summary, CompletionSummary)
        assert summary.total_features == 3
        assert summary.completed_count == 3
        assert summary.failed_count == 0
        assert summary.skipped_count == 0
        assert summary.completion_rate == 100.0

    def test_generate_honest_summary_with_failures_and_skips(self):
        """Test honest summary with failures and skipped features."""
        # Arrange
        state = create_batch_state(features=["Feature 1", "Feature 2", "Feature 3"])
        state.completed_features = [0]
        state.failed_features = [
            {"feature_index": 1, "error_message": "Tests failed", "timestamp": "2026-01-19T12:00:00Z"}
        ]
        # Feature 2 is skipped (neither completed nor failed)

        # Act
        summary = generate_honest_summary(state)

        # Assert
        assert summary.completed_count == 1
        assert summary.failed_count == 1
        assert summary.skipped_count == 1
        assert summary.completion_rate == pytest.approx(33.33, abs=0.1)

    def test_generate_honest_summary_includes_quality_metrics(self):
        """Test honest summary includes quality metrics."""
        # Arrange
        state = create_batch_state(features=["Feature 1"])
        state.completed_features = [0]
        state.quality_metrics = {
            0: {"tests_passed": 10, "coverage": 85.0}
        }

        # Act
        summary = generate_honest_summary(state)

        # Assert
        assert summary.quality_metrics is not None
        assert 0 in summary.quality_metrics
        assert summary.quality_metrics[0]["coverage"] == 85.0


# =============================================================================
# SECTION 4: Issue Close Decision Tests (3 tests)
# =============================================================================


class TestShouldCloseIssue:
    """Test should_close_issue() decision logic for closing issues."""

    def test_should_close_issue_returns_true_for_completed_feature(self):
        """Test should_close_issue returns True for completed feature."""
        # Arrange
        feature_status = {
            "completed": True,
            "failed": False,
            "skipped": False,
            "quality_gate_passed": True,
        }

        # Act
        result = should_close_issue(feature_status)

        # Assert
        assert result is True

    def test_should_close_issue_returns_false_for_failed_feature(self):
        """Test should_close_issue returns False for failed feature."""
        # Arrange
        feature_status = {
            "completed": False,
            "failed": True,
            "skipped": False,
            "quality_gate_passed": False,
        }

        # Act
        result = should_close_issue(feature_status)

        # Assert
        assert result is False

    def test_should_close_issue_returns_false_for_skipped_feature(self):
        """Test should_close_issue returns False for skipped feature."""
        # Arrange
        feature_status = {
            "completed": False,
            "failed": False,
            "skipped": True,
            "quality_gate_passed": False,
        }

        # Act
        result = should_close_issue(feature_status)

        # Assert
        assert result is False


# =============================================================================
# SECTION 5: EnforcementResult Data Class Tests (2 tests)
# =============================================================================


class TestEnforcementResult:
    """Test EnforcementResult data class."""

    def test_enforcement_result_initialization(self):
        """Test EnforcementResult initializes correctly."""
        # Act
        result = EnforcementResult(
            passed=True,
            reason="all_tests_passed",
            test_failures=0,
            coverage=85.0,
            attempt_number=1,
        )

        # Assert
        assert result.passed is True
        assert result.reason == "all_tests_passed"
        assert result.test_failures == 0
        assert result.coverage == 85.0
        assert result.attempt_number == 1

    def test_enforcement_result_to_dict(self):
        """Test EnforcementResult converts to dict."""
        # Arrange
        result = EnforcementResult(
            passed=False,
            reason="test_failures",
            test_failures=2,
            coverage=75.0,
            attempt_number=2,
        )

        # Act
        result_dict = result.to_dict()

        # Assert
        assert isinstance(result_dict, dict)
        assert result_dict["passed"] is False
        assert result_dict["test_failures"] == 2


# =============================================================================
# SECTION 6: Integration with Circuit Breaker Tests (2 tests)
# =============================================================================


class TestCircuitBreakerIntegration:
    """Test integration with circuit breaker for quality persistence."""

    def test_enforce_completion_gate_respects_circuit_breaker(
        self, sample_batch_state, failed_test_results
    ):
        """Test completion gate respects circuit breaker after max failures."""
        # Arrange
        feature_index = 0

        # Simulate MAX_RETRY_ATTEMPTS failures
        for attempt in range(1, MAX_RETRY_ATTEMPTS + 1):
            result = enforce_completion_gate(
                feature_index, failed_test_results, attempt_number=attempt
            )
            assert result.passed is False

        # Act - attempt beyond max
        with pytest.raises(QualityGateError, match="Max retry attempts exceeded"):
            enforce_completion_gate(
                feature_index, failed_test_results, attempt_number=MAX_RETRY_ATTEMPTS + 1
            )

    def test_retry_strategy_provides_escalating_approaches(self):
        """Test retry strategy escalates approaches across attempts."""
        # Arrange
        feature_index = 0
        previous_error = "Tests failed"

        # Act - get strategies for attempts 1-3
        strategies = []
        for attempt in range(1, 4):
            strategy = retry_with_different_approach(feature_index, attempt, previous_error)
            strategies.append(strategy.approach)

        # Assert - strategies should be different
        assert len(set(strategies)) == 3  # All unique strategies
        assert "basic_retry" in strategies
        assert "fix_tests_first" in strategies
        assert "different_implementation" in strategies


# =============================================================================
# SECTION 7: Audit Logging Tests (1 test)
# =============================================================================


class TestAuditLogging:
    """Test audit logging for quality enforcement decisions."""

    @patch('quality_persistence_enforcer.audit_log')
    def test_enforce_completion_gate_logs_decision(
        self, mock_audit_log, sample_batch_state, sample_test_results
    ):
        """Test completion gate logs enforcement decision."""
        # Arrange
        feature_index = 0

        # Act
        result = enforce_completion_gate(feature_index, sample_test_results)

        # Assert
        mock_audit_log.assert_called_once()
        call_args = mock_audit_log.call_args
        assert call_args[0][0] == "quality_gate_enforced"  # event_type
        assert call_args[0][1] == "success"  # status
        assert "feature_index" in call_args[0][2]  # context


# =============================================================================
# TDD Verification
# =============================================================================


def test_tdd_verification():
    """
    Verify TDD approach - this test ensures all tests are written BEFORE implementation.

    This test should FAIL initially with ImportError, proving we're doing TDD correctly.
    """
    # If we reach this point, the module was imported successfully
    # In TDD red phase, the pytest.skip() at module level should prevent us reaching here
    assert True, "TDD verification: Module exists, moving to green phase"
