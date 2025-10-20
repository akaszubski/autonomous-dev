---
description: Sync all documentation - filesystem + API docs + CHANGELOG (complete sync)
---

# Sync All Documentation

**Complete documentation synchronization with doc-master agent**

---

## Usage

```bash
/sync-docs
```

**Scope**: All documentation
**Time**: 5-10 minutes
**Agent**: doc-master (Haiku)

---

## What This Does

Complete documentation sync in three parts:

1. **Filesystem Organization**
   - Move .md files from root → `docs/`
   - Organize by category (guides, api, research)
   - Keep root clean (README, CHANGELOG, LICENSE only)

2. **API Documentation Sync**
   - Extract docstrings from code
   - Update API reference docs
   - Sync function signatures
   - Update code examples

3. **CHANGELOG Updates**
   - Detect API changes via git diff
   - Add entries to CHANGELOG.md
   - Follow Keep a Changelog format
   - Group by Added/Changed/Fixed/Deprecated

---

## Expected Output

```
Running Complete Documentation Sync...

┌─ Phase 1: Filesystem Organization ──────────┐
│  ✅ Moved 3 files to docs/                   │
│     - GUIDE.md → docs/guides/               │
│     - API.md → docs/api/                    │
│     - RESEARCH.md → docs/research/          │
│  ✅ Root directory clean                     │
└──────────────────────────────────────────────┘

┌─ Phase 2: API Documentation Sync ───────────┐
│  ✅ Scanned 45 functions                     │
│  ✅ Updated 12 API doc entries               │
│  ✅ Synced 3 code examples                   │
│  ✅ All signatures current                   │
└──────────────────────────────────────────────┘

┌─ Phase 3: CHANGELOG Updates ────────────────┐
│  ✅ Detected 5 changes since last release    │
│  ✅ Added CHANGELOG entries:                 │
│     - 2 features added                       │
│     - 1 bug fixed                            │
│     - 2 improvements                         │
│  ✅ CHANGELOG.md updated                     │
└──────────────────────────────────────────────┘

Files updated: 15
Total time: 7m 23s

✅ All documentation synchronized
```

---

## When to Use

- ✅ After API changes
- ✅ Before releases
- ✅ When docs out of sync
- ✅ In `/commit-push` (Level 3)

---

## Related Commands

- `/sync-docs-api` - API docs only
- `/sync-docs-changelog` - CHANGELOG only
- `/sync-docs-organize` - File organization only
- `/sync-docs-auto` - Auto-detect and sync

---

**Use this for complete documentation sync across all categories.**
