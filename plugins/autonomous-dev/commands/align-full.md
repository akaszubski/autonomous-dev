---
description: Deep alignment analysis - PROJECT.md is source of truth. Find conflicts and resolve them.
---

# /align-full - Alignment Analysis

**Find where PROJECT.md differs from reality, then decide: Is PROJECT.md right or does it need updating?**

---

## Quick Start

```bash
/align-full
```

System will:
1. Read your `.claude/PROJECT.md` (source of truth)
2. Scan code and documentation (reality)
3. Find mismatches
4. For each mismatch, ask: **Is PROJECT.md correct?**
5. Create GitHub issues + synced todos based on your answers

**Time**: 10-15 minutes for typical project
**Output**: GitHub issues + `.todos.md` file

---

## The One Decision

Every conflict boils down to one question:

```
PROJECT.md says: X
Code/Docs show: Y

Is PROJECT.md correct?

A) YES → Align code/docs to match PROJECT.md
B) NO  → Update PROJECT.md to match reality
```

Choose A or B. That's it.

---

## What Gets Checked

`/align-full` compares three sources:

### 1. PROJECT.md (Source of Truth)
- Vision: What are we building?
- Goals: What features/capabilities?
- Scope: What's in/excluded?
- Constraints: LOC budget, dependencies, tech stack?
- Architecture: What patterns are documented?
- Success criteria: How do we measure success?

### 2. Code (Reality)
- What features actually exist?
- What architecture is actually used?
- What constraints are violated?
- What exists but isn't in PROJECT.md (scope drift)?

### 3. Documentation (Claims)
- What features are documented as existing?
- What architecture is described?
- What versions/dates are claimed?
- What PROJECT.md references exist?

---

## Example Session

```
/align-full

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
🔍 ALIGNMENT ANALYSIS
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Phase 1: Reading PROJECT.md
  ✅ 3 goals documented
  ✅ 5 constraints documented

Phase 2: Scanning code (1,847 LOC)
  ⚠️  Found: Feature not in PROJECT.md goals

Phase 3: Scanning docs (8 files)
  ⚠️  Found: Version mismatches

Phase 4: Finding conflicts
  🔍 Comparing...

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
📋 CONFLICTS FOUND: 11
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

CONFLICT #1: Real-Time Notifications
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

PROJECT.md SAYS:
  Goal 2: "Real-time notifications (< 100ms latency)"

REALITY SHOWS:
  Code: Polling every 30 seconds
  Docs: Claim WebSocket (but not implemented)

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

IS PROJECT.MD CORRECT?

A) YES
   → Code is wrong. Must implement WebSocket.
   → Files to change: src/services/NotificationService.ts
   → Effort: 30+ hours

B) NO
   → Goal is unrealistic. Update PROJECT.md to "polling (30s)".
   → Files to change: .claude/PROJECT.md, README.md
   → Effort: 30 minutes

Which? [A/B]: B ↵

✅ DECISION: Update PROJECT.md

Creating GitHub issue #23...
Adding to .todos.md...

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
CONFLICT #2: AI Features in Scope
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

PROJECT.md SAYS:
  Scope: "No AI features"

REALITY SHOWS:
  Code: src/services/AIService.ts (uses OpenAI)

IS PROJECT.MD CORRECT?

A) YES → Remove AI feature, revert code
B) NO  → Update PROJECT.md to allow AI features

Which? [A/B]: B ↵

✅ DECISION: Update PROJECT.md scope

... [continues for all 11 conflicts]

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
📊 SUMMARY
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Conflicts: 11 found

Your decisions:
  A (PROJECT.md correct): 3 → Implement features
  B (Update PROJECT.md): 8 → Update docs/goals

GitHub Issues created: 11 (#23-#33)
Todos added to: .todos.md

Next steps:
  1. Review .todos.md
  2. Fix B issues first (quick wins)
  3. Then tackle A issues
  4. Re-run /align-full to verify

Alignment: 67% → 95% (projected after fixes)
```

---

## What Happens With Your Answers

### If You Choose A: "PROJECT.md is Correct"

System creates:
```
Issue: "Implement [Feature] per PROJECT.md Goal X"
Label: alignment, projectmd-correct, feature
Todo: Specific code changes needed
Effort: Usually medium to high
```

Next step: Use `/auto-implement "Fix issue #23"` to implement

### If You Choose B: "Update PROJECT.md"

System creates:
```
Issue: "Update PROJECT.md Goal X to reflect reality"
Label: alignment, projectmd-update, documentation
Todo: Specific file changes (usually PROJECT.md + README + docs)
Effort: Usually low to medium
```

Next step: Update PROJECT.md first, then cascade changes

---

## GitHub Issues & Todos

All decisions create:

1. **GitHub Issue** - Tracked separately, assigned by type
2. **.todos.md** - Version-controlled todo list

```markdown
# Alignment Todos

## Update PROJECT.md (8 todos)

- [ ] Update Goal 2: polling not real-time - Issue #23
  Files: .claude/PROJECT.md
  Effort: 5 min

- [ ] Remove WebSocket claim from README - Issue #23
  Files: README.md
  Effort: 5 min

## Implement Features (3 todos)

- [ ] Add PROJECT.md references to code - Issue #24
  Files: src/controllers/TaskController.ts
  Effort: 10 min

## Auto-Fixed (2 todos)

- [x] Fixed version numbers - Issue #25
- [x] Fixed broken links - Issue #26
```

Track progress:
```bash
# View todos
cat .todos.md

# Mark complete
vim .todos.md  # change [ ] to [x]

# Close issue
gh issue close 23

# Commit progress
git add .todos.md
git commit -m "chore: mark alignment todo #23 complete"
```

---

## When to Run /align-full

### Weekly (Recommended)
Every Monday morning - catch drift early

```bash
/align-full
# Fix HIGH priority issues
# Mark MEDIUM/LOW for next sprint
```

### Before Releases
Before v3.2.0 release - ensure all PROJECT.md promises are met

```bash
/align-full
# Fix ALL CRITICAL + HIGH
# Document MEDIUM issues for v3.3
```

### After Major Changes
After rewriting authentication or refactoring core system

```bash
/align-full
# Verify architecture still aligns
# Ensure docs updated
```

### When Something Feels Off
"I feel like code doesn't match our goals but can't pinpoint why"

```bash
/align-full
# GenAI finds what humans miss
```

---

## How It Works (Under the Hood)

Invokes the **alignment-analyzer** agent to:

```bash
# 1. Read PROJECT.md completely
# 2. Scan all code (src/, lib/)
# 3. Scan all docs (*.md, docs/)
# 4. Find conflicts (PROJECT.md vs reality)
# 5. Present each conflict to you
# 6. Record your decision (A or B)
# 7. Create GitHub issues
# 8. Build .todos.md file
```

---

## Interpreting Results

### "0 conflicts found"
✅ Perfect alignment. PROJECT.md matches reality.

### "Few conflicts (< 5)"
✅ Good alignment. Quick fixes will resolve.

### "Moderate conflicts (5-15)"
⚠️ Fair alignment. Plan 2-3 hours to resolve.

### "Many conflicts (15+)"
❌ Poor alignment. This is your sprint work.
   Plan: B issues (update docs), then A issues (implement)

---

## Reversibility

Don't like a decision? Just re-run:

```bash
/align-full
```

System will show the same conflict again. Choose the other option.
No cleanup needed. Fully reversible.

---

## Principles

1. **PROJECT.md is source of truth**
   Not code. Not docs. PROJECT.md.

2. **Every conflict = one binary choice**
   Is PROJECT.md right? A or B?

3. **You decide, system implements**
   GenAI finds conflicts. You choose direction.

4. **No false precision**
   No hierarchy. No assumptions. Just conflicts and choices.

5. **Fast and scalable**
   2-3 minutes per conflict. Works at any project size.

---

## Implementation

Invoke the **alignment-analyzer** agent to perform deep analysis.

```bash
# The agent will:
# 1. Read PROJECT.md (source of truth)
# 2. Analyze code (reality)
# 3. Analyze docs (claims)
# 4. Find conflicts (mismatches)
# 5. Present each conflict to you
# 6. Record your decision (A/B)
# 7. Create GitHub issues
# 8. Build synced .todos.md
```

---

**Run weekly to keep PROJECT.md and reality in sync.**

