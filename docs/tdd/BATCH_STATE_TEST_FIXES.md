# Batch State Manager Test Fixes (Issue #76)

## Summary

Fixed 3 failing tests in `test_batch_state_manager.py` by correcting the mocking strategy.

## Root Cause

Tests were mocking **high-level Path methods** instead of **low-level syscalls**.

### Why Tests Failed

The implementation uses low-level syscalls for atomic file operations:
- `tempfile.mkstemp()` - Create temp file
- `os.write()` - Write data to file descriptor
- `os.close()` - Close file descriptor  
- `Path.chmod()` - Set permissions
- `Path.replace()` - Atomic rename

Mocking `Path.write_text()` or `Path.read_text()` doesn't intercept these syscalls, so tests passed locally but would fail in production.

## Fixed Tests

### 1. `test_save_batch_state_atomic_write` (line 296)

**Before**: Mocked `Path.write_text`  
**After**: Mock `tempfile.mkstemp`, `os.write`, `os.close`, `Path.chmod`, `Path.replace`

**Validates**:
1. CREATE: Temp file created in same directory (crash safety)
2. WRITE: JSON data written to file descriptor
3. SECURITY: File permissions set to 0o600  
4. RENAME: Atomic swap temp → target

### 2. `test_save_batch_state_handles_disk_full_error` (line 671)

**Before**: Mocked `Path.write_text` to raise OSError  
**After**: Mock `os.write` to raise `OSError(28, "No space left on device")`

**Validates**:
- Error message mentions disk/space/write issue
- Graceful degradation on storage errors

### 3. `test_load_batch_state_handles_permission_error` (line 683)

**Before**: Mocked `Path.read_text` to raise PermissionError  
**After**: Mock `builtins.open` to raise `PermissionError`

**Validates**:
1. `validate_path()` executes FIRST (security check before file ops)
2. Error message mentions permission/access/read issue
3. Graceful degradation on access errors

## Security Preservation

All three tests still validate that security checks execute BEFORE file operations:

1. **Path Traversal (CWE-22)**: `validate_path()` rejects `../` patterns
2. **Symlink Attacks (CWE-59)**: `validate_path()` rejects symlinks  
3. **Audit Logging**: All operations logged to `security_audit.log`

Low-level mocks are placed AFTER security validation in execution order.

## Mocking Strategy Guidelines

### CORRECT (Low-Level Syscalls)

```python
# Atomic writes
with patch("tempfile.mkstemp"), \
     patch("os.write"), \
     patch("os.close"), \
     patch("pathlib.Path.chmod"), \
     patch("pathlib.Path.replace"):
    ...

# File reads  
with patch("builtins.open"):
    ...

# Disk errors
with patch("os.write", side_effect=OSError(28, "No space left on device")):
    ...
```

### WRONG (High-Level Abstractions)

```python
# DON'T DO THIS - bypassed by implementation
with patch("pathlib.Path.write_text"):
    ...

with patch("pathlib.Path.read_text"):
    ...
```

## Test Results

- **Before Fix**: 38/41 tests passing (92.7%)
- **After Fix**: 41/41 tests passing (100%)
- **Fixed**: 3/41 tests (7.3% of suite)
- **No Regression**: All security, concurrent access, and utility function tests still passing

## Files Modified

1. `tests/unit/lib/test_batch_state_manager.py` - Fixed 3 test mocking strategies
2. `CHANGELOG.md` - Added v3.23.1 entry documenting fixes
3. `tests/BATCH_STATE_TEST_FIXES.md` - This summary document

## Date

2025-11-16

## Issue

GitHub Issue #76 (State-Based Auto-Clearing for /batch-implement)
