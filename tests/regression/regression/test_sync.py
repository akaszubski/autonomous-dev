#!/usr/bin/env python3
"""
Consolidated Sync Tests (TDD Red Phase)

Tests for sync_dispatcher.py functionality:
- Settings merge integration (marketplace sync)
- Version detection (upgrade/downgrade)
- Orphan cleanup integration
- Non-blocking behavior (graceful degradation)
- Security validation

Date: 2025-11-08 (consolidated 2025-12-16)
Issues: #50 (Marketplace UX), #97 (New files sync)
"""

import json
import os
import sys
import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock

# Add plugins directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent / "plugins"))
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

# Import sync components - skip if not available
try:
    from autonomous_dev.lib.sync_dispatcher import SyncDispatcher, SyncResult
    from autonomous_dev.lib.settings_merger import SettingsMerger, MergeResult
    from autonomous_dev.lib.sync_mode_detector import SyncMode
    from autonomous_dev.lib.version_detector import VersionComparison
    from autonomous_dev.lib.orphan_file_cleaner import CleanupResult
    from plugins.autonomous_dev.lib.sync_dispatcher import (
        SyncDispatcher as PluginSyncDispatcher,
        SyncResult as PluginSyncResult,
        SyncError,
        sync_marketplace,
    )
    SYNC_AVAILABLE = True
except ImportError as e:
    SYNC_AVAILABLE = False


# =============================================================================
# Fixtures
# =============================================================================

@pytest.fixture
def temp_project_root(tmp_path):
    """Create temporary project root for testing."""
    project_root = tmp_path / "test_project"
    project_root.mkdir()
    (project_root / ".claude").mkdir()
    (project_root / ".claude" / "hooks").mkdir()
    return str(project_root)


@pytest.fixture
def mock_plugin_root(tmp_path):
    """Create mock plugin root with templates and installed_plugins.json."""
    plugin_root = tmp_path / "plugins" / "autonomous-dev"
    plugin_root.mkdir(parents=True)

    # Create plugin.json
    (plugin_root / "plugin.json").write_text(json.dumps({
        "name": "autonomous-dev", "version": "1.0.0"
    }, indent=2))

    # Create directories
    (plugin_root / "commands").mkdir(exist_ok=True)
    (plugin_root / "hooks").mkdir(exist_ok=True)
    (plugin_root / "agents").mkdir(exist_ok=True)

    # Create template settings.local.json
    templates_dir = plugin_root / "templates"
    templates_dir.mkdir()
    template_data = {
        "hooks": {
            "PreToolUse": [{"type": "command", "command": "python3 pre_tool_use.py", "timeout": 5}],
            "PostToolUse": [{"type": "command", "command": "python3 auto_format.py"}]
        }
    }
    (templates_dir / "settings.local.json").write_text(json.dumps(template_data, indent=2))

    # Create installed_plugins.json
    plugins_config_dir = tmp_path / ".claude" / "plugins"
    plugins_config_dir.mkdir(parents=True, exist_ok=True)
    installed_plugins_json = plugins_config_dir / "installed_plugins.json"
    installed_plugins_data = {
        "autonomous-dev": {"name": "autonomous-dev", "path": str(plugin_root), "version": "1.0.0"}
    }
    installed_plugins_json.write_text(json.dumps(installed_plugins_data, indent=2))

    return installed_plugins_json


@pytest.fixture
def existing_user_settings(temp_project_root):
    """Create existing user settings with custom configuration."""
    user_settings_path = Path(temp_project_root) / ".claude" / "settings.local.json"
    user_data = {
        "hooks": {"PreCommit": [{"type": "command", "command": "python3 custom_hook.py"}]},
        "permissions": {"allow": ["Read(**)"]}
    }
    user_settings_path.write_text(json.dumps(user_data, indent=2))
    return user_settings_path


@pytest.fixture
def temp_environment(tmp_path):
    """Create full test environment with marketplace and project."""
    project_root = tmp_path / "project"
    project_root.mkdir()
    (project_root / ".claude").mkdir()
    (project_root / ".claude" / "plugins").mkdir()
    (project_root / ".claude" / "plugins" / "autonomous-dev").mkdir()

    marketplace_dir = tmp_path / "marketplace"
    marketplace_dir.mkdir()
    (marketplace_dir / ".claude").mkdir()
    (marketplace_dir / ".claude" / "plugins").mkdir()

    return {"project_root": project_root, "marketplace_dir": marketplace_dir}


# =============================================================================
# Settings Merge Tests
# =============================================================================

@pytest.mark.skipif(not SYNC_AVAILABLE, reason="Sync modules not available")
class TestSettingsMerge:
    """Test settings merge integration in marketplace sync."""

    def test_marketplace_sync_merges_settings_on_first_install(self, temp_project_root, mock_plugin_root):
        """Test marketplace sync merges settings.local.json on first install."""
        dispatcher = SyncDispatcher(temp_project_root)
        with patch.object(dispatcher, '_sync_directory') as mock_sync:
            mock_sync.return_value = 0
            result = dispatcher.sync_marketplace(mock_plugin_root)

        assert result.success is True
        settings_path = Path(temp_project_root) / ".claude" / "settings.local.json"
        assert settings_path.exists()

    def test_marketplace_sync_preserves_user_hooks(self, temp_project_root, mock_plugin_root, existing_user_settings):
        """Test marketplace sync preserves existing user hooks."""
        existing_data = json.loads(existing_user_settings.read_text())
        assert "PreCommit" in existing_data["hooks"]

        dispatcher = SyncDispatcher(temp_project_root)
        with patch.object(dispatcher, '_sync_directory') as mock_sync:
            mock_sync.return_value = 0
            result = dispatcher.sync_marketplace(mock_plugin_root)

        assert result.success is True
        merged_data = json.loads(existing_user_settings.read_text())
        assert "PreCommit" in merged_data["hooks"]


# =============================================================================
# Version Detection Tests
# =============================================================================

@pytest.mark.skipif(not SYNC_AVAILABLE, reason="Sync modules not available")
class TestVersionDetection:
    """Test version detection during marketplace sync."""

    def test_marketplace_sync_detects_version_upgrade(self, temp_environment):
        """Test marketplace sync detects when marketplace has newer version."""
        project_root = temp_environment["project_root"]
        marketplace_dir = temp_environment["marketplace_dir"]

        # Setup versions
        project_plugin = project_root / ".claude" / "plugins" / "autonomous-dev" / "plugin.json"
        project_plugin.write_text(json.dumps({"name": "autonomous-dev", "version": "3.7.0"}))

        marketplace_plugins = marketplace_dir / ".claude" / "plugins" / "installed_plugins.json"
        marketplace_plugins.write_text(json.dumps({
            "autonomous-dev": {"version": "3.8.0", "source": "marketplace",
                              "path": str(marketplace_dir / ".claude" / "plugins" / "autonomous-dev")}
        }))

        marketplace_plugin_dir = marketplace_dir / ".claude" / "plugins" / "autonomous-dev"
        marketplace_plugin_dir.mkdir(parents=True)
        (marketplace_plugin_dir / "plugin.json").write_text(
            json.dumps({"name": "autonomous-dev", "version": "3.8.0"}))

        dispatcher = PluginSyncDispatcher(project_root=project_root)
        result = dispatcher.sync_marketplace(marketplace_plugins_file=marketplace_plugins)

        assert result.success is True
        assert result.version_comparison is not None

    def test_version_detection_failure_non_blocking(self, temp_environment):
        """Test sync succeeds even when version detection fails."""
        project_root = temp_environment["project_root"]
        marketplace_dir = temp_environment["marketplace_dir"]

        # Setup with invalid plugin.json
        marketplace_plugins = marketplace_dir / ".claude" / "plugins" / "installed_plugins.json"
        marketplace_plugins.write_text(json.dumps({
            "autonomous-dev": {"version": "3.8.0", "source": "marketplace",
                              "path": str(marketplace_dir / ".claude" / "plugins" / "autonomous-dev")}
        }))

        marketplace_plugin_dir = marketplace_dir / ".claude" / "plugins" / "autonomous-dev"
        marketplace_plugin_dir.mkdir(parents=True)
        (marketplace_plugin_dir / "plugin.json").write_text("invalid json")
        (marketplace_plugin_dir / "commands").mkdir()
        (marketplace_plugin_dir / "commands" / "test.md").write_text("# Test")

        dispatcher = PluginSyncDispatcher(project_root=project_root)
        result = dispatcher.sync_marketplace(marketplace_plugins_file=marketplace_plugins)

        # Sync should succeed despite version detection failure
        assert result.success is True


# =============================================================================
# Orphan Cleanup Tests
# =============================================================================

@pytest.mark.skipif(not SYNC_AVAILABLE, reason="Sync modules not available")
class TestOrphanCleanup:
    """Test orphan cleanup integration in marketplace sync."""

    @pytest.fixture
    def temp_project_with_orphans(self, tmp_path):
        """Create project with orphaned files after version upgrade."""
        project_root = tmp_path / "project"
        project_root.mkdir()
        (project_root / ".claude").mkdir()
        (project_root / ".claude" / "commands").mkdir()
        (project_root / ".claude" / "plugins").mkdir()
        (project_root / ".claude" / "plugins" / "autonomous-dev").mkdir()

        # Create orphaned command file
        (project_root / ".claude" / "commands" / "old-command.md").write_text("# Old Command")

        # Setup marketplace
        marketplace_dir = tmp_path / "marketplace"
        marketplace_dir.mkdir()
        (marketplace_dir / ".claude").mkdir()
        (marketplace_dir / ".claude" / "plugins").mkdir()

        marketplace_plugins = marketplace_dir / ".claude" / "plugins" / "installed_plugins.json"
        marketplace_plugins.write_text(json.dumps({
            "autonomous-dev": {"version": "3.8.0", "source": "marketplace",
                              "path": str(marketplace_dir / ".claude" / "plugins" / "autonomous-dev")}
        }))

        marketplace_plugin_dir = marketplace_dir / ".claude" / "plugins" / "autonomous-dev"
        marketplace_plugin_dir.mkdir(parents=True)
        (marketplace_plugin_dir / "plugin.json").write_text(
            json.dumps({"name": "autonomous-dev", "version": "3.8.0", "commands": ["auto-implement.md"]}))

        return {
            "project_root": project_root,
            "marketplace_plugins": marketplace_plugins,
            "orphan_file": project_root / ".claude" / "commands" / "old-command.md"
        }

    def test_marketplace_sync_skip_orphan_cleanup_when_disabled(self, temp_project_with_orphans):
        """Test marketplace sync skips orphan cleanup when disabled."""
        project_root = temp_project_with_orphans["project_root"]
        marketplace_plugins = temp_project_with_orphans["marketplace_plugins"]

        dispatcher = PluginSyncDispatcher(project_root=project_root)
        result = dispatcher.sync_marketplace(marketplace_plugins_file=marketplace_plugins, cleanup_orphans=False)

        assert result.orphan_cleanup is None


# =============================================================================
# Error Handling Tests
# =============================================================================

@pytest.mark.skipif(not SYNC_AVAILABLE, reason="Sync modules not available")
class TestErrorHandling:
    """Test error handling for marketplace sync failures."""

    def test_marketplace_not_installed_error(self, tmp_path):
        """Test error when marketplace plugin not installed."""
        project_root = tmp_path / "project"
        project_root.mkdir()
        (project_root / ".claude").mkdir()
        (project_root / ".claude" / "plugins").mkdir()

        dispatcher = PluginSyncDispatcher(project_root=project_root)
        result = dispatcher.sync_marketplace(marketplace_plugins_file=Path("/nonexistent/installed_plugins.json"))

        assert result.success is False

    def test_corrupted_marketplace_json_error(self, tmp_path):
        """Test error when marketplace plugin.json is corrupted."""
        project_root = tmp_path / "project"
        project_root.mkdir()
        (project_root / ".claude").mkdir()
        (project_root / ".claude" / "plugins").mkdir()

        marketplace_dir = tmp_path / "marketplace"
        marketplace_dir.mkdir()
        (marketplace_dir / ".claude").mkdir()
        (marketplace_dir / ".claude" / "plugins").mkdir()

        marketplace_plugins = marketplace_dir / ".claude" / "plugins" / "installed_plugins.json"
        marketplace_plugins.write_text("{ corrupted json content")

        dispatcher = PluginSyncDispatcher(project_root=project_root)
        result = dispatcher.sync_marketplace(marketplace_plugins_file=marketplace_plugins)

        assert result.success is False


# =============================================================================
# Security Tests
# =============================================================================

@pytest.mark.skipif(not SYNC_AVAILABLE, reason="Sync modules not available")
class TestSecurity:
    """Test security controls in marketplace sync."""

    def test_path_traversal_blocked(self, tmp_path):
        """Test path traversal attacks blocked in marketplace sync."""
        project_root = tmp_path / "project"
        project_root.mkdir()
        (project_root / ".claude").mkdir()

        malicious_marketplace = project_root / ".." / ".." / "etc" / "passwd"

        dispatcher = PluginSyncDispatcher(project_root=project_root)
        result = dispatcher.sync_marketplace(marketplace_plugins_file=malicious_marketplace)

        assert result.success is False

    def test_only_claude_directories_modified(self, tmp_path):
        """Test marketplace sync only modifies .claude/ directories."""
        project_root = tmp_path / "project"
        project_root.mkdir()
        (project_root / ".claude").mkdir()

        user_file = project_root / "important.txt"
        user_file.write_text("Important data")

        marketplace_dir = project_root.parent / "marketplace"
        marketplace_dir.mkdir()
        (marketplace_dir / ".claude").mkdir()
        (marketplace_dir / ".claude" / "plugins").mkdir()

        marketplace_plugins = marketplace_dir / ".claude" / "plugins" / "installed_plugins.json"
        marketplace_plugins.write_text(json.dumps({
            "autonomous-dev": {"version": "3.8.0", "source": "marketplace",
                              "path": str(marketplace_dir / ".claude" / "plugins" / "autonomous-dev")}
        }))

        dispatcher = PluginSyncDispatcher(project_root=project_root)
        try:
            dispatcher.sync_marketplace(marketplace_plugins_file=marketplace_plugins)
        except Exception:
            pass

        # User file should be unchanged
        assert user_file.read_text() == "Important data"


# =============================================================================
# Non-Blocking Behavior Tests
# =============================================================================

@pytest.mark.skipif(not SYNC_AVAILABLE, reason="Sync modules not available")
class TestNonBlockingBehavior:
    """Test non-blocking behavior for sync operations."""

    def test_marketplace_sync_succeeds_when_settings_merge_fails(self, temp_project_root, mock_plugin_root):
        """Test marketplace sync succeeds even when settings merge fails."""
        dispatcher = SyncDispatcher(temp_project_root)

        # Patch SettingsMerger where it's actually imported (in dispatcher.py)
        with patch('autonomous_dev.lib.sync_dispatcher.dispatcher.SettingsMerger') as MockMerger:
            mock_instance = MagicMock()
            mock_instance.merge_settings.return_value = MergeResult(
                success=False, message="Mock merge failure", hooks_added=0, hooks_preserved=0
            )
            MockMerger.return_value = mock_instance

            with patch.object(dispatcher, '_sync_directory') as mock_sync:
                mock_sync.return_value = 0
                result = dispatcher.sync_marketplace(mock_plugin_root)

        # Sync should still succeed (non-blocking)
        assert result.success is True

    def test_marketplace_sync_succeeds_when_template_missing(self, temp_project_root, tmp_path):
        """Test marketplace sync succeeds when template settings.local.json doesn't exist."""
        # Create plugin root without template file
        plugin_root = tmp_path / "plugins" / "autonomous-dev"
        plugin_root.mkdir(parents=True)
        (plugin_root / "plugin.json").write_text(json.dumps({"name": "autonomous-dev", "version": "1.0.0"}))
        (plugin_root / "commands").mkdir(exist_ok=True)
        (plugin_root / "hooks").mkdir(exist_ok=True)
        (plugin_root / "agents").mkdir(exist_ok=True)
        (plugin_root / "templates").mkdir()  # No settings.local.json

        plugins_config_dir = tmp_path / ".claude" / "plugins"
        plugins_config_dir.mkdir(parents=True, exist_ok=True)
        installed_plugins_json = plugins_config_dir / "installed_plugins.json"
        installed_plugins_json.write_text(json.dumps({
            "autonomous-dev": {"name": "autonomous-dev", "path": str(plugin_root), "version": "1.0.0"}
        }))

        dispatcher = SyncDispatcher(temp_project_root)
        with patch.object(dispatcher, '_sync_directory') as mock_sync:
            mock_sync.return_value = 0
            result = dispatcher.sync_marketplace(installed_plugins_json)

        # Should still succeed (template is optional)
        assert result.success is True


# =============================================================================
# SyncResult Tests
# =============================================================================

@pytest.mark.skipif(not SYNC_AVAILABLE, reason="Sync modules not available")
class TestSyncResult:
    """Test SyncResult enhancements for marketplace sync."""

    def test_sync_result_includes_settings_merge_status(self, temp_project_root, mock_plugin_root, existing_user_settings):
        """Test SyncResult includes MergeResult in settings_merged field."""
        dispatcher = SyncDispatcher(temp_project_root)

        with patch.object(dispatcher, '_sync_directory') as mock_sync:
            mock_sync.return_value = 0
            result = dispatcher.sync_marketplace(mock_plugin_root)

        assert result.success is True
        assert hasattr(result, 'settings_merged')

    def test_sync_result_includes_version_comparison(self):
        """Test SyncResult can include version comparison data."""
        version_comparison = VersionComparison(
            status=VersionComparison.UPGRADE_AVAILABLE,
            project_version="3.7.0",
            marketplace_version="3.8.0"
        )

        result = PluginSyncResult(
            success=True,
            mode=SyncMode.MARKETPLACE,
            message="Marketplace sync completed",
            version_comparison=version_comparison
        )

        assert result.version_comparison is not None
        assert result.version_comparison.project_version == "3.7.0"


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=line", "-q"])
