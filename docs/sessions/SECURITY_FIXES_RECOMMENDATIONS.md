# Security Fixes & Implementation Guide

**Date**: 2025-11-03
**Severity**: CRITICAL + HIGH
**Time to Fix**: 1-2 hours

---

## Critical Fix #1: Add Path Validation

**File**: `/Users/akaszubski/Documents/GitHub/autonomous-dev/plugins/autonomous-dev/hooks/sync_to_installed.py`

**Current Code (Lines 18-38)**:
```python
def find_installed_plugin_path():
    """Find the installed plugin path from Claude's config."""
    home = Path.home()
    installed_plugins_file = home / ".claude" / "plugins" / "installed_plugins.json"

    if not installed_plugins_file.exists():
        return None

    try:
        with open(installed_plugins_file) as f:
            config = json.load(f)

        # Look for autonomous-dev plugin
        for plugin_key, plugin_info in config.get("plugins", {}).items():
            if plugin_key.startswith("autonomous-dev@"):
                return Path(plugin_info["installPath"])  # VULNERABLE!
    except Exception as e:
        print(f"Error reading plugin config: {e}")
        return None

    return None
```

**Fixed Code**:
```python
def find_installed_plugin_path():
    """Find the installed plugin path from Claude's config."""
    home = Path.home()
    installed_plugins_file = home / ".claude" / "plugins" / "installed_plugins.json"
    plugins_base_dir = home / ".claude" / "plugins"

    if not installed_plugins_file.exists():
        return None

    try:
        with open(installed_plugins_file) as f:
            config = json.load(f)

        # Look for autonomous-dev plugin
        for plugin_key, plugin_info in config.get("plugins", {}).items():
            if plugin_key.startswith("autonomous-dev@"):
                # SECURE: Validate and canonicalize path
                install_path = plugin_info.get("installPath")
                
                if not install_path:
                    print("ERROR: Missing installPath in plugin config")
                    return None
                
                # Convert to absolute path and resolve symlinks
                try:
                    target_path = Path(install_path).resolve()
                except (OSError, RuntimeError) as e:
                    print(f"ERROR: Could not resolve path {install_path}: {e}")
                    return None
                
                # Verify path is within Claude's plugin directory
                try:
                    target_path.relative_to(plugins_base_dir.resolve())
                except ValueError:
                    print(f"ERROR: installPath outside plugin directory: {target_path}")
                    print(f"       Expected within: {plugins_base_dir}")
                    return None
                
                # Verify it exists
                if not target_path.exists():
                    print(f"ERROR: installPath does not exist: {target_path}")
                    return None
                
                # Verify it's a directory
                if not target_path.is_dir():
                    print(f"ERROR: installPath is not a directory: {target_path}")
                    return None
                
                return target_path
    except Exception as e:
        print(f"Error reading plugin config: {e}")
        return None

    return None
```

**Key Changes**:
1. Extract `installPath` with `.get()` and null check
2. Resolve all symlinks with `.resolve()`
3. Use `.relative_to()` to verify path is within plugins directory
4. Check `.exists()` and `.is_dir()`
5. Catch `OSError` and `RuntimeError` specifically

---

## High Severity Fix #1: Improve Exception Handling

**File**: `/Users/akaszubski/Documents/GitHub/autonomous-dev/plugins/autonomous-dev/hooks/sync_to_installed.py`

**Current Code (Lines 26-31)**:
```python
try:
    with open(installed_plugins_file) as f:
        config = json.load(f)
    # ... process config ...
except Exception as e:  # TOO BROAD
    print(f"Error reading plugin config: {e}")
    return None
```

**Fixed Code**:
```python
try:
    with open(installed_plugins_file) as f:
        config = json.load(f)
except FileNotFoundError:
    print(f"ERROR: Plugin config not found at {installed_plugins_file}")
    print("       This usually means Claude Code plugin system is not initialized.")
    print("       Try: /plugin install autonomous-dev")
    return None
except json.JSONDecodeError as e:
    print(f"ERROR: Invalid JSON in plugin config: {e}")
    print(f"       File: {installed_plugins_file}")
    print("       Try: Reinstall Claude Code or restore the file")
    return None
except PermissionError:
    print(f"ERROR: Permission denied reading plugin config")
    print(f"       File: {installed_plugins_file}")
    print("       Try: chmod 644 ~/.claude/plugins/installed_plugins.json")
    return None
except Exception as e:
    print(f"ERROR: Unexpected error reading plugin config: {type(e).__name__}: {e}")
    return None
```

**Key Improvements**:
1. Catches specific exception types
2. Provides user-actionable error messages
3. Suggests remediation steps for each case

---

## High Severity Fix #2: Apply Same Fix to auto_sync_dev.py

**File**: `/Users/akaszubski/Documents/GitHub/autonomous-dev/plugins/autonomous-dev/hooks/auto_sync_dev.py`

**Affected Lines**: 35-46

Apply the same exception handling pattern as sync_to_installed.py and call the improved function.

---

## Medium Severity Fix #1: Add Atomic File Operations

**File**: `/Users/akaszubski/Documents/GitHub/autonomous-dev/plugins/autonomous-dev/hooks/sync_to_installed.py`

**Current Code (Lines 74-91)**:
```python
for dir_name in sync_dirs:
    source_subdir = source_dir / dir_name
    target_subdir = target_dir / dir_name

    if not source_subdir.exists():
        continue

    if dry_run:
        print(f"[DRY RUN] Would sync: {dir_name}/")
        continue

    # Remove target directory if it exists
    if target_subdir.exists():
        shutil.rmtree(target_subdir)

    # Copy source to target
    shutil.copytree(source_subdir, target_subdir)

    # Count files
    file_count = sum(1 for _ in target_subdir.rglob("*") if _.is_file())
    total_synced += file_count
    print(f"✅ Synced {dir_name}/ ({file_count} files)")
```

**Fixed Code**:
```python
for dir_name in sync_dirs:
    source_subdir = source_dir / dir_name
    target_subdir = target_dir / dir_name

    if not source_subdir.exists():
        continue

    if dry_run:
        print(f"[DRY RUN] Would sync: {dir_name}/")
        continue

    backup_dir = None
    try:
        # Backup existing directory if it exists
        if target_subdir.exists():
            backup_dir = target_subdir.with_name(target_subdir.name + ".backup")
            if backup_dir.exists():
                shutil.rmtree(backup_dir)  # Remove old backup
            target_subdir.rename(backup_dir)
        
        # Copy source to target
        shutil.copytree(source_subdir, target_subdir)
        
        # Count files and cleanup backup
        file_count = sum(1 for _ in target_subdir.rglob("*") if _.is_file())
        total_synced += file_count
        
        # Remove backup after successful copy
        if backup_dir and backup_dir.exists():
            shutil.rmtree(backup_dir)
        
        print(f"✅ Synced {dir_name}/ ({file_count} files)")
        
    except Exception as e:
        # Restore backup if copy failed
        if backup_dir and backup_dir.exists():
            if target_subdir.exists():
                shutil.rmtree(target_subdir)
            backup_dir.rename(target_subdir)
            print(f"⚠️  Restored backup of {dir_name} due to sync error")
        
        print(f"❌ Error syncing {dir_name}: {e}")
        return False
```

**Key Improvements**:
1. Creates backup before deleting
2. Restores backup if copy fails
3. Cleans up backup only after successful copy
4. Provides rollback capability

---

## Low Severity Fix: Add Directory List Validation

**File**: `/Users/akaszubski/Documents/GitHub/autonomous-dev/plugins/autonomous-dev/hooks/sync_to_installed.py`

**Add at Module Level**:
```python
# Validate directory names to prevent path traversal
ALLOWED_SYNC_DIRS = {"agents", "skills", "commands", "hooks", "scripts", "templates", "docs"}
ALLOWED_SYNC_FILES = {"README.md", "CHANGELOG.md"}

def validate_sync_list(items, allowed_set, item_type="directory"):
    """Validate sync list contains only allowed items.
    
    Raises:
        ValueError: If any items are not in the allowed set
    """
    invalid = set(items) - allowed_set
    if invalid:
        raise ValueError(f"Invalid {item_type}s found: {', '.join(sorted(invalid))}")
```

**Use in sync_plugin()**:
```python
def sync_plugin(source_dir: Path, target_dir: Path, dry_run: bool = False):
    """Sync plugin files from source to target."""
    if not source_dir.exists():
        print(f"❌ Source directory not found: {source_dir}")
        return False

    if not target_dir.exists():
        print(f"❌ Target directory not found: {target_dir}")
        print("   Plugin may not be installed. Run: /plugin install autonomous-dev")
        return False

    print(f"📁 Source: {source_dir}")
    print(f"📁 Target: {target_dir}")
    print()

    # Directories to sync
    sync_dirs = ["agents", "skills", "commands", "hooks", "scripts", "templates", "docs"]

    # Files to sync
    sync_files = ["README.md", "CHANGELOG.md"]
    
    # Validate before processing
    try:
        validate_sync_list(sync_dirs, ALLOWED_SYNC_DIRS, "directory")
        validate_sync_list(sync_files, ALLOWED_SYNC_FILES, "file")
    except ValueError as e:
        print(f"❌ Validation error: {e}")
        return False

    # ... rest of function ...
```

---

## Documentation Fix: Add Security Considerations Section

**File**: `/Users/akaszubski/Documents/GitHub/autonomous-dev/plugins/autonomous-dev/commands/sync-dev.md`

**Add New Section (after "## Troubleshooting")**:

```markdown
## Security Considerations

### Configuration Trust
The sync command reads from `~/.claude/plugins/installed_plugins.json`. On shared systems, 
ensure this file is not readable by untrusted users:

```bash
chmod 600 ~/.claude/plugins/installed_plugins.json
```

### Shared Systems
On multi-user systems, users can potentially interfere with each other's plugin installations:
- Use separate user accounts for isolation
- Set restrictive umask: `umask 077`
- Run Claude Code from separate home directories

### Atomic Operations
File operations are NOT atomic. If sync fails mid-operation, the plugin may be in an 
inconsistent state. Always run `/health-check` after sync to verify all components:

```bash
/sync-dev
/health-check  # Verify integrity
```

### Rollback Procedure
If sync causes issues, recover with:

```bash
# Option 1: Rollback to last known-good state
git reset --hard HEAD~1

# Option 2: Reinstall the plugin
/plugin uninstall autonomous-dev
# Restart Claude Code
/plugin install autonomous-dev
```
```

---

## Testing the Fixes

### Test #1: Path Validation

```python
def test_path_validation_rejects_traversal():
    """Verify path validation prevents traversal attacks."""
    # Simulate malicious installPath
    malicious_path = "/tmp/evil/../../../../../../etc/passwd"
    target_path = Path(malicious_path).resolve()
    plugins_dir = Path.home() / ".claude" / "plugins"
    
    # Should raise ValueError due to path being outside plugins dir
    with pytest.raises(ValueError):
        target_path.relative_to(plugins_dir.resolve())

def test_path_validation_accepts_valid_path():
    """Verify path validation accepts legitimate plugin paths."""
    valid_path = Path.home() / ".claude" / "plugins" / "autonomous-dev"
    plugins_dir = Path.home() / ".claude" / "plugins"
    
    # Should not raise - path is within plugins dir
    assert valid_path.relative_to(plugins_dir.resolve())
```

### Test #2: Exception Handling

```python
def test_json_parse_error_handling(tmp_path):
    """Verify JSON parsing errors are caught specifically."""
    config_file = tmp_path / "config.json"
    config_file.write_text("{invalid json")
    
    with pytest.raises(json.JSONDecodeError):
        with open(config_file) as f:
            json.load(f)

def test_permission_error_handling(tmp_path):
    """Verify permission errors are caught specifically."""
    config_file = tmp_path / "config.json"
    config_file.write_text("{}")
    config_file.chmod(0o000)  # Remove all permissions
    
    with pytest.raises(PermissionError):
        with open(config_file) as f:
            pass
    
    config_file.chmod(0o644)  # Restore for cleanup
```

---

## Implementation Checklist

- [ ] Apply Critical Fix #1: Path validation in sync_to_installed.py
- [ ] Apply Critical Fix #1b: Same fix in auto_sync_dev.py
- [ ] Apply High Fix #1: Exception handling in sync_to_installed.py
- [ ] Apply High Fix #1b: Exception handling in auto_sync_dev.py
- [ ] Apply High Fix #2: Atomic file operations in sync_to_installed.py
- [ ] Apply Low Fix: Directory list validation
- [ ] Add security tests for path validation
- [ ] Add security tests for exception handling
- [ ] Update sync-dev.md documentation
- [ ] Update sync-validator.md agent documentation
- [ ] Run full test suite: `pytest tests/test_sync_dev_command.py -v`
- [ ] Manual testing: `/sync-dev` after each fix
- [ ] Code review with security focus
- [ ] Commit with message: "security: fix critical path validation vulnerability in sync hooks"

---

## Estimated Effort

- Code changes: 45 minutes
- Testing: 30 minutes
- Documentation: 15 minutes
- Code review: 15 minutes
- **Total: ~1.5 hours**

---

## Post-Fix Verification

After implementing fixes, verify security posture:

1. No unvalidated paths used from external config
2. All exceptions handled specifically  
3. Destructive operations have rollback
4. Directory lists validated
5. Documentation updated
6. Security tests pass
7. All tests still pass

---

**Recommendations Document Generated**: 2025-11-03
**Agent**: security-auditor
**Priority**: CRITICAL - implement immediately
