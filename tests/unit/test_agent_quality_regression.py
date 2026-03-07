"""
Agent quality regression tests.

Extracted from obsolete Phase 4/5 test files (Issue #403).
These tests validate ongoing agent quality properties that remain
relevant regardless of model optimization or prompt simplification decisions.

Date: 2026-03-08
GitHub Issue: #403
"""

import pytest
import yaml
from pathlib import Path


# Resolve agents directory relative to test file location
AGENTS_DIR = Path(__file__).parent.parent.parent / "plugins" / "autonomous-dev" / "agents"


class TestResearcherQuality:
    """Regression tests for researcher agent quality properties."""

    def test_researcher_still_has_web_search_capability(self):
        """Researcher agent must retain WebSearch and WebFetch tool access.

        These tools are essential for the researcher's core function.
        Any model or prompt change must preserve them.
        """
        researcher_file = AGENTS_DIR / "researcher.md"
        assert researcher_file.exists(), "researcher.md agent file should exist"

        content = researcher_file.read_text()
        frontmatter = content.split("---")[1].strip()
        config = yaml.safe_load(frontmatter)

        assert "tools" in config, "Researcher should have tools defined"
        tools = config["tools"]

        assert "WebSearch" in tools, "Researcher should have WebSearch capability"
        assert "WebFetch" in tools, "Researcher should have WebFetch capability"

    def test_researcher_prompt_maintains_quality_standards(self):
        """Researcher prompt must enforce quality standards.

        Checks that the prompt includes guidance on best practices,
        security considerations, and authoritative sources. Also
        verifies prompt is substantial enough for quality guidance.
        """
        researcher_file = AGENTS_DIR / "researcher.md"
        content = researcher_file.read_text()

        # Extract prompt body (after frontmatter)
        prompt = content.split("---", 2)[2]

        assert "best practices" in prompt.lower() or "best practice" in prompt.lower(), \
            "Researcher should research best practices"

        assert "security" in prompt.lower(), \
            "Researcher should consider security"

        assert "authoritative" in prompt.lower() or "official" in prompt.lower(), \
            "Researcher should prioritize authoritative sources"

        # Prompt should be substantial enough for quality guidance
        prompt_lines = [line for line in prompt.split("\n") if line.strip()]
        assert len(prompt_lines) >= 30, \
            f"Researcher prompt should have at least 30 lines of guidance, got {len(prompt_lines)}"


class TestPlannerQuality:
    """Regression tests for planner agent quality properties."""

    def test_planner_model_unchanged(self):
        """Planner must use opus model for strategic planning.

        Opus is required for the reasoning depth needed in
        architecture planning and design decisions.
        """
        planner_file = AGENTS_DIR / "planner.md"
        assert planner_file.exists(), "planner.md agent file should exist"

        content = planner_file.read_text()
        frontmatter = content.split("---")[1].strip()
        config = yaml.safe_load(frontmatter)

        assert config["model"] == "opus", \
            "Planner should use opus for strategic planning"


class TestAgentAlignmentRegression:
    """Regression tests for cross-agent alignment properties."""

    def test_agents_still_mention_project_md(self):
        """Both researcher and planner must reference PROJECT.md.

        PROJECT.md alignment is a core requirement for all agents
        involved in the planning pipeline.
        """
        researcher_file = AGENTS_DIR / "researcher.md"
        planner_file = AGENTS_DIR / "planner.md"

        researcher_content = researcher_file.read_text()
        planner_content = planner_file.read_text()

        assert "PROJECT.md" in researcher_content or "project.md" in researcher_content.lower(), \
            "Researcher should reference PROJECT.md for alignment"

        assert "PROJECT.md" in planner_content or "project.md" in planner_content.lower(), \
            "Planner should reference PROJECT.md for alignment"

    def test_agents_maintain_security_focus(self):
        """Both researcher and planner must emphasize security.

        Security-first approach is a non-negotiable quality property.
        """
        researcher_file = AGENTS_DIR / "researcher.md"
        planner_file = AGENTS_DIR / "planner.md"

        researcher_content = researcher_file.read_text()
        planner_content = planner_file.read_text()

        assert "security" in researcher_content.lower(), \
            "Researcher should consider security"

        assert "security" in planner_content.lower(), \
            "Planner should consider security"
