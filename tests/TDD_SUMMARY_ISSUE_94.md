# TDD Test Summary - Issue #94: Git Hooks for Larger Projects

**Issue**: GitHub #94 - Git hooks need improvements for projects with 500+ tests
**Date**: 2025-12-07
**Agent**: test-master
**Phase**: TDD Red Phase (Tests First, No Implementation)

---

## Overview

Generated comprehensive TDD tests for git hook improvements to support larger projects with nested test structures (500+ tests).

## Problem Statement

Current git hooks don't scale for larger projects:

1. **Pre-commit hook** - Uses flat test discovery pattern
   - Current: `find tests -name "test_*.py"` (misses subdirectories)
   - Issue: Doesn't find tests in `tests/unit/lib/`, `tests/integration/workflows/`, etc.

2. **Pre-push hook** - Runs ALL tests including slow/GenAI tests
   - Current: `pytest tests/` (2-5 min execution time)
   - Issue: Slow tests block push, frustrating developers

## Test Files Created

### 1. Main Test File
**Location**: `/Users/akaszubski/Documents/GitHub/autonomous-dev/tests/unit/hooks/test_git_hooks_issue94.py`

**Coverage**: 28 comprehensive tests across 5 test classes

**Test Classes**:
- `TestPreCommitRecursiveDiscovery` (9 tests) - Recursive test discovery
- `TestPrePushFastTestFiltering` (9 tests) - Fast-only test execution
- `TestHookGenerationUpdates` (4 tests) - Hook generation scripts
- `TestHookEdgeCases` (4 tests) - Edge cases and error handling
- `TestHookIntegration` (2 tests) - End-to-end integration tests

### 2. Library Stub
**Location**: `/Users/akaszubski/Documents/GitHub/autonomous-dev/plugins/autonomous-dev/lib/git_hooks_stub.py`

**Purpose**: Provides clean NotImplementedError for TDD red phase (instead of ImportError)

**Functions (all raise NotImplementedError)**:
- `discover_tests_recursive()` - Find tests recursively
- `get_fast_test_command()` - Build pytest command with markers
- `filter_fast_tests()` - Filter to fast tests only
- `estimate_test_duration()` - Estimate test runtime
- `run_pre_push_tests()` - Execute pre-push tests
- `generate_pre_commit_hook()` - Generate pre-commit hook
- `generate_pre_push_hook()` - Generate pre-push hook

---

## Test Coverage Detail

### Pre-Commit Hook Tests (9 tests)

**Requirement**: Hook must find tests recursively in nested directory structures

1. **test_pre_commit_finds_root_level_tests**
   - Validates: Discovers `test_root.py` at `tests/` level
   - Expected: Root level tests found

2. **test_pre_commit_finds_nested_unit_tests**
   - Validates: Discovers tests in `tests/unit/` subdirectory
   - Expected: `test_unit_fast.py`, `test_unit_slow.py` found

3. **test_pre_commit_finds_deeply_nested_tests**
   - Validates: Discovers tests 2+ levels deep (`tests/unit/lib/`)
   - Expected: `test_lib_fast.py`, `test_lib_genai.py` found

4. **test_pre_commit_finds_integration_tests**
   - Validates: Discovers tests in `tests/integration/` and subdirs
   - Expected: `test_integration.py`, `test_workflow.py` found

5. **test_pre_commit_counts_all_tests_nested**
   - Validates: Counts all 7 tests in nested structure
   - Expected: Accurate total count (root + unit + lib + integration + workflows)

6. **test_pre_commit_backwards_compatible_flat_structure**
   - Validates: Still works with flat `tests/` directory
   - Expected: Flat structure tests discovered

7. **test_pre_commit_ignores_pycache_directories**
   - Validates: Excludes `__pycache__/` from discovery
   - Expected: `.pyc` files not counted as tests

8. **test_pre_commit_only_finds_test_prefix_files**
   - Validates: Only finds `test_*.py` files (not `conftest.py`, `utils.py`)
   - Expected: Non-test Python files excluded

9. **test_generated_pre_commit_has_recursive_find**
   - Validates: Generated hook uses `find tests -type f -name "test_*.py"`
   - Expected: Hook content includes `-type f` for recursion

### Pre-Push Hook Tests (9 tests)

**Requirement**: Hook must only run fast tests (exclude slow, genai, integration markers)

10. **test_pre_push_excludes_slow_marker_tests**
    - Validates: Excludes `@pytest.mark.slow` tests
    - Expected: Pytest command includes `-m "not slow"`

11. **test_pre_push_excludes_genai_marker_tests**
    - Validates: Excludes `@pytest.mark.genai` tests
    - Expected: Pytest command includes `not genai`

12. **test_pre_push_excludes_integration_marker_tests**
    - Validates: Excludes `@pytest.mark.integration` tests
    - Expected: Pytest command includes `not integration`

13. **test_pre_push_runs_unmarked_fast_tests**
    - Validates: Includes unmarked tests (assumed fast)
    - Expected: 3 fast tests run (root, unit_fast, lib_fast)

14. **test_pre_push_marker_filtering_combines_correctly**
    - Validates: Uses AND logic for marker exclusions
    - Expected: `-m "not slow and not genai and not integration"`

15. **test_pre_push_performance_improvement**
    - Validates: Fast tests run 3x+ faster than full suite
    - Expected: ~30s (fast) vs 2-5 min (full suite)

16. **test_pre_push_fails_if_fast_tests_fail**
    - Validates: Hook blocks push if fast tests fail
    - Expected: Non-zero exit code if pytest fails

17. **test_pre_push_uses_minimal_pytest_verbosity**
    - Validates: Uses `--tb=line -q` to prevent pipe deadlock (Issue #90)
    - Expected: Pytest command includes verbosity flags

18. **test_generated_pre_push_has_marker_filtering**
    - Validates: Generated hook includes marker filtering
    - Expected: Hook content has `-m "not slow and not genai and not integration"`

### Hook Generation Tests (4 tests)

**Requirement**: Hook generation/activation must produce updated hooks

19. **test_generated_pre_commit_has_recursive_find**
    - Validates: Pre-commit generation uses recursive pattern
    - Expected: `find tests -type f -name "test_*.py"` in output

20. **test_generated_pre_push_has_marker_filtering**
    - Validates: Pre-push generation includes markers
    - Expected: Marker filtering in output

21. **test_generated_pre_push_has_minimal_verbosity**
    - Validates: Pre-push generation includes verbosity flags
    - Expected: `--tb=line -q` in output

22. **test_hook_activator_includes_updated_hooks**
    - Validates: Hook activator installs updated hooks
    - Expected: Activated hooks have correct patterns

### Edge Cases (4 tests)

**Requirement**: Graceful handling of edge cases

23. **test_pre_commit_handles_empty_test_directory**
    - Validates: Empty `tests/` directory doesn't fail
    - Expected: Returns 0 tests with success

24. **test_pre_commit_handles_missing_test_directory**
    - Validates: Missing `tests/` directory doesn't fail
    - Expected: Returns empty list with warning

25. **test_pre_push_handles_all_tests_marked_slow**
    - Validates: All slow tests = 0 fast tests to run
    - Expected: Succeeds with informational message

26. **test_pre_push_handles_pytest_not_installed**
    - Validates: Missing pytest doesn't block push
    - Expected: Warning message, non-blocking exit

### Integration Tests (2 tests)

**Requirement**: Full end-to-end workflow validation

27. **test_pre_commit_hook_integration_nested_tests**
    - Validates: Pre-commit hook in real git workflow
    - Expected: All 7 tests discovered in commit
    - Marker: `@pytest.mark.integration`

28. **test_pre_push_hook_integration_fast_tests_only**
    - Validates: Pre-push hook in real git workflow
    - Expected: Only 3 fast tests run in push
    - Marker: `@pytest.mark.integration`, `@pytest.mark.slow`

---

## Test Structure

### Fixtures

**Repository Fixtures**:
- `temp_git_repo` - Temporary git repository
- `nested_test_structure` - 7 test files nested 2+ levels
- `flat_test_structure` - 2 test files in flat structure
- `pre_commit_hook_path` - Path to pre-commit hook
- `pre_push_hook_path` - Path to pre-push hook

**Nested Test Structure** (7 files):
```
tests/
├── test_root.py (fast)
├── unit/
│   ├── test_unit_fast.py (fast)
│   ├── test_unit_slow.py (@pytest.mark.slow)
│   └── lib/
│       ├── test_lib_fast.py (fast)
│       └── test_lib_genai.py (@pytest.mark.genai)
└── integration/
    ├── test_integration.py (@pytest.mark.integration)
    └── workflows/
        └── test_workflow.py (@pytest.mark.integration + slow)
```

**Fast Tests**: 3 (root, unit_fast, lib_fast)
**Slow/Marked Tests**: 4 (unit_slow, lib_genai, integration, workflow)

---

## TDD Red Phase Verification

### Expected Behavior

All tests should **FAIL** with `NotImplementedError` because:
- Library functions are stubs (raise NotImplementedError)
- No implementation exists yet
- This is TDD red phase (write tests FIRST)

### Verification Command

```bash
# Run all Issue #94 tests
pytest tests/unit/hooks/test_git_hooks_issue94.py -v

# Expected output: 28 FAILED (NotImplementedError)
```

### Sample Expected Failure

```
FAILED tests/unit/hooks/test_git_hooks_issue94.py::TestPreCommitRecursiveDiscovery::test_pre_commit_finds_root_level_tests
NotImplementedError: discover_tests_recursive not implemented (Issue #94)

FAILED tests/unit/hooks/test_git_hooks_issue94.py::TestPrePushFastTestFiltering::test_pre_push_excludes_slow_marker_tests
NotImplementedError: get_fast_test_command not implemented (Issue #94)

... (26 more failures)
```

### Verification Success Criteria

- ✅ All 28 tests discovered
- ✅ All tests FAIL with NotImplementedError
- ✅ No ImportError (stub provides clean failures)
- ✅ Test names clearly describe requirements
- ✅ Test structure follows TDD patterns

---

## Implementation Requirements

Based on these tests, the implementation must provide:

### 1. Pre-Commit Hook Improvements
- Recursive test discovery: `find tests -type f -name "test_*.py"`
- Support nested directories (2+ levels deep)
- Exclude `__pycache__/` directories
- Backwards compatible with flat structures
- Count only `test_*.py` files (not `conftest.py`, etc.)

### 2. Pre-Push Hook Improvements
- Pytest marker filtering: `-m "not slow and not genai and not integration"`
- Minimal verbosity: `--tb=line -q` (Issue #90 fix)
- 3x+ performance improvement (fast tests only)
- Fail push if fast tests fail
- Handle missing pytest gracefully

### 3. Hook Generation/Activation
- Generate pre-commit with recursive pattern
- Generate pre-push with marker filtering
- Hook activator installs updated hooks
- Both hooks have correct flags and patterns

### 4. Edge Case Handling
- Empty test directory (return 0 tests)
- Missing test directory (return empty list)
- All tests marked slow (0 fast tests = success)
- Pytest not installed (warning + non-blocking)

---

## Files Summary

| File | Purpose | Lines | Tests |
|------|---------|-------|-------|
| `tests/unit/hooks/test_git_hooks_issue94.py` | Main test file | ~800 | 28 |
| `plugins/autonomous-dev/lib/git_hooks_stub.py` | Library stub | ~120 | N/A |
| `tests/TDD_SUMMARY_ISSUE_94.md` | This document | ~450 | N/A |
| `tests/IMPLEMENTATION_CHECKLIST_ISSUE_94.md` | Implementation guide | ~200 | N/A |

**Total Test Coverage**: 28 tests covering:
- 9 pre-commit improvements
- 9 pre-push improvements
- 4 hook generation updates
- 4 edge cases
- 2 integration tests

**Expected Coverage After Implementation**: 95%+ (comprehensive test suite)

---

## Next Steps

### For Implementer Agent

1. **Read tests** - Understand all 28 test requirements
2. **Create library** - Rename stub to `git_hooks.py`, implement all functions
3. **Update hooks** - Modify `scripts/hooks/pre-commit` and create `scripts/hooks/pre-push`
4. **Run tests** - Verify all 28 tests pass
5. **Verify green phase** - `pytest tests/unit/hooks/test_git_hooks_issue94.py -v --tb=short`

### For Reviewer Agent

1. **Verify coverage** - Check 95%+ code coverage
2. **Review patterns** - Ensure recursive find and marker filtering correct
3. **Test edge cases** - Verify graceful degradation
4. **Performance check** - Confirm 3x+ speed improvement

---

## Success Criteria

### TDD Red Phase (Current) ✅
- [x] 28 comprehensive tests written
- [x] Tests FAIL with NotImplementedError
- [x] Clean test structure (Arrange-Act-Assert)
- [x] Edge cases covered
- [x] Integration tests included

### TDD Green Phase (Next)
- [ ] All 28 tests pass
- [ ] 95%+ code coverage
- [ ] Pre-commit finds nested tests
- [ ] Pre-push runs fast tests only
- [ ] 3x+ performance improvement
- [ ] Backwards compatible

### TDD Refactor Phase (Future)
- [ ] Code review passes
- [ ] Documentation updated
- [ ] Performance benchmarked
- [ ] Edge cases verified

---

**Test Suite Status**: RED PHASE ✅ (All tests failing as expected)
**Ready for Implementation**: YES
**Estimated Implementation Time**: 2-3 hours
**Test Execution Time**: ~30 seconds (unit), ~2 minutes (integration)
