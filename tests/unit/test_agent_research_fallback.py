#!/usr/bin/env python3
"""
TDD Tests for Agent Research Fallback Mechanisms (FAILING - Red Phase)

This module contains FAILING tests that verify test-master and implementer agents
have fallback mechanisms to use Grep/Glob if research context is missing or incomplete.

Feature Requirements (from implementation plan):
1. test-master.md mentions research context usage and fallback to Grep/Glob
2. implementer.md mentions research context usage and fallback to Grep/Glob
3. Both agents can operate independently if research step fails
4. Agents prefer research context when available but don't require it

Test Coverage Target: 100% of fallback documentation

Following TDD principles:
- Write tests FIRST (red phase)
- Tests describe fallback requirements
- Tests should FAIL until agent prompts are updated
- Each test validates ONE fallback requirement

Author: test-master agent
Date: 2025-12-13
Phase: TDD Red Phase
"""

import pytest
from pathlib import Path
from typing import Dict, Any
import re


class TestTestMasterResearchFallback:
    """Test that test-master agent has fallback mechanisms for missing research context."""

    @pytest.fixture
    def test_master_file(self) -> Path:
        """Get path to test-master.md agent file."""
        test_file = Path(__file__)
        repo_root = test_file.parent.parent.parent
        agent_file = repo_root / "plugins" / "autonomous-dev" / "agents" / "test-master.md"

        assert agent_file.exists(), \
            f"test-master.md agent file should exist at {agent_file}"

        return agent_file

    @pytest.fixture
    def test_master_content(self, test_master_file: Path) -> str:
        """Read test-master.md file content."""
        return test_master_file.read_text()

    def test_test_master_mentions_research_context(self, test_master_content: str):
        """
        Test that test-master.md mentions using research context.

        NEW FEATURE: Research context awareness.
        Expected: References to testing_guidance or research findings.
        """
        content_lower = test_master_content.lower()

        # Should mention research or guidance
        has_research_ref = (
            "research" in content_lower or
            "guidance" in content_lower or
            "testing_guidance" in content_lower or
            "test_file_patterns" in content_lower
        )

        assert has_research_ref, \
            "test-master.md should reference research context or testing_guidance"

    def test_test_master_mentions_grep_glob_fallback(self, test_master_content: str):
        """
        Test that test-master.md mentions using Grep/Glob as fallback.

        FALLBACK MECHANISM: Agent can still work without research.
        Expected: Instructions to use Grep/Glob if research unavailable.
        """
        # Should mention Grep and Glob tools
        assert "Grep" in test_master_content, \
            "test-master.md should mention Grep tool as fallback"

        assert "Glob" in test_master_content, \
            "test-master.md should mention Glob tool as fallback"

    def test_test_master_has_conditional_research_usage(self, test_master_content: str):
        """
        Test that test-master.md treats research context as optional.

        GRACEFUL DEGRADATION: Agent works with or without research.
        Expected: Language indicating research is preferred but not required.
        """
        content_lower = test_master_content.lower()

        # Should have conditional language (if available, when provided, etc.)
        has_conditional = (
            "if available" in content_lower or
            "when provided" in content_lower or
            "if present" in content_lower or
            "if research" in content_lower or
            "optional" in content_lower
        )

        assert has_conditional, \
            "test-master.md should treat research context as optional (not required)"

    def test_test_master_can_discover_test_patterns_independently(self, test_master_content: str):
        """
        Test that test-master.md can discover test patterns using Grep/Glob.

        INDEPENDENCE: Agent can function without upstream dependencies.
        Expected: Instructions for finding test patterns directly.
        """
        content_lower = test_master_content.lower()

        # Should mention searching for or finding test patterns
        has_discovery = (
            "search" in content_lower or
            "find" in content_lower or
            "discover" in content_lower or
            "look for" in content_lower
        )

        assert has_discovery, \
            "test-master.md should have instructions for discovering patterns independently"

    def test_test_master_has_tools_for_independent_research(self, test_master_content: str):
        """
        Test that test-master.md has Read, Grep, Glob tools.

        TOOL ACCESS: Agent has tools needed for independent research.
        Expected: test-master has file system tools in frontmatter.
        """
        # Check frontmatter for tools
        frontmatter_match = re.search(r'---\n(.*?)\n---', test_master_content, re.DOTALL)

        assert frontmatter_match, \
            "test-master.md should have YAML frontmatter with tools list"

        frontmatter = frontmatter_match.group(1)

        # Should have Read, Grep, Glob tools
        assert "Read" in frontmatter, \
            "test-master.md should have Read tool for independent research"

        assert "Grep" in frontmatter, \
            "test-master.md should have Grep tool for independent research"

        assert "Glob" in frontmatter, \
            "test-master.md should have Glob tool for independent research"


class TestImplementerResearchFallback:
    """Test that implementer agent has fallback mechanisms for missing research context."""

    @pytest.fixture
    def implementer_file(self) -> Path:
        """Get path to implementer.md agent file."""
        test_file = Path(__file__)
        repo_root = test_file.parent.parent.parent
        agent_file = repo_root / "plugins" / "autonomous-dev" / "agents" / "implementer.md"

        assert agent_file.exists(), \
            f"implementer.md agent file should exist at {agent_file}"

        return agent_file

    @pytest.fixture
    def implementer_content(self, implementer_file: Path) -> str:
        """Read implementer.md file content."""
        return implementer_file.read_text()

    def test_implementer_mentions_research_context(self, implementer_content: str):
        """
        Test that implementer.md mentions using research context.

        NEW FEATURE: Research context awareness.
        Expected: References to implementation_guidance or research findings.
        """
        content_lower = implementer_content.lower()

        # Should mention research or guidance
        has_research_ref = (
            "research" in content_lower or
            "guidance" in content_lower or
            "implementation_guidance" in content_lower or
            "reusable_functions" in content_lower
        )

        assert has_research_ref, \
            "implementer.md should reference research context or implementation_guidance"

    def test_implementer_mentions_grep_glob_fallback(self, implementer_content: str):
        """
        Test that implementer.md mentions using Grep/Glob as fallback.

        FALLBACK MECHANISM: Agent can still work without research.
        Expected: Instructions to use Grep/Glob if research unavailable.
        """
        # Should mention Grep and Glob tools
        assert "Grep" in implementer_content, \
            "implementer.md should mention Grep tool as fallback"

        assert "Glob" in implementer_content, \
            "implementer.md should mention Glob tool as fallback"

    def test_implementer_has_conditional_research_usage(self, implementer_content: str):
        """
        Test that implementer.md treats research context as optional.

        GRACEFUL DEGRADATION: Agent works with or without research.
        Expected: Language indicating research is preferred but not required.
        """
        content_lower = implementer_content.lower()

        # Should have conditional language (if available, when provided, etc.)
        has_conditional = (
            "if available" in content_lower or
            "when provided" in content_lower or
            "if present" in content_lower or
            "if research" in content_lower or
            "optional" in content_lower
        )

        assert has_conditional, \
            "implementer.md should treat research context as optional (not required)"

    def test_implementer_can_discover_patterns_independently(self, implementer_content: str):
        """
        Test that implementer.md can discover implementation patterns using Grep/Glob.

        INDEPENDENCE: Agent can function without upstream dependencies.
        Expected: Instructions for finding implementation patterns directly.
        """
        content_lower = implementer_content.lower()

        # Should mention searching for or finding patterns
        has_discovery = (
            "search" in content_lower or
            "find" in content_lower or
            "discover" in content_lower or
            "look for" in content_lower
        )

        assert has_discovery, \
            "implementer.md should have instructions for discovering patterns independently"

    def test_implementer_has_tools_for_independent_research(self, implementer_content: str):
        """
        Test that implementer.md has Read, Grep, Glob tools.

        TOOL ACCESS: Agent has tools needed for independent research.
        Expected: implementer has file system tools in frontmatter.
        """
        # Check frontmatter for tools
        frontmatter_match = re.search(r'---\n(.*?)\n---', implementer_content, re.DOTALL)

        assert frontmatter_match, \
            "implementer.md should have YAML frontmatter with tools list"

        frontmatter = frontmatter_match.group(1)

        # Should have Read, Grep, Glob tools
        assert "Read" in frontmatter, \
            "implementer.md should have Read tool for independent research"

        assert "Grep" in frontmatter, \
            "implementer.md should have Grep tool for independent research"

        assert "Glob" in frontmatter, \
            "implementer.md should have Glob tool for independent research"


class TestFallbackWorkflow:
    """Test the fallback workflow when research context is missing or incomplete."""

    def test_agents_can_complete_workflow_without_research_step(self):
        """
        Test that agents can complete workflow even if research step is skipped.

        RESILIENCE: Workflow doesn't break if research fails.
        Expected: test-master and implementer work independently.
        """
        # This is a documentation test - we're verifying the agents have
        # the tools and instructions to work independently

        test_file = Path(__file__)
        repo_root = test_file.parent.parent.parent

        # Check test-master has necessary tools
        test_master_file = repo_root / "plugins" / "autonomous-dev" / "agents" / "test-master.md"
        test_master_content = test_master_file.read_text()

        # Check implementer has necessary tools
        implementer_file = repo_root / "plugins" / "autonomous-dev" / "agents" / "implementer.md"
        implementer_content = implementer_file.read_text()

        # Both should have file system tools
        for agent_name, content in [("test-master", test_master_content), ("implementer", implementer_content)]:
            frontmatter_match = re.search(r'---\n(.*?)\n---', content, re.DOTALL)
            assert frontmatter_match, f"{agent_name}.md should have frontmatter"

            frontmatter = frontmatter_match.group(1)
            assert "Read" in frontmatter, f"{agent_name}.md should have Read tool"
            assert "Grep" in frontmatter, f"{agent_name}.md should have Grep tool"
            assert "Glob" in frontmatter, f"{agent_name}.md should have Glob tool"

    def test_fallback_maintains_quality_standards(self):
        """
        Test that fallback workflow maintains same quality standards.

        QUALITY: Independent research should be equally thorough.
        Expected: Agents have instructions for comprehensive pattern discovery.
        """
        test_file = Path(__file__)
        repo_root = test_file.parent.parent.parent

        # Check both agents mention quality or thoroughness
        test_master_file = repo_root / "plugins" / "autonomous-dev" / "agents" / "test-master.md"
        test_master_content = test_master_file.read_text().lower()

        implementer_file = repo_root / "plugins" / "autonomous-dev" / "agents" / "implementer.md"
        implementer_content = implementer_file.read_text().lower()

        for agent_name, content in [("test-master", test_master_content), ("implementer", implementer_content)]:
            has_quality_guidance = (
                "quality" in content or
                "thorough" in content or
                "comprehensive" in content or
                "coverage" in content
            )

            assert has_quality_guidance, \
                f"{agent_name}.md should have quality/thoroughness guidance"


class TestResearchContextPriority:
    """Test that agents prefer research context when available but don't require it."""

    @pytest.fixture
    def agent_files(self) -> Dict[str, Path]:
        """Get paths to agent files."""
        test_file = Path(__file__)
        repo_root = test_file.parent.parent.parent

        return {
            "test-master": repo_root / "plugins" / "autonomous-dev" / "agents" / "test-master.md",
            "implementer": repo_root / "plugins" / "autonomous-dev" / "agents" / "implementer.md"
        }

    def test_agents_prefer_research_context_over_independent_search(self, agent_files: Dict[str, Path]):
        """
        Test that agents prefer using research context when available.

        EFFICIENCY: Research context is more comprehensive than independent search.
        Expected: Agents should use research first, fallback to Grep/Glob if missing.
        """
        for agent_name, agent_file in agent_files.items():
            content = agent_file.read_text().lower()

            # Should mention preferring or using research when available
            has_preference = (
                "prefer" in content or
                "first" in content or
                "use research" in content or
                "when available" in content or
                "if provided" in content
            )

            assert has_preference, \
                f"{agent_name}.md should indicate preference for research context"

    def test_agents_explain_when_to_use_fallback(self, agent_files: Dict[str, Path]):
        """
        Test that agents explain when to use fallback mechanisms.

        CLARITY: Agents should know when research context is insufficient.
        Expected: Instructions on when to fall back to independent search.
        """
        for agent_name, agent_file in agent_files.items():
            content = agent_file.read_text().lower()

            # Should explain fallback conditions
            has_fallback_explanation = (
                "if not available" in content or
                "if missing" in content or
                "if research" in content or
                "fallback" in content or
                "alternatively" in content
            )

            assert has_fallback_explanation, \
                f"{agent_name}.md should explain when to use fallback mechanisms"

    def test_agents_maintain_independence_from_upstream_steps(self, agent_files: Dict[str, Path]):
        """
        Test that agents can function independently from upstream workflow steps.

        RESILIENCE: Partial workflow failures don't cascade.
        Expected: Agents have self-contained instructions and tools.
        """
        for agent_name, agent_file in agent_files.items():
            content = agent_file.read_text()

            # Check for frontmatter with tools
            frontmatter_match = re.search(r'---\n(.*?)\n---', content, re.DOTALL)
            assert frontmatter_match, f"{agent_name}.md should have frontmatter"

            frontmatter = frontmatter_match.group(1)

            # Should have essential tools for independence
            assert "Read" in frontmatter, \
                f"{agent_name}.md should have Read tool for independence"

            assert "Grep" in frontmatter, \
                f"{agent_name}.md should have Grep tool for independence"

            assert "Glob" in frontmatter, \
                f"{agent_name}.md should have Glob tool for independence"

            # Content should have process/workflow instructions
            content_lower = content.lower()
            has_process = (
                "process" in content_lower or
                "workflow" in content_lower or
                "steps" in content_lower or
                "responsibilities" in content_lower
            )

            assert has_process, \
                f"{agent_name}.md should have self-contained process instructions"
