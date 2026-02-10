---
name: Preference Data Quality
version: 1.0.0
type: knowledge
description: DPO and RLVR quality metrics
keywords: [dpo, rlvr, preference, verifiable]
auto_activate: true
---

# Preference Data Quality

DPO and RLVR quality assessment.

## When Activates

DPO validation, RLVR assessment, preference pairs, decontamination

---

## Core Concepts

### DPO (Direct Preference Optimization)

Thresholds:
- Preference gap: ≥0.15
- KL divergence: ≤0.1
- Decontamination: ≥0.9
- Pair count: ≥100
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

### RLVR (Verifiable Rewards)

Verifiability by domain:
- Math/reasoning: 100%
- Coding: 90%+
- General: 80%+ minimum
- Creative: <80% (unsuitable)

---

## Quick Reference

| Metric | Threshold |
|--------|-----------|
| Preference gap | ≥0.15 |
| KL divergence | ≤0.1 |
| Decontamination | ≥0.9 |
| RLVR verifiable | ≥0.8 |
| Length bias ratio | ≤0.70 |
| Quality scores | Required on every pair |

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
- `training_metrics.py` library

---

## Key Takeaways

1. DPO gap ≥0.15
2. KL ≤0.1
3. RLVR ≥80% verifiable
4. Decontaminate ≥0.9
5. Min 100 pairs
6. Length bias ≤70% (chosen longer than rejected)
7. Quality scores REQUIRED on every DPO pair (chosen_score, rejected_score, margin)
8. Multi-dimensional scoring REQUIRED before training (use quality-scoring skill)
