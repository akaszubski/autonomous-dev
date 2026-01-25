---
name: scientific-validation
version: 1.0.0
type: knowledge
description: Scientific method for validating claims from books, papers, or theories. Enforces pre-registration, statistical rigor, bias prevention, and evidence-based acceptance/rejection. Use when testing any testable hypothesis.
keywords: scientific method, hypothesis, validation, experiment, p-value, sample size, bias, out-of-sample, backtest, evidence, claims, books, research
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
- [ ] Claim extracted with source citation
- [ ] Hypothesis documented BEFORE seeing results
- [ ] EXP-XXX ID assigned
- [ ] Success criteria defined (effect size, p-value, n)
- [ ] Train/test split defined
- [ ] Domain-specific costs/constraints specified

### During Experiment
- [ ] Look-ahead bias audit completed
- [ ] Survivorship tracking enabled
- [ ] No parameter tuning on test data
- [ ] All experiments logged (including failures)

### Post-Experiment
- [ ] Sample size adequate (n >= 30)
- [ ] p-value calculated
- [ ] Effect size reported
- [ ] Confidence intervals computed
- [ ] Multi-context validation (if applicable)
- [ ] Adversarial review completed (Phase 5.5)
- [ ] Results logged to experiment registry
- [ ] Verdict assigned with evidence

### Red Flags (Investigate!)
- [ ] 100% success rate (possible bias)
- [ ] OOS better than training (possible leakage)
- [ ] No failures in 20+ samples (suspicious)
- [ ] Parameters changed after seeing OOS (snooping)

---

## Key Principles

1. **Hypothesis BEFORE data** - No peeking
2. **Falsifiable claims** - Specific, measurable predictions
3. **Sufficient samples** - n >= 30 minimum
4. **Statistical AND practical significance** - Both required
5. **Out-of-sample testing** - Never tune on test data
6. **Multi-context validation** - One context = possible overfitting
7. **Adversarial self-critique** - Challenge your own methodology
8. **Reject failures** - Data beats authority
9. **Document everything** - Including failures
10. **Sources can be wrong** - Even experts, even textbooks
