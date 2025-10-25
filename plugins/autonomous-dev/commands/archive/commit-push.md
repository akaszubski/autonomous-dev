---
description: Push commit - full integrity + doc sync + PROJECT.md validation → push to GitHub (2-5min)
---

# Push Commit (Level 3) - Full Integrity

**Complete validation with documentation sync and push to GitHub**

---

## Usage

```bash
/commit-push
```

**Time**: 2-5 minutes
**Validates**: All tests, coverage, docs, PROJECT.md alignment, architecture
**Pushes**: Yes - commits and pushes to GitHub

---

## What This Does

1. All from Level 2 (format, all tests, coverage, security)
2. Check for dependency updates
3. **Rebuild README.md** from PROJECT.md + docs
4. **Sync documentation** cross-references
5. **Update CHANGELOG.md** from commits
6. **Validate PROJECT.md alignment** (GenAI validation)
7. **Create GitHub Issues** for findings (optional)
8. **Commit + Push to GitHub**

---

## Expected Output

```
Running Level 3: Push Commit (Full Integrity)...

┌─ Full Integrity Workflow ───────────────────────────────────┐
│                                                              │
│ Phase 1: Code Quality ✅                                     │
│  ✅ Format: PASSED                                           │
│  ✅ All Tests: PASSED (65/65, 20.3s)                         │
│  ✅ Coverage: 92%                                            │
│  ✅ Security: PASSED                                         │
│                                                              │
│ Phase 2: Documentation Sync 🔄                               │
│  🔄 Checking dependencies...                                 │
│     ✅ All dependencies up to date                           │
│  🔄 Rebuilding README.md from PROJECT.md...                  │
│     ✅ README.md updated (sections: 3, features: 12)         │
│  🔄 Syncing documentation cross-references...                │
│     ✅ All cross-references valid (48 links checked)         │
│  🔄 Updating CHANGELOG.md...                                 │
│     ✅ Added entry: v1.1.1 - 2025-10-20                      │
│                                                              │
│ Phase 3: Architectural Validation (GenAI) 🤖                 │
│  🔄 Validating PROJECT.md alignment...                       │
│     ✅ All goals aligned                                     │
│     ✅ Within scope                                          │
│     ✅ Constraints respected                                 │
│  🔄 Validating architecture...                               │
│     ✅ 100% aligned with documented intent                   │
│     ⚠️  1 optimization opportunity found                     │
│                                                              │
│ Phase 4: Issue Tracking 📋                                   │
│  ✅ Created issue #42: "Use Haiku for simple tasks"          │
│                                                              │
│ Total time: 3m 42s                                           │
│ Status: PASSED ✅ (1 optimization tracked)                   │
│                                                              │
└──────────────────────────────────────────────────────────────┘

Files modified during integrity checks:
  M README.md (auto-generated from PROJECT.md)
  M CHANGELOG.md (added v1.1.1 entry)

Staging updated files...

✅ Committed and pushed to GitHub (ghi9012)
```

---

## When to Use

- ✅ Before merge to main/master
- ✅ Sharing complete feature with team
- ✅ End of development session
- ✅ Before production deployment

---

## Related Commands

- `/commit` - Level 1: Quick commit (5s)
- `/commit-check` - Level 2: Full tests without push (60s)
- `/commit-release` - Level 4: Release with version bump (7min)

---

## Implementation

**Use the Task tool with orchestrator agent** for this complex multi-phase workflow:

```markdown
I need to run a Level 3 Push Commit with full integrity validation.

Please orchestrator agent:

1. **Phase 1: Code Quality**
   - Run /format
   - Run /test (all tests)
   - Check coverage (80%+ required)
   - Run /security-scan

2. **Phase 2: Documentation Sync**
   - Check dependencies: pip list --outdated (Python) or npm outdated (JS)
   - Rebuild README.md from PROJECT.md (extract sections, features, commands)
   - Check documentation cross-references (grep for broken links)
   - Update CHANGELOG.md from git log since last release

3. **Phase 3: Architectural Validation**
   - Validate PROJECT.md alignment (read PROJECT.md, compare with changes)
   - Check that changes align with GOALS, are IN SCOPE, respect CONSTRAINTS
   - Identify any architectural drift or optimization opportunities

4. **Phase 4: Issue Tracking**
   - Create GitHub issues for any findings (if gh CLI available)
   - Tag with "automated" label

5. **Commit and Push**
   - Stage all files (including auto-generated README, CHANGELOG)
   - Create commit with validation summary
   - Push to GitHub

Please return a detailed summary of:
- All checks performed
- Files modified
- Issues created
- Commit hash
- Push status
```

---

## Phase Details

### Phase 1: Code Quality
- Same as Level 2 (format, tests, coverage, security)

### Phase 2: Documentation Sync
**Dependency check**:
```bash
pip list --outdated  # Python
npm outdated         # JavaScript
```

**README rebuild**:
- Extract sections from PROJECT.md
- List features, commands, skills, agents
- Update installation instructions
- Validate all links

**CHANGELOG update**:
```bash
# Get commits since last release
git log $(git describe --tags --abbrev=0)..HEAD --oneline

# Parse conventional commits
# - feat: → Added section
# - fix: → Fixed section
# - docs: → Documentation section

# Append to CHANGELOG.md
```

### Phase 3: Architectural Validation (GenAI)
**PROJECT.md alignment**:
- Read GOALS, SCOPE, CONSTRAINTS from PROJECT.md
- Compare changes against strategic direction
- Flag any misalignment

**Architecture validation**:
- Check 14 architectural principles
- Verify agent pipeline order
- Validate model optimization
- Detect architectural drift

### Phase 4: Issue Tracking
**Create GitHub issues** (if enabled):
```bash
gh issue create \
  --title "Optimization: Use Haiku for simple tasks" \
  --body "Found during Level 3 commit integrity check..." \
  --label "automated,optimization"
```

---

## Configuration (.env)

```bash
# Push commit settings
COMMIT_README_REBUILD=true      # Auto-rebuild README
COMMIT_CHANGELOG_UPDATE=true    # Auto-update CHANGELOG
GITHUB_AUTO_ISSUE=true          # Create issues for findings
GITHUB_ISSUE_LABEL=automated    # Label for auto-created issues
```

---

## Error Handling

**If any phase fails**:
```
❌ Level 3 Push Commit FAILED

Phase 1: Code Quality ✅ PASSED
Phase 2: Documentation Sync ❌ FAILED
  - README.md rebuild failed (broken link: docs/missing.md)
Phase 3: Architectural Validation ⏭️  SKIPPED
Phase 4: Issue Tracking ⏭️  SKIPPED

Fix documentation issues and retry.

💡 Tip: Run '/commit-check' to commit without push
```

**Progressive fallback**:
- Offer to commit at Level 2 (without push)
- Offer to commit at Level 1 (quick commit)
- Block commit if Level 1 checks fail

---

**Use this before merge or deployment. Ensures complete quality and pushes to GitHub.**
