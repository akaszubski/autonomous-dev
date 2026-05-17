"""Regression tests for Issue #1067 — Operational Integration Test axis in plan-critic."""

from pathlib import Path
import pytest

PLAN_CRITIC_PATH = Path(__file__).resolve().parents[2] / "plugins" / "autonomous-dev" / "agents" / "plan-critic.md"


@pytest.fixture(scope="module")
def content() -> str:
    return PLAN_CRITIC_PATH.read_text()


class TestOperationalAxisPresence:
    def test_operational_integration_test_axis_listed(self, content):
        assert "Operational Integration Test" in content

    def test_axis_count_updated_to_six(self, content):
        # Tolerate "six axes" or "6 axes"
        assert ("six axes" in content) or ("6 axes" in content)

    def test_axis_description_mentions_subprocess(self, content):
        # Pull the axis description block
        marker = "Operational Integration Test"
        idx = content.index(marker)
        # Look at next 1200 chars after first mention for axis description
        window = content[idx:idx + 1200]
        assert "subprocess" in window.lower()

    def test_axis_description_mentions_cwd_or_env(self, content):
        marker = "Operational Integration Test"
        idx = content.index(marker)
        window = content[idx:idx + 1200]
        assert ("cwd" in window.lower()) or ("CWD" in window) or ("environment variable" in window.lower())


class TestScoringAnchorRow:
    def test_anchor_table_includes_operational_row(self, content):
        # The scoring anchors table row contains the axis name on a row separator
        # Find the second-or-later occurrence to confirm it's in the table, not just intro
        assert content.count("Operational Integration Test") >= 3  # axis def + budget mode + anchor row + verdict tables


class TestVerdictTemplatesIncludeAxis:
    def test_all_verdict_templates_have_axis_score_row(self, content):
        # The axis should appear in ALL THREE verdict-template Scores tables (REVISE/PROCEED/BLOCKED)
        # We check that the axis appears at least 6 times overall (intro + budget + anchor + 3 verdict templates + delta)
        assert content.count("Operational Integration Test") >= 6


class TestBudgetModeUpdated:
    def test_budget_mode_lists_four_axes(self, content):
        budget_idx = content.lower().index("budget mode")
        window = content[budget_idx:budget_idx + 500]
        assert ("four axes" in window.lower()) or ("4 axes" in window.lower())

    def test_budget_mode_includes_operational_axis(self, content):
        budget_idx = content.lower().index("budget mode")
        window = content[budget_idx:budget_idx + 500]
        assert "Operational Integration Test" in window


class TestPriorAxesPreserved:
    @pytest.mark.parametrize("axis", [
        "Assumption Audit",
        "Scope Creep Detection",
        "Existing Solution Search",
        "Minimalism Pressure",
        "Uncertainty Flagging",
    ])
    def test_prior_axis_still_present(self, axis, content):
        assert axis in content, f"Prior axis {axis!r} must remain in plan-critic.md"

    def test_verdict_score_thresholds_unchanged(self, content):
        # The verdict-score mapping table should still mention >= 3.0
        assert ">= 3.0" in content or "≥ 3.0" in content


class TestForbiddenListUpdated:
    def test_forbidden_bullet_added_for_operational_axis(self, content):
        # The FORBIDDEN list should include a bullet about not skipping the operational axis
        lower = content.lower()
        assert "operational integration test" in lower
        # And specifically about NOT skipping
        assert "MUST NOT skip" in content and "Operational Integration Test" in content
