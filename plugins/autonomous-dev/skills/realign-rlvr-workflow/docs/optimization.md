# Stage 5: RLVR Optimization

Train policy model using verifiable rewards from automated verification.

## Overview
RL training loop where reward = verification outcome (pass/fail).

## Process

1. Configure RL (PPO recommended)
2. Training loop:
   - Sample task
   - Generate solution from policy
   - Verify outcome → reward
   - Update policy with RL
   - Apply KL penalty
3. Monitor KL ≤0.1, verification success rate

## Configuration

```python
rlvr_config = {
    "algorithm": "PPO",
    "learning_rate": 1e-6,
    "kl_penalty": 0.1,
    "reward_correct": 1.0,
    "reward_incorrect": 0.0
}
```

## Quality Gate
- KL divergence ≤0.1
- Verification success rate improving
- No reward gaming detected

**See**: `../templates.md` for complete RLVR training configuration.
