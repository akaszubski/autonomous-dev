"""Test get_planner_completion_count helper (Issue #1417)."""

import json
import sys
import tempfile
import time
from pathlib import Path

import pytest

# Add lib to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "plugins/autonomous-dev/lib"))


def test_get_planner_completion_count_basic():
    """Basic test that the function exists and handles missing state."""
    from pipeline_completion_state import get_planner_completion_count
    
    # Test with non-existent session (should return 0)
    count = get_planner_completion_count("nonexistent-session-xyz", time.time())
    assert count == 0


def test_get_planner_completion_count_with_state():
    """Test counting with actual state file."""
    from pipeline_completion_state import get_planner_completion_count
    
    with tempfile.TemporaryDirectory() as tmpdir:
        # Create a state file with planner completion
        session_id = "test-session-123"
        state_file = Path(tmpdir) / f"pipeline_completion_{session_id}.json"
        
        now = time.time()
        future_time = now + 100
        past_time = now - 100
        
        state = {
            "completions": {
                "0": {
                    "completed": {
                        "planner": {
                            "timestamp": future_time,  # After check time
                            "success": True
                        },
                        "reviewer": {
                            "timestamp": past_time,
                            "success": True
                        }
                    }
                },
                "unscoped": {
                    "completed": {
                        "planner": {
                            "timestamp": past_time,  # Before check time
                            "success": True
                        }
                    }
                }
            }
        }
        state_file.write_text(json.dumps(state))
        
        # Mock the internal state file path function
        import pipeline_completion_state
        original_path_func = pipeline_completion_state._state_file_path
        
        def mock_path_func(sid, **kwargs):
            if sid == session_id:
                return state_file
            return Path(tmpdir) / f"pipeline_completion_{sid}.json"
        
        pipeline_completion_state._state_file_path = mock_path_func
        
        try:
            # Should count only the planner completion after 'now'
            count = get_planner_completion_count(session_id, now)
            assert count == 1  # Only the "0" scope planner is after 'now'
            
            # Check with time after all completions (should return 0)
            count = get_planner_completion_count(session_id, future_time + 100)
            assert count == 0
            
        finally:
            pipeline_completion_state._state_file_path = original_path_func


def test_get_planner_completion_count_legacy_format():
    """Test handling of legacy bool format."""
    from pipeline_completion_state import get_planner_completion_count
    
    with tempfile.TemporaryDirectory() as tmpdir:
        session_id = "legacy-session"
        state_file = Path(tmpdir) / f"pipeline_completion_{session_id}.json"
        
        # Legacy format uses bool instead of dict
        state = {
            "completions": {
                "0": {
                    "completed": {
                        "planner": True,  # Legacy bool
                        "reviewer": {"timestamp": time.time(), "success": True}  # New format
                    }
                }
            }
        }
        state_file.write_text(json.dumps(state))
        
        import pipeline_completion_state
        original_path_func = pipeline_completion_state._state_file_path
        
        pipeline_completion_state._state_file_path = lambda sid, **kw: state_file if sid == session_id else Path(tmpdir) / f"pipeline_completion_{sid}.json"
        
        try:
            # Legacy bool format has no timestamp, should not count
            count = get_planner_completion_count(session_id, time.time())
            assert count == 0
        finally:
            pipeline_completion_state._state_file_path = original_path_func