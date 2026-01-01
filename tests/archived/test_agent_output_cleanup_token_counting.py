"""
TDD RED Phase Tests for Issue #72: Token Counting Validation

Tests token counting functionality for measuring baseline and post-cleanup savings.
All tests should FAIL initially (no implementation exists yet).

Test Coverage:
1. Token counting script exists and is executable
2. Baseline token count measurement
3. Post-cleanup token count measurement
4. Token savings calculation
5. Per-agent token analysis
6. Section-specific token counting (Output Format sections)
"""

import pytest
import json
from pathlib import Path
from typing import Dict, List, Optional


# ============================================================================
# Test 1: Token Counting Script Exists
# ============================================================================


def test_token_counting_script_exists():
    """
    Test that token counting measurement script exists.

    EXPECTED TO FAIL: Script doesn't exist yet (TDD red phase).
    """
    script_path = Path("${PROJECT_ROOT}/scripts/measure_agent_tokens.py")
    assert script_path.exists(), f"Token counting script not found at {script_path}"
    assert script_path.is_file(), f"Path exists but is not a file: {script_path}"


def test_token_counting_script_is_executable():
    """
    Test that token counting script has proper Python shebang.

    EXPECTED TO FAIL: Script doesn't exist yet.
    """
    script_path = Path("${PROJECT_ROOT}/scripts/measure_agent_tokens.py")
    assert script_path.exists(), "Script doesn't exist"

    content = script_path.read_text()
    assert content.startswith("#!/usr/bin/env python3") or content.startswith("#!"), \
        "Script missing Python shebang"


def test_token_counting_script_has_main_function():
    """
    Test that token counting script has main() entry point.

    EXPECTED TO FAIL: Script doesn't exist yet.
    """
    script_path = Path("${PROJECT_ROOT}/scripts/measure_agent_tokens.py")
    assert script_path.exists(), "Script doesn't exist"

    content = script_path.read_text()
    assert "def main(" in content, "Script missing main() function"
    assert 'if __name__ == "__main__":' in content, "Script missing main entry point"


# ============================================================================
# Test 2: Baseline Token Count Measurement
# ============================================================================


def test_measure_baseline_tokens_for_all_agents():
    """
    Test that script can measure baseline tokens for all 20 agents.

    EXPECTED TO FAIL: Function doesn't exist yet.
    """
    from scripts.measure_agent_tokens import measure_baseline_tokens

    baseline = measure_baseline_tokens()

    # Should return dict with agent names as keys
    assert isinstance(baseline, dict), "Baseline should be a dictionary"
    assert len(baseline) == 20, f"Expected 20 agents, got {len(baseline)}"

    # Each agent should have token count
    for agent_name, token_count in baseline.items():
        assert isinstance(agent_name, str), f"Agent name should be string: {agent_name}"
        assert isinstance(token_count, int), f"Token count should be int: {token_count}"
        assert token_count > 0, f"Token count should be positive: {agent_name} = {token_count}"


def test_baseline_tokens_includes_all_agent_files():
    """
    Test that baseline measurement reads all agent .md files.

    EXPECTED TO FAIL: Function doesn't exist yet.
    """
    from scripts.measure_agent_tokens import measure_baseline_tokens

    expected_agents = [
        "advisor", "alignment-analyzer", "alignment-validator",
        "brownfield-analyzer", "commit-message-generator", "doc-master",
        "implementer", "issue-creator", "planner", "pr-description-generator",
        "project-bootstrapper", "project-progress-tracker", "project-status-analyzer",
        "quality-validator", "researcher", "reviewer", "security-auditor",
        "setup-wizard", "sync-validator", "test-master"
    ]

    baseline = measure_baseline_tokens()

    for agent in expected_agents:
        assert agent in baseline, f"Missing agent in baseline: {agent}"


def test_baseline_token_measurement_is_consistent():
    """
    Test that baseline measurement returns same results on repeated calls.

    EXPECTED TO FAIL: Function doesn't exist yet.
    """
    from scripts.measure_agent_tokens import measure_baseline_tokens

    baseline1 = measure_baseline_tokens()
    baseline2 = measure_baseline_tokens()

    assert baseline1 == baseline2, "Baseline measurement should be deterministic"


def test_baseline_saves_to_json_file():
    """
    Test that baseline measurement can be saved to JSON.

    EXPECTED TO FAIL: Function doesn't exist yet.
    """
    from scripts.measure_agent_tokens import measure_baseline_tokens, save_baseline
    import tempfile

    baseline = measure_baseline_tokens()

    with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
        output_path = Path(f.name)

    try:
        save_baseline(baseline, output_path)

        assert output_path.exists(), "Baseline JSON file not created"

        # Verify JSON is valid
        with open(output_path) as f:
            loaded = json.load(f)

        assert loaded == baseline, "Loaded baseline doesn't match original"
    finally:
        if output_path.exists():
            output_path.unlink()


# ============================================================================
# Test 3: Post-Cleanup Token Count Measurement
# ============================================================================


def test_measure_post_cleanup_tokens():
    """
    Test that script can measure tokens after cleanup.

    EXPECTED TO FAIL: Function doesn't exist yet.
    """
    from scripts.measure_agent_tokens import measure_post_cleanup_tokens

    post_cleanup = measure_post_cleanup_tokens()

    assert isinstance(post_cleanup, dict), "Post-cleanup should be a dictionary"
    assert len(post_cleanup) == 20, f"Expected 20 agents, got {len(post_cleanup)}"

    for agent_name, token_count in post_cleanup.items():
        assert isinstance(token_count, int), f"Token count should be int: {token_count}"
        assert token_count > 0, f"Token count should be positive: {agent_name} = {token_count}"


def test_post_cleanup_tokens_are_less_than_baseline():
    """
    Test that post-cleanup tokens are reduced compared to baseline.

    EXPECTED TO FAIL: Functions don't exist yet.
    """
    from scripts.measure_agent_tokens import measure_baseline_tokens, measure_post_cleanup_tokens

    baseline = measure_baseline_tokens()
    post_cleanup = measure_post_cleanup_tokens()

    # Calculate total tokens
    baseline_total = sum(baseline.values())
    post_cleanup_total = sum(post_cleanup.values())

    assert post_cleanup_total < baseline_total, \
        f"Post-cleanup tokens ({post_cleanup_total}) should be less than baseline ({baseline_total})"


def test_post_cleanup_identifies_reduced_agents():
    """
    Test that post-cleanup identifies which agents had token reduction.

    EXPECTED TO FAIL: Function doesn't exist yet.
    """
    from scripts.measure_agent_tokens import measure_baseline_tokens, measure_post_cleanup_tokens, \
        identify_reduced_agents

    baseline = measure_baseline_tokens()
    post_cleanup = measure_post_cleanup_tokens()

    reduced = identify_reduced_agents(baseline, post_cleanup)

    assert isinstance(reduced, list), "Reduced agents should be a list"
    assert len(reduced) > 0, "Should identify at least some agents with reduction"

    # Verify each reduced agent actually has fewer tokens
    for agent_name in reduced:
        assert agent_name in baseline, f"Agent {agent_name} not in baseline"
        assert agent_name in post_cleanup, f"Agent {agent_name} not in post-cleanup"
        assert post_cleanup[agent_name] < baseline[agent_name], \
            f"Agent {agent_name} marked as reduced but tokens didn't decrease"


# ============================================================================
# Test 4: Token Savings Calculation
# ============================================================================


def test_calculate_total_token_savings():
    """
    Test that script calculates total token savings.

    EXPECTED TO FAIL: Function doesn't exist yet.
    """
    from scripts.measure_agent_tokens import calculate_token_savings

    baseline = {"agent1": 1000, "agent2": 500, "agent3": 800}
    post_cleanup = {"agent1": 800, "agent2": 450, "agent3": 800}

    savings = calculate_token_savings(baseline, post_cleanup)

    assert isinstance(savings, dict), "Savings should be a dictionary"
    assert "total_saved" in savings, "Missing total_saved"
    assert savings["total_saved"] == 250, f"Expected 250 tokens saved, got {savings['total_saved']}"


def test_calculate_per_agent_token_savings():
    """
    Test that script calculates per-agent token savings.

    EXPECTED TO FAIL: Function doesn't exist yet.
    """
    from scripts.measure_agent_tokens import calculate_token_savings

    baseline = {"agent1": 1000, "agent2": 500, "agent3": 800}
    post_cleanup = {"agent1": 800, "agent2": 450, "agent3": 800}

    savings = calculate_token_savings(baseline, post_cleanup)

    assert "per_agent" in savings, "Missing per_agent savings"
    assert savings["per_agent"]["agent1"] == 200, "agent1 should save 200 tokens"
    assert savings["per_agent"]["agent2"] == 50, "agent2 should save 50 tokens"
    assert savings["per_agent"]["agent3"] == 0, "agent3 should save 0 tokens (unchanged)"


def test_calculate_percentage_token_reduction():
    """
    Test that script calculates percentage reduction.

    EXPECTED TO FAIL: Function doesn't exist yet.
    """
    from scripts.measure_agent_tokens import calculate_token_savings

    baseline = {"agent1": 1000, "agent2": 1000}  # 2000 total
    post_cleanup = {"agent1": 800, "agent2": 800}  # 1600 total, 20% reduction

    savings = calculate_token_savings(baseline, post_cleanup)

    assert "percentage_reduction" in savings, "Missing percentage_reduction"
    assert abs(savings["percentage_reduction"] - 20.0) < 0.01, \
        f"Expected 20% reduction, got {savings['percentage_reduction']}"


def test_savings_calculation_handles_no_change():
    """
    Test that savings calculation handles agents with no change.

    EXPECTED TO FAIL: Function doesn't exist yet.
    """
    from scripts.measure_agent_tokens import calculate_token_savings

    baseline = {"agent1": 1000}
    post_cleanup = {"agent1": 1000}

    savings = calculate_token_savings(baseline, post_cleanup)

    assert savings["total_saved"] == 0, "No savings expected"
    assert savings["percentage_reduction"] == 0.0, "No percentage reduction expected"


def test_savings_report_includes_agent_rankings():
    """
    Test that savings report ranks agents by token reduction.

    EXPECTED TO FAIL: Function doesn't exist yet.
    """
    from scripts.measure_agent_tokens import calculate_token_savings

    baseline = {"agent1": 1000, "agent2": 500, "agent3": 800}
    post_cleanup = {"agent1": 700, "agent2": 450, "agent3": 600}

    savings = calculate_token_savings(baseline, post_cleanup)

    assert "ranked_by_savings" in savings, "Missing ranked_by_savings"
    ranked = savings["ranked_by_savings"]

    # Should be sorted by savings (agent1: 300, agent3: 200, agent2: 50)
    assert ranked[0]["agent"] == "agent1", "agent1 should rank first (300 saved)"
    assert ranked[0]["saved"] == 300
    assert ranked[1]["agent"] == "agent3", "agent3 should rank second (200 saved)"
    assert ranked[2]["agent"] == "agent2", "agent2 should rank third (50 saved)"


# ============================================================================
# Test 5: Per-Agent Token Analysis
# ============================================================================


def test_analyze_individual_agent_tokens():
    """
    Test that script can analyze individual agent token usage.

    EXPECTED TO FAIL: Function doesn't exist yet.
    """
    from scripts.measure_agent_tokens import analyze_agent_tokens

    agent_name = "test-master"
    analysis = analyze_agent_tokens(agent_name)

    assert isinstance(analysis, dict), "Analysis should be a dictionary"
    assert "agent_name" in analysis
    assert "total_tokens" in analysis
    assert "sections" in analysis
    assert isinstance(analysis["sections"], dict)


def test_agent_analysis_breaks_down_by_section():
    """
    Test that agent analysis identifies major sections.

    EXPECTED TO FAIL: Function doesn't exist yet.
    """
    from scripts.measure_agent_tokens import analyze_agent_tokens

    analysis = analyze_agent_tokens("test-master")
    sections = analysis["sections"]

    # Should identify key sections
    expected_sections = ["Mission", "Workflow", "Test Quality", "Relevant Skills", "Summary"]
    for section in expected_sections:
        assert section in sections, f"Missing section: {section}"
        assert isinstance(sections[section], int), f"Section {section} should have token count"


def test_agent_analysis_identifies_output_format_section():
    """
    Test that agent analysis identifies Output Format section if present.

    EXPECTED TO FAIL: Function doesn't exist yet.
    """
    from scripts.measure_agent_tokens import analyze_agent_tokens

    # Test on agent with Output Format section
    analysis = analyze_agent_tokens("project-progress-tracker")

    assert "Output Format" in analysis["sections"], "Should identify Output Format section"
    assert analysis["sections"]["Output Format"] > 0, "Output Format section should have tokens"


def test_agent_analysis_calculates_section_percentages():
    """
    Test that agent analysis shows percentage of tokens per section.

    EXPECTED TO FAIL: Function doesn't exist yet.
    """
    from scripts.measure_agent_tokens import analyze_agent_tokens

    analysis = analyze_agent_tokens("test-master")

    assert "section_percentages" in analysis, "Missing section_percentages"
    percentages = analysis["section_percentages"]

    # Percentages should sum to ~100%
    total_pct = sum(percentages.values())
    assert abs(total_pct - 100.0) < 0.1, f"Section percentages should sum to 100%, got {total_pct}"


# ============================================================================
# Test 6: Section-Specific Token Counting
# ============================================================================


def test_count_tokens_in_output_format_section():
    """
    Test that script can count tokens specifically in Output Format section.

    EXPECTED TO FAIL: Function doesn't exist yet.
    """
    from scripts.measure_agent_tokens import count_output_format_tokens

    agent_name = "project-progress-tracker"
    tokens = count_output_format_tokens(agent_name)

    assert isinstance(tokens, int), "Output Format token count should be integer"
    assert tokens > 0, "project-progress-tracker should have Output Format tokens"


def test_output_format_token_count_for_agent_without_section():
    """
    Test that Output Format token count returns 0 for agents without the section.

    EXPECTED TO FAIL: Function doesn't exist yet.
    """
    from scripts.measure_agent_tokens import count_output_format_tokens

    # test-master doesn't have explicit Output Format section
    tokens = count_output_format_tokens("test-master")

    assert tokens == 0, "Agent without Output Format section should return 0"


def test_identify_agents_with_verbose_output_formats():
    """
    Test that script identifies agents with verbose (>30 lines) Output Format sections.

    EXPECTED TO FAIL: Function doesn't exist yet.
    """
    from scripts.measure_agent_tokens import identify_verbose_output_formats

    verbose_agents = identify_verbose_output_formats(line_threshold=30)

    assert isinstance(verbose_agents, list), "Should return list of verbose agents"

    # project-progress-tracker has very verbose Output Format section
    assert "project-progress-tracker" in verbose_agents, \
        "project-progress-tracker should be identified as verbose"


def test_measure_output_format_line_count():
    """
    Test that script can measure line count of Output Format section.

    EXPECTED TO FAIL: Function doesn't exist yet.
    """
    from scripts.measure_agent_tokens import measure_output_format_lines

    agent_name = "project-progress-tracker"
    line_count = measure_output_format_lines(agent_name)

    assert isinstance(line_count, int), "Line count should be integer"
    assert line_count > 30, f"project-progress-tracker Output Format should have >30 lines, got {line_count}"


def test_compare_output_format_before_after():
    """
    Test that script can compare Output Format section before/after cleanup.

    EXPECTED TO FAIL: Function doesn't exist yet.
    """
    from scripts.measure_agent_tokens import compare_output_format_sections

    agent_name = "project-progress-tracker"
    comparison = compare_output_format_sections(agent_name)

    assert isinstance(comparison, dict), "Comparison should be dictionary"
    assert "before_tokens" in comparison
    assert "after_tokens" in comparison
    assert "tokens_saved" in comparison
    assert "before_lines" in comparison
    assert "after_lines" in comparison


# ============================================================================
# Test 7: CLI Interface
# ============================================================================


def test_cli_supports_baseline_measurement():
    """
    Test that CLI supports --baseline flag.

    EXPECTED TO FAIL: CLI doesn't exist yet.
    """
    import subprocess

    result = subprocess.run(
        ["python", "scripts/measure_agent_tokens.py", "--baseline"],
        cwd="${PROJECT_ROOT}",
        capture_output=True,
        text=True
    )

    assert result.returncode == 0, f"CLI failed: {result.stderr}"
    assert "Baseline tokens measured" in result.stdout


def test_cli_supports_post_cleanup_measurement():
    """
    Test that CLI supports --post-cleanup flag.

    EXPECTED TO FAIL: CLI doesn't exist yet.
    """
    import subprocess

    result = subprocess.run(
        ["python", "scripts/measure_agent_tokens.py", "--post-cleanup"],
        cwd="${PROJECT_ROOT}",
        capture_output=True,
        text=True
    )

    assert result.returncode == 0, f"CLI failed: {result.stderr}"
    assert "Post-cleanup tokens measured" in result.stdout


def test_cli_supports_savings_report():
    """
    Test that CLI supports --report flag for savings summary.

    EXPECTED TO FAIL: CLI doesn't exist yet.
    """
    import subprocess

    result = subprocess.run(
        ["python", "scripts/measure_agent_tokens.py", "--report"],
        cwd="${PROJECT_ROOT}",
        capture_output=True,
        text=True
    )

    assert result.returncode == 0, f"CLI failed: {result.stderr}"
    assert "Token Savings Report" in result.stdout
    assert "Total tokens saved" in result.stdout


def test_cli_supports_json_output():
    """
    Test that CLI supports --json flag for machine-readable output.

    EXPECTED TO FAIL: CLI doesn't exist yet.
    """
    import subprocess

    result = subprocess.run(
        ["python", "scripts/measure_agent_tokens.py", "--report", "--json"],
        cwd="${PROJECT_ROOT}",
        capture_output=True,
        text=True
    )

    assert result.returncode == 0, f"CLI failed: {result.stderr}"

    # Output should be valid JSON
    data = json.loads(result.stdout)
    assert "total_saved" in data
    assert "percentage_reduction" in data


# ============================================================================
# Test 8: Error Handling
# ============================================================================


def test_token_counting_handles_missing_agent_file():
    """
    Test that token counting gracefully handles missing agent files.

    EXPECTED TO FAIL: Function doesn't exist yet.
    """
    from scripts.measure_agent_tokens import analyze_agent_tokens

    with pytest.raises(FileNotFoundError) as exc_info:
        analyze_agent_tokens("nonexistent-agent")

    assert "not found" in str(exc_info.value).lower()


def test_token_counting_handles_malformed_agent_file():
    """
    Test that token counting handles malformed markdown.

    EXPECTED TO FAIL: Function doesn't exist yet.
    """
    from scripts.measure_agent_tokens import analyze_agent_tokens
    import tempfile
    from pathlib import Path

    # Create malformed agent file
    with tempfile.NamedTemporaryFile(mode='w', suffix='.md', delete=False) as f:
        f.write("This is not valid agent markdown\n")
        f.write("Missing frontmatter and structure\n")
        temp_path = Path(f.name)

    try:
        # Should handle gracefully, not crash
        with pytest.raises(ValueError) as exc_info:
            # Pass the temp path to function
            from scripts.measure_agent_tokens import analyze_agent_file
            analyze_agent_file(temp_path)

        assert "malformed" in str(exc_info.value).lower() or \
               "invalid" in str(exc_info.value).lower()
    finally:
        temp_path.unlink()


def test_savings_calculation_handles_mismatched_agents():
    """
    Test that savings calculation handles baseline/post-cleanup with different agents.

    EXPECTED TO FAIL: Function doesn't exist yet.
    """
    from scripts.measure_agent_tokens import calculate_token_savings

    baseline = {"agent1": 1000, "agent2": 500}
    post_cleanup = {"agent1": 800, "agent3": 300}  # agent2 missing, agent3 added

    with pytest.raises(ValueError) as exc_info:
        calculate_token_savings(baseline, post_cleanup)

    assert "mismatch" in str(exc_info.value).lower()
