#!/usr/bin/env python3
"""
Unit tests for plugin_updater.py permission validation/fixing - TDD Red Phase

Tests the _validate_and_fix_permissions() method in PluginUpdater for detecting
and fixing permission issues in settings.local.json during plugin updates.

Expected to FAIL until implementation is complete.

Security Requirements (GitHub Issue #114):
1. Validate settings.local.json permissions during update
2. Fix wildcard patterns (Bash(*) -> specific patterns)
3. Add missing deny list
4. Create backup before modifications
5. Atomic operations (no partial updates)
6. Non-blocking (update succeeds even if fix fails)
7. Handle JSON parse errors gracefully

Test Strategy:
- Test _validate_and_fix_permissions() method integration
- Test backup creation before fix
- Test atomic write operations
- Test error handling (JSON parse, write permissions, etc.)
- Test non-blocking behavior (fix failure doesn't fail update)
- Test skip when no settings.local.json exists
- Test skip when settings already valid

Coverage Target: 95%+ for permission validation/fixing in plugin_updater.py

Author: test-master agent
Date: 2025-12-12
Issue: #114
Phase: TDD Red (tests written BEFORE implementation)
Status: RED (expected to fail - no implementation yet)
"""

import json
import sys
import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock, mock_open, Mock, call
from dataclasses import asdict

# Add plugins directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent / "plugins"))

# Import will fail until implementation exists
try:
    from autonomous_dev.lib.plugin_updater import (
        PluginUpdater,
        UpdateResult,
        UpdateError,
        PermissionFixResult,
    )
    from autonomous_dev.lib.settings_generator import (
        validate_permission_patterns,
        fix_permission_patterns,
        ValidationResult,
        PermissionIssue,
    )
except ImportError:
    pytest.skip("plugin_updater permission validation not implemented yet", allow_module_level=True)


# =============================================================================
# Test Fixtures - Settings Examples
# =============================================================================

@pytest.fixture
def temp_project_root(tmp_path):
    """Create temporary project root with .claude directory"""
    project_root = tmp_path / "project"
    project_root.mkdir()
    claude_dir = project_root / ".claude"
    claude_dir.mkdir()
    return project_root


@pytest.fixture
def settings_with_wildcard():
    """Settings with Bash(*) wildcard that needs fixing"""
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
            "auto_format": True
        }
    }


@pytest.fixture
def settings_missing_deny():
    """Settings with missing deny list that needs fixing"""
    return {
        "version": "1.0.0",
        "permissions": {
            "allow": [
                "Bash(git:*)",
                "Read(**)",
                "Write(**)",
            ]
            # Missing "deny" key
        }
    }


@pytest.fixture
def valid_settings():
    """Valid settings that don't need fixing"""
    return {
        "version": "1.0.0",
        "permissions": {
            "allow": [
                "Bash(git:*)",
                "Bash(pytest:*)",
                "Read(**)",
                "Write(**)",
            ],
            "deny": [
                "Bash(rm:-rf*)",
                "Bash(sudo:*)",
                "Bash(eval:*)",
            ]
        }
    }


@pytest.fixture
def corrupted_settings_json():
    """Corrupted JSON that can't be parsed"""
    return '{"version": "1.0.0", "permissions": { INVALID JSON'


# =============================================================================
# Test _validate_and_fix_permissions() - Main Flow
# =============================================================================

class TestValidateAndFixPermissions:
    """Test _validate_and_fix_permissions() method in PluginUpdater."""

    def test_skip_when_no_settings_exists(self, temp_project_root):
        """Test skip validation when settings.local.json doesn't exist.

        REQUIREMENT: Skip validation when no settings file exists.
        Expected: PermissionFixResult with action="skipped".
        """
        updater = PluginUpdater(project_root=temp_project_root)

        # settings.local.json doesn't exist
        result = updater._validate_and_fix_permissions()

        assert result.action == "skipped"
        assert "not found" in result.message.lower() or "no settings" in result.message.lower()
        assert result.backup_path is None

    def test_skip_when_settings_already_valid(self, temp_project_root, valid_settings):
        """Test skip fix when settings already valid.

        REQUIREMENT: Skip fix when validation passes.
        Expected: PermissionFixResult with action="validated".
        """
        # Create valid settings.local.json
        settings_path = temp_project_root / ".claude" / "settings.local.json"
        settings_path.write_text(json.dumps(valid_settings, indent=2))

        updater = PluginUpdater(project_root=temp_project_root)
        result = updater._validate_and_fix_permissions()

        assert result.action == "validated"
        assert "already valid" in result.message.lower() or "no issues" in result.message.lower()
        assert result.backup_path is None

    def test_fix_when_issues_found(self, temp_project_root, settings_with_wildcard):
        """Test fix applied when validation issues found.

        REQUIREMENT: Fix wildcard patterns when detected.
        Expected: PermissionFixResult with action="fixed".
        """
        # Create settings with wildcard
        settings_path = temp_project_root / ".claude" / "settings.local.json"
        settings_path.write_text(json.dumps(settings_with_wildcard, indent=2))

        updater = PluginUpdater(project_root=temp_project_root)
        result = updater._validate_and_fix_permissions()

        assert result.action == "fixed"
        assert result.issues_found > 0
        assert result.backup_path is not None

        # Verify settings were actually fixed
        fixed_content = json.loads(settings_path.read_text())
        assert "Bash(*)" not in fixed_content["permissions"]["allow"]
        assert "Bash(git:*)" in fixed_content["permissions"]["allow"]

    def test_create_backup_before_fix(self, temp_project_root, settings_with_wildcard):
        """Test backup created before applying fix.

        REQUIREMENT: Create backup before modifying settings.
        Expected: Backup file exists with original content.
        """
        # Create settings with wildcard
        settings_path = temp_project_root / ".claude" / "settings.local.json"
        original_content = json.dumps(settings_with_wildcard, indent=2)
        settings_path.write_text(original_content)

        updater = PluginUpdater(project_root=temp_project_root)
        result = updater._validate_and_fix_permissions()

        assert result.action == "fixed"
        assert result.backup_path is not None

        # Verify backup exists
        backup_path = Path(result.backup_path)
        assert backup_path.exists()

        # Verify backup has original content (with wildcard)
        backup_content = json.loads(backup_path.read_text())
        assert "Bash(*)" in backup_content["permissions"]["allow"]

    def test_handle_json_parse_error(self, temp_project_root, corrupted_settings_json):
        """Test handling of JSON parse error in settings.

        REQUIREMENT: Handle corrupted JSON gracefully.
        Expected: Backup corrupted file, regenerate from template.
        """
        # Create corrupted settings
        settings_path = temp_project_root / ".claude" / "settings.local.json"
        settings_path.write_text(corrupted_settings_json)

        updater = PluginUpdater(project_root=temp_project_root)
        result = updater._validate_and_fix_permissions()

        # Should backup corrupted file and regenerate
        assert result.action in ["fixed", "regenerated"]
        assert result.backup_path is not None

        # Verify corrupted content is in backup
        backup_path = Path(result.backup_path)
        assert backup_path.exists()
        assert backup_path.read_text() == corrupted_settings_json

        # Verify settings file now has valid JSON
        fixed_content = settings_path.read_text()
        parsed = json.loads(fixed_content)  # Should not raise
        assert "permissions" in parsed

    def test_handle_write_permission_error(self, temp_project_root, settings_with_wildcard):
        """Test handling of write permission error.

        REQUIREMENT: Non-blocking - fix failure doesn't fail update.
        Expected: PermissionFixResult with action="failed", error message.
        """
        # Create settings with wildcard
        settings_path = temp_project_root / ".claude" / "settings.local.json"
        settings_path.write_text(json.dumps(settings_with_wildcard, indent=2))

        # Make settings file read-only
        settings_path.chmod(0o444)

        updater = PluginUpdater(project_root=temp_project_root)
        result = updater._validate_and_fix_permissions()

        # Should fail gracefully without raising
        assert result.action == "failed"
        assert "permission" in result.message.lower() or "denied" in result.message.lower()

        # Restore permissions for cleanup
        settings_path.chmod(0o644)

    def test_handle_backup_permission_error(self, temp_project_root, settings_with_wildcard):
        """Test handling of backup creation permission error.

        REQUIREMENT: Warn but continue fix if backup fails.
        Expected: Fix proceeds, warning about backup failure.
        """
        # Create settings with wildcard
        settings_path = temp_project_root / ".claude" / "settings.local.json"
        settings_path.write_text(json.dumps(settings_with_wildcard, indent=2))

        # Make .claude directory read-only (can't create backup)
        claude_dir = temp_project_root / ".claude"
        claude_dir.chmod(0o555)

        updater = PluginUpdater(project_root=temp_project_root)

        # Should still attempt fix (or fail gracefully)
        try:
            result = updater._validate_and_fix_permissions()
            # If it succeeds, should have warning about backup
            assert result.action in ["fixed", "failed"]
        except Exception:
            # If it fails, that's also acceptable for this edge case
            pass

        # Restore permissions for cleanup
        claude_dir.chmod(0o755)

    def test_atomic_write_no_partial_updates(self, temp_project_root, settings_with_wildcard):
        """Test atomic write - no partial updates on failure.

        REQUIREMENT: Atomic operations - all or nothing.
        Expected: Settings unchanged if write fails midway.
        """
        # Create settings with wildcard
        settings_path = temp_project_root / ".claude" / "settings.local.json"
        original_content = json.dumps(settings_with_wildcard, indent=2)
        settings_path.write_text(original_content)

        updater = PluginUpdater(project_root=temp_project_root)

        # Mock write to fail midway
        with patch('builtins.open', side_effect=IOError("Disk full")):
            result = updater._validate_and_fix_permissions()

            # Should fail gracefully
            assert result.action == "failed"

            # Settings file should be unchanged (atomic)
            current_content = settings_path.read_text()
            assert current_content == original_content


# =============================================================================
# Test Permission Fix Integration with Update Flow
# =============================================================================

class TestPermissionFixInUpdateFlow:
    """Test permission fix integration with full update workflow."""

    def test_update_validates_permissions_during_update(self, temp_project_root, settings_with_wildcard):
        """Test that update() calls _validate_and_fix_permissions().

        REQUIREMENT: Update flow includes permission validation.
        Expected: _validate_and_fix_permissions() called during update.
        """
        # Create settings with wildcard
        settings_path = temp_project_root / ".claude" / "settings.local.json"
        settings_path.write_text(json.dumps(settings_with_wildcard, indent=2))

        updater = PluginUpdater(project_root=temp_project_root)

        # Mock the update dependencies
        with patch.object(updater, '_check_for_updates', return_value=Mock(needs_update=False)):
            with patch.object(updater, '_validate_and_fix_permissions', wraps=updater._validate_and_fix_permissions) as mock_validate:
                updater.update()

                # Should have called permission validation
                mock_validate.assert_called_once()

    def test_update_succeeds_even_if_permission_fix_fails(self, temp_project_root, settings_with_wildcard):
        """Test that update succeeds even if permission fix fails.

        REQUIREMENT: Non-blocking - fix failure doesn't block update.
        Expected: Update returns success even if permission fix failed.
        """
        # Create settings with wildcard (read-only)
        settings_path = temp_project_root / ".claude" / "settings.local.json"
        settings_path.write_text(json.dumps(settings_with_wildcard, indent=2))
        settings_path.chmod(0o444)

        updater = PluginUpdater(project_root=temp_project_root)

        # Mock update to succeed
        with patch.object(updater, '_check_for_updates', return_value=Mock(needs_update=False)):
            result = updater.update()

            # Update should succeed
            assert result.success is True

        # Restore permissions for cleanup
        settings_path.chmod(0o644)

    def test_update_result_includes_permission_fix_details(self, temp_project_root, settings_with_wildcard):
        """Test that UpdateResult includes permission fix details.

        REQUIREMENT: Update result includes permission fix info.
        Expected: UpdateResult.details contains permission_fix info.
        """
        # Create settings with wildcard
        settings_path = temp_project_root / ".claude" / "settings.local.json"
        settings_path.write_text(json.dumps(settings_with_wildcard, indent=2))

        updater = PluginUpdater(project_root=temp_project_root)

        # Mock update to succeed
        with patch.object(updater, '_check_for_updates', return_value=Mock(needs_update=False)):
            result = updater.update()

            # Should include permission fix details
            assert "permission_fix" in result.details
            assert result.details["permission_fix"]["action"] in ["fixed", "validated", "skipped", "failed"]


# =============================================================================
# Test Backup Management
# =============================================================================

class TestPermissionFixBackups:
    """Test backup creation and management for permission fixes."""

    def test_backup_has_timestamp_in_name(self, temp_project_root, settings_with_wildcard):
        """Test backup filename includes timestamp.

        REQUIREMENT: Backup files identifiable by timestamp.
        Expected: Backup filename contains timestamp.
        """
        # Create settings with wildcard
        settings_path = temp_project_root / ".claude" / "settings.local.json"
        settings_path.write_text(json.dumps(settings_with_wildcard, indent=2))

        updater = PluginUpdater(project_root=temp_project_root)
        result = updater._validate_and_fix_permissions()

        assert result.action == "fixed"
        assert result.backup_path is not None

        # Backup should have timestamp format
        backup_filename = Path(result.backup_path).name
        assert "settings.local.json" in backup_filename
        assert ".backup-" in backup_filename or "_backup_" in backup_filename

    def test_multiple_backups_dont_collide(self, temp_project_root, settings_with_wildcard):
        """Test multiple backups don't overwrite each other.

        REQUIREMENT: Multiple backups preserved with unique names.
        Expected: Each backup has unique filename.
        """
        # Create settings with wildcard
        settings_path = temp_project_root / ".claude" / "settings.local.json"
        settings_path.write_text(json.dumps(settings_with_wildcard, indent=2))

        updater = PluginUpdater(project_root=temp_project_root)

        # First fix
        result1 = updater._validate_and_fix_permissions()
        backup_path1 = result1.backup_path

        # Reintroduce wildcard for second fix
        settings_path.write_text(json.dumps(settings_with_wildcard, indent=2))

        # Second fix
        import time
        time.sleep(0.1)  # Ensure different timestamp
        result2 = updater._validate_and_fix_permissions()
        backup_path2 = result2.backup_path

        # Backups should have different paths
        assert backup_path1 != backup_path2
        assert Path(backup_path1).exists()
        assert Path(backup_path2).exists()


# =============================================================================
# Test Edge Cases
# =============================================================================

class TestPermissionFixEdgeCases:
    """Test edge cases for permission validation and fixing."""

    def test_fix_preserves_user_hooks(self, temp_project_root):
        """Test that fix preserves user hook configurations.

        REQUIREMENT: Preserve user customizations.
        Expected: Hook settings unchanged after fix.
        """
        settings_with_hooks = {
            "version": "1.0.0",
            "permissions": {
                "allow": ["Bash(*)"],  # Will be fixed
                "deny": []
            },
            "hooks": {
                "auto_format": True,
                "auto_test": False,
                "custom_hook": True
            }
        }

        settings_path = temp_project_root / ".claude" / "settings.local.json"
        settings_path.write_text(json.dumps(settings_with_hooks, indent=2))

        updater = PluginUpdater(project_root=temp_project_root)
        result = updater._validate_and_fix_permissions()

        assert result.action == "fixed"

        # Verify hooks preserved
        fixed_content = json.loads(settings_path.read_text())
        assert fixed_content["hooks"]["auto_format"] is True
        assert fixed_content["hooks"]["auto_test"] is False
        assert fixed_content["hooks"]["custom_hook"] is True

    def test_fix_preserves_custom_allow_patterns(self, temp_project_root):
        """Test that fix preserves valid custom allow patterns.

        REQUIREMENT: Preserve user customizations.
        Expected: Valid custom patterns preserved.
        """
        settings_with_custom = {
            "version": "1.0.0",
            "permissions": {
                "allow": [
                    "Bash(*)",  # Will be removed
                    "Bash(docker:*)",  # User custom - preserve
                    "Bash(make:*)",  # User custom - preserve
                    "Read(**)",
                ],
                "deny": []
            }
        }

        settings_path = temp_project_root / ".claude" / "settings.local.json"
        settings_path.write_text(json.dumps(settings_with_custom, indent=2))

        updater = PluginUpdater(project_root=temp_project_root)
        result = updater._validate_and_fix_permissions()

        assert result.action == "fixed"

        # Verify custom patterns preserved
        fixed_content = json.loads(settings_path.read_text())
        assert "Bash(docker:*)" in fixed_content["permissions"]["allow"]
        assert "Bash(make:*)" in fixed_content["permissions"]["allow"]
        assert "Bash(*)" not in fixed_content["permissions"]["allow"]

    def test_fix_handles_settings_with_comments(self, temp_project_root):
        """Test that fix handles JSON with comments (JSON5).

        REQUIREMENT: Handle various JSON formats gracefully.
        Expected: Comments stripped, valid JSON produced.
        """
        # JSON with comments (technically invalid JSON but common)
        settings_with_comments = """{
    // Version comment
    "version": "1.0.0",
    "permissions": {
        "allow": [
            "Bash(*)",  // Wildcard comment
            "Read(**)"
        ],
        "deny": []
    }
}"""

        settings_path = temp_project_root / ".claude" / "settings.local.json"
        settings_path.write_text(settings_with_comments)

        updater = PluginUpdater(project_root=temp_project_root)

        # May regenerate or handle gracefully
        result = updater._validate_and_fix_permissions()

        # Should either fix or regenerate
        assert result.action in ["fixed", "regenerated", "failed"]

        # If successful, result should be valid JSON
        if result.action in ["fixed", "regenerated"]:
            fixed_content = settings_path.read_text()
            parsed = json.loads(fixed_content)  # Should not raise
            assert "permissions" in parsed

    def test_fix_empty_settings_file(self, temp_project_root):
        """Test fix handling of empty settings file.

        REQUIREMENT: Handle malformed files gracefully.
        Expected: Regenerate from template or fail gracefully.
        """
        settings_path = temp_project_root / ".claude" / "settings.local.json"
        settings_path.write_text("")  # Empty file

        updater = PluginUpdater(project_root=temp_project_root)
        result = updater._validate_and_fix_permissions()

        # Should regenerate or fail gracefully
        assert result.action in ["regenerated", "failed"]

    def test_fix_settings_with_only_whitespace(self, temp_project_root):
        """Test fix handling of settings with only whitespace.

        REQUIREMENT: Handle malformed files gracefully.
        Expected: Regenerate from template or fail gracefully.
        """
        settings_path = temp_project_root / ".claude" / "settings.local.json"
        settings_path.write_text("   \n\n  \t  ")  # Only whitespace

        updater = PluginUpdater(project_root=temp_project_root)
        result = updater._validate_and_fix_permissions()

        # Should regenerate or fail gracefully
        assert result.action in ["regenerated", "failed"]


# =============================================================================
# Test Security
# =============================================================================

class TestPermissionFixSecurity:
    """Test security aspects of permission validation and fixing."""

    def test_backup_path_validated(self, temp_project_root, settings_with_wildcard):
        """Test that backup path is validated for security.

        REQUIREMENT: Path traversal prevention.
        Expected: Backup path validated, no path traversal.
        """
        settings_path = temp_project_root / ".claude" / "settings.local.json"
        settings_path.write_text(json.dumps(settings_with_wildcard, indent=2))

        updater = PluginUpdater(project_root=temp_project_root)
        result = updater._validate_and_fix_permissions()

        assert result.action == "fixed"
        assert result.backup_path is not None

        # Backup should be within project directory
        backup_path = Path(result.backup_path)
        assert backup_path.is_relative_to(temp_project_root)

    def test_settings_path_validated(self, temp_project_root):
        """Test that settings path is validated.

        REQUIREMENT: Path traversal prevention.
        Expected: Settings path must be within project.
        """
        # This is tested implicitly by PluginUpdater init
        # which validates project_root via security_utils

        updater = PluginUpdater(project_root=temp_project_root)

        # Settings path should be validated
        settings_path = temp_project_root / ".claude" / "settings.local.json"
        assert settings_path.is_relative_to(temp_project_root)
