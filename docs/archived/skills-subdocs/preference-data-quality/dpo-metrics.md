# DPO (Direct Preference Optimization) Metrics

Quality assessment for preference pairs used in DPO training.

## Overview

DPO trains models by learning from preference pairs (chosen vs rejected responses). Quality metrics ensure effective learning.

## Core Metrics

### 1. Preference Gap (≥0.15)

**Definition**: Score difference between chosen and rejected responses

```python
preference_gap = score(chosen) - score(rejected)
```

**Why it matters**:
- Gap too small (<0.15): Model can't learn clear preferences
- Gap too large (>0.5): May indicate annotation errors
- Optimal range: 0.15-0.4

**Quality issues**:
- `INSUFFICIENT_GAP`: Gap <0.15, pairs too similar

### 2. KL Divergence (≤0.1)

**Definition**: Distance from reference model distribution

**Why it matters**:
- Low divergence (≤0.1): Model stays aligned with reference
- High divergence (>0.1): Risk of mode collapse or misalignment

**Quality issues**:
- `HIGH_KL_DIVERGENCE`: Divergence >0.1, alignment risk

### 3. Decontamination Score (≥0.9)

**Definition**: Percentage of training data not in eval set

```python
decontamination_score = 1.0 - (overlap_count / total_pairs)
```

**Why it matters**:
- High score (≥0.9): Clean separation from eval
- Low score (<0.9): Eval contamination, inflated metrics

**Quality issues**:
- `CONTAMINATION_RISK`: Score <0.9, eval leakage detected

### 4. Pair Count (≥100)

**Definition**: Total number of preference pairs

**Why it matters**:
- Too few (<100): Unstable training, poor generalization
- Optimal: 1,000-10,000 pairs for robust learning

**Quality issues**:
- `INSUFFICIENT_PAIRS`: Count <100, statistical instability

## Implementation

### Using training_metrics.py

```python
from pathlib import Path
from training_metrics import validate_dpo_pairs

# Validate DPO pairs
dpo_path = Path("data/dpo_pairs.jsonl")
metrics = validate_dpo_pairs(dpo_path)

# Check quality
if metrics.is_valid:
    print("DPO pairs ready for training")
else:
    print(f"Quality issues: {metrics.quality_issues}")

# Print metrics
print(f"Preference gap: {metrics.preference_gap:.3f}")
print(f"KL divergence: {metrics.kl_divergence:.3f}")
print(f"Decontamination: {metrics.decontamination_score:.3f}")
print(f"Pair count: {metrics.pair_count}")
```

### Dataset Format

JSONL with prompt/chosen/rejected triples:

```jsonl
{"prompt": "Explain Python", "chosen": "Python is...", "rejected": "Idk"}
{"prompt": "Sort algorithm", "chosen": "Use quicksort", "rejected": "Use bubblesort"}
```

## Best Practices

1. **Filter by gap**: Remove pairs with gap <0.15
2. **Monitor KL**: Track divergence during training
3. **Decontaminate**: Remove eval overlaps before training
4. **Collect more pairs**: Aim for 1,000+ for stability

## Common Issues

| Issue | Symptom | Solution |
|-------|---------|----------|
| Insufficient gap | Model doesn't learn | Filter pairs, collect clearer preferences |
| High KL | Misalignment | Reduce learning rate, add KL penalty |
| Contamination | Inflated eval metrics | Decontaminate training set |
| Too few pairs | Unstable training | Collect more preference data |

## Related

- See `training_metrics.py` for implementation
- See `decontamination.md` for eval protection
- See `rlvr-assessment.md` for verifiable rewards
