"""
TDD RED Phase Tests for Issue #72 Phase 2: Regression Tests

Tests that Phase 1 agents remain unchanged and existing tests continue passing.
All tests should FAIL initially (no implementation exists yet).

Test Coverage:
1. Verify Phase 1 agents (5 agents) remain unchanged during Phase 2 work
2. Verify all 137 existing tests continue to pass after Phase 2 cleanup
3. Test end-to-end `/auto-implement` workflow after cleanup
4. Test backward compatibility with existing agent consumers
"""

import pytest
import subprocess
from pathlib import Path
from typing import Dict, List, Optional
import json


# Constants
AGENTS_DIR = Path("/Users/akaszubski/Documents/GitHub/autonomous-dev/plugins/autonomous-dev/agents")
TESTS_DIR = Path("/Users/akaszubski/Documents/GitHub/autonomous-dev/tests")

# Phase 1 agents (already cleaned up)
PHASE_1_AGENTS = [
    "test-master",
    "quality-validator",
    "advisor",
    "alignment-validator",
    "project-progress-tracker"
]

# Phase 2 agents (15 remaining)
PHASE_2_AGENTS = [
    "planner", "security-auditor", "brownfield-analyzer", "sync-validator",
    "alignment-analyzer", "issue-creator", "pr-description-generator",
    "project-bootstrapper", "reviewer", "commit-message-generator",
    "project-status-analyzer", "researcher", "implementer", "doc-master",
    "setup-wizard"
]

# All agents
ALL_AGENTS = PHASE_1_AGENTS + PHASE_2_AGENTS


# ============================================================================
# Test 1: Phase 1 Agents Remain Unchanged
# ============================================================================


def test_phase1_agent_content_unchanged():
    """
    Test that Phase 1 agent file content remains unchanged during Phase 2 work.

    EXPECTED TO FAIL: Need baseline comparison mechanism.
    """
    from scripts.test_phase1_stability import compare_agent_content_with_baseline

    for agent_name in PHASE_1_AGENTS:
        unchanged = compare_agent_content_with_baseline(agent_name)

        assert unchanged, \
            f"Phase 1 agent {agent_name} content changed during Phase 2 work"


def test_phase1_agent_token_counts_stable():
    """
    Test that Phase 1 agent token counts remain stable during Phase 2 work.

    EXPECTED TO FAIL: Token stability tracking needed.
    """
    from scripts.measure_agent_tokens import measure_baseline_tokens, get_phase1_baseline

    current_tokens = measure_baseline_tokens()
    phase1_baseline = get_phase1_baseline()

    for agent_name in PHASE_1_AGENTS:
        current = current_tokens.get(agent_name, 0)
        baseline = phase1_baseline.get(agent_name, 0)

        # Allow for minor variations (±5 tokens)
        assert abs(current - baseline) <= 5, \
            f"Phase 1 agent {agent_name} token count changed: {baseline} -> {current}"


def test_phase1_skill_references_intact():
    """
    Test that Phase 1 skill references remain intact during Phase 2 work.

    EXPECTED TO FAIL: Reference tracking needed.
    """
    from scripts.test_phase1_stability import verify_skill_references

    for agent_name in PHASE_1_AGENTS:
        agent_file = AGENTS_DIR / f"{agent_name}.md"

        # Skip test-master (no Output Format section)
        if agent_name == "test-master":
            continue

        content = agent_file.read_text()
        assert "agent-output-formats" in content, \
            f"Phase 1 agent {agent_name} lost skill reference during Phase 2"


def test_phase1_output_format_sections_unchanged():
    """
    Test that Phase 1 Output Format sections remain unchanged.

    EXPECTED TO FAIL: Section comparison mechanism needed.
    """
    from scripts.measure_output_format_sections import extract_output_format_section, get_phase1_sections

    phase1_sections = get_phase1_sections()

    for agent_name in PHASE_1_AGENTS:
        # Skip test-master (no Output Format section)
        if agent_name == "test-master":
            continue

        agent_file = AGENTS_DIR / f"{agent_name}.md"
        current_section = extract_output_format_section(agent_file)
        baseline_section = phase1_sections.get(agent_name, "")

        assert current_section == baseline_section, \
            f"Phase 1 agent {agent_name} Output Format section changed during Phase 2"


def test_phase1_agent_functionality_preserved():
    """
    Test that Phase 1 agent functionality is preserved during Phase 2 work.

    EXPECTED TO FAIL: Functional testing framework needed.
    """
    from scripts.test_agent_execution import execute_agent_end_to_end

    for agent_name in PHASE_1_AGENTS:
        # Skip test-master (tested separately in TDD tests)
        if agent_name == "test-master":
            continue

        result = execute_agent_end_to_end(
            agent=agent_name,
            test_scenario="standard_execution",
            verify_output_format=True
        )

        assert result["success"], f"Phase 1 agent {agent_name} functionality broken"
        assert result["output_valid"], f"Phase 1 agent {agent_name} output invalid"


# ============================================================================
# Test 2: Existing Tests Continue Passing
# ============================================================================


def test_run_all_existing_unit_tests():
    """
    Test that all existing unit tests pass after Phase 2 cleanup.

    EXPECTED TO FAIL: Phase 2 cleanup may break some tests initially.
    """
    result = subprocess.run(
        ["pytest", str(TESTS_DIR / "unit"), "-v", "--tb=short"],
        capture_output=True,
        text=True,
        cwd="/Users/akaszubski/Documents/GitHub/autonomous-dev"
    )

    assert result.returncode == 0, \
        f"Unit tests failed after Phase 2 cleanup:\n{result.stdout}\n{result.stderr}"


def test_run_all_existing_integration_tests():
    """
    Test that all existing integration tests pass after Phase 2 cleanup.

    EXPECTED TO FAIL: Integration tests may fail if agent interactions changed.
    """
    result = subprocess.run(
        ["pytest", str(TESTS_DIR / "integration"), "-v", "--tb=short"],
        capture_output=True,
        text=True,
        cwd="/Users/akaszubski/Documents/GitHub/autonomous-dev"
    )

    assert result.returncode == 0, \
        f"Integration tests failed after Phase 2 cleanup:\n{result.stdout}\n{result.stderr}"


def test_run_all_existing_skill_tests():
    """
    Test that all existing skill tests pass after Phase 2 cleanup.

    EXPECTED TO FAIL: Skill tests may need updates for Phase 2 agents.
    """
    result = subprocess.run(
        ["pytest", str(TESTS_DIR / "unit/skills"), "-v", "--tb=short"],
        capture_output=True,
        text=True,
        cwd="/Users/akaszubski/Documents/GitHub/autonomous-dev"
    )

    assert result.returncode == 0, \
        f"Skill tests failed after Phase 2 cleanup:\n{result.stdout}\n{result.stderr}"


def test_existing_test_count_preserved():
    """
    Test that test count remains 137+ after Phase 2 (no tests removed).

    EXPECTED TO FAIL: Test count validation needed.
    """
    from scripts.test_regression import count_existing_tests

    test_count = count_existing_tests()

    assert test_count >= 137, \
        f"Test count decreased after Phase 2: {test_count} (expected >=137)"


def test_no_test_regressions_introduced():
    """
    Test that no previously passing tests now fail after Phase 2.

    EXPECTED TO FAIL: Regression detection needed.
    """
    from scripts.test_regression import detect_test_regressions

    regressions = detect_test_regressions(baseline="phase1_complete")

    assert len(regressions) == 0, \
        f"Test regressions detected after Phase 2: {regressions}"


# ============================================================================
# Test 3: End-to-End /auto-implement Workflow
# ============================================================================


def test_auto_implement_workflow_completes():
    """
    Test that /auto-implement workflow completes successfully after Phase 2.

    EXPECTED TO FAIL: Workflow testing infrastructure needed.
    """
    from scripts.test_auto_implement_workflow import run_workflow_test

    result = run_workflow_test(
        feature="Add logging to test module",
        verify_all_agents=True
    )

    assert result["success"], "/auto-implement workflow failed after Phase 2 cleanup"
    assert result["all_agents_ran"], "Not all agents ran in workflow"
    assert result["output_valid"], "Workflow output invalid"


def test_auto_implement_uses_phase2_agents():
    """
    Test that /auto-implement workflow uses Phase 2 agents correctly.

    EXPECTED TO FAIL: Agent usage tracking needed.
    """
    from scripts.test_auto_implement_workflow import run_workflow_test, get_agents_used

    result = run_workflow_test(
        feature="Add error handling",
        verify_all_agents=True
    )

    agents_used = get_agents_used(result)

    # Should use planner, implementer, reviewer (all Phase 2 or mixed)
    expected_agents = ["planner", "implementer", "reviewer"]
    for agent in expected_agents:
        assert agent in agents_used, \
            f"/auto-implement should use {agent} agent (Phase 2)"


def test_auto_implement_parallel_validation_works():
    """
    Test that parallel validation (reviewer, security-auditor, doc-master) works after Phase 2.

    EXPECTED TO FAIL: Parallel execution validation needed.
    """
    from scripts.test_auto_implement_workflow import run_workflow_test, verify_parallel_execution

    result = run_workflow_test(
        feature="Add validation logic",
        verify_parallel_validation=True
    )

    parallel_verified = verify_parallel_execution(result, agents=["reviewer", "security-auditor", "doc-master"])

    assert parallel_verified, "Parallel validation not working after Phase 2 cleanup"


def test_auto_implement_maintains_tdd_workflow():
    """
    Test that TDD workflow (test-master -> implementer) maintained after Phase 2.

    EXPECTED TO FAIL: TDD workflow validation needed.
    """
    from scripts.test_auto_implement_workflow import run_workflow_test, verify_tdd_order

    result = run_workflow_test(
        feature="Add calculation function",
        verify_tdd=True
    )

    tdd_order_correct = verify_tdd_order(result, agents=["test-master", "implementer"])

    assert tdd_order_correct, "TDD workflow order broken after Phase 2 cleanup"


def test_auto_implement_generates_valid_output():
    """
    Test that /auto-implement generates valid output after Phase 2.

    EXPECTED TO FAIL: Output validation framework needed.
    """
    from scripts.test_auto_implement_workflow import run_workflow_test, validate_workflow_output

    result = run_workflow_test(
        feature="Add feature flag",
        verify_output=True
    )

    output_valid = validate_workflow_output(result)

    assert output_valid, "/auto-implement output invalid after Phase 2 cleanup"


# ============================================================================
# Test 4: Backward Compatibility
# ============================================================================


def test_agent_api_backward_compatible():
    """
    Test that agent API remains backward compatible after Phase 2.

    EXPECTED TO FAIL: API compatibility checking needed.
    """
    from scripts.test_backward_compatibility import check_agent_api_compatibility

    for agent_name in PHASE_2_AGENTS:
        compatible = check_agent_api_compatibility(
            agent=agent_name,
            baseline_version="phase1_complete"
        )

        assert compatible, f"{agent_name} API not backward compatible after Phase 2"


def test_agent_output_format_compatible():
    """
    Test that agent output format remains compatible with existing consumers.

    EXPECTED TO FAIL: Output format compatibility checking needed.
    """
    from scripts.test_backward_compatibility import check_output_format_compatibility

    for agent_name in PHASE_2_AGENTS:
        compatible = check_output_format_compatibility(
            agent=agent_name,
            baseline_version="phase1_complete"
        )

        assert compatible, f"{agent_name} output format not compatible after Phase 2"


def test_skill_reference_backward_compatible():
    """
    Test that skill references are backward compatible.

    EXPECTED TO FAIL: Skill reference compatibility checking needed.
    """
    from scripts.test_backward_compatibility import check_skill_reference_compatibility

    # New skill references should work with existing Claude Code 2.0+ progressive disclosure
    compatible = check_skill_reference_compatibility(
        skill="agent-output-formats",
        agents=PHASE_2_AGENTS
    )

    assert compatible, "Skill references not backward compatible with Claude Code 2.0+"


def test_existing_workflows_not_broken():
    """
    Test that existing workflows (commands, hooks) not broken by Phase 2.

    EXPECTED TO FAIL: Workflow compatibility testing needed.
    """
    from scripts.test_backward_compatibility import test_existing_workflows

    workflows = [
        "/auto-implement",
        "/research",
        "/plan",
        "/test-feature",
        "/implement",
        "/review",
        "/security-scan",
        "/update-docs"
    ]

    for workflow in workflows:
        result = test_existing_workflows(workflow)
        assert result["compatible"], f"Workflow {workflow} broken by Phase 2 cleanup"


def test_hook_integration_preserved():
    """
    Test that hook integration with agents preserved after Phase 2.

    EXPECTED TO FAIL: Hook integration testing needed.
    """
    from scripts.test_backward_compatibility import test_hook_integration

    hooks_to_test = [
        "auto_git_workflow.py",  # Uses commit-message-generator (Phase 2)
        "enforce_pipeline_complete.py",  # Tracks all agents
        "auto_update_project_progress.py"  # Uses project-progress-tracker (Phase 1)
    ]

    for hook_name in hooks_to_test:
        result = test_hook_integration(hook_name)
        assert result["compatible"], f"Hook {hook_name} broken by Phase 2 cleanup"


# ============================================================================
# Test 5: Performance Regression Tests
# ============================================================================


def test_auto_implement_performance_not_degraded():
    """
    Test that /auto-implement performance not degraded by Phase 2 cleanup.

    EXPECTED TO FAIL: Performance baseline comparison needed.
    """
    from scripts.test_performance_regression import benchmark_auto_implement

    current_perf = benchmark_auto_implement()
    baseline_perf = get_performance_baseline("phase1_complete")

    # Performance should improve or remain stable (not degrade)
    assert current_perf["execution_time"] <= baseline_perf["execution_time"] * 1.05, \
        f"Performance degraded: {baseline_perf['execution_time']}s -> {current_perf['execution_time']}s"


def test_token_usage_reduced():
    """
    Test that token usage is reduced after Phase 2 cleanup.

    EXPECTED TO FAIL: Token usage comparison needed.
    """
    from scripts.test_performance_regression import measure_total_token_usage

    current_usage = measure_total_token_usage(phase="phase2", post_cleanup=True)
    baseline_usage = measure_total_token_usage(phase="phase2", post_cleanup=False)

    assert current_usage < baseline_usage, \
        f"Token usage not reduced: {baseline_usage} -> {current_usage}"

    # Should save ~1,700 tokens
    tokens_saved = baseline_usage - current_usage
    assert tokens_saved >= 1700, \
        f"Token savings insufficient: {tokens_saved} (expected >=1,700)"


def test_context_size_reduced():
    """
    Test that context size is reduced after Phase 2 cleanup.

    EXPECTED TO FAIL: Context size measurement needed.
    """
    from scripts.test_performance_regression import measure_context_size

    current_size = measure_context_size(phase="phase2", post_cleanup=True)
    baseline_size = measure_context_size(phase="phase2", post_cleanup=False)

    assert current_size < baseline_size, \
        f"Context size not reduced: {baseline_size} -> {current_size}"


def test_agent_execution_time_maintained():
    """
    Test that individual agent execution times maintained after cleanup.

    EXPECTED TO FAIL: Agent timing baseline needed.
    """
    from scripts.test_performance_regression import benchmark_agent_execution_time

    for agent_name in PHASE_2_AGENTS:
        current_time = benchmark_agent_execution_time(agent_name)
        baseline_time = get_agent_baseline_time(agent_name, "phase1_complete")

        # Execution time should not increase by more than 5%
        assert current_time <= baseline_time * 1.05, \
            f"{agent_name} execution time increased: {baseline_time}s -> {current_time}s"


# ============================================================================
# Test 6: Documentation Consistency
# ============================================================================


def test_claude_md_updated_for_phase2():
    """
    Test that CLAUDE.md is updated with Phase 2 completion.

    EXPECTED TO FAIL: Documentation update verification needed.
    """
    claude_md = Path("/Users/akaszubski/Documents/GitHub/autonomous-dev/CLAUDE.md")
    content = claude_md.read_text()

    # Should mention Phase 2 completion
    assert "Phase 2" in content and "complete" in content.lower(), \
        "CLAUDE.md should document Phase 2 completion"

    # Should mention combined token savings
    assert "2,883 tokens" in content or "2883" in content, \
        "CLAUDE.md should document combined Phase 1+2 savings"


def test_issue_72_documentation_complete():
    """
    Test that Issue #72 documentation is complete after Phase 2.

    EXPECTED TO FAIL: Documentation completeness check needed.
    """
    docs_file = Path("/Users/akaszubski/Documents/GitHub/autonomous-dev/docs/ISSUE_72_IMPLEMENTATION_SUMMARY.md")

    content = docs_file.read_text()

    # Should document Phase 2
    assert "Phase 2" in content, "Issue #72 docs missing Phase 2 section"
    assert "1,700 tokens" in content or "1700" in content, \
        "Issue #72 docs should document Phase 2 savings"


def test_changelog_updated_for_phase2():
    """
    Test that CHANGELOG.md is updated with Phase 2 changes.

    EXPECTED TO FAIL: Changelog update verification needed.
    """
    changelog = Path("/Users/akaszubski/Documents/GitHub/autonomous-dev/CHANGELOG.md")
    content = changelog.read_text()

    # Should have Phase 2 entry
    assert "Issue #72" in content and "Phase 2" in content, \
        "CHANGELOG.md missing Phase 2 entry"


def test_all_phase2_agents_documented():
    """
    Test that all Phase 2 agents are documented in relevant files.

    EXPECTED TO FAIL: Agent documentation verification needed.
    """
    from scripts.test_documentation import verify_agent_documentation

    for agent_name in PHASE_2_AGENTS:
        documented = verify_agent_documentation(agent_name)

        assert documented, f"{agent_name} not properly documented after Phase 2"


# ============================================================================
# Test 7: Test Quality Metrics
# ============================================================================


def test_code_coverage_maintained():
    """
    Test that code coverage is maintained or improved after Phase 2.

    EXPECTED TO FAIL: Coverage comparison needed.
    """
    from scripts.test_quality_metrics import measure_code_coverage

    current_coverage = measure_code_coverage()
    baseline_coverage = get_coverage_baseline("phase1_complete")

    assert current_coverage >= baseline_coverage, \
        f"Code coverage decreased: {baseline_coverage}% -> {current_coverage}%"


def test_test_quality_maintained():
    """
    Test that test quality is maintained after Phase 2.

    EXPECTED TO FAIL: Test quality metrics needed.
    """
    from scripts.test_quality_metrics import analyze_test_quality

    quality = analyze_test_quality()

    assert quality["coverage"] >= 80.0, f"Coverage below target: {quality['coverage']}%"
    assert quality["assertions_per_test"] >= 1.0, "Tests lack sufficient assertions"
    assert quality["test_isolation"] >= 95.0, "Tests lack proper isolation"


def test_no_flaky_tests_introduced():
    """
    Test that no flaky tests introduced by Phase 2 cleanup.

    EXPECTED TO FAIL: Flaky test detection needed.
    """
    from scripts.test_quality_metrics import detect_flaky_tests

    flaky_tests = detect_flaky_tests(runs=5)

    assert len(flaky_tests) == 0, f"Flaky tests detected: {flaky_tests}"


def test_test_execution_time_reasonable():
    """
    Test that test execution time remains reasonable after Phase 2.

    EXPECTED TO FAIL: Test timing baseline needed.
    """
    from scripts.test_quality_metrics import measure_test_execution_time

    execution_time = measure_test_execution_time()

    # Full test suite should complete within 5 minutes
    assert execution_time < 300, \
        f"Test suite too slow: {execution_time}s (max 300s)"


# ============================================================================
# Helper Functions
# ============================================================================


def get_performance_baseline(version: str) -> Dict:
    """
    Get performance baseline for given version.

    EXPECTED TO FAIL: Baseline storage/retrieval not implemented.
    """
    raise NotImplementedError("get_performance_baseline not implemented")


def get_agent_baseline_time(agent_name: str, version: str) -> float:
    """
    Get baseline execution time for agent.

    EXPECTED TO FAIL: Agent timing baseline not implemented.
    """
    raise NotImplementedError("get_agent_baseline_time not implemented")


def get_coverage_baseline(version: str) -> float:
    """
    Get code coverage baseline for given version.

    EXPECTED TO FAIL: Coverage baseline not implemented.
    """
    raise NotImplementedError("get_coverage_baseline not implemented")


# ============================================================================
# Test 8: Error Handling and Edge Cases
# ============================================================================


def test_handles_partial_phase2_completion():
    """
    Test handling of partial Phase 2 completion (some agents cleaned, others not).

    EXPECTED TO FAIL: Partial completion detection needed.
    """
    from scripts.test_regression import detect_partial_completion

    is_partial = detect_partial_completion(phase="phase2")

    # After full Phase 2 implementation, should not be partial
    assert not is_partial, "Phase 2 completion is partial (some agents not cleaned)"


def test_handles_mixed_phase1_phase2_agents():
    """
    Test handling of mixed Phase 1 and Phase 2 agents in workflows.

    EXPECTED TO FAIL: Mixed agent handling testing needed.
    """
    from scripts.test_auto_implement_workflow import run_workflow_test

    # Workflow uses both Phase 1 (test-master) and Phase 2 (planner, implementer)
    result = run_workflow_test(
        feature="Add mixed feature",
        verify_mixed_agents=True
    )

    assert result["success"], "Workflow with mixed Phase 1/Phase 2 agents failed"


def test_graceful_degradation_on_skill_load_failure():
    """
    Test graceful degradation if agent-output-formats skill fails to load.

    EXPECTED TO FAIL: Graceful degradation handling needed.
    """
    from scripts.test_error_handling import simulate_skill_load_failure

    result = simulate_skill_load_failure(agent="planner", skill="agent-output-formats")

    # Agent should still function with fallback output format
    assert result["agent_ran"], "Agent should run even if skill load fails"
    assert result["used_fallback"], "Agent should use fallback output format"
