#!/usr/bin/env python3
"""
TDD Tests for /sync Command Integration (FAILING - Red Phase)

This module contains FAILING integration tests for the unified /sync command
that consolidates /sync-dev and /update-plugin functionality.

Requirements:
1. /sync command appears in plugin.json commands list
2. Old commands (/sync-dev, /update-plugin) moved to archived/
3. /sync command auto-detects context correctly
4. Flag overrides (--env, --marketplace, --plugin-dev, --all) work
5. Integration with sync-validator agent for environment mode

Test Coverage Target: Full integration workflow coverage

Following TDD principles:
- Write tests FIRST (red phase)
- Tests describe integration requirements
- Tests should FAIL until /sync command is implemented
- Each test validates ONE integration aspect

Author: test-master agent
Date: 2025-11-08
Issue: GitHub #44 - Unified /sync command consolidation
"""

import json
import os
import sys
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock

import pytest

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from plugins.autonomous_dev.lib.sync_mode_detector import SyncMode


class TestPluginJsonConfiguration:
    """Test that plugin.json is updated correctly for /sync command."""

    @pytest.fixture
    def plugin_json_path(self):
        """Get path to plugin.json."""
        plugin_dir = Path(__file__).parent.parent.parent / "plugins" / "autonomous-dev"
        return plugin_dir / "plugin.json"

    def test_sync_command_in_plugin_json(self, plugin_json_path):
        """Test that /sync command is listed in plugin.json.

        REQUIREMENT: New unified command must be registered.
        Expected: "sync" in commands list.
        """
        with open(plugin_json_path, 'r') as f:
            plugin_config = json.load(f)

        commands = plugin_config.get('commands', [])

        # Should contain /sync command
        assert '/sync' in commands or 'sync' in commands

    def test_old_commands_removed_from_plugin_json(self, plugin_json_path):
        """Test that old /sync-dev and /update-plugin are removed from active commands.

        REQUIREMENT: Deprecated commands should not be in active list.
        Expected: /sync-dev and /update-plugin NOT in commands.
        """
        with open(plugin_json_path, 'r') as f:
            plugin_config = json.load(f)

        commands = plugin_config.get('commands', [])

        # Old commands should be removed
        assert '/sync-dev' not in commands
        assert '/update-plugin' not in commands
        assert 'sync-dev' not in commands
        assert 'update-plugin' not in commands

    def test_plugin_json_version_incremented(self, plugin_json_path):
        """Test that plugin.json version is incremented for this change.

        REQUIREMENT: Breaking change requires version bump.
        Expected: Version >= 3.7.0 (post 3.6.0).
        """
        with open(plugin_json_path, 'r') as f:
            plugin_config = json.load(f)

        version = plugin_config.get('version', '0.0.0')
        major, minor, patch = map(int, version.split('.'))

        # Version should be at least 3.7.0 (or 4.0.0 if breaking change)
        assert (major >= 4) or (major == 3 and minor >= 7)


class TestCommandFileStructure:
    """Test that command files are organized correctly."""

    @pytest.fixture
    def commands_dir(self):
        """Get path to commands directory."""
        return Path(__file__).parent.parent.parent / "plugins" / "autonomous-dev" / "commands"

    @pytest.fixture
    def archived_dir(self):
        """Get path to archived commands directory."""
        return Path(__file__).parent.parent.parent / "plugins" / "autonomous-dev" / "commands" / "archived"

    def test_sync_command_file_exists(self, commands_dir):
        """Test that sync.md command file exists.

        REQUIREMENT: Command requires markdown file.
        Expected: commands/sync.md exists.
        """
        sync_command = commands_dir / "sync.md"
        assert sync_command.exists()

    def test_sync_command_has_frontmatter(self, commands_dir):
        """Test that sync.md has required frontmatter.

        REQUIREMENT: Claude Code requires frontmatter with description.
        Expected: File starts with --- and contains description.
        """
        sync_command = commands_dir / "sync.md"

        if sync_command.exists():
            content = sync_command.read_text()
            assert content.startswith('---')
            assert 'description:' in content

    def test_old_commands_archived(self, archived_dir):
        """Test that old command files moved to archived/ directory.

        REQUIREMENT: Preserve old commands for reference.
        Expected: sync-dev.md and update-plugin.md in archived/.
        """
        assert archived_dir.exists()

        old_sync_dev = archived_dir / "sync-dev.md"
        old_update_plugin = archived_dir / "update-plugin.md"

        assert old_sync_dev.exists()
        assert old_update_plugin.exists()

    def test_archived_commands_have_deprecation_notice(self, archived_dir):
        """Test that archived commands include deprecation notice.

        REQUIREMENT: Users should know command is deprecated.
        Expected: Deprecation notice in archived command files.
        """
        old_sync_dev = archived_dir / "sync-dev.md"

        if old_sync_dev.exists():
            content = old_sync_dev.read_text()
            assert 'deprecated' in content.lower() or 'replaced' in content.lower()
            assert '/sync' in content  # Should mention replacement


class TestAutoContextDetection:
    """Test that /sync command auto-detects context correctly."""

    @pytest.fixture
    def temp_plugin_dev_project(self, tmp_path):
        """Create plugin development project structure."""
        project_root = tmp_path / "plugin_dev"
        project_root.mkdir()

        # Create plugin directory
        plugin_dir = project_root / "plugins" / "autonomous-dev"
        plugin_dir.mkdir(parents=True)
        (plugin_dir / "plugin.json").write_text('{"version": "3.6.0"}')

        return project_root

    @pytest.fixture
    def temp_environment_project(self, tmp_path):
        """Create normal project with .claude directory."""
        project_root = tmp_path / "env_project"
        project_root.mkdir()

        # Create .claude directory
        claude_dir = project_root / ".claude"
        claude_dir.mkdir()
        (claude_dir / "PROJECT.md").write_text("# Project")

        return project_root

    def test_auto_detect_plugin_dev_context(self, temp_plugin_dev_project):
        """Test /sync auto-detects plugin development mode.

        REQUIREMENT: Smart context detection for developer convenience.
        Expected: Automatically uses PLUGIN_DEV mode when plugin dir exists.
        """
        from plugins.autonomous_dev.lib.sync_mode_detector import detect_sync_mode

        mode = detect_sync_mode(str(temp_plugin_dev_project))

        assert mode == SyncMode.PLUGIN_DEV

    def test_auto_detect_environment_context(self, temp_environment_project):
        """Test /sync auto-detects environment mode.

        REQUIREMENT: Default to environment sync for normal projects.
        Expected: Automatically uses ENVIRONMENT mode when .claude exists.
        """
        from plugins.autonomous_dev.lib.sync_mode_detector import detect_sync_mode

        mode = detect_sync_mode(str(temp_environment_project))

        assert mode == SyncMode.ENVIRONMENT

    def test_sync_command_uses_auto_detection_by_default(self, temp_environment_project):
        """Test that /sync command leverages auto-detection when no flags provided.

        REQUIREMENT: Zero-config experience for common case.
        Expected: Running /sync with no args auto-detects mode.
        """
        with patch('plugins.autonomous_dev.lib.sync_dispatcher.SyncDispatcher') as mock_dispatcher:
            mock_instance = Mock()
            mock_instance.dispatch.return_value = Mock(success=True)
            mock_dispatcher.return_value = mock_instance

            # Simulate running /sync command (implementation would call detect + dispatch)
            from plugins.autonomous_dev.lib.sync_mode_detector import detect_sync_mode
            from plugins.autonomous_dev.lib.sync_dispatcher import dispatch_sync

            mode = detect_sync_mode(str(temp_environment_project))
            result = dispatch_sync(str(temp_environment_project), mode)

            # Should have auto-detected ENVIRONMENT
            assert mode == SyncMode.ENVIRONMENT


class TestFlagOverrides:
    """Test that command-line flags override auto-detection."""

    @pytest.fixture
    def temp_plugin_dev_project(self, tmp_path):
        """Create plugin dev project (would auto-detect as PLUGIN_DEV)."""
        project_root = tmp_path / "plugin_dev"
        project_root.mkdir()

        plugin_dir = project_root / "plugins" / "autonomous-dev"
        plugin_dir.mkdir(parents=True)
        (plugin_dir / "plugin.json").write_text('{}')

        return project_root

    def test_env_flag_overrides_auto_detection(self, temp_plugin_dev_project):
        """Test that --env flag forces environment mode.

        REQUIREMENT: Allow explicit mode override.
        Expected: --env uses ENVIRONMENT even in plugin dev project.
        """
        from plugins.autonomous_dev.lib.sync_mode_detector import parse_sync_flags

        # Auto-detect would return PLUGIN_DEV, but flag overrides
        mode = parse_sync_flags(['--env'])

        assert mode == SyncMode.ENVIRONMENT

    def test_marketplace_flag_overrides_auto_detection(self, temp_plugin_dev_project):
        """Test that --marketplace flag forces marketplace mode.

        REQUIREMENT: Allow explicit marketplace sync.
        Expected: --marketplace uses MARKETPLACE mode.
        """
        from plugins.autonomous_dev.lib.sync_mode_detector import parse_sync_flags

        mode = parse_sync_flags(['--marketplace'])

        assert mode == SyncMode.MARKETPLACE

    def test_plugin_dev_flag_explicit(self, temp_plugin_dev_project):
        """Test that --plugin-dev flag explicitly sets plugin dev mode.

        REQUIREMENT: Allow explicit plugin dev sync.
        Expected: --plugin-dev uses PLUGIN_DEV mode.
        """
        from plugins.autonomous_dev.lib.sync_mode_detector import parse_sync_flags

        mode = parse_sync_flags(['--plugin-dev'])

        assert mode == SyncMode.PLUGIN_DEV

    def test_all_flag_enables_all_modes(self, temp_plugin_dev_project):
        """Test that --all flag enables comprehensive sync.

        REQUIREMENT: Single command to sync everything.
        Expected: --all uses ALL mode (env + marketplace + plugin-dev).
        """
        from plugins.autonomous_dev.lib.sync_mode_detector import parse_sync_flags

        mode = parse_sync_flags(['--all'])

        assert mode == SyncMode.ALL


class TestSyncValidatorIntegration:
    """Test integration with sync-validator agent for environment mode."""

    @pytest.fixture
    def temp_project(self, tmp_path):
        """Create test project."""
        project_root = tmp_path / "test_project"
        project_root.mkdir()
        (project_root / ".claude").mkdir()
        return project_root

    def test_environment_mode_invokes_sync_validator_agent(self, temp_project):
        """Test that environment sync delegates to sync-validator agent.

        REQUIREMENT: Reuse existing sync-validator logic.
        Expected: sync-validator agent invoked for ENVIRONMENT mode.
        """
        from plugins.autonomous_dev.lib.sync_dispatcher import SyncDispatcher

        with patch('plugins.autonomous_dev.lib.sync_dispatcher.AgentInvoker') as mock_invoker:
            mock_instance = Mock()
            mock_instance.invoke.return_value = {"status": "success"}
            mock_invoker.return_value = mock_instance

            dispatcher = SyncDispatcher(str(temp_project))
            result = dispatcher.dispatch(SyncMode.ENVIRONMENT)

            # Verify agent was invoked
            mock_instance.invoke.assert_called()

    def test_sync_passes_project_context_to_agent(self, temp_project):
        """Test that sync command passes project context to sync-validator.

        REQUIREMENT: Agent needs project path for validation.
        Expected: Project path included in agent invocation.
        """
        from plugins.autonomous_dev.lib.sync_dispatcher import SyncDispatcher

        with patch('plugins.autonomous_dev.lib.sync_dispatcher.AgentInvoker') as mock_invoker:
            mock_instance = Mock()
            mock_instance.invoke.return_value = {"status": "success"}
            mock_invoker.return_value = mock_instance

            dispatcher = SyncDispatcher(str(temp_project))
            result = dispatcher.dispatch(SyncMode.ENVIRONMENT)

            # Verify project path was passed
            call_args = mock_instance.invoke.call_args
            assert str(temp_project) in str(call_args)


class TestBackwardCompatibility:
    """Test backward compatibility considerations."""

    def test_sync_dev_command_shows_deprecation_message(self):
        """Test that old /sync-dev command shows deprecation notice.

        REQUIREMENT: Inform users of new command.
        Expected: Deprecation message points to /sync.
        """
        # This would test the archived sync-dev.md file
        archived_path = Path(__file__).parent.parent.parent / "plugins" / "autonomous-dev" / "commands" / "archived" / "sync-dev.md"

        if archived_path.exists():
            content = archived_path.read_text()

            # Should mention deprecation and replacement
            assert 'deprecated' in content.lower() or 'replaced' in content.lower()
            assert '/sync' in content

    def test_update_plugin_command_shows_deprecation_message(self):
        """Test that old /update-plugin command shows deprecation notice.

        REQUIREMENT: Guide users to new unified command.
        Expected: Deprecation message explains /sync --marketplace.
        """
        archived_path = Path(__file__).parent.parent.parent / "plugins" / "autonomous-dev" / "commands" / "archived" / "update-plugin.md"

        if archived_path.exists():
            content = archived_path.read_text()

            assert 'deprecated' in content.lower() or 'replaced' in content.lower()
            assert '/sync' in content
            assert '--marketplace' in content


class TestEndToEndWorkflow:
    """Test end-to-end /sync command workflows."""

    @pytest.fixture
    def temp_complete_project(self, tmp_path):
        """Create complete project with all contexts."""
        project_root = tmp_path / "complete_project"
        project_root.mkdir()

        # Environment context
        claude_dir = project_root / ".claude"
        claude_dir.mkdir()
        (claude_dir / "PROJECT.md").write_text("# Project")

        # Plugin dev context
        plugin_dir = project_root / "plugins" / "autonomous-dev"
        plugin_dir.mkdir(parents=True)
        (plugin_dir / "plugin.json").write_text('{"version": "3.6.0"}')

        return project_root

    def test_sync_command_no_args_auto_detects_and_syncs(self, temp_complete_project):
        """Test complete workflow: /sync with no args auto-detects and syncs.

        REQUIREMENT: Zero-config sync experience.
        Expected: Auto-detect → dispatch → return result.
        """
        from plugins.autonomous_dev.lib.sync_mode_detector import detect_sync_mode
        from plugins.autonomous_dev.lib.sync_dispatcher import dispatch_sync

        # Would auto-detect PLUGIN_DEV (plugin dir has precedence)
        mode = detect_sync_mode(str(temp_complete_project))
        assert mode == SyncMode.PLUGIN_DEV

        # Dispatch would execute sync
        with patch('plugins.autonomous_dev.lib.sync_dispatcher.shutil.copytree'):
            result = dispatch_sync(str(temp_complete_project), mode)

        # Should complete without error
        assert result is not None

    def test_sync_command_with_env_flag_forces_environment_sync(self, temp_complete_project):
        """Test workflow: /sync --env forces environment sync despite plugin dir.

        REQUIREMENT: Flag override for explicit control.
        Expected: --env → ENVIRONMENT mode → sync-validator agent.
        """
        from plugins.autonomous_dev.lib.sync_mode_detector import parse_sync_flags
        from plugins.autonomous_dev.lib.sync_dispatcher import dispatch_sync

        # Parse flag
        mode = parse_sync_flags(['--env'])
        assert mode == SyncMode.ENVIRONMENT

        # Dispatch environment sync
        with patch('plugins.autonomous_dev.lib.sync_dispatcher.AgentInvoker') as mock_invoker:
            mock_instance = Mock()
            mock_instance.invoke.return_value = {"status": "success"}
            mock_invoker.return_value = mock_instance

            result = dispatch_sync(str(temp_complete_project), mode)

            # Agent should have been invoked
            mock_instance.invoke.assert_called()

    def test_sync_command_with_all_flag_syncs_everything(self, temp_complete_project):
        """Test workflow: /sync --all executes all sync modes.

        REQUIREMENT: Comprehensive sync in single command.
        Expected: --all → ALL mode → env + marketplace + plugin-dev.
        """
        from plugins.autonomous_dev.lib.sync_mode_detector import parse_sync_flags
        from plugins.autonomous_dev.lib.sync_dispatcher import SyncDispatcher

        # Parse flag
        mode = parse_sync_flags(['--all'])
        assert mode == SyncMode.ALL

        # Dispatch all modes
        with patch.object(SyncDispatcher, '_sync_environment') as mock_env, \
             patch.object(SyncDispatcher, '_sync_marketplace') as mock_market, \
             patch.object(SyncDispatcher, '_sync_plugin_dev') as mock_plugin:

            from plugins.autonomous_dev.lib.sync_dispatcher import SyncResult

            mock_env.return_value = SyncResult(True, SyncMode.ENVIRONMENT, "Success")
            mock_market.return_value = SyncResult(True, SyncMode.MARKETPLACE, "Success")
            mock_plugin.return_value = SyncResult(True, SyncMode.PLUGIN_DEV, "Success")

            dispatcher = SyncDispatcher(str(temp_complete_project))
            result = dispatcher.dispatch(mode)

            # All three should have been called
            assert mock_env.call_count == 1
            assert mock_market.call_count == 1
            assert mock_plugin.call_count == 1


class TestCommandDocumentation:
    """Test that /sync command has proper documentation."""

    @pytest.fixture
    def sync_command_path(self):
        """Get path to sync command markdown file."""
        return Path(__file__).parent.parent.parent / "plugins" / "autonomous-dev" / "commands" / "sync.md"

    def test_sync_command_documents_all_flags(self, sync_command_path):
        """Test that sync.md documents all available flags.

        REQUIREMENT: Complete documentation for users.
        Expected: --env, --marketplace, --plugin-dev, --all documented.
        """
        if sync_command_path.exists():
            content = sync_command_path.read_text()

            assert '--env' in content
            assert '--marketplace' in content
            assert '--plugin-dev' in content
            assert '--all' in content

    def test_sync_command_explains_auto_detection(self, sync_command_path):
        """Test that sync.md explains auto-detection behavior.

        REQUIREMENT: Users should understand how mode is chosen.
        Expected: Documentation explains auto-detection logic.
        """
        if sync_command_path.exists():
            content = sync_command_path.read_text()

            assert 'auto-detect' in content.lower() or 'automatic' in content.lower()

    def test_sync_command_provides_examples(self, sync_command_path):
        """Test that sync.md includes usage examples.

        REQUIREMENT: Examples help users understand command.
        Expected: Multiple usage examples in documentation.
        """
        if sync_command_path.exists():
            content = sync_command_path.read_text()

            # Should have example section
            assert 'example' in content.lower() or 'usage' in content.lower()
            # Should show actual command invocations
            assert '/sync' in content

    def test_sync_command_references_old_commands(self, sync_command_path):
        """Test that sync.md mentions migration from old commands.

        REQUIREMENT: Help users migrate from /sync-dev and /update-plugin.
        Expected: Migration guide in documentation.
        """
        if sync_command_path.exists():
            content = sync_command_path.read_text()

            assert '/sync-dev' in content or 'sync-dev' in content
            assert '/update-plugin' in content or 'update-plugin' in content
