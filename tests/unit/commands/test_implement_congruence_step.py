"""Unit tests for STEP 8.5 documentation congruence validation in implement.md.

TDD Red Phase: These tests validate that implement.md has a STEP 8.5 section
for documentation congruence validation between STEP 8 (Report and Finalize)
and STEP 9 (Continuous Improvement Analysis).

Issue #393: Add STEP 8.5 for documentation congruence validation.
"""

import re
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).parent.parent.parent.parent
IMPLEMENT_MD = PROJECT_ROOT / "plugins" / "autonomous-dev" / "commands" / "implement.md"


@pytest.fixture
def implement_content() -> str:
    """Load implement.md content."""
    assert IMPLEMENT_MD.exists(), f"implement.md not found at {IMPLEMENT_MD}"
    return IMPLEMENT_MD.read_text()


@pytest.fixture
def step_8_5_section(implement_content: str) -> str:
    """Extract STEP 8.5 section content.

    Matches '### STEP 8.5' heading up to the next step heading or end of file.
    """
    match = re.search(
        r"### STEP 8\.5.*?(?=\n### STEP [0-9]|\n---\s*\n### STEP|\n# [A-Z]|\Z)",
        implement_content,
        re.DOTALL,
    )
    assert match, (
        "STEP 8.5 section not found in implement.md. "
        "Expected a '### STEP 8.5' heading for documentation congruence validation."
    )
    return match.group(0)


class TestStep85Exists:
    """STEP 8.5 must exist in implement.md."""

    def test_implement_has_step_8_5(self, implement_content: str):
        """implement.md must contain a STEP 8.5 section.

        STEP 8.5 is the documentation congruence validation step that runs
        between STEP 8 (Report and Finalize) and STEP 9 (Continuous Improvement).
        """
        assert "STEP 8.5" in implement_content, (
            "implement.md is missing STEP 8.5 for documentation congruence validation. "
            "This step should be added between STEP 8 and STEP 9."
        )


class TestStep85Content:
    """STEP 8.5 must reference documentation congruence tests."""

    def test_step_8_5_runs_congruence_tests(self, step_8_5_section: str):
        """STEP 8.5 must reference test_documentation_congruence.py.

        The step should invoke or mention the congruence test file that validates
        documentation matches implementation.
        """
        assert "test_documentation_congruence" in step_8_5_section, (
            "STEP 8.5 does not reference test_documentation_congruence.py. "
            "This test file validates that docs match code and must be invoked in STEP 8.5."
        )


class TestStep85Ordering:
    """STEP 8.5 must appear between STEP 8 and STEP 9."""

    def test_step_8_5_between_8_and_9(self, implement_content: str):
        """STEP 8.5 must appear AFTER STEP 8 and BEFORE STEP 9 in implement.md.

        The ordering is critical: STEP 8 finalizes the report, STEP 8.5 validates
        documentation congruence, and STEP 9 runs continuous improvement analysis.
        """
        step8_pos = implement_content.find("### STEP 8:")
        if step8_pos == -1:
            step8_pos = implement_content.find("### STEP 8")
        step8_5_pos = implement_content.find("STEP 8.5")
        step9_pos = implement_content.find("### STEP 9")

        assert step8_pos != -1, "STEP 8 not found in implement.md"
        assert step8_5_pos != -1, "STEP 8.5 not found in implement.md"
        assert step9_pos != -1, "STEP 9 not found in implement.md"

        assert step8_pos < step8_5_pos, (
            f"STEP 8.5 (pos {step8_5_pos}) must appear AFTER STEP 8 (pos {step8_pos})"
        )
        assert step8_5_pos < step9_pos, (
            f"STEP 8.5 (pos {step8_5_pos}) must appear BEFORE STEP 9 (pos {step9_pos})"
        )


class TestStep85HardGate:
    """STEP 8.5 must be a HARD GATE (blocks pipeline on failure)."""

    def test_step_8_5_is_hard_gate(self, step_8_5_section: str):
        """STEP 8.5 must contain 'HARD GATE' text.

        Documentation congruence failures should block the pipeline, not be
        advisory. The HARD GATE designation ensures the coordinator cannot
        skip past congruence failures.
        """
        assert "HARD GATE" in step_8_5_section, (
            "STEP 8.5 is missing HARD GATE designation. "
            "Documentation congruence validation must block on failure, "
            "not be an optional or advisory step."
        )
