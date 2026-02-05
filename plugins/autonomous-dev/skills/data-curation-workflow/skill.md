---
name: data-curation-workflow
version: 1.0.0
type: workflow
description: A-grade 9-stage data curation pipeline for LLM training. Bronze/Silver/Gold tier processing with quality gates, checkpoint resume, and specialized data generation.
keywords: [data-curation, pipeline, ifd, kenlm, deduplication, decontamination, dpo, rlvr, anti-hallucination, bronze, silver, gold]
auto_activate: true
allowed-tools: [Read, Bash]
---

# Data Curation Workflow Skill

Complete A-grade 9-stage data curation pipeline for preparing high-quality LLM training datasets. Discovered during the ReAlign training capabilities audit, this pipeline transforms raw data into gold-tier training-ready datasets through extraction, filtering, scoring, deduplication, decontamination, and specialized generation.

## When This Skill Activates

- Building training datasets
- Curating data for fine-tuning
- Understanding data quality pipelines
- Preparing DPO/RLVR/anti-hallucination data
- Keywords: "data curation", "pipeline", "ifd", "deduplication", "decontamination", "training data"

---

## 9-Stage Pipeline Overview

```
Bronze Layer (Raw → Extracted)
  Stage 1: Extract → Stage 2: Prefilter

Silver Layer (Extracted → Quality-Scored)
  Stage 3: Score → Stage 4: Dedup → Stage 5: Decontaminate → Stage 6: Filter

Gold Layer (Quality-Scored → Training-Ready)
  Stage 7: Generate → Stage 8: Mix → Stage 9: Validate
```

### Pipeline Visualization

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                          A-GRADE DATA PIPELINE                              │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│   ┌──────────┐    ┌───────────┐                                            │
│   │  RAW     │───▸│ 1_EXTRACT │   Bronze Layer                             │
│   │  DATA    │    │ Persona   │   ~95-98% retention                        │
│   └──────────┘    └─────┬─────┘                                            │
│                         │                                                   │
│                   ┌─────▼─────┐                                            │
│                   │ 2_PREFILTER│   KenLM perplexity                        │
│                   │  KenLM    │   ~10K examples/sec                        │
│                   └─────┬─────┘   ~85-90% retention                        │
│                         │                                                   │
│   ┌─────────────────────▼─────────────────────┐                            │
│   │               SILVER LAYER                │                            │
│   ├───────────────────────────────────────────┤                            │
│   │  ┌─────────┐  ┌─────────┐  ┌───────────┐ │                            │
│   │  │ 3_SCORE │─▸│ 4_DEDUP │─▸│5_DECONTAM │ │                            │
│   │  │   IFD   │  │  Bloom  │  │  13-gram  │ │                            │
│   │  └─────────┘  └─────────┘  └───────────┘ │                            │
│   │                                    │      │                            │
│   │                              ┌─────▼────┐ │                            │
│   │                              │ 6_FILTER │ │                            │
│   │                              │ IFD≥0.6  │ │                            │
│   │                              └──────────┘ │                            │
│   └─────────────────────┬─────────────────────┘                            │
│                         │                                                   │
│   ┌─────────────────────▼─────────────────────┐                            │
│   │               GOLD LAYER                  │                            │
│   ├───────────────────────────────────────────┤                            │
│   │  ┌──────────┐ ┌─────────┐ ┌───────────┐  │                            │
│   │  │7_GENERATE│─▸│ 8_MIX  │─▸│9_VALIDATE │  │                            │
│   │  │DPO/RLVR  │ │ Weights │ │  Final QA │  │                            │
│   │  └──────────┘ └─────────┘ └───────────┘  │                            │
│   └───────────────────────────────────────────┘                            │
│                                                                             │
│   OUTPUT: A-grade training dataset (IFD≥0.6, deduped, decontaminated)     │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## Key Classes Reference

| Purpose | Class | Location |
|---------|-------|----------|
| IFD scoring | `FastIFDScorer` | `src/realign/data/ifd_scorer_fast.py` |
| Multi-dimensional | `MultiDimensionalScorer` | `src/realign/data/quality/multi_scorer.py` |
| Deduplication | `BloomDeduplicator` | `src/realign/data/processors/bloom_deduplicator.py` |
| Fuzzy dedup | `MinHashDeduplicator` | `src/realign/data/processors/minhash_dedup.py` |
| Decontamination | `BenchmarkDecontaminator` | `src/realign/data/processors/decontaminator.py` |
| DPO generation | `RefusalDPOPairGenerator` | `src/realign/data/refusal_dpo_generator.py` |
| Finance DPO | `FinanceDPOGenerator` | `src/realign/data/finance_dpo_generator.py` |
| RLVR generation | `FinanceRLVRGenerator` | `src/realign/data/finance_rlvr_generator.py` |
| Code RLVR | `CodeRLVRGenerator` | `src/realign/data/code_rlvr_generator.py` |
| Math RLVR | `MathRLVRGenerator` | `src/realign/data/math_rlvr_generator.py` |
| Anti-hallucination | `AntiHallucinationGenerator` | `src/realign/data/antihallucination_generator.py` |
| Mixing | `DatasetMixer` | `src/realign/data/dataset_mixer.py` |
| Persona extraction | `PersonaGenerator` | `src/realign/data/persona_generator.py` |
| Coordination | `HybridCurationCoordinator` | `src/realign/data/hybrid_curator.py` |

---

## Quality Thresholds by Training Type

| Training Type | Quality Score | IFD Score | Preference Gap | Notes |
|---------------|---------------|-----------|----------------|-------|
| **SFT** | ≥8.0 | ≥0.3 | N/A | Base training data |
| **DPO chosen** | ≥9.0 | ≥0.5 | N/A | High-quality preferred |
| **DPO rejected** | ≤6.0 | any | ≥3.0 vs chosen | Low-quality dispreferred |
| **RLVR** | ≥9.0 | ≥0.5 | N/A | Verifiable reasoning |
| **Calibration** | ≥8.0 | ≥0.4 | N/A | Uncertainty handling |
| **Anti-hallucination** | ≥8.0 | ≥0.4 | N/A | Refusal/hedging data |

---

## Stage-by-Stage Commands

### Stage 1: Extract (Persona-driven)

```bash
# Extract instruction-response pairs with persona context
python -m realign.data.extract \
  --input raw_data/ \
  --output 1_extracted.jsonl \
  --persona-driven \
  --formats "jsonl,parquet,csv"
```

**Classes**: `PersonaGenerator`, `HybridCurationCoordinator`
**Output**: Structured instruction-response pairs
**Retention**: 95-98%

---

### Stage 2: Prefilter (KenLM)

```bash
# KenLM perplexity filtering - removes bottom 30-50%
python -m realign.data.kenlm_filter \
  --input 1_extracted.jsonl \
  --output 2_prefiltered.jsonl \
  --perplexity-threshold 500 \
  --batch-size 10000
```

**Performance**: ~10K examples/second
**Retention**: 50-70% (removes bottom 30-50% by perplexity)
**Memory**: ~2GB for 5-gram model

---

### Stage 3: Score (Multi-dimensional)

```bash
# Multi-dimensional quality scoring
python -m realign.data.score \
  --input 2_prefiltered.jsonl \
  --output 3_scored.jsonl \
  --scorer multi-dimensional \
  --dimensions "ifd,factuality,reasoning,diversity,domain"
```

**Classes**: `FastIFDScorer`, `MultiDimensionalScorer`
**Output**: Examples with quality scores attached
**Retention**: 100% (scoring only, no filtering)

**Scoring Dimensions**:
- **IFD** (Instruction-Following Difficulty): 0.0-1.0
- **Factuality**: Fact-checkable correctness
- **Reasoning**: Chain-of-thought quality
- **Diversity**: Lexical/semantic variety
- **Domain**: Subject matter relevance

---

### Stage 4: Deduplicate (Bloom + Fuzzy)

```bash
# Bloom filter exact dedup + MinHash fuzzy dedup
python -m realign.data.dedup \
  --input 3_scored.jsonl \
  --output 4_deduped.jsonl \
  --exact-bloom \
  --fuzzy-minhash \
  --similarity-threshold 0.85
```

**Classes**: `BloomDeduplicator`, `MinHashDeduplicator`
**Memory**: ~1GB for 100M documents (Bloom filter)
**Retention**: 85-95%

---

### Stage 5: Decontaminate (Benchmark)

```bash
# Remove benchmark contamination via 13-gram matching
python -m realign.data.decontaminate \
  --input 4_deduped.jsonl \
  --output 5_decontaminated.jsonl \
  --benchmarks "mmlu,gsm8k,humaneval,arc,hellaswag,winogrande" \
  --ngram-size 13 \
  --threshold 0.1
```

**Classes**: `BenchmarkDecontaminator`
**Benchmarks**: MMLU, GSM8K, HumanEval, ARC, HellaSwag, WinoGrande
**Retention**: 95-99% (contamination typically <5%)

---

### Stage 6: Filter (Quality Threshold)

```bash
# Quality threshold filtering
python -m realign.data.filter \
  --input 5_decontaminated.jsonl \
  --output 6_filtered.jsonl \
  --min-quality 8.0 \
  --min-ifd 0.6 \
  --min-length 50 \
  --max-length 4096
```

**Thresholds**:
- Quality score ≥8.0
- IFD score ≥0.6 (configurable per training type)
- Length: 50-4096 tokens
**Retention**: 70-85%

---

### Stage 7: Generate (Specialized Data)

```bash
# Generate DPO pairs
python -m realign.data.dpo_generator \
  --input 6_filtered.jsonl \
  --output 7_dpo.jsonl \
  --generator refusal \
  --min-gap 3.0

# Generate RLVR traces
python -m realign.data.rlvr_generator \
  --input 6_filtered.jsonl \
  --output 7_rlvr.jsonl \
  --domain finance \
  --verifier sandbox

# Generate anti-hallucination examples
python -m realign.data.antihallucination_generator \
  --input 6_filtered.jsonl \
  --output 7_antihall.jsonl \
  --refusal-ratio 0.4 \
  --uncertainty-ratio 0.3
```

**Classes**: `RefusalDPOPairGenerator`, `FinanceRLVRGenerator`, `AntiHallucinationGenerator`
**Output**: Specialized training data (DPO pairs, RLVR traces, calibration examples)
**Retention**: 150-200% (generation adds examples)

---

### Stage 8: Mix (Weighted Combination)

```bash
# Weighted dataset mixing with curriculum scheduling
python -m realign.data.mixer \
  --inputs sft:6_filtered.jsonl,dpo:7_dpo.jsonl,rlvr:7_rlvr.jsonl,antihall:7_antihall.jsonl \
  --output 8_mixed.jsonl \
  --weights "sft:0.5,dpo:0.25,rlvr:0.15,antihall:0.1" \
  --curriculum staged
```

**Classes**: `DatasetMixer`
**Curriculum Options**: `uniform`, `staged`, `domain-balanced`
**Retention**: 100% (mixing only)

**Recommended Mix Weights**:
| Data Type | Weight | Rationale |
|-----------|--------|-----------|
| SFT | 50% | Base instruction following |
| DPO | 25% | Preference alignment |
| RLVR | 15% | Reasoning improvement |
| Anti-hallucination | 10% | Calibration |

---

### Stage 9: Validate (Final QA)

```bash
# Final validation checks
python -m realign.data.validate \
  --input 8_mixed.jsonl \
  --output 9_validated.jsonl \
  --checks "format,contamination,bias,duplicates,poisoning" \
  --report validation_report.json
```

**Validation Checks**:
- Format compliance (JSON schema)
- Contamination re-check
- Bias detection
- Duplicate verification
- Data poisoning detection
**Retention**: 99-100%

---

## Full Pipeline Script

```bash
#!/bin/bash
# A-grade data curation pipeline

INPUT_DIR="raw_data"
OUTPUT_DIR="curated_data"

# Bronze Layer
python -m realign.data.extract --input "$INPUT_DIR" --output "$OUTPUT_DIR/1_extracted.jsonl"
python -m realign.data.kenlm_filter --input "$OUTPUT_DIR/1_extracted.jsonl" --output "$OUTPUT_DIR/2_prefiltered.jsonl"

# Silver Layer
python -m realign.data.score --input "$OUTPUT_DIR/2_prefiltered.jsonl" --output "$OUTPUT_DIR/3_scored.jsonl"
python -m realign.data.dedup --input "$OUTPUT_DIR/3_scored.jsonl" --output "$OUTPUT_DIR/4_deduped.jsonl"
python -m realign.data.decontaminate --input "$OUTPUT_DIR/4_deduped.jsonl" --output "$OUTPUT_DIR/5_decontaminated.jsonl"
python -m realign.data.filter --input "$OUTPUT_DIR/5_decontaminated.jsonl" --output "$OUTPUT_DIR/6_filtered.jsonl"

# Gold Layer
python -m realign.data.dpo_generator --input "$OUTPUT_DIR/6_filtered.jsonl" --output "$OUTPUT_DIR/7_dpo.jsonl"
python -m realign.data.rlvr_generator --input "$OUTPUT_DIR/6_filtered.jsonl" --output "$OUTPUT_DIR/7_rlvr.jsonl"
python -m realign.data.antihallucination_generator --input "$OUTPUT_DIR/6_filtered.jsonl" --output "$OUTPUT_DIR/7_antihall.jsonl"
python -m realign.data.mixer --inputs "sft:$OUTPUT_DIR/6_filtered.jsonl,dpo:$OUTPUT_DIR/7_dpo.jsonl,rlvr:$OUTPUT_DIR/7_rlvr.jsonl,antihall:$OUTPUT_DIR/7_antihall.jsonl" --output "$OUTPUT_DIR/8_mixed.jsonl"
python -m realign.data.validate --input "$OUTPUT_DIR/8_mixed.jsonl" --output "$OUTPUT_DIR/9_validated.jsonl"

echo "Pipeline complete: $OUTPUT_DIR/9_validated.jsonl"
```

---

## Checkpoint Resume

Each stage saves checkpoint state for crash recovery:

```python
from realign.data.checkpoint import CheckpointManager

# Resume from last checkpoint
checkpoint = CheckpointManager.load("pipeline_checkpoint.json")
if checkpoint:
    resume_stage = checkpoint["last_completed_stage"] + 1
    print(f"Resuming from stage {resume_stage}")
```

**Checkpoint Schema**:
```json
{
  "last_completed_stage": 4,
  "stage_stats": {
    "1_extract": {"input": 100000, "output": 97500, "duration_sec": 120},
    "2_prefilter": {"input": 97500, "output": 68250, "duration_sec": 85}
  },
  "timestamp": "2025-01-31T19:47:03Z"
}
```

---

## Performance Benchmarks

| Stage | Throughput | Memory | Retention |
|-------|------------|--------|-----------|
| Extract | ~50K/min | 2GB | 95-98% |
| Prefilter (KenLM) | ~600K/min | 2GB | 50-70% |
| Score | ~10K/min | 4GB | 100% |
| Dedup | ~100K/min | 1GB/100M docs | 85-95% |
| Decontaminate | ~50K/min | 500MB | 95-99% |
| Filter | ~200K/min | 1GB | 70-85% |
| Generate | ~5K/min | 4GB | 150-200% |
| Mix | ~500K/min | 2GB | 100% |
| Validate | ~100K/min | 1GB | 99-100% |

**Total Pipeline**: ~30 minutes for 100K examples (varies by stage bottlenecks)

---

## Progressive Disclosure

This skill uses progressive disclosure to prevent context bloat:

- **Index** (this file): Pipeline overview and quick commands (<500 lines)
- **Detailed docs**: `docs/*.md` files with implementation details (loaded on-demand)

**Available Documentation**:
- `docs/bronze-layer.md` - Extract and prefilter stage details
- `docs/silver-layer.md` - Score, dedup, decontaminate, filter details
- `docs/gold-layer.md` - Generate, mix, validate details
- `docs/checkpoint-schema.md` - Checkpoint state management
- `docs/quality-gates.md` - Quality threshold configuration
- `docs/troubleshooting.md` - Common issues and solutions

---

## Cross-References

**Related Skills**:
- **quality-scoring** - Multi-dimensional quality assessment
- **dpo-rlvr-generation** - DPO and RLVR data generation details
- **anti-hallucination-training** - Calibration and refusal data generation
- **training-methods** - Training method selection guide
- **preference-data-quality** - Preference pair quality metrics

**Related Agents**:
- **data-curator** - Orchestrates the 9-stage pipeline with checkpoints

**Related Libraries**:
- `training_metrics.py` - Quality metric calculation
- `data_validation.py` - Data format validation

---

## Key Takeaways

1. **9 stages** - Extract → Prefilter → Score → Dedup → Decontaminate → Filter → Generate → Mix → Validate
2. **3 layers** - Bronze (raw→extracted), Silver (extracted→quality), Gold (quality→training)
3. **KenLM** - Removes bottom 30-50% by perplexity (~10K/sec)
4. **IFD scoring** - Instruction-Following Difficulty for quality assessment
5. **Bloom dedup** - 1GB memory for 100M documents
6. **13-gram decontamination** - Removes benchmark contamination
7. **Quality thresholds** - SFT ≥8.0, DPO chosen ≥9.0, DPO rejected ≤6.0
8. **Specialized generation** - DPO, RLVR, anti-hallucination, calibration
9. **Mix weights** - SFT 50%, DPO 25%, RLVR 15%, Anti-hall 10%
10. **Checkpoint resume** - Crash recovery with stage-level checkpoints

---

**Use this skill when building training datasets, understanding data quality pipelines, or preparing specialized training data for fine-tuning.**
