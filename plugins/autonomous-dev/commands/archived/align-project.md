---
description: Analyze and fix project alignment with PROJECT.md standards
---

# Align Project

**Analyze project structure and optionally fix alignment issues**

---

## Usage

```bash
/align-project
```

**Time**: 5-20 minutes (depending on mode selected)
**Interactive**: Asks what you want to do after analysis

---

## How It Works

The command runs in two steps:

### Step 1: Analysis (Always Runs)

Analyzes your project:
- ✅ PROJECT.md exists and is complete
- ✅ Directory structure (tests/, docs/)
- ✅ Documentation organization
- ✅ Test coverage structure
- ✅ Hook configuration
- ✅ Command availability

### Step 2: Action Menu (You Choose)

After analysis, you see:

```
┌─ Alignment Report ──────────────────────────┐
│                                              │
│ Overall Alignment: 75% (needs improvement)   │
│                                              │
│ ✅ PROJECT.md: Present and complete          │
│ ✅ Directory structure: Correct              │
│ ⚠️  Documentation: 3 files in root           │
│ ❌ Test structure: Missing tests/unit/       │
│ ⚠️  Hooks: Not all active                    │
│                                              │
│ Issues Found: 5                              │
│  - 2 critical (must fix)                     │
│  - 3 warnings (should fix)                   │
└──────────────────────────────────────────────┘

What would you like to do?

1. View detailed report only (no changes)
2. Fix issues interactively (asks before each phase)
3. Preview all changes (dry run, no modifications)
4. Cancel

Choice [1-4]:
```

**You type your choice (1-4)** - no need to remember flags!

---

## Option 1: View Report Only

**Read-only analysis**:
- Shows all issues with details
- Suggests fixes
- **Makes no changes**

```
Detailed Findings:

❌ CRITICAL: Missing test directories
   Location: Root directory
   Expected: tests/unit/, tests/integration/, tests/uat/
   Impact: Cannot run automated tests
   Fix: Choose option 2 to create

❌ CRITICAL: README.md out of sync with PROJECT.md
   PROJECT.md updated: 2 days ago
   README.md updated: 1 week ago
   Impact: Documentation misleading
   Fix: Choose option 2 to rebuild

⚠️  WARNING: Documentation files in root
   Files: GUIDE.md, ARCHITECTURE.md, RESEARCH.md
   Expected location: docs/
   Impact: Cluttered root directory
   Fix: Choose option 2 to organize
```

**When to use**:
- ✅ First assessment of project
- ✅ Periodic alignment checks
- ✅ Want to see issues without fixing

---

## Option 2: Fix Interactively (Recommended)

**Three-phase interactive fix**:

### Phase 1: Directory Structure
```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
PHASE 1: Directory Structure
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Proposed changes:
  + Create tests/unit/
  + Create tests/integration/
  + Create tests/uat/
  + Create docs/guides/

Apply Phase 1? [Y/n/q]: Y

✅ Created tests/unit/
✅ Created tests/integration/
✅ Created tests/uat/
✅ Created docs/guides/
```

### Phase 2: File Organization
```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
PHASE 2: File Organization
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Proposed moves:
  GUIDE.md → docs/guides/GUIDE.md
  ARCHITECTURE.md → docs/ARCHITECTURE.md
  RESEARCH.md → docs/research/RESEARCH.md

Apply Phase 2? [Y/n/q]: Y

✅ Moved GUIDE.md → docs/guides/
✅ Moved ARCHITECTURE.md → docs/
✅ Moved RESEARCH.md → docs/research/
```

### Phase 3: Documentation & Hooks
```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
PHASE 3: Documentation & Hooks
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Proposed changes:
  - Rebuild README.md from PROJECT.md
  - Update CHANGELOG.md
  - Install auto_format.py hook
  - Configure pre-commit hooks

Apply Phase 3? [Y/n/q]: Y

✅ Rebuilt README.md
✅ Updated CHANGELOG.md
✅ Installed hooks
✅ Configured pre-commit

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
SUMMARY
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Directories created: 4
Files moved: 3
Documentation updated: 2
Hooks installed: 2

✅ All phases completed
✅ Changes committed (abc1234)

Project now 100% aligned with PROJECT.md ✅
```

**User control at each phase**:
- Type `Y` to apply phase
- Type `n` to skip phase (move to next)
- Type `q` to quit (stop all changes)

**When to use**:
- ✅ **First time** using alignment (safest)
- ✅ Want control over each change
- ✅ Unfamiliar projects
- ✅ Review before applying

---

## Option 3: Preview Changes (Dry Run)

**Show what would change without applying**:

```
DRY RUN - No changes will be made

Would create directories:
  + tests/unit/
  + tests/integration/
  + tests/uat/
  + docs/guides/

Would move files:
  GUIDE.md → docs/guides/GUIDE.md
  ARCHITECTURE.md → docs/ARCHITECTURE.md

Would update documentation:
  README.md (rebuild from PROJECT.md)
  CHANGELOG.md (add recent commits)

Would install hooks:
  auto_format.py
  security_scan.py

To apply these changes, run again and choose option 2.
```

**When to use**:
- ✅ See what would change first
- ✅ Before interactive fix
- ✅ Sanity check

---

## Option 4: Cancel

**Exit without changes**:
- Aborts immediately
- No modifications made
- Report still available (was shown before menu)

---

## Typical Workflow

### First Time Setup

```bash
# 1. Run alignment
/align-project

# 2. See report, choose option 2 (fix interactively)
Choice [1-4]: 2

# 3. Review and approve each phase
Apply Phase 1? [Y/n/q]: Y
Apply Phase 2? [Y/n/q]: Y
Apply Phase 3? [Y/n/q]: Y

# Done! Project aligned.
```

### Periodic Checks

```bash
# Quick alignment check
/align-project

# Choose option 1 (view report only)
Choice [1-4]: 1

# Review issues, decide if fixes needed
```

### Preview Before Fixing

```bash
# See what would change
/align-project

# Choose option 3 (dry run)
Choice [1-4]: 3

# Review proposed changes

# Run again to apply
/align-project
Choice [1-4]: 2
```

---

## Safety Features

✅ **Analysis first**: Always shows what's wrong before asking what to do
✅ **Interactive approval**: Option 2 asks at each phase
✅ **Dry run available**: Option 3 shows changes without applying
✅ **Git commits**: Changes are committed (easy rollback)
✅ **Cancel anytime**: Press Ctrl+C or choose option 4

---

## Comparison to Old Commands

**Before** (complicated, hard to remember):
```bash
/align-project              # Just analysis
/align-project-safe         # Interactive fix
/align-project-dry-run      # Preview
/align-project-fix          # Auto-fix (risky!)
```

**Now** (simple, self-documenting):
```bash
/align-project              # Shows menu, you choose
```

**Benefits**:
- ✅ One command to learn
- ✅ Options shown when needed
- ✅ No flag memorization
- ✅ Clearer workflow

---

## When to Use This Command

**Run /align-project when**:
- 🆕 First time setup (option 2)
- 📊 Periodic health checks (option 1)
- 🔄 After major PROJECT.md changes (option 2)
- 🔍 Before releases (option 1)
- 👥 Onboarding new team members (option 2)

**Don't need it if**:
- Project already aligned (will show 100%)
- You just want to code (not needed every time)

---

## Troubleshooting

### "PROJECT.md not found"

```bash
# Create PROJECT.md first
/setup

# Then run alignment
/align-project
```

### "Permission denied" during phase 2 (file moves)

- Check file permissions
- Close any editors with files open
- Run with proper permissions

### "Hook installation failed"

- Verify .git/ directory exists
- Check .git/hooks/ is writable
- May need to run /setup first

---

## Related Commands

- `/setup` - Create PROJECT.md from template
- `/test` - Run tests after alignment
- `/format` - Format code after alignment

---

## Implementation

Invoke the alignment-validator agent to analyze project alignment with PROJECT.md.

The agent will:
1. Analyze project structure and alignment
2. Present interactive menu with options
3. Execute user-selected action (view, fix, preview, or cancel)

---

**Use this to analyze project health and optionally fix issues. Self-documenting menu guides you through options.**
