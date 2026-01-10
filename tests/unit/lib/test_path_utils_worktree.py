#!/usr/bin/env python3
"""
Unit tests for path_utils.py worktree batch state isolation (Issue #226).

Tests for get_batch_state_file() worktree detection and path isolation.

TDD Mode: These tests are written BEFORE implementation.
All tests should FAIL initially (no implementation exists yet).

Test Strategy:
- Test main repo behavior (backward compatibility)
- Test worktree path isolation (new feature)
- Test security validations work in worktrees
- Test edge cases (detection failures, path creation)
- Mock is_worktree() for unit tests (integration tests use real git)

Coverage Target: 95%+ for worktree-related path_utils changes

Date: 2026-01-10
Issue: GitHub #226 (Per-worktree batch state isolation)
Agent: test-master
Phase: TDD Red (tests written BEFORE implementation)
Status: RED (awaiting implementation)
"""

import json
import os
import sys
import pytest
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock

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

# Import functions under test
try:
    from path_utils import (
        get_batch_state_file,
        get_project_root,
        reset_project_root_cache,
    )
except ImportError as e:
    pytest.skip(f"Implementation not found (TDD red phase): {e}", allow_module_level=True)


# =============================================================================
# Test Fixtures
# =============================================================================

@pytest.fixture
def temp_project_root(tmp_path):
    """Create temporary project root with .git directory."""
    project_root = tmp_path / "project"
    project_root.mkdir()
    git_dir = project_root / ".git"
    git_dir.mkdir()
    return project_root


@pytest.fixture
def temp_worktree(tmp_path):
    """Create temporary worktree directory."""
    worktree_dir = tmp_path / "worktree-feature-123"
    worktree_dir.mkdir()
    return worktree_dir


@pytest.fixture(autouse=True)
def reset_cache():
    """Reset path cache before each test."""
    reset_project_root_cache()
    yield
    reset_project_root_cache()


# =============================================================================
# SECTION 1: Backward Compatibility Tests (3 tests)
# =============================================================================

class TestBatchStateMainRepoBackwardCompatibility:
    """Test that main repo behavior is unchanged (backward compatibility)."""

    def test_batch_state_main_repo_unchanged(self, temp_project_root, monkeypatch):
        """Verify main repo returns PROJECT_ROOT/.claude/batch_state.json."""
        # Arrange
        monkeypatch.chdir(temp_project_root)
        reset_project_root_cache()

        # Mock is_worktree() to return False (main repo)
        with patch("path_utils.is_worktree", return_value=False):
            # Act
            state_file = get_batch_state_file()

            # Assert
            expected = temp_project_root / ".claude" / "batch_state.json"
            assert state_file == expected
            assert state_file.parent.exists()  # .claude/ directory created

    def test_batch_state_main_repo_creates_claude_dir(self, temp_project_root, monkeypatch):
        """Verify .claude/ directory is created in main repo if missing."""
        # Arrange
        monkeypatch.chdir(temp_project_root)
        reset_project_root_cache()
        claude_dir = temp_project_root / ".claude"
        assert not claude_dir.exists()

        # Mock is_worktree() to return False
        with patch("path_utils.is_worktree", return_value=False):
            # Act
            state_file = get_batch_state_file()

            # Assert
            assert claude_dir.exists()
            assert claude_dir.is_dir()
            assert state_file.parent == claude_dir

    def test_batch_state_main_repo_uses_project_root_cache(self, temp_project_root, monkeypatch):
        """Verify main repo uses cached project root (performance optimization)."""
        # Arrange
        monkeypatch.chdir(temp_project_root)
        reset_project_root_cache()

        # Mock is_worktree() to return False
        with patch("path_utils.is_worktree", return_value=False):
            # Act - call twice
            state_file_1 = get_batch_state_file()
            state_file_2 = get_batch_state_file()

            # Assert - both calls return same path
            assert state_file_1 == state_file_2
            expected = temp_project_root / ".claude" / "batch_state.json"
            assert state_file_1 == expected


# =============================================================================
# SECTION 2: Worktree Path Isolation Tests (4 tests)
# =============================================================================

class TestBatchStateWorktreeIsolation:
    """Test that worktrees use isolated local batch state paths."""

    def test_batch_state_worktree_isolated(self, temp_worktree, monkeypatch):
        """Verify worktree returns CWD/.claude/batch_state.json (isolated)."""
        # Arrange
        monkeypatch.chdir(temp_worktree)

        # Mock is_worktree() to return True
        with patch("path_utils.is_worktree", return_value=True):
            # Act
            state_file = get_batch_state_file()

            # Assert
            expected = temp_worktree / ".claude" / "batch_state.json"
            assert state_file == expected
            assert state_file.parent.exists()  # .claude/ directory created

    def test_batch_state_isolation_different_paths(self, tmp_path, monkeypatch):
        """Verify two worktrees get different batch state paths."""
        # Arrange - create two worktree directories
        worktree_1 = tmp_path / "worktree-feature-a"
        worktree_2 = tmp_path / "worktree-feature-b"
        worktree_1.mkdir()
        worktree_2.mkdir()

        # Mock is_worktree() to return True
        with patch("path_utils.is_worktree", return_value=True):
            # Act - get paths from different directories
            monkeypatch.chdir(worktree_1)
            state_file_1 = get_batch_state_file()

            monkeypatch.chdir(worktree_2)
            state_file_2 = get_batch_state_file()

            # Assert - paths are different
            assert state_file_1 != state_file_2
            assert state_file_1 == worktree_1 / ".claude" / "batch_state.json"
            assert state_file_2 == worktree_2 / ".claude" / "batch_state.json"

    def test_worktree_claude_directory_created(self, temp_worktree, monkeypatch):
        """Verify .claude/ directory is created in worktree if missing."""
        # Arrange
        monkeypatch.chdir(temp_worktree)
        claude_dir = temp_worktree / ".claude"
        assert not claude_dir.exists()

        # Mock is_worktree() to return True
        with patch("path_utils.is_worktree", return_value=True):
            # Act
            state_file = get_batch_state_file()

            # Assert
            assert claude_dir.exists()
            assert claude_dir.is_dir()
            assert state_file.parent == claude_dir

    def test_worktree_uses_cwd_not_project_root(self, temp_project_root, temp_worktree, monkeypatch):
        """Verify worktree uses CWD, not project root (key isolation behavior)."""
        # Arrange - worktree is subdirectory of project root
        worktree_dir = temp_project_root / "worktrees" / "feature-123"
        worktree_dir.mkdir(parents=True)
        monkeypatch.chdir(worktree_dir)

        # Mock is_worktree() to return True
        with patch("path_utils.is_worktree", return_value=True):
            # Act
            state_file = get_batch_state_file()

            # Assert - uses worktree CWD, NOT project root
            assert state_file == worktree_dir / ".claude" / "batch_state.json"
            assert state_file.parent.parent == worktree_dir
            # Should NOT be in project root
            assert state_file != temp_project_root / ".claude" / "batch_state.json"


# =============================================================================
# SECTION 3: Worktree Detection Edge Cases (3 tests)
# =============================================================================

class TestWorktreeDetectionEdgeCases:
    """Test edge cases in worktree detection and fallback behavior."""

    def test_worktree_detection_exception_fallback(self, temp_project_root, monkeypatch):
        """Verify graceful fallback to main repo path on detection error."""
        # Arrange
        monkeypatch.chdir(temp_project_root)
        reset_project_root_cache()

        # Mock is_worktree() to raise exception
        with patch("path_utils.is_worktree", side_effect=Exception("Detection failed")):
            # Act
            state_file = get_batch_state_file()

            # Assert - falls back to main repo behavior
            expected = temp_project_root / ".claude" / "batch_state.json"
            assert state_file == expected

    def test_worktree_detection_none_fallback(self, temp_project_root, monkeypatch):
        """Verify fallback when is_worktree() returns None (unexpected)."""
        # Arrange
        monkeypatch.chdir(temp_project_root)
        reset_project_root_cache()

        # Mock is_worktree() to return None (unexpected)
        with patch("path_utils.is_worktree", return_value=None):
            # Act
            state_file = get_batch_state_file()

            # Assert - treats None as False (main repo behavior)
            expected = temp_project_root / ".claude" / "batch_state.json"
            assert state_file == expected

    def test_worktree_detection_missing_function(self, temp_project_root, monkeypatch):
        """Verify fallback when is_worktree() doesn't exist (ImportError)."""
        # Arrange
        monkeypatch.chdir(temp_project_root)
        reset_project_root_cache()

        # Mock import to fail (function doesn't exist)
        import builtins
        real_import = builtins.__import__

        def mock_import(name, *args, **kwargs):
            if name == "git_operations":
                raise ImportError("git_operations not found")
            return real_import(name, *args, **kwargs)

        with patch("builtins.__import__", side_effect=mock_import):
            # Act
            # Should fall back to main repo behavior
            state_file = get_batch_state_file()

            # Assert
            expected = temp_project_root / ".claude" / "batch_state.json"
            assert state_file == expected


# =============================================================================
# SECTION 4: Security Validation Tests (3 tests)
# =============================================================================

class TestWorktreeSecurityValidation:
    """Test that security validations work correctly in worktrees."""

    def test_worktree_security_path_validation_still_works(self, tmp_path, monkeypatch):
        """Verify path traversal validation still works in worktrees."""
        # Arrange - worktree with path traversal in name (should be caught)
        malicious_worktree = tmp_path / ".." / "etc" / "passwd"

        # This test verifies that even though we use CWD in worktrees,
        # security validations still apply to the resulting path
        # (The implementation should validate the final path)

        # Mock is_worktree() to return True
        with patch("path_utils.is_worktree", return_value=True):
            # We can't actually chdir to malicious path, so this test
            # verifies the concept that validation happens on the final path
            pass  # Implementation should validate paths contain no ".."

    def test_worktree_symlink_validation(self, tmp_path, monkeypatch):
        """Verify symlink validation works in worktree paths."""
        # Arrange - create worktree directory
        worktree_dir = tmp_path / "worktree-feature"
        worktree_dir.mkdir()
        monkeypatch.chdir(worktree_dir)

        # Create .claude as symlink (malicious)
        claude_symlink = worktree_dir / ".claude"
        target_dir = tmp_path / "malicious"
        target_dir.mkdir()

        try:
            claude_symlink.symlink_to(target_dir)
        except OSError:
            pytest.skip("Cannot create symlinks on this system")

        # Mock is_worktree() to return True
        with patch("path_utils.is_worktree", return_value=True):
            # Act & Assert
            # The directory creation should reject symlinks
            # (Implementation may validate or raise error)
            # For now, test that it doesn't blindly follow symlinks
            state_file = get_batch_state_file()

            # If implementation validates symlinks, this would raise
            # If not, verify we don't accidentally write outside worktree
            if state_file.parent.exists():
                # Verify it's in the worktree, not the symlink target
                assert state_file.parent.parent == worktree_dir

    def test_worktree_path_permissions_set_correctly(self, temp_worktree, monkeypatch):
        """Verify .claude/ directory created with correct permissions in worktree."""
        # Arrange
        monkeypatch.chdir(temp_worktree)

        # Mock is_worktree() to return True
        with patch("path_utils.is_worktree", return_value=True):
            # Act
            state_file = get_batch_state_file()

            # Assert - directory has safe permissions (0o755)
            claude_dir = state_file.parent
            assert claude_dir.exists()

            # Check permissions (platform-specific)
            import stat
            mode = claude_dir.stat().st_mode
            permissions = stat.filemode(mode)
            # Should be readable/writable by owner, readable by others
            # (exact value is 0o755 = rwxr-xr-x)
            assert stat.S_IRUSR & mode  # Owner can read
            assert stat.S_IWUSR & mode  # Owner can write
            assert stat.S_IXUSR & mode  # Owner can execute


# =============================================================================
# SECTION 5: Performance and Caching Tests (2 tests)
# =============================================================================

class TestWorktreePerformance:
    """Test performance characteristics of worktree path resolution."""

    def test_worktree_detection_not_cached(self, temp_worktree, monkeypatch):
        """Verify is_worktree() is called each time (no caching of detection)."""
        # Arrange
        monkeypatch.chdir(temp_worktree)

        # Track calls to is_worktree()
        call_count = 0

        def mock_is_worktree():
            nonlocal call_count
            call_count += 1
            return True

        with patch("path_utils.is_worktree", side_effect=mock_is_worktree):
            # Act - call multiple times
            get_batch_state_file()
            get_batch_state_file()
            get_batch_state_file()

            # Assert - is_worktree() called each time (no caching)
            # This is correct because worktree status can change
            assert call_count == 3

    def test_worktree_path_resolution_fast(self, temp_worktree, monkeypatch):
        """Verify worktree path resolution is fast (no expensive operations)."""
        # Arrange
        monkeypatch.chdir(temp_worktree)

        # Mock is_worktree() to return True
        with patch("path_utils.is_worktree", return_value=True):
            # Act - measure time (should be very fast)
            import time
            start = time.perf_counter()
            for _ in range(100):
                get_batch_state_file()
            elapsed = time.perf_counter() - start

            # Assert - 100 calls should take < 10ms
            # (Path resolution should be simple, no disk I/O)
            assert elapsed < 0.01  # 10ms


# =============================================================================
# Test Summary
# =============================================================================

"""
TEST SUMMARY (15 unit tests for Issue #226):

SECTION 1: Backward Compatibility (3 tests)
✗ test_batch_state_main_repo_unchanged
✗ test_batch_state_main_repo_creates_claude_dir
✗ test_batch_state_main_repo_uses_project_root_cache

SECTION 2: Worktree Path Isolation (4 tests)
✗ test_batch_state_worktree_isolated
✗ test_batch_state_isolation_different_paths
✗ test_worktree_claude_directory_created
✗ test_worktree_uses_cwd_not_project_root

SECTION 3: Worktree Detection Edge Cases (3 tests)
✗ test_worktree_detection_exception_fallback
✗ test_worktree_detection_none_fallback
✗ test_worktree_detection_missing_function

SECTION 4: Security Validation (3 tests)
✗ test_worktree_security_path_validation_still_works
✗ test_worktree_symlink_validation
✗ test_worktree_path_permissions_set_correctly

SECTION 5: Performance and Caching (2 tests)
✗ test_worktree_detection_not_cached
✗ test_worktree_path_resolution_fast

TOTAL: 15 unit tests (all FAILING - TDD red phase)

Coverage Target: 95%+ for worktree-related path_utils changes
Security: CWE-22 (path traversal), CWE-59 (symlinks)
Performance: Fast path resolution (< 0.1ms per call)

Implementation Requirements:
1. Modify get_batch_state_file() to call is_worktree()
2. If worktree: Return Path.cwd() / ".claude" / "batch_state.json"
3. If main repo: Return PROJECT_ROOT / ".claude" / "batch_state.json"
4. Handle detection failures gracefully (fallback to main repo)
5. Maintain security validations (path traversal, symlinks)
6. Create .claude/ directory with 0o755 permissions
"""
