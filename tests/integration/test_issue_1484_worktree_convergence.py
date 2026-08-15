#!/usr/bin/env python3
"""Integration tests for Issue #1484 — real git-worktree sentinel convergence.

Uses actual ``git init`` + ``git worktree add`` to prove that a writer
subprocess (cwd = <worktree>/subdir, no explicit repo_root) and a reader
subprocess (cwd = <worktree>, no explicit repo_root) converge on the SAME
sentinel file, while a reader in the main checkout does NOT see the worktree's
sentinel (isolation).

Skips gracefully when git is unavailable.

Issue: #1484
"""
from __future__ import annotations

import shutil
import subprocess
import sys
import textwrap
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parents[2]
_LIB = _REPO_ROOT / "plugins" / "autonomous-dev" / "lib"

pytestmark = pytest.mark.skipif(
    shutil.which("git") is None, reason="git not available"
)


def _run(cmd: list[str], cwd: Path) -> subprocess.CompletedProcess:
    return subprocess.run(
        cmd, cwd=str(cwd), capture_output=True, text=True, check=True
    )


def _py(code: str, cwd: Path) -> str:
    """Run a python snippet in a subprocess with cwd set, return stdout."""
    full = f"import sys\nsys.path.insert(0, {str(_LIB)!r})\n" + textwrap.dedent(code)
    proc = subprocess.run(
        [sys.executable, "-c", full],
        cwd=str(cwd),
        capture_output=True,
        text=True,
    )
    assert proc.returncode == 0, f"subprocess failed: {proc.stderr}\n{proc.stdout}"
    return proc.stdout.strip()


def _make_repo_with_worktree(tmp_path: Path) -> tuple[Path, Path]:
    main = tmp_path / "main"
    main.mkdir()
    _run(["git", "init", "-q"], main)
    _run(["git", "config", "user.email", "t@t.t"], main)
    _run(["git", "config", "user.name", "t"], main)
    (main / "README.md").write_text("x\n")
    _run(["git", "add", "-A"], main)
    _run(["git", "commit", "-q", "-m", "init"], main)
    wt = tmp_path / "wt"
    _run(["git", "worktree", "add", "-q", str(wt)], main)
    return main, wt


class TestIssue1484WorktreeConvergence:
    def test_real_worktree_writer_reader_converge(self, tmp_path: Path) -> None:
        """Writer (cwd=<wt>/subdir) and reader (cwd=<wt>) converge — both no-arg."""
        _main, wt = _make_repo_with_worktree(tmp_path)
        subdir = wt / "subdir"
        subdir.mkdir()

        # Writer subprocess: cwd = worktree/subdir, NO explicit repo_root.
        _py(
            """
            import agent_dispatch_sentinel as ads
            ads.write('implementer', generation='WT_GEN')
            print('wrote', ads._path())
            """,
            cwd=subdir,
        )

        # Reader subprocess: cwd = worktree root, NO explicit repo_root.
        out = _py(
            """
            import agent_dispatch_sentinel as ads
            print('ACTIVE' if ads.is_active() else 'INACTIVE')
            """,
            cwd=wt,
        )
        assert out.endswith("ACTIVE"), f"reader did not converge: {out!r}"

    def test_real_worktree_isolated_from_main(self, tmp_path: Path) -> None:
        """A worktree's sentinel is NOT visible to a reader in the main checkout."""
        main, wt = _make_repo_with_worktree(tmp_path)

        # Arm sentinel from within the worktree.
        _py(
            """
            import agent_dispatch_sentinel as ads
            ads.write('implementer', generation='WT_ONLY')
            """,
            cwd=wt,
        )

        # Reader in the MAIN checkout must not see it.
        out = _py(
            """
            import agent_dispatch_sentinel as ads
            print('ACTIVE' if ads.is_active() else 'INACTIVE')
            """,
            cwd=main,
        )
        assert out.endswith("INACTIVE"), f"main saw worktree sentinel: {out!r}"
