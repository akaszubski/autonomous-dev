#!/usr/bin/env python3
"""Unit tests for the eval-metrics primitives (Issue #1453).

Covers all four families: reliability (pass@k, pass^k), statistical gating
(Wilson interval, gate decision), judge calibration (Cohen's kappa, agreement
report), and contamination detection (CapBencher binomial test). Golden values
are asserted with ``pytest.approx`` at the tolerances specified in the plan.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

# tests/unit/lib/test_eval_metrics.py -> parents[3] == repo root
REPO_ROOT = Path(__file__).resolve().parents[3]
LIB_PATH = REPO_ROOT / "plugins" / "autonomous-dev" / "lib"
if str(LIB_PATH) not in sys.path:
    sys.path.insert(0, str(LIB_PATH))

import eval_metrics  # noqa: E402
from eval_metrics import (  # noqa: E402
    MAX_SAMPLE_SIZE,
    AgreementReport,
    CapBencherResult,
    WilsonInterval,
    agreement_report,
    capbencher_binomial_test,
    cohens_kappa,
    gate_decision,
    pass_at_k,
    pass_hat_k,
    pass_hat_k_dataset,
    wilson_interval,
)


class TestPassAtK:
    """Chen et al. unbiased pass@k estimator."""

    def test_golden(self) -> None:
        assert pass_at_k(10, 3, 5) == pytest.approx(0.9167, abs=1e-4)

    def test_c_zero_returns_zero(self) -> None:
        assert pass_at_k(10, 0, 5) == 0.0

    def test_c_equals_n_returns_one(self) -> None:
        assert pass_at_k(10, 10, 5) == 1.0

    def test_k_greater_than_n_minus_c_returns_one(self) -> None:
        # n - c == 2, k == 5 > 2: every k-subset must contain a correct sample.
        assert pass_at_k(10, 8, 5) == 1.0

    def test_k_greater_than_n_raises(self) -> None:
        with pytest.raises(ValueError):
            pass_at_k(10, 3, 11)

    def test_k_below_one_raises(self) -> None:
        with pytest.raises(ValueError):
            pass_at_k(10, 3, 0)

    def test_c_out_of_range_raises(self) -> None:
        with pytest.raises(ValueError):
            pass_at_k(10, 11, 5)

    def test_n_below_one_raises(self) -> None:
        with pytest.raises(ValueError):
            pass_at_k(0, 0, 1)

    def test_n_exceeds_max_sample_size_raises(self) -> None:
        # Finding 1 (A04): huge n hangs the O(n) product loop; guard rejects it.
        with pytest.raises(ValueError):
            pass_at_k(10**7, 1, 1)

    def test_n_at_max_plus_one_raises(self) -> None:
        # Boundary: MAX_SAMPLE_SIZE + 1 is rejected (guard is strict `>`).
        with pytest.raises(ValueError):
            pass_at_k(MAX_SAMPLE_SIZE + 1, 1, 1)

    def test_modest_n_within_guard_accepted(self) -> None:
        # A modest n well under the cap still computes normally (fast).
        assert 0.0 <= pass_at_k(1000, 3, 5) <= 1.0


class TestPassHatK:
    """pass^k consistency (with-replacement) gating metric."""

    def test_golden(self) -> None:
        assert pass_hat_k(0.61, 8) == pytest.approx(0.0192, abs=1e-4)

    def test_k_one_returns_rate(self) -> None:
        assert pass_hat_k(0.37, 1) == pytest.approx(0.37, abs=1e-4)

    def test_rate_one_returns_one(self) -> None:
        assert pass_hat_k(1.0, 8) == 1.0

    def test_rate_zero_returns_zero(self) -> None:
        assert pass_hat_k(0.0, 8) == 0.0

    def test_rate_out_of_range_raises(self) -> None:
        with pytest.raises(ValueError):
            pass_hat_k(1.5, 2)

    def test_k_below_one_raises(self) -> None:
        with pytest.raises(ValueError):
            pass_hat_k(0.5, 0)


class TestPassHatKDataset:
    """Dataset-level pass^k as mean of per-task powers."""

    def test_mean_of_per_task_powers(self) -> None:
        per_task = [(6, 10), (3, 10)]
        expected = ((0.6**2) + (0.3**2)) / 2
        assert pass_hat_k_dataset(per_task, 2) == pytest.approx(expected, abs=1e-9)

    def test_differs_from_pooled_rate_jensen(self) -> None:
        # Averaging per-task powers must exceed (avg rate)^k for convex x^k.
        per_task = [(9, 10), (1, 10)]
        k = 2
        mean_of_powers = pass_hat_k_dataset(per_task, k)
        mean_rate = (0.9 + 0.1) / 2
        pooled = pass_hat_k(mean_rate, k)
        assert mean_of_powers != pytest.approx(pooled, abs=1e-6)
        assert mean_of_powers > pooled  # Jensen's inequality direction

    def test_empty_raises(self) -> None:
        with pytest.raises(ValueError):
            pass_hat_k_dataset([], 2)

    def test_zero_total_raises(self) -> None:
        with pytest.raises(ValueError):
            pass_hat_k_dataset([(0, 0)], 2)

    def test_k_below_one_raises(self) -> None:
        with pytest.raises(ValueError):
            pass_hat_k_dataset([(1, 2)], 0)

    def test_c_out_of_range_raises(self) -> None:
        # Finding 3: the 0 <= c_i <= n_i guard was untested. c > n and c < 0.
        with pytest.raises(ValueError):
            pass_hat_k_dataset([(11, 10)], 2)
        with pytest.raises(ValueError):
            pass_hat_k_dataset([(-1, 10)], 2)


class TestWilsonInterval:
    """Wilson score confidence interval."""

    def test_golden_bounds(self) -> None:
        wi = wilson_interval(8, 10, 0.95)
        assert wi.lower == pytest.approx(0.4902, abs=1e-3)
        assert wi.upper == pytest.approx(0.9433, abs=1e-3)

    def test_is_dataclass_instance(self) -> None:
        assert isinstance(wilson_interval(8, 10), WilsonInterval)

    def test_point_estimate(self) -> None:
        assert wilson_interval(8, 10).point_estimate == pytest.approx(0.8, abs=1e-9)

    def test_lower_clamped_at_zero_successes(self) -> None:
        assert wilson_interval(0, 10, 0.95).lower == 0.0

    def test_upper_clamped_at_full_successes(self) -> None:
        assert wilson_interval(10, 10, 0.95).upper == 1.0

    def test_bounds_ordering_invariant(self) -> None:
        for successes in range(0, 11):
            wi = wilson_interval(successes, 10, 0.95)
            assert 0.0 <= wi.lower <= wi.upper <= 1.0

    def test_arbitrary_confidence_no_raise(self) -> None:
        wi = wilson_interval(8, 10, 0.975)
        assert 0.0 <= wi.lower <= wi.upper <= 1.0

    def test_successes_out_of_range_raises(self) -> None:
        with pytest.raises(ValueError):
            wilson_interval(11, 10)

    def test_n_below_one_raises(self) -> None:
        with pytest.raises(ValueError):
            wilson_interval(0, 0)

    def test_confidence_out_of_range_raises(self) -> None:
        with pytest.raises(ValueError):
            wilson_interval(5, 10, 1.0)


class TestGateDecision:
    """Non-flaky Wilson-lower-bound gate."""

    def test_pass(self) -> None:
        passed, message = gate_decision(95, 100, baseline=0.80, margin=0.05)
        assert passed is True
        assert "PASS" in message

    def test_fail(self) -> None:
        passed, message = gate_decision(50, 100, baseline=0.80, margin=0.05)
        assert passed is False
        assert "FAIL" in message

    def test_zero_samples(self) -> None:
        passed, message = gate_decision(0, 0, baseline=0.80)
        assert passed is False
        assert "no samples" in message

    def test_message_reports_threshold(self) -> None:
        _, message = gate_decision(90, 100, baseline=0.80, margin=0.05)
        assert "threshold" in message
        assert "wilson_lower" in message


class TestCohensKappa:
    """Cohen's kappa for 2x2 rater agreement."""

    def test_golden(self) -> None:
        assert cohens_kappa(45, 15, 10, 30) == pytest.approx(0.490, abs=1e-3)

    def test_degenerate_pe_one_returns_zero(self) -> None:
        # Both raters said "yes" to everything: p_e == 1.0 -> 0.0, not a raise.
        assert cohens_kappa(50, 0, 0, 0) == 0.0

    def test_negative_kappa_allowed(self) -> None:
        # Worse-than-chance agreement produces a negative kappa.
        kappa = cohens_kappa(5, 20, 20, 5)
        assert kappa < 0.0

    def test_zero_total_raises(self) -> None:
        with pytest.raises(ValueError):
            cohens_kappa(0, 0, 0, 0)


class TestAgreementReport:
    """Agreement report exposing raw agreement and kappa."""

    def test_reports_both_raw_and_kappa(self) -> None:
        report = agreement_report(45, 15, 10, 30)
        assert isinstance(report, AgreementReport)
        assert report.raw_agreement == pytest.approx(0.75, abs=1e-9)
        assert report.kappa == pytest.approx(0.490, abs=1e-3)

    def test_overstatement_gap(self) -> None:
        report = agreement_report(45, 15, 10, 30)
        assert report.overstatement_gap == pytest.approx(
            report.raw_agreement - report.kappa, abs=1e-9
        )
        # Raw agreement overstates chance-corrected agreement here.
        assert report.overstatement_gap > 0.0

    def test_interpretation_band(self) -> None:
        # kappa ~ 0.49 falls in the Landis-Koch "moderate" band.
        assert agreement_report(45, 15, 10, 30).interpretation == "moderate"

    def test_zero_total_raises(self) -> None:
        with pytest.raises(ValueError):
            agreement_report(0, 0, 0, 0)


class TestCapBencherBinomialTest:
    """CapBencher one-sided exact binomial contamination test."""

    def test_golden_pvalue_and_flag(self) -> None:
        result = capbencher_binomial_test(100, 75, 0.5)
        assert result.p_value == pytest.approx(2.82e-07, rel=1e-2)
        assert result.flagged is True

    def test_is_dataclass_instance(self) -> None:
        assert isinstance(capbencher_binomial_test(10, 5, 0.5), CapBencherResult)

    def test_observed_accuracy(self) -> None:
        assert capbencher_binomial_test(100, 75, 0.5).observed_acc == pytest.approx(
            0.75, abs=1e-9
        )

    def test_k_zero_pvalue_one(self) -> None:
        assert capbencher_binomial_test(100, 0, 0.5).p_value == pytest.approx(
            1.0, abs=1e-9
        )

    def test_k_equals_n_pvalue_is_cap_power(self) -> None:
        result = capbencher_binomial_test(10, 10, 0.5)
        assert result.p_value == pytest.approx(0.5**10, rel=1e-9)

    def test_cap_out_of_range_raises(self) -> None:
        with pytest.raises(ValueError):
            capbencher_binomial_test(100, 75, 1.0)

    def test_k_out_of_range_raises(self) -> None:
        with pytest.raises(ValueError):
            capbencher_binomial_test(100, 101, 0.5)

    def test_large_n_stability(self) -> None:
        # Must complete without overflow at large n (log-space summation).
        result = capbencher_binomial_test(10000, 5100, 0.5)
        assert 0.0 <= result.p_value <= 1.0

    def test_not_flagged_when_below_cap(self) -> None:
        result = capbencher_binomial_test(100, 45, 0.5)
        assert result.flagged is False

    def test_n_exceeds_max_sample_size_raises(self) -> None:
        # Finding 1 (A04): huge n hangs the O(n) tail-sum; guard rejects it.
        with pytest.raises(ValueError):
            capbencher_binomial_test(10**7, 1, 0.5)

    def test_n_at_max_plus_one_raises(self) -> None:
        # Boundary: MAX_SAMPLE_SIZE + 1 is rejected (guard is strict `>`).
        with pytest.raises(ValueError):
            capbencher_binomial_test(MAX_SAMPLE_SIZE + 1, 1, 0.5)

    def test_modest_n_within_guard_accepted(self) -> None:
        # A modest n well under the cap still computes normally (fast).
        result = capbencher_binomial_test(1000, 500, 0.5)
        assert 0.0 <= result.p_value <= 1.0

    def test_alpha_zero_raises(self) -> None:
        # Finding 2 (A04): alpha must be in (0, 1); 0.0 makes flag un-triggerable.
        with pytest.raises(ValueError):
            capbencher_binomial_test(100, 75, 0.5, alpha=0.0)

    def test_alpha_one_raises(self) -> None:
        with pytest.raises(ValueError):
            capbencher_binomial_test(100, 75, 0.5, alpha=1.0)

    def test_alpha_negative_raises(self) -> None:
        with pytest.raises(ValueError):
            capbencher_binomial_test(100, 75, 0.5, alpha=-0.1)

    def test_alpha_above_one_raises(self) -> None:
        with pytest.raises(ValueError):
            capbencher_binomial_test(100, 75, 0.5, alpha=1.5)

    def test_default_alpha_accepted(self) -> None:
        # The default alpha=0.05 still works unchanged.
        result = capbencher_binomial_test(100, 75, 0.5)
        assert result.alpha == 0.05
        assert result.flagged is True


class TestModuleSurface:
    """Module-level invariants."""

    def test_all_symbols_importable(self) -> None:
        for name in eval_metrics.__all__:
            assert hasattr(eval_metrics, name), f"{name} missing from module"
