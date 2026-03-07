"""Unit tests for STEP 9 continuous improvement enforcement in implement.md.

TDD Red Phase: These tests validate structural properties of the implement command
to ensure STEP 9 enforcement is properly configured with HARD GATE, FORBIDDEN list,
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
def step9_section(implement_content: str) -> str:
    """Extract STEP 9 section content."""
    match = re.search(
        r"### STEP 9.*?(?=\n---|\n# |\Z)", implement_content, re.DOTALL
    )
    assert match, "STEP 9 section not found in implement.md"
    return match.group(0)


@pytest.fixture
def step8_section(implement_content: str) -> str:
    """Extract STEP 8 section content."""
    match = re.search(
        r"### STEP 8.*?(?=\n### STEP 9|\n---\s*\n### STEP 9|\Z)",
        implement_content,
        re.DOTALL,
    )
    assert match, "STEP 8 section not found in implement.md"
    return match.group(0)


@pytest.fixture
def coordinator_forbidden(implement_content: str) -> str:
    """Extract COORDINATOR FORBIDDEN LIST section."""
    match = re.search(
        r"COORDINATOR FORBIDDEN LIST.*?(?=\nARGUMENTS|\n---|\n###)",
        implement_content,
        re.DOTALL,
    )
    assert match, "COORDINATOR FORBIDDEN LIST not found"
    return match.group(0)


@pytest.fixture
def quick_mode_section(implement_content: str) -> str:
    """Extract QUICK MODE section (removed in v3.50.0)."""
    match = re.search(r"# QUICK MODE.*?(?=\n# [A-Z]|\Z)", implement_content, re.DOTALL)
    if not match:
        pytest.skip("QUICK MODE section was removed from implement.md (quick mode deprecated)")
    return match.group(0)


class TestStep9HardGate:
    """STEP 9 must have HARD GATE enforcement markers."""

    def test_step9_contains_hard_gate(self, step9_section: str):
        """STEP 9 should contain a HARD GATE marker."""
        assert "HARD GATE" in step9_section, (
            "STEP 9 missing HARD GATE marker — enforcement requires explicit gate"
        )

    def test_step9_contains_forbidden_keyword(self, step9_section: str):
        """STEP 9 should contain FORBIDDEN keyword."""
        assert "FORBIDDEN" in step9_section

    def test_step9_has_at_least_3_forbidden_items(self, step9_section: str):
        """STEP 9 FORBIDDEN list should have at least 3 items."""
        # Count lines starting with - or * after FORBIDDEN
        forbidden_match = re.search(
            r"FORBIDDEN.*?\n((?:\s*[-*].*\n){1,})", step9_section, re.DOTALL
        )
        assert forbidden_match, "No FORBIDDEN list items found in STEP 9"
        items = [
            line.strip()
            for line in forbidden_match.group(1).splitlines()
            if line.strip().startswith(("-", "*"))
        ]
        assert len(items) >= 3, (
            f"STEP 9 FORBIDDEN list has only {len(items)} items, need >= 3"
        )

    def test_step9_contains_required_keyword(self, step9_section: str):
        """STEP 9 should contain REQUIRED keyword."""
        assert "REQUIRED" in step9_section


class TestStep9Content:
    """STEP 9 must reference the right agent and execution model."""

    def test_step9_mentions_run_in_background(self, step9_section: str):
        """STEP 9 should mention run_in_background for non-blocking execution."""
        assert "run_in_background" in step9_section, (
            "STEP 9 should specify run_in_background for async execution"
        )

    def test_step9_mentions_analyst_agent(self, step9_section: str):
        """STEP 9 should reference the continuous-improvement-analyst agent."""
        assert "continuous-improvement-analyst" in step9_section


class TestCleanupOrdering:
    """Pipeline state cleanup must be in STEP 9, not STEP 8."""

    def test_cleanup_not_in_step8(self, step8_section: str):
        """Cleanup (rm implement_pipeline_state.json) should NOT be in STEP 8."""
        assert "implement_pipeline_state.json" not in step8_section, (
            "Cleanup should be moved from STEP 8 to STEP 9"
        )

    def test_cleanup_in_step9(self, step9_section: str):
        """Cleanup (rm implement_pipeline_state.json) should be in STEP 9."""
        assert "implement_pipeline_state.json" in step9_section, (
            "STEP 9 should contain pipeline state cleanup"
        )


class TestCoordinatorForbiddenList:
    """Coordinator-level FORBIDDEN list must reference STEP 9."""

    def test_coordinator_forbidden_mentions_step9(self, coordinator_forbidden: str):
        """Coordinator FORBIDDEN list should include skipping STEP 9."""
        # Either "STEP 9" or "continuous improvement" should appear
        has_step9 = "STEP 9" in coordinator_forbidden
        has_ci = "continuous improvement" in coordinator_forbidden.lower()
        assert has_step9 or has_ci, (
            "COORDINATOR FORBIDDEN LIST must reference STEP 9 or continuous improvement"
        )


class TestQuickModeStep9:
    """QUICK MODE must also invoke STEP 9."""

    def test_quick_mode_mentions_step9(self, quick_mode_section: str):
        """QUICK MODE should reference STEP 9 or continuous improvement."""
        has_step9 = "STEP 9" in quick_mode_section or "step 9" in quick_mode_section.lower()
        has_ci = "continuous improvement" in quick_mode_section.lower()
        assert has_step9 or has_ci, (
            "QUICK MODE must invoke STEP 9 continuous improvement analysis"
        )

    def test_quick_mode_cleanup_after_step9(self, quick_mode_section: str):
        """In QUICK MODE, cleanup should appear AFTER STEP 9 reference."""
        step9_pos = quick_mode_section.lower().find("step 9")
        if step9_pos == -1:
            step9_pos = quick_mode_section.lower().find("continuous improvement")
        cleanup_pos = quick_mode_section.find("implement_pipeline_state.json")

        assert step9_pos != -1, "QUICK MODE missing STEP 9 reference"
        assert cleanup_pos != -1, "QUICK MODE missing cleanup"
        assert cleanup_pos > step9_pos, (
            "QUICK MODE cleanup must appear AFTER STEP 9 reference"
        )
