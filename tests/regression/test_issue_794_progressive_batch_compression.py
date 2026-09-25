"""Regression test: Issue #794 — progressive compression detection across batch iterations.

The fix adds cumulative drift tracking via record_batch_observation() and
get_cumulative_shrinkage() so that progressive 3-5% per-iteration compression
that individually passes the 25% per-issue threshold is detected when it
accumulates beyond 20% total.
"""

import json
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

# Path depth: tests/regression/ -> parents[2] for project root
REPO_ROOT = Path(__file__).resolve().parents[2]
LIB_DIR = REPO_ROOT / "plugins" / "autonomous-dev" / "lib"
HOOK_DIR = REPO_ROOT / "plugins" / "autonomous-dev" / "hooks"
sys.path.insert(0, str(LIB_DIR))
sys.path.insert(0, str(HOOK_DIR))

from prompt_integrity import (
    MAX_CUMULATIVE_SHRINKAGE,
    clear_batch_observations,
    clear_prompt_baselines,
    get_cumulative_shrinkage,
    record_batch_observation,
    record_prompt_baseline,
)


class TestCumulativeDriftTracking:
    """Tests for cumulative drift detection across batch iterations."""

    def test_cumulative_shrinkage_detected_across_issues(self, tmp_path: Path) -> None:
        """Simulate 250->230->210->190->170->150->120 progression.

        Each step is <25% from previous, but 250->120 = 52% total drift.
        """
        observations = [250, 230, 210, 190, 170, 150, 120]
        for i, wc in enumerate(observations):
            record_batch_observation("reviewer", issue_number=i + 1, word_count=wc, state_dir=tmp_path)

        result = get_cumulative_shrinkage("reviewer", state_dir=tmp_path)
        assert result is not None
        assert result == 52.0  # (250 - 120) / 250 * 100

    def test_cumulative_below_threshold_passes(self, tmp_path: Path) -> None:
        """250->240->230->220 (~12%). Below 20% threshold."""
        for i, wc in enumerate([250, 240, 230, 220]):
            record_batch_observation("reviewer", issue_number=i + 1, word_count=wc, state_dir=tmp_path)

        result = get_cumulative_shrinkage("reviewer", state_dir=tmp_path)
        assert result is not None
        assert result == 12.0  # (250 - 220) / 250 * 100
        assert result < MAX_CUMULATIVE_SHRINKAGE * 100

    def test_cumulative_at_threshold_boundary(self, tmp_path: Path) -> None:
        """250->174 exactly (~30.4%). Test boundary behavior — just over 30% is blocked (Issue #870)."""
        record_batch_observation("reviewer", 1, 250, state_dir=tmp_path)
        record_batch_observation("reviewer", 2, 174, state_dir=tmp_path)

        result = get_cumulative_shrinkage("reviewer", state_dir=tmp_path)
        assert result == 30.4  # Just over threshold (raised to 30% in Issue #870)

    def test_single_observation_returns_none(self, tmp_path: Path) -> None:
        """Only 1 observation recorded. Returns None (no drift calculable)."""
        record_batch_observation("reviewer", 1, 250, state_dir=tmp_path)

        result = get_cumulative_shrinkage("reviewer", state_dir=tmp_path)
        assert result is None

    def test_clear_batch_observations_resets(self, tmp_path: Path) -> None:
        """Record observations, clear, verify get_cumulative_shrinkage returns None."""
        record_batch_observation("reviewer", 1, 250, state_dir=tmp_path)
        record_batch_observation("reviewer", 2, 200, state_dir=tmp_path)

        # Verify observations exist
        assert get_cumulative_shrinkage("reviewer", state_dir=tmp_path) is not None

        # Clear and verify reset
        clear_batch_observations(state_dir=tmp_path)
        assert get_cumulative_shrinkage("reviewer", state_dir=tmp_path) is None

    def test_nonexistent_agent_returns_none(self, tmp_path: Path) -> None:
        """get_cumulative_shrinkage for unknown agent returns None gracefully."""
        result = get_cumulative_shrinkage("nonexistent-agent", state_dir=tmp_path)
        assert result is None

    def test_growth_returns_zero(self, tmp_path: Path) -> None:
        """If prompt grows rather than shrinks, returns 0.0 not negative."""
        record_batch_observation("reviewer", 1, 200, state_dir=tmp_path)
        record_batch_observation("reviewer", 2, 250, state_dir=tmp_path)

        result = get_cumulative_shrinkage("reviewer", state_dir=tmp_path)
        assert result == 0.0

    def test_hook_blocks_on_cumulative_drift(self, tmp_path: Path) -> None:
        """Integration test: hook returns deny when cumulative exceeds 20%."""
        import unified_pre_tool as hook

        prompt = " ".join(f"word{i}" for i in range(150))  # 150 words, above minimum

        # Mock so per-issue baseline check passes but cumulative drift exceeds threshold
        passing_result = type("Result", (), {
            "passed": True, "shrinkage_pct": 5.0, "word_count": 150,
            "baseline_word_count": 160, "reason": "OK", "should_reload": False,
            "agent_type": "reviewer",
        })()

        with (
            patch("prompt_integrity.get_prompt_baseline", return_value=160),
            patch("prompt_integrity.validate_prompt_word_count", return_value=passing_result),
            patch("prompt_integrity.record_batch_observation"),
            patch("prompt_integrity.get_cumulative_shrinkage", return_value=25.0),
            patch("prompt_integrity.MAX_CUMULATIVE_SHRINKAGE", 0.20),
        ):
            decision, reason = hook.validate_prompt_integrity(
                "Agent",
                {"subagent_type": "reviewer", "prompt": prompt},
            )

        assert decision == "deny"
        assert "Cumulative" in reason
        assert "25.0%" in reason
        assert "REQUIRED NEXT ACTION" in reason

    def test_max_cumulative_shrinkage_constant(self) -> None:
        """Verify MAX_CUMULATIVE_SHRINKAGE is 0.30 (30%) — raised in Issue #870 from 0.15."""
        assert MAX_CUMULATIVE_SHRINKAGE == 0.30

    def test_observations_persisted_to_json(self, tmp_path: Path) -> None:
        """Verify observations file is valid JSON with expected structure."""
        record_batch_observation("reviewer", 1, 250, state_dir=tmp_path)
        record_batch_observation("reviewer", 2, 230, state_dir=tmp_path)

        obs_path = tmp_path / "prompt_batch_observations.json"
        assert obs_path.exists()

        data = json.loads(obs_path.read_text())
        assert "reviewer" in data
        assert len(data["reviewer"]) == 2
        assert data["reviewer"][0] == {"issue": 1, "word_count": 250}
        assert data["reviewer"][1] == {"issue": 2, "word_count": 230}


# Shared helpers/fixtures for the #1789 lifecycle cases.
# Stale prior-run observations: first=2755 -> latest 1606 = 41.7% drift > 0.30 (the #1789 case).
_STALE_PRIOR_OBSERVATIONS = [(1, 2755), (2, 2400), (3, 2000), (4, 1700)]


def _words(n: int) -> str:
    """A prompt of exactly n plain word-tokens (no reinvocation markers)."""
    return " ".join(f"w{i}" for i in range(n))


def _seed_prior_run_observations(agent: str = "reviewer") -> None:
    """Seed the stale multi-issue observations a prior run would have left behind."""
    for issue, wc in _STALE_PRIOR_OBSERVATIONS:
        record_batch_observation(agent, issue, wc)


def _dispatch(agent_type: str, prompt: str):
    """Invoke the real (executing) hook validator against the isolated state dir."""
    import unified_pre_tool as hook
    return hook.validate_prompt_integrity(
        "Agent", {"subagent_type": agent_type, "prompt": prompt}
    )


@pytest.fixture
def isolated_state(tmp_path, monkeypatch):
    """Redirect prompt_integrity's default baseline/observation paths into tmp_path.

    The hook calls the library with state_dir=None, so isolation must patch the
    module-global path resolvers (not pass state_dir) to reach the real hook path.
    """
    import types

    import prompt_integrity as pi

    baselines = tmp_path / "prompt_baselines.json"
    observations = tmp_path / "prompt_batch_observations.json"
    monkeypatch.setattr(pi, "_get_baselines_path", lambda state_dir=None: baselines)
    monkeypatch.setattr(pi, "_get_observations_path", lambda state_dir=None: observations)

    return types.SimpleNamespace(dir=tmp_path, baselines=baselines, observations=observations)


class TestClearBaselinesCoupling:
    """Issue #1789 / #794: clear_prompt_baselines clears BOTH baseline and observations.

    HELPER-TO-HOOK INTEGRATION scope: these tests call clear_prompt_baselines()
    directly. They verify the fix at the helper level; they do NOT prove actual
    native command-start behavior (full/light STEP-0 reset remains OPEN).
    """

    def test_clear_prompt_baselines_also_clears_observations(self, isolated_state) -> None:
        """Behavioral: the restored #794 coupling — clearing baselines clears observations too."""
        record_prompt_baseline("reviewer", issue_number=1, word_count=2755)
        _seed_prior_run_observations()
        assert isolated_state.baselines.exists()
        assert isolated_state.observations.exists()

        clear_prompt_baselines()

        assert not isolated_state.baselines.exists()
        assert not isolated_state.observations.exists()
        assert get_cumulative_shrinkage("reviewer") is None

    @pytest.mark.parametrize("failing_half", ["baselines", "observations"])
    def test_reset_failure_fails_closed_propagates(self, tmp_path, monkeypatch, failing_half) -> None:
        """Both halves of the coupled reset are fail-CLOSED at the library boundary: a
        failed unlink on EITHER side PROPAGATES, so the caller receives the error
        instead of a silent success on stale gate state (#1789). Proves library
        propagation ONLY — native command-start refusal is NOT proven by this arm and
        remains an open #1789 arm. LOAD-BEARING: swallowing either failure (try/except)
        would make pytest.raises see nothing and fail this arm."""
        import pathlib

        import prompt_integrity as pi
        (tmp_path / "prompt_baselines.json").write_text("{}")
        (tmp_path / "prompt_batch_observations.json").write_text("{}")

        def _raise(*a, **k):
            raise OSError("injected reset failure")

        if failing_half == "observations":
            monkeypatch.setattr(pi, "clear_batch_observations", _raise)
        else:
            orig_unlink = pathlib.Path.unlink

            def boom(self, *a, **k):
                if self.name == "prompt_baselines.json":
                    raise OSError("injected baselines unlink failure")
                return orig_unlink(self, *a, **k)

            monkeypatch.setattr(pathlib.Path, "unlink", boom)

        with pytest.raises(OSError):
            pi.clear_prompt_baselines(state_dir=tmp_path)


class TestPromptIntegrityHelperToHookIntegration:
    """Issue #1789: helper-to-hook integration — clear_prompt_baselines() + the real
    validate_prompt_integrity() called directly.

    Scope: these are INTEGRATION tests at the helper/hook level, NOT proof of native
    command-start behavior. The full/light STEP-0 reset, F0/product acceptance, and the
    hook's template_reload/recovery telemetry label all remain OPEN/unfixed (#1789).
    """

    def _run_fresh_after_prior(self, monkeypatch, *, neutralize_reset: bool):
        """Seed a prior run's stale observations, run the run-start reset, dispatch fresh.

        Returns (decision, reason, cumulative_after_reset). neutralize_reset=True installs
        the pre-#1789 mutant (clear_batch_observations no-op) — the fault control.
        """
        import prompt_integrity as pi
        import unified_pre_tool as hook

        _seed_prior_run_observations()
        assert get_cumulative_shrinkage("reviewer") is not None

        if neutralize_reset:
            monkeypatch.setattr(pi, "clear_batch_observations", lambda *a, **k: None)

        clear_prompt_baselines()  # run-start reset (restored #794 coupling)
        cumulative_after = get_cumulative_shrinkage("reviewer")

        monkeypatch.setattr(hook, "_get_current_issue_number", lambda: 0)
        decision, reason = _dispatch("reviewer", _words(1606))
        return decision, reason, cumulative_after

    def test_within_batch_drift_still_refuses(self, isolated_state, monkeypatch) -> None:
        """Behavioral: >=2 distinct-issue observations exceeding 0.30 still BLOCK (no mid-batch reset)."""
        import unified_pre_tool as hook

        for issue, wc in [(1, 2755), (2, 2200), (3, 1800)]:
            record_batch_observation("reviewer", issue, wc)
        monkeypatch.setattr(hook, "_get_current_issue_number", lambda: 5)

        decision, reason = _dispatch("reviewer", _words(1606))

        assert decision == "deny"
        assert "Cumulative" in reason
        assert "41.7%" in reason  # 2755 -> 1606, over the 0.30 threshold
        assert "REQUIRED NEXT ACTION" in reason

    def test_fresh_run_does_not_inherit_stale_observations(self, isolated_state, monkeypatch) -> None:
        """Behavioral (positive): with the reset, the 41.7% stale-drift case is ALLOWED."""
        decision, reason, cumulative_after = self._run_fresh_after_prior(
            monkeypatch, neutralize_reset=False
        )
        assert cumulative_after is None  # observations gone after coupled reset
        assert decision == "allow", f"fresh run false-blocked: {reason}"

    def test_fault_control_without_reset_false_blocks(self, isolated_state, monkeypatch) -> None:
        """Fault control (load-bearing): neutralize the reset => re-inherit stale drift => false-block."""
        decision, reason, cumulative_after = self._run_fresh_after_prior(
            monkeypatch, neutralize_reset=True
        )
        assert cumulative_after is not None  # stale observations survived the neutralized reset
        assert decision == "deny"
        assert "Cumulative" in reason

    def test_no_baseline_dispatch_records_exactly_once(self, isolated_state, monkeypatch) -> None:
        """Behavioral: the first no-baseline dispatch records exactly one observation (was two)."""
        import unified_pre_tool as hook

        monkeypatch.setattr(hook, "_get_current_issue_number", lambda: 100)

        decision, _ = _dispatch("reviewer", _words(1200))
        assert decision == "allow"

        data = json.loads(isolated_state.observations.read_text())
        assert len(data["reviewer"]) == 1, f"expected one observation, got {data['reviewer']}"
        assert data["reviewer"][0] == {"issue": 100, "word_count": 1200}
