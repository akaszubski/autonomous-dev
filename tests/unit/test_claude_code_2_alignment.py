#!/usr/bin/env python3
"""
Tests for Issue #143 - Claude Code 2.0 Alignment

Validates that autonomous-dev codebase aligns with Claude Code 2.0 native features:
1. Agent files have skills: frontmatter field
2. skills: field matches AGENT_SKILL_MAP
3. auto-implement.md has no SKILL INJECTION sections
4. Hooks have no hardcoded /Users/ paths (should use ${CLAUDE_PLUGIN_ROOT})
5. plugin.json has flat structure (not nested components)
6. All referenced skills exist in skills/ directory

See: https://github.com/akaszubski/autonomous-dev/issues/143
"""

import pytest
import sys
import json
import yaml
from pathlib import Path
from typing import Dict, List, Set

# Add lib to path
lib_path = Path(__file__).parent.parent.parent / "plugins" / "autonomous-dev" / "lib"
sys.path.insert(0, str(lib_path))

from skill_loader import AGENT_SKILL_MAP

# Project paths
PROJECT_ROOT = Path(__file__).parent.parent.parent
AGENTS_DIR = PROJECT_ROOT / "plugins" / "autonomous-dev" / "agents"
COMMANDS_DIR = PROJECT_ROOT / "plugins" / "autonomous-dev" / "commands"
HOOKS_DIR = PROJECT_ROOT / "plugins" / "autonomous-dev" / "hooks"
SKILLS_DIR = PROJECT_ROOT / "plugins" / "autonomous-dev" / "skills"
PLUGIN_JSON = PROJECT_ROOT / "plugins" / "autonomous-dev" / "plugin.json"


def parse_frontmatter(file_path: Path) -> Dict:
    """Parse YAML frontmatter from agent markdown file."""
    content = file_path.read_text(encoding='utf-8')

    if not content.startswith('---'):
        return {}

    # Find second ---
    parts = content.split('---', 2)
    if len(parts) < 3:
        return {}

    frontmatter = parts[1].strip()
    try:
        return yaml.safe_load(frontmatter) or {}
    except yaml.YAMLError:
        return {}


def get_all_agent_files() -> List[Path]:
    """Get all agent markdown files."""
    return sorted(AGENTS_DIR.glob("*.md"))


def get_all_hook_files() -> List[Path]:
    """Get all hook Python files."""
    return sorted(HOOKS_DIR.glob("*.py"))


def get_all_skills() -> Set[str]:
    """Get all available skill names from skills directory."""
    return {skill.name for skill in SKILLS_DIR.iterdir() if skill.is_dir()}


class TestPhase1AgentSkillsFrontmatter:
    """Phase 1: Verify all agents have skills: frontmatter field."""

    def test_all_agents_have_frontmatter(self):
        """All agent files should have valid YAML frontmatter."""
        agent_files = get_all_agent_files()
        assert len(agent_files) >= 22, f"Expected at least 22 agents, found {len(agent_files)}"

        for agent_file in agent_files:
            frontmatter = parse_frontmatter(agent_file)
            assert frontmatter, f"{agent_file.name} has no valid frontmatter"

    def test_all_agents_have_skills_field(self):
        """All agent files should have skills: field in frontmatter."""
        agent_files = get_all_agent_files()
        missing_skills = []

        for agent_file in agent_files:
            frontmatter = parse_frontmatter(agent_file)
            if 'skills' not in frontmatter:
                missing_skills.append(agent_file.name)

        assert not missing_skills, (
            f"Agents missing skills: field: {', '.join(missing_skills)}\n"
            "Phase 1 requires all agents to have skills: in frontmatter"
        )

    def test_skills_field_is_list(self):
        """skills: field should be a list of strings."""
        agent_files = get_all_agent_files()
        invalid_types = []

        for agent_file in agent_files:
            frontmatter = parse_frontmatter(agent_file)
            if 'skills' in frontmatter:
                skills = frontmatter['skills']
                if not isinstance(skills, list):
                    invalid_types.append(f"{agent_file.name}: {type(skills).__name__}")
                elif not all(isinstance(s, str) for s in skills):
                    invalid_types.append(f"{agent_file.name}: contains non-string items")

        assert not invalid_types, (
            f"Agents with invalid skills: type: {', '.join(invalid_types)}\n"
            "skills: must be a list of strings"
        )

    @pytest.mark.parametrize("agent_name,expected_skills", [
        ("implementer", ["python-standards", "testing-guide", "error-handling-patterns"]),
        ("test-master", ["testing-guide", "python-standards"]),
        ("reviewer", ["code-review", "python-standards"]),
        ("security-auditor", ["security-patterns", "error-handling-patterns"]),
        ("doc-master", ["documentation-guide", "git-workflow"]),
        ("planner", ["architecture-patterns", "project-management"]),
    ])
    def test_core_agent_skills_match_map(self, agent_name, expected_skills):
        """Core workflow agents should have skills matching AGENT_SKILL_MAP."""
        agent_file = AGENTS_DIR / f"{agent_name}.md"
        assert agent_file.exists(), f"Agent file {agent_name}.md not found"

        frontmatter = parse_frontmatter(agent_file)
        actual_skills = set(frontmatter.get('skills', []))
        expected_set = set(expected_skills)

        assert actual_skills == expected_set, (
            f"{agent_name}.md skills mismatch:\n"
            f"  Expected: {sorted(expected_set)}\n"
            f"  Actual: {sorted(actual_skills)}\n"
            f"  Missing: {sorted(expected_set - actual_skills)}\n"
            f"  Extra: {sorted(actual_skills - expected_set)}"
        )


class TestPhase2AgentSkillMapAlignment:
    """Phase 2: Verify skills: field matches AGENT_SKILL_MAP for all 21 agents."""

    def test_all_mapped_agents_have_correct_skills(self):
        """All agents in AGENT_SKILL_MAP should have matching skills: frontmatter."""
        mismatches = []

        for agent_name, expected_skills in AGENT_SKILL_MAP.items():
            agent_file = AGENTS_DIR / f"{agent_name}.md"

            if not agent_file.exists():
                mismatches.append(f"{agent_name}: file not found")
                continue

            frontmatter = parse_frontmatter(agent_file)
            actual_skills = set(frontmatter.get('skills', []))
            expected_set = set(expected_skills)

            if actual_skills != expected_set:
                missing = expected_set - actual_skills
                extra = actual_skills - expected_set
                mismatches.append(
                    f"{agent_name}: missing={sorted(missing)}, extra={sorted(extra)}"
                )

        assert not mismatches, (
            f"Agent skills: frontmatter doesn't match AGENT_SKILL_MAP:\n" +
            "\n".join(f"  - {m}" for m in mismatches)
        )

    def test_agent_skill_map_has_21_agents(self):
        """AGENT_SKILL_MAP should have 21 agents (orchestrator deprecated)."""
        assert len(AGENT_SKILL_MAP) == 21, (
            f"Expected 21 agents in AGENT_SKILL_MAP, got {len(AGENT_SKILL_MAP)}"
        )

    def test_all_agent_files_are_in_map(self):
        """All agent .md files should be in AGENT_SKILL_MAP."""
        agent_files = get_all_agent_files()
        agent_names = {f.stem for f in agent_files}
        mapped_names = set(AGENT_SKILL_MAP.keys())

        # Exclude special files and deprecated agents
        exclude = {'archived', '__pycache__', 'researcher'}  # researcher is deprecated (split into researcher-local + researcher-web)
        agent_names -= exclude

        unmapped = agent_names - mapped_names
        assert not unmapped, (
            f"Agent files not in AGENT_SKILL_MAP: {sorted(unmapped)}\n"
            "Either add to AGENT_SKILL_MAP or move to archived/"
        )


class TestPhase3SkillInjectionRemoval:
    """Phase 3: Verify auto-implement.md has no SKILL INJECTION sections."""

    def test_auto_implement_has_no_skill_injection_section(self):
        """auto-implement.md should not have SKILL INJECTION header."""
        auto_implement = COMMANDS_DIR / "auto-implement.md"
        assert auto_implement.exists(), "auto-implement.md not found"

        content = auto_implement.read_text(encoding='utf-8')

        # Check for various forms of skill injection headers
        forbidden_patterns = [
            "### SKILL INJECTION",
            "## SKILL INJECTION",
            "SKILL INJECTION (Issue #140)",
            "python3 plugins/autonomous-dev/lib/skill_loader.py",
            "Before EACH Task tool call, load relevant skills",
        ]

        violations = []
        for pattern in forbidden_patterns:
            if pattern in content:
                violations.append(pattern)

        assert not violations, (
            f"auto-implement.md contains SKILL INJECTION sections:\n" +
            "\n".join(f"  - Found: {v}" for v in violations) +
            "\n\nPhase 3 requires removal of manual skill injection (now native)"
        )

    def test_auto_implement_no_skill_loader_calls(self):
        """auto-implement.md should not reference skill_loader.py."""
        auto_implement = COMMANDS_DIR / "auto-implement.md"
        content = auto_implement.read_text(encoding='utf-8')

        assert "skill_loader.py" not in content, (
            "auto-implement.md references skill_loader.py\n"
            "Phase 3 requires removal of manual skill loading"
        )


class TestPhase4HardcodedPathRemoval:
    """Phase 4: Verify hooks use ${CLAUDE_PLUGIN_ROOT} instead of hardcoded paths."""

    def test_hooks_no_hardcoded_user_paths(self):
        """Hooks should not contain hardcoded /Users/ paths."""
        hook_files = get_all_hook_files()
        violations = []

        for hook_file in hook_files:
            content = hook_file.read_text(encoding='utf-8')

            # Skip if file is intentionally testing or documenting paths
            if 'test_' in hook_file.name or 'example' in hook_file.name.lower():
                continue

            # Check for hardcoded paths (excluding comments and docstrings)
            if '/Users/' in content or '/home/' in content:
                # Find line numbers for better error reporting
                lines_with_paths = []
                for i, line in enumerate(content.split('\n'), 1):
                    stripped = line.strip()
                    # Skip comments, docstrings, and example/documentation lines
                    if stripped.startswith('#') or stripped.startswith('"""') or stripped.startswith("'''"):
                        continue
                    if 'Example:' in line or 'example' in line.lower():
                        continue
                    if '/Users/' in line or '/home/' in line:
                        lines_with_paths.append(f"L{i}: {line.strip()[:80]}")

                # Only add to violations if there are actual code violations (not just comments)
                if lines_with_paths:
                    violations.append(f"{hook_file.name}:\n" + "\n".join(lines_with_paths))

        assert not violations, (
            f"Hooks contain hardcoded user paths:\n" +
            "\n\n".join(violations) +
            "\n\nPhase 4 requires using ${CLAUDE_PLUGIN_ROOT} variable"
        )

    def test_sync_to_installed_uses_plugin_root(self):
        """sync_to_installed.py should use environment variable for paths."""
        sync_hook = HOOKS_DIR / "sync_to_installed.py"
        if not sync_hook.exists():
            pytest.skip("sync_to_installed.py not found")

        content = sync_hook.read_text(encoding='utf-8')

        # Should use CLAUDE_PLUGIN_ROOT or similar
        assert (
            'CLAUDE_PLUGIN_ROOT' in content or
            'os.environ' in content or
            'Path.home()' in content
        ), "sync_to_installed.py should use environment variables, not hardcoded paths"


class TestPhase5PluginJsonFlatStructure:
    """Phase 5: Verify plugin.json has flat structure (not nested components)."""

    def test_plugin_json_exists(self):
        """plugin.json should exist."""
        assert PLUGIN_JSON.exists(), "plugin.json not found"

    def test_plugin_json_is_valid(self):
        """plugin.json should be valid JSON."""
        try:
            with PLUGIN_JSON.open() as f:
                json.load(f)
        except json.JSONDecodeError as e:
            pytest.fail(f"plugin.json is invalid: {e}")

    def test_plugin_json_has_flat_structure(self):
        """plugin.json should have flat structure (agents, skills, commands at top level)."""
        with PLUGIN_JSON.open() as f:
            manifest = json.load(f)

        # Should have top-level fields
        required_fields = ['name', 'version', 'description']
        for field in required_fields:
            assert field in manifest, f"plugin.json missing required field: {field}"

        # Should NOT have nested components structure
        assert 'components' not in manifest, (
            "plugin.json should not have 'components' structure\n"
            "Phase 5 requires flat structure with agents/skills/commands at top level"
        )

    def test_plugin_json_has_direct_arrays(self):
        """plugin.json should have commands as direct array (not nested)."""
        with PLUGIN_JSON.open() as f:
            manifest = json.load(f)

        # Commands should be direct array
        if 'commands' in manifest:
            assert isinstance(manifest['commands'], list), (
                "commands should be a direct array, not nested object"
            )


class TestPhase6SkillExistence:
    """Phase 6: Verify all referenced skills exist in skills/ directory."""

    def test_all_referenced_skills_exist(self):
        """All skills in AGENT_SKILL_MAP should exist in skills/ directory."""
        available_skills = get_all_skills()

        missing_skills = []
        for agent_name, skills in AGENT_SKILL_MAP.items():
            for skill_name in skills:
                if skill_name not in available_skills:
                    missing_skills.append(f"{agent_name} -> {skill_name}")

        assert not missing_skills, (
            f"Skills referenced in AGENT_SKILL_MAP but not found in skills/:\n" +
            "\n".join(f"  - {s}" for s in missing_skills)
        )

    def test_all_skills_have_skill_md(self):
        """All skill directories should contain SKILL.md file."""
        available_skills = get_all_skills()
        missing_skill_md = []

        for skill_name in available_skills:
            skill_md = SKILLS_DIR / skill_name / "SKILL.md"
            if not skill_md.exists():
                missing_skill_md.append(skill_name)

        assert not missing_skill_md, (
            f"Skills missing SKILL.md file:\n" +
            "\n".join(f"  - {s}" for s in missing_skill_md)
        )

    def test_skill_md_files_not_empty(self):
        """SKILL.md files should have substantial content."""
        available_skills = get_all_skills()
        empty_skills = []

        for skill_name in available_skills:
            skill_md = SKILLS_DIR / skill_name / "SKILL.md"
            if skill_md.exists():
                content = skill_md.read_text(encoding='utf-8')
                if len(content.strip()) < 100:
                    empty_skills.append(skill_name)

        assert not empty_skills, (
            f"Skills with insufficient content (< 100 chars):\n" +
            "\n".join(f"  - {s}" for s in empty_skills)
        )


class TestIntegrationClaude2Alignment:
    """Integration tests for Claude Code 2.0 alignment."""

    def test_complete_skill_injection_pipeline(self):
        """Full pipeline: frontmatter -> native injection -> agent receives skills."""
        # Pick a core agent
        agent_name = "implementer"
        agent_file = AGENTS_DIR / f"{agent_name}.md"

        # 1. Verify frontmatter exists
        frontmatter = parse_frontmatter(agent_file)
        assert 'skills' in frontmatter, f"{agent_name}.md missing skills: field"

        # 2. Verify skills match AGENT_SKILL_MAP
        expected_skills = set(AGENT_SKILL_MAP[agent_name])
        actual_skills = set(frontmatter['skills'])
        assert actual_skills == expected_skills

        # 3. Verify all skills exist
        available_skills = get_all_skills()
        for skill in actual_skills:
            assert skill in available_skills, f"Skill {skill} not found"

            # 4. Verify SKILL.md exists and has content
            skill_md = SKILLS_DIR / skill / "SKILL.md"
            assert skill_md.exists()
            content = skill_md.read_text(encoding='utf-8')
            assert len(content) > 100

    def test_no_legacy_skill_injection_in_codebase(self):
        """Codebase should not reference legacy manual skill injection."""
        # Check commands for legacy patterns
        auto_implement = COMMANDS_DIR / "auto-implement.md"
        if auto_implement.exists():
            content = auto_implement.read_text(encoding='utf-8')

            # Should not have manual injection instructions
            assert "skill_loader.py" not in content
            assert "SKILL INJECTION" not in content

    def test_all_phases_complete(self):
        """Verify all 5 phases of Issue #143 are complete."""
        # Phase 1: All agents have skills: frontmatter
        agent_files = get_all_agent_files()
        agents_with_skills = sum(
            1 for f in agent_files
            if 'skills' in parse_frontmatter(f)
        )
        assert agents_with_skills >= 21, "Phase 1 incomplete"

        # Phase 2: skills: matches AGENT_SKILL_MAP
        for agent_name in AGENT_SKILL_MAP:
            agent_file = AGENTS_DIR / f"{agent_name}.md"
            if agent_file.exists():
                frontmatter = parse_frontmatter(agent_file)
                assert set(frontmatter.get('skills', [])) == set(AGENT_SKILL_MAP[agent_name])

        # Phase 3: No SKILL INJECTION sections
        auto_implement = COMMANDS_DIR / "auto-implement.md"
        if auto_implement.exists():
            content = auto_implement.read_text(encoding='utf-8')
            assert "SKILL INJECTION" not in content

        # Phase 4: No hardcoded /Users/ paths in hooks
        hook_files = get_all_hook_files()
        for hook in hook_files:
            if 'test_' not in hook.name:
                content = hook.read_text(encoding='utf-8')
                assert '/Users/akaszubski' not in content, f"{hook.name} has hardcoded path"

        # Phase 5: Flat plugin.json
        with PLUGIN_JSON.open() as f:
            manifest = json.load(f)
        assert 'components' not in manifest


class TestBackwardsCompatibility:
    """Verify skill_loader.py still works for debugging/testing."""

    def test_skill_loader_library_still_exists(self):
        """skill_loader.py should still exist for debugging."""
        skill_loader = PROJECT_ROOT / "plugins" / "autonomous-dev" / "lib" / "skill_loader.py"
        assert skill_loader.exists(), "skill_loader.py should remain for debugging"

    def test_agent_skill_map_still_accurate(self):
        """AGENT_SKILL_MAP should be accurate reference."""
        assert len(AGENT_SKILL_MAP) == 21
        assert 'implementer' in AGENT_SKILL_MAP
        assert 'orchestrator' not in AGENT_SKILL_MAP  # Deprecated in v3.2.2


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
