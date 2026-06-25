#!/usr/bin/env python3
"""
Regression test for Issue #1296: Hook gap - pipeline-active bypass lets coordinator
direct-edit protected paths.

Tests that the unified_pre_tool hook properly blocks coordinator direct-edits to
protected infrastructure paths during an active pipeline, while allowing edits
when an agent is dispatched (sentinel active).
"""
from __future__ import annotations

import json
import os
import sys
import time
from io import StringIO
from pathlib import Path
from unittest.mock import patch

import pytest

# Add lib and hooks to path for imports
repo_root = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(repo_root / "plugins/autonomous-dev/lib"))
sys.path.insert(0, str(repo_root / "plugins/autonomous-dev/hooks"))

# Import the modules under test
import agent_dispatch_sentinel as ads
import unified_pre_tool as hook


class TestIssue1296CoordinatorBypass:
    """Test suite for Issue #1296 coordinator bypass protection."""
    
    @pytest.fixture(autouse=True)
    def setup(self, tmp_path, monkeypatch):
        """Set up test environment with temporary repo."""
        # Create a fake repo structure
        self.repo_root = tmp_path / "test_repo"
        self.repo_root.mkdir()
        (self.repo_root / ".git").mkdir()
        (self.repo_root / ".claude").mkdir()
        (self.repo_root / ".claude/local").mkdir()
        
        # Create autonomous-dev marker so repo is recognized
        (self.repo_root / ".claude/commands").mkdir(parents=True)
        (self.repo_root / ".claude/commands/implement.md").write_text("# implement command")
        
        # Create plugin structure
        plugin_dir = self.repo_root / "plugins/autonomous-dev"
        plugin_dir.mkdir(parents=True)
        (plugin_dir / "agents").mkdir()
        (plugin_dir / "commands").mkdir()
        (plugin_dir / "hooks").mkdir()
        (plugin_dir / "lib").mkdir()
        (plugin_dir / "skills").mkdir()
        
        # Create some protected files
        (plugin_dir / "agents/implementer.md").write_text("agent content")
        (plugin_dir / "commands/implement.md").write_text("command content")
        (plugin_dir / "hooks/test_hook.py").write_text("hook content")
        (plugin_dir / "lib/test_lib.py").write_text("lib content")
        (plugin_dir / "skills/test_skill").mkdir()
        (plugin_dir / "skills/test_skill/SKILL.md").write_text("skill content")
        
        # Create pipeline state file
        self.state_file = tmp_path / "implement_pipeline_state.json"
        
        # Change to test repo directory
        monkeypatch.chdir(self.repo_root)
        
        # Set environment variables
        monkeypatch.setenv("CLAUDE_SESSION_ID", "test-session-123")
        monkeypatch.setenv("PIPELINE_STATE_FILE", str(self.state_file))
        
        # Clear any existing sentinel
        ads.clear(self.repo_root)
    
    def _create_active_pipeline(self):
        """Create an active pipeline state file."""
        state_data = {
            "session_id": "test-session-123",
            "step": "implement",
            "timestamp": time.time()
        }
        self.state_file.write_text(json.dumps(state_data))
    
    def test_pipeline_active_protected_path_sentinel_absent_blocks(self):
        """Test 1: pipeline active + protected path + sentinel ABSENT → block"""
        # Create active pipeline
        self._create_active_pipeline()
        
        # Ensure no sentinel exists
        ads.clear(self.repo_root)
        
        # Prepare hook input
        tool_input = {
            "tool_name": "Edit",
            "tool_input": {
                "file_path": str(self.repo_root / "plugins/autonomous-dev/agents/implementer.md"),
                "old_string": "agent content",
                "new_string": "modified content"
            }
        }
        
        # Mock stdin and call hook
        with patch("sys.stdin", StringIO(json.dumps(tool_input))):
            with patch("sys.argv", ["unified_pre_tool.py"]):
                output_calls = []
                def capture_output(decision, reason, **kwargs):
                    output_calls.append((decision, reason))
                    if decision == "deny" and "Issue #1296" in reason:
                        # Simulate sys.exit after our deny
                        raise SystemExit(0)
                
                with patch("unified_pre_tool.output_decision", side_effect=capture_output):
                    with patch("sys.exit", side_effect=SystemExit):
                        try:
                            hook.main()
                        except SystemExit:
                            pass  # Expected
                        
                        # Should have called output_decision with deny and Issue #1296
                        assert any(decision == "deny" and "Issue #1296" in reason 
                                  for decision, reason in output_calls), \
                                  f"Expected deny with Issue #1296, got: {output_calls}"
    
    def test_pipeline_active_protected_path_sentinel_present_allows(self):
        """Test 2: pipeline active + protected path + sentinel PRESENT → allow"""
        # Create active pipeline
        self._create_active_pipeline()
        
        # Write agent dispatch sentinel
        ads.write("implementer", self.repo_root)
        
        # Prepare hook input
        tool_input = {
            "tool_name": "Edit",
            "tool_input": {
                "file_path": str(self.repo_root / "plugins/autonomous-dev/commands/implement.md"),
                "old_string": "command content",
                "new_string": "modified content"
            }
        }
        
        # Mock stdin and call hook
        with patch("sys.stdin", StringIO(json.dumps(tool_input))):
            with patch("sys.argv", ["unified_pre_tool.py"]):
                output_calls = []
                def capture_output(decision, reason, **kwargs):
                    output_calls.append((decision, reason))
                
                with patch("unified_pre_tool.output_decision", side_effect=capture_output):
                    with patch("sys.exit"):
                        hook.main()
                        
                        # Should NOT have Issue #1296 block (agent is dispatched)
                        assert not any(decision == "deny" and "Issue #1296" in reason 
                                      for decision, reason in output_calls), \
                                      f"Should not block with sentinel active, got: {output_calls}"
    
    def test_pipeline_inactive_protected_path_blocks(self):
        """Test 3: pipeline inactive + protected path → block (existing behavior preserved)"""
        # No pipeline state file = inactive
        
        # Prepare hook input
        tool_input = {
            "tool_name": "Write",
            "tool_input": {
                "file_path": str(self.repo_root / "plugins/autonomous-dev/hooks/new_hook.py"),
                "content": "new hook content"
            }
        }
        
        # Mock stdin and call hook
        with patch("sys.stdin", StringIO(json.dumps(tool_input))):
            with patch("sys.argv", ["unified_pre_tool.py"]):
                output_calls = []
                def capture_output(decision, reason, **kwargs):
                    output_calls.append((decision, reason))
                    if decision == "deny" and "Infrastructure files" in reason:
                        # Simulate sys.exit after infrastructure block
                        raise SystemExit(0)
                
                with patch("unified_pre_tool.output_decision", side_effect=capture_output):
                    with patch("sys.exit", side_effect=SystemExit):
                        try:
                            hook.main()
                        except SystemExit:
                            pass  # Expected
                        
                        # Should have called output_decision with deny and infrastructure message
                        assert any(decision == "deny" and "Infrastructure files" in reason 
                                  for decision, reason in output_calls), \
                                  f"Expected deny with infrastructure message, got: {output_calls}"
    
    def test_pipeline_active_docs_path_sentinel_absent_allows(self):
        """Test 4: pipeline active + docs path (not protected) + sentinel absent → allow"""
        # Create active pipeline
        self._create_active_pipeline()
        
        # Create a docs file
        docs_dir = self.repo_root / "docs"
        docs_dir.mkdir()
        docs_file = docs_dir / "README.md"
        docs_file.write_text("docs content")
        
        # Prepare hook input
        tool_input = {
            "tool_name": "Edit",
            "tool_input": {
                "file_path": str(docs_file),
                "old_string": "docs content",
                "new_string": "modified docs"
            }
        }
        
        # Mock stdin and call hook
        with patch("sys.stdin", StringIO(json.dumps(tool_input))):
            with patch("sys.argv", ["unified_pre_tool.py"]):
                output_calls = []
                def capture_output(decision, reason, **kwargs):
                    output_calls.append((decision, reason))
                
                with patch("unified_pre_tool.output_decision", side_effect=capture_output):
                    with patch("sys.exit"):
                        hook.main()
                        
                        # Should NOT block docs files
                        assert not any(decision == "deny" and ("Infrastructure files" in reason or "Issue #1296" in reason)
                                      for decision, reason in output_calls), \
                                      f"Should not block docs path, got: {output_calls}"
    
    def test_sentinel_ttl_expiry(self):
        """Test 5: sentinel TTL — write sentinel timestamped 31s ago, is_active() returns False"""
        # Write sentinel with old timestamp
        sentinel_path = self.repo_root / ".claude/local/active_agent_dispatch.json"
        sentinel_path.parent.mkdir(parents=True, exist_ok=True)
        old_data = {
            "agent": "implementer",
            "pid": os.getpid(),
            "timestamp": time.time() - 31  # 31 seconds ago
        }
        sentinel_path.write_text(json.dumps(old_data))
        
        # Check is_active returns False
        assert not ads.is_active(ttl_seconds=30, repo_root=self.repo_root)
        
        # Verify stale sentinel was cleaned up
        assert not sentinel_path.exists()
    
    def test_sentinel_write_clear_lifecycle(self):
        """Test sentinel write/clear lifecycle."""
        sentinel_path = self.repo_root / ".claude/local/active_agent_dispatch.json"
        
        # Initially no sentinel
        assert not ads.is_active(repo_root=self.repo_root)
        
        # Write sentinel
        ads.write("test-agent", self.repo_root)
        assert sentinel_path.exists()
        assert ads.is_active(repo_root=self.repo_root)
        
        # Read and verify content
        data = json.loads(sentinel_path.read_text())
        assert data["agent"] == "test-agent"
        assert "pid" in data
        assert "timestamp" in data
        
        # Clear sentinel
        ads.clear(self.repo_root)
        assert not sentinel_path.exists()
        assert not ads.is_active(repo_root=self.repo_root)
    
    def test_malformed_sentinel_handled_gracefully(self):
        """Test that malformed sentinel JSON is handled gracefully."""
        sentinel_path = self.repo_root / ".claude/local/active_agent_dispatch.json"
        sentinel_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Write malformed JSON
        sentinel_path.write_text("{invalid json}")
        
        # Should return False (not active)
        assert not ads.is_active(repo_root=self.repo_root)
        
        # Write valid but missing timestamp
        sentinel_path.write_text('{"agent": "test"}')
        assert not ads.is_active(repo_root=self.repo_root)
    def test_sentinel_import_error_fails_closed(self):
        """Test: ImportError on agent_dispatch_sentinel → fail closed (block)"""
        # Create active pipeline
        self._create_active_pipeline()
        
        # Prepare hook input for a protected path
        tool_input = {
            "tool_name": "Edit",
            "tool_input": {
                "file_path": str(self.repo_root / "plugins/autonomous-dev/lib/some_lib.py"),
                "old_string": "old code",
                "new_string": "new code"
            }
        }
        
        # Mock stdin and call hook
        with patch("sys.stdin", StringIO(json.dumps(tool_input))):
            with patch("sys.argv", ["unified_pre_tool.py"]):
                output_calls = []
                def capture_output(decision, reason, **kwargs):
                    output_calls.append((decision, reason))
                    if decision == "deny" and "Sentinel library missing" in reason:
                        # Simulate sys.exit after our deny
                        raise SystemExit(0)
                
                # Mock the import to raise ImportError
                import builtins
                original_import = builtins.__import__
                def mock_import(name, *args, **kwargs):
                    if name == "agent_dispatch_sentinel":
                        raise ImportError("Mock ImportError for sentinel")
                    return original_import(name, *args, **kwargs)
                
                with patch("sys.exit", side_effect=SystemExit):
                    with patch("unified_pre_tool.output_decision", side_effect=capture_output):
                        with patch("builtins.__import__", side_effect=mock_import):
                            try:
                                hook.main()
                            except SystemExit:
                                pass
                
                # Verify we got a deny decision with the correct reason
                assert len(output_calls) > 0, "Expected at least one output_decision call"
                final_decision, final_reason = output_calls[-1]
                assert final_decision == "deny", f"Expected deny decision, got {final_decision}"
                assert "Sentinel library missing" in final_reason, \
                    f"Expected 'Sentinel library missing' in reason, got: {final_reason}"
                assert "security-critical component unavailable" in final_reason, \
                    f"Expected security message in reason, got: {final_reason}"
