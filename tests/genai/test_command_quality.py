"""GenAI UAT: Command implementation quality.

Validates command files follow structural patterns.
"""

import pytest

from .conftest import PROJECT_ROOT

pytestmark = [pytest.mark.genai]

PLUGIN_ROOT = PROJECT_ROOT / "plugins" / "autonomous-dev"
COMMANDS_DIR = PLUGIN_ROOT / "commands"


def _read_commands() -> dict[str, str]:
    """Read all command markdown files."""
    commands = {}
    if COMMANDS_DIR.exists():
        for f in sorted(COMMANDS_DIR.glob("*.md")):
            commands[f.stem] = f.read_text(errors="ignore")[:2000]
    return commands


class TestCommandQuality:
    def test_commands_have_step_structure(self, genai):
        """Major commands should have STEP markers for pipeline structure."""
        commands = _read_commands()
        major_cmds = {k: v for k, v in commands.items() if k in ("implement", "create-issue", "sync")}

        if not major_cmds:
            pytest.skip("No major commands found")

        result = genai.judge(
            question="Do major commands use STEP markers for structured execution?",
            context="\n\n".join(f"--- {name} ---\n{content}" for name, content in major_cmds.items()),
            criteria="Pipeline commands (implement, create-issue) should have numbered STEP markers "
            "or equivalent structured sections. Score by percentage of commands with structure.",
        )
        assert result["score"] >= 5, f"Missing structure: {result['reasoning']}"

    def test_commands_reference_agents(self, genai):
        """Commands should invoke agents via Task tool."""
        commands = _read_commands()

        result = genai.judge(
            question="Do commands reference specialist agents for execution?",
            context="\n\n".join(f"--- {name} ---\n{content}" for name, content in list(commands.items())[:8]),
            criteria="Commands should delegate work to specialist agents (researcher, planner, "
            "implementer, etc.) or reference specific tools. Commands that are purely "
            "informational are exempt. Score by coverage of actionable commands.",
        )
        assert result["score"] >= 5, f"Agent reference gaps: {result['reasoning']}"

    def test_no_deprecated_references(self, genai):
        """Commands should not reference deprecated names."""
        commands = _read_commands()
        all_content = "\n".join(commands.values())

        deprecated = ["auto-implement", "auto_implement", "/auto-implement", "cline", "aider"]
        found = [d for d in deprecated if d.lower() in all_content.lower()]

        result = genai.judge(
            question="Do commands reference deprecated tools or names?",
            context=f"Deprecated terms found: {found}\n\nCommand names: {list(commands.keys())}",
            criteria="Commands should not reference deprecated tool names (auto-implement, cline, aider). "
            "Score 10 = no deprecated refs, 5 = only in comments, 0 = in active instructions.",
        )
        assert result["score"] >= 7, f"Deprecated references: {result['reasoning']}"
