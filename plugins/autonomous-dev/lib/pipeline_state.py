"""Pipeline state machine for /implement command.

Tracks pipeline step progression, enforces gate conditions, and persists
state to JSON. Zero external dependencies (stdlib only).

Usage:
    state = create_pipeline("run-001", "Add user auth")
    state = advance(state, Step.ALIGNMENT)
    state = complete_step(state, Step.ALIGNMENT, passed=True)
    trace = get_trace(state)
"""

import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple


# =============================================================================
# ENUMS
# =============================================================================


class Step(Enum):
    """Pipeline steps in execution order."""

    ALIGNMENT = "alignment"
    RESEARCH_CACHE = "research_cache"
    RESEARCH = "research"
    PLAN = "plan"
    ACCEPTANCE_TESTS = "acceptance_tests"
    TDD_TESTS = "tdd_tests"
    IMPLEMENT = "implement"
    HOOK_CHECK = "hook_check"
    VALIDATE = "validate"
    VERIFY = "verify"
    REPORT = "report"
    CONGRUENCE = "congruence"
    CI_ANALYSIS = "ci_analysis"


class StepStatus(Enum):
    """Status of a pipeline step."""

    PENDING = "pending"
    RUNNING = "running"
    PASSED = "passed"
    FAILED = "failed"
    SKIPPED = "skipped"


# =============================================================================
# CONSTANTS
# =============================================================================

STEP_SEQUENCE: List[Step] = list(Step)

SKIPPABLE_STEPS: Set[Step] = {
    Step.RESEARCH_CACHE,
    Step.ACCEPTANCE_TESTS,
    Step.TDD_TESTS,
    Step.HOOK_CHECK,
}

GATE_CONDITIONS: Dict[Step, Set[Step]] = {
    Step.IMPLEMENT: {Step.TDD_TESTS},
    Step.VALIDATE: {Step.IMPLEMENT},
    Step.REPORT: {Step.VERIFY},
    Step.CONGRUENCE: {Step.REPORT},
    Step.CI_ANALYSIS: {Step.CONGRUENCE},
}


# =============================================================================
# DATACLASSES
# =============================================================================


@dataclass
class StepRecord:
    """Record for a single pipeline step."""

    status: StepStatus = StepStatus.PENDING
    started_at: Optional[str] = None
    completed_at: Optional[str] = None
    error: Optional[str] = None


@dataclass
class PipelineState:
    """Full pipeline state including all steps and metadata.

    The steps dict uses string keys (step values) mapping to plain dicts
    with keys: status, started_at, completed_at, error. This keeps the
    state JSON-serializable and compatible with various access patterns.
    """

    run_id: str
    mode: str
    feature: str
    steps: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    created_at: str = ""
    updated_at: str = ""


# =============================================================================
# HELPERS
# =============================================================================


def _now() -> str:
    """Return current UTC timestamp as ISO string."""
    return datetime.now(timezone.utc).isoformat()


def _make_step_dict(
    status: str = "pending",
    started_at: Optional[str] = None,
    completed_at: Optional[str] = None,
    error: Optional[str] = None,
) -> Dict[str, Any]:
    """Create a step record dict."""
    return {
        "status": status,
        "started_at": started_at,
        "completed_at": completed_at,
        "error": error,
    }


def _get_step(state: PipelineState, step: Step) -> Dict[str, Any]:
    """Get step record dict from state, looking up by step value string."""
    return state.steps[step.value]


def _get_status(state: PipelineState, step: Step) -> StepStatus:
    """Get the StepStatus for a step in the pipeline."""
    record = state.steps.get(step.value)
    if record is None:
        return StepStatus.PENDING
    return StepStatus(record["status"])


# =============================================================================
# PUBLIC API
# =============================================================================


def create_pipeline(
    run_id: str,
    feature: str,
    *,
    mode: str = "full",
) -> PipelineState:
    """Create a new pipeline with all steps in PENDING status.

    Args:
        run_id: Unique identifier for this pipeline run.
        feature: Description of the feature being implemented.
        mode: Pipeline mode (e.g., "full", "quick", "batch").

    Returns:
        PipelineState with all 13 steps initialized to PENDING.
    """
    now = _now()
    steps = {step.value: _make_step_dict() for step in STEP_SEQUENCE}
    return PipelineState(
        run_id=run_id,
        mode=mode,
        feature=feature,
        steps=steps,
        created_at=now,
        updated_at=now,
    )


def get_state_path(run_id: str) -> Path:
    """Return the filesystem path for a pipeline state file.

    Args:
        run_id: The pipeline run identifier (alphanumeric, dashes, underscores).

    Returns:
        Path to the JSON state file in /tmp.

    Raises:
        ValueError: If run_id contains path traversal characters.
    """
    import re

    if not re.match(r"^[a-zA-Z0-9_-]{1,128}$", run_id):
        raise ValueError(
            f"run_id must be alphanumeric with dashes/underscores (1-128 chars): {run_id!r}"
        )
    return Path(f"/tmp/pipeline_state_{run_id}.json")


def load_pipeline(run_id: str) -> Optional[PipelineState]:
    """Load a pipeline state from disk.

    Args:
        run_id: The pipeline run identifier.

    Returns:
        PipelineState if found, None otherwise (backward compatible).
    """
    path = get_state_path(run_id)
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text())
        return PipelineState(
            run_id=data["run_id"],
            mode=data["mode"],
            feature=data["feature"],
            steps=data.get("steps", {}),
            created_at=data.get("created_at", ""),
            updated_at=data.get("updated_at", ""),
        )
    except (json.JSONDecodeError, KeyError, ValueError):
        return None


def save_pipeline(state: PipelineState) -> Path:
    """Write pipeline state to disk as JSON.

    Args:
        state: The pipeline state to persist.

    Returns:
        Path to the written state file.
    """
    state.updated_at = _now()
    path = get_state_path(state.run_id)
    data = {
        "run_id": state.run_id,
        "mode": state.mode,
        "feature": state.feature,
        "steps": state.steps,
        "created_at": state.created_at,
        "updated_at": state.updated_at,
    }
    path.write_text(json.dumps(data, indent=2))
    return path


def can_advance(state: PipelineState, step: Step) -> Tuple[bool, str]:
    """Check whether the pipeline can advance to the given step.

    Gate logic:
    1. Step must not already be PASSED (can't re-enter completed steps).
    2. All prior steps in STEP_SEQUENCE must be resolved (not PENDING).
    3. GATE_CONDITIONS prerequisites must be PASSED or SKIPPED.

    Args:
        state: Current pipeline state.
        step: The step to check advancement for.

    Returns:
        Tuple of (allowed, reason). If allowed, reason is empty string.
    """
    current_status = _get_status(state, step)
    if current_status == StepStatus.PASSED:
        return False, f"Step {step.value} is already PASSED and cannot be re-entered"

    # Check all prior steps are resolved (not PENDING)
    step_idx = STEP_SEQUENCE.index(step)
    for prior_step in STEP_SEQUENCE[:step_idx]:
        prior_status = _get_status(state, prior_step)
        if prior_status == StepStatus.PENDING:
            return False, (
                f"Step {prior_step.value} is still PENDING. "
                f"All prior steps must be resolved before advancing to {step.value}"
            )

    # Check gate conditions
    if step in GATE_CONDITIONS:
        for prereq in GATE_CONDITIONS[step]:
            prereq_status = _get_status(state, prereq)
            if prereq_status not in (StepStatus.PASSED, StepStatus.SKIPPED):
                return False, (
                    f"Gate condition not met: {prereq.value} must be PASSED or SKIPPED "
                    f"before advancing to {step.value} "
                    f"(current: {prereq_status.value})"
                )

    return True, ""


def advance(
    state: PipelineState,
    step: Step,
    *,
    status: StepStatus = StepStatus.RUNNING,
    error: Optional[str] = None,
) -> PipelineState:
    """Advance a step to a new status (default: RUNNING).

    Args:
        state: Current pipeline state.
        step: The step to advance.
        status: Target status (default RUNNING).
        error: Optional error message.

    Returns:
        Updated PipelineState.

    Raises:
        ValueError: If the step cannot be advanced (already PASSED).
    """
    current_status = _get_status(state, step)
    if current_status == StepStatus.PASSED:
        raise ValueError(
            f"Step {step.value} is already PASSED and cannot be re-entered"
        )

    now = _now()
    record = state.steps.get(step.value)
    if record is None:
        record = _make_step_dict()
        state.steps[step.value] = record

    record["status"] = status.value
    if status == StepStatus.RUNNING and record.get("started_at") is None:
        record["started_at"] = now
    if error is not None:
        record["error"] = error
    if status in (StepStatus.PASSED, StepStatus.FAILED, StepStatus.SKIPPED):
        record["completed_at"] = now

    state.updated_at = now
    save_pipeline(state)
    return state


def complete_step(
    state: PipelineState,
    step: Step,
    *,
    passed: bool = True,
    error: Optional[str] = None,
) -> PipelineState:
    """Convenience function to mark a step as PASSED or FAILED.

    Args:
        state: Current pipeline state.
        step: The step to complete.
        passed: True for PASSED, False for FAILED.
        error: Optional error message (typically set when passed=False).

    Returns:
        Updated PipelineState.
    """
    target_status = StepStatus.PASSED if passed else StepStatus.FAILED
    return advance(state, step, status=target_status, error=error)


def skip_step(
    state: PipelineState,
    step: Step,
    *,
    reason: str,
) -> PipelineState:
    """Skip a step (only allowed for SKIPPABLE_STEPS).

    Args:
        state: Current pipeline state.
        step: The step to skip.
        reason: Why this step is being skipped.

    Returns:
        Updated PipelineState.

    Raises:
        ValueError: If the step is not in SKIPPABLE_STEPS.
    """
    if step not in SKIPPABLE_STEPS:
        raise ValueError(
            f"Step {step.value} is not skippable. "
            f"Only these steps can be skipped: {[s.value for s in SKIPPABLE_STEPS]}"
        )
    return advance(state, step, status=StepStatus.SKIPPED, error=reason)


def get_trace(state: PipelineState) -> List[Dict[str, Any]]:
    """Get an ordered list of step records with timing information.

    Only includes steps that have been started (not PENDING).

    Args:
        state: Current pipeline state.

    Returns:
        List of dicts with step name, status, timestamps, and duration_s.
    """
    trace = []
    for step in STEP_SEQUENCE:
        record = state.steps.get(step.value)
        if record is None or record.get("status") == StepStatus.PENDING.value:
            continue

        entry: Dict[str, Any] = {
            "step": step.value,
            "status": record["status"],
            "started_at": record.get("started_at"),
            "completed_at": record.get("completed_at"),
            "error": record.get("error"),
            "duration_s": None,
        }

        # Calculate duration if both timestamps exist
        started = record.get("started_at")
        completed = record.get("completed_at")
        if started and completed:
            try:
                start_dt = datetime.fromisoformat(started)
                end_dt = datetime.fromisoformat(completed)
                entry["duration_s"] = round((end_dt - start_dt).total_seconds(), 3)
            except (ValueError, TypeError):
                pass

        trace.append(entry)

    return trace


def cleanup_pipeline(run_id: str) -> None:
    """Remove the pipeline state file from disk.

    Args:
        run_id: The pipeline run identifier.

    Does not raise if the file doesn't exist.
    """
    path = get_state_path(run_id)
    try:
        path.unlink()
    except FileNotFoundError:
        pass
