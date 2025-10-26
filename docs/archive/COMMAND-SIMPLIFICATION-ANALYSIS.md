# Command Simplification Analysis

**Date**: 2025-10-25
**Status**: Analysis & Recommendations
**User Request**: "can I remove most of the custom /commands or refactor and simplify also"

---

## Executive Summary

**Current State**: 22 commands, 5,013 total lines
**Recommendation**: Keep 15 core commands, consolidate 7 redundant ones
**Reduction**: -30% commands, -40% documentation lines

**Philosophy**: "Simple > Complex" - Keep essential commands that users actually use, consolidate variants.

---

## Command Inventory (Sorted by Size)

| Lines | Command | Purpose | Keep? |
|-------|---------|---------|-------|
| 474 | /issue | Create GitHub Issues | ✅ YES |
| 455 | /setup | Initial plugin setup | ✅ YES |
| 454 | /auto-implement | **Core feature** - autonomous development | ✅ YES |
| 430 | /uninstall | Uninstall plugin | ✅ YES |
| 370 | /align-project | PROJECT.md alignment check | ✅ YES |
| 369 | /pr-create | Create GitHub PR | ✅ YES |
| 349 | /commit-release | Release commit (Level 4) | ⚠️  CONSOLIDATE |
| 318 | /sync-docs | Documentation sync | ✅ YES |
| 239 | /commit-push | Push commit (Level 3) | ⚠️  CONSOLIDATE |
| 206 | /full-check | Full quality check | ✅ YES |
| 192 | /security-scan | Security vulnerability scan | ✅ YES |
| 166 | /test-complete | Complete pre-release validation | ⚠️  CONSOLIDATE |
| 166 | /commit-check | Standard commit (Level 2) | ⚠️  CONSOLIDATE |
| 161 | /test-architecture | Architecture GenAI validation | ⚠️  CONSOLIDATE |
| 149 | /test-uat-genai | UAT GenAI validation | ⚠️  CONSOLIDATE |
| 144 | /commit | Quick commit (Level 1) | ✅ YES |
| 82 | /format | Format code (black, isort, prettier) | ✅ YES |
| 77 | /test-uat | Run UAT tests | ⚠️  CONSOLIDATE |
| 74 | /test-integration | Run integration tests | ⚠️  CONSOLIDATE |
| 73 | /test-unit | Run unit tests | ✅ YES |
| 65 | /test | Run all tests | ✅ YES |

**Total**: 22 commands, 5,013 lines

---

## Consolidation Strategy

### Group 1: Commit Commands (4 → 2)

**Current** (4 commands):
- `/commit` (Level 1) - Quick: format + unit tests + security → commit locally
- `/commit-check` (Level 2) - Standard: all tests + coverage + doc check → commit locally
- `/commit-push` (Level 3) - Push: full integrity + doc sync + PROJECT.md → push to GitHub
- `/commit-release` (Level 4) - Release: complete validation + version bump + GitHub Release

**Problem**: 4 nearly identical commands with increasing rigor

**Recommendation**: Consolidate to 2 commands with flags

**New structure**:
```bash
# Level 1-2: Local commits
/commit [--check]
  # Default: Quick commit (format + unit tests + security)
  # --check: Full commit (all tests + coverage + docs)

# Level 3-4: Push to GitHub
/push [--release]
  # Default: Push commit (integrity + doc sync + PROJECT.md)
  # --release: Release (validation + version bump + GitHub Release)
```

**Benefit**:
- 4 commands → 2 commands
- Clearer: "commit locally" vs "push to GitHub"
- Flags make options explicit
- **-50% commands, -25% documentation**

### Group 2: Test Commands (5 → 3)

**Current** (5 commands):
- `/test-unit` - Unit tests only
- `/test-integration` - Integration tests only
- `/test-uat` - UAT tests (automated)
- `/test-uat-genai` - UAT GenAI validation
- `/test-architecture` - Architecture GenAI validation
- `/test-complete` - Complete pre-release validation
- `/test` - All automated tests (unit + integration + UAT)

**Problem**: Too many test variants

**Recommendation**: Consolidate to 3 commands with scopes

**New structure**:
```bash
# Basic: Fast automated tests
/test [--unit|--integration|--uat]
  # Default: All automated tests (unit + integration + UAT)
  # --unit: Unit tests only
  # --integration: Integration tests only
  # --uat: UAT tests only

# GenAI: Advanced validation
/test-genai [--uat|--architecture]
  # Default: Both UX and architecture validation
  # --uat: UX validation only
  # --architecture: Architecture validation only

# Complete: Pre-release validation
/test-complete
  # All tests + GenAI UX + architecture (5-10 min)
```

**Benefit**:
- 7 commands → 3 commands
- Clearer hierarchy: automated → GenAI → complete
- **-57% commands, -35% documentation**

### Group 3: Keep As-Is (11 commands)

**These serve distinct purposes**:

1. `/auto-implement` - **THE core feature** - autonomous development pipeline
2. `/align-project` - PROJECT.md strategic alignment check
3. `/setup` - Initial plugin configuration
4. `/uninstall` - Plugin removal
5. `/format` - Code formatting (black, prettier, etc.)
6. `/full-check` - Complete quality gate (manual equivalent of hooks)
7. `/security-scan` - Security vulnerability scanning
8. `/sync-docs` - Documentation synchronization
9. `/pr-create` - GitHub pull request creation
10. `/issue` - GitHub issue management
11. `/test-unit` - Fast unit test (most common)

**Why keep**:
- Each serves a unique, frequently-used purpose
- Not overlapping functionality
- Users expect these as standalone commands

---

## Final Command List (After Consolidation)

### Core Workflow (5 commands)
1. `/auto-implement` - Autonomous feature development
2. `/align-project` - Verify PROJECT.md alignment
3. `/commit [--check]` - Commit locally (quick or thorough)
4. `/push [--release]` - Push to GitHub (standard or release)
5. `/test [--unit|--integration|--uat]` - Run tests (scoped or all)

### Quality & Validation (3 commands)
6. `/test-genai [--uat|--architecture]` - GenAI validation
7. `/test-complete` - Pre-release validation (all tests + GenAI)
8. `/full-check` - Manual quality gate (format + test + security)

### Code Maintenance (3 commands)
9. `/format` - Auto-format code
10. `/security-scan` - Vulnerability scanning
11. `/sync-docs` - Documentation synchronization

### GitHub Integration (2 commands)
12. `/pr-create` - Create pull request
13. `/issue` - Manage GitHub issues

### Setup & Management (2 commands)
14. `/setup` - Initial plugin configuration
15. `/uninstall` - Plugin removal

**Total**: 15 commands (vs 22 before)
**Reduction**: -32% commands, -40% documentation lines

---

## Detailed Consolidation Plans

### /commit Consolidation

**Before** (4 commands, 898 lines):
- commit.md (144 lines)
- commit-check.md (166 lines)
- commit-push.md (239 lines)
- commit-release.md (349 lines)

**After** (2 commands, ~400 lines):

#### /commit [--check]
```markdown
---
name: commit
description: Commit changes locally with validation
---

# Commit Changes

Commit changes to git with automatic validation.

## Usage

```bash
# Quick commit (format + unit tests + security → commit)
/commit

# Thorough commit (all tests + coverage + docs → commit)
/commit --check
```

## Quick Mode (Default)
**Speed**: < 5 seconds
**Validates**:
- Code formatted (black, isort, prettier)
- Unit tests pass
- No secrets detected

## Check Mode (--check)
**Speed**: < 60 seconds
**Validates**:
- All automated tests pass (unit + integration + UAT)
- Coverage ≥ 80%
- Documentation synchronized
- No security vulnerabilities

## Process
1. Run appropriate validation level
2. If all pass: Create commit
3. If any fail: Show errors and abort

## Examples
```bash
# Quick: Fast commit for minor changes
/commit

# Thorough: Full validation before major commit
/commit --check
```

## Output
```
✅ Format: black, isort (0.5s)
✅ Unit tests: 47 passed (1.2s)
✅ Security scan: No secrets (0.3s)

📝 Commit created: abc123f
```
```
**~200 lines** (vs 310 lines for commit.md + commit-check.md)

#### /push [--release]
```markdown
---
name: push
description: Push commits to GitHub with validation
---

# Push to GitHub

Push commits to remote GitHub repository with integrity checks.

## Usage

```bash
# Standard push (integrity + doc sync + PROJECT.md → push to remote)
/push

# Release push (full validation + version bump + GitHub Release)
/push --release
```

## Standard Mode (Default)
**Speed**: 2-5 minutes
**Validates**:
- Full commit integrity (all tests pass)
- Documentation synchronized
- PROJECT.md alignment validated
- No security vulnerabilities

**Actions**:
- Runs full-check validation
- Creates commit if needed
- Pushes to origin

## Release Mode (--release)
**Speed**: 5-10 minutes
**Validates**:
- Complete pre-release validation
- GenAI UX validation
- GenAI architecture validation
- Version consistency

**Actions**:
- Runs test-complete validation
- Bumps version (MAJOR.MINOR.PATCH)
- Updates CHANGELOG.md
- Creates git tag
- Pushes to origin
- Creates GitHub Release

## Process
1. Run validation level
2. If validation passes: Create commit (if needed)
3. Push to remote
4. If --release: Create GitHub Release

## Examples
```bash
# Standard: Push feature to remote
/push

# Release: Create new version release
/push --release
```

## Output (Standard)
```
🔍 Full integrity check...
✅ Tests: 47 passed
✅ Coverage: 94%
✅ Docs: Synchronized
✅ PROJECT.md: Aligned

📤 Pushing to origin/main...
✅ Pushed: 3 commits

View on GitHub: https://github.com/user/repo/commit/abc123f
```

## Output (Release)
```
🚀 Release validation...
✅ Tests: All passed
✅ GenAI UX: 95/100 (excellent)
✅ GenAI Architecture: 92/100 (aligned)

📦 Version bump: v2.4.0 → v2.5.0
📝 CHANGELOG updated

📤 Pushing release...
✅ Pushed: v2.5.0

🎉 GitHub Release created:
https://github.com/user/repo/releases/tag/v2.5.0
```
```
**~200 lines** (vs 588 lines for commit-push.md + commit-release.md)

**Total consolidation savings**: 898 → 400 lines (-55%)

### /test Consolidation

**Before** (7 commands, 766 lines):
- test.md (65 lines)
- test-unit.md (73 lines)
- test-integration.md (74 lines)
- test-uat.md (77 lines)
- test-uat-genai.md (149 lines)
- test-architecture.md (161 lines)
- test-complete.md (166 lines)

**After** (3 commands, ~400 lines):

#### /test [--unit|--integration|--uat]
```markdown
---
name: test
description: Run automated tests with optional scoping
---

# Run Tests

Run automated test suites.

## Usage

```bash
# Run all automated tests (unit + integration + UAT)
/test

# Run specific test scope
/test --unit          # Unit tests only (< 1s)
/test --integration   # Integration tests only (< 10s)
/test --uat           # UAT tests only (< 60s)
```

## Test Scopes

### Unit Tests (--unit)
**Speed**: < 1 second
**Purpose**: Fast validation of individual functions
**Coverage**: Function-level correctness

### Integration Tests (--integration)
**Speed**: < 10 seconds
**Purpose**: Validate components work together
**Coverage**: Module interaction, API contracts

### UAT Tests (--uat)
**Speed**: < 60 seconds
**Purpose**: Complete user workflow validation
**Coverage**: End-to-end scenarios, automated

### All Tests (default)
**Speed**: < 60 seconds total
**Purpose**: Full automated test suite
**Coverage**: All of the above

## Examples

```bash
# Quick: Unit tests during development
/test --unit

# Thorough: All tests before commit
/test
```

## Output

```
🧪 Running all automated tests...

Unit Tests (1.2s):
  ✅ 47 passed

Integration Tests (8.3s):
  ✅ 12 passed

UAT Tests (42.1s):
  ✅ 5 workflows passed

📊 Total: 64 tests passed in 51.6s
📈 Coverage: 94% (target: 80%)
```
```
**~120 lines** (vs 289 lines for test.md + test-unit.md + test-integration.md + test-uat.md)

#### /test-genai [--uat|--architecture]
```markdown
---
name: test-genai
description: GenAI validation (UX and architecture)
---

# GenAI Validation

Use Claude AI for advanced validation.

## Usage

```bash
# Run both UX and architecture validation
/test-genai

# Run specific GenAI validation
/test-genai --uat           # UX validation only
/test-genai --architecture  # Architecture validation only
```

## Validation Types

### UX Validation (--uat)
**Speed**: 2-5 minutes
**Uses**: Claude Sonnet 4
**Analyzes**:
- User experience quality
- Goal alignment with PROJECT.md
- Workflow completeness
- Error handling UX

**Output**: UX score (0-100), findings, recommendations

### Architecture Validation (--architecture)
**Speed**: 2-5 minutes
**Uses**: Claude Opus 4
**Analyzes**:
- Code matches architecture
- Design pattern consistency
- No architectural drift
- Complexity assessment

**Output**: Architecture score (0-100), drift detection, suggestions

## Examples

```bash
# UX only: After implementing user-facing feature
/test-genai --uat

# Architecture only: After structural refactoring
/test-genai --architecture

# Both: Before major release
/test-genai
```

## Output

```
🤖 GenAI UX Validation (Claude Sonnet 4)...
✅ UX Score: 95/100

Findings:
- Excellent error messages (clear, actionable)
- Workflow is intuitive
- Documentation complete

Recommendations:
- Consider adding progress indicators for long operations

🤖 GenAI Architecture Validation (Claude Opus 4)...
✅ Architecture Score: 92/100

Findings:
- Code aligns with planned architecture
- Design patterns consistent
- No architectural drift detected

Recommendations:
- Consider extracting common validation logic
```
```
**~150 lines** (vs 310 lines for test-uat-genai.md + test-architecture.md)

#### /test-complete (Keep as-is, simplify)
```markdown
---
name: test-complete
description: Complete pre-release validation
---

# Complete Pre-Release Validation

Run comprehensive validation before release.

## Usage

```bash
/test-complete
```

## What It Runs

**Speed**: 5-10 minutes total

1. **All Automated Tests** (< 60s)
   - Unit + integration + UAT tests
   - Must all pass

2. **GenAI UX Validation** (2-5 min)
   - User experience analysis
   - Goal alignment check

3. **GenAI Architecture Validation** (2-5 min)
   - Architectural drift detection
   - Design pattern consistency

## Use Cases

- Before creating a release
- Before major merge to main
- Weekly quality check

## Example

```bash
# Run before release
/test-complete
```

## Output

```
📋 Complete Pre-Release Validation...

1/3 Automated Tests...
    ✅ 64 tests passed (51.6s)

2/3 GenAI UX Validation...
    ✅ Score: 95/100 (2.3 min)

3/3 GenAI Architecture Validation...
    ✅ Score: 92/100 (3.1 min)

✅ VALIDATION PASSED

Ready for release!
Total time: 6.4 minutes
```
```
**~130 lines** (vs 166 lines for test-complete.md)

**Total consolidation savings**: 766 → 400 lines (-48%)

---

## Implementation Plan

### Phase 1: Consolidate /commit Commands
1. Create new `/commit` with `--check` flag
2. Create new `/push` with `--release` flag
3. Archive old commands (commit-check.md, commit-push.md, commit-release.md → archive/)
4. Update documentation
**Time**: 1 hour

### Phase 2: Consolidate /test Commands
1. Update `/test` with scope flags
2. Create `/test-genai` with type flags
3. Simplify `/test-complete`
4. Archive old commands (test-unit.md, test-integration.md, etc. → archive/)
5. Update documentation
**Time**: 1.5 hours

### Phase 3: Documentation & Validation
1. Update README.md command list
2. Update docs/COMMAND-REFERENCE.md (if exists)
3. Test all new consolidated commands
4. Verify backward compatibility (optional aliases)
**Time**: 0.5 hours

**Total implementation**: ~3 hours

---

## Backward Compatibility

### Option 1: Hard Cutover (Recommended)
- Remove old commands entirely
- Update documentation
- Users adapt to new consolidated commands
- **Benefit**: Clean, simple, no maintenance burden
- **Risk**: Minor disruption

### Option 2: Deprecation Period
- Keep old commands with deprecation warnings
- Add to each old command:
  ```
  ⚠️  DEPRECATED: Use /commit --check instead
  This command will be removed in v2.5.0
  ```
- Remove in next major version
- **Benefit**: Smooth transition
- **Cost**: Maintain duplicate commands for 1-2 releases

**Recommendation**: Option 1 (hard cutover) since this is a personal project and consolidation makes commands better, not worse.

---

## User Impact

### Before (22 commands)
User sees overwhelming list:
```
/commit
/commit-check
/commit-push
/commit-release
/test
/test-unit
/test-integration
/test-uat
/test-uat-genai
/test-architecture
/test-complete
... (11 more)
```
**Confusion**: "Which commit command do I use?"

### After (15 commands)
User sees clear categories:
```
Core Workflow:
  /auto-implement
  /align-project
  /commit [--check]
  /push [--release]
  /test [--unit|--integration|--uat]

Quality:
  /test-genai [--uat|--architecture]
  /test-complete
  /full-check

Maintenance:
  /format
  /security-scan
  /sync-docs

GitHub:
  /pr-create
  /issue

Setup:
  /setup
  /uninstall
```
**Clarity**: Obvious which command to use, flags show options

---

## Benefits

### Code Reduction
- **Commands**: 22 → 15 (-32%)
- **Documentation lines**: 5,013 → 3,000 (-40%)
- **Cognitive load**: Much simpler

### Better UX
- **Clearer purpose**: Each command has distinct role
- **Flags show options**: `/commit --check` vs 4 separate commands
- **Less overwhelming**: 15 commands vs 22

### Easier Maintenance
- **Fewer files**: Less to maintain
- **Consolidated logic**: Shared validation code
- **Consistent patterns**: All commands follow same structure

---

## Recommendation

**YES - Simplify and consolidate commands**

**Action Plan**:
1. Implement Phase 1 (commit consolidation) - 1 hour
2. Implement Phase 2 (test consolidation) - 1.5 hours
3. Update documentation - 0.5 hours
4. Test thoroughly - 1 hour

**Total**: ~4 hours work, -40% complexity

**Result**: 15 clean, intuitive commands vs 22 overlapping ones

---

## Next: Hook Simplification

After command consolidation, we should review hooks for similar opportunities.

See: `docs/HOOK-SIMPLIFICATION-ANALYSIS.md` (to be created)
