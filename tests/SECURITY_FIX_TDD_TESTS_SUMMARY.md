# Security Fix TDD Tests Summary

**Date**: 2025-11-05
**Feature**: Replace PID-based temp file creation with `tempfile.mkstemp()`
**File**: `plugins/autonomous-dev/lib/project_md_updater.py`
**Method**: `_atomic_write()` (lines 149-189)
**Test File**: `tests/test_project_progress_update.py`

---

## TDD Red Phase - Tests Written FIRST (Implementation Not Yet Done)

All tests below are currently **FAILING** as expected. They define the security requirements for the implementation.

---

## Security Vulnerability Being Fixed

**Current Implementation (VULNERABLE)**:
```python
# Line 166 in project_md_updater.py
temp_path = self.project_file.parent / f".PROJECT_{os.getpid()}.tmp"
```

**Problem**: PID-based temp file names create a **race condition vulnerability**:
1. Attacker observes process PID via `/proc/<pid>` or `ps`
2. Attacker predicts temp filename: `.PROJECT_<pid>.tmp`
3. Attacker pre-creates malicious symlink at that location
4. Process writes to symlink → writes to arbitrary file (privilege escalation)

**Secure Implementation (REQUIRED)**:
```python
# Use tempfile.mkstemp() with cryptographic random suffix
fd, temp_path = tempfile.mkstemp(
    dir=str(self.project_file.parent),
    prefix='.PROJECT.',
    suffix='.tmp',
    text=False  # Binary mode for cross-platform compatibility
)
# Write via os.write(fd, content.encode('utf-8'))
# Close FD before rename
os.close(fd)
```

**Why mkstemp() is secure**:
- Uses cryptographic random suffix (unpredictable)
- Atomically creates file with O_EXCL flag (fails if exists)
- Returns file descriptor (immediate ownership)
- Prevents TOCTOU (Time-Of-Check-Time-Of-Use) race conditions

---

## Test Coverage Summary

### Unit Tests (3 core tests)

#### 1. `test_atomic_write_uses_mkstemp_not_pid` ❌ FAILING
**Status**: Expected 'mkstemp' to have been called once. Called 0 times.

**What it tests**:
- `tempfile.mkstemp()` is called instead of PID-based naming
- `mkstemp()` receives correct parameters:
  - `dir`: Same directory as target file
  - `prefix`: '.PROJECT.' for clarity
  - `suffix`: '.tmp' for identification
  - `text`: False (binary mode for Windows compatibility)
- Content is written via `os.write(fd)` not `Path.write_text()`
- File descriptor is closed before rename

**Security rationale**: Eliminates race condition by using unpredictable filenames.

**Assertions**:
```python
mock_mkstemp.assert_called_once()
assert call_kwargs['dir'] == str(tmpdir)
assert call_kwargs['prefix'] == '.PROJECT.'
assert call_kwargs['suffix'] == '.tmp'
assert call_kwargs['text'] is False
mock_write.assert_called_once_with(mock_fd, b"expected content")
mock_close.assert_called_once_with(mock_fd)
```

---

#### 2. `test_atomic_write_closes_fd_on_error` ❌ FAILING
**Status**: DID NOT RAISE <class 'OSError'>

**What it tests**:
- File descriptor is closed even if `os.write()` fails
- Temp file is deleted on error (cleanup)
- Prevents resource exhaustion DoS

**Security rationale**: Leaked file descriptors cause "too many open files" errors. Each process has limited FD table (typically 1024 entries).

**Scenario**:
1. `mkstemp()` succeeds, returns FD 42
2. `os.write()` raises OSError("Disk full")
3. Implementation must call `os.close(42)` in finally block
4. Implementation must call `os.unlink(temp_path)` to free space

**Assertions**:
```python
with pytest.raises(IOError, match="Failed to write"):
    updater.update_goal_progress("Goal 1", 25)
mock_close.assert_called_once_with(mock_fd)
mock_unlink.assert_called_once_with(mock_path)
```

---

#### 3. `test_atomic_write_encodes_utf8_correctly` ❌ FAILING
**Status**: Expected 'write' to have been called once. Called 0 times.

**What it tests**:
- Content is UTF-8 encoded before passing to `os.write()`
- Unicode characters (emoji, international characters) are preserved
- No data corruption from encoding errors

**Security rationale**:
- `Path.write_text()` handles encoding automatically
- `os.write()` requires manual encoding to bytes
- Incorrect encoding can truncate unicode → data loss
- Missing encoding causes TypeError → availability issue

**Test case**: Uses emoji (🔒) to verify UTF-8 encoding works correctly.

**Assertions**:
```python
written_data = mock_write.call_args[0][1]
assert isinstance(written_data, bytes)
assert written_data == expected_content.encode('utf-8')
```

---

### Edge Case Tests (3 tests)

#### 4. `test_atomic_write_windows_compatibility` ✅ PASSING
**Status**: PASSING (implementation already uses `Path.replace()`)

**What it tests**:
- Atomic rename works on both POSIX and Windows
- Uses `Path.replace()` instead of `os.rename()`

**Windows vs POSIX difference**:
- **POSIX**: `rename()` atomically replaces target if exists
- **Windows**: `rename()` fails if target exists (must delete first)
- **Solution**: `Path.replace()` handles both platforms atomically

**Note**: This test is already passing because the current implementation correctly uses `Path.replace()`.

---

#### 5. `test_atomic_write_concurrent_writes_no_collision` ❌ FAILING
**Status**: AssertionError: Should create 2 temp files

**What it tests**:
- Two concurrent updaters create different temp files
- `mkstemp()` random suffix prevents collisions
- No race condition between concurrent processes

**Security rationale**:
- PID-based naming: Two processes can collide (PID reuse after wraparound)
- `mkstemp()`: Cryptographic random suffix (~0% collision probability)

**Test approach**: Creates two updaters, calls `_atomic_write()` on both, verifies temp filenames are different.

---

#### 6. `test_atomic_write_handles_enospc_error` ❌ FAILING
**Status**: DID NOT RAISE <class 'OSError'>

**What it tests**:
- Handles "No space left on device" (ENOSPC) gracefully
- Closes FD on disk full (prevents resource leak)
- Deletes temp file on disk full (frees space)

**Security rationale**: Disk full is an availability issue. Must clean up properly:
- Close FD to free file table entry
- Delete temp file to free disk space
- Raise clear error for caller

**Scenario**: Simulates `os.write()` raising `OSError(28, "No space left on device")`.

---

## Implementation Requirements Checklist

Based on the failing tests, the implementation must:

### Core Changes to `_atomic_write()` method:

- [ ] **Replace PID-based temp file creation with `mkstemp()`**
  ```python
  # OLD (VULNERABLE):
  temp_path = self.project_file.parent / f".PROJECT_{os.getpid()}.tmp"

  # NEW (SECURE):
  fd, temp_path_str = tempfile.mkstemp(
      dir=str(self.project_file.parent),
      prefix='.PROJECT.',
      suffix='.tmp',
      text=False
  )
  temp_path = Path(temp_path_str)
  ```

- [ ] **Write content via `os.write()` instead of `Path.write_text()`**
  ```python
  # OLD:
  temp_path.write_text(content, encoding='utf-8')

  # NEW:
  os.write(fd, content.encode('utf-8'))
  ```

- [ ] **Close file descriptor before rename**
  ```python
  os.close(fd)
  temp_path.replace(self.project_file)
  ```

- [ ] **Cleanup on error (in try/except/finally)**
  ```python
  fd = None
  temp_path = None
  try:
      fd, temp_path_str = tempfile.mkstemp(...)
      temp_path = Path(temp_path_str)
      os.write(fd, content.encode('utf-8'))
      os.close(fd)
      fd = None  # Mark as closed
      temp_path.replace(self.project_file)
  except Exception as e:
      # Cleanup on error
      if fd is not None:
          try:
              os.close(fd)
          except:
              pass
      if temp_path and temp_path.exists():
          try:
              temp_path.unlink()
          except:
              pass
      raise IOError(f"Failed to write PROJECT.md: {e}") from e
  ```

### Error Handling Requirements:

- [ ] Must close FD in all error paths (use finally block or context manager)
- [ ] Must delete temp file if write fails
- [ ] Must handle ENOSPC (disk full) gracefully
- [ ] Must handle encoding errors (unlikely with UTF-8 but defensive)
- [ ] Must raise clear IOError with context on failure

---

## Running the Tests

### Run all new security tests:
```bash
source .venv/bin/activate
python -m pytest tests/test_project_progress_update.py::TestProjectMdUpdaterAtomicWrites -v
python -m pytest tests/test_project_progress_update.py::TestProjectProgressEdgeCases::test_atomic_write_windows_compatibility -v
python -m pytest tests/test_project_progress_update.py::TestProjectProgressEdgeCases::test_atomic_write_concurrent_writes_no_collision -v
python -m pytest tests/test_project_progress_update.py::TestProjectProgressEdgeCases::test_atomic_write_handles_enospc_error -v
```

### Expected results BEFORE implementation:
- ❌ `test_atomic_write_uses_mkstemp_not_pid` - FAIL
- ❌ `test_atomic_write_closes_fd_on_error` - FAIL
- ❌ `test_atomic_write_encodes_utf8_correctly` - FAIL
- ✅ `test_atomic_write_windows_compatibility` - PASS (already correct)
- ❌ `test_atomic_write_concurrent_writes_no_collision` - FAIL
- ❌ `test_atomic_write_handles_enospc_error` - FAIL

### Expected results AFTER implementation:
- ✅ All tests PASS
- ✅ Security vulnerability eliminated
- ✅ Resource leaks prevented
- ✅ Cross-platform compatibility maintained

---

## Security Impact

**BEFORE (PID-based)**:
- ⚠️ **Race condition vulnerability**: Attacker can predict temp filename
- ⚠️ **Privilege escalation**: Symlink attack can write to arbitrary files
- ⚠️ **TOCTOU vulnerability**: Check-then-use window for attack

**AFTER (mkstemp-based)**:
- ✅ **No race condition**: Cryptographic random suffix (unpredictable)
- ✅ **No privilege escalation**: Atomic creation with O_EXCL prevents symlink attack
- ✅ **No TOCTOU**: File descriptor returned immediately on creation

**CVE Risk**: This vulnerability could warrant a CVE if exploited in production (privilege escalation via symlink attack).

---

## Next Steps

1. **implementer agent**: Implement the security fix in `project_md_updater.py`
2. **Run tests**: Verify all 6 tests pass (TDD green phase)
3. **reviewer agent**: Code review for correctness and edge cases
4. **security-auditor agent**: Validate vulnerability is eliminated
5. **doc-master agent**: Update CHANGELOG and security documentation

---

## References

- **CWE-367**: Time-of-check Time-of-use (TOCTOU) Race Condition
- **CWE-377**: Insecure Temporary File
- **OWASP**: A05:2021 - Security Misconfiguration
- **Python docs**: `tempfile.mkstemp()` - https://docs.python.org/3/library/tempfile.html#tempfile.mkstemp

---

**Test Coverage**: 6 tests covering:
- ✅ Core security fix (mkstemp usage)
- ✅ Resource leak prevention (FD cleanup)
- ✅ Encoding correctness (UTF-8)
- ✅ Platform compatibility (Windows/POSIX)
- ✅ Concurrent access (race conditions)
- ✅ Error handling (disk full)

**Target Coverage**: 80%+ of `_atomic_write()` method including error paths.

---

**Generated by**: test-master agent (TDD specialist)
**Date**: 2025-11-05
**Status**: TDD RED PHASE - Tests written, implementation pending
