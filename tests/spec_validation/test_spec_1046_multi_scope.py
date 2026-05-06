"""Spec validation for issue #1046 — multi-scope auto-write in record_agent_completion.

Tests are derived BLIND from acceptance criteria only:
  AC1: Reader audit completed; affected readers fixed in same PR
  AC2: record_agent_completion() writes under issue_number=N, issue_number=0,
       and unscoped by default
  AC3: _single_scope=True opt-out preserves single-scope behavior
  AC4: No existing caller breaks (existing tests pass after assertion updates)
  AC5: New test: agent recorded once writes 3 entries; reading from any scope
       finds the agent

Scope key model (from spec):
  - record_agent_completion(sid, 'agent-X', issue_number=42)
    -> writes under "42", "0", AND "unscoped"
  - record_agent_completion(sid, 'agent-X')  # default issue_number=0
    -> writes under "0" and "unscoped"
  - record_agent_completion(sid, 'agent-X', issue_number=42, _single_scope=True)
    -> writes ONLY under "42"
"""
from __future__ import annotations

import json
import sys
import uuid
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
LIB_DIR = REPO_ROOT / "plugins" / "autonomous-dev" / "lib"
sys.path.insert(0, str(LIB_DIR))

import pipeline_completion_state as pcs  # noqa: E402


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _fresh_session(monkeypatch, tmp_path) -> str:
    """Create an isolated session with its own state file in tmp_path."""
    session_id = f"test-1046-{uuid.uuid4().hex}"
    # Redirect the state file to tmp_path to keep tests hermetic.
    state_file = tmp_path / f"state_{session_id}.json"

    def _fake_path(sid, *, run_id=None):  # match the function signature loosely
        return state_file

    monkeypatch.setattr(pcs, "_state_file_path", _fake_path)
    return session_id


def _read_state(session_id: str, *, monkeypatch_target=None) -> dict:
    """Read the raw state file produced by the module."""
    path = pcs._state_file_path(session_id)
    if not path.exists():
        return {}
    return json.loads(path.read_text())


# ---------------------------------------------------------------------------
# AC2 — tri-scope auto-write by default with explicit issue_number
# ---------------------------------------------------------------------------

def test_spec_1046_ac2_tri_scope_writes_three_entries(tmp_path, monkeypatch):
    """AC2 / AC5: issue_number=42 default writes under "42", "0", "unscoped"."""
    sid = _fresh_session(monkeypatch, tmp_path)

    pcs.record_agent_completion(sid, "agent-alpha", issue_number=42)

    state = _read_state(sid)
    assert "completions" in state, f"missing 'completions' top-level key: {state}"

    completions = state["completions"]
    # All three scope keys MUST be present
    assert "42" in completions, f"missing scope '42': keys={list(completions)}"
    assert "0" in completions, f"missing scope '0': keys={list(completions)}"
    assert "unscoped" in completions, (
        f"missing scope 'unscoped': keys={list(completions)}"
    )


def test_spec_1046_ac2_agent_present_in_all_three_scopes(tmp_path, monkeypatch):
    """AC2: the recorded agent name must appear in each of the 3 scopes."""
    sid = _fresh_session(monkeypatch, tmp_path)

    pcs.record_agent_completion(sid, "agent-beta", issue_number=99)

    state = _read_state(sid)
    completions = state["completions"]

    def _agents_in(scope_key: str) -> set[str]:
        scope = completions.get(scope_key, {})
        # Scope is dict-like; agents are either keys, or in a nested "agents" map
        if isinstance(scope, dict):
            if "agents" in scope and isinstance(scope["agents"], dict):
                return set(scope["agents"].keys())
            return set(scope.keys())
        return set()

    for scope_key in ("99", "0", "unscoped"):
        agents = _agents_in(scope_key)
        assert "agent-beta" in agents, (
            f"agent-beta not found under scope '{scope_key}': {agents}"
        )


def test_spec_1046_ac2_default_issue_zero_writes_zero_and_unscoped(
    tmp_path, monkeypatch
):
    """AC2: with default issue_number=0, writes go to '0' and 'unscoped'.

    Per spec: 'When issue_number=0 (default), writes to "0" and "unscoped"
    (no separate "N" key).'
    """
    sid = _fresh_session(monkeypatch, tmp_path)

    # Default call (no issue_number arg) -> issue_number=0
    pcs.record_agent_completion(sid, "agent-gamma")

    state = _read_state(sid)
    completions = state["completions"]

    assert "0" in completions, f"missing '0' scope: keys={list(completions)}"
    assert "unscoped" in completions, (
        f"missing 'unscoped' scope: keys={list(completions)}"
    )


# ---------------------------------------------------------------------------
# AC3 — _single_scope=True opt-out
# ---------------------------------------------------------------------------

def test_spec_1046_ac3_single_scope_with_issue_writes_only_issue_scope(
    tmp_path, monkeypatch
):
    """AC3: _single_scope=True with issue_number=42 writes ONLY under '42'."""
    sid = _fresh_session(monkeypatch, tmp_path)

    pcs.record_agent_completion(
        sid, "agent-delta", issue_number=42, _single_scope=True
    )

    state = _read_state(sid)
    completions = state["completions"]

    # Must contain the explicit scope
    assert "42" in completions, f"missing '42' scope: keys={list(completions)}"

    # Must NOT have written agent-delta under '0' or 'unscoped'
    def _has_agent(scope_key: str, agent: str) -> bool:
        scope = completions.get(scope_key, {})
        if not isinstance(scope, dict):
            return False
        if "agents" in scope and isinstance(scope["agents"], dict):
            return agent in scope["agents"]
        return agent in scope

    assert not _has_agent("0", "agent-delta"), (
        f"_single_scope leaked into '0' scope: {completions.get('0')}"
    )
    assert not _has_agent("unscoped", "agent-delta"), (
        f"_single_scope leaked into 'unscoped' scope: "
        f"{completions.get('unscoped')}"
    )


# ---------------------------------------------------------------------------
# AC5 — agent findable from any scope after a single tri-scope write
# ---------------------------------------------------------------------------

def test_spec_1046_ac5_get_completed_agents_finds_from_explicit_issue(
    tmp_path, monkeypatch
):
    """AC5: After tri-scope write, get_completed_agents(issue_number=42) finds it."""
    sid = _fresh_session(monkeypatch, tmp_path)

    pcs.record_agent_completion(sid, "agent-epsilon", issue_number=42)

    found = pcs.get_completed_agents(sid, issue_number=42)
    assert "agent-epsilon" in found, (
        f"agent not retrievable via issue_number=42: {found}"
    )


def test_spec_1046_ac5_get_completed_agents_finds_from_zero_scope(
    tmp_path, monkeypatch
):
    """AC5: After tri-scope write, get_completed_agents(issue_number=0) finds it."""
    sid = _fresh_session(monkeypatch, tmp_path)

    pcs.record_agent_completion(sid, "agent-zeta", issue_number=42)

    found_zero = pcs.get_completed_agents(sid, issue_number=0)
    assert "agent-zeta" in found_zero, (
        f"agent not retrievable via issue_number=0: {found_zero}"
    )


def test_spec_1046_ac5_get_completed_agents_finds_from_default(
    tmp_path, monkeypatch
):
    """AC5: After tri-scope write, default get_completed_agents finds the agent."""
    sid = _fresh_session(monkeypatch, tmp_path)

    pcs.record_agent_completion(sid, "agent-eta", issue_number=77)

    found_default = pcs.get_completed_agents(sid)
    assert "agent-eta" in found_default, (
        f"agent not retrievable via default get_completed_agents: {found_default}"
    )


# ---------------------------------------------------------------------------
# AC4 — backward compatibility (existing default behavior continues to work)
# ---------------------------------------------------------------------------

def test_spec_1046_ac4_default_call_round_trip(tmp_path, monkeypatch):
    """AC4: classic record-then-read pattern still works."""
    sid = _fresh_session(monkeypatch, tmp_path)

    pcs.record_agent_completion(sid, "implementer")
    pcs.record_agent_completion(sid, "reviewer")

    found = pcs.get_completed_agents(sid)
    assert "implementer" in found
    assert "reviewer" in found
