---
description: Interactive 3-phase alignment - asks before each change (recommended)
---

# Align Project - Safe Mode (Interactive)

**Interactive 3-phase alignment with user confirmation**

---

## Usage

```bash
/align-project-safe
```

**Mode**: Interactive (asks before changes)
**Time**: 15-20 minutes (includes user input)
**Changes**: Only with user approval

---

## What This Does

Three-phase interactive alignment:

**Phase 1: Directory Structure**
- Shows proposed directory changes
- Asks: "Create these directories? [Y/n]"
- Creates only with approval

**Phase 2: File Organization**
- Shows file moves (from → to)
- Asks: "Move these files? [Y/n]"
- Moves only with approval

**Phase 3: Documentation & Hooks**
- Shows documentation updates
- Shows hook installations
- Asks: "Apply these changes? [Y/n]"
- Updates only with approval

**Each phase requires confirmation** - safe for first-time use.

---

## Expected Output

```
Running Safe Mode Alignment (Interactive)...

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
PHASE 1: Directory Structure
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Proposed changes:
  + Create tests/unit/
  + Create tests/integration/
  + Create tests/uat/
  + Create docs/guides/
  + Create docs/research/

Proceed with Phase 1? [Y/n]: Y

✅ Created tests/unit/
✅ Created tests/integration/
✅ Created tests/uat/
✅ Created docs/guides/
✅ Created docs/research/

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
PHASE 2: File Organization
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Proposed moves:
  GUIDE.md → docs/guides/GUIDE.md
  ARCHITECTURE.md → docs/ARCHITECTURE.md
  RESEARCH.md → docs/research/RESEARCH.md

Proceed with Phase 2? [Y/n]: Y

✅ Moved GUIDE.md → docs/guides/
✅ Moved ARCHITECTURE.md → docs/
✅ Moved RESEARCH.md → docs/research/

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
PHASE 3: Documentation & Hooks
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Proposed changes:
  - Rebuild README.md from PROJECT.md
  - Update CHANGELOG.md
  - Install auto_format.py hook
  - Install security_scan.py hook
  - Configure pre-commit hooks

Proceed with Phase 3? [Y/n]: Y

✅ Rebuilt README.md
✅ Updated CHANGELOG.md
✅ Installed hooks
✅ Configured pre-commit

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
SUMMARY
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Directories created: 5
Files moved: 3
Documentation updated: 2
Hooks installed: 2

✅ All phases completed
✅ Changes committed (abc1234)

Project now 100% aligned with PROJECT.md ✅
```

---

## When to Use

- ✅ **First time** using alignment (recommended)
- ✅ When you want control over changes
- ✅ When reviewing proposed changes
- ✅ For unfamiliar projects

---

## User Control

**Each phase asks for confirmation**:
- Type `Y` or `y` to proceed
- Type `N` or `n` to skip phase
- Type `q` to quit (no more changes)

**You can**:
- Accept some phases, skip others
- Review changes at each step
- Stop at any point

---

## Related Commands

- `/align-project` - Analysis only (read-only)
- `/align-project-fix` - Auto-fix (no confirmation)
- `/align-project-sync` - Safe + GitHub sync ⭐ Recommended for teams
- `/align-project-dry-run` - Preview only

---

**Use this for first-time alignment or when you want control. Safest option.**
