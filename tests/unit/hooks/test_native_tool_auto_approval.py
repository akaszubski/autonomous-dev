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

POLICY_FILE = Path(__file__).resolve().parents[3] / "plugins" / "autonomous-dev" / "config" / "auto_approve_policy.json"

def _load_policy_always_allowed() -> list[str]:
    """Load always_allowed tools from the policy file (source of truth)."""
    with open(POLICY_FILE) as f:
        policy = json.load(f)
    return policy["tools"]["always_allowed"]

POLICY_ALWAYS_ALLOWED = _load_policy_always_allowed()


class TestNativeToolsMCPBypass:
    """Every native tool should be auto-approved by validate_mcp_security."""

    @pytest.mark.parametrize("tool_name", sorted(hook.NATIVE_TOOLS))
    def test_native_tool_bypasses_mcp_security(self, tool_name: str):
        decision, reason = hook.validate_mcp_security(tool_name, {})
        assert decision == "allow"
        assert "Native tool" in reason

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


class TestPolicyAndHookSync:
    """REGRESSION: Policy file and NATIVE_TOOLS must stay in sync.

    This is the critical test. Every time we've had auto-approval bugs,
    it's because a tool was added to one place but not the other.
    """

    def test_policy_always_allowed_subset_of_native_tools(self):
        """Every tool in policy always_allowed MUST be in hook NATIVE_TOOLS.

        This is the exact regression that has bitten us 4+ times:
        tool added to policy file but not to NATIVE_TOOLS set in the hook.
        """
        missing = set(POLICY_ALWAYS_ALLOWED) - hook.NATIVE_TOOLS
        assert missing == set(), (
            f"Tools in policy always_allowed but MISSING from hook NATIVE_TOOLS: {missing}\n"
            f"Fix: add {missing} to NATIVE_TOOLS in unified_pre_tool.py"
        )

    def test_native_tools_subset_of_policy(self):
        """Every tool in hook NATIVE_TOOLS SHOULD be in policy always_allowed.

        Warns about tools in the hook but not the policy (less critical but
        indicates drift).
        """
        missing = hook.NATIVE_TOOLS - set(POLICY_ALWAYS_ALLOWED)
        assert missing == set(), (
            f"Tools in hook NATIVE_TOOLS but MISSING from policy always_allowed: {missing}\n"
            f"Fix: add {missing} to always_allowed in auto_approve_policy.json"
        )


# ---------------------------------------------------------------------------
# 1b. Native tools in settings templates (deployment regression)
# ---------------------------------------------------------------------------

TEMPLATES_DIR = Path(__file__).resolve().parents[3] / "plugins" / "autonomous-dev" / "templates"

# Tools that MUST be in permissions.allow for worktrees to work without prompts.
# These are the native tools that Claude Code's permission system checks BEFORE hooks run.
REQUIRED_PERMISSION_TOOLS = {
    "Read", "Write", "Edit", "Glob", "Grep", "Bash", "Agent", "Skill",
    "ToolSearch", "NotebookEdit", "WebSearch", "WebFetch",
    "EnterPlanMode", "ExitPlanMode", "EnterWorktree", "AskUserQuestion",
    "TaskCreate", "TaskUpdate", "TaskList", "TaskGet", "TaskStop", "TaskOutput",
}


class TestSettingsTemplatesIncludeNativeTools:
    """REGRESSION: Settings templates must include native tools in permissions.allow.

    git worktree add checks out COMMITTED files. If settings.json doesn't have
    a native tool in permissions.allow, worktrees will prompt for permission
    even though the hook would auto-approve it — because the permission check
    runs BEFORE hooks.

    This has bitten us 10+ times with ToolSearch specifically.
    """

    @pytest.fixture
    def template_files(self):
        return sorted(TEMPLATES_DIR.glob("settings.*.json"))

    def test_templates_exist(self, template_files):
        assert len(template_files) >= 1, f"No settings templates found in {TEMPLATES_DIR}"

    def test_all_templates_have_native_tools_in_permissions(self, template_files):
        """Every settings template must include all required native tools in permissions.allow."""
        failures = []
        for template in template_files:
            with open(template) as f:
                settings = json.load(f)
            allow = settings.get("permissions", {}).get("allow", [])
            allow_set = set(allow)
            # Bash can be bare "Bash" or granular "Bash(git status)" in allow,
            # or "Bash(:*)" in ask (permission-batching mode). All count as "handled".
            ask_list = settings.get("permissions", {}).get("ask", [])
            has_bash = (
                "Bash" in allow_set
                or any(t.startswith("Bash(") for t in allow)
                or any(t.startswith("Bash") for t in ask_list)
            )
            missing = []
            for tool in sorted(REQUIRED_PERMISSION_TOOLS):
                if tool == "Bash":
                    if not has_bash:
                        missing.append(tool)
                elif tool not in allow_set:
                    missing.append(tool)
            if missing:
                failures.append(f"  {template.name}: missing {missing}")
        assert not failures, (
            f"Settings templates missing native tools in permissions.allow:\n"
            + "\n".join(failures)
            + f"\nFix: add missing tools to permissions.allow in each template"
        )

    def test_native_tools_set_covers_required_permissions(self):
        """NATIVE_TOOLS in the hook must be a superset of REQUIRED_PERMISSION_TOOLS."""
        missing = REQUIRED_PERMISSION_TOOLS - hook.NATIVE_TOOLS
        assert missing == set(), (
            f"REQUIRED_PERMISSION_TOOLS has tools not in hook NATIVE_TOOLS: {missing}\n"
            f"Either add to NATIVE_TOOLS or remove from REQUIRED_PERMISSION_TOOLS"
        )


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
        assert decision == "ask"
        assert "/implement" in reason

    def test_write_suggest_nudge(self, monkeypatch):
        """Write with significant code at suggest level should prompt user."""
        monkeypatch.setenv("ENFORCEMENT_LEVEL", "suggest")
        monkeypatch.setenv("CLAUDE_AGENT_NAME", "")
        monkeypatch.setenv("PIPELINE_STATE_FILE", "/nonexistent/state.json")
        decision, reason = hook.validate_agent_authorization("Write", self._make_significant_write())
        assert decision == "ask"
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


# ---------------------------------------------------------------------------
# 5. Native tool fast-path bypass in main() (Issue: permission prompts)
# ---------------------------------------------------------------------------

def _run_main_with_tool(tool_name: str, tool_input: Dict | None = None) -> Tuple[str, str]:
    """Run main() with a mocked tool invocation and capture the output decision.

    Mocks sys.stdin with JSON input, captures stdout, and handles sys.exit(0).

    Args:
        tool_name: Name of the tool to simulate.
        tool_input: Optional tool_input dict (defaults to empty dict).

    Returns:
        Tuple of (permissionDecision, permissionDecisionReason).
    """
    import io

    input_json = json.dumps({"tool_name": tool_name, "tool_input": tool_input or {}})
    captured = io.StringIO()
    with patch("sys.stdin", io.StringIO(input_json)), \
         patch("sys.stdout", captured), \
         pytest.raises(SystemExit):
        hook.main()
    raw = captured.getvalue().strip()
    output = json.loads(raw)
    decision = output["hookSpecificOutput"]["permissionDecision"]
    reason = output["hookSpecificOutput"]["permissionDecisionReason"]
    return decision, reason


class TestNativeToolMainBypass:
    """Regression tests: native tools must get 'allow' from main() via fast-path,
    bypassing ALL validator layers.

    Bug: native tools like Edit/Write were routed through validate_agent_authorization
    which returned 'ask' or 'deny' for significant code changes outside the pipeline.
    Fix: early return in main() for tools in NATIVE_TOOLS before any validators run.
    """

    @pytest.mark.parametrize("tool_name", sorted(hook.NATIVE_TOOLS))
    def test_native_tool_returns_allow_from_main(self, tool_name: str):
        """Every native tool must receive 'allow' from main(), regardless of env config."""
        decision, reason = _run_main_with_tool(tool_name)
        assert decision == "allow", (
            f"Native tool '{tool_name}' got '{decision}' from main() instead of 'allow'.\n"
            f"Reason: {reason}"
        )

    def test_native_tool_skips_all_validators(self):
        """When main() processes a native tool, none of the 4 validators should be called."""
        with patch.object(hook, "validate_sandbox_layer", wraps=hook.validate_sandbox_layer) as mock_sandbox, \
             patch.object(hook, "validate_mcp_security", wraps=hook.validate_mcp_security) as mock_mcp, \
             patch.object(hook, "validate_agent_authorization", wraps=hook.validate_agent_authorization) as mock_auth, \
             patch.object(hook, "validate_batch_permission", wraps=hook.validate_batch_permission) as mock_batch:
            _run_main_with_tool("Read", {"file_path": "/some/file.py"})
            mock_sandbox.assert_not_called()
            mock_mcp.assert_not_called()
            mock_auth.assert_not_called()
            mock_batch.assert_not_called()

    def test_mcp_tool_still_runs_validators(self):
        """Non-native (MCP) tools must still route through validator layers."""
        with patch.object(hook, "validate_sandbox_layer", return_value=("allow", "ok")) as mock_sandbox, \
             patch.object(hook, "validate_mcp_security", return_value=("allow", "ok")) as mock_mcp, \
             patch.object(hook, "validate_agent_authorization", return_value=("allow", "ok")) as mock_auth, \
             patch.object(hook, "validate_batch_permission", return_value=("allow", "ok")) as mock_batch:
            _run_main_with_tool("mcp__github__create_issue", {"title": "test"})
            mock_sandbox.assert_called_once()
            mock_mcp.assert_called_once()
            mock_auth.assert_called_once()
            mock_batch.assert_called_once()

    def test_native_tool_allow_despite_suggest_enforcement(self, monkeypatch):
        """Native Edit with significant code change must get 'allow' even at suggest level.

        Before the fix, this would return 'ask' because validate_agent_authorization
        detects the significant code change and suggests /implement.
        """
        monkeypatch.setenv("ENFORCEMENT_LEVEL", "suggest")
        monkeypatch.setenv("CLAUDE_AGENT_NAME", "")
        monkeypatch.setenv("PIPELINE_STATE_FILE", "/nonexistent/state.json")
        tool_input = {
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
        decision, reason = _run_main_with_tool("Edit", tool_input)
        assert decision == "allow", (
            f"Native Edit got '{decision}' instead of 'allow' at suggest level.\n"
            f"Reason: {reason}\n"
            f"The fast-path should bypass validate_agent_authorization entirely."
        )

    def test_native_tool_allow_despite_block_enforcement(self, monkeypatch):
        """Native Edit with significant code change must get 'allow' even at block level.

        Before the fix, this would return 'deny' because validate_agent_authorization
        blocks significant code changes outside the pipeline at block level.
        """
        monkeypatch.setenv("ENFORCEMENT_LEVEL", "block")
        monkeypatch.setenv("CLAUDE_AGENT_NAME", "")
        monkeypatch.setenv("PIPELINE_STATE_FILE", "/nonexistent/state.json")
        tool_input = {
            "file_path": "/project/src/handler.py",
            "old_string": "pass",
            "new_string": (
                "class RequestHandler:\n"
                "    def handle(self, request):\n"
                "        data = request.json()\n"
                "        result = self.process(data)\n"
                "        return Response(result)\n"
                "    def process(self, data):\n"
                "        return data\n"
            ),
        }
        decision, reason = _run_main_with_tool("Edit", tool_input)
        assert decision == "allow", (
            f"Native Edit got '{decision}' instead of 'allow' at block level.\n"
            f"Reason: {reason}\n"
            f"The fast-path should bypass validate_agent_authorization entirely."
        )

    def test_native_tool_bypass_reason_format(self):
        """The fast-path reason should contain the tool name and 'Native tool'."""
        decision, reason = _run_main_with_tool("Bash", {"command": "ls"})
        assert "Native tool" in reason, (
            f"Expected 'Native tool' in reason, got: {reason}"
        )
        assert "Bash" in reason, (
            f"Expected tool name 'Bash' in reason, got: {reason}"
        )

    @pytest.mark.parametrize("tool_name", ["Write", "Edit", "Bash"])
    def test_write_tools_bypass_despite_enforcement(self, tool_name: str, monkeypatch):
        """Write-capable native tools must bypass even with block enforcement active.

        These are the tools most likely to trigger workflow enforcement nudges,
        so they are the critical regression case.
        """
        monkeypatch.setenv("ENFORCEMENT_LEVEL", "block")
        monkeypatch.setenv("CLAUDE_AGENT_NAME", "")
        monkeypatch.setenv("PIPELINE_STATE_FILE", "/nonexistent/state.json")
        decision, reason = _run_main_with_tool(tool_name, {})
        assert decision == "allow", (
            f"Write-capable native tool '{tool_name}' got '{decision}' at block level.\n"
            f"Reason: {reason}"
        )
