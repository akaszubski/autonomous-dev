"""
Single source of truth for native Claude Code tool names.

All tools listed here are built into Claude Code and should:
- Be auto-approved by hooks (bypass all validation layers)
- Be included in settings.json permissions.allow
- Be included in auto_approve_policy.json tools.always_allowed

When Claude Code adds new tools, add them HERE and run:
    pytest tests/unit/lib/test_native_tools_sync.py
to verify all consumers are updated.

See Also:
    - hooks/unified_pre_tool.py (NATIVE_TOOLS set)
    - config/auto_approve_policy.json (tools.always_allowed)
    - templates/settings.local.json (permissions.allow)
    - lib/tool_validator.py (default policy always_allowed)
"""

# Every native Claude Code tool. Sorted alphabetically.
NATIVE_TOOLS: set[str] = {
    "Agent",
    "AgentOutputTool",
    "AskUserQuestion",
    "Bash",
    "BashOutput",
    "Edit",
    "EnterPlanMode",
    "EnterWorktree",
    "ExitPlanMode",
    "Glob",
    "Grep",
    "KillShell",
    "LSP",
    "NotebookEdit",
    "Read",
    "Skill",
    "SlashCommand",
    "Task",
    "TaskCreate",
    "TaskGet",
    "TaskList",
    "TaskOutput",
    "TaskStop",
    "TaskUpdate",
    "TodoWrite",
    "ToolSearch",
    "WebFetch",
    "WebSearch",
    "Write",
}

# Extra entries for settings.json permissions.allow that aren't tool names
# (e.g., wildcard patterns for MCP tools)
SETTINGS_EXTRA_ALLOW: list[str] = [
    "mcp__*",
]
