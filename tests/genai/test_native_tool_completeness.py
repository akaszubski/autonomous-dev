"""GenAI semantic test for native tool auto-approval completeness.

REGRESSION CONTEXT: We've had 4+ incidents where a Claude Code native tool
was missing from NATIVE_TOOLS in unified_pre_tool.py, causing the /implement
pipeline to prompt for confirmation mid-run. Each time, the hardcoded test
list was also incomplete.

Additionally, settings templates (settings.*.json) drifted independently —
some had granular Bash(cmd:*) instead of blanket Bash, others were missing
Agent, EnterWorktree, TaskStop, etc. This caused unexpected approval prompts
across all deployed repos on multiple machines.

This test asks an LLM to:
1. Identify any Claude Code native tools missing from our NATIVE_TOOLS set
2. Validate consistency between hook, policy, and settings templates
3. Detect settings templates that would cause approval prompt regressions
"""

import json
import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).parent.parent.parent
PLUGIN_DIR = PROJECT_ROOT / "plugins" / "autonomous-dev"
HOOK_DIR = PLUGIN_DIR / "hooks"
POLICY_FILE = PLUGIN_DIR / "config" / "auto_approve_policy.json"
TEMPLATES_DIR = PLUGIN_DIR / "templates"

sys.path.insert(0, str(HOOK_DIR))
sys.path.insert(0, str(PLUGIN_DIR / "lib"))

import unified_pre_tool as hook


def _load_policy_tools() -> list[str]:
    with open(POLICY_FILE) as f:
        return json.load(f)["tools"]["always_allowed"]


def _load_all_templates() -> dict[str, dict]:
    """Load all settings templates, returning {filename: parsed_json}."""
    templates = {}
    for f in TEMPLATES_DIR.glob("settings.*.json"):
        templates[f.name] = json.loads(f.read_text())
    return templates


def _extract_allow_tools(settings: dict) -> list[str]:
    """Extract tool names from a settings template's allow list."""
    allow = settings.get("permissions", {}).get("allow", [])
    tools = []
    for entry in allow:
        name = entry.split("(")[0] if "(" in entry else entry
        if name:
            tools.append(name)
    return sorted(set(tools))


@pytest.mark.genai
class TestNativeToolCompleteness:
    """LLM-as-judge validation that our native tool list is complete."""

    def test_no_missing_native_tools(self, genai):
        """Ask LLM if any known Claude Code native tools are missing from our set."""
        current_tools = sorted(hook.NATIVE_TOOLS)

        result = genai.judge(
            question="Are there any Claude Code native tools missing from this list?",
            context=f"Current NATIVE_TOOLS set:\n{json.dumps(current_tools, indent=2)}",
            criteria=(
                "Claude Code (Anthropic's CLI) provides these native tool categories:\n"
                "- File ops: Read, Write, Edit, Glob, Grep, NotebookEdit\n"
                "- Execution: Bash, BashOutput, KillShell\n"
                "- Task management: Task, TaskCreate, TaskUpdate, TaskList, TaskGet, TaskOutput, TaskStop\n"
                "- Agent/planning: Agent, AgentOutputTool, EnterPlanMode, ExitPlanMode, EnterWorktree\n"
                "- User interaction: AskUserQuestion, Skill, SlashCommand\n"
                "- Web: WebFetch, WebSearch\n"
                "- Code intelligence: LSP\n"
                "- Legacy/compat: TodoWrite\n"
                "- Tool discovery: ToolSearch\n\n"
                "Score 10 if the list contains ALL of these tools. "
                "Deduct 3 points per missing tool. "
                "If the list contains tools NOT in the categories above, that's fine (extra tools don't hurt). "
                "List any missing tools in your reasoning."
            ),
            category="architecture",
        )
        assert result["band"] != "hard_fail", (
            f"Missing native tools detected: {result['reasoning']}\n"
            f"Fix: add missing tools to NATIVE_TOOLS in unified_pre_tool.py "
            f"AND to always_allowed in auto_approve_policy.json"
        )
        # Soft fail is a warning — we want to know but it's not critical
        if result["band"] == "soft_fail":
            pytest.xfail(f"Possible missing tools (soft fail): {result['reasoning']}")

    def test_policy_and_hook_semantic_consistency(self, genai):
        """Ask LLM if the policy file and hook NATIVE_TOOLS serve the same purpose consistently."""
        policy_tools = sorted(_load_policy_tools())
        hook_tools = sorted(hook.NATIVE_TOOLS)

        policy_only = sorted(set(policy_tools) - set(hook_tools))
        hook_only = sorted(set(hook_tools) - set(policy_tools))

        result = genai.judge(
            question="Are these two lists consistent? Should they contain the same tools?",
            context=(
                f"Policy file always_allowed:\n{json.dumps(policy_tools, indent=2)}\n\n"
                f"Hook NATIVE_TOOLS:\n{json.dumps(hook_tools, indent=2)}\n\n"
                f"In policy but NOT in hook: {policy_only}\n"
                f"In hook but NOT in policy: {hook_only}"
            ),
            criteria=(
                "These two lists MUST be identical. The policy file's always_allowed "
                "defines which tools skip approval prompts, and the hook's NATIVE_TOOLS "
                "defines which tools bypass MCP security. A tool in one but not the other "
                "means broken auto-approval.\n\n"
                "Score 10 if lists are identical. "
                "Score 0 if ANY tool appears in one list but not the other. "
                "List the specific differences in your reasoning."
            ),
            category="architecture",
        )
        assert result["band"] != "hard_fail", (
            f"Policy/hook mismatch: {result['reasoning']}\n"
            f"Policy-only: {policy_only}, Hook-only: {hook_only}\n"
            f"Fix: make both lists identical"
        )

    def test_templates_cover_all_native_tools(self, genai):
        """Validate that all settings templates include necessary native tools.

        REGRESSION: settings.default.json and global_settings_template.json shipped
        with granular Bash(git:*) instead of blanket Bash, and were missing Agent,
        EnterWorktree, TaskStop. This caused approval prompts across 6 repos on 2 machines.
        """
        templates = _load_all_templates()
        hook_tools = sorted(hook.NATIVE_TOOLS)

        # Build comparison table
        comparison = {}
        for name, settings in templates.items():
            template_tools = _extract_allow_tools(settings)
            missing = sorted(set(hook_tools) - set(template_tools))
            has_granular_bash = [
                e for e in settings.get("permissions", {}).get("allow", [])
                if e.startswith("Bash(") and e not in ("Bash(:*)",)
            ]
            comparison[name] = {
                "tools_in_allow": template_tools,
                "missing_vs_hook": missing,
                "has_blanket_bash": any(
                    e in ("Bash", "Bash(:*)") for e in settings.get("permissions", {}).get("allow", [])
                ),
                "granular_bash_count": len(has_granular_bash),
            }

        result = genai.judge(
            question="Do these settings templates provide adequate tool coverage to prevent unexpected approval prompts?",
            context=(
                f"Hook NATIVE_TOOLS (canonical list):\n{json.dumps(hook_tools, indent=2)}\n\n"
                f"Template analysis:\n{json.dumps(comparison, indent=2)}"
            ),
            criteria=(
                "Each settings template defines which tools are auto-approved in Claude Code. "
                "If a native tool is missing from a template's allow list, users get unexpected "
                "approval prompts when that template is deployed.\n\n"
                "CRITICAL CHECK 1: Non-granular templates (NOT 'granular-bash' or 'permission-batching') "
                "MUST have blanket Bash (not Bash(git:*), Bash(npm:*), etc.) in their allow list. "
                "Granular entries cause prompts for any unlisted command.\n\n"
                "CRITICAL CHECK 2: ALL templates must include these core tools: "
                "Read, Write, Edit, Glob, Grep, Agent, AskUserQuestion, EnterPlanMode, "
                "ExitPlanMode, EnterWorktree, Skill, WebFetch, WebSearch, NotebookEdit, "
                "TodoWrite, TaskCreate, TaskUpdate, TaskList, TaskGet, TaskStop, Task.\n\n"
                "ACCEPTABLE: Templates may omit internal/implicit tools like LSP, SlashCommand, "
                "BashOutput, AgentOutputTool, KillShell — these are managed by Claude Code internally.\n\n"
                "ACCEPTABLE: 'granular-bash' template intentionally uses Bash(cmd:*) patterns.\n"
                "'permission-batching' template intentionally puts Bash in 'ask' not 'allow'.\n\n"
                "Score 10 if all templates pass both checks. "
                "Deduct 2 per template failing either check. "
                "List specific failures in reasoning."
            ),
            category="architecture",
        )
        assert result["band"] != "hard_fail", (
            f"Template tool coverage gaps: {result['reasoning']}\n"
            f"Fix: update templates to include all required tools. "
            f"See test_bash_blanket_allow.py for the canonical required list."
        )

    def test_three_layer_consistency(self, genai):
        """Validate hook NATIVE_TOOLS, policy always_allowed, and templates are all aligned.

        The three layers must agree:
        1. unified_pre_tool.py NATIVE_TOOLS — bypasses MCP security
        2. auto_approve_policy.json always_allowed — bypasses tool_validator
        3. settings.*.json permissions.allow — bypasses Claude Code permission system

        A tool present in layer 1+2 but missing from layer 3 means: the hook says
        'allow' but Claude Code still prompts because it's not in settings.json.
        """
        hook_tools = sorted(hook.NATIVE_TOOLS)
        policy_tools = sorted(_load_policy_tools())
        templates = _load_all_templates()

        # Find the "recommended" template (autonomous-dev.json)
        recommended = templates.get("settings.autonomous-dev.json", {})
        recommended_tools = _extract_allow_tools(recommended)

        # Find the "default" template
        default = templates.get("settings.default.json", {})
        default_tools = _extract_allow_tools(default)

        # Find the "local" template (deployed to repos)
        local = templates.get("settings.local.json", {})
        local_tools = _extract_allow_tools(local)

        result = genai.judge(
            question="Are these three permission layers consistent, or will missing tools cause approval prompts?",
            context=(
                f"Layer 1 - Hook NATIVE_TOOLS:\n{json.dumps(hook_tools, indent=2)}\n\n"
                f"Layer 2 - Policy always_allowed:\n{json.dumps(policy_tools, indent=2)}\n\n"
                f"Layer 3a - settings.autonomous-dev.json allow:\n{json.dumps(recommended_tools, indent=2)}\n\n"
                f"Layer 3b - settings.default.json allow:\n{json.dumps(default_tools, indent=2)}\n\n"
                f"Layer 3c - settings.local.json allow:\n{json.dumps(local_tools, indent=2)}\n\n"
                f"Tools in hook but NOT in default template: {sorted(set(hook_tools) - set(default_tools))}\n"
                f"Tools in hook but NOT in local template: {sorted(set(hook_tools) - set(local_tools))}\n"
                f"Tools in policy but NOT in hook: {sorted(set(policy_tools) - set(hook_tools))}\n"
                f"Tools in hook but NOT in policy: {sorted(set(hook_tools) - set(policy_tools))}"
            ),
            criteria=(
                "The three permission layers form a defense-in-depth system:\n"
                "- Layer 1 (hook): Bypasses MCP security for native tools\n"
                "- Layer 2 (policy): Bypasses tool_validator for native tools\n"
                "- Layer 3 (settings): Bypasses Claude Code's built-in permission prompt\n\n"
                "ALL THREE LAYERS must agree for a tool to be fully auto-approved. "
                "If a tool is in Layer 1+2 but missing from Layer 3, users still get prompted.\n\n"
                "IMPORTANT: Some internal tools (BashOutput, KillShell, AgentOutputTool, "
                "SlashCommand, LSP) don't need to be in Layer 3 because Claude Code handles them "
                "internally. The critical tools that MUST be in all layers are: "
                "Read, Write, Edit, Bash, Glob, Grep, Agent, Task*, WebFetch, WebSearch, "
                "AskUserQuestion, Skill, EnterPlanMode, ExitPlanMode, EnterWorktree, "
                "TodoWrite, NotebookEdit.\n\n"
                "Score 10 if all critical tools appear in all three layers. "
                "Score 0 if any critical tool is missing from any layer. "
                "List specific gaps in reasoning."
            ),
            category="architecture",
        )
        assert result["band"] != "hard_fail", (
            f"Three-layer permission inconsistency: {result['reasoning']}\n"
            f"Fix: ensure all critical tools appear in NATIVE_TOOLS, "
            f"auto_approve_policy.json, AND all settings templates."
        )
