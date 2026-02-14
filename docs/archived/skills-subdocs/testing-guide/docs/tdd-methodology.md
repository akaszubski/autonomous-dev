# Tdd Methodology

## Three Testing Approaches (Traditional)

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
