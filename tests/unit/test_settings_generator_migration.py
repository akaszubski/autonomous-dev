"""
Regression tests for settings_generator hook migration (Issue #144).

These tests ensure that settings_generator (used by install.sh) properly
migrates old hooks to unified hooks during upgrades.

Test scenarios:
1. Fresh install uses template hooks correctly
2. Upgrade removes old hooks when unified hooks are in template
3. User custom hooks are preserved
4. No duplicate hooks after upgrade
"""

import json
import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock
import sys

# Import the settings generator
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "plugins" / "autonomous-dev" / "lib"))
from settings_generator import SettingsGenerator


class TestSettingsGeneratorHookMigration:
    """Test hook migration in settings_generator._deep_merge_settings()."""

    @pytest.fixture
    def mock_generator(self, tmp_path):
        """Create a mock generator for testing."""
        # Create minimal plugin structure for generator initialization
        plugin_dir = tmp_path / "plugins" / "autonomous-dev"
        commands_dir = plugin_dir / "commands"
        commands_dir.mkdir(parents=True)
        (commands_dir / "test-command.md").write_text("# Test")

        return SettingsGenerator(plugin_dir=plugin_dir)

    def test_deep_merge_removes_old_hooks(self, mock_generator):
        """Test that old hooks are removed when unified hooks are in template."""
        # Template with unified hook
        template = {
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

        # User settings with old hook
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
            }
        }

        merged = mock_generator._deep_merge_settings(template, user_settings, fix_wildcards=False)

        # Extract hook commands
        hook_commands = []
        for matcher_config in merged["hooks"]["PreToolUse"]:
            if isinstance(matcher_config, dict) and "hooks" in matcher_config:
                for hook in matcher_config["hooks"]:
                    if isinstance(hook, dict):
                        hook_commands.append(hook.get("command", ""))

        # Should have unified hook, NOT old hook
        assert any("unified_pre_tool.py" in cmd for cmd in hook_commands), "Unified hook should be present"
        assert not any("pre_tool_use.py" in cmd and "unified" not in cmd for cmd in hook_commands), "Old hook should be removed"

    def test_deep_merge_removes_multiple_old_hooks(self, mock_generator):
        """Test that multiple old hooks are all removed."""
        # Template with unified hook
        template = {
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

        # User settings with multiple old hooks that unified_pre_tool replaces
        user_settings = {
            "hooks": {
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
        }

        merged = mock_generator._deep_merge_settings(template, user_settings, fix_wildcards=False)

        # Extract hook commands
        hook_commands = []
        for matcher_config in merged["hooks"]["PreToolUse"]:
            if isinstance(matcher_config, dict) and "hooks" in matcher_config:
                for hook in matcher_config["hooks"]:
                    if isinstance(hook, dict):
                        hook_commands.append(hook.get("command", ""))

        # Should only have unified hook
        assert len(hook_commands) == 1, f"Should have exactly 1 hook, got {len(hook_commands)}: {hook_commands}"
        assert "unified_pre_tool.py" in hook_commands[0], "Should be the unified hook"

    def test_deep_merge_preserves_custom_hooks(self, mock_generator):
        """Test that custom hooks not replaced by unified hooks are preserved."""
        # Template with unified hook
        template = {
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

        # User settings with custom hook (should be preserved) and old hook (should be removed)
        user_settings = {
            "hooks": {
                "PreToolUse": [
                    {
                        "matcher": "*",
                        "hooks": [
                            {"type": "command", "command": "python3 ~/.claude/hooks/pre_tool_use.py", "timeout": 5},
                            {"type": "command", "command": "python3 ~/.claude/hooks/my_custom_hook.py", "timeout": 5},
                        ]
                    }
                ]
            }
        }

        merged = mock_generator._deep_merge_settings(template, user_settings, fix_wildcards=False)

        # Extract hook commands
        hook_commands = []
        for matcher_config in merged["hooks"]["PreToolUse"]:
            if isinstance(matcher_config, dict) and "hooks" in matcher_config:
                for hook in matcher_config["hooks"]:
                    if isinstance(hook, dict):
                        hook_commands.append(hook.get("command", ""))

        # Should have unified hook AND custom hook, but NOT old hook
        assert any("unified_pre_tool.py" in cmd for cmd in hook_commands), "Unified hook should be present"
        assert any("my_custom_hook.py" in cmd for cmd in hook_commands), "Custom hook should be preserved"
        assert not any("pre_tool_use.py" in cmd and "unified" not in cmd for cmd in hook_commands), "Old hook should be removed"

    def test_deep_merge_handles_different_lifecycle_hooks(self, mock_generator):
        """Test that hooks in different lifecycles are all migrated correctly."""
        # Template with all unified hooks
        template = {
            "hooks": {
                "UserPromptSubmit": [
                    {
                        "matcher": "*",
                        "hooks": [
                            {"type": "command", "command": "python3 ~/.claude/hooks/unified_prompt_validator.py", "timeout": 5}
                        ]
                    }
                ],
                "PreToolUse": [
                    {
                        "matcher": "*",
                        "hooks": [
                            {"type": "command", "command": "python3 ~/.claude/hooks/unified_pre_tool.py", "timeout": 5}
                        ]
                    }
                ],
                "SubagentStop": [
                    {
                        "matcher": "*",
                        "hooks": [
                            {"type": "command", "command": "python3 ~/.claude/hooks/unified_session_tracker.py", "timeout": 5}
                        ]
                    }
                ]
            }
        }

        # User settings with old hooks across lifecycles
        user_settings = {
            "hooks": {
                "UserPromptSubmit": [
                    {
                        "matcher": "*",
                        "hooks": [
                            {"type": "command", "command": "python3 ~/.claude/hooks/detect_feature_request.py", "timeout": 5}
                        ]
                    }
                ],
                "PreToolUse": [
                    {
                        "matcher": "*",
                        "hooks": [
                            {"type": "command", "command": "python3 ~/.claude/hooks/pre_tool_use.py", "timeout": 5}
                        ]
                    }
                ],
                "SubagentStop": [
                    {
                        "matcher": "*",
                        "hooks": [
                            {"type": "command", "command": "python3 ~/.claude/hooks/session_tracker.py", "timeout": 5},
                            {"type": "command", "command": "python3 ~/.claude/hooks/log_agent_completion.py", "timeout": 5}
                        ]
                    }
                ]
            }
        }

        merged = mock_generator._deep_merge_settings(template, user_settings, fix_wildcards=False)

        # Check each lifecycle only has unified hook
        for lifecycle in ["UserPromptSubmit", "PreToolUse", "SubagentStop"]:
            hook_commands = []
            for matcher_config in merged["hooks"][lifecycle]:
                if isinstance(matcher_config, dict) and "hooks" in matcher_config:
                    for hook in matcher_config["hooks"]:
                        if isinstance(hook, dict):
                            hook_commands.append(hook.get("command", ""))

            assert len(hook_commands) == 1, f"{lifecycle} should have exactly 1 hook, got {len(hook_commands)}: {hook_commands}"
            assert "unified" in hook_commands[0], f"{lifecycle} should have unified hook"


class TestSettingsGeneratorEndToEnd:
    """End-to-end tests for settings_generator hook migration."""

    def test_merge_global_settings_with_migration(self, tmp_path):
        """Test full merge_global_settings() with hook migration."""
        # Create template with unified hooks
        template = {
            "permissions": {"allow": ["Read(**)", "Write(**)"], "deny": []},
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
        template_path = tmp_path / "template.json"
        template_path.write_text(json.dumps(template))

        # Create user settings with old hooks
        user_settings = {
            "permissions": {"allow": ["Read(**)", "Write(**)"], "deny": []},
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
            "custom_key": "preserved"
        }
        global_path = tmp_path / "settings.json"
        global_path.write_text(json.dumps(user_settings))

        # Create generator with project_root (allows missing plugin dir)
        generator = SettingsGenerator(project_root=tmp_path)

        # Merge settings
        merged = generator.merge_global_settings(
            global_path=global_path,
            template_path=template_path,
            fix_wildcards=True,
            create_backup=True
        )

        # Verify old hook was removed
        hook_commands = []
        for matcher_config in merged["hooks"]["PreToolUse"]:
            if isinstance(matcher_config, dict) and "hooks" in matcher_config:
                for hook in matcher_config["hooks"]:
                    if isinstance(hook, dict):
                        hook_commands.append(hook.get("command", ""))

        assert any("unified_pre_tool.py" in cmd for cmd in hook_commands), "Unified hook should be present"
        assert not any("pre_tool_use.py" in cmd and "unified" not in cmd for cmd in hook_commands), "Old hook should be removed"

        # Verify custom key was preserved
        assert merged.get("custom_key") == "preserved", "Custom keys should be preserved"

        # Verify file was written
        written = json.loads(global_path.read_text())
        assert "unified_pre_tool.py" in str(written), "Unified hook should be in written file"


class TestNoDoubleHooksOnUpgrade:
    """Critical regression tests to prevent duplicate hooks after upgrade."""

    def test_install_upgrade_no_duplicates(self, tmp_path):
        """Critical: Simulate install.sh upgrade - no duplicate hooks."""
        # This simulates what install.sh does via configure_global_settings.py

        # Create template (what install.sh uses)
        template = {
            "permissions": {"allow": ["Read(**)", "Write(**)"], "deny": []},
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
        template_path = tmp_path / "template.json"
        template_path.write_text(json.dumps(template))

        # Simulate existing user settings (before upgrade)
        user_settings = {
            "permissions": {"allow": ["Read(**)", "Write(**)"], "deny": []},
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
        global_path = tmp_path / "settings.json"
        global_path.write_text(json.dumps(user_settings))

        # Run upgrade (what install.sh does)
        generator = SettingsGenerator(project_root=tmp_path)
        merged = generator.merge_global_settings(
            global_path=global_path,
            template_path=template_path,
            fix_wildcards=True,
            create_backup=True
        )

        # CRITICAL: Each lifecycle should have exactly 1 hook
        for lifecycle in ["PreToolUse", "UserPromptSubmit"]:
            hook_commands = []
            for matcher_config in merged["hooks"][lifecycle]:
                if isinstance(matcher_config, dict) and "hooks" in matcher_config:
                    for hook in matcher_config["hooks"]:
                        if isinstance(hook, dict):
                            hook_commands.append(hook.get("command", ""))

            # Should have exactly 1 hook (unified), not 2 (old + unified)
            assert len(hook_commands) == 1, f"{lifecycle} should have exactly 1 hook after upgrade, got {len(hook_commands)}: {hook_commands}"
            assert "unified" in hook_commands[0], f"{lifecycle} should have unified hook, got: {hook_commands[0]}"
