"""Unit tests for STEP 15 continuous improvement enforcement in implement.md.

TDD Red Phase: These tests validate structural properties of the implement command
to ensure STEP 15 enforcement is properly configured with HARD GATE, FORBIDDEN list,
cleanup ordering, and coordinator-level references.
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
def step15_section(implement_content: str) -> str:
    """Extract STEP 15 section content.

    The boundary lookahead requires `# ` to be followed by >= 2 consecutive
    uppercase letters (e.g. "# LIGHT PIPELINE MODE") so it matches real H1
    headings but not the `# Issue #1376: ...` bash comment that Issue #1376
    introduced inside STEP 15's cleanup code fence (that comment starts with
    "# I" — one uppercase letter followed by lowercase — so it no longer
    falsely terminates the match).
    """
    match = re.search(
        r"### STEP 15.*?(?=\n---|\n# [A-Z]{2,}|\Z)", implement_content, re.DOTALL
    )
    assert match, "STEP 15 section not found in implement.md"
    return match.group(0)


@pytest.fixture
def step13_section(implement_content: str) -> str:
    """Extract STEP 13 section content."""
    match = re.search(
        r"### STEP 13.*?(?=\n### STEP 14|\n---\s*\n### STEP 14|\Z)",
        implement_content,
        re.DOTALL,
    )
    assert match, "STEP 13 section not found in implement.md"
    return match.group(0)


@pytest.fixture
def coordinator_forbidden(implement_content: str) -> str:
    """Extract COORDINATOR FORBIDDEN LIST section.

    The section contains `####` subheadings (e.g. "#### Agent Management") that
    group its bullet items. The lookahead must stop only at the next top-level
    `###` heading (a real section boundary, e.g. "### Pipeline Progress
    Protocol"), not at those `####` subheadings — `\\n###(?!#)` requires the
    matched `###` NOT be followed by a 4th `#`, so `####` lines are skipped.
    """
    match = re.search(
        r"COORDINATOR FORBIDDEN LIST.*?(?=\nARGUMENTS|\n---|\n###(?!#))",
        implement_content,
        re.DOTALL,
    )
    assert match, "COORDINATOR FORBIDDEN LIST not found"
    return match.group(0)


@pytest.fixture
def continuous_improvement_section(implement_content: str) -> str:
    """Extract the Continuous Improvement HARD GATE section.

    Issue #1211 moved the continuous-improvement-analyst (CIA) dispatch from
    STEP 15 to STEP 12.5 (before the STEP 13 git commit), so that
    unified_pre_tool.py's agent-completeness gate is satisfied before the
    commit runs. STEP 15 is cleanup-only post-#1211 (see step15_section).
    This fixture is content-based (matches on "Continuous Improvement", not a
    hardcoded step number) so it survives future step renumbering.
    """
    match = re.search(
        r"### STEP \d+(?:\.\d+)?: Continuous Improvement.*?(?=\n### STEP|\Z)",
        implement_content,
        re.DOTALL,
    )
    assert match, "Continuous Improvement HARD GATE section not found in implement.md"
    return match.group(0)


@pytest.fixture
def quick_mode_section(implement_content: str) -> str:
    """Extract QUICK MODE section (removed in v3.50.0)."""
    match = re.search(r"# QUICK MODE.*?(?=\n# [A-Z]|\Z)", implement_content, re.DOTALL)
    if not match:
        pytest.skip("QUICK MODE section was removed from implement.md (quick mode deprecated)")
    return match.group(0)


class TestStep15HardGate:
    """The Continuous Improvement HARD GATE must have enforcement markers.

    Issue #1211 moved this gate from STEP 15 to STEP 12.5 (before the git
    commit) — see `continuous_improvement_section` fixture docstring. Tests
    below target that fixture rather than the (now cleanup-only) STEP 15.
    """

    def test_step15_contains_hard_gate(self, continuous_improvement_section: str):
        """The Continuous Improvement gate should contain a HARD GATE marker."""
        assert "HARD GATE" in continuous_improvement_section, (
            "Continuous Improvement section missing HARD GATE marker — "
            "enforcement requires explicit gate"
        )

    def test_step15_contains_forbidden_keyword(self, continuous_improvement_section: str):
        """The Continuous Improvement gate should contain FORBIDDEN keyword."""
        assert "FORBIDDEN" in continuous_improvement_section

    def test_step15_has_at_least_3_forbidden_items(
        self, continuous_improvement_section: str
    ):
        """The Continuous Improvement gate's FORBIDDEN block should list >= 3 items.

        Post-#1211 the FORBIDDEN block is written as a single prose paragraph
        ("MUST NOT X, MUST NOT Y, and MUST NOT Z") rather than a bulleted
        list — this matches the style used across most other STEP sections
        in implement.md (see e.g. STEP 8.5, STEP 10.5 FORBIDDEN blocks). Count
        "MUST NOT" clauses instead of bullet lines.
        """
        forbidden_match = re.search(
            r"\*\*FORBIDDEN\*\*.*", continuous_improvement_section, re.DOTALL
        )
        assert forbidden_match, "No FORBIDDEN block found in Continuous Improvement section"
        items = re.findall(r"MUST NOT", forbidden_match.group(0))
        assert len(items) >= 3, (
            f"Continuous Improvement FORBIDDEN block has only {len(items)} "
            "'MUST NOT' items, need >= 3"
        )

    def test_step15_contains_required_keyword(self, step15_section: str):
        """STEP 15 should contain REQUIRED keyword."""
        assert "REQUIRED" in step15_section


class TestStep15Content:
    """The Continuous Improvement gate must reference the right agent and execution model."""

    def test_step15_mentions_run_in_background(self, continuous_improvement_section: str):
        """The Continuous Improvement gate should mention run_in_background for
        non-blocking execution."""
        assert "run_in_background" in continuous_improvement_section, (
            "Continuous Improvement section should specify run_in_background "
            "for async execution"
        )

    def test_step15_mentions_analyst_agent(self, step15_section: str):
        """STEP 15 should reference the continuous-improvement-analyst agent."""
        assert "continuous-improvement-analyst" in step15_section


class TestCleanupOrdering:
    """Pipeline state cleanup must be in STEP 15, not STEP 13.

    Issue #1376 replaced the hardcoded `implement_pipeline_state.json`
    literal with a `get_legacy_sentinel_path()` lookup (per-repo sentinel
    resolution), so that literal string no longer appears anywhere in
    implement.md. `cleanup_pipeline(` — the function call that actually
    performs the cleanup — is the current signal for "pipeline state
    cleanup happens here".
    """

    def test_cleanup_not_in_step13(self, step13_section: str):
        """Cleanup (cleanup_pipeline() call) should NOT be in STEP 13."""
        assert "cleanup_pipeline(" not in step13_section, (
            "Cleanup should be moved from STEP 13 to STEP 15"
        )

    def test_cleanup_in_step15(self, step15_section: str):
        """Cleanup (cleanup_pipeline() call) should be in STEP 15."""
        assert "cleanup_pipeline(" in step15_section, (
            "STEP 15 should contain pipeline state cleanup"
        )


class TestCoordinatorForbiddenList:
    """Coordinator-level FORBIDDEN list must reference STEP 15."""

    def test_coordinator_forbidden_mentions_step15(self, coordinator_forbidden: str):
        """Coordinator FORBIDDEN list should include skipping STEP 15."""
        # Either "STEP 15" or "continuous improvement" should appear
        has_step15 = "STEP 15" in coordinator_forbidden
        has_ci = "continuous improvement" in coordinator_forbidden.lower()
        assert has_step15 or has_ci, (
            "COORDINATOR FORBIDDEN LIST must reference STEP 15 or continuous improvement"
        )


class TestQuickModeStep15:
    """QUICK MODE must also invoke STEP 15."""

    def test_quick_mode_mentions_step15(self, quick_mode_section: str):
        """QUICK MODE should reference STEP 15 or continuous improvement."""
        has_step15 = "STEP 15" in quick_mode_section or "step 15" in quick_mode_section.lower()
        has_ci = "continuous improvement" in quick_mode_section.lower()
        assert has_step15 or has_ci, (
            "QUICK MODE must invoke STEP 15 continuous improvement analysis"
        )

    def test_quick_mode_cleanup_after_step15(self, quick_mode_section: str):
        """In QUICK MODE, cleanup should appear AFTER STEP 15 reference."""
        step15_pos = quick_mode_section.lower().find("step 15")
        if step15_pos == -1:
            step15_pos = quick_mode_section.lower().find("continuous improvement")
        cleanup_pos = quick_mode_section.find("implement_pipeline_state.json")

        assert step15_pos != -1, "QUICK MODE missing STEP 15 reference"
        assert cleanup_pos != -1, "QUICK MODE missing cleanup"
        assert cleanup_pos > step15_pos, (
            "QUICK MODE cleanup must appear AFTER STEP 15 reference"
        )
