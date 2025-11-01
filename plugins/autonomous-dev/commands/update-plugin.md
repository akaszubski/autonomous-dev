---
description: Update plugin files from installed marketplace version to latest
---

# Update Plugin Files

Updates your project's `.claude/` files from the installed marketplace plugin to get latest commands, hooks, and templates.

## Usage

```bash
/update-plugin
```

## What This Does

This command re-copies files from the globally installed plugin to your project:

1. **Backs up** your current `.claude/` directory (to `.claude.backup.TIMESTAMP/`)
2. **Updates** all plugin files:
   - Commands → `.claude/commands/`
   - Hooks → `.claude/hooks/`
   - Templates → `.claude/templates/`
   - Agents → `.claude/agents/`
   - Skills → `.claude/skills/`
3. **Preserves** your custom commands and configurations
4. **Reports** what was updated

## When to Use This

Run `/update-plugin` when:
- You've updated the plugin: `/plugin update autonomous-dev`
- New features were released and you want the latest
- Bug fixes in hooks or commands
- You want to restore default files

## Safety

Your existing files are backed up before updating. If something goes wrong:

```bash
# Restore from backup
rm -rf .claude
mv .claude.backup.TIMESTAMP .claude
```

## Implementation

```bash
#!/usr/bin/env bash

set -e

# Find plugin directory
PLUGIN_DIR="$HOME/.claude/plugins/marketplaces/autonomous-dev/plugins/autonomous-dev"

if [ ! -d "$PLUGIN_DIR" ]; then
    echo "❌ Plugin not found. Please install first:"
    echo "   /plugin marketplace add akaszubski/autonomous-dev"
    echo "   /plugin install autonomous-dev"
    exit 1
fi

# Project directory
PROJECT_DIR="${CLAUDE_PROJECT_DIR:-$(pwd)}"
CLAUDE_DIR="$PROJECT_DIR/.claude"

if [ ! -d "$CLAUDE_DIR" ]; then
    echo "❌ No .claude directory found. Run bootstrap first:"
    echo "   bash <(curl -sSL https://raw.githubusercontent.com/akaszubski/autonomous-dev/main/install.sh)"
    exit 1
fi

# Backup current files
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
BACKUP_DIR="$PROJECT_DIR/.claude.backup.$TIMESTAMP"

echo "📦 Creating backup: .claude.backup.$TIMESTAMP"
cp -r "$CLAUDE_DIR" "$BACKUP_DIR"

# Update files
echo "🔄 Updating plugin files..."

# Update commands (preserve custom ones)
echo "  📋 Updating commands..."
cp "$PLUGIN_DIR"/commands/*.md "$CLAUDE_DIR/commands/" 2>/dev/null || true

# Update hooks
echo "  🎣 Updating hooks..."
cp -r "$PLUGIN_DIR"/hooks/* "$CLAUDE_DIR/hooks/" 2>/dev/null || true

# Update templates
echo "  📄 Updating templates..."
cp -r "$PLUGIN_DIR"/templates/* "$CLAUDE_DIR/templates/" 2>/dev/null || true

# Update agents
echo "  🤖 Updating agents..."
cp "$PLUGIN_DIR"/agents/*.md "$CLAUDE_DIR/agents/" 2>/dev/null || true

# Update skills
echo "  📚 Updating skills..."
cp -r "$PLUGIN_DIR"/skills/* "$CLAUDE_DIR/skills/" 2>/dev/null || true

echo ""
echo "✅ Plugin files updated successfully!"
echo ""
echo "📦 Backup saved to: .claude.backup.$TIMESTAMP"
echo ""
echo "🔄 Restart Claude Code to use updated files:"
echo "   Cmd+Q (Mac) or Ctrl+Q (Windows/Linux)"
echo ""
```

---

## Alternative: Check for Updates

To check if updates are available without installing:

```bash
# Check installed version
cat ~/.claude/plugins/installed_plugins.json | grep -A 3 "autonomous-dev"

# Check latest version
curl -s https://raw.githubusercontent.com/akaszubski/autonomous-dev/main/plugins/autonomous-dev/.claude-plugin/plugin.json | grep version
```

---

## Related Commands

- `/health-check` - Verify all commands are present
- `/setup` - Initial configuration wizard
- `/uninstall` - Remove plugin files
