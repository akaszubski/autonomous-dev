# Regression Test Suite

Scalable, four-tier regression testing for autonomous-dev plugin.

**Status**: FAILING (TDD Red Phase) - Tests written first, implementation follows

## Quick Start

```bash
# Run all tests (smoke + regression + extended)
pytest tests/regression/ -v

# Run only smoke tests (< 5s)
pytest tests/regression/ -m smoke -v

# Run only regression tests (< 30s)
pytest tests/regression/ -m regression -v

# Run with parallelization (faster)
pytest tests/regression/ -n auto -v

# Run with coverage
pytest tests/regression/ --cov=plugins/autonomous-dev --cov-report=html
```

## Architecture

### Four-Tier Structure

```
tests/regression/
├── smoke/              # < 5s - Critical paths
├── regression/         # < 30s - Bug fixes, features
├── extended/           # 1-5min - Performance, edge cases
└── progression/        # Variable - Feature evolution
```

**Tier Selection Guide**:
- **Smoke**: Can I load the plugin? Do commands exist?
- **Regression**: Does the v3.4.1 security fix still work?
- **Extended**: Can it handle 100 concurrent updates?
- **Progression**: How did this feature evolve from v3.0 to v3.4?

### Pytest Markers

All tests use markers for tier classification:

```python
@pytest.mark.smoke
def test_plugin_loads():
    """Smoke test: Plugin loads without errors."""
    pass

@pytest.mark.regression
def test_v3_4_1_race_condition_fix():
    """Regression: v3.4.1 security fix still works."""
    pass

@pytest.mark.extended
def test_1000_concurrent_updates():
    """Extended: Stress test with 1000 updates."""
    pass
```

Run by marker:
```bash
pytest -m smoke     # Only smoke tests
pytest -m "smoke or regression"  # Smoke + regression
pytest -m "not extended"  # Skip slow tests
```

## Test Coverage

### Current Tests (175+ planned)

**Infrastructure (Meta-tests)**: 20 tests
- Tier classification accuracy
- Parallel execution isolation
- Hook integration
- Directory structure validation

**Smoke Tests (Critical Paths)**: 25 tests
- Plugin loading and initialization
- Command routing validation
- Basic configuration checks
- Fast failure detection

**Regression Tests (Bug/Feature Protection)**: 100+ tests
- **Security Fixes**:
  - v3.4.1: Race condition (HIGH severity)
  - v3.2.3: Path traversal prevention
  - v3.2.3: Symlink detection
  - Security audit findings (35+ audits)
- **Feature Implementations**:
  - v3.4.0: Auto-update PROJECT.md progress
  - v3.3.0: Parallel validation (3 agents)
  - v3.2.2: Orchestrator removal
  - v3.0+: TDD enforcement, quality validation

**Extended Tests (Performance/Edge Cases)**: 30 tests
- /auto-implement performance baseline (< 5min)
- Concurrent PROJECT.md updates
- Large file handling (100+ goals)
- Error recovery scenarios

**Progression Tests (Feature Evolution)**: Variable
- Feature development tracking
- Breaking change detection
- Migration path validation

### Coverage by Version

Backfilled from CHANGELOG:
- ✅ v3.4.1: Race condition fix (8 tests)
- ✅ v3.4.0: Auto-update PROJECT.md (15 tests)
- ✅ v3.3.0: Parallel validation (5 tests)
- ⏳ v3.2.3: Security hardening (TODO: 38 tests)
- ⏳ v3.2.2: Orchestrator removal (TODO)
- ⏳ v3.0+: TDD, quality validator (TODO)

Backfilled from Security Audits:
- ⏳ Command injection prevention (TODO)
- ⏳ Credential exposure checks (TODO)
- ⏳ .env gitignore validation (TODO)
- ⏳ OWASP compliance (TODO)

## Tools & Technologies

### pytest-xdist (Parallel Execution)

Run tests in parallel for faster execution:

```bash
# Auto-detect CPU cores
pytest tests/regression/ -n auto

# Use specific number of workers
pytest tests/regression/ -n 4

# Combine with markers
pytest tests/regression/ -m regression -n auto
```

**Benefits**:
- Smoke tests: 25 tests in < 5s total (parallel)
- Regression tests: 100 tests in < 30s total (parallel)
- Each test gets isolated `tmp_path` (no interference)

### syrupy (Snapshot Testing)

Validate complex outputs with snapshots:

```python
def test_health_check_output(snapshot):
    """Validate health check output format."""
    result = run_health_check()
    assert result == snapshot
```

Update snapshots:
```bash
pytest tests/regression/ --snapshot-update
```

Snapshots stored in: `tests/regression/__snapshots__/`

### pytest-testmon (Smart Test Selection)

Run only tests affected by code changes:

```bash
# First run: All tests
pytest tests/regression/ --testmon

# Subsequent runs: Only affected tests
pytest tests/regression/ --testmon
```

**Benefits**:
- Edit `project_md_updater.py` → Only PROJECT.md tests run
- Edit `git_operations.py` → Only git tests run
- Speeds up TDD cycle (red → green → refactor)

## Writing Tests

### TDD Process (Red → Green → Refactor)

**Step 1: Write FAILING test (Red)**:
```python
@pytest.mark.regression
def test_v3_5_0_new_feature():
    """Test that new feature works correctly.

    Protects: v3.5.0 feature description
    """
    import new_module

    result = new_module.new_function()
    assert result == "expected"  # FAILS - not implemented yet
```

**Step 2: Run test, verify FAILURE**:
```bash
pytest tests/regression/regression/test_feature_v3_5_0.py -v
# EXPECTED: FAILED - new_module not found
```

**Step 3: Implement feature (Green)**:
```python
# plugins/autonomous-dev/lib/new_module.py
def new_function():
    return "expected"
```

**Step 4: Run test, verify PASS**:
```bash
pytest tests/regression/regression/test_feature_v3_5_0.py -v
# EXPECTED: PASSED
```

**Step 5: Refactor if needed**:
- Improve code quality
- Tests keep passing (regression protection)

### Test Naming Convention

**Class Names**: `Test<Feature><Context>`
```python
class TestRaceConditionFix:  # Feature: Race condition fix
class TestAutoImplementPerformance:  # Feature: Performance
```

**Method Names**: `test_<what>_<scenario>`
```python
def test_atomic_write_uses_mkstemp_not_pid():  # What: atomic write, Scenario: mkstemp usage
def test_parallel_validation_completes_under_2_minutes():  # What: parallel validation, Scenario: performance
```

### Docstring Requirements

Every test MUST have a docstring explaining:
1. **What** is being tested
2. **Why** it matters (protects against what bug/regression)
3. **Version** if applicable

```python
def test_v3_4_1_race_condition_fix():
    """Test that v3.4.1 race condition fix prevents symlink attacks.

    Bug: PID-based temp files were predictable, enabling symlink race attacks
    Fix: Use tempfile.mkstemp() for cryptographic random filenames

    Protects: CWE-362 race condition (v3.4.1 HIGH severity)
    """
```

### Fixture Usage

Use fixtures for isolation and reusability:

```python
def test_project_md_update(isolated_project):
    """Test uses isolated_project fixture for safety."""
    # isolated_project provides clean tmp directory
    # No risk of corrupting real PROJECT.md
    project_md = isolated_project / ".claude" / "PROJECT.md"
    # ... test code ...
```

**Available Fixtures**:
- `project_root`: Real project root directory
- `plugins_dir`: Real plugins/autonomous-dev directory
- `isolated_project`: Isolated temp project (use for file I/O)
- `timing_validator`: Tier timing validation
- `mock_agent_invocation`: Mock agent outputs
- `mock_git_operations`: Mock git subprocess calls

## Backfill Strategy

### Automated Backfill

Use `auto_add_to_regression.py` hook to generate tests:

```bash
# Generate test from security audit
python plugins/autonomous-dev/hooks/auto_add_to_regression.py \
  --source=docs/sessions/SECURITY_AUDIT_GIT_INTEGRATION_20251105.md \
  --tier=regression \
  --output=tests/regression/regression/test_security_git_integration.py

# Generate test from CHANGELOG entry
python plugins/autonomous-dev/hooks/auto_add_to_regression.py \
  --source=CHANGELOG.md \
  --version=v3.4.1 \
  --tier=regression
```

### Manual Backfill Priorities

**Priority 1: High Severity Security** (35+ audits)
- Path traversal attacks
- Command injection
- Credential exposure
- Race conditions

**Priority 2: Critical Features** (CHANGELOG v3.0-v3.4)
- Auto-implement workflow
- Agent coordination
- Hook automation
- PROJECT.md alignment

**Priority 3: Edge Cases** (Session logs, bug reports)
- Malformed inputs
- Concurrent operations
- Error recovery

**Priority 4: Performance** (Benchmarks, user reports)
- /auto-implement < 5min
- Parallel validation < 2min
- Hook execution < 1s

## Integration with CI/CD

### Pre-commit Hook

```bash
# Run smoke tests before commit (< 5s)
pytest tests/regression/ -m smoke
```

### Pre-push Hook

```bash
# Run smoke + regression before push (< 30s)
pytest tests/regression/ -m "smoke or regression"
```

### GitHub Actions

```yaml
name: Regression Tests

on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - uses: actions/setup-python@v4
        with:
          python-version: '3.11'
      - name: Install dependencies
        run: pip install -r requirements-dev.txt
      - name: Run smoke tests
        run: pytest tests/regression/ -m smoke -v
      - name: Run regression tests
        run: pytest tests/regression/ -m regression -v -n auto
      - name: Run extended tests (nightly only)
        if: github.event_name == 'schedule'
        run: pytest tests/regression/ -m extended -v
```

## Monitoring & Metrics

### Coverage Tracking

```bash
# Generate coverage report
pytest tests/regression/ --cov=plugins/autonomous-dev --cov-report=html

# View report
open htmlcov/index.html

# Target: 80%+ coverage
```

### Performance Tracking

```bash
# Track test execution time
pytest tests/regression/ --durations=10

# Identify slow tests (> tier threshold)
pytest tests/regression/ -m smoke --durations=0 | grep "slow"
```

### Regression Tracking

```bash
# Track which features have tests
python scripts/regression_coverage.py

# Output:
# v3.4.1: 8/8 tests (100%)
# v3.4.0: 15/20 tests (75%)
# v3.3.0: 5/10 tests (50%)
```

## Troubleshooting

### Tests Fail on `import project_md_updater`

**Problem**: Module not in path

**Solution**: Tests auto-add `plugins/autonomous-dev/lib` to path via fixture:
```python
@pytest.fixture(autouse=True)
def add_lib_to_path(plugins_dir):
    """Add plugin lib directory to sys.path."""
    lib_dir = plugins_dir / "lib"
    sys.path.insert(0, str(lib_dir))
    yield
    sys.path.pop(0)
```

### Parallel Tests Fail with "File exists"

**Problem**: Tests sharing state via real filesystem

**Solution**: Use `isolated_project` fixture, not `project_root`:
```python
# BAD: Uses real project (conflicts in parallel)
def test_update(project_root):
    project_md = project_root / ".claude" / "PROJECT.md"

# GOOD: Uses isolated tmp directory (safe in parallel)
def test_update(isolated_project):
    project_md = isolated_project / ".claude" / "PROJECT.md"
```

### Snapshot Tests Fail with "Snapshot not found"

**Problem**: Snapshots not committed to git

**Solution**: Commit snapshots after generating:
```bash
pytest tests/regression/ --snapshot-update
git add tests/regression/__snapshots__/
git commit -m "test: add snapshots for regression tests"
```

### Tests Pass Locally, Fail in CI

**Problem**: Environment differences (paths, permissions)

**Solution**: Use `isolation_guard` fixture (already autouse):
```python
@pytest.fixture(autouse=True)
def isolation_guard(monkeypatch):
    """Prevent tests from modifying real environment."""
    monkeypatch.setenv('HOME', '/tmp/test_home')
    # ... more isolation ...
```

## References

**Documentation**:
- [pytest docs](https://docs.pytest.org/)
- [pytest-xdist docs](https://pytest-xdist.readthedocs.io/)
- [syrupy docs](https://github.com/tophat/syrupy)
- [Testing guide skill](../../docs/skills/testing-guide.md)

**Project Docs**:
- [CHANGELOG.md](../../CHANGELOG.md) - Version history
- [docs/sessions/](../../docs/sessions/) - Security audits
- [CLAUDE.md](../../CLAUDE.md) - Development standards

**Related Tests**:
- [tests/unit/](../unit/) - Unit tests
- [tests/integration/](../integration/) - Integration tests

---

**Last Updated**: 2025-11-05 (v3.4.1)
**Total Tests**: 175+ (20 infrastructure, 25 smoke, 100+ regression, 30 extended)
**Coverage Target**: 80%+
**TDD Status**: Red phase (tests written, implementation follows)
