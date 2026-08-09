"""Regression test for Issue #1477.

Cluster mode (BATCH_NO_WORKTREE=1) sub-issue agent completions were
still invisible in session logs even after Issue #1430's hook-side fix,
because the coordinator never advanced ``current_index`` in
``<cwd>/.claude/batch_state.json`` nor set the ``CURRENT_BATCH_ISSUE``
env var between sub-issues. Every downstream Agent PostToolUse entry was
therefore tagged with the FIRST issue number, defeating per-sub-issue
attribution for CIA post-session analysis.

Fix: ``plugins/autonomous-dev/lib/batch_orchestrator.py`` exports a new
public helper ``advance_batch_state(issue_number)`` that (a) sets the
``CURRENT_BATCH_ISSUE`` env var and (b) advances the persisted
``current_index`` to match the in-flight issue. ``implement-batch.md``
STEP B3 documents the required call at the START of each sub-issue.

This test locks four invariants:

1. The helper exists and is importable.
2. The env-var write is unconditional (works even when batch_state.json
   is absent — this is what the hook's env-first fallback relies on).
3. The state-file write advances ``current_index`` to the correct
   position when the issue is in ``issues[]``.
4. ``implement-batch.md`` mentions the helper (documentation lock so a
   future refactor can't silently drop the coordinator-side call).
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
LIB = REPO_ROOT / "plugins" / "autonomous-dev" / "lib"
IMPLEMENT_BATCH_MD = REPO_ROOT / "plugins" / "autonomous-dev" / "commands" / "implement-batch.md"

sys.path.insert(0, str(LIB))
from batch_orchestrator import advance_batch_state, InvalidArgumentError  # noqa: E402


@pytest.fixture()
def clean_env():
    """Isolate CURRENT_BATCH_ISSUE writes so the test doesn't leak state."""
    saved = os.environ.pop("CURRENT_BATCH_ISSUE", None)
    yield
    os.environ.pop("CURRENT_BATCH_ISSUE", None)
    if saved is not None:
        os.environ["CURRENT_BATCH_ISSUE"] = saved


def test_advance_batch_state_helper_is_public_and_importable():
    """The helper MUST be public — the coordinator markdown imports it."""
    assert callable(advance_batch_state)


def test_advance_batch_state_sets_env_var_unconditionally(tmp_path, clean_env):
    """Env write happens even when batch_state.json is absent.

    The hook's env-first fallback relies on this: if the state file is
    missing (single-issue run, corrupted, etc.), the env var alone MUST
    be enough to attribute the current sub-issue.
    """
    result = advance_batch_state(1477, cwd=tmp_path)
    assert os.environ.get("CURRENT_BATCH_ISSUE") == "1477"
    assert result["issue_number"] == 1477
    assert result["env_set"] is True
    assert result["state_updated"] is False
    assert result["current_index"] is None


def test_advance_batch_state_advances_current_index(tmp_path, clean_env):
    """State-file write MUST set current_index to the issue's position."""
    claude_dir = tmp_path / ".claude"
    claude_dir.mkdir()
    state_path = claude_dir / "batch_state.json"
    state_path.write_text(
        json.dumps(
            {
                "issues": [1475, 1476, 1477, 1478],
                "current_index": 0,
                "no_worktree": True,
            }
        )
    )

    result = advance_batch_state(1477, cwd=tmp_path)

    assert result["state_updated"] is True
    assert result["current_index"] == 2
    persisted = json.loads(state_path.read_text())
    assert persisted["current_index"] == 2
    assert os.environ.get("CURRENT_BATCH_ISSUE") == "1477"


def test_advance_batch_state_leaves_env_set_when_issue_not_in_list(tmp_path, clean_env):
    """When the issue isn't in issues[], env is still set (defensive)."""
    claude_dir = tmp_path / ".claude"
    claude_dir.mkdir()
    state_path = claude_dir / "batch_state.json"
    state_path.write_text(
        json.dumps({"issues": [1475, 1476], "current_index": 0})
    )

    result = advance_batch_state(9999, cwd=tmp_path)

    assert os.environ.get("CURRENT_BATCH_ISSUE") == "9999"
    assert result["state_updated"] is False
    assert result["current_index"] is None
    persisted = json.loads(state_path.read_text())
    assert persisted["current_index"] == 0


def test_advance_batch_state_tolerates_malformed_state(tmp_path, clean_env):
    """Corrupt batch_state.json MUST NOT crash — env-var write still succeeds."""
    claude_dir = tmp_path / ".claude"
    claude_dir.mkdir()
    (claude_dir / "batch_state.json").write_text("not json {")

    result = advance_batch_state(1477, cwd=tmp_path)

    assert os.environ.get("CURRENT_BATCH_ISSUE") == "1477"
    assert result["state_updated"] is False


def test_advance_batch_state_rejects_invalid_issue_number(clean_env):
    """Non-positive / non-int inputs raise so bugs surface loudly."""
    with pytest.raises(InvalidArgumentError):
        advance_batch_state(0)
    with pytest.raises(InvalidArgumentError):
        advance_batch_state(-1)
    with pytest.raises(InvalidArgumentError):
        advance_batch_state("1477")  # type: ignore[arg-type]


def test_implement_batch_md_documents_advance_batch_state():
    """implement-batch.md MUST reference advance_batch_state so the fix
    doesn't silently vanish in a future markdown refactor."""
    content = IMPLEMENT_BATCH_MD.read_text()
    assert "advance_batch_state" in content, (
        "implement-batch.md must document the coordinator's required call "
        "to advance_batch_state() at the start of each sub-issue iteration "
        "in cluster mode (Issue #1477)."
    )
    assert "1477" in content or "#1477" in content, (
        "implement-batch.md should reference Issue #1477 near the "
        "advance_batch_state instruction so future maintainers can trace "
        "the rationale."
    )
