#!/usr/bin/env python3
"""The four evidence rules must live in ``implementer.md``, not in a brief.

Issue #1587. A full day of work produced eight defect fixes and caught seven
coordinator errors, and every one of those outcomes traced to four requirements
the coordinator hand-wrote into each dispatch brief. None of the four was in the
agent prompt, so the quality was the coordinator's rather than the system's and
did not survive the session. A convention that holds only while someone is
watching is not a mechanism.

This module pins the gate that encodes them:

1. A guard is unproven until watched REFUSING *and* PERMITTING.
2. Verify the instrument (positive + negative control) before trusting output.
3. Regression attribution is a SET comparison, never counts.
4. Verify the copy that EXECUTES.
5. When two instruments disagree, the disagreement IS the finding.

Deliberate non-duplication of prior art
---------------------------------------
``## HARD GATE: Regression Test for Bug Fixes`` already requires a test that
fails without the fix and passes with it. That is red-before/green-after for the
*fixing test*, and it is not re-asserted here. What the #1587 gate adds is the
half that gate does not reach: the PERMITTING arm, class-versus-instance scope,
how you determine you BROKE something, and whether the fix is live in the copy
that runs. ``test_gate_does_not_restate_the_regression_test_gate`` pins that
boundary so a future edit cannot collapse the two into one restated rule.

What this module does NOT verify
--------------------------------
This is a prompt change, so "does it work" means "does an agent behave
differently", which no static test can establish. Everything below is a
structural presence guard on the prompt text. Behavioural efficacy is
UNVERIFIED here by construction.
"""

import re
import sys
from pathlib import Path

import pytest

# tests/unit/test_implementer_evidence_rules.py -> unit -> tests -> repo root
PROJECT_ROOT = Path(__file__).resolve().parents[2]

_LIB = PROJECT_ROOT / "plugins" / "autonomous-dev" / "lib"
if str(_LIB) not in sys.path:
    sys.path.insert(0, str(_LIB))

from prompt_quality_rules import (  # noqa: E402
    check_casual_register,
    check_persona,
)

# The TRACKED source of truth. NOT ``.claude/agents/``, a gitignored deploy
# artifact — see tests/unit/test_agent_serena_tools.py for the evidence.
IMPLEMENTER = PROJECT_ROOT / "plugins" / "autonomous-dev" / "agents" / "implementer.md"

ISSUE_REF = "#1587"

# The single text anchor. Some anchor is unavoidable to locate a section; this
# is the minimum, and every other assertion below is derived from the structure
# found beneath it rather than from further hardcoded prose.
GATE_HEADER_TOKEN = "Evidence Rules"

# Concept tokens that identify each rule, keyed on its BOLD HEADING (the
# semantic core, which is the most stable part of the block). Prose beneath a
# heading is free to be reworded; the heading concept is what the rule IS.
RULE_CONCEPTS: "dict[int, tuple[str, ...]]" = {
    1: ("REFUSING", "PERMITTING"),
    2: ("instrument",),
    3: ("SET",),
    4: ("EXECUTES",),
    5: ("disagree",),
}

_H2 = re.compile(r"^## (.+)$", re.MULTILINE)
_RULE_HEADING = re.compile(r"^\*\*Rule (\d+) — (.+?)\*\*", re.MULTILINE)
_EVIDENCE_MARKER = re.compile(r"^\*Evidence:\*", re.MULTILINE)
_FORBIDDEN_ITEM = re.compile(r"^\d+\. ❌ ", re.MULTILINE)


def _read_implementer() -> str:
    """Return the tracked implementer agent prompt.

    Returns:
        Full file text including frontmatter.

    Raises:
        AssertionError: If the agent file is absent.
    """
    assert IMPLEMENTER.exists(), (
        f"implementer.md not found at {IMPLEMENTER}\n"
        f"Expected: the tracked agent source under plugins/autonomous-dev/agents/"
    )
    return IMPLEMENTER.read_text(encoding="utf-8")


def _h2_sections(content: str) -> "dict[str, str]":
    """Split markdown into ``{level-2 header: section body}``.

    Args:
        content: Full markdown text.

    Returns:
        Mapping of each ``## `` header line (header text only) to the text
        between it and the next ``## `` header.
    """
    matches = list(_H2.finditer(content))
    sections: "dict[str, str]" = {}
    for i, match in enumerate(matches):
        end = matches[i + 1].start() if i + 1 < len(matches) else len(content)
        sections[match.group(1).strip()] = content[match.end() : end]
    return sections


def _find_gate(content: str) -> "tuple[str, str]":
    """Locate the #1587 evidence gate by its header token.

    Args:
        content: Full markdown text.

    Returns:
        ``(header, body)`` for the section whose ``## `` header contains
        :data:`GATE_HEADER_TOKEN`.

    Raises:
        AssertionError: If no such section exists, or more than one does.
    """
    hits = [
        (header, body)
        for header, body in _h2_sections(content).items()
        if GATE_HEADER_TOKEN in header
    ]
    assert len(hits) == 1, (
        f"Expected exactly one ## section whose header contains "
        f"{GATE_HEADER_TOKEN!r}; found {len(hits)}: {[h for h, _ in hits]}\n"
        f"Issue #1587 adds 'HARD GATE: Evidence Rules for Verification Claims'."
    )
    return hits[0]


def _rule_blocks(gate_body: str) -> "dict[int, str]":
    """Split a gate body into ``{rule number: block text}``.

    Args:
        gate_body: Text of the evidence gate section.

    Returns:
        Mapping of rule number to the text from its ``**Rule N — ...**``
        heading up to the next rule heading (or end of section).
    """
    matches = list(_RULE_HEADING.finditer(gate_body))
    blocks: "dict[int, str]" = {}
    for i, match in enumerate(matches):
        end = matches[i + 1].start() if i + 1 < len(matches) else len(gate_body)
        blocks[int(match.group(1))] = gate_body[match.start() : end]
    return blocks


def _evidence_gate_findings(gate_body: str) -> "list[str]":
    """Return every way ``gate_body`` fails the #1587 requirements.

    THE rule, factored out so the live prompt and the mutated-prompt controls
    run the identical code path. A control that re-implements the rule proves
    nothing about the rule.

    Args:
        gate_body: Text of the evidence gate section.

    Returns:
        Sorted list of human-readable findings; empty when the gate is complete.
    """
    findings: "list[str]" = []
    blocks = _rule_blocks(gate_body)

    for number, tokens in sorted(RULE_CONCEPTS.items()):
        block = blocks.get(number)
        if block is None:
            findings.append(
                f"Rule {number} is missing (concept: {'/'.join(tokens)})"
            )
            continue
        heading = _RULE_HEADING.search(block).group(2)
        absent = [token for token in tokens if token not in heading]
        if absent:
            findings.append(
                f"Rule {number} heading lost concept token(s) {absent}: {heading!r}"
            )
        if not _EVIDENCE_MARKER.search(block):
            findings.append(
                f"Rule {number} carries no '*Evidence:*' line — a rule with no "
                f"earning failure is an assertion, not a mechanism"
            )

    # Numbering must be contiguous from 1: a gap means a rule was deleted
    # without renumbering, which reads as complete but is not.
    if blocks:
        expected = list(range(1, max(blocks) + 1))
        gaps = sorted(set(expected) - set(blocks))
        if gaps:
            findings.append(f"Rule numbering has gaps at {gaps}")

    return sorted(findings)


@pytest.fixture(scope="module")
def gate() -> "tuple[str, str]":
    """Return ``(header, body)`` of the live #1587 evidence gate."""
    return _find_gate(_read_implementer())


class TestEvidenceGateIsPresentAndComplete:
    """The gate exists in the tracked prompt and carries all five rules."""

    def test_gate_is_declared_a_hard_gate(self, gate) -> None:
        """The section MUST use the file's HARD GATE register, not prose.

        ``prompt_quality_rules.EXEMPT_HEADER_TOKENS`` also keys bullet-density
        exemption on this token, so the header form is load-bearing twice over.
        """
        header, _ = gate
        assert header.startswith("HARD GATE:"), (
            f"Evidence-rules section header is {header!r}; it MUST begin with "
            f"'HARD GATE:' to match the register of the ~15 sibling gates in "
            f"implementer.md."
        )

    def test_gate_cites_its_issue(self, gate) -> None:
        """Traceability: the header MUST carry the issue reference (#1587)."""
        header, _ = gate
        assert ISSUE_REF in header, (
            f"Evidence-rules header {header!r} omits {ISSUE_REF}. Sibling gates "
            f"cite their issue in the header (e.g. 'HARD GATE: Mocked-API "
            f"Surface Verification (Issue #1225)')."
        )

    def test_gate_carries_every_required_rule(self, gate) -> None:
        """All five rules present, numbered contiguously, each with evidence."""
        _, body = gate
        findings = _evidence_gate_findings(body)
        assert not findings, (
            "The #1587 evidence gate is incomplete:\n  - "
            + "\n  - ".join(findings)
            + f"\n\nExpected rules: {sorted(RULE_CONCEPTS)}\n"
            f"See: {IMPLEMENTER}"
        )

    def test_every_rule_has_an_enforcement_item(self, gate) -> None:
        """The FORBIDDEN list MUST cover at least one ❌ per rule.

        A rule stated in prose with no FORBIDDEN counterpart is a nudge. The
        file's own convention pairs each gate's requirements with an explicit
        ❌ list; a rule count that outruns the ❌ count means a rule shipped
        unenforced.
        """
        _, body = gate
        rules = len(_rule_blocks(body))
        items = len(_FORBIDDEN_ITEM.findall(body))
        assert rules >= len(RULE_CONCEPTS), (
            f"premise: expected at least {len(RULE_CONCEPTS)} rules, found {rules}"
        )
        assert items >= rules, (
            f"The evidence gate states {rules} rules but lists only {items} "
            f"FORBIDDEN ❌ items. Every rule needs an enforcement counterpart."
        )


class TestGateComposesWithPriorArt:
    """The gate extends the existing gates rather than duplicating them."""

    def test_prior_gates_it_depends_on_still_exist(self) -> None:
        """Additive-only: the sections #1587 composes with MUST survive it."""
        headers = _h2_sections(_read_implementer())
        for required in (
            "HARD GATE: Regression Test for Bug Fixes",
            "Pre-Existing Failure Awareness",
        ):
            assert required in headers, (
                f"implementer.md lost the {required!r} section. Issue #1587 is "
                f"ADDITIVE and its Rule 3 composition text references this "
                f"section by name — removing it strands the reference."
            )

    def test_gate_names_the_sections_it_composes_with(self, gate) -> None:
        """The boundary MUST be explicit so a reader sees what is NOT restated."""
        _, body = gate
        for referenced in (
            "HARD GATE: Regression Test for Bug Fixes",
            "Pre-Existing Failure Awareness",
        ):
            assert referenced in body, (
                f"The evidence gate does not name {referenced!r}. Without the "
                f"explicit boundary a future editor cannot tell which half of "
                f"red-before/green-after is already covered elsewhere."
            )

    def test_gate_does_not_restate_the_regression_test_gate(self) -> None:
        """The red-before/green-after wording MUST stay in exactly one section.

        Duplicated enforcement text is two things that can drift. The #1587 gate
        covers the PERMITTING arm; the fail-without-the-fix requirement belongs
        to ``HARD GATE: Regression Test for Bug Fixes`` and stays there.
        """
        content = _read_implementer()
        marker = "MUST fail without your fix applied"
        occurrences = content.count(marker)
        assert occurrences == 1, (
            f"{marker!r} appears {occurrences} times in implementer.md; expected "
            f"exactly 1 (inside 'HARD GATE: Regression Test for Bug Fixes'). "
            f"Issue #1587 MUST NOT restate it."
        )


class TestGateRespectsPromptQualityRules:
    """The addition must not trip the write-time prompt-quality gate.

    Derived by running the REAL ``prompt_quality_rules`` library over the
    section, not by copying its pattern list into this test — a third copy is a
    third thing that can drift.
    """

    def test_gate_uses_no_casual_register(self, gate) -> None:
        """'you should' / 'make sure' / 'try to' weaken an enforcement gate."""
        _, body = gate
        violations = check_casual_register(body)
        assert violations == [], (
            "The #1587 evidence gate uses casual register, which "
            "unified_pre_tool.py Layer 6 hard-blocks:\n" + "\n".join(violations)
        )

    def test_gate_uses_no_banned_persona(self, gate) -> None:
        """No 'You are an expert ...' opener inside the section."""
        _, body = gate
        assert check_persona(body) == [], (
            "The #1587 evidence gate contains a banned persona opener:\n"
            + "\n".join(check_persona(body))
        )

    def test_whole_file_still_passes_casual_register(self) -> None:
        """Whole-file parity: implementer.md was at zero and MUST stay there.

        ``tests/unit/test_prompt_quality.py`` permits up to 5 per file. That
        headroom is not a budget to spend — the file scored 0 before #1587.
        """
        violations = check_casual_register(_read_implementer())
        assert violations == [], (
            "implementer.md now has casual-register violations; it had zero "
            "before Issue #1587:\n" + "\n".join(violations)
        )


class TestNegativeControls:
    """Watch the rule REFUSING, not only permitting (Rule 1, applied here).

    Each control feeds a MUTATED copy of the live gate through
    ``_evidence_gate_findings`` — the same function the live test calls — so a
    check that could never fail cannot pass these.
    """

    @staticmethod
    def _live_body() -> str:
        return _find_gate(_read_implementer())[1]

    @staticmethod
    def _delete_rule(body: str, number: int) -> str:
        """Remove one rule block from a gate body.

        Args:
            body: Gate section text.
            number: Rule number to excise.

        Returns:
            The body with that rule's block removed.
        """
        blocks = _rule_blocks(body)
        return body.replace(blocks[number], "")

    def test_control_live_gate_is_clean(self) -> None:
        """Positive control: the unmutated gate produces zero findings.

        Without this, every control below could pass against a rule that flags
        everything indiscriminately.
        """
        assert _evidence_gate_findings(self._live_body()) == []

    @pytest.mark.parametrize("number", sorted(RULE_CONCEPTS))
    def test_control_removing_a_rule_names_that_rule(self, number: int) -> None:
        """Refusing arm: deleting rule N MUST produce a finding naming N.

        This is the 'watched both ways' evidence for this test module itself:
        the check is observed refusing a gate missing each rule in turn, and
        (above) permitting the complete one.
        """
        mutated = self._delete_rule(self._live_body(), number)
        findings = _evidence_gate_findings(mutated)
        assert findings, f"deleting Rule {number} produced no finding at all"
        assert any(f"Rule {number}" in finding for finding in findings), (
            f"deleting Rule {number} produced findings that do not name it: "
            f"{findings}"
        )

    def test_control_stripped_evidence_line_is_detected(self) -> None:
        """A rule reduced to a bare assertion MUST be flagged.

        Different shape from the delete-a-rule control: the rule is still
        present and correctly numbered, only its earning failure is gone. A
        check keyed solely on rule headings would permit this.
        """
        body = self._live_body()
        mutated = _EVIDENCE_MARKER.sub("*Note:*", body)
        findings = _evidence_gate_findings(mutated)
        assert len(findings) == len(RULE_CONCEPTS), (
            f"expected one missing-evidence finding per rule, got {findings}"
        )
        assert all("Evidence" in finding for finding in findings), findings

    def test_control_reworded_heading_is_detected(self) -> None:
        """Losing a concept token from a heading MUST be flagged.

        Third shape: the rule, its number and its evidence all survive, but the
        heading no longer says the thing the rule is for. This is how a rule
        gets quietly softened without being deleted.
        """
        body = self._live_body()
        mutated = body.replace("REFUSING", "running")
        findings = _evidence_gate_findings(mutated)
        assert any("Rule 1" in finding for finding in findings), (
            f"softening Rule 1's heading was not detected: {findings}"
        )

    def test_control_renumbering_gap_is_detected(self) -> None:
        """A numbering gap MUST be flagged, not silently tolerated."""
        body = self._live_body()
        mutated = body.replace("**Rule 2 —", "**Rule 9 —")
        findings = _evidence_gate_findings(mutated)
        assert any("gaps" in finding for finding in findings), (
            f"a renumbering gap went undetected: {findings}"
        )

    def test_control_absent_gate_is_detected(self) -> None:
        """A prompt with no evidence gate MUST fail loudly, never vacuously."""
        with pytest.raises(AssertionError, match=GATE_HEADER_TOKEN):
            _find_gate("## HARD GATE: Something Else\n\nbody\n")

    def test_control_unrelated_section_is_permitted(self) -> None:
        """Permitting arm for the locator: a sibling gate is NOT mistaken for it.

        A locator that matched any ``## HARD GATE:`` header would pass every
        control above while being useless.
        """
        content = _read_implementer()
        header, _ = _find_gate(content)
        others = [h for h in _h2_sections(content) if h.startswith("HARD GATE:")]
        assert len(others) > 1, "premise: implementer.md has many HARD GATE sections"
        assert header in others
        assert sum(GATE_HEADER_TOKEN in h for h in others) == 1, (
            "the locator token is ambiguous across sibling gates"
        )


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
