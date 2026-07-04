#!/usr/bin/env python3
"""
Regression tests for Issue #1357: General-purpose subagent warning outside pipeline.

Tests verify that when agent=main invokes Task tool with subagent_type=general-purpose
and NO pipeline is active, an informational WARN is emitted to stderr and activity log.
This is NON-BLOCKING (informational only).
"""

import json
import subprocess
import sys
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest

# Add lib paths for imports
project_root = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(project_root / "plugins/autonomous-dev/hooks"))
sys.path.insert(0, str(project_root / "plugins/autonomous-dev/lib"))


def run_hook(input_data, env=None):
    """Helper to run unified_pre_tool.py hook with given input."""
    hook_path = project_root / "plugins/autonomous-dev/hooks/unified_pre_tool.py"
    
    # Prepare environment
    hook_env = env or {}
    
    # Run the hook
    result = subprocess.run(
        [sys.executable, str(hook_path)],
        input=json.dumps(input_data),
        capture_output=True,
        text=True,
        env={**hook_env}
    )
    
    return result


def test_pipeline_active_no_warning():
    """Test (a): pipeline ACTIVE + general-purpose invocation → NO warn."""
    # Create a pipeline state file indicating active pipeline
    with tempfile.TemporaryDirectory() as tmpdir:
        state_file = Path(tmpdir) / "implement_pipeline_state.json"
        state_data = {
            "session_start": "2024-01-01T10:00:00Z",
            "mode": "full",
            "run_id": "test-run",
            "session_id": "test-session",
            "step": "implement"
        }
        state_file.write_text(json.dumps(state_data))
        
        # Input data for general-purpose subagent
        input_data = {
            "tool_name": "Task",
            "agent_type": "main",
            "session_id": "test-session",
            "tool_input": {
                "subagent_type": "general-purpose",
                "task": "test task"
            }
        }
        
        # Run with pipeline state
        env = {
            "PIPELINE_STATE_FILE": str(state_file),
            "CLAUDE_SESSION_ID": "test-session"
        }
        result = run_hook(input_data, env)
        
        # Should NOT have warning in stderr
        assert "[WARN] general-purpose launched outside pipeline" not in result.stderr
        # Hook should allow (exit 0)
        assert result.returncode == 0


def test_pipeline_inactive_main_agent_warns():
    """Test (b): pipeline INACTIVE + general-purpose invocation from main → warn is emitted."""
    # No pipeline state file - pipeline is inactive
    input_data = {
        "tool_name": "Task",
        "agent_type": "main",
        "session_id": "test-session",
        "tool_input": {
            "subagent_type": "general-purpose",
            "task": "test task"
        }
    }
    
    # Run without pipeline state
    env = {
        "CLAUDE_SESSION_ID": "test-session"
    }
    result = run_hook(input_data, env)
    
    # SHOULD have warning in stderr
    assert "[WARN] general-purpose launched outside pipeline" in result.stderr
    assert "use /implement to route through researcher-local" in result.stderr
    # Hook should still allow (exit 0) - non-blocking
    assert result.returncode == 0


def test_pipeline_inactive_other_subagent_no_warning():
    """Test (c): pipeline INACTIVE + other subagent (e.g., 'researcher') → NO warn."""
    # No pipeline state file - pipeline is inactive
    input_data = {
        "tool_name": "Task",
        "agent_type": "main",
        "session_id": "test-session",
        "tool_input": {
            "subagent_type": "researcher",  # Not general-purpose
            "task": "test task"
        }
    }
    
    # Run without pipeline state
    env = {
        "CLAUDE_SESSION_ID": "test-session"
    }
    result = run_hook(input_data, env)
    
    # Should NOT have warning in stderr
    assert "[WARN] general-purpose launched outside pipeline" not in result.stderr
    # Hook should allow (exit 0)
    assert result.returncode == 0


def test_empty_agent_type_treated_as_main():
    """Test that empty agent_type is treated as 'main' for the warning check."""
    # No pipeline state file - pipeline is inactive
    input_data = {
        "tool_name": "Task",
        "agent_type": "",  # Empty string
        "session_id": "test-session",
        "tool_input": {
            "subagent_type": "general-purpose",
            "task": "test task"
        }
    }
    
    # Run without pipeline state
    env = {
        "CLAUDE_SESSION_ID": "test-session"
    }
    result = run_hook(input_data, env)
    
    # SHOULD have warning in stderr (empty agent_type treated as main)
    assert "[WARN] general-purpose launched outside pipeline" in result.stderr
    # Hook should still allow (exit 0) - non-blocking
    assert result.returncode == 0


def test_non_agent_tool_no_warning():
    """Test that non-Agent/Task tools don't trigger the warning."""
    # No pipeline state file - pipeline is inactive
    input_data = {
        "tool_name": "Write",  # Not an Agent tool
        "agent_type": "main",
        "session_id": "test-session",
        "tool_input": {
            "subagent_type": "general-purpose",  # Shouldn't matter for Write tool
            "file_path": "/tmp/test.txt",
            "content": "test"
        }
    }
    
    # Run without pipeline state
    env = {
        "CLAUDE_SESSION_ID": "test-session"
    }
    result = run_hook(input_data, env)
    
    # Should NOT have warning in stderr
    assert "[WARN] general-purpose launched outside pipeline" not in result.stderr
    # Hook behavior for Write tool may vary (could block or allow)
    # We're only checking that the warning isn't emitted


def test_pipeline_active_from_agent_name():
    """Test that pipeline is considered active when agent_type indicates a pipeline agent."""
    # No pipeline state file, but agent_type indicates pipeline agent
    input_data = {
        "tool_name": "Task",
        "agent_type": "implementer",  # Pipeline agent in agent_type
        "session_id": "test-session",
        "tool_input": {
            "subagent_type": "general-purpose",
            "task": "test task"
        }
    }
    
    # Run with implementer as agent_type
    env = {
        "CLAUDE_SESSION_ID": "test-session"
    }
    result = run_hook(input_data, env)
    
    # Should NOT have warning in stderr (implementer is not "main")
    assert "[WARN] general-purpose launched outside pipeline" not in result.stderr
    # Hook should allow (exit 0)
    assert result.returncode == 0