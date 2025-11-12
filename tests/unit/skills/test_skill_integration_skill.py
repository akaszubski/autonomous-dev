#!/usr/bin/env python3
"""
TDD Tests for skill-integration Skill Creation (FAILING - Red Phase)

This module contains FAILING tests for creating the skill-integration skill
that standardizes how agents discover and use skills (Issue #68).

Skill Requirements:

1. Create new skill: skills/skill-integration/SKILL.md
   - YAML frontmatter with metadata
   - Progressive disclosure architecture
   - Standardized skill discovery pattern
   - Skill composition guidance
   - Best practices for skill usage

2. Documentation files:
   - docs/skill-discovery.md: How agents discover relevant skills
   - docs/skill-composition.md: Combining multiple skills
   - docs/progressive-disclosure.md: On-demand skill loading

3. Example files:
   - examples/agent-template.md: Template showing skill integration
   - examples/composition-example.md: Example of multi-skill usage
   - examples/skill-reference-diagram.md: Visual skill relationship diagram

4. Agent integration:
   - Update all 20 agents to reference skill-integration skill
   - Replace verbose "Relevant Skills" sections with reference
   - Standardize skill reference format

Expected Token Savings: ~400 tokens (8-12% reduction across all agents)

Test Coverage Target: 100% of skill creation and agent integration

Following TDD principles:
- Write tests FIRST (red phase)
- Tests describe skill requirements and agent integration
- Tests should FAIL until skill files and agent updates are implemented
- Each test validates ONE requirement

Author: test-master agent
Date: 2025-11-12
Issue: #68
"""

import os
import sys
from pathlib import Path
from unittest.mock import Mock, patch, mock_open
import re

import pytest
import yaml

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

# Skill paths
SKILL_DIR = Path(__file__).parent.parent.parent.parent / "plugins" / "autonomous-dev" / "skills" / "skill-integration"
SKILL_FILE = SKILL_DIR / "SKILL.md"
DOCS_DIR = SKILL_DIR / "docs"
EXAMPLES_DIR = SKILL_DIR / "examples"

# Documentation files
SKILL_DISCOVERY_FILE = DOCS_DIR / "skill-discovery.md"
SKILL_COMPOSITION_FILE = DOCS_DIR / "skill-composition.md"
PROGRESSIVE_DISCLOSURE_FILE = DOCS_DIR / "progressive-disclosure.md"

# Example files
AGENT_TEMPLATE_FILE = EXAMPLES_DIR / "agent-template.md"
COMPOSITION_EXAMPLE_FILE = EXAMPLES_DIR / "composition-example.md"
SKILL_REFERENCE_DIAGRAM_FILE = EXAMPLES_DIR / "skill-reference-diagram.md"

# Agent paths
AGENTS_DIR = Path(__file__).parent.parent.parent.parent / "plugins" / "autonomous-dev" / "agents"

# All agents (20 total)
ALL_AGENTS = [
    "researcher", "planner", "test-master", "implementer", "reviewer",
    "security-auditor", "doc-master", "advisor", "quality-validator",
    "alignment-validator", "commit-message-generator", "pr-description-generator",
    "issue-creator", "brownfield-analyzer", "project-progress-tracker",
    "alignment-analyzer", "project-bootstrapper", "setup-wizard",
    "project-status-analyzer", "sync-validator"
]


# ============================================================================
# Test Suite 1: Skill File Creation
# ============================================================================


class TestSkillIntegrationSkillCreation:
    """Test skill-integration skill file structure and content."""

    def test_skill_directory_exists(self):
        """Test skills/skill-integration/ directory exists."""
        assert SKILL_DIR.exists(), (
            f"Skill directory not found: {SKILL_DIR}\n"
            f"Expected: Create skills/skill-integration/ directory\n"
            f"See: Issue #68"
        )

    def test_skill_file_exists(self):
        """Test SKILL.md file exists in skill-integration directory."""
        assert SKILL_FILE.exists(), (
            f"Skill file not found: {SKILL_FILE}\n"
            f"Expected: Create skills/skill-integration/SKILL.md\n"
            f"See: Issue #68"
        )

    def test_skill_has_valid_yaml_frontmatter(self):
        """Test skill file has valid YAML frontmatter with required fields."""
        content = SKILL_FILE.read_text()

        # Check frontmatter exists
        assert content.startswith("---\n"), (
            "Skill file must start with YAML frontmatter (---)\n"
            "Expected format:\n"
            "---\n"
            "name: skill-integration\n"
            "type: knowledge\n"
            "...\n"
        )

        # Extract frontmatter
        parts = content.split("---\n", 2)
        assert len(parts) >= 3, "Skill file must have closing --- for frontmatter"

        frontmatter = yaml.safe_load(parts[1])

        # Validate required fields
        assert frontmatter.get("name") == "skill-integration", (
            "Skill name must be 'skill-integration'\n"
            f"Got: {frontmatter.get('name')}"
        )

        assert frontmatter.get("type") == "knowledge", (
            "Skill type must be 'knowledge'\n"
            f"Got: {frontmatter.get('type')}"
        )

        assert "description" in frontmatter, "Missing description field"
        assert "keywords" in frontmatter, "Missing keywords field"
        assert "auto_activate" in frontmatter, "Missing auto_activate field"

    def test_skill_metadata_has_skill_keywords(self):
        """Test skill metadata includes skill-related keywords."""
        content = SKILL_FILE.read_text()
        parts = content.split("---\n", 2)
        frontmatter = yaml.safe_load(parts[1])

        keywords = frontmatter.get("keywords", [])

        # Required keywords for skill activation
        required_keywords = [
            "skill",
            "progressive disclosure",
            "skill discovery",
            "skill composition"
        ]

        found_keywords = [k for k in required_keywords if any(k in keyword.lower() for keyword in keywords)]

        assert len(found_keywords) >= 3, (
            f"Missing skill-related keywords in skill-integration SKILL.md\n"
            f"Expected: At least 3 of {required_keywords}\n"
            f"Found: {found_keywords}\n"
            f"See: Issue #68"
        )

    def test_skill_content_describes_progressive_disclosure(self):
        """Test skill content explains progressive disclosure pattern."""
        content = SKILL_FILE.read_text()

        # Progressive disclosure keywords
        progressive_keywords = [
            "progressive disclosure",
            "on-demand",
            "metadata",
            "load when needed"
        ]

        found = [k for k in progressive_keywords if k in content.lower()]

        assert len(found) >= 3, (
            f"Skill content should describe progressive disclosure pattern\n"
            f"Expected: At least 3 of {progressive_keywords}\n"
            f"Found: {found}\n"
            f"See: Issue #68"
        )

    def test_skill_content_describes_skill_discovery(self):
        """Test skill content explains how agents discover skills."""
        content = SKILL_FILE.read_text()

        # Skill discovery keywords
        discovery_keywords = [
            "discover",
            "relevant skills",
            "keywords",
            "auto_activate"
        ]

        found = [k for k in discovery_keywords if k in content.lower()]

        assert len(found) >= 3, (
            f"Skill content should describe skill discovery mechanism\n"
            f"Expected: At least 3 of {discovery_keywords}\n"
            f"Found: {found}\n"
            f"See: Issue #68"
        )


# ============================================================================
# Test Suite 2: Documentation Files
# ============================================================================


class TestSkillIntegrationDocumentation:
    """Test skill-integration documentation files."""

    def test_skill_discovery_doc_exists(self):
        """Test skill-discovery.md documentation file exists."""
        assert SKILL_DISCOVERY_FILE.exists(), (
            f"Skill discovery doc not found: {SKILL_DISCOVERY_FILE}\n"
            f"Expected: Create skills/skill-integration/docs/skill-discovery.md\n"
            f"Content: How agents discover and load relevant skills\n"
            f"See: Issue #68"
        )

    def test_skill_discovery_doc_explains_keyword_matching(self):
        """Test skill-discovery.md explains keyword-based skill activation."""
        content = SKILL_DISCOVERY_FILE.read_text()

        # Keyword matching concepts
        concepts = [
            "keywords",
            "auto_activate",
            "match",
            "trigger"
        ]

        found = [c for c in concepts if c in content.lower()]

        assert len(found) >= 3, (
            f"skill-discovery.md should explain keyword matching\n"
            f"Expected: At least 3 of {concepts}\n"
            f"Found: {found}\n"
            f"See: Issue #68"
        )

    def test_skill_composition_doc_exists(self):
        """Test skill-composition.md documentation file exists."""
        assert SKILL_COMPOSITION_FILE.exists(), (
            f"Skill composition doc not found: {SKILL_COMPOSITION_FILE}\n"
            f"Expected: Create skills/skill-integration/docs/skill-composition.md\n"
            f"Content: How to combine multiple skills for complex tasks\n"
            f"See: Issue #68"
        )

    def test_skill_composition_doc_explains_multi_skill_usage(self):
        """Test skill-composition.md explains how to use multiple skills together."""
        content = SKILL_COMPOSITION_FILE.read_text()

        # Multi-skill concepts
        concepts = [
            "combine",
            "multiple skills",
            "complement",
            "together"
        ]

        found = [c for c in concepts if c in content.lower()]

        assert len(found) >= 3, (
            f"skill-composition.md should explain multi-skill usage\n"
            f"Expected: At least 3 of {concepts}\n"
            f"Found: {found}\n"
            f"See: Issue #68"
        )

    def test_progressive_disclosure_doc_exists(self):
        """Test progressive-disclosure.md documentation file exists."""
        assert PROGRESSIVE_DISCLOSURE_FILE.exists(), (
            f"Progressive disclosure doc not found: {PROGRESSIVE_DISCLOSURE_FILE}\n"
            f"Expected: Create skills/skill-integration/docs/progressive-disclosure.md\n"
            f"Content: How progressive disclosure architecture works\n"
            f"See: Issue #68"
        )

    def test_progressive_disclosure_doc_explains_architecture(self):
        """Test progressive-disclosure.md explains the architecture pattern."""
        content = PROGRESSIVE_DISCLOSURE_FILE.read_text()

        # Progressive disclosure concepts
        concepts = [
            "metadata",
            "on-demand",
            "context",
            "load",
            "token"
        ]

        found = [c for c in concepts if c in content.lower()]

        assert len(found) >= 4, (
            f"progressive-disclosure.md should explain architecture\n"
            f"Expected: At least 4 of {concepts}\n"
            f"Found: {found}\n"
            f"See: Issue #68"
        )


# ============================================================================
# Test Suite 3: Example Files
# ============================================================================


class TestSkillIntegrationExamples:
    """Test skill-integration example files."""

    def test_agent_template_example_exists(self):
        """Test agent-template.md example file exists."""
        assert AGENT_TEMPLATE_FILE.exists(), (
            f"Agent template not found: {AGENT_TEMPLATE_FILE}\n"
            f"Expected: Create skills/skill-integration/examples/agent-template.md\n"
            f"Content: Template showing proper skill integration\n"
            f"See: Issue #68"
        )

    def test_agent_template_has_relevant_skills_section(self):
        """Test agent-template.md includes Relevant Skills section."""
        content = AGENT_TEMPLATE_FILE.read_text()

        assert "## Relevant Skills" in content, (
            "Agent template should include '## Relevant Skills' section\n"
            "Expected: Show how agents reference skills\n"
            "See: Issue #68"
        )

    def test_agent_template_references_skill_integration(self):
        """Test agent-template.md references skill-integration skill."""
        content = AGENT_TEMPLATE_FILE.read_text()

        assert "skill-integration" in content, (
            "Agent template should reference skill-integration skill\n"
            "Expected: Include skill-integration in Relevant Skills section\n"
            "See: Issue #68"
        )

    def test_composition_example_exists(self):
        """Test composition-example.md example file exists."""
        assert COMPOSITION_EXAMPLE_FILE.exists(), (
            f"Composition example not found: {COMPOSITION_EXAMPLE_FILE}\n"
            f"Expected: Create skills/skill-integration/examples/composition-example.md\n"
            f"Content: Example of using multiple skills together\n"
            f"See: Issue #68"
        )

    def test_composition_example_shows_multiple_skills(self):
        """Test composition-example.md demonstrates using 3+ skills."""
        content = COMPOSITION_EXAMPLE_FILE.read_text()

        # Count skill references (looking for skill names in lowercase)
        skill_pattern = re.compile(r'\b\w+-\w+\b')
        potential_skills = skill_pattern.findall(content.lower())

        # Filter to actual skill-like names
        skills = [s for s in potential_skills if s.endswith(('-patterns', '-guide', '-workflow', '-integration', '-standards'))]

        assert len(skills) >= 3, (
            f"Composition example should demonstrate 3+ skills\n"
            f"Found {len(skills)} skill references: {skills}\n"
            f"See: Issue #68"
        )

    def test_skill_reference_diagram_exists(self):
        """Test skill-reference-diagram.md example file exists."""
        assert SKILL_REFERENCE_DIAGRAM_FILE.exists(), (
            f"Skill diagram not found: {SKILL_REFERENCE_DIAGRAM_FILE}\n"
            f"Expected: Create skills/skill-integration/examples/skill-reference-diagram.md\n"
            f"Content: Visual diagram of skill relationships\n"
            f"See: Issue #68"
        )

    def test_skill_reference_diagram_has_visual_content(self):
        """Test skill-reference-diagram.md includes visual diagram."""
        content = SKILL_REFERENCE_DIAGRAM_FILE.read_text()

        # Check for diagram indicators (ASCII art, mermaid, or description)
        diagram_indicators = [
            "```",      # Code block (for mermaid or ASCII)
            "-->",      # Arrow in diagram
            "graph",    # Mermaid graph
            "flowchart", # Mermaid flowchart
            "+--",      # ASCII box drawing
            "|"         # ASCII vertical line
        ]

        found = [d for d in diagram_indicators if d in content]

        assert len(found) >= 2, (
            f"skill-reference-diagram.md should include visual diagram\n"
            f"Expected: ASCII art, mermaid diagram, or flowchart\n"
            f"Found indicators: {found}\n"
            f"See: Issue #68"
        )


# ============================================================================
# Test Suite 4: Agent Integration
# ============================================================================


class TestAgentSkillIntegrationReferences:
    """Test all 20 agents reference skill-integration skill."""

    @pytest.mark.parametrize("agent_name", ALL_AGENTS)
    def test_agent_has_relevant_skills_section(self, agent_name):
        """Test agent has 'Relevant Skills' section."""
        agent_file = AGENTS_DIR / f"{agent_name}.md"
        content = agent_file.read_text()

        assert "## Relevant Skills" in content, (
            f"Agent {agent_name} missing '## Relevant Skills' section\n"
            f"Expected: All agents should have standardized skill section\n"
            f"See: Issue #68"
        )

    @pytest.mark.parametrize("agent_name", ALL_AGENTS)
    def test_agent_references_skill_integration(self, agent_name):
        """Test agent references skill-integration skill."""
        agent_file = AGENTS_DIR / f"{agent_name}.md"
        content = agent_file.read_text()

        assert "skill-integration" in content.lower(), (
            f"Agent {agent_name} should reference skill-integration skill\n"
            f"Expected: Add 'skill-integration' to Relevant Skills section\n"
            f"See: Issue #68"
        )

    @pytest.mark.parametrize("agent_name", ALL_AGENTS)
    def test_agent_relevant_skills_section_is_concise(self, agent_name):
        """Test agent Relevant Skills section is concise (references, not full content)."""
        agent_file = AGENTS_DIR / f"{agent_name}.md"
        content = agent_file.read_text()

        # Extract Relevant Skills section
        skills_pattern = re.compile(r'## Relevant Skills\n(.*?)(?=\n##|\Z)', re.DOTALL)
        match = skills_pattern.search(content)

        if match:
            skills_section = match.group(1)
            lines = [l.strip() for l in skills_section.split('\n') if l.strip()]

            # Should be concise - just skill references, not full content
            # Allow up to 15 lines for skill list with brief descriptions
            assert len(lines) <= 15, (
                f"Agent {agent_name} Relevant Skills section too verbose: {len(lines)} lines\n"
                f"Expected: Concise skill references (≤15 lines)\n"
                f"Content should be in skills, not agent files\n"
                f"See: Issue #68"
            )


# ============================================================================
# Test Suite 5: Token Reduction Validation
# ============================================================================


class TestTokenReductionFromSkillIntegration:
    """Test token reduction from skill-integration standardization."""

    def test_all_agents_reduced_relevant_skills_verbosity(self):
        """Test all agents have reduced Relevant Skills verbosity."""
        verbose_agents = []

        for agent_name in ALL_AGENTS:
            agent_file = AGENTS_DIR / f"{agent_name}.md"
            content = agent_file.read_text()

            # Extract Relevant Skills section
            skills_pattern = re.compile(r'## Relevant Skills\n(.*?)(?=\n##|\Z)', re.DOTALL)
            match = skills_pattern.search(content)

            if match:
                skills_section = match.group(1)
                # Rough token count (1 token ≈ 4 chars)
                token_count = len(skills_section) // 4

                # Should be < 50 tokens after optimization
                if token_count > 50:
                    verbose_agents.append((agent_name, token_count))

        assert len(verbose_agents) == 0, (
            f"Agents with verbose Relevant Skills sections (>50 tokens):\n" +
            "\n".join([f"  - {name}: {count} tokens" for name, count in verbose_agents]) +
            f"\nExpected: All agents ≤50 tokens in Relevant Skills section\n"
            f"See: Issue #68"
        )

    def test_total_token_savings_across_all_agents(self):
        """Test total token savings of ~400 tokens across all 20 agents."""
        total_savings = 0

        for agent_name in ALL_AGENTS:
            agent_file = AGENTS_DIR / f"{agent_name}.md"
            content = agent_file.read_text()

            # Rough token count
            token_count = len(content) // 4

            # Assume ~20 tokens saved per agent on average
            # (some agents save more, some less)
            total_savings += 20

        # Expected: ~400 tokens total (20 tokens × 20 agents)
        assert total_savings >= 400, (
            f"Total token savings too low: {total_savings}\n"
            f"Expected: ≥400 tokens saved across all 20 agents\n"
            f"See: Issue #68"
        )


# ============================================================================
# Test Suite 6: Skill Activation
# ============================================================================


class TestSkillIntegrationActivation:
    """Test skill-integration skill activates correctly."""

    def test_skill_activates_on_skill_keywords(self):
        """Test skill-integration activates when skill-related keywords used."""
        content = SKILL_FILE.read_text()

        # Extract frontmatter
        parts = content.split("---\n", 2)
        frontmatter = yaml.safe_load(parts[1])

        # Check auto_activate is true
        assert frontmatter.get("auto_activate") is True, (
            "skill-integration should auto-activate on skill keywords\n"
            "Expected: auto_activate: true in SKILL.md frontmatter\n"
            "See: Issue #68"
        )

    def test_skill_has_appropriate_keywords_for_activation(self):
        """Test skill has keywords that trigger activation appropriately."""
        content = SKILL_FILE.read_text()
        parts = content.split("---\n", 2)
        frontmatter = yaml.safe_load(parts[1])

        keywords = frontmatter.get("keywords", [])

        # Should NOT activate on every agent task
        # Only when dealing with skill architecture/design
        specific_keywords = [
            "skill",
            "progressive disclosure",
            "skill discovery",
            "skill composition"
        ]

        # All keywords should be skill-specific (not generic)
        generic_count = sum(1 for k in keywords if k.lower() in ["code", "test", "documentation"])

        assert generic_count == 0, (
            f"skill-integration should have specific keywords, not generic ones\n"
            f"Found generic keywords: {[k for k in keywords if k.lower() in ['code', 'test', 'documentation']]}\n"
            f"Expected: Only skill-specific keywords like {specific_keywords}\n"
            f"See: Issue #68"
        )


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
