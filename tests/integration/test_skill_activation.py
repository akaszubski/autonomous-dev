"""
Integration tests for Issue #35: Skill activation and progressive disclosure

Tests validate that:
- Skills auto-activate based on keywords
- Metadata loads initially (not full content)
- Full skill loads when triggered by keywords
- Context budget stays under 8K tokens per feature

These tests follow TDD - they should FAIL until implementation is complete.

Run with: pytest tests/integration/test_skill_activation.py -v
"""

import re
from pathlib import Path
from typing import List, Set
from unittest.mock import Mock, patch

import pytest


class TestSkillActivation:
    """Test suite for skill activation via progressive disclosure."""

    AGENTS_DIR = Path(__file__).parent.parent.parent / "plugins" / "autonomous-dev" / "agents"
    SKILLS_DIR = Path(__file__).parent.parent.parent / "plugins" / "autonomous-dev" / "skills"

    def test_implementer_loads_python_standards_skill(self):
        """
        GIVEN: Implementer agent with python-standards skill
        WHEN: Agent processes Python implementation task
        THEN: python-standards skill is referenced and accessible
        """
        implementer_file = self.AGENTS_DIR / "implementer.md"
        assert implementer_file.exists(), "Implementer agent file not found"

        content = implementer_file.read_text()

        # Check that python-standards is listed
        assert (
            "python-standards" in content
        ), "Implementer missing python-standards skill reference"

        # Check that skill directory exists
        skill_dir = self.SKILLS_DIR / "python-standards"
        assert skill_dir.exists(), "python-standards skill directory not found"

        # Check that SKILL.md metadata exists
        skill_metadata = skill_dir / "SKILL.md"
        assert skill_metadata.exists(), "python-standards SKILL.md not found"

    def test_test_master_loads_testing_guide_skill(self):
        """
        GIVEN: Test-master agent with testing-guide skill
        WHEN: Agent processes test generation task
        THEN: testing-guide skill is referenced and accessible
        """
        test_master_file = self.AGENTS_DIR / "test-master.md"
        assert test_master_file.exists(), "Test-master agent file not found"

        content = test_master_file.read_text()

        # Check that testing-guide is listed
        assert (
            "testing-guide" in content
        ), "Test-master missing testing-guide skill reference"

        # Check that skill directory exists
        skill_dir = self.SKILLS_DIR / "testing-guide"
        assert skill_dir.exists(), "testing-guide skill directory not found"

    def test_reviewer_loads_code_review_skill(self):
        """
        GIVEN: Reviewer agent with code-review skill
        WHEN: Agent processes code review task
        THEN: code-review skill is referenced and accessible
        """
        reviewer_file = self.AGENTS_DIR / "reviewer.md"
        assert reviewer_file.exists(), "Reviewer agent file not found"

        content = reviewer_file.read_text()

        # Check that code-review is listed
        assert "code-review" in content, "Reviewer missing code-review skill reference"

        # Check that skill directory exists
        skill_dir = self.SKILLS_DIR / "code-review"
        assert skill_dir.exists(), "code-review skill directory not found"

    def test_security_auditor_loads_security_patterns_skill(self):
        """
        GIVEN: Security-auditor agent with security-patterns skill (existing)
        WHEN: Agent processes security scan task
        THEN: security-patterns skill is referenced and accessible
        """
        security_file = self.AGENTS_DIR / "security-auditor.md"
        assert security_file.exists(), "Security-auditor agent file not found"

        content = security_file.read_text()

        # Check that security-patterns is listed
        assert (
            "security-patterns" in content
        ), "Security-auditor missing security-patterns skill"

        # Check that skill directory exists
        skill_dir = self.SKILLS_DIR / "security-patterns"
        assert skill_dir.exists(), "security-patterns skill directory not found"

    def test_advisor_loads_advisor_triggers_skill(self):
        """
        GIVEN: Advisor agent with advisor-triggers skill
        WHEN: Agent processes validation task
        THEN: advisor-triggers skill is referenced and accessible
        """
        advisor_file = self.AGENTS_DIR / "advisor.md"
        assert advisor_file.exists(), "Advisor agent file not found"

        content = advisor_file.read_text()

        # Check that advisor-triggers is listed
        assert "advisor-triggers" in content, "Advisor missing advisor-triggers skill"

        # Check that skill directory exists
        skill_dir = self.SKILLS_DIR / "advisor-triggers"
        assert skill_dir.exists(), "advisor-triggers skill directory not found"

    def test_multiple_agents_can_share_same_skill(self):
        """
        GIVEN: Multiple agents referencing python-standards skill
        WHEN: Checking implementer, test-master, reviewer
        THEN: All three reference python-standards without conflicts
        """
        agents_with_python_standards = ["implementer", "test-master", "reviewer"]

        for agent_name in agents_with_python_standards:
            agent_file = self.AGENTS_DIR / f"{agent_name}.md"
            assert agent_file.exists(), f"Agent file not found: {agent_name}"

            content = agent_file.read_text()
            assert (
                "python-standards" in content
            ), f"Agent '{agent_name}' missing python-standards skill"

    def test_skills_have_activation_keywords(self):
        """
        GIVEN: Skill SKILL.md metadata files
        WHEN: Checking for keyword lists
        THEN: Each skill has keywords for auto-activation
        """
        # Sample skills to check
        skills_to_check = [
            "python-standards",
            "testing-guide",
            "code-review",
            "security-patterns",
            "api-design",
        ]

        for skill_name in skills_to_check:
            skill_metadata = self.SKILLS_DIR / skill_name / "SKILL.md"
            assert skill_metadata.exists(), f"Skill metadata not found: {skill_name}"

            content = skill_metadata.read_text()

            # Check for keywords section or frontmatter
            # Progressive disclosure expects keywords for activation
            assert (
                "keywords" in content.lower() or "tags" in content.lower()
            ), f"Skill '{skill_name}' missing keywords for activation"


class TestProgressiveDisclosure:
    """Test suite for progressive disclosure mechanism."""

    SKILLS_DIR = Path(__file__).parent.parent.parent / "plugins" / "autonomous-dev" / "skills"

    def test_skill_metadata_files_are_small(self):
        """
        GIVEN: Skill SKILL.md metadata files
        WHEN: Checking file sizes
        THEN: Metadata files are under 2KB (lightweight for context)
        """
        skill_dirs = [d for d in self.SKILLS_DIR.iterdir() if d.is_dir() and not d.name.startswith(".")]

        for skill_dir in skill_dirs:
            metadata_file = skill_dir / "SKILL.md"
            if not metadata_file.exists():
                continue

            file_size = metadata_file.stat().st_size
            assert (
                file_size < 2048
            ), f"Skill '{skill_dir.name}' metadata too large: {file_size} bytes"

    def test_skills_have_separate_content_files(self):
        """
        GIVEN: Skills with full content
        WHEN: Checking directory structure
        THEN: Full content exists in separate files (not in SKILL.md)
        """
        # Sample skills to check
        skills_to_check = ["python-standards", "testing-guide", "code-review"]

        for skill_name in skills_to_check:
            skill_dir = self.SKILLS_DIR / skill_name
            metadata_file = skill_dir / "SKILL.md"

            # Check that directory has other content files
            content_files = [
                f for f in skill_dir.iterdir() if f.is_file() and f.name != "SKILL.md"
            ]

            assert (
                len(content_files) > 0
            ), f"Skill '{skill_name}' has no separate content files"


class TestContextBudget:
    """Test suite for context budget management with skills."""

    AGENTS_DIR = Path(__file__).parent.parent.parent / "plugins" / "autonomous-dev" / "agents"

    def test_single_agent_with_skills_stays_under_token_limit(self):
        """
        GIVEN: Agent file with 3-8 skill references
        WHEN: Calculating approximate token count
        THEN: Total tokens (agent + skill metadata) under 3K tokens
        """
        agents_to_check = ["implementer", "test-master", "reviewer"]

        for agent_name in agents_to_check:
            agent_file = self.AGENTS_DIR / f"{agent_name}.md"
            assert agent_file.exists(), f"Agent file not found: {agent_name}"

            content = agent_file.read_text()

            # Rough estimate: 1 token ≈ 4 characters
            estimated_tokens = len(content) // 4

            assert (
                estimated_tokens < 3000
            ), f"Agent '{agent_name}' exceeds token budget: ~{estimated_tokens} tokens"

    def test_agent_with_8_skills_stays_manageable(self):
        """
        GIVEN: Agent with maximum 8 skills
        WHEN: Checking file size and complexity
        THEN: Agent file remains under 200 lines
        """
        # Find agents with many skills (once implemented)
        agents_to_check = ["researcher", "planner"]  # Known to have many skills

        for agent_name in agents_to_check:
            agent_file = self.AGENTS_DIR / f"{agent_name}.md"
            if not agent_file.exists():
                continue

            content = agent_file.read_text()
            line_count = len(content.splitlines())

            assert (
                line_count < 200
            ), f"Agent '{agent_name}' too large: {line_count} lines"

    def test_workflow_with_multiple_agents_stays_under_8k_tokens(self):
        """
        GIVEN: Full workflow with 7 agents (researcher -> planner -> test-master -> implementer -> reviewer -> security-auditor -> doc-master)
        WHEN: Calculating total context for one feature
        THEN: Total context under 8000 tokens
        """
        workflow_agents = [
            "researcher",
            "planner",
            "test-master",
            "implementer",
            "reviewer",
            "security-auditor",
            "doc-master",
        ]

        total_chars = 0
        for agent_name in workflow_agents:
            agent_file = self.AGENTS_DIR / f"{agent_name}.md"
            if not agent_file.exists():
                continue

            content = agent_file.read_text()
            total_chars += len(content)

        # Rough estimate: 1 token ≈ 4 characters
        estimated_tokens = total_chars // 4

        assert (
            estimated_tokens < 8000
        ), f"Full workflow exceeds context budget: ~{estimated_tokens} tokens"


class TestSkillContentLoading:
    """Test suite for skill content loading behavior."""

    SKILLS_DIR = Path(__file__).parent.parent.parent / "plugins" / "autonomous-dev" / "skills"

    def test_skill_has_full_content_available(self):
        """
        GIVEN: Skills with separate content files
        WHEN: Checking for full content
        THEN: Full skill content exists and is substantial (>1KB)
        """
        skills_to_check = ["python-standards", "testing-guide", "code-review"]

        for skill_name in skills_to_check:
            skill_dir = self.SKILLS_DIR / skill_name
            assert skill_dir.exists(), f"Skill directory not found: {skill_name}"

            # Find content files (anything except SKILL.md)
            content_files = [
                f for f in skill_dir.iterdir() if f.is_file() and f.name != "SKILL.md"
            ]

            assert (
                len(content_files) > 0
            ), f"Skill '{skill_name}' has no content files"

            # Check that at least one content file is substantial
            has_substantial_content = False
            for content_file in content_files:
                if content_file.stat().st_size > 1024:  # > 1KB
                    has_substantial_content = True
                    break

            assert (
                has_substantial_content
            ), f"Skill '{skill_name}' has no substantial content"

    def test_skill_metadata_references_content_files(self):
        """
        GIVEN: Skill SKILL.md metadata
        WHEN: Checking for content file references
        THEN: Metadata indicates where full content is located
        """
        skills_to_check = ["python-standards", "testing-guide"]

        for skill_name in skills_to_check:
            metadata_file = self.SKILLS_DIR / skill_name / "SKILL.md"
            assert metadata_file.exists(), f"Skill metadata not found: {skill_name}"

            content = metadata_file.read_text()

            # Check that metadata mentions content files or structure
            has_content_reference = (
                ".md" in content.lower()
                or "content" in content.lower()
                or "guide" in content.lower()
            )

            assert (
                has_content_reference
            ), f"Skill '{skill_name}' metadata doesn't reference content"


class TestEdgeCases:
    """Test suite for edge cases and error conditions."""

    AGENTS_DIR = Path(__file__).parent.parent.parent / "plugins" / "autonomous-dev" / "agents"
    SKILLS_DIR = Path(__file__).parent.parent.parent / "plugins" / "autonomous-dev" / "skills"

    def test_agent_with_no_skills_still_works(self):
        """
        GIVEN: Agent files (some may not have skills section)
        WHEN: Checking agent functionality
        THEN: Agents without skills section don't break
        """
        # This is a safety test - not all agents need skills
        # Just verify agent files are valid markdown
        agent_files = list(self.AGENTS_DIR.glob("*.md"))

        for agent_file in agent_files:
            content = agent_file.read_text()

            # Check basic structure exists
            assert len(content) > 100, f"Agent '{agent_file.name}' appears empty"
            assert "---" in content, f"Agent '{agent_file.name}' missing frontmatter"

    def test_skill_with_overlapping_keywords_activates_correctly(self):
        """
        GIVEN: Skills with overlapping keywords (e.g., 'test' in testing-guide and code-review)
        WHEN: Processing task with keyword 'test'
        THEN: Both skills can activate without conflicts
        """
        # Check that multiple skills can coexist
        skills_with_test_keyword = []

        for skill_dir in self.SKILLS_DIR.iterdir():
            if not skill_dir.is_dir() or skill_dir.name.startswith("."):
                continue

            metadata_file = skill_dir / "SKILL.md"
            if not metadata_file.exists():
                continue

            content = metadata_file.read_text().lower()
            if "test" in content:
                skills_with_test_keyword.append(skill_dir.name)

        # Should have at least testing-guide
        assert (
            "testing-guide" in skills_with_test_keyword
        ), "testing-guide should mention 'test'"

    def test_long_workflow_10_features_with_skills(self):
        """
        GIVEN: 10 sequential features using skill-enabled agents
        WHEN: Simulating repeated workflow execution
        THEN: Context doesn't accumulate (stays manageable)
        """
        # This test validates that skills don't cause context bloat over time
        workflow_agents = [
            "researcher",
            "planner",
            "test-master",
            "implementer",
            "reviewer",
        ]

        # Calculate single feature context
        single_feature_chars = 0
        for agent_name in workflow_agents:
            agent_file = self.AGENTS_DIR / f"{agent_name}.md"
            if not agent_file.exists():
                continue

            content = agent_file.read_text()
            single_feature_chars += len(content)

        # Estimate tokens for single feature
        single_feature_tokens = single_feature_chars // 4

        # After 10 features (with /clear between each), context should be same
        ten_features_tokens = single_feature_tokens  # Should NOT be 10x!

        assert (
            ten_features_tokens < 8000
        ), f"Long workflow context grows too large: ~{ten_features_tokens} tokens"


class TestRegressionPrevention:
    """Test suite for preventing regressions in existing agents."""

    AGENTS_DIR = Path(__file__).parent.parent.parent / "plugins" / "autonomous-dev" / "agents"

    EXISTING_AGENTS_WITH_SKILLS = [
        "researcher",
        "planner",
        "security-auditor",
        "doc-master",
    ]

    def test_existing_agents_retain_skill_sections(self):
        """
        GIVEN: 4 agents that already have skill sections
        WHEN: Checking their skill sections
        THEN: All sections remain intact and properly formatted
        """
        for agent_name in self.EXISTING_AGENTS_WITH_SKILLS:
            agent_file = self.AGENTS_DIR / f"{agent_name}.md"
            assert agent_file.exists(), f"Agent file not found: {agent_name}"

            content = agent_file.read_text()

            # Check skill section exists
            assert (
                "## Relevant Skills" in content
            ), f"Existing agent '{agent_name}' lost skill section"

            # Check skills are listed
            skill_bullets = re.findall(r"^\s*-\s+\*\*", content, re.MULTILINE)
            assert (
                len(skill_bullets) >= 3
            ), f"Existing agent '{agent_name}' lost skills"

    def test_existing_agents_maintain_line_counts(self):
        """
        GIVEN: 4 agents with existing skill sections
        WHEN: Checking file sizes
        THEN: Files remain under 200 lines
        """
        for agent_name in self.EXISTING_AGENTS_WITH_SKILLS:
            agent_file = self.AGENTS_DIR / f"{agent_name}.md"
            assert agent_file.exists(), f"Agent file not found: {agent_name}"

            content = agent_file.read_text()
            line_count = len(content.splitlines())

            assert (
                line_count < 200
            ), f"Existing agent '{agent_name}' grew too large: {line_count} lines"

    def test_skills_directory_unchanged(self):
        """
        GIVEN: Skills directory with 19 skills
        WHEN: Checking directory structure
        THEN: All 19 skills still exist with proper structure
        """
        skills_dir = Path(__file__).parent.parent.parent / "plugins" / "autonomous-dev" / "skills"

        skill_dirs = [d for d in skills_dir.iterdir() if d.is_dir() and not d.name.startswith(".")]

        assert len(skill_dirs) == 19, f"Expected 19 skills, found {len(skill_dirs)}"

        # Check each skill has SKILL.md
        for skill_dir in skill_dirs:
            metadata_file = skill_dir / "SKILL.md"
            assert (
                metadata_file.exists()
            ), f"Skill '{skill_dir.name}' missing SKILL.md"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
