"""Regression tests for Issue #921 — implementer agent must forbid plan-critic
revision annotations in section headers of research/ADR documents it produces.

Background:
    When the implementer produces research/ADR documents during /implement, it
    sometimes embeds plan-critic revision annotations directly in section
    headers, e.g.:

        ## Security Model (Revised: sandboxing clarified per critic feedback)

    These are plan-critic working artifacts that should NOT appear in final
    documents. The reviewer flagged this pattern as a recurring WARNING.

    The fix is a HARD GATE / FORBIDDEN block added to the implementer agent
    prompt. These tests lock in (a) that the FORBIDDEN block is present in
    implementer.md, (b) that existing FORBIDDEN gates were NOT removed, and
    (c) that we can mechanically detect the polluted-header pattern.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

# tests/regression/ -> tests/ -> repo root
REPO_ROOT = Path(__file__).resolve().parents[2]
IMPLEMENTER_MD = REPO_ROOT / "plugins" / "autonomous-dev" / "agents" / "implementer.md"

# Pattern: a Markdown H2 (or deeper) heading whose trailing parenthetical contains
# plan-critic revision-cycle vocabulary. Matches lines like:
#   ## Security Model (Revised: sandboxing clarified)
#   ### API Surface (REVISE pass 2)
#   ## Data Model (revision: added field)
POLLUTED_HEADER_PATTERN = re.compile(
    r"^#{2,}\s.*\((Revised|REVISE|revision)",
    re.MULTILINE | re.IGNORECASE,
)


def _scan_for_polluted_headers(markdown: str) -> list[str]:
    """Return all header lines in ``markdown`` that look like they embed
    plan-critic revision annotations.

    A polluted header is any ATX heading (``##`` or deeper) whose body contains
    a parenthetical opening with ``Revised``, ``REVISE``, or ``revision``
    (case-insensitive). Single-paragraph prose mentioning those words is NOT
    flagged — only heading lines.

    Args:
        markdown: Raw markdown text to scan.

    Returns:
        List of matching heading lines (without trailing newline). Empty list
        means the document is clean.
    """
    matches = []
    for line in markdown.splitlines():
        if POLLUTED_HEADER_PATTERN.match(line):
            matches.append(line)
    return matches


@pytest.fixture(scope="module")
def implementer_content() -> str:
    """Read the implementer.md prompt once per test module."""
    assert IMPLEMENTER_MD.exists(), (
        f"implementer.md not found at {IMPLEMENTER_MD}\n"
        f"Expected the implementer agent prompt to live under "
        f"plugins/autonomous-dev/agents/.\n"
        f"See: docs/ARCHITECTURE-OVERVIEW.md"
    )
    return IMPLEMENTER_MD.read_text()


class TestImplementerForbidsHeaderPollution:
    """The implementer agent prompt MUST forbid plan-critic revision annotations
    in section headers of any document it produces."""

    def test_forbidden_clean_prose_titles_phrase_present(
        self, implementer_content: str
    ) -> None:
        """The canonical phrase 'section headers MUST be clean prose titles only'
        anchors the gate so future edits cannot quietly weaken it."""
        assert "Section headers MUST be clean prose titles only" in implementer_content, (
            "Expected the canonical phrase 'Section headers MUST be clean prose titles "
            "only' in implementer.md.\n"
            "This anchors the Issue #921 FORBIDDEN gate for plan-critic revision "
            "annotations in document headers.\n"
            "See: tests/regression/test_issue_921_implementer_header_cleanliness.py"
        )

    def test_forbidden_section_calls_out_example_pattern(
        self, implementer_content: str
    ) -> None:
        """The FORBIDDEN list MUST cite the concrete pattern (e.g., 'Revised:' or
        'revision annotations') so the prohibition is unambiguous."""
        # Either the example word 'Revised' (from the example header) or the
        # phrase 'revision annotations' (from the FORBIDDEN bullet) MUST appear.
        # Both anchor the same gate, but we accept either canonical form.
        assert (
            "Revised:" in implementer_content
            or "revision annotations" in implementer_content
        ), (
            "Expected the FORBIDDEN list to cite the concrete header-pollution "
            "pattern — either the example marker 'Revised:' or the phrase "
            "'revision annotations'.\n"
            "Without a concrete example, the gate is too abstract to enforce.\n"
            "See: Issue #921"
        )

    def test_pre_existing_stub_forbidden_section_still_present(
        self, implementer_content: str
    ) -> None:
        """Regression guard: adding the #921 gate MUST NOT have accidentally
        removed the pre-existing stub / skip / Real Implementation gates."""
        # The "No New Skips" hard gate (predates #921, must survive)
        assert "HARD GATE: No New Skips" in implementer_content, (
            "Pre-existing 'HARD GATE: No New Skips' section is missing — "
            "the #921 edit accidentally removed it."
        )
        # The "Real Implementation" principle (from the 3 Implementation Quality
        # Principles block — predates #921 and #1004, must survive)
        assert "Real Implementation" in implementer_content, (
            "Pre-existing 'Real Implementation' principle is missing — "
            "the #921 edit accidentally removed it."
        )
        # The blanket FORBIDDEN-style enforcement language MUST still appear in
        # multiple places (at least 3 distinct FORBIDDEN blocks pre-existed).
        forbidden_count = implementer_content.count("**FORBIDDEN**")
        assert forbidden_count >= 3, (
            f"Expected at least 3 FORBIDDEN blocks in implementer.md, found "
            f"{forbidden_count}. The #921 edit may have removed existing gates."
        )


class TestHeaderPollutionDetector:
    """The pattern-detection helper itself must work — it is the regression
    lock that future test/lint code can reuse to scan generated docs."""

    def test_detector_flags_issue_example(self) -> None:
        """The exact example from the Issue #921 body MUST be flagged."""
        sample = "## Security Model (Revised: sandboxing clarified per critic feedback)"
        matches = _scan_for_polluted_headers(sample)
        assert matches == [sample], (
            f"Detector failed to flag the canonical Issue #921 example.\n"
            f"Expected: [{sample!r}]\n"
            f"Got: {matches!r}"
        )

    def test_detector_flags_revise_variant(self) -> None:
        """The detector MUST also flag REVISE-cycle annotations."""
        sample = "### API Surface (REVISE pass 2)"
        matches = _scan_for_polluted_headers(sample)
        assert matches == [sample]

    def test_detector_flags_lowercase_revision(self) -> None:
        """Case-insensitive: 'revision:' inside a heading MUST be flagged."""
        sample = "## Data Model (revision: added user_id field)"
        matches = _scan_for_polluted_headers(sample)
        assert matches == [sample]

    def test_detector_flags_within_multiline_doc(self) -> None:
        """Embedded inside a realistic mixed document, the detector picks out
        ONLY the polluted heading and leaves clean content alone."""
        doc = "\n".join(
            [
                "# Research Notes",
                "",
                "## Overview",
                "Some normal prose mentioning the word revision in passing.",
                "",
                "## Security Model (Revised: sandboxing clarified)",
                "More prose.",
                "",
                "## Conclusion",
            ]
        )
        matches = _scan_for_polluted_headers(doc)
        assert matches == ["## Security Model (Revised: sandboxing clarified)"], (
            f"Detector should have flagged exactly one heading; got {matches!r}"
        )


class TestHeaderPollutionDetectorNegative:
    """Clean headers MUST NOT be flagged — the detector is precise, not
    over-eager."""

    def test_detector_does_not_flag_clean_h2(self) -> None:
        assert _scan_for_polluted_headers("## Security Model") == []

    def test_detector_does_not_flag_clean_h3(self) -> None:
        assert _scan_for_polluted_headers("### API Surface") == []

    def test_detector_does_not_flag_clean_doc(self) -> None:
        doc = "\n".join(
            [
                "# Research Notes",
                "",
                "## Overview",
                "Body paragraph.",
                "",
                "## Security Model",
                "More body.",
                "",
                "## Conclusion",
            ]
        )
        assert _scan_for_polluted_headers(doc) == []

    def test_detector_does_not_flag_prose_mentioning_revision(self) -> None:
        """The word 'revision' appearing in body prose (NOT a heading) is fine
        — only headings are gated."""
        body = "This document went through a revision cycle (Revised: yes) last week."
        assert _scan_for_polluted_headers(body) == []

    def test_detector_does_not_flag_h1_with_revised(self) -> None:
        """H1 (``#``) is typically the document title — the pattern explicitly
        targets H2+ (``##`` and deeper), where section-level pollution lives.
        H1 isn't expected to be reused for section-style revision tags."""
        # POLLUTED_HEADER_PATTERN uses #{2,} so a single # is excluded by design.
        assert _scan_for_polluted_headers("# Title (Revised: 1)") == []
