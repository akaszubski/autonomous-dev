#!/usr/bin/env python3
"""Regression test for session_activity_logger.py phantom-then-real dedup (Issue #1461).

Ports the #1414 phantom-dedup guard from unified_session_tracker.py to
session_activity_logger.py's Task/Agent PostToolUse write path. Verifies:

1. A phantom Task PostToolUse (low word count + nonexistent transcript_path)
   is classified as phantom and written only as an audit entry.
2. A real Task PostToolUse (substantive word count OR valid transcript) is
   written normally.
3. Two Task PostToolUse entries for the same (session_id, subagent_type) within
   PHANTOM_DEDUP_WINDOW_SECONDS produce a normal write for the first and a
   dedup-skip audit entry for the second.
4. Two distinct subagent_types in the same session both get written (no
   cross-agent collision on the dedup key).
"""

import importlib.util
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

import pytest


HOOK_PATH = (
    Path(__file__).parents[2]
    / "plugins/autonomous-dev/hooks/session_activity_logger.py"
)


def _load_hook_module():
    """Import the hook module directly for unit-level testing of helpers."""
    spec = importlib.util.spec_from_file_location(
        "session_activity_logger_1461", HOOK_PATH
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


# ---------------------------------------------------------------------------
# Unit tests: _classify_task_agent_phantom
# ---------------------------------------------------------------------------


def test_classify_missing_transcript_low_words_returns_phantom_skip():
    m = _load_hook_module()
    m._PHANTOM_DEDUP_CACHE.clear()
    verdict, extra = m._classify_task_agent_phantom(
        subagent_type="implementer",
        session_id="s1",
        result_word_count=5,
        agent_transcript_path="/tmp/definitely-does-not-exist-1461.jsonl",
    )
    assert verdict == "phantom_skip"
    assert extra["phantom_reason"] == "transcript_missing_low_words"
    assert extra["phantom_word_count"] == 5


def test_classify_existing_transcript_low_words_returns_write():
    m = _load_hook_module()
    m._PHANTOM_DEDUP_CACHE.clear()
    with tempfile.NamedTemporaryFile(suffix=".jsonl", delete=False) as tmp:
        tpath = tmp.name
    try:
        verdict, extra = m._classify_task_agent_phantom(
            subagent_type="implementer",
            session_id="s1",
            result_word_count=5,
            agent_transcript_path=tpath,
        )
        # Transcript exists => tier-1 phantom_skip does NOT fire; first observation
        # => write.
        assert verdict == "write"
    finally:
        os.unlink(tpath)


def test_classify_high_word_count_returns_write_even_with_missing_transcript():
    m = _load_hook_module()
    m._PHANTOM_DEDUP_CACHE.clear()
    verdict, _ = m._classify_task_agent_phantom(
        subagent_type="implementer",
        session_id="s1",
        result_word_count=500,
        agent_transcript_path="/tmp/nope-1461.jsonl",
    )
    assert verdict == "write"


def test_classify_phantom_then_real_within_window_dedups_second():
    m = _load_hook_module()
    m._PHANTOM_DEDUP_CACHE.clear()
    # First observation with a real (high wc) entry => write.
    v1, _ = m._classify_task_agent_phantom(
        subagent_type="planner",
        session_id="s2",
        result_word_count=200,
        agent_transcript_path="",
    )
    assert v1 == "write"
    # Second observation of same (session, agent) within window => dedup_skip.
    v2, e2 = m._classify_task_agent_phantom(
        subagent_type="planner",
        session_id="s2",
        result_word_count=200,
        agent_transcript_path="",
    )
    assert v2 == "dedup_skip"
    assert e2["phantom_reason"] == "duplicate_within_window"


def test_classify_distinct_agents_same_session_both_write():
    m = _load_hook_module()
    m._PHANTOM_DEDUP_CACHE.clear()
    v1, _ = m._classify_task_agent_phantom(
        subagent_type="implementer",
        session_id="s3",
        result_word_count=100,
        agent_transcript_path="",
    )
    v2, _ = m._classify_task_agent_phantom(
        subagent_type="reviewer",
        session_id="s3",
        result_word_count=100,
        agent_transcript_path="",
    )
    assert v1 == "write"
    assert v2 == "write"


def test_classify_empty_subagent_returns_write():
    m = _load_hook_module()
    m._PHANTOM_DEDUP_CACHE.clear()
    # No identity => cannot dedup by key; must not silently drop.
    verdict, _ = m._classify_task_agent_phantom(
        subagent_type="",
        session_id="s4",
        result_word_count=3,
        agent_transcript_path="/tmp/nope-1461.jsonl",
    )
    assert verdict == "write"


# ---------------------------------------------------------------------------
# Integration tests: full hook subprocess
# ---------------------------------------------------------------------------


def _run_hook(hook_input: dict, tmpdir: str, env_overrides: dict = None):
    """Invoke the hook as a subprocess and return the JSONL entries written."""
    env = os.environ.copy()
    env["ACTIVITY_LOGGING"] = "true"
    env["CLAUDE_SESSION_ID"] = hook_input.get("session_id", "s-int")
    if env_overrides:
        env.update(env_overrides)
    result = subprocess.run(
        [sys.executable, str(HOOK_PATH)],
        input=json.dumps(hook_input),
        text=True,
        capture_output=True,
        env=env,
        cwd=tmpdir,
    )
    assert result.returncode == 0, f"hook failed: {result.stderr}"
    log_files = list((Path(tmpdir) / ".claude" / "logs" / "activity").glob("*.jsonl"))
    if not log_files:
        return []
    entries = []
    for lf in log_files:
        with open(lf) as f:
            entries.extend(json.loads(line) for line in f if line.strip())
    # Heartbeat entries are ambient logger-health signals unrelated to the
    # dedup gate under test. Filter them out so the assertions below focus on
    # the PostToolUse write path.
    return [e for e in entries if e.get("hook") != "Heartbeat"]


def _task_post_tool_use_payload(
    session_id: str,
    subagent_type: str,
    word_count_result_text: str,
    transcript_path: str = "",
):
    """Build a PostToolUse hook input for a Task tool invocation."""
    return {
        "hook_event_name": "PostToolUse",
        "session_id": session_id,
        "tool_name": "Task",
        "tool_input": {
            "description": "test dispatch",
            "subagent_type": subagent_type,
            "prompt": "do the thing",
        },
        "tool_output": {
            "content": [{"type": "text", "text": word_count_result_text}],
            "agent_transcript_path": transcript_path,
        },
    }


def test_integration_phantom_task_writes_audit_entry_only():
    """Full hook subprocess: phantom Task write becomes audit entry, not normal entry."""
    with tempfile.TemporaryDirectory() as tmpdir:
        (Path(tmpdir) / ".claude").mkdir()
        payload = _task_post_tool_use_payload(
            session_id="int-s1",
            subagent_type="implementer",
            word_count_result_text="tiny",  # 1 word
            transcript_path="/tmp/definitely-not-here-1461-int.jsonl",
        )
        entries = _run_hook(payload, tmpdir)
        assert len(entries) == 1
        e = entries[0]
        # Must NOT be the normal PostToolUse entry with real tool info.
        # Must carry the phantom_verdict marker instead.
        assert e.get("phantom_verdict") == "phantom_skip"
        assert e.get("subagent_type_flag", "").startswith("__phantom_skip__:")


def test_integration_real_task_writes_normal_entry():
    with tempfile.TemporaryDirectory() as tmpdir:
        (Path(tmpdir) / ".claude").mkdir()
        # 30-word "output" clears the low-wc gate; no transcript path.
        payload = _task_post_tool_use_payload(
            session_id="int-s2",
            subagent_type="planner",
            word_count_result_text=" ".join(["word"] * 30),
        )
        entries = _run_hook(payload, tmpdir)
        assert len(entries) == 1
        e = entries[0]
        assert "phantom_verdict" not in e
        assert e["tool"] == "Task"
        assert e.get("input_summary", {}).get("subagent_type") == "planner"


def test_integration_debug_mode_bypasses_dedup():
    """Debug logging must retain the raw payload — dedup gate is disabled."""
    with tempfile.TemporaryDirectory() as tmpdir:
        (Path(tmpdir) / ".claude").mkdir()
        payload = _task_post_tool_use_payload(
            session_id="int-s3",
            subagent_type="implementer",
            word_count_result_text="tiny",
            transcript_path="/tmp/nope-1461-int-debug.jsonl",
        )
        entries = _run_hook(payload, tmpdir, env_overrides={"ACTIVITY_LOGGING": "debug"})
        assert len(entries) == 1
        e = entries[0]
        # Debug entries carry the raw tool_output; no phantom_verdict field.
        assert "phantom_verdict" not in e
        assert e.get("debug") is True


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-v"]))
