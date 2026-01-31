"""
Integration tests for /auto-implement Step 8: Agent-driven git automation.

TDD Mode: These tests are written BEFORE implementation.
All tests should FAIL initially (module not found or functions not implemented).

Test Strategy:
- Test integration between /auto-implement and commit-message-generator agent
- Test integration between /auto-implement and pr-description-generator agent
- Test consent-based workflow with environment variables
- Test graceful degradation when agents fail
- Test full pipeline: agents → git ops → PR creation

Critical Context:
- git_operations.py EXISTS (tested, secure)
- pr_automation.py EXISTS (tested, secure)
- commit-message-generator agent EXISTS
- pr-description-generator agent EXISTS
- MISSING: Integration layer between /auto-implement and these components

Date: 2025-11-05
Workflow: git_automation
Agent: test-master
Phase: TDD Red (tests written BEFORE implementation)
"""

import json
import os
import sys
import pytest
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock, call, ANY
from subprocess import CalledProcessError
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

# Import will fail - integration module doesn't exist yet (TDD!)
try:
    from auto_implement_git_integration import (
        execute_step8_git_operations,
        check_consent_via_env,
        invoke_commit_message_agent,
        invoke_pr_description_agent,
        create_commit_with_agent_message,
        push_and_create_pr,
    )
except ImportError as e:
    pytest.skip(f"Implementation not found (TDD red phase): {e}", allow_module_level=True)


class TestStep8AgentIntegration:
    """Test /auto-implement Step 8 with agent-driven git operations."""

    @patch('auto_implement_git_integration.invoke_commit_message_agent')
    @patch('auto_implement_git_integration.auto_commit_and_push')
    @patch.dict(os.environ, {'AUTO_GIT_ENABLED': 'true', 'AUTO_GIT_PUSH': 'true'})
    def test_step8_full_workflow_with_consent(self, mock_git_ops, mock_agent):
        """Test complete Step 8 workflow when consent is enabled via env vars."""
        # Arrange: Agent generates commit message
        mock_agent.return_value = {
            'success': True,
            'output': 'feat: add user authentication\n\nImplemented JWT-based auth with tests',
            'error': ''
        }

        # Mock git operations success
        mock_git_ops.return_value = {
            'success': True,
            'commit_sha': 'abc1234',
            'pushed': True,
            'error': ''
        }

        # Act: Execute Step 8
        result = execute_step8_git_operations(
            workflow_id='test-workflow-123',
            branch='feature/add-auth',
            request='Add user authentication'
        )

        # Assert: Agent invoked, commit created, pushed
        mock_agent.assert_called_once_with(
            workflow_id='test-workflow-123',
            request='Add user authentication'
        )
        mock_git_ops.assert_called_once()
        assert result['success'] is True
        assert result['commit_sha'] == 'abc1234'
        assert result['pushed'] is True
        assert result['agent_invoked'] is True

    @patch('auto_implement_git_integration.invoke_commit_message_agent')
    @patch.dict(os.environ, {'AUTO_GIT_ENABLED': 'false'}, clear=True)
    def test_step8_skips_when_consent_disabled(self, mock_agent):
        """Test Step 8 gracefully skips when AUTO_GIT_ENABLED=false."""
        # Arrange: Consent disabled
        # (environment variable set above)

        # Act: Execute Step 8
        result = execute_step8_git_operations(
            workflow_id='test-workflow-123',
            branch='main',
            request='Add feature'
        )

        # Assert: Agent not invoked, git ops skipped
        mock_agent.assert_not_called()
        assert result['success'] is True  # Success = gracefully skipped
        assert result['skipped'] is True
        assert result['reason'] == 'User consent not provided (AUTO_GIT_ENABLED=false)'
        assert result.get('commit_sha') == ''

    @patch('auto_implement_git_integration.invoke_commit_message_agent')
    @patch('auto_implement_git_integration.auto_commit_and_push')
    @patch.dict(os.environ, {'AUTO_GIT_ENABLED': 'true', 'AUTO_GIT_PUSH': 'false'})
    def test_step8_commits_but_does_not_push_when_partial_consent(self, mock_git_ops, mock_agent):
        """Test Step 8 commits locally but doesn't push when AUTO_GIT_PUSH=false."""
        # Arrange: Commit consent yes, push consent no
        mock_agent.return_value = {
            'success': True,
            'output': 'feat: add feature\n\nImplemented feature',
            'error': ''
        }

        mock_git_ops.return_value = {
            'success': True,
            'commit_sha': 'abc1234',
            'pushed': False,
            'error': ''
        }

        # Act
        result = execute_step8_git_operations(
            workflow_id='test-workflow-123',
            branch='main',
            request='Add feature'
        )

        # Assert: Committed but not pushed
        mock_agent.assert_called_once()
        mock_git_ops.assert_called_once_with(
            commit_message=ANY,
            branch='main',
            push=False  # Push disabled
        )
        assert result['success'] is True
        assert result['commit_sha'] == 'abc1234'
        assert result['pushed'] is False

    @patch('auto_implement_git_integration.invoke_commit_message_agent')
    @patch.dict(os.environ, {'AUTO_GIT_ENABLED': 'true'})
    def test_step8_handles_agent_failure_gracefully(self, mock_agent):
        """Test Step 8 handles commit-message-generator failure gracefully."""
        # Arrange: Agent fails
        mock_agent.return_value = {
            'success': False,
            'output': '',
            'error': 'Agent timeout: commit-message-generator did not respond'
        }

        # Act
        result = execute_step8_git_operations(
            workflow_id='test-workflow-123',
            branch='main',
            request='Add feature'
        )

        # Assert: Step 8 fails gracefully with helpful error
        assert result['success'] is False
        assert 'commit-message-generator' in result['error'].lower()
        assert 'timeout' in result['error'].lower()
        assert result.get('commit_sha') == ''
        assert result.get('fallback_available') is True  # Suggest manual commit

    @patch('auto_implement_git_integration.invoke_commit_message_agent')
    @patch('auto_implement_git_integration.auto_commit_and_push')
    @patch.dict(os.environ, {'AUTO_GIT_ENABLED': 'true', 'AUTO_GIT_PUSH': 'true'})
    def test_step8_handles_git_operation_failure_gracefully(self, mock_git_ops, mock_agent):
        """Test Step 8 handles git operation failure after agent succeeds."""
        # Arrange: Agent succeeds, git ops fail
        mock_agent.return_value = {
            'success': True,
            'output': 'feat: add feature',
            'error': ''
        }

        mock_git_ops.return_value = {
            'success': False,
            'commit_sha': '',
            'pushed': False,
            'error': 'fatal: not a git repository'
        }

        # Act
        result = execute_step8_git_operations(
            workflow_id='test-workflow-123',
            branch='main',
            request='Add feature'
        )

        # Assert: Step 8 reports git failure but preserves agent output
        assert result['success'] is False
        assert 'not a git repository' in result['error']
        assert result['commit_message_generated'] == 'feat: add feature'
        assert result['agent_succeeded'] is True
        assert result['git_succeeded'] is False

    @patch('auto_implement_git_integration.invoke_pr_description_agent')
    @patch('auto_implement_git_integration.create_pull_request')
    @patch.dict(os.environ, {'AUTO_GIT_ENABLED': 'true', 'AUTO_GIT_PUSH': 'true', 'AUTO_GIT_PR': 'true'})
    def test_step8_creates_pr_with_agent_description(self, mock_create_pr, mock_agent):
        """Test Step 8 creates PR using pr-description-generator agent output."""
        # Arrange: Agent generates PR description
        mock_agent.return_value = {
            'success': True,
            'output': '''## Summary
- Implemented user authentication
- Added JWT token management
- Created login/logout endpoints

## Test Plan
- [x] Unit tests for auth service
- [x] Integration tests for login flow
- [ ] Manual testing with production-like setup

Generated with Claude Code
''',
            'error': ''
        }

        mock_create_pr.return_value = {
            'success': True,
            'pr_url': 'https://github.com/user/repo/pull/42',
            'pr_number': 42,
            'error': ''
        }

        # Act: Create PR (after commit+push succeeded)
        result = push_and_create_pr(
            workflow_id='test-workflow-123',
            branch='feature/add-auth',
            base_branch='main',
            title='feat: add user authentication',
            commit_sha='abc1234'
        )

        # Assert: PR created with agent-generated description
        mock_agent.assert_called_once_with(
            workflow_id='test-workflow-123',
            branch='feature/add-auth'
        )
        mock_create_pr.assert_called_once()
        assert result['success'] is True
        assert result['pr_url'] == 'https://github.com/user/repo/pull/42'
        assert result['pr_number'] == 42
        assert result['agent_invoked'] is True

    @patch('auto_implement_git_integration.invoke_pr_description_agent')
    @patch('auto_implement_git_integration.create_pull_request')
    @patch.dict(os.environ, {'AUTO_GIT_ENABLED': 'true', 'AUTO_GIT_PUSH': 'true', 'AUTO_GIT_PR': 'false'})
    def test_step8_skips_pr_when_consent_not_given(self, mock_create_pr, mock_agent):
        """Test Step 8 skips PR creation when AUTO_GIT_PR=false."""
        # Arrange: PR consent disabled
        # (environment variable set above)

        # Act
        result = push_and_create_pr(
            workflow_id='test-workflow-123',
            branch='feature/add-auth',
            base_branch='main',
            title='feat: add user authentication',
            commit_sha='abc1234'
        )

        # Assert: PR skipped
        mock_agent.assert_not_called()
        mock_create_pr.assert_not_called()
        assert result['success'] is True
        assert result['skipped'] is True
        assert result['reason'] == 'User consent not provided (AUTO_GIT_PR=false)'

    @patch('auto_implement_git_integration.invoke_pr_description_agent')
    @patch.dict(os.environ, {'AUTO_GIT_ENABLED': 'true', 'AUTO_GIT_PUSH': 'true', 'AUTO_GIT_PR': 'true'})
    def test_step8_handles_pr_agent_failure_gracefully(self, mock_agent):
        """Test Step 8 provides fallback when pr-description-generator fails."""
        # Arrange: Agent fails
        mock_agent.return_value = {
            'success': False,
            'output': '',
            'error': 'Agent error: pr-description-generator crashed'
        }

        # Act
        result = push_and_create_pr(
            workflow_id='test-workflow-123',
            branch='feature/add-auth',
            base_branch='main',
            title='feat: add user authentication',
            commit_sha='abc1234'
        )

        # Assert: Provides fallback instructions
        assert result['success'] is False
        assert 'pr-description-generator' in result['error'].lower()
        assert result.get('fallback_command') is not None
        assert 'gh pr create' in result['fallback_command']


class TestConsentManagement:
    """Test consent management via environment variables."""

    @patch.dict(os.environ, {'AUTO_GIT_ENABLED': 'true', 'AUTO_GIT_PUSH': 'true', 'AUTO_GIT_PR': 'true'})
    def test_check_consent_all_enabled(self):
        """Test consent check returns all permissions when env vars set to true."""
        # Act
        consent = check_consent_via_env()

        # Assert
        assert consent['git_enabled'] is True
        assert consent['push_enabled'] is True
        assert consent['pr_enabled'] is True
        assert consent['all_enabled'] is True

    @patch.dict(os.environ, {'AUTO_GIT_ENABLED': 'false'}, clear=True)
    def test_check_consent_git_disabled(self):
        """Test consent check returns disabled when AUTO_GIT_ENABLED=false."""
        # Act
        consent = check_consent_via_env()

        # Assert
        assert consent['git_enabled'] is False
        assert consent['push_enabled'] is False
        assert consent['pr_enabled'] is False
        assert consent['all_enabled'] is False

    @patch.dict(os.environ, {'AUTO_GIT_ENABLED': 'true', 'AUTO_GIT_PUSH': 'false'}, clear=True)
    def test_check_consent_partial_enabled(self):
        """Test consent check handles partial permissions."""
        # Act
        consent = check_consent_via_env()

        # Assert
        assert consent['git_enabled'] is True
        assert consent['push_enabled'] is False
        assert consent['pr_enabled'] is False  # PR requires push
        assert consent['all_enabled'] is False

    @patch.dict(os.environ, {}, clear=True)
    def test_check_consent_no_env_vars_defaults_to_disabled(self):
        """Test consent defaults to disabled when no env vars set."""
        # Act
        consent = check_consent_via_env()

        # Assert: Safe default = disabled
        assert consent['git_enabled'] is False
        assert consent['push_enabled'] is False
        assert consent['pr_enabled'] is False

    @patch.dict(os.environ, {'AUTO_GIT_ENABLED': 'yes', 'AUTO_GIT_PUSH': '1', 'AUTO_GIT_PR': 'YES'})
    def test_check_consent_accepts_various_truthy_values(self):
        """Test consent accepts various truthy values (yes, 1, YES, True)."""
        # Act
        consent = check_consent_via_env()

        # Assert: All variations of "true" accepted
        assert consent['git_enabled'] is True
        assert consent['push_enabled'] is True
        assert consent['pr_enabled'] is True

    @patch.dict(os.environ, {'AUTO_GIT_ENABLED': 'invalid', 'AUTO_GIT_PUSH': '0', 'AUTO_GIT_PR': ''})
    def test_check_consent_rejects_falsy_values(self):
        """Test consent rejects falsy/invalid values."""
        # Act
        consent = check_consent_via_env()

        # Assert: All non-truthy values rejected
        assert consent['git_enabled'] is False
        assert consent['push_enabled'] is False
        assert consent['pr_enabled'] is False


class TestAgentInvocation:
    """Test agent invocation for commit messages and PR descriptions."""

    @patch('auto_implement_git_integration.AgentInvoker')
    @patch('auto_implement_git_integration.ArtifactManager')
    def test_invoke_commit_message_agent_success(self, mock_artifact_mgr, mock_agent_invoker):
        """Test successful invocation of commit-message-generator agent."""
        # Arrange: Mock agent invoker
        mock_invoker_instance = MagicMock()
        mock_agent_invoker.return_value = mock_invoker_instance

        mock_invoker_instance.invoke.return_value = {
            'success': True,
            'output': 'feat: add user authentication\n\nImplemented JWT-based auth',
            'error': ''
        }

        # Act
        result = invoke_commit_message_agent(
            workflow_id='test-workflow-123',
            request='Add user authentication'
        )

        # Assert
        mock_invoker_instance.invoke.assert_called_once_with(
            'commit-message-generator',
            'test-workflow-123',
            request='Add user authentication'
        )
        assert result['success'] is True
        assert 'feat: add user authentication' in result['output']

    @patch('auto_implement_git_integration.AgentInvoker')
    @patch('auto_implement_git_integration.ArtifactManager')
    def test_invoke_pr_description_agent_success(self, mock_artifact_mgr, mock_agent_invoker):
        """Test successful invocation of pr-description-generator agent."""
        # Arrange: Mock agent invoker
        mock_invoker_instance = MagicMock()
        mock_agent_invoker.return_value = mock_invoker_instance

        mock_invoker_instance.invoke.return_value = {
            'success': True,
            'output': '''## Summary
- Implemented user authentication

## Test Plan
- [x] Unit tests
- [x] Integration tests
''',
            'error': ''
        }

        # Act
        result = invoke_pr_description_agent(
            workflow_id='test-workflow-123',
            branch='feature/add-auth'
        )

        # Assert
        mock_invoker_instance.invoke.assert_called_once_with(
            'pr-description-generator',
            'test-workflow-123',
            branch='feature/add-auth'
        )
        assert result['success'] is True
        assert '## Summary' in result['output']

    @patch('auto_implement_git_integration.AgentInvoker')
    @patch('auto_implement_git_integration.ArtifactManager')
    def test_invoke_agent_handles_timeout(self, mock_artifact_mgr, mock_agent_invoker):
        """Test agent invocation handles timeout gracefully."""
        # Arrange: Agent times out
        mock_invoker_instance = MagicMock()
        mock_agent_invoker.return_value = mock_invoker_instance

        mock_invoker_instance.invoke.side_effect = TimeoutError('Agent did not respond within 30s')

        # Act
        result = invoke_commit_message_agent(
            workflow_id='test-workflow-123',
            request='Add feature'
        )

        # Assert
        assert result['success'] is False
        assert 'timeout' in result['error'].lower()
        assert result['output'] == ''

    @patch('auto_implement_git_integration.AgentInvoker')
    @patch('auto_implement_git_integration.ArtifactManager')
    def test_invoke_agent_handles_missing_artifacts(self, mock_artifact_mgr, mock_agent_invoker):
        """Test agent invocation handles missing required artifacts."""
        # Arrange: Artifact manager can't find required artifacts
        mock_artifact_mgr_instance = MagicMock()
        mock_artifact_mgr.return_value = mock_artifact_mgr_instance

        mock_artifact_mgr_instance.read_artifact.side_effect = FileNotFoundError('manifest.json not found')

        # Act
        result = invoke_commit_message_agent(
            workflow_id='test-workflow-123',
            request='Add feature'
        )

        # Assert
        assert result['success'] is False
        assert 'manifest' in result['error'].lower()
        assert 'not found' in result['error'].lower()


class TestGracefulDegradation:
    """Test graceful degradation when components fail."""

    @patch('auto_implement_git_integration.invoke_commit_message_agent')
    @patch('auto_implement_git_integration.auto_commit_and_push')
    @patch.dict(os.environ, {'AUTO_GIT_ENABLED': 'true'})
    def test_step8_provides_manual_instructions_on_failure(self, mock_git_ops, mock_agent):
        """Test Step 8 provides manual git instructions when automation fails."""
        # Arrange: Both agent and git ops fail
        mock_agent.return_value = {
            'success': False,
            'output': '',
            'error': 'Agent failed'
        }

        # Act
        result = execute_step8_git_operations(
            workflow_id='test-workflow-123',
            branch='main',
            request='Add feature'
        )

        # Assert: Provides manual instructions
        assert result['success'] is False
        assert result.get('manual_instructions') is not None
        assert 'git add' in result['manual_instructions']
        assert 'git commit' in result['manual_instructions']

    @patch('auto_implement_git_integration.check_git_available')
    @patch.dict(os.environ, {'AUTO_GIT_ENABLED': 'true'})
    def test_step8_gracefully_handles_no_git_cli(self, mock_check_git):
        """Test Step 8 handles missing git CLI gracefully."""
        # Arrange: git not installed
        mock_check_git.return_value = False

        # Act
        result = execute_step8_git_operations(
            workflow_id='test-workflow-123',
            branch='main',
            request='Add feature'
        )

        # Assert
        assert result['success'] is False
        assert result['error'] == 'git CLI not available'
        assert result.get('install_instructions') is not None
        assert 'install git' in result['install_instructions'].lower()

    @patch('auto_implement_git_integration.invoke_pr_description_agent')
    @patch('auto_implement_git_integration.create_pull_request')
    @patch.dict(os.environ, {'AUTO_GIT_ENABLED': 'true', 'AUTO_GIT_PUSH': 'true', 'AUTO_GIT_PR': 'true'})
    def test_step8_provides_fallback_pr_command_on_agent_failure(self, mock_create_pr, mock_agent):
        """Test Step 8 provides gh pr create command when agent fails."""
        # Arrange: Agent fails
        mock_agent.return_value = {
            'success': False,
            'output': '',
            'error': 'Agent failed'
        }

        # Act
        result = push_and_create_pr(
            workflow_id='test-workflow-123',
            branch='feature/add-auth',
            base_branch='main',
            title='feat: add user authentication',
            commit_sha='abc1234'
        )

        # Assert: Provides fallback command
        assert result['success'] is False
        assert result.get('fallback_command') is not None
        assert result['fallback_command'].startswith('gh pr create')
        assert '--title' in result['fallback_command']
        assert '--base main' in result['fallback_command']
        assert '--head feature/add-auth' in result['fallback_command']


class TestFullPipeline:
    """Test complete pipeline: agents → git ops → PR creation."""

    @patch('auto_implement_git_integration.invoke_commit_message_agent')
    @patch('auto_implement_git_integration.invoke_pr_description_agent')
    @patch('auto_implement_git_integration.auto_commit_and_push')
    @patch('auto_implement_git_integration.create_pull_request')
    @patch.dict(os.environ, {'AUTO_GIT_ENABLED': 'true', 'AUTO_GIT_PUSH': 'true', 'AUTO_GIT_PR': 'true'})
    def test_full_pipeline_success(self, mock_create_pr, mock_git_ops, mock_pr_agent, mock_commit_agent):
        """Test complete successful pipeline from agents to PR."""
        # Arrange: All components succeed
        mock_commit_agent.return_value = {
            'success': True,
            'output': 'feat: add user authentication\n\nImplemented JWT-based auth',
            'error': ''
        }

        mock_git_ops.return_value = {
            'success': True,
            'commit_sha': 'abc1234',
            'pushed': True,
            'error': ''
        }

        mock_pr_agent.return_value = {
            'success': True,
            'output': '## Summary\n- Implemented user authentication',
            'error': ''
        }

        mock_create_pr.return_value = {
            'success': True,
            'pr_url': 'https://github.com/user/repo/pull/42',
            'pr_number': 42,
            'error': ''
        }

        # Act: Execute full Step 8
        result = execute_step8_git_operations(
            workflow_id='test-workflow-123',
            branch='feature/add-auth',
            request='Add user authentication',
            create_pr=True
        )

        # Assert: All steps executed successfully
        mock_commit_agent.assert_called_once()
        mock_git_ops.assert_called_once()
        mock_pr_agent.assert_called_once()
        mock_create_pr.assert_called_once()

        assert result['success'] is True
        assert result['commit_sha'] == 'abc1234'
        assert result['pushed'] is True
        assert result['pr_created'] is True
        assert result['pr_url'] == 'https://github.com/user/repo/pull/42'

    @patch('auto_implement_git_integration.invoke_commit_message_agent')
    @patch('auto_implement_git_integration.auto_commit_and_push')
    @patch.dict(os.environ, {'AUTO_GIT_ENABLED': 'true', 'AUTO_GIT_PUSH': 'true', 'AUTO_GIT_PR': 'true'})
    def test_pipeline_stops_at_git_failure(self, mock_git_ops, mock_commit_agent):
        """Test pipeline stops gracefully when git operations fail."""
        # Arrange: Agent succeeds, git fails
        mock_commit_agent.return_value = {
            'success': True,
            'output': 'feat: add feature',
            'error': ''
        }

        mock_git_ops.return_value = {
            'success': False,
            'commit_sha': '',
            'pushed': False,
            'error': 'fatal: merge conflict detected'
        }

        # Act
        result = execute_step8_git_operations(
            workflow_id='test-workflow-123',
            branch='main',
            request='Add feature',
            create_pr=True
        )

        # Assert: Pipeline stopped at git failure
        assert result['success'] is False
        assert result['stage_failed'] == 'git_operations'
        assert 'merge conflict' in result['error']
        assert result.get('pr_created') is False  # PR not attempted

    @patch('auto_implement_git_integration.invoke_commit_message_agent')
    @patch('auto_implement_git_integration.invoke_pr_description_agent')
    @patch('auto_implement_git_integration.auto_commit_and_push')
    @patch('auto_implement_git_integration.create_pull_request')
    @patch.dict(os.environ, {'AUTO_GIT_ENABLED': 'true', 'AUTO_GIT_PUSH': 'true', 'AUTO_GIT_PR': 'true'})
    def test_pipeline_commits_successfully_even_if_pr_fails(self, mock_create_pr, mock_git_ops, mock_pr_agent, mock_commit_agent):
        """Test pipeline completes commit+push even if PR creation fails."""
        # Arrange: Commit and push succeed, PR fails
        mock_commit_agent.return_value = {
            'success': True,
            'output': 'feat: add feature',
            'error': ''
        }

        mock_git_ops.return_value = {
            'success': True,
            'commit_sha': 'abc1234',
            'pushed': True,
            'error': ''
        }

        mock_pr_agent.return_value = {
            'success': True,
            'output': '## Summary\n- Feature added',
            'error': ''
        }

        mock_create_pr.return_value = {
            'success': False,
            'pr_url': '',
            'pr_number': None,
            'error': 'gh: not authenticated'
        }

        # Act
        result = execute_step8_git_operations(
            workflow_id='test-workflow-123',
            branch='feature/add-feature',
            request='Add feature',
            create_pr=True
        )

        # Assert: Commit/push succeeded, PR failed gracefully
        assert result['success'] is True  # Overall success (commit worked)
        assert result['commit_sha'] == 'abc1234'
        assert result['pushed'] is True
        assert result['pr_created'] is False
        assert 'not authenticated' in result['pr_error']
        assert result.get('manual_pr_command') is not None  # Fallback provided


class TestErrorMessages:
    """Test error messages are helpful and actionable."""

    @patch('auto_implement_git_integration.invoke_commit_message_agent')
    @patch.dict(os.environ, {'AUTO_GIT_ENABLED': 'true'})
    def test_error_message_includes_context_and_next_steps(self, mock_agent):
        """Test error messages include what went wrong and what to do next."""
        # Arrange: Agent fails
        mock_agent.return_value = {
            'success': False,
            'output': '',
            'error': 'Agent timeout: commit-message-generator did not respond'
        }

        # Act
        result = execute_step8_git_operations(
            workflow_id='test-workflow-123',
            branch='main',
            request='Add feature'
        )

        # Assert: Error message is helpful
        assert result['success'] is False
        error_message = result['error']

        # Contains what went wrong
        assert 'commit-message-generator' in error_message.lower()
        assert 'timeout' in error_message.lower()

        # Contains next steps
        assert result.get('next_steps') is not None
        assert 'manual commit' in result['next_steps'].lower() or 'git commit' in result['next_steps']

    @patch.dict(os.environ, {'AUTO_GIT_ENABLED': 'false'}, clear=True)
    def test_skipped_message_explains_why_and_how_to_enable(self):
        """Test skipped operations explain why and how to enable."""
        # Act
        result = execute_step8_git_operations(
            workflow_id='test-workflow-123',
            branch='main',
            request='Add feature'
        )

        # Assert: Provides clear explanation
        assert result['success'] is True
        assert result['skipped'] is True

        # Explains why
        assert 'AUTO_GIT_ENABLED=false' in result['reason']

        # Explains how to enable
        assert result.get('how_to_enable') is not None
        assert 'export AUTO_GIT_ENABLED=true' in result['how_to_enable']


class TestIssue318ExecuteStep8RespectsAutoGitPR:
    """
    Integration test for Issue #318: execute_step8 respects AUTO_GIT_PR=false.

    End-to-end workflow test for complete Step 8 execution with AUTO_GIT_PR=false.
    Tests full pipeline: commit -> push -> (skip PR creation).

    TDD Mode: Written BEFORE implementation (RED phase).
    Test should FAIL until agent prompts and library are updated.

    Date: 2026-02-01
    Issue: #318
    Phase: TDD Red
    """

    @patch('auto_implement_git_integration.invoke_commit_message_agent')
    @patch('auto_implement_git_integration.invoke_pr_description_agent')
    @patch('auto_implement_git_integration.auto_commit_and_push')
    @patch.dict(os.environ, {'AUTO_GIT_ENABLED': 'true', 'AUTO_GIT_PUSH': 'true', 'AUTO_GIT_PR': 'false'})
    def test_execute_step8_respects_auto_git_pr_false(self, mock_git_ops, mock_pr_agent, mock_commit_agent):
        """
        Integration test: execute_step8 should commit+push but NOT create PR.

        Workflow when AUTO_GIT_PR=false:
        1. commit-message-generator agent invoked -> commit message generated
        2. auto_commit_and_push() called -> changes committed and pushed
        3. pr-description-generator agent NOT invoked (consent check fails)
        4. gh pr create NOT called
        5. User notified: "PR creation skipped (AUTO_GIT_PR=false)"
        6. Manual command provided: gh pr create --title "..." --base main

        Expected result:
        {
            'success': True,
            'commit_sha': 'abc1234',
            'pushed': True,
            'pr_created': False,
            'pr_skipped': True,
            'reason': 'User consent not provided (AUTO_GIT_PR=false)'
        }
        """
        # Arrange: Mock commit agent (should be invoked)
        mock_commit_agent.return_value = {
            'success': True,
            'output': 'feat: add user authentication\n\nImplemented JWT-based auth',
            'error': ''
        }

        # Mock git operations (should be invoked)
        mock_git_ops.return_value = {
            'success': True,
            'commit_sha': 'abc1234',
            'pushed': True,
            'error': ''
        }

        # Mock PR agent (should NOT be invoked)
        mock_pr_agent.return_value = {
            'success': True,
            'output': '## Summary\n- Added auth',
            'error': ''
        }

        # Act: Execute full Step 8 workflow
        result = execute_step8_git_operations(
            workflow_id='test-workflow-123',
            branch='feature/add-auth',
            request='Add user authentication',
            create_pr=True  # Request PR but should be skipped due to consent
        )

        # Assert: Commit and push succeeded
        mock_commit_agent.assert_called_once()
        mock_git_ops.assert_called_once()
        assert result['success'] is True
        assert result['commit_sha'] == 'abc1234'
        assert result['pushed'] is True

        # Assert: PR creation was skipped
        mock_pr_agent.assert_not_called()  # Agent should NOT be invoked
        assert result['pr_created'] is False

        # Assert: User notification provided
        assert result.get('pr_skipped') is True or result.get('skipped') is True
        if 'reason' in result:
            assert 'AUTO_GIT_PR=false' in result['reason']

    @patch('auto_implement_git_integration.invoke_commit_message_agent')
    @patch('auto_implement_git_integration.auto_commit_and_push')
    @patch('subprocess.run')
    @patch.dict(os.environ, {'AUTO_GIT_ENABLED': 'true', 'AUTO_GIT_PUSH': 'true', 'AUTO_GIT_PR': 'false'})
    def test_execute_step8_no_gh_pr_create_called(self, mock_run, mock_git_ops, mock_commit_agent):
        """
        Integration test: verify gh pr create is never called when AUTO_GIT_PR=false.

        This is the critical regression test - ensures agents don't bypass consent.
        """
        # Arrange: Mock successful commit workflow
        mock_commit_agent.return_value = {
            'success': True,
            'output': 'feat: add feature',
            'error': ''
        }

        mock_git_ops.return_value = {
            'success': True,
            'commit_sha': 'abc1234',
            'pushed': True,
            'error': ''
        }

        # Mock subprocess for any git operations
        mock_run.return_value = Mock(returncode=0, stdout='')

        # Act: Execute Step 8
        execute_step8_git_operations(
            workflow_id='test-workflow-123',
            branch='feature/test',
            request='Add feature',
            create_pr=True
        )

        # Assert: Verify gh pr create was NEVER called
        gh_pr_calls = [
            call for call in mock_run.call_args_list
            if 'gh' in str(call) and 'pr' in str(call) and 'create' in str(call)
        ]
        assert len(gh_pr_calls) == 0, (
            f"gh pr create should not be called when AUTO_GIT_PR=false, "
            f"but found {len(gh_pr_calls)} calls: {gh_pr_calls}"
        )

    @patch('auto_implement_git_integration.invoke_commit_message_agent')
    @patch('auto_implement_git_integration.invoke_pr_description_agent')
    @patch('auto_implement_git_integration.auto_commit_and_push')
    @patch.dict(os.environ, {'AUTO_GIT_ENABLED': 'true', 'AUTO_GIT_PUSH': 'true', 'AUTO_GIT_PR': 'true'})
    def test_execute_step8_creates_pr_when_enabled(self, mock_git_ops, mock_pr_agent, mock_commit_agent):
        """
        Integration test: verify PR creation still works when AUTO_GIT_PR=true.

        This ensures the fix doesn't break existing functionality.
        """
        # Arrange: Mock successful workflow
        mock_commit_agent.return_value = {
            'success': True,
            'output': 'feat: add feature',
            'error': ''
        }

        mock_git_ops.return_value = {
            'success': True,
            'commit_sha': 'abc1234',
            'pushed': True,
            'error': ''
        }

        mock_pr_agent.return_value = {
            'success': True,
            'output': '## Summary\n- Added feature',
            'error': ''
        }

        # Mock gh pr create success
        with patch('subprocess.run') as mock_run:
            mock_run.return_value = Mock(
                returncode=0,
                stdout='https://github.com/user/repo/pull/42\n'
            )

            # Act
            result = execute_step8_git_operations(
                workflow_id='test-workflow-123',
                branch='feature/test',
                request='Add feature',
                create_pr=True
            )

            # Assert: PR created successfully
            assert result['success'] is True
            assert result['pr_created'] is True
            mock_pr_agent.assert_called_once()

    @patch('auto_implement_git_integration.invoke_commit_message_agent')
    @patch('auto_implement_git_integration.auto_commit_and_push')
    @patch.dict(os.environ, {'AUTO_GIT_ENABLED': 'false', 'AUTO_GIT_PUSH': 'true', 'AUTO_GIT_PR': 'true'})
    def test_execute_step8_cascading_from_git_disabled(self, mock_git_ops, mock_commit_agent):
        """
        Integration test: verify cascading behavior when AUTO_GIT_ENABLED=false.

        If git is disabled, PR should also be disabled (cascading).
        """
        # Act
        result = execute_step8_git_operations(
            workflow_id='test-workflow-123',
            branch='feature/test',
            request='Add feature',
            create_pr=True
        )

        # Assert: Everything skipped due to git disabled
        assert result['success'] is True
        assert result['skipped'] is True
        assert result.get('pr_created') is False
        mock_commit_agent.assert_not_called()
        mock_git_ops.assert_not_called()

    @patch('auto_implement_git_integration.invoke_commit_message_agent')
    @patch('auto_implement_git_integration.auto_commit_and_push')
    @patch.dict(os.environ, {'AUTO_GIT_ENABLED': 'true', 'AUTO_GIT_PUSH': 'false', 'AUTO_GIT_PR': 'true'})
    def test_execute_step8_cascading_from_push_disabled(self, mock_git_ops, mock_commit_agent):
        """
        Integration test: verify cascading behavior when AUTO_GIT_PUSH=false.

        If push is disabled, PR should also be disabled (cascading).
        """
        # Arrange
        mock_commit_agent.return_value = {
            'success': True,
            'output': 'feat: add feature',
            'error': ''
        }

        mock_git_ops.return_value = {
            'success': True,
            'commit_sha': 'abc1234',
            'pushed': False,
            'error': ''
        }

        # Act
        result = execute_step8_git_operations(
            workflow_id='test-workflow-123',
            branch='feature/test',
            request='Add feature',
            create_pr=True
        )

        # Assert: Commit succeeded, push and PR skipped
        assert result['success'] is True
        assert result['commit_sha'] == 'abc1234'
        assert result['pushed'] is False
        assert result.get('pr_created') is False
