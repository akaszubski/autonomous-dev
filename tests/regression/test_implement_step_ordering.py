"""Regression tests for /implement pipeline step ordering — Issues #1211, #1148, #1181.

Issue #1211: The `unified_pre_tool.py` agent-completeness gate blocks the
git commit (STEP 13) until `continuous-improvement-analyst` (CIA) has
completed. Previously the pipeline spec placed CIA at STEP 15, after the
commit, which created a structural ordering conflict that every standard
pipeline run resolved implicitly through coordinator improvisation.

Fix #1211: Move CIA dispatch to STEP 12.5 (before STEP 13 commit). Repurpose
STEP 15 as cleanup-only.

Issue #1148: When STEP 10 selects parallel validation mode, reviewer and
security-auditor were still emitted in sequential assistant messages —
defeating the parallel routing decision. Fix: spec must explicitly require
single-message dispatch of all three validators.

Issue #1181: The `--light` pipeline lacks STEP 10's sequential security
flow. A LIGHT run that detected security-sensitive paths improvised a
partial security-auditor dispatch and ended up dispatching doc-master 98s
BEFORE security-auditor (session 09f09286 pipeline 1). Fix: LIGHT mode must
escalate to FULL pipeline when security-sensitive paths are detected; the
spec must forbid improvising security-auditor inside LIGHT mode.

These tests lock the corrected spec text so that any future edit that
re-introduces a conflict trips a regression.
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


def _step_10_parallel_text(implement_lines: list[str]) -> str:
    """Return the STEP 10 parallel-mode section text.

    Bounded by the 'DEFAULT: Parallel mode' marker line and the
    'SEQUENTIAL mode' marker line that follows.
    """
    start_idx: int | None = None
    end_idx: int | None = None
    for idx, line in enumerate(implement_lines):
        if "DEFAULT: Parallel mode" in line and start_idx is None:
            start_idx = idx
        elif start_idx is not None and "SEQUENTIAL mode" in line:
            end_idx = idx
            break
    assert start_idx is not None, "STEP 10 DEFAULT: Parallel mode marker not found"
    if end_idx is None:
        end_idx = len(implement_lines)
    return "\n".join(implement_lines[start_idx:end_idx])


def _light_pipeline_intro_text(implement_lines: list[str]) -> str:
    """Return the LIGHT PIPELINE MODE intro text.

    Bounded by '# LIGHT PIPELINE MODE' and the first '### STEP L0:' header.
    """
    start_idx: int | None = None
    end_idx: int | None = None
    for idx, line in enumerate(implement_lines):
        if line.startswith("# LIGHT PIPELINE MODE") and start_idx is None:
            start_idx = idx
        elif start_idx is not None and line.startswith("### STEP L0:"):
            end_idx = idx
            break
    assert start_idx is not None, "LIGHT PIPELINE MODE header not found"
    assert end_idx is not None, "STEP L0 header not found after LIGHT PIPELINE MODE"
    return "\n".join(implement_lines[start_idx:end_idx])


class TestParallelDispatchSingleMessage1148:
    """STEP 10 parallel mode must require single-message dispatch (Issue #1148)."""

    def test_step_10_parallel_mode_requires_single_message_dispatch_for_1148(
        self, implement_lines: list[str]
    ) -> None:
        """STEP 10 parallel mode prose must require single-message dispatch and reference #1148.

        Issue #1148: When the coordinator selects parallel validation mode,
        reviewer + security-auditor + doc-master MUST be invoked in a single
        assistant message. Sequential emission defeats the parallel routing.
        """
        parallel_section = _step_10_parallel_text(implement_lines)

        # The phrase 'single message' (case-insensitive) must appear
        assert "single message" in parallel_section.lower(), (
            "STEP 10 parallel mode must explicitly require single-message dispatch "
            "of reviewer/security-auditor/doc-master (Issue #1148)."
        )

        # Issue #1148 must be referenced inline so motivation is discoverable
        assert "#1148" in parallel_section, (
            "STEP 10 parallel mode must reference Issue #1148 inline so the "
            "motivation for the single-message rule is discoverable."
        )

    def test_step_10_parallel_mode_forbidden_list_blocks_sequential_for_1148(
        self, implement_lines: list[str]
    ) -> None:
        """STEP 10 parallel mode FORBIDDEN list must block sequential emission (Issue #1148).

        The FORBIDDEN block must include language that prevents the coordinator
        from emitting reviewer and security-auditor in sequential messages when
        parallel mode is selected.
        """
        parallel_section = _step_10_parallel_text(implement_lines)

        # The FORBIDDEN block must exist in the parallel-mode section
        assert "FORBIDDEN" in parallel_section, (
            "STEP 10 parallel mode must have a FORBIDDEN block."
        )

        # The FORBIDDEN block must reference sequential emission of reviewer
        # and security-auditor — the exact failure mode from Issue #1148.
        lowered = parallel_section.lower()
        assert "sequential message" in lowered or "sequential messages" in lowered, (
            "STEP 10 parallel mode FORBIDDEN block must explicitly forbid "
            "emitting reviewer and security-auditor in sequential messages "
            "when parallel mode is selected (Issue #1148)."
        )
        # The FORBIDDEN block must mention both validators by name
        assert "reviewer" in lowered and "security-auditor" in lowered, (
            "STEP 10 parallel mode FORBIDDEN block must name both reviewer "
            "and security-auditor in the sequential-emission prohibition."
        )


class TestLightModeSecurityEscalation1181:
    """LIGHT mode must escalate to FULL pipeline on security-sensitive paths (Issue #1181)."""

    def test_light_mode_has_security_precondition_for_1181(
        self, implement_lines: list[str]
    ) -> None:
        """LIGHT PIPELINE MODE must contain a security-sensitive activation precondition (Issue #1181).

        Issue #1181: --light must escalate to FULL when security-sensitive
        paths are detected. The spec must document this precondition before
        STEP L0 so the coordinator routes correctly.
        """
        light_intro = _light_pipeline_intro_text(implement_lines)

        # A precondition marker must exist
        assert "precondition" in light_intro.lower(), (
            "LIGHT PIPELINE MODE must contain an activation precondition "
            "(Issue #1181)."
        )

        # Must reference security-sensitive paths
        assert "security-sensitive" in light_intro.lower(), (
            "LIGHT PIPELINE MODE precondition must reference security-sensitive "
            "paths so the coordinator knows when to escalate (Issue #1181)."
        )

        # Must require escalation to FULL pipeline
        assert "FULL pipeline" in light_intro or "FULL mode" in light_intro, (
            "LIGHT PIPELINE MODE precondition must require escalation to FULL "
            "pipeline mode when security-sensitive paths are detected (Issue #1181)."
        )

        # Must reference Issue #1181 inline
        assert "#1181" in light_intro, (
            "LIGHT PIPELINE MODE precondition must reference Issue #1181 inline "
            "so the motivation for the security-sensitive escalation is discoverable."
        )

    def test_light_mode_forbidden_security_improvisation_for_1181(
        self, implement_lines: list[str]
    ) -> None:
        """LIGHT mode must forbid improvising security-auditor dispatch (Issue #1181).

        The LIGHT intro must contain a FORBIDDEN directive that blocks the
        coordinator from partial-dispatching security-auditor inside LIGHT
        mode (the failure mode observed in session 09f09286 pipeline 1).
        """
        light_intro = _light_pipeline_intro_text(implement_lines)

        # FORBIDDEN block must exist in the LIGHT intro
        assert "FORBIDDEN" in light_intro, (
            "LIGHT PIPELINE MODE must contain a FORBIDDEN directive against "
            "improvising security-auditor dispatch (Issue #1181)."
        )

        # Must specifically forbid improvising security-auditor
        lowered = light_intro.lower()
        assert "improvise" in lowered or "improvising" in lowered, (
            "LIGHT PIPELINE MODE FORBIDDEN block must use 'improvise' language "
            "to block partial security-auditor dispatch (Issue #1181)."
        )
        assert "security-auditor" in lowered, (
            "LIGHT PIPELINE MODE FORBIDDEN block must name security-auditor "
            "explicitly (Issue #1181)."
        )

        # Must reference Issue #1181 in the FORBIDDEN block
        # (the precondition above already references #1181; the FORBIDDEN
        # paragraph must also reference it so a future reader who lands on
        # the FORBIDDEN can find the issue without scrolling.)
        # Extract the FORBIDDEN paragraph and check inline
        forbidden_idx = light_intro.find("FORBIDDEN")
        forbidden_paragraph = light_intro[forbidden_idx:]
        assert "#1181" in forbidden_paragraph, (
            "LIGHT PIPELINE MODE FORBIDDEN paragraph must reference Issue "
            "#1181 inline."
        )


# --- Issue #1210: --fix mode PROD verification (STEP F4.7) ---

IMPLEMENT_FIX_MD = REPO_ROOT / "plugins" / "autonomous-dev" / "commands" / "implement-fix.md"


@pytest.fixture(scope="module")
def implement_fix_text() -> str:
    """Return the implement-fix.md text content (cached per module)."""
    assert IMPLEMENT_FIX_MD.exists(), f"Expected {IMPLEMENT_FIX_MD} to exist"
    return IMPLEMENT_FIX_MD.read_text()


@pytest.fixture(scope="module")
def implement_fix_lines() -> list[str]:
    """Return the implement-fix.md text as a list of lines (cached per module)."""
    return IMPLEMENT_FIX_MD.read_text().splitlines()


class TestImplementFixProdVerification1210:
    """STEP F4.7 must enforce a PROD verification checklist for --fix pipelines (#1210).

    Issue #1210: The #1285 → #1286 → #1287 → #1288 chain on 2026-06-11 was four
    consecutive --fix pipelines that all chased the same PROD writeback failure.
    Each fix validated green in unit tests yet failed in PROD due to test-vs-PROD
    data divergence. A mandatory PROD verification step after deploy would have
    caught the regression at #1285 and collapsed the chain.

    These tests lock the spec text for STEP F4.7 so the checklist gate cannot
    be silently removed in a future edit.
    """

    def test_implement_fix_has_step_f4_7_prod_verification_for_1210(
        self, implement_fix_text: str
    ) -> None:
        """STEP F4.7 header + activation trigger + recording format must be present (#1210)."""
        # 1. STEP F4.7 header must appear
        assert "### STEP F4.7:" in implement_fix_text, (
            "STEP F4.7 header missing — required by Issue #1210 to enforce "
            "PROD verification after --fix deploy."
        )

        # 2. The header (or section body) must mention "PROD Verification" (case-insensitive)
        assert "prod verification" in implement_fix_text.lower(), (
            "STEP F4.7 must mention 'PROD Verification' so the section's "
            "purpose is discoverable (#1210)."
        )

        # 3. Activation trigger keywords must be present (substring, case-insensitive)
        lowered = implement_fix_text.lower()
        for keyword in ("sql", "execution", "trade", "payment"):
            assert keyword in lowered, (
                f"STEP F4.7 activation trigger missing keyword {keyword!r} — "
                f"required by Issue #1210 to define when PROD verification "
                f"is mandatory."
            )

        # 4. Recording format must be present
        assert "VERIFIED:" in implement_fix_text, (
            "STEP F4.7 must define the 'VERIFIED: {query} → {result}' "
            "recording format per Issue #1210."
        )

        # 5. #1210 must be referenced inline
        assert "#1210" in implement_fix_text, (
            "STEP F4.7 must reference Issue #1210 inline so the motivation "
            "is discoverable."
        )

        # 6. At least one of the 4-fix-chain issues must be referenced as
        #    motivating evidence
        chain_issues = ("#1285", "#1286", "#1287", "#1288")
        assert any(issue in implement_fix_text for issue in chain_issues), (
            f"STEP F4.7 must reference at least one of the 4-fix chain "
            f"issues {chain_issues} as motivating evidence per Issue #1210."
        )

    def test_implement_fix_forbidden_list_blocks_f4_7_skip_for_1210(
        self, implement_fix_text: str
    ) -> None:
        """The top-of-file FORBIDDEN list must block skipping STEP F4.7 (#1210).

        The Pipeline Integrity FORBIDDEN block at the top of implement-fix.md
        must include a bullet that prohibits skipping STEP F4.7 when the
        activation trigger matches, and that bullet must reference #1210.
        """
        # The Pipeline Integrity FORBIDDEN block is bounded by its heading
        # and the next "### " or "## " heading. Capture it by regex.
        pipeline_integrity_match = re.search(
            r"### Pipeline Integrity.*?(?=\n## |\n### )",
            implement_fix_text,
            re.DOTALL,
        )
        assert pipeline_integrity_match, (
            "Pipeline Integrity section not found in implement-fix.md — "
            "required to host the STEP F4.7 skip prohibition (#1210)."
        )
        block = pipeline_integrity_match.group(0)

        # The block must reference STEP F4.7
        assert "STEP F4.7" in block, (
            "Pipeline Integrity FORBIDDEN block must reference STEP F4.7 "
            "to block coordinator from skipping PROD verification (#1210)."
        )

        # The block must reference Issue #1210 on the F4.7 bullet
        assert "#1210" in block, (
            "Pipeline Integrity FORBIDDEN block must reference Issue #1210 "
            "on the STEP F4.7 skip prohibition so the motivation is "
            "discoverable."
        )

    def test_implement_fix_step_f4_7_is_between_f4_and_f5_for_1210(
        self, implement_fix_lines: list[str]
    ) -> None:
        """STEP F4.7 must appear between STEP F4 and STEP F5 in document order (#1210)."""
        f4_line = _find_header_line(implement_fix_lines, "### STEP F4:")
        f4_7_line = _find_header_line(implement_fix_lines, "### STEP F4.7:")
        f5_line = _find_header_line(implement_fix_lines, "### STEP F5:")

        assert f4_line < f4_7_line < f5_line, (
            f"STEP F4.7 (line {f4_7_line}) must appear BETWEEN STEP F4 "
            f"(line {f4_line}) and STEP F5 (line {f5_line}) per Issue #1210 "
            f"placement. The PROD verification checklist must run after the "
            f"reviewer/doc-master gate but before CIA dispatch."
        )
