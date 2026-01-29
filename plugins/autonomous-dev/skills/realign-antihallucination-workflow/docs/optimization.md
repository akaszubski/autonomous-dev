# Stage 5: Optimization

Train model to reduce hallucinations using factuality rewards.

## Overview
Fine-tune model with rewards based on factual accuracy.

## Process
1. Configure training with factuality rewards
2. Apply KL penalty (≤0.1)
3. Monitor:
   - Factuality score (increasing)
   - Hallucination rate (decreasing)
   - Citation accuracy (maintaining ≥85%)
4. Regular checkpoints

## Reward Function
```python
def factuality_reward(output: str) -> float:
    factuality = check_factuality(output)
    citation = check_citations(output)
    hallucination = detect_hallucinations(output)
    
    reward = (
        factuality * 1.0 +
        citation * 0.5 -
        hallucination * 2.0
    )
    return reward
```

## Quality Gate
- KL divergence ≤0.1
- Factuality improving
- Hallucination rate <10%

**See**: `../workflow.md` for complete training pipeline.
