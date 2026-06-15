"""Regression tests for :class:`CircuitBreaker` and :class:`PauseFlag`.

Covers (AC3-AC4):
* 2 consecutive failures → ``is_paused()`` reports a 4h pause.
* 3 failures in rolling 24h → ``is_paused()`` reports a 24h pause.
* Reset after the window passes (older failures pruned).
* ``record_success()`` clears the consecutive-failure counter.
* :class:`PauseFlag` deadline math: ``is_active()`` flips False after the deadline.

Uses ``tmp_path`` for filesystem isolation; manual datetime injection
(not ``freezegun``) for time advancement so tests have no external dependency.
"""

from __future__ import annotations

import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

_LIB = Path(__file__).resolve().parents[2] / "plugins" / "autonomous-dev" / "lib"
if str(_LIB) not in sys.path:
    sys.path.insert(0, str(_LIB))

from drain_queue_state import (  # noqa: E402
    CONSECUTIVE_FAIL_PAUSE_HOURS,
    DAILY_FAIL_THRESHOLD,
    LONG_PAUSE_HOURS,
    CircuitBreaker,
    DrainHistory,
    PauseFlag,
    _breaker_path,
    _history_path,
    _pause_flag_path,
)


def _make_repo(tmp_path: Path) -> Path:
    repo = tmp_path / "repo"
    (repo / ".claude" / "local").mkdir(parents=True)
    return repo


# =============================================================================
# CircuitBreaker — consecutive-failure pause
# =============================================================================


class TestCircuitBreakerConsecutive:
    """2 consecutive failures → 4h pause via is_paused()."""

    def test_first_failure_does_not_pause(self, tmp_path: Path) -> None:
        repo = _make_repo(tmp_path)
        breaker = CircuitBreaker.load(repo)
        breaker.record_failure()
        paused, _ = breaker.is_paused()
        assert paused is False
        assert breaker.consecutive_failures == 1

    def test_two_consecutive_failures_pauses(self, tmp_path: Path) -> None:
        repo = _make_repo(tmp_path)
        breaker = CircuitBreaker.load(repo)
        breaker.record_failure()
        breaker.record_failure()
        paused, reason = breaker.is_paused()
        assert paused is True
        assert "consecutive" in reason
        assert str(CONSECUTIVE_FAIL_PAUSE_HOURS) in reason

    def test_success_clears_consecutive_counter(self, tmp_path: Path) -> None:
        repo = _make_repo(tmp_path)
        breaker = CircuitBreaker.load(repo)
        breaker.record_failure()
        breaker.record_failure()
        # Already paused.
        paused, _ = breaker.is_paused()
        assert paused is True

        # Record a success → consecutive reset.
        breaker.record_success()
        assert breaker.consecutive_failures == 0
        # Note: is_paused() may still report True from the 24h-window check if
        # both failures fall inside it AND DAILY_FAIL_THRESHOLD <= 2. With the
        # default threshold of 3, the rolling check is below threshold here.
        paused, _ = breaker.is_paused()
        assert paused is False

    def test_state_persists_across_reload(self, tmp_path: Path) -> None:
        repo = _make_repo(tmp_path)
        breaker = CircuitBreaker.load(repo)
        breaker.record_failure()
        breaker.record_failure()

        # Reload from disk → state survived.
        breaker2 = CircuitBreaker.load(repo)
        assert breaker2.consecutive_failures == 2
        paused, _ = breaker2.is_paused()
        assert paused is True


# =============================================================================
# CircuitBreaker — rolling 24h threshold
# =============================================================================


class TestCircuitBreakerRollingWindow:
    """3 failures in rolling 24h → 24h pause."""

    def test_three_failures_in_24h_triggers_long_pause(
        self, tmp_path: Path
    ) -> None:
        repo = _make_repo(tmp_path)
        breaker = CircuitBreaker.load(repo)
        # Use distinct timestamps to avoid consecutive-pair short-circuit.
        now = datetime.now(timezone.utc)
        breaker.record_failure(now=now - timedelta(hours=20))
        breaker.record_success()  # break the consecutive run
        breaker.record_failure(now=now - timedelta(hours=10))
        breaker.record_success()
        breaker.record_failure(now=now - timedelta(hours=1))
        # After the third failure, consecutive=1 but recent_failures has 3.
        paused, reason = breaker.is_paused(now=now)
        assert paused is True
        # Could either be the consecutive (1 doesn't trigger) or rolling check.
        # Verify the rolling-window message specifically.
        assert "24h" in reason
        assert str(LONG_PAUSE_HOURS) in reason

    def test_old_failures_pruned_from_window(self, tmp_path: Path) -> None:
        """Failures older than 24h drop out of the rolling window."""
        repo = _make_repo(tmp_path)
        breaker = CircuitBreaker.load(repo)
        now = datetime.now(timezone.utc)

        # Three failures, but two outside the 24h window.
        breaker.record_failure(now=now - timedelta(hours=48))
        breaker.record_success()
        breaker.record_failure(now=now - timedelta(hours=30))
        breaker.record_success()
        breaker.record_failure(now=now - timedelta(hours=1))

        paused, _ = breaker.is_paused(now=now)
        # Only 1 failure remains inside 24h → DAILY_FAIL_THRESHOLD=3 not met,
        # consecutive=1 not met → NOT paused.
        assert paused is False

    def test_threshold_pin(self) -> None:
        """Make sure DAILY_FAIL_THRESHOLD remains 3."""
        assert DAILY_FAIL_THRESHOLD == 3


# =============================================================================
# CircuitBreaker — fail-OPEN on corrupt state
# =============================================================================


class TestCircuitBreakerFailOpen:
    """Corrupt breaker file → CLOSED state (fail-open). The system must not lock."""

    def test_corrupt_json_loads_as_closed_breaker(self, tmp_path: Path) -> None:
        repo = _make_repo(tmp_path)
        path = _breaker_path(repo)
        path.write_text("not-json")
        breaker = CircuitBreaker.load(repo)
        assert breaker.consecutive_failures == 0
        assert breaker.recent_failures == []
        paused, _ = breaker.is_paused()
        assert paused is False


# =============================================================================
# PauseFlag — deadline-based pause
# =============================================================================


class TestPauseFlag:
    """is_active() flips False after the deadline."""

    def test_no_flag_is_not_active(self, tmp_path: Path) -> None:
        repo = _make_repo(tmp_path)
        flag = PauseFlag.load(repo)
        active, reason = flag.is_active()
        assert active is False
        assert reason is None

    def test_set_within_window_is_active(self, tmp_path: Path) -> None:
        repo = _make_repo(tmp_path)
        flag = PauseFlag.load(repo)
        now = datetime.now(timezone.utc)
        flag.set("test pause", hours=4, now=now)
        active, reason = flag.is_active(now=now + timedelta(hours=1))
        assert active is True
        assert reason == "test pause"

    def test_set_after_deadline_is_inactive(self, tmp_path: Path) -> None:
        repo = _make_repo(tmp_path)
        flag = PauseFlag.load(repo)
        now = datetime.now(timezone.utc)
        flag.set("expired pause", hours=4, now=now)
        active, _ = flag.is_active(now=now + timedelta(hours=5))
        assert active is False

    def test_clear_removes_flag(self, tmp_path: Path) -> None:
        repo = _make_repo(tmp_path)
        flag = PauseFlag.load(repo)
        now = datetime.now(timezone.utc)
        flag.set("test", hours=4, now=now)
        assert _pause_flag_path(repo).exists()
        flag.clear()
        assert not _pause_flag_path(repo).exists()
        # Idempotent.
        flag.clear()

    def test_set_requires_positive_hours(self, tmp_path: Path) -> None:
        repo = _make_repo(tmp_path)
        flag = PauseFlag.load(repo)
        with pytest.raises(ValueError):
            flag.set("nope", hours=0)
        with pytest.raises(ValueError):
            flag.set("nope", hours=-3)

    def test_malformed_body_is_inactive(self, tmp_path: Path) -> None:
        """Fail-OPEN: corrupted body → not paused."""
        repo = _make_repo(tmp_path)
        _pause_flag_path(repo).write_text("not json {")
        flag = PauseFlag.load(repo)
        active, reason = flag.is_active()
        assert active is False
        assert reason is None

    def test_missing_until_iso_is_inactive(self, tmp_path: Path) -> None:
        repo = _make_repo(tmp_path)
        _pause_flag_path(repo).write_text(
            json.dumps({"reason": "no deadline", "triggered_by": "operator"})
        )
        flag = PauseFlag.load(repo)
        active, _ = flag.is_active()
        assert active is False

    def test_triggered_by_recorded(self, tmp_path: Path) -> None:
        repo = _make_repo(tmp_path)
        flag = PauseFlag.load(repo)
        flag.set("breaker", hours=4, triggered_by="circuit_breaker")
        body = json.loads(_pause_flag_path(repo).read_text())
        assert body["triggered_by"] == "circuit_breaker"
        # Schema spot-check.
        assert "until_iso" in body
        assert "triggered_at" in body
        assert "reason" in body

    def test_symlink_blocked(self, tmp_path: Path) -> None:
        """CWE-59: a symlinked flag file is rejected (fail-CLOSED).

        Updated for the security-auditor Medium finding: ``_validate()``
        raising ``ValueError`` (symlink, traversal, null byte) now causes
        ``is_active()`` to return ``(True, "path_validation_failed")`` instead
        of treating the failure as "not paused". This is the safer posture —
        a symlink attack on the flag path must HALT the drain, not silently
        allow it. The budget gate remains as a downstream safety net.
        """
        repo = _make_repo(tmp_path)
        real = tmp_path / "real_target"
        real.write_text(
            json.dumps(
                {
                    "reason": "evil",
                    "until_iso": (
                        datetime.now(timezone.utc) + timedelta(hours=4)
                    ).isoformat(),
                    "triggered_by": "operator",
                    "triggered_at": datetime.now(timezone.utc).isoformat(),
                }
            )
        )
        flag_path = _pause_flag_path(repo)
        flag_path.symlink_to(real)
        flag = PauseFlag.load(repo)
        active, reason = flag.is_active()
        # Symlink → validate raises → fail-CLOSED means ACTIVE pause with a
        # stable schema-friendly reason token.
        assert active is True
        assert reason == "path_validation_failed"


# =============================================================================
# DrainHistory — JSONL append
# =============================================================================


class TestDrainHistory:
    """Append-only JSONL; read tolerates malformed lines."""

    def test_append_single_record(self, tmp_path: Path) -> None:
        repo = _make_repo(tmp_path)
        history = DrainHistory.load(repo)
        history.append({"outcome": "success", "cluster": "TEST#1"})
        records = history.read_all()
        assert len(records) == 1
        assert records[0]["outcome"] == "success"
        assert "timestamp" in records[0]

    def test_append_preserves_existing_records(self, tmp_path: Path) -> None:
        repo = _make_repo(tmp_path)
        history = DrainHistory.load(repo)
        history.append({"outcome": "success", "n": 1})
        history.append({"outcome": "stop", "n": 2})
        records = history.read_all()
        assert len(records) == 2
        assert records[0]["n"] == 1
        assert records[1]["n"] == 2

    def test_malformed_line_skipped(self, tmp_path: Path) -> None:
        repo = _make_repo(tmp_path)
        history = DrainHistory.load(repo)
        history.append({"outcome": "ok"})
        # Inject a broken line directly.
        with open(_history_path(repo), "a") as f:
            f.write("not-json\n")
        history.append({"outcome": "ok-2"})
        records = history.read_all()
        # Two well-formed lines, one skipped.
        assert len(records) == 2

    def test_read_empty_file(self, tmp_path: Path) -> None:
        repo = _make_repo(tmp_path)
        history = DrainHistory.load(repo)
        assert history.read_all() == []
