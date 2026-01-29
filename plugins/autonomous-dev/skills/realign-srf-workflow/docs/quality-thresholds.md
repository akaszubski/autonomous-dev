# Quality Thresholds for SRF

## Core Thresholds

| Metric | Threshold | Enforcement Stage |
|--------|-----------|-------------------|
| Preference Gap | ≥0.15 | Stage 2 |
| Reward Accuracy (train) | ≥70% | Stage 3 |
| Reward Accuracy (val) | ≥70% | Stage 4 |
| Train/Val Gap | <10% | Stage 4 |
| KL Divergence | ≤0.1 | Stage 5, 7 |
| Entropy | 0.5-2.0 | Stage 5 |
| Decontamination | ≥0.9 | Stage 2 |
| Capability Retention | ≥95% | Stage 7 |

## Enforcement

Use `training_metrics.py`:
```python
from training_metrics import validate_dpo_pairs

metrics = validate_dpo_pairs(Path("pairs.jsonl"), gap_threshold=0.15)
assert metrics.avg_gap >= 0.15
```

**See**: `../workflow.md` for complete quality gate workflow.
