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

## See Also

- [DEVELOPMENT.md](DEVELOPMENT.md) - Complete setup instructions with step-by-step guide
- [README.md](../plugins/autonomous-dev/README.md) - Plugin overview and quick start
- [.gitignore](../.gitignore) - Symlink exclusion configuration

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
