# Quality Scorers

Six scorer implementations for training data quality assessment, from fast approximations to comprehensive ensemble evaluation.

---

## Overview

Quality scorers provide different speed/accuracy tradeoffs for evaluating training data quality. Choose based on dataset size, time constraints, and quality requirements.

---

## Scorer Comparison

| Scorer | Purpose | Speed | Accuracy | File |
|--------|---------|-------|----------|------|
| **FastIFD** | Instruction-following difficulty | 10-20x faster | Good | ifd_scorer_fast.py |
| **Quality** | LLM-based quality (Qwen3-30B) | 0.85 ex/s | High | quality_scorer.py |
| **MultiDimensional** | 5-dimension composite | Medium | High | quality/multi_scorer.py |
| **LLMQuality** | Multi-backend (MLX/OpenRouter) | Variable | High | llm_quality_scorer.py |
| **Ensemble** | Cross-model ensemble | Slow | Highest | ensemble_scorer.py |
| **Tulu3** | Multi-dimensional reference | Fast | Reference | training_metrics.py |

---

## 1. FastIFDScorer

**Purpose**: Rapid instruction-following difficulty estimation

**Speed**: 10-20x faster than full IFD calculation

**How It Works**:
```python
from training_metrics.scorers import FastIFDScorer

scorer = FastIFDScorer()
score = scorer.score({
    "instruction": "Explain quantum entanglement",
    "response": "Quantum entanglement is..."
})
# Returns: {"ifd_score": 0.67}
```

**Use Cases**:
- Large dataset screening (millions of examples)
- Initial filtering before expensive scoring
- Real-time quality assessment

**Approximation Method**:
- Uses simplified perplexity calculation
- Skips full model inference for response generation
- Estimates PPL ratio from instruction complexity

**Limitations**:
- Less accurate than full IFD (±0.1 score range)
- May miss nuanced difficulty patterns
- Best for relative ranking, not absolute scores

---

## 2. QualityScorer

**Purpose**: LLM-based quality assessment with Qwen3-30B

**Speed**: ~0.85 examples/second (M4 Max)

**How It Works**:
```python
from training_metrics.scorers import QualityScorer

scorer = QualityScorer(model="Qwen/Qwen3-30B-Instruct")
score = scorer.score({
    "instruction": "Write a function to reverse a string",
    "response": "def reverse(s): return s[::-1]"
})
# Returns: {
#   "quality_score": 8.5,
#   "helpfulness": 9,
#   "accuracy": 9,
#   "clarity": 8,
#   "completeness": 8
# }
```

**Quality Dimensions** (1-10 scale):
- **Helpfulness** - Does response address instruction?
- **Accuracy** - Is information correct?
- **Clarity** - Is response well-explained?
- **Completeness** - Are all aspects covered?

**Use Cases**:
- Standard training data quality assessment
- Balanced speed/accuracy needs
- Production data filtering

**Configuration**:
```python
scorer = QualityScorer(
    model="Qwen/Qwen3-30B-Instruct",
    backend="mlx",  # or "openrouter"
    batch_size=32,
    temperature=0.0  # Deterministic scoring
)
```

---

## 3. MultiDimensionalScorer

**Purpose**: Comprehensive 5-dimension quality assessment

**Speed**: Medium (0.5-0.7 ex/s)

**How It Works**:
```python
from training_metrics.scorers import MultiDimensionalScorer

scorer = MultiDimensionalScorer()
score = scorer.score({
    "instruction": "Solve: 2x + 5 = 15",
    "response": "x = 5 because 2(5) + 5 = 15"
})
# Returns: {
#   "ifd_score": 0.45,
#   "factuality": 0.95,
#   "reasoning": 0.90,
#   "diversity": 0.60,
#   "domain": 0.85,
#   "composite": 0.75  # Weighted average
# }
```

**Quality Dimensions**:
1. **IFD** (0.0-1.0) - Instruction-following difficulty
2. **Factuality** (0.0-1.0) - Verifiable accuracy
3. **Reasoning** (0.0-1.0) - Logical coherence
4. **Diversity** (0.0-1.0) - Coverage breadth (dataset-level)
5. **Domain** (0.0-1.0) - Specialized knowledge

**Composite Score Calculation**:
```python
composite = (
    0.25 * ifd_score +
    0.30 * factuality +
    0.25 * reasoning +
    0.10 * diversity +
    0.10 * domain
)
```

**Use Cases**:
- High-quality dataset curation
- Research experiments requiring detailed metrics
- Domain-specific training (math, code, reasoning)

---

## 4. LLMQualityScorer

**Purpose**: Flexible multi-backend LLM evaluation

**Speed**: Variable (depends on backend and model)

**How It Works**:
```python
from training_metrics.scorers import LLMQualityScorer

# MLX backend (local)
scorer = LLMQualityScorer(
    backend="mlx",
    model="mlx-community/Qwen3-30B-Instruct-4bit"
)

# OpenRouter backend (cloud)
scorer = LLMQualityScorer(
    backend="openrouter",
    model="anthropic/claude-3.5-sonnet",
    api_key="sk-..."
)

score = scorer.score({
    "instruction": "Explain recursion",
    "response": "Recursion is when a function calls itself..."
})
```

**Supported Backends**:
- **MLX** - Local Apple Silicon inference (fast, private)
- **OpenRouter** - Cloud models (flexible, powerful)
- **vLLM** - Self-hosted server (scalable)

**Use Cases**:
- Custom model evaluation
- Cloud-based scoring for large models
- Comparing different model assessments

---

## 5. EnsembleQualityScorer

**Purpose**: Cross-model ensemble for highest accuracy

**Speed**: Slow (0.2-0.3 ex/s)

**How It Works**:
```python
from training_metrics.scorers import EnsembleQualityScorer

scorer = EnsembleQualityScorer(
    models=[
        "Qwen/Qwen3-30B-Instruct",
        "meta-llama/Llama-3.3-70B-Instruct",
        "mistralai/Mixtral-8x22B-Instruct"
    ],
    aggregation="median"  # or "mean", "weighted"
)

score = scorer.score({
    "instruction": "Write a binary search algorithm",
    "response": "def binary_search(arr, target): ..."
})
# Returns: {
#   "quality_score": 9.0,  # Median of [8.5, 9.0, 9.5]
#   "model_scores": {
#       "Qwen3-30B": 8.5,
#       "Llama-3.3-70B": 9.0,
#       "Mixtral-8x22B": 9.5
#   },
#   "confidence": 0.85  # Agreement level
# }
```

**Aggregation Methods**:
- **Median** - Robust to outliers (default)
- **Mean** - Average across models
- **Weighted** - Trust better models more

**Use Cases**:
- Critical datasets (medical, legal, safety)
- Research requiring highest quality
- When compute budget allows

**Cost Analysis**:
- 3x slower than single model
- 3x compute cost (parallel) or 9x (sequential)
- Higher confidence and accuracy

---

## 6. Tulu3Scorer

**Purpose**: Reference implementation from Tulu3 paper

**Speed**: Fast (1.0-1.5 ex/s)

**How It Works**:
```python
from training_metrics import Tulu3Scorer

scorer = Tulu3Scorer()
score = scorer.score({
    "instruction": "Summarize the main causes of WWI",
    "response": "The main causes were militarism, alliances..."
})
# Returns: {
#   "helpfulness": 4,  # 1-5 scale
#   "accuracy": 5,
#   "clarity": 4,
#   "completeness": 4,
#   "composite": 8.5  # Normalized to 1-10
# }
```

**Quality Dimensions** (1-5 scale each):
- **Helpfulness** - Addresses instruction
- **Accuracy** - Factually correct
- **Clarity** - Well-explained
- **Completeness** - All aspects covered

**Composite Score**:
```python
composite = (helpfulness + accuracy + clarity + completeness) / 2.0
# Range: 1-10 (sum of 4-20 divided by 2)
```

**Use Cases**:
- Reproducing Tulu3 paper results
- Baseline for new scoring methods
- Standardized quality benchmarking

**Reference**: Allen Institute Tulu3 paper (training_metrics.py implementation)

---

## Choosing a Scorer

| Requirement | Recommended Scorer |
|-------------|-------------------|
| **Large dataset (>1M examples)** | FastIFD |
| **Balanced speed/quality** | QualityScorer |
| **Detailed metrics needed** | MultiDimensional |
| **Cloud models required** | LLMQuality |
| **Highest accuracy** | Ensemble |
| **Tulu3 reproducibility** | Tulu3Scorer |

---

## Performance Benchmarks

### Single Machine (M4 Max)

| Scorer | Speed (ex/s) | 100K examples | Memory |
|--------|-------------|---------------|--------|
| FastIFD | 15-20 | ~90 min | 4 GB |
| Quality | 0.85 | ~33 hours | 30 GB |
| MultiDim | 0.60 | ~46 hours | 30 GB |
| LLMQuality | 0.85 | ~33 hours | Variable |
| Ensemble | 0.25 | ~4.6 days | 90 GB |
| Tulu3 | 1.2 | ~23 hours | 25 GB |

### Distributed (2x M4 Max)

| Scorer | Combined Speed | 100K examples | Scaling |
|--------|---------------|---------------|---------|
| FastIFD | 30-40 ex/s | ~45 min | Linear |
| Quality | 1.7 ex/s | ~16 hours | Linear |
| MultiDim | 1.2 ex/s | ~23 hours | Linear |

---

## Implementation Notes

### Path Safety (CWE-22)

```python
from pathlib import Path

def load_data_safe(data_path: str) -> list:
    """Load data with path traversal protection."""
    path = Path(data_path).resolve()
    allowed_dir = Path("/data/training").resolve()

    if not str(path).startswith(str(allowed_dir)):
        raise ValueError(f"Path outside allowed directory: {path}")

    return [json.loads(line) for line in path.read_text().splitlines()]
```

### Input Validation (CWE-20)

```python
def validate_score(score: dict) -> bool:
    """Validate score ranges."""
    if "quality_score" in score:
        if not 1 <= score["quality_score"] <= 10:
            raise ValueError(f"Quality score out of range: {score['quality_score']}")

    if "ifd_score" in score:
        if not 0.0 <= score["ifd_score"] <= 1.0:
            raise ValueError(f"IFD score out of range: {score['ifd_score']}")

    return True
```

---

## Related Documentation

- `quality-dimensions.md` - Detailed dimension definitions
- `training-thresholds.md` - Threshold guidance by training type
- **data-distillation** skill - IFD methodology
- **preference-data-quality** skill - DPO/RLVR metrics
