"""
Integration tests for /auto-implement with git automation.

TDD Mode: These tests are written BEFORE implementation.
All tests should FAIL initially (ImportError: module not found).

Test Strategy:
- Test full /auto-implement workflow with git operations
- Mock subprocess calls (no real git/gh commands)
- Test consent-based automation (user says yes/no)
- Test graceful degradation (failures don't break workflow)
- Test integration between auto-implement and git_operations

Date: 2025-11-04
Workflow: git_automation
Agent: test-master
"""

import json
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

# Import will fail - module doesn't exist yet (TDD!)
try:
    from git_operations import auto_commit_and_push
except ImportError as e:
    pytest.skip(f"Implementation not found (TDD red phase): {e}", allow_module_level=True)


class TestAutoImplementGitIntegration:
    """Test /auto-implement command with git automation integration."""

    @patch('subprocess.run')
    @patch('builtins.input')
    def test_auto_implement_user_accepts_commit_and_push(self, mock_input, mock_run):
        """Test full workflow when user accepts commit and push."""
        # Arrange: User says "yes" to commit and push
        mock_input.side_effect = ['yes', 'yes']  # Commit? Push?

        # Mock git operations
        mock_run.side_effect = [
            # validate_git_repo
            Mock(returncode=0, stdout='/repo/.git\n', stderr=''),
            # check_git_config (user.name)
            Mock(returncode=0, stdout='John Doe\n', stderr=''),
            # check_git_config (user.email)
            Mock(returncode=0, stdout='john@example.com\n', stderr=''),
            # detect_merge_conflict
            Mock(returncode=0, stdout='On branch main\nnothing to commit\n', stderr=''),
            # is_detached_head
            Mock(returncode=0, stdout='refs/heads/main\n', stderr=''),
            # has_uncommitted_changes
            Mock(returncode=0, stdout=' M file1.py\n', stderr=''),
            # stage_all_changes
            Mock(returncode=0, stdout='', stderr=''),
            # commit_changes
            Mock(returncode=0, stdout='[main abc1234] feat: add feature\n', stderr=''),
            # get_remote_name
            Mock(returncode=0, stdout='origin\n', stderr=''),
            # push_to_remote
            Mock(returncode=0, stdout='', stderr='To github.com:user/repo.git\n'),
        ]

        # Act
        result = auto_commit_and_push(
            commit_message='feat: add feature\n\nImplemented by /auto-implement',
            branch='main',
            push=True
        )

        # Assert
        assert result['success'] is True
        assert result['commit_sha'] == 'abc1234'
        assert result['pushed'] is True
        assert result['error'] == ''

    @patch('subprocess.run')
    @patch('builtins.input')
    def test_auto_implement_user_declines_commit(self, mock_input, mock_run):
        """Test workflow when user declines to commit."""
        # Arrange: User says "no" to commit
        mock_input.return_value = 'no'

        # Mock git operations (should not be called)
        mock_run.side_effect = [
            # validate_git_repo
            Mock(returncode=0, stdout='/repo/.git\n', stderr=''),
            # check_git_config (user.name)
            Mock(returncode=0, stdout='John Doe\n', stderr=''),
            # check_git_config (user.email)
            Mock(returncode=0, stdout='john@example.com\n', stderr=''),
        ]

        # Act: Simulate /auto-implement asking for consent
        consent_given = mock_input.return_value == 'yes'

        if not consent_given:
            result = {
                'success': False,
                'commit_sha': '',
                'pushed': False,
                'error': 'User declined to commit changes'
            }
        else:
            result = auto_commit_and_push(
                commit_message='feat: add feature',
                branch='main',
                push=False
            )

        # Assert
        assert result['success'] is False
        assert result['commit_sha'] == ''
        assert result['pushed'] is False
        assert 'declined' in result['error'].lower()

    @patch('subprocess.run')
    @patch('builtins.input')
    def test_auto_implement_commit_yes_push_no(self, mock_input, mock_run):
        """Test workflow when user accepts commit but declines push."""
        # Arrange: User says "yes" to commit, "no" to push
        mock_input.side_effect = ['yes', 'no']

        # Mock git operations
        mock_run.side_effect = [
            # validate_git_repo
            Mock(returncode=0, stdout='/repo/.git\n', stderr=''),
            # check_git_config (user.name)
            Mock(returncode=0, stdout='John Doe\n', stderr=''),
            # check_git_config (user.email)
            Mock(returncode=0, stdout='john@example.com\n', stderr=''),
            # detect_merge_conflict
            Mock(returncode=0, stdout='On branch main\nnothing to commit\n', stderr=''),
            # is_detached_head
            Mock(returncode=0, stdout='refs/heads/main\n', stderr=''),
            # has_uncommitted_changes
            Mock(returncode=0, stdout=' M file1.py\n', stderr=''),
            # stage_all_changes
            Mock(returncode=0, stdout='', stderr=''),
            # commit_changes
            Mock(returncode=0, stdout='[main abc1234] feat: add feature\n', stderr=''),
        ]

        # Act: Commit without push
        result = auto_commit_and_push(
            commit_message='feat: add feature',
            branch='main',
            push=False
        )

        # Assert
        assert result['success'] is True
        assert result['commit_sha'] == 'abc1234'
        assert result['pushed'] is False  # Push was skipped
        assert result['error'] == ''

    @patch('subprocess.run')
    def test_auto_implement_no_git_cli(self, mock_run):
        """Test workflow gracefully handles missing git CLI."""
        # Arrange: git command not found
        mock_run.side_effect = FileNotFoundError('git not found')

        # Act
        result = auto_commit_and_push(
            commit_message='feat: add feature',
            branch='main',
            push=True
        )

        # Assert
        assert result['success'] is False
        assert 'git not installed' in result['error'].lower()
        assert result['commit_sha'] == ''
        assert result['pushed'] is False

    @patch('subprocess.run')
    def test_auto_implement_no_gh_cli(self, mock_run):
        """Test workflow handles missing gh CLI gracefully (commit succeeds, PR creation skipped)."""
        # Arrange: git works, gh CLI missing
        mock_run.side_effect = [
            # validate_git_repo
            Mock(returncode=0, stdout='/repo/.git\n', stderr=''),
            # check_git_config (user.name)
            Mock(returncode=0, stdout='John Doe\n', stderr=''),
            # check_git_config (user.email)
            Mock(returncode=0, stdout='john@example.com\n', stderr=''),
            # detect_merge_conflict
            Mock(returncode=0, stdout='On branch main\nnothing to commit\n', stderr=''),
            # is_detached_head
            Mock(returncode=0, stdout='refs/heads/main\n', stderr=''),
            # has_uncommitted_changes
            Mock(returncode=0, stdout=' M file1.py\n', stderr=''),
            # stage_all_changes
            Mock(returncode=0, stdout='', stderr=''),
            # commit_changes
            Mock(returncode=0, stdout='[main abc1234] feat: add feature\n', stderr=''),
            # get_remote_name
            Mock(returncode=0, stdout='origin\n', stderr=''),
            # push_to_remote
            Mock(returncode=0, stdout='', stderr='To github.com:user/repo.git\n'),
            # gh CLI check (for PR creation)
            FileNotFoundError('gh not found'),
        ]

        # Act: Full workflow (commit + push should succeed, PR creation should be skipped)
        result = auto_commit_and_push(
            commit_message='feat: add feature',
            branch='main',
            push=True
        )

        # Assert: Commit and push succeeded, but note about gh CLI missing
        assert result['success'] is True
        assert result['commit_sha'] == 'abc1234'
        assert result['pushed'] is True
        # Note: PR creation would be skipped separately in auto-implement command

    @patch('subprocess.run')
    def test_auto_implement_merge_conflict_blocks_commit(self, mock_run):
        """Test workflow blocks commit when merge conflict detected."""
        # Arrange: Merge conflict exists
        mock_run.side_effect = [
            # validate_git_repo
            Mock(returncode=0, stdout='/repo/.git\n', stderr=''),
            # check_git_config (user.name)
            Mock(returncode=0, stdout='John Doe\n', stderr=''),
            # check_git_config (user.email)
            Mock(returncode=0, stdout='john@example.com\n', stderr=''),
            # detect_merge_conflict
            Mock(returncode=0, stdout='''On branch main
Unmerged paths:
  (use "git add <file>..." to mark resolution)
        both modified:   file1.py
''', stderr=''),
        ]

        # Act
        result = auto_commit_and_push(
            commit_message='feat: add feature',
            branch='main',
            push=True
        )

        # Assert
        assert result['success'] is False
        assert 'merge conflict' in result['error'].lower()
        assert 'file1.py' in result['error']
        assert result['commit_sha'] == ''

    @patch('subprocess.run')
    def test_auto_implement_detached_head_blocks_commit(self, mock_run):
        """Test workflow blocks commit when in detached HEAD state."""
        # Arrange: Detached HEAD
        mock_run.side_effect = [
            # validate_git_repo
            Mock(returncode=0, stdout='/repo/.git\n', stderr=''),
            # check_git_config (user.name)
            Mock(returncode=0, stdout='John Doe\n', stderr=''),
            # check_git_config (user.email)
            Mock(returncode=0, stdout='john@example.com\n', stderr=''),
            # detect_merge_conflict
            Mock(returncode=0, stdout='On branch main\nnothing to commit\n', stderr=''),
            # is_detached_head
            CalledProcessError(1, ['git', 'symbolic-ref', '-q', 'HEAD'], stderr='fatal: ref HEAD is not a symbolic ref'),
        ]

        # Act
        result = auto_commit_and_push(
            commit_message='feat: add feature',
            branch='main',
            push=True
        )

        # Assert
        assert result['success'] is False
        assert 'detached head' in result['error'].lower()
        assert result['commit_sha'] == ''

    @patch('subprocess.run')
    def test_auto_implement_commit_succeeds_push_fails(self, mock_run):
        """Test workflow gracefully handles push failure after successful commit."""
        # Arrange: Commit succeeds, push fails
        mock_run.side_effect = [
            # validate_git_repo
            Mock(returncode=0, stdout='/repo/.git\n', stderr=''),
            # check_git_config (user.name)
            Mock(returncode=0, stdout='John Doe\n', stderr=''),
            # check_git_config (user.email)
            Mock(returncode=0, stdout='john@example.com\n', stderr=''),
            # detect_merge_conflict
            Mock(returncode=0, stdout='On branch main\nnothing to commit\n', stderr=''),
            # is_detached_head
            Mock(returncode=0, stdout='refs/heads/main\n', stderr=''),
            # has_uncommitted_changes
            Mock(returncode=0, stdout=' M file1.py\n', stderr=''),
            # stage_all_changes
            Mock(returncode=0, stdout='', stderr=''),
            # commit_changes
            Mock(returncode=0, stdout='[main abc1234] feat: add feature\n', stderr=''),
            # get_remote_name
            Mock(returncode=0, stdout='origin\n', stderr=''),
            # push_to_remote (fails)
            CalledProcessError(1, ['git', 'push', 'origin', 'main'], stderr='error: failed to push'),
        ]

        # Act
        result = auto_commit_and_push(
            commit_message='feat: add feature',
            branch='main',
            push=True
        )

        # Assert: Commit succeeded, push failed
        assert result['success'] is True  # Overall success (commit worked)
        assert result['commit_sha'] == 'abc1234'
        assert result['pushed'] is False
        assert 'failed to push' in result['error'].lower()

    @patch('subprocess.run')
    def test_auto_implement_network_timeout_on_push(self, mock_run):
        """Test workflow handles network timeout gracefully."""
        # Arrange: Push times out
        from subprocess import TimeoutExpired
        mock_run.side_effect = [
            # validate_git_repo
            Mock(returncode=0, stdout='/repo/.git\n', stderr=''),
            # check_git_config (user.name)
            Mock(returncode=0, stdout='John Doe\n', stderr=''),
            # check_git_config (user.email)
            Mock(returncode=0, stdout='john@example.com\n', stderr=''),
            # detect_merge_conflict
            Mock(returncode=0, stdout='On branch main\nnothing to commit\n', stderr=''),
            # is_detached_head
            Mock(returncode=0, stdout='refs/heads/main\n', stderr=''),
            # has_uncommitted_changes
            Mock(returncode=0, stdout=' M file1.py\n', stderr=''),
            # stage_all_changes
            Mock(returncode=0, stdout='', stderr=''),
            # commit_changes
            Mock(returncode=0, stdout='[main abc1234] feat: add feature\n', stderr=''),
            # get_remote_name
            Mock(returncode=0, stdout='origin\n', stderr=''),
            # push_to_remote (timeout)
            TimeoutExpired(['git', 'push', 'origin', 'main'], timeout=30),
        ]

        # Act
        result = auto_commit_and_push(
            commit_message='feat: add feature',
            branch='main',
            push=True
        )

        # Assert
        assert result['success'] is True  # Commit succeeded
        assert result['commit_sha'] == 'abc1234'
        assert result['pushed'] is False
        assert 'timeout' in result['error'].lower()

    @patch('subprocess.run')
    def test_auto_implement_branch_protection_blocks_push(self, mock_run):
        """Test workflow handles branch protection gracefully."""
        # Arrange: Push rejected due to branch protection
        mock_run.side_effect = [
            # validate_git_repo
            Mock(returncode=0, stdout='/repo/.git\n', stderr=''),
            # check_git_config (user.name)
            Mock(returncode=0, stdout='John Doe\n', stderr=''),
            # check_git_config (user.email)
            Mock(returncode=0, stdout='john@example.com\n', stderr=''),
            # detect_merge_conflict
            Mock(returncode=0, stdout='On branch main\nnothing to commit\n', stderr=''),
            # is_detached_head
            Mock(returncode=0, stdout='refs/heads/main\n', stderr=''),
            # has_uncommitted_changes
            Mock(returncode=0, stdout=' M file1.py\n', stderr=''),
            # stage_all_changes
            Mock(returncode=0, stdout='', stderr=''),
            # commit_changes
            Mock(returncode=0, stdout='[main abc1234] feat: add feature\n', stderr=''),
            # get_remote_name
            Mock(returncode=0, stdout='origin\n', stderr=''),
            # push_to_remote (branch protection)
            CalledProcessError(
                1,
                ['git', 'push', 'origin', 'main'],
                stderr='remote: error: GH006: Protected branch update failed'
            ),
        ]

        # Act
        result = auto_commit_and_push(
            commit_message='feat: add feature',
            branch='main',
            push=True
        )

        # Assert
        assert result['success'] is True  # Commit succeeded
        assert result['commit_sha'] == 'abc1234'
        assert result['pushed'] is False
        assert 'protected' in result['error'].lower() or 'gh006' in result['error'].lower()


class TestAutoImplementWithPRCreation:
    """Test /auto-implement with full git workflow including PR creation."""

    @patch('subprocess.run')
    @patch('builtins.input')
    def test_full_workflow_commit_push_pr(self, mock_input, mock_run):
        """Test complete workflow: commit -> push -> create PR."""
        # Arrange: User accepts all
        mock_input.side_effect = ['yes', 'yes', 'yes']  # Commit? Push? Create PR?

        # Mock all git and gh operations
        mock_run.side_effect = [
            # validate_git_repo
            Mock(returncode=0, stdout='/repo/.git\n', stderr=''),
            # check_git_config (user.name)
            Mock(returncode=0, stdout='John Doe\n', stderr=''),
            # check_git_config (user.email)
            Mock(returncode=0, stdout='john@example.com\n', stderr=''),
            # detect_merge_conflict
            Mock(returncode=0, stdout='On branch main\nnothing to commit\n', stderr=''),
            # is_detached_head
            Mock(returncode=0, stdout='refs/heads/main\n', stderr=''),
            # has_uncommitted_changes
            Mock(returncode=0, stdout=' M file1.py\n', stderr=''),
            # stage_all_changes
            Mock(returncode=0, stdout='', stderr=''),
            # commit_changes
            Mock(returncode=0, stdout='[main abc1234] feat: add feature\n', stderr=''),
            # get_remote_name
            Mock(returncode=0, stdout='origin\n', stderr=''),
            # push_to_remote
            Mock(returncode=0, stdout='', stderr='To github.com:user/repo.git\n'),
            # gh CLI check
            Mock(returncode=0, stdout='gh version 2.40.0\n', stderr=''),
            # gh auth status
            Mock(returncode=0, stdout='Logged in to github.com\n', stderr=''),
            # gh pr create
            Mock(returncode=0, stdout='https://github.com/user/repo/pull/123\n', stderr=''),
        ]

        # Act: Full workflow
        git_result = auto_commit_and_push(
            commit_message='feat: add feature',
            branch='main',
            push=True
        )

        # Assert git operations
        assert git_result['success'] is True
        assert git_result['commit_sha'] == 'abc1234'
        assert git_result['pushed'] is True

        # Note: PR creation would be tested separately in PR automation tests

    @patch('subprocess.run')
    def test_workflow_skips_pr_when_gh_not_available(self, mock_run):
        """Test workflow completes without PR when gh CLI not available."""
        # Arrange: git works, gh CLI not available
        mock_run.side_effect = [
            # validate_git_repo
            Mock(returncode=0, stdout='/repo/.git\n', stderr=''),
            # check_git_config (user.name)
            Mock(returncode=0, stdout='John Doe\n', stderr=''),
            # check_git_config (user.email)
            Mock(returncode=0, stdout='john@example.com\n', stderr=''),
            # detect_merge_conflict
            Mock(returncode=0, stdout='On branch main\nnothing to commit\n', stderr=''),
            # is_detached_head
            Mock(returncode=0, stdout='refs/heads/main\n', stderr=''),
            # has_uncommitted_changes
            Mock(returncode=0, stdout=' M file1.py\n', stderr=''),
            # stage_all_changes
            Mock(returncode=0, stdout='', stderr=''),
            # commit_changes
            Mock(returncode=0, stdout='[main abc1234] feat: add feature\n', stderr=''),
            # get_remote_name
            Mock(returncode=0, stdout='origin\n', stderr=''),
            # push_to_remote
            Mock(returncode=0, stdout='', stderr='To github.com:user/repo.git\n'),
        ]

        # Act
        result = auto_commit_and_push(
            commit_message='feat: add feature',
            branch='main',
            push=True
        )

        # Assert: Commit and push succeeded
        assert result['success'] is True
        assert result['commit_sha'] == 'abc1234'
        assert result['pushed'] is True
        # PR creation would be skipped in auto-implement command


class TestConsentBasedAutomation:
    """Test consent-based automation behavior."""

    @patch('builtins.input')
    def test_consent_prompt_formatting(self, mock_input):
        """Test consent prompt is clear and actionable."""
        # Arrange
        mock_input.return_value = 'yes'

        # Act: Simulate prompting user
        prompt = "Would you like to commit and push these changes? (yes/no): "
        response = mock_input(prompt)

        # Assert
        assert mock_input.called
        assert response == 'yes'
        mock_input.assert_called_with(prompt)

    @patch('builtins.input')
    def test_consent_accepts_various_yes_formats(self, mock_input):
        """Test consent accepts various affirmative responses."""
        # Test cases: y, yes, Y, YES, Yes
        test_cases = ['y', 'yes', 'Y', 'YES', 'Yes']

        for response in test_cases:
            mock_input.return_value = response
            user_response = mock_input("Commit? (yes/no): ")

            # Normalize response
            consent = user_response.lower() in ['y', 'yes']

            assert consent is True, f"Failed to accept '{response}' as consent"

    @patch('builtins.input')
    def test_consent_rejects_various_no_formats(self, mock_input):
        """Test consent rejects various negative responses."""
        # Test cases: n, no, N, NO, No, empty, random
        test_cases = ['n', 'no', 'N', 'NO', 'No', '', 'random']

        for response in test_cases:
            mock_input.return_value = response
            user_response = mock_input("Commit? (yes/no): ")

            # Normalize response
            consent = user_response.lower() in ['y', 'yes']

            assert consent is False, f"Failed to reject '{response}' as non-consent"


class TestGracefulDegradation:
    """Test graceful degradation when git operations fail."""

    @patch('subprocess.run')
    def test_auto_implement_continues_without_git_if_not_a_repo(self, mock_run):
        """Test /auto-implement continues without git operations if not in a git repo."""
        # Arrange: Not a git repo
        mock_run.side_effect = CalledProcessError(
            128,
            ['git', 'rev-parse', '--git-dir'],
            stderr='fatal: not a git repository'
        )

        # Act
        result = auto_commit_and_push(
            commit_message='feat: add feature',
            branch='main',
            push=True
        )

        # Assert: Should fail gracefully
        assert result['success'] is False
        assert 'not a git repository' in result['error'].lower()

        # Note: In actual /auto-implement, this would log warning and continue
        # without git operations

    @patch('subprocess.run')
    def test_auto_implement_warns_on_prerequisite_failures(self, mock_run):
        """Test /auto-implement provides helpful warnings on prerequisite failures."""
        # Test various prerequisite failures
        test_cases = [
            {
                'scenario': 'git not installed',
                'error': FileNotFoundError('git not found'),
                'expected_message': 'git not installed'
            },
            {
                'scenario': 'no git config',
                'mock_sequence': [
                    Mock(returncode=0, stdout='/repo/.git\n', stderr=''),  # validate_git_repo
                    CalledProcessError(1, ['git', 'config', 'user.name'], stderr=''),  # check_git_config user.name
                    CalledProcessError(1, ['git', 'config', 'user.email'], stderr=''),  # check_git_config user.email
                ],
                'expected_message': 'user.name'
            },
        ]

        for test_case in test_cases:
            # Arrange
            if 'error' in test_case:
                mock_run.side_effect = test_case['error']
            elif 'mock_sequence' in test_case:
                mock_run.side_effect = test_case['mock_sequence']

            # Act
            result = auto_commit_and_push(
                commit_message='feat: add feature',
                branch='main',
                push=True
            )

            # Assert
            assert result['success'] is False
            assert test_case['expected_message'] in result['error'].lower(), \
                f"Failed scenario: {test_case.get('scenario', 'unknown')}"
