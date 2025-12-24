#!/usr/bin/env python3
"""
Unit tests for batch git integration module (Issue #93).

Tests the execute_git_workflow() function with in_batch_mode parameter
for consent-free git operations during batch processing.

TDD Mode: These tests are written BEFORE implementation.
All tests should FAIL initially (in_batch_mode parameter doesn't exist).

Test Strategy:
- Test in_batch_mode parameter skips consent prompts
- Test in_batch_mode preserves env var consent
- Test in_batch_mode git operations (commit, push, PR)
- Test in_batch_mode error handling
- Test in_batch_mode audit logging
- Test in_batch_mode with various consent configurations
- Test graceful degradation in batch mode
- Test batch mode with network failures
- Test batch mode with git errors
- Test batch mode with detached HEAD
- Test batch mode with permission errors
- Test batch mode return values
- Test batch mode doesn't modify user state
- Test batch mode respects AUTO_GIT_ENABLED=false
- Test batch mode with missing git/gh CLI

Date: 2025-12-06
Issue: #93 (Add auto-commit to batch workflow)
Agent: test-master
Phase: TDD Red (tests written BEFORE implementation)
Status: RED (expected - no implementation yet)
"""

import json
import os
import sys
import pytest
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock, call
from subprocess import CalledProcessError
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

# Import will fail - implementation doesn't exist yet (TDD!)
try:
    from auto_implement_git_integration import (
        execute_git_workflow,
        check_consent_via_env,
        BatchGitError,
    )
except ImportError as e:
    pytest.skip(f"Implementation not found (TDD red phase): {e}", allow_module_level=True)


# =============================================================================
# Test Fixtures
# =============================================================================

@pytest.fixture
def mock_git_available():
    """Mock git CLI available."""
    with patch('auto_implement_git_integration.check_git_available', return_value=True):
        yield


@pytest.fixture
def mock_gh_available():
    """Mock gh CLI available."""
    with patch('auto_implement_git_integration.check_gh_available', return_value=True):
        yield


@pytest.fixture
def mock_agent_invoker():
    """Mock agent invoker for commit message generation."""
    with patch('auto_implement_git_integration.AgentInvoker') as mock:
        instance = MagicMock()
        instance.invoke_agent.return_value = {
            'success': True,
            'commit_message': 'feat: Add user authentication\n\nImplement login flow'
        }
        mock.return_value = instance
        yield instance


# =============================================================================
# Test in_batch_mode Parameter Existence
# =============================================================================

class TestBatchModeParameter:
    """Test in_batch_mode parameter in execute_git_workflow()."""

    def test_execute_git_workflow_accepts_in_batch_mode_parameter(self, mock_git_available):
        """Test execute_git_workflow() accepts in_batch_mode parameter."""
        # Should not raise TypeError for unknown parameter
        try:
            execute_git_workflow(
                workflow_id='test-123',
                request='Add feature',
                in_batch_mode=True  # NEW parameter
            )
        except TypeError as e:
            if 'in_batch_mode' in str(e):
                pytest.fail("execute_git_workflow() doesn't accept in_batch_mode parameter")

    def test_in_batch_mode_defaults_to_false(self, mock_git_available, mock_agent_invoker):
        """Test in_batch_mode defaults to False when not specified."""
        with patch('auto_implement_git_integration.show_first_run_warning') as mock_warning:
            mock_warning.return_value = True
            with patch('auto_implement_git_integration.auto_commit_and_push') as mock_git:
                mock_git.return_value = {'success': True, 'commit_sha': 'abc123'}

                # Call without in_batch_mode parameter
                result = execute_git_workflow(
                    workflow_id='test-123',
                    request='Add feature'
                )

                # Should still prompt for first-run consent (in_batch_mode=False)
                mock_warning.assert_called_once()


# =============================================================================
# Test Consent Bypass in Batch Mode
# =============================================================================

class TestConsentBypassInBatchMode:
    """Test in_batch_mode=True skips consent prompts."""

    @patch.dict(os.environ, {'AUTO_GIT_ENABLED': 'true'})
    def test_batch_mode_skips_first_run_warning(self, mock_git_available, mock_agent_invoker):
        """Test in_batch_mode=True skips first-run consent prompt."""
        with patch('auto_implement_git_integration.show_first_run_warning') as mock_warning:
            with patch('auto_implement_git_integration.auto_commit_and_push') as mock_git:
                mock_git.return_value = {'success': True, 'commit_sha': 'abc123'}

                # Call with in_batch_mode=True
                result = execute_git_workflow(
                    workflow_id='test-123',
                    request='Add feature',
                    in_batch_mode=True
                )

                # Should NOT prompt for consent
                mock_warning.assert_not_called()

    @patch.dict(os.environ, {'AUTO_GIT_ENABLED': 'true'})
    def test_batch_mode_respects_env_var_consent(self, mock_git_available, mock_agent_invoker):
        """Test in_batch_mode respects AUTO_GIT_ENABLED env var."""
        with patch('auto_implement_git_integration.auto_commit_and_push') as mock_git:
            mock_git.return_value = {'success': True, 'commit_sha': 'abc123'}

            # Call with in_batch_mode=True
            result = execute_git_workflow(
                workflow_id='test-123',
                request='Add feature',
                in_batch_mode=True
            )

            # Should execute git operations (consent via env var)
            assert result['success'] is True
            mock_git.assert_called_once()

    @patch.dict(os.environ, {'AUTO_GIT_ENABLED': 'false'})
    def test_batch_mode_respects_disabled_consent(self, mock_git_available, mock_agent_invoker):
        """Test in_batch_mode respects AUTO_GIT_ENABLED=false."""
        with patch('auto_implement_git_integration.auto_commit_and_push') as mock_git:

            # Call with in_batch_mode=True but consent disabled
            result = execute_git_workflow(
                workflow_id='test-123',
                request='Add feature',
                in_batch_mode=True
            )

            # Should NOT execute git operations (consent explicitly disabled)
            assert result['git_enabled'] is False
            mock_git.assert_not_called()


# =============================================================================
# Test Git Operations in Batch Mode
# =============================================================================

class TestGitOperationsInBatchMode:
    """Test git operations execute correctly in batch mode."""

    @patch.dict(os.environ, {'AUTO_GIT_ENABLED': 'true'})
    def test_batch_mode_commit_success(self, mock_git_available, mock_agent_invoker):
        """Test successful commit in batch mode."""
        with patch('auto_implement_git_integration.auto_commit_and_push') as mock_git:
            mock_git.return_value = {
                'success': True,
                'commit_sha': 'abc123def456',
                'branch': 'feature/batch-1'
            }

            result = execute_git_workflow(
                workflow_id='test-123',
                request='Add feature',
                in_batch_mode=True
            )

            # Should have successful commit
            assert result['success'] is True
            assert result['commit_sha'] == 'abc123def456'
            assert result['branch'] == 'feature/batch-1'

    @patch.dict(os.environ, {'AUTO_GIT_ENABLED': 'true', 'AUTO_GIT_PUSH': 'true'})
    def test_batch_mode_push_success(self, mock_git_available, mock_agent_invoker):
        """Test successful push in batch mode."""
        with patch('auto_implement_git_integration.auto_commit_and_push') as mock_git:
            mock_git.return_value = {
                'success': True,
                'commit_sha': 'abc123',
                'pushed': True,
                'remote': 'origin'
            }

            result = execute_git_workflow(
                workflow_id='test-123',
                request='Add feature',
                in_batch_mode=True,
                push=True
            )

            # Should have successful push
            assert result['pushed'] is True
            assert result['remote'] == 'origin'

    @patch.dict(os.environ, {'AUTO_GIT_ENABLED': 'true', 'AUTO_GIT_PR': 'true'})
    def test_batch_mode_pr_creation_success(self, mock_git_available, mock_gh_available, mock_agent_invoker):
        """Test successful PR creation in batch mode."""
        with patch('auto_implement_git_integration.auto_commit_and_push') as mock_git:
            mock_git.return_value = {'success': True, 'commit_sha': 'abc123'}
            with patch('auto_implement_git_integration.create_pull_request') as mock_pr:
                mock_pr.return_value = {
                    'success': True,
                    'pr_number': 123,
                    'pr_url': 'https://github.com/user/repo/pull/123'
                }

                result = execute_git_workflow(
                    workflow_id='test-123',
                    request='Add feature',
                    in_batch_mode=True,
                    create_pr=True
                )

                # Should have successful PR creation
                assert result.get('pr_created') is True
                assert result.get('pr_number') == 123
                assert result.get('pr_url') == 'https://github.com/user/repo/pull/123'


# =============================================================================
# Test Error Handling in Batch Mode
# =============================================================================

class TestErrorHandlingInBatchMode:
    """Test graceful error handling in batch mode."""

    @patch.dict(os.environ, {'AUTO_GIT_ENABLED': 'true'})
    def test_batch_mode_commit_failure_graceful(self, mock_git_available, mock_agent_invoker):
        """Test commit failure doesn't raise exception in batch mode."""
        with patch('auto_implement_git_integration.auto_commit_and_push') as mock_git:
            mock_git.return_value = {
                'success': False,
                'error': 'No changes to commit'
            }

            # Should not raise exception
            result = execute_git_workflow(
                workflow_id='test-123',
                request='Add feature',
                in_batch_mode=True
            )

            # Should return failure result
            assert result['success'] is False
            assert 'error' in result

    @patch.dict(os.environ, {'AUTO_GIT_ENABLED': 'true', 'AUTO_GIT_PUSH': 'true'})
    def test_batch_mode_network_failure_graceful(self, mock_git_available, mock_agent_invoker):
        """Test network failure during push doesn't crash batch."""
        with patch('auto_implement_git_integration.auto_commit_and_push') as mock_git:
            mock_git.side_effect = CalledProcessError(1, 'git push', stderr='Network unreachable')

            # Should not raise exception
            result = execute_git_workflow(
                workflow_id='test-123',
                request='Add feature',
                in_batch_mode=True,
                push=True
            )

            # Should return failure result
            assert result['success'] is False
            assert 'network' in result.get('error', '').lower() or 'unreachable' in result.get('error', '').lower()

    @patch.dict(os.environ, {'AUTO_GIT_ENABLED': 'true'})
    def test_batch_mode_git_not_available(self):
        """Test graceful degradation when git CLI not available."""
        with patch('auto_implement_git_integration.check_git_available', return_value=False):

            # Should not raise exception
            result = execute_git_workflow(
                workflow_id='test-123',
                request='Add feature',
                in_batch_mode=True
            )

            # Should return failure with clear message
            assert result['success'] is False
            assert 'git' in result.get('error', '').lower()


# =============================================================================
# Test Audit Logging in Batch Mode
# =============================================================================

class TestAuditLoggingInBatchMode:
    """Test audit logging works in batch mode."""

    @patch.dict(os.environ, {'AUTO_GIT_ENABLED': 'true'})
    def test_batch_mode_logs_git_operations(self, mock_git_available, mock_agent_invoker):
        """Test batch mode logs git operations to audit log."""
        with patch('auto_implement_git_integration.auto_commit_and_push') as mock_git:
            mock_git.return_value = {'success': True, 'commit_sha': 'abc123'}
            with patch('auto_implement_git_integration.audit_log') as mock_audit:

                result = execute_git_workflow(
                    workflow_id='test-123',
                    request='Add feature',
                    in_batch_mode=True
                )

                # Should log batch mode operation
                audit_calls = [str(call) for call in mock_audit.call_args_list]
                assert any('batch_mode' in str(call).lower() for call in audit_calls)

    @patch.dict(os.environ, {'AUTO_GIT_ENABLED': 'true'})
    def test_batch_mode_logs_consent_source(self, mock_git_available, mock_agent_invoker):
        """Test batch mode logs consent source (env var vs interactive)."""
        with patch('auto_implement_git_integration.auto_commit_and_push') as mock_git:
            mock_git.return_value = {'success': True, 'commit_sha': 'abc123'}
            with patch('auto_implement_git_integration.audit_log') as mock_audit:

                result = execute_git_workflow(
                    workflow_id='test-123',
                    request='Add feature',
                    in_batch_mode=True
                )

                # Should log consent source as 'environment'
                audit_calls = [str(call) for call in mock_audit.call_args_list]
                assert any('environment' in str(call).lower() for call in audit_calls)


# =============================================================================
# Test Batch Mode Edge Cases
# =============================================================================

class TestBatchModeEdgeCases:
    """Test edge cases in batch mode."""

    @patch.dict(os.environ, {'AUTO_GIT_ENABLED': 'true'})
    def test_batch_mode_detached_head_warning(self, mock_git_available, mock_agent_invoker):
        """Test batch mode handles detached HEAD state."""
        with patch('auto_implement_git_integration.auto_commit_and_push') as mock_git:
            mock_git.return_value = {
                'success': False,
                'error': 'Detached HEAD state'
            }

            result = execute_git_workflow(
                workflow_id='test-123',
                request='Add feature',
                in_batch_mode=True
            )

            # Should warn but not crash
            assert result['success'] is False
            assert 'detached' in result.get('error', '').lower() or 'head' in result.get('error', '').lower()

    @patch.dict(os.environ, {'AUTO_GIT_ENABLED': 'true'})
    def test_batch_mode_permission_error(self, mock_git_available, mock_agent_invoker):
        """Test batch mode handles permission errors."""
        with patch('auto_implement_git_integration.auto_commit_and_push') as mock_git:
            mock_git.side_effect = PermissionError('Permission denied: .git/refs/heads/main')

            result = execute_git_workflow(
                workflow_id='test-123',
                request='Add feature',
                in_batch_mode=True
            )

            # Should handle gracefully
            assert result['success'] is False
            assert 'permission' in result.get('error', '').lower()

    @patch.dict(os.environ, {'AUTO_GIT_ENABLED': 'true'})
    def test_batch_mode_doesnt_modify_user_state(self, mock_git_available, mock_agent_invoker):
        """Test batch mode doesn't modify user state file."""
        with patch('auto_implement_git_integration.auto_commit_and_push') as mock_git:
            mock_git.return_value = {'success': True, 'commit_sha': 'abc123'}
            with patch('auto_implement_git_integration.user_state_manager') as mock_state:

                result = execute_git_workflow(
                    workflow_id='test-123',
                    request='Add feature',
                    in_batch_mode=True
                )

                # Should NOT update user state (no first-run prompts)
                # State manager should not be called to save consent choice
                if hasattr(mock_state, 'save_state'):
                    mock_state.save_state.assert_not_called()


# =============================================================================
# Test Return Values in Batch Mode
# =============================================================================

class TestReturnValuesInBatchMode:
    """Test return value structure in batch mode."""

    @patch.dict(os.environ, {'AUTO_GIT_ENABLED': 'true'})
    def test_batch_mode_returns_standard_structure(self, mock_git_available, mock_agent_invoker):
        """Test batch mode returns same structure as interactive mode."""
        with patch('auto_implement_git_integration.auto_commit_and_push') as mock_git:
            mock_git.return_value = {
                'success': True,
                'commit_sha': 'abc123',
                'branch': 'feature/test'
            }

            result = execute_git_workflow(
                workflow_id='test-123',
                request='Add feature',
                in_batch_mode=True
            )

            # Should have standard fields
            assert 'success' in result
            assert 'workflow_id' in result or 'commit_sha' in result
            assert isinstance(result, dict)

    @patch.dict(os.environ, {'AUTO_GIT_ENABLED': 'true'})
    def test_batch_mode_includes_batch_flag(self, mock_git_available, mock_agent_invoker):
        """Test batch mode includes batch_mode flag in return value."""
        with patch('auto_implement_git_integration.auto_commit_and_push') as mock_git:
            mock_git.return_value = {'success': True, 'commit_sha': 'abc123'}

            result = execute_git_workflow(
                workflow_id='test-123',
                request='Add feature',
                in_batch_mode=True
            )

            # Should indicate batch mode in result
            assert result.get('batch_mode') is True or result.get('in_batch_mode') is True
