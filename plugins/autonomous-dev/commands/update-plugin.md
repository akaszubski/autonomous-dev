---
name: update-plugin
description: Update plugin with version detection, backup, and rollback
version: 1.0.0
author: autonomous-dev
tags: [plugin, update, marketplace, version]
tools: [Bash]
model: sonnet
---

# Update Plugin Command

**Interactive plugin update with version detection, backup, and rollback.**

## Purpose

This command provides a safe, interactive way to update the autonomous-dev plugin (or other plugins) from the marketplace with:

- **Version detection**: Check current vs marketplace version
- **Interactive confirmation**: Confirm before updating
- **Automatic backup**: Create timestamped backup before update
- **Verification**: Verify update succeeded
- **Rollback**: Restore from backup if update fails
- **Rich feedback**: Detailed status and progress

## Usage

```bash
# Interactive update (recommended)
/update-plugin

# Check for updates only (no update performed)
/update-plugin --check-only

# Non-interactive update (for automation)
/update-plugin --yes

# Update without backup (advanced users only)
/update-plugin --yes --no-backup

# JSON output for scripting
/update-plugin --json
```

## Workflow

1. **Check for updates**: Compare project version vs marketplace version
2. **Display comparison**: Show current and new version
3. **Confirm update**: Prompt for user confirmation (unless --yes)
4. **Create backup**: Timestamped backup in /tmp (unless --no-backup)
5. **Perform update**: Sync from marketplace to project
6. **Verify update**: Check version matches expected
7. **Rollback on failure**: Restore from backup if update fails
8. **Cleanup backup**: Remove backup after successful update

## CLI Arguments

- `--check-only`: Check for updates without performing update (dry-run)
- `--yes`, `-y`: Skip confirmation prompts (non-interactive mode)
- `--auto-backup`: Create backup before update (default: enabled)
- `--no-backup`: Skip backup creation (advanced users only)
- `--verbose`, `-v`: Enable verbose logging
- `--json`: Output JSON for scripting (machine-readable)
- `--project-root PATH`: Path to project root (default: current directory)
- `--plugin-name NAME`: Name of plugin to update (default: autonomous-dev)

## Exit Codes

- `0`: Success (update performed or already up-to-date)
- `1`: Error (update failed)
- `2`: No update needed (when --check-only and update available)

## Examples

### Interactive Update (Recommended)

```bash
/update-plugin
```

Output:
```
============================================================
Plugin Update Available
============================================================
Current version:  3.7.0
New version:      3.8.0
Status:           Upgrade Available
============================================================

Do you want to proceed with the update? [y/N]: y

Creating backup...
Updating autonomous-dev...
Verifying update...

============================================================
Update Result
============================================================
Plugin updated successfully to 3.8.0
Version: 3.7.0 → 3.8.0
Backup: /tmp/autonomous-dev-backup-20251109-120000
============================================================
```

### Check for Updates Only

```bash
/update-plugin --check-only
```

Output:
```
============================================================
Version Check
============================================================
Project version:     3.7.0
Marketplace version: 3.8.0
Status:              Upgrade Available
============================================================

Update available.
```

### Non-Interactive Update

```bash
/update-plugin --yes
```

### JSON Output for Scripting

```bash
/update-plugin --json
```

Output:
```json
{
  "success": true,
  "updated": true,
  "message": "Plugin updated successfully to 3.8.0",
  "old_version": "3.7.0",
  "new_version": "3.8.0",
  "backup_path": "/tmp/autonomous-dev-backup-20251109-120000",
  "rollback_performed": false,
  "details": {
    "files_updated": 15
  }
}
```

## Security

All operations are security-validated:

- **CWE-22**: Path traversal prevention (all paths validated)
- **CWE-59**: Symlink resolution (reject symlinks outside whitelist)
- **CWE-732**: Backup permissions (user-only, 0o700)
- **CWE-778**: Audit logging (all operations logged to security audit)

## Rollback Behavior

If update fails at any point:

1. **Verification fails**: Automatic rollback to backup
2. **Sync fails**: Automatic rollback to backup
3. **Unexpected error**: Automatic rollback to backup

Rollback restores:
- All plugin files (commands, hooks, agents, skills)
- Original plugin.json with previous version
- Original directory structure

## Implementation

Invoke the Python CLI script:

```bash
python {{pluginDir}}/lib/update_plugin.py "$@"
```

## Related

- `/sync` - Manual sync from marketplace to project
- `/health-check` - Check plugin integrity and version
- See `lib/plugin_updater.py` for implementation details
- See `lib/update_plugin.py` for CLI implementation

## Notes

- **Restart required**: After updating, exit and restart Claude Code (Cmd+Q or Ctrl+Q) for changes to take effect
- **Backup location**: Backups are created in system temp directory (/tmp or equivalent)
- **Backup cleanup**: Backups are automatically removed after successful update
- **Safe by default**: Backup is always created unless explicitly disabled with --no-backup
- **Interactive by default**: Requires user confirmation unless --yes is provided
