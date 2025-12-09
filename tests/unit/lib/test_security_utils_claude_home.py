#!/usr/bin/env python3
"""
Unit tests for ~/.claude/ path validation in security_utils.py

Tests for GitHub Issue #102: Security hook blocks writes to ~/.claude/

This module tests that the security_utils.validate_path() function properly
allows paths within ~/.claude/ directory while still maintaining security
for other paths outside PROJECT_ROOT.

Test Coverage:
- Valid paths within ~/.claude/ are allowed
- ~/.claude/plans/ allowed (Claude Code plan mode)
- ~/.claude/CLAUDE.md allowed (global instructions)
- ~/.claude/settings.json allowed (global settings)
- Symlinks within ~/.claude/ are still rejected
- Path traversal within ~/.claude/ is still rejected
- Paths outside both PROJECT_ROOT and ~/.claude/ are rejected

Author: test-master agent
Date: 2025-12-09
Issue: #102
"""

import os
import sys
import tempfile
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent / "plugins"))

from autonomous_dev.lib.security_utils import (
    validate_path,
    audit_log,
    PROJECT_ROOT,
    SYSTEM_TEMP,
    CLAUDE_HOME_DIR,
)


class TestClaudeHomeValidation:
    """Test ~/.claude/ path validation in security_utils.

    Security requirement: Allow paths within ~/.claude/ for Claude Code system
    operations while maintaining security for other paths.
    """

    @pytest.fixture
    def mock_claude_home(self, tmp_path, monkeypatch):
        """Create temporary ~/.claude/ directory for testing."""
        fake_home = tmp_path / "fake_home"
        fake_home.mkdir()
        fake_claude = fake_home / ".claude"
        fake_claude.mkdir()

        # Create subdirectories
        (fake_claude / "plans").mkdir()

        # Patch Path.home() to return our fake home
        monkeypatch.setattr(Path, "home", lambda: fake_home)

        # Also need to patch the module-level CLAUDE_HOME_DIR
        import autonomous_dev.lib.security_utils as security_module
        monkeypatch.setattr(security_module, "CLAUDE_HOME_DIR", fake_claude)

        return fake_claude

    def test_claude_home_dir_constant_exists(self):
        """Test that CLAUDE_HOME_DIR constant is exported.

        SECURITY: Constant should be available for external use.
        """
        assert CLAUDE_HOME_DIR is not None
        assert isinstance(CLAUDE_HOME_DIR, Path)
        assert ".claude" in str(CLAUDE_HOME_DIR)

    def test_valid_claude_home_path_allowed(self, mock_claude_home):
        """Test that valid paths within ~/.claude/ are allowed.

        SECURITY: ~/.claude/ is a safe, known location for Claude Code.
        Expected: validate_path() returns resolved path without error.
        """
        valid_path = mock_claude_home / "CLAUDE.md"
        valid_path.touch()

        # Should not raise exception
        result = validate_path(valid_path, "global CLAUDE.md")

        assert result == valid_path.resolve()

    def test_claude_home_plans_directory_allowed(self, mock_claude_home):
        """Test that ~/.claude/plans/ directory is allowed.

        SECURITY: Claude Code uses this for plan mode files.
        Expected: validate_path() allows plan files.
        """
        plans_dir = mock_claude_home / "plans"
        plan_file = plans_dir / "my-plan.md"
        plan_file.touch()

        # Should not raise exception
        result = validate_path(plan_file, "plan file")

        assert result == plan_file.resolve()

    def test_claude_home_nonexistent_path_allowed(self, mock_claude_home):
        """Test that nonexistent paths in ~/.claude/ are allowed.

        SECURITY: Files may not exist yet (e.g., new plan files).
        Expected: validate_path() allows future file creation.
        """
        future_path = mock_claude_home / "plans" / "future-plan.md"

        # Should not raise exception
        result = validate_path(future_path, "future plan", allow_missing=True)

        assert mock_claude_home in result.parents or result == mock_claude_home

    def test_claude_home_settings_allowed(self, mock_claude_home):
        """Test that ~/.claude/settings.json is allowed.

        SECURITY: Claude Code may use global settings file.
        Expected: validate_path() allows settings file.
        """
        settings_path = mock_claude_home / "settings.json"
        settings_path.touch()

        # Should not raise exception
        result = validate_path(settings_path, "global settings")

        assert result == settings_path.resolve()


class TestClaudeHomeSecurityBoundaries:
    """Test security boundaries are still enforced within ~/.claude/."""

    @pytest.fixture
    def mock_claude_home(self, tmp_path, monkeypatch):
        """Create temporary ~/.claude/ directory for testing."""
        fake_home = tmp_path / "fake_home"
        fake_home.mkdir()
        fake_claude = fake_home / ".claude"
        fake_claude.mkdir()

        # Patch Path.home() and CLAUDE_HOME_DIR
        monkeypatch.setattr(Path, "home", lambda: fake_home)
        import autonomous_dev.lib.security_utils as security_module
        monkeypatch.setattr(security_module, "CLAUDE_HOME_DIR", fake_claude)

        return fake_claude

    def test_path_traversal_from_claude_home_blocked(self, mock_claude_home):
        """Test that path traversal from ~/.claude/ is blocked.

        SECURITY: Prevent escaping ~/.claude/ via ../
        Expected: ValueError raised for path traversal attempts.
        """
        # Attempt to escape ~/.claude/ via path traversal
        malicious_path = mock_claude_home / ".." / ".." / "etc" / "passwd"

        with pytest.raises(ValueError) as exc_info:
            validate_path(malicious_path, "malicious path")

        assert "path traversal" in str(exc_info.value).lower()

    def test_symlink_in_claude_home_blocked(self, mock_claude_home, tmp_path):
        """Test that symlinks within ~/.claude/ are blocked.

        SECURITY: Prevent symlink attacks even within ~/.claude/.
        Expected: ValueError raised for symlinks.
        """
        # Create a symlink inside ~/.claude/ pointing outside
        outside_target = tmp_path / "outside.json"
        outside_target.touch()

        symlink_path = mock_claude_home / "symlink.json"

        if hasattr(os, 'symlink'):
            try:
                symlink_path.symlink_to(outside_target)

                with pytest.raises(ValueError) as exc_info:
                    validate_path(symlink_path, "symlink test")

                assert "symlink" in str(exc_info.value).lower()
            except OSError:
                pytest.skip("Symlinks not supported on this system")
        else:
            pytest.skip("Symlinks not available")


class TestPathsOutsideAllowedLocations:
    """Test that paths outside PROJECT_ROOT and ~/.claude/ are blocked."""

    def test_system_directories_still_blocked(self):
        """Test that system directories are always blocked.

        SECURITY: Never allow writes to /etc, /usr, /var, etc.
        Expected: ValueError for all system paths.
        """
        system_paths = [
            Path("/etc/passwd"),
            Path("/var/log/evil.json"),
            Path("/usr/bin/malware"),
        ]

        for sys_path in system_paths:
            with pytest.raises(ValueError) as exc_info:
                validate_path(sys_path, "system path test")

            error_msg = str(exc_info.value).lower()
            assert "outside" in error_msg or "allowed" in error_msg

    def test_arbitrary_home_subdirectory_blocked(self, tmp_path, monkeypatch):
        """Test that arbitrary home subdirectories are blocked.

        SECURITY: Only ~/.claude/ is allowed, not ~/* in general.
        Expected: ValueError for paths in home but not in ~/.claude/.
        """
        fake_home = tmp_path / "fake_home"
        fake_home.mkdir()

        # Create a non-.claude directory in home
        other_dir = fake_home / ".other_app"
        other_dir.mkdir()

        # Patch Path.home()
        monkeypatch.setattr(Path, "home", lambda: fake_home)

        # Try to access ~/.other_app/ (should be blocked)
        other_path = other_dir / "config.json"
        other_path.touch()

        # Force test_mode=False to use production validation
        # (otherwise pytest test mode allows temp paths)
        with pytest.raises(ValueError):
            validate_path(other_path, "other home path", test_mode=False)


class TestErrorMessageQuality:
    """Test that error messages are helpful and include ~/.claude/ info."""

    def test_error_message_includes_claude_home(self):
        """Test that error messages mention ~/.claude/ as allowed location.

        UX: Users should know ~/.claude/ is allowed when they see errors.
        Expected: Error message lists ~/.claude/ as allowed location.
        """
        # Try to access a blocked path
        blocked_path = Path("/blocked/path/file.txt")

        with pytest.raises(ValueError) as exc_info:
            validate_path(blocked_path, "blocked path test")

        error_msg = str(exc_info.value)
        assert "Claude home" in error_msg or ".claude" in error_msg


# Run tests
if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
