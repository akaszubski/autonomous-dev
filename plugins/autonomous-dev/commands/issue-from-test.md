---
description: Create GitHub Issue from specific test failure
---

# Create Issue from Test Failure

**Create GitHub Issue from a specific pytest test failure**

---

## Usage

```bash
/issue-from-test <test_name>
```

**Example**:
```bash
/issue-from-test test_export_speed
/issue-from-test tests/uat/test_export.py::test_export_large_dataset
```

**Source**: Specific test failure
**Time**: < 5 seconds
**Output**: Single GitHub Issue

---

## What This Does

Creates GitHub Issue for a specific test failure:
1. Find test in last pytest run
2. Extract failure details (assertion, traceback)
3. Identify file locations
4. Create descriptive GitHub Issue
5. Link to test file and code

---

## Expected Output

```
Creating issue from test: test_export_speed...

Found test failure:
  Test: tests/uat/test_export.py::test_export_speed
  Status: FAILED
  Error: AssertionError: Export took 12.3s (limit: 5s)

Analyzing failure context...
  File: src/export.py:export_to_csv()
  Cause: No batch processing for large datasets

Creating GitHub issue...

✅ Issue #44: "Bug: Export performance exceeds limit"
   Priority: High
   Type: bug
   Labels: performance, automated, bug
   https://github.com/user/repo/issues/44

Issue body:
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
## Test Failure

**Test**: test_export_speed
**File**: tests/uat/test_export.py::test_export_speed
**Status**: FAILED

## Error
AssertionError: Export took 12.3s (limit: 5s)

## Failure Details
Expected: < 5.0 seconds
Actual: 12.3 seconds
Performance regression: 2.46x slower

## Cause
No batch processing for large datasets (> 1000 rows).
All rows loaded into memory at once.

## Recommendation
1. Implement batch processing (100 rows/batch)
2. Add streaming export for large files
3. Show progress indicator

## Location
- Code: src/export.py:export_to_csv() (line 45)
- Test: tests/uat/test_export.py:test_export_speed (line 78)

## Reproduction
pytest tests/uat/test_export.py::test_export_speed

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
```

---

## Test Name Formats

**Supported formats**:
```bash
# Short name (searches for match)
/issue-from-test test_export_speed

# Full pytest path
/issue-from-test tests/uat/test_export.py::test_export_speed

# Class method
/issue-from-test TestExport::test_speed

# Partial match (finds first match)
/issue-from-test export_speed
```

---

## Issue Priority

**Auto-assigned based on test type**:
- `tests/unit/` → Medium (functional bug)
- `tests/integration/` → High (integration failure)
- `tests/uat/` → **Critical** (user-facing issue)

**Can override with flag**:
```bash
/issue-from-test test_export_speed --priority=low
```

---

## When to Use

- ✅ After pytest run with specific failures
- ✅ To track known test failures
- ✅ For regression tracking
- ✅ When `/issue-auto` creates too many issues

---

## Requirements

**GitHub CLI** (`gh`) must be installed and authenticated.

---

## Related Commands

- `/issue-auto` - Auto-detect all issues
- `/issue-from-genai` - Create from GenAI finding
- `/issue-create` - Manual creation
- `/test` - Run tests first

---

**Use this to create focused issues for specific test failures. More targeted than /issue-auto.**
