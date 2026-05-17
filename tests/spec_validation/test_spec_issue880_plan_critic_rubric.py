"""Spec validation tests for Issue #880: objective scoring rubric in plan-critic agent.

Validates acceptance criteria:
1. Scoring rubric section with 5 levels defined for each axis
2. Scores table in each verdict template (PROCEED, REVISE, BLOCKED)
3. Verdict-score thresholds: PROCEED >= 3.0 (no axis <2), REVISE <3.0, BLOCKED <2.0
4. Delta tracking instruction for round 2+
5. Budget mode composite note
6. All existing content preserved (no deletions)
"""

from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[2]
PLAN_CRITIC_MD = PROJECT_ROOT / "plugins/autonomous-dev/agents/plan-critic.md"


@pytest.fixture(scope="module")
def content() -> str:
    """Read plan-critic.md content."""
    assert PLAN_CRITIC_MD.exists(), f"plan-critic.md not found at {PLAN_CRITIC_MD}"
    return PLAN_CRITIC_MD.read_text()


class TestRubricPresence:
    """AC1: Scoring rubric section with levels 1-5 for each axis."""

    def test_scoring_rubric_section_exists(self, content: str) -> None:
        """Scoring Rubric section MUST exist in plan-critic.md."""
        assert "## Scoring Rubric" in content, (
            "plan-critic.md must contain a '## Scoring Rubric' section"
        )

    def test_five_levels_defined(self, content: str) -> None:
        """All five score levels (1-5) MUST be defined in the rubric."""
        # The table defines levels 1 through 5
        for level in range(1, 6):
            assert f"| {level} |" in content, (
                f"Scoring rubric must define level {level}"
            )

    def test_level_1_is_critical_gap(self, content: str) -> None:
        """Level 1 MUST be labeled as a critical/blocking issue."""
        lower = content.lower()
        assert "critical gap" in lower or "blocking issue" in lower, (
            "Level 1 must be described as a critical gap or blocking issue"
        )

    def test_level_5_is_exemplary(self, content: str) -> None:
        """Level 5 MUST be labeled as exemplary."""
        lower = content.lower()
        assert "exemplary" in lower, "Level 5 must be described as exemplary"

    def test_all_axes_covered_by_rubric(self, content: str) -> None:
        """All five critique axes MUST be referenced in the rubric coverage statement."""
        lower = content.lower()
        assert "assumption audit" in lower, "Assumption Audit axis must be referenced"
        assert "scope creep" in lower, "Scope Creep Detection axis must be referenced"
        assert "existing solution search" in lower, (
            "Existing Solution Search axis must be referenced"
        )
        assert "minimalism pressure" in lower, "Minimalism Pressure axis must be referenced"
        assert "uncertainty flagging" in lower, "Uncertainty Flagging axis must be referenced"


class TestVerdictScoreMapping:
    """AC3: Verdict-score thresholds present and correct."""

    def test_verdict_score_mapping_section_exists(self, content: str) -> None:
        """Verdict-Score Mapping section MUST exist."""
        assert "## Verdict-Score Mapping" in content, (
            "plan-critic.md must contain a '## Verdict-Score Mapping' section"
        )

    def test_proceed_threshold_defined(self, content: str) -> None:
        """PROCEED threshold (>= 3.0, no axis below 2) MUST be defined."""
        assert ">= 3.0" in content or "≥ 3.0" in content, (
            "Verdict-Score Mapping must define PROCEED threshold as >= 3.0"
        )

    def test_no_axis_below_2_rule(self, content: str) -> None:
        """PROCEED MUST require no axis below 2."""
        lower = content.lower()
        assert "no axis below 2" in lower, (
            "Verdict-Score Mapping must state 'no axis below 2' for PROCEED"
        )

    def test_revise_threshold_defined(self, content: str) -> None:
        """REVISE threshold (< 3.0 or any axis at 1) MUST be defined."""
        assert "< 3.0" in content, (
            "Verdict-Score Mapping must define REVISE threshold as < 3.0"
        )
        lower = content.lower()
        assert "any axis at 1" in lower, (
            "Verdict-Score Mapping must specify REVISE when any axis at 1"
        )

    def test_blocked_threshold_defined(self, content: str) -> None:
        """BLOCKED threshold (< 2.0 or 2+ axes at 1) MUST be defined."""
        assert "< 2.0" in content, (
            "Verdict-Score Mapping must define BLOCKED threshold as < 2.0"
        )
        lower = content.lower()
        assert "2+ axes at 1" in lower, (
            "Verdict-Score Mapping must specify BLOCKED when 2+ axes at 1"
        )


class TestScoresTableInVerdicts:
    """AC2: Scores table present in each verdict template."""

    def test_scores_table_in_revise_verdict(self, content: str) -> None:
        """REVISE verdict template MUST include a Scores table."""
        revise_start = content.find("### REVISE")
        proceed_start = content.find("### PROCEED")
        assert revise_start != -1, "REVISE verdict section not found"
        assert proceed_start != -1, "PROCEED verdict section not found"
        revise_section = content[revise_start:proceed_start]
        assert "### Scores" in revise_section, (
            "REVISE verdict template must include a '### Scores' table"
        )

    def test_scores_table_in_proceed_verdict(self, content: str) -> None:
        """PROCEED verdict template MUST include a Scores table."""
        proceed_start = content.find("### PROCEED")
        blocked_start = content.find("### BLOCKED")
        assert proceed_start != -1, "PROCEED verdict section not found"
        assert blocked_start != -1, "BLOCKED verdict section not found"
        proceed_section = content[proceed_start:blocked_start]
        assert "### Scores" in proceed_section, (
            "PROCEED verdict template must include a '### Scores' table"
        )

    def test_scores_table_in_blocked_verdict(self, content: str) -> None:
        """BLOCKED verdict template MUST include a Scores table."""
        blocked_start = content.find("### BLOCKED")
        delta_start = content.find("## Delta Tracking")
        assert blocked_start != -1, "BLOCKED verdict section not found"
        assert delta_start != -1, "Delta Tracking section not found"
        blocked_section = content[blocked_start:delta_start]
        assert "### Scores" in blocked_section, (
            "BLOCKED verdict template must include a '### Scores' table"
        )

    def test_composite_row_present(self, content: str) -> None:
        """Each Scores table MUST include a Composite row."""
        assert "**Composite**" in content, (
            "Scores table must contain a '**Composite**' row"
        )


class TestDeltaTracking:
    """AC4: Delta tracking instruction for round 2+."""

    def test_delta_tracking_section_exists(self, content: str) -> None:
        """Delta Tracking section MUST exist in plan-critic.md."""
        assert "## Delta Tracking" in content, (
            "plan-critic.md must contain a '## Delta Tracking' section"
        )

    def test_delta_column_instruction(self, content: str) -> None:
        """Delta column MUST be described for round 2+ usage."""
        lower = content.lower()
        assert "delta column" in lower, (
            "Delta Tracking section must mention adding a 'delta column'"
        )

    def test_prior_round_reference(self, content: str) -> None:
        """Delta tracking MUST reference prior round scores."""
        lower = content.lower()
        assert "prior round" in lower, (
            "Delta Tracking section must reference prior round scores"
        )


class TestBudgetModeCompatibility:
    """AC5: Budget mode composite note present."""

    def test_budget_mode_note_present(self, content: str) -> None:
        """Budget mode scoring note MUST be present in the rubric."""
        lower = content.lower()
        assert "budget mode" in lower, (
            "Scoring Rubric must include a budget mode note"
        )

    def test_budget_mode_axes_specified(self, content: str) -> None:
        """Budget mode MUST specify which axes are evaluated."""
        lower = content.lower()
        # Budget mode uses 3 axes: Assumption Audit, Existing Solution Search, Minimalism Pressure
        assert "assumption audit" in lower, (
            "Budget mode must reference Assumption Audit axis"
        )
        assert "existing solution search" in lower, (
            "Budget mode must reference Existing Solution Search axis"
        )
        assert "minimalism pressure" in lower, (
            "Budget mode must reference Minimalism Pressure axis"
        )


class TestExistingContentCompatibility:
    """AC6: All existing content preserved — 855-relevant strings still present."""

    def test_mission_section_preserved(self, content: str) -> None:
        """Mission section MUST still be present."""
        assert "## Mission" in content, "Mission section must be preserved"

    def test_hard_gate_minimum_rounds_preserved(self, content: str) -> None:
        """HARD GATE: Minimum Critique Rounds section MUST still be present."""
        # Accepts either '2' or '3' — the specific round count may be updated
        assert ("HARD GATE: Minimum 2 Critique Rounds" in content
                or "HARD GATE: Minimum 3 Critique Rounds" in content), (
            "HARD GATE minimum critique rounds section must be preserved"
        )

    def test_critique_axes_section_preserved(self, content: str) -> None:
        """Critique Axes section MUST still be present."""
        assert "## Critique Axes" in content, "Critique Axes section must be preserved"

    def test_forbidden_behaviors_section_preserved(self, content: str) -> None:
        """FORBIDDEN Behaviors section MUST still be present."""
        assert "## FORBIDDEN Behaviors" in content, (
            "FORBIDDEN Behaviors section must be preserved"
        )

    def test_proceed_must_not_before_minimum_rounds_preserved(self, content: str) -> None:
        """Original FORBIDDEN rule about PROCEED before minimum rounds MUST still be present."""
        # Accepts either the original 'first critique round' phrasing or the updated '3 critique rounds' phrasing
        assert ("MUST NOT issue PROCEED on the first critique round" in content
                or "MUST NOT issue PROCEED before completing" in content), (
            "Original FORBIDDEN rule about issuing PROCEED prematurely must be preserved"
        )
