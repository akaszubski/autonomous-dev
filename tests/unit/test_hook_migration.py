"""
Regression tests for hook migration (Issue #144).

These tests ensure that when unified hooks are added, old hooks are properly
removed to prevent duplicate processing.

Test scenarios:
1. Old hooks are removed when unified hooks are added
2. Non-replaced hooks are preserved
3. User customizations are preserved
4. Fresh install works correctly
"""

import json
import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock

# Import the settings merger
import sys
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "plugins" / "autonomous-dev" / "lib"))
from settings_merger import SettingsMerger, MergeResult, UNIFIED_HOOK_REPLACEMENTS


class TestHookMigration:
    """Test hook migration from old hooks to unified hooks."""

    def test_unified_hook_replacements_defined(self):
        """Verify all unified hooks have replacement mappings."""
        expected_unified = {
            "unified_pre_tool.py",
            "unified_prompt_validator.py",
            "unified_post_tool.py",
            "unified_session_tracker.py",
            "unified_git_automation.py",
        }
        assert set(UNIFIED_HOOK_REPLACEMENTS.keys()) == expected_unified

    def test_old_hooks_removed_when_unified_added(self):
        """Test that old hooks are removed when unified hooks are added."""
        merger = SettingsMerger(project_root=Path.cwd())

        # Existing settings with old hooks
        existing = {
            "PreToolUse": [
                {
                    "matcher": "*",
                    "hooks": [
                        {"type": "command", "command": "python3 ~/.claude/hooks/pre_tool_use.py", "timeout": 5}
                    ]
                }
            ]
        }

        # New template with unified hook
        new = {
            "PreToolUse": [
                {
                    "matcher": "*",
                    "hooks": [
                        {"type": "command", "command": "python3 ~/.claude/hooks/unified_pre_tool.py", "timeout": 5}
                    ]
                }
            ]
        }

        merged, added, preserved, migrated = merger._merge_hooks(existing, new)

        # Old hook should be migrated (removed)
        assert migrated == 1, "Old hook should be migrated"

        # New unified hook should be added
        assert added == 1, "Unified hook should be added"

        # Check that only unified hook is in result
        pre_tool_hooks = merged.get("PreToolUse", [])
        hook_commands = []
        for matcher_config in pre_tool_hooks:
            if isinstance(matcher_config, dict) and "hooks" in matcher_config:
                for hook in matcher_config["hooks"]:
                    if isinstance(hook, dict):
                        hook_commands.append(hook.get("command", ""))
            elif isinstance(matcher_config, dict):
                hook_commands.append(matcher_config.get("command", ""))

        assert any("unified_pre_tool.py" in cmd for cmd in hook_commands), "Unified hook should be present"
        assert not any("pre_tool_use.py" in cmd and "unified" not in cmd for cmd in hook_commands), "Old hook should be removed"

    def test_non_replaced_hooks_preserved(self):
        """Test that hooks not replaced by unified hooks are preserved."""
        merger = SettingsMerger(project_root=Path.cwd())

        # Existing settings with custom hook
        existing = {
            "PreCommit": [
                {
                    "matcher": "*",
                    "hooks": [
                        {"type": "command", "command": "python3 ~/.claude/hooks/my_custom_hook.py", "timeout": 5}
                    ]
                }
            ]
        }

        # New template with unified hook (different lifecycle)
        new = {
            "PreToolUse": [
                {
                    "matcher": "*",
                    "hooks": [
                        {"type": "command", "command": "python3 ~/.claude/hooks/unified_pre_tool.py", "timeout": 5}
                    ]
                }
            ]
        }

        merged, added, preserved, migrated = merger._merge_hooks(existing, new)

        # Custom hook should be preserved
        assert preserved == 1, "Custom hook should be preserved"
        assert migrated == 0, "No hooks should be migrated"

        # Check PreCommit still has custom hook
        assert "PreCommit" in merged
        pre_commit_hooks = merged["PreCommit"]
        assert len(pre_commit_hooks) == 1

    def test_multiple_old_hooks_migrated(self):
        """Test that multiple old hooks are all migrated."""
        merger = SettingsMerger(project_root=Path.cwd())

        # Existing settings with multiple old hooks that unified_pre_tool replaces
        existing = {
            "PreToolUse": [
                {
                    "matcher": "*",
                    "hooks": [
                        {"type": "command", "command": "python3 ~/.claude/hooks/pre_tool_use.py", "timeout": 5},
                        {"type": "command", "command": "python3 ~/.claude/hooks/enforce_implementation_workflow.py", "timeout": 5},
                        {"type": "command", "command": "python3 ~/.claude/hooks/batch_permission_approver.py", "timeout": 5},
                    ]
                }
            ]
        }

        # New template with unified hook
        new = {
            "PreToolUse": [
                {
                    "matcher": "*",
                    "hooks": [
                        {"type": "command", "command": "python3 ~/.claude/hooks/unified_pre_tool.py", "timeout": 5}
                    ]
                }
            ]
        }

        merged, added, preserved, migrated = merger._merge_hooks(existing, new)

        # All 3 old hooks should be migrated
        assert migrated == 3, f"All 3 old hooks should be migrated, got {migrated}"

        # Only unified hook should remain
        assert added == 1, "Unified hook should be added"

    def test_fresh_install_no_migration(self):
        """Test that fresh install (no existing hooks) doesn't migrate anything."""
        merger = SettingsMerger(project_root=Path.cwd())

        # Empty existing settings
        existing = {}

        # New template with unified hooks
        new = {
            "PreToolUse": [
                {
                    "matcher": "*",
                    "hooks": [
                        {"type": "command", "command": "python3 ~/.claude/hooks/unified_pre_tool.py", "timeout": 5}
                    ]
                }
            ]
        }

        merged, added, preserved, migrated = merger._merge_hooks(existing, new)

        # No migration on fresh install
        assert migrated == 0, "No hooks should be migrated on fresh install"
        assert preserved == 0, "No hooks to preserve on fresh install"
        assert added == 1, "Unified hook should be added"


class TestHookMigrationEndToEnd:
    """End-to-end tests for hook migration during settings merge."""

    def test_settings_merge_with_migration(self, tmp_path):
        """Test full settings merge with hook migration."""
        # Create user settings with old hooks
        user_settings = {
            "hooks": {
                "PreToolUse": [
                    {
                        "matcher": "*",
                        "hooks": [
                            {"type": "command", "command": "python3 ~/.claude/hooks/pre_tool_use.py", "timeout": 5}
                        ]
                    }
                ]
            },
            "permissions": {"allow": ["Read(**)"]}
        }

        # Create template with unified hooks
        template_settings = {
            "hooks": {
                "PreToolUse": [
                    {
                        "matcher": "*",
                        "hooks": [
                            {"type": "command", "command": "python3 ~/.claude/hooks/unified_pre_tool.py", "timeout": 5}
                        ]
                    }
                ]
            }
        }

        user_path = tmp_path / "settings.json"
        template_path = tmp_path / "template.json"

        user_path.write_text(json.dumps(user_settings))
        template_path.write_text(json.dumps(template_settings))

        # Mock validate_path to allow test paths
        with patch('settings_merger.validate_path', return_value=(True, "")):
            merger = SettingsMerger(project_root=tmp_path)
            result = merger.merge_settings(
                template_path=template_path,
                user_path=user_path,
                write_result=True
            )

        assert result.success, f"Merge should succeed: {result.message}"
        assert result.hooks_migrated == 1, f"Should migrate 1 hook, got {result.hooks_migrated}"

        # Verify file contents
        merged = json.loads(user_path.read_text())
        pre_tool_hooks = merged["hooks"]["PreToolUse"]

        # Extract all hook commands
        hook_commands = []
        for item in pre_tool_hooks:
            if isinstance(item, dict):
                if "hooks" in item:
                    for h in item["hooks"]:
                        if isinstance(h, dict):
                            hook_commands.append(h.get("command", ""))
                else:
                    hook_commands.append(item.get("command", ""))

        # Verify only unified hook present
        assert any("unified_pre_tool.py" in cmd for cmd in hook_commands), "Unified hook should be present"
        assert not any("pre_tool_use.py" in cmd and "unified" not in cmd for cmd in hook_commands), "Old hook should be removed"


class TestNoDoubleHooks:
    """Regression tests to ensure no duplicate hooks after upgrade."""

    def test_upgrade_does_not_create_duplicates(self, tmp_path):
        """Critical: Ensure upgrade doesn't result in both old and new hooks."""
        # Simulate existing user settings
        user_settings = {
            "hooks": {
                "PreToolUse": [
                    {
                        "matcher": "*",
                        "hooks": [
                            {"type": "command", "command": "MCP_AUTO_APPROVE=true python3 ~/.claude/hooks/pre_tool_use.py", "timeout": 5}
                        ]
                    }
                ],
                "UserPromptSubmit": [
                    {
                        "matcher": "*",
                        "hooks": [
                            {"type": "command", "command": "python3 ~/.claude/hooks/detect_feature_request.py", "timeout": 5}
                        ]
                    }
                ]
            }
        }

        # Template with unified hooks
        template_settings = {
            "hooks": {
                "PreToolUse": [
                    {
                        "matcher": "*",
                        "hooks": [
                            {"type": "command", "command": "MCP_AUTO_APPROVE=true python3 ~/.claude/hooks/unified_pre_tool.py", "timeout": 5}
                        ]
                    }
                ],
                "UserPromptSubmit": [
                    {
                        "matcher": "*",
                        "hooks": [
                            {"type": "command", "command": "python3 ~/.claude/hooks/unified_prompt_validator.py", "timeout": 5}
                        ]
                    }
                ]
            }
        }

        user_path = tmp_path / "settings.json"
        template_path = tmp_path / "template.json"

        user_path.write_text(json.dumps(user_settings))
        template_path.write_text(json.dumps(template_settings))

        with patch('settings_merger.validate_path', return_value=(True, "")):
            merger = SettingsMerger(project_root=tmp_path)
            result = merger.merge_settings(
                template_path=template_path,
                user_path=user_path,
                write_result=True
            )

        # Load merged settings
        merged = json.loads(user_path.read_text())

        # Count hooks per lifecycle
        for lifecycle in ["PreToolUse", "UserPromptSubmit"]:
            hooks = merged["hooks"].get(lifecycle, [])
            hook_commands = []
            for item in hooks:
                if isinstance(item, dict) and "hooks" in item:
                    for h in item["hooks"]:
                        if isinstance(h, dict):
                            hook_commands.append(h.get("command", ""))

            # Should have exactly 1 hook command per lifecycle (the unified one)
            # Not 2 (old + unified)
            assert len(hook_commands) == 1, f"{lifecycle} should have exactly 1 hook, got {len(hook_commands)}: {hook_commands}"
            assert "unified" in hook_commands[0], f"{lifecycle} should have unified hook, got: {hook_commands[0]}"
