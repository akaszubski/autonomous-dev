---
name: scientific-validation
version: 2.0.0
type: knowledge
description: Scientific method for validating claims from books, papers, or theories. Enforces pre-registration, power analysis, statistical rigor, Bayesian methods, sensitivity analysis, bias prevention, and evidence-based acceptance/rejection. Use when testing any testable hypothesis.
keywords: scientific method, hypothesis, validation, experiment, p-value, sample size, bias, out-of-sample, backtest, evidence, claims, books, research, power analysis, Bayesian, sensitivity analysis, walk-forward
auto_activate: true
allowed-tools: [Read, Grep, Glob, Bash, Write]
---

# Scientific Validation Skill

Rigorous methodology for validating claims from any source - books, papers, theories, or intuition. Domain-agnostic framework that enforces scientific standards.

## When This Skill Activates

- Testing claims from books, papers, or expert sources
- Validating rules, strategies, or hypotheses
- Running experiments or backtests
- Evaluating detection algorithms
- Keywords: "validate", "test hypothesis", "experiment", "backtest", "prove", "evidence", "claims"

---

## Core Principle: Data is the Arbiter

**The source does not matter. Only evidence matters.**

- Expert books can be wrong
- Intuitive theories can fail
- Popular wisdom can be noise
- Only empirical validation decides what works

---

## Phase 0: Claim Verification (CRITICAL)

**BEFORE extracting claims, verify you understand what the source ACTUALLY claims.**

### 0.1 Common Misinterpretation Patterns

| Source Says | Researcher Misinterprets As | Correct Interpretation |
|------------|---------------------------|----------------------|
| "Method A provides uncertainty quantification" | "Method A beats Method B" | Test calibration, not performance |
| "Method A enables intractable computations" | "Method A produces better results" | Test correctness, not superiority |
| "Method A incorporates prior knowledge" | "Method A prevents overfitting" | Test knowledge incorporation, not generalization |

### 0.2 Claim Type Classification

| Type | Definition | Testable? | Example |
|------|-----------|-----------|---------|
| **PERFORMANCE** | "A beats B on metric X" | YES - direct comparison | "SV has lower MSE than GARCH" |
| **METHODOLOGICAL** | "A enables capability X" | YES - verify capability | "MCMC samples from posterior" |
| **PHILOSOPHICAL** | "X is important because Y" | MAYBE - derived predictions | "Survivorship bias exists" |
| **BEHAVIORAL** | "Humans do X in situation Y" | HARD - needs experiments | "Traders increase size after wins" |

**Rule:** Only test PERFORMANCE claims directly. For other types, test derived predictions and note the gap.

---

## Phase 1: Claims Extraction

**BEFORE touching any data:**

### 1.1 Document the Source
```markdown
# Claims Registry: [Source Name]

**Source:** [Book/Paper/Theory Title]
**Author:** [Name]
**Year:** [Publication Year]
**Domain:** [Trading/Medicine/Psychology/etc.]
**Extraction Date:** [Today]
```

### 1.2 Extract Testable Claims

For each claim:
```markdown
## CLAIM-001: [Short Name]

**Source Location:** Chapter X, Page Y (or URL, timestamp)
**Verbatim Quote:** "[Exact quote from source]"
**Claim Type:** PERFORMANCE / METHODOLOGICAL / PHILOSOPHICAL / BEHAVIORAL
**Paraphrase:** [Your interpretation]
**What Source ACTUALLY Claims:** [Careful reading - not your interpretation]
**Our Derived Prediction:** [What we will test - may differ from source claim]
**Gap Analysis:** [How derived prediction differs from source claim]
**Detection Method:** [How to identify in data]
**Success Metric:** [What counts as "working"]
**Priority:** HIGH/MEDIUM/LOW
**Falsifiable:** YES/NO (reject if NO)
```

### 1.3 Claim Verification Checklist
- [ ] Verbatim quote extracted with page number
- [ ] Quote explicitly supports the claim (not my interpretation)
- [ ] Claim type correctly classified
- [ ] If testing derived prediction, gap documented

### 1.4 Prioritize by Testability

| Priority | Criteria |
|----------|----------|
| HIGH | Clear prediction, easy to detect, sufficient data available |
| MEDIUM | Clear prediction, detection possible but complex |
| LOW | Vague prediction OR detection difficult OR limited data |
| REJECT | Not falsifiable - cannot be tested |

---

## Phase 1.5: Publication Bias Prevention

**BEFORE selecting claims to test, prevent cherry-picking bias.**

### 1.5.1 Document ALL Claims First

```markdown
## Complete Claims Inventory

**Total claims identified:** X
**Claims selected for testing:** Y
**Selection ratio:** Y/X = Z%
**Selection method:** [Random / Highest priority / All HIGH priority]
```

### 1.5.2 Selection Bias Correction

| Selection Ratio | Correction Required |
|-----------------|---------------------|
| > 80% | None - testing most claims |
| 50-80% | Report selection criteria |
| < 50% | Apply p-value adjustment |

**Adjustment formula:**
```python
# If testing < 50% of identified claims
adjusted_p = raw_p * (total_claims / tested_claims)
```

### 1.5.3 Mandatory Reporting

- [ ] ALL identified claims listed (not just tested ones)
- [ ] Selection criteria documented BEFORE testing
- [ ] Untested claims have documented reason (LOW priority, not falsifiable, etc.)

**Red Flag:** Testing only claims that "look promising" = selection bias.

---

## Phase 2: Pre-Registration

**CRITICAL: Document hypothesis BEFORE seeing any results.**

### 2.1 Create Experiment Entry

```markdown
## EXP-XXX: [Claim Name]

**Created:** [Date]
**Status:** PRE-REGISTERED

### Hypothesis
[Copy from claims registry - what you expect to find]

### Prediction (Specific)
- Direction: [UP/DOWN/POSITIVE/NEGATIVE]
- Magnitude: [Expected effect size]
- Timeframe: [When effect should appear]

### Success Criteria (Defined Before Testing)
- Minimum sample size: n >= [30]
- Significance threshold: p < [0.05]
- Effect size threshold: [metric] > [value]
- Practical significance: [real-world threshold]

### Dataset
- Training period: [dates/range]
- Testing period: [dates/range] (HELD OUT)
- Source: [where data comes from]

### Costs/Constraints
[Domain-specific: transaction costs for trading, time costs for processes, etc.]
```

### 2.2 Pre-Registration Rules

1. **No peeking** - Do not look at test data before finalizing hypothesis
2. **Specific predictions** - "It works" is not a hypothesis
3. **Define failure** - Know what "doesn't work" looks like
4. **Lock parameters** - Set all thresholds before testing

---

## Phase 2.3: Power Analysis (MANDATORY)

**BEFORE running experiment, calculate required sample size.**

### 2.3.1 Why Power Analysis Matters

- n >= 30 is a **minimum**, not always sufficient
- Small effects require LARGER samples
- Underpowered studies waste resources and miss true effects
- 80% power = 20% chance of missing a real effect

### 2.3.2 Effect Size Standards (Cohen's d)

| Effect Size | Cohen's d | Typical n (80% power) | Typical n (90% power) |
|-------------|-----------|----------------------|----------------------|
| Very Small | 0.1 | 1,571 | 2,103 |
| Small | 0.2 | 394 | 527 |
| Medium | 0.5 | 64 | 86 |
| Large | 0.8 | 26 | 34 |
| Very Large | 1.2 | 12 | 16 |

### 2.3.3 Power Calculation

```python
from statsmodels.stats.power import TTestIndPower

def calculate_required_n(effect_size, power=0.80, alpha=0.05):
    """Calculate required sample size for given effect size."""
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

### 2.3.4 Power Analysis Checklist

- [ ] Expected effect size estimated (from pilot or literature)
- [ ] Required n calculated for 80% power minimum
- [ ] If available n < required n, document as UNDERPOWERED
- [ ] Consider 90% power for critical claims

### 2.3.5 Underpowered Study Gate

| Available n vs Required n | Action |
|---------------------------|--------|
| Available >= Required | Proceed normally |
| Available = 50-99% of Required | Proceed with CONDITIONAL max |
| Available < 50% of Required | BLOCK - need more data |

**Rule:** An underpowered study cannot achieve VALIDATED status.

---

## Phase 3: Bias Prevention Infrastructure

Build safeguards BEFORE running experiments:

### 3.1 Look-Ahead Bias
**Problem:** Using future information to make past decisions

**Prevention:**
- Process data sequentially (bar-by-bar, record-by-record)
- Compare batch vs streaming results
- Flag any discrepancies

```
Audit: Does detection at time T use only data available at time T?
```

### 3.2 Survivorship Bias
**Problem:** Only counting successes, ignoring failures

**Prevention:**
- Track ALL attempts, not just completions
- Report: attempted / completed ratio
- Include failure reasons in analysis

```
Metric: completion_rate = completed / attempted
Expected: Low completion rates (5-20%) with strict validation
```

### 3.3 Selection Bias
**Problem:** Cherry-picking favorable results

**Prevention:**
- Report ALL experiments (including failures)
- No post-hoc exclusions without documented justification
- Publish negative results

### 3.4 Data Snooping
**Problem:** Tuning parameters on test data

**Prevention:**
- Strict train/test split (typically 70/30 or 80/20)
- Parameters set on training data ONLY
- If you peek at test results and adjust, you need NEW test data

---

## Phase 3.5: Walk-Forward Validation (MANDATORY for Time Series)

**Standard train/test split leaks regime information. Use walk-forward instead.**

### 3.5.1 Why Walk-Forward is Required

| Problem with Standard Split | Walk-Forward Solution |
|----------------------------|----------------------|
| Uses "future to predict past" | Maintains temporal order |
| Single train-test boundary | Multiple rolling windows |
| Ignores regime changes | Adapts to evolving patterns |
| Overstates performance | Realistic deployment estimate |

### 3.5.2 Window Strategies

**Sliding Window (Recommended for trading):**
```python
def walk_forward_validate(data, model, train_window, test_window):
    """Walk-forward validation with sliding window."""
    results = []

    for i in range(train_window, len(data) - test_window, test_window):
        # Train on past data only
        train = data[i - train_window : i]
        test = data[i : i + test_window]

        # Fit and predict
        model.fit(train)
        predictions = model.predict(test)

        # Evaluate
        fold_result = evaluate(predictions, test)
        fold_result['fold_start'] = data.index[i]
        results.append(fold_result)

    return aggregate_results(results)
```

**Expanding Window:**
```python
# Use all available history (grows over time)
train = data[0 : i]  # Instead of fixed window
```

### 3.5.3 Recommended Parameters

| Domain | Train Window | Test Window | Min Folds |
|--------|--------------|-------------|-----------|
| Trading (daily) | 2-5 years | 6-12 months | 5 |
| Trading (intraday) | 3-6 months | 1-2 months | 6 |
| Macro signals | 5-10 years | 1-2 years | 4 |

### 3.5.4 Walk-Forward Checklist

- [ ] Temporal ordering preserved (no future data in training)
- [ ] Multiple folds evaluated (not just one split)
- [ ] Fold-to-fold variance reported
- [ ] Parameters re-optimized per fold (if applicable)

### 3.5.5 Walk-Forward Gate

**For time series experiments:**
- Standard K-fold CV → INVALID (temporal leakage)
- Single train/test split → CONDITIONAL at best
- Walk-forward validation → Can achieve VALIDATED

---

## Phase 4: Statistical Requirements

### 4.1 Minimum Standards

| Metric | Threshold | Rationale |
|--------|-----------|-----------|
| Sample size | n >= 30 (50+ preferred) | Central limit theorem |
| p-value | < 0.05 (see 4.5 for multiple testing) | 95% confidence |
| Effect size | > practical threshold | Real-world significance |
| Replication | 2+ independent tests | Not just chance |

### 4.2 Multiple Comparison Correction (MANDATORY for >1 claim)

**Problem:** Testing K claims at alpha=0.05 inflates false positive rate.

**Bonferroni Correction:**
```python
# For K simultaneous tests
alpha_corrected = 0.05 / K

# Example: 12 claims
# Threshold = 0.05 / 12 = 0.0042
```

| Claims | Corrected Threshold | Family-wise Error Rate |
|--------|---------------------|------------------------|
| 1 | 0.050 | 5% |
| 5 | 0.010 | 5% |
| 10 | 0.005 | 5% |
| 12 | 0.0042 | 5% |
| 20 | 0.0025 | 5% |

**Rule:** Always report BOTH raw p-value AND Bonferroni-corrected significance.

### 4.3 False Discovery Rate (FDR) Control

**Harvey et al. (2016) Standard:**
Academic finance research now requires:
- **t-ratio > 3.0** (not 1.96) for new trading strategy claims
- This adjusts for the "multiple testing" implicit in decades of backtesting
- A t-ratio of 2.0 corresponds to ~50% false discovery rate

**When to Apply:**
| Context | t-ratio Threshold | Rationale |
|---------|-------------------|-----------|
| Novel trading claim | 3.0 | Harvey et al. standard |
| Replication of known effect | 2.0 | Already established |
| Methodological validation | 1.96 | Not a performance claim |
| Exploratory analysis | N/A | Not claiming significance |

### 4.4 Required Calculations

```python
# Significance test (adapt to your domain)
from scipy.stats import binomtest, ttest_ind

# For binary outcomes (win/loss, success/fail)
result = binomtest(successes, total, expected_rate, alternative='greater')
p_value = result.pvalue

# For continuous outcomes
t_stat, p_value = ttest_ind(treatment_group, control_group)
```

### 4.5 Confidence Intervals

```python
# Bootstrap method (1000 iterations)
import numpy as np

def bootstrap_ci(data, metric_func, n_iter=1000, ci=0.95):
    samples = [metric_func(np.random.choice(data, len(data), replace=True))
               for _ in range(n_iter)]
    lower = np.percentile(samples, (1-ci)/2 * 100)
    upper = np.percentile(samples, (1+ci)/2 * 100)
    return {'mean': np.mean(samples), 'ci_low': lower, 'ci_high': upper}
```

### 4.6 Effect Size (Not Just Significance)

Statistical significance != practical significance

- A p-value of 0.001 with tiny effect is not useful
- Define minimum meaningful effect BEFORE testing
- Report effect size alongside p-value

### 4.6.1 Domain-Specific Effect Thresholds

**Trading/Finance:**

| Metric | Minimum Meaningful | Strong | Exceptional |
|--------|-------------------|--------|-------------|
| Sharpe Ratio | > 0.5 | > 1.0 | > 2.0 |
| Win Rate | > 55% | > 60% | > 70% |
| Profit Factor | > 1.2 | > 1.5 | > 2.0 |
| Information Ratio | > 0.3 | > 0.5 | > 1.0 |
| Max Drawdown | < 25% | < 15% | < 10% |

**Psychology/Behavioral:**

| Metric | Small | Medium | Large |
|--------|-------|--------|-------|
| Cohen's d | 0.2 | 0.5 | 0.8 |
| Correlation r | 0.1 | 0.3 | 0.5 |
| Odds Ratio | 1.5 | 2.5 | 4.0 |

**Classification Gate:**
```
Statistical significance + Effect below "Minimum Meaningful" = REJECTED
Statistical significance + Effect above "Strong" = VALIDATED candidate
```

---

### 4.7 Bayesian Complement (For Small Samples or Ambiguous Results)

**When frequentist p-values are insufficient:**

### 4.7.1 When to Use Bayesian Methods

| Scenario | Use Bayesian? |
|----------|---------------|
| n < 30 | YES - frequentist underpowered |
| p-value near 0.05 (0.03-0.07) | YES - quantify uncertainty |
| Want probability OF hypothesis (not just against null) | YES |
| Incorporating prior knowledge | YES |
| Large sample, clear result | OPTIONAL - frequentist sufficient |

### 4.7.2 Bayes Factor Interpretation (Jeffreys Scale)

| Bayes Factor | Evidence Strength | Interpretation |
|--------------|-------------------|----------------|
| < 1 | Supports null | Evidence AGAINST hypothesis |
| 1-3 | Weak/Anecdotal | Barely worth mentioning |
| 3-10 | Moderate | Substantial evidence |
| 10-30 | Strong | Strong evidence |
| 30-100 | Very Strong | Very strong evidence |
| > 100 | Decisive | Decisive evidence |

### 4.7.3 Bayesian A/B Test Example

```python
import pymc as pm
import numpy as np

def bayesian_ab_test(wins_a, n_a, wins_b, n_b):
    """Bayesian comparison of two proportions."""
    with pm.Model() as model:
        # Uninformative priors
        p_a = pm.Beta('p_a', alpha=1, beta=1)
        p_b = pm.Beta('p_b', alpha=1, beta=1)

        # Likelihoods
        obs_a = pm.Binomial('obs_a', n=n_a, p=p_a, observed=wins_a)
        obs_b = pm.Binomial('obs_b', n=n_b, p=p_b, observed=wins_b)

        # Difference
        diff = pm.Deterministic('diff', p_a - p_b)

        # Sample posterior
        trace = pm.sample(2000, return_inferencedata=True)

    # P(A > B)
    prob_a_better = (trace.posterior['p_a'] > trace.posterior['p_b']).mean()

    return {
        'prob_a_better': float(prob_a_better.values),
        'mean_diff': float(trace.posterior['diff'].mean().values),
        'ci_95': [
            float(np.percentile(trace.posterior['diff'], 2.5)),
            float(np.percentile(trace.posterior['diff'], 97.5))
        ]
    }
```

### 4.7.4 Bayesian Classification Gate

| P(Hypothesis) | Bayes Factor | Classification Allowed |
|---------------|--------------|------------------------|
| > 95% | > 30 | VALIDATED candidate |
| 90-95% | 10-30 | CONDITIONAL |
| 75-90% | 3-10 | Needs more data |
| < 75% | < 3 | REJECTED or INSUFFICIENT |

---

## Phase 5: Multi-Source Validation

**Edge should generalize across contexts:**

### 5.1 Expansion Requirements

- Test on minimum 3 different datasets/contexts
- Test across different time periods
- Include different conditions (if applicable)

### 5.2 Consistency Check

If claim only works in ONE context -> likely overfitting

```
Good: Works across 5/6 datasets
Bad: Works on 1 dataset, fails on 5
```

---

## Phase 5.3: Sensitivity Analysis (MANDATORY for VALIDATED)

**BEFORE classifying as VALIDATED, verify results are robust to parameter changes.**

### 5.3.1 Why Sensitivity Analysis Matters

- Results may be fragile to small parameter changes
- Overfitted models break with ±10% variation
- Robust results survive reasonable perturbations

### 5.3.2 One-Factor-At-a-Time (OFAT) Method

```python
def sensitivity_analysis(base_params, param_ranges, evaluate_func):
    """Test sensitivity to ±20% parameter variation."""
    results = {'base': evaluate_func(base_params)}

    for param, base_value in base_params.items():
        if param not in param_ranges:
            continue

        # Test low and high variations
        for multiplier in [0.8, 1.2]:  # ±20%
            test_params = base_params.copy()
            test_params[param] = base_value * multiplier

            key = f'{param}_{multiplier}'
            results[key] = evaluate_func(test_params)

    return analyze_stability(results)

def analyze_stability(results):
    """Check if all variations maintain positive result."""
    base_positive = results['base']['win_rate'] > 0.5

    all_positive = all(
        r['win_rate'] > 0.5
        for key, r in results.items()
        if key != 'base'
    )

    variance = np.var([r['win_rate'] for r in results.values()])

    return {
        'stable': base_positive and all_positive,
        'variance': variance,
        'sign_flips': sum(1 for k, r in results.items()
                         if k != 'base' and (r['win_rate'] > 0.5) != base_positive),
        'all_results': results
    }
```

### 5.3.3 Stability Requirements

| Stability Check | Result | Classification Impact |
|-----------------|--------|----------------------|
| All variations positive | PASS | Can achieve VALIDATED |
| 1-2 sign flips | WARN | CONDITIONAL at best |
| 3+ sign flips | FAIL | REJECTED (fragile) |
| Variance > 0.05 | WARN | Document instability |

### 5.3.4 Global Sensitivity Analysis (For Complex Models)

For models with many parameters, use Sobol indices:

```python
from SALib.sample import saltelli
from SALib.analyze import sobol

def global_sensitivity_analysis(model, problem_def, n_samples=1024):
    """Sobol variance-based sensitivity analysis."""
    # Generate parameter combinations
    param_values = saltelli.sample(problem_def, n_samples)

    # Evaluate model for all combinations
    Y = np.array([model.evaluate(params) for params in param_values])

    # Analyze sensitivity
    Si = sobol.analyze(problem_def, Y)

    return {
        'first_order': Si['S1'],      # Main effects
        'total_order': Si['ST'],       # Total effects (including interactions)
        'second_order': Si['S2']       # Pairwise interactions
    }
```

### 5.3.5 Sensitivity Analysis Checklist

- [ ] Key parameters identified for testing
- [ ] ±20% variation tested (or domain-appropriate range)
- [ ] Result sign stability verified
- [ ] High-sensitivity parameters documented
- [ ] Robustness conclusion stated

---

## Phase 5.5: Adversarial Self-Critique (MANDATORY)

**BEFORE classifying ANY experiment, invoke the experiment-critic agent.**

### 5.5.1 Invoke Critic Agent

```
Use Task tool:
  subagent_type: "experiment-critic"
  prompt: "Review experiment EXP-XXX for data adequacy, methodology, and circular validation"
```

The agent will check:
1. **Data Adequacy** - Is data sufficient, diverse, independent?
2. **Methodology** - Are assumptions valid? Costs included?
3. **Circular Validation** - Is the claim used to generate validation data?
4. **Alternative Explanations** - What else could explain results?

### 5.5.2 Classification Gate

| Critic Verdict | Allowed Classifications |
|----------------|------------------------|
| **PROCEED** | VALIDATED, CONDITIONAL, REJECTED |
| **REVISE** | Cannot classify - must fix methodology |
| **INVALID** | Experiment must be re-run |
| **UNTESTABLE** | Mark as UNTESTABLE (data unavailable) |

### 5.5.3 Blocking Issues (Automatic INVALID)

- **Circular validation detected**: Using claim as input to validate claim
- **Trading experiment without costs**: All trading experiments need costs
- **Simulated data from claim**: E.g., simulating "dead funds" to test survivorship

### 5.5.4 New Classification: UNTESTABLE

Add this to classification options:
```
UNTESTABLE: Required data is unavailable or cannot be obtained
            This is a VALID outcome - honest about limitations
```

---

## Phase 6: Classification

**REQUIRES:** Phase 5.5 (Adversarial Review) completed first.

After out-of-sample validation:

| Status | Criteria | Action |
|--------|----------|--------|
| **VALIDATED** | OOS meets all pre-registered success criteria + critic PROCEED | Use in production |
| **CONDITIONAL** | OOS meets relaxed criteria (p < 0.10, n >= 15) + critic PROCEED | Use with caution |
| **REJECTED** | OOS fails criteria OR negative effect | DO NOT USE |
| **INSUFFICIENT** | n < 15 in OOS | Need more data |
| **UNTESTABLE** | Required data unavailable (critic verdict) | Cannot validate - need data |
| **INVALID** | Circular validation OR methodology flaw (critic verdict) | Re-run with corrected methodology |

---

## Phase 7: Documentation

### 7.1 Experiment Log Entry

```markdown
## EXP-XXX: [Name] - COMPLETE

**Date Completed:** [Date]
**Status:** VALIDATED / REJECTED / INSUFFICIENT

### Pre-Registered Hypothesis
[What you predicted BEFORE testing]

### Methodology
- Dataset: [description]
- Train period: [dates]
- Test period: [dates]
- Parameters: [all settings]

### Results

| Metric | Training | Out-of-Sample |
|--------|----------|---------------|
| Sample Size | n=X | n=Y |
| Success Rate | X% | Y% |
| p-value | X.XXXX | Y.YYYY |
| Effect Size | X | Y |
| 95% CI | [low, high] | [low, high] |

### Verdict
[VALIDATED / REJECTED / INSUFFICIENT]

### Key Learnings
- [What worked]
- [What didn't]
- [Surprises]
- [Limitations]

### If Rejected: Why the Source Was Wrong
[Document specifically why the claim failed]
```

### 7.2 Registry Update

Maintain a summary table of ALL experiments:

```markdown
| ID | Claim | Source | OOS Result | p-value | Verdict |
|----|-------|--------|------------|---------|---------|
| EXP-001 | [Name] | [Book] | X% (n=Y) | 0.XXX | VALIDATED |
| EXP-002 | [Name] | [Book] | X% (n=Y) | 0.XXX | REJECTED |
```

---

## Phase 7.3: Structured Negative Results (MANDATORY for REJECTED)

**Negative results are valuable. Document them systematically.**

### 7.3.1 Negative Result Template

```markdown
## NEGATIVE RESULT: EXP-XXX - [Claim Name]

**Date:** [Date]
**Source:** [Book/Paper]
**Verdict:** REJECTED

### What We Expected
[The hypothesis and why it seemed plausible based on source]

### What We Found
| Metric | Expected | Actual |
|--------|----------|--------|
| Win Rate | > 60% | 48% |
| p-value | < 0.05 | 0.73 |
| Effect Size | > 0.5 | 0.08 |

### Why It Failed

**Failure Classification:**
- [ ] **SOURCE ERROR** - Claim was wrong (data contradicts source)
- [ ] **IMPLEMENTATION ERROR** - Our detection/methodology was flawed
- [ ] **DATA QUALITY** - Data was insufficient or biased
- [ ] **CONTEXT MISMATCH** - Works elsewhere, not in our context
- [ ] **OVERFITTING** - Source overfit to their dataset

**Evidence for Classification:**
[Explain why you chose this classification]

### Did Source Acknowledge This Limitation?
- [ ] YES - Source mentioned caveats we confirmed
- [ ] NO - Source overstated reliability
- [ ] PARTIAL - Source mentioned but downplayed

### Implications
- **What this tells us:** [Learnings]
- **What to avoid:** [Don't do this]
- **What to try next:** [Alternative approaches]

### Value of This Negative Result
[Why documenting this failure helps future research]
```

### 7.3.2 Negative Result Registry

Maintain separate registry of negative results:

```markdown
# Negative Results Registry

| ID | Source | Claim | Why Failed | Value |
|----|--------|-------|------------|-------|
| EXP-005 | Book A | Pattern X | SOURCE ERROR | Disproved claim |
| EXP-012 | Paper B | Method Y | CONTEXT MISMATCH | Works in equities only |
```

### 7.3.3 Publication of Negative Results

**Requirements:**
- All REJECTED experiments get structured documentation
- Negative results included in final research summary
- Source credibility updated based on rejection rate

---

## Phase 8: Comprehensive Logging

**MANDATORY: Complete audit trail for reproducibility.**

### 8.1 Required Directory Structure

```
experiments/[domain]/
├── EXPERIMENT_LOG.md              # Master registry and summaries
├── results/
│   ├── exp_xxx_results.json       # Machine-readable results
│   ├── exp_xxx_results.md         # Human-readable report
│   └── exp_xxx_plots/             # Visualizations
├── data/
│   ├── raw/                       # Unprocessed input data
│   │   └── [symbol]_[start]_[end].csv
│   ├── processed/                 # Cleaned/transformed data
│   │   └── [symbol]_features.parquet
│   └── data_manifest.json         # Data provenance tracking
├── models/
│   ├── exp_xxx_model.pkl          # Trained model artifacts
│   └── exp_xxx_params.json        # Model parameters
└── logs/
    └── exp_xxx_runtime.log        # Execution logs with timestamps
```

### 8.2 Data Provenance (data_manifest.json)

```json
{
  "datasets": [
    {
      "name": "DATASET_NAME",
      "source": "data_source",
      "fetch_date": "2026-01-25T10:30:00Z",
      "start_date": "2014-01-01",
      "end_date": "2026-01-25",
      "rows": 2950,
      "columns": ["col1", "col2"],
      "checksum_sha256": "abc123...",
      "preprocessing": [
        {"step": "transform_name", "column": "col_name"},
        {"step": "dropna", "rows_removed": 1}
      ]
    }
  ]
}
```

### 8.3 Checklist for Complete Logging

**Data Artifacts:**
- [ ] Raw data files saved with checksums
- [ ] Data manifest with provenance
- [ ] Preprocessing steps documented
- [ ] Train/test splits reproducible

**Model Artifacts:**
- [ ] Trained models saved (pickle/joblib)
- [ ] Model parameters in JSON
- [ ] Random seeds recorded
- [ ] Package versions recorded

**Result Artifacts:**
- [ ] JSON results file (machine-readable)
- [ ] Markdown report (human-readable)
- [ ] Visualizations saved as PNG/SVG
- [ ] Confidence intervals included

**Execution Artifacts:**
- [ ] Runtime log with timestamps
- [ ] Error logs if any
- [ ] Execution duration recorded

---

## Quick Checklist

### Pre-Experiment
- [ ] Claim extracted with source citation (Phase 1)
- [ ] ALL claims documented, not just tested ones (Phase 1.5)
- [ ] Hypothesis documented BEFORE seeing results (Phase 2)
- [ ] Power analysis completed - required n calculated (Phase 2.3)
- [ ] EXP-XXX ID assigned
- [ ] Success criteria defined (effect size, p-value, n)
- [ ] Train/test split defined (walk-forward for time series) (Phase 3.5)
- [ ] Domain-specific costs/constraints specified

### During Experiment
- [ ] Look-ahead bias audit completed (Phase 3.1)
- [ ] Survivorship tracking enabled (Phase 3.2)
- [ ] Walk-forward validation used for time series (Phase 3.5)
- [ ] No parameter tuning on test data (Phase 3.4)
- [ ] All experiments logged (including failures)

### Post-Experiment
- [ ] Sample size adequate (n >= required from power analysis) (Phase 2.3)
- [ ] p-value calculated (Phase 4.4)
- [ ] Effect size reported vs domain thresholds (Phase 4.6.1)
- [ ] Bayesian analysis if p-value ambiguous (Phase 4.7)
- [ ] Confidence intervals computed (Phase 4.5)
- [ ] Sensitivity analysis passed (Phase 5.3)
- [ ] Multi-context validation (if applicable) (Phase 5)
- [ ] Adversarial review completed (Phase 5.5)
- [ ] Results logged to experiment registry
- [ ] Negative results documented if REJECTED (Phase 7.3)
- [ ] Verdict assigned with evidence

### Red Flags (Investigate!)
- [ ] 100% success rate (possible bias)
- [ ] OOS better than training (possible leakage)
- [ ] No failures in 20+ samples (suspicious)
- [ ] Parameters changed after seeing OOS (snooping)
- [ ] Result flips with ±20% parameter change (fragile)
- [ ] Only tested "interesting" claims (selection bias)

---

## Key Principles

1. **Hypothesis BEFORE data** - No peeking
2. **Falsifiable claims** - Specific, measurable predictions
3. **Power analysis BEFORE experiment** - Know required n upfront
4. **Statistical AND practical significance** - Both required
5. **Walk-forward for time series** - Preserve temporal order
6. **Sensitivity analysis** - Results must survive ±20% parameter changes
7. **Multi-context validation** - One context = possible overfitting
8. **Adversarial self-critique** - Challenge your own methodology
9. **Bayesian when ambiguous** - Complement p-values with Bayes factors
10. **Document negative results** - Failures are valuable
11. **Reject failures** - Data beats authority
12. **Sources can be wrong** - Even experts, even textbooks
