---
description: Auto-fix project alignment issues (non-interactive, commits changes)
---

# Align Project - Auto-Fix

**Automatically fix alignment issues and commit changes**

---

## Usage

```bash
/align-project-fix
```

**Mode**: Auto-fix (non-interactive)
**Time**: 10-15 minutes
**Changes**: Yes - auto-fixes and commits

---

## What This Does

Automatically fixes alignment issues:
1. Create missing directories (tests/, docs/, etc.)
2. Move files to correct locations
3. Update README.md from PROJECT.md
4. Configure hooks
5. Update documentation
6. **Commit all changes**

**No user confirmation** - fixes everything automatically.

---

## Expected Output

```
Running Auto-Fix Alignment...

┌─ Phase 1: Directory Structure ──────────────┐
│  ✅ Created tests/unit/                      │
│  ✅ Created tests/integration/               │
│  ✅ Created tests/uat/                       │
│  ✅ Created docs/                            │
└──────────────────────────────────────────────┘

┌─ Phase 2: File Organization ────────────────┐
│  ✅ Moved GUIDE.md → docs/guides/            │
│  ✅ Moved ARCHITECTURE.md → docs/            │
│  ✅ Moved RESEARCH.md → docs/research/       │
└──────────────────────────────────────────────┘

┌─ Phase 3: Documentation Sync ───────────────┐
│  ✅ Rebuilt README.md from PROJECT.md        │
│  ✅ Updated CHANGELOG.md                     │
│  ✅ Synced cross-references                  │
└──────────────────────────────────────────────┘

┌─ Phase 4: Hook Configuration ───────────────┐
│  ✅ Installed auto_format.py                 │
│  ✅ Installed security_scan.py               │
│  ✅ Configured pre-commit hooks              │
└──────────────────────────────────────────────┘

Files changed: 12
Directories created: 4

✅ All fixes applied
✅ Changes committed (abc1234)

Project now 100% aligned with PROJECT.md ✅
```

---

## When to Use

- ✅ When you trust the auto-fix logic
- ✅ For standard alignment issues
- ✅ After reviewing /align-project report
- ⚠️  **Not recommended** for first time (use /align-project-safe instead)

---

## Safety

**Use with caution**:
- Makes changes without confirmation
- Moves files automatically
- Commits changes immediately

**Safer alternative**: `/align-project-safe` (asks before changes)

---

## Related Commands

- `/align-project` - Analysis only (read-only)
- `/align-project-safe` - Interactive fix (asks first) ⭐ Safer
- `/align-project-sync` - Fix + GitHub sync
- `/align-project-dry-run` - Preview only (no changes)

---

**Use this when you want fast auto-fix without interaction. For first time, use /align-project-safe.**
