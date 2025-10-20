---
description: Brings existing project into alignment with PROJECT.md standards. Analyzes structure, validates patterns, optionally syncs with GitHub. Supports safe mode and GitHub integration.
---

# Align Project with PROJECT.md Standards

Ensures your project structure, documentation, tests, and code align with the strategic direction defined in PROJECT.md.

## Usage

```bash
# Basic alignment check (read-only analysis)
/align-project

# Auto-fix issues
/align-project --fix

# Safe mode: Interactive 3-phase (ask before changes)
/align-project --safe

# Sync with GitHub after alignment
/align-project --sync-github

# Combined: Safe mode + GitHub sync
/align-project --safe --sync-github

# Dry run (show what would change)
/align-project --dry-run
```

## Flags

| Flag | Description |
|------|-------------|
| `--fix` | Auto-fix issues and commit changes |
| `--safe` | Interactive mode - asks before each change |
| `--sync-github` | Push commits + create GitHub issues/milestones |
| `--dry-run` | Show what would change without making changes |

---

## Standard Mode (Default)

```bash
/align-project
```

**What it does**:
- ✅ Analyzes project structure
- ✅ Validates against PROJECT.md
- ✅ Reports issues
- ❌ Makes NO changes (read-only)

**Use when**: You want to see alignment score without changes

---

## Safe Mode (`--safe`)

```bash
/align-project --safe
```

**3-Phase Interactive Approach**:

### Phase 1: Analyze (Read-Only)
- Reads codebase
- Identifies issues
- Asks clarifying questions
- Generates analysis report

### Phase 2: Generate PROJECT.md (Draft)
```bash
# After Phase 1 questions answered
/align-project --safe --generate-project-md
```
- Creates PROJECT.md from code
- You review and edit
- Saves as draft

### Phase 3: Interactive Alignment
```bash
# After PROJECT.md finalized
/align-project --safe --interactive
```
- **Asks before EACH change**
- You approve/reject individually
- Safe, reversible steps

**Use when**: First-time setup or existing projects

---

## GitHub Sync (`--sync-github`)

```bash
/align-project --sync-github
```

**Requires**: `.env` with `GITHUB_TOKEN`

**What it does**:
1. ✅ Pushes commits to GitHub
2. ✅ Creates GitHub Milestone from PROJECT.md CURRENT SPRINT
3. ✅ Creates GitHub issues for Sprint goals
4. ✅ Updates PROJECT.md with GitHub links
5. ✅ Links issues to milestone

**Example**:
```bash
# Local alignment complete
/align-project --fix
# Score: 100/100 ✅

# Sync with GitHub
/align-project --sync-github

# Creates:
# ✅ Milestone: "Sprint 6: Team Collaboration"
# ✅ Issue #42: "PR automation"
# ✅ Issue #43: "GitHub integration"
# ✅ Issue #44: "Team onboarding"
# ✅ Issue #45: "Code review integration"
# ✅ Updates PROJECT.md with links
```

**Use when**: After local alignment, ready to sync with team

---

## What Gets Checked

### 1. PROJECT.md Alignment ⭐ (MOST IMPORTANT)

**Checks**:
- ✅ PROJECT.md exists
- ✅ Contains GOALS, SCOPE, CONSTRAINTS, CURRENT SPRINT
- ✅ Strategic direction clear

**Auto-fixes** (with `--fix`):
- Creates PROJECT.md from template
- Adds missing sections
- Validates structure

### 2. Folder Structure

**Checks**:
- ✅ Source in `src/`
- ✅ Tests in `tests/`
- ✅ Docs in `docs/`
- ✅ Clean root (only essential .md files)

**Auto-fixes**:
- Moves files to correct locations
- Creates missing directories
- Updates .gitignore

### 3. Documentation

**Checks**:
- ✅ README.md exists
- ✅ CHANGELOG.md exists
- ✅ Docstrings on functions

**Auto-fixes**:
- Creates templates
- Organizes docs/

### 4. Testing

**Checks**:
- ✅ Test framework configured
- ✅ Tests organized (unit/integration/regression)
- ✅ Coverage ≥ 80%

**Auto-fixes**:
- Creates test directories
- Adds pytest/jest config

### 5. Security

**Checks**:
- ✅ No hardcoded secrets
- ✅ .env in .gitignore
- ✅ No API keys committed

**Auto-fixes**:
- Adds .env to .gitignore
- Creates .env.example
- Warns about secrets (manual fix required)

### 6. Code Quality

**Checks**:
- ✅ Code formatted
- ✅ Type hints (Python)
- ✅ No duplication

**Auto-fixes**:
- Runs formatters (black, prettier)

### 7. GitHub Integration (with `--sync-github`)

**Checks**:
- ✅ .env with GITHUB_TOKEN exists
- ✅ GitHub Milestone exists for sprint
- ✅ Issues linked to milestone

**Auto-syncs**:
- Creates milestone from PROJECT.md
- Creates issues for Sprint goals
- Links issues to milestone
- Updates PROJECT.md with URLs

---

## Alignment Report Example

```markdown
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
PROJECT ALIGNMENT REPORT
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Overall Score: 85/100

⭐ PROJECT.md: 90/100
📁 Folder Structure: 85/100
📚 Documentation: 80/100
🧪 Testing: 70/100
🔒 Security: 95/100
✨ Code Quality: 90/100
🔗 GitHub: N/A (not configured)

AUTO-FIXED (5 issues):
✅ Moved 2 .md files to docs/
✅ Created pytest.ini
✅ Ran formatters
✅ Added .env to .gitignore
✅ Created CHANGELOG.md

MANUAL ACTIONS NEEDED (2):
⏸️  Write tests to reach 80% coverage (currently 70%)
⏸️  Add docstrings to 8 functions

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
```

---

## Common Workflows

### Workflow 1: New Plugin Installation
```bash
# Install plugin
cd my-project
/plugin install autonomous-dev

# Safe first-time alignment
/align-project --safe

# Answer questions
# Review proposed changes
# Approve changes

# Sync with GitHub
/align-project --sync-github

# Result: Project aligned + GitHub synced
```

### Workflow 2: Before Sprint
```bash
# Check alignment
/align-project

# Fix issues
/align-project --fix

# Update PROJECT.md for new sprint
vim .claude/PROJECT.md

# Sync new sprint with GitHub
/align-project --sync-github

# Result: New sprint milestone and issues created
```

### Workflow 3: Quick Check
```bash
# Just check score
/align-project

# Result: Score 95/100 ✅
```

### Workflow 4: Dry Run
```bash
# See what would change
/align-project --dry-run

# Review proposed changes
# Decide to apply or not

# Apply if good
/align-project --fix
```

---

## GitHub Sync Details

When using `--sync-github`, here's what happens:

### Step 1: Read PROJECT.md
```markdown
## CURRENT SPRINT

**Sprint Name**: Sprint 6: Team Collaboration
**Duration**: 2025-10-20 → 2025-11-03
**Status**: In Progress

**Sprint Goals**:
1. PR automation
2. GitHub integration
3. Team onboarding
4. Code review integration
```

### Step 2: Create GitHub Milestone
```bash
gh api repos/OWNER/REPO/milestones \
  -f title="Sprint 6: Team Collaboration" \
  -f due_on="2025-11-03T00:00:00Z" \
  -f description="Focus on team collaboration features"
```

### Step 3: Create GitHub Issues
```bash
# For each Sprint Goal
gh issue create \
  --title "Implement PR automation" \
  --body "Auto-create PRs, link to issues, request reviews" \
  --milestone "Sprint 6" \
  --label "enhancement"

# Repeat for each goal
```

### Step 4: Update PROJECT.md
```markdown
## CURRENT SPRINT

**Sprint Name**: Sprint 6: Team Collaboration
**GitHub Milestone**: https://github.com/owner/repo/milestone/6
**Duration**: 2025-10-20 → 2025-11-03

**Sprint Goals**:
1. 🚧 PR automation (#42)
2. ⏸️ GitHub integration (#43)
3. ⏸️ Team onboarding (#44)
4. ⏸️ Code review integration (#45)
```

### Step 5: Commit Changes
```bash
git add .claude/PROJECT.md
git commit -m "chore: sync Sprint 6 with GitHub"
git push origin main
```

---

## Safe Mode Features

### 1. Smart Diff View
Shows **before/after** with risk scoring:
```markdown
CHANGE #1: Move tests/old/test_auth.py → tests/unit/test_auth.py
Risk: LOW ✅
Impact: Organization only, no code changes

Approve? (y/n/s=skip)
```

### 2. Dry Run with Stash
```bash
# Test changes without committing
/align-project --safe --dry-run

# Uses git stash to simulate
# Rolls back after preview
```

### 3. Pattern Learning
```markdown
You chose: "Move old files to docs/archive/"

Remember this pattern? (y/n)
> y

✅ Will apply same pattern to similar files:
   - lib/old_utils.py → docs/archive/
   - config/deprecated.yaml → docs/archive/
```

### 4. Conflict Resolution
```markdown
CONFLICT: PROJECT.md says "Sprint 2" but GitHub shows "Sprint 4"

Options:
A) Update PROJECT.md to Sprint 4 (trust GitHub)
B) Update GitHub to Sprint 2 (trust PROJECT.md)
C) Manual resolution (I'll help you decide)

Choose: _
```

### 5. Progressive Enhancement
```markdown
Quick Wins (< 5 min):
✅ Move 3 .md files to docs/
✅ Run formatters
✅ Create .gitignore entries

Deep Work (> 30 min):
⏸️  Write missing tests (15 tests needed)
⏸️  Add docstrings (42 functions)
⏸️  Refactor duplicated code (8 instances)

Apply quick wins now, deep work later? (y/n)
```

### 6. Undo Stack
```markdown
Changes made:
1. Moved files (5 files)
2. Created pytest.ini
3. Ran black formatter

Undo last change? (u)
Undo all changes? (U)
Keep all changes? (y)
```

### 7. Simulation Mode
```bash
# Risk-free testing
/align-project --safe --simulate

# Creates isolated branch
# Makes all changes
# Shows results
# Deletes branch (no permanent changes)
```

---

## Configuration

Add to `.claude/settings.json`:

```json
{
  "commands": {
    "align-project": {
      "auto_run_after_install": true,
      "default_mode": "safe",
      "min_score": 80,
      "github_sync_auto": false
    }
  }
}
```

---

## Rollback

All modes create git commits for safety:

```bash
# View changes
git diff HEAD~1

# Rollback if needed
git reset --hard HEAD~1

# Or use undo stack (in safe mode)
```

---

## Examples

### Example 1: First-Time Safe Alignment
```bash
cd legacy-project

# Safe mode asks questions
/align-project --safe

# Questions answered, ready to apply
/align-project --safe --interactive

# Approve each change
# Changes applied safely

# Sync with GitHub
/align-project --sync-github
```

### Example 2: Quick Fix + GitHub Sync
```bash
# Fix and sync in one command
/align-project --fix --sync-github

# Result:
# ✅ Local alignment: 100/100
# ✅ GitHub milestone created
# ✅ GitHub issues created
# ✅ PROJECT.md updated with links
```

### Example 3: Sprint Transition
```bash
# End Sprint 5
git commit -am "feat: Sprint 5 complete"

# Update PROJECT.md for Sprint 6
vim .claude/PROJECT.md

# Sync Sprint 6 with GitHub
/align-project --sync-github

# Result:
# ✅ Sprint 6 milestone created
# ✅ Sprint 6 issues created from goals
# ✅ Ready to start development
```

---

## Troubleshooting

### "GitHub sync failed"

Check:
1. `.env` file exists with `GITHUB_TOKEN`
2. Token has `repo` scope
3. Network connection
4. GitHub API rate limit

```bash
# Test GitHub auth
gh auth status

# Check token scopes
gh auth token
```

### "Conflicts in PROJECT.md"

Safe mode will detect and ask:
```markdown
PROJECT.md has uncommitted changes.

Options:
A) Commit changes first
B) Stash changes
C) Cancel alignment

Choose: _
```

---

## Related Commands

- `/format` - Code formatting only
- `/test` - Testing only
- `/security-scan` - Security only
- `/full-check` - Format + test + security
- `/auto-implement` - Start development

---

**Philosophy**: PROJECT.md defines standards. `/align-project` brings reality into alignment with those standards. `--safe` prevents breaking things. `--sync-github` connects team.
