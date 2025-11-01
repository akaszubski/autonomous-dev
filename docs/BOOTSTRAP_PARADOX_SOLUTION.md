# Bootstrap Paradox - Investigation and Solution

**Date**: 2025-11-02
**Issue**: Plugin commands not accessible after installation
**Status**: RESOLVED

---

## The Problem

Users installing the `autonomous-dev` plugin encountered a "bootstrap paradox":

1. `/setup` command is designed to copy plugin files to projects
2. But `/setup` itself wasn't available after plugin installation
3. Manual copying of commands was required (defeating the purpose of `/setup`)

---

## Investigation Findings

### How Claude Code Plugin System Works

**Plugin Installation:**
- Plugins install globally to: `~/.claude/plugins/marketplaces/{marketplace}/{plugin}/`
- Plugin is enabled in: `~/.claude/settings.json` → `"enabledPlugins"`
- Components (commands, agents, skills, hooks) stay in plugin directory

**Command Discovery:**
According to [Claude Code docs](https://docs.claude.com/en/docs/claude-code/plugins-reference):
- Commands are discovered from plugin's `commands/` directory automatically
- NO copying to project's `.claude/commands/` is required
- Commands integrate seamlessly after plugin installation + restart

**Key Quote from Docs:**
> "Plugin commands support namespacing with the format `/plugin-name:command-name` to avoid naming conflicts, though the plugin prefix is optional when there are no collisions."

### Root Cause

The issue had **two possible causes**:

#### Cause 1: Namespace Collision
If a project already has commands with the same name (e.g., `setup.md`), the plugin commands might be hidden. Solution: Use namespaced format.

#### Cause 2: Incomplete Restart
Claude Code requires a **full application restart** (Cmd+Q / Ctrl+Q), not just `/exit`, to load new plugins.

---

## The Solution

### Primary Solution: Use Namespaced Commands

After installing the plugin and restarting Claude Code completely:

```bash
/autonomous-dev:setup          # Instead of /setup
/autonomous-dev:auto-implement # Instead of /auto-implement
/autonomous-dev:align-project  # Instead of /align-project
```

### Alternative: Check for Name Collisions

If your project has existing commands with the same names, rename or remove them:

```bash
cd .claude/commands/
ls -la  # Check for: setup.md, auto-implement.md, etc.
mv setup.md old-setup.md  # Rename conflicts
```

Then restart Claude Code and try unnamespaced commands:

```bash
/setup
/auto-implement
```

---

## What We Built (But Don't Need)

During investigation, we created an auto-bootstrap solution:

**File**: `plugins/autonomous-dev/hooks/auto_bootstrap.py`
**Purpose**: SessionStart hook that copies commands to `.claude/commands/` automatically
**Status**: **NOT NEEDED** - Claude Code already does this via plugin system

**Why we don't need it**:
- Creates redundant file copies
- Violates Claude Code's plugin architecture
- Commands are already accessible via plugin system
- Adds unnecessary complexity

---

## Correct Plugin Architecture

### What Plugin SHOULD Do
✅ Provide commands in `{plugin}/commands/` directory
✅ Let Claude Code handle command discovery
✅ Use namespacing to avoid conflicts
✅ Document that full restart is required

### What Plugin SHOULD NOT Do
❌ Copy commands to every project's `.claude/commands/`
❌ Use SessionStart hooks for file copying
❌ Try to "bootstrap" files that Claude Code already provides access to
❌ Fight against the plugin system's design

---

## Recommended Changes

### 1. Update README.md

Add clear installation instructions:

```markdown
## Installation

1. Add marketplace:
   ```bash
   /plugin marketplace add akaszubski/autonomous-dev
   ```

2. Install plugin:
   ```bash
   /plugin install autonomous-dev
   ```

3. **IMPORTANT**: Completely quit and restart Claude Code (Cmd+Q or Ctrl+Q)

4. Verify installation:
   ```bash
   /help  # Should show autonomous-dev commands
   ```

5. Run setup (use namespaced format if needed):
   ```bash
   /autonomous-dev:setup
   # OR (if no name conflicts)
   /setup
   ```

### If commands don't appear:
- Use namespaced format: `/autonomous-dev:setup`
- Check for name collisions in `.claude/commands/`
- Verify plugin is enabled: check `~/.claude/settings.json`
```

### 2. Remove Auto-Bootstrap Hook

The SessionStart hook we created is unnecessary and should be removed:

```bash
# Remove from default-settings.json
vim plugins/autonomous-dev/.claude-plugin/default-settings.json
# Delete the SessionStart hook section

# Optional: Keep auto_bootstrap.py for reference but don't use it
```

### 3. Update `/setup` Command Documentation

Clarify that `/setup` is for configuring the plugin AFTER it's accessible, not for making it accessible:

```markdown
# /setup Command

**Purpose**: Configure plugin settings and copy templates/hooks to your project

**When to use**: After plugin is installed and commands are accessible

**Not for**: Making plugin commands available (that's automatic)
```

---

## Testing Checklist

To verify the fix works:

- [ ] Fresh project (no `.claude/` directory)
- [ ] Install plugin via marketplace
- [ ] Completely restart Claude Code (Cmd+Q)
- [ ] Open fresh project
- [ ] Run `/help` - verify autonomous-dev commands listed
- [ ] Run `/autonomous-dev:setup` - verify it works
- [ ] OR run `/setup` if no conflicts

---

## Lessons Learned

1. **Trust the platform** - Claude Code's plugin system works as documented
2. **RTFM carefully** - "Automatic discovery" means what it says
3. **Namespace is your friend** - Use it to avoid collisions
4. **Don't over-engineer** - We don't need to copy files that are already accessible
5. **Full restart != /exit** - Application restart is required for plugins

---

## References

- [Claude Code Plugins Docs](https://docs.claude.com/en/docs/claude-code/plugins)
- [Plugins Reference](https://docs.claude.com/en/docs/claude-code/plugins-reference)
- [Slash Commands](https://docs.claude.com/en/docs/claude-code/slash-commands)
