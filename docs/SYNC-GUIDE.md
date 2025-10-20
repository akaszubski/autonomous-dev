# Keeping Claude Code Configurations in Sync

**Last Updated**: 2025-10-20

Complete guide to maintaining sync between plugin source, local installation, and global configs.

---

## Overview: The Three Locations

### 1. **Plugin Source** (Version Control)
```
plugins/autonomous-dev/
├── agents/       # 8 agent definitions
├── commands/     # 11 slash commands
├── skills/       # 6 core skills
├── hooks/        # 13 automation hooks
└── templates/    # PROJECT.md templates
```
**Purpose**: Source of truth, version controlled, distributed to users

### 2. **Local Installation** (Active)
```
.claude/
├── agents/       # Copied from plugin
├── commands/     # Copied from plugin
├── skills/       # Copied from plugin
├── hooks/        # Copied from plugin
├── templates/    # Copied from plugin
├── PROJECT.md    # Project-specific (not from plugin)
└── settings.local.json  # Project-specific hooks config
```
**Purpose**: Active configuration used by Claude Code

### 3. **Global Configuration** (Cross-Project)
```
~/.claude/
├── commands/     # Generic commands only
├── skills/       # Generic skills (optional)
└── CLAUDE.md     # Universal instructions
```
**Purpose**: Available across all projects

---

## Sync Workflows

### Workflow 1: Plugin Development → Local (Making Changes)

**When to use**: You're developing the plugin and want to test changes locally.

```bash
# After editing plugin source files
cd /path/to/claude-code-bootstrap

# Sync to local .claude/
./scripts/refresh-claude-settings.sh

# Verify sync
ls -1 .claude/commands/ | wc -l  # Should match plugins/autonomous-dev/commands/
```

**What it does**:
- Copies agents from `plugins/autonomous-dev/agents/` → `.claude/agents/`
- Copies commands from `plugins/autonomous-dev/commands/` → `.claude/commands/`
- Copies skills from `plugins/autonomous-dev/skills/` → `.claude/skills/`
- Copies hooks from `plugins/autonomous-dev/hooks/` → `.claude/hooks/`
- Updates are **immediate** (no Claude restart needed)

**Automated version** (optional):
```bash
# Add to git pre-commit hook
cat > .git/hooks/pre-commit << 'EOF'
#!/bin/bash
# Auto-sync before commit
./scripts/refresh-claude-settings.sh --quiet
EOF
chmod +x .git/hooks/pre-commit
```

---

### Workflow 2: Local → Plugin Source (Saving Changes)

**When to use**: You edited files in `.claude/` and want to save them to the plugin source.

```bash
# Copy changes back to plugin
cp .claude/commands/sync-docs.md plugins/autonomous-dev/commands/
cp .claude/agents/doc-master.md plugins/autonomous-dev/agents/

# Commit to version control
git add plugins/autonomous-dev/
git commit -m "feat: update doc-master agent"
```

**Manual check for drift**:
```bash
# Compare local vs plugin
diff .claude/commands/align-project.md plugins/autonomous-dev/commands/align-project.md

# If different, decide which is correct
# Option A: Plugin is correct (sync from plugin)
./scripts/refresh-claude-settings.sh

# Option B: Local is correct (copy to plugin)
cp .claude/commands/align-project.md plugins/autonomous-dev/commands/
```

---

### Workflow 3: Global → Project (Updating Global Commands)

**When to use**: You updated a command in this project and want to use it globally.

```bash
# Check if command should be global (must be generic)
cat .claude/commands/commit.md | grep -i "claude-code-bootstrap"

# If no project-specific refs, update global
cp .claude/commands/commit.md ~/.claude/commands/

# Verify it works in other projects
cd /path/to/other-project
/commit  # Should use the updated global version
```

**Important**: Only update global if command is **truly generic** (see GLOBAL-COMMANDS-GUIDE.md)

---

### Workflow 4: Project → Global (Should Rarely Happen)

**When to use**: You want to share a project-specific command globally (usually wrong approach).

```bash
# ⚠️ WARNING: Check if command is generic first
grep -E "claude-code-bootstrap|PROJECT\.md|autonomous-dev" .claude/commands/align-project.md

# If project-specific, DON'T copy to global
# Instead, install plugin in other projects:
cd /path/to/other-project
/plugin install autonomous-dev
```

---

## Automation Scripts

### Script 1: `refresh-claude-settings.sh` (Existing)

**Location**: `scripts/refresh-claude-settings.sh`

**Usage**:
```bash
# Full refresh (with output)
./scripts/refresh-claude-settings.sh

# Quiet mode (for automation)
./scripts/refresh-claude-settings.sh --quiet

# Dry run (show what would change)
./scripts/refresh-claude-settings.sh --dry-run
```

**What it syncs**:
- ✅ Agents (plugins/ → .claude/)
- ✅ Commands (plugins/ → .claude/)
- ✅ Skills (plugins/ → .claude/)
- ✅ Hooks (plugins/ → .claude/)
- ❌ PROJECT.md (never overwritten)
- ❌ settings.local.json (never overwritten)

---

### Script 2: Audit Sync Status (Create This)

Create `scripts/check-sync-status.sh`:

```bash
#!/bin/bash
# Check if local and plugin are in sync

echo "🔍 Checking sync status..."
echo ""

# Count files
PLUGIN_AGENTS=$(ls -1 plugins/autonomous-dev/agents/*.md 2>/dev/null | wc -l)
LOCAL_AGENTS=$(ls -1 .claude/agents/*.md 2>/dev/null | wc -l)

PLUGIN_COMMANDS=$(ls -1 plugins/autonomous-dev/commands/*.md 2>/dev/null | wc -l)
LOCAL_COMMANDS=$(ls -1 .claude/commands/*.md 2>/dev/null | wc -l)

PLUGIN_SKILLS=$(ls -1 plugins/autonomous-dev/skills/ 2>/dev/null | wc -l)
LOCAL_SKILLS=$(ls -1 .claude/skills/ 2>/dev/null | wc -l)

PLUGIN_HOOKS=$(ls -1 plugins/autonomous-dev/hooks/*.py 2>/dev/null | wc -l)
LOCAL_HOOKS=$(ls -1 .claude/hooks/*.py 2>/dev/null | wc -l)

# Compare
echo "Agents:   Plugin=$PLUGIN_AGENTS, Local=$LOCAL_AGENTS"
[ $PLUGIN_AGENTS -eq $LOCAL_AGENTS ] && echo "  ✅ In sync" || echo "  ⚠️  Out of sync"

echo "Commands: Plugin=$PLUGIN_COMMANDS, Local=$LOCAL_COMMANDS"
[ $PLUGIN_COMMANDS -eq $LOCAL_COMMANDS ] && echo "  ✅ In sync" || echo "  ⚠️  Out of sync"

echo "Skills:   Plugin=$PLUGIN_SKILLS, Local=$LOCAL_SKILLS"
[ $PLUGIN_SKILLS -eq $LOCAL_SKILLS ] && echo "  ✅ In sync" || echo "  ⚠️  Out of sync"

echo "Hooks:    Plugin=$PLUGIN_HOOKS, Local=$LOCAL_HOOKS"
[ $PLUGIN_HOOKS -eq $LOCAL_HOOKS ] && echo "  ✅ In sync" || echo "  ⚠️  Out of sync"

echo ""
echo "To sync: ./scripts/refresh-claude-settings.sh"
```

**Usage**:
```bash
chmod +x scripts/check-sync-status.sh
./scripts/check-sync-status.sh
```

---

### Script 3: Find Changed Files (Create This)

Create `scripts/find-changes.sh`:

```bash
#!/bin/bash
# Find files that differ between plugin and local

echo "🔍 Finding differences..."
echo ""

for file in plugins/autonomous-dev/commands/*.md; do
    filename=$(basename "$file")
    if [ -f ".claude/commands/$filename" ]; then
        if ! diff -q "$file" ".claude/commands/$filename" >/dev/null 2>&1; then
            echo "⚠️  DIFFERENT: commands/$filename"
        fi
    fi
done

for file in plugins/autonomous-dev/agents/*.md; do
    filename=$(basename "$file")
    if [ -f ".claude/agents/$filename" ]; then
        if ! diff -q "$file" ".claude/agents/$filename" >/dev/null 2>&1; then
            echo "⚠️  DIFFERENT: agents/$filename"
        fi
    fi
done

echo ""
echo "To see specific changes: diff .claude/commands/FILE plugins/autonomous-dev/commands/FILE"
```

**Usage**:
```bash
chmod +x scripts/find-changes.sh
./scripts/find-changes.sh
```

---

## Daily Workflows

### Daily Workflow 1: Normal Development

```bash
# 1. Start working
cd claude-code-bootstrap

# 2. Make changes (edit files in plugins/ or .claude/)
vim plugins/autonomous-dev/commands/sync-docs.md

# 3. Sync to local
./scripts/refresh-claude-settings.sh

# 4. Test
/sync-docs --help

# 5. Commit
git add plugins/autonomous-dev/commands/sync-docs.md
git commit -m "feat: update sync-docs command"

# 6. Continue working...
```

---

### Daily Workflow 2: Quick Fix in .claude/

```bash
# 1. Quick edit in .claude/ (testing)
vim .claude/commands/test.md

# 2. Test change
/test

# 3. If good, copy back to plugin
cp .claude/commands/test.md plugins/autonomous-dev/commands/

# 4. Commit
git add plugins/autonomous-dev/commands/test.md
git commit -m "fix: correct test command output"
```

---

### Daily Workflow 3: Update from Another Project

```bash
# Working in another project, want to bring changes here
cd /other-project

# 1. Edit command
vim .claude/commands/commit.md

# 2. Test it works
/commit

# 3. Copy to claude-code-bootstrap
cp .claude/commands/commit.md ~/claude-code-bootstrap/plugins/autonomous-dev/commands/

# 4. Go to claude-code-bootstrap and sync
cd ~/claude-code-bootstrap
./scripts/refresh-claude-settings.sh
git add plugins/autonomous-dev/commands/commit.md
git commit -m "feat: improve commit command"
```

---

## Preventing Drift

### Strategy 1: Single Source of Truth

**Rule**: `plugins/autonomous-dev/` is always the source of truth.

```bash
# ALWAYS edit in plugins/ first
vim plugins/autonomous-dev/commands/new-command.md

# Then sync to .claude/
./scripts/refresh-claude-settings.sh

# NOT the other way around (unless quick testing)
```

---

### Strategy 2: Pre-Commit Hook

Automatically sync before committing:

```bash
# Add to .git/hooks/pre-commit
#!/bin/bash
echo "🔄 Auto-syncing plugin to .claude/..."
./scripts/refresh-claude-settings.sh --quiet

# Check for differences
if ./scripts/find-changes.sh | grep -q "DIFFERENT"; then
    echo "⚠️  Warning: .claude/ has uncommitted changes different from plugin"
    echo "   Run: ./scripts/find-changes.sh to see details"
fi
```

---

### Strategy 3: Weekly Audit

Add to your weekly routine:

```bash
# Monday morning checklist
./scripts/check-sync-status.sh    # Verify counts match
./scripts/find-changes.sh         # Check for drift
grep -r "project-name" ~/.claude/commands/  # Check global contamination
```

---

## Troubleshooting

### Issue 1: "Command not found after sync"

```bash
# Check if file was copied
ls -la .claude/commands/sync-docs.md

# Check if file has correct permissions
chmod +x .claude/commands/sync-docs.md

# Try reloading Claude (close and reopen)
# Commands are loaded at startup
```

---

### Issue 2: "Changes not appearing"

```bash
# 1. Verify you edited the right file
ls -la plugins/autonomous-dev/commands/test.md
ls -la .claude/commands/test.md

# 2. Verify sync happened
./scripts/refresh-claude-settings.sh

# 3. Check for errors
diff plugins/autonomous-dev/commands/test.md .claude/commands/test.md

# 4. Force re-copy
rm .claude/commands/test.md
./scripts/refresh-claude-settings.sh
```

---

### Issue 3: "Global command overriding project command"

```bash
# Check which command is active
ls -la ~/.claude/commands/commit.md    # Global
ls -la .claude/commands/commit.md      # Project (wins)

# Project commands ALWAYS override global
# If you want global, remove from project:
rm .claude/commands/commit.md
```

---

## Best Practices

### 1. **Always Sync After Editing Plugin Source**
```bash
vim plugins/autonomous-dev/commands/new.md
./scripts/refresh-claude-settings.sh  # ← IMPORTANT!
```

### 2. **Commit Plugin Source, Not .claude/**
```bash
# DO commit
git add plugins/autonomous-dev/

# DON'T commit (these are generated)
git add .claude/commands/
git add .claude/agents/
```

### 3. **Use Separate Branches for Experiments**
```bash
# Experiment in a branch
git checkout -b experiment/new-command
vim plugins/autonomous-dev/commands/experimental.md
./scripts/refresh-claude-settings.sh
/experimental  # Test

# If good, merge
git checkout main
git merge experiment/new-command

# If bad, discard
git checkout main
git branch -D experiment/new-command
./scripts/refresh-claude-settings.sh  # Re-sync to clean state
```

### 4. **Document Non-Plugin Files**
```bash
# If you have project-specific hooks not in plugin
echo "# Project-Specific (Not in Plugin)" > .claude/hooks/README.md
echo "- custom_hook.py - Does XYZ" >> .claude/hooks/README.md
```

---

## Sync Checklist

Use this checklist before committing:

- [ ] Edited files in `plugins/autonomous-dev/` (source of truth)
- [ ] Ran `./scripts/refresh-claude-settings.sh`
- [ ] Tested changes locally (`/command-name`)
- [ ] Checked sync status (`./scripts/check-sync-status.sh`)
- [ ] No drift detected (`./scripts/find-changes.sh`)
- [ ] Committed plugin source to git
- [ ] Did NOT commit `.claude/` to git (it's generated)
- [ ] Updated documentation if needed
- [ ] Tested in clean environment (another project)

---

## Quick Reference

| Task | Command |
|------|---------|
| Sync plugin → local | `./scripts/refresh-claude-settings.sh` |
| Check sync status | `./scripts/check-sync-status.sh` |
| Find differences | `./scripts/find-changes.sh` |
| Copy local → plugin | `cp .claude/commands/FILE plugins/autonomous-dev/commands/` |
| Update global | `cp .claude/commands/FILE ~/.claude/commands/` (if generic) |
| Test command | `/command-name` |
| Verify file exists | `ls -la .claude/commands/FILE` |
| Check precedence | Project > Global > Built-in |

---

## Summary

**Golden Rules**:
1. **Plugin source is truth** - Always edit in `plugins/autonomous-dev/` first
2. **Sync immediately** - Run `./scripts/refresh-claude-settings.sh` after edits
3. **Test before commit** - Verify `/command` works
4. **Keep global minimal** - Only generic commands in `~/.claude/commands/`
5. **Audit weekly** - Run sync status checks regularly

**Files to Version Control**:
- ✅ `plugins/autonomous-dev/` (source of truth)
- ✅ `scripts/` (sync scripts)
- ✅ `docs/` (documentation)
- ❌ `.claude/` (generated, don't commit)

**Sync Flow**:
```
plugins/autonomous-dev/ → ./scripts/refresh-claude-settings.sh → .claude/ → Claude Code
(source, git)                    (copy script)                  (active)   (running)
```

---

**Related Docs**:
- [GLOBAL-COMMANDS-GUIDE.md](GLOBAL-COMMANDS-GUIDE.md) - Managing global vs project commands
- [DEVELOPMENT.md](DEVELOPMENT.md) - Development workflow
- [REFRESH-SETTINGS.md](../REFRESH-SETTINGS.md) - Refresh script details

---

**Last Updated**: 2025-10-20
