# Stage 3: Automated Verification

Build robust verification system with low false positive rate.

## Overview
Implement verification logic that accurately judges task completion.

## Requirements

1. **Objective**: No subjective judgment
2. **Deterministic**: Same input → same output
3. **Robust**: Handles edge cases
4. **Fast**: Verification in seconds, not minutes
5. **Low FP**: False positive rate <5%

## Implementation

**Coding Verification**:
```python
def verify_code(solution: str, tests: list) -> bool:
    """Execute solution against test suite."""
    try:
        # Sandbox execution
        result = execute_in_sandbox(solution, tests, timeout=10)
        return all(test.passed for test in result)
    except TimeoutError:
        return False
    except Exception:
        return False
```

**Math Verification**:
```python
import sympy

def verify_math(solution: str, expected: str) -> bool:
    """Symbolic comparison of math answers."""
    try:
        sol_expr = sympy.sympify(solution)
        exp_expr = sympy.sympify(expected)
        return sympy.simplify(sol_expr - exp_expr) == 0
    except:
        return False
```

## Quality Gate
- False positive rate <5%
- Verification coverage ≥90%
- Fast execution (<10s per task)

**See**: `../templates.md` for complete verification examples.
