---
description: Sync documentation - Quick (smart sync) or Full (everything + GenAI validation)
---

# Sync Documentation

**Simplified documentation sync with smart defaults**

---

## Usage

```bash
/sync-docs
```

**Time**: 1-5 min (quick) or 5-10 min (full)
**Interactive**: Shows what needs syncing, then 3 simple choices

---

## How It Works

### Step 1: Auto-Detection (Always Runs)

Analyzes what needs syncing:
- ✅ Check for .md files in root (should be in docs/)
- ✅ Compare code docstrings vs API docs
- ✅ Check commits since last CHANGELOG update
- ✅ Detect new features/breaking changes
- ✅ Validate version consistency

### Step 2: Choose Your Path (3 Options)

After analysis, you see:

```
┌─ Documentation Analysis ────────────────────┐
│                                              │
│ Status: Some documentation needs updating    │
│                                              │
│ ✅ Filesystem: Clean (no .md in root)        │
│ ⚠️  API docs: 3 functions outdated           │
│ ❌ CHANGELOG: 5 commits not documented       │
│ ⚠️  Versions: 8 inconsistent references      │
│                                              │
└──────────────────────────────────────────────┘

What would you like to do?

1. Quick sync (fast - syncs only detected changes) ← Recommended
2. Full sync (thorough - everything + GenAI validation) ← Before releases
3. Cancel

Choice [1-3]:
```

**Simple and fast** - no complex decisions needed!

---

## Option 1: Quick Sync (Recommended)

**Intelligently syncs only what changed**:

```
Running quick sync...

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

**What it does**:
1. **Filesystem Organization** (if needed)
   - Move .md files from root → `docs/`
   - Keep root clean

2. **API Documentation Sync** (if changed)
   - Extract docstrings from code
   - Update API reference docs
   - Update function signatures

3. **CHANGELOG Updates** (if commits exist)
   - Scan commits since last release
   - Categorize by type
   - Add to CHANGELOG.md

4. **Version Consistency** (if inconsistencies found)
   - Fix version references to match VERSION file

**When to use**:
- ✅ Regular maintenance (after each feature)
- ✅ Quick sync before commits
- ✅ Want fastest sync possible

**Time**: 1-5 minutes (only syncs changed parts)

---

## Option 2: Full Sync (Before Releases)

**Complete documentation refresh with GenAI validation**:

Runs all sync operations plus bulletproof GenAI validation:

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

4. **Version Consistency Check**
   - Validate all version references match VERSION file
   - Fix any inconsistencies automatically

5. **GenAI Documentation Validation** (NEW)
   - AI-powered consistency check using Claude Sonnet 4.5
   - Detects overpromising and documentation drift
   - Provides detailed fix suggestions
   - 99%+ accuracy vs code reality

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
Phase 4: Version Consistency
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

✅ All version references consistent with v2.3.1

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Phase 5: GenAI Documentation Validation
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

🤖 Using Claude Sonnet 4.5 for validation...

  ✅ README.md: Consistent (95% confidence)
  ✅ PROJECT.md: Consistent (98% confidence)
  ✅ All documentation matches code reality

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
SUMMARY
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Files updated: 10
CHANGELOG entries: 11
GenAI validation: ✅ Pass

✅ Complete sync finished - documentation bulletproof
```

**When to use**:
- ✅ Major releases
- ✅ After big refactoring
- ✅ First time setup
- ✅ Documentation audit
- ✅ Before creating pull requests

**Time**: 5-10 minutes (syncs everything)

---

## Option 3: Cancel

**Exit without syncing**:
- Aborts immediately
- No modifications made
- Analysis results still displayed for your reference

**When to use**:
- ✅ Just wanted to see what needs syncing
- ✅ Will sync manually later
- ✅ Need to make code changes first

---

## Typical Workflows

### After Each Feature

```bash
# Quick smart sync
/sync-docs
Choice [1-3]: 1

# Done in < 2 minutes
```

### Before Major Release

```bash
# Full sync with GenAI validation
/sync-docs
Choice [1-3]: 2

# Complete validation in 5-10 minutes
```

### Just Checking Status

```bash
# See what needs syncing, then decide
/sync-docs
Choice [1-3]: 3  # Cancel after seeing analysis
```

---

## Related Commands

- `/format` - Format code before extracting docstrings
- `/test` - Test after API changes
- `/commit-push` - Commit docs after syncing

## Standalone Tools

### Unified GenAI Validator

**For all GenAI validation tasks**:

```bash
# Documentation consistency
python plugins/autonomous-dev/lib/genai_validate.py docs --full

# Version sync
python plugins/autonomous-dev/lib/genai_validate.py version-sync --check

# PROJECT.md alignment
python plugins/autonomous-dev/lib/genai_validate.py alignment --feature "Add OAuth"

# Code review
python plugins/autonomous-dev/lib/genai_validate.py code-review --diff

# Security scan
python plugins/autonomous-dev/lib/genai_validate.py security --file src/api.py
```

**See**: `docs/GENAI-VALIDATION-GUIDE.md` for complete documentation

---

## Key Improvements (v2.3.1)

**Simplification**:
- 3 options instead of 8 (62% simpler)
- Smart defaults (no complex decisions)
- Clear use cases for each option

**GenAI Integration**:
- Full sync now includes Claude Sonnet 4.5 validation
- Detects documentation drift automatically
- 99%+ accuracy vs code reality
- $0 cost on Max Plan

**Speed**:
- Quick sync: 1-5 min (only changed parts)
- Full sync: 5-10 min (everything + GenAI)

---

**Use this to keep documentation synchronized with code.**
- **Regular use**: Quick sync (Option 1)
- **Before releases**: Full sync (Option 2)
- **Max Plan**: Use full sync liberally - GenAI validation is free and bulletproof!
