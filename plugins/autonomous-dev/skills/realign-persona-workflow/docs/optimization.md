# Stage 5: Optimization

Train model to maintain persona consistency.

## Overview
Fine-tune model with rewards for persona adherence.

## Process
1. Configure training with consistency rewards
2. Apply KL penalty (≤0.1)
3. Monitor:
   - Consistency score (≥85%)
   - Trait adherence (≥90%)
   - Style variance (<15%)
4. Balance persona/general examples (70/30 recommended)

## Reward Function
```python
def persona_reward(output: str, persona_profile: dict) -> float:
    eval_result = evaluate_persona_consistency(output, persona_profile)
    
    reward = (
        eval_result["consistency_score"] * 1.0 +
        sum(eval_result["trait_adherence"].values()) / len(eval_result["trait_adherence"]) * 0.5 -
        eval_result["style_variance"] * 0.5
    )
    return reward
```

## Quality Gate
- KL ≤0.1
- Consistency ≥85%
- Trait adherence ≥90%
- Style variance <15%

**See**: `../workflow.md` for complete training pipeline.
