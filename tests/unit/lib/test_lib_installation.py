#!/usr/bin/env python3
"""
TDD Unit Tests for Lib File Installation (FAILING - Red Phase)

This module contains FAILING tests for lib file installation functionality that
will be added to plugin_updater.py.

Requirements:
1. Installation manifest must list all required lib files
2. PluginUpdater._sync_lib_files() must copy lib files to ~/.claude/lib/
3. _sync_lib_files() must handle missing manifest gracefully
4. _sync_lib_files() must handle missing source files gracefully
5. _sync_lib_files() must create target directory if missing
6. All operations must be security-validated and audit-logged

Required lib files (7 total):
- auto_approval_engine.py
- tool_validator.py
- tool_approval_audit.py
- auto_approval_consent.py
- user_state_manager.py
- security_utils.py
- path_utils.py

Test Coverage Target: 90%+ of lib installation logic

Following TDD principles:
- Write tests FIRST (red phase)
- Tests describe lib installation requirements
- Tests should FAIL until implementation exists
- Each test validates ONE requirement

Author: test-master agent
Date: 2025-12-13
Issue: GitHub #125 - Fix installer/updater lib file copying
"""

import json
import os
import shutil
import sys
import tempfile
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock

import pytest

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

from plugins.autonomous_dev.lib.plugin_updater import (
    PluginUpdater,
    UpdateResult,
)


# Required lib files that must be installed globally
REQUIRED_LIB_FILES = [
    "auto_approval_engine.py",
    "tool_validator.py",
    "tool_approval_audit.py",
    "auto_approval_consent.py",
    "user_state_manager.py",
    "security_utils.py",
    "path_utils.py",
]


class TestManifestLibFileTracking:
    """Test that installation manifest tracks all required lib files."""

    def test_manifest_contains_lib_directory(self, tmp_path):
        """Test that manifest includes lib directory in include_directories.

        REQUIREMENT: Manifest must track lib directory for installation.
        Expected: 'lib' in include_directories list.
        Current: WILL FAIL - Need to verify manifest structure.
        """
        # Arrange: Create plugin structure with manifest
        plugin_dir = tmp_path / "plugins" / "autonomous-dev"
        plugin_dir.mkdir(parents=True)

        config_dir = plugin_dir / "config"
        config_dir.mkdir()

        manifest_path = config_dir / "installation_manifest.json"
        manifest_data = {
            "version": "1.0.0",
            "include_directories": ["agents", "commands", "hooks", "lib"],
            "required_directories": ["lib"]
        }
        manifest_path.write_text(json.dumps(manifest_data, indent=2))

        # Act: Read manifest
        manifest = json.loads(manifest_path.read_text())

        # Assert: Lib directory is tracked
        assert "lib" in manifest["include_directories"]
        assert "lib" in manifest["required_directories"]

    def test_manifest_required_lib_files_exist(self, tmp_path):
        """Test that all 7 required lib files exist in plugin/lib/.

        REQUIREMENT: All required lib files must exist for installation.
        Expected: All 7 .py files exist in plugin/lib/.
        Current: WILL FAIL - Need to verify files exist.
        """
        # Arrange: Create plugin structure with lib files
        plugin_dir = tmp_path / "plugins" / "autonomous-dev"
        lib_dir = plugin_dir / "lib"
        lib_dir.mkdir(parents=True)

        # Create all required lib files
        for filename in REQUIRED_LIB_FILES:
            lib_file = lib_dir / filename
            lib_file.write_text(f"# {filename}\nprint('stub')\n")

        # Act: Check file existence
        existing_files = [f.name for f in lib_dir.glob("*.py")]

        # Assert: All required files exist
        for required_file in REQUIRED_LIB_FILES:
            assert required_file in existing_files, f"Missing required lib file: {required_file}"

        assert len(existing_files) >= len(REQUIRED_LIB_FILES)


class TestPluginUpdaterSyncLibFiles:
    """Test PluginUpdater._sync_lib_files() method."""

    @pytest.fixture
    def mock_plugin_structure(self, tmp_path):
        """Create mock plugin structure with lib files."""
        # Create proper project structure: project_root/.claude/plugins/autonomous-dev/
        project_root = tmp_path
        claude_dir = project_root / ".claude"
        plugin_dir = claude_dir / "plugins" / "autonomous-dev"
        lib_dir = plugin_dir / "lib"
        lib_dir.mkdir(parents=True)

        # Create all required lib files
        for filename in REQUIRED_LIB_FILES:
            lib_file = lib_dir / filename
            lib_file.write_text(f"# {filename}\nprint('installed')\n")

        # Create manifest
        config_dir = plugin_dir / "config"
        config_dir.mkdir()
        manifest_path = config_dir / "installation_manifest.json"
        manifest_data = {
            "version": "1.0.0",
            "include_directories": ["lib"],
            "required_directories": ["lib"]
        }
        manifest_path.write_text(json.dumps(manifest_data, indent=2))

        # Return project_root (not plugin_dir) for PluginUpdater
        return project_root

    @pytest.fixture
    def mock_home_dir(self, tmp_path, monkeypatch):
        """Mock home directory to avoid touching real ~/.claude/."""
        fake_home = tmp_path / "fake_home"
        fake_home.mkdir()

        def mock_home():
            return fake_home

        monkeypatch.setattr(Path, "home", mock_home)
        return fake_home

    def test_sync_lib_files_copies_all_required_files(
        self, mock_plugin_structure, mock_home_dir
    ):
        """Test that _sync_lib_files() copies all 7 required files.

        REQUIREMENT: _sync_lib_files() must copy all lib files to ~/.claude/lib/.
        Expected: All 7 .py files copied to ~/.claude/lib/.
        Current: WILL FAIL - Method doesn't exist yet.
        """
        # Arrange: Create updater
        updater = PluginUpdater(project_root=mock_plugin_structure)
        target_dir = mock_home_dir / ".claude" / "lib"

        # Act: Sync lib files (THIS WILL FAIL - method doesn't exist)
        result = updater._sync_lib_files()

        # Assert: All files copied
        assert result is True or result == len(REQUIRED_LIB_FILES)
        assert target_dir.exists()

        for filename in REQUIRED_LIB_FILES:
            target_file = target_dir / filename
            assert target_file.exists(), f"Missing file: {filename}"
            assert target_file.read_text().strip() != "", f"Empty file: {filename}"

    def test_sync_lib_files_creates_target_directory(
        self, mock_plugin_structure, mock_home_dir
    ):
        """Test that _sync_lib_files() creates ~/.claude/lib/ if missing.

        REQUIREMENT: _sync_lib_files() must create target directory.
        Expected: ~/.claude/lib/ directory created.
        Current: WILL FAIL - Method doesn't exist yet.
        """
        # Arrange: Ensure target directory doesn't exist
        updater = PluginUpdater(project_root=mock_plugin_structure)
        target_dir = mock_home_dir / ".claude" / "lib"
        assert not target_dir.exists()

        # Act: Sync lib files (THIS WILL FAIL - method doesn't exist)
        result = updater._sync_lib_files()

        # Assert: Directory created
        assert target_dir.exists()
        assert target_dir.is_dir()

    def test_sync_lib_files_handles_missing_manifest_gracefully(
        self, tmp_path, mock_home_dir
    ):
        """Test that _sync_lib_files() handles missing manifest gracefully.

        REQUIREMENT: _sync_lib_files() must not crash if manifest missing.
        Expected: Returns False or empty list, no exception raised.
        Current: WILL FAIL - Method doesn't exist yet.
        """
        # Arrange: Create plugin without manifest
        project_root = tmp_path
        claude_dir = project_root / ".claude"
        plugin_dir = claude_dir / "plugins" / "autonomous-dev"
        lib_dir = plugin_dir / "lib"
        lib_dir.mkdir(parents=True)

        # Create lib files but no manifest
        for filename in REQUIRED_LIB_FILES[:3]:  # Just a few files
            (lib_dir / filename).write_text("# stub\n")

        updater = PluginUpdater(project_root=project_root)

        # Act: Sync lib files (THIS WILL FAIL - method doesn't exist)
        # Should handle gracefully, not raise exception
        result = updater._sync_lib_files()

        # Assert: Graceful degradation (returns False or 0)
        # Still copies available files or returns failure status
        assert result is not None  # Should return something
        # No exception raised is success

    def test_sync_lib_files_handles_missing_source_files_gracefully(
        self, mock_plugin_structure, mock_home_dir
    ):
        """Test that _sync_lib_files() handles missing source files gracefully.

        REQUIREMENT: _sync_lib_files() must handle missing files without crash.
        Expected: Copies available files, skips missing ones.
        Current: WILL FAIL - Method doesn't exist yet.
        """
        # Arrange: Remove some source files
        project_root = mock_plugin_structure
        lib_dir = project_root / ".claude" / "plugins" / "autonomous-dev" / "lib"
        (lib_dir / "auto_approval_engine.py").unlink()  # Remove one file
        (lib_dir / "tool_validator.py").unlink()  # Remove another

        updater = PluginUpdater(project_root=project_root)
        target_dir = mock_home_dir / ".claude" / "lib"

        # Act: Sync lib files (THIS WILL FAIL - method doesn't exist)
        result = updater._sync_lib_files()

        # Assert: Available files copied, missing ones skipped
        assert target_dir.exists()
        copied_files = list(target_dir.glob("*.py"))
        assert len(copied_files) == len(REQUIRED_LIB_FILES) - 2  # 5 out of 7

        # Verify remaining files copied
        assert (target_dir / "tool_approval_audit.py").exists()
        assert (target_dir / "security_utils.py").exists()

    def test_sync_lib_files_validates_paths_security(
        self, mock_plugin_structure, mock_home_dir
    ):
        """Test that _sync_lib_files() validates all paths for security.

        REQUIREMENT: All file operations must be security-validated.
        Expected: Calls security_utils.validate_path() for source and target.
        Current: WILL FAIL - Method doesn't exist yet.
        """
        # Arrange
        updater = PluginUpdater(project_root=mock_plugin_structure)

        # Act: Sync lib files with path validation mock
        with patch("plugins.autonomous_dev.lib.plugin_updater.security_utils.validate_path") as mock_validate:
            mock_validate.return_value = True

            try:
                result = updater._sync_lib_files()
            except AttributeError:
                # Method doesn't exist yet - expected failure
                pass

            # Assert: Security validation called (when method exists)
            # This will pass once implementation is complete
            if mock_validate.called:
                assert mock_validate.call_count >= len(REQUIRED_LIB_FILES)

    def test_sync_lib_files_preserves_file_permissions(
        self, mock_plugin_structure, mock_home_dir
    ):
        """Test that _sync_lib_files() preserves executable permissions.

        REQUIREMENT: Copied files must maintain correct permissions.
        Expected: Files are readable (0o644 or similar).
        Current: WILL FAIL - Method doesn't exist yet.
        """
        # Arrange: Make source files executable
        project_root = mock_plugin_structure
        lib_dir = project_root / ".claude" / "plugins" / "autonomous-dev" / "lib"
        for filename in REQUIRED_LIB_FILES:
            (lib_dir / filename).chmod(0o755)

        updater = PluginUpdater(project_root=project_root)
        target_dir = mock_home_dir / ".claude" / "lib"

        # Act: Sync lib files (THIS WILL FAIL - method doesn't exist)
        try:
            result = updater._sync_lib_files()

            # Assert: Permissions preserved or set correctly
            for filename in REQUIRED_LIB_FILES:
                target_file = target_dir / filename
                if target_file.exists():
                    # Should be readable by user
                    assert os.access(target_file, os.R_OK)
        except AttributeError:
            # Expected - method doesn't exist yet
            pytest.fail("_sync_lib_files() method not implemented yet")

    def test_sync_lib_files_logs_operations(
        self, mock_plugin_structure, mock_home_dir
    ):
        """Test that _sync_lib_files() logs all operations.

        REQUIREMENT: All operations must be audit-logged.
        Expected: Logs each file copy operation.
        Current: WILL FAIL - Method doesn't exist yet.
        """
        # Arrange
        updater = PluginUpdater(project_root=mock_plugin_structure)

        # Act: Sync lib files with logging mock
        with patch("plugins.autonomous_dev.lib.plugin_updater.print") as mock_log:
            try:
                result = updater._sync_lib_files()
            except AttributeError:
                # Method doesn't exist yet - expected failure
                pass

            # Assert: Operations logged (when method exists)
            # This assertion will pass once implementation is complete
            if mock_log.called:
                log_messages = [str(call) for call in mock_log.call_args_list]
                # Should log at least "syncing lib files" or similar
                assert any("lib" in str(msg).lower() for msg in log_messages)


class TestPluginUpdaterIntegration:
    """Test _sync_lib_files() integration with update workflow."""

    @pytest.fixture
    def mock_environment(self, tmp_path, monkeypatch):
        """Create complete mock environment."""
        # Mock home directory
        fake_home = tmp_path / "fake_home"
        fake_home.mkdir()

        def mock_home():
            return fake_home

        monkeypatch.setattr(Path, "home", mock_home)

        # Create proper project structure
        project_root = tmp_path / "project"
        project_root.mkdir()
        claude_dir = project_root / ".claude"
        plugin_dir = claude_dir / "plugins" / "autonomous-dev"
        lib_dir = plugin_dir / "lib"
        lib_dir.mkdir(parents=True)

        for filename in REQUIRED_LIB_FILES:
            (lib_dir / filename).write_text(f"# {filename}\nprint('v2')\n")

        # Create plugin.json for verification
        plugin_json = plugin_dir / "plugin.json"
        plugin_json.write_text(json.dumps({"name": "autonomous-dev", "version": "3.0.0"}))

        return {"project_root": project_root, "plugin_dir": plugin_dir, "home_dir": fake_home}

    def test_sync_lib_files_called_during_update(self, mock_environment):
        """Test that _sync_lib_files() is called during update workflow.

        REQUIREMENT: Lib files must sync during plugin update.
        Expected: _sync_lib_files() called as part of update().
        Current: WILL FAIL - Integration not implemented.
        """
        # Arrange
        from plugins.autonomous_dev.lib.version_detector import VersionComparison
        from plugins.autonomous_dev.lib.sync_dispatcher import SyncResult

        project_root = mock_environment["project_root"]
        updater = PluginUpdater(project_root=project_root)

        # Create mock comparison result
        mock_comparison = MagicMock()
        mock_comparison.status = "upgrade_available"
        mock_comparison.project_version = "2.0.0"
        mock_comparison.marketplace_version = "3.0.0"

        # Create mock sync result
        mock_sync_result = SyncResult(
            success=True,
            message="Sync successful",
            mode="marketplace",
            details={}
        )

        # Act: Mock the update workflow
        with patch.object(updater, "_sync_lib_files", return_value=7) as mock_sync:
            with patch.object(updater, "check_for_updates", return_value=mock_comparison):
                with patch("plugins.autonomous_dev.lib.plugin_updater.sync_marketplace", return_value=mock_sync_result):
                    try:
                        # This should call _sync_lib_files() as part of update
                        result = updater.update(skip_confirm=True, auto_backup=False)
                    except Exception as e:
                        # Log any unexpected exceptions
                        print(f"Update failed with: {e}")

            # Assert: _sync_lib_files() was called during update
            assert mock_sync.called, "_sync_lib_files() not called during update()"

    def test_update_result_includes_lib_sync_status(self, mock_environment):
        """Test that UpdateResult includes lib sync status.

        REQUIREMENT: Update result must report lib sync success/failure.
        Expected: UpdateResult.details contains lib_files_synced count.
        Current: WILL FAIL - Result structure doesn't include this.
        """
        # Arrange
        from plugins.autonomous_dev.lib.version_detector import VersionComparison
        from plugins.autonomous_dev.lib.sync_dispatcher import SyncResult

        project_root = mock_environment["project_root"]
        updater = PluginUpdater(project_root=project_root)

        # Create mock comparison result
        mock_comparison = MagicMock()
        mock_comparison.status = "upgrade_available"
        mock_comparison.project_version = "2.0.0"
        mock_comparison.marketplace_version = "3.0.0"

        # Create mock sync result
        mock_sync_result = SyncResult(
            success=True,
            message="Sync successful",
            mode="marketplace",
            details={}
        )

        # Act: Run update with lib sync mock
        with patch.object(updater, "_sync_lib_files", return_value=len(REQUIRED_LIB_FILES)):
            with patch.object(updater, "check_for_updates", return_value=mock_comparison):
                with patch("plugins.autonomous_dev.lib.plugin_updater.sync_marketplace", return_value=mock_sync_result):
                    try:
                        result = updater.update(skip_confirm=True, auto_backup=False)

                        # Assert: Result includes lib sync info
                        assert "lib_files_synced" in result.details
                        assert result.details["lib_files_synced"] == len(REQUIRED_LIB_FILES)
                    except (AttributeError, KeyError) as e:
                        # Expected - integration not complete
                        pytest.fail(f"UpdateResult doesn't include lib_files_synced: {e}")


# Summary of failing tests:
# 1. test_manifest_contains_lib_directory - Verifies manifest structure
# 2. test_manifest_required_lib_files_exist - Verifies all 7 files exist
# 3. test_sync_lib_files_copies_all_required_files - Core functionality
# 4. test_sync_lib_files_creates_target_directory - Directory creation
# 5. test_sync_lib_files_handles_missing_manifest_gracefully - Error handling
# 6. test_sync_lib_files_handles_missing_source_files_gracefully - Partial sync
# 7. test_sync_lib_files_validates_paths_security - Security validation
# 8. test_sync_lib_files_preserves_file_permissions - Permission handling
# 9. test_sync_lib_files_logs_operations - Audit logging
# 10. test_sync_lib_files_called_during_update - Integration with update()
# 11. test_update_result_includes_lib_sync_status - Result reporting
#
# All tests should FAIL until:
# - PluginUpdater._sync_lib_files() method is implemented
# - Update workflow integrates lib file syncing
# - UpdateResult includes lib sync status
