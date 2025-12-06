# Implementation Checklist - Issue #94: Git Hooks for Larger Projects

**Issue**: GitHub #94
**Phase**: Ready for Implementation (TDD Green Phase)
**Tests**: 28 tests written and failing (red phase complete)

---

## Overview

This checklist guides the implementer through making all 28 TDD tests pass.

**Implementation Strategy**:
1. Library implementation (core logic)
2. Hook script updates (pre-commit, pre-push)
3. Hook generation updates (if applicable)
4. Verification (all tests pass)

---

## Step 1: Library Implementation

**File**: `plugins/autonomous-dev/lib/git_hooks.py`
**Action**: Rename stub and implement all functions

### Function 1: `discover_tests_recursive()`

**Tests**: 9 tests in `TestPreCommitRecursiveDiscovery`

**Requirements**:
- Find all `test_*.py` files recursively
- Use `find tests -type f -name "test_*.py"` or Python equivalent
- Exclude `__pycache__/` directories
- Return list of Path objects
- Handle empty/missing test directories gracefully

**Implementation Hints**:
```python
def discover_tests_recursive(tests_dir: Path) -> List[Path]:
    """Discover all test files recursively."""
    if not tests_dir.exists():
        return []

    # Use Path.rglob() for recursive search
    test_files = []
    for test_file in tests_dir.rglob("test_*.py"):
        # Exclude __pycache__
        if "__pycache__" not in str(test_file):
            test_files.append(test_file)

    return sorted(test_files)
```

**Passing Tests**:
- [ ] test_pre_commit_finds_root_level_tests
- [ ] test_pre_commit_finds_nested_unit_tests
- [ ] test_pre_commit_finds_deeply_nested_tests
- [ ] test_pre_commit_finds_integration_tests
- [ ] test_pre_commit_counts_all_tests_nested
- [ ] test_pre_commit_backwards_compatible_flat_structure
- [ ] test_pre_commit_ignores_pycache_directories
- [ ] test_pre_commit_only_finds_test_prefix_files
- [ ] test_pre_commit_handles_empty_test_directory
- [ ] test_pre_commit_handles_missing_test_directory

### Function 2: `get_fast_test_command()`

**Tests**: 6 tests in `TestPrePushFastTestFiltering`

**Requirements**:
- Return pytest command string
- Include marker filtering: `-m "not slow and not genai and not integration"`
- Include minimal verbosity: `--tb=line -q`
- Include tests directory path

**Implementation Hints**:
```python
def get_fast_test_command(tests_dir: Path) -> str:
    """Get pytest command for fast tests only."""
    return (
        f'pytest {tests_dir} '
        f'-m "not slow and not genai and not integration" '
        f'--tb=line -q'
    )
```

**Passing Tests**:
- [ ] test_pre_push_excludes_slow_marker_tests
- [ ] test_pre_push_excludes_genai_marker_tests
- [ ] test_pre_push_excludes_integration_marker_tests
- [ ] test_pre_push_marker_filtering_combines_correctly
- [ ] test_pre_push_uses_minimal_pytest_verbosity

### Function 3: `filter_fast_tests()`

**Tests**: 1 test

**Requirements**:
- Parse test files for pytest markers
- Return only tests without slow/genai/integration markers
- Read test file content and check for `@pytest.mark.*`

**Implementation Hints**:
```python
def filter_fast_tests(all_tests: List[str], tests_dir: Path) -> List[str]:
    """Filter test list to only fast tests."""
    fast_tests = []
    for test_name in all_tests:
        test_path = tests_dir / test_name
        if not test_path.exists():
            # Try finding it recursively
            matches = list(tests_dir.rglob(test_name))
            if not matches:
                continue
            test_path = matches[0]

        # Read file and check for markers
        content = test_path.read_text()
        if any(marker in content for marker in ["@pytest.mark.slow", "@pytest.mark.genai", "@pytest.mark.integration"]):
            continue

        fast_tests.append(test_name)

    return fast_tests
```

**Passing Tests**:
- [ ] test_pre_push_runs_unmarked_fast_tests

### Function 4: `estimate_test_duration()`

**Tests**: 1 test

**Requirements**:
- Estimate test runtime based on markers
- Fast tests: ~10s total (3 tests × ~3s each)
- Full suite: ~180s (mix of fast and slow)
- Return float (seconds)

**Implementation Hints**:
```python
def estimate_test_duration(tests_dir: Path, fast_only: bool = False) -> float:
    """Estimate test execution duration."""
    tests = discover_tests_recursive(tests_dir)

    if not tests:
        return 0.0

    if fast_only:
        # Fast tests: ~3 seconds each
        fast_count = len(filter_fast_tests([t.name for t in tests], tests_dir))
        return fast_count * 3.0
    else:
        # Full suite: fast (3s) + slow (30s) + genai (60s) + integration (20s)
        # Estimate based on markers
        total = 0.0
        for test in tests:
            content = test.read_text()
            if "@pytest.mark.genai" in content:
                total += 60.0
            elif "@pytest.mark.slow" in content:
                total += 30.0
            elif "@pytest.mark.integration" in content:
                total += 20.0
            else:
                total += 3.0
        return total
```

**Passing Tests**:
- [ ] test_pre_push_performance_improvement

### Function 5: `run_pre_push_tests()`

**Tests**: 3 tests

**Requirements**:
- Execute pytest with fast test filtering
- Return TestRunResult with returncode and output
- Handle pytest not installed (FileNotFoundError)
- Capture stdout/stderr

**Implementation Hints**:
```python
def run_pre_push_tests(tests_dir: Path) -> TestRunResult:
    """Run pre-push tests (fast only)."""
    cmd = get_fast_test_command(tests_dir)

    try:
        result = subprocess.run(
            cmd.split(),
            capture_output=True,
            text=True,
            cwd=tests_dir.parent if tests_dir.parent.exists() else Path.cwd()
        )

        output = result.stdout + result.stderr
        return TestRunResult(returncode=result.returncode, output=output)

    except FileNotFoundError:
        # Pytest not installed
        return TestRunResult(
            returncode=0,  # Non-blocking
            output="⚠️  Warning: pytest not installed, skipping pre-push tests"
        )
```

**Passing Tests**:
- [ ] test_pre_push_fails_if_fast_tests_fail
- [ ] test_pre_push_handles_all_tests_marked_slow
- [ ] test_pre_push_handles_pytest_not_installed

### Function 6: `generate_pre_commit_hook()`

**Tests**: 2 tests

**Requirements**:
- Return bash script content for pre-commit hook
- Include recursive find: `find tests -type f -name "test_*.py"`
- Include hook header and execution logic

**Implementation Hints**:
```python
def generate_pre_commit_hook() -> str:
    """Generate pre-commit hook content."""
    return '''#!/bin/bash
#
# Pre-commit hook - Validate test coverage with recursive discovery
#

set -e

echo "🔍 Discovering tests recursively..."

# Count tests recursively (supports nested structures)
TEST_COUNT=$(find tests -type f -name "test_*.py" 2>/dev/null | grep -v __pycache__ | wc -l)

echo "Found $TEST_COUNT test files"

# Add additional validation as needed

exit 0
'''
```

**Passing Tests**:
- [ ] test_generated_pre_commit_has_recursive_find

### Function 7: `generate_pre_push_hook()`

**Tests**: 2 tests

**Requirements**:
- Return bash script content for pre-push hook
- Include pytest with marker filtering
- Include minimal verbosity flags
- Include hook header

**Implementation Hints**:
```python
def generate_pre_push_hook() -> str:
    """Generate pre-push hook content."""
    return '''#!/bin/bash
#
# Pre-push hook - Run fast tests only (exclude slow, genai, integration)
#

set -e

echo "🧪 Running fast tests before push..."

# Run fast tests only (improves performance 3x+)
if command -v pytest &> /dev/null; then
    pytest tests/ -m "not slow and not genai and not integration" --tb=line -q
else
    echo "⚠️  Warning: pytest not installed, skipping tests"
fi

exit 0
'''
```

**Passing Tests**:
- [ ] test_generated_pre_push_has_marker_filtering
- [ ] test_generated_pre_push_has_minimal_verbosity

---

## Step 2: Hook Script Updates

### File 1: `scripts/hooks/pre-commit`

**Action**: Update existing hook with recursive find pattern

**Current Line**:
```bash
# Somewhere in the hook:
find tests -name "test_*.py"
```

**Updated Line**:
```bash
# Recursive discovery (supports nested test structures)
find tests -type f -name "test_*.py" | grep -v __pycache__
```

**Verification**:
```bash
# Test in repo root
cd /path/to/autonomous-dev
find tests -type f -name "test_*.py" | grep -v __pycache__ | wc -l
# Should count all tests (500+)
```

**Passing Tests**:
- [ ] test_generated_pre_commit_has_recursive_find
- [ ] test_pre_commit_hook_integration_nested_tests

### File 2: `scripts/hooks/pre-push` (NEW)

**Action**: Create new pre-push hook with fast test filtering

**Content**:
```bash
#!/bin/bash
#
# Pre-push hook - Run fast tests before pushing
#
# This hook runs only fast tests to provide quick feedback before push.
# Slow, GenAI, and integration tests are excluded (run in CI instead).
#
# To install: ln -sf ../../scripts/hooks/pre-push .git/hooks/pre-push
# To bypass: git push --no-verify

set -e

echo "🧪 Running fast tests before push..."

# Check if pytest is available
if ! command -v pytest &> /dev/null; then
    echo "⚠️  Warning: pytest not installed, skipping pre-push tests"
    echo "   Install: pip install pytest"
    exit 0  # Non-blocking
fi

# Run fast tests only (exclude slow, genai, integration markers)
echo "   Excluding: @pytest.mark.slow, @pytest.mark.genai, @pytest.mark.integration"

pytest tests/ -m "not slow and not genai and not integration" --tb=line -q

EXIT_CODE=$?

if [ $EXIT_CODE -eq 0 ]; then
    echo "✅ Fast tests passed"
else
    echo ""
    echo "❌ Fast tests failed - fix failures before pushing"
    echo "   To bypass (NOT recommended): git push --no-verify"
fi

exit $EXIT_CODE
```

**Installation**:
```bash
chmod +x scripts/hooks/pre-push
ln -sf ../../scripts/hooks/pre-push .git/hooks/pre-push
```

**Passing Tests**:
- [ ] test_generated_pre_push_has_marker_filtering
- [ ] test_generated_pre_push_has_minimal_verbosity
- [ ] test_pre_push_hook_integration_fast_tests_only

---

## Step 3: Hook Activation Updates (Optional)

**File**: `plugins/autonomous-dev/lib/hook_activator.py`

**Action**: Update to install new pre-push hook

**Requirements**:
- Activate both pre-commit and pre-push hooks
- Use updated hook content from generate_* functions
- Maintain backwards compatibility

**Passing Tests**:
- [ ] test_hook_activator_includes_updated_hooks

---

## Step 4: Verification

### Run All Tests

```bash
# Run Issue #94 tests only
pytest tests/unit/hooks/test_git_hooks_issue94.py -v --tb=short

# Expected: 28 passed (all green)
```

### Run Specific Test Classes

```bash
# Pre-commit tests
pytest tests/unit/hooks/test_git_hooks_issue94.py::TestPreCommitRecursiveDiscovery -v

# Pre-push tests
pytest tests/unit/hooks/test_git_hooks_issue94.py::TestPrePushFastTestFiltering -v

# Integration tests
pytest tests/unit/hooks/test_git_hooks_issue94.py::TestHookIntegration -v
```

### Verify Coverage

```bash
# Check code coverage
pytest tests/unit/hooks/test_git_hooks_issue94.py --cov=plugins/autonomous-dev/lib/git_hooks --cov-report=term-missing

# Expected: 95%+ coverage
```

### Manual Testing

```bash
# Test pre-commit hook
cd /path/to/autonomous-dev
scripts/hooks/pre-commit
# Should find 500+ tests recursively

# Test pre-push hook
scripts/hooks/pre-push
# Should run only fast tests (~30s, not 2-5 min)
```

---

## Success Criteria

### Code Quality
- [ ] All 28 tests pass (green phase)
- [ ] 95%+ code coverage
- [ ] No lint errors
- [ ] Type hints on all public functions
- [ ] Docstrings on all functions

### Functionality
- [ ] Pre-commit finds nested tests (2+ levels)
- [ ] Pre-commit excludes `__pycache__/`
- [ ] Pre-commit backwards compatible with flat structure
- [ ] Pre-push excludes slow/genai/integration tests
- [ ] Pre-push runs 3x+ faster than full suite
- [ ] Pre-push fails if fast tests fail
- [ ] Both hooks handle edge cases gracefully

### Documentation
- [ ] Function docstrings complete
- [ ] Hook comments explain purpose
- [ ] README updated with hook improvements
- [ ] CHANGELOG.md entry added

---

## Troubleshooting

### "NotImplementedError" still appearing
- Ensure you renamed `git_hooks_stub.py` to `git_hooks.py`
- Ensure test imports are updated to `from ...git_hooks import ...`

### Tests still failing after implementation
- Check function signatures match test expectations
- Verify return types (List[Path] vs List[str])
- Check Path objects vs strings in comparisons

### Integration tests failing
- Ensure hooks are executable: `chmod +x scripts/hooks/*`
- Check git is available in test environment
- Verify pytest is installed for hook execution

### Coverage below 95%
- Add tests for error paths
- Test edge cases (empty dirs, missing pytest)
- Ensure all functions have test coverage

---

## Estimated Timeline

| Task | Time | Status |
|------|------|--------|
| Library implementation | 1.5 hours | ⏳ |
| Hook script updates | 0.5 hours | ⏳ |
| Hook activation updates | 0.5 hours | ⏳ |
| Verification & testing | 0.5 hours | ⏳ |
| **Total** | **3 hours** | ⏳ |

---

## Next Steps After Implementation

1. **Run full test suite** - Ensure no regressions
2. **Update documentation** - README, CHANGELOG, hook comments
3. **Manual testing** - Test with actual large project (500+ tests)
4. **Performance benchmark** - Measure actual 3x+ improvement
5. **Code review** - Submit for review with test results
6. **Deploy** - Merge and release

---

**Implementation Status**: READY TO START
**Test Status**: RED PHASE (28 failing tests)
**Target**: GREEN PHASE (28 passing tests)
