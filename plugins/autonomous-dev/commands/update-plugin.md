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
- `--activate-hooks`: Automatically activate hooks after update (default: enabled on first install, prompted on update)
- `--no-activate-hooks`: Skip hook activation (manual setup required)

## Exit Codes

- `0`: Success (update performed or already up-to-date)
- `1`: Error (update failed)
- `2`: No update needed (when --check-only and update available)

## Hook Activation (Phase 2.5 - Turnkey Updates)

**Automatic hook activation** makes plugin updates turnkey - just update and hooks are ready to use.

### First Install vs Update Behavior

**First Install** (settings.json doesn't exist):
- Hooks are automatically activated
- No prompts (safe default)
- Settings file created with all hooks enabled
- Example: Initial `/update-plugin` after fresh install

**Update** (settings.json already exists):
- Interactive prompt asks to activate hooks (if not using --yes or --activate-hooks)
- Existing customizations are preserved (merge, not overwrite)
- Only new hooks are added (doesn't remove existing hooks)
- Example: Running `/update-plugin` on existing installation

### Hook Activation Flags

**Enable hook activation** (default):
```bash
/update-plugin                    # Interactive, prompts on update
/update-plugin --yes --activate-hooks   # Non-interactive, activates hooks
/update-plugin --yes              # Non-interactive, auto-activates (default behavior)
```

**Disable hook activation**:
```bash
/update-plugin --no-activate-hooks    # Skip hook activation (manual setup required)
/update-plugin --yes --no-activate-hooks   # Non-interactive, no hooks
```

### What Gets Activated

When hooks are activated, `/update-plugin` configures in `.claude/settings.json`:
- Hook lifecycle events (UserPromptSubmit, SubagentStop, etc.)
- Hook execution list (which hooks run on each event)
- Preserves existing customizations if updating

Example activation:
```json
{
  "hooks": {
    "PrePush": ["auto_test.py", "security_scan.py"],
    "SubagentStop": ["log_agent_completion.py", "auto_update_project_progress.py"]
  }
}
```

### Troubleshooting Hook Activation

**Hooks not activating on first install**:
- Check that settings.json was created: `ls -la .claude/settings.json`
- Verify permissions: `ls -la .claude/` should show readable/writable directory
- Manual activation: Run `/setup` to manually configure hooks

**Hooks not activating on update**:
- Use `--activate-hooks` flag: `/update-plugin --yes --activate-hooks`
- Or use interactive mode: `/update-plugin` (without --yes)
- Check existing settings: `cat .claude/settings.json` to see current hooks

**Activation failed, but update succeeded**:
- Don't worry! Hook activation is non-blocking (update succeeds even if activation fails)
- Manual fix: Run `/setup` to configure hooks manually
- Or: Use `--yes --activate-hooks` to retry activation
- Or: Edit `.claude/settings.json` directly (see `docs/SETTINGS.md`)

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
Hook Activation
============================================================
Activating hooks from updated plugin...
Hooks activated: auto_test.py, security_scan.py, auto_format.py
Settings saved to .claude/settings.json
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
  "hooks_activated": true,
  "hooks_added": 3,
  "details": {
    "files_updated": 15,
    "hooks": ["auto_test.py", "security_scan.py", "auto_format.py"],
    "settings_path": "/path/to/project/.claude/settings.json"
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
- `/setup` - Manual hook configuration (alternative to auto-activation)
- See `lib/plugin_updater.py` for implementation details
- See `lib/update_plugin.py` for CLI implementation
- See `lib/hook_activator.py` for hook activation logic

## Notes

- **Restart required**: After updating, exit and restart Claude Code (Cmd+Q or Ctrl+Q) for changes to take effect
- **Backup location**: Backups are created in system temp directory (/tmp or equivalent)
- **Backup cleanup**: Backups are automatically removed after successful update
- **Safe by default**: Backup is always created unless explicitly disabled with --no-backup
- **Interactive by default**: Requires user confirmation unless --yes is provided
- **Hook activation**: Automatically enabled on first install; prompted on updates (unless --yes or explicit flags)
- **Hook customizations preserved**: When updating, existing hook settings are merged with new hooks (not overwritten)
- **Non-blocking activation**: If hook activation fails, update still succeeds (activation is optional enhancement)
