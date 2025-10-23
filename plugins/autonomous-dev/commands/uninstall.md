---
description: Uninstall or disable autonomous-dev plugin features with guided options
---

# Uninstall or Disable Autonomous-Dev Plugin

Interactive command to remove or disable plugin features based on your needs.

## Usage

### Interactive Mode (Guided)

```bash
/uninstall
```

Shows all 6 options and prompts you to choose.

### Direct Mode (Specify Option)

```bash
# Option 1: Disable automatic hooks
/uninstall --disable-hooks

# Option 2: Remove project files, keep PROJECT.md
/uninstall --clean-project

# Option 3: Remove hooks and templates only
/uninstall --remove-automation

# Option 4: Remove all project files including PROJECT.md
/uninstall --full-clean

# Option 5: Uninstall plugin globally
/uninstall --global

# Option 6: Show options (same as interactive)
/uninstall --help
```

**Aliases also work**:
```bash
/uninstall 1    # Same as --disable-hooks
/uninstall 2    # Same as --clean-project
/uninstall 3    # Same as --remove-automation
/uninstall 4    # Same as --full-clean
/uninstall 5    # Same as --global
```

---

## What This Command Does

Presents you with 6 options:

### Option 1: Disable Automatic Hooks Only

**Removes**:
- `.claude/settings.local.json` (hook configuration)

**Keeps**:
- Hooks in `.claude/hooks/` (for future use)
- Templates in `.claude/templates/`
- PROJECT.md
- Plugin (agents, skills, commands)

**Result**: Switches to slash commands mode. Run `/format`, `/test` manually.

**Use when**: You want manual control but keep plugin installed.

### Option 2: Remove Project Files Only (Keep PROJECT.md)

**Removes** (from THIS PROJECT only):
- `.claude/hooks/` directory (copied hooks)
- `.claude/templates/` directory (copied templates)
- `.claude/settings.local.json` (project hook configuration)
- `.env` (project GitHub config, if exists)

**Keeps** (in THIS PROJECT):
- `PROJECT.md` (your project goals and scope)
- Generated code in your project
- Tests that were created
- Session logs in `docs/sessions/`

**Keeps** (globally in Claude Code):
- Plugin installation (agents, skills, commands)
- Available for use in OTHER projects

**Result**: Project cleaned up, but plugin still available for other projects.

**Use when**: Done with autonomous dev in THIS PROJECT but want to keep plugin for other projects.

### Option 3: Remove Hooks and Templates Only

**Removes**:
- `.claude/hooks/` directory
- `.claude/templates/` directory
- `.claude/settings.local.json`

**Keeps**:
- PROJECT.md
- Plugin (agents, skills, commands still work)

**Result**: Can still use `/auto-implement`, `/align-project`, but no local hooks.

**Use when**: You want agent workflow but no automation hooks.

### Option 4: Remove All Project Files (Including PROJECT.md)

**Removes** (from THIS PROJECT only):
- `.claude/hooks/` directory
- `.claude/templates/` directory
- `.claude/settings.local.json`
- `PROJECT.md`
- `.env` (if exists)

**Keeps** (in THIS PROJECT):
- Generated code in your project
- Tests that were created
- Session logs in `docs/sessions/`

**Keeps** (globally in Claude Code):
- Plugin installation (still available for other projects)

**Result**: Complete project cleanup, plugin still available globally.

**Use when**: Done with autonomous dev in THIS PROJECT, want fresh start.

### Option 5: Uninstall Plugin Globally (All Projects)

**Removes** (GLOBALLY from Claude Code):
- Plugin via `/plugin uninstall autonomous-dev`
  - No longer available in ANY project
  - Agents, skills, commands removed

**Keeps** (in THIS PROJECT):
- `PROJECT.md`
- `.claude/hooks/` (files remain but won't work without plugin)
- `.claude/templates/`
- `.claude/settings.local.json`

**Result**: Plugin removed from Claude Code entirely.

**Use when**: Done with autonomous-dev plugin across ALL your projects.

### Option 6: Cancel (No Changes)

Exits without making any changes.

---

## Implementation

### Interactive Mode

When you run `/uninstall` (no arguments):

1. **Show you these 6 options** with clear descriptions
2. **Ask you to choose** which option you want
3. **Confirm your choice** before making changes
4. **Execute the removal** (see commands below)
5. **Show what was removed** and what remains
6. **Provide next steps** based on your choice

### Direct Mode

When you run `/uninstall 2` or `/uninstall --clean-project`:

1. **Parse the option** from your command
2. **Show what will be removed** for that specific option
3. **Confirm your choice** before making changes
4. **Execute the removal** immediately
5. **Show results** and next steps

### Removal Commands

**Project-level only** (Options 1-4):
- `rm -rf .claude/hooks/` (if removing hooks)
- `rm -rf .claude/templates/` (if removing templates)
- `rm -f .claude/settings.local.json` (if removing settings)
- `rm -f PROJECT.md` (if removing PROJECT.md)
- `rm -f .env` (if removing GitHub config)

**Global removal** (Option 5 only):
- `/plugin uninstall autonomous-dev` (removes plugin from Claude Code)

**Important**: Options 1-4 only affect THIS PROJECT. Plugin remains installed in Claude Code for use in other projects.

---

## Example Sessions

### Example 1: Interactive Mode

```
User: /uninstall

Claude: Choose an option:

[1] Disable automatic hooks only
[2] Remove project files only (keep PROJECT.md)
[3] Remove hooks and templates only
[4] Remove all project files (including PROJECT.md)
[5] Uninstall plugin globally (all projects)
[6] Cancel

Your choice: 2

Claude: You chose: Remove project files (keep PROJECT.md)

[Shows confirmation, executes removal...]

✓ Done! Plugin still available for other projects.
```

### Example 2: Direct Mode (Number)

```
User: /uninstall 2

Claude: You requested: Remove project files (keep PROJECT.md)

This will remove FROM THIS PROJECT:
✗ Hooks directory (.claude/hooks/)
✗ Templates directory (.claude/templates/)
✗ Settings file (.claude/settings.local.json)
✗ GitHub config (.env, if exists)

This will keep:
✓ PROJECT.md, code, tests, session logs
✓ Plugin installation (works in other projects)

Are you sure? [y/N]: y

[Executes removal...]

✓ Done!
```

### Example 3: Direct Mode (Named Option)

```
User: /uninstall --clean-project

Claude: You requested: Remove project files (keep PROJECT.md)

[Same as Example 2...]
```

### Example 4: Full Interactive Session (Option 2)

```
User: /uninstall

Claude: I'll help you uninstall or disable autonomous-dev plugin features.

Choose an option:

[1] Disable automatic hooks only (switch to slash commands)
[2] Remove project files only (keep PROJECT.md)
[3] Remove hooks and templates only
[4] Remove all project files (including PROJECT.md)
[5] Uninstall plugin globally (all projects)
[6] Cancel

Your choice: 2

Claude: You chose: Remove project files (keep PROJECT.md)

This will remove FROM THIS PROJECT:
✗ Hooks directory (.claude/hooks/)
✗ Templates directory (.claude/templates/)
✗ Settings file (.claude/settings.local.json)
✗ GitHub config (.env, if exists)

This will keep IN THIS PROJECT:
✓ PROJECT.md (your project goals)
✓ Generated code
✓ Tests
✓ Session logs

This will keep GLOBALLY:
✓ Plugin installation (still available for other projects)

Are you sure? [y/N]: y

Claude: Removing project files...

[Executes: rm -rf .claude/hooks/]
✓ Hooks removed

[Executes: rm -rf .claude/templates/]
✓ Templates removed

[Executes: rm -f .claude/settings.local.json]
✓ Settings removed

[Executes: rm -f .env]
✓ GitHub config removed (if existed)

Done! ✓

What remains in this project:
- PROJECT.md (your project goals and scope)
- Your generated code and tests
- Session logs in docs/sessions/

Plugin still available:
- You can still use autonomous-dev in OTHER projects
- Commands like /auto-implement work in other projects
- To use again in THIS project: /setup
```

### Example 2: Option 1 (Disable Hooks Only)

```
User: /uninstall

Claude: Choose an option:
[1] Disable automatic hooks only
...

Your choice: 1

Claude: Removing .claude/settings.local.json...

✓ Automatic hooks disabled

You're now in slash commands mode. Use:
- /format - Format code
- /test - Run tests
- /security-scan - Security check
- /full-check - All checks

To re-enable automatic hooks: /setup
```

### Example 3: Option 6 (Cancel)

```
User: /uninstall

Claude: Choose an option:
...
[6] Cancel

Your choice: 6

Claude: No changes made. Plugin remains installed.
```

---

## Quick Reference

| # | Command | Removes (THIS project) | Keeps Globally | Use Case |
|---|---------|------------------------|----------------|----------|
| 1 | `/uninstall --disable-hooks` or `/uninstall 1` | settings.local.json | Plugin + everything | Switch to manual |
| 2 | `/uninstall --clean-project` or `/uninstall 2` | Hooks + templates + settings | Plugin + PROJECT.md | **Clean project** ⭐ |
| 3 | `/uninstall --remove-automation` or `/uninstall 3` | Hooks + templates + settings | Plugin + PROJECT.md | Remove automation |
| 4 | `/uninstall --full-clean` or `/uninstall 4` | Hooks + templates + settings + PROJECT.md | Plugin | Fresh start |
| 5 | `/uninstall --global` or `/uninstall 5` | **Plugin globally** + project files | Nothing | Done everywhere ⚠️ |
| 6 | `/uninstall` or `/uninstall --help` | Nothing | Everything | Interactive menu |

**Key Difference**:
- **Options 1-4**: Project-level only (plugin still works in other projects)
- **Option 5**: Global removal (plugin removed from Claude Code entirely)

**Quick Commands**:
```bash
# Most common: Clean this project, keep docs and plugin
/uninstall 2

# Switch to manual mode
/uninstall 1

# Nuclear option: Remove from all projects
/uninstall 5
```

---

## After Uninstall

### If You Used Options 1-4 (Project-Level Only)

**In THIS project**:
- Project files cleaned up
- No automatic hooks or templates

**In OTHER projects**:
- Plugin still fully functional
- Can use /auto-implement, /setup, etc.
- All agents and skills available

**To use again in THIS project**:
```bash
/setup
```

### If You Used Option 5 (Global Removal)

**In ALL projects**:
- Slash commands no longer available
- Agents and skills removed
- Standard Claude Code behavior

**To reinstall globally**:
```bash
/plugin install autonomous-dev
```

Then in each project where you want to use it:
```bash
/setup
```

### If You Kept PROJECT.md

**Useful for**:
- Documenting project goals and scope
- Onboarding new developers
- Strategic planning with vanilla Claude Code
- Reference for any development work

---

## Related Commands

- `/setup` - Initial plugin configuration
- `/align-project` - Check alignment with PROJECT.md (requires plugin)