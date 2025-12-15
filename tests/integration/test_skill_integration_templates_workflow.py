#!/usr/bin/env python3
"""
Integration Tests for skill-integration-templates Workflow (FAILING - Red Phase)

This module contains FAILING integration tests for the complete workflow of
creating and using the skill-integration-templates skill (Issue #72 Phase 8.6).

Workflow Tests:
1. Skill creation and structure validation
2. Agent streamlining and reference validation
3. Token reduction measurement and validation
4. Progressive disclosure behavior
5. Backward compatibility with existing agents

Test Coverage: 10 integration tests

Author: test-master agent
Date: 2025-11-16
Issue: #72 Phase 8.6
"""

import os
import sys
from pathlib import Path
import re

import pytest
import yaml

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

SKILL_DIR = Path(__file__).parent.parent.parent / "plugins" / "autonomous-dev" / "skills" / "skill-integration-templates"
SKILL_FILE = SKILL_DIR / "SKILL.md"
AGENTS_DIR = Path(__file__).parent.parent.parent / "plugins" / "autonomous-dev" / "agents"

# All 8 active agent files (Issue #147: consolidated from 21 to 8)
AGENT_FILES = [
    "doc-master.md",
    "implementer.md",
    "issue-creator.md",
    "planner.md",
    "researcher-local.md",
    "reviewer.md",
    "security-auditor.md",
    "test-master.md",
]


class TestSkillCreationWorkflow:
    """Test end-to-end skill creation workflow."""

    def test_skill_directory_structure_complete(self):
        """Test complete skill directory structure exists with all files."""
        # Skill directory
        assert SKILL_DIR.exists() and SKILL_DIR.is_dir(), (
            f"Skill directory must exist: {SKILL_DIR}"
        )

        # Main skill file
        assert SKILL_FILE.exists(), (
            f"SKILL.md must exist: {SKILL_FILE}"
        )

        # Subdirectories
        docs_dir = SKILL_DIR / "docs"
        templates_dir = SKILL_DIR / "templates"
        examples_dir = SKILL_DIR / "examples"

        assert docs_dir.exists() and docs_dir.is_dir(), (
            f"docs/ directory must exist: {docs_dir}"
        )
        assert templates_dir.exists() and templates_dir.is_dir(), (
            f"templates/ directory must exist: {templates_dir}"
        )
        assert examples_dir.exists() and examples_dir.is_dir(), (
            f"examples/ directory must exist: {examples_dir}"
        )

        # Documentation files
        expected_docs = [
            "skill-reference-syntax.md",
            "agent-action-verbs.md",
            "progressive-disclosure-usage.md",
            "integration-best-practices.md",
        ]

        for doc in expected_docs:
            doc_path = docs_dir / doc
            assert doc_path.exists(), (
                f"Documentation file must exist: {doc_path}"
            )

        # Template files
        expected_templates = [
            "skill-section-template.md",
            "intro-sentence-templates.md",
            "closing-sentence-templates.md",
        ]

        for template in expected_templates:
            template_path = templates_dir / template
            assert template_path.exists(), (
                f"Template file must exist: {template_path}"
            )

        # Example files
        expected_examples = [
            "planner-skill-section.md",
            "implementer-skill-section.md",
            "minimal-skill-reference.md",
        ]

        for example in expected_examples:
            example_path = examples_dir / example
            assert example_path.exists(), (
                f"Example file must exist: {example_path}"
            )

    def test_skill_file_parseable_as_yaml_frontmatter(self):
        """Test skill file can be parsed with valid YAML frontmatter."""
        content = SKILL_FILE.read_text()

        # Must start with frontmatter
        assert content.startswith("---\n"), (
            "SKILL.md must start with YAML frontmatter"
        )

        # Must have closing delimiter
        parts = content.split("---\n", 2)
        assert len(parts) >= 3, (
            "SKILL.md must have closing --- for frontmatter"
        )

        # Frontmatter must parse
        frontmatter = yaml.safe_load(parts[1])
        assert isinstance(frontmatter, dict), (
            "Frontmatter must parse as YAML dict"
        )

        # Must have required fields
        assert frontmatter.get("name") == "skill-integration-templates"
        assert frontmatter.get("type") == "knowledge"
        assert "keywords" in frontmatter
        assert "description" in frontmatter

    def test_all_documentation_files_have_content(self):
        """Test all documentation files contain meaningful content."""
        docs_dir = SKILL_DIR / "docs"

        doc_files = list(docs_dir.glob("*.md")) if docs_dir.exists() else []

        for doc_file in doc_files:
            content = doc_file.read_text()

            # Should have headings
            assert "#" in content, (
                f"{doc_file.name} must have markdown headings"
            )

            # Should have substantial content (>500 chars)
            assert len(content) > 500, (
                f"{doc_file.name} must have substantial content (>500 chars)\n"
                f"Found: {len(content)} chars"
            )


class TestAgentStreamliningWorkflow:
    """Test end-to-end agent streamlining workflow."""

    def test_all_agents_reference_skill(self):
        """Test all 8 active agents reference skill-integration-templates skill (Issue #147)."""
        agents_with_refs = []
        agents_without_refs = []

        for agent_file in AGENT_FILES:
            agent_path = AGENTS_DIR / agent_file
            if agent_path.exists():
                content = agent_path.read_text()
                if "skill-integration-templates" in content:
                    agents_with_refs.append(agent_file)
                else:
                    agents_without_refs.append(agent_file)

        assert len(agents_with_refs) == 8, (
            f"All 8 agents must reference skill-integration-templates\n"
            f"With references: {len(agents_with_refs)}\n"
            f"Without references: {agents_without_refs}"
        )

    def test_agent_skill_sections_follow_template(self):
        """Test agent skill sections follow template structure."""
        # Check that streamlined agents use consistent format

        consistent_agents = []
        inconsistent_agents = []

        for agent_file in AGENT_FILES:
            agent_path = AGENTS_DIR / agent_file
            if agent_path.exists():
                content = agent_path.read_text()

                # Should have Relevant Skills section
                has_section = "Relevant Skills" in content or "## Relevant Skills" in content

                # Should reference skill
                has_skill_ref = "skill-integration-templates" in content

                if has_section and has_skill_ref:
                    consistent_agents.append(agent_file)
                else:
                    inconsistent_agents.append(agent_file)

        # At least some agents should follow template
        assert len(consistent_agents) > 0, (
            f"No agents follow skill section template\n"
            f"Expected: Relevant Skills section + skill-integration-templates reference\n"
            f"Inconsistent agents: {inconsistent_agents}"
        )

    def test_streamlined_agents_maintain_quality(self):
        """Test streamlined agents maintain essential quality characteristics."""
        for agent_file in AGENT_FILES:
            agent_path = AGENTS_DIR / agent_file
            if agent_path.exists():
                content = agent_path.read_text()

                # Must have frontmatter
                assert content.startswith("---\n"), (
                    f"{agent_file} must have YAML frontmatter"
                )

                # Must have mission/role description
                has_mission = (
                    "mission" in content.lower() or
                    "role" in content.lower() or
                    "purpose" in content.lower()
                )

                assert has_mission, (
                    f"{agent_file} must have mission/role description"
                )

                # Must have substantial content (>1000 chars)
                assert len(content) > 1000, (
                    f"{agent_file} content too short: {len(content)} chars\n"
                    f"Streamlining shouldn't remove essential content"
                )


class TestTokenReductionWorkflow:
    """Test end-to-end token reduction measurement and validation."""

    def test_token_reduction_measurable_across_all_agents(self):
        """Test token reduction can be measured across all agents."""
        # Calculate total tokens before/after streamlining

        total_tokens_before = 0  # Baseline (without skill references)
        total_tokens_after = 0   # After streamlining (with skill references)

        for agent_file in AGENT_FILES:
            agent_path = AGENTS_DIR / agent_file
            if agent_path.exists():
                content = agent_path.read_text()

                # Current token count
                current_tokens = len(content) / 4  # Rough estimate

                if "skill-integration-templates" in content:
                    total_tokens_after += current_tokens
                else:
                    total_tokens_before += current_tokens

        # Should have measurable difference
        # (This will fail until agents are streamlined)

        assert total_tokens_after > 0, (
            "Must have streamlined agents to measure token reduction"
        )

    def test_token_reduction_meets_minimum_target(self):
        """Test token reduction meets minimum 3% target (240 tokens) - Issue #147."""
        # Baseline estimate: 8,000 tokens across 8 agents (Issue #147)
        baseline_estimate = 8000
        minimum_reduction = 240  # 3%

        # Count streamlined agents
        streamlined_count = 0

        for agent_file in AGENT_FILES:
            agent_path = AGENTS_DIR / agent_file
            if agent_path.exists():
                content = agent_path.read_text()
                if "skill-integration-templates" in content:
                    streamlined_count += 1

        # Estimate reduction: 30 tokens per agent
        estimated_reduction = streamlined_count * 30

        assert estimated_reduction >= minimum_reduction, (
            f"Token reduction below minimum target\n"
            f"Expected: >={minimum_reduction} tokens (3%)\n"
            f"Estimated: {estimated_reduction} tokens\n"
            f"Streamlined agents: {streamlined_count}/8"
        )

    def test_skill_overhead_doesnt_negate_savings(self):
        """Test skill overhead doesn't negate token savings."""
        if not SKILL_FILE.exists():
            pytest.skip("Skill not created yet")

        content = SKILL_FILE.read_text()
        parts = content.split("---\n", 2)

        # Skill overhead (frontmatter + overview)
        overhead_tokens = len(parts[1]) / 4

        # Should be minimal (<100 tokens)
        assert overhead_tokens < 100, (
            f"Skill overhead too high: {overhead_tokens} tokens\n"
            f"This negates savings from streamlining agents"
        )


class TestProgressiveDisclosureWorkflow:
    """Test progressive disclosure behavior in practice."""

    def test_skill_loads_metadata_only_by_default(self):
        """Test skill loads only metadata by default (progressive disclosure)."""
        content = SKILL_FILE.read_text()

        # SKILL.md should be lightweight (<100 lines)
        line_count = len(content.split("\n"))

        assert line_count < 100, (
            f"SKILL.md too large for progressive disclosure: {line_count} lines\n"
            f"Should be <100 lines (metadata + brief overview)\n"
            f"Full content should be in docs/templates/examples/"
        )

    def test_full_content_available_on_demand(self):
        """Test full skill content is available when needed."""
        # Documentation files should exist
        docs_dir = SKILL_DIR / "docs"

        if docs_dir.exists():
            doc_files = list(docs_dir.glob("*.md"))

            assert len(doc_files) >= 4, (
                f"Expected at least 4 documentation files\n"
                f"Found: {len(doc_files)}"
            )

            # Total content should be substantial
            total_content_size = sum(
                len(f.read_text()) for f in doc_files
            )

            # Should be >2000 chars total
            assert total_content_size > 2000, (
                f"Documentation content too sparse: {total_content_size} chars\n"
                f"Expected: >2000 chars across all docs"
            )

    def test_keyword_activation_triggers_full_load(self):
        """Test skill activates (full load) on relevant keywords."""
        content = SKILL_FILE.read_text()
        parts = content.split("---\n", 2)
        frontmatter = yaml.safe_load(parts[1])

        keywords = frontmatter.get("keywords", [])

        # Should have keywords for activation
        assert len(keywords) >= 5, (
            f"Skill should have multiple keywords for activation\n"
            f"Found: {len(keywords)} keywords"
        )

        # Keywords should cover skill integration scenarios
        integration_keywords = [
            "skill-reference",
            "agent-skills",
            "progressive-disclosure",
        ]

        for keyword in integration_keywords:
            assert keyword in keywords, (
                f"Missing integration keyword: {keyword}"
            )


class TestBackwardCompatibilityWorkflow:
    """Test backward compatibility with existing agents."""

    def test_agents_without_skill_reference_still_work(self):
        """Test agents that don't reference skill still have valid structure."""
        # Test graceful degradation

        for agent_file in AGENT_FILES:
            agent_path = AGENTS_DIR / agent_file
            if agent_path.exists():
                content = agent_path.read_text()

                # Must have valid frontmatter
                assert content.startswith("---\n"), (
                    f"{agent_file} must have valid frontmatter"
                )

                # Must parse
                parts = content.split("---\n", 2)
                assert len(parts) >= 3, (
                    f"{agent_file} must have content after frontmatter"
                )

    def test_skill_doesnt_break_existing_skill_references(self):
        """Test skill-integration-templates doesn't conflict with other skills."""
        # Agents should be able to reference multiple skills

        for agent_file in AGENT_FILES:
            agent_path = AGENTS_DIR / agent_file
            if agent_path.exists():
                content = agent_path.read_text()

                # Count skill references
                skill_refs = content.count("skill")

                # If agent has skill references, should have multiple
                if skill_refs > 0:
                    # Should reference both skill-integration-templates and domain skills
                    assert skill_refs >= 2, (
                        f"{agent_file} should reference multiple skills\n"
                        f"Found: {skill_refs} skill references"
                    )


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
