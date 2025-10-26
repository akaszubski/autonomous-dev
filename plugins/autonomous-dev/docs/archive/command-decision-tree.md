# Autonomous-Dev Command Decision Tree

**Last Updated**: 2025-10-26
**Version**: 3.0.0

A visual guide to help you choose the right autonomous-dev command for your task.

---

## Quick Reference

**Just starting?** → [`/setup`](#setup-workflow)
**Check project health?** → [`/align-project`](#alignment-commands)
**Run tests?** → [Testing Commands](#testing-commands)
**Ready to commit?** → [Commit Commands](#commit-commands)
**Update docs?** → [Documentation Commands](#documentation-commands)

---

## Decision Trees

### Setup Workflow

```
New to autonomous-dev?
└───┐
    │
    ▼
  /setup
    │
    ├─→ Install hooks
    ├─→ Create PROJECT.md (if missing)
    └─→ Configure GitHub (optional)

Done! All commands now available.
```

**When to use**: First time setup, new project onboarding

---

### Alignment Commands

```
Need to check project alignment?
└───┬─────────────────┬──────────┬────────────┐
    │                 │          │            │
  Just         Want to    See what     Trust AI
checking?       fix?      changes?    to fix all?
    │            │            │            │
    ▼            ▼            ▼            ▼
/align-     /align-      /align-      /align-
project     project      project      project

Choose       Choose       Choose     (deprecated)
Option 1     Option 2     Option 3

(view        (fix         (preview
 only)      interactive)   changes)
```

#### Detailed Alignment Flow

```
/align-project
    │
    ├─→ Phase 1: Structural Validation
    │   └─→ Check file organization, directories
    │
    ├─→ Phase 2: Semantic Validation (GenAI)
    │   └─→ Verify docs match implementation
    │
    ├─→ Phase 3: Documentation Currency (GenAI)
    │   └─→ Detect stale markers, old TODOs
    │
    ├─→ Phase 4: Cross-Reference Validation (GenAI)
    │   └─→ Validate file paths, links
    │
    └─→ Phase 5: Action Menu
        │
        ├─→ Option 1: View detailed report only
        │
        ├─→ Option 2: Fix interactively
        │   ├─→ Phase A: Structural fixes
        │   ├─→ Phase B: Documentation fixes
        │   └─→ Phase C: Cross-reference fixes
        │
        ├─→ Option 3: Preview changes (dry run)
        │
        └─→ Option 4: Cancel
```

**When to use**:
- ✅ First time setup (after `/setup`)
- ✅ Weekly health checks
- ✅ After major refactoring
- ✅ Before releases

**Don't use if**: Project already aligned (will show 100%)

---

### Testing Commands

```
Want to run tests?
└───┬────────────────┬──────────┬────────────┐
    │                │          │            │
  Unit tests    Integration  Complete    Just UAT/
  (< 1s)        (< 10s)      validation  UX check
    │                │        (5-10min)      │
    ▼                ▼            ▼           ▼
/test-unit   /test-integration  /test-    /test-uat-genai
                                complete  (GenAI UX)
```

#### Test Command Details

| Command | Speed | What It Does | When to Use |
|---------|-------|--------------|-------------|
| `/test-unit` | < 1s | Run unit tests only | Quick validation during development |
| `/test-integration` | < 10s | Component interactions | After API/service changes |
| `/test` | < 60s | All automated tests | Before commit (standard workflow) |
| `/test-complete` | 5-10min | All tests + GenAI UX + architecture | Before releases |
| `/test-uat-genai` | 2-5min | GenAI UX analysis | User experience validation |

---

### Commit Commands

```
Ready to commit?
└───┬────────────────┬──────────┬────────────┐
    │                │          │            │
  Quick       Standard    Full check    Release
  commit      commit      before push   commit
  (< 5s)      (< 60s)     (2-5min)      (5-10min)
    │            │            │             │
    ▼            ▼            ▼             ▼
/commit    /commit-check  /commit-push  /commit-release

Format +   All tests +    + Doc sync +  + Version bump +
unit tests coverage       PROJECT.md    GitHub Release
```

#### Commit Workflow Details

**`/commit`** - Quick Commit (< 5s)
```
Format code → Unit tests → Security scan → Commit locally
```
✅ Use when: Fast iteration, small changes
❌ Don't use: Before pushing to main

**`/commit-check`** - Standard Commit (< 60s)
```
Format → All tests → Coverage check → Doc validation → Commit
```
✅ Use when: Standard workflow, feature complete
❌ Don't use: In a hurry

**`/commit-push`** - Push Commit (2-5min)
```
All tests → Coverage → Doc sync → PROJECT.md validation → Commit → Push
```
✅ Use when: Ready to push to remote
❌ Don't use: Multiple rapid commits

**`/commit-release`** - Release Commit (5-10min)
```
Complete validation → Version bump → CHANGELOG → GitHub Release
```
✅ Use when: Creating official release
❌ Don't use: Regular development

---

### Documentation Commands

```
Need to update docs?
└───┬────────────────┬──────────┬────────────┐
    │                │          │            │
  Just        Just API    Just         All docs
CHANGELOG      docs    filesystem   at once
    │            │          │            │
    ▼            ▼          ▼            ▼
/sync-docs-  /sync-docs-  /sync-docs-  /sync-docs
changelog     api        organize      (complete)
```

#### Documentation Sync Details

| Command | What It Syncs | When to Use |
|---------|---------------|-------------|
| `/sync-docs-changelog` | CHANGELOG.md from commits | After sprint/milestone |
| `/sync-docs-api` | API docs from docstrings | After API changes |
| `/sync-docs-organize` | Move .md files to docs/ | After creating docs |
| `/sync-docs` | Everything | Before releases |

---

## Choosing Based on Urgency

### High Urgency (need results now)

```
Need quick results? (< 10s)
    │
    ├─→ Test changes?        → /test-unit
    ├─→ Commit changes?      → /commit
    └─→ Check alignment?     → /align-project (Option 1)
```

### Medium Urgency (can wait ~1 min)

```
Can wait a minute? (< 60s)
    │
    ├─→ Test thoroughly?     → /test or /test-integration
    ├─→ Standard commit?     → /commit-check
    └─→ Fix alignment?       → /align-project (Option 2)
```

### Low Urgency (can wait 5-10 min)

```
Can wait longer? (5-10min)
    │
    ├─→ Complete validation? → /test-complete
    ├─→ Release commit?      → /commit-release
    └─→ Full doc sync?       → /sync-docs
```

---

## Common Workflows

### Daily Development Workflow

```
1. Make changes to code
2. /test-unit (quick validation)
3. /commit (quick commit)
4. Repeat

Before end of day:
5. /test (all tests)
6. /commit-push (if tests pass)
```

### Pre-Release Workflow

```
1. /test-complete (comprehensive validation)
2. /align-project → Option 2 (fix issues)
3. /sync-docs (update all documentation)
4. /commit-release (version bump + release)
```

### Weekly Health Check Workflow

```
1. /align-project → Option 1 (view report)
2. Review alignment score
3. If < 90%:
   → /align-project → Option 2 (fix interactively)
4. If >= 90%:
   → Continue development
```

---

## Special Situations

### "I just installed autonomous-dev"

```
/setup
    → Choose workflow (slash commands or auto hooks)
    → Create PROJECT.md (generate from codebase recommended)
    → Setup GitHub (optional)

Done! All commands work now.
```

### "My PROJECT.md is missing"

```
/create-project-md --generate

Or during setup:
/setup → PROJECT.md creation menu
```

### "Documentation is outdated"

```
/align-project
    → Phase 2 will detect outdated docs
    → Phase 3 will find stale markers
    → Option 2 to fix interactively
```

### "Files are in wrong locations"

```
/align-project
    → Phase 1 detects misplaced files
    → Option 2 → Phase A moves files
    → Cross-references auto-updated
```

### "I moved files, docs are broken"

```
Automatic: post-file-move hook runs
    → Detects broken references
    → Offers to auto-fix

Manual:
/align-project → Option 2 → Phase C (fix cross-refs)
```

---

## Command Comparison Matrix

| Task | Fast (< 10s) | Standard (< 60s) | Thorough (5-10min) |
|------|--------------|------------------|-------------------|
| **Testing** | /test-unit | /test | /test-complete |
| **Committing** | /commit | /commit-check | /commit-release |
| **Alignment** | /align-project (Option 1) | /align-project (Option 2) | /align-project (full fix) |
| **Docs** | /sync-docs-changelog | /sync-docs-api | /sync-docs |

---

## Troubleshooting

### "Command not working"

```
Is autonomous-dev installed?
    ├─→ No → /plugin install autonomous-dev
    │        Exit and restart Claude Code
    │
    └─→ Yes → /health-check
              (validates all components)
```

### "PROJECT.md not found"

```
/create-project-md --generate
    OR
/setup → Option 1 (generate from codebase)
```

### "Tests failing"

```
/test-unit → Fast feedback
    │
    ├─→ Unit tests pass → /test-integration
    │   │
    │   └─→ All pass → /commit-check
    │
    └─→ Failures → Fix code → Repeat
```

### "Alignment score low"

```
/align-project → Review report → Option 2

Follow 3-phase interactive fix:
    Phase A: Structural fixes
    Phase B: Documentation fixes
    Phase C: Cross-reference fixes
```

---

## Tips & Best Practices

### DO

✅ Use `/test-unit` frequently (< 1s overhead)
✅ Run `/align-project` weekly
✅ Use `/commit-check` before pushing
✅ Run `/test-complete` before releases
✅ Clear context after each feature (`/clear`)

### DON'T

❌ Skip `/setup` (commands won't work optimally)
❌ Use `/commit-release` for regular commits
❌ Run `/test-complete` on every change (too slow)
❌ Ignore alignment warnings (debt accumulates)
❌ Forget to create PROJECT.md (required for validation)

---

## Quick Command Reference

### Most Used (Daily)
- `/test-unit` - Quick validation
- `/commit` - Fast commit
- `/format` - Format code

### Moderate Use (Weekly)
- `/test` - All tests
- `/commit-check` - Standard commit
- `/align-project` - Health check

### Occasional (Monthly/Release)
- `/test-complete` - Full validation
- `/commit-release` - Release
- `/sync-docs` - Full doc sync

### Setup (Once)
- `/setup` - Initial setup
- `/create-project-md` - Bootstrap PROJECT.md

---

## Getting Help

```
Need help with a command?
    │
    ├─→ Command docs → See .claude/commands/<command>.md
    ├─→ General help → /help
    ├─→ Health check → /health-check
    └─→ Uninstall → /uninstall
```

---

**Remember**: `/align-project` is your friend. Run it weekly to keep your project healthy!
