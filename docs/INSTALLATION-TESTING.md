# Installation Testing & Edge Cases

## Issues Found During Testing

### Current State

**What `/plugin install autonomous-dev` actually does:**
1. Downloads plugin files to `~/.claude/plugins/marketplaces/autonomous-dev/`
2. Copies agents, commands, skills to Claude Code's internal registry
3. **Does NOT** copy hooks automatically
4. **Does NOT** handle upgrades (overwrites without backup)
5. **Does NOT** clean up old versions
6. **Does NOT** validate installation completeness

### Pain Points You Identified

1. **"What about hooks?"** - They don't auto-install, need manual setup
2. **"What about old versions?"** - No cleanup, can cause conflicts
3. **"What about outdated?"** - No version comparison before install
4. **"What if it doesn't complete?"** - No rollback, partial installs break things

---

## The Real Installation Flow

### Step 1: Plugin Install (Minimal)

```bash
/plugin marketplace add akaszubski/autonomous-dev
/plugin install autonomous-dev
```

**What this does:**
- ✅ Downloads to `~/.claude/plugins/marketplaces/autonomous-dev/`
- ✅ Registers commands (/auto-implement, etc.)
- ✅ Registers agents (researcher, planner, etc.)
- ✅ Registers skills (progressive disclosure enabled)
- ❌ **Does NOT install hooks** (requires manual activation)
- ❌ **Does NOT create PROJECT.md** (optional bootstrap)
- ❌ **Does NOT validate dependencies** (Python, pytest, etc.)

### Step 2: Bootstrap (Complete Setup)

```bash
bash <(curl -sSL https://raw.githubusercontent.com/akaszubski/autonomous-dev/master/install.sh)
```

**What this does:**
- ✅ Detects plugin directory
- ✅ Validates installation
- ✅ Creates .claude/PROJECT.md
- ✅ Creates .claude/knowledge/ directory
- ✅ Generates installation report
- ⚠️ **Still does NOT install hooks** (separate step)

### Step 3: Hook Activation (Optional)

```bash
python ~/.claude/plugins/marketplaces/autonomous-dev/plugins/autonomous-dev/hooks/setup.py
```

**What this does:**
- ✅ Installs git hooks (pre-commit, pre-push)
- ✅ Configures hook activation
- ✅ Sets up automatic validation
- ⚠️ **Modifies .git/hooks** - can conflict with existing hooks

---

## Edge Cases & Failures

### 1. Partial Installation

**Problem**: Command execution interrupted during download
**Symptom**: Commands don't autocomplete after restart
**Cause**: Plugin directory incomplete, no marker file
**Fix**: Remove partial install, reinstall

```bash
rm -rf ~/.claude/plugins/marketplaces/autonomous-dev
/plugin install autonomous-dev
```

### 2. Version Conflict

**Problem**: Old version cached, new version won't load
**Symptom**: `/health-check` shows version mismatch
**Cause**: Claude Code caches old files, doesn't reload
**Fix**: Full cleanup and restart

```bash
# Remove all traces
rm -rf ~/.claude/plugins/marketplaces/autonomous-dev
rm -rf ~/.claude/cache/autonomous-dev
killall "Claude Code"  # Force quit
# Wait 10 seconds
# Restart Claude Code
/plugin install autonomous-dev
```

### 3. Missing Dependencies

**Problem**: Python libraries missing (pytest, PyYAML, etc.)
**Symptom**: `/test` command fails, agents error out
**Cause**: Plugin requires Python packages not in user environment
**Fix**: Install dependencies

```bash
pip install pytest pytest-cov pytest-xdist syrupy pytest-testmon PyYAML
```

### 4. Hook Conflicts

**Problem**: Existing git hooks conflict with autonomous-dev hooks
**Symptom**: Commits fail, hooks error out
**Cause**: `.git/hooks/pre-commit` already exists
**Fix**: Merge hooks manually or skip hook installation

### 5. PROJECT.md Drift

**Problem**: PROJECT.md exists but outdated (pre-v3.0)
**Symptom**: Alignment checks fail, features blocked
**Cause**: Bootstrap script doesn't update existing PROJECT.md
**Fix**: Manual update or re-bootstrap with force flag

### 6. Symlink Issues (Development)

**Problem**: `from autonomous_dev.lib import ...` fails
**Symptom**: Tests fail with ModuleNotFoundError
**Cause**: Python requires `autonomous_dev` (underscore), but directory is `autonomous-dev` (hyphen)
**Fix**: Create symlink

```bash
cd ~/.claude/plugins/marketplaces/autonomous-dev/plugins
ln -s autonomous-dev autonomous_dev
```

---

## Improved Installation Prompts

### Ultra-Comprehensive Installation

**Paste this for a COMPLETE setup (all features):**

```
Please install autonomous-dev with full validation and error handling:

STEP 1: Clean any existing installation
- Check if plugin exists: ls ~/.claude/plugins/marketplaces/autonomous-dev
- If exists, remove: rm -rf ~/.claude/plugins/marketplaces/autonomous-dev
- Clear cache: rm -rf ~/.claude/cache/autonomous-dev 2>/dev/null || true

STEP 2: Install plugin
- Run: /plugin marketplace add akaszubski/autonomous-dev
- Run: /plugin install autonomous-dev
- Verify download succeeded (directory should exist)

STEP 3: Restart check
- Tell me to restart Claude Code (Cmd+Q on Mac, Ctrl+Q on Windows/Linux)
- IMPORTANT: Wait for full process termination before reopening
- After restart, verify commands work: /auto-implement should autocomplete

STEP 4: Validate installation
- Run: /health-check
- Show me the results
- If ANY errors, stop and let me review before continuing

STEP 5: Bootstrap project (optional)
- Ask if I want to create PROJECT.md for strategic alignment
- If yes: run bootstrap script
- If no: explain I can run /setup later

STEP 6: Dependencies check
- Check Python version: python3 --version (need 3.9+)
- Check pytest: pytest --version
- If missing, show me installation command

STEP 7: Final verification
- Run a test command: /status
- List all available commands
- Explain next steps

If ANY step fails:
- Stop immediately
- Show me the exact error
- Suggest specific fix for that error
- Ask if I want to retry or troubleshoot

Ready to proceed? Let me know and I'll start with Step 1.
```

### Minimal Installation (Commands Only)

**Paste this for basic setup (no hooks, no bootstrap):**

```
Please install autonomous-dev (minimal setup, commands only):

1. Check for existing install: ls ~/.claude/plugins/marketplaces/autonomous-dev
2. If exists, ask me if I want to remove it first (recommended)
3. Run: /plugin marketplace add akaszubski/autonomous-dev
4. Run: /plugin install autonomous-dev
5. Tell me to restart Claude Code
6. After restart, verify: /auto-implement should autocomplete
7. Run: /health-check and show results

If anything fails, stop and show me the exact error message.

Note: This installs commands only. Hooks and PROJECT.md can be added later with /setup.
```

### Update/Upgrade Existing Installation

**Paste this to upgrade safely with backup:**

```
Please update my autonomous-dev installation safely:

STEP 1: Pre-update validation
- Run: /health-check and show current version
- Ask me to confirm I want to update (show what version I'm on)

STEP 2: Backup current installation
- Create backup: tar -czf ~/autonomous-dev-backup-$(date +%Y%m%d).tar.gz ~/.claude/plugins/marketplaces/autonomous-dev
- Confirm backup created and show location

STEP 3: Update plugin
- Run: /update-plugin
- OR if that fails: manual reinstall with version check

STEP 4: Post-update validation
- Tell me to restart Claude Code
- Run: /health-check and verify new version
- Run: /status to check functionality

STEP 5: Cleanup (if update successful)
- Ask if I want to remove backup (since update worked)
- If yes, remove backup file

If update fails:
- Keep backup
- Ask if I want to rollback to backup version
- Show me how to restore from backup

Proceed with Step 1?
```

---

## Testing Checklist

After any installation/update, verify:

- [ ] Commands autocomplete (type `/auto` and see suggestions)
- [ ] `/health-check` passes all checks
- [ ] `/status` shows project information
- [ ] Version matches latest (shown in /health-check)
- [ ] Python dependencies installed (pytest, etc.)
- [ ] Hooks installed (optional, check `.git/hooks/`)
- [ ] PROJECT.md exists (optional, check `.claude/PROJECT.md`)

If ANY item fails, investigate before using the plugin.

---

## Common Failure Modes & Fixes

| Symptom | Cause | Fix |
|---------|-------|-----|
| Commands don't autocomplete | Partial install or cache issue | Clean install (remove + reinstall) |
| /health-check shows version mismatch | Old version cached | Force quit + restart + reinstall |
| Tests fail (ModuleNotFoundError) | Missing symlink | Create `autonomous_dev` symlink |
| Hooks fail on commit | Hook conflict or missing deps | Skip hooks or merge manually |
| Alignment checks fail | Outdated PROJECT.md | Run /align-project to fix |
| Agent errors "tool not found" | Missing Python packages | Install pytest, PyYAML, etc. |
| /auto-implement times out | Context full from previous session | Run /clear before starting |

---

## Recommended Installation Path

**For most users (safest, most complete):**

1. Use "Ultra-Comprehensive Installation" prompt above
2. Let Claude guide through each step with validation
3. Stop and fix any errors before continuing
4. Run /health-check after completion
5. Try a simple feature: `/auto-implement "Add a comment to README"`

**For minimal testing:**

1. Use "Minimal Installation" prompt
2. Test commands work
3. Add hooks/bootstrap later with `/setup` if needed

**For upgrades:**

1. Use "Update/Upgrade" prompt
2. Always create backup first
3. Validate after update
4. Keep backup until confirmed working

---

**Why this matters**:

The original "paste one prompt" approach is great for simplicity, but real-world installations have edge cases. These improved prompts handle:
- Pre-flight checks
- Error recovery
- Version conflicts
- Partial installations
- Dependency validation
- Rollback capability

This is honest documentation - showing both the easy path AND the edge cases.
