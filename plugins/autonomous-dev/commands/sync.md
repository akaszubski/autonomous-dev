---
description: Unified sync command - smart context detection for environment, marketplace, and plugin development
argument_hint: "Optional flags: --env, --marketplace, --plugin-dev, --all"
---

# Sync - Unified Synchronization Command

**Smart context-aware sync with automatic mode detection**

The unified `/sync` command replaces `/sync-dev` and `/update-plugin` with intelligent context detection. It automatically detects whether you're syncing your development environment, updating from the marketplace, or working on plugin development.

---

## Quick Start

```bash
# Auto-detect and sync (recommended)
/sync

# Force specific mode
/sync --env              # Environment sync only
/sync --marketplace      # Marketplace update only
/sync --plugin-dev       # Plugin dev sync only
/sync --all              # Execute all modes
```

**Time**: 30-90 seconds (depends on mode)
**Interactive**: Shows detected mode, asks for confirmation
**Smart Detection**: Analyzes project structure to determine sync mode

---

## Auto-Detection Logic

The command automatically detects the appropriate sync mode:

### Detection Priority (highest to lowest):

1. **Plugin Development** → `--plugin-dev`
   - Detected when: `plugins/autonomous-dev/plugin.json` exists
   - Action: Sync plugin files to local `.claude/` directory
   - Use case: Plugin developers testing changes

2. **Environment Sync** → `--env`
   - Detected when: `.claude/PROJECT.md` exists
   - Action: Sync development environment (dependencies, config, migrations)
   - Use case: Daily development workflow

3. **Marketplace Update** → `--marketplace`
   - Detected when: `~/.claude/installed_plugins.json` exists
   - Action: Update plugin from Claude marketplace
   - Use case: Updating to latest plugin release

4. **Default Fallback** → `--env`
   - If no context detected, defaults to environment sync (safest)

---

## Sync Modes

### Environment Mode (`--env`)

Synchronizes your development environment using the sync-validator agent:

**What it does**:
- Detects dependency conflicts (package.json, requirements.txt, etc.)
- Validates environment variables (.env files)
- Checks for pending database migrations
- Removes stale build artifacts
- Ensures configuration consistency

**When to use**:
- Daily development workflow
- After pulling upstream changes
- When dependencies seem out of sync
- Before starting new feature work

**Example**:
```bash
/sync --env
```

**Output**:
```
Detecting sync mode... Environment sync detected
Invoking sync-validator agent...
✓ Environment sync complete: 3 files updated, 0 conflicts
```

---

### Marketplace Mode (`--marketplace`)

Updates plugin files from the Claude marketplace installation with intelligent version detection and orphan cleanup:

**What it does**:
- **Version Detection** (NEW in v3.7.1): Checks marketplace vs project version and informs about available updates
- **Smart Copy**: Copies latest commands from `~/.claude/plugins/marketplaces/autonomous-dev/`
- **Security Updates**: Syncs hooks with latest security fixes
- **Agent Sync**: Updates agent definitions
- **Orphan Cleanup** (NEW in v3.7.1): Detects and removes files no longer in plugin (safe dry-run by default)
- **Local Preservation**: Preserves local customizations in `.claude/local/`

**When to use**:
- After installing plugin updates via `/plugin update`
- When commands aren't showing expected behavior
- To reset to marketplace defaults
- To clean up old/deprecated plugin files

**Example**:
```bash
/sync --marketplace
```

**Output**:
```
Detecting sync mode... Marketplace update detected

Checking version...
  Project version: 3.7.0
  Marketplace version: 3.7.1
  ⬆ Update available: 3.7.0 → 3.7.1

Copying files from installed plugin...
✓ Marketplace sync complete: 47 files updated
  - Commands: 18 updated
  - Hooks: 12 updated
  - Agents: 17 updated

Checking for orphaned files...
  Found 2 orphaned files (marked for cleanup):
    - .claude/commands/deprecated-sync-dev.md (no longer in v3.7.1)
    - .claude/hooks/old-validation.py (consolidated into newer hook)

  Dry-run mode: No files deleted (use --cleanup to remove)

✓ All marketplace sync operations complete
```

**Version Detection** (NEW in v3.7.1):
- Compares marketplace vs project plugin versions
- Shows available upgrades (3.7.0 → 3.7.1)
- Warns about downgrade risk if applicable
- Prevents silent stale plugin issues

**Orphan Cleanup** (NEW in v3.7.1):
- Detects files removed/renamed in newer plugin versions
- Reports orphans in dry-run mode (safe default)
- Optional cleanup with `--cleanup` flag (removes old files)
- User approval required before deletion (unless `-y` flag)
- Atomic cleanup with rollback on failure

See `lib/version_detector.py` and `lib/orphan_file_cleaner.py` for implementation details.

---

### Plugin Development Mode (`--plugin-dev`)

Syncs plugin development files to local `.claude/` directory:

**What it does**:
- Copies `plugins/autonomous-dev/commands/` → `.claude/commands/`
- Copies `plugins/autonomous-dev/hooks/` → `.claude/hooks/`
- Copies `plugins/autonomous-dev/agents/` → `.claude/agents/`
- Enables testing plugin changes without reinstalling

**When to use**:
- Developing new plugin features
- Testing command modifications
- Debugging agent behavior
- Contributing to plugin development

**Example**:
```bash
/sync --plugin-dev
```

**Output**:
```
Detecting sync mode... Plugin development detected
Syncing plugin files to .claude/...
✓ Plugin dev sync complete: 52 files updated
  - Commands: 18 synced
  - Hooks: 29 synced
  - Agents: 18 synced
```

---

### All Mode (`--all`)

Executes all sync modes in sequence:

**Execution order**:
1. Environment sync (most critical)
2. Marketplace update (get latest releases)
3. Plugin dev sync (apply local changes)

**When to use**:
- Fresh project setup
- Major version updates
- Comprehensive synchronization
- Troubleshooting sync issues

**Example**:
```bash
/sync --all
```

**Output**:
```
Executing all sync modes...

[1/3] Environment sync...
✓ Environment: 3 files updated

[2/3] Marketplace sync...
✓ Marketplace: 47 files updated

[3/3] Plugin dev sync...
✓ Plugin dev: 52 files updated

✓ All sync modes complete: 102 total files updated
```

**Rollback support**: If any mode fails, changes are rolled back automatically.

---

## Migration from Old Commands

### `/sync-dev` → `/sync --env`

Old command:
```bash
/sync-dev
```

New equivalent:
```bash
/sync --env
```

**Note**: `/sync-dev` still works but shows deprecation warning. Update your workflows to use `/sync --env`.

---

### `/update-plugin` → `/sync --marketplace`

Old command:
```bash
/update-plugin
```

New equivalent:
```bash
/sync --marketplace
```

**Note**: `/update-plugin` still works but shows deprecation warning. Update your workflows to use `/sync --marketplace`.

---

## Security

All sync operations include comprehensive security validation:

- **Path Validation**: CWE-22 (path traversal) protection via `security_utils`
- **Symlink Detection**: CWE-59 (symlink resolution) protection
- **Audit Logging**: All operations logged to `logs/security_audit.log`
- **Backup Support**: Automatic backup before sync (rollback on failure)
- **Whitelist Validation**: Only allow writes to approved directories

**Security requirements**:
- All paths validated through 4-layer security checks
- Symlinks resolved before validation
- Log injection prevention (CWE-117)
- User permissions only (no privilege escalation)

See `docs/SECURITY.md` for comprehensive security documentation.

---

## Troubleshooting

### "Sync failed: Project path does not exist"

**Cause**: Invalid project path
**Fix**: Ensure you're running `/sync` from a valid project directory

```bash
cd /path/to/project
/sync
```

---

### "Plugin directory not found" (plugin-dev mode)

**Cause**: Not in a plugin development environment
**Fix**: Only use `--plugin-dev` when working on the plugin itself

```bash
# Check if plugin directory exists
ls plugins/autonomous-dev/

# If not present, you probably want environment sync instead
/sync --env
```

---

### "Conflicting sync flags"

**Cause**: Multiple incompatible flags specified
**Fix**: Use only one flag (or `--all`)

```bash
# ❌ Wrong
/sync --env --marketplace

# ✓ Correct
/sync --env

# ✓ Or use --all
/sync --all
```

---

### "Cannot use --all with specific flags"

**Cause**: Mixing `--all` with specific mode flags
**Fix**: Choose either `--all` OR specific flags

```bash
# ❌ Wrong
/sync --all --env

# ✓ Correct
/sync --all

# ✓ Or specific mode
/sync --env
```

---

### "Update available" notification during marketplace sync

**What it means**: Your project plugin is older than the marketplace version
**Example**: Project v3.7.0, Marketplace v3.7.1

**What to do**:
1. Review changelog for new features/fixes
2. Run `/sync --marketplace` to apply updates
3. Full restart Claude Code (Cmd+Q or Ctrl+Q) to reload commands
4. Test updated commands to verify

**Note**: This is just informational. Your current version still works fine, but updates may include security fixes, performance improvements, or bug fixes.

---

### "Orphaned files detected" warning during marketplace sync

**What it means**: Files exist in your project that aren't in the current plugin version
**Examples**:
- Old commands from previous version (e.g., `sync-dev.md` if upgrading from v3.6 to v3.7)
- Deprecated hooks that were consolidated into newer versions
- Agent files that were renamed

**What to do**:

**Option 1: Review before cleanup** (RECOMMENDED)
```bash
/sync --marketplace     # Shows orphans in dry-run mode
# Review the list of orphaned files

/sync --marketplace --cleanup  # Prompts for each file
# Confirm deletion: y/n for each orphan
```

**Option 2: Auto-cleanup** (Non-interactive)
```bash
/sync --marketplace --cleanup -y
# Automatically deletes all orphans without prompting
```

**Option 3: Keep files** (Conservative)
```bash
# Just ignore the warning - old files won't hurt anything
# They'll still be there but won't interfere
```

**When to be cautious**:
- If you made custom modifications to plugin files
- If you have local extensions relying on old files
- If you're not sure what files do

**Safe choice**: Use `--cleanup` (with confirmation) - it's the best practice to keep your `.claude/` directory clean and in sync with the current plugin version.

---

### "Orphan cleanup failed" during marketplace sync

**Cause**: Permission denied or file locked
**Fix**: Ensure the file isn't in use

```bash
# Close Claude Code completely
# (Press Cmd+Q on Mac or Ctrl+Q on Linux/Windows)

# Wait 5 seconds for process to exit

# Restart Claude Code

# Try sync again
/sync --marketplace --cleanup -y
```

**If still fails**:
```bash
# Check file permissions
ls -la .claude/commands/problematic-file.md

# Fix permissions if needed
chmod 644 .claude/commands/problematic-file.md

# Try cleanup again
/sync --marketplace --cleanup -y
```

---

## Examples

### Daily Development Workflow

```bash
# Morning: Sync environment before starting work
/sync

# Auto-detects environment mode
# Validates dependencies, config, migrations
```

---

### Plugin Update Workflow

```bash
# Step 1: Update plugin via marketplace
/plugin update autonomous-dev

# Step 2: FULL RESTART REQUIRED
# CRITICAL: /exit is NOT enough! Claude Code caches commands in memory.
# Press Cmd+Q (Mac) or Ctrl+Q (Windows/Linux) to fully quit
# Verify: ps aux | grep claude | grep -v grep (should return nothing)
# Wait 5 seconds, then restart Claude Code

# Step 3: Sync marketplace updates to project
/sync --marketplace

# Step 4: FULL RESTART AGAIN
# Commands won't reload until you fully restart Claude Code
# Press Cmd+Q again, wait 5 seconds, restart
```

---

### Plugin Development Workflow

```bash
# Step 1: Make changes to plugin files
vim plugins/autonomous-dev/commands/new-feature.md

# Step 2: Sync to .claude/ for testing
/sync --plugin-dev

# Step 3: FULL RESTART REQUIRED
# CRITICAL: /exit is NOT enough! You must fully quit Claude Code.
# Press Cmd+Q (Mac) or Ctrl+Q (Windows/Linux)
# Verify: ps aux | grep claude | grep -v grep (should return nothing)
# Wait 5 seconds, then restart Claude Code

# Step 4: Test the command
/new-feature

# Step 5: Repeat as needed (restart required each time!)
```

---

### Fresh Project Setup

```bash
# Sync everything
/sync --all

# Ensures:
# - Environment is configured
# - Marketplace updates applied
# - Plugin dev files synced (if applicable)
```

---

## Implementation

Invoke the sync dispatcher to execute the appropriate sync mode based on context detection.

The command uses `sync_mode_detector.py` to auto-detect the mode, then `sync_dispatcher.py` to execute the sync operation.

---

## Technical Details

### Architecture

The unified `/sync` command uses two core libraries:

1. **sync_mode_detector.py**: Intelligent context detection
   - Analyzes project structure
   - Parses command-line flags
   - Validates all paths for security

2. **sync_dispatcher.py**: Mode-specific sync operations
   - Delegates to sync-validator agent (environment mode)
   - Copies files from marketplace (marketplace mode)
   - Syncs plugin dev files (plugin-dev mode)
   - Executes all modes in sequence (all mode)

---

### Performance

**Environment mode**: 30-60 seconds
- Dominated by sync-validator agent analysis
- Depends on project size and changes

**Marketplace mode**: 5-10 seconds
- Fast file copy operations
- Depends on plugin size (~50 files)

**Plugin dev mode**: 5-10 seconds
- Fast local file sync
- Depends on number of files changed

**All mode**: 40-80 seconds
- Sum of all individual modes
- Progress reported for each phase

---

### Backup and Rollback

All sync operations create automatic backups:

- **Backup location**: `$(mktemp -d)/claude_sync_backup_*/`
- **Backup contents**: Complete `.claude/` directory
- **Rollback trigger**: Any sync failure
- **Cleanup**: Automatic after successful sync

**Manual rollback** (if needed):
```bash
# Find backup
ls -la /tmp/claude_sync_backup_*

# Restore manually
cp -r /tmp/claude_sync_backup_*/`.claude/` .claude/
```

---

## See Also

- **Environment Sync**: See archived `/sync-dev` command for detailed workflow
- **Marketplace Updates**: See archived `/update-plugin` command for update process
- **Security**: See `docs/SECURITY.md` for comprehensive security documentation
- **Development**: See `docs/DEVELOPMENT.md` for plugin development guide

---

**Last Updated**: 2025-11-08
**Issue**: GitHub #44 - Unified /sync command consolidation
**Replaces**: `/sync-dev`, `/update-plugin`
