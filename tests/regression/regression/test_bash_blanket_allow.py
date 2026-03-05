"""Regression test: All settings templates must include all native tools.

Root cause: Templates were hand-maintained, so they drifted — some missing
Bash, LSP, AgentOutputTool, SlashCommand, BashOutput, etc. Any missing tool
causes unexpected approval prompts in deployed repos.

Canonical native tool list comes from unified_pre_tool.py NATIVE_TOOLS.
"""

import json
from pathlib import Path

import pytest

PLUGIN_DIR = Path(__file__).resolve().parents[3] / "plugins" / "autonomous-dev"
TEMPLATES_DIR = PLUGIN_DIR / "templates"
CONFIG_DIR = PLUGIN_DIR / "config"

# The canonical list of all native Claude Code tools that should never
# trigger approval prompts. Must match NATIVE_TOOLS in unified_pre_tool.py.
NATIVE_TOOLS = {
    "Read", "Write", "Edit", "Glob", "Grep", "Bash",
    "Task", "TaskOutput", "TaskCreate", "TaskUpdate", "TaskList", "TaskGet", "TaskStop",
    "AskUserQuestion", "Skill", "SlashCommand", "BashOutput", "NotebookEdit",
    "TodoWrite", "EnterPlanMode", "ExitPlanMode", "AgentOutputTool", "KillShell",
    "LSP", "WebFetch", "WebSearch",
    "Agent", "EnterWorktree",
}

# Tools that are always required in every template's allow list.
# Bash is excluded because granular-bash and permission-batching handle it specially.
# LSP, SlashCommand, BashOutput, AgentOutputTool, KillShell are internal tools
# that Claude Code manages — they don't need explicit allow entries.
REQUIRED_ALLOW_TOOLS = {
    "Read", "Write", "Edit", "Glob", "Grep",
    "Agent", "AskUserQuestion", "EnterPlanMode", "ExitPlanMode", "EnterWorktree",
    "Skill", "WebFetch", "WebSearch", "NotebookEdit", "TodoWrite",
    "TaskCreate", "TaskUpdate", "TaskList", "TaskGet", "TaskStop", "Task",
}

# Templates that intentionally use granular Bash (not blanket)
GRANULAR_BASH_TEMPLATES = {
    "settings.granular-bash.json",
    "settings.permission-batching.json",
}


def _get_settings_files():
    """Collect all settings JSON files from templates and config."""
    files = []
    for d in [TEMPLATES_DIR, CONFIG_DIR]:
        if d.exists():
            files.extend(d.glob("*settings*.json"))
    return files


@pytest.mark.parametrize("settings_file", _get_settings_files(), ids=lambda p: p.name)
def test_required_tools_present(settings_file):
    """Every settings template must include all required tools in allow list."""
    data = json.loads(settings_file.read_text())
    permissions = data.get("permissions", {})
    allow_list = permissions.get("allow", [])

    if not allow_list:
        pytest.skip(f"{settings_file.name} has no permissions.allow section")

    # Extract tool names (strip parenthetical args like "Bash(:*)")
    allowed_tools = set()
    for entry in allow_list:
        tool_name = entry.split("(")[0] if "(" in entry else entry
        allowed_tools.add(tool_name)

    missing = REQUIRED_ALLOW_TOOLS - allowed_tools
    assert not missing, (
        f"{settings_file.name} is missing required tools in permissions.allow: {sorted(missing)}\n"
        f"These missing tools will cause unexpected approval prompts in deployed repos.\n"
        f"Add them to the allow list."
    )


@pytest.mark.parametrize("settings_file", _get_settings_files(), ids=lambda p: p.name)
def test_no_granular_bash_in_allow(settings_file):
    """Non-granular templates must not use Bash(cmd:*) in allow list."""
    if settings_file.name in GRANULAR_BASH_TEMPLATES:
        pytest.skip(f"{settings_file.name} is an intentional granular template")

    data = json.loads(settings_file.read_text())
    allow_list = data.get("permissions", {}).get("allow", [])

    granular_entries = [
        entry for entry in allow_list
        if entry.startswith("Bash(") and entry not in ("Bash(:*)",)
    ]

    assert not granular_entries, (
        f"{settings_file.name} has granular Bash permissions in 'allow' that will "
        f"cause unexpected approval prompts. Use blanket 'Bash' or 'Bash(:*)' instead.\n"
        f"Found: {granular_entries[:5]}{'...' if len(granular_entries) > 5 else ''}"
    )


@pytest.mark.parametrize("settings_file", _get_settings_files(), ids=lambda p: p.name)
def test_blanket_bash_present(settings_file):
    """Non-granular templates must have blanket Bash in allow list."""
    if settings_file.name in GRANULAR_BASH_TEMPLATES:
        pytest.skip(f"{settings_file.name} handles Bash differently by design")

    data = json.loads(settings_file.read_text())
    allow_list = data.get("permissions", {}).get("allow", [])

    if not allow_list:
        pytest.skip(f"{settings_file.name} has no permissions.allow section")

    has_blanket_bash = any(entry in ("Bash", "Bash(:*)") for entry in allow_list)
    assert has_blanket_bash, (
        f"{settings_file.name} has no blanket Bash in allow list. "
        f"Add 'Bash' to prevent approval prompts for bash commands."
    )


def test_native_tools_match_hook():
    """NATIVE_TOOLS in this test must match NATIVE_TOOLS in unified_pre_tool.py."""
    hook_path = PLUGIN_DIR / "hooks" / "unified_pre_tool.py"
    content = hook_path.read_text()

    # Extract the set from the source
    import re
    match = re.search(r'NATIVE_TOOLS\s*=\s*\{([^}]+)\}', content)
    assert match, "Could not find NATIVE_TOOLS set in unified_pre_tool.py"

    # Parse tool names from the source
    hook_tools = set(re.findall(r'"(\w+)"', match.group(1)))

    assert NATIVE_TOOLS == hook_tools, (
        f"NATIVE_TOOLS in test ({sorted(NATIVE_TOOLS - hook_tools)} extra, "
        f"{sorted(hook_tools - NATIVE_TOOLS)} missing) doesn't match "
        f"unified_pre_tool.py. Update one to match the other."
    )


def test_policy_file_matches_native_tools():
    """auto_approve_policy.json always_allowed must include all native tools."""
    policy_path = CONFIG_DIR / "auto_approve_policy.json"
    if not policy_path.exists():
        pytest.skip("No auto_approve_policy.json found")

    data = json.loads(policy_path.read_text())
    always_allowed = set(data.get("tools", {}).get("always_allowed", []))

    missing = NATIVE_TOOLS - always_allowed
    assert not missing, (
        f"auto_approve_policy.json is missing native tools from always_allowed: {sorted(missing)}\n"
        f"This causes the MCP security layer to reject these tools."
    )
