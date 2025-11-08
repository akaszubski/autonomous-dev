# GenAI-Powered Sync Script

**Version**: v3.7.0 (GitHub Issue #47)
**Status**: Active
**Location**: `plugins/autonomous-dev/hooks/sync_to_installed.py`

## Overview

The sync script now includes **GenAI-powered orphan detection** to intelligently identify and clean up files that exist in the installed plugin location but not in the development directory.

## Features

### 1. Orphan Detection

Automatically detects files in the installed location that don't exist in your dev directory:

```bash
python plugins/autonomous-dev/hooks/sync_to_installed.py --detect-orphans
```

**Output Example**:
```
🔍 Scanning for orphaned files...

⚠️  Found 1 orphaned file(s):

📂 COMMANDS:
  - commands/dev-sync.md
    Reason: Likely renamed to 'sync.md'
```

### 2. GenAI Reasoning

The script analyzes orphaned files and provides human-readable explanations:

**Detected Patterns**:
- **Renamed files**: "Likely renamed to 'sync.md'"
- **Consolidated commands**: "Likely consolidated into 'sync.md'"
- **Deprecated files**: "Deprecated - replaced by unified /sync command"
- **Moved files**: "Moved to commands/ directory"
- **Removed files**: "Removed from source (no longer needed)"

**Algorithm**:
1. Check for similar filenames in source directory (partial match)
2. Check for deprecated patterns (known deprecations)
3. Check if file moved to different directory
4. Default to "removed from source"

### 3. Interactive Cleanup

Safely remove orphaned files with confirmation:

```bash
# Interactive mode (prompts for confirmation)
python plugins/autonomous-dev/hooks/sync_to_installed.py --cleanup

# Non-interactive mode (auto-confirm)
python plugins/autonomous-dev/hooks/sync_to_installed.py --cleanup -y
```

**Safety Features**:
- Creates backup before deletion
- Shows reasoning for each orphan
- Prompts for confirmation (unless `-y` flag)
- Reports success/failure for each file

### 4. Auto-Detection After Sync

After every sync, the script automatically checks for orphans:

```bash
python plugins/autonomous-dev/hooks/sync_to_installed.py

# Output:
✅ Successfully synced 151 items to installed plugin

🔍 Checking for orphaned files...
⚠️  Found 1 orphaned file(s)
   Run with --detect-orphans to see details and clean up
```

## Usage Modes

### Normal Sync (Default)

```bash
python plugins/autonomous-dev/hooks/sync_to_installed.py
```

**What it does**:
1. Syncs dev files to installed location
2. Auto-detects orphans (non-intrusive)
3. Reminds you to restart Claude Code

### Dry Run (Preview)

```bash
python plugins/autonomous-dev/hooks/sync_to_installed.py --dry-run
```

**What it does**:
- Shows what would be synced
- Doesn't actually sync files
- Useful for testing

### Detect Orphans

```bash
python plugins/autonomous-dev/hooks/sync_to_installed.py --detect-orphans
```

**What it does**:
1. Scans for orphaned files
2. Shows GenAI reasoning for each orphan
3. Prompts to clean up (interactive)

### Cleanup Orphans

```bash
# Interactive (prompts for confirmation)
python plugins/autonomous-dev/hooks/sync_to_installed.py --cleanup

# Non-interactive (auto-confirm)
python plugins/autonomous-dev/hooks/sync_to_installed.py --cleanup -y

# Dry run (preview cleanup)
python plugins/autonomous-dev/hooks/sync_to_installed.py --cleanup --dry-run
```

**What it does**:
1. Detects orphaned files
2. Creates backup in `autonomous-dev.backup.YYYYMMDD_HHMMSS/`
3. Removes orphaned files
4. Reports results

## Command Reference

```bash
# Basic sync
python plugins/autonomous-dev/hooks/sync_to_installed.py

# Preview sync
python plugins/autonomous-dev/hooks/sync_to_installed.py --dry-run

# Detect orphans
python plugins/autonomous-dev/hooks/sync_to_installed.py --detect-orphans

# Clean up orphans (interactive)
python plugins/autonomous-dev/hooks/sync_to_installed.py --cleanup

# Clean up orphans (non-interactive)
python plugins/autonomous-dev/hooks/sync_to_installed.py --cleanup -y

# Preview cleanup
python plugins/autonomous-dev/hooks/sync_to_installed.py --cleanup --dry-run
```

## Backup System

### Automatic Backups

Before removing orphaned files, the script creates a timestamped backup:

```
~/.claude/plugins/marketplaces/autonomous-dev/plugins/
  autonomous-dev.backup.20251108_085259/
    commands/
      dev-sync.md
```

### Restore from Backup

If you need to restore orphaned files:

```bash
# Find backups
ls ~/.claude/plugins/marketplaces/autonomous-dev/plugins/ | grep backup

# Restore specific file
cp ~/.claude/plugins/marketplaces/autonomous-dev/plugins/autonomous-dev.backup.YYYYMMDD_HHMMSS/commands/file.md \
   ~/.claude/plugins/marketplaces/autonomous-dev/plugins/autonomous-dev/commands/
```

## Security

### Path Validation (3-Layer Defense)

The script uses the same security validation as other plugin scripts:

1. **NULL Validation**: Checks for missing/empty paths
2. **Symlink Detection**: Rejects symlinks (before and after resolution)
3. **Whitelist Validation**: Ensures paths are within `.claude/plugins/`

See `find_installed_plugin_path()` docstring for detailed security design.

### Backup Safety

- Backups created in sibling directory (not overwritten)
- Timestamped to prevent collisions
- Preserves file metadata (permissions, timestamps)

## Examples

### Example 1: Normal Workflow

```bash
# Make changes to plugin
vim plugins/autonomous-dev/commands/sync.md

# Sync to installed location
python plugins/autonomous-dev/hooks/sync_to_installed.py

# Output:
✅ Successfully synced 151 items to installed plugin
🔍 Checking for orphaned files...
✅ No orphaned files detected

# Restart Claude Code
# (Cmd+Q on Mac, Ctrl+Q on Linux/Windows)
```

### Example 2: Cleanup Workflow

```bash
# Detect orphans
python plugins/autonomous-dev/hooks/sync_to_installed.py --detect-orphans

# Output:
⚠️  Found 2 orphaned file(s):

📂 COMMANDS:
  - commands/dev-sync.md
    Reason: Deprecated - replaced by unified /sync command
  - commands/sync-dev.md
    Reason: Deprecated - replaced by unified /sync command

# Clean up (interactive)
python plugins/autonomous-dev/hooks/sync_to_installed.py --cleanup
# [Prompts for confirmation]

# Or clean up (non-interactive)
python plugins/autonomous-dev/hooks/sync_to_installed.py --cleanup -y

# Output:
💾 Creating backup...
✅ Backup created at: autonomous-dev.backup.20251108_085259
🗑️  Removing orphaned files...
  ✅ Removed: commands/dev-sync.md
  ✅ Removed: commands/sync-dev.md
✅ Cleanup complete - 2 file(s) removed
```

### Example 3: Dry Run Preview

```bash
# Preview cleanup without actually removing files
python plugins/autonomous-dev/hooks/sync_to_installed.py --cleanup --dry-run

# Output:
⚠️  Found 2 orphaned file(s):
📂 COMMANDS:
  - commands/dev-sync.md
    Reason: Deprecated - replaced by unified /sync command
  - commands/sync-dev.md
    Reason: Deprecated - replaced by unified /sync command

🔍 DRY RUN - No files will be removed
```

## Troubleshooting

### "EOF when reading a line"

**Cause**: Script tried to prompt for input in non-interactive environment

**Solution**: Use `-y` flag for non-interactive mode:
```bash
python plugins/autonomous-dev/hooks/sync_to_installed.py --cleanup -y
```

### "Could not find installed autonomous-dev plugin"

**Cause**: Plugin not installed or `installed_plugins.json` missing

**Solution**: Install plugin first:
```bash
/plugin marketplace add akaszubski/autonomous-dev
/plugin install autonomous-dev
# Restart Claude Code
```

### Orphans Not Detected

**Cause**: Files exist in both source and target (not orphans)

**Solution**: This is expected. Orphans are files that exist ONLY in the installed location.

### Backup Not Found

**Cause**: Backup created in parent directory, not plugin directory

**Solution**: Check parent directory:
```bash
ls ~/.claude/plugins/marketplaces/autonomous-dev/plugins/ | grep backup
```

## Integration

### With `/sync` Command

The `/sync` command can integrate orphan detection:

```bash
# In .claude/commands/sync.md
python plugins/autonomous-dev/hooks/sync_to_installed.py --detect-orphans --cleanup -y
```

### With Pre-Commit Hook

Auto-detect orphans before commits:

```python
# In .git/hooks/pre-commit
result = subprocess.run([
    "python",
    "plugins/autonomous-dev/hooks/sync_to_installed.py",
    "--detect-orphans",
    "--dry-run"
], capture_output=True, text=True)

if "Found" in result.stdout:
    print("⚠️  Orphaned files detected - run --cleanup to fix")
```

## Limitations

### Current Limitations

1. **Only detects file-level orphans**: Doesn't detect orphaned directories
2. **Pattern matching only**: GenAI reasoning is heuristic-based
3. **No undo**: Once deleted, must restore from backup
4. **Manual confirmation**: Requires restart for changes to take effect

### Future Enhancements

1. **True GenAI reasoning**: Use Claude API for deeper analysis
2. **Auto-restart**: Restart Claude Code after cleanup
3. **Git integration**: Show git history for orphaned files
4. **Similarity scoring**: Show confidence level for rename detection

## Related Documentation

- [Unified /sync Command](../CHANGELOG.md#v370---2025-11-08) - GitHub Issue #47
- [Security Hardening](./SECURITY.md) - Path validation and security
- [Plugin Development](./DEVELOPMENT.md) - Plugin development workflow

## Changelog

**v3.7.0** (2025-11-08) - GitHub Issue #47
- Added GenAI-powered orphan detection
- Added smart reasoning for why files are orphaned
- Added interactive cleanup with backup
- Added auto-detection after sync
- Added `-y` flag for non-interactive mode
- Added `--detect-orphans` and `--cleanup` flags

**v3.2.3** (2025-11-03) - GitHub Issue #45
- Added 3-layer path validation (symlink + whitelist)
- Added security documentation

**v3.0.0** (2025-11-01)
- Initial sync script implementation
