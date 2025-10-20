---
description: Analyze project alignment with PROJECT.md (read-only, no changes)
---

# Align Project - Analysis Only

**Read-only analysis of project alignment with PROJECT.md standards**

---

## Usage

```bash
/align-project
```

**Mode**: Analysis only (read-only)
**Time**: 5-10 minutes
**Changes**: None (reports findings only)

---

## What This Does

Analyzes project structure and reports alignment:
- ✅ PROJECT.md exists and is complete
- ✅ Directory structure matches standards
- ✅ Documentation organization
- ✅ Test coverage and structure
- ✅ Hook configuration
- ✅ Command availability

**No changes made** - only generates report.

---

## Expected Output

```
Analyzing project alignment with PROJECT.md...

┌─ Alignment Report ──────────────────────────┐
│                                              │
│ Overall Alignment: 75% (needs improvement)   │
│                                              │
│ ✅ PROJECT.md: Present and complete          │
│ ✅ Directory structure: Correct              │
│ ⚠️  Documentation: 3 files in root (should   │
│    be in docs/)                              │
│ ❌ Test structure: Missing tests/unit/       │
│ ⚠️  Hooks: Configured but not all active     │
│ ✅ Commands: All available                   │
│                                              │
│ Issues Found: 5                              │
│  - 2 critical (must fix)                     │
│  - 3 warnings (should fix)                   │
│                                              │
└──────────────────────────────────────────────┘

Detailed Findings:

❌ CRITICAL: Missing test directories
   - tests/unit/ not found
   - tests/integration/ not found
   Fix: Run /align-project-fix

❌ CRITICAL: README.md out of sync with PROJECT.md
   - Last PROJECT.md update: 2 days ago
   - README.md last updated: 1 week ago
   Fix: Run /align-project-fix

⚠️  WARNING: Documentation files in root
   - docs/GUIDE.md should be in docs/
   - docs/ARCHITECTURE.md should be in docs/
   - docs/RESEARCH.md should be in docs/
   Fix: Run /align-project-fix --organize

To fix issues automatically:
  /align-project-fix          Auto-fix all issues
  /align-project-safe         Interactive fix (ask first)
  /align-project-dry-run      Preview changes only
```

---

## When to Use

- ✅ Initial project assessment
- ✅ After major changes
- ✅ Periodic alignment checks
- ✅ Before using /align-project-fix

---

## Related Commands

- `/align-project-fix` - Auto-fix all issues
- `/align-project-safe` - Interactive 3-phase fix
- `/align-project-sync` - Safe fix + GitHub sync
- `/align-project-dry-run` - Preview changes only

---

**Use this to assess alignment without making changes. Safe for any project.**
