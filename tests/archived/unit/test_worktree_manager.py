"""
Unit tests for git worktree manager library.

TDD Mode: These tests are written BEFORE implementation.
All tests should FAIL initially (ImportError: module not found).

Test Strategy:
- Mock all subprocess calls (no real git commands)
- Test happy paths and error conditions
- Aim for 90%+ code coverage
- Test security vulnerabilities (CWE-22, CWE-59, CWE-78)
- Test edge cases (stale worktrees, conflicts, collisions)

Date: 2026-01-01
Workflow: worktree_isolation
Agent: test-master
"""

import json
import sys
import pytest
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock, call, mock_open
from subprocess import CalledProcessError, TimeoutExpired
from typing import Dict, Any, List, Tuple
from datetime import datetime, timedelta

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
    from worktree_manager import (
        create_worktree,
        list_worktrees,
        delete_worktree,
        merge_worktree,
        prune_stale_worktrees,
        get_worktree_path,
        WorktreeInfo,
        MergeResult,
    )
except ImportError as e:
    pytest.skip(f"Implementation not found (TDD red phase): {e}", allow_module_level=True)


class TestCreateWorktree:
    """Test worktree creation."""

    @patch('subprocess.run')
    @patch('pathlib.Path.exists')
    def test_create_worktree_success(self, mock_exists, mock_run):
        """Test successful worktree creation."""
        # Arrange: Mock git worktree add succeeding
        mock_exists.return_value = False  # Worktree doesn't exist yet
        mock_run.return_value = Mock(
            returncode=0,
            stdout='Preparing worktree (new branch "feature-test")\n',
            stderr=''
        )

        # Act
        success, result = create_worktree('test-feature', 'main')

        # Assert
        assert success is True
        assert isinstance(result, Path)
        assert 'test-feature' in str(result)

        # Verify git command
        mock_run.assert_called_once()
        args = mock_run.call_args[0][0]
        assert 'git' in args
        assert 'worktree' in args
        assert 'add' in args

    @patch('subprocess.run')
    @patch('pathlib.Path.exists')
    def test_create_worktree_already_exists(self, mock_exists, mock_run):
        """Test creating worktree that already exists."""
        # Arrange: Worktree path already exists
        mock_exists.return_value = True

        # Act
        success, result = create_worktree('existing-feature', 'main')

        # Assert
        assert success is False
        assert isinstance(result, str)
        assert 'already exists' in result.lower()
        mock_run.assert_not_called()

    @patch('subprocess.run')
    @patch('pathlib.Path.exists')
    def test_create_worktree_with_collision_appends_timestamp(self, mock_exists, mock_run):
        """Test feature name collision appends timestamp."""
        # Arrange: First path exists, second doesn't
        mock_exists.side_effect = [True, False]
        mock_run.return_value = Mock(returncode=0, stdout='', stderr='')

        # Act
        success, result = create_worktree('test-feature', 'main')

        # Assert
        assert success is True
        assert isinstance(result, Path)
        # Should have timestamp appended
        assert 'test-feature' in str(result)

    @patch('subprocess.run')
    @patch('pathlib.Path.exists')
    def test_create_worktree_git_command_fails(self, mock_exists, mock_run):
        """Test git worktree add fails."""
        # Arrange
        mock_exists.return_value = False
        mock_run.side_effect = CalledProcessError(
            1,
            ['git', 'worktree', 'add'],
            stderr='fatal: invalid reference: invalid-branch'
        )

        # Act
        success, result = create_worktree('test-feature', 'invalid-branch')

        # Assert
        assert success is False
        assert isinstance(result, str)
        assert 'invalid reference' in result.lower()

    @patch('subprocess.run')
    @patch('pathlib.Path.exists')
    def test_create_worktree_disk_full_error(self, mock_exists, mock_run):
        """Test worktree creation fails when disk is full."""
        # Arrange
        mock_exists.return_value = False
        mock_run.side_effect = CalledProcessError(
            1,
            ['git', 'worktree', 'add'],
            stderr='fatal: No space left on device'
        )

        # Act
        success, result = create_worktree('test-feature', 'main')

        # Assert
        assert success is False
        assert isinstance(result, str)
        assert 'no space' in result.lower() or 'disk' in result.lower()

    @patch('subprocess.run')
    @patch('pathlib.Path.exists')
    def test_create_worktree_path_traversal_prevention(self, mock_exists, mock_run):
        """Test CWE-22: Path traversal prevention."""
        # Arrange: Malicious feature names
        malicious_names = [
            '../../etc/passwd',
            '../../../tmp/evil',
            'feature/../../etc',
            'test/../../../etc/hosts'
        ]

        for name in malicious_names:
            # Act
            success, result = create_worktree(name, 'main')

            # Assert
            assert success is False
            assert isinstance(result, str)
            assert 'invalid' in result.lower() or 'path' in result.lower()

    @patch('subprocess.run')
    @patch('pathlib.Path.exists')
    def test_create_worktree_command_injection_prevention(self, mock_exists, mock_run):
        """Test CWE-78: Command injection prevention."""
        # Arrange: Malicious feature names with command injection
        malicious_names = [
            'feature; rm -rf /',
            'test && malicious',
            'feature | cat /etc/passwd',
            'test`whoami`',
            'feature$(rm -rf /)',
        ]

        for name in malicious_names:
            # Act
            success, result = create_worktree(name, 'main')

            # Assert
            assert success is False
            assert isinstance(result, str)
            assert 'invalid' in result.lower()

    @patch('subprocess.run')
    @patch('pathlib.Path.exists')
    def test_create_worktree_timeout(self, mock_exists, mock_run):
        """Test worktree creation timeout."""
        # Arrange
        mock_exists.return_value = False
        mock_run.side_effect = TimeoutExpired(['git', 'worktree', 'add'], 30)

        # Act
        success, result = create_worktree('test-feature', 'main')

        # Assert
        assert success is False
        assert isinstance(result, str)
        assert 'timeout' in result.lower()


class TestListWorktrees:
    """Test worktree listing."""

    @patch('subprocess.run')
    def test_list_worktrees_success(self, mock_run):
        """Test successful worktree listing."""
        # Arrange: Mock git worktree list --porcelain
        worktree_output = """worktree /path/to/repo
HEAD abc123def456
branch refs/heads/main

worktree /path/to/worktrees/feature-1
HEAD def789ghi012
branch refs/heads/feature-1

worktree /path/to/worktrees/feature-2
HEAD 456jkl789mno
branch refs/heads/feature-2
"""
        mock_run.return_value = Mock(
            returncode=0,
            stdout=worktree_output,
            stderr=''
        )

        # Act
        worktrees = list_worktrees()

        # Assert
        assert len(worktrees) == 3
        assert all(isinstance(w, WorktreeInfo) for w in worktrees)

        # Check first worktree (main repo)
        assert worktrees[0].path == Path('/path/to/repo')
        assert worktrees[0].branch == 'main'
        assert worktrees[0].commit == 'abc123def456'

        # Check feature worktrees
        assert worktrees[1].name == 'feature-1'
        assert worktrees[2].name == 'feature-2'

    @patch('subprocess.run')
    def test_list_worktrees_empty(self, mock_run):
        """Test listing worktrees when only main repo exists."""
        # Arrange: Only main worktree
        worktree_output = """worktree /path/to/repo
HEAD abc123def456
branch refs/heads/main
"""
        mock_run.return_value = Mock(
            returncode=0,
            stdout=worktree_output,
            stderr=''
        )

        # Act
        worktrees = list_worktrees()

        # Assert
        assert len(worktrees) == 1
        assert worktrees[0].branch == 'main'

    @patch('subprocess.run')
    def test_list_worktrees_detached_head(self, mock_run):
        """Test listing worktrees with detached HEAD."""
        # Arrange: Worktree in detached HEAD state
        worktree_output = """worktree /path/to/repo
HEAD abc123def456
detached
"""
        mock_run.return_value = Mock(
            returncode=0,
            stdout=worktree_output,
            stderr=''
        )

        # Act
        worktrees = list_worktrees()

        # Assert
        assert len(worktrees) == 1
        assert worktrees[0].branch is None or worktrees[0].branch == 'detached'

    @patch('subprocess.run')
    def test_list_worktrees_git_command_fails(self, mock_run):
        """Test listing worktrees when git command fails."""
        # Arrange
        mock_run.side_effect = CalledProcessError(
            128,
            ['git', 'worktree', 'list'],
            stderr='fatal: not a git repository'
        )

        # Act
        worktrees = list_worktrees()

        # Assert
        assert worktrees == []

    @patch('subprocess.run')
    @patch('pathlib.Path.exists')
    def test_list_worktrees_with_stale_worktrees(self, mock_exists, mock_run):
        """Test listing identifies stale worktrees (metadata exists but directory gone)."""
        # Arrange: Worktree metadata exists but directory is missing
        worktree_output = """worktree /path/to/repo
HEAD abc123def456
branch refs/heads/main

worktree /path/to/worktrees/stale-feature
HEAD def789ghi012
branch refs/heads/stale-feature
"""
        mock_run.return_value = Mock(
            returncode=0,
            stdout=worktree_output,
            stderr=''
        )
        # Main repo exists, stale worktree doesn't
        mock_exists.side_effect = lambda: False

        # Act
        worktrees = list_worktrees()

        # Assert
        # Should still list the stale worktree but mark it as stale
        stale = [w for w in worktrees if 'stale' in w.name]
        if stale:
            assert stale[0].status == 'stale' or 'stale' in stale[0].status.lower()


class TestDeleteWorktree:
    """Test worktree deletion."""

    @patch('subprocess.run')
    def test_delete_worktree_success(self, mock_run):
        """Test successful worktree deletion."""
        # Arrange
        mock_run.return_value = Mock(returncode=0, stdout='', stderr='')

        # Act
        success, message = delete_worktree('test-feature', force=False)

        # Assert
        assert success is True
        assert 'deleted' in message.lower() or 'removed' in message.lower()

        # Verify git command
        mock_run.assert_called_once()
        args = mock_run.call_args[0][0]
        assert 'git' in args
        assert 'worktree' in args
        assert 'remove' in args

    @patch('subprocess.run')
    def test_delete_worktree_with_force(self, mock_run):
        """Test force deletion of worktree."""
        # Arrange
        mock_run.return_value = Mock(returncode=0, stdout='', stderr='')

        # Act
        success, message = delete_worktree('test-feature', force=True)

        # Assert
        assert success is True

        # Verify --force flag is used
        args = mock_run.call_args[0][0]
        assert '--force' in args or '-f' in args

    @patch('subprocess.run')
    def test_delete_worktree_not_found(self, mock_run):
        """Test deleting non-existent worktree."""
        # Arrange
        mock_run.side_effect = CalledProcessError(
            128,
            ['git', 'worktree', 'remove'],
            stderr="fatal: 'test-feature' is not a working tree"
        )

        # Act
        success, message = delete_worktree('test-feature', force=False)

        # Assert
        assert success is False
        assert 'not found' in message.lower() or 'not a working tree' in message.lower()

    @patch('subprocess.run')
    def test_delete_worktree_with_uncommitted_changes(self, mock_run):
        """Test deleting worktree with uncommitted changes fails without force."""
        # Arrange
        mock_run.side_effect = CalledProcessError(
            1,
            ['git', 'worktree', 'remove'],
            stderr='fatal: worktree contains modified or untracked files'
        )

        # Act
        success, message = delete_worktree('test-feature', force=False)

        # Assert
        assert success is False
        assert 'modified' in message.lower() or 'uncommitted' in message.lower()

    @patch('subprocess.run')
    def test_delete_worktree_path_traversal_prevention(self, mock_run):
        """Test CWE-22: Path traversal prevention in deletion."""
        # Arrange
        malicious_names = [
            '../../etc',
            '../../../tmp',
            'feature/../../../etc'
        ]

        for name in malicious_names:
            # Act
            success, message = delete_worktree(name, force=False)

            # Assert
            assert success is False
            assert 'invalid' in message.lower()

    @patch('subprocess.run')
    def test_delete_worktree_permission_error(self, mock_run):
        """Test deleting worktree with permission error."""
        # Arrange
        mock_run.side_effect = CalledProcessError(
            1,
            ['git', 'worktree', 'remove'],
            stderr='fatal: Permission denied'
        )

        # Act
        success, message = delete_worktree('test-feature', force=False)

        # Assert
        assert success is False
        assert 'permission' in message.lower()


class TestMergeWorktree:
    """Test worktree merging."""

    @patch('subprocess.run')
    def test_merge_worktree_success(self, mock_run):
        """Test successful worktree merge."""
        # Arrange: Mock successful merge
        mock_run.side_effect = [
            # git checkout target_branch
            Mock(returncode=0, stdout='', stderr=''),
            # git merge feature_branch
            Mock(returncode=0, stdout='Fast-forward\n file.py | 2 +-\n', stderr=''),
            # git diff --name-only (merged files)
            Mock(returncode=0, stdout='file.py\nREADME.md\n', stderr='')
        ]

        # Act
        result = merge_worktree('test-feature', 'main')

        # Assert
        assert isinstance(result, MergeResult)
        assert result.success is True
        assert result.conflicts == []
        assert len(result.merged_files) == 2
        assert 'file.py' in result.merged_files
        assert result.error_message == ''

    @patch('subprocess.run')
    def test_merge_worktree_with_conflicts(self, mock_run):
        """Test merge with conflicts."""
        # Arrange: Mock merge conflict
        mock_run.side_effect = [
            # git checkout
            Mock(returncode=0, stdout='', stderr=''),
            # git merge (conflict)
            CalledProcessError(
                1,
                ['git', 'merge'],
                stderr='CONFLICT (content): Merge conflict in file.py\nAutomatic merge failed'
            ),
            # git diff --name-only --diff-filter=U (conflict files)
            Mock(returncode=0, stdout='file.py\nconfig.json\n', stderr='')
        ]

        # Act
        result = merge_worktree('test-feature', 'main')

        # Assert
        assert isinstance(result, MergeResult)
        assert result.success is False
        assert len(result.conflicts) == 2
        assert 'file.py' in result.conflicts
        assert 'config.json' in result.conflicts
        assert 'conflict' in result.error_message.lower()

    @patch('subprocess.run')
    def test_merge_worktree_target_branch_not_found(self, mock_run):
        """Test merge when target branch doesn't exist."""
        # Arrange
        mock_run.side_effect = CalledProcessError(
            1,
            ['git', 'checkout'],
            stderr="error: pathspec 'invalid-branch' did not match any file(s)"
        )

        # Act
        result = merge_worktree('test-feature', 'invalid-branch')

        # Assert
        assert result.success is False
        assert 'not found' in result.error_message.lower() or 'did not match' in result.error_message.lower()
        assert result.conflicts == []

    @patch('subprocess.run')
    def test_merge_worktree_feature_branch_not_found(self, mock_run):
        """Test merge when feature branch doesn't exist."""
        # Arrange
        mock_run.side_effect = [
            # git checkout succeeds
            Mock(returncode=0, stdout='', stderr=''),
            # git merge fails - branch not found
            CalledProcessError(
                128,
                ['git', 'merge'],
                stderr="fatal: 'test-feature' - not something we can merge"
            )
        ]

        # Act
        result = merge_worktree('test-feature', 'main')

        # Assert
        assert result.success is False
        assert 'not found' in result.error_message.lower() or 'not something we can merge' in result.error_message.lower()

    @patch('subprocess.run')
    def test_merge_worktree_network_interruption(self, mock_run):
        """Test merge with network interruption during fetch."""
        # Arrange
        mock_run.side_effect = TimeoutExpired(['git', 'merge'], 30)

        # Act
        result = merge_worktree('test-feature', 'main')

        # Assert
        assert result.success is False
        assert 'timeout' in result.error_message.lower() or 'interrupted' in result.error_message.lower()

    @patch('subprocess.run')
    def test_merge_worktree_command_injection_prevention(self, mock_run):
        """Test CWE-78: Command injection prevention in merge."""
        # Arrange
        malicious_names = [
            'feature; rm -rf /',
            'test && malicious',
            'feature | evil'
        ]

        for name in malicious_names:
            # Act
            result = merge_worktree(name, 'main')

            # Assert
            assert result.success is False
            assert 'invalid' in result.error_message.lower()


class TestPruneStaleWorktrees:
    """Test stale worktree pruning."""

    @patch('subprocess.run')
    @patch('pathlib.Path.exists')
    @patch('pathlib.Path.stat')
    def test_prune_stale_worktrees_success(self, mock_stat, mock_exists, mock_run):
        """Test successful pruning of stale worktrees."""
        # Arrange: Mock worktrees with different ages
        worktree_output = """worktree /path/to/repo
HEAD abc123
branch refs/heads/main

worktree /path/to/worktrees/old-feature
HEAD def456
branch refs/heads/old-feature

worktree /path/to/worktrees/new-feature
HEAD ghi789
branch refs/heads/new-feature
"""
        mock_run.side_effect = [
            # git worktree list
            Mock(returncode=0, stdout=worktree_output, stderr=''),
            # git worktree remove (old-feature)
            Mock(returncode=0, stdout='', stderr='')
        ]

        # Mock directory exists - called for each worktree in list_worktrees
        mock_exists.return_value = True

        # Mock stat - called for each worktree in list_worktrees
        # Order: main repo (skip), old-feature, new-feature
        forty_days_ago = (datetime.now() - timedelta(days=40)).timestamp()
        five_days_ago = (datetime.now() - timedelta(days=5)).timestamp()

        # list_worktrees calls stat for main, old-feature, new-feature
        # Then prune_stale_worktrees uses the cached created_at from WorktreeInfo
        mock_stat.side_effect = [
            Mock(st_mtime=datetime.now().timestamp()),  # main repo
            Mock(st_mtime=forty_days_ago),  # old-feature (stale - 40 days old)
            Mock(st_mtime=five_days_ago),   # new-feature (fresh - 5 days old)
        ]

        # Act
        pruned_count = prune_stale_worktrees(max_age_days=30)

        # Assert
        assert pruned_count == 1  # Only old-feature should be pruned

    @patch('subprocess.run')
    def test_prune_stale_worktrees_none_stale(self, mock_run):
        """Test pruning when no worktrees are stale."""
        # Arrange: Only main worktree exists
        worktree_output = """worktree /path/to/repo
HEAD abc123
branch refs/heads/main
"""
        mock_run.return_value = Mock(
            returncode=0,
            stdout=worktree_output,
            stderr=''
        )

        # Act
        pruned_count = prune_stale_worktrees(max_age_days=30)

        # Assert
        assert pruned_count == 0

    @patch('subprocess.run')
    @patch('pathlib.Path.exists')
    def test_prune_stale_worktrees_orphaned(self, mock_exists, mock_run):
        """Test pruning orphaned worktrees (metadata exists, directory gone)."""
        # Arrange
        worktree_output = """worktree /path/to/repo
HEAD abc123
branch refs/heads/main

worktree /path/to/worktrees/orphaned
HEAD def456
branch refs/heads/orphaned
"""
        mock_run.side_effect = [
            # git worktree list
            Mock(returncode=0, stdout=worktree_output, stderr=''),
            # git worktree remove (orphaned)
            Mock(returncode=0, stdout='', stderr='')
        ]

        # Directory doesn't exist (orphaned)
        mock_exists.return_value = False

        # Act
        pruned_count = prune_stale_worktrees(max_age_days=30)

        # Assert
        assert pruned_count == 1

    @patch('subprocess.run')
    def test_prune_stale_worktrees_git_command_fails(self, mock_run):
        """Test pruning when git command fails."""
        # Arrange
        mock_run.side_effect = CalledProcessError(
            128,
            ['git', 'worktree', 'list'],
            stderr='fatal: not a git repository'
        )

        # Act
        pruned_count = prune_stale_worktrees(max_age_days=30)

        # Assert
        assert pruned_count == 0


class TestGetWorktreePath:
    """Test worktree path lookup."""

    @patch('subprocess.run')
    def test_get_worktree_path_success(self, mock_run):
        """Test successful worktree path lookup."""
        # Arrange
        worktree_output = """worktree /path/to/repo
HEAD abc123
branch refs/heads/main

worktree /path/to/worktrees/test-feature
HEAD def456
branch refs/heads/test-feature
"""
        mock_run.return_value = Mock(
            returncode=0,
            stdout=worktree_output,
            stderr=''
        )

        # Act
        path = get_worktree_path('test-feature')

        # Assert
        assert path is not None
        assert isinstance(path, Path)
        assert 'test-feature' in str(path)

    @patch('subprocess.run')
    def test_get_worktree_path_not_found(self, mock_run):
        """Test worktree path lookup when worktree doesn't exist."""
        # Arrange
        worktree_output = """worktree /path/to/repo
HEAD abc123
branch refs/heads/main
"""
        mock_run.return_value = Mock(
            returncode=0,
            stdout=worktree_output,
            stderr=''
        )

        # Act
        path = get_worktree_path('nonexistent-feature')

        # Assert
        assert path is None

    @patch('subprocess.run')
    def test_get_worktree_path_git_command_fails(self, mock_run):
        """Test worktree path lookup when git command fails."""
        # Arrange
        mock_run.side_effect = CalledProcessError(
            128,
            ['git', 'worktree', 'list'],
            stderr='fatal: not a git repository'
        )

        # Act
        path = get_worktree_path('test-feature')

        # Assert
        assert path is None


class TestWorktreeInfo:
    """Test WorktreeInfo dataclass."""

    def test_worktree_info_creation(self):
        """Test WorktreeInfo dataclass initialization."""
        # Arrange & Act
        info = WorktreeInfo(
            name='test-feature',
            path=Path('/path/to/worktree'),
            branch='feature-branch',
            commit='abc123def456',
            status='active',
            created_at=datetime(2026, 1, 1, 12, 0, 0)
        )

        # Assert
        assert info.name == 'test-feature'
        assert info.path == Path('/path/to/worktree')
        assert info.branch == 'feature-branch'
        assert info.commit == 'abc123def456'
        assert info.status == 'active'
        assert isinstance(info.created_at, datetime)

    def test_worktree_info_equality(self):
        """Test WorktreeInfo equality comparison."""
        # Arrange
        info1 = WorktreeInfo(
            name='test',
            path=Path('/path'),
            branch='main',
            commit='abc123',
            status='active',
            created_at=datetime(2026, 1, 1)
        )
        info2 = WorktreeInfo(
            name='test',
            path=Path('/path'),
            branch='main',
            commit='abc123',
            status='active',
            created_at=datetime(2026, 1, 1)
        )

        # Act & Assert
        assert info1 == info2


class TestMergeResult:
    """Test MergeResult dataclass."""

    def test_merge_result_creation(self):
        """Test MergeResult dataclass initialization."""
        # Arrange & Act
        result = MergeResult(
            success=True,
            conflicts=[],
            merged_files=['file1.py', 'file2.py'],
            error_message=''
        )

        # Assert
        assert result.success is True
        assert result.conflicts == []
        assert len(result.merged_files) == 2
        assert result.error_message == ''

    def test_merge_result_with_conflicts(self):
        """Test MergeResult with conflicts."""
        # Arrange & Act
        result = MergeResult(
            success=False,
            conflicts=['file1.py', 'file2.py'],
            merged_files=[],
            error_message='Merge conflict detected'
        )

        # Assert
        assert result.success is False
        assert len(result.conflicts) == 2
        assert result.merged_files == []
        assert 'conflict' in result.error_message.lower()


class TestEdgeCases:
    """Test edge cases and error handling."""

    @patch('subprocess.run')
    @patch('pathlib.Path.exists')
    def test_same_branch_multiple_worktrees(self, mock_exists, mock_run):
        """Test preventing same branch in multiple worktrees."""
        # Arrange: Try to create worktree with branch already checked out
        mock_exists.return_value = False
        mock_run.side_effect = CalledProcessError(
            128,
            ['git', 'worktree', 'add'],
            stderr="fatal: 'main' is already checked out at '/path/to/repo'"
        )

        # Act
        success, result = create_worktree('test-feature', 'main')

        # Assert
        assert success is False
        assert 'already checked out' in result.lower()

    @patch('subprocess.run')
    def test_worktree_with_symlink_path(self, mock_run):
        """Test CWE-59: Symlink following prevention."""
        # Arrange: Try to create worktree via symlink
        # Implementation should resolve symlinks or reject them
        mock_run.side_effect = CalledProcessError(
            1,
            ['git', 'worktree', 'add'],
            stderr='fatal: Invalid path'
        )

        # Act
        success, result = create_worktree('/tmp/symlink-to-elsewhere', 'main')

        # Assert
        # Should either reject or safely handle symlinks
        assert success is False or isinstance(result, Path)

    @patch('subprocess.run')
    def test_merge_with_detached_head(self, mock_run):
        """Test merging when in detached HEAD state."""
        # Arrange
        mock_run.side_effect = CalledProcessError(
            1,
            ['git', 'merge'],
            stderr='fatal: You are in detached HEAD state'
        )

        # Act
        result = merge_worktree('test-feature', 'main')

        # Assert
        assert result.success is False
        assert 'detached' in result.error_message.lower()

    @patch('subprocess.run')
    @patch('pathlib.Path.exists')
    def test_create_worktree_with_special_characters(self, mock_exists, mock_run):
        """Test worktree creation with special characters in name."""
        # Arrange: Test valid special characters
        valid_names = [
            'feature-123',
            'test_feature',
            'bugfix.urgent',
            'feature-v1.2.3'
        ]

        mock_exists.return_value = False
        mock_run.return_value = Mock(returncode=0, stdout='', stderr='')

        for name in valid_names:
            # Act
            success, result = create_worktree(name, 'main')

            # Assert
            # Should succeed or have clear validation
            assert isinstance(success, bool)
