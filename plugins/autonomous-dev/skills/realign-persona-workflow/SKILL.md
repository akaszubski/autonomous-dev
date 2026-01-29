---
name: realign-persona-workflow
version: 1.0.0
type: knowledge
description: Complete persona consistency workflow for model realignment. Guides practitioners through 7 stages to maintain consistent character traits, personality, and style with quality thresholds and consistency scoring.
keywords: [persona, character consistency, personality, style consistency, voice, character traits, model alignment]
auto_activate: true
allowed-tools: [Read, Grep, Glob, Bash, Write]
---

# Realign Persona Workflow Skill

Complete workflow for persona consistency training to maintain consistent character traits and personality.

## When This Skill Activates

- Planning persona consistency training workflows
- Implementing character-based alignment
- Validating personality trait adherence
- Detecting capability regression during persona training
- Keywords: "persona", "character consistency", "personality", "style consistency", "voice", "character traits"

---

## Core Principle

**Consistent persona builds trust and predictable user experience.**

- Persona training maintains character traits across interactions
- Consistency scoring measures adherence to defined traits
- Style consistency ensures recognizable voice
- Quality thresholds prevent trait drift

---

## 7-Stage Persona Pipeline

| Stage | Name | Key Output | Quality Gate |
|-------|------|------------|--------------|
| 1 | SFT Preparation | Base model | Baseline metrics established |
| 2 | Persona Definition | Character profile | Traits clearly defined |
| 3 | Consistency Data Generation | Persona pairs | Consistency ≥85% |
| 4 | Persona Evaluation | Evaluation system | Trait adherence ≥90% |
| 5 | Optimization | Aligned model | KL ≤0.1, consistency ≥85% |
| 6 | Iterative Training | Refined model | Metrics improving |
| 7 | Evaluation & Monitoring | Validated model | No capability regression |

**See**: `workflow.md` for detailed stage-by-stage instructions.

---

## Quality Thresholds

Critical metrics that must be met for persona consistency success:

| Metric | Threshold | Purpose |
|--------|-----------|---------|
| **Consistency Score** | ≥85% | Ensures persona maintained across contexts |
| **Trait Adherence** | ≥90% | Core personality traits present |
| **Style Variance** | <15% | Recognizable voice and style |
| **KL Divergence** | ≤0.1 | Prevents drift from base model |
| **Capability Retention** | ≥95% | No regression on benchmarks |

**See**: `docs/quality-thresholds.md` for detailed threshold definitions and enforcement strategies.

---

## Integration with preference-data-quality Skill

This skill integrates with the **preference-data-quality** skill for persona metric validation:

- KL divergence monitoring (≤0.1)
- Data quality validation
- Preference pair quality

Use `training_metrics.py` library functions:
- `validate_dpo_pairs()` - Validate persona data pairs
- `calculate_ifd_score()` - Instruction-following difficulty

**See**: `docs/consistency-data-generation.md` for integration details.

---

## Quick Start Checklist

### Pre-Training Checklist
- [ ] Base model SFT trained and validated
- [ ] Persona character profile defined
- [ ] Core traits documented (5-10 key traits)
- [ ] Style guidelines established
- [ ] Quality thresholds understood

### During Training Checklist
- [ ] Persona consistency validated (≥85%)
- [ ] Trait adherence measured (≥90%)
- [ ] Style variance tracked (<15%)
- [ ] Training monitored (KL ≤0.1)
- [ ] Quality gates enforced

### Post-Training Checklist
- [ ] Final model meets all quality thresholds
- [ ] No capability regression detected
- [ ] Persona consistency improved
- [ ] Trait adherence validated
- [ ] Documentation complete

**See**: `templates.md` for detailed checklists and configuration templates.

---

## Capability Regression Detection

Critical for ensuring persona training maintains consistency without degrading capabilities:

**Detection Methods**:
1. Baseline comparison - Compare to pre-training persona metrics
2. Benchmark tracking - Monitor standard benchmarks
3. Trait analysis - Validate core traits present
4. Style consistency - Measure variance in voice/style

**Prevention Strategies**:
- Small KL divergence constraint (≤0.1)
- Balanced persona/general task distribution
- Regular capability checkpoints
- Trait consistency enforcement

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
| **Trait inconsistency** | Adherence <90% | Strengthen persona data, clearer trait definitions |
| **High style variance** | Variance >15% | More style examples, consistent prompting |
| **Over-characterization** | Persona too strong | Balance persona/general examples |
| **Model drift** | KL >0.1 | Reduce learning rate, strengthen KL penalty |
| **Capability loss** | Benchmark drop >5% | Rollback, adjust training data balance |

---

## Progressive Disclosure

This skill uses progressive disclosure to prevent context bloat:

- **Index** (this file): High-level workflow overview and quick reference (<500 lines)
- **Workflow**: `workflow.md` - Complete 7-stage pipeline with decision points
- **Templates**: `templates.md` - Checklists and configuration examples
- **Detailed docs**: `docs/*.md` files - Stage-specific implementation details (loaded on-demand)

**Available Documentation**:
- `workflow.md` - Complete 7-stage persona workflow
- `templates.md` - Checklists and configuration templates
- `docs/sft-preparation.md` - Stage 1: Base model preparation
- `docs/persona-definition.md` - Stage 2: Defining character profile
- `docs/consistency-data-generation.md` - Stage 3: Creating consistency data
- `docs/persona-evaluation.md` - Stage 4: Evaluation system setup
- `docs/optimization.md` - Stage 5: Persona training
- `docs/iterative-training.md` - Stage 6: Refinement iterations
- `docs/evaluation-monitoring.md` - Stage 7: Final validation
- `docs/quality-thresholds.md` - Threshold definitions and enforcement
- `docs/capability-assessment.md` - Regression detection methods

---

## Cross-References

**Related Skills**:
- **preference-data-quality** - Data quality metrics
- **data-distillation** - Data generation and augmentation
- **scientific-validation** - Experimental validation methodology

**Related Libraries**:
- `training_metrics.py` - Validation functions

**Related Tools**:
- Sentiment analysis - Style consistency measurement
- Personality assessment - Trait validation
- Weights & Biases - Training monitoring

---

## Key Principles

1. **Clear persona definition** - 5-10 core traits explicitly defined
2. **Consistency over intensity** - Maintain traits across contexts (≥85%)
3. **Style recognition** - Predictable voice and tone (<15% variance)
4. **Trait adherence** - Core personality present (≥90%)
5. **KL constraint critical** - Prevents drift from base model (≤0.1)
6. **Balanced training** - Maintain general capabilities
7. **Quality gates** - Enforce thresholds between stages
8. **Capability regression is critical** - Monitor benchmarks continuously

---

## Key Takeaways

1. **7 stages**: SFT → Persona Definition → Data Generation → Evaluation → Optimization → Iteration → Evaluation
2. **Quality thresholds**: Consistency ≥85%, trait adherence ≥90%, style variance <15%, KL ≤0.1
3. **Capability regression**: Monitor benchmarks, detect drops >5%, prevent with small KL
4. **Persona focus**: Consistent character traits and style
5. **Integration**: Use preference-data-quality skill and training_metrics.py
6. **Progressive disclosure**: See workflow.md and docs/*.md for details
7. **Trait definition**: Clear, measurable personality characteristics
8. **Quality gates**: Enforce thresholds between stages
