"""Integration tests for the coordinator session-ID fallback chain.

Covers Issue #904 subclass #898: coordinator subshells that lose
CLAUDE_SESSION_ID must recover it from /tmp/implement_pipeline_state.json.

The chain under test is `env → sentinel → 'unknown'`. The reference
implementation is the inline helper injected at three call sites in
`plugins/autonomous-dev/commands/implement.md`. The integration tests
reconstruct that helper as a subprocess script and verify behavior
under each branch.
"""

import json
import os
import subprocess
import sys
import time
from pathlib import Path

import pytest


# Canonical helper — MUST stay byte-for-byte in sync with the three
# fallback-chain blocks in `commands/implement.md`. If those change,
# update this literal (and the test proves the contract).
RESOLVER_SCRIPT = """
import sys, os, json, time

def _resolve_session_id():
    sid = os.environ.get('CLAUDE_SESSION_ID', '').strip()
    if sid and sid != 'unknown':
        return sid
    sentinel = '/tmp/implement_pipeline_state.json'
    try:
        if os.path.exists(sentinel):
            mtime = os.path.getmtime(sentinel)
            if time.time() - mtime < 3600:
                with open(sentinel) as _f:
                    _state = json.load(_f)
                _recovered = str(_state.get('session_id', '')).strip()
                if _recovered and _recovered != 'unknown':
                    return _recovered
    except (OSError, ValueError, json.JSONDecodeError):
        pass
    return 'unknown'

print(_resolve_session_id())
"""


@pytest.fixture()
def sentinel_path(tmp_path, monkeypatch):
    """Redirect the sentinel path to a test-controlled location.

    The helper hard-codes ``/tmp/implement_pipeline_state.json``. We can't
    monkeypatch a subprocess, so we manage the real path but restore any
    pre-existing sentinel after the test.
    """
    real_path = Path("/tmp/implement_pipeline_state.json")
    backup = None
    if real_path.exists():
        backup = real_path.read_bytes()
        real_path.unlink()
    yield real_path
    # Cleanup: remove the test sentinel and restore any original.
    try:
        if real_path.exists():
            real_path.unlink()
    except OSError:
        pass
    if backup is not None:
        real_path.write_bytes(backup)


def _run_resolver(env: dict) -> str:
    """Run the resolver in a subprocess with a given environment."""
    result = subprocess.run(
        [sys.executable, "-c", RESOLVER_SCRIPT],
        env=env,
        capture_output=True,
        text=True,
        timeout=10,
    )
    assert result.returncode == 0, f"resolver crashed: {result.stderr}"
    return result.stdout.strip()


class TestFallbackChain:
    """Issue #898: subshell session-id recovery contract."""

    def test_env_var_primary_source(self, sentinel_path):
        """When env var is set and meaningful, it wins over the sentinel."""
        # Write a DIFFERENT sentinel value so we can prove env wins.
        sentinel_path.write_text(json.dumps({"session_id": "from-sentinel"}))
        env = dict(os.environ)
        env["CLAUDE_SESSION_ID"] = "from-env"
        assert _run_resolver(env) == "from-env"

    def test_coordinator_subshell_reads_sentinel_when_env_unset(self, sentinel_path):
        """Issue #898: subshell with no env var falls through to sentinel."""
        sentinel_path.write_text(
            json.dumps({"session_id": "recovered-from-sentinel"})
        )
        env = {k: v for k, v in os.environ.items() if k != "CLAUDE_SESSION_ID"}
        # Explicitly set PATH so subprocess can find python.
        env.setdefault("PATH", os.environ.get("PATH", ""))
        assert _run_resolver(env) == "recovered-from-sentinel"

    def test_fallback_to_unknown_when_sentinel_missing(self, sentinel_path):
        """No env var, no sentinel → 'unknown' (compat)."""
        assert not sentinel_path.exists(), "precondition"
        env = {k: v for k, v in os.environ.items() if k != "CLAUDE_SESSION_ID"}
        env.setdefault("PATH", os.environ.get("PATH", ""))
        assert _run_resolver(env) == "unknown"

    def test_stale_sentinel_older_than_ttl_falls_through(self, sentinel_path):
        """Sentinel mtime > 3600s → 'unknown' fallback (avoids #875 bleed)."""
        sentinel_path.write_text(
            json.dumps({"session_id": "stale-session"})
        )
        # Backdate mtime past the TTL.
        stale_time = time.time() - 3700
        os.utime(sentinel_path, (stale_time, stale_time))

        env = {k: v for k, v in os.environ.items() if k != "CLAUDE_SESSION_ID"}
        env.setdefault("PATH", os.environ.get("PATH", ""))
        assert _run_resolver(env) == "unknown", (
            "Issue #875: a stale sentinel must NOT leak into a fresh pipeline."
        )

    def test_env_var_literal_unknown_triggers_fallback(self, sentinel_path):
        """CLAUDE_SESSION_ID=='unknown' is not meaningful — fall through."""
        sentinel_path.write_text(
            json.dumps({"session_id": "real-session"})
        )
        env = dict(os.environ)
        env["CLAUDE_SESSION_ID"] = "unknown"
        assert _run_resolver(env) == "real-session"

    def test_malformed_sentinel_falls_through_to_unknown(self, sentinel_path):
        """Invalid JSON in sentinel must NOT crash — returns 'unknown'."""
        sentinel_path.write_text("{{not valid json")
        env = {k: v for k, v in os.environ.items() if k != "CLAUDE_SESSION_ID"}
        env.setdefault("PATH", os.environ.get("PATH", ""))
        assert _run_resolver(env) == "unknown"
