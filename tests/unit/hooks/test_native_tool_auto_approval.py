"""
Regression tests for native tool auto-approval in unified_pre_tool.py.

Validates that:
1. All native Claude Code tools bypass MCP security (NATIVE_TOOLS set)
2. MCP tools still route through security validation
3. Workflow enforcement nudges still fire for raw Edit/Write on code files

Date: 2026-02-06
"""

import json
import os
import sys
from pathlib import Path
from typing import Dict, Tuple
from unittest.mock import patch, MagicMock

import pytest

# Add hook's parent to path so we can import the module
HOOK_DIR = Path(__file__).resolve().parents[3] / "plugins" / "autonomous-dev" / "hooks"
sys.path.insert(0, str(HOOK_DIR))

# Also add lib dir for any transitive imports
LIB_DIR = Path(__file__).resolve().parents[3] / "plugins" / "autonomous-dev" / "lib"
sys.path.insert(0, str(LIB_DIR))

import unified_pre_tool as hook


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def clean_env(monkeypatch):
    """Reset relevant env vars for each test."""
    env_keys = [
        "SANDBOX_ENABLED", "PRE_TOOL_MCP_SECURITY", "PRE_TOOL_AGENT_AUTH",
        "PRE_TOOL_BATCH_PERMISSION", "MCP_AUTO_APPROVE", "ENFORCEMENT_LEVEL",
        "CLAUDE_AGENT_NAME", "PIPELINE_STATE_FILE",
    ]
    for key in env_keys:
        monkeypatch.delenv(key, raising=False)
    # Defaults: MCP security on, agent auth on, sandbox off, batch off
    monkeypatch.setenv("PRE_TOOL_MCP_SECURITY", "true")
    monkeypatch.setenv("PRE_TOOL_AGENT_AUTH", "true")


# ---------------------------------------------------------------------------
# 1. Native tools bypass MCP security
# ---------------------------------------------------------------------------

NATIVE_TOOLS = [
    "Read", "Write", "Edit", "Bash", "Glob", "Grep",
    "Task", "TaskCreate", "TaskUpdate", "TaskList", "TaskGet", "TaskOutput", "TaskStop",
    "NotebookEdit", "WebFetch", "WebSearch", "AskUserQuestion", "Skill",
    "EnterPlanMode", "ExitPlanMode",
]

# Extra native tools in the set but not in the user's original list
EXTRA_NATIVE_TOOLS = ["SlashCommand", "BashOutput", "TodoWrite", "AgentOutputTool", "KillShell", "LSP"]


class TestNativeToolsMCPBypass:
    """Every native tool should be auto-approved by validate_mcp_security."""

    @pytest.mark.parametrize("tool_name", NATIVE_TOOLS)
    def test_native_tool_bypasses_mcp_security(self, tool_name: str):
        decision, reason = hook.validate_mcp_security(tool_name, {})
        assert decision == "allow"
        assert "Native tool" in reason

    @pytest.mark.parametrize("tool_name", EXTRA_NATIVE_TOOLS)
    def test_extra_native_tool_bypasses_mcp_security(self, tool_name: str):
        decision, reason = hook.validate_mcp_security(tool_name, {})
        assert decision == "allow"
        assert "Native tool" in reason

    def test_native_tools_set_completeness(self):
        """All tools listed in NATIVE_TOOLS constant exist in the hook module."""
        all_expected = set(NATIVE_TOOLS + EXTRA_NATIVE_TOOLS)
        assert all_expected.issubset(hook.NATIVE_TOOLS)

    def test_native_tool_with_arbitrary_input(self):
        """Native tools bypass regardless of tool_input content."""
        decision, reason = hook.validate_mcp_security("Read", {
            "file_path": "/etc/passwd",
            "malicious": "../../secrets",
        })
        assert decision == "allow"
        assert "Native tool" in reason

    def test_native_tool_reason_includes_tool_name(self):
        decision, reason = hook.validate_mcp_security("Glob", {"pattern": "**/*"})
        assert "Glob" in reason


# ---------------------------------------------------------------------------
# 2. MCP (non-native) tools route through security validation
# ---------------------------------------------------------------------------

MCP_TOOLS = [
    "mcp__github__create_issue",
    "mcp__searxng__web_search",
    "mcp__filesystem__read_file",
    "mcp__custom_server__do_something",
]


class TestMCPToolsSecurityRouting:
    """Non-native MCP tools should NOT get the early return bypass."""

    @pytest.mark.parametrize("tool_name", MCP_TOOLS)
    def test_mcp_tool_not_in_native_set(self, tool_name: str):
        assert tool_name not in hook.NATIVE_TOOLS

    @pytest.mark.parametrize("tool_name", MCP_TOOLS)
    def test_mcp_tool_does_not_get_native_bypass(self, tool_name: str, monkeypatch):
        """MCP tools should go through security validation, not get native bypass."""
        monkeypatch.setenv("PRE_TOOL_MCP_SECURITY", "true")
        monkeypatch.setenv("MCP_AUTO_APPROVE", "false")
        decision, reason = hook.validate_mcp_security(tool_name, {})
        # Should NOT contain "Native tool" — it went through the validation path
        assert "Native tool" not in reason

    def test_mcp_tool_with_security_disabled(self, monkeypatch):
        """When MCP security is disabled, MCP tools still get allowed (but via disabled path)."""
        monkeypatch.setenv("PRE_TOOL_MCP_SECURITY", "false")
        decision, reason = hook.validate_mcp_security("mcp__github__create_issue", {})
        assert decision == "allow"
        assert "disabled" in reason.lower()

    def test_mcp_tool_asks_when_no_validator(self, monkeypatch):
        """MCP tool with security enabled but no validator available should ask."""
        monkeypatch.setenv("PRE_TOOL_MCP_SECURITY", "true")
        monkeypatch.setenv("MCP_AUTO_APPROVE", "false")
        decision, reason = hook.validate_mcp_security("mcp__unknown__action", {"arg": "val"})
        assert decision == "ask"

    def test_mcp_tool_auto_approve_fallback(self, monkeypatch):
        """MCP tool with MCP_AUTO_APPROVE=true but no validators should allow."""
        monkeypatch.setenv("PRE_TOOL_MCP_SECURITY", "true")
        monkeypatch.setenv("MCP_AUTO_APPROVE", "true")
        # Neither mcp_security_validator nor auto_approval_engine importable in test env
        # The code tries mcp_security_validator (ImportError) -> auto_approval_engine (ImportError)
        # -> falls through to "allow" with "MCP security validators unavailable, MCP_AUTO_APPROVE=true"
        decision, reason = hook.validate_mcp_security("mcp__unknown__action", {})
        # Could be "allow" (if neither import exists) or "ask" (if auto_approval_engine exists but rejects)
        # In test env without auto_approval_engine: allow
        # In test env WITH auto_approval_engine on path (from lib/): may get "ask"
        assert decision in ("allow", "ask")


# ---------------------------------------------------------------------------
# 3. Workflow enforcement nudges for raw Edit/Write
# ---------------------------------------------------------------------------

class TestWorkflowEnforcementNudges:
    """Workflow enforcement should still fire for Edit/Write on code files."""

    def _make_significant_edit(self) -> Dict:
        """Create an Edit tool_input that triggers significant change detection."""
        return {
            "file_path": "/project/src/main.py",
            "old_string": "pass",
            "new_string": (
                "def new_feature(data: list) -> dict:\n"
                "    result = {}\n"
                "    for item in data:\n"
                "        result[item] = process(item)\n"
                "    return result\n"
                "    # extra line\n"
                "    # more lines\n"
            ),
        }

    def _make_significant_write(self) -> Dict:
        """Create a Write tool_input that triggers significant change detection."""
        return {
            "file_path": "/project/src/handler.py",
            "content": (
                "def handler(request):\n"
                "    data = request.json()\n"
                "    result = process(data)\n"
                "    return Response(result)\n"
                "    # padding\n"
                "    # padding\n"
            ),
        }

    def test_edit_suggest_nudge(self, monkeypatch):
        """Edit with significant code change at suggest level should nudge."""
        monkeypatch.setenv("ENFORCEMENT_LEVEL", "suggest")
        monkeypatch.setenv("CLAUDE_AGENT_NAME", "")
        monkeypatch.setenv("PIPELINE_STATE_FILE", "/nonexistent/state.json")
        decision, reason = hook.validate_agent_authorization("Edit", self._make_significant_edit())
        assert decision == "allow"
        assert "/implement" in reason

    def test_write_suggest_nudge(self, monkeypatch):
        """Write with significant code at suggest level should nudge."""
        monkeypatch.setenv("ENFORCEMENT_LEVEL", "suggest")
        monkeypatch.setenv("CLAUDE_AGENT_NAME", "")
        monkeypatch.setenv("PIPELINE_STATE_FILE", "/nonexistent/state.json")
        decision, reason = hook.validate_agent_authorization("Write", self._make_significant_write())
        assert decision == "allow"
        assert "/implement" in reason

    def test_edit_block_level_denies(self, monkeypatch):
        """Edit with significant code at block level should deny."""
        monkeypatch.setenv("ENFORCEMENT_LEVEL", "block")
        monkeypatch.setenv("CLAUDE_AGENT_NAME", "")
        monkeypatch.setenv("PIPELINE_STATE_FILE", "/nonexistent/state.json")
        decision, reason = hook.validate_agent_authorization("Edit", self._make_significant_edit())
        assert decision == "deny"
        assert "WORKFLOW ENFORCEMENT" in reason

    def test_edit_warn_level_allows(self, monkeypatch):
        """Edit with significant code at warn level should allow with warning."""
        monkeypatch.setenv("ENFORCEMENT_LEVEL", "warn")
        monkeypatch.setenv("CLAUDE_AGENT_NAME", "")
        monkeypatch.setenv("PIPELINE_STATE_FILE", "/nonexistent/state.json")
        decision, reason = hook.validate_agent_authorization("Edit", self._make_significant_edit())
        assert decision == "allow"
        assert "WARN" in reason or "warn" in reason.lower()

    def test_pipeline_agent_bypasses_enforcement(self, monkeypatch):
        """Pipeline agents skip workflow enforcement entirely."""
        monkeypatch.setenv("ENFORCEMENT_LEVEL", "block")
        monkeypatch.setenv("CLAUDE_AGENT_NAME", "implementer")
        decision, reason = hook.validate_agent_authorization("Edit", self._make_significant_edit())
        assert decision == "allow"
        assert "Pipeline agent" in reason or "implementer" in reason

    def test_enforcement_off_allows_all(self, monkeypatch):
        """Enforcement level 'off' skips all checks."""
        monkeypatch.setenv("ENFORCEMENT_LEVEL", "off")
        monkeypatch.setenv("CLAUDE_AGENT_NAME", "")
        monkeypatch.setenv("PIPELINE_STATE_FILE", "/nonexistent/state.json")
        decision, reason = hook.validate_agent_authorization("Edit", self._make_significant_edit())
        assert decision == "allow"

    def test_exempt_file_skips_enforcement(self, monkeypatch):
        """Test files are exempt from workflow enforcement."""
        monkeypatch.setenv("ENFORCEMENT_LEVEL", "block")
        monkeypatch.setenv("CLAUDE_AGENT_NAME", "")
        monkeypatch.setenv("PIPELINE_STATE_FILE", "/nonexistent/state.json")
        tool_input = {
            "file_path": "tests/test_main.py",
            "old_string": "pass",
            "new_string": "def test_new():\n    assert True\n    # l1\n    # l2\n    # l3\n    # l4\n",
        }
        decision, reason = hook.validate_agent_authorization("Edit", tool_input)
        assert decision == "allow"
        assert "exempt" in reason.lower() or "File exempt" in reason

    def test_minor_edit_no_nudge(self, monkeypatch):
        """Minor edits (< threshold) should not trigger nudge."""
        monkeypatch.setenv("ENFORCEMENT_LEVEL", "suggest")
        monkeypatch.setenv("CLAUDE_AGENT_NAME", "")
        monkeypatch.setenv("PIPELINE_STATE_FILE", "/nonexistent/state.json")
        tool_input = {
            "file_path": "/project/src/main.py",
            "old_string": "x = 1",
            "new_string": "x = 2",
        }
        decision, reason = hook.validate_agent_authorization("Edit", tool_input)
        assert decision == "allow"
        assert "/implement" not in reason

    def test_non_code_file_no_enforcement(self, monkeypatch):
        """Non-code files skip enforcement."""
        monkeypatch.setenv("ENFORCEMENT_LEVEL", "block")
        monkeypatch.setenv("CLAUDE_AGENT_NAME", "")
        monkeypatch.setenv("PIPELINE_STATE_FILE", "/nonexistent/state.json")
        tool_input = {
            "file_path": "/project/data/config.csv",
            "old_string": "",
            "new_string": "a,b,c\n1,2,3\n",
        }
        decision, reason = hook.validate_agent_authorization("Edit", tool_input)
        assert decision == "allow"


# ---------------------------------------------------------------------------
# 4. Integration: combine_decisions with native vs MCP
# ---------------------------------------------------------------------------

class TestCombineDecisions:
    """Validate decision combination logic."""

    def test_all_allow_returns_allow(self):
        results = [
            ("Sandbox", "allow", "disabled"),
            ("MCP Security", "allow", "native tool"),
            ("Agent Auth", "allow", "pipeline agent"),
            ("Batch", "allow", "disabled"),
        ]
        decision, reason = hook.combine_decisions(results)
        assert decision == "allow"

    def test_any_deny_returns_deny(self):
        results = [
            ("Sandbox", "allow", "ok"),
            ("MCP Security", "deny", "path traversal detected"),
            ("Agent Auth", "allow", "ok"),
            ("Batch", "allow", "ok"),
        ]
        decision, reason = hook.combine_decisions(results)
        assert decision == "deny"

    def test_ask_without_deny_returns_ask(self):
        results = [
            ("Sandbox", "allow", "ok"),
            ("MCP Security", "ask", "needs approval"),
            ("Agent Auth", "allow", "ok"),
            ("Batch", "allow", "ok"),
        ]
        decision, reason = hook.combine_decisions(results)
        assert decision == "ask"
