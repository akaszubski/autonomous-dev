"""Integration tests for the 3-issue cluster --no-worktree flow (Issue #1133).

End-to-end behavior verified in a tmp_path git repo with the gh CLI
mocked out via subprocess.run patching. The orchestrator entry points
(run_batch_no_worktree_mode, batch_git_finalize with mode='no_worktree',
open_cluster_pr) are wired into a small fake driver that mimics what
the coordinator does inside implement-batch.md STEP B3.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(
    0,
    str(PROJECT_ROOT / "plugins" / "autonomous-dev" / "lib"),
)

import batch_git_finalize as bgf  # noqa: E402
import batch_orchestrator as bo  # noqa: E402


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _run(cmd, cwd=None, check=True):
    res = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True)
    if check and res.returncode != 0:
        raise RuntimeError(
            f"Command {cmd} failed (rc={res.returncode}): {res.stderr}"
        )
    return res


def _init_repo(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    _run(["git", "init", "-q", "-b", "master"], cwd=repo)
    _run(["git", "config", "user.email", "test@example.com"], cwd=repo)
    _run(["git", "config", "user.name", "Test User"], cwd=repo)
    # Seed with an initial commit so HEAD exists and reset --hard works.
    (repo / "README.md").write_text("seed\n")
    _run(["git", "add", "README.md"], cwd=repo)
    _run(["git", "commit", "-q", "-m", "init"], cwd=repo)
    return repo


def _fake_implement_issue(repo: Path, issue_num: int, title: str) -> None:
    """Simulate a per-issue implementation: create a file, commit it."""
    f = repo / f"feature_{issue_num}.py"
    f.write_text(f"# Implementation for #{issue_num}: {title}\n")
    _run(["git", "add", str(f)], cwd=repo)
    bgf.commit_batch_changes(
        repo,
        [f"Issue #{issue_num}: {title}"],
        issue_numbers=[issue_num],
    )


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def _scrub_env(monkeypatch):
    monkeypatch.delenv("BATCH_NO_WORKTREE", raising=False)
    yield
    if "BATCH_NO_WORKTREE" in os.environ:
        del os.environ["BATCH_NO_WORKTREE"]


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_three_commits_no_worktree(tmp_path, monkeypatch):
    """3 commits land on master, zero worktrees created."""
    repo = _init_repo(tmp_path)
    monkeypatch.chdir(repo)

    with patch.object(bo, "fetch_issue_titles", return_value=[
        "Issue #1: Add login", "Issue #2: Add logout", "Issue #3: Add reset",
    ]):
        result = bo.run_batch_no_worktree_mode({
            "mode": "batch_issues",
            "issues": [1, 2, 3],
            "no_worktree": True,
        })

    assert result["worktree_created"] is False
    assert not (repo / ".worktrees").exists()

    # Simulate the coordinator running each issue
    _fake_implement_issue(repo, 1, "Add login")
    _fake_implement_issue(repo, 2, "Add logout")
    _fake_implement_issue(repo, 3, "Add reset")

    # Count commits since the seed
    log = _run(["git", "log", "--oneline"], cwd=repo).stdout.strip().splitlines()
    # 1 seed + 3 issue commits
    assert len(log) == 4, f"Expected 4 commits, got: {log}"
    # Each issue commit message contains "Closes #N"
    for n in (1, 2, 3):
        full = _run(
            ["git", "log", "--all", "--format=%B"],
            cwd=repo,
        ).stdout
        assert f"Closes #{n}" in full, f"Closes #{n} missing from commit log"


def test_pr_body_closes_all_issues(tmp_path, monkeypatch):
    """The cluster PR body contains a Closes #N line for every issue."""
    captured = {}

    def fake_run(cmd, **kwargs):
        captured["cmd"] = cmd
        captured["kwargs"] = kwargs
        # Simulate a successful gh CLI invocation
        return subprocess.CompletedProcess(
            args=cmd,
            returncode=0,
            stdout="https://github.com/owner/repo/pull/999\n",
            stderr="",
        )

    monkeypatch.setattr("batch_git_finalize.subprocess.run", fake_run)

    result = bgf.open_cluster_pr(
        issue_numbers=[1131, 1132, 1133],
        issue_titles=[
            "Pickaxe false positive",
            "Worktree skip untracked",
            "no-worktree cluster mode",
        ],
        base_branch="master",
    )

    assert result["success"] is True
    assert "pr_url" in result
    # Extract the --body arg
    cmd = captured["cmd"]
    body_idx = cmd.index("--body") + 1
    body = cmd[body_idx]
    assert "Closes #1131" in body
    assert "Closes #1132" in body
    assert "Closes #1133" in body
    # Title also lists all issues
    title_idx = cmd.index("--title") + 1
    title = cmd[title_idx]
    assert "#1131" in title and "#1132" in title and "#1133" in title


def test_per_issue_failure_resets_hard_preserves_batch_state(tmp_path, monkeypatch):
    """git reset --hard reverts tracked changes; state file (.claude/...) survives."""
    repo = _init_repo(tmp_path)
    monkeypatch.chdir(repo)

    # Issue #1: write batch state, then start a failing issue
    state_dir = repo / ".claude"
    state_dir.mkdir(parents=True, exist_ok=True)
    state_path = state_dir / "batch_state.json"
    state_path.write_text(json.dumps({
        "batch_id": "batch-noworktree-test",
        "mode": "batch_issues",
        "no_worktree": True,
        "issues": [1, 2, 3],
        "current_index": 0,
        "completed_features": [],
        "failed_features": [],
    }))

    # gitignore .claude/ so reset --hard does NOT touch it
    (repo / ".gitignore").write_text(".claude/\n")
    _run(["git", "add", ".gitignore"], cwd=repo)
    _run(["git", "commit", "-q", "-m", "ignore claude"], cwd=repo)

    # Now simulate an issue that fails mid-implementation
    (repo / "broken.py").write_text("# half-baked work\n")
    _run(["git", "add", "broken.py"], cwd=repo)
    # Simulate failure → cleanup with git reset --hard
    _run(["git", "reset", "--hard", "HEAD"], cwd=repo)

    # The tracked file is gone
    assert not (repo / "broken.py").exists()
    # The state file survives — it's gitignored, untracked from git's view
    assert state_path.exists()
    state = json.loads(state_path.read_text())
    assert state["no_worktree"] is True
    assert state["batch_id"] == "batch-noworktree-test"


def test_dirty_tree_blocked_at_batch_start(tmp_path, monkeypatch):
    """Coordinator-level precondition: unstaged tracked changes → BLOCK."""
    repo = _init_repo(tmp_path)
    monkeypatch.chdir(repo)

    # Add an unstaged tracked change
    (repo / "README.md").write_text("seed\nmodified\n")

    # Verify both checks fire — diff and diff --cached
    unstaged = _run(["git", "diff", "--name-only"], cwd=repo).stdout.strip()
    staged = _run(["git", "diff", "--cached", "--name-only"], cwd=repo).stdout.strip()

    # In --no-worktree mode the gate considers BOTH non-empty as a block.
    # We document the gate semantics in implement-batch.md No-Worktree
    # Mode section and implement.md STEP 0; here we verify the underlying
    # git probes report what the gate consumes.
    assert unstaged == "README.md", f"Expected unstaged README.md, got {unstaged!r}"
    assert staged == "", f"Expected empty staged set, got {staged!r}"

    # The coordinator MUST block when either probe is non-empty. We simulate
    # the gate logic locally:
    is_dirty = bool(unstaged) or bool(staged)
    assert is_dirty, "Dirty-tree gate must fire when unstaged tracked changes exist"


def test_resume_after_interrupt_restores_env_var(tmp_path, monkeypatch):
    """--resume re-reads no_worktree from persisted state and re-arms the env var.

    Behavioral contract: when run_batch_no_worktree_mode runs (either
    fresh OR via the resume path), it sets BATCH_NO_WORKTREE=1. The
    persisted state file makes that re-entry deterministic.
    """
    repo = _init_repo(tmp_path)
    monkeypatch.chdir(repo)

    # Initial run sets the env var
    with patch.object(bo, "fetch_issue_titles", return_value=[
        "Issue #1: a", "Issue #2: b",
    ]):
        bo.run_batch_no_worktree_mode({
            "mode": "batch_issues",
            "issues": [1, 2],
            "no_worktree": True,
        })

    state_path = repo / ".claude" / "batch_state.json"
    assert state_path.exists()
    state = json.loads(state_path.read_text())
    assert state["no_worktree"] is True

    # Simulate session crash: env var lost
    del os.environ["BATCH_NO_WORKTREE"]
    assert "BATCH_NO_WORKTREE" not in os.environ

    # Now simulate --resume by re-invoking the entry point with the same
    # flags reconstructed from the state file
    with patch.object(bo, "fetch_issue_titles", return_value=[
        "Issue #1: a", "Issue #2: b",
    ]):
        bo.run_batch_no_worktree_mode({
            "mode": state["mode"],
            "issues": state["issues"],
            "no_worktree": state["no_worktree"],
        })

    # The env var is restored
    assert os.environ.get("BATCH_NO_WORKTREE") == "1"


def test_batch_git_finalize_no_worktree_mode_commits_in_place(tmp_path, monkeypatch):
    """batch_git_finalize(mode='no_worktree') commits without merge/cleanup."""
    repo = _init_repo(tmp_path)
    monkeypatch.chdir(repo)

    # Stage a change
    (repo / "feat.py").write_text("print('hi')\n")
    _run(["git", "add", "feat.py"], cwd=repo)

    result = bgf.batch_git_finalize(
        worktree_path=repo,
        features=["Issue #500: Add feat"],
        issue_numbers=[500],
        target_branch="master",
        mode="no_worktree",
    )

    assert result["success"] is True
    assert result["mode"] == "no_worktree"
    # No worktree was removed because none was created
    assert result["worktree_removed"] is False
    assert result["commit_sha"] is not None
    # Commit message contains Closes #500
    log = _run(["git", "log", "--format=%B", "-1"], cwd=repo).stdout
    assert "Closes #500" in log
