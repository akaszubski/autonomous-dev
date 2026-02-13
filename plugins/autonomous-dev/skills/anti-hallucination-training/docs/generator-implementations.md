# Generator Implementations

API documentation for anti-hallucination data generators.

## AntiHallucinationGenerator

```python
class AntiHallucinationGenerator:
    """Generate refusal and uncertainty examples."""

    def __init__(
        self,
        model: str = "anthropic/claude-3.5-sonnet",
        refusal_ratio: float = 0.4,
        uncertainty_ratio: float = 0.3,
        confident_ratio: float = 0.2,
        edge_case_ratio: float = 0.1
    ):
        """
        Initialize generator with data type ratios.

        Args:
            model: Model to use for generation
            refusal_ratio: Proportion of refusal examples (default 0.4)
            uncertainty_ratio: Proportion of hedged examples (default 0.3)
            confident_ratio: Proportion of confident examples (default 0.2)
            edge_case_ratio: Proportion of edge cases (default 0.1)
        """

    def generate(self, num_examples: int) -> List[Dict]:
        """Generate anti-hallucination training examples."""
```

## RefusalPreferenceGenerator

```python
class RefusalPreferenceGenerator:
    """Generate DPO-format preference pairs for refusal training."""

    def __init__(self, refusal_style: str = "polite"):
        """
        Args:
            refusal_style: "polite", "direct", or "explanatory"
        """

    def generate_pair(self, prompt: str) -> Dict:
        """Generate chosen (refusal) vs rejected (hallucination) pair."""
```

## CalibrationTrainer

```python
class CalibrationTrainer:
    """Train confidence calibration with temperature scaling."""

    def __init__(self, initial_temperature: float = 1.5):
        """
        Args:
            initial_temperature: Starting temperature for scaling
        """

    def fit(self, validation_data: Path) -> float:
        """Fit temperature to minimize ECE. Returns optimal temperature."""
```

## Error Handling

All generators raise:
- `ValueError`: Invalid ratios (must sum to 1.0)
- `FileNotFoundError`: Input file not found
- `JSONDecodeError`: Malformed input data
