
## Phase 1: Analysis Only (Default - SAFE ✅)

```bash
/align-project
```

**What it does**:
- ✅ Reads current codebase
- ✅ Identifies potential issues
- ✅ **Asks questions** about unclear things
- ✅ Generates analysis report
- ❌ **Makes ZERO changes** to your code

### Example Output:

```markdown
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
📊 PROJECT ANALYSIS (Phase 1 - Read-Only)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Discovered:
✅ Language: Python 3.11
✅ Framework: FastAPI
✅ Database: PostgreSQL
✅ Tests: pytest (found 45 tests)
✅ Coverage: 65%
✅ Documentation: README.md, API docs

Potential Issues Found (12):

┌─────────────────────────────────────────────────────────┐
│ QUESTIONS I NEED ANSWERED                               │
└─────────────────────────────────────────────────────────┘

1. Found stale files - what should I do with them?
   - src/old_auth.py (last modified: 6 months ago)
   - lib/deprecated_utils.py
   - config_old.yaml

   Options:
   A) Move to docs/archive/ (preserve but hide)
   B) Delete (I can confirm they're obsolete)
   C) Keep where they are (still in use)

2. Found multiple configuration files - which is current?
   - config.yaml (last used: 2 months ago)
   - config.json (last used: yesterday)
   - settings.py (referenced in 15 files)

   Which is the active config?

3. Tests in two directories - which is preferred?
   - tests/ (30 tests)
   - test/ (15 tests)

   Should I:
   A) Consolidate all to tests/
   B) Keep both (different purposes?)

4. Sprint mismatch:
   - PROJECT.md says: "Sprint 2: User Authentication"
   - GitHub Milestone: "Sprint 4: Performance"
   - Git branch: feature/sprint-4-caching

   What is the CURRENT sprint?

5. Found programs/paths that may not be current:
   - scripts/deploy.sh references "old-server.com"
   - Dockerfile uses python:3.9 (but code requires 3.11)
   - README mentions "npm start" but project uses Python

   Should I flag these for manual update?

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

📝 ANSWER THESE QUESTIONS, THEN:

Option A: Let me generate a PROJECT.md from current code
   /align-project --generate-project-md

Option B: You'll provide a PROJECT.md
   Create PROJECT.md manually, then run:
   /align-project --interactive

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
```


## Phase 2: Generate PROJECT.md from Code (SAFE ✅)

```bash
# After you answer questions from Phase 1
/align-project --generate-project-md
```

**What it does**:
- ✅ Uses your answers to understand project
- ✅ Analyzes code to infer goals/standards
- ✅ **Creates DRAFT PROJECT.md** (in docs/draft/)
- ✅ **Doesn't overwrite** existing PROJECT.md
- ❌ **Makes no other changes**

### Example Output:

```markdown
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
📄 DRAFT PROJECT.md GENERATED
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Location: docs/draft/PROJECT.md

Based on code analysis:

GOALS (inferred):
1. Build FastAPI REST API for e-commerce
2. Support 1K concurrent users
3. Maintain 80%+ test coverage

SCOPE (inferred):
IN:
- User authentication (found: src/auth.py)
- Product catalog (found: src/products/)
- Shopping cart (found: src/cart.py)

OUT:
- Mobile app (no mobile code found)
- Real-time features (async only)

CONSTRAINTS (detected):
- Tech Stack: Python 3.11, FastAPI, PostgreSQL
- Testing: pytest (current coverage: 65%)
- Formatting: black + isort (configured)

CURRENT SPRINT (best guess):
- "Sprint 4: Performance" (from GitHub Milestone)

STANDARDS (observed):
- Type hints: Used in 80% of functions (good!)
- Docstrings: Present on 60% of functions (need more)
- Tests: Organized in tests/unit/, tests/integration/

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

⚠️  IMPORTANT: This is a DRAFT based on code analysis

NEXT STEPS:
1. Review: cat docs/draft/PROJECT.md
2. Edit: Fix any misunderstandings
   - Correct GOALS if I misunderstood
   - Update SCOPE if incomplete
   - Adjust CONSTRAINTS as needed
3. Approve: When satisfied, move it:
   mv docs/draft/PROJECT.md ./PROJECT.md
4. Continue: Then run:
   /align-project --interactive

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

📋 DRAFT PREVIEW:

# Project Context

## GOALS
1. Primary Objective: Build scalable e-commerce REST API
   (Inferred from: README, src/products/, src/cart.py)

2. Success Metric: Support 1K concurrent users with <100ms response
   (Inferred from: load tests in tests/load/)

3. Quality Standard: 80%+ coverage, type-safe APIs
   (Inferred from: pytest config, mypy config)

... (full draft in docs/draft/PROJECT.md)

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
```


## Phase 3: Interactive Alignment (ASK BEFORE ACTING ✅)

```bash
# After reviewing and approving PROJECT.md
/align-project --interactive
```

**What it does**:
- ✅ Proposes ONE change at a time
- ✅ **Asks for approval** before doing it
- ✅ Shows exactly what will change
- ✅ Commits after EACH approved change (easy rollback)
- ✅ Allows skip/undo/stop anytime

### Example Interactive Session:

```markdown
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
🔧 INTERACTIVE ALIGNMENT (Phase 3)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Based on PROJECT.md, I found 12 alignment opportunities.
I'll ask about each one before making changes.

You can:
- Approve (Y)
- Skip (N)
- Stop entirely (Ctrl+C)
- Undo last change (U)
- See details (?)

Let's start...

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Action 1 of 12
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

🔍 Found: IMPLEMENTATION_NOTES.md in root

Proposed Action:
   Move to: docs/archive/IMPLEMENTATION_NOTES.md
   Reason: Keep root clean (PROJECT.md standard)

────────────────────────────────────────
Current:  ./IMPLEMENTATION_NOTES.md
New:      docs/archive/IMPLEMENTATION_NOTES.md

Last modified: 6 months ago (may be stale)
Size: 3.2 KB
────────────────────────────────────────

Options:
[Y] Yes, move to archive
[N] No, keep in root (skip this)
[D] Delete it (I'll confirm obsolete first)
[?] Show file contents before deciding
[S] Stop alignment (save progress)

Your choice: ?

────────────────────────────────────────
File contents (first 20 lines):

# Implementation Notes - Sprint 2

## Auth System Design
- Using JWT tokens
- Bcrypt for hashing
...
(20 more lines)

────────────────────────────────────────

This looks like old sprint notes. Still relevant?

[Y] Move to archive
[N] Keep in root
[D] Delete it

Your choice: Y

✅ Moving IMPLEMENTATION_NOTES.md to archive...

Creating commit:
   "chore: move IMPLEMENTATION_NOTES.md to archive (stale)"

✅ Done! (Commit: a1b2c3d)

Rollback command: git reset --hard HEAD~1

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Action 2 of 12
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

🔍 Found: src/old_auth.py (last modified: 6 months ago)

Proposed Action:
   Move to: src/archive/old_auth.py
   Reason: File appears unused (no imports found)

────────────────────────────────────────
Current:  src/old_auth.py
New:      src/archive/old_auth.py

References found: 0 imports
Last commit: 6 months ago - "feat: migrate to new auth"
────────────────────────────────────────

⚠️  WARNING: No code references this file, but:
- It's in active src/ directory
- Contains 200 lines of code
- May have been replaced

Should I:
[Y] Move to archive (preserve but hide)
[D] Delete it (confirm it's replaced)
[N] Keep it (still needed)
[?] Show code diff with current auth.py

Your choice: ?

────────────────────────────────────────
Comparing old_auth.py vs auth.py:

OLD (old_auth.py):
class OldAuthSystem:
    def login(user, password):  # No type hints
        # Basic auth logic

NEW (auth.py):
class AuthSystem:
    def login(user: str, password: str) -> Token:  # Type safe
        # JWT-based auth

Looks like old_auth.py was replaced by auth.py
────────────────────────────────────────

Recommendation: Move to archive (safe to preserve)

[Y] Move to archive
[D] Delete permanently
[N] Keep in src/

Your choice: Y

✅ Moving old_auth.py to archive...

Creating commit:
   "chore: archive old_auth.py (replaced by auth.py)"

✅ Done! (Commit: d4e5f6g)

Progress: 2/12 actions completed
Rollback: git reset --hard HEAD~2

[Continue? Y/N]: Y

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Action 3 of 12
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

🔍 Found: Dockerfile references python:3.9

Proposed Action:
   Update to: python:3.11 (matches PROJECT.md constraint)
   Reason: Code requires Python 3.11+ but Dockerfile uses 3.9

────────────────────────────────────────
File: Dockerfile
Line 1: FROM python:3.9

PROJECT.md says: Python 3.11+
Current code uses: match/case (requires 3.10+)
────────────────────────────────────────

⚠️  This will change your Docker build!

[Y] Update Dockerfile to python:3.11
[N] Skip (I'll update manually)
[?] Show full Dockerfile first

Your choice: Y

✅ Updating Dockerfile...

Changed:
   FROM python:3.9
   FROM python:3.11

Creating commit:
   "fix: update Dockerfile to Python 3.11 (matches PROJECT.md)"

✅ Done! (Commit: h7i8j9k)

Progress: 3/12 actions completed

[Continue? Y/N/U(ndo)]: Y

... (continues for remaining 9 actions)
```


## Safety Features

### 1. One Change at a Time
- Each action is isolated
- Committed separately
- Easy to rollback individually

### 2. Before/After Visibility
```markdown
Before: ./IMPLEMENTATION_NOTES.md
After:  docs/archive/IMPLEMENTATION_NOTES.md

Show diff? [Y/N]
```

### 3. Stale Detection
```markdown
⚠️  File last modified: 6 months ago
    Last commit: "feat: migrate to new system"
    May be obsolete
```

### 4. Reference Checking
```markdown
Checking references to old_auth.py:
- Imports found: 0
- Comments mentioning it: 2
- Git history: Replaced in commit abc123
```

### 5. Archive Instead of Delete
```markdown
Default action: Move to archive/
Reason: Preserve history, easy to restore

Only suggests DELETE when:
- File is empty
- File is duplicate
- You explicitly confirm
```

### 6. Rollback Commands
```markdown
After each change:
✅ Done! (Commit: a1b2c3d)

Rollback this change: git reset --hard HEAD~1
Rollback all changes: git reset --hard HEAD~12
```


## What Gets Checked (Same as Before)

1. ⭐ PROJECT.md alignment (MOST IMPORTANT)
2. Folder structure
3. Documentation completeness
4. Testing infrastructure
5. Security validation
6. Code quality
7. GitHub integration (optional)

(Same detailed checks as before, but now **asks before acting**)


## Workflow Examples

### Scenario 1: New Plugin in Messy Project

```bash
cd very-messy-legacy-project

# Step 1: Analyze (safe, read-only)
/align-project

# Output: Found 20 potential issues, 5 questions
# Answer questions...

# Step 2: Generate PROJECT.md from code
/align-project --generate-project-md

# Output: Draft created in docs/draft/PROJECT.md
# Review and edit draft...

# Step 3: Approve draft
mv docs/draft/PROJECT.md ./PROJECT.md

# Step 4: Interactive alignment
/align-project --interactive

# Interactive session asks about each of 20 issues
# You approve/skip/undo each one
# Each change is a separate commit

# Result: Project aligned safely!
```

### Scenario 2: Before New Sprint

```bash
# Analyze current state
/align-project

# Output: 95/100 score, found 2 minor issues

# Interactive fix
/align-project --interactive

# 1. Update PROJECT.md sprint reference? [Y]
# 2. Move old sprint docs to archive? [Y]

# Done!
Score: 100/100 ✅
```


## Configuration

```json
{
  "align-project": {
    "interactive_mode": true,
    "archive_threshold_days": 90,
    "auto_detect_stale": true,
    "ask_before_delete": true,
    "commit_per_action": true
  }
}
```


## Philosophy

**SAFETY FIRST**:
1. Analyze before acting (Phase 1)
2. Generate truth from code (Phase 2)
3. Ask before each change (Phase 3)
4. One commit per change (easy rollback)
5. Archive > Delete (preserve history)
6. User always in control

**NEVER**:
- ❌ Make bulk changes without asking
- ❌ Delete files without confirmation
- ❌ Assume what's stale
- ❌ Change working code
- ❌ Break existing paths/references

**ALWAYS**:
- ✅ Ask questions when uncertain
- ✅ Show before/after
- ✅ Check for references
- ✅ Detect staleness
- ✅ Provide rollback commands
- ✅ Commit incrementally


**Your project. Your control. Your approval for every change.**
