#!/usr/bin/env python3
"""
TDD Tests for Tracking Directory Auto-Creation (Issue #79)

This module tests that tracking modules automatically create missing directories:
- SessionTracker: Creates docs/sessions/ if missing
- AgentTracker: Creates docs/sessions/ if missing
- BatchStateManager: Creates .claude/ if missing

These tests verify idempotent directory creation (no errors if already exists).

Test Coverage Target: 100% of directory creation code paths
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
    BatchStateManager,
    create_batch_state,
    save_batch_state,
    load_batch_state,
    DEFAULT_STATE_FILE
)


class TestSessionTrackerDirectoryCreation:
    """Test that SessionTracker creates docs/sessions/ if missing."""

    @pytest.fixture
    def empty_project(self, tmp_path):
        """Create project with no docs/ directory."""
        project = tmp_path / "project"
        project.mkdir()
        (project / ".git").mkdir()
        # Don't create docs/ - should be auto-created
        return project

    def test_creates_docs_directory_if_missing(self, empty_project):
        """Test that docs/ is created if it doesn't exist.

        Expected:
        - PROJECT_ROOT/docs/ created automatically
        - No error if PROJECT_ROOT exists but docs/ doesn't
        """
        assert not (empty_project / "docs").exists()

        original_cwd = os.getcwd()
        try:
            os.chdir(str(empty_project))

            tracker = SessionTracker()

            # Should auto-create docs/
            assert (empty_project / "docs").exists()
            assert (empty_project / "docs").is_dir()

        finally:
            os.chdir(original_cwd)

    def test_creates_sessions_directory_if_missing(self, empty_project):
        """Test that docs/sessions/ is created if docs/ exists but sessions/ doesn't.

        Expected:
        - docs/sessions/ created automatically
        - Uses parents=True for nested creation
        """
        # Create docs/ but not sessions/
        (empty_project / "docs").mkdir()
        assert not (empty_project / "docs" / "sessions").exists()

        original_cwd = os.getcwd()
        try:
            os.chdir(str(empty_project))

            tracker = SessionTracker()

            # Should auto-create sessions/
            assert (empty_project / "docs" / "sessions").exists()
            assert (empty_project / "docs" / "sessions").is_dir()

        finally:
            os.chdir(original_cwd)

    def test_creates_full_path_if_both_missing(self, empty_project):
        """Test that docs/sessions/ is created if both are missing.

        Expected:
        - Both docs/ and sessions/ created in one call
        - mkdir(parents=True, exist_ok=True)
        """
        assert not (empty_project / "docs").exists()

        original_cwd = os.getcwd()
        try:
            os.chdir(str(empty_project))

            tracker = SessionTracker()

            # Should auto-create full path
            assert (empty_project / "docs" / "sessions").exists()
            assert tracker.session_dir == empty_project / "docs" / "sessions"

        finally:
            os.chdir(original_cwd)

    def test_no_error_if_directory_already_exists(self, empty_project):
        """Test that no error occurs if docs/sessions/ already exists.

        Expected:
        - exist_ok=True prevents errors
        - Idempotent operation
        """
        # Create directory first
        (empty_project / "docs" / "sessions").mkdir(parents=True)

        original_cwd = os.getcwd()
        try:
            os.chdir(str(empty_project))

            # Should not raise error
            tracker = SessionTracker()

            assert tracker.session_dir.exists()

        finally:
            os.chdir(original_cwd)

    def test_creates_session_file_in_new_directory(self, empty_project):
        """Test that session file is created after directory auto-creation.

        Expected:
        - Directory created
        - Session file created inside it
        - File has correct format
        """
        original_cwd = os.getcwd()
        try:
            os.chdir(str(empty_project))

            tracker = SessionTracker()

            # Should create directory and file
            assert tracker.session_dir.exists()
            assert tracker.session_file.exists()
            assert tracker.session_file.parent == tracker.session_dir

        finally:
            os.chdir(original_cwd)


class TestAgentTrackerDirectoryCreation:
    """Test that AgentTracker creates docs/sessions/ if missing."""

    @pytest.fixture
    def empty_project(self, tmp_path):
        """Create project with no docs/ directory."""
        project = tmp_path / "project"
        project.mkdir()
        (project / ".git").mkdir()
        return project

    def test_creates_sessions_directory_on_init(self, empty_project):
        """Test that docs/sessions/ is created during AgentTracker initialization.

        Expected:
        - Directory created in __init__
        - No error if already exists
        """
        assert not (empty_project / "docs" / "sessions").exists()

        original_cwd = os.getcwd()
        try:
            os.chdir(str(empty_project))

            tracker = AgentTracker()

            assert (empty_project / "docs" / "sessions").exists()
            assert tracker.session_dir == empty_project / "docs" / "sessions"

        finally:
            os.chdir(original_cwd)

    def test_creates_session_file_on_first_log(self, empty_project):
        """Test that session file is created when first log entry is written.

        Expected:
        - log_start() creates file if missing
        - File created in correct directory
        """
        original_cwd = os.getcwd()
        try:
            os.chdir(str(empty_project))

            tracker = AgentTracker()
            tracker.log_start("researcher", "First log entry")

            # Session file should exist
            assert tracker.session_file.exists()
            assert tracker.session_file.parent == empty_project / "docs" / "sessions"

        finally:
            os.chdir(original_cwd)

    def test_multiple_trackers_share_directory(self, empty_project):
        """Test that multiple AgentTracker instances share same directory.

        Expected:
        - Both trackers use PROJECT_ROOT/docs/sessions/
        - No conflicts or errors
        """
        original_cwd = os.getcwd()
        try:
            os.chdir(str(empty_project))

            tracker1 = AgentTracker()
            tracker2 = AgentTracker()

            # Both should use same directory
            assert tracker1.session_dir == tracker2.session_dir
            assert tracker1.session_dir == empty_project / "docs" / "sessions"

        finally:
            os.chdir(original_cwd)


class TestBatchStateDirectoryCreation:
    """Test that BatchStateManager creates .claude/ if missing."""

    @pytest.fixture
    def empty_project(self, tmp_path):
        """Create project with no .claude/ directory."""
        project = tmp_path / "project"
        project.mkdir()
        (project / ".git").mkdir()
        # Don't create .claude/ - should be auto-created
        return project

    def test_creates_claude_directory_if_missing(self, empty_project):
        """Test that .claude/ is created if it doesn't exist.

        Expected:
        - .claude/ created automatically
        - No error if directory missing
        """
        assert not (empty_project / ".claude").exists()

        original_cwd = os.getcwd()
        try:
            os.chdir(str(empty_project))

            manager = BatchStateManager()

            # Should auto-create .claude/
            assert (empty_project / ".claude").exists()
            assert (empty_project / ".claude").is_dir()

        finally:
            os.chdir(original_cwd)

    def test_no_error_if_claude_directory_exists(self, empty_project):
        """Test that no error occurs if .claude/ already exists.

        Expected:
        - exist_ok=True prevents errors
        - Idempotent operation
        """
        # Create .claude/ first
        (empty_project / ".claude").mkdir()

        original_cwd = os.getcwd()
        try:
            os.chdir(str(empty_project))

            # Should not raise error
            manager = BatchStateManager()

            assert manager.state_file.parent.exists()

        finally:
            os.chdir(original_cwd)

    def test_state_file_path_correct_after_creation(self, empty_project):
        """Test that state_file path is correct after directory creation.

        Expected:
        - state_file = PROJECT_ROOT/.claude/batch_state.json
        - Parent directory exists
        """
        original_cwd = os.getcwd()
        try:
            os.chdir(str(empty_project))

            manager = BatchStateManager()

            expected_file = empty_project / ".claude" / "batch_state.json"
            assert manager.state_file == expected_file
            assert manager.state_file.parent.exists()

        finally:
            os.chdir(original_cwd)

    def test_creates_custom_state_file_parent_directory(self, empty_project):
        """Test that custom state file parent directory is created.

        Expected:
        - manager = BatchStateManager(state_file="custom/dir/state.json")
        - custom/dir/ created if missing
        """
        custom_path = "custom/dir/state.json"

        original_cwd = os.getcwd()
        try:
            os.chdir(str(empty_project))

            manager = BatchStateManager(state_file=custom_path)

            # Should create custom/dir/
            expected_parent = empty_project / "custom" / "dir"
            assert expected_parent.exists()
            assert manager.state_file.parent == expected_parent

        finally:
            os.chdir(original_cwd)


class TestPermissionsHandling:
    """Test that directory creation handles permissions correctly."""

    def test_created_directories_have_correct_permissions(self, tmp_path):
        """Test that auto-created directories have appropriate permissions.

        Expected:
        - Directories readable/writable by owner
        - No execute needed for files
        """
        project = tmp_path / "project"
        project.mkdir()
        (project / ".git").mkdir()

        original_cwd = os.getcwd()
        try:
            os.chdir(str(project))

            tracker = SessionTracker()

            # Check directory permissions (should be readable and writable)
            sessions_dir = project / "docs" / "sessions"
            assert sessions_dir.exists()
            assert os.access(sessions_dir, os.R_OK)
            assert os.access(sessions_dir, os.W_OK)
            assert os.access(sessions_dir, os.X_OK)  # Execute for directories

        finally:
            os.chdir(original_cwd)

    @pytest.mark.skipif(os.name == 'nt', reason="POSIX permissions not applicable on Windows")
    def test_readonly_parent_directory_raises_error(self, tmp_path):
        """Test that read-only parent directory prevents creation.

        Expected:
        - PermissionError raised
        - Helpful error message
        """
        project = tmp_path / "project"
        project.mkdir()
        (project / ".git").mkdir()

        # Make project read-only
        project.chmod(0o555)

        original_cwd = os.getcwd()
        try:
            os.chdir(str(project))

            # Should raise PermissionError
            with pytest.raises(PermissionError):
                tracker = SessionTracker()

        finally:
            # Restore permissions for cleanup
            project.chmod(0o755)
            os.chdir(original_cwd)


class TestConcurrentDirectoryCreation:
    """Test that concurrent directory creation doesn't cause race conditions."""

    def test_multiple_trackers_create_directory_concurrently(self, tmp_path):
        """Test that multiple trackers can initialize concurrently.

        Expected:
        - Race condition handled by exist_ok=True
        - No errors if directory created by another process
        """
        project = tmp_path / "project"
        project.mkdir()
        (project / ".git").mkdir()

        import threading

        errors = []

        def create_tracker():
            try:
                original_cwd = os.getcwd()
                os.chdir(str(project))
                tracker = SessionTracker()
                os.chdir(original_cwd)
            except Exception as e:
                errors.append(e)

        # Create multiple trackers concurrently
        threads = [threading.Thread(target=create_tracker) for _ in range(5)]

        for thread in threads:
            thread.start()

        for thread in threads:
            thread.join()

        # No errors should occur
        assert len(errors) == 0

        # Directory should exist
        assert (project / "docs" / "sessions").exists()


class TestDirectoryCreationRollback:
    """Test that directory creation failures are handled gracefully."""

    def test_partial_directory_creation_cleaned_up(self, tmp_path):
        """Test that failed creation doesn't leave partial directories.

        Expected:
        - If creation fails partway through, cleanup occurs
        - No orphaned directories left behind
        """
        project = tmp_path / "project"
        project.mkdir()
        (project / ".git").mkdir()

        # Create docs/ but make it read-only
        (project / "docs").mkdir()
        if os.name != 'nt':  # Skip on Windows
            (project / "docs").chmod(0o555)

        original_cwd = os.getcwd()
        try:
            os.chdir(str(project))

            # Should fail to create sessions/
            with pytest.raises(PermissionError):
                tracker = SessionTracker()

            # sessions/ should not exist
            assert not (project / "docs" / "sessions").exists()

        finally:
            if os.name != 'nt':
                (project / "docs").chmod(0o755)
            os.chdir(original_cwd)


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
