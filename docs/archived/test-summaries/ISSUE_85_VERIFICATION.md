# Issue #85 Verification Checklist

**Issue**: Hardcoded developer paths in auto-implement.md checkpoints
**Date**: 2025-11-17
**Status**: TDD Red Phase Complete (Tests written, awaiting implementation)

---

## Current State (BEFORE Implementation)

### Problems
- ❌ Hardcoded `/Users/akaszubski/Documents/GitHub/autonomous-dev` on lines 112 and 344
- ❌ Breaks for other developers
- ❌ Breaks in CI/CD environments
- ❌ Not cross-platform compatible

---

## Expected State (AFTER Implementation)

### Benefits
- ✅ Works from any directory (root, subdirectories)
- ✅ Cross-platform (Windows, macOS, Linux)
- ✅ Graceful fallback if path_utils unavailable
- ✅ Clear error messages guide users
- ✅ No breaking changes (same functionality)

---

## Test Results

### Current Test Status (TDD Red Phase)
```bash
source venv/bin/activate
pytest tests/integration/test_auto_implement_checkpoint_portability.py -v
```

**Results**:
- ✅ 16 tests PASS (infrastructure and portable logic work)
- ❌ 2 tests FAIL (expected - detect hardcoded paths)
- ⏭️ 1 test SKIP (Windows-specific, run on macOS)

**Failed Tests** (expected in TDD red phase):
1. `test_auto_implement_md_has_no_hardcoded_paths` - Detects `/Users/akaszubski`
2. `test_checkpoint_heredocs_contain_path_utils_import` - Heredocs missing path_utils

### Expected Test Status (After Implementation)
```
- ✅ 18 tests PASS (all working!)
- ⏭️ 1 test SKIP (Windows-specific)
```

---

## Verification Steps

After implementation, run these verification steps:

### 1. Run Tests
```bash
source venv/bin/activate
pytest tests/integration/test_auto_implement_checkpoint_portability.py -v
```
**Expected**: All 18 non-skipped tests PASS

### 2. Search for Hardcoded Paths
```bash
grep -n "/Users/akaszubski" plugins/autonomous-dev/commands/auto-implement.md
```
**Expected**: No results (empty output)

### 3. Verify CHECKPOINT 1 (line ~112)
```bash
sed -n '100,130p' plugins/autonomous-dev/commands/auto-implement.md | grep -E "cd /|from path_utils"
```
**Expected**: Contains `from path_utils import` or fallback logic

### 4. Verify CHECKPOINT 4.1 (line ~344)
```bash
sed -n '335,365p' plugins/autonomous-dev/commands/auto-implement.md | grep -E "cd /|from path_utils"
```
**Expected**: Contains `from path_utils import` or fallback logic

---

## Acceptance Criteria

Mark complete when ALL criteria met:

- [ ] All 18 tests PASS (only Windows test skipped on macOS)
- [ ] No hardcoded paths in auto-implement.md (grep returns empty)
- [ ] CHECKPOINT 1 (line ~112) uses dynamic path detection
- [ ] CHECKPOINT 4.1 (line ~344) uses dynamic path detection
- [ ] Both checkpoints use IDENTICAL detection logic
- [ ] Checkpoints work from project root (test passes)
- [ ] Checkpoints work from subdirectories (test passes)
- [ ] Clear error message if run outside repository (test passes)
- [ ] Graceful fallback if path_utils missing (test passes)
- [ ] Cross-platform (pathlib handles Windows/POSIX paths)

---

## Performance Impact

**Checkpoint Execution Time**:
- Path detection: ~10-50ms per checkpoint
- Total workflow time: Still 20-40 min (path detection is negligible)
- No impact on /auto-implement performance

**Token Impact**:
- Heredoc code increases by ~15 lines per checkpoint
- Still under 1KB total (minimal)
- No context bloat

---

## Breaking Changes

**None** - This is a transparent enhancement:
- Same functionality, just more portable
- Same output format
- Same error handling (actually better)
- Same checkpoint results

Users won't notice any difference except:
- ✅ Checkpoints now work from any directory
- ✅ Works for other developers (not just akaszubski)
- ✅ Works in CI/CD environments

---

## Related Files

**Modified**:
- `plugins/autonomous-dev/commands/auto-implement.md` (lines 112, 344)

**New**:
- `tests/integration/test_auto_implement_checkpoint_portability.py` (979 lines)
- `tests/integration/TEST_SUMMARY_ISSUE_85.md` (documentation)
- `tests/integration/ISSUE_85_TEST_PATTERNS.md` (reference guide)
- `tests/integration/ISSUE_85_VERIFICATION.md` (this file)

**Dependencies** (existing):
- `plugins/autonomous-dev/lib/path_utils.py` (already exists - Issue #79)
- `scripts/agent_tracker.py` (already exists)

---

## Commit Message Template

After implementation passes all tests:

```
fix: Replace hardcoded paths in auto-implement.md checkpoints (Issue #85)

Problem:
- Lines 112 and 344 had hardcoded /Users/akaszubski/... paths
- Broke portability for other developers and CI/CD environments

Solution:
- Use path_utils.get_project_root() for dynamic detection
- Fallback to manual .git/.claude search if path_utils unavailable
- Both checkpoints now work from any directory

Changes:
- CHECKPOINT 1 (line 112): Dynamic path detection
- CHECKPOINT 4.1 (line 344): Dynamic path detection
- Cross-platform (pathlib handles Windows/POSIX)

Tests:
- 19 comprehensive tests (16 passed initially, 2 failed as expected)
- All 18 tests now PASS (1 skipped - Windows-specific)
- Validates path detection, imports, errors, integration

Impact:
- No breaking changes (transparent enhancement)
- Checkpoints portable across developers and environments
- Graceful fallback if path_utils missing

Related: Issue #79 (path_utils.py)
Closes: Issue #85
```

---

## Next Steps

1. **Implementer Agent**: Modify auto-implement.md with portable heredocs
2. **Re-run Tests**: Verify all 18 tests PASS
3. **Manual Verification**: Test checkpoints from different directories
4. **Commit**: Use template above
5. **Document**: Update TROUBLESHOOTING.md if needed

---

**TDD Red Phase Complete** ✅
**Ready for Implementation** ✅
