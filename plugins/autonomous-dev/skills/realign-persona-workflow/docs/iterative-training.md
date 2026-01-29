# Stage 6: Iterative Training

Refine persona consistency through multiple passes.

## Process
1. Evaluate current persona metrics
2. Identify trait gaps or inconsistencies
3. Add targeted examples
4. Re-train with adjusted weights
5. Compare to previous iteration

## Decision
- Improving → Continue
- Stable → Proceed to evaluation
- Degrading → Rollback

**See**: `../workflow.md` for iteration strategies.
