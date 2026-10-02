"""Tests for pipeline_state.py - Pipeline state machine for /implement.

TDD Red Phase: These tests should FAIL until pipeline_state.py is implemented.

Tests cover:
1. Creation and serialization (5 tests)
2. Step advancement (6 tests)
3. Gate enforcement (8 tests)
4. Trace and reporting (3 tests)
5. Cleanup (2 tests)
6. Edge cases (3 tests)

Total: 27 tests
"""

import json
import os
import sys
import time
from pathlib import Path
from typing import Dict, List, Optional

import pytest

# Add lib to path for imports
lib_path = (
    Path(__file__).resolve().parent.parent.parent
    / "plugins"
    / "autonomous-dev"
    / "lib"
)
sys.path.insert(0, str(lib_path))

from pipeline_state import (
    GATE_CONDITIONS,
    SKIPPABLE_STEPS,
    STEP_SEQUENCE,
    Step,
    StepStatus,
    advance,
    can_advance,
    cleanup_pipeline,
    complete_step,
    create_pipeline,
    finalize_to_session,
    get_completion_summary,
    get_state_path,
    get_trace,
    load_pipeline,
    save_pipeline,
    skip_step,
)


def test_save_pipeline_restricts_checkpoint_permissions(pipeline_with_tmp):
    """Native-owned checkpoints reuse restrictive atomic persistence."""
    state, _root = pipeline_with_tmp
    previous = os.umask(0o022)
    try:
        path = save_pipeline(state)
    finally:
        os.umask(previous)
    assert path.stat().st_mode & 0o777 == 0o600


def test_save_pipeline_failed_replace_preserves_checkpoint(pipeline_with_tmp, monkeypatch):
    """Failure retains the previous bytes and removes the temporary candidate."""
    state, root = pipeline_with_tmp
    path = save_pipeline(state)
    before = path.read_bytes()

    def refuse_replace(source, target):
        raise OSError("replacement unavailable")

    monkeypatch.setattr("pipeline_state.os.replace", refuse_replace)
    state.feature = "Changed workflow intent"
    with pytest.raises(OSError, match="replacement unavailable"):
        save_pipeline(state)
    assert path.read_bytes() == before
    assert not list(root.glob("*.tmp"))


# =============================================================================
# FIXTURES
# =============================================================================


@pytest.fixture
def run_id():
    """A unique run ID for testing."""
    return f"test-run-{int(time.time() * 1000)}"


@pytest.fixture
def pipeline(run_id, monkeypatch, tmp_path):
    """Create a fresh pipeline with /tmp redirected to tmp_path."""
    monkeypatch.setattr(
        "pipeline_state.get_state_path",
        lambda rid: tmp_path / f"pipeline_state_{rid}.json",
    )
    return create_pipeline(run_id, "Add user authentication")


@pytest.fixture
def pipeline_with_tmp(run_id, monkeypatch, tmp_path):
    """Create a pipeline and return (state, tmp_path) for save/load tests."""
    monkeypatch.setattr(
        "pipeline_state.get_state_path",
        lambda rid: tmp_path / f"pipeline_state_{rid}.json",
    )
    state = create_pipeline(run_id, "Add user authentication")
    return state, tmp_path


# =============================================================================
# 1. CREATION AND SERIALIZATION
# =============================================================================


class TestCreationAndSerialization:
    """Test pipeline creation, save, load, and path formatting."""

    def test_create_pipeline_returns_state_with_all_steps(self, run_id):
        """Creating a pipeline should produce a state with all steps in PENDING status."""
        state = create_pipeline(run_id, "Add login feature")

        # All steps from STEP_SEQUENCE should be present
        for step in STEP_SEQUENCE:
            assert step.value in state.steps or step in state.steps, (
                f"Step {step} missing from pipeline state"
            )

    def test_create_pipeline_stores_metadata(self, run_id):
        """Pipeline state should store run_id, feature description, and mode."""
        state = create_pipeline(run_id, "Fix bug #123", mode="quick")

        assert state.run_id == run_id
        assert state.feature == "Fix bug #123"
        assert state.mode == "quick"

    def test_save_and_load_roundtrip(self, run_id, monkeypatch, tmp_path):
        """Saving then loading a pipeline should produce identical state."""
        monkeypatch.setattr(
            "pipeline_state.get_state_path",
            lambda rid: tmp_path / f"pipeline_state_{rid}.json",
        )
        original = create_pipeline(run_id, "Feature X")
        save_pipeline(original)
        loaded = load_pipeline(run_id)

        assert loaded is not None
        assert loaded.run_id == original.run_id
        assert loaded.feature == original.feature
        assert loaded.mode == original.mode

    def test_load_nonexistent_returns_none(self, monkeypatch, tmp_path):
        """Loading a pipeline that doesn't exist should return None."""
        monkeypatch.setattr(
            "pipeline_state.get_state_path",
            lambda rid: tmp_path / f"pipeline_state_{rid}.json",
        )
        result = load_pipeline("nonexistent-run-id-12345")
        assert result is None

    def test_get_state_path_format(self):
        """State path should be in /tmp with the run_id embedded."""
        path = get_state_path("my-run-42")
        assert "my-run-42" in str(path)
        assert str(path).startswith("/tmp") or str(path).startswith("/var")
        assert path.suffix == ".json"


# =============================================================================
# 2. STEP ADVANCEMENT
# =============================================================================


class TestStepAdvancement:
    """Test advancing steps through the state machine."""

    def test_advance_sets_step_to_running(self, pipeline):
        """Advancing a step should set its status to RUNNING."""
        updated = advance(pipeline, Step.ALIGNMENT)
        # Check the step is now RUNNING
        step_status = self._get_step_status(updated, Step.ALIGNMENT)
        assert step_status == StepStatus.RUNNING

    def test_complete_step_passed(self, pipeline):
        """Completing a step with passed=True should set status to PASSED."""
        started = advance(pipeline, Step.ALIGNMENT)
        completed = complete_step(started, Step.ALIGNMENT, passed=True)
        step_status = self._get_step_status(completed, Step.ALIGNMENT)
        assert step_status == StepStatus.PASSED

    def test_complete_step_failed(self, pipeline):
        """Completing a step with passed=False should set status to FAILED."""
        started = advance(pipeline, Step.ALIGNMENT)
        completed = complete_step(
            started, Step.ALIGNMENT, passed=False, error="Misaligned with PROJECT.md"
        )
        step_status = self._get_step_status(completed, Step.ALIGNMENT)
        assert step_status == StepStatus.FAILED

    def test_skip_allowed_step(self, pipeline):
        """Skipping a step in SKIPPABLE_STEPS should succeed."""
        # Pick a skippable step
        skippable = next(iter(SKIPPABLE_STEPS))
        # First resolve all prior steps
        state = self._resolve_steps_up_to(pipeline, skippable)
        skipped = skip_step(state, skippable, reason="Not needed for this run")
        step_status = self._get_step_status(skipped, skippable)
        assert step_status == StepStatus.SKIPPED

    def test_skip_non_skippable_step_raises(self, pipeline):
        """Skipping a step NOT in SKIPPABLE_STEPS should raise an error."""
        # ALIGNMENT is not skippable
        assert Step.ALIGNMENT not in SKIPPABLE_STEPS
        with pytest.raises((ValueError, RuntimeError)):
            skip_step(pipeline, Step.ALIGNMENT, reason="Trying to skip")

    def test_advance_already_passed_step_raises(self, pipeline):
        """Advancing a step that's already PASSED should raise an error."""
        started = advance(pipeline, Step.ALIGNMENT)
        completed = complete_step(started, Step.ALIGNMENT, passed=True)
        with pytest.raises((ValueError, RuntimeError)):
            advance(completed, Step.ALIGNMENT)

    # -- Helpers --

    @staticmethod
    def _get_step_status(state, step: Step) -> StepStatus:
        """Extract step status from state (handles dict or attribute access)."""
        if hasattr(state, "steps"):
            steps = state.steps
            # Handle both Step enum keys and string keys
            if isinstance(steps, dict):
                entry = steps.get(step) or steps.get(step.value)
                if isinstance(entry, dict):
                    status_val = entry.get("status", entry.get("step_status"))
                    if isinstance(status_val, str):
                        return StepStatus(status_val)
                    return status_val
                return entry
        raise AssertionError(f"Could not extract status for {step} from state")

    @staticmethod
    def _resolve_steps_up_to(state, target_step: Step):
        """Advance and complete all steps before target_step."""
        for step in STEP_SEQUENCE:
            if step == target_step:
                break
            if step in SKIPPABLE_STEPS:
                state = skip_step(state, step, reason="test setup")
            else:
                state = advance(state, step)
                state = complete_step(state, step, passed=True)
        return state


# =============================================================================
# 3. GATE ENFORCEMENT
# =============================================================================


class TestGateEnforcement:
    """Test that gate conditions prevent advancing past unresolved prerequisites."""

    def test_implement_requires_tdd_tests(self, pipeline):
        """Cannot advance to IMPLEMENT unless TDD_TESTS is resolved."""
        # Advance through alignment, research_cache, research, plan, acceptance_tests
        # but skip TDD_TESTS
        state = pipeline
        for step in STEP_SEQUENCE:
            if step == Step.TDD_TESTS:
                # Leave TDD_TESTS in PENDING
                break
            if step in SKIPPABLE_STEPS:
                state = skip_step(state, step, reason="test setup")
            else:
                state = advance(state, step)
                state = complete_step(state, step, passed=True)

        # Now try to advance to IMPLEMENT - should be blocked
        allowed, reason = can_advance(state, Step.IMPLEMENT)
        assert not allowed, f"IMPLEMENT should be blocked without TDD_TESTS, got: {reason}"
        assert "TDD" in reason.upper() or "tdd" in reason.lower() or "test" in reason.lower()

    def test_implement_allowed_after_tdd_passed(self, pipeline):
        """Can advance to IMPLEMENT after TDD_TESTS is PASSED."""
        state = pipeline
        for step in STEP_SEQUENCE:
            if step == Step.IMPLEMENT:
                break
            if step in SKIPPABLE_STEPS and step != Step.TDD_TESTS:
                state = skip_step(state, step, reason="test setup")
            else:
                state = advance(state, step)
                state = complete_step(state, step, passed=True)

        allowed, reason = can_advance(state, Step.IMPLEMENT)
        assert allowed, f"IMPLEMENT should be allowed after TDD_TESTS passed: {reason}"

    def test_validate_requires_implement(self, pipeline):
        """Cannot advance to VALIDATE unless IMPLEMENT is resolved."""
        state = pipeline
        for step in STEP_SEQUENCE:
            if step == Step.IMPLEMENT:
                break  # Leave IMPLEMENT unresolved
            if step in SKIPPABLE_STEPS:
                state = skip_step(state, step, reason="test setup")
            else:
                state = advance(state, step)
                state = complete_step(state, step, passed=True)

        allowed, reason = can_advance(state, Step.VALIDATE)
        assert not allowed, f"VALIDATE should require IMPLEMENT: {reason}"

    def test_report_requires_verify(self, pipeline):
        """Cannot advance to REPORT unless VERIFY is resolved."""
        # Build up state to just before REPORT but skip VERIFY
        state = pipeline
        for step in STEP_SEQUENCE:
            if step == Step.REPORT:
                break
            if step == Step.VERIFY:
                # Leave VERIFY unresolved
                continue
            if step in SKIPPABLE_STEPS:
                state = skip_step(state, step, reason="test setup")
            else:
                state = advance(state, step)
                state = complete_step(state, step, passed=True)

        allowed, reason = can_advance(state, Step.REPORT)
        assert not allowed, f"REPORT should require VERIFY: {reason}"

    def test_congruence_requires_report(self, pipeline):
        """Cannot advance to CONGRUENCE unless REPORT is resolved."""
        # CONGRUENCE has a gate on REPORT
        assert Step.REPORT in GATE_CONDITIONS.get(Step.CONGRUENCE, set())

    def test_ci_analysis_requires_congruence(self, pipeline):
        """Cannot advance to CI_ANALYSIS unless CONGRUENCE is resolved."""
        assert Step.CONGRUENCE in GATE_CONDITIONS.get(Step.CI_ANALYSIS, set())

    def test_gate_conditions_are_consistent_with_step_sequence(self):
        """All gate prerequisites must appear before the gated step in STEP_SEQUENCE."""
        for gated_step, prerequisites in GATE_CONDITIONS.items():
            gated_idx = STEP_SEQUENCE.index(gated_step)
            for prereq in prerequisites:
                prereq_idx = STEP_SEQUENCE.index(prereq)
                assert prereq_idx < gated_idx, (
                    f"Gate prerequisite {prereq} (index {prereq_idx}) "
                    f"must come before {gated_step} (index {gated_idx})"
                )

    def test_prior_steps_must_be_resolved_before_advancing(self, pipeline):
        """Cannot advance to a step if earlier non-skippable steps are unresolved."""
        # Try to advance directly to RESEARCH (skipping ALIGNMENT)
        allowed, reason = can_advance(pipeline, Step.RESEARCH)
        assert not allowed, (
            f"Should not advance to RESEARCH with ALIGNMENT still PENDING: {reason}"
        )


# =============================================================================
# 4. TRACE AND REPORTING
# =============================================================================


class TestTraceAndReporting:
    """Test the execution trace and timing information."""

    def test_empty_trace_on_new_pipeline(self, pipeline):
        """A freshly created pipeline should have an empty or minimal trace."""
        trace = get_trace(pipeline)
        assert isinstance(trace, list)
        # Fresh pipeline may have 0 entries or just a creation entry
        assert len(trace) <= 1

    def test_trace_records_step_transitions(self, pipeline):
        """Advancing and completing steps should produce trace entries."""
        state = advance(pipeline, Step.ALIGNMENT)
        state = complete_step(state, Step.ALIGNMENT, passed=True)
        state = advance(state, Step.RESEARCH_CACHE)

        trace = get_trace(state)
        assert isinstance(trace, list)
        # Should have at least 2 entries (advance + complete for ALIGNMENT,
        # and advance for RESEARCH_CACHE)
        assert len(trace) >= 2

        # Trace entries should reference step names
        step_names_in_trace = [
            entry.get("step", entry.get("name", ""))
            for entry in trace
        ]
        alignment_found = any(
            "alignment" in str(name).lower() for name in step_names_in_trace
        )
        assert alignment_found, f"ALIGNMENT not found in trace: {trace}"

    def test_trace_includes_timestamps(self, pipeline):
        """Trace entries should include timing information."""
        state = advance(pipeline, Step.ALIGNMENT)
        state = complete_step(state, Step.ALIGNMENT, passed=True)

        trace = get_trace(state)
        assert len(trace) >= 1

        # At least one entry should have a timestamp or duration field
        has_timing = any(
            "timestamp" in entry or "time" in entry or "started_at" in entry or "duration" in entry
            for entry in trace
        )
        assert has_timing, f"No timing info in trace entries: {trace}"


# =============================================================================
# 5. CLEANUP
# =============================================================================


class TestCleanup:
    """Test pipeline state file cleanup."""

    def test_cleanup_removes_state_file(self, run_id, monkeypatch, tmp_path):
        """Cleaning up a pipeline should remove its state file."""
        monkeypatch.setattr(
            "pipeline_state.get_state_path",
            lambda rid: tmp_path / f"pipeline_state_{rid}.json",
        )
        state = create_pipeline(run_id, "Temporary feature")
        path = save_pipeline(state)
        assert path.exists()

        cleanup_pipeline(run_id)
        assert not path.exists()

    def test_cleanup_nonexistent_no_error(self, monkeypatch, tmp_path):
        """Cleaning up a nonexistent pipeline should not raise an error."""
        monkeypatch.setattr(
            "pipeline_state.get_state_path",
            lambda rid: tmp_path / f"pipeline_state_{rid}.json",
        )
        # Should not raise
        cleanup_pipeline("does-not-exist-99999")


# =============================================================================
# 6. EDGE CASES
# =============================================================================


class TestEdgeCases:
    """Test edge cases and full pipeline traversals."""

    def test_full_happy_path(self, pipeline):
        """All steps can be advanced and completed in sequence (full mode)."""
        state = pipeline
        for step in STEP_SEQUENCE:
            allowed, reason = can_advance(state, step)
            assert allowed, f"Should be able to advance to {step}: {reason}"

            state = advance(state, step)
            state = complete_step(state, step, passed=True)

        # All steps should be PASSED or SKIPPED
        trace = get_trace(state)
        assert len(trace) >= len(STEP_SEQUENCE)

    def test_happy_path_with_skips(self, pipeline):
        """Pipeline completes when skippable steps are skipped."""
        state = pipeline
        for step in STEP_SEQUENCE:
            if step in SKIPPABLE_STEPS:
                state = skip_step(state, step, reason="Not needed")
            else:
                state = advance(state, step)
                state = complete_step(state, step, passed=True)

        # Verify all steps are resolved (none PENDING)
        for step in STEP_SEQUENCE:
            status = self._get_step_status(state, step)
            assert status in (StepStatus.PASSED, StepStatus.SKIPPED), (
                f"Step {step} should be resolved, got {status}"
            )

    def test_concurrent_save_last_write_wins(self, run_id, monkeypatch, tmp_path):
        """If two saves happen, the last one should be what load returns."""
        monkeypatch.setattr(
            "pipeline_state.get_state_path",
            lambda rid: tmp_path / f"pipeline_state_{rid}.json",
        )
        state1 = create_pipeline(run_id, "Feature A")
        state2 = create_pipeline(run_id, "Feature B")

        save_pipeline(state1)
        save_pipeline(state2)  # Overwrites

        loaded = load_pipeline(run_id)
        assert loaded is not None
        assert loaded.feature == "Feature B"

    # -- Helpers --

    @staticmethod
    def _get_step_status(state, step: Step) -> StepStatus:
        """Extract step status from state."""
        if hasattr(state, "steps"):
            steps = state.steps
            if isinstance(steps, dict):
                entry = steps.get(step) or steps.get(step.value)
                if isinstance(entry, dict):
                    status_val = entry.get("status", entry.get("step_status"))
                    if isinstance(status_val, str):
                        return StepStatus(status_val)
                    return status_val
                return entry
        raise AssertionError(f"Could not extract status for {step} from state")


# =============================================================================
# STRUCTURAL VALIDATION
# =============================================================================


class TestStructuralValidation:
    """Validate the constants and enums are well-formed."""

    def test_step_sequence_contains_all_steps(self):
        """STEP_SEQUENCE should contain all Step enum members."""
        all_steps = set(Step)
        sequence_steps = set(STEP_SEQUENCE)
        assert all_steps == sequence_steps, (
            f"Missing from sequence: {all_steps - sequence_steps}, "
            f"Extra in sequence: {sequence_steps - all_steps}"
        )

    def test_step_sequence_has_no_duplicates(self):
        """STEP_SEQUENCE should not contain duplicate steps."""
        assert len(STEP_SEQUENCE) == len(set(STEP_SEQUENCE))

    def test_skippable_steps_are_valid_steps(self):
        """All SKIPPABLE_STEPS should be valid Step enum members."""
        for step in SKIPPABLE_STEPS:
            assert isinstance(step, Step), f"{step} is not a Step enum member"

    def test_gate_conditions_reference_valid_steps(self):
        """All steps in GATE_CONDITIONS (keys and values) should be valid Steps."""
        for gated_step, prerequisites in GATE_CONDITIONS.items():
            assert isinstance(gated_step, Step), f"Gate key {gated_step} is not a Step"
            for prereq in prerequisites:
                assert isinstance(prereq, Step), (
                    f"Prerequisite {prereq} for {gated_step} is not a Step"
                )

    def test_step_sequence_minimum_length(self):
        """STEP_SEQUENCE should have at least 8 steps (the core pipeline)."""
        assert len(STEP_SEQUENCE) >= 8, (
            f"STEP_SEQUENCE too short: {len(STEP_SEQUENCE)} steps"
        )

    def test_step_status_has_required_values(self):
        """StepStatus enum should have PENDING, RUNNING, PASSED, FAILED, SKIPPED."""
        required = {"pending", "running", "passed", "failed", "skipped"}
        actual = {s.value for s in StepStatus}
        assert required.issubset(actual), f"Missing statuses: {required - actual}"


# =============================================================================
# 7. COMPLETION SUMMARY AND FINALIZATION
# =============================================================================


class TestGetCompletionSummary:
    """Tests for get_completion_summary function."""

    def test_summary_of_completed_pipeline(self, pipeline):
        """Completed pipeline returns correct summary with agent/step counts."""
        state = pipeline
        for step in STEP_SEQUENCE:
            if step in SKIPPABLE_STEPS:
                state = skip_step(state, step, reason="test setup")
            else:
                state = advance(state, step)
                state = complete_step(state, step, passed=True)

        summary = get_completion_summary(state)
        assert summary["mode"] == "full"
        assert summary["status"] == "completed"
        assert summary["step_count"] >= len(STEP_SEQUENCE)
        assert summary["agent_count"] > 0
        assert "started_at" in summary
        assert "completed_at" in summary

    def test_summary_of_failed_pipeline(self, pipeline):
        """Failed pipeline returns status='failed'."""
        state = advance(pipeline, Step.ALIGNMENT)
        state = complete_step(state, Step.ALIGNMENT, passed=False, error="Misaligned")

        summary = get_completion_summary(state)
        assert summary["status"] == "failed"

    def test_summary_of_empty_pipeline(self, pipeline):
        """Fresh pipeline with no steps started returns 'partial' status."""
        summary = get_completion_summary(pipeline)
        assert summary["status"] == "partial"
        assert summary["step_count"] == 0


class TestFinalizeToSession:
    """Tests for finalize_to_session function."""

    def test_finalize_creates_session_file(self, run_id, monkeypatch, tmp_path):
        """finalize_to_session creates a session record with pipeline data."""
        monkeypatch.setattr(
            "pipeline_state.get_state_path",
            lambda rid: tmp_path / f"pipeline_state_{rid}.json",
        )
        # Create and save a pipeline
        state = create_pipeline(run_id, "Test feature", mode="quick")
        state = advance(state, Step.ALIGNMENT)
        state = complete_step(state, Step.ALIGNMENT, passed=True)
        save_pipeline(state)

        # Set cwd to tmp_path so docs/sessions/ is created there
        monkeypatch.chdir(tmp_path)

        result = finalize_to_session(run_id)
        assert result is True

        session_file = tmp_path / "docs" / "sessions" / f"{run_id}-pipeline.json"
        assert session_file.exists()

        data = json.loads(session_file.read_text())
        assert data["run_id"] == run_id
        assert data["mode"] == "quick"
        assert data["feature"] == "Test feature"
        assert "pipeline_summary" in data
        assert "pipeline_steps" in data
        assert data["pipeline_summary"]["mode"] == "quick"

    def test_finalize_nonexistent_pipeline_returns_false(self, monkeypatch, tmp_path):
        """finalize_to_session returns False for nonexistent pipeline."""
        monkeypatch.setattr(
            "pipeline_state.get_state_path",
            lambda rid: tmp_path / f"pipeline_state_{rid}.json",
        )
        result = finalize_to_session("does-not-exist-99999")
        assert result is False


# =============================================================================
# 8. BATCH MODE FINALIZATION (Issue #540)
# =============================================================================


class TestFinalizeBatchMode:
    """Tests for finalize_to_session batch mode (feature_ref parameter).

    Issue #540: Pipeline JSON collapses batch into single session record.
    These tests verify that batch mode appends per-feature entries to a
    features[] list while preserving flat fields for v1 compatibility.
    """

    def test_finalize_batch_appends_features(self, run_id, monkeypatch, tmp_path):
        """Calling finalize_to_session with different feature_refs appends to features[]."""
        monkeypatch.setattr(
            "pipeline_state.get_state_path",
            lambda rid: tmp_path / f"pipeline_state_{rid}.json",
        )
        monkeypatch.chdir(tmp_path)

        # Create and finalize first feature
        state1 = create_pipeline(run_id, "Add login feature", mode="batch")
        state1 = advance(state1, Step.ALIGNMENT)
        state1 = complete_step(state1, Step.ALIGNMENT, passed=True)
        save_pipeline(state1)
        result1 = finalize_to_session(run_id, feature_ref="issue-101")
        assert result1 is True

        # Modify pipeline to represent second feature (reuse run_id for same session)
        state2 = create_pipeline(run_id, "Add signup feature", mode="batch")
        state2 = advance(state2, Step.ALIGNMENT)
        state2 = complete_step(state2, Step.ALIGNMENT, passed=True)
        save_pipeline(state2)
        result2 = finalize_to_session(run_id, feature_ref="issue-102")
        assert result2 is True

        # Verify features list has 2 entries
        session_file = tmp_path / "docs" / "sessions" / f"{run_id}-pipeline.json"
        data = json.loads(session_file.read_text())
        assert "features" in data
        assert len(data["features"]) == 2
        refs = [f["feature_ref"] for f in data["features"]]
        assert "issue-101" in refs
        assert "issue-102" in refs

    def test_finalize_batch_preserves_flat_fields(self, run_id, monkeypatch, tmp_path):
        """After batch finalization, flat pipeline_summary/pipeline_steps still exist."""
        monkeypatch.setattr(
            "pipeline_state.get_state_path",
            lambda rid: tmp_path / f"pipeline_state_{rid}.json",
        )
        monkeypatch.chdir(tmp_path)

        state = create_pipeline(run_id, "Batch feature A", mode="batch")
        state = advance(state, Step.ALIGNMENT)
        state = complete_step(state, Step.ALIGNMENT, passed=True)
        save_pipeline(state)
        finalize_to_session(run_id, feature_ref="feat-A")

        session_file = tmp_path / "docs" / "sessions" / f"{run_id}-pipeline.json"
        data = json.loads(session_file.read_text())
        assert "pipeline_summary" in data
        assert "pipeline_steps" in data
        assert data["feature"] == "Batch feature A"

    def test_finalize_batch_schema_version(self, run_id, monkeypatch, tmp_path):
        """Batch mode sets schema_version to '2.0', single mode to '1.0'."""
        monkeypatch.setattr(
            "pipeline_state.get_state_path",
            lambda rid: tmp_path / f"pipeline_state_{rid}.json",
        )
        monkeypatch.chdir(tmp_path)

        # Batch mode
        state = create_pipeline(run_id, "Batch feature", mode="batch")
        state = advance(state, Step.ALIGNMENT)
        state = complete_step(state, Step.ALIGNMENT, passed=True)
        save_pipeline(state)
        finalize_to_session(run_id, feature_ref="feat-1")

        session_file = tmp_path / "docs" / "sessions" / f"{run_id}-pipeline.json"
        data = json.loads(session_file.read_text())
        assert data["schema_version"] == "2.0"

        # Single mode (different run_id)
        single_run_id = run_id + "-single"
        state2 = create_pipeline(single_run_id, "Single feature", mode="quick")
        state2 = advance(state2, Step.ALIGNMENT)
        state2 = complete_step(state2, Step.ALIGNMENT, passed=True)
        save_pipeline(state2)
        finalize_to_session(single_run_id)

        single_file = tmp_path / "docs" / "sessions" / f"{single_run_id}-pipeline.json"
        data2 = json.loads(single_file.read_text())
        assert data2["schema_version"] == "1.0"

    def test_finalize_batch_idempotent(self, run_id, monkeypatch, tmp_path):
        """Calling finalize with same feature_ref twice produces only 1 entry."""
        monkeypatch.setattr(
            "pipeline_state.get_state_path",
            lambda rid: tmp_path / f"pipeline_state_{rid}.json",
        )
        monkeypatch.chdir(tmp_path)

        state = create_pipeline(run_id, "Idempotent feature", mode="batch")
        state = advance(state, Step.ALIGNMENT)
        state = complete_step(state, Step.ALIGNMENT, passed=True)
        save_pipeline(state)

        finalize_to_session(run_id, feature_ref="issue-200")
        finalize_to_session(run_id, feature_ref="issue-200")

        session_file = tmp_path / "docs" / "sessions" / f"{run_id}-pipeline.json"
        data = json.loads(session_file.read_text())
        assert len(data["features"]) == 1
        assert data["features"][0]["feature_ref"] == "issue-200"

    def test_finalize_single_feature_unchanged(self, run_id, monkeypatch, tmp_path):
        """Single-feature finalize (no feature_ref) keeps flat behavior, no features key."""
        monkeypatch.setattr(
            "pipeline_state.get_state_path",
            lambda rid: tmp_path / f"pipeline_state_{rid}.json",
        )
        monkeypatch.chdir(tmp_path)

        state = create_pipeline(run_id, "Single feature only", mode="quick")
        state = advance(state, Step.ALIGNMENT)
        state = complete_step(state, Step.ALIGNMENT, passed=True)
        save_pipeline(state)
        finalize_to_session(run_id)

        session_file = tmp_path / "docs" / "sessions" / f"{run_id}-pipeline.json"
        data = json.loads(session_file.read_text())
        assert "features" not in data
        assert data["pipeline_summary"]["mode"] == "quick"
        assert data["feature"] == "Single feature only"
        assert data["schema_version"] == "1.0"

    def test_finalize_batch_batch_id(self, run_id, monkeypatch, tmp_path):
        """Batch mode with batch_id sets the batch_id field in session data."""
        monkeypatch.setattr(
            "pipeline_state.get_state_path",
            lambda rid: tmp_path / f"pipeline_state_{rid}.json",
        )
        monkeypatch.chdir(tmp_path)

        state = create_pipeline(run_id, "Batch with ID", mode="batch")
        state = advance(state, Step.ALIGNMENT)
        state = complete_step(state, Step.ALIGNMENT, passed=True)
        save_pipeline(state)
        finalize_to_session(run_id, feature_ref="feat-X", batch_id="batch-42")

        session_file = tmp_path / "docs" / "sessions" / f"{run_id}-pipeline.json"
        data = json.loads(session_file.read_text())
        assert data["batch_id"] == "batch-42"
