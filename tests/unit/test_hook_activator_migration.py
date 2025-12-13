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
                                "command": "python /Users/akaszubski/Documents/GitHub/autonomous-dev/.claude/hooks/pre_tool_use.py"
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
# Mark tests as expected to fail (TDD Red Phase)
# ============================================================================

# Mark all tests as expected to fail until migration is implemented
pytestmark = pytest.mark.xfail(
    not MIGRATION_FUNCTIONS_EXIST,
    reason="Migration functions not implemented yet (TDD Red Phase)",
    strict=False
)
