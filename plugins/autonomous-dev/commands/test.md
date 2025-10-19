---
description: Run test suite with coverage reporting (pytest for Python, jest for JS/TS)
---

# Run Tests

Execute the test suite and generate coverage reports.

## Usage

```bash
/test
```

## What This Does

Runs tests with coverage measurement:

**Python**:
```bash
pytest --cov=src --cov-report=term-missing --cov-report=html -v
```

**JavaScript/TypeScript**:
```bash
npm test -- --coverage
```

## Example Output

```
Running test suite...

=================== test session starts ====================
collected 45 items

tests/unit/test_auth.py::test_login PASSED           [ 2%]
tests/unit/test_auth.py::test_logout PASSED          [ 4%]
tests/unit/test_user.py::test_create_user PASSED     [ 6%]
...
tests/integration/test_workflow.py::test_full_flow PASSED [100%]

=================== 45 passed in 2.34s =====================

Coverage Report:
Name                    Stmts   Miss  Cover   Missing
-----------------------------------------------------
src/auth.py               42      3    93%   45-48
src/user.py               35      2    94%   67-68
src/models/base.py        28      0   100%
-----------------------------------------------------
TOTAL                    105      5    95%

✅ All tests passing
✅ Coverage: 95% (exceeds 80% threshold)

HTML report: file://./htmlcov/index.html
```

## When to Use

- After implementing features
- After making code changes
- Before committing code
- To verify bug fixes
- To check test coverage

## Coverage Thresholds

- **Target**: ≥80% coverage on all code
- **Fails**: If coverage drops below 80% (configurable)

## Test Categories

Tests are organized by type:

```
tests/
├── unit/              # Fast, isolated tests
├── integration/       # Multi-component tests
├── progression/       # Baseline tracking tests
└── regression/        # Bug prevention tests
```

## Troubleshooting

### Tests not found
```bash
# Ensure pytest installed
pip install pytest pytest-cov

# Or for JS/TS
npm install
```

### Tests failing
1. Check error messages in output
2. Run specific test: `pytest tests/unit/test_auth.py::test_login -v`
3. Use debugger: `pytest --pdb`

### Low coverage
1. View HTML report: `open htmlcov/index.html`
2. Add tests for uncovered lines
3. Use `/test` again to verify

## Auto-Run vs Manual

This command is **manual** (you control when it runs).

**Alternative**: The `auto_test.py` hook can run automatically:
- On file save (related tests only)
- Before git commit (pre-commit hook)
- Before git push (pre-push hook)

**Recommended**: Use `/test` manually for full control.

## Related Commands

- `/format` - Format code before testing
- `/security-scan` - Security scan after tests pass
- `/full-check` - Run all checks (format + test + security)

---

**Run this after implementing features to verify all tests pass and coverage is sufficient.**
