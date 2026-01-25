# Scientific Validation Workflow

Step-by-step guide to validate claims from any source using rigorous methodology.

---

## Overview: The 8-Step Process

| Step | Phase | Deliverable |
|------|-------|-------------|
| 1 | Claims Extraction | `docs/research/[SOURCE]_CLAIMS.md` |
| 2 | Experiment Setup | `experiments/[DOMAIN]/EXPERIMENT_LOG.md` |
| 3 | Detection Infrastructure | Validators in `[project]/validation/` |
| 4 | Bias Prevention | Audit tools configured |
| 5 | Training Validation | In-sample results documented |
| 6 | OOS Validation | Out-of-sample results documented |
| 7 | Adversarial Review | Experiment-critic agent review |
| 8 | Classification | Each claim assigned verdict |

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

## Step 7: Adversarial Review (MANDATORY)

**Goal:** Challenge methodology before finalizing classification.

### Process

1. **Invoke experiment-critic agent**

   ```
   Use Task tool:
     subagent_type: "experiment-critic"
     prompt: "Review experiment EXP-XXX for data adequacy, methodology, and circular validation"
   ```

2. **Review critic output**

   The critic will assess:
   - Data adequacy (sufficiency, quality, diversity, independence)
   - Methodology soundness
   - Circular validation detection
   - Cost inclusion (for trading experiments)
   - Alternative explanations

3. **Handle critic verdict**

   | Verdict | Action |
   |---------|--------|
   | PROCEED | Continue to classification |
   | REVISE | Fix methodology issues first |
   | INVALID | Re-run experiment |
   | UNTESTABLE | Mark claim as UNTESTABLE |

### Checklist
- [ ] Critic agent invoked
- [ ] All blocking issues addressed
- [ ] Verdict documented

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
Following scientific-validation skill workflow:
1. Claims extraction to `docs/research/[SOURCE]_CLAIMS.md`
2. Experiment log at `experiments/[DOMAIN]/EXPERIMENT_LOG.md`
3. Validators in `[project]/validation/`
4. Bias prevention infrastructure
5. Training validation
6. OOS validation
7. Adversarial review (experiment-critic agent)
8. Classification and documentation

### Success Criteria per Claim
- [ ] Win rate > 55% OOS
- [ ] p-value < 0.05
- [ ] Sample size n >= 30 OOS
- [ ] Multi-context validation (3+ datasets)
- [ ] Effect size meets practical threshold
- [ ] Passes adversarial review

### Deliverables
- [ ] Claims registry with all testable claims
- [ ] Experiment log with all results
- [ ] Validators for each HIGH priority claim
- [ ] Bias audit reports
- [ ] Adversarial review documentation
- [ ] Final Claims vs Reality summary
- [ ] Rejected claims documented with evidence
- [ ] Production rules (validated only)

### Labels
`research`, `validation`, `[domain]`
```

---

## Quality Gates

| Metric | Threshold | Action if Fail |
|--------|-----------|----------------|
| OOS Sample Size | n >= 30 | Mark INSUFFICIENT DATA |
| OOS p-value | < 0.05 | Mark NO EDGE |
| OOS Win Rate | > 55% | Mark NO EDGE |
| Net Return | > 0 after costs | Mark UNPROFITABLE |
| Max Drawdown | < 25% | Flag HIGH RISK |
| Adversarial Review | PROCEED | Fix issues first |

---

## Common Pitfalls

1. **Peeking at OOS data** - Always define hypothesis BEFORE looking at test period
2. **Skipping look-ahead audit** - Leads to inflated results that fail in live trading
3. **Cherry-picking results** - Report ALL experiments, including failures
4. **Insufficient sample size** - Need 30+ OOS trades for statistical validity
5. **Ignoring transaction costs** - Always include costs for trading experiments
6. **Skipping adversarial review** - Catches circular validation and methodology flaws
7. **Confirmation bias** - Be harder on confirming evidence than disconfirming

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
