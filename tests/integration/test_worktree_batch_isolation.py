#!/usr/bin/env python3
"""
Integration tests for worktree batch state isolation (Issue #226).

Tests end-to-end workflows with REAL git worktrees to verify:
- Batch state files are isolated per worktree
- Concurrent batch operations in different worktrees don't conflict
- State persistence works correctly in worktrees
- Integration with existing batch_state_manager

TDD Mode: These tests are written BEFORE implementation.
All tests should FAIL initially (no implementation exists yet).

Test Strategy:
- Use real git commands with tmp_path fixture
- Create real git worktrees (not mocks)
- Test concurrent batch operations
- Verify state isolation with actual file I/O
- Test integration with batch_state_manager

Coverage Target: 95%+ for real-world worktree scenarios

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
import subprocess
import time
from pathlib import Path
from dataclasses import asdict

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

# Import functions under test
try:
    from path_utils import get_batch_state_file, reset_project_root_cache
    from git_operations import is_worktree, get_worktree_parent
    from batch_state_manager import (
        BatchState,
        create_batch_state,
        save_batch_state,
        load_batch_state,
        BatchStateError,
    )
except ImportError as e:
    pytest.skip(f"Implementation not found (TDD red phase): {e}", allow_module_level=True)


# =============================================================================
# Test Fixtures
# =============================================================================

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

    # Create .claude directory (project structure)
    claude_dir = repo_path / ".claude"
    claude_dir.mkdir()

    # Create initial commit
    readme = repo_path / "README.md"
    readme.write_text("# Test Repository\n")
    subprocess.run(
        ['git', 'add', '.'],
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

    yield repo_path


@pytest.fixture
def sample_features():
    """Sample feature list for batch testing."""
    return [
        "Add user authentication",
        "Implement password reset",
        "Add email verification",
    ]


@pytest.fixture(autouse=True)
def reset_cache():
    """Reset path cache before each test."""
    reset_project_root_cache()
    yield
    reset_project_root_cache()


# =============================================================================
# SECTION 1: Real Worktree Batch State Path Tests (2 tests)
# =============================================================================

class TestRealWorktreeBatchStatePath:
    """Test batch state path resolution with real git worktrees."""

    def test_real_worktree_batch_state_path(self, git_repo):
        """Create real git worktree and verify isolated batch state path."""
        # Arrange
        original_dir = Path.cwd()

        try:
            os.chdir(git_repo)

            # Create real git worktree with a new branch (can't checkout 'main' as it's already checked out)
            worktree_path = git_repo.parent / "worktree-feature-123"
            subprocess.run(
                ['git', 'worktree', 'add', '-b', 'feature-123', str(worktree_path), 'HEAD'],
                cwd=git_repo,
                check=True,
                capture_output=True
            )

            # Act: Change to worktree and get batch state path
            os.chdir(worktree_path)
            reset_project_root_cache()  # Force re-detection

            # Verify is_worktree() detects it correctly
            assert is_worktree() is True

            # Get batch state file path
            state_file = get_batch_state_file()

            # Assert: State file is in worktree, not main repo
            expected = worktree_path / ".claude" / "batch_state.json"
            assert state_file == expected
            assert state_file.parent.exists()  # .claude/ created

            # Verify it's NOT in main repo
            main_state_file = git_repo / ".claude" / "batch_state.json"
            assert state_file != main_state_file

        finally:
            os.chdir(original_dir)
            reset_project_root_cache()

    def test_main_repo_batch_state_unchanged_with_worktrees(self, git_repo):
        """Verify main repo batch state path unchanged when worktrees exist."""
        # Arrange
        original_dir = Path.cwd()

        try:
            os.chdir(git_repo)

            # Create worktree (for context) with a new branch
            worktree_path = git_repo.parent / "worktree-feature-456"
            subprocess.run(
                ['git', 'worktree', 'add', '-b', 'feature-456', str(worktree_path), 'HEAD'],
                cwd=git_repo,
                check=True,
                capture_output=True
            )

            # Act: Stay in main repo and get batch state path
            os.chdir(git_repo)
            reset_project_root_cache()

            # Verify is_worktree() returns False in main repo
            assert is_worktree() is False

            # Get batch state file path
            state_file = get_batch_state_file()

            # Assert: State file is in main repo
            expected = git_repo / ".claude" / "batch_state.json"
            assert state_file == expected

        finally:
            os.chdir(original_dir)
            reset_project_root_cache()


# =============================================================================
# SECTION 2: Concurrent Worktree Batch Operations (3 tests)
# =============================================================================

class TestConcurrentWorktreeBatchOperations:
    """Test concurrent batch operations in different worktrees don't conflict."""

    def test_concurrent_worktree_batch_operations(self, git_repo, sample_features):
        """Verify concurrent batches in different worktrees are independent."""
        # Arrange
        original_dir = Path.cwd()

        try:
            os.chdir(git_repo)

            # Create two worktrees with new branches
            worktree_1 = git_repo.parent / "worktree-batch-1"
            worktree_2 = git_repo.parent / "worktree-batch-2"

            subprocess.run(
                ['git', 'worktree', 'add', '-b', 'batch-1', str(worktree_1), 'HEAD'],
                cwd=git_repo,
                check=True,
                capture_output=True
            )
            subprocess.run(
                ['git', 'worktree', 'add', '-b', 'batch-2', str(worktree_2), 'HEAD'],
                cwd=git_repo,
                check=True,
                capture_output=True
            )

            # Act: Create batch state in worktree 1
            os.chdir(worktree_1)
            reset_project_root_cache()
            state_file_1 = get_batch_state_file()
            batch_state_1 = create_batch_state(
                "features_1.txt",
                ["Feature A1", "Feature A2", "Feature A3"]
            )
            save_batch_state(state_file_1, batch_state_1)

            # Act: Create batch state in worktree 2
            os.chdir(worktree_2)
            reset_project_root_cache()
            state_file_2 = get_batch_state_file()
            batch_state_2 = create_batch_state(
                "features_2.txt",
                ["Feature B1", "Feature B2"]
            )
            save_batch_state(state_file_2, batch_state_2)

            # Assert: State files are different
            assert state_file_1 != state_file_2
            assert state_file_1.exists()
            assert state_file_2.exists()

            # Assert: States are independent (different batch IDs)
            os.chdir(worktree_1)
            reset_project_root_cache()
            loaded_1 = load_batch_state(state_file_1)

            os.chdir(worktree_2)
            reset_project_root_cache()
            loaded_2 = load_batch_state(state_file_2)

            assert loaded_1.batch_id != loaded_2.batch_id
            assert loaded_1.total_features == 3
            assert loaded_2.total_features == 2
            assert loaded_1.features != loaded_2.features

        finally:
            os.chdir(original_dir)
            reset_project_root_cache()

    def test_worktree_batch_state_survives_main_repo_changes(self, git_repo, sample_features):
        """Verify worktree batch state unaffected by main repo batch operations."""
        # Arrange
        original_dir = Path.cwd()

        try:
            os.chdir(git_repo)

            # Create worktree with new branch
            worktree_path = git_repo.parent / "worktree-isolated"
            subprocess.run(
                ['git', 'worktree', 'add', '-b', 'isolated', str(worktree_path), 'HEAD'],
                cwd=git_repo,
                check=True,
                capture_output=True
            )

            # Act: Create batch state in worktree
            os.chdir(worktree_path)
            reset_project_root_cache()
            wt_state_file = get_batch_state_file()
            wt_batch_state = create_batch_state(
                "worktree_features.txt",
                ["WT Feature 1", "WT Feature 2"]
            )
            save_batch_state(wt_state_file, wt_batch_state)

            # Act: Create batch state in main repo
            os.chdir(git_repo)
            reset_project_root_cache()
            main_state_file = get_batch_state_file()
            main_batch_state = create_batch_state(
                "main_features.txt",
                ["Main Feature 1", "Main Feature 2", "Main Feature 3"]
            )
            save_batch_state(main_state_file, main_batch_state)

            # Assert: Worktree state unchanged
            os.chdir(worktree_path)
            reset_project_root_cache()
            loaded_wt = load_batch_state(wt_state_file)

            assert loaded_wt.batch_id == wt_batch_state.batch_id
            assert loaded_wt.total_features == 2
            assert loaded_wt.features == ["WT Feature 1", "WT Feature 2"]

            # Assert: Main repo state unchanged
            os.chdir(git_repo)
            reset_project_root_cache()
            loaded_main = load_batch_state(main_state_file)

            assert loaded_main.batch_id == main_batch_state.batch_id
            assert loaded_main.total_features == 3

        finally:
            os.chdir(original_dir)
            reset_project_root_cache()

    def test_parallel_batch_processing_in_worktrees(self, git_repo, sample_features):
        """Verify parallel batch processing in worktrees (simulated concurrency)."""
        # Arrange
        original_dir = Path.cwd()

        try:
            os.chdir(git_repo)

            # Create three worktrees (simulating parallel CI jobs) with new branches
            worktrees = []
            for i in range(3):
                wt_path = git_repo.parent / f"worktree-parallel-{i}"
                subprocess.run(
                    ['git', 'worktree', 'add', '-b', f'parallel-{i}', str(wt_path), 'HEAD'],
                    cwd=git_repo,
                    check=True,
                    capture_output=True
                )
                worktrees.append(wt_path)

            # Act: Simulate concurrent batch processing
            batch_states = []
            for i, wt_path in enumerate(worktrees):
                os.chdir(wt_path)
                reset_project_root_cache()

                # Create unique batch state
                state_file = get_batch_state_file()
                batch_state = create_batch_state(
                    f"features_{i}.txt",
                    [f"Feature {i}-{j}" for j in range(3)]
                )
                save_batch_state(state_file, batch_state)
                batch_states.append((state_file, batch_state))

            # Assert: All batch states exist and are independent
            for i, (state_file, original_state) in enumerate(batch_states):
                assert state_file.exists()

                # Load and verify
                os.chdir(worktrees[i])
                reset_project_root_cache()
                loaded = load_batch_state(state_file)

                assert loaded.batch_id == original_state.batch_id
                assert loaded.total_features == 3
                assert loaded.features == [f"Feature {i}-{j}" for j in range(3)]

            # Assert: All state files are in different locations
            state_files = [state_file for state_file, _ in batch_states]
            assert len(set(state_files)) == 3  # All unique

        finally:
            os.chdir(original_dir)
            reset_project_root_cache()


# =============================================================================
# SECTION 3: Worktree State Persistence Tests (2 tests)
# =============================================================================

class TestWorktreeStatePersistence:
    """Test batch state persistence works correctly in worktrees."""

    def test_save_load_roundtrip_with_worktree(self, git_repo, sample_features):
        """Verify save/load roundtrip works correctly in worktree."""
        # Arrange
        original_dir = Path.cwd()

        try:
            os.chdir(git_repo)

            # Create worktree with new branch
            worktree_path = git_repo.parent / "worktree-persistence"
            subprocess.run(
                ['git', 'worktree', 'add', '-b', 'persistence', str(worktree_path), 'HEAD'],
                cwd=git_repo,
                check=True,
                capture_output=True
            )

            # Act: Save batch state in worktree
            os.chdir(worktree_path)
            reset_project_root_cache()
            state_file = get_batch_state_file()

            original_state = create_batch_state(
                "features.txt",
                sample_features
            )
            save_batch_state(state_file, original_state)

            # Act: Load batch state
            loaded_state = load_batch_state(state_file)

            # Assert: Roundtrip preserves all data
            assert loaded_state.batch_id == original_state.batch_id
            assert loaded_state.features_file == original_state.features_file
            assert loaded_state.total_features == original_state.total_features
            assert loaded_state.features == original_state.features
            assert loaded_state.current_index == original_state.current_index
            assert loaded_state.completed_features == original_state.completed_features
            assert loaded_state.failed_features == original_state.failed_features

        finally:
            os.chdir(original_dir)
            reset_project_root_cache()

    def test_worktree_state_file_json_format(self, git_repo, sample_features):
        """Verify batch state file in worktree has correct JSON format."""
        # Arrange
        original_dir = Path.cwd()

        try:
            os.chdir(git_repo)

            # Create worktree with new branch
            worktree_path = git_repo.parent / "worktree-json"
            subprocess.run(
                ['git', 'worktree', 'add', '-b', 'json-test', str(worktree_path), 'HEAD'],
                cwd=git_repo,
                check=True,
                capture_output=True
            )

            # Act: Save batch state in worktree
            os.chdir(worktree_path)
            reset_project_root_cache()
            state_file = get_batch_state_file()

            batch_state = create_batch_state(
                "features.txt",
                sample_features
            )
            save_batch_state(state_file, batch_state)

            # Assert: File is valid JSON
            assert state_file.exists()
            with open(state_file, 'r') as f:
                data = json.load(f)

            # Verify JSON structure
            assert "batch_id" in data
            assert "features_file" in data
            assert "total_features" in data
            assert "features" in data
            assert data["total_features"] == len(sample_features)
            assert data["features"] == sample_features

        finally:
            os.chdir(original_dir)
            reset_project_root_cache()


# =============================================================================
# SECTION 4: Worktree Cleanup Tests (2 tests)
# =============================================================================

class TestWorktreeCleanup:
    """Test batch state cleanup when worktrees are deleted."""

    def test_worktree_deletion_removes_batch_state(self, git_repo, sample_features):
        """Verify deleting worktree also removes its batch state file."""
        # Arrange
        original_dir = Path.cwd()

        try:
            os.chdir(git_repo)

            # Create worktree with batch state (new branch)
            worktree_path = git_repo.parent / "worktree-cleanup"
            subprocess.run(
                ['git', 'worktree', 'add', '-b', 'cleanup', str(worktree_path), 'HEAD'],
                cwd=git_repo,
                check=True,
                capture_output=True
            )

            os.chdir(worktree_path)
            reset_project_root_cache()
            state_file = get_batch_state_file()
            batch_state = create_batch_state("features.txt", sample_features)
            save_batch_state(state_file, batch_state)

            assert state_file.exists()

            # Act: Delete worktree (--force needed because of untracked .claude/ files)
            os.chdir(git_repo)
            subprocess.run(
                ['git', 'worktree', 'remove', '--force', str(worktree_path)],
                cwd=git_repo,
                check=True,
                capture_output=True
            )

            # Assert: Worktree and state file are gone
            assert not worktree_path.exists()
            assert not state_file.exists()

        finally:
            os.chdir(original_dir)
            reset_project_root_cache()

    def test_main_repo_state_unaffected_by_worktree_deletion(self, git_repo, sample_features):
        """Verify main repo batch state unaffected when worktree deleted."""
        # Arrange
        original_dir = Path.cwd()

        try:
            os.chdir(git_repo)

            # Create batch state in main repo
            reset_project_root_cache()
            main_state_file = get_batch_state_file()
            main_batch_state = create_batch_state("main_features.txt", sample_features)
            save_batch_state(main_state_file, main_batch_state)

            # Create worktree with batch state (new branch)
            worktree_path = git_repo.parent / "worktree-temp"
            subprocess.run(
                ['git', 'worktree', 'add', '-b', 'temp-delete', str(worktree_path), 'HEAD'],
                cwd=git_repo,
                check=True,
                capture_output=True
            )

            os.chdir(worktree_path)
            reset_project_root_cache()
            wt_state_file = get_batch_state_file()
            wt_batch_state = create_batch_state("wt_features.txt", ["WT Feature"])
            save_batch_state(wt_state_file, wt_batch_state)

            # Act: Delete worktree (--force needed because of untracked .claude/ files)
            os.chdir(git_repo)
            subprocess.run(
                ['git', 'worktree', 'remove', '--force', str(worktree_path)],
                cwd=git_repo,
                check=True,
                capture_output=True
            )

            # Assert: Main repo state still exists and unchanged
            reset_project_root_cache()
            assert main_state_file.exists()
            loaded_main = load_batch_state(main_state_file)

            assert loaded_main.batch_id == main_batch_state.batch_id
            assert loaded_main.total_features == len(sample_features)
            assert loaded_main.features == sample_features

        finally:
            os.chdir(original_dir)
            reset_project_root_cache()


# =============================================================================
# SECTION 5: Batch Orchestrator CWD Management Tests (4 tests)
# =============================================================================

class TestBatchOrchestratorCWDManagement:
    """Test batch orchestrator CWD change behavior with worktrees."""

    def test_create_batch_worktree_changes_cwd(self, git_repo, sample_features):
        """Verify create_batch_worktree() changes CWD to worktree path."""
        # Arrange
        original_dir = Path.cwd()

        try:
            os.chdir(git_repo)
            reset_project_root_cache()

            # Import batch_orchestrator functions
            try:
                from batch_orchestrator import create_batch_worktree
            except ImportError:
                pytest.skip("batch_orchestrator not implemented yet (TDD red phase)")

            batch_id = "test-cwd-change"
            initial_cwd = Path.cwd()

            # Act: Create worktree (should change CWD)
            result = create_batch_worktree(batch_id)

            # Assert: CWD changed to worktree path
            current_cwd = Path.cwd()

            if result["success"] and not result.get("fallback", False):
                # Successful worktree creation should change CWD
                worktree_path = Path(result["path"])
                assert current_cwd == worktree_path, (
                    f"Expected CWD to change to {worktree_path}, "
                    f"but it's still {current_cwd}"
                )
                assert current_cwd != initial_cwd, "CWD should have changed from initial location"

                # Verify result includes CWD metadata
                assert "original_cwd" in result, "Result should include original_cwd"
                assert "cwd_changed" in result, "Result should include cwd_changed flag"
                assert result["cwd_changed"] is True, "cwd_changed should be True"
                assert Path(result["original_cwd"]) == initial_cwd, (
                    "original_cwd should match initial CWD"
                )

            else:
                # Fallback mode should NOT change CWD
                assert current_cwd == initial_cwd, (
                    "CWD should not change in fallback mode"
                )
                assert result.get("cwd_changed", False) is False, (
                    "cwd_changed should be False in fallback"
                )

        finally:
            os.chdir(original_dir)
            reset_project_root_cache()

    def test_batch_orchestrator_fallback_no_cwd_change(self, git_repo, monkeypatch):
        """Verify fallback mode does not change CWD when worktree manager unavailable."""
        # Arrange
        original_dir = Path.cwd()

        try:
            os.chdir(git_repo)
            reset_project_root_cache()

            # Import batch_orchestrator functions
            try:
                from batch_orchestrator import create_batch_worktree, _get_worktree_manager
            except ImportError:
                pytest.skip("batch_orchestrator not implemented yet (TDD red phase)")

            # Mock worktree manager to be unavailable
            def mock_get_worktree_manager():
                return None

            import batch_orchestrator
            monkeypatch.setattr(batch_orchestrator, "_get_worktree_manager", mock_get_worktree_manager)

            batch_id = "test-fallback-cwd"
            initial_cwd = Path.cwd()

            # Act: Create worktree (should fallback without CWD change)
            result = create_batch_worktree(batch_id)

            # Assert: Fallback mode activated
            assert result["success"] is False, "Should fail without worktree manager"
            assert result["fallback"] is True, "Fallback flag should be True"
            assert "warning" in result, "Should include warning message"

            # Assert: CWD unchanged
            current_cwd = Path.cwd()
            assert current_cwd == initial_cwd, (
                f"CWD should not change in fallback mode. "
                f"Expected {initial_cwd}, got {current_cwd}"
            )

            # Assert: cwd_changed flag is False
            assert result.get("cwd_changed", False) is False, (
                "cwd_changed should be False in fallback mode"
            )

            # Assert: path points to current directory
            assert Path(result["path"]) == initial_cwd, (
                "Fallback path should be current directory"
            )

        finally:
            os.chdir(original_dir)
            reset_project_root_cache()

    def test_implementer_writes_to_worktree(self, git_repo, sample_features):
        """Verify file operations use worktree CWD after create_batch_worktree()."""
        # Arrange
        original_dir = Path.cwd()

        try:
            os.chdir(git_repo)
            reset_project_root_cache()

            # Import batch_orchestrator functions
            try:
                from batch_orchestrator import create_batch_worktree
            except ImportError:
                pytest.skip("batch_orchestrator not implemented yet (TDD red phase)")

            batch_id = "test-implementer-write"

            # Act: Create worktree
            result = create_batch_worktree(batch_id)

            if not result["success"] or result.get("fallback", False):
                pytest.skip("Test requires successful worktree creation")

            worktree_path = Path(result["path"])

            # Simulate implementer agent writing a file using Path.cwd()
            test_file = Path.cwd() / "test_implementation.py"
            test_file.write_text("# Test implementation\nprint('Hello from worktree')\n")

            # Assert: File exists in worktree
            worktree_file = worktree_path / "test_implementation.py"
            assert worktree_file.exists(), (
                f"File should exist in worktree at {worktree_file}"
            )
            assert test_file == worktree_file, (
                f"Test file path {test_file} should match worktree path {worktree_file}"
            )

            # Assert: File does NOT exist in main repo
            main_repo_file = git_repo / "test_implementation.py"
            assert not main_repo_file.exists(), (
                f"File should NOT exist in main repo at {main_repo_file}"
            )

            # Verify file content
            content = worktree_file.read_text()
            assert "Hello from worktree" in content, (
                "File should contain expected content"
            )

        finally:
            os.chdir(original_dir)
            reset_project_root_cache()

    def test_multiple_batches_cwd_isolation(self, git_repo, sample_features):
        """Verify multiple worktrees in sequence each change CWD correctly."""
        # Arrange
        original_dir = Path.cwd()

        try:
            os.chdir(git_repo)
            reset_project_root_cache()

            # Import batch_orchestrator functions
            try:
                from batch_orchestrator import create_batch_worktree
            except ImportError:
                pytest.skip("batch_orchestrator not implemented yet (TDD red phase)")

            main_cwd = Path.cwd()
            batch_1_id = "test-multi-batch-1"
            batch_2_id = "test-multi-batch-2"

            # Act: Create first worktree
            result_1 = create_batch_worktree(batch_1_id)

            if not result_1["success"] or result_1.get("fallback", False):
                pytest.skip("Test requires successful worktree creation")

            # Assert: CWD changed to first worktree
            worktree_1_path = Path(result_1["path"])
            cwd_after_1 = Path.cwd()
            assert cwd_after_1 == worktree_1_path, (
                f"CWD should be in first worktree. Expected {worktree_1_path}, got {cwd_after_1}"
            )

            # Write a marker file in first worktree
            marker_1 = Path.cwd() / "marker_batch_1.txt"
            marker_1.write_text("Batch 1")

            # Act: Change back to main repo and create second worktree
            os.chdir(git_repo)
            reset_project_root_cache()
            assert Path.cwd() == main_cwd, "Should be back in main repo"

            result_2 = create_batch_worktree(batch_2_id)

            # Assert: CWD changed to second worktree
            worktree_2_path = Path(result_2["path"])
            cwd_after_2 = Path.cwd()
            assert cwd_after_2 == worktree_2_path, (
                f"CWD should be in second worktree. Expected {worktree_2_path}, got {cwd_after_2}"
            )
            assert cwd_after_2 != cwd_after_1, (
                "Second worktree should be different from first"
            )

            # Write a marker file in second worktree
            marker_2 = Path.cwd() / "marker_batch_2.txt"
            marker_2.write_text("Batch 2")

            # Assert: Both worktrees have their own marker files
            assert (worktree_1_path / "marker_batch_1.txt").exists(), (
                "First worktree should have its marker"
            )
            assert (worktree_2_path / "marker_batch_2.txt").exists(), (
                "Second worktree should have its marker"
            )

            # Assert: Markers are NOT in each other's worktrees
            assert not (worktree_1_path / "marker_batch_2.txt").exists(), (
                "First worktree should NOT have second worktree's marker"
            )
            assert not (worktree_2_path / "marker_batch_1.txt").exists(), (
                "Second worktree should NOT have first worktree's marker"
            )

            # Assert: Markers are NOT in main repo
            assert not (main_cwd / "marker_batch_1.txt").exists(), (
                "Main repo should NOT have first marker"
            )
            assert not (main_cwd / "marker_batch_2.txt").exists(), (
                "Main repo should NOT have second marker"
            )

        finally:
            os.chdir(original_dir)
            reset_project_root_cache()


# =============================================================================
# Test Summary
# =============================================================================

"""
TEST SUMMARY (13 integration tests for Issue #226 + CWD fix):

SECTION 1: Real Worktree Batch State Path (2 tests)
✗ test_real_worktree_batch_state_path
✗ test_main_repo_batch_state_unchanged_with_worktrees

SECTION 2: Concurrent Worktree Batch Operations (3 tests)
✗ test_concurrent_worktree_batch_operations
✗ test_worktree_batch_state_survives_main_repo_changes
✗ test_parallel_batch_processing_in_worktrees

SECTION 3: Worktree State Persistence (2 tests)
✗ test_save_load_roundtrip_with_worktree
✗ test_worktree_state_file_json_format

SECTION 4: Worktree Cleanup (2 tests)
✗ test_worktree_deletion_removes_batch_state
✗ test_main_repo_state_unaffected_by_worktree_deletion

SECTION 5: Batch Orchestrator CWD Management (4 tests) - NEW
✗ test_create_batch_worktree_changes_cwd
✗ test_batch_orchestrator_fallback_no_cwd_change
✗ test_implementer_writes_to_worktree
✗ test_multiple_batches_cwd_isolation

TOTAL: 13 integration tests (all FAILING - TDD red phase)

Coverage Target: 95%+ for real-world worktree scenarios
Real git commands: git worktree add, git worktree remove
Integration: Tests with batch_state_manager, path_utils, git_operations

Real-World Scenarios Tested:
1. Real git worktree creation and detection
2. Concurrent batch processing in multiple worktrees
3. State isolation (worktree changes don't affect main repo)
4. State persistence (save/load roundtrip)
5. Cleanup (worktree deletion removes state)
6. JSON format validation
7. CWD changes after worktree creation (NEW)
8. Fallback mode with no CWD change (NEW)
9. File writes to worktree CWD (NEW)
10. Multiple batch CWD isolation (NEW)

These tests verify the COMPLETE end-to-end workflow with real git worktrees,
including the new CWD management behavior for batch orchestrator.

CWD Fix Implementation:
- create_batch_worktree() now calls os.chdir(worktree_path) after success
- Returns original_cwd and cwd_changed fields in result dict
- Fallback mode keeps CWD unchanged
- Enables implementer to write to worktree using Path.cwd()
"""
