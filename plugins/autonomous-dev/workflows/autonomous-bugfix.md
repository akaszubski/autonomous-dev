---
name: Autonomous Bug Fix Workflow
description: TDD-driven bug fix with regression testing to prevent bug from returning
---

# Autonomous Bug Fix Workflow

Execute bug fixes using TDD to ensure bugs never return through regression testing.

## When to Use

- User reports bug: "Fix bug [description]"
- Tests are failing: "Tests failing: [error]"
- Issue reference: "Closes #123"
- Regression prevention needed

## Workflow Sequence

### Phase 1: Bug Analysis (2-5 minutes)

**Orchestrator Analyzes Bug**:
1. Read bug description from user
2. Examine error messages/stack traces
3. Review recent changes (`git diff`)
4. Identify affected components
5. Determine bug complexity

### Phase 2: Regression Test (5-10 minutes)

**Agent 1: Test-Master (Write Failing Test)**
- **Purpose**: Create test that reproduces the bug
- **Input**: Bug description + error details
- **Output**: Failing regression test
- **Actions**:
  1. Understand bug trigger conditions
  2. Write minimal test that reproduces bug
  3. Place test in `tests/regression/test_regression_suite.py`
  4. Run test to confirm it fails (bug present)
  5. Document bug details in test docstring:
     - Bug ID/issue number
     - Date found
     - Original error
     - Expected behavior
  6. Stage regression test file

**Validation**: Test MUST fail before proceeding (confirms bug reproduction)

### Phase 3: Bug Fix (5-15 minutes)

**Agent 2: Implementer (Fix Bug)**
- **Purpose**: Implement minimal fix to make test pass
- **Input**: Bug description + failing regression test
- **Output**: Bug fix implementation
- **Actions**:
  1. Review failing test and bug details
  2. Identify root cause
  3. Implement minimal fix (smallest change possible)
  4. Preserve existing functionality
  5. Add error handling if needed
  6. Run regression test to verify fix
  7. Ensure no other changes

**Requirements**:
- Minimal changes only
- No refactoring (unless necessary for fix)
- No additional features
- Preserve existing tests

### Phase 4: Validation (5-10 minutes)

**Agent 3: Test-Master (Run Full Suite)**
- **Purpose**: Verify fix works and no regressions introduced
- **Input**: Bug fix implementation
- **Output**: Full test results
- **Actions**:
  1. Run regression test (should now pass ✅)
  2. Run full test suite (all tests should pass ✅)
  3. Measure coverage (should maintain or improve)
  4. Verify no test regressions
  5. Report results
  6. If failures: loop back to implementer with errors

**Validation Criteria**:
- ✅ Regression test now passes (bug fixed)
- ✅ All existing tests still pass (no regressions)
- ✅ Coverage maintained or improved

### Phase 5: Security Check (2-5 minutes)

**Agent 4: Security-Auditor (Quick Scan)**
- **Purpose**: Ensure fix doesn't introduce security issues
- **Input**: Bug fix changes
- **Output**: Security scan report
- **Actions**:
  1. Scan changed files for security issues
  2. Check if bug was security-related
  3. Verify no new vulnerabilities
  4. Quick dependency check
  5. Report findings

**Focus**: Only scan changes (not full codebase)

### Phase 6: Documentation (2-5 minutes)

**Agent 5: Doc-Master (Update CHANGELOG)**
- **Purpose**: Document bug fix
- **Input**: Bug details + fix description
- **Output**: Updated CHANGELOG.md
- **Actions**:
  1. Add entry to CHANGELOG.md under "### Fixed"
  2. Include bug ID/issue number
  3. Brief description of bug
  4. Brief description of fix
  5. Stage CHANGELOG changes

**CHANGELOG Format**:
```markdown
### Fixed
- Fixed [bug description] ([#123](link-to-issue))
  - Symptoms: [what users experienced]
  - Cause: [root cause]
  - Fix: [what was changed]
```

### Phase 7: Completion (1 minute)

**Orchestrator Reports**:
```
✅ Bug Fix Complete

Bug: [Description]
Issue: #123
Duration: [X] minutes

Results:
- Regression Test: ✅ Created and passing
- Bug Fix: ✅ Minimal fix implemented
- Full Test Suite: ✅ All [N] tests passing
- No Regressions: ✅ Verified
- Security: ✅ No new issues
- CHANGELOG: ✅ Updated

Files Modified:
- [implementation file] (bug fix)
- tests/regression/test_regression_suite.py (regression test)
- CHANGELOG.md (documentation)

This bug will never return - regression test will catch it!

Ready to commit
Suggested commit message: "fix: [bug description] (closes #123)"
```

## Success Criteria

Bug fix is complete when:
- ✅ Regression test reproduces bug (initially failing)
- ✅ Fix makes regression test pass
- ✅ All other tests still pass (no regressions)
- ✅ Coverage maintained or improved
- ✅ Security scan clean
- ✅ CHANGELOG updated
- ✅ Minimal changes (no unnecessary modifications)

## Regression Test Best Practices

### Test Docstring Format
```python
def test_bug_123_description(self):
    """
    Regression test: [Brief bug description]

    Bug: [What was broken]
    Cause: [Why it broke]
    Fix: [How it was fixed]
    Date: [YYYY-MM-DD]
    Issue: #123

    Ensures we don't regress to [specific error].
    """
    # Test implementation
```

### Test Location
- **General bugs**: `tests/regression/test_regression_suite.py`
- **Category-specific**: `tests/regression/test_[category]_regressions.py`

### Test Categories
```python
class TestAuthRegressions:
    """Authentication-related regression tests."""

class TestMLXRegressions:
    """MLX framework-specific regression tests."""

class TestDataRegressions:
    """Data processing regression tests."""
```

## Error Handling

### Test Still Fails After Fix
→ Review fix logic
→ Re-implement fix
→ Re-run tests
→ Max 2 retries
→ If still failing: escalate to user

### New Tests Failing (Regressions)
→ Revert fix
→ Analyze failing tests
→ Implement different fix approach
→ Re-run full suite

### Security Issue Introduced
→ Pass findings to implementer
→ Request security fix
→ Re-scan
→ Re-validate

## Time Estimates

- **Simple bug**: 10-15 minutes
- **Medium bug**: 20-30 minutes
- **Complex bug**: 35-50 minutes

## Comparison: Manual vs Autonomous

| Aspect | Manual | Autonomous |
|--------|--------|------------|
| Write regression test | Sometimes | Always (enforced) |
| Run full test suite | Sometimes | Always (enforced) |
| Security check | Rarely | Always (automated) |
| CHANGELOG update | Often forgotten | Always (automated) |
| Time to fix | Varies widely | Consistent 10-30 min |
| Bug returns | Possible | Prevented (regression test) |

## Context Management

After bug fix completes:
```bash
/clear
```

This clears conversation context while preserving:
- Bug fix code
- Regression test
- CHANGELOG entry
- Git history

---

**This workflow ensures bugs are fixed once and never return. Invoke via orchestrator agent or directly: "Fix bug [description]"**
