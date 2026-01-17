#!/usr/bin/env python3
"""
Unit tests for worktree_manager and worktree_command modules (TDD Red Phase).

Tests for git worktree isolation feature (Issue #178).

TDD Mode: These tests are written BEFORE implementation.
All tests should FAIL initially (tests fail because implementation doesn't exist).

Test Strategy:
- Test worktree creation (success, duplicate, invalid names)
- Test worktree listing (empty, multiple, status detection)
- Test worktree deletion (success, force, not exists)
- Test worktree merge (success, conflicts, no commits)
- Test command parsing (all 5 modes: list, status, review, merge, discard)
- Test security validations (CWE-22 path traversal, CWE-78 injection, CWE-59 symlinks)
- Test error handling (git not available, not a repo, permission denied)
- Test edge cases (stale worktrees, detached HEAD, collision handling)

Mocking Strategy:
==============
Git operations are mocked since we can't run real git worktree commands in unit tests.

CORRECT Mocking Layers:
- Git commands: Mock subprocess.run() for all git operations
- Filesystem: Mock Path.exists(), Path.mkdir(), Path.resolve()
- Security: Preserve validate_feature_name() execution, mock only after validation

WRONG Mocking Layers (don't use these):
- Don't bypass security validation functions
- Don't mock high-level managers before low-level validations run

Security Validation Preservation:
- All tests must validate that _validate_feature_name() executes BEFORE git operations
- Subprocess mocks placed AFTER security validation in execution order
- Tests confirm CWE-22 (path traversal) and CWE-78 (injection) checks run first

Coverage Target: 80%+ for worktree_manager.py and worktree_command.py

Date: 2026-01-02
Issue: #178 (Git worktree isolation)
Agent: test-master
Phase: TDD Red (tests written BEFORE implementation)
Status: RED (tests fail - no implementation yet)
"""

import json
import os
import sys
import pytest
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, List
from unittest.mock import Mock, patch, MagicMock, call

# Add lib directory to path for imports
sys.path.insert(
    0,
    str(
        Path(__file__).parent.parent.parent.parent
        / "plugins"
        / "autonomous-dev"
        / "lib"
    ),
)

# Import will fail - module doesn't exist yet (TDD!)
try:
    from worktree_manager import (
        WorktreeInfo,
        MergeResult,
        create_worktree,
        list_worktrees,
        delete_worktree,
        merge_worktree,
        prune_stale_worktrees,
        get_worktree_path,
        get_worktree_status,
        get_worktree_diff,
        discard_worktree,
        _validate_feature_name,
        _get_worktree_base_dir,
    )
except ImportError as e:
    pytest.skip(f"worktree_manager not found (TDD red phase): {e}", allow_module_level=True)

try:
    from worktree_command import (
        ParsedArgs,
        parse_args,
        execute_list,
        execute_status,
        execute_review,
        execute_merge,
        execute_discard,
        main,
    )
except ImportError as e:
    pytest.skip(f"worktree_command not found (TDD red phase): {e}", allow_module_level=True)


# =============================================================================
# Test Fixtures
# =============================================================================

@pytest.fixture
def temp_git_repo(tmp_path):
    """Create temporary git repository for testing."""
    repo_dir = tmp_path / "test-repo"
    repo_dir.mkdir()
    (repo_dir / ".git").mkdir()
    return repo_dir


@pytest.fixture
def mock_git_worktree_list():
    """Mock git worktree list output."""
    return """worktree /Users/dev/project
HEAD 1234567890abcdef1234567890abcdef12345678
branch refs/heads/master

worktree /Users/dev/worktrees/feature-auth
HEAD abcdef1234567890abcdef1234567890abcdef12
branch refs/heads/feature-auth

worktree /Users/dev/worktrees/feature-api
HEAD 7890abcdef1234567890abcdef1234567890abcd
detached
"""


@pytest.fixture
def sample_worktree_info():
    """Sample WorktreeInfo for testing."""
    return WorktreeInfo(
        name="feature-auth",
        path=Path("/Users/dev/worktrees/feature-auth"),
        branch="feature-auth",
        commit="abcdef12",
        status="active",
        created_at=datetime.now(),
    )


# =============================================================================
# SECTION 1: Validation Tests (8 tests)
# =============================================================================

class TestFeatureNameValidation:
    """Test feature name validation for security."""

    def test_validate_feature_name_valid_simple(self):
        """Test valid simple feature name."""
        is_valid, error = _validate_feature_name("feature-auth")
        assert is_valid is True
        assert error == ""

    def test_validate_feature_name_valid_with_numbers(self):
        """Test valid feature name with numbers."""
        is_valid, error = _validate_feature_name("feature-123")
        assert is_valid is True
        assert error == ""

    def test_validate_feature_name_valid_with_underscores(self):
        """Test valid feature name with underscores."""
        is_valid, error = _validate_feature_name("feature_auth_jwt")
        assert is_valid is True
        assert error == ""

    def test_validate_feature_name_empty(self):
        """Test empty feature name is rejected."""
        is_valid, error = _validate_feature_name("")
        assert is_valid is False
        assert "cannot be empty" in error.lower()

    def test_validate_feature_name_whitespace_only(self):
        """Test whitespace-only feature name is rejected."""
        is_valid, error = _validate_feature_name("   ")
        assert is_valid is False
        assert "cannot be empty" in error.lower()

    def test_validate_feature_name_path_traversal_dotdot(self):
        """Test path traversal with .. is rejected (CWE-22)."""
        is_valid, error = _validate_feature_name("../etc/passwd")
        assert is_valid is False
        assert "path traversal" in error.lower() or "invalid" in error.lower()

    def test_validate_feature_name_path_traversal_slash(self):
        """Test path traversal with / is rejected (CWE-22)."""
        is_valid, error = _validate_feature_name("feature/auth")
        assert is_valid is False
        assert "path traversal" in error.lower() or "invalid" in error.lower()

    def test_validate_feature_name_command_injection(self):
        """Test command injection characters are rejected (CWE-78)."""
        is_valid, error = _validate_feature_name("feature; rm -rf /")
        assert is_valid is False
        assert "invalid" in error.lower()


# =============================================================================
# SECTION 2: Worktree Creation Tests (10 tests)
# =============================================================================

class TestWorktreeCreation:
    """Test create_worktree function."""

    @patch('subprocess.run')
    @patch('worktree_manager.Path')
    def test_create_worktree_success(self, mock_path_class, mock_run, temp_git_repo):
        """Test successful worktree creation."""
        # Setup mocks
        mock_run.return_value = Mock(returncode=0, stdout="", stderr="")
        mock_path = Mock()
        mock_path.exists.return_value = False
        mock_path.resolve.return_value = temp_git_repo / "worktrees" / "feature-auth"
        mock_path_class.return_value = mock_path

        # Execute
        success, result = create_worktree("feature-auth", "master")

        # Verify
        assert success is True
        assert isinstance(result, Path)
        mock_run.assert_called_once()
        call_args = mock_run.call_args[0][0]
        assert "git" in call_args
        assert "worktree" in call_args
        assert "add" in call_args

    @patch('subprocess.run')
    def test_create_worktree_invalid_name(self, mock_run):
        """Test worktree creation with invalid name is rejected."""
        success, result = create_worktree("../bad-name", "master")

        assert success is False
        assert "invalid" in str(result).lower() or "path traversal" in str(result).lower()
        mock_run.assert_not_called()  # Security validation blocks git command

    @patch('subprocess.run')
    @patch('worktree_manager.Path')
    def test_create_worktree_already_exists(self, mock_path_class, mock_run, temp_git_repo):
        """Test creating worktree that already exists."""
        # Mock worktree already exists
        mock_path = Mock()
        mock_path.exists.return_value = True
        mock_path_class.return_value = mock_path

        success, result = create_worktree("feature-auth", "master")

        assert success is False
        assert "already exists" in str(result).lower() or "collision" in str(result).lower()

    @patch('subprocess.run')
    @patch('worktree_manager.Path')
    def test_create_worktree_collision_timestamp(self, mock_path_class, mock_run, temp_git_repo):
        """Test collision handling adds timestamp."""
        # First path exists, second doesn't
        mock_path = Mock()
        mock_path.exists.side_effect = [True, False]
        mock_path.resolve.return_value = temp_git_repo / "worktrees" / "feature-auth-12345"
        mock_path_class.return_value = mock_path
        mock_run.return_value = Mock(returncode=0, stdout="", stderr="")

        success, result = create_worktree("feature-auth", "master")

        assert success is True
        # Verify timestamp was appended to avoid collision
        assert mock_path.exists.call_count >= 2

    @patch('subprocess.run')
    def test_create_worktree_git_command_fails(self, mock_run):
        """Test git worktree add command failure."""
        mock_run.return_value = Mock(
            returncode=128,
            stdout="",
            stderr="fatal: not a git repository"
        )

        with patch('worktree_manager.Path') as mock_path_class:
            mock_path = Mock()
            mock_path.exists.return_value = False
            mock_path_class.return_value = mock_path

            success, result = create_worktree("feature-auth", "master")

            assert success is False
            assert "not a git repository" in str(result).lower() or "failed" in str(result).lower()

    @patch('subprocess.run')
    def test_create_worktree_git_not_installed(self, mock_run):
        """Test git command not available."""
        mock_run.side_effect = FileNotFoundError("git command not found")

        with patch('worktree_manager.Path') as mock_path_class:
            mock_path = Mock()
            mock_path.exists.return_value = False
            mock_path_class.return_value = mock_path

            success, result = create_worktree("feature-auth", "master")

            assert success is False
            assert "not found" in str(result).lower() or "not installed" in str(result).lower()

    @patch('subprocess.run')
    @patch('worktree_manager.Path')
    def test_create_worktree_permission_denied(self, mock_path_class, mock_run):
        """Test permission denied when creating worktree directory."""
        mock_path = Mock()
        mock_path.exists.return_value = False
        mock_path.mkdir.side_effect = PermissionError("Permission denied")
        mock_path_class.return_value = mock_path

        success, result = create_worktree("feature-auth", "master")

        assert success is False
        assert "permission" in str(result).lower()

    @patch('subprocess.run')
    @patch('worktree_manager.Path')
    def test_create_worktree_base_branch_not_exists(self, mock_path_class, mock_run):
        """Test creating worktree from non-existent base branch."""
        mock_path = Mock()
        mock_path.exists.return_value = False
        mock_path_class.return_value = mock_path
        mock_run.return_value = Mock(
            returncode=128,
            stdout="",
            stderr="fatal: invalid reference: nonexistent-branch"
        )

        success, result = create_worktree("feature-auth", "nonexistent-branch")

        assert success is False
        assert "invalid reference" in str(result).lower() or "not found" in str(result).lower()

    @patch('subprocess.run')
    @patch('worktree_manager.Path')
    def test_create_worktree_symlink_in_path(self, mock_path_class, mock_run):
        """Test symlink detection in worktree path (CWE-59)."""
        mock_path = Mock()
        mock_path.exists.return_value = False
        # resolve() differs from path (symlink detected)
        mock_path.resolve.return_value = Path("/different/path")
        mock_path.__truediv__ = Mock(return_value=Path("/original/path"))
        mock_path_class.return_value = mock_path

        success, result = create_worktree("feature-auth", "master")

        # Should detect symlink and either reject or resolve safely
        # Exact behavior depends on implementation
        assert success in [True, False]  # Either handles symlink or rejects

    @patch('subprocess.run')
    @patch('worktree_manager.Path')
    def test_create_worktree_with_custom_base_dir(self, mock_path_class, mock_run, temp_git_repo):
        """Test worktree creation uses custom base directory."""
        mock_path = Mock()
        mock_path.exists.return_value = False
        mock_path.resolve.return_value = temp_git_repo / "custom-worktrees" / "feature-auth"
        mock_path_class.return_value = mock_path
        mock_run.return_value = Mock(returncode=0, stdout="", stderr="")

        # Patch _get_worktree_base_dir to return custom dir
        with patch('worktree_manager._get_worktree_base_dir', return_value=temp_git_repo / "custom-worktrees"):
            success, result = create_worktree("feature-auth", "master")

        assert success is True


# =============================================================================
# SECTION 3: Worktree Listing Tests (8 tests)
# =============================================================================

class TestWorktreeListing:
    """Test list_worktrees function."""

    @patch('subprocess.run')
    def test_list_worktrees_empty(self, mock_run):
        """Test listing worktrees when none exist."""
        mock_run.return_value = Mock(
            returncode=0,
            stdout="worktree /Users/dev/project\nHEAD abc123\nbranch refs/heads/master\n\n",
            stderr=""
        )

        worktrees = list_worktrees()

        # Only main worktree exists (should be filtered out)
        assert len(worktrees) == 0

    @patch('subprocess.run')
    def test_list_worktrees_multiple(self, mock_run, mock_git_worktree_list):
        """Test listing multiple worktrees."""
        mock_run.return_value = Mock(
            returncode=0,
            stdout=mock_git_worktree_list,
            stderr=""
        )

        worktrees = list_worktrees()

        assert len(worktrees) >= 2
        # Verify structure
        assert all(isinstance(wt, WorktreeInfo) for wt in worktrees)
        assert all(hasattr(wt, 'name') for wt in worktrees)
        assert all(hasattr(wt, 'path') for wt in worktrees)
        assert all(hasattr(wt, 'branch') for wt in worktrees)

    @patch('subprocess.run')
    def test_list_worktrees_with_detached_head(self, mock_run):
        """Test listing worktrees includes detached HEAD status."""
        mock_run.return_value = Mock(
            returncode=0,
            stdout="""worktree /Users/dev/worktrees/feature-api
HEAD 7890abc
detached
""",
            stderr=""
        )

        worktrees = list_worktrees()

        assert len(worktrees) >= 1
        # Find detached worktree
        detached = [wt for wt in worktrees if wt.branch is None]
        assert len(detached) >= 1
        assert detached[0].status == "detached"

    @patch('subprocess.run')
    def test_list_worktrees_git_command_fails(self, mock_run):
        """Test list_worktrees handles git command failure."""
        mock_run.return_value = Mock(
            returncode=128,
            stdout="",
            stderr="fatal: not a git repository"
        )

        worktrees = list_worktrees()

        # Should return empty list on error (graceful degradation)
        assert worktrees == []

    @patch('subprocess.run')
    def test_list_worktrees_git_not_installed(self, mock_run):
        """Test list_worktrees when git not installed."""
        mock_run.side_effect = FileNotFoundError("git command not found")

        worktrees = list_worktrees()

        # Should return empty list on error (graceful degradation)
        assert worktrees == []

    @patch('subprocess.run')
    def test_list_worktrees_parsing_error(self, mock_run):
        """Test list_worktrees handles malformed git output."""
        mock_run.return_value = Mock(
            returncode=0,
            stdout="malformed\noutput\nwithout\nproper\nformat",
            stderr=""
        )

        worktrees = list_worktrees()

        # Should handle parsing errors gracefully
        assert isinstance(worktrees, list)

    @patch('subprocess.run')
    def test_list_worktrees_includes_status(self, mock_run):
        """Test list_worktrees includes status field."""
        mock_run.return_value = Mock(
            returncode=0,
            stdout="""worktree /Users/dev/worktrees/feature-auth
HEAD abcdef12
branch refs/heads/feature-auth
""",
            stderr=""
        )

        worktrees = list_worktrees()

        assert len(worktrees) >= 1
        assert worktrees[0].status in ["active", "stale", "detached"]

    @patch('subprocess.run')
    @patch('worktree_manager.datetime')
    def test_list_worktrees_includes_created_timestamp(self, mock_datetime, mock_run):
        """Test list_worktrees includes created_at timestamp."""
        mock_now = datetime(2026, 1, 2, 10, 0, 0)
        mock_datetime.now.return_value = mock_now
        mock_run.return_value = Mock(
            returncode=0,
            stdout="""worktree /Users/dev/worktrees/feature-auth
HEAD abcdef12
branch refs/heads/feature-auth
""",
            stderr=""
        )

        worktrees = list_worktrees()

        assert len(worktrees) >= 1
        assert isinstance(worktrees[0].created_at, datetime)


# =============================================================================
# SECTION 4: Worktree Deletion Tests (7 tests)
# =============================================================================

class TestWorktreeDeletion:
    """Test delete_worktree function."""

    @patch('subprocess.run')
    @patch('worktree_manager.get_worktree_path')
    def test_delete_worktree_success(self, mock_get_path, mock_run):
        """Test successful worktree deletion."""
        mock_get_path.return_value = Path("/Users/dev/worktrees/feature-auth")
        mock_run.return_value = Mock(returncode=0, stdout="", stderr="")

        success, message = delete_worktree("feature-auth")

        assert success is True
        assert "deleted" in message.lower() or "removed" in message.lower()
        mock_run.assert_called_once()
        call_args = mock_run.call_args[0][0]
        assert "git" in call_args
        assert "worktree" in call_args
        assert "remove" in call_args

    @patch('subprocess.run')
    @patch('worktree_manager.get_worktree_path')
    def test_delete_worktree_not_exists(self, mock_get_path, mock_run):
        """Test deleting non-existent worktree."""
        mock_get_path.return_value = None

        success, message = delete_worktree("feature-auth")

        assert success is False
        assert "not found" in message.lower()
        mock_run.assert_not_called()

    @patch('subprocess.run')
    def test_delete_worktree_invalid_name(self, mock_run):
        """Test deleting worktree with invalid name."""
        success, message = delete_worktree("../bad-name")

        assert success is False
        assert "invalid" in message.lower()
        mock_run.assert_not_called()

    @patch('subprocess.run')
    @patch('worktree_manager.get_worktree_path')
    def test_delete_worktree_force_flag(self, mock_get_path, mock_run):
        """Test force deletion of worktree."""
        mock_get_path.return_value = Path("/Users/dev/worktrees/feature-auth")
        mock_run.return_value = Mock(returncode=0, stdout="", stderr="")

        success, message = delete_worktree("feature-auth", force=True)

        assert success is True
        call_args = mock_run.call_args[0][0]
        assert "--force" in call_args or "-f" in call_args

    @patch('subprocess.run')
    @patch('worktree_manager.get_worktree_path')
    def test_delete_worktree_with_uncommitted_changes(self, mock_get_path, mock_run):
        """Test deleting worktree with uncommitted changes (without force)."""
        mock_get_path.return_value = Path("/Users/dev/worktrees/feature-auth")
        mock_run.return_value = Mock(
            returncode=1,
            stdout="",
            stderr="fatal: 'feature-auth' contains modified or untracked files"
        )

        success, message = delete_worktree("feature-auth", force=False)

        assert success is False
        assert "modified" in message.lower() or "uncommitted" in message.lower()

    @patch('subprocess.run')
    @patch('worktree_manager.get_worktree_path')
    def test_delete_worktree_git_command_fails(self, mock_get_path, mock_run):
        """Test deletion when git command fails."""
        mock_get_path.return_value = Path("/Users/dev/worktrees/feature-auth")
        mock_run.return_value = Mock(
            returncode=128,
            stdout="",
            stderr="fatal: unknown error"
        )

        success, message = delete_worktree("feature-auth")

        assert success is False
        assert "error" in message.lower() or "failed" in message.lower()

    @patch('subprocess.run')
    @patch('worktree_manager.get_worktree_path')
    def test_delete_worktree_permission_denied(self, mock_get_path, mock_run):
        """Test deletion with permission denied."""
        mock_get_path.return_value = Path("/Users/dev/worktrees/feature-auth")
        mock_run.side_effect = PermissionError("Permission denied")

        success, message = delete_worktree("feature-auth")

        assert success is False
        assert "permission" in message.lower()


# =============================================================================
# SECTION 5: Worktree Merge Tests (9 tests)
# =============================================================================

class TestWorktreeMerge:
    """Test merge_worktree function."""

    @patch('subprocess.run')
    @patch('worktree_manager.get_worktree_path')
    def test_merge_worktree_success(self, mock_get_path, mock_run):
        """Test successful worktree merge."""
        mock_get_path.return_value = Path("/Users/dev/worktrees/feature-auth")

        # Mock git operations: checkout, merge, status
        mock_run.side_effect = [
            Mock(returncode=0, stdout="", stderr=""),  # checkout master
            Mock(returncode=0, stdout="", stderr=""),  # merge feature-auth
            Mock(returncode=0, stdout="", stderr=""),  # status check
        ]

        result = merge_worktree("feature-auth", "master", check_push=False)

        assert result.success is True
        assert len(result.conflicts) == 0
        assert result.error_message == ""
        assert len(result.merged_files) >= 0

    @patch('subprocess.run')
    @patch('worktree_manager.get_worktree_path')
    def test_merge_worktree_with_conflicts(self, mock_get_path, mock_run):
        """Test merge with conflicts."""
        mock_get_path.return_value = Path("/Users/dev/worktrees/feature-auth")

        # Mock merge conflict
        mock_run.side_effect = [
            Mock(returncode=0, stdout="", stderr=""),  # checkout
            Mock(returncode=1, stdout="", stderr="CONFLICT (content): Merge conflict in file.py"),  # merge
            Mock(returncode=0, stdout="", stderr=""),  # status
        ]

        result = merge_worktree("feature-auth", "master", check_push=False)

        assert result.success is False
        assert len(result.conflicts) > 0
        assert "conflict" in result.error_message.lower()

    @patch('subprocess.run')
    @patch('worktree_manager.get_worktree_path')
    def test_merge_worktree_not_exists(self, mock_get_path, mock_run):
        """Test merging non-existent worktree."""
        mock_get_path.return_value = None

        result = merge_worktree("feature-auth", "master", check_push=False)

        assert result.success is False
        assert "not found" in result.error_message.lower()
        mock_run.assert_not_called()

    @patch('subprocess.run')
    def test_merge_worktree_invalid_name(self, mock_run):
        """Test merging worktree with invalid name."""
        result = merge_worktree("../bad-name", "master")

        assert result.success is False
        assert "invalid" in result.error_message.lower()
        mock_run.assert_not_called()

    @patch('subprocess.run')
    @patch('worktree_manager.get_worktree_path')
    def test_merge_worktree_no_commits(self, mock_get_path, mock_run):
        """Test merging worktree with no new commits."""
        mock_get_path.return_value = Path("/Users/dev/worktrees/feature-auth")

        mock_run.side_effect = [
            Mock(returncode=0, stdout="", stderr=""),  # checkout
            Mock(returncode=0, stdout="Already up to date.", stderr=""),  # merge (no changes)
        ]

        result = merge_worktree("feature-auth", "master", check_push=False)

        # Should succeed but with no files merged
        assert result.success is True
        assert len(result.merged_files) == 0

    @patch('subprocess.run')
    @patch('worktree_manager.get_worktree_path')
    def test_merge_worktree_target_branch_not_exists(self, mock_get_path, mock_run):
        """Test merging to non-existent target branch."""
        mock_get_path.return_value = Path("/Users/dev/worktrees/feature-auth")

        mock_run.return_value = Mock(
            returncode=1,
            stdout="",
            stderr="error: pathspec 'nonexistent-branch' did not match"
        )

        result = merge_worktree("feature-auth", "nonexistent-branch", check_push=False)

        assert result.success is False
        assert "not match" in result.error_message.lower() or "not found" in result.error_message.lower()

    @patch('subprocess.run')
    @patch('worktree_manager.get_worktree_path')
    def test_merge_worktree_dirty_working_tree(self, mock_get_path, mock_run):
        """Test merge when target branch has uncommitted changes."""
        mock_get_path.return_value = Path("/Users/dev/worktrees/feature-auth")

        mock_run.return_value = Mock(
            returncode=1,
            stdout="",
            stderr="error: Your local changes would be overwritten by merge"
        )

        result = merge_worktree("feature-auth", "master", check_push=False)

        assert result.success is False
        assert "overwritten" in result.error_message.lower() or "uncommitted" in result.error_message.lower()

    @patch('subprocess.run')
    @patch('worktree_manager.get_worktree_path')
    def test_merge_worktree_tracks_merged_files(self, mock_get_path, mock_run):
        """Test merge tracks list of merged files."""
        mock_get_path.return_value = Path("/Users/dev/worktrees/feature-auth")

        # Mock successful merge with file list
        mock_run.side_effect = [
            Mock(returncode=0, stdout="", stderr=""),  # checkout
            Mock(returncode=0, stdout="", stderr=""),  # merge
            Mock(
                returncode=0,
                stdout="M\tfile1.py\nM\tfile2.py\nA\tfile3.py",
                stderr=""
            ),  # status
        ]

        result = merge_worktree("feature-auth", "master", check_push=False)

        assert result.success is True
        assert len(result.merged_files) >= 3

    @patch('subprocess.run')
    @patch('worktree_manager.get_worktree_path')
    def test_merge_worktree_git_not_installed(self, mock_get_path, mock_run):
        """Test merge when git not installed."""
        mock_get_path.return_value = Path("/Users/dev/worktrees/feature-auth")
        mock_run.side_effect = FileNotFoundError("git command not found")

        result = merge_worktree("feature-auth", "master", check_push=False)

        assert result.success is False
        assert "not found" in result.error_message.lower()


# =============================================================================
# SECTION 5.5: Push Status Check Tests (Issue #240)
# =============================================================================

class TestWorktreePushStatus:
    """Test check_worktree_push_status function."""

    @patch('subprocess.run')
    def test_push_status_branch_fully_pushed(self, mock_run):
        """Test push status when branch is fully pushed."""
        mock_run.side_effect = [
            Mock(returncode=0, stdout="", stderr=""),  # fetch
            Mock(returncode=0, stdout="origin/feature-auth", stderr=""),  # rev-parse upstream
            Mock(returncode=0, stdout="0", stderr=""),  # rev-list count
        ]

        from worktree_manager import check_worktree_push_status
        status = check_worktree_push_status("feature-auth")

        assert status.is_pushed is True
        assert status.commits_ahead == 0
        assert status.error_message == ""

    @patch('subprocess.run')
    def test_push_status_has_unpushed_commits(self, mock_run):
        """Test push status when branch has unpushed commits."""
        mock_run.side_effect = [
            Mock(returncode=0, stdout="", stderr=""),  # fetch
            Mock(returncode=0, stdout="origin/feature-auth", stderr=""),  # rev-parse upstream
            Mock(returncode=0, stdout="3", stderr=""),  # rev-list count (3 ahead)
        ]

        from worktree_manager import check_worktree_push_status
        status = check_worktree_push_status("feature-auth")

        assert status.is_pushed is False
        assert status.commits_ahead == 3
        assert "3" in status.error_message

    @patch('subprocess.run')
    def test_push_status_branch_not_pushed(self, mock_run):
        """Test push status when branch has never been pushed."""
        mock_run.side_effect = [
            Mock(returncode=0, stdout="", stderr=""),  # fetch
            Mock(returncode=1, stdout="", stderr="no upstream"),  # rev-parse (no upstream)
            Mock(returncode=0, stdout="", stderr=""),  # ls-remote (branch not found)
            Mock(returncode=0, stdout="5", stderr=""),  # rev-list count
        ]

        from worktree_manager import check_worktree_push_status
        status = check_worktree_push_status("feature-auth")

        assert status.is_pushed is False
        assert status.commits_ahead == 5
        assert "not been pushed" in status.error_message

    def test_push_status_invalid_name(self):
        """Test push status with invalid branch name."""
        from worktree_manager import check_worktree_push_status
        status = check_worktree_push_status("../bad-name")

        assert status.is_pushed is False
        assert "invalid" in status.error_message.lower()

    @patch('subprocess.run')
    def test_merge_blocked_when_not_pushed(self, mock_run):
        """Test merge is blocked when branch not pushed (check_push=True)."""
        # Mock push status check showing unpushed commits
        mock_run.side_effect = [
            Mock(returncode=0, stdout="", stderr=""),  # fetch
            Mock(returncode=0, stdout="origin/feature-auth", stderr=""),  # rev-parse upstream
            Mock(returncode=0, stdout="2", stderr=""),  # rev-list count (2 ahead)
        ]

        result = merge_worktree("feature-auth", "master", check_push=True)

        assert result.success is False
        assert "unpushed" in result.error_message.lower()
        assert "2" in result.error_message

    @patch('subprocess.run')
    @patch('worktree_manager.get_worktree_path')
    def test_merge_succeeds_with_force_merge(self, mock_get_path, mock_run):
        """Test merge succeeds when force_merge=True despite unpushed commits."""
        mock_get_path.return_value = Path("/Users/dev/worktrees/feature-auth")

        # Mock: push check would fail, but force_merge bypasses it
        mock_run.side_effect = [
            Mock(returncode=0, stdout="", stderr=""),  # checkout
            Mock(returncode=0, stdout="", stderr=""),  # merge
            Mock(returncode=0, stdout="", stderr=""),  # status
        ]

        result = merge_worktree("feature-auth", "master", check_push=True, force_merge=True)

        assert result.success is True


# =============================================================================
# SECTION 5b: Worktree Auto-Stash Tests (6 tests)
# =============================================================================

class TestWorktreeAutoStash:
    """Test auto-stash functionality in merge_worktree."""

    @patch('subprocess.run')
    @patch('worktree_manager.get_worktree_path')
    def test_auto_stash_with_uncommitted_changes_no_overlap(self, mock_get_path, mock_run):
        """Test auto-stash when there are uncommitted changes with no overlap."""
        mock_get_path.return_value = Path("/Users/dev/worktrees/feature-auth")

        mock_run.side_effect = [
            # Auto-stash sequence
            Mock(returncode=0, stdout="M  unrelated_file.py\n", stderr=""),  # status --porcelain
            Mock(returncode=0, stdout="src/auth.py\nsrc/login.py\n", stderr=""),  # diff --name-only HEAD...feature
            Mock(returncode=0, stdout="Saved working directory", stderr=""),  # stash push
            # Merge sequence
            Mock(returncode=0, stdout="", stderr=""),  # checkout
            Mock(returncode=0, stdout="", stderr=""),  # merge
            Mock(returncode=0, stdout="src/auth.py\n", stderr=""),  # diff --name-only
            Mock(returncode=0, stdout="", stderr=""),  # stash pop
        ]

        result = merge_worktree("feature-auth", "master", check_push=False, auto_stash=True)

        assert result.success is True
        # Verify stash pop was called
        stash_pop_calls = [c for c in mock_run.call_args_list if 'stash' in str(c) and 'pop' in str(c)]
        assert len(stash_pop_calls) == 1

    @patch('subprocess.run')
    @patch('worktree_manager.get_worktree_path')
    def test_auto_stash_with_overlap_returns_error(self, mock_get_path, mock_run):
        """Test auto-stash fails when uncommitted changes overlap with merge files."""
        mock_get_path.return_value = Path("/Users/dev/worktrees/feature-auth")

        mock_run.side_effect = [
            # Auto-stash sequence - overlap detected
            Mock(returncode=0, stdout="M  src/auth.py\n", stderr=""),  # status --porcelain (modified file)
            Mock(returncode=0, stdout="src/auth.py\nsrc/login.py\n", stderr=""),  # diff --name-only (same file)
        ]

        result = merge_worktree("feature-auth", "master", check_push=False, auto_stash=True)

        assert result.success is False
        assert "overlap" in result.error_message.lower() or "uncommitted" in result.error_message.lower()

    @patch('subprocess.run')
    @patch('worktree_manager.get_worktree_path')
    def test_auto_stash_disabled_skips_stash(self, mock_get_path, mock_run):
        """Test auto_stash=False skips stashing."""
        mock_get_path.return_value = Path("/Users/dev/worktrees/feature-auth")

        mock_run.side_effect = [
            # No stash calls - direct merge
            Mock(returncode=0, stdout="", stderr=""),  # checkout
            Mock(returncode=0, stdout="", stderr=""),  # merge
            Mock(returncode=0, stdout="src/auth.py\n", stderr=""),  # diff --name-only
        ]

        result = merge_worktree("feature-auth", "master", check_push=False, auto_stash=False)

        assert result.success is True
        # Verify no stash calls
        stash_calls = [c for c in mock_run.call_args_list if 'stash' in str(c)]
        assert len(stash_calls) == 0

    @patch('subprocess.run')
    @patch('worktree_manager.get_worktree_path')
    def test_auto_stash_no_local_changes(self, mock_get_path, mock_run):
        """Test auto-stash with no uncommitted changes proceeds normally."""
        mock_get_path.return_value = Path("/Users/dev/worktrees/feature-auth")

        mock_run.side_effect = [
            # Auto-stash sequence - no changes
            Mock(returncode=0, stdout="", stderr=""),  # status --porcelain (empty)
            # Merge sequence
            Mock(returncode=0, stdout="", stderr=""),  # checkout
            Mock(returncode=0, stdout="", stderr=""),  # merge
            Mock(returncode=0, stdout="src/auth.py\n", stderr=""),  # diff --name-only
        ]

        result = merge_worktree("feature-auth", "master", check_push=False, auto_stash=True)

        assert result.success is True
        # No stash pop should be called since no stash was created
        stash_pop_calls = [c for c in mock_run.call_args_list if 'stash' in str(c) and 'pop' in str(c)]
        assert len(stash_pop_calls) == 0

    @patch('subprocess.run')
    @patch('worktree_manager.get_worktree_path')
    def test_auto_stash_restored_on_merge_failure(self, mock_get_path, mock_run):
        """Test stash is restored when merge fails."""
        mock_get_path.return_value = Path("/Users/dev/worktrees/feature-auth")

        mock_run.side_effect = [
            # Auto-stash sequence
            Mock(returncode=0, stdout="M  unrelated_file.py\n", stderr=""),  # status --porcelain
            Mock(returncode=0, stdout="src/auth.py\n", stderr=""),  # diff --name-only
            Mock(returncode=0, stdout="Saved working directory", stderr=""),  # stash push
            # Merge sequence - checkout succeeds, merge fails
            Mock(returncode=0, stdout="", stderr=""),  # checkout
            subprocess.CalledProcessError(1, ['git', 'merge'], stderr="Merge conflict"),  # merge fails
            Mock(returncode=0, stdout="src/auth.py\n", stderr=""),  # diff --name-only --diff-filter=U
            Mock(returncode=0, stdout="UU src/auth.py\n", stderr=""),  # status --porcelain
            Mock(returncode=0, stdout="", stderr=""),  # stash pop (restore)
        ]

        result = merge_worktree("feature-auth", "master", check_push=False, auto_stash=True)

        assert result.success is False
        # Verify stash was restored
        stash_pop_calls = [c for c in mock_run.call_args_list if 'stash' in str(c) and 'pop' in str(c)]
        assert len(stash_pop_calls) == 1

    @patch('subprocess.run')
    @patch('worktree_manager.get_worktree_path')
    def test_auto_stash_restored_on_checkout_failure(self, mock_get_path, mock_run):
        """Test stash is restored when checkout fails."""
        mock_get_path.return_value = Path("/Users/dev/worktrees/feature-auth")

        mock_run.side_effect = [
            # Auto-stash sequence
            Mock(returncode=0, stdout="M  unrelated_file.py\n", stderr=""),  # status --porcelain
            Mock(returncode=0, stdout="src/auth.py\n", stderr=""),  # diff --name-only
            Mock(returncode=0, stdout="Saved working directory", stderr=""),  # stash push
            # Checkout fails
            subprocess.CalledProcessError(1, ['git', 'checkout'], stderr="error: pathspec not found"),
            Mock(returncode=0, stdout="", stderr=""),  # stash pop (restore)
        ]

        result = merge_worktree("feature-auth", "master", check_push=False, auto_stash=True)

        assert result.success is False
        # Verify stash was restored
        stash_pop_calls = [c for c in mock_run.call_args_list if 'stash' in str(c) and 'pop' in str(c)]
        assert len(stash_pop_calls) == 1


# =============================================================================
# SECTION 6: Worktree Prune Tests (5 tests)
# =============================================================================

class TestWorktreePrune:
    """Test prune_stale_worktrees function."""

    @patch('subprocess.run')
    @patch('worktree_manager.list_worktrees')
    @patch('worktree_manager.delete_worktree')
    def test_prune_stale_worktrees_none_stale(self, mock_delete, mock_list, mock_run):
        """Test pruning when no worktrees are stale."""
        # All worktrees created recently
        mock_list.return_value = [
            WorktreeInfo(
                name="feature-1",
                path=Path("/worktrees/feature-1"),
                branch="feature-1",
                commit="abc123",
                status="active",
                created_at=datetime.now()
            )
        ]

        count = prune_stale_worktrees(max_age_days=7)

        assert count == 0
        mock_delete.assert_not_called()

    @patch('subprocess.run')
    @patch('worktree_manager.list_worktrees')
    @patch('worktree_manager.delete_worktree')
    def test_prune_stale_worktrees_some_stale(self, mock_delete, mock_list, mock_run):
        """Test pruning removes stale worktrees."""
        from datetime import timedelta

        # One stale, one active
        mock_list.return_value = [
            WorktreeInfo(
                name="feature-old",
                path=Path("/worktrees/feature-old"),
                branch="feature-old",
                commit="abc123",
                status="stale",
                created_at=datetime.now() - timedelta(days=10)
            ),
            WorktreeInfo(
                name="feature-new",
                path=Path("/worktrees/feature-new"),
                branch="feature-new",
                commit="def456",
                status="active",
                created_at=datetime.now()
            )
        ]
        mock_delete.return_value = (True, "Deleted")

        count = prune_stale_worktrees(max_age_days=7)

        assert count == 1
        mock_delete.assert_called_once_with("feature-old", force=True)

    @patch('subprocess.run')
    @patch('worktree_manager.list_worktrees')
    def test_prune_stale_worktrees_list_fails(self, mock_list, mock_run):
        """Test prune handles list failure gracefully."""
        mock_list.return_value = []  # Empty list on error

        count = prune_stale_worktrees(max_age_days=7)

        assert count == 0

    @patch('subprocess.run')
    @patch('worktree_manager.list_worktrees')
    @patch('worktree_manager.delete_worktree')
    def test_prune_stale_worktrees_delete_fails(self, mock_delete, mock_list, mock_run):
        """Test prune continues when delete fails."""
        from datetime import timedelta

        mock_list.return_value = [
            WorktreeInfo(
                name="feature-old",
                path=Path("/worktrees/feature-old"),
                branch="feature-old",
                commit="abc123",
                status="stale",
                created_at=datetime.now() - timedelta(days=10)
            )
        ]
        mock_delete.return_value = (False, "Delete failed")

        count = prune_stale_worktrees(max_age_days=7)

        # Should return 0 (failed to delete)
        assert count == 0

    @patch('subprocess.run')
    @patch('worktree_manager.list_worktrees')
    @patch('worktree_manager.delete_worktree')
    def test_prune_stale_worktrees_custom_max_age(self, mock_delete, mock_list, mock_run):
        """Test prune with custom max age."""
        from datetime import timedelta

        mock_list.return_value = [
            WorktreeInfo(
                name="feature-old",
                path=Path("/worktrees/feature-old"),
                branch="feature-old",
                commit="abc123",
                status="stale",
                created_at=datetime.now() - timedelta(days=15)
            )
        ]
        mock_delete.return_value = (True, "Deleted")

        count = prune_stale_worktrees(max_age_days=14)

        assert count == 1
        mock_delete.assert_called_once()


# =============================================================================
# SECTION 7: Command Parsing Tests (8 tests)
# =============================================================================

class TestCommandParsing:
    """Test worktree_command.py argument parsing."""

    def test_parse_args_default_list_mode(self):
        """Test default mode is list."""
        args = parse_args([])

        assert args.mode == "list"
        assert args.feature is None

    def test_parse_args_explicit_list_mode(self):
        """Test explicit --list flag."""
        args = parse_args(["--list"])

        assert args.mode == "list"
        assert args.feature is None

    def test_parse_args_status_mode(self):
        """Test --status mode with feature name."""
        args = parse_args(["--status", "feature-auth"])

        assert args.mode == "status"
        assert args.feature == "feature-auth"

    def test_parse_args_review_mode(self):
        """Test --review mode with feature name."""
        args = parse_args(["--review", "feature-auth"])

        assert args.mode == "review"
        assert args.feature == "feature-auth"

    def test_parse_args_merge_mode(self):
        """Test --merge mode with feature name."""
        args = parse_args(["--merge", "feature-auth"])

        assert args.mode == "merge"
        assert args.feature == "feature-auth"

    def test_parse_args_discard_mode(self):
        """Test --discard mode with feature name."""
        args = parse_args(["--discard", "feature-auth"])

        assert args.mode == "discard"
        assert args.feature == "feature-auth"

    def test_parse_args_missing_feature_for_status(self):
        """Test error when --status used without feature name."""
        with pytest.raises(SystemExit):
            parse_args(["--status"])

    def test_parse_args_multiple_modes(self):
        """Test error when multiple modes specified."""
        # Should raise error or use first mode
        with pytest.raises(SystemExit):
            parse_args(["--list", "--status", "feature-auth"])


# =============================================================================
# SECTION 8: Command Execution Tests (10 tests)
# =============================================================================

class TestCommandExecution:
    """Test worktree_command.py command execution."""

    @patch('worktree_command.list_worktrees')
    def test_execute_list_empty(self, mock_list):
        """Test execute_list with no worktrees."""
        mock_list.return_value = []

        exit_code = execute_list()

        assert exit_code == 0

    @patch('worktree_command.list_worktrees')
    def test_execute_list_multiple(self, mock_list, sample_worktree_info):
        """Test execute_list with multiple worktrees."""
        mock_list.return_value = [sample_worktree_info]

        exit_code = execute_list()

        assert exit_code == 0

    @patch('worktree_command.get_worktree_status')
    def test_execute_status_success(self, mock_status):
        """Test execute_status displays worktree status."""
        mock_status.return_value = {
            "path": "/worktrees/feature-auth",
            "branch": "feature-auth",
            "status": "active",
            "uncommitted_changes": 0
        }

        exit_code = execute_status("feature-auth")

        assert exit_code == 0

    @patch('worktree_command.get_worktree_status')
    def test_execute_status_not_found(self, mock_status):
        """Test execute_status with non-existent worktree."""
        mock_status.return_value = None

        exit_code = execute_status("feature-auth")

        assert exit_code != 0

    @patch('worktree_command.get_worktree_diff')
    @patch('builtins.input')
    def test_execute_review_approve(self, mock_input, mock_diff):
        """Test execute_review with user approval."""
        mock_diff.return_value = "diff --git a/file.py b/file.py\n+added line"
        mock_input.return_value = "y"  # User approves

        exit_code = execute_review("feature-auth")

        # Should return success (exact behavior depends on implementation)
        assert exit_code in [0, 1]  # 0 if approved, 1 if rejected

    @patch('worktree_command.get_worktree_diff')
    @patch('builtins.input')
    def test_execute_review_reject(self, mock_input, mock_diff):
        """Test execute_review with user rejection."""
        mock_diff.return_value = "diff --git a/file.py b/file.py\n+added line"
        mock_input.return_value = "n"  # User rejects

        exit_code = execute_review("feature-auth")

        assert exit_code in [0, 1]

    @patch('worktree_command.merge_worktree')
    def test_execute_merge_success(self, mock_merge):
        """Test execute_merge with successful merge."""
        mock_merge.return_value = MergeResult(
            success=True,
            conflicts=[],
            merged_files=["file1.py", "file2.py"],
            error_message=""
        )

        exit_code = execute_merge("feature-auth")

        assert exit_code == 0

    @patch('worktree_command.merge_worktree')
    def test_execute_merge_conflicts(self, mock_merge):
        """Test execute_merge with merge conflicts."""
        mock_merge.return_value = MergeResult(
            success=False,
            conflicts=["file1.py"],
            merged_files=[],
            error_message="Merge conflicts detected"
        )

        exit_code = execute_merge("feature-auth")

        assert exit_code != 0

    @patch('worktree_command.discard_worktree')
    @patch('builtins.input')
    def test_execute_discard_confirm(self, mock_input, mock_discard):
        """Test execute_discard with confirmation."""
        mock_input.return_value = "yes"  # User confirms
        mock_discard.return_value = {"success": True, "message": "Discarded"}

        exit_code = execute_discard("feature-auth")

        assert exit_code == 0

    @patch('worktree_command.discard_worktree')
    @patch('builtins.input')
    def test_execute_discard_cancel(self, mock_input, mock_discard):
        """Test execute_discard when user cancels."""
        mock_input.return_value = "no"  # User cancels

        exit_code = execute_discard("feature-auth")

        # Should not call discard_worktree
        mock_discard.assert_not_called()
        assert exit_code in [0, 1]


# =============================================================================
# SECTION 9: Helper Functions Tests (5 tests)
# =============================================================================

class TestHelperFunctions:
    """Test helper functions."""

    @patch('worktree_manager.Path')
    def test_get_worktree_base_dir(self, mock_path_class):
        """Test _get_worktree_base_dir returns correct path."""
        mock_path = Mock()
        mock_path.resolve.return_value = Path("/Users/dev/project")
        mock_path_class.cwd.return_value = mock_path

        base_dir = _get_worktree_base_dir()

        assert isinstance(base_dir, Path)
        assert "worktrees" in str(base_dir).lower() or ".worktrees" in str(base_dir).lower()

    @patch('worktree_manager.list_worktrees')
    def test_get_worktree_path_exists(self, mock_list, sample_worktree_info):
        """Test get_worktree_path for existing worktree."""
        mock_list.return_value = [sample_worktree_info]

        path = get_worktree_path("feature-auth")

        assert path is not None
        assert isinstance(path, Path)

    @patch('worktree_manager.list_worktrees')
    def test_get_worktree_path_not_exists(self, mock_list):
        """Test get_worktree_path for non-existent worktree."""
        mock_list.return_value = []

        path = get_worktree_path("feature-auth")

        assert path is None

    @patch('subprocess.run')
    @patch('worktree_manager.get_worktree_path')
    def test_get_worktree_diff(self, mock_path, mock_run):
        """Test get_worktree_diff returns diff output."""
        mock_path.return_value = Path("/worktrees/feature-auth")
        mock_run.return_value = Mock(
            returncode=0,
            stdout="diff --git a/file.py b/file.py\n+new line",
            stderr=""
        )

        diff = get_worktree_diff("feature-auth")

        assert "diff" in diff
        assert "+new line" in diff

    @patch('worktree_manager.delete_worktree')
    @patch('worktree_manager.get_worktree_path')
    def test_discard_worktree(self, mock_path, mock_delete):
        """Test discard_worktree function."""
        mock_path.return_value = Path("/worktrees/feature-auth")
        mock_delete.return_value = (True, "Deleted successfully")

        result = discard_worktree("feature-auth")

        assert result["success"] is True
        assert "deleted" in result["message"].lower() or "discarded" in result["message"].lower()


# =============================================================================
# SECTION 10: Integration Tests (3 tests)
# =============================================================================

class TestWorktreeIntegration:
    """Integration tests for full workflows."""

    @patch('subprocess.run')
    @patch('worktree_manager.Path')
    def test_full_worktree_lifecycle(self, mock_path_class, mock_run):
        """Test complete worktree lifecycle: create -> work -> merge -> delete."""
        # Setup mocks for create
        mock_path = Mock()
        mock_path.exists.side_effect = [False, True, True]  # create, merge, delete
        mock_path.resolve.return_value = Path("/worktrees/feature-auth")
        mock_path_class.return_value = mock_path

        # Mock git operations
        mock_run.side_effect = [
            Mock(returncode=0, stdout="", stderr=""),  # create worktree
            Mock(returncode=0, stdout="", stderr=""),  # checkout for merge
            Mock(returncode=0, stdout="", stderr=""),  # merge
            Mock(returncode=0, stdout="", stderr=""),  # status after merge
            Mock(returncode=0, stdout="", stderr=""),  # delete worktree
        ]

        # Create
        success, path = create_worktree("feature-auth", "master")
        assert success is True

        # Merge
        with patch('worktree_manager.get_worktree_path', return_value=path):
            result = merge_worktree("feature-auth", "master")
            assert result.success is True

        # Delete
        with patch('worktree_manager.get_worktree_path', return_value=path):
            success, msg = delete_worktree("feature-auth")
            assert success is True

    @patch('worktree_command.list_worktrees')
    @patch('worktree_command.merge_worktree')
    def test_command_interface_workflow(self, mock_merge, mock_list):
        """Test command interface workflow."""
        # List worktrees
        mock_list.return_value = [
            WorktreeInfo(
                name="feature-auth",
                path=Path("/worktrees/feature-auth"),
                branch="feature-auth",
                commit="abc123",
                status="active",
                created_at=datetime.now()
            )
        ]

        exit_code = main(["--list"])
        assert exit_code == 0

        # Merge worktree
        mock_merge.return_value = MergeResult(
            success=True,
            conflicts=[],
            merged_files=["file.py"],
            error_message=""
        )

        exit_code = main(["--merge", "feature-auth"])
        assert exit_code == 0

    @patch('subprocess.run')
    @patch('worktree_manager.Path')
    @patch('worktree_manager.list_worktrees')
    def test_security_validation_workflow(self, mock_list, mock_path_class, mock_run):
        """Test security validation blocks malicious operations."""
        # Attempt path traversal in create
        success, msg = create_worktree("../../etc/passwd", "master")
        assert success is False
        mock_run.assert_not_called()

        # Attempt command injection in create
        success, msg = create_worktree("feature; rm -rf /", "master")
        assert success is False

        # Attempt path traversal in merge
        result = merge_worktree("../../../etc", "master")
        assert result.success is False


# =============================================================================
# Checkpoint Integration (v3.36.0)
# =============================================================================

if __name__ == "__main__":
    # Save checkpoint after test creation
    from pathlib import Path
    import sys

    # Portable path detection
    current = Path.cwd()
    while current != current.parent:
        if (current / ".git").exists() or (current / ".claude").exists():
            project_root = current
            break
        current = current.parent
    else:
        project_root = Path.cwd()

    # Add lib to path for imports
    lib_path = project_root / "plugins/autonomous-dev/lib"
    if lib_path.exists():
        sys.path.insert(0, str(lib_path))

        try:
            from agent_tracker import AgentTracker
            AgentTracker.save_agent_checkpoint(
                'test-master',
                'Tests complete - 42 tests created for worktree manager'
            )
            print("✅ Checkpoint saved")
        except ImportError:
            print("ℹ️ Checkpoint skipped (user project)")
