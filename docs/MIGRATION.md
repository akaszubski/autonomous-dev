# Migration Guide

**Last Updated**: 2025-10-20

Adopting autonomous-dev plugin in existing projects.

---

## Prerequisites Check

Before migrating:
- [ ] Project uses Git
- [ ] Tests exist (pytest, jest, etc.)
- [ ] Python 3.11+ or Node.js 16+ installed
- [ ] Team ready to adopt new workflow

---

## Migration Steps

### Step 1: Install Plugin

```bash
cd your-existing-project
/plugin install autonomous-dev
```

### Step 2: Create PROJECT.md

```bash
# Create from template
cp .claude/templates/PROJECT.md .claude/PROJECT.md

# Customize for your project
vim .claude/PROJECT.md
```

Fill in:
- **GOALS**: Your project's objectives
- **SCOPE**: What's in/out
- **CONSTRAINTS**: Technical limits
- **CURRENT SPRINT**: Active work

### Step 3: Run Alignment Check

```bash
/align-project

# Or safe interactive mode:
/align-project-safe
```

Fixes:
- Missing tests
- Documentation gaps
- File organization
- Quality standards

### Step 4: Configure GitHub (Optional)

```bash
# Create .env
cp .env.example .env

# Add GitHub token
# See docs/GITHUB_AUTH_SETUP.md
```

### Step 5: Test Workflow

```bash
# Pick small feature
"Add a simple helper function with tests"

# Try autonomous implementation
/auto-implement

# Verify quality
/full-check

# Commit
/commit

# Clear context
/clear
```

---

## Common Migration Scenarios

### Python Project

```bash
# Install plugin
/plugin install autonomous-dev

# Run alignment
/align-project

# Start using
/auto-implement
```

### JavaScript/TypeScript Project

Same process, auto-detects language and uses appropriate tools (prettier, jest, etc.)

### Monorepo

Install at root, customize PROJECT.md for each sub-project.

### Legacy Project

1. Start with `/align-project --safe` (interactive)
2. Fix critical gaps first
3. Gradually adopt features
4. Team training on workflow

---

## Rollback

If needed:
```bash
/plugin uninstall autonomous-dev
rm -rf .claude/
git checkout .  # Restore original files
```

---

**For help**, see:
- Alignment Command: `/align-project --help`
- Troubleshooting: `docs/TROUBLESHOOTING.md`
- Team Onboarding: `docs/TEAM-ONBOARDING.md`
