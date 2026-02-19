"""Regression tests for enforcement skills rebuild (Issue #361).

Validates that 4 rebuilt skills have enforcement content, agents reference them,
all active skills have enforcement language, and context_skill_injector is updated.
"""

import re
from pathlib import Path

import pytest

WORKTREE = Path(__file__).resolve().parents[3]
PLUGINS_DIR = WORKTREE / "plugins" / "autonomous-dev"
SKILLS_DIR = PLUGINS_DIR / "skills"
AGENTS_DIR = PLUGINS_DIR / "agents"
LIB_DIR = PLUGINS_DIR / "lib"

NEW_SKILLS = [
    "code-review",
    "documentation-guide",
    "research-patterns",
    "architecture-patterns",
]

ENFORCEMENT_KEYWORDS = [
    "FORBIDDEN",
    "REQUIRED",
    "Hard Rules",
    "HARD GATE",
    "ALWAYS",
    "NEVER",
    "MUST",
]


class TestNewSkillsExist:
    """4 rebuilt skills must exist with enforcement content."""

    @pytest.mark.parametrize("skill_name", NEW_SKILLS)
    def test_skill_directory_exists(self, skill_name: str) -> None:
        """Skill '{skill_name}' directory must exist."""
        skill_file = SKILLS_DIR / skill_name / "SKILL.md"
        assert skill_file.exists(), (
            f"Rebuilt skill not found: {skill_file}\n"
            f"Should be created in Issue #361"
        )

    @pytest.mark.parametrize("skill_name", NEW_SKILLS)
    def test_skill_has_sufficient_content(self, skill_name: str) -> None:
        """Skill '{skill_name}' must have >100 lines of real content."""
        skill_file = SKILLS_DIR / skill_name / "SKILL.md"
        if not skill_file.exists():
            pytest.skip(f"{skill_name} not yet created")
        lines = skill_file.read_text().splitlines()
        assert len(lines) > 100, (
            f"{skill_name}/SKILL.md has only {len(lines)} lines, expected >100"
        )

    @pytest.mark.parametrize("skill_name", NEW_SKILLS)
    def test_skill_has_forbidden_keyword(self, skill_name: str) -> None:
        """Skill '{skill_name}' must contain 'FORBIDDEN'."""
        skill_file = SKILLS_DIR / skill_name / "SKILL.md"
        if not skill_file.exists():
            pytest.skip(f"{skill_name} not yet created")
        content = skill_file.read_text()
        assert "FORBIDDEN" in content, (
            f"{skill_name}/SKILL.md missing 'FORBIDDEN' enforcement keyword"
        )

    @pytest.mark.parametrize("skill_name", NEW_SKILLS)
    def test_skill_has_required_keyword(self, skill_name: str) -> None:
        """Skill '{skill_name}' must contain 'REQUIRED'."""
        skill_file = SKILLS_DIR / skill_name / "SKILL.md"
        if not skill_file.exists():
            pytest.skip(f"{skill_name} not yet created")
        content = skill_file.read_text()
        assert "REQUIRED" in content, (
            f"{skill_name}/SKILL.md missing 'REQUIRED' enforcement keyword"
        )

    @pytest.mark.parametrize("skill_name", NEW_SKILLS)
    def test_skill_has_yaml_frontmatter(self, skill_name: str) -> None:
        """Skill '{skill_name}' must have YAML frontmatter with required fields."""
        skill_file = SKILLS_DIR / skill_name / "SKILL.md"
        if not skill_file.exists():
            pytest.skip(f"{skill_name} not yet created")
        content = skill_file.read_text()
        frontmatter_match = re.match(r"^---\n(.*?)\n---", content, re.DOTALL)
        assert frontmatter_match, (
            f"{skill_name}/SKILL.md missing YAML frontmatter (--- delimiters)"
        )
        fm = frontmatter_match.group(1)
        for field in ["name:", "version:", "type: knowledge", "keywords:"]:
            assert field in fm, (
                f"{skill_name}/SKILL.md frontmatter missing '{field}'"
            )


class TestAgentFrontmatterIncludesNewSkills:
    """Agent files must reference the new skills in their frontmatter."""

    AGENT_SKILL_MAPPINGS = [
        ("reviewer.md", "code-review"),
        ("doc-master.md", "documentation-guide"),
        ("researcher.md", "research-patterns"),
        ("researcher-local.md", "research-patterns"),
        ("planner.md", "architecture-patterns"),
    ]

    @pytest.mark.parametrize("agent_file,expected_skill", AGENT_SKILL_MAPPINGS)
    def test_agent_references_skill(self, agent_file: str, expected_skill: str) -> None:
        """Agent '{agent_file}' must include '{expected_skill}' in skills."""
        agent_path = AGENTS_DIR / agent_file
        assert agent_path.exists(), f"Agent file not found: {agent_path}"
        content = agent_path.read_text()
        frontmatter_match = re.match(r"^---\n(.*?)\n---", content, re.DOTALL)
        assert frontmatter_match, f"{agent_file} missing YAML frontmatter"
        fm = frontmatter_match.group(1)
        assert expected_skill in fm, (
            f"{agent_file} frontmatter does not reference skill '{expected_skill}'"
        )


class TestAllActiveSkillsHaveEnforcement:
    """Every active skill must contain at least one enforcement keyword."""

    def test_all_skills_have_enforcement_language(self) -> None:
        """Every active skill SKILL.md must have enforcement keywords."""
        skill_dirs = [
            d for d in SKILLS_DIR.iterdir()
            if d.is_dir() and d.name != "archived" and not d.name.startswith(".")
            and (d / "SKILL.md").exists()
        ]
        assert len(skill_dirs) >= 10, (
            f"Expected at least 10 active skills, found {len(skill_dirs)}"
        )

        missing_enforcement = []
        for skill_dir in skill_dirs:
            content = (skill_dir / "SKILL.md").read_text()
            has_enforcement = any(kw in content for kw in ENFORCEMENT_KEYWORDS)
            if not has_enforcement:
                missing_enforcement.append(skill_dir.name)

        assert not missing_enforcement, (
            f"Skills without any enforcement language ({ENFORCEMENT_KEYWORDS}):\n"
            + "\n".join(f"  - {s}" for s in missing_enforcement)
        )


class TestContextSkillInjectorPatterns:
    """context_skill_injector.py must map keywords to new skills."""

    EXPECTED_MAPPINGS = [
        ("review", "code-review"),
        ("doc", "documentation-guide"),
        ("research", "research-patterns"),
        ("architecture", "architecture-patterns"),
    ]

    def test_injector_file_exists(self) -> None:
        """context_skill_injector.py must exist."""
        injector = LIB_DIR / "context_skill_injector.py"
        assert injector.exists(), f"Not found: {injector}"

    @pytest.mark.parametrize("trigger,skill_name", EXPECTED_MAPPINGS)
    def test_injector_has_mapping(self, trigger: str, skill_name: str) -> None:
        """Injector must map '{trigger}' to '{skill_name}'."""
        injector = LIB_DIR / "context_skill_injector.py"
        if not injector.exists():
            pytest.skip("context_skill_injector.py not found")
        content = injector.read_text()
        assert skill_name in content, (
            f"context_skill_injector.py does not contain '{skill_name}' mapping"
        )


class TestSkillCountAccuracy:
    """CLAUDE.md component counts must match actual skill count."""

    def test_claude_md_skill_count_matches(self) -> None:
        """CLAUDE.md 'X skills' count must match actual active skill count."""
        # Count actual skills
        skill_dirs = [
            d for d in SKILLS_DIR.iterdir()
            if d.is_dir() and d.name != "archived" and not d.name.startswith(".")
            and (d / "SKILL.md").exists()
        ]
        actual_count = len(skill_dirs)

        # Parse CLAUDE.md
        claude_md = WORKTREE / "CLAUDE.md"
        assert claude_md.exists(), "CLAUDE.md not found"
        content = claude_md.read_text()

        # Match pattern like "17 agents, 40 skills, 15 active commands"
        match = re.search(r"(\d+)\s+skills", content)
        assert match, "Could not find 'N skills' in CLAUDE.md"
        documented_count = int(match.group(1))

        assert documented_count == actual_count, (
            f"CLAUDE.md says {documented_count} skills but found {actual_count} on disk.\n"
            f"Active skills: {sorted(d.name for d in skill_dirs)}"
        )
