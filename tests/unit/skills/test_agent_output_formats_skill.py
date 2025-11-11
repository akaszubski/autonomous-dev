#!/usr/bin/env python3
"""
TDD Tests for agent-output-formats Skill (FAILING - Red Phase)

This module contains FAILING tests for the agent-output-formats skill that will
extract duplicated output format specifications from 15 agent prompts (Issue #63).

Skill Requirements:
1. YAML frontmatter with name, type, description, keywords, auto_activate
2. Progressive disclosure architecture (metadata in frontmatter, content loads on-demand)
3. Standardized output formats for 4 agent types:
   - Research agents (Patterns Found, Best Practices, Security, Recommendations)
   - Planning agents (Feature Summary, Architecture, Components, Implementation Plan, Risks)
   - Implementation agents (Changes Made, Files Modified, Tests Updated, Next Steps)
   - Review agents (Findings, Code Quality, Security, Documentation, Verdict)
4. Example outputs for each format (examples/ directory)
5. Token reduction: ~200 tokens per agent × 15 agents = ~3,000 tokens

Test Coverage Target: 100% of skill creation and agent integration

Following TDD principles:
- Write tests FIRST (red phase)
- Tests describe skill requirements and agent integration
- Tests should FAIL until skill file and agent updates are implemented
- Each test validates ONE requirement

Author: test-master agent
Date: 2025-11-11
Issue: #63
"""

import os
import sys
from pathlib import Path
from unittest.mock import Mock, patch, mock_open

import pytest
import yaml

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

SKILL_DIR = Path(__file__).parent.parent.parent.parent / "plugins" / "autonomous-dev" / "skills" / "agent-output-formats"
SKILL_FILE = SKILL_DIR / "SKILL.md"
EXAMPLES_DIR = SKILL_DIR / "examples"
AGENTS_DIR = Path(__file__).parent.parent.parent.parent / "plugins" / "autonomous-dev" / "agents"


class TestSkillCreation:
    """Test agent-output-formats skill file structure and metadata."""

    def test_skill_file_exists(self):
        """Test SKILL.md file exists in skills/agent-output-formats/ directory."""
        assert SKILL_FILE.exists(), (
            f"Skill file not found: {SKILL_FILE}\n"
            f"Expected: Create skills/agent-output-formats/SKILL.md\n"
            f"See: Issue #63"
        )

    def test_skill_has_valid_yaml_frontmatter(self):
        """Test skill file has valid YAML frontmatter with required fields."""
        content = SKILL_FILE.read_text()

        # Check frontmatter exists
        assert content.startswith("---\n"), (
            "Skill file must start with YAML frontmatter (---)\n"
            "Expected format:\n"
            "---\n"
            "name: agent-output-formats\n"
            "type: knowledge\n"
            "...\n"
        )

        # Extract frontmatter
        parts = content.split("---\n", 2)
        assert len(parts) >= 3, "Skill file must have closing --- for frontmatter"

        frontmatter = yaml.safe_load(parts[1])

        # Validate required fields
        assert frontmatter.get("name") == "agent-output-formats", (
            "Skill name must be 'agent-output-formats'"
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

    def test_skill_keywords_cover_output_terms(self):
        """Test skill keywords include common output format terms."""
        content = SKILL_FILE.read_text()
        parts = content.split("---\n", 2)
        frontmatter = yaml.safe_load(parts[1])

        keywords = frontmatter.get("keywords", "")
        if isinstance(keywords, list):
            keywords = " ".join(keywords)

        expected_keywords = ["output", "format", "research", "planning", "implementation", "review"]

        for keyword in expected_keywords:
            assert keyword.lower() in keywords.lower(), (
                f"Skill keywords must include '{keyword}' for auto-activation\n"
                f"Current keywords: {keywords}"
            )

    def test_skill_defines_research_agent_format(self):
        """Test skill defines output format for research agents."""
        content = SKILL_FILE.read_text()

        # Check for research agent format specification
        assert "## Research Agent Output Format" in content or "Research agents" in content, (
            "Skill must define output format for research agents\n"
            "Expected sections: Patterns Found, Best Practices, Security, Recommendations"
        )

        # Check for required sections
        required_sections = ["Patterns Found", "Best Practices", "Security", "Recommendations"]
        for section in required_sections:
            assert section in content, (
                f"Research agent format must include '{section}' section\n"
                f"See: plugins/autonomous-dev/agents/researcher.md for current format"
            )

    def test_skill_defines_planning_agent_format(self):
        """Test skill defines output format for planning agents."""
        content = SKILL_FILE.read_text()

        # Check for planning agent format specification
        assert "## Planning Agent Output Format" in content or "Planning agents" in content, (
            "Skill must define output format for planning agents\n"
            "Expected sections: Feature Summary, Architecture, Components, Implementation Plan, Risks"
        )

        # Check for required sections
        required_sections = ["Feature Summary", "Architecture", "Components", "Implementation Plan", "Risks"]
        for section in required_sections:
            assert section in content, (
                f"Planning agent format must include '{section}' section\n"
                f"See: plugins/autonomous-dev/agents/planner.md for current format"
            )

    def test_skill_defines_implementation_agent_format(self):
        """Test skill defines output format for implementation agents."""
        content = SKILL_FILE.read_text()

        # Check for implementation agent format specification
        assert "## Implementation Agent Output Format" in content or "Implementation agents" in content, (
            "Skill must define output format for implementation agents\n"
            "Expected sections: Changes Made, Files Modified, Tests Updated, Next Steps"
        )

        # Check for required sections
        required_sections = ["Changes Made", "Files Modified", "Tests Updated", "Next Steps"]
        for section in required_sections:
            assert section in content, (
                f"Implementation agent format must include '{section}' section\n"
                f"See: plugins/autonomous-dev/agents/implementer.md for current format"
            )

    def test_skill_defines_review_agent_format(self):
        """Test skill defines output format for review agents."""
        content = SKILL_FILE.read_text()

        # Check for review agent format specification
        assert "## Review Agent Output Format" in content or "Review agents" in content, (
            "Skill must define output format for review agents\n"
            "Expected sections: Findings, Code Quality, Security, Documentation, Verdict"
        )

        # Check for required sections
        required_sections = ["Findings", "Code Quality", "Security", "Documentation", "Verdict"]
        for section in required_sections:
            assert section in content, (
                f"Review agent format must include '{section}' section\n"
                f"See: plugins/autonomous-dev/agents/reviewer.md for current format"
            )


class TestSkillExamples:
    """Test agent-output-formats skill provides example outputs."""

    def test_examples_directory_exists(self):
        """Test examples/ directory exists with sample outputs."""
        assert EXAMPLES_DIR.exists(), (
            f"Examples directory not found: {EXAMPLES_DIR}\n"
            f"Expected: Create skills/agent-output-formats/examples/\n"
            f"Purpose: Provide sample outputs for each agent type"
        )

    def test_research_example_exists(self):
        """Test research agent example output exists."""
        example_file = EXAMPLES_DIR / "research-output-example.md"
        assert example_file.exists(), (
            f"Research example not found: {example_file}\n"
            f"Expected: Create example showing Patterns Found, Best Practices, etc."
        )

    def test_planning_example_exists(self):
        """Test planning agent example output exists."""
        example_file = EXAMPLES_DIR / "planning-output-example.md"
        assert example_file.exists(), (
            f"Planning example not found: {example_file}\n"
            f"Expected: Create example showing Feature Summary, Architecture, etc."
        )

    def test_implementation_example_exists(self):
        """Test implementation agent example output exists."""
        example_file = EXAMPLES_DIR / "implementation-output-example.md"
        assert example_file.exists(), (
            f"Implementation example not found: {example_file}\n"
            f"Expected: Create example showing Changes Made, Files Modified, etc."
        )

    def test_review_example_exists(self):
        """Test review agent example output exists."""
        example_file = EXAMPLES_DIR / "review-output-example.md"
        assert example_file.exists(), (
            f"Review example not found: {example_file}\n"
            f"Expected: Create example showing Findings, Code Quality, etc."
        )


class TestAgentIntegration:
    """Test 15 agents reference agent-output-formats skill."""

    AGENTS_USING_SKILL = [
        "researcher.md",
        "planner.md",
        "implementer.md",
        "reviewer.md",
        "security-auditor.md",
        "doc-master.md",
        "commit-message-generator.md",
        "pr-description-generator.md",
        "issue-creator.md",
        "brownfield-analyzer.md",
        "alignment-analyzer.md",
        "project-bootstrapper.md",
        "setup-wizard.md",
        "project-status-analyzer.md",
        "sync-validator.md"
    ]

    @pytest.mark.parametrize("agent_file", AGENTS_USING_SKILL)
    def test_agent_references_skill(self, agent_file):
        """Test agent prompt references agent-output-formats skill."""
        agent_path = AGENTS_DIR / agent_file
        content = agent_path.read_text()

        assert "agent-output-formats" in content, (
            f"Agent {agent_file} must reference 'agent-output-formats' skill\n"
            f"Expected: Add to 'Relevant Skills' section\n"
            f"Format: - **agent-output-formats**: Standardized output formats\n"
            f"See: Issue #63"
        )

    @pytest.mark.parametrize("agent_file", AGENTS_USING_SKILL)
    def test_agent_output_format_section_removed(self, agent_file):
        """Test agent prompt no longer has redundant ## Output Format section."""
        agent_path = AGENTS_DIR / agent_file
        content = agent_path.read_text()

        # Allow agents that need custom output formats (not covered by skill)
        # Most agents should remove ## Output Format section
        if "## Output Format" in content:
            # If section exists, it should reference the skill
            assert "agent-output-formats" in content, (
                f"Agent {agent_file} has ## Output Format section but doesn't reference skill\n"
                f"Expected: Either remove ## Output Format or reference skill for standard formats\n"
                f"Token savings: ~200 tokens per agent × 15 agents = ~3,000 tokens"
            )

    def test_total_agent_count_using_skill(self):
        """Test 15 agents use agent-output-formats skill."""
        count = 0
        for agent_file in self.AGENTS_USING_SKILL:
            agent_path = AGENTS_DIR / agent_file
            if agent_path.exists():
                content = agent_path.read_text()
                if "agent-output-formats" in content:
                    count += 1

        assert count == 15, (
            f"Expected 15 agents to reference agent-output-formats skill, found {count}\n"
            f"Target: researcher, planner, implementer, reviewer, security-auditor, doc-master, "
            f"commit-message-generator, pr-description-generator, issue-creator, brownfield-analyzer, "
            f"alignment-analyzer, project-bootstrapper, setup-wizard, project-status-analyzer, sync-validator\n"
            f"See: Issue #63"
        )


class TestTokenSavings:
    """Test token reduction from skill extraction."""

    def test_token_reduction_per_agent(self):
        """Test each agent saves ~200 tokens by using skill reference."""
        # This is a placeholder test - actual token counting would require
        # tokenization library or manual calculation

        # Expected savings calculation:
        # Before: ~250 tokens for ## Output Format section
        # After: ~50 tokens for skill reference
        # Savings: ~200 tokens per agent

        pytest.skip(
            "Token counting requires implementation\n"
            "Expected: Use tiktoken or similar to count tokens\n"
            "Baseline: Measure tokens before/after skill extraction\n"
            "Target: 200 tokens saved per agent"
        )

    def test_total_token_reduction(self):
        """Test total token savings across all 15 agents."""
        # Expected total savings: 200 tokens × 15 agents = 3,000 tokens

        pytest.skip(
            "Token counting requires implementation\n"
            "Expected: Aggregate token savings across all agents\n"
            "Target: 3,000 tokens total reduction (8-12% of agent prompts)\n"
            "See: Issue #63"
        )


class TestProgressiveDisclosure:
    """Test progressive disclosure functionality."""

    def test_skill_metadata_small_for_context(self):
        """Test skill metadata (frontmatter) is small enough to keep in context."""
        content = SKILL_FILE.read_text()
        parts = content.split("---\n", 2)
        frontmatter = parts[1]

        # Frontmatter should be < 200 tokens (very rough estimate: ~4 chars per token)
        assert len(frontmatter) < 800, (
            f"Skill frontmatter too large: {len(frontmatter)} chars\n"
            f"Expected: < 800 chars (~200 tokens) for efficient context usage\n"
            f"Progressive disclosure keeps metadata small, loads full content on-demand"
        )

    def test_skill_full_content_loads_on_demand(self):
        """Test skill full content (after frontmatter) is available when needed."""
        content = SKILL_FILE.read_text()
        parts = content.split("---\n", 2)

        assert len(parts) >= 3, "Skill must have content after frontmatter"

        full_content = parts[2]

        # Full content should have detailed format specifications
        assert len(full_content) > 1000, (
            f"Skill content too small: {len(full_content)} chars\n"
            f"Expected: Detailed output format specifications for all agent types\n"
            f"Progressive disclosure: Metadata always loaded, content loaded when keywords match"
        )


class TestBackwardCompatibility:
    """Test skill integration doesn't break existing agent behavior."""

    def test_agents_still_produce_expected_outputs(self):
        """Test agents produce outputs matching skill specifications."""
        # This test would require running agents and validating outputs
        # Placeholder for integration testing

        pytest.skip(
            "Integration test requires agent execution\n"
            "Expected: Run researcher, planner, implementer, reviewer agents\n"
            "Validate: Outputs match agent-output-formats skill specifications\n"
            "See: tests/integration/test_full_workflow_with_skills.py"
        )


# Performance benchmarks (optional, for optimization tracking)
class TestPerformance:
    """Test skill doesn't degrade performance."""

    def test_skill_load_time(self):
        """Test skill loads quickly for progressive disclosure."""
        import time

        start = time.time()
        content = SKILL_FILE.read_text()
        duration = time.time() - start

        assert duration < 0.1, (
            f"Skill load took {duration:.3f}s, expected < 0.1s\n"
            f"Performance: Skill load must be fast for progressive disclosure"
        )

    def test_yaml_parsing_performance(self):
        """Test YAML frontmatter parsing is fast."""
        import time

        content = SKILL_FILE.read_text()
        parts = content.split("---\n", 2)

        start = time.time()
        frontmatter = yaml.safe_load(parts[1])
        duration = time.time() - start

        assert duration < 0.01, (
            f"YAML parsing took {duration:.3f}s, expected < 0.01s\n"
            f"Performance: Frontmatter parsing must be fast for context efficiency"
        )


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
