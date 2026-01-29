---
name: realign-srf-workflow
version: 1.0.0
type: knowledge
description: Complete SRF (Supervised Reward Fine-tuning) workflow for model realignment. Guides practitioners through 7 stages from SFT preparation to evaluation with quality thresholds, reward model accuracy validation, and integration with preference-data-quality skill.
keywords: [srf, srft, supervised reward, reward model, rl fine-tuning, model alignment, reward learning, reinforcement learning, capability regression]
auto_activate: true
allowed-tools: [Read, Grep, Glob, Bash, Write]
---

# Realign SRF Workflow Skill

Complete workflow for Supervised Reward Fine-tuning (SRF) model realignment with explicit reward model training and RL fine-tuning.

## When This Skill Activates

- Planning SRF training workflows
- Implementing reward model-based alignment
- Validating reward model accuracy metrics
- Detecting capability regression during RL fine-tuning
- Keywords: "srf", "supervised reward", "reward model", "rl fine-tuning", "reward learning"

---

## Core Principle

**Explicit reward model provides interpretable feedback for RL fine-tuning.**

- SRF separates reward learning from policy optimization
- Reward model accuracy directly impacts alignment quality
- RL fine-tuning uses learned rewards with KL constraints
- Quality thresholds prevent capability degradation

---

## 7-Stage SRF Pipeline

| Stage | Name | Key Output | Quality Gate |
|-------|------|------------|--------------|
| 1 | SFT Preparation | Base model | Baseline metrics established |
| 2 | Preference Data Generation | Preference pairs | Gap ≥0.15, pairs ≥1000 |
| 3 | Reward Model Training | Reward model | Accuracy ≥70% |
| 4 | Reward Model Validation | Validated reward | Val accuracy ≥70%, no overfit |
| 5 | RL Fine-tuning | Aligned model | KL ≤0.1, entropy 0.5-2.0 |
| 6 | Iterative Training | Refined model | Metrics improving |
| 7 | Evaluation & Monitoring | Validated model | No capability regression |

**See**: `workflow.md` for detailed stage-by-stage instructions.

---

## Quality Thresholds

Critical metrics that must be met for SRF success:

| Metric | Threshold | Purpose |
|--------|-----------|---------|
| **Reward Model Accuracy** | ≥70% | Ensures reliable preference prediction |
| **KL Divergence** | ≤0.1 | Prevents drift from base model |
| **Entropy Range** | 0.5-2.0 | Maintains output diversity |
| **Decontamination** | ≥0.9 | Prevents eval leakage |
| **Capability Retention** | ≥95% | No regression on benchmarks |

**See**: `docs/quality-thresholds.md` for detailed threshold definitions and enforcement strategies.

---

## Integration with preference-data-quality Skill

This skill integrates with the **preference-data-quality** skill for SRF metric validation:

- Preference gap calculation (≥0.15)
- KL divergence monitoring (≤0.1)
- Decontamination checks (≥0.9)
- Reward model accuracy tracking

Use `training_metrics.py` library functions:
- `validate_dpo_pairs()` - Validate preference pairs and check gap threshold
- `assess_rlvr_verifiability()` - Check reward verifiability (if applicable)
- `calculate_ifd_score()` - Instruction-following difficulty

**See**: `docs/preference-data-generation.md` for integration details.

---

## Quick Start Checklist

### Pre-SRF Checklist
- [ ] Base model SFT trained and validated
- [ ] Baseline capability metrics recorded
- [ ] Preference data collection plan defined
- [ ] Quality thresholds understood
- [ ] Reward model architecture selected

### During SRF Checklist
- [ ] Preference pairs validated (gap ≥0.15)
- [ ] Reward model trained (accuracy ≥70%)
- [ ] RL fine-tuning monitored (KL ≤0.1, entropy 0.5-2.0)
- [ ] Capability benchmarks tracked
- [ ] Quality gates enforced

### Post-SRF Checklist
- [ ] Final model meets all quality thresholds
- [ ] No capability regression detected
- [ ] Model outperforms baseline on alignment
- [ ] Reward model interpretable
- [ ] Documentation complete

**See**: `templates.md` for detailed checklists and configuration templates.

---

## Capability Regression Detection

Critical for ensuring SRF improves alignment without degrading capabilities:

**Detection Methods**:
1. Baseline comparison - Compare to pre-SRF metrics
2. Benchmark tracking - Monitor standard benchmarks
3. Task-specific evaluation - Test domain capabilities
4. Reward model analysis - Validate reward consistency

**Prevention Strategies**:
- Small KL divergence constraint (≤0.1)
- Entropy monitoring (0.5-2.0 range)
- Gradual reward scaling
- Regular capability checkpoints

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
| **Low reward accuracy** | Accuracy <70% | Improve data quality, increase model capacity |
| **Model drift** | KL >0.1 | Reduce learning rate, strengthen KL penalty |
| **Entropy collapse** | Entropy <0.5 | Reduce reward scale, add entropy bonus |
| **Capability loss** | Benchmark drop >5% | Rollback, adjust hyperparameters, add capability data |
| **Reward overfitting** | Train/val gap >10% | Regularization, more diverse data |

---

## Progressive Disclosure

This skill uses progressive disclosure to prevent context bloat:

- **Index** (this file): High-level workflow overview and quick reference (<500 lines)
- **Workflow**: `workflow.md` - Complete 7-stage pipeline with decision points
- **Templates**: `templates.md` - Checklists and configuration examples
- **Detailed docs**: `docs/*.md` files - Stage-specific implementation details (loaded on-demand)

**Available Documentation**:
- `workflow.md` - Complete 7-stage SRF workflow
- `templates.md` - Checklists and configuration templates
- `docs/sft-preparation.md` - Stage 1: Base model preparation
- `docs/preference-data-generation.md` - Stage 2: Creating preference pairs
- `docs/reward-model-training.md` - Stage 3: Training reward model
- `docs/reward-model-validation.md` - Stage 4: Validating reward model
- `docs/optimization.md` - Stage 5: RL fine-tuning loop
- `docs/iterative-training.md` - Stage 6: Refinement iterations
- `docs/evaluation-monitoring.md` - Stage 7: Final validation
- `docs/quality-thresholds.md` - Threshold definitions and enforcement
- `docs/capability-assessment.md` - Regression detection methods

---

## Cross-References

**Related Skills**:
- **preference-data-quality** - SRF quality metrics (gap, KL, decontamination)
- **realign-dpo-workflow** - Alternative alignment approach (implicit rewards)
- **data-distillation** - Data generation and augmentation
- **scientific-validation** - Experimental validation methodology

**Related Libraries**:
- `training_metrics.py` - SRF validation functions

**Related Tools**:
- HuggingFace TRL library - RL fine-tuning implementation
- Weights & Biases - Training monitoring
- PyTorch - Model training

---

## Key Principles

1. **Explicit reward model** - Interpretable, separate from policy
2. **Reward accuracy matters** - Low accuracy → poor alignment
3. **KL constraint critical** - Prevents drift from base model (≤0.1)
4. **Entropy monitoring** - Maintains output diversity (0.5-2.0)
5. **Iterative refinement** - Multiple passes improve results
6. **Quality gates** - Enforce thresholds between stages
7. **Capability regression is critical** - Monitor benchmarks continuously
8. **Decontamination is mandatory** - Prevent eval leakage (≥0.9)

---

## Key Takeaways

1. **7 stages**: SFT → Preference Data → Reward Training → Reward Validation → RL Fine-tuning → Iteration → Evaluation
2. **Quality thresholds**: Reward accuracy ≥70%, KL ≤0.1, entropy 0.5-2.0, decontamination ≥0.9
3. **Capability regression**: Monitor benchmarks, detect drops >5%, prevent with small KL
4. **Reward model**: Separate training enables interpretability and debugging
5. **Integration**: Use preference-data-quality skill and training_metrics.py
6. **Progressive disclosure**: See workflow.md and docs/*.md for details
7. **RL fine-tuning**: Uses learned rewards with KL penalty and entropy bonus
8. **Quality gates**: Enforce thresholds between stages
