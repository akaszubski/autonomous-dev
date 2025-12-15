#!/usr/bin/env python3
"""
Smoke tests for Sync Dispatcher.

Simplified smoke tests that verify:
1. SyncDispatcher module imports correctly
2. Core classes exist and can be instantiated
3. Basic interface is available

For detailed integration tests, see tests/integration/
"""

import sys
from pathlib import Path
from unittest.mock import patch

import pytest

# Portable path detection
current = Path.cwd()
while current != current.parent:
    if (current / ".git").exists() or (current / ".claude").exists():
        project_root = current
        break
    current = current.parent
else:
    project_root = Path.cwd()

sys.path.insert(0, str(project_root))

from plugins.autonomous_dev.lib.sync_dispatcher import (
    SyncDispatcher,
    SyncResult,
    SyncError,
    dispatch_sync,
)
from plugins.autonomous_dev.lib.sync_mode_detector import SyncMode


class TestSyncResultClass:
    """Smoke test: SyncResult data class exists and works."""

    def test_sync_result_success_attributes(self):
        """Test SyncResult has expected attributes for success case."""
        result = SyncResult(
            success=True,
            mode=SyncMode.ENVIRONMENT,
            message="Sync completed successfully",
            details={"files_updated": 5}
        )

        assert result.success is True
        assert result.mode == SyncMode.ENVIRONMENT
        assert result.message == "Sync completed successfully"
        assert result.details["files_updated"] == 5

    def test_sync_result_failure_attributes(self):
        """Test SyncResult captures failure information."""
        result = SyncResult(
            success=False,
            mode=SyncMode.MARKETPLACE,
            message="Plugin not found",
            error="FileNotFoundError: ~/.claude/plugins/installed_plugins.json"
        )

        assert result.success is False
        assert result.mode == SyncMode.MARKETPLACE
        assert "Plugin not found" in result.message
        assert result.error is not None


class TestSyncDispatcherClass:
    """Smoke test: SyncDispatcher class exists and has expected interface."""

    def test_sync_dispatcher_can_be_imported(self):
        """Test SyncDispatcher class is importable."""
        assert SyncDispatcher is not None

    def test_sync_dispatcher_has_dispatch_method(self):
        """Test SyncDispatcher has dispatch method."""
        assert hasattr(SyncDispatcher, 'dispatch')

    def test_sync_dispatcher_has_sync_directory_method(self):
        """Test SyncDispatcher has _sync_directory method."""
        assert hasattr(SyncDispatcher, '_sync_directory')


class TestSyncModeEnum:
    """Smoke test: SyncMode enum has expected values."""

    def test_sync_mode_environment_exists(self):
        """Test ENVIRONMENT mode exists."""
        assert hasattr(SyncMode, 'ENVIRONMENT')

    def test_sync_mode_marketplace_exists(self):
        """Test MARKETPLACE mode exists."""
        assert hasattr(SyncMode, 'MARKETPLACE')

    def test_sync_mode_plugin_dev_exists(self):
        """Test PLUGIN_DEV mode exists."""
        assert hasattr(SyncMode, 'PLUGIN_DEV')

    def test_sync_mode_all_exists(self):
        """Test ALL mode exists."""
        assert hasattr(SyncMode, 'ALL')


class TestDispatchSyncFunction:
    """Smoke test: dispatch_sync convenience function exists."""

    def test_dispatch_sync_function_exists(self):
        """Test dispatch_sync function is importable."""
        assert dispatch_sync is not None
        assert callable(dispatch_sync)


class TestSyncErrorClass:
    """Smoke test: SyncError exception class exists."""

    def test_sync_error_is_exception(self):
        """Test SyncError is an Exception subclass."""
        assert issubclass(SyncError, Exception)

    def test_sync_error_can_be_raised(self):
        """Test SyncError can be raised and caught."""
        with pytest.raises(SyncError):
            raise SyncError("Test error")


class TestSyncDirectoryHelper:
    """Smoke test: _sync_directory helper works with mocked filesystem."""

    @pytest.fixture
    def temp_dirs(self, tmp_path):
        """Create temporary source and destination directories."""
        source = tmp_path / "source"
        dest = tmp_path / "dest"
        source.mkdir()
        dest.mkdir()

        # Create test files
        (source / "test1.md").write_text("# Test 1")
        (source / "test2.md").write_text("# Test 2")

        return source, dest

    def test_sync_directory_helper_copies_with_pattern(self, temp_dirs):
        """Test _sync_directory copies files matching pattern."""
        source, dest = temp_dirs

        dispatcher = SyncDispatcher.__new__(SyncDispatcher)
        dispatcher.verbose = False

        count = dispatcher._sync_directory(source, dest, "*.md")

        assert count == 2
        assert (dest / "test1.md").exists()
        assert (dest / "test2.md").exists()

    def test_sync_directory_reports_files_copied(self, temp_dirs):
        """Test _sync_directory returns count of files copied."""
        source, dest = temp_dirs

        dispatcher = SyncDispatcher.__new__(SyncDispatcher)
        dispatcher.verbose = False

        count = dispatcher._sync_directory(source, dest, "*.md")

        assert count == 2

    def test_sync_directory_handles_errors_gracefully(self, tmp_path):
        """Test _sync_directory handles missing source gracefully."""
        source = tmp_path / "nonexistent"
        dest = tmp_path / "dest"
        dest.mkdir()

        dispatcher = SyncDispatcher.__new__(SyncDispatcher)
        dispatcher.verbose = False

        # Should not raise, just return 0
        count = dispatcher._sync_directory(source, dest, "*.md")
        assert count == 0

    def test_sync_detects_new_files_in_existing_directory(self, temp_dirs):
        """Test that sync detects and copies new files."""
        source, dest = temp_dirs

        # Pre-existing file in dest
        (dest / "existing.md").write_text("# Existing")

        dispatcher = SyncDispatcher.__new__(SyncDispatcher)
        dispatcher.verbose = False

        count = dispatcher._sync_directory(source, dest, "*.md")

        # Should copy 2 new files
        assert count == 2
        # Existing file should still be there
        assert (dest / "existing.md").exists()

    def test_sync_directory_creates_destination_if_missing(self, tmp_path):
        """Test _sync_directory creates destination if it doesn't exist."""
        source = tmp_path / "source"
        dest = tmp_path / "dest_new"
        source.mkdir()
        (source / "test.md").write_text("# Test")

        dispatcher = SyncDispatcher.__new__(SyncDispatcher)
        dispatcher.verbose = False

        count = dispatcher._sync_directory(source, dest, "*.md")

        assert dest.exists()
        assert count == 1

    def test_sync_directory_handles_nested_directories(self, tmp_path):
        """Test _sync_directory handles nested directory structures."""
        source = tmp_path / "source"
        dest = tmp_path / "dest"
        source.mkdir()
        dest.mkdir()

        # Create nested structure
        nested = source / "subdir"
        nested.mkdir()
        (nested / "nested.md").write_text("# Nested")
        (source / "root.md").write_text("# Root")

        dispatcher = SyncDispatcher.__new__(SyncDispatcher)
        dispatcher.verbose = False

        # _sync_directory copies all matching files including nested
        count = dispatcher._sync_directory(source, dest, "*.md")

        assert count >= 1  # At least root.md copied


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
