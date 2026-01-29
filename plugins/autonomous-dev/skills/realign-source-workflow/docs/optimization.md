# Stage 5: Optimization

Train model to improve source attribution.

## Overview
Fine-tune model with rewards for proper citation.

## Process
1. Configure training with citation rewards
2. Apply KL penalty (≤0.1)
3. Monitor:
   - Citation accuracy (≥90%)
   - Attribution coverage (≥80%)
   - Retrieval precision (≥85%)
4. Balance citation/general examples

## Reward Function
```python
def citation_reward(output: str, knowledge_base) -> float:
    eval_result = evaluate_source_attribution(output, knowledge_base)
    
    reward = (
        eval_result["citation_accuracy"] * 1.0 +
        eval_result["attribution_coverage"] * 0.5 +
        eval_result["retrieval_precision"] * 0.5
    )
    return reward
```

## Quality Gate
- KL ≤0.1
- Citation accuracy ≥90%
- Attribution coverage ≥80%

**See**: `../workflow.md` for complete training pipeline.
