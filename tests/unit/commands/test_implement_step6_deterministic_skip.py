"""Unit tests for Issue #981: STEP 6 deterministic-skip variant in implement.md.

These tests verify that implement.md documents the explicit "all criteria deterministic"
skip case for STEP 6, and that the continuous-improvement-analyst agent correctly
excludes this case from its false-positive detection.
"""

from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[3]
IMPLEMENT_MD = PROJECT_ROOT / "plugins" / "autonomous-dev" / "commands" / "implement.md"
CIA_MD = PROJECT_ROOT / "plugins" / "autonomous-dev" / "agents" / "continuous-improvement-analyst.md"


def test_deterministic_skip_log_line_present() -> None:
    """implement.md MUST contain the deterministic-skip STEP 6 log line.

    The fourth recognized skip variant must be documented in the Required
    Skip/Execute Logging block so coordinators know to emit it when every
    acceptance criterion is classified as deterministic.
    """
    assert IMPLEMENT_MD.exists(), f"implement.md not found at {IMPLEMENT_MD}"
    content = IMPLEMENT_MD.read_text(encoding="utf-8")
    assert "STEP 6: SKIPPED (all criteria classified deterministic" in content, (
        "implement.md is missing the deterministic-skip log line for STEP 6. "
        "Expected: 'STEP 6: SKIPPED (all criteria classified deterministic — N/N tests written by implementer in STEP 5/8)'"
    )


def test_executed_zero_not_sole_option() -> None:
    """implement.md MUST NOT contain a bare 'EXECUTED (0 acceptance tests generated)' line.

    When all criteria are deterministic the correct output is the SKIPPED variant,
    not EXECUTED with a zero count.  The bare zero-execution string should not
    appear as a recognized log line (it would signal a misconfigured run, not a
    valid skip).
    """
    assert IMPLEMENT_MD.exists(), f"implement.md not found at {IMPLEMENT_MD}"
    content = IMPLEMENT_MD.read_text(encoding="utf-8")
    assert "EXECUTED (0 acceptance tests generated)" not in content, (
        "implement.md must not define 'EXECUTED (0 acceptance tests generated)' as a "
        "valid outcome. Use the deterministic-skip variant instead."
    )


def test_cia_known_fp_covers_deterministic_skip() -> None:
    """The CIA agent file MUST document the deterministic-skip case as a known false positive.

    Without this entry the CIA agent would file spurious issues whenever a pipeline
    run legitimately skips STEP 6 because all criteria were deterministic.
    """
    assert CIA_MD.exists(), f"continuous-improvement-analyst.md not found at {CIA_MD}"
    content = CIA_MD.read_text(encoding="utf-8")
    assert "all criteria classified deterministic" in content, (
        "continuous-improvement-analyst.md is missing the 'all criteria classified deterministic' "
        "entry in its Known False Positives section."
    )


def test_cia_ghost_criteria_requires_no_log_line() -> None:
    """The CIA agent file MUST specify 'no STEP 6 log line appears at all' as a trigger condition.

    The false-positive guidance must tell the analyst WHEN to flag STEP 6 as a problem
    (no log line at all), so it can distinguish missing-step from valid deterministic skip.
    """
    assert CIA_MD.exists(), f"continuous-improvement-analyst.md not found at {CIA_MD}"
    content = CIA_MD.read_text(encoding="utf-8")
    assert "no STEP 6 log line appears at all" in content, (
        "continuous-improvement-analyst.md must state 'no STEP 6 log line appears at all' "
        "as the condition under which STEP 6 absence is a real problem."
    )
