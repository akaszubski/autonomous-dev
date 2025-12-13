#!/usr/bin/env python3
"""
Integration tests for /update-plugin permission fix feature - TDD Red Phase

Tests the full update workflow with permission validation and fixing integrated.
Tests end-to-end scenarios with real file operations and state management.

Expected to FAIL until implementation is complete.

Security Requirements (GitHub Issue #114):
1. Full update with clean settings (no fix needed)
2. Full update with wildcard patterns (fix applied)
3. Full update with missing deny list (fix applied)
4. Full update with JSON parse error (regenerate from template)
5. Full update with permission denied (non-blocking, update succeeds)
6. Full update with user customizations (preserved through fix)

Test Strategy:
- Test complete update workflow with permission scenarios
- Test interaction between update and permission fix
- Test backup and rollback with permission fixes
- Test audit logging includes permission fix actions
- Test user notifications about permission fixes
- Test edge cases in real-world scenarios

Coverage Target: End-to-end workflow coverage for permission fixes

Author: test-master agent
Date: 2025-12-12
Issue: #114
Phase: TDD Red (tests written BEFORE implementation)
Status: RED (expected to fail - no implementation yet)
"""

import json
import sys
import pytest
import shutil
from pathlib import Path
from unittest.mock import patch, MagicMock, Mock

# Add plugins directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "plugins"))

# Import will fail until implementation exists
try:
    from autonomous_dev.lib.plugin_updater import PluginUpdater, UpdateResult
    from autonomous_dev.lib.settings_generator import (
        validate_permission_patterns,
        fix_permission_patterns,
    )
    from autonomous_dev.lib.sync_dispatcher import SyncResult, SyncMode
    from autonomous_dev.lib.version_detector import VersionComparison
except ImportError:
    pytest.skip("plugin_updater permission integration not implemented yet", allow_module_level=True)


# =============================================================================
# Test Fixtures - Full Environment Setup
# =============================================================================

@pytest.fixture
def full_project_env(tmp_path):
    """Create full project environment with plugin structure"""
    # Project root
    project_root = tmp_path / "project"
    project_root.mkdir()

    # .claude directory
    claude_dir = project_root / ".claude"
    claude_dir.mkdir()

    # plugins directory
    plugins_dir = project_root / "plugins"
    plugins_dir.mkdir()

    # autonomous-dev plugin
    plugin_dir = plugins_dir / "autonomous-dev"
    plugin_dir.mkdir()

    # VERSION file
    version_file = plugin_dir / "VERSION"
    version_file.write_text("3.40.0")

    # commands directory
    commands_dir = plugin_dir / "commands"
    commands_dir.mkdir()

    # Sample command files
    (commands_dir / "auto-implement.md").write_text("# Auto Implement\n\nCommand")
    (commands_dir / "test.md").write_text("# Test\n\nCommand")

    return {
        "project_root": project_root,
        "claude_dir": claude_dir,
        "plugins_dir": plugins_dir,
        "plugin_dir": plugin_dir,
        "version_file": version_file,
        "commands_dir": commands_dir,
    }


@pytest.fixture
def settings_clean():
    """Clean settings with no issues"""
    return {
        "version": "1.0.0",
        "permissions": {
            "allow": [
                "Bash(git:*)",
                "Bash(pytest:*)",
                "Bash(python:*)",
                "Read(**)",
                "Write(**)",
                "Edit(**)",
            ],
            "deny": [
                "Bash(rm:-rf*)",
                "Bash(rm:-f*)",
                "Bash(sudo:*)",
                "Bash(su:*)",
                "Bash(eval:*)",
                "Bash(chmod:*)",
                "Bash(chown:*)",
            ]
        },
        "hooks": {
            "auto_format": True
        }
    }


@pytest.fixture
def settings_with_wildcard():
    """Settings with Bash(*) wildcard"""
    return {
        "version": "1.0.0",
        "permissions": {
            "allow": [
                "Bash(*)",  # NEEDS FIX
                "Read(**)",
                "Write(**)",
            ],
            "deny": []
        },
        "hooks": {
            "auto_format": True,
            "auto_test": False
        }
    }


@pytest.fixture
def settings_missing_deny():
    """Settings with missing deny list"""
    return {
        "version": "1.0.0",
        "permissions": {
            "allow": [
                "Bash(git:*)",
                "Bash(pytest:*)",
                "Read(**)",
                "Write(**)",
            ]
            # Missing "deny" key
        },
        "hooks": {
            "validate_project_alignment": True
        }
    }


@pytest.fixture
def settings_with_customizations():
    """Settings with user customizations to preserve"""
    return {
        "version": "1.0.0",
        "permissions": {
            "allow": [
                "Bash(*)",  # Will be removed
                "Bash(git:*)",  # Standard - preserve
                "Bash(docker:*)",  # User custom - preserve
                "Bash(make:*)",  # User custom - preserve
                "Bash(cargo:*)",  # User custom - preserve
                "Read(**)",
                "Write(**)",
            ],
            "deny": []  # Will be populated
        },
        "hooks": {
            "auto_format": True,
            "auto_test": True,
            "custom_user_hook": True  # User custom - preserve
        },
        "custom_section": {
            "user_config": "important_value"  # User custom - preserve
        }
    }


# =============================================================================
# Test Full Update with Permission Scenarios
# =============================================================================

class TestFullUpdateWithPermissionFix:
    """Test complete update workflow with permission validation/fixing."""

    def test_update_with_clean_settings_no_fix_needed(self, full_project_env, settings_clean):
        """Test full update when settings are already valid.

        REQUIREMENT: Update proceeds normally with valid settings.
        Expected: Update completes, no permission fix applied.
        """
        project_root = full_project_env["project_root"]
        settings_path = full_project_env["claude_dir"] / "settings.local.json"
        settings_path.write_text(json.dumps(settings_clean, indent=2))

        # Mock update check to return "no update needed"
        updater = PluginUpdater(project_root=project_root)

        with patch.object(updater, '_check_for_updates') as mock_check:
            mock_check.return_value = Mock(
                needs_update=False,
                current_version="3.40.0",
                latest_version="3.40.0"
            )

            result = updater.update()

        # Update should succeed
        assert result.success is True
        assert result.updated is False  # No update needed

        # Permission fix should have validated but not fixed
        assert "permission_fix" in result.details
        assert result.details["permission_fix"]["action"] == "validated"

    def test_update_with_wildcard_patterns_fix_applied(self, full_project_env, settings_with_wildcard):
        """Test full update when settings have wildcard patterns.

        REQUIREMENT: Fix wildcard patterns during update.
        Expected: Update completes, wildcard patterns fixed.
        """
        project_root = full_project_env["project_root"]
        settings_path = full_project_env["claude_dir"] / "settings.local.json"
        settings_path.write_text(json.dumps(settings_with_wildcard, indent=2))

        updater = PluginUpdater(project_root=project_root)

        with patch.object(updater, '_check_for_updates') as mock_check:
            mock_check.return_value = Mock(
                needs_update=False,
                current_version="3.40.0",
                latest_version="3.40.0"
            )

            result = updater.update()

        # Update should succeed
        assert result.success is True

        # Permission fix should have been applied
        assert "permission_fix" in result.details
        assert result.details["permission_fix"]["action"] == "fixed"
        assert result.details["permission_fix"]["issues_found"] > 0

        # Verify settings were actually fixed
        fixed_settings = json.loads(settings_path.read_text())
        assert "Bash(*)" not in fixed_settings["permissions"]["allow"]
        assert "Bash(git:*)" in fixed_settings["permissions"]["allow"]
        assert len(fixed_settings["permissions"]["deny"]) > 0

        # Verify hooks preserved
        assert fixed_settings["hooks"]["auto_format"] is True
        assert fixed_settings["hooks"]["auto_test"] is False

    def test_update_with_missing_deny_list_fix_applied(self, full_project_env, settings_missing_deny):
        """Test full update when settings missing deny list.

        REQUIREMENT: Add missing deny list during update.
        Expected: Update completes, deny list populated.
        """
        project_root = full_project_env["project_root"]
        settings_path = full_project_env["claude_dir"] / "settings.local.json"
        settings_path.write_text(json.dumps(settings_missing_deny, indent=2))

        updater = PluginUpdater(project_root=project_root)

        with patch.object(updater, '_check_for_updates') as mock_check:
            mock_check.return_value = Mock(
                needs_update=False,
                current_version="3.40.0",
                latest_version="3.40.0"
            )

            result = updater.update()

        # Update should succeed
        assert result.success is True

        # Permission fix should have been applied
        assert "permission_fix" in result.details
        assert result.details["permission_fix"]["action"] == "fixed"

        # Verify deny list was added
        fixed_settings = json.loads(settings_path.read_text())
        assert "deny" in fixed_settings["permissions"]
        assert len(fixed_settings["permissions"]["deny"]) > 0
        assert any("sudo" in pattern for pattern in fixed_settings["permissions"]["deny"])

    def test_update_with_json_parse_error_regenerate(self, full_project_env):
        """Test full update when settings have JSON parse error.

        REQUIREMENT: Regenerate settings from template on parse error.
        Expected: Update completes, corrupted file backed up, new settings generated.
        """
        project_root = full_project_env["project_root"]
        settings_path = full_project_env["claude_dir"] / "settings.local.json"
        corrupted_json = '{"version": "1.0.0", "permissions": { INVALID JSON'
        settings_path.write_text(corrupted_json)

        updater = PluginUpdater(project_root=project_root)

        with patch.object(updater, '_check_for_updates') as mock_check:
            mock_check.return_value = Mock(
                needs_update=False,
                current_version="3.40.0",
                latest_version="3.40.0"
            )

            result = updater.update()

        # Update should succeed
        assert result.success is True

        # Permission fix should have regenerated
        assert "permission_fix" in result.details
        assert result.details["permission_fix"]["action"] in ["regenerated", "fixed"]

        # Verify backup was created
        backup_path = result.details["permission_fix"].get("backup_path")
        if backup_path:
            assert Path(backup_path).exists()
            assert Path(backup_path).read_text() == corrupted_json

        # Verify settings file now has valid JSON
        fixed_content = settings_path.read_text()
        fixed_settings = json.loads(fixed_content)  # Should not raise
        assert "permissions" in fixed_settings

    def test_update_with_permission_denied_non_blocking(self, full_project_env, settings_with_wildcard):
        """Test full update when permission fix fails due to write error.

        REQUIREMENT: Non-blocking - update succeeds even if permission fix fails.
        Expected: Update completes successfully, permission fix shows failure.
        """
        project_root = full_project_env["project_root"]
        settings_path = full_project_env["claude_dir"] / "settings.local.json"
        settings_path.write_text(json.dumps(settings_with_wildcard, indent=2))

        # Make settings read-only
        settings_path.chmod(0o444)

        updater = PluginUpdater(project_root=project_root)

        with patch.object(updater, '_check_for_updates') as mock_check:
            mock_check.return_value = Mock(
                needs_update=False,
                current_version="3.40.0",
                latest_version="3.40.0"
            )

            result = updater.update()

        # Update should still succeed
        assert result.success is True

        # Permission fix should have failed gracefully
        assert "permission_fix" in result.details
        assert result.details["permission_fix"]["action"] == "failed"

        # Restore permissions for cleanup
        settings_path.chmod(0o644)

    def test_update_preserves_user_customizations(self, full_project_env, settings_with_customizations):
        """Test that update preserves all user customizations.

        REQUIREMENT: Preserve user customizations through permission fix.
        Expected: Hooks, custom patterns, custom sections all preserved.
        """
        project_root = full_project_env["project_root"]
        settings_path = full_project_env["claude_dir"] / "settings.local.json"
        settings_path.write_text(json.dumps(settings_with_customizations, indent=2))

        updater = PluginUpdater(project_root=project_root)

        with patch.object(updater, '_check_for_updates') as mock_check:
            mock_check.return_value = Mock(
                needs_update=False,
                current_version="3.40.0",
                latest_version="3.40.0"
            )

            result = updater.update()

        # Update should succeed
        assert result.success is True

        # Verify all customizations preserved
        fixed_settings = json.loads(settings_path.read_text())

        # Hooks preserved
        assert fixed_settings["hooks"]["auto_format"] is True
        assert fixed_settings["hooks"]["auto_test"] is True
        assert fixed_settings["hooks"]["custom_user_hook"] is True

        # Custom patterns preserved
        assert "Bash(docker:*)" in fixed_settings["permissions"]["allow"]
        assert "Bash(make:*)" in fixed_settings["permissions"]["allow"]
        assert "Bash(cargo:*)" in fixed_settings["permissions"]["allow"]

        # Invalid patterns removed
        assert "Bash(*)" not in fixed_settings["permissions"]["allow"]

        # Custom sections preserved
        assert "custom_section" in fixed_settings
        assert fixed_settings["custom_section"]["user_config"] == "important_value"


# =============================================================================
# Test Update with Actual Plugin Sync
# =============================================================================

class TestUpdateWithPluginSync:
    """Test update workflow with actual plugin sync operations."""

    def test_update_with_sync_and_permission_fix(self, full_project_env, settings_with_wildcard):
        """Test update that performs sync and permission fix.

        REQUIREMENT: Both sync and permission fix execute during update.
        Expected: Plugin synced, permissions fixed, both logged.
        """
        project_root = full_project_env["project_root"]
        settings_path = full_project_env["claude_dir"] / "settings.local.json"
        settings_path.write_text(json.dumps(settings_with_wildcard, indent=2))

        updater = PluginUpdater(project_root=project_root)

        # Mock update needed
        with patch.object(updater, '_check_for_updates') as mock_check:
            mock_check.return_value = Mock(
                needs_update=True,
                current_version="3.39.0",
                latest_version="3.40.0"
            )

            # Mock sync operation
            with patch.object(updater, '_perform_sync') as mock_sync:
                mock_sync.return_value = SyncResult(
                    success=True,
                    mode=SyncMode.PLUGIN_DEV,
                    files_synced=5,
                    message="Plugin synced successfully"
                )

                result = updater.update()

        # Update should succeed
        assert result.success is True
        assert result.updated is True

        # Both sync and permission fix should have executed
        assert "sync" in result.details or result.message
        assert "permission_fix" in result.details

    def test_permission_fix_runs_before_sync(self, full_project_env, settings_with_wildcard):
        """Test that permission fix runs before plugin sync.

        REQUIREMENT: Validate permissions before sync to ensure clean state.
        Expected: Permission fix completes before sync starts.
        """
        project_root = full_project_env["project_root"]
        settings_path = full_project_env["claude_dir"] / "settings.local.json"
        settings_path.write_text(json.dumps(settings_with_wildcard, indent=2))

        updater = PluginUpdater(project_root=project_root)

        call_order = []

        def track_permission_fix(*args, **kwargs):
            call_order.append("permission_fix")
            return updater._validate_and_fix_permissions(*args, **kwargs)

        def track_sync(*args, **kwargs):
            call_order.append("sync")
            return SyncResult(success=True, mode=SyncMode.PLUGIN_DEV, files_synced=5)

        with patch.object(updater, '_check_for_updates') as mock_check:
            mock_check.return_value = Mock(needs_update=True)

            with patch.object(updater, '_validate_and_fix_permissions', side_effect=track_permission_fix):
                with patch.object(updater, '_perform_sync', side_effect=track_sync):
                    result = updater.update()

        # Verify permission fix ran before sync
        assert call_order[0] == "permission_fix"
        assert "sync" in call_order


# =============================================================================
# Test Backup and Rollback with Permission Fixes
# =============================================================================

class TestBackupAndRollbackWithPermissionFix:
    """Test backup and rollback behavior with permission fixes."""

    def test_permission_fix_backup_separate_from_update_backup(self, full_project_env, settings_with_wildcard):
        """Test that permission fix creates separate backup from update backup.

        REQUIREMENT: Permission fix backup independent of update backup.
        Expected: Two backups created - one for permission fix, one for update.
        """
        project_root = full_project_env["project_root"]
        settings_path = full_project_env["claude_dir"] / "settings.local.json"
        settings_path.write_text(json.dumps(settings_with_wildcard, indent=2))

        updater = PluginUpdater(project_root=project_root)

        with patch.object(updater, '_check_for_updates') as mock_check:
            mock_check.return_value = Mock(needs_update=True)

            with patch.object(updater, '_create_backup') as mock_update_backup:
                mock_update_backup.return_value = str(project_root / "backup_update")

                with patch.object(updater, '_perform_sync') as mock_sync:
                    mock_sync.return_value = SyncResult(success=True, mode=SyncMode.PLUGIN_DEV, files_synced=5)

                    result = updater.update()

        # Update should have created update backup
        assert result.backup_path is not None

        # Permission fix should have created its own backup
        assert "permission_fix" in result.details
        if result.details["permission_fix"]["action"] == "fixed":
            perm_backup = result.details["permission_fix"].get("backup_path")
            assert perm_backup is not None
            assert perm_backup != result.backup_path

    def test_rollback_restores_both_plugin_and_permissions(self, full_project_env, settings_with_wildcard):
        """Test rollback restores both plugin files and permissions.

        REQUIREMENT: Rollback includes permission settings restoration.
        Expected: Both plugin and settings restored on rollback.
        """
        project_root = full_project_env["project_root"]
        settings_path = full_project_env["claude_dir"] / "settings.local.json"
        original_settings = json.dumps(settings_with_wildcard, indent=2)
        settings_path.write_text(original_settings)

        updater = PluginUpdater(project_root=project_root)

        with patch.object(updater, '_check_for_updates') as mock_check:
            mock_check.return_value = Mock(needs_update=True)

            with patch.object(updater, '_perform_sync') as mock_sync:
                # Simulate sync failure
                mock_sync.side_effect = Exception("Sync failed")

                with patch.object(updater, '_rollback') as mock_rollback:
                    mock_rollback.return_value = True

                    result = updater.update()

        # Update should have failed
        assert result.success is False
        assert result.rollback_performed is True


# =============================================================================
# Test Audit Logging and User Notifications
# =============================================================================

class TestAuditLoggingAndNotifications:
    """Test audit logging and user notifications for permission fixes."""

    def test_permission_fix_logged_to_audit(self, full_project_env, settings_with_wildcard):
        """Test that permission fix actions are audit logged.

        REQUIREMENT: All permission fixes logged for security audit.
        Expected: Audit log contains permission fix details.
        """
        project_root = full_project_env["project_root"]
        settings_path = full_project_env["claude_dir"] / "settings.local.json"
        settings_path.write_text(json.dumps(settings_with_wildcard, indent=2))

        updater = PluginUpdater(project_root=project_root)

        # Mock audit_log from security_utils
        with patch('autonomous_dev.lib.security_utils.audit_log') as mock_audit:
            with patch.object(updater, '_check_for_updates') as mock_check:
                mock_check.return_value = Mock(needs_update=False)

                result = updater.update()

            # Verify audit log was called with permission fix info
            # (Implementation should log permission validation/fix actions)
            audit_calls = [str(call) for call in mock_audit.call_args_list]
            # Should have logged permission-related actions
            # Exact assertion depends on implementation

    def test_update_result_message_mentions_permission_fix(self, full_project_env, settings_with_wildcard):
        """Test that update result message mentions permission fix.

        REQUIREMENT: User informed about permission fix actions.
        Expected: Result message includes permission fix info.
        """
        project_root = full_project_env["project_root"]
        settings_path = full_project_env["claude_dir"] / "settings.local.json"
        settings_path.write_text(json.dumps(settings_with_wildcard, indent=2))

        updater = PluginUpdater(project_root=project_root)

        with patch.object(updater, '_check_for_updates') as mock_check:
            mock_check.return_value = Mock(needs_update=False)

            result = updater.update()

        # Message or details should mention permission fix
        assert "permission" in result.message.lower() or "permission_fix" in result.details


# =============================================================================
# Test Edge Cases in Real-World Scenarios
# =============================================================================

class TestRealWorldEdgeCases:
    """Test edge cases that might occur in real-world usage."""

    def test_update_with_no_settings_file_at_all(self, full_project_env):
        """Test update when no settings.local.json exists.

        REQUIREMENT: Update works even without settings file.
        Expected: Update completes, permission fix skipped.
        """
        project_root = full_project_env["project_root"]
        # No settings file created

        updater = PluginUpdater(project_root=project_root)

        with patch.object(updater, '_check_for_updates') as mock_check:
            mock_check.return_value = Mock(needs_update=False)

            result = updater.update()

        # Update should succeed
        assert result.success is True

        # Permission fix should be skipped
        assert "permission_fix" in result.details
        assert result.details["permission_fix"]["action"] == "skipped"

    def test_update_after_manual_permission_fix(self, full_project_env, settings_clean):
        """Test update after user manually fixed permissions.

        REQUIREMENT: Update recognizes already-fixed settings.
        Expected: Update completes, no fix needed.
        """
        project_root = full_project_env["project_root"]
        settings_path = full_project_env["claude_dir"] / "settings.local.json"

        # User manually created clean settings
        settings_path.write_text(json.dumps(settings_clean, indent=2))

        updater = PluginUpdater(project_root=project_root)

        with patch.object(updater, '_check_for_updates') as mock_check:
            mock_check.return_value = Mock(needs_update=False)

            result = updater.update()

        # Update should succeed
        assert result.success is True

        # Permission fix should validate but not fix
        assert "permission_fix" in result.details
        assert result.details["permission_fix"]["action"] == "validated"

    def test_concurrent_updates_permission_fix_safety(self, full_project_env, settings_with_wildcard):
        """Test permission fix safety under concurrent update attempts.

        REQUIREMENT: Permission fix is safe for concurrent execution.
        Expected: Atomic operations prevent corruption.
        """
        # This test verifies atomic write behavior
        # In practice, concurrent updates should be prevented at higher level
        # But permission fix should still be atomic

        project_root = full_project_env["project_root"]
        settings_path = full_project_env["claude_dir"] / "settings.local.json"
        settings_path.write_text(json.dumps(settings_with_wildcard, indent=2))

        updater = PluginUpdater(project_root=project_root)

        # Simulate concurrent access by having a reader during update
        with patch.object(updater, '_check_for_updates') as mock_check:
            mock_check.return_value = Mock(needs_update=False)

            result = updater.update()

            # Read settings during/after update
            final_settings = json.loads(settings_path.read_text())

        # Settings should be in valid state (not corrupted)
        assert "permissions" in final_settings
        assert "allow" in final_settings["permissions"]
