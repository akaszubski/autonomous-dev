# Scientific Validation Workflow

Step-by-step guide to validate claims from any source using rigorous methodology.

## Related Files

| File | Content |
|------|---------|
| `SKILL.md` | Quick reference, activation, key principles |
| `code-examples.md` | Python implementations |
| `templates.md` | Markdown templates for documentation |
| `../../agents/experiment-critic.md` | Adversarial review agent |

---

## Overview: The Enhanced Validation Process

| Step | Phase | Deliverable |
|------|-------|-------------|
| 1 | Claims Extraction | `docs/research/[SOURCE]_CLAIMS.md` |
| 1.5 | **Publication Bias Prevention** | Selection rationale documented |
| 2 | Experiment Setup | `experiments/[DOMAIN]/EXPERIMENT_LOG.md` |
| 2.3 | **Power Analysis (MANDATORY)** | Required n calculated |
| 3 | Detection Infrastructure | Validators in `[project]/validation/` |
| 3.5 | **Walk-Forward Validation** | Time series validation configured |
| 4 | Bias Prevention | Audit tools configured |
| 5 | Training Validation | In-sample results documented |
| 5.3 | **Sensitivity Analysis (MANDATORY)** | Parameter stability documented |
| 6 | OOS Validation | Out-of-sample results documented |
| 6.5 | **Bayesian Complement** | Bayes Factors calculated |
| 7 | Adversarial Review | Experiment-critic agent review |
| 7.3 | **Structured Negative Results** | REJECTED claims fully documented |
| 8 | Classification | Each claim assigned verdict |

**New in v2.0:** Steps marked with **bold** are new mandatory or recommended phases.

---

## Step 1: Claims Extraction

**Goal:** Extract testable claims from source material.

### Process

1. **Get source material in searchable format**
   ```bash
   # For PDFs
   python scripts/extract_pdf.py source.pdf --output docs/research/source_extracted.txt

   # For other formats, manually extract or use appropriate tools
   ```

2. **Create claims registry**

   File: `docs/research/[SOURCE]_CLAIMS.md`

   ```markdown
   # Claims from [Source Title]

   **Author:** [Name]
   **Domain:** [Domain]
   **Extracted:** [Date]

   ## Summary
   - Total claims identified: X
   - Testable claims: Y
   - Priority HIGH: Z

   ---

   ## CLAIM-001: [Name]

   **Location:** Chapter X, Page Y
   **Quote:** "[Exact quote]"
   **Testable Prediction:** [Specific outcome]
   **Detection:** [How to identify]
   **Data Required:** [What data needed]
   **Priority:** HIGH/MEDIUM/LOW

   ## CLAIM-002: [Name]
   ...
   ```

3. **Prioritize claims**
   - HIGH: Clear, testable, data available
   - MEDIUM: Testable but needs infrastructure
   - LOW: Vague or limited data
   - SKIP: Not falsifiable

### Checklist
- [ ] Source material extracted/accessible
- [ ] Claims identified with source citations
- [ ] Each claim has testable prediction
- [ ] Claims prioritized by testability
- [ ] Directory structure created

---

## Step 1.5: Publication Bias Prevention (NEW)

**Goal:** Prevent cherry-picking by documenting ALL claims BEFORE selecting which to test.

### Process

1. **Document ALL claims first** (not just interesting ones)

   ```markdown
   ## Complete Claims Inventory

   | ID | Claim | Testable | Selected | Reason if Not Selected |
   |----|-------|----------|----------|------------------------|
   | C-001 | Pattern X predicts Y | Yes | Yes | - |
   | C-002 | Effect Z is 5% | Yes | No | Insufficient data available |
   | C-003 | Method A outperforms B | No | Skip | Not falsifiable |
   ```

2. **Apply selection bias correction**

   If testing subset of claims, adjust p-values:
   ```python
   adjusted_p = raw_p * (total_claims / tested_claims)
   ```

3. **Pre-commit to reporting**

   Add to experiment log:
   ```markdown
   ## Pre-Registration

   **Total claims identified:** 47
   **Claims selected for testing:** 12
   **Selection criteria:** Data availability, clear falsifiability
   **Commitment:** Will report ALL 12 results regardless of outcome
   ```

### Checklist
- [ ] ALL claims documented (not just selected ones)
- [ ] Selection rationale documented for each claim
- [ ] Pre-committed to reporting all tested claims
- [ ] Adjustment factor calculated if testing subset

---

## Step 2: Experiment Setup

**Goal:** Create tracking infrastructure before any testing.

### Process

1. **Create experiment log**

   File: `experiments/[DOMAIN]/EXPERIMENT_LOG.md`

   ```markdown
   # [Domain] Validation Experiment Log

   **Research Question:** [Main question]
   **Source:** [Book/Paper]
   **Started:** [Date]

   ## Claims vs Reality Summary

   | Claim | Source Says | Data Says | Verdict |
   |-------|-------------|-----------|---------|
   | [Name] | [Quote] | [Result] | [Status] |

   ## Experiment Registry

   | ID | Claim | Dataset | Status | Result | p-value | Verdict |
   |----|-------|---------|--------|--------|---------|---------|
   | EXP-001 | | | PLANNED | | | |

   ## Detailed Results

   [Individual experiment entries below]
   ```

2. **Define standard datasets**

   ```markdown
   ## Standard Validation Datasets

   | Name | Source | Period | Size | Purpose |
   |------|--------|--------|------|---------|
   | Primary Train | [source] | [dates] | [n] | In-sample |
   | Primary Test | [source] | [dates] | [n] | OOS |
   | Secondary | [source] | [dates] | [n] | Replication |
   ```

3. **Define cost model (domain-specific)**

   For trading: transaction costs, slippage
   For processes: time costs, resource costs
   For predictions: error costs

### Checklist
- [ ] EXPERIMENT_LOG.md created
- [ ] Claims vs Reality table initialized
- [ ] Datasets defined with train/test split
- [ ] Cost model documented

---

## Step 2.3: Power Analysis (MANDATORY - NEW)

**Goal:** Calculate required sample size BEFORE running experiments.

### Process

1. **Determine minimum detectable effect**

   Ask: "What's the smallest effect that would be practically meaningful?"

   | Domain | Metric | Minimum Meaningful |
   |--------|--------|-------------------|
   | Trading | Win Rate | 55% (vs 50% baseline) |
   | Trading | Sharpe Ratio | 0.5 |
   | Medicine | Risk Reduction | 20% relative |
   | A/B Testing | Conversion Lift | 5% relative |

2. **Calculate required sample size**

   ```python
   from statsmodels.stats.power import TTestIndPower

   def calculate_required_n(effect_size, power=0.80, alpha=0.05):
       """
       Calculate required sample size.

       Args:
           effect_size: Cohen's d or equivalent
           power: Probability of detecting true effect (0.80 standard)
           alpha: Significance level (0.05 standard)

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

   # Example: Detect 55% win rate vs 50% baseline
   # effect_size = (0.55 - 0.50) / 0.5 = 0.1 (Cohen's h for proportions)
   required_n = calculate_required_n(0.1)  # ~1571 per group
   ```

3. **Document in experiment log**

   ```markdown
   ## Power Analysis

   | Claim | Effect Size | Required n | Available n | Powered? |
   |-------|-------------|------------|-------------|----------|
   | Pattern X | d=0.3 | 176 | 250 | Yes |
   | Pattern Y | d=0.2 | 394 | 150 | NO |

   **Underpowered experiments:** Will report but mark INSUFFICIENT DATA
   ```

### Power Thresholds

| Achieved Power | Classification |
|----------------|----------------|
| ≥ 80% | Adequately powered |
| 50-80% | Underpowered - interpret with caution |
| < 50% | Severely underpowered - INSUFFICIENT DATA |

### Checklist
- [ ] Minimum meaningful effect defined per claim
- [ ] Required n calculated for each experiment
- [ ] Underpowered experiments identified upfront
- [ ] Power analysis documented in experiment log

---

## Step 3: Detection Infrastructure

**Goal:** Build validators/detectors for each testable claim.

### Process

1. **Create base validator pattern**

   ```python
   from abc import ABC, abstractmethod
   from dataclasses import dataclass
   from typing import List
   from datetime import datetime

   @dataclass
   class DetectionResult:
       """Result of attempting to detect a pattern/signal."""
       detected: bool
       confidence: float  # 0.0 to 1.0
       metadata: dict
       detection_time: datetime  # When detection occurred

   class BaseValidator(ABC):
       """Base class for all validators."""

       @abstractmethod
       def detect(self, data) -> List[DetectionResult]:
           """Detect patterns/signals in data."""
           pass

       @abstractmethod
       def validate_no_lookahead(self, data) -> bool:
           """Verify no future data is used in detection."""
           pass
   ```

2. **Implement one validator per claim**
   - Input: Domain-appropriate data
   - Output: List of detections with confidence and timing
   - Include detection time for bias auditing

3. **Test on known examples**
   - Manually identify 5-10 examples
   - Verify validator detects them
   - Document false positives/negatives

### Checklist
- [ ] Base validator class created
- [ ] One validator per HIGH priority claim
- [ ] Each validator tested on manual examples
- [ ] Detection timing tracked

---

## Step 3.5: Walk-Forward Validation (MANDATORY for Time Series - NEW)

**Goal:** Use proper time series validation to prevent look-ahead bias.

### Why Walk-Forward?

Standard train/test split assumes data is i.i.d. Time series data is NOT:
- Future data can leak into training
- Market regimes change over time
- Single split may land in unrepresentative period

### Process

1. **Configure walk-forward parameters**

   ```python
   def walk_forward_validate(data, model, train_window, test_window, min_folds=5):
       """
       Walk-forward validation with sliding window.

       Args:
           data: Time-indexed DataFrame
           model: Model/validator to test
           train_window: Number of periods for training
           test_window: Number of periods for testing (out-of-sample)
           min_folds: Minimum number of test folds required

       Returns:
           List of fold results
       """
       results = []

       for i in range(train_window, len(data) - test_window, test_window):
           # Train on past data only
           train_data = data[i - train_window : i]

           # Test on future data
           test_data = data[i : i + test_window]

           # Fit model on training data
           model.fit(train_data)

           # Predict on test data
           predictions = model.predict(test_data)

           # Evaluate
           fold_result = {
               'fold': len(results) + 1,
               'train_start': train_data.index[0],
               'train_end': train_data.index[-1],
               'test_start': test_data.index[0],
               'test_end': test_data.index[-1],
               'metrics': evaluate(predictions, test_data)
           }
           results.append(fold_result)

       return results
   ```

2. **Validate across multiple folds**

   ```markdown
   ## Walk-Forward Results

   | Fold | Train Period | Test Period | Win Rate | p-value |
   |------|--------------|-------------|----------|---------|
   | 1 | 2015-2017 | 2018 | 58% | 0.04 |
   | 2 | 2016-2018 | 2019 | 54% | 0.21 |
   | 3 | 2017-2019 | 2020 | 61% | 0.01 |
   | 4 | 2018-2020 | 2021 | 52% | 0.38 |
   | 5 | 2019-2021 | 2022 | 55% | 0.12 |

   **Aggregate:** 56% (n=250), p=0.03
   **Consistency:** 3/5 folds significant
   ```

3. **Check for regime dependence**

   Red flags:
   - Performance varies wildly across folds
   - Works only in specific market conditions
   - Recent folds perform worse (strategy decay)

### Checklist
- [ ] Walk-forward configured with appropriate windows
- [ ] Minimum 5 folds for statistical reliability
- [ ] Results reported per-fold AND aggregate
- [ ] Regime dependence assessed

---

## Step 4: Bias Prevention

**Goal:** Build safeguards BEFORE running experiments.

### 4.1 Look-Ahead Bias Audit

```python
class LookaheadAuditor:
    """Compare batch vs streaming detection."""

    def audit(self, data, validator) -> AuditReport:
        # Batch: process all data at once
        batch_results = validator.detect(data)

        # Streaming: process bar-by-bar
        streaming_results = []
        for i in range(len(data)):
            partial = data[:i+1]
            detections = validator.detect(partial)
            # Only count NEW detections at this bar
            streaming_results.extend([d for d in detections
                                      if d.detection_time == data.index[i]])

        # Compare
        discrepancies = self._find_discrepancies(batch_results, streaming_results)

        return AuditReport(
            has_bias=len(discrepancies) > 0,
            discrepancies=discrepancies,
            bias_percentage=len(discrepancies) / len(batch_results) * 100
        )
```

### 4.2 Survivorship Tracker

```python
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

        return AttemptMetrics(
            attempted=attempted,
            completed=completed,
            failed=failed,
            completion_rate=completed / attempted if attempted > 0 else 0,
            failure_reasons=self._count_reasons()
        )
```

### Checklist
- [ ] Look-ahead auditor built and tested
- [ ] Survivorship tracking enabled
- [ ] All validators pass look-ahead audit

---

## Step 5: Training Validation (In-Sample)

**Goal:** Test claims on training data to identify promising patterns.

### Process

1. **Pre-register each experiment**

   ```markdown
   ## EXP-001: [Claim Name]

   **Created:** [Date]
   **Status:** PRE-REGISTERED

   ### Hypothesis
   [Specific prediction BEFORE seeing results]

   ### Success Criteria
   - Win rate > 55%
   - p-value < 0.05
   - Sample size n >= 30
   - [Domain-specific criteria]

   ### Dataset
   - Training: [dates]
   - Costs: [specification]
   ```

2. **Run training validation**

   ```python
   def run_experiment(validator, data, cost_model):
       # Detect patterns
       detections = validator.detect(data)

       # Simulate outcomes
       results = []
       for d in detections:
           outcome = simulate_outcome(data, d, cost_model)
           results.append(outcome)

       # Calculate statistics
       wins = sum(1 for r in results if r['success'])
       n = len(results)

       if n > 0:
           win_rate = wins / n
           p_value = binomtest(wins, n, 0.5, alternative='greater').pvalue
           ci = bootstrap_ci([r['success'] for r in results])

       return {
           'n': n,
           'wins': wins,
           'win_rate': win_rate,
           'p_value': p_value,
           'ci': ci
       }
   ```

3. **Document results**

   Update experiment entry with in-sample results.

   **DO NOT adjust parameters based on results yet.**

### Checklist
- [ ] All HIGH claims have EXP-XXX entries
- [ ] Hypotheses documented BEFORE running
- [ ] Training results documented
- [ ] No parameter tuning yet

---

## Step 5.3: Sensitivity Analysis (MANDATORY for VALIDATED - NEW)

**Goal:** Verify results are robust to parameter changes, not fragile optimizations.

### Why Sensitivity Analysis?

A result that only works with specific parameter values is likely overfit:
- Parameters tuned to historical noise
- Won't generalize to new data
- False sense of edge

### Process

1. **Define parameter ranges**

   Test ±20% variation on each parameter:
   ```python
   base_params = {
       'lookback': 20,
       'threshold': 0.05,
       'holding_period': 5
   }

   # Test each at 80% and 120% of base value
   param_ranges = {
       'lookback': [16, 24],
       'threshold': [0.04, 0.06],
       'holding_period': [4, 6]
   }
   ```

2. **Run OFAT (One-Factor-At-a-Time) analysis**

   ```python
   def sensitivity_analysis(base_params, param_ranges, evaluate_func):
       """
       Test sensitivity to ±20% parameter variation.

       Args:
           base_params: Dictionary of baseline parameter values
           param_ranges: Dictionary of [low, high] values per parameter
           evaluate_func: Function that returns performance metric

       Returns:
           dict with base result and sensitivity to each parameter
       """
       results = {'base': evaluate_func(base_params)}

       for param, (low, high) in param_ranges.items():
           # Test low value
           test_params = base_params.copy()
           test_params[param] = low
           results[f'{param}_low'] = evaluate_func(test_params)

           # Test high value
           test_params = base_params.copy()
           test_params[param] = high
           results[f'{param}_high'] = evaluate_func(test_params)

       return results
   ```

3. **Document sensitivity table**

   ```markdown
   ## Sensitivity Analysis

   | Parameter | Base | -20% | +20% | Stable? |
   |-----------|------|------|------|---------|
   | lookback | 58% WR | 55% WR | 57% WR | Yes |
   | threshold | 58% WR | 52% WR | 61% WR | **NO** |
   | holding | 58% WR | 56% WR | 59% WR | Yes |

   **Conclusion:** Results sensitive to threshold parameter.
   Need wider validation or mark as CONDITIONAL.
   ```

### Stability Criteria

| Change in Metric | Classification |
|------------------|----------------|
| < 10% relative | Stable |
| 10-25% relative | Moderately sensitive |
| > 25% relative | **Fragile** - CONDITIONAL at best |

### Checklist
- [ ] All key parameters identified
- [ ] ±20% variation tested for each
- [ ] Sensitivity table documented
- [ ] Fragile parameters flagged

---

## Step 6: Out-of-Sample Validation

**Goal:** Test on held-out data to verify edge is real.

### Critical Rules

1. **NEVER tune parameters on OOS data**
2. **Use SAME parameters as training**
3. **If you peek and adjust, need NEW OOS data**

### Process

1. **Run OOS validation**

   ```python
   # Use EXACT same validator settings as training
   oos_results = run_experiment(validator, oos_data, cost_model)
   ```

2. **Compare to training**

   | Metric | Training | OOS |
   |--------|----------|-----|
   | Win Rate | X% | Y% |
   | p-value | | |
   | Sample Size | | |

3. **Classify result**

   | Status | Criteria |
   |--------|----------|
   | VALIDATED | Meets all pre-registered criteria |
   | CONDITIONAL | Meets relaxed criteria |
   | REJECTED | Fails criteria |
   | INSUFFICIENT | n < 15 OOS |

### Red Flags

- OOS win rate > training (possible leakage)
- 100% win rate (audit for bias)
- Very small OOS sample (need more data)

### Checklist
- [ ] OOS run with SAME parameters
- [ ] Results compared to training
- [ ] Each claim classified
- [ ] Rejected claims documented with evidence

---

## Step 6.5: Bayesian Complement (RECOMMENDED - NEW)

**Goal:** Supplement p-values with Bayes Factors for more interpretable evidence.

### Why Bayesian Methods?

P-values have limitations:
- Can't quantify evidence FOR null hypothesis
- "Not significant" ≠ "No effect"
- Sensitive to sample size and stopping rules

Bayes Factors answer: "How much more likely is the data under H1 vs H0?"

### Process

1. **Calculate Bayes Factor**

   ```python
   import pymc as pm
   import arviz as az

   def calculate_bayes_factor(wins, n, null_p=0.5):
       """
       Calculate Bayes Factor for win rate vs null hypothesis.

       Args:
           wins: Number of successes
           n: Total trials
           null_p: Null hypothesis probability (usually 0.5)

       Returns:
           Bayes Factor (BF10) - evidence for alternative vs null
       """
       with pm.Model() as model:
           # Prior: uniform over [0, 1]
           p = pm.Beta('p', alpha=1, beta=1)

           # Likelihood
           obs = pm.Binomial('obs', n=n, p=p, observed=wins)

           # Sample posterior
           trace = pm.sample(2000, return_inferencedata=True)

       # Calculate BF using Savage-Dickey ratio
       prior_density_at_null = 1.0  # Beta(1,1) is uniform
       posterior_samples = trace.posterior['p'].values.flatten()

       # KDE estimate of posterior at null
       from scipy.stats import gaussian_kde
       kde = gaussian_kde(posterior_samples)
       posterior_density_at_null = kde(null_p)[0]

       bf_01 = posterior_density_at_null / prior_density_at_null
       bf_10 = 1 / bf_01  # Evidence FOR alternative

       return bf_10
   ```

2. **Interpret Bayes Factor**

   | BF₁₀ | Evidence |
   |------|----------|
   | < 1 | Supports null hypothesis |
   | 1-3 | Anecdotal |
   | 3-10 | Moderate |
   | 10-30 | Strong |
   | 30-100 | Very strong |
   | > 100 | Extreme |

3. **Document both metrics**

   ```markdown
   ## Statistical Evidence

   | Claim | Win Rate | p-value | BF₁₀ | Interpretation |
   |-------|----------|---------|------|----------------|
   | Pattern A | 58% | 0.04 | 12.3 | Strong evidence |
   | Pattern B | 54% | 0.18 | 1.8 | Anecdotal - need more data |
   | Pattern C | 51% | 0.42 | 0.4 | Supports null (no edge) |
   ```

### When p-value and BF Disagree

| Scenario | p-value | BF₁₀ | Action |
|----------|---------|------|--------|
| Both support effect | < 0.05 | > 10 | Strong evidence for VALIDATED |
| p significant, BF weak | < 0.05 | < 3 | Collect more data |
| p not significant, BF supports null | > 0.05 | < 1/3 | Evidence for REJECTED |
| Both inconclusive | > 0.05 | 1/3 to 3 | INSUFFICIENT DATA |

### Checklist
- [ ] Bayes Factors calculated for key claims
- [ ] Both p-values and BFs reported
- [ ] Disagreements investigated
- [ ] Final classification considers both metrics

---

## Step 7: Adversarial Review (MANDATORY)

**Goal:** Challenge methodology before finalizing classification.

### Process

1. **Invoke experiment-critic agent**

   ```
   Use Task tool:
     subagent_type: "experiment-critic"
     prompt: "Review experiment EXP-XXX for data adequacy, methodology, circular validation, and statistical fallacies"
   ```

2. **Review critic output**

   The critic will assess:
   - Data adequacy (sufficiency, quality, diversity, independence)
   - Methodology soundness
   - Circular validation detection
   - Cost inclusion (for trading experiments)
   - Alternative explanations
   - **Statistical fallacies (NEW in v2.0):**
     - Regression to mean (post-hoc selection on extremes)
     - Simpson's Paradox (aggregate reverses in subgroups)
     - Ecological fallacy (group stats applied to individuals)

3. **Handle critic verdict**

   | Verdict | Action |
   |---------|--------|
   | PROCEED | Continue to classification |
   | REVISE | Fix methodology issues first |
   | INVALID | Re-run experiment (circular validation or Simpson's Paradox) |
   | UNTESTABLE | Mark claim as UNTESTABLE |

### Checklist
- [ ] Critic agent invoked
- [ ] All blocking issues addressed
- [ ] Statistical fallacies checked
- [ ] Verdict documented

---

## Step 7.3: Structured Negative Results (NEW)

**Goal:** Document REJECTED claims with same rigor as validated ones.

### Why Document Negative Results?

- Prevents re-testing the same failed approaches
- Reveals patterns in what DOESN'T work
- Contributes to scientific knowledge
- Prevents publication bias in your own work

### Template for REJECTED Claims

```markdown
## REJECTED: [Claim Name]

### Source Claim
**Book/Paper:** [Title]
**Author:** [Name]
**Quote:** "[Exact quote from source]"
**Claimed Effect:** [What they claimed]

### Our Test
**Methodology:** [Brief description]
**Sample Size:** n = [number]
**Time Period:** [dates]
**Markets/Instruments:** [what was tested]

### Results
**Observed Effect:** [what we found]
**Win Rate:** [X]% vs [Y]% claimed
**p-value:** [value]
**Bayes Factor:** [value]
**95% CI:** [[low], [high]]

### Why It Failed

**Primary Reason:** [Main cause of failure]

**Contributing Factors:**
1. [Factor 1]
2. [Factor 2]
3. [Factor 3]

### Conditions Where It Might Work

[Be generous - when COULD this work?]
- If sample size increased to [n]
- In market conditions: [specific conditions]
- With modified parameters: [changes needed]

### Lessons Learned

1. [Key takeaway 1]
2. [Key takeaway 2]

### Replication Data

[Link to raw data and code for others to verify]
```

### Negative Results Summary Table

```markdown
## What Didn't Work

| Claim | Source Says | We Found | Why It Failed |
|-------|-------------|----------|---------------|
| Pattern X | "70% win rate" | 48% (n=156) | Overfitted to author's dataset |
| Method Y | "Outperforms" | No difference | Transaction costs eliminated edge |
| Signal Z | "Strong predictor" | 51% (n=89) | Too few occurrences, noise |
```

### Checklist
- [ ] All REJECTED claims have structured documentation
- [ ] Each rejection includes "Why It Failed"
- [ ] Conditions where it might work identified
- [ ] Lessons learned documented

---

## Step 8: Classification and Documentation

**Goal:** Assign final verdicts and document learnings.

### Process

1. **Update Claims vs Reality table**

   ```markdown
   | Claim | Source Says | Data Says | Verdict |
   |-------|-------------|-----------|---------|
   | Pattern A | "Highly reliable" | 91% (n=403) | VALIDATED |
   | Pattern B | "Strong signal" | 48% (n=78) | REJECTED |
   | Pattern C | "Works well" | n=5 | INSUFFICIENT |
   ```

2. **Document rejected claims**

   **This is critical** - document WHY the source was wrong.

   ```markdown
   ### REJECTED: [Claim Name]

   **Source Claim:** "[Exact quote]"
   **Our Finding:** [Result with statistics]
   **Why Source Was Wrong:** [Analysis]
   **Evidence:** [Data supporting rejection]
   ```

3. **Summarize key learnings**

   - What worked that we expected?
   - What worked that we didn't expect?
   - What failed that we expected to work?
   - What patterns emerged?

### Checklist
- [ ] All claims have final verdicts
- [ ] Rejected claims have documented evidence
- [ ] Key learnings captured
- [ ] Experiment log complete

---

## GitHub Issue Template for Validation Projects

```markdown
## Validate Claims from [Source Title]

### Source
- **Title:** [Full title]
- **Author:** [Name]
- **Domain:** [Trading/Medicine/etc.]

### Scope
- **Claims to test:** [Number]
- **Priority HIGH claims:** [Number]
- **Estimated experiments:** [Number]

### Methodology
Following scientific-validation skill workflow v2.0:
1. Claims extraction to `docs/research/[SOURCE]_CLAIMS.md`
1.5. Publication bias prevention (document ALL claims)
2. Experiment log at `experiments/[DOMAIN]/EXPERIMENT_LOG.md`
2.3. Power analysis (calculate required n)
3. Validators in `[project]/validation/`
3.5. Walk-forward validation (for time series)
4. Bias prevention infrastructure
5. Training validation
5.3. Sensitivity analysis (±20% parameter variation)
6. OOS validation
6.5. Bayesian complement (Bayes Factors)
7. Adversarial review (experiment-critic agent)
7.3. Structured negative results documentation
8. Classification and documentation

### Success Criteria per Claim
- [ ] Power analysis: ≥ 80% power achieved
- [ ] Win rate > 55% OOS
- [ ] p-value < 0.05 AND Bayes Factor > 3
- [ ] Sample size n >= 30 OOS
- [ ] Multi-context validation (3+ datasets)
- [ ] Effect size meets practical threshold
- [ ] Sensitivity: < 25% variation with ±20% parameters
- [ ] Walk-forward: ≥ 3/5 folds significant
- [ ] Passes adversarial review (no statistical fallacies)

### Deliverables
- [ ] Claims registry with ALL claims (not just selected)
- [ ] Power analysis documenting required n per claim
- [ ] Experiment log with all results
- [ ] Validators for each HIGH priority claim
- [ ] Walk-forward validation results (for time series)
- [ ] Sensitivity analysis tables
- [ ] Bias audit reports
- [ ] Adversarial review documentation (including fallacy checks)
- [ ] Final Claims vs Reality summary
- [ ] Structured negative results for REJECTED claims
- [ ] Production rules (validated only)

### Labels
`research`, `validation`, `[domain]`
```

---

## Quality Gates

| Metric | Threshold | Action if Fail |
|--------|-----------|----------------|
| Power Analysis | ≥ 80% power | Mark UNDERPOWERED |
| OOS Sample Size | n >= 30 | Mark INSUFFICIENT DATA |
| OOS p-value | < 0.05 | Mark NO EDGE |
| Bayes Factor | BF₁₀ > 3 | Requires additional evidence |
| OOS Win Rate | > 55% | Mark NO EDGE |
| Sensitivity | < 25% variation | Mark FRAGILE if fails |
| Net Return | > 0 after costs | Mark UNPROFITABLE |
| Max Drawdown | < 25% | Flag HIGH RISK |
| Walk-Forward | ≥ 3/5 folds | Mark INCONSISTENT |
| Adversarial Review | PROCEED | Fix issues first |
| Simpson's Paradox | Not detected | Mark INVALID if found |

---

## Common Pitfalls

1. **Peeking at OOS data** - Always define hypothesis BEFORE looking at test period
2. **Skipping look-ahead audit** - Leads to inflated results that fail in live trading
3. **Cherry-picking results** - Report ALL experiments, including failures
4. **Insufficient sample size** - Need 30+ OOS trades for statistical validity
5. **Ignoring transaction costs** - Always include costs for trading experiments
6. **Skipping adversarial review** - Catches circular validation and methodology flaws
7. **Confirmation bias** - Be harder on confirming evidence than disconfirming
8. **Skipping power analysis** - Running underpowered experiments wastes time
9. **Parameter fragility** - Results that only work with exact parameters are overfit
10. **Ignoring Simpson's Paradox** - Aggregate results can be completely misleading
11. **Regression to mean** - Selecting on extremes guarantees artificial "reversion"
12. **Single train/test split** - For time series, use walk-forward validation
13. **P-hacking** - Multiple comparisons without correction inflate false positives

---

## Time Investment Guidance

Based on real-world validation projects:

| Phase | Typical Duration | Activities |
|-------|------------------|------------|
| Claims Extraction | 1 session | Read source, document claims |
| Infrastructure | 1-2 sessions | Build validators, tracking |
| Initial Testing | 2-3 sessions | Training validation |
| Sample Expansion | 2-3 sessions | Multi-market, increase n |
| OOS Validation | 1-2 sessions | Final validation |
| Adversarial Review | 1 session | Critic agent review |
| Documentation | 1 session | Summarize, classify |

**Total: 9-13 sessions for thorough validation**

The rigor takes time. But it prevents using unvalidated approaches.
