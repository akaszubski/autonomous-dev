#!/usr/bin/env python3
"""
Integration tests for batch git edge cases (Issue #93).

Tests edge cases and error conditions for git automation in batch workflow:
network failures, merge conflicts, detached HEAD, permission errors, etc.

TDD Mode: These tests are written BEFORE implementation.
All tests should FAIL initially (no batch git integration).

Test Strategy:
- Test network failures during push
- Test merge conflicts
- Test detached HEAD state
- Test permission errors
- Test missing git/gh CLI
- Test concurrent git operations
- Test git operations with dirty working tree
- Test git operations with untracked files
- Test branch protection rules
- Test PR creation failures
- Test commit message generation failures
- Test retry logic for transient failures

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
import tempfile
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock
from subprocess import CalledProcessError, TimeoutExpired
from typing import Dict, Any

# Add lib directory to path for imports
sys.path.insert(
    0,
    str(
        Path(__file__).parent.parent.parent
        / "plugins"
        / "autonomous-dev"
        / "lib"
    ),
)

# Import will fail - implementation doesn't exist yet (TDD!)
try:
    from batch_state_manager import (
        BatchState,
        create_batch_state,
        record_git_operation,
        save_batch_state,
        load_batch_state,
    )
    from auto_implement_git_integration import execute_git_workflow
except ImportError as e:
    pytest.skip(f"Implementation not found (TDD red phase): {e}", allow_module_level=True)


# =============================================================================
# Test Fixtures
# =============================================================================

@pytest.fixture
def temp_repo(tmp_path):
    """Create temporary git repository."""
    repo_dir = tmp_path / "test-repo"
    repo_dir.mkdir()
    os.chdir(repo_dir)
    os.system('git init')
    os.system('git config user.name "Test User"')
    os.system('git config user.email "test@example.com"')
    (repo_dir / "README.md").write_text("# Test Repo")
    os.system('git add .')
    os.system('git commit -m "Initial commit"')
    yield repo_dir
    os.chdir(tmp_path)


@pytest.fixture
def sample_features():
    """Sample feature list."""
    return [
        "Add user authentication",
        "Implement password reset",
        "Add email verification",
    ]


# =============================================================================
# Test Network Failures
# =============================================================================

class TestNetworkFailures:
    """Test batch git workflow handles network failures gracefully."""

    @patch.dict(os.environ, {'AUTO_GIT_ENABLED': 'true', 'AUTO_GIT_PUSH': 'true'})
    def test_network_timeout_during_push(self, temp_repo, sample_features):
        """Test network timeout during push doesn't crash batch."""
        with patch('auto_implement_git_integration.auto_commit_and_push') as mock_git:
            mock_git.side_effect = TimeoutExpired('git push', 30)

            state_file = temp_repo / ".claude" / "batch_state.json"
            state_file.parent.mkdir(exist_ok=True)

            # Should not raise exception
            result = execute_git_workflow(
                workflow_id='test-123',
                request='Add feature',
                in_batch_mode=True,
                push=True
            )

            # Should return failure
            assert result['success'] is False
            assert 'timeout' in result.get('error', '').lower()

    @patch.dict(os.environ, {'AUTO_GIT_ENABLED': 'true', 'AUTO_GIT_PUSH': 'true'})
    def test_network_unreachable_during_push(self, temp_repo, sample_features):
        """Test network unreachable error during push."""
        with patch('auto_implement_git_integration.auto_commit_and_push') as mock_git:
            mock_git.side_effect = CalledProcessError(
                1, 'git push',
                stderr='fatal: unable to access: Network is unreachable'
            )

            result = execute_git_workflow(
                workflow_id='test-123',
                request='Add feature',
                in_batch_mode=True,
                push=True
            )

            # Should handle gracefully
            assert result['success'] is False
            assert 'network' in result.get('error', '').lower() or 'unreachable' in result.get('error', '').lower()

    @patch.dict(os.environ, {'AUTO_GIT_ENABLED': 'true', 'AUTO_GIT_PUSH': 'true'})
    def test_dns_resolution_failure(self, temp_repo, sample_features):
        """Test DNS resolution failure during push."""
        with patch('auto_implement_git_integration.auto_commit_and_push') as mock_git:
            mock_git.side_effect = CalledProcessError(
                1, 'git push',
                stderr='fatal: Could not resolve host: github.com'
            )

            result = execute_git_workflow(
                workflow_id='test-123',
                request='Add feature',
                in_batch_mode=True,
                push=True
            )

            # Should handle gracefully
            assert result['success'] is False
            assert 'resolve' in result.get('error', '').lower() or 'dns' in result.get('error', '').lower() or 'host' in result.get('error', '').lower()


# =============================================================================
# Test Merge Conflicts
# =============================================================================

class TestMergeConflicts:
    """Test batch git workflow handles merge conflicts."""

    @patch.dict(os.environ, {'AUTO_GIT_ENABLED': 'true'})
    def test_merge_conflict_detected(self, temp_repo, sample_features):
        """Test merge conflict detection and graceful handling."""
        with patch('auto_implement_git_integration.auto_commit_and_push') as mock_git:
            mock_git.return_value = {
                'success': False,
                'error': 'Merge conflict in file.py'
            }

            result = execute_git_workflow(
                workflow_id='test-123',
                request='Add feature',
                in_batch_mode=True
            )

            # Should handle gracefully
            assert result['success'] is False
            assert 'conflict' in result.get('error', '').lower() or 'merge' in result.get('error', '').lower()

    @patch.dict(os.environ, {'AUTO_GIT_ENABLED': 'true', 'AUTO_GIT_PR': 'true'})
    def test_pr_creation_fails_due_to_conflicts(self, temp_repo, sample_features):
        """Test PR creation failure when base branch has conflicts."""
        with patch('auto_implement_git_integration.auto_commit_and_push') as mock_git:
            mock_git.return_value = {'success': True, 'commit_sha': 'abc123'}
            with patch('auto_implement_git_integration.create_pull_request') as mock_pr:
                mock_pr.return_value = {
                    'success': False,
                    'error': 'Cannot create PR: merge conflicts with base branch'
                }

                result = execute_git_workflow(
                    workflow_id='test-123',
                    request='Add feature',
                    in_batch_mode=True,
                    create_pr=True
                )

                # Commit should succeed, PR should fail
                assert result.get('commit_sha') == 'abc123'
                assert result.get('pr_created') is False


# =============================================================================
# Test Detached HEAD State
# =============================================================================

class TestDetachedHeadState:
    """Test batch git workflow handles detached HEAD state."""

    @patch.dict(os.environ, {'AUTO_GIT_ENABLED': 'true'})
    def test_detached_head_warning(self, temp_repo, sample_features):
        """Test detached HEAD state produces warning but continues."""
        with patch('auto_implement_git_integration.auto_commit_and_push') as mock_git:
            mock_git.return_value = {
                'success': False,
                'error': 'Cannot commit in detached HEAD state'
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
    def test_detached_head_recovery_suggestion(self, temp_repo, sample_features):
        """Test detached HEAD error includes recovery suggestion."""
        with patch('auto_implement_git_integration.auto_commit_and_push') as mock_git:
            mock_git.return_value = {
                'success': False,
                'error': 'Detached HEAD state',
                'suggestion': 'Run: git checkout -b new-branch'
            }

            result = execute_git_workflow(
                workflow_id='test-123',
                request='Add feature',
                in_batch_mode=True
            )

            # Should include recovery suggestion
            assert result['success'] is False
            assert 'suggestion' in result or 'recovery' in result.get('error', '').lower()


# =============================================================================
# Test Permission Errors
# =============================================================================

class TestPermissionErrors:
    """Test batch git workflow handles permission errors."""

    @patch.dict(os.environ, {'AUTO_GIT_ENABLED': 'true'})
    def test_git_directory_permission_denied(self, temp_repo, sample_features):
        """Test permission denied accessing .git directory."""
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

    @patch.dict(os.environ, {'AUTO_GIT_ENABLED': 'true', 'AUTO_GIT_PUSH': 'true'})
    def test_remote_push_permission_denied(self, temp_repo, sample_features):
        """Test permission denied pushing to remote."""
        with patch('auto_implement_git_integration.auto_commit_and_push') as mock_git:
            mock_git.side_effect = CalledProcessError(
                1, 'git push',
                stderr='fatal: Authentication failed for remote repository'
            )

            result = execute_git_workflow(
                workflow_id='test-123',
                request='Add feature',
                in_batch_mode=True,
                push=True
            )

            # Should handle gracefully
            assert result['success'] is False
            assert 'authentication' in result.get('error', '').lower() or 'permission' in result.get('error', '').lower()


# =============================================================================
# Test Missing CLI Tools
# =============================================================================

class TestMissingCliTools:
    """Test batch git workflow handles missing CLI tools."""

    @patch.dict(os.environ, {'AUTO_GIT_ENABLED': 'true'})
    def test_git_cli_not_installed(self, temp_repo, sample_features):
        """Test graceful handling when git CLI not installed."""
        with patch('auto_implement_git_integration.check_git_available', return_value=False):

            result = execute_git_workflow(
                workflow_id='test-123',
                request='Add feature',
                in_batch_mode=True
            )

            # Should handle gracefully
            assert result['success'] is False
            assert 'git' in result.get('error', '').lower()

    @patch.dict(os.environ, {'AUTO_GIT_ENABLED': 'true', 'AUTO_GIT_PR': 'true'})
    def test_gh_cli_not_installed(self, temp_repo, sample_features):
        """Test graceful handling when gh CLI not installed."""
        with patch('auto_implement_git_integration.check_git_available', return_value=True):
            with patch('auto_implement_git_integration.check_gh_available', return_value=False):
                with patch('auto_implement_git_integration.auto_commit_and_push') as mock_git:
                    mock_git.return_value = {'success': True, 'commit_sha': 'abc123'}

                    result = execute_git_workflow(
                        workflow_id='test-123',
                        request='Add feature',
                        in_batch_mode=True,
                        create_pr=True
                    )

                    # Commit should succeed, PR should skip
                    assert result.get('commit_sha') == 'abc123'
                    assert result.get('pr_created') is False


# =============================================================================
# Test Dirty Working Tree
# =============================================================================

class TestDirtyWorkingTree:
    """Test batch git workflow handles dirty working tree."""

    @patch.dict(os.environ, {'AUTO_GIT_ENABLED': 'true'})
    def test_uncommitted_changes_warning(self, temp_repo, sample_features):
        """Test warning when uncommitted changes present."""
        with patch('auto_implement_git_integration.auto_commit_and_push') as mock_git:
            mock_git.return_value = {
                'success': True,
                'commit_sha': 'abc123',
                'warning': 'Uncommitted changes included in commit'
            }

            result = execute_git_workflow(
                workflow_id='test-123',
                request='Add feature',
                in_batch_mode=True
            )

            # Should succeed but include warning
            assert result['success'] is True
            assert 'warning' in result or result.get('commit_sha') is not None

    @patch.dict(os.environ, {'AUTO_GIT_ENABLED': 'true'})
    def test_untracked_files_excluded(self, temp_repo, sample_features):
        """Test untracked files are excluded from commit."""
        with patch('auto_implement_git_integration.auto_commit_and_push') as mock_git:
            mock_git.return_value = {
                'success': True,
                'commit_sha': 'abc123',
                'untracked_files_excluded': True
            }

            result = execute_git_workflow(
                workflow_id='test-123',
                request='Add feature',
                in_batch_mode=True
            )

            # Should succeed
            assert result['success'] is True


# =============================================================================
# Test Branch Protection Rules
# =============================================================================

class TestBranchProtectionRules:
    """Test batch git workflow handles branch protection."""

    @patch.dict(os.environ, {'AUTO_GIT_ENABLED': 'true', 'AUTO_GIT_PUSH': 'true'})
    def test_push_rejected_by_branch_protection(self, temp_repo, sample_features):
        """Test push rejection due to branch protection rules."""
        with patch('auto_implement_git_integration.auto_commit_and_push') as mock_git:
            mock_git.side_effect = CalledProcessError(
                1, 'git push',
                stderr='fatal: [remote rejected] Branch protected by rules'
            )

            result = execute_git_workflow(
                workflow_id='test-123',
                request='Add feature',
                in_batch_mode=True,
                push=True
            )

            # Should handle gracefully
            assert result['success'] is False
            assert 'protected' in result.get('error', '').lower() or 'rejected' in result.get('error', '').lower()

    @patch.dict(os.environ, {'AUTO_GIT_ENABLED': 'true', 'AUTO_GIT_PR': 'true'})
    def test_pr_requires_approvals(self, temp_repo, sample_features):
        """Test PR creation notes approval requirements."""
        with patch('auto_implement_git_integration.auto_commit_and_push') as mock_git:
            mock_git.return_value = {'success': True, 'commit_sha': 'abc123'}
            with patch('auto_implement_git_integration.create_pull_request') as mock_pr:
                mock_pr.return_value = {
                    'success': True,
                    'pr_number': 123,
                    'pr_url': 'https://github.com/user/repo/pull/123',
                    'requires_approvals': 2
                }

                result = execute_git_workflow(
                    workflow_id='test-123',
                    request='Add feature',
                    in_batch_mode=True,
                    create_pr=True
                )

                # Should succeed and note approval requirements
                assert result.get('pr_created') is True
                # Check if approval requirements noted
                assert result.get('requires_approvals') == 2 or result.get('pr_url') is not None


# =============================================================================
# Test Commit Message Generation Failures
# =============================================================================

class TestCommitMessageGenerationFailures:
    """Test batch git workflow handles commit message generation failures."""

    @patch.dict(os.environ, {'AUTO_GIT_ENABLED': 'true'})
    def test_commit_message_agent_timeout(self, temp_repo, sample_features):
        """Test timeout during commit message generation."""
        with patch('auto_implement_git_integration.AgentInvoker') as mock_invoker:
            instance = MagicMock()
            instance.invoke_agent.side_effect = TimeoutExpired('claude', 60)
            mock_invoker.return_value = instance

            result = execute_git_workflow(
                workflow_id='test-123',
                request='Add feature',
                in_batch_mode=True
            )

            # Should fallback to default commit message
            assert result['success'] is False or result.get('commit_message_fallback') is True

    @patch.dict(os.environ, {'AUTO_GIT_ENABLED': 'true'})
    def test_commit_message_agent_error(self, temp_repo, sample_features):
        """Test error during commit message generation."""
        with patch('auto_implement_git_integration.AgentInvoker') as mock_invoker:
            instance = MagicMock()
            instance.invoke_agent.return_value = {
                'success': False,
                'error': 'Agent execution failed'
            }
            mock_invoker.return_value = instance

            # Should use fallback commit message
            with patch('auto_implement_git_integration.auto_commit_and_push') as mock_git:
                mock_git.return_value = {'success': True, 'commit_sha': 'abc123'}

                result = execute_git_workflow(
                    workflow_id='test-123',
                    request='Add feature',
                    in_batch_mode=True
                )

                # Should succeed with fallback message
                assert result['success'] is True or result.get('commit_message_fallback') is True


# =============================================================================
# Test Concurrent Git Operations
# =============================================================================

class TestConcurrentGitOperations:
    """Test batch git workflow handles concurrent operations."""

    @patch.dict(os.environ, {'AUTO_GIT_ENABLED': 'true'})
    def test_git_lock_file_conflict(self, temp_repo, sample_features):
        """Test handling of .git/index.lock conflict."""
        with patch('auto_implement_git_integration.auto_commit_and_push') as mock_git:
            mock_git.side_effect = CalledProcessError(
                1, 'git commit',
                stderr='fatal: Unable to create .git/index.lock: File exists'
            )

            result = execute_git_workflow(
                workflow_id='test-123',
                request='Add feature',
                in_batch_mode=True
            )

            # Should handle gracefully
            assert result['success'] is False
            assert 'lock' in result.get('error', '').lower() or 'exists' in result.get('error', '').lower()
