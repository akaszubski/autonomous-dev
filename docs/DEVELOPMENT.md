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
