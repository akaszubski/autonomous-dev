# Stage 4: Persona Evaluation

Build system to measure trait adherence and style consistency.

## Overview
Implement automated evaluation of persona characteristics.

## Metrics
1. **Trait Adherence**: Presence of core traits (≥90%)
2. **Style Variance**: Consistency in voice (<15%)
3. **Consistency Score**: Overall persona maintenance (≥85%)

## Implementation
```python
def evaluate_trait_adherence(output: str, traits: list) -> dict:
    """Measure presence of each core trait."""
    scores = {}
    for trait in traits:
        scores[trait] = detect_trait(output, trait)
    return scores
```

## Quality Gate
- Trait adherence ≥90%
- Style variance <15%
- Evaluation reliable

**See**: `../templates.md` for evaluation implementation.
