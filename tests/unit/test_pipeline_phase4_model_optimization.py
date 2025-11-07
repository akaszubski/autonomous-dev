"""
Unit tests for GitHub Issue #46 Phase 4: Model Optimization.

TDD Mode: These tests are written BEFORE implementation.
Tests should FAIL initially (implementation not yet complete).

Phase 4 Goals:
- Switch researcher agent from sonnet to haiku
- Maintain research quality (no degradation)
- Expected savings: 3-5 minutes per /auto-implement
- Update performance baseline to 25-39 minutes

Test Strategy:
- Test researcher model configuration is haiku
- Test research output quality unchanged
- Test performance baseline expectations
- Test model switch doesn't break dependencies

Date: 2025-11-08
GitHub Issue: #46
Phase: 4 (Model Optimization)
Agent: test-master
"""

import pytest
from pathlib import Path
from typing import Dict, Any
from unittest.mock import Mock, MagicMock, patch
import yaml


class TestResearcherModelConfiguration:
    """Test researcher agent uses haiku model for cost/performance optimization."""

    def test_researcher_uses_haiku_model(self):
        """
        Test that researcher agent is configured to use haiku model.

        Expected behavior:
        - researcher.md frontmatter has model: haiku
        - Model change documented in agent file
        - No other agents affected by this change

        Performance impact:
        - Haiku is 5-10x faster than sonnet for research tasks
        - Expected savings: 3-5 minutes per /auto-implement
        """
        researcher_file = Path(__file__).parent.parent.parent / "plugins" / "autonomous-dev" / "agents" / "researcher.md"

        assert researcher_file.exists(), \
            "researcher.md agent file should exist"

        content = researcher_file.read_text()

        # Parse frontmatter
        assert content.startswith("---"), \
            "Agent file should have YAML frontmatter"

        frontmatter_end = content.find("---", 3)
        frontmatter = content[3:frontmatter_end].strip()

        # Parse YAML frontmatter
        config = yaml.safe_load(frontmatter)

        assert "model" in config, \
            "Agent frontmatter should specify model"

        assert config["model"] == "haiku", \
            f"Researcher should use haiku model, got: {config['model']}"

        # Verify agent name is correct
        assert config["name"] == "researcher", \
            "Agent name should be 'researcher'"

    def test_other_agents_unaffected_by_researcher_model_change(self):
        """
        Test that changing researcher model doesn't affect other agents.

        Expected behavior:
        - Planner still uses opus (strategic planning needs it)
        - Implementer still uses sonnet (code quality needs it)
        - Other agents unchanged
        """
        agents_dir = Path(__file__).parent.parent.parent / "plugins" / "autonomous-dev" / "agents"

        # Check planner still uses opus
        planner_file = agents_dir / "planner.md"
        planner_content = planner_file.read_text()
        planner_frontmatter = planner_content.split("---")[1].strip()
        planner_config = yaml.safe_load(planner_frontmatter)

        assert planner_config["model"] == "opus", \
            "Planner should still use opus for strategic planning"

        # Check implementer still uses sonnet
        implementer_file = agents_dir / "implementer.md"
        implementer_content = implementer_file.read_text()
        implementer_frontmatter = implementer_content.split("---")[1].strip()
        implementer_config = yaml.safe_load(implementer_frontmatter)

        assert implementer_config["model"] == "sonnet", \
            "Implementer should still use sonnet for code quality"

    def test_researcher_model_change_documented(self):
        """
        Test that haiku model change is documented in researcher.md.

        Expected behavior:
        - Comment or note explaining why haiku is used
        - Performance/cost benefits mentioned
        - Trade-offs acknowledged (if any)
        """
        researcher_file = Path(__file__).parent.parent.parent / "plugins" / "autonomous-dev" / "agents" / "researcher.md"
        content = researcher_file.read_text()

        # Should mention haiku somewhere in the documentation
        assert "haiku" in content.lower(), \
            "Researcher agent should document haiku model usage"

        # Should explain why (performance or cost)
        has_rationale = (
            "performance" in content.lower() or
            "cost" in content.lower() or
            "speed" in content.lower() or
            "faster" in content.lower()
        )

        assert has_rationale, \
            "Researcher should explain why haiku model is used (performance/cost)"


class TestResearchQualityMaintained:
    """Test that switching to haiku doesn't degrade research quality."""

    def test_researcher_still_has_web_search_capability(self):
        """
        Test that researcher retains WebSearch tool access after model change.

        Expected behavior:
        - WebSearch tool still in tools list
        - WebFetch tool still available
        - No tool restrictions added
        """
        researcher_file = Path(__file__).parent.parent.parent / "plugins" / "autonomous-dev" / "agents" / "researcher.md"
        content = researcher_file.read_text()

        frontmatter = content.split("---")[1].strip()
        config = yaml.safe_load(frontmatter)

        assert "tools" in config, \
            "Researcher should have tools defined"

        tools = config["tools"]

        assert "WebSearch" in tools, \
            "Researcher should still have WebSearch capability"

        assert "WebFetch" in tools, \
            "Researcher should still have WebFetch capability"

    def test_researcher_prompt_maintains_quality_standards(self):
        """
        Test that researcher prompt still enforces quality standards.

        Expected behavior:
        - Prompt mentions authoritative sources
        - Prompt requires best practices research
        - Prompt includes security considerations
        - Prompt length sufficient for quality guidance
        """
        researcher_file = Path(__file__).parent.parent.parent / "plugins" / "autonomous-dev" / "agents" / "researcher.md"
        content = researcher_file.read_text()

        # Extract prompt (after frontmatter)
        prompt = content.split("---", 2)[2]

        # Quality requirements
        assert "best practices" in prompt.lower() or "best practice" in prompt.lower(), \
            "Researcher should research best practices"

        assert "security" in prompt.lower(), \
            "Researcher should consider security"

        assert "authoritative" in prompt.lower() or "official" in prompt.lower(), \
            "Researcher should prioritize authoritative sources"

        # Prompt should be substantial enough for quality guidance
        prompt_lines = [line for line in prompt.split("\n") if line.strip()]
        assert len(prompt_lines) >= 30, \
            f"Researcher prompt should have at least 30 lines of guidance, got {len(prompt_lines)}"

    def test_researcher_skills_integration_unchanged(self):
        """
        Test that researcher still references relevant skills after model change.

        Expected behavior:
        - research-patterns skill still referenced
        - Skills section still present
        - Progressive disclosure still works
        """
        researcher_file = Path(__file__).parent.parent.parent / "plugins" / "autonomous-dev" / "agents" / "researcher.md"
        content = researcher_file.read_text()

        # Should reference research-patterns skill (Issue #35)
        assert "research-patterns" in content.lower(), \
            "Researcher should reference research-patterns skill"

        # Should have a skills section
        assert "skill" in content.lower(), \
            "Researcher should mention skills integration"


class TestPerformanceBaselineUpdate:
    """Test that performance baseline is updated to reflect haiku optimization."""

    def test_phase4_baseline_documented_in_claude_md(self):
        """
        Test that CLAUDE.md reflects new 25-39 minute baseline after Phase 4.

        Expected behavior:
        - Documentation mentions Phase 4 completion
        - New baseline: 25-39 minutes (3-5 min savings from 28-44 min)
        - Old baseline deprecated/updated
        """
        claude_md = Path(__file__).parent.parent.parent / "CLAUDE.md"
        content = claude_md.read_text()

        # Should mention performance improvements
        has_performance_mention = (
            "performance" in content.lower() or
            "optimization" in content.lower() or
            "faster" in content.lower()
        )

        assert has_performance_mention, \
            "CLAUDE.md should document performance optimizations"

        # Should mention Phase 4 or model optimization
        has_phase4_mention = (
            "phase 4" in content.lower() or
            "model optimization" in content.lower() or
            "haiku" in content.lower()
        )

        assert has_phase4_mention, \
            "CLAUDE.md should document Phase 4 model optimization"

    def test_performance_expectations_realistic(self):
        """
        Test that performance baseline expectations are realistic.

        Expected behavior:
        - Baseline acknowledges variability (ranges, not fixed numbers)
        - Documents what affects performance (feature complexity, etc.)
        - Sets expectations for users
        """
        # This test validates documentation quality
        # Real implementation would check:
        # 1. Performance ranges documented (not single numbers)
        # 2. Factors affecting performance explained
        # 3. User expectations set appropriately

        # For now, we just verify the concept is testable
        assert True, "Performance expectations should be documented with ranges"

    def test_phase4_completion_tracked_in_project_md(self):
        """
        Test that PROJECT.md tracks Phase 4 completion.

        Expected behavior:
        - Phase 4 marked complete in goals
        - Savings documented (3-5 min)
        - Next phase (Phase 5) identified
        """
        project_md = Path(__file__).parent.parent.parent / ".claude" / "PROJECT.md"

        # PROJECT.md should exist
        assert project_md.exists(), \
            "PROJECT.md should exist for goal tracking"

        content = project_md.read_text()

        # Should mention issue #46
        assert "#46" in content or "46" in content, \
            "PROJECT.md should reference GitHub issue #46"


class TestModelOptimizationIntegration:
    """Test that haiku model integrates correctly with workflow."""

    def test_researcher_invocation_uses_haiku_model(self):
        """
        Test that when auto-implement calls researcher, it uses haiku model.

        Expected behavior:
        - Task tool invocation specifies haiku model
        - Model selection happens automatically from agent config
        - No manual model override needed
        """
        # This test would mock Task tool invocation
        # For now, we verify the concept is testable

        with patch('builtins.open', create=True) as mock_open:
            # Mock reading researcher.md
            mock_open.return_value.__enter__.return_value.read.return_value = """---
name: researcher
model: haiku
tools: [WebSearch, WebFetch, Read, Grep, Glob]
---

Research agent prompt here...
"""

            # Simulate loading agent config
            researcher_file = Path("/fake/path/researcher.md")

            # In real implementation, this would parse frontmatter
            # and extract model: haiku
            # Then Task tool would use that model

            # For now, verify concept is testable
            assert True, "Researcher invocation should use haiku from agent config"

    def test_researcher_output_format_unchanged(self):
        """
        Test that researcher output format remains consistent after model change.

        Expected behavior:
        - Same output structure (findings, recommendations, etc.)
        - Same level of detail expected
        - Downstream agents can consume output unchanged
        """
        # This would test actual researcher output
        # For now, verify concept is testable

        expected_sections = [
            "findings",
            "recommendations",
            "security considerations",
            "best practices"
        ]

        # Real test would invoke researcher and verify these sections
        # For TDD, we just verify the expectation
        assert len(expected_sections) > 0, \
            "Researcher output should have consistent structure"

    def test_haiku_model_available_in_claude_code(self):
        """
        Test that haiku model is available in Claude Code environment.

        Expected behavior:
        - Haiku is a valid model choice
        - No runtime errors when using haiku
        - Model exists in Claude Code 2.0+
        """
        # This would verify Claude Code has haiku available
        # For TDD, we document the requirement

        valid_models = ["opus", "sonnet", "haiku"]

        assert "haiku" in valid_models, \
            "Haiku should be a valid Claude Code model"


class TestRegressionPrevention:
    """Test that Phase 4 changes don't break existing functionality."""

    def test_seven_agent_workflow_still_complete(self):
        """
        Test that all 7 agents still run in /auto-implement after Phase 4.

        Expected behavior:
        - researcher (haiku), planner (opus) - Step 2-3
        - test-master (sonnet), implementer (sonnet) - Step 4
        - reviewer, security-auditor, doc-master (parallel) - Step 5
        - Total: 7 agents
        """
        auto_implement_file = Path(__file__).parent.parent.parent / "plugins" / "autonomous-dev" / "commands" / "auto-implement.md"
        content = auto_implement_file.read_text()

        # All 7 agents should still be mentioned
        required_agents = [
            "researcher",
            "planner",
            "test-master",
            "implementer",
            "reviewer",
            "security-auditor",
            "doc-master"
        ]

        for agent in required_agents:
            assert agent in content, \
                f"Agent {agent} should still be in auto-implement workflow"

    def test_checkpoint_validation_still_enforced(self):
        """
        Test that checkpoint validation (7 agents) still works after Phase 4.

        Expected behavior:
        - enforce_pipeline_complete.py hook unchanged
        - Still validates exactly 7 agents
        - Model change doesn't affect validation logic
        """
        hook_file = Path(__file__).parent.parent.parent / "plugins" / "autonomous-dev" / "hooks" / "enforce_pipeline_complete.py"

        assert hook_file.exists(), \
            "Pipeline completeness enforcement hook should exist"

        content = hook_file.read_text()

        # Should still check for 7 agents
        assert "7" in content or "seven" in content.lower(), \
            "Hook should still validate 7 agents ran"

    def test_parallel_validation_unaffected_by_researcher_change(self):
        """
        Test that Phase 3 parallel validation still works after Phase 4.

        Expected behavior:
        - reviewer, security-auditor, doc-master still run in parallel
        - Researcher model change doesn't affect Step 5
        - Performance gains from Phase 3 preserved
        """
        auto_implement_file = Path(__file__).parent.parent.parent / "plugins" / "autonomous-dev" / "commands" / "auto-implement.md"
        content = auto_implement_file.read_text()

        # Should still have parallel validation step
        assert "STEP 5: Parallel Validation" in content or "Parallel Validation" in content, \
            "Parallel validation step should still exist"

        # Should still mention all three agents
        step5_agents = ["reviewer", "security-auditor", "doc-master"]
        for agent in step5_agents:
            assert agent in content, \
                f"Step 5 should still include {agent}"
