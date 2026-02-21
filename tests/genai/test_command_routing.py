"""GenAI UAT: Command routing consistency.

Validates CLAUDE.md command table matches actual command files on disk.
"""

import pytest

from .conftest import PROJECT_ROOT

pytestmark = [pytest.mark.genai]

PLUGIN_ROOT = PROJECT_ROOT / "plugins" / "autonomous-dev"


class TestCommandRouting:
    def test_documented_commands_match_disk(self, genai):
        """CLAUDE.md command table should match actual command files."""
        claude_md = (PROJECT_ROOT / "CLAUDE.md").read_text()

        commands_dir = PLUGIN_ROOT / "commands"
        commands_on_disk = sorted(
            f.stem for f in commands_dir.glob("*.md")
            if f.stem != "__init__"
        )

        result = genai.judge(
            question="Are the commands documented in CLAUDE.md consistent with command files on disk?",
            context=f"CLAUDE.md command section:\n{claude_md[:4000]}\n\nCommand files on disk: {commands_on_disk}",
            criteria="Every command in the CLAUDE.md table should have a corresponding .md file. "
            "Every .md file should be documented. Score by consistency percentage. "
            "10 = perfect match, 7 = minor gaps, 4 = significant mismatches.",
        )
        assert result["score"] >= 7, f"Command routing inconsistency: {result['reasoning']}"

    def test_command_descriptions_accurate(self, genai):
        """Command descriptions in CLAUDE.md should match actual command content."""
        claude_md = (PROJECT_ROOT / "CLAUDE.md").read_text()

        commands_dir = PLUGIN_ROOT / "commands"
        cmd_samples = []
        for f in sorted(commands_dir.glob("*.md"))[:8]:
            content = f.read_text()[:500]
            cmd_samples.append(f"--- {f.stem} ---\n{content}")

        result = genai.judge(
            question="Do the command descriptions in CLAUDE.md accurately describe what each command does?",
            context=f"CLAUDE.md:\n{claude_md[:3000]}\n\nActual command content:\n{''.join(cmd_samples)[:4000]}",
            criteria="Command descriptions should match the actual purpose of each command file. "
            "Score by accuracy of descriptions. 10 = all accurate, 7 = mostly accurate.",
        )
        assert result["score"] >= 7, f"Command description inaccuracy: {result['reasoning']}"
