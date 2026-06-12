"""Tests for gh issue command context allow-through in unified_pre_tool.py (Issue #630).

Validates that _is_issue_command_active() correctly reads the command context file
and fails-closed on all error conditions.
"""

import json
import os
import sys
import time
from pathlib import Path
from unittest.mock import patch

import pytest

# Add the hooks directory to sys.path so we can import the function under test
HOOKS_DIR = str(
    Path(__file__).resolve().parent.parent.parent.parent
    / "plugins"
    / "autonomous-dev"
    / "hooks"
)
LIB_DIR = str(
    Path(__file__).resolve().parent.parent.parent.parent
    / "plugins"
    / "autonomous-dev"
    / "lib"
)
if HOOKS_DIR not in sys.path:
    sys.path.insert(0, HOOKS_DIR)
if LIB_DIR not in sys.path:
    sys.path.insert(0, LIB_DIR)

from unified_pre_tool import (
    GH_ISSUE_COMMAND_CONTEXT_PATH,
    GH_ISSUE_COMMANDS,
    PROTECTED_ENV_VARS,
    _is_issue_command_active,
)


class TestIsIssueCommandActive:
    """Tests for _is_issue_command_active() fail-closed behavior."""

    def test_returns_true_with_valid_context_and_fresh_timestamp(self, tmp_path):
        """Valid context file with a recognized command and fresh mtime => True."""
        ctx_file = tmp_path / "ctx.json"
        ctx_file.write_text(
            json.dumps({
                "command": "create-issue",
                "timestamp": "2026-03-30T00:00:00+00:00",
            }),
            encoding="utf-8",
        )
        with patch(
            "unified_pre_tool.GH_ISSUE_COMMAND_CONTEXT_PATH", str(ctx_file)
        ):
            assert _is_issue_command_active() is True

    def test_returns_false_with_stale_timestamp(self, tmp_path):
        """Context file with mtime older than 1 hour => False."""
        ctx_file = tmp_path / "ctx.json"
        ctx_file.write_text(
            json.dumps({
                "command": "create-issue",
                "timestamp": "2020-01-01T00:00:00+00:00",
            }),
            encoding="utf-8",
        )
        # Set mtime to 2 hours ago
        old_time = time.time() - 7200
        os.utime(ctx_file, (old_time, old_time))

        with patch(
            "unified_pre_tool.GH_ISSUE_COMMAND_CONTEXT_PATH", str(ctx_file)
        ):
            assert _is_issue_command_active() is False

    def test_returns_false_when_file_missing(self):
        """No context file => False (fail-closed)."""
        with patch(
            "unified_pre_tool.GH_ISSUE_COMMAND_CONTEXT_PATH",
            "/tmp/nonexistent_ctx_file_test_630.json",
        ):
            assert _is_issue_command_active() is False

    def test_returns_false_with_invalid_json(self, tmp_path):
        """Corrupted JSON => False (fail-closed)."""
        ctx_file = tmp_path / "ctx.json"
        ctx_file.write_text("not valid json {{{", encoding="utf-8")
        with patch(
            "unified_pre_tool.GH_ISSUE_COMMAND_CONTEXT_PATH", str(ctx_file)
        ):
            assert _is_issue_command_active() is False

    def test_returns_false_with_unknown_command(self, tmp_path):
        """Command not in GH_ISSUE_COMMANDS => False (fail-closed)."""
        ctx_file = tmp_path / "ctx.json"
        ctx_file.write_text(
            json.dumps({
                "command": "evil-command",
                "timestamp": "2026-03-30T00:00:00+00:00",
            }),
            encoding="utf-8",
        )
        with patch(
            "unified_pre_tool.GH_ISSUE_COMMAND_CONTEXT_PATH", str(ctx_file)
        ):
            assert _is_issue_command_active() is False

    def test_autonomous_dev_command_env_is_protected(self):
        """AUTONOMOUS_DEV_COMMAND must be in PROTECTED_ENV_VARS to block spoofing."""
        assert "AUTONOMOUS_DEV_COMMAND" in PROTECTED_ENV_VARS

    @pytest.mark.parametrize("command", sorted(GH_ISSUE_COMMANDS))
    def test_all_known_commands_accepted(self, command, tmp_path):
        """Each command in GH_ISSUE_COMMANDS should be accepted when context is fresh."""
        ctx_file = tmp_path / "ctx.json"
        ctx_file.write_text(
            json.dumps({
                "command": command,
                "timestamp": "2026-03-30T00:00:00+00:00",
            }),
            encoding="utf-8",
        )
        with patch(
            "unified_pre_tool.GH_ISSUE_COMMAND_CONTEXT_PATH", str(ctx_file)
        ):
            assert _is_issue_command_active() is True

    def test_returns_true_for_plan_command(self, tmp_path):
        """Issue #1203 Change A: 'plan' must be in GH_ISSUE_COMMANDS.

        plan.md STEP 6 files issues by design when >=2 independent work items
        are produced. Whitelisting 'plan' here is the minimal fix so the gh
        issue create calls in plan.md pass through.
        """
        assert "plan" in GH_ISSUE_COMMANDS, (
            "Issue #1203 Change A: 'plan' must be in GH_ISSUE_COMMANDS"
        )
        ctx_file = tmp_path / "ctx.json"
        ctx_file.write_text(
            json.dumps({
                "command": "plan",
                "timestamp": "2026-06-11T00:00:00+00:00",
            }),
            encoding="utf-8",
        )
        with patch(
            "unified_pre_tool.GH_ISSUE_COMMAND_CONTEXT_PATH", str(ctx_file)
        ):
            assert _is_issue_command_active() is True
