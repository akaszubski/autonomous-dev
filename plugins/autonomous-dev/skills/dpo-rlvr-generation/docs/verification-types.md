# Verification Types

Complete taxonomy of verification methods for RLVR data generation.

## Core Principle

**Automated verification must be objective, deterministic, and verifiable.**

Rewards should be calculated automatically without human judgment.

---

## Verification Type Taxonomy

### 1. Math Verification

**Use Case**: Symbolic math problems, equations, algebraic reasoning

**Verifiability**: 95%+ (highest of all types)

**Implementation**:
```python
from realign.data.math_rlvr_generator import MathRLVRGenerator

generator = MathRLVRGenerator()
data = generator.generate(
    input_file="math_problems.jsonl",
    output_file="math_rlvr.jsonl",
    verification_type="math"
)
```

**Output Format**:
```json
{
  "task": "Solve for x: 2x + 5 = 13",
  "solution": "x = 4",
  "verification": {
    "type": "math",
    "symbolic": "2*x + 5 = 13",
    "expected": 4,
    "tolerance": null
  }
}
```

**Verification Logic**:
```python
import sympy as sp

def verify_math_solution(solution: str, expected: float) -> bool:
    """Verify math solution using symbolic manipulation."""
    x = sp.Symbol('x')
    equation = sp.Eq(2*x + 5, 13)
    actual_solution = sp.solve(equation, x)[0]
    return abs(float(actual_solution) - expected) < 1e-6
```

**Best For**: Algebra, calculus, symbolic manipulation, proofs

**Limitations**:
- Requires symbolic representation
- May fail on approximate numerical solutions
- Needs SymPy or similar library

---

### 2. Code Verification

**Use Case**: Code generation tasks, algorithm implementation

**Verifiability**: 90%+ (second highest)

**Implementation**:
```python
from realign.data.code_rlvr_generator import CodeRLVRGenerator

generator = CodeRLVRGenerator()
data = generator.generate(
    input_file="coding_tasks.jsonl",
    output_file="code_rlvr.jsonl",
    verification_type="code"
)
```

**Output Format**:
```json
{
  "task": "Write a function to reverse a string",
  "solution": "def reverse(s):\n    return s[::-1]",
  "verification": {
    "type": "code",
    "tests": [
      "assert reverse('hello') == 'olleh'",
      "assert reverse('') == ''",
      "assert reverse('a') == 'a'"
    ]
  }
}
```

**Verification Logic**:
```python
import subprocess
import tempfile

def verify_code_solution(solution: str, tests: List[str]) -> bool:
    """Verify code solution via test suite execution."""
    with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
        f.write(solution + '\n')
        for test in tests:
            f.write(test + '\n')
        f.flush()

        # Execute in sandbox
        result = subprocess.run(
            ['python', f.name],
            capture_output=True,
            timeout=5
        )
        return result.returncode == 0
```

**Best For**: Functions, algorithms, data structures, small programs

**Limitations**:
- Requires sandboxed execution environment
- Timeout handling needed
- May have side effects (file I/O, network)

**Security Note**: Always run in isolated sandbox (Docker, VM, or restricted environment).

---

### 3. Custom Verification

**Use Case**: Domain-specific verification logic

**Verifiability**: Variable (depends on implementation)

**Implementation**:
```python
from realign.data.custom_rlvr_generator import CustomRLVRGenerator

def finance_verifier(solution: str, expected: dict) -> bool:
    """Custom verifier for finance calculations."""
    # Parse solution
    result = parse_finance_solution(solution)

    # Verify ROI calculation
    if expected['type'] == 'roi':
        calculated_roi = result['roi']
        expected_roi = expected['value']
        return abs(calculated_roi - expected_roi) < 0.01

    return False

generator = CustomRLVRGenerator(verifier=finance_verifier)
data = generator.generate(
    input_file="finance_tasks.jsonl",
    output_file="finance_rlvr.jsonl",
    verification_type="custom"
)
```

**Output Format**:
```json
{
  "task": "Calculate ROI: Initial $10,000, Final $12,500",
  "solution": "ROI = (Final - Initial) / Initial = (12500 - 10000) / 10000 = 0.25 = 25%",
  "verification": {
    "type": "custom",
    "verifier": "finance_roi",
    "expected": {"type": "roi", "value": 0.25},
    "tolerance": 0.01
  }
}
```

**Best For**: Domain-specific logic, multi-step procedures, business rules

**Limitations**:
- Requires custom implementation
- May be less reliable than math/code
- Needs thorough testing

---

## Verification Requirements

### Determinism

**Requirement**: Same input → Same verification result

**Anti-Pattern**: Random sampling, external API calls

```python
# ❌ BAD: Non-deterministic
def verify_bad(solution):
    return random.random() > 0.5  # Different results each time

# ✅ GOOD: Deterministic
def verify_good(solution, expected):
    return solution == expected  # Same result every time
```

### Objectivity

**Requirement**: No subjective judgment

**Anti-Pattern**: Quality assessment, stylistic preferences

```python
# ❌ BAD: Subjective
def verify_bad(solution):
    return "looks good" in solution  # Subjective judgment

# ✅ GOOD: Objective
def verify_good(solution, expected):
    return abs(solution - expected) < 1e-6  # Numerical comparison
```

### Speed

**Requirement**: Fast verification (<1 second per example)

**Anti-Pattern**: Complex simulations, expensive computations

```python
# ❌ BAD: Slow (10+ seconds)
def verify_bad(solution):
    # Monte Carlo simulation with 1M samples
    return monte_carlo_verify(solution, samples=1_000_000)

# ✅ GOOD: Fast (<1 second)
def verify_good(solution, expected):
    return solution == expected  # Instant
```

---

## Verifiability Scoring

From **realign-rlvr-workflow** skill:

**Target**: ≥80% verifiability

**Measurement**:
```python
from training_metrics import assess_rlvr_verifiability

# Assess dataset verifiability
verifiable = assess_rlvr_verifiability(
    data_path=Path("rlvr_tasks.jsonl"),
    domain="math"
)

print(f"Verifiability: {verifiable:.2%}")

# Domain-specific thresholds
thresholds = {
    "math": 0.95,
    "code": 0.90,
    "finance": 0.85,
    "general": 0.80
}

assert verifiable >= thresholds[domain], f"Verifiability too low for {domain}"
```

---

## False Positive Prevention

**Target**: <5% false positive rate

**Definition**: Incorrect verification (gives reward when shouldn't)

**Prevention Strategies**:

1. **Multiple test cases** - Don't rely on single test
2. **Edge case coverage** - Test boundary conditions
3. **Error handling** - Catch exceptions, timeouts
4. **Validation suite** - Pre-validate verifier on known examples

**Example**:
```python
def verify_with_multiple_tests(solution: str, tests: List[str]) -> bool:
    """Run multiple tests to reduce false positives."""
    passed = 0
    for test in tests:
        if run_test(solution, test):
            passed += 1

    # Require all tests to pass (strict)
    return passed == len(tests)
```

---

## Integration with Training Workflow

From **realign-rlvr-workflow** skill Stage 4:

```python
# Generate RLVR data with verification
generator = MathRLVRGenerator()
data = generator.generate(
    input_file="math_problems.jsonl",
    output_file="rlvr.jsonl",
    verification_type="math"
)

# Validate verifiability
verifiable = assess_rlvr_verifiability(
    data_path=Path("rlvr.jsonl"),
    domain="math"
)

if verifiable < 0.8:
    raise ValueError("Verifiability too low - redesign tasks")

# Proceed to Stage 5: RLVR Optimization
```

---

## Best Practices

### Math Verification

1. Use symbolic libraries (SymPy, SageMath)
2. Normalize representations (simplify expressions)
3. Handle floating-point tolerance (±1e-6)
4. Validate symbolic equivalence (not just numerical)

### Code Verification

1. Run in sandboxed environment (Docker, restricted subprocess)
2. Set execution timeouts (5 seconds max)
3. Capture both stdout and stderr
4. Validate syntax before execution
5. Use multiple test cases (3-5 per task)

### Custom Verification

1. Document verification logic clearly
2. Test verifier on known examples (100+ samples)
3. Measure false positive/negative rates
4. Handle edge cases explicitly
5. Provide tolerance parameters

---

## Common Issues

| Issue | Detection | Solution |
|-------|-----------|----------|
| **Low verifiability** | Score <80% | Redesign tasks, simplify verification logic |
| **High false positives** | FP >5% | Add test cases, strengthen verification |
| **Slow verification** | >1s per example | Optimize logic, reduce test complexity |
| **Non-deterministic** | Different results on same input | Remove randomness, external dependencies |

---

## Key Takeaways

1. **3 types**: Math (95%+), Code (90%+), Custom (variable)
2. **Requirements**: Deterministic, objective, fast (<1s)
3. **Verifiability target**: ≥80% overall, domain-specific higher
4. **False positives**: <5% target
5. **Best practices**: Multiple tests, edge cases, sandbox for code
6. **Security**: Always sandbox code execution
7. **Integration**: Use training_metrics library for assessment
