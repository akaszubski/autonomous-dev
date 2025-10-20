---
description: Run unit tests only - fast individual function validation (< 1s)
---

# Run Unit Tests

**Fast validation of individual functions and classes**

---

## Usage

```bash
/test-unit
```

**Time**: < 1 second
**Tool**: pytest
**Scope**: Unit tests only (`tests/unit/`)

---

## What This Does

Runs pytest against unit tests directory only:

```bash
pytest tests/unit/ -v --tb=short
```

Unit tests validate:
- Individual functions
- Class methods
- Pure logic (no external dependencies)
- Edge cases and error handling

---

## Expected Output

```
Running unit tests...

tests/unit/test_auth.py::test_token_generation ✅
tests/unit/test_auth.py::test_token_validation ✅
tests/unit/test_utils.py::test_parse_input ✅

============================================
45/45 tests passed
Time: 0.8s
============================================
```

---

## When to Use

- ✅ During active development (fast feedback)
- ✅ After changing a function
- ✅ Before committing
- ✅ In `/commit` (Level 1 quick commit)

---

## Related Commands

- `/test` - All automated tests (< 60s)
- `/test-integration` - Integration tests only (< 10s)
- `/test-uat` - UAT tests only (< 60s)

---

**Use this for rapid iteration - fastest test feedback loop.**
