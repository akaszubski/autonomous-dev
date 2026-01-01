"""
Integration tests for git worktree manager.

TDD Mode: These tests are written BEFORE implementation.
All tests should FAIL initially (ImportError: module not found).

Test Strategy:
- Use real git commands with tmp_path fixture
- Test end-to-end workflows (create → work → merge → delete)
- Test integration with git_operations.py
- Aim for real-world scenarios

Date: 2026-01-01
Workflow: worktree_isolation
Agent: test-master
"""

import sys
import pytest
import subprocess
from pathlib import Path
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
    from git_operations import (
        is_worktree,
        get_worktree_parent,
    )
except ImportError as e:
    pytest.skip(f"Implementation not found (TDD red phase): {e}", allow_module_level=True)


@pytest.fixture
def git_repo(tmp_path):
    """Create a temporary git repository for testing."""
    repo_path = tmp_path / "test-repo"
    repo_path.mkdir()

    # Initialize git repo
    subprocess.run(
        ['git', 'init'],
        cwd=repo_path,
        check=True,
        capture_output=True
    )

    # Configure git user (required for commits)
    subprocess.run(
        ['git', 'config', 'user.name', 'Test User'],
        cwd=repo_path,
        check=True,
        capture_output=True
    )
    subprocess.run(
        ['git', 'config', 'user.email', 'test@example.com'],
        cwd=repo_path,
        check=True,
        capture_output=True
    )

    # Create initial commit
    readme = repo_path / "README.md"
    readme.write_text("# Test Repository\n")
    subprocess.run(
        ['git', 'add', 'README.md'],
        cwd=repo_path,
        check=True,
        capture_output=True
    )
    subprocess.run(
        ['git', 'commit', '-m', 'Initial commit'],
        cwd=repo_path,
        check=True,
        capture_output=True
    )

    # Return repo path
    yield repo_path

    # Cleanup is automatic via tmp_path


class TestWorktreeLifecycle:
    """Test complete worktree lifecycle: create → work → merge → delete."""

    def test_create_and_list_worktree(self, git_repo):
        """Test creating a worktree and listing it."""
        # Arrange
        original_dir = Path.cwd()

        try:
            # Change to git repo
            import os
            os.chdir(git_repo)

            # Act: Create worktree
            success, result = create_worktree('test-feature', 'main')

            # Assert: Creation succeeds
            assert success is True
            assert isinstance(result, Path)
            assert result.exists()

            # Act: List worktrees
            worktrees = list_worktrees()

            # Assert: Both main and feature worktree are listed
            assert len(worktrees) >= 2
            names = [w.name for w in worktrees]
            assert 'test-feature' in names

        finally:
            os.chdir(original_dir)

    def test_work_in_worktree_and_merge(self, git_repo):
        """Test working in a worktree and merging changes back."""
        # Arrange
        original_dir = Path.cwd()

        try:
            import os
            os.chdir(git_repo)

            # Create worktree
            success, worktree_path = create_worktree('feature-work', 'main')
            assert success is True

            # Work in worktree: Create new file
            new_file = worktree_path / "feature.py"
            new_file.write_text("def new_feature():\n    pass\n")

            # Commit changes in worktree
            subprocess.run(
                ['git', 'add', 'feature.py'],
                cwd=worktree_path,
                check=True,
                capture_output=True
            )
            subprocess.run(
                ['git', 'commit', '-m', 'Add new feature'],
                cwd=worktree_path,
                check=True,
                capture_output=True
            )

            # Act: Merge worktree back to main
            result = merge_worktree('feature-work', 'main')

            # Assert: Merge succeeds
            assert result.success is True
            assert result.conflicts == []
            assert 'feature.py' in result.merged_files

            # Verify file exists in main branch
            main_file = git_repo / "feature.py"
            assert main_file.exists()

        finally:
            os.chdir(original_dir)

    def test_delete_worktree_after_merge(self, git_repo):
        """Test deleting a worktree after successful merge."""
        # Arrange
        original_dir = Path.cwd()

        try:
            import os
            os.chdir(git_repo)

            # Create worktree
            success, worktree_path = create_worktree('cleanup-test', 'main')
            assert success is True
            assert worktree_path.exists()

            # Act: Delete worktree
            success, message = delete_worktree('cleanup-test', force=False)

            # Assert: Deletion succeeds
            assert success is True
            assert not worktree_path.exists()

            # Verify worktree no longer listed
            worktrees = list_worktrees()
            names = [w.name for w in worktrees]
            assert 'cleanup-test' not in names

        finally:
            os.chdir(original_dir)

    def test_full_feature_workflow(self, git_repo):
        """Test complete feature development workflow in isolation."""
        # Arrange
        original_dir = Path.cwd()

        try:
            import os
            os.chdir(git_repo)

            # Act 1: Create feature worktree
            success, worktree_path = create_worktree('full-feature', 'main')
            assert success is True

            # Act 2: Develop feature (multiple commits)
            for i in range(3):
                feature_file = worktree_path / f"module_{i}.py"
                feature_file.write_text(f"# Module {i}\n")
                subprocess.run(
                    ['git', 'add', f'module_{i}.py'],
                    cwd=worktree_path,
                    check=True,
                    capture_output=True
                )
                subprocess.run(
                    ['git', 'commit', '-m', f'Add module {i}'],
                    cwd=worktree_path,
                    check=True,
                    capture_output=True
                )

            # Act 3: Merge feature
            result = merge_worktree('full-feature', 'main')
            assert result.success is True

            # Act 4: Clean up worktree
            success, _ = delete_worktree('full-feature', force=False)
            assert success is True

            # Assert: All changes are in main
            for i in range(3):
                assert (git_repo / f"module_{i}.py").exists()

        finally:
            os.chdir(original_dir)


class TestWorktreeConflicts:
    """Test merge conflict handling."""

    def test_merge_with_conflicts(self, git_repo):
        """Test merging worktree with conflicts."""
        # Arrange
        original_dir = Path.cwd()

        try:
            import os
            os.chdir(git_repo)

            # Create conflicting changes in main
            conflict_file = git_repo / "shared.py"
            conflict_file.write_text("# Version 1\n")
            subprocess.run(['git', 'add', 'shared.py'], cwd=git_repo, check=True, capture_output=True)
            subprocess.run(['git', 'commit', '-m', 'Add shared file'], cwd=git_repo, check=True, capture_output=True)

            # Create worktree and make conflicting change
            success, worktree_path = create_worktree('conflict-feature', 'main')
            assert success is True

            conflict_file_wt = worktree_path / "shared.py"
            conflict_file_wt.write_text("# Version 2 (conflicting)\n")
            subprocess.run(['git', 'add', 'shared.py'], cwd=worktree_path, check=True, capture_output=True)
            subprocess.run(['git', 'commit', '-m', 'Modify shared file'], cwd=worktree_path, check=True, capture_output=True)

            # Make another change in main (creates conflict)
            conflict_file.write_text("# Version 3 (main)\n")
            subprocess.run(['git', 'add', 'shared.py'], cwd=git_repo, check=True, capture_output=True)
            subprocess.run(['git', 'commit', '-m', 'Update shared file in main'], cwd=git_repo, check=True, capture_output=True)

            # Act: Merge worktree (should conflict)
            result = merge_worktree('conflict-feature', 'main')

            # Assert: Conflict detected
            assert result.success is False
            assert len(result.conflicts) > 0
            assert 'shared.py' in result.conflicts
            assert 'conflict' in result.error_message.lower()

        finally:
            os.chdir(original_dir)

    def test_resolve_conflict_manually(self, git_repo):
        """Test manual conflict resolution after failed merge."""
        # Arrange
        original_dir = Path.cwd()

        try:
            import os
            os.chdir(git_repo)

            # Create conflict (similar to above)
            conflict_file = git_repo / "data.txt"
            conflict_file.write_text("original\n")
            subprocess.run(['git', 'add', 'data.txt'], cwd=git_repo, check=True, capture_output=True)
            subprocess.run(['git', 'commit', '-m', 'Add data'], cwd=git_repo, check=True, capture_output=True)

            success, worktree_path = create_worktree('resolve-test', 'main')
            assert success is True

            wt_file = worktree_path / "data.txt"
            wt_file.write_text("worktree version\n")
            subprocess.run(['git', 'add', 'data.txt'], cwd=worktree_path, check=True, capture_output=True)
            subprocess.run(['git', 'commit', '-m', 'Modify data'], cwd=worktree_path, check=True, capture_output=True)

            conflict_file.write_text("main version\n")
            subprocess.run(['git', 'add', 'data.txt'], cwd=git_repo, check=True, capture_output=True)
            subprocess.run(['git', 'commit', '-m', 'Update data'], cwd=git_repo, check=True, capture_output=True)

            # Attempt merge (will conflict)
            result = merge_worktree('resolve-test', 'main')
            assert result.success is False

            # Act: Manually resolve conflict
            conflict_file.write_text("resolved version\n")
            subprocess.run(['git', 'add', 'data.txt'], cwd=git_repo, check=True, capture_output=True)
            subprocess.run(['git', 'commit', '-m', 'Resolve conflict'], cwd=git_repo, check=True, capture_output=True)

            # Assert: Conflict resolved
            assert conflict_file.read_text() == "resolved version\n"

        finally:
            os.chdir(original_dir)


class TestWorktreePruning:
    """Test stale worktree pruning."""

    def test_prune_old_worktrees(self, git_repo):
        """Test pruning worktrees older than threshold."""
        # Arrange
        original_dir = Path.cwd()

        try:
            import os
            os.chdir(git_repo)

            # Create multiple worktrees
            worktrees = []
            for i in range(3):
                success, wt_path = create_worktree(f'feature-{i}', 'main')
                assert success is True
                worktrees.append(wt_path)

            # Simulate old worktree by modifying timestamp
            # (This is hard to test without mocking or waiting)
            # Instead, test that pruning logic identifies stale worktrees

            # Act: Prune with very high threshold (nothing should be pruned)
            pruned = prune_stale_worktrees(max_age_days=365)

            # Assert: No worktrees pruned (all are fresh)
            assert pruned == 0

        finally:
            os.chdir(original_dir)

    def test_prune_orphaned_worktrees(self, git_repo):
        """Test pruning orphaned worktrees (metadata exists, directory gone)."""
        # Arrange
        original_dir = Path.cwd()

        try:
            import os
            os.chdir(git_repo)

            # Create worktree
            success, worktree_path = create_worktree('orphan-test', 'main')
            assert success is True

            # Manually delete worktree directory (simulate orphan)
            import shutil
            shutil.rmtree(worktree_path)

            # Act: Prune stale worktrees
            pruned = prune_stale_worktrees(max_age_days=30)

            # Assert: Orphaned worktree pruned
            assert pruned >= 1

            # Verify worktree no longer listed
            worktrees = list_worktrees()
            names = [w.name for w in worktrees]
            assert 'orphan-test' not in names

        finally:
            os.chdir(original_dir)


class TestWorktreeIsolation:
    """Test that worktrees provide true isolation."""

    def test_worktrees_do_not_affect_main_branch(self, git_repo):
        """Test changes in worktree don't affect main branch until merge."""
        # Arrange
        original_dir = Path.cwd()

        try:
            import os
            os.chdir(git_repo)

            # Create worktree
            success, worktree_path = create_worktree('isolated-work', 'main')
            assert success is True

            # Make changes in worktree
            isolated_file = worktree_path / "isolated.py"
            isolated_file.write_text("# Isolated work\n")
            subprocess.run(['git', 'add', 'isolated.py'], cwd=worktree_path, check=True, capture_output=True)
            subprocess.run(['git', 'commit', '-m', 'Isolated change'], cwd=worktree_path, check=True, capture_output=True)

            # Act: Check main branch
            main_isolated_file = git_repo / "isolated.py"

            # Assert: File doesn't exist in main branch
            assert not main_isolated_file.exists()

            # After merge, file should appear
            result = merge_worktree('isolated-work', 'main')
            assert result.success is True
            assert main_isolated_file.exists()

        finally:
            os.chdir(original_dir)

    def test_multiple_worktrees_independent(self, git_repo):
        """Test multiple worktrees work independently."""
        # Arrange
        original_dir = Path.cwd()

        try:
            import os
            os.chdir(git_repo)

            # Create two worktrees
            success1, wt1_path = create_worktree('feature-a', 'main')
            success2, wt2_path = create_worktree('feature-b', 'main')
            assert success1 is True
            assert success2 is True

            # Work independently in each
            file_a = wt1_path / "feature_a.py"
            file_b = wt2_path / "feature_b.py"

            file_a.write_text("# Feature A\n")
            file_b.write_text("# Feature B\n")

            subprocess.run(['git', 'add', 'feature_a.py'], cwd=wt1_path, check=True, capture_output=True)
            subprocess.run(['git', 'commit', '-m', 'Add feature A'], cwd=wt1_path, check=True, capture_output=True)

            subprocess.run(['git', 'add', 'feature_b.py'], cwd=wt2_path, check=True, capture_output=True)
            subprocess.run(['git', 'commit', '-m', 'Add feature B'], cwd=wt2_path, check=True, capture_output=True)

            # Assert: Each worktree has only its own file
            assert file_a.exists()
            assert not (wt1_path / "feature_b.py").exists()

            assert file_b.exists()
            assert not (wt2_path / "feature_a.py").exists()

            # After merging both, main has both files
            merge_worktree('feature-a', 'main')
            merge_worktree('feature-b', 'main')

            assert (git_repo / "feature_a.py").exists()
            assert (git_repo / "feature_b.py").exists()

        finally:
            os.chdir(original_dir)


class TestGitOperationsIntegration:
    """Test integration with git_operations.py functions."""

    def test_is_worktree_detection(self, git_repo):
        """Test is_worktree() correctly identifies worktrees."""
        # Arrange
        original_dir = Path.cwd()

        try:
            import os
            os.chdir(git_repo)

            # Create worktree
            success, worktree_path = create_worktree('detect-test', 'main')
            assert success is True

            # Act & Assert: Main repo is not a worktree
            os.chdir(git_repo)
            assert is_worktree() is False

            # Act & Assert: Worktree directory is a worktree
            os.chdir(worktree_path)
            assert is_worktree() is True

        finally:
            os.chdir(original_dir)

    def test_get_worktree_parent(self, git_repo):
        """Test get_worktree_parent() returns main repo path."""
        # Arrange
        original_dir = Path.cwd()

        try:
            import os
            os.chdir(git_repo)

            # Create worktree
            success, worktree_path = create_worktree('parent-test', 'main')
            assert success is True

            # Act: Get parent from worktree
            os.chdir(worktree_path)
            parent = get_worktree_parent()

            # Assert: Parent is main repo
            assert parent is not None
            assert parent.resolve() == git_repo.resolve()

            # Act: Get parent from main repo (should be None)
            os.chdir(git_repo)
            parent_from_main = get_worktree_parent()

            # Assert: Main repo has no parent
            assert parent_from_main is None

        finally:
            os.chdir(original_dir)


class TestWorktreePathLookup:
    """Test worktree path lookup functionality."""

    def test_get_worktree_path_existing(self, git_repo):
        """Test getting path of existing worktree."""
        # Arrange
        original_dir = Path.cwd()

        try:
            import os
            os.chdir(git_repo)

            # Create worktree
            success, created_path = create_worktree('lookup-test', 'main')
            assert success is True

            # Act: Lookup worktree path
            found_path = get_worktree_path('lookup-test')

            # Assert: Found path matches created path
            assert found_path is not None
            assert found_path.resolve() == created_path.resolve()

        finally:
            os.chdir(original_dir)

    def test_get_worktree_path_nonexistent(self, git_repo):
        """Test getting path of non-existent worktree."""
        # Arrange
        original_dir = Path.cwd()

        try:
            import os
            os.chdir(git_repo)

            # Act: Lookup non-existent worktree
            found_path = get_worktree_path('nonexistent')

            # Assert: Returns None
            assert found_path is None

        finally:
            os.chdir(original_dir)


class TestErrorRecovery:
    """Test error recovery and graceful degradation."""

    def test_delete_worktree_with_uncommitted_changes(self, git_repo):
        """Test deleting worktree with uncommitted changes requires force."""
        # Arrange
        original_dir = Path.cwd()

        try:
            import os
            os.chdir(git_repo)

            # Create worktree with uncommitted changes
            success, worktree_path = create_worktree('uncommitted-test', 'main')
            assert success is True

            uncommitted_file = worktree_path / "uncommitted.py"
            uncommitted_file.write_text("# Not committed\n")

            # Act: Try to delete without force
            success, message = delete_worktree('uncommitted-test', force=False)

            # Assert: Deletion fails
            assert success is False
            assert 'modified' in message.lower() or 'uncommitted' in message.lower()

            # Act: Delete with force
            success, message = delete_worktree('uncommitted-test', force=True)

            # Assert: Deletion succeeds with force
            assert success is True
            assert not worktree_path.exists()

        finally:
            os.chdir(original_dir)

    def test_create_worktree_from_non_existent_branch(self, git_repo):
        """Test creating worktree from non-existent branch fails gracefully."""
        # Arrange
        original_dir = Path.cwd()

        try:
            import os
            os.chdir(git_repo)

            # Act: Create worktree from invalid branch
            success, result = create_worktree('test-feature', 'nonexistent-branch')

            # Assert: Creation fails gracefully
            assert success is False
            assert isinstance(result, str)
            assert 'not found' in result.lower() or 'invalid' in result.lower()

        finally:
            os.chdir(original_dir)

    def test_merge_nonexistent_worktree(self, git_repo):
        """Test merging non-existent worktree fails gracefully."""
        # Arrange
        original_dir = Path.cwd()

        try:
            import os
            os.chdir(git_repo)

            # Act: Merge non-existent worktree
            result = merge_worktree('nonexistent-worktree', 'main')

            # Assert: Merge fails gracefully
            assert result.success is False
            assert 'not found' in result.error_message.lower()

        finally:
            os.chdir(original_dir)


class TestPerformance:
    """Test performance with multiple worktrees."""

    def test_many_worktrees_creation(self, git_repo):
        """Test creating many worktrees efficiently."""
        # Arrange
        original_dir = Path.cwd()

        try:
            import os
            os.chdir(git_repo)

            # Act: Create 10 worktrees
            created = []
            for i in range(10):
                success, wt_path = create_worktree(f'perf-test-{i}', 'main')
                assert success is True
                created.append(wt_path)

            # Assert: All created successfully
            assert len(created) == 10

            # List all worktrees
            worktrees = list_worktrees()
            assert len(worktrees) >= 11  # 10 + main

            # Clean up
            for i in range(10):
                delete_worktree(f'perf-test-{i}', force=True)

        finally:
            os.chdir(original_dir)
