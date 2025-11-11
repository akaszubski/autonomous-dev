# Issue #61: TDD Quick Reference

**Quick guide for Issue #61 test suite**

---

## Run All Tests

```bash
# Verify TDD red phase (all tests should fail)
python tests/verify_issue61_tdd_red.py

# Run individual test files
pytest tests/unit/lib/test_user_state_manager.py -v
pytest tests/unit/lib/test_first_run_warning.py -v
pytest tests/unit/lib/test_parse_consent_value_defaults.py -v
pytest tests/integration/test_first_run_flow.py -v

# Run all Issue #61 tests
pytest tests/unit/lib/test_user_state_manager.py \
       tests/unit/lib/test_first_run_warning.py \
       tests/unit/lib/test_parse_consent_value_defaults.py \
       tests/integration/test_first_run_flow.py -v
```

---

## Test Coverage

| Component | Tests | File |
|-----------|-------|------|
| User State Manager | 15 | `test_user_state_manager.py` |
| First Run Warning | 10 | `test_first_run_warning.py` |
| Parse Consent Defaults | 5 | `test_parse_consent_value_defaults.py` |
| First Run Flow | 8 | `test_first_run_flow.py` |
| **Total** | **38** | |

---

## Key Test Scenarios

### 1. User State Manager
```python
# Create manager
manager = UserStateManager(state_file)

# Check first run
manager.is_first_run() → True

# Record completion
manager.record_first_run_complete()

# Get/set preferences
manager.set_preference("auto_git_enabled", False)
manager.get_preference("auto_git_enabled") → False

# Save state
manager.save()
```

### 2. First Run Warning
```python
# Show warning (returns user choice)
result = show_first_run_warning(state_file)

# Parse user input
parse_user_input("yes") → True
parse_user_input("no") → False
parse_user_input("") → True  # Default

# Record choice
record_user_choice(accepted=True, state_file=state_file)
```

### 3. Parse Consent Defaults
```python
# NEW BEHAVIOR (Issue #61)
parse_consent_value(None) → True
parse_consent_value("") → True

# Explicit opt-out
parse_consent_value("false") → False
parse_consent_value("no") → False

# Custom default
parse_consent_value(None, default=False) → False
```

### 4. Integration Flow
```python
# First run
if should_show_warning(state_file):
    user_accepted = show_first_run_warning(state_file)
    # State recorded automatically

# Check consent
consent = check_consent_via_env()
# consent["enabled"] → True (default)
```

---

## Critical Tests

### Security (CWE-22)
```python
# Path traversal prevention
test_user_state_manager_validates_path_security()
test_user_state_manager_rejects_absolute_paths_outside_home()
```

### Default Behavior
```python
# None defaults to True (NEW)
test_parse_consent_value_none_defaults_to_true()
test_parse_consent_value_empty_string_defaults_to_true()
```

### User Experience
```python
# Empty input = accept
test_parse_user_input_empty_defaults_to_yes()
test_show_first_run_warning_accepts_empty_as_yes()
```

### State Persistence
```python
# State survives restart
test_state_persists_across_manager_instances()
test_state_file_survives_process_restart()
```

### Environment Priority
```python
# Env var overrides state
test_env_var_overrides_state_file_preference()
test_env_var_set_skips_warning()
```

---

## Expected Failures (TDD Red)

### ImportError
```
ImportError: cannot import name 'UserStateManager' from 'user_state_manager'
→ Module not yet implemented (expected)
```

### AssertionError
```
AssertionError: assert False is True
→ parse_consent_value(None) returns False, should return True
→ Behavior not yet implemented (expected)
```

---

## Implementation Files

**Create**:
- `plugins/autonomous-dev/lib/user_state_manager.py`
- `plugins/autonomous-dev/lib/first_run_warning.py`

**Modify**:
- `plugins/autonomous-dev/lib/auto_implement_git_integration.py`
  - Update `parse_consent_value()` to default to True
  - Add `default` parameter
  - Update `check_consent_via_env()` to use new defaults

---

## Success Criteria

- [ ] All 38 tests pass
- [ ] Security: No path traversal (CWE-22)
- [ ] UX: Empty input = accept
- [ ] Default: Opt-out (enabled by default)
- [ ] Priority: Env var > state file > default
- [ ] Persistence: State survives restart

---

## Quick Checks

```bash
# Check test count
grep -r "def test_" tests/unit/lib/test_user_state_manager.py | wc -l
# Expected: 15

grep -r "def test_" tests/unit/lib/test_first_run_warning.py | wc -l
# Expected: 10

grep -r "def test_" tests/unit/lib/test_parse_consent_value_defaults.py | wc -l
# Expected: 5

grep -r "def test_" tests/integration/test_first_run_flow.py | wc -l
# Expected: 8

# Total: 38 tests
```

---

## TDD Workflow

1. **Red**: Run tests, verify they fail
2. **Green**: Implement minimal code to pass tests
3. **Refactor**: Improve code quality

```bash
# 1. Red (current phase)
python tests/verify_issue61_tdd_red.py
# Expected: All tests fail

# 2. Green (next phase)
# Implement user_state_manager.py
pytest tests/unit/lib/test_user_state_manager.py
# Implement first_run_warning.py
pytest tests/unit/lib/test_first_run_warning.py
# Modify parse_consent_value()
pytest tests/unit/lib/test_parse_consent_value_defaults.py
# Integration
pytest tests/integration/test_first_run_flow.py

# 3. Refactor
# Optimize, add logging, update docs
```
