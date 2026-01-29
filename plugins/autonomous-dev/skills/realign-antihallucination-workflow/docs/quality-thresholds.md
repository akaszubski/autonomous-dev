# Quality Thresholds for Anti-hallucination

| Metric | Threshold | Stage |
|--------|-----------|-------|
| Citation Accuracy | ≥85% | 2 |
| Factuality Score | ≥90% | 3 |
| Hallucination Rate | <10% | 4, 5, 7 |
| KL Divergence | ≤0.1 | 5, 7 |
| Capability Retention | ≥95% | 7 |

## Enforcement
Monitor continuously, enforce at quality gates.

**See**: `../workflow.md` for complete enforcement workflow.
