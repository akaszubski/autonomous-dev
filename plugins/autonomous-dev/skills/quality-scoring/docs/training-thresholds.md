# Training Thresholds

Quality and IFD thresholds by training type, with CLI commands and distributed performance guidance.

---

## Overview

Different training types require different quality thresholds. Use this guide to filter datasets appropriately for SFT, DPO, RLVR, and calibration training.

---

## Threshold Summary

| Training Type | Quality Score | IFD Score | Purpose | Example Count |
|--------------|---------------|-----------|---------|---------------|
| **SFT** | ≥8.0 | ≥0.3 | Base training | 100K-1M |
| **DPO (chosen)** | ≥9.0 | ≥0.5 | High quality responses | 10K-100K |
| **DPO (rejected)** | ≤6.0 | any | Low quality responses | 10K-100K |
| **RLVR** | ≥9.0 | ≥0.5 | Verified reasoning | 10K-50K |
| **Calibration** | ≥8.0 | ≥0.4 | Uncertainty examples | 5K-20K |

---

## 1. SFT (Supervised Fine-Tuning)

**Purpose**: Base instruction-following training

**Thresholds**:
- Quality: ≥8.0 (good overall quality)
- IFD: ≥0.3 (avoid trivial examples)
- Factuality: ≥0.8 (accurate information)
- Reasoning: ≥0.7 (logical responses)

**Rationale**:
- SFT establishes base capabilities
- Need broad coverage (moderate thresholds)
- Quality matters more than extreme difficulty

**CLI Command**:
```bash
# Filter dataset for SFT training
python -m training_metrics filter \
  --input data/raw_train.jsonl \
  --output data/sft_train.jsonl \
  --quality-threshold 8.0 \
  --ifd-threshold 0.3 \
  --factuality-threshold 0.8 \
  --reasoning-threshold 0.7 \
  --training-type sft
```

**Expected Retention**:
- 30-50% of raw data (depends on source quality)
- Target: 100K-1M examples for full SFT

**Example (Acceptable SFT)**:
```json
{
  "instruction": "What is photosynthesis?",
  "response": "Photosynthesis is the process by which plants convert light energy into chemical energy, producing glucose and oxygen from CO2 and water.",
  "scores": {
    "quality": 8.2,
    "ifd": 0.35,
    "factuality": 0.95,
    "reasoning": 0.75
  }
}
```

---

## 2. DPO (Direct Preference Optimization)

### DPO Chosen (Preferred Responses)

**Purpose**: High-quality responses to learn from

**Thresholds**:
- Quality: ≥9.0 (excellent quality only)
- IFD: ≥0.5 (challenging examples)
- Factuality: ≥0.9 (highly accurate)
- Reasoning: ≥0.85 (strong reasoning)

**Rationale**:
- DPO chosen sets quality target
- Need clear positive examples
- Higher difficulty drives learning

**CLI Command**:
```bash
# Filter for DPO chosen examples
python -m training_metrics filter \
  --input data/scored_train.jsonl \
  --output data/dpo_chosen.jsonl \
  --quality-threshold 9.0 \
  --ifd-threshold 0.5 \
  --factuality-threshold 0.9 \
  --reasoning-threshold 0.85 \
  --training-type dpo-chosen
```

### DPO Rejected (Dispreferred Responses)

**Purpose**: Low-quality responses to avoid

**Thresholds**:
- Quality: ≤6.0 (poor quality)
- IFD: any (difficulty doesn't matter)
- Factuality: ≤0.6 (inaccurate acceptable)
- Reasoning: ≤0.6 (weak reasoning)

**Rationale**:
- DPO rejected shows what to avoid
- Quality matters, not difficulty
- Creates preference gap with chosen

**CLI Command**:
```bash
# Filter for DPO rejected examples
python -m training_metrics filter \
  --input data/scored_train.jsonl \
  --output data/dpo_rejected.jsonl \
  --quality-threshold-max 6.0 \
  --factuality-threshold-max 0.6 \
  --reasoning-threshold-max 0.6 \
  --training-type dpo-rejected
```

### DPO Pair Validation

**Quality Gap**: ≥3.0 points (chosen 9.0, rejected ≤6.0)

**Validation Command**:
```bash
# Validate DPO pairs have sufficient quality gap
python -m training_metrics validate_dpo \
  --chosen data/dpo_chosen.jsonl \
  --rejected data/dpo_rejected.jsonl \
  --output data/dpo_pairs.jsonl \
  --min-gap 3.0
```

**Example DPO Pair**:
```json
{
  "instruction": "Explain quantum entanglement",
  "chosen": {
    "response": "Quantum entanglement is a phenomenon where two particles...",
    "quality": 9.2,
    "ifd": 0.65
  },
  "rejected": {
    "response": "It's when things are connected somehow.",
    "quality": 5.5,
    "ifd": 0.25
  },
  "gap": 3.7
}
```

---

## 3. RLVR (Reinforcement Learning with Verifiable Rewards)

**Purpose**: Training with verifiable solution correctness

**Thresholds**:
- Quality: ≥9.0 (excellent quality)
- IFD: ≥0.5 (challenging problems)
- Verifiability: ≥0.9 (highly verifiable)
- Reasoning: ≥0.9 (strong reasoning chains)

**Domain Requirements**:
- **Math**: 95%+ verifiable (unit tests, symbolic solvers)
- **Code**: 90%+ verifiable (test suites, execution)
- **Logic**: 90%+ verifiable (formal proofs)
- **General**: <80% verifiable (unsuitable for RLVR)

**CLI Command**:
```bash
# Filter for RLVR training
python -m training_metrics filter_rlvr \
  --input data/scored_math.jsonl \
  --output data/rlvr_train.jsonl \
  --quality-threshold 9.0 \
  --ifd-threshold 0.5 \
  --verifiability-threshold 0.9 \
  --domain math
```

**Verifiability Assessment**:
```bash
# Assess verifiability of reasoning traces
python -m training_metrics assess_rlvr \
  --input data/reasoning_traces.jsonl \
  --output data/verifiable.jsonl \
  --domain math \
  --threshold 0.9
```

**Example (RLVR)**:
```json
{
  "instruction": "Solve: If 3x - 7 = 14, what is x?",
  "response": "Step 1: Add 7 to both sides: 3x = 21\nStep 2: Divide by 3: x = 7\nVerification: 3(7) - 7 = 21 - 7 = 14 ✓",
  "scores": {
    "quality": 9.5,
    "ifd": 0.55,
    "verifiability": 1.0,
    "reasoning": 0.95
  },
  "verification": {
    "method": "symbolic_solver",
    "result": "correct",
    "confidence": 1.0
  }
}
```

---

## 4. Calibration Training

**Purpose**: Improve model uncertainty estimation

**Thresholds**:
- Quality: ≥8.0 (good quality)
- IFD: ≥0.4 (moderate-to-hard)
- Uncertainty: varies (mix of confident and uncertain)
- Reasoning: ≥0.75 (logical explanations)

**Uncertainty Distribution**:
- 40% high confidence (easy, verifiable)
- 40% moderate uncertainty (medium difficulty)
- 20% high uncertainty (hard, ambiguous)

**CLI Command**:
```bash
# Filter for calibration training (mixed uncertainty)
python -m training_metrics filter_calibration \
  --input data/scored_train.jsonl \
  --output data/calibration_train.jsonl \
  --quality-threshold 8.0 \
  --ifd-threshold 0.4 \
  --high-confidence-ratio 0.4 \
  --moderate-uncertainty-ratio 0.4 \
  --high-uncertainty-ratio 0.2
```

**Example (Calibration)**:
```json
{
  "instruction": "Is this claim verifiable: 'Most people prefer summer'?",
  "response": "This claim is difficult to verify definitively. While surveys exist, preferences vary by culture, climate, and individual factors. Confidence: Medium (60%)",
  "scores": {
    "quality": 8.3,
    "ifd": 0.45,
    "reasoning": 0.80
  },
  "calibration": {
    "uncertainty_level": "moderate",
    "confidence": 0.60,
    "category": "subjective_claim"
  }
}
```

---

## CLI Commands Reference

### Comprehensive Scoring

```bash
# Score entire dataset with all dimensions
python -m training_metrics score \
  --input data/raw_train.jsonl \
  --output data/scored_train.jsonl \
  --scorer multidim \
  --batch-size 32 \
  --num-workers 4
```

### Fast IFD Screening

```bash
# Rapid IFD filtering (10-20x faster)
python -m training_metrics score \
  --input data/raw_train.jsonl \
  --output data/ifd_filtered.jsonl \
  --scorer fastifd \
  --ifd-threshold 0.3 \
  --batch-size 128
```

### Ensemble Quality Scoring

```bash
# High-accuracy ensemble scoring
python -m training_metrics score \
  --input data/critical_data.jsonl \
  --output data/ensemble_scored.jsonl \
  --scorer ensemble \
  --models "Qwen3-30B,Llama-3.3-70B,Mixtral-8x22B" \
  --aggregation median
```

### Parallel Processing (Distributed)

```bash
# Machine 1 (M4 Max): Process first half
python -m training_metrics score \
  --input data/raw_train.jsonl \
  --output data/scored_part1.jsonl \
  --scorer quality \
  --start-idx 0 \
  --end-idx 50000 \
  --device cuda:0

# Machine 2 (M3 Ultra): Process second half
python -m training_metrics score \
  --input data/raw_train.jsonl \
  --output data/scored_part2.jsonl \
  --scorer quality \
  --start-idx 50000 \
  --end-idx 100000 \
  --device cuda:1

# Merge results
python -m training_metrics merge \
  --inputs data/scored_part1.jsonl data/scored_part2.jsonl \
  --output data/scored_full.jsonl
```

### Batch Analysis

```bash
# Generate quality distribution report
python -m training_metrics analyze \
  --input data/scored_train.jsonl \
  --output reports/quality_analysis.json \
  --plot reports/quality_distribution.png
```

---

## Distributed Performance

### Single Machine Benchmarks

**M4 Max (Apple Silicon)**:
- QualityScorer (Qwen3-30B): ~0.85 ex/s
- MultiDimensionalScorer: ~0.60 ex/s
- FastIFDScorer: ~15-20 ex/s
- Memory: 30 GB (Quality), 4 GB (FastIFD)

**M3 Ultra (Apple Silicon)**:
- QualityScorer (Qwen3-30B): ~0.85 ex/s
- MultiDimensionalScorer: ~0.60 ex/s
- FastIFDScorer: ~15-20 ex/s
- Memory: Similar to M4 Max

### Parallel Processing Performance

**2 Machines (M4 Max + M3 Ultra)**:
- Combined QualityScorer: ~1.7 ex/s (50/50 split)
- Combined MultiDim: ~1.2 ex/s
- Combined FastIFD: ~35-40 ex/s
- **Scaling**: Linear with machine count

**Throughput Calculations**:
```python
# Dataset: 100K examples
# QualityScorer: 0.85 ex/s (single machine)
# Time: 100,000 / 0.85 = 117,647 seconds = ~33 hours

# Parallel (2 machines): 100,000 / 1.7 = 58,824 seconds = ~16 hours
# Speedup: 2.0x (linear scaling)

# Parallel (4 machines): 100,000 / 3.4 = 29,412 seconds = ~8 hours
# Speedup: 4.0x (linear scaling)
```

### Optimization Strategies

**1. Batching**
```bash
# Increase batch size for throughput
python -m training_metrics score \
  --batch-size 64 \  # Default: 32
  --num-workers 8    # Parallel batches
```

**2. Fast Pre-filtering**
```bash
# Use FastIFD to filter before expensive scoring
python -m training_metrics score \
  --input data/raw.jsonl \
  --output data/ifd_filtered.jsonl \
  --scorer fastifd \
  --ifd-threshold 0.3

# Then comprehensive scoring on filtered data
python -m training_metrics score \
  --input data/ifd_filtered.jsonl \
  --output data/final_scored.jsonl \
  --scorer quality
```

**3. Progressive Quality Tiers**
```bash
# Tier 1: FastIFD (90% reduction)
# Tier 2: QualityScorer (50% reduction)
# Tier 3: MultiDimensional (final 10%)

# Result: 10x faster than scoring all with MultiDim
```

### Distributed Architecture

```
Raw Dataset (1M examples)
    ↓
Split into N shards
    ↓
Distribute to N machines
    ↓
[Machine 1]  [Machine 2]  ...  [Machine N]
  ↓ (0.85 ex/s)  ↓ (0.85 ex/s)     ↓ (0.85 ex/s)
Scored Shard 1   Scored Shard 2       Scored Shard N
    ↓                ↓                     ↓
                 Merge Results
                      ↓
              Final Scored Dataset
              (Combined: N * 0.85 ex/s)
```

---

## Quality Monitoring

### Real-time Monitoring

```bash
# Monitor scoring progress and quality distribution
python -m training_metrics score \
  --input data/train.jsonl \
  --output data/scored.jsonl \
  --scorer quality \
  --monitor \
  --dashboard http://localhost:8080
```

### Quality Alerts

```python
# Set up quality alerts for anomalies
from training_metrics import QualityMonitor

monitor = QualityMonitor(
    alert_thresholds={
        "quality_score": (8.0, 10.0),  # Alert if outside range
        "ifd_score": (0.3, 1.0),
        "factuality": (0.8, 1.0)
    }
)

monitor.track_batch(scored_examples)
if monitor.has_anomalies():
    print(f"Anomalies detected: {monitor.get_anomalies()}")
```

---

## Security Considerations

### Path Traversal Prevention (CWE-22)

```python
from pathlib import Path

def safe_filter_dataset(input_path: str, output_path: str) -> None:
    """Filter dataset with path validation."""
    # Validate input path
    input_file = Path(input_path).resolve()
    allowed_input = Path("/data/raw").resolve()
    if not str(input_file).startswith(str(allowed_input)):
        raise ValueError(f"Input path outside allowed directory: {input_file}")

    # Validate output path
    output_file = Path(output_path).resolve()
    allowed_output = Path("/data/processed").resolve()
    if not str(output_file).startswith(str(allowed_output)):
        raise ValueError(f"Output path outside allowed directory: {output_file}")

    # Proceed with filtering
    filter_dataset(input_file, output_file)
```

### Input Validation (CWE-20)

```python
def validate_thresholds(
    quality_threshold: float,
    ifd_threshold: float,
    training_type: str
) -> None:
    """Validate threshold parameters."""
    # Quality score: 1-10
    if not 1 <= quality_threshold <= 10:
        raise ValueError(f"Quality threshold out of range: {quality_threshold}")

    # IFD score: 0.0-1.0
    if not 0.0 <= ifd_threshold <= 1.0:
        raise ValueError(f"IFD threshold out of range: {ifd_threshold}")

    # Training type: whitelist
    allowed_types = ["sft", "dpo-chosen", "dpo-rejected", "rlvr", "calibration"]
    if training_type not in allowed_types:
        raise ValueError(f"Invalid training type: {training_type}")
```

---

## Related Documentation

- `quality-scorers.md` - Scorer implementations
- `quality-dimensions.md` - Dimension definitions
- **data-distillation** skill - IFD methodology
- **preference-data-quality** skill - DPO/RLVR details
- **python-standards** skill - Code quality patterns
