"""
Unit tests for Issue #333: batch_git_finalize.py library

Tests for post-batch git finalization: commit, merge, cleanup operations.

These tests follow TDD - they should FAIL until implementation is complete.

Run with: pytest tests/unit/lib/test_batch_git_finalize.py --tb=line -q
"""

import subprocess
import sys
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import pytest

# Add library to path
sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "plugins" / "autonomous-dev" / "lib"))

from batch_git_finalize import batch_git_finalize, cleanup_worktree, commit_batch_changes


class TestCommitBatchChanges:
    """Test suite for commit_batch_changes helper function."""

    @pytest.fixture
    def git_repo(self, tmp_path: Path) -> Path:
        """Create a real git repository for testing."""
        repo_dir = tmp_path / "test_repo"
        repo_dir.mkdir()

        # Initialize git repo
        subprocess.run(["git", "init"], cwd=repo_dir, check=True, capture_output=True)
        subprocess.run(
            ["git", "config", "user.name", "Test User"],
            cwd=repo_dir,
            check=True,
            capture_output=True,
        )
        subprocess.run(
            ["git", "config", "user.email", "test@example.com"],
            cwd=repo_dir,
            check=True,
            capture_output=True,
        )

        # Create initial commit
        (repo_dir / "README.md").write_text("# Test Repo")
        subprocess.run(["git", "add", "."], cwd=repo_dir, check=True, capture_output=True)
        subprocess.run(
            ["git", "commit", "-m", "Initial commit"],
            cwd=repo_dir,
            check=True,
            capture_output=True,
        )

        return repo_dir

    @pytest.fixture
    def worktree_dir(self, git_repo: Path, tmp_path: Path) -> Path:
        """Create a git worktree for testing."""
        worktree_path = tmp_path / "worktree"

        subprocess.run(
            ["git", "worktree", "add", str(worktree_path), "-b", "batch-test"],
            cwd=git_repo,
            check=True,
            capture_output=True,
        )

        return worktree_path

    def test_commits_all_staged_changes(self, worktree_dir: Path):
        """
        GIVEN: Worktree with staged changes
        WHEN: commit_batch_changes is called
        THEN: All staged changes are committed successfully
        """
        # Create and stage changes
        test_file = worktree_dir / "feature1.py"
        test_file.write_text("def feature1():\n    pass\n")
        subprocess.run(
            ["git", "add", str(test_file)],
            cwd=worktree_dir,
            check=True,
            capture_output=True,
        )

        # Execute
        success, commit_sha, error = commit_batch_changes(
            worktree_dir, features=["Feature 1"]
        )

        # Assert
        assert success is True, f"Commit failed: {error}"
        assert commit_sha is not None, "Commit SHA should be returned"
        assert len(commit_sha) == 40, "Commit SHA should be 40 characters"
        assert error is None, "No error should be returned on success"

        # Verify commit exists with feature in message body
        result = subprocess.run(
            ["git", "log", "-1", "--pretty=%B"],
            cwd=worktree_dir,
            capture_output=True,
            text=True,
        )
        assert "Feature 1" in result.stdout

    def test_commit_message_includes_feature_names(self, worktree_dir: Path):
        """
        GIVEN: Multiple features in batch
        WHEN: commit_batch_changes is called
        THEN: Commit message includes all feature names
        """
        # Create and stage changes
        (worktree_dir / "f1.py").write_text("# Feature 1")
        (worktree_dir / "f2.py").write_text("# Feature 2")
        subprocess.run(["git", "add", "."], cwd=worktree_dir, check=True, capture_output=True)

        # Execute
        features = ["Add user authentication", "Fix database connection"]
        success, commit_sha, error = commit_batch_changes(worktree_dir, features=features)

        # Assert
        assert success is True

        # Check commit message
        result = subprocess.run(
            ["git", "log", "-1", "--pretty=%B"],
            cwd=worktree_dir,
            capture_output=True,
            text=True,
        )
        commit_msg = result.stdout.strip()

        assert "Add user authentication" in commit_msg
        assert "Fix database connection" in commit_msg

    def test_commit_message_includes_closes_issue_numbers(self, worktree_dir: Path):
        """
        GIVEN: Issue numbers associated with batch
        WHEN: commit_batch_changes is called with issue_numbers
        THEN: Commit message includes "Closes #N" for each issue
        """
        # Create and stage changes
        (worktree_dir / "fix.py").write_text("# Fix")
        subprocess.run(["git", "add", "."], cwd=worktree_dir, check=True, capture_output=True)

        # Execute
        success, commit_sha, error = commit_batch_changes(
            worktree_dir, features=["Fix bug"], issue_numbers=[123, 456]
        )

        # Assert
        assert success is True

        # Check commit message
        result = subprocess.run(
            ["git", "log", "-1", "--pretty=%B"],
            cwd=worktree_dir,
            capture_output=True,
            text=True,
        )
        commit_msg = result.stdout.strip()

        assert "Closes #123" in commit_msg
        assert "Closes #456" in commit_msg

    def test_no_changes_returns_success_with_no_sha(self, worktree_dir: Path):
        """
        GIVEN: Worktree with no staged changes
        WHEN: commit_batch_changes is called
        THEN: Returns success=True with commit_sha=None (nothing to commit)
        """
        # Execute (no changes staged)
        success, commit_sha, error = commit_batch_changes(
            worktree_dir, features=["No changes"]
        )

        # Assert
        assert success is True, "Should succeed when nothing to commit"
        assert commit_sha is None, "No SHA when nothing committed"
        assert error is None

    def test_empty_features_list_still_commits(self, worktree_dir: Path):
        """
        GIVEN: Empty features list but staged changes
        WHEN: commit_batch_changes is called
        THEN: Commits with generic message
        """
        # Create and stage changes
        (worktree_dir / "file.py").write_text("# Code")
        subprocess.run(["git", "add", "."], cwd=worktree_dir, check=True, capture_output=True)

        # Execute
        success, commit_sha, error = commit_batch_changes(worktree_dir, features=[])

        # Assert
        assert success is True
        assert commit_sha is not None

        # Check commit message
        result = subprocess.run(
            ["git", "log", "-1", "--pretty=%B"],
            cwd=worktree_dir,
            capture_output=True,
            text=True,
        )
        commit_msg = result.stdout.strip()

        # Should have generic message like "Batch changes"
        assert len(commit_msg) > 0


class TestBatchGitFinalize:
    """Test suite for batch_git_finalize main function."""

    @pytest.fixture
    def git_repo(self, tmp_path: Path) -> Path:
        """Create a real git repository for testing."""
        repo_dir = tmp_path / "test_repo"
        repo_dir.mkdir()

        # Initialize git repo
        subprocess.run(["git", "init"], cwd=repo_dir, check=True, capture_output=True)
        subprocess.run(
            ["git", "config", "user.name", "Test User"],
            cwd=repo_dir,
            check=True,
            capture_output=True,
        )
        subprocess.run(
            ["git", "config", "user.email", "test@example.com"],
            cwd=repo_dir,
            check=True,
            capture_output=True,
        )

        # Create initial commit on master
        (repo_dir / "README.md").write_text("# Test Repo")
        subprocess.run(["git", "add", "."], cwd=repo_dir, check=True, capture_output=True)
        subprocess.run(
            ["git", "commit", "-m", "Initial commit"],
            cwd=repo_dir,
            check=True,
            capture_output=True,
        )

        return repo_dir

    @pytest.fixture
    def worktree_dir(self, git_repo: Path, tmp_path: Path) -> Path:
        """Create a git worktree for testing."""
        worktree_path = tmp_path / "worktree"

        subprocess.run(
            ["git", "worktree", "add", str(worktree_path), "-b", "batch-features"],
            cwd=git_repo,
            check=True,
            capture_output=True,
        )

        return worktree_path

    def test_full_finalize_success(self, git_repo: Path, worktree_dir: Path):
        """
        GIVEN: Worktree with changes to finalize
        WHEN: batch_git_finalize is called with cleanup=True
        THEN: Commits changes, merges to master, removes worktree
        """

        # Create changes in worktree
        (worktree_dir / "feature.py").write_text("def feature():\n    pass\n")
        subprocess.run(["git", "add", "."], cwd=worktree_dir, check=True, capture_output=True)

        # Execute
        result = batch_git_finalize(
            worktree_path=worktree_dir,
            features=["Add feature"],
            target_branch="master",
            cleanup=True,
        )

        # Assert
        assert result["success"] is True, f"Finalize failed: {result.get('error')}"
        assert result["commit_sha"] is not None
        assert result["merged"] is True
        assert result["worktree_removed"] is True
        assert result["conflicts"] == []
        assert result["error"] is None

        # Verify merge commit is in master
        result_check = subprocess.run(
            ["git", "log", "--oneline", "-3"],
            cwd=git_repo,
            capture_output=True,
            text=True,
        )
        assert "batch" in result_check.stdout.lower() or "merge" in result_check.stdout.lower()

        # Verify worktree is gone
        assert not worktree_dir.exists()

    def test_finalize_with_conflicts_leaves_worktree(self, git_repo: Path, worktree_dir: Path):
        """
        GIVEN: Changes that will cause merge conflicts
        WHEN: batch_git_finalize attempts merge
        THEN: Reports conflicts, leaves worktree intact, merged=False
        """

        # Create conflicting changes in master
        (git_repo / "conflict.py").write_text("master version")
        subprocess.run(["git", "add", "."], cwd=git_repo, check=True, capture_output=True)
        subprocess.run(
            ["git", "commit", "-m", "Master change"],
            cwd=git_repo,
            check=True,
            capture_output=True,
        )

        # Create conflicting changes in worktree
        (worktree_dir / "conflict.py").write_text("worktree version")
        subprocess.run(["git", "add", "."], cwd=worktree_dir, check=True, capture_output=True)

        # Execute
        result = batch_git_finalize(
            worktree_path=worktree_dir,
            features=["Conflicting feature"],
            target_branch="master",
            cleanup=True,
        )

        # Assert
        assert result["success"] is False, "Should fail due to conflicts"
        assert result["merged"] is False
        assert result["worktree_removed"] is False
        assert len(result["conflicts"]) > 0
        assert "conflict.py" in result["conflicts"]
        assert result["error"] is not None

        # Verify worktree still exists
        assert worktree_dir.exists()

    def test_finalize_with_issue_numbers(self, git_repo: Path, worktree_dir: Path):
        """
        GIVEN: Batch with associated GitHub issue numbers
        WHEN: batch_git_finalize is called with issue_numbers
        THEN: Commit message includes "Closes #N" references
        """

        # Create changes
        (worktree_dir / "fix.py").write_text("# Fix")
        subprocess.run(["git", "add", "."], cwd=worktree_dir, check=True, capture_output=True)

        # Execute
        result = batch_git_finalize(
            worktree_path=worktree_dir,
            features=["Fix bugs"],
            issue_numbers=[100, 200],
            target_branch="master",
            cleanup=False,
        )

        # Assert
        assert result["success"] is True

        # Check commit message
        commit_result = subprocess.run(
            ["git", "log", "-1", "--pretty=%B"],
            cwd=worktree_dir,
            capture_output=True,
            text=True,
        )
        commit_msg = commit_result.stdout

        assert "Closes #100" in commit_msg
        assert "Closes #200" in commit_msg

    def test_finalize_cleanup_false_preserves_worktree(self, git_repo: Path, worktree_dir: Path):
        """
        GIVEN: Successful finalize operation
        WHEN: cleanup=False
        THEN: Worktree is NOT removed after merge
        """

        # Create changes
        (worktree_dir / "keep.py").write_text("# Keep")
        subprocess.run(["git", "add", "."], cwd=worktree_dir, check=True, capture_output=True)

        # Execute
        result = batch_git_finalize(
            worktree_path=worktree_dir,
            features=["Feature"],
            target_branch="master",
            cleanup=False,
        )

        # Assert
        assert result["success"] is True
        assert result["merged"] is True
        assert result["worktree_removed"] is False

        # Verify worktree still exists
        assert worktree_dir.exists()

    def test_finalize_invalid_worktree_returns_error(self, tmp_path: Path):
        """
        GIVEN: Invalid/non-existent worktree path
        WHEN: batch_git_finalize is called
        THEN: Returns error without attempting operations
        """

        invalid_path = tmp_path / "nonexistent"

        # Execute
        result = batch_git_finalize(
            worktree_path=invalid_path,
            features=["Feature"],
            target_branch="master",
        )

        # Assert
        assert result["success"] is False
        assert result["error"] is not None
        assert "not found" in result["error"].lower() or "invalid" in result["error"].lower()
        assert result["commit_sha"] is None
        assert result["merged"] is False

    def test_finalize_auto_stash_when_master_dirty(self, git_repo: Path, worktree_dir: Path):
        """
        GIVEN: Target branch (master) has uncommitted changes
        WHEN: batch_git_finalize with auto_stash=True
        THEN: Stashes changes, performs merge, restores stash
        """

        # Create uncommitted changes in master
        (git_repo / "dirty.py").write_text("# Uncommitted")

        # Create changes in worktree
        (worktree_dir / "feature.py").write_text("# Feature")
        subprocess.run(["git", "add", "."], cwd=worktree_dir, check=True, capture_output=True)

        # Execute
        result = batch_git_finalize(
            worktree_path=worktree_dir,
            features=["Feature"],
            target_branch="master",
            auto_stash=True,
            cleanup=False,
        )

        # Assert
        assert result["success"] is True, f"Should handle dirty master: {result.get('error')}"
        assert result["merged"] is True

        # Verify dirty.py still exists (stash preserved)
        assert (git_repo / "dirty.py").exists()


class TestCleanupWorktree:
    """Test suite for cleanup_worktree helper function."""

    @pytest.fixture
    def git_repo(self, tmp_path: Path) -> Path:
        """Create a real git repository for testing."""
        repo_dir = tmp_path / "test_repo"
        repo_dir.mkdir()

        # Initialize git repo
        subprocess.run(["git", "init"], cwd=repo_dir, check=True, capture_output=True)
        subprocess.run(
            ["git", "config", "user.name", "Test User"],
            cwd=repo_dir,
            check=True,
            capture_output=True,
        )
        subprocess.run(
            ["git", "config", "user.email", "test@example.com"],
            cwd=repo_dir,
            check=True,
            capture_output=True,
        )

        # Create initial commit
        (repo_dir / "README.md").write_text("# Test Repo")
        subprocess.run(["git", "add", "."], cwd=repo_dir, check=True, capture_output=True)
        subprocess.run(
            ["git", "commit", "-m", "Initial commit"],
            cwd=repo_dir,
            check=True,
            capture_output=True,
        )

        return repo_dir

    @pytest.fixture
    def worktree_dir(self, git_repo: Path, tmp_path: Path) -> Path:
        """Create a git worktree for testing."""
        worktree_path = tmp_path / "worktree"

        subprocess.run(
            ["git", "worktree", "add", str(worktree_path), "-b", "cleanup-test"],
            cwd=git_repo,
            check=True,
            capture_output=True,
        )

        return worktree_path

    def test_removes_worktree_directory(self, git_repo: Path, worktree_dir: Path):
        """
        GIVEN: Valid worktree
        WHEN: cleanup_worktree is called
        THEN: Worktree directory is removed
        """
        # Verify worktree exists
        assert worktree_dir.exists()

        # Execute (from parent repo, not from within worktree)
        success, error = cleanup_worktree(worktree_dir)

        # Assert
        assert success is True, f"Cleanup failed: {error}"
        assert error is None
        assert not worktree_dir.exists()

    def test_prunes_git_worktrees(self, git_repo: Path, worktree_dir: Path):
        """
        GIVEN: Worktree that will be removed
        WHEN: cleanup_worktree is called
        THEN: Git worktree list is pruned (removes stale references)
        """
        # Execute
        success, error = cleanup_worktree(worktree_dir)

        # Assert
        assert success is True

        # Verify worktree no longer in list
        result = subprocess.run(
            ["git", "worktree", "list"],
            cwd=git_repo,
            capture_output=True,
            text=True,
        )

        assert str(worktree_dir) not in result.stdout

    def test_nonexistent_worktree_returns_error(self, tmp_path: Path):
        """
        GIVEN: Non-existent worktree path
        WHEN: cleanup_worktree is called
        THEN: Returns error (success=False)
        """

        nonexistent = tmp_path / "does_not_exist"

        # Execute
        success, error = cleanup_worktree(nonexistent)

        # Assert
        assert success is False
        assert error is not None
        assert "not found" in error.lower() or "does not exist" in error.lower()

    def test_cleanup_from_outside_worktree(self, git_repo: Path, worktree_dir: Path):
        """
        GIVEN: Worktree to be cleaned up
        WHEN: cleanup_worktree called from parent repo (not from within worktree)
        THEN: Successfully removes worktree
        """
        # Execute from parent repo directory
        original_cwd = Path.cwd()
        try:
            import os

            os.chdir(git_repo)

            success, error = cleanup_worktree(worktree_dir)

            assert success is True, f"Should succeed from outside worktree: {error}"
            assert not worktree_dir.exists()
        finally:
            os.chdir(original_cwd)


class TestEdgeCasesBatchGitFinalize:
    """Edge case tests for batch_git_finalize."""

    @pytest.fixture
    def git_repo(self, tmp_path: Path) -> Path:
        """Create a real git repository for testing."""
        repo_dir = tmp_path / "test_repo"
        repo_dir.mkdir()

        subprocess.run(["git", "init"], cwd=repo_dir, check=True, capture_output=True)
        subprocess.run(
            ["git", "config", "user.name", "Test User"],
            cwd=repo_dir,
            check=True,
            capture_output=True,
        )
        subprocess.run(
            ["git", "config", "user.email", "test@example.com"],
            cwd=repo_dir,
            check=True,
            capture_output=True,
        )

        (repo_dir / "README.md").write_text("# Test Repo")
        subprocess.run(["git", "add", "."], cwd=repo_dir, check=True, capture_output=True)
        subprocess.run(
            ["git", "commit", "-m", "Initial commit"],
            cwd=repo_dir,
            check=True,
            capture_output=True,
        )

        return repo_dir

    def test_empty_features_list(self, git_repo: Path, tmp_path: Path):
        """
        GIVEN: Empty features list
        WHEN: batch_git_finalize is called
        THEN: Still commits with generic message
        """

        worktree_path = tmp_path / "worktree"
        subprocess.run(
            ["git", "worktree", "add", str(worktree_path), "-b", "empty-features"],
            cwd=git_repo,
            check=True,
            capture_output=True,
        )

        (worktree_path / "file.py").write_text("# Code")
        subprocess.run(["git", "add", "."], cwd=worktree_path, check=True, capture_output=True)

        result = batch_git_finalize(
            worktree_path=worktree_path, features=[], cleanup=False
        )

        assert result["success"] is True
        assert result["commit_sha"] is not None

    def test_target_branch_does_not_exist(self, git_repo: Path, tmp_path: Path):
        """
        GIVEN: Non-existent target branch
        WHEN: batch_git_finalize attempts merge
        THEN: Returns error
        """

        worktree_path = tmp_path / "worktree"
        subprocess.run(
            ["git", "worktree", "add", str(worktree_path), "-b", "feature"],
            cwd=git_repo,
            check=True,
            capture_output=True,
        )

        (worktree_path / "file.py").write_text("# Code")
        subprocess.run(["git", "add", "."], cwd=worktree_path, check=True, capture_output=True)

        result = batch_git_finalize(
            worktree_path=worktree_path,
            features=["Feature"],
            target_branch="nonexistent-branch",
            cleanup=False,
        )

        assert result["success"] is False
        assert result["error"] is not None

    def test_worktree_path_is_not_a_git_directory(self, tmp_path: Path):
        """
        GIVEN: Path that is not a git worktree
        WHEN: batch_git_finalize is called
        THEN: Returns error
        """

        not_git = tmp_path / "not_a_git_dir"
        not_git.mkdir()

        result = batch_git_finalize(
            worktree_path=not_git, features=["Feature"], cleanup=False
        )

        assert result["success"] is False
        assert result["error"] is not None

    def test_auto_stash_false_with_dirty_master_fails(self, git_repo: Path, tmp_path: Path):
        """
        GIVEN: Dirty master branch and auto_stash=False
        WHEN: batch_git_finalize attempts merge
        THEN: Merge fails, returns error
        """

        # Create dirty master
        (git_repo / "dirty.py").write_text("# Uncommitted")

        worktree_path = tmp_path / "worktree"
        subprocess.run(
            ["git", "worktree", "add", str(worktree_path), "-b", "feature"],
            cwd=git_repo,
            check=True,
            capture_output=True,
        )

        (worktree_path / "file.py").write_text("# Code")
        subprocess.run(["git", "add", "."], cwd=worktree_path, check=True, capture_output=True)

        result = batch_git_finalize(
            worktree_path=worktree_path,
            features=["Feature"],
            auto_stash=False,
            cleanup=False,
        )

        # Should fail because master is dirty
        assert result["success"] is False
        assert "dirty" in result["error"].lower() or "uncommitted" in result["error"].lower()


class TestIntegrationBatchGitFinalize:
    """Integration tests for complete batch finalization workflow."""

    @pytest.fixture
    def git_repo(self, tmp_path: Path) -> Path:
        """Create a real git repository for testing."""
        repo_dir = tmp_path / "test_repo"
        repo_dir.mkdir()

        subprocess.run(["git", "init"], cwd=repo_dir, check=True, capture_output=True)
        subprocess.run(
            ["git", "config", "user.name", "Test User"],
            cwd=repo_dir,
            check=True,
            capture_output=True,
        )
        subprocess.run(
            ["git", "config", "user.email", "test@example.com"],
            cwd=repo_dir,
            check=True,
            capture_output=True,
        )

        (repo_dir / "README.md").write_text("# Test Repo")
        subprocess.run(["git", "add", "."], cwd=repo_dir, check=True, capture_output=True)
        subprocess.run(
            ["git", "commit", "-m", "Initial commit"],
            cwd=repo_dir,
            check=True,
            capture_output=True,
        )

        return repo_dir

    def test_full_workflow_multiple_features(self, git_repo: Path, tmp_path: Path):
        """
        GIVEN: Batch with multiple features and issues
        WHEN: Complete finalize workflow runs
        THEN: All features committed, merged, worktree cleaned up
        """

        worktree_path = tmp_path / "worktree"
        subprocess.run(
            ["git", "worktree", "add", str(worktree_path), "-b", "batch-multi"],
            cwd=git_repo,
            check=True,
            capture_output=True,
        )

        # Create multiple feature files
        (worktree_path / "auth.py").write_text("def login(): pass")
        (worktree_path / "db.py").write_text("def connect(): pass")
        (worktree_path / "api.py").write_text("def endpoint(): pass")

        subprocess.run(["git", "add", "."], cwd=worktree_path, check=True, capture_output=True)

        # Execute
        result = batch_git_finalize(
            worktree_path=worktree_path,
            features=["Add authentication", "Fix database", "Update API"],
            issue_numbers=[10, 20, 30],
            target_branch="master",
            cleanup=True,
        )

        # Assert
        assert result["success"] is True
        assert result["merged"] is True
        assert result["worktree_removed"] is True

        # Verify files in master
        assert (git_repo / "auth.py").exists()
        assert (git_repo / "db.py").exists()
        assert (git_repo / "api.py").exists()

        # Verify commit messages (merge commit + feature commit)
        commit_result = subprocess.run(
            ["git", "log", "-3", "--pretty=%B"],
            cwd=git_repo,
            capture_output=True,
            text=True,
        )
        all_msgs = commit_result.stdout

        assert "Add authentication" in all_msgs
        assert "Closes #10" in all_msgs
        assert "Closes #20" in all_msgs

    def test_workflow_preserves_master_history(self, git_repo: Path, tmp_path: Path):
        """
        GIVEN: Existing commits in master
        WHEN: Batch is finalized and merged
        THEN: Master history is preserved, batch commits added
        """

        # Add commit to master
        (git_repo / "existing.py").write_text("# Existing")
        subprocess.run(["git", "add", "."], cwd=git_repo, check=True, capture_output=True)
        subprocess.run(
            ["git", "commit", "-m", "Existing feature"],
            cwd=git_repo,
            check=True,
            capture_output=True,
        )

        # Create worktree and add feature
        worktree_path = tmp_path / "worktree"
        subprocess.run(
            ["git", "worktree", "add", str(worktree_path), "-b", "new-feature"],
            cwd=git_repo,
            check=True,
            capture_output=True,
        )

        (worktree_path / "new.py").write_text("# New")
        subprocess.run(["git", "add", "."], cwd=worktree_path, check=True, capture_output=True)

        # Execute
        result = batch_git_finalize(
            worktree_path=worktree_path,
            features=["New feature"],
            cleanup=True,
        )

        # Assert
        assert result["success"] is True

        # Verify both files exist in master
        assert (git_repo / "existing.py").exists()
        assert (git_repo / "new.py").exists()

        # Verify git history
        log_result = subprocess.run(
            ["git", "log", "--oneline"],
            cwd=git_repo,
            capture_output=True,
            text=True,
        )

        assert "Existing feature" in log_result.stdout
        assert "batch" in log_result.stdout.lower() or "merge" in log_result.stdout.lower()


if __name__ == "__main__":
    pytest.main([__file__, "--tb=line", "-q"])
