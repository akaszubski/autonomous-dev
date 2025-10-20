# Quick Reference: Refreshing Claude Code Settings

**When you modify the plugin, your project's `.claude/` folder needs to be refreshed.**

---

## One Command Solution

```bash
./scripts/refresh-claude-settings.sh
```

**What it syncs**:
- ✅ Agents (8 files) → `.claude/agents/`
- ✅ Commands (11 files) → `.claude/commands/`
- ✅ Skills (6 files) → `.claude/skills/`
- ✅ Hooks (10 files) → `.claude/hooks/`
- ✅ Verifies plugin symlink

**Result**: Changes active immediately (no restart!)

---

## When to Refresh

### ✅ YES - Refresh needed

- Modified agent definitions (`plugins/autonomous-dev/agents/*.md`)
- Modified command definitions (`plugins/autonomous-dev/commands/*.md`)
- Modified skill definitions (`plugins/autonomous-dev/skills/*/SKILL.md`)
- Modified hook scripts (`plugins/autonomous-dev/hooks/*.py`)

### ❌ NO - Refresh not needed

- Changed documentation (`docs/*.md`) - Not part of Claude settings
- Changed Python code (`scripts/*.py`, `tests/*.py`) - Imported dynamically
- Changed git hooks (`.git/hooks/`) - Managed separately
- Changed README, DEVELOPMENT.md, etc. - Not used by Claude

---

## Typical Development Workflow

```bash
# 1. Make changes to plugin
vim plugins/autonomous-dev/agents/orchestrator.md

# 2. Refresh Claude settings
./scripts/refresh-claude-settings.sh

# 3. Test in Claude immediately
# (No restart needed!)

# 4. Commit and push
git add plugins/autonomous-dev/agents/orchestrator.md
git commit -m "feat: enhance orchestrator"
git push
```

---

## Troubleshooting

### "Command not found" or "Changes not showing"

```bash
# Full refresh
./scripts/refresh-claude-settings.sh

# Verify files copied
ls -la .claude/agents/
ls -la .claude/commands/
ls -la .claude/skills/
ls -la .claude/hooks/
```

### "Script permission denied"

```bash
chmod +x scripts/refresh-claude-settings.sh
./scripts/refresh-claude-settings.sh
```

### "Want to see what changed"

```bash
# Before refresh - see differences
diff -r plugins/autonomous-dev/agents/ .claude/agents/

# After refresh - verify sync
diff -r plugins/autonomous-dev/agents/ .claude/agents/
# (Should show no differences)
```

---

## Architecture Diagram

```
Repository Structure:
plugins/autonomous-dev/          ← Source of truth (you edit here)
  ├── agents/
  ├── commands/
  ├── skills/
  └── hooks/

Project-Specific:
.claude/                         ← Active settings (synced via script)
  ├── agents/       ← Copied from plugin
  ├── commands/     ← Copied from plugin
  ├── skills/       ← Copied from plugin
  ├── hooks/        ← Copied from plugin
  ├── PROJECT.md    ← Project-specific
  └── settings.local.json ← Project-specific

Global Plugin:
~/.claude/plugins/autonomous-dev → Symlink to plugins/autonomous-dev/
```

**Flow**:
1. You edit `plugins/autonomous-dev/agents/X.md`
2. Run `./scripts/refresh-claude-settings.sh`
3. Changes copied to `.claude/agents/X.md`
4. Claude picks up changes immediately
5. Symlink at `~/.claude/plugins/` already up-to-date

---

## What Gets Synced Where

| File Type | Source | Destination | Sync Method |
|-----------|--------|-------------|-------------|
| Agents | `plugins/autonomous-dev/agents/` | `.claude/agents/` | Refresh script |
| Commands | `plugins/autonomous-dev/commands/` | `.claude/commands/` | Refresh script |
| Skills | `plugins/autonomous-dev/skills/` | `.claude/skills/` | Refresh script |
| Hooks | `plugins/autonomous-dev/hooks/` | `.claude/hooks/` | Refresh script |
| Plugin (global) | `plugins/autonomous-dev/` | `~/.claude/plugins/autonomous-dev` | Symlink (auto) |
| PROJECT.md | `.claude/PROJECT.md` | N/A | Project-specific |
| settings.local.json | `.claude/settings.local.json` | N/A | Project-specific |

---

## Remember

**Refresh after every plugin change** before testing in Claude!

```bash
./scripts/refresh-claude-settings.sh
```
