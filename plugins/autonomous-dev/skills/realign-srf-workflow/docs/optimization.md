# Stage 5: RL Fine-tuning (Optimization)

Use trained reward model to fine-tune policy with reinforcement learning.

## Overview
Apply RL (PPO/A2C) to optimize policy using learned reward model while maintaining KL constraint and entropy.

## Process
1. Initialize RL trainer (PPO recommended)
2. Configure hyperparameters (KL penalty=0.1, entropy bonus=0.01)
3. Training loop:
   - Generate responses from policy
   - Score with reward model
   - Update policy with RL
   - Apply KL penalty vs base model
4. Monitor: KL ≤0.1, entropy 0.5-2.0, reward increasing
5. Early stopping if KL exceeds threshold

## Quality Gate
- KL divergence ≤0.1
- Entropy in range 0.5-2.0
- Average reward improving

## Outputs
- RL-trained policy model
- Training metrics (KL, entropy, reward)
- Checkpoint trajectory

**See**: `../templates.md` for RL configuration examples.
