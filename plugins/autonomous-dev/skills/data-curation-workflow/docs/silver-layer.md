# Silver Layer

Quality scoring, deduplication, decontamination, and filtering stages.

## Stage 3: Score (Multi-dimensional)

### FastIFDScorer

```python
class FastIFDScorer:
    """Calculate Instruction-Following Difficulty scores."""

    def __init__(
        self,
        model: str = "anthropic/claude-3.5-sonnet",
        batch_size: int = 100
    ):
        """
        Args:
            model: Model for IFD calculation
            batch_size: Batch size for API calls
        """

    def score(self, examples: List[Dict]) -> List[float]:
        """Calculate IFD scores (0.0-1.0)."""
```

### MultiDimensionalScorer

```python
class MultiDimensionalScorer:
    """Score across multiple quality dimensions."""

    def __init__(self, dimensions: List[str] = None):
        """
        Args:
            dimensions: List of dimensions to score
                Default: ["ifd", "factuality", "reasoning", "diversity", "domain"]
        """

    def score(self, examples: List[Dict]) -> List[Dict]:
        """Return multi-dimensional scores for each example."""
```

### Scoring Dimensions

| Dimension | Range | Description |
|-----------|-------|-------------|
| IFD | 0.0-1.0 | Instruction-following difficulty |
| Factuality | 0.0-1.0 | Fact-checkable correctness |
| Reasoning | 0.0-1.0 | Chain-of-thought quality |
| Diversity | 0.0-1.0 | Lexical/semantic variety |
| Domain | 0.0-1.0 | Subject matter relevance |

### Output Schema

```json
{
  "instruction": "...",
  "output": "...",
  "scores": {
    "ifd": 0.72,
    "factuality": 0.85,
    "reasoning": 0.68,
    "diversity": 0.45,
    "domain": 0.91,
    "overall": 8.2
  }
}
```

---

## Stage 4: Deduplicate (Bloom + Fuzzy)

### BloomDeduplicator

```python
class BloomDeduplicator:
    """Exact deduplication using Bloom filter."""

    def __init__(
        self,
        expected_items: int = 100_000_000,
        false_positive_rate: float = 0.01
    ):
        """
        Args:
            expected_items: Expected number of items
            false_positive_rate: Acceptable false positive rate

        Memory: ~1GB for 100M items at 1% FPR
        """

    def deduplicate(self, input_path: Path, output_path: Path) -> Dict:
        """Remove exact duplicates using content hash."""
```

### MinHashDeduplicator

```python
class MinHashDeduplicator:
    """Fuzzy deduplication using MinHash + LSH."""

    def __init__(
        self,
        num_perm: int = 128,
        threshold: float = 0.85
    ):
        """
        Args:
            num_perm: Number of permutations (higher = more accurate)
            threshold: Jaccard similarity threshold for duplicates
        """

    def deduplicate(self, input_path: Path, output_path: Path) -> Dict:
        """Remove near-duplicates using MinHash similarity."""
```

### Deduplication Strategy

1. **Exact match first** (Bloom filter) - O(1) lookup
2. **Fuzzy match second** (MinHash) - Higher accuracy for paraphrases
3. **Preserve highest-scoring** when duplicates found

---

## Stage 5: Decontaminate (Benchmark)

### BenchmarkDecontaminator

```python
class BenchmarkDecontaminator:
    """Remove benchmark contamination via n-gram matching."""

    def __init__(
        self,
        benchmarks: List[str],
        ngram_size: int = 13,
        threshold: float = 0.1
    ):
        """
        Args:
            benchmarks: List of benchmark names to check
            ngram_size: N-gram size for matching (13 recommended)
            threshold: Maximum overlap ratio (0.1 = 10%)
        """

    def decontaminate(self, input_path: Path, output_path: Path) -> Dict:
        """Remove examples with benchmark overlap."""
```

### Supported Benchmarks

| Benchmark | Domain | Examples |
|-----------|--------|----------|
| MMLU | Knowledge | 14K |
| GSM8K | Math | 8.5K |
| HumanEval | Code | 164 |
| ARC | Reasoning | 7.7K |
| HellaSwag | Common sense | 10K |
| WinoGrande | Coreference | 1.7K |
| TruthfulQA | Truthfulness | 817 |

### N-gram Matching

- **13-gram**: Standard for text (catches most contamination)
- **8-gram**: For code (shorter matches relevant)
- **20-gram**: Strict matching (fewer false positives)

---

## Stage 6: Filter (Quality Threshold)

### QualityFilter

```python
class QualityFilter:
    """Filter by quality thresholds."""

    def __init__(
        self,
        min_quality: float = 8.0,
        min_ifd: float = 0.6,
        min_length: int = 50,
        max_length: int = 4096
    ):
        """
        Args:
            min_quality: Minimum overall quality score (0-10)
            min_ifd: Minimum IFD score (0.0-1.0)
            min_length: Minimum token count
            max_length: Maximum token count
        """

    def filter(self, input_path: Path, output_path: Path) -> Dict:
        """Filter by quality thresholds."""
```

### Thresholds by Training Type

| Type | Quality | IFD | Length |
|------|---------|-----|--------|
| SFT | ≥8.0 | ≥0.3 | 50-4096 |
| DPO (chosen) | ≥9.0 | ≥0.5 | 100-2048 |
| DPO (rejected) | ≤6.0 | any | 50-2048 |
| RLVR | ≥9.0 | ≥0.5 | 100-4096 |

---

## Silver Layer Pipeline

```bash
# Complete Silver Layer
python -m realign.data.pipeline silver \
  --input bronze_output/2_prefiltered.jsonl \
  --output silver_output/ \
  --min-quality 8.0 \
  --min-ifd 0.6 \
  --checkpoint silver_checkpoint.json
```

### Checkpoint State

```json
{
  "layer": "silver",
  "stages_completed": ["3_score", "4_dedup", "5_decontaminate"],
  "stage_stats": {
    "3_score": {
      "input": 68250,
      "scored": 68250,
      "mean_quality": 7.8,
      "mean_ifd": 0.65
    },
    "4_dedup": {
      "input": 68250,
      "output": 61425,
      "duplicates_removed": 6825,
      "duplicate_rate": 0.10
    }
  }
}
```
