"""Regression tests for Issue #1067 — Operational Integration Test axis in plan-critic."""

import pytest

from tests.helpers.plan_critic_axes import (
    PLAN_CRITIC_PATH,
    count_numbered_axes,
    critique_axes_section,
    stated_axis_counts,
)


@pytest.fixture(scope="module")
def content() -> str:
    return PLAN_CRITIC_PATH.read_text()


class TestOperationalAxisPresence:
    def test_operational_integration_test_axis_listed(self, content):
        assert "Operational Integration Test" in content

    def test_stated_axis_count_matches_live_axis_list(self, content):
        """Every full-roster axis count in the prose must equal the live list.

        The original form of this assertion hardcoded "six axes"/"6 axes".
        A hardcoded count is a guard scoped to the instance: it went stale the
        moment axis 7 (Reachability & Enforceability) landed and then blocked
        the very change it was meant to check. The intent — the file's prose
        must not lie about how many axes exist — is preserved by deriving the
        expected number from the ``## Critique Axes`` list.

        Subjects are discovered by scanning the file, not from a list fixed
        here, so a stale count written into a new sentence fails too.
        """
        expected = count_numbered_axes(critique_axes_section(content))
        statements = stated_axis_counts(content)

        assert statements, (
            "plan-critic.md states no full-roster axis count anywhere. The "
            "prose must tell the reader how many critique axes there are; a "
            "check that finds nothing to compare passes by doing nothing."
        )

        mismatched = [
            (lineno, stated, line)
            for lineno, stated, line in statements
            if stated != expected
        ]
        assert not mismatched, (
            f"plan-critic.md lists {expected} numbered critique axes, but "
            f"these prose statements disagree:\n"
            + "\n".join(
                f"  line {lineno}: says {stated} — {line[:120]!r}"
                for lineno, stated, line in mismatched
            )
            + "\nUpdate every stated count when adding or removing an axis."
        )

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
