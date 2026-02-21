"""
Unit tests for git operations library.

TDD Mode: These tests are written BEFORE implementation.
All tests should FAIL initially (ImportError: module not found).

Test Strategy:
- Mock all subprocess calls (no real git/gh commands)
- Test happy paths and error conditions
- Aim for 90%+ code coverage
- Test each function independently
- Test graceful degradation and consent-based automation

Date: 2025-11-04
Workflow: git_automation
Agent: test-master
"""

import json
import sys
import pytest
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock, call
from subprocess import CalledProcessError, TimeoutExpired
from typing import Dict, Any, List, Tuple

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
    from git_operations import (
        validate_git_repo,
        stage_all_changes,
        commit_changes,
        push_to_remote,
        create_feature_branch,
        check_git_config,
        detect_merge_conflict,
        is_detached_head,
        has_uncommitted_changes,
        get_remote_name,
        auto_commit_and_push,
        auto_commit_and_push_worktree,
        get_files_to_stage,
        push_worktree_branch,
    )
except ImportError as e:
    pytest.skip(f"Implementation not found (TDD red phase): {e}", allow_module_level=True)


class TestValidateGitRepo:
    """Test git repository validation."""

    @patch('subprocess.run')
    def test_validate_git_repo_success(self, mock_run):
        """Test validation succeeds in a valid git repository."""
        # Arrange: Mock successful git rev-parse
        mock_run.return_value = Mock(
            returncode=0,
            stdout='/path/to/repo/.git\n',
            stderr=''
        )

        # Act
        is_valid, error_message = validate_git_repo()

        # Assert
        assert is_valid is True
        assert error_message == ''
        mock_run.assert_called_once()
        args = mock_run.call_args[0][0]
        assert 'git' in args
        assert 'rev-parse' in args
        assert '--git-dir' in args

    @patch('subprocess.run')
    def test_validate_git_repo_not_a_repo(self, mock_run):
        """Test validation fails when not in a git repository."""
        # Arrange: Mock git command failing
        mock_run.side_effect = CalledProcessError(
            128,
            ['git', 'rev-parse', '--git-dir'],
            stderr='fatal: not a git repository'
        )

        # Act
        is_valid, error_message = validate_git_repo()

        # Assert
        assert is_valid is False
        assert 'not a git repository' in error_message.lower()

    @patch('subprocess.run')
    def test_validate_git_repo_git_not_installed(self, mock_run):
        """Test validation fails when git is not installed."""
        # Arrange: Mock FileNotFoundError (git not found)
        mock_run.side_effect = FileNotFoundError('git not found')

        # Act
        is_valid, error_message = validate_git_repo()

        # Assert
        assert is_valid is False
        assert 'git not installed' in error_message.lower()

    @patch('subprocess.run')
    def test_validate_git_repo_permission_denied(self, mock_run):
        """Test validation fails when permission denied."""
        # Arrange: Mock PermissionError
        mock_run.side_effect = PermissionError('Permission denied')

        # Act
        is_valid, error_message = validate_git_repo()

        # Assert
        assert is_valid is False
        assert 'permission' in error_message.lower()


class TestCheckGitConfig:
    """Test git configuration validation."""

    @patch('subprocess.run')
    def test_check_git_config_success(self, mock_run):
        """Test git config check succeeds when user.name and user.email are set."""
        # Arrange: Mock successful git config calls
        mock_run.side_effect = [
            Mock(returncode=0, stdout='John Doe\n', stderr=''),  # user.name
            Mock(returncode=0, stdout='john@example.com\n', stderr=''),  # user.email
        ]

        # Act
        is_configured, error_message = check_git_config()

        # Assert
        assert is_configured is True
        assert error_message == ''
        assert mock_run.call_count == 2

    @patch('subprocess.run')
    def test_check_git_config_missing_user_name(self, mock_run):
        """Test git config check fails when user.name is not set."""
        # Arrange: user.name fails, user.email succeeds
        mock_run.side_effect = [
            CalledProcessError(1, ['git', 'config', 'user.name'], stderr=''),
            Mock(returncode=0, stdout='john@example.com\n', stderr=''),
        ]

        # Act
        is_configured, error_message = check_git_config()

        # Assert
        assert is_configured is False
        assert 'user.name' in error_message.lower()

    @patch('subprocess.run')
    def test_check_git_config_missing_user_email(self, mock_run):
        """Test git config check fails when user.email is not set."""
        # Arrange: user.name succeeds, user.email fails
        mock_run.side_effect = [
            Mock(returncode=0, stdout='John Doe\n', stderr=''),
            CalledProcessError(1, ['git', 'config', 'user.email'], stderr=''),
        ]

        # Act
        is_configured, error_message = check_git_config()

        # Assert
        assert is_configured is False
        assert 'user.email' in error_message.lower()

    @patch('subprocess.run')
    def test_check_git_config_missing_both(self, mock_run):
        """Test git config check fails when both user.name and user.email are not set."""
        # Arrange: Both fail
        mock_run.side_effect = [
            CalledProcessError(1, ['git', 'config', 'user.name'], stderr=''),
            CalledProcessError(1, ['git', 'config', 'user.email'], stderr=''),
        ]

        # Act
        is_configured, error_message = check_git_config()

        # Assert
        assert is_configured is False
        assert 'user.name' in error_message.lower() or 'user.email' in error_message.lower()


class TestDetectMergeConflict:
    """Test merge conflict detection."""

    @patch('subprocess.run')
    def test_detect_merge_conflict_no_conflict(self, mock_run):
        """Test merge conflict detection when no conflict exists."""
        # Arrange: Mock git status showing clean state
        mock_run.return_value = Mock(
            returncode=0,
            stdout='On branch main\nnothing to commit, working tree clean\n',
            stderr=''
        )

        # Act
        has_conflict, conflict_files = detect_merge_conflict()

        # Assert
        assert has_conflict is False
        assert conflict_files == []

    @patch('subprocess.run')
    def test_detect_merge_conflict_with_conflicts(self, mock_run):
        """Test merge conflict detection when conflicts exist."""
        # Arrange: Mock git status showing unmerged paths
        mock_run.return_value = Mock(
            returncode=0,
            stdout='''On branch main
Unmerged paths:
  (use "git add <file>..." to mark resolution)
        both modified:   file1.py
        both modified:   file2.py
''',
            stderr=''
        )

        # Act
        has_conflict, conflict_files = detect_merge_conflict()

        # Assert
        assert has_conflict is True
        assert len(conflict_files) == 2
        assert 'file1.py' in conflict_files
        assert 'file2.py' in conflict_files

    @patch('subprocess.run')
    def test_detect_merge_conflict_git_error(self, mock_run):
        """Test merge conflict detection handles git errors gracefully."""
        # Arrange: Mock git command failing
        mock_run.side_effect = CalledProcessError(
            128,
            ['git', 'status'],
            stderr='fatal: not a git repository'
        )

        # Act
        has_conflict, conflict_files = detect_merge_conflict()

        # Assert
        assert has_conflict is False
        assert conflict_files == []


class TestIsDetachedHead:
    """Test detached HEAD state detection."""

    @patch('subprocess.run')
    def test_is_detached_head_false(self, mock_run):
        """Test detached HEAD detection when on a branch."""
        # Arrange: Mock git symbolic-ref succeeding
        mock_run.return_value = Mock(
            returncode=0,
            stdout='refs/heads/main\n',
            stderr=''
        )

        # Act
        is_detached = is_detached_head()

        # Assert
        assert is_detached is False

    @patch('subprocess.run')
    def test_is_detached_head_true(self, mock_run):
        """Test detached HEAD detection when in detached HEAD state."""
        # Arrange: Mock git symbolic-ref failing (detached HEAD)
        mock_run.side_effect = CalledProcessError(
            1,
            ['git', 'symbolic-ref', '-q', 'HEAD'],
            stderr='fatal: ref HEAD is not a symbolic ref'
        )

        # Act
        is_detached = is_detached_head()

        # Assert
        assert is_detached is True

    @patch('subprocess.run')
    def test_is_detached_head_git_error(self, mock_run):
        """Test detached HEAD detection handles git errors gracefully."""
        # Arrange: Mock unexpected error
        mock_run.side_effect = FileNotFoundError('git not found')

        # Act
        is_detached = is_detached_head()

        # Assert: Default to safe state (treat as detached)
        assert is_detached is True


class TestHasUncommittedChanges:
    """Test uncommitted changes detection."""

    @patch('subprocess.run')
    def test_has_uncommitted_changes_clean(self, mock_run):
        """Test uncommitted changes detection when working tree is clean."""
        # Arrange: Mock git status showing clean state
        mock_run.return_value = Mock(
            returncode=0,
            stdout='',
            stderr=''
        )

        # Act
        has_changes = has_uncommitted_changes()

        # Assert
        assert has_changes is False

    @patch('subprocess.run')
    def test_has_uncommitted_changes_with_changes(self, mock_run):
        """Test uncommitted changes detection when changes exist."""
        # Arrange: Mock git status showing changes
        mock_run.return_value = Mock(
            returncode=0,
            stdout=' M file1.py\n?? file2.py\n',
            stderr=''
        )

        # Act
        has_changes = has_uncommitted_changes()

        # Assert
        assert has_changes is True

    @patch('subprocess.run')
    def test_has_uncommitted_changes_git_error(self, mock_run):
        """Test uncommitted changes detection handles git errors gracefully."""
        # Arrange: Mock git error
        mock_run.side_effect = CalledProcessError(
            128,
            ['git', 'status', '--porcelain'],
            stderr='fatal: not a git repository'
        )

        # Act
        has_changes = has_uncommitted_changes()

        # Assert: Default to safe state (assume changes)
        assert has_changes is True


class TestStageAllChanges:
    """Test staging all changes."""

    @patch('subprocess.run')
    def test_stage_all_changes_success(self, mock_run):
        """Test staging all changes succeeds."""
        # Arrange: Mock successful git add
        mock_run.return_value = Mock(returncode=0, stdout='', stderr='')

        # Act
        success, error_message = stage_all_changes()

        # Assert
        assert success is True
        assert error_message == ''
        mock_run.assert_called_once()
        args = mock_run.call_args[0][0]
        assert args == ['git', 'add', '.']

    @patch('subprocess.run')
    def test_stage_all_changes_nothing_to_add(self, mock_run):
        """Test staging when nothing to add (should still succeed)."""
        # Arrange: Mock git add with no changes
        mock_run.return_value = Mock(
            returncode=0,
            stdout='',
            stderr=''
        )

        # Act
        success, error_message = stage_all_changes()

        # Assert
        assert success is True
        assert error_message == ''

    @patch('subprocess.run')
    def test_stage_all_changes_permission_denied(self, mock_run):
        """Test staging fails when permission denied."""
        # Arrange: Mock permission error
        mock_run.side_effect = PermissionError('Permission denied')

        # Act
        success, error_message = stage_all_changes()

        # Assert
        assert success is False
        assert 'permission' in error_message.lower()

    @patch('subprocess.run')
    def test_stage_all_changes_git_error(self, mock_run):
        """Test staging fails when git command fails."""
        # Arrange: Mock git add failing
        mock_run.side_effect = CalledProcessError(
            1,
            ['git', 'add', '.'],
            stderr='error: pathspec "." did not match any files'
        )

        # Act
        success, error_message = stage_all_changes()

        # Assert
        assert success is False
        assert error_message != ''


class TestCommitChanges:
    """Test creating git commits."""

    @patch('subprocess.run')
    def test_commit_changes_success(self, mock_run):
        """Test commit succeeds with valid message."""
        # Arrange: Mock successful git commit
        mock_run.return_value = Mock(
            returncode=0,
            stdout='[main abc1234] feat: add new feature\n 3 files changed, 50 insertions(+)\n',
            stderr=''
        )

        # Act
        success, commit_sha, error_message = commit_changes('feat: add new feature')

        # Assert
        assert success is True
        assert commit_sha == 'abc1234'
        assert error_message == ''
        mock_run.assert_called_once()
        args = mock_run.call_args[0][0]
        assert 'git' in args
        assert 'commit' in args
        assert '-m' in args

    @patch('subprocess.run')
    def test_commit_changes_nothing_to_commit(self, mock_run):
        """Test commit gracefully handles nothing to commit."""
        # Arrange: Mock git commit with nothing to commit
        exc = CalledProcessError(
            1,
            ['git', 'commit', '-m', 'message'],
            stderr='nothing to commit, working tree clean'
        )
        exc.stdout = ''  # Set stdout as attribute after creation
        mock_run.side_effect = exc

        # Act
        success, commit_sha, error_message = commit_changes('feat: add new feature')

        # Assert
        assert success is False
        assert commit_sha == ''
        assert 'nothing to commit' in error_message.lower()

    @patch('subprocess.run')
    def test_commit_changes_no_git_config(self, mock_run):
        """Test commit fails when git user config is not set."""
        # Arrange: Mock git commit failing due to config
        mock_run.side_effect = CalledProcessError(
            128,
            ['git', 'commit', '-m', 'message'],
            stderr='fatal: unable to auto-detect email address'
        )

        # Act
        success, commit_sha, error_message = commit_changes('feat: add new feature')

        # Assert
        assert success is False
        assert commit_sha == ''
        assert 'email' in error_message.lower() or 'config' in error_message.lower()

    @patch('subprocess.run')
    def test_commit_changes_empty_message(self, mock_run):
        """Test commit fails with empty message."""
        # Arrange: Empty message should fail validation
        # Act
        success, commit_sha, error_message = commit_changes('')

        # Assert
        assert success is False
        assert commit_sha == ''
        assert 'message' in error_message.lower()
        mock_run.assert_not_called()

    @patch('subprocess.run')
    def test_commit_changes_multiline_message(self, mock_run):
        """Test commit succeeds with multiline message."""
        # Arrange: Mock successful commit
        mock_run.return_value = Mock(
            returncode=0,
            stdout='[main abc1234] feat: add feature\n',
            stderr=''
        )

        # Act
        message = 'feat: add feature\n\nDetailed description here.'
        success, commit_sha, error_message = commit_changes(message)

        # Assert
        assert success is True
        assert commit_sha == 'abc1234'
        assert error_message == ''


class TestGetRemoteName:
    """Test getting git remote name."""

    @patch('subprocess.run')
    def test_get_remote_name_origin(self, mock_run):
        """Test getting remote name when origin exists."""
        # Arrange: Mock git remote
        mock_run.return_value = Mock(
            returncode=0,
            stdout='origin\n',
            stderr=''
        )

        # Act
        remote_name = get_remote_name()

        # Assert
        assert remote_name == 'origin'

    @patch('subprocess.run')
    def test_get_remote_name_custom(self, mock_run):
        """Test getting remote name when custom remote exists."""
        # Arrange: Mock git remote with custom name
        mock_run.return_value = Mock(
            returncode=0,
            stdout='upstream\norigin\n',
            stderr=''
        )

        # Act
        remote_name = get_remote_name()

        # Assert: Should return first remote
        assert remote_name == 'upstream'

    @patch('subprocess.run')
    def test_get_remote_name_no_remote(self, mock_run):
        """Test getting remote name when no remote exists."""
        # Arrange: Mock git remote with no output
        mock_run.return_value = Mock(
            returncode=0,
            stdout='',
            stderr=''
        )

        # Act
        remote_name = get_remote_name()

        # Assert
        assert remote_name == ''

    @patch('subprocess.run')
    def test_get_remote_name_git_error(self, mock_run):
        """Test getting remote name handles git errors gracefully."""
        # Arrange: Mock git error
        mock_run.side_effect = CalledProcessError(
            128,
            ['git', 'remote'],
            stderr='fatal: not a git repository'
        )

        # Act
        remote_name = get_remote_name()

        # Assert
        assert remote_name == ''


class TestPushToRemote:
    """Test pushing to remote repository."""

    @patch('subprocess.run')
    def test_push_to_remote_success(self, mock_run):
        """Test push succeeds to existing remote."""
        # Arrange: Mock successful git push
        mock_run.return_value = Mock(
            returncode=0,
            stdout='',
            stderr='To github.com:user/repo.git\n   abc1234..def5678  main -> main\n'
        )

        # Act
        success, error_message = push_to_remote('main', 'origin')

        # Assert
        assert success is True
        assert error_message == ''
        mock_run.assert_called_once()
        args = mock_run.call_args[0][0]
        assert args == ['git', 'push', 'origin', 'main']

    @patch('subprocess.run')
    def test_push_to_remote_with_set_upstream(self, mock_run):
        """Test push with --set-upstream for new branch."""
        # Arrange: Mock successful git push -u
        mock_run.return_value = Mock(
            returncode=0,
            stdout='',
            stderr='Branch \'feature\' set up to track remote branch \'feature\' from \'origin\'.\n'
        )

        # Act
        success, error_message = push_to_remote('feature', 'origin', set_upstream=True)

        # Assert
        assert success is True
        assert error_message == ''
        args = mock_run.call_args[0][0]
        assert args == ['git', 'push', '-u', 'origin', 'feature']

    @patch('subprocess.run')
    def test_push_to_remote_no_remote(self, mock_run):
        """Test push fails when remote doesn't exist."""
        # Arrange: Mock git push failing (no remote)
        mock_run.side_effect = CalledProcessError(
            128,
            ['git', 'push', 'origin', 'main'],
            stderr='fatal: \'origin\' does not appear to be a git repository'
        )

        # Act
        success, error_message = push_to_remote('main', 'origin')

        # Assert
        assert success is False
        assert 'remote' in error_message.lower() or 'origin' in error_message.lower()

    @patch('subprocess.run')
    def test_push_to_remote_network_timeout(self, mock_run):
        """Test push fails when network times out."""
        # Arrange: Mock timeout
        mock_run.side_effect = TimeoutExpired(
            ['git', 'push', 'origin', 'main'],
            timeout=30
        )

        # Act
        success, error_message = push_to_remote('main', 'origin', timeout=30)

        # Assert
        assert success is False
        assert 'timeout' in error_message.lower()

    @patch('subprocess.run')
    def test_push_to_remote_rejected(self, mock_run):
        """Test push fails when rejected (non-fast-forward)."""
        # Arrange: Mock git push rejected
        mock_run.side_effect = CalledProcessError(
            1,
            ['git', 'push', 'origin', 'main'],
            stderr='! [rejected]        main -> main (non-fast-forward)'
        )

        # Act
        success, error_message = push_to_remote('main', 'origin')

        # Assert
        assert success is False
        assert 'rejected' in error_message.lower()

    @patch('subprocess.run')
    def test_push_to_remote_permission_denied(self, mock_run):
        """Test push fails when permission denied."""
        # Arrange: Mock permission error
        mock_run.side_effect = CalledProcessError(
            128,
            ['git', 'push', 'origin', 'main'],
            stderr='Permission denied (publickey)'
        )

        # Act
        success, error_message = push_to_remote('main', 'origin')

        # Assert
        assert success is False
        assert 'permission' in error_message.lower()

    @patch('subprocess.run')
    def test_push_to_remote_branch_protected(self, mock_run):
        """Test push fails when branch is protected."""
        # Arrange: Mock branch protection error
        mock_run.side_effect = CalledProcessError(
            1,
            ['git', 'push', 'origin', 'main'],
            stderr='remote: error: GH006: Protected branch update failed'
        )

        # Act
        success, error_message = push_to_remote('main', 'origin')

        # Assert
        assert success is False
        assert 'protected' in error_message.lower() or 'gh006' in error_message.lower()


class TestCreateFeatureBranch:
    """Test creating feature branches."""

    @patch('subprocess.run')
    def test_create_feature_branch_success(self, mock_run):
        """Test creating feature branch succeeds."""
        # Arrange: Mock successful git checkout -b
        mock_run.return_value = Mock(
            returncode=0,
            stdout='',
            stderr='Switched to a new branch \'feature/new-feature\'\n'
        )

        # Act
        success, branch_name, error_message = create_feature_branch('feature/new-feature')

        # Assert
        assert success is True
        assert branch_name == 'feature/new-feature'
        assert error_message == ''
        args = mock_run.call_args[0][0]
        assert args == ['git', 'checkout', '-b', 'feature/new-feature']

    @patch('subprocess.run')
    def test_create_feature_branch_already_exists(self, mock_run):
        """Test creating branch fails when branch already exists."""
        # Arrange: Mock git checkout -b failing
        mock_run.side_effect = CalledProcessError(
            128,
            ['git', 'checkout', '-b', 'feature/existing'],
            stderr='fatal: A branch named \'feature/existing\' already exists.'
        )

        # Act
        success, branch_name, error_message = create_feature_branch('feature/existing')

        # Assert
        assert success is False
        assert branch_name == ''
        assert 'already exists' in error_message.lower()

    @patch('subprocess.run')
    def test_create_feature_branch_invalid_name(self, mock_run):
        """Test creating branch fails with invalid name."""
        # Arrange: Mock git checkout -b failing
        mock_run.side_effect = CalledProcessError(
            128,
            ['git', 'checkout', '-b', 'invalid..name'],
            stderr='fatal: \'invalid..name\' is not a valid branch name'
        )

        # Act
        success, branch_name, error_message = create_feature_branch('invalid..name')

        # Assert
        assert success is False
        assert branch_name == ''
        assert 'not a valid' in error_message.lower()


class TestAutoCommitAndPush:
    """Test high-level auto-commit-and-push workflow."""

    @patch('git_operations.validate_git_repo')
    @patch('git_operations.check_git_config')
    @patch('git_operations.detect_merge_conflict')
    @patch('git_operations.is_detached_head')
    @patch('git_operations.has_uncommitted_changes')
    @patch('git_operations.stage_all_changes')
    @patch('git_operations.commit_changes')
    @patch('git_operations.get_remote_name')
    @patch('git_operations.push_to_remote')
    def test_auto_commit_and_push_success(
        self,
        mock_push,
        mock_get_remote,
        mock_commit,
        mock_stage,
        mock_has_changes,
        mock_detached,
        mock_conflict,
        mock_config,
        mock_validate,
    ):
        """Test full auto-commit-and-push workflow succeeds."""
        # Arrange: All prerequisites pass
        mock_validate.return_value = (True, '')
        mock_config.return_value = (True, '')
        mock_conflict.return_value = (False, [])
        mock_detached.return_value = False
        mock_has_changes.return_value = True
        mock_stage.return_value = (True, '')
        mock_commit.return_value = (True, 'abc1234', '')
        mock_get_remote.return_value = 'origin'
        mock_push.return_value = (True, '')

        # Act
        result = auto_commit_and_push(
            commit_message='feat: add feature',
            branch='main',
            push=True
        )

        # Assert
        assert result['success'] is True
        assert result['commit_sha'] == 'abc1234'
        assert result['pushed'] is True
        assert result['error'] == ''

    @patch('git_operations.validate_git_repo')
    def test_auto_commit_and_push_not_a_repo(self, mock_validate):
        """Test auto-commit-and-push fails when not a git repo."""
        # Arrange: Not a git repo
        mock_validate.return_value = (False, 'Not a git repository')

        # Act
        result = auto_commit_and_push(
            commit_message='feat: add feature',
            branch='main'
        )

        # Assert
        assert result['success'] is False
        assert 'not a git repository' in result['error'].lower()
        assert result['commit_sha'] == ''
        assert result['pushed'] is False

    @patch('git_operations.validate_git_repo')
    @patch('git_operations.check_git_config')
    def test_auto_commit_and_push_no_git_config(self, mock_config, mock_validate):
        """Test auto-commit-and-push fails when git config missing."""
        # Arrange: Valid repo, but no git config
        mock_validate.return_value = (True, '')
        mock_config.return_value = (False, 'Git user.name not set')

        # Act
        result = auto_commit_and_push(
            commit_message='feat: add feature',
            branch='main'
        )

        # Assert
        assert result['success'] is False
        assert 'user.name' in result['error'].lower()
        assert result['commit_sha'] == ''

    @patch('git_operations.validate_git_repo')
    @patch('git_operations.check_git_config')
    @patch('git_operations.detect_merge_conflict')
    def test_auto_commit_and_push_merge_conflict(
        self,
        mock_conflict,
        mock_config,
        mock_validate
    ):
        """Test auto-commit-and-push fails when merge conflict exists."""
        # Arrange: Valid repo, but merge conflict
        mock_validate.return_value = (True, '')
        mock_config.return_value = (True, '')
        mock_conflict.return_value = (True, ['file1.py', 'file2.py'])

        # Act
        result = auto_commit_and_push(
            commit_message='feat: add feature',
            branch='main'
        )

        # Assert
        assert result['success'] is False
        assert 'merge conflict' in result['error'].lower()
        assert 'file1.py' in result['error']
        assert 'file2.py' in result['error']

    @patch('git_operations.validate_git_repo')
    @patch('git_operations.check_git_config')
    @patch('git_operations.detect_merge_conflict')
    @patch('git_operations.is_detached_head')
    def test_auto_commit_and_push_detached_head(
        self,
        mock_detached,
        mock_conflict,
        mock_config,
        mock_validate
    ):
        """Test auto-commit-and-push fails when in detached HEAD state."""
        # Arrange: Valid repo, but detached HEAD
        mock_validate.return_value = (True, '')
        mock_config.return_value = (True, '')
        mock_conflict.return_value = (False, [])
        mock_detached.return_value = True

        # Act
        result = auto_commit_and_push(
            commit_message='feat: add feature',
            branch='main'
        )

        # Assert
        assert result['success'] is False
        assert 'detached head' in result['error'].lower()

    @patch('git_operations.validate_git_repo')
    @patch('git_operations.check_git_config')
    @patch('git_operations.detect_merge_conflict')
    @patch('git_operations.is_detached_head')
    @patch('git_operations.has_uncommitted_changes')
    def test_auto_commit_and_push_nothing_to_commit(
        self,
        mock_has_changes,
        mock_detached,
        mock_conflict,
        mock_config,
        mock_validate
    ):
        """Test auto-commit-and-push succeeds gracefully when nothing to commit."""
        # Arrange: Valid repo, but no changes
        mock_validate.return_value = (True, '')
        mock_config.return_value = (True, '')
        mock_conflict.return_value = (False, [])
        mock_detached.return_value = False
        mock_has_changes.return_value = False

        # Act
        result = auto_commit_and_push(
            commit_message='feat: add feature',
            branch='main'
        )

        # Assert
        assert result['success'] is True
        assert result['commit_sha'] == ''
        assert result['pushed'] is False
        assert 'nothing to commit' in result['error'].lower()

    @patch('git_operations.validate_git_repo')
    @patch('git_operations.check_git_config')
    @patch('git_operations.detect_merge_conflict')
    @patch('git_operations.is_detached_head')
    @patch('git_operations.has_uncommitted_changes')
    @patch('git_operations.stage_all_changes')
    @patch('git_operations.commit_changes')
    @patch('git_operations.get_remote_name')
    @patch('git_operations.push_to_remote')
    def test_auto_commit_and_push_commit_succeeds_push_fails(
        self,
        mock_push,
        mock_get_remote,
        mock_commit,
        mock_stage,
        mock_has_changes,
        mock_detached,
        mock_conflict,
        mock_config,
        mock_validate,
    ):
        """Test auto-commit-and-push gracefully handles push failure after successful commit."""
        # Arrange: Commit succeeds, push fails
        mock_validate.return_value = (True, '')
        mock_config.return_value = (True, '')
        mock_conflict.return_value = (False, [])
        mock_detached.return_value = False
        mock_has_changes.return_value = True
        mock_stage.return_value = (True, '')
        mock_commit.return_value = (True, 'abc1234', '')
        mock_get_remote.return_value = 'origin'
        mock_push.return_value = (False, 'Network timeout')

        # Act
        result = auto_commit_and_push(
            commit_message='feat: add feature',
            branch='main',
            push=True
        )

        # Assert
        assert result['success'] is True  # Commit succeeded
        assert result['commit_sha'] == 'abc1234'
        assert result['pushed'] is False  # Push failed
        assert 'network timeout' in result['error'].lower()

    @patch('git_operations.validate_git_repo')
    @patch('git_operations.check_git_config')
    @patch('git_operations.detect_merge_conflict')
    @patch('git_operations.is_detached_head')
    @patch('git_operations.has_uncommitted_changes')
    @patch('git_operations.stage_all_changes')
    @patch('git_operations.commit_changes')
    def test_auto_commit_and_push_no_push_requested(
        self,
        mock_commit,
        mock_stage,
        mock_has_changes,
        mock_detached,
        mock_conflict,
        mock_config,
        mock_validate,
    ):
        """Test auto-commit-and-push skips push when push=False."""
        # Arrange: Commit succeeds, push not requested
        mock_validate.return_value = (True, '')
        mock_config.return_value = (True, '')
        mock_conflict.return_value = (False, [])
        mock_detached.return_value = False
        mock_has_changes.return_value = True
        mock_stage.return_value = (True, '')
        mock_commit.return_value = (True, 'abc1234', '')

        # Act
        result = auto_commit_and_push(
            commit_message='feat: add feature',
            branch='main',
            push=False
        )

        # Assert
        assert result['success'] is True
        assert result['commit_sha'] == 'abc1234'
        assert result['pushed'] is False
        assert result['error'] == ''


class TestGetFilesToStage:
    """Test gitignore-aware file staging (Issue #325)."""

    @patch('subprocess.run')
    def test_get_files_to_stage_filters_gitignored(self, mock_run):
        """Test that gitignored files are filtered out."""
        # Arrange: Mock git status showing both tracked and gitignored files
        # Porcelain format: XY filename (XY is 2 chars, then space, then filename)
        # ' M' means index unmodified, worktree modified
        # '??' means untracked file
        mock_run.side_effect = [
            # git status --porcelain
            Mock(
                returncode=0,
                stdout='M  file1.py\nM  .claude/hooks/test.py\n?? new_file.py\n',
                stderr=''
            ),
            # git check-ignore --stdin
            Mock(
                returncode=0,
                stdout='.claude/hooks/test.py\n',
                stderr=''
            ),
        ]

        # Act
        files_to_stage, ignored_files = get_files_to_stage()

        # Assert
        assert 'file1.py' in files_to_stage
        assert 'new_file.py' in files_to_stage
        assert '.claude/hooks/test.py' not in files_to_stage
        assert '.claude/hooks/test.py' in ignored_files

    @patch('subprocess.run')
    def test_get_files_to_stage_no_files(self, mock_run):
        """Test when there are no files to stage."""
        # Arrange: Mock git status showing clean
        mock_run.return_value = Mock(
            returncode=0,
            stdout='',
            stderr=''
        )

        # Act
        files_to_stage, ignored_files = get_files_to_stage()

        # Assert
        assert files_to_stage == []
        assert ignored_files == []

    @patch('subprocess.run')
    def test_get_files_to_stage_handles_renamed_files(self, mock_run):
        """Test handling of renamed files in git status output."""
        # Arrange: Mock git status with renamed file
        mock_run.side_effect = [
            # git status --porcelain
            Mock(
                returncode=0,
                stdout='R  old_name.py -> new_name.py\n',
                stderr=''
            ),
            # git check-ignore --stdin
            Mock(
                returncode=0,
                stdout='',
                stderr=''
            ),
        ]

        # Act
        files_to_stage, ignored_files = get_files_to_stage()

        # Assert: Should extract the new name
        assert 'new_name.py' in files_to_stage

    @patch('subprocess.run')
    def test_get_files_to_stage_with_cwd(self, mock_run):
        """Test get_files_to_stage with custom working directory."""
        # Arrange
        mock_run.side_effect = [
            Mock(returncode=0, stdout=' M file.py\n', stderr=''),
            Mock(returncode=0, stdout='', stderr=''),
        ]
        custom_cwd = Path('/custom/path')

        # Act
        files_to_stage, ignored_files = get_files_to_stage(cwd=custom_cwd)

        # Assert: Verify cwd was passed to subprocess
        assert mock_run.call_args_list[0][1]['cwd'] == str(custom_cwd)

    @patch('subprocess.run')
    def test_get_files_to_stage_timeout_fallback(self, mock_run):
        """Test that timeout returns empty lists (fallback behavior)."""
        # Arrange
        mock_run.side_effect = TimeoutExpired(['git', 'status'], 30)

        # Act
        files_to_stage, ignored_files = get_files_to_stage()

        # Assert: Fallback returns empty lists
        assert files_to_stage == []
        assert ignored_files == []


class TestStageAllChangesWithCwd:
    """Test stage_all_changes with cwd and gitignore_aware parameters (Issue #325)."""

    @patch('subprocess.run')
    def test_stage_all_changes_with_cwd(self, mock_run):
        """Test stage_all_changes passes cwd to subprocess."""
        # Arrange
        mock_run.return_value = Mock(returncode=0, stdout='', stderr='')
        custom_cwd = Path('/custom/path')

        # Act
        success, error = stage_all_changes(cwd=custom_cwd)

        # Assert
        assert success is True
        assert mock_run.call_args[1]['cwd'] == str(custom_cwd)

    @patch('git_operations.get_files_to_stage')
    @patch('subprocess.run')
    def test_stage_all_changes_gitignore_aware(self, mock_run, mock_get_files):
        """Test gitignore_aware=True filters files before staging."""
        # Arrange
        mock_get_files.return_value = (['file1.py', 'file2.py'], ['.claude/hooks/test.py'])
        mock_run.return_value = Mock(returncode=0, stdout='', stderr='')

        # Act
        success, error = stage_all_changes(gitignore_aware=True)

        # Assert
        assert success is True
        mock_get_files.assert_called_once()
        # Verify git add was called with specific files, not '.'
        args = mock_run.call_args[0][0]
        assert 'file1.py' in args
        assert 'file2.py' in args
        assert '.claude/hooks/test.py' not in args

    @patch('git_operations.get_files_to_stage')
    @patch('subprocess.run')
    def test_stage_all_changes_gitignore_aware_only_ignored_files(self, mock_run, mock_get_files):
        """Test gitignore_aware=True when only gitignored files exist."""
        # Arrange: Only gitignored files, nothing to stage
        mock_get_files.return_value = ([], ['.claude/hooks/test.py'])
        mock_run.return_value = Mock(returncode=0, stdout='', stderr='')

        # Act
        success, error = stage_all_changes(gitignore_aware=True)

        # Assert: Should succeed with nothing staged
        assert success is True

    @patch('subprocess.run')
    def test_stage_all_changes_default_not_gitignore_aware(self, mock_run):
        """Test that default behavior (gitignore_aware=False) uses git add ."""
        # Arrange
        mock_run.return_value = Mock(returncode=0, stdout='', stderr='')

        # Act
        success, error = stage_all_changes()

        # Assert
        assert success is True
        args = mock_run.call_args[0][0]
        assert args == ['git', 'add', '.']


class TestPushWorktreeBranch:
    """Test push_worktree_branch for handling detached HEAD state (Issue #325)."""

    @patch('subprocess.run')
    def test_push_worktree_branch_detached_head(self, mock_run):
        """Test push from detached HEAD uses HEAD:<branch> syntax."""
        # Arrange: Simulate detached HEAD
        # Note: symbolic-ref doesn't use check=True, so it returns with non-zero
        # returncode instead of raising CalledProcessError
        mock_run.side_effect = [
            # git symbolic-ref returns non-zero for detached HEAD (no exception, just returncode)
            Mock(returncode=1, stdout='', stderr=''),
            # git push succeeds
            Mock(returncode=0, stdout='', stderr=''),
        ]

        # Act
        success, error = push_worktree_branch('batch-20260205-123456')

        # Assert
        assert success is True
        # Verify push used HEAD:<branch> syntax
        push_call = mock_run.call_args_list[1]
        push_args = push_call[0][0]
        assert 'HEAD:batch-20260205-123456' in push_args

    @patch('subprocess.run')
    def test_push_worktree_branch_on_branch(self, mock_run):
        """Test push when on branch uses standard syntax."""
        # Arrange: On a branch (not detached)
        mock_run.side_effect = [
            # git symbolic-ref succeeds (on a branch)
            Mock(returncode=0, stdout='refs/heads/batch-20260205-123456\n'),
            # git push succeeds
            Mock(returncode=0, stdout='', stderr=''),
        ]

        # Act
        success, error = push_worktree_branch('batch-20260205-123456')

        # Assert
        assert success is True
        # Verify push used standard syntax (not HEAD:)
        push_call = mock_run.call_args_list[1]
        push_args = push_call[0][0]
        assert 'batch-20260205-123456' in push_args
        # Check that HEAD: syntax was NOT used
        assert not any('HEAD:' in str(arg) for arg in push_args)

    @patch('subprocess.run')
    def test_push_worktree_branch_with_cwd(self, mock_run):
        """Test push_worktree_branch with custom working directory."""
        # Arrange
        mock_run.side_effect = [
            Mock(returncode=0, stdout='refs/heads/main\n'),
            Mock(returncode=0, stdout='', stderr=''),
        ]
        custom_cwd = Path('/custom/worktree/path')

        # Act
        success, error = push_worktree_branch('main', cwd=custom_cwd)

        # Assert
        assert success is True
        # Both calls should use cwd
        assert mock_run.call_args_list[0][1]['cwd'] == str(custom_cwd)
        assert mock_run.call_args_list[1][1]['cwd'] == str(custom_cwd)

    @patch('subprocess.run')
    def test_push_worktree_branch_with_set_upstream(self, mock_run):
        """Test push_worktree_branch with set_upstream=True."""
        # Arrange
        mock_run.side_effect = [
            Mock(returncode=0, stdout='refs/heads/feature\n'),
            Mock(returncode=0, stdout='', stderr=''),
        ]

        # Act
        success, error = push_worktree_branch('feature', set_upstream=True)

        # Assert
        assert success is True
        push_args = mock_run.call_args_list[1][0][0]
        assert '-u' in push_args

    @patch('subprocess.run')
    def test_push_worktree_branch_network_timeout(self, mock_run):
        """Test push_worktree_branch handles network timeout."""
        # Arrange
        mock_run.side_effect = [
            Mock(returncode=0, stdout='refs/heads/main\n'),
            TimeoutExpired(['git', 'push'], 30),
        ]

        # Act
        success, error = push_worktree_branch('main')

        # Assert
        assert success is False
        assert 'timeout' in error.lower()

    @patch('subprocess.run')
    def test_push_worktree_branch_unqualified_destination_error(self, mock_run):
        """Test push_worktree_branch handles unqualified destination error."""
        # Arrange: This is the error we're fixing with Issue #325
        # symbolic-ref doesn't use check=True, so returns non-zero returncode
        mock_run.side_effect = [
            Mock(returncode=1, stdout='', stderr=''),  # detached HEAD
            CalledProcessError(
                1,
                ['git', 'push'],
                stderr='error: unable to push to unqualified destination'
            ),
        ]

        # Act
        success, error = push_worktree_branch('batch-20260205-123456')

        # Assert
        assert success is False
        assert 'detached head' in error.lower() or 'unqualified' in error.lower()


class TestAutoCommitAndPushWorktree:
    """Test worktree-aware auto-commit-and-push workflow (Issue #325)."""

    @patch('git_operations.validate_git_repo')
    @patch('git_operations.check_git_config')
    @patch('git_operations.detect_merge_conflict')
    @patch('git_operations.has_uncommitted_changes')
    @patch('git_operations.stage_all_changes')
    @patch('git_operations.commit_changes')
    @patch('git_operations.get_remote_name')
    @patch('git_operations.push_worktree_branch')
    def test_auto_commit_and_push_worktree_success(
        self,
        mock_push_worktree,
        mock_get_remote,
        mock_commit,
        mock_stage,
        mock_has_changes,
        mock_conflict,
        mock_config,
        mock_validate,
    ):
        """Test full worktree workflow succeeds with gitignore-aware staging."""
        # Arrange: All prerequisites pass
        mock_validate.return_value = (True, '')
        mock_config.return_value = (True, '')
        mock_conflict.return_value = (False, [])
        mock_has_changes.return_value = True
        mock_stage.return_value = (True, '')
        mock_commit.return_value = (True, 'abc1234', '')
        mock_get_remote.return_value = 'origin'
        mock_push_worktree.return_value = (True, '')

        # Act
        result = auto_commit_and_push_worktree(
            commit_message='feat: add feature',
            branch='batch-20260205-123456',
            push=True,
            cwd=Path('/worktrees/batch')
        )

        # Assert
        assert result['success'] is True
        assert result['commit_sha'] == 'abc1234'
        assert result['pushed'] is True
        assert result['error'] == ''
        # Verify gitignore-aware staging was used
        mock_stage.assert_called_once()
        call_kwargs = mock_stage.call_args[1]
        assert call_kwargs.get('gitignore_aware') is True
        # Verify worktree-aware push was used
        mock_push_worktree.assert_called_once()
        call_args = mock_push_worktree.call_args
        assert call_args[1]['branch'] == 'batch-20260205-123456'

    @patch('git_operations.validate_git_repo')
    @patch('git_operations.check_git_config')
    @patch('git_operations.detect_merge_conflict')
    @patch('git_operations.has_uncommitted_changes')
    @patch('git_operations.stage_all_changes')
    @patch('git_operations.commit_changes')
    @patch('git_operations.get_remote_name')
    @patch('git_operations.push_worktree_branch')
    def test_auto_commit_and_push_worktree_with_cwd(
        self,
        mock_push_worktree,
        mock_get_remote,
        mock_commit,
        mock_stage,
        mock_has_changes,
        mock_conflict,
        mock_config,
        mock_validate,
    ):
        """Test that cwd is passed to stage and push functions."""
        # Arrange
        mock_validate.return_value = (True, '')
        mock_config.return_value = (True, '')
        mock_conflict.return_value = (False, [])
        mock_has_changes.return_value = True
        mock_stage.return_value = (True, '')
        mock_commit.return_value = (True, 'abc1234', '')
        mock_get_remote.return_value = 'origin'
        mock_push_worktree.return_value = (True, '')
        worktree_path = Path('/worktrees/my-batch')

        # Act
        result = auto_commit_and_push_worktree(
            commit_message='feat: batch feature',
            branch='batch-branch',
            push=True,
            cwd=worktree_path
        )

        # Assert
        assert result['success'] is True
        # Verify cwd was passed to stage_all_changes
        mock_stage.assert_called_with(cwd=worktree_path, gitignore_aware=True)
        # Verify cwd was passed to push_worktree_branch
        push_call_kwargs = mock_push_worktree.call_args[1]
        assert push_call_kwargs['cwd'] == worktree_path

    @patch('git_operations.validate_git_repo')
    @patch('git_operations.check_git_config')
    @patch('git_operations.detect_merge_conflict')
    @patch('git_operations.has_uncommitted_changes')
    def test_auto_commit_and_push_worktree_nothing_to_commit(
        self,
        mock_has_changes,
        mock_conflict,
        mock_config,
        mock_validate,
    ):
        """Test worktree workflow handles nothing to commit gracefully."""
        # Arrange: No changes to commit
        mock_validate.return_value = (True, '')
        mock_config.return_value = (True, '')
        mock_conflict.return_value = (False, [])
        mock_has_changes.return_value = False

        # Act
        result = auto_commit_and_push_worktree(
            commit_message='feat: feature',
            branch='batch-branch',
            push=True
        )

        # Assert
        assert result['success'] is True  # Not an error
        assert result['commit_sha'] == ''
        assert result['pushed'] is False
        assert 'nothing to commit' in result['error'].lower()

    @patch('git_operations.validate_git_repo')
    @patch('git_operations.check_git_config')
    @patch('git_operations.detect_merge_conflict')
    @patch('git_operations.has_uncommitted_changes')
    @patch('git_operations.stage_all_changes')
    @patch('git_operations.commit_changes')
    @patch('git_operations.get_remote_name')
    @patch('git_operations.push_worktree_branch')
    def test_auto_commit_and_push_worktree_push_fails_gracefully(
        self,
        mock_push_worktree,
        mock_get_remote,
        mock_commit,
        mock_stage,
        mock_has_changes,
        mock_conflict,
        mock_config,
        mock_validate,
    ):
        """Test worktree workflow handles push failure gracefully (commit succeeds)."""
        # Arrange: Commit succeeds, push fails
        mock_validate.return_value = (True, '')
        mock_config.return_value = (True, '')
        mock_conflict.return_value = (False, [])
        mock_has_changes.return_value = True
        mock_stage.return_value = (True, '')
        mock_commit.return_value = (True, 'abc1234', '')
        mock_get_remote.return_value = 'origin'
        mock_push_worktree.return_value = (False, 'Network timeout')

        # Act
        result = auto_commit_and_push_worktree(
            commit_message='feat: feature',
            branch='batch-branch',
            push=True
        )

        # Assert: Commit succeeded, push failed
        assert result['success'] is True
        assert result['commit_sha'] == 'abc1234'
        assert result['pushed'] is False
        assert 'network timeout' in result['error'].lower()
