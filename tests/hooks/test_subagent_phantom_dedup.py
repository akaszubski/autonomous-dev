"""Test the phantom dedup logic for SubagentStop events (Issue #1414).

The #1176 dedup guard keys on agent_transcript_path, but phantom and real
firings emit different paths. This tests the second-tier guard that keys
on (session_id, subagent_type) to prevent duplicate record_agent_completion
calls within a time window.
"""

import json
import os
import sys
import time
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest


def test_phantom_then_real_same_agent_records_once(tmp_path, monkeypatch):
    """Test that phantom-then-real firings for same agent only record completion once."""
    
    # Import the hook module and lib modules
    hook_path = Path(__file__).resolve().parents[2] / "plugins/autonomous-dev/hooks"
    lib_path = Path(__file__).resolve().parents[2] / "plugins/autonomous-dev/lib"
    sys.path.insert(0, str(hook_path))
    sys.path.insert(0, str(lib_path))
    
    # Mock environment and dependencies
    monkeypatch.setenv("TRACK_SESSIONS", "false")  # Disable other tracking
    monkeypatch.setenv("TRACK_PIPELINE", "true")
    monkeypatch.setenv("AUTO_UPDATE_PROGRESS", "false")
    
    session_id = "test-session-123"
    agent_name = "researcher"
    
    # Track record_agent_completion calls
    completion_calls = []
    
    def mock_record_agent_completion(**kwargs):
        completion_calls.append(kwargs)
    
    # Prepare test data for two SubagentStop events
    phantom_data = {
        "hook_event_name": "SubagentStop",
        "agent_type": agent_name,
        "session_id": session_id,
        "agent_transcript_path": "/nonexistent/phantom/path.md",
        "last_assistant_message": "Short",
        "duration_ms": 25000,
        "result_word_count": 4
    }
    
    real_data = {
        "hook_event_name": "SubagentStop",
        "agent_type": agent_name,
        "session_id": session_id,
        "agent_transcript_path": str(tmp_path / "real_transcript.md"),
        "last_assistant_message": "Much longer real output with actual content",
        "duration_ms": 120000,
        "result_word_count": 250
    }
    
    # Create the real transcript file
    (tmp_path / "real_transcript.md").write_text(real_data["last_assistant_message"])
    
    # Mock stdin, record_agent_completion, and time
    with patch("sys.stdin.read") as mock_stdin, \
         patch("pipeline_completion_state.record_agent_completion", mock_record_agent_completion), \
         patch("unified_session_tracker._write_jsonl_entry", MagicMock()), \
         patch("time.time") as mock_time:
        
        # Import after patching to get fresh module state
        import unified_session_tracker
        
        # Clear the cache to ensure clean test
        unified_session_tracker._PHANTOM_DEDUP_CACHE.clear()
        
        # First event (phantom) at t=1000
        mock_time.return_value = 1000.0
        mock_stdin.return_value = json.dumps(phantom_data)
        
        # Process first event
        monkeypatch.setattr("sys.argv", ["unified_session_tracker.py"])
        result1 = unified_session_tracker.main()
        assert result1 == 0
        
        # Second event (real) 30 seconds later at t=1030
        mock_time.return_value = 1030.0
        mock_stdin.return_value = json.dumps(real_data)
        
        # Process second event
        result2 = unified_session_tracker.main()
        assert result2 == 0
    
    # Verify only one completion was recorded
    assert len(completion_calls) == 1, f"Expected 1 completion call, got {len(completion_calls)}: {completion_calls}"
    assert completion_calls[0]["session_id"] == session_id
    assert completion_calls[0]["agent_type"] == agent_name


def test_two_real_invocations_beyond_window_both_record(tmp_path, monkeypatch):
    """Test that two invocations beyond the dedup window both record."""
    
    # Import the hook module and lib modules
    hook_path = Path(__file__).resolve().parents[2] / "plugins/autonomous-dev/hooks"
    lib_path = Path(__file__).resolve().parents[2] / "plugins/autonomous-dev/lib"
    sys.path.insert(0, str(hook_path))
    sys.path.insert(0, str(lib_path))
    
    # Mock environment
    monkeypatch.setenv("TRACK_SESSIONS", "false")
    monkeypatch.setenv("TRACK_PIPELINE", "true")
    monkeypatch.setenv("AUTO_UPDATE_PROGRESS", "false")
    
    session_id = "test-session-456"
    agent_name = "implementer"
    
    # Track record_agent_completion calls
    completion_calls = []
    
    def mock_record_agent_completion(**kwargs):
        completion_calls.append(kwargs)
    
    # Prepare test data for two SubagentStop events
    first_data = {
        "hook_event_name": "SubagentStop",
        "agent_type": agent_name,
        "session_id": session_id,
        "agent_transcript_path": str(tmp_path / "first.md"),
        "last_assistant_message": "First invocation output",
        "duration_ms": 60000,
        "result_word_count": 100
    }
    
    second_data = {
        "hook_event_name": "SubagentStop",
        "agent_type": agent_name,
        "session_id": session_id,
        "agent_transcript_path": str(tmp_path / "second.md"),
        "last_assistant_message": "Second invocation output after window",
        "duration_ms": 75000,
        "result_word_count": 150
    }
    
    # Create transcript files
    (tmp_path / "first.md").write_text(first_data["last_assistant_message"])
    (tmp_path / "second.md").write_text(second_data["last_assistant_message"])
    
    with patch("sys.stdin.read") as mock_stdin, \
         patch("pipeline_completion_state.record_agent_completion", mock_record_agent_completion), \
         patch("unified_session_tracker._write_jsonl_entry", MagicMock()), \
         patch("time.time") as mock_time:
        
        import unified_session_tracker
        unified_session_tracker._PHANTOM_DEDUP_CACHE.clear()
        
        # First event at t=1000
        mock_time.return_value = 1000.0
        mock_stdin.return_value = json.dumps(first_data)
        monkeypatch.setattr("sys.argv", ["unified_session_tracker.py"])
        result1 = unified_session_tracker.main()
        assert result1 == 0
        
        # Second event 400 seconds later (beyond 300s window) at t=1400
        mock_time.return_value = 1400.0
        mock_stdin.return_value = json.dumps(second_data)
        result2 = unified_session_tracker.main()
        assert result2 == 0
    
    # Verify both completions were recorded
    assert len(completion_calls) == 2, f"Expected 2 completion calls, got {len(completion_calls)}: {completion_calls}"
    assert completion_calls[0]["session_id"] == session_id
    assert completion_calls[1]["session_id"] == session_id


def test_different_agents_same_session_both_record(tmp_path, monkeypatch):
    """Test that different agents in the same session both record."""
    
    # Import the hook module and lib modules
    hook_path = Path(__file__).resolve().parents[2] / "plugins/autonomous-dev/hooks"
    lib_path = Path(__file__).resolve().parents[2] / "plugins/autonomous-dev/lib"
    sys.path.insert(0, str(hook_path))
    sys.path.insert(0, str(lib_path))
    
    # Mock environment
    monkeypatch.setenv("TRACK_SESSIONS", "false")
    monkeypatch.setenv("TRACK_PIPELINE", "true")
    monkeypatch.setenv("AUTO_UPDATE_PROGRESS", "false")
    
    session_id = "test-session-789"
    
    # Track record_agent_completion calls
    completion_calls = []
    
    def mock_record_agent_completion(**kwargs):
        completion_calls.append(kwargs)
    
    # Prepare test data for two different agents
    researcher_data = {
        "hook_event_name": "SubagentStop",
        "agent_type": "researcher",
        "session_id": session_id,
        "agent_transcript_path": str(tmp_path / "researcher.md"),
        "last_assistant_message": "Research output",
        "duration_ms": 45000,
        "result_word_count": 200
    }
    
    planner_data = {
        "hook_event_name": "SubagentStop",
        "agent_type": "planner",
        "session_id": session_id,
        "agent_transcript_path": str(tmp_path / "planner.md"),
        "last_assistant_message": "Planning output",
        "duration_ms": 55000,
        "result_word_count": 300
    }
    
    # Create transcript files
    (tmp_path / "researcher.md").write_text(researcher_data["last_assistant_message"])
    (tmp_path / "planner.md").write_text(planner_data["last_assistant_message"])
    
    with patch("sys.stdin.read") as mock_stdin, \
         patch("pipeline_completion_state.record_agent_completion", mock_record_agent_completion), \
         patch("unified_session_tracker._write_jsonl_entry", MagicMock()), \
         patch("time.time") as mock_time:
        
        import unified_session_tracker
        unified_session_tracker._PHANTOM_DEDUP_CACHE.clear()
        
        # First agent at t=1000
        mock_time.return_value = 1000.0
        mock_stdin.return_value = json.dumps(researcher_data)
        monkeypatch.setattr("sys.argv", ["unified_session_tracker.py"])
        result1 = unified_session_tracker.main()
        assert result1 == 0
        
        # Different agent 20 seconds later at t=1020 (within window but different agent)
        mock_time.return_value = 1020.0
        mock_stdin.return_value = json.dumps(planner_data)
        result2 = unified_session_tracker.main()
        assert result2 == 0
    
    # Verify both completions were recorded (different agents)
    assert len(completion_calls) == 2, f"Expected 2 completion calls, got {len(completion_calls)}: {completion_calls}"
    assert completion_calls[0]["agent_type"] == "researcher"
    assert completion_calls[1]["agent_type"] == "planner"


def test_empty_type_phantom_not_gate_counted(tmp_path, monkeypatch):
    """Issue #1436: an empty-agent_type SubagentStop takes the unattributable
    branch — it STILL calls record_agent_completion (preserving the #1396
    contract) but MUST NOT enter _PHANTOM_DEDUP_CACHE (the #1414 collision
    keyed on (session_id, "") is bypassed).
    """
    hook_path = Path(__file__).resolve().parents[2] / "plugins/autonomous-dev/hooks"
    lib_path = Path(__file__).resolve().parents[2] / "plugins/autonomous-dev/lib"
    sys.path.insert(0, str(hook_path))
    sys.path.insert(0, str(lib_path))

    monkeypatch.setenv("TRACK_SESSIONS", "false")
    monkeypatch.setenv("TRACK_PIPELINE", "true")
    monkeypatch.setenv("AUTO_UPDATE_PROGRESS", "false")

    session_id = "test-session-unattributable-1"

    completion_calls = []

    def mock_record_agent_completion(**kwargs):
        completion_calls.append(kwargs)

    # Empty agent_type, zero duration, nonexistent transcript, but a 6-word
    # last_assistant_message so the #1396 heartbeat-drop is survived and the
    # event reaches the record block (where the unattributable branch fires).
    empty_data = {
        "hook_event_name": "SubagentStop",
        "agent_type": "",
        "session_id": session_id,
        "agent_transcript_path": str(tmp_path / "nonexistent_empty.md"),
        "last_assistant_message": "one two three four five six",
        "duration_ms": 0,
        "result_word_count": 6,
    }

    with patch("sys.stdin.read") as mock_stdin, \
         patch("pipeline_completion_state.record_agent_completion", mock_record_agent_completion), \
         patch("unified_session_tracker._write_jsonl_entry", MagicMock()):

        import unified_session_tracker

        unified_session_tracker._PHANTOM_DEDUP_CACHE.clear()

        mock_stdin.return_value = json.dumps(empty_data)
        monkeypatch.setattr("sys.argv", ["unified_session_tracker.py"])
        result = unified_session_tracker.main()
        assert result == 0

        # The unattributable branch STILL records (backward-compat #1396 contract).
        assert len(completion_calls) == 1, (
            f"Expected 1 completion call, got {len(completion_calls)}: {completion_calls}"
        )
        assert completion_calls[0]["agent_type"] == ""

        # The phantom-dedup cache MUST remain empty — the collision key
        # (session_id, "") was never inserted.
        assert unified_session_tracker._PHANTOM_DEDUP_CACHE == {}, (
            f"Expected empty phantom cache, got {unified_session_tracker._PHANTOM_DEDUP_CACHE}"
        )


def test_two_distinct_empty_type_phantoms_do_not_collide(tmp_path, monkeypatch):
    """Issue #1436: two distinct empty-agent_type firings within the dedup
    window must NOT suppress each other — the (session_id, "") collision that
    #1414's cache would create is avoided. Both record, cache stays empty.
    """
    hook_path = Path(__file__).resolve().parents[2] / "plugins/autonomous-dev/hooks"
    lib_path = Path(__file__).resolve().parents[2] / "plugins/autonomous-dev/lib"
    sys.path.insert(0, str(hook_path))
    sys.path.insert(0, str(lib_path))

    monkeypatch.setenv("TRACK_SESSIONS", "false")
    monkeypatch.setenv("TRACK_PIPELINE", "true")
    monkeypatch.setenv("AUTO_UPDATE_PROGRESS", "false")

    session_id = "test-session-unattributable-2"

    completion_calls = []

    def mock_record_agent_completion(**kwargs):
        completion_calls.append(kwargs)

    # Two distinct transcript paths (so the #1176 first-tier marker does not
    # dedup them), both empty agent_type, both with a 6-word message so they
    # survive the #1396 heartbeat-drop.
    first_data = {
        "hook_event_name": "SubagentStop",
        "agent_type": "",
        "session_id": session_id,
        "agent_transcript_path": str(tmp_path / "empty_first.md"),
        "last_assistant_message": "alpha beta gamma delta epsilon zeta",
        "duration_ms": 0,
        "result_word_count": 6,
    }
    second_data = {
        "hook_event_name": "SubagentStop",
        "agent_type": "",
        "session_id": session_id,
        "agent_transcript_path": str(tmp_path / "empty_second.md"),
        "last_assistant_message": "eta theta iota kappa lambda mu",
        "duration_ms": 0,
        "result_word_count": 6,
    }

    with patch("sys.stdin.read") as mock_stdin, \
         patch("pipeline_completion_state.record_agent_completion", mock_record_agent_completion), \
         patch("unified_session_tracker._write_jsonl_entry", MagicMock()), \
         patch("time.time") as mock_time:

        import unified_session_tracker

        unified_session_tracker._PHANTOM_DEDUP_CACHE.clear()

        # First event at t=1000.
        mock_time.return_value = 1000.0
        mock_stdin.return_value = json.dumps(first_data)
        monkeypatch.setattr("sys.argv", ["unified_session_tracker.py"])
        result1 = unified_session_tracker.main()
        assert result1 == 0

        # Second event 20 seconds later — well within the 300s window.
        mock_time.return_value = 1020.0
        mock_stdin.return_value = json.dumps(second_data)
        result2 = unified_session_tracker.main()
        assert result2 == 0

    # Neither suppressed the other: both recorded.
    assert len(completion_calls) == 2, (
        f"Expected 2 completion calls, got {len(completion_calls)}: {completion_calls}"
    )
    assert all(c["agent_type"] == "" for c in completion_calls)

    # The collision cache was never populated for the empty identity.
    assert unified_session_tracker._PHANTOM_DEDUP_CACHE == {}, (
        f"Expected empty phantom cache, got {unified_session_tracker._PHANTOM_DEDUP_CACHE}"
    )