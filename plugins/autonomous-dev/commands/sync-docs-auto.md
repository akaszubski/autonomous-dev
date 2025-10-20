---
description: Auto-detect documentation changes and sync intelligently
---

# Auto-Detect and Sync Documentation

**Intelligently detect what needs syncing and do only that**

---

## Usage

```bash
/sync-docs-auto
```

**Scope**: Auto-detected (smart sync)
**Time**: 1-5 minutes (varies by what's needed)
**Mode**: Intelligent - only syncs what changed

---

## What This Does

Analyzes what documentation needs updating:
1. Check for .md files in root → Organize if found
2. Compare code docstrings vs API docs → Sync API if outdated
3. Check commits since last CHANGELOG update → Update if needed
4. **Only runs necessary syncs** - skips what's current

---

## Expected Output

```
Auto-detecting documentation changes...

┌─ Analysis ───────────────────────────────────┐
│  ✅ Root directory: Clean (no .md files)      │
│  ⚠️  API docs: 3 functions outdated           │
│  ⚠️  CHANGELOG: 7 commits not documented      │
│  ✅ Cross-references: All valid               │
└──────────────────────────────────────────────┘

Running necessary syncs...

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
1/2: Syncing API Documentation
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

  ✅ Updated generate_token()
  ✅ Updated validate_token()
  ✅ Added refresh_token() (new)

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
2/2: Updating CHANGELOG
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

  ✅ Added 3 features
  ✅ Added 2 bug fixes
  ✅ Added 1 improvement

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
SUMMARY
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Syncs performed: 2 / 3
  ✅ File organization: Skipped (already clean)
  ✅ API docs: Updated (3 changes)
  ✅ CHANGELOG: Updated (7 commits)

Total time: 2m 15s

✅ Documentation is now synchronized
```

---

## Detection Logic

**File Organization** - Runs if:
- .md files found in root (excluding README, CHANGELOG, LICENSE, CLAUDE.md)

**API Documentation** - Runs if:
- Code docstrings modified since last API doc update
- New functions/classes added
- Function signatures changed

**CHANGELOG** - Runs if:
- Commits exist since last CHANGELOG update
- Conventional commits found (feat:, fix:, etc.)

**Skips if**:
- Everything already synchronized
- No changes detected

---

## When to Use

- ✅ **After code changes** (auto-sync related docs)
- ✅ Periodic maintenance
- ✅ Before commits (ensures docs current)
- ✅ In automated workflows
- ✅ When unsure what needs syncing

---

## Comparison

| Command | Scope | When to Use |
|---------|-------|-------------|
| `/sync-docs` | Everything | Complete sync needed |
| `/sync-docs-auto` | Auto-detect | Smart, incremental sync |
| `/sync-docs-api` | API only | After API changes |
| `/sync-docs-changelog` | CHANGELOG only | Before releases |
| `/sync-docs-organize` | Files only | Cleanup needed |

---

## Output Levels

**Minimal changes**:
```
Auto-detecting documentation changes...
✅ All documentation current (no sync needed)
```

**Some changes**:
```
Auto-detecting documentation changes...
⚠️  2 syncs needed
  1. API docs: 3 functions outdated
  2. CHANGELOG: 5 commits not documented

Running syncs... (2m 15s)
✅ Documentation synchronized
```

**Major changes**:
```
Auto-detecting documentation changes...
⚠️  All syncs needed
  1. File organization: 4 files in root
  2. API docs: 12 functions outdated
  3. CHANGELOG: 20 commits not documented

Running complete sync... (7m 30s)
✅ Documentation synchronized
```

---

## Configuration (.env)

```bash
# Auto-sync settings
DOCS_AUTO_SYNC=true                 # Enable auto-sync
DOCS_AUTO_SYNC_ON_COMMIT=true       # Auto-sync before commits
DOCS_SKIP_IF_CURRENT=true           # Skip syncs if current
```

---

## Related Commands

- `/sync-docs` - Complete sync (all)
- `/sync-docs-api` - API docs only
- `/sync-docs-changelog` - CHANGELOG only
- `/sync-docs-organize` - File organization only

---

**Use this for intelligent, incremental documentation sync. Only does what's needed.**
