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

### Option 2: Remove All Plugin Files (Keep PROJECT.md)

**Removes**:
- Plugin via `/plugin uninstall autonomous-dev`
  - Agents (orchestrator, researcher, planner, etc.)
  - Skills (python-standards, testing-guide, etc.)
  - Commands (/auto-implement, /format, /test, etc.)
- `.claude/hooks/` directory
- `.claude/templates/` directory
- `.claude/settings.local.json`
- `.env` (if exists)

**Keeps**:
- `.claude/PROJECT.md` (your project goals and scope)
- Generated code in your project
- Tests that were created
- Session logs in `docs/sessions/`

**Result**: Back to vanilla Claude Code, but PROJECT.md remains for reference.

**Use when**: Done with autonomous dev but want to keep project documentation.

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

### Option 4: Complete Uninstall (Remove Everything)

**Removes**:
- Plugin via `/plugin uninstall autonomous-dev`
- `.claude/hooks/`
- `.claude/templates/`
- `.claude/settings.local.json`
- `.claude/PROJECT.md`
- `.env` (if exists)

**Keeps**:
- Generated code in your project
- Tests that were created
- Session logs in `docs/sessions/`

**Result**: Complete removal, back to vanilla Claude Code.

**Use when**: Done with autonomous development entirely.

### Option 5: Remove Plugin, Keep PROJECT.md and Hooks

**Removes**:
- Plugin via `/plugin uninstall autonomous-dev`
  - Agents, skills, commands removed

**Keeps**:
- `.claude/PROJECT.md`
- `.claude/hooks/` (can still use manually)
- `.claude/templates/`
- `.claude/settings.local.json`

**Result**: Hooks remain but won't auto-trigger (no plugin to trigger them).

**Use when**: Want to keep project structure but remove agent automation.

### Option 6: Cancel (No Changes)

Exits without making any changes.

---

## Implementation

When you run `/uninstall`, I will:

1. **Show you these 6 options** with clear descriptions
2. **Ask you to choose** which option you want
3. **Confirm your choice** before making changes
4. **Execute the removal** using appropriate commands:
   - `/plugin uninstall autonomous-dev` (if removing plugin)
   - `rm -rf .claude/hooks/` (if removing hooks)
   - `rm -rf .claude/templates/` (if removing templates)
   - `rm -f .claude/settings.local.json` (if removing settings)
   - `rm -f .env` (if removing GitHub config)
5. **Show what was removed** and what remains
6. **Provide next steps** based on your choice

---

## Example Sessions

### Example 1: Option 2 (Remove All Plugin Files, Keep PROJECT.md)

```
User: /uninstall

Claude: I'll help you uninstall or disable autonomous-dev plugin features.

Choose an option:

[1] Disable automatic hooks only (switch to slash commands)
[2] Remove all plugin files (keep PROJECT.md only)
[3] Remove hooks and templates only
[4] Complete uninstall (remove everything)
[5] Remove plugin, keep PROJECT.md and hooks
[6] Cancel

Your choice: 2

Claude: You chose: Remove all plugin files (keep PROJECT.md)

This will remove:
✗ Plugin installation (agents, skills, commands)
✗ Hooks directory (.claude/hooks/)
✗ Templates directory (.claude/templates/)
✗ Settings file (.claude/settings.local.json)
✗ GitHub config (.env, if exists)

This will keep:
✓ PROJECT.md (your project goals)
✓ Generated code
✓ Tests
✓ Session logs

Are you sure? [y/N]: y

Claude: Removing plugin files...

[Executes: /plugin uninstall autonomous-dev]
✓ Plugin uninstalled

[Executes: rm -rf .claude/hooks/]
✓ Hooks removed

[Executes: rm -rf .claude/templates/]
✓ Templates removed

[Executes: rm -f .claude/settings.local.json]
✓ Settings removed

[Executes: rm -f .env]
✓ GitHub config removed (if existed)

Done! ✓

What remains:
- .claude/PROJECT.md (your project goals and scope)
- Your generated code and tests
- Session logs in docs/sessions/

Next steps:
- You can still use Claude Code normally
- PROJECT.md is available for reference
- To reinstall: /plugin install autonomous-dev
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

| Option | Removes | Keeps | Use Case |
|--------|---------|-------|----------|
| 1 | settings.local.json | Everything else | Switch to manual mode |
| 2 | Plugin + hooks + templates | PROJECT.md only | **Done with plugin, keep docs** |
| 3 | Hooks + templates | Plugin + PROJECT.md | Keep agents, remove automation |
| 4 | Everything | Generated code/tests | Complete removal |
| 5 | Plugin only | PROJECT.md + hooks | Keep structure, remove agents |
| 6 | Nothing | Everything | Cancel operation |

---

## After Uninstall

Depending on your choice:

**If you kept PROJECT.md**:
- Still useful for documenting project goals
- Can be used with vanilla Claude Code
- Easy to reference for any development work

**If you removed the plugin**:
- Slash commands no longer available
- Agents and skills removed
- Standard Claude Code behavior

**To reinstall**:
```bash
/plugin install autonomous-dev
/setup
```

---

## Related Commands

- `/setup` - Initial plugin configuration
- `/align-project` - Check alignment with PROJECT.md (requires plugin)