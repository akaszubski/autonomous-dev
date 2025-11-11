"""
TDD RED Phase Tests for Issue #72: Agent Output Quality Validation

Integration tests that invoke agents and verify their outputs still follow
expected formats after cleanup. All tests should FAIL initially.

Test Coverage:
1. Agent outputs follow agent-output-formats skill templates
2. Research agents produce properly formatted findings
3. Planning agents produce properly formatted plans
4. Implementation agents produce properly formatted reports
5. Review agents produce properly formatted assessments
6. Progressive disclosure loads skill when needed
"""

import pytest
from pathlib import Path
from typing import Dict, Any, Optional
import json
import subprocess


# ============================================================================
# Mock Agent Invocation (will be replaced with actual invocation)
# ============================================================================


def invoke_agent(agent_name: str, task: str) -> str:
    """
    Invoke an agent and capture its output.

    EXPECTED TO FAIL: Function doesn't exist yet.
    """
    raise NotImplementedError("invoke_agent not implemented yet")


def parse_agent_output(output: str, expected_format: str) -> Dict:
    """
    Parse agent output and validate against expected format.

    EXPECTED TO FAIL: Function doesn't exist yet.
    """
    raise NotImplementedError("parse_agent_output not implemented yet")


# ============================================================================
# Test 1: Agent Outputs Follow agent-output-formats Skill Templates
# ============================================================================


def test_agent_outputs_conform_to_skill_templates():
    """
    Test that agent outputs follow templates from agent-output-formats skill.

    EXPECTED TO FAIL: Need to implement agent invocation and validation.
    """
    from tests.helpers.agent_testing import invoke_test_agent, validate_output_format

    # Test a research agent
    output = invoke_test_agent("researcher", "Research Python testing best practices")

    # Validate against research template from skill
    is_valid = validate_output_format(output, "research")

    assert is_valid, "Researcher output should follow research template from agent-output-formats skill"


def test_output_validation_checks_required_sections():
    """
    Test that validation checks for required sections from skill templates.

    EXPECTED TO FAIL: Validation function doesn't exist yet.
    """
    from tests.helpers.agent_testing import validate_output_format

    # Mock output with missing sections
    incomplete_output = """
## Patterns Found

- Pattern 1: Example

## Best Practices

- Practice 1: Example

[Missing: Security Considerations and Recommendations sections]
"""

    is_valid = validate_output_format(incomplete_output, "research")

    assert not is_valid, "Output missing required sections should fail validation"


def test_output_validation_allows_agent_specific_sections():
    """
    Test that validation allows agent-specific sections beyond templates.

    EXPECTED TO FAIL: Validation may be too strict.
    """
    from tests.helpers.agent_testing import validate_output_format

    # Output with template sections plus agent-specific ones
    extended_output = """
## Patterns Found

- Pattern 1: Example

## Best Practices

- Practice 1: Example

## Security Considerations

- Security 1: Example

## Recommendations

- Rec 1: Example

## Additional Context

[Agent-specific section]

This should be allowed.
"""

    is_valid = validate_output_format(extended_output, "research", strict=False)

    assert is_valid, "Output with additional sections should be valid in non-strict mode"


# ============================================================================
# Test 2: Research Agents Produce Properly Formatted Findings
# ============================================================================


def test_researcher_agent_output_format():
    """
    Test that researcher agent produces properly formatted output.

    EXPECTED TO FAIL: Agent may not follow format after cleanup.
    """
    from tests.helpers.agent_testing import invoke_test_agent, validate_research_output

    output = invoke_test_agent("researcher", "Research Python async/await patterns")

    # Should have required research sections
    assert "## Patterns Found" in output, "Missing Patterns Found section"
    assert "## Best Practices" in output, "Missing Best Practices section"
    assert "## Security Considerations" in output, "Missing Security Considerations section"
    assert "## Recommendations" in output, "Missing Recommendations section"

    # Validate structure
    is_valid = validate_research_output(output)
    assert is_valid, "Researcher output should follow research template"


def test_issue_creator_agent_output_format():
    """
    Test that issue-creator agent produces properly formatted output.

    EXPECTED TO FAIL: Agent may not follow format after cleanup.
    """
    from tests.helpers.agent_testing import invoke_test_agent

    output = invoke_test_agent("issue-creator", "Create issue for adding dark mode")

    # Should have research-like sections plus issue-specific content
    assert "## Patterns Found" in output or "## Research Findings" in output
    assert "## Recommendations" in output or "## Proposed Solution" in output

    # Should include GitHub issue format elements
    assert any(marker in output for marker in ["## Description", "## Acceptance Criteria", "## Test Plan"])


def test_brownfield_analyzer_agent_output_format():
    """
    Test that brownfield-analyzer agent produces properly formatted output.

    EXPECTED TO FAIL: Agent may not follow format after cleanup.
    """
    from tests.helpers.agent_testing import invoke_test_agent

    output = invoke_test_agent("brownfield-analyzer", "Analyze project for retrofit")

    # Should have analysis sections
    assert "## Analysis" in output or "## Findings" in output
    assert "## Recommendations" in output or "## Next Steps" in output


# ============================================================================
# Test 3: Planning Agents Produce Properly Formatted Plans
# ============================================================================


def test_planner_agent_output_format():
    """
    Test that planner agent produces properly formatted plans.

    EXPECTED TO FAIL: Agent may not follow format after cleanup.
    """
    from tests.helpers.agent_testing import invoke_test_agent, validate_planning_output

    output = invoke_test_agent("planner", "Plan implementation of user authentication")

    # Should have required planning sections
    assert "## Feature Summary" in output, "Missing Feature Summary section"
    assert "## Architecture" in output, "Missing Architecture section"
    assert "## Components" in output, "Missing Components section"
    assert "## Implementation Plan" in output, "Missing Implementation Plan section"
    assert "## Risks and Mitigations" in output, "Missing Risks and Mitigations section"

    # Validate structure
    is_valid = validate_planning_output(output)
    assert is_valid, "Planner output should follow planning template"


def test_migration_planner_output_format():
    """
    Test that migration-planner produces properly formatted plans.

    EXPECTED TO FAIL: Agent may not follow format after cleanup.
    """
    from tests.helpers.agent_testing import invoke_test_agent

    output = invoke_test_agent("migration-planner", "Plan migration to new architecture")

    # Should have planning sections
    assert "## " in output  # Has at least one section header
    assert "plan" in output.lower() or "phase" in output.lower()


def test_setup_wizard_output_format():
    """
    Test that setup-wizard produces properly formatted setup instructions.

    EXPECTED TO FAIL: Agent may not follow format after cleanup.
    """
    from tests.helpers.agent_testing import invoke_test_agent

    output = invoke_test_agent("setup-wizard", "Detect tech stack and recommend setup")

    # Should have structured output
    assert "## " in output  # Has section headers
    assert "detected" in output.lower() or "recommended" in output.lower()


# ============================================================================
# Test 4: Implementation Agents Produce Properly Formatted Reports
# ============================================================================


def test_implementer_agent_output_format():
    """
    Test that implementer agent produces properly formatted reports.

    EXPECTED TO FAIL: Agent may not follow format after cleanup.
    """
    from tests.helpers.agent_testing import invoke_test_agent, validate_implementation_output

    output = invoke_test_agent("implementer", "Implement user login feature")

    # Should have required implementation sections
    assert "## Changes Made" in output, "Missing Changes Made section"
    assert "## Files Modified" in output or "## Files" in output, "Missing Files section"
    assert "## Tests Updated" in output or "## Tests" in output, "Missing Tests section"

    # Validate structure
    is_valid = validate_implementation_output(output)
    assert is_valid, "Implementer output should follow implementation template"


def test_implementer_reports_file_changes():
    """
    Test that implementer reports file changes in structured format.

    EXPECTED TO FAIL: Format may not be consistent.
    """
    from tests.helpers.agent_testing import invoke_test_agent

    output = invoke_test_agent("implementer", "Add logging to API endpoints")

    # Should clearly list files changed
    assert "### Created Files" in output or "**Created**:" in output or \
           "New files:" in output.lower()
    assert "### Modified Files" in output or "**Modified**:" in output or \
           "Modified files:" in output.lower()


def test_implementer_reports_test_coverage():
    """
    Test that implementer reports test coverage.

    EXPECTED TO FAIL: Test reporting may be inconsistent.
    """
    from tests.helpers.agent_testing import invoke_test_agent

    output = invoke_test_agent("implementer", "Add input validation")

    # Should mention tests
    assert "test" in output.lower()
    assert "coverage" in output.lower() or "test" in output.lower()


# ============================================================================
# Test 5: Review Agents Produce Properly Formatted Assessments
# ============================================================================


def test_reviewer_agent_output_format():
    """
    Test that reviewer agent produces properly formatted reviews.

    EXPECTED TO FAIL: Agent may not follow format after cleanup.
    """
    from tests.helpers.agent_testing import invoke_test_agent, validate_review_output

    output = invoke_test_agent("reviewer", "Review user authentication implementation")

    # Should have required review sections
    assert "## Findings" in output or "## Review Results" in output, "Missing Findings section"
    assert "## Code Quality" in output or "## Quality" in output, "Missing Code Quality section"
    assert "## Security" in output, "Missing Security section"
    assert "## Verdict" in output or "## Recommendation" in output, "Missing Verdict section"

    # Validate structure
    is_valid = validate_review_output(output)
    assert is_valid, "Reviewer output should follow review template"


def test_security_auditor_agent_output_format():
    """
    Test that security-auditor agent produces properly formatted audits.

    EXPECTED TO FAIL: Agent may not follow format after cleanup.
    """
    from tests.helpers.agent_testing import invoke_test_agent

    output = invoke_test_agent("security-auditor", "Audit API security")

    # Should have security-focused sections
    assert "## Security" in output or "## Findings" in output
    assert "vulnerability" in output.lower() or "security" in output.lower()


def test_quality_validator_agent_output_format():
    """
    Test that quality-validator agent produces properly formatted validations.

    EXPECTED TO FAIL: Agent may not follow format after cleanup.
    """
    from tests.helpers.agent_testing import invoke_test_agent

    output = invoke_test_agent("quality-validator", "Validate feature implementation")

    # Should have scoring and verdict
    assert "score" in output.lower() or "rating" in output.lower()
    assert "verdict" in output.lower() or "status" in output.lower()

    # Should indicate pass/fail/needs improvement
    assert any(marker in output.lower() for marker in [
        "pass", "approved", "needs improvement", "redesign", "fail"
    ])


def test_quality_validator_includes_specific_issues():
    """
    Test that quality-validator reports specific issues with file:line references.

    EXPECTED TO FAIL: Format may not include file:line references.
    """
    from tests.helpers.agent_testing import invoke_test_agent

    output = invoke_test_agent("quality-validator", "Validate code quality")

    # If issues found, should have file:line format
    if "issue" in output.lower() or "problem" in output.lower():
        # Look for file:line pattern
        import re
        has_file_ref = bool(re.search(r'\w+\.(py|js|ts|md):\d+', output))
        assert has_file_ref, "Quality validator should include file:line references for issues"


# ============================================================================
# Test 6: Progressive Disclosure Loads Skill When Needed
# ============================================================================


def test_agent_loads_output_formats_skill_on_demand():
    """
    Test that agent-output-formats skill is loaded when agent runs.

    EXPECTED TO FAIL: Need to implement skill loading detection.
    """
    from tests.helpers.agent_testing import invoke_test_agent, get_loaded_skills

    # Invoke agent that should use output formats
    output = invoke_test_agent("researcher", "Research testing patterns")

    # Check which skills were loaded
    loaded_skills = get_loaded_skills()

    assert "agent-output-formats" in loaded_skills, \
        "agent-output-formats skill should be loaded during agent execution"


def test_skill_loads_only_when_keywords_match():
    """
    Test that agent-output-formats loads only when relevant keywords present.

    EXPECTED TO FAIL: Need to implement keyword detection.
    """
    from tests.helpers.agent_testing import invoke_test_agent, get_loaded_skills

    # Task without output-related keywords
    output = invoke_test_agent("researcher", "Find information about Python")

    # If task doesn't mention output/format, skill may not load (that's OK)
    # But when formatting output, it should load
    loaded_skills = get_loaded_skills()

    # Agent should still produce valid output even if skill doesn't auto-load
    assert "## Patterns Found" in output or "## " in output


def test_skill_metadata_always_available():
    """
    Test that skill metadata is always available (progressive disclosure).

    EXPECTED TO FAIL: Need to implement metadata checking.
    """
    from tests.helpers.skill_testing import get_skill_metadata

    metadata = get_skill_metadata("agent-output-formats")

    assert metadata is not None, "Skill metadata should always be available"
    assert "name" in metadata
    assert "description" in metadata
    assert "keywords" in metadata


def test_skill_full_content_loads_when_needed():
    """
    Test that full skill content loads only when keywords trigger it.

    EXPECTED TO FAIL: Need to implement content loading detection.
    """
    from tests.helpers.skill_testing import is_skill_content_loaded

    # Before agent runs
    assert not is_skill_content_loaded("agent-output-formats"), \
        "Skill content should not be loaded initially"

    # Run agent that needs output formatting
    from tests.helpers.agent_testing import invoke_test_agent
    invoke_test_agent("researcher", "Research and format output")

    # After agent runs with output keywords
    # Content should be loaded (if keywords matched)
    # Note: This is optional - skill may load lazily


# ============================================================================
# Test 7: Dual-Mode Outputs (YAML vs JSON)
# ============================================================================


def test_project_progress_tracker_yaml_output():
    """
    Test that project-progress-tracker produces valid YAML in automated mode.

    EXPECTED TO FAIL: Agent may not produce valid YAML.
    """
    from tests.helpers.agent_testing import invoke_test_agent
    import yaml

    output = invoke_test_agent(
        "project-progress-tracker",
        "Update progress for feature completion",
        mode="automated"
    )

    # Should be valid YAML
    try:
        data = yaml.safe_load(output)
        assert isinstance(data, dict), "YAML output should parse to dictionary"
        assert "assessment" in data, "YAML should have assessment key"
    except yaml.YAMLError as e:
        pytest.fail(f"Output is not valid YAML: {e}")


def test_project_progress_tracker_json_output():
    """
    Test that project-progress-tracker produces valid JSON in interactive mode.

    EXPECTED TO FAIL: Agent may not produce valid JSON.
    """
    from tests.helpers.agent_testing import invoke_test_agent

    output = invoke_test_agent(
        "project-progress-tracker",
        "Provide detailed progress report",
        mode="interactive"
    )

    # Should be valid JSON
    try:
        data = json.loads(output)
        assert isinstance(data, dict), "JSON output should be a dictionary"
        assert "feature_completed" in data, "JSON should have feature_completed key"
    except json.JSONDecodeError as e:
        pytest.fail(f"Output is not valid JSON: {e}")


def test_dual_mode_guidance_preserved_in_agent():
    """
    Test that project-progress-tracker preserves dual-mode guidance after cleanup.

    EXPECTED TO FAIL: Cleanup may remove mode-specific guidance.
    """
    agent_file = Path(
        "/Users/akaszubski/Documents/GitHub/autonomous-dev/plugins/autonomous-dev/agents/"
        "project-progress-tracker.md"
    )
    content = agent_file.read_text()

    # Should mention both YAML and JSON modes
    assert "YAML" in content and "JSON" in content, \
        "project-progress-tracker should document both output modes"

    # Should explain when to use each
    assert "automated" in content.lower() or "hook" in content.lower(), \
        "Should explain automated/hook mode"
    assert "interactive" in content.lower() or "user" in content.lower(), \
        "Should explain interactive mode"


# ============================================================================
# Test 8: Commit and PR Format Agents
# ============================================================================


def test_commit_message_generator_follows_conventional_commits():
    """
    Test that commit-message-generator follows conventional commits format.

    EXPECTED TO FAIL: Agent may not follow format consistently.
    """
    from tests.helpers.agent_testing import invoke_test_agent

    output = invoke_test_agent(
        "commit-message-generator",
        "Generate commit message for adding authentication"
    )

    # Should follow conventional commits format
    assert any(output.startswith(prefix) for prefix in [
        "feat:", "fix:", "docs:", "style:", "refactor:", "test:", "chore:"
    ]), "Commit message should start with conventional type"

    # Should have subject line
    lines = output.strip().split('\n')
    assert len(lines[0]) <= 72, "Subject line should be ≤72 characters"


def test_pr_description_generator_format():
    """
    Test that pr-description-generator produces properly formatted PRs.

    EXPECTED TO FAIL: Agent may not follow format consistently.
    """
    from tests.helpers.agent_testing import invoke_test_agent

    output = invoke_test_agent(
        "pr-description-generator",
        "Generate PR description for authentication feature"
    )

    # Should have required PR sections
    assert "## Summary" in output, "Missing Summary section"
    assert "## Test Plan" in output, "Missing Test Plan section"

    # Should include checkboxes for test plan
    assert "- [" in output, "Test plan should have checkboxes"


# ============================================================================
# Test 9: Error Handling in Agent Outputs
# ============================================================================


def test_agents_handle_invalid_input_gracefully():
    """
    Test that agents handle invalid input and produce structured errors.

    EXPECTED TO FAIL: Error handling may not follow format.
    """
    from tests.helpers.agent_testing import invoke_test_agent

    # Give agent invalid/nonsensical input
    output = invoke_test_agent("researcher", "")

    # Should produce structured output even for errors
    assert "## " in output, "Error output should still have sections"
    assert "error" in output.lower() or "invalid" in output.lower() or \
           "missing" in output.lower(), "Should indicate the error"


def test_agents_report_missing_information():
    """
    Test that agents clearly report when information is missing.

    EXPECTED TO FAIL: Missing info handling may be inconsistent.
    """
    from tests.helpers.agent_testing import invoke_test_agent

    # Task that can't be completed fully
    output = invoke_test_agent("planner", "Plan feature XYZ")  # Vague task

    # Should either ask for clarification or note limitations
    if "XYZ" in output:  # If agent mentions the vague name
        assert any(marker in output.lower() for marker in [
            "clarification", "more information", "unclear", "specify", "details needed"
        ]), "Should indicate when information is insufficient"


# ============================================================================
# Test 10: Integration with Test Harness
# ============================================================================


def test_agent_testing_harness_exists():
    """
    Test that agent testing helper module exists.

    EXPECTED TO FAIL: Helper module doesn't exist yet.
    """
    from tests.helpers import agent_testing

    assert hasattr(agent_testing, 'invoke_test_agent'), \
        "Helper module should have invoke_test_agent function"
    assert hasattr(agent_testing, 'validate_output_format'), \
        "Helper module should have validate_output_format function"


def test_harness_supports_all_agent_types():
    """
    Test that testing harness supports all agent types.

    EXPECTED TO FAIL: Harness doesn't exist yet.
    """
    from tests.helpers.agent_testing import get_supported_agent_types

    supported_types = get_supported_agent_types()

    expected_types = ["research", "planning", "implementation", "review"]
    for agent_type in expected_types:
        assert agent_type in supported_types, \
            f"Harness should support {agent_type} agent type"


def test_harness_can_mock_agent_execution():
    """
    Test that harness can mock agent execution for fast testing.

    EXPECTED TO FAIL: Mock functionality doesn't exist yet.
    """
    from tests.helpers.agent_testing import invoke_test_agent

    # Mock mode should return quickly without actually running agent
    output = invoke_test_agent("researcher", "Test task", mock=True)

    assert output is not None, "Mock mode should return sample output"
    assert isinstance(output, str), "Mock output should be string"
    assert len(output) > 0, "Mock output should not be empty"
