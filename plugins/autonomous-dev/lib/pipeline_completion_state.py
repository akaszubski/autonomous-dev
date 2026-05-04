#!/usr/bin/env python3
"""
Pipeline Completion State - Shared state for agent ordering enforcement.

Manages a per-session JSON state file that tracks which pipeline agents
have completed. Written by unified_session_tracker.py (SubagentStop),
read by unified_pre_tool.py (PreToolUse) to enforce ordering.

State file path: /tmp/pipeline_agent_completions_{hash(session_id)[:8]}.json

Issues: #625, #629, #632
"""

import fcntl
import hashlib
import json
import os
import time
from pathlib import Path
from typing import Optional

# File-based bypass for the agent completeness gate.
# The env var SKIP_AGENT_COMPLETENESS_GATE=1 is unreachable from Bash commands
# because the hook runs in a separate process spawned by the harness.
# This file provides a one-shot bypass: touch the file, it's consumed on first check.
# Issue #802
SKIP_GATE_FILE = Path("/tmp/skip_agent_completeness_gate")

# Staleness TTL for the 'unknown' session-id fallback merge.
# When the primary-session lookup in get_completed_agents() falls back to
# reading the 'unknown' state file (for the Issue #738/#777 in-flight boot
# case where the coordinator initialized state before CLAUDE_SESSION_ID was
# known), the merge ONLY applies if the 'unknown' state file's mtime is
# within this window. Older 'unknown' state from crashed/stale prior runs
# must not contaminate a fresh pipeline. Issue #875 / Issue #904.
STALE_UNKNOWN_TTL_SECONDS = 3600


def _check_file_bypass() -> bool:
    """Check and consume the file-based bypass for the agent completeness gate.

    If the bypass file exists, delete it (one-shot consumption) and return True.
    Fail-open on deletion errors to avoid blocking commits.

    Returns:
        True if bypass file was found (and consumed), False otherwise.

    Issues: #802
    """
    try:
        if SKIP_GATE_FILE.exists():
            try:
                SKIP_GATE_FILE.unlink()
            except OSError:
                pass  # Fail-open: bypass even if unlink fails
            return True
    except OSError:
        pass  # Fail-open on existence check errors
    return False


def _state_file_path(session_id: str) -> Path:
    """Compute the state file path for a given session.

    Args:
        session_id: The pipeline session identifier.

    Returns:
        Path to the state file in /tmp.
    """
    h = hashlib.sha256(session_id.encode()).hexdigest()[:8]
    return Path(f"/tmp/pipeline_agent_completions_{h}.json")


def _read_state(session_id: str) -> dict:
    """Read state file with file locking. Returns empty dict on any failure.

    Args:
        session_id: The pipeline session identifier.

    Returns:
        Parsed state dict, or empty dict if file missing/corrupt/stale.
    """
    path = _state_file_path(session_id)
    if not path.exists():
        return {}

    # Stale check: ignore files older than 2 hours
    try:
        mtime = path.stat().st_mtime
        if time.time() - mtime > 7200:
            return {}
    except OSError:
        return {}

    try:
        with open(path, "r") as f:
            fcntl.flock(f.fileno(), fcntl.LOCK_SH)
            try:
                data = json.load(f)
            finally:
                fcntl.flock(f.fileno(), fcntl.LOCK_UN)
        if not isinstance(data, dict):
            return {}
        return data
    except (json.JSONDecodeError, OSError, ValueError):
        return {}


def _write_state(session_id: str, state: dict) -> None:
    """Write state file atomically with file locking.

    Args:
        session_id: The pipeline session identifier.
        state: The state dict to write.
    """
    path = _state_file_path(session_id)
    try:
        with open(path, "w") as f:
            fcntl.flock(f.fileno(), fcntl.LOCK_EX)
            try:
                json.dump(state, f, indent=2)
            finally:
                fcntl.flock(f.fileno(), fcntl.LOCK_UN)
    except OSError:
        pass  # Non-blocking: state write failure is not fatal


def _ensure_state(session_id: str) -> dict:
    """Read existing state or create a new skeleton.

    Args:
        session_id: The pipeline session identifier.

    Returns:
        A valid state dict (may be freshly created).
    """
    state = _read_state(session_id)
    if not state:
        from datetime import datetime, timezone

        state = {
            "session_id": session_id,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "validation_mode": "sequential",
            "completions": {},
            "prompt_baselines": {},
        }
    return state


def record_agent_completion(
    session_id: str,
    agent_type: str,
    *,
    issue_number: int = 0,
    success: bool = True,
    is_remediation: bool = False,
) -> None:
    """Record that an agent has completed for a given session and issue.

    Args:
        session_id: The pipeline session identifier.
        agent_type: The agent type (e.g., "researcher-local", "planner").
        issue_number: The issue number (0 for non-batch).
        success: Whether the agent completed successfully.
        is_remediation: When True, this completion is part of a remediation
            pass (e.g., reviewer re-run after BLOCKING findings). The stored
            entry is marked so the intent validator can skip duplicate-agent
            ordering findings for remediation events. Issue #902 / Issue #904.

    Notes:
        Backwards compatible: existing callers that do not pass
        ``is_remediation`` continue to work — the stored value is the plain
        boolean ``success`` (legacy shape). When ``is_remediation=True`` is
        passed, the stored value becomes a dict ``{"success": <bool>,
        "remediation": True}``. All readers in this module tolerate both
        shapes (see ``_completion_is_success``).
    """
    state = _ensure_state(session_id)
    completions = state.setdefault("completions", {})
    issue_key = str(issue_number)
    issue_completions = completions.setdefault(issue_key, {})
    if is_remediation:
        # Store as dict so the remediation flag persists alongside success.
        issue_completions[agent_type] = {
            "success": bool(success),
            "remediation": True,
        }
    else:
        # Preserve legacy plain-bool shape for backwards compatibility.
        issue_completions[agent_type] = success
    _write_state(session_id, state)


def _completion_is_success(entry) -> bool:
    """Interpret a stored completion entry as a success boolean.

    Completion entries may be stored as:
      - ``bool`` (legacy shape — ``True`` means success).
      - ``dict`` with a ``"success"`` key (Issue #902 / #904 remediation shape).

    Any other type is treated as non-success (fail-safe).

    Args:
        entry: Value read from ``completions[issue_key][agent_type]``.

    Returns:
        True when the entry represents a successful completion.
    """
    if isinstance(entry, bool):
        return entry
    if isinstance(entry, dict):
        return bool(entry.get("success", False))
    return False


def is_remediation_completion(
    session_id: str,
    agent_type: str,
    *,
    issue_number: int = 0,
) -> bool:
    """Check whether a recorded completion was flagged as remediation.

    Reads both the primary session state and the 'unknown' fallback state
    (respecting the TTL in ``STALE_UNKNOWN_TTL_SECONDS``) so the result is
    consistent with ``get_completed_agents``. Returns False when no matching
    completion exists or the recorded entry has no remediation flag.

    Args:
        session_id: The pipeline session identifier.
        agent_type: The agent type (e.g., "reviewer").
        issue_number: The issue number (0 for non-batch).

    Returns:
        True if the completion entry exists and has ``remediation=True``.

    Issues: #902, #904.
    """
    def _read(sid: str) -> dict:
        state = _read_state(sid)
        if not state:
            return {}
        completions = state.get("completions", {})
        issue_completions = completions.get(str(issue_number), {})
        return issue_completions if isinstance(issue_completions, dict) else {}

    primary = _read(session_id)
    entry = primary.get(agent_type)
    if isinstance(entry, dict) and entry.get("remediation") is True:
        return True

    # Check unknown-session fallback (with TTL guard) for completeness.
    if session_id != "unknown":
        path = _state_file_path("unknown")
        try:
            if path.exists():
                mtime = path.stat().st_mtime
                if time.time() - mtime <= STALE_UNKNOWN_TTL_SECONDS:
                    fallback = _read("unknown")
                    f_entry = fallback.get(agent_type)
                    if isinstance(f_entry, dict) and f_entry.get("remediation") is True:
                        return True
        except OSError:
            pass

    return False


def get_completed_agents(
    session_id: str,
    *,
    issue_number: int = 0,
) -> set[str]:
    """Get the set of agents that have completed for a session/issue.

    Falls back to checking the 'unknown' session state when the primary
    session lookup returns empty. This handles the case where the coordinator
    initialized pipeline state before CLAUDE_SESSION_ID was set — state is
    written under session_id='unknown' but the hook reads with the real session
    ID. Issue #738.

    Staleness guard (Issue #875 / #904): the 'unknown'-session merge is
    skipped when the 'unknown' state file's mtime is older than
    ``STALE_UNKNOWN_TTL_SECONDS``. This prevents cross-pipeline contamination
    from a crashed / abandoned prior run whose state file still lingers in
    ``/tmp/`` — the old 'unknown' state must not bleed into a fresh session.

    Args:
        session_id: The pipeline session identifier.
        issue_number: The issue number (0 for non-batch).

    Returns:
        Set of agent type strings that completed successfully.
    """
    result: set[str] = set()
    state = _read_state(session_id)
    if state:
        completions = state.get("completions", {})
        issue_key = str(issue_number)
        issue_completions = completions.get(issue_key, {})
        if isinstance(issue_completions, dict):
            result = {
                k for k, v in issue_completions.items()
                if _completion_is_success(v)
            }

    # Merge completions from the 'unknown' session. The coordinator may have
    # recorded some agent completions before CLAUDE_SESSION_ID was available,
    # writing them under session_id='unknown'. We MERGE (not fallback) because
    # the primary session may have SOME completions but be MISSING agents that
    # were recorded under 'unknown'. Issues #738, #777.
    #
    # Staleness guard (Issue #875 / #904): skip merge if 'unknown' state is
    # older than STALE_UNKNOWN_TTL_SECONDS — prevents contamination from a
    # crashed / abandoned prior pipeline whose /tmp state file survived.
    if session_id != "unknown":
        path = _state_file_path("unknown")
        try:
            if path.exists():
                mtime = path.stat().st_mtime
                if time.time() - mtime > STALE_UNKNOWN_TTL_SECONDS:
                    # Stale 'unknown' state — do NOT merge.
                    return result
            else:
                return result
        except OSError:
            # Fail-safe: if stat fails we can't verify freshness, skip merge.
            return result

        fallback_state = _read_state("unknown")
        if fallback_state:
            completions = fallback_state.get("completions", {})
            issue_key = str(issue_number)
            issue_completions = completions.get(issue_key, {})
            if isinstance(issue_completions, dict):
                fallback_result = {
                    k for k, v in issue_completions.items()
                    if _completion_is_success(v)
                }
                if fallback_result - result:
                    import logging
                    logging.getLogger("pipeline_completion_state").info(
                        "Merging completions from session_id='unknown' (%s) into "
                        "primary session_id=%r (%s). Issues #738, #777.",
                        fallback_result - result,
                        session_id,
                        result,
                    )
                    result |= fallback_result

    return result


def record_agent_launch(
    session_id: str,
    agent_type: str,
    *,
    issue_number: int = 0,
) -> None:
    """Record that an agent has been launched (started) for a given session and issue.

    Called from PreToolUse BEFORE the agent runs. Tracks which agents have been
    started, separate from completions. Used by the parallel-mode defense-in-depth
    guard to distinguish "running concurrently" from "skipped entirely".

    Args:
        session_id: The pipeline session identifier.
        agent_type: The agent type (e.g., "reviewer", "security-auditor").
        issue_number: The issue number (0 for non-batch).

    Issues: #686
    """
    state = _ensure_state(session_id)
    launches = state.setdefault("launches", {})
    issue_key = str(issue_number)
    issue_launches = launches.setdefault(issue_key, {})
    issue_launches[agent_type] = True
    _write_state(session_id, state)


def get_launched_agents(
    session_id: str,
    *,
    issue_number: int = 0,
) -> set[str]:
    """Get the set of agents that have been launched for a session/issue.

    Falls back to checking the 'unknown' session state when the primary
    session lookup returns empty. This mirrors the fallback in
    get_completed_agents. Issue #738.

    Args:
        session_id: The pipeline session identifier.
        issue_number: The issue number (0 for non-batch).

    Returns:
        Set of agent type strings that have been launched.

    Issues: #686, #738
    """
    result = set()
    state = _read_state(session_id)
    if state:
        launches = state.get("launches", {})
        issue_key = str(issue_number)
        issue_launches = launches.get(issue_key, {})
        result = {k for k, v in issue_launches.items() if v}

    # Merge launches from 'unknown' session (same rationale as
    # get_completed_agents — see Issues #738, #777).
    if session_id != "unknown":
        fallback_state = _read_state("unknown")
        if fallback_state:
            launches = fallback_state.get("launches", {})
            issue_key = str(issue_number)
            issue_launches = launches.get(issue_key, {})
            fallback_result = {k for k, v in issue_launches.items() if v}
            result |= fallback_result

    return result


def record_prompt_baseline(
    session_id: str,
    agent_type: str,
    word_count: int,
    issue_number: int,
) -> None:
    """Record baseline prompt word count for an agent.

    Args:
        session_id: The pipeline session identifier.
        agent_type: The agent type.
        word_count: The prompt word count.
        issue_number: The issue number.
    """
    state = _ensure_state(session_id)
    baselines = state.setdefault("prompt_baselines", {})
    baselines[agent_type] = word_count
    _write_state(session_id, state)


def get_prompt_baseline(session_id: str, agent_type: str) -> Optional[int]:
    """Get baseline prompt word count for an agent.

    Args:
        session_id: The pipeline session identifier.
        agent_type: The agent type.

    Returns:
        Word count if recorded, None otherwise.
    """
    state = _read_state(session_id)
    if not state:
        return None
    baselines = state.get("prompt_baselines", {})
    value = baselines.get(agent_type)
    return int(value) if value is not None else None


def set_validation_mode(session_id: str, mode: str) -> None:
    """Set the validation mode for ordering enforcement.

    Args:
        session_id: The pipeline session identifier.
        mode: "sequential" or "parallel".
    """
    state = _ensure_state(session_id)
    state["validation_mode"] = mode
    _write_state(session_id, state)


def get_validation_mode(session_id: str) -> str:
    """Get the validation mode for ordering enforcement.

    Args:
        session_id: The pipeline session identifier.

    Returns:
        "sequential" (default) or "parallel".
    """
    state = _read_state(session_id)
    if not state:
        return "sequential"
    return state.get("validation_mode", "sequential")


def verify_batch_cia_completions(session_id: str) -> tuple[bool, list[int], list[int]]:
    """Verify CIA completed for all batch issues.

    Checks the completion state for a given session and verifies that
    'continuous-improvement-analyst' has been recorded as completed for
    every tracked issue. Designed to be called from the unified_pre_tool
    hook before allowing git commit in batch mode.

    Fail-open: returns (True, [], []) on any error to avoid blocking
    legitimate commits due to state file issues.

    Args:
        session_id: The pipeline session identifier.

    Returns:
        Tuple of (all_passed, issues_with_cia, issues_missing_cia).
        all_passed is True when every tracked issue has CIA completion.
        issues_with_cia lists issue numbers that have CIA.
        issues_missing_cia lists issue numbers missing CIA.

    Issues: #712
    """
    # Escape hatch: skip gate entirely if env var set
    if os.environ.get("SKIP_BATCH_CIA_GATE", "").strip().lower() in ("1", "true", "yes"):
        return (True, [], [])

    try:
        state = _read_state(session_id)
        if not state:
            # No state file — fail-open (nothing to enforce)
            return (True, [], [])

        completions = state.get("completions", {})
        if not completions:
            # No completions tracked — fail-open
            return (True, [], [])

        issues_with_cia: list[int] = []
        issues_missing_cia: list[int] = []

        for issue_key, issue_completions in completions.items():
            # Skip the "0" key (non-batch single-issue pipeline)
            if issue_key == "0":
                continue

            try:
                issue_num = int(issue_key)
            except (ValueError, TypeError):
                continue

            if not isinstance(issue_completions, dict):
                continue

            if _completion_is_success(
                issue_completions.get("continuous-improvement-analyst")
            ):
                issues_with_cia.append(issue_num)
            else:
                issues_missing_cia.append(issue_num)

        # If no batch issues found (only "0" key or empty), fail-open
        if not issues_with_cia and not issues_missing_cia:
            return (True, [], [])

        all_passed = len(issues_missing_cia) == 0
        return (all_passed, sorted(issues_with_cia), sorted(issues_missing_cia))

    except Exception:
        # Fail-open: any error returns pass
        return (True, [], [])


def record_doc_verdict(
    session_id: str,
    issue_number: int,
    verdict: str,
) -> None:
    """Record a doc-master verdict for a specific issue.

    Persists the verdict string to the completion state JSON under
    a "doc-master-verdict" key at the issue level. Uses the same
    fcntl locking pattern as record_agent_completion.

    Args:
        session_id: The pipeline session identifier.
        issue_number: The issue number.
        verdict: The verdict string (e.g., "PASS", "FAIL", "DOCS-UPDATED",
                 "NO-UPDATE-NEEDED", "DOCS-DRIFT-FOUND", "MISSING", "SHALLOW").

    Issues: #837
    """
    state = _ensure_state(session_id)
    completions = state.setdefault("completions", {})
    issue_key = str(issue_number)
    issue_completions = completions.setdefault(issue_key, {})
    issue_completions["doc-master-verdict"] = verdict
    _write_state(session_id, state)


# Valid doc-master verdicts that count as "verdict present".
_VALID_DOC_VERDICTS: set[str] = {
    "PASS",
    "FAIL",
    "DOCS-UPDATED",
    "NO-UPDATE-NEEDED",
    "DOCS-DRIFT-FOUND",
}


def verify_batch_doc_master_completions(session_id: str) -> tuple[bool, list[int], list[int]]:
    """Verify doc-master completed with a valid verdict for all batch issues.

    Checks the completion state for a given session and verifies that
    'doc-master' has been recorded as completed AND has a valid verdict
    for every tracked issue. Issues where doc-master completed but the
    verdict is MISSING, SHALLOW, or absent are treated as incomplete.

    Backward compatible: old state entries without a "doc-master-verdict"
    field but WITH doc-master completion pass through (fail-open on
    missing verdict field for backward compatibility).

    Fail-open: returns (True, [], []) on any error to avoid blocking
    legitimate commits due to state file issues.

    Args:
        session_id: The pipeline session identifier.

    Returns:
        Tuple of (all_passed, issues_with_doc_master, issues_missing_doc_master).
        all_passed is True when every tracked issue has doc-master completion
        AND a valid verdict (or no verdict field at all for backward compat).
        issues_with_doc_master lists issue numbers that have doc-master.
        issues_missing_doc_master lists issue numbers missing doc-master
        or having an invalid verdict (MISSING/SHALLOW).

    Issues: #786, #837
    """
    # Escape hatch: skip gate entirely if env var set
    if os.environ.get("SKIP_BATCH_DOC_MASTER_GATE", "").strip().lower() in ("1", "true", "yes"):
        return (True, [], [])

    try:
        state = _read_state(session_id)
        if not state:
            # No state file — fail-open (nothing to enforce)
            return (True, [], [])

        completions = state.get("completions", {})
        if not completions:
            # No completions tracked — fail-open
            return (True, [], [])

        issues_with_doc_master: list[int] = []
        issues_missing_doc_master: list[int] = []

        for issue_key, issue_completions in completions.items():
            # Skip the "0" key (non-batch single-issue pipeline)
            if issue_key == "0":
                continue

            try:
                issue_num = int(issue_key)
            except (ValueError, TypeError):
                continue

            if not isinstance(issue_completions, dict):
                continue

            if _completion_is_success(issue_completions.get("doc-master")):
                # Doc-master completed — now check verdict if present
                verdict = issue_completions.get("doc-master-verdict")
                if verdict is None:
                    # Backward compat: no verdict field recorded (old state).
                    # Treat as valid — fail-open on missing field.
                    issues_with_doc_master.append(issue_num)
                elif verdict in _VALID_DOC_VERDICTS:
                    # Valid verdict present
                    issues_with_doc_master.append(issue_num)
                else:
                    # Invalid verdict (MISSING, SHALLOW, etc.) — treat as incomplete
                    issues_missing_doc_master.append(issue_num)
            else:
                issues_missing_doc_master.append(issue_num)

        # If no batch issues found (only "0" key or empty), fail-open
        if not issues_with_doc_master and not issues_missing_doc_master:
            return (True, [], [])

        all_passed = len(issues_missing_doc_master) == 0
        return (all_passed, sorted(issues_with_doc_master), sorted(issues_missing_doc_master))

    except Exception:
        # Fail-open: any error returns pass
        return (True, [], [])


def record_pytest_gate_passed(
    session_id: str,
    *,
    issue_number: int = 0,
    passed: bool = True,
) -> None:
    """Record pytest gate result as a virtual agent completion.

    Uses the existing record_agent_completion infrastructure with
    agent_type='pytest-gate'. This means get_completed_agents() will
    automatically include 'pytest-gate' when the gate has passed.

    Args:
        session_id: Current session ID.
        issue_number: Issue number (0 for single-issue pipeline).
        passed: Whether pytest gate passed (True) or failed (False).

    Issues: #838
    """
    record_agent_completion(session_id, "pytest-gate", issue_number=issue_number, success=passed)


def get_pytest_gate_passed(
    session_id: str,
    *,
    issue_number: int = 0,
) -> bool:
    """Check if pytest gate has been recorded as passed.

    Args:
        session_id: Current session ID.
        issue_number: Issue number (0 for single-issue pipeline).

    Returns:
        True if pytest gate passed or SKIP_PYTEST_GATE env var is set.
        False if not recorded or recorded as failed.

    Issues: #838
    """
    skip = os.environ.get("SKIP_PYTEST_GATE", "").strip().lower()
    if skip in ("1", "true", "yes"):
        return True
    return "pytest-gate" in get_completed_agents(session_id, issue_number=issue_number)


def record_research_skipped(
    session_id: str,
    *,
    issue_number: int = 0,
) -> None:
    """Record that research was skipped for a given session/issue.

    Called by the coordinator after STEP 3.5 determines that research
    agents should be skipped (fully-specified change detection).

    Args:
        session_id: The pipeline session identifier.
        issue_number: The issue number (0 for non-batch).

    Issues: #802
    """
    state = _ensure_state(session_id)
    research_skipped = state.setdefault("research_skipped", {})
    issue_key = str(issue_number)
    research_skipped[issue_key] = True
    _write_state(session_id, state)


def get_research_skipped(
    session_id: str,
    *,
    issue_number: int = 0,
) -> bool:
    """Check if research was skipped for a given session/issue.

    Args:
        session_id: The pipeline session identifier.
        issue_number: The issue number (0 for non-batch).

    Returns:
        True if research was recorded as skipped, False otherwise.

    Issues: #802
    """
    state = _read_state(session_id)
    if not state:
        return False
    research_skipped = state.get("research_skipped", {})
    issue_key = str(issue_number)
    return bool(research_skipped.get(issue_key, False))


def record_plan_critic_skipped(
    session_id: str,
    *,
    issue_number: int = 0,
    reason: str = "pre_validated",
) -> None:
    """Record that plan-critic was skipped for a given session/issue.

    Called by the coordinator at STEP 5.5a when a pre-validated plan is
    found, OR at STEP 5.5a.1 when the Phase 2 classifier gate fires.

    Args:
        session_id: The pipeline session identifier.
        issue_number: The issue number (0 for non-batch).
        reason: Audit string. "pre_validated" (5.5a default) or "classifier" (Phase 2).

    Issues: #878, #961
    """
    state = _ensure_state(session_id)
    plan_critic_skipped = state.setdefault("plan_critic_skipped", {})
    issue_key = str(issue_number)
    plan_critic_skipped[issue_key] = {"skipped": True, "reason": reason}
    _write_state(session_id, state)


def get_plan_critic_skipped(
    session_id: str,
    *,
    issue_number: int = 0,
) -> bool:
    """Check if plan-critic was skipped for a given session/issue.

    Args:
        session_id: The pipeline session identifier.
        issue_number: The issue number (0 for non-batch).

    Returns:
        True if plan-critic was recorded as skipped, False otherwise.

    Issues: #878, #961
    """
    state = _read_state(session_id)
    if not state:
        return False
    plan_critic_skipped = state.get("plan_critic_skipped", {})
    issue_key = str(issue_number)
    entry = plan_critic_skipped.get(issue_key, False)
    if isinstance(entry, dict):
        return bool(entry.get("skipped", False))
    return bool(entry)


def record_web_research_skipped(
    session_id: str,
    *,
    issue_number: int = 0,
    reason: str = "classifier",
) -> None:
    """Record that web research (researcher agent) was skipped at STEP 4.

    Distinct from `record_research_skipped` (STEP 3.5 fully-specified path) so
    Phase 5 telemetry can attribute the skip to the classifier vs the
    pre-existing fully-specified gate.

    Args:
        session_id: The pipeline session identifier.
        issue_number: The issue number (0 for non-batch).
        reason: Audit string from pipeline_intent_gates.should_skip_web_research.

    Issues: #961
    """
    state = _ensure_state(session_id)
    web_research_skipped = state.setdefault("web_research_skipped", {})
    issue_key = str(issue_number)
    web_research_skipped[issue_key] = {"skipped": True, "reason": reason}
    _write_state(session_id, state)


def get_web_research_skipped(
    session_id: str,
    *,
    issue_number: int = 0,
) -> bool:
    """Check if web research was skipped (Phase 2 classifier gate).

    Args:
        session_id: The pipeline session identifier.
        issue_number: The issue number (0 for non-batch).

    Returns:
        True if recorded as skipped, False otherwise.

    Issues: #961
    """
    state = _read_state(session_id)
    if not state:
        return False
    web_research_skipped = state.get("web_research_skipped", {})
    issue_key = str(issue_number)
    entry = web_research_skipped.get(issue_key, False)
    if isinstance(entry, dict):
        return bool(entry.get("skipped", False))
    return bool(entry)


def verify_pipeline_agent_completions(
    session_id: str,
    pipeline_mode: str = "full",
    *,
    issue_number: int = 0,
) -> tuple[bool, set[str], set[str]]:
    """Verify all required agents completed for a pipeline run.

    Reads completed agents from state, determines required agents based on
    pipeline_mode and research_skipped, and returns whether all are present.

    Fail-open: returns (True, set(), set()) on any error to avoid blocking
    legitimate commits due to state file issues.

    Escape hatch: set SKIP_AGENT_COMPLETENESS_GATE=1 to bypass, or run:
    touch /tmp/skip_agent_completeness_gate (Issue #802)

    Args:
        session_id: The pipeline session identifier.
        pipeline_mode: Pipeline mode — "full", "light", "fix", or "tdd-first".
        issue_number: The issue number (0 for non-batch).

    Returns:
        Tuple of (passed, completed_agents, missing_agents).
        passed is True when all required agents have completed.

    Issues: #802
    """
    # Escape hatch: env var (works when set in harness command) or file-based bypass
    # (works from Bash: touch /tmp/skip_agent_completeness_gate)
    if os.environ.get("SKIP_AGENT_COMPLETENESS_GATE", "").strip().lower() in (
        "1",
        "true",
        "yes",
    ):
        return (True, set(), set())

    if _check_file_bypass():
        return (True, set(), set())

    try:
        completed = get_completed_agents(session_id, issue_number=issue_number)
        research_skipped = get_research_skipped(session_id, issue_number=issue_number)
        plan_critic_skipped = get_plan_critic_skipped(session_id, issue_number=issue_number)

        # Import agent_ordering_gate for get_required_agents
        try:
            from agent_ordering_gate import get_required_agents
        except ImportError:
            # Try relative import path
            import importlib.util

            gate_path = Path(__file__).resolve().parent / "agent_ordering_gate.py"
            if gate_path.exists():
                spec = importlib.util.spec_from_file_location(
                    "agent_ordering_gate", str(gate_path)
                )
                if spec and spec.loader:
                    mod = importlib.util.module_from_spec(spec)
                    spec.loader.exec_module(mod)
                    get_required_agents = mod.get_required_agents
                else:
                    return (True, set(), set())  # Fail-open
            else:
                return (True, set(), set())  # Fail-open

        required = get_required_agents(
            pipeline_mode,
            research_skipped=research_skipped,
            plan_critic_skipped=plan_critic_skipped,
        )
        missing = required - completed

        if missing:
            return (False, completed, missing)

        return (True, completed, set())

    except Exception:
        # Fail-open: any error returns pass
        return (True, set(), set())


def clear_session(session_id: str) -> None:
    """Remove the state file for a session.

    Args:
        session_id: The pipeline session identifier.
    """
    path = _state_file_path(session_id)
    try:
        path.unlink(missing_ok=True)
    except OSError:
        pass
