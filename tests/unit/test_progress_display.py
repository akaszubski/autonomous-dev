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
import signal
import subprocess
import sys
import threading
import time
from datetime import datetime
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock, mock_open
import pytest

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

# Safety bounds for tests that drive ProgressDisplay.run().
# Issue #1567: this loop hung CI for two months, so every test that enters it
# must be able to leave it. MAX_POLL_ITERATIONS caps the loop from the inside;
# RUN_JOIN_TIMEOUT_SECONDS caps it from the outside, so a regression in the
# exit condition surfaces as a named assertion failure, never as a hang.
MAX_POLL_ITERATIONS = 5
RUN_JOIN_TIMEOUT_SECONDS = 5.0

# Outer bound for the real-subprocess SIGTERM test. Deliberately equal to
# stop_display()'s own grace period: if the display cannot exit within the
# window its only production caller allows, the wiring is not working.
SIGTERM_EXIT_TIMEOUT_SECONDS = 5.0


def _run_display_bounded(display) -> threading.Thread:
    """Run ``display.run()`` on a daemon thread and join with a hard bound.

    Args:
        display: A ``ProgressDisplay`` instance to drive.

    Returns:
        The thread. ``thread.is_alive()`` is True if ``run()`` never returned,
        which callers MUST assert against.
    """
    thread = threading.Thread(target=display.run, daemon=True)
    thread.start()
    thread.join(timeout=RUN_JOIN_TIMEOUT_SECONDS)
    return thread


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
        """Test that display loop polls the session file.

        Regression for Issue #1567. The previous version of this test patched
        the ``should_continue`` *attribute* with ``side_effect=[True, False]``.
        ``patch.object`` builds a MagicMock for that, but ``while
        self.should_continue:`` only evaluates truthiness — a MagicMock is
        always truthy and the side_effect list is never consumed, so the loop
        span forever inside ``time.sleep()`` and burned every CI run.

        The loop is now ended through the production ``stop()`` API, and the
        real ``load_pipeline_state`` is spied on rather than mocked so the test
        still proves the loop genuinely reads the session file.
        """
        from plugins.autonomous_dev.scripts.progress_display import ProgressDisplay

        session_file = tmp_path / "session.json"
        session_file.write_text(json.dumps(mock_pipeline_state))

        display = ProgressDisplay(session_file=session_file, refresh_interval=0.01)

        # Spy on the REAL loader: proves the loop actually polls the file.
        polled_states = []
        real_load = display.load_pipeline_state

        def spy_load():
            state = real_load()
            polled_states.append(state)
            return state

        # End the loop after the first render, via the production API.
        def stop_after_render(state):
            display.stop()
            return ""

        # Inner bound: never sleep for real, and force an exit if the loop
        # somehow keeps spinning past MAX_POLL_ITERATIONS.
        sleep_calls = []

        def bounded_sleep(seconds):
            sleep_calls.append(seconds)
            if len(sleep_calls) > MAX_POLL_ITERATIONS:
                display.stop()

        with patch.object(display, "load_pipeline_state", side_effect=spy_load), \
                patch.object(display, "render_tree_view",
                             side_effect=stop_after_render) as mock_render, \
                patch("time.sleep", side_effect=bounded_sleep):
            thread = _run_display_bounded(display)

        assert not thread.is_alive(), (
            f"ProgressDisplay.run() did not return within "
            f"{RUN_JOIN_TIMEOUT_SECONDS}s - the poll loop has no working exit "
            f"condition (Issue #1567)"
        )
        assert mock_render.call_count >= 1, "loop must render at least once"
        assert polled_states, "loop must poll the session file at least once"
        assert polled_states[0] == mock_pipeline_state, (
            "poll must return the real contents of the session file"
        )
        assert len(sleep_calls) <= MAX_POLL_ITERATIONS, (
            f"loop over-iterated: {len(sleep_calls)} sleeps for a single stop()"
        )

    def test_regression_issue_1567_stop_gives_poll_loop_bounded_exit(
        self, tmp_path, mock_pipeline_state
    ):
        """Regression for Issue #1567: run() must honour a stop() request.

        Fails before the fix (``ProgressDisplay`` has no ``stop()``), passes
        after. Uses no mock of the loop body at all — real polling, real
        rendering — so it cannot pass by neutering the behaviour under test.
        """
        from plugins.autonomous_dev.scripts.progress_display import ProgressDisplay

        session_file = tmp_path / "session.json"
        session_file.write_text(json.dumps(mock_pipeline_state))

        display = ProgressDisplay(session_file=session_file, refresh_interval=0.01)

        # A second thread stops the loop shortly after it starts.
        stopper = threading.Timer(0.05, display.stop)

        started = time.monotonic()
        stopper.start()
        thread = _run_display_bounded(display)
        stopper.cancel()
        elapsed = time.monotonic() - started

        assert not thread.is_alive(), (
            f"run() ignored stop() and was still looping after "
            f"{RUN_JOIN_TIMEOUT_SECONDS}s"
        )
        assert display.should_continue is False, "stop() must clear should_continue"
        assert elapsed < RUN_JOIN_TIMEOUT_SECONDS, (
            f"run() took {elapsed:.2f}s to honour stop()"
        )

    def test_regression_issue_1567_main_registers_sigterm_handler_that_stops(
        self, tmp_path, mock_pipeline_state
    ):
        """Regression for Issue #1567: ``main()`` must wire SIGTERM to ``stop()``.

        ``stop()`` shipped with zero production callers — a method that exists,
        reads as capability, and nothing invokes. SIGTERM is precisely what
        ``pipeline_controller.stop_display()`` sends this process, so it is the
        caller that makes the method real.

        This asserts the wiring; the subprocess test below proves it fires.
        """
        from plugins.autonomous_dev.scripts import progress_display as pd

        session_file = tmp_path / "session.json"
        session_file.write_text(json.dumps(mock_pipeline_state))

        registered = {}

        def capture_signal(signum, handler):
            registered[signum] = handler

        # Capture the real instance main() built, via the stubbed run(), so the
        # assertion below can check actual state rather than a mock call.
        instances = []
        with patch.object(sys, "argv", ["progress_display.py", str(session_file)]), \
                patch.object(pd.signal, "signal", side_effect=capture_signal), \
                patch.object(pd.ProgressDisplay, "run", autospec=True,
                             side_effect=lambda self: instances.append(self)):
            pd.main()

        assert instances, "main() never reached display.run()"
        display = instances[0]

        assert signal.SIGTERM in registered, (
            "main() registered no SIGTERM handler, so a terminating signal kills "
            "the render mid-write and stop() keeps its zero production callers "
            "(Issue #1567). Registered: "
            f"{sorted(int(s) for s in registered)}"
        )

        handler = registered[signal.SIGTERM]
        assert callable(handler), f"SIGTERM handler must be callable, got {handler!r}"
        assert handler not in (signal.SIG_DFL, signal.SIG_IGN), (
            "SIGTERM must map to a real handler, not SIG_DFL/SIG_IGN"
        )

        # The handler must ask the loop to stop — and must NOT raise, which
        # would unwind from an arbitrary point inside run() and land in its
        # broad `except Exception`, racing the render instead of cooperating.
        assert display.should_continue is True, "precondition: loop not yet stopped"
        handler(int(signal.SIGTERM), None)
        assert display.should_continue is False, (
            "SIGTERM handler did not stop the poll loop — run() re-checks "
            "should_continue each pass, and that flag is the only exit the "
            "handler can cooperate with (Issue #1567)"
        )

    def test_regression_issue_1567_real_sigterm_exits_cleanly_and_flushes(
        self, tmp_path, mock_pipeline_state
    ):
        """Regression for Issue #1567: a REAL SIGTERM must produce a clean exit.

        A handler nobody has watched run is the same class of defect as an
        unwired method, so this spawns the actual script and signals it exactly
        as ``stop_display()`` does (``Popen.terminate()``).

        Measured before the fix: returncode -15 (killed by SIGTERM) with **0
        bytes** of stdout — stdout is block-buffered on a pipe, so every
        rendered frame was discarded. After: returncode 0 and the render
        survives. Asserting on the flushed bytes, not merely on the exit code,
        is what makes this test fail on the pre-fix behaviour.
        """
        script = (
            Path(__file__).resolve().parents[2]
            / "plugins" / "autonomous-dev" / "scripts" / "progress_display.py"
        )
        assert script.is_file(), f"progress_display.py not found at {script}"

        session_file = tmp_path / "session.json"
        session_file.write_text(json.dumps(mock_pipeline_state))

        proc = subprocess.Popen(
            [sys.executable, str(script), str(session_file), "--refresh", "0.05"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        try:
            time.sleep(0.4)  # let it render a few passes into the pipe buffer
            proc.terminate()  # the real SIGTERM stop_display() sends
            try:
                out, err = proc.communicate(timeout=SIGTERM_EXIT_TIMEOUT_SECONDS)
            except subprocess.TimeoutExpired:
                proc.kill()
                proc.communicate()
                pytest.fail(
                    f"progress_display.py ignored SIGTERM for "
                    f"{SIGTERM_EXIT_TIMEOUT_SECONDS}s. stop_display() would then "
                    f"escalate to SIGKILL (Issue #1567)."
                )
        finally:
            if proc.poll() is None:  # pragma: no cover - only if the fail path missed
                proc.kill()

        assert proc.returncode == 0, (
            f"SIGTERM did not produce a clean exit: returncode {proc.returncode} "
            f"(negative means killed by signal "
            f"{-proc.returncode if proc.returncode < 0 else 'n/a'}). The handler "
            f"must let run() fall out of its loop normally.\nstderr: {err[-500:]}"
        )
        assert "Agent Pipeline Progress" in out, (
            "Rendered output was lost on shutdown. stdout is block-buffered on a "
            "pipe, so an abrupt kill discards every frame; a clean exit flushes "
            f"them (Issue #1567). Got {len(out)} bytes: {out[-300:]!r}"
        )

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
