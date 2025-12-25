"""
Unit tests for hook path migration script (Issue #113).

Tests for migrate_hook_paths.py - dynamic PreToolUse hook path resolution.
These tests should FAIL initially (TDD red phase).
"""

import json
from pathlib import Path
from unittest.mock import patch

import pytest


class TestMigrateHookPaths:
    """Test migrate_hook_paths() function for Issue #113."""

    @pytest.fixture
    def settings_hardcoded(self):
        """Settings with hardcoded absolute path (needs migration)."""
        return {
            "hooks": {
                "PreToolUse": [
                    {
                        "matcher": "*",
                        "hooks": [
                            {
                                "type": "command",
                                "command": "MCP_AUTO_APPROVE=true python3 /Users/akaszubski/Documents/GitHub/autonomous-dev/plugins/autonomous-dev/hooks/pre_tool_use.py"
                            }
                        ]
                    }
                ]
            }
        }

    @pytest.fixture
    def settings_correct(self):
        """Settings with correct portable path (no migration needed)."""
        return {
            "hooks": {
                "PreToolUse": [
                    {
                        "matcher": "*",
                        "hooks": [
                            {
                                "type": "command",
                                "command": "MCP_AUTO_APPROVE=true python3 ~/.claude/hooks/pre_tool_use.py"
                            }
                        ]
                    }
                ]
            }
        }

    @pytest.fixture
    def settings_multiple_hooks(self):
        """Settings with multiple hooks, one needs migration."""
        return {
            "hooks": {
                "PreToolUse": [
                    {
                        "matcher": "*",
                        "hooks": [
                            {
                                "type": "command",
                                "command": "MCP_AUTO_APPROVE=true python3 /Users/akaszubski/Documents/GitHub/autonomous-dev/plugins/autonomous-dev/hooks/pre_tool_use.py"
                            }
                        ]
                    }
                ],
                "SubagentStop": [
                    {
                        "matcher": "*",
                        "hooks": [
                            {
                                "type": "command",
                                "command": "python3 ~/.claude/hooks/auto_git_workflow.py"
                            }
                        ]
                    }
                ]
            }
        }

    @pytest.fixture
    def settings_file(self, tmp_path):
        """Create temporary settings.json file."""
        settings_path = tmp_path / ".claude" / "settings.json"
        settings_path.parent.mkdir(parents=True, exist_ok=True)
        return settings_path

    def test_detects_hardcoded_path(self, settings_hardcoded, settings_file):
        """Test detect hardcoded absolute paths like /Users/akaszubski/..."""
        # Import will fail initially (no implementation)
        from autonomous_dev.scripts.migrate_hook_paths import migrate_hook_paths

        settings_file.write_text(json.dumps(settings_hardcoded, indent=2))

        result = migrate_hook_paths(settings_file)

        # Should detect hardcoded path
        assert result["migrated"] is True
        assert result["changes"] > 0
        assert "hardcoded path" in result["summary"].lower()

    def test_replaces_with_tilde_path(self, settings_hardcoded, settings_file):
        """Test replace hardcoded path with ~/.claude/hooks/pre_tool_use.py."""
        from autonomous_dev.scripts.migrate_hook_paths import migrate_hook_paths

        settings_file.write_text(json.dumps(settings_hardcoded, indent=2))

        migrate_hook_paths(settings_file)

        # Read migrated settings
        migrated = json.loads(settings_file.read_text())
        command = migrated["hooks"]["PreToolUse"][0]["hooks"][0]["command"]

        # Should use tilde path
        assert "~/.claude/hooks/pre_tool_use.py" in command
        assert "/Users/akaszubski/" not in command
        assert "/Documents/GitHub/" not in command

    def test_preserves_environment_variable(self, settings_hardcoded, settings_file):
        """Test preserve MCP_AUTO_APPROVE=true environment variable."""
        from autonomous_dev.scripts.migrate_hook_paths import migrate_hook_paths

        settings_file.write_text(json.dumps(settings_hardcoded, indent=2))

        migrate_hook_paths(settings_file)

        # Read migrated settings
        migrated = json.loads(settings_file.read_text())
        command = migrated["hooks"]["PreToolUse"][0]["hooks"][0]["command"]

        # Should preserve environment variable
        assert "MCP_AUTO_APPROVE=true" in command

    def test_creates_backup_before_modification(self, settings_hardcoded, settings_file):
        """Test create backup file before modifying settings."""
        from autonomous_dev.scripts.migrate_hook_paths import migrate_hook_paths

        settings_file.write_text(json.dumps(settings_hardcoded, indent=2))
        original_content = settings_file.read_text()

        result = migrate_hook_paths(settings_file)

        # Should create backup
        assert result["backup_path"] is not None
        backup_path = Path(result["backup_path"])
        assert backup_path.exists()
        assert backup_path.name.startswith("settings.json.backup.")

        # Backup should contain original content
        assert backup_path.read_text() == original_content

    def test_handles_missing_settings_gracefully(self, settings_file):
        """Test gracefully handle missing ~/.claude/settings.json."""
        from autonomous_dev.scripts.migrate_hook_paths import migrate_hook_paths

        # Don't create settings file

        result = migrate_hook_paths(settings_file)

        # Should not fail
        assert result["migrated"] is False
        assert "not found" in result["summary"].lower()

    def test_handles_already_migrated_paths(self, settings_correct, settings_file):
        """Test idempotent - handle already-migrated paths (no changes)."""
        from autonomous_dev.scripts.migrate_hook_paths import migrate_hook_paths

        settings_file.write_text(json.dumps(settings_correct, indent=2))
        original_content = settings_file.read_text()

        result = migrate_hook_paths(settings_file)

        # Should be idempotent
        assert result["migrated"] is False
        assert result["changes"] == 0
        assert "already portable" in result["summary"].lower()

        # Should not modify file
        assert settings_file.read_text() == original_content

    def test_handles_corrupted_json(self, settings_file):
        """Test gracefully handle corrupted JSON file."""
        from autonomous_dev.scripts.migrate_hook_paths import migrate_hook_paths

        settings_file.write_text("{invalid json")

        result = migrate_hook_paths(settings_file)

        # Should not crash
        assert result["migrated"] is False
        assert "error" in result["summary"].lower() or "invalid" in result["summary"].lower()

    def test_migrates_multiple_hook_types(self, settings_multiple_hooks, settings_file):
        """Test migrate only PreToolUse hooks, leave others unchanged."""
        from autonomous_dev.scripts.migrate_hook_paths import migrate_hook_paths

        settings_file.write_text(json.dumps(settings_multiple_hooks, indent=2))

        migrate_hook_paths(settings_file)

        # Read migrated settings
        migrated = json.loads(settings_file.read_text())

        # PreToolUse should be migrated
        pre_tool_command = migrated["hooks"]["PreToolUse"][0]["hooks"][0]["command"]
        assert "~/.claude/hooks/pre_tool_use.py" in pre_tool_command

        # SubagentStop should remain unchanged (already portable)
        subagent_command = migrated["hooks"]["SubagentStop"][0]["hooks"][0]["command"]
        assert "~/.claude/hooks/auto_git_workflow.py" in subagent_command

    def test_handles_no_hooks_section(self, settings_file):
        """Test gracefully handle settings with no hooks section."""
        from autonomous_dev.scripts.migrate_hook_paths import migrate_hook_paths

        settings_file.write_text(json.dumps({"other": "config"}, indent=2))

        result = migrate_hook_paths(settings_file)

        # Should not crash
        assert result["migrated"] is False
        assert result["changes"] == 0

    def test_preserves_other_settings(self, settings_hardcoded, settings_file):
        """Test preserve other settings sections during migration."""
        from autonomous_dev.scripts.migrate_hook_paths import migrate_hook_paths

        settings_with_extras = {
            **settings_hardcoded,
            "plugins": ["autonomous-dev"],
            "theme": "dark"
        }
        settings_file.write_text(json.dumps(settings_with_extras, indent=2))

        migrate_hook_paths(settings_file)

        # Read migrated settings
        migrated = json.loads(settings_file.read_text())

        # Should preserve other settings
        assert migrated["plugins"] == ["autonomous-dev"]
        assert migrated["theme"] == "dark"

    def test_detects_various_hardcoded_patterns(self, settings_file):
        """Test detect various hardcoded path patterns."""
        from autonomous_dev.scripts.migrate_hook_paths import migrate_hook_paths

        patterns = [
            "/Users/akaszubski/Documents/GitHub/autonomous-dev/plugins/autonomous-dev/hooks/pre_tool_use.py",
            "/home/user/projects/autonomous-dev/plugins/autonomous-dev/hooks/pre_tool_use.py",
            "C:\\Users\\user\\autonomous-dev\\plugins\\autonomous-dev\\hooks\\pre_tool_use.py",
            "/opt/autonomous-dev/plugins/autonomous-dev/hooks/pre_tool_use.py"
        ]

        for pattern in patterns:
            settings = {
                "hooks": {
                    "PreToolUse": [{
                        "matcher": "*",
                        "hooks": [{"type": "command", "command": f"python3 {pattern}"}]
                    }]
                }
            }
            settings_file.write_text(json.dumps(settings, indent=2))

            result = migrate_hook_paths(settings_file)

            # Should detect and migrate all patterns
            assert result["migrated"] is True, f"Failed to detect pattern: {pattern}"


class TestFindLibDirectory:
    """Test find_lib_directory() function in pre_tool_use.py."""

    def test_finds_lib_from_claude_hooks(self, tmp_path):
        """Test find lib directory from ~/.claude/hooks/ location."""
        from autonomous_dev.hooks.pre_tool_use import find_lib_directory

        # Create ~/.claude/hooks/pre_tool_use.py location
        hooks_dir = tmp_path / ".claude" / "hooks"
        hooks_dir.mkdir(parents=True)
        lib_dir = tmp_path / ".claude" / "lib"
        lib_dir.mkdir(parents=True)

        with patch("pathlib.Path.home", return_value=tmp_path):
            result = find_lib_directory(hooks_dir / "pre_tool_use.py")

        # Should find lib directory
        assert result is not None
        assert result == lib_dir
        assert result.exists()

    def test_finds_lib_from_development_location(self, tmp_path):
        """Test find lib directory from development location."""
        from autonomous_dev.hooks.pre_tool_use import find_lib_directory

        # Create plugins/autonomous-dev/hooks/ location
        hooks_dir = tmp_path / "plugins" / "autonomous-dev" / "hooks"
        hooks_dir.mkdir(parents=True)
        lib_dir = tmp_path / "plugins" / "autonomous-dev" / "lib"
        lib_dir.mkdir(parents=True)

        result = find_lib_directory(hooks_dir / "pre_tool_use.py")

        # Should find lib directory
        assert result is not None
        assert result == lib_dir
        assert result.exists()

    def test_returns_none_if_lib_not_found(self, tmp_path):
        """Test return None if lib directory not found (graceful failure)."""
        from autonomous_dev.hooks.pre_tool_use import find_lib_directory

        # Create hooks directory without lib
        hooks_dir = tmp_path / "hooks"
        hooks_dir.mkdir(parents=True)

        result = find_lib_directory(hooks_dir / "pre_tool_use.py")

        # Should return None gracefully
        assert result is None

    def test_checks_marketplace_location_as_fallback(self, tmp_path):
        """Test check marketplace location as fallback."""
        from autonomous_dev.hooks.pre_tool_use import find_lib_directory

        # Create marketplace location
        hooks_dir = tmp_path / ".claude" / "hooks"
        hooks_dir.mkdir(parents=True)
        marketplace_lib = tmp_path / ".claude" / "plugins" / "autonomous-dev" / "lib"
        marketplace_lib.mkdir(parents=True)

        with patch("pathlib.Path.home", return_value=tmp_path):
            result = find_lib_directory(hooks_dir / "pre_tool_use.py")

        # Should find marketplace lib as fallback
        assert result is not None
        assert result == marketplace_lib

    def test_prioritizes_local_over_marketplace(self, tmp_path):
        """Test prioritize ~/.claude/lib over marketplace location."""
        from autonomous_dev.hooks.pre_tool_use import find_lib_directory

        # Create both local and marketplace locations
        hooks_dir = tmp_path / ".claude" / "hooks"
        hooks_dir.mkdir(parents=True)
        local_lib = tmp_path / ".claude" / "lib"
        local_lib.mkdir(parents=True)
        marketplace_lib = tmp_path / ".claude" / "plugins" / "autonomous-dev" / "lib"
        marketplace_lib.mkdir(parents=True)

        with patch("pathlib.Path.home", return_value=tmp_path):
            result = find_lib_directory(hooks_dir / "pre_tool_use.py")

        # Should prefer local lib
        assert result == local_lib

    def test_handles_missing_parent_directory(self, tmp_path):
        """Test gracefully handle missing parent directory."""
        from autonomous_dev.hooks.pre_tool_use import find_lib_directory

        # Create hook file in non-existent directory
        result = find_lib_directory(tmp_path / "nonexistent" / "pre_tool_use.py")

        # Should return None gracefully
        assert result is None

    def test_handles_symlinks(self, tmp_path):
        """Test handle symlinked directories correctly."""
        from autonomous_dev.hooks.pre_tool_use import find_lib_directory

        # Create real lib directory
        real_lib = tmp_path / "real" / "lib"
        real_lib.mkdir(parents=True)

        # Create symlink from hooks location
        hooks_dir = tmp_path / ".claude" / "hooks"
        hooks_dir.mkdir(parents=True)
        lib_symlink = tmp_path / ".claude" / "lib"
        lib_symlink.symlink_to(real_lib)

        with patch("pathlib.Path.home", return_value=tmp_path):
            result = find_lib_directory(hooks_dir / "pre_tool_use.py")

        # Should follow symlinks
        assert result is not None
        assert result.resolve() == real_lib.resolve()


class TestMigrationCLI:
    """Test command-line interface for migration script."""

    def test_accepts_settings_path_argument(self):
        """Test accept --settings-path command-line argument."""
        from autonomous_dev.scripts.migrate_hook_paths import main

        with patch("sys.argv", ["migrate_hook_paths.py", "--settings-path", "~/.claude/settings.json"]):
            # Should not crash on argument parsing
            try:
                main()
            except (FileNotFoundError, SystemExit):
                pass  # Expected if file doesn't exist

    def test_uses_default_settings_path(self):
        """Test use ~/.claude/settings.json by default."""
        from autonomous_dev.scripts.migrate_hook_paths import main

        with patch("sys.argv", ["migrate_hook_paths.py"]):
            with patch("autonomous_dev.scripts.migrate_hook_paths.migrate_hook_paths") as mock_migrate:
                mock_migrate.return_value = {"migrated": False, "changes": 0, "summary": "No changes"}
                try:
                    main()
                except SystemExit:
                    pass

                # Should use default path
                assert mock_migrate.called

    def test_dry_run_mode(self, settings_file):
        """Test --dry-run mode doesn't modify files."""
        from autonomous_dev.scripts.migrate_hook_paths import main

        settings = {
            "hooks": {
                "PreToolUse": [{
                    "matcher": "*",
                    "hooks": [{"type": "command", "command": "python3 /Users/akaszubski/path/to/pre_tool_use.py"}]
                }]
            }
        }
        settings_file.write_text(json.dumps(settings, indent=2))
        original_content = settings_file.read_text()

        with patch("sys.argv", ["migrate_hook_paths.py", "--settings-path", str(settings_file), "--dry-run"]):
            try:
                main()
            except SystemExit:
                pass

        # Should not modify file in dry-run mode
        assert settings_file.read_text() == original_content

    def test_verbose_mode(self, settings_file, capsys):
        """Test --verbose mode outputs detailed information."""
        from autonomous_dev.scripts.migrate_hook_paths import main

        settings = {
            "hooks": {
                "PreToolUse": [{
                    "matcher": "*",
                    "hooks": [{"type": "command", "command": "python3 ~/.claude/hooks/pre_tool_use.py"}]
                }]
            }
        }
        settings_file.write_text(json.dumps(settings, indent=2))

        with patch("sys.argv", ["migrate_hook_paths.py", "--settings-path", str(settings_file), "--verbose"]):
            try:
                main()
            except SystemExit:
                pass

        captured = capsys.readouterr()

        # Should output verbose information
        assert len(captured.out) > 0 or len(captured.err) > 0
