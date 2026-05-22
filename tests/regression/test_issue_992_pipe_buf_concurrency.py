"""Regression test for Issue #992: PIPE_BUF atomic-append boundary.

``MAX_REASON_LENGTH = 8000`` in ``hook_telemetry`` exceeds POSIX PIPE_BUF
atomic-append guarantees (4096B Linux, 512B macOS). Without an advisory
lock, concurrent ``log_block_event`` writes from multiple processes to
the same ``.claude/logs/hook-blocks.jsonl`` file can interleave, producing
torn JSONL rows that break downstream triage tooling.

The fix (Option B from the issue): wrap the file-append with
``fcntl.flock(LOCK_EX)``. This module verifies that the fix holds under
real multi-process load — synthetic single-threaded tests cannot exercise
the race window.

Test design:

- **Test 1 (concurrent, large events)** — 10 processes x 100 calls each,
  each event carries a ~7000-character reason. Every line in the resulting
  JSONL file MUST ``json.loads`` cleanly and the line count MUST equal 1000.
- **Test 2 (large single event)** — One large reason (~7000 chars) appended
  by a single writer produces exactly one intact JSONL line.
- **Test 3 (single-writer baseline)** — Functional smoke test that single-
  writer operation still works after the lock was added (no regression).

Multiprocessing rationale: threads would not exercise the OS-level race
because CPython's GIL serializes ``write()`` syscalls in practice. Real
hook invocations come from separate Claude Code sessions = separate
processes, so ``multiprocessing.Process`` is the right vehicle.
"""

from __future__ import annotations

import json
import multiprocessing as mp
import sys
from pathlib import Path

import pytest

# Make hook_telemetry importable. tests/regression/test_*.py -> repo root is
# parents[2] (regression -> tests -> repo).
REPO_ROOT = Path(__file__).resolve().parents[2]
LIB_DIR = REPO_ROOT / "plugins" / "autonomous-dev" / "lib"
if str(LIB_DIR) not in sys.path:
    sys.path.insert(0, str(LIB_DIR))

import hook_telemetry  # noqa: E402


# ---------------------------------------------------------------------------
# Worker functions (must be top-level for multiprocessing pickling on macOS
# spawn-start-method).
# ---------------------------------------------------------------------------

# Large reason payload near MAX_REASON_LENGTH. Sized so the full JSONL
# line is well above PIPE_BUF on every mainstream platform (4096B Linux,
# 512B macOS) — this is the exact configuration the bug requires to
# manifest.
LARGE_REASON_LENGTH = 7000


def _worker_emit_events(
    project_dir_str: str,
    worker_id: int,
    events_per_worker: int,
    lib_dir_str: str,
) -> int:
    """Child-process entry point. Emit N large events, return count."""
    # Re-import inside the child because ``spawn`` starts a fresh
    # interpreter that has not seen the parent's sys.path edits.
    import sys
    from pathlib import Path

    if lib_dir_str not in sys.path:
        sys.path.insert(0, lib_dir_str)

    import hook_telemetry as _ht

    reason = f"worker={worker_id} " + ("x" * LARGE_REASON_LENGTH)
    project_dir = Path(project_dir_str)

    for i in range(events_per_worker):
        _ht.log_block_event(
            hook_name="test_issue_992.py",
            decision_shape="tuple",
            reason=reason,
            metadata={"worker_id": worker_id, "iter": i},
            session_id=f"sess-{worker_id}",
            start_dir=project_dir,
        )
    return events_per_worker


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def project_dir(tmp_path: Path) -> Path:
    """Isolated project root with .claude/logs/."""
    (tmp_path / ".claude" / "logs").mkdir(parents=True, exist_ok=True)
    return tmp_path


@pytest.fixture(autouse=True)
def _clean_env(monkeypatch):
    """Ensure telemetry env vars are unset (no disable flag in effect)."""
    monkeypatch.delenv(hook_telemetry.DISABLE_ENV_VAR, raising=False)
    monkeypatch.delenv(hook_telemetry.LEGACY_DISABLE_ENV_VAR, raising=False)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestIssue992PipeBufConcurrency:
    """Regression for Issue #992 (PIPE_BUF atomic-append boundary)."""

    def test_concurrent_writers_produce_no_torn_lines(
        self, project_dir: Path
    ) -> None:
        """10 processes x 100 large events each -> 1000 intact JSONL lines.

        Without ``fcntl.flock`` the events would interleave because each
        event is well above the platform PIPE_BUF threshold. With the
        lock in place every line MUST parse as JSON and the line count
        MUST equal the requested event count.
        """
        n_workers = 10
        events_per_worker = 100
        expected_total = n_workers * events_per_worker

        log_path = project_dir / hook_telemetry.LOG_FILE_RELATIVE
        # Pre-create the file so all workers append to the same inode.
        log_path.parent.mkdir(parents=True, exist_ok=True)
        log_path.touch()

        # Use ``spawn`` start method explicitly so the child does not
        # inherit interpreter state — closer to real hook invocations.
        ctx = mp.get_context("spawn")
        procs = []
        for wid in range(n_workers):
            p = ctx.Process(
                target=_worker_emit_events,
                args=(
                    str(project_dir),
                    wid,
                    events_per_worker,
                    str(LIB_DIR),
                ),
            )
            procs.append(p)

        for p in procs:
            p.start()
        for p in procs:
            p.join(timeout=60)
            assert p.exitcode == 0, (
                f"Worker process exited with code {p.exitcode}; "
                f"telemetry must never raise"
            )

        # Read the resulting file and validate every line parses as JSON.
        raw = log_path.read_text(encoding="utf-8")
        lines = [ln for ln in raw.split("\n") if ln]

        assert len(lines) == expected_total, (
            f"Expected {expected_total} lines (10 workers x 100 events), "
            f"got {len(lines)}. Lost or duplicated events indicate the lock "
            f"is not holding."
        )

        torn_lines: list[tuple[int, str]] = []
        for i, ln in enumerate(lines):
            try:
                event = json.loads(ln)
            except json.JSONDecodeError as exc:
                torn_lines.append((i, f"{exc}: {ln[:200]!r}"))
                continue
            # Every event MUST have the expected schema fields. A torn
            # line that happens to be valid JSON would still be missing
            # fields.
            for field in ("ts", "hook_name", "decision_shape", "reason"):
                assert field in event, (
                    f"Line {i} missing field {field!r}: {event!r}"
                )

        assert not torn_lines, (
            f"Found {len(torn_lines)} torn (non-parseable) JSONL lines out "
            f"of {len(lines)}. First 3: {torn_lines[:3]}. "
            f"This indicates fcntl.flock is NOT being applied to the file "
            f"append — Issue #992 has regressed."
        )

        # Sanity: events from every worker must appear (no full event loss).
        worker_ids_seen = {
            json.loads(ln).get("metadata", {}).get("worker_id") for ln in lines
        }
        assert worker_ids_seen == set(range(n_workers)), (
            f"Missing workers: {set(range(n_workers)) - worker_ids_seen}"
        )

    def test_large_single_event_writes_one_intact_line(
        self, project_dir: Path
    ) -> None:
        """A ~7000-char reason produces exactly one parseable JSONL row."""
        log_path = project_dir / hook_telemetry.LOG_FILE_RELATIVE

        large_reason = "Y" * LARGE_REASON_LENGTH
        hook_telemetry.log_block_event(
            hook_name="test_issue_992.py",
            decision_shape="dict",
            reason=large_reason,
            metadata={"test": "single_large"},
            start_dir=project_dir,
        )

        raw = log_path.read_text(encoding="utf-8")
        lines = [ln for ln in raw.split("\n") if ln]

        assert len(lines) == 1, (
            f"Expected exactly 1 line for single large event, got {len(lines)}"
        )

        event = json.loads(lines[0])
        # Reason is capped at MAX_REASON_LENGTH (8000), and 7000 < 8000,
        # so the full payload survives intact.
        assert event["reason"] == large_reason, (
            "Large reason was truncated or corrupted"
        )
        assert event["decision_shape"] == "dict"
        assert event["metadata"] == {"test": "single_large"}

    def test_single_writer_baseline_still_functional(
        self, project_dir: Path
    ) -> None:
        """Smoke: single-writer path works after the lock change.

        This guards against the obvious regression where adding the lock
        accidentally breaks the common single-writer case (e.g. closing
        the file before releasing the lock, or releasing on a closed fd).
        """
        log_path = project_dir / hook_telemetry.LOG_FILE_RELATIVE

        for i in range(5):
            hook_telemetry.log_block_event(
                hook_name="test_issue_992.py",
                decision_shape="tuple",
                reason=f"event {i}",
                metadata={"i": i},
                start_dir=project_dir,
            )

        raw = log_path.read_text(encoding="utf-8")
        lines = [ln for ln in raw.split("\n") if ln]
        assert len(lines) == 5
        for i, ln in enumerate(lines):
            event = json.loads(ln)
            assert event["reason"] == f"event {i}"
            assert event["metadata"] == {"i": i}
