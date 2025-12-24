"""
Unit tests for sync_dispatcher.py settings merge integration - TDD Red Phase

Tests the integration of SettingsMerger into sync_dispatcher.py for
marketplace sync operations.

Expected to FAIL until implementation is complete.
"""

import json
import sys
import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock, call

# Add plugins directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent / "plugins"))

# Import will fail until implementation exists
try:
    from autonomous_dev.lib.sync_dispatcher import SyncDispatcher, SyncResult
    from autonomous_dev.lib.settings_merger import SettingsMerger, MergeResult
except ImportError:
    pytest.skip("sync_dispatcher.py settings merge not implemented yet", allow_module_level=True)


@pytest.fixture
def temp_project_root(tmp_path):
    """Create temporary project root for testing"""
    project_root = tmp_path / "test_project"
    project_root.mkdir()

    # Create necessary directories
    (project_root / ".claude").mkdir()
    (project_root / ".claude" / "hooks").mkdir()

    return str(project_root)


@pytest.fixture
def mock_plugin_root(tmp_path):
    """Create mock plugin root with templates and installed_plugins.json"""
    plugin_root = tmp_path / "plugins" / "autonomous-dev"
    plugin_root.mkdir(parents=True)

    # Create plugin.json (needed for sync_marketplace)
    plugin_json = plugin_root / "plugin.json"
    plugin_json.write_text(json.dumps({"name": "autonomous-dev", "version": "1.0.0"}, indent=2))

    # Create empty directories for commands, hooks, agents (to prevent sync errors)
    (plugin_root / "commands").mkdir(exist_ok=True)
    (plugin_root / "hooks").mkdir(exist_ok=True)
    (plugin_root / "agents").mkdir(exist_ok=True)

    # Create templates directory
    templates_dir = plugin_root / "templates"
    templates_dir.mkdir()

    # Create template settings.local.json
    template_data = {
        "hooks": {
            "PreToolUse": [
                {"type": "command", "command": "python3 pre_tool_use.py", "timeout": 5}
            ],
            "PostToolUse": [
                {"type": "command", "command": "python3 auto_format.py"}
            ]
        }
    }

    template_path = templates_dir / "settings.local.json"
    template_path.write_text(json.dumps(template_data, indent=2))

    # Create installed_plugins.json (what sync_marketplace actually expects)
    # Format: plugins are keyed by name, not in an array
    plugins_config_dir = tmp_path / ".claude" / "plugins"
    plugins_config_dir.mkdir(parents=True, exist_ok=True)

    installed_plugins_json = plugins_config_dir / "installed_plugins.json"
    installed_plugins_data = {
        "autonomous-dev": {
            "name": "autonomous-dev",
            "path": str(plugin_root),
            "version": "1.0.0"
        }
    }
    installed_plugins_json.write_text(json.dumps(installed_plugins_data, indent=2))

    return installed_plugins_json


@pytest.fixture
def existing_user_settings(temp_project_root):
    """Create existing user settings with custom configuration"""
    user_settings_path = Path(temp_project_root) / ".claude" / "settings.local.json"

    user_data = {
        "hooks": {
            "PreCommit": [
                {"type": "command", "command": "python3 custom_hook.py"}
            ]
        },
        "permissions": {
            "allow": ["Read(**)"]
        }
    }

    user_settings_path.write_text(json.dumps(user_data, indent=2))
    return user_settings_path


# ============================================================================
# Marketplace Sync Integration Tests (4 tests)
# ============================================================================

def test_marketplace_sync_merges_settings_on_first_install(temp_project_root, mock_plugin_root):
    """Test marketplace sync merges settings.local.json on first install (no existing file)"""
    dispatcher = SyncDispatcher(temp_project_root)

    # Mock sync_directory to avoid actual file operations
    with patch.object(dispatcher, '_sync_directory') as mock_sync:
        mock_sync.return_value = 0

        result = dispatcher.sync_marketplace(mock_plugin_root)

    assert result.success is True
    assert result.settings_merged is not None
    assert result.settings_merged.success is True
    assert result.settings_merged.hooks_added >= 1  # At least PreToolUse added

    # Verify settings.local.json was created
    settings_path = Path(temp_project_root) / ".claude" / "settings.local.json"
    assert settings_path.exists()

    # Verify PreToolUse hook present
    settings_data = json.loads(settings_path.read_text())
    assert "PreToolUse" in settings_data["hooks"]


def test_marketplace_sync_merges_settings_on_update(temp_project_root, mock_plugin_root, existing_user_settings):
    """Test marketplace sync merges settings.local.json on plugin update (existing file)"""
    dispatcher = SyncDispatcher(temp_project_root)

    # Verify existing settings before sync
    existing_data = json.loads(existing_user_settings.read_text())
    assert "PreCommit" in existing_data["hooks"]
    assert "PreToolUse" not in existing_data["hooks"]

    with patch.object(dispatcher, '_sync_directory') as mock_sync:
        mock_sync.return_value = 0

        result = dispatcher.sync_marketplace(mock_plugin_root)

    assert result.success is True
    assert result.settings_merged is not None
    assert result.settings_merged.success is True
    assert result.settings_merged.hooks_added >= 1  # PreToolUse added
    assert result.settings_merged.hooks_preserved >= 1  # PreCommit preserved

    # Verify merged settings
    merged_data = json.loads(existing_user_settings.read_text())
    assert "PreCommit" in merged_data["hooks"]  # Preserved
    assert "PreToolUse" in merged_data["hooks"]  # Added


def test_marketplace_sync_preserves_user_hook_customizations(temp_project_root, mock_plugin_root):
    """Test marketplace sync preserves user-modified hooks and custom config"""
    # Create user settings with custom hook configuration
    user_settings_path = Path(temp_project_root) / ".claude" / "settings.local.json"
    user_data = {
        "hooks": {
            "PreToolUse": [
                {"type": "command", "command": "python3 custom_pre_tool_use.py", "timeout": 10}
            ]
        },
        "permissions": {
            "allow": ["Read(**)"],
            "deny": ["Write(/etc/**)"]
        },
        "customConfig": {
            "myFeature": "enabled"
        }
    }
    user_settings_path.write_text(json.dumps(user_data, indent=2))

    dispatcher = SyncDispatcher(temp_project_root)

    with patch.object(dispatcher, '_sync_directory') as mock_sync:
        mock_sync.return_value = 0

        result = dispatcher.sync_marketplace(mock_plugin_root)

    assert result.success is True

    # Verify user customizations preserved
    merged_data = json.loads(user_settings_path.read_text())

    # Custom PreToolUse hook preserved (not overwritten by template)
    assert merged_data["hooks"]["PreToolUse"][0]["command"] == "python3 custom_pre_tool_use.py"
    assert merged_data["hooks"]["PreToolUse"][0]["timeout"] == 10

    # Custom permissions preserved
    assert merged_data["permissions"]["deny"] == ["Write(/etc/**)"]

    # Custom config preserved
    assert merged_data["customConfig"]["myFeature"] == "enabled"


def test_marketplace_sync_adds_pretooluse_from_template(temp_project_root, mock_plugin_root, existing_user_settings):
    """Test marketplace sync specifically adds PreToolUse hook from template"""
    # Verify PreToolUse not in existing settings
    existing_data = json.loads(existing_user_settings.read_text())
    assert "PreToolUse" not in existing_data["hooks"]

    dispatcher = SyncDispatcher(temp_project_root)

    with patch.object(dispatcher, '_sync_directory') as mock_sync:
        mock_sync.return_value = 0

        result = dispatcher.sync_marketplace(mock_plugin_root)

    assert result.success is True
    assert result.settings_merged.hooks_added >= 1

    # Verify PreToolUse hook added with correct configuration
    merged_data = json.loads(existing_user_settings.read_text())
    assert "PreToolUse" in merged_data["hooks"]

    pretooluse_hook = merged_data["hooks"]["PreToolUse"][0]
    assert pretooluse_hook["type"] == "command"
    assert "pre_tool_use.py" in pretooluse_hook["command"]
    assert pretooluse_hook["timeout"] == 5


# ============================================================================
# Non-Blocking Behavior Tests (2 tests)
# ============================================================================

def test_marketplace_sync_succeeds_when_settings_merge_fails(temp_project_root, mock_plugin_root):
    """Test marketplace sync succeeds even when settings merge fails (graceful degradation)"""
    dispatcher = SyncDispatcher(temp_project_root)

    # Mock SettingsMerger to fail
    with patch('autonomous_dev.lib.sync_dispatcher.SettingsMerger') as MockMerger:
        mock_merger_instance = MagicMock()
        mock_merger_instance.merge_settings.return_value = MergeResult(
            success=False,
            message="Mock merge failure",
            hooks_added=0,
            hooks_preserved=0
        )
        MockMerger.return_value = mock_merger_instance

        with patch.object(dispatcher, '_sync_directory') as mock_sync:
            mock_sync.return_value = 0

            result = dispatcher.sync_marketplace(mock_plugin_root)

    # Sync should still succeed (non-blocking)
    assert result.success is True

    # But settings merge should have failed
    assert result.settings_merged is not None
    assert result.settings_merged.success is False

    # Summary should indicate the failed merge
    assert "settings" in result.summary.lower() or "merge" in result.summary.lower() or "failed" in result.summary.lower()


def test_marketplace_sync_succeeds_when_template_missing(temp_project_root, tmp_path):
    """Test marketplace sync succeeds when template settings.local.json doesn't exist"""
    # Create plugin root without template file
    plugin_root = tmp_path / "plugins" / "autonomous-dev"
    plugin_root.mkdir(parents=True)

    # Create minimal plugin structure
    (plugin_root / "plugin.json").write_text(json.dumps({"name": "autonomous-dev", "version": "1.0.0"}))
    (plugin_root / "commands").mkdir(exist_ok=True)
    (plugin_root / "hooks").mkdir(exist_ok=True)
    (plugin_root / "agents").mkdir(exist_ok=True)

    templates_dir = plugin_root / "templates"
    templates_dir.mkdir()
    # No settings.local.json in templates

    # Create installed_plugins.json
    plugins_config_dir = tmp_path / ".claude" / "plugins"
    plugins_config_dir.mkdir(parents=True, exist_ok=True)
    installed_plugins_json = plugins_config_dir / "installed_plugins.json"
    installed_plugins_data = {
        "autonomous-dev": {
            "name": "autonomous-dev",
            "path": str(plugin_root),
            "version": "1.0.0"
        }
    }
    installed_plugins_json.write_text(json.dumps(installed_plugins_data, indent=2))

    dispatcher = SyncDispatcher(temp_project_root)

    with patch.object(dispatcher, '_sync_directory') as mock_sync:
        mock_sync.return_value = 0

        result = dispatcher.sync_marketplace(installed_plugins_json)

    # Should still succeed (template is optional)
    assert result.success is True

    # Settings merge might fail or be skipped
    if result.settings_merged is not None:
        assert result.settings_merged.success is False


# ============================================================================
# Result Reporting Tests (2 tests)
# ============================================================================

def test_sync_result_includes_settings_merge_status(temp_project_root, mock_plugin_root, existing_user_settings):
    """Test SyncResult includes MergeResult in settings_merged field"""
    dispatcher = SyncDispatcher(temp_project_root)

    with patch.object(dispatcher, '_sync_directory') as mock_sync:
        mock_sync.return_value = 0

        result = dispatcher.sync_marketplace(mock_plugin_root)

    assert result.success is True

    # Verify settings_merged field exists and has correct structure
    assert hasattr(result, 'settings_merged')
    assert result.settings_merged is not None
    # Check it has the expected fields (duck typing instead of isinstance check)
    assert hasattr(result.settings_merged, 'success')
    assert hasattr(result.settings_merged, 'message')
    assert hasattr(result.settings_merged, 'hooks_added')
    assert hasattr(result.settings_merged, 'hooks_preserved')
    # Verify it's the right type by checking the class name
    assert result.settings_merged.__class__.__name__ == 'MergeResult'


def test_sync_result_summary_includes_settings_info(temp_project_root, mock_plugin_root, existing_user_settings):
    """Test SyncResult summary message includes settings merge information"""
    dispatcher = SyncDispatcher(temp_project_root)

    with patch.object(dispatcher, '_sync_directory') as mock_sync:
        mock_sync.return_value = 0

        result = dispatcher.sync_marketplace(mock_plugin_root)

    assert result.success is True
    assert result.settings_merged is not None

    # Summary message should mention settings merge
    summary = result.summary.lower()

    # Should include information about hooks being added
    if result.settings_merged.hooks_added > 0:
        assert "hook" in summary or "setting" in summary or "merge" in summary

    # Should include counts if available
    if result.settings_merged.hooks_added > 0 or result.settings_merged.hooks_preserved > 0:
        # Message should reference the merge operation
        assert len(summary) > 0  # Summary exists


# ============================================================================
# Integration Test - Full Workflow
# ============================================================================

def test_full_marketplace_sync_workflow_with_settings_merge(temp_project_root, mock_plugin_root):
    """Test complete marketplace sync workflow including settings merge"""
    # Setup: Create user settings with some existing hooks
    user_settings_path = Path(temp_project_root) / ".claude" / "settings.local.json"
    user_data = {
        "hooks": {
            "PreCommit": [{"type": "command", "command": "python3 validate.py"}]
        },
        "permissions": {"allow": ["Read(**)"]}
    }
    user_settings_path.write_text(json.dumps(user_data, indent=2))

    # Execute sync
    dispatcher = SyncDispatcher(temp_project_root)

    with patch.object(dispatcher, '_sync_directory') as mock_sync:
        mock_sync.return_value = 0

        result = dispatcher.sync_marketplace(mock_plugin_root)

    # Verify overall success
    assert result.success is True

    # Verify settings merge occurred
    assert result.settings_merged is not None
    assert result.settings_merged.success is True
    assert result.settings_merged.hooks_added >= 1  # PreToolUse added
    assert result.settings_merged.hooks_preserved >= 1  # PreCommit preserved

    # Verify final merged settings
    final_data = json.loads(user_settings_path.read_text())

    # Template hooks added
    assert "PreToolUse" in final_data["hooks"]
    assert "PostToolUse" in final_data["hooks"]

    # User hooks preserved
    assert "PreCommit" in final_data["hooks"]

    # User config preserved
    assert final_data["permissions"]["allow"] == ["Read(**)"]

    # Verify hook count
    assert len(final_data["hooks"]) == 3  # PreCommit + PreToolUse + PostToolUse
