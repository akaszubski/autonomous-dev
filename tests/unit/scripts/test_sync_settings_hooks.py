#!/usr/bin/env python3
"""
Unit tests for sync_settings_hooks.py CLI script.

Tests the deploy-time settings.json hook synchronization that ensures
all hook lifecycle events are registered after deploy. Updated to test
the _replace_hooks approach (not the old SettingsMerger additive merge).

Issue: GitHub #648
Date: 2026-04-03
Agent: implementer
"""

import json
import os
import sys
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest

# Add plugins directory to path for imports
REPO_ROOT = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(REPO_ROOT / "plugins" / "autonomous-dev" / "scripts"))
sys.path.insert(0, str(REPO_ROOT / "plugins" / "autonomous-dev" / "lib"))

from sync_settings_hooks import (
    _count_lifecycle_events,
    _get_canonical_deny_list,
    _replace_hooks,
    sync_global,
    sync_repo,
)


# --- Fixtures ---

@pytest.fixture
def temp_dir():
    """Temporary directory for test files."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


@pytest.fixture
def global_template():
    """Minimal global settings template with hooks."""
    return {
        "hooks": {
            "PreToolUse": [
                {
                    "matcher": "*",
                    "hooks": [
                        {
                            "type": "command",
                            "command": "python3 ~/.claude/hooks/unified_pre_tool.py",
                            "timeout": 5,
                        }
                    ],
                }
            ],
            "PostToolUse": [
                {
                    "matcher": "*",
                    "hooks": [
                        {
                            "type": "command",
                            "command": "python3 ~/.claude/hooks/session_activity_logger.py",
                            "timeout": 5,
                        }
                    ],
                }
            ],
            "UserPromptSubmit": [
                {
                    "matcher": "*",
                    "hooks": [
                        {
                            "type": "command",
                            "command": "python3 ~/.claude/hooks/unified_prompt_validator.py",
                            "timeout": 5,
                        }
                    ],
                }
            ],
            "Stop": [
                {
                    "matcher": "*",
                    "hooks": [
                        {
                            "type": "command",
                            "command": "python3 ~/.claude/hooks/stop_quality_gate.py",
                            "timeout": 60,
                        }
                    ],
                }
            ],
            "SubagentStop": [
                {
                    "matcher": "*",
                    "hooks": [
                        {
                            "type": "command",
                            "command": "python3 ~/.claude/hooks/unified_session_tracker.py",
                            "timeout": 5,
                        }
                    ],
                }
            ],
            "TaskCompleted": [
                {
                    "matcher": "*",
                    "hooks": [
                        {
                            "type": "command",
                            "command": "python3 ~/.claude/hooks/task_completed_handler.py",
                            "timeout": 5,
                        }
                    ],
                }
            ],
            "PreCompact": [
                {
                    "matcher": "*",
                    "hooks": [
                        {
                            "type": "command",
                            "command": "bash ~/.claude/hooks/pre_compact_batch_saver.sh",
                            "timeout": 5,
                        }
                    ],
                }
            ],
            "PostCompact": [
                {
                    "matcher": "*",
                    "hooks": [
                        {
                            "type": "command",
                            "command": "bash ~/.claude/hooks/post_compact_enricher.sh",
                            "timeout": 5,
                        }
                    ],
                }
            ],
        },
        "permissions": {
            "allow": ["Read", "Write", "Edit"],
            "deny": ["Bash(rm -rf /)"],
        },
    }


@pytest.fixture
def repo_template():
    """Minimal repo settings template with hooks."""
    return {
        "hooks": {
            "PreToolUse": [
                {
                    "matcher": "*",
                    "hooks": [
                        {
                            "type": "command",
                            "command": "python3 ~/.claude/hooks/unified_pre_tool.py",
                            "timeout": 5,
                        }
                    ],
                }
            ],
            "PostToolUse": [
                {
                    "matcher": "*",
                    "hooks": [
                        {
                            "type": "command",
                            "command": "python3 ~/.claude/hooks/session_activity_logger.py",
                            "timeout": 5,
                        }
                    ],
                }
            ],
            "UserPromptSubmit": [
                {
                    "matcher": "*",
                    "hooks": [
                        {
                            "type": "command",
                            "command": "python3 ~/.claude/hooks/unified_prompt_validator.py",
                            "timeout": 5,
                        }
                    ],
                }
            ],
            "Stop": [
                {
                    "matcher": "",
                    "hooks": [
                        {
                            "type": "command",
                            "command": "python3 ~/.claude/hooks/stop_quality_gate.py",
                            "timeout": 60,
                        }
                    ],
                }
            ],
        },
        "permissions": {
            "allow": ["Read", "Write"],
            "deny": [],
        },
    }


def _write_json(path: Path, data: dict) -> None:
    """Helper to write JSON to a file."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")


# --- Tests ---


class TestReplaceHooks:
    """Tests for _replace_hooks core function."""

    def test_creates_settings_when_missing(self, temp_dir, global_template):
        """No existing settings.json -> creates from template hooks."""
        template_path = temp_dir / "template.json"
        _write_json(template_path, global_template)

        settings_path = temp_dir / "output" / "settings.json"

        result = _replace_hooks(settings_path, template_path)

        assert result["success"] is True
        assert settings_path.exists()
        data = json.loads(settings_path.read_text())
        assert "hooks" in data
        assert len(data["hooks"]) == 8

    def test_replaces_hooks_preserving_user_config(self, temp_dir, global_template):
        """Existing settings with user config -> preserved after replace."""
        template_path = temp_dir / "template.json"
        _write_json(template_path, global_template)

        existing = {
            "hooks": {
                "PreToolUse": [{"matcher": "*", "hooks": [{"type": "command", "command": "old"}]}],
            },
            "permissions": {
                "allow": ["Read", "Write", "Edit", "CustomTool"],
                "deny": ["Bash(rm -rf /)", "Bash(custom:danger)"],
            },
            "mcpServers": {
                "my-server": {"url": "http://localhost:3000"}
            },
            "enabledPlugins": ["my-plugin"],
        }
        settings_path = temp_dir / "settings.json"
        _write_json(settings_path, existing)

        result = _replace_hooks(settings_path, template_path)

        assert result["success"] is True
        data = json.loads(settings_path.read_text())

        # User config preserved
        assert "mcpServers" in data
        assert data["mcpServers"]["my-server"]["url"] == "http://localhost:3000"
        assert "enabledPlugins" in data
        assert "my-plugin" in data["enabledPlugins"]

        # User permission entries preserved (untouched) -- but NOTE:
        # `allow`/`ask` are left alone; `deny` is deliberately NOT a "user
        # customization" surface. Since commit 320d4ce0 (#814) and
        # reinforced by the Issue #1409 Write->Edit deny-pattern migration,
        # `_replace_hooks` wholesale-syncs `permissions.deny` from the
        # canonical `settings_generator.DEFAULT_DENY_LIST` on every deploy
        # specifically so stale/invalid/missing security patterns cannot
        # persist -- a purely custom entry like "Bash(custom:danger)" that
        # isn't part of the canonical list does not survive a sync.
        # Retargeted 2026-08-23; see docstring of sync_settings_hooks.py.
        assert "CustomTool" in data["permissions"]["allow"]
        assert data["permissions"]["deny"] == _get_canonical_deny_list()
        assert "Bash(custom:danger)" not in data["permissions"]["deny"]

        # Template hooks replaced entirely
        assert len(data["hooks"]) == 8

    def test_dry_run_no_write(self, temp_dir, global_template):
        """Dry-run computes but does not write."""
        template_path = temp_dir / "template.json"
        _write_json(template_path, global_template)

        settings_path = temp_dir / "settings.json"

        result = _replace_hooks(settings_path, template_path, dry_run=True)

        assert result["success"] is True
        assert not settings_path.exists()


class TestGlobalMode:
    """Tests for --global mode (sync_global function)."""

    def test_global_mode_creates_settings_when_missing(self, temp_dir, global_template):
        """No existing settings.json -> creates from template."""
        fake_home = temp_dir / "home"
        fake_home.mkdir()

        template_path = temp_dir / "config" / "global_settings_template.json"
        _write_json(template_path, global_template)

        settings_path = fake_home / ".claude" / "settings.json"

        with patch("sync_settings_hooks._find_plugin_root", return_value=temp_dir), \
             patch("sync_settings_hooks.Path") as MockPath:
            # Path.home() returns fake_home, but Path() still works normally
            MockPath.home.return_value = fake_home
            # Make Path() calls pass through to real Path
            MockPath.side_effect = Path
            MockPath.home = lambda: fake_home

            # Directly test _replace_hooks since patching Path is fragile
        result = _replace_hooks(settings_path, template_path)

        assert result["success"] is True
        assert settings_path.exists()
        data = json.loads(settings_path.read_text())
        assert "hooks" in data
        assert len(data["hooks"]) == 8

    def test_global_mode_preserves_user_config(self, temp_dir, global_template):
        """Existing settings with user config -> preserved after sync."""
        template_path = temp_dir / "config" / "global_settings_template.json"
        _write_json(template_path, global_template)

        existing = {
            "hooks": {
                "PreToolUse": [{"matcher": "*", "hooks": [{"type": "command", "command": "old"}]}],
            },
            "permissions": {
                "allow": ["Read", "Write", "Edit", "CustomTool"],
                "deny": ["Bash(rm -rf /)", "Bash(custom:danger)"],
            },
            "mcpServers": {
                "my-server": {"url": "http://localhost:3000"}
            },
            "enabledPlugins": ["my-plugin"],
        }
        settings_path = temp_dir / "settings.json"
        _write_json(settings_path, existing)

        result = _replace_hooks(settings_path, template_path)

        assert result["success"] is True
        data = json.loads(settings_path.read_text())

        # User config preserved
        assert "mcpServers" in data
        assert data["mcpServers"]["my-server"]["url"] == "http://localhost:3000"
        assert "enabledPlugins" in data
        assert "my-plugin" in data["enabledPlugins"]
        assert "CustomTool" in data["permissions"]["allow"]
        # `deny` is synced wholesale from the canonical DEFAULT_DENY_LIST on
        # every sync (Issue #814/#1409) -- a purely custom entry does not
        # survive. Retargeted 2026-08-23; see TestReplaceHooks equivalent.
        assert data["permissions"]["deny"] == _get_canonical_deny_list()
        assert "Bash(custom:danger)" not in data["permissions"]["deny"]

        # Template hooks replaced
        assert len(data["hooks"]) == 8


class TestRepoMode:
    """Tests for --repo mode."""

    def test_repo_mode_replaces_hooks(self, temp_dir, repo_template):
        """Per-repo template hooks replaced correctly into repo settings."""
        template_path = temp_dir / "templates" / "settings.default.json"
        _write_json(template_path, repo_template)

        settings_path = temp_dir / "settings.json"
        _write_json(settings_path, {})

        result = _replace_hooks(settings_path, template_path)

        assert result["success"] is True
        data = json.loads(settings_path.read_text())
        assert "PreToolUse" in data["hooks"]
        assert "PostToolUse" in data["hooks"]
        assert "UserPromptSubmit" in data["hooks"]
        assert "Stop" in data["hooks"]
        assert len(data["hooks"]) == 4


class TestIdempotency:
    """Tests for idempotent behavior."""

    def test_idempotent_double_run(self, temp_dir, global_template):
        """Running replace twice produces identical output."""
        template_path = temp_dir / "template.json"
        _write_json(template_path, global_template)

        settings_path = temp_dir / "settings.json"

        # First run
        result1 = _replace_hooks(settings_path, template_path)
        data_after_first = json.loads(settings_path.read_text())

        # Second run
        result2 = _replace_hooks(settings_path, template_path)
        data_after_second = json.loads(settings_path.read_text())

        assert result1["success"] is True
        assert result2["success"] is True
        assert data_after_first == data_after_second


class TestDryRun:
    """Tests for --dry-run mode."""

    def test_dry_run_no_write(self, temp_dir, global_template):
        """Dry-run reads but does not write."""
        template_path = temp_dir / "template.json"
        _write_json(template_path, global_template)

        settings_path = temp_dir / "settings.json"

        result = _replace_hooks(settings_path, template_path, dry_run=True)

        assert result["success"] is True
        assert not settings_path.exists()


class TestCountOnly:
    """Tests for --count-only mode."""

    def test_count_only_output(self, temp_dir, global_template):
        """Returns correct hook count."""
        settings_path = temp_dir / "settings.json"
        _write_json(settings_path, global_template)

        count = _count_lifecycle_events(settings_path)
        assert count == 8


class TestMigration:
    """Tests for hook replacement of old hooks."""

    def test_old_hooks_replaced(self, temp_dir, global_template):
        """Old/deprecated hooks are replaced entirely by template hooks."""
        template_path = temp_dir / "template.json"
        _write_json(template_path, global_template)

        existing = {
            "hooks": {
                "PreToolUse": [
                    {
                        "matcher": "*",
                        "hooks": [
                            {
                                "type": "command",
                                "command": "python3 ~/.claude/hooks/pre_tool_use.py",
                                "timeout": 5,
                            },
                            {
                                "type": "command",
                                "command": "python3 ~/.claude/hooks/enforce_implementation_workflow.py",
                                "timeout": 5,
                            },
                        ],
                    }
                ],
            },
        }
        settings_path = temp_dir / "settings.json"
        _write_json(settings_path, existing)

        result = _replace_hooks(settings_path, template_path)

        assert result["success"] is True

        data = json.loads(settings_path.read_text())
        # Verify old hooks are gone (replaced by template)
        for event_hooks in data["hooks"].values():
            for matcher_config in event_hooks:
                for hook in matcher_config.get("hooks", []):
                    cmd = hook.get("command", "")
                    assert "pre_tool_use.py" not in cmd
                    assert "enforce_implementation_workflow.py" not in cmd


class TestErrorHandling:
    """Tests for error conditions."""

    def test_missing_template_error(self, temp_dir):
        """sync_global returns error when template not found."""
        with patch("sync_settings_hooks._find_plugin_root", return_value=temp_dir):
            result = sync_global()

        assert result["success"] is False
        assert "not found" in result["message"].lower() or "template" in result["message"].lower()

    def test_invalid_json_settings(self, temp_dir):
        """_replace_hooks raises on corrupt settings.json."""
        template_path = temp_dir / "template.json"
        _write_json(template_path, {"hooks": {}})

        settings_path = temp_dir / "settings.json"
        settings_path.write_text("{invalid json!!!", encoding="utf-8")

        with pytest.raises(json.JSONDecodeError):
            _replace_hooks(settings_path, template_path)


class TestPermissions:
    """Tests for permission list handling."""

    def test_permissions_preserved(self, temp_dir):
        """User permissions are untouched by hook replacement."""
        template = {
            "hooks": {"PreToolUse": [{"matcher": "*", "hooks": []}]},
            "permissions": {
                "allow": ["Read", "Write", "Edit"],
                "deny": ["Bash(rm -rf /)"],
            },
        }
        template_path = temp_dir / "template.json"
        _write_json(template_path, template)

        existing = {
            "hooks": {},
            "permissions": {
                "allow": ["Read", "Write", "CustomUserTool", "MyMCPTool"],
                "deny": ["Bash(rm -rf /)", "Bash(my-custom-deny)"],
                "ask": ["Bash(git push:*)"],
            },
        }
        settings_path = temp_dir / "settings.json"
        _write_json(settings_path, existing)

        result = _replace_hooks(settings_path, template_path)

        assert result["success"] is True
        data = json.loads(settings_path.read_text())

        # User permission entries preserved (untouched - replace only touches
        # hooks) EXCEPT `deny`, which is deliberately re-synced wholesale
        # from the canonical DEFAULT_DENY_LIST on every deploy (Issue
        # #814/#1409) so a purely custom entry does not survive.
        # Retargeted 2026-08-23; see TestReplaceHooks for full rationale.
        assert "CustomUserTool" in data["permissions"]["allow"]
        assert "MyMCPTool" in data["permissions"]["allow"]
        assert data["permissions"]["deny"] == _get_canonical_deny_list()
        assert "Bash(my-custom-deny)" not in data["permissions"]["deny"]
        assert "Bash(git push:*)" in data["permissions"]["ask"]
