"""
Integration tests for concurrent /implement run isolation — Issue #1047.

Acceptance criteria:
- AC#2: Lockfile acquired via fcntl LOCK_NB; second concurrent /implement
  in same process gets clear "lock held" error.
- AC#5: Two /implement from different Claude Code processes get distinct
  run_ids and do not collide.

These tests use direct Python API calls (not subprocess) since fcntl is
in-process for same-process locking tests.
"""

import sys
from pathlib import Path

import pytest

_LIB = Path(__file__).resolve().parents[2] / "plugins" / "autonomous-dev" / "lib"
if str(_LIB) not in sys.path:
    sys.path.insert(0, str(_LIB))

from pipeline_state import acquire_run_lock, generate_run_id, release_run_lock


class TestLockfileBlocksSameProcess:
    """AC#2: Second concurrent /implement in same process is blocked."""

    def test_lockfile_blocks_same_process(self) -> None:
        """Acquiring the same run_id twice in the same process MUST block second call."""
        run_id = generate_run_id()

        fd1 = acquire_run_lock(run_id)
        assert fd1 is not None, "First acquire failed unexpectedly"

        fd2 = acquire_run_lock(run_id)
        assert fd2 is None, (
            "Second acquire on same run_id returned non-None — "
            "lock not blocking concurrent access"
        )

        release_run_lock(fd1)

        # After release, a third acquire MUST succeed
        fd3 = acquire_run_lock(run_id)
        assert fd3 is not None, "Acquire after release failed"
        release_run_lock(fd3)

    def test_lock_held_string_signal(self) -> None:
        """When lock is held, acquire returns None (maps to LOCK_HELD sentinel in shell)."""
        run_id = generate_run_id()
        fd1 = acquire_run_lock(run_id)
        try:
            result = acquire_run_lock(run_id)
            # The shell code checks: if [ "$LOCK_FD" = "LOCK_HELD" ]
            # In Python, None represents the LOCK_HELD case
            assert result is None, "Expected None (LOCK_HELD) for blocked acquire"
        finally:
            release_run_lock(fd1)


class TestDistinctRunIdsDoNotCollide:
    """AC#5: Two /implement runs get distinct run_ids and do not collide."""

    def test_distinct_run_ids_do_not_collide(self) -> None:
        """generate_run_id() MUST produce distinct IDs every call."""
        run_id_a = generate_run_id()
        run_id_b = generate_run_id()

        assert run_id_a != run_id_b, (
            "generate_run_id() produced identical run_ids — "
            "concurrent /implement runs would collide"
        )

        # Both runs can hold their locks simultaneously
        fd_a = acquire_run_lock(run_id_a)
        fd_b = acquire_run_lock(run_id_b)
        try:
            assert fd_a is not None, f"Lock for run_id_a ({run_id_a}) not acquired"
            assert fd_b is not None, f"Lock for run_id_b ({run_id_b}) not acquired"
        finally:
            if fd_a is not None:
                release_run_lock(fd_a)
            if fd_b is not None:
                release_run_lock(fd_b)

    def test_large_batch_of_run_ids_are_unique(self) -> None:
        """50 rapid generate_run_id() calls MUST all produce distinct values."""
        ids = [generate_run_id() for _ in range(50)]
        assert len(set(ids)) == 50, (
            f"Collisions found in 50 rapid generate_run_id() calls. "
            f"Distinct: {len(set(ids))}"
        )

    def test_lockfile_cleanup_after_release(self) -> None:
        """Lockfile is left on disk after release (OS recycles it on next acquire)."""
        run_id = generate_run_id()
        lock_path = Path(f"/tmp/pipeline_{run_id}.lock")

        fd = acquire_run_lock(run_id)
        assert fd is not None
        assert lock_path.exists(), "Lockfile should exist after acquire"

        release_run_lock(fd)
        # Lockfile stays on disk (OS semantics) — that is acceptable and expected.
        # The next acquire will reuse it. We only verify release doesn't crash.
