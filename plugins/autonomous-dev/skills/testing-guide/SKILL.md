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

## Three-Layer Testing Strategy ⭐ UPDATED

### Critical Insight

**Layer 1 (pytest)** validates **STRUCTURE** and **BEHAVIOR**
**Layer 2 (GenAI)** validates **INTENT** and **MEANING**
**Layer 3 (Meta-analysis)** validates **SYSTEM PERFORMANCE** and **OPTIMIZATION**

All three layers are needed for complete autonomous system coverage.

---

## Testing Decision Matrix

### Layer 1: When to Use Traditional Tests (pytest)

✅ **BEST FOR**:
- **Fast, deterministic checks** (CI/CD, pre-commit)
- **Binary outcomes** (file exists? count correct? function returns X?)
- **Regression prevention** (catches obvious breaks)
- **Automated validation** (no human needed)
- **Structural correctness** (file format, API signature)
- **Performance benchmarks** (< 100ms response time)
- **Coverage tracking** (80%+ line coverage)

❌ **NOT GOOD FOR**:
- Semantic understanding (does code match intent?)
- Quality assessment (is this "good" code?)
- Architectural alignment (does implementation serve goals?)
- Context-aware decisions (does this fit the project?)

**Examples**:

```python
# ✅ PERFECT for traditional tests
def test_user_creation():
    """Test user is created with email."""
    user = create_user("test@example.com")
    assert user.email == "test@example.com"  # Binary check

def test_file_exists():
    """Test config file exists."""
    assert Path(".env").exists()  # Clear yes/no

def test_api_response_time():
    """Test API responds in < 100ms."""
    start = time.time()
    response = api.get("/users")
    duration = time.time() - start
    assert duration < 0.1  # Measurable benchmark
```

---

### Layer 2: When to Use GenAI Validation (Claude)

✅ **BEST FOR**:
- **Semantic understanding** (does implementation match documented intent?)
- **Behavioral validation** (does agent DO what description says?)
- **Architectural drift detection** (subtle changes in meaning)
- **Quality assessment** (is code maintainable, clear, well-designed?)
- **Context-aware validation** (does this align with PROJECT.md goals?)
- **Intent preservation** (does WHY match WHAT?)
- **Complex reasoning** (trade-offs, design decisions)

❌ **NOT GOOD FOR**:
- Fast CI/CD checks (too slow, requires API calls)
- Deterministic outcomes (slightly different answers each run)
- Simple binary checks (overkill for "does file exist")
- Automated regression tests (needs human review)

**Examples**:

```markdown
# ✅ PERFECT for GenAI validation

## Validate Architectural Intent

Read orchestrator.md. Does it actually validate PROJECT.md before
starting work? Look for:
- File existence checks (bash if statements)
- Reading GOALS/SCOPE/CONSTRAINTS
- Blocking behavior if misaligned
- Clear rejection messages

Don't just check if "PROJECT.md" appears - validate the BEHAVIOR
matches the documented INTENT.

## Assess Code Quality

Review the authentication implementation. Evaluate:
- Is error handling comprehensive?
- Are security best practices followed?
- Is the code maintainable for future developers?
- Does it align with project's security constraints?

Provide contextual assessment with trade-offs.
```

---

### Layer 3: When to Use System Performance Testing (Meta-analysis) ⭐ NEW

✅ **BEST FOR**:
- **Agent effectiveness tracking** (which agents succeed? which fail?)
- **Model optimization** (is Opus needed or can we use Haiku?)
- **Cost efficiency analysis** (are we spending too much per feature?)
- **ROI measurement** (what's the return on investment?)
- **System-level optimization** (how can the autonomous system improve itself?)
- **Resource allocation** (where should we invest more/less?)

❌ **NOT GOOD FOR**:
- Individual feature validation (use Layer 1 or 2)
- Fast feedback loops (takes time to collect data)
- Binary pass/fail checks (provides metrics, not yes/no)

**What it measures**:
```markdown
## Agent Performance
| Agent | Invocations | Success Rate | Avg Time | Cost |
|-------|-------------|--------------|----------|------|
| researcher | 1.8/feature | 100% | 42s | $0.09 |
| planner | 1.0/feature | 100% | 28s | $0.07 |
| implementer | 1.2/feature | 95% | 180s | $0.45 |

## Model Optimization Opportunities
- reviewer: Sonnet → Haiku (save 92%)
- security-auditor: Already Haiku ✅
- doc-master: Already Haiku ✅

## ROI Tracking
- Total cost: $18.70 (22 features)
- Value delivered: $8,800 (88hr × $100/hr)
- ROI: 470× return on investment

## System Performance
- Average cost per feature: $0.85
- Average time per feature: 18 minutes
- Success rate: 95%
- Target: < $1.00/feature, < 20min, > 90%
```

**Commands**:
```bash
/test system-performance              # Run system performance analysis
/test system-performance --track-issues  # Auto-create optimization issues
```

**When to run**:
- Weekly or monthly (not per-feature)
- After major changes to agent pipeline
- When reviewing system costs
- During sprint retrospectives

**See**: [SYSTEM-PERFORMANCE-GUIDE.md](../docs/SYSTEM-PERFORMANCE-GUIDE.md)

---

## Testing Layers: When to Use Which

### Layer 1: Unit Tests (pytest, fast)

**What**: Individual functions in isolation
**When**: Every function with logic
**Speed**: < 1 second total
**CI/CD**: YES, run on every commit

**Example**:
```python
# tests/unit/test_auth.py
def test_hash_password():
    """Test password is hashed."""
    hashed = hash_password("secret123")
    assert hashed != "secret123"  # Binary: not plaintext
    assert len(hashed) == 60  # bcrypt length
```

**Validation Type**: STRUCTURE
- ✅ Fast
- ✅ Deterministic
- ✅ Automated
- ❌ Doesn't check if hashing algorithm is secure

---

### Layer 2: Integration Tests (pytest, medium)

**What**: Components working together
**When**: Testing workflows, API endpoints, database interactions
**Speed**: < 10 seconds total
**CI/CD**: YES, run before merge

**Example**:
```python
# tests/integration/test_user_workflow.py
def test_user_registration_workflow(db):
    """Test complete user registration."""
    # Create user
    user = register_user("test@example.com", "password123")

    # Verify in database
    db_user = db.query(User).filter_by(email="test@example.com").first()
    assert db_user is not None

    # Verify password hashed
    assert db_user.password != "password123"
```

**Validation Type**: BEHAVIOR
- ✅ Tests real workflows
- ✅ Catches integration issues
- ✅ Automated
- ❌ Doesn't validate if workflow serves business goals

---

### Layer 3: UAT Tests (pytest, slow)

**What**: End-to-end user workflows
**When**: Before release, testing complete features
**Speed**: < 60 seconds total
**CI/CD**: Optional, can run nightly

**Example**:
```python
# tests/uat/test_user_journey.py
def test_complete_user_journey(tmp_path):
    """Test user journey: signup → login → create post → logout."""
    # Setup
    app = create_app(tmp_path)

    # Signup
    response = app.post("/signup", data={"email": "user@test.com"})
    assert response.status_code == 201

    # Login
    response = app.post("/login", data={"email": "user@test.com"})
    assert "session_token" in response.cookies

    # Create post
    response = app.post("/posts", json={"title": "Test"})
    assert response.status_code == 201

    # Logout
    response = app.post("/logout")
    assert "session_token" not in response.cookies
```

**Validation Type**: WORKS
- ✅ Tests complete user experience
- ✅ Catches workflow breaks
- ✅ Can be automated (but slow)
- ❌ Doesn't validate if feature aligns with strategic goals

---

### Layer 4: GenAI Validation (Claude, comprehensive)

**What**: Architectural intent, semantic alignment, quality assessment
**When**: Before release, after major changes, monthly maintenance
**Speed**: 2-5 minutes (manual review)
**CI/CD**: NO, requires human review

**Example**:
```markdown
# /validate-architecture

## Validate: Does orchestrator enforce PROJECT.md-first architecture?

Read agents/orchestrator.md and analyze:

1. **Intent (from ARCHITECTURE.md)**:
   "Prevent scope creep by validating alignment before work"

2. **Implementation Analysis**:
   - Does orchestrator check if PROJECT.md exists?
   - Does it read GOALS, SCOPE, CONSTRAINTS?
   - Does it validate feature aligns with goals?
   - Does it block work if misaligned?
   - Does it create PROJECT.md if missing?

3. **Behavioral Evidence**:
   - Line 20: `if [ ! -f PROJECT.md ]` ✓ Checks existence
   - Line 81-83: Reads GOALS/SCOPE/CONSTRAINTS ✓
   - Line 357-391: Displays rejection if misaligned ✓
   - Line 77: `exit 0` blocks work if PROJECT.md missing ✓

**Assessment**: ✅ ALIGNED
Implementation matches documented intent. Orchestrator actually
enforces PROJECT.md-first, not just mentions it.

**Why GenAI?**:
Static test could only check if "PROJECT.md" appears in file.
GenAI validates the BEHAVIOR matches the INTENT.
```

**Validation Type**: INTENT
- ✅ Validates semantic meaning
- ✅ Detects architectural drift
- ✅ Assesses quality and design
- ❌ Slow, requires human review
- ❌ Not deterministic (slight variations)

---

## Recommended Testing Workflow

### Development Phase

1. **Write unit tests** (pytest, fast feedback)
   ```bash
   pytest tests/unit/test_feature.py -v
   ```

2. **Write integration tests** (pytest, workflow validation)
   ```bash
   pytest tests/integration/test_feature.py -v
   ```

3. **Run all tests locally** (before commit)
   ```bash
   pytest -v
   ```

---

### Pre-Commit (Automated)

```bash
# .claude/hooks/pre-commit or CI/CD pipeline
pytest tests/unit/ tests/integration/ -v --tb=short
# Fast: < 10 seconds
# Automated: Catches obvious breaks
```

---

### Pre-Release (Manual)

1. **Run UAT tests** (complete workflows)
   ```bash
   pytest tests/uat/ -v
   ```

2. **GenAI architectural validation** (intent alignment)
   ```bash
   /validate-architecture
   ```

3. **Manual testing** (critical user paths)

---

## Hybrid Approach: Best of Both Worlds

### Example: Testing Orchestrator

#### Static Tests (pytest) - Layer 1

```python
# tests/test_architecture.py
def test_orchestrator_exists():
    """Test orchestrator agent file exists."""
    assert (agents_dir / "orchestrator.md").exists()

def test_orchestrator_has_task_tool():
    """Test orchestrator can coordinate agents."""
    content = (agents_dir / "orchestrator.md").read_text()
    assert "Task" in content
```

**Catches**: File deletion, obvious regressions
**Misses**: Whether orchestrator actually uses Task tool correctly

---

#### GenAI Validation (Claude) - Layer 4

```markdown
Read orchestrator.md. Validate:

1. Does it use Task tool to coordinate agents?
2. Does it coordinate in correct order (researcher → planner → test-master → implementer)?
3. Does it enforce TDD (tests before code)?
4. Does it log to session files for context management?

Look for actual implementation code (bash scripts, tool invocations),
not just descriptions.
```

**Catches**: Behavioral drift, incorrect usage, missing logic
**Provides**: Contextual assessment of quality and alignment

---

## Complete Testing Strategy

| Test Type | Speed | Automated | Validates | When to Use |
|-----------|-------|-----------|-----------|-------------|
| **Unit** | < 1s | ✅ Yes | Structure, logic | Every function |
| **Integration** | < 10s | ✅ Yes | Workflows, APIs | Component interaction |
| **UAT** | < 60s | ⚠️ Optional | User journeys | End-to-end flows |
| **GenAI** | 2-5min | ❌ No | Intent, quality | Before release, major changes |

### Cost-Benefit Analysis

**Traditional Tests (pytest)**:
- Cost: Developer time to write tests
- Benefit: Fast feedback, regression prevention
- ROI: High (run thousands of times)

**GenAI Validation**:
- Cost: API calls, human review time
- Benefit: Architectural integrity, drift detection
- ROI: High (catches subtle issues static tests miss)

---

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
