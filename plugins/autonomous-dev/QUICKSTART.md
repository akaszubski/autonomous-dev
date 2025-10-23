# Quick Start Guide - Autonomous Development Plugin

Get up and running in 3 minutes!

## Installation

```bash
# 1. Add marketplace
/plugin marketplace add akaszubski/autonomous-dev

# 2. Install plugin
/plugin install autonomous-dev

# 3. Exit and restart Claude Code (REQUIRED!)
# Press Cmd+Q (Mac) or Ctrl+Q (Linux/Windows)
```

**Done!** All commands work immediately: `/test`, `/format`, `/commit`, etc.

### Updating the Plugin

```bash
# 1. Uninstall
/plugin uninstall autonomous-dev

# 2. Exit and restart Claude Code (REQUIRED!)
# Press Cmd+Q (Mac) or Ctrl+Q (Linux/Windows)

# 3. Reinstall
/plugin install autonomous-dev

# 4. Exit and restart again
```

**IMPORTANT**: You must exit and restart Claude Code after both uninstall AND install!

---

## Optional Setup (Advanced)

**Most users don't need this!** All commands work immediately after installation.

**Only run setup if you want automatic hooks** (auto-format on save, auto-test on commit):

### Option 1: Interactive Setup (Recommended)

```bash
python plugins/autonomous-dev/scripts/setup.py
```

This wizard helps you:
1. Enable automatic formatting when you save files
2. Enable automatic testing when you commit
3. Create PROJECT.md from template
4. Configure GitHub integration (.env file)
5. **Asks before overwriting any existing files** (safe!)

### Option 2: Automated Setup

**For solo developers** (slash commands only - no setup needed!):
```bash
# Just use the commands - no setup required
/format
/test
/commit
```

**For teams** (automatic hooks + GitHub):
```bash
python plugins/autonomous-dev/scripts/setup.py --preset=team
```

**Power users** (everything enabled):
```bash
python plugins/autonomous-dev/scripts/setup.py --preset=power-user
```

**Custom automated setup**:
```bash
# Slash commands + PROJECT.md
python plugins/autonomous-dev/scripts/setup.py --auto --hooks=slash-commands --project-md

# Automatic hooks + PROJECT.md + GitHub
python plugins/autonomous-dev/scripts/setup.py --auto --hooks=automatic --project-md --github
```

**Note**: The setup script always asks before overwriting existing files unless you use `--auto` mode.

## First Feature

### Using Slash Commands (Default)

```bash
# 1. Describe your feature
"implement a hello world function with tests"

# 2. Let Claude implement it
/auto-implement

# 3. Before committing, run quality checks
/full-check

# 4. Commit with smart message
/commit
```

### Using Automatic Hooks

```bash
# 1. Describe your feature
"implement a hello world function with tests"

# 2. Let Claude implement it
/auto-implement

# 3. Commit (hooks run automatically)
git commit -m "feat: add hello world function"
```

## Available Commands (33 Total)

### Quick Reference
**Testing**: `/test`, `/test-unit`, `/test-integration`, `/test-uat`, `/test-uat-genai`, `/test-architecture`, `/test-complete`

**Commit**: `/commit`, `/commit-check`, `/commit-push`, `/commit-release`

**Alignment**: `/align-project`, `/align-project-fix`, `/align-project-safe`, `/align-project-sync`, `/align-project-dry-run`

**Issues**: `/issue-auto`, `/issue-from-test`, `/issue-from-genai`, `/issue-create`, `/issue-preview`

**Docs**: `/sync-docs`, `/sync-docs-api`, `/sync-docs-changelog`, `/sync-docs-organize`, `/sync-docs-auto`

**Quality**: `/format`, `/security-scan`, `/full-check`

**Workflow**: `/auto-implement`, `/setup`, `/uninstall`

### Most Used Commands

**Daily development**:
- `/test-unit` - Fast unit tests (< 1s)
- `/commit` - Quick commit (< 5s)
- `/format` - Format code

**Feature completion**:
- `/test` - All automated tests
- `/commit-check` - Full validation
- `/commit-push` - Push to GitHub

**Pre-release**:
- `/test-complete` - Complete validation
- `/commit-release` - Production release

See [docs/COMMANDS.md](../../docs/COMMANDS.md) for complete reference.

## Workflows

### Slash Commands Workflow
```
┌─────────────────────────────────────────┐
│ 1. Describe feature                     │
│ 2. /auto-implement                      │
│ 3. /full-check (before commit)          │
│ 4. /commit                              │
│ 5. /clear (reset context)               │
└─────────────────────────────────────────┘
```

### Automatic Hooks Workflow
```
┌─────────────────────────────────────────┐
│ 1. Describe feature                     │
│ 2. /auto-implement                      │
│ 3. git commit (hooks run automatically) │
│ 4. /clear (reset context)               │
└─────────────────────────────────────────┘
```

## Configuration Files

### `PROJECT.md`
Strategic direction for your project:
- **GOALS**: What success looks like
- **SCOPE**: What's in/out of scope
- **CONSTRAINTS**: Technical limits
- **CURRENT SPRINT**: Active work

All agents validate against this before working!

### `.claude/settings.local.json` (If using automatic hooks)
```json
{
  "hooks": {
    "PostToolUse": {
      "Write": ["python .claude/hooks/auto_format.py"],
      "Edit": ["python .claude/hooks/auto_format.py"]
    },
    "PreCommit": {
      "*": [
        "python .claude/hooks/auto_test.py",
        "python .claude/hooks/security_scan.py"
      ]
    }
  }
}
```

### `.env` (If using GitHub integration)
```bash
# GitHub Personal Access Token
GITHUB_TOKEN=ghp_your_token_here
```

## Switching Workflows

### From Slash Commands → Automatic Hooks

```bash
# Copy template
cp .claude/templates/settings.local.json .claude/settings.local.json

# Or run setup again
python .claude/scripts/setup.py --auto --hooks=automatic
```

### From Automatic Hooks → Slash Commands

```bash
# Remove hooks config
rm .claude/settings.local.json

# Use slash commands instead
/format
/test
/security-scan
```

## Troubleshooting

### "Commands not available after install"

**Solution:** Exit and restart Claude Code (Cmd+Q or Ctrl+Q)

After restarting, test by typing:
```bash
/test
/format
/commit
```

All 33 commands should appear in autocomplete.

### Still not working?

```bash
# 1. Check if plugin is installed
ls ~/.claude/plugins/autonomous-dev

# 2. Reinstall completely
/plugin uninstall autonomous-dev
# Exit and restart Claude Code
/plugin install autonomous-dev
# Exit and restart Claude Code again
```

### "Hooks not running" (if you ran the optional setup)

1. Check: `.claude/settings.local.json` exists
2. Check: Python 3.11+ installed
3. Try: Re-run `python plugins/autonomous-dev/scripts/setup.py`

### "Tests failing"
1. Check: Test framework installed (pytest/jest)
2. Run: `/test` to see details
3. Fix failing tests before committing

### "Context too large"
1. Run: `/clear` after each feature
2. This resets context budget
3. Session logs saved to `docs/sessions/`

### "GitHub auth failed"
1. Check: `.env` file has valid token
2. Check: Token has `repo` scope
3. See: `.claude/docs/GITHUB_AUTH_SETUP.md`

## Pro Tips

1. **Clear context regularly**: Run `/clear` after each feature to keep context under 8K tokens

2. **Start simple**: Begin with slash commands, enable hooks once comfortable

3. **Check alignment**: Run `/align-project` to validate project structure

4. **Use presets for teams**: Standardize setup across team with `--preset=team`

5. **Customize PROJECT.md**: Tailor GOALS/SCOPE to your specific project

## Next Steps

1. **Complete PROJECT.md**: Fill in your project's goals and constraints
2. **Try a feature**: Implement something small to learn the workflow
3. **Check coverage**: Run `/test` to see current test coverage
4. **Read docs**: See `.claude/README.md` for complete documentation

## Support

- **Plugin docs**: `.claude/README.md` (installed)
- **GitHub issues**: https://github.com/akaszubski/autonomous-dev/issues
- **Testing guide**: `tests/README.md`

## Summary

```bash
# Install
/plugin install autonomous-dev

# Setup (choose one)
/setup                                    # Interactive
python .claude/scripts/setup.py --preset=solo  # Automated

# First feature
/auto-implement

# Quality check
/full-check

# Commit
/commit

# Clear context
/clear
```

**You're ready to go! 🚀**
