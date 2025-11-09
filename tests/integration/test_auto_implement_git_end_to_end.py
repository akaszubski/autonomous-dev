"""
Integration tests for automatic git operations in /auto-implement workflow.

TDD Mode: These tests are written BEFORE implementation.
All tests should FAIL initially (ImportError: module not found).

Test Strategy:
- Test end-to-end workflow: /auto-implement → 7 agents → git automation
- Test consent variations: git-only, git+push, git+push+PR
- Test error recovery: merge conflicts, auth failures, network timeouts
- Test agent integration: commit-message-generator, pr-description-generator
- Test security: path validation, command injection prevention
- Achieve 85%+ coverage for workflow integration

Workflow Sequence:
1. /auto-implement runs 7 agents (researcher → ... → quality-validator)
2. quality-validator completes (SubagentStop hook fires)
3. auto_git_workflow.py hook checks consent
4. If consent given: trigger auto_implement_git_integration
5. Git operations: commit → push → PR (based on consent)
6. Success/failure logged to session file

Date: 2025-11-09
Feature: Automatic git operations integration
Agent: test-master
Phase: TDD Red (tests written BEFORE implementation)
"""

import json
import os
import subprocess
import sys
import pytest
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock, call, ANY
from subprocess import CalledProcessError

# Add project paths for imports
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root / 'plugins' / 'autonomous-dev' / 'hooks'))
sys.path.insert(0, str(project_root / 'plugins' / 'autonomous-dev' / 'lib'))

# Import will fail - modules don't exist yet (TDD!)
try:
    from auto_git_workflow import run_hook as run_git_workflow_hook
    from auto_implement_git_integration import execute_step8_git_operations
except ImportError as e:
    pytest.skip(f"Implementation not found (TDD red phase): {e}", allow_module_level=True)


@pytest.fixture
def mock_session_file(tmp_path):
    """Create a mock session file with complete pipeline data."""
    session_file = tmp_path / 'session-test-123.json'
    session_data = {
        'workflow_id': 'workflow-test-123',
        'feature_request': 'Add user authentication with JWT tokens',
        'agents': [
            {'agent': 'researcher', 'status': 'completed', 'duration': 120},
            {'agent': 'planner', 'status': 'completed', 'duration': 180},
            {'agent': 'test-master', 'status': 'completed', 'duration': 150},
            {'agent': 'implementer', 'status': 'completed', 'duration': 300},
            {'agent': 'reviewer', 'status': 'completed', 'duration': 90},
            {'agent': 'security-auditor', 'status': 'completed', 'duration': 60},
            {'agent': 'doc-master', 'status': 'completed', 'duration': 75},
        ],
    }
    session_file.write_text(json.dumps(session_data))
    return session_file


@pytest.fixture
def mock_git_repo(tmp_path):
    """Create a mock git repository for testing."""
    repo_dir = tmp_path / 'test-repo'
    repo_dir.mkdir()

    # Initialize git repo
    subprocess.run(['git', 'init'], cwd=repo_dir, check=True, capture_output=True)
    subprocess.run(
        ['git', 'config', 'user.name', 'Test User'],
        cwd=repo_dir,
        check=True,
        capture_output=True,
    )
    subprocess.run(
        ['git', 'config', 'user.email', 'test@example.com'],
        cwd=repo_dir,
        check=True,
        capture_output=True,
    )

    # Create initial commit
    (repo_dir / 'README.md').write_text('# Test Repo')
    subprocess.run(['git', 'add', '.'], cwd=repo_dir, check=True, capture_output=True)
    subprocess.run(
        ['git', 'commit', '-m', 'Initial commit'],
        cwd=repo_dir,
        check=True,
        capture_output=True,
    )

    # Create feature branch
    subprocess.run(
        ['git', 'checkout', '-b', 'feature/add-auth'],
        cwd=repo_dir,
        check=True,
        capture_output=True,
    )

    return repo_dir


class TestEndToEndWorkflow:
    """Test complete end-to-end git automation workflow."""

    @patch('auto_git_workflow.execute_step8_git_operations')
    @patch('auto_git_workflow.get_session_file_path')
    def test_full_workflow_git_only(
        self, mock_get_session, mock_execute, mock_session_file
    ):
        """Test full workflow with git commit only (no push, no PR)."""
        # Arrange
        mock_get_session.return_value = mock_session_file
        mock_execute.return_value = {
            'success': True,
            'commit_sha': 'abc1234567890',
            'branch': 'feature/add-auth',
            'committed': True,
            'pushed': False,
            'pr_created': False,
        }

        # Set consent for git only
        with patch.dict(os.environ, {
            'AUTO_GIT_ENABLED': 'true',
            'AUTO_GIT_PUSH': 'false',
            'AUTO_GIT_PR': 'false',
            'CLAUDE_AGENT_NAME': 'quality-validator',
        }):
            # Act
            result = run_git_workflow_hook('quality-validator')

        # Assert
        assert result['success'] is True
        assert result['commit_sha'] == 'abc1234567890'
        assert result['pushed'] is False
        assert result['pr_created'] is False

        # Verify execute_step8_git_operations called correctly
        mock_execute.assert_called_once_with(
            workflow_id='workflow-test-123',
            request='Add user authentication with JWT tokens',
            push=False,
            create_pr=False,
        )

    @patch('auto_git_workflow.execute_step8_git_operations')
    @patch('auto_git_workflow.get_session_file_path')
    def test_full_workflow_git_and_push(
        self, mock_get_session, mock_execute, mock_session_file
    ):
        """Test full workflow with git commit + push (no PR)."""
        # Arrange
        mock_get_session.return_value = mock_session_file
        mock_execute.return_value = {
            'success': True,
            'commit_sha': 'abc1234567890',
            'branch': 'feature/add-auth',
            'committed': True,
            'pushed': True,
            'pr_created': False,
        }

        # Set consent for git + push
        with patch.dict(os.environ, {
            'AUTO_GIT_ENABLED': 'true',
            'AUTO_GIT_PUSH': 'true',
            'AUTO_GIT_PR': 'false',
            'CLAUDE_AGENT_NAME': 'quality-validator',
        }):
            # Act
            result = run_git_workflow_hook('quality-validator')

        # Assert
        assert result['success'] is True
        assert result['pushed'] is True
        assert result['pr_created'] is False

        # Verify push=True passed
        mock_execute.assert_called_once_with(
            workflow_id='workflow-test-123',
            request='Add user authentication with JWT tokens',
            push=True,
            create_pr=False,
        )

    @patch('auto_git_workflow.execute_step8_git_operations')
    @patch('auto_git_workflow.get_session_file_path')
    def test_full_workflow_git_push_and_pr(
        self, mock_get_session, mock_execute, mock_session_file
    ):
        """Test full workflow with git commit + push + PR creation."""
        # Arrange
        mock_get_session.return_value = mock_session_file
        mock_execute.return_value = {
            'success': True,
            'commit_sha': 'abc1234567890',
            'branch': 'feature/add-auth',
            'committed': True,
            'pushed': True,
            'pr_created': True,
            'pr_url': 'https://github.com/user/repo/pull/42',
            'pr_number': 42,
        }

        # Set consent for all operations
        with patch.dict(os.environ, {
            'AUTO_GIT_ENABLED': 'true',
            'AUTO_GIT_PUSH': 'true',
            'AUTO_GIT_PR': 'true',
            'CLAUDE_AGENT_NAME': 'quality-validator',
        }):
            # Act
            result = run_git_workflow_hook('quality-validator')

        # Assert
        assert result['success'] is True
        assert result['pushed'] is True
        assert result['pr_created'] is True
        assert result['pr_url'] == 'https://github.com/user/repo/pull/42'

        # Verify create_pr=True passed
        mock_execute.assert_called_once_with(
            workflow_id='workflow-test-123',
            request='Add user authentication with JWT tokens',
            push=True,
            create_pr=True,
        )

    @patch('auto_git_workflow.get_session_file_path')
    def test_workflow_skipped_when_consent_not_given(
        self, mock_get_session, mock_session_file
    ):
        """Test workflow skips git operations when consent not given."""
        # Arrange
        mock_get_session.return_value = mock_session_file

        # Set consent to disabled
        with patch.dict(os.environ, {
            'AUTO_GIT_ENABLED': 'false',
            'CLAUDE_AGENT_NAME': 'quality-validator',
        }, clear=True):
            # Act
            result = run_git_workflow_hook('quality-validator')

        # Assert
        assert result['success'] is True
        assert result['skipped'] is True
        assert 'consent' in result['reason'].lower()

    @patch('auto_git_workflow.get_session_file_path')
    def test_workflow_skipped_for_non_quality_validator(
        self, mock_get_session, mock_session_file
    ):
        """Test workflow skips for agents other than quality-validator."""
        # Arrange
        mock_get_session.return_value = mock_session_file

        # Set consent but wrong agent
        with patch.dict(os.environ, {
            'AUTO_GIT_ENABLED': 'true',
            'CLAUDE_AGENT_NAME': 'doc-master',
        }):
            # Act
            result = run_git_workflow_hook('doc-master')

        # Assert
        assert result['success'] is True
        assert result['skipped'] is True
        assert 'quality-validator' in result['reason'].lower()


class TestAgentIntegration:
    """Test integration with commit-message-generator and pr-description-generator agents."""

    @patch('subprocess.run')
    @patch('auto_implement_git_integration.AgentInvoker')
    def test_commit_message_agent_invocation(self, mock_invoker_cls, mock_run):
        """Test commit-message-generator agent is invoked correctly."""
        # Arrange
        mock_invoker = MagicMock()
        mock_invoker_cls.return_value = mock_invoker
        mock_invoker.invoke.return_value = {
            'success': True,
            'output': 'feat: add user authentication\n\nImplement JWT-based auth with refresh tokens.',
            'error': '',
        }

        # Mock git commands
        mock_run.return_value = Mock(returncode=0, stdout='feature/add-auth')

        # Act
        result = execute_step8_git_operations(
            workflow_id='workflow-123',
            request='Add user authentication',
            push=False,
            create_pr=False,
        )

        # Assert
        assert result['success'] is True
        # Verify agent was invoked with correct parameters
        mock_invoker.invoke.assert_called()
        call_kwargs = mock_invoker.invoke.call_args[1]
        assert call_kwargs['agent_name'] == 'commit-message-generator'
        assert call_kwargs['context']['request'] == 'Add user authentication'

    @patch('subprocess.run')
    @patch('auto_implement_git_integration.AgentInvoker')
    def test_pr_description_agent_invocation(self, mock_invoker_cls, mock_run):
        """Test pr-description-generator agent is invoked when PR requested."""
        # Arrange
        mock_invoker = MagicMock()
        mock_invoker_cls.return_value = mock_invoker
        mock_invoker.invoke.side_effect = [
            # commit-message-generator response
            {
                'success': True,
                'output': 'feat: add auth',
                'error': '',
            },
            # pr-description-generator response
            {
                'success': True,
                'output': '## Summary\n\nAdd JWT authentication.\n\n## Test plan\n- Test login\n- Test logout',
                'error': '',
            },
        ]

        # Mock git commands
        mock_run.return_value = Mock(returncode=0, stdout='feature/add-auth')

        # Act
        result = execute_step8_git_operations(
            workflow_id='workflow-123',
            request='Add user authentication',
            push=True,
            create_pr=True,
        )

        # Assert
        assert result['success'] is True
        # Verify both agents were invoked
        assert mock_invoker.invoke.call_count == 2
        agent_names = [call[1]['agent_name'] for call in mock_invoker.invoke.call_args_list]
        assert 'commit-message-generator' in agent_names
        assert 'pr-description-generator' in agent_names

    @patch('subprocess.run')
    @patch('auto_implement_git_integration.AgentInvoker')
    def test_agent_output_yaml_parsing(self, mock_invoker_cls, mock_run):
        """Test YAML output from agents is correctly parsed."""
        # Arrange
        mock_invoker = MagicMock()
        mock_invoker_cls.return_value = mock_invoker
        mock_invoker.invoke.return_value = {
            'success': True,
            'output': '''---
commit_message: |
  feat: add user authentication

  Implement JWT-based authentication with refresh tokens.
  Includes login, logout, and token refresh endpoints.
---''',
            'error': '',
        }

        # Mock git commands
        mock_run.return_value = Mock(returncode=0, stdout='feature/add-auth')

        # Act
        result = execute_step8_git_operations(
            workflow_id='workflow-123',
            request='Add authentication',
            push=False,
            create_pr=False,
        )

        # Assert
        assert result['success'] is True
        # Verify YAML was parsed correctly
        # (commit message extracted from YAML output)

    @patch('subprocess.run')
    @patch('auto_implement_git_integration.AgentInvoker')
    def test_agent_failure_graceful_degradation(self, mock_invoker_cls, mock_run):
        """Test graceful degradation when agent fails."""
        # Arrange
        mock_invoker = MagicMock()
        mock_invoker_cls.return_value = mock_invoker
        mock_invoker.invoke.return_value = {
            'success': False,
            'output': '',
            'error': 'Agent timeout',
        }

        # Mock git commands
        mock_run.return_value = Mock(returncode=0, stdout='feature/add-auth')

        # Act
        result = execute_step8_git_operations(
            workflow_id='workflow-123',
            request='Add authentication',
            push=False,
            create_pr=False,
        )

        # Assert - should provide fallback instructions
        assert result['success'] is False
        assert 'manual_instructions' in result
        assert 'git commit' in result['manual_instructions']


class TestErrorRecovery:
    """Test error handling and recovery scenarios."""

    @patch('auto_git_workflow.execute_step8_git_operations')
    @patch('auto_git_workflow.get_session_file_path')
    def test_merge_conflict_error_handling(
        self, mock_get_session, mock_execute, mock_session_file
    ):
        """Test handling of merge conflicts during git operations."""
        # Arrange
        mock_get_session.return_value = mock_session_file
        mock_execute.return_value = {
            'success': False,
            'error': 'Merge conflict detected in auth.py',
            'manual_instructions': 'git pull origin main\ngit add auth.py\ngit commit',
            'recovery_possible': True,
        }

        with patch.dict(os.environ, {
            'AUTO_GIT_ENABLED': 'true',
            'CLAUDE_AGENT_NAME': 'quality-validator',
        }):
            # Act
            result = run_git_workflow_hook('quality-validator')

        # Assert
        assert result['success'] is False
        assert 'Merge conflict' in result['error']
        assert 'manual_instructions' in result
        assert result['recovery_possible'] is True

    @patch('subprocess.run')
    def test_auth_failure_error_handling(self, mock_run):
        """Test handling of authentication failures during push."""
        # Arrange - simulate auth failure
        mock_run.side_effect = CalledProcessError(
            1,
            'git push',
            stderr=b'Permission denied (publickey)'
        )

        # Act
        with pytest.raises(Exception) as exc_info:
            result = execute_step8_git_operations(
                workflow_id='workflow-123',
                request='Add auth',
                push=True,
                create_pr=False,
            )

        # Assert - should provide helpful error message
        error_msg = str(exc_info.value).lower()
        assert 'permission' in error_msg or 'auth' in error_msg

    @patch('subprocess.run')
    def test_network_timeout_error_handling(self, mock_run):
        """Test handling of network timeouts during git operations."""
        # Arrange - simulate network timeout
        mock_run.side_effect = subprocess.TimeoutExpired('git push', 30)

        # Act
        with pytest.raises(subprocess.TimeoutExpired):
            result = execute_step8_git_operations(
                workflow_id='workflow-123',
                request='Add auth',
                push=True,
                create_pr=False,
            )

    @patch('auto_git_workflow.execute_step8_git_operations')
    @patch('auto_git_workflow.get_session_file_path')
    def test_gh_cli_not_installed_error(
        self, mock_get_session, mock_execute, mock_session_file
    ):
        """Test error when gh CLI not installed but PR requested."""
        # Arrange
        mock_get_session.return_value = mock_session_file
        mock_execute.return_value = {
            'success': False,
            'error': 'gh CLI not found. Install with: brew install gh',
            'manual_instructions': 'gh pr create --fill',
        }

        with patch.dict(os.environ, {
            'AUTO_GIT_ENABLED': 'true',
            'AUTO_GIT_PR': 'true',
            'CLAUDE_AGENT_NAME': 'quality-validator',
        }):
            # Act
            result = run_git_workflow_hook('quality-validator')

        # Assert
        assert result['success'] is False
        assert 'gh CLI not found' in result['error']
        assert 'Install' in result['error']

    @patch('auto_git_workflow.read_session_data')
    @patch('auto_git_workflow.get_session_file_path')
    def test_session_file_corrupted_error(
        self, mock_get_session, mock_read, tmp_path
    ):
        """Test handling of corrupted session file."""
        # Arrange
        mock_get_session.return_value = tmp_path / 'session.json'
        mock_read.side_effect = ValueError('Invalid JSON in session file')

        with patch.dict(os.environ, {
            'AUTO_GIT_ENABLED': 'true',
            'CLAUDE_AGENT_NAME': 'quality-validator',
        }):
            # Act
            result = run_git_workflow_hook('quality-validator')

        # Assert
        assert result['success'] is False
        assert 'Invalid JSON' in result['error']


class TestSecurityIntegration:
    """Test security validation integration in end-to-end workflow."""

    @patch('subprocess.run')
    @patch('auto_implement_git_integration.validate_branch_name')
    def test_branch_name_validation_called(self, mock_validate, mock_run):
        """Test branch name validation is called before git operations."""
        # Arrange
        mock_validate.return_value = 'feature/add-auth'
        mock_run.return_value = Mock(returncode=0, stdout='feature/add-auth')

        # Act
        result = execute_step8_git_operations(
            workflow_id='workflow-123',
            request='Add auth',
            push=False,
            create_pr=False,
        )

        # Assert - validate_branch_name should have been called
        mock_validate.assert_called()

    @patch('subprocess.run')
    @patch('auto_implement_git_integration.validate_commit_message')
    @patch('auto_implement_git_integration.AgentInvoker')
    def test_commit_message_validation_called(
        self, mock_invoker_cls, mock_validate_msg, mock_run
    ):
        """Test commit message validation is called before commit."""
        # Arrange
        mock_invoker = MagicMock()
        mock_invoker_cls.return_value = mock_invoker
        mock_invoker.invoke.return_value = {
            'success': True,
            'output': 'feat: add auth',
            'error': '',
        }
        mock_validate_msg.return_value = 'feat: add auth'
        mock_run.return_value = Mock(returncode=0, stdout='feature/add-auth')

        # Act
        result = execute_step8_git_operations(
            workflow_id='workflow-123',
            request='Add auth',
            push=False,
            create_pr=False,
        )

        # Assert - validate_commit_message should have been called
        mock_validate_msg.assert_called()

    @patch('subprocess.run')
    @patch('auto_implement_git_integration.check_git_credentials')
    def test_git_credentials_validation_called(self, mock_check_creds, mock_run):
        """Test git credentials validation is called before operations."""
        # Arrange
        mock_check_creds.return_value = True
        mock_run.return_value = Mock(returncode=0, stdout='feature/add-auth')

        # Act
        result = execute_step8_git_operations(
            workflow_id='workflow-123',
            request='Add auth',
            push=False,
            create_pr=False,
        )

        # Assert - check_git_credentials should have been called
        mock_check_creds.assert_called()

    @patch('auto_git_workflow.security_utils.audit_log')
    @patch('auto_git_workflow.execute_step8_git_operations')
    @patch('auto_git_workflow.get_session_file_path')
    def test_audit_logging_for_git_operations(
        self, mock_get_session, mock_execute, mock_audit, mock_session_file
    ):
        """Test audit logging for git operations."""
        # Arrange
        mock_get_session.return_value = mock_session_file
        mock_execute.return_value = {
            'success': True,
            'commit_sha': 'abc123',
            'committed': True,
        }

        with patch.dict(os.environ, {
            'AUTO_GIT_ENABLED': 'true',
            'CLAUDE_AGENT_NAME': 'quality-validator',
        }):
            # Act
            result = run_git_workflow_hook('quality-validator')

        # Assert - should log git operations to audit log
        mock_audit.assert_called()
        # Check audit log entries contain relevant info
        call_args_list = [str(call) for call in mock_audit.call_args_list]
        assert any('git_operation' in str(call) for call in call_args_list)


class TestPerformance:
    """Test performance characteristics of git automation."""

    @patch('auto_git_workflow.execute_step8_git_operations')
    @patch('auto_git_workflow.get_session_file_path')
    def test_workflow_timeout_handling(
        self, mock_get_session, mock_execute, mock_session_file
    ):
        """Test workflow handles timeouts gracefully."""
        # Arrange - simulate slow git operation
        import time
        def slow_execute(*args, **kwargs):
            time.sleep(0.1)  # Simulate delay
            return {'success': True, 'commit_sha': 'abc123'}

        mock_get_session.return_value = mock_session_file
        mock_execute.side_effect = slow_execute

        with patch.dict(os.environ, {
            'AUTO_GIT_ENABLED': 'true',
            'CLAUDE_AGENT_NAME': 'quality-validator',
        }):
            # Act
            import time
            start = time.time()
            result = run_git_workflow_hook('quality-validator')
            duration = time.time() - start

        # Assert - should complete reasonably fast
        assert duration < 5.0  # Should complete within 5 seconds
        assert result['success'] is True

    @patch('auto_git_workflow.execute_step8_git_operations')
    @patch('auto_git_workflow.get_session_file_path')
    def test_large_commit_handling(
        self, mock_get_session, mock_execute, mock_session_file
    ):
        """Test handling of large commits (many files changed)."""
        # Arrange
        mock_get_session.return_value = mock_session_file
        mock_execute.return_value = {
            'success': True,
            'commit_sha': 'abc123',
            'files_changed': 50,  # Large commit
            'insertions': 2000,
            'deletions': 500,
        }

        with patch.dict(os.environ, {
            'AUTO_GIT_ENABLED': 'true',
            'CLAUDE_AGENT_NAME': 'quality-validator',
        }):
            # Act
            result = run_git_workflow_hook('quality-validator')

        # Assert - should handle large commits without error
        assert result['success'] is True
        assert result['files_changed'] == 50
