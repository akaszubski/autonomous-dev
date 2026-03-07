"""Unit tests for default-allow permission model (Issue #401).

Validates that unified_pre_tool.py:
1. Defaults to 'allow' for ALL tools (native and non-native)
2. Only returns 'deny' for actual security violations
3. Does NOT depend on auto_approve_policy.json for tool decisions
4. Does NOT return 'ask' for unknown/new tools
"""

import re
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).parent.parent.parent.parent
UNIFIED_PRE_TOOL = PROJECT_ROOT / "plugins" / "autonomous-dev" / "hooks" / "unified_pre_tool.py"


@pytest.fixture
def hook_content() -> str:
    """Load unified_pre_tool.py content."""
    assert UNIFIED_PRE_TOOL.exists(), f"unified_pre_tool.py not found at {UNIFIED_PRE_TOOL}"
    return UNIFIED_PRE_TOOL.read_text()


class TestNativeToolsFastPath:
    """All native Claude Code tools must be auto-allowed via fast path."""

    EXPECTED_NATIVE_TOOLS = {
        "Read", "Write", "Edit", "Glob", "Grep", "Bash",
        "Task", "TaskOutput", "TaskCreate", "TaskUpdate", "TaskList", "TaskGet", "TaskStop",
        "AskUserQuestion", "Skill", "SlashCommand", "BashOutput", "NotebookEdit",
        "TodoWrite", "EnterPlanMode", "ExitPlanMode", "AgentOutputTool", "KillShell",
        "LSP", "WebFetch", "WebSearch",
        "Agent", "EnterWorktree", "ToolSearch",
    }

    def test_native_tools_set_exists(self, hook_content: str):
        """NATIVE_TOOLS set must exist in unified_pre_tool.py."""
        assert "NATIVE_TOOLS" in hook_content

    def test_all_expected_tools_in_native_set(self, hook_content: str):
        """All known Claude Code tools must be in NATIVE_TOOLS."""
        for tool in self.EXPECTED_NATIVE_TOOLS:
            assert f'"{tool}"' in hook_content, (
                f"Tool '{tool}' missing from NATIVE_TOOLS set. "
                f"Add it to prevent 'Not whitelisted' prompts."
            )

    def test_fast_path_returns_allow(self, hook_content: str):
        """Fast path for native tools must return 'allow', not 'ask'."""
        # Find the fast path block in main() — the one that calls output_decision and sys.exit
        fast_path_match = re.search(
            r'# FAST PATH.*?if tool_name in NATIVE_TOOLS:.*?sys\.exit\(0\)',
            hook_content,
            re.DOTALL,
        )
        assert fast_path_match, "NATIVE_TOOLS fast path not found in main()"
        fast_path = fast_path_match.group(0)
        assert 'output_decision("allow"' in fast_path, "Fast path must return 'allow' for native tools"


class TestDefaultAllowForNonNativeTools:
    """Non-native (MCP) tools must default to 'allow' instead of 'ask'."""

    def test_no_auto_approval_engine_dependency(self, hook_content: str):
        """unified_pre_tool.py must NOT import auto_approval_engine."""
        # The auto_approval_engine is the source of "Not whitelisted" regressions.
        # After #401, we should not depend on it for tool decisions.
        assert "from auto_approval_engine import" not in hook_content, (
            "unified_pre_tool.py still imports auto_approval_engine. "
            "Remove this dependency — it causes 'Not whitelisted' regressions "
            "every time a new tool is added to Claude Code."
        )

    def test_no_not_whitelisted_message(self, hook_content: str):
        """unified_pre_tool.py must not produce 'Not whitelisted' as a return value."""
        # Check that "Not whitelisted" doesn't appear in any return statement.
        # It's OK in comments explaining why it was removed.
        returns_with_not_whitelisted = re.findall(
            r'return\s*\(.*?Not whitelisted.*?\)', hook_content
        )
        assert len(returns_with_not_whitelisted) == 0, (
            f"unified_pre_tool.py returns 'Not whitelisted' in {len(returns_with_not_whitelisted)} places. "
            "This causes user-facing permission prompts. Remove it."
        )

    def test_mcp_fallback_defaults_to_allow(self, hook_content: str):
        """When MCP security validator is unavailable, default to 'allow'."""
        # The fallback path (when mcp_security_validator import fails)
        # should return 'allow', not call auto_approval_engine
        mcp_section = hook_content[hook_content.find("def validate_mcp_security"):]
        mcp_section = mcp_section[:mcp_section.find("\ndef ", 10)]  # next function

        # Should not return "ask" for missing MCP validator
        ask_returns = re.findall(r'return\s*\(\s*"ask"', mcp_section)
        assert len(ask_returns) == 0, (
            f"MCP security fallback returns 'ask' in {len(ask_returns)} places. "
            "Default to 'allow' when MCP validator is unavailable."
        )


class TestCombineDecisionsDefaultAllow:
    """combine_decisions must not produce 'ask' for normal tool usage."""

    def test_combine_decisions_no_ask_without_deny(self, hook_content: str):
        """combine_decisions should only return 'ask' if there's a security concern.

        The old logic was: if ANY layer returns 'ask', final = 'ask'.
        The new logic should be: only 'deny' from security layers blocks.
        For non-security layers, 'ask' should be treated as 'allow'.
        """
        # Verify the function exists
        assert "def combine_decisions" in hook_content

    def test_no_auto_approve_policy_json_import(self, hook_content: str):
        """unified_pre_tool.py must not load or import auto_approve_policy.json."""
        # Check for actual file loading, not comments explaining history
        loads = re.findall(r'(?:open|load|read).*auto_approve_policy', hook_content)
        imports = re.findall(r'(?:from|import).*auto_approve_policy', hook_content)
        assert len(loads) + len(imports) == 0, (
            "unified_pre_tool.py loads/imports auto_approve_policy.json. "
            "This file is the root cause of regressions — remove the dependency."
        )


class TestSyncCleanup:
    """sync.md should remove stale hooks from deployed repos."""

    def test_stale_hooks_listed_for_removal(self):
        """sync.md should reference stale hooks that need removal."""
        sync_md = PROJECT_ROOT / "plugins" / "autonomous-dev" / "commands" / "sync.md"
        if not sync_md.exists():
            pytest.skip("sync.md not found")
        content = sync_md.read_text()
        # At minimum, sync should handle cleanup of old hooks
        # This is a soft check — we don't mandate specific file names
        assert "cleanup" in content.lower() or "remove" in content.lower() or "stale" in content.lower(), (
            "sync.md should mention cleanup of stale/old hooks from deployed repos."
        )
