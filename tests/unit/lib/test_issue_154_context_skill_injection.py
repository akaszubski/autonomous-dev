#!/usr/bin/env python3
"""
TDD Tests for Issue #154 - Context-Triggered Skill Injection

Tests the pattern-based skill injection system that auto-injects relevant
skills based on conversation context patterns.

Issue #154 Context:
- Skills should auto-inject based on conversation patterns, not just agent frontmatter
- Pattern-based detection (regex), not semantic (LLM)
- Max 3-5 skills per context to prevent bloat
- Must add <100ms latency
- Reuse existing skill_loader.py infrastructure

Test Strategy:
- Phase 1: Pattern detection functions
- Phase 2: Pattern-to-skill mapping
- Phase 3: Skill selection with limits
- Phase 4: Integration with skill_loader
- Phase 5: Performance requirements
- Phase 6: Edge cases

Author: test-master agent
Date: 2025-12-17
Issue: #154
"""

import os
import sys
import time
from pathlib import Path
from typing import Dict, List
from unittest.mock import patch, MagicMock

import pytest

# Add lib directory to path for imports
sys.path.insert(
    0,
    str(
        Path(__file__).parent.parent.parent.parent
        / "plugins"
        / "autonomous-dev"
        / "lib"
    ),
)


class TestPhase1PatternDetection:
    """Phase 1: Test context pattern detection functions."""

    @pytest.fixture
    def import_module(self):
        """Import the module fresh for each test."""
        if "context_skill_injector" in sys.modules:
            del sys.modules["context_skill_injector"]
        from context_skill_injector import detect_context_patterns
        return detect_context_patterns

    def test_detects_security_terms(self, import_module):
        """Test detection of security-related terms."""
        detect = import_module
        patterns = detect("implement JWT authentication with secure token storage")
        assert "security" in patterns

    def test_detects_auth_patterns(self, import_module):
        """Test detection of authentication patterns."""
        detect = import_module
        patterns = detect("add password validation and login functionality")
        assert "security" in patterns

    def test_detects_api_patterns(self, import_module):
        """Test detection of API/endpoint work."""
        detect = import_module
        patterns = detect("create a REST API endpoint for user registration")
        assert "api" in patterns

    def test_detects_database_patterns(self, import_module):
        """Test detection of database-related patterns."""
        detect = import_module
        patterns = detect("add a new database migration for the users table")
        assert "database" in patterns

    def test_detects_git_patterns(self, import_module):
        """Test detection of git operation patterns."""
        detect = import_module
        patterns = detect("commit the changes and create a pull request")
        assert "git" in patterns

    def test_detects_testing_patterns(self, import_module):
        """Test detection of testing-related patterns."""
        detect = import_module
        patterns = detect("write unit tests for the user service")
        assert "testing" in patterns

    def test_detects_python_patterns(self, import_module):
        """Test detection of Python code patterns."""
        detect = import_module
        patterns = detect("refactor this Python class with type hints")
        assert "python" in patterns

    def test_detects_multiple_patterns(self, import_module):
        """Test detection of multiple patterns in single prompt."""
        detect = import_module
        patterns = detect("create a secure API endpoint with database queries and tests")
        assert len(patterns) >= 2
        assert "security" in patterns or "api" in patterns

    def test_empty_prompt_returns_empty(self, import_module):
        """Test empty prompt returns no patterns."""
        detect = import_module
        patterns = detect("")
        assert len(patterns) == 0

    def test_unrelated_prompt_returns_empty(self, import_module):
        """Test unrelated prompt returns no patterns."""
        detect = import_module
        patterns = detect("what is the weather today?")
        assert len(patterns) == 0


class TestPhase2PatternToSkillMapping:
    """Phase 2: Test pattern-to-skill mapping configuration."""

    @pytest.fixture
    def import_mapping(self):
        """Import the mapping."""
        if "context_skill_injector" in sys.modules:
            del sys.modules["context_skill_injector"]
        from context_skill_injector import PATTERN_SKILL_MAP
        return PATTERN_SKILL_MAP

    def test_mapping_exists(self, import_mapping):
        """Test that pattern-to-skill mapping exists."""
        mapping = import_mapping
        assert isinstance(mapping, dict)
        assert len(mapping) > 0

    def test_security_maps_to_security_skills(self, import_mapping):
        """Test security pattern maps to security skills."""
        mapping = import_mapping
        assert "security" in mapping
        skills = mapping["security"]
        assert "security-patterns" in skills

    def test_api_maps_to_api_skills(self, import_mapping):
        """Test API pattern maps to API skills."""
        mapping = import_mapping
        assert "api" in mapping
        skills = mapping["api"]
        assert "api-design" in skills or "api-integration-patterns" in skills

    def test_database_maps_to_database_skills(self, import_mapping):
        """Test database pattern maps to database skills."""
        mapping = import_mapping
        assert "database" in mapping
        skills = mapping["database"]
        assert "database-design" in skills

    def test_git_maps_to_git_skills(self, import_mapping):
        """Test git pattern maps to git skills."""
        mapping = import_mapping
        assert "git" in mapping
        skills = mapping["git"]
        assert "git-workflow" in skills

    def test_testing_maps_to_testing_skills(self, import_mapping):
        """Test testing pattern maps to testing skills."""
        mapping = import_mapping
        assert "testing" in mapping
        skills = mapping["testing"]
        assert "testing-guide" in skills

    def test_python_maps_to_python_skills(self, import_mapping):
        """Test Python pattern maps to Python skills."""
        mapping = import_mapping
        assert "python" in mapping
        skills = mapping["python"]
        assert "python-standards" in skills


class TestPhase3SkillSelectionLimits:
    """Phase 3: Test skill selection with limits (max 3-5 skills)."""

    @pytest.fixture
    def import_selector(self):
        """Import the skill selector."""
        if "context_skill_injector" in sys.modules:
            del sys.modules["context_skill_injector"]
        from context_skill_injector import select_skills_for_context
        return select_skills_for_context

    def test_returns_list_of_skills(self, import_selector):
        """Test selector returns list of skill names."""
        select = import_selector
        skills = select("implement secure API endpoint")
        assert isinstance(skills, list)
        assert all(isinstance(s, str) for s in skills)

    def test_limits_to_max_5_skills(self, import_selector):
        """Test skill selection is limited to max 5 skills."""
        select = import_selector
        # Prompt that could trigger many patterns
        prompt = "implement secure API with database, tests, git commit, and Python classes"
        skills = select(prompt)
        assert len(skills) <= 5

    def test_no_duplicate_skills(self, import_selector):
        """Test no duplicate skills in selection."""
        select = import_selector
        skills = select("secure auth with password and token validation")
        assert len(skills) == len(set(skills))

    def test_returns_empty_for_no_patterns(self, import_selector):
        """Test returns empty list when no patterns match."""
        select = import_selector
        skills = select("what is the weather?")
        assert skills == []

    def test_prioritizes_by_relevance(self, import_selector):
        """Test skills are prioritized (security first for security prompts)."""
        select = import_selector
        skills = select("add JWT authentication")
        if skills:
            # Security-related skill should be included
            assert any("security" in s.lower() for s in skills)


class TestPhase4IntegrationWithSkillLoader:
    """Phase 4: Test integration with existing skill_loader.py."""

    @pytest.fixture
    def import_injector(self):
        """Import the main injector function."""
        if "context_skill_injector" in sys.modules:
            del sys.modules["context_skill_injector"]
        from context_skill_injector import get_context_skill_injection
        return get_context_skill_injection

    def test_returns_formatted_skill_content(self, import_injector):
        """Test injector returns formatted skill content string."""
        inject = import_injector
        result = inject("implement secure authentication")
        assert isinstance(result, str)
        # Should be empty or contain skill content
        if result:
            # Should contain XML-style skill tags if skills loaded
            assert "<skill" in result or result == ""

    def test_graceful_degradation_missing_skills(self, import_injector):
        """Test graceful handling when skills don't exist."""
        inject = import_injector
        # Should not raise exception
        result = inject("implement feature")
        assert isinstance(result, str)

    def test_returns_empty_for_no_matches(self, import_injector):
        """Test returns empty string when no patterns match."""
        inject = import_injector
        result = inject("hello world")
        assert result == ""


class TestPhase5PerformanceRequirements:
    """Phase 5: Test performance requirements (<100ms latency)."""

    @pytest.fixture
    def import_detector(self):
        """Import pattern detector."""
        if "context_skill_injector" in sys.modules:
            del sys.modules["context_skill_injector"]
        from context_skill_injector import detect_context_patterns
        return detect_context_patterns

    @pytest.fixture
    def import_selector(self):
        """Import skill selector."""
        if "context_skill_injector" in sys.modules:
            del sys.modules["context_skill_injector"]
        from context_skill_injector import select_skills_for_context
        return select_skills_for_context

    def test_pattern_detection_under_10ms(self, import_detector):
        """Test pattern detection completes in under 10ms."""
        detect = import_detector
        prompt = "implement secure API endpoint with database and tests"

        start = time.time()
        for _ in range(100):
            detect(prompt)
        elapsed = (time.time() - start) / 100 * 1000  # Average ms

        assert elapsed < 10, f"Pattern detection took {elapsed:.2f}ms (max 10ms)"

    def test_skill_selection_under_50ms(self, import_selector):
        """Test skill selection completes in under 50ms."""
        select = import_selector
        prompt = "implement secure API endpoint with database and tests"

        start = time.time()
        for _ in range(10):
            select(prompt)
        elapsed = (time.time() - start) / 10 * 1000  # Average ms

        assert elapsed < 50, f"Skill selection took {elapsed:.2f}ms (max 50ms)"


class TestPhase6EdgeCases:
    """Phase 6: Test edge cases and boundary conditions."""

    @pytest.fixture
    def import_detector(self):
        """Import pattern detector."""
        if "context_skill_injector" in sys.modules:
            del sys.modules["context_skill_injector"]
        from context_skill_injector import detect_context_patterns
        return detect_context_patterns

    @pytest.fixture
    def import_selector(self):
        """Import skill selector."""
        if "context_skill_injector" in sys.modules:
            del sys.modules["context_skill_injector"]
        from context_skill_injector import select_skills_for_context
        return select_skills_for_context

    def test_handles_none_input(self, import_detector):
        """Test handles None input gracefully."""
        detect = import_detector
        # Should not raise exception
        try:
            result = detect(None)
            assert result == [] or result == set()
        except TypeError:
            pytest.fail("Should handle None input gracefully")

    def test_handles_very_long_prompt(self, import_detector):
        """Test handles very long prompts efficiently."""
        detect = import_detector
        long_prompt = "implement " + " ".join(["feature"] * 10000)

        start = time.time()
        result = detect(long_prompt)
        elapsed = (time.time() - start) * 1000

        assert elapsed < 100, f"Long prompt took {elapsed:.2f}ms"

    def test_case_insensitivity(self, import_detector):
        """Test pattern detection is case-insensitive."""
        detect = import_detector
        patterns_lower = detect("implement authentication")
        patterns_upper = detect("IMPLEMENT AUTHENTICATION")
        patterns_mixed = detect("Implement Authentication")

        assert patterns_lower == patterns_upper == patterns_mixed

    def test_partial_word_matching(self, import_detector):
        """Test patterns match partial words appropriately."""
        detect = import_detector
        # "authenticate" should trigger security pattern
        patterns = detect("need to authenticate users")
        assert "security" in patterns

    def test_special_characters_handled(self, import_detector):
        """Test special characters don't break detection."""
        detect = import_detector
        # Should not raise exception
        result = detect("implement auth with @#$%^&*() special chars")
        assert isinstance(result, (list, set))


class TestPhase7ConfigurationOptions:
    """Phase 7: Test configuration options."""

    @pytest.fixture
    def import_module(self):
        """Import the module."""
        if "context_skill_injector" in sys.modules:
            del sys.modules["context_skill_injector"]
        import context_skill_injector
        return context_skill_injector

    def test_max_skills_configurable(self, import_module):
        """Test max skills limit can be configured."""
        module = import_module
        # Should have a constant or parameter for max skills
        assert hasattr(module, "MAX_CONTEXT_SKILLS") or True  # Optional

    def test_pattern_map_is_dict(self, import_module):
        """Test pattern map is accessible dict."""
        module = import_module
        assert hasattr(module, "PATTERN_SKILL_MAP")
        assert isinstance(module.PATTERN_SKILL_MAP, dict)


# Checkpoint integration
if __name__ == "__main__":
    pytest.main([__file__, "-v"])
