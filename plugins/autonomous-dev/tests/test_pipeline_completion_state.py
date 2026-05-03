"""Tests for pipeline_completion_state.resolve_session_id() — Issue #904."""
import json
import os
import sys
import time
from pathlib import Path

import pytest

_HERE = Path(__file__).resolve()
_LIB = _HERE.parents[1] / "lib"
if str(_LIB) not in sys.path:
    sys.path.insert(0, str(_LIB))

import pipeline_completion_state as pcs


class TestResolveSessionId:
    def test_env_var_takes_precedence(self, monkeypatch, tmp_path):
        monkeypatch.setenv("CLAUDE_SESSION_ID", "abc-123")
        sentinel = tmp_path / "sentinel.json"
        sentinel.write_text(json.dumps({"session_id": "from-sentinel"}))
        monkeypatch.setattr(pcs, "_IMPLEMENT_STATE_SENTINEL", sentinel)
        assert pcs.resolve_session_id() == "abc-123"

    def test_falls_back_to_sentinel_when_env_unset(self, monkeypatch, tmp_path):
        monkeypatch.delenv("CLAUDE_SESSION_ID", raising=False)
        sentinel = tmp_path / "sentinel.json"
        sentinel.write_text(json.dumps({"session_id": "from-sentinel"}))
        monkeypatch.setattr(pcs, "_IMPLEMENT_STATE_SENTINEL", sentinel)
        assert pcs.resolve_session_id() == "from-sentinel"

    def test_ignores_stale_sentinel(self, monkeypatch, tmp_path):
        monkeypatch.delenv("CLAUDE_SESSION_ID", raising=False)
        sentinel = tmp_path / "sentinel.json"
        sentinel.write_text(json.dumps({"session_id": "stale-id"}))
        old = time.time() - (pcs._SESSION_SENTINEL_TTL_SECONDS + 60)
        os.utime(sentinel, (old, old))
        monkeypatch.setattr(pcs, "_IMPLEMENT_STATE_SENTINEL", sentinel)
        assert pcs.resolve_session_id() == "unknown"

    def test_returns_unknown_with_no_signal(self, monkeypatch, tmp_path):
        monkeypatch.delenv("CLAUDE_SESSION_ID", raising=False)
        nonexistent = tmp_path / "no-sentinel.json"
        monkeypatch.setattr(pcs, "_IMPLEMENT_STATE_SENTINEL", nonexistent)
        assert pcs.resolve_session_id() == "unknown"

    def test_env_unknown_treated_as_no_signal(self, monkeypatch, tmp_path):
        monkeypatch.setenv("CLAUDE_SESSION_ID", "unknown")
        nonexistent = tmp_path / "no-sentinel.json"
        monkeypatch.setattr(pcs, "_IMPLEMENT_STATE_SENTINEL", nonexistent)
        assert pcs.resolve_session_id() == "unknown"
