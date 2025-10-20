#!/bin/bash
# Refresh Claude Code settings from repo
# Run this after making changes to agents, commands, skills, or hooks

set -e

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PLUGIN_DIR="$REPO_ROOT/plugins/autonomous-dev"
CLAUDE_DIR="$REPO_ROOT/.claude"

echo "🔄 Refreshing Claude Code settings..."
echo ""

# 1. Sync agents
echo "📋 Copying agents..."
cp -r "$PLUGIN_DIR/agents/"* "$CLAUDE_DIR/agents/"

# 2. Sync commands
echo "⚡ Copying commands..."
cp -r "$PLUGIN_DIR/commands/"* "$CLAUDE_DIR/commands/"

# 3. Sync skills
echo "🎓 Copying skills..."
cp -r "$PLUGIN_DIR/skills/"* "$CLAUDE_DIR/skills/"

# 4. Sync hooks
echo "🪝 Copying hooks..."
cp -r "$PLUGIN_DIR/hooks/"* "$CLAUDE_DIR/hooks/"

# 5. Verify symlink for plugin installation
echo "🔗 Verifying plugin symlink..."
if [ -L "$HOME/.claude/plugins/autonomous-dev" ]; then
    echo "   ✅ Plugin symlink exists"
else
    echo "   ⚠️  Plugin symlink missing - creating..."
    mkdir -p "$HOME/.claude/plugins"
    ln -s "$PLUGIN_DIR" "$HOME/.claude/plugins/autonomous-dev"
    echo "   ✅ Created symlink"
fi

echo ""
echo "✅ Refresh complete!"
echo ""
echo "Updated:"
echo "  - Agents: $(ls -1 $CLAUDE_DIR/agents/*.md | wc -l | xargs) files"
echo "  - Commands: $(ls -1 $CLAUDE_DIR/commands/*.md | wc -l | xargs) files"
echo "  - Skills: $(ls -1 $CLAUDE_DIR/skills/*/SKILL.md 2>/dev/null | wc -l | xargs) files"
echo "  - Hooks: $(ls -1 $CLAUDE_DIR/hooks/*.py 2>/dev/null | wc -l | xargs) files"
echo ""
echo "💡 Changes active immediately - no restart needed"
