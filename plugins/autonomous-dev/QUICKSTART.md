# Quick Start Guide - Autonomous Development Plugin

Get up and running in 2 minutes!

## Installation (Copy-Paste This)

**In your project folder:**

```bash
bash <(curl -sSL https://raw.githubusercontent.com/akaszubski/autonomous-dev/master/install.sh)
```

**That's it!** The script does everything:
- Checks if plugin is installed
- Guides you to install if needed
- Copies files to your project
- Shows next steps

**First run?** You'll see:
```
❌ Plugin not found
Install: /plugin marketplace add akaszubski/autonomous-dev
         /plugin install autonomous-dev
Restart Claude Code, then run this command again.
```

**After installing plugin**, run the same curl command. Restart. Done!

✅ All 8 commands work: `/auto-implement`, `/align-project`, `/setup`, `/test`, `/status`, `/health-check`, `/align-claude`, `/uninstall`

### Updating (Same Command!)

**When new version released:**

```bash
bash <(curl -sSL https://raw.githubusercontent.com/akaszubski/autonomous-dev/master/install.sh)
```

**Same command!** Always gets latest. Or use:

```bash
/update-plugin  # Inside Claude Code
```

Both work. Always restart after (Cmd+Q, not `/exit`).

---

## Optional Setup (Advanced)

**Most users don't need this!** All commands work immediately after installation.

**Only run setup if you want automatic hooks** (auto-format on save, auto-test on commit):

### Option 1: Interactive Setup (Recommended)

```bash
/setup
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
/auto-implement "your feature description"
/test
```

**For teams** (automatic hooks + GitHub):
```bash
/setup
# Then select: Automatic hooks, PROJECT.md, GitHub integration
```

**Power users** (everything enabled):
```bash
/setup
# Then select: All options
```

**Note**: The /setup command always asks before overwriting existing files.

## First Feature

### Using Slash Commands (Default)

```bash
# 1. Implement feature with autonomous pipeline
/auto-implement "implement a hello world function with tests"

# This automatically:
# - Validates alignment with PROJECT.md
# - Researches best practices
# - Plans architecture
# - Writes tests (TDD)
# - Implements code
# - Reviews quality
# - Scans security
# - Updates docs

# 2. Optionally run tests manually
/test

# 3. Commit changes (hooks validate automatically)
git add .
git commit -m "feat: add hello world function"
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
/setup
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
3. Try: Re-run `/setup`

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
/setup  # Interactive wizard

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
