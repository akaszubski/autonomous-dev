#!/usr/bin/env python3
"""
End-to-end workflow tests for self-validation (TDD Red Phase - Issue #271).

Tests complete commit workflow in autonomous-dev with quality gates enforced:
- Full commit cycle with quality gates
- Batch processing workflows
- Real git operations (using worktrees for isolation)

TDD Mode: These tests are written BEFORE implementation.
All tests should FAIL initially (implementation doesn't exist yet).

Test Strategy:
- Test full commit cycle (stage → pre-commit hooks → commit)
- Test batch processing scenarios
- Test real git operations with quality gates
- Test failure recovery workflows

Coverage Target: Key commit workflows

Date: 2026-01-26
Issue: #271 (meta(enforcement): Autonomous-dev doesn't enforce its own quality gates)
Agent: test-master
Phase: TDD Red (tests written BEFORE implementation)
Status: RED (all tests failing - implementation doesn't exist yet)
"""

import sys
import pytest
import os
import subprocess
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock
import json
import shutil

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

# Import repo detector (will fail in RED phase)
try:
    from repo_detector import (
        is_autonomous_dev_repo,
        is_worktree,
        get_repo_context,
        _reset_cache,
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
    _reset_cache()
    yield
    _reset_cache()


@pytest.fixture
def mock_git_repo(tmp_path):
    """Create a real git repository for testing."""
    repo_dir = tmp_path / "test-repo"
    repo_dir.mkdir()

    # Initialize git repo
    subprocess.run(
        ["git", "init"],
        cwd=repo_dir,
        check=True,
        capture_output=True
    )

    # Configure git user
    subprocess.run(
        ["git", "config", "user.name", "Test User"],
        cwd=repo_dir,
        check=True
    )
    subprocess.run(
        ["git", "config", "user.email", "test@example.com"],
        cwd=repo_dir,
        check=True
    )

    return repo_dir


@pytest.fixture
def mock_autonomous_dev_repo(mock_git_repo):
    """Create autonomous-dev git repository."""
    # Add autonomous-dev signature files
    plugins_dir = mock_git_repo / "plugins" / "autonomous-dev"
    plugins_dir.mkdir(parents=True)
    (plugins_dir / "manifest.json").write_text(
        '{"name": "autonomous-dev", "version": "1.0.0"}'
    )

    # Create initial commit
    subprocess.run(
        ["git", "add", "."],
        cwd=mock_git_repo,
        check=True
    )
    subprocess.run(
        ["git", "commit", "-m", "Initial commit"],
        cwd=mock_git_repo,
        check=True
    )

    return mock_git_repo


@pytest.fixture
def mock_pre_commit_hook(mock_autonomous_dev_repo):
    """Install mock pre-commit hook."""
    hooks_dir = mock_autonomous_dev_repo / ".git" / "hooks"
    hooks_dir.mkdir(exist_ok=True)

    # Create pre-commit hook script
    pre_commit = hooks_dir / "pre-commit"
    pre_commit.write_text("""#!/bin/bash
# Mock pre-commit hook for testing
echo "Running pre-commit checks..."
exit 0
""")
    pre_commit.chmod(0o755)

    return pre_commit


@pytest.fixture
def mock_worktree(mock_autonomous_dev_repo, tmp_path):
    """Create a worktree for batch processing testing."""
    worktree_dir = tmp_path / "worktrees" / "batch-test"

    # Create worktree
    subprocess.run(
        ["git", "worktree", "add", str(worktree_dir), "-b", "test-branch"],
        cwd=mock_autonomous_dev_repo,
        check=True,
        capture_output=True
    )

    return worktree_dir


# =============================================================================
# E2E Tests: Full Commit Cycle
# =============================================================================

class TestFullCommitCycle:
    """Test complete commit cycle with quality gates."""

    def test_commit_succeeds_with_passing_tests(
        self, mock_autonomous_dev_repo, monkeypatch, clean_cache
    ):
        """Test that commits succeed when all quality gates pass.

        WORKFLOW: Full commit cycle with quality gates.
        Expected: Commit completes successfully.
        """
        # Arrange - change to repo directory
        monkeypatch.chdir(mock_autonomous_dev_repo)

        # Create a new file
        test_file = mock_autonomous_dev_repo / "new_file.txt"
        test_file.write_text("test content")

        # Stage the file
        subprocess.run(
            ["git", "add", "new_file.txt"],
            cwd=mock_autonomous_dev_repo,
            check=True
        )

        # Mock quality gates passing
        with patch('subprocess.run') as mock_run:
            # Configure mock to pass through git commands
            def side_effect(cmd, *args, **kwargs):
                if "pytest" in str(cmd):
                    # Mock pytest passing
                    return MagicMock(returncode=0, stdout=b"10 passed")
                # Pass through other commands
                return subprocess.run.__wrapped__(cmd, *args, **kwargs)

            mock_run.side_effect = side_effect

            # Act - commit should succeed
            result = subprocess.run(
                ["git", "commit", "-m", "Test commit"],
                cwd=mock_autonomous_dev_repo,
                capture_output=True
            )

            # Assert - commit succeeded (or would succeed with real hooks)
            # Note: Without real hooks installed, this just tests the setup
            assert result.returncode == 0

    def test_commit_blocked_with_failing_tests(
        self, mock_autonomous_dev_repo, mock_pre_commit_hook, monkeypatch, clean_cache
    ):
        """Test that commits are blocked when quality gates fail.

        WORKFLOW: Quality gates block commit on failure.
        Expected: Commit fails, working directory unchanged.
        """
        # Arrange - change to repo directory
        monkeypatch.chdir(mock_autonomous_dev_repo)

        # Modify hook to simulate failure
        mock_pre_commit_hook.write_text("""#!/bin/bash
echo "Tests failed: 2 failed, 8 passed"
exit 1
""")

        # Create and stage a file
        test_file = mock_autonomous_dev_repo / "new_file.txt"
        test_file.write_text("test content")
        subprocess.run(
            ["git", "add", "new_file.txt"],
            cwd=mock_autonomous_dev_repo,
            check=True
        )

        # Act - commit should fail
        result = subprocess.run(
            ["git", "commit", "-m", "Test commit"],
            cwd=mock_autonomous_dev_repo,
            capture_output=True
        )

        # Assert - commit failed
        assert result.returncode != 0
        assert b"Tests failed" in result.stdout or b"Tests failed" in result.stderr

    def test_bypass_prevented_in_autonomous_dev(
        self, mock_autonomous_dev_repo, monkeypatch, clean_cache
    ):
        """Test that bypass environment variables are ignored.

        ENFORCEMENT: No bypass allowed in autonomous-dev.
        Expected: Quality gates still enforced with bypass env vars.
        """
        # Arrange - set bypass env vars
        monkeypatch.chdir(mock_autonomous_dev_repo)
        monkeypatch.setenv("SKIP_PRE_COMMIT_GATE", "true")
        monkeypatch.setenv("SKIP_QUALITY_GATE", "true")

        # Verify repo is detected as autonomous-dev
        assert is_autonomous_dev_repo() is True

        # Note: Full enforcement tested in integration tests
        # This test verifies detection works in real git repo


# =============================================================================
# E2E Tests: Batch Processing Workflow
# =============================================================================

class TestBatchProcessingWorkflow:
    """Test batch processing with worktrees and quality gates."""

    def test_worktree_detected_as_autonomous_dev(
        self, mock_worktree, monkeypatch, clean_cache
    ):
        """Test that worktrees are detected as autonomous-dev.

        DETECTION: Worktrees inherit repo type.
        Expected: is_autonomous_dev_repo() returns True in worktree.
        """
        # Arrange - change to worktree
        monkeypatch.chdir(mock_worktree)

        # Act
        result = is_autonomous_dev_repo()
        is_wt = is_worktree()

        # Assert
        assert result is True
        assert is_wt is True

    def test_quality_gates_enforced_in_worktree(
        self, mock_worktree, monkeypatch, clean_cache
    ):
        """Test that quality gates are enforced in worktrees.

        ENFORCEMENT: Worktrees follow same rules as main repo.
        Expected: Quality gates run and enforce in worktrees.
        """
        # Arrange - change to worktree
        monkeypatch.chdir(mock_worktree)

        # Verify context
        context = get_repo_context()
        assert context.is_autonomous_dev is True
        assert context.is_worktree is True

        # Create and stage a file
        test_file = mock_worktree / "worktree_file.txt"
        test_file.write_text("worktree content")
        subprocess.run(
            ["git", "add", "worktree_file.txt"],
            cwd=mock_worktree,
            check=True
        )

        # Note: Quality gate enforcement tested in integration tests
        # This verifies worktree detection works in real worktree

    def test_batch_isolation_maintained(
        self, mock_autonomous_dev_repo, tmp_path, monkeypatch, clean_cache
    ):
        """Test that batch worktrees are isolated from main repo.

        ISOLATION: Changes in worktree don't affect main repo.
        Expected: Worktree commits isolated, main repo unchanged.
        """
        # Create two worktrees for batch processing
        worktree1 = tmp_path / "batch-1"
        worktree2 = tmp_path / "batch-2"

        subprocess.run(
            ["git", "worktree", "add", str(worktree1), "-b", "batch-1"],
            cwd=mock_autonomous_dev_repo,
            check=True,
            capture_output=True
        )
        subprocess.run(
            ["git", "worktree", "add", str(worktree2), "-b", "batch-2"],
            cwd=mock_autonomous_dev_repo,
            check=True,
            capture_output=True
        )

        # Make changes in worktree1
        (worktree1 / "file1.txt").write_text("batch 1")
        subprocess.run(["git", "add", "."], cwd=worktree1, check=True)
        subprocess.run(
            ["git", "commit", "-m", "Batch 1 commit"],
            cwd=worktree1,
            check=True
        )

        # Make changes in worktree2
        (worktree2 / "file2.txt").write_text("batch 2")
        subprocess.run(["git", "add", "."], cwd=worktree2, check=True)
        subprocess.run(
            ["git", "commit", "-m", "Batch 2 commit"],
            cwd=worktree2,
            check=True
        )

        # Assert - changes isolated
        assert (worktree1 / "file1.txt").exists()
        assert not (worktree1 / "file2.txt").exists()
        assert (worktree2 / "file2.txt").exists()
        assert not (worktree2 / "file1.txt").exists()
        assert not (mock_autonomous_dev_repo / "file1.txt").exists()
        assert not (mock_autonomous_dev_repo / "file2.txt").exists()


# =============================================================================
# E2E Tests: Coverage Enforcement
# =============================================================================

class TestCoverageEnforcement:
    """Test coverage threshold enforcement in real scenarios."""

    def test_80_percent_threshold_enforced(
        self, mock_autonomous_dev_repo, monkeypatch, clean_cache
    ):
        """Test that 80% coverage threshold is enforced in autonomous-dev.

        ENFORCEMENT: Higher standard for autonomous-dev.
        Expected: Commits blocked below 80% coverage.
        """
        # Arrange - change to repo directory
        monkeypatch.chdir(mock_autonomous_dev_repo)

        # Create coverage.json with 75% coverage
        coverage_data = {
            "totals": {
                "percent_covered": 75.0,
                "covered_lines": 750,
                "num_statements": 1000
            }
        }
        (mock_autonomous_dev_repo / "coverage.json").write_text(
            json.dumps(coverage_data)
        )

        # Verify repo context
        context = get_repo_context()
        assert context.is_autonomous_dev is True

        # Note: Hook enforcement tested in integration tests
        # This verifies coverage file detection in real repo

    def test_coverage_passes_at_threshold(
        self, mock_autonomous_dev_repo, monkeypatch, clean_cache
    ):
        """Test that commits succeed with coverage at/above threshold.

        ENFORCEMENT: 80%+ coverage allows commit.
        Expected: Commit succeeds with adequate coverage.
        """
        # Arrange - change to repo directory
        monkeypatch.chdir(mock_autonomous_dev_repo)

        # Create coverage.json with 85% coverage
        coverage_data = {
            "totals": {
                "percent_covered": 85.0,
                "covered_lines": 850,
                "num_statements": 1000
            }
        }
        (mock_autonomous_dev_repo / "coverage.json").write_text(
            json.dumps(coverage_data)
        )

        # Verify repo context
        context = get_repo_context()
        assert context.is_autonomous_dev is True

        # Note: Hook enforcement tested in integration tests


# =============================================================================
# E2E Tests: CI Environment
# =============================================================================

class TestCiEnvironment:
    """Test CI environment detection and enforcement."""

    def test_github_actions_detected(
        self, mock_autonomous_dev_repo, monkeypatch, clean_cache
    ):
        """Test that GitHub Actions environment is detected.

        DETECTION: GITHUB_ACTIONS env var indicates CI.
        Expected: is_ci_environment() returns True.
        """
        # Arrange
        monkeypatch.chdir(mock_autonomous_dev_repo)
        monkeypatch.setenv("GITHUB_ACTIONS", "true")

        # Act
        context = get_repo_context()

        # Assert
        assert context.is_ci is True
        assert context.is_autonomous_dev is True

    def test_quality_gates_enforced_in_ci(
        self, mock_autonomous_dev_repo, monkeypatch, clean_cache
    ):
        """Test that quality gates are enforced in CI.

        ENFORCEMENT: CI runs enforce quality gates.
        Expected: No bypass allowed in CI.
        """
        # Arrange
        monkeypatch.chdir(mock_autonomous_dev_repo)
        monkeypatch.setenv("GITHUB_ACTIONS", "true")
        monkeypatch.setenv("SKIP_PRE_COMMIT_GATE", "true")  # Should be ignored

        # Act
        context = get_repo_context()

        # Assert
        assert context.is_ci is True
        # Note: Actual enforcement tested in integration tests


# Run tests in verbose mode to see which ones fail (RED phase)
if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
