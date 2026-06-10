"""Regression tests for Issue #1180 — Security-auditor advisory finding tracking.

These tests lock in the prompt/coordinator contract that:

1. security-auditor.md REQUIRES an `ADVISORY-FINDINGS:` block on every audit
   output, and FORBIDS silent deferral of Low/Medium findings.
2. commands/implement.md contains the "Security-Auditor Advisory Finding
   Tracking" parser block that runs after STEP 11, files dedup-checked
   GitHub issues with the `security` + `auto-improvement` labels, and lists
   the new FORBIDDEN behavior under STEP 11.

If a future edit removes or weakens any of these clauses, these tests fail
and the regression is caught at PR time. See Issue #1180 for full context.
"""

from __future__ import annotations

from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
SECURITY_AUDITOR_MD = ROOT / "plugins" / "autonomous-dev" / "agents" / "security-auditor.md"
IMPLEMENT_MD = ROOT / "plugins" / "autonomous-dev" / "commands" / "implement.md"


def _read(path: Path) -> str:
    assert path.exists(), f"Required file missing: {path}"
    return path.read_text(encoding="utf-8")


class TestSecurityAuditorAdvisoryClause:
    """security-auditor.md MUST mandate the ADVISORY-FINDINGS block."""

    def test_security_auditor_md_contains_advisory_findings_clause(self) -> None:
        """AC: agents/security-auditor.md must define the ADVISORY-FINDINGS block
        with MUST-level phrasing so the agent always emits it."""
        content = _read(SECURITY_AUDITOR_MD)
        assert "ADVISORY-FINDINGS:" in content, (
            "security-auditor.md must reference the literal 'ADVISORY-FINDINGS:' "
            "block (Issue #1180)"
        )
        assert "MUST emit" in content or "MUST emit an" in content, (
            "security-auditor.md must use MUST-level phrasing to require the "
            "ADVISORY-FINDINGS block on every audit output (Issue #1180)"
        )
        assert "ADVISORY-FINDINGS: none" in content, (
            "security-auditor.md must instruct the agent to emit the literal "
            "'ADVISORY-FINDINGS: none' when there are no advisory findings "
            "(absence-as-malformed-output contract)"
        )

    def test_security_auditor_md_forbids_silent_deferral(self) -> None:
        """AC: agents/security-auditor.md must FORBID deferring a Low/Medium
        finding to 'follow-up' without listing it in the advisory block."""
        content = _read(SECURITY_AUDITOR_MD)
        assert "MUST NOT defer" in content, (
            "security-auditor.md must contain a FORBIDDEN bullet using 'MUST NOT "
            "defer' phrasing to block silent deferral of Low/Medium findings "
            "(Issue #1180)"
        )
        # Confirm the bullet ties the deferral prohibition to the advisory block.
        assert "ADVISORY-FINDINGS" in content, (
            "the deferral-prohibition bullet must reference ADVISORY-FINDINGS so "
            "the agent knows where the deferred finding belongs"
        )


class TestImplementMdAdvisoryParser:
    """commands/implement.md MUST contain the coordinator-side parser block."""

    def test_implement_md_contains_advisory_parser(self) -> None:
        """AC: commands/implement.md must contain a 'Security-Auditor Advisory
        Finding Tracking' section that mirrors the reviewer out-of-scope
        tracker."""
        content = _read(IMPLEMENT_MD)
        assert "Security-Auditor Advisory Finding Tracking" in content, (
            "commands/implement.md must contain the literal section header "
            "'Security-Auditor Advisory Finding Tracking' so the coordinator "
            "knows to run the parser (Issue #1180)"
        )

    def test_implement_md_advisory_filer_uses_security_label(self) -> None:
        """AC: filed issues must carry both `security` and `auto-improvement`
        labels so the auto-improvement triage loop picks them up."""
        content = _read(IMPLEMENT_MD)
        assert "--label security --label auto-improvement" in content, (
            "commands/implement.md must invoke `gh issue create` with "
            "`--label security --label auto-improvement` for advisory findings "
            "(Issue #1180 AC1)"
        )

    def test_implement_md_advisory_parser_dedup_step(self) -> None:
        """AC: parser must dedup against existing open security advisory
        issues before filing (Issue #1180 AC2)."""
        content = _read(IMPLEMENT_MD)
        assert "gh issue list --label security" in content, (
            "commands/implement.md must include a `gh issue list --label security` "
            "dedup query before filing (Issue #1180 AC2)"
        )
        assert "--state open" in content, (
            "dedup query must restrict to `--state open` so closed duplicates "
            "do not block re-filing"
        )

    def test_implement_md_step11_forbidden_includes_advisory_skip(self) -> None:
        """AC: STEP 11 FORBIDDEN list must include a bullet preventing the
        coordinator from proceeding past STEP 11 without parsing the
        ADVISORY-FINDINGS block (Issue #1180)."""
        content = _read(IMPLEMENT_MD)
        # The new FORBIDDEN bullet, verbatim from the plan.
        expected_bullet = (
            "Proceeding past STEP 11 without parsing the ADVISORY-FINDINGS block"
        )
        assert expected_bullet in content, (
            "commands/implement.md STEP 11 FORBIDDEN list must include the "
            f"bullet: '{expected_bullet}' (Issue #1180)"
        )


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
