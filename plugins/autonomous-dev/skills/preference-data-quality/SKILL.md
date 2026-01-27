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
