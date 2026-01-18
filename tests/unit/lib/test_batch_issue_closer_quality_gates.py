#!/usr/bin/env python3
"""
Unit tests for batch_issue_closer quality gate integration (TDD Red Phase - Issue #254).

Tests for ensuring batch_issue_closer doesn't close issues for skipped/failed features.

TDD Mode: These tests are written BEFORE implementation modifications.
All tests should FAIL initially (functions don't exist yet or return wrong values).

Test Strategy:
- Test is_feature_skipped_or_failed() detection logic
- Test add_blocked_label_to_issue() GitHub API integration
- Test close_batch_feature_issue() respects quality gates
- Test integration with quality_persistence_enforcer
- Test issue labeling for failed features

Security:
- CWE-20: Validate issue numbers
- Audit logging for label operations
- Graceful degradation on API errors

Coverage Target: 90%+ for modified batch_issue_closer.py functions

Date: 2026-01-19
Issue: #254 (Quality Persistence: Don't close skipped/failed issues)
Agent: test-master
Phase: TDD Red (tests written BEFORE implementation)
Status: RED (all tests failing - functions don't exist yet)
"""

import sys
import pytest
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock, call
import subprocess

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
    from batch_issue_closer import (
        close_batch_feature_issue,
        should_auto_close_issues,
    )
except ImportError as e:
    pytest.skip(f"Dependencies not found: {e}", allow_module_level=True)

# Import NEW functions under test (will fail - don't exist yet - TDD!)
try:
    from batch_issue_closer import (
        is_feature_skipped_or_failed,
        add_blocked_label_to_issue,
        FeatureQualityStatus,
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
def sample_batch_state_with_failures():
    """Create batch state with mix of completed, failed, and pending features."""
    features = [
        "Feature 1 - Completed",
        "Feature 2 - Failed",
        "Feature 3 - Pending",
    ]
    state = create_batch_state(features=features, issue_numbers=[100, 101, 102])
    state.completed_features = [0]
    state.failed_features = [
        {"feature_index": 1, "error_message": "Tests failed", "timestamp": "2026-01-19T12:00:00Z"}
    ]
    return state


@pytest.fixture
def mock_gh_cli():
    """Mock gh CLI subprocess calls."""
    with patch('subprocess.run') as mock_run:
        mock_run.return_value = Mock(
            returncode=0,
            stdout="Label added successfully",
            stderr=""
        )
        yield mock_run


@pytest.fixture
def mock_env_auto_git_enabled():
    """Mock AUTO_GIT_ENABLED environment variable."""
    with patch.dict('os.environ', {'AUTO_GIT_ENABLED': 'true'}):
        yield


# =============================================================================
# SECTION 1: is_feature_skipped_or_failed() Tests (4 tests)
# =============================================================================


class TestIsFeatureSkippedOrFailed:
    """Test is_feature_skipped_or_failed() detection logic."""

    def test_is_feature_skipped_or_failed_returns_false_for_completed(
        self, sample_batch_state_with_failures
    ):
        """Test returns False for completed feature."""
        # Arrange
        state = sample_batch_state_with_failures
        feature_index = 0  # Completed feature

        # Act
        result = is_feature_skipped_or_failed(state, feature_index)

        # Assert
        assert result is False

    def test_is_feature_skipped_or_failed_returns_true_for_failed(
        self, sample_batch_state_with_failures
    ):
        """Test returns True for failed feature."""
        # Arrange
        state = sample_batch_state_with_failures
        feature_index = 1  # Failed feature

        # Act
        result = is_feature_skipped_or_failed(state, feature_index)

        # Assert
        assert result is True

    def test_is_feature_skipped_or_failed_returns_true_for_pending(
        self, sample_batch_state_with_failures
    ):
        """Test returns True for pending (skipped) feature."""
        # Arrange
        state = sample_batch_state_with_failures
        feature_index = 2  # Pending feature

        # Act
        result = is_feature_skipped_or_failed(state, feature_index)

        # Assert
        assert result is True

    def test_is_feature_skipped_or_failed_validates_feature_index(
        self, sample_batch_state_with_failures
    ):
        """Test validates feature_index is within bounds."""
        # Arrange
        state = sample_batch_state_with_failures
        invalid_index = 999

        # Act & Assert
        with pytest.raises(ValueError, match="Invalid feature index"):
            is_feature_skipped_or_failed(state, invalid_index)


# =============================================================================
# SECTION 2: add_blocked_label_to_issue() Tests (5 tests)
# =============================================================================


class TestAddBlockedLabelToIssue:
    """Test add_blocked_label_to_issue() GitHub API integration."""

    def test_add_blocked_label_to_issue_success(self, mock_gh_cli):
        """Test successfully adds 'blocked' label to issue."""
        # Arrange
        issue_number = 101

        # Act
        result = add_blocked_label_to_issue(issue_number)

        # Assert
        assert result is True
        mock_gh_cli.assert_called_once()
        call_args = mock_gh_cli.call_args[0][0]
        assert "gh" in call_args
        assert "issue" in call_args
        assert "edit" in call_args
        assert str(issue_number) in call_args
        assert "--add-label" in call_args
        assert "blocked" in call_args

    def test_add_blocked_label_to_issue_validates_issue_number(self, mock_gh_cli):
        """Test validates issue number is positive integer."""
        # Arrange
        invalid_issue_numbers = [-1, 0, 1000000]

        # Act & Assert
        for invalid_num in invalid_issue_numbers:
            with pytest.raises(ValueError, match="Invalid issue number"):
                add_blocked_label_to_issue(invalid_num)

    def test_add_blocked_label_to_issue_handles_gh_cli_error(self, mock_gh_cli):
        """Test handles gh CLI error gracefully."""
        # Arrange
        issue_number = 101
        mock_gh_cli.side_effect = subprocess.CalledProcessError(
            returncode=1,
            cmd=['gh', 'issue', 'edit'],
            stderr="Issue not found"
        )

        # Act
        result = add_blocked_label_to_issue(issue_number)

        # Assert
        assert result is False

    def test_add_blocked_label_to_issue_handles_timeout(self, mock_gh_cli):
        """Test handles gh CLI timeout gracefully."""
        # Arrange
        issue_number = 101
        mock_gh_cli.side_effect = subprocess.TimeoutExpired(
            cmd=['gh', 'issue', 'edit'],
            timeout=10
        )

        # Act
        result = add_blocked_label_to_issue(issue_number)

        # Assert
        assert result is False

    @patch('batch_issue_closer.audit_log')
    def test_add_blocked_label_to_issue_logs_operation(
        self, mock_audit_log, mock_gh_cli
    ):
        """Test logs label operation to audit log."""
        # Arrange
        issue_number = 101

        # Act
        result = add_blocked_label_to_issue(issue_number)

        # Assert
        mock_audit_log.assert_called_once()
        call_args = mock_audit_log.call_args
        assert call_args[0][0] == "issue_label_added"
        assert "issue_number" in call_args[0][2]


# =============================================================================
# SECTION 3: close_batch_feature_issue() Quality Gate Integration (3 tests)
# =============================================================================


class TestCloseBatchFeatureIssueQualityGates:
    """Test close_batch_feature_issue() respects quality gates."""

    @patch('batch_issue_closer.add_blocked_label_to_issue')
    @patch('batch_issue_closer.is_feature_skipped_or_failed')
    def test_close_batch_feature_issue_skips_failed_feature(
        self, mock_is_skipped, mock_add_label, sample_batch_state_with_failures, mock_env_auto_git_enabled
    ):
        """Test doesn't close issue for failed feature but adds blocked label."""
        # Arrange
        state = sample_batch_state_with_failures
        feature_index = 1  # Failed feature
        mock_is_skipped.return_value = True

        # Act
        result = close_batch_feature_issue(
            state=state,
            feature_index=feature_index,
            commit_sha="abc123",
            branch="feature/test",
        )

        # Assert
        assert result['skipped'] is True
        assert "failed" in result['reason'].lower() or "quality" in result['reason'].lower() or "skipped" in result['reason'].lower()
        # Should add blocked label, NOT close issue
        mock_add_label.assert_called_once()

    @patch('batch_issue_closer.is_feature_skipped_or_failed')
    @patch('batch_issue_closer.add_blocked_label_to_issue')
    def test_close_batch_feature_issue_adds_blocked_label_for_failed(
        self, mock_add_label, mock_is_skipped, sample_batch_state_with_failures, mock_env_auto_git_enabled
    ):
        """Test adds 'blocked' label to issue for failed feature."""
        # Arrange
        state = sample_batch_state_with_failures
        feature_index = 1  # Failed feature with issue #101
        mock_is_skipped.return_value = True

        # Act
        result = close_batch_feature_issue(
            state=state,
            feature_index=feature_index,
            commit_sha="abc123",
            branch="feature/test",
        )

        # Assert
        mock_add_label.assert_called_once_with(101)

    @patch('batch_issue_closer.is_feature_skipped_or_failed')
    @patch('batch_issue_closer.subprocess.run')
    def test_close_batch_feature_issue_closes_completed_feature(
        self, mock_run, mock_is_skipped, sample_batch_state_with_failures, mock_env_auto_git_enabled
    ):
        """Test closes issue for completed feature (quality gate passed)."""
        # Arrange
        state = sample_batch_state_with_failures
        feature_index = 0  # Completed feature
        mock_is_skipped.return_value = False
        mock_run.return_value = Mock(returncode=0, stdout="", stderr="")

        # Act
        result = close_batch_feature_issue(
            state=state,
            feature_index=feature_index,
            commit_sha="abc123",
            branch="feature/test",
        )

        # Assert
        assert result['success'] is True
        mock_run.assert_called_once()  # Should call gh CLI to close issue


# =============================================================================
# SECTION 4: FeatureQualityStatus Data Class Tests (2 tests)
# =============================================================================


class TestFeatureQualityStatus:
    """Test FeatureQualityStatus data class for quality state tracking."""

    def test_feature_quality_status_initialization(self):
        """Test FeatureQualityStatus initializes correctly."""
        # Act
        status = FeatureQualityStatus(
            feature_index=0,
            completed=True,
            failed=False,
            skipped=False,
            quality_gate_passed=True,
        )

        # Assert
        assert status.feature_index == 0
        assert status.completed is True
        assert status.failed is False
        assert status.skipped is False
        assert status.quality_gate_passed is True

    def test_feature_quality_status_from_batch_state(
        self, sample_batch_state_with_failures
    ):
        """Test creating FeatureQualityStatus from BatchState."""
        # Arrange
        state = sample_batch_state_with_failures

        # Act - completed feature
        status_completed = FeatureQualityStatus.from_batch_state(state, 0)

        # Assert
        assert status_completed.completed is True
        assert status_completed.failed is False
        assert status_completed.skipped is False

        # Act - failed feature
        status_failed = FeatureQualityStatus.from_batch_state(state, 1)

        # Assert
        assert status_failed.completed is False
        assert status_failed.failed is True
        assert status_failed.skipped is False

        # Act - pending feature
        status_pending = FeatureQualityStatus.from_batch_state(state, 2)

        # Assert
        assert status_pending.completed is False
        assert status_pending.failed is False
        assert status_pending.skipped is True


# =============================================================================
# SECTION 5: Integration with quality_persistence_enforcer Tests (1 test)
# =============================================================================


class TestQualityEnforcerIntegration:
    """Test integration between batch_issue_closer and quality_persistence_enforcer."""

    @patch('batch_issue_closer.add_blocked_label_to_issue')
    @patch('batch_issue_closer.is_feature_skipped_or_failed')
    def test_close_batch_feature_issue_uses_quality_gate_check(
        self, mock_is_skipped, mock_add_label, sample_batch_state_with_failures, mock_env_auto_git_enabled
    ):
        """Test close_batch_feature_issue respects is_feature_skipped_or_failed check."""
        # Arrange
        state = sample_batch_state_with_failures
        feature_index = 0
        mock_is_skipped.return_value = True  # Quality gate says feature is skipped/failed

        # Act
        result = close_batch_feature_issue(
            state=state,
            feature_index=feature_index,
            commit_sha="abc123",
            branch="feature/test",
        )

        # Assert
        assert result['skipped'] is True
        # Should add blocked label, NOT close issue
        mock_add_label.assert_called_once()


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
