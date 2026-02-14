# RLVR (Reinforcement Learning with Verifiable Rewards) Assessment

Assess dataset suitability for RLVR training approach.

## Overview

RLVR requires task outputs to be automatically verifiable. Assessment determines if dataset meets ≥80% verifiability threshold.

## Verifiability by Domain

### Highly Verifiable (90-100%)

**Math and Reasoning**:
- Symbolic expressions: `2+2=4` (exact match)
- Logical proofs: Step-by-step validation
- Arithmetic: Deterministic evaluation

**Coding**:
- Unit tests: `assert add(2, 3) == 5`
- Static analysis: Syntax checking
- Integration tests: End-to-end validation

**Automated checks**: ✓ (no human verification needed)

### Moderately Verifiable (80-90%)

**General Knowledge**:
- Factual questions: Cross-reference databases
- Structured outputs: JSON/XML validation
- Classification: Ground truth labels

**Automated checks**: Partial (some human verification)

### Poorly Verifiable (<80%)

**Creative Tasks**:
- Story writing: Subjective quality
- Poetry: Aesthetic evaluation
- Art descriptions: Personal interpretation

**Opinion-Based**:
- Ethical judgments: No single correct answer
- Preferences: Subjective by definition
- Open-ended discussions: Multiple valid responses

**Automated checks**: ✗ (unsuitable for RLVR)

## Implementation

### Using training_metrics.py

```python
from pathlib import Path
from training_metrics import assess_rlvr_verifiability

# Assess RLVR suitability
dataset_path = Path("data/math_problems.jsonl")
assessment = assess_rlvr_verifiability(dataset_path, domain="math")

# Check suitability
if assessment.is_suitable:
    print(f"Dataset suitable for RLVR ({assessment.verifiable_percentage:.1%} verifiable)")
else:
    print(f"Dataset unsuitable ({assessment.verifiable_percentage:.1%} < 80%)")

# Print details
print(f"Domain: {assessment.domain}")
print(f"Automated checks: {assessment.automated_checks}")
print(f"Human verification: {assessment.human_verification_required}")
```

### Dataset Format

JSONL with problem/solution/verifiable fields:

```jsonl
{"problem": "2+2", "solution": "4", "verifiable": true}
{"problem": "Solve x^2=4", "solution": "x=2 or x=-2", "verifiable": true}
```

## Domain-Specific Guidelines

### Math Domain

```python
assessment = assess_rlvr_verifiability(path, domain="math")
# Expected: 95-100% verifiable
```

**Verification methods**:
- Symbolic math libraries (SymPy)
- Numerical approximation
- Unit testing for algorithms

### Reasoning Domain

```python
assessment = assess_rlvr_verifiability(path, domain="reasoning")
# Expected: 85-95% verifiable
```

**Verification methods**:
- Logical proof checkers
- Constraint satisfaction solvers
- Graph algorithms for logic puzzles

### Coding Domain

```python
assessment = assess_rlvr_verifiability(path, domain="coding")
# Expected: 90-95% verifiable
```

**Verification methods**:
- Unit tests (pytest, unittest)
- Static analysis (mypy, pylint)
- Integration tests

## Best Practices

1. **Choose verifiable domains**: Math, reasoning, coding
2. **Design automated checks**: Unit tests, validators
3. **Measure verifiability**: Track percentage during collection
4. **Filter unverifiable**: Remove subjective tasks
5. **Document verification**: Specify how outputs are checked

## Unsuitable Tasks for RLVR

Avoid these for RLVR training:
- Creative writing (subjective)
- Ethical dilemmas (no single answer)
- Aesthetic judgments (personal preference)
- Open-ended conversations (multiple valid responses)

Use DPO or RLHF instead for these tasks.

## Related

- See `training_metrics.py` for implementation
- See `dpo-metrics.md` for preference-based approaches
- External: SymPy for math verification
- External: pytest for code verification
