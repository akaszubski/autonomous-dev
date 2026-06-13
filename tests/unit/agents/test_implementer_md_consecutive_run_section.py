"""Regression tests for Issue #1184.

Validates that implementer.md contains the Consecutive-Run Test Isolation
HARD GATE section and all required content elements.
"""

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
IMPLEMENTER_MD = REPO_ROOT / "plugins/autonomous-dev/agents/implementer.md"

SECTION_HEADER = "## HARD GATE: Consecutive-Run Test Isolation (Issue #1184)"
SELF_VALIDATION_HEADER = "## HARD GATE: Output Self-Validation (Issue #707)"
ERROR_RECOVERY_HEADER = "## HARD GATE: Error Recovery with Retry Budget (Issue #708)"


def _content() -> str:
    return IMPLEMENTER_MD.read_text(encoding="utf-8")


def test_implementer_md_has_consecutive_run_section() -> None:
    """Issue #1184: implementer.md must contain the new HARD GATE section header."""
    assert SECTION_HEADER in _content(), (
        f"Missing section '{SECTION_HEADER}' in implementer.md"
    )


def test_implementer_md_mentions_twice_consecutively() -> None:
    """Issue #1184: the new section must require running tests twice consecutively."""
    content = _content()
    section_start = content.find(SECTION_HEADER)
    assert section_start != -1, f"Section header not found: {SECTION_HEADER}"

    # Find the next top-level ## header after our section
    next_section = content.find("\n## ", section_start + len(SECTION_HEADER))
    section_body = content[section_start:next_section] if next_section != -1 else content[section_start:]

    assert "twice consecutively" in section_body, (
        "Section must mention running tests 'twice consecutively'"
    )


def test_implementer_md_mentions_autouse_fixture() -> None:
    """Issue #1184: the new section must include an autouse fixture example."""
    content = _content()
    section_start = content.find(SECTION_HEADER)
    assert section_start != -1, f"Section header not found: {SECTION_HEADER}"

    next_section = content.find("\n## ", section_start + len(SECTION_HEADER))
    section_body = content[section_start:next_section] if next_section != -1 else content[section_start:]

    assert "autouse" in section_body, (
        "Section must include an autouse fixture example"
    )


def test_implementer_md_mentions_subagent_stop_marker_example() -> None:
    """Issue #1184: the new section must reference the #1176 subagent_stop_seen pattern."""
    content = _content()
    section_start = content.find(SECTION_HEADER)
    assert section_start != -1, f"Section header not found: {SECTION_HEADER}"

    next_section = content.find("\n## ", section_start + len(SECTION_HEADER))
    section_body = content[section_start:next_section] if next_section != -1 else content[section_start:]

    assert "subagent_stop_seen" in section_body, (
        "Section must contain the subagent_stop_seen marker example from Issue #1176"
    )


def test_implementer_md_section_appears_after_output_self_validation_and_before_error_recovery() -> None:
    """Issue #1184: new section must appear AFTER Output Self-Validation and BEFORE Error Recovery."""
    content = _content()

    self_val_pos = content.find(SELF_VALIDATION_HEADER)
    consec_run_pos = content.find(SECTION_HEADER)
    error_rec_pos = content.find(ERROR_RECOVERY_HEADER)

    assert self_val_pos != -1, f"Missing: {SELF_VALIDATION_HEADER}"
    assert consec_run_pos != -1, f"Missing: {SECTION_HEADER}"
    assert error_rec_pos != -1, f"Missing: {ERROR_RECOVERY_HEADER}"

    assert self_val_pos < consec_run_pos, (
        "Consecutive-Run section must appear AFTER Output Self-Validation section"
    )
    assert consec_run_pos < error_rec_pos, (
        "Consecutive-Run section must appear BEFORE Error Recovery section"
    )
