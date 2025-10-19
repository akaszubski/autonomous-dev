---
description: Brings existing project into alignment with PROJECT.md standards. Analyzes structure, creates missing docs/tests, validates patterns. Run after installing plugin or before each sprint.
---

# Align Project with PROJECT.md Standards

Ensures your project structure, documentation, tests, and code align with the strategic direction defined in PROJECT.md.

## Usage

```bash
# Basic alignment check
/align-project

# Auto-fix issues (commit changes after)
/align-project --fix

# Dry run (show what would be fixed)
/align-project --dry-run
```

## When to Run

### 1. After Installing Plugin in Existing Project ✅
```bash
cd my-existing-project
/plugin install autonomous-dev
# Plugin auto-runs: /align-project --fix
# Review changes: git diff HEAD~1
# Rollback if needed: git reset --hard HEAD~1
```

### 2. Before Starting New Sprint ✅
```bash
# End of Sprint 3
git commit -am "feat: Sprint 3 complete"

# Before Sprint 4
/align-project
# Result: Score 95/100, 2 minor issues auto-fixed
# Update PROJECT.md for Sprint 4
# Create GitHub Milestone "Sprint 4"
```

### 3. Regular Maintenance (Weekly/Monthly)
```bash
/align-project --fix
# Keeps project aligned with PROJECT.md standards
```

## What Gets Checked

### 1. PROJECT.md Alignment ⭐ (MOST IMPORTANT)

**Checks:**
- ✅ PROJECT.md exists
- ✅ Contains required sections (GOALS, SCOPE, CONSTRAINTS)
- ✅ Current sprint is defined
- ✅ Strategic direction is clear

**Auto-fixes:**
- Creates PROJECT.md from template if missing
- Adds missing sections
- Validates structure

**Example:**
```markdown
Score: 0/100 - No PROJECT.md found

Auto-fix:
✅ Created PROJECT.md from template
⏸️  Manual: Fill in GOALS, SCOPE, CONSTRAINTS for your project

Score after fix: 40/100
```

### 2. Folder Structure

**Checks:**
- ✅ Source code in `src/` or project-specific directory
- ✅ Tests in `tests/` directory
- ✅ Documentation in `docs/` directory
- ✅ No `.md` files in root (except README, CHANGELOG, LICENSE, CLAUDE)
- ✅ Proper .gitignore entries

**Auto-fixes:**
- Moves scattered tests to `tests/`
- Moves documentation to `docs/`
- Creates missing directories
- Updates .gitignore

**Example:**
```markdown
Score: 60/100 - Folder structure issues

Found:
❌ tests/test_auth.py in wrong location
❌ IMPLEMENTATION_NOTES.md in root

Auto-fix:
✅ Moved tests/test_auth.py → tests/unit/test_auth.py
✅ Moved IMPLEMENTATION_NOTES.md → docs/archive/
✅ Created docs/ directory structure

Score after fix: 85/100
```

### 3. Documentation Completeness

**Checks:**
- ✅ README.md exists with project overview
- ✅ CHANGELOG.md exists and follows format
- ✅ API documentation (if applicable)
- ✅ Docstrings on public functions (Python)

**Auto-fixes:**
- Creates README.md from template
- Creates CHANGELOG.md
- Creates docs/ subdirectories

**Example:**
```markdown
Score: 70/100 - Documentation gaps

Found:
❌ No CHANGELOG.md
❌ API functions missing docstrings (12 functions)

Auto-fix:
✅ Created CHANGELOG.md with template
⏸️  Manual: Add docstrings to functions (see list below)

Score after fix: 85/100
```

### 4. Testing Infrastructure

**Checks:**
- ✅ Test framework configured (pytest/jest)
- ✅ Coverage measurement enabled
- ✅ Tests organized by type (unit, integration, regression)
- ✅ Test coverage ≥ 80%

**Auto-fixes:**
- Creates test directories
- Adds pytest/jest configuration
- Creates sample test files

**Example:**
```markdown
Score: 50/100 - Testing gaps

Found:
❌ No pytest.ini configuration
❌ Tests not organized (all in one directory)
❌ Coverage: 45% (below 80% threshold)

Auto-fix:
✅ Created pytest.ini with coverage config
✅ Organized tests: unit/, integration/, regression/
⏸️  Manual: Write tests to reach 80% coverage (35% more needed)

Score after fix: 70/100
```

### 5. Security Validation

**Checks:**
- ✅ No hardcoded secrets in code
- ✅ .env in .gitignore
- ✅ No API keys committed
- ✅ Input validation on user-facing code

**Auto-fixes:**
- Adds .env to .gitignore
- Creates .env.example template
- Warns about hardcoded secrets (manual fix required)

**Example:**
```markdown
Score: 30/100 - SECURITY ISSUES

Found:
🔴 CRITICAL: API key found in src/config.py line 42
❌ .env not in .gitignore

Auto-fix:
✅ Added .env to .gitignore
✅ Created .env.example template
🔴 MANUAL REQUIRED: Remove API key from src/config.py
   Move to .env: API_KEY=...

Score after fix: 50/100 (critical issue blocks higher score)
```

### 6. Code Quality

**Checks:**
- ✅ Code formatted (black/prettier)
- ✅ Type hints on functions (Python)
- ✅ No code duplication
- ✅ Functions under 50 lines

**Auto-fixes:**
- Runs formatters (black, isort, prettier)
- Reports issues needing manual fix

**Example:**
```markdown
Score: 75/100 - Code quality issues

Found:
❌ Code not formatted (23 files)
❌ 45 functions missing type hints

Auto-fix:
✅ Ran black + isort on Python files
✅ Ran prettier on JS/TS files
⏸️  Manual: Add type hints to functions (see list)

Score after fix: 90/100
```

### 7. GitHub Integration

**Checks:**
- ✅ .env file exists with GITHUB_TOKEN
- ✅ GitHub Milestone exists for current sprint
- ✅ Issues tagged with milestone

**Auto-fixes:**
- Creates .env.example
- Links to setup guide

**Example:**
```markdown
Score: 100/100 - GitHub integration optional

Found:
⚠️  No .env file (GitHub integration disabled)

Suggestion:
💡 To enable GitHub integration:
   1. See: .claude/docs/GITHUB_AUTH_SETUP.md
   2. Create .env with GITHUB_TOKEN
   3. Create GitHub Milestone for current sprint

Note: GitHub integration is optional
Score: 100/100 (not required for alignment)
```

## Alignment Report Format

```markdown
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
PROJECT ALIGNMENT REPORT
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Overall Score: 75/100

┌─────────────────────────────────────────────────────────┐
│ ⭐ PROJECT.md Alignment (MOST IMPORTANT)                │
│ Score: 90/100                                           │
│ ✅ PROJECT.md exists                                    │
│ ✅ Contains GOALS, SCOPE, CONSTRAINTS                   │
│ ⏸️  Current sprint needs updating                      │
└─────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────┐
│ 📁 Folder Structure                                     │
│ Score: 85/100                                           │
│ ✅ Source in src/                                       │
│ ✅ Tests in tests/                                      │
│ ✅ Docs in docs/                                        │
│ ⏸️  2 .md files in root (should be in docs/)           │
└─────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────┐
│ 📚 Documentation                                        │
│ Score: 70/100                                           │
│ ✅ README.md exists                                     │
│ ✅ CHANGELOG.md exists                                  │
│ ⏸️  12 functions missing docstrings                    │
└─────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────┐
│ 🧪 Testing                                              │
│ Score: 60/100                                           │
│ ✅ pytest configured                                    │
│ ⚠️  Coverage: 65% (need 80%)                           │
│ ⏸️  Write 15% more tests                               │
└─────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────┐
│ 🔒 Security                                             │
│ Score: 95/100                                           │
│ ✅ No hardcoded secrets                                 │
│ ✅ .env in .gitignore                                   │
│ ✅ Input validation present                             │
└─────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────┐
│ ✨ Code Quality                                         │
│ Score: 80/100                                           │
│ ✅ Code formatted                                       │
│ ⏸️  45 functions need type hints                       │
└─────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────┐
│ 🔗 GitHub Integration (Optional)                        │
│ Score: N/A                                              │
│ ⚠️  GitHub integration not configured                  │
│ 💡 See: .claude/docs/GITHUB_AUTH_SETUP.md              │
└─────────────────────────────────────────────────────────┘

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

AUTO-FIXED (8 issues):
✅ Moved 2 .md files to docs/
✅ Created missing test directories
✅ Ran black + isort formatters
✅ Added .env to .gitignore
✅ Created .env.example template
✅ Created pytest.ini
✅ Organized tests into unit/integration/regression
✅ Created CHANGELOG.md

MANUAL ACTIONS NEEDED (3 issues):
⏸️  1. Update PROJECT.md current sprint to "Sprint 4"
⏸️  2. Add docstrings to 12 functions (see list below)
⏸️  3. Write tests to reach 80% coverage (currently 65%)

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

NEXT STEPS:
1. Review changes: git diff HEAD~1
2. Complete manual actions (listed above)
3. Re-run: /align-project (should reach 100/100)
4. If satisfied with changes: git push
5. If not satisfied: git reset --hard HEAD~1 (rollback)

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
```

## Git Safety (Rollback Protection)

**Before making changes**, /align-project creates a checkpoint:

```bash
# Checkpoint commit
git add -A
git commit -m "checkpoint: before align-project"

# Make alignment changes
# ... auto-fixes ...

# Commit alignment changes
git add -A
git commit -m "chore: align project with PROJECT.md standards"
```

**To rollback:**
```bash
# View what changed
git diff HEAD~1

# Rollback if not satisfied
git reset --hard HEAD~1  # Removes alignment changes
git reset --hard HEAD~2  # Removes checkpoint too
```

## Scoring System

| Score | Meaning | Action |
|-------|---------|--------|
| 90-100 | ✅ Excellent alignment | Ready for autonomous development |
| 70-89 | ⚠️ Good, minor issues | Fix manual actions, re-run |
| 50-69 | ⚠️ Needs work | Address issues, may take time |
| 0-49 | 🔴 Poor alignment | Significant work needed |

## Auto-Fix vs Manual

### Auto-Fixed (Immediate)
- ✅ Folder structure (move files)
- ✅ Create missing directories
- ✅ Run formatters
- ✅ Create template files (PROJECT.md, CHANGELOG.md)
- ✅ Update .gitignore
- ✅ Organize tests

### Manual Required
- ⏸️ Write missing tests
- ⏸️ Add docstrings
- ⏸️ Remove hardcoded secrets
- ⏸️ Fill in PROJECT.md content
- ⏸️ Create GitHub Milestones
- ⏸️ Set up .env authentication

## Example Workflows

### Scenario 1: New Plugin Installation
```bash
cd my-existing-api
/plugin install autonomous-dev

# Plugin auto-runs:
/align-project --fix

# Result:
Score: 65/100 → 85/100 (after auto-fixes)
Manual actions needed: 3

# Complete manual actions
vim PROJECT.md  # Fill in goals
# Add missing tests
# Add docstrings

# Re-run
/align-project

# Result:
Score: 100/100 ✅

# Ready!
git push
```

### Scenario 2: Before Sprint
```bash
# End Sprint 3
git commit -am "feat: Sprint 3 complete"

# Align before Sprint 4
/align-project

# Result:
Score: 95/100
Issues: PROJECT.md current sprint outdated

# Fix
vim PROJECT.md  # Update to Sprint 4

# Re-run
/align-project

# Result:
Score: 100/100 ✅

# Create Sprint 4 Milestone
gh api repos/owner/repo/milestones -f title="Sprint 4"

# Start Sprint 4
"implement first feature from Sprint 4"
```

### Scenario 3: Messy Existing Project
```bash
cd very-messy-project
# Files everywhere, no docs, tests failing

/plugin install autonomous-dev

# Result:
Score: 35/100
Critical issues: 5
Auto-fixes: 12
Manual actions: 8

# Review changes
git diff HEAD~1

# Keep changes
git push

# Work through manual actions (over time)
# Each fix improves score

# Week 1: 35 → 60
# Week 2: 60 → 80
# Week 3: 80 → 100 ✅
```

## Configuration

Add to `.claude/settings.json`:

```json
{
  "commands": {
    "align-project": {
      "auto_run_after_install": true,
      "strict_mode": false,
      "min_score": 80
    }
  }
}
```

- `auto_run_after_install`: Run after plugin install (recommended: true)
- `strict_mode`: Require 100/100 score (recommended: false)
- `min_score`: Minimum acceptable score (recommended: 80)

## Related Commands

- `/format` - Format code only
- `/test` - Run tests only
- `/security-scan` - Security check only
- `/full-check` - Format + test + security
- `/auto-implement` - Start autonomous development

---

**Philosophy**: PROJECT.md defines standards. /align-project brings reality into alignment with those standards.
