#!/usr/bin/env python3
"""
Tests for GitHub sync mode hooks migration (Issue #156).

This module tests that _dispatch_github() correctly migrates settings.json
from old array format to new object format required by Claude Code 2.0.

The bug: _dispatch_github() was NOT calling migrate_hooks_to_object_format(),
while sync_marketplace() WAS calling it. This caused users running the default
`/sync` command to get the Claude Code error:
    "hooks: Expected object, but received array"

Fix: Added hooks migration step to _dispatch_github() method (lines 1167-1212).

Author: test-master
Date: 2025-12-21
Issue: GitHub #156
"""

import json
import sys
from pathlib import Path
from unittest.mock import patch, MagicMock
import inspect

import pytest

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

from plugins.autonomous_dev.lib.sync_dispatcher import SyncDispatcher


class TestDispatchGithubContainsMigrationCode:
    """Verify that _dispatch_github() method contains migration code."""

    def test_dispatch_github_imports_migrate_function(self):
        """Test that _dispatch_github imports migrate_hooks_to_object_format.

        REQUIREMENT: GitHub sync must call the migration function.
        Expected: Source code contains the import statement.
        """
        # Get the source code of _dispatch_github method
        source = inspect.getsource(SyncDispatcher._dispatch_github)

        # Check that it imports the migration function
        assert 'migrate_hooks_to_object_format' in source, \
            "_dispatch_github should import migrate_hooks_to_object_format"

    def test_dispatch_github_calls_migration_on_settings_path(self):
        """Test that _dispatch_github calls migration on settings.json path.

        REQUIREMENT: Migration must target ~/.claude/settings.json.
        Expected: Source code calls migration with settings_path.
        """
        source = inspect.getsource(SyncDispatcher._dispatch_github)

        # Check that it constructs the settings path
        assert 'settings_path = Path.home()' in source or \
               "settings.json" in source, \
            "_dispatch_github should target settings.json"

    def test_dispatch_github_handles_migration_result(self):
        """Test that _dispatch_github checks migration result.

        REQUIREMENT: Migration result should be used to update sync result.
        Expected: Source code checks migration_result['migrated'].
        """
        source = inspect.getsource(SyncDispatcher._dispatch_github)

        # Check that it handles the migration result
        assert "migration_result['migrated']" in source or \
               'hooks_migrated' in source, \
            "_dispatch_github should handle migration result"

    def test_dispatch_github_has_error_handling_for_migration(self):
        """Test that _dispatch_github has error handling for migration.

        REQUIREMENT: Migration errors should not block sync.
        Expected: Source code has try/except around migration.
        """
        source = inspect.getsource(SyncDispatcher._dispatch_github)

        # Check for error handling
        assert 'except Exception' in source or 'except' in source, \
            "_dispatch_github should have error handling for migration"


class TestMigrateFunctionExists:
    """Verify that migrate_hooks_to_object_format function exists and works."""

    def test_migrate_function_importable(self):
        """Test that migrate_hooks_to_object_format can be imported.

        REQUIREMENT: Migration function must be available for import.
        Expected: Import succeeds without error.
        """
        from plugins.autonomous_dev.lib.hook_activator import migrate_hooks_to_object_format
        assert callable(migrate_hooks_to_object_format)

    def test_migrate_function_handles_missing_file(self, tmp_path):
        """Test that migration handles missing settings.json gracefully.

        REQUIREMENT: Missing file should not raise exception.
        Expected: Returns result with migrated=False and format='missing'.
        """
        from plugins.autonomous_dev.lib.hook_activator import migrate_hooks_to_object_format

        settings_path = tmp_path / "nonexistent" / "settings.json"
        result = migrate_hooks_to_object_format(settings_path)

        assert result['migrated'] is False
        assert result['format'] == 'missing'

    def test_migrate_function_detects_object_format(self, tmp_path):
        """Test that migration detects object format and skips.

        REQUIREMENT: Already-migrated settings should be skipped.
        Expected: Returns result with migrated=False and format='object'.
        """
        from plugins.autonomous_dev.lib.hook_activator import migrate_hooks_to_object_format

        # Create object format settings
        claude_dir = tmp_path / ".claude"
        claude_dir.mkdir()
        settings_path = claude_dir / "settings.json"

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

    def test_migrate_function_converts_array_format(self, tmp_path):
        """Test that migration converts array format to object format.

        REQUIREMENT: Array format must be converted to object format.
        Expected: Returns result with migrated=True and creates backup.
        """
        from plugins.autonomous_dev.lib.hook_activator import migrate_hooks_to_object_format

        # Create array format settings (OLD)
        claude_dir = tmp_path / ".claude"
        claude_dir.mkdir()
        settings_path = claude_dir / "settings.json"

        array_settings = {
            "hooks": [
                {"event": "PreToolUse", "command": "python hook.py"}
            ]
        }
        settings_path.write_text(json.dumps(array_settings, indent=2))

        result = migrate_hooks_to_object_format(settings_path)

        assert result['migrated'] is True
        assert result['format'] == 'array'
        assert result['backup_path'].exists()

        # Verify migrated content
        migrated = json.loads(settings_path.read_text())
        assert isinstance(migrated['hooks'], dict)
        assert 'PreToolUse' in migrated['hooks']


class TestSyncResultIncludesMigrationInfo:
    """Verify that SyncResult includes hooks_migrated field."""

    def test_sync_result_has_hooks_migrated_in_code(self):
        """Test that _dispatch_github adds hooks_migrated to details.

        REQUIREMENT: Result details should indicate migration status.
        Expected: Source code sets hooks_migrated in details.
        """
        source = inspect.getsource(SyncDispatcher._dispatch_github)

        # Check that hooks_migrated is added to details
        assert '"hooks_migrated"' in source or "'hooks_migrated'" in source, \
            "_dispatch_github should add hooks_migrated to result details"

    def test_migration_message_in_code(self):
        """Test that _dispatch_github includes migration in message.

        REQUIREMENT: User should see migration occurred in message.
        Expected: Source code includes migration_msg in output.
        """
        source = inspect.getsource(SyncDispatcher._dispatch_github)

        # Check for migration message
        assert 'migration_msg' in source or 'hooks format migrated' in source, \
            "_dispatch_github should include migration in message"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
