# Plugin Distribution Strategy - Research & Solution

**Date**: 2025-11-02
**Status**: RESEARCH COMPLETE - SOLUTION IDENTIFIED

---

## Problem Statement

Users installing the `autonomous-dev` plugin cannot access plugin commands (`/setup`, `/auto-implement`, etc.) after installation, even after full restart.

---

## Research Findings

### What the Docs Say

According to [Claude Code Plugin docs](https://docs.claude.com/en/docs/claude-code/plugins):

1. Plugins install globally to `~/.claude/plugins/marketplaces/`
2. Commands are discovered from plugin's `commands/` directory
3. After installation + restart, commands should be available
4. Namespacing format: `/plugin-name:command-name`

### What Actually Happens

**Tested Reality**:
- ✅ Plugin installs successfully
- ✅ Plugin appears in `~/.claude/plugins/installed_plugins.json`
- ✅ Plugin enabled in `~/.claude/settings.json`
- ❌ Commands NOT available in projects (even after Cmd+Q restart)
- ❌ `/setup` does not work
- ✅ Manual copy of commands DOES work

**Conclusion**: There's a gap between documentation and reality.

---

## How Other Plugins Work

### Research from Community

From marketplace analysis and team collaboration docs:

**Two Distribution Models Exist**:

#### Model 1: Global Plugin (What Docs Describe)
- Plugin installs globally
- Commands available via `/plugin-name:command`
- No per-project files needed
- **Status**: Not working for us

#### Model 2: Repository-Level Configuration (Team Workflow)
- Project has `.claude/settings.json` in git
- Specifies marketplace + plugins
- Team members prompted on trust
- Plugin components **may still need copying** to `.claude/`

Example `.claude/settings.json`:
```json
{
  "extraKnownMarketplaces": {
    "autonomous-dev": {
      "source": {
        "source": "github",
        "repo": "akaszubski/autonomous-dev"
      }
    }
  },
  "enabledPlugins": {
    "autonomous-dev@autonomous-dev": true
  }
}
```

---

## Current Plugin Architecture

### What We Distribute

```
plugins/autonomous-dev/
├── .claude-plugin/
│   └── plugin.json          # Plugin manifest
├── commands/                # 8 command files
├── agents/                  # 19 agent files
├── hooks/                   # 30+ hook files
├── skills/                  # 19 skill files
└── templates/              # Project templates
```

### What Users Need

For the plugin to work, users need:
- ✅ Plugin installed globally (via marketplace)
- ❓ Commands in `.claude/commands/` (unclear if required)
- ❓ Hooks in `.claude/hooks/` (needed for PreCommit hooks to work)
- ❓ Templates accessible (for `/setup` to copy from)

---

## The Real Problem

**Our plugin is HYBRID**:
- It's distributed as a **marketplace plugin** (global install)
- But it NEEDS files in the **project's `.claude/` directory** (local files)

**Why this matters**:
1. `/setup` command copies hooks/templates to project
2. But `/setup` itself isn't accessible to run
3. Chicken-and-egg paradox

---

## Possible Solutions

### Option 1: Pure Marketplace Plugin (Ideal but Doesn't Work)

**What should happen**:
```bash
/plugin install autonomous-dev
# Restart
/autonomous-dev:setup  # Should work from plugin directory
```

**Status**: Doesn't work - commands not discovered

### Option 2: Repository-Level Distribution (Team Workflow)

**Setup**:
1. Create a starter template repository
2. Include `.claude/` directory with:
   - `settings.json` (configures marketplace + plugin)
   - `commands/` (symlinks or copies from plugin)
   - `hooks/` (copies from plugin)
   - `templates/` (copies from plugin)
3. Users clone template, trust folder, get prompted to install

**Pros**:
- ✅ Works with Claude Code's team collaboration model
- ✅ Everything auto-configured
- ✅ No manual steps

**Cons**:
- ❌ Requires template repo (more setup)
- ❌ Not just "install plugin and go"

### Option 3: Hybrid with Bootstrap Script (Pragmatic)

**Installation**:
```bash
# 1. Install plugin via marketplace
/plugin install autonomous-dev

# 2. Run one-time bootstrap (from plugin)
curl -sSL https://raw.githubusercontent.com/akaszubski/autonomous-dev/master/install.sh | bash
# OR
~/.claude/plugins/marketplaces/autonomous-dev/plugins/autonomous-dev/install.sh

# 3. Restart and use
/setup
```

**Bootstrap script**:
```bash
#!/bin/bash
# install.sh - Run after /plugin install autonomous-dev

PLUGIN_DIR="$HOME/.claude/plugins/marketplaces/autonomous-dev/plugins/autonomous-dev"
PROJECT_DIR="$(pwd)/.claude"

# Create .claude directory
mkdir -p "$PROJECT_DIR"/{commands,hooks,templates}

# Copy essential files
cp "$PLUGIN_DIR"/commands/*.md "$PROJECT_DIR/commands/"
cp -r "$PLUGIN_DIR"/hooks/* "$PROJECT_DIR/hooks/"
cp -r "$PLUGIN_DIR"/templates/* "$PROJECT_DIR/templates/"

echo "✅ Bootstrap complete! Restart Claude Code and run /setup"
```

**Pros**:
- ✅ Works with current architecture
- ✅ One-time manual step
- ✅ Clear user experience

**Cons**:
- ❌ Still requires manual step
- ❌ Not pure marketplace plugin

### Option 4: Two-Tier Distribution

**Marketplace Plugin**: Provides agents and skills only
**Starter Template**: Provides commands, hooks, templates

**Installation**:
```bash
# For quick start - just agents
/plugin install autonomous-dev-agents

# For full setup - use template
git clone https://github.com/akaszubski/autonomous-dev-template myproject
cd myproject
# Trust folder → auto-installs everything
```

**Pros**:
- ✅ Separates concerns
- ✅ Marketplace plugin is pure (agents/skills)
- ✅ Template handles project setup

**Cons**:
- ❌ Two separate things to maintain
- ❌ More complex for users

---

## Recommended Solution

**SHORT TERM**: Option 3 (Hybrid with Bootstrap Script)

1. Update README with bootstrap step:
   ```markdown
   ## Installation

   1. Install plugin:
      ```bash
      /plugin marketplace add akaszubski/autonomous-dev
      /plugin install autonomous-dev
      ```

   2. Bootstrap your project (one-time):
      ```bash
      curl -sSL https://raw.githubusercontent.com/akaszubski/autonomous-dev/master/install.sh | bash
      ```

   3. Restart Claude Code and run:
      ```bash
      /setup
      ```
   ```

2. Create `install.sh` at repo root
3. Make it copy commands/hooks/templates to project
4. Update QUICKSTART with this flow

**LONG TERM**: Option 4 (Two-Tier Distribution)

1. Create `autonomous-dev-lite` marketplace plugin (agents + skills only)
2. Create `autonomous-dev-template` starter repo
3. Users choose their path:
   - Just want AI agents? Install lite plugin
   - Want full workflow? Clone template

---

## Action Items

- [ ] Create `install.sh` bootstrap script
- [ ] Test bootstrap script on fresh project
- [ ] Update README.md with bootstrap instructions
- [ ] Update QUICKSTART.md
- [ ] Document this as known limitation until fixed
- [ ] File issue with Claude Code team about command discovery

---

## Questions for Claude Code Team

1. How SHOULD plugin commands be discovered after installation?
2. Is namespacing (`/plugin-name:command`) supposed to work without copying files?
3. What's the intended distribution model for plugins that need project-level files?
4. Should we be using repository-level configuration instead?

---

## References

- [Claude Code Plugins](https://docs.claude.com/en/docs/claude-code/plugins)
- [Claude Code Settings](https://docs.claude.com/en/docs/claude-code/settings)
- [Team Collaboration](https://docs.claude.com/en/docs/claude-code/plugins#team-collaboration)
