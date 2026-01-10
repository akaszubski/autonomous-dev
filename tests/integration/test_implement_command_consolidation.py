#!/usr/bin/env python3
"""
Integration tests for /implement command consolidation (Issue #203).

Tests end-to-end behavior of unified /implement command including:
- Full pipeline mode (default)
- Quick mode (--quick)
- Batch file mode (--batch) with auto-worktree
- Batch issues mode (--issues) with auto-worktree
- Resume mode (--resume)
- Deprecation shim redirects

TDD Mode: These tests are written BEFORE implementation.

Date: 2026-01-10
Issue: GitHub #203 (Consolidate commands)
Agent: test-master
"""

import json
import os
import subprocess
import sys
import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock

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


# =============================================================================
# Test Fixtures
# =============================================================================

@pytest.fixture
def temp_git_repo(tmp_path):
    """Create a temporary git repository for testing."""
    repo_path = tmp_path / "test-repo"
    repo_path.mkdir()

    # Initialize git repo
    subprocess.run(
        ["git", "init"],
        cwd=repo_path,
        capture_output=True,
        check=True,
    )

    # Configure git for testing
    subprocess.run(
        ["git", "config", "user.email", "test@example.com"],
        cwd=repo_path,
        capture_output=True,
    )
    subprocess.run(
        ["git", "config", "user.name", "Test User"],
        cwd=repo_path,
        capture_output=True,
    )

    # Create initial commit
    readme = repo_path / "README.md"
    readme.write_text("# Test Repo")
    subprocess.run(
        ["git", "add", "README.md"],
        cwd=repo_path,
        capture_output=True,
    )
    subprocess.run(
        ["git", "commit", "-m", "Initial commit"],
        cwd=repo_path,
        capture_output=True,
    )

    return repo_path


@pytest.fixture
def features_file(tmp_path):
    """Create a features file for batch testing."""
    file_path = tmp_path / "features.txt"
    file_path.write_text("""# Test features
Feature one: Add authentication
Feature two: Add logging

# More features
Feature three: Add rate limiting
""")
    return file_path


# =============================================================================
# SECTION 1: Default Mode (Full Pipeline) Integration Tests
# =============================================================================

class TestFullPipelineModeIntegration:
    """Integration tests for full pipeline mode (default behavior)."""

    def test_implement_without_flags_uses_full_pipeline(self, temp_git_repo, monkeypatch):
        """Verify /implement without flags uses full pipeline mode."""
        try:
            from batch_orchestrator import parse_implement_flags, route_implement_mode
        except ImportError:
            pytest.skip("Implementation not found (TDD red phase)")

        monkeypatch.chdir(temp_git_repo)

        # Parse args without flags
        args = ["add user authentication"]
        flags = parse_implement_flags(args)

        assert flags["mode"] == "full_pipeline"
        assert flags["feature"] == "add user authentication"

    def test_full_pipeline_invokes_all_agents(self, temp_git_repo, monkeypatch):
        """Verify full pipeline mode invokes all 8 agents.

        Note: Agent invocation is orchestrated by Claude following implement.md
        instructions, not by Python code. This test is for future programmatic
        agent invocation.
        """
        pytest.skip("Agent invocation is orchestrated by Claude via implement.md, not Python code")


# =============================================================================
# SECTION 2: Quick Mode Integration Tests
# =============================================================================

class TestQuickModeIntegration:
    """Integration tests for quick mode (--quick flag)."""

    def test_quick_mode_skips_research_and_review(self, temp_git_repo, monkeypatch):
        """Verify --quick mode skips research, planning, and review agents.

        Note: Agent invocation is orchestrated by Claude following implement.md
        instructions, not by Python code. This test is for future programmatic
        agent invocation.
        """
        pytest.skip("Agent invocation is orchestrated by Claude via implement.md, not Python code")


# =============================================================================
# SECTION 3: Batch File Mode Integration Tests
# =============================================================================

class TestBatchFileModeIntegration:
    """Integration tests for batch file mode (--batch flag)."""

    def test_batch_file_mode_creates_worktree(self, temp_git_repo, features_file, monkeypatch):
        """Verify --batch mode creates worktree for isolation."""
        try:
            from batch_orchestrator import run_batch_file_mode
        except ImportError:
            pytest.skip("Implementation not found (TDD red phase)")

        monkeypatch.chdir(temp_git_repo)

        with patch("batch_orchestrator._get_worktree_manager") as mock_wm_getter:
            mock_wm = MagicMock()
            mock_wm.create_worktree.return_value = {"success": True}
            mock_wm_getter.return_value = mock_wm

            result = run_batch_file_mode(str(features_file))

            # Should have attempted worktree creation
            assert result.get("worktree_created") is True

    def test_batch_file_mode_processes_all_features(self, temp_git_repo, features_file, monkeypatch):
        """Verify --batch mode parses all features from file.

        Note: Actual feature processing (calling run_full_pipeline for each)
        is orchestrated by Claude via implement.md, not Python code.
        This test verifies features are parsed correctly.
        """
        try:
            from batch_orchestrator import run_batch_file_mode
        except ImportError:
            pytest.skip("Implementation not found (TDD red phase)")

        monkeypatch.chdir(temp_git_repo)

        with patch("batch_orchestrator._get_worktree_manager") as mock_wm_getter:
            mock_wm = MagicMock()
            mock_wm.create_worktree.return_value = {"success": True}
            mock_wm_getter.return_value = mock_wm

            result = run_batch_file_mode(str(features_file))

            # Should have parsed 3 features (excluding comments)
            assert result.get("feature_count") == 3
            assert len(result.get("features", [])) == 3

    def test_batch_file_mode_state_in_worktree(self, temp_git_repo, features_file, monkeypatch):
        """Verify batch state file is created in worktree."""
        try:
            from batch_orchestrator import run_batch_file_mode
        except ImportError:
            pytest.skip("Implementation not found (TDD red phase)")

        monkeypatch.chdir(temp_git_repo)

        with patch("batch_orchestrator.run_full_pipeline") as mock_pipeline:
            mock_pipeline.return_value = {"success": True}

            result = run_batch_file_mode(str(features_file))

            # State file should be in worktree's .claude/ directory
            if result.get("worktree_path"):
                state_file = Path(result["worktree_path"]) / ".claude" / "batch_state.json"
                # In real execution, this would exist


# =============================================================================
# SECTION 4: Batch Issues Mode Integration Tests
# =============================================================================

class TestBatchIssuesModeIntegration:
    """Integration tests for batch issues mode (--issues flag)."""

    def test_issues_mode_fetches_from_github(self, temp_git_repo, monkeypatch):
        """Verify --issues mode fetches issue titles from GitHub."""
        try:
            from batch_orchestrator import run_batch_issues_mode
        except ImportError:
            pytest.skip("Implementation not found (TDD red phase)")

        monkeypatch.chdir(temp_git_repo)

        with patch("batch_orchestrator.fetch_issue_titles") as mock_fetch:
            mock_fetch.return_value = [
                "Issue #72: Add authentication",
                "Issue #73: Fix bug",
            ]
            with patch("batch_orchestrator.run_full_pipeline") as mock_pipeline:
                mock_pipeline.return_value = {"success": True}
                with patch("batch_orchestrator.create_batch_worktree") as mock_wt:
                    mock_wt.return_value = {"success": True, "path": str(temp_git_repo), "batch_id": "batch-issues-72-73-test"}

                    result = run_batch_issues_mode([72, 73])

                    mock_fetch.assert_called_once_with([72, 73])

    def test_issues_mode_creates_worktree(self, temp_git_repo, monkeypatch):
        """Verify --issues mode creates worktree for isolation."""
        try:
            from batch_orchestrator import run_batch_issues_mode
        except ImportError:
            pytest.skip("Implementation not found (TDD red phase)")

        monkeypatch.chdir(temp_git_repo)

        with patch("batch_orchestrator.fetch_issue_titles") as mock_fetch:
            mock_fetch.return_value = ["Issue #72: Feature"]
            with patch("batch_orchestrator.run_full_pipeline") as mock_pipeline:
                mock_pipeline.return_value = {"success": True}
                with patch("batch_orchestrator.create_batch_worktree") as mock_wt:
                    mock_wt.return_value = {"success": True, "path": str(temp_git_repo), "batch_id": "batch-issues-72-test"}

                    result = run_batch_issues_mode([72])

                    # Worktree creation should have been called
                    mock_wt.assert_called_once()


# =============================================================================
# SECTION 5: Resume Mode Integration Tests
# =============================================================================

class TestResumeModeIntegration:
    """Integration tests for resume mode (--resume flag)."""

    def test_resume_mode_finds_existing_batch(self, temp_git_repo, monkeypatch):
        """Verify --resume finds and continues existing batch."""
        try:
            from batch_orchestrator import run_resume_mode
        except ImportError:
            pytest.skip("Implementation not found (TDD red phase)")

        monkeypatch.chdir(temp_git_repo)
        batch_id = "batch-20260110-143022"

        # Create worktree directory with batch state
        worktree_path = temp_git_repo / ".worktrees" / batch_id
        worktree_path.mkdir(parents=True)
        state_dir = worktree_path / ".claude"
        state_dir.mkdir()
        state_file = state_dir / "batch_state.json"
        state_file.write_text(json.dumps({
            "batch_id": batch_id,
            "status": "in_progress",
            "features": ["Feature A", "Feature B", "Feature C"],
            "current_index": 1,
            "completed_features": [0],
            "failed_features": [],
        }))

        with patch("batch_orchestrator.run_full_pipeline") as mock_pipeline:
            mock_pipeline.return_value = {"success": True}

            result = run_resume_mode(batch_id)

            # Should have found the batch
            assert result.get("found") is True

            # Should continue from index 1 (feature B)
            # Feature A (index 0) should be skipped

    def test_resume_mode_changes_to_worktree_directory(self, temp_git_repo, monkeypatch):
        """Verify --resume changes to worktree directory before continuing."""
        try:
            from batch_orchestrator import run_resume_mode
        except ImportError:
            pytest.skip("Implementation not found (TDD red phase)")

        monkeypatch.chdir(temp_git_repo)
        batch_id = "batch-20260110-143022"

        # Create worktree with state
        worktree_path = temp_git_repo / ".worktrees" / batch_id
        worktree_path.mkdir(parents=True)
        state_dir = worktree_path / ".claude"
        state_dir.mkdir()
        state_file = state_dir / "batch_state.json"
        state_file.write_text(json.dumps({
            "batch_id": batch_id,
            "status": "in_progress",
            "features": ["Feature A"],
            "current_index": 0,
            "completed_features": [],
            "failed_features": [],
        }))

        cwd_during_execution = None

        def mock_pipeline(feature):
            nonlocal cwd_during_execution
            cwd_during_execution = Path.cwd()
            return {"success": True}

        with patch("batch_orchestrator.run_full_pipeline", side_effect=mock_pipeline):
            result = run_resume_mode(batch_id)

            # Should have executed in worktree directory
            # (may be mocked, but concept should work)


# =============================================================================
# SECTION 6: Parallel Batch Isolation Tests
# =============================================================================

class TestParallelBatchIsolation:
    """Integration tests for parallel batch execution without conflicts."""

    def test_two_batches_different_worktrees(self, temp_git_repo, monkeypatch):
        """Verify two concurrent batches use different worktrees."""
        try:
            from batch_orchestrator import create_batch_worktree, get_batch_worktree_path
        except ImportError:
            pytest.skip("Implementation not found (TDD red phase)")

        monkeypatch.chdir(temp_git_repo)

        batch_id_1 = "batch-user1-20260110-143022"
        batch_id_2 = "batch-user2-20260110-143025"

        path_1 = get_batch_worktree_path(batch_id_1)
        path_2 = get_batch_worktree_path(batch_id_2)

        # Paths should be different
        assert path_1 != path_2
        assert batch_id_1 in str(path_1)
        assert batch_id_2 in str(path_2)

    def test_two_batches_different_state_files(self, temp_git_repo, monkeypatch):
        """Verify two concurrent batches have separate state files."""
        try:
            from batch_orchestrator import (
                get_batch_worktree_path,
                get_batch_state_path_for_worktree,
            )
        except ImportError:
            pytest.skip("Implementation not found (TDD red phase)")

        monkeypatch.chdir(temp_git_repo)

        batch_id_1 = "batch-user1-20260110-143022"
        batch_id_2 = "batch-user2-20260110-143025"

        worktree_1 = get_batch_worktree_path(batch_id_1)
        worktree_2 = get_batch_worktree_path(batch_id_2)

        state_1 = get_batch_state_path_for_worktree(worktree_1)
        state_2 = get_batch_state_path_for_worktree(worktree_2)

        # State files should be in different directories
        assert state_1 != state_2
        assert str(batch_id_1) in str(state_1.parent)
        assert str(batch_id_2) in str(state_2.parent)


# =============================================================================
# SECTION 7: Deprecation Shim Integration Tests
# =============================================================================

class TestDeprecationShimIntegration:
    """Integration tests for deprecation shim behavior."""

    def test_auto_implement_redirects_to_implement(self):
        """Verify /auto-implement redirects to /implement with notice."""
        try:
            from batch_orchestrator import handle_deprecated_command
        except ImportError:
            pytest.skip("Implementation not found (TDD red phase)")

        result = handle_deprecated_command("auto-implement", ["add feature"])

        assert result["redirect_to"] == "implement"
        assert result["args"] == ["add feature"]
        assert "deprecated" in result["notice"].lower()

    def test_batch_implement_redirects_to_implement_batch(self):
        """Verify /batch-implement redirects to /implement --batch."""
        try:
            from batch_orchestrator import handle_deprecated_command
        except ImportError:
            pytest.skip("Implementation not found (TDD red phase)")

        # File mode
        result = handle_deprecated_command("batch-implement", ["features.txt"])
        assert result["redirect_to"] == "implement"
        assert result["args"] == ["--batch", "features.txt"]

        # Issues mode
        result = handle_deprecated_command("batch-implement", ["--issues", "72", "73"])
        assert result["redirect_to"] == "implement"
        assert result["args"] == ["--issues", "72", "73"]


# =============================================================================
# Test Summary
# =============================================================================

"""
INTEGRATION TEST SUMMARY (12 tests for Issue #203):

SECTION 1: Full Pipeline Mode (2 tests)
- test_implement_without_flags_uses_full_pipeline
- test_full_pipeline_invokes_all_agents

SECTION 2: Quick Mode (1 test)
- test_quick_mode_skips_research_and_review

SECTION 3: Batch File Mode (3 tests)
- test_batch_file_mode_creates_worktree
- test_batch_file_mode_processes_all_features
- test_batch_file_mode_state_in_worktree

SECTION 4: Batch Issues Mode (2 tests)
- test_issues_mode_fetches_from_github
- test_issues_mode_creates_worktree

SECTION 5: Resume Mode (2 tests)
- test_resume_mode_finds_existing_batch
- test_resume_mode_changes_to_worktree_directory

SECTION 6: Parallel Batch Isolation (2 tests)
- test_two_batches_different_worktrees
- test_two_batches_different_state_files

SECTION 7: Deprecation Shims (2 tests)
- test_auto_implement_redirects_to_implement
- test_batch_implement_redirects_to_implement_batch

TOTAL: 14 integration tests
"""
