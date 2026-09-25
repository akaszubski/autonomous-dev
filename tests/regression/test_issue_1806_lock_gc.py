"""Regression tests for Issue #1806 — stale-state GC must not unlink live lockfiles.

``_gc_stale_states()`` deleted every ``/tmp/pipeline_*.lock`` older than its
mtime cutoff.  ``acquire_run_lock()`` opens that pathname and takes
``fcntl.flock`` on the resulting inode.  Unlinking the pathname of a *held*
lock leaves the holder on an orphan inode while the next process creates and
locks a brand-new inode under the same pathname — two processes each believing
they own the run (split-brain run authority).  A nonblocking-flock probe before
the unlink does not fix it: another process can open the old inode between the
probe and the unlink (TOCTOU).  The accepted resolution is to stop deleting
lockfiles in the normal GC at all.

Both arms observe real filesystem state: real paths, real ``st_ino`` values,
real subprocesses with raw exit codes recorded.  Nothing about ``os.unlink`` is
mocked.

SAFETY: every path used here lives under the test's ``tmp_path``.  The GC's
``/tmp/`` globs are redirected to ``tmp_path`` and ``get_lockfile_path`` is
redirected to ``tmp_path`` in both parent and children, so no real
``/tmp/pipeline_*.lock`` (which may belong to a live pipeline run) is ever
read, created, or deleted — including under the pre-fix deleting behaviour.

Issues: #1806
"""

from __future__ import annotations

import glob as _glob_module
import json
import os
import selectors
import subprocess
import sys
import time
import uuid
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
LIB_DIR = REPO_ROOT / "plugins" / "autonomous-dev" / "lib"
if str(LIB_DIR) not in sys.path:
    sys.path.insert(0, str(LIB_DIR))

import pipeline_completion_state as pcs  # noqa: E402
import pipeline_state as ps  # noqa: E402

AGED_SECONDS = 10_000  # > the 7200s GC cutoff
GC_MAX_AGE = 7200

# Child that performs a *canonical* acquisition via acquire_run_lock().
# Exit code 0 == acquired, 4 == refused.  Prints one JSON line with the inode
# it observed at the lock pathname.
_ACQUIRE_CHILD = r"""
import json, os, sys
from pathlib import Path
sys.path.insert(0, os.environ["LIB_DIR"])
import pipeline_state as ps
lock_dir = Path(os.environ["LOCK_DIR"])
run_id = os.environ["RUN_ID"]
# SAFETY: redirect the canonical pathname into the test directory.
ps.get_lockfile_path = lambda rid: lock_dir / ("pipeline_%s.lock" % rid)
fd = ps.acquire_run_lock(run_id)
path = lock_dir / ("pipeline_%s.lock" % run_id)
ino = os.stat(path).st_ino if path.exists() else None
print(json.dumps({"acquired": fd is not None, "ino": ino}), flush=True)
sys.exit(0 if fd is not None else 4)
"""

# Child that pre-opens the lock pathname and PAUSES BEFORE flock().
# Synchronisation is by pipe lines only — no sleeps.
# Protocol: prints {"stage": "opened", "ino": N} then blocks on stdin;
# on "go" it flocks the pre-opened fd and prints {"stage": "flocked", ...};
# on "exit" it closes and exits 0.
_PREOPEN_CHILD = r"""
import fcntl, json, os, sys
from pathlib import Path
lock_path = Path(os.environ["LOCK_PATH"])
fd = os.open(str(lock_path), os.O_CREAT | os.O_WRONLY, 0o600)
print(json.dumps({"stage": "opened", "ino": os.fstat(fd).st_ino}), flush=True)
if sys.stdin.readline().strip() != "go":
    sys.exit(9)
try:
    fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
    flocked = True
except OSError:
    flocked = False
print(json.dumps({"stage": "flocked", "flocked": flocked,
                  "ino": os.fstat(fd).st_ino}), flush=True)
if sys.stdin.readline().strip() != "exit":
    sys.exit(9)
os.close(fd)
sys.exit(0)
"""


def _redirect_gc_globs(monkeypatch: pytest.MonkeyPatch, lock_dir: Path) -> None:
    """Point the GC's hardcoded ``/tmp/`` globs at ``lock_dir`` (SAFETY)."""
    real_glob = _glob_module.glob

    def fake_glob(pattern: str):
        if pattern.startswith("/tmp/"):
            return real_glob(str(lock_dir / pattern[len("/tmp/") :]))
        return real_glob(pattern)

    monkeypatch.setattr(pcs.glob, "glob", fake_glob)


def _age(path: Path, seconds: float = AGED_SECONDS) -> None:
    mtime = time.time() - seconds
    os.utime(path, (mtime, mtime))


def _run_acquire_child(lock_dir: Path, run_id: str) -> tuple[int, dict]:
    """Run the canonical-acquire child; return (raw exit code, parsed payload)."""
    env = dict(os.environ, LIB_DIR=str(LIB_DIR), LOCK_DIR=str(lock_dir), RUN_ID=run_id)
    proc = subprocess.run(
        [sys.executable, "-c", _ACQUIRE_CHILD],
        env=env,
        capture_output=True,
        text=True,
        timeout=60,
    )
    payload = json.loads(proc.stdout.strip().splitlines()[-1]) if proc.stdout.strip() else {}
    return proc.returncode, payload


def _readline(proc: subprocess.Popen, timeout: float = 30.0) -> str:
    """Read one line from ``proc.stdout``, failing instead of wedging the suite."""
    sel = selectors.DefaultSelector()
    sel.register(proc.stdout, selectors.EVENT_READ)
    try:
        if not sel.select(timeout):
            raise AssertionError(f"child produced no output within {timeout}s")
        return proc.stdout.readline()
    finally:
        sel.unregister(proc.stdout)
        sel.close()


@pytest.mark.regression
@pytest.mark.timeout(120)
def test_gc_retains_held_lock_inode_and_authority(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Two-process fault arm: GC must not unlink a held lock's pathname.

    A held lock whose mtime is older than the cutoff must survive the GC with
    the SAME inode, and a second canonical acquisition from a separate process
    must still be refused while it is held.  An unheld, equally aged lockfile
    must be RETAINED too (the fix removes lock deletion entirely, it does not
    merely probe for liveness).
    """
    lock_dir = tmp_path
    run_id = f"i1806a{uuid.uuid4().hex[:10]}"
    monkeypatch.setattr(
        ps, "get_lockfile_path", lambda rid: lock_dir / f"pipeline_{rid}.lock"
    )

    fd = ps.acquire_run_lock(run_id)
    assert fd is not None, "parent failed to acquire its own fresh lock"
    try:
        lock_path = lock_dir / f"pipeline_{run_id}.lock"
        assert lock_path.exists()
        ino_before = os.stat(lock_path).st_ino

        # An unheld lockfile of the same age — the retention control.
        unheld = lock_dir / f"pipeline_i1806unheld{uuid.uuid4().hex[:8]}.lock"
        unheld.write_text("")
        # A stale completion-state file — the positive control proving the GC
        # actually ran and still reaps what it is supposed to reap.
        stale_state = lock_dir / "pipeline_agent_completions_i1806old.json"
        stale_state.write_text("{}")
        for p in (lock_path, unheld, stale_state):
            _age(p)

        _redirect_gc_globs(monkeypatch, lock_dir)
        result = pcs._gc_stale_states(max_age_seconds=GC_MAX_AGE)

        # Positive control: the GC ran and did reap the stale state file.
        assert not stale_state.exists(), (
            "GC did not reap the stale completion-state file — the GC did not "
            f"run against {lock_dir} and this arm proves nothing. result={result}"
        )

        # (a) held lock pathname retained, same inode.
        assert lock_path.exists(), (
            f"GC unlinked a HELD lock pathname {lock_path} — the next process "
            f"will create a second inode under it (split-brain). result={result}"
        )
        assert os.stat(lock_path).st_ino == ino_before, (
            f"inode at {lock_path} changed across GC "
            f"({ino_before} -> {os.stat(lock_path).st_ino}) — lock authority split"
        )

        # Retention control: unheld aged lockfile also survives.
        assert unheld.exists(), (
            f"GC removed an unheld aged lockfile {unheld} — automatic lockfile "
            "deletion must be gone from the normal GC entirely"
        )
        assert result["lockfiles_removed"] == 0, (
            f"GC reported deleting {result['lockfiles_removed']} lockfile(s); "
            "the count must always be 0"
        )

        # (b) a second canonical acquisition from a SEPARATE process refuses.
        code, payload = _run_acquire_child(lock_dir, run_id)
        assert code == 4, (
            f"child raw exit code {code} (expected 4 == refused); "
            f"payload={payload} — a second process took run authority while the "
            "parent still holds the lock"
        )
        assert payload.get("acquired") is False
        assert payload.get("ino") == ino_before, (
            f"child saw inode {payload.get('ino')}, parent holds {ino_before} — "
            "two different inodes under one lock pathname"
        )
    finally:
        ps.release_run_lock(fd)

    # After release, the same pathname is acquirable again.
    code_after, payload_after = _run_acquire_child(lock_dir, run_id)
    assert code_after == 0, (
        f"child raw exit code {code_after} (expected 0 == acquired) after release"
    )
    assert payload_after.get("acquired") is True
    assert payload_after.get("ino") == ino_before, (
        "post-release acquisition landed on a different inode than the "
        f"original ({payload_after.get('ino')} != {ino_before})"
    )


@pytest.mark.regression
@pytest.mark.timeout(120)
def test_gc_cannot_swap_inode_under_a_pre_opened_fd(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Deterministic pre-open race arm: open-then-GC-then-flock keeps authority.

    A child opens the aged lock pathname and PAUSES before ``flock`` (the exact
    TOCTOU window a pre-unlink flock probe cannot close).  The GC runs while it
    is paused.  The child then flocks its pre-opened fd; a second canonical
    acquisition must be refused, and the inode the child holds must be the same
    inode the second acquirer opened.  Synchronisation is by pipe lines only.
    """
    lock_dir = tmp_path
    run_id = f"i1806b{uuid.uuid4().hex[:10]}"
    lock_path = lock_dir / f"pipeline_{run_id}.lock"
    monkeypatch.setattr(
        ps, "get_lockfile_path", lambda rid: lock_dir / f"pipeline_{rid}.lock"
    )

    # Pre-create and age the pathname so the GC considers it stale.
    lock_path.write_text("")
    _age(lock_path)
    stale_state = lock_dir / "pipeline_agent_completions_i1806race.json"
    stale_state.write_text("{}")
    _age(stale_state)

    env = dict(os.environ, LOCK_PATH=str(lock_path))
    child = subprocess.Popen(
        [sys.executable, "-c", _PREOPEN_CHILD],
        env=env,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        bufsize=1,
    )
    try:
        opened = json.loads(_readline(child))
        assert opened["stage"] == "opened"
        ino_child_open = opened["ino"]

        # ---- GC runs while the child is paused between open() and flock() ----
        _redirect_gc_globs(monkeypatch, lock_dir)
        result = pcs._gc_stale_states(max_age_seconds=GC_MAX_AGE)

        assert not stale_state.exists(), (
            "GC did not reap the stale completion-state file — the GC did not "
            f"run against {lock_dir} and this arm proves nothing. result={result}"
        )
        assert lock_path.exists(), (
            f"GC unlinked {lock_path} while a child held a pre-opened fd to it "
            f"— the child's flock will bind an orphan inode. result={result}"
        )
        assert os.stat(lock_path).st_ino == ino_child_open, (
            f"inode at {lock_path} changed across GC "
            f"({ino_child_open} -> {os.stat(lock_path).st_ino})"
        )
        assert result["lockfiles_removed"] == 0

        # ---- child now takes the lock on its pre-opened fd ----
        child.stdin.write("go\n")
        child.stdin.flush()
        flocked = json.loads(_readline(child))
        assert flocked["stage"] == "flocked"
        assert flocked["flocked"] is True, "child failed to flock its pre-opened fd"
        assert flocked["ino"] == ino_child_open

        # ---- a second canonical acquisition must be refused on that inode ----
        code, payload = _run_acquire_child(lock_dir, run_id)
        assert code == 4, (
            f"second acquirer raw exit code {code} (expected 4 == refused); "
            f"payload={payload} — it acquired run authority the child holds"
        )
        assert payload.get("ino") == ino_child_open, (
            f"second acquirer opened inode {payload.get('ino')}, child holds "
            f"{ino_child_open} — the GC swapped the inode under the pathname"
        )

        child.stdin.write("exit\n")
        child.stdin.flush()
        child_code = child.wait(timeout=30)
        assert child_code == 0, f"pre-open child raw exit code {child_code} (expected 0)"
    finally:
        if child.poll() is None:
            child.kill()
            child.wait(timeout=10)
