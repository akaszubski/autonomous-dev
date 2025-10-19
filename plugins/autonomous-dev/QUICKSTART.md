# Quick Start Guide - Autonomous Development Plugin

Get up and running in 3 minutes!

## Installation

```bash
# Add marketplace
/plugin marketplace add akaszubski/claude-code-bootstrap

# Install plugin
/plugin install autonomous-dev
```

## Setup (Choose One)

### Option 1: Interactive Setup (Recommended)

Run the setup wizard:
```bash
/setup
```

This will guide you through:
1. Copying hooks and templates from plugin to project
2. Choosing workflow (slash commands vs automatic hooks)
3. Setting up PROJECT.md
4. Configuring GitHub (optional)

### Option 2: Automated Setup

**For solo developers** (slash commands):
```bash
python .claude/scripts/setup.py --preset=solo
```

**For teams** (automatic hooks + GitHub):
```bash
python .claude/scripts/setup.py --preset=team
```

**Power users** (everything enabled):
```bash
python .claude/scripts/setup.py --preset=power-user
```

**Custom automated setup**:
```bash
# Slash commands + PROJECT.md
python .claude/scripts/setup.py --auto --hooks=slash-commands --project-md

# Automatic hooks + PROJECT.md + GitHub
python .claude/scripts/setup.py --auto --hooks=automatic --project-md --github
```

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

## Available Commands

### Development
- `/auto-implement` - Autonomous feature implementation (uses all 8 agents)
- `/commit` - Smart commit with conventional message

### Quality Checks (Slash Commands Mode)
- `/format` - Format code (black, prettier, gofmt)
- `/test` - Run tests with coverage
- `/security-scan` - Scan for secrets and vulnerabilities
- `/full-check` - Run all checks (format + test + security)

### Project Alignment
- `/align-project` - Validate project alignment with PROJECT.md
- `/setup` - Re-run setup wizard

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

### `.claude/PROJECT.md`
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

### "Hooks not running"
1. Check: `.claude/settings.local.json` exists
2. Check: Python 3.11+ installed
3. Try: `/setup` to reconfigure

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
- **GitHub issues**: https://github.com/akaszubski/claude-code-bootstrap/issues
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
