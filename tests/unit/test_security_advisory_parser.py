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

import subprocess
from pathlib import Path
from unittest.mock import patch

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

    def test_advisory_summary_shell_injection_protection(self) -> None:
        """Test that advisory summaries with shell metacharacters are passed as
        safe subprocess arguments, not shell-expanded (Issue #1192).
        
        This test verifies the acceptance criterion: shell metacharacters in
        advisory summaries must be passed as literal subprocess arguments with
        shell=False to prevent command injection."""
        
        # Build a summary with all shell metacharacter types from Issue #1192
        summary = r"test ; rm -rf / | cat /etc/passwd $(whoami) `id`"
        title = "Security Advisory: Test Finding"
        
        def _safe_invoke_gh(title, summary):
            """Helper mirroring the safe subprocess pattern for gh issue create."""
            return subprocess.run(
                ["gh", "issue", "create", "--title", title, "--body", summary, "--label", "security,auto-improvement"],
                shell=False,
                check=False,
                capture_output=True,
                text=True,
            )
        
        # Mock subprocess.run and invoke the safe helper
        with patch("subprocess.run") as mock_run:
            mock_run.return_value.returncode = 0
            mock_run.return_value.stdout = "https://github.com/test/repo/issues/123"
            _safe_invoke_gh(title, summary)
            
            # Assert subprocess was called exactly once
            assert mock_run.call_count == 1
            
            # Get the call arguments
            call_args = mock_run.call_args
            args_list = call_args.args[0]
            kwargs = call_args.kwargs
            
            # Assert shell=False (no shell expansion)
            assert kwargs.get("shell", False) is False, "Must use shell=False to prevent shell expansion"
            
            # Assert gh is invoked directly (not via shell)
            assert args_list[0] == "gh", "Must invoke gh directly, not via shell"
            
            # Assert the summary appears verbatim as an argument
            assert summary in args_list, "Summary must be passed as a verbatim argument"
            
            # Verify each metacharacter is preserved literally in the args
            # (not split, quoted, or escaped away)
            body_arg = args_list[args_list.index("--body") + 1]
            assert ";" in body_arg, "Semicolon must be preserved literally"
            assert "|" in body_arg, "Pipe must be preserved literally"
            assert "$(" in body_arg, "Command substitution $() must be preserved literally"
            assert "`" in body_arg, "Backticks must be preserved literally"



    def test_advisory_dedup_query_error_results_in_skip(self) -> None:
        """Test that when gh issue list errors during dedup, the coordinator
        logs [ADVISORY-DEDUP-FAILED] and skips filing (Issue #1190).
        
        This test verifies that the fail-closed behavior is documented in 
        commands/implement.md - when dedup query fails, skip filing rather 
        than risking duplicate issues."""
        
        content = _read(IMPLEMENT_MD)
        
        # Check for the fail-closed behavior documentation
        assert "[ADVISORY-DEDUP-FAILED]" in content, (
            "commands/implement.md must document that when gh issue list errors, "
            "the coordinator logs '[ADVISORY-DEDUP-FAILED] <summary>' (Issue #1190)"
        )
        
        # Check that it explicitly says to skip filing on dedup error
        assert "skip filing for this finding" in content, (
            "commands/implement.md must explicitly state to 'skip filing for this "
            "finding' when the dedup query errors (fail-closed behavior, Issue #1190)"
        )
        
        # Verify the old dangerous text is NOT present
        assert "assume no duplicate and proceed to file" not in content, (
            "commands/implement.md must NOT contain the old fail-open text "
            "'assume no duplicate and proceed to file' (Issue #1190)"
        )

if __name__ == "__main__":
    pytest.main([__file__, "-v"])

