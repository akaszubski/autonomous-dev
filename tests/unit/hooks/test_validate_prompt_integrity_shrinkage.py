"""
Tests for progressive baseline shrinkage enforcement in validate_prompt_integrity.

Validates that the hook-level baseline shrinkage check (Issue #723):
- Seeds a baseline when none exists (fails open)
- Blocks prompts that shrink more than 25% from the established baseline
- Allows prompts that stay within the 25% threshold
- Fails open on import errors or unexpected exceptions
- Includes actionable instructions (stick+carrot) in the deny message
"""

import sys
from pathlib import Path
from unittest.mock import ANY, MagicMock, call, patch

import pytest

# Add hook and lib dirs to path — parents[3] because:
# test file → hooks → unit → tests → repo root
HOOK_DIR = Path(__file__).resolve().parents[3] / "plugins" / "autonomous-dev" / "hooks"
LIB_DIR = Path(__file__).resolve().parents[3] / "plugins" / "autonomous-dev" / "lib"
sys.path.insert(0, str(HOOK_DIR))
sys.path.insert(0, str(LIB_DIR))

import unified_pre_tool as hook
from prompt_integrity import PromptIntegrityResult


def _make_prompt(word_count: int) -> str:
    """Generate a prompt with exactly word_count words."""
    return " ".join(f"word{i}" for i in range(word_count))


class TestBaselineShrinkageEnforcement:
    """Tests for the baseline shrinkage enforcement added in Issue #723."""

    def test_non_critical_agent_bypasses_shrinkage_check(self):
        """Non-critical agent is allowed without consulting the baseline at all."""
        with patch("prompt_integrity.get_prompt_baseline") as mock_get_baseline:
            decision, reason = hook.validate_prompt_integrity(
                "Agent",
                {"subagent_type": "some-other-agent", "prompt": "short prompt"},
            )
        assert decision == "allow"
        assert "not compression-critical" in reason
        # Baseline should never be consulted for non-critical agents
        mock_get_baseline.assert_not_called()

    def test_minimum_floor_blocks_before_baseline_check(self):
        """50-word prompt is blocked at the floor check; baseline is never consulted."""
        short_prompt = _make_prompt(50)
        with patch("prompt_integrity.get_prompt_baseline") as mock_get_baseline:
            decision, reason = hook.validate_prompt_integrity(
                "Agent",
                {"subagent_type": "reviewer", "prompt": short_prompt},
            )
        assert decision == "deny"
        assert "BLOCKED" in reason
        assert "50 words" in reason
        # Floor check fires before baseline — baseline must not be reached
        mock_get_baseline.assert_not_called()

    def test_no_baseline_seeds_and_allows(self):
        """When no baseline exists, the observed word count is seeded and the call is allowed."""
        adequate_prompt = _make_prompt(150)
        expected_baseline = 150  # Observed word count (Issue #759: hook seeds from observed, not template)
        with (
            patch("prompt_integrity.get_prompt_baseline", return_value=None) as mock_get,
            patch("prompt_integrity.record_prompt_baseline") as mock_record,
            patch("prompt_integrity.validate_prompt_word_count") as mock_validate,
            # Simulate no active pipeline context (issue_number=0 → seed_issue=0)
            patch.object(hook, "_get_current_issue_number", return_value=0),
            # Isolate cumulative drift check from stale on-disk data (Issue #861)
            patch("prompt_integrity.record_batch_observation"),
            patch("prompt_integrity.get_cumulative_shrinkage", return_value=None),
        ):
            decision, reason = hook.validate_prompt_integrity(
                "Agent",
                {"subagent_type": "reviewer", "prompt": adequate_prompt},
            )

        assert decision == "allow"
        # record_prompt_baseline seeded at observed word count (Issue #759).
        # Issue #1471 (landmine 1): the hook also passes pipeline_mode= (added in
        # Issue #1358, unified_pre_tool.py:~1308). The assertion is TIGHTENED to
        # include it rather than weakened — mock.ANY is used because the value is
        # environment-dependent (_get_pipeline_mode_from_state reads live pipeline state).
        mock_record.assert_called_once_with(
            "reviewer",
            issue_number=0,
            word_count=expected_baseline,
            pipeline_mode=ANY,
        )
        # validate_prompt_word_count should NOT be called when baseline is None
        mock_validate.assert_not_called()

    def test_shrinkage_within_threshold_allows(self):
        """169-word baseline, 140-word current (~17.2% shrinkage) → allow."""
        current_prompt = _make_prompt(140)
        passing_result = PromptIntegrityResult(
            agent_type="reviewer",
            word_count=140,
            baseline_word_count=169,
            shrinkage_pct=17.2,
            passed=True,
            reason="Prompt for reviewer OK (140 words).",
            should_reload=False,
        )
        with (
            patch("prompt_integrity.get_prompt_baseline", return_value=169),
            patch("prompt_integrity.record_prompt_baseline") as mock_record,
            patch(
                "prompt_integrity.validate_prompt_word_count", return_value=passing_result
            ),
            # Isolate cumulative drift check from stale on-disk data (Issue #861)
            patch("prompt_integrity.record_batch_observation"),
            patch("prompt_integrity.get_cumulative_shrinkage", return_value=None),
        ):
            decision, reason = hook.validate_prompt_integrity(
                "Agent",
                {"subagent_type": "reviewer", "prompt": current_prompt},
            )

        assert decision == "allow"
        assert "Prompt integrity OK" in reason
        # No new baseline should be seeded when one already exists
        mock_record.assert_not_called()

    def test_shrinkage_exceeds_threshold_blocks(self):
        """169-word baseline, 84-word current (~50.3% shrinkage) → deny."""
        current_prompt = _make_prompt(84)
        failing_result = PromptIntegrityResult(
            agent_type="reviewer",
            word_count=84,
            baseline_word_count=169,
            shrinkage_pct=50.3,
            passed=False,
            reason="Prompt for reviewer shrank 50.3% from baseline (169 -> 84 words, threshold: 25%).",
            should_reload=True,
        )
        with (
            patch("prompt_integrity.get_prompt_baseline", return_value=169),
            patch(
                "prompt_integrity.validate_prompt_word_count", return_value=failing_result
            ),
        ):
            decision, reason = hook.validate_prompt_integrity(
                "Agent",
                {"subagent_type": "reviewer", "prompt": current_prompt},
            )

        assert decision == "deny"
        assert "BLOCKED" in reason
        assert "50.3%" in reason
        assert "169" in reason  # baseline in message
        assert "84" in reason   # current word count in message

    def test_shrinkage_exactly_at_threshold_allows(self):
        """169-word baseline, 136-word current (19.5% shrinkage) → allow (just under 20% threshold)."""
        current_prompt = _make_prompt(136)
        passing_result = PromptIntegrityResult(
            agent_type="reviewer",
            word_count=136,
            baseline_word_count=169,
            shrinkage_pct=19.5,
            passed=True,
            reason="Prompt for reviewer OK (136 words).",
            should_reload=False,
        )
        with (
            patch("prompt_integrity.get_prompt_baseline", return_value=169),
            patch(
                "prompt_integrity.validate_prompt_word_count", return_value=passing_result
            ),
            # Isolate cumulative drift check from stale on-disk data (Issue #861)
            patch("prompt_integrity.record_batch_observation"),
            patch("prompt_integrity.get_cumulative_shrinkage", return_value=None),
        ):
            decision, reason = hook.validate_prompt_integrity(
                "Agent",
                {"subagent_type": "reviewer", "prompt": current_prompt},
            )

        assert decision == "allow"

    def test_shrinkage_just_over_threshold_blocks(self):
        """169-word baseline, 135-word current (20.1% shrinkage) → deny (just over 20% threshold)."""
        current_prompt = _make_prompt(135)
        failing_result = PromptIntegrityResult(
            agent_type="reviewer",
            word_count=135,
            baseline_word_count=169,
            shrinkage_pct=20.1,
            passed=False,
            reason="Prompt for reviewer shrank 20.1% from baseline (169 -> 135 words, threshold: 20%).",
            should_reload=True,
        )
        with (
            patch("prompt_integrity.get_prompt_baseline", return_value=169),
            patch(
                "prompt_integrity.validate_prompt_word_count", return_value=failing_result
            ),
        ):
            decision, reason = hook.validate_prompt_integrity(
                "Agent",
                {"subagent_type": "reviewer", "prompt": current_prompt},
            )

        assert decision == "deny"
        assert "BLOCKED" in reason

    def test_import_error_fails_open(self):
        """If prompt_integrity module raises ImportError, the hook must allow (fail open)."""
        adequate_prompt = _make_prompt(150)
        # We need to make the import inside the function fail.
        # The function tries: from prompt_integrity import get_prompt_baseline, ...
        # We can patch the module-level import to raise ImportError by temporarily
        # removing the module from sys.modules after the floor check passes.
        original_module = sys.modules.get("prompt_integrity")
        try:
            # Remove so the re-import inside validate_prompt_integrity raises ImportError
            sys.modules["prompt_integrity"] = None  # type: ignore[assignment]
            decision, reason = hook.validate_prompt_integrity(
                "Agent",
                {"subagent_type": "reviewer", "prompt": adequate_prompt},
            )
        finally:
            if original_module is not None:
                sys.modules["prompt_integrity"] = original_module
            elif "prompt_integrity" in sys.modules:
                del sys.modules["prompt_integrity"]

        # The hook must fail open — allow the call, not block it
        assert decision == "allow"

    def test_deny_message_contains_actionable_instructions(self):
        """Blocked message must include get_agent_prompt_template (stick+carrot pattern)."""
        current_prompt = _make_prompt(84)
        failing_result = PromptIntegrityResult(
            agent_type="security-auditor",
            word_count=84,
            baseline_word_count=169,
            shrinkage_pct=50.3,
            passed=False,
            reason="Prompt shrank.",
            should_reload=True,
        )
        with (
            patch("prompt_integrity.get_prompt_baseline", return_value=169),
            patch(
                "prompt_integrity.validate_prompt_word_count", return_value=failing_result
            ),
        ):
            decision, reason = hook.validate_prompt_integrity(
                "Agent",
                {"subagent_type": "security-auditor", "prompt": current_prompt},
            )

        assert decision == "deny"
        # Must include the REQUIRED NEXT ACTION directive (stick+carrot)
        assert "REQUIRED NEXT ACTION" in reason
        assert "get_agent_prompt_template" in reason
        assert "security-auditor" in reason

    def test_validate_prompt_word_count_called_with_20pct_max_shrinkage(self):
        """validate_prompt_word_count must be called with max_shrinkage=0.20 (Issue #812)."""
        current_prompt = _make_prompt(140)
        passing_result = PromptIntegrityResult(
            agent_type="reviewer",
            word_count=140,
            baseline_word_count=169,
            shrinkage_pct=17.2,
            passed=True,
            reason="OK",
            should_reload=False,
        )
        with (
            patch("prompt_integrity.get_prompt_baseline", return_value=169),
            patch(
                "prompt_integrity.validate_prompt_word_count", return_value=passing_result
            ) as mock_validate,
        ):
            hook.validate_prompt_integrity(
                "Agent",
                {"subagent_type": "reviewer", "prompt": current_prompt},
            )

        mock_validate.assert_called_once()
        _, kwargs = mock_validate.call_args
        assert kwargs.get("max_shrinkage") == 0.20, (
            f"Expected max_shrinkage=0.20 but got {kwargs.get('max_shrinkage')}"
        )

    def test_stale_observations_file_does_not_cause_false_denial(self):
        """Regression: stale on-disk observations with >15% cumulative drift must not deny (Issue #861).

        Without mocking get_cumulative_shrinkage, a stale
        .claude/logs/prompt_batch_observations.json with >15% cumulative shrinkage
        causes `validate_prompt_integrity` to return 'deny' for tests that expect
        'allow'. This regression test verifies the isolation: even when
        get_cumulative_shrinkage returns a high value (simulating stale data),
        the correct fix is to mock it to None so tests are environment-independent.
        """
        adequate_prompt = _make_prompt(140)
        passing_result = PromptIntegrityResult(
            agent_type="reviewer",
            word_count=140,
            baseline_word_count=169,
            shrinkage_pct=17.2,
            passed=True,
            reason="Prompt for reviewer OK (140 words).",
            should_reload=False,
        )

        # Simulate what stale data looks like: get_cumulative_shrinkage returns >15%
        # This would cause a deny WITHOUT the mock isolation fix.
        # With the fix (return_value=None), the test correctly allows.
        with (
            patch("prompt_integrity.get_prompt_baseline", return_value=169),
            patch("prompt_integrity.validate_prompt_word_count", return_value=passing_result),
            patch("prompt_integrity.record_batch_observation"),
            patch("prompt_integrity.get_cumulative_shrinkage", return_value=None),
        ):
            decision, reason = hook.validate_prompt_integrity(
                "Agent",
                {"subagent_type": "reviewer", "prompt": adequate_prompt},
            )

        assert decision == "allow", (
            "Expected 'allow' but got 'deny' — stale observations file is leaking into test"
        )
        assert "Prompt integrity OK" in reason
