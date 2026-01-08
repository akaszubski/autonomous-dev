# Troubleshooting Guide

**Last Updated**: 2026-01-08
**For**: Users and developers encountering common issues

---

## Quick Fixes

| Problem | Solution |
|---------|----------|
| Commands not appearing | Restart Claude Code (Cmd+Q / Ctrl+Q) |
| ModuleNotFoundError | Create symlink (see below) |
| Hook not running | Check `~/.claude/settings.json` |
| Context exceeded | Run `/clear` |
| Plugin changes not visible | Run `/sync --plugin-dev` then restart |

---

## Installation Issues

### "Commands not found after installation"

**Symptom**: After running `install.sh`, commands like `/auto-implement` don't appear.

**Cause**: Claude Code caches commands at startup.

**Solution**:
```bash
# 1. Fully quit Claude Code
#    Press Cmd+Q (Mac) or Ctrl+Q (Windows/Linux)

# 2. Verify process is dead
ps aux | grep -i claude | grep -v grep
# Should return nothing

# 3. Wait 5 seconds, then reopen Claude Code

# 4. Verify commands appear
/health-check
```

### "install.sh fails or incomplete"

**Symptom**: Installation script errors or missing components.

**Solution**:
```bash
# 1. Check what was installed
ls -la ~/.claude/hooks/ | wc -l    # Should be ~50 hooks
ls -la ~/.claude/lib/ | wc -l      # Should be ~69 libs

# 2. Re-run installation
bash <(curl -sSL https://raw.githubusercontent.com/akaszubski/autonomous-dev/master/install.sh)

# 3. Restart Claude Code
```

### "How do I uninstall?"

**Solution**: Use the `/sync --uninstall` command (added in v3.41.0):

```bash
# Preview what will be removed
/sync --uninstall

# Confirm with --force flag
/sync --uninstall --force

# Keep global ~/.claude/ files (only remove project files)
/sync --uninstall --force --local-only
```

Creates automatic backup before removal. Rollback available if needed.

---

## Development Issues

### ModuleNotFoundError: No module named 'autonomous_dev'

**Symptom**: When running tests or importing:
```python
ModuleNotFoundError: No module named 'autonomous_dev'
```

**Cause**: Python can't use hyphens in package names. Directory is `autonomous-dev` but imports need `autonomous_dev`.

**Solution**: Create a symlink:

```bash
# macOS/Linux
cd plugins
ln -s autonomous-dev autonomous_dev

# Windows (Command Prompt as Admin)
cd plugins
mklink /D autonomous_dev autonomous-dev

# Verify
python3 -c "from autonomous_dev.lib import security_utils; print('OK')"
```

### "Plugin changes don't appear when testing"

**Symptom**: Edit agent/command files but changes don't show up.

**Cause**: Claude Code reads from `~/.claude/` not your development directory.

**Solution**:
```bash
# 1. Make your changes
vim plugins/autonomous-dev/agents/implementer.md

# 2. Sync to installed location
/sync --plugin-dev

# 3. REQUIRED: Restart Claude Code
#    Press Cmd+Q (Mac) or Ctrl+Q (Windows/Linux)

# 4. Test changes
/health-check
```

### "Lib files not found by hooks"

**Symptom**: Hooks fail with import errors:
```
ModuleNotFoundError: No module named 'security_utils'
```

**Cause**: Lib files not copied to `~/.claude/lib/`.

**Solution**:
```bash
# 1. Check lib directory
ls ~/.claude/lib/*.py | wc -l
# Should show ~69 files

# 2. If missing, re-run install or copy manually
cp plugins/autonomous-dev/lib/*.py ~/.claude/lib/

# 3. Verify imports work
python3 -c "import sys; sys.path.insert(0, '$HOME/.claude/lib'); import security_utils; print('OK')"
```

---

## Runtime Issues

### "Context budget exceeded"

**Symptom**: Token limit errors, truncated responses.

**Cause**: Too many features in one session without clearing context.

**Solution**:
```bash
# Clear context after each feature
/clear

# Best practice workflow:
# 1. Complete feature with /auto-implement
# 2. Run /clear
# 3. Start next feature
```

### "Hooks not running"

**Symptom**: Expected hooks (auto-format, validation) don't trigger.

**Solution**:
```bash
# 1. Check hooks are installed
ls ~/.claude/hooks/*.py | head -5

# 2. Check settings configuration
cat ~/.claude/settings.json | grep -A 10 '"hooks"'

# 3. Check hook is executable
chmod +x ~/.claude/hooks/*.py

# 4. Test hook manually
python3 ~/.claude/hooks/auto_format.py
echo "Exit code: $?"
```

### "Feature doesn't align with PROJECT.md"

**Symptom**: Warning about feature not matching project goals.

**Solution**:
```bash
# Option 1: Modify feature to align with PROJECT.md goals

# Option 2: Update PROJECT.md if direction changed
vim .claude/PROJECT.md
# Update GOALS, SCOPE sections

# Option 3: Run alignment check
/align
```

---

## Command-Specific Issues

### "/auto-implement stops mid-way"

**Symptom**: Pipeline doesn't complete all 8 steps.

**Solutions**:
1. Check for test failures (step 4) - fix failing tests
2. Check for security issues (step 6) - address vulnerabilities
3. Context may be full - run `/clear` and retry
4. Check agent output for specific errors

### "/batch-implement crashes"

**Symptom**: Batch processing stops unexpectedly.

**Solution**:
```bash
# Resume from where it stopped
/batch-implement --resume <batch-id>

# Check batch state
cat .claude/batch_state.json
```

### "/sync fails"

**Symptom**: Sync command errors.

**Solutions**:
```bash
# Check which mode is failing
/sync --github    # Fetch from GitHub
/sync --env       # Environment sync
/sync --plugin-dev # Dev sync (requires being in autonomous-dev repo)

# For GitHub sync, ensure git remote is configured
git remote -v
```

### "/sync tries to fetch URL instead of executing script"

**Symptom**: When you run `/sync`, Claude attempts to fetch content from a URL (e.g., GitHub) instead of executing the script locally.

**Cause**: The sync.md command file should have a strong "Do NOT fetch" directive to prevent Claude from web requests. If missing or incorrectly placed, Claude may interpret the script as needing external resources.

**Solution**:
```bash
# 1. Verify the directive is in place
grep "Do NOT fetch" .claude/commands/sync.md
# Should output: Do NOT fetch any URLs or documentation. Execute the script below directly.

# 2. If directive is missing or incorrect, re-sync
/sync --plugin-dev

# 3. Restart Claude Code to ensure command is reloaded
# Press Cmd+Q (Mac) or Ctrl+Q (Windows/Linux), wait 5 seconds, reopen

# 4. Test the command again
/sync --github

# 5. If still failing, check installed version
cat ~/.claude/commands/sync.md | head -15
# Should see "Do NOT fetch" in lines 1-10
```

**Note**: The "Do NOT fetch" directive must appear BEFORE the bash code block to ensure Claude reads and respects it immediately.

---

## Diagnostic Commands

```bash
# Environment check
echo "=== Environment ==="
python3 --version
which python3

# Installation check
echo "=== Installation ==="
echo "Hooks: $(ls ~/.claude/hooks/*.py 2>/dev/null | wc -l)"
echo "Libs: $(ls ~/.claude/lib/*.py 2>/dev/null | wc -l)"
echo "Commands: $(ls .claude/commands/*.md 2>/dev/null | wc -l)"
echo "Agents: $(ls .claude/agents/*.md 2>/dev/null | wc -l)"

# Test a hook
echo "=== Hook Test ==="
python3 ~/.claude/hooks/validate_commands.py
echo "Exit code: $?"

# Check settings
echo "=== Settings ==="
cat ~/.claude/settings.json | python3 -m json.tool | head -20
```

---

## Getting Help

1. **Run health check**: `/health-check` validates plugin integrity
2. **Check CLAUDE.md**: Project instructions and troubleshooting section
3. **Search issues**: [GitHub Issues](https://github.com/akaszubski/autonomous-dev/issues)
4. **Open new issue**: Include error messages, OS, Python version

---

## Version Info

- **Current version**: v3.41.0+
- **Agents**: 22 specialists
- **Hooks**: 50 automation hooks
- **Commands**: 7 active (`/auto-implement`, `/batch-implement`, `/create-issue`, `/align`, `/setup`, `/sync`, `/health-check`)
