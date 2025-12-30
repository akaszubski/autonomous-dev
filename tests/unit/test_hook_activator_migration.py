#!/usr/bin/env python3
"""
TDD Tests for Hook Activator Migration (FAILING - Red Phase)

This module contains FAILING tests for Claude Code 2.0 hook format migration
functionality in hook_activator.py. These tests will fail until migration
implementation is complete.

Security Requirements (from GitHub issue #112):
1. Format Detection: Identify legacy hooks missing timeout, nested structure
2. Format Migration: Transform legacy → CC2 format with timeout, nested hooks
3. Backup Creation: Timestamped backup before migration
4. Atomic Operations: Safe write/rollback on failure
5. Idempotent Migration: Running twice produces same result
6. Preservation: Keep user customizations during migration

Test Coverage Target: 100% of migration code paths (28+ tests)

Following TDD principles:
- Write tests FIRST (red phase)
- Tests describe migration requirements
- Tests should FAIL until migration logic is implemented
- Each test validates ONE requirement

Author: test-master agent
Date: 2025-12-12
Issue: #112
"""

import json
import os
import sys
import tempfile
from datetime import datetime
from pathlib import Path
from unittest.mock import Mock, patch, mock_open

import pytest

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

# This import should work (file exists) but migration functions don't exist yet
from plugins.autonomous_dev.lib.hook_activator import (
    HookActivator,
    ActivationError,
    SettingsValidationError,
)

# These imports will FAIL until migration functions are added
try:
    from plugins.autonomous_dev.lib.hook_activator import (
        validate_hook_format,
        migrate_hook_format_cc2,
        _backup_settings,
    )
    MIGRATION_FUNCTIONS_EXIST = True
except ImportError:
    MIGRATION_FUNCTIONS_EXIST = False
    # Define placeholder functions for tests
    def validate_hook_format(settings_data):
        raise NotImplementedError("validate_hook_format not implemented")

    def migrate_hook_format_cc2(settings_data):
        raise NotImplementedError("migrate_hook_format_cc2 not implemented")

    def _backup_settings(settings_path):
        raise NotImplementedError("_backup_settings not implemented")


# ============================================================================
# Format Detection Tests (8 tests)
# ============================================================================


class TestFormatDetection:
    """Test detection of legacy vs modern hook formats.

    Legacy format indicators:
    - Missing 'timeout' field in hook definitions
    - Flat structure (direct command strings)
    - Missing nested 'hooks' array within matchers

    Modern CC2 format:
    - Every hook has 'timeout' field
    - Nested structure with matchers containing hooks arrays
    - Each hook is a dict with 'type', 'command', 'timeout'
    """

    def test_detect_legacy_missing_timeout(self):
        """Test detection of legacy format missing timeout field.

        REQUIREMENT: Detect hooks without timeout field as legacy.
        Expected: validate_hook_format() returns {'is_legacy': True, 'reason': 'missing_timeout'}
        """
        legacy_settings = {
            "hooks": {
                "PreToolUse": [
                    {
                        "matcher": "*",
                        "hooks": [
                            {
                                "type": "command",
                                "command": "python .claude/hooks/pre_tool_use.py"
                                # Missing timeout field!
                            }
                        ]
                    }
                ]
            }
        }

        result = validate_hook_format(legacy_settings)

        assert result['is_legacy'] is True
        assert 'missing_timeout' in result['reason'].lower() or 'timeout' in result['reason'].lower()

    def test_detect_legacy_flat_structure(self):
        """Test detection of legacy flat structure (strings instead of dicts).

        REQUIREMENT: Detect flat hook structure as legacy.
        Expected: validate_hook_format() returns {'is_legacy': True, 'reason': 'flat_structure'}
        """
        legacy_settings = {
            "hooks": {
                "PrePush": ["auto_test.py"],  # Flat structure - just strings!
                "SubagentStop": ["log_agent_completion.py"]
            }
        }

        result = validate_hook_format(legacy_settings)

        assert result['is_legacy'] is True
        assert 'flat' in result['reason'].lower() or 'structure' in result['reason'].lower()

    def test_detect_legacy_missing_nested_hooks_array(self):
        """Test detection of legacy format missing nested hooks array.

        REQUIREMENT: Detect missing nested hooks array as legacy.
        Expected: validate_hook_format() returns {'is_legacy': True, 'reason': 'missing_nested_hooks'}
        """
        legacy_settings = {
            "hooks": {
                "PreToolUse": [
                    {
                        "matcher": "*",
                        "type": "command",
                        "command": "python .claude/hooks/pre_tool_use.py"
                        # Missing nested 'hooks' array!
                    }
                ]
            }
        }

        result = validate_hook_format(legacy_settings)

        assert result['is_legacy'] is True
        assert 'nested' in result['reason'].lower() or 'hooks' in result['reason'].lower()

    def test_detect_modern_format_no_false_positives(self):
        """Test that modern CC2 format is NOT flagged as legacy.

        REQUIREMENT: Modern format detection must not have false positives.
        Expected: validate_hook_format() returns {'is_legacy': False}
        """
        modern_settings = {
            "hooks": {
                "PreToolUse": [
                    {
                        "matcher": "*",
                        "hooks": [
                            {
                                "type": "command",
                                "command": "python .claude/hooks/pre_tool_use.py",
                                "timeout": 5
                            }
                        ]
                    }
                ]
            }
        }

        result = validate_hook_format(modern_settings)

        assert result['is_legacy'] is False

    def test_detect_mixed_format(self):
        """Test detection when some hooks are legacy, some are modern.

        REQUIREMENT: Mixed format should be flagged as legacy (requires migration).
        Expected: validate_hook_format() returns {'is_legacy': True, 'reason': 'mixed_format'}
        """
        mixed_settings = {
            "hooks": {
                "PreToolUse": [
                    {
                        "matcher": "*",
                        "hooks": [
                            {
                                "type": "command",
                                "command": "python .claude/hooks/pre_tool_use.py",
                                "timeout": 5  # Modern
                            }
                        ]
                    }
                ],
                "PrePush": ["auto_test.py"]  # Legacy flat structure
            }
        }

        result = validate_hook_format(mixed_settings)

        assert result['is_legacy'] is True

    def test_detect_empty_hooks(self):
        """Test detection of empty hooks object.

        REQUIREMENT: Empty hooks should be valid modern format (nothing to migrate).
        Expected: validate_hook_format() returns {'is_legacy': False}
        """
        empty_settings = {
            "hooks": {}
        }

        result = validate_hook_format(empty_settings)

        assert result['is_legacy'] is False

    def test_detect_malformed_json(self):
        """Test detection handles malformed settings gracefully.

        REQUIREMENT: Malformed settings should raise SettingsValidationError.
        Expected: SettingsValidationError raised with clear message.
        """
        malformed_settings = {
            "hooks": "not a dict"  # Should be a dict!
        }

        with pytest.raises(SettingsValidationError) as exc_info:
            validate_hook_format(malformed_settings)

        assert "invalid" in str(exc_info.value).lower() or "malformed" in str(exc_info.value).lower()

    def test_detect_missing_hooks_key(self):
        """Test detection when 'hooks' key is missing entirely.

        REQUIREMENT: Missing hooks key should be treated as empty (modern format).
        Expected: validate_hook_format() returns {'is_legacy': False}
        """
        no_hooks_settings = {
            "other_config": "value"
        }

        result = validate_hook_format(no_hooks_settings)

        assert result['is_legacy'] is False


# ============================================================================
# Migration Tests (10 tests)
# ============================================================================


class TestFormatMigration:
    """Test migration from legacy format to Claude Code 2.0 format.

    Migration transformations:
    1. Add 'timeout': 5 to all hooks missing it
    2. Convert flat strings to nested dict structure
    3. Wrap commands in nested 'hooks' array
    4. Add 'matcher': '*' if missing
    5. Preserve user customizations (custom timeouts, matchers)
    """

    def test_migrate_adds_timeout(self):
        """Test that migration adds timeout field to hooks missing it.

        REQUIREMENT: All migrated hooks must have timeout field.
        Expected: migrate_hook_format_cc2() adds 'timeout': 5 to all hooks.
        """
        legacy_settings = {
            "hooks": {
                "PreToolUse": [
                    {
                        "matcher": "*",
                        "hooks": [
                            {
                                "type": "command",
                                "command": "python .claude/hooks/pre_tool_use.py"
                                # Missing timeout!
                            }
                        ]
                    }
                ]
            }
        }

        migrated = migrate_hook_format_cc2(legacy_settings)

        hook = migrated['hooks']['PreToolUse'][0]['hooks'][0]
        assert 'timeout' in hook
        assert hook['timeout'] == 5  # Default timeout

    def test_migrate_nests_hooks_array(self):
        """Test that migration creates nested hooks array structure.

        REQUIREMENT: Modern format requires nested hooks array within matchers.
        Expected: migrate_hook_format_cc2() wraps hooks in nested array.
        """
        legacy_settings = {
            "hooks": {
                "PreToolUse": [
                    {
                        "matcher": "*",
                        "type": "command",
                        "command": "python .claude/hooks/pre_tool_use.py"
                        # Missing nested hooks array!
                    }
                ]
            }
        }

        migrated = migrate_hook_format_cc2(legacy_settings)

        matcher_config = migrated['hooks']['PreToolUse'][0]
        assert 'hooks' in matcher_config
        assert isinstance(matcher_config['hooks'], list)
        assert len(matcher_config['hooks']) > 0

    def test_migrate_preserves_customizations(self):
        """Test that migration preserves user customizations.

        REQUIREMENT: Don't overwrite user's custom timeout values.
        Expected: migrate_hook_format_cc2() preserves custom timeout if present.
        """
        legacy_settings = {
            "hooks": {
                "PreToolUse": [
                    {
                        "matcher": "*",
                        "hooks": [
                            {
                                "type": "command",
                                "command": "python .claude/hooks/pre_tool_use.py",
                                "timeout": 10  # Custom timeout - preserve this!
                            }
                        ]
                    }
                ]
            }
        }

        migrated = migrate_hook_format_cc2(legacy_settings)

        hook = migrated['hooks']['PreToolUse'][0]['hooks'][0]
        assert hook['timeout'] == 10  # Custom timeout preserved

    def test_migrate_preserves_matcher(self):
        """Test that migration preserves custom matcher patterns.

        REQUIREMENT: Don't overwrite user's custom matchers.
        Expected: migrate_hook_format_cc2() preserves custom matcher.
        """
        legacy_settings = {
            "hooks": {
                "PreToolUse": [
                    {
                        "matcher": "*.py",  # Custom matcher - preserve this!
                        "hooks": [
                            {
                                "type": "command",
                                "command": "python .claude/hooks/pre_tool_use.py"
                            }
                        ]
                    }
                ]
            }
        }

        migrated = migrate_hook_format_cc2(legacy_settings)

        matcher_config = migrated['hooks']['PreToolUse'][0]
        assert matcher_config['matcher'] == "*.py"  # Custom matcher preserved

    def test_migrate_converts_string_commands(self):
        """Test that migration converts flat string commands to dict structure.

        REQUIREMENT: Flat strings must become proper hook dicts.
        Expected: migrate_hook_format_cc2() converts strings to dicts with type, command, timeout.
        """
        legacy_settings = {
            "hooks": {
                "PrePush": ["auto_test.py"]  # Flat string - convert this!
            }
        }

        migrated = migrate_hook_format_cc2(legacy_settings)

        matcher_config = migrated['hooks']['PrePush'][0]
        assert 'matcher' in matcher_config
        assert 'hooks' in matcher_config

        hook = matcher_config['hooks'][0]
        assert hook['type'] == 'command'
        assert 'auto_test.py' in hook['command']
        assert hook['timeout'] == 5

    def test_migrate_handles_edge_cases(self):
        """Test that migration handles edge cases gracefully.

        REQUIREMENT: Handle empty lifecycle events, missing fields gracefully.
        Expected: migrate_hook_format_cc2() handles edge cases without error.
        """
        edge_case_settings = {
            "hooks": {
                "PrePush": [],  # Empty lifecycle event
                "PreToolUse": [
                    {
                        # Missing matcher, command, everything!
                    }
                ]
            }
        }

        # Should not raise exception
        migrated = migrate_hook_format_cc2(edge_case_settings)

        assert 'hooks' in migrated
        assert isinstance(migrated['hooks'], dict)

    def test_migrate_idempotent(self):
        """Test that migration is idempotent (running twice produces same result).

        REQUIREMENT: Running migration on already-migrated settings should be safe.
        Expected: migrate_hook_format_cc2() on migrated settings returns same result.
        """
        modern_settings = {
            "hooks": {
                "PreToolUse": [
                    {
                        "matcher": "*",
                        "hooks": [
                            {
                                "type": "command",
                                "command": "python .claude/hooks/pre_tool_use.py",
                                "timeout": 5
                            }
                        ]
                    }
                ]
            }
        }

        # Migrate once
        first_migration = migrate_hook_format_cc2(modern_settings)

        # Migrate again
        second_migration = migrate_hook_format_cc2(first_migration)

        # Should be identical
        assert first_migration == second_migration

    def test_migrate_preserves_other_lifecycle_hooks(self):
        """Test that migration preserves non-hook lifecycle events.

        REQUIREMENT: Don't touch other lifecycle events during migration.
        Expected: migrate_hook_format_cc2() preserves PrePush, SubagentStop, etc.
        """
        legacy_settings = {
            "hooks": {
                "PreToolUse": [
                    {
                        "matcher": "*",
                        "hooks": [
                            {
                                "type": "command",
                                "command": "python .claude/hooks/pre_tool_use.py"
                            }
                        ]
                    }
                ],
                "PrePush": ["auto_test.py"],  # Legacy format
                "SubagentStop": ["log_completion.py"]  # Legacy format
            }
        }

        migrated = migrate_hook_format_cc2(legacy_settings)

        # All lifecycle events should be present
        assert 'PreToolUse' in migrated['hooks']
        assert 'PrePush' in migrated['hooks']
        assert 'SubagentStop' in migrated['hooks']

        # All should be in modern format
        for lifecycle in ['PreToolUse', 'PrePush', 'SubagentStop']:
            matcher_config = migrated['hooks'][lifecycle][0]
            assert 'matcher' in matcher_config
            assert 'hooks' in matcher_config
            hook = matcher_config['hooks'][0]
            assert 'timeout' in hook

    def test_migrate_handles_multiple_matchers(self):
        """Test that migration handles multiple matchers in same lifecycle event.

        REQUIREMENT: Support multiple matchers per lifecycle event.
        Expected: migrate_hook_format_cc2() migrates all matchers independently.
        """
        legacy_settings = {
            "hooks": {
                "PreToolUse": [
                    {
                        "matcher": "*.py",
                        "hooks": [
                            {
                                "type": "command",
                                "command": "python hook1.py"
                            }
                        ]
                    },
                    {
                        "matcher": "*.js",
                        "hooks": [
                            {
                                "type": "command",
                                "command": "node hook2.js"
                            }
                        ]
                    }
                ]
            }
        }

        migrated = migrate_hook_format_cc2(legacy_settings)

        matchers = migrated['hooks']['PreToolUse']
        assert len(matchers) == 2

        # Both matchers should have timeout
        for matcher_config in matchers:
            hook = matcher_config['hooks'][0]
            assert 'timeout' in hook

    def test_migrate_preserves_other_settings_keys(self):
        """Test that migration preserves other settings keys (not just hooks).

        REQUIREMENT: Don't delete other settings during migration.
        Expected: migrate_hook_format_cc2() preserves all non-hook settings.
        """
        legacy_settings = {
            "hooks": {
                "PreToolUse": [
                    {
                        "matcher": "*",
                        "hooks": [
                            {
                                "type": "command",
                                "command": "python .claude/hooks/pre_tool_use.py"
                            }
                        ]
                    }
                ]
            },
            "editor": {
                "theme": "dark"
            },
            "other_config": "value"
        }

        migrated = migrate_hook_format_cc2(legacy_settings)

        # Other settings should be preserved
        assert 'editor' in migrated
        assert migrated['editor']['theme'] == "dark"
        assert migrated['other_config'] == "value"


# ============================================================================
# Backup Tests (5 tests)
# ============================================================================


class TestBackupCreation:
    """Test settings backup before migration.

    Backup requirements:
    - Timestamped filename (settings.json.backup.YYYYMMDD_HHMMSS)
    - Atomic write (tempfile + rename)
    - Secure permissions (0o600)
    - Path validation (security_utils)
    - Enable rollback if migration fails
    """

    @pytest.fixture
    def temp_settings_dir(self, tmp_path):
        """Create temporary directory with settings.json file."""
        claude_dir = tmp_path / ".claude"
        claude_dir.mkdir()

        settings_file = claude_dir / "settings.json"
        settings_data = {
            "hooks": {
                "PrePush": ["auto_test.py"]
            }
        }
        settings_file.write_text(json.dumps(settings_data, indent=2))

        return tmp_path, settings_file

    def test_backup_creates_timestamped_file(self, temp_settings_dir):
        """Test that backup creates timestamped backup file.

        REQUIREMENT: Backup filename must include timestamp for tracking.
        Expected: _backup_settings() creates settings.json.backup.YYYYMMDD_HHMMSS
        """
        project_root, settings_file = temp_settings_dir

        # Create backup
        backup_path = _backup_settings(settings_file)

        # Verify backup exists
        assert backup_path.exists()

        # Verify filename format
        assert backup_path.name.startswith("settings.json.backup.")

        # Verify timestamp format (YYYYMMDD_HHMMSS)
        timestamp = backup_path.name.split(".")[-1]
        # Should be able to parse as datetime
        datetime.strptime(timestamp, "%Y%m%d_%H%M%S")

    def test_backup_atomic_write(self, temp_settings_dir):
        """Test that backup uses atomic write (tempfile + rename).

        REQUIREMENT: Backup write must be atomic to prevent corruption.
        Expected: _backup_settings() uses tempfile.mkstemp + os.rename
        """
        project_root, settings_file = temp_settings_dir

        # Mock tempfile.mkstemp to verify atomic write
        with patch('tempfile.mkstemp') as mock_mkstemp:
            mock_fd = 123
            mock_temp_path = str(settings_file.parent / ".settings.backup.tmp")
            mock_mkstemp.return_value = (mock_fd, mock_temp_path)

            with patch('os.write') as mock_write:
                with patch('os.close') as mock_close:
                    with patch('os.rename') as mock_rename:
                        # Create backup
                        _backup_settings(settings_file)

                        # Verify atomic write pattern
                        mock_mkstemp.assert_called_once()
                        mock_write.assert_called_once()
                        mock_close.assert_called_once_with(mock_fd)
                        mock_rename.assert_called_once()

    def test_backup_permission_validation(self, temp_settings_dir):
        """Test that backup validates path permissions via security_utils.

        REQUIREMENT: All file operations must go through security_utils.
        Expected: _backup_settings() calls security_utils.validate_path()
        """
        project_root, settings_file = temp_settings_dir

        # Mock security validation
        with patch('plugins.autonomous_dev.lib.hook_activator.security_utils.validate_path') as mock_validate:
            mock_validate.return_value = str(settings_file)

            # Create backup
            _backup_settings(settings_file)

            # Verify validation was called
            mock_validate.assert_called()

    def test_backup_rollback_possible(self, temp_settings_dir):
        """Test that backup enables rollback after failed migration.

        REQUIREMENT: Backup must be restorable if migration fails.
        Expected: Backup file contains exact copy of original settings.
        """
        project_root, settings_file = temp_settings_dir

        # Read original settings
        original_content = settings_file.read_text()

        # Create backup
        backup_path = _backup_settings(settings_file)

        # Verify backup content matches original
        backup_content = backup_path.read_text()
        assert backup_content == original_content

        # Verify backup can be restored (JSON is valid)
        backup_data = json.loads(backup_content)
        assert 'hooks' in backup_data

    def test_backup_secure_permissions(self, temp_settings_dir):
        """Test that backup file has secure permissions (0o600).

        REQUIREMENT: Backup files must be user-only readable/writable.
        Expected: _backup_settings() sets permissions to 0o600.
        """
        project_root, settings_file = temp_settings_dir

        # Create backup
        backup_path = _backup_settings(settings_file)

        # Verify permissions (user-only read/write)
        stat_info = backup_path.stat()
        permissions = stat_info.st_mode & 0o777
        assert permissions == 0o600


# ============================================================================
# Integration Tests (5 tests)
# ============================================================================


class TestMigrationIntegration:
    """Integration tests for complete migration workflow.

    End-to-end tests covering:
    1. Fresh install (no migration needed)
    2. Upgrade install (migration required)
    3. Failed migration (rollback)
    4. Multiple lifecycle events
    5. Real-world legacy formats
    """

    @pytest.fixture
    def temp_project_dir(self, tmp_path):
        """Create temporary project directory."""
        project_root = tmp_path / "project"
        project_root.mkdir()

        claude_dir = project_root / ".claude"
        claude_dir.mkdir()

        return project_root, claude_dir

    def test_migration_in_fresh_install(self, temp_project_dir):
        """Test that fresh install doesn't trigger migration.

        REQUIREMENT: Fresh install should skip migration (no existing settings).
        Expected: activate_hooks() installs modern format, no backup created.
        """
        project_root, claude_dir = temp_project_dir
        settings_file = claude_dir / "settings.json"

        # Fresh install - no settings.json exists
        assert not settings_file.exists()

        activator = HookActivator(project_root)

        new_hooks = {
            "hooks": {
                "PreToolUse": [
                    {
                        "matcher": "*",
                        "hooks": [
                            {
                                "type": "command",
                                "command": "python .claude/hooks/pre_tool_use.py",
                                "timeout": 5
                            }
                        ]
                    }
                ]
            }
        }

        result = activator.activate_hooks(new_hooks)

        # Verify settings created in modern format
        assert settings_file.exists()
        settings_data = json.loads(settings_file.read_text())

        # Verify modern format (has timeout)
        hook = settings_data['hooks']['PreToolUse'][0]['hooks'][0]
        assert 'timeout' in hook

        # Verify no backup created (fresh install)
        backup_files = list(claude_dir.glob("settings.json.backup.*"))
        assert len(backup_files) == 0

    def test_migration_in_upgrade_install(self, temp_project_dir):
        """Test that upgrade install triggers migration.

        REQUIREMENT: Upgrade install should detect legacy format and migrate.
        Expected: activate_hooks() detects legacy, creates backup, migrates to CC2.
        """
        project_root, claude_dir = temp_project_dir
        settings_file = claude_dir / "settings.json"

        # Create legacy settings
        legacy_settings = {
            "hooks": {
                "PrePush": ["auto_test.py"]  # Legacy flat format
            }
        }
        settings_file.write_text(json.dumps(legacy_settings, indent=2))

        activator = HookActivator(project_root)

        new_hooks = {
            "hooks": {
                "PreToolUse": [
                    {
                        "matcher": "*",
                        "hooks": [
                            {
                                "type": "command",
                                "command": "python .claude/hooks/pre_tool_use.py",
                                "timeout": 5
                            }
                        ]
                    }
                ]
            }
        }

        result = activator.activate_hooks(new_hooks)

        # Verify backup created
        backup_files = list(claude_dir.glob("settings.json.backup.*"))
        assert len(backup_files) > 0

        # Verify settings migrated to modern format
        settings_data = json.loads(settings_file.read_text())

        # PrePush should be migrated
        prepush_hook = settings_data['hooks']['PrePush'][0]['hooks'][0]
        assert 'timeout' in prepush_hook

        # New PreToolUse should be added
        assert 'PreToolUse' in settings_data['hooks']

    def test_full_workflow_legacy_to_cc2(self, temp_project_dir):
        """Test complete workflow from legacy format to CC2 format.

        REQUIREMENT: End-to-end migration workflow must be seamless.
        Expected: Legacy → Detect → Backup → Migrate → Validate → Success.
        """
        project_root, claude_dir = temp_project_dir
        settings_file = claude_dir / "settings.json"

        # Create complex legacy settings
        legacy_settings = {
            "hooks": {
                "PrePush": ["auto_test.py", "auto_format.py"],
                "PreToolUse": [
                    {
                        "matcher": "*",
                        "hooks": [
                            {
                                "type": "command",
                                "command": "python hook.py"
                                # Missing timeout!
                            }
                        ]
                    }
                ],
                "SubagentStop": ["log_completion.py"]
            },
            "editor": {
                "theme": "dark"
            }
        }
        settings_file.write_text(json.dumps(legacy_settings, indent=2))

        # Step 1: Detect legacy format
        is_legacy = validate_hook_format(legacy_settings)['is_legacy']
        assert is_legacy is True

        # Step 2: Create backup
        backup_path = _backup_settings(settings_file)
        assert backup_path.exists()

        # Step 3: Migrate to CC2
        migrated = migrate_hook_format_cc2(legacy_settings)

        # Step 4: Validate migrated format
        is_modern = validate_hook_format(migrated)['is_legacy']
        assert is_modern is False

        # Verify all hooks have timeout
        for lifecycle, matchers in migrated['hooks'].items():
            for matcher_config in matchers:
                for hook in matcher_config['hooks']:
                    assert 'timeout' in hook

        # Verify other settings preserved
        assert migrated['editor']['theme'] == "dark"

    def test_migration_preserves_multiple_lifecycle_hooks(self, temp_project_dir):
        """Test that migration handles multiple lifecycle events correctly.

        REQUIREMENT: Support all lifecycle events (PrePush, PreToolUse, SubagentStop, etc).
        Expected: All lifecycle events migrated independently.
        """
        project_root, claude_dir = temp_project_dir

        # Create settings with multiple lifecycle events
        legacy_settings = {
            "hooks": {
                "PrePush": ["auto_test.py"],
                "PreToolUse": ["security_check.py"],
                "SubagentStop": ["log_completion.py"],
                "UserPromptSubmit": ["display_context.py"]
            }
        }

        # Migrate
        migrated = migrate_hook_format_cc2(legacy_settings)

        # Verify all lifecycle events present
        expected_lifecycles = ["PrePush", "PreToolUse", "SubagentStop", "UserPromptSubmit"]
        for lifecycle in expected_lifecycles:
            assert lifecycle in migrated['hooks']

            # Verify modern format
            matcher_config = migrated['hooks'][lifecycle][0]
            assert 'matcher' in matcher_config
            assert 'hooks' in matcher_config

            hook = matcher_config['hooks'][0]
            assert 'timeout' in hook
            assert hook['timeout'] == 5

    def test_migration_handles_real_world_settings(self, temp_project_dir):
        """Test migration with real-world autonomous-dev settings.

        REQUIREMENT: Must handle actual autonomous-dev settings files.
        Expected: Real-world settings migrate successfully.
        """
        project_root, claude_dir = temp_project_dir
        settings_file = claude_dir / "settings.json"

        # Real-world legacy settings (from autonomous-dev)
        real_world_settings = {
            "hooks": {
                "PreToolUse": [
                    {
                        "matcher": "*",
                        "hooks": [
                            {
                                "type": "command",
                                "command": "python ${PROJECT_ROOT}/.claude/hooks/pre_tool_use.py"
                                # Missing timeout!
                            }
                        ]
                    }
                ],
                "PrePush": [
                    "python .claude/hooks/auto_test.py",
                    "python .claude/hooks/validate_project_alignment.py"
                ],
                "SubagentStop": [
                    "python .claude/hooks/log_agent_completion.py"
                ]
            }
        }
        settings_file.write_text(json.dumps(real_world_settings, indent=2))

        # Migrate
        migrated = migrate_hook_format_cc2(real_world_settings)

        # Verify PreToolUse migrated (timeout added)
        pretooluse_hook = migrated['hooks']['PreToolUse'][0]['hooks'][0]
        assert pretooluse_hook['timeout'] == 5

        # Verify PrePush migrated (flat → nested)
        prepush_matchers = migrated['hooks']['PrePush']
        assert len(prepush_matchers) == 2  # Two hooks
        for matcher_config in prepush_matchers:
            hook = matcher_config['hooks'][0]
            assert 'timeout' in hook
            assert 'type' in hook
            assert hook['type'] == 'command'

        # Verify SubagentStop migrated
        subagent_hook = migrated['hooks']['SubagentStop'][0]['hooks'][0]
        assert subagent_hook['timeout'] == 5


# ============================================================================
# Array to Object Migration Tests (Issue #135) - 42 tests
# ============================================================================


class TestArrayToObjectMigration:
    """Test migration from array-based hooks to object-based hooks (Issue #135).

    OLD array format (Claude Code <2.0.69):
    {
        "hooks": [
            {"event": "PreToolUse", "command": "python hook.py"}
        ]
    }

    NEW object format (Claude Code >=2.0.69):
    {
        "hooks": {
            "PreToolUse": [
                {
                    "matcher": "*",
                    "hooks": [
                        {"type": "command", "command": "python hook.py", "timeout": 5}
                    ]
                }
            ]
        }
    }

    Test coverage:
    - Fresh install path (3 tests)
    - Valid array format path (8 tests)
    - Already migrated path (3 tests)
    - Corrupted file path (5 tests)
    - Migration failure path (5 tests)
    - Edge cases (6 tests)
    - Integration with sync_marketplace (5 tests)
    - Backup and rollback (7 tests)

    Total: 42 tests for comprehensive coverage
    """

    @pytest.fixture
    def temp_settings_dir(self, tmp_path):
        """Create temporary .claude directory for testing."""
        claude_dir = tmp_path / ".claude"
        claude_dir.mkdir()
        return claude_dir

    # ========================================================================
    # Fresh Install Path (3 tests)
    # ========================================================================

    @pytest.mark.xfail(reason="migrate_hooks_to_object_format not implemented yet")
    def test_fresh_install_no_settings_file(self, temp_settings_dir):
        """Test migration skipped when settings.json doesn't exist.

        REQUIREMENT: Fresh install should skip migration gracefully.
        Expected: migrate_hooks_to_object_format() returns {'migrated': False}
        """
        from plugins.autonomous_dev.lib.hook_activator import migrate_hooks_to_object_format

        settings_path = temp_settings_dir / "settings.json"

        # Settings file doesn't exist
        assert not settings_path.exists()

        result = migrate_hooks_to_object_format(settings_path)

        assert result['migrated'] is False
        assert 'backup_path' not in result or result['backup_path'] is None
        assert result['format'] == 'missing'

    @pytest.mark.xfail(reason="migrate_hooks_to_object_format not implemented yet")
    def test_fresh_install_creates_object_format(self, temp_settings_dir):
        """Test that fresh install creates object format directly.

        REQUIREMENT: New installations should use object format from start.
        Expected: No migration needed for newly created settings.
        """
        from plugins.autonomous_dev.lib.hook_activator import migrate_hooks_to_object_format

        settings_path = temp_settings_dir / "settings.json"

        # Create fresh settings with object format
        fresh_settings = {
            "hooks": {
                "PreToolUse": [
                    {
                        "matcher": "*",
                        "hooks": [
                            {"type": "command", "command": "python hook.py", "timeout": 5}
                        ]
                    }
                ]
            }
        }
        settings_path.write_text(json.dumps(fresh_settings, indent=2))

        result = migrate_hooks_to_object_format(settings_path)

        assert result['migrated'] is False
        assert result['format'] == 'object'

    @pytest.mark.xfail(reason="migrate_hooks_to_object_format not implemented yet")
    def test_fresh_install_empty_hooks(self, temp_settings_dir):
        """Test fresh install with empty hooks object.

        REQUIREMENT: Empty hooks should be valid (no migration needed).
        Expected: migrate_hooks_to_object_format() returns {'migrated': False}
        """
        from plugins.autonomous_dev.lib.hook_activator import migrate_hooks_to_object_format

        settings_path = temp_settings_dir / "settings.json"

        # Create settings with empty hooks
        empty_settings = {"hooks": {}}
        settings_path.write_text(json.dumps(empty_settings, indent=2))

        result = migrate_hooks_to_object_format(settings_path)

        assert result['migrated'] is False
        assert result['format'] == 'object'

    # ========================================================================
    # Valid Array Format Path (8 tests)
    # ========================================================================

    @pytest.mark.xfail(reason="migrate_hooks_to_object_format not implemented yet")
    def test_simple_array_migration(self, temp_settings_dir):
        """Test migration of simple array format to object format.

        REQUIREMENT: Simple array format should convert to object format.
        Expected: Array converted to nested object structure with matcher and timeout.
        """
        from plugins.autonomous_dev.lib.hook_activator import migrate_hooks_to_object_format

        settings_path = temp_settings_dir / "settings.json"

        # Create array format settings
        array_settings = {
            "hooks": [
                {"event": "PreToolUse", "command": "python pre_tool_use.py"}
            ]
        }
        settings_path.write_text(json.dumps(array_settings, indent=2))

        result = migrate_hooks_to_object_format(settings_path)

        assert result['migrated'] is True
        assert result['format'] == 'array'
        assert 'backup_path' in result
        assert result['backup_path'].exists()

        # Verify migrated content
        migrated = json.loads(settings_path.read_text())
        assert isinstance(migrated['hooks'], dict)
        assert 'PreToolUse' in migrated['hooks']

        hook_config = migrated['hooks']['PreToolUse'][0]
        assert hook_config['matcher'] == '*'
        assert len(hook_config['hooks']) == 1

        hook = hook_config['hooks'][0]
        assert hook['type'] == 'command'
        assert 'pre_tool_use.py' in hook['command']
        assert hook['timeout'] == 5

    @pytest.mark.xfail(reason="migrate_hooks_to_object_format not implemented yet")
    def test_multiple_events_migration(self, temp_settings_dir):
        """Test migration with multiple lifecycle events.

        REQUIREMENT: Multiple events should be grouped correctly by event type.
        Expected: Each event type gets its own key in hooks object.
        """
        from plugins.autonomous_dev.lib.hook_activator import migrate_hooks_to_object_format

        settings_path = temp_settings_dir / "settings.json"

        array_settings = {
            "hooks": [
                {"event": "PreToolUse", "command": "python pre_tool.py"},
                {"event": "PostToolUse", "command": "python post_tool.py"},
                {"event": "SubagentStop", "command": "python subagent.py"}
            ]
        }
        settings_path.write_text(json.dumps(array_settings, indent=2))

        result = migrate_hooks_to_object_format(settings_path)

        assert result['migrated'] is True

        migrated = json.loads(settings_path.read_text())
        assert 'PreToolUse' in migrated['hooks']
        assert 'PostToolUse' in migrated['hooks']
        assert 'SubagentStop' in migrated['hooks']

    @pytest.mark.xfail(reason="migrate_hooks_to_object_format not implemented yet")
    def test_nested_matcher_fields_preserved(self, temp_settings_dir):
        """Test that nested matcher fields are preserved during migration.

        REQUIREMENT: Custom matcher patterns should be preserved.
        Expected: Glob, path, and other matcher fields maintained.
        """
        from plugins.autonomous_dev.lib.hook_activator import migrate_hooks_to_object_format

        settings_path = temp_settings_dir / "settings.json"

        array_settings = {
            "hooks": [
                {
                    "event": "PreToolUse",
                    "command": "python hook.py",
                    "matcher": "*.py",
                    "glob": "**/*.test.py"
                }
            ]
        }
        settings_path.write_text(json.dumps(array_settings, indent=2))

        result = migrate_hooks_to_object_format(settings_path)

        assert result['migrated'] is True

        migrated = json.loads(settings_path.read_text())
        hook_config = migrated['hooks']['PreToolUse'][0]

        # Matcher preserved
        assert hook_config['matcher'] == '*.py'
        # Additional fields preserved
        assert hook_config.get('glob') == '**/*.test.py'

    @pytest.mark.xfail(reason="migrate_hooks_to_object_format not implemented yet")
    def test_command_hooks_maintain_structure(self, temp_settings_dir):
        """Test that command hook structure is maintained.

        REQUIREMENT: Command hooks should preserve all fields (type, command, etc).
        Expected: type: "command", command: "...", timeout: 5 structure created.
        """
        from plugins.autonomous_dev.lib.hook_activator import migrate_hooks_to_object_format

        settings_path = temp_settings_dir / "settings.json"

        array_settings = {
            "hooks": [
                {
                    "event": "PreToolUse",
                    "command": "python /absolute/path/to/hook.py --arg1 --arg2"
                }
            ]
        }
        settings_path.write_text(json.dumps(array_settings, indent=2))

        result = migrate_hooks_to_object_format(settings_path)

        migrated = json.loads(settings_path.read_text())
        hook = migrated['hooks']['PreToolUse'][0]['hooks'][0]

        assert hook['type'] == 'command'
        assert hook['command'] == 'python /absolute/path/to/hook.py --arg1 --arg2'
        assert hook['timeout'] == 5

    @pytest.mark.xfail(reason="migrate_hooks_to_object_format not implemented yet")
    def test_backup_timestamp_format(self, temp_settings_dir):
        """Test that backup file has correct timestamp format.

        REQUIREMENT: Backup filename must include timestamp.
        Expected: settings.json.backup.YYYYMMDD_HHMMSS format.
        """
        from plugins.autonomous_dev.lib.hook_activator import migrate_hooks_to_object_format

        settings_path = temp_settings_dir / "settings.json"

        array_settings = {
            "hooks": [
                {"event": "PreToolUse", "command": "python hook.py"}
            ]
        }
        settings_path.write_text(json.dumps(array_settings, indent=2))

        result = migrate_hooks_to_object_format(settings_path)

        backup_path = result['backup_path']
        assert backup_path.name.startswith("settings.json.backup.")

        # Extract timestamp
        timestamp_str = backup_path.name.split(".")[-1]

        # Verify format (should parse without error)
        datetime.strptime(timestamp_str, "%Y%m%d_%H%M%S")

    @pytest.mark.xfail(reason="migrate_hooks_to_object_format not implemented yet")
    def test_multiple_hooks_same_event(self, temp_settings_dir):
        """Test migration with multiple hooks for same event.

        REQUIREMENT: Multiple hooks for same event should be grouped.
        Expected: All hooks for event grouped in single array.
        """
        from plugins.autonomous_dev.lib.hook_activator import migrate_hooks_to_object_format

        settings_path = temp_settings_dir / "settings.json"

        array_settings = {
            "hooks": [
                {"event": "PreToolUse", "command": "python hook1.py"},
                {"event": "PreToolUse", "command": "python hook2.py"}
            ]
        }
        settings_path.write_text(json.dumps(array_settings, indent=2))

        result = migrate_hooks_to_object_format(settings_path)

        migrated = json.loads(settings_path.read_text())

        # Both hooks should be in PreToolUse array
        assert len(migrated['hooks']['PreToolUse']) == 2

    @pytest.mark.xfail(reason="migrate_hooks_to_object_format not implemented yet")
    def test_unicode_in_commands_preserved(self, temp_settings_dir):
        """Test that Unicode characters in hook commands are preserved.

        REQUIREMENT: Unicode should be preserved during migration.
        Expected: Unicode characters maintained correctly.
        """
        from plugins.autonomous_dev.lib.hook_activator import migrate_hooks_to_object_format

        settings_path = temp_settings_dir / "settings.json"

        array_settings = {
            "hooks": [
                {"event": "PreToolUse", "command": "python hook.py --msg='测试 🚀'"}
            ]
        }
        settings_path.write_text(json.dumps(array_settings, indent=2, ensure_ascii=False))

        result = migrate_hooks_to_object_format(settings_path)

        migrated = json.loads(settings_path.read_text())
        hook = migrated['hooks']['PreToolUse'][0]['hooks'][0]

        assert "测试 🚀" in hook['command']

    @pytest.mark.xfail(reason="migrate_hooks_to_object_format not implemented yet")
    def test_large_hooks_array_migration(self, temp_settings_dir):
        """Test migration with very large hooks array (100+ entries).

        REQUIREMENT: Migration should handle large arrays efficiently.
        Expected: All 100 hooks migrated successfully.
        """
        from plugins.autonomous_dev.lib.hook_activator import migrate_hooks_to_object_format

        settings_path = temp_settings_dir / "settings.json"

        # Create 100 hooks
        array_settings = {
            "hooks": [
                {"event": "PreToolUse", "command": f"python hook{i}.py"}
                for i in range(100)
            ]
        }
        settings_path.write_text(json.dumps(array_settings, indent=2))

        result = migrate_hooks_to_object_format(settings_path)

        migrated = json.loads(settings_path.read_text())

        # All 100 hooks should be migrated
        assert len(migrated['hooks']['PreToolUse']) == 100

    # ========================================================================
    # Already Migrated Path (3 tests)
    # ========================================================================

    @pytest.mark.xfail(reason="migrate_hooks_to_object_format not implemented yet")
    def test_object_format_detected_no_migration(self, temp_settings_dir):
        """Test that object format is detected and no migration occurs.

        REQUIREMENT: Already-migrated settings should be left untouched.
        Expected: migrate_hooks_to_object_format() returns {'migrated': False}
        """
        from plugins.autonomous_dev.lib.hook_activator import migrate_hooks_to_object_format

        settings_path = temp_settings_dir / "settings.json"

        object_settings = {
            "hooks": {
                "PreToolUse": [
                    {
                        "matcher": "*",
                        "hooks": [
                            {"type": "command", "command": "python hook.py", "timeout": 5}
                        ]
                    }
                ]
            }
        }
        settings_path.write_text(json.dumps(object_settings, indent=2))

        result = migrate_hooks_to_object_format(settings_path)

        assert result['migrated'] is False
        assert result['format'] == 'object'

    @pytest.mark.xfail(reason="migrate_hooks_to_object_format not implemented yet")
    def test_no_backup_when_already_migrated(self, temp_settings_dir):
        """Test that no backup is created for already-migrated settings.

        REQUIREMENT: Don't create unnecessary backups.
        Expected: No backup file created when format is already object.
        """
        from plugins.autonomous_dev.lib.hook_activator import migrate_hooks_to_object_format

        settings_path = temp_settings_dir / "settings.json"

        object_settings = {
            "hooks": {
                "PreToolUse": [
                    {
                        "matcher": "*",
                        "hooks": [
                            {"type": "command", "command": "python hook.py", "timeout": 5}
                        ]
                    }
                ]
            }
        }
        settings_path.write_text(json.dumps(object_settings, indent=2))

        result = migrate_hooks_to_object_format(settings_path)

        # No backup should be created
        backup_files = list(temp_settings_dir.glob("settings.json.backup.*"))
        assert len(backup_files) == 0

    @pytest.mark.xfail(reason="migrate_hooks_to_object_format not implemented yet")
    def test_silent_success_already_migrated(self, temp_settings_dir):
        """Test silent success when settings already migrated.

        REQUIREMENT: No error messages when already in correct format.
        Expected: Result indicates success with no migration needed.
        """
        from plugins.autonomous_dev.lib.hook_activator import migrate_hooks_to_object_format

        settings_path = temp_settings_dir / "settings.json"

        object_settings = {
            "hooks": {
                "PreToolUse": [
                    {
                        "matcher": "*",
                        "hooks": [
                            {"type": "command", "command": "python hook.py", "timeout": 5}
                        ]
                    }
                ]
            }
        }
        settings_path.write_text(json.dumps(object_settings, indent=2))

        result = migrate_hooks_to_object_format(settings_path)

        assert 'error' not in result or result['error'] is None

    # ========================================================================
    # Corrupted File Path (5 tests)
    # ========================================================================

    @pytest.mark.xfail(reason="migrate_hooks_to_object_format not implemented yet")
    def test_malformed_json_creates_backup(self, temp_settings_dir):
        """Test that malformed JSON triggers backup and template replacement.

        REQUIREMENT: Corrupted settings should be backed up and replaced.
        Expected: Backup created, template settings written.
        """
        from plugins.autonomous_dev.lib.hook_activator import migrate_hooks_to_object_format

        settings_path = temp_settings_dir / "settings.json"

        # Write malformed JSON
        settings_path.write_text("{invalid json")

        result = migrate_hooks_to_object_format(settings_path)

        # Backup should be created
        assert 'backup_path' in result
        assert result['backup_path'].exists()

        # Settings should be replaced with template
        migrated = json.loads(settings_path.read_text())
        assert 'hooks' in migrated
        assert isinstance(migrated['hooks'], dict)

    @pytest.mark.xfail(reason="migrate_hooks_to_object_format not implemented yet")
    def test_missing_hooks_key_template_replacement(self, temp_settings_dir):
        """Test that missing hooks key triggers template replacement.

        REQUIREMENT: Missing hooks key should result in template settings.
        Expected: Template settings written with empty hooks object.
        """
        from plugins.autonomous_dev.lib.hook_activator import migrate_hooks_to_object_format

        settings_path = temp_settings_dir / "settings.json"

        # Settings without hooks key
        settings_path.write_text(json.dumps({"other": "config"}))

        result = migrate_hooks_to_object_format(settings_path)

        # Should add hooks key
        migrated = json.loads(settings_path.read_text())
        assert 'hooks' in migrated

    @pytest.mark.xfail(reason="migrate_hooks_to_object_format not implemented yet")
    def test_invalid_hook_structure_template_replacement(self, temp_settings_dir):
        """Test that invalid hook structure triggers template replacement.

        REQUIREMENT: Invalid hook structure should be replaced.
        Expected: Template settings with correct structure.
        """
        from plugins.autonomous_dev.lib.hook_activator import migrate_hooks_to_object_format

        settings_path = temp_settings_dir / "settings.json"

        # Invalid hook structure (hooks is string instead of array/object)
        settings_path.write_text(json.dumps({"hooks": "invalid"}))

        result = migrate_hooks_to_object_format(settings_path)

        migrated = json.loads(settings_path.read_text())
        assert isinstance(migrated['hooks'], dict)

    @pytest.mark.xfail(reason="migrate_hooks_to_object_format not implemented yet")
    def test_empty_file_template_replacement(self, temp_settings_dir):
        """Test that empty file triggers template replacement.

        REQUIREMENT: Empty file should be replaced with template.
        Expected: Template settings written.
        """
        from plugins.autonomous_dev.lib.hook_activator import migrate_hooks_to_object_format

        settings_path = temp_settings_dir / "settings.json"

        # Create empty file
        settings_path.write_text("")

        result = migrate_hooks_to_object_format(settings_path)

        migrated = json.loads(settings_path.read_text())
        assert 'hooks' in migrated

    @pytest.mark.xfail(reason="migrate_hooks_to_object_format not implemented yet")
    def test_corrupted_file_preserves_original(self, temp_settings_dir):
        """Test that corrupted file is backed up before replacement.

        REQUIREMENT: Original corrupted content should be preserved in backup.
        Expected: Backup contains original corrupted content.
        """
        from plugins.autonomous_dev.lib.hook_activator import migrate_hooks_to_object_format

        settings_path = temp_settings_dir / "settings.json"

        corrupted_content = "{invalid json"
        settings_path.write_text(corrupted_content)

        result = migrate_hooks_to_object_format(settings_path)

        # Backup should contain original corrupted content
        backup_path = result['backup_path']
        assert backup_path.read_text() == corrupted_content

    # ========================================================================
    # Migration Failure Path (5 tests)
    # ========================================================================

    @pytest.mark.xfail(reason="migrate_hooks_to_object_format not implemented yet")
    def test_parse_error_rollback(self, temp_settings_dir):
        """Test rollback from backup on parse error during migration.

        REQUIREMENT: Parse errors should trigger rollback.
        Expected: Original settings restored from backup.
        """
        from plugins.autonomous_dev.lib.hook_activator import migrate_hooks_to_object_format

        settings_path = temp_settings_dir / "settings.json"

        array_settings = {
            "hooks": [
                {"event": "PreToolUse", "command": "python hook.py"}
            ]
        }
        settings_path.write_text(json.dumps(array_settings, indent=2))

        # Mock parse error during migration
        with patch('json.dumps', side_effect=ValueError("Parse error")):
            result = migrate_hooks_to_object_format(settings_path)

            # Should report error
            assert 'error' in result
            assert result['error'] is not None

            # Original settings should be restored
            current = json.loads(settings_path.read_text())
            assert current == array_settings

    @pytest.mark.xfail(reason="migrate_hooks_to_object_format not implemented yet")
    def test_write_error_rollback(self, temp_settings_dir):
        """Test rollback from backup on write error.

        REQUIREMENT: Write errors should trigger rollback.
        Expected: Original settings restored.
        """
        from plugins.autonomous_dev.lib.hook_activator import migrate_hooks_to_object_format

        settings_path = temp_settings_dir / "settings.json"

        array_settings = {
            "hooks": [
                {"event": "PreToolUse", "command": "python hook.py"}
            ]
        }
        settings_path.write_text(json.dumps(array_settings, indent=2))

        # Mock write error
        with patch('pathlib.Path.write_text', side_effect=IOError("Write error")):
            result = migrate_hooks_to_object_format(settings_path)

            assert 'error' in result

    @pytest.mark.xfail(reason="migrate_hooks_to_object_format not implemented yet")
    def test_unexpected_schema_rollback(self, temp_settings_dir):
        """Test rollback on unexpected hook schema.

        REQUIREMENT: Unexpected schema should trigger rollback.
        Expected: Original settings preserved.
        """
        from plugins.autonomous_dev.lib.hook_activator import migrate_hooks_to_object_format

        settings_path = temp_settings_dir / "settings.json"

        # Unexpected schema (event is integer instead of string)
        unexpected_settings = {
            "hooks": [
                {"event": 123, "command": "python hook.py"}
            ]
        }
        settings_path.write_text(json.dumps(unexpected_settings, indent=2))

        result = migrate_hooks_to_object_format(settings_path)

        # Should handle gracefully (either migrate or report error)
        assert 'error' in result or result['migrated'] is True

    @pytest.mark.xfail(reason="migrate_hooks_to_object_format not implemented yet")
    def test_disk_full_error_message(self, temp_settings_dir):
        """Test error message when disk is full.

        REQUIREMENT: Disk full errors should be reported clearly.
        Expected: Error message indicates disk space issue.
        """
        from plugins.autonomous_dev.lib.hook_activator import migrate_hooks_to_object_format

        settings_path = temp_settings_dir / "settings.json"

        array_settings = {
            "hooks": [
                {"event": "PreToolUse", "command": "python hook.py"}
            ]
        }
        settings_path.write_text(json.dumps(array_settings, indent=2))

        # Mock disk full error
        with patch('pathlib.Path.write_text', side_effect=OSError(28, "No space left on device")):
            result = migrate_hooks_to_object_format(settings_path)

            assert 'error' in result
            assert 'space' in result['error'].lower() or 'disk' in result['error'].lower()

    @pytest.mark.xfail(reason="migrate_hooks_to_object_format not implemented yet")
    def test_original_preserved_on_failure(self, temp_settings_dir):
        """Test that original settings are preserved when migration fails.

        REQUIREMENT: Failed migration should not corrupt original settings.
        Expected: Original array format maintained.
        """
        from plugins.autonomous_dev.lib.hook_activator import migrate_hooks_to_object_format

        settings_path = temp_settings_dir / "settings.json"

        array_settings = {
            "hooks": [
                {"event": "PreToolUse", "command": "python hook.py"}
            ]
        }
        settings_path.write_text(json.dumps(array_settings, indent=2))
        original_content = settings_path.read_text()

        # Mock failure
        with patch('json.dumps', side_effect=Exception("Unknown error")):
            result = migrate_hooks_to_object_format(settings_path)

            # Original content should be unchanged
            assert settings_path.read_text() == original_content

    # ========================================================================
    # Edge Cases (6 tests)
    # ========================================================================

    @pytest.mark.xfail(reason="migrate_hooks_to_object_format not implemented yet")
    def test_readonly_settings_error_message(self, temp_settings_dir):
        """Test error message when settings.json is read-only.

        REQUIREMENT: Read-only files should be reported clearly.
        Expected: Error message indicates permission issue.
        """
        from plugins.autonomous_dev.lib.hook_activator import migrate_hooks_to_object_format

        settings_path = temp_settings_dir / "settings.json"

        array_settings = {
            "hooks": [
                {"event": "PreToolUse", "command": "python hook.py"}
            ]
        }
        settings_path.write_text(json.dumps(array_settings, indent=2))

        # Make file read-only
        settings_path.chmod(0o444)

        try:
            result = migrate_hooks_to_object_format(settings_path)

            assert 'error' in result
            assert 'permission' in result['error'].lower() or 'readonly' in result['error'].lower()
        finally:
            # Restore permissions for cleanup
            settings_path.chmod(0o644)

    @pytest.mark.xfail(reason="migrate_hooks_to_object_format not implemented yet")
    def test_concurrent_modification_atomic_write(self, temp_settings_dir):
        """Test that atomic write prevents corruption from concurrent modification.

        REQUIREMENT: Atomic write should prevent corruption.
        Expected: Either original or migrated settings, never corrupt.
        """
        from plugins.autonomous_dev.lib.hook_activator import migrate_hooks_to_object_format

        settings_path = temp_settings_dir / "settings.json"

        array_settings = {
            "hooks": [
                {"event": "PreToolUse", "command": "python hook.py"}
            ]
        }
        settings_path.write_text(json.dumps(array_settings, indent=2))

        # Migration should use atomic write (tempfile + rename)
        # This test verifies the pattern is used
        with patch('tempfile.mkstemp') as mock_mkstemp:
            mock_fd = 123
            mock_temp = str(settings_path.parent / ".settings.tmp")
            mock_mkstemp.return_value = (mock_fd, mock_temp)

            with patch('os.write'):
                with patch('os.close'):
                    with patch('os.rename') as mock_rename:
                        result = migrate_hooks_to_object_format(settings_path)

                        # Should use atomic rename
                        if result['migrated']:
                            mock_rename.assert_called()

    @pytest.mark.xfail(reason="migrate_hooks_to_object_format not implemented yet")
    def test_symlink_resolution(self, temp_settings_dir):
        """Test that symlinks are resolved correctly.

        REQUIREMENT: Symlinks should be resolved to real paths.
        Expected: Migration works on symlink targets.
        """
        from plugins.autonomous_dev.lib.hook_activator import migrate_hooks_to_object_format

        settings_path = temp_settings_dir / "settings.json"
        symlink_path = temp_settings_dir / "settings.link.json"

        array_settings = {
            "hooks": [
                {"event": "PreToolUse", "command": "python hook.py"}
            ]
        }
        settings_path.write_text(json.dumps(array_settings, indent=2))

        # Create symlink
        symlink_path.symlink_to(settings_path)

        result = migrate_hooks_to_object_format(symlink_path)

        # Migration should work on symlink
        assert result['migrated'] is True

        # Original file should be migrated
        migrated = json.loads(settings_path.read_text())
        assert isinstance(migrated['hooks'], dict)

    @pytest.mark.xfail(reason="migrate_hooks_to_object_format not implemented yet")
    def test_whitespace_preservation(self, temp_settings_dir):
        """Test that JSON formatting/whitespace is normalized.

        REQUIREMENT: Output should have consistent formatting.
        Expected: Migrated JSON has consistent indentation.
        """
        from plugins.autonomous_dev.lib.hook_activator import migrate_hooks_to_object_format

        settings_path = temp_settings_dir / "settings.json"

        # Settings with inconsistent whitespace
        array_settings = {"hooks":[{"event":"PreToolUse","command":"python hook.py"}]}
        settings_path.write_text(json.dumps(array_settings))  # No indentation

        result = migrate_hooks_to_object_format(settings_path)

        # Migrated content should have consistent formatting
        content = settings_path.read_text()
        assert '\n' in content  # Should have newlines (formatted)
        assert '  ' in content or '\t' in content  # Should have indentation

    @pytest.mark.xfail(reason="migrate_hooks_to_object_format not implemented yet")
    def test_special_characters_in_paths(self, temp_settings_dir):
        """Test that special characters in hook paths are preserved.

        REQUIREMENT: Special characters should be escaped correctly.
        Expected: Paths with spaces, quotes, etc. preserved.
        """
        from plugins.autonomous_dev.lib.hook_activator import migrate_hooks_to_object_format

        settings_path = temp_settings_dir / "settings.json"

        array_settings = {
            "hooks": [
                {
                    "event": "PreToolUse",
                    "command": 'python "/path/with spaces/hook.py" --arg="value with \'quotes\'"'
                }
            ]
        }
        settings_path.write_text(json.dumps(array_settings, indent=2))

        result = migrate_hooks_to_object_format(settings_path)

        migrated = json.loads(settings_path.read_text())
        hook = migrated['hooks']['PreToolUse'][0]['hooks'][0]

        assert "/path/with spaces/hook.py" in hook['command']
        assert "value with 'quotes'" in hook['command']

    @pytest.mark.xfail(reason="migrate_hooks_to_object_format not implemented yet")
    def test_custom_timeout_preserved(self, temp_settings_dir):
        """Test that custom timeout values in array format are preserved.

        REQUIREMENT: Custom timeouts should not be overwritten.
        Expected: Custom timeout value maintained in object format.
        """
        from plugins.autonomous_dev.lib.hook_activator import migrate_hooks_to_object_format

        settings_path = temp_settings_dir / "settings.json"

        array_settings = {
            "hooks": [
                {
                    "event": "PreToolUse",
                    "command": "python hook.py",
                    "timeout": 10  # Custom timeout
                }
            ]
        }
        settings_path.write_text(json.dumps(array_settings, indent=2))

        result = migrate_hooks_to_object_format(settings_path)

        migrated = json.loads(settings_path.read_text())
        hook = migrated['hooks']['PreToolUse'][0]['hooks'][0]

        assert hook['timeout'] == 10  # Custom timeout preserved

    # ========================================================================
    # Integration with sync_marketplace (5 tests)
    # ========================================================================

    @pytest.mark.xfail(reason="sync_marketplace integration not implemented yet")
    def test_sync_marketplace_calls_migration(self, temp_settings_dir, tmp_path):
        """Test that sync_marketplace() calls migration after settings merge.

        REQUIREMENT: Marketplace sync should trigger migration.
        Expected: migrate_hooks_to_object_format() called during sync.
        """
        from plugins.autonomous_dev.lib.sync_dispatcher import sync_marketplace
        from plugins.autonomous_dev.lib.hook_activator import migrate_hooks_to_object_format

        project_root = tmp_path / "project"
        project_root.mkdir()
        claude_dir = project_root / ".claude"
        claude_dir.mkdir()

        settings_path = claude_dir / "settings.json"
        array_settings = {
            "hooks": [
                {"event": "PreToolUse", "command": "python hook.py"}
            ]
        }
        settings_path.write_text(json.dumps(array_settings, indent=2))

        marketplace_file = tmp_path / "installed_plugins.json"
        marketplace_file.write_text(json.dumps({
            "plugins": [{
                "id": "autonomous-dev",
                "version": "3.41.0"
            }]
        }))

        # Mock migration to verify it's called
        with patch('plugins.autonomous_dev.lib.sync_dispatcher.migrate_hooks_to_object_format') as mock_migrate:
            mock_migrate.return_value = {'migrated': True, 'format': 'array'}

            result = sync_marketplace(
                project_root=str(project_root),
                marketplace_plugins_file=marketplace_file
            )

            # Migration should have been called
            mock_migrate.assert_called_once()

    @pytest.mark.xfail(reason="sync_marketplace integration not implemented yet")
    def test_sync_continues_on_migration_failure(self, temp_settings_dir, tmp_path):
        """Test that sync continues even if migration fails.

        REQUIREMENT: Migration failure should not block sync.
        Expected: Sync completes successfully, migration error logged.
        """
        from plugins.autonomous_dev.lib.sync_dispatcher import sync_marketplace

        project_root = tmp_path / "project"
        project_root.mkdir()
        claude_dir = project_root / ".claude"
        claude_dir.mkdir()

        settings_path = claude_dir / "settings.json"
        settings_path.write_text("{invalid json")

        marketplace_file = tmp_path / "installed_plugins.json"
        marketplace_file.write_text(json.dumps({
            "plugins": [{
                "id": "autonomous-dev",
                "version": "3.41.0"
            }]
        }))

        # Sync should complete even with migration failure
        result = sync_marketplace(
            project_root=str(project_root),
            marketplace_plugins_file=marketplace_file
        )

        assert result.success is True

    @pytest.mark.xfail(reason="sync_marketplace integration not implemented yet")
    def test_migration_after_settings_merge(self, temp_settings_dir, tmp_path):
        """Test that migration happens after settings merge.

        REQUIREMENT: Migration should work on merged settings.
        Expected: New hooks merged, then migration applied to combined result.
        """
        from plugins.autonomous_dev.lib.sync_dispatcher import sync_marketplace

        project_root = tmp_path / "project"
        project_root.mkdir()
        claude_dir = project_root / ".claude"
        claude_dir.mkdir()

        # Existing array format settings
        settings_path = claude_dir / "settings.json"
        array_settings = {
            "hooks": [
                {"event": "PrePush", "command": "python existing_hook.py"}
            ]
        }
        settings_path.write_text(json.dumps(array_settings, indent=2))

        marketplace_file = tmp_path / "installed_plugins.json"
        marketplace_file.write_text(json.dumps({
            "plugins": [{
                "id": "autonomous-dev",
                "version": "3.41.0"
            }]
        }))

        result = sync_marketplace(
            project_root=str(project_root),
            marketplace_plugins_file=marketplace_file
        )

        # Settings should be in object format after sync
        migrated = json.loads(settings_path.read_text())
        assert isinstance(migrated['hooks'], dict)

    @pytest.mark.xfail(reason="sync_marketplace integration not implemented yet")
    def test_migration_logged_in_sync_result(self, temp_settings_dir, tmp_path):
        """Test that migration status is logged in sync result.

        REQUIREMENT: Sync result should indicate migration occurred.
        Expected: SyncResult contains migration information.
        """
        from plugins.autonomous_dev.lib.sync_dispatcher import sync_marketplace

        project_root = tmp_path / "project"
        project_root.mkdir()
        claude_dir = project_root / ".claude"
        claude_dir.mkdir()

        settings_path = claude_dir / "settings.json"
        array_settings = {
            "hooks": [
                {"event": "PreToolUse", "command": "python hook.py"}
            ]
        }
        settings_path.write_text(json.dumps(array_settings, indent=2))

        marketplace_file = tmp_path / "installed_plugins.json"
        marketplace_file.write_text(json.dumps({
            "plugins": [{
                "id": "autonomous-dev",
                "version": "3.41.0"
            }]
        }))

        result = sync_marketplace(
            project_root=str(project_root),
            marketplace_plugins_file=marketplace_file
        )

        # Result should contain migration info
        assert hasattr(result, 'migration_performed') or 'migration' in result.summary.lower()

    @pytest.mark.xfail(reason="sync_marketplace integration not implemented yet")
    def test_no_migration_on_fresh_sync(self, temp_settings_dir, tmp_path):
        """Test that fresh sync (no existing settings) doesn't trigger migration.

        REQUIREMENT: Fresh installs should skip migration.
        Expected: No migration attempted when settings.json doesn't exist.
        """
        from plugins.autonomous_dev.lib.sync_dispatcher import sync_marketplace

        project_root = tmp_path / "project"
        project_root.mkdir()
        claude_dir = project_root / ".claude"
        claude_dir.mkdir()

        # No settings.json exists

        marketplace_file = tmp_path / "installed_plugins.json"
        marketplace_file.write_text(json.dumps({
            "plugins": [{
                "id": "autonomous-dev",
                "version": "3.41.0"
            }]
        }))

        result = sync_marketplace(
            project_root=str(project_root),
            marketplace_plugins_file=marketplace_file
        )

        # Should complete without migration
        assert result.success is True

    # ========================================================================
    # Backup and Rollback (7 tests)
    # ========================================================================

    @pytest.mark.xfail(reason="migrate_hooks_to_object_format not implemented yet")
    def test_backup_created_before_migration(self, temp_settings_dir):
        """Test that backup is created before migration starts.

        REQUIREMENT: Backup must exist before any modification.
        Expected: Backup contains original array format.
        """
        from plugins.autonomous_dev.lib.hook_activator import migrate_hooks_to_object_format

        settings_path = temp_settings_dir / "settings.json"

        array_settings = {
            "hooks": [
                {"event": "PreToolUse", "command": "python hook.py"}
            ]
        }
        settings_path.write_text(json.dumps(array_settings, indent=2))

        result = migrate_hooks_to_object_format(settings_path)

        # Backup should contain original array format
        backup_path = result['backup_path']
        backup_content = json.loads(backup_path.read_text())

        assert isinstance(backup_content['hooks'], list)

    @pytest.mark.xfail(reason="migrate_hooks_to_object_format not implemented yet")
    def test_rollback_on_migration_error(self, temp_settings_dir):
        """Test that settings are rolled back on migration error.

        REQUIREMENT: Failed migration should restore original settings.
        Expected: Original array format restored from backup.
        """
        from plugins.autonomous_dev.lib.hook_activator import migrate_hooks_to_object_format

        settings_path = temp_settings_dir / "settings.json"

        array_settings = {
            "hooks": [
                {"event": "PreToolUse", "command": "python hook.py"}
            ]
        }
        original_content = json.dumps(array_settings, indent=2)
        settings_path.write_text(original_content)

        # Mock error during migration
        with patch('json.dumps', side_effect=[
            original_content,  # First call for backup succeeds
            Exception("Migration error")  # Second call for migration fails
        ]):
            result = migrate_hooks_to_object_format(settings_path)

            # Original should be restored
            current_content = settings_path.read_text()
            assert current_content == original_content

    @pytest.mark.xfail(reason="migrate_hooks_to_object_format not implemented yet")
    def test_multiple_backups_different_timestamps(self, temp_settings_dir):
        """Test that multiple migrations create different backup files.

        REQUIREMENT: Each migration should create unique backup.
        Expected: Different timestamp in backup filename.
        """
        from plugins.autonomous_dev.lib.hook_activator import migrate_hooks_to_object_format
        import time

        settings_path = temp_settings_dir / "settings.json"

        # First migration
        array_settings1 = {
            "hooks": [
                {"event": "PreToolUse", "command": "python hook1.py"}
            ]
        }
        settings_path.write_text(json.dumps(array_settings1, indent=2))

        result1 = migrate_hooks_to_object_format(settings_path)
        backup1 = result1['backup_path']

        # Wait to ensure different timestamp
        time.sleep(1)

        # Manually revert to array format for second test
        array_settings2 = {
            "hooks": [
                {"event": "PreToolUse", "command": "python hook2.py"}
            ]
        }
        settings_path.write_text(json.dumps(array_settings2, indent=2))

        result2 = migrate_hooks_to_object_format(settings_path)
        backup2 = result2['backup_path']

        # Backups should have different filenames (different timestamps)
        assert backup1.name != backup2.name

    @pytest.mark.xfail(reason="migrate_hooks_to_object_format not implemented yet")
    def test_backup_secure_permissions(self, temp_settings_dir):
        """Test that backup file has secure permissions (0o600).

        REQUIREMENT: Backup files must be user-only readable.
        Expected: Permissions set to 0o600.
        """
        from plugins.autonomous_dev.lib.hook_activator import migrate_hooks_to_object_format

        settings_path = temp_settings_dir / "settings.json"

        array_settings = {
            "hooks": [
                {"event": "PreToolUse", "command": "python hook.py"}
            ]
        }
        settings_path.write_text(json.dumps(array_settings, indent=2))

        result = migrate_hooks_to_object_format(settings_path)

        backup_path = result['backup_path']
        stat_info = backup_path.stat()
        permissions = stat_info.st_mode & 0o777

        assert permissions == 0o600

    @pytest.mark.xfail(reason="migrate_hooks_to_object_format not implemented yet")
    def test_backup_atomic_write(self, temp_settings_dir):
        """Test that backup uses atomic write pattern.

        REQUIREMENT: Backup write must be atomic.
        Expected: Tempfile + rename pattern used.
        """
        from plugins.autonomous_dev.lib.hook_activator import migrate_hooks_to_object_format

        settings_path = temp_settings_dir / "settings.json"

        array_settings = {
            "hooks": [
                {"event": "PreToolUse", "command": "python hook.py"}
            ]
        }
        settings_path.write_text(json.dumps(array_settings, indent=2))

        # Mock to verify atomic write
        with patch('tempfile.mkstemp') as mock_mkstemp:
            mock_fd = 123
            mock_temp = str(temp_settings_dir / ".backup.tmp")
            mock_mkstemp.return_value = (mock_fd, mock_temp)

            with patch('os.write'):
                with patch('os.close'):
                    with patch('os.rename') as mock_rename:
                        result = migrate_hooks_to_object_format(settings_path)

                        # Should use atomic write for backup
                        mock_rename.assert_called()

    @pytest.mark.xfail(reason="migrate_hooks_to_object_format not implemented yet")
    def test_rollback_preserves_file_permissions(self, temp_settings_dir):
        """Test that rollback preserves original file permissions.

        REQUIREMENT: Rollback should maintain file permissions.
        Expected: Permissions unchanged after rollback.
        """
        from plugins.autonomous_dev.lib.hook_activator import migrate_hooks_to_object_format

        settings_path = temp_settings_dir / "settings.json"

        array_settings = {
            "hooks": [
                {"event": "PreToolUse", "command": "python hook.py"}
            ]
        }
        settings_path.write_text(json.dumps(array_settings, indent=2))

        # Set custom permissions
        settings_path.chmod(0o640)
        original_perms = settings_path.stat().st_mode & 0o777

        # Mock error to trigger rollback
        with patch('json.dumps', side_effect=Exception("Error")):
            result = migrate_hooks_to_object_format(settings_path)

            # Permissions should be unchanged
            current_perms = settings_path.stat().st_mode & 0o777
            assert current_perms == original_perms

    @pytest.mark.xfail(reason="migrate_hooks_to_object_format not implemented yet")
    def test_backup_cleanup_on_success(self, temp_settings_dir):
        """Test that old backups are not automatically cleaned up.

        REQUIREMENT: Backups should be retained for manual recovery.
        Expected: Multiple backups can coexist.
        """
        from plugins.autonomous_dev.lib.hook_activator import migrate_hooks_to_object_format
        import time

        settings_path = temp_settings_dir / "settings.json"

        # Create first backup
        array_settings1 = {
            "hooks": [
                {"event": "PreToolUse", "command": "python hook1.py"}
            ]
        }
        settings_path.write_text(json.dumps(array_settings1, indent=2))

        result1 = migrate_hooks_to_object_format(settings_path)

        time.sleep(1)

        # Create second backup
        array_settings2 = {
            "hooks": [
                {"event": "PreToolUse", "command": "python hook2.py"}
            ]
        }
        settings_path.write_text(json.dumps(array_settings2, indent=2))

        result2 = migrate_hooks_to_object_format(settings_path)

        # Both backups should exist
        backup_files = list(temp_settings_dir.glob("settings.json.backup.*"))
        assert len(backup_files) >= 2


# ============================================================================
# Mark tests as expected to fail (TDD Red Phase)
# ============================================================================

# Mark all tests as expected to fail until migration is implemented
pytestmark = pytest.mark.xfail(
    not MIGRATION_FUNCTIONS_EXIST,
    reason="Migration functions not implemented yet (TDD Red Phase)",
    strict=False
)
