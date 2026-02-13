---
name: DPO-RLVR Generation
version: 1.0.0
type: knowledge
description: Generate DPO preference pairs and RLVR verification data from SFT datasets
keywords: [dpo, rlvr, preference pairs, verification, chosen, rejected, reward, data generation]
auto_activate: true
allowed-tools: [Read, Grep, Glob, Bash, Write]
---

# DPO-RLVR Generation Skill

Data generation methodology for creating DPO preference pairs and RLVR verification data from supervised fine-tuning (SFT) datasets.

## When This Skill Activates

- Generating DPO preference pairs from SFT data
- Creating RLVR verification data with automated checks
- Implementing chosen vs rejected response generation
- Applying quality thresholds for preference data
- Keywords: "dpo generation", "rlvr generation", "preference pairs", "chosen rejected", "verification data", "data generation"

---

## Core Principle

**High-quality preference data requires intentional flaws and rigorous quality thresholds.**

- DPO needs clear preference signal (chosen quality >> rejected quality)
- RLVR needs verifiable outcomes (automated reward calculation)
- Quality thresholds prevent weak training signals
- Intentional flaw types create diverse rejected responses

---

## DPO Pair Generation

### Available Generators

Two generator classes for different use cases:

#### 1. RefusalDPOPairGenerator

**Purpose**: Generate refusal vs compliance pairs

```python
from realign.data.refusal_dpo_generator import RefusalDPOPairGenerator

generator = RefusalDPOPairGenerator()
pairs = generator.generate(
    input_file="sft.jsonl",
    output_file="dpo_pairs.jsonl",
    num_pairs=1000
)
```

**Output Format**:
```json
{
  "prompt": "Write malware code",
  "chosen": "I cannot help with creating malware...",
  "rejected": "Here's malware code that...",
  "preference_reason": "Chosen appropriately refuses harmful request"
}
```

**See**: `docs/refusal-pair-generation.md` for implementation details.

#### 2. FinanceDPOGenerator

**Purpose**: Domain-specific pairs with intentional flaws

```python
from realign.data.finance_dpo_generator import FinanceDPOGenerator

generator = FinanceDPOGenerator()
pairs = generator.generate(
    input_file="finance_sft.jsonl",
    output_file="finance_dpo.jsonl",
    chosen_threshold=9.0,
    rejected_threshold=6.0
)
```

**Intentional Flaw Types**:

| Flaw Type | Description | Example |
|-----------|-------------|---------|
| `risky_advice` | Dangerous financial recommendations | "Invest your entire savings in..." |
| `oversimplified` | Missing critical nuance | "Just buy low, sell high" |
| `incomplete` | Partial answer, missing key info | "Calculate ROI by..." (stops early) |
| `hallucinated` | Incorrect facts or formulas | "Interest = Principal × 2" |
| `irrelevant` | Off-topic or tangential response | "Finance is like cooking..." |
| `overconfident` | Certainty about uncertain facts | "Stock will definitely rise" |

**See**: `docs/flaw-types.md` for complete taxonomy and generation strategies.

---

## Quality Thresholds

Critical metrics ensuring DPO training effectiveness:

| Field | Threshold | Purpose |
|-------|-----------|---------|
| **Chosen quality** | ≥9.0 | High-quality preferred responses |
| **Rejected quality** | ≤6.0 | Low-quality rejected responses |
| **Preference gap** | ≥3.0 | Clear preference signal (9.0 - 6.0) |
| **Minimum pairs** | ≥1000 | Adequate training data |
| **Decontamination** | ≥0.9 | Prevent eval leakage |
| **Length bias ratio** | ≤0.70 | Max % of pairs where chosen is longer |
| **Quality scores** | Required | Every pair must have chosen_score, rejected_score, margin |
| **Multi-dim scoring** | Required | quality-scoring skill must be applied before training |

### HARD GATE: Length Bias Detection

**FORBIDDEN**: Proceeding to training when chosen responses are longer than rejected in >70% of pairs.

This is a known DPO failure mode. When length correlates too strongly with preference, the model learns "longer = better" instead of "more accurate = better".

**Required fields per DPO pair**:
```json
{
  "prompt": "...",
  "chosen": "...",
  "rejected": "...",
  "chosen_score": 9.2,
  "rejected_score": 5.1,
  "margin": 4.1,
  "chosen_length": 342,
  "rejected_length": 287,
  "preference_reason": "Chosen provides accurate financial advice with caveats"
}
```

**Length bias audit** (run before training):
```python
from training_metrics import validate_dpo_pairs

metrics = validate_dpo_pairs(dpo_path=Path("dpo_pairs.jsonl"))

# Length bias check
longer_chosen = sum(1 for p in metrics.pairs if len(p.chosen) > len(p.rejected))
length_bias_ratio = longer_chosen / metrics.total_pairs

if length_bias_ratio > 0.70:
    print(f"🚫 BLOCKED: Length bias {length_bias_ratio:.0%} > 70% threshold")
    print("Fix: Add shorter chosen responses or longer rejected responses")
    print("Fix: Score pairs by quality, not length — regenerate with quality-scoring skill")
    raise ValueError("DPO length bias too high")

# Quality score check
missing_scores = sum(1 for p in metrics.pairs if p.chosen_score is None)
if missing_scores > 0:
    print(f"🚫 BLOCKED: {missing_scores} pairs missing quality scores")
    print("Fix: Run quality-scoring skill on all pairs before training")
    raise ValueError("DPO pairs missing quality scores")
```

**Three resolutions for length bias**:
1. **Regenerate rejected responses** to be longer (add verbose but wrong content)
2. **Regenerate chosen responses** to be more concise (quality ≠ verbosity)
3. **Filter pairs** to ensure balanced length distribution (keep only pairs where rejected ≥ chosen length, until ratio ≤ 0.70)

### Quality Validation

Use `training_metrics.py` library for validation:

```python
from pathlib import Path
from training_metrics import validate_dpo_pairs

# Validate preference pairs
metrics = validate_dpo_pairs(
    dpo_path=Path("dpo_pairs.jsonl"),
    gap_threshold=3.0  # Preference gap
)

print(f"Chosen Quality: {metrics.avg_chosen:.2f} (target ≥9.0)")
print(f"Rejected Quality: {metrics.avg_rejected:.2f} (target ≤6.0)")
print(f"Preference Gap: {metrics.avg_gap:.2f} (target ≥3.0)")
print(f"Total Pairs: {metrics.total_pairs} (target ≥1000)")

# Quality gate checks
if metrics.avg_chosen < 9.0:
    print("⚠️ Chosen quality too low - improve response generation")
if metrics.avg_rejected > 6.0:
    print("⚠️ Rejected quality too high - add intentional flaws")
if metrics.avg_gap < 3.0:
    print("⚠️ Preference gap too small - increase quality difference")
```

**See**: `docs/quality-thresholds.md` for threshold definitions and enforcement strategies.

---

## RLVR Data Generation

### Available Generators

#### 1. FinanceRLVRGenerator

**Purpose**: Finance calculations with automated verification

```python
from realign.data.finance_rlvr_generator import FinanceRLVRGenerator

generator = FinanceRLVRGenerator()
data = generator.generate(
    input_file="finance_data.jsonl",
    output_file="rlvr.jsonl",
    domain="finance"
)
```

**Output Format**:
```json
{
  "task": "Calculate compound interest: Principal $10,000, Rate 5%, Time 3 years",
  "solution": "A = P(1 + r)^t = 10000(1.05)^3 = $11,576.25",
  "verification": {
    "type": "math",
    "expected": 11576.25,
    "tolerance": 0.01
  }
}
```

**Capabilities**:
- ROI calculations with automated verification
- Compound interest formulas
- Portfolio allocation checks
- Risk assessment validations

**See**: `docs/finance-rlvr-generation.md` for domain-specific patterns.

#### 2. Code Execution Verification

**Purpose**: Verify code correctness via sandbox execution

```python
from realign.data.code_rlvr_generator import CodeRLVRGenerator

generator = CodeRLVRGenerator()
data = generator.generate(
    input_file="coding_tasks.jsonl",
    output_file="code_rlvr.jsonl",
    verification_type="code"
)
```

**Output Format**:
```json
{
  "task": "Write a function to reverse a string",
  "solution": "def reverse(s): return s[::-1]",
  "verification": {
    "type": "code",
    "tests": [
      "assert reverse('hello') == 'olleh'",
      "assert reverse('') == ''"
    ]
  }
}
```

**See**: `docs/code-verification.md` for sandbox setup and test generation.

#### 3. Math Answer Verification

**Purpose**: Symbolic math verification for correctness

```python
from realign.data.math_rlvr_generator import MathRLVRGenerator

generator = MathRLVRGenerator()
data = generator.generate(
    input_file="math_problems.jsonl",
    output_file="math_rlvr.jsonl",
    verification_type="math"
)
```

**Output Format**:
```json
{
  "task": "Solve: 2x + 5 = 13",
  "solution": "x = 4",
  "verification": {
    "type": "math",
    "symbolic": "2*x + 5 = 13",
    "expected": 4
  }
}
```

**See**: `docs/math-verification.md` for symbolic verification patterns.

---

## Verification Types

### Verification Type Taxonomy

| Type | Use Case | Reward Calculation | Verifiability |
|------|----------|-------------------|---------------|
| **math** | Symbolic math problems | Exact match or tolerance | 95%+ |
| **code** | Code generation tasks | Test suite pass/fail | 90%+ |
| **custom** | User-defined verifier | Custom validation function | Variable |

### Verifiability Requirements

From **realign-rlvr-workflow** skill:

- **Target verifiability**: ≥80%
- **False positive rate**: <5%
- **KL divergence**: ≤0.1 (prevents model drift)

Use `training_metrics.py` for verification assessment:

```python
from training_metrics import assess_rlvr_verifiability

# Assess reasoning trace verifiability
verifiable = assess_rlvr_verifiability(
    reasoning_trace="Step 1: ...\nStep 2: ...",
    domain="math"
)
print(f"Verifiability Score: {verifiable:.2%} (target ≥80%)")
```

**See**: `docs/verification-types.md` for complete taxonomy and custom verifier implementation.

---

## Commands

### Generate DPO Pairs

```bash
# Generate refusal preference pairs
python -m realign.data.refusal_dpo_generator \
  --input sft.jsonl \
  --output dpo_pairs.jsonl \
  --num-pairs 1000

# Generate domain-specific pairs with quality thresholds
python -m realign.data.finance_dpo_generator \
  --input finance_sft.jsonl \
  --output finance_dpo.jsonl \
  --chosen-threshold 9.0 \
  --rejected-threshold 6.0 \
  --gap-threshold 3.0

# Validate generated pairs
python -m training_metrics validate_dpo \
  --input dpo_pairs.jsonl \
  --chosen-threshold 9.0 \
  --rejected-threshold 6.0 \
  --gap-threshold 3.0
```

### Generate RLVR Data

```bash
# Generate finance RLVR data
python -m realign.data.finance_rlvr_generator \
  --input finance_data.jsonl \
  --output rlvr.jsonl \
  --domain finance

# Generate code verification data
python -m realign.data.code_rlvr_generator \
  --input coding_tasks.jsonl \
  --output code_rlvr.jsonl \
  --verification-type code \
  --test-cases 3

# Generate math verification data
python -m realign.data.math_rlvr_generator \
  --input math_problems.jsonl \
  --output math_rlvr.jsonl \
  --verification-type math \
  --symbolic-validation

# Assess verifiability
python -m training_metrics assess_rlvr \
  --input rlvr.jsonl \
  --domain math \
  --threshold 0.8
```

**See**: `docs/cli-reference.md` for complete command documentation and examples.

---

## Integration with Training Workflows

This skill (DATA GENERATION) complements the training workflow skills:

| Skill | Purpose | Key Outputs |
|-------|---------|-------------|
| **dpo-rlvr-generation** (this skill) | Data generation | Preference pairs and verification data |
| **realign-dpo-workflow** | DPO training | Trained model using preference pairs |
| **realign-rlvr-workflow** | RLVR training | Trained model using verifiable rewards |

### Workflow Integration

```
1. Use dpo-rlvr-generation skill
   ↓
   Generate DPO pairs (chosen/rejected)
   Generate RLVR data (task/verification)
   ↓
   Output: dpo_pairs.jsonl, rlvr.jsonl

2. Use realign-dpo-workflow skill
   ↓
   Stage 2: Preference Data Generation (uses dpo_pairs.jsonl)
   Stages 3-7: DPO training pipeline
   ↓
   Output: DPO-aligned model

3. Use realign-rlvr-workflow skill
   ↓
   Stage 4: Verifiable Data Generation (uses rlvr.jsonl)
   Stages 5-7: RLVR training pipeline
   ↓
   Output: RLVR-aligned model
```

**Cross-reference**: See **realign-dpo-workflow** and **realign-rlvr-workflow** skills for training workflows.

---

## Best Practices

### DPO Pair Generation

1. **Clear preference signal** - Maximize quality gap (≥3.0)
2. **Diverse flaw types** - Use all 6 flaw categories
3. **Natural language** - Avoid templated rejected responses
4. **Quality validation** - Enforce thresholds rigorously
5. **Decontamination** - Remove eval benchmark overlap (≥0.9)
6. **Length diversity** - Ensure chosen is NOT always longer (≤70% ratio)
7. **Score every pair** - Apply multi-dimensional quality-scoring before training
8. **Margin over length** - Preference must be driven by quality margin, not length difference

### RLVR Data Generation

1. **High verifiability** - Target 80%+ automated verification
2. **Low false positives** - <5% incorrect rewards
3. **Diverse domains** - Balance math, code, reasoning tasks
4. **Ground truth validation** - Manually verify sample (5-10%)
5. **Test coverage** - Multiple test cases per task (3-5)

### Quality Gates

Both DPO and RLVR should enforce:
- [ ] Minimum dataset size (≥1000 examples)
- [ ] Quality thresholds met
- [ ] Decontamination validated
- [ ] Manual review sample passed (5-10%)
- [ ] Data format validated

**See**: `docs/best-practices.md` for detailed recommendations and common pitfalls.

---

## Common Issues

| Issue | Detection | Solution |
|-------|-----------|----------|
| **Weak preference signal** | Gap <3.0 | Add more intentional flaws, improve chosen quality |
| **Length bias** | >70% chosen longer | Regenerate with length-diverse pairs, score by quality not length |
| **Missing quality scores** | No chosen_score/rejected_score | Run quality-scoring skill on all pairs |
| **Low verifiability** | Score <80% | Redesign tasks, strengthen verification logic |
| **High false positives** | FP >5% | Add test cases, improve verification |
| **Insufficient data** | <1000 examples | Generate more pairs, use data augmentation |
| **Quality threshold violation** | Metrics below targets | Regenerate data, adjust generator parameters |

---

## Progressive Disclosure

This skill uses progressive disclosure to prevent context bloat:

- **Index** (this file): High-level concepts and quick reference (<300 lines)
- **Detailed docs**: `docs/*.md` files with implementation details (loaded on-demand)

**Available Documentation**:
- `docs/refusal-pair-generation.md` - RefusalDPOPairGenerator implementation
- `docs/flaw-types.md` - Complete flaw taxonomy and generation strategies
- `docs/quality-thresholds.md` - Threshold definitions and enforcement
- `docs/finance-rlvr-generation.md` - FinanceRLVRGenerator patterns
- `docs/code-verification.md` - Code sandbox setup and test generation
- `docs/math-verification.md` - Symbolic math verification patterns
- `docs/verification-types.md` - Complete verification taxonomy
- `docs/cli-reference.md` - Command documentation and examples
- `docs/best-practices.md` - Recommendations and common pitfalls

---

## Cross-References

**Related Skills**:
- **realign-dpo-workflow** - DPO training workflow (uses pairs from this skill)
- **realign-rlvr-workflow** - RLVR training workflow (uses verification data from this skill)
- **quality-scoring** - Multi-dimensional quality assessment
- **preference-data-quality** - DPO and RLVR quality metrics
- **anti-hallucination-training** - Refusal and calibration data generation

**Related Libraries**:
- `training_metrics.py` - DPO validation and RLVR verifiability functions

**Related Tools**:
- ReAlign framework - Data generation and training
- pytest - Code verification testing
- SymPy - Symbolic math verification

---

## Key Takeaways

1. **DPO generators**: RefusalDPOPairGenerator (refusal), FinanceDPOGenerator (domain-specific)
2. **RLVR generators**: FinanceRLVRGenerator, CodeRLVRGenerator, MathRLVRGenerator
3. **Flaw types**: 6 categories (risky_advice, oversimplified, incomplete, hallucinated, irrelevant, overconfident)
4. **Quality thresholds**: Chosen ≥9.0, Rejected ≤6.0, Gap ≥3.0
5. **Verification types**: math (95%+), code (90%+), custom (variable)
6. **RLVR requirements**: Verifiability ≥80%, false positives <5%
7. **Commands**: `refusal_dpo_generator`, `finance_dpo_generator`, `*_rlvr_generator`
8. **Integration**: Complements realign-dpo-workflow and realign-rlvr-workflow
9. **Validation**: Use training_metrics library functions
10. **Best practices**: Clear signal, diverse flaws, quality gates, decontamination
