#!/usr/bin/env python3
"""
Tests for skill_loader.py - Skill Injection for Subagents

Issue #140: Skills not available to subagents spawned via Task tool

These tests verify:
1. All agents have skills mapped
2. All mapped skills can be loaded
3. Skill content is properly formatted
4. Security (no path traversal)
5. Graceful degradation for missing skills
"""

import pytest
import sys
from pathlib import Path

# Add lib to path
lib_path = Path(__file__).parent.parent.parent / "plugins" / "autonomous-dev" / "lib"
sys.path.insert(0, str(lib_path))

from skill_loader import (
    AGENT_SKILL_MAP,
    load_skills_for_agent,
    load_skill_content,
    format_skills_for_prompt,
    get_skill_injection_for_agent,
    get_available_skills,
    parse_agent_skills,
)


class TestAgentSkillMapping:
    """Test agent-skill mapping configuration."""

    def test_all_core_agents_have_mappings(self):
        """Core workflow agents should have skill mappings."""
        core_agents = [
            "implementer",
            "test-master",
            "reviewer",
            "security-auditor",
            "doc-master",
            "planner",
        ]
        for agent in core_agents:
            assert agent in AGENT_SKILL_MAP, f"Agent '{agent}' missing from AGENT_SKILL_MAP"
            assert len(AGENT_SKILL_MAP[agent]) > 0, f"Agent '{agent}' has no skills mapped"

    def test_agent_skill_map_has_8_agents(self):
        """Should have mappings for all 8 active agents (Issue #147)."""
        assert len(AGENT_SKILL_MAP) == 8, f"Expected 8 agents, got {len(AGENT_SKILL_MAP)}"

    def test_no_duplicate_skills_per_agent(self):
        """Each agent should not have duplicate skills."""
        for agent, skills in AGENT_SKILL_MAP.items():
            assert len(skills) == len(set(skills)), f"Agent '{agent}' has duplicate skills"


class TestSkillLoading:
    """Test skill content loading."""

    def test_load_skills_for_implementer(self):
        """Implementer should load python-standards, testing-guide, error-handling-patterns."""
        skills = load_skills_for_agent("implementer")
        assert "python-standards" in skills
        assert "testing-guide" in skills
        assert "error-handling-patterns" in skills
        assert len(skills) == 3

    def test_load_skills_for_security_auditor(self):
        """Security auditor should load security-patterns, error-handling-patterns."""
        skills = load_skills_for_agent("security-auditor")
        assert "security-patterns" in skills
        assert "error-handling-patterns" in skills
        assert len(skills) == 2

    def test_load_skill_content_returns_string(self):
        """Loaded skill content should be a non-empty string."""
        content = load_skill_content("python-standards")
        assert content is not None
        assert isinstance(content, str)
        assert len(content) > 100  # SKILL.md should have substantial content

    def test_load_nonexistent_skill_returns_none(self):
        """Loading a nonexistent skill should return None."""
        content = load_skill_content("nonexistent-skill-xyz")
        assert content is None

    def test_all_mapped_skills_exist(self):
        """All skills in AGENT_SKILL_MAP should exist and be loadable."""
        all_skills = set()
        for skills in AGENT_SKILL_MAP.values():
            all_skills.update(skills)

        for skill_name in all_skills:
            content = load_skill_content(skill_name)
            assert content is not None, f"Skill '{skill_name}' not found or empty"
            assert len(content) > 50, f"Skill '{skill_name}' has insufficient content"


class TestSkillFormatting:
    """Test skill content formatting for prompt injection."""

    def test_format_skills_includes_xml_tags(self):
        """Formatted skills should include XML tags."""
        skills = {"test-skill": "Test content here"}
        formatted = format_skills_for_prompt(skills)
        assert "<skills>" in formatted
        assert "</skills>" in formatted
        assert '<skill name="test-skill">' in formatted
        assert "</skill>" in formatted

    def test_format_empty_skills_returns_empty_string(self):
        """Empty skills dict should return empty string."""
        formatted = format_skills_for_prompt({})
        assert formatted == ""

    def test_format_respects_line_limit(self):
        """Formatting should truncate if exceeding line limit."""
        # Create a skill with many lines
        long_content = "\n".join(["line"] * 2000)
        skills = {"long-skill": long_content}
        formatted = format_skills_for_prompt(skills, max_total_lines=100)
        # Should be truncated
        assert "truncated" in formatted.lower() or len(formatted.split('\n')) < 150


class TestConvenienceFunctions:
    """Test convenience functions."""

    def test_get_skill_injection_for_agent(self):
        """Convenience function should return formatted skills."""
        injection = get_skill_injection_for_agent("implementer")
        assert injection is not None
        assert "<skills>" in injection
        assert "python-standards" in injection

    def test_get_skill_injection_for_unknown_agent(self):
        """Unknown agent should return empty string."""
        injection = get_skill_injection_for_agent("unknown-agent-xyz")
        assert injection == ""

    def test_get_available_skills(self):
        """Should return list of available skill names."""
        skills = get_available_skills()
        assert isinstance(skills, list)
        assert len(skills) >= 20  # We have 28 skills
        assert "python-standards" in skills
        assert "security-patterns" in skills


class TestSecurity:
    """Test security features."""

    def test_path_traversal_blocked(self):
        """Path traversal attempts should be blocked."""
        content = load_skill_content("../../../etc/passwd")
        assert content is None

    def test_absolute_path_blocked(self):
        """Absolute paths should be blocked."""
        content = load_skill_content("/etc/passwd")
        assert content is None

    def test_backslash_path_blocked(self):
        """Backslash paths should be blocked."""
        content = load_skill_content("..\\..\\windows\\system32")
        assert content is None


class TestParseAgentSkills:
    """Test parsing agent frontmatter for skills."""

    def test_parse_returns_list(self):
        """parse_agent_skills should return a list."""
        skills = parse_agent_skills("implementer")
        assert isinstance(skills, list)

    def test_parse_known_agent_returns_skills(self):
        """Known agent should return skills from mapping."""
        skills = parse_agent_skills("implementer")
        assert len(skills) > 0
        assert "python-standards" in skills

    def test_parse_unknown_agent_returns_empty(self):
        """Unknown agent should return empty list."""
        skills = parse_agent_skills("unknown-agent-xyz")
        assert skills == []


class TestIntegration:
    """Integration tests for skill injection workflow."""

    def test_all_agents_can_load_skills(self):
        """All mapped agents should be able to load their skills."""
        for agent_name in AGENT_SKILL_MAP:
            skills = load_skills_for_agent(agent_name)
            expected_count = len(AGENT_SKILL_MAP[agent_name])
            assert len(skills) == expected_count, (
                f"Agent '{agent_name}' loaded {len(skills)} skills, expected {expected_count}"
            )

    def test_skill_injection_produces_reasonable_output(self):
        """Skill injection should produce reasonable token counts."""
        for agent_name in ["implementer", "test-master", "security-auditor"]:
            injection = get_skill_injection_for_agent(agent_name)
            # Should be non-empty
            assert len(injection) > 100
            # Should be under reasonable limit (roughly 3000 lines * 4 chars = 12000)
            assert len(injection) < 100000, f"Agent '{agent_name}' injection too large"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
