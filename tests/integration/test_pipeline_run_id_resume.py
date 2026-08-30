"""
Integration tests for run_id-based crash/resume — Issues #1047, #1045.

Two distinct mechanisms live here and they do NOT share a physical file:

1. **#1041/#1047 run-id-scoped state file** —
   ``/tmp/pipeline_agent_completions_{run_id}.json``, selected by passing
   ``run_id=`` to any public function. ZERO production call sites pass it, so
   nothing populates this file in a real run.
2. **#1045 run stamping inside the legacy session file** — ``record_run_start``
   writes ``current_run_id`` into the session-hashed file that every production
   writer already uses, and completions are stamped with it.

Resume in production goes through mechanism 2, because that is the only file
production writes. Mechanism 1 is exercised below only as the API-level
isolation contract it was built as; see
``test_characterization_run_id_scoped_read_is_empty_for_production_writer`` for
the gap that pairing leaves, written down rather than implied.
"""

import os
import sys
import time
import uuid
from pathlib import Path

import pytest

_LIB = Path(__file__).resolve().parents[2] / "plugins" / "autonomous-dev" / "lib"
if str(_LIB) not in sys.path:
    sys.path.insert(0, str(_LIB))

from pipeline_completion_state import (
    _state_file_path,
    get_completed_agents,
    record_agent_completion,
    record_run_start,
)
from pipeline_state import generate_run_id


def _unique_sid(tag: str) -> str:
    """Per-test session id. ``/tmp`` is process-global and never cleared."""
    return f"test-1045-resume-{tag}-{os.getpid()}-{time.time_ns()}-{uuid.uuid4().hex[:8]}"


def _purge(*session_ids: str) -> None:
    """Remove the session-hashed state files and their sibling lockfiles."""
    for session_id in session_ids:
        path = _state_file_path(session_id)
        try:
            path.unlink(missing_ok=True)
            path.with_suffix(".lock").unlink(missing_ok=True)
        except OSError:
            pass


class TestRunIdResumeInheritsCompletions:
    """AC#4: --resume <run_id> inherits completions across session boundaries."""

    def test_resume_same_run_id_inherits_completions_via_session_file(self) -> None:
        """What resume ACTUALLY does: same session file, same ``current_run_id``.

        Re-pointed at the PRODUCTION writer shape. The previous version of this
        test passed ``run_id=`` to ``record_agent_completion`` and then read
        back with the same ``run_id=`` — it supplied a writer production does
        not have, constructed both sides of its own assertion, and could not
        fail.

        The resume path that production actually exercises is: STEP 0 re-runs
        ``record_run_start`` with the SAME run id, so the stamps already on the
        completions still match and the work survives.
        """
        run_id = generate_run_id()
        sid = _unique_sid("same")
        try:
            assert record_run_start(sid, run_id) is True

            # Production writer shape — no run_id kwarg.
            record_agent_completion(sid, "planner", issue_number=1047)
            record_agent_completion(sid, "implementer", issue_number=1047)

            # Crash. STEP 0 re-enters with the SAME run id (idempotent).
            assert record_run_start(sid, run_id) is True

            completions = get_completed_agents(sid, issue_number=1047)
            assert "planner" in completions, (
                f"planner not inherited across resume: {sorted(completions)}"
            )
            assert "implementer" in completions, (
                f"implementer not inherited across resume: {sorted(completions)}"
            )
        finally:
            _purge(sid)

    def test_resume_with_a_different_run_id_does_not_inherit(self) -> None:
        """Negative control for the test above.

        The two tests differ in exactly one bit — whether the second
        ``record_run_start`` uses the same run id. Without this control, a
        ``_filter_to_current_run`` that ignored the run id entirely would still
        make the inheritance test pass.
        """
        run_a = generate_run_id()
        run_b = f"{generate_run_id()}-{uuid.uuid4().hex[:8]}"
        assert run_a != run_b, "two-run test requires two distinct run ids"

        sid = _unique_sid("diff")
        try:
            assert record_run_start(sid, run_a) is True
            record_agent_completion(sid, "planner", issue_number=1047)
            record_agent_completion(sid, "implementer", issue_number=1047)
            assert get_completed_agents(sid, issue_number=1047) == {
                "planner",
                "implementer",
            }, "precondition: run A's completions are credited to run A"

            # A NEW run in the same session — not a resume.
            assert record_run_start(sid, run_b) is True

            completions = get_completed_agents(sid, issue_number=1047)
            assert completions == set(), (
                f"run B must inherit nothing from run A, got {sorted(completions)}"
            )
        finally:
            _purge(sid)

    def test_characterization_run_id_scoped_read_is_empty_for_production_writer(
        self,
    ) -> None:
        """CHARACTERIZATION of a pre-existing gap, deliberately NOT fixed here.

        ``implement.md`` documents resume as ``get_completed_agents(sid,
        run_id=<id>)``. That reads
        ``/tmp/pipeline_agent_completions_{run_id}.json`` — a DIFFERENT physical
        file from the session-hashed one every production writer writes. So the
        documented read returns EMPTY no matter how much work the run did.

        Fixing it means re-keying every reader onto the run-id-scoped path with
        ~13 unmigrated writers still on the session path (the rejected
        Option A), which would block commits in five repos. This test pins the
        current behaviour so the gap is written down rather than implied, and so
        a future fix has to change it on purpose.
        """
        run_id = generate_run_id()
        sid = _unique_sid("gap")
        try:
            assert record_run_start(sid, run_id) is True
            record_agent_completion(sid, "planner", issue_number=1047)

            via_session_file = get_completed_agents(sid, issue_number=1047)
            assert via_session_file == {"planner"}, (
                "control: the production writer IS visible through the session file"
            )

            via_run_id_file = get_completed_agents(sid, issue_number=1047, run_id=run_id)
            assert via_run_id_file == set(), (
                "PRE-EXISTING GAP (not introduced here): the run-id-scoped file is "
                f"never written by production, so this read is empty. "
                f"Got {sorted(via_run_id_file)} — if this is now non-empty the gap "
                "has been closed and this characterization must be deleted."
            )
            assert not _state_file_path(sid, run_id=run_id).exists(), (
                "the run-id-scoped file should not even exist"
            )
        finally:
            _purge(sid)
            _state_file_path(sid, run_id=run_id).unlink(missing_ok=True)

    def test_run_id_isolation_between_runs(self) -> None:
        """Two distinct run_ids do NOT share completion state."""
        run_id_a = generate_run_id()
        run_id_b = generate_run_id()
        sid = "test-sid-1047-isolation"

        record_agent_completion(sid, "planner", issue_number=1, run_id=run_id_a)

        completions_b = get_completed_agents(sid, issue_number=1, run_id=run_id_b)
        assert "planner" not in completions_b, (
            f"planner from run_id_a leaked into run_id_b: {completions_b}"
        )

    def test_multiple_agents_survive_resume(self) -> None:
        """All agents recorded before crash are available post-resume."""
        run_id = generate_run_id()
        sid_pre_crash = "test-sid-1047-pre-crash"
        sid_post_crash = "test-sid-1047-post-crash"
        agents = ["planner", "researcher-local", "implementer", "reviewer"]

        for agent in agents:
            record_agent_completion(
                sid_pre_crash, agent, issue_number=1047, run_id=run_id
            )

        completions = get_completed_agents(
            sid_post_crash, issue_number=1047, run_id=run_id
        )

        for agent in agents:
            assert agent in completions, (
                f"Agent '{agent}' missing after resume. Present: {completions}"
            )
