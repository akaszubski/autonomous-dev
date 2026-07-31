"""Regression test for Issue #1430.

Cluster mode (BATCH_NO_WORKTREE=1) sub-issue agent completions were
invisible in session logs — every log entry looked the same as a
top-level activity entry, so CIA post-session analysis could not
attribute per-issue agent completions.

Fix: session_activity_logger.py stamps two additional fields on every
PostToolUse entry when BATCH_NO_WORKTREE=1:

* ``batch_no_worktree: true`` — a stable boolean flag
* ``batch_issue_number: <int>`` — the in-flight issue, resolved from
  ``CURRENT_BATCH_ISSUE`` env var or ``.claude/batch_state.json``
  (issues[current_index]).

This test locks the tagging behaviour so post-session analyzers keep
seeing per-sub-issue attribution.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
HOOK = REPO_ROOT / "plugins" / "autonomous-dev" / "hooks" / "session_activity_logger.py"


def _run_hook(stdin_payload: dict, env_extra: dict, cwd: Path) -> tuple[int, str]:
    env = os.environ.copy()
    # Clear any inherited CLAUDE_SESSION_ID so the test controls it.
    for k in ("BATCH_NO_WORKTREE", "CURRENT_BATCH_ISSUE", "CLAUDE_SESSION_ID"):
        env.pop(k, None)
    env.update(env_extra)
    proc = subprocess.run(
        [sys.executable, str(HOOK)],
        input=json.dumps(stdin_payload),
        text=True,
        capture_output=True,
        env=env,
        cwd=str(cwd),
        timeout=15,
    )
    return proc.returncode, proc.stderr


def _read_last_log_entry(activity_dir: Path) -> dict:
    """Return the most recent PostToolUse entry (skips Heartbeat)."""
    files = sorted(activity_dir.glob("*.jsonl"))
    assert files, f"no jsonl log written in {activity_dir}"
    lines = files[-1].read_text().strip().splitlines()
    assert lines, "log file is empty"
    for line in reversed(lines):
        entry = json.loads(line)
        if entry.get("hook") == "PostToolUse":
            return entry
    raise AssertionError(f"no PostToolUse entry in {files[-1]}")


@pytest.fixture()
def workspace(tmp_path: Path) -> Path:
    # Minimal .claude/logs/activity/ tree so the hook writes here.
    (tmp_path / ".claude" / "logs" / "activity").mkdir(parents=True)
    return tmp_path


def _agent_payload(session_id: str = "regression-1430") -> dict:
    return {
        "hook_event_name": "PostToolUse",
        "tool_name": "Task",
        "session_id": session_id,
        "tool_input": {
            "subagent_type": "implementer",
            "description": "fix the thing",
            "prompt": "do work",
        },
        "tool_output": {"output": "done"},
    }


def test_batch_no_worktree_tags_entries(workspace: Path):
    """When BATCH_NO_WORKTREE=1, entries get batch_no_worktree=true."""
    rc, stderr = _run_hook(
        _agent_payload(),
        env_extra={"BATCH_NO_WORKTREE": "1", "CURRENT_BATCH_ISSUE": "1430"},
        cwd=workspace,
    )
    assert rc == 0, f"hook exited nonzero: {stderr}"
    entry = _read_last_log_entry(workspace / ".claude" / "logs" / "activity")
    assert entry.get("batch_no_worktree") is True, entry
    assert entry.get("batch_issue_number") == 1430, entry


def test_batch_no_worktree_falls_back_to_batch_state(workspace: Path):
    """Without CURRENT_BATCH_ISSUE env, issue is read from batch_state.json."""
    batch_state = workspace / ".claude" / "batch_state.json"
    batch_state.write_text(
        json.dumps(
            {
                "issues": [1430, 1431, 1432],
                "current_index": 1,
                "no_worktree": True,
            }
        )
    )
    rc, stderr = _run_hook(
        _agent_payload(),
        env_extra={"BATCH_NO_WORKTREE": "true"},
        cwd=workspace,
    )
    assert rc == 0, f"hook exited nonzero: {stderr}"
    entry = _read_last_log_entry(workspace / ".claude" / "logs" / "activity")
    assert entry.get("batch_no_worktree") is True
    assert entry.get("batch_issue_number") == 1431, entry


def test_no_batch_flag_leaves_entry_untagged(workspace: Path):
    """Outside cluster mode, no batch_no_worktree tag is emitted."""
    rc, stderr = _run_hook(_agent_payload(), env_extra={}, cwd=workspace)
    assert rc == 0, f"hook exited nonzero: {stderr}"
    entry = _read_last_log_entry(workspace / ".claude" / "logs" / "activity")
    assert "batch_no_worktree" not in entry, entry
    assert "batch_issue_number" not in entry, entry


def test_missing_batch_state_does_not_crash(workspace: Path):
    """If batch_state.json is absent, only the boolean tag is set."""
    rc, stderr = _run_hook(
        _agent_payload(),
        env_extra={"BATCH_NO_WORKTREE": "1"},
        cwd=workspace,
    )
    assert rc == 0, f"hook exited nonzero: {stderr}"
    entry = _read_last_log_entry(workspace / ".claude" / "logs" / "activity")
    assert entry.get("batch_no_worktree") is True
    # No issue number available — key omitted rather than set to null.
    assert "batch_issue_number" not in entry, entry


def test_malformed_batch_state_does_not_crash(workspace: Path):
    """Malformed batch_state.json is tolerated silently (non-blocking hook)."""
    (workspace / ".claude" / "batch_state.json").write_text("not json {")
    rc, stderr = _run_hook(
        _agent_payload(),
        env_extra={"BATCH_NO_WORKTREE": "1"},
        cwd=workspace,
    )
    assert rc == 0, f"hook exited nonzero: {stderr}"
    entry = _read_last_log_entry(workspace / ".claude" / "logs" / "activity")
    assert entry.get("batch_no_worktree") is True
    assert "batch_issue_number" not in entry
