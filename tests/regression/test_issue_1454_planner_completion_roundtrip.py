"""Regression tests for Issue #1454 — the plan-critic REVISE gate is unsatisfiable.

MEASURED LIVE (session cc5ba4af, 2026-08-15):

    planner count BEFORE:                              0
    record_agent_completion(sid, 'planner', issue_number=1503)
    planner count AFTER record_agent_completion:       0

``unified_pre_tool`` blocks implementer dispatch when
``.claude/plan_critic_verdict.json`` holds ``verdict: REVISE`` and
``get_planner_completion_count(session_id, verdict_epoch)`` returns 0. That
counter never returns non-zero, so the gate's allow-branch is dead code and an
honest REVISE verdict deadlocks the pipeline permanently.

WHY THE EXISTING TESTS DIDN'T CATCH IT
--------------------------------------
Per #1454: the existing tests exercise the READER against hand-built fixtures
rather than against what the WRITER actually produces. Two writer/reader
mismatches were reported:

  1. Nesting  -- reader expects completions[issue]["completed"]["planner"],
                 writer stores completions[issue]["planner"]
  2. Shape    -- reader requires a dict carrying a numeric timestamp,
                 writer stores a bare bool

Either alone makes the count structurally 0.

So every test here goes THROUGH THE REAL WRITER. A fixture-based test of the
reader would pass while the pipeline stays deadlocked -- that is precisely the
defect class, and writing the test against fixtures would reproduce it.

Why it matters beyond the deadlock: #1457 documents that both available exits
are dishonest -- hand-edit the verdict to PASS (fabricating a quality result
that was never derived), or re-label the work to a non-gated agent type. A gate
whose only escapes are dishonest will be escaped dishonestly, and its verdicts
stop meaning anything.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

_LIB = Path(__file__).resolve().parents[2] / "plugins" / "autonomous-dev" / "lib"
if str(_LIB) not in sys.path:
    sys.path.insert(0, str(_LIB))

import pipeline_completion_state as pcs  # noqa: E402


@pytest.fixture
def session(tmp_path, monkeypatch):
    """A clean, isolated session so tests never read live pipeline state."""
    monkeypatch.chdir(tmp_path)
    (tmp_path / ".claude" / "local").mkdir(parents=True, exist_ok=True)
    sid = "test-session-1454"
    try:
        pcs.clear_session(sid)
    except Exception:
        pass
    return sid


class TestPlannerCompletionRoundTrip:
    """THE CORE DEFECT — writer and reader must agree.

    Every assertion goes through record_agent_completion(), the only
    production writer. This is the round-trip test #1454 asks for.
    """

    def test_recording_planner_makes_the_count_nonzero(self, session):
        """THE MEASURED CASE. Record via the real writer, read via the real
        reader, expect the gate's allow-branch to become reachable."""
        assert pcs.get_planner_completion_count(session, 0) == 0, "precondition"

        pcs.record_agent_completion(session, "planner", issue_number=1503)

        assert pcs.get_planner_completion_count(session, 0) > 0, (
            "record_agent_completion() did not make the planner count "
            "non-zero. The REVISE gate's allow-branch is therefore dead code "
            "and an honest REVISE verdict deadlocks the pipeline with no "
            "honest escape (#1454)."
        )

    def test_count_is_zero_before_any_planner_runs(self, session):
        """NEGATIVE CONTROL. A fix that always returns non-zero would make the
        gate never fire, which is a regression, not a fix."""
        assert pcs.get_planner_completion_count(session, 0) == 0

    def test_recording_a_different_agent_does_not_count_as_planner(self, session):
        """NEGATIVE CONTROL. Only the planner satisfies the planner gate."""
        pcs.record_agent_completion(session, "implementer", issue_number=1503)
        pcs.record_agent_completion(session, "reviewer", issue_number=1503)
        assert pcs.get_planner_completion_count(session, 0) == 0, (
            "A non-planner completion satisfied the planner gate -- the gate "
            "would then be satisfiable without re-invoking the planner, which "
            "is the behaviour it exists to require."
        )

    def test_remediation_recording_also_counts(self, session):
        """The gate's whole purpose is the post-REVISE re-invocation, which the
        pipeline records as a remediation cycle."""
        pcs.record_agent_completion(
            session, "planner", issue_number=1503, is_remediation=True
        )
        assert pcs.get_planner_completion_count(session, 0) > 0


class TestSinceTimestampSemantics:
    """The gate passes a verdict epoch: only planner runs AFTER the REVISE
    verdict should satisfy it, or a stale pre-verdict run would clear the gate.
    """

    def test_planner_before_the_epoch_does_not_satisfy_a_later_verdict(self, session):
        import time

        pcs.record_agent_completion(session, "planner", issue_number=1503)
        time.sleep(0.01)
        future_epoch = time.time() + 3600

        assert pcs.get_planner_completion_count(session, future_epoch) == 0, (
            "A planner run that predates the REVISE verdict satisfied the "
            "gate. The gate would then be clearable by work done before the "
            "critique existed."
        )

    def test_planner_after_the_epoch_satisfies_the_gate(self, session):
        import time

        epoch = time.time()
        time.sleep(0.01)
        pcs.record_agent_completion(session, "planner", issue_number=1503)

        assert pcs.get_planner_completion_count(session, epoch) > 0


class TestNeverRaises:
    """State helpers must never break a hook."""

    def test_count_on_unknown_session_is_zero_not_an_error(self, session):
        assert pcs.get_planner_completion_count("no-such-session-xyz", 0) == 0
