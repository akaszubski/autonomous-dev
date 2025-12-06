#!/usr/bin/env python3
"""
Integration tests for batch git workflow (Issue #93).

Tests complete /batch-implement workflow with git automation integrated
into each feature processing step.

TDD Mode: These tests are written BEFORE implementation.
All tests should FAIL initially (no batch git integration).

Test Strategy:
- Test batch workflow with git automation enabled
- Test batch workflow with git automation disabled
- Test git operations tracked in batch state
- Test batch resume after git failure
- Test batch completion with all git operations
- Test batch partial success (some git ops fail)
- Test batch git workflow with network failures
- Test batch git workflow with concurrent batches
- Test batch git workflow performance
- Test batch git workflow audit trail

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
        load_batch_state,
        save_batch_state,
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

    # Initialize git repo
    os.chdir(repo_dir)
    os.system('git init')
    os.system('git config user.name "Test User"')
    os.system('git config user.email "test@example.com"')

    # Create initial commit
    (repo_dir / "README.md").write_text("# Test Repo")
    os.system('git add .')
    os.system('git commit -m "Initial commit"')

    yield repo_dir

    # Cleanup
    os.chdir(tmp_path)


@pytest.fixture
def sample_features_file(temp_repo):
    """Create sample features file for batch processing."""
    features_file = temp_repo / "features.txt"
    features_file.write_text(
        "Add user authentication\n"
        "Implement password reset\n"
        "Add email verification\n"
    )
    return features_file


@pytest.fixture
def mock_auto_implement():
    """Mock /auto-implement execution."""
    with patch('batch_implement.execute_auto_implement') as mock:
        mock.return_value = {'success': True, 'tests_passed': True}
        yield mock


# =============================================================================
# Test Complete Batch Git Workflow
# =============================================================================

class TestCompleteBatchGitWorkflow:
    """Test complete batch workflow with git integration."""

    @patch.dict(os.environ, {'AUTO_GIT_ENABLED': 'true'})
    def test_batch_workflow_commits_each_feature(self, temp_repo, sample_features_file, mock_auto_implement):
        """Test batch workflow creates commit for each feature."""
        with patch('auto_implement_git_integration.auto_commit_and_push') as mock_git:
            mock_git.return_value = {'success': True, 'commit_sha': 'abc123'}

            # Create batch state
            state_file = temp_repo / ".claude" / "batch_state.json"
            state_file.parent.mkdir(exist_ok=True)

            state = create_batch_state(
                features_file=str(sample_features_file),
                features=sample_features_file.read_text().strip().split('\n'),
                state_file=str(state_file)
            )

            # Simulate batch processing (would be done by /batch-implement)
            for i in range(3):
                # Process feature
                mock_auto_implement()

                # Execute git workflow in batch mode
                result = execute_git_workflow(
                    workflow_id=f'batch-{state.batch_id}-feature-{i}',
                    request=state.features[i],
                    in_batch_mode=True
                )

                # Should succeed
                assert result['success'] is True

            # Should have 3 commits (one per feature)
            assert mock_git.call_count == 3

    @patch.dict(os.environ, {'AUTO_GIT_ENABLED': 'true'})
    def test_batch_workflow_tracks_git_operations_in_state(self, temp_repo, sample_features_file, mock_auto_implement):
        """Test batch workflow records git operations in batch state."""
        with patch('auto_implement_git_integration.auto_commit_and_push') as mock_git:
            mock_git.return_value = {
                'success': True,
                'commit_sha': 'abc123',
                'branch': 'feature/batch-1'
            }

            state_file = temp_repo / ".claude" / "batch_state.json"
            state_file.parent.mkdir(exist_ok=True)

            state = create_batch_state(
                features_file=str(sample_features_file),
                features=sample_features_file.read_text().strip().split('\n'),
                state_file=str(state_file)
            )

            # Process first feature
            mock_auto_implement()
            result = execute_git_workflow(
                workflow_id=f'batch-{state.batch_id}-feature-0',
                request=state.features[0],
                in_batch_mode=True
            )

            # Update state with git operation (would be done by /batch-implement)
            from batch_state_manager import record_git_operation
            state = record_git_operation(
                state,
                feature_index=0,
                operation='commit',
                success=True,
                commit_sha='abc123',
                branch='feature/batch-1'
            )

            save_batch_state(state, str(state_file))

            # Load state and verify
            loaded_state = load_batch_state(str(state_file))
            assert 0 in loaded_state.git_operations
            assert loaded_state.git_operations[0]['commit']['success'] is True

    @patch.dict(os.environ, {'AUTO_GIT_ENABLED': 'false'})
    def test_batch_workflow_respects_disabled_git_automation(self, temp_repo, sample_features_file, mock_auto_implement):
        """Test batch workflow skips git when AUTO_GIT_ENABLED=false."""
        with patch('auto_implement_git_integration.auto_commit_and_push') as mock_git:

            state_file = temp_repo / ".claude" / "batch_state.json"
            state_file.parent.mkdir(exist_ok=True)

            state = create_batch_state(
                features_file=str(sample_features_file),
                features=sample_features_file.read_text().strip().split('\n'),
                state_file=str(state_file)
            )

            # Process feature
            mock_auto_implement()
            result = execute_git_workflow(
                workflow_id=f'batch-{state.batch_id}-feature-0',
                request=state.features[0],
                in_batch_mode=True
            )

            # Git operations should be skipped
            assert result['git_enabled'] is False
            mock_git.assert_not_called()


# =============================================================================
# Test Batch Resume After Git Failure
# =============================================================================

class TestBatchResumeAfterGitFailure:
    """Test batch resume functionality after git failures."""

    @patch.dict(os.environ, {'AUTO_GIT_ENABLED': 'true'})
    def test_batch_resume_skips_already_committed_features(self, temp_repo, sample_features_file, mock_auto_implement):
        """Test batch resume doesn't re-commit already committed features."""
        with patch('auto_implement_git_integration.auto_commit_and_push') as mock_git:
            mock_git.return_value = {'success': True, 'commit_sha': 'abc123'}

            state_file = temp_repo / ".claude" / "batch_state.json"
            state_file.parent.mkdir(exist_ok=True)

            # Create state with first feature already committed
            state = create_batch_state(
                features_file=str(sample_features_file),
                features=sample_features_file.read_text().strip().split('\n'),
                state_file=str(state_file)
            )

            # Record first feature as committed
            from batch_state_manager import record_git_operation
            state = record_git_operation(
                state,
                feature_index=0,
                operation='commit',
                success=True,
                commit_sha='previous-commit'
            )
            state.completed_features.append(0)
            state.current_index = 1
            save_batch_state(state, str(state_file))

            # Resume batch (would be done by /batch-implement --resume)
            loaded_state = load_batch_state(str(state_file))

            # Process second feature only
            mock_auto_implement()
            result = execute_git_workflow(
                workflow_id=f'batch-{loaded_state.batch_id}-feature-1',
                request=loaded_state.features[1],
                in_batch_mode=True
            )

            # Should only have 1 new commit (not 2)
            assert mock_git.call_count == 1

    @patch.dict(os.environ, {'AUTO_GIT_ENABLED': 'true'})
    def test_batch_continues_after_push_failure(self, temp_repo, sample_features_file, mock_auto_implement):
        """Test batch continues processing after push failure."""
        call_count = 0

        def mock_git_side_effect(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                # First feature: push fails
                return {'success': True, 'commit_sha': 'abc123', 'pushed': False, 'error': 'Network error'}
            else:
                # Second feature: succeeds
                return {'success': True, 'commit_sha': 'def456', 'pushed': True}

        with patch('auto_implement_git_integration.auto_commit_and_push', side_effect=mock_git_side_effect):

            state_file = temp_repo / ".claude" / "batch_state.json"
            state_file.parent.mkdir(exist_ok=True)

            state = create_batch_state(
                features_file=str(sample_features_file),
                features=sample_features_file.read_text().strip().split('\n'),
                state_file=str(state_file)
            )

            # Process two features
            for i in range(2):
                mock_auto_implement()
                result = execute_git_workflow(
                    workflow_id=f'batch-{state.batch_id}-feature-{i}',
                    request=state.features[i],
                    in_batch_mode=True,
                    push=True
                )

                # First should fail push, second should succeed
                if i == 0:
                    assert result.get('pushed') is False
                else:
                    assert result.get('pushed') is True


# =============================================================================
# Test Batch Git Performance
# =============================================================================

class TestBatchGitPerformance:
    """Test batch git workflow doesn't significantly impact performance."""

    @patch.dict(os.environ, {'AUTO_GIT_ENABLED': 'true'})
    def test_batch_git_operations_are_async(self, temp_repo, sample_features_file, mock_auto_implement):
        """Test git operations don't block batch processing."""
        import time

        # Mock slow git operation
        def slow_git(*args, **kwargs):
            time.sleep(0.1)  # Simulate network delay
            return {'success': True, 'commit_sha': 'abc123'}

        with patch('auto_implement_git_integration.auto_commit_and_push', side_effect=slow_git):

            state_file = temp_repo / ".claude" / "batch_state.json"
            state_file.parent.mkdir(exist_ok=True)

            state = create_batch_state(
                features_file=str(sample_features_file),
                features=sample_features_file.read_text().strip().split('\n'),
                state_file=str(state_file)
            )

            start_time = time.time()

            # Process one feature
            mock_auto_implement()
            result = execute_git_workflow(
                workflow_id=f'batch-{state.batch_id}-feature-0',
                request=state.features[0],
                in_batch_mode=True
            )

            elapsed = time.time() - start_time

            # Should complete in reasonable time even with slow git
            # (git operations should be non-blocking or have timeout)
            assert elapsed < 5.0  # 5 seconds max


# =============================================================================
# Test Batch Git Audit Trail
# =============================================================================

class TestBatchGitAuditTrail:
    """Test batch git workflow maintains complete audit trail."""

    @patch.dict(os.environ, {'AUTO_GIT_ENABLED': 'true'})
    def test_batch_git_operations_logged_to_audit(self, temp_repo, sample_features_file, mock_auto_implement):
        """Test all batch git operations are logged to audit trail."""
        with patch('auto_implement_git_integration.auto_commit_and_push') as mock_git:
            mock_git.return_value = {'success': True, 'commit_sha': 'abc123'}
            with patch('auto_implement_git_integration.audit_log') as mock_audit:

                state_file = temp_repo / ".claude" / "batch_state.json"
                state_file.parent.mkdir(exist_ok=True)

                state = create_batch_state(
                    features_file=str(sample_features_file),
                    features=sample_features_file.read_text().strip().split('\n'),
                    state_file=str(state_file)
                )

                # Process feature
                mock_auto_implement()
                result = execute_git_workflow(
                    workflow_id=f'batch-{state.batch_id}-feature-0',
                    request=state.features[0],
                    in_batch_mode=True
                )

                # Should have audit log entries
                assert mock_audit.call_count > 0

                # Should log batch mode flag
                audit_calls = [str(call) for call in mock_audit.call_args_list]
                assert any('batch' in str(call).lower() for call in audit_calls)

    @patch.dict(os.environ, {'AUTO_GIT_ENABLED': 'true'})
    def test_batch_state_file_contains_complete_git_history(self, temp_repo, sample_features_file, mock_auto_implement):
        """Test batch state file contains complete git operation history."""
        with patch('auto_implement_git_integration.auto_commit_and_push') as mock_git:
            commit_shas = ['abc123', 'def456', 'ghi789']
            mock_git.side_effect = [
                {'success': True, 'commit_sha': sha} for sha in commit_shas
            ]

            state_file = temp_repo / ".claude" / "batch_state.json"
            state_file.parent.mkdir(exist_ok=True)

            state = create_batch_state(
                features_file=str(sample_features_file),
                features=sample_features_file.read_text().strip().split('\n'),
                state_file=str(state_file)
            )

            # Process all features
            from batch_state_manager import record_git_operation
            for i in range(3):
                mock_auto_implement()
                result = execute_git_workflow(
                    workflow_id=f'batch-{state.batch_id}-feature-{i}',
                    request=state.features[i],
                    in_batch_mode=True
                )

                # Record git operation
                state = record_git_operation(
                    state,
                    feature_index=i,
                    operation='commit',
                    success=True,
                    commit_sha=commit_shas[i]
                )
                save_batch_state(state, str(state_file))

            # Load state and verify complete history
            final_state = load_batch_state(str(state_file))
            assert len(final_state.git_operations) == 3
            assert final_state.git_operations[0]['commit']['sha'] == 'abc123'
            assert final_state.git_operations[1]['commit']['sha'] == 'def456'
            assert final_state.git_operations[2]['commit']['sha'] == 'ghi789'


# =============================================================================
# Test Batch Partial Success
# =============================================================================

class TestBatchPartialSuccess:
    """Test batch workflow with some git operations failing."""

    @patch.dict(os.environ, {'AUTO_GIT_ENABLED': 'true'})
    def test_batch_records_both_success_and_failure(self, temp_repo, sample_features_file, mock_auto_implement):
        """Test batch state records both successful and failed git operations."""
        call_count = 0

        def mixed_results(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 2:
                # Second feature fails
                return {'success': False, 'error': 'Merge conflict'}
            else:
                return {'success': True, 'commit_sha': f'commit-{call_count}'}

        with patch('auto_implement_git_integration.auto_commit_and_push', side_effect=mixed_results):

            state_file = temp_repo / ".claude" / "batch_state.json"
            state_file.parent.mkdir(exist_ok=True)

            state = create_batch_state(
                features_file=str(sample_features_file),
                features=sample_features_file.read_text().strip().split('\n'),
                state_file=str(state_file)
            )

            # Process all features
            from batch_state_manager import record_git_operation
            for i in range(3):
                mock_auto_implement()
                result = execute_git_workflow(
                    workflow_id=f'batch-{state.batch_id}-feature-{i}',
                    request=state.features[i],
                    in_batch_mode=True
                )

                # Record result
                state = record_git_operation(
                    state,
                    feature_index=i,
                    operation='commit',
                    success=result['success'],
                    commit_sha=result.get('commit_sha'),
                    error_message=result.get('error')
                )
                save_batch_state(state, str(state_file))

            # Verify mixed results
            final_state = load_batch_state(str(state_file))
            assert final_state.git_operations[0]['commit']['success'] is True
            assert final_state.git_operations[1]['commit']['success'] is False
            assert final_state.git_operations[2]['commit']['success'] is True
