# Global vs Project Commands Guide

**Last Updated**: 2025-10-20

Guide to managing Claude Code commands across multiple projects.

---

## Command Locations

### Global Commands: `~/.claude/commands/`
- Available in **ALL projects**
- Should be **generic** and **project-agnostic**
- Examples: `/commit`, `/format`, `/test`, `/full-check`

### Project Commands: `.claude/commands/`
- Available in **THIS project only**
- Can be **project-specific**
- Examples: `/auto-implement`, `/align-project`, `/sync-docs`

---

## Current Global Commands

After cleanup (2025-10-20), only **generic** commands remain in `~/.claude/commands/`:

| Command | Purpose | Project-Specific? |
|---------|---------|-------------------|
| `/align-project` | Validate project alignment | ✅ From claude-code-bootstrap |
| `/auto-implement` | Autonomous feature implementation | ✅ From claude-code-bootstrap |
| `/commit` | Smart conventional commits | ❌ Generic |
| `/format` | Code formatting | ❌ Generic |
| `/full-check` | Complete quality checks | ❌ Generic |
| `/security-scan` | Security scanning | ❌ Generic |
| `/test` | Run tests | ❌ Generic |

**Total**: 7 commands

---

## Cleanup History

### 2025-10-20: Removed Project-Specific Commands

**Removed from global** (were from adaptive-mlx project):
- ❌ `add-feature.md` - Referenced `src/uncensored_mlx/`
- ❌ `learn-pattern.md` - MLX-specific pattern library
- ❌ `pattern-library.md` - MLX-specific patterns
- ❌ `README.md` - "Slash Commands for adaptive-mlx"
- ❌ `HOW_AUTOMATION_WORKS.md` - Project-specific
- ❌ `SAFE_AUTO_MODES.md` - Project-specific
- ❌ `fix-bug.md` - Part of adaptive-mlx command set
- ❌ `implement.md` - Part of adaptive-mlx command set
- ❌ `refactor.md` - Part of adaptive-mlx command set
- ❌ `release.md` - Part of adaptive-mlx command set
- ❌ `research.md` - Part of adaptive-mlx command set
- ❌ `session-end.md` - Part of adaptive-mlx command set
- ❌ `auto-doc-update.md` - From uncensored_mlx project
- ❌ `align-project-safe.md` - Now `--safe` flag

**Updated in global**:
- ✅ `align-project.md` - Added `--safe` and `--sync-github` flags
- ✅ `test.md` - Removed GenAI validation references

**Backup**: `~/.claude/commands-backup-20251020/`

---

## Guidelines

### What Should Be Global?

✅ **YES - Make it global if**:
- Works across **all projects**
- No project-specific paths or references
- Generic workflow (commit, test, format, etc.)
- You use it in multiple projects

Examples:
- `/commit` - Works with any git repo
- `/format` - Works with any language
- `/test` - Generic test runner

### What Should Be Project-Specific?

❌ **NO - Keep it project-specific if**:
- References specific directories (`src/uncensored_mlx/`)
- References specific files or modules
- Part of a specialized plugin
- Only relevant to one project

Examples:
- `/auto-implement` - Part of autonomous-dev plugin
- `/align-project` - Validates PROJECT.md (plugin-specific)
- `/sync-docs` - Links to doc-master agent (plugin-specific)

---

## Managing Multiple Projects

### Problem: Different Projects, Different Commands

**Before cleanup**:
```
~/.claude/commands/
├── add-feature.md        (adaptive-mlx)
├── align-project.md      (claude-code-bootstrap, outdated)
├── auto-doc-update.md    (uncensored_mlx)
├── learn-pattern.md      (adaptive-mlx)
└── ... (mixed)
```

**After cleanup**:
```
~/.claude/commands/
├── align-project.md      (generic, updated)
├── commit.md             (generic)
├── format.md             (generic)
├── full-check.md         (generic)
├── security-scan.md      (generic)
└── test.md               (generic)
```

### Solution 1: Keep Global Clean (Current Approach)

**Global**: Only generic commands
**Project**: Project-specific commands in `.claude/commands/`

```bash
# Working in claude-code-bootstrap
cd ~/claude-code-bootstrap
/align-project    # Uses .claude/commands/align-project.md
/sync-docs        # Uses .claude/commands/sync-docs.md
/commit           # Uses ~/.claude/commands/commit.md (global)

# Working in adaptive-mlx
cd ~/adaptive-mlx
/add-feature      # Uses .claude/commands/add-feature.md
/commit           # Uses ~/.claude/commands/commit.md (global)
```

**Pros**:
- Clear separation
- No conflicts
- Each project self-contained

**Cons**:
- Have to maintain commands per project
- Global commands duplicated if needed in multiple projects

### Solution 2: Project-Specific Global Directories (Alternative)

Create separate global command directories per project:

```bash
~/.claude/
├── commands/                           # Generic only
├── commands-claude-code-bootstrap/     # This project
└── commands-adaptive-mlx/              # Other project
```

**Setup**:
```bash
# In claude-code-bootstrap
ln -sf ~/.claude/commands-claude-code-bootstrap ~/.claude/commands-active
export CLAUDE_COMMANDS_DIR=~/.claude/commands-active

# In adaptive-mlx
ln -sf ~/.claude/commands-adaptive-mlx ~/.claude/commands-active
```

**Pros**:
- Complete isolation
- No conflicts ever
- Can maintain different versions

**Cons**:
- More complex
- Have to switch contexts manually
- Requires shell configuration

---

## Checking for Conflicts

To audit your commands for project-specific references:

```bash
# Search for project-specific keywords
grep -r "mlx\|uncensored\|adaptive" ~/.claude/commands/

# Find duplicates between global and project
comm -12 \
  <(ls -1 ~/.claude/commands/ | sort) \
  <(ls -1 .claude/commands/ | sort)

# Compare duplicates for differences
for cmd in $(comm -12 <(ls -1 ~/.claude/commands/) <(ls -1 .claude/commands/)); do
  diff -q ~/.claude/commands/$cmd .claude/commands/$cmd || echo "⚠️  $cmd differs"
done
```

---

## Backup & Recovery

### Creating Backups

```bash
# Backup before cleanup
mkdir -p ~/.claude/commands-backup-$(date +%Y%m%d)
cp ~/.claude/commands/*.md ~/.claude/commands-backup-$(date +%Y%m%d)/
```

### Restoring from Backup

```bash
# List backups
ls -d ~/.claude/commands-backup-*

# Restore specific command
cp ~/.claude/commands-backup-20251020/add-feature.md ~/.claude/commands/

# Restore all
cp ~/.claude/commands-backup-20251020/*.md ~/.claude/commands/
```

---

## Updating Global Commands

When a project updates a command that's also global:

```bash
# Check if project command differs from global
diff .claude/commands/align-project.md ~/.claude/commands/align-project.md

# Update global from project (if appropriate)
cp .claude/commands/align-project.md ~/.claude/commands/align-project.md

# Or use refresh script (if project has one)
./scripts/refresh-claude-settings.sh --global
```

---

## Best Practices

### 1. Keep Global Commands Minimal

Only put commands in `~/.claude/commands/` if they're:
- Used in 3+ projects
- Completely generic
- No project-specific references

### 2. Version Control Project Commands

```bash
# Project commands are versioned
git add .claude/commands/
git commit -m "feat: add sync-docs command"

# Global commands are NOT versioned
# They're in ~/.claude/ (outside project)
```

### 3. Document Command Ownership

Add to command frontmatter:

```markdown
---
description: Sync documentation with code
source: claude-code-bootstrap
generic: false  # This command is project-specific
---
```

### 4. Audit Regularly

```bash
# Monthly audit
/align-project               # Check project alignment
grep -r "project-name" ~/.claude/commands/  # Check for leaks
```

---

## FAQ

### Q: Should I commit `~/.claude/commands/` to git?

**No.** Global commands are per-user, not per-project. Only commit `.claude/commands/`.

### Q: What if two projects need different versions of `/test`?

Keep `/test` in each project's `.claude/commands/`. Remove from global.

### Q: Can I have both global and project versions of same command?

Yes! Project commands override global. If both exist, project version wins.

### Q: How do I know which command is running?

```bash
# Check which file Claude will use
ls -la ~/.claude/commands/align-project.md  # Global
ls -la .claude/commands/align-project.md    # Project (wins if exists)
```

### Q: What's the precedence order?

1. **Project commands** (`.claude/commands/`) - Highest priority
2. **Global commands** (`~/.claude/commands/`)
3. **Built-in commands** (Claude Code built-ins)

---

## Migration Checklist

When setting up a new project with commands:

- [ ] Install plugin: `/plugin install autonomous-dev`
- [ ] Review project commands: `ls .claude/commands/`
- [ ] Check for global conflicts: Compare with `~/.claude/commands/`
- [ ] Remove project-specific from global (if any)
- [ ] Update outdated global commands (if needed)
- [ ] Document which commands are project-specific
- [ ] Test commands work: `/align-project`, `/sync-docs`, etc.

---

**Related**:
- [QUICKSTART.md](../QUICKSTART.md) - Available commands
- [DEVELOPMENT.md](DEVELOPMENT.md) - Development workflow
- [TROUBLESHOOTING.md](TROUBLESHOOTING.md) - Command issues

---

**Summary**: Global commands should be **generic** and work across all projects. Project-specific commands go in `.claude/commands/`. Audit regularly to prevent cross-contamination.
