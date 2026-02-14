# Experiment Critic - Methodology

Detailed step-by-step review process.

---

## Step 1: Read Experiment

```bash
Read experiments/<experiment_path>/results/*.json
Read experiments/<experiment_path>/*.py
```

Understand:
- Hypothesis being tested
- Methodology used
- Data sources
- Results claimed

---

## Step 2: Data Adequacy Check

| Criterion | Question | Failure Mode |
|-----------|----------|--------------|
| **Sufficiency** | Is n large enough for statistical power? | n < 30 for claims |
| **Quality** | Is data accurate and representative? | Single source, biased sample |
| **Diversity** | Multiple sources, periods, markets? | Single market/period |
| **Independence** | Is data independent of the claim? | Circular validation |
| **Completeness** | Does data include failures/delisted? | Survivorship bias |

**Scoring:**
- HIGH: All criteria pass
- MEDIUM: 4/5 criteria pass, issues are minor
- LOW: 2-3 criteria pass
- INSUFFICIENT: <2 criteria pass

---

## Step 3: Circular Validation Detection

**RED FLAGS - Automatic INVALID:**
- Simulating data based on the claim being tested
- Using literature estimates as "validation data"
- Testing a claim using assumptions derived from the claim
- Using the claim's output as ground truth

**Examples:**
```
BAD: "Survivorship bias is 1%" → Simulate dead funds with 1% → "Validated: ~1%"
BAD: "MCMC is better" → Use MCMC posterior as truth → "Validated: matches"
BAD: "Pattern X predicts Y" → Generate Y from X → "Validated: X predicts Y"
```

**Detection questions:**
1. Where does the validation data come from?
2. Was any part generated using the claim being tested?
3. Could the result be explained by methodology alone?

---

## Step 4: Cost/Friction Enforcement

For ANY trading or economic experiment:

- [ ] Transaction costs included?
- [ ] Realistic constraints (leverage, position limits, liquidity)?
- [ ] GROSS and NET returns reported separately?
- [ ] Slippage/market impact modeled?

**If costs missing:** Experiment is **INVALID** (not just incomplete)

For non-trading experiments:
- Time costs
- Resource costs
- Error costs
- Opportunity costs

---

## Step 5: Alternative Explanations

Ask:
- What else could explain this result?
- Have confounders been ruled out?
- Is there selection bias in the methodology?
- Would result replicate on different data?
- Is the effect size practically meaningful?

**List at least 3 alternative explanations for any positive result.**

---

## Step 6: Replication Requirements

Determine what would be needed to replicate:
- Same methodology on different data
- Different methodology on same data
- Independent researcher validation

---

## Step 7: Classification Gate

| Data Adequacy | Methodology | Classification Allowed |
|---------------|-------------|----------------------|
| HIGH | Sound | VALIDATED/REJECTED |
| MEDIUM | Sound | CONDITIONAL only |
| LOW | Sound | INSUFFICIENT DATA |
| ANY | Flawed | REQUEST REVISION |
| ANY | Circular | **INVALID** |

---

## Common Failure Patterns

| Pattern | Detection | Classification |
|---------|-----------|----------------|
| No actual data | Used simulation based on claim | **INVALID** |
| Literature as validation | Combined published numbers | **UNTESTABLE** |
| Missing costs | Trading experiment without costs | **INVALID** |
| Single market | Only tested on one market/period | CONDITIONAL at best |
| Trivial case | Tested easy scenario, claimed general | CONDITIONAL at best |
| Confirmation bias | Only reported supportive results | REQUEST REVISION |
| Overfitting | Parameters tuned on test data | **INVALID** |
