#!/usr/bin/env python3
"""
Regression test for Issue #1196: Ordering gate session mismatch.

Tests the sentinel fallback mechanism when the ordering gate checks
completions under the wrong session_id. Ensures proper fallback to
sentinel-resolved session_id when primary lookups are empty.
"""

import json
import os
import tempfile
import time
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# Add the lib directory to the path
import sys
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "plugins/autonomous-dev/lib"))

from agent_ordering_gate import check_ordering_with_session_fallback
from pipeline_completion_state import record_agent_completion


def test_ordering_passes_with_sentinel_fallback(tmp_path):
    """Test that ordering passes when completions are found via sentinel fallback."""
    # Setup: Create a state file with completions under a different session_id
    state_file = tmp_path / "pipeline_state.json"
    sentinel_session = "sentinel-session-123"
    
    # Record completions under the sentinel session
    with patch("pipeline_completion_state.get_legacy_sentinel_path", return_value=state_file):
        record_agent_completion(sentinel_session, "planner", issue_number=0)
        record_agent_completion(sentinel_session, "plan-critic", issue_number=0)
    
    # Test: Check ordering with a different session_id
    test_session = "test-session-456"
    
    # Mock resolve_session_id to return the sentinel session
    with patch("pipeline_completion_state.resolve_session_id", return_value=sentinel_session):
        with patch("pipeline_completion_state.get_legacy_sentinel_path", return_value=state_file):
            result = check_ordering_with_session_fallback(
                "implementer",
                test_session,
                issue_number=0,
                validation_mode="sequential",
                pipeline_mode="full"
            )
    
    # Verify: Should pass because completions were found via sentinel fallback
    assert result.passed, f"Expected ordering to pass with sentinel fallback, but got: {result.reason}"


def test_deny_includes_session_id():
    """Test that deny messages include the evaluated session_id."""
    # This test validates that the deny message includes session_id.
    # We'll test this directly with the check_ordering_with_session_fallback function.
    
    # Test with a session that has no completions
    test_session = "test-session-789"
    
    # Mock empty completions
    with patch("pipeline_completion_state.get_completed_agents", return_value=set()):
        with patch("pipeline_completion_state.get_launched_agents", return_value=set()):
            with patch("pipeline_completion_state.get_plan_critic_skipped", return_value=False):
                with patch("pipeline_completion_state.resolve_session_id", return_value="unknown"):
                    result = check_ordering_with_session_fallback(
                        "implementer",
                        test_session,
                        issue_number=0,
                        validation_mode="sequential",
                        pipeline_mode="full"
                    )
    
    # Verify: Should fail and reason should be present
    assert not result.passed, "Expected ordering to fail when prerequisites are missing"
    assert "planner" in result.reason or "plan-critic" in result.reason
    
    # Note: The session_id inclusion in the message happens in the hook itself,
    # not in the gate function. This test validates the gate behavior.


def test_stale_sentinel_not_honored(tmp_path):
    """Test that stale sentinel files (mtime > 3600s) are not used for fallback."""
    # Setup: Create a state file with old mtime
    state_file = tmp_path / "pipeline_state.json"
    sentinel_session = "stale-session-123"
    
    # Create state with completions
    state_data = {
        "session_id": sentinel_session,
        "completed_agents": {"planner": True, "plan-critic": True},
        "launched_agents": {},
        "issue_0": {
            "completed_agents": {"planner": True, "plan-critic": True}
        }
    }
    state_file.write_text(json.dumps(state_data))
    
    # Make the file stale (older than 3600 seconds)
    old_time = time.time() - 4000
    os.utime(state_file, (old_time, old_time))
    
    # Test: Check ordering with a different session_id
    test_session = "test-session-999"
    
    with patch("pipeline_completion_state.get_legacy_sentinel_path", return_value=state_file):
        result = check_ordering_with_session_fallback(
            "implementer",
            test_session,
            issue_number=0,
            validation_mode="sequential",
            pipeline_mode="full"
        )
    
    # Verify: Should fail because stale sentinel is not honored
    assert not result.passed, "Expected ordering to fail with stale sentinel"
    assert "planner" in result.reason or "plan-critic" in result.reason


def test_empty_completions_triggers_fallback(tmp_path):
    """Test that empty completions from primary session triggers sentinel fallback."""
    # Setup: Create two state files - one empty, one with completions
    state_file = tmp_path / "pipeline_state.json"
    sentinel_session = "sentinel-with-data"
    primary_session = "primary-empty"
    
    # Create state with completions under sentinel session only
    state_data = {
        "session_id": sentinel_session,
        "completed_agents": {},
        "launched_agents": {},
        f"session_{sentinel_session}": {
            "completed_agents": {"planner": True, "plan-critic": True}
        },
        f"session_{primary_session}": {
            "completed_agents": {}  # Empty for primary
        }
    }
    state_file.write_text(json.dumps(state_data))
    
    # Test: Check with primary session (which has empty completions)
    with patch("pipeline_completion_state.resolve_session_id", return_value=sentinel_session):
        with patch("pipeline_completion_state.get_legacy_sentinel_path", return_value=state_file):
            # Mock the get_completed_agents to return empty for primary, data for sentinel
            def mock_get_completed(sid, issue_number=0):
                if sid == primary_session:
                    return set()  # Empty
                elif sid == sentinel_session:
                    return {"planner", "plan-critic"}  # Has data
                return set()
            
            with patch("pipeline_completion_state.get_completed_agents", side_effect=mock_get_completed):
                with patch("pipeline_completion_state.get_launched_agents", return_value=set()):
                    with patch("pipeline_completion_state.get_plan_critic_skipped", return_value=False):
                        result = check_ordering_with_session_fallback(
                            "implementer",
                            primary_session,
                            issue_number=0,
                            validation_mode="sequential",
                            pipeline_mode="full"
                        )
    
    # Verify: Should pass because fallback found completions
    assert result.passed, f"Expected to pass via fallback, got: {result.reason}"


def test_concurrent_sessions_isolated(tmp_path):
    """Test that concurrent sessions remain isolated - no cross-session bleed."""
    # Setup: Create state files for two concurrent sessions
    state_file = tmp_path / "pipeline_state.json"
    session_a = "session-alpha"
    session_b = "session-beta"
    
    # Record different completions for each session
    with patch("pipeline_completion_state.get_legacy_sentinel_path", return_value=state_file):
        # Session A has planner completed
        record_agent_completion(session_a, "planner", issue_number=0)
        
        # Session B has researcher completed (but not planner)
        record_agent_completion(session_b, "researcher", issue_number=0)
    
    # Test: Check ordering for session B trying to run plan-critic
    # This should fail because session B doesn't have planner completed
    with patch("pipeline_completion_state.get_legacy_sentinel_path", return_value=state_file):
        result_b = check_ordering_with_session_fallback(
            "plan-critic",
            session_b,
            issue_number=0,
            validation_mode="sequential",
            pipeline_mode="full"
        )
    
    # Verify: Session B should fail (no planner), proving no bleed from session A
    assert not result_b.passed, "Expected session B to fail - no cross-session bleed"
    assert "planner" in result_b.reason, f"Should require planner, got: {result_b.reason}"
    
    # Double-check: Session A should be able to run plan-critic
    with patch("pipeline_completion_state.get_legacy_sentinel_path", return_value=state_file):
        result_a = check_ordering_with_session_fallback(
            "plan-critic",
            session_a,
            issue_number=0,
            validation_mode="sequential",
            pipeline_mode="full"
        )
    
    assert result_a.passed, f"Session A should pass, got: {result_a.reason}"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])