---
description: Run all automated tests (unit + integration + UAT) with pytest (< 60s)
---

## Implementation

```bash
pytest tests/ -v --tb=short
```

# Run All Tests (Default)

**Execute complete automated test suite with pytest**

---

## Usage

```bash
/test
```

**Time**: < 60 seconds (varies by project size)
**Tool**: pytest
**Scope**: All automated tests (unit + integration + UAT)

---

## What This Does

Runs pytest against all test directories:
- `tests/unit/` - Unit tests
- `tests/integration/` - Integration tests
- `tests/uat/` - User acceptance tests

```bash
pytest tests/ --cov=src --cov-report=term-missing -v
```

---

## Expected Output

```
Running all automated tests...

tests/unit/test_auth.py ✅✅✅✅✅ (5/5)
tests/integration/test_api.py ✅✅✅ (3/3)
tests/uat/test_workflows.py ✅✅ (2/2)

============================================
10/10 tests passed
Coverage: 87%
Time: 12.3s
============================================
```

---

## Related Commands

- `/test-unit` - Unit tests only (< 1s)
- `/test-integration` - Integration tests only (< 10s)
- `/test-uat` - UAT tests only (< 60s)
- `/test-uat-genai` - GenAI UX validation (2-5min)
- `/test-architecture` - GenAI architectural validation (2-5min)
- `/test-complete` - Complete pre-release validation (all + GenAI)

---

**Use this for quick validation that all automated tests pass.**
