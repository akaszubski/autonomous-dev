"""GenAI UAT: Architecture validation.

Validates plugin structure matches documented architecture in CLAUDE.md.
"""

import pytest

from .conftest import PROJECT_ROOT

pytestmark = [pytest.mark.genai]

PLUGIN_ROOT = PROJECT_ROOT / "plugins" / "autonomous-dev"


def _list_dir_names(path, pattern="*.md"):
    """List stem names from a directory, excluding archived."""
    if not path.exists():
        return []
    return sorted(
        f.stem for f in path.glob(pattern) if "archived" not in str(f) and f.stem != "__init__"
    )


class TestArchitecture:
    def test_agents_documented_in_claude_md(self, genai):
        """All active agents on disk should be mentioned in CLAUDE.md."""
        agents_on_disk = _list_dir_names(PLUGIN_ROOT / "agents")
        claude_md = (PROJECT_ROOT / "CLAUDE.md").read_text()

        result = genai.judge(
            question="Does CLAUDE.md document all active agents?",
            context=f"Agents on disk: {agents_on_disk}\n\nCLAUDE.md content:\n{claude_md[:3000]}",
            criteria="All active agents should be referenced or accounted for in CLAUDE.md. "
            "Score based on coverage percentage. 10 = all mentioned, 5 = half missing.",
        )
        assert result["score"] >= 5, f"Agent documentation gap: {result['reasoning']}"

    def test_hooks_follow_lifecycle_pattern(self, genai):
        """Active hooks should follow documented lifecycle patterns."""
        hooks_dir = PLUGIN_ROOT / "hooks"
        hooks_on_disk = _list_dir_names(hooks_dir, "*.py")

        hook_samples = []
        for name in hooks_on_disk[:5]:
            hook_file = hooks_dir / f"{name}.py"
            if hook_file.exists():
                content = hook_file.read_text()[:1500]
                hook_samples.append(f"--- {name}.py ---\n{content}")

        result = genai.judge(
            question="Do hooks follow consistent lifecycle patterns?",
            context=f"Hook files on disk: {hooks_on_disk}\n\nSample hook content:\n{''.join(hook_samples)[:4000]}",
            criteria="Hooks should: use sys.exit() for exit codes, have docstrings, "
            "handle errors gracefully, follow a consistent pattern. "
            "Score 10 = exemplary consistency, 5 = acceptable, 0 = chaotic.",
        )
        assert result["score"] >= 5, f"Hook pattern issues: {result['reasoning']}"

    def test_commands_have_implementations(self, genai):
        """Each command .md should reference an agent or library."""
        commands_dir = PLUGIN_ROOT / "commands"
        commands = _list_dir_names(commands_dir)

        cmd_samples = []
        for name in commands[:8]:
            cmd_file = commands_dir / f"{name}.md"
            if cmd_file.exists():
                content = cmd_file.read_text()[:1000]
                cmd_samples.append(f"--- {name}.md ---\n{content}")

        result = genai.judge(
            question="Do commands reference their implementations (agents, libs, or tools)?",
            context=f"Commands: {commands}\n\nSamples:\n{''.join(cmd_samples)[:4000]}",
            criteria="Each command should reference at least one agent, library, or tool that "
            "implements its functionality. Score by percentage that have clear implementation refs.",
        )
        assert result["score"] >= 5, f"Command implementation gaps: {result['reasoning']}"
