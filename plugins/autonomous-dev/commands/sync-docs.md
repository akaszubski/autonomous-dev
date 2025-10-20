---
description: Synchronize documentation with code changes - updates API docs, CHANGELOG, and organizes files
---

# Sync Documentation with Code

Automatically updates documentation to match code changes using the **doc-master agent**.

## Usage

```bash
# Sync all documentation
/sync-docs

# Sync after code changes (auto-detects what changed)
/sync-docs --auto

# Organize documentation files only
/sync-docs --organize

# Update API documentation only
/sync-docs --api

# Update CHANGELOG only
/sync-docs --changelog
```

## What It Does

The **doc-master agent** performs three types of documentation sync:

### 1. Filesystem Organization
- Moves .md files from root to `docs/`
- Organizes by category (guides, api, research, archive)
- Maintains clean root (only README, CHANGELOG, LICENSE, CLAUDE.md)

### 2. API Documentation Sync
- Extracts docstrings from code
- Updates API reference docs
- Syncs function signatures with documentation
- Updates code examples

### 3. CHANGELOG Updates
- Detects API changes via git diff
- Adds entries to CHANGELOG.md
- Follows Keep a Changelog format
- Groups by Added/Changed/Fixed/Deprecated

---

## When to Use

### After Code Changes
```bash
# Made changes to public API
git diff --name-only | grep "src/"

# Sync docs automatically
/sync-docs --auto
```

**Auto-detects:**
- New/modified functions
- Changed signatures
- Added/removed modules
- Breaking changes

### After Creating Documentation
```bash
# Created new documentation files
ls -1 *.md | grep -v "README\|CHANGELOG\|LICENSE\|CLAUDE"

# Organize files
/sync-docs --organize
```

**Moves files to:**
- `docs/guides/` - How-to guides
- `docs/api/` - API reference
- `docs/research/` - Research notes
- `docs/archive/` - Old summaries/audits

### Manual API Sync
```bash
# Updated function signatures
/sync-docs --api
```

**Updates:**
- Function parameter docs
- Return type docs
- Code examples
- Cross-references

### Manual CHANGELOG Update
```bash
# Need to document changes
/sync-docs --changelog
```

**Adds entries for:**
- New features (Added)
- Behavior changes (Changed)
- Bug fixes (Fixed)
- Deprecations (Deprecated)

---

## Examples

### Example 1: After Feature Implementation
```bash
# Implement feature
"Add custom learning rate parameter to trainer"

# Feature complete, sync docs
/sync-docs --auto

# Result:
# ✅ Updated docs/api/trainer.md (added learning_rate param)
# ✅ Updated examples/train.py (added parameter)
# ✅ Updated CHANGELOG.md (Added: learning_rate parameter)
```

### Example 2: Documentation Cleanup
```bash
# Multiple .md files in root
ls -1 *.md
# IMPLEMENTATION_NOTES.md
# ARCHITECTURE_SUMMARY.md
# RESEARCH_FINDINGS.md

# Organize
/sync-docs --organize

# Result:
# ✅ Moved IMPLEMENTATION_NOTES.md → docs/archive/
# ✅ Moved ARCHITECTURE_SUMMARY.md → docs/architecture/
# ✅ Moved RESEARCH_FINDINGS.md → docs/research/
```

### Example 3: Breaking Change
```bash
# Changed function signature (breaking)
git diff src/api.py
# -def train(model, data):
# +def train(model, data, *, learning_rate=1e-4):

# Update docs
/sync-docs --api --changelog

# Result:
# ✅ Updated docs/api/training.md (new parameter)
# ✅ Updated CHANGELOG.md (Changed: train() now requires learning_rate)
# ⚠️  Breaking change detected, added migration guide
```

---

## Flags

| Flag | Description | Use Case |
|------|-------------|----------|
| (none) | Full sync (organize + api + changelog) | After major changes |
| `--auto` | Auto-detect changes via git diff | After feature implementation |
| `--organize` | Filesystem organization only | Clean up .md files |
| `--api` | API documentation sync only | After function changes |
| `--changelog` | CHANGELOG update only | Manual changelog entry |

---

## How It Works

### Step 1: Detect Changes (with `--auto`)

```bash
# Check what files changed
git diff --name-only HEAD~1

# Check what functions changed
git diff src/ | grep -E "^(\+|-)def |^(\+|-)class "
```

### Step 2: Invoke doc-master Agent

The command uses the **Task tool** to invoke the doc-master agent:

```markdown
Task: Update documentation for recent code changes

Files changed:
- src/trainer.py (modified)
- src/utils.py (new)

Please:
1. Update API docs for modified functions
2. Add docs for new modules
3. Update CHANGELOG.md
4. Organize any new .md files
```

### Step 3: Agent Actions

**doc-master agent**:
- Reads changed files
- Extracts docstrings
- Updates API reference docs
- Adds CHANGELOG entries
- Moves .md files to correct locations
- Reports what was updated

### Step 4: Review & Commit

```bash
# Review changes
git diff docs/

# Commit docs with code
git add src/ docs/ CHANGELOG.md
git commit -m "feat: add custom learning rate

- Add learning_rate parameter to train()
- Update API docs and examples
- Add CHANGELOG entry"
```

---

## Configuration

Add to `.claude/settings.json`:

```json
{
  "commands": {
    "sync-docs": {
      "auto_run_after_code_changes": false,
      "update_changelog_automatically": true,
      "organize_on_doc_creation": true
    }
  }
}
```

---

## Integration with Other Commands

### With `/auto-implement`
```bash
# Auto-implement includes doc sync
/auto-implement

# Workflow:
# 1. researcher → planner → test-master → implementer
# 2. reviewer → security-auditor
# 3. doc-master (auto-runs) ← YOU ARE HERE
```

### With `/commit`
```bash
# Sync docs before committing
/sync-docs --auto
/commit
```

### With `/align-project`
```bash
# Align checks structure
/align-project

# Sync updates content
/sync-docs
```

---

## Related

- **Agent**: `.claude/agents/doc-master.md`
- **Skill**: `.claude/skills/documentation-guide.md`
- **Command**: `/align-project` (structure)
- **Command**: `/commit` (git workflow)

---

## Troubleshooting

### "No changes detected"
```bash
# Force full sync
/sync-docs --api --changelog --organize
```

### "Can't find API docs"
```bash
# Create API doc structure
mkdir -p docs/api
# Then run
/sync-docs --api
```

### "CHANGELOG format wrong"
```bash
# View current format
head -30 CHANGELOG.md

# Should follow: https://keepachangelog.com/
# doc-master will auto-fix format
```

---

**Philosophy**: Documentation should always reflect code reality. Use `/sync-docs` after every code change to maintain perfect sync.
