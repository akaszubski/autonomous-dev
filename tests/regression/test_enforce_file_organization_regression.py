"""Subprocess-level regression tests for enforce_file_organization (Issue #1034).

These tests invoke the hook as a real subprocess, mirroring how Claude Code
would invoke it. They prove the hook works end-to-end (shebang, imports,
hook_safety wrap, JSON contract) — not just its internal functions.

In-process unit tests live in tests/unit/hooks/test_enforce_file_organization.py.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest


REPO_ROOT = Path(__file__).resolve().parents[2]
HOOK_PATH = REPO_ROOT / "plugins" / "autonomous-dev" / "hooks" / "enforce_file_organization.py"


def _init_repo(repo_dir: Path) -> Path:
    """Initialize ``repo_dir`` as a git repo and return its resolved path."""
    subprocess.run(
        ["git", "init", "--quiet", str(repo_dir)],
        check=True,
        capture_output=True,
    )
    return repo_dir.resolve()


def _run_hook(
    payload: dict,
    *,
    cwd: Path,
    env: dict | None = None,
) -> subprocess.CompletedProcess:
    """Invoke the hook as a subprocess with ``payload`` on stdin."""
    full_env = os.environ.copy()
    # Clear bypass by default so tests don't accidentally inherit it.
    full_env.pop("AUTONOMOUS_DEV_BYPASS", None)
    if env:
        full_env.update(env)
    return subprocess.run(
        [sys.executable, str(HOOK_PATH)],
        input=json.dumps(payload),
        capture_output=True,
        text=True,
        cwd=str(cwd),
        env=full_env,
        timeout=10,
    )


class TestSubprocessHook:
    """Real subprocess invocations covering the end-to-end contract."""

    def test_subprocess_blocks_root_py(self, tmp_path: Path) -> None:
        repo = _init_repo(tmp_path)
        payload = {
            "tool_name": "Write",
            "tool_input": {"file_path": str(repo / "foo.py")},
        }
        result = _run_hook(payload, cwd=repo)
        assert result.returncode == 0, f"hook exited {result.returncode}: {result.stderr}"
        assert result.stdout.strip(), f"expected deny JSON on stdout, got empty (stderr={result.stderr})"
        envelope = json.loads(result.stdout)
        assert envelope["hookSpecificOutput"]["permissionDecision"] == "deny"
        reason = envelope["hookSpecificOutput"]["permissionDecisionReason"]
        assert "foo.py" in reason
        assert "scripts/" in reason

    def test_subprocess_allows_subdir_write(self, tmp_path: Path) -> None:
        repo = _init_repo(tmp_path)
        scripts = repo / "scripts"
        scripts.mkdir()
        payload = {
            "tool_name": "Write",
            "tool_input": {"file_path": str(scripts / "foo.py")},
        }
        result = _run_hook(payload, cwd=repo)
        assert result.returncode == 0, f"hook exited {result.returncode}: {result.stderr}"
        # Allow path produces NO JSON envelope on stdout.
        assert result.stdout.strip() == "", (
            f"expected silent allow, got stdout={result.stdout!r}"
        )

    def test_subprocess_bypass_env_short_circuits(self, tmp_path: Path) -> None:
        repo = _init_repo(tmp_path)
        payload = {
            "tool_name": "Write",
            "tool_input": {"file_path": str(repo / "foo.py")},
        }
        result = _run_hook(payload, cwd=repo, env={"AUTONOMOUS_DEV_BYPASS": "1"})
        assert result.returncode == 0, f"hook exited {result.returncode}: {result.stderr}"
        # Bypass produces no deny envelope on stdout.
        assert result.stdout.strip() == "", (
            f"bypass should suppress deny output, got: {result.stdout!r}"
        )

    def test_subprocess_in_worktree_uses_worktree_root(self, tmp_path: Path) -> None:
        """When invoked from inside a git worktree, the hook's git rev-parse
        MUST resolve to the worktree's root — not the main repo root. The
        worktree IS its own checkout for path-resolution purposes."""
        # Build a main repo with at least one commit so worktree add works.
        main_repo = tmp_path / "main"
        main_repo.mkdir()
        _init_repo(main_repo)
        # git worktree add requires HEAD to exist. Make one commit.
        subprocess.run(
            ["git", "-C", str(main_repo), "config", "user.email", "test@example.invalid"],
            check=True, capture_output=True,
        )
        subprocess.run(
            ["git", "-C", str(main_repo), "config", "user.name", "Test"],
            check=True, capture_output=True,
        )
        (main_repo / "README.md").write_text("seed\n", encoding="utf-8")
        subprocess.run(
            ["git", "-C", str(main_repo), "add", "README.md"],
            check=True, capture_output=True,
        )
        subprocess.run(
            ["git", "-C", str(main_repo), "commit", "-m", "seed", "--quiet"],
            check=True, capture_output=True,
        )
        # Create a worktree at tmp_path/wt on a new branch.
        worktree = tmp_path / "wt"
        subprocess.run(
            [
                "git", "-C", str(main_repo), "worktree", "add", "--quiet",
                "-b", "feature-1034", str(worktree),
            ],
            check=True, capture_output=True,
        )
        worktree_resolved = worktree.resolve()

        # Try to write foo.py at worktree root — must be blocked.
        payload = {
            "tool_name": "Write",
            "tool_input": {"file_path": str(worktree_resolved / "foo.py")},
        }
        result = _run_hook(payload, cwd=worktree_resolved)
        assert result.returncode == 0, f"hook exited {result.returncode}: {result.stderr}"
        assert result.stdout.strip(), (
            f"expected deny in worktree, got empty stdout (stderr={result.stderr})"
        )
        envelope = json.loads(result.stdout)
        assert envelope["hookSpecificOutput"]["permissionDecision"] == "deny"
        # The suggested folder must reference the *worktree* tree.
        assert "scripts/" in envelope["hookSpecificOutput"]["permissionDecisionReason"]
