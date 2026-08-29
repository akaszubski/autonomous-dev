"""Regression tests for plan-critic.md axis content (Issue #1172).

Locks the Assumption Audit axis tool-use mandate in place. If a future
edit removes the REQUIRED clause or weakens the score-3 anchor, these
tests fail.

Also locks the Reachability & Enforceability axis (axis 7) and the
read-only Serena symbol-tool grants that axis depends on. A criterion its
holder cannot check is a guard that cannot refuse, so the axis text and
the frontmatter grants must not drift apart.
"""

import re
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[2]
PLAN_CRITIC = ROOT / "plugins" / "autonomous-dev" / "agents" / "plan-critic.md"

# Read-only symbol tools the reachability criteria require.
REQUIRED_SERENA_TOOLS = (
    "mcp__serena__find_symbol",
    "mcp__serena__find_referencing_symbols",
    "mcp__serena__get_symbols_overview",
)

# Serena tools that mutate source or the filesystem. plan-critic is a
# read-only adversarial reviewer and must never declare one of these.
FORBIDDEN_WRITE_TOOLS = (
    "mcp__serena__replace_symbol_body",
    "mcp__serena__insert_after_symbol",
    "mcp__serena__insert_before_symbol",
    "mcp__serena__rename_symbol",
    "mcp__serena__safe_delete_symbol",
    "mcp__serena__replace_in_files",
    "mcp__serena__replace_content",
    "mcp__serena__write_memory",
    "mcp__serena__execute_shell_command",
    "Write",
    "Edit",
    "MultiEdit",
    "NotebookEdit",
)


def _read() -> str:
    return PLAN_CRITIC.read_text(encoding="utf-8")


def _declared_tools() -> list[str]:
    """Return the ``tools:`` list from plan-critic.md frontmatter."""
    content = _read()
    parts = content.split("---", 2)
    assert len(parts) >= 3, "plan-critic.md frontmatter is not terminated"
    frontmatter = yaml.safe_load(parts[1])
    assert isinstance(frontmatter, dict), "plan-critic.md frontmatter is not a mapping"
    tools = frontmatter.get("tools")
    assert isinstance(tools, list), f"plan-critic.md tools: must be a list, got {tools!r}"
    return [str(t).strip() for t in tools]


def _critique_axes_section(text: str) -> str:
    """Return the '## Critique Axes' section body."""
    m = re.search(r"##\s*Critique Axes\s*\n(.*?)(?=\n##\s)", text, re.DOTALL)
    assert m, "plan-critic.md missing '## Critique Axes' section"
    return m.group(1)


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


class TestSerenaSymbolToolGrants:
    """plan-critic must hold the read-only instruments its criteria require."""

    @pytest.mark.parametrize("tool", REQUIRED_SERENA_TOOLS)
    def test_required_serena_tool_is_granted(self, tool: str):
        tools = _declared_tools()
        assert tool in tools, (
            f"plan-critic.md must grant {tool!r} — the Reachability & "
            f"Enforceability axis and the Assumption Audit instrument-adequacy "
            f"check both require symbol-level verification, which grep cannot "
            f"perform. Declared: {tools}"
        )

    def test_pre_existing_tools_preserved(self):
        """Additive only: the original tool grants must survive.

        The web-search grant is the one deliberate SUBSTITUTION rather than a
        loss: ``WebSearch`` needs Anthropic's hosted service and is a no-op
        here, so the Existing Solution Search criterion is now carried by
        ``mcp__searxng__search``. The capability is preserved; the carrier
        changed. Every other grant is unchanged.
        """
        tools = _declared_tools()
        for tool in ("mcp__searxng__search", "Read", "Grep", "Glob", "Bash"):
            assert tool in tools, f"plan-critic.md lost pre-existing tool {tool!r}"

        assert "WebSearch" not in tools, (
            "plan-critic.md re-declared WebSearch. It is a no-op in this "
            "environment; use mcp__searxng__search."
        )

    @pytest.mark.parametrize("tool", FORBIDDEN_WRITE_TOOLS)
    def test_no_write_capable_tool_is_granted(self, tool: str):
        """Negative control: the reviewer stays read-only.

        The grant-side test above is only meaningful if the file could also
        fail — a rule that accepted every tool list would pass it vacuously.
        This watches the same declaration refuse write capability.
        """
        content = _read()
        parts = content.split("---", 2)
        frontmatter = yaml.safe_load(parts[1])
        declared = set(_declared_tools()) | {
            str(t).strip() for t in (frontmatter.get("optional_mcp") or [])
        }
        assert tool not in declared, (
            f"plan-critic.md declares write-capable tool {tool!r}. plan-critic "
            f"is a read-only adversarial reviewer and MUST NOT hold mutation "
            f"capability."
        )


class TestReachabilityAxis:
    """Axis 7 (Reachability & Enforceability) must exist and stay substantive."""

    def test_axis_7_is_listed_in_critique_axes(self):
        axes = _critique_axes_section(_read())
        assert re.search(
            r"^\s*7\.\s*\*\*Reachability & Enforceability\*\*", axes, re.MULTILINE
        ), (
            "plan-critic.md must list 'Reachability & Enforceability' as "
            "numbered axis 7 in the ## Critique Axes section"
        )

    def test_axis_7_covers_all_five_probes(self):
        axes = _critique_axes_section(_read())
        m = re.search(
            r"7\.\s*\*\*Reachability & Enforceability\*\*(.*)", axes, re.DOTALL
        )
        assert m, "Could not extract the Reachability & Enforceability axis block"
        block = m.group(1).lower()
        for probe in (
            "consumer",       # dead-on-arrival check
            "fire",           # inert-threshold check
            "class",          # class-vs-instance scoping check
            "did not run",    # success-by-doing-nothing check
            "both",           # watched-both-ways check
        ):
            assert probe in block, (
                f"Reachability & Enforceability axis must address {probe!r}; "
                f"the axis block does not mention it"
            )

    def test_axis_7_is_scored_and_anchored(self):
        content = _read()
        assert re.search(
            r"^\|\s*Reachability & Enforceability\s*\|", content, re.MULTILINE
        ), (
            "Scoring Anchors table must include a 'Reachability & Enforceability' row"
        )
        # One anchors row + REVISE/PROCEED/BLOCKED score tables + Delta table.
        rows = re.findall(
            r"^\|\s*Reachability & Enforceability\s*\|", content, re.MULTILINE
        )
        assert len(rows) >= 5, (
            f"Expected the axis in the Scoring Anchors table, all three verdict "
            f"templates, and the Delta Tracking template (>= 5 rows); found "
            f"{len(rows)}"
        )

    def test_axis_7_named_in_rubric_coverage_statement(self):
        content = _read()
        assert "Reachability & Enforceability" in content.split("## Scoring Rubric")[1].split("## Verdict-Score Mapping")[0], (
            "The Scoring Rubric coverage sentence must name the "
            "Reachability & Enforceability axis"
        )
