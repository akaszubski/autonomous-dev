# tests/integration/test_pr_workflow.py
"""
Integration tests for end-to-end PR creation workflow.

Tests workflow integration:
- validate_gh_prerequisites → get_current_branch → parse_commits → create_pull_request
- Error handling across function boundaries
- Issue linking from commit messages
- Draft PR workflow

Date: 2025-10-23
Workflow: 20251023_104242
Agent: test-master
"""

import pytest
from unittest.mock import patch, Mock
from subprocess import CalledProcessError
import sys
from pathlib import Path

# Add lib directory to path for imports
lib_dir = Path(__file__).parent.parent.parent / 'plugins' / 'autonomous-dev' / 'lib'
sys.path.insert(0, str(lib_dir))

try:
    from pr_automation import create_pull_request, validate_gh_prerequisites, get_current_branch, parse_commit_messages_for_issues
except ImportError as e:
    pytest.skip(f"Implementation not found (TDD red phase): {e}", allow_module_level=True)


class TestPRWorkflow:
    """End-to-end PR creation workflow tests."""

    @patch('subprocess.run')
    def test_end_to_end_pr_creation_success(self, mock_run):
        """Test complete workflow from validation to PR creation."""
        # Arrange: Mock all subprocess calls in correct order
        mock_run.side_effect = [
            Mock(returncode=0, stdout='gh version 2.40.0'),  # gh --version
            Mock(returncode=0, stdout='Logged in to github.com'),  # gh auth status
            Mock(returncode=0, stdout='* feature/pr-automation\n  main\n'),  # git branch
            Mock(returncode=0, stdout='commit abc\n\n    feat: add PR automation\n\n    Closes #42\n'),  # git log
            Mock(returncode=0, stdout='https://github.com/akaszubski/autonomous-dev/pull/42\n'),  # gh pr create
        ]

        # Act
        result = create_pull_request()

        # Assert
        assert result['success'] is True
        assert result['pr_number'] == 42
        assert result['pr_url'] == 'https://github.com/akaszubski/autonomous-dev/pull/42'
        assert result['linked_issues'] == [42]
        assert result['draft'] is True
        # Verify all validation steps executed
        assert mock_run.call_count >= 3  # At least: gh version, gh auth, git branch

    @patch('subprocess.run')
    def test_pr_creation_with_issue_linking(self, mock_run):
        """Test PR auto-links issues from commit messages."""
        # Arrange: Mock commits with multiple issue references
        mock_run.side_effect = [
            Mock(returncode=0, stdout='gh version 2.40.0'),
            Mock(returncode=0, stdout='Logged in'),
            Mock(returncode=0, stdout='* feature/test\n'),
            Mock(returncode=0, stdout='commit abc\n\n    Closes #42\n    Fixes #123\n    Resolves #456\n'),
            Mock(returncode=0, stdout='https://github.com/user/repo/pull/10\n'),
        ]

        # Act
        result = create_pull_request()

        # Assert
        assert result['success'] is True
        assert set(result['linked_issues']) == {42, 123, 456}

    @patch('subprocess.run')
    def test_pr_creation_fails_validation_early(self, mock_run):
        """Test workflow aborts if prerequisites not met."""
        # Arrange: gh not authenticated
        mock_run.side_effect = [
            Mock(returncode=0, stdout='gh version 2.40.0'),  # gh --version succeeds
            Mock(returncode=1, stderr='You are not logged into any GitHub hosts'),  # gh auth fails
        ]

        # Act
        result = create_pull_request()

        # Assert
        assert result['success'] is False
        assert 'not authenticated' in result['error'].lower()
        # Verify gh pr create NOT called (stopped after validation)
        assert mock_run.call_count == 2

    @patch('subprocess.run')
    def test_pr_creation_from_main_branch_fails(self, mock_run):
        """Test PR creation from main branch fails with clear error."""
        # Arrange: Current branch is main
        mock_run.side_effect = [
            Mock(returncode=0, stdout='gh version 2.40.0'),
            Mock(returncode=0, stdout='Logged in'),
            Mock(returncode=0, stdout='* main\n  feature/test\n'),  # On main branch!
        ]

        # Act & Assert
        with pytest.raises(ValueError, match='Cannot create PR from main'):
            create_pull_request()

        # Verify gh pr create NOT called
        assert mock_run.call_count == 3

    @patch('subprocess.run')
    def test_pr_creation_from_master_branch_fails(self, mock_run):
        """Test PR creation from master branch fails with clear error."""
        # Arrange: Current branch is master
        mock_run.side_effect = [
            Mock(returncode=0),
            Mock(returncode=0),
            Mock(returncode=0, stdout='* master\n'),  # On master branch!
        ]

        # Act & Assert
        with pytest.raises(ValueError, match='Cannot create PR from master'):
            create_pull_request()

    @patch('subprocess.run')
    def test_pr_creation_with_no_commits_fails(self, mock_run):
        """Test PR creation fails when no commits exist between base and head."""
        # Arrange: git log returns empty (no commits)
        mock_run.side_effect = [
            Mock(returncode=0),  # gh --version
            Mock(returncode=0),  # gh auth status
            Mock(returncode=0, stdout='* feature/test\n'),  # git branch
            Mock(returncode=0, stdout=''),  # git log (empty!)
        ]

        # Act & Assert
        with pytest.raises(ValueError, match='No commits found'):
            create_pull_request()

    @patch('subprocess.run')
    def test_pr_creation_with_reviewer_assignment(self, mock_run):
        """Test PR created with reviewer assigned."""
        # Arrange
        mock_run.side_effect = [
            Mock(returncode=0),  # gh --version
            Mock(returncode=0),  # gh auth status
            Mock(returncode=0, stdout='* feature/test\n'),  # git branch
            Mock(returncode=0, stdout='commit abc\n\n    test\n'),  # git log
            Mock(returncode=0, stdout='https://github.com/user/repo/pull/1\n'),  # gh pr create
        ]

        # Act
        result = create_pull_request(reviewer='alice')

        # Assert
        assert result['success'] is True
        # Verify --reviewer flag used in gh pr create call
        gh_pr_create_call = [call for call in mock_run.call_args_list if 'gh' in str(call) and 'pr' in str(call)]
        assert len(gh_pr_create_call) > 0
        call_str = str(gh_pr_create_call[-1])
        assert '--reviewer' in call_str
        assert 'alice' in call_str

    @patch('subprocess.run')
    def test_draft_pr_workflow(self, mock_run):
        """Test draft PR creation (default for autonomous workflow)."""
        # Arrange
        mock_run.side_effect = [
            Mock(returncode=0),
            Mock(returncode=0),
            Mock(returncode=0, stdout='* feature/test\n'),
            Mock(returncode=0, stdout='commit abc\n\n    test\n'),
            Mock(returncode=0, stdout='https://github.com/user/repo/pull/1\n'),
        ]

        # Act
        result = create_pull_request(draft=True)

        # Assert
        assert result['success'] is True
        assert result['draft'] is True
        # Verify --draft flag used
        gh_pr_create_call = str(mock_run.call_args_list[-1])
        assert '--draft' in gh_pr_create_call

    @patch('subprocess.run')
    def test_ready_pr_workflow(self, mock_run):
        """Test ready PR creation (not draft)."""
        # Arrange
        mock_run.side_effect = [
            Mock(returncode=0),
            Mock(returncode=0),
            Mock(returncode=0, stdout='* feature/test\n'),
            Mock(returncode=0, stdout='commit abc\n\n    test\n'),
            Mock(returncode=0, stdout='https://github.com/user/repo/pull/1\n'),
        ]

        # Act
        result = create_pull_request(draft=False)

        # Assert
        assert result['success'] is True
        assert result['draft'] is False
        # Verify --draft flag NOT used
        gh_pr_create_call = str(mock_run.call_args_list[-1])
        assert '--draft' not in gh_pr_create_call

    @patch('subprocess.run')
    def test_pr_creation_with_custom_title_body(self, mock_run):
        """Test custom title and body override --fill-verbose."""
        # Arrange
        mock_run.side_effect = [
            Mock(returncode=0),
            Mock(returncode=0),
            Mock(returncode=0, stdout='* feature/test\n'),
            Mock(returncode=0, stdout='commit abc\n\n    test\n'),
            Mock(returncode=0, stdout='https://github.com/user/repo/pull/1\n'),
        ]

        # Act
        result = create_pull_request(
            title='Custom PR Title',
            body='Custom PR body content'
        )

        # Assert
        assert result['success'] is True
        gh_pr_create_call = str(mock_run.call_args_list[-1])
        assert '--title' in gh_pr_create_call
        assert 'Custom PR Title' in gh_pr_create_call
        assert '--body' in gh_pr_create_call
        assert '--fill-verbose' not in gh_pr_create_call  # Should use custom, not auto-fill


class TestErrorHandling:
    """Test error handling across workflow boundaries."""

    @patch('subprocess.run')
    def test_network_timeout_during_pr_creation(self, mock_run):
        """Test graceful handling of network timeout."""
        # Arrange
        from subprocess import TimeoutExpired
        mock_run.side_effect = [
            Mock(returncode=0),
            Mock(returncode=0),
            Mock(returncode=0, stdout='* feature/test\n'),
            Mock(returncode=0, stdout='commit abc\n\n    test\n'),
            TimeoutExpired(cmd='gh pr create', timeout=30),  # Timeout!
        ]

        # Act
        result = create_pull_request()

        # Assert
        assert result['success'] is False
        assert 'timeout' in result['error'].lower()

    @patch('subprocess.run')
    def test_rate_limit_during_pr_creation(self, mock_run):
        """Test graceful handling of GitHub rate limit."""
        # Arrange
        mock_run.side_effect = [
            Mock(returncode=0),
            Mock(returncode=0),
            Mock(returncode=0, stdout='* feature/test\n'),
            Mock(returncode=0, stdout='commit abc\n\n    test\n'),
            CalledProcessError(
                returncode=1,
                cmd='gh pr create',
                stderr='GraphQL error: API rate limit exceeded'
            ),
        ]

        # Act
        result = create_pull_request()

        # Assert
        assert result['success'] is False
        assert 'rate limit' in result['error'].lower()
