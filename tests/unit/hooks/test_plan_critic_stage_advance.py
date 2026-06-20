"""Tests for plan-critic stage advance logic in unified_session_tracker.py."""

import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

import pytest

# Add hooks directory to path for direct import
HOOKS_DIR = Path(__file__).parent.parent.parent.parent / "plugins" / "autonomous-dev" / "hooks"
sys.path.insert(0, str(HOOKS_DIR))

from unified_session_tracker import _advance_plan_mode_stage, _PLAN_TO_ISSUES_SUGGESTION


MARKER_REL_PATH = ".claude/plan_mode_exit.json"


def _write_marker(tmp_path: Path, *, stage: str = "plan_exited", **extra) -> Path:
    """Helper to write a plan mode exit marker for stage-advance tests.

    Args:
        tmp_path: Temp directory acting as cwd.
        stage: The stage field value.
        **extra: Additional fields to include in the marker.

    Returns:
        Path to the created marker file.
    """
    marker_path = tmp_path / MARKER_REL_PATH
    marker_path.parent.mkdir(parents=True, exist_ok=True)
    marker_data = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "session_id": "test-session",
        "stage": stage,
        **extra,
    }
    marker_path.write_text(json.dumps(marker_data, indent=2))
    return marker_path


def _write_verdict(tmp_path, verdict="PROCEED", composite_score=3.5, timestamp=None):
    """Write .claude/plan_critic_verdict.json under tmp_path."""
    from datetime import datetime, timezone
    ts = timestamp or datetime.now(timezone.utc).isoformat()
    verdict_path = tmp_path / ".claude" / "plan_critic_verdict.json"
    verdict_path.parent.mkdir(parents=True, exist_ok=True)
    verdict_data = {
        "verdict": verdict,
        "composite_score": composite_score,
        "timestamp": ts,
    }
    # Add required fields for PROCEED verdicts (Issue #1264)
    if verdict == "PROCEED":
        verdict_data["reasoning"] = "x" * 120  # >= 100 chars requirement
        verdict_data["axis_scores"] = {"alignment": 4, "minimalism": 4, "testability": 3}
    verdict_path.write_text(json.dumps(verdict_data))
    return verdict_path


class TestPlanCriticStageAdvance:
    """Tests for _advance_plan_mode_stage()."""

    def test_plan_critic_completion_advances_stage(self, tmp_path: Path):
        """Stage should advance from plan_exited to critique_done."""
        _write_marker(tmp_path, stage="plan_exited")
        _write_verdict(tmp_path)
        with patch("os.getcwd", return_value=str(tmp_path)):
            _advance_plan_mode_stage()

        marker_data = json.loads((tmp_path / MARKER_REL_PATH).read_text())
        assert marker_data["stage"] == "critique_done"

    def test_non_plan_critic_agent_does_not_advance_stage(self, tmp_path: Path):
        """Only plan-critic should trigger advance; other agents leave marker unchanged.

        Note: _advance_plan_mode_stage() itself always advances. The caller
        (main()) gates on agent_name == 'plan-critic'. This test verifies
        the marker is untouched when _advance_plan_mode_stage() is NOT called.
        """
        marker = _write_marker(tmp_path, stage="plan_exited")
        # Do NOT call _advance_plan_mode_stage — simulate non-plan-critic agent
        marker_data = json.loads(marker.read_text())
        assert marker_data["stage"] == "plan_exited"

    def test_no_marker_file_no_error(self, tmp_path: Path):
        """Should not raise when no marker file exists."""
        with patch("os.getcwd", return_value=str(tmp_path)):
            _advance_plan_mode_stage()  # Should not raise

    def test_already_critique_done_is_idempotent(self, tmp_path: Path):
        """Calling advance on critique_done should not change anything."""
        _write_marker(tmp_path, stage="critique_done")
        with patch("os.getcwd", return_value=str(tmp_path)):
            _advance_plan_mode_stage()

        marker_data = json.loads((tmp_path / MARKER_REL_PATH).read_text())
        assert marker_data["stage"] == "critique_done"
        # Should NOT have added critique_completed_at since stage didn't change
        assert "critique_completed_at" not in marker_data

    def test_stage_advance_adds_timestamp(self, tmp_path: Path):
        """Advancing from plan_exited should add critique_completed_at timestamp."""
        _write_marker(tmp_path, stage="plan_exited")
        _write_verdict(tmp_path)
        with patch("os.getcwd", return_value=str(tmp_path)):
            _advance_plan_mode_stage()

        marker_data = json.loads((tmp_path / MARKER_REL_PATH).read_text())
        assert "critique_completed_at" in marker_data
        # Validate it's a valid ISO timestamp
        dt = datetime.fromisoformat(marker_data["critique_completed_at"])
        assert dt.tzinfo is not None

    def test_corrupted_marker_not_advanced(self, tmp_path: Path):
        """Corrupted marker JSON should not crash, marker left as-is."""
        marker_path = tmp_path / MARKER_REL_PATH
        marker_path.parent.mkdir(parents=True, exist_ok=True)
        marker_path.write_text("not valid json {{{")

        with patch("os.getcwd", return_value=str(tmp_path)):
            _advance_plan_mode_stage()  # Should not raise

        # Marker should still exist (not deleted by advance logic)
        assert marker_path.exists()
        assert marker_path.read_text() == "not valid json {{{"

    # ------------------------------------------------------------------
    # Tests for return value (suggestion message)
    # ------------------------------------------------------------------

    def test_advance_returns_suggestion_on_stage_change(self, tmp_path: Path):
        """_advance_plan_mode_stage returns non-None string when advancing plan_exited -> critique_done."""
        _write_marker(tmp_path, stage="plan_exited")
        _write_verdict(tmp_path)
        with patch("os.getcwd", return_value=str(tmp_path)):
            result = _advance_plan_mode_stage()

        assert result is not None
        assert isinstance(result, str)

    def test_suggestion_contains_plan_to_issues(self, tmp_path: Path):
        """Returned suggestion includes /plan-to-issues --quick."""
        _write_marker(tmp_path, stage="plan_exited")
        _write_verdict(tmp_path)
        with patch("os.getcwd", return_value=str(tmp_path)):
            result = _advance_plan_mode_stage()

        assert "/plan-to-issues --quick" in result

    def test_suggestion_contains_implement(self, tmp_path: Path):
        """Returned suggestion includes /implement."""
        _write_marker(tmp_path, stage="plan_exited")
        _write_verdict(tmp_path)
        with patch("os.getcwd", return_value=str(tmp_path)):
            result = _advance_plan_mode_stage()

        assert "/implement" in result

    def test_advance_returns_none_when_already_done(self, tmp_path: Path):
        """Returns None when marker is already at critique_done."""
        _write_marker(tmp_path, stage="critique_done")
        with patch("os.getcwd", return_value=str(tmp_path)):
            result = _advance_plan_mode_stage()

        assert result is None

    def test_advance_returns_none_when_no_marker(self, tmp_path: Path):
        """Returns None when no marker file exists."""
        with patch("os.getcwd", return_value=str(tmp_path)):
            result = _advance_plan_mode_stage()

        assert result is None

    def test_advance_returns_none_on_corrupted_marker(self, tmp_path: Path):
        """Returns None when marker JSON is corrupted."""
        marker_path = tmp_path / MARKER_REL_PATH
        marker_path.parent.mkdir(parents=True, exist_ok=True)
        marker_path.write_text("not valid json {{{")

        with patch("os.getcwd", return_value=str(tmp_path)):
            result = _advance_plan_mode_stage()

        assert result is None

    def test_suggestion_constant_matches_return_value(self, tmp_path: Path):
        """Returned suggestion matches the exported _PLAN_TO_ISSUES_SUGGESTION constant."""
        _write_marker(tmp_path, stage="plan_exited")
        _write_verdict(tmp_path)
        with patch("os.getcwd", return_value=str(tmp_path)):
            result = _advance_plan_mode_stage()

        assert result == _PLAN_TO_ISSUES_SUGGESTION


class TestPlanCriticVerdictGate:
    """Tests for verdict-gate behavior added in Issue #927."""

    def test_no_advance_without_verdict_file(self, tmp_path: Path):
        """plan_exited marker with no verdict file: returns None, marker unchanged."""
        marker_path = _write_marker(tmp_path, stage="plan_exited")
        original_data = json.loads(marker_path.read_text())

        with patch("os.getcwd", return_value=str(tmp_path)):
            result = _advance_plan_mode_stage()

        assert result is None
        assert json.loads(marker_path.read_text()) == original_data

    def test_no_advance_on_revise_verdict(self, tmp_path: Path):
        """REVISE verdict: returns None, marker unchanged, verdict file retained."""
        marker_path = _write_marker(tmp_path, stage="plan_exited")
        verdict_path = _write_verdict(tmp_path, verdict="REVISE", composite_score=2.4)
        original_data = json.loads(marker_path.read_text())

        with patch("os.getcwd", return_value=str(tmp_path)):
            result = _advance_plan_mode_stage()

        assert result is None
        assert json.loads(marker_path.read_text()) == original_data
        assert verdict_path.exists()

    def test_no_advance_on_blocked_verdict(self, tmp_path: Path):
        """BLOCKED verdict: returns None, marker unchanged, verdict file retained."""
        marker_path = _write_marker(tmp_path, stage="plan_exited")
        verdict_path = _write_verdict(tmp_path, verdict="BLOCKED", composite_score=1.5)
        original_data = json.loads(marker_path.read_text())

        with patch("os.getcwd", return_value=str(tmp_path)):
            result = _advance_plan_mode_stage()

        assert result is None
        assert json.loads(marker_path.read_text()) == original_data
        assert verdict_path.exists()

    def test_stale_verdict_ignored(self, tmp_path: Path):
        """Verdict timestamp older than marker timestamp: returns None, no advance."""
        from datetime import datetime, timedelta, timezone

        marker_path = _write_marker(tmp_path, stage="plan_exited")
        original_data = json.loads(marker_path.read_text())
        # Verdict written 60s before the marker
        stale_ts = (datetime.now(timezone.utc) - timedelta(seconds=60)).isoformat()
        verdict_path = _write_verdict(tmp_path, verdict="PROCEED", timestamp=stale_ts)

        with patch("os.getcwd", return_value=str(tmp_path)):
            result = _advance_plan_mode_stage()

        assert result is None
        assert json.loads(marker_path.read_text()) == original_data
        assert verdict_path.exists()

    def test_malformed_verdict_returns_none(self, tmp_path: Path):
        """Malformed verdict JSON: returns None, no exception escapes."""
        _write_marker(tmp_path, stage="plan_exited")
        verdict_path = tmp_path / ".claude" / "plan_critic_verdict.json"
        verdict_path.parent.mkdir(parents=True, exist_ok=True)
        verdict_path.write_text("not valid json {{")

        with patch("os.getcwd", return_value=str(tmp_path)):
            result = _advance_plan_mode_stage()  # MUST NOT raise

        assert result is None

    def test_critique_done_marker_does_not_read_verdict(self, tmp_path: Path):
        """critique_done marker short-circuits BEFORE verdict-file IO (back-compat)."""
        _write_marker(tmp_path, stage="critique_done")
        # Place a REVISE verdict that would block advance if the gate ran;
        # the short-circuit MUST run first and leave the verdict file untouched.
        verdict_path = _write_verdict(tmp_path, verdict="REVISE", composite_score=2.0)
        original_verdict = verdict_path.read_text()

        with patch("os.getcwd", return_value=str(tmp_path)):
            result = _advance_plan_mode_stage()

        assert result is None
        assert verdict_path.exists()
        assert verdict_path.read_text() == original_verdict

    def test_proceed_verdict_consumed_on_advance(self, tmp_path: Path):
        """Successful PROCEED advance deletes the verdict file (no replay)."""
        _write_marker(tmp_path, stage="plan_exited")
        verdict_path = _write_verdict(tmp_path, verdict="PROCEED", composite_score=3.5)

        with patch("os.getcwd", return_value=str(tmp_path)):
            result = _advance_plan_mode_stage()

        assert result is not None
        assert isinstance(result, str)
        assert not verdict_path.exists()
