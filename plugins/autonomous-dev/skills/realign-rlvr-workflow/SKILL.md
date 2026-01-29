---
name: realign-rlvr-workflow
version: 1.0.0
type: knowledge
description: Complete RLVR (Reinforcement Learning with Verifiable Rewards) workflow for model realignment. Guides practitioners through 7 stages using automated verification as reward signal with quality thresholds and verifiability scoring.
keywords: [rlvr, verifiable rewards, formal verification, outcome verification, rl fine-tuning, automated verification, model alignment, capability regression]
auto_activate: true
allowed-tools: [Read, Grep, Glob, Bash, Write]
---

# Realign RLVR Workflow Skill

Complete workflow for Reinforcement Learning with Verifiable Rewards (RLVR) model realignment using automated outcome verification.

## When This Skill Activates

- Planning RLVR training workflows
- Implementing verifiable reward-based alignment
- Validating outcome verification systems
- Detecting capability regression during RLVR
- Keywords: "rlvr", "verifiable rewards", "automated verification", "outcome verification", "formal verification"

---

## Core Principle

**Automated verification provides objective, scalable reward signal.**

- RLVR uses verifiable outcomes (test pass, proof valid, output correct)
- No human annotation needed for rewards
- Eliminates reward model training overhead
- Ideal for coding, math, formal reasoning tasks

---

## 7-Stage RLVR Pipeline

| Stage | Name | Key Output | Quality Gate |
|-------|------|------------|--------------|
| 1 | SFT Preparation | Base model | Baseline metrics established |
| 2 | Verifiable Task Design | Task suite | Verifiability ≥80% |
| 3 | Automated Verification | Verification system | False positive rate <5% |
| 4 | Verifiable Data Generation | Training tasks | Task coverage validated |
| 5 | RLVR Optimization | Aligned model | KL ≤0.1, verify rate improving |
| 6 | Iterative Training | Refined model | Metrics improving |
| 7 | Evaluation & Monitoring | Validated model | No capability regression |

**See**: `workflow.md` for detailed stage-by-stage instructions.

---

## Quality Thresholds

Critical metrics that must be met for RLVR success:

| Metric | Threshold | Purpose |
|--------|-----------|---------|
| **Verifiability Score** | ≥80% | Ensures outcomes can be automatically verified |
| **False Positive Rate** | <5% | Prevents incorrect rewards |
| **KL Divergence** | ≤0.1 | Prevents drift from base model |
| **Verification Success Rate** | Improving | Training effectiveness |
| **Capability Retention** | ≥95% | No regression on benchmarks |

**See**: `docs/quality-thresholds.md` for detailed threshold definitions and enforcement strategies.

---

## Integration with preference-data-quality Skill

This skill integrates with the **preference-data-quality** skill for RLVR metric validation:

- RLVR verifiability assessment
- KL divergence monitoring (≤0.1)
- Verification quality tracking

Use `training_metrics.py` library functions:
- `assess_rlvr_verifiability()` - Check reward verifiability score
- `validate_dpo_pairs()` - KL divergence validation (if using paired examples)
- `calculate_ifd_score()` - Instruction-following difficulty

**See**: `docs/verifiable-task-design.md` for integration details.

---

## Quick Start Checklist

### Pre-RLVR Checklist
- [ ] Base model SFT trained and validated
- [ ] Baseline capability metrics recorded
- [ ] Verifiable task domain selected (coding, math, etc.)
- [ ] Automated verification system implemented
- [ ] Quality thresholds understood

### During RLVR Checklist
- [ ] Task verifiability validated (≥80%)
- [ ] Verification system tested (false positive <5%)
- [ ] RLVR training monitored (KL ≤0.1)
- [ ] Verification success rate tracked
- [ ] Quality gates enforced

### Post-RLVR Checklist
- [ ] Final model meets all quality thresholds
- [ ] No capability regression detected
- [ ] Model outperforms baseline on verified tasks
- [ ] Verification system documented
- [ ] Deployment ready

**See**: `templates.md` for detailed checklists and configuration templates.

---

## Capability Regression Detection

Critical for ensuring RLVR improves task performance without degrading capabilities:

**Detection Methods**:
1. Baseline comparison - Compare to pre-RLVR metrics
2. Benchmark tracking - Monitor standard benchmarks
3. Verification analysis - Track false positive/negative rates
4. Task-specific evaluation - Test domain capabilities

**Prevention Strategies**:
- Small KL divergence constraint (≤0.1)
- Diverse task distribution
- Regular capability checkpoints
- Balanced verification difficulty

**See**: `docs/capability-assessment.md` for detailed regression detection workflows.

---

---

## Performance Optimization (CRITICAL - Claude Always Forgets)

MLX-specific hardware selection, batch sizing, and distributed training decisions for ReAlign workflows.

### Machine Selection (Validated Benchmarks)
**Measured GFLOPS performance**:
- M4 Max: 12,956 GFLOPS (324 per core)
- M3 Ultra: 4,599 GFLOPS (57 per core)
- Real scoring: M4 Max 3.86 ex/s vs M3 Ultra 0.76 ex/s (5.1x faster)

**Decision Matrix**:
| Model Size | Machine | Rationale |
|------------|---------|-----------|
| ≤30B | M4 Max | 1.9x faster than M3 Ultra |
| 30-70B | M4 Max | Faster unless >128GB memory needed |
| 70B+ | M3 Ultra | Requires 512GB memory |

### Batch Size Configuration
**Empirically validated optimal batch sizes**:
- M4 Max: `batch_size=32` (optimal peak throughput)
- M3 Ultra: `batch_size=4` (peaks early, DON'T increase)

**Anti-Pattern**: DO NOT use batch_size=32 on M3 Ultra (wastes compute)

### RDMA vs Separate Batches Decision

**USE RDMA WHEN**:
| Scenario | Why |
|----------|-----|
| Model > 128GB (70B+ fp16) | Model doesn't fit on one machine |
| Model > 512GB (405B) | Must shard across machines |
| Training with gradient sync | Need synchronized weight updates |

**USE SEPARATE BATCHES WHEN**:
| Scenario | Why |
|----------|-----|
| Model fits on one machine | No coordination overhead |
| Independent scoring/eval | Each machine works at own pace |
| ReAlign curation | Combined throughput = M4 + M3 |

### Work Distribution (Distributed Training)
- **DO**: Split 65.5% to M4 Max, 34.5% to M3 Ultra (proportional to throughput)
- **DON'T**: Split 50/50 based on GPU cores (wastes days on slower machine)

### Required Environment Variables
```bash
export MLX_METAL_PREALLOCATE=1
export MLX_METAL_FAST_SYNCH=1
export TOKENIZERS_PARALLELISM=false
sudo nice -n -10 realign curate ...
```

**See**: `docs/performance-optimization.md` for detailed benchmarks and configuration examples.

**Cross-References**:
- **mlx-performance** skill - MLX distributed training, RDMA, FlashRecovery
- `hardware_calibrator.py` library - Empirical benchmarking and workload distribution


## Common Issues

| Issue | Detection | Solution |
|-------|-----------|----------|
| **Low verifiability** | Score <80% | Redesign tasks, improve verification system |
| **High false positives** | FP >5% | Strengthen verification logic, add test cases |
| **Model drift** | KL >0.1 | Reduce learning rate, strengthen KL penalty |
| **Verification gaming** | Success without quality | Add diverse test cases, multi-faceted verification |
| **Capability loss** | Benchmark drop >5% | Rollback, adjust task distribution |

---

## Progressive Disclosure

This skill uses progressive disclosure to prevent context bloat:

- **Index** (this file): High-level workflow overview and quick reference (<500 lines)
- **Workflow**: `workflow.md` - Complete 7-stage pipeline with decision points
- **Templates**: `templates.md` - Checklists and configuration examples
- **Detailed docs**: `docs/*.md` files - Stage-specific implementation details (loaded on-demand)

**Available Documentation**:
- `workflow.md` - Complete 7-stage RLVR workflow
- `templates.md` - Checklists and configuration templates
- `docs/sft-preparation.md` - Stage 1: Base model preparation
- `docs/verifiable-task-design.md` - Stage 2: Creating verifiable tasks
- `docs/automated-verification.md` - Stage 3: Verification system setup
- `docs/preference-data-generation.md` - Stage 4: Task data generation
- `docs/optimization.md` - Stage 5: RLVR training loop
- `docs/iterative-training.md` - Stage 6: Refinement iterations
- `docs/evaluation-monitoring.md` - Stage 7: Final validation
- `docs/quality-thresholds.md` - Threshold definitions and enforcement
- `docs/capability-assessment.md` - Regression detection methods

---

## Cross-References

**Related Skills**:
- **preference-data-quality** - RLVR verifiability metrics
- **realign-dpo-workflow** - Alternative alignment approach (preference-based)
- **realign-srf-workflow** - Alternative RL approach (learned rewards)
- **scientific-validation** - Experimental validation methodology

**Related Libraries**:
- `training_metrics.py` - RLVR validation functions

**Related Tools**:
- HuggingFace TRL library - RL fine-tuning implementation
- pytest - Verification for coding tasks
- SymPy - Verification for math tasks
- Weights & Biases - Training monitoring

---

## Key Principles

1. **Verifiable outcomes** - Rewards must be automatically and objectively verifiable
2. **Low false positives** - Incorrect rewards corrupt training (<5% threshold)
3. **Task diversity** - Wide range prevents overfitting to specific patterns
4. **KL constraint critical** - Prevents drift from base model (≤0.1)
5. **Scalability** - No human annotation required
6. **Quality gates** - Enforce thresholds between stages
7. **Capability regression is critical** - Monitor benchmarks continuously
8. **Verification transparency** - Clear why tasks pass/fail

---

## Key Takeaways

1. **7 stages**: SFT → Task Design → Verification → Data → RLVR → Iteration → Evaluation
2. **Quality thresholds**: Verifiability ≥80%, false positive <5%, KL ≤0.1
3. **Capability regression**: Monitor benchmarks, detect drops >5%, prevent with small KL
4. **Automated rewards**: No human annotation, scalable to large datasets
5. **Integration**: Use preference-data-quality skill and training_metrics.py
6. **Progressive disclosure**: See workflow.md and docs/*.md for details
7. **Best domains**: Coding, math, formal reasoning (objective verification)
8. **Quality gates**: Enforce thresholds between stages
