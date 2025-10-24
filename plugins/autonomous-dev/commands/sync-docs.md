---
description: Sync documentation with interactive menu (filesystem + API + CHANGELOG)
---

# Sync Documentation

**Synchronize documentation with intelligent detection and manual options**

---

## Usage

```bash
/sync-docs
```

**Time**: 1-10 minutes (depends on mode selected)
**Interactive**: Shows detection results, then presents menu

---

## How It Works

The command runs in two steps:

### Step 1: Auto-Detection (Always Runs)

Analyzes what needs syncing:
- ✅ Check for .md files in root (should be in docs/)
- ✅ Compare code docstrings vs API docs
- ✅ Check commits since last CHANGELOG update
- ✅ Detect new features/breaking changes

### Step 2: Action Menu (You Choose)

After analysis, you see:

```
┌─ Documentation Analysis ────────────────────┐
│                                              │
│ Status: Some documentation needs updating    │
│                                              │
│ ✅ Filesystem: Clean (no .md in root)        │
│ ⚠️  API docs: 3 functions outdated           │
│ ❌ CHANGELOG: 5 commits not documented       │
│                                              │
└──────────────────────────────────────────────┘

What would you like to sync?

1. Smart sync (auto-detect and sync only what changed) ← Recommended
2. Full sync (filesystem + API + CHANGELOG - everything)
3. Filesystem only (organize .md files to docs/)
4. API docs only (extract docstrings, update references)
5. CHANGELOG only (add recent commits)
6. Cancel

Choice [1-6]:
```

**You type your choice (1-6)** - no need to remember flags!

---

## Option 1: Smart Sync (Recommended)

**Intelligently syncs only what changed**:

```
Running smart sync...

Skipping filesystem (already clean)
Updating API docs (3 functions changed)...
  ✅ Updated docs/api/auth.md
  ✅ Updated docs/api/database.md
  ✅ Updated docs/api/utils.md

Updating CHANGELOG.md (5 commits)...
  ✅ Added 2 features
  ✅ Added 2 bug fixes
  ✅ Added 1 refactoring

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
SUMMARY
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Files updated: 4
Time saved: 6 minutes (vs full sync)

✅ Documentation up to date
```

**When to use**:
- ✅ Regular maintenance (after each feature)
- ✅ Quick sync before commits
- ✅ Want fastest sync possible

**Time**: 1-5 minutes (only syncs changed parts)

---

## Option 2: Full Sync

**Complete documentation refresh**:

Runs all three sync operations:

1. **Filesystem Organization**
   - Move .md files from root → `docs/`
   - Organize by category (guides, api, research)
   - Keep root clean (README, CHANGELOG, PROJECT.md, LICENSE only)

2. **API Documentation Sync**
   - Extract all docstrings from code
   - Regenerate API reference docs
   - Update all function signatures
   - Update code examples
   - Cross-reference updates

3. **CHANGELOG Updates**
   - Scan all commits since last release
   - Categorize (features, fixes, breaking, refactoring)
   - Add to CHANGELOG.md (Keep a Changelog format)
   - Update version references

```
Running full sync...

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Phase 1: Filesystem Organization
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

✅ Root directory clean (no moves needed)

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Phase 2: API Documentation
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Extracting docstrings from src/...
  ✅ Extracted 42 functions
  ✅ Extracted 12 classes
  ✅ Generated docs/api/ (8 files)

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Phase 3: CHANGELOG
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Scanning commits since v1.2.0...
  ✅ Added 5 features
  ✅ Added 3 bug fixes
  ✅ Added 1 breaking change
  ✅ Added 2 refactorings

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
SUMMARY
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Files updated: 10
CHANGELOG entries: 11

✅ Complete sync finished
```

**When to use**:
- ✅ Major releases
- ✅ After big refactoring
- ✅ First time setup
- ✅ Documentation audit

**Time**: 5-10 minutes (syncs everything)

---

## Option 3: Filesystem Only

**Organize .md files to docs/**:

Moves documentation files from root to proper locations:

```
Scanning for .md files in root...

Found 3 files to organize:
  GUIDE.md → docs/guides/GUIDE.md
  API.md → docs/api/API.md
  RESEARCH.md → docs/research/RESEARCH.md

Moving files...
  ✅ Moved GUIDE.md
  ✅ Moved API.md
  ✅ Moved RESEARCH.md

✅ Root directory clean
```

**When to use**:
- ✅ Clean up after creating docs in wrong location
- ✅ Organize repository structure
- ✅ Prepare for release

**Time**: < 30 seconds

---

## Option 4: API Docs Only

**Extract docstrings and update API references**:

```
Extracting docstrings from codebase...

Found changes:
  src/auth.py → docs/api/auth.md (3 functions changed)
  src/database.py → docs/api/database.md (1 class added)
  src/utils.py → docs/api/utils.md (2 functions removed)

Updating API documentation...
  ✅ Updated docs/api/auth.md
  ✅ Updated docs/api/database.md
  ✅ Updated docs/api/utils.md

✅ API docs synchronized
```

**When to use**:
- ✅ After changing function signatures
- ✅ Adding new public APIs
- ✅ Updating docstrings

**Time**: 2-3 minutes

---

## Option 5: CHANGELOG Only

**Update CHANGELOG.md from recent commits**:

```
Scanning commits since last CHANGELOG update...

Found 5 unreleased commits:
  feat: Add OAuth authentication (abc1234)
  fix: Resolve database connection leak (def5678)
  feat: Add export to PDF (ghi9012)
  refactor: Simplify API response format (jkl3456)
  fix: Handle null values in user input (mno7890)

Categorizing by type...
  Features: 2
  Bug fixes: 2
  Refactoring: 1

Updating CHANGELOG.md...

Added to [Unreleased] section:

### Added
- OAuth authentication support
- Export to PDF functionality

### Fixed
- Database connection leak
- Null value handling in user input

### Changed
- Simplified API response format

✅ CHANGELOG updated (5 entries)
```

**When to use**:
- ✅ Before releases
- ✅ After feature sprints
- ✅ Regular commit hygiene

**Time**: < 1 minute

---

## Option 6: Cancel

**Exit without syncing**:
- Aborts immediately
- No modifications made
- Analysis results still shown

---

## Typical Workflows

### After Each Feature

```bash
# Quick smart sync
/sync-docs
Choice [1-6]: 1

# Syncs only what changed (1-5 min)
```

### Before Release

```bash
# Full sync for completeness
/sync-docs
Choice [1-6]: 2

# Everything synchronized (5-10 min)
```

### Fix Messy Root Directory

```bash
# Organize files
/sync-docs
Choice [1-6]: 3

# Moves .md files to docs/ (< 30s)
```

---

## Safety Features

✅ **Detection first**: Always shows what needs syncing
✅ **Interactive choice**: Pick exactly what you need
✅ **Git commits**: Changes are committed (easy rollback)
✅ **Smart skip**: Option 1 skips what's already current
✅ **Cancel anytime**: Press Ctrl+C or choose option 6

---

## Comparison to Old Commands

**Before** (2 commands, confusing):
```bash
/sync-docs       # Full sync (everything)
/sync-docs-auto  # Smart sync (only changed)
# Which one should I use? 🤔
```

**Now** (1 command, self-documenting):
```bash
/sync-docs       # Shows menu, you choose
```

**Benefits**:
- ✅ One command to learn
- ✅ Options shown when needed
- ✅ Can pick specific parts (filesystem/API/CHANGELOG)
- ✅ Clearer workflow

---

## When to Use This Command

**Run /sync-docs when**:
- 📝 After adding/changing public APIs
- 🚀 Before releases (full sync)
- 🧹 Regular maintenance (smart sync)
- 📁 Files in wrong location (filesystem only)
- 📋 Need CHANGELOG update (CHANGELOG only)

**Don't need it if**:
- All docs already current (will show "✅ Up to date")
- No code changes since last sync

---

## Troubleshooting

### "No docstrings found"

- Check that functions have docstrings
- Verify source files in expected locations
- API docs require Google-style docstrings

### "CHANGELOG format invalid"

- Ensure CHANGELOG.md follows Keep a Changelog format
- Must have `## [Unreleased]` section
- Check existing format before running

### "Permission denied" moving files

- Check file permissions
- Close any editors with files open
- Verify destination directories writable

---

## Related Commands

- `/format` - Format code before extracting docstrings
- `/test` - Test after API changes
- `/commit-push` - Commit docs before syncing

---

**Use this to keep documentation synchronized with code. Smart sync for regular use, full sync for releases.**
