#!/usr/bin/env python3
"""Evaluation-metrics primitives for LLM/agent evals (Issue #1453).

CORE, dependency-free building blocks used to score model/agent evaluations.
Four families of primitives are provided:

1. Reliability
   - ``pass_at_k``: Chen et al. unbiased pass@k estimator (any-of-k success).
   - ``pass_hat_k`` / ``pass_hat_k_dataset``: consistency metric (all-of-k
     success under resampling) — THE gating metric, distinct from pass@k.
2. Statistical gating
   - ``wilson_interval`` / ``WilsonInterval``: non-flaky score-rate confidence
     bounds via the Wilson score interval.
   - ``gate_decision``: pass/fail gate using the Wilson lower bound vs a
     baseline minus margin.
3. Judge calibration
   - ``cohens_kappa``: chance-corrected inter-rater agreement (2x2).
   - ``agreement_report`` / ``AgreementReport``: reports both raw agreement and
     kappa, exposing the overstatement gap.
4. Contamination detection
   - ``capbencher_binomial_test`` / ``CapBencherResult``: one-sided exact
     binomial test (Karlin-Rubin UMP) flagging accuracy above a Bayes cap.

Constraints:
    - stdlib-only. Imports are limited to ``math``, ``statistics``,
      ``dataclasses``, ``typing``, and ``__future__``.
    - No egress: no file I/O, no network, no subprocess. Every function is a
      pure computation over its arguments.

Deferred / follow-ups (intentionally NOT implemented here):
    - Judge-panel aggregation (majority/weighted vote across judges) — ships
      with the #1452 judge wiring.
    - DeepEval integration (adapters to the DeepEval metric suite).
    - Trajectory / span evals (per-step agent scoring) — needs #1452.
    - Krippendorff's alpha for >2 raters (this module only covers the 2-rater
      2x2 case via Cohen's kappa).
    - Sealed-holdout plumbing into ``/autoresearch`` and ``/improve``.

Related:
    - GitHub Issue #1453: CORE eval-metrics primitives module.
"""

from __future__ import annotations

import math
import statistics
from dataclasses import dataclass, field
from typing import Sequence, Tuple

# Upper bound on ``n`` for the O(n) tail-sum paths (``pass_at_k`` product loop
# and the ``_one_sided_binom_pvalue`` tail sum). Realistic eval-suite sizes are
# in the thousands; this guard prevents an accidental/buggy/untrusted huge ``n``
# (e.g. 10**9) from hanging the synchronous call once these primitives are wired
# into ``/autoresearch`` and ``/improve`` per the deferred block above.
MAX_SAMPLE_SIZE = 1_000_000

# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------


def _log_comb(n: int, i: int) -> float:
    """Return the natural log of the binomial coefficient C(n, i).

    Uses log-gamma so that large ``n`` does not overflow an intermediate
    factorial. ``lgamma(x + 1) == log(x!)``.

    Args:
        n: Total number of items (``n >= 0``).
        i: Number chosen (``0 <= i <= n``).

    Returns:
        ``log(C(n, i))`` as a float.
    """
    return math.lgamma(n + 1) - math.lgamma(i + 1) - math.lgamma(n - i + 1)


def _one_sided_binom_pvalue(n: int, k: int, p0: float) -> float:
    """Return the upper-tail binomial p-value ``P(X >= k | X ~ Binom(n, p0))``.

    Computed in log-space and summed with :func:`math.fsum` for numerical
    stability at large ``n``.

    Args:
        n: Number of trials (``n >= 0``).
        k: Observed (or hypothesised) number of successes (``0 <= k <= n``).
        p0: Success probability under the null hypothesis (``0 < p0 < 1``).

    Returns:
        The upper-tail probability ``sum_{i=k..n} C(n, i) p0^i (1-p0)^(n-i)``.
    """
    log_p0 = math.log(p0)
    log_q0 = math.log1p(-p0)
    terms = [
        math.exp(_log_comb(n, i) + i * log_p0 + (n - i) * log_q0)
        for i in range(k, n + 1)
    ]
    return math.fsum(terms)


# ---------------------------------------------------------------------------
# (1) Reliability
# ---------------------------------------------------------------------------


def pass_at_k(n: int, c: int, k: int) -> float:
    """Return the Chen et al. unbiased pass@k estimator.

    ``pass@k`` estimates the probability that at least one of ``k`` samples
    drawn (without replacement) from ``n`` total samples is correct, given that
    ``c`` of the ``n`` samples are correct. The estimator is
    ``1 - C(n - c, k) / C(n, k)``, evaluated with the numerically stable
    product form ``1 - prod_{i=n-c+1..n} (1 - k / i)`` (Chen et al. 2021,
    "Evaluating Large Language Models Trained on Code").

    Args:
        n: Total number of samples generated (``n >= 1``).
        c: Number of correct samples (``0 <= c <= n``).
        k: Number of samples considered per attempt (``1 <= k <= n``).

    Returns:
        The pass@k estimate in ``[0.0, 1.0]``.

    Raises:
        ValueError: If ``n < 1``, ``c`` is outside ``[0, n]``, ``k < 1``,
            ``k > n``, or ``n > MAX_SAMPLE_SIZE``.
    """
    if n < 1:
        raise ValueError(f"n must be >= 1, got {n}")
    if n > MAX_SAMPLE_SIZE:
        raise ValueError(f"n={n} exceeds MAX_SAMPLE_SIZE={MAX_SAMPLE_SIZE}")
    if not 0 <= c <= n:
        raise ValueError(f"c must satisfy 0 <= c <= n (n={n}), got {c}")
    if k < 1:
        raise ValueError(f"k must be >= 1, got {k}")
    if k > n:
        raise ValueError(f"k must be <= n (n={n}), got {k}")

    if c == 0:
        return 0.0
    if c == n:
        return 1.0
    # If k > n - c, every choice of k must include a correct sample.
    if k > n - c:
        return 1.0

    product = 1.0
    for i in range(n - c + 1, n + 1):
        product *= 1.0 - k / i
    return 1.0 - product


def pass_hat_k(success_rate: float, k: int) -> float:
    """Return the pass^k consistency metric ``success_rate ** k``.

    This is the CONSISTENCY metric: the probability that ``k`` independent
    samples (drawn WITH replacement, i.e. resampled) are ALL correct. It is
    DISTINCT from :func:`pass_at_k` (which measures any-of-k success). pass^k is
    THE GATING metric for reliability — a system that is right once in a while
    but not consistently will have a high pass@k yet a low pass^k.

    Args:
        success_rate: Per-sample success probability (``0.0 <= rate <= 1.0``).
        k: Number of independent samples required to all succeed (``k >= 1``).

    Returns:
        ``success_rate ** k`` in ``[0.0, 1.0]``.

    Raises:
        ValueError: If ``success_rate`` is outside ``[0.0, 1.0]`` or ``k < 1``.
    """
    if not 0.0 <= success_rate <= 1.0:
        raise ValueError(f"success_rate must be in [0.0, 1.0], got {success_rate}")
    if k < 1:
        raise ValueError(f"k must be >= 1, got {k}")
    return success_rate**k


def pass_hat_k_dataset(per_task: Sequence[Tuple[int, int]], k: int) -> float:
    """Return the dataset-level pass^k as the mean of per-task pass^k values.

    For each task ``i`` with ``c_i`` correct out of ``n_i`` samples, the per-task
    consistency is ``(c_i / n_i) ** k``. The dataset metric is the mean of those
    per-task powers.

    This MUST average the per-task powers, NOT raise the average success rate to
    the ``k`` power. By Jensen's inequality, ``mean((c_i/n_i)^k)`` >=
    ``(mean(c_i/n_i))^k`` for the convex function ``x^k`` (``k >= 1``), so using
    the pooled rate would systematically understate consistency. Averaging the
    powers per task avoids that bias.

    Args:
        per_task: Sequence of ``(correct, total)`` pairs, one per task.
        k: Number of independent samples required to all succeed (``k >= 1``).

    Returns:
        The mean per-task pass^k value in ``[0.0, 1.0]``.

    Raises:
        ValueError: If ``per_task`` is empty, ``k < 1``, or any task has
            ``total == 0`` (or a total/correct pair outside ``0 <= c <= n``).
    """
    if k < 1:
        raise ValueError(f"k must be >= 1, got {k}")
    if not per_task:
        raise ValueError("per_task must be non-empty")

    powers = []
    for idx, (c_i, n_i) in enumerate(per_task):
        if n_i == 0:
            raise ValueError(f"task {idx} has total n_i == 0 (division undefined)")
        if not 0 <= c_i <= n_i:
            raise ValueError(
                f"task {idx} must satisfy 0 <= c <= n (n={n_i}), got c={c_i}"
            )
        rate = c_i / n_i
        powers.append(rate**k)
    return statistics.fmean(powers)


# ---------------------------------------------------------------------------
# (2) Statistical gating
# ---------------------------------------------------------------------------


@dataclass
class WilsonInterval:
    """Wilson score confidence interval for a success rate.

    Attributes:
        successes: Number of observed successes (``0 <= successes <= n``).
        n: Number of trials (``n >= 1``).
        confidence: Two-sided confidence level (``0 < confidence < 1``).
        point_estimate: Computed observed rate ``successes / n``.
        lower: Computed clamped lower bound in ``[0.0, 1.0]``.
        upper: Computed clamped upper bound in ``[0.0, 1.0]``.
        z: Computed two-sided z critical value for ``confidence``.
    """

    successes: int
    n: int
    confidence: float = 0.95
    point_estimate: float = field(init=False)
    lower: float = field(init=False)
    upper: float = field(init=False)
    z: float = field(init=False)

    def __post_init__(self) -> None:
        """Compute the point estimate, z critical value, and clamped bounds."""
        if self.n < 1:
            raise ValueError(f"n must be >= 1, got {self.n}")
        if not 0 <= self.successes <= self.n:
            raise ValueError(
                f"successes must satisfy 0 <= successes <= n (n={self.n}), "
                f"got {self.successes}"
            )
        if not 0.0 < self.confidence < 1.0:
            raise ValueError(
                f"confidence must be in (0, 1), got {self.confidence}"
            )

        n = self.n
        p_hat = self.successes / n
        q_hat = 1.0 - p_hat
        # Two-sided z: inv_cdf at 1 - alpha/2. No hardcoded z-table.
        z = statistics.NormalDist().inv_cdf(1.0 - (1.0 - self.confidence) / 2.0)

        denom = 2.0 * (n + z * z)
        center = 2.0 * n * p_hat + z * z
        spread = z * math.sqrt(z * z + 4.0 * n * p_hat * q_hat)
        lower = (center - spread) / denom
        upper = (center + spread) / denom

        # Clamp: the closed form can underflow to a tiny negative (e.g. -2e-17)
        # at p_hat == 0, or overshoot 1.0 at p_hat == 1.
        self.point_estimate = p_hat
        self.z = z
        self.lower = max(0.0, lower)
        self.upper = min(1.0, upper)


def wilson_interval(
    successes: int, n: int, confidence: float = 0.95
) -> WilsonInterval:
    """Return the Wilson score interval for an observed success rate.

    The Wilson score interval is well-behaved for extreme rates and small
    samples (unlike the normal-approximation "Wald" interval), which makes it
    suitable for non-flaky eval gating. The z critical value is derived from
    :class:`statistics.NormalDist` rather than a hardcoded table.

    Args:
        successes: Number of observed successes (``0 <= successes <= n``).
        n: Number of trials (``n >= 1``).
        confidence: Two-sided confidence level (``0 < confidence < 1``).

    Returns:
        A :class:`WilsonInterval` with clamped ``lower``/``upper`` bounds
        satisfying ``0 <= lower <= upper <= 1``.

    Raises:
        ValueError: If ``n < 1``, ``successes`` is outside ``[0, n]``, or
            ``confidence`` is outside ``(0, 1)``.
    """
    return WilsonInterval(successes=successes, n=n, confidence=confidence)


def gate_decision(
    successes: int,
    n: int,
    baseline: float,
    margin: float = 0.05,
    confidence: float = 0.95,
) -> Tuple[bool, str]:
    """Return a non-flaky pass/fail gate decision for an eval score rate.

    The gate passes when the Wilson lower confidence bound is at or above
    ``baseline - margin``. Using the lower bound (rather than the point
    estimate) makes the gate robust to sampling noise: a lucky run whose point
    estimate clears the bar but whose lower bound does not will NOT pass.

    Args:
        successes: Number of observed successes (``0 <= successes <= n``).
        n: Number of trials. ``n == 0`` short-circuits to a failing gate.
        baseline: Target success rate to compare against.
        margin: Allowed slack below ``baseline`` (default 0.05).
        confidence: Confidence level for the Wilson interval (default 0.95).

    Returns:
        ``(passed, message)`` where ``message`` states the point estimate, the
        Wilson lower bound, the ``baseline - margin`` threshold, and the verdict.
    """
    if n == 0:
        return (False, "no samples: n == 0, cannot evaluate gate")

    interval = wilson_interval(successes, n, confidence)
    threshold = baseline - margin
    passed = interval.lower >= threshold
    verdict = "PASS" if passed else "FAIL"
    message = (
        f"{verdict}: point={interval.point_estimate:.4f}, "
        f"wilson_lower={interval.lower:.4f}, "
        f"threshold={threshold:.4f} (baseline {baseline:.4f} - margin {margin:.4f})"
    )
    return (passed, message)


# ---------------------------------------------------------------------------
# (3) Judge calibration
# ---------------------------------------------------------------------------


def cohens_kappa(a: int, b: int, c: int, d: int) -> float:
    """Return Cohen's kappa for a 2x2 rater-agreement confusion matrix.

    The four cells describe two raters over the same items:
        - ``a``: both raters said "yes".
        - ``b``: rater 1 said "yes", rater 2 said "no".
        - ``c``: rater 1 said "no", rater 2 said "yes".
        - ``d``: both raters said "no".

    Kappa is ``(p_o - p_e) / (1 - p_e)`` where ``p_o`` is the observed agreement
    and ``p_e`` is the chance agreement,
    ``p_e = (row_yes * col_yes + row_no * col_no) / N^2``.

    When ``p_e == 1.0`` (both raters answered a single class for every item),
    chance-corrected agreement is undefined (0/0). This returns ``0.0`` in that
    degenerate case rather than raising ``ZeroDivisionError`` — with no residual
    disagreement to correct for, there is no evidence of agreement beyond
    chance. Negative kappa (worse-than-chance agreement) is allowed.

    Args:
        a: Count of both-yes agreements.
        b: Count of rater1-yes / rater2-no disagreements.
        c: Count of rater1-no / rater2-yes disagreements.
        d: Count of both-no agreements.

    Returns:
        Cohen's kappa, which may be negative.

    Raises:
        ValueError: If the total ``N == a + b + c + d`` is zero.
    """
    n = a + b + c + d
    if n == 0:
        raise ValueError("total N must be > 0 (all cells are zero)")

    p_o = (a + d) / n
    row_yes = a + b
    row_no = c + d
    col_yes = a + c
    col_no = b + d
    p_e = (row_yes * col_yes + row_no * col_no) / (n * n)

    if p_e == 1.0:
        # Degenerate: no chance-disagreement to correct for. Undefined -> 0.0.
        return 0.0
    return (p_o - p_e) / (1.0 - p_e)


def _landis_koch_band(kappa: float) -> str:
    """Return the Landis-Koch interpretation band for a kappa value.

    The bands are a widely cited convention (Landis & Koch, 1977), NOT a
    statistical law — treat them as rough guidance, not hard thresholds.

    Args:
        kappa: A Cohen's kappa value.

    Returns:
        One of: ``"poor"``, ``"slight"``, ``"fair"``, ``"moderate"``,
        ``"substantial"``, or ``"almost perfect"``.
    """
    if kappa < 0.0:
        return "poor"
    if kappa <= 0.20:
        return "slight"
    if kappa <= 0.40:
        return "fair"
    if kappa <= 0.60:
        return "moderate"
    if kappa <= 0.80:
        return "substantial"
    return "almost perfect"


@dataclass
class AgreementReport:
    """Inter-rater agreement report exposing both raw agreement and kappa.

    Attributes:
        a: Count of both-yes agreements.
        b: Count of rater1-yes / rater2-no disagreements.
        c: Count of rater1-no / rater2-yes disagreements.
        d: Count of both-no agreements.
        raw_agreement: Computed observed agreement ``p_o = (a + d) / N``.
        kappa: Computed Cohen's kappa.
        overstatement_gap: Computed ``raw_agreement - kappa`` — how much raw
            agreement overstates chance-corrected agreement.
        interpretation: Computed Landis-Koch band for ``kappa``.
    """

    a: int
    b: int
    c: int
    d: int
    raw_agreement: float = field(init=False)
    kappa: float = field(init=False)
    overstatement_gap: float = field(init=False)
    interpretation: str = field(init=False)

    def __post_init__(self) -> None:
        """Compute raw agreement, kappa, overstatement gap, and interpretation."""
        n = self.a + self.b + self.c + self.d
        if n == 0:
            raise ValueError("total N must be > 0 (all cells are zero)")
        self.raw_agreement = (self.a + self.d) / n
        self.kappa = cohens_kappa(self.a, self.b, self.c, self.d)
        self.overstatement_gap = self.raw_agreement - self.kappa
        self.interpretation = _landis_koch_band(self.kappa)


def agreement_report(a: int, b: int, c: int, d: int) -> AgreementReport:
    """Return an :class:`AgreementReport` reporting BOTH raw agreement and kappa.

    Raw agreement (``p_o``) must NEVER be the headline metric: it is inflated by
    chance agreement and can look impressive even for near-random raters. Kappa
    is the headline; raw agreement and the ``overstatement_gap`` are reported
    alongside it so the inflation is visible.

    Args:
        a: Count of both-yes agreements.
        b: Count of rater1-yes / rater2-no disagreements.
        c: Count of rater1-no / rater2-yes disagreements.
        d: Count of both-no agreements.

    Returns:
        An :class:`AgreementReport` with raw agreement, kappa, the overstatement
        gap, and the Landis-Koch interpretation band.

    Raises:
        ValueError: If the total ``N == a + b + c + d`` is zero.
    """
    return AgreementReport(a=a, b=b, c=c, d=d)


# ---------------------------------------------------------------------------
# (4) Contamination detection (CapBencher)
# ---------------------------------------------------------------------------


@dataclass
class CapBencherResult:
    """Result of the CapBencher one-sided binomial contamination test.

    Attributes:
        n: Number of benchmark items evaluated (``n >= 0``).
        k: Number of items answered correctly (``0 <= k <= n``).
        bayes_cap: Upper bound on plausible non-contaminated accuracy
            (``0 < bayes_cap < 1``).
        alpha: Significance level for flagging (``0 < alpha < 1``, default 0.05).
        observed_acc: Computed observed accuracy ``k / n`` (0.0 when ``n == 0``).
        p_value: Computed one-sided upper-tail binomial p-value.
        flagged: Computed ``p_value < alpha`` — True suggests contamination.
    """

    n: int
    k: int
    bayes_cap: float
    alpha: float = 0.05
    observed_acc: float = field(init=False)
    p_value: float = field(init=False)
    flagged: bool = field(init=False)

    def __post_init__(self) -> None:
        """Validate inputs and compute observed accuracy, p-value, and flag."""
        if not 0.0 < self.bayes_cap < 1.0:
            raise ValueError(
                f"bayes_cap must be in (0, 1), got {self.bayes_cap}"
            )
        if not 0.0 < self.alpha < 1.0:
            raise ValueError(
                f"alpha must be in (0, 1), got {self.alpha}"
            )
        if self.n < 0:
            raise ValueError(f"n must be >= 0, got {self.n}")
        if self.n > MAX_SAMPLE_SIZE:
            raise ValueError(
                f"n={self.n} exceeds MAX_SAMPLE_SIZE={MAX_SAMPLE_SIZE}"
            )
        if not 0 <= self.k <= self.n:
            raise ValueError(
                f"k must satisfy 0 <= k <= n (n={self.n}), got {self.k}"
            )

        self.observed_acc = self.k / self.n if self.n > 0 else 0.0
        self.p_value = _one_sided_binom_pvalue(self.n, self.k, self.bayes_cap)
        self.flagged = self.p_value < self.alpha


def capbencher_binomial_test(
    n: int, k: int, bayes_cap: float, alpha: float = 0.05
) -> CapBencherResult:
    """Run the CapBencher one-sided exact binomial contamination test.

    Tests ``H0: true accuracy <= bayes_cap`` against ``H1: true accuracy >
    bayes_cap`` using the upper-tail exact binomial p-value. By Karlin-Rubin,
    the one-sided test that rejects for large ``k`` is uniformly most powerful
    (UMP) for this monotone-likelihood-ratio family. A small p-value means the
    observed number of correct answers is implausibly high under the Bayes cap,
    which suggests benchmark contamination (memorised test items).

    Args:
        n: Number of benchmark items evaluated (``n >= 0``).
        k: Number of items answered correctly (``0 <= k <= n``).
        bayes_cap: Upper bound on plausible non-contaminated accuracy
            (``0 < bayes_cap < 1``).
        alpha: Significance level for flagging (default 0.05).

    Returns:
        A :class:`CapBencherResult` with the observed accuracy, p-value, and
        the ``flagged`` verdict.

    Raises:
        ValueError: If ``bayes_cap`` is outside ``(0, 1)``, ``alpha`` is outside
            ``(0, 1)``, ``n < 0``, ``n > MAX_SAMPLE_SIZE``, or ``k`` is outside
            ``[0, n]``.
    """
    return CapBencherResult(n=n, k=k, bayes_cap=bayes_cap, alpha=alpha)


__all__ = [
    "pass_at_k",
    "pass_hat_k",
    "pass_hat_k_dataset",
    "WilsonInterval",
    "wilson_interval",
    "gate_decision",
    "cohens_kappa",
    "AgreementReport",
    "agreement_report",
    "CapBencherResult",
    "capbencher_binomial_test",
]
