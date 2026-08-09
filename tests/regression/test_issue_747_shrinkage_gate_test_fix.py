"""Regression test: Issue #747 — shrinkage gate test fix.

Before the fix, test_critical_agent_above_minimum_allowed created a 100-word
reviewer prompt and expected "allow". Issue #723 added a baseline shrinkage gate
to validate_prompt_integrity(). The live prompt_baselines.json contains a reviewer
baseline of 396 words. Since 100 < 396 * 0.75 = 297, the hook correctly denied it.

The fix:
1. Patches get_prompt_baseline to return None in the above-minimum test so only
   the minimum word-count gate is exercised (not the shrinkage gate).
2. Adds explicit tests for the shrinkage gate with mocked baselines.

This regression test verifies that the fix is in place and behaves correctly.
"""
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

HOOK_DIR = Path(__file__).resolve().parents[2] / "plugins" / "autonomous-dev" / "hooks"
LIB_DIR = Path(__file__).resolve().parents[2] / "plugins" / "autonomous-dev" / "lib"
sys.path.insert(0, str(HOOK_DIR))
sys.path.insert(0, str(LIB_DIR))

import unified_pre_tool as hook


def _make_prompt(word_count: int) -> str:
    """Generate a prompt with exactly word_count words."""
    return " ".join(f"word{i}" for i in range(word_count))


class TestIssue747ShrinkageGateTestFix:
    """Regression tests for Issue #747 — shrinkage gate coexists with min-word-count gate."""

    def test_above_minimum_passes_when_no_baseline(self):
        """A 100-word reviewer prompt should be allowed when no baseline is recorded.

        This is the original test_critical_agent_above_minimum_allowed scenario.
        Patching get_prompt_baseline to None isolates the minimum word-count gate.
        """
        prompt = _make_prompt(100)
        with (
            patch.object(hook, "_is_pipeline_active", return_value=True),
            patch("prompt_integrity.get_prompt_baseline", return_value=None),
        ):
            decision, reason = hook.validate_prompt_integrity(
                "Agent",
                {"subagent_type": "reviewer", "prompt": prompt},
            )
        assert decision == "allow", f"Expected allow, got deny. Reason: {reason}"
        assert "Prompt integrity OK" in reason

    def test_shrinkage_gate_fires_when_below_threshold(self):
        """A 100-word prompt is denied when baseline is 396 (shrinkage = 74.7%, > 25%).

        This test would have been failing BEFORE the Issue #747 fix because the
        original test did not mock get_prompt_baseline and hit the live baseline file.
        Now the shrinkage gate is tested explicitly via mocking.
        """
        prompt = _make_prompt(100)
        with (
            patch.object(hook, "_is_pipeline_active", return_value=True),
            patch("prompt_integrity.get_prompt_baseline", return_value=396),
        ):
            decision, reason = hook.validate_prompt_integrity(
                "Agent",
                {"subagent_type": "reviewer", "prompt": prompt},
            )
        assert decision == "deny", f"Expected deny (shrinkage), got: {decision}. Reason: {reason}"
        assert "BLOCKED" in reason
        assert "shrank" in reason

    def test_shrinkage_gate_passes_when_above_threshold(self):
        """A 330-word prompt is allowed with a 396-word baseline (shrinkage = 16.7%, < 20%).

        Verifies that the shrinkage threshold (20%, per hook's max_shrinkage=0.20 in
        unified_pre_tool.py validate_prompt_integrity) is a soft boundary that allows
        natural variation while blocking catastrophic compression.

        Issue #1471: recalibrated from 300 words (24.2% shrinkage) to 330 words
        (16.7% shrinkage). The original 300-word fixture was written when the
        shrinkage gate was silently fail-open (dead code path), so its arithmetic
        was never actually exercised — 24.2% exceeds the 20% threshold and an
        enforcing gate correctly denies it. 330 words keeps this test's INTENT
        (a prompt within the shrinkage threshold must be allowed) while giving
        genuinely-under-threshold math: (396 - 330) / 396 = 16.7% < 20%.
        """
        prompt = _make_prompt(330)
        with (
            patch.object(hook, "_is_pipeline_active", return_value=True),
            patch("prompt_integrity.get_prompt_baseline", return_value=396),
        ):
            decision, reason = hook.validate_prompt_integrity(
                "Agent",
                {"subagent_type": "reviewer", "prompt": prompt},
            )
        assert decision == "allow", f"Expected allow (within threshold), got deny. Reason: {reason}"
        assert "Prompt integrity OK" in reason

    def test_unit_test_file_patches_baseline_in_above_minimum_test(self):
        """The unit test file must patch get_prompt_baseline in test_critical_agent_above_minimum_allowed.

        This is a meta-regression: verifies the fix is present in the test file itself
        so future readers can see why the mock is necessary.
        """
        test_file = (
            Path(__file__).resolve().parents[1]
            / "unit"
            / "hooks"
            / "test_prompt_integrity_enforcement.py"
        )
        assert test_file.exists(), f"Test file not found: {test_file}"
        content = test_file.read_text(encoding="utf-8")

        # The above-minimum test must include a get_prompt_baseline patch
        assert "test_critical_agent_above_minimum_allowed" in content
        assert "get_prompt_baseline" in content
        assert "return_value=None" in content
