"""
Unit tests for unified_pre_tool.py permission logic.

Regression test for bug where disabled layers returned "ask" instead of "allow",
causing every command to prompt for approval.

Issue: Sandbox layer disabled should pass through (allow), not ask.
"""

import json
import subprocess
import sys
from pathlib import Path
import pytest
import os


# Portable path detection
current = Path.cwd()
while current != current.parent:
    if (current / ".git").exists() or (current / ".claude").exists():
        project_root = current
        break
    current = current.parent
else:
    project_root = Path.cwd()

HOOK_PATH = project_root / "plugins/autonomous-dev/hooks/unified_pre_tool.py"


class TestDisabledLayersPassThrough:
    """
    Test that disabled layers return 'allow' (pass through) not 'ask'.

    This is a regression test for the bug where SANDBOX_ENABLED=false
    caused the sandbox layer to return 'ask', which then caused
    the combine_decisions logic to return 'ask' for every command.
    """

    def run_hook(self, tool_name: str, tool_input: dict, env_overrides: dict = None) -> dict:
        """Run the hook with given input and environment variables."""
        env = os.environ.copy()
        env.update(env_overrides or {})

        input_data = json.dumps({"tool_name": tool_name, "tool_input": tool_input})

        result = subprocess.run(
            [sys.executable, str(HOOK_PATH)],
            input=input_data,
            capture_output=True,
            text=True,
            env=env,
            cwd=str(project_root)
        )

        if result.returncode != 0:
            pytest.fail(f"Hook failed: {result.stderr}")

        return json.loads(result.stdout)

    def test_sandbox_disabled_returns_allow(self):
        """
        REGRESSION TEST: When SANDBOX_ENABLED=false, sandbox layer should
        return 'allow' to pass through, not 'ask'.
        """
        env = {
            "SANDBOX_ENABLED": "false",
            "MCP_AUTO_APPROVE": "true",
            "PRE_TOOL_AGENT_AUTH": "true",
            "PRE_TOOL_BATCH_PERMISSION": "false",
        }

        result = self.run_hook("Bash", {"command": "ls -la"}, env)
        output = result.get("hookSpecificOutput", {})

        decision = output.get("permissionDecision")
        reason = output.get("permissionDecisionReason", "")

        # Should be 'allow', not 'ask'
        assert decision == "allow", \
            f"Expected 'allow' when sandbox disabled, got '{decision}'. Reason: {reason}"

        # Verify sandbox layer says "pass through" not just disabled
        assert "Sandbox layer disabled" in reason, \
            f"Sandbox reason should mention 'disabled': {reason}"

    def test_batch_permission_disabled_returns_allow(self):
        """When PRE_TOOL_BATCH_PERMISSION=false, batch layer should pass through."""
        env = {
            "SANDBOX_ENABLED": "false",
            "MCP_AUTO_APPROVE": "true",
            "PRE_TOOL_AGENT_AUTH": "true",
            "PRE_TOOL_BATCH_PERMISSION": "false",
        }

        result = self.run_hook("Bash", {"command": "git status"}, env)
        output = result.get("hookSpecificOutput", {})

        decision = output.get("permissionDecision")
        reason = output.get("permissionDecisionReason", "")

        assert decision == "allow", \
            f"Expected 'allow' when batch permission disabled, got '{decision}'. Reason: {reason}"

    def test_all_layers_disabled_still_allows(self):
        """When all optional layers are disabled, should still allow approved commands."""
        env = {
            "SANDBOX_ENABLED": "false",
            "MCP_AUTO_APPROVE": "true",
            "PRE_TOOL_AGENT_AUTH": "false",  # Disabled
            "PRE_TOOL_BATCH_PERMISSION": "false",  # Disabled
            "PRE_TOOL_MCP_SECURITY": "true",  # Enabled but should auto-approve
        }

        result = self.run_hook("Bash", {"command": "echo hello"}, env)
        output = result.get("hookSpecificOutput", {})

        decision = output.get("permissionDecision")

        assert decision == "allow", \
            f"Expected 'allow' when layers disabled with MCP_AUTO_APPROVE=true, got '{decision}'"

    def test_non_bash_commands_pass_through_sandbox(self):
        """Sandbox layer should pass through non-Bash tools (Read, Glob, etc.)."""
        env = {
            "SANDBOX_ENABLED": "true",  # Even when enabled
            "MCP_AUTO_APPROVE": "true",
            "PRE_TOOL_AGENT_AUTH": "true",
            "PRE_TOOL_BATCH_PERMISSION": "false",
        }

        # Use a valid path within the project to avoid path traversal blocking
        valid_path = str(project_root / "README.md")
        result = self.run_hook("Read", {"file_path": valid_path}, env)
        output = result.get("hookSpecificOutput", {})

        decision = output.get("permissionDecision")
        reason = output.get("permissionDecisionReason", "")

        # Sandbox should pass through (not applicable to Read) and overall should allow
        assert decision == "allow", \
            f"Should allow Read tool within project. Decision: {decision}, Reason: {reason}"
        assert "Sandbox layer only validates Bash" in reason, \
            f"Sandbox reason should indicate pass-through for non-Bash: {reason}"


class TestCombineDecisionsLogic:
    """Test that the decision combining logic works correctly."""

    def run_hook(self, tool_name: str, tool_input: dict, env_overrides: dict = None) -> dict:
        """Run the hook with given input and environment variables."""
        env = os.environ.copy()
        env.update(env_overrides or {})

        input_data = json.dumps({"tool_name": tool_name, "tool_input": tool_input})

        result = subprocess.run(
            [sys.executable, str(HOOK_PATH)],
            input=input_data,
            capture_output=True,
            text=True,
            env=env,
            cwd=str(project_root)
        )

        return json.loads(result.stdout)

    def test_all_allow_results_in_allow(self):
        """When all layers return 'allow', final decision should be 'allow'."""
        env = {
            "SANDBOX_ENABLED": "false",  # Returns allow (pass through)
            "MCP_AUTO_APPROVE": "true",  # Returns allow
            "PRE_TOOL_AGENT_AUTH": "false",  # Returns allow (disabled)
            "PRE_TOOL_BATCH_PERMISSION": "false",  # Returns allow (disabled)
        }

        result = self.run_hook("Bash", {"command": "ls"}, env)
        output = result.get("hookSpecificOutput", {})

        assert output.get("permissionDecision") == "allow"

    def test_mcp_auto_approve_with_missing_libraries_allows(self):
        """When MCP_AUTO_APPROVE=true but libraries missing, should allow not ask."""
        env = {
            "SANDBOX_ENABLED": "false",
            "MCP_AUTO_APPROVE": "true",
            "PRE_TOOL_AGENT_AUTH": "false",
            "PRE_TOOL_BATCH_PERMISSION": "false",
            # MCP security will try to import libraries
        }

        result = self.run_hook("Bash", {"command": "pwd"}, env)
        output = result.get("hookSpecificOutput", {})

        decision = output.get("permissionDecision")

        # Should be allow, even if libraries fail to import
        # MCP_AUTO_APPROVE=true should be respected
        assert decision == "allow", \
            f"Expected 'allow' with MCP_AUTO_APPROVE=true, got '{decision}'"
