"""Unit tests for validate_command_consistency.py hook.

Tests command reference consistency validation across:
- plugin.json
- install_manifest.json
- Command .md files
- install.sh
- setup.md
"""

import json
import sys
from pathlib import Path

import pytest


# Add hooks directory to path for imports
sys.path.insert(
    0,
    str(
        Path(__file__).parent.parent.parent.parent
        / "plugins"
        / "autonomous-dev"
        / "hooks"
    ),
)

from validate_command_consistency import (
    get_active_command_files,
    get_archived_command_files,
    get_deprecated_commands,
    get_plugin_json_commands,
    get_manifest_command_files,
    find_command_refs_in_file,
    is_historical_file,
    validate_command_consistency,
)


class TestGetActiveCommandFiles:
    """Test active command file detection."""

    def test_finds_command_files(self, tmp_path):
        """Test finding .md files in commands directory."""
        commands_dir = tmp_path / "commands"
        commands_dir.mkdir()
        (commands_dir / "setup.md").write_text("# Setup")
        (commands_dir / "sync.md").write_text("# Sync")

        result = get_active_command_files(tmp_path)
        assert result == {"setup", "sync"}

    def test_excludes_archived_commands(self, tmp_path):
        """Test that archived commands are excluded.

        Uses non-recursive glob so files in archived/ subdirectory are not found.
        """
        commands_dir = tmp_path / "commands"
        commands_dir.mkdir()
        archived_dir = commands_dir / "archived"
        archived_dir.mkdir()

        (commands_dir / "active.md").write_text("# Active")
        (archived_dir / "old.md").write_text("# Old")

        result = get_active_command_files(tmp_path)
        assert result == {"active"}
        assert "old" not in result

    def test_returns_empty_for_missing_dir(self, tmp_path):
        """Test returns empty set when commands dir missing."""
        result = get_active_command_files(tmp_path)
        assert result == set()


class TestGetArchivedCommandFiles:
    """Test archived command file detection."""

    def test_finds_archived_commands(self, tmp_path):
        """Test finding files in archived directory."""
        archived_dir = tmp_path / "commands" / "archived"
        archived_dir.mkdir(parents=True)
        (archived_dir / "old-cmd.md").write_text("deprecated: true")

        result = get_archived_command_files(tmp_path)
        assert result == {"old-cmd"}

    def test_returns_empty_when_no_archived(self, tmp_path):
        """Test returns empty set when no archived dir."""
        result = get_archived_command_files(tmp_path)
        assert result == set()


class TestGetDeprecatedCommands:
    """Test deprecated command detection."""

    def test_detects_deprecated_frontmatter(self, tmp_path):
        """Test detection of deprecated: true in frontmatter."""
        commands_dir = tmp_path / "commands"
        commands_dir.mkdir()

        (commands_dir / "active.md").write_text("---\nname: active\n---")
        (commands_dir / "old.md").write_text("---\ndeprecated: true\n---")

        result = get_deprecated_commands(tmp_path)
        assert result == {"old"}
        assert "active" not in result

    def test_handles_no_frontmatter(self, tmp_path):
        """Test handling files without frontmatter."""
        commands_dir = tmp_path / "commands"
        commands_dir.mkdir()
        (commands_dir / "plain.md").write_text("# Just content")

        result = get_deprecated_commands(tmp_path)
        assert result == set()


class TestGetPluginJsonCommands:
    """Test plugin.json command parsing."""

    def test_parses_commands_list(self, tmp_path):
        """Test parsing commands from plugin.json."""
        plugin_json = tmp_path / "plugin.json"
        plugin_json.write_text(json.dumps({
            "commands": ["/setup", "/sync", "/implement"]
        }))

        result = get_plugin_json_commands(tmp_path)
        assert result == {"setup", "sync", "implement"}

    def test_strips_leading_slash(self, tmp_path):
        """Test that leading / is stripped from command names."""
        plugin_json = tmp_path / "plugin.json"
        plugin_json.write_text(json.dumps({
            "commands": ["/test", "no-slash"]
        }))

        result = get_plugin_json_commands(tmp_path)
        assert result == {"test", "no-slash"}

    def test_returns_empty_for_missing_file(self, tmp_path):
        """Test returns empty set when file missing."""
        result = get_plugin_json_commands(tmp_path)
        assert result == set()


class TestGetManifestCommandFiles:
    """Test install_manifest.json command file parsing."""

    def test_extracts_command_names_from_paths(self, tmp_path):
        """Test extracting command names from file paths."""
        config_dir = tmp_path / "config"
        config_dir.mkdir()
        manifest = config_dir / "install_manifest.json"
        manifest.write_text(json.dumps({
            "components": {
                "commands": {
                    "files": [
                        "plugins/autonomous-dev/commands/setup.md",
                        "plugins/autonomous-dev/commands/sync.md"
                    ]
                }
            }
        }))

        result = get_manifest_command_files(tmp_path)
        assert result == {"setup", "sync"}


class TestFindCommandRefsInFile:
    """Test finding command references in files."""

    def test_finds_slash_command_refs(self, tmp_path):
        """Test finding /command references."""
        test_file = tmp_path / "test.md"
        test_file.write_text("""
Line 1
Try /setup for setup
Use /implement "feature"
""")

        result = find_command_refs_in_file(test_file, {"setup", "implement"})
        assert "setup" in result
        assert "implement" in result
        assert 3 in result["setup"]
        assert 4 in result["implement"]

    def test_ignores_partial_matches(self, tmp_path):
        """Test that partial matches are ignored."""
        test_file = tmp_path / "test.md"
        test_file.write_text("Try /setup-wizard for advanced setup")

        result = find_command_refs_in_file(test_file, {"setup"})
        # Should not match /setup-wizard when looking for /setup
        assert "setup" not in result

    def test_returns_empty_for_missing_file(self, tmp_path):
        """Test returns empty dict for missing file."""
        result = find_command_refs_in_file(tmp_path / "missing.md", {"setup"})
        assert result == {}


class TestIsHistoricalFile:
    """Test historical file detection."""

    def test_detects_changelog(self, tmp_path):
        """Test CHANGELOG is marked as historical."""
        assert is_historical_file(tmp_path / "CHANGELOG.md")

    def test_detects_history_files(self, tmp_path):
        """Test *-HISTORY.md files are historical."""
        assert is_historical_file(tmp_path / "docs/COMMAND-HISTORY.md")

    def test_detects_epic_files(self, tmp_path):
        """Test epic-* files are historical."""
        assert is_historical_file(tmp_path / "docs/epic-batch-processing.md")

    def test_detects_archived(self, tmp_path):
        """Test archived/ paths are historical."""
        assert is_historical_file(tmp_path / "commands/archived/old.md")

    def test_regular_docs_not_historical(self, tmp_path):
        """Test regular docs are NOT historical."""
        assert not is_historical_file(tmp_path / "README.md")
        assert not is_historical_file(tmp_path / "docs/QUICKSTART.md")


class TestValidateCommandConsistency:
    """Integration tests for full validation."""

    def test_passes_when_consistent(self):
        """Test validation passes for actual codebase."""
        # This tests against the real codebase
        is_valid, errors = validate_command_consistency()

        # After our fixes, should pass
        if not is_valid:
            print(f"Errors: {errors}")
        assert is_valid, f"Validation failed with: {errors}"

    def test_detects_deprecated_in_plugin_json(self, tmp_path, monkeypatch):
        """Test detecting deprecated commands in plugin.json."""
        # Create mock plugin structure
        plugin_dir = tmp_path / "plugins" / "autonomous-dev"
        plugin_dir.mkdir(parents=True)
        commands_dir = plugin_dir / "commands"
        commands_dir.mkdir()
        config_dir = plugin_dir / "config"
        config_dir.mkdir()

        # Create deprecated command
        (commands_dir / "old-cmd.md").write_text("---\ndeprecated: true\n---")

        # Add to plugin.json (error: deprecated command listed)
        (plugin_dir / "plugin.json").write_text(json.dumps({
            "commands": ["/old-cmd"]
        }))

        # Empty manifest
        (config_dir / "install_manifest.json").write_text(json.dumps({
            "commands": [],
            "components": {"commands": {"files": []}}
        }))

        # Mock to use tmp_path
        monkeypatch.setattr(
            "validate_command_consistency.get_project_root",
            lambda: tmp_path
        )

        is_valid, errors = validate_command_consistency()
        assert not is_valid
        assert any("deprecated" in e.lower() for e in errors)
