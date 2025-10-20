---
description: Uninstall or disable autonomous-dev plugin features with guided options
---

# Uninstall or Disable Autonomous-Dev Plugin

Interactive command to remove or disable plugin features based on your needs.

## Usage

```bash
/uninstall
```

This command will guide you through removal options.

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
- `.claude/PROJECT.md` (your project goals and scope)
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
- `.claude/PROJECT.md`
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
- `.claude/PROJECT.md`
- `.claude/hooks/` (files remain but won't work without plugin)
- `.claude/templates/`
- `.claude/settings.local.json`

**Result**: Plugin removed from Claude Code entirely.

**Use when**: Done with autonomous-dev plugin across ALL your projects.

### Option 6: Cancel (No Changes)

Exits without making any changes.

---

## Implementation

When you run `/uninstall`, I will:

1. **Show you these 6 options** with clear descriptions
2. **Ask you to choose** which option you want
3. **Confirm your choice** before making changes
4. **Execute the removal** using appropriate commands:
   - **Project-level only** (Options 1-4):
     - `rm -rf .claude/hooks/` (if removing hooks)
     - `rm -rf .claude/templates/` (if removing templates)
     - `rm -f .claude/settings.local.json` (if removing settings)
     - `rm -f .claude/PROJECT.md` (if removing PROJECT.md)
     - `rm -f .env` (if removing GitHub config)
   - **Global removal** (Option 5 only):
     - `/plugin uninstall autonomous-dev` (removes plugin from Claude Code)
5. **Show what was removed** and what remains
6. **Provide next steps** based on your choice

**Important**: Options 1-4 only affect THIS PROJECT. Plugin remains installed in Claude Code for use in other projects.

---

## Example Sessions

### Example 1: Option 2 (Remove Project Files, Keep PROJECT.md)

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
- .claude/PROJECT.md (your project goals and scope)
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

| Option | Removes (from THIS project) | Keeps Globally | Use Case |
|--------|----------------------------|----------------|----------|
| 1 | settings.local.json | Plugin + everything else | Switch to manual mode |
| 2 | Hooks + templates + settings | Plugin + PROJECT.md | **Clean project, keep docs + plugin** ⭐ |
| 3 | Hooks + templates + settings | Plugin + PROJECT.md | Remove automation only |
| 4 | Hooks + templates + settings + PROJECT.md | Plugin | Fresh start this project |
| 5 | **Plugin globally** + project files | Nothing (complete removal) | Done with plugin everywhere |
| 6 | Nothing | Everything | Cancel operation |

**Key Difference**:
- **Options 1-4**: Project-level only (plugin still works in other projects)
- **Option 5**: Global removal (plugin removed from Claude Code entirely)

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