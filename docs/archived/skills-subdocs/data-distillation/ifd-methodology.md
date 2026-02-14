# IFD (Instruction-Following Data) Methodology

Comprehensive guide to assessing instruction-following data quality.

## Overview

IFD methodology evaluates training data quality across three dimensions:
1. **Instruction clarity**: How clear and unambiguous are the instructions?
2. **Response quality**: How accurate and complete are the responses?
3. **Diversity**: How varied are the task types and domains?

## Quality Scoring

### Overall Score Calculation

```python
overall_score = (instruction_clarity + response_quality + diversity_score) / 3.0
```

### Quality Tiers

| Tier | Score Range | Description |
|------|-------------|-------------|
| HIGH | 0.8+ | Excellent quality, ready for training |
| MEDIUM | 0.6-0.8 | Acceptable quality, may benefit from filtering |
| LOW | <0.6 | Needs improvement or filtering |
| INSUFFICIENT | 0 examples | No data available |

## Implementation

### Using training_metrics.py

```python
from pathlib import Path
from training_metrics import calculate_ifd_score

# Calculate IFD score for dataset
dataset_path = Path("data/instruction_dataset.jsonl")
score = calculate_ifd_score(dataset_path)

print(f"Overall Score: {score.overall_score:.2f}")
print(f"Quality Tier: {score.quality_tier}")
print(f"Total Examples: {score.total_examples}")
```

### Dataset Format

JSONL format with instruction/response pairs:

```jsonl
{"instruction": "Add two numbers", "response": "def add(a, b): return a + b"}
{"instruction": "Sort a list", "response": "def sort(lst): return sorted(lst)"}
```

## Best Practices

1. **Set clear thresholds**: Use 0.6 as minimum for training data
2. **Filter incrementally**: Start with IFD, then apply KenLM
3. **Monitor diversity**: Ensure varied task types
4. **Track metrics**: Log scores for each filtering stage

## Performance

- **Typical datasets**: 1,000-10,000 examples process in <5 seconds
- **Large datasets**: 10,000+ examples sampled for efficiency
- **Memory**: Scales linearly with dataset size

## Related

- See `training_metrics.py` for implementation details
- See `kenlm-filtering.md` for next filtering stage
