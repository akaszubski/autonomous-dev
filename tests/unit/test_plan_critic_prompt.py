"""Regression tests for plan-critic.md axis content (Issue #1172).

Locks the Assumption Audit axis tool-use mandate in place. If a future
edit removes the REQUIRED clause or weakens the score-3 anchor, these
tests fail.
"""

import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
PLAN_CRITIC = ROOT / "plugins" / "autonomous-dev" / "agents" / "plan-critic.md"


def _read() -> str:
    return PLAN_CRITIC.read_text(encoding="utf-8")


def _assumption_audit_block(text: str) -> str:
    """Extract the prose block for axis #1 (between heading 1 and heading 2)."""
    m = re.search(
        r"^1\. \*\*Assumption Audit\*\*.*?(?=^2\. \*\*Scope Creep Detection\*\*)",
        text,
        re.MULTILINE | re.DOTALL,
    )
    assert m, "Assumption Audit axis block not found in plan-critic.md"
    return m.group(0)


def _assumption_audit_anchor_row(text: str) -> list[str]:
    """Extract Assumption Audit row from the Scoring Anchors table, return cells."""
    m = re.search(r"^\| Assumption Audit \|.*$", text, re.MULTILINE)
    assert m, "Assumption Audit row not found in Scoring Anchors table"
    cells = [c.strip() for c in m.group(0).split("|") if c.strip()]
    # Expected: 4 cells — axis name, score-1, score-3, score-5
    assert len(cells) == 4, f"Expected 4 cells in anchor row, got {len(cells)}: {cells}"
    return cells


class TestAssumptionAuditToolUseMandate:
    """Issue #1172: Assumption Audit must require tool-use to verify factual claims."""

    def test_axis_block_contains_required_keyword(self):
        block = _assumption_audit_block(_read())
        assert "REQUIRED" in block, (
            "Assumption Audit axis must contain literal 'REQUIRED' marking the "
            "tool-use mandate (Issue #1172)"
        )

    def test_axis_block_mentions_factual_claim_verification(self):
        block = _assumption_audit_block(_read())
        # Must mention factual claims AND at least one tool (Grep/Glob/Read/Bash)
        assert re.search(r"factual\s+claim", block, re.IGNORECASE), (
            "Assumption Audit axis must mention 'factual claim' verification"
        )
        assert re.search(r"\b(Grep|Glob|Read|Bash)\b", block), (
            "Assumption Audit axis must reference at least one verification tool "
            "(Grep, Glob, Read, or Bash)"
        )

    def test_axis_block_caps_unverified_claims_at_score_2(self):
        block = _assumption_audit_block(_read())
        # Look for cap language: 'cap' + '2' in proximity
        assert re.search(r"cap[s]?\b.*\b2\b", block, re.IGNORECASE | re.DOTALL), (
            "Assumption Audit axis must state that unverified factual claims cap "
            "the score at 2"
        )


class TestScoringAnchorRow:
    """Issue #1172: Score-3 anchor for Assumption Audit must require tool calls."""

    def test_score3_cell_requires_tool_verification(self):
        cells = _assumption_audit_anchor_row(_read())
        # cells = [axis_name, score-1, score-3, score-5]
        score3 = cells[2]
        # Must mention a tool name (Grep/Read/Bash/tool call) AND 'verif'
        assert re.search(r"\b(Grep|Read|Bash|tool call)\b", score3, re.IGNORECASE), (
            f"Score-3 anchor must mention a tool (Grep/Read/Bash/tool call). "
            f"Got: {score3!r}"
        )
        assert re.search(r"verif", score3, re.IGNORECASE), (
            f"Score-3 anchor must contain a 'verif*' word indicating verification. "
            f"Got: {score3!r}"
        )

    def test_score1_anchor_grep_phrase_preserved(self):
        """Anti-regression: don't weaken the score-1 anchor."""
        cells = _assumption_audit_anchor_row(_read())
        score1 = cells[1]
        assert "grep shows it doesn't" in score1, (
            f"Score-1 anchor must still contain 'grep shows it doesn't' "
            f"(anti-regression). Got: {score1!r}"
        )
