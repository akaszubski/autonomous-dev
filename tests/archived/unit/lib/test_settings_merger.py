"""
Unit tests for settings_merger.py - TDD Red Phase

Tests the SettingsMerger class for merging settings.local.json files
with PreToolUse hook registration from templates.

Expected to FAIL until implementation is complete.
"""

import json
import sys
import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock
from dataclasses import asdict

# Add plugins directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent / "plugins"))

# Import will fail until implementation exists
try:
    from autonomous_dev.lib.settings_merger import SettingsMerger, MergeResult
except ImportError:
    pytest.skip("settings_merger.py not implemented yet", allow_module_level=True)


@pytest.fixture
def temp_project_root(tmp_path):
    """Create temporary project root for testing"""
    return str(tmp_path)


@pytest.fixture
def template_settings_path(tmp_path):
    """Create template settings.local.json"""
    template_dir = tmp_path / "templates"
    template_dir.mkdir()
    template_path = template_dir / "settings.local.json"

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

    template_path.write_text(json.dumps(template_data, indent=2))
    return template_path


@pytest.fixture
def user_settings_path(tmp_path):
    """Create user settings.local.json directory (file created per test)"""
    user_dir = tmp_path / ".claude"
    user_dir.mkdir()
    return user_dir / "settings.local.json"


@pytest.fixture
def existing_user_settings(user_settings_path):
    """Create existing user settings with custom configuration"""
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
# Core Functionality Tests (5 tests)
# ============================================================================

def test_merge_empty_user_settings(temp_project_root, template_settings_path, user_settings_path):
    """Test merge when user has no existing settings.local.json (first install)"""
    merger = SettingsMerger(temp_project_root)

    # User settings file does not exist
    assert not user_settings_path.exists()

    result = merger.merge_settings(template_settings_path, user_settings_path)

    # Should succeed and create new file
    assert result.success is True
    assert "created" in result.message.lower() or "merged" in result.message.lower()
    assert result.settings_path == str(user_settings_path)
    assert result.hooks_added == 2  # PreToolUse + PostToolUse
    assert result.hooks_preserved == 0  # No existing hooks

    # Verify file was created with template content
    assert user_settings_path.exists()
    merged_data = json.loads(user_settings_path.read_text())
    assert "PreToolUse" in merged_data["hooks"]
    assert "PostToolUse" in merged_data["hooks"]


def test_merge_preserves_user_customizations(temp_project_root, template_settings_path, existing_user_settings):
    """Test merge preserves non-hook user customizations (permissions, etc.)"""
    merger = SettingsMerger(temp_project_root)

    result = merger.merge_settings(template_settings_path, existing_user_settings)

    assert result.success is True
    assert result.hooks_added == 2  # PreToolUse + PostToolUse added
    assert result.hooks_preserved >= 1  # PreCommit preserved

    # Verify user customizations preserved
    merged_data = json.loads(existing_user_settings.read_text())
    assert merged_data["permissions"]["allow"] == ["Read(**)"]
    assert "PreCommit" in merged_data["hooks"]  # User hook preserved
    assert "PreToolUse" in merged_data["hooks"]  # Template hook added
    assert "PostToolUse" in merged_data["hooks"]  # Template hook added


def test_merge_adds_missing_hooks(temp_project_root, template_settings_path, existing_user_settings):
    """Test merge adds PreToolUse from template to user settings"""
    merger = SettingsMerger(temp_project_root)

    # Verify PreToolUse not in existing settings
    existing_data = json.loads(existing_user_settings.read_text())
    assert "PreToolUse" not in existing_data["hooks"]

    result = merger.merge_settings(template_settings_path, existing_user_settings)

    assert result.success is True
    assert result.hooks_added >= 1  # At least PreToolUse added

    # Verify PreToolUse now exists
    merged_data = json.loads(existing_user_settings.read_text())
    assert "PreToolUse" in merged_data["hooks"]
    assert merged_data["hooks"]["PreToolUse"][0]["command"] == "python3 pre_tool_use.py"


def test_merge_avoids_duplicate_hooks(temp_project_root, template_settings_path, user_settings_path):
    """Test merge doesn't re-add hooks that already exist"""
    # Create user settings with PreToolUse already present
    user_data = {
        "hooks": {
            "PreToolUse": [
                {"type": "command", "command": "python3 pre_tool_use.py", "timeout": 5}
            ]
        }
    }
    user_settings_path.write_text(json.dumps(user_data, indent=2))

    merger = SettingsMerger(temp_project_root)
    result = merger.merge_settings(template_settings_path, user_settings_path)

    assert result.success is True
    assert result.hooks_preserved >= 1  # PreToolUse already exists

    # Verify no duplicate PreToolUse hooks
    merged_data = json.loads(user_settings_path.read_text())
    assert len(merged_data["hooks"]["PreToolUse"]) == 1


def test_merge_deep_merge_preserves_nested_config(temp_project_root, template_settings_path, user_settings_path):
    """Test merge handles nested objects correctly (deep merge)"""
    # User has nested config
    user_data = {
        "hooks": {
            "PreCommit": [{"type": "command", "command": "custom.py"}]
        },
        "permissions": {
            "allow": ["Read(**)"],
            "deny": ["Write(/etc/**)"]
        },
        "customConfig": {
            "nested": {
                "deeply": {
                    "value": "preserved"
                }
            }
        }
    }
    user_settings_path.write_text(json.dumps(user_data, indent=2))

    merger = SettingsMerger(temp_project_root)
    result = merger.merge_settings(template_settings_path, user_settings_path)

    assert result.success is True

    # Verify deep nested config preserved
    merged_data = json.loads(user_settings_path.read_text())
    assert merged_data["customConfig"]["nested"]["deeply"]["value"] == "preserved"
    assert merged_data["permissions"]["deny"] == ["Write(/etc/**)"]
    assert "PreToolUse" in merged_data["hooks"]  # Template hooks added


# ============================================================================
# Edge Cases (4 tests)
# ============================================================================

def test_template_not_found_returns_error(temp_project_root, user_settings_path):
    """Test merge fails gracefully when template file doesn't exist"""
    merger = SettingsMerger(temp_project_root)

    # Use a path within temp_project_root but non-existent
    non_existent_template = Path(temp_project_root) / "nonexistent" / "template.json"
    result = merger.merge_settings(non_existent_template, user_settings_path)

    assert result.success is False
    assert "not found" in result.message.lower() or "does not exist" in result.message.lower()
    assert result.hooks_added == 0


def test_user_settings_invalid_json_returns_error(temp_project_root, template_settings_path, user_settings_path):
    """Test merge fails gracefully with corrupt JSON in user settings"""
    # Write invalid JSON
    user_settings_path.write_text("{invalid json")

    merger = SettingsMerger(temp_project_root)
    result = merger.merge_settings(template_settings_path, user_settings_path)

    assert result.success is False
    assert "json" in result.message.lower() or "parse" in result.message.lower()


def test_user_settings_missing_creates_new(temp_project_root, template_settings_path, user_settings_path):
    """Test merge creates new file when user settings don't exist"""
    # Ensure file doesn't exist
    assert not user_settings_path.exists()

    merger = SettingsMerger(temp_project_root)
    result = merger.merge_settings(template_settings_path, user_settings_path)

    assert result.success is True
    assert user_settings_path.exists()
    assert result.hooks_added == 2  # PreToolUse + PostToolUse from template


def test_atomic_write_creates_file_with_secure_permissions(temp_project_root, template_settings_path, user_settings_path):
    """Test atomic write creates file with 0o600 permissions (user read/write only)"""
    merger = SettingsMerger(temp_project_root)
    result = merger.merge_settings(template_settings_path, user_settings_path)

    assert result.success is True
    assert user_settings_path.exists()

    # Verify secure permissions (0o600)
    import stat
    file_stat = user_settings_path.stat()
    file_mode = stat.S_IMODE(file_stat.st_mode)
    assert file_mode == 0o600, f"Expected 0o600, got {oct(file_mode)}"


# ============================================================================
# Security Tests (3 tests)
# ============================================================================

def test_path_traversal_blocked(temp_project_root, template_settings_path):
    """Test merge rejects paths with '..' (CWE-22)"""
    merger = SettingsMerger(temp_project_root)

    malicious_path = Path("../../etc/passwd")
    result = merger.merge_settings(template_settings_path, malicious_path)

    assert result.success is False
    assert "path" in result.message.lower() or "security" in result.message.lower()


def test_symlink_attack_blocked(temp_project_root, template_settings_path, tmp_path):
    """Test merge rejects symlinks (CWE-59)"""
    # Create symlink to sensitive file
    sensitive_file = tmp_path / "sensitive.json"
    sensitive_file.write_text('{"secret": "data"}')

    symlink_path = tmp_path / "symlink.json"
    symlink_path.symlink_to(sensitive_file)

    merger = SettingsMerger(temp_project_root)
    result = merger.merge_settings(template_settings_path, symlink_path)

    assert result.success is False
    assert "symlink" in result.message.lower() or "security" in result.message.lower()


@patch('autonomous_dev.lib.settings_merger.validate_path')
def test_validates_paths_before_operations(mock_validate, temp_project_root, template_settings_path, user_settings_path):
    """Test security validation called for all paths"""
    # Mock should return Path (not tuple) - validate_path returns Path on success
    mock_validate.return_value = template_settings_path

    merger = SettingsMerger(temp_project_root)
    merger.merge_settings(template_settings_path, user_settings_path)

    # Should validate both template and user paths
    assert mock_validate.call_count >= 2
    call_args = [call[0][0] for call in mock_validate.call_args_list]
    # Call args will be Path objects
    assert template_settings_path in call_args or str(template_settings_path) in [str(arg) for arg in call_args]
    assert user_settings_path in call_args or str(user_settings_path) in [str(arg) for arg in call_args]


# ============================================================================
# Integration Tests (3 tests)
# ============================================================================

def test_merge_result_contains_accurate_counts(temp_project_root, template_settings_path, existing_user_settings):
    """Test MergeResult contains accurate hooks_added and hooks_preserved counts"""
    merger = SettingsMerger(temp_project_root)
    result = merger.merge_settings(template_settings_path, existing_user_settings)

    assert result.success is True
    assert isinstance(result.hooks_added, int)
    assert isinstance(result.hooks_preserved, int)
    assert result.hooks_added == 2  # PreToolUse + PostToolUse
    assert result.hooks_preserved >= 1  # PreCommit from existing

    # Verify counts match actual merged data
    merged_data = json.loads(existing_user_settings.read_text())
    total_hooks = len(merged_data["hooks"])
    assert total_hooks == result.hooks_added + result.hooks_preserved


def test_audit_log_records_merge_operations(temp_project_root, template_settings_path, user_settings_path):
    """Test audit trail is created for merge operations"""
    merger = SettingsMerger(temp_project_root)

    with patch('autonomous_dev.lib.settings_merger.audit_log') as mock_log:
        result = merger.merge_settings(template_settings_path, user_settings_path)

        assert result.success is True
        # Should log the merge operation
        assert mock_log.called
        # audit_log takes (event_type, status, context) - check the event_type
        call_args = mock_log.call_args[0]
        assert "merge" in str(call_args).lower() or "settings" in str(call_args).lower()


def test_dry_run_mode_no_writes(temp_project_root, template_settings_path, user_settings_path):
    """Test dry run mode doesn't modify files (write_result=False)"""
    # Create existing user settings
    user_data = {"hooks": {}, "custom": "value"}
    user_settings_path.write_text(json.dumps(user_data, indent=2))
    original_content = user_settings_path.read_text()

    merger = SettingsMerger(temp_project_root)
    result = merger.merge_settings(template_settings_path, user_settings_path, write_result=False)

    assert result.success is True
    assert result.hooks_added > 0  # Should calculate what would be added

    # Verify file wasn't modified
    assert user_settings_path.read_text() == original_content
