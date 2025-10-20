---
description: Run UAT tests - validate complete user workflows (< 60s, automated)
---

# Run UAT Tests (Automated)

**Validate complete user workflows with automated tests**

---

## Usage

```bash
/test-uat
```

**Time**: < 60 seconds
**Tool**: pytest
**Scope**: UAT tests only (`tests/uat/`)

---

## What This Does

Runs pytest against UAT tests directory:

```bash
pytest tests/uat/ -v --tb=short
```

UAT tests validate:
- Complete user workflows
- End-to-end scenarios
- User journey success
- Critical business flows
- Realistic usage patterns

**Note**: These are **automated** UAT tests (pytest). For GenAI UX validation, use `/test-uat-genai`.

---

## Expected Output

```
Running UAT tests...

tests/uat/test_user_signup.py::test_complete_signup_flow ✅
tests/uat/test_export.py::test_export_to_csv ✅
tests/uat/test_export.py::test_export_to_json ✅

============================================
8/8 tests passed
Time: 15.3s
============================================
```

---

## When to Use

- ✅ Before feature completion
- ✅ Before deployment
- ✅ After significant workflow changes
- ✅ In `/commit-check` (Level 2 standard commit)

---

## Related Commands

- `/test` - All automated tests (< 60s)
- `/test-unit` - Unit tests only (< 1s)
- `/test-integration` - Integration tests only (< 10s)
- `/test-uat-genai` - GenAI UX validation (2-5min) ⭐ More comprehensive

---

**Use this to validate user workflows work correctly with automated tests.**
