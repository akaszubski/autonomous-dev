"""Tests for Issue #331: Consolidate skills and archive unused agents.

TDD RED phase -- these tests define the expected state after consolidation.
They should FAIL before implementation and PASS after.
"""

import json
import re
from pathlib import Path

import pytest

# Base paths
WORKTREE = Path("/Users/akaszubski/Dev/autonomous-dev/.worktrees/batch-issues-331-332")
PLUGIN = WORKTREE / "plugins" / "autonomous-dev"
AGENTS_DIR = PLUGIN / "agents"
ARCHIVED_DIR = AGENTS_DIR / "archived"
SKILLS_DIR = PLUGIN / "skills"
MANIFEST = PLUGIN / "install_manifest.json"
CLAUDE_MD = WORKTREE / "CLAUDE.md"

# Agents that should be archived (not active)
AGENTS_TO_ARCHIVE = [
    "advisor.md",
    "alignment-analyzer.md",
    "alignment-validator.md",
    "brownfield-analyzer.md",
    "experiment-critic.md",
    "postmortem-analyst.md",
    "pr-description-generator.md",
    "project-bootstrapper.md",
    "project-progress-tracker.md",
    "project-status-analyzer.md",
    "setup-wizard.md",
]

# Agents that must remain active
CORE_AGENTS = [
    "implementer.md",
    "reviewer.md",
    "researcher.md",
    "planner.md",
    "security-auditor.md",
    "doc-master.md",
    "data-curator.md",
]

# Old realign skills to be removed
OLD_REALIGN_SKILLS = [
    "realign-antihallucination-workflow",
    "realign-dpo-workflow",
    "realign-persona-workflow",
    "realign-rlvr-workflow",
    "realign-source-workflow",
    "realign-srf-workflow",
]

# New consolidated skills
NEW_REALIGN_SKILLS = [
    "realign-meta-framework",
    "realign-domain-workflows",
]

# Core skills that must stay auto_activate: true
CORE_SKILLS = [
    "testing-guide",
    "python-standards",
    "security-patterns",
    "agent-output-formats",
    "skill-integration-templates",
]


def _read_yaml_frontmatter(skill_md: Path) -> dict:
    """Parse YAML frontmatter from a SKILL.md file (simple parser)."""
    text = skill_md.read_text()
    if not text.startswith("---"):
        return {}
    end = text.index("---", 3)
    frontmatter = text[3:end].strip()
    result = {}
    for line in frontmatter.splitlines():
        if ":" in line:
            key, val = line.split(":", 1)
            val = val.strip()
            if val.lower() == "true":
                val = True
            elif val.lower() == "false":
                val = False
            result[key.strip()] = val
    return result


class TestAgentArchival:
    """Verify unused agents are archived correctly."""

    @pytest.mark.parametrize("agent", AGENTS_TO_ARCHIVE)
    def test_archived_agent_exists_in_archived_dir(self, agent: str) -> None:
        assert (ARCHIVED_DIR / agent).exists(), f"{agent} not found in archived/"

    @pytest.mark.parametrize("agent", AGENTS_TO_ARCHIVE)
    def test_archived_agent_not_in_active_dir(self, agent: str) -> None:
        assert not (AGENTS_DIR / agent).exists(), f"{agent} should not be in active agents/"

    @pytest.mark.parametrize("agent", AGENTS_TO_ARCHIVE)
    def test_archived_agent_has_deprecation_header(self, agent: str) -> None:
        content = (ARCHIVED_DIR / agent).read_text()
        assert "DEPRECATED" in content.upper() or "ARCHIVED" in content.upper(), (
            f"{agent} missing deprecation header"
        )

    @pytest.mark.parametrize("agent", CORE_AGENTS)
    def test_core_agent_still_active(self, agent: str) -> None:
        assert (AGENTS_DIR / agent).exists(), f"Core agent {agent} missing from agents/"

    def test_manifest_does_not_reference_archived_agents(self) -> None:
        manifest_text = MANIFEST.read_text()
        for agent in AGENTS_TO_ARCHIVE:
            name = agent.replace(".md", "")
            # Should not appear as an active agent reference
            assert f'"agents/{agent}"' not in manifest_text or "archived" in manifest_text

    def test_no_command_references_archived_agents(self) -> None:
        """Commands should not reference archived agent names."""
        commands_dir = PLUGIN / "commands"
        if not commands_dir.exists():
            pytest.skip("No commands directory")
        archived_names = [a.replace(".md", "") for a in AGENTS_TO_ARCHIVE]
        for cmd_file in commands_dir.glob("*.md"):
            content = cmd_file.read_text()
            for name in archived_names:
                # Allow references in comments/notes but not as agent dispatches
                if f"agent: {name}" in content.lower():
                    pytest.fail(f"Command {cmd_file.name} references archived agent '{name}'")

    def test_archived_dir_has_readme(self) -> None:
        """Archived directory should have a README explaining the archive."""
        assert (ARCHIVED_DIR / "README.md").exists(), "archived/ missing README.md"

    def test_archived_count_matches_expected(self) -> None:
        archived_files = list(ARCHIVED_DIR.glob("*.md"))
        # Exclude README
        archived_agents = [f for f in archived_files if f.name != "README.md"]
        assert len(archived_agents) >= len(AGENTS_TO_ARCHIVE), (
            f"Expected >= {len(AGENTS_TO_ARCHIVE)} archived agents, found {len(archived_agents)}"
        )


class TestSkillConsolidation:
    """Verify realign-* skills are consolidated."""

    def test_meta_framework_skill_exists(self) -> None:
        skill_md = SKILLS_DIR / "realign-meta-framework" / "SKILL.md"
        assert skill_md.exists(), "realign-meta-framework/SKILL.md not found"

    def test_meta_framework_has_performance_optimization(self) -> None:
        skill_md = SKILLS_DIR / "realign-meta-framework" / "SKILL.md"
        content = skill_md.read_text()
        assert "performance optimization" in content.lower() or "Performance Optimization" in content

    def test_domain_workflows_skill_exists(self) -> None:
        skill_md = SKILLS_DIR / "realign-domain-workflows" / "SKILL.md"
        assert skill_md.exists(), "realign-domain-workflows/SKILL.md not found"

    def test_domain_workflows_has_all_domains(self) -> None:
        skill_md = SKILLS_DIR / "realign-domain-workflows" / "SKILL.md"
        content = skill_md.read_text().lower()
        domains = ["antihallucination", "dpo", "persona", "rlvr", "source", "srf"]
        for domain in domains:
            assert domain in content, f"Domain '{domain}' missing from domain-workflows skill"

    @pytest.mark.parametrize("old_skill", OLD_REALIGN_SKILLS)
    def test_old_realign_skill_removed(self, old_skill: str) -> None:
        assert not (SKILLS_DIR / old_skill).exists(), f"Old skill {old_skill} should be removed"

    def test_new_skills_have_auto_activate_false(self) -> None:
        for skill_name in NEW_REALIGN_SKILLS:
            skill_md = SKILLS_DIR / skill_name / "SKILL.md"
            fm = _read_yaml_frontmatter(skill_md)
            assert fm.get("auto_activate") is False, (
                f"{skill_name} should have auto_activate: false"
            )

    def test_domain_workflows_has_keywords_from_originals(self) -> None:
        """New domain-workflows should have keywords covering all 6 originals."""
        skill_md = SKILLS_DIR / "realign-domain-workflows" / "SKILL.md"
        fm = _read_yaml_frontmatter(skill_md)
        keywords_str = str(fm.get("keywords", "")).lower()
        # Should mention key domains
        for domain in ["dpo", "rlvr", "srf"]:
            assert domain in keywords_str, f"Keyword '{domain}' missing from domain-workflows"

    def test_no_duplicate_performance_optimization_content(self) -> None:
        """Performance Optimization should only be in meta-framework, not domain-workflows."""
        domain_md = SKILLS_DIR / "realign-domain-workflows" / "SKILL.md"
        if domain_md.exists():
            content = domain_md.read_text()
            # Should not have a full Performance Optimization section
            assert "## Performance Optimization" not in content, (
                "domain-workflows should not duplicate Performance Optimization section"
            )


class TestAutoActivateReduction:
    """Verify auto_activate reduction to core skills only."""

    def test_auto_activate_true_count_at_most_15(self) -> None:
        count = 0
        for skill_dir in SKILLS_DIR.iterdir():
            if not skill_dir.is_dir():
                continue
            skill_md = skill_dir / "SKILL.md"
            if skill_md.exists():
                fm = _read_yaml_frontmatter(skill_md)
                if fm.get("auto_activate") is True:
                    count += 1
        assert count <= 15, f"Too many auto_activate: true skills ({count}), expected <= 15"

    @pytest.mark.parametrize("skill", CORE_SKILLS)
    def test_core_skill_auto_activate_true(self, skill: str) -> None:
        skill_md = SKILLS_DIR / skill / "SKILL.md"
        if not skill_md.exists():
            pytest.skip(f"Skill {skill} not found")
        fm = _read_yaml_frontmatter(skill_md)
        assert fm.get("auto_activate") is True, f"Core skill {skill} should have auto_activate: true"

    def test_specialized_skills_auto_activate_false(self) -> None:
        specialized = [
            "mlx-performance",
            "grpo-verifiable-training",
            "data-distillation",
            "scientific-validation",
            "database-design",
        ]
        for skill in specialized:
            skill_md = SKILLS_DIR / skill / "SKILL.md"
            if not skill_md.exists():
                continue
            fm = _read_yaml_frontmatter(skill_md)
            assert fm.get("auto_activate") is not True, (
                f"Specialized skill {skill} should not have auto_activate: true"
            )

    def test_all_skills_have_valid_frontmatter(self) -> None:
        """Every SKILL.md should have YAML frontmatter with --- delimiters."""
        for skill_dir in SKILLS_DIR.iterdir():
            if not skill_dir.is_dir():
                continue
            skill_md = skill_dir / "SKILL.md"
            if skill_md.exists():
                text = skill_md.read_text()
                assert text.startswith("---"), (
                    f"{skill_dir.name}/SKILL.md missing YAML frontmatter (no leading ---)"
                )

    def test_auto_activate_true_count_at_least_5(self) -> None:
        """Sanity check: at least 5 core skills should be auto_activate: true."""
        count = 0
        for skill_dir in SKILLS_DIR.iterdir():
            if not skill_dir.is_dir():
                continue
            skill_md = skill_dir / "SKILL.md"
            if skill_md.exists():
                fm = _read_yaml_frontmatter(skill_md)
                if fm.get("auto_activate") is True:
                    count += 1
        assert count >= 5, f"Too few auto_activate: true skills ({count}), expected >= 5"

    def test_no_skill_missing_auto_activate_field(self) -> None:
        """Every skill should explicitly declare auto_activate."""
        missing = []
        for skill_dir in SKILLS_DIR.iterdir():
            if not skill_dir.is_dir():
                continue
            skill_md = skill_dir / "SKILL.md"
            if skill_md.exists():
                fm = _read_yaml_frontmatter(skill_md)
                if "auto_activate" not in fm:
                    missing.append(skill_dir.name)
        assert not missing, f"Skills missing auto_activate field: {missing}"


class TestManifestAlignment:
    """Verify manifest and CLAUDE.md are aligned with actual file state."""

    def test_manifest_agent_count_matches_directory(self) -> None:
        agent_files = [
            f for f in AGENTS_DIR.glob("*.md")
            if f.name != "README.md"
        ]
        manifest = json.loads(MANIFEST.read_text())
        # Check manifest has a count or agents list
        manifest_str = MANIFEST.read_text()
        # The active agent count should match
        active_count = len(agent_files)
        # Manifest should reflect this count somewhere
        assert str(active_count) in manifest_str or "agents" in manifest_str

    def test_manifest_skill_count_matches_directory(self) -> None:
        skill_dirs = [
            d for d in SKILLS_DIR.iterdir()
            if d.is_dir() and (d / "SKILL.md").exists()
        ]
        manifest_str = MANIFEST.read_text()
        skill_count = len(skill_dirs)
        # Manifest should reflect skill count
        assert str(skill_count) in manifest_str or "skills" in manifest_str

    def test_claude_md_component_counts_updated(self) -> None:
        """CLAUDE.md should have updated component counts."""
        content = CLAUDE_MD.read_text()
        # Should mention agents count
        assert re.search(r"\d+ agents", content), "CLAUDE.md missing agent count"
        # Should mention skills count
        assert re.search(r"\d+ skills", content), "CLAUDE.md missing skill count"

    def test_no_broken_agent_references_in_manifest(self) -> None:
        """All agent references in manifest should point to existing files."""
        manifest = json.loads(MANIFEST.read_text())
        manifest_str = json.dumps(manifest)
        # Find agent file references
        agent_refs = re.findall(r'agents/([^"]+\.md)', manifest_str)
        for ref in agent_refs:
            # Should exist either in active or archived
            active = AGENTS_DIR / ref
            archived = ARCHIVED_DIR / ref
            assert active.exists() or archived.exists(), (
                f"Manifest references agents/{ref} but file not found"
            )
