"""Regression test for Issue #986: user-pause subtraction in extract_agent_timings."""

import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

LIB_DIR = Path(__file__).resolve().parents[2] / "plugins" / "autonomous-dev" / "lib"
sys.path.insert(0, str(LIB_DIR))

from pipeline_timing_analyzer import extract_agent_timings
from pipeline_intent_validator import PipelineEvent


def _event(action, agent, ts, session_id="s1", result_word_count=0):
    return PipelineEvent(
        pipeline_action=action,
        subagent_type=agent,
        timestamp=ts,
        result_word_count=result_word_count,
        session_id=session_id,
        tool="Agent",
        agent="coordinator",
    )


def _iso(seconds_after_epoch):
    return datetime.fromtimestamp(seconds_after_epoch, tz=timezone.utc).isoformat()


def test_extract_agent_timings_unchanged_for_normal_span():
    inv_ts = _iso(1000.0)
    comp_ts = _iso(1180.0)  # 180s span — under 3600s threshold
    events = [
        _event("agent_invocation", "planner", inv_ts),
        _event("agent_completion", "planner", comp_ts, result_word_count=500),
    ]
    timings = extract_agent_timings(events)
    assert len(timings) == 1
    # 180s span unchanged; no subtraction.
    assert abs(timings[0].wall_clock_seconds - 180.0) < 1.0


def test_extract_agent_timings_subtracts_user_pause_for_long_span():
    # Synthetic 36881s span with a single 36000s gap → 881s adjusted.
    inv_ts = _iso(0.0)
    comp_ts = _iso(36881.0)
    events = [
        _event("agent_invocation", "plan-critic", inv_ts),
        _event("agent_completion", "plan-critic", comp_ts, result_word_count=200),
        # No intermediate events => sentinel boundaries detect 36881s contiguous gap;
        # since gap > MIN_PAUSE_GAP_SECONDS, longest_pause = 36881, adjusted = 0 → clamped.
        # That over-subtracts the WHOLE span. Add a synthetic mid-event to bound the pause.
    ]
    # Add one mid event 881s in (so the pause is 36000s, not 36881s)
    mid_ts = _iso(881.0)
    events.insert(1, _event("agent_completion", "researcher", mid_ts))
    timings = extract_agent_timings(events)
    plan_critic = [t for t in timings if t.agent_type == "plan-critic"][0]
    # Subtracts the 36000s gap (881 → 36881), leaving 881s active.
    assert 800.0 <= plan_critic.wall_clock_seconds <= 900.0
