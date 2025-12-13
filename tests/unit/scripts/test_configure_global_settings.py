#!/usr/bin/env python3
"""
Unit tests for configure_global_settings CLI script - TDD Red Phase

Tests the CLI wrapper script that configures ~/.claude/settings.json during
fresh install or upgrade.

Expected to FAIL until implementation is complete.

Security Requirements (GitHub Issue #116):
1. Fresh install: Create ~/.claude/settings.json from template
2. Upgrade: Preserve user customizations while fixing broken patterns
3. Broken patterns: Replace Bash(:*) with specific safe patterns
4. Non-blocking: Exit 0 even on errors (installation continues)
5. JSON output: Return structured data for install.sh consumption
6. Directory creation: Create ~/.claude/ if missing

Test Strategy:
- Test fresh install scenario (no existing settings)
- Test upgrade scenario (existing valid settings)
- Test broken pattern detection and fix
- Test missing template handling
- Test directory creation
- Test JSON output format
- Test exit code behavior (always 0)
- Test integration with SettingsGenerator.merge_global_settings()

Coverage Target: 95%+ for CLI script

Author: test-master agent
Date: 2025-12-13
Issue: #116
Phase: TDD Red (tests written BEFORE implementation)
Status: RED (expected to fail - no implementation yet)
"""

import json
import sys
import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock, mock_open, call
from typing import Dict, Any
import tempfile
import shutil

# Add plugins directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent / "plugins"))

# Mock the script for test discovery (will fail until implementation exists)
try:
    # This import will fail - implementation doesn't exist yet
    from autonomous_dev.scripts import configure_global_settings
except ImportError:
    # Create minimal mock for test discovery
    class MockModule:
        @staticmethod
        def main():
            raise NotImplementedError("Implementation pending - TDD Red Phase")

        @staticmethod
        def create_fresh_settings(template_path: Path, global_path: Path) -> Dict[str, Any]:
            raise NotImplementedError("Implementation pending - TDD Red Phase")

        @staticmethod
        def upgrade_existing_settings(global_path: Path, template_path: Path) -> Dict[str, Any]:
            raise NotImplementedError("Implementation pending - TDD Red Phase")

        @staticmethod
        def ensure_claude_directory(claude_dir: Path) -> bool:
            raise NotImplementedError("Implementation pending - TDD Red Phase")

    configure_global_settings = MockModule()


# Test Constants
GLOBAL_SETTINGS_PATH = Path.home() / ".claude" / "settings.json"
TEMPLATE_PATH = Path(__file__).parent.parent.parent.parent / "plugins" / "autonomous-dev" / "config" / "global_settings_template.json"

TEMPLATE_SETTINGS = {
    "permissions": {
        "allow": [
            "Bash(git:*)",
            "Bash(python:*)",
            "Bash(python3:*)",
            "Bash(pytest:*)",
            "Bash(pip:*)",
            "Bash(pip3:*)",
            "Bash(ls:*)",
            "Bash(cat:*)",
            "Bash(gh:*)",
            "Read(**)",
            "Write(**)",
            "Edit(**)",
            "Glob",
            "Grep",
            "Task",
            "WebFetch",
            "WebSearch"
        ],
        "deny": [
            "Bash(rm -rf /)",
            "Bash(sudo:*)",
            "Read(./.env)",
            "Read(~/.ssh/**)"
        ]
    },
    "hooks": {
        "PreToolUse": [
            {
                "matcher": "*",
                "hooks": [
                    {
                        "type": "command",
                        "command": "MCP_AUTO_APPROVE=true python3 ~/.claude/hooks/pre_tool_use.py",
                        "timeout": 5
                    }
                ]
            }
        ]
    }
}

BROKEN_USER_SETTINGS = {
    "permissions": {
        "allow": [
            "Bash(:*)",  # BROKEN - overly permissive wildcard
            "Read(**)"
        ],
        "deny": []
    },
    "hooks": {
        "PreToolUse": [
            {
                "matcher": "*",
                "hooks": [
                    {
                        "type": "command",
                        "command": "python3 ~/.my-hooks/custom_hook.py",
                        "timeout": 10
                    }
                ]
            }
        ]
    }
}

VALID_USER_SETTINGS = {
    "permissions": {
        "allow": [
            "Bash(git:*)",
            "Bash(python:*)",
            "Bash(custom-tool:*)",  # User addition
            "Read(**)",
            "Write(**)"
        ],
        "deny": [
            "Bash(sudo:*)",
            "Bash(custom-dangerous:*)"  # User addition
        ]
    },
    "hooks": {
        "PreToolUse": [
            {
                "matcher": "*",
                "hooks": [
                    {
                        "type": "command",
                        "command": "python3 ~/.my-hooks/custom_hook.py",
                        "timeout": 10
                    }
                ]
            }
        ]
    }
}


class TestConfigureGlobalSettings:
    """Test suite for configure_global_settings CLI script"""

    def test_fresh_install_creates_settings(self, tmp_path):
        """
        Test: Fresh install creates settings.json from template when none exist

        Scenario:
        - No ~/.claude/settings.json exists
        - Template file exists
        - Should create settings.json with template content
        - Should return success JSON

        Expected Result:
        - settings.json created with all template patterns
        - JSON output: {"success": true, "created": true, "message": "..."}
        - Exit code: 0
        """
        # ARRANGE
        template_path = tmp_path / "template.json"
        template_path.write_text(json.dumps(TEMPLATE_SETTINGS, indent=2))

        global_path = tmp_path / ".claude" / "settings.json"
        claude_dir = tmp_path / ".claude"

        # Directory doesn't exist yet
        assert not claude_dir.exists()
        assert not global_path.exists()

        # ACT
        result = configure_global_settings.create_fresh_settings(template_path, global_path)

        # ASSERT
        # Verify directory created
        assert claude_dir.exists()
        assert claude_dir.is_dir()

        # Verify settings file created
        assert global_path.exists()
        created_settings = json.loads(global_path.read_text())

        # Verify content matches template
        assert created_settings["permissions"]["allow"] == TEMPLATE_SETTINGS["permissions"]["allow"]
        assert created_settings["permissions"]["deny"] == TEMPLATE_SETTINGS["permissions"]["deny"]
        assert created_settings["hooks"] == TEMPLATE_SETTINGS["hooks"]

        # Verify JSON output
        assert result["success"] is True
        assert result["created"] is True
        assert "fresh install" in result["message"].lower()

    def test_existing_settings_preserved(self, tmp_path):
        """
        Test: Existing valid settings are preserved during upgrade

        Scenario:
        - ~/.claude/settings.json exists with valid patterns
        - User has custom additions (custom-tool, custom-dangerous)
        - Template has standard patterns
        - Should merge without losing user customizations

        Expected Result:
        - User customizations preserved
        - Standard patterns added from template
        - JSON output: {"success": true, "created": false, "message": "..."}
        """
        # ARRANGE
        template_path = tmp_path / "template.json"
        template_path.write_text(json.dumps(TEMPLATE_SETTINGS, indent=2))

        claude_dir = tmp_path / ".claude"
        claude_dir.mkdir(parents=True)
        global_path = claude_dir / "settings.json"
        global_path.write_text(json.dumps(VALID_USER_SETTINGS, indent=2))

        # ACT
        result = configure_global_settings.upgrade_existing_settings(global_path, template_path)

        # ASSERT
        merged_settings = json.loads(global_path.read_text())

        # Verify user customizations preserved
        assert "Bash(custom-tool:*)" in merged_settings["permissions"]["allow"]
        assert "Bash(custom-dangerous:*)" in merged_settings["permissions"]["deny"]

        # Verify custom hook preserved
        custom_hook_found = False
        for hook_config in merged_settings["hooks"]["PreToolUse"]:
            for hook in hook_config["hooks"]:
                if "custom_hook.py" in hook["command"]:
                    custom_hook_found = True
                    assert hook["timeout"] == 10  # User's custom timeout
        assert custom_hook_found, "Custom hook should be preserved"

        # Verify standard patterns also present
        assert "Bash(pytest:*)" in merged_settings["permissions"]["allow"]
        assert "Bash(gh:*)" in merged_settings["permissions"]["allow"]

        # Verify JSON output
        assert result["success"] is True
        assert result["created"] is False
        assert "upgraded" in result["message"].lower() or "merged" in result["message"].lower()

    def test_broken_patterns_fixed(self, tmp_path):
        """
        Test: Broken wildcard patterns (Bash(:*)) are replaced with safe patterns

        Scenario:
        - Existing settings contain broken pattern: Bash(:*)
        - Template contains safe specific patterns
        - Should detect and replace broken pattern
        - Should preserve other valid patterns

        Expected Result:
        - Bash(:*) removed
        - Safe patterns added: Bash(git:*), Bash(python:*), etc.
        - JSON output indicates fix applied
        """
        # ARRANGE
        template_path = tmp_path / "template.json"
        template_path.write_text(json.dumps(TEMPLATE_SETTINGS, indent=2))

        claude_dir = tmp_path / ".claude"
        claude_dir.mkdir(parents=True)
        global_path = claude_dir / "settings.json"
        global_path.write_text(json.dumps(BROKEN_USER_SETTINGS, indent=2))

        # ACT
        result = configure_global_settings.upgrade_existing_settings(global_path, template_path)

        # ASSERT
        fixed_settings = json.loads(global_path.read_text())

        # Verify broken pattern removed
        assert "Bash(:*)" not in fixed_settings["permissions"]["allow"]
        assert "Bash(*)" not in fixed_settings["permissions"]["allow"]

        # Verify safe patterns added
        safe_patterns = [
            "Bash(git:*)",
            "Bash(python:*)",
            "Bash(python3:*)",
            "Bash(pytest:*)",
            "Bash(pip:*)",
            "Bash(gh:*)"
        ]
        for pattern in safe_patterns:
            assert pattern in fixed_settings["permissions"]["allow"], f"Safe pattern {pattern} should be added"

        # Verify user's valid patterns preserved (Read(**)
        assert "Read(**)" in fixed_settings["permissions"]["allow"]

        # Verify JSON output indicates fix
        assert result["success"] is True
        assert "fixed" in result["message"].lower() or "replaced" in result["message"].lower()

    def test_missing_template_handled(self, tmp_path):
        """
        Test: Gracefully handle missing template file

        Scenario:
        - Template file doesn't exist
        - Should not crash
        - Should return error JSON
        - Should exit 0 (non-blocking)

        Expected Result:
        - JSON output: {"success": false, "error": "..."}
        - Exit code: 0 (non-blocking)
        - No settings file created/modified
        """
        # ARRANGE
        missing_template = tmp_path / "nonexistent.json"
        global_path = tmp_path / ".claude" / "settings.json"

        # ACT
        result = configure_global_settings.create_fresh_settings(missing_template, global_path)

        # ASSERT
        # Verify error returned but doesn't crash
        assert result["success"] is False
        assert "error" in result or "message" in result
        assert "template" in result.get("error", result.get("message", "")).lower()

        # Verify no settings file created
        assert not global_path.exists()

    def test_creates_claude_dir(self, tmp_path):
        """
        Test: Creates ~/.claude/ directory if it doesn't exist

        Scenario:
        - ~/.claude/ directory doesn't exist
        - Should create directory with proper permissions
        - Should then create settings.json inside

        Expected Result:
        - Directory created with 0o755 permissions
        - settings.json created inside
        - Parent directory creation (mkdir -p behavior)
        """
        # ARRANGE
        template_path = tmp_path / "template.json"
        template_path.write_text(json.dumps(TEMPLATE_SETTINGS, indent=2))

        claude_dir = tmp_path / ".claude"
        global_path = claude_dir / "settings.json"

        # Verify directory doesn't exist
        assert not claude_dir.exists()

        # ACT
        result = configure_global_settings.ensure_claude_directory(claude_dir)

        # ASSERT
        # Verify directory created
        assert result is True
        assert claude_dir.exists()
        assert claude_dir.is_dir()

        # Verify permissions (should be readable/writable by user)
        stat = claude_dir.stat()
        # Check owner has read/write/execute
        assert stat.st_mode & 0o700 == 0o700

    def test_json_output_format(self, tmp_path):
        """
        Test: CLI outputs valid JSON for consumption by install.sh

        Scenario:
        - Script should output JSON to stdout
        - Format: {"success": bool, "created": bool, "message": str}
        - Should be parseable by shell scripts

        Expected Result:
        - Valid JSON structure
        - All required fields present
        - Proper boolean/string types
        """
        # ARRANGE
        template_path = tmp_path / "template.json"
        template_path.write_text(json.dumps(TEMPLATE_SETTINGS, indent=2))

        global_path = tmp_path / ".claude" / "settings.json"

        # ACT
        result = configure_global_settings.create_fresh_settings(template_path, global_path)

        # ASSERT
        # Verify result is valid JSON-serializable dict
        json_str = json.dumps(result)
        parsed = json.loads(json_str)

        # Verify required fields
        assert "success" in parsed
        assert isinstance(parsed["success"], bool)

        assert "created" in parsed
        assert isinstance(parsed["created"], bool)

        assert "message" in parsed
        assert isinstance(parsed["message"], str)
        assert len(parsed["message"]) > 0

    def test_exit_code_always_zero(self, tmp_path):
        """
        Test: Script exits 0 even on errors (non-blocking for installation)

        Scenario:
        - Various error conditions (missing template, permission errors, etc.)
        - Should return error JSON but exit 0
        - Installation should continue even if this step fails

        Expected Result:
        - sys.exit(0) called on success
        - sys.exit(0) called on error
        - Never exits with non-zero code
        """
        # ARRANGE
        missing_template = tmp_path / "nonexistent.json"
        global_path = tmp_path / ".claude" / "settings.json"

        # ACT - Missing template
        with patch('sys.exit') as mock_exit:
            result = configure_global_settings.create_fresh_settings(missing_template, global_path)

            # ASSERT
            # Should still exit 0 even on error
            if mock_exit.called:
                mock_exit.assert_called_with(0)

            # Should return error in JSON
            assert result["success"] is False

    def test_integration_with_settings_generator(self, tmp_path):
        """
        Test: CLI correctly integrates with SettingsGenerator.merge_global_settings()

        Scenario:
        - CLI script should call SettingsGenerator.merge_global_settings()
        - Should pass correct paths
        - Should handle return value correctly

        Expected Result:
        - SettingsGenerator.merge_global_settings() called with (global_path, template_path)
        - Return value processed into JSON output
        - Errors from generator handled gracefully
        """
        # ARRANGE
        template_path = tmp_path / "template.json"
        template_path.write_text(json.dumps(TEMPLATE_SETTINGS, indent=2))

        claude_dir = tmp_path / ".claude"
        claude_dir.mkdir(parents=True)
        global_path = claude_dir / "settings.json"
        global_path.write_text(json.dumps(VALID_USER_SETTINGS, indent=2))

        # ACT - Call upgrade_existing_settings directly
        # This exercises the real SettingsGenerator integration
        result = configure_global_settings.upgrade_existing_settings(global_path, template_path)

        # ASSERT
        # Verify result is successful
        assert result["success"] is True
        assert result["merged"] is True or "merged" in str(result)  # May be in message

        # Verify settings file was modified
        final_settings = json.loads(global_path.read_text())
        assert "permissions" in final_settings
        assert "allow" in final_settings["permissions"]

        # Verify backup was created (SettingsGenerator creates backup before merge)
        backup_path = global_path.with_suffix(".json.backup")
        assert backup_path.exists(), "Backup should be created by SettingsGenerator"

    def test_backup_creation_before_modification(self, tmp_path):
        """
        Test: Creates backup of existing settings before modification

        Scenario:
        - Existing settings.json present
        - Should create settings.json.backup before any changes
        - Backup should contain original content

        Expected Result:
        - settings.json.backup created
        - Backup contains exact copy of original
        - Original then modified
        """
        # ARRANGE
        template_path = tmp_path / "template.json"
        template_path.write_text(json.dumps(TEMPLATE_SETTINGS, indent=2))

        claude_dir = tmp_path / ".claude"
        claude_dir.mkdir(parents=True)
        global_path = claude_dir / "settings.json"
        original_content = json.dumps(VALID_USER_SETTINGS, indent=2)
        global_path.write_text(original_content)

        backup_path = claude_dir / "settings.json.backup"

        # ACT
        result = configure_global_settings.upgrade_existing_settings(global_path, template_path)

        # ASSERT
        # Verify backup created
        assert backup_path.exists()

        # Verify backup contains original content
        backup_content = backup_path.read_text()
        assert backup_content == original_content

        # Verify original was modified (different from backup)
        current_content = global_path.read_text()
        # Content should be different (merged) but both valid JSON
        assert json.loads(current_content) != json.loads(backup_content)

    def test_handles_permission_errors_gracefully(self, tmp_path):
        """
        Test: Gracefully handles permission errors during file operations

        Scenario:
        - Template file doesn't exist (simulating permission issue)
        - Should catch error
        - Should return error JSON
        - Should exit 0 (non-blocking)

        Expected Result:
        - Error returned in JSON
        - No crash or exception
        - Function returns gracefully
        """
        # ARRANGE
        # Use non-existent template to simulate permission/access issue
        template_path = tmp_path / "nonexistent_template.json"
        assert not template_path.exists()

        claude_dir = tmp_path / ".claude"
        global_path = claude_dir / "settings.json"

        # ACT
        result = configure_global_settings.create_fresh_settings(template_path, global_path)

        # ASSERT
        # Should return error but not crash
        assert result["success"] is False
        assert result["created"] is False
        assert "error" in result or "not found" in result.get("message", "").lower()


# Test fixtures and helpers
@pytest.fixture
def clean_test_env(tmp_path):
    """Provide clean isolated test environment"""
    test_claude_dir = tmp_path / ".claude"
    test_template = tmp_path / "template.json"

    yield {
        "claude_dir": test_claude_dir,
        "template": test_template,
        "settings": test_claude_dir / "settings.json"
    }

    # Cleanup
    if test_claude_dir.exists():
        shutil.rmtree(test_claude_dir)


if __name__ == "__main__":
    # Run tests with pytest
    pytest.main([__file__, "-v", "--tb=short"])
