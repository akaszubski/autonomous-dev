#!/usr/bin/env python3
"""Regression tests for Issues #1479 (absolute-lifetime ceiling) and #1480
(is_active() isinstance guard) on agent_dispatch_sentinel.

Issue #1479: refresh() previously slid the timestamp forward on ANY session tool
activity, so a hung background dispatch (no SubagentStop) could keep the #1296
protected-path gate armed indefinitely as long as an unrelated coordinator kept
using tools. Fix: absolute ceiling anchored on a fixed ``armed_at`` field, not
subject to refresh() sliding.

Issue #1480: is_active() called .get() on the parsed JSON payload without
verifying it was a dict. A malformed non-dict payload (e.g. a JSON list)
raised AttributeError instead of returning False.
"""
from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_REPO_ROOT / "plugins/autonomous-dev/lib"))

import agent_dispatch_sentinel as ads  # noqa: E402


class _FakeClock:
    """Controllable wall clock so we can advance time without sleeping."""

    def __init__(self, start: float = 1_800_000_000.0) -> None:
        self.now = start

    def time(self) -> float:
        return self.now

    def advance(self, seconds: float) -> None:
        self.now += seconds


class TestIssue1480IsActiveDictGuard:
    """is_active() must return False for non-dict payloads, not raise."""

    @pytest.fixture(autouse=True)
    def setup(self, tmp_path):
        self.repo = tmp_path / "repo"
        (self.repo / ".claude/local").mkdir(parents=True)
        self.sentinel = self.repo / ".claude/local/active_agent_dispatch.json"

    def test_is_active_returns_false_for_list_payload(self):
        """A JSON list payload must not raise AttributeError."""
        self.sentinel.write_text("[1, 2, 3]")
        # Must return False without raising.
        assert ads.is_active(repo_root=self.repo) is False

    def test_is_active_returns_false_for_string_payload(self):
        """A JSON string payload must not raise AttributeError."""
        self.sentinel.write_text('"not-a-dict"')
        assert ads.is_active(repo_root=self.repo) is False

    def test_is_active_returns_false_for_number_payload(self):
        """A JSON number payload must not raise AttributeError."""
        self.sentinel.write_text("42")
        assert ads.is_active(repo_root=self.repo) is False

    def test_is_active_returns_false_for_null_payload(self):
        """A JSON null payload must not raise AttributeError."""
        self.sentinel.write_text("null")
        assert ads.is_active(repo_root=self.repo) is False

    def test_is_active_still_works_for_valid_dict(self):
        """Regression: the guard must not break the happy path."""
        payload = {
            "agent": "implementer",
            "pid": os.getpid(),
            "timestamp": time.time(),
            "armed_at": time.time(),
        }
        self.sentinel.write_text(json.dumps(payload))
        assert ads.is_active(repo_root=self.repo) is True


class TestIssue1479AbsoluteLifetimeCeiling:
    """refresh() and is_active() must respect an absolute ceiling anchored on armed_at."""

    @pytest.fixture(autouse=True)
    def setup(self, tmp_path, monkeypatch):
        self.repo = tmp_path / "repo"
        (self.repo / ".claude/local").mkdir(parents=True)
        self.sentinel = self.repo / ".claude/local/active_agent_dispatch.json"
        self.clock = _FakeClock()
        monkeypatch.setattr(ads, "time", self.clock)

    def test_write_records_armed_at_equal_to_timestamp(self):
        ads.write("implementer", self.repo)
        data = json.loads(self.sentinel.read_text())
        assert "armed_at" in data
        assert data["armed_at"] == data["timestamp"]

    def test_refresh_slides_timestamp_but_not_armed_at(self):
        """armed_at is the fixed anchor; refresh() must never touch it."""
        ads.write("implementer", self.repo)
        original_armed_at = json.loads(self.sentinel.read_text())["armed_at"]

        self.clock.advance(300)
        assert ads.refresh(repo_root=self.repo) is True

        data = json.loads(self.sentinel.read_text())
        assert data["armed_at"] == original_armed_at
        assert data["timestamp"] == pytest.approx(original_armed_at + 300)

    def test_refresh_noops_past_absolute_ceiling(self):
        """Past MAX_LIFETIME_SECONDS from armed_at, refresh() must not extend."""
        ads.write("implementer", self.repo)
        armed_at = json.loads(self.sentinel.read_text())["armed_at"]

        # Simulate steady refresh activity right up to the ceiling.
        for _ in range(20):
            self.clock.advance(ads.DEFAULT_TTL_SECONDS // 2)
            ads.refresh(repo_root=self.repo)

        # Advance past the absolute ceiling. Even continued refresh calls now
        # return False and do not slide the timestamp.
        target = armed_at + ads.MAX_LIFETIME_SECONDS + 1
        self.clock.now = target
        assert ads.refresh(repo_root=self.repo) is False

    def test_is_active_returns_false_past_absolute_ceiling(self):
        """is_active() enforces the ceiling even if timestamp appears fresh."""
        # Manually craft a sentinel whose timestamp is fresh but armed_at is old,
        # simulating the hung-dispatch + coordinator-refresh attack scenario.
        armed_at = self.clock.time()
        self.clock.advance(ads.MAX_LIFETIME_SECONDS + 60)
        payload = {
            "agent": "implementer",
            "pid": os.getpid(),
            "timestamp": self.clock.time(),  # fresh timestamp (refresh kept it alive)
            "armed_at": armed_at,             # but armed long past the ceiling
        }
        self.sentinel.write_text(json.dumps(payload))

        assert ads.is_active(repo_root=self.repo) is False
        # Opportunistic cleanup happened.
        assert not self.sentinel.exists()

    def test_ceiling_blocks_hung_dispatch_kept_alive_by_coordinator(self):
        """End-to-end scenario from Issue #1479.

        A background dispatch hangs (no SubagentStop) at t=0. The coordinator
        keeps issuing tool calls, each of which invokes refresh(). Without the
        ceiling, is_active() would remain True forever. With the ceiling, it
        goes False once MAX_LIFETIME_SECONDS elapses from armed_at.
        """
        ads.write("implementer", self.repo)

        # 4 hours of refresh activity at 5-minute intervals — 48 refreshes,
        # exactly at the ceiling.
        for _ in range(48):
            self.clock.advance(300)
            ads.refresh(repo_root=self.repo)
            # For most of the window, is_active() should still be True.

        # Just past the ceiling.
        self.clock.advance(1)
        # Additional refresh attempts are no-ops.
        assert ads.refresh(repo_root=self.repo) is False
        # And is_active() reports False, cleaning up the sentinel.
        assert ads.is_active(repo_root=self.repo) is False

    def test_pre_1479_sentinel_without_armed_at_gracefully_upgraded(self):
        """A sentinel written before this fix (no armed_at field) must not crash.

        For backward compat, armed_at defaults to the timestamp value.
        """
        payload = {
            "agent": "implementer",
            "pid": os.getpid(),
            "timestamp": self.clock.time(),
            # no armed_at
        }
        self.sentinel.write_text(json.dumps(payload))

        # Fresh → active.
        assert ads.is_active(repo_root=self.repo) is True

        # Refresh works.
        self.clock.advance(60)
        assert ads.refresh(repo_root=self.repo) is True
