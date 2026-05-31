"""Unit tests for the --no-worktree modifier (Issue #1133).

Covers `parse_implement_flags` recognition, `route_implement_mode` dispatch,
and `run_batch_no_worktree_mode` behavior. Includes regression cases
proving the existing batch_file / batch_issues / single-issue paths are
unchanged when the modifier is absent.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

# Add lib directory to path for direct module import
PROJECT_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(
    0,
    str(PROJECT_ROOT / "plugins" / "autonomous-dev" / "lib"),
)

import batch_orchestrator as bo  # noqa: E402


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def _scrub_env_and_cwd(tmp_path, monkeypatch):
    """Ensure each test starts from a known cwd and clean BATCH_NO_WORKTREE.

    `run_batch_no_worktree_mode` writes `<cwd>/.claude/batch_state.json` and
    sets `BATCH_NO_WORKTREE=1`. Without isolation, tests would pollute the
    real repo and the process env.
    """
    monkeypatch.delenv("BATCH_NO_WORKTREE", raising=False)
    monkeypatch.chdir(tmp_path)
    yield
    # Reset after the test in case the SUT set it
    if "BATCH_NO_WORKTREE" in os.environ:
        del os.environ["BATCH_NO_WORKTREE"]


@pytest.fixture
def features_file(tmp_path):
    p = tmp_path / "features.txt"
    p.write_text("Feature one\nFeature two\n")
    return p


# ---------------------------------------------------------------------------
# Parse flag tests
# ---------------------------------------------------------------------------


class TestParseNoWorktreeFlag:
    """parse_implement_flags must recognize --no-worktree as a modifier."""

    def test_parse_no_worktree_with_batch_file(self, features_file):
        flags = bo.parse_implement_flags(["--batch", str(features_file), "--no-worktree"])
        assert flags["mode"] == "batch_file"
        assert flags["no_worktree"] is True
        assert flags["batch_file"] == str(features_file)

    def test_parse_no_worktree_with_issues(self):
        flags = bo.parse_implement_flags(["--issues", "1", "2", "3", "--no-worktree"])
        assert flags["mode"] == "batch_issues"
        assert flags["no_worktree"] is True
        assert flags["issues"] == [1, 2, 3]

    def test_parse_no_worktree_first_then_issues(self):
        """Flag order independence — --no-worktree before --issues works."""
        flags = bo.parse_implement_flags(["--no-worktree", "--issues", "5", "6"])
        assert flags["mode"] == "batch_issues"
        assert flags["no_worktree"] is True
        assert flags["issues"] == [5, 6]

    def test_parse_no_worktree_without_batch_or_issues_raises(self):
        with pytest.raises(bo.FlagConflictError):
            bo.parse_implement_flags(["--no-worktree", "some feature"])

    def test_parse_no_worktree_with_quick_raises(self):
        with pytest.raises(bo.FlagConflictError):
            bo.parse_implement_flags(["--quick", "fix typo", "--no-worktree"])

    def test_parse_no_worktree_with_resume_raises(self):
        with pytest.raises(bo.FlagConflictError):
            bo.parse_implement_flags(["--resume", "batch-2026", "--no-worktree"])

    def test_parse_no_worktree_alone_raises(self):
        """Bare --no-worktree without batch/issues raises FlagConflictError."""
        with pytest.raises(bo.FlagConflictError):
            bo.parse_implement_flags(["--no-worktree"])


# ---------------------------------------------------------------------------
# run_batch_no_worktree_mode tests
# ---------------------------------------------------------------------------


class TestRunBatchNoWorktreeMode:
    """run_batch_no_worktree_mode env var, state file, and worktree-skip."""

    def test_run_batch_no_worktree_mode_sets_env_var(self):
        flags = {
            "mode": "batch_issues",
            "issues": [101, 102],
            "no_worktree": True,
            "features": [],
        }
        with patch.object(bo, "fetch_issue_titles", return_value=[
            "Issue #101: A", "Issue #102: B",
        ]):
            result = bo.run_batch_no_worktree_mode(flags)
        assert os.environ.get("BATCH_NO_WORKTREE") == "1"
        assert result["no_worktree"] is True

    def test_run_batch_no_worktree_mode_does_not_create_worktree(self, tmp_path):
        """No .worktrees/ directory must be created in this mode."""
        flags = {
            "mode": "batch_issues",
            "issues": [201, 202, 203],
            "no_worktree": True,
        }
        with patch.object(bo, "fetch_issue_titles", return_value=[
            "Issue #201: A", "Issue #202: B", "Issue #203: C",
        ]):
            result = bo.run_batch_no_worktree_mode(flags)
        assert result["worktree_created"] is False
        assert result["worktree_path"] == str(tmp_path)
        assert not (tmp_path / ".worktrees").exists()

    def test_run_batch_no_worktree_mode_writes_batch_state(self, tmp_path):
        flags = {
            "mode": "batch_issues",
            "issues": [301, 302],
            "no_worktree": True,
        }
        with patch.object(bo, "fetch_issue_titles", return_value=[
            "Issue #301: X", "Issue #302: Y",
        ]):
            result = bo.run_batch_no_worktree_mode(flags)
        state_path = tmp_path / ".claude" / "batch_state.json"
        assert state_path.exists()
        import json
        state = json.loads(state_path.read_text())
        assert state["no_worktree"] is True
        assert state["mode"] == "batch_issues"
        assert state["issues"] == [301, 302]
        assert state["current_index"] == 0
        assert state["completed_features"] == []
        assert state["failed_features"] == []
        # The result reports the same state path
        assert result["state_path"] == str(state_path)

    def test_run_batch_no_worktree_mode_batch_file(self, features_file, tmp_path):
        """The batch_file mode also works with --no-worktree."""
        # Move the features file into the tmp cwd so validate_features_file passes
        local_file = tmp_path / "features.txt"
        local_file.write_text(features_file.read_text())
        flags = {
            "mode": "batch_file",
            "batch_file": str(local_file),
            "no_worktree": True,
        }
        result = bo.run_batch_no_worktree_mode(flags)
        assert result["worktree_created"] is False
        assert result["mode"] == "batch_file"
        assert result["features"] == ["Feature one", "Feature two"]


# ---------------------------------------------------------------------------
# route_implement_mode tests
# ---------------------------------------------------------------------------


class TestRouteDispatchesNoWorktree:
    """route_implement_mode must dispatch to no_worktree mode when flag set."""

    def test_route_dispatches_to_no_worktree_when_flag_set(self):
        flags = {
            "mode": "batch_issues",
            "issues": [401, 402, 403],
            "no_worktree": True,
            "feature": None,
            "quick": False,
            "batch_file": None,
            "resume_id": None,
        }
        with patch.object(bo, "fetch_issue_titles", return_value=[
            "Issue #401: A", "Issue #402: B", "Issue #403: C",
        ]):
            result = bo.route_implement_mode(flags)
        assert result.get("no_worktree") is True
        assert result.get("worktree_created") is False

    def test_route_dispatches_to_no_worktree_batch_file(self, features_file, tmp_path):
        local_file = tmp_path / "features.txt"
        local_file.write_text(features_file.read_text())
        flags = {
            "mode": "batch_file",
            "batch_file": str(local_file),
            "no_worktree": True,
            "feature": None,
            "quick": False,
            "issues": None,
            "resume_id": None,
        }
        result = bo.route_implement_mode(flags)
        assert result.get("no_worktree") is True


# ---------------------------------------------------------------------------
# Regression: existing modes unchanged when flag absent
# ---------------------------------------------------------------------------


class TestExistingModesUnchanged:
    """Without --no-worktree, existing paths must dispatch to the worktree flow."""

    def test_existing_batch_file_mode_unchanged_when_flag_absent(
        self, features_file, tmp_path
    ):
        local_file = tmp_path / "features.txt"
        local_file.write_text(features_file.read_text())
        flags = {
            "mode": "batch_file",
            "batch_file": str(local_file),
            "no_worktree": False,
            "feature": None,
            "quick": False,
            "issues": None,
            "resume_id": None,
        }
        with patch.object(bo, "create_batch_worktree", return_value={
            "success": True,
            "fallback": False,
            "path": "/fake/worktree",
            "batch_id": "batch-test",
            "warning": None,
        }):
            result = bo.route_implement_mode(flags)
        # The classic path returns the run_batch_file_mode shape — there should
        # NOT be a no_worktree key set to True.
        assert result.get("no_worktree") is not True
        assert result["mode"] == "batch_file"

    def test_existing_batch_issues_mode_unchanged_when_flag_absent(self):
        flags = {
            "mode": "batch_issues",
            "issues": [501, 502],
            "no_worktree": False,
            "feature": None,
            "quick": False,
            "batch_file": None,
            "resume_id": None,
        }
        with patch.object(bo, "create_batch_worktree", return_value={
            "success": True,
            "fallback": False,
            "path": "/fake/worktree",
            "batch_id": "batch-issues-test",
            "warning": None,
        }), patch.object(bo, "fetch_issue_titles", return_value=[
            "Issue #501: A", "Issue #502: B",
        ]):
            result = bo.route_implement_mode(flags)
        assert result.get("no_worktree") is not True
        assert result["mode"] == "batch_issues"

    def test_existing_single_issue_mode_unchanged(self):
        """Full pipeline mode must not be affected by the new flag plumbing."""
        flags = {
            "mode": "full_pipeline",
            "feature": "add user login",
            "no_worktree": False,
            "quick": False,
            "batch_file": None,
            "issues": None,
            "resume_id": None,
        }
        result = bo.route_implement_mode(flags)
        assert result["mode"] == "full_pipeline"
        assert result.get("no_worktree") is not True
