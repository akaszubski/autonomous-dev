# Bronze Layer

Raw data extraction and language quality filtering stages.

## Stage 1: Extract (Persona-driven)

### PersonaGenerator

```python
class PersonaGenerator:
    """Generate diverse personas for data extraction."""

    def __init__(
        self,
        model: str = "anthropic/claude-3.5-sonnet",
        diversity_target: float = 0.8
    ):
        """
        Args:
            model: Model for persona generation
            diversity_target: Target diversity score (0.0-1.0)
        """

    def generate_personas(self, count: int, domain: str) -> List[Dict]:
        """Generate diverse personas for a domain."""
```

### HybridCurationCoordinator

```python
class HybridCurationCoordinator:
    """Coordinate persona-driven extraction across sources."""

    def __init__(
        self,
        persona_generator: PersonaGenerator,
        sources: List[str]
    ):
        """
        Args:
            persona_generator: Persona generator instance
            sources: List of data source paths
        """

    def extract(self, output_path: Path) -> Dict:
        """Extract data using persona-driven approach."""
```

### Input Formats

| Format | Extension | Parser |
|--------|-----------|--------|
| JSONL | `.jsonl` | Line-by-line JSON |
| Parquet | `.parquet` | PyArrow reader |
| CSV | `.csv` | Pandas with header detection |
| Web scrape | `.html` | BeautifulSoup + trafilatura |

### Output Schema

```json
{
  "instruction": "string (required)",
  "output": "string (required)",
  "context": "string (optional)",
  "source": "string (metadata)",
  "persona": "string (metadata)",
  "timestamp": "ISO 8601"
}
```

### Quality Gate

- Schema validation: All required fields present
- Non-empty check: instruction and output have content
- Length check: instruction ≥10 chars, output ≥20 chars

### Expected Retention: 95-98%

---

## Stage 2: Prefilter (KenLM)

### KenLM Perplexity Filter

```python
class KenLMFilter:
    """Filter by language model perplexity."""

    def __init__(
        self,
        model_path: str,
        perplexity_threshold: float = 500.0,
        batch_size: int = 10000
    ):
        """
        Args:
            model_path: Path to KenLM .arpa or .bin model
            perplexity_threshold: Maximum perplexity (lower = better)
            batch_size: Batch size for processing
        """

    def filter(self, input_path: Path, output_path: Path) -> Dict:
        """Filter by perplexity, keeping examples below threshold."""
```

### Perplexity Thresholds

| Quality Level | Threshold | Use Case |
|---------------|-----------|----------|
| Strict | <200 | High-quality only |
| Standard | <500 | General training (recommended) |
| Permissive | <1000 | Maximum coverage |

### Performance

- **Throughput**: ~10K examples/second
- **Memory**: ~2GB for 5-gram model
- **Model size**: ~1.5GB for standard English model

### Language Detection

```python
# Combined with fastText language detection
from fasttext import load_model

lang_model = load_model("lid.176.bin")
prediction = lang_model.predict(text)
# Keep if: prediction[0][0] == "__label__en" and prediction[1][0] > 0.9
```

### Expected Retention: 50-70%

Removes bottom 30-50% by perplexity (noisy, gibberish, non-fluent text).

---

## Bronze Layer Pipeline

```bash
# Complete Bronze Layer
python -m realign.data.pipeline bronze \
  --input raw_data/ \
  --output bronze_output/ \
  --persona-count 100 \
  --perplexity-threshold 500 \
  --checkpoint bronze_checkpoint.json
```

### Checkpoint State

```json
{
  "layer": "bronze",
  "stages_completed": ["1_extract"],
  "stage_stats": {
    "1_extract": {
      "input_files": 42,
      "output_examples": 97500,
      "duration_sec": 120,
      "personas_used": 100
    }
  }
}
```
