---
name: debugging-workflow
description: "Systematic debugging methodology — reproduce, isolate, bisect, fix, verify. Use when diagnosing failures, tracing errors, or investigating unexpected behavior. TRIGGER when: debug, error, traceback, stack trace, bisect, breakpoint, failing test, unexpected behavior. DO NOT TRIGGER when: writing new features, code review, documentation, refactoring."
allowed-tools: "Read, Grep, Glob, Bash"
---

# Debugging Workflow

Systematic methodology for diagnosing and fixing bugs. Follow these phases in order — do not skip ahead.

## Phase 1: Reproduce

Before anything else, reproduce the failure reliably.

### Steps
1. **Get the exact error** — full traceback, not a summary
2. **Find the minimal reproduction** — smallest input/command that triggers it
3. **Confirm it's consistent** — run 3 times. Flaky? Note the frequency
4. **Record the environment** — Python version, OS, relevant config

### Anti-patterns
- FORBIDDEN: Guessing the fix without reproducing first
- FORBIDDEN: Reading code and theorizing without running it
- FORBIDDEN: "I think I know what's wrong" before seeing the error

```bash
# Good: run the failing test with verbose output
python -m pytest tests/path/test_file.py::test_name -xvs 2>&1

# Good: reproduce with minimal script
python -c "from module import func; func(failing_input)"
```

## Phase 2: Isolate

Narrow down where the failure originates.

### Binary Search (Bisect)
- **Code bisect**: Comment out half the logic, does it still fail?
- **Git bisect**: `git bisect start`, `git bisect bad`, `git bisect good <known-good-commit>`
- **Input bisect**: Halve the input data until you find the minimal failing case

### Trace the Call Chain
1. Start at the exception/error location
2. Walk up the call stack — who called this function with what args?
3. Find the **first wrong value** — where did correct data become incorrect?

```python
# Quick tracing without debugger
import traceback
traceback.print_stack()  # Print call stack at any point

# Targeted print debugging
def suspect_function(data):
    print(f"DEBUG: data type={type(data)}, len={len(data) if hasattr(data, '__len__') else 'N/A'}")
    print(f"DEBUG: data={data!r:.200}")  # First 200 chars of repr
```

### Debugger Usage
```python
# Drop into debugger at specific point
import pdb; pdb.set_trace()      # stdlib
import ipdb; ipdb.set_trace()    # enhanced (if available)
breakpoint()                      # Python 3.7+ (uses PYTHONBREAKPOINT env var)
```

**Debugger commands**: `n` (next), `s` (step into), `c` (continue), `p expr` (print), `w` (where/stack), `u`/`d` (up/down stack)

## Phase 3: Diagnose

Identify the root cause, not just the symptom.

### Root Cause Categories
| Category | Example | Fix Pattern |
|----------|---------|-------------|
| **Wrong type** | `str` where `int` expected | Add type check or convert |
| **Wrong state** | Object not initialized | Fix initialization order |
| **Race condition** | File read before write completes | Add synchronization |
| **Missing check** | `None` not handled | Add guard clause |
| **Stale data** | Cache not invalidated | Fix cache lifecycle |
| **Wrong assumption** | API changed behavior | Update to match reality |

### The "5 Whys"
Don't stop at the first explanation:
1. Why did the test fail? → `KeyError: 'name'`
2. Why is 'name' missing? → The dict comes from `parse_config()`
3. Why doesn't `parse_config()` include 'name'? → The config file format changed
4. Why did the format change? → A migration script ran but didn't update the schema
5. Why didn't the schema update? → The migration has no test → **Root cause**

## Phase 4: Fix

Apply the minimum change that addresses the root cause.

### Rules
- Fix the root cause, not the symptom
- One fix per bug — don't refactor while fixing
- If the fix is > 20 lines, reconsider — you may be fixing the wrong thing
- Add a regression test BEFORE or WITH the fix, never after

### Fix Verification Checklist
- [ ] The original reproduction now passes
- [ ] No existing tests broke
- [ ] A new test covers this specific failure
- [ ] The fix handles edge cases (None, empty, boundary values)

## Phase 5: Verify

Confirm the fix is complete and doesn't introduce new issues.

```bash
# Run the specific failing test
python -m pytest tests/path/test_file.py::test_name -xvs

# Run the full test suite
python -m pytest --tb=short

# Run with coverage to verify the fix path is exercised
python -m pytest --cov=module --cov-report=term-missing tests/path/test_file.py
```

### Post-Fix Checks
1. Does the original error still occur? → Must be NO
2. Do all existing tests still pass? → Must be YES
3. Is there a regression test for this bug? → Must be YES
4. Could this bug occur elsewhere? → Search for similar patterns

## Cross-References

- [testing-guide](../testing-guide/SKILL.md) — Test patterns for regression tests
- [error-handling](../error-handling/SKILL.md) — Error handling patterns
