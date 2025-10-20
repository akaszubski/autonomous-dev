# Quick Start - Get Running in 2 Minutes

**Last Updated**: 2025-10-20

---

## 1. Install Plugin

```bash
# Add this marketplace
/plugin marketplace add akaszubski/claude-code-bootstrap

# Install autonomous development plugin
/plugin install autonomous-dev
```

**Done!** The plugin is now installed.

---

## 2. First Feature

Try implementing a simple feature:

```bash
# Describe what you want
"Add a hello world function with tests"

# Let Claude autonomously implement it
/auto-implement
```

**What happens**:
1. orchestrator validates alignment with PROJECT.md
2. researcher finds best practices
3. planner creates implementation plan
4. test-master writes tests first (TDD)
5. implementer makes tests pass
6. reviewer checks quality
7. security-auditor scans for issues
8. doc-master updates documentation

**Total time**: ~30 minutes, fully autonomous

---

## 3. Quality Check & Commit

```bash
# Run all quality checks
/full-check

# Commit with smart message
/commit
```

---

## 4. Clear Context (Important!)

```bash
# After each feature, clear context
/clear
```

**Why**: Keeps context under 8K tokens, enables 100+ features per session

---

## Available Commands

### Development
- `/auto-implement` - Autonomous feature implementation (8-agent pipeline)
- `/commit` - Smart commit with conventional message

### Quality Checks
- `/format` - Format code (black, prettier)
- `/test` - Run tests with coverage
- `/security-scan` - Scan for secrets & vulnerabilities
- `/full-check` - All checks (format + test + security)

### Project Alignment
- `/align-project` - Validate alignment with PROJECT.md
- `/align-project --safe` - Safe 3-phase alignment workflow
- `/align-project --sync-github` - Sync with GitHub (create milestones/issues)

### Documentation
- `/sync-docs` - Sync documentation with code changes
- `/sync-docs --auto` - Auto-detect and sync based on git changes
- `/sync-docs --organize` - Organize .md files into docs/

---

## Workflow

```
┌─────────────────────────────────────────────────┐
│ 1. Describe feature                             │
│ 2. /auto-implement  (orchestrator coordinates)  │
│ 3. /full-check      (validate quality)          │
│ 4. /commit          (smart commit message)      │
│ 5. /clear           (reset context)             │
└─────────────────────────────────────────────────┘
```

---

## What You Get

### 8 Specialized Agents
- **orchestrator** - Master coordinator (validates PROJECT.md alignment)
- **researcher** - Web research for best practices
- **planner** - Architecture & implementation planning
- **test-master** - TDD specialist (writes tests first)
- **implementer** - Code implementation
- **reviewer** - Quality gate checks
- **security-auditor** - Security scanning
- **doc-master** - Documentation sync

### 6 Core Skills
- **python-standards** - PEP 8, type hints, docstrings
- **testing-guide** - TDD workflow, pytest patterns
- **security-patterns** - OWASP, secrets management
- **documentation-guide** - Docstring format, README updates
- **research-patterns** - Web search strategies
- **engineering-standards** - Code quality standards

### Auto-Everything
- **Auto-format**: black, isort (Python), prettier (JS/TS)
- **Auto-test**: pytest (Python), jest (JS/TS)
- **Auto-coverage**: 80%+ minimum enforced
- **Auto-security**: Secrets detection, vulnerability scanning
- **Auto-docs**: README, CHANGELOG, docstrings synced

---

## Troubleshooting

### "Context too large"
```bash
/clear  # Then retry
```

### "Hooks not running"
Check Python 3.11+ is installed and hooks exist in `.claude/hooks/`

### "Tests failing"
```bash
/test  # See details
# Fix failing tests before committing
```

### "GitHub auth failed"
1. Create `.env` file with `GITHUB_TOKEN=ghp_your_token`
2. Get token from https://github.com/settings/tokens
3. Token needs `repo` scope

---

## Pro Tips

1. **Clear context regularly** - `/clear` after each feature keeps context under 8K tokens
2. **Use PROJECT.md** - Defines GOALS/SCOPE/CONSTRAINTS for alignment
3. **Start simple** - Try a small feature first to learn workflow
4. **Check alignment** - `/align-project` validates project structure
5. **Read docs** - See [plugins/autonomous-dev/README.md](plugins/autonomous-dev/README.md) for complete guide

---

## Configuration

### PROJECT.md (Strategic Direction)
Located: `.claude/PROJECT.md`

Defines:
- **GOALS**: What success looks like
- **SCOPE**: What's in/out of scope
- **CONSTRAINTS**: Technical limits
- **CURRENT SPRINT**: Active work

All agents validate against this before working!

### Environment Variables (Optional GitHub Integration)
Create `.env` file:
```bash
GITHUB_TOKEN=ghp_your_token_here
```

Enables:
- Sprint tracking via GitHub Milestones
- Auto-issue creation
- PR automation

---

## Next Steps

1. **Edit PROJECT.md** - Customize for your project
2. **Try /auto-implement** - Implement a small feature
3. **Check coverage** - Run `/test` to see current coverage
4. **Read full docs** - [plugins/autonomous-dev/README.md](plugins/autonomous-dev/README.md)

---

## Support

- **Issues**: [GitHub Issues](https://github.com/akaszubski/claude-code-bootstrap/issues)
- **Discussions**: [GitHub Discussions](https://github.com/akaszubski/claude-code-bootstrap/discussions)
- **Full Docs**: [plugins/autonomous-dev/README.md](plugins/autonomous-dev/README.md)
- **Troubleshooting**: [TROUBLESHOOTING.md](TROUBLESHOOTING.md)

---

## Summary

```bash
# Install
/plugin install autonomous-dev

# First feature
/auto-implement

# Quality check
/full-check

# Commit
/commit

# Clear context
/clear
```

**You're ready! Transform your development workflow in one command. 🚀**
