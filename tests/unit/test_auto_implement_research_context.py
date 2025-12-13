#!/usr/bin/env python3
"""
TDD Tests for Auto-Implement Research Context Injection (FAILING - Red Phase)

This module contains FAILING tests for the auto-implement.md command that will
inject research context (implementation_guidance and testing_guidance) to
test-master and implementer agents.

Feature Requirements (from implementation plan):
1. auto-implement.md contains test-master context injection section
2. auto-implement.md contains implementer context injection section
3. Context injection includes both codebase patterns (researcher-local) and external guidance (researcher-web)
4. Context sections reference implementation_guidance and testing_guidance fields
5. Preserves existing STEP structure and parallel research workflow

Test Coverage Target: 100% of context injection paths

Following TDD principles:
- Write tests FIRST (red phase)
- Tests describe context injection requirements
- Tests should FAIL until auto-implement.md is updated
- Each test validates ONE injection requirement

Author: test-master agent
Date: 2025-12-13
Phase: TDD Red Phase
"""

import pytest
from pathlib import Path
from typing import List
import re


class TestAutoImplementCommandStructure:
    """Test auto-implement.md command file structure and content."""

    @pytest.fixture
    def auto_implement_file(self) -> Path:
        """Get path to auto-implement.md command file."""
        # Navigate from tests/unit/ to plugins/autonomous-dev/commands/
        test_file = Path(__file__)
        repo_root = test_file.parent.parent.parent
        command_file = repo_root / "plugins" / "autonomous-dev" / "commands" / "auto-implement.md"

        assert command_file.exists(), \
            f"auto-implement.md command file should exist at {command_file}"

        return command_file

    @pytest.fixture
    def auto_implement_content(self, auto_implement_file: Path) -> str:
        """Read auto-implement.md file content."""
        return auto_implement_file.read_text()

    def test_auto_implement_has_step_1_parallel_research(self, auto_implement_content: str):
        """
        Test that auto-implement.md has STEP 1 for parallel research.

        EXISTING STRUCTURE: Verify parallel research step exists.
        Expected: STEP 1 section with researcher-local and researcher-web.
        """
        assert "STEP 1: Parallel Research" in auto_implement_content, \
            "auto-implement.md must have 'STEP 1: Parallel Research' section"

        assert "researcher-local" in auto_implement_content, \
            "STEP 1 must reference researcher-local agent"

        assert "researcher-web" in auto_implement_content, \
            "STEP 1 must reference researcher-web agent"

    def test_auto_implement_has_step_1_1_merge_research(self, auto_implement_content: str):
        """
        Test that auto-implement.md has STEP 1.1 for merging research findings.

        EXISTING STRUCTURE: Verify research merge step exists.
        Expected: STEP 1.1 section that combines local and web research.
        """
        assert "STEP 1.1: Merge Research Findings" in auto_implement_content, \
            "auto-implement.md must have 'STEP 1.1: Merge Research Findings' section"

        assert "Combine:" in auto_implement_content, \
            "STEP 1.1 should describe how to combine research"


class TestTestMasterContextInjection:
    """Test that auto-implement.md injects research context to test-master agent."""

    @pytest.fixture
    def auto_implement_file(self) -> Path:
        """Get path to auto-implement.md command file."""
        test_file = Path(__file__)
        repo_root = test_file.parent.parent.parent
        command_file = repo_root / "plugins" / "autonomous-dev" / "commands" / "auto-implement.md"
        return command_file

    @pytest.fixture
    def auto_implement_content(self, auto_implement_file: Path) -> str:
        """Read auto-implement.md file content."""
        return auto_implement_file.read_text()

    def test_auto_implement_has_test_master_step(self, auto_implement_content: str):
        """
        Test that auto-implement.md has a STEP for invoking test-master.

        EXISTING STRUCTURE: Verify test-master invocation step exists.
        Expected: STEP referencing test-master agent (likely STEP 3).
        """
        # Look for test-master in any STEP
        assert "test-master" in auto_implement_content, \
            "auto-implement.md must reference test-master agent"

        # Should have a STEP section that invokes test-master
        assert re.search(r'STEP \d+:.*test', auto_implement_content, re.IGNORECASE), \
            "auto-implement.md should have a STEP for testing/test-master"

    def test_auto_implement_injects_codebase_testing_guidance_to_test_master(self, auto_implement_content: str):
        """
        Test that auto-implement.md injects codebase testing_guidance to test-master.

        NEW FEATURE: Context injection from researcher-local.
        Expected: test-master prompt includes testing_guidance fields.
        """
        # Should reference testing_guidance from researcher-local
        assert "testing_guidance" in auto_implement_content or "testing guidance" in auto_implement_content.lower(), \
            "auto-implement.md must reference testing_guidance for test-master context"

        # Should mention test file patterns
        assert "test_file_patterns" in auto_implement_content or "test file pattern" in auto_implement_content.lower(), \
            "auto-implement.md should inject test_file_patterns to test-master"

    def test_auto_implement_injects_edge_cases_to_test_master(self, auto_implement_content: str):
        """
        Test that auto-implement.md injects edge_cases_to_test to test-master.

        NEW FEATURE: Context injection from researcher-local.
        Expected: test-master prompt includes edge_cases_to_test.
        """
        # Should reference edge cases from research
        assert "edge_cases_to_test" in auto_implement_content or "edge case" in auto_implement_content.lower(), \
            "auto-implement.md should inject edge_cases_to_test to test-master"

    def test_auto_implement_injects_mocking_patterns_to_test_master(self, auto_implement_content: str):
        """
        Test that auto-implement.md injects mocking_patterns to test-master.

        NEW FEATURE: Context injection from researcher-local.
        Expected: test-master prompt includes mocking_patterns.
        """
        # Should reference mocking patterns from research
        assert "mocking_patterns" in auto_implement_content or "mocking pattern" in auto_implement_content.lower(), \
            "auto-implement.md should inject mocking_patterns to test-master"

    def test_auto_implement_injects_web_testing_guidance_to_test_master(self, auto_implement_content: str):
        """
        Test that auto-implement.md injects web testing_guidance to test-master.

        NEW FEATURE: Context injection from researcher-web.
        Expected: test-master prompt includes testing_frameworks and coverage_recommendations.
        """
        # Should reference testing frameworks from web research
        assert "testing_frameworks" in auto_implement_content or "testing framework" in auto_implement_content.lower(), \
            "auto-implement.md should inject testing_frameworks to test-master"

        # Should reference coverage recommendations
        assert "coverage_recommendations" in auto_implement_content or "coverage recommendation" in auto_implement_content.lower(), \
            "auto-implement.md should inject coverage_recommendations to test-master"

    def test_auto_implement_injects_testing_antipatterns_to_test_master(self, auto_implement_content: str):
        """
        Test that auto-implement.md injects testing_antipatterns to test-master.

        NEW FEATURE: Context injection from researcher-web.
        Expected: test-master prompt includes testing_antipatterns.
        """
        # Should reference testing antipatterns from web research
        assert "testing_antipatterns" in auto_implement_content or "testing antipattern" in auto_implement_content.lower(), \
            "auto-implement.md should inject testing_antipatterns to test-master"


class TestImplementerContextInjection:
    """Test that auto-implement.md injects research context to implementer agent."""

    @pytest.fixture
    def auto_implement_file(self) -> Path:
        """Get path to auto-implement.md command file."""
        test_file = Path(__file__)
        repo_root = test_file.parent.parent.parent
        command_file = repo_root / "plugins" / "autonomous-dev" / "commands" / "auto-implement.md"
        return command_file

    @pytest.fixture
    def auto_implement_content(self, auto_implement_file: Path) -> str:
        """Read auto-implement.md file content."""
        return auto_implement_file.read_text()

    def test_auto_implement_has_implementer_step(self, auto_implement_content: str):
        """
        Test that auto-implement.md has a STEP for invoking implementer.

        EXISTING STRUCTURE: Verify implementer invocation step exists.
        Expected: STEP referencing implementer agent (likely STEP 4).
        """
        # Look for implementer in any STEP
        assert "implementer" in auto_implement_content, \
            "auto-implement.md must reference implementer agent"

        # Should have a STEP section that invokes implementer
        assert re.search(r'STEP \d+:.*implement', auto_implement_content, re.IGNORECASE), \
            "auto-implement.md should have a STEP for implementation/implementer"

    def test_auto_implement_injects_codebase_implementation_guidance_to_implementer(self, auto_implement_content: str):
        """
        Test that auto-implement.md injects codebase implementation_guidance to implementer.

        NEW FEATURE: Context injection from researcher-local.
        Expected: implementer prompt includes implementation_guidance fields.
        """
        # Should reference implementation_guidance from researcher-local
        assert "implementation_guidance" in auto_implement_content or "implementation guidance" in auto_implement_content.lower(), \
            "auto-implement.md must reference implementation_guidance for implementer context"

        # Should mention reusable functions
        assert "reusable_functions" in auto_implement_content or "reusable function" in auto_implement_content.lower(), \
            "auto-implement.md should inject reusable_functions to implementer"

    def test_auto_implement_injects_import_patterns_to_implementer(self, auto_implement_content: str):
        """
        Test that auto-implement.md injects import_patterns to implementer.

        NEW FEATURE: Context injection from researcher-local.
        Expected: implementer prompt includes import_patterns.
        """
        # Should reference import patterns from research
        assert "import_patterns" in auto_implement_content or "import pattern" in auto_implement_content.lower(), \
            "auto-implement.md should inject import_patterns to implementer"

    def test_auto_implement_injects_error_handling_patterns_to_implementer(self, auto_implement_content: str):
        """
        Test that auto-implement.md injects error_handling_patterns to implementer.

        NEW FEATURE: Context injection from researcher-local.
        Expected: implementer prompt includes error_handling_patterns.
        """
        # Should reference error handling patterns from research
        assert "error_handling_patterns" in auto_implement_content or "error handling pattern" in auto_implement_content.lower(), \
            "auto-implement.md should inject error_handling_patterns to implementer"

    def test_auto_implement_injects_web_implementation_guidance_to_implementer(self, auto_implement_content: str):
        """
        Test that auto-implement.md injects web implementation_guidance to implementer.

        NEW FEATURE: Context injection from researcher-web.
        Expected: implementer prompt includes design_patterns and performance_tips.
        """
        # Should reference design patterns from web research
        assert "design_patterns" in auto_implement_content or "design pattern" in auto_implement_content.lower(), \
            "auto-implement.md should inject design_patterns to implementer"

        # Should reference performance tips
        assert "performance_tips" in auto_implement_content or "performance tip" in auto_implement_content.lower(), \
            "auto-implement.md should inject performance_tips to implementer"

    def test_auto_implement_injects_library_integration_tips_to_implementer(self, auto_implement_content: str):
        """
        Test that auto-implement.md injects library_integration_tips to implementer.

        NEW FEATURE: Context injection from researcher-web.
        Expected: implementer prompt includes library_integration_tips.
        """
        # Should reference library integration tips from web research
        assert "library_integration_tips" in auto_implement_content or "library integration" in auto_implement_content.lower(), \
            "auto-implement.md should inject library_integration_tips to implementer"


class TestContextInjectionStructure:
    """Test the structure and organization of context injection in auto-implement.md."""

    @pytest.fixture
    def auto_implement_file(self) -> Path:
        """Get path to auto-implement.md command file."""
        test_file = Path(__file__)
        repo_root = test_file.parent.parent.parent
        command_file = repo_root / "plugins" / "autonomous-dev" / "commands" / "auto-implement.md"
        return command_file

    @pytest.fixture
    def auto_implement_content(self, auto_implement_file: Path) -> str:
        """Read auto-implement.md file content."""
        return auto_implement_file.read_text()

    def test_context_injection_includes_both_local_and_web_research(self, auto_implement_content: str):
        """
        Test that context injection combines both researcher-local and researcher-web findings.

        NEW FEATURE: Unified context from both research agents.
        Expected: References to both codebase patterns and external guidance.
        """
        # Should reference local codebase context
        assert "codebase" in auto_implement_content.lower() or "local" in auto_implement_content.lower(), \
            "auto-implement.md should reference local codebase context"

        # Should reference external/web guidance
        assert "external" in auto_implement_content.lower() or "web" in auto_implement_content.lower() or "best practice" in auto_implement_content.lower(), \
            "auto-implement.md should reference external/web guidance"

    def test_context_injection_preserves_step_order(self, auto_implement_content: str):
        """
        Test that context injection doesn't break existing STEP order.

        BACKWARD COMPATIBILITY: Ensure STEP sequence is maintained.
        Expected: Steps proceed in logical order (research → test → implement).
        """
        # Extract step numbers
        steps = re.findall(r'STEP (\d+(?:\.\d+)?)', auto_implement_content)

        assert len(steps) > 0, \
            "auto-implement.md should have numbered STEP sections"

        # Verify steps are in ascending order (allowing decimals like 1.1, 1.2)
        step_numbers = [float(s) for s in steps]
        assert step_numbers == sorted(step_numbers), \
            "STEPs should be in ascending order"

    def test_context_injection_has_clear_section_headers(self, auto_implement_content: str):
        """
        Test that context injection sections have clear headers.

        READABILITY: Ensure context sections are well-organized.
        Expected: Headers indicate what context is being passed.
        """
        # Should have sections explaining what context is passed
        assert re.search(r'(context|guidance|research)', auto_implement_content, re.IGNORECASE), \
            "auto-implement.md should have clear context/guidance sections"

    def test_context_injection_includes_usage_examples(self, auto_implement_content: str):
        """
        Test that context injection includes examples of how agents use the context.

        DOCUMENTATION: Ensure agents know how to use injected context.
        Expected: Examples or instructions for using guidance fields.
        """
        # Should have some form of example or usage instruction
        # This could be in prompt text or example blocks
        assert "example" in auto_implement_content.lower() or "use" in auto_implement_content.lower(), \
            "auto-implement.md should include usage examples or instructions"


class TestMergedContextFormat:
    """Test the format of merged research context passed to downstream agents."""

    @pytest.fixture
    def auto_implement_file(self) -> Path:
        """Get path to auto-implement.md command file."""
        test_file = Path(__file__)
        repo_root = test_file.parent.parent.parent
        command_file = repo_root / "plugins" / "autonomous-dev" / "commands" / "auto-implement.md"
        return command_file

    @pytest.fixture
    def auto_implement_content(self, auto_implement_file: Path) -> str:
        """Read auto-implement.md file content."""
        return auto_implement_file.read_text()

    def test_merged_context_separates_codebase_and_web_findings(self, auto_implement_content: str):
        """
        Test that merged context clearly separates codebase findings from web research.

        CLARITY: Agents should know which guidance is local vs external.
        Expected: Clear distinction between local patterns and web best practices.
        """
        # Should distinguish between local and external sources
        # This might be in section headers or prompt structure
        content_lower = auto_implement_content.lower()

        # Check for some form of source distinction
        has_local_marker = "local" in content_lower or "codebase" in content_lower or "existing" in content_lower
        has_web_marker = "web" in content_lower or "external" in content_lower or "best practice" in content_lower

        assert has_local_marker, \
            "auto-implement.md should mark local/codebase findings"

        assert has_web_marker, \
            "auto-implement.md should mark web/external findings"

    def test_merged_context_highlights_conflicts_between_local_and_web(self, auto_implement_content: str):
        """
        Test that merged context identifies conflicts between local patterns and best practices.

        DECISION SUPPORT: Help agents identify where local code differs from standards.
        Expected: Mentions conflict detection or pattern comparison.
        """
        # Should mention checking for conflicts or differences
        content_lower = auto_implement_content.lower()

        assert "conflict" in content_lower or "differ" in content_lower or "align" in content_lower, \
            "auto-implement.md should mention checking for conflicts between local and web findings"

    def test_merged_context_prioritizes_guidance(self, auto_implement_content: str):
        """
        Test that merged context provides prioritization guidance.

        DECISION SUPPORT: Help agents decide which guidance to follow.
        Expected: Mentions priority, importance, or decision criteria.
        """
        # Should provide some prioritization or decision guidance
        content_lower = auto_implement_content.lower()

        has_priority_guidance = (
            "priority" in content_lower or
            "important" in content_lower or
            "should" in content_lower or
            "must" in content_lower
        )

        assert has_priority_guidance, \
            "auto-implement.md should provide prioritization guidance for context"
