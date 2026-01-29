# Stage 6: Iterative Training

Refine model through multiple RL passes.

## Overview
Improve model by iterating on data, reward model, or hyperparameters.

## Process
1. Evaluate current model
2. Identify weaknesses
3. Options:
   - Collect new preference data
   - Retrain reward model
   - Adjust RL hyperparameters
4. Run another RL pass
5. Compare to previous iteration
6. Repeat until convergence

## Decision Points
- Improving → Continue
- Degrading → Rollback
- Stable → Proceed to evaluation

**See**: `../workflow.md` for iteration strategies.
