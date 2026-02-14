---
name: realign-meta-framework
version: 1.0.0
type: knowledge
auto_activate: false
keywords: realignment, training pipeline, quality thresholds, capability regression, performance optimization, SFT, DPO, RLVR
---

# Realignment Meta-Framework

Shared framework for all realignment training workflows. Provides the common pipeline template, quality thresholds, and performance optimization guidance used across all domain-specific realignment workflows.

## 7-Stage Pipeline Template

All realignment workflows follow this common pipeline:

1. **Capability Assessment**: Evaluate current model capabilities and identify gaps
2. **Data Preparation**: Collect and prepare domain-specific training data
3. **SFT Preparation**: Supervised fine-tuning on curated examples
4. **Preference/Reward Modeling**: Domain-specific optimization (DPO, RLVR, SRF, etc.)
5. **Iterative Training**: Multi-round training with quality gates
6. **Evaluation & Monitoring**: Comprehensive evaluation against baselines
7. **Deployment & Validation**: Final validation and deployment readiness

## Quality Thresholds

| Metric | Minimum | Target | Critical |
|--------|---------|--------|----------|
| Task accuracy | 85% | 92% | < 80% triggers rollback |
| Capability retention | 95% | 98% | < 90% triggers rollback |
| Data quality score | 0.8 | 0.9 | < 0.7 blocks training |
| Evaluation coverage | 80% | 95% | < 70% blocks deployment |

## Capability Regression Detection

- Run baseline evaluation suite before and after each training stage
- Track per-capability scores across training rounds
- Automatic rollback if any capability drops > 5% from baseline
- Cross-domain contamination checks between training stages

## Performance Optimization

### Memory Management
- Use gradient checkpointing for models > 7B parameters
- Batch size auto-tuning based on available memory
- Mixed precision training (fp16/bf16) by default

### Training Efficiency
- Learning rate warmup: 5-10% of total steps
- Cosine annealing schedule with min_lr = 0.1 * max_lr
- Early stopping with patience = 3 evaluation rounds
- Checkpoint every N steps (configurable per domain)

### Hardware Considerations
- See `mlx-performance` skill for Apple Silicon optimization
- GPU memory estimation: model_params * 4 bytes * 3 (model + optimizer + gradients)
- Multi-device training coordination patterns

## Cross-References

- **Hardware details**: See `mlx-performance` skill
- **Domain workflows**: See `realign-domain-workflows` skill
- **Data quality**: See `preference-data-quality` skill
