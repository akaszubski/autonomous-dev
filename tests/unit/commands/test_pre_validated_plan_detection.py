"""Regression guard for STEP 4.7 pre-validated plan detection in implement.md.

Issue #1138 identified that STEP 5.5a correctly detected pre-validated plans
(after Issue #1135 fixed the verdict-format gate) but the planner had already
produced a divergent plan by the time 5.5a ran. The fix adds STEP 4.7 (inline
detection before the planner) and augments STEP 5 to inject the pre-validated
plan content with a "refine, do not re-scope" directive.

This test suite locks all five acceptance criteria:
- AC1: STEP 4.7 section exists in implement.md
- AC2: STEP 4.7 references .claude/plans/ directory
- AC3: STEP 4.7 stores PRE_VALIDATED_PLAN_PATH and PRE_VALIDATED_PLAN_CONTENT
- AC4: STEP 5 planner prompt augmentation contains pre-validated plan prefix
- AC5: Both verdict formats are accepted (regression guard for Issue #1135)
"""
from pathlib import Path

COMMANDS_DIR = Path(__file__).parents[3] / "plugins" / "autonomous-dev" / "commands"


def _read_command(name: str) -> str:
    """Read a command file by name from the commands directory.

    Args:
        name: Filename within the commands directory (e.g. "implement.md").

    Returns:
        Full text content of the command file.
    """
    return (COMMANDS_DIR / name).read_text()


def test_implement_md_contains_step_47_section() -> None:
    """STEP 4.7 must be present in implement.md (Issue #1138)."""
    content = _read_command("implement.md")
    assert "STEP 4.7" in content, "implement.md must contain STEP 4.7 section (Issue #1138)"


def test_implement_md_step_47_section_references_plans_directory() -> None:
    """STEP 4.7 must reference .claude/plans/ for pre-validated plan lookup (Issue #1138)."""
    content = _read_command("implement.md")
    assert ".claude/plans/" in content, (
        "implement.md STEP 4.7 must reference '.claude/plans/' as the search directory "
        "for pre-validated plans (Issue #1138)"
    )


def test_implement_md_step_47_stores_coordinator_state() -> None:
    """STEP 4.7 must describe storing both coordinator state variables (Issue #1138)."""
    content = _read_command("implement.md")
    assert "PRE_VALIDATED_PLAN_PATH" in content, (
        "implement.md must contain 'PRE_VALIDATED_PLAN_PATH' coordinator state variable "
        "(Issue #1138)"
    )
    assert "PRE_VALIDATED_PLAN_CONTENT" in content, (
        "implement.md must contain 'PRE_VALIDATED_PLAN_CONTENT' coordinator state variable "
        "(Issue #1138)"
    )


def test_implement_md_step_5_planner_prompt_contains_pre_validated_prefix() -> None:
    """STEP 5 planner augmentation must contain the pre-validated plan prefix (Issue #1138)."""
    content = _read_command("implement.md")
    sentinel_phrases = [
        "Pre-validated plan available",
        "Use it as your primary starting point",
        "DO NOT re-scope",
    ]
    found = [phrase for phrase in sentinel_phrases if phrase in content]
    assert len(found) >= 1, (
        f"implement.md STEP 5 planner augmentation must contain at least one of "
        f"{sentinel_phrases!r} (Issue #1138). None were found."
    )


def test_implement_md_step_47_accepts_both_verdict_formats() -> None:
    """STEP 4.7 must accept both verdict formats — regression guard for Issue #1135.

    plan-critic writes verdicts as:
    - "Verdict: PROCEED" (prose/section-header format)
    - "**PROCEED**" (bold table-cell format, in Critique History table)

    Both must appear in implement.md so the coordinator detects pre-validated plans
    regardless of which format the plan file uses.
    """
    content = _read_command("implement.md")
    assert "Verdict: PROCEED" in content, (
        "implement.md must mention 'Verdict: PROCEED' (prose-header verdict format) — "
        "regression guard for Issue #1135"
    )
    assert "**PROCEED**" in content, (
        "implement.md must mention '**PROCEED**' (bold table-cell verdict format) — "
        "regression guard for Issue #1135"
    )
