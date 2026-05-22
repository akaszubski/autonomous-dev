"""
Regression tests for Issue #1051: Stale agent-deny file cleanup.

`_check_agent_denial()` previously returned None for stale (TTL-expired) and
session-mismatched deny files but did NOT unlink them. Files at
`/tmp/adev-agent-deny-{session_id}.json` persisted across pipeline runs and
session boundaries, requiring manual `rm` to unblock subsequent agent
invocations.

This module validates:

1. Stale deny files (timestamp older than AGENT_DENY_TTL) are deleted on read.
2. Session-mismatched deny files are deleted on read (orphans from prior sessions).
3. Fresh deny files (within TTL, matching session) are PRESERVED — they are
   still actionable signal.
4. Cleanup is fail-open: OSError from `os.unlink` is swallowed; the function
   still returns None.
5. The path-confinement guard is preserved — a `state_path` that escapes
   `AGENT_DENY_STATE_DIR` does NOT trigger unlink.

Date: 2026-05-21
Issue: #1051
"""

from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path

import pytest

# Add hook + lib dirs to path so we can import the module under test.
# This file lives at tests/regression/test_issue_1051_deny_ttl_cleanup.py
# so parents[2] = repo root.
HOOK_DIR = Path(__file__).resolve().parents[2] / "plugins" / "autonomous-dev" / "hooks"
LIB_DIR = Path(__file__).resolve().parents[2] / "plugins" / "autonomous-dev" / "lib"
sys.path.insert(0, str(HOOK_DIR))
sys.path.insert(0, str(LIB_DIR))

import unified_pre_tool as hook  # noqa: E402


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def clean_env(monkeypatch):
    """Reset relevant env vars for each test."""
    for key in [
        "SANDBOX_ENABLED",
        "PRE_TOOL_MCP_SECURITY",
        "PRE_TOOL_AGENT_AUTH",
        "PRE_TOOL_BATCH_PERMISSION",
        "MCP_AUTO_APPROVE",
        "ENFORCEMENT_LEVEL",
        "CLAUDE_AGENT_NAME",
        "PIPELINE_STATE_FILE",
    ]:
        monkeypatch.delenv(key, raising=False)


@pytest.fixture
def session_env(tmp_path, monkeypatch):
    """Point the hook at a temp dir and pin a known session id.

    Returns:
        Tuple of (session_id, deny_file_path) for use in tests.
    """
    sid = "test-session-1051"
    monkeypatch.setattr(hook, "_session_id", sid)
    monkeypatch.setattr(hook, "AGENT_DENY_STATE_DIR", str(tmp_path))
    deny_path = tmp_path / f"adev-agent-deny-{sid}.json"
    return sid, deny_path


def _write_deny_file(path: Path, *, agent_type: str, session_id: str, timestamp: float) -> None:
    """Write a deny state file directly (bypassing _record_agent_denial)."""
    path.write_text(
        json.dumps(
            {
                "agent_type": agent_type,
                "session_id": session_id,
                "timestamp": timestamp,
            }
        )
    )


# ---------------------------------------------------------------------------
# Test 1: Stale deny file (TTL-expired) is deleted
# ---------------------------------------------------------------------------


class TestIssue1051StaleDenyCleanup:
    """Regression tests for Issue #1051."""

    def test_stale_deny_file_is_deleted(self, session_env):
        """A deny file older than AGENT_DENY_TTL must be unlinked when read.

        This is the core failure mode in Issue #1051: stale state persisted
        and required manual `rm` to unblock agents.
        """
        sid, deny_path = session_env
        # Write a deny file with timestamp older than TTL
        stale_ts = time.time() - (hook.AGENT_DENY_TTL + 60)
        _write_deny_file(deny_path, agent_type="implementer", session_id=sid, timestamp=stale_ts)
        assert deny_path.exists(), "precondition: deny file should exist before check"

        result = hook._check_agent_denial()

        assert result is None, "stale deny must report no active denial"
        assert not deny_path.exists(), (
            f"Issue #1051 regression: stale deny file at {deny_path} was NOT cleaned up"
        )

    def test_session_mismatched_deny_file_is_deleted(self, session_env, tmp_path):
        """A deny file from a different session is orphaned — must be unlinked.

        The path is keyed on session_id, so a foreign session_id inside the
        file means the file is junk from a previous session that crashed
        before writing the matching record.
        """
        sid, deny_path = session_env
        # Write a deny file with a DIFFERENT session_id inside (fresh timestamp)
        _write_deny_file(
            deny_path,
            agent_type="implementer",
            session_id="some-OTHER-session-xyz",
            timestamp=time.time(),
        )
        assert deny_path.exists(), "precondition: deny file should exist before check"

        result = hook._check_agent_denial()

        assert result is None, "session-mismatched deny must report no active denial"
        assert not deny_path.exists(), (
            f"Issue #1051 regression: orphaned deny file at {deny_path} was NOT cleaned up"
        )

    def test_fresh_matching_deny_file_is_preserved(self, session_env):
        """A fresh deny file (within TTL, matching session) MUST survive.

        Fresh denies are active signal — they're what unblocks the gate.
        Deleting them on read would defeat the entire denial mechanism.
        """
        sid, deny_path = session_env
        _write_deny_file(
            deny_path,
            agent_type="implementer",
            session_id=sid,
            timestamp=time.time(),  # fresh
        )
        assert deny_path.exists(), "precondition"

        result = hook._check_agent_denial()

        assert result == "implementer", "fresh matching deny must return agent_type"
        assert deny_path.exists(), (
            "fresh matching deny file MUST NOT be deleted — it is still active signal"
        )

    def test_cleanup_failure_does_not_propagate(self, session_env, monkeypatch):
        """If os.unlink raises OSError, _check_agent_denial must still return None.

        Fail-open contract: a deny-file cleanup error must not block agents
        or surface a traceback. This protects against permission errors,
        races (file removed between exists() and unlink()), and read-only FS.
        """
        sid, deny_path = session_env
        stale_ts = time.time() - (hook.AGENT_DENY_TTL + 60)
        _write_deny_file(deny_path, agent_type="implementer", session_id=sid, timestamp=stale_ts)

        # Monkeypatch os.unlink on the hook module's `os` namespace to raise
        unlink_calls = {"count": 0}

        def _failing_unlink(path):
            unlink_calls["count"] += 1
            raise OSError("simulated unlink failure")

        monkeypatch.setattr(hook.os, "unlink", _failing_unlink)

        # Must not raise
        result = hook._check_agent_denial()

        assert result is None, "fail-open: stale deny still reports no active denial"
        assert unlink_calls["count"] >= 1, "unlink must have been attempted"

    def test_path_confinement_guard_preserved(self, session_env, monkeypatch, tmp_path):
        """Path-confinement check must still gate unlink for escaping paths.

        If the resolved state_path escapes AGENT_DENY_STATE_DIR, the function
        returns None WITHOUT calling unlink. This preserves the existing
        security guard (lines 3232-3235) against symlink-based path escapes.
        """
        sid, _deny_path = session_env

        # Construct a scenario where os.path.realpath would resolve to a path
        # OUTSIDE AGENT_DENY_STATE_DIR. We monkey-patch realpath to simulate
        # a symlink that escapes the base directory.
        escape_target = "/tmp/somewhere-else/adev-agent-deny-escape.json"
        base_dir = str(tmp_path)

        real_realpath = hook.os.path.realpath

        def _escaping_realpath(path):
            # The state_path resolves to an escape; the base resolves normally.
            if "adev-agent-deny-" in str(path):
                return escape_target
            return real_realpath(path)

        monkeypatch.setattr(hook.os.path, "realpath", _escaping_realpath)

        # Track whether os.unlink is called — it MUST NOT be for escaping paths
        unlink_calls = {"count": 0}
        real_unlink = hook.os.unlink

        def _tracking_unlink(path):
            unlink_calls["count"] += 1
            return real_unlink(path)

        monkeypatch.setattr(hook.os, "unlink", _tracking_unlink)

        result = hook._check_agent_denial()

        assert result is None, "escaping path must return None (path-confinement guard)"
        assert unlink_calls["count"] == 0, (
            "path-confinement violation: unlink must NOT be called when state_path "
            f"escapes AGENT_DENY_STATE_DIR (was called {unlink_calls['count']} times)"
        )
