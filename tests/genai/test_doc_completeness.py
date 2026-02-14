"""GenAI UAT: Documentation completeness.

Validates that documentation accurately reflects codebase state.
"""

import pytest

from .conftest import PROJECT_ROOT

pytestmark = [pytest.mark.genai]

PLUGIN_ROOT = PROJECT_ROOT / "plugins" / "autonomous-dev"


def _count_pattern_in_source(pattern: str) -> list[str]:
    """Find pattern occurrences in Python source files."""
    results = []
    for f in PLUGIN_ROOT.rglob("*.py"):
        if "archived" in str(f) or "__pycache__" in str(f):
            continue
        for i, line in enumerate(f.read_text(errors="ignore").splitlines(), 1):
            if pattern in line and not line.strip().startswith("#"):
                results.append(f"{f.relative_to(PROJECT_ROOT)}:{i}: {line.strip()}")
    return results


class TestDocCompleteness:
    def test_claude_md_covers_all_components(self, genai):
        """CLAUDE.md should mention agents, skills, commands, hooks."""
        claude_md = (PROJECT_ROOT / "CLAUDE.md").read_text()

        agents = sorted(f.stem for f in (PLUGIN_ROOT / "agents").glob("*.md") if "archived" not in str(f))
        commands = sorted(f.stem for f in (PLUGIN_ROOT / "commands").glob("*.md"))
        hooks = sorted(f.stem for f in (PLUGIN_ROOT / "hooks").glob("*.py") if f.stem != "__init__")

        result = genai.judge(
            question="Does CLAUDE.md cover all major component categories?",
            context=f"CLAUDE.md:\n{claude_md[:3000]}\n\nAgents: {agents}\nCommands: {commands}\nHooks: {hooks}",
            criteria="CLAUDE.md should reference or account for agents, commands, hooks, and skills "
            "as component categories. Individual items don't all need listing, but categories "
            "should be covered with approximate counts. Score 10 = comprehensive, 5 = adequate.",
        )
        assert result["score"] >= 5, f"Documentation gaps: {result['reasoning']}"

    def test_readme_matches_claude_md(self, genai):
        """README and CLAUDE.md should be broadly consistent."""
        readme_path = PROJECT_ROOT / "README.md"
        readme = readme_path.read_text()[:3000] if readme_path.exists() else "No README.md found"
        claude_md = (PROJECT_ROOT / "CLAUDE.md").read_text()[:3000]

        result = genai.judge(
            question="Are README.md and CLAUDE.md broadly consistent?",
            context=f"README.md:\n{readme}\n\nCLAUDE.md:\n{claude_md}",
            criteria="Key facts (project purpose, component counts, installation) should not "
            "contradict between the two files. Minor differences in detail are OK. "
            "Score 10 = perfectly aligned, 5 = no contradictions, 0 = conflicting info.",
        )
        assert result["score"] >= 5, f"README/CLAUDE.md drift: {result['reasoning']}"

    def test_todo_fixme_manageable(self, genai):
        """TODO/FIXME volume should be manageable."""
        todos = _count_pattern_in_source("TODO")
        fixmes = _count_pattern_in_source("FIXME")

        result = genai.judge(
            question="Is the volume of TODO/FIXME comments manageable?",
            context=f"TODO count: {len(todos)}\nFIXME count: {len(fixmes)}\n\nSamples:\n"
            + "\n".join((todos + fixmes)[:20]),
            criteria="A healthy codebase has <50 TODOs and <10 FIXMEs. "
            "Score 10 = very few, 5 = acceptable, 0 = overwhelming tech debt.",
        )
        assert result["score"] >= 3, f"Tech debt concerns: {result['reasoning']}"

    def test_dead_code_indicators(self, genai):
        """Minimal commented-out code (def/class)."""
        commented_defs = _count_pattern_in_source("# def ")
        commented_classes = _count_pattern_in_source("# class ")

        total = len(commented_defs) + len(commented_classes)
        result = genai.judge(
            question="Is there excessive commented-out code?",
            context=f"Commented-out defs: {len(commented_defs)}\nCommented-out classes: {len(commented_classes)}\n"
            f"Total: {total}\n\nSamples:\n" + "\n".join((commented_defs + commented_classes)[:15]),
            criteria="Commented-out function/class definitions indicate dead code. "
            "<5 is clean, 5-15 is acceptable, >15 needs cleanup. Score accordingly.",
        )
        assert result["score"] >= 3, f"Dead code issues: {result['reasoning']}"
