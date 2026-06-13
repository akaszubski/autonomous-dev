#!/usr/bin/env python3
"""Regression tests locking behavioral invariants in agent prompt files.

These tests prevent future agent-prompt refactors from accidentally dropping
behavioral guidance added in response to specific issues. Each test asserts
the presence of substring markers tied to a GitHub issue number, so that any
removal trips the test and forces a deliberate, traceable decision.

Issues protected here:
- #1182: Planner Call-Boundary Audit step
- #1147: Spec-validator Tautology Check
- #1209: CIA report persistence — coordinator-side Write only (Bash writes silently fail)
"""

from pathlib import Path

import pytest

# Resolve project root: tests/regression/test_*.py -> parents[2] = repo root
PROJECT_ROOT = Path(__file__).resolve().parents[2]

PLANNER_AGENT = PROJECT_ROOT / "plugins" / "autonomous-dev" / "agents" / "planner.md"
SPEC_VALIDATOR_AGENT = (
    PROJECT_ROOT / "plugins" / "autonomous-dev" / "agents" / "spec-validator.md"
)
CIA_AGENT = (
    PROJECT_ROOT
    / "plugins"
    / "autonomous-dev"
    / "agents"
    / "continuous-improvement-analyst.md"
)
IMPLEMENT_FIX_COMMAND = (
    PROJECT_ROOT / "plugins" / "autonomous-dev" / "commands" / "implement-fix.md"
)


class TestPlannerCallBoundaryAudit:
    """Regression: planner.md MUST retain the Call-Boundary Audit step (#1182)."""

    def test_planner_agent_file_exists(self) -> None:
        """planner.md must exist at the expected path."""
        assert PLANNER_AGENT.exists(), f"planner.md not found at {PLANNER_AGENT}"

    def test_planner_includes_call_boundary_audit_section_for_1182(self) -> None:
        """planner.md must contain the Call-Boundary Audit section and trigger condition.

        Locks Issue #1182: planner agent prompt must enumerate call sites before
        drafting plans that add/modify function parameters, fields, or flags.
        """
        content = PLANNER_AGENT.read_text()

        # Section header substring
        assert "Call-Boundary Audit" in content, (
            "planner.md is missing the 'Call-Boundary Audit' section "
            "added for Issue #1182. If you intentionally removed it, "
            "open an issue and remove this test in the same PR."
        )

        # Trigger condition keyword
        assert "adding a parameter" in content, (
            "planner.md is missing the 'adding a parameter' trigger condition "
            "for the Call-Boundary Audit (Issue #1182)."
        )

        # Issue reference must be present so future readers can trace context
        assert "#1182" in content, (
            "planner.md is missing the '#1182' issue reference for the "
            "Call-Boundary Audit section."
        )

    def test_planner_output_format_references_call_boundary_audit(self) -> None:
        """planner.md Output Format must reference the Call-Boundary Audit section.

        Per Issue #1182 acceptance criteria, the audit results must appear in
        the plan output under a clearly-labeled section.
        """
        content = PLANNER_AGENT.read_text()
        assert "## Call-Boundary Audit" in content, (
            "planner.md must reference the '## Call-Boundary Audit' section name "
            "(in Output Format) so reviewers and implementers can locate the audit."
        )


class TestSpecValidatorTautologyCheck:
    """Regression: spec-validator.md MUST retain the Tautology Check (#1147)."""

    def test_spec_validator_agent_file_exists(self) -> None:
        """spec-validator.md must exist at the expected path."""
        assert SPEC_VALIDATOR_AGENT.exists(), (
            f"spec-validator.md not found at {SPEC_VALIDATOR_AGENT}"
        )

    def test_spec_validator_includes_tautology_check_for_1147(self) -> None:
        """spec-validator.md must contain the Tautology Check guidance.

        Locks Issue #1147: spec-validator must flag parametrize tests where
        the assertion body restates what the parametrize loop already
        guarantees.
        """
        content = SPEC_VALIDATOR_AGENT.read_text()

        # Section header substring
        assert "Tautology Check" in content, (
            "spec-validator.md is missing the 'Tautology Check' guidance "
            "added for Issue #1147. If you intentionally removed it, "
            "open an issue and remove this test in the same PR."
        )

        # Core technical claim — must explain WHY the test is vacuous
        assert "structurally vacuous" in content, (
            "spec-validator.md is missing the 'structurally vacuous' explanation "
            "for the Tautology Check (Issue #1147). Without this, future readers "
            "cannot distinguish tautology from test-weakening."
        )

        # Issue reference must be present so future readers can trace context
        assert "#1147" in content, (
            "spec-validator.md is missing the '#1147' issue reference for "
            "the Tautology Check section."
        )

    def test_spec_validator_tautology_check_includes_positive_example(self) -> None:
        """Tautology Check must include a non-tautological positive example.

        Per Issue #1147 spec, the prompt must show what a NON-tautological
        parametrize test looks like (one where the assertion targets a
        different surface than the parametrize source).
        """
        content = SPEC_VALIDATOR_AGENT.read_text()
        assert "Non-tautological positive example" in content, (
            "spec-validator.md is missing the 'Non-tautological positive example' "
            "showing a parametrize test that catches drift between two collections "
            "(Issue #1147)."
        )


class TestCiaPersistenceFor1209:
    """Regression: CIA report persistence must be coordinator-side only (#1209).

    Three consecutive --fix pipelines on 2026-06-11 (#1283, #1287, #1288) produced
    30-byte placeholder CIA reports because the CIA agent attempted to self-persist
    via Bash subprocess writes that silently fail at the OS/sandbox level. The fix:
    CIA outputs as final message, coordinator captures via Agent tool return value,
    coordinator persists via Write tool from the parent session.
    """

    def test_cia_agent_does_not_instruct_bash_write_for_1209(self) -> None:
        """CIA agent prompt must NOT instruct Bash/subprocess writes to .claude/local/cia-*.md.

        Locks Issue #1209: CIA-internal Bash writes silently fail at the OS/sandbox
        level. The agent prompt must direct CIA to emit the report as its final
        assistant message; the coordinator (parent session) performs the persist
        via the Write tool. Any reintroduction of Bash/subprocess write instructions
        will recreate the silent-failure mode.
        """
        assert CIA_AGENT.exists(), f"CIA agent file not found at {CIA_AGENT}"
        content = CIA_AGENT.read_text()

        # The broken heredoc pattern: must NOT appear in the prompt
        assert "cat > .claude/local/cia-" not in content, (
            "continuous-improvement-analyst.md contains the broken Bash heredoc "
            "write pattern 'cat > .claude/local/cia-'. This pattern silently "
            "fails at the OS/sandbox level (Issue #1209). Remove it — the "
            "coordinator persists CIA output via the Write tool."
        )

        # The broken python3 -c write_text instruction pattern must NOT appear.
        # We distinguish *instructions* to perform the broken write from *warnings*
        # that describe it. Instructions take the form `Path('...cia...').write_text(`
        # or `p = Path('...cia...'); p.write_text(` — an actual code call. Warnings
        # use quoted descriptive form (e.g. `"...write_text(...)"`).
        #
        # Broken instruction signatures (any of these on one line is a violation):
        #   Path('...cia-...').write_text(...)
        #   Path("...cia-...").write_text(...)
        #   <varname>.write_text(report)  # following a Path(...) cia assignment
        broken_instruction_patterns = (
            "Path('.claude/local/cia-",
            'Path(".claude/local/cia-',
            "p.write_text(report)",
            "f.write_text(report)",
        )
        for line in content.splitlines():
            for pattern in broken_instruction_patterns:
                if pattern in line:
                    pytest.fail(
                        f"continuous-improvement-analyst.md contains the broken "
                        f"Python subprocess write instruction pattern {pattern!r} "
                        f"that silently fails at the OS/sandbox level (Issue #1209). "
                        f"Offending line: {line!r}"
                    )

        # Positive assertion: the prompt MUST direct CIA to rely on the coordinator
        # to persist via the Write tool, with explicit reference to #1209
        assert "coordinator" in content.lower(), (
            "continuous-improvement-analyst.md must mention 'coordinator' to "
            "explain who persists the CIA report (Issue #1209)."
        )
        assert "Write tool" in content, (
            "continuous-improvement-analyst.md must reference the 'Write tool' "
            "as the canonical persistence mechanism (Issue #1209)."
        )
        assert "#1209" in content, (
            "continuous-improvement-analyst.md must reference '#1209' inline "
            "so future readers can trace why Bash-write instructions were removed."
        )

    def test_implement_fix_has_cia_persist_step_for_1209(self) -> None:
        """implement-fix.md must define a coordinator-side CIA capture-and-persist step.

        Locks Issue #1209: the coordinator must capture CIA output from the Agent
        tool's return value and persist it via the Write tool. The canonical path
        scheme is `.claude/local/cia-YYYY-MM-DD-issue-NNNN-fix.md`. Persist-failure
        detection (file <100 bytes) must be present so silent failures surface.
        """
        assert IMPLEMENT_FIX_COMMAND.exists(), (
            f"implement-fix.md not found at {IMPLEMENT_FIX_COMMAND}"
        )
        content = IMPLEMENT_FIX_COMMAND.read_text()

        # Path scheme must be documented (the canonical persist path)
        assert ".claude/local/cia-" in content, (
            "implement-fix.md must document the canonical CIA persist path "
            "'.claude/local/cia-YYYY-MM-DD-issue-NNNN-fix.md' (Issue #1209)."
        )

        # The capture-and-persist step must reference the Write tool
        assert "Write tool" in content, (
            "implement-fix.md must reference the 'Write tool' in the CIA "
            "capture-and-persist step — this is the only persistence path "
            "that does not silently fail (Issue #1209)."
        )

        # Issue reference must be present inline for traceability
        assert "#1209" in content, (
            "implement-fix.md must reference '#1209' inline so future readers "
            "can trace why coordinator-side Write was made the canonical path."
        )


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
