"""GenAI UAT: Documentation completeness.

Validates that documentation accurately reflects codebase state.
Universal test — works in any repo with CLAUDE.md.
"""

import pytest

from .conftest import PROJECT_ROOT

pytestmark = [pytest.mark.genai]


def _count_pattern_in_source(pattern: str, extensions: tuple = ("*.py",)) -> list[str]:
    """Find pattern occurrences in source files."""
    results = []
    for ext in extensions:
        for f in PROJECT_ROOT.rglob(ext):
            if any(x in str(f) for x in ["archived", "__pycache__", ".genai_cache", "venv", "node_modules"]):
                continue
            for i, line in enumerate(f.read_text(errors="ignore").splitlines(), 1):
                if pattern in line and not line.strip().startswith("#"):
                    results.append(f"{f.relative_to(PROJECT_ROOT)}:{i}: {line.strip()}")
    return results


class TestDocCompleteness:
    def test_claude_md_exists_and_has_content(self, genai):
        """CLAUDE.md should exist and contain meaningful content."""
        claude_md_path = PROJECT_ROOT / "CLAUDE.md"
        if not claude_md_path.exists():
            pytest.fail("CLAUDE.md not found — required for autonomous-dev projects")

        claude_md = claude_md_path.read_text()
        result = genai.judge(
            question="Is this CLAUDE.md well-structured and useful?",
            context=f"CLAUDE.md ({len(claude_md)} chars):\n{claude_md[:3000]}",
            criteria="A good CLAUDE.md should have: project overview, key commands or workflows, "
            "file organization notes, and critical rules. Score 10 = comprehensive, "
            "5 = adequate, 0 = empty/boilerplate.",
        )
        assert result["score"] >= 5, f"CLAUDE.md quality: {result['reasoning']}"

    def test_readme_matches_claude_md(self, genai):
        """README and CLAUDE.md should be broadly consistent."""
        readme_path = PROJECT_ROOT / "README.md"
        claude_md_path = PROJECT_ROOT / "CLAUDE.md"
        if not readme_path.exists():
            pytest.skip("No README.md found")
        if not claude_md_path.exists():
            pytest.skip("No CLAUDE.md found")

        readme = readme_path.read_text()[:3000]
        claude_md = claude_md_path.read_text()[:3000]

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
