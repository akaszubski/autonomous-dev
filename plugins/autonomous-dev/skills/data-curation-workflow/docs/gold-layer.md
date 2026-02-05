# Gold Layer

Specialized data generation, mixing, and final validation stages.

## Stage 7: Generate (Specialized Data)

### DPO Pair Generation

```python
class RefusalDPOPairGenerator:
    """Generate DPO pairs for refusal training."""

    def __init__(
        self,
        model: str = "anthropic/claude-3.5-sonnet",
        min_gap: float = 3.0
    ):
        """
        Args:
            model: Model for generation
            min_gap: Minimum score gap between chosen/rejected
        """

    def generate(self, prompts: List[str]) -> List[Dict]:
        """Generate chosen (refusal) vs rejected (hallucination) pairs."""
```

### RLVR Trace Generation

```python
class FinanceRLVRGenerator:
    """Generate RLVR traces for finance domain."""

    def __init__(
        self,
        verifier: str = "sandbox",
        domain: str = "finance"
    ):
        """
        Args:
            verifier: Verification method (sandbox, regex, api)
            domain: Domain for verification rules
        """

    def generate(self, problems: List[Dict]) -> List[Dict]:
        """Generate traces with step-by-step verification."""
```

### Anti-Hallucination Generation

```python
class AntiHallucinationGenerator:
    """Generate refusal and uncertainty examples."""

    def __init__(
        self,
        refusal_ratio: float = 0.4,
        uncertainty_ratio: float = 0.3,
        confident_ratio: float = 0.2,
        edge_case_ratio: float = 0.1
    ):
        """
        Args:
            refusal_ratio: Proportion of refusal examples
            uncertainty_ratio: Proportion of hedged examples
            confident_ratio: Proportion of confident examples
            edge_case_ratio: Proportion of edge cases
        """

    def generate(self, num_examples: int) -> List[Dict]:
        """Generate anti-hallucination training examples."""
```

### Generation Data Types

| Type | Generator | Use Case |
|------|-----------|----------|
| DPO pairs | `RefusalDPOPairGenerator` | Preference alignment |
| Finance DPO | `FinanceDPOGenerator` | Financial domain |
| Finance RLVR | `FinanceRLVRGenerator` | Financial reasoning |
| Code RLVR | `CodeRLVRGenerator` | Code correctness |
| Math RLVR | `MathRLVRGenerator` | Math verification |
| Anti-hallucination | `AntiHallucinationGenerator` | Calibration |

---

## Stage 8: Mix (Weighted Combination)

### DatasetMixer

```python
class DatasetMixer:
    """Weighted dataset mixing with curriculum scheduling."""

    def __init__(
        self,
        curriculum: str = "staged"
    ):
        """
        Args:
            curriculum: Mixing strategy
                - "uniform": Equal sampling from all sources
                - "staged": SFT first, then DPO, then RLVR
                - "domain-balanced": Equal domain representation
        """

    def mix(
        self,
        inputs: Dict[str, Path],
        weights: Dict[str, float],
        output_path: Path
    ) -> Dict:
        """Mix datasets with specified weights."""
```

### Recommended Mix Weights

| Data Type | Weight | Epoch Order | Rationale |
|-----------|--------|-------------|-----------|
| SFT | 50% | First | Base instruction following |
| DPO | 25% | Second | Preference alignment |
| RLVR | 15% | Third | Reasoning improvement |
| Anti-hall | 10% | Last | Calibration |

### Curriculum Strategies

**Uniform**: Random sampling proportional to weights
```python
weights = {"sft": 0.5, "dpo": 0.25, "rlvr": 0.15, "antihall": 0.1}
# Each batch contains mixed data according to weights
```

**Staged**: Sequential exposure
```python
stages = [
    {"data": "sft", "epochs": 2},
    {"data": "dpo", "epochs": 1},
    {"data": "rlvr", "epochs": 1},
    {"data": "antihall", "epochs": 0.5}
]
# Train on SFT first, then DPO, etc.
```

**Domain-balanced**: Equal domain representation
```python
domains = ["math", "code", "general", "finance"]
# Each batch contains equal samples from each domain
```

---

## Stage 9: Validate (Final QA)

### ValidationPipeline

```python
class ValidationPipeline:
    """Final validation checks before training."""

    def __init__(
        self,
        checks: List[str] = None
    ):
        """
        Args:
            checks: List of validation checks to run
                Default: ["format", "contamination", "bias", "duplicates", "poisoning"]
        """

    def validate(self, input_path: Path) -> Dict:
        """Run all validation checks and generate report."""
```

### Validation Checks

| Check | Description | Failure Action |
|-------|-------------|----------------|
| Format | JSON schema compliance | Reject malformed |
| Contamination | Re-check benchmark overlap | Remove contaminated |
| Bias | Demographic/topic bias detection | Flag for review |
| Duplicates | Final duplicate check | Remove duplicates |
| Poisoning | Data poisoning detection | Reject dataset |

### Poisoning Detection

```python
def detect_data_poisoning(dataset_path: Path) -> Dict:
    """Detect potential data poisoning attacks.

    Checks for:
    - Abnormal token distributions
    - Suspicious patterns (repeated strings, encoded payloads)
    - Statistical outliers
    - Known attack signatures

    Returns:
        Dict with poisoning_detected (bool), confidence, and details
    """
```

### Validation Report Schema

```json
{
  "validation_status": "PASSED",
  "total_examples": 85000,
  "checks": {
    "format": {"passed": 85000, "failed": 0},
    "contamination": {"passed": 84800, "failed": 200},
    "bias": {"flagged": 150, "severity": "low"},
    "duplicates": {"unique": 84600, "duplicates": 200},
    "poisoning": {"detected": false, "confidence": 0.95}
  },
  "final_count": 84600,
  "recommendations": [
    "Review 150 flagged bias examples",
    "200 examples removed for benchmark contamination"
  ]
}
```

---

## Gold Layer Pipeline

```bash
# Complete Gold Layer
python -m realign.data.pipeline gold \
  --input silver_output/6_filtered.jsonl \
  --output gold_output/ \
  --mix-weights "sft:0.5,dpo:0.25,rlvr:0.15,antihall:0.1" \
  --curriculum staged \
  --checkpoint gold_checkpoint.json
```

### Checkpoint State

```json
{
  "layer": "gold",
  "stages_completed": ["7_generate", "8_mix"],
  "stage_stats": {
    "7_generate": {
      "dpo_pairs": 15000,
      "rlvr_traces": 8000,
      "antihall_examples": 5000,
      "total_generated": 28000
    },
    "8_mix": {
      "sft": 42000,
      "dpo": 15000,
      "rlvr": 8000,
      "antihall": 5000,
      "total_mixed": 70000
    }
  }
}
```

---

## Output: A-Grade Training Dataset

Final output meets these quality criteria:

| Metric | Target | Actual |
|--------|--------|--------|
| IFD score | ≥0.6 | 0.72 |
| Quality score | ≥8.0 | 8.4 |
| Duplicate rate | <1% | 0.3% |
| Contamination | 0% | 0% |
| Poisoning | None | None |
