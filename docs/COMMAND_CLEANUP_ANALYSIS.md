# Command Cleanup Analysis

**Current State**: 33 commands
**Goal**: Remove redundancy, keep only essential commands

---

## REDUNDANT COMMANDS (Retire These - 9 commands)

### 1. Alignment Commands: **RETIRE 3 of 5**

| Command | Purpose | Status | Reason |
|---------|---------|--------|--------|
| `/align-project` | Read-only analysis | **KEEP** | Useful for checking alignment |
| `/align-project-dry-run` | Preview changes (no modifications) | **❌ RETIRE** | Same as `/align-project` (both read-only) |
| `/align-project-safe` | Interactive 3-phase | **KEEP** | User controls changes (recommended) |
| `/align-project-fix` | Auto-fix without approval | **❌ RETIRE** | Risky - use safe instead |
| `/align-project-sync` | Fix + push + issues | **❌ RETIRE** | Too automatic - break into manual steps |

**Result**: Keep 2, retire 3

---

### 2. Documentation Commands: **RETIRE 3 of 5**

| Command | Purpose | Status | Reason |
|---------|---------|--------|--------|
| `/sync-docs` | Complete sync (all docs) | **KEEP** | Most used - sync everything |
| `/sync-docs-auto` | Intelligent auto-detect | **KEEP** | Smart alternative to sync-docs |
| `/sync-docs-api` | API docs only | **❌ RETIRE** | Niche - use /sync-docs |
| `/sync-docs-changelog` | CHANGELOG only | **❌ RETIRE** | Niche - use /sync-docs |
| `/sync-docs-organize` | Move files to docs/ | **❌ RETIRE** | One-time setup - not recurring need |

**Result**: Keep 2, retire 3

---

### 3. Issue Commands: **RETIRE 3 of 6**

| Command | Purpose | Status | Reason |
|---------|---------|--------|--------|
| `/issue` | Auto-create from tests | **❌ RETIRE** | Duplicate of `/issue-auto` |
| `/issue-auto` | Auto-create from tests | **KEEP** | Primary auto-create command |
| `/issue-create` | Manual creation | **❌ RETIRE** | Use `gh issue create` directly |
| `/issue-from-test` | From specific test failure | **❌ RETIRE** | Covered by `/issue-auto` |
| `/issue-from-genai` | From GenAI findings | **KEEP** | Specialized - not covered by auto |
| `/issue-preview` | Dry run (no creation) | **KEEP** | Useful for validation |

**Result**: Keep 3, retire 3

---

## COMMANDS TO KEEP (24 commands)

### Core Workflow (6 commands) ✅
- `/format` - Code formatting
- `/test` - Quick unit tests
- `/test-unit` - Unit tests only
- `/test-integration` - Integration tests
- `/test-uat` - User acceptance tests
- `/full-check` - Complete validation

### Advanced Testing (4 commands) ✅
- `/test-complete` - Pre-release (5-10 min, expensive)
- `/test-uat-genai` - GenAI UX validation (expensive)
- `/test-architecture` - GenAI arch validation (expensive)
- `/security-scan` - Vulnerability scanning

### Commit Workflow (4 commands) ✅
- `/commit` - Quick commit (< 5s)
- `/commit-check` - Full validation (< 60s)
- `/commit-push` - Push with docs sync (2-5 min)
- `/commit-release` - Release with version bump (5-10 min)

**Progressive ladder**: Fast iteration → Standard quality → Push → Release

### Project Management (2 commands) ✅
- `/align-project` - Check alignment (read-only)
- `/align-project-safe` - Fix alignment (interactive)

### Documentation (2 commands) ✅
- `/sync-docs` - Sync everything
- `/sync-docs-auto` - Intelligent auto-detect

### GitHub Issues (3 commands) ✅
- `/issue-auto` - Auto-create from failures
- `/issue-from-genai` - Create from GenAI findings
- `/issue-preview` - Preview without creating

### Setup/Management (2 commands) ✅
- `/setup` - Initial plugin setup
- `/uninstall` - Remove plugin

### Orchestration (1 command) ✅
- `/auto-implement` - Full 8-agent autonomous workflow

---

## SUMMARY

| Category | Before | After | Removed |
|----------|--------|-------|---------|
| Alignment | 5 | 2 | 3 |
| Documentation | 5 | 2 | 3 |
| Issues | 6 | 3 | 3 |
| Testing | 7 | 7 | 0 |
| Commits | 4 | 4 | 0 |
| Other | 6 | 6 | 0 |
| **TOTAL** | **33** | **24** | **9** |

**Reduction**: 27% fewer commands (33 → 24)

---

## COMMANDS TO RETIRE (9 total)

```bash
# Alignment redundancy (3)
rm align-project-dry-run.md     # Same as align-project
rm align-project-fix.md         # Too risky, use safe
rm align-project-sync.md        # Too automatic

# Docs redundancy (3)
rm sync-docs-api.md             # Use sync-docs
rm sync-docs-changelog.md       # Use sync-docs
rm sync-docs-organize.md        # One-time setup

# Issue redundancy (3)
rm issue.md                     # Duplicate of issue-auto
rm issue-create.md              # Use gh CLI directly
rm issue-from-test.md           # Covered by issue-auto
```

---

## RATIONALE FOR KEEPING EACH COMMAND

### Why Keep Test Commands (7)?
- **Progressive granularity**: unit (1s) → integration (10s) → uat (60s)
- **Expensive operations separate**: GenAI tests (2-5 min) opt-in only
- **Different purposes**: fast iteration vs pre-release validation

### Why Keep Commit Commands (4)?
- **Progressive quality ladder**: fast (5s) → standard (60s) → push (5min) → release (10min)
- **User choice**: quick iteration vs thorough validation
- **Clear use cases**: `/commit` daily, `/commit-release` milestones

### Why Keep Only 2 Alignment Commands?
- **Read-only check**: `/align-project` (safe, informational)
- **Interactive fix**: `/align-project-safe` (user controls changes)
- **Remove**: dry-run (duplicate), fix (risky), sync (too automatic)

### Why Keep Only 2 Docs Commands?
- **Complete sync**: `/sync-docs` (do everything)
- **Smart sync**: `/sync-docs-auto` (auto-detect what needs updating)
- **Remove**: api/changelog/organize (niche, rarely needed)

### Why Keep Only 3 Issue Commands?
- **Auto from tests**: `/issue-auto` (most common)
- **From GenAI**: `/issue-from-genai` (specialized findings)
- **Preview mode**: `/issue-preview` (validation before creating)
- **Remove**: issue (duplicate), create (use gh), from-test (covered)

---

## NEXT STEPS

1. ✅ Review this analysis
2. ⚠️ Approve retirement of 9 commands
3. 🔧 Execute cleanup (delete 9 .md files)
4. 📝 Update documentation to reflect new command set
5. ✅ Result: Cleaner, less confusing command structure

**After cleanup**: 24 essential commands, no redundancy
