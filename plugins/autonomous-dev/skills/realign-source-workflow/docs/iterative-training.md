# Stage 6: Iterative Training

Refine source attribution through multiple passes.

## Process
1. Evaluate current citation metrics
2. Identify attribution gaps
3. Add targeted citation examples
4. Re-train with adjusted weights
5. Compare to previous iteration

## Decision
- Improving → Continue
- Stable → Proceed to evaluation
- Degrading → Rollback

**See**: `../workflow.md` for iteration strategies.
