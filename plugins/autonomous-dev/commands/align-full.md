---
description: Deep GenAI alignment analysis - find ALL inconsistencies and build synced GitHub issues + todos
---

# /align-full - Interactive Conflict Resolution

**GenAI-powered deep scan** - Finds every inconsistency between PROJECT.md (vision), code (reality), and docs (claims).

Then asks **you** which source of truth should win, and creates actionable GitHub issues + todos based on your decision.

---

## Usage

```bash
/align-full
```

**Time**: 5-15 minutes (depending on project size)
**Output**: Inconsistencies found, GitHub issues created, synced todos

---

## What This Does

### Phase 1: Read SOURCE OF TRUTH (2 min)

Reads and analyzes `.claude/PROJECT.md`:
- Vision (what/why)
- Goals with features
- Scope (exclusions)
- Constraints (LOC, dependencies, etc.)
- Architecture patterns
- Success criteria

**This becomes the benchmark** - everything else is compared against this.

---

### Phase 2: Analyze CODEBASE REALITY (3 min)

Scans all implementation:
- All source files (`src/`, `lib/`)
- Counts LOC (compare vs budget)
- Counts dependencies (compare vs limit)
- Detects architecture patterns used
- Finds features implemented

**Detects**: Features not in PROJECT.md (scope drift)

---

### Phase 3: Analyze DOCUMENTATION CLAIMS (2 min)

Scans all documentation:
- All `.md` files
- README, CHANGELOG, architecture docs
- Checks for PROJECT.md references
- Validates cross-references

**Detects**: Docs claiming features that don't exist

---

### Phase 4: Find INCONSISTENCIES (5-10 min GenAI)

**GenAI deep analysis** comparing all three sources:

1. **Docs vs Code**: Docs claim X, code does Y
2. **Code vs PROJECT.md**: Feature exists but not in goals (drift)
3. **Missing References**: Code doesn't link to PROJECT.md
4. **Constraint Violations**: Exceeds LOC/dependency budgets
5. **Broken Links**: Cross-references to missing files
6. **Outdated Claims**: Version mismatches, stale info

**Each inconsistency gets**:
- Type classification
- Severity (CRITICAL/HIGH/MEDIUM/LOW)
- Impact assessment
- Multiple resolution options

---

### Phase 5: Interactive Conflict Resolution (3-5 min)

For **each inconsistency**, presents all three perspectives and asks user which source of truth wins:

```markdown
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
CONFLICT #1: Notifications Implementation
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Three sources disagree:

1️⃣  PROJECT.md SAYS (Strategic Intent):
   Goal 2: "Real-time user notifications"
   Success Criteria: "Instant delivery (< 100ms latency)"
   Constraint: "No expensive infrastructure"

2️⃣  CODE SHOWS (Reality):
   src/services/NotificationService.ts:12
   • Uses polling (30 second intervals)
   • Zero latency guarantee
   • No infrastructure requirements

3️⃣  DOCS CLAIM (Communication):
   README.md:45 - "Real-time notifications via WebSocket"

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

THE CONFLICT:
❌ PROJECT.md promises "real-time" (instant)
❌ Code delivers "polling" (30-second delay)
❌ Docs claim "WebSocket" (which isn't implemented)

All three disagree. Which source should WIN?

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

RESOLUTION OPTIONS:

A) PROJECT.md wins (Adjust code to match promise)
   Action: Implement WebSocket for true real-time notifications
   Files to change: src/services/NotificationService.ts
   Effort: Medium (add WebSocket infrastructure)
   Why: Users expect real-time (per PROJECT.md promise)

B) CODE wins (Adjust PROJECT.md + docs to match reality)
   Action: Update PROJECT.md Goal 2 to say "polling-based (30s)"
           Update README.md to remove WebSocket mention
   Files to change: .claude/PROJECT.md, README.md
   Effort: Low (documentation updates only)
   Why: Polling meets constraints + works (pragmatic choice)

C) COMPROMISE (Update code + docs, redefine goal)
   Action: Keep polling BUT implement client-side notification queue
           Update PROJECT.md to "near-real-time with queued delivery"
           Update docs to explain polling + queuing approach
   Files to change: src/services/NotificationService.ts, .claude/PROJECT.md, README.md
   Effort: Medium (add queue + update docs)
   Why: Balances promise vs constraints (best UX within limits)

Which approach? [A/B/C]:
```

**You choose**: `B` ↵

```
✅ YOU CHOSE: CODE wins

This means:
1. PROJECT.md Goal 2 will be updated (polling, not real-time)
2. README.md will be corrected (polling, not WebSocket)
3. Code stays as-is (polling implementation is correct)

Creating GitHub issues for the fixes:
  ✅ Issue #23: Update PROJECT.md Goal 2 to describe polling approach
  ✅ Issue #24: Update README.md to remove WebSocket claim

Adding to .todos.md:
  Priority: HIGH (user-facing documentation mismatch)

Next step: Fix these issues, then re-run /align-full to verify alignment

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
CONFLICT #2: Authentication System Scope...
```

**System records decision** and moves to next conflict.

---

### Phase 6: Create GITHUB ISSUES (1 min)

For each inconsistency, auto-creates GitHub issue:

```bash
Created Issue #23:
  Title: "Fix docs: Notifications use polling, not WebSocket"
  Labels: documentation, inconsistency, alignment
  Body: [Full details with file references]

Created Issue #24:
  Title: "Add PROJECT.md references to TaskController"
  Labels: documentation, traceability
  Body: [Specific changes needed]
```

**All issues tagged** with `alignment` label for easy filtering.

---

### Phase 7: Build SYNCED TODOS (1 min)

Creates `.todos.md` synced with GitHub issues:

```markdown
# Alignment Todos

Synced with GitHub Issues - Updated: 2025-10-26

## Critical (1)

- [ ] Remove AI feature (enforce scope) - Issue #25
  Files: src/services/AIService.ts
  Reason: Violates PROJECT.md scope exclusions

## High Priority (3)

- [ ] Update docs: polling not WebSocket - Issue #23
  Files: README.md:45
  Fix: Replace "WebSocket" with "polling (30s)"

- [ ] Add PROJECT.md references - Issue #24
  File: src/controllers/TaskController.ts
  Add: // Serves: PROJECT.md Goal 1

## Medium (2)

- [ ] Update version in README - Issue #26
  Change: 2.0.0 → 3.1.0

## Low (1)

- [ ] Fix broken link - Issue #27
  Create: docs/installation.md
```

**Committed to git** so todos are version controlled.

---

## Example Session

```bash
/align-full
```

**Output you see**:

```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
🔍 FULL ALIGNMENT ANALYSIS
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Invoking alignment-analyzer agent...

Phase 1: Reading PROJECT.md (source of truth)
✅ Vision extracted
✅ 3 goals documented
✅ 5 constraints documented
✅ Architecture pattern: REST API

Phase 2: Analyzing codebase (45 files, 1,847 LOC)
✅ LOC: 1,847 / 5,000 budget (37% used) ✅
✅ Dependencies: 12 / 20 max (60% used) ✅
✅ Architecture: REST API ✅ Matches PROJECT.md

⚠️  Found feature not in PROJECT.md:
    - AI suggestions (src/services/AIService.ts)

Phase 3: Analyzing documentation (82 files)
✅ Scanned all .md files
✅ Checked cross-references (3 broken links found)

⚠️  Low traceability: 10% of docs reference PROJECT.md

Phase 4: Finding inconsistencies (GenAI deep analysis)
🔍 Comparing PROJECT.md vs code vs docs...

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
📋 FOUND 8 INCONSISTENCIES
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

CRITICAL: 1
HIGH: 3
MEDIUM: 3
LOW: 1

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
INCONSISTENCY #1: Documentation Mismatch
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Severity: HIGH

Documentation says:
  README.md:45 - "Real-time notifications via WebSocket"

Code reality:
  src/services/NotificationService.ts:12
  Uses polling (30s interval), no WebSocket detected

Impact: Users expect real-time, get polling

Options:
A) Update docs to match code (polling)
B) Update code to match docs (implement WebSocket)
C) Explain in docs why polling was chosen

What should we do? [A/B/C]:
```

**You type**: `A` ↵

```
✅ Noted: Update docs to match polling implementation

Creating GitHub Issue #23...
✅ Created: "Fix docs: Notifications use polling, not WebSocket"

Adding to todos...
✅ Added to .todos.md (HIGH priority)

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
INCONSISTENCY #2: Scope Drift Detected
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Severity: CRITICAL

PROJECT.md says:
  Scope exclusions: "No AI features" (PROJECT.md:78)

Code reality:
  src/services/AIService.ts - AI-powered suggestions
  Dependencies: openai (v4.2.0)

Impact: Major scope violation

Options:
A) Remove AI feature (enforce scope)
B) Update PROJECT.md to allow AI (intentional scope change)
C) Mark as experimental (temporary exception)

What should we do? [A/B/C]:
```

**You type**: `B` ↵

```
✅ Noted: Update PROJECT.md to allow AI features

⚠️  SCOPE CHANGE DETECTED
This is a major decision. Documenting rationale is critical.

Creating GitHub Issue #25...
✅ Created: "SCOPE CHANGE: Allow AI features in PROJECT.md"
Labels: scope-change, breaking, PROJECT.md

Adding to todos...
✅ Added to .todos.md (CRITICAL priority)

... [Continues for all 8 inconsistencies]

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
📊 ANALYSIS COMPLETE
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Inconsistencies: 8 found
GitHub Issues: 8 created (#23-#30)
Todos: 8 added to .todos.md

Overall Alignment: 78% (before fixes)
Projected: 95% (after fixing all 8)

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
📋 NEXT STEPS
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

1. Review GitHub issues:
   gh issue list --label alignment

2. Review todos:
   cat .todos.md

3. Start fixing (highest priority first):
   - Fix Issue #25 (CRITICAL): Update PROJECT.md scope
   - Fix Issue #23 (HIGH): Update notification docs
   - Fix Issue #24 (HIGH): Add PROJECT.md references

4. Track progress:
   - Mark todos [x] as you complete them
   - Close GitHub issues: gh issue close #23

5. Re-run alignment after fixes:
   /align-full
   (Should show 95%+ alignment)

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
💡 PRO TIP
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Run /align-full weekly to catch drift early.

Small misalignments are easy to fix.
Large misalignments require rewrites.

Weekly runs keep alignment > 90%.
```

---

## When to Run /align-full

### Weekly Health Check (Recommended)

```bash
# Every Monday morning
/align-full

# Quick scan if project stable
# Deep analysis if lots of changes
```

**Catches drift early** - easier to fix 3 small issues than 20 large ones.

---

### Before Releases

```bash
# Before v3.2.0 release
/align-full

# Fix all CRITICAL and HIGH issues
# Document MEDIUM issues for next release
# Defer LOW issues
```

**Ensures release aligns** with documented vision.

---

### After Major Changes

```bash
# Just rewrote authentication system
/align-full

# Verify:
# - Architecture still aligns
# - Docs updated
# - PROJECT.md reflects changes
```

**Prevents accidental drift** during refactors.

---

### When Things Feel Off

```bash
# Project feels misaligned but can't pinpoint why
/align-full

# GenAI finds what humans miss
# Objective analysis, no assumptions
```

**Trust your instincts** - run analysis.

---

## What Gets Checked & How Conflicts Are Resolved

### 🔍 Detection: Finds Inconsistencies

Scans all three sources and detects conflicts:

1. **PROJECT.md vs Code**: Goal promises X, code does Y
2. **PROJECT.md vs Docs**: Goal says X, docs claim Y
3. **Code vs Docs**: Implementation is X, documentation says Y
4. **Features vs Goals**: Code has feature not in PROJECT.md (scope drift)
5. **Constraints**: LOC/dependency budgets exceeded
6. **Traceability**: Code doesn't link to which goal it serves

### 🤔 Resolution: Asks You Which Source Wins

For each conflict, presents three perspectives:

```
PROJECT.md (VISION)      CODE (REALITY)      DOCS (CLAIMS)
    ↓                        ↓                    ↓
 "X feature"           "Actually does Y"    "Claims it's Z"

                   CONFLICT!
            Which source should WIN?

A) PROJECT.md wins → Update code (implement vision)
B) CODE wins → Update PROJECT.md + docs (accept reality)
C) COMPROMISE → Update all three (balanced approach)
```

### 📋 Action: Creates Issues Based on Your Decision

**If you choose A (PROJECT.md wins)**:
- Creates issue: "Implement WebSocket notifications"
- Todo: Code needs feature work
- Docs and PROJECT.md stay as-is

**If you choose B (CODE wins)**:
- Creates issues: "Update PROJECT.md Goal 2" + "Fix README documentation"
- Todos: Documentation updates only
- Code stays as-is (already correct)

**If you choose C (COMPROMISE)**:
- Creates issues: "Add queuing to notifications" + "Update PROJECT.md" + "Update docs"
- Todos: Both code and documentation updates
- Balances promise vs constraints

---

## GitHub Issue Integration

### Auto-Created Issues

Every inconsistency gets a GitHub issue:

```yaml
Title: "Fix docs: Notifications use polling, not WebSocket"
Labels: [documentation, inconsistency, alignment]
Assignee: (you)
Body: |
  Inconsistency #1 from /align-full analysis

  **Type**: docs_vs_code
  **Severity**: HIGH

  **Documentation says**:
  - File: README.md:45
  - Claim: "Real-time notifications via WebSocket"

  **Code reality**:
  - File: src/services/NotificationService.ts:12
  - Implementation: Polling (30s interval)

  **Decision**: Update docs to match code

  **Action Items**:
  - [ ] Update README.md:45 to describe polling
  - [ ] Add explanation why polling chosen over WebSocket
  - [ ] Update architecture docs (if applicable)
```

### Filtering Issues

```bash
# All alignment issues
gh issue list --label alignment

# Critical only
gh issue list --label alignment,critical

# Documentation issues
gh issue list --label alignment,documentation
```

---

## Todo Sync (.todos.md)

### Auto-Generated Todo File

```markdown
# Alignment Todos

**Generated**: 2025-10-26 22:45 by /align-full
**Synced with**: GitHub Issues #23-#30
**Last Updated**: 2025-10-26 22:45

---

## Critical Priority (1 issue)

- [ ] **Update PROJECT.md scope to allow AI features** - Issue #25
  - **Reason**: Code violates documented scope exclusions
  - **Files**: .claude/PROJECT.md (scope section)
  - **Action**: Document why AI features now acceptable + constraints
  - **Impact**: SCOPE CHANGE - requires justification

---

## High Priority (3 issues)

- [ ] **Update docs: polling not WebSocket** - Issue #23
  - **Files**: README.md:45, docs/ARCHITECTURE.md:89
  - **Action**: Replace "WebSocket" with "polling (30s interval)"
  - **Impact**: Documentation misleading users

- [ ] **Add PROJECT.md references to TaskController** - Issue #24
  - **File**: src/controllers/TaskController.ts
  - **Action**: Add comment: `// Serves: PROJECT.md Goal 1 (Core Task Management)`
  - **Impact**: No traceability to strategy

- [ ] **Update CHANGELOG version references** - Issue #26
  - **Files**: README.md:4, package.json:2
  - **Action**: Sync all versions to 3.1.0
  - **Impact**: Version confusion

---

## Medium Priority (3 issues)

- [ ] **Create missing installation.md** - Issue #27
  - **File**: docs/installation.md (create)
  - **Action**: Write installation guide (unblocks README.md:87 link)
  - **Impact**: Broken link in README

... [continues]

---

## Completed (0 issues)

*No issues completed yet*

---

## Workflow

1. Pick highest priority todo
2. Work on it (or use /auto-implement "Fix issue #23")
3. Mark [x] when complete
4. Close GitHub issue: `gh issue close 23`
5. Commit updated .todos.md
6. Repeat for next todo
```

### Manual Sync

```bash
# Update .todos.md after fixing issue
vim .todos.md
# Change [ ] to [x]

# Commit
git add .todos.md
git commit -m "chore: mark todo #23 complete"

# Close issue
gh issue close 23
```

---

## Troubleshooting

### "Analysis takes too long" (>15 min)

**Cause**: Very large project (10K+ LOC, 200+ files)

**Solutions**:
- Run less frequently (monthly vs weekly)
- Scope to specific directories: `/align-full src/`
- Use faster model (opus → sonnet)

---

### "Too many inconsistencies found" (50+)

**Cause**: Project hasn't been aligned in long time

**Solutions**:
- Fix CRITICAL issues first
- Run /align-full again weekly (prevent accumulation)
- Consider this technical debt cleanup sprint

---

### "GitHub issue creation failed"

**Cause**: GitHub CLI not authenticated

**Fix**:
```bash
gh auth login
gh auth status
```

---

### ".todos.md conflicts in git"

**Cause**: Multiple people running /align-full

**Fix**:
- Coordinate alignment runs (one person weekly)
- Or merge conflicts manually
- Or use GitHub issues as source of truth

---

## Comparison to Other Commands

| Command | Purpose | Frequency | Duration |
|---------|---------|-----------|----------|
| `/status` | Goal progress tracking | Daily | 5 sec |
| `/auto-implement` | Feature implementation | Per feature | 5-15 min |
| `/align-full` | Deep alignment analysis | Weekly | 10-15 min |

**Different purposes**:
- `/status` - Strategic progress (quick)
- `/auto-implement` - Build features (medium)
- `/align-full` - Deep consistency check (slow, thorough)

---

## Pro Tips

1. **Run weekly** - Don't let issues accumulate
2. **Fix CRITICAL first** - Defer LOW priority issues
3. **Document scope changes** - Justify all PROJECT.md updates
4. **Use GitHub labels** - Filter issues by type
5. **Track in .todos.md** - Version control your action items
6. **Re-run after fixes** - Verify alignment improved

---

## Implementation

Invoke the **alignment-analyzer** agent to perform deep GenAI-powered analysis.

```bash
# Invoke alignment-analyzer agent
# The agent will:
# 1. Read PROJECT.md (source of truth)
# 2. Analyze all code (reality)
# 3. Analyze all docs (claims)
# 4. Find every inconsistency (GenAI comparison)
# 5. Present options interactively
# 6. Create GitHub issues automatically
# 7. Build synced .todos.md file
```

**Use this weekly to maintain > 90% alignment between vision, code, and docs.**
