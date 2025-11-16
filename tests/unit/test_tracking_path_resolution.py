#!/usr/bin/env python3
"""
TDD Tests for Tracking Path Resolution (Issue #79)

This module contains FAILING tests (TDD red phase) for fixing hardcoded paths:
- session_tracker.py line 25: hardcoded Path("docs/sessions")
- agent_tracker.py line 179: hardcoded Path("docs/sessions")
- batch_state_manager.py line 118: hardcoded Path(".claude/batch_state.json")

These tests will fail until paths are resolved dynamically from PROJECT_ROOT.

Security Requirements:
1. All paths must resolve from PROJECT_ROOT (not current working directory)
2. Paths must work from any subdirectory
3. No hardcoded relative paths

Test Coverage Target: 100% of path resolution code paths
"""

import os
import sys
import tempfile
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock
import pytest

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from plugins.autonomous_dev.lib.session_tracker import SessionTracker
from scripts.agent_tracker import AgentTracker
from plugins.autonomous_dev.lib.batch_state_manager import (
    BatchState,
    create_batch_state,
    save_batch_state,
    load_batch_state,
    get_default_state_file  # Use function for testing (lazy evaluation)
)


class TestSessionTrackerPathResolution:
    """Test that SessionTracker resolves paths from PROJECT_ROOT, not cwd."""

    @pytest.fixture
    def mock_project_root(self, tmp_path):
        """Create a mock project root directory."""
        project_root = tmp_path / "project"
        project_root.mkdir()
        (project_root / ".git").mkdir()  # Required for PROJECT_ROOT detection
        (project_root / "docs").mkdir()
        (project_root / "docs" / "sessions").mkdir()
        return project_root

    def test_session_tracker_uses_project_root_not_cwd(self, mock_project_root):
        """Test SessionTracker resolves session_dir from PROJECT_ROOT.

        CRITICAL: session_tracker.py line 25 has hardcoded Path("docs/sessions")
        This fails when running from subdirectories like plugins/ or scripts/

        Expected behavior:
        - Resolve PROJECT_ROOT first (search for .git or .claude/)
        - session_dir = PROJECT_ROOT / "docs" / "sessions"
        - Works regardless of current working directory

        Current behavior (SHOULD FAIL):
        - Uses Path("docs/sessions") relative to cwd
        - Fails when cwd != project root
        """
        # Change to subdirectory to expose the bug
        subdirectory = mock_project_root / "plugins"
        subdirectory.mkdir()
        original_cwd = os.getcwd()

        try:
            os.chdir(str(subdirectory))

            # This should work from any subdirectory
            tracker = SessionTracker()

            # Expected: session_dir resolves to PROJECT_ROOT/docs/sessions
            expected_session_dir = mock_project_root / "docs" / "sessions"
            assert tracker.session_dir == expected_session_dir, (
                f"SessionTracker should resolve from PROJECT_ROOT, not cwd. "
                f"Expected: {expected_session_dir}, "
                f"Got: {tracker.session_dir}"
            )

            # Verify session files are created in correct location
            assert tracker.session_file.parent == expected_session_dir

        finally:
            os.chdir(original_cwd)

    def test_session_tracker_resolves_project_root_from_git(self, tmp_path):
        """Test PROJECT_ROOT detection via .git directory.

        Expected:
        - Search upward from cwd for .git/ directory
        - PROJECT_ROOT = directory containing .git/
        - session_dir = PROJECT_ROOT / "docs" / "sessions"
        """
        # Create mock project structure
        project_root = tmp_path / "my-project"
        project_root.mkdir()
        (project_root / ".git").mkdir()
        (project_root / "docs" / "sessions").mkdir(parents=True)

        # Run from nested subdirectory
        nested_dir = project_root / "src" / "lib"
        nested_dir.mkdir(parents=True)
        original_cwd = os.getcwd()

        try:
            os.chdir(str(nested_dir))

            tracker = SessionTracker()

            # Should resolve to project root, not nested dir
            expected = project_root / "docs" / "sessions"
            assert tracker.session_dir == expected

        finally:
            os.chdir(original_cwd)

    def test_session_tracker_resolves_project_root_from_claude_dir(self, tmp_path):
        """Test PROJECT_ROOT detection via .claude/ directory.

        Expected:
        - If no .git/, search for .claude/ directory
        - PROJECT_ROOT = directory containing .claude/
        - session_dir = PROJECT_ROOT / "docs" / "sessions"
        """
        # Create project without .git (might use .claude/ only)
        project_root = tmp_path / "my-project"
        project_root.mkdir()
        (project_root / ".claude").mkdir()
        (project_root / "docs" / "sessions").mkdir(parents=True)

        nested_dir = project_root / "plugins"
        nested_dir.mkdir()
        original_cwd = os.getcwd()

        try:
            os.chdir(str(nested_dir))

            tracker = SessionTracker()

            expected = project_root / "docs" / "sessions"
            assert tracker.session_dir == expected

        finally:
            os.chdir(original_cwd)

    def test_session_tracker_creates_missing_sessions_directory(self, tmp_path):
        """Test that session_dir is auto-created if missing.

        Expected:
        - Detect PROJECT_ROOT correctly
        - If docs/sessions/ doesn't exist, create it
        - No errors if directory already exists
        """
        project_root = tmp_path / "project"
        project_root.mkdir()
        (project_root / ".git").mkdir()
        # Don't create docs/sessions - should be auto-created

        original_cwd = os.getcwd()
        try:
            os.chdir(str(project_root))

            tracker = SessionTracker()

            # Should auto-create the directory
            expected = project_root / "docs" / "sessions"
            assert tracker.session_dir.exists()
            assert tracker.session_dir == expected

        finally:
            os.chdir(original_cwd)


class TestAgentTrackerPathResolution:
    """Test that AgentTracker resolves paths from PROJECT_ROOT, not cwd."""

    @pytest.fixture
    def mock_project_root(self, tmp_path):
        """Create a mock project root directory."""
        project_root = tmp_path / "project"
        project_root.mkdir()
        (project_root / ".git").mkdir()
        (project_root / "docs" / "sessions").mkdir(parents=True)
        return project_root

    def test_agent_tracker_uses_project_root_not_cwd(self, mock_project_root):
        """Test AgentTracker resolves session_dir from PROJECT_ROOT.

        CRITICAL: agent_tracker.py line 179 has hardcoded Path("docs/sessions")
        Same issue as session_tracker.py

        Expected:
        - Resolve PROJECT_ROOT first
        - session_dir = PROJECT_ROOT / "docs" / "sessions"
        - Works from any subdirectory

        Current behavior (SHOULD FAIL):
        - Uses hardcoded Path("docs/sessions")
        """
        subdirectory = mock_project_root / "scripts"
        subdirectory.mkdir()
        original_cwd = os.getcwd()

        try:
            os.chdir(str(subdirectory))

            tracker = AgentTracker()

            expected_session_dir = mock_project_root / "docs" / "sessions"
            assert tracker.session_dir == expected_session_dir, (
                f"AgentTracker should resolve from PROJECT_ROOT. "
                f"Expected: {expected_session_dir}, "
                f"Got: {tracker.session_dir}"
            )

        finally:
            os.chdir(original_cwd)

    def test_agent_tracker_session_file_in_correct_location(self, mock_project_root):
        """Test that session files are created in PROJECT_ROOT/docs/sessions/.

        Expected:
        - tracker.log_start() creates file in PROJECT_ROOT/docs/sessions/
        - Not in cwd/docs/sessions/
        """
        subdirectory = mock_project_root / "hooks"
        subdirectory.mkdir()
        original_cwd = os.getcwd()

        try:
            os.chdir(str(subdirectory))

            tracker = AgentTracker()
            tracker.start_agent("researcher", "Testing path resolution")

            # Verify session file created in correct location
            expected_dir = mock_project_root / "docs" / "sessions"
            assert tracker.session_file.parent == expected_dir
            assert tracker.session_file.exists()

        finally:
            os.chdir(original_cwd)


class TestBatchStatePathResolution:
    """Test that BatchStateManager resolves paths from PROJECT_ROOT, not cwd."""

    @pytest.fixture
    def mock_project_root(self, tmp_path):
        """Create a mock project root directory."""
        project_root = tmp_path / "project"
        project_root.mkdir()
        (project_root / ".git").mkdir()
        (project_root / ".claude").mkdir()
        return project_root

    def test_batch_state_uses_project_root_not_cwd(self, mock_project_root):
        """Test batch_state_manager resolves state_file from PROJECT_ROOT.

        CRITICAL: batch_state_manager.py has hardcoded Path(".claude/batch_state.json")

        Expected:
        - Resolve PROJECT_ROOT first
        - state_file = PROJECT_ROOT / ".claude" / "batch_state.json"
        - Works from any subdirectory

        Current behavior (SHOULD FAIL):
        - Uses hardcoded Path(".claude/batch_state.json")
        """
        subdirectory = mock_project_root / "plugins" / "autonomous-dev"
        subdirectory.mkdir(parents=True)
        original_cwd = os.getcwd()

        try:
            os.chdir(str(subdirectory))

            # Create and save state
            state = create_batch_state(
                "features.txt",  # features_file (positional)
                ["feature1", "feature2"]  # features (positional)
            )

            # get_default_state_file() should resolve from PROJECT_ROOT
            # This will fail because it's hardcoded as relative path
            expected_state_file = mock_project_root / ".claude" / "batch_state.json"

            # When we save, it should go to PROJECT_ROOT, not cwd
            save_batch_state(get_default_state_file(), state)

            # Verify file created in correct location
            assert expected_state_file.exists(), (
                f"State file should be at PROJECT_ROOT/.claude/batch_state.json. "
                f"Expected: {expected_state_file}, "
                f"File exists: {expected_state_file.exists()}"
            )

        finally:
            os.chdir(original_cwd)

    def test_batch_state_creates_parent_directory(self, mock_project_root):
        """Test that .claude/ directory is auto-created if missing.

        Expected:
        - Detect PROJECT_ROOT
        - Create .claude/ if it doesn't exist
        - state_file path resolves correctly
        """
        # Remove .claude directory
        (mock_project_root / ".claude").rmdir()

        original_cwd = os.getcwd()
        try:
            os.chdir(str(mock_project_root))

            # Create and save state (should auto-create .claude/)
            state = create_batch_state(
                "features.txt",  # features_file (positional)
                ["feature1"]  # features (positional)
            )
            save_batch_state(get_default_state_file(), state)

            # Should auto-create .claude/
            expected = mock_project_root / ".claude"
            assert expected.exists()
            assert (expected / "batch_state.json").exists()

        finally:
            os.chdir(original_cwd)

    def test_batch_state_custom_path_resolves_from_project_root(self, mock_project_root):
        """Test custom state_file path still resolves from PROJECT_ROOT.

        Expected:
        - If custom path provided, still resolve from PROJECT_ROOT
        - save_batch_state("custom/state.json", state)
        - Resolves to PROJECT_ROOT / "custom" / "state.json"
        """
        subdirectory = mock_project_root / "scripts"
        subdirectory.mkdir()
        original_cwd = os.getcwd()

        try:
            os.chdir(str(subdirectory))

            custom_path = "custom/state.json"
            state = create_batch_state(
                "features.txt",  # features_file (positional)
                ["feature1"]  # features (positional)
            )

            # Should resolve relative to PROJECT_ROOT, not cwd
            save_batch_state(custom_path, state)

            expected = mock_project_root / "custom" / "state.json"
            assert expected.exists(), (
                f"Custom path should resolve from PROJECT_ROOT. "
                f"Expected: {expected}"
            )

        finally:
            os.chdir(original_cwd)


class TestTrackingWorksFromSubdirectory:
    """Integration test: All tracking works from any subdirectory."""

    @pytest.fixture
    def project_structure(self, tmp_path):
        """Create realistic project structure."""
        project = tmp_path / "autonomous-dev"
        project.mkdir()

        # Project markers
        (project / ".git").mkdir()
        (project / ".claude").mkdir()

        # Required directories
        (project / "docs" / "sessions").mkdir(parents=True)
        (project / "plugins" / "autonomous-dev").mkdir(parents=True)
        (project / "scripts").mkdir()
        (project / "hooks").mkdir()

        return project

    def test_all_tracking_works_from_plugins_subdirectory(self, project_structure):
        """Test all trackers work when cwd = plugins/autonomous-dev/.

        Real-world scenario: Running from plugin directory

        Expected:
        - SessionTracker resolves to PROJECT_ROOT/docs/sessions/
        - AgentTracker resolves to PROJECT_ROOT/docs/sessions/
        - BatchStateManager resolves to PROJECT_ROOT/.claude/batch_state.json
        - All work correctly despite being 2 levels deep
        """
        subdirectory = project_structure / "plugins" / "autonomous-dev"
        original_cwd = os.getcwd()

        try:
            os.chdir(str(subdirectory))

            # All three should work
            session_tracker = SessionTracker()
            agent_tracker = AgentTracker()

            # Save batch state
            state = create_batch_state("test.txt", ["f1"])
            save_batch_state(get_default_state_file(), state)

            # Verify all resolve to project root
            expected_session_dir = project_structure / "docs" / "sessions"
            expected_state_file = project_structure / ".claude" / "batch_state.json"

            assert session_tracker.session_dir == expected_session_dir
            assert agent_tracker.session_dir == expected_session_dir
            assert expected_state_file.exists()

        finally:
            os.chdir(original_cwd)

    def test_all_tracking_works_from_scripts_subdirectory(self, project_structure):
        """Test all trackers work when cwd = scripts/.

        Real-world scenario: Running scripts directly

        Expected: All resolve to PROJECT_ROOT correctly
        """
        subdirectory = project_structure / "scripts"
        original_cwd = os.getcwd()

        try:
            os.chdir(str(subdirectory))

            session_tracker = SessionTracker()
            agent_tracker = AgentTracker()

            state = create_batch_state("test.txt", ["f1"])
            save_batch_state(get_default_state_file(), state)

            # Verify all resolve correctly
            expected_session_dir = project_structure / "docs" / "sessions"
            expected_state_file = project_structure / ".claude" / "batch_state.json"

            assert session_tracker.session_dir == expected_session_dir
            assert agent_tracker.session_dir == expected_session_dir
            assert expected_state_file.exists()

        finally:
            os.chdir(original_cwd)

    def test_all_tracking_works_from_hooks_subdirectory(self, project_structure):
        """Test all trackers work when cwd = hooks/.

        Real-world scenario: Pre-commit hooks running

        Expected: All resolve to PROJECT_ROOT correctly
        """
        subdirectory = project_structure / "hooks"
        original_cwd = os.getcwd()

        try:
            os.chdir(str(subdirectory))

            session_tracker = SessionTracker()
            agent_tracker = AgentTracker()

            state = create_batch_state("test.txt", ["f1"])
            save_batch_state(get_default_state_file(), state)

            expected_session_dir = project_structure / "docs" / "sessions"
            expected_state_file = project_structure / ".claude" / "batch_state.json"

            assert session_tracker.session_dir == expected_session_dir
            assert agent_tracker.session_dir == expected_session_dir
            assert expected_state_file.exists()

        finally:
            os.chdir(original_cwd)


class TestProjectRootDetection:
    """Test PROJECT_ROOT detection logic."""

    def test_project_root_detected_from_git(self, tmp_path):
        """Test PROJECT_ROOT = directory containing .git/."""
        project = tmp_path / "my-project"
        project.mkdir()
        (project / ".git").mkdir()

        nested = project / "src" / "lib" / "utils"
        nested.mkdir(parents=True)

        original_cwd = os.getcwd()
        try:
            os.chdir(str(nested))

            # All trackers should find project root
            # (This tests the helper function, which doesn't exist yet - will fail)
            from plugins.autonomous_dev.lib.session_tracker import find_project_root

            detected_root = find_project_root()
            assert detected_root == project

        finally:
            os.chdir(original_cwd)

    def test_project_root_detected_from_claude_dir(self, tmp_path):
        """Test PROJECT_ROOT = directory containing .claude/ if no .git/."""
        project = tmp_path / "my-project"
        project.mkdir()
        (project / ".claude").mkdir()

        nested = project / "plugins"
        nested.mkdir()

        original_cwd = os.getcwd()
        try:
            os.chdir(str(nested))

            from plugins.autonomous_dev.lib.session_tracker import find_project_root

            detected_root = find_project_root()
            assert detected_root == project

        finally:
            os.chdir(original_cwd)

    def test_project_root_prefers_git_over_claude(self, tmp_path):
        """Test that .git/ takes precedence over .claude/ for PROJECT_ROOT."""
        project = tmp_path / "my-project"
        project.mkdir()
        (project / ".git").mkdir()
        (project / ".claude").mkdir()

        # Create nested .claude/ to ensure we pick the .git/ one
        nested = project / "submodule"
        nested.mkdir()
        (nested / ".claude").mkdir()

        original_cwd = os.getcwd()
        try:
            os.chdir(str(nested))

            from plugins.autonomous_dev.lib.session_tracker import find_project_root

            detected_root = find_project_root()
            # Should find parent with .git/, not current dir with .claude/
            assert detected_root == project

        finally:
            os.chdir(original_cwd)

    def test_project_root_raises_if_not_found(self, tmp_path):
        """Test error raised if no .git/ or .claude/ found."""
        no_markers = tmp_path / "not-a-project"
        no_markers.mkdir()

        original_cwd = os.getcwd()
        try:
            os.chdir(str(no_markers))

            from plugins.autonomous_dev.lib.session_tracker import find_project_root

            with pytest.raises(FileNotFoundError, match="Could not find project root"):
                find_project_root()

        finally:
            os.chdir(original_cwd)


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
