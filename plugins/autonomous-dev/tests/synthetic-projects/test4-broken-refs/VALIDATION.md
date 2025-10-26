# Test Project 4: Broken References - Validation Guide

**Purpose**: Test Enhancement 4 - Automatic Cross-Reference Updates

## What This Tests

✅ `cross-reference-validation` skill
✅ `post_file_move.py` hook
✅ Broken file path detection
✅ Broken markdown link detection
✅ Invalid file:line reference detection
✅ Auto-update functionality

## Simulated Scenario

This project simulates the situation where:
1. Script files were moved from root to `scripts/debug/`
2. Documentation still references old paths
3. Cross-reference validation detects broken references
4. Auto-fix offers to update all references

## Planted Issues

### 1. Broken File Path References

**Files with broken references:**

- `README.md:7`
  - References: `./debug-local.sh`
  - Actual: `./scripts/debug/debug-local.sh`

- `docs/debugging/DEBUG-GUIDE.md:7`
  - References: `./debug-local.sh` (2 times)
  - Actual: `./scripts/debug/debug-local.sh`

- `docs/debugging/LMSTUDIO-FIX.md:7`
  - References: `./debug-local.sh`
  - Actual: `./scripts/debug/debug-local.sh`

- `docs/debugging/QUICK-START-LOCAL.md:9`
  - References: `./start-local.sh`
  - Actual: File doesn't exist (was never moved)

**Total**: 4 broken file path references in 4 files

### 2. Broken Markdown Link

- `README.md:11`
  - Links to: `docs/DEBUG-GUIDE.md`
  - Actual: `docs/debugging/DEBUG-GUIDE.md`

### 3. Broken File:Line Reference

- `docs/debugging/LMSTUDIO-FIX.md:9`
  - References: `src/server.ts:125`
  - Actual: File has only ~10 lines (line 125 doesn't exist)

**Total Issues**: 6 broken references

## Running Validation

### Option 1: Run /align-project

```bash
cd plugins/autonomous-dev/tests/synthetic-projects/test4-broken-refs
/align-project
```

Expected Phase 4 output:

```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
PHASE 4: Cross-Reference Validation
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Scanning documentation for references...

❌ BROKEN FILE PATH: README.md:7
   Referenced: ./debug-local.sh
   Status: File not found
   Detected move: ./scripts/debug/debug-local.sh
   Auto-fix: YES

❌ BROKEN FILE PATH: docs/debugging/DEBUG-GUIDE.md:7
   Referenced: ./debug-local.sh (2 occurrences)
   Status: File not found
   Detected move: ./scripts/debug/debug-local.sh
   Auto-fix: YES

❌ BROKEN FILE PATH: docs/debugging/DEBUG-GUIDE.md:13
   Referenced: ./start-local.sh
   Status: File not found
   No move detected
   Auto-fix: NO (file may have been deleted)

❌ BROKEN FILE PATH: docs/debugging/LMSTUDIO-FIX.md:7
   Referenced: ./debug-local.sh
   Status: File not found
   Detected move: ./scripts/debug/debug-local.sh
   Auto-fix: YES

❌ BROKEN FILE PATH: docs/debugging/QUICK-START-LOCAL.md:9
   Referenced: ./start-local.sh
   Status: File not found
   Auto-fix: NO

❌ BROKEN LINK: README.md:11
   Links to: docs/DEBUG-GUIDE.md
   Status: File not found
   Possible match: docs/debugging/DEBUG-GUIDE.md
   Auto-fix: YES (with confirmation)

❌ INVALID LINE REFERENCE: docs/debugging/LMSTUDIO-FIX.md:9
   References: src/server.ts:125
   Problem: File only has 10 lines
   Auto-fix: NO (suggest removing line number)

Issues found: 7 broken references
  - 4 file paths (3 auto-fixable)
  - 1 broken link (auto-fixable)
  - 1 invalid line reference (manual fix)
  - 1 missing file (deleted?)

Auto-fix available: 4/7 references
```

### Option 2: Simulate post_file_move Hook

```bash
# Simulate moving a file
cd plugins/autonomous-dev/tests/synthetic-projects/test4-broken-refs
python ../../../hooks/post_file_move.py "debug-local.sh" "scripts/debug/debug-local.sh"
```

Expected output:

```
🔍 Checking for documentation references to: debug-local.sh

📝 Found 4 reference(s) in documentation:
  - README.md:7
    For debugging, see: ./debug-local.sh

  - docs/debugging/DEBUG-GUIDE.md:7
    ./debug-local.sh

  - docs/debugging/DEBUG-GUIDE.md:13
    1. Check the debug script: ./debug-local.sh

  - docs/debugging/LMSTUDIO-FIX.md:7
    ./debug-local.sh

Auto-update all references to: scripts/debug/debug-local.sh? [Y/n] Y

🔄 Updating references...
  ✅ Updated: README.md
  ✅ Updated: docs/debugging/DEBUG-GUIDE.md
  ✅ Updated: docs/debugging/LMSTUDIO-FIX.md

✅ Updated 3 file(s)

Changed files:
Run 'git status' to see changes
```

## Expected Behavior - Interactive Fix

When user chooses Option 2 → Phase C:

```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
PHASE C: Cross-Reference Fixes
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Auto-fixable references:

1. Update 4 references to debug-local.sh:
   README.md:7
   docs/debugging/DEBUG-GUIDE.md:7
   docs/debugging/DEBUG-GUIDE.md:13
   docs/debugging/LMSTUDIO-FIX.md:7

   New path: scripts/debug/debug-local.sh

2. Update broken link in README.md:11:
   Old: docs/DEBUG-GUIDE.md
   New: docs/debugging/DEBUG-GUIDE.md

Apply auto-fixes? [Y/n/q]: Y

Updating references...
  ✅ Updated 4 file path references
  ✅ Updated 1 markdown link

Manual fixes needed:

⚠️ Invalid line reference: docs/debugging/LMSTUDIO-FIX.md:9
   Current: src/server.ts:125
   Problem: File only has 10 lines

   Options:
   1. Remove line number → src/server.ts
   2. Find correct line number
   3. Remove reference entirely

⚠️ Missing file: ./start-local.sh
   Referenced in:
   - docs/debugging/DEBUG-GUIDE.md:13
   - docs/debugging/QUICK-START-LOCAL.md:9

   Options:
   1. Create the missing file
   2. Remove references
   3. Update to different file

Please fix these manually and re-run /align-project.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Summary:
  ✅ Auto-fixed: 5 references
  ⚠️ Manual review needed: 2 references
```

## Validation Checklist

**Detection:**
- [ ] All 6 broken references detected
- [ ] File moves detected via existing files
- [ ] Markdown links validated
- [ ] File:line references checked

**Classification:**
- [ ] Auto-fixable vs manual fix correctly identified
- [ ] Moved files (auto-fix) vs deleted files (manual)
- [ ] Invalid line numbers detected

**Auto-Fix:**
- [ ] File path references updated
- [ ] Markdown links updated
- [ ] Multiple occurrences in same file handled
- [ ] Changes preview shown before applying

**Hook Integration:**
- [ ] post_file_move.py detects references
- [ ] Offers interactive update
- [ ] Shows preview of changes
- [ ] Updates all references atomically

## Success Criteria

✅ All 6 broken references detected
✅ 4-5 references correctly classified as auto-fixable
✅ File move detected via git or file existence
✅ Auto-fix updates all references correctly
✅ Manual fix suggestions provided for edge cases
✅ post_file_move hook works standalone
✅ Integration with /align-project Phase 4

## Common Issues

**Issue**: File moves not detected
**Cause**: No git history (git log shows move)
**Fix**: Either use file existence check or init git repo

**Issue**: References not found
**Cause**: Grep pattern doesn't match file paths with ./
**Fix**: Ensure grep searches for both "./file" and "file"

**Issue**: Auto-fix updates wrong occurrences
**Cause**: Overly broad search/replace
**Fix**: Should update exact matches only, not partial

## Cleanup

After testing:

```bash
# Restore original state
git checkout .

# Or manually revert auto-fixes
```

## Integration Test

Full workflow test:

```bash
# 1. Run alignment, see broken references
/align-project

# 2. Choose Option 2 (interactive fix)
# 3. Approve Phase C (cross-reference fixes)
# 4. Review manual fix suggestions

# 5. Run alignment again
/align-project

# Expected: Reduced issues (4-5 fixed, 1-2 manual remain)
```
