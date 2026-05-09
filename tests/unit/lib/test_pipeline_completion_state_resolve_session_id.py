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


def test_resolve_session_id_returns_unknown_when_sentinel_stale(
    monkeypatch, tmp_path
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
    monkeypatch, tmp_path
):
    """When env unset and sentinel file does not exist, return 'unknown'."""
    from pipeline_completion_state import resolve_session_id

    monkeypatch.delenv("CLAUDE_SESSION_ID", raising=False)
    missing = tmp_path / "does_not_exist.json"

    result = resolve_session_id(sentinel_path=str(missing))
    assert result == "unknown"


def test_resolve_session_id_returns_unknown_on_malformed_sentinel(
    monkeypatch, tmp_path
):
    """Malformed JSON in sentinel must NOT raise — return 'unknown'."""
    from pipeline_completion_state import resolve_session_id

    monkeypatch.delenv("CLAUDE_SESSION_ID", raising=False)
    sentinel = tmp_path / "implement_pipeline_state.json"
    sentinel.write_text("not valid json {{{")

    result = resolve_session_id(sentinel_path=str(sentinel))
    assert result == "unknown"
