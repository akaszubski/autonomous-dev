"""Regression tests for /implement pipeline step ordering — Issue #1211.

Issue #1211: The `unified_pre_tool.py` agent-completeness gate blocks the
git commit (STEP 13) until `continuous-improvement-analyst` (CIA) has
completed. Previously the pipeline spec placed CIA at STEP 15, after the
commit, which created a structural ordering conflict that every standard
pipeline run resolved implicitly through coordinator improvisation.

Fix: Move CIA dispatch to STEP 12.5 (before STEP 13 commit). Repurpose
STEP 15 as cleanup-only.

These tests lock the corrected ordering in the spec file so that any future
edit that re-introduces the conflict trips a regression.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

# tests/regression/test_X.py -> parents[2] is repo root
REPO_ROOT = Path(__file__).resolve().parents[2]
IMPLEMENT_MD = REPO_ROOT / "plugins" / "autonomous-dev" / "commands" / "implement.md"


@pytest.fixture(scope="module")
def implement_text() -> str:
    """Return the implement.md text content (cached per module)."""
    assert IMPLEMENT_MD.exists(), f"Expected {IMPLEMENT_MD} to exist"
    return IMPLEMENT_MD.read_text()


@pytest.fixture(scope="module")
def implement_lines() -> list[str]:
    """Return the implement.md text as a list of lines (cached per module)."""
    return IMPLEMENT_MD.read_text().splitlines()


def _find_header_line(lines: list[str], header_prefix: str) -> int:
    """Return the 1-indexed line number of the first line starting with header_prefix.

    Raises AssertionError if not found.
    """
    for idx, line in enumerate(lines, start=1):
        if line.startswith(header_prefix):
            return idx
    raise AssertionError(f"Header not found: {header_prefix!r}")


def _section_text(lines: list[str], start_header: str, next_header_prefix: str) -> str:
    """Return the text between start_header and the next line starting with next_header_prefix.

    The returned text excludes both the start header and the next header lines.
    """
    start_idx = _find_header_line(lines, start_header)
    # Find the next header AFTER start_idx
    for idx in range(start_idx, len(lines)):
        if idx == start_idx - 1:
            continue
        if lines[idx].startswith(next_header_prefix) and idx + 1 != start_idx:
            return "\n".join(lines[start_idx:idx])
    # No next header — return to EOF
    return "\n".join(lines[start_idx:])


class TestStep12_5InsertedForIssue1211:
    """STEP 12.5 must dispatch CIA before STEP 13 commit (Issue #1211)."""

    def test_step_12_5_cia_before_step_13_commit_for_1211(
        self, implement_text: str, implement_lines: list[str]
    ) -> None:
        """STEP 12.5 header exists, appears before STEP 13, and contains CIA dispatch."""
        # 1. STEP 12.5 header must appear
        assert "### STEP 12.5: Continuous Improvement" in implement_text, (
            "STEP 12.5 header missing — required by Issue #1211 to satisfy the "
            "unified_pre_tool.py agent-completeness gate before the STEP 13 commit."
        )

        # 2. STEP 12.5 line number must be LESS than STEP 13 line number
        step_12_5_line = _find_header_line(implement_lines, "### STEP 12.5:")
        step_13_line = _find_header_line(implement_lines, "### STEP 13:")
        assert step_12_5_line < step_13_line, (
            f"STEP 12.5 (line {step_12_5_line}) must appear BEFORE STEP 13 "
            f"(line {step_13_line}) per Issue #1211 ordering fix."
        )

        # 3. The CIA dispatch must appear inside the STEP 12.5 section
        step_12_5_section = _section_text(
            implement_lines, "### STEP 12.5:", "### STEP 13:"
        )
        cia_dispatch_pattern = re.compile(
            r'subagent_type\s*=\s*"continuous-improvement-analyst"'
        )
        assert cia_dispatch_pattern.search(step_12_5_section), (
            "STEP 12.5 section must contain the CIA dispatch "
            '(subagent_type="continuous-improvement-analyst") per Issue #1211.'
        )

    def test_step_12_5_references_issue_1211_inline(
        self, implement_lines: list[str]
    ) -> None:
        """STEP 12.5 section must reference Issue #1211 inline."""
        step_12_5_section = _section_text(
            implement_lines, "### STEP 12.5:", "### STEP 13:"
        )
        assert "#1211" in step_12_5_section, (
            "STEP 12.5 must reference Issue #1211 inline so the motivation is "
            "discoverable when reading the spec."
        )

    def test_step_12_5_has_forbidden_list(self, implement_lines: list[str]) -> None:
        """STEP 12.5 must include the FORBIDDEN guard text (Issue #1211 spec)."""
        step_12_5_section = _section_text(
            implement_lines, "### STEP 12.5:", "### STEP 13:"
        )
        # The FORBIDDEN guard may be consolidated into prose or bullets.
        # Required keywords from the Issue #1211 FORBIDDEN list:
        for keyword in ("FORBIDDEN", "skip STEP 12.5", "clean up", "inline"):
            assert keyword in step_12_5_section, (
                f"STEP 12.5 FORBIDDEN guard missing keyword {keyword!r} — "
                f"required by Issue #1211 spec."
            )


class TestStep15IsCleanupOnly:
    """STEP 15 must no longer dispatch CIA after Issue #1211."""

    def test_step_15_is_cleanup_only_after_1211(
        self, implement_lines: list[str]
    ) -> None:
        """STEP 15 section must NOT contain an Agent dispatch for CIA."""
        # STEP 15 in the full pipeline ends at the '---' separator before
        # the LIGHT PIPELINE block, or at the next '### STEP' header.
        start_idx = _find_header_line(implement_lines, "### STEP 15:")
        # Find the next top-level boundary: either a "# " (h1) header or "---" separator
        section_end = len(implement_lines)
        for idx in range(start_idx, len(implement_lines)):
            line = implement_lines[idx]
            if line.startswith("# LIGHT PIPELINE MODE"):
                section_end = idx
                break
            if line.startswith("### STEP") and idx + 1 != start_idx:
                section_end = idx
                break
        step_15_section = "\n".join(implement_lines[start_idx:section_end])

        # The dispatch pattern must NOT appear in STEP 15
        cia_dispatch_pattern = re.compile(
            r'subagent_type\s*=\s*"continuous-improvement-analyst"'
        )
        assert not cia_dispatch_pattern.search(step_15_section), (
            "STEP 15 must be cleanup-only after Issue #1211 — the CIA dispatch "
            "was moved to STEP 12.5. Found dispatch in STEP 15 section."
        )

    def test_step_15_retains_cleanup_command(self, implement_lines: list[str]) -> None:
        """STEP 15 must still contain the pipeline state cleanup command."""
        start_idx = _find_header_line(implement_lines, "### STEP 15:")
        section_end = len(implement_lines)
        for idx in range(start_idx, len(implement_lines)):
            if implement_lines[idx].startswith("# LIGHT PIPELINE MODE"):
                section_end = idx
                break
        step_15_section = "\n".join(implement_lines[start_idx:section_end])

        assert "PIPELINE_STATE_FILE" in step_15_section, (
            "STEP 15 must retain the pipeline state cleanup command "
            "(rm -f $PIPELINE_STATE_FILE) per Issue #1211 spec."
        )
        assert (
            "cleanup_pipeline" in step_15_section
            or "clear_session" in step_15_section
        ), (
            "STEP 15 must retain the pipeline_state.cleanup_pipeline / "
            "clear_session cleanup logic per Issue #1211 spec."
        )

    def test_step_15_references_issue_1211(self, implement_lines: list[str]) -> None:
        """STEP 15 must reference Issue #1211 inline."""
        start_idx = _find_header_line(implement_lines, "### STEP 15:")
        section_end = len(implement_lines)
        for idx in range(start_idx, len(implement_lines)):
            if implement_lines[idx].startswith("# LIGHT PIPELINE MODE"):
                section_end = idx
                break
        step_15_section = "\n".join(implement_lines[start_idx:section_end])
        assert "#1211" in step_15_section, (
            "STEP 15 must reference Issue #1211 inline — it now documents the "
            "ordering fix that moved CIA to STEP 12.5."
        )


class TestCoordinatorForbiddenList:
    """The coordinator FORBIDDEN list must reference STEP 12.5 ordering."""

    def test_coordinator_forbidden_list_references_step_12_5(
        self, implement_text: str
    ) -> None:
        """The COORDINATOR FORBIDDEN LIST must reference STEP 12.5 in connection with STEP 13."""
        # The COORDINATOR FORBIDDEN LIST is near the top of the file.
        # Find the block bounded by 'COORDINATOR FORBIDDEN LIST' and the next '###' header.
        coord_match = re.search(
            r"\*\*COORDINATOR FORBIDDEN LIST\*\*.*?(?=\n### )",
            implement_text,
            re.DOTALL,
        )
        assert coord_match, "COORDINATOR FORBIDDEN LIST block not found in implement.md"
        coord_block = coord_match.group(0)

        # The block must mention STEP 12.5 in connection with STEP 13
        assert "STEP 12.5" in coord_block, (
            "COORDINATOR FORBIDDEN LIST must reference STEP 12.5 per Issue #1211 "
            "so the CIA-before-commit ordering is enforced at the coordinator level."
        )
        # The reference must tie STEP 12.5 to STEP 13 (commit)
        assert "STEP 13" in coord_block, (
            "COORDINATOR FORBIDDEN LIST must still reference STEP 13 to anchor "
            "the STEP 12.5 ordering relationship."
        )

    def test_coordinator_forbidden_list_no_stale_step_15_only_language(
        self, implement_text: str
    ) -> None:
        """The 'STEP 15 is mandatory' phrasing must be updated to include STEP 14."""
        coord_match = re.search(
            r"\*\*COORDINATOR FORBIDDEN LIST\*\*.*?(?=\n### )",
            implement_text,
            re.DOTALL,
        )
        assert coord_match
        coord_block = coord_match.group(0)
        # The stale phrasing was: "(STEP 15 is mandatory)" — must now also mention STEP 14
        # We assert the corrected phrasing is present.
        assert "STEP 14 and STEP 15 are mandatory" in coord_block, (
            "COORDINATOR FORBIDDEN LIST must use the corrected phrasing "
            "'STEP 14 and STEP 15 are mandatory' per Issue #1211."
        )


class TestLightPipelineCiaOrdering:
    """The LIGHT pipeline must dispatch CIA before its git operations (Issue #1211)."""

    def test_light_pipeline_cia_dispatch_before_git_push(
        self, implement_lines: list[str]
    ) -> None:
        """In the LIGHT pipeline, the CIA dispatch must appear before the final git push."""
        # Find the LIGHT PIPELINE MODE block
        light_start = None
        for idx, line in enumerate(implement_lines):
            if line.startswith("# LIGHT PIPELINE MODE"):
                light_start = idx
                break
        assert light_start is not None, "LIGHT PIPELINE MODE block not found"
        light_section = implement_lines[light_start:]

        # Locate the CIA dispatch line index (within the light section, not the
        # informational summary line that just names agents)
        cia_dispatch_pattern = re.compile(
            r'subagent_type\s*=\s*"continuous-improvement-analyst"'
        )
        cia_idx = None
        for idx, line in enumerate(light_section):
            if cia_dispatch_pattern.search(line):
                cia_idx = idx
                break
        assert cia_idx is not None, (
            "LIGHT pipeline must contain a CIA dispatch per Issue #1211 ordering."
        )

        # Locate the git push line (which represents the commit/push step)
        push_idx = None
        for idx, line in enumerate(light_section):
            if "git push origin" in line:
                push_idx = idx
                break
        assert push_idx is not None, "LIGHT pipeline git push line not found"

        assert cia_idx < push_idx, (
            f"In LIGHT pipeline, CIA dispatch (offset {cia_idx}) must appear "
            f"BEFORE the git push (offset {push_idx}) so the agent-completeness "
            f"gate is satisfied before the commit/push (Issue #1211)."
        )

    def test_light_pipeline_step_l4_5_exists(self, implement_lines: list[str]) -> None:
        """The LIGHT pipeline must have a STEP L4.5 (CIA) inserted between L4 and L5."""
        try:
            l4_5_line = _find_header_line(implement_lines, "### STEP L4.5:")
        except AssertionError:
            pytest.fail(
                "STEP L4.5 header missing from LIGHT pipeline — required to "
                "mirror the STEP 12.5 ordering fix (Issue #1211)."
            )
        l4_line = _find_header_line(implement_lines, "### STEP L4:")
        l5_line = _find_header_line(implement_lines, "### STEP L5:")
        assert l4_line < l4_5_line < l5_line, (
            f"STEP L4.5 (line {l4_5_line}) must appear between STEP L4 "
            f"(line {l4_line}) and STEP L5 (line {l5_line})."
        )
