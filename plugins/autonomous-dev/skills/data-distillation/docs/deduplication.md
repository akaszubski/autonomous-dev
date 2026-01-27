# Deduplication Strategies

Remove redundant examples from training data.

## Overview

Deduplication removes duplicate and near-duplicate examples to:
- Reduce training dataset size
- Prevent memorization
- Improve model generalization
- Remove contamination

## Deduplication Levels

### 1. Exact Deduplication

Remove exact string matches:

```python
def exact_deduplicate(dataset):
    seen = set()
    unique = []
    for example in dataset:
        key = example['instruction'] + example['response']
        if key not in seen:
            seen.add(key)
            unique.append(example)
    return unique
```

**Use case**: Fast, simple, catches obvious duplicates

### 2. Near-Deduplication (MinHash/LSH)

Remove similar examples (0.9+ similarity):

```python
# Pseudo-code
from datasketch import MinHash, MinHashLSH

def near_deduplicate(dataset, threshold=0.9):
    lsh = MinHashLSH(threshold=threshold)
    unique = []

    for i, example in enumerate(dataset):
        m = MinHash()
        for word in example['response'].split():
            m.update(word.encode('utf-8'))

        if not lsh.query(m):
            lsh.insert(f"example_{i}", m)
            unique.append(example)

    return unique
```

**Use case**: Catch paraphrases and minor variations

### 3. Semantic Deduplication (Embeddings)

Remove semantically similar examples:

```python
# Pseudo-code
from sentence_transformers import SentenceTransformer
import faiss

def semantic_deduplicate(dataset, threshold=0.95):
    model = SentenceTransformer('all-MiniLM-L6-v2')

    # Generate embeddings
    texts = [ex['response'] for ex in dataset]
    embeddings = model.encode(texts)

    # Build FAISS index
    index = faiss.IndexFlatL2(embeddings.shape[1])
    index.add(embeddings)

    # Find duplicates
    unique_indices = []
    seen = set()

    for i, emb in enumerate(embeddings):
        if i not in seen:
            D, I = index.search(emb.reshape(1, -1), k=10)
            for j, dist in zip(I[0], D[0]):
                if dist < (1 - threshold) and j > i:
                    seen.add(j)
            unique_indices.append(i)

    return [dataset[i] for i in unique_indices]
```

**Use case**: Most thorough, catches semantic duplicates

## Recommended Pipeline

```
Raw Data
  ↓
Exact Deduplication (-5-10%)
  ↓
IFD Filtering (-40-50%)
  ↓
KenLM Filtering (-40-45%)
  ↓
Near-Deduplication (-5-10%)
  ↓
Final Dataset (5-10% of original)
```

## Performance Comparison

| Method | Speed | Thoroughness | Memory |
|--------|-------|--------------|--------|
| Exact | Very Fast | Low | Low |
| MinHash/LSH | Fast | Medium | Medium |
| Semantic | Slow | High | High |

## Best Practices

1. **Start with exact**: Always run exact deduplication first (fast, effective)
2. **Use MinHash for scale**: LSH handles million+ examples efficiently
3. **Reserve semantic for critical data**: Use only when quality is paramount
4. **Set appropriate thresholds**: 0.9+ for near-dup, 0.95+ for semantic
5. **Decontaminate eval sets**: Remove eval examples from training data

## Decontamination

Special case of deduplication to prevent data leakage:

```python
def decontaminate(train_data, eval_data, threshold=0.98):
    """Remove training examples similar to eval set."""
    # Use semantic deduplication between train and eval
    # Keep eval set intact, remove from training
    pass
```

**Threshold**: Use 0.98+ to catch eval contamination

## Related

- See `ifd-methodology.md` for quality filtering
- See `kenlm-filtering.md` for perplexity filtering
- External: datasketch library (MinHash/LSH implementation)
- External: sentence-transformers for semantic similarity
