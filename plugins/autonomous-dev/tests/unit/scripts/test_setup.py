"""
Tests for scripts/setup.py

Tests the SetupWizard class and its methods for plugin setup automation.
"""

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# Import after adding parent to path
import sys
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent / "scripts"))
from setup import SetupWizard


class TestSetupWizardInit:
    """Test SetupWizard initialization."""

    def test_default_initialization(self, tmp_path, monkeypatch):
        """Test wizard initializes with correct defaults."""
        monkeypatch.chdir(tmp_path)
        wizard = SetupWizard()

        assert wizard.auto is False
        assert wizard.preset is None
        assert wizard.project_root == tmp_path
        assert wizard.claude_dir == tmp_path / ".claude"
        assert wizard.plugin_dir == tmp_path / ".claude" / "plugins" / "autonomous-dev"

    def test_auto_mode_initialization(self, tmp_path, monkeypatch):
        """Test wizard initializes in auto mode."""
        monkeypatch.chdir(tmp_path)
        wizard = SetupWizard(auto=True)

        assert wizard.auto is True

    def test_preset_initialization(self, tmp_path, monkeypatch):
        """Test wizard initializes with preset."""
        monkeypatch.chdir(tmp_path)
        wizard = SetupWizard(preset="team")

        assert wizard.preset == "team"


class TestVerifyPluginInstallation:
    """Test plugin installation verification."""

    def test_plugin_exists(self, tmp_path, monkeypatch):
        """Test returns True when plugin directory exists."""
        monkeypatch.chdir(tmp_path)
        plugin_dir = tmp_path / ".claude" / "plugins" / "autonomous-dev"
        plugin_dir.mkdir(parents=True)

        wizard = SetupWizard()
        assert wizard.verify_plugin_installation() is True

    def test_plugin_missing(self, tmp_path, monkeypatch, capsys):
        """Test returns False and prints error when plugin missing."""
        monkeypatch.chdir(tmp_path)
        wizard = SetupWizard(auto=True)  # Auto mode to suppress output

        assert wizard.verify_plugin_installation() is False

    def test_plugin_exists_shows_message(self, tmp_path, monkeypatch, capsys):
        """Test shows success message when plugin found (non-auto mode)."""
        monkeypatch.chdir(tmp_path)
        plugin_dir = tmp_path / ".claude" / "plugins" / "autonomous-dev"
        plugin_dir.mkdir(parents=True)

        wizard = SetupWizard(auto=False)
        wizard.verify_plugin_installation()

        captured = capsys.readouterr()
        assert "Plugin found" in captured.out


class TestCopyPluginFiles:
    """Test copying hooks and templates from plugin."""

    def test_copies_hooks_directory(self, tmp_path, monkeypatch):
        """Test copies hooks from plugin to project."""
        monkeypatch.chdir(tmp_path)

        # Create source plugin directory with hooks
        plugin_hooks = tmp_path / ".claude" / "plugins" / "autonomous-dev" / "hooks"
        plugin_hooks.mkdir(parents=True)
        (plugin_hooks / "auto_format.py").write_text("# hook code")

        wizard = SetupWizard()
        wizard.copy_plugin_files()

        # Check hooks copied
        dest_hooks = tmp_path / ".claude" / "hooks"
        assert dest_hooks.exists()
        assert (dest_hooks / "auto_format.py").exists()

    def test_copies_templates_directory(self, tmp_path, monkeypatch):
        """Test copies templates from plugin to project."""
        monkeypatch.chdir(tmp_path)

        # Create source plugin directory with templates
        plugin_templates = tmp_path / ".claude" / "plugins" / "autonomous-dev" / "templates"
        plugin_templates.mkdir(parents=True)
        (plugin_templates / "PROJECT.md").write_text("# Template")

        wizard = SetupWizard()
        wizard.copy_plugin_files()

        # Check templates copied
        dest_templates = tmp_path / ".claude" / "templates"
        assert dest_templates.exists()
        assert (dest_templates / "PROJECT.md").exists()

    def test_skips_if_already_exists(self, tmp_path, monkeypatch):
        """Test doesn't overwrite existing directories."""
        monkeypatch.chdir(tmp_path)

        # Create source and destination
        plugin_hooks = tmp_path / ".claude" / "plugins" / "autonomous-dev" / "hooks"
        plugin_hooks.mkdir(parents=True)
        (plugin_hooks / "auto_format.py").write_text("# new")

        dest_hooks = tmp_path / ".claude" / "hooks"
        dest_hooks.mkdir(parents=True)
        (dest_hooks / "existing.py").write_text("# old")

        wizard = SetupWizard()
        wizard.copy_plugin_files()

        # Check existing file still there, new file not copied
        assert (dest_hooks / "existing.py").exists()
        assert not (dest_hooks / "auto_format.py").exists()


class TestLoadPreset:
    """Test preset configuration loading."""

    def test_loads_team_preset(self, tmp_path, monkeypatch):
        """Test team preset loads correctly."""
        monkeypatch.chdir(tmp_path)
        wizard = SetupWizard()
        wizard.load_preset("team")

        assert wizard.config["hooks_mode"] == "automatic"
        assert wizard.config["setup_project_md"] is True
        assert wizard.config["setup_github"] is True

    def test_loads_solo_preset(self, tmp_path, monkeypatch):
        """Test solo preset loads correctly."""
        monkeypatch.chdir(tmp_path)
        wizard = SetupWizard()
        wizard.load_preset("solo")

        assert wizard.config["hooks_mode"] == "slash-commands"
        assert wizard.config["setup_project_md"] is True
        assert wizard.config["setup_github"] is False

    def test_loads_minimal_preset(self, tmp_path, monkeypatch):
        """Test minimal preset loads correctly."""
        monkeypatch.chdir(tmp_path)
        wizard = SetupWizard()
        wizard.load_preset("minimal")

        assert wizard.config["hooks_mode"] == "slash-commands"
        assert wizard.config["setup_project_md"] is True
        assert wizard.config["setup_github"] is False

    def test_loads_power_user_preset(self, tmp_path, monkeypatch):
        """Test power-user preset loads correctly."""
        monkeypatch.chdir(tmp_path)
        wizard = SetupWizard()
        wizard.load_preset("power-user")

        assert wizard.config["hooks_mode"] == "automatic"
        assert wizard.config["setup_project_md"] is True
        assert wizard.config["setup_github"] is True

    def test_invalid_preset_exits(self, tmp_path, monkeypatch):
        """Test invalid preset causes exit."""
        monkeypatch.chdir(tmp_path)
        wizard = SetupWizard()

        with pytest.raises(SystemExit):
            wizard.load_preset("invalid-preset")


class TestSetupHooks:
    """Test hooks configuration."""

    def test_slash_commands_mode_no_files(self, tmp_path, monkeypatch):
        """Test slash commands mode doesn't create settings file."""
        monkeypatch.chdir(tmp_path)
        wizard = SetupWizard()
        wizard.config["hooks_mode"] = "slash-commands"
        wizard.setup_hooks()

        settings_file = tmp_path / ".claude" / "settings.local.json"
        assert not settings_file.exists()

    def test_custom_mode_no_files(self, tmp_path, monkeypatch):
        """Test custom mode doesn't create settings file."""
        monkeypatch.chdir(tmp_path)
        wizard = SetupWizard()
        wizard.config["hooks_mode"] = "custom"
        wizard.setup_hooks()

        settings_file = tmp_path / ".claude" / "settings.local.json"
        assert not settings_file.exists()

    def test_automatic_mode_creates_settings(self, tmp_path, monkeypatch):
        """Test automatic mode creates settings.local.json."""
        monkeypatch.chdir(tmp_path)
        (tmp_path / ".claude").mkdir()

        wizard = SetupWizard()
        wizard.config["hooks_mode"] = "automatic"
        wizard.setup_hooks()

        settings_file = tmp_path / ".claude" / "settings.local.json"
        assert settings_file.exists()

        settings = json.loads(settings_file.read_text())
        assert "hooks" in settings
        assert "PostToolUse" in settings["hooks"]
        assert "PreCommit" in settings["hooks"]

    def test_automatic_mode_merges_existing_settings(self, tmp_path, monkeypatch):
        """Test automatic mode merges with existing settings."""
        monkeypatch.chdir(tmp_path)
        (tmp_path / ".claude").mkdir()

        # Create existing settings
        settings_file = tmp_path / ".claude" / "settings.local.json"
        existing = {"custom_key": "custom_value"}
        settings_file.write_text(json.dumps(existing))

        wizard = SetupWizard()
        wizard.config["hooks_mode"] = "automatic"
        wizard.setup_hooks()

        settings = json.loads(settings_file.read_text())
        assert "custom_key" in settings
        assert "hooks" in settings


class TestSetupProjectMd:
    """Test PROJECT.md setup."""

    def test_copies_template_when_requested(self, tmp_path, monkeypatch):
        """Test copies PROJECT.md from template."""
        monkeypatch.chdir(tmp_path)

        # Create template
        templates_dir = tmp_path / ".claude" / "templates"
        templates_dir.mkdir(parents=True)
        template = templates_dir / "PROJECT.md"
        template.write_text("# Template Content")

        wizard = SetupWizard()
        wizard.config["setup_project_md"] = True
        wizard.setup_project_md()

        project_md = tmp_path / ".claude" / "PROJECT.md"
        assert project_md.exists()
        assert project_md.read_text() == "# Template Content"

    def test_skips_when_not_requested(self, tmp_path, monkeypatch):
        """Test doesn't copy when not requested."""
        monkeypatch.chdir(tmp_path)

        wizard = SetupWizard()
        wizard.config["setup_project_md"] = False
        wizard.setup_project_md()

        project_md = tmp_path / ".claude" / "PROJECT.md"
        assert not project_md.exists()

    def test_handles_missing_template(self, tmp_path, monkeypatch, capsys):
        """Test handles missing template gracefully."""
        monkeypatch.chdir(tmp_path)

        wizard = SetupWizard()
        wizard.config["setup_project_md"] = True
        wizard.setup_project_md()

        captured = capsys.readouterr()
        assert "Template not found" in captured.out


class TestSetupGithub:
    """Test GitHub integration setup."""

    def test_creates_env_file_when_requested(self, tmp_path, monkeypatch):
        """Test creates .env file with template."""
        monkeypatch.chdir(tmp_path)

        wizard = SetupWizard()
        wizard.config["setup_github"] = True
        wizard.setup_github()

        env_file = tmp_path / ".env"
        assert env_file.exists()
        content = env_file.read_text()
        assert "GITHUB_TOKEN" in content

    def test_skips_when_not_requested(self, tmp_path, monkeypatch):
        """Test doesn't create .env when not requested."""
        monkeypatch.chdir(tmp_path)

        wizard = SetupWizard()
        wizard.config["setup_github"] = False
        wizard.setup_github()

        env_file = tmp_path / ".env"
        assert not env_file.exists()

    def test_doesnt_overwrite_existing_env(self, tmp_path, monkeypatch):
        """Test doesn't overwrite existing .env file."""
        monkeypatch.chdir(tmp_path)

        # Create existing .env
        env_file = tmp_path / ".env"
        env_file.write_text("EXISTING=value")

        wizard = SetupWizard()
        wizard.config["setup_github"] = True
        wizard.setup_github()

        # Check not overwritten
        assert env_file.read_text() == "EXISTING=value"


class TestCreateGitignoreEntries:
    """Test .gitignore entry creation."""

    def test_creates_gitignore_if_missing(self, tmp_path, monkeypatch):
        """Test creates .gitignore if it doesn't exist."""
        monkeypatch.chdir(tmp_path)

        wizard = SetupWizard()
        wizard.create_gitignore_entries()

        gitignore = tmp_path / ".gitignore"
        assert gitignore.exists()
        content = gitignore.read_text()
        assert ".env" in content
        assert ".claude/settings.local.json" in content

    def test_appends_to_existing_gitignore(self, tmp_path, monkeypatch):
        """Test appends entries to existing .gitignore."""
        monkeypatch.chdir(tmp_path)

        # Create existing .gitignore
        gitignore = tmp_path / ".gitignore"
        gitignore.write_text("existing_entry\n")

        wizard = SetupWizard()
        wizard.create_gitignore_entries()

        content = gitignore.read_text()
        assert "existing_entry" in content
        assert ".env" in content

    def test_skips_existing_entries(self, tmp_path, monkeypatch):
        """Test doesn't duplicate existing entries."""
        monkeypatch.chdir(tmp_path)

        # Create .gitignore with some entries
        gitignore = tmp_path / ".gitignore"
        gitignore.write_text(".env\n")

        wizard = SetupWizard()
        wizard.create_gitignore_entries()

        content = gitignore.read_text()
        # Should only appear once
        assert content.count(".env") == 1


class TestFullWorkflow:
    """Test complete setup workflow."""

    def test_team_preset_workflow(self, tmp_path, monkeypatch):
        """Test complete workflow with team preset."""
        monkeypatch.chdir(tmp_path)

        # Setup plugin structure
        plugin_dir = tmp_path / ".claude" / "plugins" / "autonomous-dev"
        plugin_hooks = plugin_dir / "hooks"
        plugin_hooks.mkdir(parents=True)
        (plugin_hooks / "auto_format.py").write_text("# hook")

        plugin_templates = plugin_dir / "templates"
        plugin_templates.mkdir(parents=True)
        (plugin_templates / "PROJECT.md").write_text("# Template")

        # Run wizard
        wizard = SetupWizard(auto=True, preset="team")
        wizard.run()

        # Verify all files created
        assert (tmp_path / ".claude" / "hooks" / "auto_format.py").exists()
        assert (tmp_path / ".claude" / "templates" / "PROJECT.md").exists()
        assert (tmp_path / ".claude" / "PROJECT.md").exists()
        assert (tmp_path / ".claude" / "settings.local.json").exists()
        assert (tmp_path / ".env").exists()
        assert (tmp_path / ".gitignore").exists()

    def test_solo_preset_workflow(self, tmp_path, monkeypatch):
        """Test complete workflow with solo preset."""
        monkeypatch.chdir(tmp_path)

        # Setup plugin structure
        plugin_dir = tmp_path / ".claude" / "plugins" / "autonomous-dev"
        plugin_hooks = plugin_dir / "hooks"
        plugin_hooks.mkdir(parents=True)

        plugin_templates = plugin_dir / "templates"
        plugin_templates.mkdir(parents=True)
        (plugin_templates / "PROJECT.md").write_text("# Template")

        # Run wizard
        wizard = SetupWizard(auto=True, preset="solo")
        wizard.run()

        # Verify slash commands mode (no settings.local.json)
        assert not (tmp_path / ".claude" / "settings.local.json").exists()
        # But PROJECT.md created
        assert (tmp_path / ".claude" / "PROJECT.md").exists()
        # No GitHub
        assert not (tmp_path / ".env").exists()
