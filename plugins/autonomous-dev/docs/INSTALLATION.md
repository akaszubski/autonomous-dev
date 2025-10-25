# Installation Guide - Tiered Approach

**Version**: 2.4.0-beta
**Last Updated**: 2025-10-26
**Issue**: #15 - Installation Complexity vs Simplicity Promise

---

## Choose Your Tier

Pick the installation tier that matches your workflow:

| Tier | Who It's For | Time | What You Get |
|------|-------------|------|--------------|
| **[Basic](#basic-tier)** | Solo developer, learning | 2 min | Slash commands only |
| **[Standard](#standard-tier)** | Solo with automation | 5 min | Commands + auto-format/test hooks |
| **[Team](#team-tier)** | Team collaboration | 10 min | Full integration + GitHub + PROJECT.md |

**Not sure?** Start with **Basic** → upgrade to Standard/Team later as needed.

---

## Basic Tier

**For**: Solo developers who want explicit control
**Time**: 2 minutes
**Philosophy**: You tell Claude what to do, when to do it

### Installation (3 Steps)

```bash
# 1. Add marketplace
/plugin marketplace add akaszubski/autonomous-dev

# 2. Install plugin
/plugin install autonomous-dev

# 3. Exit and restart Claude Code (REQUIRED!)
# Press Cmd+Q (Mac) or Ctrl+Q (Windows/Linux)
```

**Done!** All commands immediately work.

### What You Get

**8 Slash Commands**:
- `/test` - Run all tests
- `/align-project` - Check PROJECT.md alignment
- `/auto-implement` - Autonomous feature implementation
- `/setup` - Configuration wizard
- `/status` - Project status overview
- `/health-check` - Validate plugin components
- `/sync-dev` - Sync plugin changes (developers only)
- `/uninstall` - Remove plugin

**Usage Example**:
```bash
# Write some code
# ...

# When ready, run checks manually
/test
/format  # If you want formatting

# Commit when you're satisfied
git add .
git commit -m "Add feature"
```

### Upgrading from Basic

Want automation? → [Standard Tier](#standard-tier)
Want GitHub integration? → [Team Tier](#team-tier)

---

## Standard Tier

**For**: Solo developers who want automatic quality checks
**Time**: 5 minutes (Basic + 3 min setup)
**Philosophy**: Quality checks run automatically, you focus on coding

### Prerequisites

✅ Basic tier installed
✅ One of: Python project OR JavaScript/TypeScript project OR Go project

### Installation (2 Additional Steps)

```bash
# 1. Run setup wizard
/setup

# 2. Choose "Automatic Hooks" when prompted
#    This enables:
#    - Auto-format on save (black/prettier/gofmt)
#    - Auto-test before commit
#    - Security scan before commit
```

### What You Get (Basic +)

**Automatic Hooks**:
- **Auto-format**: Code formatted on every save
- **Auto-test**: Tests run before every commit
- **Security scan**: Secrets detection before commit
- **Coverage enforcement**: 80% minimum (configurable)

**Usage Example**:
```bash
# Write code
# → Auto-formatted on save automatically

# Try to commit
git commit -m "Add feature"
# → Tests run automatically
# → Security scan runs automatically
# → Only commits if all pass
```

### Configuration

**Enable hooks** (if you skipped /setup):
```bash
/setup
# Choose: "Automatic Hooks"
```

**Disable hooks temporarily**:
```bash
git commit --no-verify  # Skip hooks for this commit
```

**Disable hooks permanently**:
```bash
rm .claude/settings.local.json
# Restart Claude Code
```

### Upgrading from Standard

Want GitHub integration? → [Team Tier](#team-tier)

---

## Team Tier

**For**: Teams collaborating with GitHub
**Time**: 10 minutes (Standard + 5 min setup)
**Philosophy**: Fully automated workflow with sprint tracking

### Prerequisites

✅ Standard tier installed
✅ GitHub repository
✅ GitHub Personal Access Token (we'll help you create one)

### Installation (3 Additional Steps)

```bash
# 1. Create PROJECT.md (strategic direction)
/setup
# Choose: "Create PROJECT.md from template"
# Fill in: GOALS, SCOPE, CONSTRAINTS

# 2. Setup GitHub integration
/setup
# Choose: "GitHub Integration"
# Follow prompts to:
#  - Create GitHub Personal Access Token
#  - Add token to .env
#  - Create GitHub Milestone

# 3. Verify everything works
/align-project
/health-check
```

### What You Get (Standard +)

**PROJECT.md Governance**:
- All features validated against strategic goals
- `/auto-implement` checks alignment before starting
- `/status` tracks progress toward PROJECT.md goals
- **Zero scope creep** - Claude won't implement out-of-scope features

**GitHub Integration**:
- Sprint tracking via Milestones
- Automatic issue creation from test failures
- PR description generation
- Commit message generation following conventional commits

**Usage Example**:
```bash
# Define what you're building
vim PROJECT.md
# GOALS: Build REST API
# SCOPE: CRUD operations, pagination
# OUT OF SCOPE: Admin UI, real-time features

# Autonomous implementation
/auto-implement "add user authentication"
# → Validates against PROJECT.md goals
# → Researches existing patterns
# → Writes tests (TDD)
# → Implements code
# → Runs security scan
# → Updates documentation
# → Creates commit

# Track progress
/status
# Shows: 40% toward "Performance" goal
```

### PROJECT.md Template

Minimal example:
```markdown
# Project Context

## GOALS
1. Build a REST API for blog posts
2. 80%+ test coverage
3. < 100ms response time

## SCOPE

### In Scope
- CRUD operations
- Pagination
- Search

### Out of Scope
- Admin UI
- Real-time features
- GraphQL

## CONSTRAINTS
- Use Python 3.11+
- PostgreSQL only
- No external API dependencies
```

### GitHub Setup

**Create Personal Access Token**:
1. Go to: https://github.com/settings/tokens
2. Click: "Generate new token (classic)"
3. Select scopes: `repo`, `workflow`
4. Copy token

**Add to .env**:
```bash
echo "GITHUB_TOKEN=ghp_your_token_here" > .env
```

**Create Milestone**:
1. Go to: https://github.com/YOUR_USER/YOUR_REPO/milestones
2. Click: "New milestone"
3. Title: "Sprint 1" (or current sprint name)
4. Set due date
5. Create

---

## Tier Comparison Matrix

| Feature | Basic | Standard | Team |
|---------|-------|----------|------|
| **Slash Commands** | ✅ 8 commands | ✅ 8 commands | ✅ 8 commands |
| **Installation Time** | 2 min | 5 min | 10 min |
| **Auto-format on save** | ❌ Manual | ✅ Automatic | ✅ Automatic |
| **Auto-test before commit** | ❌ Manual | ✅ Automatic | ✅ Automatic |
| **Security scan** | ❌ Manual | ✅ Automatic | ✅ Automatic |
| **PROJECT.md governance** | ❌ Optional | ❌ Optional | ✅ Required |
| **GitHub integration** | ❌ No | ❌ No | ✅ Yes |
| **Sprint tracking** | ❌ No | ❌ No | ✅ Milestones |
| **Scope enforcement** | ❌ No | ❌ No | ✅ Yes |
| **Best for** | Learning | Solo dev | Teams |

---

## Troubleshooting by Tier

### Basic Tier Issues

**"Commands don't work after install"**:
- Did you restart Claude Code? (Required!)
- Press Cmd+Q (Mac) or Ctrl+Q (Windows/Linux)
- Verify: `/plugin list` shows autonomous-dev

**"Want automation but don't know where to start"**:
- Upgrade to [Standard Tier](#standard-tier)

### Standard Tier Issues

**"Hooks not running"**:
- Check: `.claude/settings.local.json` exists
- Check: Formatter installed (black/prettier/gofmt)
- See: [ERR-101] docs/ERROR_MESSAGES.md

**"Tests fail on commit"**:
- This is working as intended!
- Fix tests: `pytest -v`
- OR skip once: `git commit --no-verify`

**"Too much automation, want control back"**:
- Downgrade to [Basic Tier](#basic-tier)
- Remove: `.claude/settings.local.json`
- Restart Claude Code

### Team Tier Issues

**"PROJECT.md validation failing"**:
- Check: PROJECT.md has GOALS, SCOPE, CONSTRAINTS sections
- Validate: `/align-project`
- Template: `.claude/templates/PROJECT.md`

**"GitHub authentication failing"**:
- Check: `.env` file exists with GITHUB_TOKEN
- Check: Token has `repo` scope
- Test: `gh auth status`
- See: [ERR-103] docs/ERROR_MESSAGES.md

**"Claude won't implement my feature"**:
- Is it in PROJECT.md SCOPE?
- If yes: Update request to align with goals
- If no: Update PROJECT.md to include it

**"Too much governance, want freedom"**:
- Downgrade to [Standard Tier](#standard-tier)
- Use `/auto-implement` without PROJECT.md validation
- GitHub integration remains optional

---

## Migration Between Tiers

### Basic → Standard

```bash
/setup
# Choose: "Automatic Hooks"
# Restart Claude Code
```

### Standard → Team

```bash
# 1. Create PROJECT.md
/setup
# Choose: "Create PROJECT.md"

# 2. Setup GitHub
/setup
# Choose: "GitHub Integration"

# 3. Verify
/align-project
```

### Team → Standard (Downgrade)

```bash
# Keep hooks, remove PROJECT.md validation
mv PROJECT.md PROJECT.md.backup  # Optional: keep for reference
rm .env  # Remove GitHub token

# Features still work, just no validation
```

### Standard → Basic (Downgrade)

```bash
# Remove automation
rm .claude/settings.local.json

# Restart Claude Code
# Commands still work, no automatic hooks
```

---

## FAQ

### Which tier should I choose?

**Start Basic** if:
- You're new to the plugin
- You want to learn one command at a time
- You prefer explicit control

**Upgrade to Standard** if:
- You're comfortable with commands
- You want to focus on coding, not manual checks
- You trust automatic formatting/testing

**Upgrade to Team** if:
- You're working with a team
- You have clear project goals
- You want scope enforcement
- You use GitHub for collaboration

### Can I mix tiers?

Yes! You can:
- Use Basic commands with Standard hooks
- Use Standard automation without Team governance
- Enable/disable features individually

### What's the recommended path?

**Week 1**: Basic (learn commands)
**Week 2**: Standard (add automation)
**Week 3+**: Team (if collaborating)

### Is Basic missing features?

No! Basic tier has all 8 commands. You're only missing **automation** and **governance**, which you can add later.

---

## Summary

| Tier | Commands | Hooks | PROJECT.md | GitHub | Time |
|------|----------|-------|------------|--------|------|
| **Basic** | ✅ | ❌ | ❌ | ❌ | 2 min |
| **Standard** | ✅ | ✅ | ❌ | ❌ | 5 min |
| **Team** | ✅ | ✅ | ✅ | ✅ | 10 min |

**Start with Basic → Upgrade as needed**

---

**Related**:
- Issue #15: Installation Complexity vs Simplicity Promise
- docs/TROUBLESHOOTING.md: Detailed troubleshooting by tier
- docs/ERROR_MESSAGES.md: Error code reference
