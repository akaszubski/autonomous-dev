"""
Regression tests for Issue #867 — cross-issue baseline lookup.

History:
    Issue #867 originally added a silent cross-issue fallback INSIDE
    ``get_prompt_baseline()``: when ``issue_number`` was provided but no
    per-issue baseline existed, the function silently returned the
    lowest-issue baseline. The intent was to keep cross-issue shrinkage
    detection working in batch mode.

    Issue #1082 Phase 1a removed that silent fallback because it directly
    contradicted Issue #764's per-issue isolation contract — every new issue's
    FIRST dispatch in a batch inherited a prior issue's baseline and was
    guaranteed to trip the 20% shrinkage gate against it.

    The new contract:
        - ``get_prompt_baseline(agent_type, issue_number=N)`` returns the
          per-issue baseline for N, or None if absent. NO silent fallback.
        - ``get_cross_issue_baseline(agent_type, exclude_issue=N)`` is the
          explicit, opt-in API for the previous silent-fallback behavior.
        - Cross-issue *drift detection* in batch mode is the job of
          ``record_batch_observation()`` + ``get_cumulative_shrinkage()``
          (Issue #794), which tracks the full trajectory across the batch
          and reports cumulative drift against ``MAX_CUMULATIVE_SHRINKAGE``.

    These regression tests now lock in the post-#1082-Phase-1a contract.
"""

import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
LIB_DIR = REPO_ROOT / "plugins" / "autonomous-dev" / "lib"
if str(LIB_DIR) not in sys.path:
    sys.path.insert(0, str(LIB_DIR))

from prompt_integrity import (
    MAX_CUMULATIVE_SHRINKAGE,
    clear_batch_observations,
    clear_prompt_baselines,
    get_cross_issue_baseline,
    get_cumulative_shrinkage,
    get_prompt_baseline,
    record_batch_observation,
    record_prompt_baseline,
    validate_prompt_word_count,
)


class TestIssue867CrossIssueBaselineFallback:
    """Regression: explicit cross-issue baseline lookup + cumulative drift detection.

    Post Issue #1082 Phase 1a: ``get_prompt_baseline()`` is strictly per-issue.
    Cross-issue lookup goes through ``get_cross_issue_baseline()``; cross-issue
    drift detection goes through ``record_batch_observation()`` +
    ``get_cumulative_shrinkage()``.
    """

    def test_per_issue_baseline_returned_when_exists(self, tmp_path: Path) -> None:
        """``get_prompt_baseline`` returns the per-issue baseline when present.

        Unchanged from the original #867 contract — positive per-issue lookup
        is the same before and after #1082 Phase 1a.
        """
        state_dir = tmp_path / "state"
        state_dir.mkdir()
        clear_prompt_baselines(state_dir=state_dir)

        record_prompt_baseline(
            "implementer", issue_number=5, word_count=400, state_dir=state_dir
        )

        baseline = get_prompt_baseline(
            "implementer", issue_number=5, state_dir=state_dir
        )
        assert baseline == 400

    def test_fallback_to_lowest_issue_when_no_per_issue_baseline(
        self, tmp_path: Path
    ) -> None:
        """Cross-issue lookup is now explicit via ``get_cross_issue_baseline()``.

        Rewritten for Issue #1082 Phase 1a. The original test asserted that
        ``get_prompt_baseline(issue_number=860)`` silently returned the
        lowest-issue baseline. The new contract: callers that want cross-issue
        baselines MUST ask for them explicitly via ``get_cross_issue_baseline``.
        """
        state_dir = tmp_path / "state"
        state_dir.mkdir()
        clear_prompt_baselines(state_dir=state_dir)

        # Record baseline for issue 851 (first issue in batch)
        record_prompt_baseline(
            "security-auditor", issue_number=851, word_count=284, state_dir=state_dir
        )

        # Per-issue lookup for a brand-new issue MUST return None
        # (Issue #1082 Phase 1a — no silent fallback).
        per_issue = get_prompt_baseline(
            "security-auditor", issue_number=860, state_dir=state_dir
        )
        assert per_issue is None, (
            f"Expected None for new issue's per-issue baseline (Issue #1082 "
            f"Phase 1a contract), got {per_issue}. The silent cross-issue "
            f"fallback that produced the #764 first-dispatch block is gone."
        )

        # Explicit cross-issue lookup returns the lowest-issue baseline.
        cross_issue = get_cross_issue_baseline(
            "security-auditor", state_dir=state_dir
        )
        assert cross_issue == 284, (
            f"Expected explicit cross-issue baseline 284 (issue #851), "
            f"got {cross_issue}."
        )

    def test_returns_none_when_no_baselines_exist(self, tmp_path: Path) -> None:
        """``get_prompt_baseline`` returns None when no baselines exist at all.

        Unchanged from the original #867 contract.
        """
        state_dir = tmp_path / "state"
        state_dir.mkdir()
        clear_prompt_baselines(state_dir=state_dir)

        baseline = get_prompt_baseline(
            "implementer", issue_number=1, state_dir=state_dir
        )
        assert baseline is None

        # Cross-issue lookup with no data should also return None.
        cross = get_cross_issue_baseline("implementer", state_dir=state_dir)
        assert cross is None

    def test_cross_issue_shrinkage_detected_end_to_end(
        self, tmp_path: Path
    ) -> None:
        """End-to-end cross-issue drift detection via Issue #794's mechanism.

        Rewritten for Issue #1082 Phase 1a. The original test relied on the
        silent fallback in ``get_prompt_baseline`` to fabricate a cross-issue
        baseline. That mechanism is gone. Cross-issue drift is now the job of
        ``record_batch_observation()`` + ``get_cumulative_shrinkage()``.

        Scenario: a batch processes issues #1 -> #2 with progressive shrinkage.
        Cumulative drift across the batch trips ``MAX_CUMULATIVE_SHRINKAGE``.
        """
        state_dir = tmp_path / "state"
        state_dir.mkdir()
        clear_prompt_baselines(state_dir=state_dir)
        clear_batch_observations(state_dir=state_dir)

        # Issue #1 dispatch: 300-word prompt observed.
        record_batch_observation(
            "security-auditor", issue_number=1, word_count=300,
            state_dir=state_dir,
        )

        # Issue #2 dispatch: 130-word prompt observed.
        # 300 -> 130 = ~57% cumulative shrinkage, well above the 30% threshold.
        record_batch_observation(
            "security-auditor", issue_number=2, word_count=130,
            state_dir=state_dir,
        )

        cumulative = get_cumulative_shrinkage(
            "security-auditor", state_dir=state_dir
        )
        assert cumulative is not None, (
            "Cumulative drift should be computable after >=2 observations."
        )
        assert cumulative > MAX_CUMULATIVE_SHRINKAGE * 100, (
            f"Expected cumulative shrinkage > {MAX_CUMULATIVE_SHRINKAGE:.0%} "
            f"to be detected, got {cumulative}%."
        )

    def test_fallback_selects_lowest_issue_number(self, tmp_path: Path) -> None:
        """``get_cross_issue_baseline()`` picks the lowest-numbered issue.

        Rewritten for Issue #1082 Phase 1a. The selection rule (lowest issue
        number wins) moved from inside ``get_prompt_baseline`` to the dedicated
        ``get_cross_issue_baseline`` function.
        """
        state_dir = tmp_path / "state"
        state_dir.mkdir()
        clear_prompt_baselines(state_dir=state_dir)

        # Record baselines for issues 10, 3, and 7 (out of natural order).
        record_prompt_baseline(
            "implementer", issue_number=10, word_count=200, state_dir=state_dir
        )
        record_prompt_baseline(
            "implementer", issue_number=3, word_count=450, state_dir=state_dir
        )
        record_prompt_baseline(
            "implementer", issue_number=7, word_count=350, state_dir=state_dir
        )

        # Cross-issue lookup returns the lowest-numbered issue's baseline.
        cross = get_cross_issue_baseline("implementer", state_dir=state_dir)
        assert cross == 450, (
            f"Expected lowest-issue (#3) baseline 450, got {cross}."
        )

        # Excluding issue #3 promotes #7 to the lowest.
        cross_excl = get_cross_issue_baseline(
            "implementer", exclude_issue=3, state_dir=state_dir
        )
        assert cross_excl == 350, (
            f"Expected exclude_issue=3 to promote issue #7 (350), got {cross_excl}."
        )

    def test_per_issue_baseline_preferred_over_fallback(
        self, tmp_path: Path
    ) -> None:
        """``get_prompt_baseline()`` returns the per-issue baseline when one exists.

        Simplified for Issue #1082 Phase 1a. The original test asserted that
        per-issue takes precedence over the silent cross-issue fallback. There
        is no longer any fallback to compete with, so this test just confirms
        the basic per-issue contract.
        """
        state_dir = tmp_path / "state"
        state_dir.mkdir()
        clear_prompt_baselines(state_dir=state_dir)

        record_prompt_baseline(
            "implementer", issue_number=1, word_count=500, state_dir=state_dir
        )
        record_prompt_baseline(
            "implementer", issue_number=2, word_count=300, state_dir=state_dir
        )

        # Issue #2 has its own baseline -- returned as-is.
        baseline = get_prompt_baseline(
            "implementer", issue_number=2, state_dir=state_dir
        )
        assert baseline == 300

        # Issue #1 still retrievable independently.
        baseline_1 = get_prompt_baseline(
            "implementer", issue_number=1, state_dir=state_dir
        )
        assert baseline_1 == 500
