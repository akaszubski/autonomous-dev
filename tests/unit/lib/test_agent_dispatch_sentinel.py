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
        """Test that default TTL is 30 seconds."""
        # Write sentinel 31 seconds ago
        old_data = {
            "agent": "test-agent",
            "pid": os.getpid(),
            "timestamp": time.time() - 31
        }
        self.sentinel_path.write_text(json.dumps(old_data))
        
        # Without specifying TTL, should use default (30s)
        assert not ads.is_active(repo_root=self.test_root)
        
        # Write sentinel 29 seconds ago
        recent_data = {
            "agent": "test-agent",
            "pid": os.getpid(),
            "timestamp": time.time() - 29
        }
        self.sentinel_path.write_text(json.dumps(recent_data))
        
        # Should be active with default TTL
        assert ads.is_active(repo_root=self.test_root)