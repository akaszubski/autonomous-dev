# Scientific Validation - Code Examples

Python code snippets for implementing scientific validation methodology.

---

## Power Analysis

### Calculate Required Sample Size

```python
from statsmodels.stats.power import TTestIndPower
import numpy as np

def calculate_required_n(effect_size, power=0.80, alpha=0.05):
    """
    Calculate required sample size for given effect size.

    Args:
        effect_size: Cohen's d (0.2=small, 0.5=medium, 0.8=large)
        power: Probability of detecting true effect (default 0.80)
        alpha: Significance level (default 0.05)

    Returns:
        Required n per group
    """
    analysis = TTestIndPower()
    n = analysis.solve_power(
        effect_size=effect_size,
        power=power,
        alpha=alpha,
        alternative='two-sided'
    )
    return int(np.ceil(n))

# Example: Detect 10% difference with std=20%
# Cohen's d = 0.10 / 0.20 = 0.5 (medium effect)
required_n = calculate_required_n(effect_size=0.5, power=0.80)
# Result: n = 64 per group
```

### Power Analysis for Proportions

```python
from statsmodels.stats.power import NormalIndPower
from statsmodels.stats.proportion import proportion_effectsize

def power_for_proportions(p1, p2, power=0.80, alpha=0.05):
    """
    Calculate required n for comparing two proportions.

    Args:
        p1: Expected proportion in group 1 (e.g., 0.55 for 55% win rate)
        p2: Null hypothesis proportion (e.g., 0.50 for random)
    """
    effect_size = proportion_effectsize(p1, p2)
    analysis = NormalIndPower()
    n = analysis.solve_power(
        effect_size=effect_size,
        power=power,
        alpha=alpha,
        alternative='two-sided'
    )
    return int(np.ceil(n))

# Example: Detect 55% vs 50% win rate
required_n = power_for_proportions(0.55, 0.50)
# Result: n ≈ 783
```

---

## Walk-Forward Validation

### Sliding Window Implementation

```python
def walk_forward_validate(data, model, train_window, test_window, min_folds=5):
    """
    Walk-forward validation with sliding window.

    Args:
        data: Time-indexed DataFrame
        model: Model with fit() and predict() methods
        train_window: Number of periods for training
        test_window: Number of periods for testing
        min_folds: Minimum folds required

    Returns:
        List of fold results
    """
    results = []

    for i in range(train_window, len(data) - test_window, test_window):
        # Train on past data only
        train = data[i - train_window : i]
        test = data[i : i + test_window]

        # Fit and predict
        model.fit(train)
        predictions = model.predict(test)

        # Evaluate
        fold_result = {
            'fold': len(results) + 1,
            'train_start': train.index[0],
            'train_end': train.index[-1],
            'test_start': test.index[0],
            'test_end': test.index[-1],
            'metrics': evaluate(predictions, test)
        }
        results.append(fold_result)

    if len(results) < min_folds:
        raise ValueError(f"Only {len(results)} folds, need {min_folds}")

    return results

def aggregate_results(fold_results):
    """Aggregate metrics across folds."""
    metrics = [r['metrics'] for r in fold_results]
    return {
        'mean_win_rate': np.mean([m['win_rate'] for m in metrics]),
        'std_win_rate': np.std([m['win_rate'] for m in metrics]),
        'folds_significant': sum(1 for m in metrics if m['p_value'] < 0.05),
        'total_folds': len(metrics)
    }
```

### Expanding Window Variant

```python
def walk_forward_expanding(data, model, initial_train, test_window):
    """Expanding window - uses all available history."""
    results = []

    for i in range(initial_train, len(data) - test_window, test_window):
        # Train on ALL past data (expanding)
        train = data[0 : i]
        test = data[i : i + test_window]

        model.fit(train)
        predictions = model.predict(test)

        results.append({
            'fold': len(results) + 1,
            'train_size': len(train),
            'metrics': evaluate(predictions, test)
        })

    return results
```

---

## Sensitivity Analysis

### One-Factor-At-a-Time (OFAT)

```python
def sensitivity_analysis(base_params, param_ranges, evaluate_func):
    """
    Test sensitivity to ±20% parameter variation.

    Args:
        base_params: Dict of baseline parameter values
        param_ranges: Dict of parameters to test (keys must be in base_params)
        evaluate_func: Function that takes params and returns metrics dict

    Returns:
        Dict with base result and sensitivity analysis
    """
    results = {'base': evaluate_func(base_params)}

    for param in param_ranges:
        base_value = base_params[param]

        # Test -20%
        test_params = base_params.copy()
        test_params[param] = base_value * 0.8
        results[f'{param}_0.8'] = evaluate_func(test_params)

        # Test +20%
        test_params = base_params.copy()
        test_params[param] = base_value * 1.2
        results[f'{param}_1.2'] = evaluate_func(test_params)

    return analyze_stability(results)

def analyze_stability(results):
    """Check if all variations maintain positive result."""
    base_positive = results['base']['win_rate'] > 0.5

    sign_flips = sum(
        1 for key, r in results.items()
        if key != 'base' and (r['win_rate'] > 0.5) != base_positive
    )

    win_rates = [r['win_rate'] for r in results.values()]

    return {
        'stable': sign_flips == 0,
        'sign_flips': sign_flips,
        'min_win_rate': min(win_rates),
        'max_win_rate': max(win_rates),
        'variance': np.var(win_rates),
        'classification': (
            'STABLE' if sign_flips == 0 else
            'CONDITIONAL' if sign_flips <= 2 else
            'FRAGILE'
        ),
        'all_results': results
    }
```

### Global Sensitivity (Sobol Indices)

```python
from SALib.sample import saltelli
from SALib.analyze import sobol

def global_sensitivity_analysis(model_func, problem_def, n_samples=1024):
    """
    Sobol variance-based sensitivity analysis for complex models.

    Args:
        model_func: Function that takes parameter array, returns scalar
        problem_def: SALib problem definition dict
        n_samples: Base sample count (actual samples = n_samples * (2D + 2))
    """
    # Generate parameter combinations
    param_values = saltelli.sample(problem_def, n_samples)

    # Evaluate model for all combinations
    Y = np.array([model_func(params) for params in param_values])

    # Analyze sensitivity
    Si = sobol.analyze(problem_def, Y)

    return {
        'first_order': dict(zip(problem_def['names'], Si['S1'])),
        'total_order': dict(zip(problem_def['names'], Si['ST'])),
        'most_sensitive': problem_def['names'][np.argmax(Si['ST'])]
    }

# Example problem definition
problem = {
    'num_vars': 3,
    'names': ['lookback', 'threshold', 'holding_period'],
    'bounds': [[10, 30], [0.03, 0.07], [3, 7]]
}
```

---

## Statistical Tests

### Significance Tests

```python
from scipy.stats import binomtest, ttest_ind

def test_win_rate(wins, total, null_rate=0.5):
    """Test if win rate significantly exceeds null hypothesis."""
    result = binomtest(wins, total, null_rate, alternative='greater')
    return {
        'win_rate': wins / total,
        'p_value': result.pvalue,
        'significant': result.pvalue < 0.05,
        'ci_95': result.proportion_ci(confidence_level=0.95)
    }

def test_two_groups(group_a, group_b):
    """Compare means of two groups."""
    t_stat, p_value = ttest_ind(group_a, group_b)
    return {
        't_statistic': t_stat,
        'p_value': p_value,
        'mean_a': np.mean(group_a),
        'mean_b': np.mean(group_b),
        'significant': p_value < 0.05
    }
```

### Bootstrap Confidence Intervals

```python
def bootstrap_ci(data, metric_func=np.mean, n_iter=1000, ci=0.95):
    """
    Calculate bootstrap confidence interval.

    Args:
        data: Array of observations
        metric_func: Function to compute metric (default: mean)
        n_iter: Number of bootstrap iterations
        ci: Confidence level (default: 0.95)
    """
    samples = [
        metric_func(np.random.choice(data, len(data), replace=True))
        for _ in range(n_iter)
    ]

    lower = np.percentile(samples, (1-ci)/2 * 100)
    upper = np.percentile(samples, (1+ci)/2 * 100)

    return {
        'mean': np.mean(samples),
        'ci_low': lower,
        'ci_high': upper,
        'std': np.std(samples)
    }
```

### Multiple Comparison Correction

```python
def bonferroni_correction(p_values, alpha=0.05):
    """
    Apply Bonferroni correction for multiple comparisons.

    Args:
        p_values: List of raw p-values
        alpha: Family-wise error rate (default 0.05)

    Returns:
        Dict with corrected threshold and which tests pass
    """
    k = len(p_values)
    corrected_alpha = alpha / k

    return {
        'corrected_alpha': corrected_alpha,
        'significant': [p < corrected_alpha for p in p_values],
        'num_significant': sum(p < corrected_alpha for p in p_values),
        'original_p_values': p_values
    }
```

---

## Bayesian Analysis

### Bayes Factor for Proportions

```python
import pymc as pm
import numpy as np
from scipy.stats import gaussian_kde

def calculate_bayes_factor(wins, n, null_p=0.5):
    """
    Calculate Bayes Factor for win rate vs null hypothesis.

    Args:
        wins: Number of successes
        n: Total trials
        null_p: Null hypothesis probability (default 0.5)

    Returns:
        Bayes Factor (BF10) - evidence for alternative vs null
    """
    with pm.Model() as model:
        # Uniform prior
        p = pm.Beta('p', alpha=1, beta=1)

        # Likelihood
        obs = pm.Binomial('obs', n=n, p=p, observed=wins)

        # Sample posterior
        trace = pm.sample(2000, return_inferencedata=True, progressbar=False)

    # Savage-Dickey ratio
    posterior_samples = trace.posterior['p'].values.flatten()
    kde = gaussian_kde(posterior_samples)

    prior_density_at_null = 1.0  # Beta(1,1) is uniform
    posterior_density_at_null = kde(null_p)[0]

    bf_01 = posterior_density_at_null / prior_density_at_null
    bf_10 = 1 / bf_01

    return {
        'bf_10': bf_10,
        'interpretation': interpret_bayes_factor(bf_10),
        'posterior_mean': np.mean(posterior_samples),
        'posterior_std': np.std(posterior_samples)
    }

def interpret_bayes_factor(bf):
    """Interpret Bayes Factor using Jeffreys scale."""
    if bf < 1: return 'Supports null'
    if bf < 3: return 'Anecdotal'
    if bf < 10: return 'Moderate'
    if bf < 30: return 'Strong'
    if bf < 100: return 'Very strong'
    return 'Decisive'
```

### Bayesian A/B Test

```python
def bayesian_ab_test(wins_a, n_a, wins_b, n_b):
    """
    Bayesian comparison of two proportions.

    Returns:
        Probability that A > B and credible interval for difference
    """
    with pm.Model() as model:
        p_a = pm.Beta('p_a', alpha=1, beta=1)
        p_b = pm.Beta('p_b', alpha=1, beta=1)

        obs_a = pm.Binomial('obs_a', n=n_a, p=p_a, observed=wins_a)
        obs_b = pm.Binomial('obs_b', n=n_b, p=p_b, observed=wins_b)

        diff = pm.Deterministic('diff', p_a - p_b)

        trace = pm.sample(2000, return_inferencedata=True, progressbar=False)

    prob_a_better = float((trace.posterior['p_a'] > trace.posterior['p_b']).mean())
    diff_samples = trace.posterior['diff'].values.flatten()

    return {
        'prob_a_better': prob_a_better,
        'mean_diff': float(np.mean(diff_samples)),
        'ci_95': [float(np.percentile(diff_samples, 2.5)),
                  float(np.percentile(diff_samples, 97.5))]
    }
```

---

## Effect Thresholds

### Trading/Finance

| Metric | Minimum | Strong | Exceptional |
|--------|---------|--------|-------------|
| Sharpe Ratio | > 0.5 | > 1.0 | > 2.0 |
| Win Rate | > 55% | > 60% | > 70% |
| Profit Factor | > 1.2 | > 1.5 | > 2.0 |
| Information Ratio | > 0.3 | > 0.5 | > 1.0 |
| Max Drawdown | < 25% | < 15% | < 10% |

### Psychology/Behavioral

| Metric | Small | Medium | Large |
|--------|-------|--------|-------|
| Cohen's d | 0.2 | 0.5 | 0.8 |
| Correlation r | 0.1 | 0.3 | 0.5 |
| Odds Ratio | 1.5 | 2.5 | 4.0 |

### Classification Logic

```python
def classify_effect(metric_name, value, domain='trading'):
    """Classify effect size against domain thresholds."""
    thresholds = {
        'trading': {
            'sharpe': {'min': 0.5, 'strong': 1.0, 'exceptional': 2.0},
            'win_rate': {'min': 0.55, 'strong': 0.60, 'exceptional': 0.70},
            'profit_factor': {'min': 1.2, 'strong': 1.5, 'exceptional': 2.0}
        },
        'behavioral': {
            'cohens_d': {'min': 0.2, 'strong': 0.5, 'exceptional': 0.8},
            'correlation': {'min': 0.1, 'strong': 0.3, 'exceptional': 0.5}
        }
    }

    t = thresholds[domain][metric_name]

    if value >= t['exceptional']: return 'EXCEPTIONAL'
    if value >= t['strong']: return 'STRONG'
    if value >= t['min']: return 'MEANINGFUL'
    return 'BELOW_THRESHOLD'
```

---

## Bias Detection

### Look-Ahead Bias Audit

```python
class LookaheadAuditor:
    """Compare batch vs streaming detection."""

    def audit(self, data, validator):
        # Batch: process all data at once
        batch_results = validator.detect(data)

        # Streaming: process bar-by-bar
        streaming_results = []
        for i in range(len(data)):
            partial = data[:i+1]
            detections = validator.detect(partial)
            # Only count NEW detections at this bar
            streaming_results.extend([
                d for d in detections
                if d.detection_time == data.index[i]
            ])

        # Compare
        batch_set = set((d.time, d.signal) for d in batch_results)
        stream_set = set((d.time, d.signal) for d in streaming_results)

        discrepancies = batch_set - stream_set

        return {
            'has_bias': len(discrepancies) > 0,
            'discrepancy_count': len(discrepancies),
            'bias_percentage': len(discrepancies) / len(batch_results) * 100,
            'discrepancies': list(discrepancies)
        }
```

### Survivorship Tracker

```python
from dataclasses import dataclass
from datetime import datetime

@dataclass
class AttemptMetrics:
    attempted: int
    completed: int
    failed: int
    completion_rate: float
    failure_reasons: dict

class SurvivorshipTracker:
    """Track all attempts, not just successes."""

    def __init__(self):
        self.attempts = []

    def track_attempt(self, pattern_id: str, status: str, reason: str = None):
        self.attempts.append({
            'id': pattern_id,
            'status': status,  # 'initiated', 'completed', 'failed'
            'reason': reason,
            'timestamp': datetime.now()
        })

    def get_metrics(self) -> AttemptMetrics:
        attempted = len([a for a in self.attempts if a['status'] == 'initiated'])
        completed = len([a for a in self.attempts if a['status'] == 'completed'])
        failed = len([a for a in self.attempts if a['status'] == 'failed'])

        reasons = {}
        for a in self.attempts:
            if a['status'] == 'failed' and a['reason']:
                reasons[a['reason']] = reasons.get(a['reason'], 0) + 1

        return AttemptMetrics(
            attempted=attempted,
            completed=completed,
            failed=failed,
            completion_rate=completed / attempted if attempted > 0 else 0,
            failure_reasons=reasons
        )
```
