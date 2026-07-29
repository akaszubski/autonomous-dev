"""Test plan-critic REVISE gate enforcement (Issue #1417)."""

import json
import os
import sys
import tempfile
import time
from pathlib import Path

import pytest


def test_check_plan_critic_revise_gate_basic():
    """Basic test that the gate function exists and can be called."""
    # Add hook directory to path
    sys.path.insert(0, str(Path(__file__).parent.parent.parent / "plugins/autonomous-dev/hooks"))
    sys.path.insert(0, str(Path(__file__).parent.parent.parent / "plugins/autonomous-dev/lib"))
    
    # Import the function
    from unified_pre_tool import check_plan_critic_revise_gate, AGENT_TOOL_NAMES
    
    # Test with non-agent tool (should allow)
    decision, reason = check_plan_critic_revise_gate("Write", {})
    assert decision == "allow"
    assert "Not an agent invocation" in reason
    
    # Test with non-implementer agent (should allow)
    decision, reason = check_plan_critic_revise_gate("Agent", {"subagent_type": "reviewer"})
    assert decision == "allow"
    assert "Not implementer dispatch" in reason
    
    # Test with implementer but no verdict file (should allow)
    decision, reason = check_plan_critic_revise_gate("Agent", {"subagent_type": "implementer"})
    assert decision == "allow"
    # Either "No plan-critic verdict file" or error message


def test_revise_gate_with_verdict_file():
    """Test gate behavior with actual verdict file."""
    sys.path.insert(0, str(Path(__file__).parent.parent.parent / "plugins/autonomous-dev/hooks"))
    sys.path.insert(0, str(Path(__file__).parent.parent.parent / "plugins/autonomous-dev/lib"))
    
    from unified_pre_tool import check_plan_critic_revise_gate
    
    # Create temporary directory structure
    with tempfile.TemporaryDirectory() as tmpdir:
        claude_dir = Path(tmpdir) / ".claude"
        claude_dir.mkdir()
        
        # Save original cwd and change to tmpdir
        orig_cwd = os.getcwd()
        try:
            os.chdir(tmpdir)
            
            # Test 1: PROCEED verdict (should allow)
            verdict_file = claude_dir / "plan_critic_verdict.json"
            verdict_file.write_text(json.dumps({
                "verdict": "PROCEED",
                "timestamp": "2024-12-20T10:00:00Z",
                "composite_score": 80
            }))
            
            decision, reason = check_plan_critic_revise_gate(
                "Agent", {"subagent_type": "implementer"}
            )
            assert decision == "allow"
            assert "PROCEED" in reason
            
            # Test 2: BLOCKED verdict (should allow - coordinator handles)
            verdict_file.write_text(json.dumps({
                "verdict": "BLOCKED",
                "timestamp": "2024-12-20T10:00:00Z",
                "composite_score": 30
            }))
            
            decision, reason = check_plan_critic_revise_gate(
                "Agent", {"subagent_type": "implementer"}
            )
            assert decision == "allow"
            assert "BLOCKED" in reason
            
            # Test 3: REVISE verdict without timestamp (should allow - error case)
            verdict_file.write_text(json.dumps({
                "verdict": "REVISE",
                "composite_score": 60
            }))
            
            decision, reason = check_plan_critic_revise_gate(
                "Agent", {"subagent_type": "implementer"}
            )
            assert decision == "allow"
            assert "No timestamp" in reason or "Error" in reason
            
        finally:
            os.chdir(orig_cwd)


def test_revise_gate_integration_mock():
    """Test REVISE gate with mocked planner completion count."""
    sys.path.insert(0, str(Path(__file__).parent.parent.parent / "plugins/autonomous-dev/hooks"))
    sys.path.insert(0, str(Path(__file__).parent.parent.parent / "plugins/autonomous-dev/lib"))
    
    # We need to mock get_planner_completion_count before importing the hook
    import pipeline_completion_state
    original_func = pipeline_completion_state.get_planner_completion_count if hasattr(pipeline_completion_state, 'get_planner_completion_count') else None
    
    # Create mock function
    def mock_get_planner_completion_count(session_id, since_timestamp):
        # Return 0 for first test (no re-invoke), 1 for second test (re-invoked)
        return getattr(mock_get_planner_completion_count, 'return_value', 0)
    
    pipeline_completion_state.get_planner_completion_count = mock_get_planner_completion_count
    
    try:
        from unified_pre_tool import check_plan_critic_revise_gate
        
        with tempfile.TemporaryDirectory() as tmpdir:
            claude_dir = Path(tmpdir) / ".claude"
            claude_dir.mkdir()
            
            orig_cwd = os.getcwd()
            try:
                os.chdir(tmpdir)
                
                # Create REVISE verdict file
                verdict_file = claude_dir / "plan_critic_verdict.json"
                verdict_file.write_text(json.dumps({
                    "verdict": "REVISE",
                    "timestamp": "2024-12-20T10:00:00Z",
                    "composite_score": 60,
                    "reasoning": "Plan needs improvements"
                }))
                
                # Test 1: No planner re-invocation (should deny)
                mock_get_planner_completion_count.return_value = 0
                decision, reason = check_plan_critic_revise_gate(
                    "Agent", {"subagent_type": "implementer"}
                )
                assert decision == "deny"
                assert "planner was not re-invoked" in reason
                
                # Test 2: Planner was re-invoked (should allow)
                mock_get_planner_completion_count.return_value = 1
                decision, reason = check_plan_critic_revise_gate(
                    "Agent", {"subagent_type": "implementer"}
                )
                assert decision == "allow"
                assert "Planner re-invoked 1 time(s)" in reason
                
            finally:
                os.chdir(orig_cwd)
    finally:
        # Restore original function if it existed
        if original_func:
            pipeline_completion_state.get_planner_completion_count = original_func