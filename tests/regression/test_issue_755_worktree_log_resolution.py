#!/usr/bin/env python3
"""
Regression test for Issue #755: Worktree log resolution in session_activity_logger.

Problem: _find_log_dir() walks up from CWD to find .claude. When running in a
worktree (.worktrees/batch-*/), the worktree has its own .claude directory, so
logs go to the WORKTREE's .claude/logs/activity/ instead of the PARENT repo's.
This causes downstream agents' events to be missed by post-session analysis.

Fix: _find_log_dir() detects worktree paths and uses git to resolve to the
parent repo's .claude directory.
"""

import subprocess
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# Portable project root detection
_current = Path.cwd()
while _current != _current.parent:
    if (_current / ".git").exists() or (_current / ".claude").exists():
        PROJECT_ROOT = _current
        break
    _current = _current.parent
else:
    PROJECT_ROOT = Path.cwd()

sys.path.insert(0, str(PROJECT_ROOT / "plugins" / "autonomous-dev" / "hooks"))

from session_activity_logger import _find_log_dir

# Issue #1779 (AC1): these tests' SUBJECT is activity-root INFERENCE, so the
# session-wide redirect from tests/conftest.py must not stand in front of it.
from tests.helpers.state_isolation import (  # noqa: E402,F401
    activity_root_inference_is_the_subject,
)


class TestWorktreeLogResolution:
    """Regression tests for Issue #755: worktree log path resolution."""

    def test_worktree_cwd_resolves_to_parent_log_dir(self, tmp_path: Path) -> None:
        """When CWD is inside a .worktrees/ directory, _find_log_dir should
        resolve to the PARENT repo's .claude/logs/activity/ directory."""
        # Set up parent repo with .claude directory
        parent_repo = tmp_path / "repo"
        parent_claude = parent_repo / ".claude"
        parent_claude.mkdir(parents=True)

        # Set up worktree with its own .claude (the problematic scenario)
        worktree = parent_repo / ".worktrees" / "batch-123"
        worktree_claude = worktree / ".claude"
        worktree_claude.mkdir(parents=True)

        # Mock CWD to be inside the worktree
        with patch("session_activity_logger.Path") as mock_path_cls:
            mock_cwd = MagicMock()
            mock_cwd.__str__ = lambda self: str(worktree)
            mock_cwd.parents = list(worktree.parents)
            mock_path_cls.cwd.return_value = mock_cwd

            # Mock subprocess to return parent repo's .git directory
            mock_result = MagicMock()
            mock_result.returncode = 0
            mock_result.stdout = str(parent_repo / ".git") + "\n"

            with patch("subprocess.run", return_value=mock_result) as mock_run:
                # Also need Path() constructor to work normally for the git result
                mock_path_cls.side_effect = lambda x: Path(x)

                result = _find_log_dir()

            # Verify git was called with correct args
            mock_run.assert_called_once()
            call_args = mock_run.call_args
            assert "git" in call_args[0][0]
            assert "--git-common-dir" in call_args[0][0]

        assert result == parent_claude / "logs" / "activity"

    def test_non_worktree_cwd_uses_normal_resolution(self, tmp_path: Path) -> None:
        """When CWD is NOT inside a .worktrees/ directory, _find_log_dir should
        use the normal walk-up resolution to find .claude."""
        # Set up a normal repo with .claude
        repo = tmp_path / "repo"
        claude_dir = repo / ".claude"
        claude_dir.mkdir(parents=True)

        with patch("session_activity_logger.Path") as mock_path_cls:
            mock_cwd = MagicMock()
            mock_cwd.__str__ = lambda self: str(repo)
            mock_cwd.parents = list(repo.parents)

            # Make iteration work: [cwd] + list(cwd.parents)
            # The for loop needs .claude check to work
            mock_path_cls.cwd.return_value = mock_cwd

            # Path needs to work normally for claude_dir checks
            mock_path_cls.side_effect = lambda x: Path(x)

            # The __truediv__ on mock_cwd needs to return real Paths
            mock_cwd.__truediv__ = lambda self, other: repo / other

            result = _find_log_dir()

        assert result == claude_dir / "logs" / "activity"

    def test_worktree_git_failure_falls_through(self, tmp_path: Path) -> None:
        """When CWD is a worktree but git command fails, _find_log_dir should
        fall through to normal walk-up resolution."""
        # Set up worktree with its own .claude
        parent_repo = tmp_path / "repo"
        worktree = parent_repo / ".worktrees" / "batch-456"
        worktree_claude = worktree / ".claude"
        worktree_claude.mkdir(parents=True)

        with patch("session_activity_logger.Path") as mock_path_cls:
            mock_cwd = MagicMock()
            mock_cwd.__str__ = lambda self: str(worktree)
            mock_cwd.parents = list(worktree.parents)
            mock_cwd.__truediv__ = lambda self, other: worktree / other

            mock_path_cls.cwd.return_value = mock_cwd
            mock_path_cls.side_effect = lambda x: Path(x)

            # Git command fails
            mock_result = MagicMock()
            mock_result.returncode = 1
            mock_result.stdout = ""

            with patch("subprocess.run", return_value=mock_result):
                result = _find_log_dir()

        # Falls through to normal resolution, finds worktree's .claude
        assert result == worktree_claude / "logs" / "activity"

    def test_worktree_parent_claude_missing_falls_through(self, tmp_path: Path) -> None:
        """When worktree detection succeeds but parent repo has no .claude,
        _find_log_dir should fall through to normal resolution."""
        # Parent repo WITHOUT .claude
        parent_repo = tmp_path / "repo"
        parent_repo.mkdir(parents=True)

        # Worktree WITH .claude
        worktree = parent_repo / ".worktrees" / "batch-789"
        worktree_claude = worktree / ".claude"
        worktree_claude.mkdir(parents=True)

        with patch("session_activity_logger.Path") as mock_path_cls:
            mock_cwd = MagicMock()
            mock_cwd.__str__ = lambda self: str(worktree)
            mock_cwd.parents = list(worktree.parents)
            mock_cwd.__truediv__ = lambda self, other: worktree / other

            mock_path_cls.cwd.return_value = mock_cwd
            mock_path_cls.side_effect = lambda x: Path(x)

            # Git returns parent repo's .git, but parent has no .claude
            mock_result = MagicMock()
            mock_result.returncode = 0
            mock_result.stdout = str(parent_repo / ".git") + "\n"

            with patch("subprocess.run", return_value=mock_result):
                result = _find_log_dir()

        # Falls through to normal resolution, finds worktree's .claude
        assert result == worktree_claude / "logs" / "activity"
