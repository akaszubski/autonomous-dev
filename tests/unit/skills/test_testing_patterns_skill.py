#!/usr/bin/env python3
"""
TDD Tests for testing-guide Skill Enhancement (FAILING - Red Phase)

This module contains FAILING tests for enhancing the testing-guide skill to
consolidate testing patterns from 3 agent prompts (Issue #65).

Skill Enhancement Requirements:
1. Create 4 new skill enhancement files:
   - pytest-patterns.md (fixtures, mocking, parametrization)
   - coverage-strategies.md (80%+ coverage approaches)
   - arrange-act-assert.md (AAA pattern guidance)
   - test-templates/ directory with 3 template files
2. Update 3 agent prompts to reference testing-guide skill:
   - test-master.md (~80-100 lines removed)
   - implementer.md (~40-60 lines removed)
   - reviewer.md (~40-60 lines removed)
3. Expected token savings: ~190-210 tokens (5-8% reduction)

Test Coverage Target: 100% of skill enhancement and agent integration

Following TDD principles:
- Write tests FIRST (red phase)
- Tests describe skill requirements and agent integration
- Tests should FAIL until skill files and agent updates are implemented
- Each test validates ONE requirement

Author: test-master agent
Date: 2025-11-12
Issue: #65
"""

import os
import sys
from pathlib import Path
from unittest.mock import Mock, patch, mock_open

import pytest
import yaml

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

SKILL_DIR = Path(__file__).parent.parent.parent.parent / "plugins" / "autonomous-dev" / "skills" / "testing-guide"
PYTEST_PATTERNS_FILE = SKILL_DIR / "pytest-patterns.md"
COVERAGE_STRATEGIES_FILE = SKILL_DIR / "coverage-strategies.md"
AAA_PATTERN_FILE = SKILL_DIR / "arrange-act-assert.md"
TEST_TEMPLATES_DIR = SKILL_DIR / "test-templates"
AGENTS_DIR = Path(__file__).parent.parent.parent.parent / "plugins" / "autonomous-dev" / "agents"


class TestSkillStructure:
    """Test testing-guide skill enhancement file structure."""

    def test_pytest_patterns_file_exists(self):
        """Test pytest-patterns.md file exists in skills/testing-guide/ directory."""
        assert PYTEST_PATTERNS_FILE.exists(), (
            f"Skill enhancement file not found: {PYTEST_PATTERNS_FILE}\n"
            f"Expected: Create skills/testing-guide/pytest-patterns.md\n"
            f"See: Issue #65"
        )

    def test_pytest_patterns_contains_fixtures_section(self):
        """Test pytest-patterns.md contains fixtures guidance."""
        content = PYTEST_PATTERNS_FILE.read_text()

        # Check for fixtures section
        assert "fixtures" in content.lower() or "Fixtures" in content, (
            "pytest-patterns.md must contain fixtures section\n"
            "Expected: Guidance on pytest fixtures (@pytest.fixture)\n"
            "See: plugins/autonomous-dev/agents/test-master.md for current patterns"
        )

        # Check for fixture decorator
        assert "@pytest.fixture" in content, (
            "pytest-patterns.md must include @pytest.fixture examples\n"
            "Expected: Show how to create and use pytest fixtures"
        )

    def test_pytest_patterns_contains_mocking_section(self):
        """Test pytest-patterns.md contains mocking guidance."""
        content = PYTEST_PATTERNS_FILE.read_text()

        # Check for mocking section
        assert "mock" in content.lower() or "Mock" in content, (
            "pytest-patterns.md must contain mocking section\n"
            "Expected: Guidance on unittest.mock patterns\n"
            "See: plugins/autonomous-dev/agents/test-master.md for current patterns"
        )

        # Check for common mock patterns
        mock_patterns = ["patch", "Mock", "mock_open"]
        found_patterns = [p for p in mock_patterns if p in content]
        assert len(found_patterns) >= 2, (
            f"pytest-patterns.md must include common mock patterns\n"
            f"Expected at least 2 of: {mock_patterns}\n"
            f"Found: {found_patterns}"
        )

    def test_pytest_patterns_contains_parametrization_section(self):
        """Test pytest-patterns.md contains parametrization guidance."""
        content = PYTEST_PATTERNS_FILE.read_text()

        # Check for parametrization section
        assert "parametrize" in content.lower() or "@pytest.mark.parametrize" in content, (
            "pytest-patterns.md must contain parametrization section\n"
            "Expected: Guidance on @pytest.mark.parametrize\n"
            "See: plugins/autonomous-dev/agents/test-master.md for current patterns"
        )

        # Check for parametrize decorator
        assert "@pytest.mark.parametrize" in content, (
            "pytest-patterns.md must include @pytest.mark.parametrize examples\n"
            "Expected: Show how to parametrize tests for multiple scenarios"
        )

    def test_coverage_strategies_file_exists(self):
        """Test coverage-strategies.md file exists in skills/testing-guide/ directory."""
        assert COVERAGE_STRATEGIES_FILE.exists(), (
            f"Skill enhancement file not found: {COVERAGE_STRATEGIES_FILE}\n"
            f"Expected: Create skills/testing-guide/coverage-strategies.md\n"
            f"See: Issue #65"
        )

    def test_coverage_strategies_contains_80_percent_guidance(self):
        """Test coverage-strategies.md contains 80%+ coverage guidance."""
        content = COVERAGE_STRATEGIES_FILE.read_text()

        # Check for coverage percentage guidance
        assert "80%" in content or "80 percent" in content.lower(), (
            "coverage-strategies.md must contain 80% coverage guidance\n"
            "Expected: Strategies for achieving 80%+ code coverage\n"
            "See: CLAUDE.md '80%+ coverage target' requirement"
        )

        # Check for coverage strategy keywords
        coverage_keywords = ["branch coverage", "edge case", "boundary condition", "error handling"]
        found_keywords = [k for k in coverage_keywords if k.lower() in content.lower()]
        assert len(found_keywords) >= 2, (
            f"coverage-strategies.md must include coverage strategy keywords\n"
            f"Expected at least 2 of: {coverage_keywords}\n"
            f"Found: {found_keywords}"
        )

    def test_arrange_act_assert_file_exists(self):
        """Test arrange-act-assert.md file exists in skills/testing-guide/ directory."""
        assert AAA_PATTERN_FILE.exists(), (
            f"Skill enhancement file not found: {AAA_PATTERN_FILE}\n"
            f"Expected: Create skills/testing-guide/arrange-act-assert.md\n"
            f"See: Issue #65"
        )

    def test_arrange_act_assert_contains_aaa_pattern(self):
        """Test arrange-act-assert.md contains AAA pattern guidance."""
        content = AAA_PATTERN_FILE.read_text()

        # Check for AAA pattern sections
        aaa_keywords = ["Arrange", "Act", "Assert"]
        for keyword in aaa_keywords:
            assert keyword in content, (
                f"arrange-act-assert.md must contain '{keyword}' section\n"
                "Expected: Full AAA pattern explanation with examples\n"
                "See: test-master agent prompt 'Arrange-Act-Assert pattern'"
            )

        # Check for example code
        assert "```python" in content or "```" in content, (
            "arrange-act-assert.md must include code examples\n"
            "Expected: Show AAA pattern in action with pytest examples"
        )

    def test_test_templates_directory_exists(self):
        """Test test-templates/ directory exists in skills/testing-guide/."""
        assert TEST_TEMPLATES_DIR.exists() and TEST_TEMPLATES_DIR.is_dir(), (
            f"Test templates directory not found: {TEST_TEMPLATES_DIR}\n"
            f"Expected: Create skills/testing-guide/test-templates/ directory\n"
            f"See: Issue #65 - 3 template files required"
        )

    def test_unit_test_template_exists(self):
        """Test unit-test-template.py exists in test-templates/ directory."""
        template_file = TEST_TEMPLATES_DIR / "unit-test-template.py"
        assert template_file.exists(), (
            f"Template file not found: {template_file}\n"
            f"Expected: Create test-templates/unit-test-template.py\n"
            f"See: Issue #65"
        )

    def test_integration_test_template_exists(self):
        """Test integration-test-template.py exists in test-templates/ directory."""
        template_file = TEST_TEMPLATES_DIR / "integration-test-template.py"
        assert template_file.exists(), (
            f"Template file not found: {template_file}\n"
            f"Expected: Create test-templates/integration-test-template.py\n"
            f"See: Issue #65"
        )

    def test_fixture_examples_template_exists(self):
        """Test fixture-examples.py exists in test-templates/ directory."""
        template_file = TEST_TEMPLATES_DIR / "fixture-examples.py"
        assert template_file.exists(), (
            f"Template file not found: {template_file}\n"
            f"Expected: Create test-templates/fixture-examples.py\n"
            f"See: Issue #65"
        )


class TestAgentIntegration:
    """Test agent prompts reference testing-guide skill."""

    def test_test_master_references_testing_guide_skill(self):
        """Test test-master.md references testing-guide skill in Relevant Skills section."""
        agent_file = AGENTS_DIR / "test-master.md"
        content = agent_file.read_text()

        # Check for Relevant Skills section
        assert "## Relevant Skills" in content or "Relevant Skills" in content, (
            "test-master.md must have 'Relevant Skills' section\n"
            "Expected: Section listing available skills for this agent"
        )

        # Check for testing-guide skill reference
        assert "testing-guide" in content, (
            "test-master.md must reference 'testing-guide' skill\n"
            "Expected: Add to Relevant Skills section for pytest patterns, coverage, AAA\n"
            "See: Issue #65 - consolidate testing patterns into skill"
        )

    def test_implementer_references_testing_guide_skill(self):
        """Test implementer.md references testing-guide skill in Relevant Skills section."""
        agent_file = AGENTS_DIR / "implementer.md"
        content = agent_file.read_text()

        # Check for Relevant Skills section
        assert "## Relevant Skills" in content or "Relevant Skills" in content, (
            "implementer.md must have 'Relevant Skills' section\n"
            "Expected: Section listing available skills for this agent"
        )

        # Check for testing-guide skill reference
        assert "testing-guide" in content, (
            "implementer.md must reference 'testing-guide' skill\n"
            "Expected: Add to Relevant Skills section for test implementation\n"
            "See: Issue #65 - consolidate testing patterns into skill"
        )

    def test_reviewer_references_testing_guide_skill(self):
        """Test reviewer.md references testing-guide skill in Relevant Skills section."""
        agent_file = AGENTS_DIR / "reviewer.md"
        content = agent_file.read_text()

        # Check for Relevant Skills section
        assert "## Relevant Skills" in content or "Relevant Skills" in content, (
            "reviewer.md must have 'Relevant Skills' section\n"
            "Expected: Section listing available skills for this agent"
        )

        # Check for testing-guide skill reference
        assert "testing-guide" in content, (
            "reviewer.md must reference 'testing-guide' skill\n"
            "Expected: Add to Relevant Skills section for test quality review\n"
            "See: Issue #65 - consolidate testing patterns into skill"
        )


class TestTokenMeasurement:
    """Test token counting for baseline and post-cleanup measurements."""

    def test_baseline_token_count_measured(self):
        """Test baseline token count is measured for 3 agents before cleanup."""
        # This test validates we can measure tokens before cleanup
        # Will use scripts/measure_agent_tokens.py pattern

        agents_to_measure = ["test-master.md", "implementer.md", "reviewer.md"]
        baseline_counts = {}

        for agent_name in agents_to_measure:
            agent_file = AGENTS_DIR / agent_name
            assert agent_file.exists(), f"Agent file not found: {agent_file}"

            content = agent_file.read_text()
            token_count = len(content) // 4  # ~4 chars per token approximation

            baseline_counts[agent_name] = token_count

        # Validate we got token counts for all 3 agents
        assert len(baseline_counts) == 3, (
            f"Expected token counts for 3 agents, got {len(baseline_counts)}\n"
            f"Agents measured: {list(baseline_counts.keys())}"
        )

        # Store baseline for comparison (in real implementation, this would be persisted)
        # For now, just validate the measurement works
        for agent_name, count in baseline_counts.items():
            assert count > 0, f"Token count for {agent_name} should be > 0, got {count}"

    def test_post_cleanup_shows_token_reduction(self):
        """Test post-cleanup token count shows 5-8% reduction."""
        # This test will FAIL until cleanup is implemented
        # Expected: ~190-210 tokens saved across 3 agents

        agents_to_measure = ["test-master.md", "implementer.md", "reviewer.md"]

        # Measure current token counts
        current_counts = {}
        for agent_name in agents_to_measure:
            agent_file = AGENTS_DIR / agent_name
            content = agent_file.read_text()
            current_counts[agent_name] = len(content) // 4

        # Expected baseline counts (approximate, from planner analysis)
        expected_baselines = {
            "test-master.md": 2500,  # ~80-100 lines to remove
            "implementer.md": 2000,  # ~40-60 lines to remove
            "reviewer.md": 2000,     # ~40-60 lines to remove
        }

        # Calculate expected token reduction (5-8% = 190-210 tokens)
        total_baseline = sum(expected_baselines.values())
        expected_min_reduction = int(total_baseline * 0.05)  # 5%
        expected_max_reduction = int(total_baseline * 0.08)  # 8%

        # This assertion will FAIL until cleanup is implemented
        total_current = sum(current_counts.values())
        actual_reduction = total_baseline - total_current

        assert actual_reduction >= expected_min_reduction, (
            f"Token reduction insufficient: {actual_reduction} tokens\n"
            f"Expected: {expected_min_reduction}-{expected_max_reduction} tokens (5-8%)\n"
            f"Baseline total: {total_baseline} tokens\n"
            f"Current total: {total_current} tokens\n"
            f"See: Issue #65 - consolidate testing patterns to achieve token reduction"
        )

        assert actual_reduction <= expected_max_reduction + 50, (
            f"Token reduction excessive: {actual_reduction} tokens\n"
            f"Expected: {expected_min_reduction}-{expected_max_reduction} tokens (5-8%)\n"
            f"Warning: Ensure essential testing guidance is preserved\n"
            f"See: Issue #65"
        )


class TestTemplateValidation:
    """Test template files are valid Python and follow pytest conventions."""

    def test_unit_test_template_is_valid_python(self):
        """Test unit-test-template.py is valid Python syntax."""
        template_file = TEST_TEMPLATES_DIR / "unit-test-template.py"
        content = template_file.read_text()

        # Validate Python syntax by attempting to compile
        try:
            compile(content, str(template_file), 'exec')
        except SyntaxError as e:
            pytest.fail(
                f"unit-test-template.py has invalid Python syntax:\n"
                f"Error: {e}\n"
                f"See: Issue #65 - templates must be valid Python"
            )

    def test_unit_test_template_follows_pytest_conventions(self):
        """Test unit-test-template.py follows pytest conventions."""
        template_file = TEST_TEMPLATES_DIR / "unit-test-template.py"
        content = template_file.read_text()

        # Check for pytest conventions
        pytest_patterns = [
            "import pytest",           # pytest import
            "def test_",               # test function naming
            "assert ",                 # assertions
        ]

        for pattern in pytest_patterns:
            assert pattern in content, (
                f"unit-test-template.py must include pytest pattern: {pattern}\n"
                f"Expected: Follow pytest conventions for unit tests\n"
                f"See: Issue #65"
            )

    def test_unit_test_template_demonstrates_aaa_pattern(self):
        """Test unit-test-template.py demonstrates Arrange-Act-Assert pattern."""
        template_file = TEST_TEMPLATES_DIR / "unit-test-template.py"
        content = template_file.read_text()

        # Check for AAA pattern comments or structure
        aaa_indicators = [
            "# Arrange" or "# ARRANGE",
            "# Act" or "# ACT",
            "# Assert" or "# ASSERT",
        ]

        # At least show AAA structure in comments or docstring
        has_aaa = any(
            indicator[0] in content or indicator[1] in content
            for indicator in aaa_indicators
        )

        assert has_aaa, (
            "unit-test-template.py must demonstrate AAA pattern\n"
            "Expected: Include # Arrange, # Act, # Assert comments\n"
            "See: skills/testing-guide/arrange-act-assert.md"
        )

    def test_integration_test_template_is_valid_python(self):
        """Test integration-test-template.py is valid Python syntax."""
        template_file = TEST_TEMPLATES_DIR / "integration-test-template.py"
        content = template_file.read_text()

        # Validate Python syntax by attempting to compile
        try:
            compile(content, str(template_file), 'exec')
        except SyntaxError as e:
            pytest.fail(
                f"integration-test-template.py has invalid Python syntax:\n"
                f"Error: {e}\n"
                f"See: Issue #65 - templates must be valid Python"
            )

    def test_integration_test_template_follows_pytest_conventions(self):
        """Test integration-test-template.py follows pytest conventions."""
        template_file = TEST_TEMPLATES_DIR / "integration-test-template.py"
        content = template_file.read_text()

        # Check for pytest conventions
        pytest_patterns = [
            "import pytest",           # pytest import
            "def test_",               # test function naming
            "assert ",                 # assertions
        ]

        for pattern in pytest_patterns:
            assert pattern in content, (
                f"integration-test-template.py must include pytest pattern: {pattern}\n"
                f"Expected: Follow pytest conventions for integration tests\n"
                f"See: Issue #65"
            )

    def test_integration_test_template_shows_component_interaction(self):
        """Test integration-test-template.py demonstrates component interaction."""
        template_file = TEST_TEMPLATES_DIR / "integration-test-template.py"
        content = template_file.read_text()

        # Check for integration test indicators
        integration_indicators = [
            "integration" in content.lower(),
            "component" in content.lower(),
            "workflow" in content.lower(),
            "@pytest.fixture" in content,  # Likely uses fixtures for setup
        ]

        found_indicators = sum(1 for indicator in integration_indicators if indicator)

        assert found_indicators >= 2, (
            "integration-test-template.py must demonstrate component interaction\n"
            f"Expected: At least 2 integration test patterns\n"
            f"Found: {found_indicators} indicators\n"
            "See: Issue #65"
        )

    def test_fixture_examples_is_valid_python(self):
        """Test fixture-examples.py is valid Python syntax."""
        template_file = TEST_TEMPLATES_DIR / "fixture-examples.py"
        content = template_file.read_text()

        # Validate Python syntax by attempting to compile
        try:
            compile(content, str(template_file), 'exec')
        except SyntaxError as e:
            pytest.fail(
                f"fixture-examples.py has invalid Python syntax:\n"
                f"Error: {e}\n"
                f"See: Issue #65 - templates must be valid Python"
            )

    def test_fixture_examples_demonstrates_pytest_fixtures(self):
        """Test fixture-examples.py demonstrates pytest fixtures."""
        template_file = TEST_TEMPLATES_DIR / "fixture-examples.py"
        content = template_file.read_text()

        # Check for fixture patterns
        fixture_patterns = [
            "import pytest",
            "@pytest.fixture",
            "def ",  # Fixture functions
        ]

        for pattern in fixture_patterns:
            assert pattern in content, (
                f"fixture-examples.py must include fixture pattern: {pattern}\n"
                f"Expected: Demonstrate pytest fixture creation and usage\n"
                f"See: Issue #65"
            )

        # Check for at least 2 fixture examples
        fixture_count = content.count("@pytest.fixture")
        assert fixture_count >= 2, (
            f"fixture-examples.py must demonstrate at least 2 fixtures\n"
            f"Found: {fixture_count} fixtures\n"
            "Expected: Show different fixture patterns (function, session, module scope)\n"
            "See: Issue #65"
        )


class TestSkillContentQuality:
    """Test skill content is comprehensive and high-quality."""

    def test_pytest_patterns_has_sufficient_content(self):
        """Test pytest-patterns.md has sufficient content (not just placeholder)."""
        content = PYTEST_PATTERNS_FILE.read_text()

        # Check for minimum content length (should be substantial)
        assert len(content) >= 1000, (
            f"pytest-patterns.md content too brief: {len(content)} characters\n"
            f"Expected: At least 1000 characters of guidance\n"
            f"Should include: Fixtures, mocking, parametrization sections with examples\n"
            f"See: Issue #65"
        )

        # Check for code examples
        code_block_count = content.count("```")
        assert code_block_count >= 4, (  # At least 2 code blocks (opening and closing)
            f"pytest-patterns.md must include code examples\n"
            f"Found: {code_block_count // 2} code blocks\n"
            f"Expected: At least 2 code examples\n"
            f"See: Issue #65"
        )

    def test_coverage_strategies_has_sufficient_content(self):
        """Test coverage-strategies.md has sufficient content (not just placeholder)."""
        content = COVERAGE_STRATEGIES_FILE.read_text()

        # Check for minimum content length
        assert len(content) >= 800, (
            f"coverage-strategies.md content too brief: {len(content)} characters\n"
            f"Expected: At least 800 characters of guidance\n"
            f"Should include: 80%+ coverage strategies, edge cases, boundary conditions\n"
            f"See: Issue #65"
        )

        # Check for actionable guidance
        strategy_keywords = ["strategy", "approach", "technique", "pattern"]
        found_keywords = [k for k in strategy_keywords if k in content.lower()]
        assert len(found_keywords) >= 2, (
            f"coverage-strategies.md must provide actionable strategies\n"
            f"Found keywords: {found_keywords}\n"
            f"See: Issue #65"
        )

    def test_arrange_act_assert_has_sufficient_content(self):
        """Test arrange-act-assert.md has sufficient content (not just placeholder)."""
        content = AAA_PATTERN_FILE.read_text()

        # Check for minimum content length
        assert len(content) >= 600, (
            f"arrange-act-assert.md content too brief: {len(content)} characters\n"
            f"Expected: At least 600 characters of guidance\n"
            f"Should include: AAA pattern explanation with examples\n"
            f"See: Issue #65"
        )

        # Check for all three phases explained
        phases = ["Arrange", "Act", "Assert"]
        for phase in phases:
            # Look for phase heading or explanation
            phase_explained = (
                f"## {phase}" in content or
                f"### {phase}" in content or
                f"**{phase}**" in content or
                f"# {phase}" in content
            )
            assert phase_explained, (
                f"arrange-act-assert.md must explain {phase} phase\n"
                f"Expected: Section or emphasis on {phase} phase\n"
                f"See: Issue #65"
            )


if __name__ == "__main__":
    # Run tests with pytest
    pytest.main([__file__, "-v"])
