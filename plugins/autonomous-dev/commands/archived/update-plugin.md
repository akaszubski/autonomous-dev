---
description: "[DEPRECATED] Use /sync --marketplace instead. Legacy marketplace update command."
deprecated: true
replacement: "/sync --marketplace"
---

# [DEPRECATED] Update Plugin - Use /sync --marketplace

**This command is deprecated as of v3.7.0. Use `/sync --marketplace` instead.**

---

## Migration

Old command:
```bash
/update-plugin
```

New command:
```bash
/sync --marketplace
```

**Why deprecated?** The unified `/sync` command provides:
- Smart auto-detection of sync mode
- Better integration with environment sync
- Simplified workflow for plugin development
- Consistent interface across all sync operations

---

## Original Documentation

For reference, the original `/update-plugin` documentation is preserved below.

---

# Update Plugin Files

Updates your project's `.claude/` files from the installed marketplace plugin to get latest commands, hooks, and templates.

## Usage

```bash
/update-plugin
```

## What This Does

This command re-copies files from the globally installed plugin to your project:

1. **Backs up** your current `.claude/` directory (to `.claude.backup.TIMESTAMP/`)
2. **Updates** all plugin files:
   - Commands → `.claude/commands/`
   - Hooks → `.claude/hooks/`
   - Templates → `.claude/templates/`
   - Agents → `.claude/agents/`
   - Skills → `.claude/skills/`
3. **Preserves** your custom commands and configurations
4. **Reports** what was updated

## When to Use This

Run `/update-plugin` when:
- You've updated the plugin: `/plugin update autonomous-dev`
- New features were released and you want the latest
- Bug fixes in hooks or commands
- You want to restore default files

## Safety

Your existing files are backed up before updating. If something goes wrong:

```bash
# Restore from backup
rm -rf .claude
mv .claude.backup.TIMESTAMP .claude
```

[Rest of original documentation omitted for brevity - see /sync --marketplace for current documentation]

---

**Archived**: 2025-11-08
**Replaced by**: `/sync --marketplace`
**Issue**: GitHub #44 - Unified /sync command consolidation
