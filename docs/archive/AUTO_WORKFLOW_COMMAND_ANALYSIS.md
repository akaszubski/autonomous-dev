# Auto-Workflow Command Analysis

**Question**: With `/auto-implement` (8-agent orchestrator), what commands do we still need?

---

## The `/auto-implement` Workflow

```
User: /auto-implement "add user authentication"
  ↓
orchestrator → researcher → planner → test-master → implementer → reviewer → security-auditor → doc-master
  ↓
Complete, production-ready feature (code + tests + docs + security validated)
```

**Result**: User gets everything in one command (~10 agent hours, 20-30 minutes)

---

## Command Categories: Keep or Retire?

### 🎯 **ESSENTIAL** (Keep - 8 commands)

| Command | Why Still Needed | Use Case |
|---------|------------------|----------|
| `/auto-implement` | ✅ PRIMARY WORKFLOW | Full feature implementation |
| `/test` | ✅ Quick validation | Check if tests pass (1s) |
| `/test-complete` | ✅ Pre-release gate | Before merging PR (5-10min) |
| `/commit` | ✅ Fast iteration | Save work quickly (5s) |
| `/commit-check` | ✅ Quality gate | Before pushing (60s) |
| `/format` | ✅ Code cleanup | Fix formatting only |
| `/setup` | ✅ First-time install | Initial plugin setup |
| `/uninstall` | ✅ Plugin management | Remove plugin |

---

### 🤔 **DEBATABLE** (Maybe keep - 11 commands)

#### Testing (5 commands)
| Command | Needed? | Reason |
|---------|---------|--------|
| `/test-unit` | 🟡 Maybe | `/auto-implement` runs tests, but debugging needs granular control |
| `/test-integration` | 🟡 Maybe | Same - debugging specific layer |
| `/test-uat` | 🟡 Maybe | Same - debugging user workflows |
| `/test-architecture` | 🟡 Maybe | Expensive GenAI validation - opt-in for quality checks |
| `/test-uat-genai` | 🟡 Maybe | Expensive UX validation - opt-in |

**Verdict**: Keep for **debugging** when `/auto-implement` tests fail

#### Commits (2 commands)
| Command | Needed? | Reason |
|---------|---------|--------|
| `/commit-push` | 🟡 Maybe | Could just run `/commit-check` then `git push` manually |
| `/commit-release` | 🟡 Maybe | Infrequent - might not need dedicated command |

**Verdict**: Keep `/commit-push` (common), retire `/commit-release` (use `/test-complete` + manual release)

#### Project Management (2 commands)
| Command | Needed? | Reason |
|---------|---------|--------|
| `/align-project` | ✅ Keep | `/auto-implement` checks alignment, but users need manual check |
| `/align-project-safe` | 🟡 Maybe | Could just fix alignment manually |

**Verdict**: Keep `/align-project` (check only), retire `/align-project-safe` (manual fix is fine)

#### Other (2 commands)
| Command | Needed? | Reason |
|---------|---------|--------|
| `/security-scan` | 🟡 Maybe | `/auto-implement` runs security-auditor, but users might want standalone scan |
| `/full-check` | ✅ Keep | Manual equivalent of pre-commit hooks |

**Verdict**: Keep both (useful for manual validation)

---

### ❌ **REDUNDANT** (Retire - 14 commands)

#### Alignment (3 redundant)
- `/align-project-dry-run` → Same as `/align-project`
- `/align-project-fix` → `/auto-implement` handles alignment, or fix manually
- `/align-project-sync` → Too automatic

#### Documentation (5 redundant)
- `/sync-docs` → `/auto-implement` runs doc-master
- `/sync-docs-auto` → `/auto-implement` runs doc-master
- `/sync-docs-api` → Niche
- `/sync-docs-changelog` → Niche
- `/sync-docs-organize` → One-time

**Reasoning**: `/auto-implement` runs doc-master agent (complete docs sync). Users don't need manual doc commands anymore!

#### Issues (3 redundant)
- `/issue` → Duplicate
- `/issue-create` → Use `gh issue create`
- `/issue-from-test` → `/auto-implement` auto-creates from test failures

**Keep**: `/issue-auto`, `/issue-from-genai`, `/issue-preview` for manual issue management

---

## RECOMMENDED COMMAND SET (19 commands)

### Core Workflow (3)
- `/auto-implement` - Full 8-agent pipeline
- `/format` - Quick formatting
- `/full-check` - Manual pre-commit validation

### Testing (6) - For debugging when auto-implement fails
- `/test` - Quick unit tests
- `/test-unit`, `/test-integration`, `/test-uat` - Granular debugging
- `/test-architecture`, `/test-uat-genai` - Expensive validations
- `/test-complete` - Pre-release gate

### Commits (2)
- `/commit` - Fast (5s)
- `/commit-check` - Quality gate (60s)

Retire: `/commit-push` (use `/commit-check` + `git push`), `/commit-release` (use `/test-complete` + manual)

### Project (1)
- `/align-project` - Check alignment only

Retire: `/align-project-safe` (manual fix is fine)

### Issues (3)
- `/issue-auto`, `/issue-from-genai`, `/issue-preview`

### Security (1)
- `/security-scan` - Manual security validation

### Management (2)
- `/setup`, `/uninstall`

### Docs (1)
- ⚠️ Maybe keep `/sync-docs` for manual doc updates when not using `/auto-implement`

---

## AGGRESSIVE CLEANUP (Minimum Viable Set)

**If you ONLY use `/auto-implement`**: You only need **11 commands**:

1. `/auto-implement` - Full pipeline
2. `/test` - Quick validation
3. `/test-complete` - Pre-release
4. `/commit` - Save work
5. `/format` - Fix formatting
6. `/full-check` - Manual hooks
7. `/align-project` - Check alignment
8. `/security-scan` - Manual security
9. `/setup` - Install
10. `/uninstall` - Remove
11. `/issue-preview` - Preview issues before creating

**Retire**: 22 commands (67% reduction!)

---

## MODERATE CLEANUP (Balanced)

**Keep debugging tools**: **19 commands** (recommended)

- Core workflow (3)
- Testing suite (6) - for debugging
- Commits (2) - fast + quality gate
- Project management (1) - alignment check
- Issues (3) - manual management
- Security (1) - manual scan
- Management (2) - setup/uninstall
- Docs (1) - manual updates

**Retire**: 14 commands (42% reduction)

---

## RECOMMENDATION

**With `/auto-implement` as primary workflow**:

### Phase 1: Conservative Cleanup (NOW)
Retire **9 obvious duplicates**:
- 3 alignment variants
- 3 docs variants (keep `/sync-docs` for manual updates)
- 3 issue variants

**Result**: 33 → 24 commands (27% reduction)
**Risk**: LOW (clear duplicates)

### Phase 2: Aggressive Cleanup (LATER - after 1 month of usage)
After validating `/auto-implement` is primary workflow:
- Retire all doc commands (auto-implement handles it)
- Retire commit variants (keep only `/commit`)
- Retire test variants (keep only `/test`, `/test-complete`)

**Result**: 24 → 11 commands (67% total reduction)
**Risk**: MEDIUM (requires workflow validation)

---

## ANSWER TO YOUR QUESTION

**"Do I need all these commands with my auto workflow?"**

**NO. With `/auto-implement`, you need ~50% fewer commands.**

`/auto-implement` includes:
- ✅ Documentation sync (doc-master) → Don't need `/sync-docs*`
- ✅ Testing (test-master) → Don't need granular test commands (except debugging)
- ✅ Security (security-auditor) → Don't need `/security-scan` (except manual)
- ✅ Quality checks (reviewer) → Don't need `/full-check` (except manual)

**Most users will run**: `/auto-implement` → `/test-complete` → `/commit` → done

**Debugging users need**: `/test-unit`, `/test-integration` when tests fail

**Manual validation users need**: `/security-scan`, `/full-check`, `/align-project`

---

**Recommendation**: Start with conservative cleanup (9 commands), then monitor usage and remove more after 1 month.
