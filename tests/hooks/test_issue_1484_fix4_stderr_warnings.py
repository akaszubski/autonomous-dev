#!/usr/bin/env python3
"""Fix-4 tests for Issue #1484 — loud, non-blocking sentinel warnings.

The silent ``except Exception: pass`` around the agent-dispatch sentinel
write/refresh (session_activity_logger) and clear (unified_session_tracker) is
replaced with a ``[agent_dispatch_sentinel] WARNING: ...`` line on stderr. The
hook MUST still exit 0 / return 0 (non-blocking).

These tests drive the hook ``main()`` in-process with the sentinel functions
monkeypatched to raise, then assert (a) the warning reaches stderr and (b) the
hook does not fail the tool call.

Issue: #1484
"""
from __future__ import annotations

import importlib
import io
import json
import sys
import uuid
from pathlib import Path

import pytest

_REPO = Path(__file__).resolve().parents[2]
_LIB = _REPO / "plugins" / "autonomous-dev" / "lib"
_HOOKS = _REPO / "plugins" / "autonomous-dev" / "hooks"
for _p in (str(_LIB), str(_HOOKS)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import agent_dispatch_sentinel as ads  # noqa: E402


def _feed_stdin(monkeypatch, payload: dict) -> None:
    monkeypatch.setattr(sys, "stdin", io.StringIO(json.dumps(payload)))


class TestIssue1484Fix4WriteWarning:
    def test_write_failure_warns_and_exits_zero(self, monkeypatch, capsys) -> None:
        sal = importlib.import_module("session_activity_logger")

        def _boom(*_a, **_k):
            raise RuntimeError("simulated write failure")

        monkeypatch.setattr(ads, "write", _boom)
        monkeypatch.setenv("ACTIVITY_LOGGING", "true")
        monkeypatch.setenv("CLAUDE_SESSION_ID", f"sess-{uuid.uuid4().hex}")
        _feed_stdin(
            monkeypatch,
            {
                "hook_event_name": "PreToolUse",
                "tool_name": "Task",
                "tool_input": {"subagent_type": "implementer", "description": "d"},
            },
        )
        with pytest.raises(SystemExit) as exc:
            sal.main()
        assert exc.value.code == 0
        err = capsys.readouterr().err
        assert "[agent_dispatch_sentinel] WARNING: write failed" in err


class TestIssue1484Fix4RefreshWarning:
    def test_refresh_failure_warns_and_exits_zero(
        self, monkeypatch, capsys, tmp_path
    ) -> None:
        sal = importlib.import_module("session_activity_logger")

        def _boom(*_a, **_k):
            raise RuntimeError("simulated refresh failure")

        monkeypatch.setattr(ads, "refresh", _boom)
        monkeypatch.setenv("ACTIVITY_LOGGING", "true")
        monkeypatch.setenv("CLAUDE_SESSION_ID", f"sess-{uuid.uuid4().hex}")
        # chdir to a hermetic root so any downstream JSONL write stays in tmp.
        (tmp_path / ".claude").mkdir()
        monkeypatch.chdir(tmp_path)
        _feed_stdin(
            monkeypatch,
            {
                "hook_event_name": "PostToolUse",
                "tool_name": "Read",
                "tool_input": {"file_path": "x"},
                "tool_output": {},
            },
        )
        with pytest.raises(SystemExit) as exc:
            sal.main()
        assert exc.value.code == 0
        err = capsys.readouterr().err
        assert "[agent_dispatch_sentinel] WARNING: refresh failed" in err


class TestIssue1484Fix4ClearWarning:
    def test_clear_failure_warns_and_returns_zero(
        self, monkeypatch, capsys, tmp_path
    ) -> None:
        ust = importlib.import_module("unified_session_tracker")

        def _boom(*_a, **_k):
            raise RuntimeError("simulated clear failure")

        monkeypatch.setattr(ads, "clear", _boom)
        # Hermetic marker root.
        (tmp_path / ".claude").mkdir()
        monkeypatch.chdir(tmp_path)
        # Unique session so the #1176 dedup marker claim succeeds (not a dup).
        uniq = uuid.uuid4().hex
        monkeypatch.setenv("CLAUDE_SESSION_ID", f"sess-{uniq}")
        _feed_stdin(
            monkeypatch,
            {
                "hook_event_name": "SubagentStop",
                "agent_type": "implementer",
                "last_assistant_message": "done",
                "agent_transcript_path": "",
                "session_id": f"sess-{uniq}",
            },
        )
        rc = ust.main()
        assert rc == 0
        err = capsys.readouterr().err
        assert "[agent_dispatch_sentinel] WARNING: clear failed" in err
