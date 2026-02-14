# Decontamination Strategies

Protect eval set integrity by removing training examples that overlap with evaluation data.

## Overview

Decontamination prevents inflated evaluation metrics by ensuring training and eval sets are disjoint.

## Why Decontamination Matters

### Problem: Eval Contamination

Training on eval examples leads to:
- **Memorization**: Model memorizes eval answers
- **Inflated metrics**: Artificially high eval scores
- **False confidence**: Overestimation of real-world performance

### Solution: 2% Overlap Threshold

- **Target**: ≥0.9 decontamination score (≤10% overlap)
- **Reality**: Modern datasets aim for 0.98+ (≤2% overlap)
- **Detection**: Semantic similarity matching

## Decontamination Methods

### 1. Exact Match Removal

Remove training examples exactly matching eval:

```python
def exact_decontaminate(train_data, eval_data):
    """Remove exact matches from training."""
    eval_set = set(json.dumps(ex, sort_keys=True) for ex in eval_data)
    return [ex for ex in train_data
            if json.dumps(ex, sort_keys=True) not in eval_set]
```

**Use case**: Fast, catches obvious contamination

### 2. Semantic Similarity Removal (0.98+ threshold)

Remove training examples semantically similar to eval:

```python
from sentence_transformers import SentenceTransformer
import faiss

def semantic_decontaminate(train_data, eval_data, threshold=0.98):
    """Remove training examples similar to eval (0.98+ match)."""
    model = SentenceTransformer('all-MiniLM-L6-v2')

    # Embed eval set
    eval_texts = [ex['text'] for ex in eval_data]
    eval_embeddings = model.encode(eval_texts)

    # Build FAISS index
    index = faiss.IndexFlatL2(eval_embeddings.shape[1])
    index.add(eval_embeddings)

    # Filter training data
    clean_train = []
    for train_ex in train_data:
        train_emb = model.encode([train_ex['text']])
        D, I = index.search(train_emb, k=1)

        # Compute similarity (1 - normalized distance)
        similarity = 1 - D[0][0] / 2  # L2 to cosine similarity

        if similarity < threshold:
            clean_train.append(train_ex)

    return clean_train
```

**Use case**: Thorough, catches paraphrases and variations

### 3. N-gram Overlap Detection

Detect overlap via common n-grams:

```python
def ngram_decontaminate(train_data, eval_data, n=13, threshold=0.8):
    """Remove training with >80% 13-gram overlap with eval."""
    from collections import Counter

    def get_ngrams(text, n):
        words = text.split()
        return set(' '.join(words[i:i+n]) for i in range(len(words)-n+1))

    eval_ngrams = set()
    for ex in eval_data:
        eval_ngrams.update(get_ngrams(ex['text'], n))

    clean_train = []
    for train_ex in train_data:
        train_ngrams = get_ngrams(train_ex['text'], n)
        overlap = len(train_ngrams & eval_ngrams) / max(len(train_ngrams), 1)

        if overlap < threshold:
            clean_train.append(train_ex)

    return clean_train
```

**Use case**: Industry standard (used by LLaMA, GPT)

## Implementation with training_metrics.py

```python
from training_metrics import DPOMetrics

# DPO metrics include decontamination score
metrics = DPOMetrics(
    preference_gap=0.2,
    kl_divergence=0.05,
    pair_count=1000,
    decontamination_score=0.95  # 95% clean (5% overlap)
)

# Check quality
if metrics.decontamination_score < 0.9:
    print("WARNING: Eval contamination detected!")
    print(f"Overlap: {(1 - metrics.decontamination_score) * 100:.1f}%")
```

## Recommended Pipeline

```
1. Exact match removal (fast)
   ↓
2. N-gram overlap detection (medium)
   ↓
3. Semantic similarity removal (thorough)
   ↓
4. Manual spot-check (quality control)
```

## Performance Comparison

| Method | Speed | Thoroughness | Recommended Threshold |
|--------|-------|--------------|----------------------|
| Exact | Very Fast | Low | 100% match |
| N-gram | Fast | Medium | 80% overlap |
| Semantic | Slow | High | 98% similarity |

## Best Practices

1. **Decontaminate early**: Before any training
2. **Use multiple methods**: Exact + N-gram + Semantic
3. **Document overlap**: Track removed examples
4. **Verify manually**: Spot-check borderline cases
5. **Update regularly**: Re-decontaminate when eval set changes

## Common Pitfalls

| Pitfall | Impact | Solution |
|---------|--------|----------|
| Skipping decontamination | Inflated metrics | Always decontaminate |
| Threshold too low | False positives | Use 0.98+ for semantic |
| Missing paraphrases | Subtle contamination | Use semantic similarity |
| One-time check | Eval set changes | Re-decontaminate regularly |

## Measuring Contamination

### Decontamination Score

```python
decontamination_score = 1.0 - (contaminated_count / total_train_examples)
```

**Target**: ≥0.9 (industry standard is 0.98+)

### Overlap Percentage

```python
overlap_percentage = (contaminated_count / total_train_examples) * 100
```

**Target**: ≤2% (10% max acceptable)

## Related

- See `dpo-metrics.md` for DPO quality metrics
- See `training_metrics.py` for implementation
- External: sentence-transformers for semantic similarity
- External: FAISS for efficient similarity search
