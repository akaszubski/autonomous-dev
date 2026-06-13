"""
Tests for pipeline_completion_state.py — shared state for agent ordering enforcement.

Issues: #625, #629, #632
"""

import json
import os
import sys
import time
from pathlib import Path
from unittest.mock import patch

import pytest

# Add lib to path
LIB_DIR = Path(__file__).resolve().parents[3] / "plugins" / "autonomous-dev" / "lib"
sys.path.insert(0, str(LIB_DIR))

from pipeline_completion_state import (
    _read_state,
    _state_file_path,
    clear_session,
    get_completed_agents,
    get_launched_agents,
    get_plan_critic_skipped,
    get_prompt_baseline,
    get_research_skipped,
    get_validation_mode,
    record_agent_completion,
    record_agent_launch,
    record_plan_critic_skipped,
    record_prompt_baseline,
    record_research_skipped,
    set_validation_mode,
)


@pytest.fixture()
def session_id():
    """Unique session ID for test isolation."""
    return f"test_session_{os.getpid()}_{time.time_ns()}"


@pytest.fixture(autouse=True)
def cleanup_state(session_id):
    """Clean up state file after each test.

    Also clears the 'unknown' session to prevent cross-test contamination
    from the merge logic added in Issue #777.
    """
    clear_session("unknown")
    yield
    clear_session(session_id)
    clear_session("unknown")


class TestRecordAndRead:
    """Round-trip tests for recording and reading completions."""

    def test_record_and_read_single(self, session_id):
        record_agent_completion(session_id, "planner")
        completed = get_completed_agents(session_id)
        assert "planner" in completed

    def test_multiple_agents_accumulate(self, session_id):
        record_agent_completion(session_id, "planner")
        record_agent_completion(session_id, "implementer")
        completed = get_completed_agents(session_id)
        assert completed == {"planner", "implementer"}

    def test_issue_isolation(self, session_id):
        record_agent_completion(session_id, "planner", issue_number=1)
        record_agent_completion(session_id, "reviewer", issue_number=2)

        issue1 = get_completed_agents(session_id, issue_number=1)
        issue2 = get_completed_agents(session_id, issue_number=2)

        assert issue1 == {"planner"}
        assert issue2 == {"reviewer"}

    def test_success_false_not_in_completed(self, session_id):
        record_agent_completion(session_id, "planner", success=False)
        completed = get_completed_agents(session_id)
        assert "planner" not in completed

    def test_missing_file_returns_empty_set(self, session_id):
        completed = get_completed_agents(session_id)
        assert completed == set()


class TestPromptBaselines:
    """Tests for prompt baseline tracking."""

    def test_record_and_get_baseline(self, session_id):
        record_prompt_baseline(session_id, "reviewer", 718, 0)
        baseline = get_prompt_baseline(session_id, "reviewer")
        assert baseline == 718

    def test_missing_baseline_returns_none(self, session_id):
        baseline = get_prompt_baseline(session_id, "reviewer")
        assert baseline is None

    def test_baseline_for_unknown_agent_returns_none(self, session_id):
        record_prompt_baseline(session_id, "reviewer", 718, 0)
        baseline = get_prompt_baseline(session_id, "unknown")
        assert baseline is None


class TestValidationMode:
    """Tests for validation mode management."""

    def test_default_mode_is_sequential(self, session_id):
        mode = get_validation_mode(session_id)
        assert mode == "sequential"

    def test_set_and_get_mode(self, session_id):
        set_validation_mode(session_id, "parallel")
        mode = get_validation_mode(session_id)
        assert mode == "parallel"

    def test_set_validation_mode_accepts_issue_number_kwarg(self, session_id):
        """Regression for #1214: set_validation_mode must accept issue_number
        kwarg without TypeError, even though validation mode is session-scoped
        and the value is intentionally ignored."""
        # The coordinator passes issue_number by reflex (parity with the rest
        # of the module). Before #1214 this raised TypeError mid-pipeline.
        set_validation_mode(session_id, "sequential", issue_number=1292)
        assert get_validation_mode(session_id) == "sequential"

        # Verify a non-zero issue number does not "leak" into the stored
        # state — mode is session-scoped only.
        set_validation_mode(session_id, "parallel", issue_number=999)
        assert get_validation_mode(session_id) == "parallel"

    def test_set_validation_mode_accepts_run_id_kwarg(self, session_id, tmp_path, monkeypatch):
        """#1214 symmetry: set_validation_mode must accept run_id kwarg and
        route writes to the run-id-scoped state file. Reading via the legacy
        path (no run_id) must NOT return the run-id-scoped value."""
        run_id = f"test-1214-{os.getpid()}-{time.time_ns()}"

        # Default-path reads "sequential" (no state yet).
        assert get_validation_mode(session_id) == "sequential"

        # Write to the run-id-scoped state file.
        set_validation_mode(session_id, "parallel", run_id=run_id)

        # Read it back via the same run_id — must round-trip.
        assert get_validation_mode(session_id, run_id=run_id) == "parallel"

        # Legacy-path read (no run_id) must still return the default,
        # proving the run-id-scoped write is isolated.
        assert get_validation_mode(session_id) == "sequential"

        # Clean up the run-id state file
        run_id_path = _state_file_path(session_id, run_id=run_id)
        if run_id_path.exists():
            run_id_path.unlink()


class TestRecordResearchSkipped1213:
    """Regression tests for Issue #1213 — record_research_skipped multi-scope write."""

    def test_record_research_skipped_writes_under_issue_number_zero_when_explicit(
        self, session_id
    ):
        """Core regression test for #1213: when issue_number is non-zero, the
        marker must ALSO be queryable under issue_number=0 (the commit-gate
        fallback key). Writer compensates so the reader contract is preserved."""
        record_research_skipped(session_id, issue_number=1292)

        # Per-issue lookup must still work (no regression).
        assert get_research_skipped(session_id, issue_number=1292) is True

        # Fallback "0" scope lookup must now ALSO work — this is the #1213 fix.
        # Before the fix, the commit-time gate queried "0" and found nothing,
        # incorrectly reporting researcher/researcher-local as missing.
        assert get_research_skipped(session_id, issue_number=0) is True

    def test_record_research_skipped_no_zero_write_when_already_zero(self, session_id):
        """When the caller already passes issue_number=0 (or omits it), the
        state must contain exactly ONE key in research_skipped — no spurious
        duplicate write."""
        record_research_skipped(session_id, issue_number=0)

        # Inspect the raw state to confirm structure: exactly one key, "0".
        state = _read_state(session_id)
        assert state, "state file should exist after record_research_skipped"
        research_skipped = state.get("research_skipped", {})
        assert research_skipped == {"0": True}, (
            f"Expected exactly one key '0': True, got {research_skipped!r}"
        )

    def test_record_research_skipped_unrelated_issue_not_marked(self, session_id):
        """Sanity: writing for issue 1292 does NOT mark some other issue
        (1293) as skipped. The "0" scope is the explicit fallback; arbitrary
        per-issue scopes must remain isolated."""
        record_research_skipped(session_id, issue_number=1292)
        assert get_research_skipped(session_id, issue_number=1293) is False


class TestRecordPlanCriticSkipped1213:
    """Regression tests for Issue #1213 — record_plan_critic_skipped multi-scope write."""

    def test_record_plan_critic_skipped_writes_under_issue_number_zero_when_explicit(
        self, session_id
    ):
        """Symmetric to record_research_skipped #1213 fix: when issue_number
        is non-zero, the plan_critic_skipped marker must ALSO be queryable
        under issue_number=0."""
        record_plan_critic_skipped(session_id, issue_number=1292)

        assert get_plan_critic_skipped(session_id, issue_number=1292) is True
        assert get_plan_critic_skipped(session_id, issue_number=0) is True

    def test_record_plan_critic_skipped_no_zero_write_when_already_zero(self, session_id):
        """When issue_number=0, state contains exactly one key — no spurious
        duplicate."""
        record_plan_critic_skipped(session_id, issue_number=0)

        state = _read_state(session_id)
        assert state, "state file should exist after record_plan_critic_skipped"
        plan_critic_skipped = state.get("plan_critic_skipped", {})
        assert plan_critic_skipped == {"0": True}, (
            f"Expected exactly one key '0': True, got {plan_critic_skipped!r}"
        )


class TestClearSession:
    """Tests for session cleanup."""

    def test_clear_removes_file(self, session_id):
        record_agent_completion(session_id, "planner")
        path = _state_file_path(session_id)
        assert path.exists()
        clear_session(session_id)
        assert not path.exists()

    def test_clear_nonexistent_session_is_safe(self):
        clear_session("nonexistent_session_12345")


class TestLaunchTracking:
    """Tests for agent launch tracking. Issue #686."""

    def test_record_and_get_single_launch(self, session_id):
        record_agent_launch(session_id, "reviewer")
        launched = get_launched_agents(session_id)
        assert "reviewer" in launched

    def test_multiple_launches_accumulate(self, session_id):
        record_agent_launch(session_id, "reviewer")
        record_agent_launch(session_id, "security-auditor")
        launched = get_launched_agents(session_id)
        assert launched == {"reviewer", "security-auditor"}

    def test_launch_issue_isolation(self, session_id):
        record_agent_launch(session_id, "reviewer", issue_number=1)
        record_agent_launch(session_id, "implementer", issue_number=2)

        issue1 = get_launched_agents(session_id, issue_number=1)
        issue2 = get_launched_agents(session_id, issue_number=2)

        assert issue1 == {"reviewer"}
        assert issue2 == {"implementer"}

    def test_missing_file_returns_empty_set(self, session_id):
        launched = get_launched_agents(session_id)
        assert launched == set()

    def test_launches_independent_of_completions(self, session_id):
        """Launches and completions are tracked separately."""
        record_agent_launch(session_id, "reviewer")
        record_agent_completion(session_id, "implementer")

        launched = get_launched_agents(session_id)
        completed = get_completed_agents(session_id)

        assert launched == {"reviewer"}
        assert completed == {"implementer"}

    def test_launch_idempotent(self, session_id):
        """Recording same launch twice doesn't break anything."""
        record_agent_launch(session_id, "reviewer")
        record_agent_launch(session_id, "reviewer")
        launched = get_launched_agents(session_id)
        assert launched == {"reviewer"}


class TestCorruptedFile:
    """Tests for corrupted/stale file handling."""

    def test_corrupted_file_returns_empty_set(self, session_id):
        path = _state_file_path(session_id)
        path.write_text("not valid json {{{")
        completed = get_completed_agents(session_id)
        assert completed == set()

    def test_stale_file_returns_empty_set(self, session_id):
        record_agent_completion(session_id, "planner")
        path = _state_file_path(session_id)
        # Set mtime to 3 hours ago
        old_time = time.time() - 3 * 3600
        os.utime(path, (old_time, old_time))
        completed = get_completed_agents(session_id)
        assert completed == set()
