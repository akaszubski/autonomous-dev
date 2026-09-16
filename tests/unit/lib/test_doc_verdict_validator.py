"""Tests for doc_verdict_validator module (Issue #602).

Validates the reusable DOC-DRIFT-VERDICT parser that the coordinator
uses to check doc-master output.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

# Ensure lib is importable
PROJECT_ROOT = Path(__file__).resolve().parents[3]
LIB_PATH = PROJECT_ROOT / "plugins" / "autonomous-dev" / "lib"
if str(LIB_PATH) not in sys.path:
    sys.path.insert(0, str(LIB_PATH))

from doc_verdict_validator import DocVerdictResult, validate_doc_verdict

PLUGIN_ROOT = PROJECT_ROOT / "plugins" / "autonomous-dev"
DOC_MASTER_AGENT_PATH = PLUGIN_ROOT / "agents" / "doc-master.md"
IMPLEMENT_CMD_PATH = PLUGIN_ROOT / "commands" / "implement.md"
IMPLEMENT_FIX_CMD_PATH = PLUGIN_ROOT / "commands" / "implement-fix.md"

# Issue #1773: the three tokens the dispatch templates used to request.
RETIRED_VERDICT_TOKENS = ("DOCS-UPDATED", "NO-UPDATE-NEEDED", "DOCS-DRIFT-FOUND")


class TestDocVerdictValidator:
    """Tests for validate_doc_verdict function."""

    def test_pass_verdict_found(self):
        """Output ending with DOC-DRIFT-VERDICT: PASS is correctly parsed."""
        output = (
            "Checked 5 docs, fixed 2.\n"
            "docs-checked: 5\n"
            "docs-fixed: 2\n"
            "DOC-DRIFT-VERDICT: PASS"
        )
        result = validate_doc_verdict(output)
        assert result.found is True
        assert result.verdict == "PASS"
        assert result.finding_count == 0
        assert result.raw_line == "DOC-DRIFT-VERDICT: PASS"
        assert result.position_warning == ""

    def test_fail_verdict_with_count(self):
        """Output ending with DOC-DRIFT-VERDICT: FAIL(3) is correctly parsed."""
        output = (
            "Found 3 unfixable findings.\n"
            "DOC-DRIFT-VERDICT: FAIL(3)"
        )
        result = validate_doc_verdict(output)
        assert result.found is True
        assert result.verdict == "FAIL"
        assert result.finding_count == 3
        assert result.raw_line == "DOC-DRIFT-VERDICT: FAIL(3)"
        assert result.position_warning == ""

    def test_fail_verdict_without_count(self):
        """DOC-DRIFT-VERDICT: FAIL (no parentheses) is treated as FAIL with count=-1."""
        output = "DOC-DRIFT-VERDICT: FAIL"
        result = validate_doc_verdict(output)
        assert result.found is True
        assert result.verdict == "FAIL"
        assert result.finding_count == -1
        assert result.raw_line == "DOC-DRIFT-VERDICT: FAIL"

    def test_verdict_not_found(self):
        """Output with no verdict line returns found=False."""
        output = (
            "Checked 5 docs, fixed 2.\n"
            "All good, nothing to report.\n"
        )
        result = validate_doc_verdict(output)
        assert result.found is False
        assert result.verdict == ""
        assert result.finding_count == 0
        assert result.raw_line == ""

    def test_verdict_not_last_line(self):
        """Verdict exists but is not the last non-empty line sets position_warning."""
        output = (
            "DOC-DRIFT-VERDICT: PASS\n"
            "Some extra text after the verdict.\n"
        )
        result = validate_doc_verdict(output)
        assert result.found is True
        assert result.verdict == "PASS"
        assert result.position_warning != ""
        assert "last" in result.position_warning.lower()

    def test_empty_output(self):
        """Empty string returns found=False."""
        result = validate_doc_verdict("")
        assert result.found is False
        assert result.verdict == ""
        assert result.finding_count == 0

    def test_whitespace_only_output(self):
        """Whitespace-only output returns found=False."""
        result = validate_doc_verdict("   \n\n  \t  \n")
        assert result.found is False
        assert result.verdict == ""

    def test_verdict_in_code_block(self):
        """Verdict inside a markdown code block is still found."""
        output = (
            "```\n"
            "DOC-DRIFT-VERDICT: PASS\n"
            "```"
        )
        result = validate_doc_verdict(output)
        assert result.found is True
        assert result.verdict == "PASS"
        # Position warning because ``` is the last non-empty line
        assert result.position_warning != ""

    def test_multiple_verdicts(self):
        """When multiple verdict lines exist, the last one is used."""
        output = (
            "DOC-DRIFT-VERDICT: FAIL(2)\n"
            "After fixing, re-checked:\n"
            "DOC-DRIFT-VERDICT: PASS"
        )
        result = validate_doc_verdict(output)
        assert result.found is True
        assert result.verdict == "PASS"
        assert result.finding_count == 0
        assert result.position_warning == ""

    def test_fail_zero_is_pass(self):
        """FAIL(0) is treated as PASS since zero findings means passing."""
        output = "DOC-DRIFT-VERDICT: FAIL(0)"
        result = validate_doc_verdict(output)
        assert result.found is True
        assert result.verdict == "PASS"
        assert result.finding_count == 0

    def test_fail_non_numeric(self):
        """FAIL(abc) is treated as FAIL with finding_count=-1 (parse error)."""
        output = "DOC-DRIFT-VERDICT: FAIL(abc)"
        result = validate_doc_verdict(output)
        assert result.found is True
        assert result.verdict == "FAIL"
        assert result.finding_count == -1

    def test_ansi_escape_codes(self):
        """Verdict with ANSI escape codes is stripped and parsed correctly."""
        output = "\x1b[32mDOC-DRIFT-VERDICT: PASS\x1b[0m"
        result = validate_doc_verdict(output)
        assert result.found is True
        assert result.verdict == "PASS"
        assert result.finding_count == 0

    def test_trailing_whitespace(self):
        """Verdict with trailing spaces/newlines is handled correctly."""
        output = "DOC-DRIFT-VERDICT: PASS   \n\n\n"
        result = validate_doc_verdict(output)
        assert result.found is True
        assert result.verdict == "PASS"
        assert result.position_warning == ""

    def test_verdict_with_leading_spaces_on_line(self):
        """Verdict line with leading spaces is still matched after strip."""
        output = "  DOC-DRIFT-VERDICT: FAIL(1)  "
        result = validate_doc_verdict(output)
        assert result.found is True
        assert result.verdict == "FAIL"
        assert result.finding_count == 1

    def test_large_finding_count(self):
        """Large finding count is parsed correctly."""
        output = "DOC-DRIFT-VERDICT: FAIL(42)"
        result = validate_doc_verdict(output)
        assert result.found is True
        assert result.verdict == "FAIL"
        assert result.finding_count == 42


def _extract_step5_section(agent_text: str) -> str:
    """Return the body of the canonical 'Step 5: Output Verdict' section.

    Args:
        agent_text: Full text of agents/doc-master.md.

    Returns:
        The section text from the Step 5 heading up to the next top-level heading.

    Raises:
        AssertionError: If the canonical section cannot be located.
    """
    start = agent_text.find("### Step 5: Output Verdict")
    assert start != -1, (
        "agents/doc-master.md must contain the canonical section "
        "'### Step 5: Output Verdict' (Issue #1773 Decision 3)."
    )
    end = agent_text.find("\n## ", start)
    assert end != -1, "No top-level heading found after Step 5 in doc-master.md."
    return agent_text[start:end]


def _extract_declared_verdict_tokens(section: str) -> list[str]:
    """Extract every ``DOC-DRIFT-VERDICT: <token>`` literal declared in a section.

    Args:
        section: Markdown text to scan (backticks and code fences are tolerated).

    Returns:
        Deduplicated, order-preserving list of declared token strings,
        e.g. ``["PASS", "FAIL(N)"]``.
    """
    matches = re.findall(r"DOC-DRIFT-VERDICT:\s*([A-Za-z-]+(?:\([^)\s]*\))?)", section)
    seen: list[str] = []
    for token in matches:
        if token not in seen:
            seen.append(token)
    return seen


def _extract_doc_master_templates(content: str) -> list[str]:
    """Extract doc-master dispatch prompt templates from a command markdown file.

    Uses the same non-greedy extraction shape as
    tests/unit/commands/test_batch_doc_master_prompt_minimum.py so the two
    test modules agree on what counts as a dispatch template.

    Args:
        content: Full text of a command markdown file.

    Returns:
        List of raw template bodies.
    """
    return re.findall(
        r'subagent_type:\s*"doc-master".*?prompt:\s*"(.*?)"',
        content,
        re.DOTALL,
    )


class TestRoleParserContractAgreement:
    """Issue #1773: the dispatched contract and the parsed contract must agree.

    Observed: doc-master was dispatched with the exact task, omitted required
    examination, and still reported PASS, while the dispatched vocabulary and
    the parsed vocabulary disagreed. What the capture does NOT establish is
    whether the pipeline then accepted that verdict — no claim about acceptance
    is made here. The underlying contract defect: agents/doc-master.md declared
    DOC-DRIFT-VERDICT: PASS / FAIL(N) while four dispatch templates asked for
    DOCS-UPDATED / NO-UPDATE-NEEDED / DOCS-DRIFT-FOUND — tokens this parser has
    never matched.

    Every assertion below reads REAL source bytes. No fixture restates the
    contract, because a fixture copy is a third source of truth and would drift
    exactly as the templates did.
    """

    def test_step5_declared_tokens_all_parse(self) -> None:
        """POSITIVE ARM: every token declared in Step 5 parses with found=True."""
        section = _extract_step5_section(DOC_MASTER_AGENT_PATH.read_text(encoding="utf-8"))
        tokens = _extract_declared_verdict_tokens(section)

        # Positive control on the extractor itself: a zero-token extraction would
        # make every assertion below vacuously true.
        assert tokens, (
            "Extracted zero verdict tokens from doc-master.md Step 5. The "
            "extractor is broken or the canonical declaration was removed; "
            "either way this test cannot inform until it is fixed."
        )

        for token in tokens:
            line = f"DOC-DRIFT-VERDICT: {token}"
            result = validate_doc_verdict(line)
            assert result.found is True, (
                f"agents/doc-master.md Step 5 declares {line!r}, but the real "
                f"parser in lib/doc_verdict_validator.py does not recognise it. "
                f"The role definition and the parser have diverged (Issue #1773)."
            )

    def test_step5_declares_both_canonical_forms(self) -> None:
        """The canonical declaration must still cover PASS and the FAIL(N) form."""
        section = _extract_step5_section(DOC_MASTER_AGENT_PATH.read_text(encoding="utf-8"))
        tokens = _extract_declared_verdict_tokens(section)

        assert "PASS" in tokens, (
            f"doc-master.md Step 5 no longer declares PASS. Found: {tokens}."
        )
        assert any(t.startswith("FAIL(") for t in tokens), (
            f"doc-master.md Step 5 no longer declares the FAIL(N) form. Found: {tokens}."
        )

    def test_retired_tokens_are_unparseable_in_verdict_position(self) -> None:
        """NEGATIVE ARM: retired tokens yield found=False after the field name.

        This proves the contract the templates used to request was never
        parseable — an agent obeying the old dispatch prompt produced output the
        pipeline could not read, whatever it actually did.
        """
        for token in RETIRED_VERDICT_TOKENS:
            line = f"DOC-DRIFT-VERDICT: {token}"
            result = validate_doc_verdict(line)
            assert result.found is False, (
                f"{line!r} unexpectedly parsed (verdict={result.verdict!r}). The "
                f"retired vocabulary must remain unparseable (Issue #1773)."
            )
            assert result.verdict == ""

    def test_retired_tokens_are_unparseable_as_bare_verdict_lines(self) -> None:
        """NEGATIVE ARM, second shape: the tokens as the templates actually used them.

        The old templates instructed doc-master to write ``DOCS-UPDATED: ...``
        as a standalone line rather than after the DOC-DRIFT-VERDICT field name.
        That shape is equally unparseable, which is the practical failure mode.
        """
        for token in RETIRED_VERDICT_TOKENS:
            output = (
                "Reviewed the changed files and the docs that cover them.\n"
                f"{token}: docs/EXAMPLE.md was reviewed and needs no change."
            )
            result = validate_doc_verdict(output)
            assert result.found is False, (
                f"A bare {token!r} line parsed as a verdict (verdict="
                f"{result.verdict!r}). It MUST NOT (Issue #1773)."
            )

    def test_dispatch_templates_carry_no_unparseable_verdict_token(self) -> None:
        """All four dispatch templates must be free of parser-rejected tokens.

        Reads the real implement.md and implement-fix.md bytes. The count check
        is a positive control: if template extraction silently returned fewer
        blocks than exist, the per-template loop would pass over nothing.
        """
        implement_templates = _extract_doc_master_templates(
            IMPLEMENT_CMD_PATH.read_text(encoding="utf-8")
        )
        fix_templates = _extract_doc_master_templates(
            IMPLEMENT_FIX_CMD_PATH.read_text(encoding="utf-8")
        )

        assert len(implement_templates) >= 3, (
            f"Expected at least 3 doc-master dispatch templates in implement.md "
            f"(STEP 10 parallel, STEP 10c sequential, STEP L4 light); extracted "
            f"{len(implement_templates)}."
        )
        assert len(fix_templates) >= 1, (
            f"Expected at least 1 doc-master dispatch template in "
            f"implement-fix.md; extracted {len(fix_templates)}."
        )

        for label, templates in (
            ("implement.md", implement_templates),
            ("implement-fix.md", fix_templates),
        ):
            for i, template in enumerate(templates):
                upper = template.upper()
                present = [tok for tok in RETIRED_VERDICT_TOKENS if tok in upper]
                assert not present, (
                    f"{label} doc-master template #{i + 1} requests verdict "
                    f"token(s) {present} that lib/doc_verdict_validator.py "
                    f"rejects. Dispatched contract must match parsed contract "
                    f"(Issue #1773)."
                )
