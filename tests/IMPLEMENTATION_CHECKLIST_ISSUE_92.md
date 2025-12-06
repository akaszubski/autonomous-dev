# Implementation Checklist - Issue #92: Fix Strict Mode Template Hook References

**Status**: TDD RED PHASE COMPLETE - Ready for implementation

**Issue**: Strict mode template references `.claude/hooks/` (only exists after optional setup) instead of `plugins/autonomous-dev/hooks/` (always available after plugin install)

---

## Pre-Implementation Verification

- [x] Tests written and failing (TDD red phase)
- [x] All 9 hooks verified to exist in `plugins/autonomous-dev/hooks/`
- [x] Test coverage documented
- [x] Implementation plan reviewed

**Test Results**: 11 tests failing as expected (see TEST_COVERAGE_ISSUE_92.md)

---

## Implementation Tasks

### Task 1: Update Hook Paths in Template

**File**: `/Users/akaszubski/Documents/GitHub/autonomous-dev/plugins/autonomous-dev/templates/settings.strict-mode.json`

**Changes Required**: Update 9 hook paths

#### UserPromptSubmit Hooks (1 path)
- [ ] Line ~19: `python .claude/hooks/detect_feature_request.py` → `python plugins/autonomous-dev/hooks/detect_feature_request.py`

#### PostToolUse Hooks (2 paths - same hook for Write and Edit)
- [ ] Line ~28: `python .claude/hooks/auto_format.py` → `python plugins/autonomous-dev/hooks/auto_format.py` (Write matcher)
- [ ] Line ~35: `python .claude/hooks/auto_format.py` → `python plugins/autonomous-dev/hooks/auto_format.py` (Edit matcher)

#### PreCommit Hooks (7 paths)
- [ ] Line ~43: `python .claude/hooks/validate_project_alignment.py || exit 1` → `python plugins/autonomous-dev/hooks/validate_project_alignment.py || exit 1`
- [ ] Line ~46: `python .claude/hooks/enforce_orchestrator.py || exit 1` → `python plugins/autonomous-dev/hooks/enforce_orchestrator.py || exit 1`
- [ ] Line ~49: `python .claude/hooks/enforce_tdd.py || exit 1` → `python plugins/autonomous-dev/hooks/enforce_tdd.py || exit 1`
- [ ] Line ~52: `python .claude/hooks/auto_fix_docs.py || exit 1` → `python plugins/autonomous-dev/hooks/auto_fix_docs.py || exit 1`
- [ ] Line ~55: `python .claude/hooks/validate_session_quality.py || exit 1` → `python plugins/autonomous-dev/hooks/validate_session_quality.py || exit 1`
- [ ] Line ~58: `python .claude/hooks/auto_test.py || exit 1` → `python plugins/autonomous-dev/hooks/auto_test.py || exit 1`
- [ ] Line ~61: `python .claude/hooks/security_scan.py || exit 1` → `python plugins/autonomous-dev/hooks/security_scan.py || exit 1`

#### SubagentStop Hooks (unchanged - already correct)
- [x] Line ~68: `python scripts/session_tracker.py subagent 'Subagent completed task'` - NO CHANGE (correct path)

**Total Changes**: 9 path updates

---

## Validation Steps

### Step 1: Run Unit Tests
```bash
python -m pytest tests/unit/templates/test_strict_mode_template.py -v
```

**Expected Result**: All 16 tests pass (currently 7 failing)

**Key Tests to Watch**:
- `test_no_deprecated_claude_hooks_paths` - Should pass after update
- `test_hook_paths_use_plugin_directory` - Should pass after update
- `test_count_hook_references` - Should pass (9 hooks in plugins/, 1 in scripts/)
- `test_all_hooks_exist` - Should pass (all hooks exist in plugin dir)
- `test_detect_feature_request_hook` - Should pass
- `test_auto_format_hook` - Should pass
- `test_precommit_hooks` - Should pass

### Step 2: Run Integration Tests
```bash
python -m pytest tests/integration/test_strict_mode_workflow.py -v
```

**Expected Result**: All 11 tests pass (currently 4 failing)

**Key Tests to Watch**:
- `test_template_does_not_depend_on_claude_hooks` - Should pass
- `test_all_hooks_exist_in_plugin_directory` - Should pass
- `test_hook_paths_are_relative_to_project_root` - Should pass
- `test_all_9_hooks_referenced_correctly` - Should pass

### Step 3: Verify JSON Validity
```bash
python -c "import json; json.load(open('plugins/autonomous-dev/templates/settings.strict-mode.json'))"
```

**Expected Result**: No errors (valid JSON)

### Step 4: Manual Verification
```bash
# Check no .claude/hooks/ references remain
grep -r "\.claude/hooks/" plugins/autonomous-dev/templates/settings.strict-mode.json

# Should return nothing (exit code 1)
```

---

## Post-Implementation Verification

### Automated Checks
- [ ] All unit tests pass (16/16)
- [ ] All integration tests pass (11/11)
- [ ] JSON is valid
- [ ] No `.claude/hooks/` references remain

### Manual Checks
- [ ] All 9 hooks use `plugins/autonomous-dev/hooks/` prefix
- [ ] `session_tracker.py` still uses `scripts/` prefix (unchanged)
- [ ] No typos in hook paths
- [ ] Consistent formatting maintained

### End-to-End Test (Optional)
```bash
# Enable strict mode in a test project
# Verify hooks can execute without running optional setup.py
# This simulates real user experience after plugin installation
```

---

## Expected Test Results

### Before Implementation (Current)
```
Unit Tests:     9/16 passing, 7 failing
Integration:    7/11 passing, 4 failing
Total:         16/27 passing, 11 failing
```

### After Implementation (Target)
```
Unit Tests:     16/16 passing, 0 failing
Integration:    11/11 passing, 0 failing
Total:         27/27 passing, 0 failing
```

---

## Common Pitfalls to Avoid

1. **Don't change `session_tracker.py` path** - It's correctly in `scripts/`, not hooks
2. **Preserve exit codes** - All PreCommit hooks must have `|| exit 1`
3. **Don't add leading slashes** - Paths should be `plugins/...` not `/plugins/...`
4. **Don't use relative paths** - Use `plugins/autonomous-dev/hooks/` not `../../../plugins/...`
5. **Maintain JSON validity** - Easy to break with copy/paste errors

---

## Success Criteria

1. ✅ All 27 tests pass
2. ✅ Template is valid JSON
3. ✅ No `.claude/hooks/` references remain
4. ✅ All hooks use `plugins/autonomous-dev/hooks/` prefix (except session_tracker.py)
5. ✅ Strict mode works immediately after plugin installation (no setup needed)

---

## Files Modified

**Total**: 1 file

1. `/Users/akaszubski/Documents/GitHub/autonomous-dev/plugins/autonomous-dev/templates/settings.strict-mode.json` - Update 9 hook paths

**No new files created** - Only template updates needed

---

## Estimated Effort

**Time**: 5-10 minutes
**Complexity**: Low (simple find/replace in JSON file)
**Risk**: Very low (well-tested, no code changes)

---

**Ready for Implementation**: YES ✅

The implementer should:
1. Read this checklist
2. Update the 9 hook paths in settings.strict-mode.json
3. Run tests to verify all pass
4. Done!
