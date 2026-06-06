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
        "CLAUDE_AGENT_NAME", "PIPELINE_STATE_FILE", "PRE_TOOL_PIPELINE_ORDERING",
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

    def test_mcp_tool_allows_when_no_validator(self, monkeypatch):
        """MCP tool with no validator available should default to allow (Issue #401)."""
        monkeypatch.setenv("PRE_TOOL_MCP_SECURITY", "true")
        monkeypatch.setenv("MCP_AUTO_APPROVE", "false")
        decision, reason = hook.validate_mcp_security("mcp__unknown__action", {"arg": "val"})
        assert decision == "allow"

    def test_mcp_tool_auto_approve_fallback(self, monkeypatch):
        """MCP tool with no validators should always allow (Issue #401)."""
        monkeypatch.setenv("PRE_TOOL_MCP_SECURITY", "true")
        monkeypatch.setenv("MCP_AUTO_APPROVE", "true")
        decision, reason = hook.validate_mcp_security("mcp__unknown__action", {})
        assert decision == "allow"


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
        """Non-native (MCP) tools must still route through validator layers.

        _is_adev_project must return True so the project guard (Issue #662)
        does not short-circuit before validators are invoked.
        """
        with patch.object(hook, "_is_adev_project", return_value=True), \
             patch.object(hook, "validate_sandbox_layer", return_value=("allow", "ok")) as mock_sandbox, \
             patch.object(hook, "validate_mcp_security", return_value=("allow", "ok")) as mock_mcp, \
             patch.object(hook, "validate_agent_authorization", return_value=("allow", "ok")) as mock_auth, \
             patch.object(hook, "validate_batch_permission", return_value=("allow", "ok")) as mock_batch:
            _run_main_with_tool("mcp__github__create_issue", {"title": "test"})
            mock_sandbox.assert_called_once()
            mock_mcp.assert_called_once()
            mock_auth.assert_called_once()
            mock_batch.assert_called_once()

    def test_native_tool_blocked_by_default_on_write_gate_new_function(
        self, monkeypatch, tmp_path
    ):
        """Native Edit adding a new function to production code must be DENIED by
        the default-on tier-aware Write/Edit gate (Issue #1142 Phase 1).

        Phase 1 polarity flip: the previous opt-IN check via ``.claude/.enforce``
        was replaced with a default-on gate. Per-repo opt-out is now via
        ``.claude/.bypass``. The new gate runs regardless of ENFORCEMENT_LEVEL,
        so the formerly-allowed "Native Edit at suggest level" case now denies.

        New-function edit -> tier="light" -> directive points to ``/implement --light``.
        """
        # No .claude/.bypass marker in tmp_path or ancestors. No pipeline active.
        monkeypatch.chdir(tmp_path)
        monkeypatch.setenv("ENFORCEMENT_LEVEL", "suggest")
        monkeypatch.delenv("CLAUDE_AGENT_NAME", raising=False)
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
        assert decision == "deny", (
            f"Native Edit got '{decision}' instead of 'deny' for new-function "
            f"edit without bypass marker.\nReason: {reason}\n"
            f"The default-on tier-aware gate should fire."
        )
        # New function -> light tier -> /implement --light directive
        assert "Tier: light" in reason or "tier: light" in reason, (
            f"Expected tier='light' in reason, got: {reason}"
        )
        assert "/implement --light" in reason, (
            f"Expected '/implement --light' directive in reason, got: {reason}"
        )

    def test_native_tool_allowed_with_bypass_marker_new_function(
        self, monkeypatch, tmp_path
    ):
        """Native Edit to code file with new function is ALLOWED when the
        universal ``.claude/.bypass`` marker is present in the cwd ancestor chain.

        Companion positive test for the polarity-flipped default-on gate
        (Issue #1142 Phase 1). The universal bypass short-circuits all hooks
        BEFORE the write-pipeline-gate runs (Issue #969).
        """
        # Create the .claude/.bypass marker in tmp_path, then chdir into it.
        bypass_dir = tmp_path / ".claude"
        bypass_dir.mkdir()
        (bypass_dir / ".bypass").write_text("")
        monkeypatch.chdir(tmp_path)
        monkeypatch.setenv("ENFORCEMENT_LEVEL", "suggest")
        monkeypatch.delenv("CLAUDE_AGENT_NAME", raising=False)
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
            f"Native Edit got '{decision}' instead of 'allow' with "
            f".claude/.bypass marker present.\nReason: {reason}"
        )

    def test_native_tool_blocked_by_default_on_write_gate_new_class(
        self, monkeypatch, tmp_path
    ):
        """Native Edit adding a new class to production code must be DENIED by
        the default-on tier-aware Write/Edit gate (Issue #1142 Phase 1).

        New-class edit -> tier="full" -> directive points to bare ``/implement``.
        The gate fires regardless of ENFORCEMENT_LEVEL (the new gate is always
        on; ENFORCEMENT_LEVEL no longer controls it).
        """
        monkeypatch.chdir(tmp_path)
        monkeypatch.setenv("ENFORCEMENT_LEVEL", "block")
        monkeypatch.delenv("CLAUDE_AGENT_NAME", raising=False)
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
        assert decision == "deny", (
            f"Native Edit got '{decision}' instead of 'deny' for new-class "
            f"edit without bypass marker.\nReason: {reason}\n"
            f"The default-on tier-aware gate should fire."
        )
        # New class -> full tier -> bare /implement directive
        assert "Tier: full" in reason or "tier: full" in reason, (
            f"Expected tier='full' in reason, got: {reason}"
        )
        assert "/implement" in reason, (
            f"Expected '/implement' directive in reason, got: {reason}"
        )

    def test_native_tool_allowed_with_bypass_marker_new_class(
        self, monkeypatch, tmp_path
    ):
        """Native Edit to code file with new class is ALLOWED when the universal
        ``.claude/.bypass`` marker is present (companion positive test)."""
        bypass_dir = tmp_path / ".claude"
        bypass_dir.mkdir()
        (bypass_dir / ".bypass").write_text("")
        monkeypatch.chdir(tmp_path)
        monkeypatch.setenv("ENFORCEMENT_LEVEL", "block")
        monkeypatch.delenv("CLAUDE_AGENT_NAME", raising=False)
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
            f"Native Edit got '{decision}' instead of 'allow' with "
            f".claude/.bypass marker present.\nReason: {reason}"
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



# ---------------------------------------------------------------------------
# 6. Schema validation: prevent policy file regression (Issue: 9b42c0d)
# ---------------------------------------------------------------------------

class TestPolicyFileSchema:
    """Regression tests for auto_approve_policy.json v2.0 schema.

    Commit 9b42c0d replaced both policy files with an older v1.1 schema
    that lacked the 'tools' key, causing KeyError during pytest collection
    in test_native_tool_auto_approval.py and test_command_allowed_tools.py.

    These tests ensure the schema regression can never happen silently again.
    """

    REQUIRED_TOP_LEVEL_KEYS = {"version", "bash", "file_paths", "agents", "web_tools", "tools"}
    POLICY_FILES = [
        Path(__file__).resolve().parents[3] / "plugins" / "autonomous-dev" / "config" / "auto_approve_policy.json",
        Path(__file__).resolve().parents[3] / ".claude" / "config" / "auto_approve_policy.json",
    ]

    @pytest.mark.parametrize("policy_path", POLICY_FILES, ids=["source", "installed"])
    def test_policy_file_has_tools_key(self, policy_path: Path):
        """Policy file must contain the 'tools' top-level key (v2.0 schema).

        Without this key, test_command_allowed_tools.py fails at collection
        with KeyError: 'tools'.
        """
        assert policy_path.exists(), f"Policy file missing: {policy_path}"
        with open(policy_path) as f:
            policy = json.load(f)
        assert "tools" in policy, (
            f"Policy file {policy_path.name} is missing 'tools' key. "
            f"Found keys: {sorted(policy.keys())}. "
            f"This is the v1.1 schema regression from commit 9b42c0d."
        )

    @pytest.mark.parametrize("policy_path", POLICY_FILES, ids=["source", "installed"])
    def test_policy_file_has_all_required_keys(self, policy_path: Path):
        """Policy file must have all v2.0 required top-level keys."""
        assert policy_path.exists(), f"Policy file missing: {policy_path}"
        with open(policy_path) as f:
            policy = json.load(f)
        missing = self.REQUIRED_TOP_LEVEL_KEYS - set(policy.keys())
        assert not missing, (
            f"Policy file {policy_path.name} missing required keys: {sorted(missing)}. "
            f"Found: {sorted(policy.keys())}"
        )

    @pytest.mark.parametrize("policy_path", POLICY_FILES, ids=["source", "installed"])
    def test_policy_file_tools_has_always_allowed(self, policy_path: Path):
        """The 'tools' section must contain 'always_allowed' list."""
        with open(policy_path) as f:
            policy = json.load(f)
        assert "always_allowed" in policy.get("tools", {}), (
            f"Policy file {policy_path.name} 'tools' section missing 'always_allowed' list."
        )
        assert isinstance(policy["tools"]["always_allowed"], list), (
            f"'tools.always_allowed' must be a list, got {type(policy['tools']['always_allowed'])}"
        )
        assert len(policy["tools"]["always_allowed"]) > 0, (
            "'tools.always_allowed' must not be empty"
        )

    @pytest.mark.parametrize("policy_path", POLICY_FILES, ids=["source", "installed"])
    def test_policy_version_is_2_0(self, policy_path: Path):
        """Policy file must be v2.0 schema, not v1.1."""
        with open(policy_path) as f:
            policy = json.load(f)
        assert policy.get("version") == "2.0", (
            f"Policy file {policy_path.name} has version {policy.get('version')!r}, expected '2.0'. "
            f"The v1.1 schema is missing critical keys."
        )

    def test_source_and_installed_are_identical(self):
        """Source and installed policy files must have identical content."""
        source = self.POLICY_FILES[0]
        installed = self.POLICY_FILES[1]
        assert source.exists() and installed.exists()
        with open(source) as f:
            source_data = json.load(f)
        with open(installed) as f:
            installed_data = json.load(f)
        assert source_data == installed_data, (
            "Source and installed policy files have diverged. "
            "Run install or sync to reconcile."
        )


# ---------------------------------------------------------------------------
# 7. Regression: subagent_type priority over text extraction (Issue #636)
# ---------------------------------------------------------------------------

class TestSubagentTypePriority:
    """Regression tests for subagent_type field taking precedence over text extraction.

    Bug (Issue #636, commit 45565eb): When a planner's prompt contained
    "implementer" in research context, _extract_subagent_type matched
    "implementer" (longest-first), causing a false ORDERING VIOLATION.

    Fix: validate_pipeline_ordering() now checks tool_input["subagent_type"]
    before falling back to text extraction from prompt content.
    """

    def test_extract_subagent_type_basic(self):
        """_extract_subagent_type finds agent names in text."""
        assert hook._extract_subagent_type("Run the planner agent") == "planner"
        assert hook._extract_subagent_type("Launch implementer") == "implementer"
        assert hook._extract_subagent_type("no agent here") == ""
        assert hook._extract_subagent_type("") == ""

    def test_planner_prompt_mentioning_implementer_uses_subagent_type(self, monkeypatch):
        """Planner prompt that mentions 'implementer' should be identified as planner.

        This is the exact regression from Issue #636: the planner's prompt
        contained research context mentioning the implementer agent, and
        _extract_subagent_type matched 'implementer' instead of 'planner'.

        With the fix, subagent_type='planner' takes precedence over text.
        """
        monkeypatch.setenv("PRE_TOOL_PIPELINE_ORDERING", "true")
        # Mock pipeline as active and ordering gate to capture the target_agent
        captured = {}

        def mock_check(target, completed, validation_mode=None, launched_agents=None, pipeline_mode=None):
            captured["target"] = target
            result = MagicMock()
            result.passed = True
            result.reason = "OK"
            return result

        with patch.object(hook, "_is_pipeline_active", return_value=True), \
             patch("pipeline_completion_state.get_completed_agents", return_value=set()), \
             patch("pipeline_completion_state.get_validation_mode", return_value="strict"), \
             patch("agent_ordering_gate.check_ordering_prerequisites", side_effect=mock_check):
            decision, reason = hook.validate_pipeline_ordering("Agent", {
                "subagent_type": "planner",
                "prompt": (
                    "You are the planner. Review the research context.\n"
                    "The implementer agent will handle implementation.\n"
                    "The researcher found that the implementer needs test data.\n"
                    "Plan the work for the implementer to execute."
                ),
            })
        assert decision == "allow"
        assert "planner" in reason.lower(), f"Expected reason to mention 'planner', got: {reason}"
        assert captured["target"] == "planner", (
            f"Expected target agent 'planner' but got '{captured['target']}'. "
            f"subagent_type field should take precedence over text extraction."
        )

    def test_no_subagent_type_falls_back_to_text_extraction(self, monkeypatch):
        """Agent with no subagent_type field should fall back to text extraction.

        This ensures backward compatibility for callers that do not set
        subagent_type.
        """
        monkeypatch.setenv("PRE_TOOL_PIPELINE_ORDERING", "true")
        captured = {}

        def mock_check(target, completed, validation_mode=None, launched_agents=None, pipeline_mode=None):
            captured["target"] = target
            result = MagicMock()
            result.passed = True
            result.reason = "OK"
            return result

        with patch.object(hook, "_is_pipeline_active", return_value=True), \
             patch("pipeline_completion_state.get_completed_agents", return_value=set()), \
             patch("pipeline_completion_state.get_validation_mode", return_value="strict"), \
             patch("agent_ordering_gate.check_ordering_prerequisites", side_effect=mock_check):
            decision, reason = hook.validate_pipeline_ordering("Agent", {
                "prompt": "You are the researcher-local agent. Research this topic.",
            })
        assert decision == "allow"
        assert captured["target"] == "researcher-local", (
            f"Expected text extraction to find 'researcher-local', got '{captured['target']}'."
        )

    def test_implementer_blocked_when_prerequisites_not_met(self, monkeypatch):
        """Implementer agent launched normally should be blocked if prerequisites not met.

        Ordering enforcement must still work correctly when subagent_type
        is properly set.
        """
        monkeypatch.setenv("PRE_TOOL_PIPELINE_ORDERING", "true")

        def mock_check(target, completed, validation_mode=None, launched_agents=None, pipeline_mode=None):
            result = MagicMock()
            result.passed = False
            result.reason = "ORDERING VIOLATION: implementer requires planner to complete first"
            return result

        with patch.object(hook, "_is_pipeline_active", return_value=True), \
             patch("pipeline_completion_state.get_completed_agents", return_value=set()), \
             patch("pipeline_completion_state.get_validation_mode", return_value="strict"), \
             patch("agent_ordering_gate.check_ordering_prerequisites", side_effect=mock_check):
            decision, reason = hook.validate_pipeline_ordering("Agent", {
                "subagent_type": "implementer",
                "prompt": "You are the agent. Execute the plan.",
            })
        assert decision == "deny"
        assert "ORDERING VIOLATION" in reason

    def test_multiple_agent_names_in_prompt_subagent_type_wins(self, monkeypatch):
        """Agent prompt mentions multiple agent names -- subagent_type takes precedence.

        Text extraction would match whichever agent name appears first
        (longest-first sort), but subagent_type should override all text matches.
        """
        monkeypatch.setenv("PRE_TOOL_PIPELINE_ORDERING", "true")
        captured = {}

        def mock_check(target, completed, validation_mode=None, launched_agents=None, pipeline_mode=None):
            captured["target"] = target
            result = MagicMock()
            result.passed = True
            result.reason = "OK"
            return result

        with patch.object(hook, "_is_pipeline_active", return_value=True), \
             patch("pipeline_completion_state.get_completed_agents", return_value=set()), \
             patch("pipeline_completion_state.get_validation_mode", return_value="strict"), \
             patch("agent_ordering_gate.check_ordering_prerequisites", side_effect=mock_check):
            decision, reason = hook.validate_pipeline_ordering("Agent", {
                "subagent_type": "reviewer",
                "prompt": (
                    "You are the reviewer. Check the implementer output.\n"
                    "The planner defined these requirements.\n"
                    "The researcher-local gathered this context.\n"
                    "The security-auditor will run after you."
                ),
            })
        assert decision == "allow"
        assert captured["target"] == "reviewer", (
            f"Expected 'reviewer' from subagent_type, got '{captured['target']}'. "
            f"Text extraction would have matched 'researcher-local' or 'security-auditor'."
        )

    def test_empty_subagent_type_falls_back_to_text_extraction(self, monkeypatch):
        """Empty subagent_type field should fall back to text extraction.

        Some callers may set subagent_type to an empty string explicitly.
        This must behave identically to the field being absent.
        """
        monkeypatch.setenv("PRE_TOOL_PIPELINE_ORDERING", "true")
        captured = {}

        def mock_check(target, completed, validation_mode=None, launched_agents=None, pipeline_mode=None):
            captured["target"] = target
            result = MagicMock()
            result.passed = True
            result.reason = "OK"
            return result

        with patch.object(hook, "_is_pipeline_active", return_value=True), \
             patch("pipeline_completion_state.get_completed_agents", return_value=set()), \
             patch("pipeline_completion_state.get_validation_mode", return_value="strict"), \
             patch("agent_ordering_gate.check_ordering_prerequisites", side_effect=mock_check):
            decision, reason = hook.validate_pipeline_ordering("Agent", {
                "subagent_type": "",
                "prompt": "You are the test-master. Run the acceptance tests.",
            })
        assert decision == "allow"
        assert captured["target"] == "test-master", (
            f"Expected text extraction fallback to find 'test-master', got '{captured['target']}'."
        )

    def test_launched_agents_kwarg_forwarded_to_ordering_gate(self, monkeypatch):
        """Regression test for Issue #690: launched_agents kwarg must reach check_ordering_prerequisites.

        Bug: After #686 added launched_agents=launched to the call site in
        unified_pre_tool.py, mock stubs in this class lacked the parameter,
        causing KeyError on 'target' (mock crashed before capturing) or
        incorrect allow/deny decisions.

        This test verifies the kwarg is actually forwarded by capturing it.
        Without the fix, the mock would raise TypeError on the unexpected kwarg.
        """
        monkeypatch.setenv("PRE_TOOL_PIPELINE_ORDERING", "true")
        captured = {}

        def mock_check(target, completed, validation_mode=None, launched_agents=None, pipeline_mode=None):
            captured["target"] = target
            captured["launched_agents"] = launched_agents
            result = MagicMock()
            result.passed = True
            result.reason = "OK"
            return result

        with patch.object(hook, "_is_pipeline_active", return_value=True), \
             patch("pipeline_completion_state.get_completed_agents", return_value=set()), \
             patch("pipeline_completion_state.get_launched_agents", return_value={"planner"}), \
             patch("pipeline_completion_state.get_validation_mode", return_value="strict"), \
             patch("agent_ordering_gate.check_ordering_prerequisites", side_effect=mock_check):
            decision, reason = hook.validate_pipeline_ordering("Agent", {
                "subagent_type": "implementer",
                "prompt": "You are the implementer.",
            })
        assert decision == "allow"
        assert captured["target"] == "implementer"
        # The launched_agents kwarg should be forwarded from the hook
        assert captured["launched_agents"] is not None, (
            "launched_agents kwarg was not forwarded to check_ordering_prerequisites. "
            "This is the regression from Issue #690."
        )
