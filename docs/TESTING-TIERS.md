# Testing Tiers - Automatic Categorization System

> **Purpose**: Ensure tests are automatically categorized and run at appropriate stages
> **Last Updated**: 2025-12-16

## Overview

Tests are **automatically marked** based on their file location. Place your test in the correct directory and it gets the right pytest marker - no manual `@pytest.mark` decorators needed!

## Test Tier Structure

```
tests/
├── regression/
│   ├── smoke/           # Tier 0: Critical path (<5s) - CI GATE
│   ├── regression/      # Tier 1: Feature protection (<30s)
│   ├── extended/        # Tier 2: Deep validation (<5min)
│   └── progression/     # Tier 3: TDD red phase
├── unit/                # Unit tests (isolated functions)
├── integration/         # Integration tests (multi-component)
├── security/            # Security-focused tests
├── hooks/               # Hook-specific tests
├── fixtures/            # Shared test fixtures (not tests)
├── helpers/             # Test helper utilities (not tests)
└── archived/            # Obsolete tests (excluded from runs)
```

## Tier Definitions

### Tier 0: Smoke Tests (`tests/regression/smoke/`)

**Purpose**: Fast validation of critical paths. Must pass for CI to proceed.

**Criteria**:
- Execution time: **< 5 seconds** per test
- No external dependencies (network, database, APIs)
- No file system modifications
- Tests basic functionality that MUST work

**What belongs here**:
- `install.sh` critical path tests
- `/sync` command validation
- Plugin loading/structure tests
- Manifest integrity checks
- Settings file validation

**Example**:
```python
# tests/regression/smoke/test_install_sync_critical.py
def test_install_manifest_exists():
    """Verify install manifest file exists."""
    manifest = Path("plugins/autonomous-dev/manifest.json")
    assert manifest.exists()
```

### Tier 1: Regression Tests (`tests/regression/regression/`)

**Purpose**: Protect released features from breaking.

**Criteria**:
- Execution time: **< 30 seconds** per test
- One test file per released feature/fix
- Tests specific bug fixes or features
- Named with version: `test_feature_v3_3_0_parallel_validation.py`

**What belongs here**:
- Feature-specific regression tests
- Bug fix verification tests
- Security fix tests
- Claude Code 2.0 compliance tests

**Example**:
```python
# tests/regression/regression/test_feature_v3_3_0_parallel_validation.py
def test_parallel_validation_agents_execute():
    """Verify parallel validation from v3.3.0 still works."""
    # Test the specific feature behavior
```

### Tier 2: Extended Tests (`tests/regression/extended/`)

**Purpose**: Deep validation and performance baselines.

**Criteria**:
- Execution time: **< 5 minutes** per test
- May use more resources
- Runs nightly, not every commit
- Performance benchmarks

**What belongs here**:
- Performance baseline tests
- Large dataset tests
- End-to-end workflow tests
- Resource-intensive validation

### Tier 3: Progression Tests (`tests/regression/progression/`)

**Purpose**: TDD red phase - tests for features in development.

**Criteria**:
- Expected to **FAIL** until implementation complete
- Marked as `@pytest.mark.tdd_red` automatically
- Move to appropriate tier when implementation done

**What belongs here**:
- Tests written before implementation
- Feature specification tests
- Acceptance criteria tests

## Standard Categories

### Unit Tests (`tests/unit/`)

Single function/class tests with mocked dependencies.

**Structure**:
```
tests/unit/
├── agents/           # Agent-specific unit tests
├── hooks/            # Hook unit tests
├── lib/              # Library unit tests
├── scripts/          # Script unit tests
├── skills/           # Skill unit tests
└── templates/        # Template unit tests
```

### Integration Tests (`tests/integration/`)

Multi-component tests with real interactions.

### Security Tests (`tests/security/`)

Security-focused tests (input validation, injection prevention, etc.)

### Hook Tests (`tests/hooks/`)

Hook-specific behavior tests.

## Running Tests by Tier

```bash
# Smoke tests only (CI gate)
pytest -m smoke -o "addopts="

# Regression tests
pytest -m regression -o "addopts="

# Both smoke and regression
pytest -m "smoke or regression" -o "addopts="

# All except slow tests
pytest -m "not slow" -o "addopts="

# Unit tests only
pytest -m unit -o "addopts="

# Security tests only
pytest -m security -o "addopts="
```

## Validation

Run the categorization validator:

```bash
# Show report
python scripts/validate_test_categorization.py --report

# Show guidance
python scripts/validate_test_categorization.py --guidance

# Strict mode (fail on uncategorized)
python scripts/validate_test_categorization.py --strict
```

## CI Pipeline

```
┌─────────────────┐
│ Smoke Tests     │  ← Tier 0 (must pass to proceed)
│ (< 5 minutes)   │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ Unit Tests      │  ← Standard tests
│ Integration     │
│ Regression      │
│ (< 15 minutes)  │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ Extended Tests  │  ← Nightly only
│ (< 30 minutes)  │
└─────────────────┘
```

## Adding New Tests

### Workflow

1. **Determine category**: What type of test is it?
2. **Choose directory**: Place in correct directory
3. **Write test**: Test gets auto-marked based on location
4. **Verify**: Run `python scripts/validate_test_categorization.py --report`

### Decision Tree

```
Is it protecting a released feature?
├─ Yes → Is it critical path (install, sync, load)?
│        ├─ Yes → tests/regression/smoke/
│        └─ No  → tests/regression/regression/
└─ No  → Is it TDD red phase (not implemented yet)?
         ├─ Yes → tests/regression/progression/
         └─ No  → Is it testing a single function/class?
                  ├─ Yes → tests/unit/{subcategory}/
                  └─ No  → tests/integration/
```

## Moving Tests to Regression

When a feature is released and should be protected:

1. Identify the test that validates the feature
2. Move it to `tests/regression/regression/`
3. Rename with version: `test_feature_v{VERSION}_{name}.py`
4. Ensure it runs in < 30 seconds

Example:
```bash
# Feature released in v3.42.0
mv tests/unit/test_skill_loader.py \
   tests/regression/regression/test_feature_v3_42_0_skill_loader.py
```

## Best Practices

1. **Keep smoke tests fast** - If it takes > 5s, it's not smoke
2. **One feature per regression file** - Easy to track what's protected
3. **Version in filename** - Know when protection was added
4. **No manual markers needed** - Trust the auto-marker system
5. **Validate before commit** - Run the validation script
