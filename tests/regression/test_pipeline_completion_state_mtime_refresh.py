"""
Regression test for Issue #1413: pipeline completion state mtime refresh.

Ensures that reading a state file refreshes its mtime, preventing active
sessions from crossing the staleness threshold mid-pipeline.
"""
import os
import sys
import time
from pathlib import Path

# Add lib to path
repo_root = Path(__file__).resolve().parents[2]
lib_path = repo_root / "plugins" / "autonomous-dev" / "lib"
sys.path.insert(0, str(lib_path))

from pipeline_completion_state import (
    _state_file_path,
    get_completed_agents,
    record_agent_completion,
)

def test_read_refreshes_mtime_issue_1413(tmp_path, monkeypatch):
    """Test that successful read updates mtime to prevent mid-pipeline wipes.
    
    Issue #1413: Active sessions that keep reading their state file should
    never cross the 7200s staleness threshold and self-wipe mid-pipeline.
    The fix is to refresh mtime on successful reads.
    """
    # Use tmp_path for state files
    monkeypatch.setenv("HOME", str(tmp_path))
    session_id = "test-session-1413"
    
    # Create a state file with some data
    record_agent_completion(session_id, "researcher")
    path = _state_file_path(session_id)
    
    # Set mtime to 1 hour ago (still fresh, under 7200s threshold)
    old_time = time.time() - 3600
    os.utime(path, (old_time, old_time))
    
    # Verify the mtime was set to the old time
    initial_mtime = path.stat().st_mtime
    assert abs(initial_mtime - old_time) < 1, "mtime should be set to old_time"
    
    # Read the state (this should refresh mtime due to the fix)
    completed = get_completed_agents(session_id)
    assert completed == {"researcher"}, "Should successfully read the data"
    
    # Verify mtime was refreshed to approximately now
    new_mtime = path.stat().st_mtime
    now = time.time()
    assert abs(new_mtime - now) < 5, f"mtime should be refreshed to ~now, got diff={now - new_mtime}"
    assert new_mtime > initial_mtime, "mtime should be newer than before"


def test_simulated_long_session_with_periodic_reads(tmp_path, monkeypatch):
    """Simulate a long-running session with periodic reads.
    
    Without the fix, a session reading its state every 30 minutes would
    still get wiped after 2 hours because mtime never updates.
    With the fix, each read refreshes mtime, keeping the file fresh.
    """
    # Use tmp_path for state files
    monkeypatch.setenv("HOME", str(tmp_path))
    session_id = "long-session-1413"
    
    # Create initial state
    record_agent_completion(session_id, "planner")
    path = _state_file_path(session_id)
    
    # Simulate session start at T-90 minutes
    session_start = time.time() - 90 * 60
    os.utime(path, (session_start, session_start))
    
    # Simulate periodic reads every 30 minutes
    simulated_times = [
        session_start + 30 * 60,  # T-60 minutes
        session_start + 60 * 60,  # T-30 minutes
        session_start + 90 * 60,  # T-0 (now)
    ]
    
    for sim_time in simulated_times:
        # Fast-forward logical time by setting file mtime
        # (without the fix, this would keep aging)
        current_mtime = path.stat().st_mtime
        
        # Read should refresh mtime
        completed = get_completed_agents(session_id)
        assert completed == {"planner"}, f"Data should remain readable at sim_time {sim_time}"
        
        # Verify mtime got refreshed (should be ~now, not sim_time)
        new_mtime = path.stat().st_mtime
        assert new_mtime > current_mtime, f"mtime should advance on each read"
    
    # Final verification: even though logical session is 90 minutes old,
    # the file should be fresh due to the recent read
    final_mtime = path.stat().st_mtime
    age = time.time() - final_mtime
    assert age < 10, f"File should be fresh after recent read, but age={age}s"


if __name__ == "__main__":
    import pytest
    pytest.main([__file__, "-v"])