"""GenAI semantic test for native tool auto-approval completeness.

REGRESSION CONTEXT: We've had 4+ incidents where a Claude Code native tool
was missing from NATIVE_TOOLS in unified_pre_tool.py, causing the /implement
pipeline to prompt for confirmation mid-run. Each time, the hardcoded test
list was also incomplete.

This test asks an LLM to identify any Claude Code native tools that are
missing from our NATIVE_TOOLS set, catching drift that no hardcoded list can.
"""

import json
import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).parent.parent.parent
HOOK_DIR = PROJECT_ROOT / "plugins" / "autonomous-dev" / "hooks"
POLICY_FILE = PROJECT_ROOT / "plugins" / "autonomous-dev" / "config" / "auto_approve_policy.json"

sys.path.insert(0, str(HOOK_DIR))
sys.path.insert(0, str(PROJECT_ROOT / "plugins" / "autonomous-dev" / "lib"))

import unified_pre_tool as hook


def _load_policy_tools() -> list[str]:
    with open(POLICY_FILE) as f:
        return json.load(f)["tools"]["always_allowed"]


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
                "- Legacy/compat: TodoWrite\n\n"
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
