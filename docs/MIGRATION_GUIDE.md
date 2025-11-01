# Migration Guide - Existing Projects

**For users who already have autonomous-dev installed**

This guide helps you migrate existing projects to the new bootstrap-based installation (v3.2.2+).

---

## Do You Need to Migrate?

**Check your installation version:**

```bash
# If this file exists, you need to migrate
ls .claude/.autonomous-dev-bootstrapped
```

If the file **doesn't exist**, you're on an older installation method and should migrate.

---

## Migration Options

### Option 1: Quick Update (Recommended)

**If you already have `.claude/commands/` with autonomous-dev commands:**

```bash
# 1. Just run the bootstrap script
bash <(curl -sSL https://raw.githubusercontent.com/akaszubski/autonomous-dev/main/install.sh)

# 2. Restart Claude Code
# Cmd+Q (Mac) or Ctrl+Q (Windows/Linux)
```

**What this does:**
- ✅ Updates commands to latest versions
- ✅ Adds any new commands (like `/update-plugin`)
- ✅ Updates hooks to latest versions
- ✅ Updates templates
- ✅ Preserves your existing files (PROJECT.md, settings, etc.)
- ✅ Creates marker file (`.claude/.autonomous-dev-bootstrapped`)

**Safe?** Yes! The script only overwrites plugin files, not your custom work.

---

### Option 2: Fresh Install (Clean Slate)

**If you want to start fresh:**

```bash
# 1. Backup your current .claude directory
cp -r .claude .claude.backup.$(date +%Y%m%d)

# 2. Remove old plugin files (keep your custom files)
rm .claude/commands/{setup,auto-implement,align-project,align-claude,status,health-check,test,uninstall}.md 2>/dev/null
rm -rf .claude/hooks/*.py 2>/dev/null
rm -rf .claude/templates/* 2>/dev/null

# 3. Run bootstrap
bash <(curl -sSL https://raw.githubusercontent.com/akaszubski/autonomous-dev/main/install.sh)

# 4. Restart Claude Code
```

**Preserves:**
- ✅ Your PROJECT.md
- ✅ Your custom commands
- ✅ Your `.claude/settings.json` and `settings.local.json`
- ✅ Your `.env` file

---

### Option 3: Manual Migration (Full Control)

**If you want to see exactly what changes:**

```bash
# 1. Backup everything
cp -r .claude .claude.backup.$(date +%Y%m%d)

# 2. Download bootstrap script to review
curl -O https://raw.githubusercontent.com/akaszubski/autonomous-dev/main/install.sh
cat install.sh  # Review what it does

# 3. Run it
bash install.sh

# 4. Check what changed
diff -r .claude.backup.$(date +%Y%m%d) .claude

# 5. Restart Claude Code
```

---

## What Changes in Your Project

### Files Added/Updated

```
.claude/
├── commands/
│   ├── setup.md              ← Updated
│   ├── auto-implement.md      ← Updated
│   ├── align-project.md       ← Updated
│   ├── align-claude.md        ← Updated
│   ├── status.md              ← Updated
│   ├── health-check.md        ← Updated
│   ├── test.md                ← Updated
│   ├── uninstall.md           ← Updated
│   └── update-plugin.md       ← NEW!
│
├── hooks/
│   └── *.py                   ← Updated (30+ hooks)
│
├── templates/
│   └── *                      ← Updated
│
├── agents/
│   └── *.md                   ← Updated (19 agents)
│
└── .autonomous-dev-bootstrapped  ← NEW (marker file)
```

### Files Preserved

```
.claude/
├── PROJECT.md                 ← KEPT (if exists)
├── settings.json              ← KEPT
├── settings.local.json        ← KEPT
├── .env                       ← KEPT (if exists)
└── commands/
    └── your-custom-*.md       ← KEPT (non-plugin commands)
```

---

## Specific Project Examples

### For `realign` Project

The realign project already has bootstrap files from our earlier testing:

```bash
cd /Users/akaszubski/Documents/GitHub/realign

# Check current state
ls .claude/commands/
# Should see: autonomous-dev commands + realign's custom commands

# Update to latest
bash <(curl -sSL https://raw.githubusercontent.com/akaszubski/autonomous-dev/main/install.sh)

# Restart Claude Code
```

**Result**:
- ✅ 8 autonomous-dev commands updated
- ✅ 4 realign custom commands preserved (`check-congruence.md`, `check-health.md`, `implement.md`, `research.md`)

---

### For Projects with Custom Hooks

**If you have custom hooks in `.claude/hooks/`:**

```bash
# 1. Backup your custom hooks
mkdir -p .claude/hooks.custom
cp .claude/hooks/my_custom_*.py .claude/hooks.custom/

# 2. Run bootstrap (overwrites hooks/)
bash <(curl -sSL https://raw.githubusercontent.com/akaszubski/autonomous-dev/main/install.sh)

# 3. Restore your custom hooks
cp .claude/hooks.custom/my_custom_*.py .claude/hooks/

# 4. Update settings.json to use your custom hooks
vim .claude/settings.json
```

---

### For Projects with Modified Templates

**If you customized PROJECT.md template:**

```bash
# 1. Backup your template
cp .claude/templates/PROJECT.md .claude/templates/PROJECT.md.custom

# 2. Run bootstrap
bash <(curl -sSL https://raw.githubusercontent.com/akaszubski/autonomous-dev/main/install.sh)

# 3. Restore or merge your customizations
# Use your custom one:
cp .claude/templates/PROJECT.md.custom .claude/templates/PROJECT.md

# OR merge changes:
# (manually compare and merge)
```

---

## Verification After Migration

### 1. Check Marker File

```bash
cat .claude/.autonomous-dev-bootstrapped
# Should show: autonomous-dev-plugin
```

### 2. Verify Commands

```bash
/health-check
# Should show: Commands: 9/9 present ✅
# (8 core + new update-plugin command)
```

### 3. Test New Command

```bash
/update-plugin
# Should recognize the command and show help/usage
```

### 4. Check Settings

```bash
cat .claude/settings.json
# Verify your hooks and permissions are still there
```

---

## Troubleshooting Migration

### "Commands still missing after migration"

**Solution**: Full restart required
```bash
# Quit Claude Code completely
# Cmd+Q (Mac) or Ctrl+Q (Windows/Linux)
# Wait 5 seconds
# Reopen Claude Code
```

### "Bootstrap script fails"

**Check plugin installation**:
```bash
ls ~/.claude/plugins/marketplaces/autonomous-dev/
# If not found:
/plugin marketplace add akaszubski/autonomous-dev
/plugin install autonomous-dev
# Restart, then retry bootstrap
```

### "Lost my custom commands"

**Restore from backup**:
```bash
# List backups
ls -d .claude.backup.*

# Restore specific files
cp .claude.backup.TIMESTAMP/commands/my-custom.md .claude/commands/
```

### "Hooks not working after migration"

**Check settings**:
```bash
# Ensure hooks are configured in settings.json
cat .claude/settings.json | grep -A 10 hooks
```

**Re-run setup**:
```bash
/setup
# Choose "Automatic Hooks" option
```

---

## Rollback (If Something Goes Wrong)

### Restore from Backup

```bash
# 1. Remove current .claude
rm -rf .claude

# 2. Restore from backup
cp -r .claude.backup.TIMESTAMP .claude

# 3. Restart Claude Code
```

### Start Completely Fresh

```bash
# 1. Remove everything
rm -rf .claude

# 2. Reinstall plugin
/plugin uninstall autonomous-dev
# Restart
/plugin install autonomous-dev
# Restart

# 3. Bootstrap
bash <(curl -sSL https://raw.githubusercontent.com/akaszubski/autonomous-dev/main/install.sh)
# Restart
```

---

## Future Updates

Once migrated, use the new update workflow:

```bash
# When new plugin version released
/plugin update autonomous-dev

# Restart Claude Code

# Update your project files
/update-plugin

# Restart Claude Code
```

**Or re-run bootstrap**:
```bash
bash <(curl -sSL https://raw.githubusercontent.com/akaszubski/autonomous-dev/main/install.sh)
```

---

## FAQ

**Q: Will migration break my existing workflows?**
A: No. All existing commands, hooks, and settings are preserved.

**Q: Do I need to migrate if everything works?**
A: Not required, but recommended to get:
- New `/update-plugin` command
- Latest bug fixes in hooks
- Easier update process going forward

**Q: What if I have multiple projects?**
A: Run bootstrap in each project separately:
```bash
cd ~/project1 && bash <(curl -sSL https://..../install.sh)
cd ~/project2 && bash <(curl -sSL https://..../install.sh)
# etc.
```

**Q: Will this affect my global plugin installation?**
A: No. Global plugin at `~/.claude/plugins/marketplaces/` is unchanged. Bootstrap only copies files to project-level `.claude/`.

**Q: Can I automate this for multiple projects?**
A: Yes:
```bash
#!/bin/bash
for project in ~/projects/*/; do
    cd "$project"
    if [ -d .claude ]; then
        echo "Migrating $project..."
        bash <(curl -sSL https://raw.githubusercontent.com/akaszubski/autonomous-dev/main/install.sh)
    fi
done
```

---

## Summary

**For most users**: Just run the bootstrap script
```bash
bash <(curl -sSL https://raw.githubusercontent.com/akaszubski/autonomous-dev/main/install.sh)
```

**Safe?** Yes - preserves your custom work
**Time?** ~30 seconds
**Benefit?** Latest features + easier updates

**After migration**, use `/update-plugin` for future updates instead of manual reinstalls.
