"""
Unit tests for new run_id helpers in pipeline_state.py — Issue #1047.

Tests:
- generate_run_id() format and uniqueness
- classify_resume_id() for all four cases (batch, run_id, run_id_legacy, invalid)
- classify_resume_id() ordering: batch prefix takes priority over hex match
- acquire_run_lock() / release_run_lock() behaviour
- Lockfile blocks same process, allows after release, distinct IDs do not collide

Issue: #1047
"""

import sys
from pathlib import Path

import pytest

# Add lib to path
_LIB = Path(__file__).resolve().parents[3] / "plugins" / "autonomous-dev" / "lib"
if str(_LIB) not in sys.path:
    sys.path.insert(0, str(_LIB))

from pipeline_state import (
    acquire_run_lock,
    classify_resume_id,
    generate_run_id,
    get_lockfile_path,
    release_run_lock,
)


# =============================================================================
# generate_run_id()
# =============================================================================


class TestGenerateRunId:
    """Tests for generate_run_id() helper — Issue #1047."""

    def test_generate_run_id_format(self) -> None:
        """run_id MUST be exactly 16 lowercase hex characters."""
        import re

        run_id = generate_run_id()
        assert re.match(r"^[a-f0-9]{16}$", run_id), (
            f"Expected 16-char lowercase hex, got: {run_id!r}"
        )

    def test_generate_run_id_length(self) -> None:
        """run_id MUST be exactly 16 characters long."""
        assert len(generate_run_id()) == 16

    def test_generate_run_id_unique(self) -> None:
        """100 calls MUST produce 100 distinct run_ids (collision probability negligible)."""
        ids = [generate_run_id() for _ in range(100)]
        assert len(set(ids)) == 100, "Duplicate run_ids generated — entropy too low"

    def test_generate_run_id_accepted_by_completion_state_validator(self) -> None:
        """run_id MUST match pipeline_completion_state._RUN_ID_RE."""
        import re

        _RUN_ID_RE = re.compile(r"^[a-zA-Z0-9_-]{1,64}$")
        run_id = generate_run_id()
        assert _RUN_ID_RE.match(run_id), (
            f"run_id {run_id!r} rejected by _RUN_ID_RE — cross-module contract broken"
        )


# =============================================================================
# classify_resume_id()
# =============================================================================


class TestClassifyResumeId:
    """Tests for classify_resume_id() helper — Issue #1047."""

    def test_classify_resume_id_batch(self) -> None:
        """IDs starting with 'batch-' MUST return 'batch'."""
        assert classify_resume_id("batch-20260101-120000-abcdef") == "batch"

    def test_classify_resume_id_batch_minimal(self) -> None:
        """'batch-' with nothing after it still returns 'batch' (prefix match)."""
        assert classify_resume_id("batch-") == "batch"

    def test_classify_resume_id_run_id_hex(self) -> None:
        """Exactly 16 lowercase hex characters MUST return 'run_id'."""
        assert classify_resume_id("abc123def456789a") == "run_id"

    def test_classify_resume_id_run_id_hex_all_digits(self) -> None:
        """16 hex digits with no letters MUST return 'run_id'."""
        assert classify_resume_id("1234567890abcdef") == "run_id"

    def test_classify_resume_id_legacy_timestamp(self) -> None:
        """YYYYMMDD-HHMMSS format MUST return 'run_id_legacy'."""
        assert classify_resume_id("20260505-130244") == "run_id_legacy"

    def test_classify_resume_id_invalid_empty(self) -> None:
        """Empty string MUST return 'invalid'."""
        assert classify_resume_id("") == "invalid"

    def test_classify_resume_id_invalid_special_chars(self) -> None:
        """String with special characters MUST return 'invalid'."""
        assert classify_resume_id("feat/issue-123") == "invalid"

    def test_classify_resume_id_invalid_too_long(self) -> None:
        """32-char hex string (not 16) MUST return 'invalid' (too long for run_id)."""
        assert classify_resume_id("a" * 32) == "invalid"

    def test_classify_resume_id_invalid_uppercase_hex(self) -> None:
        """Uppercase hex is NOT a valid run_id (only lowercase 16-char hex)."""
        assert classify_resume_id("ABC123DEF456789A") == "invalid"

    def test_classify_resume_id_ordering_batch_beats_hex(self) -> None:
        """'batch-' prefix takes priority even if the rest looks like hex.

        'batch-' + 16 hex chars should be classified as 'batch', not 'run_id'.
        """
        arg = "batch-" + "a" * 16
        assert classify_resume_id(arg) == "batch", (
            "batch prefix must take priority over run_id hex pattern"
        )

    def test_classify_resume_id_invalid_15_char_hex(self) -> None:
        """15-char hex is NOT a valid run_id (must be exactly 16)."""
        assert classify_resume_id("abc123def456789") == "invalid"

    def test_classify_resume_id_invalid_17_char_hex(self) -> None:
        """17-char hex is NOT a valid run_id (must be exactly 16)."""
        assert classify_resume_id("abc123def456789ab") == "invalid"


# =============================================================================
# acquire_run_lock() / release_run_lock()
# =============================================================================


class TestRunLockfile:
    """Tests for lockfile acquire/release helpers — Issue #1047."""

    def test_acquire_run_lock_first_succeeds(self, tmp_path: Path) -> None:
        """First acquire MUST return an integer file descriptor."""
        run_id = generate_run_id()
        fd = acquire_run_lock(run_id)
        try:
            assert fd is not None, "First acquire returned None — lock not obtained"
            assert isinstance(fd, int), f"Expected int fd, got {type(fd)}"
        finally:
            if fd is not None:
                release_run_lock(fd)

    def test_acquire_run_lock_second_blocks_same_process(self) -> None:
        """Second acquire on the same run_id MUST return None (lock already held)."""
        run_id = generate_run_id()
        fd1 = acquire_run_lock(run_id)
        try:
            assert fd1 is not None, "First acquire failed"
            fd2 = acquire_run_lock(run_id)
            assert fd2 is None, (
                "Second acquire on same run_id returned non-None — lock not blocking"
            )
        finally:
            if fd1 is not None:
                release_run_lock(fd1)

    def test_acquire_run_lock_after_release_succeeds(self) -> None:
        """After releasing a lock, a new acquire on the same run_id MUST succeed."""
        run_id = generate_run_id()
        fd1 = acquire_run_lock(run_id)
        assert fd1 is not None
        release_run_lock(fd1)

        fd3 = acquire_run_lock(run_id)
        try:
            assert fd3 is not None, "Re-acquire after release returned None"
        finally:
            if fd3 is not None:
                release_run_lock(fd3)

    def test_release_run_lock_idempotent(self) -> None:
        """Calling release_run_lock twice on the same fd MUST NOT raise."""
        run_id = generate_run_id()
        fd = acquire_run_lock(run_id)
        assert fd is not None
        release_run_lock(fd)
        # Second release must not raise
        release_run_lock(fd)

    def test_distinct_run_ids_do_not_collide(self) -> None:
        """Two different run_ids MUST both be acquirable simultaneously."""
        run_id_a = generate_run_id()
        run_id_b = generate_run_id()
        assert run_id_a != run_id_b, "generate_run_id() returned identical IDs"

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

    def test_lockfile_path_is_correct(self) -> None:
        """get_lockfile_path() MUST return /tmp/pipeline_<run_id>.lock."""
        run_id = generate_run_id()
        expected = Path(f"/tmp/pipeline_{run_id}.lock")
        assert get_lockfile_path(run_id) == expected
