#!/usr/bin/env python3
"""
Regression tests for Issue #1448 (corroborated by #1475): the agent-dispatch
sentinel expired mid-dispatch, blocking a legitimately-dispatched implementer.

Before the fix the sentinel carried one timestamp written at dispatch time and
never moved, so any protected-path edit landing after DEFAULT_TTL_SECONDS was
denied by the Issue #1296 gate in unified_pre_tool.py — the common case for a
multi-file infra fix with reads and test runs between edits. The documented
workaround (manually rewriting the sentinel file before each edit) was flagged
by the CIA with root_cause_tag BYPASS.

The fix: agent_dispatch_sentinel.refresh() slides the TTL forward on observed
tool activity (called from session_activity_logger PostToolUse), turning the
fixed window into a sliding one while keeping the TTL as an idle/crash backstop.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from io import StringIO
from pathlib import Path
from unittest.mock import patch

import pytest

repo_root = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(repo_root / "plugins/autonomous-dev/lib"))
sys.path.insert(0, str(repo_root / "plugins/autonomous-dev/hooks"))

import agent_dispatch_sentinel as ads  # noqa: E402
import unified_pre_tool as hook  # noqa: E402

SESSION_ACTIVITY_LOGGER = (
    repo_root / "plugins/autonomous-dev/hooks/session_activity_logger.py"
)


class FakeClock:
    """Controllable wall clock so TTL windows can be crossed without sleeping."""

    def __init__(self, start: float = 1_700_000_000.0) -> None:
        self.now = start

    def time(self) -> float:
        """Return the current fake wall-clock time."""
        return self.now

    def advance(self, seconds: float) -> None:
        """Move the fake clock forward."""
        self.now += seconds


class TestIssue1448SlidingSentinelTTL:
    """Dispatched-implementer edits must stay permitted for the whole dispatch."""

    @pytest.fixture(autouse=True)
    def setup(self, tmp_path, monkeypatch):
        """Build a fake repo with protected infra paths and an active pipeline."""
        self.repo_root = tmp_path / "test_repo"
        self.repo_root.mkdir()
        (self.repo_root / ".git").mkdir()
        (self.repo_root / ".claude/local").mkdir(parents=True)
        (self.repo_root / ".claude/commands").mkdir(parents=True)
        (self.repo_root / ".claude/commands/implement.md").write_text("# implement")

        plugin_dir = self.repo_root / "plugins/autonomous-dev"
        for sub in ("agents", "commands", "hooks", "lib", "skills"):
            (plugin_dir / sub).mkdir(parents=True)
        (plugin_dir / "agents/implementer.md").write_text("agent content")
        (plugin_dir / "commands/implement.md").write_text("command content")
        (plugin_dir / "lib/agent_dispatch_sentinel.py").write_text("lib content")

        self.sentinel_path = self.repo_root / ".claude/local/active_agent_dispatch.json"
        self.state_file = tmp_path / "implement_pipeline_state.json"

        monkeypatch.chdir(self.repo_root)
        monkeypatch.setenv("CLAUDE_SESSION_ID", "test-session-1448")
        monkeypatch.setenv("PIPELINE_STATE_FILE", str(self.state_file))

        ads.clear(self.repo_root)

    def _activate_pipeline(self) -> None:
        """Write an active /implement pipeline state file."""
        self.state_file.write_text(
            json.dumps(
                {
                    "session_id": "test-session-1448",
                    "step": "implement",
                    "timestamp": time.time(),
                }
            )
        )

    def _attempt_protected_edit(self, rel_path: str) -> list[tuple[str, str]]:
        """Run the PreToolUse gate for an Edit to a protected path.

        Args:
            rel_path: Path to the protected file, relative to the fake repo root.

        Returns:
            List of (decision, reason) tuples captured from output_decision.
        """
        payload = {
            "tool_name": "Edit",
            "tool_input": {
                "file_path": str(self.repo_root / rel_path),
                "old_string": "agent content",
                "new_string": "modified content",
            },
        }
        calls: list[tuple[str, str]] = []

        def capture_output(decision, reason, **kwargs):
            calls.append((decision, reason))
            if decision == "deny":
                raise SystemExit(0)

        # patch.object on the module we actually call, NOT patch("unified_pre_tool.
        # output_decision"): another test module may have importlib.reload()ed the hook,
        # in which case the string form patches the reloaded module in sys.modules while
        # `hook.main` still resolves output_decision from this (stale) module's globals —
        # the decision is emitted but never captured, making the test order-dependent.
        with patch("sys.stdin", StringIO(json.dumps(payload))):
            with patch("sys.argv", ["unified_pre_tool.py"]):
                with patch.object(hook, "output_decision", side_effect=capture_output):
                    with patch("sys.exit", side_effect=SystemExit):
                        try:
                            hook.main()
                        except SystemExit:
                            pass
        return calls

    @staticmethod
    def _blocked_by_1296(calls: list[tuple[str, str]]) -> bool:
        """Return True if the Issue #1296 coordinator-bypass block fired."""
        return any(d == "deny" and "Issue #1296" in r for d, r in calls)

    def test_three_edits_spaced_beyond_ttl_all_permitted(self, monkeypatch):
        """#1448 spec: 3 protected edits spaced > TTL apart all succeed.

        Tool activity between edits refreshes the sentinel, so the dispatch stays
        active across a span far longer than DEFAULT_TTL_SECONDS. Without the
        refresh() fix, edits 2 and 3 are denied by the Issue #1296 gate.
        """
        clock = FakeClock()
        monkeypatch.setattr(ads, "time", clock)

        self._activate_pipeline()
        ads.write("implementer", self.repo_root)

        for edit_index in range(3):
            calls = self._attempt_protected_edit(
                "plugins/autonomous-dev/agents/implementer.md"
            )
            assert not self._blocked_by_1296(calls), (
                f"Edit {edit_index + 1} blocked despite active dispatch: {calls}"
            )
            # Simulate the dispatched agent working (reads, test runs) for longer
            # than the TTL, with PostToolUse refreshing the sentinel as it goes.
            for _ in range(4):
                clock.advance(ads.DEFAULT_TTL_SECONDS // 2)
                assert ads.refresh(repo_root=self.repo_root) is True

    def test_coordinator_direct_edit_without_dispatch_still_blocked(self):
        """Control: no sentinel => coordinator direct edit is still denied."""
        self._activate_pipeline()
        ads.clear(self.repo_root)

        calls = self._attempt_protected_edit(
            "plugins/autonomous-dev/agents/implementer.md"
        )

        assert self._blocked_by_1296(calls), f"Expected #1296 deny, got: {calls}"

    def test_refresh_cannot_arm_gate_without_a_real_dispatch(self):
        """Control: refresh() alone never creates a sentinel, so the gate stays shut."""
        self._activate_pipeline()
        ads.clear(self.repo_root)

        assert ads.refresh(repo_root=self.repo_root) is False
        assert not self.sentinel_path.exists()

        calls = self._attempt_protected_edit(
            "plugins/autonomous-dev/agents/implementer.md"
        )
        assert self._blocked_by_1296(calls), f"Expected #1296 deny, got: {calls}"

    def test_idle_dispatch_past_ttl_is_blocked_crash_backstop(self, monkeypatch):
        """Control: a crashed agent (no tool activity) still expires and is blocked."""
        clock = FakeClock()
        monkeypatch.setattr(ads, "time", clock)

        self._activate_pipeline()
        ads.write("implementer", self.repo_root)
        clock.advance(ads.DEFAULT_TTL_SECONDS + 1)

        calls = self._attempt_protected_edit(
            "plugins/autonomous-dev/agents/implementer.md"
        )

        assert self._blocked_by_1296(calls), f"Expected #1296 deny, got: {calls}"


class TestIssue1448HookWiring:
    """session_activity_logger PostToolUse must actually call refresh()."""

    @pytest.fixture(autouse=True)
    def setup(self, tmp_path):
        """Create a minimal repo the hook can log into."""
        self.repo_root = tmp_path / "hook_repo"
        (self.repo_root / ".claude/local").mkdir(parents=True)
        self.sentinel_path = self.repo_root / ".claude/local/active_agent_dispatch.json"

    def _run_hook(self, payload: dict) -> subprocess.CompletedProcess:
        """Run session_activity_logger.py as a real hook subprocess."""
        env = dict(os.environ)
        env["CLAUDE_SESSION_ID"] = "test-session-1448"
        env["ACTIVITY_LOGGING"] = "true"
        return subprocess.run(
            [sys.executable, str(SESSION_ACTIVITY_LOGGER)],
            input=json.dumps(payload),
            capture_output=True,
            text=True,
            timeout=60,
            cwd=str(self.repo_root),
            env=env,
        )

    def test_posttooluse_refreshes_existing_sentinel(self):
        """Regression: any tool use slides the active dispatch sentinel forward."""
        stale_but_valid = time.time() - 300
        self.sentinel_path.write_text(
            json.dumps(
                {"agent": "implementer", "pid": os.getpid(), "timestamp": stale_but_valid}
            )
        )

        result = self._run_hook(
            {
                "hook_event_name": "PostToolUse",
                "tool_name": "Read",
                "tool_input": {"file_path": "/tmp/some_file.py"},
                "tool_output": {"success": True},
            }
        )

        assert result.returncode == 0, result.stderr
        data = json.loads(self.sentinel_path.read_text())
        assert data["timestamp"] > stale_but_valid, (
            "PostToolUse did not refresh the sentinel timestamp"
        )
        assert data["agent"] == "implementer", "refresh() must preserve the agent name"

    def test_posttooluse_does_not_create_sentinel_when_absent(self):
        """Regression: tool activity outside a dispatch must not arm the gate."""
        assert not self.sentinel_path.exists()

        result = self._run_hook(
            {
                "hook_event_name": "PostToolUse",
                "tool_name": "Read",
                "tool_input": {"file_path": "/tmp/some_file.py"},
                "tool_output": {"success": True},
            }
        )

        assert result.returncode == 0, result.stderr
        assert not self.sentinel_path.exists(), (
            "PostToolUse created a sentinel with no dispatch in flight"
        )
