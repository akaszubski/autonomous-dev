---
name: testing-guide
type: knowledge
description: Complete testing methodology - TDD, progression tracking, regression prevention, and test patterns
keywords: test, testing, tdd, pytest, coverage, baseline, progression, regression, quality
auto_activate: true
---

# Complete Testing Guide

**Purpose**: Unified testing methodology covering TDD, progression tracking, and regression prevention.

**Auto-activates when**: Keywords like "test", "tdd", "coverage", "baseline", "progression", "regression" appear.

---

## Three Testing Approaches

### 1. TDD (Test-Driven Development)
**Purpose**: Write tests BEFORE implementation
**When**: New features, refactoring, coverage gaps
**Location**: `tests/unit/` and `tests/integration/`

### 2. Progression Testing
**Purpose**: Track metrics over time, prevent regressions
**When**: Optimizing performance, training models
**Location**: `tests/progression/`

### 3. Regression Testing
**Purpose**: Ensure fixed bugs never return
**When**: After bug fixes
**Location**: `tests/regression/`

---

## TDD Methodology

### Core Principle
**Red → Green → Refactor**

1. **Red**: Write failing test (feature doesn't exist yet)
2. **Green**: Implement minimum code to make test pass
3. **Refactor**: Clean up code while keeping tests green

### TDD Workflow

**Step 1: Write Test First**
```python
# tests/unit/test_trainer.py

def test_train_lora_with_valid_params():
    """Test LoRA training succeeds with valid parameters."""
    result = train_lora(
        model="[model_repo]/Llama-3.2-1B-Instruct-4bit",
        data="data/sample.json",
        rank=8
    )

    assert result.success is True
    assert result.adapter_path.exists()
```

**Step 2: Run Test (Should FAIL)**
```bash
pytest tests/unit/test_trainer.py::test_train_lora_with_valid_params -v
# FAILED - NameError: 'train_lora' not defined ✅ Expected!
```

**Step 3: Implement Code**
```python
# src/[project_name]/methods/lora.py

def train_lora(model: str, data: str, rank: int = 8):
    """Train LoRA adapter."""
    # Minimum implementation to pass test
    ...
    return Result(success=True, adapter_path=Path("adapter.npz"))
```

**Step 4: Run Test (Should PASS)**
```bash
pytest tests/unit/test_trainer.py::test_train_lora_with_valid_params -v
# PASSED ✅
```

### Test Coverage Standards

**Minimum**: 80% coverage
**Target**: 90%+ coverage

**Check coverage**:
```bash
pytest --cov=src/[project_name] --cov-report=term-missing tests/
```

### Test Patterns

**Arrange-Act-Assert (AAA)**:
```python
def test_example():
    # Arrange: Set up test data
    model = load_model()
    data = load_test_data()

    # Act: Execute the operation
    result = train_model(model, data)

    # Assert: Verify expected outcome
    assert result.success is True
```

**Parametrize for multiple cases**:
```python
@pytest.mark.parametrize("rank,expected_params", [
    (8, 8 * 4096 * 2),
    (16, 16 * 4096 * 2),
    (32, 32 * 4096 * 2),
])
def test_lora_parameter_count(rank, expected_params):
    adapter = create_lora_adapter(rank=rank)
    assert adapter.num_parameters == expected_params
```

---

## Progression Testing

### Purpose
Track metrics over time, automatically detect regressions.

### How It Works

1. **First Run**: Establish baseline
2. **Subsequent Runs**: Compare to baseline
3. **Regression**: Test FAILS if metric drops >tolerance
4. **Progression**: Baseline updates if metric improves >2%

### Baseline File Format

```json
{
  "metric_name": "lora_accuracy",
  "baseline_value": 0.856,
  "tolerance": 0.05,
  "established_at": "2025-10-18T10:30:00",
  "history": [
    {"date": "2025-10-18", "value": 0.856, "change": "baseline established"},
    {"date": "2025-10-20", "value": 0.872, "change": "+1.9% improvement"}
  ]
}
```

### Progression Test Template

```python
# tests/progression/test_lora_accuracy.py

import json
import pytest
from pathlib import Path
from datetime import datetime

BASELINE_FILE = Path(__file__).parent / "baselines" / "lora_accuracy_baseline.json"
TOLERANCE = 0.05  # ±5%

class TestProgressionLoRAAccuracy:
    @pytest.fixture
    def baseline(self):
        if BASELINE_FILE.exists():
            return json.loads(BASELINE_FILE.read_text())
        return None

    def test_lora_accuracy_progression(self, baseline):
        # Measure current metric
        current_accuracy = self._train_and_evaluate()

        # First run - establish baseline
        if baseline is None:
            self._establish_baseline(current_accuracy)
            pytest.skip(f"Baseline established: {current_accuracy:.4f}")

        # Compare to baseline
        baseline_value = baseline["baseline_value"]
        diff_pct = ((current_accuracy - baseline_value) / baseline_value) * 100

        # Check for regression
        if diff_pct < -TOLERANCE * 100:
            pytest.fail(f"REGRESSION: {abs(diff_pct):.1f}% worse than baseline")

        # Check for progression
        if diff_pct > 2.0:
            self._update_baseline(current_accuracy, diff_pct, baseline)

        print(f"✅ Accuracy: {current_accuracy:.4f} ({diff_pct:+.1f}%)")

    def _train_and_evaluate(self) -> float:
        # Your measurement logic here
        pass

    def _establish_baseline(self, value: float):
        # Create baseline file
        pass

    def _update_baseline(self, new_value: float, improvement: float, old_baseline: dict):
        # Update baseline file
        pass
```

### Metrics to Track

| Metric | Higher Better? | Typical Tolerance |
|--------|----------------|-------------------|
| Accuracy | ✅ Yes | ±5% |
| Loss | ❌ No (lower better) | ±5% |
| Training Speed | ✅ Yes | ±10% |
| Memory Usage | ❌ No (lower better) | ±5% |
| Inference Latency | ❌ No (lower better) | ±10% |

---

## Regression Testing

### Purpose
Ensure fixed bugs never return.

### When to Create

- After fixing any bug
- Issue closed with "Closes #123"
- Commit contains "fix:"

### Regression Test Template

```python
# tests/regression/test_regression_suite.py

class TestMLXPatterns:
    """[FRAMEWORK]-specific regression tests."""

    def test_bug_47_mlx_nested_layers(self):
        \"\"\"
        Regression test: [FRAMEWORK] model.layers AttributeError

        Bug: Code tried model.layers[i] (doesn't exist)
        Fix: Use model.model.layers[i] (nested structure)
        Date fixed: 2025-10-18
        Issue: #47

        Ensures bug never returns.
        \"\"\"

        # Arrange
        model = create_mock_mlx_model()

        # Act & Assert: Correct way works
        layer = model.model.layers[0]
        assert layer is not None

        # Assert: Wrong way fails (bug would use this)
        with pytest.raises(AttributeError):
            _ = model.layers
```

### Test Organization

```python
# tests/regression/test_regression_suite.py

class TestMLXPatterns:
    """[FRAMEWORK]-specific bugs."""
    pass

class TestDataProcessing:
    """Data handling bugs."""
    pass

class TestAPIIntegration:
    """External API bugs."""
    pass

class TestErrorHandling:
    """Error handling bugs."""
    pass
```

---

## Test Organization

### Directory Structure

```
tests/
├── unit/                    # TDD unit tests
│   ├── test_trainer.py
│   ├── test_lora.py
│   └── test_dpo.py
├── integration/             # TDD integration tests
│   └── test_training_pipeline.py
├── progression/             # Baseline tracking
│   ├── test_lora_accuracy.py
│   ├── test_training_speed.py
│   └── baselines/
│       └── *.json
└── regression/              # Bug prevention
    ├── test_regression_suite.py
    └── README.md
```

### Naming Conventions

**Test Files**: `test_{module}.py`
**Test Functions**: `test_{what_is_being_tested}()`
**Test Classes**: `Test{Feature}`

**Examples**:
- `test_trainer.py` - Tests for trainer module
- `test_train_lora_with_valid_params()` - Specific test
- `TestProgressionLoRAAccuracy` - Progression test class

---

## Best Practices

### ✅ DO

1. **Write tests first** (TDD)
2. **Test one thing per test** (focused)
3. **Use descriptive names** (`test_train_lora_raises_error_on_invalid_model`)
4. **Arrange-Act-Assert** pattern
5. **Mock external dependencies** (APIs, files)
6. **Test edge cases** (empty data, None, negative numbers)
7. **Keep tests fast** (<1 second each)
8. **Maintain 80%+ coverage**

### ❌ DON'T

1. **Don't test implementation details** (test behavior, not internal code)
2. **Don't have test dependencies** (tests should be isolated)
3. **Don't hardcode paths** (use fixtures, temporary directories)
4. **Don't skip tests** (fix them or delete them)
5. **Don't write tests after implementation** (that's not TDD!)
6. **Don't test third-party libraries** (trust they're tested)
7. **Don't ignore failing tests** (fix immediately)

---

## Pytest Fixtures

### Common Fixtures

```python
# conftest.py

import pytest
from pathlib import Path
import tempfile

@pytest.fixture
def temp_dir():
    """Temporary directory for test files."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)

@pytest.fixture
def sample_data():
    """Sample training data."""
    return {
        "messages": [
            {"role": "user", "content": "Hello"},
            {"role": "assistant", "content": "Hi there!"}
        ]
    }

@pytest.fixture
def mock_model():
    """Mock [FRAMEWORK] model."""
    class MockModel:
        def __init__(self):
            self.model = type('obj', (object,), {'layers': []})()
    return MockModel()
```

---

## Coverage Targets

### By Test Type

| Test Type | Target Coverage |
|-----------|-----------------|
| Unit | 90%+ |
| Integration | 70%+ |
| Progression | N/A (metric tracking) |
| Regression | N/A (bug prevention) |

### Overall Project

- **Minimum**: 80% (enforced in CI/CD)
- **Target**: 90%
- **Stretch**: 95%

### Check Coverage

```bash
# Run tests with coverage
pytest --cov=src/[project_name] --cov-report=html tests/

# Open coverage report
open htmlcov/index.html

# Show missing lines
pytest --cov=src/[project_name] --cov-report=term-missing tests/
```

---

## CI/CD Integration

### Pre-Push Hook

```bash
# Run all tests before push
pytest tests/ -v

# Check coverage
pytest --cov=src/[project_name] --cov-report=term --cov-fail-under=80 tests/
```

### GitHub Actions

```yaml
- name: Run Tests
  run: |
    pytest tests/ -v --cov=src/[project_name] --cov-report=xml

- name: Upload Coverage
  uses: codecov/codecov-action@v3
  with:
    files: ./coverage.xml
```

---

## Quick Reference

### Test Types Decision Matrix

| Scenario | Test Type | Location |
|----------|-----------|----------|
| New feature | **TDD** | tests/unit/ |
| Optimize performance | **Progression** | tests/progression/ |
| Fixed bug | **Regression** | tests/regression/ |
| Multiple components | **Integration** | tests/integration/ |

### Running Tests

```bash
# All tests
pytest tests/

# Specific file
pytest tests/unit/test_trainer.py

# Specific test
pytest tests/unit/test_trainer.py::test_train_lora

# With coverage
pytest --cov=src/[project_name] tests/

# Verbose output
pytest -v tests/

# Stop on first failure
pytest -x tests/

# Parallel execution
pytest -n auto tests/
```

---

**This skill provides complete testing methodology for maintaining high-quality, well-tested code in [PROJECT_NAME].**
