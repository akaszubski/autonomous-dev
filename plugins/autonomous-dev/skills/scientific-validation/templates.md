# Scientific Validation - Templates

Markdown templates for claims extraction, experiment logging, and results documentation.

---

## Claims Registry Template

File: `docs/research/[SOURCE]_CLAIMS.md`

```markdown
# Claims Registry: [Source Name]

**Source:** [Book/Paper/Theory Title]
**Author:** [Name]
**Year:** [Publication Year]
**Domain:** [Trading/Medicine/Psychology/etc.]
**Extraction Date:** [Today]

---

## Summary

| Metric | Count |
|--------|-------|
| Total claims identified | X |
| Testable claims | Y |
| Priority HIGH | Z |
| Selected for testing | W |

---

## Complete Claims Inventory

| ID | Claim | Testable | Selected | Reason if Not |
|----|-------|----------|----------|---------------|
| C-001 | [Short name] | Yes | Yes | - |
| C-002 | [Short name] | Yes | No | Insufficient data |
| C-003 | [Short name] | No | Skip | Not falsifiable |

---

## CLAIM-001: [Short Name]

**Source Location:** Chapter X, Page Y
**Verbatim Quote:** "[Exact quote from source]"
**Claim Type:** PERFORMANCE / METHODOLOGICAL / PHILOSOPHICAL / BEHAVIORAL
**Paraphrase:** [Your interpretation]
**What Source ACTUALLY Claims:** [Careful reading]
**Our Derived Prediction:** [What we will test]
**Gap Analysis:** [How derived differs from source]
**Detection Method:** [How to identify in data]
**Success Metric:** [What counts as "working"]
**Priority:** HIGH / MEDIUM / LOW
**Falsifiable:** YES / NO

---

## CLAIM-002: [Short Name]
...
```

---

## Experiment Log Template

File: `experiments/[DOMAIN]/EXPERIMENT_LOG.md`

```markdown
# [Domain] Validation Experiment Log

**Research Question:** [Main question]
**Source:** [Book/Paper]
**Started:** [Date]

---

## Claims vs Reality Summary

| Claim | Source Says | Data Says | Verdict |
|-------|-------------|-----------|---------|
| [Name] | "[Quote]" | X% (n=Y) | VALIDATED |
| [Name] | "[Quote]" | X% (n=Y) | REJECTED |

---

## Experiment Registry

| ID | Claim | Dataset | Status | Win Rate | p-value | Verdict |
|----|-------|---------|--------|----------|---------|---------|
| EXP-001 | | | PLANNED | | | |
| EXP-002 | | | IN_PROGRESS | | | |
| EXP-003 | | | COMPLETE | 58% | 0.03 | VALIDATED |

---

## Power Analysis Summary

| Claim | Effect Size | Required n | Available n | Powered? |
|-------|-------------|------------|-------------|----------|
| [Name] | d=0.3 | 176 | 250 | YES |
| [Name] | d=0.2 | 394 | 150 | NO |

---

## Standard Validation Datasets

| Name | Source | Period | Size | Purpose |
|------|--------|--------|------|---------|
| Primary Train | [source] | [dates] | [n] | In-sample |
| Primary Test | [source] | [dates] | [n] | OOS |
| Secondary | [source] | [dates] | [n] | Replication |

---

## Detailed Results

[Individual experiment entries below]
```

---

## Pre-Registration Template

```markdown
## EXP-XXX: [Claim Name]

**Created:** [Date]
**Status:** PRE-REGISTERED

### Source Claim
**Quote:** "[Exact quote]"
**Location:** Chapter X, Page Y

### Hypothesis
[Specific prediction BEFORE seeing results]

### Prediction (Specific)
- Direction: [UP/DOWN/POSITIVE/NEGATIVE]
- Magnitude: [Expected effect size]
- Timeframe: [When effect should appear]

### Success Criteria (Defined Before Testing)
- Minimum sample size: n >= [X]
- Significance threshold: p < [0.05]
- Effect size threshold: [metric] > [value]
- Practical significance: [threshold]

### Power Analysis
- Expected effect size: [Cohen's d or domain metric]
- Required n (80% power): [calculated]
- Available n: [actual]
- Powered: YES / NO

### Dataset
- Training period: [dates/range]
- Testing period: [dates/range] (HELD OUT)
- Source: [where data comes from]
- Walk-forward folds: [if time series]

### Costs/Constraints
[Domain-specific: transaction costs, time costs, etc.]
```

---

## Experiment Results Template

```markdown
## EXP-XXX: [Name] - COMPLETE

**Date Completed:** [Date]
**Status:** VALIDATED / CONDITIONAL / REJECTED / INSUFFICIENT

### Pre-Registered Hypothesis
[What you predicted BEFORE testing]

### Methodology
- Dataset: [description]
- Train period: [dates]
- Test period: [dates]
- Parameters: [all settings]
- Walk-forward: [Yes/No, number of folds]

### Results

| Metric | Training | Out-of-Sample |
|--------|----------|---------------|
| Sample Size | n=X | n=Y |
| Win Rate | X% | Y% |
| p-value | X.XXXX | Y.YYYY |
| Bayes Factor | X.X | Y.Y |
| Effect Size | X | Y |
| 95% CI | [low, high] | [low, high] |

### Sensitivity Analysis

| Parameter | Base | -20% | +20% | Stable? |
|-----------|------|------|------|---------|
| [param1] | X% | X% | X% | YES/NO |
| [param2] | X% | X% | X% | YES/NO |

### Walk-Forward Results (if applicable)

| Fold | Period | Win Rate | p-value |
|------|--------|----------|---------|
| 1 | [dates] | X% | 0.XX |
| 2 | [dates] | X% | 0.XX |

Folds significant: X/Y

### Adversarial Review
- Critic verdict: PROCEED / REVISE / INVALID
- Issues identified: [list]
- Resolution: [how addressed]

### Verdict
[VALIDATED / CONDITIONAL / REJECTED / INSUFFICIENT]

### Key Learnings
- [What worked]
- [What didn't]
- [Surprises]
- [Limitations]
```

---

## Negative Results Template

```markdown
## NEGATIVE RESULT: EXP-XXX - [Claim Name]

**Date:** [Date]
**Source:** [Book/Paper]
**Verdict:** REJECTED

### What We Expected
[The hypothesis and why it seemed plausible]

### What We Found

| Metric | Expected | Actual |
|--------|----------|--------|
| Win Rate | > 60% | 48% |
| p-value | < 0.05 | 0.73 |
| Effect Size | > 0.5 | 0.08 |
| Bayes Factor | > 10 | 0.4 |

### Why It Failed

**Failure Classification:**
- [ ] **SOURCE ERROR** - Claim was wrong
- [ ] **IMPLEMENTATION ERROR** - Our methodology was flawed
- [ ] **DATA QUALITY** - Data was insufficient or biased
- [ ] **CONTEXT MISMATCH** - Works elsewhere, not here
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

---

## Negative Results Registry

```markdown
# Negative Results Registry

| ID | Source | Claim | Why Failed | Value |
|----|--------|-------|------------|-------|
| EXP-005 | Book A | Pattern X | SOURCE ERROR | Disproved claim |
| EXP-012 | Paper B | Method Y | CONTEXT MISMATCH | Works in equities only |
| EXP-018 | Book A | Signal Z | DATA QUALITY | Need longer history |
```

---

## GitHub Issue Template

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
Following scientific-validation skill workflow v2.1:
1. Claims extraction
2. Publication bias prevention
3. Pre-registration with power analysis
4. Walk-forward validation (time series)
5. Sensitivity analysis
6. Adversarial review
7. Classification and documentation

### Success Criteria per Claim
- [ ] Power analysis: ≥ 80% power achieved
- [ ] Win rate > 55% OOS
- [ ] p-value < 0.05 AND Bayes Factor > 3
- [ ] Sample size n >= required from power analysis
- [ ] Sensitivity: < 25% variation with ±20% params
- [ ] Walk-forward: ≥ 3/5 folds significant
- [ ] Passes adversarial review

### Deliverables
- [ ] Claims registry with ALL claims
- [ ] Power analysis documenting required n
- [ ] Experiment log with results
- [ ] Sensitivity analysis tables
- [ ] Adversarial review documentation
- [ ] Structured negative results
- [ ] Final Claims vs Reality summary

### Labels
`research`, `validation`, `[domain]`
```

---

## Directory Structure

```
experiments/[domain]/
├── EXPERIMENT_LOG.md              # Master registry
├── results/
│   ├── exp_xxx_results.json       # Machine-readable
│   ├── exp_xxx_results.md         # Human-readable
│   └── exp_xxx_plots/             # Visualizations
├── data/
│   ├── raw/                       # Unprocessed
│   ├── processed/                 # Cleaned
│   └── data_manifest.json         # Provenance
├── models/
│   ├── exp_xxx_model.pkl          # Trained models
│   └── exp_xxx_params.json        # Parameters
└── logs/
    └── exp_xxx_runtime.log        # Execution logs
```

---

## Data Manifest Template

File: `experiments/[domain]/data/data_manifest.json`

```json
{
  "datasets": [
    {
      "name": "DATASET_NAME",
      "source": "data_provider",
      "fetch_date": "2026-01-25T10:30:00Z",
      "start_date": "2014-01-01",
      "end_date": "2026-01-25",
      "rows": 2950,
      "columns": ["open", "high", "low", "close", "volume"],
      "checksum_sha256": "abc123...",
      "preprocessing": [
        {"step": "adjust_splits", "column": "close"},
        {"step": "dropna", "rows_removed": 1}
      ]
    }
  ],
  "experiment_id": "EXP-XXX",
  "created": "2026-01-25T10:30:00Z"
}
```
