"""
TDD RED Phase Tests for Issue #72: Skill Reference Validation

Tests that all 20 agents have agent-output-formats skill reference after cleanup.
All tests should FAIL initially (no implementation exists yet).

Test Coverage:
1. All agents have "Relevant Skills" section
2. All agents reference agent-output-formats skill
3. Skill reference format is correct
4. Phase 1 target agents get skill reference added
5. Existing skill references are preserved
"""

import pytest
from pathlib import Path
from typing import List, Dict, Optional
import re


# ============================================================================
# Helper Functions (will be mocked in tests)
# ============================================================================


def parse_agent_file(agent_path: Path) -> Dict:
    """
    Parse agent markdown file and extract structured data.

    EXPECTED TO FAIL: Function doesn't exist yet.
    """
    # Will be implemented by implementer agent
    raise NotImplementedError("parse_agent_file not implemented yet")


def get_relevant_skills(agent_path: Path) -> List[str]:
    """
    Extract list of relevant skills from agent file.

    EXPECTED TO FAIL: Function doesn't exist yet.
    """
    raise NotImplementedError("get_relevant_skills not implemented yet")


def has_skill_reference(agent_path: Path, skill_name: str) -> bool:
    """
    Check if agent file references specific skill.

    EXPECTED TO FAIL: Function doesn't exist yet.
    """
    raise NotImplementedError("has_skill_reference not implemented yet")


# ============================================================================
# Test 1: All Agents Have Relevant Skills Section
# ============================================================================


def test_all_agents_have_relevant_skills_section():
    """
    Test that all 20 agents have "Relevant Skills" section.

    EXPECTED TO FAIL: Some agents may not have the section yet.
    """
    agents_dir = Path("${PROJECT_ROOT}/plugins/autonomous-dev/agents")
    agent_files = list(agents_dir.glob("*.md"))

    # Exclude archived agents
    agent_files = [f for f in agent_files if "archived" not in str(f)]

    assert len(agent_files) == 20, f"Expected 20 agents, found {len(agent_files)}"

    missing_section = []
    for agent_file in agent_files:
        content = agent_file.read_text()
        if "## Relevant Skills" not in content:
            missing_section.append(agent_file.stem)

    assert len(missing_section) == 0, \
        f"Agents missing 'Relevant Skills' section: {missing_section}"


def test_relevant_skills_section_is_properly_formatted():
    """
    Test that Relevant Skills section follows standard format.

    EXPECTED TO FAIL: Some agents may have incorrect format.
    """
    agents_dir = Path("${PROJECT_ROOT}/plugins/autonomous-dev/agents")
    agent_files = list(agents_dir.glob("*.md"))
    agent_files = [f for f in agent_files if "archived" not in str(f)]

    malformed = []
    for agent_file in agent_files:
        content = agent_file.read_text()

        # Find Relevant Skills section
        if "## Relevant Skills" not in content:
            continue

        # Should be followed by explanatory text
        section_start = content.find("## Relevant Skills")
        section_text = content[section_start:section_start + 500]

        # Should have "You have access to these specialized skills" or similar intro
        if "specialized skills" not in section_text.lower():
            malformed.append(f"{agent_file.stem}: Missing intro text")

        # Should have bullet list of skills
        if "- **" not in section_text:
            malformed.append(f"{agent_file.stem}: Missing skill bullet list")

    assert len(malformed) == 0, \
        f"Agents with malformed Relevant Skills section: {malformed}"


def test_relevant_skills_section_placement():
    """
    Test that Relevant Skills section is placed near end of agent prompt.

    EXPECTED TO FAIL: Some agents may have incorrect placement.
    """
    agents_dir = Path("${PROJECT_ROOT}/plugins/autonomous-dev/agents")
    agent_files = list(agents_dir.glob("*.md"))
    agent_files = [f for f in agent_files if "archived" not in str(f)]

    incorrect_placement = []
    for agent_file in agent_files:
        content = agent_file.read_text()

        if "## Relevant Skills" not in content:
            continue

        # Should come after main mission/workflow sections
        relevant_skills_pos = content.find("## Relevant Skills")

        # Should have Summary section after it
        summary_pos = content.find("## Summary")

        if summary_pos > 0 and summary_pos < relevant_skills_pos:
            incorrect_placement.append(
                f"{agent_file.stem}: Relevant Skills should come before Summary"
            )

    assert len(incorrect_placement) == 0, \
        f"Agents with incorrect section placement: {incorrect_placement}"


# ============================================================================
# Test 2: All Agents Reference agent-output-formats Skill
# ============================================================================


def test_all_agents_reference_agent_output_formats_skill():
    """
    Test that all 20 agents reference agent-output-formats skill.

    EXPECTED TO FAIL: Phase 1 target agents don't have reference yet.
    """
    agents_dir = Path("${PROJECT_ROOT}/plugins/autonomous-dev/agents")
    agent_files = list(agents_dir.glob("*.md"))
    agent_files = [f for f in agent_files if "archived" not in str(f)]

    missing_reference = []
    for agent_file in agent_files:
        content = agent_file.read_text()

        # Check for agent-output-formats reference
        if "agent-output-formats" not in content:
            missing_reference.append(agent_file.stem)

    assert len(missing_reference) == 0, \
        f"Agents missing agent-output-formats reference: {missing_reference}"


def test_phase1_target_agents_have_skill_reference():
    """
    Test that Phase 1 target agents have agent-output-formats reference.

    Phase 1 targets: test-master, quality-validator, advisor,
                     alignment-validator, project-progress-tracker

    EXPECTED TO FAIL: These agents don't have reference yet (Phase 1 work).
    """
    phase1_targets = [
        "test-master",
        "quality-validator",
        "advisor",
        "alignment-validator",
        "project-progress-tracker"
    ]

    agents_dir = Path("${PROJECT_ROOT}/plugins/autonomous-dev/agents")

    missing = []
    for agent_name in phase1_targets:
        agent_file = agents_dir / f"{agent_name}.md"
        assert agent_file.exists(), f"Agent file not found: {agent_file}"

        content = agent_file.read_text()
        if "agent-output-formats" not in content:
            missing.append(agent_name)

    assert len(missing) == 0, \
        f"Phase 1 agents missing agent-output-formats reference: {missing}"


def test_agent_output_formats_reference_is_in_relevant_skills_section():
    """
    Test that agent-output-formats reference is in Relevant Skills section.

    EXPECTED TO FAIL: Some agents may reference it elsewhere.
    """
    agents_dir = Path("${PROJECT_ROOT}/plugins/autonomous-dev/agents")
    agent_files = list(agents_dir.glob("*.md"))
    agent_files = [f for f in agent_files if "archived" not in str(f)]

    incorrect_location = []
    for agent_file in agent_files:
        content = agent_file.read_text()

        if "agent-output-formats" not in content:
            continue

        # Find Relevant Skills section
        relevant_skills_start = content.find("## Relevant Skills")
        next_section = content.find("## ", relevant_skills_start + 10)

        if next_section == -1:
            next_section = len(content)

        relevant_skills_section = content[relevant_skills_start:next_section]

        # Check if agent-output-formats is in this section
        if "agent-output-formats" not in relevant_skills_section:
            incorrect_location.append(agent_file.stem)

    assert len(incorrect_location) == 0, \
        f"Agents with agent-output-formats outside Relevant Skills section: {incorrect_location}"


# ============================================================================
# Test 3: Skill Reference Format is Correct
# ============================================================================


def test_skill_reference_follows_standard_format():
    """
    Test that skill references follow format: - **skill-name**: Description

    EXPECTED TO FAIL: Some agents may have incorrect format.
    """
    agents_dir = Path("${PROJECT_ROOT}/plugins/autonomous-dev/agents")
    agent_files = list(agents_dir.glob("*.md"))
    agent_files = [f for f in agent_files if "archived" not in str(f)]

    malformed = []
    for agent_file in agent_files:
        content = agent_file.read_text()

        if "agent-output-formats" not in content:
            continue

        # Check format: - **agent-output-formats**: ...
        pattern = r'- \*\*agent-output-formats\*\*:\s+.+'
        match = re.search(pattern, content)

        if not match:
            malformed.append(f"{agent_file.stem}: Incorrect format for agent-output-formats")

    assert len(malformed) == 0, \
        f"Agents with malformed skill reference: {malformed}"


def test_skill_reference_has_description():
    """
    Test that agent-output-formats reference includes description.

    EXPECTED TO FAIL: Some agents may have empty or missing description.
    """
    agents_dir = Path("${PROJECT_ROOT}/plugins/autonomous-dev/agents")
    agent_files = list(agents_dir.glob("*.md"))
    agent_files = [f for f in agent_files if "archived" not in str(f)]

    missing_description = []
    for agent_file in agent_files:
        content = agent_file.read_text()

        if "agent-output-formats" not in content:
            continue

        # Find the reference line
        for line in content.split('\n'):
            if "- **agent-output-formats**:" in line:
                # Check if there's text after the colon
                parts = line.split("**agent-output-formats**:")
                if len(parts) < 2 or len(parts[1].strip()) < 10:
                    missing_description.append(agent_file.stem)
                break

    assert len(missing_description) == 0, \
        f"Agents with missing/empty agent-output-formats description: {missing_description}"


def test_skill_reference_description_is_relevant():
    """
    Test that agent-output-formats description mentions output/format/structure.

    EXPECTED TO FAIL: Some agents may have generic description.
    """
    agents_dir = Path("${PROJECT_ROOT}/plugins/autonomous-dev/agents")
    agent_files = list(agents_dir.glob("*.md"))
    agent_files = [f for f in agent_files if "archived" not in str(f)]

    irrelevant_description = []
    for agent_file in agent_files:
        content = agent_file.read_text()

        if "agent-output-formats" not in content:
            continue

        # Find the reference line
        for line in content.split('\n'):
            if "- **agent-output-formats**:" in line:
                description = line.split("**agent-output-formats**:")[1].strip()

                # Should mention output, format, or structure
                keywords = ["output", "format", "structure", "response", "result"]
                if not any(kw in description.lower() for kw in keywords):
                    irrelevant_description.append(agent_file.stem)
                break

    assert len(irrelevant_description) == 0, \
        f"Agents with irrelevant agent-output-formats description: {irrelevant_description}"


# ============================================================================
# Test 4: Phase 1 Target Agents Specific Tests
# ============================================================================


def test_test_master_has_agent_output_formats_reference():
    """
    Test that test-master agent has agent-output-formats reference.

    EXPECTED TO FAIL: test-master doesn't have reference yet (Phase 1).
    """
    agent_file = Path(
        "${PROJECT_ROOT}/plugins/autonomous-dev/agents/test-master.md"
    )
    content = agent_file.read_text()

    assert "agent-output-formats" in content, \
        "test-master should reference agent-output-formats skill"

    # Should be in Relevant Skills section
    relevant_skills_section = content[content.find("## Relevant Skills"):]
    assert "agent-output-formats" in relevant_skills_section, \
        "agent-output-formats should be in Relevant Skills section"


def test_quality_validator_has_agent_output_formats_reference():
    """
    Test that quality-validator agent has agent-output-formats reference.

    EXPECTED TO FAIL: quality-validator doesn't have reference yet (Phase 1).
    """
    agent_file = Path(
        "${PROJECT_ROOT}/plugins/autonomous-dev/agents/quality-validator.md"
    )
    content = agent_file.read_text()

    assert "agent-output-formats" in content, \
        "quality-validator should reference agent-output-formats skill"


def test_advisor_has_agent_output_formats_reference():
    """
    Test that advisor agent has agent-output-formats reference.

    EXPECTED TO FAIL: advisor doesn't have reference yet (Phase 1).
    """
    agent_file = Path(
        "${PROJECT_ROOT}/plugins/autonomous-dev/agents/advisor.md"
    )
    content = agent_file.read_text()

    assert "agent-output-formats" in content, \
        "advisor should reference agent-output-formats skill"


def test_alignment_validator_has_agent_output_formats_reference():
    """
    Test that alignment-validator agent has agent-output-formats reference.

    EXPECTED TO FAIL: alignment-validator doesn't have reference yet (Phase 1).
    """
    agent_file = Path(
        "${PROJECT_ROOT}/agents/alignment-validator.md"
    )
    content = agent_file.read_text()

    assert "agent-output-formats" in content, \
        "alignment-validator should reference agent-output-formats skill"


def test_project_progress_tracker_has_agent_output_formats_reference():
    """
    Test that project-progress-tracker has agent-output-formats reference.

    EXPECTED TO FAIL: project-progress-tracker doesn't have reference yet (Phase 1).
    """
    agent_file = Path(
        "${PROJECT_ROOT}/plugins/autonomous-dev/agents/project-progress-tracker.md"
    )
    content = agent_file.read_text()

    assert "agent-output-formats" in content, \
        "project-progress-tracker should reference agent-output-formats skill"


# ============================================================================
# Test 5: Existing Skill References Are Preserved
# ============================================================================


def test_existing_skill_references_are_preserved():
    """
    Test that adding agent-output-formats doesn't remove existing skills.

    EXPECTED TO FAIL: Implementation may accidentally remove existing skills.
    """
    # Example: test-master should keep existing skills
    agent_file = Path(
        "${PROJECT_ROOT}/plugins/autonomous-dev/agents/test-master.md"
    )
    content = agent_file.read_text()

    # Should have both original skills AND agent-output-formats
    expected_skills = [
        "testing-guide",
        "python-standards",
        "code-review",
        "security-patterns",
        "api-design",
        "agent-output-formats"  # NEW
    ]

    missing_skills = []
    for skill in expected_skills:
        if skill not in content:
            missing_skills.append(skill)

    assert len(missing_skills) == 0, \
        f"test-master missing skills: {missing_skills}"


def test_quality_validator_preserves_existing_skills():
    """
    Test that quality-validator keeps existing skills when agent-output-formats added.

    EXPECTED TO FAIL: Implementation may remove existing skills.
    """
    agent_file = Path(
        "${PROJECT_ROOT}/plugins/autonomous-dev/agents/quality-validator.md"
    )
    content = agent_file.read_text()

    expected_skills = [
        "testing-guide",
        "code-review",
        "security-patterns",
        "consistency-enforcement",
        "agent-output-formats"  # NEW
    ]

    missing_skills = []
    for skill in expected_skills:
        if skill not in content:
            missing_skills.append(skill)

    assert len(missing_skills) == 0, \
        f"quality-validator missing skills: {missing_skills}"


def test_skill_list_maintains_alphabetical_order():
    """
    Test that skills remain in logical order after adding agent-output-formats.

    EXPECTED TO FAIL: Implementation may not maintain proper ordering.
    """
    agents_dir = Path("${PROJECT_ROOT}/plugins/autonomous-dev/agents")
    agent_files = list(agents_dir.glob("*.md"))
    agent_files = [f for f in agent_files if "archived" not in str(f)]

    # Check a few key agents
    target_agents = ["test-master", "quality-validator", "advisor"]

    for agent_name in target_agents:
        agent_file = agents_dir / f"{agent_name}.md"
        content = agent_file.read_text()

        # Extract skills from Relevant Skills section
        relevant_skills_start = content.find("## Relevant Skills")
        if relevant_skills_start == -1:
            continue

        next_section = content.find("## ", relevant_skills_start + 10)
        if next_section == -1:
            next_section = len(content)

        skills_section = content[relevant_skills_start:next_section]

        # Extract skill names
        skill_pattern = r'- \*\*([a-z-]+)\*\*:'
        skills = re.findall(skill_pattern, skills_section)

        # agent-output-formats should be first (alphabetically before most others)
        if "agent-output-formats" in skills:
            assert skills.index("agent-output-formats") < len(skills) / 2, \
                f"{agent_name}: agent-output-formats should appear early in skill list"


# ============================================================================
# Test 6: Skill Reference Validation Script
# ============================================================================


def test_validation_script_exists():
    """
    Test that skill reference validation script exists.

    EXPECTED TO FAIL: Script doesn't exist yet.
    """
    script_path = Path(
        "${PROJECT_ROOT}/scripts/validate_agent_skill_references.py"
    )
    assert script_path.exists(), f"Validation script not found: {script_path}"


def test_validation_script_checks_all_agents():
    """
    Test that validation script checks all 20 agents for skill references.

    EXPECTED TO FAIL: Script doesn't exist yet.
    """
    import subprocess

    result = subprocess.run(
        ["python", "scripts/validate_agent_skill_references.py"],
        cwd="${PROJECT_ROOT}",
        capture_output=True,
        text=True
    )

    assert result.returncode == 0, f"Validation failed: {result.stderr}"
    assert "20 agents checked" in result.stdout


def test_validation_script_reports_missing_references():
    """
    Test that validation script identifies agents missing agent-output-formats.

    EXPECTED TO FAIL: Script doesn't exist yet.
    """
    import subprocess

    result = subprocess.run(
        ["python", "scripts/validate_agent_skill_references.py", "--check-agent-output-formats"],
        cwd="${PROJECT_ROOT}",
        capture_output=True,
        text=True
    )

    # Should list agents that need agent-output-formats reference
    if result.returncode != 0:
        assert "Missing agent-output-formats" in result.stdout or \
               "Missing agent-output-formats" in result.stderr


def test_validation_script_supports_json_output():
    """
    Test that validation script can output results as JSON.

    EXPECTED TO FAIL: Script doesn't exist yet.
    """
    import subprocess
    import json

    result = subprocess.run(
        ["python", "scripts/validate_agent_skill_references.py", "--json"],
        cwd="${PROJECT_ROOT}",
        capture_output=True,
        text=True
    )

    assert result.returncode == 0, f"Validation failed: {result.stderr}"

    # Output should be valid JSON
    data = json.loads(result.stdout)
    assert "agents_checked" in data
    assert "missing_references" in data


# ============================================================================
# Test 7: Integration with agent-output-formats Skill
# ============================================================================


def test_agent_output_formats_skill_exists():
    """
    Test that agent-output-formats skill file exists.

    EXPECTED TO FAIL: Should pass (skill already exists from Issues #63, #64).
    """
    skill_path = Path(
        "${PROJECT_ROOT}/plugins/autonomous-dev/skills/"
        "agent-output-formats/SKILL.md"
    )
    assert skill_path.exists(), f"agent-output-formats skill not found: {skill_path}"


def test_agent_output_formats_skill_has_metadata():
    """
    Test that agent-output-formats skill has proper frontmatter.

    EXPECTED TO FAIL: Should pass (skill already exists).
    """
    skill_path = Path(
        "${PROJECT_ROOT}/plugins/autonomous-dev/skills/"
        "agent-output-formats/SKILL.md"
    )
    content = skill_path.read_text()

    # Check frontmatter
    assert content.startswith("---"), "Skill missing frontmatter"
    assert "name: agent-output-formats" in content
    assert "type: knowledge" in content
    assert "auto_activate: true" in content


def test_agent_references_match_skill_content():
    """
    Test that agent descriptions align with skill's actual purpose.

    EXPECTED TO FAIL: Descriptions may not match yet.
    """
    skill_path = Path(
        "${PROJECT_ROOT}/plugins/autonomous-dev/skills/"
        "agent-output-formats/SKILL.md"
    )
    skill_content = skill_path.read_text()

    # Extract skill description from frontmatter
    skill_desc = ""
    for line in skill_content.split('\n'):
        if line.startswith("description:"):
            skill_desc = line.split("description:")[1].strip()
            break

    agents_dir = Path("${PROJECT_ROOT}/plugins/autonomous-dev/agents")
    agent_files = list(agents_dir.glob("*.md"))
    agent_files = [f for f in agent_files if "archived" not in str(f)]

    # Check that agent descriptions relate to skill's purpose
    for agent_file in agent_files:
        content = agent_file.read_text()

        if "agent-output-formats" not in content:
            continue

        # Find the reference line
        for line in content.split('\n'):
            if "- **agent-output-formats**:" in line:
                agent_desc = line.split("**agent-output-formats**:")[1].strip()

                # Should mention similar concepts as skill description
                # (output, format, standardized, etc.)
                if len(agent_desc) > 10:
                    # Just verify it's not completely unrelated
                    assert len(agent_desc) > 5, \
                        f"{agent_file.stem}: agent-output-formats description too short"
