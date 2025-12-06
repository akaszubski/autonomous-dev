# Implementation Checklist - Issue #82

**Feature**: Make checkpoint verification optional in /auto-implement
**Issue**: GitHub #82
**Date**: 2025-11-18
**Status**: TDD Red Phase (Tests written, implementation pending)

---

## Overview

This checklist guides implementation of optional AgentTracker verification in /auto-implement checkpoints.

**Goal**: Make /auto-implement work in user projects without scripts/ directory while maintaining full verification in autonomous-dev repo.

---

## Files to Modify

### 1. auto-implement.md (2 checkpoints)

**File**: `/plugins/autonomous-dev/commands/auto-implement.md`

#### CHECKPOINT 1 (Line ~138)

**Current Code** (blocks user projects):
```python
from scripts.agent_tracker import AgentTracker
tracker = AgentTracker()
success = tracker.verify_parallel_exploration()
print(f"\n{'✅ PARALLEL EXPLORATION: SUCCESS' if success else '❌ PARALLEL EXPLORATION: FAILED'}")
if not success:
    print("\n⚠️ One or more agents missing. Check session file for details.")
    print("Re-invoke missing agents before continuing to STEP 2.\n")
```

**New Code** (works everywhere):
```python
# Optional verification - gracefully degrade if AgentTracker unavailable
try:
    from scripts.agent_tracker import AgentTracker
    tracker = AgentTracker()
    success = tracker.verify_parallel_exploration()

    print(f"\n{'✅ PARALLEL EXPLORATION: SUCCESS' if success else '❌ PARALLEL EXPLORATION: FAILED'}")
    if not success:
        print("\n⚠️ One or more agents missing. Check session file for details.")
        print("Re-invoke missing agents before continuing to STEP 2.\n")

except ImportError:
    # User project without scripts/ directory - skip verification
    print("\nℹ️  Parallel exploration verification skipped (AgentTracker not available)")
    print("    This is normal for user projects. Verification only runs in autonomous-dev repo.")
    success = True

except AttributeError as e:
    # scripts.agent_tracker exists but missing methods
    print(f"\n⚠️  Parallel exploration verification unavailable: {e}")
    print("    Continuing workflow. Verification is optional.")
    success = True

except Exception as e:
    # Any other error - don't block workflow
    print(f"\n⚠️  Parallel exploration verification error: {e}")
    print("    Continuing workflow. Verification is optional.")
    success = True

# Checkpoint always succeeds - verification is informational only
if not success:
    print("\n⚠️  Continue to STEP 2 anyway (verification issues don't block workflow)")
```

---

#### CHECKPOINT 4.1 (Line ~403)

**Current Code** (blocks user projects):
```python
from scripts.agent_tracker import AgentTracker
tracker = AgentTracker()
success = tracker.verify_parallel_validation()

if success:
    # Extract parallel_validation metrics from session
    import json
    if tracker.session_file.exists():
        data = json.loads(tracker.session_file.read_text())
        metrics = data.get("parallel_validation", {})

        status = metrics.get("status", "unknown")
        time_saved = metrics.get("time_saved_seconds", 0)
        efficiency = metrics.get("efficiency_percent", 0)

        print(f"\n✅ PARALLEL VALIDATION: SUCCESS")
        print(f"   Status: {status}")
        print(f"   Time saved: {time_saved} seconds")
        print(f"   Efficiency: {efficiency}%")
else:
    print(f"\n❌ PARALLEL VALIDATION: FAILED")
    print("Check session file for details.")
```

**New Code** (works everywhere):
```python
# Optional verification - gracefully degrade if AgentTracker unavailable
try:
    from scripts.agent_tracker import AgentTracker
    tracker = AgentTracker()
    success = tracker.verify_parallel_validation()

    if success:
        # Extract metrics from session file
        import json
        if tracker.session_file and tracker.session_file.exists():
            data = json.loads(tracker.session_file.read_text())
            metrics = data.get("parallel_validation", {})

            status = metrics.get("status", "unknown")
            time_saved = metrics.get("time_saved_seconds", 0)
            efficiency = metrics.get("efficiency_percent", 0)

            print(f"\n✅ PARALLEL VALIDATION: SUCCESS")
            print(f"   Status: {status}")
            print(f"   Time saved: {time_saved} seconds")
            print(f"   Efficiency: {efficiency}%")
        else:
            print(f"\n✅ PARALLEL VALIDATION: SUCCESS")
    else:
        print(f"\n❌ PARALLEL VALIDATION: FAILED")
        print("Check session file for details.")

except ImportError:
    # User project without scripts/ directory - skip verification
    print("\nℹ️  Parallel validation verification skipped (AgentTracker not available)")
    print("    This is normal for user projects. Verification only runs in autonomous-dev repo.")
    success = True

except AttributeError as e:
    # scripts.agent_tracker exists but missing methods
    print(f"\n⚠️  Parallel validation verification unavailable: {e}")
    print("    Continuing workflow. Verification is optional.")
    success = True

except Exception as e:
    # Any other error - don't block workflow
    print(f"\n⚠️  Parallel validation verification error: {e}")
    print("    Continuing workflow. Verification is optional.")
    success = True

# Checkpoint always succeeds
if not success:
    print("\n⚠️  Continue to STEP 5 anyway (verification issues don't block workflow)")
```

---

## Implementation Steps

### Step 1: Backup Current Version
```bash
cp plugins/autonomous-dev/commands/auto-implement.md plugins/autonomous-dev/commands/auto-implement.md.backup
```

### Step 2: Update CHECKPOINT 1 (Line ~138)
1. Find the line: `from scripts.agent_tracker import AgentTracker`
2. Wrap entire verification block in try/except ImportError
3. Add try/except AttributeError for broken methods
4. Add try/except Exception for other errors
5. Set success = True in all except blocks
6. Add informational messages

### Step 3: Update CHECKPOINT 4.1 (Line ~403)
1. Find the line: `from scripts.agent_tracker import AgentTracker`
2. Apply same try/except pattern as CHECKPOINT 1
3. Ensure metrics extraction only runs when tracker available
4. Add null check: `if tracker.session_file and tracker.session_file.exists()`

### Step 4: Run Tests
```bash
# Run all Issue #82 tests
pytest tests/integration/test_issue82_optional_checkpoint_verification.py -v

# Expected: All 14 tests PASS
```

### Step 5: Manual Testing

**Test in user project** (no scripts/):
```bash
cd /path/to/user-project
/auto-implement "Add feature X"

# At CHECKPOINT 1: Should see "ℹ️  Parallel exploration verification skipped"
# At CHECKPOINT 4.1: Should see "ℹ️  Parallel validation verification skipped"
# Both checkpoints should succeed (not block workflow)
```

**Test in autonomous-dev repo** (WITH scripts/):
```bash
cd /path/to/autonomous-dev
/auto-implement "Add feature Y"

# At CHECKPOINT 1: Should see "✅ PARALLEL EXPLORATION: SUCCESS" or "❌ FAILED"
# At CHECKPOINT 4.1: Should see "✅ PARALLEL VALIDATION: SUCCESS" with metrics
# Both checkpoints should run full verification
```

---

## Verification Checklist

After implementation, verify:

- [ ] ✅ User projects work: ImportError caught → informational message (ℹ️)
- [ ] ✅ Broken scripts work: Runtime errors caught → warning message (⚠️)
- [ ] ✅ Dev repo verification: Full verification runs when agent_tracker available
- [ ] ✅ Exit code 0: Both checkpoints succeed in all scenarios
- [ ] ✅ Clear messages: Different icons for different scenarios
- [ ] ✅ Consistency: Both checkpoints use identical error handling
- [ ] ✅ All tests pass: `pytest tests/integration/test_issue82_optional_checkpoint_verification.py -v`
- [ ] ✅ Manual testing: Works in user project and dev repo
- [ ] ✅ Regression testing: Existing /auto-implement workflows unaffected

---

## Message Semantics

**ℹ️ Informational** (ImportError - normal in user projects):
```
ℹ️  Parallel exploration verification skipped (AgentTracker not available)
    This is normal for user projects. Verification only runs in autonomous-dev repo.
```

**⚠️ Warning** (Runtime errors - broken scripts):
```
⚠️  Parallel exploration verification unavailable: 'AgentTracker' object has no attribute 'verify_parallel_exploration'
    Continuing workflow. Verification is optional.
```

**✅ Success** (Verification passed):
```
✅ PARALLEL EXPLORATION: SUCCESS
```

**❌ Failure** (Verification failed - missing agents):
```
❌ PARALLEL EXPLORATION: FAILED

⚠️ One or more agents missing. Check session file for details.
Re-invoke missing agents before continuing to STEP 2.
```

---

## Success Criteria

Implementation is complete when:

1. ✅ Both checkpoints have try/except ImportError
2. ✅ Both checkpoints have try/except AttributeError
3. ✅ Both checkpoints have try/except Exception
4. ✅ success = True in all error paths
5. ✅ Informational message for ImportError
6. ✅ Warning message for runtime errors
7. ✅ Full verification message when tracker available
8. ✅ All 14 tests pass
9. ✅ Manual testing succeeds in both environments
10. ✅ No regressions in existing workflows

---

## Edge Cases Handled

1. **No scripts/ directory**: ImportError → skip gracefully
2. **Broken agent_tracker.py**: AttributeError → warn and continue
3. **Missing methods**: AttributeError → warn and continue
4. **Session file not found**: Handled by agent_tracker itself
5. **Invalid JSON in session**: Exception → warn and continue
6. **Symlink to scripts/**: Works (pathlib resolves)
7. **Windows paths**: Works (pathlib cross-platform)
8. **Permission errors**: Exception → warn and continue

---

## Rollback Plan

If issues arise after implementation:

```bash
# Restore backup
cp plugins/autonomous-dev/commands/auto-implement.md.backup plugins/autonomous-dev/commands/auto-implement.md

# Verify rollback
git diff plugins/autonomous-dev/commands/auto-implement.md
```

---

## Related Issues

- **Issue #85**: Hardcoded developer paths in auto-implement.md (already fixed)
- **Issue #82**: Make checkpoint verification optional (this issue)

Both issues improve /auto-implement portability for user projects.

---

**Implementation Ready**: All tests written, implementation checklist complete, success criteria defined.

**Next Step**: implementer agent will apply these changes to auto-implement.md.

---

**End of Implementation Checklist**
