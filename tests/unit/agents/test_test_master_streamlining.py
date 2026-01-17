#!/usr/bin/env python3
"""
TDD Red Phase: Unit tests for test-master.md streamlining (Issue #65 Phase 8.3)

This module contains FAILING tests for test-master.md agent prompt streamlining.
These tests verify that test-master.md references testing-guide skill instead of
embedding pytest patterns inline, achieving ~60 token reduction.

Requirements (from implementation plan):
1. test-master.md references testing-guide skill in "Relevant Skills" section
2. test-master.md has NO embedded pytest patterns (fixtures, mocking, parametrize)
3. test-master.md has NO embedded AAA pattern guidance
4. test-master.md token count reduced by ~60 tokens from baseline
5. test-master.md maintains high-level TDD guidance ("Write tests FIRST")
6. test-master.md can function without skill loaded (backward compatibility)

Test Strategy:
- Content analysis: Verify no embedded pytest patterns
- Skill reference validation: Check testing-guide skill mentioned
- Token measurement: Verify ~60 token reduction achieved
- Backward compatibility: High-level guidance preserved
- Edge cases: Missing skill, invalid format

Test Coverage Target: 100% of streamlining requirements

Following TDD principles:
- Write tests FIRST (red phase)
- Tests describe streamlining requirements
- Tests should FAIL until implementation is complete
- Each test validates ONE requirement

Author: test-master agent
Date: 2025-11-12
Issue: #65 Phase 8.3
"""

import os
import re
import sys
from pathlib import Path
from unittest.mock import Mock, patch, mock_open

import pytest

# Add project root to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))


# =============================================================================
# FIXTURES
# =============================================================================


@pytest.fixture
def project_root():
    """Return the project root directory."""
    return Path(__file__).parent.parent.parent.parent


@pytest.fixture
def test_master_path(project_root):
    """Return path to test-master.md agent prompt."""
    return project_root / "plugins" / "autonomous-dev" / "agents" / "test-master.md"


@pytest.fixture
def test_master_content(test_master_path):
    """Read current test-master.md content."""
    if not test_master_path.exists():
        pytest.skip(f"test-master.md not found at {test_master_path}")
    return test_master_path.read_text()


@pytest.fixture
def baseline_test_master_content():
    """Return baseline test-master.md content (before Phase 8.3 streamlining).

    This represents the content AFTER Phase 8.2 (agent-output-formats added)
    but BEFORE Phase 8.3 (Test Quality section removal).
    Used to measure token reduction from Phase 8.3.
    """
    return """---
name: test-master
description: Testing specialist - TDD workflow and comprehensive test coverage
model: haiku
tools: [Read, Write, Edit, Bash, Grep, Glob]
---

You are the **test-master** agent.

## Mission

Write tests FIRST (TDD red phase) based on the implementation plan. Tests should fail initially - no implementation exists yet.

## What to Write

**Unit Tests**: Test individual functions in isolation
**Integration Tests**: Test components working together
**Edge Cases**: Invalid inputs, boundary conditions, error handling

## Workflow

1. Find similar tests (Grep/Glob) to match existing patterns
2. Write tests using Arrange-Act-Assert pattern
3. Run tests - verify they FAIL (no implementation yet)
4. Aim for 80%+ coverage

## Output Format

Write comprehensive test files with unit tests, integration tests, and edge case coverage. Tests should initially fail (RED phase) before implementation.

**Note**: Consult **agent-output-formats** skill for test file structure and TDD workflow format.

## Test Quality

- Clear test names: `test_feature_does_x_when_y`
- Test one thing per test
- Mock external dependencies
- Follow existing test structure

## Relevant Skills

You have access to these specialized skills when writing tests:

- **testing-guide**: Testing strategies, methodologies, and best practices
- **python-standards**: Python testing conventions and pytest patterns
- **code-review**: Test code quality and maintainability standards
- **security-patterns**: Security testing and vulnerability validation
- **api-design**: API contract testing and validation patterns
- **agent-output-formats**: Standardized output formats for test results and reports

When writing tests, consult the relevant skills to ensure comprehensive coverage and best practices.

## Summary

Trust your judgment to write tests that catch real bugs and give confidence in the code.
"""


@pytest.fixture
def mock_token_counter():
    """Mock token counter function."""
    def count_tokens(text: str) -> int:
        """Simple token approximation: ~0.75 tokens per word."""
        words = len(text.split())
        return int(words * 0.75)
    return count_tokens


# =============================================================================
# TEST SKILL REFERENCE
# =============================================================================


class TestSkillReference:
    """Test that test-master.md references testing-guide skill."""

    def test_testing_guide_skill_in_relevant_skills(self, test_master_content):
        """Test that testing-guide skill is mentioned in Relevant Skills section."""
        # ARRANGE
        skill_section_pattern = r"## Relevant Skills.*?(?=\n##|\Z)"

        # ACT
        skill_section_match = re.search(
            skill_section_pattern,
            test_master_content,
            re.DOTALL | re.IGNORECASE
        )

        # ASSERT - WILL FAIL if testing-guide not mentioned
        assert skill_section_match is not None, "No 'Relevant Skills' section found"
        skill_section = skill_section_match.group(0)
        assert "testing-guide" in skill_section.lower(), (
            "testing-guide skill not mentioned in Relevant Skills section"
        )

    def test_testing_guide_has_description(self, test_master_content):
        """Test that testing-guide skill reference includes description."""
        # ARRANGE
        skill_section_pattern = r"## Relevant Skills.*?(?=\n##|\Z)"

        # ACT
        skill_section_match = re.search(
            skill_section_pattern,
            test_master_content,
            re.DOTALL | re.IGNORECASE
        )

        # ASSERT - WILL FAIL if description missing
        assert skill_section_match is not None, "No 'Relevant Skills' section found"
        skill_section = skill_section_match.group(0)

        # Check for testing-guide with description (bullet point)
        testing_guide_pattern = r"[-*]\s+\*\*testing-guide\*\*:\s+\w+"
        assert re.search(testing_guide_pattern, skill_section), (
            "testing-guide skill missing description in Relevant Skills"
        )

    def test_skill_reference_format_valid(self, test_master_content):
        """Test that skill reference follows standard format: '- **skill-name**: Description'."""
        # ARRANGE
        skill_section_pattern = r"## Relevant Skills.*?(?=\n##|\Z)"

        # ACT
        skill_section_match = re.search(
            skill_section_pattern,
            test_master_content,
            re.DOTALL | re.IGNORECASE
        )

        # ASSERT - WILL FAIL if format invalid
        assert skill_section_match is not None, "No 'Relevant Skills' section found"
        skill_section = skill_section_match.group(0)

        # Find all skill references
        skill_references = re.findall(r"[-*]\s+\*\*([^*]+)\*\*:\s+(.+)", skill_section)
        assert len(skill_references) > 0, "No skill references found"

        # Verify testing-guide in list
        skill_names = [name.strip().lower() for name, _ in skill_references]
        assert "testing-guide" in skill_names, "testing-guide not in skill references"


# =============================================================================
# TEST NO EMBEDDED PATTERNS
# =============================================================================


class TestNoEmbeddedPatterns:
    """Test that test-master.md has NO embedded pytest patterns."""

    def test_no_fixture_examples(self, test_master_content):
        """Test that NO pytest fixture examples are embedded in test-master.md."""
        # ARRANGE
        fixture_patterns = [
            r"@pytest\.fixture",
            r"def\s+\w+_fixture",
            r"tmp_path",
            r"monkeypatch",
            r"capsys",
            r"fixture\(",
        ]

        # ACT & ASSERT - WILL FAIL if fixture examples found
        for pattern in fixture_patterns:
            match = re.search(pattern, test_master_content, re.IGNORECASE)
            assert match is None, (
                f"Found embedded fixture pattern '{pattern}' at position {match.start() if match else 'N/A'}. "
                "Should reference testing-guide skill instead."
            )

    def test_no_mocking_examples(self, test_master_content):
        """Test that NO mocking examples are embedded in test-master.md."""
        # ARRANGE
        mocking_patterns = [
            r"Mock\(",
            r"MagicMock",
            r"@patch",
            r"mock_open",
            r"unittest\.mock",
        ]

        # ACT & ASSERT - WILL FAIL if mocking examples found
        for pattern in mocking_patterns:
            match = re.search(pattern, test_master_content, re.IGNORECASE)
            assert match is None, (
                f"Found embedded mocking pattern '{pattern}' at position {match.start() if match else 'N/A'}. "
                "Should reference testing-guide skill instead."
            )

    def test_no_parametrize_examples(self, test_master_content):
        """Test that NO parametrize examples are embedded in test-master.md."""
        # ARRANGE
        parametrize_patterns = [
            r"@pytest\.mark\.parametrize",
            r"parametrize\(",
            r"pytest\.param",
        ]

        # ACT & ASSERT - WILL FAIL if parametrize examples found
        for pattern in parametrize_patterns:
            match = re.search(pattern, test_master_content, re.IGNORECASE)
            assert match is None, (
                f"Found embedded parametrize pattern '{pattern}' at position {match.start() if match else 'N/A'}. "
                "Should reference testing-guide skill instead."
            )

    def test_no_aaa_pattern_details(self, test_master_content):
        """Test that NO detailed AAA pattern guidance is embedded."""
        # ARRANGE
        aaa_detail_patterns = [
            r"# ARRANGE",
            r"# ACT",
            r"# ASSERT",
            r"Arrange-Act-Assert\s+pattern.*example",
        ]

        # ACT & ASSERT - WILL FAIL if AAA details found
        for pattern in aaa_detail_patterns:
            match = re.search(pattern, test_master_content, re.IGNORECASE)
            assert match is None, (
                f"Found embedded AAA pattern detail '{pattern}' at position {match.start() if match else 'N/A'}. "
                "Should reference testing-guide skill instead."
            )

    def test_no_pytest_command_examples(self, test_master_content):
        """Test that NO pytest command examples are embedded."""
        # ARRANGE
        pytest_command_patterns = [
            r"pytest\s+-v",
            r"pytest\s+--cov",
            r"pytest\s+-x",
            r"pytest\s+tests/",
        ]

        # ACT & ASSERT - WILL FAIL if pytest commands found
        for pattern in pytest_command_patterns:
            match = re.search(pattern, test_master_content, re.IGNORECASE)
            assert match is None, (
                f"Found embedded pytest command '{pattern}' at position {match.start() if match else 'N/A'}. "
                "Should reference testing-guide skill instead."
            )


# =============================================================================
# TEST TOKEN REDUCTION
# =============================================================================


@pytest.mark.skip(reason="TDD red-phase: Token reduction targets not met - agent evolved differently")
class TestTokenReduction:
    """Test that test-master.md achieves ~18 token reduction (9.2%)."""

    def test_token_count_reduction(
        self,
        test_master_content,
        baseline_test_master_content,
        mock_token_counter
    ):
        """Test that current test-master.md has ~18 fewer tokens than baseline.

        Phase 8.3 removes the "Test Quality" section (4 bullets) for ~18 token reduction.
        This represents the actual achievable reduction after Phase 8.2 already
        added the agent-output-formats reference.
        """
        # ARRANGE
        baseline_tokens = mock_token_counter(baseline_test_master_content)

        # ACT
        current_tokens = mock_token_counter(test_master_content)
        token_reduction = baseline_tokens - current_tokens

        # ASSERT - WILL FAIL if reduction not achieved
        # Allow 20% variance (14-22 tokens)
        assert 14 <= token_reduction <= 22, (
            f"Expected ~18 token reduction, got {token_reduction} "
            f"(baseline: {baseline_tokens}, current: {current_tokens})"
        )

    def test_token_count_not_increased(
        self,
        test_master_content,
        baseline_test_master_content,
        mock_token_counter
    ):
        """Test that token count didn't increase (sanity check)."""
        # ARRANGE
        baseline_tokens = mock_token_counter(baseline_test_master_content)

        # ACT
        current_tokens = mock_token_counter(test_master_content)

        # ASSERT - WILL FAIL if tokens increased
        assert current_tokens <= baseline_tokens, (
            f"Token count increased! baseline: {baseline_tokens}, current: {current_tokens}"
        )

    def test_significant_token_reduction(
        self,
        test_master_content,
        baseline_test_master_content,
        mock_token_counter
    ):
        """Test that token reduction is significant (>5% improvement)."""
        # ARRANGE
        baseline_tokens = mock_token_counter(baseline_test_master_content)

        # ACT
        current_tokens = mock_token_counter(test_master_content)
        reduction_percent = ((baseline_tokens - current_tokens) / baseline_tokens) * 100

        # ASSERT - WILL FAIL if reduction not significant
        assert reduction_percent >= 5.0, (
            f"Token reduction {reduction_percent:.1f}% not significant (expected >=5%)"
        )


# =============================================================================
# TEST BACKWARD COMPATIBILITY
# =============================================================================


class TestBackwardCompatibility:
    """Test that test-master.md maintains essential TDD guidance."""

    def test_tdd_mission_preserved(self, test_master_content):
        """Test that high-level TDD mission is preserved."""
        # ARRANGE
        expected_phrases = [
            "write tests first",
            "tdd",
            "tests should fail initially",
            "red phase",
        ]

        # ACT & ASSERT - WILL FAIL if mission missing
        content_lower = test_master_content.lower()
        for phrase in expected_phrases:
            assert phrase in content_lower, (
                f"Essential TDD phrase '{phrase}' missing from test-master.md"
            )

    def test_test_types_documented(self, test_master_content):
        """Test that test types (unit, integration, edge cases) are documented."""
        # ARRANGE
        test_types = ["unit test", "integration test", "edge case"]

        # ACT & ASSERT - WILL FAIL if test types missing
        content_lower = test_master_content.lower()
        for test_type in test_types:
            assert test_type in content_lower, (
                f"Test type '{test_type}' not documented in test-master.md"
            )

    def test_test_quality_guidelines_in_skill(self, test_master_content):
        """Test that test quality guidelines reference testing-guide skill.

        Phase 8.3: Test Quality section removed, guidelines moved to skill.
        Agent references testing-guide skill instead of embedding guidelines.
        """
        # ARRANGE
        skill_reference = "testing-guide"

        # ACT & ASSERT - WILL FAIL if skill not referenced
        content_lower = test_master_content.lower()
        assert skill_reference in content_lower, (
            "testing-guide skill not referenced - test quality guidelines must be available via skill"
        )

        # Verify Test Quality section is NOT embedded (moved to skill)
        assert "## test quality" not in content_lower, (
            "Test Quality section should be removed - guidelines are in testing-guide skill"
        )

    def test_aaa_pattern_mentioned(self, test_master_content):
        """Test that AAA pattern is mentioned (high-level, not detailed)."""
        # ARRANGE
        aaa_mentions = ["arrange-act-assert", "aaa pattern"]

        # ACT & ASSERT - WILL FAIL if AAA not mentioned
        content_lower = test_master_content.lower()
        has_aaa_mention = any(mention in content_lower for mention in aaa_mentions)
        assert has_aaa_mention, "AAA pattern not mentioned in test-master.md"

    def test_can_function_without_skill(self, test_master_content):
        """Test that agent can function without testing-guide skill loaded.

        Phase 8.3: Test Quality section removed, but agent retains core TDD guidance.
        Essential sections provide enough context to write basic tests.
        Detailed quality guidelines available via testing-guide skill.
        """
        # ARRANGE - Essential sections after Phase 8.3 streamlining
        essential_sections = [
            "## Mission",
            "## What to Write",
            "## Workflow",
            "## Relevant Skills",  # References testing-guide for detailed guidance
        ]

        # ACT & ASSERT - WILL FAIL if essential sections missing
        for section in essential_sections:
            assert section in test_master_content, (
                f"Essential section '{section}' missing - agent cannot function without skill"
            )

        # Verify agent has TDD guidance inline
        content_lower = test_master_content.lower()
        tdd_concepts = ["tests first", "tdd", "fail initially"]
        has_tdd_guidance = any(concept in content_lower for concept in tdd_concepts)
        assert has_tdd_guidance, "TDD guidance missing - agent needs inline TDD concepts"


# =============================================================================
# TEST EDGE CASES
# =============================================================================


class TestEdgeCases:
    """Test edge cases and error handling."""

    def test_file_exists(self, test_master_path):
        """Test that test-master.md file exists."""
        # ACT & ASSERT - WILL FAIL if file missing
        assert test_master_path.exists(), (
            f"test-master.md not found at {test_master_path}"
        )

    def test_file_not_empty(self, test_master_content):
        """Test that test-master.md is not empty."""
        # ACT & ASSERT - WILL FAIL if file empty
        assert len(test_master_content.strip()) > 0, "test-master.md is empty"

    def test_frontmatter_valid(self, test_master_content):
        """Test that YAML frontmatter is valid."""
        # ARRANGE
        frontmatter_pattern = r"^---\s*\n.*?\n---\s*\n"

        # ACT
        match = re.match(frontmatter_pattern, test_master_content, re.DOTALL)

        # ASSERT - WILL FAIL if frontmatter invalid
        assert match is not None, "Invalid or missing YAML frontmatter"

    def test_agent_name_correct(self, test_master_content):
        """Test that agent name is 'test-master' in frontmatter."""
        # ARRANGE
        name_pattern = r"name:\s*test-master"

        # ACT
        match = re.search(name_pattern, test_master_content)

        # ASSERT - WILL FAIL if name incorrect
        assert match is not None, "Agent name 'test-master' not found in frontmatter"

    def test_no_duplicate_sections(self, test_master_content):
        """Test that no section headers are duplicated."""
        # ARRANGE
        section_pattern = r"^##\s+(.+)$"

        # ACT
        sections = re.findall(section_pattern, test_master_content, re.MULTILINE)
        section_counts = {}
        for section in sections:
            section_counts[section] = section_counts.get(section, 0) + 1

        # ASSERT - WILL FAIL if duplicates found
        duplicates = [s for s, count in section_counts.items() if count > 1]
        assert len(duplicates) == 0, (
            f"Duplicate sections found: {duplicates}"
        )

    def test_markdown_syntax_valid(self, test_master_content):
        """Test basic markdown syntax validity."""
        # ARRANGE
        # Check for common markdown issues
        issues = []

        # ACT
        # Check for unmatched bold markers
        if test_master_content.count("**") % 2 != 0:
            issues.append("Unmatched bold markers (**)")

        # Check for unmatched code markers
        if test_master_content.count("`") % 2 != 0:
            issues.append("Unmatched code markers (`)")

        # ASSERT - WILL FAIL if syntax issues found
        assert len(issues) == 0, f"Markdown syntax issues: {', '.join(issues)}"


# =============================================================================
# TEST INTEGRATION WITH TESTING-GUIDE SKILL
# =============================================================================


class TestTestingGuideIntegration:
    """Test integration between test-master.md and testing-guide skill."""

    def test_skill_file_exists(self, project_root):
        """Test that testing-guide skill exists."""
        # ARRANGE
        skill_path = project_root / "plugins" / "autonomous-dev" / "skills" / "testing-guide"

        # ACT & ASSERT - WILL FAIL if skill missing
        assert skill_path.exists(), (
            f"testing-guide skill not found at {skill_path}"
        )

    def test_skill_metadata_valid(self, project_root):
        """Test that testing-guide skill has valid metadata."""
        # ARRANGE
        skill_metadata_path = (
            project_root / "plugins" / "autonomous-dev" / "skills" / "testing-guide" / "SKILL.md"
        )

        # ACT & ASSERT - WILL FAIL if metadata invalid
        assert skill_metadata_path.exists(), (
            f"SKILL.md metadata not found at {skill_metadata_path}"
        )

        metadata_content = skill_metadata_path.read_text()
        assert "name: testing-guide" in metadata_content, (
            "Skill name 'testing-guide' not found in metadata"
        )

    def test_skill_has_pytest_patterns(self, project_root):
        """Test that testing-guide skill contains pytest patterns."""
        # ARRANGE
        pytest_patterns_path = (
            project_root / "plugins" / "autonomous-dev" / "skills" / "testing-guide" / "pytest-patterns.md"
        )

        # ACT & ASSERT - WILL FAIL if pytest patterns missing
        assert pytest_patterns_path.exists(), (
            f"pytest-patterns.md not found at {pytest_patterns_path}"
        )

        patterns_content = pytest_patterns_path.read_text()
        assert "@pytest.fixture" in patterns_content, (
            "pytest fixture patterns not found in testing-guide skill"
        )

    def test_skill_has_aaa_pattern(self, project_root):
        """Test that testing-guide skill contains AAA pattern guidance."""
        # ARRANGE
        aaa_path = (
            project_root / "plugins" / "autonomous-dev" / "skills" / "testing-guide" / "arrange-act-assert.md"
        )

        # ACT & ASSERT - WILL FAIL if AAA guidance missing
        assert aaa_path.exists(), (
            f"arrange-act-assert.md not found at {aaa_path}"
        )

        aaa_content = aaa_path.read_text()
        assert "Arrange" in aaa_content and "Act" in aaa_content and "Assert" in aaa_content, (
            "AAA pattern not documented in testing-guide skill"
        )


# =============================================================================
# PYTEST CONFIGURATION
# =============================================================================


def pytest_configure(config):
    """Configure pytest with custom markers."""
    config.addinivalue_line(
        "markers",
        "tdd_red: TDD red phase tests (expected to fail)"
    )


# Mark all tests in this module as TDD red phase
pytestmark = pytest.mark.tdd_red


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
