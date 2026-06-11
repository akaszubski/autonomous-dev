"""Tests for CIA cross-repo finding routing (Issue #739)."""

import re
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
CIA_AGENT = REPO_ROOT / "plugins" / "autonomous-dev" / "agents" / "continuous-improvement-analyst.md"
WORKFLOW_DOCS = REPO_ROOT / "docs" / "WORKFLOW-DISCIPLINE.md"


class TestCIAFindingRouting:
    """Verify CIA agent has cross-repo finding routing."""

    def setup_method(self):
        self.cia_content = CIA_AGENT.read_text()

    def test_has_finding_routing_section(self):
        """AC1: CIA prompt has a Finding Routing section."""
        assert re.search(r"(?i)#+\s*finding\s+routing", self.cia_content), \
            "CIA agent prompt must have a 'Finding Routing' section header"

    def test_has_routing_decision_heuristic(self):
        """AC1: Routing section has decision heuristic based on fix location."""
        assert "plugins/autonomous-dev/" in self.cia_content, \
            "CIA must reference plugins/autonomous-dev/ path for routing heuristic"
        # Should mention routing to autonomous-dev vs consumer
        assert re.search(r"(?i)(consumer|active\s+repo)", self.cia_content), \
            "CIA must mention consumer/active repo as a routing target"

    def test_has_target_repo_field(self):
        """AC2: Structured output includes target_repo field."""
        assert "target_repo" in self.cia_content, \
            "CIA output must include target_repo field"
        # Should list the valid values
        for value in ["consumer", "autonomous-dev", "both"]:
            assert value in self.cia_content, \
                f"CIA must list '{value}' as a valid target_repo value"

    def test_has_filing_commands_with_repo_flag(self):
        """AC3 (Issue #1200 C2): CIA emits findings via append_finding(), NOT via gh CLI.

        Updated contract: routing/dedup/filing was moved out of CIA into
        ``/improve --auto-file`` (C3). CIA now emits a structured record per
        finding through :func:`cia_finding_store.append_finding`. The
        ``target_repo`` value (``autonomous-dev`` | ``consumer`` | ``both``)
        is a pass-through field on the emitted record — the downstream
        promotion layer uses it to pick the ``-R`` repo flag at file time.

        This test locks the inverse of the OLD behavior: there must be zero
        ``gh issue create`` / ``gh issue comment`` invocations in the prompt,
        AND the prompt must explicitly instruct emission via append_finding()
        with target_repo as a pass-through.
        """
        # NEW contract: zero direct filing commands of either kind.
        assert "gh issue create" not in self.cia_content, (
            "CIA prompt must not contain `gh issue create` — filing moved to "
            "/improve --auto-file (Issue #1200 C2/C3)"
        )
        assert "gh issue comment" not in self.cia_content, (
            "CIA prompt must not contain `gh issue comment` — commenting moved "
            "to /improve --auto-file (Issue #1200 C2/C3)"
        )

        # NEW contract: emission goes through append_finding().
        assert "append_finding" in self.cia_content, (
            "CIA prompt must instruct emission via append_finding() "
            "(Issue #1200 C2 finding-store contract)"
        )

        # NEW contract: target_repo is a pass-through field on the emitted
        # record so the downstream promoter can fan out cross-repo without
        # re-routing.
        assert re.search(
            r"target_repo.*(?:pass-through|pass\s*through)",
            self.cia_content,
            re.IGNORECASE | re.DOTALL,
        ), (
            "CIA prompt must describe target_repo as a pass-through field on "
            "the emitted record (downstream /improve --auto-file owns routing)"
        )

    def test_has_at_least_4_routing_examples(self):
        """AC4: At least 4 routing examples in the prompt."""
        # Find the routing section and count examples
        routing_match = re.search(r"(?i)(#+\s*finding\s+routing.*?)(?=\n#+\s|\Z)", self.cia_content, re.DOTALL)
        assert routing_match, "Finding Routing section must exist"
        routing_section = routing_match.group(1)

        # Count distinct example patterns (numbered items, bullet items with arrows, etc.)
        examples = re.findall(r"(?:→|->|⟶)", routing_section)
        assert len(examples) >= 4, \
            f"Need at least 4 routing examples (with → arrows), found {len(examples)}"

    def test_workflow_docs_has_cross_repo_section(self):
        """AC5: WORKFLOW-DISCIPLINE.md has cross-repo finding routing subsection."""
        docs_content = WORKFLOW_DOCS.read_text()
        assert re.search(r"(?i)#+\s*cross-repo\s+finding\s+routing", docs_content), \
            "WORKFLOW-DISCIPLINE.md must have a 'Cross-repo finding routing' subsection"

    def test_both_target_creates_framework_issue_first(self):
        """Issue #1200 C2 update: ``target_repo: both`` emits a SINGLE record.

        Original Issue #742 regression: for ``target_repo: both``, the
        framework issue had to be filed first so the consumer issue body
        could cross-reference ``${FRAMEWORK_ISSUE}``. That ordering
        constraint lived in the CIA prompt's bash block.

        Issue #1200 C2 collapsed that two-issue dance into a single emitted
        record. CIA now emits one ``append_finding`` call with
        ``target_repo: "both"`` as a pass-through; the downstream
        ``/improve --auto-file`` layer (C3) is responsible for cross-repo
        fan-out and the framework-first ordering. Putting the ordering rule
        in the promoter (one place) eliminates the failure mode that
        Issue #742 fixed (two places drifting out of sync).

        This test locks the new contract: the prompt explicitly states that
        ``target_repo: both`` must emit a SINGLE record (not two), and the
        cross-repo fan-out responsibility is delegated to
        ``/improve --auto-file``.
        """
        # The prompt must explicitly forbid the old "two records for both"
        # pattern and instruct a single emission instead.
        # We accept either "SINGLE record" or "single record" phrasing and
        # require the words to be near a "both" mention so we are actually
        # locking the both-path contract.
        both_single_record = re.search(
            r"target_repo[^\n]{0,40}\"?both\"?.*?(?:SINGLE|single)\s+record",
            self.cia_content,
            re.DOTALL | re.IGNORECASE,
        )
        assert both_single_record, (
            "CIA prompt must instruct emitting a SINGLE record with "
            "target_repo: \"both\" (not two records). Cross-repo fan-out "
            "is /improve --auto-file's responsibility (Issue #1200 C2/C3)."
        )

        # The promoter (C3 / /improve --auto-file) must be named as the
        # owner of cross-repo fan-out so future readers know where the
        # framework-first ordering rule lives now.
        assert re.search(
            r"/improve\s+--auto-file.*(?:cross-repo|fan-out|fan\s*out|C3)",
            self.cia_content,
            re.DOTALL | re.IGNORECASE,
        ), (
            "CIA prompt must delegate cross-repo fan-out for target_repo: "
            "\"both\" to /improve --auto-file (C3). The framework-first "
            "ordering rule from Issue #742 now lives there, not in CIA."
        )

        # The OLD pattern (two gh issue create calls with the ${FRAMEWORK_ISSUE}
        # shell-variable dance) MUST be gone — that is precisely what Issue
        # #1200 C2 removed.
        assert "${FRAMEWORK_ISSUE}" not in self.cia_content, (
            "CIA prompt must not retain the ${FRAMEWORK_ISSUE} shell-variable "
            "dance — Issue #1200 C2 moved cross-repo fan-out to "
            "/improve --auto-file (C3)."
        )
        assert "gh issue create" not in self.cia_content, (
            "CIA prompt must not invoke `gh issue create` directly — filing "
            "moved to /improve --auto-file (Issue #1200 C2/C3)."
        )
