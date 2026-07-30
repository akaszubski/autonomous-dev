#!/usr/bin/env python3
"""Regression tests for Issue #1396 — SubagentStop heartbeat-drop + transcript
agent-type resolver in ``unified_session_tracker``.

Claude Code emits SubagentStop for internal/tool-level firings that carry NO
usable identity: empty ``agent_type``, zero duration, no #1087 PreToolUse
cache hit, and no transcript-resolved identity (~95 of ~113 events per run,
Anthropic #27423). Fix #1396 adds:

  * ``_resolve_agent_type_from_transcript()`` — best-effort recovery of the
    agent identity from the subagent transcript's early JSONL entries. Runs
    AFTER the #1087 cache and BEFORE the 'unknown' fallback.
  * a heartbeat-drop — computed AFTER duration_ms and BEFORE the #1414
    phantom-dedup block, so a dropped event never perturbs
    ``_PHANTOM_DEDUP_CACHE``.

CRITICAL guard (plan-critic mandate): the drop must ONLY ever remove true
zero-identity + zero-duration + no-cache noise. A genuine foreground agent
racing ahead of its PreToolUse cache write (COLD cache) must NOT be dropped
when it has EITHER a resolvable transcript identity OR a non-zero duration.

Background agents (``run_in_background=true``) never fire SubagentStop
(Anthropic #25147) so they are intentionally out of scope here.
"""

import glob
import json
import os
import sys
import uuid
from pathlib import Path
from unittest.mock import MagicMock, patch

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

import unified_session_tracker  # noqa: E402


@pytest.fixture(autouse=True)
def _clear_subagent_stop_markers():
    """Remove /tmp/subagent_stop_seen_*.marker files left by prior runs (#1184/#1176)."""
    def _sweep():
        for marker in glob.glob("/tmp/subagent_stop_seen_*.marker"):
            try:
                os.unlink(marker)
            except OSError:
                pass
    _sweep()
    unified_session_tracker._PHANTOM_DEDUP_CACHE.clear()
    yield
    _sweep()
    unified_session_tracker._PHANTOM_DEDUP_CACHE.clear()


@pytest.fixture
def transcript_home(tmp_path_factory):
    """A transcript directory UNDER ~/.claude (required by _validate_transcript_path).

    _validate_transcript_path only accepts paths inside ~/.claude, so a bare
    tmp_path will be rejected. We create a unique subdir under the real
    ~/.claude and clean it up afterwards.
    """
    base = Path.home() / ".claude" / f"test_1396_{uuid.uuid4().hex[:12]}"
    base.mkdir(parents=True, exist_ok=True)
    yield base
    # Best-effort cleanup
    for child in base.glob("*"):
        try:
            child.unlink()
        except OSError:
            pass
    try:
        base.rmdir()
    except OSError:
        pass


def _run_main(stdin_payload: dict, *, completion_calls: list, duration_ms: int,
              cache_return=None):
    """Drive unified_session_tracker.main() with controlled dependencies.

    Args:
        stdin_payload: The SubagentStop hook JSON payload.
        completion_calls: List that captures record_agent_completion kwargs.
        duration_ms: The value _compute_duration_ms() should return (steers the
            heartbeat-drop's ``duration_ms == 0`` predicate deterministically).
        cache_return: What _pop_cached_subagent_invocation returns (None = cold
            cache / no #1087 hit).

    Returns:
        The int return code from main().
    """
    def _mock_record(**kwargs):
        completion_calls.append(kwargs)

    with patch("sys.stdin.read", return_value=json.dumps(stdin_payload)), \
         patch("pipeline_completion_state.record_agent_completion", _mock_record), \
         patch.object(unified_session_tracker, "_write_jsonl_entry", MagicMock()), \
         patch.object(unified_session_tracker, "track_basic_session", MagicMock()), \
         patch.object(unified_session_tracker, "track_pipeline_completion", MagicMock()), \
         patch.object(unified_session_tracker, "_pop_cached_subagent_invocation",
                      return_value=cache_return), \
         patch.object(unified_session_tracker, "_compute_duration_ms",
                      return_value=duration_ms):
        return unified_session_tracker.main()


# ---------------------------------------------------------------------------
# Heartbeat drop
# ---------------------------------------------------------------------------

def test_heartbeat_drop_zero_identity_zero_duration_no_cache_not_recorded():
    """Empty agent_type + duration 0 + no cache + no transcript → dropped (not recorded)."""
    completion_calls: list = []
    payload = {
        "hook_event_name": "SubagentStop",
        "agent_type": "",
        "session_id": f"sess-1396-drop-{uuid.uuid4().hex[:10]}",
        "agent_transcript_path": "",
        "last_assistant_message": "",
    }
    rc = _run_main(payload, completion_calls=completion_calls, duration_ms=0, cache_return=None)
    assert rc == 0, "#1396: heartbeat-drop path must return 0 (non-blocking hook)"
    assert completion_calls == [], (
        "#1396: a zero-identity/zero-duration/no-cache heartbeat must NOT be "
        f"recorded, but record_agent_completion was called: {completion_calls}"
    )


def test_unknown_identity_zero_duration_no_cache_dropped():
    """Literal 'unknown' agent_type behaves the same as empty for the drop."""
    completion_calls: list = []
    payload = {
        "hook_event_name": "SubagentStop",
        "agent_type": "unknown",
        "session_id": f"sess-1396-unk-{uuid.uuid4().hex[:10]}",
        "agent_transcript_path": "",
        "last_assistant_message": "",
    }
    rc = _run_main(payload, completion_calls=completion_calls, duration_ms=0, cache_return=None)
    assert rc == 0
    assert completion_calls == [], (
        "#1396: 'unknown' identity with zero duration and no cache must be dropped"
    )


# ---------------------------------------------------------------------------
# Cache-starvation false-drop guard (plan-critic mandate)
# ---------------------------------------------------------------------------

def test_cold_cache_but_nonzero_duration_is_not_dropped():
    """COLD #1087 cache + non-zero duration + empty identity → NOT dropped.

    Proves the drop never removes a genuine foreground agent that raced ahead
    of its PreToolUse cache write when it still has a real duration signal.
    """
    completion_calls: list = []
    payload = {
        "hook_event_name": "SubagentStop",
        "agent_type": "",
        "session_id": f"sess-1396-dur-{uuid.uuid4().hex[:10]}",
        "agent_transcript_path": "",
        "last_assistant_message": "real work output",
    }
    rc = _run_main(payload, completion_calls=completion_calls, duration_ms=45000, cache_return=None)
    assert rc == 0
    assert len(completion_calls) == 1, (
        "#1396: an event with a non-zero duration must NOT be dropped even with a "
        f"cold cache and empty identity, calls: {completion_calls}"
    )
    # Falls through to the 'unknown' fallback (no identity recoverable here).
    assert completion_calls[0]["agent_type"] in ("", "unknown")


def test_cold_cache_but_transcript_identity_is_not_dropped(transcript_home):
    """COLD #1087 cache + resolvable transcript identity + zero duration → NOT dropped.

    Proves the transcript resolver rescues a genuine foreground agent whose
    cache write has not landed yet, and its recovered identity is recorded.
    """
    completion_calls: list = []
    transcript = transcript_home / "cold_cache_transcript.jsonl"
    transcript.write_text(
        json.dumps({"agent_type": "reviewer", "role": "system"}) + "\n"
        + json.dumps({"type": "message", "content": "..."}) + "\n"
    )
    payload = {
        "hook_event_name": "SubagentStop",
        "agent_type": "",
        "session_id": f"sess-1396-tx-{uuid.uuid4().hex[:10]}",
        "agent_transcript_path": str(transcript),
        "last_assistant_message": "reviewer output",
    }
    rc = _run_main(payload, completion_calls=completion_calls, duration_ms=0, cache_return=None)
    assert rc == 0
    assert len(completion_calls) == 1, (
        "#1396: an event with a resolvable transcript identity must NOT be dropped "
        f"even at zero duration with a cold cache, calls: {completion_calls}"
    )
    assert completion_calls[0]["agent_type"] == "reviewer", (
        "#1396: recovered transcript identity must be recorded, got "
        f"{completion_calls[0]['agent_type']!r}"
    )


def test_cold_cache_zero_duration_no_transcript_but_substantive_output_not_dropped():
    """INTERSECTION guard (remediation): cold cache + duration 0 + unresolvable
    transcript + SUBSTANTIVE last_assistant_message → NOT dropped (recorded).

    This is the exact false-negative Fix C could reintroduce: a genuine
    foreground agent whose #1087 PreToolUse cache write has not landed (cache=None
    → cache_hit False), whose duration computes to 0 (native Task, cold cache),
    AND whose transcript is absent/unresolvable (empty path → resolver returns
    "") would hit all three prior survival misses. Without the 4th survival
    signal (substantive output) it would be silently dropped, discarding a real
    completion and blocking a legit commit via the #802 completeness gate.
    """
    completion_calls: list = []
    substantive = (
        "Implementation complete. All twelve regression tests pass and the "
        "evidence manifest is included below with per-file verification signals."
    )
    payload = {
        "hook_event_name": "SubagentStop",
        "agent_type": "",  # zero identity from payload
        "session_id": f"sess-1396-intersect-{uuid.uuid4().hex[:10]}",
        "agent_transcript_path": "",  # no transcript → resolver returns ""
        "last_assistant_message": substantive,
    }
    # cache_return=None → cold cache (cache_hit False); duration_ms=0 → zero duration.
    rc = _run_main(
        payload, completion_calls=completion_calls, duration_ms=0, cache_return=None
    )
    assert rc == 0
    assert len(completion_calls) == 1, (
        "#1396 remediation: an event at the cold-cache/zero-duration/no-transcript "
        "intersection with a SUBSTANTIVE last_assistant_message must NOT be dropped "
        f"(it is a genuine foreground completion), calls: {completion_calls}"
    )
    # Identity is unrecoverable here, so it falls through to the 'unknown' record.
    assert completion_calls[0]["agent_type"] in ("", "unknown")


def test_intersection_trivial_output_still_dropped():
    """A NON-substantive (below-threshold) output at the same intersection is
    still dropped — the 4th signal filters trivial heartbeat noise, it does not
    blanket-preserve every non-empty string."""
    completion_calls: list = []
    payload = {
        "hook_event_name": "SubagentStop",
        "agent_type": "",
        "session_id": f"sess-1396-trivial-{uuid.uuid4().hex[:10]}",
        "agent_transcript_path": "",
        "last_assistant_message": "ok",  # 1 word, below HEARTBEAT_MIN_OUTPUT_WORDS
    }
    rc = _run_main(
        payload, completion_calls=completion_calls, duration_ms=0, cache_return=None
    )
    assert rc == 0
    assert completion_calls == [], (
        "#1396 remediation: a trivial below-threshold output at the noise "
        f"intersection must still be dropped, calls: {completion_calls}"
    )


# ---------------------------------------------------------------------------
# Transcript resolver — direct unit coverage
# ---------------------------------------------------------------------------

def test_resolver_recovers_top_level_identity(transcript_home):
    """Resolver reads a top-level agent_type from the transcript's early entries."""
    transcript = transcript_home / "top_level.jsonl"
    transcript.write_text(json.dumps({"agent_type": "security-auditor"}) + "\n")
    assert (
        unified_session_tracker._resolve_agent_type_from_transcript(str(transcript))
        == "security-auditor"
    )


def test_resolver_recovers_nested_identity(transcript_home):
    """Resolver reads a nested session_meta.name when no top-level field exists."""
    transcript = transcript_home / "nested.jsonl"
    transcript.write_text(
        json.dumps({"type": "start", "session_meta": {"name": "doc-master"}}) + "\n"
    )
    assert (
        unified_session_tracker._resolve_agent_type_from_transcript(str(transcript))
        == "doc-master"
    )


def test_resolver_returns_empty_on_missing_file(transcript_home):
    """A non-existent (but path-valid) transcript → '' (graceful)."""
    missing = transcript_home / "does_not_exist.jsonl"
    assert unified_session_tracker._resolve_agent_type_from_transcript(str(missing)) == ""


def test_resolver_returns_empty_on_malformed_lines(transcript_home):
    """Malformed / identity-less JSONL → '' (graceful, no crash)."""
    transcript = transcript_home / "malformed.jsonl"
    transcript.write_text("{not json at all\n" + json.dumps({"type": "message"}) + "\n")
    assert unified_session_tracker._resolve_agent_type_from_transcript(str(transcript)) == ""


def test_resolver_rejects_path_outside_claude_home(tmp_path):
    """A transcript path OUTSIDE ~/.claude is rejected by validation → ''."""
    outside = tmp_path / "outside.jsonl"
    outside.write_text(json.dumps({"agent_type": "planner"}) + "\n")
    assert unified_session_tracker._resolve_agent_type_from_transcript(str(outside)) == ""


def test_resolver_empty_path_returns_empty():
    """Empty path → '' without touching the filesystem."""
    assert unified_session_tracker._resolve_agent_type_from_transcript("") == ""


# ---------------------------------------------------------------------------
# Resolver failure inside main() falls through gracefully
# ---------------------------------------------------------------------------

def test_resolver_failure_nonzero_duration_falls_through_to_unknown():
    """Malformed/rejected transcript + non-zero duration → records as 'unknown', no crash."""
    completion_calls: list = []
    payload = {
        "hook_event_name": "SubagentStop",
        "agent_type": "",
        "session_id": f"sess-1396-fall-{uuid.uuid4().hex[:10]}",
        # Path outside ~/.claude → validation rejects → resolver returns ""
        "agent_transcript_path": "/tmp/not-in-claude-home-1396.jsonl",
        "last_assistant_message": "some output",
    }
    rc = _run_main(payload, completion_calls=completion_calls, duration_ms=30000, cache_return=None)
    assert rc == 0
    assert len(completion_calls) == 1, (
        "#1396: non-zero duration event must still record even when the resolver "
        f"fails, calls: {completion_calls}"
    )
    assert completion_calls[0]["agent_type"] in ("", "unknown")


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-v"]))
