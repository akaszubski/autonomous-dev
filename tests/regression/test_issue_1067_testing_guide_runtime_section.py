"""Regression tests for Issue #1067 — Runtime Integration Testing section in testing-guide skill."""

from pathlib import Path
import pytest

SKILL_PATH = Path(__file__).resolve().parents[2] / "plugins" / "autonomous-dev" / "skills" / "testing-guide" / "SKILL.md"


@pytest.fixture(scope="module")
def content() -> str:
    return SKILL_PATH.read_text()


class TestRuntimeSectionExists:
    def test_section_heading_present(self, content):
        assert "Runtime Integration Testing Patterns" in content

    def test_section_mentions_monkeypatch(self, content):
        assert "monkeypatch" in content

    def test_section_mentions_subprocess_kwargs(self, content):
        # The section should explicitly teach kwargs assertion
        assert "kwargs" in content
        assert "subprocess" in content

    def test_section_mentions_cwd(self, content):
        assert "cwd" in content.lower()

    def test_section_references_issue_1064(self, content):
        assert "1064" in content

    def test_section_cites_reference_example(self, content):
        # Either the test function name or the file path
        assert ("test_call_claude_p_judge_passes_cwd_to_avoid_project_context" in content
                or "test_extract_and_label_intent_corpus.py" in content)

    def test_section_includes_anti_pattern(self, content):
        # The anti-pattern subsection
        assert "Anti-pattern" in content or "anti-pattern" in content
