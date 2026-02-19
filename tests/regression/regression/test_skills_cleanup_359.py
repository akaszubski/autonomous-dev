"""Regression tests for skills cleanup refactoring (Issue #359).

Validates post-cleanup filesystem state: hollow shells removed, training skills
removed, skills archived/merged correctly, agent frontmatter updated.
"""

import re
from pathlib import Path

import pytest

# Resolve paths relative to repo root
WORKTREE = Path(__file__).resolve().parents[3]
PLUGINS_DIR = WORKTREE / "plugins" / "autonomous-dev"
SKILLS_DIR = PLUGINS_DIR / "skills"
ARCHIVED_SKILLS_DIR = SKILLS_DIR / "archived"
AGENTS_DIR = PLUGINS_DIR / "agents"
ARCHIVED_AGENTS_DIR = AGENTS_DIR / "archived"


class TestHollowShellsRemoved:
    """Hollow shell skill directories should not exist after cleanup."""

    HOLLOW_SHELLS = [
        "architecture-patterns",
        "code-review",
        "cross-reference-validation",
        "database-design",
        "documentation-currency",
        "documentation-guide",
        "file-organization",
        "project-management",
        "research-patterns",
        "project-alignment",
    ]

    @pytest.mark.parametrize("skill_name", HOLLOW_SHELLS)
    def test_hollow_shell_removed(self, skill_name: str) -> None:
        """Hollow shell directory '{skill_name}' should not exist in active skills."""
        skill_path = SKILLS_DIR / skill_name
        assert not skill_path.exists(), (
            f"Hollow shell skill still exists: {skill_path}\n"
            f"Should have been removed in Issue #359"
        )


class TestTrainingSkillsRemoved:
    """Training/realign skills should be removed (moved to different repo)."""

    TRAINING_SKILLS = [
        "anti-hallucination-training",
        "data-distillation",
        "dpo-rlvr-generation",
        "grpo-verifiable-training",
        "mlx-performance",
        "preference-data-quality",
        "realign-domain-workflows",
        "training-methods",
        "training-operations",
    ]

    @pytest.mark.parametrize("skill_name", TRAINING_SKILLS)
    def test_training_skill_removed(self, skill_name: str) -> None:
        """Training skill '{skill_name}' should not exist in active skills."""
        skill_path = SKILLS_DIR / skill_name
        assert not skill_path.exists(), (
            f"Training skill still exists: {skill_path}\n"
            f"Should have been moved to realign repo in Issue #359"
        )


class TestArchivedSkillsPresent:
    """Unused skills should be archived properly."""

    ARCHIVED_SKILLS = [
        "advisor-triggers",
        "agent-output-formats",
        "consistency-enforcement",
        "project-alignment-validation",
        "semantic-validation",
    ]

    @pytest.mark.parametrize("skill_name", ARCHIVED_SKILLS)
    def test_archived_skill_exists(self, skill_name: str) -> None:
        """Archived skill '{skill_name}' should exist in skills/archived/."""
        archived_path = ARCHIVED_SKILLS_DIR / skill_name
        assert archived_path.exists(), (
            f"Archived skill not found: {archived_path}\n"
            f"Should have been moved to archived/ in Issue #359"
        )


class TestTrainingAgentsArchived:
    """Training-related agents should be moved to agents/archived/."""

    ARCHIVED_AGENT_FILES = [
        "data-curator.md",
        "distributed-training-coordinator.md",
        "data-quality-validator.md",
    ]

    @pytest.mark.parametrize("agent_file", ARCHIVED_AGENT_FILES)
    def test_training_agent_archived(self, agent_file: str) -> None:
        """Training agent '{agent_file}' should be in agents/archived/."""
        archived_path = ARCHIVED_AGENTS_DIR / agent_file
        active_path = AGENTS_DIR / agent_file
        assert not active_path.exists(), (
            f"Training agent still in active directory: {active_path}"
        )
        assert archived_path.exists(), (
            f"Training agent not found in archived: {archived_path}"
        )

    def test_realign_curator_archived(self) -> None:
        """realign-curator directory should be in agents/archived/."""
        archived_path = ARCHIVED_AGENTS_DIR / "realign-curator"
        assert archived_path.exists(), (
            f"realign-curator not found in archived agents: {archived_path}"
        )


class TestMergedSkills:
    """Skills that were merged should exist in their new form."""

    def test_git_github_exists(self) -> None:
        """Merged git-github skill should exist with real content."""
        skill_file = SKILLS_DIR / "git-github" / "SKILL.md"
        assert skill_file.exists(), (
            f"Merged git-github skill not found: {skill_file}"
        )
        lines = skill_file.read_text().splitlines()
        assert len(lines) > 50, (
            f"git-github/SKILL.md has only {len(lines)} lines, expected >50 "
            f"(should contain merged content from git-workflow + github-workflow)"
        )

    def test_git_workflow_removed(self) -> None:
        """Old git-workflow skill should not exist separately."""
        assert not (SKILLS_DIR / "git-workflow").exists(), (
            "git-workflow should be merged into git-github"
        )

    def test_github_workflow_removed(self) -> None:
        """Old github-workflow skill should not exist separately."""
        assert not (SKILLS_DIR / "github-workflow").exists(), (
            "github-workflow should be merged into git-github"
        )

    def test_skill_integration_exists(self) -> None:
        """skill-integration should exist (absorbed skill-integration-templates)."""
        skill_file = SKILLS_DIR / "skill-integration" / "SKILL.md"
        assert skill_file.exists(), (
            f"skill-integration/SKILL.md not found: {skill_file}"
        )

    def test_skill_integration_templates_removed(self) -> None:
        """skill-integration-templates should not exist as separate skill."""
        assert not (SKILLS_DIR / "skill-integration-templates").exists(), (
            "skill-integration-templates should be merged into skill-integration"
        )

    def test_error_handling_patterns_removed(self) -> None:
        """error-handling-patterns should be merged into python-standards."""
        assert not (SKILLS_DIR / "error-handling-patterns").exists(), (
            "error-handling-patterns should be merged into python-standards"
        )


class TestAgentFrontmatterClean:
    """Active agent files should not reference deleted/archived skills."""

    DELETED_SKILLS = {
        "architecture-patterns",
        "code-review",
        "cross-reference-validation",
        "database-design",
        "documentation-currency",
        "documentation-guide",
        "file-organization",
        "project-management",
        "research-patterns",
        "project-alignment",
        "advisor-triggers",
        "agent-output-formats",
        "consistency-enforcement",
        "project-alignment-validation",
        "semantic-validation",
        "anti-hallucination-training",
        "data-distillation",
        "dpo-rlvr-generation",
        "grpo-verifiable-training",
        "mlx-performance",
        "preference-data-quality",
        "realign-domain-workflows",
        "training-methods",
        "training-operations",
        "git-workflow",
        "github-workflow",
        "skill-integration-templates",
        "error-handling-patterns",
    }

    def test_no_agent_references_deleted_skills(self) -> None:
        """No active agent should reference any deleted/archived skill."""
        agent_files = list(AGENTS_DIR.glob("*.md"))
        assert len(agent_files) >= 5, "Expected at least 5 active agent files"

        violations = []
        for agent_file in agent_files:
            content = agent_file.read_text()
            # Look for skills in frontmatter (between --- markers)
            frontmatter_match = re.match(r"^---\n(.*?)\n---", content, re.DOTALL)
            if not frontmatter_match:
                continue
            frontmatter = frontmatter_match.group(1)
            for deleted_skill in self.DELETED_SKILLS:
                if deleted_skill in frontmatter:
                    violations.append(
                        f"{agent_file.name} references deleted skill: {deleted_skill}"
                    )

        assert not violations, (
            f"Agents still reference deleted/archived skills:\n"
            + "\n".join(f"  - {v}" for v in violations)
        )


class TestSurvivingSkillsHaveContent:
    """Every active skill directory should have a SKILL.md file."""

    def test_all_active_skills_have_skill_md(self) -> None:
        """Every directory in skills/ (excluding archived/) should have SKILL.md."""
        skill_dirs = [
            d for d in SKILLS_DIR.iterdir()
            if d.is_dir() and d.name != "archived" and not d.name.startswith(".")
        ]
        assert len(skill_dirs) >= 10, (
            f"Expected at least 10 active skill directories, found {len(skill_dirs)}"
        )

        missing = [
            d.name for d in skill_dirs
            if not (d / "SKILL.md").exists()
        ]
        assert not missing, (
            f"Skills missing SKILL.md: {missing}"
        )


class TestExpectedSkillCount:
    """Active skill count should be in a reasonable range."""

    def test_active_skill_count_in_range(self) -> None:
        """Should have between 12 and 20 active skills (not archived)."""
        skill_dirs = [
            d for d in SKILLS_DIR.iterdir()
            if d.is_dir() and d.name != "archived" and not d.name.startswith(".")
        ]
        count = len(skill_dirs)
        assert 12 <= count <= 20, (
            f"Expected 12-20 active skills, found {count}. "
            f"Skills: {sorted(d.name for d in skill_dirs)}"
        )
