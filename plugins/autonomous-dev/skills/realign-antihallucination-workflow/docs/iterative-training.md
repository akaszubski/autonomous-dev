# Stage 6: Iterative Training

Refine anti-hallucination training through multiple passes.

## Process
1. Evaluate factuality metrics
2. Identify hallucination patterns
3. Add targeted training data
4. Re-train with adjusted weights
5. Compare to previous iteration

## Decision
- Improving → Continue
- Stable → Proceed to evaluation
- Degrading → Rollback

**See**: `../workflow.md` for iteration strategies.
