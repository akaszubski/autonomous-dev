"""
Retroactive tests for existing skills that were added without tests.

Tests for: architecture-patterns, code-review, git-workflow, project-management
"""

from pathlib import Path

import pytest


class TestArchitecturePatternsSkill:
    """Validate architecture-patterns skill."""

    @pytest.fixture
    def skill_content(self):
        skill_path = Path(__file__).parent.parent.parent / "skills" / "architecture-patterns" / "SKILL.md"
        return skill_path.read_text()

    def test_exists(self):
        """Test architecture-patterns skill file exists."""
        skill_path = Path(__file__).parent.parent.parent / "skills" / "architecture-patterns" / "SKILL.md"
        assert skill_path.exists(), "architecture-patterns/SKILL.md not found"

    def test_has_frontmatter(self, skill_content):
        """Test architecture-patterns has YAML frontmatter."""
        assert skill_content.startswith("---"), "Missing frontmatter start"
        assert "name: architecture-patterns" in skill_content, "Missing name field"
        assert "description:" in skill_content, "Missing description field"
        assert "keywords:" in skill_content, "Missing keywords field"

    def test_has_required_keywords(self, skill_content):
        """Test architecture-patterns has relevant keywords."""
        required_keywords = [
            "architecture",
            "pattern",
            "design",
        ]

        for keyword in required_keywords:
            assert keyword in skill_content.lower(), f"Missing keyword: {keyword}"

    def test_covers_design_patterns(self, skill_content):
        """Test architecture-patterns covers common design patterns."""
        pattern_topics = [
            "solid",
            "singleton",
            "factory",
            "observer",
            "strategy",
        ]

        # Should cover at least 3 of these patterns
        pattern_count = sum(1 for pattern in pattern_topics if pattern.lower() in skill_content.lower())
        assert pattern_count >= 3, f"Should cover common design patterns (found {pattern_count}/5)"

    def test_has_code_examples(self, skill_content):
        """Test architecture-patterns includes code examples."""
        assert "```python" in skill_content, "Missing Python code examples"

    def test_has_substantial_content(self, skill_content):
        """Test architecture-patterns has substantial content."""
        line_count = len(skill_content.splitlines())
        assert line_count > 300, f"Content too short: {line_count} lines"


class TestCodeReviewSkill:
    """Validate code-review skill."""

    @pytest.fixture
    def skill_content(self):
        skill_path = Path(__file__).parent.parent.parent / "skills" / "code-review" / "SKILL.md"
        return skill_path.read_text()

    def test_exists(self):
        """Test code-review skill file exists."""
        skill_path = Path(__file__).parent.parent.parent / "skills" / "code-review" / "SKILL.md"
        assert skill_path.exists(), "code-review/SKILL.md not found"

    def test_has_frontmatter(self, skill_content):
        """Test code-review has YAML frontmatter."""
        assert skill_content.startswith("---"), "Missing frontmatter start"
        assert "name: code-review" in skill_content, "Missing name field"
        assert "description:" in skill_content, "Missing description field"
        assert "keywords:" in skill_content, "Missing keywords field"

    def test_has_required_keywords(self, skill_content):
        """Test code-review has relevant keywords."""
        required_keywords = [
            "review",
            "code",
            "feedback",
        ]

        for keyword in required_keywords:
            assert keyword in skill_content.lower(), f"Missing keyword: {keyword}"

    def test_covers_review_practices(self, skill_content):
        """Test code-review covers review best practices."""
        review_topics = [
            "review",
            "feedback",
            "pull request",
            "pr",
            "comment",
        ]

        for topic in review_topics:
            assert topic.lower() in skill_content.lower(), f"Missing review topic: {topic}"

    def test_covers_constructive_feedback(self, skill_content):
        """Test code-review emphasizes constructive feedback."""
        feedback_concepts = [
            "constructive",
            "helpful",
            "specific",
            "actionable",
        ]

        # Should mention at least 2 of these
        concept_count = sum(1 for concept in feedback_concepts if concept.lower() in skill_content.lower())
        assert concept_count >= 2, f"Should emphasize constructive feedback (found {concept_count}/4)"

    def test_has_examples(self, skill_content):
        """Test code-review includes review examples."""
        # Should show good vs bad examples
        has_indicators = ("✅" in skill_content and "❌" in skill_content) or \
                       ("GOOD" in skill_content.upper() and "BAD" in skill_content.upper())

        assert has_indicators, "Should show good vs bad review examples"

    def test_has_substantial_content(self, skill_content):
        """Test code-review has substantial content."""
        line_count = len(skill_content.splitlines())
        assert line_count > 200, f"Content too short: {line_count} lines"


class TestGitWorkflowSkill:
    """Validate git-workflow skill."""

    @pytest.fixture
    def skill_content(self):
        skill_path = Path(__file__).parent.parent.parent / "skills" / "git-workflow" / "SKILL.md"
        return skill_path.read_text()

    def test_exists(self):
        """Test git-workflow skill file exists."""
        skill_path = Path(__file__).parent.parent.parent / "skills" / "git-workflow" / "SKILL.md"
        assert skill_path.exists(), "git-workflow/SKILL.md not found"

    def test_has_frontmatter(self, skill_content):
        """Test git-workflow has YAML frontmatter."""
        assert skill_content.startswith("---"), "Missing frontmatter start"
        assert "name: git-workflow" in skill_content, "Missing name field"
        assert "description:" in skill_content, "Missing description field"
        assert "keywords:" in skill_content, "Missing keywords field"

    def test_has_required_keywords(self, skill_content):
        """Test git-workflow has relevant keywords."""
        required_keywords = [
            "git",
            "commit",
            "branch",
        ]

        for keyword in required_keywords:
            assert keyword in skill_content.lower(), f"Missing keyword: {keyword}"

    def test_covers_git_basics(self, skill_content):
        """Test git-workflow covers git fundamentals."""
        git_topics = [
            "commit",
            "branch",
            "merge",
            "pull request",
            "rebase",
        ]

        for topic in git_topics:
            assert topic.lower() in skill_content.lower(), f"Missing git topic: {topic}"

    def test_covers_commit_messages(self, skill_content):
        """Test git-workflow covers commit message conventions."""
        commit_concepts = [
            "commit message",
            "conventional commits",
            "semantic",
        ]

        # Should mention commit message standards
        commit_count = sum(1 for concept in commit_concepts if concept.lower() in skill_content.lower())
        assert commit_count >= 1, "Should cover commit message conventions"

    def test_covers_branching_strategies(self, skill_content):
        """Test git-workflow covers branching strategies."""
        branching_topics = [
            "branch",
            "main",
            "feature",
            "develop",
        ]

        for topic in branching_topics:
            assert topic.lower() in skill_content.lower(), f"Missing branching topic: {topic}"

    def test_has_git_commands(self, skill_content):
        """Test git-workflow includes git command examples."""
        git_commands = [
            "git commit",
            "git branch",
            "git merge",
        ]

        # Should show at least 2 git commands
        command_count = sum(1 for cmd in git_commands if cmd in skill_content.lower())
        assert command_count >= 2, f"Should show git command examples (found {command_count}/3)"

    def test_has_substantial_content(self, skill_content):
        """Test git-workflow has substantial content."""
        line_count = len(skill_content.splitlines())
        assert line_count > 200, f"Content too short: {line_count} lines"


class TestProjectManagementSkill:
    """Validate project-management skill."""

    @pytest.fixture
    def skill_content(self):
        skill_path = Path(__file__).parent.parent.parent / "skills" / "project-management" / "SKILL.md"
        return skill_path.read_text()

    def test_exists(self):
        """Test project-management skill file exists."""
        skill_path = Path(__file__).parent.parent.parent / "skills" / "project-management" / "SKILL.md"
        assert skill_path.exists(), "project-management/SKILL.md not found"

    def test_has_frontmatter(self, skill_content):
        """Test project-management has YAML frontmatter."""
        assert skill_content.startswith("---"), "Missing frontmatter start"
        assert "name: project-management" in skill_content, "Missing name field"
        assert "description:" in skill_content, "Missing description field"
        assert "keywords:" in skill_content, "Missing keywords field"

    def test_has_required_keywords(self, skill_content):
        """Test project-management has relevant keywords."""
        required_keywords = [
            "project",
            "sprint",
            "roadmap",
        ]

        # Should have at least 2 of these
        keyword_count = sum(1 for keyword in required_keywords if keyword in skill_content.lower())
        assert keyword_count >= 2, f"Missing project management keywords (found {keyword_count}/3)"

    def test_covers_project_md(self, skill_content):
        """Test project-management covers PROJECT.md (plugin's core concept)."""
        assert "project.md" in skill_content.lower(), "Should reference PROJECT.md"

    def test_covers_planning_concepts(self, skill_content):
        """Test project-management covers planning concepts."""
        planning_topics = [
            "goal",
            "scope",
            "requirement",
            "milestone",
        ]

        # Should mention at least 3 planning concepts
        planning_count = sum(1 for topic in planning_topics if topic.lower() in skill_content.lower())
        assert planning_count >= 3, f"Should cover planning concepts (found {planning_count}/4)"

    def test_covers_agile_or_workflow(self, skill_content):
        """Test project-management covers agile or workflow concepts."""
        workflow_concepts = [
            "agile",
            "sprint",
            "iteration",
            "backlog",
            "kanban",
            "workflow",
        ]

        # Should mention at least 2 workflow concepts
        workflow_count = sum(1 for concept in workflow_concepts if concept.lower() in skill_content.lower())
        assert workflow_count >= 2, f"Should cover workflow concepts (found {workflow_count}/6)"

    def test_has_substantial_content(self, skill_content):
        """Test project-management has substantial content."""
        line_count = len(skill_content.splitlines())
        assert line_count > 200, f"Content too short: {line_count} lines"


class TestAllExistingSkillsConsistency:
    """Test consistency across all existing skills."""

    @pytest.fixture
    def skills_dir(self):
        return Path(__file__).parent.parent.parent / "skills"

    def test_all_existing_skills_have_skill_md(self, skills_dir):
        """Test all skill directories have SKILL.md file."""
        existing_skills = [
            "architecture-patterns",
            "code-review",
            "git-workflow",
            "project-management",
        ]

        for skill in existing_skills:
            skill_file = skills_dir / skill / "SKILL.md"
            assert skill_file.exists(), f"SKILL.md not found for {skill}"

    def test_existing_skills_follow_structure(self, skills_dir):
        """Test existing skills follow proper structure."""
        existing_skills = [
            "architecture-patterns",
            "code-review",
            "git-workflow",
            "project-management",
        ]

        for skill in existing_skills:
            skill_file = skills_dir / skill / "SKILL.md"
            content = skill_file.read_text()

            # Check frontmatter
            assert content.startswith("---"), f"{skill}: Missing frontmatter"

            # Check required fields
            assert f"name: {skill}" in content, f"{skill}: Missing name field"
            assert "description:" in content, f"{skill}: Missing description"
            assert "keywords:" in content, f"{skill}: Missing keywords"

    def test_existing_skills_are_not_stubs(self, skills_dir):
        """Test existing skills have substantial content (not placeholder stubs)."""
        existing_skills = [
            "architecture-patterns",
            "code-review",
            "git-workflow",
            "project-management",
        ]

        for skill in existing_skills:
            skill_file = skills_dir / skill / "SKILL.md"
            content = skill_file.read_text()

            line_count = len(content.splitlines())
            assert line_count > 100, f"{skill}: Too short ({line_count} lines), appears to be a stub"

    def test_existing_skills_have_when_activates_section(self, skills_dir):
        """Test existing skills document when they activate."""
        existing_skills = [
            "architecture-patterns",
            "code-review",
            "git-workflow",
            "project-management",
        ]

        for skill in existing_skills:
            skill_file = skills_dir / skill / "SKILL.md"
            content = skill_file.read_text()

            # Should document activation conditions
            has_activation_docs = "when" in content.lower() and (
                "activate" in content.lower() or
                "use" in content.lower() or
                "trigger" in content.lower()
            )

            assert has_activation_docs, f"{skill}: Should document activation conditions"
