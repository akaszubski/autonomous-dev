#!/usr/bin/env python3
"""
TDD Tests for Plugin Updater (FAILING - Red Phase)

This module contains FAILING tests for plugin_updater.py which will provide
interactive plugin update functionality with version detection, backup, and rollback.

Requirements:
1. Check for plugin updates by comparing versions
2. Create automatic backups before updating
3. Perform update via sync_dispatcher
4. Verify update success (version check + file validation)
5. Rollback on failure (restore backup)
6. Cleanup backups after successful update
7. Security: Path validation, audit logging
8. User consent: Interactive confirmation before update

Test Coverage Target: 90%+ of plugin update logic

Following TDD principles:
- Write tests FIRST (red phase)
- Tests describe plugin update requirements
- Tests should FAIL until plugin_updater.py is implemented
- Each test validates ONE update requirement

Author: test-master agent
Date: 2025-11-09
Issue: GitHub #50 Phase 2 - Interactive /update-plugin command
"""

import json
import os
import shutil
import sys
import tempfile
from dataclasses import asdict
from pathlib import Path
from unittest.mock import Mock, patch, call, MagicMock, mock_open

import pytest

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

# This import will FAIL until plugin_updater.py is created
from plugins.autonomous_dev.lib.plugin_updater import (
    PluginUpdater,
    UpdateResult,
    UpdateError,
    BackupError,
    VerificationError,
)
from plugins.autonomous_dev.lib.version_detector import VersionComparison
from plugins.autonomous_dev.lib.sync_dispatcher import SyncResult, SyncMode


class TestUpdateResultDataclass:
    """Test UpdateResult dataclass creation and attributes."""

    def test_update_result_success_instantiation(self):
        """Test creating UpdateResult for successful update.

        REQUIREMENT: UpdateResult must capture success status and details.
        Expected: UpdateResult with success=True, version info, backup path.
        """
        result = UpdateResult(
            success=True,
            updated=True,
            message="Plugin updated successfully",
            old_version="3.7.0",
            new_version="3.8.0",
            backup_path="/tmp/backup",
            rollback_performed=False,
            details={"files_updated": 5}
        )

        assert result.success is True
        assert result.updated is True
        assert result.message == "Plugin updated successfully"
        assert result.old_version == "3.7.0"
        assert result.new_version == "3.8.0"
        assert result.backup_path == "/tmp/backup"
        assert result.rollback_performed is False
        assert result.details["files_updated"] == 5

    def test_update_result_no_update_needed(self):
        """Test creating UpdateResult when no update needed.

        REQUIREMENT: UpdateResult must differentiate between success and no update.
        Expected: UpdateResult with success=True, updated=False.
        """
        result = UpdateResult(
            success=True,
            updated=False,
            message="Plugin is already up to date",
            old_version="3.8.0",
            new_version="3.8.0",
            backup_path=None,
            rollback_performed=False,
            details={}
        )

        assert result.success is True
        assert result.updated is False
        assert result.message == "Plugin is already up to date"
        assert result.old_version == result.new_version
        assert result.backup_path is None

    def test_update_result_failure_with_rollback(self):
        """Test creating UpdateResult for failed update with rollback.

        REQUIREMENT: UpdateResult must capture rollback status.
        Expected: UpdateResult with success=False, rollback_performed=True.
        """
        result = UpdateResult(
            success=False,
            updated=False,
            message="Update failed, rolled back to 3.7.0",
            old_version="3.7.0",
            new_version="3.8.0",
            backup_path="/tmp/backup",
            rollback_performed=True,
            details={"error": "Verification failed"}
        )

        assert result.success is False
        assert result.rollback_performed is True
        assert "rolled back" in result.message
        assert result.details["error"] == "Verification failed"


class TestPluginUpdaterInitialization:
    """Test PluginUpdater initialization and path validation."""

    def test_plugin_updater_init_valid_path(self, tmp_path):
        """Test PluginUpdater initialization with valid project path.

        REQUIREMENT: PluginUpdater must validate project root on init.
        Expected: PluginUpdater instance created successfully.
        """
        project_root = tmp_path / "test_project"
        project_root.mkdir()
        (project_root / ".claude").mkdir()

        updater = PluginUpdater(project_root=project_root)

        assert updater.project_root == project_root
        assert updater.plugin_name == "autonomous-dev"

    def test_plugin_updater_init_custom_plugin_name(self, tmp_path):
        """Test PluginUpdater initialization with custom plugin name.

        REQUIREMENT: Support updating plugins other than autonomous-dev.
        Expected: PluginUpdater accepts custom plugin_name.
        """
        project_root = tmp_path / "test_project"
        project_root.mkdir()
        (project_root / ".claude").mkdir()

        updater = PluginUpdater(
            project_root=project_root,
            plugin_name="custom-plugin"
        )

        assert updater.plugin_name == "custom-plugin"

    @patch("plugins.autonomous_dev.lib.security_utils.validate_path")
    def test_plugin_updater_init_path_validation(self, mock_validate, tmp_path):
        """Test PluginUpdater validates path via security_utils.

        REQUIREMENT: All paths must be validated for security (CWE-22).
        Expected: security_utils.validate_path called on project_root.
        """
        project_root = tmp_path / "test_project"
        project_root.mkdir()
        (project_root / ".claude").mkdir()

        mock_validate.return_value = project_root

        updater = PluginUpdater(project_root=project_root)

        mock_validate.assert_called_once()
        call_args = mock_validate.call_args[0]
        assert str(call_args[0]) == str(project_root)

    def test_plugin_updater_init_invalid_path_raises(self, tmp_path):
        """Test PluginUpdater rejects invalid project path.

        REQUIREMENT: Reject paths outside whitelist.
        Expected: UpdateError raised for path traversal attempts.
        """
        invalid_path = Path("/etc/passwd")

        with pytest.raises(UpdateError) as exc_info:
            PluginUpdater(project_root=invalid_path)

        assert "Invalid project path" in str(exc_info.value)

    def test_plugin_updater_init_nonexistent_path_raises(self, tmp_path):
        """Test PluginUpdater rejects nonexistent project path.

        REQUIREMENT: Validate project path exists.
        Expected: UpdateError raised for nonexistent path.
        """
        nonexistent = tmp_path / "does_not_exist"

        with pytest.raises(UpdateError) as exc_info:
            PluginUpdater(project_root=nonexistent)

        assert "does not exist" in str(exc_info.value).lower()


class TestCheckForUpdates:
    """Test check_for_updates() version detection."""

    @pytest.fixture
    def temp_project(self, tmp_path):
        """Create temporary project with plugin structure."""
        project_root = tmp_path / "test_project"
        project_root.mkdir()
        (project_root / ".claude").mkdir()
        (project_root / ".claude" / "plugins").mkdir()
        plugin_dir = project_root / ".claude" / "plugins" / "autonomous-dev"
        plugin_dir.mkdir()
        return project_root

    @patch("plugins.autonomous_dev.lib.plugin_updater.detect_version_mismatch")
    def test_check_for_updates_upgrade_available(self, mock_detect, temp_project):
        """Test check_for_updates detects available upgrade.

        REQUIREMENT: Detect when marketplace has newer version.
        Expected: Returns VersionComparison with UPGRADE_AVAILABLE status.
        """
        # Mock version detector to return upgrade available
        mock_comparison = VersionComparison(
            project_version="3.7.0",
            marketplace_version="3.8.0",
            status=VersionComparison.UPGRADE_AVAILABLE,
            message="Upgrade available: 3.7.0 → 3.8.0"
        )
        mock_detect.return_value = mock_comparison

        updater = PluginUpdater(project_root=temp_project)
        comparison = updater.check_for_updates()

        assert comparison.status == VersionComparison.UPGRADE_AVAILABLE
        assert comparison.marketplace_version == "3.8.0"
        assert comparison.project_version == "3.7.0"
        mock_detect.assert_called_once()

    @patch("plugins.autonomous_dev.lib.plugin_updater.detect_version_mismatch")
    def test_check_for_updates_up_to_date(self, mock_detect, temp_project):
        """Test check_for_updates when versions match.

        REQUIREMENT: Detect when no update is needed.
        Expected: Returns VersionComparison with UP_TO_DATE status.
        """
        mock_comparison = VersionComparison(
            project_version="3.8.0",
            marketplace_version="3.8.0",
            status=VersionComparison.UP_TO_DATE,
            message="Versions are equal: 3.8.0"
        )
        mock_detect.return_value = mock_comparison

        updater = PluginUpdater(project_root=temp_project)
        comparison = updater.check_for_updates()

        assert comparison.status == VersionComparison.UP_TO_DATE
        assert comparison.is_upgrade is False
        assert comparison.is_downgrade is False

    @patch("plugins.autonomous_dev.lib.plugin_updater.detect_version_mismatch")
    def test_check_for_updates_downgrade_risk(self, mock_detect, temp_project):
        """Test check_for_updates detects downgrade scenario.

        REQUIREMENT: Warn user when marketplace is behind project.
        Expected: Returns VersionComparison with DOWNGRADE_RISK status.
        """
        mock_comparison = VersionComparison(
            project_version="3.9.0",
            marketplace_version="3.8.0",
            status=VersionComparison.DOWNGRADE_RISK,
            message="Downgrade risk: 3.9.0 → 3.8.0"
        )
        mock_detect.return_value = mock_comparison

        updater = PluginUpdater(project_root=temp_project)
        comparison = updater.check_for_updates()

        assert comparison.status == VersionComparison.DOWNGRADE_RISK
        assert comparison.is_downgrade is True

    @patch("plugins.autonomous_dev.lib.plugin_updater.detect_version_mismatch")
    def test_check_for_updates_error_handling(self, mock_detect, temp_project):
        """Test check_for_updates handles version detection errors.

        REQUIREMENT: Gracefully handle version detection failures.
        Expected: Raises UpdateError with helpful message.
        """
        mock_detect.side_effect = Exception("Marketplace not found")

        updater = PluginUpdater(project_root=temp_project)

        with pytest.raises(UpdateError) as exc_info:
            updater.check_for_updates()

        assert "failed to check for updates" in str(exc_info.value).lower()
        assert "Marketplace not found" in str(exc_info.value)


class TestCreateBackup:
    """Test _create_backup() backup creation."""

    @pytest.fixture
    def temp_project(self, tmp_path):
        """Create temporary project with plugin files."""
        project_root = tmp_path / "test_project"
        project_root.mkdir()
        (project_root / ".claude").mkdir()
        plugin_dir = project_root / ".claude" / "plugins" / "autonomous-dev"
        plugin_dir.mkdir(parents=True)

        # Create sample plugin files
        (plugin_dir / "plugin.json").write_text('{"version": "3.7.0"}')
        (plugin_dir / "commands").mkdir()
        (plugin_dir / "commands" / "test.md").write_text("# Test")

        return project_root

    def test_create_backup_success(self, temp_project):
        """Test successful backup creation.

        REQUIREMENT: Create timestamped backup before update.
        Expected: Backup directory created with all plugin files.
        """
        updater = PluginUpdater(project_root=temp_project)
        backup_path = updater._create_backup()

        assert backup_path.exists()
        assert backup_path.is_dir()
        assert "autonomous-dev-backup" in backup_path.name
        assert (backup_path / "plugin.json").exists()
        assert (backup_path / "commands" / "test.md").exists()

    def test_create_backup_permissions(self, temp_project):
        """Test backup directory has secure permissions.

        REQUIREMENT: Backup must be user-only accessible (CWE-732).
        Expected: Backup directory has 0o700 permissions.
        """
        updater = PluginUpdater(project_root=temp_project)
        backup_path = updater._create_backup()

        stat_info = os.stat(backup_path)
        permissions = stat_info.st_mode & 0o777

        # Should be user-only (rwx------)
        assert permissions == 0o700

    def test_create_backup_empty_plugin_dir(self, temp_project):
        """Test backup creation when plugin directory is empty.

        REQUIREMENT: Handle edge case of empty plugin directory.
        Expected: Backup directory created even if source is empty.
        """
        # Remove all files from plugin directory
        plugin_dir = temp_project / ".claude" / "plugins" / "autonomous-dev"
        shutil.rmtree(plugin_dir)
        plugin_dir.mkdir()

        updater = PluginUpdater(project_root=temp_project)
        backup_path = updater._create_backup()

        assert backup_path.exists()
        assert backup_path.is_dir()

    def test_create_backup_permission_denied(self, temp_project):
        """Test backup creation fails when permission denied.

        REQUIREMENT: Handle filesystem permission errors gracefully.
        Expected: BackupError raised with helpful message.
        """
        updater = PluginUpdater(project_root=temp_project)

        with patch("shutil.copytree") as mock_copy:
            mock_copy.side_effect = PermissionError("Permission denied")

            with pytest.raises(BackupError) as exc_info:
                updater._create_backup()

            assert "permission denied" in str(exc_info.value).lower()

    @patch("plugins.autonomous_dev.lib.security_utils.audit_log")
    def test_create_backup_audit_logged(self, mock_audit, temp_project):
        """Test backup creation is audit logged.

        REQUIREMENT: All backup operations must be logged (CWE-778).
        Expected: audit_log called with backup event.
        """
        updater = PluginUpdater(project_root=temp_project)
        backup_path = updater._create_backup()

        mock_audit.assert_called()
        # Check event_type (first argument)
        assert mock_audit.call_args[0][0] == "plugin_updater"
        # Check status (second argument)
        assert mock_audit.call_args[0][1] == "plugin_backup_created"
        # Check context dict (third argument)
        call_args = mock_audit.call_args[0][2]
        assert "backup_path" in call_args
        assert "plugin_name" in call_args


class TestRollback:
    """Test _rollback() backup restoration."""

    @pytest.fixture
    def temp_project_with_backup(self, tmp_path):
        """Create project with backup directory."""
        project_root = tmp_path / "test_project"
        project_root.mkdir()
        (project_root / ".claude").mkdir()
        plugin_dir = project_root / ".claude" / "plugins" / "autonomous-dev"
        plugin_dir.mkdir(parents=True)

        # Create backup directory
        backup_path = tmp_path / "autonomous-dev-backup-20251109-120000"
        backup_path.mkdir()
        (backup_path / "plugin.json").write_text('{"version": "3.7.0"}')
        (backup_path / "commands").mkdir()
        (backup_path / "commands" / "old.md").write_text("# Old Command")

        # Create corrupted current plugin
        (plugin_dir / "plugin.json").write_text('{"version": "3.8.0"}')
        (plugin_dir / "commands").mkdir()
        (plugin_dir / "commands" / "broken.md").write_text("# Broken")

        return {
            "project_root": project_root,
            "backup_path": backup_path,
            "plugin_dir": plugin_dir
        }

    def test_rollback_success(self, temp_project_with_backup):
        """Test successful rollback from backup.

        REQUIREMENT: Restore from backup when update fails.
        Expected: Plugin directory restored to backup state.
        """
        project_root = temp_project_with_backup["project_root"]
        backup_path = temp_project_with_backup["backup_path"]
        plugin_dir = temp_project_with_backup["plugin_dir"]

        updater = PluginUpdater(project_root=project_root)
        updater._rollback(backup_path)

        # Plugin should be restored to backup version
        plugin_json = json.loads((plugin_dir / "plugin.json").read_text())
        assert plugin_json["version"] == "3.7.0"
        assert (plugin_dir / "commands" / "old.md").exists()
        assert not (plugin_dir / "commands" / "broken.md").exists()

    def test_rollback_nonexistent_backup(self, temp_project_with_backup):
        """Test rollback fails when backup doesn't exist.

        REQUIREMENT: Handle missing backup gracefully.
        Expected: BackupError raised with clear message.
        """
        project_root = temp_project_with_backup["project_root"]
        nonexistent_backup = project_root / "nonexistent-backup"

        updater = PluginUpdater(project_root=project_root)

        with pytest.raises(BackupError) as exc_info:
            updater._rollback(nonexistent_backup)

        assert "backup path does not exist" in str(exc_info.value).lower()

    def test_rollback_permission_error(self, temp_project_with_backup):
        """Test rollback handles permission errors.

        REQUIREMENT: Gracefully handle filesystem permission errors.
        Expected: BackupError raised with helpful message.
        """
        project_root = temp_project_with_backup["project_root"]
        backup_path = temp_project_with_backup["backup_path"]

        updater = PluginUpdater(project_root=project_root)

        with patch("shutil.rmtree") as mock_rm:
            mock_rm.side_effect = PermissionError("Permission denied")

            with pytest.raises(BackupError) as exc_info:
                updater._rollback(backup_path)

            assert "permission" in str(exc_info.value).lower()

    @patch("plugins.autonomous_dev.lib.security_utils.audit_log")
    def test_rollback_audit_logged(self, mock_audit, temp_project_with_backup):
        """Test rollback is audit logged.

        REQUIREMENT: All rollback operations must be logged (CWE-778).
        Expected: audit_log called with rollback event.
        """
        project_root = temp_project_with_backup["project_root"]
        backup_path = temp_project_with_backup["backup_path"]

        updater = PluginUpdater(project_root=project_root)
        updater._rollback(backup_path)

        mock_audit.assert_called()
        # Check event_type (first argument)
        assert mock_audit.call_args[0][0] == "plugin_updater"
        # Check status (second argument)
        assert mock_audit.call_args[0][1] == "plugin_rollback"
        # Check context dict (third argument)
        call_args = mock_audit.call_args[0][2]
        assert "backup_path" in call_args


class TestCleanupBackup:
    """Test _cleanup_backup() backup removal."""

    def test_cleanup_backup_success(self, tmp_path):
        """Test successful backup cleanup.

        REQUIREMENT: Remove backup after successful update.
        Expected: Backup directory deleted.
        """
        project_root = tmp_path / "test_project"
        project_root.mkdir()
        (project_root / ".claude").mkdir()

        backup_path = tmp_path / "autonomous-dev-backup-20251109-120000"
        backup_path.mkdir()
        (backup_path / "test.txt").write_text("test")

        updater = PluginUpdater(project_root=project_root)
        updater._cleanup_backup(backup_path)

        assert not backup_path.exists()

    def test_cleanup_backup_nonexistent_ok(self, tmp_path):
        """Test cleanup succeeds even if backup doesn't exist.

        REQUIREMENT: Cleanup should be idempotent.
        Expected: No error raised if backup already gone.
        """
        project_root = tmp_path / "test_project"
        project_root.mkdir()
        (project_root / ".claude").mkdir()

        nonexistent = tmp_path / "nonexistent-backup"

        updater = PluginUpdater(project_root=project_root)
        # Should not raise
        updater._cleanup_backup(nonexistent)

    @patch("plugins.autonomous_dev.lib.security_utils.audit_log")
    def test_cleanup_backup_audit_logged(self, mock_audit, tmp_path):
        """Test backup cleanup is audit logged.

        REQUIREMENT: All cleanup operations must be logged (CWE-778).
        Expected: audit_log called with cleanup event.
        """
        project_root = tmp_path / "test_project"
        project_root.mkdir()
        (project_root / ".claude").mkdir()

        backup_path = tmp_path / "autonomous-dev-backup-20251109-120000"
        backup_path.mkdir()

        updater = PluginUpdater(project_root=project_root)
        updater._cleanup_backup(backup_path)

        mock_audit.assert_called()
        # Check event_type (first argument)
        assert mock_audit.call_args[0][0] == "plugin_updater"
        # Check status (second argument)
        assert mock_audit.call_args[0][1] == "plugin_backup_cleanup"
        # Check context dict (third argument)
        call_args = mock_audit.call_args[0][2]
        assert "backup_path" in call_args


class TestVerifyUpdate:
    """Test _verify_update() post-update validation."""

    @pytest.fixture
    def temp_project(self, tmp_path):
        """Create temporary project with plugin."""
        project_root = tmp_path / "test_project"
        project_root.mkdir()
        (project_root / ".claude").mkdir()
        plugin_dir = project_root / ".claude" / "plugins" / "autonomous-dev"
        plugin_dir.mkdir(parents=True)
        return project_root

    def test_verify_update_success(self, temp_project):
        """Test successful update verification.

        REQUIREMENT: Verify plugin updated correctly.
        Expected: Verification passes for correct version and files.
        """
        plugin_dir = temp_project / ".claude" / "plugins" / "autonomous-dev"
        (plugin_dir / "plugin.json").write_text(json.dumps({
            "name": "autonomous-dev",
            "version": "3.8.0"
        }))
        (plugin_dir / "commands").mkdir()
        (plugin_dir / "commands" / "test.md").write_text("# Test")

        updater = PluginUpdater(project_root=temp_project)
        # Should not raise
        updater._verify_update(expected_version="3.8.0")

    def test_verify_update_version_mismatch(self, temp_project):
        """Test verification fails on version mismatch.

        REQUIREMENT: Detect version mismatch after update.
        Expected: VerificationError raised if version doesn't match.
        """
        plugin_dir = temp_project / ".claude" / "plugins" / "autonomous-dev"
        (plugin_dir / "plugin.json").write_text(json.dumps({
            "name": "autonomous-dev",
            "version": "3.7.0"  # Wrong version
        }))

        updater = PluginUpdater(project_root=temp_project)

        with pytest.raises(VerificationError) as exc_info:
            updater._verify_update(expected_version="3.8.0")

        assert "version mismatch" in str(exc_info.value).lower()
        assert "3.8.0" in str(exc_info.value)
        assert "3.7.0" in str(exc_info.value)

    def test_verify_update_missing_plugin_json(self, temp_project):
        """Test verification fails when plugin.json missing.

        REQUIREMENT: Detect corrupted update.
        Expected: VerificationError raised for missing plugin.json.
        """
        # Don't create plugin.json - plugin_dir already exists from fixture
        plugin_dir = temp_project / ".claude" / "plugins" / "autonomous-dev"

        # Delete plugin.json if it exists
        plugin_json = plugin_dir / "plugin.json"
        if plugin_json.exists():
            plugin_json.unlink()

        updater = PluginUpdater(project_root=temp_project)

        with pytest.raises(VerificationError) as exc_info:
            updater._verify_update(expected_version="3.8.0")

        assert "plugin.json not found" in str(exc_info.value).lower()

    def test_verify_update_corrupted_plugin_json(self, temp_project):
        """Test verification fails on corrupted plugin.json.

        REQUIREMENT: Detect JSON corruption.
        Expected: VerificationError raised for invalid JSON.
        """
        plugin_dir = temp_project / ".claude" / "plugins" / "autonomous-dev"
        (plugin_dir / "plugin.json").write_text("not valid json {{{")

        updater = PluginUpdater(project_root=temp_project)

        with pytest.raises(VerificationError) as exc_info:
            updater._verify_update(expected_version="3.8.0")

        assert "corrupted" in str(exc_info.value).lower() or "invalid json" in str(exc_info.value).lower()


class TestUpdateMethod:
    """Test update() main workflow method."""

    @pytest.fixture
    def temp_project(self, tmp_path):
        """Create temporary project."""
        project_root = tmp_path / "test_project"
        project_root.mkdir()
        (project_root / ".claude").mkdir()
        plugin_dir = project_root / ".claude" / "plugins" / "autonomous-dev"
        plugin_dir.mkdir(parents=True)
        (plugin_dir / "plugin.json").write_text(json.dumps({
            "name": "autonomous-dev",
            "version": "3.7.0"
        }))
        return project_root

    @patch("plugins.autonomous_dev.lib.plugin_updater.detect_version_mismatch")
    @patch("plugins.autonomous_dev.lib.plugin_updater.sync_marketplace")
    def test_update_success_workflow(self, mock_sync, mock_detect, temp_project):
        """Test successful update workflow end-to-end.

        REQUIREMENT: Complete update workflow with backup, sync, verify.
        Expected: UpdateResult with success=True, version updated.
        """
        # Mock version detection - upgrade available
        mock_detect.return_value = VersionComparison(
            project_version="3.7.0",
            marketplace_version="3.8.0",
            status=VersionComparison.UPGRADE_AVAILABLE,
            message="Upgrade available: 3.7.0 → 3.8.0"
        )

        # Mock successful sync
        mock_sync.return_value = SyncResult(
            success=True,
            mode=SyncMode.MARKETPLACE,
            message="Synced successfully",
            details={"files_updated": 5}
        )

        # Update plugin.json to new version after sync
        plugin_dir = temp_project / ".claude" / "plugins" / "autonomous-dev"
        with patch.object(Path, "read_text") as mock_read:
            mock_read.return_value = json.dumps({
                "name": "autonomous-dev",
                "version": "3.8.0"
            })

            updater = PluginUpdater(project_root=temp_project)
            result = updater.update()

            assert result.success is True
            assert result.updated is True
            assert result.old_version == "3.7.0"
            assert result.new_version == "3.8.0"
            assert result.rollback_performed is False
            assert result.backup_path is not None

    @patch("plugins.autonomous_dev.lib.plugin_updater.detect_version_mismatch")
    def test_update_no_update_needed(self, mock_detect, temp_project):
        """Test update when versions are equal.

        REQUIREMENT: Skip update if already up-to-date.
        Expected: UpdateResult with updated=False.
        """
        # Mock version detection - up to date
        mock_detect.return_value = VersionComparison(
            project_version="3.8.0",
            marketplace_version="3.8.0",
            status=VersionComparison.UP_TO_DATE,
            message="Versions are equal: 3.8.0"
        )

        updater = PluginUpdater(project_root=temp_project)
        result = updater.update()

        assert result.success is True
        assert result.updated is False
        assert result.message == "Plugin is already up to date"

    @patch("plugins.autonomous_dev.lib.plugin_updater.detect_version_mismatch")
    @patch("plugins.autonomous_dev.lib.plugin_updater.sync_marketplace")
    def test_update_rollback_on_verification_failure(self, mock_sync, mock_detect, temp_project):
        """Test rollback when verification fails.

        REQUIREMENT: Rollback on verification failure.
        Expected: UpdateResult with rollback_performed=True, success=False.
        """
        # Mock version detection
        mock_detect.return_value = VersionComparison(
            project_version="3.7.0",
            marketplace_version="3.8.0",
            status=VersionComparison.UPGRADE_AVAILABLE,
            message="Upgrade available: 3.7.0 → 3.8.0"
        )

        # Mock successful sync
        mock_sync.return_value = SyncResult(
            success=True,
            mode=SyncMode.MARKETPLACE,
            message="Synced",
            details={}
        )

        updater = PluginUpdater(project_root=temp_project)

        # Mock verification failure
        with patch.object(updater, "_verify_update") as mock_verify:
            mock_verify.side_effect = VerificationError("Version mismatch")

            result = updater.update()

            assert result.success is False
            assert result.rollback_performed is True
            assert "verification failed" in result.message.lower()

    @patch("plugins.autonomous_dev.lib.plugin_updater.detect_version_mismatch")
    @patch("plugins.autonomous_dev.lib.plugin_updater.sync_marketplace")
    def test_update_sync_failure(self, mock_sync, mock_detect, temp_project):
        """Test update handles sync failure.

        REQUIREMENT: Handle sync errors gracefully.
        Expected: UpdateResult with success=False, rollback performed (restore original state).
        """
        # Mock version detection
        mock_detect.return_value = VersionComparison(
            project_version="3.7.0",
            marketplace_version="3.8.0",
            status=VersionComparison.UPGRADE_AVAILABLE,
            message="Upgrade available: 3.7.0 → 3.8.0"
        )

        # Mock failed sync
        mock_sync.return_value = SyncResult(
            success=False,
            mode=SyncMode.MARKETPLACE,
            message="Sync failed: Permission denied",
            details={"error": "Permission denied"}
        )

        updater = PluginUpdater(project_root=temp_project)
        result = updater.update()

        assert result.success is False
        # Rollback SHOULD be performed to restore original state after backup was created
        assert result.rollback_performed is True
        assert "sync failed" in result.message.lower()

    @patch("plugins.autonomous_dev.lib.security_utils.audit_log")
    @patch("plugins.autonomous_dev.lib.plugin_updater.detect_version_mismatch")
    def test_update_audit_logged(self, mock_detect, mock_audit, temp_project):
        """Test update operations are audit logged.

        REQUIREMENT: All update operations must be logged (CWE-778).
        Expected: audit_log called for update events.
        """
        mock_detect.return_value = VersionComparison(
            project_version="3.8.0",
            marketplace_version="3.8.0",
            status=VersionComparison.UP_TO_DATE,
            message="Versions are equal: 3.8.0"
        )

        updater = PluginUpdater(project_root=temp_project)
        result = updater.update()

        # Should log update check
        assert mock_audit.called
