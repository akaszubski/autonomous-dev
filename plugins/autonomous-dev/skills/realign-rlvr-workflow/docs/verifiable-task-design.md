# Stage 2: Verifiable Task Design

Create tasks with automated, objective verification.

## Overview
Design tasks where success can be automatically verified without human judgment.

## Verifiable Domains

**Coding Tasks**:
- Solution passes unit tests
- Code executes without errors
- Output matches expected

**Math Tasks**:
- Answer equals ground truth (symbolic)
- Proof validates formally
- Calculation correct

**Formal Reasoning**:
- Logical argument valid
- Deduction follows rules
- Conclusion provable

## Process

1. **Select Domain**: Choose objectively verifiable domain
2. **Design Task Format**: Clear prompt, expected outcome
3. **Implement Verification**: Automated checking function
4. **Validate Verifiability**: Use `assess_rlvr_verifiability()` from training_metrics.py

```python
from training_metrics import assess_rlvr_verifiability

verifiability_score = assess_rlvr_verifiability(task_suite)
assert verifiability_score >= 0.80
```

## Quality Gate
- Verifiability score ≥80%
- Clear success criteria
- Automated verification implemented

**See**: `../templates.md` for task format examples.
