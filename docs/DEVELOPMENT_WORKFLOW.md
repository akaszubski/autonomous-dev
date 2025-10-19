# Development Workflow - Plugin Development & Testing

**Purpose**: How to develop, test, and sync the autonomous-dev plugin while dogfooding it on this repository.

**Last Updated**: 2025-10-20

---

## Understanding the Setup

### Three Layers

```
1. SOURCE CODE (what you edit)
   plugins/autonomous-dev/
   ├── agents/           ← Edit here
   ├── skills/           ← Edit here
   ├── commands/         ← Edit here
   └── templates/        ← Edit here

2. LOCAL INSTALL (what Claude Code uses)
   .claude/
   ├── agents/           ← Used by Claude Code
   ├── skills/           ← Used by Claude Code
   ├── commands/         ← Used by Claude Code
   ├── templates/        ← Used by Claude Code
   ├── PROJECT.md        ← Your customization (not synced)
   └── settings.local.json ← Your customization (not synced)

3. GITHUB (what users fetch)
   https://github.com/akaszubski/claude-code-bootstrap
   └── plugins/autonomous-dev/  ← Users install from here
```

### The Sync Problem

**Problem**: When you edit `plugins/autonomous-dev/agents/orchestrator.md`, Claude Code still uses the old version in `.claude/agents/orchestrator.md`

**Solution**: Run sync script to copy source → local install

---

## Development Workflow

### Workflow A: Edit → Sync → Test → Commit (Recommended)

**Use this for rapid iteration**:

```bash
# 1. Edit source code
vim plugins/autonomous-dev/agents/orchestrator.md

# 2. Sync to local install
./scripts/sync-plugin.sh

# 3. Test in Claude Code
# (orchestrator now uses your updated code)

# 4. If it works, commit source
git add plugins/autonomous-dev/agents/orchestrator.md
git commit -m "feat: improve orchestrator alignment validation"
git push origin master

# 5. Users get update via /plugin update autonomous-dev
```

**Advantages**:
- ✅ Test changes immediately
- ✅ No reinstall needed
- ✅ Preserves local customizations (PROJECT.md, settings)
- ✅ Fast iteration

---

### Workflow B: Commit → GitHub → Reinstall (Full E2E Test)

**Use this for final validation before release**:

```bash
# 1. Edit and commit source
vim plugins/autonomous-dev/agents/orchestrator.md
git add plugins/autonomous-dev/
git commit -m "feat: improve orchestrator"
git push origin master

# 2. Remove local install
rm -rf .claude/agents .claude/skills .claude/commands .claude/templates

# 3. Fetch from GitHub (like users do)
cd /tmp
git clone https://github.com/akaszubski/claude-code-bootstrap.git
cd claude-code-bootstrap
cp -r plugins/autonomous-dev/agents /path/to/project/.claude/
cp -r plugins/autonomous-dev/skills /path/to/project/.claude/
cp -r plugins/autonomous-dev/commands /path/to/project/.claude/
cp -r plugins/autonomous-dev/templates /path/to/project/.claude/

# 4. Test (exactly as users experience it)
```

**Advantages**:
- ✅ Tests real user experience
- ✅ Validates GitHub integration
- ✅ Catches path issues
- ✅ Ensures .gitignore works

**When to use**: Before tagging a release

---

## Quick Reference

### Daily Development

```bash
# Make changes
vim plugins/autonomous-dev/agents/orchestrator.md

# Sync and test
./scripts/sync-plugin.sh
# Test in Claude Code

# Commit when satisfied
git add plugins/autonomous-dev/
git commit -m "feat: your change"
git push
```

### Before Release

```bash
# 1. Update version
vim plugins/autonomous-dev/.claude-plugin/plugin.json
# Change: "version": "2.0.0" → "2.1.0"

# 2. Update CHANGELOG
vim CHANGELOG.md
# Add new version section

# 3. Full E2E test (Workflow B above)

# 4. Tag release
git tag v2.1.0
git push origin v2.1.0

# 5. Users update via:
# /plugin update autonomous-dev
```

---

## What Gets Synced vs Preserved

### Synced (Source → Local)
- ✅ `agents/` - All agent definitions
- ✅ `skills/` - All skill definitions
- ✅ `commands/` - All slash commands
- ✅ `templates/` - All templates (including PROJECT.md template)

### Preserved (Local Only)
- ✅ `.claude/PROJECT.md` - Your project-specific goals
- ✅ `.claude/settings.local.json` - Your hooks and permissions
- ✅ `.claude/CLAUDE.md` - Your project instructions (if exists)

### Why This Matters

**Example**:
- You have custom PROJECT.md defining YOUR goals
- You edit `plugins/autonomous-dev/templates/PROJECT.md` (the generic template)
- Run `./scripts/sync-plugin.sh`
- Result: Template updates, but YOUR PROJECT.md is unchanged ✅

---

## Troubleshooting

### Issue: Changes Not Showing Up

**Symptom**: Edited agent, but Claude Code uses old behavior

**Diagnosis**:
```bash
# Check if local install is stale
diff plugins/autonomous-dev/agents/orchestrator.md .claude/agents/orchestrator.md
```

**Fix**:
```bash
./scripts/sync-plugin.sh
```

---

### Issue: Sync Script Fails

**Symptom**: Permission denied or file not found

**Diagnosis**:
```bash
# Check source exists
ls plugins/autonomous-dev/

# Check script is executable
ls -la scripts/sync-plugin.sh
```

**Fix**:
```bash
chmod +x scripts/sync-plugin.sh
./scripts/sync-plugin.sh
```

---

### Issue: Lost Custom PROJECT.md

**Symptom**: After sync, PROJECT.md is generic template

**Why**: You manually copied templates over

**Prevention**: Sync script doesn't overwrite `.claude/PROJECT.md` ✅

**Recovery**:
```bash
# Check git history
git log --all --full-history -- .claude/PROJECT.md

# Restore from commit
git show <commit>:.claude/PROJECT.md > .claude/PROJECT.md
```

---

## Git Workflow Integration

### .gitignore Setup

```bash
# Installed components (gitignored)
.claude/agents/
.claude/skills/
.claude/commands/
.claude/templates/

# Local customizations (committed)
.claude/PROJECT.md
.claude/settings.local.json
```

**Why**:
- Installed components come from `plugins/`, no need to duplicate in git
- Customizations are project-specific, should be committed

---

## Team Workflow

### Scenario: Multiple Developers

**Developer A**:
```bash
# Edit orchestrator
vim plugins/autonomous-dev/agents/orchestrator.md
./scripts/sync-plugin.sh
git commit -m "feat: improve orchestrator"
git push
```

**Developer B**:
```bash
# Pull changes
git pull origin master

# Sync to local install
./scripts/sync-plugin.sh

# Now has Developer A's changes
```

**Key**: Everyone runs `sync-plugin.sh` after pulling

---

## Testing Checklist

Before pushing changes:

- [ ] Run `./scripts/sync-plugin.sh`
- [ ] Test in Claude Code (does it work?)
- [ ] Check CHANGELOG.md updated
- [ ] Verify version bumped (if needed)
- [ ] Run automated tests: `./scripts/test-installation.sh`
- [ ] Commit source: `git add plugins/autonomous-dev/`
- [ ] Push: `git push origin master`

Before release:

- [ ] Full E2E test (Workflow B)
- [ ] Tag version: `git tag v2.x.x`
- [ ] Push tag: `git push origin v2.x.x`
- [ ] Update marketplace listing

---

## Advanced: Watching for Changes

For continuous development, you can watch for file changes:

```bash
# Install fswatch (macOS)
brew install fswatch

# Watch source directory
fswatch -o plugins/autonomous-dev/ | while read; do
  echo "Changes detected, syncing..."
  ./scripts/sync-plugin.sh
done
```

**Use case**: Edit agent files, auto-sync on save

---

## Quick Command Reference

```bash
# Development cycle
vim plugins/autonomous-dev/agents/orchestrator.md
./scripts/sync-plugin.sh
# Test in Claude Code
git add plugins/autonomous-dev/ && git commit -m "feat: update" && git push

# Check sync status
diff -r plugins/autonomous-dev/agents/ .claude/agents/

# Full reinstall (E2E test)
rm -rf .claude/agents .claude/skills .claude/commands .claude/templates
./scripts/sync-plugin.sh

# Validate installation
./scripts/test-installation.sh
```

---

**Last Updated**: 2025-10-20
