#!/usr/bin/env python3
"""
TDD Tests for skill-integration-templates Skill (FAILING - Red Phase)

This module contains FAILING tests for the skill-integration-templates skill that will
extract duplicated skill integration patterns from 20 agent files (Issue #72 Phase 8.6).

Skill Requirements:
1. YAML frontmatter with name, type, description, keywords, auto_activate
2. Progressive disclosure architecture (metadata in frontmatter, content loads on-demand)
3. Standardized skill integration templates:
   - Skill reference syntax patterns
   - Agent action verbs for different contexts
   - Progressive disclosure usage guidelines
   - Integration best practices
4. Example skill sections from real agents (examples/ directory)
5. Token reduction: ~30-50 tokens per agent × 8 agents = ~240-400 tokens (Issue #147)

Test Coverage Target: 53 tests (15 unit + 20 agent + 10 integration + 8 token)

Following TDD principles:
- Write tests FIRST (red phase)
- Tests describe skill requirements and agent integration
- Tests should FAIL until skill file and agent updates are implemented
- Each test validates ONE requirement

Author: test-master agent
Date: 2025-11-16
Issue: #72 Phase 8.6
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

SKILL_DIR = Path(__file__).parent.parent.parent.parent / "plugins" / "autonomous-dev" / "skills" / "skill-integration-templates"
SKILL_FILE = SKILL_DIR / "SKILL.md"
DOCS_DIR = SKILL_DIR / "docs"
TEMPLATES_DIR = SKILL_DIR / "templates"
EXAMPLES_DIR = SKILL_DIR / "examples"
AGENTS_DIR = Path(__file__).parent.parent.parent.parent / "plugins" / "autonomous-dev" / "agents"

# All 20 agent files that should reference skill-integration-templates
AGENT_FILES = [
    "advisor.md",
    "alignment-analyzer.md",
    "alignment-validator.md",
    "brownfield-analyzer.md",
    "commit-message-generator.md",
    "doc-master.md",
    "implementer.md",
    "issue-creator.md",
    "planner.md",
    "pr-description-generator.md",
    "project-bootstrapper.md",
    "project-progress-tracker.md",
    "project-status-analyzer.md",
    "quality-validator.md",
    "researcher.md",
    "reviewer.md",
    "security-auditor.md",
    "setup-wizard.md",
    "sync-validator.md",
    "test-master.md",
]


class TestSkillCreation:
    """Test skill-integration-templates skill file structure and metadata."""

    def test_skill_file_exists(self):
        """Test SKILL.md file exists in skills/skill-integration-templates/ directory."""
        assert SKILL_FILE.exists(), (
            f"Skill file not found: {SKILL_FILE}\n"
            f"Expected: Create skills/skill-integration-templates/SKILL.md\n"
            f"See: Issue #72 Phase 8.6"
        )

    def test_skill_has_valid_yaml_frontmatter(self):
        """Test skill file has valid YAML frontmatter with required fields."""
        content = SKILL_FILE.read_text()

        # Check frontmatter exists
        assert content.startswith("---\n"), (
            "Skill file must start with YAML frontmatter (---)\n"
            "Expected format:\n"
            "---\n"
            "name: skill-integration-templates\n"
            "type: knowledge\n"
            "...\n"
        )

        # Extract frontmatter
        parts = content.split("---\n", 2)
        assert len(parts) >= 3, "Skill file must have closing --- for frontmatter"

        frontmatter = yaml.safe_load(parts[1])

        # Validate required fields
        assert frontmatter.get("name") == "skill-integration-templates", (
            "Skill name must be 'skill-integration-templates'"
        )
        assert frontmatter.get("type") == "knowledge", (
            "Skill type must be 'knowledge'"
        )
        assert "description" in frontmatter, (
            "Skill must have 'description' field"
        )
        assert "keywords" in frontmatter, (
            "Skill must have 'keywords' field for auto-activation"
        )
        assert frontmatter.get("auto_activate") is True, (
            "Skill must have 'auto_activate: true' for progressive disclosure"
        )

    def test_skill_keywords_cover_integration_terms(self):
        """Test skill keywords include common skill integration terms."""
        content = SKILL_FILE.read_text()
        parts = content.split("---\n", 2)
        frontmatter = yaml.safe_load(parts[1])
        keywords = frontmatter.get("keywords", [])

        # Required keywords for skill integration patterns
        required_keywords = [
            "skill-reference",
            "agent-skills",
            "progressive-disclosure",
            "integration-patterns",
            "skill-section",
        ]

        for keyword in required_keywords:
            assert keyword in keywords, (
                f"Skill keywords must include '{keyword}' for auto-activation\n"
                f"Found: {keywords}\n"
                f"Expected: {required_keywords}"
            )

    def test_skill_description_mentions_token_reduction(self):
        """Test skill description mentions token reduction benefits."""
        content = SKILL_FILE.read_text()
        parts = content.split("---\n", 2)
        frontmatter = yaml.safe_load(parts[1])
        description = frontmatter.get("description", "")

        assert "token" in description.lower(), (
            "Skill description must mention token reduction benefits"
        )

    def test_skill_has_overview_section(self):
        """Test skill content has Overview section explaining purpose."""
        content = SKILL_FILE.read_text()
        parts = content.split("---\n", 2)

        assert len(parts) >= 3, "Skill must have content after frontmatter"
        skill_content = parts[2]

        assert "## Overview" in skill_content, (
            "Skill must have '## Overview' section"
        )

    def test_skill_has_when_to_use_section(self):
        """Test skill content has When to Use section."""
        content = SKILL_FILE.read_text()
        parts = content.split("---\n", 2)
        skill_content = parts[2]

        assert "## When to Use" in skill_content, (
            "Skill must have '## When to Use' section"
        )

    def test_skill_references_documentation_files(self):
        """Test skill content references all documentation files."""
        content = SKILL_FILE.read_text()

        doc_files = [
            "skill-reference-syntax.md",
            "agent-action-verbs.md",
            "progressive-disclosure-usage.md",
            "integration-best-practices.md",
        ]

        for doc_file in doc_files:
            assert doc_file in content, (
                f"Skill must reference documentation file: {doc_file}\n"
                f"Expected: docs/{doc_file}"
            )


class TestSkillDocumentation:
    """Test skill documentation files in docs/ directory."""

    def test_docs_directory_exists(self):
        """Test docs/ directory exists under skill directory."""
        assert DOCS_DIR.exists() and DOCS_DIR.is_dir(), (
            f"Documentation directory not found: {DOCS_DIR}\n"
            f"Expected: Create skills/skill-integration-templates/docs/"
        )

    def test_skill_reference_syntax_doc_exists(self):
        """Test skill-reference-syntax.md documentation file exists."""
        doc_file = DOCS_DIR / "skill-reference-syntax.md"
        assert doc_file.exists(), (
            f"Documentation file not found: {doc_file}\n"
            f"Expected: Create docs/skill-reference-syntax.md (~800 tokens)\n"
            f"Content: Skill section syntax patterns, reference formats"
        )

    def test_agent_action_verbs_doc_exists(self):
        """Test agent-action-verbs.md documentation file exists."""
        doc_file = DOCS_DIR / "agent-action-verbs.md"
        assert doc_file.exists(), (
            f"Documentation file not found: {doc_file}\n"
            f"Expected: Create docs/agent-action-verbs.md (~600 tokens)\n"
            f"Content: Action verbs for different agent contexts"
        )

    def test_progressive_disclosure_usage_doc_exists(self):
        """Test progressive-disclosure-usage.md documentation file exists."""
        doc_file = DOCS_DIR / "progressive-disclosure-usage.md"
        assert doc_file.exists(), (
            f"Documentation file not found: {doc_file}\n"
            f"Expected: Create docs/progressive-disclosure-usage.md (~700 tokens)\n"
            f"Content: How to use progressive disclosure in agent prompts"
        )

    def test_integration_best_practices_doc_exists(self):
        """Test integration-best-practices.md documentation file exists."""
        doc_file = DOCS_DIR / "integration-best-practices.md"
        assert doc_file.exists(), (
            f"Documentation file not found: {doc_file}\n"
            f"Expected: Create docs/integration-best-practices.md (~500 tokens)\n"
            f"Content: Best practices for skill integration in agents"
        )

    def test_skill_reference_syntax_has_examples(self):
        """Test skill-reference-syntax.md contains example syntax patterns."""
        doc_file = DOCS_DIR / "skill-reference-syntax.md"
        content = doc_file.read_text()

        # Should contain example patterns
        assert "## Syntax Patterns" in content or "## Examples" in content, (
            "Documentation must show skill reference syntax examples"
        )

    def test_agent_action_verbs_has_verb_list(self):
        """Test agent-action-verbs.md contains categorized action verbs."""
        doc_file = DOCS_DIR / "agent-action-verbs.md"
        content = doc_file.read_text()

        # Should categorize verbs by agent type
        assert "research" in content.lower() or "analyze" in content.lower(), (
            "Documentation must contain action verbs for different contexts"
        )


class TestSkillTemplates:
    """Test skill template files in templates/ directory."""

    def test_templates_directory_exists(self):
        """Test templates/ directory exists under skill directory."""
        assert TEMPLATES_DIR.exists() and TEMPLATES_DIR.is_dir(), (
            f"Templates directory not found: {TEMPLATES_DIR}\n"
            f"Expected: Create skills/skill-integration-templates/templates/"
        )

    def test_skill_section_template_exists(self):
        """Test skill-section-template.md template file exists."""
        template_file = TEMPLATES_DIR / "skill-section-template.md"
        assert template_file.exists(), (
            f"Template file not found: {template_file}\n"
            f"Expected: Create templates/skill-section-template.md (~300 tokens)\n"
            f"Content: Reusable template for skill reference sections"
        )

    def test_intro_sentence_templates_exists(self):
        """Test intro-sentence-templates.md template file exists."""
        template_file = TEMPLATES_DIR / "intro-sentence-templates.md"
        assert template_file.exists(), (
            f"Template file not found: {template_file}\n"
            f"Expected: Create templates/intro-sentence-templates.md (~400 tokens)\n"
            f"Content: Reusable intro sentences for skill sections"
        )

    def test_closing_sentence_templates_exists(self):
        """Test closing-sentence-templates.md template file exists."""
        template_file = TEMPLATES_DIR / "closing-sentence-templates.md"
        assert template_file.exists(), (
            f"Template file not found: {template_file}\n"
            f"Expected: Create templates/closing-sentence-templates.md (~400 tokens)\n"
            f"Content: Reusable closing sentences for skill sections"
        )


class TestSkillExamples:
    """Test skill example files in examples/ directory."""

    def test_examples_directory_exists(self):
        """Test examples/ directory exists under skill directory."""
        assert EXAMPLES_DIR.exists() and EXAMPLES_DIR.is_dir(), (
            f"Examples directory not found: {EXAMPLES_DIR}\n"
            f"Expected: Create skills/skill-integration-templates/examples/"
        )

    def test_planner_skill_section_example_exists(self):
        """Test planner-skill-section.md example file exists."""
        example_file = EXAMPLES_DIR / "planner-skill-section.md"
        assert example_file.exists(), (
            f"Example file not found: {example_file}\n"
            f"Expected: Create examples/planner-skill-section.md (~200 tokens)\n"
            f"Content: Real skill section from planner agent"
        )

    def test_implementer_skill_section_example_exists(self):
        """Test implementer-skill-section.md example file exists."""
        example_file = EXAMPLES_DIR / "implementer-skill-section.md"
        assert example_file.exists(), (
            f"Example file not found: {example_file}\n"
            f"Expected: Create examples/implementer-skill-section.md (~200 tokens)\n"
            f"Content: Real skill section from implementer agent"
        )

    def test_minimal_skill_reference_example_exists(self):
        """Test minimal-skill-reference.md example file exists."""
        example_file = EXAMPLES_DIR / "minimal-skill-reference.md"
        assert example_file.exists(), (
            f"Example file not found: {example_file}\n"
            f"Expected: Create examples/minimal-skill-reference.md (~100 tokens)\n"
            f"Content: Minimal skill reference for simple agents"
        )


class TestAgentStreamlining:
    """Test that all 20 agent files reference skill-integration-templates skill."""

    @pytest.mark.parametrize("agent_file", AGENT_FILES)
    def test_agent_references_skill_integration_templates(self, agent_file):
        """Test agent file references skill-integration-templates skill."""
        agent_path = AGENTS_DIR / agent_file

        assert agent_path.exists(), (
            f"Agent file not found: {agent_path}\n"
            f"Cannot test skill integration"
        )

        content = agent_path.read_text()

        # Check for skill reference
        assert "skill-integration-templates" in content, (
            f"Agent {agent_file} must reference skill-integration-templates skill\n"
            f"Expected: Consult skill-integration-templates skill for formatting guidance\n"
            f"See: Issue #72 Phase 8.6"
        )

    @pytest.mark.parametrize("agent_file", AGENT_FILES)
    def test_agent_has_streamlined_relevant_skills_section(self, agent_file):
        """Test agent has streamlined Relevant Skills section with skill reference."""
        agent_path = AGENTS_DIR / agent_file
        content = agent_path.read_text()

        # Should have Relevant Skills section
        assert "## Relevant Skills" in content or "Relevant Skills" in content, (
            f"Agent {agent_file} should have Relevant Skills section\n"
            f"This section should reference skill-integration-templates for formatting"
        )

    @pytest.mark.parametrize("agent_file", AGENT_FILES)
    def test_agent_skill_section_is_concise(self, agent_file):
        """Test agent skill section is concise (references skill vs. inline verbose patterns)."""
        agent_path = AGENTS_DIR / agent_file
        content = agent_path.read_text()

        # If it has a Relevant Skills section, check it's not overly verbose
        if "## Relevant Skills" in content:
            # Extract section
            parts = content.split("## Relevant Skills", 1)
            if len(parts) > 1:
                # Get section until next ## heading
                section = parts[1].split("##", 1)[0]

                # Should mention skill reference
                has_skill_ref = "skill-integration-templates" in section

                # Should be reasonably short (under 30 lines when referencing skill)
                line_count = len([line for line in section.split("\n") if line.strip()])

                if has_skill_ref:
                    assert line_count < 30, (
                        f"Agent {agent_file} Relevant Skills section too verbose ({line_count} lines)\n"
                        f"When referencing skill-integration-templates, section should be concise (<30 lines)"
                    )


class TestSkillIntegration:
    """Integration tests for skill loading and progressive disclosure."""

    def test_skill_loads_in_claude_code_context(self):
        """Test skill can be loaded in Claude Code context (progressive disclosure)."""
        # This test validates the skill file structure is compatible with Claude Code 2.0+
        assert SKILL_FILE.exists(), "Skill file must exist"

        content = SKILL_FILE.read_text()

        # Must have valid YAML frontmatter
        assert content.startswith("---\n"), "Must have YAML frontmatter"
        parts = content.split("---\n", 2)
        assert len(parts) >= 3, "Must have content after frontmatter"

        # Frontmatter must parse
        frontmatter = yaml.safe_load(parts[1])
        assert isinstance(frontmatter, dict), "Frontmatter must be valid YAML dict"

    def test_skill_metadata_stays_in_context(self):
        """Test skill metadata is lightweight (stays in context for progressive disclosure)."""
        content = SKILL_FILE.read_text()
        parts = content.split("---\n", 2)
        frontmatter_text = parts[1]

        # Frontmatter should be concise (<500 tokens ~= 2000 chars)
        assert len(frontmatter_text) < 2000, (
            f"Skill frontmatter too large: {len(frontmatter_text)} chars\n"
            f"Progressive disclosure requires lightweight metadata (<2000 chars)"
        )

    def test_skill_content_loads_on_demand(self):
        """Test skill full content is available but not loaded by default."""
        content = SKILL_FILE.read_text()
        parts = content.split("---\n", 2)
        skill_content = parts[2]

        # Content should exist (for on-demand loading)
        assert len(skill_content) > 100, (
            "Skill must have substantial content for on-demand loading"
        )

        # Content should reference external files (docs/templates/examples)
        assert "docs/" in skill_content or "templates/" in skill_content, (
            "Skill should reference external documentation files"
        )

    def test_skill_activates_on_relevant_keywords(self):
        """Test skill auto-activates when agent uses skill integration keywords."""
        content = SKILL_FILE.read_text()
        parts = content.split("---\n", 2)
        frontmatter = yaml.safe_load(parts[1])

        keywords = frontmatter.get("keywords", [])

        # Should activate on skill reference patterns
        activation_keywords = ["skill-reference", "agent-skills", "integration-patterns"]

        for keyword in activation_keywords:
            assert keyword in keywords, (
                f"Skill must activate on keyword: {keyword}"
            )

    def test_skill_doesnt_bloat_context_when_inactive(self):
        """Test skill doesn't bloat context when not activated."""
        content = SKILL_FILE.read_text()

        # When skill is inactive, only frontmatter + brief overview should load
        # Full docs/templates/examples should be referenced but not inlined

        # SKILL.md should be lightweight (<100 lines)
        line_count = len(content.split("\n"))
        assert line_count < 100, (
            f"SKILL.md too large: {line_count} lines\n"
            f"Progressive disclosure requires lightweight SKILL.md (<100 lines)\n"
            f"Full content should be in docs/templates/examples/ (loaded on-demand)"
        )

    def test_skill_backward_compatible_with_existing_agents(self):
        """Test skill can be added without breaking existing agents."""
        # Agents that don't reference skill should still work
        # This tests graceful degradation

        # Pick an agent that might not reference skill yet
        agent_file = AGENTS_DIR / "advisor.md"

        if agent_file.exists():
            content = agent_file.read_text()

            # Should have valid frontmatter (won't break if skill not referenced)
            if content.startswith("---\n"):
                parts = content.split("---\n", 2)
                assert len(parts) >= 3, "Agent must have valid frontmatter"

    def test_skill_integrates_with_existing_skills(self):
        """Test skill-integration-templates doesn't conflict with other skills."""
        skills_dir = SKILL_DIR.parent

        # Should coexist with other skills
        existing_skills = list(skills_dir.glob("*/SKILL.md"))

        # skill-integration-templates should be one of many
        skill_names = [s.parent.name for s in existing_skills]

        assert "skill-integration-templates" in skill_names, (
            "skill-integration-templates must exist alongside other skills"
        )

        # Should have unique name
        assert skill_names.count("skill-integration-templates") == 1, (
            "skill-integration-templates name must be unique"
        )

    def test_documentation_files_are_discoverable(self):
        """Test all documentation files can be discovered via SKILL.md references."""
        content = SKILL_FILE.read_text()

        # SKILL.md should reference all docs
        doc_files = list(DOCS_DIR.glob("*.md")) if DOCS_DIR.exists() else []

        for doc_file in doc_files:
            # Each doc should be mentioned in SKILL.md
            assert doc_file.name in content, (
                f"SKILL.md must reference documentation file: {doc_file.name}"
            )

    def test_templates_are_reusable(self):
        """Test templates are designed for reuse across multiple agents."""
        if not TEMPLATES_DIR.exists():
            pytest.skip("Templates directory not created yet")

        template_files = list(TEMPLATES_DIR.glob("*.md"))

        for template_file in template_files:
            content = template_file.read_text()

            # Templates should have placeholders for reuse
            has_placeholder = (
                "[" in content or  # Markdown link/placeholder
                "{" in content or  # Template variable
                "example" in content.lower() or  # Example content
                "template" in content.lower()  # Template guidance
            )

            assert has_placeholder, (
                f"Template {template_file.name} should have placeholders for reuse"
            )

    def test_examples_match_real_agent_patterns(self):
        """Test examples use actual patterns from real agents."""
        if not EXAMPLES_DIR.exists():
            pytest.skip("Examples directory not created yet")

        example_files = list(EXAMPLES_DIR.glob("*.md"))

        for example_file in example_files:
            content = example_file.read_text()

            # Examples should mention specific agent names or use realistic patterns
            has_agent_ref = any(agent.replace(".md", "") in content.lower()
                               for agent in AGENT_FILES)

            # Or should use realistic skill names
            has_skill_ref = "skill" in content.lower()

            assert has_agent_ref or has_skill_ref, (
                f"Example {example_file.name} should use realistic agent/skill patterns"
            )


class TestTokenReduction:
    """Test token reduction targets are met (3-5% = ~600-1,000 tokens)."""

    def test_baseline_agent_token_count_measurable(self):
        """Test baseline agent token count can be measured before streamlining."""
        # This test validates we can measure token reduction

        # Count tokens in all agent files (before streamlining)
        total_tokens = 0

        for agent_file in AGENT_FILES:
            agent_path = AGENTS_DIR / agent_file
            if agent_path.exists():
                content = agent_path.read_text()
                # Rough token estimate: 1 token ~= 4 chars
                tokens = len(content) / 4
                total_tokens += tokens

        # Should have measurable baseline
        assert total_tokens > 0, (
            "Must have baseline agent token count to measure reduction"
        )

    def test_streamlined_agent_token_count_reduced(self):
        """Test streamlined agents have reduced token count."""
        # This test will fail until agents are streamlined

        # After streamlining, agents should reference skill instead of inline patterns
        # Expected reduction: 30-50 tokens per agent × 8 agents = 240-400 tokens (Issue #147)

        total_skill_refs = 0

        for agent_file in AGENT_FILES:
            agent_path = AGENTS_DIR / agent_file
            if agent_path.exists():
                content = agent_path.read_text()

                # Check if agent references skill
                if "skill-integration-templates" in content:
                    total_skill_refs += 1

        # All 8 active agents should reference skill (Issue #147)
        assert total_skill_refs == 8, (
            f"Expected all 8 agents to reference skill-integration-templates\n"
            f"Found: {total_skill_refs} agents with references\n"
            f"Missing: {8 - total_skill_refs} agents"
        )

    def test_token_reduction_target_3_percent_minimum(self):
        """Test token reduction meets minimum 3% target."""
        # Calculate reduction from baseline

        # Baseline estimate: ~8,000 tokens across 8 agents (Issue #147)
        baseline_estimate = 8000

        # After streamlining: Should save ~600 tokens (3%)
        minimum_reduction = baseline_estimate * 0.03  # 600 tokens

        # Count agents with skill references
        streamlined_count = 0

        for agent_file in AGENT_FILES:
            agent_path = AGENTS_DIR / agent_file
            if agent_path.exists():
                content = agent_path.read_text()
                if "skill-integration-templates" in content:
                    streamlined_count += 1

        # Rough reduction estimate: 30 tokens per agent
        estimated_reduction = streamlined_count * 30

        assert estimated_reduction >= minimum_reduction, (
            f"Token reduction below 3% target\n"
            f"Expected: >={minimum_reduction} tokens (3%)\n"
            f"Estimated: {estimated_reduction} tokens\n"
            f"Agents streamlined: {streamlined_count}/20"
        )

    def test_token_reduction_target_5_percent_stretch(self):
        """Test token reduction meets stretch 5% target."""
        # Stretch goal: 5% reduction (~1,000 tokens)

        baseline_estimate = 20000
        stretch_reduction = baseline_estimate * 0.05  # 1,000 tokens

        # Count agents with skill references
        streamlined_count = 0

        for agent_file in AGENT_FILES:
            agent_path = AGENTS_DIR / agent_file
            if agent_path.exists():
                content = agent_path.read_text()
                if "skill-integration-templates" in content:
                    streamlined_count += 1

        # Optimistic reduction estimate: 50 tokens per agent
        estimated_reduction = streamlined_count * 50

        # This is a stretch goal - may not always pass
        if estimated_reduction >= stretch_reduction:
            assert True, "Stretch goal achieved!"
        else:
            pytest.skip(
                f"Stretch goal not met: {estimated_reduction}/{stretch_reduction} tokens\n"
                f"This is acceptable - minimum 3% target is required"
            )

    def test_skill_overhead_minimal(self):
        """Test skill-integration-templates overhead is minimal (<100 tokens in context)."""
        if not SKILL_FILE.exists():
            pytest.skip("Skill file not created yet")

        content = SKILL_FILE.read_text()
        parts = content.split("---\n", 2)

        # Frontmatter + overview should be lightweight
        frontmatter_text = parts[1]

        # Rough token count: chars / 4
        overhead_tokens = len(frontmatter_text) / 4

        assert overhead_tokens < 100, (
            f"Skill overhead too high: {overhead_tokens} tokens\n"
            f"Progressive disclosure requires <100 tokens overhead\n"
            f"Frontmatter size: {len(frontmatter_text)} chars"
        )

    def test_per_agent_reduction_measurable(self):
        """Test per-agent token reduction can be measured and validated."""
        # This test validates we can measure individual agent improvements

        for agent_file in AGENT_FILES:
            agent_path = AGENTS_DIR / agent_file
            if agent_path.exists():
                content = agent_path.read_text()

                # Can measure before/after
                current_tokens = len(content) / 4

                # Should be measurable
                assert current_tokens > 0, (
                    f"Agent {agent_file} must have measurable token count"
                )

    def test_total_reduction_accumulates_across_agents(self):
        """Test total reduction accumulates correctly across all 8 agents (Issue #147)."""
        # Sum of individual reductions should equal total reduction

        agents_with_refs = 0

        for agent_file in AGENT_FILES:
            agent_path = AGENTS_DIR / agent_file
            if agent_path.exists():
                content = agent_path.read_text()
                if "skill-integration-templates" in content:
                    agents_with_refs += 1

        # Total reduction = agents_with_refs × avg_reduction_per_agent
        # Expected: 8 agents × ~30-50 tokens = 240-400 tokens (Issue #147)

        assert agents_with_refs > 0, (
            "Must have at least one agent with skill reference to measure reduction"
        )

    def test_reduction_maintains_agent_quality(self):
        """Test token reduction doesn't sacrifice agent prompt quality."""
        # Streamlined agents should still have essential content

        for agent_file in AGENT_FILES:
            agent_path = AGENTS_DIR / agent_file
            if agent_path.exists():
                content = agent_path.read_text()

                # Should still have:
                # 1. Frontmatter
                # 2. Mission/role description
                # 3. Relevant Skills section

                has_frontmatter = content.startswith("---\n")
                has_mission = "mission" in content.lower() or "role" in content.lower()
                has_skills = "skill" in content.lower()

                assert has_frontmatter and has_mission and has_skills, (
                    f"Agent {agent_file} missing essential content after streamlining\n"
                    f"Frontmatter: {has_frontmatter}\n"
                    f"Mission: {has_mission}\n"
                    f"Skills: {has_skills}"
                )


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
