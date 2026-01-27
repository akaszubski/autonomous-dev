# KenLM Perplexity Filtering

High-speed statistical language model filtering for training data.

## Overview

KenLM provides 45-100x speedup over model-based filtering while retaining highest quality 5-10% of data.

## How It Works

### Perplexity Measurement

Perplexity measures text predictability:
- **Low perplexity**: Predictable, well-formed text (good quality)
- **High perplexity**: Unpredictable, unusual text (potentially low quality)

### Optimal Thresholds

| Threshold | Data Retention | Use Case |
|-----------|----------------|----------|
| 0.6 | ~5% | Ultra-high quality |
| 0.7 | ~7-8% | High quality |
| 0.8 | ~10% | Balanced quality/quantity |

## Performance Benefits

### Speedup Comparison

| Method | Processing Time | Quality | Notes |
|--------|----------------|---------|-------|
| KenLM | 1 min | High | 45-100x faster |
| GPT-4 scoring | 45-100 min | High | Expensive, slow |
| Random sampling | Instant | Variable | No quality filter |

### Real-World Results

- **RedPajama dataset**: 100x speedup, 5% retention, maintained quality
- **Typical workflow**: IFD (1 min) → KenLM (1 min) → Training-ready data

## Implementation

### Basic Usage

```python
# Pseudo-code (KenLM not included in training_metrics.py)
import kenlm

# Load language model
model = kenlm.Model('path/to/model.arpa')

# Calculate perplexity for text
def calculate_perplexity(text):
    return model.perplexity(text)

# Filter dataset
def filter_by_perplexity(dataset, threshold=0.7):
    filtered = []
    for example in dataset:
        perplexity = calculate_perplexity(example['response'])
        if perplexity >= threshold:
            filtered.append(example)
    return filtered
```

## Best Practices

1. **Use after IFD**: First filter by IFD score, then apply KenLM
2. **Tune threshold**: Start with 0.7, adjust based on retention rate
3. **Domain-specific models**: Train KenLM on domain data for best results
4. **Batch processing**: Process large datasets in chunks

## Related

- See `ifd-methodology.md` for first filtering stage
- See `deduplication.md` for final filtering stage
- External: KenLM GitHub (kpu/kenlm)
