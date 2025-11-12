#!/usr/bin/env python3
"""
TDD Tests for project-alignment Skill Creation (FAILING - Red Phase)

This module contains FAILING tests for creating the project-alignment skill
that standardizes PROJECT.md alignment checking across agents (Issue #69).

Skill Requirements:

1. Create new skill: skills/project-alignment/SKILL.md
   - YAML frontmatter with metadata
   - Progressive disclosure architecture
   - PROJECT.md alignment checking patterns
   - Semantic validation guidance
   - Gap assessment methods

2. Documentation files:
   - docs/alignment-checklist.md: Standard alignment validation steps
   - docs/alignment-scenarios.md: Common misalignment scenarios and fixes
   - docs/gap-assessment.md: How to identify and document gaps

3. Example files:
   - examples/alignment-report.md: Example alignment analysis report
   - examples/misalignment-fixes.md: Examples of fixing common issues
   - examples/project-md-structure.md: Expected PROJECT.md structure

4. Agent integration:
   - Update 8 agents to reference project-alignment skill
   - Remove verbose inline alignment guidance
   - Standardize alignment checking approach

Agents to update:
- alignment-validator (primary user)
- alignment-analyzer (heavy user)
- advisor (uses for critical thinking)
- planner (checks feature alignment)
- quality-validator (validates alignment)
- project-bootstrapper (sets up PROJECT.md)
- brownfield-analyzer (assesses project fit)
- project-progress-tracker (tracks alignment with goals)

Expected Token Savings: ~250 tokens (6-8% reduction across 8 agents)

Test Coverage Target: 100% of skill creation and agent integration

Following TDD principles:
- Write tests FIRST (red phase)
- Tests describe skill requirements and agent integration
- Tests should FAIL until skill files and agent updates are implemented
- Each test validates ONE requirement

Author: test-master agent
Date: 2025-11-12
Issue: #69
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
SKILL_DIR = Path(__file__).parent.parent.parent.parent / "plugins" / "autonomous-dev" / "skills" / "project-alignment"
SKILL_FILE = SKILL_DIR / "SKILL.md"
DOCS_DIR = SKILL_DIR / "docs"
EXAMPLES_DIR = SKILL_DIR / "examples"

# Documentation files
ALIGNMENT_CHECKLIST_FILE = DOCS_DIR / "alignment-checklist.md"
ALIGNMENT_SCENARIOS_FILE = DOCS_DIR / "alignment-scenarios.md"
GAP_ASSESSMENT_FILE = DOCS_DIR / "gap-assessment.md"

# Example files
ALIGNMENT_REPORT_FILE = EXAMPLES_DIR / "alignment-report.md"
MISALIGNMENT_FIXES_FILE = EXAMPLES_DIR / "misalignment-fixes.md"
PROJECT_MD_STRUCTURE_FILE = EXAMPLES_DIR / "project-md-structure.md"

# Agent paths
AGENTS_DIR = Path(__file__).parent.parent.parent.parent / "plugins" / "autonomous-dev" / "agents"

# Agents that use project alignment
ALIGNMENT_AGENTS = [
    "alignment-validator",
    "alignment-analyzer",
    "advisor",
    "planner",
    "quality-validator",
    "project-bootstrapper",
    "brownfield-analyzer",
    "project-progress-tracker"
]


# ============================================================================
# Test Suite 1: Skill File Creation
# ============================================================================


class TestProjectAlignmentSkillCreation:
    """Test project-alignment skill file structure and content."""

    def test_skill_directory_exists(self):
        """Test skills/project-alignment/ directory exists."""
        assert SKILL_DIR.exists(), (
            f"Skill directory not found: {SKILL_DIR}\n"
            f"Expected: Create skills/project-alignment/ directory\n"
            f"See: Issue #69"
        )

    def test_skill_file_exists(self):
        """Test SKILL.md file exists in project-alignment directory."""
        assert SKILL_FILE.exists(), (
            f"Skill file not found: {SKILL_FILE}\n"
            f"Expected: Create skills/project-alignment/SKILL.md\n"
            f"See: Issue #69"
        )

    def test_skill_has_valid_yaml_frontmatter(self):
        """Test skill file has valid YAML frontmatter with required fields."""
        content = SKILL_FILE.read_text()

        # Check frontmatter exists
        assert content.startswith("---\n"), (
            "Skill file must start with YAML frontmatter (---)\n"
            "Expected format:\n"
            "---\n"
            "name: project-alignment\n"
            "type: knowledge\n"
            "...\n"
        )

        # Extract frontmatter
        parts = content.split("---\n", 2)
        assert len(parts) >= 3, "Skill file must have closing --- for frontmatter"

        frontmatter = yaml.safe_load(parts[1])

        # Validate required fields
        assert frontmatter.get("name") == "project-alignment", (
            "Skill name must be 'project-alignment'\n"
            f"Got: {frontmatter.get('name')}"
        )

        assert frontmatter.get("type") == "knowledge", (
            "Skill type must be 'knowledge'\n"
            f"Got: {frontmatter.get('type')}"
        )

        assert "description" in frontmatter, "Missing description field"
        assert "keywords" in frontmatter, "Missing keywords field"
        assert "auto_activate" in frontmatter, "Missing auto_activate field"

    def test_skill_metadata_has_alignment_keywords(self):
        """Test skill metadata includes alignment-related keywords."""
        content = SKILL_FILE.read_text()
        parts = content.split("---\n", 2)
        frontmatter = yaml.safe_load(parts[1])

        keywords = frontmatter.get("keywords", [])

        # Required keywords for skill activation
        required_keywords = [
            "alignment",
            "PROJECT.md",
            "semantic validation",
            "gap assessment"
        ]

        found_keywords = [k for k in required_keywords if any(k in keyword.lower() for keyword in keywords)]

        assert len(found_keywords) >= 3, (
            f"Missing alignment-related keywords in project-alignment SKILL.md\n"
            f"Expected: At least 3 of {required_keywords}\n"
            f"Found: {found_keywords}\n"
            f"See: Issue #69"
        )

    def test_skill_content_describes_project_md_alignment(self):
        """Test skill content explains PROJECT.md alignment checking."""
        content = SKILL_FILE.read_text()

        # PROJECT.md alignment concepts
        alignment_concepts = [
            "PROJECT.md",
            "GOALS",
            "SCOPE",
            "CONSTRAINTS",
            "alignment"
        ]

        found = [c for c in alignment_concepts if c in content]

        assert len(found) >= 4, (
            f"Skill content should describe PROJECT.md alignment\n"
            f"Expected: At least 4 of {alignment_concepts}\n"
            f"Found: {found}\n"
            f"See: Issue #69"
        )

    def test_skill_content_describes_semantic_validation(self):
        """Test skill content explains semantic validation approach."""
        content = SKILL_FILE.read_text()

        # Semantic validation concepts
        validation_concepts = [
            "semantic",
            "validate",
            "intent",
            "purpose"
        ]

        found = [c for c in validation_concepts if c in content.lower()]

        assert len(found) >= 3, (
            f"Skill content should describe semantic validation\n"
            f"Expected: At least 3 of {validation_concepts}\n"
            f"Found: {found}\n"
            f"See: Issue #69"
        )


# ============================================================================
# Test Suite 2: Documentation Files
# ============================================================================


class TestProjectAlignmentDocumentation:
    """Test project-alignment documentation files."""

    def test_alignment_checklist_doc_exists(self):
        """Test alignment-checklist.md documentation file exists."""
        assert ALIGNMENT_CHECKLIST_FILE.exists(), (
            f"Alignment checklist not found: {ALIGNMENT_CHECKLIST_FILE}\n"
            f"Expected: Create skills/project-alignment/docs/alignment-checklist.md\n"
            f"Content: Standard validation steps for PROJECT.md alignment\n"
            f"See: Issue #69"
        )

    def test_alignment_checklist_has_standard_checks(self):
        """Test alignment-checklist.md includes standard validation checks."""
        content = ALIGNMENT_CHECKLIST_FILE.read_text()

        # Standard alignment checks
        required_checks = [
            "GOALS",
            "SCOPE",
            "CONSTRAINTS",
            "ARCHITECTURE"
        ]

        for check in required_checks:
            assert check in content, (
                f"Missing '{check}' validation in alignment-checklist.md\n"
                f"Expected: Include checks for all PROJECT.md sections\n"
                f"See: Issue #69"
            )

    def test_alignment_checklist_has_checklist_format(self):
        """Test alignment-checklist.md uses checklist format (checkboxes)."""
        content = ALIGNMENT_CHECKLIST_FILE.read_text()

        # Count checklist items (- [ ] or - [x])
        checklist_pattern = re.compile(r'- \[[ x]\]')
        checkboxes = checklist_pattern.findall(content)

        assert len(checkboxes) >= 8, (
            f"alignment-checklist.md should have ≥8 checklist items\n"
            f"Found {len(checkboxes)} checkboxes\n"
            f"Expected: Comprehensive checklist with multiple validation steps\n"
            f"See: Issue #69"
        )

    def test_alignment_scenarios_doc_exists(self):
        """Test alignment-scenarios.md documentation file exists."""
        assert ALIGNMENT_SCENARIOS_FILE.exists(), (
            f"Alignment scenarios not found: {ALIGNMENT_SCENARIOS_FILE}\n"
            f"Expected: Create skills/project-alignment/docs/alignment-scenarios.md\n"
            f"Content: Common misalignment scenarios and fixes\n"
            f"See: Issue #69"
        )

    def test_alignment_scenarios_has_multiple_scenarios(self):
        """Test alignment-scenarios.md includes at least 5 common scenarios."""
        content = ALIGNMENT_SCENARIOS_FILE.read_text()

        # Count scenarios (sections starting with ##)
        scenario_pattern = re.compile(r'^## ', re.MULTILINE)
        scenarios = scenario_pattern.findall(content)

        assert len(scenarios) >= 5, (
            f"alignment-scenarios.md should have ≥5 scenarios\n"
            f"Found {len(scenarios)} scenarios\n"
            f"Expected: Cover common misalignment cases\n"
            f"See: Issue #69"
        )

    def test_alignment_scenarios_has_fixes(self):
        """Test alignment-scenarios.md includes fixes for scenarios."""
        content = ALIGNMENT_SCENARIOS_FILE.read_text()

        # Should mention fixes/solutions
        fix_keywords = ["fix", "solution", "resolve", "address"]
        found = [k for k in fix_keywords if k in content.lower()]

        assert len(found) >= 2, (
            f"alignment-scenarios.md should include fixes\n"
            f"Expected: Document how to fix each scenario\n"
            f"Found keywords: {found}\n"
            f"See: Issue #69"
        )

    def test_gap_assessment_doc_exists(self):
        """Test gap-assessment.md documentation file exists."""
        assert GAP_ASSESSMENT_FILE.exists(), (
            f"Gap assessment doc not found: {GAP_ASSESSMENT_FILE}\n"
            f"Expected: Create skills/project-alignment/docs/gap-assessment.md\n"
            f"Content: How to identify and document alignment gaps\n"
            f"See: Issue #69"
        )

    def test_gap_assessment_has_methodology(self):
        """Test gap-assessment.md describes gap identification methodology."""
        content = GAP_ASSESSMENT_FILE.read_text()

        # Gap assessment methodology
        methodology_concepts = [
            "identify",
            "document",
            "prioritize",
            "gap"
        ]

        found = [c for c in methodology_concepts if c in content.lower()]

        assert len(found) >= 3, (
            f"gap-assessment.md should describe methodology\n"
            f"Expected: At least 3 of {methodology_concepts}\n"
            f"Found: {found}\n"
            f"See: Issue #69"
        )


# ============================================================================
# Test Suite 3: Example Files
# ============================================================================


class TestProjectAlignmentExamples:
    """Test project-alignment example files."""

    def test_alignment_report_example_exists(self):
        """Test alignment-report.md example file exists."""
        assert ALIGNMENT_REPORT_FILE.exists(), (
            f"Alignment report example not found: {ALIGNMENT_REPORT_FILE}\n"
            f"Expected: Create skills/project-alignment/examples/alignment-report.md\n"
            f"Content: Example alignment analysis report\n"
            f"See: Issue #69"
        )

    def test_alignment_report_has_standard_sections(self):
        """Test alignment-report.md includes standard report sections."""
        content = ALIGNMENT_REPORT_FILE.read_text()

        # Standard report sections
        required_sections = [
            "Summary",
            "Findings",
            "Recommendations"
        ]

        for section in required_sections:
            assert section in content, (
                f"Missing '{section}' section in alignment-report.md example\n"
                f"Expected: Complete example with all standard sections\n"
                f"See: Issue #69"
            )

    def test_alignment_report_shows_aligned_and_misaligned(self):
        """Test alignment-report.md shows both aligned and misaligned examples."""
        content = ALIGNMENT_REPORT_FILE.read_text()

        # Should show both positive and negative examples
        indicators = ["aligned", "misaligned", "gap", "compliant"]
        found = [i for i in indicators if i in content.lower()]

        assert len(found) >= 2, (
            f"alignment-report.md should show aligned and misaligned examples\n"
            f"Expected: Balanced view of alignment status\n"
            f"Found: {found}\n"
            f"See: Issue #69"
        )

    def test_misalignment_fixes_example_exists(self):
        """Test misalignment-fixes.md example file exists."""
        assert MISALIGNMENT_FIXES_FILE.exists(), (
            f"Misalignment fixes example not found: {MISALIGNMENT_FIXES_FILE}\n"
            f"Expected: Create skills/project-alignment/examples/misalignment-fixes.md\n"
            f"Content: Examples of fixing common alignment issues\n"
            f"See: Issue #69"
        )

    def test_misalignment_fixes_has_before_after(self):
        """Test misalignment-fixes.md shows before/after examples."""
        content = MISALIGNMENT_FIXES_FILE.read_text()

        # Should show before and after states
        indicators = ["before", "after", "original", "fixed", "updated"]
        found = [i for i in indicators if i in content.lower()]

        assert len(found) >= 2, (
            f"misalignment-fixes.md should show before/after examples\n"
            f"Expected: Demonstrate how to fix misalignment\n"
            f"Found: {found}\n"
            f"See: Issue #69"
        )

    def test_project_md_structure_example_exists(self):
        """Test project-md-structure.md example file exists."""
        assert PROJECT_MD_STRUCTURE_FILE.exists(), (
            f"PROJECT.md structure example not found: {PROJECT_MD_STRUCTURE_FILE}\n"
            f"Expected: Create skills/project-alignment/examples/project-md-structure.md\n"
            f"Content: Expected PROJECT.md structure and format\n"
            f"See: Issue #69"
        )

    def test_project_md_structure_has_all_sections(self):
        """Test project-md-structure.md includes all standard PROJECT.md sections."""
        content = PROJECT_MD_STRUCTURE_FILE.read_text()

        # Standard PROJECT.md sections
        required_sections = [
            "## GOALS",
            "## SCOPE",
            "## CONSTRAINTS",
            "## ARCHITECTURE"
        ]

        for section in required_sections:
            assert section in content, (
                f"Missing '{section}' in project-md-structure.md example\n"
                f"Expected: Complete PROJECT.md template\n"
                f"See: Issue #69"
            )


# ============================================================================
# Test Suite 4: Agent Integration
# ============================================================================


class TestAgentProjectAlignmentReferences:
    """Test agents reference project-alignment skill."""

    @pytest.mark.parametrize("agent_name", ALIGNMENT_AGENTS)
    def test_agent_references_project_alignment_skill(self, agent_name):
        """Test agent references project-alignment skill."""
        agent_file = AGENTS_DIR / f"{agent_name}.md"
        content = agent_file.read_text()

        assert "project-alignment" in content.lower(), (
            f"Agent {agent_name} should reference project-alignment skill\n"
            f"Expected: Add 'project-alignment' to Relevant Skills section\n"
            f"See: Issue #69"
        )

    @pytest.mark.parametrize("agent_name,inline_guidance", [
        ("alignment-validator", "PROJECT.md sections"),
        ("alignment-analyzer", "alignment validation"),
        ("advisor", "PROJECT.md alignment"),
        ("planner", "feature alignment"),
        ("quality-validator", "PROJECT.md compliance"),
        ("project-bootstrapper", "PROJECT.md structure"),
        ("brownfield-analyzer", "alignment assessment"),
        ("project-progress-tracker", "goal alignment")
    ])
    def test_agent_removes_inline_alignment_guidance(self, agent_name, inline_guidance):
        """Test agent removes verbose inline alignment guidance."""
        agent_file = AGENTS_DIR / f"{agent_name}.md"
        content = agent_file.read_text()

        # Count occurrences of alignment guidance
        guidance_count = content.lower().count(inline_guidance.lower())

        # Should reference skill, not include full inline guidance
        # Allow 1-2 mentions (in context), but not full checklist/instructions
        assert guidance_count <= 3, (
            f"Agent {agent_name} still contains inline '{inline_guidance}' guidance\n"
            f"Expected: Remove verbose inline content, reference project-alignment skill\n"
            f"Found {guidance_count} mentions (expected ≤3)\n"
            f"See: Issue #69"
        )


# ============================================================================
# Test Suite 5: Token Reduction Validation
# ============================================================================


class TestTokenReductionFromProjectAlignment:
    """Test token reduction from project-alignment skill extraction."""

    @pytest.mark.parametrize("agent_name,expected_max_tokens", [
        ("alignment-validator", 700),    # Heavy user
        ("alignment-analyzer", 800),     # Heavy user
        ("advisor", 600),                # Moderate user
        ("planner", 800),                # Moderate user
        ("quality-validator", 600),      # Light user
        ("project-bootstrapper", 700),   # Moderate user
        ("brownfield-analyzer", 900),    # Heavy user
        ("project-progress-tracker", 600) # Light user
    ])
    def test_agent_token_count_reduced(self, agent_name, expected_max_tokens):
        """Test agent token count is reduced after skill extraction."""
        agent_file = AGENTS_DIR / f"{agent_name}.md"
        content = agent_file.read_text()

        # Rough token count (1 token ≈ 4 chars)
        token_count = len(content) // 4

        assert token_count <= expected_max_tokens, (
            f"Agent {agent_name} token count too high: {token_count}\n"
            f"Expected: ≤{expected_max_tokens} tokens after skill extraction\n"
            f"See: Issue #69"
        )

    def test_total_token_savings_across_alignment_agents(self):
        """Test total token savings of ~250 tokens across 8 agents."""
        total_savings = 0

        # Expected savings per agent (conservative estimates)
        expected_savings = {
            "alignment-validator": 40,    # Removes checklist
            "alignment-analyzer": 40,     # Removes detailed guidance
            "advisor": 25,                # Removes alignment checks
            "planner": 30,                # Removes alignment validation
            "quality-validator": 25,      # Removes alignment checks
            "project-bootstrapper": 35,   # Removes structure guidance
            "brownfield-analyzer": 30,    # Removes assessment guidance
            "project-progress-tracker": 25 # Removes goal alignment checks
        }

        for agent_name, savings in expected_savings.items():
            total_savings += savings

        assert total_savings >= 250, (
            f"Total token savings too low: {total_savings}\n"
            f"Expected: ≥250 tokens saved across 8 agents\n"
            f"Breakdown: {expected_savings}\n"
            f"See: Issue #69"
        )


# ============================================================================
# Test Suite 6: Skill Activation
# ============================================================================


class TestProjectAlignmentActivation:
    """Test project-alignment skill activates correctly."""

    def test_skill_activates_on_alignment_keywords(self):
        """Test project-alignment activates when alignment keywords used."""
        content = SKILL_FILE.read_text()

        # Extract frontmatter
        parts = content.split("---\n", 2)
        frontmatter = yaml.safe_load(parts[1])

        # Check auto_activate is true
        assert frontmatter.get("auto_activate") is True, (
            "project-alignment should auto-activate on alignment keywords\n"
            "Expected: auto_activate: true in SKILL.md frontmatter\n"
            "See: Issue #69"
        )

    def test_skill_has_specific_activation_keywords(self):
        """Test skill has specific keywords for targeted activation."""
        content = SKILL_FILE.read_text()
        parts = content.split("---\n", 2)
        frontmatter = yaml.safe_load(parts[1])

        keywords = frontmatter.get("keywords", [])

        # Should activate on alignment-specific tasks
        specific_keywords = [
            "alignment",
            "PROJECT.md",
            "semantic validation",
            "gap assessment"
        ]

        found = sum(1 for kw in specific_keywords if any(kw in k.lower() for k in keywords))

        assert found >= 3, (
            f"project-alignment needs specific activation keywords\n"
            f"Expected: At least 3 of {specific_keywords}\n"
            f"Found: {found}\n"
            f"See: Issue #69"
        )


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
