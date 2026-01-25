# Statistical Fallacy Detection

Detailed detection methods for critical statistical fallacies.

---

## Regression to the Mean

**What it is:** Extreme initial observations tend to be followed by more moderate ones, purely due to randomness.

**Detection questions:**
- Were subjects/instruments selected based on extreme initial performance?
- Did the "best" or "worst" performers show mean-reverting results?
- Is the effect size smaller than expected regression to mean?

**Red flags:**
```
BAD: "Top 10 traders maintained edge" → Selected AFTER seeing performance → Regression expected
BAD: "Strategy worked best on volatile days" → Volatile days regress to normal → Overstated effect
BAD: "Hot hand detected" → Extreme streaks regress naturally → Spurious pattern
```

**Required action:** If subjects were selected post-hoc based on extreme values, calculate expected regression:

```python
def expected_regression(initial_z_score, reliability):
    """
    Expected value after regression to mean.

    Args:
        initial_z_score: How extreme the initial observation was
        reliability: Test-retest correlation (0-1)

    Returns:
        Expected z-score on retest (closer to 0)
    """
    return initial_z_score * reliability

# Example: Top trader with z=2.5, reliability=0.6
# Expected retest: 2.5 * 0.6 = 1.5 (regression of 1.0)
```

**Verdict:** If observed effect ≤ expected regression → **REVISE** (not a real effect)

---

## Simpson's Paradox

**What it is:** A trend in aggregated data reverses when data is split into subgroups.

**Detection questions:**
- Does the effect hold within each meaningful subgroup?
- Are there confounding variables that stratify the data?
- Would controlling for a lurking variable reverse the conclusion?

**Red flags:**
```
BAD: "Strategy wins 60% overall" but loses in bull AND bear markets separately
BAD: "Pattern predicts reversals" but fails in both high AND low volatility
BAD: "Treatment works" but fails for both young AND old patients separately
```

**Required check:**

```python
def check_simpsons_paradox(data, outcome_col, treatment_col, stratify_cols):
    """
    Check if aggregate result reverses in subgroups.

    Returns:
        dict with 'paradox_detected', 'aggregate_effect', 'subgroup_effects'
    """
    # Calculate aggregate effect
    aggregate = calculate_effect(data, outcome_col, treatment_col)

    # Calculate effect within each stratum
    subgroup_effects = {}
    for col in stratify_cols:
        for value in data[col].unique():
            subset = data[data[col] == value]
            effect = calculate_effect(subset, outcome_col, treatment_col)
            subgroup_effects[f"{col}={value}"] = effect

    # Detect paradox: aggregate positive but all subgroups negative (or vice versa)
    aggregate_sign = np.sign(aggregate)
    subgroup_signs = [np.sign(e) for e in subgroup_effects.values()]

    paradox = all(s != aggregate_sign for s in subgroup_signs if s != 0)

    return {
        'paradox_detected': paradox,
        'aggregate_effect': aggregate,
        'subgroup_effects': subgroup_effects,
        'recommendation': 'INVALID - Simpson\'s Paradox' if paradox else 'OK'
    }
```

**Mandatory stratifications for trading:**
- Market regime (bull/bear/sideways)
- Volatility regime (high/low)
- Time period (pre/post major events)
- Instrument type (if multi-instrument)

**Verdict:** If paradox detected → **INVALID** (aggregate result is misleading)

---

## Ecological Fallacy

**What it is:** Assuming group-level statistics apply to individuals within the group.

**Detection questions:**
- Are conclusions about individuals drawn from aggregate data?
- Does the claim require individual-level data that wasn't collected?
- Is there within-group variation that contradicts the aggregate?

**Red flags:**
```
BAD: "Traders using X average 60% win rate" → Individual trader may have 40%
BAD: "Markets with pattern Y rise 5%" → Specific market may fall
BAD: "Funds in category Z beat benchmark" → Your fund may underperform
```

**Detection framework:**

```python
def check_ecological_fallacy(data, group_col, outcome_col, claim_level='individual'):
    """
    Check if group-level findings are being applied to individuals.

    Args:
        data: DataFrame with individual observations
        group_col: Column defining groups
        outcome_col: Outcome being measured
        claim_level: 'individual' or 'group' - what the claim is about

    Returns:
        dict with 'fallacy_risk', 'group_variance', 'within_group_variance'
    """
    # Calculate group means
    group_means = data.groupby(group_col)[outcome_col].mean()

    # Calculate within-group variance
    within_variance = data.groupby(group_col)[outcome_col].var().mean()

    # Calculate between-group variance
    between_variance = group_means.var()

    # Intraclass correlation: how much variance is between vs within groups
    icc = between_variance / (between_variance + within_variance)

    # High within-group variance + individual-level claim = ecological fallacy risk
    fallacy_risk = (claim_level == 'individual' and icc < 0.5)

    return {
        'fallacy_risk': fallacy_risk,
        'icc': icc,
        'interpretation': (
            f"Only {icc:.0%} of variance is between groups. "
            f"Individual outcomes vary widely within groups."
            if fallacy_risk else "Group-level findings may apply to individuals."
        ),
        'recommendation': 'REVISE - need individual-level analysis' if fallacy_risk else 'OK'
    }
```

**Verdict:** If ecological fallacy risk AND claim is about individuals → **REVISE**

---

## Summary Table

| Fallacy | Detection | Severity | Action |
|---------|-----------|----------|--------|
| Regression to Mean | Post-hoc selection on extreme values | HIGH | Calculate expected regression, adjust |
| Simpson's Paradox | Aggregate reverses in subgroups | CRITICAL | **INVALID** - result is misleading |
| Ecological Fallacy | Group stats applied to individuals | MEDIUM | **REVISE** - need individual analysis |
