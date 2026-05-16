"""
Tests for resolve_session_id() — Issue #1081.

Verifies the env -> sentinel -> "unknown" fallback chain that
commands/implement.md STEP 0 / STEP 2 / Pre-Dispatch Ordering Protocol
all rely on but which is not currently exported from
pipeline_completion_state.py (the spec/code drift bug).

Today (before fix): import fails with ImportError.
After fix: all four scenarios below pass.

Issue: #1081
"""

import json
import os
import sys
import time
from datetime import datetime
from pathlib import Path

import pytest

LIB_DIR = Path(__file__).resolve().parents[3] / "plugins" / "autonomous-dev" / "lib"
sys.path.insert(0, str(LIB_DIR))


def test_resolve_session_id_is_importable():
    """The function MUST be importable from pipeline_completion_state.

    This is the load-bearing assertion: commands/implement.md embeds
    `from pipeline_completion_state import resolve_session_id` at STEP 0
    and STEP 2. Today this raises ImportError on a fresh checkout.
    """
    from pipeline_completion_state import resolve_session_id  # noqa: F401

    assert callable(resolve_session_id)


def test_resolve_session_id_returns_env_var_when_set(monkeypatch):
    """When CLAUDE_SESSION_ID env var is set, return it verbatim."""
    from pipeline_completion_state import resolve_session_id

    monkeypatch.setenv("CLAUDE_SESSION_ID", "abc123-real-session")
    assert resolve_session_id() == "abc123-real-session"


def test_resolve_session_id_falls_back_to_sentinel_when_env_unset(
    monkeypatch, tmp_path
):
    """When env unset and sentinel file is fresh, return sentinel session_id."""
    from pipeline_completion_state import resolve_session_id

    monkeypatch.delenv("CLAUDE_SESSION_ID", raising=False)
    sentinel = tmp_path / "implement_pipeline_state.json"
    sentinel.write_text(json.dumps({"session_id": "xyz789-from-sentinel"}))

    result = resolve_session_id(sentinel_path=str(sentinel))
    assert result == "xyz789-from-sentinel"


@pytest.fixture
def disable_activity_log(monkeypatch):
    """Force the activity-log fallback (#1093) to return None.

    Used by tests that assert the legacy "unknown" return — they MUST NOT
    accidentally pick up a real or leftover activity log via ``Path.cwd()``
    ancestor walk. Without this fixture the tests would be flaky across
    environments (test pollution from sibling tmp_path fixtures, etc.).
    """
    import pipeline_completion_state as pcs

    monkeypatch.setattr(
        pcs, "_resolve_session_id_from_activity_log", lambda *a, **kw: None
    )


def test_resolve_session_id_returns_unknown_when_sentinel_stale(
    monkeypatch, tmp_path, disable_activity_log
):
    """When env unset and sentinel file mtime > max_age_seconds old, return 'unknown'."""
    from pipeline_completion_state import resolve_session_id

    monkeypatch.delenv("CLAUDE_SESSION_ID", raising=False)
    sentinel = tmp_path / "implement_pipeline_state.json"
    sentinel.write_text(json.dumps({"session_id": "stale-session"}))
    # Force mtime far in the past (2 hours ago).
    old_time = time.time() - 7200
    os.utime(sentinel, (old_time, old_time))

    result = resolve_session_id(
        sentinel_path=str(sentinel), max_age_seconds=3600
    )
    assert result == "unknown"


def test_resolve_session_id_returns_unknown_when_sentinel_missing(
    monkeypatch, tmp_path, disable_activity_log
):
    """When env unset and sentinel file does not exist, return 'unknown'."""
    from pipeline_completion_state import resolve_session_id

    monkeypatch.delenv("CLAUDE_SESSION_ID", raising=False)
    missing = tmp_path / "does_not_exist.json"

    result = resolve_session_id(sentinel_path=str(missing))
    assert result == "unknown"


def test_resolve_session_id_returns_unknown_on_malformed_sentinel(
    monkeypatch, tmp_path, disable_activity_log
):
    """Malformed JSON in sentinel must NOT raise — return 'unknown'."""
    from pipeline_completion_state import resolve_session_id

    monkeypatch.delenv("CLAUDE_SESSION_ID", raising=False)
    sentinel = tmp_path / "implement_pipeline_state.json"
    sentinel.write_text("not valid json {{{")

    result = resolve_session_id(sentinel_path=str(sentinel))
    assert result == "unknown"


# =============================================================================
# Issue #1093 — activity-log fallback regression tests.
#
# Bug: resolve_session_id() returned "unknown" from Bash subprocess context
# because the chain stopped at sentinel="unknown" / sentinel-missing and never
# consulted the activity log (which DOES have the real session_id thanks to
# session_activity_logger.py PreToolUse hooks).
#
# Fix: add a 4-step fallback chain — env -> sentinel -> activity log -> unknown.
# =============================================================================


def _write_activity_log(log_dir: Path, today: str, entries: list[dict]) -> Path:
    """Helper: build a synthetic activity log JSONL file under log_dir."""
    log_dir.mkdir(parents=True, exist_ok=True)
    log_file = log_dir / f"{today}.jsonl"
    log_file.write_text("\n".join(json.dumps(e) for e in entries) + "\n")
    return log_file


def test_resolve_session_id_activity_log_fallback(monkeypatch, tmp_path):
    """Issue #1093: env unset + sentinel has 'unknown' + activity log has real id
    → return the real id from the log.

    This is the load-bearing regression: in Bash subprocess context the env var
    is empty and the coordinator-written sentinel says 'unknown', but the
    activity log (written by PreToolUse/PostToolUse hooks that see the real
    session_id from stdin) carries the truth.
    """
    from pipeline_completion_state import resolve_session_id

    monkeypatch.delenv("CLAUDE_SESSION_ID", raising=False)
    monkeypatch.chdir(tmp_path)

    # Sentinel with stale "unknown" placeholder (boot-time write).
    sentinel = tmp_path / "implement_pipeline_state.json"
    sentinel.write_text(json.dumps({"session_id": "unknown"}))

    # Activity log under tmp_path/.claude/logs/activity/{today}.jsonl
    today = datetime.now().strftime("%Y-%m-%d")
    log_dir = tmp_path / ".claude" / "logs" / "activity"
    real_sid = "0df986e1-81ba-4caa-a524-dfa559f5d2bb"
    _write_activity_log(
        log_dir,
        today,
        [
            {"timestamp": "2026-05-17T00:00:00Z", "hook": "PreToolUse",
             "session_id": "unknown"},
            {"timestamp": "2026-05-17T00:00:01Z", "hook": "PreToolUse",
             "session_id": real_sid},
            {"timestamp": "2026-05-17T00:00:02Z", "hook": "PostToolUse",
             "session_id": real_sid},
        ],
    )

    result = resolve_session_id(sentinel_path=str(sentinel))
    assert result == real_sid


def test_resolve_session_id_activity_log_missing(monkeypatch, tmp_path):
    """Issue #1093: env unset + sentinel 'unknown' + log file MISSING → 'unknown'.

    The activity log fallback must return None (and the chain must continue
    to step 4) when today's log file does not exist.
    """
    from pipeline_completion_state import resolve_session_id

    monkeypatch.delenv("CLAUDE_SESSION_ID", raising=False)
    monkeypatch.chdir(tmp_path)

    sentinel = tmp_path / "implement_pipeline_state.json"
    sentinel.write_text(json.dumps({"session_id": "unknown"}))

    # Create the .claude/logs/activity dir but NO file for today.
    (tmp_path / ".claude" / "logs" / "activity").mkdir(parents=True)

    result = resolve_session_id(sentinel_path=str(sentinel))
    assert result == "unknown"


def test_resolve_session_id_activity_log_only_unknown_entries(
    monkeypatch, tmp_path
):
    """Issue #1093: env unset + sentinel 'unknown' + log has ONLY 'unknown'
    entries → returns 'unknown'.

    The scan must reject 'unknown' entries (they are not real session ids)
    and fall through to step 4.
    """
    from pipeline_completion_state import resolve_session_id

    monkeypatch.delenv("CLAUDE_SESSION_ID", raising=False)
    monkeypatch.chdir(tmp_path)

    sentinel = tmp_path / "implement_pipeline_state.json"
    sentinel.write_text(json.dumps({"session_id": "unknown"}))

    today = datetime.now().strftime("%Y-%m-%d")
    log_dir = tmp_path / ".claude" / "logs" / "activity"
    _write_activity_log(
        log_dir,
        today,
        [
            {"hook": "PreToolUse", "session_id": "unknown"},
            {"hook": "PreToolUse", "session_id": ""},
            {"hook": "PreToolUse", "session_id": "unknown"},
        ],
    )

    result = resolve_session_id(sentinel_path=str(sentinel))
    assert result == "unknown"


def test_resolve_session_id_activity_log_corrupt_json(monkeypatch, tmp_path):
    """Issue #1093: log with a mix of valid + corrupt JSON lines → scan
    skips bad lines and still returns the most recent real id.
    """
    from pipeline_completion_state import resolve_session_id

    monkeypatch.delenv("CLAUDE_SESSION_ID", raising=False)
    monkeypatch.chdir(tmp_path)

    sentinel = tmp_path / "implement_pipeline_state.json"
    sentinel.write_text(json.dumps({"session_id": "unknown"}))

    today = datetime.now().strftime("%Y-%m-%d")
    log_dir = tmp_path / ".claude" / "logs" / "activity"
    log_dir.mkdir(parents=True, exist_ok=True)
    log_file = log_dir / f"{today}.jsonl"
    real_sid = "abcdef12-3456-7890-abcd-ef1234567890"
    # Hand-craft mixed content: one corrupt line, one valid older entry,
    # one corrupt line, one valid newer entry (which should win).
    log_file.write_text(
        '{"this is not valid json\n'
        + json.dumps({"hook": "PreToolUse", "session_id": "old-id"})
        + "\n"
        + "garbage line {{{\n"
        + json.dumps({"hook": "PreToolUse", "session_id": real_sid})
        + "\n"
    )

    result = resolve_session_id(sentinel_path=str(sentinel))
    assert result == real_sid


def test_resolve_session_id_activity_log_fallback_prefers_newest(
    monkeypatch, tmp_path
):
    """Issue #1093: when multiple real session ids appear, the MOST RECENT
    (last in scan order) wins. Newest entries are at the end of the
    append-only log.
    """
    from pipeline_completion_state import resolve_session_id

    monkeypatch.delenv("CLAUDE_SESSION_ID", raising=False)
    monkeypatch.chdir(tmp_path)

    sentinel = tmp_path / "implement_pipeline_state.json"
    sentinel.write_text(json.dumps({"session_id": "unknown"}))

    today = datetime.now().strftime("%Y-%m-%d")
    log_dir = tmp_path / ".claude" / "logs" / "activity"
    older = "11111111-1111-1111-1111-111111111111"
    newer = "22222222-2222-2222-2222-222222222222"
    _write_activity_log(
        log_dir,
        today,
        [
            {"hook": "PreToolUse", "session_id": older},
            {"hook": "PreToolUse", "session_id": older},
            {"hook": "PreToolUse", "session_id": newer},
        ],
    )

    result = resolve_session_id(sentinel_path=str(sentinel))
    assert result == newer
