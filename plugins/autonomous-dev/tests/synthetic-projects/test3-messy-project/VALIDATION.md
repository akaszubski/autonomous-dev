# Test Project 3: Messy Project - Validation Guide

**Purpose**: Test Enhancement 2 - File Organization Enforcement

## What This Tests

✅ `file-organization` skill enforcement
✅ Pre-commit hook file organization validation
✅ Auto-fix mode (files moved to correct locations)
✅ Root directory policy enforcement

## Planted Issues

This project intentionally has these misplaced files:

### 1. Shell Scripts in Root (Should be in scripts/)
- `test-auth.sh` → Should be `scripts/test/test-auth.sh`
- `debug-local.sh` → Should be `scripts/debug/debug-local.sh`

### 2. Documentation in Root (Should be in docs/)
- `USER-GUIDE.md` → Should be `docs/guides/user-guide.md`
- `ARCHITECTURE.md` → Should be `docs/architecture/ARCHITECTURE.md`
- `DEBUG-GUIDE.md` → Should be `docs/debugging/debug-guide.md`
- `API-REFERENCE.md` → Should be `docs/reference/api-reference.md`

### 3. Source Code in Root (Should be in src/)
- `helper.ts` → Should be `src/helper.ts`
- `utils.ts` → Should be `src/utils.ts`

**Total**: 8 misplaced files

## Running Validation

### Option 1: Use /align-project

```bash
cd plugins/autonomous-dev/tests/synthetic-projects/test3-messy-project
/align-project
```

Expected Phase 1 output:

```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
PHASE 1: Structural Validation
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

❌ Root directory violations:

Shell scripts in root (should be in scripts/):
  - test-auth.sh → scripts/test/test-auth.sh
  - debug-local.sh → scripts/debug/debug-local.sh

Non-essential .md files in root (should be in docs/):
  - USER-GUIDE.md → docs/guides/user-guide.md
  - ARCHITECTURE.md → docs/architecture/ARCHITECTURE.md
  - DEBUG-GUIDE.md → docs/debugging/debug-guide.md
  - API-REFERENCE.md → docs/reference/api-reference.md

Source code in root (should be in src/):
  - helper.ts → src/helper.ts
  - utils.ts → src/utils.ts

Issues found: 8 misplaced files

Auto-fix available: YES (all 8 files can be moved automatically)
```

### Option 2: Test Auto-Fix on File Creation

Simulate Claude creating a new file in wrong location:

```
When file-organization skill is active:

Proposed: ./test-new-feature.sh

🤖 file-organization skill activated

Proposed: ./test-new-feature.sh
Rule Check: Shell scripts → scripts/debug/ or scripts/test/
File Purpose: Testing script (detected from "test-" prefix)
Correct Location: scripts/test/

✅ Auto-corrected to: scripts/test/test-new-feature.sh
   Reason: Testing scripts belong in scripts/test/ (CLAUDE.md:12)
```

### Option 3: Test Pre-Commit Hook

Try to commit misplaced files:

```bash
git init
git add test-auth.sh USER-GUIDE.md helper.ts
git commit -m "test commit"
```

Expected output:

```
🔍 Validating file organization...

❌ Attempting to commit files in wrong locations:

Shell scripts in root:
  - test-auth.sh

Non-essential .md in root:
  - USER-GUIDE.md

Source code in root:
  - helper.ts

Move to correct locations per CLAUDE.md/PROJECT.md

Commit blocked.
```

## Expected Behavior - Phase 1 of /align-project

```
PHASE 1: Structural Validation

Checking root directory...
  ❌ Too many .md files: 9/8 allowed
  ❌ Non-essential files:
     - USER-GUIDE.md
     - ARCHITECTURE.md
     - DEBUG-GUIDE.md
     - API-REFERENCE.md

Checking scripts organization...
  ❌ Shell scripts in wrong location:
     - ./test-auth.sh (should be scripts/test/)
     - ./debug-local.sh (should be scripts/debug/)

Checking source code organization...
  ❌ Source files in wrong location:
     - ./helper.ts (should be src/)
     - ./utils.ts (should be src/)

Total issues: 8 files misplaced
```

## Expected Behavior - Option 2 (Interactive Fix)

When user chooses Option 2:

```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
PHASE A: File Organization Fixes
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Proposed moves:
  1. test-auth.sh → scripts/test/test-auth.sh
  2. debug-local.sh → scripts/debug/debug-local.sh
  3. USER-GUIDE.md → docs/guides/user-guide.md
  4. ARCHITECTURE.md → docs/architecture/ARCHITECTURE.md
  5. DEBUG-GUIDE.md → docs/debugging/debug-guide.md
  6. API-REFERENCE.md → docs/reference/api-reference.md
  7. helper.ts → src/helper.ts
  8. utils.ts → src/utils.ts

Apply Phase A? [Y/n/q]: Y

Creating directories...
  ✅ Created scripts/test/
  ✅ Created scripts/debug/
  ✅ Created docs/guides/
  ✅ Created docs/architecture/
  ✅ Created docs/debugging/
  ✅ Created docs/reference/
  ✅ Created src/

Moving files...
  ✅ test-auth.sh → scripts/test/test-auth.sh
  ✅ debug-local.sh → scripts/debug/debug-local.sh
  ✅ USER-GUIDE.md → docs/guides/user-guide.md
  ✅ ARCHITECTURE.md → docs/architecture/ARCHITECTURE.md
  ✅ DEBUG-GUIDE.md → docs/debugging/debug-guide.md
  ✅ API-REFERENCE.md → docs/reference/api-reference.md
  ✅ helper.ts → src/helper.ts
  ✅ utils.ts → src/utils.ts

✅ All 8 files moved to correct locations
```

## Validation Checklist

**Detection:**
- [ ] All 8 misplaced files detected
- [ ] Correct target locations suggested
- [ ] Categories inferred correctly (test-*.sh → scripts/test/)

**Auto-Fix:**
- [ ] Directories created if missing
- [ ] Files moved to correct locations
- [ ] Original files removed
- [ ] No broken references (or cross-ref validation catches them)

**Pre-Commit:**
- [ ] Blocks commits with misplaced files
- [ ] Provides clear error messages
- [ ] Suggests correct locations

**File Organization Skill:**
- [ ] Intercepts file creation in wrong location
- [ ] Auto-corrects to right location
- [ ] Logs correction to audit trail

## Success Criteria

✅ All 8 misplaced files detected in Phase 1
✅ Correct target directories identified
✅ Auto-fix moves all files correctly
✅ Directories created as needed
✅ Pre-commit hook blocks commits with misplaced files
✅ File organization skill prevents future misplacements
✅ Root directory clean after fix (only essential .md files)

## Common Issues

**Issue**: Skill doesn't intercept file creation
**Cause**: file-organization skill not registered as auto-invoke
**Fix**: Check skill frontmatter has `auto_invoke: true`

**Issue**: Pre-commit allows misplaced files through
**Cause**: Hook not installed or not executable
**Fix**: Run /setup to install hooks

**Issue**: Auto-fix doesn't create directories
**Cause**: mkdir -p flag missing
**Fix**: Verify fix implementation creates parent directories

## Cleanup

After testing, you can reset the project:

```bash
# Move files back to wrong locations
git checkout .

# Or delete and recreate from template
```
