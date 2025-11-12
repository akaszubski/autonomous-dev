"""
TDD RED Phase Tests for Issue #72 Phase 2: Agent Functionality Tests

Tests that all 15 Phase 2 agents still produce correct output after cleanup.
All tests should FAIL initially (no implementation exists yet).

Phase 2 Agents (15 total):
- High-priority (8): planner, security-auditor, brownfield-analyzer, sync-validator,
  alignment-analyzer, issue-creator, pr-description-generator, project-bootstrapper
- Medium-priority (4): reviewer, commit-message-generator, project-status-analyzer
- Low-priority (3): researcher, implementer, doc-master, setup-wizard

Test Coverage:
1. Test all 15 Phase 2 agents produce correct output after cleanup
2. Test agent-specific requirements are preserved (e.g., security-auditor's "NOT a Vulnerability")
3. Test progressive disclosure: agent-output-formats skill loads when needed
4. Test output format validation works with skill reference
"""

import pytest
import json
from pathlib import Path
from typing import Dict, List, Optional
import subprocess
import tempfile


# Constants
AGENTS_DIR = Path("/Users/akaszubski/Documents/GitHub/autonomous-dev/plugins/autonomous-dev/agents")
SKILLS_DIR = Path("/Users/akaszubski/Documents/GitHub/autonomous-dev/plugins/autonomous-dev/skills")

# Phase 2 agents (15 remaining)
PHASE_2_HIGH_PRIORITY = [
    "planner",
    "security-auditor",
    "brownfield-analyzer",
    "sync-validator",
    "alignment-analyzer",
    "issue-creator",
    "pr-description-generator",
    "project-bootstrapper"
]

PHASE_2_MEDIUM_PRIORITY = [
    "reviewer",
    "commit-message-generator",
    "project-status-analyzer"
]

PHASE_2_LOW_PRIORITY = [
    "researcher",
    "implementer",
    "doc-master",
    "setup-wizard"
]

PHASE_2_AGENTS = PHASE_2_HIGH_PRIORITY + PHASE_2_MEDIUM_PRIORITY + PHASE_2_LOW_PRIORITY


# ============================================================================
# Test 1: Agent Output Correctness - High Priority
# ============================================================================


def test_planner_produces_valid_output_after_cleanup():
    """
    Test that planner agent produces valid planning output after cleanup.

    EXPECTED TO FAIL: Cleanup not yet implemented, output format may change.
    """
    from scripts.test_agent_output import run_agent_with_test_input

    test_input = {
        "feature": "Add user authentication",
        "requirements": ["OAuth2", "JWT tokens", "session management"]
    }

    output = run_agent_with_test_input("planner", test_input)

    assert output is not None, "planner should produce output"
    assert "architecture" in output or "design" in output, \
        "planner output missing architecture/design section"
    assert "implementation" in output or "steps" in output, \
        "planner output missing implementation steps"


def test_security_auditor_produces_valid_output_after_cleanup():
    """
    Test that security-auditor produces valid security scan output after cleanup.

    EXPECTED TO FAIL: Cleanup not yet implemented.
    """
    from scripts.test_agent_output import run_agent_with_test_input

    test_input = {
        "code_files": ["test_file.py"],
        "scan_type": "vulnerability_scan"
    }

    output = run_agent_with_test_input("security-auditor", test_input)

    assert output is not None, "security-auditor should produce output"
    assert "vulnerabilities" in output or "findings" in output, \
        "security-auditor output missing vulnerabilities section"


def test_brownfield_analyzer_produces_valid_output_after_cleanup():
    """
    Test that brownfield-analyzer produces valid analysis output after cleanup.

    EXPECTED TO FAIL: Cleanup not yet implemented.
    """
    from scripts.test_agent_output import run_agent_with_test_input

    test_input = {
        "project_path": "/tmp/test_project",
        "analysis_type": "tech_stack_detection"
    }

    output = run_agent_with_test_input("brownfield-analyzer", test_input)

    assert output is not None, "brownfield-analyzer should produce output"
    assert "tech_stack" in output or "analysis" in output, \
        "brownfield-analyzer output missing tech stack analysis"


def test_sync_validator_produces_valid_output_after_cleanup():
    """
    Test that sync-validator produces valid validation output after cleanup.

    EXPECTED TO FAIL: Cleanup not yet implemented.
    """
    from scripts.test_agent_output import run_agent_with_test_input

    test_input = {
        "files_to_sync": ["file1.py", "file2.py"],
        "validation_type": "conflict_detection"
    }

    output = run_agent_with_test_input("sync-validator", test_input)

    assert output is not None, "sync-validator should produce output"
    assert "conflicts" in output or "validation" in output, \
        "sync-validator output missing conflict/validation section"


def test_alignment_analyzer_produces_valid_output_after_cleanup():
    """
    Test that alignment-analyzer produces valid alignment analysis after cleanup.

    EXPECTED TO FAIL: Cleanup not yet implemented.
    """
    from scripts.test_agent_output import run_agent_with_test_input

    test_input = {
        "project_md_path": ".claude/PROJECT.md",
        "analysis_type": "goal_alignment"
    }

    output = run_agent_with_test_input("alignment-analyzer", test_input)

    assert output is not None, "alignment-analyzer should produce output"
    assert "alignment" in output or "goals" in output, \
        "alignment-analyzer output missing alignment analysis"


def test_issue_creator_produces_valid_output_after_cleanup():
    """
    Test that issue-creator produces valid GitHub issue after cleanup.

    EXPECTED TO FAIL: Cleanup not yet implemented.
    """
    from scripts.test_agent_output import run_agent_with_test_input

    test_input = {
        "feature_request": "Add dark mode support",
        "research_required": True
    }

    output = run_agent_with_test_input("issue-creator", test_input)

    assert output is not None, "issue-creator should produce output"
    assert "title" in output and "body" in output, \
        "issue-creator output missing title/body"


def test_pr_description_generator_produces_valid_output_after_cleanup():
    """
    Test that pr-description-generator produces valid PR description after cleanup.

    EXPECTED TO FAIL: Cleanup not yet implemented.
    """
    from scripts.test_agent_output import run_agent_with_test_input

    test_input = {
        "branch_name": "feature/new-feature",
        "commits": ["commit1", "commit2"]
    }

    output = run_agent_with_test_input("pr-description-generator", test_input)

    assert output is not None, "pr-description-generator should produce output"
    assert "summary" in output or "description" in output, \
        "pr-description-generator output missing summary/description"


def test_project_bootstrapper_produces_valid_output_after_cleanup():
    """
    Test that project-bootstrapper produces valid setup output after cleanup.

    EXPECTED TO FAIL: Cleanup not yet implemented.
    """
    from scripts.test_agent_output import run_agent_with_test_input

    test_input = {
        "project_type": "python",
        "setup_type": "new_project"
    }

    output = run_agent_with_test_input("project-bootstrapper", test_input)

    assert output is not None, "project-bootstrapper should produce output"
    assert "setup" in output or "bootstrap" in output, \
        "project-bootstrapper output missing setup instructions"


# ============================================================================
# Test 2: Agent Output Correctness - Medium Priority
# ============================================================================


def test_reviewer_produces_valid_output_after_cleanup():
    """
    Test that reviewer produces valid code review after cleanup.

    EXPECTED TO FAIL: Cleanup not yet implemented.
    """
    from scripts.test_agent_output import run_agent_with_test_input

    test_input = {
        "code_files": ["test_file.py"],
        "review_type": "code_quality"
    }

    output = run_agent_with_test_input("reviewer", test_input)

    assert output is not None, "reviewer should produce output"
    assert "approve" in output.lower() or "reject" in output.lower() or "changes" in output.lower(), \
        "reviewer output missing review decision"


def test_commit_message_generator_produces_valid_output_after_cleanup():
    """
    Test that commit-message-generator produces valid commit message after cleanup.

    EXPECTED TO FAIL: Cleanup not yet implemented.
    """
    from scripts.test_agent_output import run_agent_with_test_input

    test_input = {
        "changes": ["file1.py modified", "file2.py added"],
        "message_type": "conventional"
    }

    output = run_agent_with_test_input("commit-message-generator", test_input)

    assert output is not None, "commit-message-generator should produce output"
    assert "feat:" in output or "fix:" in output or "docs:" in output, \
        "commit-message-generator output missing conventional commit prefix"


def test_project_status_analyzer_produces_valid_output_after_cleanup():
    """
    Test that project-status-analyzer produces valid status report after cleanup.

    EXPECTED TO FAIL: Cleanup not yet implemented.
    """
    from scripts.test_agent_output import run_agent_with_test_input

    test_input = {
        "project_path": "/tmp/test_project",
        "analysis_type": "health_check"
    }

    output = run_agent_with_test_input("project-status-analyzer", test_input)

    assert output is not None, "project-status-analyzer should produce output"
    assert "status" in output or "health" in output or "metrics" in output, \
        "project-status-analyzer output missing status/health metrics"


# ============================================================================
# Test 3: Agent Output Correctness - Low Priority
# ============================================================================


def test_researcher_produces_valid_output_after_cleanup():
    """
    Test that researcher produces valid research output after cleanup.

    EXPECTED TO FAIL: Cleanup not yet implemented.
    """
    from scripts.test_agent_output import run_agent_with_test_input

    test_input = {
        "research_topic": "Python async patterns",
        "depth": "comprehensive"
    }

    output = run_agent_with_test_input("researcher", test_input)

    assert output is not None, "researcher should produce output"
    assert "findings" in output or "research" in output or "patterns" in output, \
        "researcher output missing research findings"


def test_implementer_produces_valid_output_after_cleanup():
    """
    Test that implementer produces valid implementation after cleanup.

    EXPECTED TO FAIL: Cleanup not yet implemented.
    """
    from scripts.test_agent_output import run_agent_with_test_input

    test_input = {
        "feature": "Add logging",
        "test_file": "test_logging.py"
    }

    output = run_agent_with_test_input("implementer", test_input)

    assert output is not None, "implementer should produce output"
    assert "implementation" in output or "code" in output, \
        "implementer output missing implementation details"


def test_doc_master_produces_valid_output_after_cleanup():
    """
    Test that doc-master produces valid documentation after cleanup.

    EXPECTED TO FAIL: Cleanup not yet implemented.
    """
    from scripts.test_agent_output import run_agent_with_test_input

    test_input = {
        "documentation_type": "api_docs",
        "files": ["api.py"]
    }

    output = run_agent_with_test_input("doc-master", test_input)

    assert output is not None, "doc-master should produce output"
    assert "documentation" in output or "docs" in output, \
        "doc-master output missing documentation content"


def test_setup_wizard_produces_valid_output_after_cleanup():
    """
    Test that setup-wizard produces valid setup guide after cleanup.

    EXPECTED TO FAIL: Cleanup not yet implemented.
    """
    from scripts.test_agent_output import run_agent_with_test_input

    test_input = {
        "project_type": "python",
        "wizard_type": "interactive_setup"
    }

    output = run_agent_with_test_input("setup-wizard", test_input)

    assert output is not None, "setup-wizard should produce output"
    assert "setup" in output or "wizard" in output or "configuration" in output, \
        "setup-wizard output missing setup guidance"


# ============================================================================
# Test 4: Agent-Specific Requirements Preserved
# ============================================================================


def test_security_auditor_preserves_not_vulnerability_guidance():
    """
    Test that security-auditor preserves "What is NOT a Vulnerability" guidance.

    EXPECTED TO FAIL: Cleanup not yet implemented, need to verify preserved content.
    """
    security_file = AGENTS_DIR / "security-auditor.md"
    content = security_file.read_text()

    assert "NOT a Vulnerability" in content or "not a vulnerability" in content, \
        "security-auditor missing 'What is NOT a Vulnerability' section"

    # Should reference agent-output-formats skill
    assert "agent-output-formats" in content, \
        "security-auditor should reference agent-output-formats skill"


def test_planner_preserves_architecture_specific_guidance():
    """
    Test that planner preserves architecture-specific guidance.

    EXPECTED TO FAIL: Cleanup not yet implemented.
    """
    planner_file = AGENTS_DIR / "planner.md"
    content = planner_file.read_text()

    # Should have architecture-related guidance
    architecture_keywords = ["architecture", "design patterns", "implementation phases"]
    has_guidance = any(keyword in content.lower() for keyword in architecture_keywords)

    assert has_guidance, "planner missing architecture-specific guidance"

    # Should reference agent-output-formats skill
    assert "agent-output-formats" in content, \
        "planner should reference agent-output-formats skill"


def test_reviewer_preserves_review_criteria():
    """
    Test that reviewer preserves review criteria guidance.

    EXPECTED TO FAIL: Cleanup not yet implemented.
    """
    reviewer_file = AGENTS_DIR / "reviewer.md"
    content = reviewer_file.read_text()

    # Should have review criteria
    review_keywords = ["approve", "request changes", "reject", "quality criteria"]
    has_criteria = any(keyword in content.lower() for keyword in review_keywords)

    assert has_criteria, "reviewer missing review criteria guidance"

    # Should reference agent-output-formats skill
    assert "agent-output-formats" in content, \
        "reviewer should reference agent-output-formats skill"


def test_all_phase2_agents_reference_skill():
    """
    Test that all Phase 2 agents reference agent-output-formats skill.

    EXPECTED TO FAIL: Cleanup not yet implemented, skill references need to be added.
    """
    for agent_name in PHASE_2_AGENTS:
        agent_file = AGENTS_DIR / f"{agent_name}.md"
        content = agent_file.read_text()

        assert "agent-output-formats" in content, \
            f"{agent_name} missing agent-output-formats skill reference"


# ============================================================================
# Test 5: Progressive Disclosure - Skill Loading
# ============================================================================


def test_agent_output_formats_skill_exists():
    """
    Test that agent-output-formats skill exists for progressive disclosure.

    EXPECTED TO FAIL: Need to verify skill file exists.
    """
    skill_file = SKILLS_DIR / "agent-output-formats" / "SKILL.md"

    assert skill_file.exists(), \
        f"agent-output-formats skill not found at {skill_file}"

    content = skill_file.read_text()
    assert len(content) > 100, "Skill file should have substantial content"


def test_skill_provides_standard_output_formats():
    """
    Test that agent-output-formats skill provides standard output formats.

    EXPECTED TO FAIL: Need to verify skill content.
    """
    skill_file = SKILLS_DIR / "agent-output-formats" / "SKILL.md"
    content = skill_file.read_text()

    # Should provide various output format templates
    expected_formats = ["research", "planning", "implementation", "review", "security"]
    for format_type in expected_formats:
        assert format_type in content.lower(), \
            f"Skill missing {format_type} output format template"


def test_skill_loads_only_when_referenced():
    """
    Test that skill loads only when agent references it (progressive disclosure).

    EXPECTED TO FAIL: Progressive disclosure mechanism needs testing.
    """
    from scripts.test_progressive_disclosure import test_skill_loading

    # Simulate agent execution without skill reference
    loaded_without_ref = test_skill_loading(agent="test-master", has_skill_ref=False)
    assert not loaded_without_ref, "Skill should not load without reference"

    # Simulate agent execution with skill reference
    loaded_with_ref = test_skill_loading(agent="planner", has_skill_ref=True)
    assert loaded_with_ref, "Skill should load when referenced"


def test_skill_content_accessible_to_agents():
    """
    Test that skill content is accessible to agents during execution.

    EXPECTED TO FAIL: Need to verify skill accessibility.
    """
    from scripts.test_progressive_disclosure import test_skill_accessibility

    # Planner should be able to access agent-output-formats skill
    accessible = test_skill_accessibility(agent="planner", skill="agent-output-formats")

    assert accessible, "planner should access agent-output-formats skill"


# ============================================================================
# Test 6: Output Format Validation with Skill Reference
# ============================================================================


def test_validate_output_with_skill_reference():
    """
    Test that output validation works when agent references skill.

    EXPECTED TO FAIL: Validation mechanism needs implementation.
    """
    from scripts.test_agent_output import validate_agent_output

    # Planner output should be valid according to skill format
    test_output = {
        "architecture": "Microservices",
        "implementation_phases": ["Phase 1", "Phase 2"]
    }

    is_valid = validate_agent_output(
        agent="planner",
        output=test_output,
        use_skill_validation=True
    )

    assert is_valid, "planner output should be valid according to skill format"


def test_output_validation_uses_skill_templates():
    """
    Test that output validation uses skill templates.

    EXPECTED TO FAIL: Template-based validation needs implementation.
    """
    from scripts.test_agent_output import validate_against_skill_template

    # Security-auditor output should match skill template
    test_output = {
        "vulnerabilities": [],
        "findings": ["CWE-22 detected"],
        "recommendations": ["Fix path traversal"]
    }

    template_match = validate_against_skill_template(
        agent="security-auditor",
        output=test_output,
        skill="agent-output-formats"
    )

    assert template_match, "security-auditor output should match skill template"


def test_output_validation_handles_agent_specific_fields():
    """
    Test that validation handles agent-specific fields not in skill.

    EXPECTED TO FAIL: Agent-specific field handling needs implementation.
    """
    from scripts.test_agent_output import validate_agent_specific_fields

    # Security-auditor has "What is NOT a Vulnerability" - not in generic skill
    test_output = {
        "vulnerabilities": [],
        "not_vulnerabilities": ["INFO log messages", "Non-sensitive data"]
    }

    is_valid = validate_agent_specific_fields(
        agent="security-auditor",
        output=test_output
    )

    assert is_valid, "security-auditor agent-specific fields should be valid"


# ============================================================================
# Test 7: End-to-End Agent Execution Tests
# ============================================================================


def test_planner_end_to_end_execution():
    """
    Test planner agent end-to-end execution after cleanup.

    EXPECTED TO FAIL: Cleanup not yet implemented, execution may differ.
    """
    from scripts.test_agent_execution import execute_agent_end_to_end

    result = execute_agent_end_to_end(
        agent="planner",
        test_scenario="plan_new_feature",
        verify_output_format=True
    )

    assert result["success"], "planner execution should succeed"
    assert result["output_valid"], "planner output should be valid"
    assert result["skill_loaded"], "agent-output-formats skill should load"


def test_security_auditor_end_to_end_execution():
    """
    Test security-auditor end-to-end execution after cleanup.

    EXPECTED TO FAIL: Cleanup not yet implemented.
    """
    from scripts.test_agent_execution import execute_agent_end_to_end

    result = execute_agent_end_to_end(
        agent="security-auditor",
        test_scenario="scan_vulnerabilities",
        verify_output_format=True
    )

    assert result["success"], "security-auditor execution should succeed"
    assert result["output_valid"], "security-auditor output should be valid"
    assert result["preserves_not_vulnerability"], \
        "security-auditor should preserve 'What is NOT a Vulnerability' guidance"


def test_all_phase2_agents_end_to_end():
    """
    Test all Phase 2 agents end-to-end execution after cleanup.

    EXPECTED TO FAIL: Cleanup not yet implemented for all agents.
    """
    from scripts.test_agent_execution import execute_all_agents_end_to_end

    results = execute_all_agents_end_to_end(phase="phase2")

    assert isinstance(results, dict), "Should return dict of results"
    assert len(results) == 15, f"Expected 15 Phase 2 agent results, got {len(results)}"

    # All agents should succeed
    for agent_name, result in results.items():
        assert result["success"], f"{agent_name} execution failed"
        assert result["output_valid"], f"{agent_name} output invalid"


# ============================================================================
# Test 8: Performance Tests
# ============================================================================


def test_phase2_agents_maintain_performance():
    """
    Test that Phase 2 agents maintain performance after cleanup.

    EXPECTED TO FAIL: Performance benchmarking needs baseline.
    """
    from scripts.test_agent_performance import benchmark_agent_performance

    for agent_name in PHASE_2_HIGH_PRIORITY:
        perf = benchmark_agent_performance(agent_name)

        assert perf["execution_time"] < 5.0, \
            f"{agent_name} execution time too high: {perf['execution_time']}s (max 5s)"
        assert perf["token_count"] < perf["baseline_token_count"], \
            f"{agent_name} token count not reduced after cleanup"


def test_phase2_reduces_total_context_size():
    """
    Test that Phase 2 cleanup reduces total context size.

    EXPECTED TO FAIL: Cleanup not yet implemented.
    """
    from scripts.test_agent_performance import measure_total_context_size

    baseline_size = measure_total_context_size(phase="phase2", post_cleanup=False)
    cleanup_size = measure_total_context_size(phase="phase2", post_cleanup=True)

    assert cleanup_size < baseline_size, \
        f"Context size not reduced: {baseline_size} -> {cleanup_size}"

    # Should save ~1,700 tokens
    tokens_saved = baseline_size - cleanup_size
    assert tokens_saved >= 1700, \
        f"Token savings insufficient: {tokens_saved} (expected >=1,700)"


# ============================================================================
# Test 9: Error Handling
# ============================================================================


def test_handles_missing_skill_reference():
    """
    Test handling when agent missing skill reference after cleanup.

    EXPECTED TO FAIL: Error detection needs implementation.
    """
    from scripts.test_agent_output import detect_missing_skill_reference

    # Temporarily remove skill reference from planner
    missing_ref = detect_missing_skill_reference("planner")

    # After cleanup, should detect missing reference
    assert not missing_ref, "planner should have skill reference after cleanup"


def test_handles_malformed_output_format_section():
    """
    Test handling of malformed Output Format section.

    EXPECTED TO FAIL: Error handling needs implementation.
    """
    from scripts.test_agent_output import validate_output_format_structure

    # Create test agent with malformed section
    test_content = """
# Test Agent

## Output Format
<!-- Missing proper structure -->
"""

    is_valid = validate_output_format_structure(test_content)

    assert not is_valid, "Should detect malformed Output Format section"


def test_provides_helpful_error_messages():
    """
    Test that helpful error messages are provided for validation failures.

    EXPECTED TO FAIL: Error message improvements needed.
    """
    from scripts.test_agent_output import validate_agent_output

    invalid_output = {"invalid": "structure"}

    try:
        validate_agent_output(agent="planner", output=invalid_output, use_skill_validation=True)
        pytest.fail("Should raise validation error")
    except ValueError as e:
        error_msg = str(e)
        assert "expected format" in error_msg.lower(), "Error should mention expected format"
        assert "agent-output-formats" in error_msg, "Error should reference skill"
