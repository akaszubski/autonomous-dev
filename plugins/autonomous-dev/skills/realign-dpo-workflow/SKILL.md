---
name: realign-dpo-workflow
version: 1.0.0
type: knowledge
description: Complete DPO (Direct Preference Optimization) workflow for model realignment. Guides practitioners through 7 stages from SFT preparation to evaluation with quality thresholds, capability regression detection, and integration with preference-data-quality skill.
keywords: [dpo, preference, realign, rlhf, direct preference optimization, model alignment, preference optimization, preference data, preference modeling, capability regression]
auto_activate: true
allowed-tools: [Read, Grep, Glob, Bash, Write]
---

# Realign DPO Workflow Skill

Complete workflow for Direct Preference Optimization (DPO) model realignment with quality thresholds and capability regression detection.

## When This Skill Activates

- Planning DPO training workflows
- Implementing preference-based model alignment
- Validating DPO quality metrics
- Detecting capability regression during alignment
- Keywords: "dpo", "preference optimization", "realignment", "rlhf", "direct preference", "model alignment"

---

## Core Principle

**Quality gates at every stage prevent capability regression.**

- DPO can improve alignment but degrade capabilities
- Quality thresholds enforce minimum standards
- Capability assessment detects performance loss
- Iterative refinement recovers from failures

---

## 7-Stage DPO Pipeline

| Stage | Name | Key Output | Quality Gate |
|-------|------|------------|--------------|
| 1 | SFT Preparation | Base model | Baseline metrics established |
| 2 | Preference Data Generation | Preference pairs | Gap ≥0.15, pairs ≥1000 |
| 3 | Model Initialization | Reference model | KL divergence calculated |
| 4 | Preference Modeling | Reward model | Accuracy ≥70% |
| 5 | DPO Optimization | Aligned model | KL ≤0.1, gap maintained |
| 6 | Iterative Training | Refined model | Metrics improving |
| 7 | Evaluation & Monitoring | Validated model | No capability regression |

**See**: `workflow.md` for detailed stage-by-stage instructions.

---

## Quality Thresholds

Critical metrics that must be met for DPO success:

| Metric | Threshold | Purpose |
|--------|-----------|---------|
| **Preference Gap** | ≥0.15 | Ensures clear preference signal |
| **KL Divergence** | ≤0.1 | Prevents drift from base model |
| **Minimum Pairs** | ≥1000 | Adequate training data |
| **Decontamination** | ≥0.9 | Prevents eval leakage |
| **Capability Retention** | ≥95% | No regression on benchmarks |

**See**: `docs/quality-thresholds.md` for detailed threshold definitions and enforcement strategies.

---

## Integration with preference-data-quality Skill

This skill integrates with the **preference-data-quality** skill for DPO metric validation:

- Preference gap calculation (≥0.15)
- KL divergence monitoring (≤0.1)
- Decontamination checks (≥0.9)
- Data quality validation

Use `training_metrics.py` library functions:
- `validate_dpo_pairs()` - Validate preference pairs and check gap threshold
- `assess_rlvr_verifiability()` - Check reward verifiability
- `calculate_ifd_score()` - Instruction-following difficulty

**See**: `docs/preference-data-generation.md` for integration details.

---

## Quick Start Checklist

### Pre-DPO Checklist
- [ ] Base model SFT trained and validated
- [ ] Baseline capability metrics recorded
- [ ] Preference data collection plan defined
- [ ] Quality thresholds understood
- [ ] Evaluation benchmarks selected

### During DPO Checklist
- [ ] Preference pairs validated (gap ≥0.15)
- [ ] KL divergence monitored (≤0.1)
- [ ] Capability benchmarks tracked
- [ ] Training metrics logged
- [ ] Quality gates enforced

### Post-DPO Checklist
- [ ] Final model meets all quality thresholds
- [ ] No capability regression detected
- [ ] Model outperforms baseline on alignment
- [ ] Documentation complete
- [ ] Deployment ready

**See**: `templates.md` for detailed checklists and configuration templates.

---

## Capability Regression Detection

Critical for ensuring DPO improves alignment without degrading capabilities:

**Detection Methods**:
1. Baseline comparison - Compare to pre-DPO metrics
2. Benchmark tracking - Monitor standard benchmarks
3. Task-specific evaluation - Test domain capabilities
4. Human evaluation - Qualitative assessment

**Prevention Strategies**:
- Small KL divergence constraint (≤0.1)
- Gradual preference strength increase
- Multi-stage iterative refinement
- Regular capability checkpoints

**See**: `docs/capability-assessment.md` for detailed regression detection workflows.

---

## Performance Optimization

Hardware-specific optimization critical for DPO training efficiency. Proper configuration achieves 5x speedup.

**Machine Selection** (by model size):
- ≤30B: M4 Max (5.1x faster than M3 Ultra)
- 30-70B: M4 Max preferred (faster unless need >128GB memory)
- 70-200B: M3 Ultra (requires 512GB memory)
- 200B+: Distributed across both machines

**Batch Size Configuration**:
- M4 Max: batch_size=32 (peaks at 776 ex/s)
- M3 Ultra: batch_size=4 (peaks early, DO NOT increase)

**Work Distribution** (if distributed):
- M4 Max: 65.5% of work (M4_RATIO = 0.655)
- M3 Ultra: 34.5% of work (M3_RATIO = 0.345)
- Anti-pattern: DO NOT split 50/50 based on GPU cores

**Environment Setup**:
```bash
export MLX_METAL_PREALLOCATE=1
export MLX_METAL_FAST_SYNCH=1
export TOKENIZERS_PARALLELISM=false
sudo nice -n -10 python train_dpo.py ...
```

**Integration**:
- Use `hardware_calibrator.py` library for automatic hardware detection
- Reference `mlx-performance` skill for advanced optimization

**See**: `docs/performance-optimization.md` for complete hardware-specific guidance.

---

## Common Issues

| Issue | Detection | Solution |
|-------|-----------|----------|
| **Weak preference signal** | Gap below minimum | Collect more diverse examples, improve prompt quality |
| **Model drift** | KL >0.1 | Reduce learning rate, strengthen KL penalty |
| **Capability loss** | Benchmark drop >5% | Rollback, adjust hyperparameters, add capability data |
| **Insufficient data** | Pairs <1000 | Generate more pairs, use data augmentation |
| **Preference conflicts** | Low accuracy | Review annotation quality, resolve conflicts |

---

## Progressive Disclosure

This skill uses progressive disclosure to prevent context bloat:

- **Index** (this file): High-level workflow overview and quick reference (<500 lines)
- **Workflow**: `workflow.md` - Complete 7-stage pipeline with decision points
- **Templates**: `templates.md` - Checklists and configuration examples
- **Detailed docs**: `docs/*.md` files - Stage-specific implementation details (loaded on-demand)

**Available Documentation**:
- `workflow.md` - Complete 7-stage DPO workflow
- `templates.md` - Checklists and configuration templates
- `docs/sft-preparation.md` - Stage 1: Base model preparation
- `docs/preference-data-generation.md` - Stage 2: Creating preference pairs
- `docs/model-initialization.md` - Stage 3: Reference model setup
- `docs/preference-modeling.md` - Stage 4: Reward model training
- `docs/dpo-optimization.md` - Stage 5: DPO training loop
- `docs/iterative-training.md` - Stage 6: Refinement iterations
- `docs/evaluation-monitoring.md` - Stage 7: Final validation
- `docs/quality-thresholds.md` - Threshold definitions and enforcement
- `docs/capability-assessment.md` - Regression detection methods
- `docs/performance-optimization.md` - Hardware-specific optimization for Apple Silicon

---

## Cross-References

**Related Skills**:
- **preference-data-quality** - DPO and RLVR quality metrics (gap, KL, decontamination)
- **data-distillation** - Data generation and augmentation
- **scientific-validation** - Experimental validation methodology
- **mlx-performance** - Hardware calibration and optimization for Apple Silicon

**Related Libraries**:
- `training_metrics.py` - DPO validation functions
- `hardware_calibrator.py` - Automatic hardware detection and configuration

**Related Tools**:
- HuggingFace TRL library - DPO implementation
- Weights & Biases - Training monitoring
- PyTorch - Model training

---

## Key Principles

1. **Quality gates at every stage** - Prevent propagation of poor data/models
2. **Capability regression is critical** - Monitor benchmarks continuously
3. **Small KL divergence** - Stay close to base model (≤0.1)
4. **Strong preference signal** - Ensure clear preferences (gap ≥0.15)
5. **Iterative refinement** - Multiple passes improve results
6. **Data quality matters** - Poor pairs produce poor models
7. **Decontamination is mandatory** - Prevent eval leakage (≥0.9)
8. **Baseline comparison** - Always compare to pre-DPO metrics

---

## Key Takeaways

1. **7 stages**: SFT → Preference Data → Init → Modeling → Optimization → Iteration → Evaluation
2. **Quality thresholds**: Gap ≥0.15, KL ≤0.1, pairs ≥1000, decontamination ≥0.9
3. **Capability regression**: Monitor benchmarks, detect drops >5%, prevent with small KL
4. **Integration**: Use preference-data-quality skill and training_metrics.py
5. **Progressive disclosure**: See workflow.md and docs/*.md for details
6. **Iterative process**: Expect multiple refinement passes
7. **Data quality**: Preference pairs are the foundation
8. **Quality gates**: Enforce thresholds between stages
