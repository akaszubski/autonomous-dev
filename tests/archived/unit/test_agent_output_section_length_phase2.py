"""
TDD RED Phase Tests for Issue #72 Phase 2: Section Length Validation Tests

Tests that no agent has >30 lines in Output Format section after Phase 2 cleanup.
All tests should FAIL initially (no implementation exists yet).

Phase 2 Agents (15 total):
- High-priority (8): planner, security-auditor, brownfield-analyzer, sync-validator,
  alignment-analyzer, issue-creator, pr-description-generator, project-bootstrapper
- Medium-priority (4): reviewer, commit-message-generator, project-status-analyzer
- Low-priority (3): researcher, implementer, doc-master, setup-wizard

Test Coverage:
1. Measure Output Format section line counts for Phase 2 agents
2. Validate no agent exceeds 30-line threshold after cleanup
3. Identify verbose agents requiring cleanup (before implementation)
4. Track Phase 2 cleanup progress
5. Verify agent-specific guidance is preserved
"""

import pytest
from pathlib import Path
from typing import Dict, List, Optional, Tuple
import re


# Constants
AGENTS_DIR = Path("/Users/akaszubski/Documents/GitHub/autonomous-dev/plugins/autonomous-dev/agents")
MAX_OUTPUT_FORMAT_LINES = 30

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
ALL_AGENTS = PHASE_1_AGENTS + PHASE_2_AGENTS


# ============================================================================
# Test 1: Measure Output Format Section Line Counts - Before Cleanup
# ============================================================================


def test_count_output_format_lines_before_cleanup():
    """
    Test measuring Output Format section line counts before cleanup.

    EXPECTED TO FAIL: Function needs implementation to count lines.
    """
    from scripts.measure_output_format_sections import count_output_format_lines

    # Test high-priority agent with verbose Output Format section
    planner_file = AGENTS_DIR / "planner.md"
    assert planner_file.exists(), f"Agent file not found: {planner_file}"

    line_count = count_output_format_lines(planner_file)

    assert isinstance(line_count, int), "Line count should be integer"
    assert line_count > 30, \
        f"planner should have >30 lines in Output Format before cleanup, got {line_count}"


def test_identify_verbose_agents_before_cleanup():
    """
    Test identifying all Phase 2 agents with verbose Output Format sections.

    EXPECTED TO FAIL: Need to identify which agents exceed threshold before cleanup.
    """
    from scripts.measure_output_format_sections import identify_verbose_agents

    verbose_agents = identify_verbose_agents(threshold=MAX_OUTPUT_FORMAT_LINES, phase="phase2")

    assert isinstance(verbose_agents, list), "Should return list of verbose agents"
    assert len(verbose_agents) > 0, "Should identify verbose agents in Phase 2"

    # High-priority agents likely to be verbose
    expected_verbose = ["planner", "security-auditor", "brownfield-analyzer"]
    for agent_name in expected_verbose:
        assert agent_name in verbose_agents, \
            f"Expected {agent_name} to have verbose Output Format section"


def test_measure_all_phase2_section_lengths():
    """
    Test measuring section lengths for all Phase 2 agents.

    EXPECTED TO FAIL: Measurement function needs implementation.
    """
    from scripts.measure_output_format_sections import measure_all_section_lengths

    section_lengths = measure_all_section_lengths(phase="phase2")

    assert isinstance(section_lengths, dict), "Should return dict of section lengths"
    assert len(section_lengths) == 15, f"Expected 15 Phase 2 agents, got {len(section_lengths)}"

    # Each agent should have line count
    for agent_name in PHASE_2_AGENTS:
        assert agent_name in section_lengths, f"Missing section length for {agent_name}"
        assert isinstance(section_lengths[agent_name], int), \
            f"Section length should be int for {agent_name}"


# ============================================================================
# Test 2: Validate No Agent Exceeds 30-Line Threshold - After Cleanup
# ============================================================================


def test_no_phase2_agent_exceeds_threshold_after_cleanup():
    """
    Test that no Phase 2 agent exceeds 30-line threshold after cleanup.

    EXPECTED TO FAIL: Cleanup not yet implemented.
    """
    from scripts.measure_output_format_sections import validate_section_lengths

    violations = validate_section_lengths(
        threshold=MAX_OUTPUT_FORMAT_LINES,
        phase="phase2",
        post_cleanup=True
    )

    assert isinstance(violations, list), "Should return list of violations"
    assert len(violations) == 0, \
        f"Phase 2 agents still exceed threshold after cleanup: {violations}"


def test_phase2_high_priority_agents_under_threshold():
    """
    Test that all high-priority Phase 2 agents are under threshold after cleanup.

    EXPECTED TO FAIL: Cleanup not yet implemented.
    """
    from scripts.measure_output_format_sections import count_output_format_lines

    for agent_name in PHASE_2_HIGH_PRIORITY:
        agent_file = AGENTS_DIR / f"{agent_name}.md"
        assert agent_file.exists(), f"Agent file not found: {agent_file}"

        line_count = count_output_format_lines(agent_file, post_cleanup=True)

        assert line_count <= MAX_OUTPUT_FORMAT_LINES, \
            f"{agent_name} exceeds threshold after cleanup: {line_count} lines (max {MAX_OUTPUT_FORMAT_LINES})"


def test_phase2_medium_priority_agents_under_threshold():
    """
    Test that all medium-priority Phase 2 agents are under threshold after cleanup.

    EXPECTED TO FAIL: Cleanup not yet implemented.
    """
    from scripts.measure_output_format_sections import count_output_format_lines

    for agent_name in PHASE_2_MEDIUM_PRIORITY:
        agent_file = AGENTS_DIR / f"{agent_name}.md"
        assert agent_file.exists(), f"Agent file not found: {agent_file}"

        line_count = count_output_format_lines(agent_file, post_cleanup=True)

        assert line_count <= MAX_OUTPUT_FORMAT_LINES, \
            f"{agent_name} exceeds threshold after cleanup: {line_count} lines (max {MAX_OUTPUT_FORMAT_LINES})"


def test_phase2_low_priority_agents_under_threshold():
    """
    Test that all low-priority Phase 2 agents are under threshold after cleanup.

    EXPECTED TO FAIL: Cleanup not yet implemented.
    """
    from scripts.measure_output_format_sections import count_output_format_lines

    for agent_name in PHASE_2_LOW_PRIORITY:
        agent_file = AGENTS_DIR / f"{agent_name}.md"
        assert agent_file.exists(), f"Agent file not found: {agent_file}"

        line_count = count_output_format_lines(agent_file, post_cleanup=True)

        assert line_count <= MAX_OUTPUT_FORMAT_LINES, \
            f"{agent_name} exceeds threshold after cleanup: {line_count} lines (max {MAX_OUTPUT_FORMAT_LINES})"


def test_all_20_agents_under_threshold_after_phase2():
    """
    Test that all 20 agents (Phase 1 + Phase 2) are under threshold after Phase 2 cleanup.

    EXPECTED TO FAIL: Phase 2 cleanup not yet implemented.
    """
    from scripts.measure_output_format_sections import validate_all_agents

    violations = validate_all_agents(threshold=MAX_OUTPUT_FORMAT_LINES, post_cleanup=True)

    assert isinstance(violations, list), "Should return list of violations"
    assert len(violations) == 0, \
        f"Agents still exceed threshold after Phase 2: {violations}"


# ============================================================================
# Test 3: Identify Verbose Agents Requiring Cleanup
# ============================================================================


def test_identify_verbose_subsections_in_planner():
    """
    Test identifying verbose subsections in planner agent.

    EXPECTED TO FAIL: Need subsection analysis.
    """
    from scripts.measure_output_format_sections import identify_verbose_subsections

    planner_file = AGENTS_DIR / "planner.md"
    verbose_subsections = identify_verbose_subsections(planner_file)

    assert isinstance(verbose_subsections, list), "Should return list of verbose subsections"
    assert len(verbose_subsections) > 0, "planner should have verbose subsections"

    # Planner likely has verbose JSON examples or templates
    subsection_names = [s["name"] for s in verbose_subsections]
    assert any("json" in name.lower() or "example" in name.lower() or "template" in name.lower()
               for name in subsection_names), \
        "planner should have verbose JSON/example/template subsections"


def test_identify_verbose_subsections_in_security_auditor():
    """
    Test identifying verbose subsections in security-auditor agent.

    EXPECTED TO FAIL: Need subsection analysis.
    """
    from scripts.measure_output_format_sections import identify_verbose_subsections

    security_file = AGENTS_DIR / "security-auditor.md"
    verbose_subsections = identify_verbose_subsections(security_file)

    assert isinstance(verbose_subsections, list), "Should return list of verbose subsections"

    # security-auditor has "What is NOT a Vulnerability" - should be preserved, not removed
    subsection_names = [s["name"] for s in verbose_subsections if s.get("preserve", False)]
    assert any("not" in name.lower() and "vulnerability" in name.lower()
               for name in subsection_names), \
        "security-auditor should preserve 'What is NOT a Vulnerability' guidance"


def test_generate_cleanup_recommendations():
    """
    Test generating cleanup recommendations for verbose agents.

    EXPECTED TO FAIL: Recommendation engine needs implementation.
    """
    from scripts.measure_output_format_sections import generate_cleanup_recommendations

    recommendations = generate_cleanup_recommendations(phase="phase2")

    assert isinstance(recommendations, dict), "Should return dict of recommendations"
    assert len(recommendations) > 0, "Should have recommendations for Phase 2 agents"

    # High-priority agents should have recommendations
    for agent_name in PHASE_2_HIGH_PRIORITY[:3]:  # Check first 3
        if agent_name in recommendations:
            rec = recommendations[agent_name]
            assert "current_lines" in rec, f"Missing current_lines for {agent_name}"
            assert "target_lines" in rec, f"Missing target_lines for {agent_name}"
            assert "actions" in rec, f"Missing actions for {agent_name}"


# ============================================================================
# Test 4: Track Phase 2 Cleanup Progress
# ============================================================================


def test_track_cleanup_progress_before_start():
    """
    Test cleanup progress tracking before Phase 2 starts.

    EXPECTED TO FAIL: Progress tracking needs implementation.
    """
    from scripts.measure_output_format_sections import track_cleanup_progress

    progress = track_cleanup_progress(phase="phase2")

    assert isinstance(progress, dict), "Progress should be dict"
    assert "agents_cleaned" in progress, "Missing 'agents_cleaned' key"
    assert "agents_remaining" in progress, "Missing 'agents_remaining' key"
    assert "completion_percentage" in progress, "Missing 'completion_percentage' key"

    # Before cleanup: 0 agents cleaned, 15 remaining
    assert progress["agents_cleaned"] == 0, \
        f"Expected 0 agents cleaned before start, got {progress['agents_cleaned']}"
    assert progress["agents_remaining"] == 15, \
        f"Expected 15 agents remaining, got {progress['agents_remaining']}"
    assert progress["completion_percentage"] == 0.0, \
        f"Expected 0% completion, got {progress['completion_percentage']}"


def test_track_cleanup_progress_after_high_priority():
    """
    Test cleanup progress tracking after high-priority agents.

    EXPECTED TO FAIL: Cleanup not yet implemented.
    """
    from scripts.measure_output_format_sections import track_cleanup_progress

    progress = track_cleanup_progress(phase="phase2", checkpoint="high_priority_complete")

    assert isinstance(progress, dict), "Progress should be dict"
    assert progress["agents_cleaned"] == 8, \
        f"Expected 8 high-priority agents cleaned, got {progress['agents_cleaned']}"
    assert progress["agents_remaining"] == 7, \
        f"Expected 7 agents remaining, got {progress['agents_remaining']}"


def test_track_cleanup_progress_after_completion():
    """
    Test cleanup progress tracking after Phase 2 completion.

    EXPECTED TO FAIL: Cleanup not yet implemented.
    """
    from scripts.measure_output_format_sections import track_cleanup_progress

    progress = track_cleanup_progress(phase="phase2", checkpoint="complete")

    assert isinstance(progress, dict), "Progress should be dict"
    assert progress["agents_cleaned"] == 15, \
        f"Expected 15 agents cleaned, got {progress['agents_cleaned']}"
    assert progress["agents_remaining"] == 0, \
        f"Expected 0 agents remaining, got {progress['agents_remaining']}"
    assert progress["completion_percentage"] == 100.0, \
        f"Expected 100% completion, got {progress['completion_percentage']}"


def test_cleanup_progress_includes_token_savings():
    """
    Test that cleanup progress includes token savings metrics.

    EXPECTED TO FAIL: Token metrics integration needed.
    """
    from scripts.measure_output_format_sections import track_cleanup_progress

    progress = track_cleanup_progress(phase="phase2", include_savings=True)

    assert "tokens_saved_so_far" in progress, "Missing token savings metric"
    assert "estimated_total_savings" in progress, "Missing estimated total savings"


# ============================================================================
# Test 5: Verify Agent-Specific Guidance is Preserved
# ============================================================================


def test_security_auditor_preserves_not_vulnerability_section():
    """
    Test that security-auditor preserves "What is NOT a Vulnerability" guidance.

    EXPECTED TO FAIL: Cleanup not yet implemented, need to verify preservation.
    """
    from scripts.measure_output_format_sections import extract_agent_specific_guidance

    security_file = AGENTS_DIR / "security-auditor.md"
    guidance = extract_agent_specific_guidance(security_file, section="Output Format")

    assert guidance is not None, "security-auditor guidance missing"
    assert "NOT a Vulnerability" in guidance, \
        "security-auditor missing 'What is NOT a Vulnerability' section"

    # Should have specific examples
    assert "Missing input validation" in guidance or "CWE-" in guidance, \
        "security-auditor missing specific vulnerability guidance"


def test_planner_preserves_planning_specific_format():
    """
    Test that planner preserves planning-specific output format guidance.

    EXPECTED TO FAIL: Cleanup not yet implemented.
    """
    from scripts.measure_output_format_sections import extract_agent_specific_guidance

    planner_file = AGENTS_DIR / "planner.md"
    guidance = extract_agent_specific_guidance(planner_file, section="Output Format")

    assert guidance is not None, "planner guidance missing"

    # Planner should have architecture-specific guidance
    planning_keywords = ["architecture", "design", "implementation", "phases"]
    assert any(keyword in guidance.lower() for keyword in planning_keywords), \
        "planner missing architecture/design guidance"


def test_reviewer_preserves_review_specific_format():
    """
    Test that reviewer preserves review-specific output format guidance.

    EXPECTED TO FAIL: Cleanup not yet implemented.
    """
    from scripts.measure_output_format_sections import extract_agent_specific_guidance

    reviewer_file = AGENTS_DIR / "reviewer.md"
    guidance = extract_agent_specific_guidance(reviewer_file, section="Output Format")

    assert guidance is not None, "reviewer guidance missing"

    # Reviewer should have code review guidance
    review_keywords = ["approve", "reject", "changes", "quality"]
    assert any(keyword in guidance.lower() for keyword in review_keywords), \
        "reviewer missing code review guidance"


def test_all_agents_reference_skill_after_cleanup():
    """
    Test that all Phase 2 agents reference agent-output-formats skill after cleanup.

    EXPECTED TO FAIL: Cleanup not yet implemented.
    """
    from scripts.measure_output_format_sections import check_skill_references

    skill_refs = check_skill_references(phase="phase2")

    assert isinstance(skill_refs, dict), "Skill references should be dict"

    # All 15 Phase 2 agents should reference the skill
    for agent_name in PHASE_2_AGENTS:
        assert agent_name in skill_refs, f"Missing skill reference check for {agent_name}"
        assert skill_refs[agent_name] is True, \
            f"{agent_name} missing agent-output-formats skill reference"


def test_preserved_guidance_is_concise():
    """
    Test that preserved agent-specific guidance is concise (not verbose).

    EXPECTED TO FAIL: Cleanup not yet implemented.
    """
    from scripts.measure_output_format_sections import extract_agent_specific_guidance

    for agent_name in PHASE_2_HIGH_PRIORITY:
        agent_file = AGENTS_DIR / f"{agent_name}.md"
        guidance = extract_agent_specific_guidance(agent_file, section="Output Format")

        if guidance:
            # Preserved guidance should be concise (max 200 words)
            word_count = len(guidance.split())
            assert word_count <= 200, \
                f"{agent_name} preserved guidance too verbose: {word_count} words (max 200)"


# ============================================================================
# Test 6: Section Extraction and Analysis
# ============================================================================


def test_extract_output_format_section():
    """
    Test extracting Output Format section from agent file.

    EXPECTED TO FAIL: Extraction function needs implementation.
    """
    from scripts.measure_output_format_sections import extract_output_format_section

    planner_file = AGENTS_DIR / "planner.md"
    section_text = extract_output_format_section(planner_file)

    assert section_text is not None, "Should extract Output Format section"
    assert "## Output Format" in section_text or "## Output" in section_text, \
        "Section should have Output Format heading"
    assert len(section_text) > 100, "Section should have substantial content"


def test_count_lines_excludes_empty_lines():
    """
    Test that line counting excludes empty lines.

    EXPECTED TO FAIL: Line counting logic needs refinement.
    """
    from scripts.measure_output_format_sections import count_significant_lines

    sample_text = """
## Output Format

Line 1

Line 2

Line 3
"""

    line_count = count_significant_lines(sample_text)

    # Should count 4 lines (heading + 3 content lines), exclude 2 empty lines
    assert line_count == 4, f"Expected 4 significant lines, got {line_count}"


def test_count_lines_excludes_comments():
    """
    Test that line counting excludes markdown comments.

    EXPECTED TO FAIL: Comment handling needs implementation.
    """
    from scripts.measure_output_format_sections import count_significant_lines

    sample_text = """
## Output Format

Line 1
<!-- This is a comment -->
Line 2
"""

    line_count = count_significant_lines(sample_text)

    # Should count 3 lines (heading + 2 content lines), exclude comment
    assert line_count == 3, f"Expected 3 significant lines, got {line_count}"


def test_extract_subsections():
    """
    Test extracting subsections from Output Format section.

    EXPECTED TO FAIL: Subsection extraction needs implementation.
    """
    from scripts.measure_output_format_sections import extract_subsections

    sample_text = """
## Output Format

### Subsection 1
Content 1

### Subsection 2
Content 2
"""

    subsections = extract_subsections(sample_text)

    assert isinstance(subsections, list), "Should return list of subsections"
    assert len(subsections) == 2, f"Expected 2 subsections, got {len(subsections)}"

    assert subsections[0]["name"] == "Subsection 1"
    assert subsections[1]["name"] == "Subsection 2"


# ============================================================================
# Test 7: Regression Tests - Phase 1 Stability
# ============================================================================


def test_phase1_agents_remain_under_threshold():
    """
    Test that Phase 1 agents remain under threshold during Phase 2 work.

    EXPECTED TO FAIL: Need to verify Phase 1 stability.
    """
    from scripts.measure_output_format_sections import count_output_format_lines

    for agent_name in PHASE_1_AGENTS:
        agent_file = AGENTS_DIR / f"{agent_name}.md"

        # Skip test-master (no Output Format section)
        if agent_name == "test-master":
            continue

        assert agent_file.exists(), f"Agent file not found: {agent_file}"

        line_count = count_output_format_lines(agent_file)

        assert line_count <= MAX_OUTPUT_FORMAT_LINES, \
            f"Phase 1 agent {agent_name} regressed: {line_count} lines (max {MAX_OUTPUT_FORMAT_LINES})"


def test_phase1_skill_references_remain_intact():
    """
    Test that Phase 1 skill references remain intact during Phase 2 work.

    EXPECTED TO FAIL: Need to verify Phase 1 references not affected.
    """
    from scripts.measure_output_format_sections import check_skill_references

    skill_refs = check_skill_references(phase="phase1")

    # Phase 1 agents (except test-master) should still reference skill
    for agent_name in PHASE_1_AGENTS:
        if agent_name == "test-master":
            continue  # test-master has no Output Format section

        assert agent_name in skill_refs, f"Missing skill reference check for {agent_name}"
        assert skill_refs[agent_name] is True, \
            f"Phase 1 agent {agent_name} lost skill reference during Phase 2"


# ============================================================================
# Test 8: Validation and Error Handling
# ============================================================================


def test_handles_missing_output_format_section():
    """
    Test handling of agents without Output Format section.

    EXPECTED TO FAIL: Special case handling needed.
    """
    from scripts.measure_output_format_sections import count_output_format_lines

    # test-master has no Output Format section
    test_master_file = AGENTS_DIR / "test-master.md"

    line_count = count_output_format_lines(test_master_file)

    # Should return 0 for missing section, not error
    assert line_count == 0, f"Expected 0 lines for missing section, got {line_count}"


def test_handles_empty_output_format_section():
    """
    Test handling of empty Output Format section.

    EXPECTED TO FAIL: Edge case handling needed.
    """
    from scripts.measure_output_format_sections import count_output_format_lines
    from pathlib import Path

    # Create temporary file with empty Output Format
    test_file = Path("/tmp/test_empty_output_format.md")
    test_file.write_text("""
# Test Agent

## Output Format

""")

    try:
        line_count = count_output_format_lines(test_file)
        assert line_count == 1, f"Expected 1 line (heading only), got {line_count}"
    finally:
        test_file.unlink(missing_ok=True)


def test_validates_phase_parameter():
    """
    Test validation of phase parameter.

    EXPECTED TO FAIL: Parameter validation needed.
    """
    from scripts.measure_output_format_sections import identify_verbose_agents

    with pytest.raises(ValueError) as exc_info:
        identify_verbose_agents(threshold=30, phase="invalid_phase")

    assert "Invalid phase" in str(exc_info.value)


def test_validates_threshold_parameter():
    """
    Test validation of threshold parameter.

    EXPECTED TO FAIL: Parameter validation needed.
    """
    from scripts.measure_output_format_sections import validate_section_lengths

    with pytest.raises(ValueError) as exc_info:
        validate_section_lengths(threshold=-1, phase="phase2")

    assert "Threshold must be positive" in str(exc_info.value)
