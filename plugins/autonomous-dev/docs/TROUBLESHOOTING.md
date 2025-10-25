# Troubleshooting Guide

**Last Updated**: 2025-10-25

Common issues and solutions for the autonomous-dev plugin.

---

## 🔥 CRITICAL: Plugin Development Issues

### 0. "I'm editing plugin files but changes don't appear when testing" (MOST COMMON!)

**Symptoms**:
- Edit agent/command/skill files
- Test with `/health-check` or commands
- See NO CHANGES (old behavior persists)
- Edit more, test more, still nothing
- Start questioning reality
- Eventually discover the two-location problem

**Root Cause**:
**YOU ARE EDITING THE WRONG LOCATION!**

When developing this plugin, there are TWO separate locations:

1. **Development location** (where you edit):
   ```
   /path/to/autonomous-dev/plugins/autonomous-dev/
   ```

2. **Runtime location** (where Claude Code reads):
   ```
   ~/.claude/plugins/marketplaces/akaszubski-autonomous-dev/plugins/autonomous-dev/
   ```

**Claude Code reads from the runtime location, NOT your development directory!**

**Solutions**:

**Option 1: Use `/sync-dev` command (EASIEST)**
```bash
# 1. Make changes to plugin files
vim plugins/autonomous-dev/agents/implementer.md

# 2. CRITICAL: Sync to Claude Code's runtime location
/sync-dev

# 3. Restart Claude Code (REQUIRED!)
# Press Cmd+Q (Mac) or Ctrl+Q (Linux/Windows)

# 4. Test your changes
/health-check
```

**Option 2: Use sync script directly**
```bash
# 1. Make changes
vim plugins/autonomous-dev/agents/implementer.md

# 2. Run sync script
python plugins/autonomous-dev/scripts/sync_to_installed.py

# 3. Restart Claude Code
# Press Cmd+Q (Mac) or Ctrl+Q (Linux/Windows)

# 4. Test
/health-check
```

**Option 3: Manual sync (NOT RECOMMENDED)**
```bash
# Find runtime location first
find ~/.claude/plugins/marketplaces -name "autonomous-dev" -type d

# Copy files manually
cp -r plugins/autonomous-dev/* ~/.claude/plugins/marketplaces/.../autonomous-dev/

# Restart Claude Code
```

**Prevention**:
```bash
# ALWAYS follow this workflow:
# Edit → Sync → Restart → Test → Repeat

# NEVER skip the sync step!
# Your edits won't appear without it.
```

**How to verify you're synced**:
```bash
# Check file timestamps match
ls -lt plugins/autonomous-dev/agents/implementer.md
ls -lt ~/.claude/plugins/marketplaces/.../autonomous-dev/agents/implementer.md

# Should show same modification time after sync
```

**When restart IS required**:
- Installing/uninstalling plugins ← YES
- Changing plugin.json manifest ← YES
- Adding/removing agents/skills/commands ← YES
- Editing existing agent/skill/command content ← YES (after sync)

**When restart NOT required**:
- Editing test files (tests/) ← NO
- Editing dev docs (docs/dev/) ← NO
- Editing project README.md ← NO (unless testing user view)

**This will save you HOURS of frustration!**

---

### 0b. "Slash commands don't do anything"

**Symptom**: Command runs but only shows documentation, doesn't execute anything.

**Cause**: Command file missing `## Implementation` section.

**Fix**: Commands must have one of these patterns:

**Bash script:**
```markdown
## Implementation

```bash
pytest tests/ -v
```
\```
```

**Agent invocation:**
```markdown
## Implementation

Invoke the test-master agent with prompt:
```
Run comprehensive tests...
```
\```
```

**To create new command**: Copy an existing working command and modify it.

**Validator**: Pre-commit hook automatically checks all commands have implementations.

---

## Installation Issues

### 1. "Plugin not found" after installation

**Symptoms**:
```
/plugin install autonomous-dev
Error: Plugin 'autonomous-dev' not found
```

**Causes**:
- Plugin not in marketplace
- Incorrect plugin name
- Repository not accessible

**Solutions**:
```bash
# Option 1: Install from local path
cd /path/to/autonomous-dev
/plugin install ./plugins/autonomous-dev

# Option 2: Create symlink manually
ln -s /path/to/autonomous-dev/plugins/autonomous-dev \
      ~/.claude/plugins/autonomous-dev

# Option 3: Add to marketplace first
# See plugins/autonomous-dev/.claude-plugin/plugin.json
```

---

### 2. "Commands not found" after installation

**Symptoms**:
```
/test
Error: Command not found
```

**Causes**:
- Plugin installed but not activated in project
- Commands not copied to `.claude/commands/`

**Solutions**:
```bash
# Reinstall plugin
/plugin uninstall autonomous-dev
/plugin install autonomous-dev

# Verify commands exist
ls -la .claude/commands/
```

---

### 3. "Agents not available"

**Symptoms**:
- Agents not showing up in Claude Code
- Task tool fails with "agent not found"

**Causes**:
- Agents not in `.claude/agents/`
- Symlink broken

**Solutions**:
```bash
# Reinstall plugin
/plugin uninstall autonomous-dev
/plugin install autonomous-dev

# Verify agents exist (should have 8 agents)
ls -la .claude/agents/
```

---

## Hook Issues

### 4. "Hooks not running automatically"

**Symptoms**:
- Write files but no auto-format
- Edit files but no validation
- Hooks configured but silent

**Causes**:
- Hooks not in `.claude/hooks/`
- Hooks not executable
- Settings not configured

**Solutions**:
```bash
# 1. Verify hooks exist
ls -la .claude/hooks/

# 2. Make hooks executable
chmod +x .claude/hooks/*.py

# 3. Check settings.local.json
cat .claude/settings.local.json

# Should have PostToolUse hooks:
{
  "hooks": {
    "PostToolUse": [
      {
        "matcher": "Write",
        "hooks": [{"type": "command", "command": "python .claude/hooks/auto_format.py"}]
      }
    ]
  }
}

# 4. Reinstall if needed
/plugin uninstall autonomous-dev
/plugin install autonomous-dev
```

---

### 5. "Hook fails with Python error"

**Symptoms**:
```
Error: ModuleNotFoundError: No module named 'black'
```

**Causes**:
- Missing Python dependencies
- Wrong Python version
- Virtual environment not activated

**Solutions**:
```bash
# Check Python version (need 3.11+)
python3 --version

# Install dependencies
pip install black isort ruff pytest

# Or use requirements.txt if available
pip install -r requirements.txt

# For hooks, ensure system Python has packages
# (hooks run outside venv)
python3 -m pip install black isort ruff
```

---

## Performance Issues

### 6. "Context budget exceeded"

**Symptoms**:
```
Error: Token limit exceeded
Response truncated
```

**Causes**:
- Too many features in one session
- Large file reads
- Not clearing context

**Solutions**:
```bash
# CRITICAL: Clear context after each feature
/clear

# Best practice:
# 1. Complete feature
# 2. Run /clear
# 3. Start next feature

# See CLAUDE.md for context management strategy
```

---

### 7. "Commands run slowly"

**Symptoms**:
- /test takes minutes
- /format hangs
- Hooks timeout

**Causes**:
- Large codebase
- Too many files
- Infinite loops in hooks

**Solutions**:
```bash
# 1. Check what's being processed
/test unit  # Instead of /test all

# 2. Limit hook scope (edit hook files)
vim .claude/hooks/auto_format.py
# Add file size limits, path exclusions

# 3. Skip hooks temporarily
# Edit settings.local.json, comment out hook

# 4. Check for infinite loops
python3 .claude/hooks/auto_format.py --verbose
```

---

## Configuration Issues

### 8. "Settings conflict with existing project"

**Symptoms**:
- Pre-existing hooks overwritten
- Custom settings lost
- Conflicts with team setup

**Causes**:
- Plugin overwrites existing config
- No merge strategy

**Solutions**:
```bash
# 1. Backup existing settings FIRST
cp .claude/settings.local.json .claude/settings.local.json.backup

# 2. Manual merge
# Compare and merge settings carefully
diff .claude/settings.local.json.backup .claude/settings.local.json

# 3. Selective installation
# Copy only what you need
cp plugins/autonomous-dev/agents/* .claude/agents/
# (Don't copy hooks if you have custom ones)

# 4. Use custom settings
# Edit settings.local.json to disable unwanted hooks
```

---

### 9. "PROJECT.md alignment warnings"

**Symptoms**:
```
⚠️  Feature doesn't align with PROJECT.md goals
```

**Causes**:
- Feature request doesn't match PROJECT.md
- PROJECT.md outdated
- Legitimate new direction

**Solutions**:
```bash
# Option 1: Modify feature to align
# Adjust your request to match PROJECT.md goals

# Option 2: Update PROJECT.md if direction changed
vim PROJECT.md
# Update GOALS, SCOPE sections

# Option 3: Use /align-project-safe
/align-project-safe
# Analyzes and asks before making changes
```

---

### 10. "Git hooks conflict"

**Symptoms**:
```
.git/hooks/pre-commit already exists
Error: Hook installation failed
```

**Causes**:
- Existing git hooks
- Team uses different hook manager
- Husky/lefthook already installed

**Solutions**:
```bash
# Option 1: Merge hooks manually
cat .git/hooks/pre-commit  # Check existing
cat plugins/autonomous-dev/hooks/pre-commit  # Check new

# Combine both into one file
vim .git/hooks/pre-commit

# Option 2: Use hook chaining
# Most hook managers support chaining
# Add to existing hook:
python3 .claude/hooks/auto_format.py

# Option 3: Skip git hooks, use Claude Code hooks only
# Claude Code hooks (PostToolUse) run on file changes
# Git hooks run on commits
# Choose which you prefer
```

---

## Common Questions

### "How do I disable a specific hook?"

```bash
# Edit settings.local.json
vim .claude/settings.local.json

# Remove or comment out the hook:
{
  "hooks": {
    "PostToolUse": [
      // {
      //   "matcher": "Write",
      //   "hooks": [{"type": "command", "command": "python .claude/hooks/auto_format.py"}]
      // }
    ]
  }
}
```

### "How do I customize an agent?"

```bash
# Edit agent file
vim .claude/agents/orchestrator.md

# Modify:
# - Tools available
# - Workflow steps
# - Examples

# Refresh
./scripts/refresh-claude-settings.sh
```

### "How do I add custom commands?"

```bash
# Create command file
vim .claude/commands/my-command.md

# Use template from CONTRIBUTING.md

# Test
/my-command
```

### "Where are session logs?"

```bash
# Check docs/sessions/
ls -lt docs/sessions/ | head -5

# View latest
cat docs/sessions/$(ls -t docs/sessions/ | head -1)
```

### "How do I uninstall cleanly?"

```bash
# 1. Remove plugin
/plugin uninstall autonomous-dev

# 2. Remove project settings (optional)
rm -rf .claude/agents .claude/commands .claude/skills .claude/hooks

# 3. Remove from settings.local.json
vim .claude/settings.local.json
# Remove hook configurations

# 4. Remove symlink
rm ~/.claude/plugins/autonomous-dev
```

---

## Getting More Help

### Still stuck?

1. **Check documentation**:
   - README.md - Overview
   - DEVELOPMENT.md - Development workflow
   - ARCHITECTURE.md - System design
   - IMPLEMENTATION-STATUS.md - What's implemented

2. **Search issues**:
   - [GitHub Issues](https://github.com/akaszubski/autonomous-dev/issues)

3. **Ask for help**:
   - Open a new issue with:
     - What you tried
     - Error messages (full output)
     - Your environment (OS, Python version, Claude Code version)
     - Relevant config files

4. **Enable verbose logging**:
   ```bash
   # Add to hook files for debugging
   VERBOSE = True

   # Or run hooks manually
   python3 .claude/hooks/auto_format.py --verbose
   ```

---

## Diagnostic Commands

```bash
# Check environment
echo "=== Environment ==="
python3 --version
which python3
echo $PATH

# Check plugin installation
echo "=== Plugin ==="
ls -la ~/.claude/plugins/autonomous-dev
ls -la .claude/

# Check file counts
echo "=== Components ==="
echo "Agents: $(ls -1 .claude/agents/*.md 2>/dev/null | wc -l | xargs)"
echo "Commands: $(ls -1 .claude/commands/*.md 2>/dev/null | wc -l | xargs)"
echo "Skills: $(ls -1 .claude/skills/*/SKILL.md 2>/dev/null | wc -l | xargs)"
echo "Hooks: $(ls -1 .claude/hooks/*.py 2>/dev/null | wc -l | xargs)"

# Check settings
echo "=== Settings ==="
cat .claude/settings.local.json | grep -A 5 hooks

# Test hook manually
echo "=== Test Hook ==="
python3 .claude/hooks/auto_format.py
echo "Exit code: $?"
```

---

**Last Updated**: 2025-10-25

**Found a new issue?** Add it to this guide via pull request!
