# Quality Gates

Configuration and thresholds for quality gates at each pipeline stage.

## Stage Quality Gates

| Stage | Metric | Threshold | Action if Failed |
|-------|--------|-----------|------------------|
| 2_prefilter | Perplexity | <500 | Filter out high perplexity |
| 3_score | IFD score | ≥0.6 | Flag for review |
| 4_dedup | Similarity | <0.85 | Remove duplicates |
| 5_decontaminate | N-gram overlap | <0.1 | Remove contaminated |
| 6_filter | IFD score | ≥0.6 | Filter out low quality |
| 7_generate | DPO gap | ≥3.0 | Regenerate pairs |
| 9_validate | Poisoning | None | Reject dataset |

## Training Type Thresholds

### SFT (Supervised Fine-Tuning)

```python
SFT_THRESHOLDS = {
    "quality_score": 8.0,  # Minimum overall quality (0-10)
    "ifd_score": 0.3,      # Minimum IFD (0.0-1.0)
    "min_length": 50,      # Minimum tokens
    "max_length": 4096     # Maximum tokens
}
```

### DPO (Direct Preference Optimization)

```python
DPO_CHOSEN_THRESHOLDS = {
    "quality_score": 9.0,  # High quality for chosen
    "ifd_score": 0.5,      # Higher IFD for chosen
    "min_length": 100,
    "max_length": 2048
}

DPO_REJECTED_THRESHOLDS = {
    "quality_score_max": 6.0,  # Low quality for rejected
    "preference_gap": 3.0,     # Minimum gap vs chosen
    "min_length": 50,
    "max_length": 2048
}
```

### RLVR (Reinforcement Learning with Verified Rewards)

```python
RLVR_THRESHOLDS = {
    "quality_score": 9.0,
    "ifd_score": 0.5,
    "verifiability": 0.8,  # 80%+ must be verifiable
    "min_length": 100,
    "max_length": 4096
}
```

### Calibration Data

```python
CALIBRATION_THRESHOLDS = {
    "quality_score": 8.0,
    "ifd_score": 0.4,
    "confidence_accuracy": 0.8  # Stated confidence matches accuracy
}
```

## Adjusting Thresholds

### When to Loosen Thresholds

- Not enough data passing (< 50% retention)
- Domain-specific data with different quality profiles
- Exploratory training runs

### When to Tighten Thresholds

- Quality issues in training (loss spikes, poor eval)
- Overfitting symptoms
- Production deployment requirements

### Threshold Tuning Workflow

```python
from realign.data.quality import QualityAnalyzer

# Analyze quality distribution
analyzer = QualityAnalyzer()
stats = analyzer.analyze("scored_data.jsonl")

# Adjust thresholds based on distribution
print(f"Quality mean: {stats['quality_mean']}")
print(f"Quality std: {stats['quality_std']}")
print(f"Suggested threshold: {stats['quality_mean'] - stats['quality_std']}")
```

## Quality Reports

Each stage generates a quality report:

```json
{
  "stage": "6_filter",
  "input_count": 61000,
  "output_count": 52000,
  "retention_rate": 0.85,
  "quality_distribution": {
    "high_quality": {"count": 35000, "percentage": 0.67},
    "medium_quality": {"count": 12000, "percentage": 0.23},
    "low_quality": {"count": 5000, "percentage": 0.10}
  },
  "threshold_applied": {
    "min_quality": 8.0,
    "min_ifd": 0.6
  },
  "filtered_reasons": {
    "below_quality_threshold": 6000,
    "below_ifd_threshold": 2000,
    "length_violation": 1000
  }
}
```
