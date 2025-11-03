#!/usr/bin/env python3
"""
Tests for pipeline_controller.py - Process lifecycle management

This module tests the controller that manages the progress display process:
- Starting the display subprocess
- Stopping the display subprocess
- Cleanup on errors and signals
- PID tracking and management

Test Coverage:
- Process lifecycle (start/stop)
- PID file management
- Signal handling (SIGTERM, SIGINT)
- Error recovery and cleanup
- Multiple concurrent displays prevention
- Process monitoring

These tests follow TDD - they WILL FAIL until pipeline_controller.py is implemented.
"""

import os
import signal
import subprocess
import sys
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock, call
import pytest

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))


class TestPipelineController:
    """Test pipeline controller process management."""

    # ========================================
    # FIXTURES
    # ========================================

    @pytest.fixture
    def tmp_session_dir(self, tmp_path):
        """Create temporary session directory."""
        session_dir = tmp_path / "sessions"
        session_dir.mkdir()
        return session_dir

    @pytest.fixture
    def mock_session_file(self, tmp_session_dir):
        """Create mock session file."""
        session_file = tmp_session_dir / "20251104-120000-pipeline.json"
        session_file.write_text('{"session_id": "20251104-120000", "agents": []}')
        return session_file

    @pytest.fixture
    def pid_file_path(self, tmp_path):
        """Path for PID file."""
        return tmp_path / "display.pid"

    # ========================================
    # INITIALIZATION TESTS
    # ========================================

    def test_controller_initialization(self, mock_session_file):
        """Test controller initializes with session file."""
        from plugins.autonomous_dev.scripts.pipeline_controller import PipelineController

        controller = PipelineController(session_file=mock_session_file)

        assert controller.session_file == mock_session_file
        assert controller.display_process is None

    def test_controller_creates_pid_file_path(self, mock_session_file, tmp_path):
        """Test controller creates PID file path."""
        from plugins.autonomous_dev.scripts.pipeline_controller import PipelineController

        controller = PipelineController(
            session_file=mock_session_file,
            pid_dir=tmp_path
        )

        assert controller.pid_file.parent == tmp_path

    # ========================================
    # START DISPLAY TESTS
    # ========================================

    def test_start_display_process(self, mock_session_file):
        """Test starting the display subprocess."""
        from plugins.autonomous_dev.scripts.pipeline_controller import PipelineController

        controller = PipelineController(session_file=mock_session_file)

        with patch('subprocess.Popen') as mock_popen:
            mock_process = Mock()
            mock_process.pid = 12345
            mock_popen.return_value = mock_process

            controller.start_display()

            # Should have started subprocess
            assert mock_popen.called
            assert controller.display_process is not None
            assert controller.display_process.pid == 12345

    def test_start_display_writes_pid_file(self, mock_session_file, tmp_path):
        """Test that starting display writes PID to file."""
        from plugins.autonomous_dev.scripts.pipeline_controller import PipelineController

        controller = PipelineController(
            session_file=mock_session_file,
            pid_dir=tmp_path
        )

        with patch('subprocess.Popen') as mock_popen:
            mock_process = Mock()
            mock_process.pid = 12345
            mock_popen.return_value = mock_process

            controller.start_display()

            # Should have written PID file
            pid_file = tmp_path / "progress_display.pid"
            assert pid_file.exists()
            assert pid_file.read_text().strip() == "12345"

    def test_start_display_passes_session_file_arg(self, mock_session_file):
        """Test that session file path is passed to subprocess."""
        from plugins.autonomous_dev.scripts.pipeline_controller import PipelineController

        controller = PipelineController(session_file=mock_session_file)

        with patch('subprocess.Popen') as mock_popen:
            mock_process = Mock()
            mock_popen.return_value = mock_process

            controller.start_display()

            # Check that subprocess was called with correct arguments
            call_args = mock_popen.call_args
            cmd = call_args[0][0]  # First positional arg is command list

            assert "progress_display.py" in " ".join(cmd)
            assert str(mock_session_file) in " ".join(cmd)

    def test_start_display_detaches_process(self, mock_session_file):
        """Test that display process is detached (doesn't block)."""
        from plugins.autonomous_dev.scripts.pipeline_controller import PipelineController

        controller = PipelineController(session_file=mock_session_file)

        with patch('subprocess.Popen') as mock_popen:
            mock_process = Mock()
            mock_popen.return_value = mock_process

            controller.start_display()

            # Should use Popen (not run) for non-blocking execution
            assert mock_popen.called

    def test_start_display_prevents_duplicate(self, mock_session_file, tmp_path):
        """Test that starting display twice doesn't create duplicate processes."""
        from plugins.autonomous_dev.scripts.pipeline_controller import PipelineController

        controller = PipelineController(
            session_file=mock_session_file,
            pid_dir=tmp_path
        )

        with patch('subprocess.Popen') as mock_popen:
            mock_process = Mock()
            mock_process.pid = 12345
            mock_process.poll.return_value = None  # Process still running
            mock_popen.return_value = mock_process

            controller.start_display()
            first_pid = controller.display_process.pid

            # Try to start again
            controller.start_display()

            # Should not have created second process
            assert controller.display_process.pid == first_pid
            assert mock_popen.call_count == 1

    def test_start_display_handles_existing_pid_file(self, mock_session_file, tmp_path):
        """Test handling of stale PID file from previous run."""
        from plugins.autonomous_dev.scripts.pipeline_controller import PipelineController

        # Write stale PID file
        pid_file = tmp_path / "progress_display.pid"
        pid_file.write_text("99999")  # PID that doesn't exist

        controller = PipelineController(
            session_file=mock_session_file,
            pid_dir=tmp_path
        )

        with patch('subprocess.Popen') as mock_popen:
            mock_process = Mock()
            mock_process.pid = 12345
            mock_popen.return_value = mock_process

            with patch('os.kill', side_effect=ProcessLookupError):
                # Should detect stale PID and start new process
                controller.start_display()

                assert controller.display_process.pid == 12345

    # ========================================
    # STOP DISPLAY TESTS
    # ========================================

    def test_stop_display_process(self, mock_session_file):
        """Test stopping the display subprocess."""
        from plugins.autonomous_dev.scripts.pipeline_controller import PipelineController

        controller = PipelineController(session_file=mock_session_file)

        with patch('subprocess.Popen') as mock_popen:
            mock_process = Mock()
            mock_process.pid = 12345
            mock_process.poll.return_value = None  # Running
            mock_popen.return_value = mock_process

            controller.start_display()
            controller.stop_display()

            # Should have terminated process
            mock_process.terminate.assert_called_once()

    def test_stop_display_sends_sigterm(self, mock_session_file):
        """Test that stop sends SIGTERM for graceful shutdown."""
        from plugins.autonomous_dev.scripts.pipeline_controller import PipelineController

        controller = PipelineController(session_file=mock_session_file)

        with patch('subprocess.Popen') as mock_popen:
            mock_process = Mock()
            mock_process.pid = 12345
            mock_process.poll.return_value = None
            mock_popen.return_value = mock_process

            controller.start_display()
            controller.stop_display()

            # Should use terminate() (SIGTERM) not kill() (SIGKILL)
            assert mock_process.terminate.called
            assert not mock_process.kill.called

    def test_stop_display_waits_for_exit(self, mock_session_file):
        """Test that stop waits for process to exit."""
        from plugins.autonomous_dev.scripts.pipeline_controller import PipelineController

        controller = PipelineController(session_file=mock_session_file)

        with patch('subprocess.Popen') as mock_popen:
            mock_process = Mock()
            mock_process.pid = 12345
            mock_process.poll.side_effect = [None, None, 0]  # Running, then exits
            mock_popen.return_value = mock_process

            controller.start_display()
            controller.stop_display(timeout=1.0)

            # Should wait for process
            assert mock_process.wait.called or mock_process.poll.call_count > 1

    def test_stop_display_force_kills_after_timeout(self, mock_session_file):
        """Test that stop force-kills if process doesn't exit gracefully."""
        from plugins.autonomous_dev.scripts.pipeline_controller import PipelineController

        controller = PipelineController(session_file=mock_session_file)

        with patch('subprocess.Popen') as mock_popen:
            mock_process = Mock()
            mock_process.pid = 12345
            # Process doesn't exit after terminate
            mock_process.poll.return_value = None
            mock_process.wait.side_effect = subprocess.TimeoutExpired("cmd", 1.0)
            mock_popen.return_value = mock_process

            controller.start_display()
            controller.stop_display(timeout=0.1)

            # Should escalate to kill after timeout
            assert mock_process.kill.called

    def test_stop_display_removes_pid_file(self, mock_session_file, tmp_path):
        """Test that stopping removes PID file."""
        from plugins.autonomous_dev.scripts.pipeline_controller import PipelineController

        pid_file = tmp_path / "progress_display.pid"

        controller = PipelineController(
            session_file=mock_session_file,
            pid_dir=tmp_path
        )

        with patch('subprocess.Popen') as mock_popen:
            mock_process = Mock()
            mock_process.pid = 12345
            mock_process.poll.return_value = None
            mock_popen.return_value = mock_process

            controller.start_display()
            assert pid_file.exists()

            controller.stop_display()

            # PID file should be removed
            assert not pid_file.exists()

    def test_stop_display_handles_already_stopped(self, mock_session_file):
        """Test that stopping already-stopped process is safe."""
        from plugins.autonomous_dev.scripts.pipeline_controller import PipelineController

        controller = PipelineController(session_file=mock_session_file)

        # Try to stop without starting
        controller.stop_display()  # Should not raise error

        # Start and let process exit on its own
        with patch('subprocess.Popen') as mock_popen:
            mock_process = Mock()
            mock_process.pid = 12345
            mock_process.poll.return_value = 0  # Already exited
            mock_popen.return_value = mock_process

            controller.start_display()
            controller.stop_display()  # Should handle gracefully

    # ========================================
    # PID FILE TESTS
    # ========================================

    def test_read_pid_file(self, mock_session_file, tmp_path):
        """Test reading PID from file."""
        from plugins.autonomous_dev.scripts.pipeline_controller import PipelineController

        pid_file = tmp_path / "progress_display.pid"
        pid_file.write_text("12345")

        controller = PipelineController(
            session_file=mock_session_file,
            pid_dir=tmp_path
        )

        pid = controller.read_pid_file()
        assert pid == 12345

    def test_read_pid_file_not_found(self, mock_session_file, tmp_path):
        """Test reading PID when file doesn't exist."""
        from plugins.autonomous_dev.scripts.pipeline_controller import PipelineController

        controller = PipelineController(
            session_file=mock_session_file,
            pid_dir=tmp_path
        )

        pid = controller.read_pid_file()
        assert pid is None

    def test_read_pid_file_invalid_content(self, mock_session_file, tmp_path):
        """Test reading PID file with invalid content."""
        from plugins.autonomous_dev.scripts.pipeline_controller import PipelineController

        pid_file = tmp_path / "progress_display.pid"
        pid_file.write_text("not a number")

        controller = PipelineController(
            session_file=mock_session_file,
            pid_dir=tmp_path
        )

        pid = controller.read_pid_file()
        assert pid is None

    def test_is_process_running(self, mock_session_file):
        """Test checking if process is running."""
        from plugins.autonomous_dev.scripts.pipeline_controller import PipelineController

        controller = PipelineController(session_file=mock_session_file)

        # Mock process that exists
        with patch('os.kill') as mock_kill:
            mock_kill.return_value = None  # Process exists
            assert controller.is_process_running(12345) is True

        # Mock process that doesn't exist
        with patch('os.kill', side_effect=ProcessLookupError):
            assert controller.is_process_running(99999) is False

    def test_is_process_running_permission_denied(self, mock_session_file):
        """Test handling permission denied when checking process."""
        from plugins.autonomous_dev.scripts.pipeline_controller import PipelineController

        controller = PipelineController(session_file=mock_session_file)

        with patch('os.kill', side_effect=PermissionError):
            # Process exists but we don't have permission - treat as running
            assert controller.is_process_running(12345) is True

    # ========================================
    # CLEANUP TESTS
    # ========================================

    def test_cleanup_on_error(self, mock_session_file, tmp_path):
        """Test cleanup when subprocess fails to start."""
        from plugins.autonomous_dev.scripts.pipeline_controller import PipelineController

        controller = PipelineController(
            session_file=mock_session_file,
            pid_dir=tmp_path
        )

        with patch('subprocess.Popen', side_effect=OSError("Failed to start")):
            with pytest.raises(OSError):
                controller.start_display()

            # Should not leave stale PID file
            pid_file = tmp_path / "progress_display.pid"
            assert not pid_file.exists()

    def test_cleanup_on_signal(self, mock_session_file):
        """Test cleanup on signal (SIGTERM, SIGINT)."""
        from plugins.autonomous_dev.scripts.pipeline_controller import PipelineController

        controller = PipelineController(session_file=mock_session_file)

        with patch('subprocess.Popen') as mock_popen:
            mock_process = Mock()
            mock_process.pid = 12345
            mock_process.poll.return_value = None
            mock_popen.return_value = mock_process

            controller.start_display()

            # Simulate receiving SIGTERM
            controller.cleanup()

            # Should have stopped display
            assert mock_process.terminate.called

    def test_context_manager_cleanup(self, mock_session_file):
        """Test cleanup using context manager."""
        from plugins.autonomous_dev.scripts.pipeline_controller import PipelineController

        with patch('subprocess.Popen') as mock_popen:
            mock_process = Mock()
            mock_process.pid = 12345
            mock_process.poll.return_value = None
            mock_popen.return_value = mock_process

            with PipelineController(session_file=mock_session_file) as controller:
                controller.start_display()
                # Process should be running
                assert controller.display_process is not None

            # After context exit, should be stopped
            assert mock_process.terminate.called

    def test_atexit_cleanup(self, mock_session_file):
        """Test that cleanup is registered with atexit."""
        from plugins.autonomous_dev.scripts.pipeline_controller import PipelineController

        with patch('atexit.register') as mock_register:
            controller = PipelineController(session_file=mock_session_file)

            # Should register cleanup function
            assert mock_register.called
            # Verify cleanup function was registered
            registered_func = mock_register.call_args[0][0]
            assert callable(registered_func)

    # ========================================
    # SIGNAL HANDLING TESTS
    # ========================================

    def test_register_signal_handlers(self, mock_session_file):
        """Test that signal handlers are registered."""
        from plugins.autonomous_dev.scripts.pipeline_controller import PipelineController

        with patch('signal.signal') as mock_signal:
            controller = PipelineController(session_file=mock_session_file)
            controller.register_signal_handlers()

            # Should register handlers for SIGTERM and SIGINT
            calls = mock_signal.call_args_list
            signals = [call[0][0] for call in calls]

            assert signal.SIGTERM in signals
            assert signal.SIGINT in signals

    def test_signal_handler_stops_display(self, mock_session_file):
        """Test that signal handler stops display."""
        from plugins.autonomous_dev.scripts.pipeline_controller import PipelineController

        controller = PipelineController(session_file=mock_session_file)

        with patch('subprocess.Popen') as mock_popen:
            mock_process = Mock()
            mock_process.pid = 12345
            mock_process.poll.return_value = None
            mock_popen.return_value = mock_process

            controller.start_display()

            # Call signal handler directly
            controller.handle_signal(signal.SIGTERM, None)

            # Should have stopped display
            assert mock_process.terminate.called

    # ========================================
    # ERROR HANDLING TESTS
    # ========================================

    def test_start_display_handles_file_not_found(self, mock_session_file):
        """Test handling when progress_display.py is not found."""
        from plugins.autonomous_dev.scripts.pipeline_controller import PipelineController

        controller = PipelineController(session_file=mock_session_file)

        with patch('subprocess.Popen', side_effect=FileNotFoundError):
            with pytest.raises(FileNotFoundError):
                controller.start_display()

    def test_start_display_handles_permission_error(self, mock_session_file):
        """Test handling permission error when starting subprocess."""
        from plugins.autonomous_dev.scripts.pipeline_controller import PipelineController

        controller = PipelineController(session_file=mock_session_file)

        with patch('subprocess.Popen', side_effect=PermissionError):
            with pytest.raises(PermissionError):
                controller.start_display()

    def test_stop_display_handles_process_not_found(self, mock_session_file):
        """Test handling when process disappears before stop."""
        from plugins.autonomous_dev.scripts.pipeline_controller import PipelineController

        controller = PipelineController(session_file=mock_session_file)

        with patch('subprocess.Popen') as mock_popen:
            mock_process = Mock()
            mock_process.pid = 12345
            mock_process.poll.return_value = None
            mock_process.terminate.side_effect = ProcessLookupError
            mock_popen.return_value = mock_process

            controller.start_display()
            controller.stop_display()  # Should handle gracefully

    # ========================================
    # PROCESS MONITORING TESTS
    # ========================================

    def test_check_display_health(self, mock_session_file):
        """Test checking if display process is healthy."""
        from plugins.autonomous_dev.scripts.pipeline_controller import PipelineController

        controller = PipelineController(session_file=mock_session_file)

        with patch('subprocess.Popen') as mock_popen:
            mock_process = Mock()
            mock_process.pid = 12345
            mock_process.poll.return_value = None  # Still running
            mock_popen.return_value = mock_process

            controller.start_display()

            assert controller.is_display_running() is True

            # Simulate process exit
            mock_process.poll.return_value = 0
            assert controller.is_display_running() is False

    def test_restart_display_if_crashed(self, mock_session_file):
        """Test restarting display if it crashes."""
        from plugins.autonomous_dev.scripts.pipeline_controller import PipelineController

        controller = PipelineController(session_file=mock_session_file)

        with patch('subprocess.Popen') as mock_popen:
            mock_process = Mock()
            mock_process.pid = 12345
            # First call: running, second call: crashed, third call: restarted
            mock_process.poll.side_effect = [None, 1, None]
            mock_popen.return_value = mock_process

            controller.start_display()

            # Simulate crash detection and restart
            if not controller.is_display_running():
                controller.start_display()

            # Should have attempted to create new process
            assert mock_popen.call_count >= 1

    def test_get_display_status(self, mock_session_file):
        """Test getting display status information."""
        from plugins.autonomous_dev.scripts.pipeline_controller import PipelineController

        controller = PipelineController(session_file=mock_session_file)

        with patch('subprocess.Popen') as mock_popen:
            mock_process = Mock()
            mock_process.pid = 12345
            mock_process.poll.return_value = None
            mock_popen.return_value = mock_process

            controller.start_display()

            status = controller.get_status()

            assert status["running"] is True
            assert status["pid"] == 12345
            assert "session_file" in status
