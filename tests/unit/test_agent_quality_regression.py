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
        """Researcher agent must retain a search AND a fetch capability.

        The CAPABILITY is what this test protects, not the tool names. The
        carrier changed from the native WebSearch/WebFetch pair (which needs
        Anthropic's hosted service and is a no-op in this environment) to the
        self-hosted searxng pair. Any model or prompt change must preserve
        both halves — search alone cannot read a source document.
        """
        researcher_file = AGENTS_DIR / "researcher.md"
        assert researcher_file.exists(), "researcher.md agent file should exist"

        content = researcher_file.read_text()
        frontmatter = content.split("---")[1].strip()
        config = yaml.safe_load(frontmatter)

        assert "tools" in config, "Researcher should have tools defined"
        tools = config["tools"]

        assert "mcp__searxng__search" in tools, (
            "Researcher should have a web SEARCH capability "
            "(mcp__searxng__search)"
        )
        assert "mcp__searxng__fetch" in tools, (
            "Researcher should have a web FETCH capability "
            "(mcp__searxng__fetch) — search alone cannot read a source"
        )

    def test_researcher_declares_no_hosted_web_tools(self):
        """The withdrawn native pair must not creep back in.

        A tools: entry is a BLOCKING dependency for a subagent: it is the
        only route to the capability. Naming a tool that is a no-op here
        grants the researcher a capability it provably does not have.
        """
        content = (AGENTS_DIR / "researcher.md").read_text()
        config = yaml.safe_load(content.split("---")[1].strip())
        tools = set(config["tools"])

        assert not (tools & {"WebSearch", "WebFetch"}), (
            f"researcher.md re-declared hosted web tools: "
            f"{sorted(tools & {'WebSearch', 'WebFetch'})}"
        )

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
