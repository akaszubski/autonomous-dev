---
name: realign-antihallucination-workflow
version: 1.0.0
type: knowledge
description: Complete anti-hallucination workflow for model realignment. Guides practitioners through 7 stages to reduce factual errors, improve grounding, and enhance citation accuracy with quality thresholds and factuality scoring.
keywords: [antihallucination, factuality, grounding, attribution, hallucination reduction, fact-checking, citation accuracy, model alignment]
auto_activate: true
allowed-tools: [Read, Grep, Glob, Bash, Write]
---

# Realign Anti-hallucination Workflow Skill

Complete workflow for anti-hallucination training to reduce factual errors and improve model grounding.

## When This Skill Activates

- Planning anti-hallucination training workflows
- Implementing factuality-based alignment
- Validating citation and attribution accuracy
- Detecting capability regression during factuality training
- Keywords: "antihallucination", "factuality", "grounding", "attribution", "hallucination reduction", "fact-checking"

---

## Core Principle

**Factual grounding prevents hallucinations and improves trustworthiness.**

- Anti-hallucination training reduces unsupported claims
- Citation training ensures proper attribution
- Factuality scoring measures improvement objectively
- Quality thresholds prevent accuracy degradation

---

## 7-Stage Anti-hallucination Pipeline

| Stage | Name | Key Output | Quality Gate |
|-------|------|------------|--------------|
| 1 | SFT Preparation | Base model | Baseline metrics established |
| 2 | Factuality Data Collection | Factual pairs | Citation accuracy ≥85% |
| 3 | Citation Training | Citation model | Factuality score ≥90% |
| 4 | Hallucination Detection | Detection system | Hallucination rate <10% |
| 5 | Optimization | Aligned model | KL ≤0.1, factuality improving |
| 6 | Iterative Training | Refined model | Metrics improving |
| 7 | Evaluation & Monitoring | Validated model | No capability regression |

**See**: `workflow.md` for detailed stage-by-stage instructions.

---

## Quality Thresholds

Critical metrics that must be met for anti-hallucination success:

| Metric | Threshold | Purpose |
|--------|-----------|---------|
| **Factuality Score** | ≥90% | Ensures claims are factually accurate |
| **Citation Accuracy** | ≥85% | Proper source attribution |
| **Hallucination Rate** | <10% | Minimal unsupported claims |
| **KL Divergence** | ≤0.1 | Prevents drift from base model |
| **Capability Retention** | ≥95% | No regression on benchmarks |

**See**: `docs/quality-thresholds.md` for detailed threshold definitions and enforcement strategies.

---

## Integration with preference-data-quality Skill

This skill integrates with the **preference-data-quality** skill for factuality metric validation:

- KL divergence monitoring (≤0.1)
- Data quality validation
- Decontamination checks

Use `training_metrics.py` library functions:
- `validate_dpo_pairs()` - Validate factual data pairs
- `calculate_ifd_score()` - Instruction-following difficulty

**See**: `docs/factuality-data-collection.md` for integration details.

---

## Quick Start Checklist

### Pre-Training Checklist
- [ ] Base model SFT trained and validated
- [ ] Baseline hallucination rate measured
- [ ] Factuality data sources identified
- [ ] Citation system designed
- [ ] Quality thresholds understood

### During Training Checklist
- [ ] Factual data validated (citation accuracy ≥85%)
- [ ] Citation training completed (factuality ≥90%)
- [ ] Hallucination detection implemented (rate <10%)
- [ ] Training monitored (KL ≤0.1)
- [ ] Quality gates enforced

### Post-Training Checklist
- [ ] Final model meets all quality thresholds
- [ ] No capability regression detected
- [ ] Hallucination rate reduced
- [ ] Citation accuracy improved
- [ ] Documentation complete

**See**: `templates.md` for detailed checklists and configuration templates.

---

## Capability Regression Detection

Critical for ensuring anti-hallucination training improves factuality without degrading capabilities:

**Detection Methods**:
1. Baseline comparison - Compare to pre-training hallucination rate
2. Benchmark tracking - Monitor standard benchmarks
3. Factuality evaluation - Measure claim accuracy
4. Citation analysis - Track attribution quality

**Prevention Strategies**:
- Small KL divergence constraint (≤0.1)
- Balanced factual/creative task distribution
- Regular capability checkpoints
- Citation consistency enforcement

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
| **High hallucination rate** | Rate >10% | Improve grounding data, strengthen fact-checking |
| **Low citation accuracy** | Accuracy <85% | Better source attribution training |
| **Over-hedging** | Model too cautious | Balance certainty calibration |
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
- `workflow.md` - Complete 7-stage anti-hallucination workflow
- `templates.md` - Checklists and configuration templates
- `docs/sft-preparation.md` - Stage 1: Base model preparation
- `docs/factuality-data-collection.md` - Stage 2: Collecting factual data
- `docs/citation-training.md` - Stage 3: Training citation behavior
- `docs/hallucination-detection.md` - Stage 4: Detection system setup
- `docs/optimization.md` - Stage 5: Anti-hallucination training
- `docs/iterative-training.md` - Stage 6: Refinement iterations
- `docs/evaluation-monitoring.md` - Stage 7: Final validation
- `docs/quality-thresholds.md` - Threshold definitions and enforcement
- `docs/capability-assessment.md` - Regression detection methods

---

## Cross-References

**Related Skills**:
- **preference-data-quality** - Data quality metrics
- **realign-source-workflow** - Source attribution (complementary)
- **data-distillation** - Data generation and augmentation
- **scientific-validation** - Experimental validation methodology

**Related Libraries**:
- `training_metrics.py` - Validation functions

**Related Tools**:
- Fact-checking APIs - External verification
- Knowledge bases - Grounding sources
- Weights & Biases - Training monitoring

---

## Key Principles

1. **Factual grounding** - All claims must be supported
2. **Citation accuracy** - Proper source attribution (≥85%)
3. **Hallucination detection** - Automated checking (<10% rate)
4. **KL constraint critical** - Prevents drift from base model (≤0.1)
5. **Balanced training** - Maintain creative capabilities
6. **Quality gates** - Enforce thresholds between stages
7. **Capability regression is critical** - Monitor benchmarks continuously
8. **Transparency** - Clear when uncertain

---

## Key Takeaways

1. **7 stages**: SFT → Data Collection → Citation Training → Detection → Optimization → Iteration → Evaluation
2. **Quality thresholds**: Factuality ≥90%, citation ≥85%, hallucination <10%, KL ≤0.1
3. **Capability regression**: Monitor benchmarks, detect drops >5%, prevent with small KL
4. **Factuality focus**: Reduce unsupported claims, improve grounding
5. **Integration**: Use preference-data-quality skill and training_metrics.py
6. **Progressive disclosure**: See workflow.md and docs/*.md for details
7. **Citation training**: Explicit source attribution
8. **Quality gates**: Enforce thresholds between stages
