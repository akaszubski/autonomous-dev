# Plugin Update Workflow

**Version**: 1.0.0
**Date**: 2025-11-02
**Status**: WORKING SOLUTION

---

## How Updates Work

The autonomous-dev plugin uses a **copy-based distribution model**:

1. **Installation**: Files copied from plugin to `.claude/` (one-time)
2. **Usage**: Claude Code reads from `.claude/` (your project)
3. **Updates**: Re-copy files when plugin updates (manual)

This is necessary because Claude Code currently requires plugin components to be in the project's `.claude/` directory to be discovered.

---

## Update Workflows

### Option 1: Use /update-plugin Command (Recommended)

After updating the plugin in marketplace:

```bash
# 1. Update plugin via marketplace
/plugin update autonomous-dev

# 2. Restart Claude Code (Cmd+Q)

# 3. Update your project files
/update-plugin

# 4. Restart Claude Code again
```

**What /update-plugin does**:
- ✅ Backs up current `.claude/` directory
- ✅ Copies latest commands, hooks, templates from plugin
- ✅ Preserves your custom files
- ✅ Reports what changed

### Option 2: Re-run Bootstrap Script

```bash
# Re-run install script (overwrites with latest)
bash <(curl -sSL https://raw.githubusercontent.com/akaszubski/autonomous-dev/master/install.sh)

# Restart Claude Code
```

**When to use**: If you want a completely fresh installation.

### Option 3: Manual Update

```bash
# Copy specific components
cp ~/.claude/plugins/marketplaces/autonomous-dev/plugins/autonomous-dev/commands/*.md .claude/commands/
cp -r ~/.claude/plugins/marketplaces/autonomous-dev/plugins/autonomous-dev/hooks/* .claude/hooks/
# etc.

# Restart Claude Code
```

**When to use**: If you only want to update specific files.

---

## Update Frequency

**When should you update?**

1. **Major releases** (v3.x → v4.x)
   - New features, commands, or agents
   - Breaking changes
   - Run `/update-plugin` after updating marketplace plugin

2. **Minor releases** (v3.2 → v3.3)
   - Bug fixes in hooks or commands
   - New templates or improvements
   - Run `/update-plugin` when convenient

3. **Patch releases** (v3.2.1 → v3.2.2)
   - Critical bug fixes
   - Security patches
   - Run `/update-plugin` promptly

**Check for updates**:
```bash
# Check your installed version
cat .claude/.autonomous-dev-bootstrapped

# Check latest version
curl -s https://raw.githubusercontent.com/akaszubski/autonomous-dev/master/plugins/autonomous-dev/.claude-plugin/plugin.json | grep version
```

---

## What Gets Updated

### Always Updated
- ✅ **Commands** (`.claude/commands/*.md`)
  - New slash commands
  - Bug fixes to existing commands
  - Updated documentation

- ✅ **Hooks** (`.claude/hooks/*.py`)
  - Automation improvements
  - Bug fixes
  - New hooks

- ✅ **Templates** (`.claude/templates/*`)
  - Updated PROJECT.md template
  - New template options
  - Improved examples

- ✅ **Agents** (`.claude/agents/*.md`)
  - New specialist agents
  - Improved prompts
  - Better tool configurations

### Preserved
- ✅ **Your custom commands** (non-plugin commands)
- ✅ **Your PROJECT.md** (if it exists)
- ✅ **Your settings** (`.claude/settings.local.json`)
- ✅ **Your custom configurations**

---

## Backup & Recovery

### Automatic Backup

`/update-plugin` creates automatic backups:
```
.claude.backup.20251102_143022/
```

### Manual Backup

Before major updates:
```bash
cp -r .claude .claude.backup.manual
```

### Restore from Backup

If update causes issues:
```bash
# Remove problematic update
rm -rf .claude

# Restore backup
mv .claude.backup.TIMESTAMP .claude

# Restart Claude Code
```

---

## Development Workflow (Plugin Developers)

If you're developing the plugin itself:

### 1. Make Changes in Plugin Source
```bash
cd ~/Documents/GitHub/autonomous-dev
# Edit files in plugins/autonomous-dev/
```

### 2. Sync to Installed Plugin
```bash
python plugins/autonomous-dev/hooks/sync_to_installed.py
```

### 3. Update Test Project
```bash
cd ~/path/to/test/project
/update-plugin
```

### 4. Test Changes
```bash
# Restart Claude Code
# Test your changes
```

---

## CI/CD Considerations

For teams using the plugin in CI/CD:

### Pin to Specific Version

In `.claude/settings.json`:
```json
{
  "enabledPlugins": {
    "autonomous-dev@autonomous-dev": "3.2.1"
  }
}
```

### Version Lock File

Create `.claude/plugin-versions.lock`:
```json
{
  "autonomous-dev": {
    "version": "3.2.1",
    "hash": "9988e5a86407e72e10d978ae28dd79760845c5ba"
  }
}
```

### Automated Updates

```bash
#!/bin/bash
# update-plugins.sh

# Check for updates
CURRENT=$(cat .claude/.autonomous-dev-bootstrapped)
LATEST=$(curl -s https://api.github.com/repos/akaszubski/autonomous-dev/releases/latest | jq -r .tag_name)

if [ "$CURRENT" != "$LATEST" ]; then
    echo "Update available: $CURRENT → $LATEST"

    # Update plugin
    /plugin update autonomous-dev

    # Update files
    /update-plugin

    # Run tests
    /test
fi
```

---

## Troubleshooting

### Update Fails

**Error**: "Plugin not found"
```bash
# Reinstall plugin
/plugin marketplace add akaszubski/autonomous-dev
/plugin install autonomous-dev
# Restart, then /update-plugin
```

**Error**: "No .claude directory"
```bash
# Run bootstrap first
bash <(curl -sSL https://raw.githubusercontent.com/akaszubski/autonomous-dev/master/install.sh)
```

### Files Not Updating

**Check installed plugin version**:
```bash
cat ~/.claude/plugins/installed_plugins.json | grep -A 5 "autonomous-dev"
```

**Force refresh**:
```bash
# Uninstall
/plugin uninstall autonomous-dev

# Reinstall
/plugin install autonomous-dev

# Bootstrap again
bash <(curl -sSL https://raw.githubusercontent.com/akaszubski/autonomous-dev/master/install.sh)
```

### Commands Still Old After Update

**Restart required**:
- Must fully quit Claude Code (Cmd+Q)
- Wait 5 seconds
- Reopen

**Cache issue**:
```bash
# Clear Claude Code cache (last resort)
rm -rf ~/.claude/debug
rm -rf ~/.claude/shell-snapshots
# Restart
```

---

## Future Improvements

**Planned for v4.0**:

1. **Auto-update detection**: `/health-check` warns if updates available
2. **Selective updates**: Update only commands, or only hooks
3. **Changelog in CLI**: See what changed before updating
4. **Rollback command**: `/rollback-plugin` to previous version
5. **Update notifications**: Alert when new version released

**Long-term vision**:

Once Claude Code supports true plugin component discovery, the copy-based model won't be needed. Updates will be automatic when plugin updates.

---

## Summary

**Current workflow** (working solution):
```bash
# Initial install
/plugin install autonomous-dev → Restart → Bootstrap → Restart

# Updates
/plugin update autonomous-dev → Restart → /update-plugin → Restart
```

**Future workflow** (when Claude Code fixes discovery):
```bash
# Initial install
/plugin install autonomous-dev → Restart → Done

# Updates
/plugin update autonomous-dev → Restart → Done
```

The current solution bridges the gap between how Claude Code plugins are supposed to work and how they actually work.
