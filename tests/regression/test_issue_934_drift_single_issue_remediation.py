"""Regression test: Issue #934 - cumulative drift false positive in single-issue remediation.

The cumulative prompt drift detector in unified_pre_tool.py blocked legitimate
same-agent invocations during remediation loops. In a remediation loop (N rounds,
1 issue), round 2's prompt may legitimately be shorter than round 1 because the
remediation scope is narrower — but get_cumulative_shrinkage() compared first vs.
latest observation regardless of how many distinct issues those observations spanned.

The fix gates the drift computation on len(distinct_issues) >= 2. Single-issue
remediation loops return None (no drift signal); true batch mode (>=2 distinct
issues) still triggers drift detection.

Fixes #934.
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Any, Dict

import pytest

# Path depth: tests/regression/ -> parents[2] for project root
REPO_ROOT = Path(__file__).resolve().parents[2]
LIB_DIR = REPO_ROOT / "plugins" / "autonomous-dev" / "lib"
HOOK_DIR = REPO_ROOT / "plugins" / "autonomous-dev" / "hooks"
sys.path.insert(0, str(LIB_DIR))
sys.path.insert(0, str(HOOK_DIR))

from prompt_integrity import (  # noqa: E402
    MAX_CUMULATIVE_SHRINKAGE,
    get_cumulative_shrinkage,
    record_batch_observation,
)


class TestIssue934SingleIssueRemediation:
    """Cumulative drift check must not fire for single-issue remediation loops."""

    def test_same_issue_three_rounds_returns_none(self, tmp_path: Path) -> None:
        """Three observations on the SAME issue (remediation rounds) with
        decreasing word counts must not produce a drift signal.

        This is the core Issue #934 regression: round 2's prompt is legitimately
        shorter (narrower remediation scope) but the detector previously flagged
        it as compression evidence regardless of single-issue context.
        """
        # Same issue #926, three rounds, decreasing word counts (simulating
        # narrowing remediation scope between rounds).
        record_batch_observation("doc-master", issue_number=926, word_count=500, state_dir=tmp_path)
        record_batch_observation("doc-master", issue_number=926, word_count=400, state_dir=tmp_path)
        record_batch_observation("doc-master", issue_number=926, word_count=300, state_dir=tmp_path)

        # 500 -> 300 = 40% drift (would have blocked at 30% threshold), but
        # since all observations are for the same issue, the gate returns None.
        result = get_cumulative_shrinkage("doc-master", state_dir=tmp_path)
        assert result is None, (
            f"Expected None for single-issue remediation loop, got {result}. "
            f"This is the Issue #934 false-positive."
        )

    def test_two_distinct_issues_returns_percentage(self, tmp_path: Path) -> None:
        """Existing behavior preserved: >=2 distinct issues triggers drift computation."""
        # True batch mode: two distinct issues with significant drift.
        record_batch_observation("implementer", issue_number=900, word_count=500, state_dir=tmp_path)
        record_batch_observation("implementer", issue_number=901, word_count=300, state_dir=tmp_path)

        result = get_cumulative_shrinkage("implementer", state_dir=tmp_path)
        assert result is not None, (
            "Expected drift percentage for >=2 distinct issues, got None. "
            "Batch mode drift detection regressed."
        )
        # (500 - 300) / 500 * 100 = 40.0
        assert result == 40.0, f"Expected 40.0% drift, got {result}%"
        # And the value exceeds the threshold, confirming batch mode still fires.
        assert result >= MAX_CUMULATIVE_SHRINKAGE * 100

    def test_missing_issue_field_treated_as_single_issue(self, tmp_path: Path) -> None:
        """Observations with missing issue identifier are discarded from the
        distinct-issue set rather than counted as a pseudo-issue.

        When all observations lack an issue identifier, the distinct set is
        empty (after discarding None), so the gate returns None.
        """
        # Write observations directly with missing "issue" field to simulate
        # legacy or malformed entries.
        obs_path = tmp_path / "prompt_batch_observations.json"
        data: Dict[str, Any] = {
            "reviewer": [
                {"word_count": 500},  # no issue field
                {"word_count": 300},  # no issue field
            ]
        }
        obs_path.write_text(json.dumps(data) + "\n", encoding="utf-8")

        result = get_cumulative_shrinkage("reviewer", state_dir=tmp_path)
        assert result is None, (
            f"Expected None when all observations lack an issue identifier, "
            f"got {result}. None must not be counted as a pseudo-issue."
        )

    def test_mixed_some_missing_issue_field_still_works(self, tmp_path: Path) -> None:
        """If some observations have issue ids and others don't, the gate counts
        only the present ones. If >=2 distinct ids remain, drift is computed."""
        obs_path = tmp_path / "prompt_batch_observations.json"
        data: Dict[str, Any] = {
            "reviewer": [
                {"issue": 100, "word_count": 500},
                {"word_count": 400},  # missing issue id - discarded
                {"issue": 101, "word_count": 300},
            ]
        }
        obs_path.write_text(json.dumps(data) + "\n", encoding="utf-8")

        # Two distinct issues remain after discarding the missing-id entry,
        # so drift is computed using first vs latest observation.
        result = get_cumulative_shrinkage("reviewer", state_dir=tmp_path)
        assert result is not None
        # First word_count = 500, latest = 300 -> 40% shrinkage
        assert result == 40.0


class TestIssue934HookLevelBehavior:
    """Hook-level (validate_prompt_integrity) regression: same-issue, multi-round
    invocations must not be blocked by cumulative drift even with decreasing
    word counts."""

    def test_hook_does_not_block_same_issue_remediation_loop(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Simulate three calls to validate_prompt_integrity for the same agent
        on the same issue with decreasing word counts. Verify the third call
        is NOT blocked by cumulative drift.
        """
        # Redirect prompt_integrity state files to tmp_path so observations
        # don't leak between tests.
        monkeypatch.setenv("PIPELINE_ISSUE_NUMBER", "934")

        # Patch _get_observations_path and _get_baselines_path to write into tmp_path.
        import prompt_integrity as pi

        def fake_obs_path(state_dir: Path | None = None) -> Path:
            return tmp_path / "prompt_batch_observations.json"

        def fake_baselines_path(state_dir: Path | None = None) -> Path:
            return tmp_path / "prompt_baselines.json"

        monkeypatch.setattr(pi, "_get_observations_path", fake_obs_path)
        monkeypatch.setattr(pi, "_get_baselines_path", fake_baselines_path)

        # Import the hook function after patching.
        import unified_pre_tool as upt
        # Also patch in the hook module's namespace if it re-exports
        # (defensive: the hook imports from prompt_integrity at call time).

        # Build a prompt with enough words to pass the minimum word-count check
        # but decreasing across calls to simulate a remediation loop scope
        # narrowing.
        def make_prompt(word_count: int) -> str:
            return " ".join(["word"] * word_count)

        tool_input_round1: Dict[str, Any] = {
            "subagent_type": "doc-master",
            "prompt": make_prompt(500),
        }
        tool_input_round2: Dict[str, Any] = {
            "subagent_type": "doc-master",
            "prompt": make_prompt(400),
        }
        tool_input_round3: Dict[str, Any] = {
            "subagent_type": "doc-master",
            "prompt": make_prompt(300),
        }

        # Call the hook three times for the same agent on the same issue.
        decision1, _ = upt.validate_prompt_integrity("Task", tool_input_round1)
        decision2, _ = upt.validate_prompt_integrity("Task", tool_input_round2)
        decision3, reason3 = upt.validate_prompt_integrity("Task", tool_input_round3)

        # The third call must NOT be blocked by cumulative drift even though
        # 500 -> 300 = 40% drift, because all three observations are for the
        # same issue (#934).
        # NOTE: rounds 2 and 3 may legitimately be blocked by the per-issue
        # baseline shrinkage check (separate mechanism, 20% threshold against
        # the per-issue baseline). That is correct behavior and outside the
        # scope of Issue #934. This test only asserts that the CUMULATIVE
        # drift reason is not the cause of any block.
        # If a block fires, it must NOT be for cumulative drift across the batch.
        if decision3 == "deny":
            assert "Cumulative prompt drift" not in reason3, (
                f"Hook blocked round 3 with cumulative-drift reason despite single-issue "
                f"remediation loop. This is the Issue #934 false positive. Reason: {reason3}"
            )
