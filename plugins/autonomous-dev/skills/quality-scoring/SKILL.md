---
name: Quality Scoring
version: 1.0.0
type: knowledge
description: Multi-dimensional data assessment for training quality evaluation
keywords: [quality, scoring, assessment, IFD, factuality, reasoning]
auto_activate: true
---

# Quality Scoring

Multi-dimensional assessment for training data quality.

## When Activates

Quality assessment, data scoring, multi-dimensional evaluation, IFD scoring, factuality checks, reasoning validation, training data prep

---

## Core Concepts

### Quality Scorers (6 Types)

Fast to comprehensive scoring approaches:

1. **FastIFD** - Instruction-following difficulty (10-20x faster)
2. **Quality** - LLM-based quality (Qwen3-30B, 0.85 ex/s)
3. **MultiDimensional** - 5-dimension composite
4. **LLMQuality** - Multi-backend (MLX/OpenRouter)
5. **Ensemble** - Cross-model ensemble
6. **Tulu3** - Multi-dimensional reference (training_metrics.py)

### Quality Dimensions (6 Metrics)

1. **IFD Score** (0.0-1.0) - Instruction-following difficulty
2. **Factuality** (0.0-1.0) - Hallucination detection
3. **Reasoning** (0.0-1.0) - Step-by-step logic quality
4. **Diversity** (0.0-1.0) - Dataset-level diversity
5. **Domain** (0.0-1.0) - Domain-specific relevance
6. **LLM Quality** (1-10) - Tulu3 comprehensive score

### Training Thresholds

| Type | Quality | IFD | Use Case |
|------|---------|-----|----------|
| **SFT** | ≥8.0 | ≥0.3 | Base training |
| **DPO chosen** | ≥9.0 | ≥0.5 | High quality only |
| **DPO rejected** | ≤6.0 | any | Low quality |
| **RLVR** | ≥9.0 | ≥0.5 | Verified solutions |
| **Calibration** | ≥8.0 | ≥0.4 | Uncertainty examples |

---

## Quick Reference

| Concept | Details | Reference |
|---------|---------|-----------|
| **Scorers** | 6 types (FastIFD to Ensemble) | `quality-scorers.md` |
| **Dimensions** | 6 metrics (IFD to LLM Quality) | `quality-dimensions.md` |
| **Thresholds** | By training type (SFT, DPO, RLVR) | `training-thresholds.md` |
| **Library** | `training_metrics.py` | Integration functions |

### IFD Score Calculation

```python
from training_metrics import calculate_ifd_score

# IFD = PPL(response) / PPL(response|instruction)
ifd_score = calculate_ifd_score(
    instruction="Explain quantum computing",
    response="Quantum computing uses qubits..."
)
# Higher score = more challenging
```

### DPO Pair Validation

```python
from training_metrics import validate_dpo_pairs

# Validate chosen/rejected quality gap
is_valid = validate_dpo_pairs(
    chosen_score=9.2,  # High quality
    rejected_score=5.8  # Low quality
)
# Ensures quality gap ≥0.15
```

### REQUIRED: DPO Multi-Dimensional Scoring

**Every DPO pair MUST have multi-dimensional quality scores before training.**

This is a hard requirement — DPO data without quality scores will learn shortcuts (e.g., "longer = better") instead of genuine preference signal.

**Required output fields per pair**:
- `chosen_score` (float): Composite quality score for chosen response
- `rejected_score` (float): Composite quality score for rejected response
- `margin` (float): chosen_score - rejected_score (must be ≥3.0)

**Length bias audit** (MUST run before DPO training):
```python
from pathlib import Path
from training_metrics import validate_dpo_pairs

metrics = validate_dpo_pairs(dpo_path=Path("dpo_pairs.jsonl"))

# Check length bias
longer_chosen = sum(1 for p in metrics.pairs if len(p.chosen) > len(p.rejected))
length_bias = longer_chosen / metrics.total_pairs

if length_bias > 0.70:
    raise ValueError(
        f"DPO length bias {length_bias:.0%} > 70% threshold.\n"
        f"Model will learn 'longer = better' shortcut.\n"
        f"Fix: Score by quality dimensions, not length."
    )

# Check quality scores present
missing = sum(1 for p in metrics.pairs if p.chosen_score is None)
if missing > 0:
    raise ValueError(f"{missing} pairs missing quality scores — run scoring first")
```

**Scoring workflow**:
1. Generate DPO pairs (dpo-rlvr-generation skill)
2. Score all pairs with multi-dimensional scorer (this skill)
3. Filter by quality margin ≥3.0
4. Audit length bias ≤70%
5. Only then proceed to training

### RLVR Verifiability

```python
from training_metrics import assess_rlvr_verifiability

# Assess reasoning trace verifiability
verifiable = assess_rlvr_verifiability(
    reasoning_trace="Step 1: ...\nStep 2: ...",
    domain="math"
)
# Math/coding: 90%+ verifiable required
```

---

## Progressive Disclosure

**Detailed guides**: See `docs/*.md`

- `docs/quality-scorers.md` - 6 scorer implementations
- `docs/quality-dimensions.md` - 6 dimension definitions
- `docs/training-thresholds.md` - Thresholds, CLI, distributed performance

---

## Security Considerations

### Input Validation (CWE-20)

- Validate score ranges (0.0-1.0 or 1-10)
- Sanitize data inputs before scoring
- Check threshold values before application

### Path Traversal (CWE-22)

- Sanitize file paths for data loading
- Whitelist directories for training data
- Validate output paths for scored datasets

### Security Patterns (training_metrics.py)

```python
from pathlib import Path

def safe_load_data(data_path: str) -> dict:
    """Load data with path validation."""
    # Validate path within allowed directory
    path = Path(data_path).resolve()
    if not str(path).startswith('/allowed/data/'):
        raise ValueError(f"Path outside allowed directory: {path}")

    # Load safely
    return json.loads(path.read_text())
```

---

## Distributed Performance

### Single Machine Performance

- **M4 Max**: ~0.85 ex/s (Qwen3-30B)
- **M3 Ultra**: ~0.85 ex/s (Qwen3-30B)

### Parallel Processing

- **Combined throughput**: ~1.7 ex/s (50/50 split)
- **Scaling**: Linear with machine count
- **Bottleneck**: Model inference, not I/O

### CLI Commands

```bash
# Score dataset with FastIFD
python -m training_metrics score \
  --input data/train.jsonl \
  --output data/scored.jsonl \
  --scorer fastifd \
  --threshold 0.3

# Multi-dimensional scoring
python -m training_metrics score \
  --input data/train.jsonl \
  --output data/scored.jsonl \
  --scorer multidim \
  --quality-threshold 8.0 \
  --ifd-threshold 0.5

# DPO pair filtering
python -m training_metrics filter_dpo \
  --input data/dpo_pairs.jsonl \
  --output data/filtered_pairs.jsonl \
  --chosen-threshold 9.0 \
  --rejected-threshold 6.0

# RLVR verifiability check
python -m training_metrics assess_rlvr \
  --input data/rlvr_traces.jsonl \
  --output data/verified.jsonl \
  --domain math \
  --threshold 0.9
```

---

## Related Skills

- **data-distillation** - IFD methodology and KenLM filtering
- **preference-data-quality** - DPO and RLVR metrics
- **python-standards** - Code quality standards

---

## Library Integration

**Primary library**: `training_metrics.py`

Key functions:
- `calculate_ifd_score()` - IFD calculation
- `validate_dpo_pairs()` - DPO pair validation
- `assess_rlvr_verifiability()` - RLVR assessment
- `score_quality()` - Multi-dimensional scoring
- `ensemble_score()` - Cross-model ensemble

---

## Key Takeaways

1. **6 scorers** - FastIFD (fast) to Ensemble (comprehensive)
2. **6 dimensions** - IFD, Factuality, Reasoning, Diversity, Domain, LLM Quality
3. **Training thresholds** - SFT ≥8.0, DPO chosen ≥9.0, RLVR ≥9.0
4. **IFD score** - PPL(response) / PPL(response|instruction), higher = harder
5. **Security** - CWE-20 (input validation), CWE-22 (path traversal)
6. **Distributed** - ~1.7 ex/s with 2 machines (linear scaling)
7. **CLI commands** - training_metrics module for all operations
8. **Integration** - Use training_metrics library functions
9. **DPO pairs** - Chosen ≥9.0, Rejected ≤6.0, gap ≥0.15
10. **RLVR** - Math/coding 90%+ verifiable, general 80%+
11. **DPO scoring REQUIRED** - Every pair must have chosen_score, rejected_score, margin before training
12. **Length bias audit** - ≤70% of pairs where chosen is longer (prevents "longer = better" shortcut)
