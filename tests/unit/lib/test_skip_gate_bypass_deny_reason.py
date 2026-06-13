"""Regression tests for Issue #1212 — skip_agent_completeness_gate bypass
requires two separate Bash calls; chaining with && does not work.

These tests verify that the deny-reason messages and docstrings explicitly
warn about the && chaining limitation so coordinators do not accidentally
use the chained form that fails silently.
"""
from pathlib import Path

# Repo root: tests/unit/lib/ -> tests/unit/ -> tests/ -> repo root
REPO_ROOT = Path(__file__).resolve().parents[3]
PIPELINE_COMPLETION_STATE = (
    REPO_ROOT / "plugins/autonomous-dev/lib/pipeline_completion_state.py"
)
UNIFIED_PRE_TOOL = REPO_ROOT / "plugins/autonomous-dev/hooks/unified_pre_tool.py"


class TestIssue1212SkipGateBypassDenyReason:
    """Issue #1212: ensure && chaining limitation is documented in deny-reason messages
    and docstrings for the skip_agent_completeness_gate file bypass."""

    def test_check_file_bypass_docstring_warns_about_ampersand_chaining(self) -> None:
        """_check_file_bypass() docstring must warn that chaining with && will not work.

        Regression for Issue #1212: coordinators chained
        ``touch /tmp/skip_agent_completeness_gate && git commit`` in one Bash call,
        but the hook intercepts before touch executes so the bypass had no effect.
        """
        import sys

        sys.path.insert(0, str(REPO_ROOT / "plugins/autonomous-dev/lib"))
        from pipeline_completion_state import _check_file_bypass

        docstring = _check_file_bypass.__doc__ or ""
        assert "&&" in docstring, (
            "_check_file_bypass docstring must mention '&&' to warn about chaining limitation"
        )
        assert "WILL NOT WORK" in docstring, (
            "_check_file_bypass docstring must contain 'WILL NOT WORK' to explicitly warn about "
            "the && chaining limitation (Issue #1212)"
        )

    def test_verify_pipeline_agent_completions_docstring_warns_about_ampersand_chaining(
        self,
    ) -> None:
        """verify_pipeline_agent_completions() docstring must warn that && chaining will not work.

        Regression for Issue #1212.
        """
        import sys

        sys.path.insert(0, str(REPO_ROOT / "plugins/autonomous-dev/lib"))
        from pipeline_completion_state import verify_pipeline_agent_completions

        docstring = verify_pipeline_agent_completions.__doc__ or ""
        assert "&&" in docstring, (
            "verify_pipeline_agent_completions docstring must mention '&&' to warn about chaining"
        )
        assert "WILL NOT WORK" in docstring, (
            "verify_pipeline_agent_completions docstring must contain 'WILL NOT WORK' to "
            "explicitly warn about the && chaining limitation (Issue #1212)"
        )

    def test_unified_pre_tool_single_issue_deny_reason_warns_about_ampersand(
        self,
    ) -> None:
        """The single-issue agent completeness deny-reason in unified_pre_tool.py must
        explicitly warn that chaining with && will not work.

        The region around the BYPASS instructions (Issue #802) is checked for both
        'SEPARATE' (already present) and the new && warning phrase (Issue #1212).
        """
        content = UNIFIED_PRE_TOOL.read_text(encoding="utf-8")

        # Locate the single-issue bypass block — anchored by the Issue #802 reference
        # which appears only in the single-issue deny-reason message.
        marker = "Issue #802)"
        idx = content.find(marker)
        assert idx != -1, (
            f"Could not find the single-issue deny-reason block (marker: '{marker}') "
            f"in {UNIFIED_PRE_TOOL}"
        )

        # Extract the surrounding region (2 000 chars before the marker is plenty
        # to cover the full deny-reason string).
        region = content[max(0, idx - 2000) : idx + len(marker)]

        assert "SEPARATE" in region, (
            "Single-issue deny-reason must still say 'SEPARATE' (existing wording)"
        )
        assert "WILL NOT WORK" in region, (
            "Single-issue deny-reason must now contain 'WILL NOT WORK' to warn about "
            "&& chaining limitation (Issue #1212)"
        )
        assert "&&" in region, (
            "Single-issue deny-reason must reference '&&' so coordinators recognise the "
            "exact pattern that fails"
        )

    def test_unified_pre_tool_batch_deny_reason_warns_about_ampersand(self) -> None:
        """The batch agent completeness deny-reason in unified_pre_tool.py must
        explicitly warn that chaining with && will not work.

        The region around the BYPASS instructions (Issue #853) is checked for both
        'SEPARATE' (already present) and the new && warning phrase (Issue #1212).
        """
        content = UNIFIED_PRE_TOOL.read_text(encoding="utf-8")

        # Locate the batch bypass block — anchored by the Issue #853 reference
        # which appears only in the batch deny-reason message.
        marker = "Issue #853)"
        idx = content.find(marker)
        assert idx != -1, (
            f"Could not find the batch deny-reason block (marker: '{marker}') "
            f"in {UNIFIED_PRE_TOOL}"
        )

        region = content[max(0, idx - 2000) : idx + len(marker)]

        assert "SEPARATE" in region, (
            "Batch deny-reason must still say 'SEPARATE' (existing wording)"
        )
        assert "WILL NOT WORK" in region, (
            "Batch deny-reason must now contain 'WILL NOT WORK' to warn about "
            "&& chaining limitation (Issue #1212)"
        )
        assert "&&" in region, (
            "Batch deny-reason must reference '&&' so coordinators recognise the "
            "exact pattern that fails"
        )
