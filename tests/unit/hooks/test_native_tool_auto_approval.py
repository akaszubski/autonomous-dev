"""
Regression tests for native Claude Code tool auto-approval.

Ensures all native tools (TaskCreate, TaskUpdate, Read, Edit, etc.) are
auto-approved through the unified_pre_tool.py hook without user prompts.

Root cause (2026-02-06): The policy file auto_approve_policy.json was missing
TaskCreate/Update/List/Get/Stop from tools.always_allowed. The MCP Security
layer fell through to auto_approval_engine which rejected unknown tools.
The agent authorization layer (Layer 2) was incorrectly gutted to work around
this, which broke workflow enforcement for ad-hoc code changes.

Fix: Added NATIVE_TOOLS bypass in validate_mcp_security + synced policy file.
These tests prevent both regressions from recurring.
"""

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest


# Find project root
current = Path.cwd()
while current != current.parent:
    if (current / ".git").exists() or (current / ".claude").exists():
        project_root = current
        break
    current = current.parent
else:
    project_root = Path.cwd()

HOOK_PATH = project_root / "plugins/autonomous-dev/hooks/unified_pre_tool.py"
POLICY_SOURCE = project_root / "plugins/autonomous-dev/config/auto_approve_policy.json"
POLICY_INSTALLED = project_root / ".claude/config/auto_approve_policy.json"

# The minimum set of native tools that MUST be auto-approved.
# If Claude Code adds new tools, add them here.
REQUIRED_NATIVE_TOOLS = {
    "Read", "Write", "Edit", "Glob", "Grep", "Bash",
    "Task", "TaskOutput", "TaskCreate", "TaskUpdate", "TaskList", "TaskGet", "TaskStop",
    "AskUserQuestion", "Skill", "SlashCommand", "BashOutput", "NotebookEdit",
    "TodoWrite", "EnterPlanMode", "ExitPlanMode", "AgentOutputTool", "KillShell",
    "LSP", "WebFetch", "WebSearch",
}


def run_hook(tool_name: str, tool_input: dict, env_overrides: dict = None) -> dict:
    """Run the unified_pre_tool hook and return parsed output."""
    env = os.environ.copy()
    env.update({
        "SANDBOX_ENABLED": "false",
        "MCP_AUTO_APPROVE": "true",
        "PRE_TOOL_AGENT_AUTH": "true",
        "PRE_TOOL_BATCH_PERMISSION": "false",
    })
    env.update(env_overrides or {})

    input_data = json.dumps({"tool_name": tool_name, "tool_input": tool_input})

    result = subprocess.run(
        [sys.executable, str(HOOK_PATH)],
        input=input_data,
        capture_output=True,
        text=True,
        env=env,
        cwd=str(project_root),
    )

    if result.returncode != 0:
        pytest.fail(f"Hook failed with exit code {result.returncode}: {result.stderr}")

    try:
        return json.loads(result.stdout)
    except json.JSONDecodeError:
        pytest.fail(f"Hook produced invalid JSON: {result.stdout[:500]}")


# Tools that MUST be in policy always_allowed (no dedicated validator).
# Bash, WebFetch, WebSearch have their own validators and are NOT required here.
REQUIRED_IN_POLICY = REQUIRED_NATIVE_TOOLS - {"Bash", "WebFetch", "WebSearch"}


class TestPolicyFileSync:
    """Verify policy files contain all required native tools."""

    def _load_always_allowed(self, path: Path) -> set:
        """Load always_allowed from a policy file."""
        if not path.exists():
            pytest.skip(f"Policy file not found: {path}")
        policy = json.loads(path.read_text())
        return set(policy.get("tools", {}).get("always_allowed", []))

    def test_source_policy_has_all_required_tools(self):
        """Source policy file must include tools without dedicated validators."""
        allowed = self._load_always_allowed(POLICY_SOURCE)
        missing = REQUIRED_IN_POLICY - allowed
        assert not missing, (
            f"Source policy file is missing tools: {sorted(missing)}. "
            f"File: {POLICY_SOURCE}"
        )

    def test_installed_policy_has_all_required_tools(self):
        """Installed policy file must include tools without dedicated validators."""
        allowed = self._load_always_allowed(POLICY_INSTALLED)
        missing = REQUIRED_IN_POLICY - allowed
        assert not missing, (
            f"Installed policy file is missing tools: {sorted(missing)}. "
            f"File: {POLICY_INSTALLED}"
        )

    def test_source_and_installed_policy_in_sync(self):
        """Source and installed policy files must have the same always_allowed."""
        source = self._load_always_allowed(POLICY_SOURCE)
        installed = self._load_always_allowed(POLICY_INSTALLED)
        only_source = source - installed
        only_installed = installed - source
        assert not only_source and not only_installed, (
            f"Policy files out of sync.\n"
            f"Only in source: {sorted(only_source)}\n"
            f"Only in installed: {sorted(only_installed)}"
        )


class TestNativeToolsAutoApproved:
    """
    REGRESSION TEST: All native Claude Code tools must be auto-approved
    through the full hook pipeline (all 4 layers).

    This was the root cause of the TaskCreate blocking bug.
    """

    @pytest.mark.parametrize("tool_name", sorted(REQUIRED_NATIVE_TOOLS))
    def test_native_tool_allowed(self, tool_name):
        """Each native tool must get 'allow' from the hook."""
        # Use minimal valid inputs for each tool type
        tool_inputs = {
            "Read": {"file_path": "/tmp/test.txt"},
            "Write": {"file_path": "/tmp/test.txt", "content": "x"},
            "Edit": {"file_path": "/tmp/test.txt", "old_string": "a", "new_string": "b"},
            "Glob": {"pattern": "*.py"},
            "Grep": {"pattern": "test"},
            "Bash": {"command": "echo hello"},
            "Task": {"prompt": "test", "description": "test", "subagent_type": "Explore"},
            "TaskOutput": {"task_id": "1", "block": False, "timeout": 1000},
            "TaskCreate": {"subject": "test", "description": "test"},
            "TaskUpdate": {"taskId": "1", "status": "completed"},
            "TaskList": {},
            "TaskGet": {"taskId": "1"},
            "TaskStop": {"task_id": "1"},
            "AskUserQuestion": {"questions": []},
            "Skill": {"skill": "test"},
            "SlashCommand": {"command": "test"},
            "BashOutput": {"task_id": "1", "block": False, "timeout": 1000},
            "NotebookEdit": {"notebook_path": "/tmp/test.ipynb", "new_source": "x"},
            "TodoWrite": {"todos": []},
            "EnterPlanMode": {},
            "ExitPlanMode": {},
            "AgentOutputTool": {"output": "test"},
            "KillShell": {"task_id": "1"},
            "LSP": {"action": "hover", "file_path": "/tmp/test.py", "line": 1, "character": 0},
            "WebFetch": {"url": "https://example.com", "prompt": "test"},
            "WebSearch": {"query": "test"},
        }
        tool_input = tool_inputs.get(tool_name, {})

        result = run_hook(tool_name, tool_input)
        output = result.get("hookSpecificOutput", {})
        decision = output.get("permissionDecision")
        reason = output.get("permissionDecisionReason", "")

        assert decision == "allow", (
            f"Native tool '{tool_name}' was NOT auto-approved.\n"
            f"Decision: {decision}\n"
            f"Reason: {reason}\n"
            f"This is the TaskCreate regression bug - native tools must not be "
            f"routed through MCP security validation."
        )


class TestMcpSecuritySkipsNativeTools:
    """Verify the MCP Security layer returns 'allow' for native tools."""

    def test_mcp_security_reason_mentions_native(self):
        """MCP Security reason should indicate native tool bypass."""
        result = run_hook("TaskCreate", {"subject": "test", "description": "test"})
        reason = result["hookSpecificOutput"]["permissionDecisionReason"]
        assert "Native tool" in reason or "not applicable" in reason, (
            f"MCP Security should mention native tool bypass. Got: {reason}"
        )

    def test_mcp_tool_still_validated(self):
        """MCP tools (mcp__*) should still go through MCP security validation."""
        result = run_hook("mcp__test__dangerous", {"path": "/etc/passwd"})
        output = result["hookSpecificOutput"]
        # Should NOT mention "native tool" - it's an MCP tool
        assert "Native tool" not in output.get("permissionDecisionReason", "")


class TestWorkflowEnforcementRegression:
    """
    Verify workflow enforcement (Layer 2) correctly:
    - Allows non-Edit/Write tools (TaskCreate, Bash, Read, etc.)
    - Blocks significant code changes to .py files outside /implement
    - Allows minor edits, exempt paths, non-code files
    """

    def test_task_tools_not_subject_to_workflow(self):
        """Task tools must not be subject to workflow enforcement."""
        for tool in ["TaskCreate", "TaskUpdate", "TaskList", "TaskGet", "TaskStop"]:
            result = run_hook(tool, {"subject": "test", "description": "test"})
            decision = result["hookSpecificOutput"]["permissionDecision"]
            assert decision == "allow", f"{tool} should not be blocked by workflow enforcement"

    def test_significant_code_edit_blocked(self):
        """Significant code additions to .py files should be blocked."""
        result = run_hook("Edit", {
            "file_path": "/tmp/app.py",
            "old_string": "pass",
            "new_string": "def handler():\n    return 'ok'\ndef process():\n    return True",
        }, {"ENFORCEMENT_LEVEL": "block"})

        decision = result["hookSpecificOutput"]["permissionDecision"]
        assert decision == "deny", "Significant code edits should be blocked"

    def test_minor_edit_allowed(self):
        """Minor edits (no new functions, few lines) should be allowed."""
        result = run_hook("Edit", {
            "file_path": "/tmp/app.py",
            "old_string": "x = 1",
            "new_string": "x = 2",
        }, {"ENFORCEMENT_LEVEL": "block"})

        decision = result["hookSpecificOutput"]["permissionDecision"]
        assert decision == "allow", "Minor edits should pass through"

    def test_test_file_exempt(self):
        """Test files should be exempt from workflow enforcement."""
        result = run_hook("Edit", {
            "file_path": "/tmp/test_app.py",
            "old_string": "pass",
            "new_string": "def test_handler():\n    assert True\ndef test_process():\n    assert True",
        }, {"ENFORCEMENT_LEVEL": "block"})

        decision = result["hookSpecificOutput"]["permissionDecision"]
        assert decision == "allow", "Test files should be exempt"

    def test_config_file_exempt(self):
        """Config files (.json, .yaml, .md) should be exempt."""
        for ext in [".json", ".yaml", ".md", ".toml"]:
            result = run_hook("Write", {
                "file_path": f"/tmp/config{ext}",
                "content": "def foo():\n    pass\ndef bar():\n    pass",
            }, {"ENFORCEMENT_LEVEL": "block"})

            decision = result["hookSpecificOutput"]["permissionDecision"]
            assert decision == "allow", f"{ext} files should be exempt"

    def test_enforcement_off_allows_everything(self):
        """ENFORCEMENT_LEVEL=off should allow all edits."""
        result = run_hook("Edit", {
            "file_path": "/tmp/app.py",
            "old_string": "pass",
            "new_string": "def handler():\n    return 'ok'\ndef process():\n    return True",
        }, {"ENFORCEMENT_LEVEL": "off"})

        decision = result["hookSpecificOutput"]["permissionDecision"]
        assert decision == "allow", "Enforcement off should allow everything"

    def test_pipeline_agent_allowed(self):
        """Pipeline agents (implementer, test-master) should bypass enforcement."""
        result = run_hook("Edit", {
            "file_path": "/tmp/app.py",
            "old_string": "pass",
            "new_string": "def handler():\n    return 'ok'\ndef process():\n    return True",
        }, {"ENFORCEMENT_LEVEL": "block", "CLAUDE_AGENT_NAME": "implementer"})

        decision = result["hookSpecificOutput"]["permissionDecision"]
        assert decision == "allow", "Pipeline agents should bypass enforcement"
