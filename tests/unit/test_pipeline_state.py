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
    get_state_path,
    get_trace,
    load_pipeline,
    save_pipeline,
    skip_step,
)


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
