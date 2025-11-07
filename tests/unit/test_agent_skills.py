"""
Unit tests for Issue #35: Agents should actively use skills

Tests validate that all 13 agents have "Relevant Skills" sections added
following the pattern from researcher, planner, security-auditor, doc-master.

These tests follow TDD - they should FAIL until implementation is complete.

Run with: pytest tests/unit/test_agent_skills.py -v
"""

import re
from pathlib import Path
from typing import Dict, List

import pytest


class TestAgentSkillsSections:
    """Test suite for agent skill section validation."""

    # Base directory for agents
    AGENTS_DIR = Path(__file__).parent.parent.parent / "plugins" / "autonomous-dev" / "agents"

    # All 19 available skills
    AVAILABLE_SKILLS = [
        "api-design",
        "architecture-patterns",
        "code-review",
        "database-design",
        "testing-guide",
        "security-patterns",
        "git-workflow",
        "github-workflow",
        "project-management",
        "documentation-guide",
        "python-standards",
        "observability",
        "consistency-enforcement",
        "file-organization",
        "research-patterns",
        "semantic-validation",
        "cross-reference-validation",
        "documentation-currency",
        "advisor-triggers",
    ]

    # 13 agents that need skill sections added (per implementation plan)
    AGENTS_NEEDING_SKILLS = [
        "implementer",
        "test-master",
        "reviewer",
        "advisor",
        "quality-validator",
        "alignment-validator",
        "commit-message-generator",
        "pr-description-generator",
        "project-progress-tracker",
        "alignment-analyzer",
        "project-bootstrapper",
        "project-status-analyzer",
        "sync-validator",
    ]

    # Agents that already have skill sections (for regression testing)
    AGENTS_WITH_EXISTING_SKILLS = [
        "researcher",
        "planner",
        "security-auditor",
        "doc-master",
    ]

    # Expected skill mappings per agent (from implementation plan)
    EXPECTED_SKILL_MAPPINGS: Dict[str, List[str]] = {
        "implementer": [
            "python-standards",
            "api-design",
            "architecture-patterns",
            "code-review",
            "database-design",
        ],
        "test-master": [
            "testing-guide",
            "python-standards",
            "code-review",
            "security-patterns",
            "api-design",
        ],
        "reviewer": [
            "code-review",
            "python-standards",
            "testing-guide",
            "security-patterns",
            "architecture-patterns",
            "api-design",
        ],
        "advisor": [
            "advisor-triggers",
            "architecture-patterns",
            "security-patterns",
            "testing-guide",
            "code-review",
        ],
        "quality-validator": [
            "testing-guide",
            "code-review",
            "security-patterns",
            "consistency-enforcement",
        ],
        "alignment-validator": [
            "semantic-validation",
            "cross-reference-validation",
            "consistency-enforcement",
        ],
        "commit-message-generator": [
            "git-workflow",
            "semantic-validation",
            "consistency-enforcement",
        ],
        "pr-description-generator": [
            "github-workflow",
            "documentation-guide",
            "semantic-validation",
        ],
        "project-progress-tracker": [
            "project-management",
            "semantic-validation",
            "documentation-currency",
        ],
        "alignment-analyzer": [
            "semantic-validation",
            "cross-reference-validation",
            "project-management",
        ],
        "project-bootstrapper": [
            "architecture-patterns",
            "file-organization",
            "project-management",
        ],
        "project-status-analyzer": [
            "project-management",
            "semantic-validation",
            "observability",
        ],
        "sync-validator": [
            "consistency-enforcement",
            "file-organization",
            "semantic-validation",
        ],
    }

    def test_agents_directory_exists(self):
        """
        GIVEN: Plugin directory structure
        WHEN: Checking for agents directory
        THEN: Directory exists and contains agent files
        """
        assert self.AGENTS_DIR.exists(), f"Agents directory not found: {self.AGENTS_DIR}"
        assert self.AGENTS_DIR.is_dir(), f"Agents path is not a directory: {self.AGENTS_DIR}"

        # Verify at least 18 agent files exist
        agent_files = list(self.AGENTS_DIR.glob("*.md"))
        assert len(agent_files) >= 18, f"Expected at least 18 agents, found {len(agent_files)}"

    def test_all_target_agents_have_skill_sections(self):
        """
        GIVEN: 13 agents that need skill sections
        WHEN: Checking each agent file
        THEN: All agents have '## Relevant Skills' header
        """
        for agent_name in self.AGENTS_NEEDING_SKILLS:
            agent_file = self.AGENTS_DIR / f"{agent_name}.md"
            assert agent_file.exists(), f"Agent file not found: {agent_file}"

            content = agent_file.read_text()
            assert (
                "## Relevant Skills" in content
            ), f"Agent '{agent_name}' missing '## Relevant Skills' section"

    def test_each_agent_has_correct_skill_count(self):
        """
        GIVEN: Expected skill mappings for each agent
        WHEN: Checking skill bullet points in each agent
        THEN: Each agent has 3-8 skills listed (no more, no less)
        """
        for agent_name in self.AGENTS_NEEDING_SKILLS:
            agent_file = self.AGENTS_DIR / f"{agent_name}.md"
            content = agent_file.read_text()

            # Extract skills section
            match = re.search(r"## Relevant Skills(.*?)(?=\n##|\Z)", content, re.DOTALL)
            assert match, f"Agent '{agent_name}' has no Relevant Skills section"

            skills_section = match.group(1)

            # Count bullet points (skills are listed as "- **skill-name**: description")
            skill_bullets = re.findall(r"^\s*-\s+\*\*", skills_section, re.MULTILINE)
            skill_count = len(skill_bullets)

            assert (
                3 <= skill_count <= 8
            ), f"Agent '{agent_name}' has {skill_count} skills, expected 3-8"

    def test_referenced_skills_exist_in_filesystem(self):
        """
        GIVEN: Skills directory with 19 available skills
        WHEN: Checking skills referenced in agent files
        THEN: All referenced skill names match actual skill directories
        """
        skills_dir = self.AGENTS_DIR.parent / "skills"

        for agent_name in self.AGENTS_NEEDING_SKILLS:
            agent_file = self.AGENTS_DIR / f"{agent_name}.md"
            content = agent_file.read_text()

            # Extract skill names from bullet points (format: - **skill-name**: description)
            skill_names = re.findall(r"^\s*-\s+\*\*([a-z-]+)\*\*:", content, re.MULTILINE)

            for skill_name in skill_names:
                skill_dir = skills_dir / skill_name
                assert (
                    skill_dir.exists()
                ), f"Agent '{agent_name}' references non-existent skill '{skill_name}'"
                assert (
                    skill_name in self.AVAILABLE_SKILLS
                ), f"Agent '{agent_name}' references unknown skill '{skill_name}'"

    def test_skill_mappings_match_implementation_plan(self):
        """
        GIVEN: Expected skill mappings from implementation plan
        WHEN: Checking actual skills in each agent file
        THEN: Skills match the planned mappings exactly
        """
        for agent_name, expected_skills in self.EXPECTED_SKILL_MAPPINGS.items():
            agent_file = self.AGENTS_DIR / f"{agent_name}.md"
            content = agent_file.read_text()

            # Extract actual skill names
            actual_skills = re.findall(r"^\s*-\s+\*\*([a-z-]+)\*\*:", content, re.MULTILINE)

            # Check that all expected skills are present
            for expected_skill in expected_skills:
                assert (
                    expected_skill in actual_skills
                ), f"Agent '{agent_name}' missing expected skill '{expected_skill}'"

    def test_skill_section_placement(self):
        """
        GIVEN: Agent files with multiple sections
        WHEN: Checking placement of Relevant Skills section
        THEN: Section appears after Mission/Workflow but before final sections
        """
        for agent_name in self.AGENTS_NEEDING_SKILLS:
            agent_file = self.AGENTS_DIR / f"{agent_name}.md"
            content = agent_file.read_text()

            # Find section positions
            sections = re.findall(r"^## (.+)$", content, re.MULTILINE)

            assert "Relevant Skills" in sections, f"Agent '{agent_name}' missing skills section"

            # Skills should appear somewhere in middle, not first or last
            skills_index = sections.index("Relevant Skills")
            assert (
                0 < skills_index < len(sections) - 1
            ), f"Agent '{agent_name}' has skills section in wrong position"

    def test_agent_files_stay_under_200_lines(self):
        """
        GIVEN: Agent files with skill sections added
        WHEN: Counting total lines in each agent file
        THEN: Files remain under 200 lines (manageable size)
        """
        for agent_name in self.AGENTS_NEEDING_SKILLS:
            agent_file = self.AGENTS_DIR / f"{agent_name}.md"
            content = agent_file.read_text()

            line_count = len(content.splitlines())
            assert (
                line_count < 200
            ), f"Agent '{agent_name}' has {line_count} lines (exceeds 200 line limit)"

    def test_existing_agent_skills_unchanged(self):
        """
        GIVEN: 4 agents with existing skill sections
        WHEN: Checking their skill sections
        THEN: Existing sections remain intact (regression test)
        """
        for agent_name in self.AGENTS_WITH_EXISTING_SKILLS:
            agent_file = self.AGENTS_DIR / f"{agent_name}.md"
            assert agent_file.exists(), f"Agent file not found: {agent_file}"

            content = agent_file.read_text()
            assert (
                "## Relevant Skills" in content
            ), f"Existing agent '{agent_name}' lost its skill section"

            # Verify they still have skills listed
            skill_bullets = re.findall(r"^\s*-\s+\*\*", content, re.MULTILINE)
            assert (
                len(skill_bullets) >= 3
            ), f"Existing agent '{agent_name}' has too few skills"

    def test_skill_descriptions_are_meaningful(self):
        """
        GIVEN: Skills with descriptions after colons
        WHEN: Checking skill bullet points
        THEN: Each skill has a non-empty description
        """
        for agent_name in self.AGENTS_NEEDING_SKILLS:
            agent_file = self.AGENTS_DIR / f"{agent_name}.md"
            content = agent_file.read_text()

            # Extract skills section
            match = re.search(r"## Relevant Skills(.*?)(?=\n##|\Z)", content, re.DOTALL)
            if not match:
                continue  # Will fail in other test

            skills_section = match.group(1)

            # Check each skill line has description
            skill_lines = re.findall(
                r"^\s*-\s+\*\*([a-z-]+)\*\*:\s*(.+)$", skills_section, re.MULTILINE
            )

            for skill_name, description in skill_lines:
                assert (
                    len(description.strip()) > 10
                ), f"Agent '{agent_name}' skill '{skill_name}' has insufficient description"

    def test_no_duplicate_skills_in_agent(self):
        """
        GIVEN: Skills listed in agent files
        WHEN: Checking for duplicate skill references
        THEN: Each skill appears only once per agent
        """
        for agent_name in self.AGENTS_NEEDING_SKILLS:
            agent_file = self.AGENTS_DIR / f"{agent_name}.md"
            content = agent_file.read_text()

            # Extract skill names
            skill_names = re.findall(r"^\s*-\s+\*\*([a-z-]+)\*\*:", content, re.MULTILINE)

            # Check for duplicates
            seen = set()
            for skill_name in skill_names:
                assert (
                    skill_name not in seen
                ), f"Agent '{agent_name}' has duplicate skill '{skill_name}'"
                seen.add(skill_name)


class TestSkillFormatting:
    """Test suite for skill section formatting standards."""

    AGENTS_DIR = Path(__file__).parent.parent.parent / "plugins" / "autonomous-dev" / "agents"

    AGENTS_TO_TEST = [
        "implementer",
        "test-master",
        "reviewer",
        "advisor",
        "quality-validator",
        "alignment-validator",
        "commit-message-generator",
        "pr-description-generator",
        "project-progress-tracker",
        "alignment-analyzer",
        "project-bootstrapper",
        "project-status-analyzer",
        "sync-validator",
    ]

    def test_skill_section_has_intro_text(self):
        """
        GIVEN: Agent with Relevant Skills section
        WHEN: Checking section content
        THEN: Section starts with intro text before listing skills
        """
        for agent_name in self.AGENTS_TO_TEST:
            agent_file = self.AGENTS_DIR / f"{agent_name}.md"
            content = agent_file.read_text()

            # Extract skills section
            match = re.search(r"## Relevant Skills(.*?)(?=\n##|\Z)", content, re.DOTALL)
            if not match:
                pytest.fail(f"Agent '{agent_name}' missing skills section")

            skills_section = match.group(1)

            # Check for intro text (should have text before first bullet)
            first_bullet_pos = skills_section.find("-")
            if first_bullet_pos > 0:
                intro_text = skills_section[:first_bullet_pos].strip()
                assert (
                    len(intro_text) > 20
                ), f"Agent '{agent_name}' needs intro text before skills list"

    def test_skill_bullet_formatting_consistent(self):
        """
        GIVEN: Skills listed in bullet points
        WHEN: Checking formatting pattern
        THEN: All bullets follow format: '- **skill-name**: Description'
        """
        pattern = re.compile(r"^\s*-\s+\*\*[a-z-]+\*\*:\s+.+$", re.MULTILINE)

        for agent_name in self.AGENTS_TO_TEST:
            agent_file = self.AGENTS_DIR / f"{agent_name}.md"
            content = agent_file.read_text()

            # Extract skills section
            match = re.search(r"## Relevant Skills(.*?)(?=\n##|\Z)", content, re.DOTALL)
            if not match:
                continue

            skills_section = match.group(1)

            # Find all bullet points
            bullets = re.findall(r"^\s*-\s+.+$", skills_section, re.MULTILINE)

            for bullet in bullets:
                assert pattern.match(
                    bullet
                ), f"Agent '{agent_name}' has incorrectly formatted skill bullet: {bullet}"

    def test_skill_names_use_kebab_case(self):
        """
        GIVEN: Skill names in agent files
        WHEN: Checking naming convention
        THEN: All skill names use kebab-case (lowercase-with-hyphens)
        """
        for agent_name in self.AGENTS_TO_TEST:
            agent_file = self.AGENTS_DIR / f"{agent_name}.md"
            content = agent_file.read_text()

            # Extract skill names
            skill_names = re.findall(r"^\s*-\s+\*\*([a-z-]+)\*\*:", content, re.MULTILINE)

            for skill_name in skill_names:
                # Check kebab-case: lowercase letters and hyphens only
                assert re.match(
                    r"^[a-z]+(-[a-z]+)*$", skill_name
                ), f"Agent '{agent_name}' skill '{skill_name}' not in kebab-case"


class TestSkillsDirectoryStructure:
    """Test suite for skills directory structure validation."""

    SKILLS_DIR = Path(__file__).parent.parent.parent / "plugins" / "autonomous-dev" / "skills"

    def test_all_19_skills_exist(self):
        """
        GIVEN: Skills directory
        WHEN: Counting skill subdirectories
        THEN: Exactly 19 skill directories exist
        """
        assert self.SKILLS_DIR.exists(), f"Skills directory not found: {self.SKILLS_DIR}"

        skill_dirs = [d for d in self.SKILLS_DIR.iterdir() if d.is_dir() and not d.name.startswith(".")]
        assert len(skill_dirs) == 19, f"Expected 19 skills, found {len(skill_dirs)}"

    def test_each_skill_has_metadata_file(self):
        """
        GIVEN: 19 skill directories
        WHEN: Checking each directory contents
        THEN: Each has a SKILL.md metadata file
        """
        skill_dirs = [d for d in self.SKILLS_DIR.iterdir() if d.is_dir() and not d.name.startswith(".")]

        for skill_dir in skill_dirs:
            metadata_file = skill_dir / "SKILL.md"
            assert (
                metadata_file.exists()
            ), f"Skill '{skill_dir.name}' missing SKILL.md metadata file"

    def test_skill_names_match_directory_names(self):
        """
        GIVEN: Skill directories and agent references
        WHEN: Cross-checking names
        THEN: All referenced skills have matching directories
        """
        available_skills = [
            "api-design",
            "architecture-patterns",
            "code-review",
            "database-design",
            "testing-guide",
            "security-patterns",
            "git-workflow",
            "github-workflow",
            "project-management",
            "documentation-guide",
            "python-standards",
            "observability",
            "consistency-enforcement",
            "file-organization",
            "research-patterns",
            "semantic-validation",
            "cross-reference-validation",
            "documentation-currency",
            "advisor-triggers",
        ]

        skill_dirs = [d.name for d in self.SKILLS_DIR.iterdir() if d.is_dir() and not d.name.startswith(".")]

        for skill_name in available_skills:
            assert skill_name in skill_dirs, f"Expected skill directory '{skill_name}' not found"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
