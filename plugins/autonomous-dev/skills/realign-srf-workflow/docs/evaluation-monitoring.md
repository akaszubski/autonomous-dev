# Stage 7: Evaluation & Monitoring

Validate final model meets quality thresholds without capability regression.

## Overview
Comprehensive evaluation of alignment and capability retention.

## Process
1. Run capability benchmarks (MMLU, HumanEval, GSM8K)
2. Compare to baseline: capability_retention = (final/baseline) * 100
3. Must be ≥95% retention
4. Evaluate alignment:
   - Win rate vs baseline
   - Reward model scores
   - Human evaluation
5. Analyze reward interpretability

## Success Criteria
- ✅ Capability retention ≥95%
- ✅ Alignment improved
- ✅ All quality thresholds met
- ✅ Reward model interpretable

**See**: `capability-assessment.md` for regression detection methods.
