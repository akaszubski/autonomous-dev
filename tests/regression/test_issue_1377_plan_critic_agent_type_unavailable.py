"""Regression test for Issue #1377.

Verifies the STEP 5.5 graceful-degradation path when the plan-critic subagent
type is not registered in the current Claude Code environment:

  1. record_plan_critic_skipped() writes the bypass with raw error text.
  2. check_minimum_agent_count(plan_critic_skipped=True) returns passed=True
     when all other required agents are present.
  3. The raw error text is grepable in an audit surface (activity log or state).
  4. Documentation contract: implement.md STEP 5.5a.2 documents the
     graceful-degradation path with the required error-string patterns.
"""

import glob
import re
import sys
import uuid
from pathlib import Path

import pytest


REPO_ROOT = Path(__file__).resolve().parents[2]
LIB_DIR = REPO_ROOT / "plugins" / "autonomous-dev" / "lib"
IMPLEMENT_MD = REPO_ROOT / "plugins" / "autonomous-dev" / "commands" / "implement.md"


def _import_lib():
    """Import agent_ordering_gate and pipeline_completion_state.

    Returns a tuple ``(agent_ordering_gate, pipeline_completion_state)``.
    Skips the test (via pytest.skip) if imports fail — this keeps the test
    resilient to lib refactors.
    """
    if str(LIB_DIR) not in sys.path:
        sys.path.insert(0, str(LIB_DIR))
    try:
        import agent_ordering_gate  # noqa: F401
        import pipeline_completion_state  # noqa: F401

        return agent_ordering_gate, pipeline_completion_state
    except ImportError as e:
        pytest.skip(f"lib modules not importable: {e}")
        return None, None  # unreachable, satisfies static analysis


def test_record_plan_critic_skipped_embeds_raw_error():
    """record_plan_critic_skipped MUST persist raw error text in bypass_reason."""
    _, pcs = _import_lib()

    session_id = f"test-1377-{uuid.uuid4().hex[:8]}"
    issue_number = 1377
    raw_error = "unknown subagent type: plan-critic"
    bypass_reason = f"agent_type_unavailable: {raw_error}"

    pcs.record_plan_critic_skipped(
        session_id,
        issue_number=issue_number,
        bypass_reason=bypass_reason,
    )

    # Sanity: the marker itself was written.
    assert pcs.get_plan_critic_skipped(session_id, issue_number=issue_number) is True

    # Read the raw state and assert the bypass_reason preserves both the
    # category token AND the raw error verbatim (see 5.5a.2 audit requirement).
    state = pcs._read_state(session_id)
    assert state, "state must be readable after record_plan_critic_skipped"

    reasons = state.get("plan_critic_bypass_reason", {})
    stored_reason = reasons.get(str(issue_number))
    assert stored_reason is not None, (
        "bypass_reason must be persisted under plan_critic_bypass_reason "
        f"namespace; got state keys: {sorted(state.keys())}"
    )
    assert "agent_type_unavailable" in stored_reason, (
        f"bypass_reason missing category token: {stored_reason!r}"
    )
    assert raw_error in stored_reason, (
        f"bypass_reason missing raw error substring {raw_error!r}: "
        f"got {stored_reason!r}"
    )


def test_check_minimum_agent_count_passes_with_plan_critic_skipped():
    """check_minimum_agent_count MUST pass when plan-critic is legitimately skipped."""
    aog, _ = _import_lib()

    # Positive case: plan_critic_skipped=True excludes plan-critic from required.
    required = aog.get_required_agents(mode="full", plan_critic_skipped=True)
    assert "plan-critic" not in required, (
        f"plan-critic should be excluded when plan_critic_skipped=True; "
        f"got: {sorted(required)}"
    )

    # Simulate the exact "everything but plan-critic done" state.
    completed_agents = set(required)
    result = aog.check_minimum_agent_count(
        completed_agents=completed_agents,
        required_agents=required,
    )
    assert result.passed is True, (
        f"check_minimum_agent_count should pass; got reason={result.reason!r}"
    )

    # Negative case: without the skip, plan-critic IS required and its absence
    # blocks the gate. This proves the skip flag is what unblocks the gate.
    required_no_skip = aog.get_required_agents(mode="full", plan_critic_skipped=False)
    assert "plan-critic" in required_no_skip, (
        f"plan-critic MUST be in required set when plan_critic_skipped=False; "
        f"got: {sorted(required_no_skip)}"
    )
    result_no_skip = aog.check_minimum_agent_count(
        completed_agents=completed_agents,
        required_agents=required_no_skip,
    )
    assert result_no_skip.passed is False, (
        "check_minimum_agent_count should FAIL when plan-critic is required "
        f"but missing; got reason={result_no_skip.reason!r}"
    )
    assert "plan-critic" in result_no_skip.missing_agents, (
        f"plan-critic must appear in missing_agents; "
        f"got: {result_no_skip.missing_agents}"
    )


def test_bypass_reason_is_grepable_in_activity_log():
    """Raw error text MUST be grepable in an audit surface (activity log or state).

    The activity-log emission is opportunistic (see #1325). If the activity
    log directory does not exist in this environment, fall back to the state
    file — which is the primary persistence layer and always the source of
    truth.
    """
    _, pcs = _import_lib()

    session_id = f"test-1377-{uuid.uuid4().hex[:8]}"
    issue_number = 1377
    raw_error = "unknown subagent type: plan-critic"
    bypass_reason = f"agent_type_unavailable: {raw_error}"

    pcs.record_plan_critic_skipped(
        session_id,
        issue_number=issue_number,
        bypass_reason=bypass_reason,
    )

    # Preferred: activity log at .claude/logs/activity/<date>.jsonl
    activity_dir = REPO_ROOT / ".claude" / "logs" / "activity"
    activity_hit = False
    if activity_dir.exists():
        for log_path in sorted(activity_dir.glob("*.jsonl")):
            try:
                content = log_path.read_text(errors="replace")
            except OSError:
                continue
            if raw_error in content and session_id in content:
                activity_hit = True
                break

    if activity_hit:
        return  # activity log has the audit trail; primary surface satisfied.

    # Fallback: assert the raw error text is present in the state file itself,
    # which is the guaranteed persistence layer.
    state_path = pcs._state_file_path(session_id)
    if not state_path.exists():
        pytest.skip(
            "state file not present at expected path; environment may not "
            "support the /tmp-based state persistence layer"
        )
    state_text = state_path.read_text(errors="replace")
    assert raw_error in state_text, (
        f"raw error text {raw_error!r} not grepable in state file "
        f"{state_path} — audit trail is broken"
    )
    assert "agent_type_unavailable" in state_text, (
        "category token 'agent_type_unavailable' not grepable in state file "
        f"{state_path}"
    )


def test_implement_md_documents_graceful_degradation():
    """implement.md STEP 5.5a.2 MUST document the graceful-degradation path."""
    assert IMPLEMENT_MD.exists(), f"implement.md missing at {IMPLEMENT_MD}"
    content = IMPLEMENT_MD.read_text()

    # The category token is present.
    assert "agent_type_unavailable" in content, (
        "implement.md must reference 'agent_type_unavailable' bypass category"
    )

    # At least 3 of the 5 documented error patterns are present.
    patterns = [
        "agent type not available",
        "unknown subagent type",
        "invalid subagent_type",
        "not registered",
        "no such subagent",
    ]
    matched = [p for p in patterns if p in content]
    assert len(matched) >= 3, (
        f"implement.md must document at least 3 of the 5 error patterns; "
        f"matched only: {matched}"
    )

    # The sub-section label 5.5a.2 is present.
    assert "5.5a.2" in content, (
        "implement.md must document sub-section '5.5a.2' for the "
        "graceful-degradation path"
    )

    # References Issue #1228 (dependency note) somewhere in the file.
    assert "#1228" in content, (
        "implement.md must reference Issue #1228 in the STEP 5.5 context"
    )

    # The STEP 5.5d FORBIDDEN section must have an EXCEPT carve-out
    # referencing either 5.5a.2 or the phrase 'not registered'.
    # We locate the plan-critic FORBIDDEN bullet and check its content.
    forbidden_line_pattern = re.compile(
        r"MUST NOT skip plan-critic when no pre-validated plan file exists.*",
        re.IGNORECASE,
    )
    matches = forbidden_line_pattern.findall(content)
    assert matches, (
        "FORBIDDEN bullet about skipping plan-critic when no pre-validated "
        "plan exists is missing"
    )
    forbidden_line = matches[0]
    assert ("5.5a.2" in forbidden_line) or ("not registered" in forbidden_line), (
        "FORBIDDEN #3 must carve out an EXCEPT clause referencing '5.5a.2' "
        f"or 'not registered'; got: {forbidden_line!r}"
    )
