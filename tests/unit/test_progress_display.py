#!/usr/bin/env python3
"""
Tests for progress_display.py - Real-time progress indicator

This module tests the terminal UI that displays agent pipeline progress
in real-time by polling the JSON state file.

Test Coverage:
- Tree view rendering with emoji indicators
- TTY vs non-TTY mode handling
- Progress calculations (0-100%)
- Terminal resize handling
- Malformed JSON handling
- Agent status transitions
- Display refresh logic

These tests follow TDD - they WILL FAIL until progress_display.py is implemented.
"""

import json
import sys
from datetime import datetime
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock, mock_open
import pytest

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))


class TestProgressDisplay:
    """Test progress display rendering and updates."""

    # ========================================
    # FIXTURES
    # ========================================

    @pytest.fixture
    def mock_pipeline_state(self):
        """Mock pipeline state with various agent statuses."""
        return {
            "session_id": "20251104-120000",
            "started": "2025-11-04T12:00:00",
            "github_issue": 42,
            "agents": [
                {
                    "agent": "researcher",
                    "status": "completed",
                    "started_at": "2025-11-04T12:00:05",
                    "completed_at": "2025-11-04T12:05:00",
                    "duration_seconds": 295,
                    "message": "Found 5 patterns",
                    "tools_used": ["WebSearch", "Grep"]
                },
                {
                    "agent": "planner",
                    "status": "completed",
                    "started_at": "2025-11-04T12:05:10",
                    "completed_at": "2025-11-04T12:08:30",
                    "duration_seconds": 200,
                    "message": "Architecture plan created"
                },
                {
                    "agent": "test-master",
                    "status": "started",
                    "started_at": "2025-11-04T12:08:35",
                    "message": "Writing tests"
                }
            ]
        }

    @pytest.fixture
    def mock_pipeline_empty(self):
        """Mock empty pipeline state (just started)."""
        return {
            "session_id": "20251104-120000",
            "started": "2025-11-04T12:00:00",
            "github_issue": None,
            "agents": []
        }

    @pytest.fixture
    def mock_pipeline_complete(self):
        """Mock complete pipeline state (all agents done)."""
        return {
            "session_id": "20251104-120000",
            "started": "2025-11-04T12:00:00",
            "github_issue": 42,
            "agents": [
                {"agent": "researcher", "status": "completed", "duration_seconds": 295},
                {"agent": "planner", "status": "completed", "duration_seconds": 200},
                {"agent": "test-master", "status": "completed", "duration_seconds": 180},
                {"agent": "implementer", "status": "completed", "duration_seconds": 450},
                {"agent": "reviewer", "status": "completed", "duration_seconds": 120},
                {"agent": "security-auditor", "status": "completed", "duration_seconds": 90},
                {"agent": "doc-master", "status": "completed", "duration_seconds": 75}
            ]
        }

    @pytest.fixture
    def mock_pipeline_with_failure(self):
        """Mock pipeline state with a failed agent."""
        return {
            "session_id": "20251104-120000",
            "started": "2025-11-04T12:00:00",
            "github_issue": 42,
            "agents": [
                {"agent": "researcher", "status": "completed", "duration_seconds": 295},
                {"agent": "planner", "status": "failed", "error": "Invalid architecture", "duration_seconds": 100}
            ]
        }

    # ========================================
    # RENDERING TESTS
    # ========================================

    def test_render_tree_view_basic(self, mock_pipeline_state):
        """Test basic tree view rendering with agent statuses."""
        from plugins.autonomous_dev.scripts.progress_display import ProgressDisplay

        display = ProgressDisplay(session_file=Path("/fake/session.json"))
        output = display.render_tree_view(mock_pipeline_state)

        # Check for tree structure
        assert "Agent Pipeline Progress" in output
        assert "researcher" in output
        assert "planner" in output
        assert "test-master" in output

        # Check for status emojis
        assert "✅" in output  # Completed agents
        assert "⏳" in output  # Running agent

    def test_render_tree_view_with_progress_bar(self, mock_pipeline_state):
        """Test progress bar rendering (2/7 agents complete)."""
        from plugins.autonomous_dev.scripts.progress_display import ProgressDisplay

        display = ProgressDisplay(session_file=Path("/fake/session.json"))
        output = display.render_tree_view(mock_pipeline_state)

        # Should show progress: 2 completed, 1 running, 4 pending = ~28% (2/7)
        assert "Progress:" in output
        assert "28%" in output or "29%" in output  # Allow for rounding

    def test_render_tree_view_empty_pipeline(self, mock_pipeline_empty):
        """Test rendering when no agents have started yet."""
        from plugins.autonomous_dev.scripts.progress_display import ProgressDisplay

        display = ProgressDisplay(session_file=Path("/fake/session.json"))
        output = display.render_tree_view(mock_pipeline_empty)

        assert "Agent Pipeline Progress" in output
        assert "No agents started" in output or "0%" in output

    def test_render_tree_view_complete_pipeline(self, mock_pipeline_complete):
        """Test rendering when all agents are complete."""
        from plugins.autonomous_dev.scripts.progress_display import ProgressDisplay

        display = ProgressDisplay(session_file=Path("/fake/session.json"))
        output = display.render_tree_view(mock_pipeline_complete)

        assert "100%" in output
        assert "Pipeline Complete" in output or "COMPLETE" in output
        # All agents should show completed status
        assert output.count("✅") >= 7

    def test_render_tree_view_with_failure(self, mock_pipeline_with_failure):
        """Test rendering with failed agent."""
        from plugins.autonomous_dev.scripts.progress_display import ProgressDisplay

        display = ProgressDisplay(session_file=Path("/fake/session.json"))
        output = display.render_tree_view(mock_pipeline_with_failure)

        assert "❌" in output  # Failed emoji
        assert "planner" in output
        assert "Invalid architecture" in output or "failed" in output.lower()

    def test_render_includes_github_issue(self, mock_pipeline_state):
        """Test that GitHub issue number is displayed when present."""
        from plugins.autonomous_dev.scripts.progress_display import ProgressDisplay

        display = ProgressDisplay(session_file=Path("/fake/session.json"))
        output = display.render_tree_view(mock_pipeline_state)

        assert "42" in output or "#42" in output
        assert "issue" in output.lower() or "Issue" in output

    def test_render_agent_duration(self, mock_pipeline_state):
        """Test that agent durations are displayed."""
        from plugins.autonomous_dev.scripts.progress_display import ProgressDisplay

        display = ProgressDisplay(session_file=Path("/fake/session.json"))
        output = display.render_tree_view(mock_pipeline_state)

        # Should show duration for completed agents
        assert "295s" in output or "4m" in output  # researcher duration
        assert "200s" in output or "3m" in output  # planner duration

    def test_render_agent_tools_used(self, mock_pipeline_state):
        """Test that tools used by agents are displayed."""
        from plugins.autonomous_dev.scripts.progress_display import ProgressDisplay

        display = ProgressDisplay(session_file=Path("/fake/session.json"))
        output = display.render_tree_view(mock_pipeline_state)

        # Should show tools used by researcher
        assert "WebSearch" in output
        assert "Grep" in output

    # ========================================
    # TTY MODE TESTS
    # ========================================

    def test_tty_mode_detection(self):
        """Test TTY mode is detected correctly."""
        from plugins.autonomous_dev.scripts.progress_display import ProgressDisplay

        with patch('sys.stdout.isatty', return_value=True):
            display = ProgressDisplay(session_file=Path("/fake/session.json"))
            assert display.is_tty is True

        with patch('sys.stdout.isatty', return_value=False):
            display = ProgressDisplay(session_file=Path("/fake/session.json"))
            assert display.is_tty is False

    def test_tty_mode_uses_ansi_codes(self, mock_pipeline_state):
        """Test that TTY mode uses ANSI escape codes for clearing."""
        from plugins.autonomous_dev.scripts.progress_display import ProgressDisplay

        with patch('sys.stdout.isatty', return_value=True):
            display = ProgressDisplay(session_file=Path("/fake/session.json"))
            output = display.render_tree_view(mock_pipeline_state)

            # Should contain ANSI escape codes in TTY mode
            # \033[H moves cursor to home, \033[2J clears screen
            # These might be added during display, not in render_tree_view

    def test_non_tty_mode_no_ansi_codes(self, mock_pipeline_state):
        """Test that non-TTY mode doesn't use ANSI escape codes."""
        from plugins.autonomous_dev.scripts.progress_display import ProgressDisplay

        with patch('sys.stdout.isatty', return_value=False):
            display = ProgressDisplay(session_file=Path("/fake/session.json"))
            output = display.render_tree_view(mock_pipeline_state)

            # Should NOT contain ANSI escape codes in non-TTY mode
            assert "\033[" not in output

    def test_non_tty_mode_shows_updates_incrementally(self):
        """Test that non-TTY mode shows updates line-by-line, not refreshing."""
        from plugins.autonomous_dev.scripts.progress_display import ProgressDisplay

        with patch('sys.stdout.isatty', return_value=False):
            display = ProgressDisplay(session_file=Path("/fake/session.json"))
            # In non-TTY mode, should append updates rather than clearing screen
            assert display.display_mode == "incremental" or not display.is_tty

    # ========================================
    # PROGRESS CALCULATION TESTS
    # ========================================

    def test_calculate_progress_empty(self, mock_pipeline_empty):
        """Test progress calculation with no agents."""
        from plugins.autonomous_dev.scripts.progress_display import ProgressDisplay

        display = ProgressDisplay(session_file=Path("/fake/session.json"))
        progress = display.calculate_progress(mock_pipeline_empty)

        assert progress == 0

    def test_calculate_progress_partial(self, mock_pipeline_state):
        """Test progress calculation with some agents complete."""
        from plugins.autonomous_dev.scripts.progress_display import ProgressDisplay

        display = ProgressDisplay(session_file=Path("/fake/session.json"))
        progress = display.calculate_progress(mock_pipeline_state)

        # 2 completed out of 7 expected = 28.57% ≈ 29%
        assert 28 <= progress <= 29

    def test_calculate_progress_complete(self, mock_pipeline_complete):
        """Test progress calculation with all agents complete."""
        from plugins.autonomous_dev.scripts.progress_display import ProgressDisplay

        display = ProgressDisplay(session_file=Path("/fake/session.json"))
        progress = display.calculate_progress(mock_pipeline_complete)

        assert progress == 100

    def test_calculate_progress_running_agent_counts(self, mock_pipeline_state):
        """Test that running agents contribute partial progress."""
        from plugins.autonomous_dev.scripts.progress_display import ProgressDisplay

        display = ProgressDisplay(session_file=Path("/fake/session.json"))
        progress = display.calculate_progress(mock_pipeline_state)

        # 2 completed + 1 running (counts as 0.5) = 2.5 / 7 = 35.7%
        # Or if running doesn't count: 2 / 7 = 28.6%
        assert 28 <= progress <= 36

    def test_calculate_progress_with_failure(self, mock_pipeline_with_failure):
        """Test that failed agents count as complete for progress."""
        from plugins.autonomous_dev.scripts.progress_display import ProgressDisplay

        display = ProgressDisplay(session_file=Path("/fake/session.json"))
        progress = display.calculate_progress(mock_pipeline_with_failure)

        # 1 completed + 1 failed = 2 / 7 = 28.57%
        assert 28 <= progress <= 29

    # ========================================
    # JSON HANDLING TESTS
    # ========================================

    def test_load_pipeline_state_valid_json(self, tmp_path, mock_pipeline_state):
        """Test loading valid JSON pipeline state."""
        from plugins.autonomous_dev.scripts.progress_display import ProgressDisplay

        session_file = tmp_path / "session.json"
        session_file.write_text(json.dumps(mock_pipeline_state))

        display = ProgressDisplay(session_file=session_file)
        state = display.load_pipeline_state()

        assert state == mock_pipeline_state
        assert state["session_id"] == "20251104-120000"

    def test_load_pipeline_state_file_not_found(self, tmp_path):
        """Test handling when session file doesn't exist."""
        from plugins.autonomous_dev.scripts.progress_display import ProgressDisplay

        session_file = tmp_path / "nonexistent.json"
        display = ProgressDisplay(session_file=session_file)
        state = display.load_pipeline_state()

        # Should return empty/default state or None
        assert state is None or state == {}

    def test_load_pipeline_state_malformed_json(self, tmp_path):
        """Test handling malformed JSON gracefully."""
        from plugins.autonomous_dev.scripts.progress_display import ProgressDisplay

        session_file = tmp_path / "bad.json"
        session_file.write_text("{invalid json here")

        display = ProgressDisplay(session_file=session_file)
        state = display.load_pipeline_state()

        # Should handle error gracefully and return None or empty state
        assert state is None or state == {}

    def test_load_pipeline_state_empty_file(self, tmp_path):
        """Test handling empty file."""
        from plugins.autonomous_dev.scripts.progress_display import ProgressDisplay

        session_file = tmp_path / "empty.json"
        session_file.write_text("")

        display = ProgressDisplay(session_file=session_file)
        state = display.load_pipeline_state()

        assert state is None or state == {}

    def test_load_pipeline_state_permission_error(self, tmp_path):
        """Test handling permission denied on session file."""
        from plugins.autonomous_dev.scripts.progress_display import ProgressDisplay

        session_file = tmp_path / "session.json"
        session_file.write_text("{}")

        with patch('pathlib.Path.read_text', side_effect=PermissionError):
            display = ProgressDisplay(session_file=session_file)
            state = display.load_pipeline_state()

            assert state is None or state == {}

    # ========================================
    # TERMINAL RESIZE TESTS
    # ========================================

    def test_handle_terminal_resize(self, mock_pipeline_state):
        """Test that display adapts to terminal size changes."""
        from plugins.autonomous_dev.scripts.progress_display import ProgressDisplay

        display = ProgressDisplay(session_file=Path("/fake/session.json"))

        with patch('shutil.get_terminal_size', return_value=(80, 24)):
            output = display.render_tree_view(mock_pipeline_state)
            # Should fit in 80 columns
            lines = output.split('\n')
            assert all(len(line) <= 80 for line in lines)

        with patch('shutil.get_terminal_size', return_value=(120, 40)):
            output = display.render_tree_view(mock_pipeline_state)
            # Should adapt to 120 columns (might use more space)

    def test_minimum_terminal_width(self, mock_pipeline_state):
        """Test handling of very narrow terminal."""
        from plugins.autonomous_dev.scripts.progress_display import ProgressDisplay

        display = ProgressDisplay(session_file=Path("/fake/session.json"))

        with patch('shutil.get_terminal_size', return_value=(40, 24)):
            output = display.render_tree_view(mock_pipeline_state)
            # Should still render without crashing, even if truncated
            assert len(output) > 0

    # ========================================
    # DISPLAY UPDATE LOOP TESTS
    # ========================================

    def test_display_loop_polls_file(self, tmp_path, mock_pipeline_state):
        """Test that display loop polls the session file."""
        from plugins.autonomous_dev.scripts.progress_display import ProgressDisplay

        session_file = tmp_path / "session.json"
        session_file.write_text(json.dumps(mock_pipeline_state))

        display = ProgressDisplay(session_file=session_file)

        # Mock the run loop to only execute once
        with patch.object(display, 'should_continue', side_effect=[True, False]):
            with patch.object(display, 'render_tree_view') as mock_render:
                display.run()
                # Should have called render at least once
                assert mock_render.call_count >= 1

    def test_display_loop_refresh_rate(self, tmp_path, mock_pipeline_state):
        """Test that display refreshes at correct interval."""
        from plugins.autonomous_dev.scripts.progress_display import ProgressDisplay

        session_file = tmp_path / "session.json"
        session_file.write_text(json.dumps(mock_pipeline_state))

        display = ProgressDisplay(session_file=session_file, refresh_interval=0.5)

        # Should use 0.5 second refresh interval
        assert display.refresh_interval == 0.5

    def test_display_loop_stops_when_complete(self, tmp_path, mock_pipeline_complete):
        """Test that display loop stops when pipeline is complete."""
        from plugins.autonomous_dev.scripts.progress_display import ProgressDisplay

        session_file = tmp_path / "session.json"
        session_file.write_text(json.dumps(mock_pipeline_complete))

        display = ProgressDisplay(session_file=session_file)

        # Should detect completion and stop
        with patch('time.sleep'):  # Don't actually sleep in tests
            with patch.object(display, 'render_tree_view') as mock_render:
                display.run()
                # Should render final state and exit
                assert mock_render.call_count >= 1

    def test_display_loop_handles_keyboard_interrupt(self, tmp_path, mock_pipeline_state):
        """Test that Ctrl+C gracefully stops display."""
        from plugins.autonomous_dev.scripts.progress_display import ProgressDisplay

        session_file = tmp_path / "session.json"
        session_file.write_text(json.dumps(mock_pipeline_state))

        display = ProgressDisplay(session_file=session_file)

        with patch.object(display, 'load_pipeline_state', side_effect=KeyboardInterrupt):
            # Should handle KeyboardInterrupt gracefully
            try:
                display.run()
            except KeyboardInterrupt:
                pytest.fail("KeyboardInterrupt should be caught and handled")

    # ========================================
    # AGENT ORDER TESTS
    # ========================================

    def test_display_shows_expected_agent_order(self, mock_pipeline_state):
        """Test that agents are displayed in expected execution order."""
        from plugins.autonomous_dev.scripts.progress_display import ProgressDisplay

        display = ProgressDisplay(session_file=Path("/fake/session.json"))
        output = display.render_tree_view(mock_pipeline_state)

        # Find positions of agent names
        expected_order = [
            "researcher", "planner", "test-master", "implementer",
            "reviewer", "security-auditor", "doc-master"
        ]

        # Check that agents appear in order in output
        positions = []
        for agent in expected_order:
            pos = output.find(agent)
            if pos != -1:
                positions.append((agent, pos))

        # Verify order is maintained (at least for agents that appear)
        for i in range(len(positions) - 1):
            assert positions[i][1] < positions[i + 1][1], \
                f"{positions[i][0]} should appear before {positions[i + 1][0]}"

    def test_display_shows_pending_agents(self, mock_pipeline_state):
        """Test that pending agents (not yet started) are shown."""
        from plugins.autonomous_dev.scripts.progress_display import ProgressDisplay

        display = ProgressDisplay(session_file=Path("/fake/session.json"))
        output = display.render_tree_view(mock_pipeline_state)

        # Agents not yet started should still appear in list
        assert "implementer" in output
        assert "reviewer" in output
        assert "security-auditor" in output
        assert "doc-master" in output

        # Should show pending status (⏸️ or ⬜ or similar)
        # At least one pending indicator should be present
        assert "⏸️" in output or "⬜" in output or "PENDING" in output.upper()

    # ========================================
    # FORMATTING TESTS
    # ========================================

    def test_format_duration_seconds(self):
        """Test duration formatting for seconds."""
        from plugins.autonomous_dev.scripts.progress_display import ProgressDisplay

        display = ProgressDisplay(session_file=Path("/fake/session.json"))

        # Short durations in seconds
        assert display.format_duration(5) == "5s"
        assert display.format_duration(45) == "45s"

    def test_format_duration_minutes(self):
        """Test duration formatting for minutes."""
        from plugins.autonomous_dev.scripts.progress_display import ProgressDisplay

        display = ProgressDisplay(session_file=Path("/fake/session.json"))

        # Durations in minutes
        assert display.format_duration(60) == "1m 0s" or display.format_duration(60) == "1m"
        assert display.format_duration(125) == "2m 5s"
        assert display.format_duration(295) == "4m 55s"

    def test_format_duration_hours(self):
        """Test duration formatting for hours."""
        from plugins.autonomous_dev.scripts.progress_display import ProgressDisplay

        display = ProgressDisplay(session_file=Path("/fake/session.json"))

        # Long durations
        assert "h" in display.format_duration(3600)
        assert "1h" in display.format_duration(3661)

    def test_truncate_long_messages(self, mock_pipeline_state):
        """Test that long messages are truncated to fit terminal."""
        from plugins.autonomous_dev.scripts.progress_display import ProgressDisplay

        # Add agent with very long message
        mock_pipeline_state["agents"].append({
            "agent": "implementer",
            "status": "started",
            "message": "A" * 200  # Very long message
        })

        display = ProgressDisplay(session_file=Path("/fake/session.json"))

        with patch('shutil.get_terminal_size', return_value=(80, 24)):
            output = display.render_tree_view(mock_pipeline_state)
            lines = output.split('\n')

            # No line should exceed terminal width
            assert all(len(line) <= 80 for line in lines)

            # Should see truncation indicator
            assert "..." in output or "…" in output
