"""Issue #1130: integration tests for scripts/cleanup-worktrees.sh.

Tests the truth table:
  - Main worktree: always skipped (MAIN)
  - Branched + merged: removed (REMOVED)
  - Branched + unmerged: skipped (SKIPPED)
  - Detached + reachable from master: removed (REMOVED)
  - Detached + unreachable from master: skipped (SKIPPED)
  - Missing directory: counted as PRUNED
  - --dry-run: no modifications
  - Outside git repo: exits 1
"""
import os
import subprocess
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "cleanup-worktrees.sh"


@pytest.fixture
def repo_with_worktrees(tmp_path: Path) -> Path:
    """Create a temp git repo with:
    - master branch with an initial commit
    - merged-branch (merged into master via --no-ff)
    - unmerged-branch (not merged)
    - detached-reachable worktree (checked out at master HEAD)
    - detached-unreachable worktree (at unmerged commit, NOT reachable from master)
    """
    repo = tmp_path / "repo"
    repo.mkdir()
    env = {
        **os.environ,
        "GIT_AUTHOR_NAME": "Test",
        "GIT_AUTHOR_EMAIL": "test@test.com",
        "GIT_COMMITTER_NAME": "Test",
        "GIT_COMMITTER_EMAIL": "test@test.com",
        # Suppress any global hooks
        "GIT_CONFIG_NOSYSTEM": "1",
        "HOME": str(tmp_path),
    }

    def run(*args, cwd=repo):
        return subprocess.run(
            ["git"] + list(args),
            cwd=cwd,
            env=env,
            check=True,
            capture_output=True,
            text=True,
        )

    run("init", "-b", "master")
    run("config", "user.email", "test@test.com")
    run("config", "user.name", "Test")
    (repo / "base.txt").write_text("base\n")
    run("add", "base.txt")
    run("commit", "-m", "initial commit")

    # Create a worktree for merged-branch
    wt_merged = repo / ".worktrees" / "merged-wt"
    wt_merged.parent.mkdir(parents=True, exist_ok=True)
    run("worktree", "add", "-b", "merged-branch", str(wt_merged))
    (wt_merged / "merged.txt").write_text("merged content\n")
    run("add", "merged.txt", cwd=wt_merged)
    run("commit", "-m", "merged commit", cwd=wt_merged)

    # Merge merged-branch into master so it's an ancestor
    run("merge", "--no-ff", "merged-branch", "-m", "merge merged-branch")

    # Create a worktree for unmerged-branch
    wt_unmerged = repo / ".worktrees" / "unmerged-wt"
    run("worktree", "add", "-b", "unmerged-branch", str(wt_unmerged))
    (wt_unmerged / "unmerged.txt").write_text("unmerged content\n")
    run("add", "unmerged.txt", cwd=wt_unmerged)
    run("commit", "-m", "unmerged commit", cwd=wt_unmerged)

    # Capture SHA of unmerged commit (unreachable from master)
    unmerged_sha = run("rev-parse", "unmerged-branch").stdout.strip()

    # Create a detached-reachable worktree (at master HEAD — reachable)
    master_head = run("rev-parse", "master").stdout.strip()
    wt_detached_reachable = repo / ".worktrees" / "detached-reachable"
    run("worktree", "add", "--detach", str(wt_detached_reachable), master_head)

    # Create a detached-unreachable worktree (at unmerged commit — not reachable from master)
    wt_detached_unreachable = repo / ".worktrees" / "detached-unreachable"
    run("worktree", "add", "--detach", str(wt_detached_unreachable), unmerged_sha)

    return repo


def _run_script(repo: Path, *args) -> subprocess.CompletedProcess:
    """Run the cleanup script from the given repo directory."""
    return subprocess.run(
        ["bash", str(SCRIPT)] + list(args),
        cwd=repo,
        capture_output=True,
        text=True,
    )


# ---------------------------------------------------------------------------
# Test: help flag
# ---------------------------------------------------------------------------

def test_help_flag(tmp_path: Path) -> None:
    """--help prints usage and exits 0."""
    # Initialize a bare git repo so preflight doesn't block
    subprocess.run(
        ["git", "init", "-b", "master"],
        cwd=tmp_path,
        capture_output=True,
        env={**os.environ, "GIT_CONFIG_NOSYSTEM": "1", "HOME": str(tmp_path)},
    )
    result = _run_script(tmp_path, "--help")
    assert result.returncode == 0, f"stderr: {result.stderr}"
    assert "Usage:" in result.stdout
    assert "--dry-run" in result.stdout


# ---------------------------------------------------------------------------
# Test: merged branch worktree is removed
# ---------------------------------------------------------------------------

def test_removes_merged_branch_worktree(repo_with_worktrees: Path) -> None:
    """A worktree on a branch merged into master must be removed."""
    repo = repo_with_worktrees
    wt_merged = repo / ".worktrees" / "merged-wt"
    assert wt_merged.exists(), "Test setup: merged worktree should exist before run"

    result = _run_script(repo)
    assert result.returncode == 0, f"Script failed:\nstdout={result.stdout}\nstderr={result.stderr}"
    assert "REMOVED:" in result.stdout, f"Expected REMOVED in output:\n{result.stdout}"
    assert "merged" in result.stdout
    assert not wt_merged.exists(), "Merged worktree should be deleted"


# ---------------------------------------------------------------------------
# Test: unmerged branch worktree is skipped
# ---------------------------------------------------------------------------

def test_skips_unmerged_branch_worktree(repo_with_worktrees: Path) -> None:
    """A worktree on an unmerged branch must be skipped (left on disk)."""
    repo = repo_with_worktrees
    wt_unmerged = repo / ".worktrees" / "unmerged-wt"

    result = _run_script(repo)
    assert result.returncode == 0, f"Script failed:\nstdout={result.stdout}\nstderr={result.stderr}"
    assert "SKIPPED:" in result.stdout, f"Expected SKIPPED in output:\n{result.stdout}"
    assert "unmerged" in result.stdout
    assert wt_unmerged.exists(), "Unmerged worktree must still exist"


# ---------------------------------------------------------------------------
# Test: main worktree is always skipped
# ---------------------------------------------------------------------------

def test_skips_main_worktree(repo_with_worktrees: Path) -> None:
    """The main worktree (repo root) must never be removed."""
    repo = repo_with_worktrees

    result = _run_script(repo)
    assert result.returncode == 0, f"Script failed:\nstdout={result.stdout}\nstderr={result.stderr}"
    assert "MAIN:" in result.stdout, f"Expected MAIN: in output:\n{result.stdout}"
    # Repo root must still exist
    assert (repo / ".git").exists(), "Main worktree must survive"


# ---------------------------------------------------------------------------
# Test: detached-reachable worktree is removed
# ---------------------------------------------------------------------------

def test_detached_reachable_removed(repo_with_worktrees: Path) -> None:
    """A detached-HEAD worktree whose SHA is reachable from master must be removed."""
    repo = repo_with_worktrees
    wt_detached = repo / ".worktrees" / "detached-reachable"
    assert wt_detached.exists(), "Test setup: detached-reachable worktree should exist"

    result = _run_script(repo)
    assert result.returncode == 0, f"Script failed:\nstdout={result.stdout}\nstderr={result.stderr}"
    assert "detached" in result.stdout.lower(), f"Expected detached mention:\n{result.stdout}"
    assert not wt_detached.exists(), "Detached-reachable worktree should be removed"


# ---------------------------------------------------------------------------
# Test: detached-unreachable worktree is skipped
# ---------------------------------------------------------------------------

def test_detached_unreachable_skipped(repo_with_worktrees: Path) -> None:
    """A detached-HEAD worktree whose SHA is NOT reachable from master must be skipped."""
    repo = repo_with_worktrees
    wt_unreachable = repo / ".worktrees" / "detached-unreachable"
    assert wt_unreachable.exists(), "Test setup: detached-unreachable worktree should exist"

    result = _run_script(repo)
    assert result.returncode == 0, f"Script failed:\nstdout={result.stdout}\nstderr={result.stderr}"
    assert wt_unreachable.exists(), "Detached-unreachable worktree must still exist"
    # Should appear in SKIPPED output
    assert "SKIPPED:" in result.stdout, f"Expected SKIPPED in output:\n{result.stdout}"


# ---------------------------------------------------------------------------
# Test: --dry-run makes no changes
# ---------------------------------------------------------------------------

def test_dry_run_does_not_modify(repo_with_worktrees: Path) -> None:
    """--dry-run must print what would happen but leave all worktrees intact."""
    repo = repo_with_worktrees
    wt_merged = repo / ".worktrees" / "merged-wt"
    wt_detached = repo / ".worktrees" / "detached-reachable"

    result = _run_script(repo, "--dry-run")
    assert result.returncode == 0, f"Script failed:\nstdout={result.stdout}\nstderr={result.stderr}"
    assert "WOULD REMOVE:" in result.stdout, f"Expected WOULD REMOVE in output:\n{result.stdout}"
    assert "DRY RUN" in result.stdout, f"Expected DRY RUN in output:\n{result.stdout}"
    # Nothing should have been removed
    assert wt_merged.exists(), "Dry-run must not remove merged worktree"
    assert wt_detached.exists(), "Dry-run must not remove detached-reachable worktree"


# ---------------------------------------------------------------------------
# Test: running outside a git repo exits 1
# ---------------------------------------------------------------------------

def test_exits_1_outside_git_repo(tmp_path: Path) -> None:
    """Running the script outside a git repository must exit with code 1."""
    # tmp_path is NOT a git repo
    result = subprocess.run(
        ["bash", str(SCRIPT)],
        cwd=tmp_path,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 1, f"Expected exit code 1, got {result.returncode}"
    assert "not inside a git repository" in result.stderr, (
        f"Expected error message in stderr:\n{result.stderr}"
    )
