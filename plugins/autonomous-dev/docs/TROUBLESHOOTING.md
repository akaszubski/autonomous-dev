# Troubleshooting Guide

**Last Updated**: 2025-11-19
**For**: Developers and contributors encountering common issues

---

## ModuleNotFoundError: No module named 'autonomous_dev'

### Symptom

When running tests or importing from the plugin, you see:

```python
Traceback (most recent call last):
  File "tests/unit/test_something.py", line 10, in <module>
    from autonomous_dev.lib import security_utils
ModuleNotFoundError: No module named 'autonomous_dev'
```

### Root Cause

Python package names cannot contain hyphens (`-`), only underscores (`_`).
The plugin directory is named `autonomous-dev` (with hyphen) but Python expects
`autonomous_dev` (with underscore) for imports.

### Solution: Create a Development Symlink

The solution is to create a symbolic link that maps the underscore name to the hyphen directory.

#### macOS/Linux

```bash
cd plugins
ln -s autonomous-dev autonomous_dev
```

#### Windows (Command Prompt - Run as Administrator)

```cmd
cd plugins
mklink /D autonomous_dev autonomous-dev
```

#### Windows (PowerShell - Run as Administrator)

```powershell
cd plugins
New-Item -ItemType SymbolicLink -Path "autonomous_dev" -Target "autonomous-dev"
```

### Verification

After creating the symlink, verify it works:

#### macOS/Linux

```bash
ls -la plugins/ | grep autonomous_dev
# Expected output: autonomous_dev -> autonomous-dev
```

#### Windows (Command Prompt)

```cmd
dir plugins\ | findstr autonomous_dev
# Expected output: <SYMLINKD> autonomous_dev [autonomous-dev]
```

#### Windows (PowerShell)

```powershell
Get-Item plugins\autonomous_dev | Select-Object LinkType, Target
# Expected output: LinkType: SymbolicLink, Target: autonomous-dev
```

### Test the Import

```bash
python -c "from autonomous_dev.lib import security_utils; print('✓ Import works')"
# Should print: ✓ Import works
```

If this still fails, ensure you're in the project root and the symlink was created correctly.

### Why a Symlink?

1. **Python Limitation**: Python's import system requires valid identifiers (no hyphens)
2. **Human Readability**: The directory name `autonomous-dev` is more readable in file explorers
3. **Git Compatibility**: The symlink is gitignored (see `.gitignore`) and won't affect the repository
4. **Security**: Uses relative paths within the repository, no external dependencies

### Security Note

This symlink is safe - it uses a relative path within the repository and is automatically gitignored.
It will not be committed to version control.

---

## Lib Files Not Installed to ~/.claude/lib/

### Symptom

Hook operations fail with errors like:

```
ModuleNotFoundError: No module named 'auto_approval_engine'
ImportError: cannot import name 'security_utils' from 'autonomous_dev.lib'
```

Or hooks don't execute with permission validation errors.

### Root Cause

Lib files (security_utils.py, path_utils.py, validation.py, etc.) need to be copied from `plugins/autonomous-dev/lib/` to `~/.claude/lib/` where hooks can import them. This happens automatically during:
- Fresh installation (install.sh)
- Plugin updates (/sync, /update-plugin)
- /setup command

If this fails silently, hooks can't access required libraries.

### Solution: Manual Lib File Installation

If lib files didn't install automatically:

#### 1. Verify lib directory exists

```bash
ls -la ~/.claude/lib/
```

If empty or missing, proceed to step 2.

#### 2. Copy lib files manually

```bash
# Identify plugin location
# In development: plugins/autonomous-dev/lib/
# In marketplace: ~/.claude/plugins/autonomous-dev/lib/

# Copy all .py files to ~/.claude/lib/
cp plugins/autonomous-dev/lib/*.py ~/.claude/lib/

# Verify copy
ls -la ~/.claude/lib/ | grep .py
# Should show: security_utils.py, path_utils.py, validation.py, etc.
```

#### 3. Fix permissions

```bash
# Ensure files are readable
chmod 644 ~/.claude/lib/*.py
chmod 755 ~/.claude/lib/
```

#### 4. Verify hooks can import

```bash
# Test import from hook context
python3 -c "import sys; sys.path.insert(0, '~/.claude/lib'); from security_utils import audit_log; print('OK')"
```

### Why This Happens

- **Fresh Install**: install.sh may skip lib files if permission denied or directory doesn't exist
- **Updates**: Plugin updates may fail to sync lib files due to:
  - Permission issues on ~/.claude/lib/
  - Missing source lib directory in plugin
  - Installation manifest doesn't list lib directory
- **Marketplace**: Marketplace-only installs don't have access to global infrastructure

### Automatic Installation Workflow (Issue #123)

Starting with v3.42.0+, lib files are automatically installed:

1. **install.sh**: Calls `install_lib_files()` after file staging
   - Creates ~/.claude/lib if missing
   - Copies all .py files from plugin/lib
   - Validates file integrity (rejects symlinks)
   - Non-blocking (installation continues even if lib copy fails)

2. **Plugin Updates** (/sync, /update-plugin): Calls `_sync_lib_files()` after sync
   - Reads installation_manifest.json to verify lib should be synced
   - Copies lib files to ~/.claude/lib after successful plugin sync
   - Validates paths for security (CWE-22, CWE-59 prevention)
   - Audit logs all operations
   - Non-blocking (update succeeds even if lib sync fails)

3. **Permissions Validation**: Calls `_validate_and_fix_permissions()`
   - Validates settings.local.json permission patterns
   - Fixes broken patterns (wildcard → specific commands)
   - Creates timestamped backups before fixes
   - Non-blocking (update continues even if validation fails)

### If Manual Installation Still Fails

Check file permissions:

```bash
# Verify you can write to ~/.claude/lib/
touch ~/.claude/lib/test.txt && rm ~/.claude/lib/test.txt && echo "OK" || echo "FAILED"

# Check existing permissions
ls -la ~/.claude/
# Should see: drwx------ user group .claude
```

If permission denied, you may need to:
- Check ~/.claude/ permissions (should be 0o700, user-only)
- Delete ~/.claude/ and reinstall: `rm -rf ~/.claude/` then `/setup`
- Check disk space and filesystem errors

---

## See Also

- [DEVELOPMENT.md](DEVELOPMENT.md) - Complete setup instructions with step-by-step guide
- [README.md](../plugins/autonomous-dev/README.md) - Plugin overview and quick start
- [.gitignore](../.gitignore) - Symlink exclusion configuration
- [docs/LIBRARIES.md](../../docs/LIBRARIES.md) - Lib file API documentation
- GitHub Issue #123 - Automatic lib file installation implementation

---

## Other Common Issues

### Commands Not Loading After Plugin Update

**Symptom**: After updating the plugin, new commands don't appear.

**Solution**: Fully restart Claude Code (not just `/exit`):
1. Press `Cmd+Q` (Mac) or `Ctrl+Q` (Windows/Linux)
2. Wait 5 seconds
3. Reopen Claude Code

### Hooks Not Triggering

**Symptom**: Expected hooks (auto-format, feature detection) aren't running.

**Solution**: Check `.claude/settings.local.json` configuration:
```bash
cat .claude/settings.local.json
```

Ensure hooks are properly configured. See [DEVELOPMENT.md](DEVELOPMENT.md) for setup instructions.

### Tests Failing After Clean Checkout

**Symptom**: Tests fail immediately after cloning the repository.

**Checklist**:
1. Did you create the `autonomous_dev` symlink? (See above)
2. Did you install dependencies? `pip install -r requirements.txt`
3. Are you in the project root? `pwd` should show the autonomous-dev directory
4. Is Python 3.8+ installed? `python --version`

---

**For more help**: See the [DEVELOPMENT.md](DEVELOPMENT.md) guide or open an issue on GitHub.
