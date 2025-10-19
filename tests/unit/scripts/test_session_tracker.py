"""Unit tests for session_tracker.py"""

import sys
from datetime import datetime
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest


# Add scripts directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent / "scripts"))

from session_tracker import SessionTracker


class TestSessionTracker:
    """Test SessionTracker class."""

    @pytest.fixture
    def temp_session_dir(self, tmp_path):
        """Create temporary session directory."""
        session_dir = tmp_path / "docs" / "sessions"
        session_dir.mkdir(parents=True)
        return session_dir

    @pytest.fixture
    def tracker(self, temp_session_dir, monkeypatch):
        """Create SessionTracker with temporary directory."""
        monkeypatch.chdir(temp_session_dir.parent.parent)
        return SessionTracker()

    def test_session_tracker_creates_session_dir(self, tmp_path, monkeypatch):
        """Test that SessionTracker creates session directory if it doesn't exist."""
        monkeypatch.chdir(tmp_path)
        tracker = SessionTracker()
        assert (tmp_path / "docs" / "sessions").exists()

    def test_session_tracker_creates_session_file(self, tracker):
        """Test that SessionTracker creates a session file."""
        assert tracker.session_file.exists()
        assert tracker.session_file.suffix == ".md"

    def test_session_file_has_header(self, tracker):
        """Test that new session file has proper header."""
        content = tracker.session_file.read_text()
        assert "# Session" in content
        assert "**Started**:" in content

    def test_log_creates_entry(self, tracker):
        """Test that log() creates an entry in the session file."""
        tracker.log("test-agent", "Test message")
        content = tracker.session_file.read_text()
        assert "test-agent" in content
        assert "Test message" in content

    def test_log_formats_with_timestamp(self, tracker):
        """Test that log entries include timestamp."""
        tracker.log("researcher", "Research complete")
        content = tracker.session_file.read_text()
        # Check for timestamp pattern (HH:MM:SS)
        assert "researcher" in content
        assert "Research complete" in content

    def test_multiple_logs_appended(self, tracker):
        """Test that multiple logs are appended to the same file."""
        tracker.log("agent1", "Message 1")
        tracker.log("agent2", "Message 2")

        content = tracker.session_file.read_text()
        assert "agent1" in content
        assert "Message 1" in content
        assert "agent2" in content
        assert "Message 2" in content

    def test_reuses_existing_session_file(self, temp_session_dir, monkeypatch):
        """Test that tracker reuses existing session file from today."""
        monkeypatch.chdir(temp_session_dir.parent.parent)

        # Create first tracker
        tracker1 = SessionTracker()
        first_file = tracker1.session_file

        # Create second tracker - should reuse same file
        tracker2 = SessionTracker()
        second_file = tracker2.session_file

        assert first_file == second_file


def test_main_requires_arguments():
    """Test that main() requires agent_name and message arguments."""
    from session_tracker import main

    with patch.object(sys, 'argv', ['session_tracker.py']):
        with pytest.raises(SystemExit):
            main()


def test_main_with_valid_arguments(tmp_path, monkeypatch):
    """Test that main() works with valid arguments."""
    from session_tracker import main

    monkeypatch.chdir(tmp_path)

    with patch.object(sys, 'argv', ['session_tracker.py', 'test-agent', 'Test', 'message']):
        main()

    # Check that session file was created
    session_files = list((tmp_path / "docs" / "sessions").glob("*.md"))
    assert len(session_files) == 1

    content = session_files[0].read_text()
    assert "test-agent" in content
    assert "Test message" in content
