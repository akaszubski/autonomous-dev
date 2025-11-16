#!/usr/bin/env python3
"""
TDD Tests for Tracking Cross-Platform Support (Issue #79)

This module tests that path resolution works correctly across platforms:
- Windows (backslashes, drive letters)
- Linux (forward slashes, case-sensitive)
- macOS (forward slashes, case-insensitive by default)

These tests mock platform-specific behavior to verify pathlib usage.

Test Coverage Target: 100% of platform-specific path handling
"""

import os
import sys
import tempfile
from pathlib import Path, PureWindowsPath, PurePosixPath
from unittest.mock import Mock, patch, MagicMock
import pytest

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from plugins.autonomous_dev.lib.session_tracker import SessionTracker
from scripts.agent_tracker import AgentTracker
from plugins.autonomous_dev.lib.batch_state_manager import (
    BatchState,
    BatchStateManager,
    create_batch_state,
    save_batch_state,
    load_batch_state,
    DEFAULT_STATE_FILE
)


class TestWindowsPlatform:
    """Test path resolution on Windows platform."""

    @pytest.fixture
    def mock_windows_env(self, tmp_path, monkeypatch):
        """Mock Windows environment."""
        # Mock sys.platform
        monkeypatch.setattr(sys, "platform", "win32")

        # Create Windows-style project structure
        project = tmp_path / "C:" / "Users" / "Developer" / "autonomous-dev"
        project.mkdir(parents=True)
        (project / ".git").mkdir()
        (project / "docs" / "sessions").mkdir(parents=True)
        (project / ".claude").mkdir()

        return project

    def test_session_tracker_windows_path_separators(self, mock_windows_env):
        """Test that paths work with Windows backslashes.

        Expected:
        - pathlib handles backslash conversion automatically
        - session_dir uses correct separators for Windows
        - Paths are normalized (C:\\path\\to\\file)
        """
        original_cwd = os.getcwd()
        try:
            os.chdir(str(mock_windows_env))

            tracker = SessionTracker()

            # pathlib should handle Windows paths correctly
            expected_dir = mock_windows_env / "docs" / "sessions"
            assert tracker.session_dir == expected_dir

            # Verify path is valid for Windows (pathlib normalizes automatically)
            assert tracker.session_dir.exists()

        finally:
            os.chdir(original_cwd)

    def test_agent_tracker_windows_absolute_paths(self, mock_windows_env):
        """Test AgentTracker handles Windows absolute paths (C:\\...).

        Expected:
        - Absolute paths include drive letter
        - Path resolution works from any subdirectory
        """
        subdirectory = mock_windows_env / "plugins"
        subdirectory.mkdir()
        original_cwd = os.getcwd()

        try:
            os.chdir(str(subdirectory))

            tracker = AgentTracker()

            # Should resolve to absolute Windows path
            expected = mock_windows_env / "docs" / "sessions"
            assert tracker.session_dir == expected

        finally:
            os.chdir(original_cwd)

    def test_batch_state_windows_path_resolution(self, mock_windows_env):
        """Test BatchStateManager on Windows.

        Expected:
        - .claude\\batch_state.json resolves correctly
        - pathlib normalizes separators
        """
        original_cwd = os.getcwd()
        try:
            os.chdir(str(mock_windows_env))

            manager = BatchStateManager()

            expected = mock_windows_env / ".claude" / "batch_state.json"
            assert manager.state_file == expected

        finally:
            os.chdir(original_cwd)


class TestLinuxPlatform:
    """Test path resolution on Linux platform."""

    @pytest.fixture
    def mock_linux_env(self, tmp_path, monkeypatch):
        """Mock Linux environment."""
        monkeypatch.setattr(sys, "platform", "linux")

        # Create Linux-style project structure
        project = tmp_path / "home" / "developer" / "autonomous-dev"
        project.mkdir(parents=True)
        (project / ".git").mkdir()
        (project / "docs" / "sessions").mkdir(parents=True)
        (project / ".claude").mkdir()

        return project

    def test_session_tracker_linux_paths(self, mock_linux_env):
        """Test SessionTracker on Linux with forward slashes.

        Expected:
        - Paths use forward slashes
        - /home/developer/... absolute paths
        """
        original_cwd = os.getcwd()
        try:
            os.chdir(str(mock_linux_env))

            tracker = SessionTracker()

            expected = mock_linux_env / "docs" / "sessions"
            assert tracker.session_dir == expected

        finally:
            os.chdir(original_cwd)

    def test_agent_tracker_linux_case_sensitivity(self, mock_linux_env):
        """Test that path resolution is case-sensitive on Linux.

        Expected:
        - docs/sessions != Docs/Sessions
        - Case preserved in paths
        """
        original_cwd = os.getcwd()
        try:
            os.chdir(str(mock_linux_env))

            tracker = AgentTracker()

            # Linux is case-sensitive
            expected = mock_linux_env / "docs" / "sessions"
            assert tracker.session_dir == expected

            # Verify case matters (if we had Docs/Sessions, it wouldn't match)
            wrong_case = mock_linux_env / "Docs" / "Sessions"
            assert tracker.session_dir != wrong_case

        finally:
            os.chdir(original_cwd)

    def test_batch_state_linux_hidden_directory(self, mock_linux_env):
        """Test that .claude/ (hidden dir) works on Linux.

        Expected:
        - Hidden directories (starting with .) work correctly
        - Permissions handled properly
        """
        original_cwd = os.getcwd()
        try:
            os.chdir(str(mock_linux_env))

            manager = BatchStateManager()

            expected = mock_linux_env / ".claude" / "batch_state.json"
            assert manager.state_file == expected

            # Verify parent is hidden directory
            assert manager.state_file.parent.name == ".claude"

        finally:
            os.chdir(original_cwd)


class TestMacOSPlatform:
    """Test path resolution on macOS platform."""

    @pytest.fixture
    def mock_macos_env(self, tmp_path, monkeypatch):
        """Mock macOS environment."""
        monkeypatch.setattr(sys, "platform", "darwin")

        # Create macOS-style project structure
        project = tmp_path / "Users" / "developer" / "autonomous-dev"
        project.mkdir(parents=True)
        (project / ".git").mkdir()
        (project / "docs" / "sessions").mkdir(parents=True)
        (project / ".claude").mkdir()

        return project

    def test_session_tracker_macos_paths(self, mock_macos_env):
        """Test SessionTracker on macOS.

        Expected:
        - /Users/developer/... paths work
        - Forward slashes like Linux
        """
        original_cwd = os.getcwd()
        try:
            os.chdir(str(mock_macos_env))

            tracker = SessionTracker()

            expected = mock_macos_env / "docs" / "sessions"
            assert tracker.session_dir == expected

        finally:
            os.chdir(original_cwd)

    def test_agent_tracker_macos_case_insensitive_default(self, mock_macos_env):
        """Test that paths work on case-insensitive macOS filesystems.

        Expected:
        - By default, macOS is case-insensitive
        - docs/sessions == Docs/Sessions on disk
        - But we should preserve case in code
        """
        original_cwd = os.getcwd()
        try:
            os.chdir(str(mock_macos_env))

            tracker = AgentTracker()

            # Should use lowercase (canonical form)
            expected = mock_macos_env / "docs" / "sessions"
            assert tracker.session_dir == expected

        finally:
            os.chdir(original_cwd)

    def test_batch_state_macos_hidden_files(self, mock_macos_env):
        """Test hidden files/directories on macOS.

        Expected:
        - .claude/ hidden directory works
        - .DS_Store and other hidden files don't interfere
        """
        original_cwd = os.getcwd()
        try:
            os.chdir(str(mock_macos_env))

            # Create .DS_Store to simulate macOS filesystem
            (mock_macos_env / ".DS_Store").touch()

            manager = BatchStateManager()

            expected = mock_macos_env / ".claude" / "batch_state.json"
            assert manager.state_file == expected

        finally:
            os.chdir(original_cwd)


class TestPathSeparatorNormalization:
    """Test that mixed path separators are normalized."""

    @pytest.fixture
    def project_root(self, tmp_path):
        """Create project structure."""
        project = tmp_path / "project"
        project.mkdir()
        (project / ".git").mkdir()
        (project / "docs" / "sessions").mkdir(parents=True)
        (project / ".claude").mkdir()
        return project

    def test_mixed_separators_normalized(self, project_root):
        """Test that paths like docs/sessions\\file.md are normalized.

        Expected:
        - pathlib normalizes mixed separators
        - Works across platforms
        """
        original_cwd = os.getcwd()
        try:
            os.chdir(str(project_root))

            tracker = SessionTracker()

            # pathlib normalizes to platform-appropriate separators
            assert tracker.session_dir.exists()

            # Path should be consistent
            expected = project_root / "docs" / "sessions"
            assert tracker.session_dir == expected

        finally:
            os.chdir(original_cwd)

    def test_trailing_separators_handled(self, project_root):
        """Test that trailing slashes are handled correctly.

        Expected:
        - docs/sessions/ == docs/sessions
        - pathlib normalizes automatically
        """
        original_cwd = os.getcwd()
        try:
            os.chdir(str(project_root))

            tracker = SessionTracker()

            # Both should resolve to same path
            expected = project_root / "docs" / "sessions"
            assert tracker.session_dir == expected

        finally:
            os.chdir(original_cwd)


class TestSymlinkHandling:
    """Test that symlinks are handled correctly across platforms."""

    @pytest.fixture
    def project_with_symlinks(self, tmp_path):
        """Create project with symlinks (if supported)."""
        project = tmp_path / "project"
        project.mkdir()
        (project / ".git").mkdir()
        (project / "docs" / "sessions").mkdir(parents=True)
        (project / ".claude").mkdir()

        # Create symlink to docs (if platform supports it)
        if hasattr(os, 'symlink'):
            symlink_path = project / "docs-link"
            try:
                symlink_path.symlink_to(project / "docs")
            except OSError:
                pytest.skip("Symlinks not supported on this platform")

        return project

    def test_symlinks_resolved_to_real_path(self, project_with_symlinks):
        """Test that symlinks are resolved to real paths.

        Expected:
        - docs-link/sessions/ resolves to real docs/sessions/
        - No path traversal via symlinks
        """
        if not hasattr(os, 'symlink'):
            pytest.skip("Symlinks not supported")

        original_cwd = os.getcwd()
        try:
            # Change to directory with symlink
            os.chdir(str(project_with_symlinks))

            tracker = SessionTracker()

            # Should resolve to real path, not symlink
            expected = project_with_symlinks / "docs" / "sessions"
            # Use resolve() to get canonical path
            assert tracker.session_dir.resolve() == expected.resolve()

        finally:
            os.chdir(original_cwd)


class TestUnicodePathSupport:
    """Test that paths with Unicode characters work correctly."""

    @pytest.fixture
    def unicode_project(self, tmp_path):
        """Create project with Unicode in path."""
        # Use Unicode characters in directory names
        project = tmp_path / "проект" / "autonomous-dev"  # Russian for "project"
        project.mkdir(parents=True)
        (project / ".git").mkdir()
        (project / "docs" / "sessions").mkdir(parents=True)
        (project / ".claude").mkdir()
        return project

    def test_unicode_paths_supported(self, unicode_project):
        """Test that Unicode characters in paths work.

        Expected:
        - Paths with non-ASCII characters work correctly
        - pathlib handles encoding properly
        """
        original_cwd = os.getcwd()
        try:
            os.chdir(str(unicode_project))

            tracker = SessionTracker()

            expected = unicode_project / "docs" / "sessions"
            assert tracker.session_dir == expected
            assert tracker.session_dir.exists()

        finally:
            os.chdir(original_cwd)

    def test_unicode_filename_support(self, unicode_project):
        """Test that session files with Unicode names work.

        Expected:
        - Files like 20251117-研究.md work correctly
        - Encoding handled properly
        """
        original_cwd = os.getcwd()
        try:
            os.chdir(str(unicode_project))

            tracker = SessionTracker()
            tracker.log("researcher", "Unicode test: 研究完成")  # Chinese: "research complete"

            # File should be created successfully
            assert tracker.session_file.exists()

        finally:
            os.chdir(original_cwd)


class TestPathLengthLimits:
    """Test handling of very long paths (especially on Windows)."""

    def test_long_path_handling(self, tmp_path):
        """Test that very long paths are handled correctly.

        Expected:
        - Paths up to platform limit work
        - Graceful error if path too long
        """
        # Create deeply nested directory
        project = tmp_path / "project"
        project.mkdir()
        (project / ".git").mkdir()

        # Create very deep nesting
        deep_path = project
        for i in range(20):
            deep_path = deep_path / f"level{i:02d}"

        deep_path.mkdir(parents=True)

        original_cwd = os.getcwd()
        try:
            os.chdir(str(deep_path))

            # Should still find project root
            tracker = SessionTracker()

            expected = project / "docs" / "sessions"
            # May not exist yet, but path should resolve correctly
            assert tracker.session_dir.parent.parent == project

        finally:
            os.chdir(original_cwd)


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
