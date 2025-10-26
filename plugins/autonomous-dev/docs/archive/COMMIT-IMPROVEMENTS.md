# `/commit` Command Improvements

**Proposed enhancements based on three-layer testing framework**

---

## Current State

**Current `/commit` command**:
```bash
/commit                 # Generate message, commit
/commit --check         # Run /full-check first (format + test + security)
/commit "message"       # Use custom message
```

**Current --check runs**:
1. `/format` - Code formatting
2. `/test` - All pytest tests
3. `/security-scan` - Security check
4. Then commits if all pass

---

## Proposed Improvements

### 1. Layered Testing Integration ⭐

**Add `--layer` flag** for different validation levels:

```bash
# Layer 1: Fast (current default)
/commit --layer=1
/commit --quick           # Alias
# Runs: format + unit tests + security (< 5s)

# Layer 2: Standard (new default) ⭐
/commit --layer=2
/commit --check          # Updated behavior
# Runs: format + all tests + security (< 60s)

# Layer 3: Complete (pre-merge/release)
/commit --layer=3
/commit --complete       # Alias
# Runs: format + all tests + uat-genai + architecture + security (2-5min)
```

---

### 2. Smart Default Based on Changes

**Auto-detect validation level** based on files changed:

```bash
/commit --smart          # New flag (could be default)

# Detection logic:
# - Tests only? → Layer 1 (quick)
# - Documentation only? → Layer 1 (quick)
# - Core logic changed? → Layer 2 (standard)
# - API/UX changed? → Layer 3 (complete with GenAI)
# - Architecture changed? → Layer 3 (complete)
```

**Example**:
```bash
$ /commit --smart

Analyzing changes...
- Modified: src/api/endpoints.py (API change)
- Modified: src/models/user.py (core logic)
- Added: tests/test_api.py

Detected: API/UX changes
Recommended validation: Layer 3 (complete)

Proceed with Layer 3 validation? [Y/n/1/2]:
```

---

### 3. Pre-Commit Validation Report

**Show validation results inline**:

```bash
$ /commit --layer=3

┌─ Pre-Commit Validation ─────────────────────┐
│                                              │
│ Layer 1: Code Quality                       │
│  ✅ Formatting: PASSED                       │
│  ✅ Unit Tests: PASSED (45/45, 0.8s)         │
│  ✅ Security: PASSED                         │
│                                              │
│ Layer 2: Integration                        │
│  ✅ Integration Tests: PASSED (12/12, 4.2s)  │
│  ✅ UAT Tests: PASSED (8/8, 15.3s)           │
│  ✅ Coverage: 92% (target: 80%+) ✅          │
│                                              │
│ Layer 3: Quality Validation (GenAI)         │
│  ✅ UX Quality: 8.5/10 ✅                     │
│  ✅ Architecture: 100% aligned ✅             │
│  ⚠️  1 optimization opportunity found        │
│                                              │
│ Total time: 2m 15s                           │
│ All required checks: PASSED ✅               │
│                                              │
└──────────────────────────────────────────────┘

Issues found: 1 optimization (non-blocking)
 → Created issue #42: "Switch reviewer to Haiku (save 92%)"

Proceed with commit? [Y/n]:
```

---

### 4. Auto-Track Issues During Commit

**Integrate with automatic issue tracking**:

```bash
/commit --track-issues   # Enable issue tracking
/commit --layer=3        # Auto-enables tracking

# During validation:
# - Test failures → Create bug issues
# - UX problems → Create enhancement issues
# - Optimizations → Create optimization issues
# - All automatic, non-blocking
```

**Example**:
```bash
$ /commit --layer=3 --track-issues

Running Layer 3 validation...
✅ All tests passed
⚠️  UX validation found 1 issue
   ✅ Created issue #43: "No progress indicator during export"

⚠️  Architecture validation found 1 drift
   ✅ Created issue #44: "Context management drift in orchestrator"

Validation: PASSED (issues are non-blocking)
Created 2 issues for future improvement

Proceed with commit? [Y/n]:
```

---

### 5. Validation Profiles

**Pre-configured validation sets**:

```bash
# Profiles in .env or PROJECT.md
COMMIT_PROFILE_DEV=layer1        # Quick during dev
COMMIT_PROFILE_FEATURE=layer2    # Standard for features
COMMIT_PROFILE_RELEASE=layer3    # Complete for releases

# Usage
/commit --profile=dev       # Quick
/commit --profile=feature   # Standard
/commit --profile=release   # Complete
/commit                     # Uses COMMIT_PROFILE_DEFAULT
```

---

### 6. Commit Message Enhancement with Test Results

**Include test summary in commit message footer**:

```bash
$ /commit --layer=2

Generated message:
┌──────────────────────────────────────────┐
│ feat(api): add user export functionality │
│                                          │
│ - Added CSV and JSON export formats     │
│ - Added progress indicators              │
│ - Added export rate limiting             │
│                                          │
│ Closes #38                               │
│                                          │
│ Validation:                              │
│ - Tests: 57/57 passed (95% coverage)     │
│ - UX Score: 8/10                         │
│ - Security: PASSED                       │
│                                          │
│ 🤖 Generated with Claude Code            │
│ Co-Authored-By: Claude <noreply@...>    │
└──────────────────────────────────────────┘
```

---

### 7. Fail-Fast Options

**Stop on first failure or continue**:

```bash
/commit --fail-fast      # Stop on first failure (default)
/commit --continue       # Run all checks, report all issues

# With --continue:
$ /commit --layer=3 --continue

✅ Layer 1: PASSED
❌ Layer 2: FAILED (2 integration tests failed)
   → Created issue #45, #46
⚠️  Layer 3: UX score 6/10 (below 8/10 target)
   → Created issue #47

Summary:
- Critical failures: 2 (blocking)
- Warnings: 1 (non-blocking)
- Issues created: 3

Cannot commit (critical failures present)
Fix issues #45, #46 first
```

---

### 8. Selective Layer Execution

**Run specific layers only**:

```bash
/commit --layers=1,3     # Layer 1 + Layer 3 (skip Layer 2)
/commit --skip-genai     # Skip GenAI validation
/commit --genai-only     # Only GenAI validation
/commit --quick-genai    # Only UX (skip architecture)
```

---

## Improved Command Structure

### New Flags

```bash
/commit [message]                      # Basic commit
  --layer=1|2|3                        # Validation layer
  --quick | --complete                 # Aliases for layer 1 | 3
  --smart                              # Auto-detect layer
  --profile=dev|feature|release        # Use profile
  --track-issues                       # Enable issue tracking
  --fail-fast | --continue             # Failure behavior
  --layers=1,2,3                       # Selective layers
  --skip-genai                         # Skip GenAI validation
  --dry-run                            # Show what would run
  --force                              # Skip validation (emergency only)
```

### Usage Examples

```bash
# During development (fast)
/commit --quick
/commit --layer=1

# Feature complete (standard)
/commit --check
/commit --layer=2

# Before merge/release (complete)
/commit --complete
/commit --layer=3 --track-issues

# Smart detection
/commit --smart

# Custom
/commit --layers=1,3 --track-issues

# Emergency (skip all validation)
/commit --force "hotfix: critical security patch"
```

---

## Enhanced Workflow

### Workflow 1: Quick Dev Commits

```bash
# Fast iteration during development
git add .
/commit --quick

# Runs:
# - Format
# - Unit tests only (< 1s)
# - Security scan
# - Commit

# Total time: < 5s
```

---

### Workflow 2: Feature Complete

```bash
# Feature done, ready for review
git add .
/commit --check

# Runs:
# - Format
# - All pytest tests (unit + integration + UAT)
# - Security scan
# - Commit

# Total time: < 60s
```

---

### Workflow 3: Pre-Merge Validation

```bash
# Before merging to main
git add .
/commit --complete --track-issues

# Runs:
# - Format
# - All pytest tests
# - GenAI UX validation
# - GenAI architecture validation
# - Security scan
# - Auto-creates issues for findings
# - Commit

# Total time: 2-5min
# Issues created: Non-blocking warnings tracked
```

---

### Workflow 4: Smart Commit (Recommended Default)

```bash
# Let command decide validation level
git add .
/commit --smart

# Auto-detects based on changes:
# - Docs only? → Layer 1
# - Tests only? → Layer 1
# - Core logic? → Layer 2
# - API/UX? → Layer 3
# - Architecture? → Layer 3

# Asks for confirmation if Layer 3
```

---

## Configuration

### .env Configuration

```bash
# Default validation layer
COMMIT_DEFAULT_LAYER=2              # 1, 2, or 3

# Smart detection
COMMIT_SMART_DETECT=true            # Enable smart layer detection

# Issue tracking
COMMIT_AUTO_TRACK_ISSUES=true       # Always track issues on commit
COMMIT_TRACK_LAYER=3                # Only track on layer 3

# Behavior
COMMIT_FAIL_FAST=true               # Stop on first failure
COMMIT_SHOW_SUMMARY=true            # Show validation summary

# Profiles
COMMIT_PROFILE_DEFAULT=feature      # dev, feature, release
```

---

### PROJECT.md Configuration

```markdown
## Commit Validation

**Default Layer**: 2 (standard)
**Smart Detection**: Enabled
**Issue Tracking**: Layer 3 only

**Profiles**:
- `dev`: Layer 1 (quick) - for rapid iteration
- `feature`: Layer 2 (standard) - for feature completion
- `release`: Layer 3 (complete) - for merges and releases

**File-based Rules**:
- `src/api/**` → Layer 3 (API changes need UX validation)
- `src/core/**` → Layer 2 (core logic needs full tests)
- `docs/**` → Layer 1 (docs need minimal validation)
- `tests/**` → Layer 1 (tests need quick validation)
```

---

## Comparison: Current vs Proposed

| Feature | Current | Proposed |
|---------|---------|----------|
| **Validation Levels** | 2 (none, --check) | 4 (none, layer 1/2/3) |
| **Smart Detection** | ❌ No | ✅ Yes |
| **Issue Tracking** | ❌ Manual | ✅ Automatic |
| **Test Summary** | ❌ No | ✅ Yes (in message) |
| **GenAI Validation** | ❌ No | ✅ Yes (layer 3) |
| **Profiles** | ❌ No | ✅ Yes |
| **Selective Layers** | ❌ No | ✅ Yes |
| **Fail-Fast** | ✅ Yes (implicit) | ✅ Configurable |
| **Dry Run** | ❌ No | ✅ Yes |

---

## Benefits

### Developer Experience

**Before**:
- Choose: commit now or run `/full-check` first
- Full check is slow (includes all tests)
- No GenAI validation
- No automatic issue tracking

**After**:
- Smart default based on changes
- Multiple validation levels (quick/standard/complete)
- GenAI validation option
- Automatic issue tracking
- Clear validation summary

### Quality Assurance

**Before**:
- Binary: validate or don't
- No UX/architecture validation
- Manual issue tracking

**After**:
- Layered validation (appropriate for change)
- UX and architecture validation available
- Automatic issue tracking
- Non-blocking warnings with issues created

### Time Efficiency

**Quick commits** (Layer 1):
- Format + unit tests + security
- < 5s total
- Perfect for rapid iteration

**Standard commits** (Layer 2):
- Format + all tests + security
- < 60s total
- Perfect for feature completion

**Complete validation** (Layer 3):
- Format + all tests + GenAI + security
- 2-5min total
- Perfect for merge/release

---

## Implementation Priority

### High Priority (Implement First)
1. ✅ `--layer=1|2|3` flags
2. ✅ Update `--check` to mean layer 2
3. ✅ Add `--quick` (layer 1) and `--complete` (layer 3) aliases
4. ✅ Validation summary display

### Medium Priority
5. ✅ `--smart` detection based on files changed
6. ✅ `--track-issues` integration
7. ✅ Test summary in commit message footer
8. ✅ `.env` configuration

### Low Priority (Nice to Have)
9. Profiles (`--profile=dev|feature|release`)
10. Selective layers (`--layers=1,3`)
11. `--continue` (don't fail-fast)
12. PROJECT.md file-based rules

---

## Backward Compatibility

**Ensure existing usage still works**:

```bash
/commit                  # Still works (uses default layer)
/commit "message"        # Still works
/commit --check          # Still works (now layer 2, previously all tests)
```

**Migration path**:
- Current `--check` → New `--layer=2` (same behavior)
- Current no flag → New `--layer=1` or `--smart`
- Add new flags without breaking old ones

---

## Example Implementation

### commands/commit.md (Updated)

```markdown
## Usage

### Basic Usage
/commit                       # Smart commit (auto-detect layer)
/commit "message"             # Use custom message

### Validation Layers
/commit --layer=1             # Quick (format + unit + security, < 5s)
/commit --layer=2             # Standard (all tests, < 60s) [DEFAULT]
/commit --layer=3             # Complete (all + GenAI, 2-5min)

### Aliases
/commit --quick               # Same as --layer=1
/commit --check               # Same as --layer=2
/commit --complete            # Same as --layer=3

### Smart Detection
/commit --smart               # Auto-detect based on files changed

### Issue Tracking
/commit --track-issues        # Create GitHub Issues for findings
/commit --layer=3             # Auto-enables issue tracking

### Advanced
/commit --layers=1,3          # Run specific layers
/commit --skip-genai          # Skip GenAI validation
/commit --fail-fast           # Stop on first failure (default)
/commit --continue            # Run all checks, report all
/commit --dry-run             # Show what would run
/commit --force               # Skip validation (emergency only)
```

---

## Summary

**Current `/commit`**:
- Basic: no validation
- `--check`: format + all tests + security

**Proposed `/commit`**:
- Layer 1 (quick): format + unit + security (< 5s)
- Layer 2 (standard): format + all tests + security (< 60s)
- Layer 3 (complete): format + all tests + GenAI + security (2-5min)
- Smart detection based on files
- Automatic issue tracking
- Clear validation summary
- Configurable defaults

**Result**: Flexible, intelligent commit validation that adapts to your needs!

---

**Next Steps**: Would you like me to implement these improvements?
