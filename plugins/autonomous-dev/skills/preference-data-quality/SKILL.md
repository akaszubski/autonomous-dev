---
name: Preference Data Quality
version: 2.0.0
type: knowledge
description: DPO quality scoring, length bias detection, RLVR verification, preference pair validation
keywords: [dpo, rlvr, preference, verifiable, length-bias, quality-gap]
auto_activate: false
---

# Preference Data Quality

DPO and RLVR quality assessment with length bias detection.

## When Activates

DPO validation, RLVR assessment, preference pairs, decontamination, length bias detection

---

## Core Concepts

### DPO (Direct Preference Optimization)

Thresholds:
- Preference gap: ≥0.08 (relaxed) or ≥0.15 (strict)
- KL divergence: ≤0.1
- Decontamination: ≥0.9
- Pair count: 5K-20K (saturation point)
- Length bias ratio: ≤0.70 (max % pairs where chosen is longer)
- Quality scores: REQUIRED (chosen_score, rejected_score, margin on every pair)
- Multi-dimensional scoring: REQUIRED (quality-scoring skill must be applied)

### HARD GATE: Length Bias

**FORBIDDEN**: Training on DPO data where >70% of chosen responses are longer than rejected.

When length bias ratio is 100%, the model learns "longer = better" — a known DPO failure mode. The preference signal must come from quality margin, not length difference.

**Detection**:
```python
length_bias = sum(len(c) > len(r) for c, r in pairs) / len(pairs)
if length_bias > 0.70:
    raise ValueError(f"Length bias {length_bias:.0%} exceeds 70% threshold")
```

**Required fields per pair**: `chosen_score`, `rejected_score`, `margin`
- If these fields are missing, the data is NOT ready for training
- Run the **quality-scoring** skill to add multi-dimensional scores

### DPO Quality Scoring (Substance, NOT Length)

Score chosen/rejected independently:
- Specificity (numbers, percentages, formulas): 0-0.3
- Structure (lists, paragraphs): 0-0.2
- Vocabulary density (unique content words / total words): 0-0.3
- Completeness (proper ending punctuation): 0-0.1
- Vagueness penalty ("it depends", "various factors"): -0.1

### DPO Filtering Thresholds

| Filter | Threshold | Effect |
|--------|-----------|--------|
| Min chosen score | ≥ 0.25 | Removes low-quality chosen responses |
| Min quality gap | ≥ 0.08 | Ensures genuine preference signal |
| **Length bias** | ratio > 8x AND gap < 0.03 | Removes extreme length-only preference |
| Aggressive (risky) | gap ≥ 0.15 | Keeps only 5-10% — usually too harsh |
| **Relaxed (recommended)** | ratio > 8x filter only | Keeps ~91% — removes only worst offenders |

### DPO Saturation

- DPO saturates at **5-20K pairs** (research consensus)
- Beyond 20K: diminishing returns, risk of reward hacking
- Select top pairs by `quality_gap` score, not random sampling
- 10K quality-filtered pairs > 50K unfiltered

### RLVR (Verifiable Rewards)

Verifiability by domain:
- Math/reasoning: 100%
- Coding (test-based): 90%+
- Finance (factual): 80%+
- General knowledge: 80%+ minimum
- Creative: <80% (unsuitable for RLVR)

#### RLVR Schema Warning

Normalize schemas before mixing domains. Two common formats exist:

```json
// Format A (math/finance)
{"problem": "...", "answer": "..."}

// Format B (coding/tool_use)
{"verification_question": "...", "expected_verification": "..."}
```

Always normalize to a single format before assembling training mix.

---

## Quick Reference

| Metric | Threshold | Action |
|--------|-----------|--------|
| Preference gap | ≥ 0.08 | Filter below |
| Length ratio | ≤ 8x | Filter above if gap < 0.03 |
| Chosen score | ≥ 0.25 | Filter below |
| Length bias ratio | ≤ 0.70 | HARD GATE — block training |
| DPO total | 5-20K max | Cap (saturation point) |
| KL divergence | ≤ 0.1 | Monitor during training |
| Decontamination | ≥ 0.9 | Filter below |
| RLVR verifiable | ≥ 0.80 | Filter below |
| Empty fields | 0 tolerated | Remove all empty prompt/chosen/rejected |

---

## Progressive Disclosure

**Detailed guides**: See `docs/*.md`

- `docs/dpo-metrics.md` - DPO assessment
- `docs/rlvr-assessment.md` - RLVR verifiability
- `docs/decontamination.md` - Eval protection
- `docs/pii-protection.md` - Privacy safeguards

---

## Related

- **data-distillation** skill
- **quality-scoring** skill
- `training_metrics.py` library

---

## Key Takeaways

1. DPO gap ≥0.08 (relaxed) or ≥0.15 (strict)
2. KL ≤0.1
3. RLVR ≥80% verifiable
4. Decontaminate ≥0.9
5. **DPO saturates at 5-20K pairs** — don't use more
6. **Length bias ≤70%** (chosen longer than rejected) — HARD GATE
7. Quality scores REQUIRED on every DPO pair (chosen_score, rejected_score, margin)
8. Multi-dimensional scoring REQUIRED before training (use quality-scoring skill)
9. Score on substance (specificity, structure, vocabulary) NOT length
10. Normalize RLVR schemas across domains before mixing
