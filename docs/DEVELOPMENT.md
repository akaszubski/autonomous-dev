# Development Guide

**Last Updated**: 2025-10-20

Simple guide for developing and updating the autonomous-dev plugin.

---

## For Plugin Users (Installing)

```bash
# Install
/plugin marketplace add akaszubski/autonomous-dev
/plugin install autonomous-dev

# Update to latest
/plugin uninstall autonomous-dev
/plugin install autonomous-dev
```

That's it. No scripts, no sync, no complexity.

---

## For Plugin Developers (You)

### Your Current Setup

You have a **symlink** from Claude to your repo:
```
~/.claude/plugins/autonomous-dev → ~/Documents/GitHub/autonomous-dev/plugins/autonomous-dev
```

This means:
- ✅ Edit files in repo → Changes active immediately in Claude
- ✅ No refresh scripts needed
- ✅ Test locally before pushing

### Development Workflow

```bash
# 1. Edit plugin files
vim plugins/autonomous-dev/commands/test.md

# 2. Test immediately (symlink makes it active)
/test

# 3. Commit and push when ready
git add plugins/autonomous-dev/commands/test.md
git commit -m "feat: improve test command"
git push

# 4. Users update with:
/plugin uninstall autonomous-dev
/plugin install autonomous-dev
```

### Repository Structure

```
autonomous-dev/
├── marketplace.json              # Tells Claude where to find plugins
├── plugins/
│   └── autonomous-dev/
│       ├── .claude-plugin/
│       │   └── plugin.json       # Plugin metadata
│       ├── agents/               # 8 specialized agents
│       ├── commands/             # 11 slash commands
│       ├── skills/               # 6 core skills
│       ├── hooks/                # 9 automation hooks
│       └── templates/            # PROJECT.md templates
└── docs/                         # Documentation
```

### File Location Guidelines (CRITICAL)

**This repository serves TWO audiences:**
1. **Contributors** (building the plugin) → ROOT level
2. **Users** (using the plugin) → PLUGIN level

#### The Golden Rule

Before creating or moving any file, ask these 3 questions:

1. **WHO** is this for?
   - Contributors/Developers → ROOT
   - End users → PLUGIN

2. **WHEN** do they need it?
   - While building the plugin → ROOT
   - While using the plugin → PLUGIN

3. **WHAT** is it?
   - Development tool/doc → ROOT
   - Plugin feature/doc → PLUGIN

#### ROOT Level (Development workspace - NOT distributed)

```
ROOT/
├── docs/                         DEV/CONTRIBUTOR DOCS
│   ├── CONTRIBUTING.md           How to contribute
│   ├── DEVELOPMENT.md            Development workflow (this file)
│   ├── CODE-REVIEW-WORKFLOW.md  Code review process
│   ├── IMPLEMENTATION-STATUS.md Build status
│   └── ... (dev docs only)
│
├── scripts/                      BUILD/DEV SCRIPTS
│   ├── validate_structure.py    Structure validation
│   ├── session_tracker.py       Dev session tracking
│   └── hooks/                   Git hook templates
│       └── pre-commit           Structure validation hook
│
├── tests/                        REPO TESTS
│   ├── unit/                    Test build scripts
│   └── integration/             Test repo functionality
│
└── Root files
    ├── README.md                About the repository
    ├── CONTRIBUTING.md          Contributor guide
    ├── CLAUDE.md                Instructions for Claude
    └── CHANGELOG.md             Version history
```

#### PLUGIN Level (Distribution package - what users get)

```
plugins/autonomous-dev/
├── docs/                         USER DOCS
│   ├── COMMANDS.md              Command reference
│   ├── QUICKSTART.md            Quick start guide
│   ├── TROUBLESHOOTING.md       User troubleshooting
│   ├── GITHUB_AUTH_SETUP.md     GitHub setup guide
│   └── ... (user docs only)
│
├── agents/                       AI AGENTS
│   ├── orchestrator.md          Master coordinator
│   ├── planner.md               Architecture planner
│   └── ...
│
├── commands/                     SLASH COMMANDS
│   ├── test.md                  /test command
│   ├── format.md                /format command
│   └── ...
│
├── skills/                       SKILLS
│   ├── python-standards/        Python best practices
│   ├── testing-guide/           Testing methodology
│   └── ...
│
├── hooks/                        AUTOMATION HOOKS
│   ├── auto_format.py           Auto-format on save
│   ├── auto_test.py             Auto-test on commit
│   └── ...
│
├── scripts/                      USER SCRIPTS
│   └── setup.py                 Setup wizard for users
│
├── templates/                    TEMPLATES
│   ├── PROJECT.md               PROJECT.md template
│   └── settings.local.json      Settings template
│
└── tests/                        PLUGIN TESTS
    ├── test_uat.py              User acceptance tests
    └── test_architecture.py    Architecture validation
```

#### Enforcement

**Automated validation** prevents misplaced files:

```bash
# Run validation manually
python scripts/validate_structure.py

# Install pre-commit hook (recommended)
ln -sf ../../scripts/hooks/pre-commit .git/hooks/pre-commit
```

**What validation checks:**
- User docs only in `plugins/autonomous-dev/docs/`
- Dev docs only in `docs/`
- No duplicate files between root and plugin
- Clean root directory (only essential .md files)

**See also:**
- [CONTRIBUTING.md](../CONTRIBUTING.md) - Complete file location guidelines
- [.claude/PROJECT.md](../.claude/PROJECT.md) - Repository structure constraints

### Publishing Updates

```bash
# 1. Make changes locally, test with symlink
vim plugins/autonomous-dev/agents/planner.md
/auto-implement "test feature"  # Test it works

# 2. Update version in plugin.json
vim plugins/autonomous-dev/.claude-plugin/plugin.json
# Change version: "2.0.0" → "2.1.0"

# 3. Update marketplace.json
vim marketplace.json
# Change version: "2.0.0" → "2.1.0"

# 4. Update CHANGELOG.md
vim CHANGELOG.md
# Add release notes

# 5. Commit and push
git add .
git commit -m "release: v2.1.0 - improve planner agent"
git push

# 6. Tag release
git tag v2.1.0
git push --tags

# 7. Users get update with:
/plugin uninstall autonomous-dev
/plugin install autonomous-dev
```

---

## Testing Locally

Since you have the symlink, you can test immediately:

```bash
# Edit
vim plugins/autonomous-dev/commands/align-project.md

# Test (no reload needed!)
/align-project --help

# If it works, commit
git add plugins/autonomous-dev/commands/align-project.md
git commit -m "docs: update align-project help"
```

---

## Troubleshooting

### Changes not appearing in Claude?

Check if symlink exists:
```bash
ls -la ~/.claude/plugins/autonomous-dev
# Should show: ... -> /Users/.../autonomous-dev/plugins/autonomous-dev
```

If not a symlink, recreate it:
```bash
rm -rf ~/.claude/plugins/autonomous-dev
ln -s ~/Documents/GitHub/autonomous-dev/plugins/autonomous-dev \
      ~/.claude/plugins/autonomous-dev
```

### Want to test as a real user?

Remove symlink and install from marketplace:
```bash
# Remove symlink
rm ~/.claude/plugins/autonomous-dev

# Install as user would
/plugin marketplace add akaszubski/autonomous-dev
/plugin install autonomous-dev

# Test
/align-project

# Restore symlink for development
rm -rf ~/.claude/plugins/autonomous-dev
ln -s ~/Documents/GitHub/autonomous-dev/plugins/autonomous-dev \
      ~/.claude/plugins/autonomous-dev
```

---

## Summary

**Simple workflow**:
1. Edit files in repo (symlink makes them active immediately)
2. Test in Claude (no restart needed)
3. Commit and push to GitHub
4. Users update with uninstall/install

**No scripts. No sync. No complexity.**

---

**Related**:
- [CONTRIBUTING.md](CONTRIBUTING.md) - Contribution guidelines
- [CUSTOMIZATION.md](CUSTOMIZATION.md) - Customize agents/commands
- [README.md](../README.md) - Plugin overview
