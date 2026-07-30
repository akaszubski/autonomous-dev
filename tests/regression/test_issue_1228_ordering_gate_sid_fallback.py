#!/usr/bin/env python3
"""Regression tests for Issue #1228 — read-side session-id fallback in the
agent-completeness gate (``_check_pipeline_agent_completions``).

At ``git commit`` time the gate may be handed a session_id that has ZERO
completion records because the Bash subprocess dropped ``CLAUDE_SESSION_ID``
and fell back to a boot-time ``"unknown"`` sentinel, while the real agent
completions were recorded under a resolvable id. Fix #1228 adds a
SCOPE-LOCKED read-side fallback:

  * fires ONLY when the payload session_id yielded zero records
    (``not passed AND not completed AND missing``);
  * retries ``verify_pipeline_agent_completions`` under
    ``resolve_session_id()`` when that resolves to a *different*, non-"unknown"
    id; a pass there returns None (gate passes);
  * a PARTIAL primary session (some completed, some missing) STILL blocks —
    the fallback never fires, so an incomplete pipeline is never masked;
  * ``resolved == payload`` or ``resolved == "unknown"`` → no retry, block;
  * the evaluated session id(s) are appended to the deny reason.

These tests drive the REAL ``pipeline_completion_state`` state (file-based in
/tmp keyed by sha256(session_id)) that the hook loads dynamically, so no mock
is used for the module under test. ``resolve_session_id()`` is steered
deterministically via ``CLAUDE_SESSION_ID`` (highest-priority resolver step)
and the pipeline mode via ``PIPELINE_MODE``.
"""

import sys
import uuid
from pathlib import Path

import pytest

# Portable project root detection
_current = Path.cwd()
while _current != _current.parent:
    if (_current / ".git").exists() or (_current / ".claude").exists():
        PROJECT_ROOT = _current
        break
    _current = _current.parent
else:
    PROJECT_ROOT = Path.cwd()

HOOK_DIR = PROJECT_ROOT / "plugins" / "autonomous-dev" / "hooks"
LIB_DIR = PROJECT_ROOT / "plugins" / "autonomous-dev" / "lib"
sys.path.insert(0, str(HOOK_DIR))
sys.path.insert(0, str(LIB_DIR))

import json  # noqa: E402

import pipeline_completion_state as pcs  # noqa: E402
import pipeline_state  # noqa: E402
import unified_pre_tool  # noqa: E402
from agent_ordering_gate import get_required_agents  # noqa: E402

FIX_REQUIRED = sorted(get_required_agents("fix"))


@pytest.fixture
def clean_env(monkeypatch):
    """Isolate the gate env: fix mode, no bypass, no issue scoping."""
    monkeypatch.setenv("PIPELINE_MODE", "fix")
    monkeypatch.delenv("PIPELINE_ISSUE_NUMBER", raising=False)
    monkeypatch.delenv("SKIP_AGENT_COMPLETENESS_GATE", raising=False)
    # Ensure the file-based bypass is not present.
    try:
        pcs.SKIP_GATE_FILE.unlink()
    except (OSError, AttributeError):
        pass
    # Isolation (#1184): get_completed_agents merges the shared session_id='unknown'
    # state into any primary session (#738/#777). Other suites (e.g. the tracker
    # tests) record completions under 'unknown', which would contaminate the
    # "zero records" precondition of these tests. Clear it before each test so the
    # payload session genuinely starts with no records.
    try:
        pcs.clear_session("unknown")
    except Exception:
        pass
    yield
    try:
        pcs.clear_session("unknown")
    except Exception:
        pass


def _new_sid(tag: str) -> str:
    return f"sid-1228-{tag}-{uuid.uuid4().hex[:12]}"


def _record_all_fix_agents(session_id: str) -> None:
    for agent in FIX_REQUIRED:
        pcs.record_agent_completion(
            session_id=session_id, agent_type=agent, issue_number=0, success=True
        )


def _cleanup(*session_ids: str) -> None:
    for sid in session_ids:
        try:
            pcs.clear_session(sid)
        except Exception:
            pass


def test_zero_records_resolved_complete_gate_passes(clean_env, monkeypatch):
    """Zero payload-sid records + resolve yields a COMPLETE sid → gate passes (None)."""
    payload_sid = _new_sid("empty")
    resolved_sid = _new_sid("complete")
    try:
        _record_all_fix_agents(resolved_sid)
        # resolve_session_id() reads CLAUDE_SESSION_ID first.
        monkeypatch.setenv("CLAUDE_SESSION_ID", resolved_sid)

        result = unified_pre_tool._check_pipeline_agent_completions(payload_sid)
        assert result is None, (
            "#1228: zero records under payload sid + a complete resolved sid must "
            f"pass the gate via the read-side fallback, got: {result!r}"
        )
    finally:
        _cleanup(payload_sid, resolved_sid)


def test_partial_primary_session_still_blocks(clean_env, monkeypatch):
    """PARTIAL payload-sid records → fallback does NOT fire (scope-lock), still blocks."""
    payload_sid = _new_sid("partial")
    resolved_sid = _new_sid("complete")
    try:
        # Payload session has ONE agent recorded → completed is non-empty.
        pcs.record_agent_completion(
            session_id=payload_sid, agent_type=FIX_REQUIRED[0], issue_number=0, success=True
        )
        # A fully-complete session exists behind resolve — must NOT be consulted.
        _record_all_fix_agents(resolved_sid)
        monkeypatch.setenv("CLAUDE_SESSION_ID", resolved_sid)

        result = unified_pre_tool._check_pipeline_agent_completions(payload_sid)
        assert isinstance(result, str), (
            "#1228: a partial primary session must STILL block (scope-lock), "
            f"got: {result!r}"
        )
        # Scope-lock proof: the complete resolved sid must NOT have been evaluated.
        assert resolved_sid not in result, (
            "#1228: partial-session block must not consult the resolved complete "
            f"sid, but the deny reason referenced it: {result}"
        )
        assert payload_sid in result
    finally:
        _cleanup(payload_sid, resolved_sid)


def test_resolved_equals_payload_no_retry_blocks(clean_env, monkeypatch):
    """resolved == payload sid → no retry, blocks (deny reason has the evaluated sid)."""
    payload_sid = _new_sid("same")
    try:
        # No records anywhere; resolve returns the SAME sid as the payload.
        monkeypatch.setenv("CLAUDE_SESSION_ID", payload_sid)

        result = unified_pre_tool._check_pipeline_agent_completions(payload_sid)
        assert isinstance(result, str), "#1228: resolved==payload must block"
        assert payload_sid in result, (
            "#1228: deny reason must contain the evaluated session id"
        )
        # Only the payload sid should be listed once (no second evaluated sid).
        assert "Evaluated session id(s):" in result
    finally:
        _cleanup(payload_sid)


def test_resolved_unknown_no_retry_blocks(clean_env, monkeypatch):
    """resolved == 'unknown' → no retry, blocks."""
    payload_sid = _new_sid("noresolve")
    try:
        # CLAUDE_SESSION_ID literally "unknown" makes resolve_session_id() return
        # "unknown" (env step returns it verbatim), so the fallback must not retry.
        monkeypatch.setenv("CLAUDE_SESSION_ID", "unknown")

        result = unified_pre_tool._check_pipeline_agent_completions(payload_sid)
        assert isinstance(result, str), "#1228: resolved=='unknown' must block"
        assert payload_sid in result
        # 'unknown' must not appear as a *second* evaluated sid.
        evaluated_line = [
            ln for ln in result.split(". ") if ln.startswith("Evaluated session id(s):")
        ]
        assert evaluated_line, "#1228: deny reason must include evaluated sid(s) line"
        assert "unknown" not in evaluated_line[0], (
            "#1228: 'unknown' resolution must not be added as an evaluated sid"
        )
    finally:
        _cleanup(payload_sid)


def test_deny_reason_contains_both_evaluated_sids_on_failed_fallback(clean_env, monkeypatch):
    """When the fallback retries but still fails, BOTH evaluated sids are reported."""
    payload_sid = _new_sid("bothempty")
    resolved_sid = _new_sid("alsoempty")
    try:
        # Neither session has any records → fallback retries resolved, still fails.
        monkeypatch.setenv("CLAUDE_SESSION_ID", resolved_sid)

        result = unified_pre_tool._check_pipeline_agent_completions(payload_sid)
        assert isinstance(result, str), "#1228: both-empty must block"
        assert payload_sid in result and resolved_sid in result, (
            "#1228: deny reason must list BOTH evaluated session ids when the "
            f"fallback fired but still failed, got: {result}"
        )
    finally:
        _cleanup(payload_sid, resolved_sid)


# ---------------------------------------------------------------------------
# #1228 concurrent-session hardening (remediation) — activity-log path affinity
# ---------------------------------------------------------------------------
#
# These tests exercise the ACTUAL activity-log resolution path (NOT the env-var
# path the 5 tests above steer through). They prove:
#   (1) the broad activity-log scan WOULD return an unrelated concurrent
#       session's id (the collision hole);
#   (2) the affine resolver used by the gate does NOT trust that scan; and
#   (3) the gate therefore STILL BLOCKS a zero-completion current session even
#       when a fully-complete concurrent session exists in the same repo's log.
# A positive test proves the legitimate same-session recovery (via the STEP-0
# sentinel, which carries the real session id) DOES pass.


def _today() -> str:
    from datetime import datetime

    return datetime.now().strftime("%Y-%m-%d")


def test_broad_activity_log_scan_returns_concurrent_session_documents_hole(tmp_path):
    """Document the hole: the broad activity-log scan returns the most-recent
    real session id today, with NO cwd/PID/temporal scoping — so a concurrent
    UNRELATED session (Y) is what it resolves, not the committing session (X)."""
    today = _today()
    log_dir = tmp_path / ".claude" / "logs" / "activity"
    log_dir.mkdir(parents=True)
    session_x = _new_sid("commit-X")
    session_y = _new_sid("concurrent-Y")
    log_file = log_dir / f"{today}.jsonl"
    # X's entry first, Y's entry LAST → Y is the most-recent real sid.
    log_file.write_text(
        json.dumps({"session_id": session_x, "hook": "PreToolUse"}) + "\n"
        + json.dumps({"session_id": session_y, "hook": "SubagentStop"}) + "\n"
    )
    resolved = pcs._resolve_session_id_from_activity_log(log_dir=log_dir, today=today)
    assert resolved == session_y, (
        "#1228: the broad activity-log scan returns the most-recent real sid "
        f"(concurrent session Y), documenting the collision hole; got {resolved!r}"
    )


def test_affine_resolver_ignores_activity_log_returns_none(tmp_path, monkeypatch):
    """The affine resolver NEVER consults the activity-log scan: with no env var
    and no fresh sentinel it returns None (fail-safe), not a concurrent sid."""
    monkeypatch.delenv("CLAUDE_SESSION_ID", raising=False)
    nonexistent = tmp_path / "no_such_sentinel.json"
    resolved = pcs.resolve_session_id_affine(sentinel_path=str(nonexistent))
    assert resolved is None, (
        "#1228: affine resolver must return None when no affine source (env/"
        f"sentinel) yields a real id — it must NOT scan the activity log; got {resolved!r}"
    )


def test_concurrent_session_does_not_satisfy_gate_still_blocks(
    clean_env, tmp_path, monkeypatch
):
    """CONCURRENT-COLLISION BLOCK: session X commits with ZERO completions while
    a fully-complete concurrent session Y sits in the same repo's activity log.
    Resolution is driven through the ACTIVITY-LOG path (no env var, no fresh
    sentinel). The gate MUST STILL BLOCK — Y's completions must NOT satisfy X's
    commit gate.

    TRUE REGRESSION: we ``chdir`` into a synthetic repo whose activity log holds
    both sessions, so the pre-fix gate (which called the broad
    ``resolve_session_id()`` → cwd activity-log scan) WOULD resolve the complete
    Y and wrongly PASS. The sub-assertion below proves the broad resolver still
    returns Y here; the fixed gate uses ``resolve_session_id_affine()`` (which
    ignores the activity-log scan → None) and therefore blocks.
    """
    monkeypatch.delenv("CLAUDE_SESSION_ID", raising=False)
    payload_sid = _new_sid("X-commit-empty")  # current commit, zero records
    session_y = _new_sid("Y-concurrent-complete")
    today = _today()
    # Synthetic repo root: has .claude so find_project_root stops here and the
    # per-repo sentinel path resolves under it (and does NOT exist → no affine
    # source). The activity log lives where _find_activity_log_dir() looks.
    log_dir = tmp_path / ".claude" / "logs" / "activity"
    log_dir.mkdir(parents=True)
    (log_dir / f"{today}.jsonl").write_text(
        json.dumps({"session_id": payload_sid, "hook": "PreToolUse"}) + "\n"
        + json.dumps({"session_id": session_y, "hook": "SubagentStop"}) + "\n"
    )
    monkeypatch.chdir(tmp_path)
    try:
        # Y is a fully-complete concurrent session.
        _record_all_fix_agents(session_y)

        # Sub-assertion (regression anchor): the BROAD resolver — what the
        # pre-fix gate used — resolves the complete concurrent Y from the cwd
        # activity log. If the gate still used it, it would wrongly PASS.
        assert pcs.resolve_session_id() == session_y, (
            "#1228: broad resolve_session_id() must return the concurrent Y here "
            "(this is the hole the fix closes)"
        )
        # The affine resolver used by the fixed gate returns None (no env, no
        # fresh sentinel; it never consults the activity log).
        assert pcs.resolve_session_id_affine() is None

        result = unified_pre_tool._check_pipeline_agent_completions(payload_sid)
        assert isinstance(result, str), (
            "#1228: gate must STILL BLOCK X's zero-completion commit — a concurrent "
            f"complete session (Y) must not satisfy it, got: {result!r}"
        )
        assert session_y not in result, (
            "#1228: the concurrent session Y must NEVER be evaluated by the gate; "
            f"the deny reason referenced it: {result}"
        )
        assert payload_sid in result
    finally:
        _cleanup(payload_sid, session_y)


def test_same_session_sentinel_recovery_passes(clean_env, tmp_path, monkeypatch):
    """POSITIVE recovery: the legitimate Bash-subprocess-dropped-CLAUDE_SESSION_ID
    case. The env var is gone, but the STEP-0 sentinel carries THIS session's
    real id (written by the coordinator). The affine resolver reads the sentinel
    → the gate resolves the real, COMPLETE session → passes (None).
    """
    monkeypatch.delenv("CLAUDE_SESSION_ID", raising=False)
    payload_sid = _new_sid("dropped-env")  # boot-time 'unknown'-like empty session
    real_sid = _new_sid("real-complete")
    sentinel = tmp_path / "implement_pipeline_state.json"
    sentinel.write_text(json.dumps({"session_id": real_sid}))
    # Fresh mtime (just written) → within the affine resolver's max_age window.
    monkeypatch.setattr(
        pipeline_state, "get_legacy_sentinel_path", lambda repo_root=None: sentinel
    )
    try:
        _record_all_fix_agents(real_sid)

        # Unit-level: affine resolver reads the sentinel's real sid.
        assert pcs.resolve_session_id_affine(sentinel_path=str(sentinel)) == real_sid

        result = unified_pre_tool._check_pipeline_agent_completions(payload_sid)
        assert result is None, (
            "#1228: legitimate same-session sentinel recovery must PASS the gate — "
            f"the real complete session id is affine and resolvable, got: {result!r}"
        )
    finally:
        _cleanup(payload_sid, real_sid)


def test_stale_sentinel_is_ignored_by_affine_resolver(tmp_path, monkeypatch):
    """A sentinel older than max_age_seconds is NOT trusted (temporal affinity) —
    a stale marker from a prior/abandoned run must not resolve a session id."""
    import os as _os
    import time as _time

    monkeypatch.delenv("CLAUDE_SESSION_ID", raising=False)
    sentinel = tmp_path / "stale_sentinel.json"
    sentinel.write_text(json.dumps({"session_id": _new_sid("stale")}))
    # Age the sentinel well beyond the default 3600s window.
    old = _time.time() - 7200
    _os.utime(sentinel, (old, old))
    resolved = pcs.resolve_session_id_affine(sentinel_path=str(sentinel))
    assert resolved is None, (
        "#1228: a stale sentinel (mtime beyond max_age) must be ignored by the "
        f"affine resolver, got {resolved!r}"
    )


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-v"]))
