---
name: realign-source-workflow
version: 1.0.0
type: knowledge
description: Complete source attribution workflow for model realignment. Guides practitioners through 7 stages to improve citation accuracy, provenance tracking, and transparency with quality thresholds and attribution scoring.
keywords: [source attribution, citation, provenance, transparency, grounding, citation accuracy, source retrieval, model alignment]
auto_activate: true
allowed-tools: [Read, Grep, Glob, Bash, Write]
---

# Realign Source Workflow Skill

Complete workflow for source attribution training to improve citation accuracy and information provenance.

## When This Skill Activates

- Planning source attribution training workflows
- Implementing citation-based alignment
- Validating source retrieval and attribution accuracy
- Detecting capability regression during citation training
- Keywords: "source attribution", "citation", "provenance", "transparency", "grounding", "citation accuracy"

---

## Core Principle

**Proper source attribution builds trust and enables verification.**

- Source attribution training ensures proper citation of information
- Citation accuracy measures attribution quality
- Source retrieval precision validates grounding
- Quality thresholds prevent unsupported claims

---

## 7-Stage Source Attribution Pipeline

| Stage | Name | Key Output | Quality Gate |
|-------|------|------------|--------------|
| 1 | SFT Preparation | Base model | Baseline metrics established |
| 2 | Source Data Preparation | Source pairs | Retrieval precision ≥85% |
| 3 | Citation Training | Citation model | Citation accuracy ≥90% |
| 4 | Attribution Verification | Verification system | Attribution coverage ≥80% |
| 5 | Optimization | Aligned model | KL ≤0.1, citation ≥90% |
| 6 | Iterative Training | Refined model | Metrics improving |
| 7 | Evaluation & Monitoring | Validated model | No capability regression |

**See**: `workflow.md` for detailed stage-by-stage instructions.

---

## Quality Thresholds

Critical metrics that must be met for source attribution success:

| Metric | Threshold | Purpose |
|--------|-----------|---------|
| **Citation Accuracy** | ≥90% | Ensures correct source attribution |
| **Source Retrieval Precision** | ≥85% | Accurate source identification |
| **Attribution Coverage** | ≥80% | Percentage of claims with sources |
| **KL Divergence** | ≤0.1 | Prevents drift from base model |
| **Capability Retention** | ≥95% | No regression on benchmarks |

**See**: `docs/quality-thresholds.md` for detailed threshold definitions and enforcement strategies.

---

## Integration with preference-data-quality Skill

This skill integrates with the **preference-data-quality** skill for source attribution metric validation:

- KL divergence monitoring (≤0.1)
- Data quality validation
- Citation quality assessment

Use `training_metrics.py` library functions:
- `validate_dpo_pairs()` - Validate citation data pairs
- `calculate_ifd_score()` - Instruction-following difficulty

**See**: `docs/source-data-preparation.md` for integration details.

---

## Quick Start Checklist

### Pre-Training Checklist
- [ ] Base model SFT trained and validated
- [ ] Baseline citation accuracy measured
- [ ] Source databases identified and indexed
- [ ] Citation format standardized
- [ ] Quality thresholds understood

### During Training Checklist
- [ ] Source data validated (retrieval precision ≥85%)
- [ ] Citation training completed (accuracy ≥90%)
- [ ] Attribution verification implemented (coverage ≥80%)
- [ ] Training monitored (KL ≤0.1)
- [ ] Quality gates enforced

### Post-Training Checklist
- [ ] Final model meets all quality thresholds
- [ ] No capability regression detected
- [ ] Citation accuracy improved
- [ ] Source attribution consistent
- [ ] Documentation complete

**See**: `templates.md` for detailed checklists and configuration templates.

---

## Capability Regression Detection

Critical for ensuring source attribution training improves citation without degrading capabilities:

**Detection Methods**:
1. Baseline comparison - Compare to pre-training citation metrics
2. Benchmark tracking - Monitor standard benchmarks
3. Citation analysis - Validate attribution accuracy
4. Source retrieval - Test precision and recall

**Prevention Strategies**:
- Small KL divergence constraint (≤0.1)
- Balanced citation/general task distribution
- Regular capability checkpoints
- Attribution consistency enforcement

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
| **Low citation accuracy** | Accuracy <90% | Improve source data quality, strengthen citation training |
| **Poor source retrieval** | Precision <85% | Better indexing, improved retrieval system |
| **Low attribution coverage** | Coverage <80% | More citation examples, reward attribution |
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
- `workflow.md` - Complete 7-stage source attribution workflow
- `templates.md` - Checklists and configuration templates
- `docs/sft-preparation.md` - Stage 1: Base model preparation
- `docs/source-data-preparation.md` - Stage 2: Preparing source data
- `docs/citation-training.md` - Stage 3: Training citation behavior
- `docs/attribution-verification.md` - Stage 4: Verification system setup
- `docs/optimization.md` - Stage 5: Source attribution training
- `docs/iterative-training.md` - Stage 6: Refinement iterations
- `docs/evaluation-monitoring.md` - Stage 7: Final validation
- `docs/quality-thresholds.md` - Threshold definitions and enforcement
- `docs/capability-assessment.md` - Regression detection methods

---

## Cross-References

**Related Skills**:
- **preference-data-quality** - Data quality metrics
- **realign-antihallucination-workflow** - Factuality (complementary)
- **data-distillation** - Data generation and augmentation
- **scientific-validation** - Experimental validation methodology

**Related Libraries**:
- `training_metrics.py` - Validation functions

**Related Tools**:
- RAG systems - Source retrieval
- Citation databases - Reference validation
- Weights & Biases - Training monitoring

---

## Key Principles

1. **Explicit citation** - All factual claims must cite sources
2. **Retrieval precision** - Accurate source identification (≥85%)
3. **Attribution coverage** - High percentage of cited claims (≥80%)
4. **Citation accuracy** - Correct source attribution (≥90%)
5. **KL constraint critical** - Prevents drift from base model (≤0.1)
6. **Transparent provenance** - Clear information trail
7. **Quality gates** - Enforce thresholds between stages
8. **Capability regression is critical** - Monitor benchmarks continuously

---

## Key Takeaways

1. **7 stages**: SFT → Source Data → Citation Training → Verification → Optimization → Iteration → Evaluation
2. **Quality thresholds**: Citation ≥90%, retrieval ≥85%, coverage ≥80%, KL ≤0.1
3. **Capability regression**: Monitor benchmarks, detect drops >5%, prevent with small KL
4. **Citation focus**: Proper source attribution for all claims
5. **Integration**: Use preference-data-quality skill and training_metrics.py
6. **Progressive disclosure**: See workflow.md and docs/*.md for details
7. **Source retrieval**: Accurate identification and attribution
8. **Quality gates**: Enforce thresholds between stages
