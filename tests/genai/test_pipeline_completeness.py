"""GenAI UAT: Pipeline completeness validation.

Validates implement.md defines all SDLC steps and references correct agents.
"""

import pytest

from .conftest import PROJECT_ROOT

pytestmark = [pytest.mark.genai]

PLUGIN_ROOT = PROJECT_ROOT / "plugins" / "autonomous-dev"


class TestPipelineCompleteness:
    def test_implement_defines_all_sdlc_steps(self, genai):
        """implement.md should define all 8 SDLC pipeline steps."""
        implement_md = (PLUGIN_ROOT / "commands" / "implement.md").read_text()

        agents_dir = PLUGIN_ROOT / "agents"
        agent_names = sorted(
            f.stem for f in agents_dir.glob("*.md")
            if "archived" not in str(f)
        )

        result = genai.judge(
            question="Does implement.md define all 8 SDLC steps? Does each step reference the correct agent?",
            context=f"implement.md content:\n{implement_md[:6000]}\n\nAvailable agents: {agent_names}",
            criteria="The implement command should define a clear multi-step pipeline "
            "(research, plan, test, implement, review, security, docs, etc). "
            "Each step should reference a specific agent. "
            "Score 10 = all steps clearly defined with agent refs, 7 = mostly complete, 4 = missing steps.",
        )
        assert result["score"] >= 7, f"Pipeline completeness issue: {result['reasoning']}"

    def test_agents_cover_sdlc_roles(self, genai):
        """Agent files should cover the key SDLC roles."""
        agents_dir = PLUGIN_ROOT / "agents"
        agent_samples = []
        for f in sorted(agents_dir.glob("*.md")):
            if "archived" not in str(f):
                content = f.read_text()[:500]
                agent_samples.append(f"--- {f.stem} ---\n{content}")

        result = genai.judge(
            question="Do these agents cover the full SDLC lifecycle?",
            context="\n\n".join(agent_samples[:10]),
            criteria="A complete SDLC pipeline needs: research, planning, testing, implementation, "
            "code review, security audit, and documentation. Score by coverage of these roles.",
        )
        assert result["score"] >= 7, f"Agent SDLC coverage gap: {result['reasoning']}"
