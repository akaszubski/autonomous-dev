# Quality Thresholds for RLVR

| Metric | Threshold | Stage |
|--------|-----------|-------|
| Verifiability Score | ≥80% | 2 |
| False Positive Rate | <5% | 3 |
| KL Divergence | ≤0.1 | 5, 7 |
| Capability Retention | ≥95% | 7 |

## Enforcement

```python
from training_metrics import assess_rlvr_verifiability

# Stage 2
verifiability = assess_rlvr_verifiability(tasks)
assert verifiability >= 0.80

# Stage 5
assert kl_divergence <= 0.1
```

**See**: `../workflow.md` for complete enforcement workflow.
