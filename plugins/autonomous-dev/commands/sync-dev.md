---
description: Sync local plugin changes to installed location for testing (developer command)
---

# Sync Dev Changes - Developer Testing Command

**Developer command** - Syncs local plugin development changes to the installed plugin location so you can test changes as users would see them.

## Usage

```bash
/sync-dev
```

**Time**: < 2 seconds
**Scope**: Copies all plugin files from development to installed location

## What This Does

Copies local development files to `~/.claude/plugins/marketplaces/.../autonomous-dev/`:

1. **agents/** - All 8 specialist agents
2. **skills/** - All core skills
3. **commands/** - All slash commands
4. **hooks/** - All automation hooks
5. **scripts/** - All utility scripts
6. **templates/** - All project templates
7. **docs/** - All documentation
8. **README.md, CHANGELOG.md** - Root documentation

## Workflow

```bash
# 1. Make changes to plugin files
vim plugins/autonomous-dev/agents/implementer.md

# 2. Sync to installed location
/sync-dev

# 3. Restart Claude Code (REQUIRED!)
# Press Cmd+Q (Mac) or Ctrl+Q (Windows/Linux)

# 4. Test your changes
/health-check    # Verify plugin loaded correctly
```

## When to Use

**Essential for plugin development:**
- ✅ Testing agent changes
- ✅ Testing command changes
- ✅ Testing hook changes
- ✅ Testing skill updates
- ✅ Validating user experience

**Not needed for:**
- ❌ Regular plugin usage
- ❌ Documentation-only changes (unless testing rendering)
- ❌ Changes to tests/ or docs/dev/

## Output Example

```
🔍 Finding installed plugin location...
✅ Found installed plugin at: ~/.claude/plugins/marketplaces/claude-code-bootstrap/plugins/autonomous-dev

📁 Source: /Users/you/dev/autonomous-dev/plugins/autonomous-dev
📁 Target: /Users/you/.claude/plugins/marketplaces/.../autonomous-dev

✅ Synced agents/ (8 files)
✅ Synced skills/ (14 files)
✅ Synced commands/ (7 files)
✅ Synced hooks/ (8 files)
✅ Synced scripts/ (3 files)
✅ Synced templates/ (2 files)
✅ Synced docs/ (15 files)
✅ Synced README.md
✅ Synced CHANGELOG.md

✅ Successfully synced 59 items to installed plugin

⚠️  RESTART REQUIRED
   Claude Code must be restarted to pick up changes:
   1. Save your work
   2. Quit Claude Code (Cmd+Q or Ctrl+Q)
   3. Restart Claude Code
```

## Dry Run Mode

Preview what would be synced without actually syncing:

```bash
python plugins/autonomous-dev/scripts/sync_to_installed.py --dry-run
```

## Troubleshooting

**"Could not find installed plugin"**
```bash
# Install the plugin first
/plugin marketplace add akaszubski/autonomous-dev
/plugin install autonomous-dev
# Restart Claude Code
# Then try /sync-dev again
```

**Changes not visible after sync**
- Did you restart Claude Code? (Required!)
- Check that sync completed successfully
- Try `/health-check` to verify component count

**Want to test fresh install**
```bash
# Uninstall
/plugin uninstall autonomous-dev
# Restart Claude Code

# Reinstall (pulls from git, not local)
/plugin install autonomous-dev
# Restart Claude Code
```

## Related Commands

- `/health-check` - Verify plugin components loaded correctly
- `/setup` - Configure plugin hooks and templates
- `/plugin update autonomous-dev` - Update from git (not local changes)

---

**Run the sync script to copy local changes to installed plugin location.**

```bash
python "$(dirname "$0")/../scripts/sync_to_installed.py"
```
