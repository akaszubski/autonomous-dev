"""Regression tests for /implement pipeline step ordering — Issues #1211, #1148, #1181, #1210, #1073, #1145, #1155.

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

Issue #1210: The #1285 -> #1286 -> #1287 -> #1288 fix chain on 2026-06-11
all chased the same PROD writeback failure. Each fix validated green in unit
tests yet failed in PROD due to test-vs-PROD data divergence. Fix: STEP F4.7
PROD verification checklist after deploy.

Issue #1073: LIGHT mode deliberately skips plan-critic to trade scrutiny
for speed. For most LIGHT plans this is correct, but a subset are complex
enough that the minimalism axis alone would have caught real
over-engineering (observed in #1072: 24:43 implementer run). Fix: insert
STEP L2.6 as a budget plan-critic invocation gated on a complexity
heuristic (plan_word_count > 400 OR estimated_file_changes > 5).

Issue #1145: Plan-critic returned REVISE on the #1142 first plan (composite
2.0/3.0). The default 3-round budget caught the initial problems but cannot
catch a revision that addresses one finding while re-introducing another
under pressure to satisfy the critic's checklist. Fix: for plans touching
security-sensitive paths (hooks/*.py, lib/quality_persistence_enforcer.py,
etc.), increase max rounds from 3 to 5.

Issue #1155: The 5.5a skip triggered on the macro plan
.claude/plans/1260-cycle5-audit-fixes.md which self-assessed its verdict
as 'PROCEED (provisional)' and included the note 'Awaits plan-critic at
/implement time.' Fix: 5.5a skip does NOT fire when the plan's Critique
History contains 'provisional', '(provisional)', or 'awaits plan-critic'
(case-insensitive). plan.md secondary edit documents the verdict-authorship
contract.

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


# --- Issue #1073: LIGHT mode conditional plan-critic (STEP L2.6) ---


def _light_pipeline_full_text(implement_lines: list[str]) -> str:
    """Return the full LIGHT PIPELINE MODE block (from header to EOF).

    Used by Issue #1073 tests to assert STEP L2.6 prose lives inside the LIGHT
    pipeline block (not accidentally inserted into the FULL pipeline).
    """
    light_start: int | None = None
    for idx, line in enumerate(implement_lines):
        if line.startswith("# LIGHT PIPELINE MODE"):
            light_start = idx
            break
    assert light_start is not None, "LIGHT PIPELINE MODE block not found"
    return "\n".join(implement_lines[light_start:])


def _step_l2_6_section_text(implement_lines: list[str]) -> str:
    """Return the STEP L2.6 section bounded by its header and the next ### header."""
    start_idx = _find_header_line(implement_lines, "### STEP L2.6:")
    end_idx = len(implement_lines)
    # 1-indexed -> 0-indexed for slicing
    for idx in range(start_idx, len(implement_lines)):
        if implement_lines[idx].startswith("### STEP") and idx + 1 != start_idx:
            end_idx = idx
            break
    # start_idx is 1-indexed; slice from start_idx-1 to end_idx
    return "\n".join(implement_lines[start_idx - 1:end_idx])


class TestLightModeConditionalPlanCritic1073:
    """STEP L2.6 must add a budget plan-critic invocation in LIGHT mode (Issue #1073).

    Issue #1073: LIGHT mode (--light) deliberately skips plan-critic for speed.
    For most light-mode plans this is correct, but a subset are complex enough
    that the minimalism axis alone would have caught real over-engineering
    (observed in #1072: implementer ran 24:43, ~8x average, due to a plan that
    over-abstracted a single-use constant and split a parametrize-shaped test
    into 13 individual functions).

    Fix #1073: insert STEP L2.6 between STEP L2.5 (Plan Structural Validation)
    and STEP L3 (Implementer). Activation: plan_word_count > 400 OR
    estimated_file_changes > 5. Configuration: 1 round, minimalism axis only,
    Haiku, 60s hard cap. Verdict: PROCEED continues, REVISE re-invokes planner
    once (no loop), BLOCKED blocks.
    """

    def test_light_mode_has_step_l2_6_conditional_plan_critic_for_1073(
        self, implement_lines: list[str]
    ) -> None:
        """STEP L2.6 header must exist inside the LIGHT PIPELINE MODE block (Issue #1073)."""
        # 1. STEP L2.6 header must appear
        try:
            l2_6_line = _find_header_line(implement_lines, "### STEP L2.6:")
        except AssertionError:
            pytest.fail(
                "STEP L2.6 header missing from LIGHT PIPELINE MODE — required by "
                "Issue #1073 to add a budget plan-critic for complex LIGHT plans."
            )

        # 2. Must be between STEP L2.5 and STEP L3
        l2_5_line = _find_header_line(implement_lines, "### STEP L2.5:")
        l3_line = _find_header_line(implement_lines, "### STEP L3:")
        assert l2_5_line < l2_6_line < l3_line, (
            f"STEP L2.6 (line {l2_6_line}) must appear BETWEEN STEP L2.5 "
            f"(line {l2_5_line}) and STEP L3 (line {l3_line}) per Issue #1073."
        )

        # 3. STEP L2.6 must live inside the LIGHT PIPELINE MODE block
        light_text = _light_pipeline_full_text(implement_lines)
        assert "### STEP L2.6:" in light_text, (
            "STEP L2.6 must live inside the LIGHT PIPELINE MODE block, not the "
            "FULL pipeline — Issue #1073 targets LIGHT mode only."
        )

    def test_step_l2_6_activation_thresholds_for_1073(
        self, implement_lines: list[str]
    ) -> None:
        """STEP L2.6 prose must reference all four configuration knobs (Issue #1073)."""
        section = _step_l2_6_section_text(implement_lines)

        # Activation thresholds: word count threshold AND file count threshold
        assert "400" in section, (
            "STEP L2.6 must reference the 400-word activation threshold "
            "(Issue #1073)."
        )
        assert "> 5" in section or " 5 " in section or "or 5" in section.lower(), (
            "STEP L2.6 must reference the 5-file activation threshold "
            "(Issue #1073)."
        )

        # Single-axis configuration: minimalism only
        assert "minimalism" in section.lower(), (
            "STEP L2.6 must restrict critique to the minimalism axis only "
            "(Issue #1073)."
        )

        # Model selection: Haiku for budget
        assert "haiku" in section.lower(), (
            "STEP L2.6 must specify model='haiku' for the budget invocation "
            "(Issue #1073)."
        )

        # Timeout budget: 60 seconds hard cap
        assert "60" in section, (
            "STEP L2.6 must specify a 60-second hard cap (Issue #1073)."
        )

    def test_step_l2_6_references_issue_1073(
        self, implement_lines: list[str]
    ) -> None:
        """STEP L2.6 section must reference Issue #1073 inline."""
        section = _step_l2_6_section_text(implement_lines)
        assert "#1073" in section, (
            "STEP L2.6 must reference Issue #1073 inline so the motivation for "
            "the LIGHT-mode budget plan-critic is discoverable when reading the "
            "spec."
        )


# --- Issue #1145: Security-sensitive plan-critic rounds escalation (STEP 5.5b) ---


def _step_5_5_section_text(implement_lines: list[str]) -> str:
    """Return the STEP 5.5 section text bounded by its header and STEP 6."""
    start_idx = _find_header_line(implement_lines, "### STEP 5.5:")
    end_idx = len(implement_lines)
    for idx in range(start_idx, len(implement_lines)):
        if implement_lines[idx].startswith("### STEP 6:") and idx + 1 != start_idx:
            end_idx = idx
            break
    return "\n".join(implement_lines[start_idx - 1:end_idx])


class TestSecuritySensitivePlanCriticRounds1145:
    """STEP 5.5b must escalate plan-critic rounds for security-sensitive plans (Issue #1145).

    Issue #1145: Plan-critic returned REVISE on the #1142 first plan (composite
    2.0/3.0), catching three independently actionable problems in a single
    pass. #1142 was a hook modification to unified_pre_tool.py — a
    security-enforcement file. The default 3-round budget caught the initial
    problems but cannot catch a revision that addresses finding #1 while
    re-introducing finding #2 under pressure to satisfy the critic's checklist.

    Fix #1145: when the plan touches security-sensitive paths (hooks/*.py,
    lib/quality_persistence_enforcer.py, lib/*security*, lib/*auth*,
    lib/*token*, config/auto_approve_policy.json, templates/settings.*.json),
    increase the maximum rounds from 3 to 5. The additional rounds fire ONLY
    if the critic continues to return REVISE — a clean PROCEED still
    terminates the loop normally.
    """

    def test_step_5_5b_has_security_sensitive_escalation_for_1145(
        self, implement_lines: list[str]
    ) -> None:
        """STEP 5.5b must contain the 3-to-5 rounds escalation prose with #1145 reference."""
        section = _step_5_5_section_text(implement_lines)

        # Issue reference must be present
        assert "#1145" in section, (
            "STEP 5.5b must reference Issue #1145 inline so the security-sensitive "
            "escalation motivation is discoverable when reading the spec."
        )

        # The escalation prose must mention both "3" and "5" rounds
        lowered = section.lower()
        assert "3 to 5" in lowered or "from 3 to 5" in lowered, (
            "STEP 5.5b must contain '3 to 5' or 'from 3 to 5' to describe the "
            "rounds escalation for security-sensitive plans (Issue #1145)."
        )

        # The escalation must reference the security-sensitive path patterns
        # `hooks/*.py` is the canonical example cited in the issue body
        assert "hooks/*.py" in section, (
            "STEP 5.5b must reference the `hooks/*.py` pattern as a "
            "security-sensitive trigger for the 3-to-5 rounds escalation "
            "(Issue #1145)."
        )

        # The 5.5d FORBIDDEN block must also block the 3-round cap when
        # security-sensitive paths are touched
        assert "cap rounds at 3" in section.lower() or (
            "rounds at 3" in section.lower() and "#1145" in section
        ), (
            "STEP 5.5d FORBIDDEN must include a directive against capping "
            "rounds at 3 for security-sensitive plans (Issue #1145)."
        )


# --- Issue #1155: Plan-critic skip negative filter (STEP 5.5a) ---


class TestPlanCriticSkipNegativeFilter1155:
    """STEP 5.5a must filter self-assessed provisional verdicts (Issue #1155).

    Issue #1155: The 5.5a skip triggers when a plan contains 'Verdict: PROCEED'.
    The macro plan at .claude/plans/1260-cycle5-audit-fixes.md self-assessed its
    verdict as 'PROCEED (provisional)' and included the note 'Awaits plan-critic
    at /implement time.' The coordinator read the PROCEED marker, applied the
    skip, and ran without plan-critic — exactly the failure mode this filter
    prevents.

    Fix #1155: the skip does NOT fire when the plan's Critique History contains
    'provisional', '(provisional)', or 'awaits plan-critic' (case-insensitive).
    The plan-critic verdict must come from a completed adversarial round, not
    from the planner's self-assessment.
    """

    def test_step_5_5a_has_provisional_negative_filter_for_1155(
        self, implement_lines: list[str]
    ) -> None:
        """STEP 5.5a must contain the negative-filter marker substrings (Issue #1155)."""
        section = _step_5_5_section_text(implement_lines)

        # The negative filter must reference the three marker substrings
        # from the Issue #1155 spec.
        lowered = section.lower()
        assert "provisional" in lowered, (
            "STEP 5.5a negative filter must reference the `provisional` marker "
            "substring (Issue #1155)."
        )
        assert "awaits plan-critic" in lowered, (
            "STEP 5.5a negative filter must reference the `awaits plan-critic` "
            "marker substring (Issue #1155)."
        )

        # Inline reference to Issue #1155 so a future reader can find motivation
        assert "#1155" in section, (
            "STEP 5.5a must reference Issue #1155 inline so the motivation for "
            "the negative filter is discoverable when reading the spec."
        )

        # The 5.5d FORBIDDEN block must include a directive that blocks the
        # provisional-verdict skip
        assert "self-assessed" in lowered or "not adversarial" in lowered, (
            "STEP 5.5d FORBIDDEN must include a directive blocking the skip "
            "on self-assessed provisional verdicts (Issue #1155)."
        )


PLAN_MD = REPO_ROOT / "plugins" / "autonomous-dev" / "commands" / "plan.md"


@pytest.fixture(scope="module")
def plan_text() -> str:
    """Return the plan.md text content (cached per module)."""
    assert PLAN_MD.exists(), f"Expected {PLAN_MD} to exist"
    return PLAN_MD.read_text()


class TestPlanMdVerdictAuthorship1155:
    """plan.md must document verdict authorship — only plan-critic issues PROCEED (#1155)."""

    def test_plan_md_documents_verdict_authorship_for_1155(
        self, plan_text: str
    ) -> None:
        """plan.md must contain the verdict-authorship note referencing #1155.

        Issue #1155 secondary edit: a `Verdict: PROCEED` line must come from a
        completed plan-critic round, not from the planner's self-assessment.
        plan.md is the natural location to document this contract because it
        owns the round protocol that produces the verdict.
        """
        # The note must reference Issue #1155
        assert "#1155" in plan_text, (
            "plan.md must reference Issue #1155 inline so the verdict-authorship "
            "contract is discoverable from the planner spec."
        )

        # The note must explicitly call out the self-assessed / planner-authored
        # case as illegitimate
        lowered = plan_text.lower()
        assert "self-assessed" in lowered or "self-assessment" in lowered, (
            "plan.md verdict-authorship note must distinguish self-assessed "
            "verdicts from adversarial-round verdicts (Issue #1155)."
        )

        # The note must reference the three marker substrings that 5.5a's
        # negative filter detects so a planner knows what NOT to write
        assert "provisional" in lowered, (
            "plan.md verdict-authorship note must reference `provisional` so "
            "the planner knows this marker triggers the 5.5a fall-through "
            "(Issue #1155)."
        )
        assert "awaits plan-critic" in lowered, (
            "plan.md verdict-authorship note must reference `awaits plan-critic` "
            "so the planner knows this marker triggers the 5.5a fall-through "
            "(Issue #1155)."
        )


# ---------------------------------------------------------------------------
# Issue #1149 — Single-Run Resume Protocol
# ---------------------------------------------------------------------------

IMPLEMENT_RESUME_MD = (
    REPO_ROOT / "plugins" / "autonomous-dev" / "commands" / "implement-resume.md"
)


@pytest.fixture(scope="module")
def implement_resume_text() -> str:
    """Return the implement-resume.md text content (cached per module)."""
    assert IMPLEMENT_RESUME_MD.exists(), f"Expected {IMPLEMENT_RESUME_MD} to exist"
    return IMPLEMENT_RESUME_MD.read_text()


class TestSingleRunResumeProtocol1149:
    """implement-resume.md must document the single-run resume protocol (#1149).

    Issue #1149: the coordinator improvised a "ratify the cached plan" path
    when resuming after context-pressure interruption. The shortcut was
    functionally correct in the observed session but not a codified code
    path — there was no spec for HEAD-state verification, plan staleness,
    or run-lock acquisition on resume. This test locks the codified
    protocol so future edits cannot silently remove it.
    """

    def test_implement_resume_has_single_run_protocol_for_1149(
        self, implement_resume_text: str
    ) -> None:
        """implement-resume.md must contain the codified Single-Run Resume Protocol.

        The protocol section must define five required elements: an
        activation condition, the four pre-resume checks (HEAD hash,
        staging clean, alignment re-verification, run lock), the plan
        staleness gate (with 24h and 4h thresholds), state restoration,
        and a FORBIDDEN list — all referencing Issue #1149.
        """
        text = implement_resume_text

        # Section header must exist
        assert "Single-Run Resume Protocol" in text, (
            "implement-resume.md must contain a 'Single-Run Resume Protocol' "
            "section codifying the state-recovery sequence for run_id resume "
            "(Issue #1149)."
        )

        # Issue reference must be inline (in or near the section header)
        assert "#1149" in text, (
            "implement-resume.md Single-Run Resume Protocol must reference "
            "Issue #1149 inline so the codified protocol is discoverable from "
            "the issue."
        )

        # Required protocol elements — keywords from each of the five sections
        # of the codified protocol
        required_keywords = [
            "HEAD hash",        # pre-resume check 1
            "staging",          # pre-resume check 2 (staging clean)
            "alignment",        # pre-resume check 3 (alignment re-verification)
            "run lock",         # pre-resume check 4 (run lock available)
            "24 hour",          # staleness gate threshold
            "plan-critic",      # staleness gate: re-run plan-critic on security-sensitive paths
        ]
        for kw in required_keywords:
            assert kw.lower() in text.lower(), (
                f"implement-resume.md Single-Run Resume Protocol must mention "
                f"{kw!r} as a required check/threshold (Issue #1149)."
            )

        # FORBIDDEN list locks the known failure modes
        assert "FORBIDDEN" in text, (
            "implement-resume.md Single-Run Resume Protocol must include a "
            "FORBIDDEN list of the failure modes the protocol is codifying "
            "against (Issue #1149)."
        )

    def test_implement_md_step_0_cross_references_resume_protocol_for_1149(
        self, implement_text: str
    ) -> None:
        """implement.md STEP 0 must cross-reference the Single-Run Resume Protocol.

        STEP 0 routes `--resume <id>` based on the id form. The route to
        the single-run branch (16-char hex / legacy timestamp) must point
        to the codified protocol in implement-resume.md so the coordinator
        cannot improvise a different recovery sequence (Issue #1149).
        """
        # Locate STEP 0
        step_0_idx = implement_text.find("### STEP 0: Parse Mode and Route")
        assert step_0_idx >= 0, "STEP 0 header must exist in implement.md"

        # Look at the section that follows STEP 0 (until the next ### header)
        rest = implement_text[step_0_idx:]
        next_step_idx = rest.find("\n### ", 10)
        step_0_section = rest if next_step_idx < 0 else rest[:next_step_idx]

        # The cross-reference must mention either the protocol section name
        # or the file path AND the issue
        assert (
            "Single-Run Resume Protocol" in step_0_section
            or "implement-resume.md" in step_0_section
        ), (
            "implement.md STEP 0 must cross-reference either the "
            "'Single-Run Resume Protocol' section or implement-resume.md "
            "so the coordinator follows the codified protocol on run_id "
            "resume (Issue #1149)."
        )

        assert "#1149" in step_0_section, (
            "implement.md STEP 0 cross-reference to the Single-Run Resume "
            "Protocol must include the #1149 issue reference so the codified "
            "protocol is discoverable from STEP 0."
        )


# ---------------------------------------------------------------------------
# Issue #1040 — Documentation of SKIP_AGENT_COMPLETENESS_GATE bypass
# ---------------------------------------------------------------------------

CLAUDE_MD = REPO_ROOT / "CLAUDE.md"
HOOKS_MD = REPO_ROOT / "docs" / "HOOKS.md"


@pytest.fixture(scope="module")
def claude_md_text() -> str:
    """Return the repo-root CLAUDE.md text content (cached per module)."""
    assert CLAUDE_MD.exists(), f"Expected {CLAUDE_MD} to exist"
    return CLAUDE_MD.read_text()


@pytest.fixture(scope="module")
def hooks_md_text() -> str:
    """Return the docs/HOOKS.md text content (cached per module)."""
    assert HOOKS_MD.exists(), f"Expected {HOOKS_MD} to exist"
    return HOOKS_MD.read_text()


class TestBypassDocumentation1040:
    """CLAUDE.md and docs/HOOKS.md must document the agent-completeness gate bypasses (#1040).

    Issue #1040: the `SKIP_AGENT_COMPLETENESS_GATE` env var and
    `/tmp/skip_agent_completeness_gate` file marker bypasses are
    implemented in `unified_pre_tool.py` but were undocumented in the
    operator-facing docs (CLAUDE.md, docs/HOOKS.md). An operator who
    needs to commit a hotfix outside the normal pipeline would either
    re-discover the bypass through code spelunking or improvise around
    the gate. This test locks the documentation so the bypass remains
    visible and the audit trail is discoverable.
    """

    def test_claude_md_documents_skip_gate_bypass_for_1040(
        self, claude_md_text: str
    ) -> None:
        """CLAUDE.md Maintainer Escape Hatches must document the bypass forms.

        The three bypass forms (env var, inline command-string env var,
        file marker) and the audit-log location must be documented in
        CLAUDE.md so an operator can find them without reading hook
        source. Reference Issue #1040 inline.
        """
        text = claude_md_text

        # Env var name must appear
        assert "SKIP_AGENT_COMPLETENESS_GATE" in text, (
            "CLAUDE.md must document the `SKIP_AGENT_COMPLETENESS_GATE` "
            "env-var bypass (Issue #1040)."
        )

        # File marker form must appear
        assert "/tmp/skip_agent_completeness_gate" in text, (
            "CLAUDE.md must document the `/tmp/skip_agent_completeness_gate` "
            "file marker bypass form (Issue #1040)."
        )

        # Issue reference must be inline
        assert "#1040" in text, (
            "CLAUDE.md bypass documentation must reference Issue #1040 inline "
            "so the codified documentation is discoverable from the issue."
        )

        # Audit-log location should be referenced (any of these substrings)
        lowered = text.lower()
        assert (
            "logs/activity" in lowered
            or "activity/" in lowered
            or "activity log" in lowered
        ), (
            "CLAUDE.md bypass documentation must point at the audit-log "
            "location (`.claude/logs/activity/`) so operators know where "
            "the bypass is recorded (Issue #1040)."
        )

    def test_hooks_md_documents_bypass_mechanisms_for_1040(
        self, hooks_md_text: str
    ) -> None:
        """docs/HOOKS.md must document the bypass mechanisms with audit context.

        The bypass mechanisms section must list the env-var form, file
        marker form, and the audit-log behavior (so an operator can
        distinguish legitimate skips from gaming). Reference Issue
        #1040 inline.
        """
        text = hooks_md_text

        # Env var name must appear
        assert "SKIP_AGENT_COMPLETENESS_GATE" in text, (
            "docs/HOOKS.md must document the `SKIP_AGENT_COMPLETENESS_GATE` "
            "env-var bypass for the agent-completeness gate (Issue #1040)."
        )

        # Audit notion must appear (the bypass is logged, distinguishable
        # from a legitimate pass)
        lowered = text.lower()
        assert "audit" in lowered, (
            "docs/HOOKS.md bypass documentation must reference the audit "
            "trail (so legitimate skips are distinguishable from gaming) "
            "(Issue #1040)."
        )

        # Issue reference must be inline
        assert "#1040" in text, (
            "docs/HOOKS.md bypass documentation must reference Issue #1040 "
            "inline so the codified documentation is discoverable from the "
            "issue."
        )


# ---------------------------------------------------------------------------
# Issue #1055 — Evidence Manifest coordinator-side gate
# ---------------------------------------------------------------------------

IMPLEMENTER_MD = (
    REPO_ROOT / "plugins" / "autonomous-dev" / "agents" / "implementer.md"
)


@pytest.fixture(scope="module")
def implementer_md_text() -> str:
    """Return the implementer.md text content (cached per module)."""
    assert IMPLEMENTER_MD.exists(), f"Expected {IMPLEMENTER_MD} to exist"
    return IMPLEMENTER_MD.read_text()


def _step_8_section_text(implement_lines: list[str]) -> str:
    """Return the STEP 8 section text bounded by the STEP 8 header and STEP 8.5.

    The STEP 8 section is where the Evidence Manifest output-validation gate
    must live (between Plan-Implementation Alignment and STEP 8.5).
    """
    start_idx = _find_header_line(implement_lines, "### STEP 8:")
    end_idx = len(implement_lines)
    for idx in range(start_idx, len(implement_lines)):
        if implement_lines[idx].startswith("### STEP 8.5:") and idx + 1 != start_idx:
            end_idx = idx
            break
    return "\n".join(implement_lines[start_idx - 1:end_idx])


class TestEvidenceManifestGate1055:
    """STEP 8 OUTPUT VALIDATION GATE must check for the Evidence Manifest table (#1055).

    Issue #1055: The implementer agent prompt defines a HARD GATE requiring a
    structured Evidence Manifest table in full pipeline mode, but the gate was
    prompt-advisory only — there was no coordinator or hook check that verified
    the manifest was emitted. In the M1 batch (#1022) the reviewer explicitly
    flagged the missing manifest, but the pipeline did not block.

    Fix #1055: STEP 8 OUTPUT VALIDATION GATE: Evidence Manifest subsection
    converts the advisory check into a mechanical coordinator-side gate. The
    gate checks the implementer output for the literal table header
    `| File | State | Verification Signal |`, re-invokes the implementer once
    if missing, and BLOCKS the pipeline if still absent after the remediation
    cycle. Full pipeline mode only — `--light` and `--fix` modes treat the
    manifest as RECOMMENDED per the agent spec.

    These tests lock the corrected spec text so the gate cannot be silently
    re-downgraded to advisory.
    """

    def test_step_8_has_evidence_manifest_gate_for_1055(
        self, implement_lines: list[str]
    ) -> None:
        """STEP 8 must contain the Evidence Manifest output validation gate (#1055).

        The gate header, the marker substring (table header line), and the
        #1055 issue reference must all appear inside the STEP 8 section so the
        check is discoverable when reading the spec.
        """
        section = _step_8_section_text(implement_lines)

        # 1. The gate header must appear as a subsection of STEP 8
        assert "OUTPUT VALIDATION GATE: Evidence Manifest" in section, (
            "STEP 8 must contain an 'OUTPUT VALIDATION GATE: Evidence Manifest' "
            "subsection per Issue #1055 — converts the advisory-only check "
            "into a mechanical coordinator-side gate."
        )

        # 2. The literal table header marker substring must appear
        assert "| File | State | Verification Signal |" in section, (
            "STEP 8 Evidence Manifest gate must specify the exact marker "
            "substring `| File | State | Verification Signal |` per Issue "
            "#1055 — this is the literal table header the coordinator searches "
            "for in the implementer output."
        )

        # 3. Issue #1055 must be referenced inline
        assert "#1055" in section, (
            "STEP 8 Evidence Manifest gate must reference Issue #1055 inline "
            "so the motivation for the gate is discoverable when reading the "
            "spec."
        )

    def test_step_8_evidence_manifest_gate_has_remediation_path_for_1055(
        self, implement_lines: list[str]
    ) -> None:
        """STEP 8 Evidence Manifest gate must document the remediation + BLOCK paths (#1055).

        The gate prose must describe re-invocation of the implementer in
        REMEDIATION MODE on the first failure and a BLOCK outcome if the
        manifest is still missing after the remediation cycle. This locks the
        spec text so the gate cannot be silently re-downgraded to a warning.
        """
        section = _step_8_section_text(implement_lines)

        # The gate must mention re-invocation OR remediation language
        lowered = section.lower()
        assert "re-invoke" in lowered or "remediation" in lowered, (
            "STEP 8 Evidence Manifest gate must document re-invocation in "
            "REMEDIATION MODE on the first missing-manifest failure per "
            "Issue #1055."
        )

        # The gate must include a BLOCK handling clause for the post-remediation
        # failure case (still missing after the single cycle)
        assert "BLOCK" in section, (
            "STEP 8 Evidence Manifest gate must include a BLOCK handling "
            "clause for the post-remediation failure case per Issue #1055."
        )

        # The exact BLOCKED message substring must appear so a future edit
        # cannot soften the failure outcome to a warning
        assert "BLOCKED: Implementer output is missing the Evidence Manifest" in section, (
            "STEP 8 Evidence Manifest gate must contain the exact BLOCK "
            "message string ('BLOCKED: Implementer output is missing the "
            "Evidence Manifest...') per Issue #1055 so the failure outcome "
            "cannot be silently softened."
        )

    def test_step_8_evidence_manifest_gate_is_full_pipeline_only_for_1055(
        self, implement_lines: list[str]
    ) -> None:
        """STEP 8 Evidence Manifest gate must be full-pipeline-only (#1055).

        Per the implementer agent spec, the Evidence Manifest is REQUIRED in
        full pipeline mode but RECOMMENDED in `--light` and `--fix` modes.
        The coordinator gate prose must explicitly note that the check does
        NOT apply to `--light` and `--fix`.
        """
        section = _step_8_section_text(implement_lines)

        # The gate must explicitly note "full pipeline mode only" activation
        lowered = section.lower()
        assert "full pipeline mode only" in lowered or "full pipeline mode" in lowered, (
            "STEP 8 Evidence Manifest gate must explicitly state that it "
            "activates in 'full pipeline mode only' per Issue #1055."
        )

        # The gate must explicitly mention BOTH --light AND --fix as
        # non-applicable so the coordinator does not improvise activation
        # on the wrong mode
        assert "--light" in section, (
            "STEP 8 Evidence Manifest gate must explicitly reference --light "
            "as a non-applicable mode per Issue #1055."
        )
        assert "--fix" in section, (
            "STEP 8 Evidence Manifest gate must explicitly reference --fix "
            "as a non-applicable mode per Issue #1055."
        )

    def test_implementer_md_cross_references_coordinator_gate_for_1055(
        self, implementer_md_text: str
    ) -> None:
        """agents/implementer.md HARD GATE section must cross-reference the coordinator (#1055).

        The agent prompt's HARD GATE: Evidence Manifest Output section must
        contain a cross-reference note pointing at the coordinator-side gate
        in commands/implement.md STEP 8. This makes the mechanical-vs-advisory
        status discoverable to the implementer agent at invocation time.
        """
        text = implementer_md_text

        # The HARD GATE section header must exist (precondition for the
        # cross-reference being meaningful)
        assert "## HARD GATE: Evidence Manifest Output" in text, (
            "agents/implementer.md must retain the 'HARD GATE: Evidence "
            "Manifest Output' section header — the cross-reference note "
            "lives inside that section (Issue #1055)."
        )

        # The cross-reference note must call out coordinator-side enforcement
        assert "Coordinator-side enforcement" in text, (
            "agents/implementer.md HARD GATE: Evidence Manifest Output must "
            "contain a 'Coordinator-side enforcement' note pointing at the "
            "mechanical gate in commands/implement.md STEP 8 (Issue #1055)."
        )

        # The cross-reference must mention STEP 8 explicitly
        assert "STEP 8" in text, (
            "agents/implementer.md HARD GATE: Evidence Manifest Output "
            "cross-reference must mention STEP 8 explicitly so the agent "
            "knows where the coordinator-side gate lives (Issue #1055)."
        )

        # The cross-reference must reference Issue #1055 inline
        assert "#1055" in text, (
            "agents/implementer.md HARD GATE: Evidence Manifest Output "
            "cross-reference must reference Issue #1055 inline so the "
            "motivation for the mechanical conversion is discoverable."
        )
