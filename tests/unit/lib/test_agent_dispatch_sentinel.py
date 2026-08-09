#!/usr/bin/env python3
"""
Unit tests for agent_dispatch_sentinel library (Issue #1296).

Tests the sentinel file operations that track active agent dispatches.
"""
from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path

import pytest

# Add lib to path
repo_root = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(repo_root / "plugins/autonomous-dev/lib"))

import agent_dispatch_sentinel as ads


class TestAgentDispatchSentinel:
    """Unit tests for agent dispatch sentinel operations."""
    
    @pytest.fixture(autouse=True)
    def setup(self, tmp_path):
        """Set up test environment with temporary directory."""
        self.test_root = tmp_path / "test_repo"
        self.test_root.mkdir()
        (self.test_root / ".claude/local").mkdir(parents=True)
        self.sentinel_path = self.test_root / ".claude/local/active_agent_dispatch.json"
    
    def test_write_creates_sentinel_file(self):
        """Test that write() creates the sentinel file with correct content."""
        assert not self.sentinel_path.exists()
        
        ads.write("test-agent", self.test_root)
        
        assert self.sentinel_path.exists()
        data = json.loads(self.sentinel_path.read_text())
        assert data["agent"] == "test-agent"
        assert data["pid"] == os.getpid()
        assert abs(data["timestamp"] - time.time()) < 1  # Within 1 second
    
    def test_clear_removes_sentinel_file(self):
        """Test that clear() removes the sentinel file."""
        # Create a sentinel
        ads.write("test-agent", self.test_root)
        assert self.sentinel_path.exists()
        
        # Clear it
        ads.clear(self.test_root)
        assert not self.sentinel_path.exists()
    
    def test_clear_handles_missing_file_gracefully(self):
        """Test that clear() doesn't error when file doesn't exist."""
        assert not self.sentinel_path.exists()
        
        # Should not raise an exception
        ads.clear(self.test_root)
        
        assert not self.sentinel_path.exists()
    
    def test_is_active_returns_true_for_fresh_sentinel(self):
        """Test that is_active() returns True for a recently written sentinel."""
        ads.write("test-agent", self.test_root)
        
        assert ads.is_active(repo_root=self.test_root)
    
    def test_is_active_returns_false_for_missing_file(self):
        """Test that is_active() returns False when no sentinel exists."""
        assert not self.sentinel_path.exists()
        
        assert not ads.is_active(repo_root=self.test_root)
    
    def test_is_active_returns_false_for_stale_sentinel(self):
        """Test that is_active() returns False for sentinel older than TTL."""
        # Write sentinel with old timestamp
        old_data = {
            "agent": "test-agent",
            "pid": os.getpid(),
            "timestamp": time.time() - 35  # 35 seconds ago
        }
        self.sentinel_path.write_text(json.dumps(old_data))
        
        # Check with 30 second TTL
        assert not ads.is_active(ttl_seconds=30, repo_root=self.test_root)
    
    def test_is_active_cleans_up_stale_sentinel(self):
        """Test that is_active() removes stale sentinels opportunistically."""
        # Write stale sentinel
        old_data = {
            "agent": "test-agent",
            "pid": os.getpid(),
            "timestamp": time.time() - 35
        }
        self.sentinel_path.write_text(json.dumps(old_data))
        assert self.sentinel_path.exists()
        
        # Call is_active - should clean up
        result = ads.is_active(ttl_seconds=30, repo_root=self.test_root)
        
        assert not result
        assert not self.sentinel_path.exists()
    
    def test_is_active_handles_malformed_json(self):
        """Test that is_active() returns False for malformed JSON."""
        self.sentinel_path.write_text("{invalid json}")
        
        assert not ads.is_active(repo_root=self.test_root)
    
    def test_is_active_handles_missing_timestamp(self):
        """Test that is_active() returns False when timestamp is missing."""
        data = {"agent": "test-agent", "pid": os.getpid()}
        self.sentinel_path.write_text(json.dumps(data))
        
        assert not ads.is_active(repo_root=self.test_root)
    
    def test_is_active_handles_invalid_timestamp(self):
        """Test that is_active() returns False for non-numeric timestamp."""
        data = {
            "agent": "test-agent",
            "pid": os.getpid(),
            "timestamp": "not-a-number"
        }
        self.sentinel_path.write_text(json.dumps(data))
        
        assert not ads.is_active(repo_root=self.test_root)
    
    def test_ttl_boundary_conditions(self):
        """Test TTL boundary conditions."""
        # Exactly at TTL boundary (30 seconds)
        boundary_data = {
            "agent": "test-agent",
            "pid": os.getpid(),
            "timestamp": time.time() - 30
        }
        self.sentinel_path.write_text(json.dumps(boundary_data))
        
        # At exactly 30s, should be considered stale
        assert not ads.is_active(ttl_seconds=30, repo_root=self.test_root)
        
        # Just under TTL (29 seconds)
        under_data = {
            "agent": "test-agent", 
            "pid": os.getpid(),
            "timestamp": time.time() - 29
        }
        self.sentinel_path.write_text(json.dumps(under_data))
        
        # At 29s with 30s TTL, should still be active
        assert ads.is_active(ttl_seconds=30, repo_root=self.test_root)
    
    def test_write_creates_parent_directories(self):
        """Test that write() creates parent directories if they don't exist."""
        # Remove the .claude/local directory
        import shutil
        shutil.rmtree(self.test_root / ".claude")
        
        assert not (self.test_root / ".claude/local").exists()
        
        # Write should create the directories
        ads.write("test-agent", self.test_root)
        
        assert (self.test_root / ".claude/local").exists()
        assert self.sentinel_path.exists()
    
    def test_default_ttl_value(self):
        """Test that default TTL is 600 seconds (Issue #1447/#1471).

        30s was shorter than real implementer dispatch latency —
        system-prompt/skill loading + one Read + streaming a multi-line
        Edit call reliably exceeds it, structurally denying every large
        protected-path edit. Bumped to 600s; SubagentStop still clears the
        sentinel on agent completion, so the TTL is only the crash backstop.
        """
        # Write sentinel 601 seconds ago
        old_data = {
            "agent": "test-agent",
            "pid": os.getpid(),
            "timestamp": time.time() - 601
        }
        self.sentinel_path.write_text(json.dumps(old_data))

        # Without specifying TTL, should use default (600s)
        assert not ads.is_active(repo_root=self.test_root)

        # Write sentinel 599 seconds ago
        recent_data = {
            "agent": "test-agent",
            "pid": os.getpid(),
            "timestamp": time.time() - 599
        }
        self.sentinel_path.write_text(json.dumps(recent_data))

        # Should be active with default TTL
        assert ads.is_active(repo_root=self.test_root)


class FakeClock:
    """Controllable monotonic-ish wall clock for TTL tests (no real sleeping)."""

    def __init__(self, start: float = 1_700_000_000.0) -> None:
        self.now = start

    def time(self) -> float:
        """Return the current fake wall-clock time."""
        return self.now

    def advance(self, seconds: float) -> None:
        """Move the fake clock forward."""
        self.now += seconds


class TestRefreshSlidingTTL:
    """Unit tests for refresh() — the sliding-TTL half of Issue #1448.

    The sentinel used to carry a single timestamp written at dispatch time, so any
    dispatched implementer whose protected-path edit landed after the TTL window was
    blocked mid-run. refresh() slides the timestamp forward on observed tool activity.
    """

    @pytest.fixture(autouse=True)
    def setup(self, tmp_path, monkeypatch):
        """Set up a temp repo and a fake clock injected into the sentinel module."""
        self.test_root = tmp_path / "test_repo"
        (self.test_root / ".claude/local").mkdir(parents=True)
        self.sentinel_path = self.test_root / ".claude/local/active_agent_dispatch.json"
        self.clock = FakeClock()
        monkeypatch.setattr(ads, "time", self.clock)

    def test_refresh_slides_timestamp_forward(self):
        """refresh() moves an existing sentinel's timestamp to now."""
        ads.write("implementer", self.test_root)
        original_ts = json.loads(self.sentinel_path.read_text())["timestamp"]

        self.clock.advance(120)
        assert ads.refresh(repo_root=self.test_root) is True

        new_ts = json.loads(self.sentinel_path.read_text())["timestamp"]
        assert new_ts == pytest.approx(original_ts + 120)

    def test_refresh_on_missing_sentinel_is_noop(self):
        """refresh() must never create a sentinel from nothing (no gate self-arming)."""
        assert not self.sentinel_path.exists()

        assert ads.refresh(repo_root=self.test_root) is False

        assert not self.sentinel_path.exists()
        assert not ads.is_active(repo_root=self.test_root)

    def test_refresh_preserves_agent_and_pid_payload(self):
        """refresh() rewrites only the timestamp; identity fields survive."""
        ads.write("implementer", self.test_root)
        self.clock.advance(30)

        ads.refresh(repo_root=self.test_root)

        data = json.loads(self.sentinel_path.read_text())
        assert data["agent"] == "implementer"
        assert data["pid"] == os.getpid()

    def test_refresh_does_not_resurrect_stale_sentinel(self):
        """A sentinel already past TTL is not revived — crash backstop preserved."""
        ads.write("implementer", self.test_root)
        stale_ts = json.loads(self.sentinel_path.read_text())["timestamp"]

        self.clock.advance(ads.DEFAULT_TTL_SECONDS + 1)
        assert ads.refresh(repo_root=self.test_root) is False

        assert json.loads(self.sentinel_path.read_text())["timestamp"] == stale_ts
        assert not ads.is_active(repo_root=self.test_root)

    def test_refresh_handles_malformed_json(self):
        """Malformed sentinel payload is a no-op, not a crash."""
        self.sentinel_path.write_text("{invalid json}")

        assert ads.refresh(repo_root=self.test_root) is False

    def test_refresh_handles_non_dict_payload(self):
        """A JSON payload that is not an object is a no-op, not a crash."""
        self.sentinel_path.write_text("[1, 2, 3]")

        assert ads.refresh(repo_root=self.test_root) is False

    def test_dispatch_stays_active_far_beyond_original_ttl(self):
        """Regression for #1448: periodic refresh keeps a long dispatch active.

        Total elapsed time is 3x the TTL, but each interval between tool uses is
        below it — the exact shape of a multi-file implementer run.
        """
        ads.write("implementer", self.test_root)

        for _ in range(6):
            self.clock.advance(ads.DEFAULT_TTL_SECONDS // 2)
            assert ads.refresh(repo_root=self.test_root) is True
            assert ads.is_active(repo_root=self.test_root)

        self.clock.advance(1)
        assert ads.is_active(repo_root=self.test_root)

    def test_idle_dispatch_still_expires_without_refresh(self):
        """Without refresh activity, the TTL backstop still expires the sentinel."""
        ads.write("implementer", self.test_root)

        self.clock.advance(ads.DEFAULT_TTL_SECONDS + 1)

        assert not ads.is_active(repo_root=self.test_root)
        assert not self.sentinel_path.exists()