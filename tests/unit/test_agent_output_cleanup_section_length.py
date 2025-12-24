"""
TDD RED Phase Tests for Issue #72: Output Format Section Length Validation

Tests that no agent has >30 lines in Output Format section after cleanup.
All tests should FAIL initially (no implementation exists yet).

Test Coverage:
1. Measure Output Format section line counts
2. Validate no agent exceeds 30-line threshold
3. Identify verbose agents requiring cleanup
4. Track Phase 2 cleanup progress
5. Verify agent-specific guidance is preserved
"""

import pytest
from pathlib import Path
from typing import Dict, List, Optional
import re


# ============================================================================
# Helper Functions
# ============================================================================


def count_output_format_lines(agent_file: Path) -> int:
    """
    Count lines in Output Format section.

    EXPECTED TO FAIL: Function doesn't exist yet.
    """
    raise NotImplementedError("count_output_format_lines not implemented yet")


def extract_output_format_section(agent_file: Path) -> Optional[str]:
    """
    Extract Output Format section text from agent file.

    EXPECTED TO FAIL: Function doesn't exist yet.
    """
    raise NotImplementedError("extract_output_format_section not implemented yet")


def identify_verbose_sections(agent_file: Path) -> List[str]:
    """
    Identify verbose subsections within Output Format.

    EXPECTED TO FAIL: Function doesn't exist yet.
    """
    raise NotImplementedError("identify_verbose_sections not implemented yet")


# ============================================================================
# Test 1: Measure Output Format Section Line Counts
# ============================================================================


def test_count_output_format_lines_in_agent():
    """
    Test that we can accurately count lines in Output Format section.

    EXPECTED TO FAIL: Function doesn't exist yet.
    """
    from scripts.measure_output_format_sections import count_output_format_lines

    agent_file = Path(
        "/Users/akaszubski/Documents/GitHub/autonomous-dev/plugins/autonomous-dev/agents/"
        "project-progress-tracker.md"
    )

    line_count = count_output_format_lines(agent_file)

    assert isinstance(line_count, int), "Line count should be integer"
    assert line_count > 30, \
        f"project-progress-tracker should have >30 lines in Output Format, got {line_count}"


def test_output_format_section_extraction():
    """
    Test that we can extract Output Format section text.

    EXPECTED TO FAIL: Function doesn't exist yet.
    """
    from scripts.measure_output_format_sections import extract_output_format_section

    agent_file = Path(
        "/Users/akaszubski/Documents/GitHub/autonomous-dev/plugins/autonomous-dev/agents/"
        "project-progress-tracker.md"
    )

    section_text = extract_output_format_section(agent_file)

    assert section_text is not None, "Should extract Output Format section"
    assert "## Output Format" in section_text or "## Output" in section_text
    assert len(section_text) > 100, "Section should have substantial content"


def test_count_lines_excludes_empty_lines():
    """
    Test that line counting excludes empty lines.

    EXPECTED TO FAIL: Function doesn't exist yet.
    """
    from scripts.measure_output_format_sections import count_output_format_lines

    # Create test content with empty lines
    import tempfile

    test_content = """---
name: test-agent
---

## Output Format

Line 1

Line 2

Line 3

## Next Section
"""

    with tempfile.NamedTemporaryFile(mode='w', suffix='.md', delete=False) as f:
        f.write(test_content)
        temp_path = Path(f.name)

    try:
        line_count = count_output_format_lines(temp_path)
        # Should count only 3 non-empty lines
        assert line_count == 3, f"Expected 3 lines (excluding empty), got {line_count}"
    finally:
        temp_path.unlink()


def test_count_lines_excludes_code_blocks():
    """
    Test that line counting handles code blocks properly.

    EXPECTED TO FAIL: Function doesn't exist yet.
    """
    from scripts.measure_output_format_sections import count_output_format_lines

    test_content = """---
name: test-agent
---

## Output Format

Here is an example:

```json
{
  "key": "value",
  "another": "line"
}
```

More content here.

## Next Section
"""

    import tempfile
    with tempfile.NamedTemporaryFile(mode='w', suffix='.md', delete=False) as f:
        f.write(test_content)
        temp_path = Path(f.name)

    try:
        line_count = count_output_format_lines(temp_path)
        # Should count text lines, but code blocks count as single unit
        assert line_count > 0, "Should count lines"
    finally:
        temp_path.unlink()


# ============================================================================
# Test 2: Validate No Agent Exceeds 30-Line Threshold
# ============================================================================


def test_no_agent_exceeds_30_line_threshold():
    """
    Test that no agent has >30 lines in Output Format section after cleanup.

    EXPECTED TO FAIL: Some agents still have verbose Output Format sections.
    """
    from scripts.measure_output_format_sections import count_output_format_lines

    agents_dir = Path("/Users/akaszubski/Documents/GitHub/autonomous-dev/plugins/autonomous-dev/agents")
    agent_files = list(agents_dir.glob("*.md"))
    agent_files = [f for f in agent_files if "archived" not in str(f)]

    verbose_agents = []
    for agent_file in agent_files:
        line_count = count_output_format_lines(agent_file)

        if line_count > 30:
            verbose_agents.append((agent_file.stem, line_count))

    assert len(verbose_agents) == 0, \
        f"Agents exceeding 30-line threshold: {verbose_agents}"


def test_agents_with_output_format_section_are_within_limits():
    """
    Test that agents with explicit Output Format sections are concise.

    EXPECTED TO FAIL: Some agents need cleanup.
    """
    from scripts.measure_output_format_sections import extract_output_format_section, \
        count_output_format_lines

    agents_dir = Path("/Users/akaszubski/Documents/GitHub/autonomous-dev/plugins/autonomous-dev/agents")
    agent_files = list(agents_dir.glob("*.md"))
    agent_files = [f for f in agent_files if "archived" not in str(f)]

    agents_with_section = []
    for agent_file in agent_files:
        section = extract_output_format_section(agent_file)
        if section:
            line_count = count_output_format_lines(agent_file)
            agents_with_section.append((agent_file.stem, line_count))

    # All agents with Output Format section should be ≤30 lines
    over_limit = [(name, count) for name, count in agents_with_section if count > 30]

    assert len(over_limit) == 0, \
        f"Agents with Output Format >30 lines: {over_limit}"


def test_30_line_threshold_allows_agent_specific_guidance():
    """
    Test that 30-line limit is sufficient for agent-specific guidance.

    EXPECTED TO FAIL: May need to adjust threshold.
    """
    from scripts.measure_output_format_sections import count_output_format_lines

    # Test agents with unique output requirements
    special_agents = [
        "project-progress-tracker",  # Dual-mode output (YAML vs JSON)
        "quality-validator",  # Scoring and verdict format
        "commit-message-generator",  # Conventional commits format
    ]

    agents_dir = Path("/Users/akaszubski/Documents/GitHub/autonomous-dev/plugins/autonomous-dev/agents")

    for agent_name in special_agents:
        agent_file = agents_dir / f"{agent_name}.md"
        line_count = count_output_format_lines(agent_file)

        # Should be under 30 even with agent-specific guidance
        assert line_count <= 30, \
            f"{agent_name} Output Format should be ≤30 lines, got {line_count}"


# ============================================================================
# Test 3: Identify Verbose Agents Requiring Cleanup
# ============================================================================


def test_identify_verbose_agents_for_phase2_cleanup():
    """
    Test that we can identify agents needing Phase 2 cleanup.

    EXPECTED TO FAIL: Function doesn't exist yet.
    """
    from scripts.identify_verbose_agents import identify_cleanup_candidates

    candidates = identify_cleanup_candidates(line_threshold=30)

    assert isinstance(candidates, list), "Candidates should be a list"
    assert len(candidates) > 0, "Should identify some verbose agents"

    # Each candidate should have agent name and current line count
    for candidate in candidates:
        assert "agent_name" in candidate
        assert "line_count" in candidate
        assert candidate["line_count"] > 30


def test_prioritize_verbose_agents_by_line_count():
    """
    Test that verbose agents are prioritized by line count (highest first).

    EXPECTED TO FAIL: Function doesn't exist yet.
    """
    from scripts.identify_verbose_agents import identify_cleanup_candidates

    candidates = identify_cleanup_candidates(line_threshold=30)

    if len(candidates) > 1:
        # Should be sorted by line count descending
        for i in range(len(candidates) - 1):
            assert candidates[i]["line_count"] >= candidates[i + 1]["line_count"], \
                "Candidates should be sorted by line count (highest first)"


def test_verbose_agent_report_includes_section_breakdown():
    """
    Test that verbose agent report shows which subsections are lengthy.

    EXPECTED TO FAIL: Function doesn't exist yet.
    """
    from scripts.identify_verbose_agents import identify_cleanup_candidates

    candidates = identify_cleanup_candidates(line_threshold=30)

    for candidate in candidates:
        assert "verbose_subsections" in candidate, \
            f"Missing verbose_subsections for {candidate['agent_name']}"

        # Should identify specific subsections
        subsections = candidate["verbose_subsections"]
        assert isinstance(subsections, list)


def test_verbose_agent_report_suggests_cleanup_approach():
    """
    Test that report suggests how to clean up each verbose agent.

    EXPECTED TO FAIL: Function doesn't exist yet.
    """
    from scripts.identify_verbose_agents import identify_cleanup_candidates

    candidates = identify_cleanup_candidates(line_threshold=30)

    for candidate in candidates:
        assert "cleanup_suggestion" in candidate, \
            f"Missing cleanup_suggestion for {candidate['agent_name']}"

        suggestion = candidate["cleanup_suggestion"]
        assert isinstance(suggestion, str)
        assert len(suggestion) > 0


# ============================================================================
# Test 4: Track Phase 2 Cleanup Progress
# ============================================================================


def test_track_cleanup_progress_before_and_after():
    """
    Test that we can track cleanup progress over time.

    EXPECTED TO FAIL: Function doesn't exist yet.
    """
    from scripts.track_cleanup_progress import measure_progress

    progress = measure_progress()

    assert "before" in progress
    assert "after" in progress
    assert "agents_cleaned" in progress
    assert "total_lines_removed" in progress


def test_cleanup_progress_shows_per_agent_improvement():
    """
    Test that progress tracking shows improvement per agent.

    EXPECTED TO FAIL: Function doesn't exist yet.
    """
    from scripts.track_cleanup_progress import measure_progress

    progress = measure_progress()

    assert "per_agent_improvements" in progress
    improvements = progress["per_agent_improvements"]

    assert isinstance(improvements, dict)

    # Each improved agent should show before/after line counts
    for agent_name, improvement in improvements.items():
        assert "before_lines" in improvement
        assert "after_lines" in improvement
        assert "lines_removed" in improvement
        assert improvement["before_lines"] > improvement["after_lines"]


def test_cleanup_progress_calculates_percentage_reduction():
    """
    Test that progress tracking calculates percentage reduction.

    EXPECTED TO FAIL: Function doesn't exist yet.
    """
    from scripts.track_cleanup_progress import measure_progress

    progress = measure_progress()

    assert "percentage_reduction" in progress

    # Should show overall reduction in Output Format section verbosity
    reduction = progress["percentage_reduction"]
    assert isinstance(reduction, float)
    assert reduction >= 0.0 and reduction <= 100.0


# ============================================================================
# Test 5: Verify Agent-Specific Guidance is Preserved
# ============================================================================


def test_agent_specific_guidance_preserved_after_cleanup():
    """
    Test that unique agent guidance is preserved after cleanup.

    EXPECTED TO FAIL: Cleanup may accidentally remove important guidance.
    """
    # Check specific agents with unique output requirements

    # 1. project-progress-tracker: Should keep dual-mode guidance
    tracker_file = Path(
        "/Users/akaszubski/Documents/GitHub/autonomous-dev/plugins/autonomous-dev/agents/"
        "project-progress-tracker.md"
    )
    tracker_content = tracker_file.read_text()

    assert "dual-mode" in tracker_content.lower() or \
           "YAML format" in tracker_content and "JSON format" in tracker_content, \
        "project-progress-tracker should preserve dual-mode output guidance"

    # 2. quality-validator: Should keep scoring guidance
    validator_file = Path(
        "/Users/akaszubski/Documents/GitHub/autonomous-dev/plugins/autonomous-dev/agents/"
        "quality-validator.md"
    )
    validator_content = validator_file.read_text()

    assert "score" in validator_content.lower() or "verdict" in validator_content.lower(), \
        "quality-validator should preserve scoring/verdict guidance"

    # 3. commit-message-generator: Should keep conventional commits format
    commit_file = Path(
        "/Users/akaszubski/Documents/GitHub/autonomous-dev/plugins/autonomous-dev/agents/"
        "commit-message-generator.md"
    )
    commit_content = commit_file.read_text()

    assert "conventional" in commit_content.lower() or \
           "feat:" in commit_content or "fix:" in commit_content, \
        "commit-message-generator should preserve conventional commits guidance"


def test_output_format_cleanup_preserves_examples():
    """
    Test that cleanup preserves essential examples while removing templates.

    EXPECTED TO FAIL: Cleanup may remove examples.
    """
    from scripts.measure_output_format_sections import extract_output_format_section

    agents_dir = Path("/Users/akaszubski/Documents/GitHub/autonomous-dev/plugins/autonomous-dev/agents")

    # Check agents that have examples in Output Format
    agents_with_examples = ["quality-validator", "project-progress-tracker"]

    for agent_name in agents_with_examples:
        agent_file = agents_dir / f"{agent_name}.md"
        content = agent_file.read_text()

        # Should have at least one example (look for "Example:", "e.g.", or code blocks)
        has_example = any(marker in content for marker in ["Example:", "e.g.", "```"])

        assert has_example, \
            f"{agent_name} should preserve at least one example after cleanup"


def test_output_format_cleanup_removes_verbose_templates():
    """
    Test that cleanup removes verbose template definitions.

    EXPECTED TO FAIL: Templates may still be present.
    """
    from scripts.measure_output_format_sections import extract_output_format_section

    agents_dir = Path("/Users/akaszubski/Documents/GitHub/autonomous-dev/plugins/autonomous-dev/agents")
    agent_files = list(agents_dir.glob("*.md"))
    agent_files = [f for f in agent_files if "archived" not in str(f)]

    verbose_templates = []
    for agent_file in agent_files:
        content = agent_file.read_text()

        # Look for verbose template patterns in Output Format section
        if "## Output Format" in content:
            section_start = content.find("## Output Format")
            next_section = content.find("## ", section_start + 10)
            if next_section == -1:
                next_section = len(content)

            output_section = content[section_start:next_section]

            # Check for verbose template markers
            verbose_markers = [
                "### Template",
                "Complete template:",
                "Full format specification:",
                "```markdown\n## " * 3,  # Multiple markdown template sections
            ]

            for marker in verbose_markers:
                if marker in output_section:
                    verbose_templates.append(agent_file.stem)
                    break

    assert len(verbose_templates) == 0, \
        f"Agents with verbose templates in Output Format: {verbose_templates}"


def test_output_format_references_agent_output_formats_skill():
    """
    Test that Output Format sections reference agent-output-formats skill.

    EXPECTED TO FAIL: References may not be added yet.
    """
    agents_dir = Path("/Users/akaszubski/Documents/GitHub/autonomous-dev/plugins/autonomous-dev/agents")
    agent_files = list(agents_dir.glob("*.md"))
    agent_files = [f for f in agent_files if "archived" not in str(f)]

    missing_reference = []
    for agent_file in agent_files:
        content = agent_file.read_text()

        # If agent has Output Format section, it should reference the skill
        if "## Output Format" in content:
            section_start = content.find("## Output Format")
            next_section = content.find("## ", section_start + 10)
            if next_section == -1:
                next_section = len(content)

            output_section = content[section_start:next_section]

            # Should mention the skill or refer to standard format
            if "agent-output-formats" not in output_section and \
               "standard format" not in output_section.lower():
                missing_reference.append(agent_file.stem)

    assert len(missing_reference) == 0, \
        f"Output Format sections missing skill reference: {missing_reference}"


# ============================================================================
# Test 6: Phase 2 Target Agents Specific Tests
# ============================================================================


def test_project_progress_tracker_output_format_cleaned():
    """
    Test that project-progress-tracker Output Format is ≤30 lines.

    EXPECTED TO FAIL: project-progress-tracker has very verbose Output Format.
    """
    from scripts.measure_output_format_sections import count_output_format_lines

    agent_file = Path(
        "/Users/akaszubski/Documents/GitHub/autonomous-dev/plugins/autonomous-dev/agents/"
        "project-progress-tracker.md"
    )

    line_count = count_output_format_lines(agent_file)

    assert line_count <= 30, \
        f"project-progress-tracker Output Format should be ≤30 lines, got {line_count}"


def test_quality_validator_output_format_cleaned():
    """
    Test that quality-validator Output Format is concise.

    EXPECTED TO FAIL: May have verbose template.
    """
    from scripts.measure_output_format_sections import count_output_format_lines

    agent_file = Path(
        "/Users/akaszubski/Documents/GitHub/autonomous-dev/plugins/autonomous-dev/agents/"
        "quality-validator.md"
    )

    line_count = count_output_format_lines(agent_file)

    assert line_count <= 30, \
        f"quality-validator Output Format should be ≤30 lines, got {line_count}"


def test_agents_without_output_format_section_have_zero_lines():
    """
    Test that agents without Output Format section return 0 line count.

    EXPECTED TO FAIL: Function may not handle missing section.
    """
    from scripts.measure_output_format_sections import count_output_format_lines

    # test-master doesn't have Output Format section
    agent_file = Path(
        "/Users/akaszubski/Documents/GitHub/autonomous-dev/plugins/autonomous-dev/agents/test-master.md"
    )

    line_count = count_output_format_lines(agent_file)

    assert line_count == 0, \
        f"Agent without Output Format section should return 0, got {line_count}"


# ============================================================================
# Test 7: Cleanup Script Functionality
# ============================================================================


def test_cleanup_script_exists():
    """
    Test that Output Format cleanup script exists.

    EXPECTED TO FAIL: Script doesn't exist yet.
    """
    script_path = Path(
        "/Users/akaszubski/Documents/GitHub/autonomous-dev/scripts/cleanup_output_formats.py"
    )
    assert script_path.exists(), f"Cleanup script not found: {script_path}"


def test_cleanup_script_dry_run_mode():
    """
    Test that cleanup script supports --dry-run mode.

    EXPECTED TO FAIL: Script doesn't exist yet.
    """
    import subprocess

    result = subprocess.run(
        ["python", "scripts/cleanup_output_formats.py", "--dry-run"],
        cwd="/Users/akaszubski/Documents/GitHub/autonomous-dev",
        capture_output=True,
        text=True
    )

    assert result.returncode == 0, f"Dry run failed: {result.stderr}"
    assert "would be modified" in result.stdout.lower() or \
           "dry run" in result.stdout.lower()


def test_cleanup_script_reports_changes():
    """
    Test that cleanup script reports what it changed.

    EXPECTED TO FAIL: Script doesn't exist yet.
    """
    import subprocess

    result = subprocess.run(
        ["python", "scripts/cleanup_output_formats.py", "--dry-run"],
        cwd="/Users/akaszubski/Documents/GitHub/autonomous-dev",
        capture_output=True,
        text=True
    )

    # Should list agents that would be modified
    assert "agents" in result.stdout.lower()
    assert "lines removed" in result.stdout.lower() or \
           "reduction" in result.stdout.lower()


def test_cleanup_script_validates_output():
    """
    Test that cleanup script validates changes don't break agent files.

    EXPECTED TO FAIL: Script doesn't exist yet.
    """
    import subprocess

    # Run with validation flag
    result = subprocess.run(
        ["python", "scripts/cleanup_output_formats.py", "--validate"],
        cwd="/Users/akaszubski/Documents/GitHub/autonomous-dev",
        capture_output=True,
        text=True
    )

    assert result.returncode == 0, f"Validation failed: {result.stderr}"
    assert "validation" in result.stdout.lower()
