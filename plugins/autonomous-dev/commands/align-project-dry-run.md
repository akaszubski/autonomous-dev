---
description: Preview alignment changes without making any modifications (dry run)
---

# Align Project - Dry Run (Preview Only)

**Preview proposed changes without modifying anything**

---

## Usage

```bash
/align-project-dry-run
```

**Mode**: Preview only (no changes)
**Time**: 5-10 minutes
**Changes**: None - shows what WOULD change

---

## What This Does

Analyzes and shows proposed changes WITHOUT applying them:
- ✅ Show directories that would be created
- ✅ Show files that would be moved
- ✅ Show documentation updates
- ✅ Show hook installations
- ❌ **Does NOT make any changes**

Perfect for testing before actual alignment.

---

## Expected Output

```
DRY RUN: Previewing alignment changes (no modifications)...

┌─ Proposed Directory Changes ────────────────┐
│  + Create tests/unit/                        │
│  + Create tests/integration/                 │
│  + Create tests/uat/                         │
│  + Create docs/guides/                       │
│  + Create docs/research/                     │
└──────────────────────────────────────────────┘

┌─ Proposed File Moves ───────────────────────┐
│  GUIDE.md                                    │
│    → docs/guides/GUIDE.md                    │
│                                              │
│  ARCHITECTURE.md                             │
│    → docs/ARCHITECTURE.md                    │
│                                              │
│  RESEARCH.md                                 │
│    → docs/research/RESEARCH.md               │
└──────────────────────────────────────────────┘

┌─ Proposed Documentation Updates ────────────┐
│  README.md                                   │
│    - Rebuild from PROJECT.md                 │
│    - Update sections: Goals, Features        │
│    - Update command list (4 new)             │
│                                              │
│  CHANGELOG.md                                │
│    - Add entry for alignment changes         │
└──────────────────────────────────────────────┘

┌─ Proposed Hook Installations ───────────────┐
│  + auto_format.py (pre-commit)               │
│  + security_scan.py (pre-commit)             │
│  + auto_test.py (file-write)                 │
└──────────────────────────────────────────────┘

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
SUMMARY (DRY RUN)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Would create: 5 directories
Would move: 3 files
Would update: 2 documentation files
Would install: 3 hooks

NO CHANGES MADE - This was a preview only

To apply these changes:
  /align-project-fix          Auto-fix
  /align-project-safe         Interactive fix
  /align-project-sync         Fix + GitHub sync
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
```

---

## When to Use

- ✅ **Before first alignment** (see what will change)
- ✅ Testing alignment logic
- ✅ Reviewing impact of changes
- ✅ Before committing to auto-fix
- ✅ For documentation/demos

---

## Output Format

**Clear preview sections**:
1. Directory changes (+ create, - delete)
2. File moves (from → to)
3. Documentation updates (what will change)
4. Hook installations (which hooks)

**Color-coded**:
- 🟢 Green: Additions
- 🔵 Blue: Moves/Changes
- 🔴 Red: Deletions (rare)

---

## Next Steps

**After dry run, choose**:
- `/align-project-safe` - Interactive (recommended)
- `/align-project-fix` - Auto-fix (fast)
- `/align-project-sync` - Fix + GitHub
- `/align-project` - Analysis only (more details)

---

## Comparison

| Command | Changes | User Input | GitHub |
|---------|---------|------------|--------|
| `/align-project` | None | None | No |
| `/align-project-dry-run` | None | None | No |
| `/align-project-fix` | Yes | None | No |
| `/align-project-safe` | Yes | Required | No |
| `/align-project-sync` | Yes | Required | Yes |

---

## Related Commands

- `/align-project` - Analysis with details
- `/align-project-safe` - Interactive fix
- `/align-project-fix` - Auto-fix
- `/align-project-sync` - Fix + GitHub

---

**Use this to preview changes before committing. Completely safe - makes no modifications.**
