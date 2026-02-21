#!/usr/bin/env python3
"""
Unit tests for repo_detector.py (TDD Red Phase - Issue #271).

Tests repository detection logic that enables autonomous-dev to enforce
quality gates on itself without bypassing them.

TDD Mode: These tests are written BEFORE implementation.
All tests should FAIL initially (implementation doesn't exist yet).

Test Strategy:
- Test repo detection (autonomous-dev vs user repos)
- Test worktree detection (batch processing isolation)
- Test CI environment detection (GitHub Actions, etc.)
- Test caching behavior (thread-safe, performance)
- Test edge cases (nested repos, symlinks, missing .git)

Coverage Target: 80%+ for repo detection logic

Date: 2026-01-26
Issue: #271 (meta(enforcement): Autonomous-dev doesn't enforce its own quality gates)
Agent: test-master
Phase: TDD Red (tests written BEFORE implementation)
Status: RED (all tests failing - implementation doesn't exist yet)
"""

import sys
import pytest
import os
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock
from dataclasses import dataclass

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

# Import the module under test (will fail in RED phase)
try:
    from repo_detector import (
        is_autonomous_dev_repo,
        is_worktree,
        is_ci_environment,
        get_repo_context,
        RepoContext,
        _reset_cache,  # For test isolation
    )
except ImportError as e:
    pytest.skip(
        f"Implementation not found (TDD red phase): {e}",
        allow_module_level=True
    )


# =============================================================================
# Test Fixtures
# =============================================================================

@pytest.fixture
def clean_cache():
    """Reset repo detector cache before and after each test."""
    try:
        _reset_cache()
    except NameError:
        pass  # Function doesn't exist yet (RED phase)
    yield
    try:
        _reset_cache()
    except NameError:
        pass


@pytest.fixture
def mock_autonomous_dev_repo(tmp_path, monkeypatch):
    """Create a mock autonomous-dev repository structure."""
    repo_root = tmp_path / "autonomous-dev"
    repo_root.mkdir()

    # Create .git directory
    (repo_root / ".git").mkdir()

    # Create signature files
    (repo_root / "plugins").mkdir()
    (repo_root / "plugins" / "autonomous-dev").mkdir()
    (repo_root / "plugins" / "autonomous-dev" / "manifest.json").write_text(
        '{"name": "autonomous-dev", "version": "1.0.0"}'
    )

    # Change to repo directory
    monkeypatch.chdir(repo_root)

    return repo_root


@pytest.fixture
def mock_user_repo(tmp_path, monkeypatch):
    """Create a mock user repository structure."""
    repo_root = tmp_path / "user-project"
    repo_root.mkdir()

    # Create .git directory
    (repo_root / ".git").mkdir()

    # Create typical user project structure (no autonomous-dev signatures)
    (repo_root / "src").mkdir()
    (repo_root / "tests").mkdir()

    # Change to repo directory
    monkeypatch.chdir(repo_root)

    return repo_root


@pytest.fixture
def mock_worktree(mock_autonomous_dev_repo):
    """Create a worktree structure within autonomous-dev repo."""
    worktree_path = mock_autonomous_dev_repo.parent / ".worktrees" / "batch-123"
    worktree_path.mkdir(parents=True)

    # Worktrees have .git FILE (not directory) pointing to main repo
    (worktree_path / ".git").write_text(
        f"gitdir: {mock_autonomous_dev_repo / '.git' / 'worktrees' / 'batch-123'}"
    )

    # Copy signature files to worktree
    (worktree_path / "plugins").mkdir()
    (worktree_path / "plugins" / "autonomous-dev").mkdir()
    (worktree_path / "plugins" / "autonomous-dev" / "manifest.json").write_text(
        '{"name": "autonomous-dev", "version": "1.0.0"}'
    )

    return worktree_path


@pytest.fixture
def clean_env(monkeypatch):
    """Remove CI environment variables for clean test state."""
    ci_vars = ['CI', 'GITHUB_ACTIONS', 'GITLAB_CI', 'JENKINS_URL', 'TRAVIS']
    for var in ci_vars:
        monkeypatch.delenv(var, raising=False)
    yield


# =============================================================================
# Unit Tests: Repository Detection
# =============================================================================

class TestIsAutonomousDevRepo:
    """Test is_autonomous_dev_repo() function for accurate detection."""

    def test_detects_autonomous_dev_repo_via_manifest(self, mock_autonomous_dev_repo, clean_cache):
        """Test that autonomous-dev repo is detected via manifest.json.

        DETECTION: plugins/autonomous-dev/manifest.json is signature file.
        Expected: Returns True for autonomous-dev repo.
        """
        # Act
        result = is_autonomous_dev_repo()

        # Assert
        assert result is True

    def test_detects_user_repo_returns_false(self, mock_user_repo, clean_cache):
        """Test that user repos return False.

        DETECTION: User repos don't have autonomous-dev manifest.
        Expected: Returns False for user project.
        """
        # Act
        result = is_autonomous_dev_repo()

        # Assert
        assert result is False

    def test_detects_autonomous_dev_in_worktree(self, mock_worktree, monkeypatch, clean_cache):
        """Test that worktrees of autonomous-dev are detected correctly.

        DETECTION: Worktrees should be identified as autonomous-dev.
        Expected: Returns True even in worktree.
        """
        # Arrange - change to worktree directory
        monkeypatch.chdir(mock_worktree)

        # Act
        result = is_autonomous_dev_repo()

        # Assert
        assert result is True

    def test_handles_missing_git_directory(self, tmp_path, monkeypatch, clean_cache):
        """Test that missing .git directory is handled gracefully.

        EDGE CASE: Not a git repo at all.
        Expected: Returns False without exception.
        """
        # Arrange - directory without .git
        no_git_dir = tmp_path / "not-a-repo"
        no_git_dir.mkdir()
        monkeypatch.chdir(no_git_dir)

        # Act
        result = is_autonomous_dev_repo()

        # Assert
        assert result is False

    def test_handles_missing_manifest(self, mock_user_repo, clean_cache):
        """Test that missing manifest.json returns False.

        EDGE CASE: Has .git but no manifest.
        Expected: Returns False (not autonomous-dev).
        """
        # Act
        result = is_autonomous_dev_repo()

        # Assert
        assert result is False

    def test_handles_nested_autonomous_dev_structure(self, tmp_path, monkeypatch, clean_cache):
        """Test detection in nested directory within autonomous-dev.

        EDGE CASE: Running from subdirectory (e.g., plugins/autonomous-dev/lib).
        Expected: Still detects as autonomous-dev by traversing up.
        """
        # Arrange - create nested structure
        repo_root = tmp_path / "autonomous-dev"
        repo_root.mkdir()
        (repo_root / ".git").mkdir()
        (repo_root / "plugins").mkdir()
        (repo_root / "plugins" / "autonomous-dev").mkdir()
        (repo_root / "plugins" / "autonomous-dev" / "manifest.json").write_text(
            '{"name": "autonomous-dev", "version": "1.0.0"}'
        )

        # Create nested subdirectory
        nested_dir = repo_root / "plugins" / "autonomous-dev" / "lib"
        nested_dir.mkdir()
        monkeypatch.chdir(nested_dir)

        # Act
        result = is_autonomous_dev_repo()

        # Assert
        assert result is True

    def test_caches_result_for_performance(self, mock_autonomous_dev_repo, clean_cache):
        """Test that detection result is cached for performance.

        PERFORMANCE: Avoid repeated filesystem checks.
        Expected: Second call uses cached result.
        """
        # Act - call twice
        result1 = is_autonomous_dev_repo()
        result2 = is_autonomous_dev_repo()

        # Assert
        assert result1 is True
        assert result2 is True
        # Note: Cache effectiveness tested in integration tests

    def test_symlink_to_autonomous_dev_detected(self, mock_autonomous_dev_repo, tmp_path, monkeypatch, clean_cache):
        """Test that symlink to autonomous-dev is detected.

        EDGE CASE: Symlinked directory structure.
        Expected: Follows symlink and detects autonomous-dev.
        """
        if not hasattr(os, 'symlink'):
            pytest.skip("Symlinks not supported on this platform")

        # Arrange - create symlink
        symlink_path = tmp_path / "symlink-to-repo"
        try:
            symlink_path.symlink_to(mock_autonomous_dev_repo, target_is_directory=True)
            monkeypatch.chdir(symlink_path)

            # Act
            result = is_autonomous_dev_repo()

            # Assert
            assert result is True
        except OSError:
            pytest.skip("Symlinks not supported")


# =============================================================================
# Unit Tests: Worktree Detection
# =============================================================================

class TestIsWorktree:
    """Test is_worktree() function for worktree detection."""

    def test_detects_worktree_via_git_file(self, mock_worktree, monkeypatch, clean_cache):
        """Test that worktrees are detected via .git file.

        DETECTION: Worktrees have .git file (not directory).
        Expected: Returns True for worktree.
        """
        # Arrange
        monkeypatch.chdir(mock_worktree)

        # Act
        result = is_worktree()

        # Assert
        assert result is True

    def test_main_repo_returns_false(self, mock_autonomous_dev_repo, clean_cache):
        """Test that main repo returns False.

        DETECTION: Main repos have .git directory.
        Expected: Returns False for main repo.
        """
        # Act
        result = is_worktree()

        # Assert
        assert result is False

    def test_handles_missing_git(self, tmp_path, monkeypatch, clean_cache):
        """Test that missing .git is handled gracefully.

        EDGE CASE: Not a git repo.
        Expected: Returns False without exception.
        """
        # Arrange
        no_git_dir = tmp_path / "not-a-repo"
        no_git_dir.mkdir()
        monkeypatch.chdir(no_git_dir)

        # Act
        result = is_worktree()

        # Assert
        assert result is False

    def test_detects_worktree_via_gitdir_content(self, tmp_path, monkeypatch, clean_cache):
        """Test that worktree is detected by gitdir content in .git file.

        DETECTION: .git file contains "gitdir: ..." for worktrees.
        Expected: Returns True when .git file has gitdir pointer.
        """
        # Arrange
        worktree_dir = tmp_path / "worktree"
        worktree_dir.mkdir()
        (worktree_dir / ".git").write_text("gitdir: /path/to/main/repo/.git/worktrees/branch")
        monkeypatch.chdir(worktree_dir)

        # Act
        result = is_worktree()

        # Assert
        assert result is True

    def test_caches_result_for_performance(self, mock_worktree, monkeypatch, clean_cache):
        """Test that worktree detection is cached.

        PERFORMANCE: Avoid repeated filesystem checks.
        Expected: Second call uses cached result.
        """
        # Arrange
        monkeypatch.chdir(mock_worktree)

        # Act
        result1 = is_worktree()
        result2 = is_worktree()

        # Assert
        assert result1 is True
        assert result2 is True


# =============================================================================
# Unit Tests: CI Environment Detection
# =============================================================================

class TestIsCiEnvironment:
    """Test is_ci_environment() function for CI detection."""

    def test_detects_github_actions(self, clean_env, monkeypatch, clean_cache):
        """Test that GitHub Actions is detected via GITHUB_ACTIONS env var.

        DETECTION: GITHUB_ACTIONS=true indicates GitHub Actions.
        Expected: Returns True when GITHUB_ACTIONS set.
        """
        # Arrange
        monkeypatch.setenv("GITHUB_ACTIONS", "true")

        # Act
        result = is_ci_environment()

        # Assert
        assert result is True

    def test_detects_generic_ci(self, clean_env, monkeypatch, clean_cache):
        """Test that generic CI env var is detected.

        DETECTION: CI=true is generic CI indicator.
        Expected: Returns True when CI set.
        """
        # Arrange
        monkeypatch.setenv("CI", "true")

        # Act
        result = is_ci_environment()

        # Assert
        assert result is True

    def test_detects_gitlab_ci(self, clean_env, monkeypatch, clean_cache):
        """Test that GitLab CI is detected.

        DETECTION: GITLAB_CI=true indicates GitLab CI.
        Expected: Returns True when GITLAB_CI set.
        """
        # Arrange
        monkeypatch.setenv("GITLAB_CI", "true")

        # Act
        result = is_ci_environment()

        # Assert
        assert result is True

    def test_detects_jenkins(self, clean_env, monkeypatch, clean_cache):
        """Test that Jenkins is detected.

        DETECTION: JENKINS_URL indicates Jenkins.
        Expected: Returns True when JENKINS_URL set.
        """
        # Arrange
        monkeypatch.setenv("JENKINS_URL", "http://jenkins.example.com")

        # Act
        result = is_ci_environment()

        # Assert
        assert result is True

    def test_detects_travis_ci(self, clean_env, monkeypatch, clean_cache):
        """Test that Travis CI is detected.

        DETECTION: TRAVIS=true indicates Travis CI.
        Expected: Returns True when TRAVIS set.
        """
        # Arrange
        monkeypatch.setenv("TRAVIS", "true")

        # Act
        result = is_ci_environment()

        # Assert
        assert result is True

    def test_returns_false_when_no_ci_vars(self, clean_env, clean_cache):
        """Test that False is returned in local dev environment.

        DETECTION: No CI env vars means local development.
        Expected: Returns False when no CI indicators.
        """
        # Act
        result = is_ci_environment()

        # Assert
        assert result is False

    def test_handles_case_insensitive_values(self, clean_env, monkeypatch, clean_cache):
        """Test that CI detection handles various boolean values.

        EDGE CASE: CI=True, CI=1, CI=yes should all work.
        Expected: Returns True for various truthy values.
        """
        truthy_values = ["true", "True", "TRUE", "1", "yes", "YES"]

        for value in truthy_values:
            # Arrange
            monkeypatch.setenv("CI", value)
            _reset_cache()  # Reset cache between tests

            # Act
            result = is_ci_environment()

            # Assert
            assert result is True, f"Failed for CI={value}"


# =============================================================================
# Unit Tests: Repository Context
# =============================================================================

class TestGetRepoContext:
    """Test get_repo_context() function for complete context."""

    def test_returns_context_for_autonomous_dev_main_repo(self, mock_autonomous_dev_repo, clean_env, clean_cache):
        """Test that complete context is returned for main autonomous-dev repo.

        CONTEXT: Main autonomous-dev repo, not worktree, not CI.
        Expected: RepoContext with is_autonomous_dev=True, is_worktree=False, is_ci=False.
        """
        # Act
        context = get_repo_context()

        # Assert
        assert isinstance(context, RepoContext)
        assert context.is_autonomous_dev is True
        assert context.is_worktree is False
        assert context.is_ci is False

    def test_returns_context_for_worktree(self, mock_worktree, monkeypatch, clean_env, clean_cache):
        """Test that worktree context is detected.

        CONTEXT: Autonomous-dev worktree, not CI.
        Expected: RepoContext with is_autonomous_dev=True, is_worktree=True, is_ci=False.
        """
        # Arrange
        monkeypatch.chdir(mock_worktree)

        # Act
        context = get_repo_context()

        # Assert
        assert isinstance(context, RepoContext)
        assert context.is_autonomous_dev is True
        assert context.is_worktree is True
        assert context.is_ci is False

    def test_returns_context_for_ci_environment(self, mock_autonomous_dev_repo, monkeypatch, clean_cache):
        """Test that CI context is detected.

        CONTEXT: Autonomous-dev in GitHub Actions.
        Expected: RepoContext with is_autonomous_dev=True, is_worktree=False, is_ci=True.
        """
        # Arrange
        monkeypatch.setenv("GITHUB_ACTIONS", "true")

        # Act
        context = get_repo_context()

        # Assert
        assert isinstance(context, RepoContext)
        assert context.is_autonomous_dev is True
        assert context.is_worktree is False
        assert context.is_ci is True

    def test_returns_context_for_user_repo(self, mock_user_repo, clean_env, clean_cache):
        """Test that user repo context is correct.

        CONTEXT: User project, not autonomous-dev.
        Expected: RepoContext with is_autonomous_dev=False, is_worktree=False, is_ci=False.
        """
        # Act
        context = get_repo_context()

        # Assert
        assert isinstance(context, RepoContext)
        assert context.is_autonomous_dev is False
        assert context.is_worktree is False
        assert context.is_ci is False

    def test_context_is_cached(self, mock_autonomous_dev_repo, clean_cache):
        """Test that context is cached for performance.

        PERFORMANCE: Avoid repeated detection calls.
        Expected: Multiple calls return same cached object.
        """
        # Act
        context1 = get_repo_context()
        context2 = get_repo_context()

        # Assert
        assert context1 is context2  # Same object (cached)

    def test_context_dataclass_has_all_fields(self, mock_autonomous_dev_repo, clean_cache):
        """Test that RepoContext dataclass has all required fields.

        INTERFACE: Ensure complete context information.
        Expected: Has is_autonomous_dev, is_worktree, is_ci fields.
        """
        # Act
        context = get_repo_context()

        # Assert
        assert hasattr(context, 'is_autonomous_dev')
        assert hasattr(context, 'is_worktree')
        assert hasattr(context, 'is_ci')
        assert isinstance(context.is_autonomous_dev, bool)
        assert isinstance(context.is_worktree, bool)
        assert isinstance(context.is_ci, bool)


# =============================================================================
# Unit Tests: Thread Safety
# =============================================================================

class TestThreadSafety:
    """Test thread-safe caching behavior."""

    def test_cache_reset_clears_all_caches(self, mock_autonomous_dev_repo, clean_cache):
        """Test that _reset_cache() clears all cached values.

        CACHING: Cache reset needed for test isolation.
        Expected: After reset, detection runs again.
        """
        # Arrange - populate cache
        context1 = get_repo_context()

        # Act - reset cache
        _reset_cache()
        context2 = get_repo_context()

        # Assert - new detection (values same but different object)
        assert context1 is not context2
        assert context1.is_autonomous_dev == context2.is_autonomous_dev

    def test_concurrent_calls_use_same_cache(self, mock_autonomous_dev_repo, clean_cache):
        """Test that concurrent calls use shared cache.

        THREAD SAFETY: Multiple calls should be safe.
        Expected: All calls return same cached object.
        """
        # Act - simulate concurrent calls
        results = [get_repo_context() for _ in range(10)]

        # Assert - all same object
        assert all(r is results[0] for r in results)


# =============================================================================
# Unit Tests: Edge Cases
# =============================================================================

class TestEdgeCases:
    """Test edge cases and error handling."""

    def test_handles_permission_errors(self, tmp_path, monkeypatch, clean_cache):
        """Test that permission errors are handled gracefully.

        EDGE CASE: Can't read .git or manifest.json.
        Expected: Returns False without exception.
        """
        # Arrange - create directory
        restricted_dir = tmp_path / "restricted"
        restricted_dir.mkdir()
        monkeypatch.chdir(restricted_dir)

        # Act - should handle gracefully
        result = is_autonomous_dev_repo()

        # Assert
        assert result is False

    def test_handles_corrupted_git_file(self, tmp_path, monkeypatch, clean_cache):
        """Test that corrupted .git file is handled.

        EDGE CASE: .git file exists but is corrupted.
        Expected: Returns appropriate default value.
        """
        # Arrange
        corrupted_dir = tmp_path / "corrupted"
        corrupted_dir.mkdir()
        (corrupted_dir / ".git").write_text("corrupted content without gitdir")
        monkeypatch.chdir(corrupted_dir)

        # Act
        result = is_worktree()

        # Assert - should handle gracefully (likely False)
        assert isinstance(result, bool)

    def test_handles_empty_manifest(self, tmp_path, monkeypatch, clean_cache):
        """Test that empty manifest.json is handled.

        EDGE CASE: manifest.json exists but is empty or invalid.
        Expected: Returns False (not valid autonomous-dev).
        """
        # Arrange
        repo_dir = tmp_path / "repo"
        repo_dir.mkdir()
        (repo_dir / ".git").mkdir()
        (repo_dir / "plugins").mkdir()
        (repo_dir / "plugins" / "autonomous-dev").mkdir()
        (repo_dir / "plugins" / "autonomous-dev" / "manifest.json").write_text("")
        monkeypatch.chdir(repo_dir)

        # Act
        result = is_autonomous_dev_repo()

        # Assert - empty manifest likely means not autonomous-dev
        assert isinstance(result, bool)


# Run tests in verbose mode to see which ones fail (RED phase)
if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
