---
name: scientific-validation
version: 2.1.0
type: knowledge
description: Scientific method for validating claims from books, papers, or theories. Enforces pre-registration, power analysis, statistical rigor, Bayesian methods, sensitivity analysis, bias prevention, and evidence-based acceptance/rejection.
keywords: scientific method, hypothesis, validation, experiment, p-value, sample size, bias, out-of-sample, backtest, evidence, claims, power analysis, Bayesian, sensitivity
auto_activate: false
allowed-tools: [Read, Grep, Glob, Bash, Write]
---

# Scientific Validation Skill

Rigorous methodology for validating claims from any source - books, papers, theories, or intuition.

## When This Skill Activates

- Testing claims from books, papers, or expert sources
- Validating rules, strategies, or hypotheses
- Running experiments or backtests
- Keywords: "validate", "test hypothesis", "experiment", "backtest", "prove", "evidence"

---

## Core Principle

**Data is the arbiter. Sources can be wrong.**

- Expert books can be wrong
- Only empirical validation decides what works
- Document negative results - they're valuable

---

## Phase Overview

| Phase | Name | Key Requirement |
|-------|------|-----------------|
| 0 | Claim Verification | Understand what source ACTUALLY claims |
| 1 | Claims Extraction | Document with source citations |
| 1.5 | Publication Bias Prevention | Document ALL claims before selecting |
| 2 | Pre-Registration | Hypothesis BEFORE seeing results |
| 2.3 | **Power Analysis** | Calculate required n (MANDATORY) |
| 3 | Bias Prevention | Look-ahead, survivorship, selection |
| 3.5 | **Walk-Forward** | Required for time series (MANDATORY) |
| 4 | Statistical Requirements | p-values, effect sizes, corrections |
| 4.7 | Bayesian Complement | Bayes Factors for ambiguous results |
| 5 | Multi-Source Validation | Test across 3+ contexts |
| 5.3 | **Sensitivity Analysis** | ±20% parameter stability (MANDATORY) |
| 5.5 | Adversarial Review | Invoke experiment-critic agent |
| 6 | Classification | VALIDATED / REJECTED / INSUFFICIENT |
| 7 | Documentation | Complete audit trail |
| 7.3 | Negative Results | Structured failure documentation |

**See**: `workflow.md` for detailed step-by-step instructions per phase.

---

## Quick Reference

### Claim Types

| Type | Testable? | Example |
|------|-----------|---------|
| PERFORMANCE | YES | "A beats B on metric X" |
| METHODOLOGICAL | YES | "A enables capability X" |
| PHILOSOPHICAL | MAYBE | "X is important because Y" |
| BEHAVIORAL | HARD | "Humans do X in situation Y" |

### Sample Size Requirements (80% Power)

| Effect Size | Cohen's d | Required n |
|-------------|-----------|------------|
| Small | 0.2 | 394 |
| Medium | 0.5 | 64 |
| Large | 0.8 | 26 |

**See**: `code-examples.md#power-analysis` for calculation code.

### Classification Criteria

| Status | Criteria |
|--------|----------|
| **VALIDATED** | OOS meets all criteria + critic PROCEED |
| **CONDITIONAL** | OOS meets relaxed criteria (p < 0.10) |
| **REJECTED** | OOS fails OR negative effect |
| **INSUFFICIENT** | n < 15 in OOS |
| **UNTESTABLE** | Required data unavailable |
| **INVALID** | Circular validation detected |

### Domain Effect Thresholds (Trading)

| Metric | Minimum | Strong | Exceptional |
|--------|---------|--------|-------------|
| Sharpe Ratio | > 0.5 | > 1.0 | > 2.0 |
| Win Rate | > 55% | > 60% | > 70% |
| Profit Factor | > 1.2 | > 1.5 | > 2.0 |

**See**: `code-examples.md#effect-thresholds` for other domains.

### Bayes Factor Interpretation

| BF | Evidence |
|----|----------|
| < 1 | Supports null |
| 1-3 | Anecdotal |
| 3-10 | Moderate |
| 10-30 | Strong |
| > 30 | Very strong |

---

## Critical Rules

### 1. Pre-Registration
- Document hypothesis BEFORE seeing any results
- Define success criteria BEFORE testing
- No peeking at test data

### 2. Power Analysis (Phase 2.3)
```python
from statsmodels.stats.power import TTestIndPower
n = TTestIndPower().solve_power(effect_size=0.5, power=0.80, alpha=0.05)
```
**Rule:** Underpowered studies cannot achieve VALIDATED status.

### 3. Walk-Forward for Time Series (Phase 3.5)
- Standard K-fold CV → INVALID (temporal leakage)
- Single train/test → CONDITIONAL at best
- Walk-forward → Can achieve VALIDATED

**See**: `code-examples.md#walk-forward` for implementation.

### 4. Multiple Comparison Correction
```python
alpha_corrected = 0.05 / num_claims  # Bonferroni
```
For trading claims: require **t-ratio > 3.0** (Harvey et al. standard).

### 5. Sensitivity Analysis (Phase 5.3)
Test ±20% parameter variation:
- All variations positive → Can achieve VALIDATED
- 1-2 sign flips → CONDITIONAL at best
- 3+ sign flips → REJECTED (fragile)

**See**: `code-examples.md#sensitivity-analysis` for implementation.

### 6. Adversarial Review (Phase 5.5)
```
Use Task tool:
  subagent_type: "experiment-critic"
  prompt: "Review experiment EXP-XXX"
```
**MANDATORY** before any classification.

---

## Bias Prevention Checklist

| Bias | Prevention |
|------|------------|
| Look-ahead | Process data sequentially, compare batch vs streaming |
| Survivorship | Track ALL attempts, not just completions |
| Selection | Report ALL experiments including failures |
| Data snooping | Strict train/test split, no tuning on test data |
| Publication | Document ALL claims before selecting which to test |

---

## Pre-Experiment Checklist

- [ ] Claim extracted with source citation
- [ ] ALL claims documented (not just tested ones)
- [ ] Hypothesis documented BEFORE results
- [ ] Power analysis: required n calculated
- [ ] Success criteria defined
- [ ] Walk-forward configured (time series)
- [ ] Costs/constraints specified

## Post-Experiment Checklist

- [ ] Sample size adequate per power analysis
- [ ] p-value AND effect size reported
- [ ] Bayesian analysis if ambiguous
- [ ] Sensitivity analysis passed
- [ ] Adversarial review completed
- [ ] Negative results documented if REJECTED

---

## Red Flags

- 100% success rate → Possible bias
- OOS better than training → Possible leakage
- Result flips with ±20% params → Fragile
- Only tested "interesting" claims → Selection bias

---

## Key Principles

1. **Hypothesis BEFORE data** - No peeking
2. **Power analysis BEFORE experiment** - Know required n
3. **Walk-forward for time series** - Preserve temporal order
4. **Sensitivity analysis** - Results must survive ±20% changes
5. **Adversarial self-critique** - Challenge your methodology
6. **Document negative results** - Failures are valuable
7. **Sources can be wrong** - Even experts, even textbooks

---

## Detailed Documentation

| Topic | File |
|-------|------|
| Step-by-step workflow | `workflow.md` |
| Python code examples | `code-examples.md` |
| Markdown templates | `templates.md` |
| Adversarial review | `../../agents/experiment-critic.md` |
