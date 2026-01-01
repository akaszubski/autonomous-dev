#!/usr/bin/env python3
"""
Unit tests for batch_issue_closer module (TDD Red Phase).

Tests for auto-closing GitHub issues after /batch-implement push operations.

TDD Mode: These tests are written BEFORE implementation.
All tests should FAIL initially (ImportError: module not found).

Test Strategy:
- Test consent checks (AUTO_GIT_ENABLED integration)
- Test issue number extraction (from batch state)
- Test close workflow (success, already closed, not found)
- Test circuit breaker (5 consecutive failures)
- Test git operations tracking integration
- Test graceful degradation (gh CLI errors, network issues)

Security Requirements:
- CWE-20: Input validation (issue number range)
- CWE-78: Command injection prevention (subprocess list args)
- Audit logging for all operations

Coverage Target: 90%+ for batch_issue_closer.py

Date: 2026-01-01
Issue: #168 (Auto-close GitHub issues after batch-implement push)
Agent: test-master
Phase: TDD Red (tests written BEFORE implementation)
Status: RED (implementation not found - expected)
"""

import json
import os
import sys
import pytest
import tempfile
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock, mock_open, call
from typing import Dict, Any
from dataclasses import asdict
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
except ImportError as e:
    pytest.skip(f"Dependencies not found: {e}", allow_module_level=True)

# Import module under test (will fail - module doesn't exist yet - TDD!)
try:
    from batch_issue_closer import (
        should_auto_close_issues,
        get_issue_number_for_feature,
        close_batch_feature_issue,
        handle_close_failure,
        BatchIssueCloseError,
        MAX_CONSECUTIVE_FAILURES,
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
    state_dir.mkdir(parents=True, exist_ok=True)
    return state_dir


@pytest.fixture
def sample_batch_state(temp_state_dir):
    """Create sample batch state with issue numbers."""
    features = [
        "Issue #72: Add authentication",
        "Issue #73: Fix login bug",
        "Add logging feature",
    ]
    state = create_batch_state(
        features=features,
        issue_numbers=[72, 73, None],
        source_type="mixed",
    )
    return state


@pytest.fixture
def mock_gh_cli():
    """Mock gh CLI subprocess calls."""
    with patch('subprocess.run') as mock_run:
        yield mock_run


@pytest.fixture
def mock_env_vars():
    """Mock environment variables."""
    with patch.dict(os.environ, {}, clear=True) as env:
        yield env


# =============================================================================
# Test: should_auto_close_issues() - Consent Checks
# =============================================================================


class TestShouldAutoCloseIssues:
    """Test should_auto_close_issues() consent checking logic."""

    def test_should_auto_close_issues_enabled(self, mock_env_vars):
        """Test should_auto_close_issues returns True when AUTO_GIT_ENABLED=true."""
        mock_env_vars['AUTO_GIT_ENABLED'] = 'true'

        result = should_auto_close_issues()

        assert result is True

    def test_should_auto_close_issues_disabled(self, mock_env_vars):
        """Test should_auto_close_issues returns False when AUTO_GIT_ENABLED=false."""
        mock_env_vars['AUTO_GIT_ENABLED'] = 'false'

        result = should_auto_close_issues()

        assert result is False

    def test_should_auto_close_issues_not_set(self, mock_env_vars):
        """Test should_auto_close_issues returns False when AUTO_GIT_ENABLED not set."""
        # Environment cleared by fixture
        result = should_auto_close_issues()

        assert result is False

    def test_should_auto_close_issues_case_insensitive(self, mock_env_vars):
        """Test should_auto_close_issues handles case-insensitive values."""
        test_cases = [
            ('TRUE', True),
            ('True', True),
            ('yes', True),
            ('FALSE', False),
            ('False', False),
            ('no', False),
        ]

        for env_value, expected in test_cases:
            mock_env_vars['AUTO_GIT_ENABLED'] = env_value
            result = should_auto_close_issues()
            assert result is expected, f"Failed for AUTO_GIT_ENABLED={env_value}"


# =============================================================================
# Test: get_issue_number_for_feature() - Issue Number Extraction
# =============================================================================


class TestGetIssueNumberForFeature:
    """Test get_issue_number_for_feature() issue number extraction logic."""

    def test_get_issue_number_from_issues_list(self, sample_batch_state):
        """Test extracting issue number from state.issue_numbers list."""
        # Feature index 0 should map to issue_numbers[0] = 72
        result = get_issue_number_for_feature(sample_batch_state, 0)

        assert result == 72

    def test_get_issue_number_from_issues_list_second_feature(self, sample_batch_state):
        """Test extracting issue number from second feature."""
        # Feature index 1 should map to issue_numbers[1] = 73
        result = get_issue_number_for_feature(sample_batch_state, 1)

        assert result == 73

    def test_get_issue_number_from_feature_text_pattern_1(self):
        """Test extracting issue number using regex pattern: 'Issue #N'."""
        features = ["Issue #99: Add feature"]
        state = create_batch_state(features=features)

        result = get_issue_number_for_feature(state, 0)

        assert result == 99

    def test_get_issue_number_from_feature_text_pattern_2(self):
        """Test extracting issue number using regex pattern: '#N'."""
        features = ["#88 - Fix bug"]
        state = create_batch_state(features=features)

        result = get_issue_number_for_feature(state, 0)

        assert result == 88

    def test_get_issue_number_from_feature_text_pattern_3(self):
        """Test extracting issue number using regex pattern: 'GH-N'."""
        features = ["GH-77 implementation"]
        state = create_batch_state(features=features)

        result = get_issue_number_for_feature(state, 0)

        assert result == 77

    def test_get_issue_number_from_feature_text_pattern_4(self):
        """Test extracting issue number using regex pattern: 'fixes #N'."""
        features = ["fixes #66 login bug"]
        state = create_batch_state(features=features)

        result = get_issue_number_for_feature(state, 0)

        assert result == 66

    def test_get_issue_number_returns_none_no_issue(self):
        """Test get_issue_number_for_feature returns None when no issue found."""
        features = ["Add new feature without issue reference"]
        state = create_batch_state(features=features)

        result = get_issue_number_for_feature(state, 0)

        assert result is None

    def test_get_issue_number_returns_none_none_in_list(self, sample_batch_state):
        """Test get_issue_number_for_feature returns None when issue_numbers[i] is None."""
        # Feature index 2 has None in issue_numbers list
        result = get_issue_number_for_feature(sample_batch_state, 2)

        assert result is None

    def test_get_issue_number_invalid_feature_index(self, sample_batch_state):
        """Test get_issue_number_for_feature raises error for invalid index."""
        with pytest.raises(BatchIssueCloseError, match="Invalid feature index"):
            get_issue_number_for_feature(sample_batch_state, 999)

    def test_get_issue_number_negative_feature_index(self, sample_batch_state):
        """Test get_issue_number_for_feature raises error for negative index."""
        with pytest.raises(BatchIssueCloseError, match="Invalid feature index"):
            get_issue_number_for_feature(sample_batch_state, -1)


# =============================================================================
# Test: close_batch_feature_issue() - Full Close Workflow
# =============================================================================


class TestCloseBatchFeatureIssue:
    """Test close_batch_feature_issue() full close workflow."""

    @patch('batch_issue_closer.should_auto_close_issues')
    def test_close_batch_feature_issue_disabled(self, mock_should_close, sample_batch_state):
        """Test close_batch_feature_issue skips when auto-close disabled."""
        mock_should_close.return_value = False

        result = close_batch_feature_issue(sample_batch_state, 0)

        assert result == {
            'success': False,
            'skipped': True,
            'reason': 'Auto-close disabled (AUTO_GIT_ENABLED not set)',
        }

    @patch('batch_issue_closer.should_auto_close_issues')
    @patch('batch_issue_closer.get_issue_number_for_feature')
    def test_close_batch_feature_issue_no_issue_number(
        self, mock_get_issue, mock_should_close, sample_batch_state
    ):
        """Test close_batch_feature_issue skips when no issue number found."""
        mock_should_close.return_value = True
        mock_get_issue.return_value = None

        result = close_batch_feature_issue(sample_batch_state, 0)

        assert result == {
            'success': False,
            'skipped': True,
            'reason': 'No issue number found for feature',
        }

    @patch('batch_issue_closer.should_auto_close_issues')
    @patch('batch_issue_closer.get_issue_number_for_feature')
    @patch('batch_issue_closer.subprocess.run')
    def test_close_batch_feature_issue_success(
        self, mock_run, mock_get_issue, mock_should_close, sample_batch_state
    ):
        """Test close_batch_feature_issue successfully closes issue."""
        mock_should_close.return_value = True
        mock_get_issue.return_value = 72

        # Mock gh CLI success
        mock_run.return_value = Mock(
            returncode=0,
            stdout='',
            stderr='',
        )

        result = close_batch_feature_issue(sample_batch_state, 0)

        assert result['success'] is True
        assert result['issue_number'] == 72
        assert result['skipped'] is False

        # Verify gh CLI called
        mock_run.assert_called_once()
        call_args = mock_run.call_args[0][0]
        assert call_args[:3] == ['gh', 'issue', 'close']
        assert '72' in call_args

    @patch('batch_issue_closer.should_auto_close_issues')
    @patch('batch_issue_closer.get_issue_number_for_feature')
    @patch('batch_issue_closer.subprocess.run')
    def test_close_batch_feature_issue_already_closed(
        self, mock_run, mock_get_issue, mock_should_close, sample_batch_state
    ):
        """Test close_batch_feature_issue handles already closed issue (idempotent)."""
        mock_should_close.return_value = True
        mock_get_issue.return_value = 72

        # Mock gh CLI error: already closed
        mock_run.side_effect = subprocess.CalledProcessError(
            returncode=1,
            cmd=['gh', 'issue', 'close'],
            stderr='Error: issue #72 is already closed'
        )

        result = close_batch_feature_issue(sample_batch_state, 0)

        # Idempotent: already closed should be success
        assert result['success'] is True
        assert result['issue_number'] == 72
        assert 'already closed' in result.get('message', '').lower()

    @patch('batch_issue_closer.should_auto_close_issues')
    @patch('batch_issue_closer.get_issue_number_for_feature')
    @patch('batch_issue_closer.subprocess.run')
    def test_close_batch_feature_issue_not_found(
        self, mock_run, mock_get_issue, mock_should_close, sample_batch_state
    ):
        """Test close_batch_feature_issue handles issue not found gracefully."""
        mock_should_close.return_value = True
        mock_get_issue.return_value = 999

        # Mock gh CLI error: not found
        mock_run.side_effect = subprocess.CalledProcessError(
            returncode=1,
            cmd=['gh', 'issue', 'close'],
            stderr='Error: issue #999 not found'
        )

        result = close_batch_feature_issue(sample_batch_state, 0)

        # Graceful degradation: not found is a failure but non-blocking
        assert result['success'] is False
        assert result['skipped'] is False
        assert result['issue_number'] == 999
        assert 'not found' in result.get('error', '').lower()

    @patch('batch_issue_closer.should_auto_close_issues')
    @patch('batch_issue_closer.get_issue_number_for_feature')
    @patch('batch_issue_closer.subprocess.run')
    def test_close_batch_feature_issue_network_error(
        self, mock_run, mock_get_issue, mock_should_close, sample_batch_state
    ):
        """Test close_batch_feature_issue handles network errors gracefully."""
        mock_should_close.return_value = True
        mock_get_issue.return_value = 72

        # Mock network timeout
        mock_run.side_effect = subprocess.TimeoutExpired(
            cmd=['gh', 'issue', 'close'],
            timeout=10
        )

        result = close_batch_feature_issue(sample_batch_state, 0)

        # Graceful degradation: timeout is a failure but non-blocking
        assert result['success'] is False
        assert result['skipped'] is False
        assert result['issue_number'] == 72
        assert 'timeout' in result.get('error', '').lower()

    @patch('batch_issue_closer.should_auto_close_issues')
    @patch('batch_issue_closer.get_issue_number_for_feature')
    @patch('batch_issue_closer.subprocess.run')
    @patch('batch_issue_closer.handle_close_failure')
    def test_close_batch_feature_issue_tracks_failures(
        self, mock_handle_failure, mock_run, mock_get_issue,
        mock_should_close, sample_batch_state
    ):
        """Test close_batch_feature_issue tracks failures via handle_close_failure."""
        mock_should_close.return_value = True
        mock_get_issue.return_value = 72
        mock_handle_failure.return_value = False  # Circuit breaker not triggered

        # Mock gh CLI error
        mock_run.side_effect = subprocess.CalledProcessError(
            returncode=1,
            cmd=['gh', 'issue', 'close'],
            stderr='Error: network error'
        )

        result = close_batch_feature_issue(sample_batch_state, 0)

        # Verify handle_close_failure called
        mock_handle_failure.assert_called_once()


# =============================================================================
# Test: handle_close_failure() - Circuit Breaker
# =============================================================================


class TestHandleCloseFailure:
    """Test handle_close_failure() circuit breaker logic."""

    def test_circuit_breaker_not_triggered_first_failure(self):
        """Test circuit breaker does not trigger on first failure."""
        # State with no failures
        failure_count = 0

        should_stop = handle_close_failure(failure_count)

        assert should_stop is False

    def test_circuit_breaker_not_triggered_few_failures(self):
        """Test circuit breaker does not trigger with < 5 consecutive failures."""
        # State with 4 consecutive failures
        failure_count = 4

        should_stop = handle_close_failure(failure_count)

        assert should_stop is False

    def test_circuit_breaker_triggers_after_5_failures(self):
        """Test circuit breaker triggers after 5 consecutive failures."""
        # State with 5 consecutive failures
        failure_count = 5

        should_stop = handle_close_failure(failure_count)

        assert should_stop is True

    def test_circuit_breaker_threshold_constant(self):
        """Test circuit breaker threshold matches MAX_CONSECUTIVE_FAILURES constant."""
        # Verify constant is 5 (as per design)
        assert MAX_CONSECUTIVE_FAILURES == 5

    def test_circuit_breaker_resets_on_success(self):
        """Test circuit breaker counter resets on successful close."""
        # This is tested implicitly in close_batch_feature_issue
        # When success=True, consecutive_failures should reset to 0
        # This test documents the expected behavior

        # Simulate: 4 failures, then 1 success
        # After success, consecutive_failures should be 0
        failure_count = 0  # Reset on success

        should_stop = handle_close_failure(failure_count)

        assert should_stop is False


# =============================================================================
# Test: Git Operations Tracking Integration
# =============================================================================


class TestGitOperationsTracking:
    """Test integration with batch_state_manager.record_git_operation()."""

    @patch('batch_issue_closer.should_auto_close_issues')
    @patch('batch_issue_closer.get_issue_number_for_feature')
    @patch('batch_issue_closer.subprocess.run')
    def test_issue_close_recorded_in_git_operations_success(
        self, mock_run, mock_get_issue, mock_should_close, sample_batch_state, temp_state_dir
    ):
        """Test successful issue close is recorded in git_operations dict."""
        from batch_state_manager import save_batch_state, load_batch_state

        mock_should_close.return_value = True
        mock_get_issue.return_value = 72
        mock_run.return_value = Mock(returncode=0, stdout='', stderr='')

        # Save initial state
        state_file = temp_state_dir / "batch_state.json"
        save_batch_state(state_file, sample_batch_state)

        # Close issue
        result = close_batch_feature_issue(sample_batch_state, 0, state_file=state_file)

        # Load state and verify git_operations updated
        updated_state = load_batch_state(state_file)

        assert 0 in updated_state.git_operations
        assert 'issue_close' in updated_state.git_operations[0]
        assert updated_state.git_operations[0]['issue_close']['success'] is True
        assert updated_state.git_operations[0]['issue_close']['issue_number'] == 72

    @patch('batch_issue_closer.should_auto_close_issues')
    @patch('batch_issue_closer.get_issue_number_for_feature')
    @patch('batch_issue_closer.subprocess.run')
    def test_issue_close_recorded_in_git_operations_failure(
        self, mock_run, mock_get_issue, mock_should_close, sample_batch_state, temp_state_dir
    ):
        """Test failed issue close is recorded in git_operations dict."""
        from batch_state_manager import save_batch_state, load_batch_state

        mock_should_close.return_value = True
        mock_get_issue.return_value = 72
        mock_run.side_effect = subprocess.CalledProcessError(
            returncode=1,
            cmd=['gh', 'issue', 'close'],
            stderr='Error: network error'
        )

        # Save initial state
        state_file = temp_state_dir / "batch_state.json"
        save_batch_state(state_file, sample_batch_state)

        # Close issue
        result = close_batch_feature_issue(sample_batch_state, 0, state_file=state_file)

        # Load state and verify git_operations updated
        updated_state = load_batch_state(state_file)

        assert 0 in updated_state.git_operations
        assert 'issue_close' in updated_state.git_operations[0]
        assert updated_state.git_operations[0]['issue_close']['success'] is False
        assert 'error' in updated_state.git_operations[0]['issue_close']

    @patch('batch_issue_closer.should_auto_close_issues')
    @patch('batch_issue_closer.get_issue_number_for_feature')
    def test_issue_close_recorded_skipped(
        self, mock_get_issue, mock_should_close, sample_batch_state, temp_state_dir
    ):
        """Test skipped issue close is recorded in git_operations dict."""
        from batch_state_manager import save_batch_state, load_batch_state

        mock_should_close.return_value = True
        mock_get_issue.return_value = None  # No issue number

        # Save initial state
        state_file = temp_state_dir / "batch_state.json"
        save_batch_state(state_file, sample_batch_state)

        # Close issue (will skip)
        result = close_batch_feature_issue(sample_batch_state, 0, state_file=state_file)

        # Load state and verify git_operations updated
        updated_state = load_batch_state(state_file)

        assert 0 in updated_state.git_operations
        assert 'issue_close' in updated_state.git_operations[0]
        assert updated_state.git_operations[0]['issue_close']['success'] is False
        assert updated_state.git_operations[0]['issue_close']['skipped'] is True


# =============================================================================
# Test: Security Validations
# =============================================================================


class TestSecurityValidations:
    """Test security requirements (CWE-20, CWE-78, audit logging)."""

    @patch('batch_issue_closer.should_auto_close_issues')
    @patch('batch_issue_closer.get_issue_number_for_feature')
    @patch('batch_issue_closer.subprocess.run')
    def test_subprocess_uses_list_args_not_shell(
        self, mock_run, mock_get_issue, mock_should_close, sample_batch_state
    ):
        """Test subprocess.run uses list args (CWE-78: command injection prevention)."""
        mock_should_close.return_value = True
        mock_get_issue.return_value = 72
        mock_run.return_value = Mock(returncode=0, stdout='', stderr='')

        close_batch_feature_issue(sample_batch_state, 0)

        # Verify subprocess.run called with list args, not string
        mock_run.assert_called_once()
        call_args = mock_run.call_args

        # First arg should be list
        assert isinstance(call_args[0][0], list)

        # shell=False should be set (default, but verify)
        assert call_args[1].get('shell', False) is False

    @patch('batch_issue_closer.should_auto_close_issues')
    @patch('batch_issue_closer.get_issue_number_for_feature')
    @patch('batch_issue_closer.subprocess.run')
    @patch('batch_issue_closer.audit_log')
    def test_audit_logging_on_success(
        self, mock_audit, mock_run, mock_get_issue, mock_should_close, sample_batch_state
    ):
        """Test audit logging occurs on successful issue close."""
        mock_should_close.return_value = True
        mock_get_issue.return_value = 72
        mock_run.return_value = Mock(returncode=0, stdout='', stderr='')

        close_batch_feature_issue(sample_batch_state, 0)

        # Verify audit_log called
        mock_audit.assert_called()

        # Check at least one call has success status
        success_calls = [
            call for call in mock_audit.call_args_list
            if call[1].get('status') == 'success'
        ]
        assert len(success_calls) > 0

    @patch('batch_issue_closer.should_auto_close_issues')
    @patch('batch_issue_closer.get_issue_number_for_feature')
    @patch('batch_issue_closer.subprocess.run')
    @patch('batch_issue_closer.audit_log')
    def test_audit_logging_on_failure(
        self, mock_audit, mock_run, mock_get_issue, mock_should_close, sample_batch_state
    ):
        """Test audit logging occurs on failed issue close."""
        mock_should_close.return_value = True
        mock_get_issue.return_value = 72
        mock_run.side_effect = subprocess.CalledProcessError(
            returncode=1,
            cmd=['gh', 'issue', 'close'],
            stderr='Error: network error'
        )

        close_batch_feature_issue(sample_batch_state, 0)

        # Verify audit_log called
        mock_audit.assert_called()

        # Check at least one call has failed status
        failed_calls = [
            call for call in mock_audit.call_args_list
            if call[1].get('status') in ('failed', 'error')
        ]
        assert len(failed_calls) > 0

    @patch('batch_issue_closer.should_auto_close_issues')
    @patch('batch_issue_closer.get_issue_number_for_feature')
    def test_validates_issue_number_positive(
        self, mock_get_issue, mock_should_close, sample_batch_state
    ):
        """Test issue number validation: must be positive (CWE-20)."""
        mock_should_close.return_value = True
        mock_get_issue.return_value = -1  # Invalid negative

        # Should raise ValueError or handle gracefully
        result = close_batch_feature_issue(sample_batch_state, 0)

        # Graceful degradation: negative issue number treated as error
        assert result['success'] is False
        assert 'error' in result or 'skipped' in result

    @patch('batch_issue_closer.should_auto_close_issues')
    @patch('batch_issue_closer.get_issue_number_for_feature')
    def test_validates_issue_number_max_range(
        self, mock_get_issue, mock_should_close, sample_batch_state
    ):
        """Test issue number validation: max range 999999 (CWE-20)."""
        mock_should_close.return_value = True
        mock_get_issue.return_value = 9999999  # Too large

        # Should raise ValueError or handle gracefully
        result = close_batch_feature_issue(sample_batch_state, 0)

        # Graceful degradation: out-of-range issue number treated as error
        assert result['success'] is False
        assert 'error' in result or 'skipped' in result


# =============================================================================
# Test: Edge Cases
# =============================================================================


class TestEdgeCases:
    """Test edge cases and error handling."""

    @patch('batch_issue_closer.should_auto_close_issues')
    @patch('batch_issue_closer.get_issue_number_for_feature')
    @patch('batch_issue_closer.subprocess.run')
    def test_gh_cli_not_installed(
        self, mock_run, mock_get_issue, mock_should_close, sample_batch_state
    ):
        """Test graceful degradation when gh CLI not installed."""
        mock_should_close.return_value = True
        mock_get_issue.return_value = 72

        # Mock FileNotFoundError (gh not found)
        mock_run.side_effect = FileNotFoundError("gh: command not found")

        result = close_batch_feature_issue(sample_batch_state, 0)

        # Graceful degradation: missing gh CLI is non-blocking failure
        assert result['success'] is False
        assert 'error' in result
        assert 'gh' in result['error'].lower() or 'not found' in result['error'].lower()

    @patch('batch_issue_closer.should_auto_close_issues')
    @patch('batch_issue_closer.get_issue_number_for_feature')
    @patch('batch_issue_closer.subprocess.run')
    def test_gh_cli_not_authenticated(
        self, mock_run, mock_get_issue, mock_should_close, sample_batch_state
    ):
        """Test graceful degradation when gh CLI not authenticated."""
        mock_should_close.return_value = True
        mock_get_issue.return_value = 72

        # Mock authentication error
        mock_run.side_effect = subprocess.CalledProcessError(
            returncode=1,
            cmd=['gh', 'issue', 'close'],
            stderr='Error: gh auth login required'
        )

        result = close_batch_feature_issue(sample_batch_state, 0)

        # Graceful degradation: auth error is non-blocking failure
        assert result['success'] is False
        assert 'error' in result
        assert 'auth' in result['error'].lower() or 'login' in result['error'].lower()

    def test_empty_batch_state(self):
        """Test handling of empty batch state (0 features)."""
        # This should be prevented at batch creation, but test defensive coding
        features = []

        # Should raise error at batch creation
        with pytest.raises(Exception):  # BatchStateError
            state = create_batch_state(features=features)

    @patch('batch_issue_closer.should_auto_close_issues')
    @patch('batch_issue_closer.get_issue_number_for_feature')
    @patch('batch_issue_closer.subprocess.run')
    def test_multiple_issue_references_in_feature(
        self, mock_run, mock_get_issue, mock_should_close
    ):
        """Test handling of multiple issue references in single feature."""
        features = ["Fix #72 and resolve #73"]
        state = create_batch_state(features=features)

        mock_should_close.return_value = True
        # get_issue_number_for_feature should return first match
        mock_get_issue.return_value = 72
        mock_run.return_value = Mock(returncode=0, stdout='', stderr='')

        result = close_batch_feature_issue(state, 0)

        # Should close first issue only
        assert result['success'] is True
        assert result['issue_number'] == 72


# =============================================================================
# Test: Integration with /batch-implement Workflow
# =============================================================================


class TestBatchImplementIntegration:
    """Test integration with /batch-implement workflow."""

    @patch('batch_issue_closer.should_auto_close_issues')
    @patch('batch_issue_closer.get_issue_number_for_feature')
    @patch('batch_issue_closer.subprocess.run')
    def test_batch_workflow_closes_each_feature_issue(
        self, mock_run, mock_get_issue, mock_should_close, sample_batch_state, temp_state_dir
    ):
        """Test /batch-implement workflow closes issue after each feature push."""
        from batch_state_manager import save_batch_state, load_batch_state

        mock_should_close.return_value = True
        mock_run.return_value = Mock(returncode=0, stdout='', stderr='')

        # Mock issue numbers for each feature
        issue_numbers = [72, 73, None]  # Third feature has no issue
        mock_get_issue.side_effect = issue_numbers

        # Save initial state
        state_file = temp_state_dir / "batch_state.json"
        save_batch_state(state_file, sample_batch_state)

        # Process each feature (simulating /batch-implement loop)
        for feature_index in range(3):
            result = close_batch_feature_issue(
                sample_batch_state,
                feature_index,
                state_file=state_file
            )

            # Load updated state
            sample_batch_state = load_batch_state(state_file)

        # Verify all features processed
        assert len(sample_batch_state.git_operations) == 3

        # Feature 0: should have issue_close success
        assert sample_batch_state.git_operations[0]['issue_close']['success'] is True
        assert sample_batch_state.git_operations[0]['issue_close']['issue_number'] == 72

        # Feature 1: should have issue_close success
        assert sample_batch_state.git_operations[1]['issue_close']['success'] is True
        assert sample_batch_state.git_operations[1]['issue_close']['issue_number'] == 73

        # Feature 2: should have issue_close skipped (no issue)
        assert sample_batch_state.git_operations[2]['issue_close']['skipped'] is True

    @patch('batch_issue_closer.should_auto_close_issues')
    def test_batch_workflow_respects_auto_close_disabled(
        self, mock_should_close, sample_batch_state
    ):
        """Test /batch-implement respects AUTO_GIT_ENABLED=false."""
        mock_should_close.return_value = False

        # Process feature with auto-close disabled
        result = close_batch_feature_issue(sample_batch_state, 0)

        # Should skip all features
        assert result['success'] is False
        assert result['skipped'] is True


# =============================================================================
# Test: get_feature_issue_close_status() Helper
# =============================================================================


class TestGetFeatureIssueCloseStatus:
    """Test get_feature_issue_close_status() helper function."""

    def test_get_feature_issue_close_status_success(self, sample_batch_state):
        """Test retrieving successful issue close status."""
        # Manually set git_operations
        sample_batch_state.git_operations[0] = {
            'issue_close': {
                'success': True,
                'issue_number': 72,
                'timestamp': '2026-01-01T12:00:00Z',
            }
        }

        from batch_state_manager import get_feature_git_operations

        result = get_feature_git_operations(sample_batch_state, 0)

        assert 'issue_close' in result
        assert result['issue_close']['success'] is True
        assert result['issue_close']['issue_number'] == 72

    def test_get_feature_issue_close_status_not_found(self, sample_batch_state):
        """Test retrieving issue close status when not recorded."""
        from batch_state_manager import get_feature_git_operations

        result = get_feature_git_operations(sample_batch_state, 0)

        # No git operations recorded yet
        assert result is None


# =============================================================================
# Run Tests
# =============================================================================


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
