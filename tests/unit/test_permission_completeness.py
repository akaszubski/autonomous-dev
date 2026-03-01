"""
Regression tests for permission completeness across settings templates and deployed repos.

Ensures that all native Claude Code tools are included in permission allow lists,
preventing the recurring issue where new tools (Agent, Task*, EnterWorktree) are
added to Claude Code but missing from our settings templates and deployed repos.

Date: 2026-03-02
"""

import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
TEMPLATES_DIR = ROOT / "plugins" / "autonomous-dev" / "templates"
POLICY_FILE = ROOT / "plugins" / "autonomous-dev" / "config" / "auto_approve_policy.json"

# Every native Claude Code tool that should be auto-allowed.
# Update this set when Claude Code adds new tools.
REQUIRED_PERMISSION_TOOLS = {
    "Read",
    "Write",
    "Edit",
    "Glob",
    "Grep",
    "Agent",
    "AskUserQuestion",
    "EnterPlanMode",
    "ExitPlanMode",
    "EnterWorktree",
    "Skill",
    "Task",
    "TaskCreate",
    "TaskUpdate",
    "TaskList",
    "TaskGet",
    "TaskStop",
    "WebFetch",
    "WebSearch",
    "TodoWrite",
    "NotebookEdit",
}

# Tools that must be in auto_approve_policy.json always_allowed
REQUIRED_POLICY_TOOLS = REQUIRED_PERMISSION_TOOLS | {
    "Bash",
    "AgentOutputTool",
    "KillShell",
    "LSP",
    "SlashCommand",
    "BashOutput",
}


class TestSettingsTemplatePermissions:
    """Verify settings templates include all required tool permissions."""

    def _get_template_allows(self, template_path: Path) -> set:
        data = json.loads(template_path.read_text())
        allows = data.get("permissions", {}).get("allow", [])
        # Extract bare tool names (ignore Bash(cmd:*) patterns)
        tools = set()
        for entry in allows:
            if "(" not in entry:
                tools.add(entry)
        return tools

    def test_default_template_has_all_required_tools(self):
        template = TEMPLATES_DIR / "settings.default.json"
        assert template.exists(), "Default settings template missing"
        allows = self._get_template_allows(template)
        missing = REQUIRED_PERMISSION_TOOLS - allows
        assert not missing, (
            f"Default template missing permissions: {sorted(missing)}. "
            f"Add them to plugins/autonomous-dev/templates/settings.default.json"
        )

    @pytest.mark.parametrize("template", sorted(TEMPLATES_DIR.glob("settings.*.json")))
    def test_all_templates_have_required_tools(self, template):
        allows = self._get_template_allows(template)
        missing = REQUIRED_PERMISSION_TOOLS - allows
        assert not missing, (
            f"{template.name} missing permissions: {sorted(missing)}. "
            f"Sync with settings.default.json"
        )


class TestAutoPolicyCompleteness:
    """Verify auto_approve_policy.json includes all native tools."""

    def test_policy_has_all_required_tools(self):
        assert POLICY_FILE.exists(), "Auto-approve policy file missing"
        data = json.loads(POLICY_FILE.read_text())
        always_allowed = set(data.get("tools", {}).get("always_allowed", []))
        missing = REQUIRED_POLICY_TOOLS - always_allowed
        assert not missing, (
            f"auto_approve_policy.json missing from always_allowed: {sorted(missing)}. "
            f"Add them to plugins/autonomous-dev/config/auto_approve_policy.json"
        )


class TestDeployedRepoPermissions:
    """Verify deployed repos have complete permissions (runs only when repos exist)."""

    REPOS = ["spektiv", "realign", "anyclaude"]

    def _get_repo_allows(self, repo_name: str) -> set:
        settings = Path.home() / "Dev" / repo_name / ".claude" / "settings.json"
        if not settings.exists():
            pytest.skip(f"Repo {repo_name} not found at {settings}")
        data = json.loads(settings.read_text())
        allows = data.get("permissions", {}).get("allow", [])
        tools = set()
        for entry in allows:
            if "(" not in entry:
                tools.add(entry)
        return tools

    @pytest.mark.parametrize("repo", REPOS)
    def test_deployed_repo_has_required_tools(self, repo):
        allows = self._get_repo_allows(repo)
        missing = REQUIRED_PERMISSION_TOOLS - allows
        assert not missing, (
            f"~/Dev/{repo}/.claude/settings.json missing permissions: {sorted(missing)}. "
            f"Run /sync --env or manually add them."
        )
