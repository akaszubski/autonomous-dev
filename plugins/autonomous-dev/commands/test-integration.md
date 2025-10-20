---
description: Run integration tests - validate components work together (< 10s)
---

# Run Integration Tests

**Validate that components interact correctly**

---

## Usage

```bash
/test-integration
```

**Time**: < 10 seconds
**Tool**: pytest
**Scope**: Integration tests only (`tests/integration/`)

---

## What This Does

Runs pytest against integration tests directory:

```bash
pytest tests/integration/ -v --tb=short
```

Integration tests validate:
- API endpoints
- Database interactions
- Service integration
- External API mocks
- Component communication

---

## Expected Output

```
Running integration tests...

tests/integration/test_api.py::test_auth_flow ✅
tests/integration/test_api.py::test_data_retrieval ✅
tests/integration/test_db.py::test_crud_operations ✅

============================================
12/12 tests passed
Time: 4.2s
============================================
```

---

## When to Use

- ✅ After changing API endpoints
- ✅ After database schema changes
- ✅ Before code review
- ✅ In `/commit-check` (Level 2 standard commit)

---

## Related Commands

- `/test` - All automated tests (< 60s)
- `/test-unit` - Unit tests only (< 1s)
- `/test-uat` - UAT tests only (< 60s)

---

**Use this to ensure components integrate correctly.**
