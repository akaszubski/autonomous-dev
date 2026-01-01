"""
TDD RED Phase Tests for Issue #72 Phase 2: Token Measurement Tests

Tests token counting for 15 remaining agents after Phase 1 cleanup.
All tests should FAIL initially (no implementation exists yet).

Phase 2 Agents (15 total):
- High-priority (8): planner, security-auditor, brownfield-analyzer, sync-validator,
  alignment-analyzer, issue-creator, pr-description-generator, project-bootstrapper
- Medium-priority (4): reviewer, commit-message-generator, project-status-analyzer
- Low-priority (3): researcher, implementer, doc-master, setup-wizard

Expected Savings: ~1,700 tokens (7% reduction in Output Format sections)
Combined Phase 1+2: ~2,883 tokens total

Test Coverage:
1. Baseline token measurement for 15 Phase 2 agents
2. Post-cleanup token measurement
3. Token reduction calculation (expect 1,700+ tokens saved)
4. Combined Phase 1+2 savings verification (expect 2,883+ tokens total)
5. Per-agent token analysis for Phase 2 agents
"""

import pytest
import json
from pathlib import Path
from typing import Dict, List, Optional


# Constants
AGENTS_DIR = Path("${PROJECT_ROOT}/plugins/autonomous-dev/agents")

# Phase 1 agents (already cleaned up)
PHASE_1_AGENTS = [
    "test-master",
    "quality-validator",
    "advisor",
    "alignment-validator",
    "project-progress-tracker"
]

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

# All 20 agents
ALL_AGENTS = PHASE_1_AGENTS + PHASE_2_AGENTS


# ============================================================================
# Test 1: Baseline Token Measurement for Phase 2 Agents
# ============================================================================


def test_measure_baseline_tokens_for_phase2_agents():
    """
    Test baseline token measurement for all 15 Phase 2 agents.

    EXPECTED TO FAIL: Phase 2 agents not yet cleaned up, measurement function needs update.
    """
    from scripts.measure_agent_tokens import measure_baseline_tokens

    baseline = measure_baseline_tokens()

    # Should include all Phase 2 agents
    for agent_name in PHASE_2_AGENTS:
        assert agent_name in baseline, f"Missing baseline for Phase 2 agent: {agent_name}"
        assert baseline[agent_name] > 0, f"Invalid token count for {agent_name}"

    # Total baseline for Phase 2 agents should be substantial
    phase2_total = sum(baseline.get(agent, 0) for agent in PHASE_2_AGENTS)
    assert phase2_total > 15000, \
        f"Phase 2 baseline too low: {phase2_total} tokens (expected >15,000)"


def test_baseline_includes_output_format_sections():
    """
    Test that baseline measurement captures Output Format sections.

    EXPECTED TO FAIL: Need to verify Output Format sections are measured.
    """
    from scripts.measure_agent_tokens import measure_baseline_tokens, get_section_tokens

    baseline = measure_baseline_tokens()

    # High-priority agents should have Output Format sections with tokens
    for agent_name in PHASE_2_HIGH_PRIORITY:
        section_tokens = get_section_tokens(agent_name, "Output Format")
        assert section_tokens > 0, \
            f"{agent_name} missing Output Format section tokens (got {section_tokens})"


def test_baseline_measurement_per_agent():
    """
    Test per-agent baseline token counts for Phase 2.

    EXPECTED TO FAIL: Need individual agent measurements.
    """
    from scripts.measure_agent_tokens import measure_agent_tokens_detailed

    # Test each Phase 2 agent individually
    for agent_name in PHASE_2_AGENTS:
        agent_file = AGENTS_DIR / f"{agent_name}.md"
        assert agent_file.exists(), f"Agent file not found: {agent_file}"

        tokens = measure_agent_tokens_detailed(agent_file)

        assert isinstance(tokens, dict), f"Expected dict for {agent_name}"
        assert "total" in tokens, f"Missing 'total' key for {agent_name}"
        assert tokens["total"] > 100, \
            f"Token count too low for {agent_name}: {tokens['total']}"


# ============================================================================
# Test 2: Post-Cleanup Token Measurement
# ============================================================================


def test_measure_post_cleanup_tokens_for_phase2():
    """
    Test post-cleanup token measurement for Phase 2 agents.

    EXPECTED TO FAIL: Phase 2 cleanup not yet implemented.
    """
    from scripts.measure_agent_tokens import measure_post_cleanup_tokens

    post_cleanup = measure_post_cleanup_tokens()

    # Should include all Phase 2 agents
    for agent_name in PHASE_2_AGENTS:
        assert agent_name in post_cleanup, f"Missing post-cleanup for Phase 2 agent: {agent_name}"
        assert post_cleanup[agent_name] > 0, f"Invalid token count for {agent_name}"

    # Total post-cleanup should be less than baseline
    phase2_total = sum(post_cleanup.get(agent, 0) for agent in PHASE_2_AGENTS)
    assert phase2_total > 13000, \
        f"Phase 2 post-cleanup total: {phase2_total} tokens (expected >13,000 after cleanup)"


def test_post_cleanup_reduces_output_format_sections():
    """
    Test that Output Format sections are reduced after cleanup.

    EXPECTED TO FAIL: Cleanup not yet implemented.
    """
    from scripts.measure_agent_tokens import get_section_tokens

    # High-priority agents should have reduced Output Format sections
    for agent_name in PHASE_2_HIGH_PRIORITY:
        section_tokens = get_section_tokens(agent_name, "Output Format", post_cleanup=True)
        baseline_tokens = get_section_tokens(agent_name, "Output Format", post_cleanup=False)

        assert section_tokens < baseline_tokens, \
            f"{agent_name} Output Format section not reduced: {section_tokens} >= {baseline_tokens}"


def test_post_cleanup_preserves_agent_specific_guidance():
    """
    Test that agent-specific guidance is preserved in cleaned sections.

    EXPECTED TO FAIL: Cleanup not yet implemented, need to verify preserved content.
    """
    from scripts.measure_agent_tokens import extract_agent_specific_guidance

    # security-auditor should preserve "What is NOT a Vulnerability"
    security_guidance = extract_agent_specific_guidance("security-auditor")
    assert security_guidance is not None, "security-auditor guidance missing"
    assert "NOT a Vulnerability" in security_guidance, \
        "security-auditor missing 'What is NOT a Vulnerability' guidance"

    # planner should preserve planning-specific guidance
    planner_guidance = extract_agent_specific_guidance("planner")
    assert planner_guidance is not None, "planner guidance missing"


# ============================================================================
# Test 3: Token Reduction Calculation
# ============================================================================


def test_calculate_phase2_token_savings():
    """
    Test token savings calculation for Phase 2 agents.

    EXPECTED TO FAIL: Phase 2 cleanup not yet implemented, savings should be ~1,700 tokens.
    """
    from scripts.measure_agent_tokens import calculate_token_savings

    savings = calculate_token_savings(phase="phase2")

    assert isinstance(savings, dict), "Savings should be a dictionary"
    assert "total_saved" in savings, "Missing 'total_saved' key"
    assert "percentage_reduction" in savings, "Missing 'percentage_reduction' key"
    assert "per_agent" in savings, "Missing 'per_agent' key"

    # Phase 2 should save ~1,700 tokens (7% reduction)
    assert savings["total_saved"] >= 1700, \
        f"Phase 2 savings too low: {savings['total_saved']} tokens (expected >=1,700)"

    # Percentage reduction should be ~7%
    assert savings["percentage_reduction"] >= 6.5, \
        f"Phase 2 reduction too low: {savings['percentage_reduction']}% (expected >=6.5%)"


def test_token_savings_per_agent_phase2():
    """
    Test per-agent token savings for Phase 2 agents.

    EXPECTED TO FAIL: Cleanup not yet implemented.
    """
    from scripts.measure_agent_tokens import calculate_token_savings

    savings = calculate_token_savings(phase="phase2")
    per_agent = savings.get("per_agent", {})

    # Each Phase 2 agent should have some savings
    for agent_name in PHASE_2_HIGH_PRIORITY:
        assert agent_name in per_agent, f"Missing savings data for {agent_name}"
        agent_savings = per_agent[agent_name]

        assert agent_savings > 0, \
            f"No savings for high-priority agent {agent_name}: {agent_savings}"


def test_token_savings_breakdown_by_section():
    """
    Test that token savings are broken down by section.

    EXPECTED TO FAIL: Need section-level savings tracking.
    """
    from scripts.measure_agent_tokens import calculate_token_savings_by_section

    savings = calculate_token_savings_by_section(phase="phase2")

    assert "output_format" in savings, "Missing 'output_format' section savings"

    # Output Format section should have most savings
    output_format_savings = savings["output_format"]
    assert output_format_savings >= 1500, \
        f"Output Format savings too low: {output_format_savings} (expected >=1,500)"


# ============================================================================
# Test 4: Combined Phase 1+2 Savings Verification
# ============================================================================


def test_combined_phase1_and_phase2_savings():
    """
    Test combined token savings from Phase 1 and Phase 2.

    EXPECTED TO FAIL: Phase 2 not yet implemented, total should be ~2,883 tokens.
    """
    from scripts.measure_agent_tokens import calculate_combined_savings

    combined = calculate_combined_savings()

    assert isinstance(combined, dict), "Combined savings should be a dictionary"
    assert "phase1_saved" in combined, "Missing 'phase1_saved' key"
    assert "phase2_saved" in combined, "Missing 'phase2_saved' key"
    assert "total_saved" in combined, "Missing 'total_saved' key"

    # Phase 1: ~1,183 tokens (already implemented)
    assert combined["phase1_saved"] >= 1183, \
        f"Phase 1 savings incorrect: {combined['phase1_saved']} (expected >=1,183)"

    # Phase 2: ~1,700 tokens (not yet implemented)
    assert combined["phase2_saved"] >= 1700, \
        f"Phase 2 savings too low: {combined['phase2_saved']} (expected >=1,700)"

    # Combined: ~2,883 tokens
    assert combined["total_saved"] >= 2883, \
        f"Combined savings too low: {combined['total_saved']} (expected >=2,883)"


def test_combined_savings_percentage_across_all_agents():
    """
    Test combined savings percentage across all 20 agents.

    EXPECTED TO FAIL: Phase 2 not yet implemented.
    """
    from scripts.measure_agent_tokens import calculate_combined_savings

    combined = calculate_combined_savings()

    assert "percentage_reduction" in combined, "Missing 'percentage_reduction' key"

    # Combined reduction should be ~10.9% (2,883 / 26,401 baseline)
    assert combined["percentage_reduction"] >= 10.0, \
        f"Combined reduction too low: {combined['percentage_reduction']}% (expected >=10%)"


def test_combined_savings_with_issues_63_64():
    """
    Test combined savings including Issues #63, #64, #72.

    EXPECTED TO FAIL: Phase 2 not yet implemented.
    """
    from scripts.measure_agent_tokens import calculate_all_optimization_savings

    all_savings = calculate_all_optimization_savings()

    assert "issue_63_64_saved" in all_savings, "Missing Issues #63, #64 savings"
    assert "issue_72_saved" in all_savings, "Missing Issue #72 savings"
    assert "total_saved" in all_savings, "Missing 'total_saved' key"

    # Issues #63, #64: ~10,500 tokens
    assert all_savings["issue_63_64_saved"] >= 10500, \
        f"Issues #63, #64 savings incorrect: {all_savings['issue_63_64_saved']}"

    # Issue #72: ~2,883 tokens (Phase 1 + Phase 2)
    assert all_savings["issue_72_saved"] >= 2883, \
        f"Issue #72 savings too low: {all_savings['issue_72_saved']} (expected >=2,883)"

    # Total: ~11,683 tokens (20-28% reduction)
    assert all_savings["total_saved"] >= 11683, \
        f"Total savings too low: {all_savings['total_saved']} (expected >=11,683)"


# ============================================================================
# Test 5: Per-Agent Token Analysis for Phase 2
# ============================================================================


def test_per_agent_analysis_high_priority():
    """
    Test detailed per-agent analysis for high-priority Phase 2 agents.

    EXPECTED TO FAIL: Cleanup not yet implemented.
    """
    from scripts.measure_agent_tokens import analyze_agent_tokens

    for agent_name in PHASE_2_HIGH_PRIORITY:
        analysis = analyze_agent_tokens(agent_name)

        assert analysis is not None, f"Missing analysis for {agent_name}"
        assert "baseline_tokens" in analysis, f"Missing baseline for {agent_name}"
        assert "post_cleanup_tokens" in analysis, f"Missing post-cleanup for {agent_name}"
        assert "tokens_saved" in analysis, f"Missing savings for {agent_name}"

        # High-priority agents should save significant tokens
        assert analysis["tokens_saved"] > 50, \
            f"Insufficient savings for {agent_name}: {analysis['tokens_saved']} (expected >50)"


def test_per_agent_analysis_medium_priority():
    """
    Test detailed per-agent analysis for medium-priority Phase 2 agents.

    EXPECTED TO FAIL: Cleanup not yet implemented.
    """
    from scripts.measure_agent_tokens import analyze_agent_tokens

    for agent_name in PHASE_2_MEDIUM_PRIORITY:
        analysis = analyze_agent_tokens(agent_name)

        assert analysis is not None, f"Missing analysis for {agent_name}"
        assert "tokens_saved" in analysis, f"Missing savings for {agent_name}"

        # Medium-priority agents should save moderate tokens
        assert analysis["tokens_saved"] > 30, \
            f"Insufficient savings for {agent_name}: {analysis['tokens_saved']} (expected >30)"


def test_per_agent_analysis_low_priority():
    """
    Test detailed per-agent analysis for low-priority Phase 2 agents.

    EXPECTED TO FAIL: Cleanup not yet implemented.
    """
    from scripts.measure_agent_tokens import analyze_agent_tokens

    for agent_name in PHASE_2_LOW_PRIORITY:
        analysis = analyze_agent_tokens(agent_name)

        assert analysis is not None, f"Missing analysis for {agent_name}"
        assert "tokens_saved" in analysis, f"Missing savings for {agent_name}"

        # Low-priority agents should save some tokens
        assert analysis["tokens_saved"] >= 0, \
            f"Invalid savings for {agent_name}: {analysis['tokens_saved']}"


def test_per_agent_section_breakdown():
    """
    Test section-level token breakdown for Phase 2 agents.

    EXPECTED TO FAIL: Need section-level analysis.
    """
    from scripts.measure_agent_tokens import analyze_agent_sections

    for agent_name in PHASE_2_HIGH_PRIORITY:
        sections = analyze_agent_sections(agent_name)

        assert isinstance(sections, dict), f"Sections should be dict for {agent_name}"
        assert "output_format" in sections, f"Missing Output Format section for {agent_name}"

        output_format = sections["output_format"]
        assert "baseline_tokens" in output_format, f"Missing baseline for {agent_name} Output Format"
        assert "post_cleanup_tokens" in output_format, f"Missing post-cleanup for {agent_name} Output Format"


# ============================================================================
# Test 6: Validation Tests
# ============================================================================


def test_phase1_agents_remain_unchanged():
    """
    Test that Phase 1 agents remain unchanged during Phase 2 cleanup.

    EXPECTED TO FAIL: Need to verify Phase 1 stability.
    """
    from scripts.measure_agent_tokens import measure_baseline_tokens, measure_post_cleanup_tokens

    baseline = measure_baseline_tokens()
    post_cleanup = measure_post_cleanup_tokens()

    # Phase 1 agents should have same token counts (already cleaned)
    for agent_name in PHASE_1_AGENTS:
        baseline_tokens = baseline.get(agent_name, 0)
        post_cleanup_tokens = post_cleanup.get(agent_name, 0)

        # Allow for minor variations (±5 tokens) due to skill reference formatting
        assert abs(baseline_tokens - post_cleanup_tokens) <= 5, \
            f"Phase 1 agent {agent_name} changed: {baseline_tokens} -> {post_cleanup_tokens}"


def test_all_agents_have_measurements():
    """
    Test that all 20 agents have baseline and post-cleanup measurements.

    EXPECTED TO FAIL: Phase 2 measurements not yet complete.
    """
    from scripts.measure_agent_tokens import measure_baseline_tokens, measure_post_cleanup_tokens

    baseline = measure_baseline_tokens()
    post_cleanup = measure_post_cleanup_tokens()

    # All 20 agents should be measured
    assert len(baseline) == 20, f"Expected 20 baseline measurements, got {len(baseline)}"
    assert len(post_cleanup) == 20, f"Expected 20 post-cleanup measurements, got {len(post_cleanup)}"

    # Check each agent list
    for agent_name in ALL_AGENTS:
        assert agent_name in baseline, f"Missing baseline for {agent_name}"
        assert agent_name in post_cleanup, f"Missing post-cleanup for {agent_name}"


def test_savings_report_generation():
    """
    Test that savings report can be generated for Phase 2.

    EXPECTED TO FAIL: Report generation needs Phase 2 data.
    """
    from scripts.measure_agent_tokens import generate_savings_report

    report = generate_savings_report(phase="phase2", format="json")

    assert report is not None, "Report generation failed"
    assert "phase2_agents" in report, "Report missing Phase 2 agents"
    assert "total_savings" in report, "Report missing total savings"
    assert "per_agent_savings" in report, "Report missing per-agent savings"

    # Report should include all Phase 2 agents
    phase2_agents = report["phase2_agents"]
    assert len(phase2_agents) == 15, f"Report missing agents: {len(phase2_agents)}/15"


# ============================================================================
# Test 7: Error Handling
# ============================================================================


def test_handles_missing_agent_file():
    """
    Test error handling for missing agent files.

    EXPECTED TO FAIL: Error handling needs implementation.
    """
    from scripts.measure_agent_tokens import analyze_agent_tokens

    # Try to analyze non-existent agent
    with pytest.raises(FileNotFoundError) as exc_info:
        analyze_agent_tokens("nonexistent-agent")

    assert "Agent file not found" in str(exc_info.value)


def test_handles_invalid_phase():
    """
    Test error handling for invalid phase parameter.

    EXPECTED TO FAIL: Validation needs implementation.
    """
    from scripts.measure_agent_tokens import calculate_token_savings

    with pytest.raises(ValueError) as exc_info:
        calculate_token_savings(phase="invalid_phase")

    assert "Invalid phase" in str(exc_info.value)


def test_handles_missing_output_format_section():
    """
    Test handling of agents without Output Format section.

    EXPECTED TO FAIL: Special case handling needed.
    """
    from scripts.measure_agent_tokens import get_section_tokens

    # test-master has no Output Format section
    tokens = get_section_tokens("test-master", "Output Format")

    # Should return 0 tokens, not error
    assert tokens == 0, f"Expected 0 tokens for missing section, got {tokens}"
