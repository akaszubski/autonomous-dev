"""
Integration tests for run_id-based crash/resume — Issue #1047.

Verifies that agent completions written under one session_id are readable
via run_id from a fresh (different) session_id, matching the crash-resume
scenario: "Crash + resume in fresh Claude process via --resume <run_id>
inherits completions without manual record_agent_completion()."

Acceptance criterion #4 from Issue #1047.
"""

import sys
from pathlib import Path

import pytest

_LIB = Path(__file__).resolve().parents[2] / "plugins" / "autonomous-dev" / "lib"
if str(_LIB) not in sys.path:
    sys.path.insert(0, str(_LIB))

from pipeline_completion_state import get_completed_agents, record_agent_completion
from pipeline_state import generate_run_id


class TestRunIdResumeInheritsCompletions:
    """AC#4: --resume <run_id> inherits completions across session boundaries."""

    def test_run_id_resume_inherits_completions(self) -> None:
        """Completions recorded under session A are visible from session B via run_id."""
        run_id = generate_run_id()
        sid_original = "test-sid-1047-resume-original"

        # Original session records two agents
        record_agent_completion(sid_original, "planner", issue_number=1047, run_id=run_id)
        record_agent_completion(sid_original, "implementer", issue_number=1047, run_id=run_id)

        # Fresh session (simulating crash + new Claude process) reads via run_id
        sid_fresh = "fresh-sid-1047-resume-new"
        completions = get_completed_agents(sid_fresh, issue_number=1047, run_id=run_id)

        assert "planner" in completions, (
            f"planner not found in completions after resume: {completions}"
        )
        assert "implementer" in completions, (
            f"implementer not found in completions after resume: {completions}"
        )

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
