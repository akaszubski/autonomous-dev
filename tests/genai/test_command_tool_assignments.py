"""GenAI semantic tests for command allowed-tools assignments.

Replaces hardcoded EXPECTED_TOOLS dict from test_command_allowed_tools.py.
Instead of maintaining a stale mapping of 7/15 commands, asks an LLM to
judge whether each command's tool set makes sense given its purpose.

REGRESSION CONTEXT: The old test had VALID_TOOLS missing 15+ native tools
and EXPECTED_TOOLS covering only 7 of 15 commands. New commands were never
validated. This GenAI test covers ALL commands dynamically.
"""

import json
import yaml
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).parent.parent.parent
COMMANDS_DIR = PROJECT_ROOT / "plugins" / "autonomous-dev" / "commands"


def _parse_frontmatter(file_path: Path) -> dict:
    content = file_path.read_text(encoding='utf-8')
    if not content.startswith('---'):
        return {}
    parts = content.split('---', 2)
    if len(parts) < 3:
        return {}
    try:
        return yaml.safe_load(parts[1].strip()) or {}
    except yaml.YAMLError:
        return {}


def _get_command_summary(file_path: Path) -> str:
    """Extract command name, description, and first ~50 lines for context."""
    content = file_path.read_text(encoding='utf-8')
    fm = _parse_frontmatter(file_path)
    # Get body (after frontmatter)
    parts = content.split('---', 2)
    body = parts[2][:2000] if len(parts) >= 3 else content[:2000]
    return (
        f"Command: {file_path.name}\n"
        f"Description: {fm.get('description', 'N/A')}\n"
        f"Allowed tools: {fm.get('allowed-tools', [])}\n"
        f"First ~2000 chars of body:\n{body}"
    )


def _all_commands() -> list[Path]:
    return sorted(COMMANDS_DIR.glob("*.md"))


def _commands_with_tools() -> list[tuple[str, list[str], str]]:
    """Return (name, tools, summary) for each command with allowed-tools."""
    result = []
    for cmd in _all_commands():
        fm = _parse_frontmatter(cmd)
        tools = fm.get('allowed-tools', [])
        if tools:
            result.append((cmd.name, tools, _get_command_summary(cmd)))
    return result


@pytest.mark.genai
class TestCommandToolAssignmentsSemantic:
    """LLM judges whether each command's tool set is appropriate."""

    @pytest.mark.parametrize(
        "cmd_name,tools,summary",
        _commands_with_tools(),
        ids=[t[0] for t in _commands_with_tools()],
    )
    def test_tools_appropriate_for_command(self, genai, cmd_name, tools, summary):
        """Each command's tool set should make sense for what it does."""
        result = genai.judge(
            question=f"Is this tool assignment appropriate for the {cmd_name} command?",
            context=summary,
            criteria=(
                "Judge whether the allowed-tools list makes sense for this command's purpose.\n"
                "Rules:\n"
                "- Read-only/diagnostic commands (health-check, status) should NOT have Write/Edit\n"
                "- Commands that spawn sub-agents need 'Task' (for agent orchestration)\n"
                "- Commands that modify code need Write and/or Edit\n"
                "- Commands that search code need Grep and Glob\n"
                "- Commands that run shell commands need Bash\n"
                "- Commands doing web research need WebSearch/WebFetch\n"
                "- Over-permissioned is worse than under-permissioned (principle of least privilege)\n\n"
                "Score 10 if tools are a good fit. Deduct 3 per clearly wrong tool "
                "(e.g., Write on a read-only command, missing Bash for a command that runs shell). "
                "Deduct 1 for minor concerns (slightly broad but defensible)."
            ),
            category="architecture",
        )
        assert result["band"] != "hard_fail", (
            f"{cmd_name} tool assignment inappropriate: {result['reasoning']}\n"
            f"Tools: {tools}"
        )

    def test_all_commands_covered(self, genai):
        """Every non-internal command should have allowed-tools."""
        # Internal commands inherit tools from parent
        INTERNAL = {"implement-batch.md", "implement-resume.md"}
        all_cmds = _all_commands()
        without_tools = [
            c.name for c in all_cmds
            if not _parse_frontmatter(c).get('allowed-tools')
            and c.name not in INTERNAL
        ]
        assert not without_tools, (
            f"Commands without allowed-tools (not validated): {without_tools}\n"
            f"Add allowed-tools frontmatter or mark as internal"
        )

    def test_no_command_is_over_permissioned(self, genai):
        """Non-pipeline commands shouldn't have ALL tools."""
        # implement.md is the full SDLC pipeline coordinator — needs everything
        PIPELINE_COMMANDS = {"implement.md"}

        all_tool_names = set()
        for cmd in _all_commands():
            tools = _parse_frontmatter(cmd).get('allowed-tools', [])
            all_tool_names.update(tools)

        over_permissioned = []
        for cmd in _all_commands():
            if cmd.name in PIPELINE_COMMANDS:
                continue
            tools = set(_parse_frontmatter(cmd).get('allowed-tools', []))
            if all_tool_names and len(tools) / len(all_tool_names) > 0.8:
                over_permissioned.append(f"{cmd.name}: {len(tools)}/{len(all_tool_names)} tools")

        assert not over_permissioned, (
            f"Over-permissioned commands (>80% of all tools):\n"
            + "\n".join(f"  - {o}" for o in over_permissioned)
        )

    def test_read_only_commands_no_write(self, genai):
        """Commands that are clearly read-only should not have Write/Edit."""
        read_only_indicators = ["health-check", "status", "pipeline-status"]
        violations = []

        for cmd in _all_commands():
            name = cmd.stem
            if any(indicator in name for indicator in read_only_indicators):
                tools = set(_parse_frontmatter(cmd).get('allowed-tools', []))
                write_tools = tools & {'Write', 'Edit'}
                if write_tools:
                    violations.append(f"{cmd.name}: has {write_tools}")

        assert not violations, (
            f"Read-only commands with write tools:\n"
            + "\n".join(f"  - {v}" for v in violations)
        )
