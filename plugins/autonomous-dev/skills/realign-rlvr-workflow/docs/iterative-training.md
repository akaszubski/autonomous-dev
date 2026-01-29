# Stage 6: Iterative Training

Refine model through multiple RLVR passes.

## Process
1. Evaluate current model on verification tasks
2. Identify failure patterns
3. Add more diverse tasks or adjust hyperparameters
4. Run another RLVR pass
5. Compare metrics

## Decision
- Improving → Continue
- Stable → Proceed to evaluation
- Degrading → Rollback

**See**: `../workflow.md` for iteration strategies.
