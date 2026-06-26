"""Pipeline state machine for /implement command.

Tracks pipeline step progression, enforces gate conditions, and persists
state to JSON. Zero external dependencies (stdlib only).

Usage:
    state = create_pipeline("run-001", "Add user auth")
    state = advance(state, Step.ALIGNMENT)
    state = complete_step(state, Step.ALIGNMENT, passed=True)
    trace = get_trace(state)
"""

import fcntl
import hashlib
import hmac as _hmac
import json
import os
import re as _re
import secrets
import tempfile
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

try:
    # Normal package-style import (preferred when invoked from production code).
    from .path_utils import find_project_root  # type: ignore
except ImportError:  # pragma: no cover - fallback for scripts that load module by path
    try:
        from path_utils import find_project_root  # type: ignore
    except ImportError:
        # Last-resort no-op fallback: callers will hit the cwd-based fallback below.
        def find_project_root(*_args: Any, **_kwargs: Any) -> Path:  # type: ignore
            raise FileNotFoundError("path_utils.find_project_root unavailable")


# =============================================================================
# CONSTANTS
# =============================================================================

# Legacy sentinel file name (Issue #1206). The full path is now per-repo:
# <repo_root>/.claude/local/implement_pipeline_state.json. Resolve via
# get_legacy_sentinel_path() — DO NOT hardcode the old /tmp/... literal.
#
# The sentinel is touched on every hook invocation during active pipeline runs,
# making its mtime a reliable indicator of recent pipeline activity. It is
# distinct from the HMAC-signed per-run state file created by
# get_state_path(run_id) at /tmp/pipeline_state_{run_id}.json.
#
# Used by verify_state_hmac() for stale-state fail-open detection (Issue #753):
# if this sentinel's mtime is >1 hour old, the pipeline is considered stale and
# HMAC verification fails open to avoid blocking subsequent sessions.
#
# Cross-reference: unified_pre_tool.py PIPELINE_STATE_FILE env var,
#                  pre_compact_batch_saver.sh, implement-fix.md.
#
# Issue #1206: relocated from machine-global /tmp/implement_pipeline_state.json
# to per-repo path so concurrent /implement sessions in different repos no
# longer clobber each other's sentinels.
LEGACY_SENTINEL_FILENAME: str = "implement_pipeline_state.json"


def get_legacy_sentinel_path(repo_root: Optional[Path] = None) -> Path:
    """Resolve the per-repo legacy sentinel file path.

    Returns ``<repo_root>/.claude/local/implement_pipeline_state.json`` where
    ``repo_root`` is determined by (in order):

    1. The explicit ``repo_root`` argument if provided.
    2. :func:`path_utils.find_project_root` (walks for ``.git`` or ``.claude``).
    3. ``Path.cwd().resolve()`` if no marker file is found.

    The parent directory is created with mode 0o700 if missing. The created
    directory is owner-only because it can contain run-scoped state with
    HMAC-signed content.

    Args:
        repo_root: Optional explicit repo root. When provided, the marker-file
            walk is skipped and the path is computed directly under this root.

    Returns:
        The fully-qualified sentinel path. The file itself MAY or MAY NOT
        exist; only the parent directory is created.

    Issue #1206: per-repo isolation eliminates cross-repo collisions on the
    machine-global ``/tmp/implement_pipeline_state.json`` location.
    """
    if repo_root is not None:
        root = Path(repo_root).resolve()
    else:
        try:
            root = find_project_root()
        except FileNotFoundError:
            root = Path.cwd().resolve()

    sentinel_dir = root / ".claude" / "local"
    try:
        sentinel_dir.mkdir(parents=True, exist_ok=True, mode=0o700)
        # mkdir() honors mode only when creating; force 0o700 on existing dirs too.
        try:
            sentinel_dir.chmod(0o700)
        except OSError:
            # Best effort; caller will still get a usable path.
            pass
    except OSError:
        # Best effort: parent dir creation may fail (read-only FS, permissions);
        # callers using the path for read operations still get a valid object.
        pass

    return sentinel_dir / LEGACY_SENTINEL_FILENAME


def atomic_write_json(
    path: Path,
    data: dict,
    *,
    indent: Optional[int] = None,
) -> None:
    """Atomically write a JSON dict to ``path`` using a temp file + rename.

    Uses ``tempfile.mkstemp`` in the destination's parent directory so the
    rename is on the same filesystem (atomic on POSIX). The temp file is
    chmod'd to 0o600 BEFORE the rename so the destination inherits restrictive
    permissions even if the directory has a permissive umask.

    On exception, the temp file is unlinked and the exception re-raised so the
    caller can decide how to handle persistence failure.

    Args:
        path: Destination file path. Parent directory MUST exist.
        data: JSON-serialisable dict.
        indent: Optional JSON pretty-print indent (passed through to
            ``json.dump``). ``None`` produces the most compact form.

    Raises:
        OSError: From ``tempfile.mkstemp``, ``os.replace``, or ``os.chmod``.
        TypeError: If ``data`` is not JSON-serialisable.
    """
    parent = path.parent
    fd, tmp = tempfile.mkstemp(
        dir=str(parent), suffix=".tmp", prefix=f".{path.name}_"
    )
    try:
        with os.fdopen(fd, "w") as f:
            json.dump(data, f, indent=indent)
        try:
            os.chmod(tmp, 0o600)
        except OSError:
            # Non-fatal: permission tightening is best-effort on platforms
            # like Windows or FUSE mounts that ignore chmod.
            pass
        os.replace(tmp, str(path))
    except Exception:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


# Backward-compat alias — external callers that imported the private name continue to work.
_atomic_write_json = atomic_write_json


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
    redispatch_agents: Dict[str, bool] = field(default_factory=dict)

    remediation_occurred: bool = False  # Issue #1271: Track if STEP 11 remediation was triggered

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




def _get_pipeline_secret_path(run_id: str) -> Path:
    """Return the filesystem path for a pipeline secret key file.

    The secret is stored separately from the state file so an attacker who
    controls the state file cannot forge the HMAC without also accessing the
    secret file (which has restricted permissions).

    Args:
        run_id: The pipeline run identifier.

    Returns:
        Path to the secret key file (~/.claude/pipeline_secrets/<run_id>.key).
    """
    import re as _re

    secrets_dir = Path.home() / ".claude" / "pipeline_secrets"
    safe_id = _re.sub(r"[^a-zA-Z0-9_-]", "_", run_id)[:128] if run_id else "unknown"
    return secrets_dir / f"{safe_id}.key"


def _get_or_create_pipeline_secret(run_id: str) -> str:
    """Get existing pipeline secret or create a new one.

    Creates the secret file with 0o600 permissions. The secret is a 32-byte
    hex string that is NOT stored in the pipeline state file.

    Args:
        run_id: The pipeline run identifier.

    Returns:
        The hex-encoded secret string.
    """
    import os as _os

    secret_path = _get_pipeline_secret_path(run_id)
    if secret_path.exists():
        return secret_path.read_text().strip()

    secret = secrets.token_hex(32)
    secret_path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    fd = _os.open(str(secret_path), _os.O_WRONLY | _os.O_CREAT | _os.O_TRUNC, 0o600)
    try:
        _os.write(fd, secret.encode("utf-8"))
    finally:
        _os.close(fd)
    return secret


def _read_pipeline_secret(run_id: str) -> "Optional[str]":
    """Read a pipeline secret from the secrets directory.

    Args:
        run_id: The pipeline run identifier.

    Returns:
        The secret string, or None if the secret file does not exist.
    """
    secret_path = _get_pipeline_secret_path(run_id)
    if not secret_path.exists():
        return None
    try:
        return secret_path.read_text().strip()
    except OSError:
        return None


def cleanup_pipeline_secret(run_id: str) -> None:
    """Remove the pipeline secret file from disk.

    Args:
        run_id: The pipeline run identifier.

    Does not raise if the file does not exist.
    """
    secret_path = _get_pipeline_secret_path(run_id)
    try:
        secret_path.unlink()
    except FileNotFoundError:
        pass


def _compute_state_hmac(state: dict, secret: str) -> str:
    """Compute HMAC-SHA256 over critical pipeline state fields.

    Uses an external secret (NOT stored in the state file) as the HMAC key,
    combined with the nonce. This prevents forgery even if an attacker
    controls the state file contents.

    Args:
        state: Pipeline state dict (must contain 'nonce' key).
        secret: The pipeline secret from a separate restricted-permission file.

    Returns:
        Hex-encoded HMAC-SHA256 digest.
    """
    nonce = state.get("nonce", "")
    key = (secret + nonce).encode("utf-8")
    # Deterministic message from critical fields
    parts = [
        state.get("session_start", ""),
        state.get("mode", ""),
        state.get("run_id", ""),
        str(state.get("explicitly_invoked", False)),
        str(state.get("alignment_passed", False)),
        nonce,
    ]
    message = "|".join(parts).encode("utf-8")
    return _hmac.new(key, message, hashlib.sha256).hexdigest()


def verify_state_hmac(state: dict, session_id: str) -> bool:
    """Verify the HMAC on a pipeline state dict.

    Reads the secret from a separate pipeline secrets file. The session_id
    parameter is kept for API compatibility but the actual HMAC key is derived
    from the secret file.

    When the secret file has been cleaned up between sessions (common in
    batch/worktree workflows after /clear), stale states older than 1 hour
    are treated as expired rather than tampered to avoid generating repeated
    HMAC failures (Issue #753).

    Args:
        state: Pipeline state dict with 'hmac' and 'nonce' fields.
        session_id: Session identifier (fallback if secret file missing).

    Returns:
        True if the HMAC is valid, False if tampered or missing nonce.
        Returns True if there is no 'hmac' field (backward compatibility).
    """
    stored_hmac = state.get("hmac")
    if stored_hmac is None:
        # Backward compatibility: old state files without HMAC are accepted
        return True
    if not state.get("nonce"):
        # HMAC present but no nonce means tampering
        return False

    run_id = state.get("run_id", "")
    secret = _read_pipeline_secret(run_id) if run_id else None

    if secret is not None:
        expected = _compute_state_hmac(state, secret)
        if _hmac.compare_digest(stored_hmac, expected):
            return True

    # Session-id fallback for backward compat with states signed before
    # the secret-file approach was introduced
    fallback_key = session_id
    expected = _compute_state_hmac(state, fallback_key)
    if _hmac.compare_digest(stored_hmac, expected):
        return True

    # Stale state fail-open (Issue #753): checks the LEGACY SENTINEL file
    # (<repo>/.claude/local/implement_pipeline_state.json — was
    # /tmp/implement_pipeline_state.json before Issue #1206), NOT the HMAC-
    # signed per-run state file (/tmp/pipeline_state_{run_id}.json). The legacy
    # sentinel is touched on every hook invocation during active pipeline runs
    # (see unified_pre_tool.py PIPELINE_STATE_FILE env var). Its mtime is used
    # as a proxy for "was the pipeline recently active?" — if >1 hour old, the
    # pipeline is considered stale and HMAC verification fails open. This
    # coupling is intentional: the sentinel mtime cannot be forged by editing
    # JSON content (unlike session_start in the state dict).
    # Cross-reference: get_legacy_sentinel_path() (this module).
    import time as _time

    state_path = get_legacy_sentinel_path()
    if state_path.exists():
        try:
            mtime = state_path.stat().st_mtime
            age_seconds = _time.time() - mtime
            if age_seconds > 3600:  # > 1 hour old
                return True  # fail-open for stale state files
        except OSError:
            pass

    return False


def sign_state(state: dict, session_id: str) -> dict:
    """Add HMAC signature and nonce to a pipeline state dict.

    Generates a per-run secret stored in a separate file with restricted
    permissions. The HMAC key is derived from this secret, not from
    session_id (which may be absent or guessable).

    Args:
        state: Pipeline state dict to sign.
        session_id: Session identifier (kept for API compat; not used as key).

    Returns:
        The same dict with 'nonce' and 'hmac' fields set.
    """
    if not state.get("nonce"):
        state["nonce"] = secrets.token_hex(16)

    run_id = state.get("run_id", "unknown")
    secret = _get_or_create_pipeline_secret(run_id)
    state["hmac"] = _compute_state_hmac(state, secret)
    return state


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
            redispatch_agents=data.get("redispatch_agents", {}),
            remediation_occurred=data.get("remediation_occurred", False),  # Issue #1271: Default False for old state files
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
        "redispatch_agents": state.redispatch_agents,
        "remediation_occurred": state.remediation_occurred,  # Issue #1271
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


def get_completion_summary(state: PipelineState) -> Dict[str, Any]:
    """Build a completion summary from pipeline state.

    Extracts agent count, step count, mode, overall status, and timing.

    Args:
        state: The completed pipeline state.

    Returns:
        Dict with keys: agent_count, step_count, mode, status, started_at,
        completed_at, duration_s.
    """
    trace = get_trace(state)
    step_count = len(trace)

    # Count distinct agents from step names that map to agents
    agent_step_names = {
        "alignment", "research_cache", "research", "plan",
        "acceptance_tests", "tdd_tests", "implement",
        "validate", "verify", "report",
    }
    agent_count = sum(
        1 for entry in trace
        if entry.get("step") in agent_step_names
        and entry.get("status") in ("passed", "skipped")
    )

    # Determine overall status
    statuses = [entry.get("status", "pending") for entry in trace]
    if any(s == "failed" for s in statuses):
        overall_status = "failed"
    elif all(s in ("passed", "skipped") for s in statuses) and statuses:
        overall_status = "completed"
    else:
        overall_status = "partial"

    # Timing
    started_at = state.created_at
    completed_at = state.updated_at
    duration_s = None  # type: Optional[float]
    if started_at and completed_at:
        try:
            start_dt = datetime.fromisoformat(started_at)
            end_dt = datetime.fromisoformat(completed_at)
            duration_s = round((end_dt - start_dt).total_seconds(), 3)
        except (ValueError, TypeError):
            pass

    return {
        "agent_count": agent_count,
        "step_count": step_count,
        "mode": state.mode,
        "status": overall_status,
        "started_at": started_at,
        "completed_at": completed_at,
        "duration_s": duration_s,
    }


def finalize_to_session(
    run_id: str,
    *,
    feature_ref: Optional[str] = None,
    batch_id: Optional[str] = None,
) -> bool:
    """Merge pipeline state into session record for post-analysis.

    Loads pipeline state from /tmp/pipeline_state_{run_id}.json, reads the
    session record from docs/sessions/{run_id}-pipeline.json (if it exists),
    merges completion data, and writes back atomically.

    In batch mode (feature_ref is provided), each feature's pipeline data is
    appended to a ``features`` list in the session record, enabling per-feature
    analysis.  Flat ``pipeline_summary`` / ``pipeline_steps`` fields are still
    written for backward compatibility (last-feature-wins).

    Args:
        run_id: The pipeline run identifier.
        feature_ref: Optional feature reference for batch mode (e.g. issue
            number or feature slug).  When provided, the session record uses
            schema_version "2.0" with a ``features`` list.
        batch_id: Optional batch identifier to tag the session record.

    Returns:
        True if finalization succeeded, False otherwise.
    """
    import os
    import tempfile

    # Load pipeline state
    state = load_pipeline(run_id)
    if state is None:
        return False

    # Build completion summary
    summary = get_completion_summary(state)

    # Find session record path
    session_dir = Path(os.getcwd()) / "docs" / "sessions"
    session_file = session_dir / f"{run_id}-pipeline.json"

    # Load existing session record or create new one
    session_data = {}  # type: Dict[str, Any]
    if session_file.exists():
        try:
            session_data = json.loads(session_file.read_text())
        except (json.JSONDecodeError, OSError):
            session_data = {}

    # Merge pipeline data into session record (flat fields for v1 compat)
    session_data["pipeline_summary"] = summary
    session_data["pipeline_steps"] = state.steps
    session_data["run_id"] = run_id
    session_data["mode"] = state.mode
    session_data["feature"] = state.feature

    if feature_ref is not None:
        # Batch mode: append to features list (schema v2.0)
        session_data["schema_version"] = "2.0"
        if batch_id is not None:
            session_data["batch_id"] = batch_id

        features = session_data.setdefault("features", [])

        # Idempotency: skip if feature_ref already recorded
        existing_refs = {f.get("feature_ref") for f in features}
        if feature_ref not in existing_refs:
            features.append({
                "feature_ref": feature_ref,
                "pipeline_summary": summary,
                "pipeline_steps": state.steps,
                "feature": state.feature,
            })
    else:
        # Single-feature mode: set v1.0 schema (default)
        session_data.setdefault("schema_version", "1.0")

    # Write atomically (temp file + os.replace)
    try:
        session_dir.mkdir(parents=True, exist_ok=True)
    except OSError:
        return False
    try:
        atomic_write_json(session_file, session_data, indent=2)
    except Exception:
        return False

    return True


def cleanup_pipeline(run_id: str) -> None:
    """Remove the pipeline state file and its secret from disk.

    Args:
        run_id: The pipeline run identifier.

    Does not raise if the files don't exist.
    """
    path = get_state_path(run_id)
    try:
        path.unlink()
    except FileNotFoundError:
        pass
    # Also clean up the associated secret file
    cleanup_pipeline_secret(run_id)



def set_remediation_flag(run_id: str) -> bool:
    """Set the remediation_occurred flag to True in the pipeline state.
    
    Issue #1271: This is called by the coordinator at STEP 11 when remediation
    is triggered (implementer re-invoked in REMEDIATION MODE).
    
    Args:
        run_id: The pipeline run identifier.
        
    Returns:
        True if the flag was successfully set, False otherwise.
    """
    state = load_pipeline(run_id)
    if state is None:
        return False
    
    state.remediation_occurred = True
    try:
        save_pipeline(state)
        return True
    except Exception:
        return False


def get_remediation_flag(run_id: str) -> bool:
    """Get the remediation_occurred flag from the pipeline state.
    
    Issue #1271: This is called by the coordinator at STEP 12 to determine
    whether doc-master needs to be re-invoked due to STEP 11 remediation.
    
    Args:
        run_id: The pipeline run identifier.
        
    Returns:
        True if remediation occurred, False otherwise (including if state not found).
    """
    state = load_pipeline(run_id)
    if state is None:
        return False
    
    return state.remediation_occurred

# =============================================================================
# BASE COMMIT ANCHORING (Issue #1069)
# =============================================================================
#
# Pre-existing working-tree modifications cause `git diff --name-only HEAD` to
# include files unrelated to the current pipeline run. When the coordinator
# emits acceptance criteria that reference "files in the diff", spec-validator
# correctly verifies the criterion and FAILs on pre-existing tree state —
# producing a false-positive that requires human override.
#
# The fix anchors diff commands to the commit SHA captured at pipeline start
# (PIPELINE_BASE_COMMIT). This restricts the diff to files actually changed by
# the current run, ignoring any tree state that existed before the pipeline
# began. The base commit is stored in the legacy sentinel state file
# (PIPELINE_STATE_FILE, default <repo>/.claude/local/implement_pipeline_state.json
# — was /tmp/implement_pipeline_state.json before Issue #1206) under the
# 'base_commit' key.


def set_pipeline_base_commit(
    base_commit: str,
    *,
    state_path: Optional[str] = None,
) -> bool:
    """Record PIPELINE_BASE_COMMIT in the pipeline state file.

    Called at pipeline start (full-pipeline STEP 1 or fix-mode STEP F1) to
    capture the git HEAD before any pipeline-driven file modifications. The
    captured SHA is later used by spec-validator (STEP 8.5 / STEP F3.5) to
    anchor `git diff --name-only` commands so the diff reflects only files
    changed by the current pipeline run, not pre-existing tree state.

    Args:
        base_commit: The git commit SHA captured via `git rev-parse HEAD`.
            Empty string is permitted (e.g., no-commit repository) but
            disables anchoring — callers should fall back to plain HEAD diff
            in that case.
        state_path: Optional override for the state file path. Defaults to
            the PIPELINE_STATE_FILE env var, falling back to the per-repo
            <repo>/.claude/local/implement_pipeline_state.json (Issue #1206).

    Returns:
        True if the base commit was successfully written, False if the state
        file does not exist or could not be read/written.
    """
    path = state_path or os.environ.get(
        "PIPELINE_STATE_FILE", str(get_legacy_sentinel_path())
    )
    if not os.path.exists(path):
        return False
    try:
        with open(path) as f:
            state = json.load(f)
    except (OSError, json.JSONDecodeError):
        return False
    state["base_commit"] = base_commit
    try:
        atomic_write_json(Path(path), state)
    except OSError:
        return False
    return True


def get_pipeline_base_commit(
    state_path: Optional[str] = None,
) -> Optional[str]:
    """Read PIPELINE_BASE_COMMIT from the pipeline state file.

    Returns the commit SHA captured at pipeline start, or None if not set.
    Callers SHOULD fall back to plain `HEAD` when the base commit is missing
    (e.g., legacy pipelines, fresh state files, no-commit repos).

    Args:
        state_path: Optional override for the state file path. Defaults to
            the PIPELINE_STATE_FILE env var, falling back to the per-repo
            <repo>/.claude/local/implement_pipeline_state.json (Issue #1206).

    Returns:
        The base commit SHA string if recorded and non-empty, otherwise None.
    """
    path = state_path or os.environ.get(
        "PIPELINE_STATE_FILE", str(get_legacy_sentinel_path())
    )
    if not os.path.exists(path):
        return None
    try:
        with open(path) as f:
            state = json.load(f)
    except (OSError, json.JSONDecodeError):
        return None
    base = state.get("base_commit")
    if not isinstance(base, str) or not base.strip():
        return None
    return base.strip()


# =============================================================================
# BASELINE SCOPE HELPERS (Issue #990)
# =============================================================================
#
# In the #972 run, the coordinator's STEP 5 test gate initially reported 188
# "new failures" that were pre-existing failures in test directories outside
# the baseline scope. The mismatch arose because the coordinator captured a
# baseline test count using one directory set (e.g., `tests/unit/ tests/integration/`)
# but the implementer ran tests against a broader set (e.g., adding
# `tests/regression/ tests/property/`). Directories never in the baseline
# appeared as regressions.
#
# The fix: normalize test scope at STEP 1 by recording the exact pytest
# invocation used for baseline capture in the sentinel. The implementer
# MUST use this recorded scope — not a self-chosen broader one — when
# running pytest at STEP 8.

#: The canonical baseline pytest command — stored as a list for shell-injection
#: safety (never joined into a shell string). Callers that need a string form
#: must join explicitly: ``" ".join(CANONICAL_BASELINE_CMD)``.
CANONICAL_BASELINE_CMD: List[str] = [
    "pytest",
    "tests/unit",
    "tests/integration",
    "-q",
    "--tb=no",
]


def record_baseline_scope(
    state_path: str,
    baseline_cmd: List[str],
    baseline_count: int,
) -> bool:
    """Persist baseline test scope into the pipeline sentinel JSON.

    Reads the existing sentinel at ``state_path``, merges ``baseline_cmd``
    and ``baseline_count`` under those exact key names, and writes back
    atomically (temp-file + os.replace). Overwrites any existing
    ``baseline_cmd``/``baseline_count`` keys — re-baselining within a
    session is intentional.

    ``baseline_cmd`` is stored as a list (not a shell string) to eliminate
    shell-injection ambiguity when it is later read back and passed directly
    to ``subprocess.run``.

    Args:
        state_path: Absolute path to the pipeline sentinel JSON file.
        baseline_cmd: The exact pytest invocation used for baseline capture,
            as a list of strings (e.g., ``["pytest", "tests/unit", "-q",
            "--tb=no"]``).
        baseline_count: The total number of tests found by the baseline run.

    Returns:
        True on success, False on any IO or JSON error. NEVER raises.
    """
    if not os.path.exists(state_path):
        return False
    try:
        with open(state_path) as f:
            state = json.load(f)
    except (OSError, json.JSONDecodeError):
        return False

    state["baseline_cmd"] = list(baseline_cmd)
    state["baseline_count"] = int(baseline_count)

    try:
        atomic_write_json(Path(state_path), state)
    except (OSError, json.JSONDecodeError):
        return False
    return True


def get_baseline_scope(state_path: str) -> Optional[Dict[str, Any]]:
    """Return the recorded baseline test scope from the pipeline sentinel.

    Returns a dict with keys ``baseline_cmd`` (list of str) and
    ``baseline_count`` (int), or ``None`` if either field is missing or
    malformed (wrong type, empty list, non-integer count). NEVER raises.

    Args:
        state_path: Absolute path to the pipeline sentinel JSON file.

    Returns:
        ``{"baseline_cmd": [...], "baseline_count": N}`` if both fields are
        present and well-formed; ``None`` otherwise.
    """
    if not os.path.exists(state_path):
        return None
    try:
        with open(state_path) as f:
            state = json.load(f)
    except (OSError, json.JSONDecodeError):
        return None

    cmd = state.get("baseline_cmd")
    count = state.get("baseline_count")

    if not isinstance(cmd, list) or len(cmd) == 0:
        return None
    if not all(isinstance(item, str) for item in cmd):
        return None
    if not isinstance(count, int):
        return None

    return {"baseline_cmd": cmd, "baseline_count": count}


# =============================================================================
# RUN_ID GENERATION AND LOCKFILE HELPERS (Issue #1047)
# =============================================================================

# Resume classification regexes — order matters (batch first, then hex, then legacy)
_BATCH_ID_RE = _re.compile(r"^batch-")
_RUN_ID_HEX_RE = _re.compile(r"^[a-f0-9]{16}$")
_RUN_ID_LEGACY_TIMESTAMP_RE = _re.compile(r"^\d{8}-\d{6}$")  # YYYYMMDD-HHMMSS back-compat


def generate_run_id() -> str:
    """Generate a 16-char hex run_id via secrets.token_hex(8).

    The format matches ``_RUN_ID_HEX_RE`` (16 lowercase hex characters) and
    is also accepted by the ``_RUN_ID_RE`` validator in
    ``pipeline_completion_state``.

    Returns:
        16-character lowercase hex string (e.g., ``'a3f1b2c4d5e67890'``).
    """
    return secrets.token_hex(8)


def get_lockfile_path(run_id: str) -> Path:
    """Return the lockfile path for the given run_id.

    Args:
        run_id: The pipeline run identifier.

    Returns:
        Path to ``/tmp/pipeline_<run_id>.lock``.
    """
    return Path(f"/tmp/pipeline_{run_id}.lock")


def acquire_run_lock(run_id: str) -> Optional[int]:
    """Acquire exclusive non-blocking lock on /tmp/pipeline_<run_id>.lock.

    Uses ``fcntl.flock(LOCK_EX | LOCK_NB)``.  The OS releases the lock
    automatically when the process exits, even on a crash.  The caller must
    hold the returned file descriptor open for the entire duration of the
    pipeline run; closing it releases the lock.

    Args:
        run_id: The pipeline run identifier used to derive the lock path.

    Returns:
        An open file descriptor (int) on success; ``None`` if the lock is
        already held by another process or thread.
    """
    lock_path = get_lockfile_path(run_id)
    fd = os.open(str(lock_path), os.O_CREAT | os.O_WRONLY, 0o600)
    try:
        fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        return fd
    except (BlockingIOError, OSError):
        os.close(fd)
        return None


def release_run_lock(fd: int) -> None:
    """Release the run lock by unlocking and closing the file descriptor.

    Idempotent — calling on an already-released descriptor does not raise.

    Args:
        fd: The file descriptor returned by ``acquire_run_lock``.
    """
    try:
        fcntl.flock(fd, fcntl.LOCK_UN)
    except OSError:
        pass
    try:
        os.close(fd)
    except OSError:
        pass


def classify_resume_id(arg: str) -> str:
    """Classify a ``--resume <id>`` argument by format.

    Classification order (first match wins):

    1. ``batch``        — ``arg`` starts with ``'batch-'``
    2. ``run_id``       — ``arg`` is exactly 16 lowercase hex characters
    3. ``run_id_legacy``— ``arg`` matches ``YYYYMMDD-HHMMSS`` (back-compat)
    4. ``invalid``      — no pattern matched

    Args:
        arg: The raw ``--resume`` argument value.

    Returns:
        One of ``"batch"``, ``"run_id"``, ``"run_id_legacy"``, or
        ``"invalid"``.
    """
    if not arg:
        return "invalid"
    if _BATCH_ID_RE.match(arg):
        return "batch"
    if _RUN_ID_HEX_RE.match(arg):
        return "run_id"
    if _RUN_ID_LEGACY_TIMESTAMP_RE.match(arg):
        return "run_id_legacy"
    return "invalid"
