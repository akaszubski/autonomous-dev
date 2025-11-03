#!/usr/bin/env bash
#
# Quick Resync for Dogfooding
#
# Use this when you've changed files in plugins/autonomous-dev/
# and need to reload them into your .claude/ directory
#
# Usage:
#   ./scripts/resync-dogfood.sh
#

set -e

echo "🔄 Resyncing plugin files to .claude/..."
echo ""

# Get repo directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
PLUGIN_SOURCE="$REPO_DIR/plugins/autonomous-dev"
CLAUDE_DIR="$REPO_DIR/.claude"

# Verify we're in the right place
if [ ! -d "$PLUGIN_SOURCE" ]; then
    echo "❌ Error: Can't find plugins/autonomous-dev/"
    exit 1
fi

echo "📁 Source: $PLUGIN_SOURCE"
echo "📁 Target: $CLAUDE_DIR"
echo ""

# Resync commands
echo "📋 Resyncing commands..."
rm -f "$CLAUDE_DIR/commands"/*.md 2>/dev/null || true
cp "$PLUGIN_SOURCE"/commands/*.md "$CLAUDE_DIR/commands/" 2>/dev/null || true
CMD_COUNT=$(ls -1 "$CLAUDE_DIR/commands"/*.md 2>/dev/null | wc -l | tr -d ' ')
echo "   ✅ $CMD_COUNT commands"

# Resync hooks
echo "🎣 Resyncing hooks..."
rm -rf "$CLAUDE_DIR/hooks"/* 2>/dev/null || true
cp -r "$PLUGIN_SOURCE"/hooks/* "$CLAUDE_DIR/hooks/" 2>/dev/null || true
chmod +x "$CLAUDE_DIR/hooks"/*.py 2>/dev/null || true
HOOK_COUNT=$(find "$CLAUDE_DIR/hooks" -name "*.py" 2>/dev/null | wc -l | tr -d ' ')
echo "   ✅ $HOOK_COUNT hooks"

# Resync templates (if changed)
echo "📄 Resyncing templates..."
rm -rf "$CLAUDE_DIR/templates"/* 2>/dev/null || true
cp -r "$PLUGIN_SOURCE"/templates/* "$CLAUDE_DIR/templates/" 2>/dev/null || true
TMPL_COUNT=$(find "$CLAUDE_DIR/templates" -type f 2>/dev/null | wc -l | tr -d ' ')
echo "   ✅ $TMPL_COUNT templates"

echo ""
echo "✅ Resync complete!"
echo ""
echo "💡 Changes applied:"
echo "   - Commands updated in .claude/commands/"
echo "   - Hooks updated in .claude/hooks/"
echo "   - Templates updated in .claude/templates/"
echo ""
echo "⚠️  Note: Agents are loaded from ~/.claude/plugins/marketplaces/"
echo "   To test agent changes, you need to push to GitHub and reinstall"
echo ""
echo "🔄 To reload in Claude Code:"
echo "   1. No restart needed for hooks/commands (live reload)"
echo "   2. For settings changes: restart Claude Code"
echo ""
