#!/usr/bin/env python3
"""Regression tests locking behavioral invariants in agent prompt files.

These tests prevent future agent-prompt refactors from accidentally dropping
behavioral guidance added in response to specific issues. Each test asserts
the presence of substring markers tied to a GitHub issue number, so that any
removal trips the test and forces a deliberate, traceable decision.

Issues protected here:
- #1182: Planner Call-Boundary Audit step
- #1147: Spec-validator Tautology Check
"""

from pathlib import Path

import pytest

# Resolve project root: tests/regression/test_*.py -> parents[2] = repo root
PROJECT_ROOT = Path(__file__).resolve().parents[2]

PLANNER_AGENT = PROJECT_ROOT / "plugins" / "autonomous-dev" / "agents" / "planner.md"
SPEC_VALIDATOR_AGENT = (
    PROJECT_ROOT / "plugins" / "autonomous-dev" / "agents" / "spec-validator.md"
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


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
