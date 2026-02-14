#!/usr/bin/env python3
"""Tests for GitHub issue manager."""

import json
import subprocess
import sys
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock
import pytest

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from plugins.autonomous_dev.hooks.archived.github_issue_manager import GitHubIssueManager


class TestGitHubIssueManager:
    """Test GitHub issue creation and closure."""

    def test_gh_cli_available(self):
        """Test detection of gh CLI availability."""
        with patch('subprocess.run') as mock_run:
            mock_run.return_value = Mock(returncode=0)
            manager = GitHubIssueManager()
            assert manager.enabled is True

    def test_gh_cli_unavailable(self):
        """Test graceful degradation when gh CLI missing."""
        with patch('subprocess.run', side_effect=FileNotFoundError):
            manager = GitHubIssueManager()
            assert manager.enabled is False

    def test_create_issue_success(self, tmp_path):
        """Test successful issue creation."""
        session_file = tmp_path / "session.json"
        session_file.write_text("{}")

        with patch('subprocess.run') as mock_run:
            # Mock gh auth status (for __init__)
            auth_result = Mock(returncode=0)
            # Mock gh issue create
            create_result = Mock(
                returncode=0,
                stdout="https://github.com/user/repo/issues/42\n",
                stderr=""
            )
            mock_run.side_effect = [auth_result, create_result]

            # Mock _is_git_repo
            with patch.object(GitHubIssueManager, '_is_git_repo', return_value=True):
                manager = GitHubIssueManager()
                issue_number = manager.create_issue("Test feature", session_file)

            assert issue_number == 42

    def test_create_issue_no_git_repo(self, tmp_path, monkeypatch):
        """Test skipping issue creation in non-git directory."""
        monkeypatch.chdir(tmp_path)
        session_file = tmp_path / "session.json"
        session_file.write_text("{}")

        with patch('subprocess.run') as mock_run:
            mock_run.return_value = Mock(returncode=0)
            manager = GitHubIssueManager()
            issue_number = manager.create_issue("Test", session_file)

            assert issue_number is None

    def test_create_issue_cli_not_available(self, tmp_path):
        """Test skipping issue creation when gh CLI unavailable."""
        session_file = tmp_path / "session.json"
        session_file.write_text("{}")

        with patch('subprocess.run', side_effect=FileNotFoundError):
            manager = GitHubIssueManager()
            issue_number = manager.create_issue("Test", session_file)

            assert issue_number is None

    def test_close_issue_success(self):
        """Test successful issue closure."""
        session_data = {
            "session_id": "20251103-143022",
            "agents": [
                {
                    "agent": "researcher",
                    "status": "completed",
                    "duration_seconds": 120
                },
                {
                    "agent": "implementer",
                    "status": "completed",
                    "duration_seconds": 300
                }
            ]
        }

        with patch('subprocess.run') as mock_run:
            # Mock gh auth status (for __init__)
            auth_result = Mock(returncode=0)
            # Mock all gh commands (comment, close, edit)
            success_result = Mock(returncode=0, stdout="", stderr="")
            mock_run.side_effect = [auth_result, success_result, success_result, success_result]

            manager = GitHubIssueManager()
            result = manager.close_issue(42, session_data)

            assert result is True
            # Verify comment, close, and label commands called
            assert mock_run.call_count >= 3

    def test_close_issue_with_commits(self):
        """Test closing issue with commit references."""
        session_data = {
            "session_id": "20251103-143022",
            "agents": [
                {"agent": "test", "status": "completed", "duration_seconds": 60}
            ]
        }
        commits = ["abc123", "def456"]

        with patch('subprocess.run') as mock_run:
            # Mock gh auth status (for __init__)
            auth_result = Mock(returncode=0)
            # Mock all gh commands
            success_result = Mock(returncode=0, stdout="", stderr="")
            mock_run.side_effect = [auth_result, success_result, success_result, success_result]

            manager = GitHubIssueManager()
            result = manager.close_issue(42, session_data, commits=commits)

            assert result is True
            # Verify commit info included in comment
            call_args = str(mock_run.call_args_list)
            assert "abc123" in call_args
            assert "def456" in call_args

    def test_close_issue_cli_not_available(self):
        """Test graceful handling when gh CLI unavailable during close."""
        session_data = {
            "session_id": "20251103-143022",
            "agents": []
        }

        with patch('subprocess.run', side_effect=FileNotFoundError):
            manager = GitHubIssueManager()
            result = manager.close_issue(42, session_data)

            assert result is False

    def test_create_issue_timeout(self, tmp_path):
        """Test handling of timeout during issue creation."""
        session_file = tmp_path / "session.json"
        session_file.write_text("{}")

        with patch('subprocess.run') as mock_run:
            # Mock gh auth status (for __init__)
            auth_result = Mock(returncode=0)
            # Mock timeout on gh issue create
            mock_run.side_effect = [auth_result, subprocess.TimeoutExpired("gh", 30)]

            with patch.object(GitHubIssueManager, '_is_git_repo', return_value=True):
                manager = GitHubIssueManager()
                issue_number = manager.create_issue("Test", session_file)

            assert issue_number is None

    def test_close_issue_timeout(self):
        """Test handling of timeout during issue closure."""
        session_data = {
            "session_id": "20251103-143022",
            "agents": []
        }

        with patch('subprocess.run') as mock_run:
            # Mock gh auth status (for __init__)
            auth_result = Mock(returncode=0)
            # Mock timeout on gh issue command
            mock_run.side_effect = [auth_result, subprocess.TimeoutExpired("gh", 30)]

            manager = GitHubIssueManager()
            result = manager.close_issue(42, session_data)

            assert result is False


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
