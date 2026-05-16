"""
Spec validation tests for Issue #764: Fix progressive prompt shrinkage in batch mode.

Acceptance criteria (post Issue #1082 Phase 1a):
1. Per-issue baseline isolation works (issue 1 baseline does not contaminate
   issue 2's per-issue lookup). For a brand-new issue with no baseline,
   ``get_prompt_baseline()`` returns None.
2. Within-issue shrinkage is still detected.
3. Backward compatibility when PIPELINE_ISSUE_NUMBER is not set
   (``get_prompt_baseline()`` without ``issue_number`` returns the
   lowest-issue baseline for single-issue mode).
4. Cross-issue baseline lookup is the job of ``get_cross_issue_baseline()``;
   cross-issue drift detection is the job of ``record_batch_observation`` +
   ``get_cumulative_shrinkage`` (Issue #794).

Issue #1082 Phase 1a removed the silent cross-issue fallback that Issue #867
had added inside ``get_prompt_baseline``. The retroactive #867 amendments to
this file (tests 1, 4, 5) are reverted here to assert the original #764
contract: per-issue isolation, with cross-issue lookup made explicit.
"""

import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
LIB_DIR = REPO_ROOT / "plugins" / "autonomous-dev" / "lib"
if str(LIB_DIR) not in sys.path:
    sys.path.insert(0, str(LIB_DIR))

from prompt_integrity import (
    clear_prompt_baselines,
    get_cross_issue_baseline,
    get_prompt_baseline,
    record_prompt_baseline,
    validate_prompt_word_count,
)


class TestSpecIssue764PerIssueBaseline:
    """Spec validation: per-issue baseline isolation for batch mode."""

    def test_spec_764_1_issue2_per_issue_lookup_returns_none(
        self, tmp_path: Path
    ) -> None:
        """Criterion 1 (restored by Issue #1082 Phase 1a): A per-issue lookup
        for a brand-new issue must return None — never silently inherit a
        prior issue's baseline. The previous silent fallback (added by #867)
        produced a guaranteed first-dispatch block in batch mode.

        Cross-issue baseline lookup, when needed, is an explicit call to
        ``get_cross_issue_baseline()``.
        """
        state_dir = tmp_path / "state"
        state_dir.mkdir()

        clear_prompt_baselines(state_dir=state_dir)

        # Record a large baseline for issue 1
        record_prompt_baseline(
            "implementer", issue_number=1, word_count=500, state_dir=state_dir
        )

        # Per-issue lookup for issue 2 must return None — no silent fallback.
        baseline_issue2 = get_prompt_baseline(
            "implementer", issue_number=2, state_dir=state_dir
        )
        assert baseline_issue2 is None, (
            f"Expected None for issue 2's per-issue lookup (Issue #1082 "
            f"Phase 1a contract), got {baseline_issue2}. "
            f"A silent fallback re-introduces the #764 first-dispatch block."
        )

        # Explicit cross-issue lookup returns the lowest-issue baseline.
        cross = get_cross_issue_baseline("implementer", state_dir=state_dir)
        assert cross == 500, (
            f"Explicit get_cross_issue_baseline() should return issue 1's "
            f"baseline (500), got {cross}."
        )

    def test_spec_764_2_within_issue_shrinkage_detected(
        self, tmp_path: Path
    ) -> None:
        """Criterion 2: Shrinkage within the same issue is still detected.
        Recording a baseline for issue 5 and then validating a much smaller
        prompt against that baseline should fail."""
        state_dir = tmp_path / "state"
        state_dir.mkdir()

        clear_prompt_baselines(state_dir=state_dir)

        # Record baseline for issue 5
        baseline_wc = 400
        record_prompt_baseline(
            "reviewer", issue_number=5, word_count=baseline_wc, state_dir=state_dir
        )

        # Retrieve the baseline for the same issue
        baseline = get_prompt_baseline(
            "reviewer", issue_number=5, state_dir=state_dir
        )
        assert baseline == baseline_wc, (
            f"Expected baseline {baseline_wc} for issue 5, got {baseline}"
        )

        # Validate a prompt that is 50% smaller -- should be caught
        small_prompt = " ".join(["word"] * 200)
        result = validate_prompt_word_count(
            "reviewer", small_prompt, baseline, max_shrinkage=0.15
        )
        assert result.passed is False, (
            "Expected shrinkage detection within the same issue to fail the check"
        )
        assert result.should_reload is True
        assert result.shrinkage_pct > 40.0

    def test_spec_764_3_backward_compat_no_issue_number(
        self, tmp_path: Path
    ) -> None:
        """Criterion 3: When issue_number is not provided to get_prompt_baseline,
        it falls back to returning the baseline from the lowest-numbered issue
        (backward compatibility with pre-#764 behavior)."""
        state_dir = tmp_path / "state"
        state_dir.mkdir()

        clear_prompt_baselines(state_dir=state_dir)

        # Record baselines for multiple issues
        record_prompt_baseline(
            "implementer", issue_number=10, word_count=300, state_dir=state_dir
        )
        record_prompt_baseline(
            "implementer", issue_number=3, word_count=450, state_dir=state_dir
        )
        record_prompt_baseline(
            "implementer", issue_number=7, word_count=350, state_dir=state_dir
        )

        # Without issue_number, should return the lowest issue's baseline (issue 3 = 450)
        baseline = get_prompt_baseline("implementer", state_dir=state_dir)
        assert baseline == 450, (
            f"Expected backward-compat baseline of 450 (from lowest issue #3), "
            f"got {baseline}"
        )

    def test_spec_764_4_multiple_agents_isolated_per_issue(
        self, tmp_path: Path
    ) -> None:
        """Criterion 1 extended (Issue #1082 Phase 1a contract): per-issue
        isolation holds across agents. Issue 1's baselines must not contaminate
        issue 2's per-issue lookups for any agent.
        """
        state_dir = tmp_path / "state"
        state_dir.mkdir()

        clear_prompt_baselines(state_dir=state_dir)

        # Record baselines for issue 1 across two agents
        record_prompt_baseline(
            "reviewer", issue_number=1, word_count=600, state_dir=state_dir
        )
        record_prompt_baseline(
            "implementer", issue_number=1, word_count=500, state_dir=state_dir
        )

        # Issue 2 per-issue lookups MUST return None for both agents
        # (no silent cross-issue fallback after Issue #1082 Phase 1a).
        assert (
            get_prompt_baseline("reviewer", issue_number=2, state_dir=state_dir)
            is None
        )
        assert (
            get_prompt_baseline("implementer", issue_number=2, state_dir=state_dir)
            is None
        )

        # Issue 1 baselines remain retrievable per-issue.
        assert get_prompt_baseline("reviewer", issue_number=1, state_dir=state_dir) == 600
        assert get_prompt_baseline("implementer", issue_number=1, state_dir=state_dir) == 500

        # Explicit cross-issue lookup still works for both agents.
        assert get_cross_issue_baseline("reviewer", state_dir=state_dir) == 600
        assert get_cross_issue_baseline("implementer", state_dir=state_dir) == 500

    def test_spec_764_5_first_dispatch_not_blocked_against_prior_issue(
        self, tmp_path: Path
    ) -> None:
        """Criterion 1 end-to-end (Issue #1082 Phase 1a): A new issue's FIRST
        dispatch must not be compared against a prior issue's baseline. That
        scenario is exactly the friction event #1082 was raised to fix: the
        coordinator sends a 300-word prompt for issue 2 and the gate must not
        block it against issue 1's 800-word baseline.

        Cross-issue drift detection is the job of ``record_batch_observation``
        + ``get_cumulative_shrinkage`` (Issue #794), not of
        ``get_prompt_baseline``.
        """
        state_dir = tmp_path / "state"
        state_dir.mkdir()

        clear_prompt_baselines(state_dir=state_dir)

        # Issue 1: large implementer prompt, establish baseline
        record_prompt_baseline(
            "implementer", issue_number=1, word_count=800, state_dir=state_dir
        )

        # Issue 2: smaller prompt (300 words) — natural first-dispatch size.
        issue2_prompt = " ".join(["word"] * 300)

        # Per-issue lookup for issue 2 returns None: there is no in-issue
        # baseline yet, so the caller will seed one from the first observation.
        baseline_for_issue2 = get_prompt_baseline(
            "implementer", issue_number=2, state_dir=state_dir
        )
        assert baseline_for_issue2 is None, (
            f"Expected None for issue 2's per-issue lookup (Issue #1082 "
            f"Phase 1a), got {baseline_for_issue2}. The silent fallback to "
            f"issue 1's 800-word baseline guaranteed a first-dispatch block."
        )

        # With no baseline, validation against None is a no-op shrinkage check:
        # the prompt is accepted on its own merits (>= MIN_CRITICAL words).
        result = validate_prompt_word_count(
            "implementer", issue2_prompt, baseline_for_issue2, max_shrinkage=0.15
        )
        assert result.passed is True, (
            f"First dispatch should be allowed when no per-issue baseline "
            f"exists. Decision: passed={result.passed}, reason={result.reason}"
        )
