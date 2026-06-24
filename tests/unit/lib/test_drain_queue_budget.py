"""Unit tests for ``DrainBudget`` in ``drain_queue_state``.

Covers:
* UTC-midnight reset of counters.
* Drain-count cap fires at the 11th drain attempt.
* Wall-seconds cap fires at 14400.01s.
* Fail-CLOSED behavior on corrupt JSON (planner correction).
* Atomic round-trip via ``_atomic_write_json``.
* Module-constant pin tests (prevent silent drift).
"""

from __future__ import annotations

import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

# Add lib directory to sys.path so `from drain_queue_state import ...` works.
_LIB = Path(__file__).resolve().parents[3] / "plugins" / "autonomous-dev" / "lib"
if str(_LIB) not in sys.path:
    sys.path.insert(0, str(_LIB))

from drain_queue_state import (  # noqa: E402
    AUTO_DRAINABLE_SEVERITY,
    CONSECUTIVE_FAIL_PAUSE_HOURS,
    DAILY_FAIL_THRESHOLD,
    HUMAN_GATE_TAGS,
    LONG_PAUSE_HOURS,
    MAX_CLUSTER_SIZE_AUTO_DRAINABLE,
    MAX_DRAINS_PER_DAY,
    MAX_WALL_SECONDS_PER_DAY,
    DrainBudget,
    _budget_path,
)


def _make_repo(tmp_path: Path) -> Path:
    """Create an isolated repo root with .claude/local/ scaffolding."""
    repo = tmp_path / "repo"
    (repo / ".claude" / "local").mkdir(parents=True)
    return repo


# =============================================================================
# Module-constant pins — prevent silent drift
# =============================================================================


class TestConstantsPin:
    """Pin every threshold the gates depend on (AC1)."""

    def test_max_drains_per_day_value(self) -> None:
        assert MAX_DRAINS_PER_DAY == 10

    def test_max_wall_seconds_per_day_value(self) -> None:
        assert MAX_WALL_SECONDS_PER_DAY == 14400

    def test_consecutive_fail_pause_hours_value(self) -> None:
        assert CONSECUTIVE_FAIL_PAUSE_HOURS == 4

    def test_daily_fail_threshold_value(self) -> None:
        assert DAILY_FAIL_THRESHOLD == 3

    def test_long_pause_hours_value(self) -> None:
        assert LONG_PAUSE_HOURS == 24

    def test_max_cluster_size_auto_drainable_value(self) -> None:
        assert MAX_CLUSTER_SIZE_AUTO_DRAINABLE == 5

    def test_auto_drainable_severity_includes_medium_phase_d(self) -> None:
        assert AUTO_DRAINABLE_SEVERITY == frozenset({"low", "info", "medium"})

    def test_human_gate_tags_includes_security_and_breaking(self) -> None:
        # Spot-check the security-critical entries.
        for tag in ("security", "breaking-change", "auth", "human-only", "major"):
            assert tag in HUMAN_GATE_TAGS, f"missing required gate tag: {tag}"


# =============================================================================
# Load / save / cold start
# =============================================================================


class TestLoadColdStart:
    """When no budget file exists, load returns a fresh zero budget."""

    def test_load_cold_start_returns_zero_budget(self, tmp_path: Path) -> None:
        repo = _make_repo(tmp_path)
        budget = DrainBudget.load(repo)
        assert budget.today_drains == 0
        assert budget.today_wall_seconds == 0.0
        # date_utc must be today (UTC).
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        assert budget.date_utc == today

    def test_load_then_save_roundtrip(self, tmp_path: Path) -> None:
        repo = _make_repo(tmp_path)
        budget = DrainBudget.load(repo)
        budget.today_drains = 3
        budget.today_wall_seconds = 1234.5
        budget.save()

        budget2 = DrainBudget.load(repo)
        assert budget2.today_drains == 3
        assert budget2.today_wall_seconds == 1234.5

    def test_save_writes_atomic_json(self, tmp_path: Path) -> None:
        repo = _make_repo(tmp_path)
        budget = DrainBudget.load(repo)
        budget.today_drains = 5
        budget.save()

        # Verify the file is valid JSON with expected schema.
        data = json.loads(_budget_path(repo).read_text())
        assert data["today_drains"] == 5
        assert "date_utc" in data
        assert "today_wall_seconds" in data


# =============================================================================
# Fail-CLOSED on corrupt JSON  (planner correction)
# =============================================================================


class TestFailClosed:
    """Corrupt/missing JSON MUST NOT be a free pass (OWASP LLM06)."""

    def test_budget_fail_closed_on_corrupt_json(self, tmp_path: Path) -> None:
        repo = _make_repo(tmp_path)
        budget_path = _budget_path(repo)
        # Truncated / malformed JSON body.
        budget_path.write_text('{"corrupt": json')

        budget = DrainBudget.load(repo)
        blocked, reason = budget.check_or_block()
        assert blocked is True
        assert ("corrupt" in reason.lower()) or ("exhausted" in reason.lower())

    def test_budget_fail_closed_on_empty_file(self, tmp_path: Path) -> None:
        repo = _make_repo(tmp_path)
        _budget_path(repo).write_text("")
        budget = DrainBudget.load(repo)
        blocked, reason = budget.check_or_block()
        assert blocked is True
        # The exhaustion message refers to one of the two caps.
        assert ("drain count" in reason.lower()) or (
            "wall-clock" in reason.lower()
        )

    def test_budget_fail_closed_on_wrong_type(self, tmp_path: Path) -> None:
        repo = _make_repo(tmp_path)
        # JSON valid but not a dict — int.
        _budget_path(repo).write_text("42")
        budget = DrainBudget.load(repo)
        blocked, _ = budget.check_or_block()
        assert blocked is True


# =============================================================================
# Cap thresholds
# =============================================================================


class TestCaps:
    """Cap fires when either counter exceeds its limit."""

    def test_drain_count_cap_fires_at_eleventh_drain(self, tmp_path: Path) -> None:
        repo = _make_repo(tmp_path)
        budget = DrainBudget.load(repo)
        budget.today_drains = MAX_DRAINS_PER_DAY  # exactly at cap → blocked
        blocked, reason = budget.check_or_block()
        assert blocked is True
        assert "drain count" in reason.lower()

    def test_drain_count_below_cap_passes(self, tmp_path: Path) -> None:
        repo = _make_repo(tmp_path)
        budget = DrainBudget.load(repo)
        budget.today_drains = MAX_DRAINS_PER_DAY - 1
        blocked, _ = budget.check_or_block()
        assert blocked is False

    def test_wall_seconds_cap_fires_at_14400(self, tmp_path: Path) -> None:
        repo = _make_repo(tmp_path)
        budget = DrainBudget.load(repo)
        budget.today_wall_seconds = float(MAX_WALL_SECONDS_PER_DAY) + 0.01
        blocked, reason = budget.check_or_block()
        assert blocked is True
        assert "wall-clock" in reason.lower()

    def test_wall_seconds_below_cap_passes(self, tmp_path: Path) -> None:
        repo = _make_repo(tmp_path)
        budget = DrainBudget.load(repo)
        budget.today_wall_seconds = float(MAX_WALL_SECONDS_PER_DAY - 1)
        blocked, _ = budget.check_or_block()
        assert blocked is False


# =============================================================================
# UTC-midnight reset
# =============================================================================


class TestReset:
    """Reset behaviour when date_utc no longer matches current UTC day."""

    def test_reset_if_new_day_clears_counters(self, tmp_path: Path) -> None:
        repo = _make_repo(tmp_path)
        budget = DrainBudget.load(repo)
        # Manually set a stale date_utc.
        yesterday = (
            datetime.now(timezone.utc) - timedelta(days=1)
        ).strftime("%Y-%m-%d")
        budget.date_utc = yesterday
        budget.today_drains = 9
        budget.today_wall_seconds = 9999.0

        did_reset = budget.reset_if_new_day()
        assert did_reset is True
        assert budget.today_drains == 0
        assert budget.today_wall_seconds == 0.0
        assert budget.date_utc == datetime.now(timezone.utc).strftime("%Y-%m-%d")

    def test_reset_noop_when_same_day(self, tmp_path: Path) -> None:
        repo = _make_repo(tmp_path)
        budget = DrainBudget.load(repo)
        budget.today_drains = 4
        did_reset = budget.reset_if_new_day()
        assert did_reset is False
        assert budget.today_drains == 4

    def test_check_or_block_auto_resets_on_new_day(self, tmp_path: Path) -> None:
        """check_or_block() must invoke reset_if_new_day() implicitly."""
        repo = _make_repo(tmp_path)
        budget = DrainBudget.load(repo)
        # Stale date + exhausted counters → after reset, NOT blocked.
        budget.date_utc = "2000-01-01"
        budget.today_drains = MAX_DRAINS_PER_DAY
        budget.today_wall_seconds = float(MAX_WALL_SECONDS_PER_DAY)
        blocked, _ = budget.check_or_block()
        assert blocked is False


# =============================================================================
# add() — successful-drain bookkeeping
# =============================================================================


class TestAdd:
    """add() increments count and accumulates wall_seconds."""

    def test_add_increments_count_and_wall_seconds(self, tmp_path: Path) -> None:
        repo = _make_repo(tmp_path)
        budget = DrainBudget.load(repo)
        budget.add(123.4)
        budget.add(56.6)
        # Reload to confirm persistence.
        budget2 = DrainBudget.load(repo)
        assert budget2.today_drains == 2
        assert budget2.today_wall_seconds == pytest.approx(180.0)

    def test_add_clamps_negative_wall_seconds_to_zero(
        self, tmp_path: Path
    ) -> None:
        repo = _make_repo(tmp_path)
        budget = DrainBudget.load(repo)
        budget.add(-50.0)
        # The drain still counted (one attempt), but no negative time accrued.
        assert budget.today_drains == 1
        assert budget.today_wall_seconds == 0.0
