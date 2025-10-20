# Contributing to Claude Code Bootstrap

**This repository builds Claude Code automation tools for distribution.**

---

## Important: File Locations

### ✅ ALWAYS Edit These (Git-Tracked)

All changes MUST go to these locations:

```
.claude/                          # Project-specific config
├── commands/                     # Slash commands
├── PROJECT.md                    # Project architecture
└── hooks/                        # Git hooks

plugins/autonomous-dev/           # Plugin for marketplace
├── commands/                     # Slash commands (same as .claude/commands/)
├── agents/                       # AI agents
├── skills/                       # Skills
├── hooks/                        # Automation hooks
└── marketplace.json              # Plugin metadata
```

### ❌ NEVER Edit These (Personal Config)

These are your personal global settings, NOT for git:

```
~/.claude/                        # Your personal config (NOT IN GIT)
├── commands/                     # Don't edit manually
├── CLAUDE.md                     # Your personal instructions
└── settings.json                 # Your personal settings
```

---

## Workflow for Changes

### Adding/Updating Commands

**Always edit in BOTH locations**:

```bash
# 1. Edit project config
vim .claude/commands/my-command.md

# 2. Copy to plugin
cp .claude/commands/my-command.md plugins/autonomous-dev/commands/

# 3. Commit to git
git add .claude/commands/ plugins/autonomous-dev/commands/
git commit -m "feat: add my-command"

# 4. Push to GitHub
git push

# 5. Test by reloading plugin
# In Claude Code:
# /plugin uninstall autonomous-dev
# /plugin install autonomous-dev
```

### Adding/Updating Agents

```bash
# Edit in plugin directory only
vim plugins/autonomous-dev/agents/my-agent.md

# Commit and push
git add plugins/autonomous-dev/agents/
git commit -m "feat: add my-agent"
git push
```

### Adding/Updating Skills

```bash
# Edit in plugin directory only
vim plugins/autonomous-dev/skills/my-skill.md

# Commit and push
git add plugins/autonomous-dev/skills/
git commit -m "feat: add my-skill"
git push
```

---

## Helper Scripts

Use the sync script to ensure consistency:

```bash
# Sync commands from .claude to plugin
./scripts/sync-plugin.sh

# This ensures both locations stay in sync
```

---

## Before Committing

**Checklist**:
- [ ] Changes are in `.claude/` or `plugins/autonomous-dev/`
- [ ] NOT in `~/.claude/` (personal config)
- [ ] Commands synced to both `.claude/commands/` and `plugins/autonomous-dev/commands/`
- [ ] Committed to git
- [ ] Pushed to GitHub
- [ ] Tested by reloading plugin

---

## Testing Changes

After making changes:

1. **Commit and push to GitHub**:
   ```bash
   git add .
   git commit -m "feat: your change"
   git push
   ```

2. **Reload plugin in Claude Code**:
   ```bash
   /plugin uninstall autonomous-dev
   /plugin install autonomous-dev
   ```

3. **Test the changes**:
   ```bash
   /your-new-command
   ```

---

## Directory Structure

```
claude-code-bootstrap/
├── .claude/                      ← Project config (git-tracked)
│   ├── commands/                 ← Commands (sync to plugin)
│   ├── PROJECT.md                ← Architecture
│   └── hooks/                    ← Git hooks
├── plugins/
│   └── autonomous-dev/           ← Plugin (git-tracked)
│       ├── commands/             ← Commands (synced from .claude)
│       ├── agents/               ← AI agents
│       ├── skills/               ← Skills
│       ├── hooks/                ← Automation hooks
│       └── marketplace.json      ← Plugin metadata
├── docs/                         ← Documentation (git-tracked)
└── scripts/                      ← Helper scripts (git-tracked)

~/.claude/                        ← Personal config (NOT in git)
├── commands/                     ← Auto-populated by plugin install
└── CLAUDE.md                     ← Your personal instructions
```

---

## Key Principle

**This repository is the SOURCE OF TRUTH for the autonomous-dev plugin.**

All changes must be:
1. Made in git-tracked locations
2. Committed to git
3. Pushed to GitHub
4. Distributed via marketplace

Personal `~/.claude/` folder is just where the plugin gets INSTALLED, not where you develop.
