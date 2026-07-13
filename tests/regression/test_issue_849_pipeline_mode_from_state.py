#!/usr/bin/env python3
"""Regression tests for Issue #849: Pipeline mode detection from state file.

Bug: _check_pipeline_agent_completions in unified_pre_tool.py read
PIPELINE_MODE from the environment variable with a default of "full".
Since hooks run as subprocesses, they never inherit the env var set by
the coordinator process. This caused fix-mode and light-mode pipelines
to be checked against full-mode agent requirements.

Fix: Fall back to _get_pipeline_mode_from_state() when the env var is
not set, which reads the mode from /tmp/implement_pipeline_state.json.

Issues: #849
"""

import json
import os
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
LIB_DIR = REPO_ROOT / "plugins" / "autonomous-dev" / "lib"
HOOK_DIR = REPO_ROOT / "plugins" / "autonomous-dev" / "hooks"
sys.path.insert(0, str(LIB_DIR))
sys.path.insert(0, str(HOOK_DIR))

import pipeline_completion_state as pcs
import unified_pre_tool


@pytest.fixture(autouse=True)
def clean_env(monkeypatch):
    """Remove pipeline env vars before each test."""
    monkeypatch.delenv("PIPELINE_MODE", raising=False)
    monkeypatch.delenv("PIPELINE_ISSUE_NUMBER", raising=False)
    monkeypatch.delenv("SKIP_AGENT_COMPLETENESS_GATE", raising=False)


@pytest.fixture
def session_id(tmp_path, monkeypatch):
    """Create a unique session and patch state file path to tmp."""
    sid = "test-regression-849"

    def _patched(s, *, run_id=None):
        import hashlib

        h = hashlib.sha256(s.encode()).hexdigest()[:8]
        return tmp_path / f"pipeline_agent_completions_{h}.json"

    monkeypatch.setattr(pcs, "_state_file_path", _patched)
    return sid


class TestPipelineModeFromStateFile:
    """Verify pipeline mode is read from state file when env var is absent."""

    def _record_agents(self, session_id: str, agents: set[str]) -> None:
        """Helper to record multiple agent completions."""
        for agent in agents:
            pcs.record_agent_completion(session_id, agent)

    def test_fix_mode_from_state_uses_fix_agents(self, session_id, tmp_path):
        """When env var is unset and state file says 'fix', fix-mode agents
        should be required -- NOT full-mode agents.

        This is the core regression test for #849. Before the fix,
        the hook would default to 'full' mode and require researchers
        and security-auditor, causing false blocks in fix pipelines.
        """
        # Record only fix-mode agents (no researchers, no security-auditor)
        fix_agents = {
            "implementer",
            "pytest-gate",
            "reviewer",
            "doc-master",
            "continuous-improvement-analyst",
        }
        self._record_agents(session_id, fix_agents)

        # Verify: using fix mode explicitly should pass
        passed, completed, missing = pcs.verify_pipeline_agent_completions(
            session_id, "fix"
        )
        assert passed is True, f"Fix-mode agents should pass fix-mode check. Missing: {missing}"
        assert missing == set()

        # Verify: using full mode with same agents should FAIL (missing researchers etc.)
        passed_full, _, missing_full = pcs.verify_pipeline_agent_completions(
            session_id, "full"
        )
        assert passed_full is False, "Fix-mode agents should NOT pass full-mode check"
        assert "researcher" in missing_full or "researcher-local" in missing_full

    def test_light_mode_from_state_uses_light_agents(self, session_id):
        """When env var is unset and state file says 'light', light-mode agents
        should be required.
        """
        light_agents = {
            "planner",
            "implementer",
            "pytest-gate",
            "doc-master",
            "continuous-improvement-analyst",
        }
        self._record_agents(session_id, light_agents)

        # Light mode should pass
        passed, completed, missing = pcs.verify_pipeline_agent_completions(
            session_id, "light"
        )
        assert passed is True, f"Light-mode agents should pass light-mode check. Missing: {missing}"
        assert missing == set()

        # Full mode with same agents should fail
        passed_full, _, missing_full = pcs.verify_pipeline_agent_completions(
            session_id, "full"
        )
        assert passed_full is False, "Light-mode agents should NOT pass full-mode check"

    def test_env_var_takes_precedence_over_state_file(self, session_id, monkeypatch):
        """When PIPELINE_MODE env var IS set, it should take precedence.

        This validates the env var path still works correctly for cases
        where the coordinator and hook share the same process.
        """
        # Record fix-mode agents
        fix_agents = {
            "implementer",
            "pytest-gate",
            "reviewer",
            "doc-master",
            "continuous-improvement-analyst",
        }
        self._record_agents(session_id, fix_agents)

        # With env var set to "fix", should pass
        passed, _, missing = pcs.verify_pipeline_agent_completions(
            session_id, "fix"
        )
        assert passed is True

    def test_default_to_full_when_neither_available(self, session_id):
        """When neither env var nor state file has mode, default to 'full'.

        This validates the fallback behavior: without any mode signal,
        the most restrictive (full) mode is assumed.
        """
        # Record only fix-mode agents (incomplete for full mode)
        fix_agents = {
            "implementer",
            "pytest-gate",
            "reviewer",
            "doc-master",
            "continuous-improvement-analyst",
        }
        self._record_agents(session_id, fix_agents)

        # With "full" mode (the default), these agents are insufficient
        passed, _, missing = pcs.verify_pipeline_agent_completions(
            session_id, "full"
        )
        assert passed is False, "Fix-mode agents should not satisfy full-mode requirements"
        assert len(missing) > 0


class TestHookPipelineModeReading:
    """Verify the hook file reads pipeline mode from state file."""

    def test_hook_uses_state_file_fallback(self):
        """unified_pre_tool.py must resolve pipeline mode via
        ``_get_pipeline_mode_from_state()`` and the helper itself must
        honor the ``PIPELINE_MODE`` env var.

        History:
          - Issue #849 introduced the ``env or helper`` pattern at call sites.
          - Issue #1173 moved the env-var read INSIDE the helper so all
            call sites benefit from the override uniformly (the previous
            asymmetry was the actual #849 bug class).
          - Issue #1177 removed the now-dead outer
            ``os.environ.get("PIPELINE_MODE") or ...`` short-circuit at
            both remaining call sites since the helper already honors it.

        Post-#1177 contract — both must hold:
          1. The hook calls ``_get_pipeline_mode_from_state()``.
          2. The helper itself reads ``PIPELINE_MODE`` (preserving the
             #849 override path).
        """
        hook_path = (
            REPO_ROOT / "plugins" / "autonomous-dev" / "hooks" / "unified_pre_tool.py"
        )
        assert hook_path.exists(), "unified_pre_tool.py must exist"
        source = hook_path.read_text()

        # (1) Hook still calls the resolver helper at least once.
        assert "_get_pipeline_mode_from_state()" in source, (
            "Hook must call _get_pipeline_mode_from_state() to resolve "
            "pipeline mode (Issue #849)."
        )

        # (2) The PIPELINE_MODE env-var override is preserved — but now
        # internalized in the helper (#1173). Without this, the #849
        # override path is gone entirely.
        assert 'os.getenv("PIPELINE_MODE"' in source or \
               'os.environ.get("PIPELINE_MODE"' in source, (
            "PIPELINE_MODE env-var read must remain somewhere in the "
            "hook source — #1173 moved it inside "
            "_get_pipeline_mode_from_state(), removing it entirely "
            "would break the #849 override contract."
        )

    def test_hook_does_not_default_to_full(self):
        """unified_pre_tool.py should NOT have a hardcoded 'full' default
        for PIPELINE_MODE in _check_pipeline_agent_completions.

        This verifies the bug pattern is not present.
        """
        hook_path = (
            REPO_ROOT / "plugins" / "autonomous-dev" / "hooks" / "unified_pre_tool.py"
        )
        source = hook_path.read_text()

        # The bug pattern: os.environ.get("PIPELINE_MODE", "full")
        # This should NOT appear in the agent completions section
        # Find the _check_pipeline_agent_completions function
        fn_start = source.find("def _check_pipeline_agent_completions")
        assert fn_start != -1, "Function _check_pipeline_agent_completions must exist"

        # Find the next function definition to bound the search
        fn_end = source.find("\ndef ", fn_start + 10)
        if fn_end == -1:
            fn_end = len(source)

        fn_body = source[fn_start:fn_end]

        assert 'os.environ.get("PIPELINE_MODE", "full")' not in fn_body, (
            "Bug pattern found: PIPELINE_MODE must not default to 'full' directly. "
            "It should fall back to _get_pipeline_mode_from_state() instead (Issue #849)."
        )


class TestIssue1027ModeTTLSameSession:
    """Regression for Issue #1027: mtime-TTL must NOT misclassify a confirmed
    same-session long-running light run as 'full'.

    The #1173 mtime-TTL fallback fired even for a CONFIRMED same-session run,
    demoting a --light pipeline to 'full' merely because 30 min elapsed since
    the last state write. The #1027 fix scopes the TTL fallback to
    INDETERMINATE sessions only.
    """

    def _write_state(self, path: Path, *, session_id: str, mode: str, age_seconds: float) -> None:
        """Write a pipeline state file with a controlled mtime age."""
        import time as _time

        path.write_text(json.dumps({"session_id": session_id, "mode": mode}))
        old = _time.time() - age_seconds
        os.utime(path, (old, old))

    def test_long_mtime_same_session_light_honored(self, tmp_path, monkeypatch):
        """Confirmed same-session run with a stale mtime honors 'light'.

        This is the core #1027 regression. Before the fix, the mtime-TTL
        fallback returned 'full' even though the session matched.
        """
        state_path = tmp_path / "state.json"
        # mtime far older than the 30-min TTL.
        self._write_state(
            state_path,
            session_id="sess-1027",
            mode="light",
            age_seconds=unified_pre_tool._PIPELINE_STATE_TTL_SECONDS + 600,
        )
        monkeypatch.setenv("PIPELINE_STATE_FILE", str(state_path))
        monkeypatch.setenv("CLAUDE_SESSION_ID", "sess-1027")
        monkeypatch.delenv("PIPELINE_MODE", raising=False)

        assert unified_pre_tool._get_pipeline_mode_from_state() == "light"

    def test_indeterminate_session_old_mtime_returns_full(self, tmp_path, monkeypatch):
        """Unknown/indeterminate session + old mtime -> 'full' (TTL guard intact)."""
        state_path = tmp_path / "state.json"
        self._write_state(
            state_path,
            session_id="unknown",
            mode="light",
            age_seconds=unified_pre_tool._PIPELINE_STATE_TTL_SECONDS + 600,
        )
        monkeypatch.setenv("PIPELINE_STATE_FILE", str(state_path))
        # Current session also indeterminate.
        monkeypatch.delenv("CLAUDE_SESSION_ID", raising=False)
        monkeypatch.setattr(unified_pre_tool, "_session_id", "unknown")
        monkeypatch.delenv("PIPELINE_MODE", raising=False)

        assert unified_pre_tool._get_pipeline_mode_from_state() == "full"

    def test_mismatched_known_session_returns_full_no_leak(self, tmp_path, monkeypatch):
        """Mismatched known sessions -> 'full' (stale file unlinked, no leak).

        _is_stale_session() unlinks the foreign file and the helper returns the
        'full' safe default. Guards against cross-session mode leakage.
        """
        state_path = tmp_path / "state.json"
        self._write_state(
            state_path,
            session_id="sess-OTHER",
            mode="light",
            age_seconds=5,  # fresh mtime — proves it's the session check, not TTL
        )
        monkeypatch.setenv("PIPELINE_STATE_FILE", str(state_path))
        monkeypatch.setenv("CLAUDE_SESSION_ID", "sess-CURRENT")
        monkeypatch.delenv("PIPELINE_MODE", raising=False)

        assert unified_pre_tool._get_pipeline_mode_from_state() == "full"
        # Stale-session detection removed the foreign file.
        assert not state_path.exists()

    def test_same_session_fresh_mtime_honors_mode(self, tmp_path, monkeypatch):
        """Confirmed same-session run with a fresh mtime honors the stored mode."""
        state_path = tmp_path / "state.json"
        self._write_state(
            state_path,
            session_id="sess-fresh",
            mode="fix",
            age_seconds=5,
        )
        monkeypatch.setenv("PIPELINE_STATE_FILE", str(state_path))
        monkeypatch.setenv("CLAUDE_SESSION_ID", "sess-fresh")
        monkeypatch.delenv("PIPELINE_MODE", raising=False)

        assert unified_pre_tool._get_pipeline_mode_from_state() == "fix"

    def test_env_var_precedence_over_state(self, tmp_path, monkeypatch):
        """PIPELINE_MODE env var still takes precedence over the state file."""
        state_path = tmp_path / "state.json"
        self._write_state(
            state_path,
            session_id="sess-env",
            mode="light",
            age_seconds=5,
        )
        monkeypatch.setenv("PIPELINE_STATE_FILE", str(state_path))
        monkeypatch.setenv("CLAUDE_SESSION_ID", "sess-env")
        monkeypatch.setenv("PIPELINE_MODE", "fix")

        assert unified_pre_tool._get_pipeline_mode_from_state() == "fix"
