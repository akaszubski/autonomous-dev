# Capability Assessment & Regression Detection

## Detection Methods

1. **Baseline Comparison**
   - Compare final model to pre-SRF baseline
   - Threshold: ≥95% retention on all benchmarks

2. **Benchmark Tracking**
   - MMLU, HumanEval, GSM8K
   - Domain-specific benchmarks

3. **Reward Analysis**
   - Check reward model consistency
   - Identify capability-reward trade-offs

## Prevention Strategies

- Small KL constraint (≤0.1)
- Entropy monitoring (0.5-2.0)
- Gradual reward scaling
- Regular checkpoints

## Rollback Criteria

- Capability drop >5%
- KL divergence >0.1
- Entropy outside range

**See**: `../workflow.md` for rollback procedures.
