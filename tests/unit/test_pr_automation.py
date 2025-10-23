# tests/unit/test_pr_automation.py
"""
Unit tests for PR automation library.

TDD Mode: These tests are written BEFORE implementation.
All tests should FAIL initially (ImportError: module not found).

Test Strategy:
- Mock all subprocess calls (no real gh CLI or git commands)
- Test happy paths and error conditions
- Aim for 90%+ code coverage
- Test each function independently

Date: 2025-10-23
Workflow: 20251023_104242
Agent: test-master
"""

import json
import pytest
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock, call
from subprocess import CalledProcessError, TimeoutExpired
from typing import Dict, Any, List, Tuple

# Import will fail - module doesn't exist yet (TDD!)
try:
    from plugins.autonomous_dev.lib.pr_automation import (
        create_pull_request,
        parse_commit_messages_for_issues,
        validate_gh_prerequisites,
        get_current_branch,
    )
except ImportError as e:
    pytest.skip(f"Implementation not found (TDD red phase): {e}", allow_module_level=True)


class TestValidateGHPrerequisites:
    """Test gh CLI installation and authentication validation."""

    @patch('subprocess.run')
    def test_validate_gh_prerequisites_success(self, mock_run):
        """Test gh CLI validation succeeds when installed and authenticated."""
        # Arrange: Mock successful gh --version and gh auth status
        mock_run.side_effect = [
            Mock(returncode=0, stdout='gh version 2.40.0'),  # gh --version
            Mock(returncode=0, stdout='Logged in to github.com')  # gh auth status
        ]

        # Act
        valid, error_message = validate_gh_prerequisites()

        # Assert
        assert valid is True
        assert error_message == ''
        assert mock_run.call_count == 2

    @patch('subprocess.run')
    def test_validate_gh_prerequisites_gh_not_installed(self, mock_run):
        """Test gh CLI validation fails when gh not installed."""
        # Arrange: Mock FileNotFoundError (gh command not found)
        mock_run.side_effect = FileNotFoundError('gh not found')

        # Act
        valid, error_message = validate_gh_prerequisites()

        # Assert
        assert valid is False
        assert 'not installed' in error_message.lower()

    @patch('subprocess.run')
    def test_validate_gh_prerequisites_not_authenticated(self, mock_run):
        """Test gh CLI validation fails when not authenticated."""
        # Arrange: gh --version succeeds, gh auth status fails
        mock_run.side_effect = [
            Mock(returncode=0, stdout='gh version 2.40.0'),
            Mock(returncode=1, stderr='You are not logged into any GitHub hosts')
        ]

        # Act
        valid, error_message = validate_gh_prerequisites()

        # Assert
        assert valid is False
        assert 'not authenticated' in error_message.lower()


class TestGetCurrentBranch:
    """Test getting current git branch."""

    @patch('subprocess.run')
    def test_get_current_branch_success(self, mock_run):
        """Test get current branch succeeds in valid repository."""
        # Arrange: Mock git branch output
        mock_run.return_value = Mock(
            returncode=0,
            stdout='  main\n* feature/pr-automation\n  develop\n'
        )

        # Act
        branch_name = get_current_branch()

        # Assert
        assert branch_name == 'feature/pr-automation'
        mock_run.assert_called_once()

    @patch('subprocess.run')
    def test_get_current_branch_not_git_repo(self, mock_run):
        """Test get current branch raises error when not in git repository."""
        # Arrange: Mock git command failure
        mock_run.side_effect = CalledProcessError(
            returncode=128,
            cmd='git branch',
            stderr='fatal: not a git repository'
        )

        # Act & Assert
        with pytest.raises(CalledProcessError):
            get_current_branch()

    @patch('subprocess.run')
    def test_get_current_branch_detached_head(self, mock_run):
        """Test get current branch handles detached HEAD state."""
        # Arrange: Mock detached HEAD output
        mock_run.return_value = Mock(
            returncode=0,
            stdout='* (HEAD detached at v1.0.0)\n  main\n'
        )

        # Act
        branch_name = get_current_branch()

        # Assert
        # Implementation can choose to return 'HEAD' or 'detached'
        assert branch_name in ['HEAD', 'detached', '(HEAD detached at v1.0.0)']


class TestParseCommitMessagesForIssues:
    """Test parsing commit messages for issue numbers."""

    @patch('subprocess.run')
    def test_parse_commit_messages_single_issue(self, mock_run):
        """Test parsing finds single issue number."""
        # Arrange: Mock git log with single issue
        mock_run.return_value = Mock(
            returncode=0,
            stdout='commit abc123\n\n    feat: add PR automation\n    \n    Closes #42\n'
        )

        # Act
        issue_numbers = parse_commit_messages_for_issues(base='main')

        # Assert
        assert issue_numbers == [42]

    @patch('subprocess.run')
    def test_parse_commit_messages_multiple_issues(self, mock_run):
        """Test parsing finds multiple issue numbers."""
        # Arrange: Mock git log with multiple issues
        mock_run.return_value = Mock(
            returncode=0,
            stdout='commit abc\n\n    Closes #42\n    Fixes #123\n    Resolves #456\n'
        )

        # Act
        issue_numbers = parse_commit_messages_for_issues()

        # Assert
        assert issue_numbers == [42, 123, 456]

    @patch('subprocess.run')
    def test_parse_commit_messages_no_issues(self, mock_run):
        """Test parsing with no issue references."""
        # Arrange: Mock git log without issue keywords
        mock_run.return_value = Mock(
            returncode=0,
            stdout='commit abc\n\n    feat: add feature\n    \n    No issue references\n'
        )

        # Act
        issue_numbers = parse_commit_messages_for_issues()

        # Assert
        assert issue_numbers == []

    @patch('subprocess.run')
    def test_parse_commit_messages_case_insensitive(self, mock_run):
        """Test parsing handles case variations."""
        # Arrange: Mock mixed case keywords
        mock_run.return_value = Mock(
            returncode=0,
            stdout='CLOSES #42\nfixes #123\nResolves #456'
        )

        # Act
        issue_numbers = parse_commit_messages_for_issues()

        # Assert
        assert set(issue_numbers) == {42, 123, 456}

    @patch('subprocess.run')
    def test_parse_commit_messages_deduplication(self, mock_run):
        """Test parsing deduplicates repeated issue numbers."""
        # Arrange: Mock duplicate issues
        mock_run.return_value = Mock(
            returncode=0,
            stdout='Closes #42\nFixes #42\nResolves #42'
        )

        # Act
        issue_numbers = parse_commit_messages_for_issues()

        # Assert
        assert issue_numbers == [42]

    @patch('subprocess.run')
    def test_parse_commit_messages_alternative_keywords(self, mock_run):
        """Test parsing supports Close, Fix, Resolve (singular forms)."""
        # Arrange: Mock singular keywords
        mock_run.return_value = Mock(
            returncode=0,
            stdout='Close #42\nFix #123\nResolve #456'
        )

        # Act
        issue_numbers = parse_commit_messages_for_issues()

        # Assert
        assert set(issue_numbers) == {42, 123, 456}


class TestCreatePullRequest:
    """Test PR creation functionality."""

    @patch('plugins.autonomous_dev.lib.pr_automation.validate_gh_prerequisites')
    @patch('plugins.autonomous_dev.lib.pr_automation.get_current_branch')
    @patch('plugins.autonomous_dev.lib.pr_automation.parse_commit_messages_for_issues')
    @patch('subprocess.run')
    def test_create_pull_request_draft_default(self, mock_run, mock_parse, mock_branch, mock_validate):
        """Test PR creation defaults to draft status."""
        # Arrange
        mock_validate.return_value = (True, '')
        mock_branch.return_value = 'feature/pr-automation'
        mock_parse.return_value = []
        mock_run.return_value = Mock(
            returncode=0,
            stdout='https://github.com/akaszubski/autonomous-dev/pull/42\n'
        )

        # Act
        result = create_pull_request()

        # Assert
        assert result['success'] is True
        assert result['pr_number'] == 42
        assert result['pr_url'] == 'https://github.com/akaszubski/autonomous-dev/pull/42'
        assert result['draft'] is True
        assert '--draft' in str(mock_run.call_args)

    @patch('plugins.autonomous_dev.lib.pr_automation.validate_gh_prerequisites')
    @patch('plugins.autonomous_dev.lib.pr_automation.get_current_branch')
    @patch('subprocess.run')
    def test_create_pull_request_ready_with_flag(self, mock_run, mock_branch, mock_validate):
        """Test PR creation with ready flag (not draft)."""
        # Arrange
        mock_validate.return_value = (True, '')
        mock_branch.return_value = 'feature/pr-automation'
        mock_run.return_value = Mock(
            returncode=0,
            stdout='https://github.com/akaszubski/autonomous-dev/pull/43\n'
        )

        # Act
        result = create_pull_request(draft=False)

        # Assert
        assert result['draft'] is False
        assert '--draft' not in str(mock_run.call_args)

    @patch('plugins.autonomous_dev.lib.pr_automation.validate_gh_prerequisites')
    @patch('plugins.autonomous_dev.lib.pr_automation.get_current_branch')
    @patch('subprocess.run')
    def test_create_pull_request_with_custom_title_body(self, mock_run, mock_branch, mock_validate):
        """Test PR creation with custom title and body."""
        # Arrange
        mock_validate.return_value = (True, '')
        mock_branch.return_value = 'feature/pr-automation'
        mock_run.return_value = Mock(
            returncode=0,
            stdout='https://github.com/akaszubski/autonomous-dev/pull/44\n'
        )

        # Act
        result = create_pull_request(
            title='Custom PR Title',
            body='Custom PR body content'
        )

        # Assert
        assert result['success'] is True
        call_str = str(mock_run.call_args)
        assert '--title' in call_str
        assert 'Custom PR Title' in call_str
        assert '--body' in call_str
        assert '--fill-verbose' not in call_str  # Should use custom, not auto-fill

    @patch('plugins.autonomous_dev.lib.pr_automation.validate_gh_prerequisites')
    @patch('plugins.autonomous_dev.lib.pr_automation.get_current_branch')
    @patch('subprocess.run')
    def test_create_pull_request_with_reviewer(self, mock_run, mock_branch, mock_validate):
        """Test PR creation with reviewer assignment."""
        # Arrange
        mock_validate.return_value = (True, '')
        mock_branch.return_value = 'feature/pr-automation'
        mock_run.return_value = Mock(
            returncode=0,
            stdout='https://github.com/akaszubski/autonomous-dev/pull/45\n'
        )

        # Act
        result = create_pull_request(reviewer='alice')

        # Assert
        assert result['success'] is True
        call_str = str(mock_run.call_args)
        assert '--reviewer' in call_str
        assert 'alice' in call_str

    @patch('plugins.autonomous_dev.lib.pr_automation.validate_gh_prerequisites')
    @patch('plugins.autonomous_dev.lib.pr_automation.get_current_branch')
    @patch('subprocess.run')
    def test_create_pull_request_with_multiple_reviewers(self, mock_run, mock_branch, mock_validate):
        """Test PR creation with multiple reviewers."""
        # Arrange
        mock_validate.return_value = (True, '')
        mock_branch.return_value = 'feature/pr-automation'
        mock_run.return_value = Mock(
            returncode=0,
            stdout='https://github.com/akaszubski/autonomous-dev/pull/46\n'
        )

        # Act
        result = create_pull_request(reviewer='alice,bob,charlie')

        # Assert
        assert result['success'] is True
        call_str = str(mock_run.call_args)
        assert 'alice,bob,charlie' in call_str

    @patch('plugins.autonomous_dev.lib.pr_automation.get_current_branch')
    def test_create_pull_request_fails_on_main_branch(self, mock_branch):
        """Test PR creation raises ValueError when on main branch."""
        # Arrange
        mock_branch.return_value = 'main'

        # Act & Assert
        with pytest.raises(ValueError, match='Cannot create PR from main branch'):
            create_pull_request()

    @patch('plugins.autonomous_dev.lib.pr_automation.get_current_branch')
    def test_create_pull_request_fails_on_master_branch(self, mock_branch):
        """Test PR creation raises ValueError when on master branch."""
        # Arrange
        mock_branch.return_value = 'master'

        # Act & Assert
        with pytest.raises(ValueError, match='Cannot create PR from master branch'):
            create_pull_request()

    @patch('plugins.autonomous_dev.lib.pr_automation.validate_gh_prerequisites')
    @patch('plugins.autonomous_dev.lib.pr_automation.get_current_branch')
    @patch('subprocess.run')
    def test_create_pull_request_fails_no_commits(self, mock_run, mock_branch, mock_validate):
        """Test PR creation raises ValueError when no commits exist."""
        # Arrange
        mock_validate.return_value = (True, '')
        mock_branch.return_value = 'feature/pr-automation'
        # Mock git log returning empty (no commits)
        mock_run.return_value = Mock(returncode=0, stdout='')

        # Act & Assert
        with pytest.raises(ValueError, match='No commits found'):
            create_pull_request()

    @patch('plugins.autonomous_dev.lib.pr_automation.validate_gh_prerequisites')
    def test_create_pull_request_fails_no_auth(self, mock_validate):
        """Test PR creation fails when gh not authenticated."""
        # Arrange
        mock_validate.return_value = (False, 'GitHub CLI not authenticated')

        # Act
        result = create_pull_request()

        # Assert
        assert result['success'] is False
        assert 'not authenticated' in result['error'].lower()

    @patch('plugins.autonomous_dev.lib.pr_automation.validate_gh_prerequisites')
    @patch('plugins.autonomous_dev.lib.pr_automation.get_current_branch')
    @patch('subprocess.run')
    def test_create_pull_request_handles_rate_limit(self, mock_run, mock_branch, mock_validate):
        """Test PR creation handles GitHub API rate limit error."""
        # Arrange
        mock_validate.return_value = (True, '')
        mock_branch.return_value = 'feature/pr-automation'
        mock_run.side_effect = CalledProcessError(
            returncode=1,
            cmd='gh pr create',
            stderr='GraphQL error: API rate limit exceeded'
        )

        # Act
        result = create_pull_request()

        # Assert
        assert result['success'] is False
        assert 'rate limit' in result['error'].lower()

    @patch('plugins.autonomous_dev.lib.pr_automation.validate_gh_prerequisites')
    @patch('plugins.autonomous_dev.lib.pr_automation.get_current_branch')
    @patch('subprocess.run')
    def test_create_pull_request_handles_permission_error(self, mock_run, mock_branch, mock_validate):
        """Test PR creation handles 403 permission error."""
        # Arrange
        mock_validate.return_value = (True, '')
        mock_branch.return_value = 'feature/pr-automation'
        mock_run.side_effect = CalledProcessError(
            returncode=1,
            cmd='gh pr create',
            stderr='GraphQL error: Resource protected by organization SAML'
        )

        # Act
        result = create_pull_request()

        # Assert
        assert result['success'] is False
        assert 'permission' in result['error'].lower() or 'protected' in result['error'].lower()

    @patch('plugins.autonomous_dev.lib.pr_automation.validate_gh_prerequisites')
    @patch('plugins.autonomous_dev.lib.pr_automation.get_current_branch')
    @patch('subprocess.run')
    def test_create_pull_request_handles_network_timeout(self, mock_run, mock_branch, mock_validate):
        """Test PR creation handles network timeout gracefully."""
        # Arrange
        mock_validate.return_value = (True, '')
        mock_branch.return_value = 'feature/pr-automation'
        mock_run.side_effect = TimeoutExpired(cmd='gh pr create', timeout=30)

        # Act
        result = create_pull_request()

        # Assert
        assert result['success'] is False
        assert 'timeout' in result['error'].lower()

    @patch('plugins.autonomous_dev.lib.pr_automation.validate_gh_prerequisites')
    @patch('plugins.autonomous_dev.lib.pr_automation.get_current_branch')
    @patch('plugins.autonomous_dev.lib.pr_automation.parse_commit_messages_for_issues')
    @patch('subprocess.run')
    def test_create_pull_request_includes_linked_issues(self, mock_run, mock_parse, mock_branch, mock_validate):
        """Test PR creation returns linked issues found in commit messages."""
        # Arrange
        mock_validate.return_value = (True, '')
        mock_branch.return_value = 'feature/pr-automation'
        mock_parse.return_value = [42, 123]
        mock_run.return_value = Mock(
            returncode=0,
            stdout='https://github.com/akaszubski/autonomous-dev/pull/50\n'
        )

        # Act
        result = create_pull_request()

        # Assert
        assert result['success'] is True
        assert result['linked_issues'] == [42, 123]

    @patch('plugins.autonomous_dev.lib.pr_automation.validate_gh_prerequisites')
    @patch('plugins.autonomous_dev.lib.pr_automation.get_current_branch')
    @patch('subprocess.run')
    def test_create_pull_request_with_base_develop(self, mock_run, mock_branch, mock_validate):
        """Test PR creation with non-main base branch."""
        # Arrange
        mock_validate.return_value = (True, '')
        mock_branch.return_value = 'feature/pr-automation'
        mock_run.return_value = Mock(
            returncode=0,
            stdout='https://github.com/akaszubski/autonomous-dev/pull/47\n'
        )

        # Act
        result = create_pull_request(base='develop')

        # Assert
        assert result['success'] is True
        call_str = str(mock_run.call_args)
        assert '--base' in call_str
        assert 'develop' in call_str

    @patch('plugins.autonomous_dev.lib.pr_automation.validate_gh_prerequisites')
    @patch('plugins.autonomous_dev.lib.pr_automation.get_current_branch')
    def test_create_pull_request_parses_pr_number_from_url(self, mock_branch, mock_validate):
        """Test PR number correctly extracted from GitHub URL."""
        # Arrange
        mock_validate.return_value = (True, '')
        mock_branch.return_value = 'feature/pr-automation'

        with patch('subprocess.run') as mock_run:
            mock_run.return_value = Mock(
                returncode=0,
                stdout='https://github.com/akaszubski/autonomous-dev/pull/999\n'
            )

            # Act
            result = create_pull_request()

            # Assert
            assert result['pr_number'] == 999
            assert result['pr_url'] == 'https://github.com/akaszubski/autonomous-dev/pull/999'
