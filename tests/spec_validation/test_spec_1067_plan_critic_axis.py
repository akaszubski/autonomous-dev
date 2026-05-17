"""Spec-validation tests for Issue #1067.

Tests the 21 acceptance criteria for adding a 6th critique axis
"Operational Integration Test" to the plan-critic agent and related
infrastructure updates (implement.md STEP 5.5b, testing-guide SKILL.md,
PLANNING-WORKFLOW.md).

These tests are derived from the spec only — no implementation knowledge.
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]

PLAN_CRITIC = REPO_ROOT / "plugins" / "autonomous-dev" / "agents" / "plan-critic.md"
IMPLEMENT = REPO_ROOT / "plugins" / "autonomous-dev" / "commands" / "implement.md"
TESTING_GUIDE = REPO_ROOT / "plugins" / "autonomous-dev" / "skills" / "testing-guide" / "SKILL.md"
PLANNING_WORKFLOW = REPO_ROOT / "docs" / "PLANNING-WORKFLOW.md"


@pytest.fixture(scope="module")
def plan_critic_text() -> str:
    return PLAN_CRITIC.read_text()


@pytest.fixture(scope="module")
def implement_text() -> str:
    return IMPLEMENT.read_text()


@pytest.fixture(scope="module")
def testing_guide_text() -> str:
    return TESTING_GUIDE.read_text()


@pytest.fixture(scope="module")
def planning_workflow_text() -> str:
    return PLANNING_WORKFLOW.read_text()


def _critique_axes_section(text: str) -> str:
    """Return text between '## Critique Axes' and the next '## ' heading."""
    m = re.search(r"##\s*Critique Axes\s*\n(.*?)(?=\n##\s)", text, re.DOTALL)
    assert m, "plan-critic.md missing '## Critique Axes' section"
    return m.group(1)


# Criterion 1: plan-critic.md contains "Operational Integration Test" as a 6th axis
def test_spec_issue_1067_criterion_01_axis_6_exists(plan_critic_text: str) -> None:
    axes = _critique_axes_section(plan_critic_text)
    # Must appear in Critique Axes section
    assert "Operational Integration Test" in axes, (
        "Operational Integration Test axis must appear in ## Critique Axes section"
    )
    # Must be the 6th numbered item
    assert re.search(r"^\s*6\.\s*\*\*Operational Integration Test\*\*", axes, re.MULTILINE), (
        "Operational Integration Test must be listed as item 6 in Critique Axes"
    )


# Criterion 2: intro of "## Critique Axes" references "six axes" (or "6 axes")
def test_spec_issue_1067_criterion_02_six_axes_intro(plan_critic_text: str) -> None:
    axes = _critique_axes_section(plan_critic_text)
    # Get just intro before numbered list
    intro = axes.split("1.")[0]
    assert re.search(r"\b(six|6)\s+axes\b", intro, re.IGNORECASE), (
        f"Critique Axes intro must reference 'six axes' or '6 axes'; got: {intro!r}"
    )


# Criterion 3: new axis description mentions subprocess
def test_spec_issue_1067_criterion_03_mentions_subprocess(plan_critic_text: str) -> None:
    axes = _critique_axes_section(plan_critic_text)
    m = re.search(
        r"6\.\s*\*\*Operational Integration Test\*\*[:\s]*(.*?)(?=\n##\s|\Z)",
        axes,
        re.DOTALL,
    )
    assert m, "Could not extract axis 6 description"
    assert "subprocess" in m.group(1).lower()


# Criterion 4: axis description mentions CWD, env vars, or runtime context
def test_spec_issue_1067_criterion_04_mentions_runtime_context(plan_critic_text: str) -> None:
    axes = _critique_axes_section(plan_critic_text)
    m = re.search(
        r"6\.\s*\*\*Operational Integration Test\*\*[:\s]*(.*?)(?=\n##\s|\Z)",
        axes,
        re.DOTALL,
    )
    assert m
    desc = m.group(1).lower()
    assert any(token in desc for token in ("cwd", "env var", "environment variable", "runtime context")), (
        "Axis 6 must mention CWD, env vars, or runtime context"
    )


# Criterion 5: all 5 prior axes remain present
def test_spec_issue_1067_criterion_05_prior_axes_preserved(plan_critic_text: str) -> None:
    axes = _critique_axes_section(plan_critic_text)
    for name in (
        "Assumption Audit",
        "Scope Creep Detection",
        "Existing Solution Search",
        "Minimalism Pressure",
        "Uncertainty Flagging",
    ):
        assert name in axes, f"Prior axis '{name}' must remain present in Critique Axes"


# Criterion 6: Scoring Anchors table includes a row for Operational Integration Test with 1, 3, 5 anchors
def test_spec_issue_1067_criterion_06_scoring_anchors_row(plan_critic_text: str) -> None:
    # Find the Scoring Anchors section
    m = re.search(r"##\s*Scoring Anchors\s*\n(.*?)(?=\n##\s)", plan_critic_text, re.DOTALL)
    assert m, "plan-critic.md missing '## Scoring Anchors' section"
    section = m.group(1)
    # Find the row for Operational Integration Test
    row = re.search(r"^\|\s*Operational Integration Test\s*\|(.*)$", section, re.MULTILINE)
    assert row, "Scoring Anchors table must include a row for 'Operational Integration Test'"
    # The row must have 3 anchor cells beyond the axis name (cells separated by |)
    cells = [c.strip() for c in row.group(1).split("|") if c.strip()]
    assert len(cells) >= 3, (
        f"Operational Integration Test row must have score 1, 3, 5 anchor cells; "
        f"got {len(cells)} cells: {cells}"
    )


def _verdict_section(text: str, verdict: str) -> str:
    """Return the verdict template block for REVISE/PROCEED/BLOCKED.

    Section starts at '### VERDICT' header and ends at the next top-level
    '## ' header or another '### ' header *outside* a fenced code block.
    """
    # Find start
    start_match = re.search(rf"^###\s*{verdict}\s*$", text, re.MULTILINE)
    assert start_match, f"plan-critic.md missing '### {verdict}' verdict template"
    start = start_match.end()
    # Walk forward, tracking fence state, to find the next header outside a fence
    lines = text[start:].splitlines(keepends=True)
    in_fence = False
    collected = []
    for line in lines:
        stripped = line.lstrip()
        if stripped.startswith("```"):
            in_fence = not in_fence
            collected.append(line)
            continue
        if not in_fence and (
            re.match(r"^##\s", line) or re.match(r"^###\s", line)
        ):
            break
        collected.append(line)
    return "".join(collected)


# Criterion 7: REVISE template Scores table includes new axis
def test_spec_issue_1067_criterion_07_revise_template_axis(plan_critic_text: str) -> None:
    section = _verdict_section(plan_critic_text, "REVISE")
    assert "Operational Integration Test" in section, (
        "REVISE verdict template's Scores table must include 'Operational Integration Test'"
    )


# Criterion 8: PROCEED template Scores table includes new axis
def test_spec_issue_1067_criterion_08_proceed_template_axis(plan_critic_text: str) -> None:
    section = _verdict_section(plan_critic_text, "PROCEED")
    assert "Operational Integration Test" in section


# Criterion 9: BLOCKED template Scores table includes new axis
def test_spec_issue_1067_criterion_09_blocked_template_axis(plan_critic_text: str) -> None:
    section = _verdict_section(plan_critic_text, "BLOCKED")
    assert "Operational Integration Test" in section


# Criterion 10: Delta Tracking template includes the new axis
def test_spec_issue_1067_criterion_10_delta_tracking_axis(plan_critic_text: str) -> None:
    m = re.search(r"##\s*Delta Tracking\s*\n(.*?)(?=\n##\s|\Z)", plan_critic_text, re.DOTALL)
    assert m, "plan-critic.md missing '## Delta Tracking' section"
    assert "Operational Integration Test" in m.group(1), (
        "Delta Tracking template must include 'Operational Integration Test'"
    )


# Criterion 11: Budget Mode subsection states 4 axes including Operational Integration Test
def test_spec_issue_1067_criterion_11_budget_mode_four_axes(plan_critic_text: str) -> None:
    m = re.search(
        r"(?:###|##)\s*Budget Mode\s*\n?(.*?)(?=\n##\s|\Z)",
        plan_critic_text,
        re.DOTALL,
    )
    # Budget Mode may also appear as '**Budget Mode**:' inline
    if not m:
        m = re.search(r"\*\*Budget Mode\*\*[:\s](.*?)(?=\n##\s|\n###\s|\Z)", plan_critic_text, re.DOTALL)
    assert m, "plan-critic.md missing 'Budget Mode' subsection"
    section = m.group(1)
    assert re.search(r"\b(four|4)\s+axes\b", section, re.IGNORECASE), (
        "Budget Mode must state '4 axes' (or 'four axes')"
    )
    assert "Operational Integration Test" in section


# Criterion 12: Verdict-Score Mapping table unchanged
def test_spec_issue_1067_criterion_12_verdict_score_mapping_unchanged(plan_critic_text: str) -> None:
    m = re.search(r"##\s*Verdict-Score Mapping\s*\n(.*?)(?=\n##\s)", plan_critic_text, re.DOTALL)
    assert m, "plan-critic.md missing '## Verdict-Score Mapping' section"
    section = m.group(1)
    # PROCEED: composite >= 3.0, no axis below 2
    assert re.search(r">\s*=?\s*3\.0", section), "PROCEED threshold (>=3.0) must be present"
    # REVISE: < 3.0 OR any axis at 1
    assert re.search(r"<\s*3\.0", section), "REVISE threshold (<3.0) must be present"
    # BLOCKED: < 2.0 OR 2+ axes at 1
    assert re.search(r"<\s*2\.0", section), "BLOCKED threshold (<2.0) must be present"
    assert "PROCEED" in section
    assert "REVISE" in section
    assert "BLOCKED" in section


# Criterion 13: implement.md STEP 5.5b lists 4 axes including Operational Integration Test
def test_spec_issue_1067_criterion_13_implement_5_5b_four_axes(implement_text: str) -> None:
    m = re.search(
        r"####\s*5\.5b\s*[—–-].*?\n(.*?)(?=\n####\s|\n###\s|\n##\s)",
        implement_text,
        re.DOTALL,
    )
    assert m, "implement.md missing '#### 5.5b' subsection"
    section = m.group(1)
    # Must list 4 axes
    assert re.search(r"\b(four|4)\s+(axes|only)\b", section, re.IGNORECASE) or "4 only" in section, (
        f"STEP 5.5b must reference 4 axes; section: {section[:500]}"
    )
    # Must include Operational Integration Test
    assert "Operational Integration Test" in section


# Criterion 14: STEP 5.5b inline instruction string mentions all 4 axes
def test_spec_issue_1067_criterion_14_implement_5_5b_inline_instructions(implement_text: str) -> None:
    m = re.search(
        r"####\s*5\.5b\s*[—–-].*?\n(.*?)(?=\n####\s|\n###\s|\n##\s)",
        implement_text,
        re.DOTALL,
    )
    assert m
    section = m.group(1)
    # Find quoted instruction string (the Instruct: "..." sentence)
    quoted = re.search(r'Instruct:\s*"([^"]+)"', section)
    assert quoted, "STEP 5.5b must contain an Instruct: \"...\" quoted instruction string"
    instruction = quoted.group(1)
    for axis in (
        "Assumption Audit",
        "Existing Solution Search",
        "Minimalism Pressure",
        "Operational Integration Test",
    ):
        assert axis in instruction, (
            f"STEP 5.5b inline Instruct: string must mention '{axis}'; got: {instruction!r}"
        )


# Criterion 15: testing-guide SKILL.md contains heading "Runtime Integration Testing Patterns"
def test_spec_issue_1067_criterion_15_runtime_section_heading(testing_guide_text: str) -> None:
    assert re.search(r"^#+\s*.*Runtime Integration Testing Patterns", testing_guide_text, re.MULTILINE), (
        "testing-guide SKILL.md must contain a heading 'Runtime Integration Testing Patterns'"
    )


def _runtime_section(text: str) -> str:
    """Extract the Runtime Integration Testing Patterns section.

    Walks forward from the heading and stops at the next heading of the
    SAME or HIGHER level (i.e. fewer or equal number of '#'), tracking
    fenced code blocks so '###' inside a code fence is not treated as a
    heading boundary.
    """
    start_match = re.search(
        r"^(#+)\s*.*Runtime Integration Testing Patterns.*$", text, re.MULTILINE
    )
    assert start_match, "Cannot find 'Runtime Integration Testing Patterns' section"
    heading_level = len(start_match.group(1))
    start = start_match.end()
    lines = text[start:].splitlines(keepends=True)
    in_fence = False
    collected = []
    for line in lines:
        stripped = line.lstrip()
        if stripped.startswith("```"):
            in_fence = not in_fence
            collected.append(line)
            continue
        if not in_fence:
            h = re.match(r"^(#+)\s", line)
            if h and len(h.group(1)) <= heading_level:
                break
        collected.append(line)
    return "".join(collected)


# Criterion 16: section mentions "monkeypatch"
def test_spec_issue_1067_criterion_16_mentions_monkeypatch(testing_guide_text: str) -> None:
    section = _runtime_section(testing_guide_text)
    assert "monkeypatch" in section.lower()


# Criterion 17: section mentions "kwargs" and "subprocess"
def test_spec_issue_1067_criterion_17_mentions_kwargs_subprocess(testing_guide_text: str) -> None:
    section = _runtime_section(testing_guide_text)
    assert "kwargs" in section.lower()
    assert "subprocess" in section.lower()


# Criterion 18: section mentions "cwd"
def test_spec_issue_1067_criterion_18_mentions_cwd(testing_guide_text: str) -> None:
    section = _runtime_section(testing_guide_text)
    assert "cwd" in section.lower()


# Criterion 19: section references Issue #1064
def test_spec_issue_1067_criterion_19_references_issue_1064(testing_guide_text: str) -> None:
    section = _runtime_section(testing_guide_text)
    assert re.search(r"#1064|Issue\s*1064|issue\s*#?1064", section, re.IGNORECASE), (
        "Runtime Integration Testing Patterns section must reference Issue #1064"
    )


# Criterion 20: section cites the reference example
def test_spec_issue_1067_criterion_20_cites_reference_example(testing_guide_text: str) -> None:
    section = _runtime_section(testing_guide_text)
    has_test_name = "test_call_claude_p_judge_passes_cwd_to_avoid_project_context" in section
    has_test_file = "test_extract_and_label_intent_corpus.py" in section
    assert has_test_name or has_test_file, (
        "Runtime section must cite either the test function name or the test file path"
    )


# Criterion 21: section includes an anti-pattern example
def test_spec_issue_1067_criterion_21_includes_anti_pattern(testing_guide_text: str) -> None:
    section = _runtime_section(testing_guide_text)
    assert re.search(r"[Aa]nti-?[Pp]attern", section), (
        "Runtime section must include an Anti-pattern subsection / example"
    )


# Bonus: docs/PLANNING-WORKFLOW.md line ~44 says "6 axes" with the new bullet
def test_spec_issue_1067_planning_workflow_six_axes(planning_workflow_text: str) -> None:
    # Find "X axes" reference
    assert re.search(r"\b6\s+axes\b", planning_workflow_text) or re.search(
        r"\bsix\s+axes\b", planning_workflow_text, re.IGNORECASE
    ), "PLANNING-WORKFLOW.md must reference '6 axes' (or 'six axes')"
    assert "Operational Integration Test" in planning_workflow_text, (
        "PLANNING-WORKFLOW.md must list 'Operational Integration Test' as a critique axis bullet"
    )
