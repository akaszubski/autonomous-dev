# Implementation Checklist - Issue #85

**Issue**: Fix hardcoded paths in batch_state_manager.py docstrings for portability
**Current Phase**: TDD RED (tests failing)
**Next Phase**: TDD GREEN (implement fixes)

---

## TDD Status

- ✅ **RED Phase Complete**: All tests written and FAILING
- ⏭️ **GREEN Phase**: Make tests pass (this checklist)
- ⏭️ **REFACTOR Phase**: Clean up if needed

---

## Files to Modify

### Primary File
- `/Users/akaszubski/Documents/GitHub/autonomous-dev/plugins/autonomous-dev/lib/batch_state_manager.py`

### Test Files (DO NOT MODIFY)
- `/Users/akaszubski/Documents/GitHub/autonomous-dev/tests/unit/lib/test_batch_state_manager_portability.py`
- `/Users/akaszubski/Documents/GitHub/autonomous-dev/tests/unit/lib/run_portability_tests.py`

---

## Implementation Tasks

### Task 1: Update Module Docstring (Lines 1-100)

**Location**: Module-level docstring, "Usage:" section

**Current** (FAILING):
```python
Usage:
    from batch_state_manager import (
        create_batch_state,
        load_batch_state,
        save_batch_state,
        # ... other imports
    )

    # Create new batch
    state = create_batch_state("/path/to/features.txt", ["feature 1", "feature 2"])
    save_batch_state(state_file, state)  # ❌ Where does state_file come from?

    # Process features
    while True:
        next_feature = get_next_pending_feature(state)
        # ...
```

**Fixed** (PASSING):
```python
Usage:
    from batch_state_manager import (
        create_batch_state,
        load_batch_state,
        save_batch_state,
        get_default_state_file,  # ✅ Add this import
        # ... other imports
    )
    from path_utils import get_batch_state_file  # ✅ Show portable import

    # Get portable state file path
    state_file = get_batch_state_file()  # ✅ Show how to get path

    # Create new batch
    state = create_batch_state("/path/to/features.txt", ["feature 1", "feature 2"])
    save_batch_state(state_file, state)  # ✅ Now it's clear

    # Process features
    while True:
        next_feature = get_next_pending_feature(state)
        # ...
```

**Verification**:
```bash
grep -A 20 "Usage:" plugins/autonomous-dev/lib/batch_state_manager.py | grep "get_batch_state_file"
```

---

### Task 2: Update save_batch_state() Docstring (Line ~455)

**Current** (FAILING):
```python
Example:
    >>> state = create_batch_state("/path/to/features.txt", ["feature 1"])
    >>> save_batch_state(Path(".claude/batch_state.json"), state)
```

**Fixed** (PASSING):
```python
Example:
    >>> state = create_batch_state("/path/to/features.txt", ["feature 1"])
    >>> save_batch_state(get_batch_state_file(), state)
```

**Verification**:
```bash
grep -A 3 "Example:" plugins/autonomous-dev/lib/batch_state_manager.py | grep -A 1 "save_batch_state"
```

---

### Task 3: Update load_batch_state() Docstring (Line ~540)

**Current** (FAILING):
```python
Example:
    >>> state = load_batch_state(Path(".claude/batch_state.json"))
    >>> state.batch_id
    'batch-20251116-123456'
```

**Fixed** (PASSING):
```python
Example:
    >>> state = load_batch_state(get_batch_state_file())
    >>> state.batch_id
    'batch-20251116-123456'
```

**Verification**:
```bash
grep -A 3 "Example:" plugins/autonomous-dev/lib/batch_state_manager.py | grep -A 1 "load_batch_state"
```

---

### Task 4: Update update_batch_progress() Docstring (Line ~710)

**Current** (FAILING):
```python
Example:
    >>> update_batch_progress(
    ...     state_file=Path(".claude/batch_state.json"),
    ...     feature_index=0,
    ...     status="completed",
    ...     context_token_delta=5000,
    ... )
```

**Fixed** (PASSING):
```python
Example:
    >>> update_batch_progress(
    ...     state_file=get_batch_state_file(),
    ...     feature_index=0,
    ...     status="completed",
    ...     context_token_delta=5000,
    ... )
```

**Verification**:
```bash
grep -A 6 "Example:" plugins/autonomous-dev/lib/batch_state_manager.py | grep -A 5 "update_batch_progress"
```

---

### Task 5: Update record_auto_clear_event() Docstring (Line ~790)

**Current** (FAILING):
```python
Example:
    >>> record_auto_clear_event(
    ...     state_file=Path(".claude/batch_state.json"),
    ...     feature_index=2,
    ...     context_tokens_before_clear=155000,
    ... )
```

**Fixed** (PASSING):
```python
Example:
    >>> record_auto_clear_event(
    ...     state_file=get_batch_state_file(),
    ...     feature_index=2,
    ...     context_tokens_before_clear=155000,
    ... )
```

**Verification**:
```bash
grep -A 5 "Example:" plugins/autonomous-dev/lib/batch_state_manager.py | grep -A 4 "record_auto_clear_event"
```

---

## Verification Commands

### Before Implementation (should FAIL)
```bash
# Verify RED phase
python3 scripts/verification/verify_issue85_tdd_red.py

# Expected output: All checks pass (tests in RED phase)
```

### After Implementation (should PASS)
```bash
# Run minimal test suite
python3 tests/unit/lib/run_portability_tests.py

# Expected output:
# Passed: 5
# Failed: 0
# STATUS: All tests passed
```

### Full Test Suite (with pytest)
```bash
# If pytest available
pytest tests/unit/lib/test_batch_state_manager_portability.py -v

# Expected output: 16 tests pass
```

---

## Search and Replace Patterns

**IMPORTANT**: Only replace within docstrings (lines starting with triple quotes or indented Example: sections)

### Pattern 1: save_batch_state examples
```bash
# Find
Path(".claude/batch_state.json")

# Replace with
get_batch_state_file()
```

### Pattern 2: Module usage section
```bash
# Add after import section
from path_utils import get_batch_state_file

# Add before create_batch_state
state_file = get_batch_state_file()
```

---

## Testing Checklist

After each change, verify:

- [ ] Task 1: Module docstring shows `get_batch_state_file()` usage
- [ ] Task 2: `save_batch_state()` example uses portable path
- [ ] Task 3: `load_batch_state()` example uses portable path
- [ ] Task 4: `update_batch_progress()` example uses portable path
- [ ] Task 5: `record_auto_clear_event()` example uses portable path
- [ ] All 5 docstring validation tests pass
- [ ] No hardcoded `Path(".claude/batch_state.json")` in examples
- [ ] Module imports show `get_batch_state_file` function
- [ ] Documentation is clear and helpful for developers

---

## Regression Prevention

After implementation, the test suite will:

1. **Detect hardcoded paths** automatically using regex
2. **Validate examples** programmatically via `inspect.getdoc()`
3. **Run on every change** to batch_state_manager.py
4. **Fail CI/CD** if hardcoded paths reintroduced

---

## Success Criteria

**Definition of Done**:

1. ✅ All 5 validation tests pass
2. ✅ No hardcoded `Path(".claude/batch_state.json")` in docstrings
3. ✅ Module docstring demonstrates `get_batch_state_file()` usage
4. ✅ Function examples show portable path patterns
5. ✅ Verification script confirms GREEN phase
6. ✅ Documentation is clear and helpful

---

## Files Changed Summary

| File | Changes | Lines Modified |
|------|---------|----------------|
| `batch_state_manager.py` | Update 5 docstrings | ~15-20 lines |

**Total Impact**: Minimal code changes, maximum documentation improvement

---

## Commands Quick Reference

```bash
# 1. Verify current state (RED phase)
python3 scripts/verification/verify_issue85_tdd_red.py

# 2. Make changes to batch_state_manager.py
vim plugins/autonomous-dev/lib/batch_state_manager.py

# 3. Test changes
python3 tests/unit/lib/run_portability_tests.py

# 4. Verify all patterns updated
grep -n 'Path(".claude/batch_state.json")' plugins/autonomous-dev/lib/batch_state_manager.py

# Should return NO matches in docstrings (only in code is OK)
```

---

## Related Documentation

- **Issue #79**: Original tracking infrastructure portability fixes
- **Issue #85**: This issue - batch_state_manager.py docstring fixes
- **Testing Guide**: `plugins/autonomous-dev/skills/testing-guide/SKILL.md`
- **TDD Patterns**: `plugins/autonomous-dev/skills/testing-guide/pytest-patterns.md`

---

## Implementation Time Estimate

- **Complexity**: LOW (simple find-replace in docstrings)
- **Time**: 5-10 minutes
- **Risk**: MINIMAL (only documentation changes, no code logic)
- **Testing**: 2 minutes (run verification scripts)

**Total**: ~15 minutes

---

**Ready for GREEN phase!** All tests are failing as expected. Implementation will make them pass.
