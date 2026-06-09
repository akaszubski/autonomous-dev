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

Issue #1175 extends this file with STEP 4.8 (Plan Freshness Re-Verification)
coverage: a complementary T2 fix that re-verifies referenced paths in a
pre-validated plan still exist before seeding the planner.
"""
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).parents[3]
COMMANDS_DIR = REPO_ROOT / "plugins" / "autonomous-dev" / "commands"
LIB_DIR = REPO_ROOT / "plugins" / "autonomous-dev" / "lib"

# Make the lib package importable for the Issue #1175 helper tests.
if str(LIB_DIR) not in sys.path:
    sys.path.insert(0, str(LIB_DIR))

from plan_freshness import extract_referenced_paths, verify_paths_exist  # noqa: E402


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


# ----------------------------------------------------------------------------
# Issue #1175 — STEP 4.8 Plan Freshness Re-Verification
# ----------------------------------------------------------------------------


def test_extract_referenced_paths_finds_python_and_md_files() -> None:
    """Helper unit test: regex extraction returns expected paths (Issue #1175)."""
    plan = (
        "## Files to Modify\n"
        "- `plugins/autonomous-dev/lib/foo.py` — add helper\n"
        "- `docs/RUNBOOK.md` — update reference\n"
        "- `config/settings.json` — new key\n"
        "Some prose with no path here.\n"
        "Duplicate: plugins/autonomous-dev/lib/foo.py is listed twice.\n"
    )
    paths = extract_referenced_paths(plan)
    # Deduplicated + sorted output.
    assert paths == [
        "config/settings.json",
        "docs/RUNBOOK.md",
        "plugins/autonomous-dev/lib/foo.py",
    ], f"Unexpected extraction output: {paths!r}"


def test_extract_referenced_paths_handles_empty_input() -> None:
    """Helper unit test: empty/whitespace input returns empty list (Issue #1175)."""
    assert extract_referenced_paths("") == []
    assert extract_referenced_paths("no paths in this prose at all") == []


def test_verify_paths_exist_returns_missing_paths_only(tmp_path: Path) -> None:
    """Helper unit test: existence verification returns only the missing subset (Issue #1175)."""
    # Stage two real files under tmp_path, leave a third unreferenced.
    (tmp_path / "real_a.py").write_text("# real")
    (tmp_path / "docs").mkdir()
    (tmp_path / "docs" / "real_b.md").write_text("# real")

    paths = [
        "real_a.py",
        "docs/real_b.md",
        "docs/missing_c.md",
        "nonexistent/missing_d.py",
    ]
    missing = verify_paths_exist(paths, tmp_path)
    assert missing == [
        "docs/missing_c.md",
        "nonexistent/missing_d.py",
    ], f"Unexpected missing list: {missing!r}"


def test_verify_paths_exist_returns_empty_when_all_present(tmp_path: Path) -> None:
    """Helper unit test: empty list when every path exists (Issue #1175)."""
    (tmp_path / "a.py").write_text("")
    (tmp_path / "b.md").write_text("")
    assert verify_paths_exist(["a.py", "b.md"], tmp_path) == []


def test_step_48_integration_detects_missing_file_path(tmp_path: Path) -> None:
    """Integration smoke test: plan referencing a nonexistent file is flagged (Issue #1175)."""
    plan = (
        "## Plan\n"
        "Edit `plugins/autonomous-dev/lib/nonexistent_module_for_test.py`\n"
        "Update `plugins/autonomous-dev/commands/implement.md` too.\n"
    )
    paths = extract_referenced_paths(plan)
    missing = verify_paths_exist(paths, REPO_ROOT)

    # The nonexistent helper module must appear in the missing list.
    assert "plugins/autonomous-dev/lib/nonexistent_module_for_test.py" in missing, (
        f"Expected nonexistent path to be flagged. Got missing={missing!r}"
    )
    # The real implement.md must NOT appear in the missing list.
    assert "plugins/autonomous-dev/commands/implement.md" not in missing, (
        "Real file implement.md was incorrectly flagged as missing"
    )


def test_step_48_section_exists_in_implement_md() -> None:
    """AC1: STEP 4.8 section header exists in implement.md (Issue #1175)."""
    content = _read_command("implement.md")
    assert "STEP 4.8" in content, (
        "implement.md must contain STEP 4.8 section header (Issue #1175)"
    )


def test_step_48_positioned_between_47_and_5() -> None:
    """AC1: STEP 4.8 must appear after STEP 4.7 and before STEP 5 (Issue #1175)."""
    content = _read_command("implement.md")
    idx_47 = content.find("### STEP 4.7:")
    idx_48 = content.find("### STEP 4.8:")
    idx_5 = content.find("### STEP 5:")
    assert idx_47 != -1, "STEP 4.7 section heading missing"
    assert idx_48 != -1, "STEP 4.8 section heading missing"
    assert idx_5 != -1, "STEP 5 section heading missing"
    assert idx_47 < idx_48 < idx_5, (
        f"STEP 4.8 must be positioned between 4.7 and 5. "
        f"Got positions 4.7={idx_47}, 4.8={idx_48}, 5={idx_5}"
    )


def test_step_48_activation_gate_uses_AND() -> None:
    """AC2: STEP 4.8 gate uses AND of PRE_VALIDATED_PLAN_PATH and mtime (Issue #1175)."""
    content = _read_command("implement.md")
    idx_48 = content.find("### STEP 4.8:")
    idx_5 = content.find("### STEP 5:")
    assert idx_48 != -1 and idx_5 != -1
    section = content[idx_48:idx_5]

    assert "PRE_VALIDATED_PLAN_PATH" in section, (
        "STEP 4.8 must reference PRE_VALIDATED_PLAN_PATH activation variable"
    )
    assert "86400" in section, (
        "STEP 4.8 must specify the 86400-second (24h) mtime staleness threshold"
    )
    # Case-insensitive AND check.
    assert "AND" in section.upper(), (
        "STEP 4.8 activation gate must explicitly use AND logic (not OR) — "
        "both PRE_VALIDATED_PLAN_PATH set AND mtime > 86400s"
    )


def test_step_48_references_construct_revision_prompt() -> None:
    """AC3: STEP 4.8 failure path uses construct_revision_prompt and no retry loop (Issue #1175)."""
    content = _read_command("implement.md")
    idx_48 = content.find("### STEP 4.8:")
    idx_5 = content.find("### STEP 5:")
    assert idx_48 != -1 and idx_5 != -1
    section = content[idx_48:idx_5]

    assert "construct_revision_prompt" in section, (
        "STEP 4.8 must reference construct_revision_prompt for the planner "
        "re-invocation (mirrors STEP 5.5b pattern, Issue #1116)"
    )
    # No retry loop language — single-revision semantics.
    lowered = section.lower()
    assert " while " not in lowered and "\nwhile " not in lowered, (
        "STEP 4.8 must NOT contain a 'while' retry loop — single-revision semantics"
    )
    assert "until" not in lowered, (
        "STEP 4.8 must NOT contain 'until' retry-loop language — single-revision semantics"
    )
    # Allow the word "retry" only if absent — assert it is absent.
    assert "retry" not in lowered, (
        "STEP 4.8 must NOT contain retry-loop language — re-invoke planner ONCE then continue"
    )
