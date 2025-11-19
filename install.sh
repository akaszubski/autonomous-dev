#!/usr/bin/env bash
#
# Autonomous Dev Plugin - Bootstrap Installer
#
# Run this AFTER: /plugin install autonomous-dev
#
# Usage:
#   bash install.sh [PLUGIN_DIR] [PROJECT_DIR]
#   OR
#   curl -sSL https://raw.githubusercontent.com/akaszubski/autonomous-dev/master/install.sh | bash
#

set -e  # Exit on error

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "🚀 Autonomous Dev Plugin - Bootstrap"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

# Detect plugin directory (from args or default)
if [ -n "$1" ]; then
    PLUGIN_DIR="$1"
elif [ -n "$PLUGIN_DIR" ]; then
    # Use environment variable if set
    :
else
    PLUGIN_DIR="$HOME/.claude/plugins/marketplaces/autonomous-dev/plugins/autonomous-dev"
fi

if [ ! -d "$PLUGIN_DIR" ]; then
    echo "❌ Plugin not found at: $PLUGIN_DIR"
    echo ""
    echo "Please install the plugin first:"
    echo "  /plugin marketplace add akaszubski/autonomous-dev"
    echo "  /plugin install autonomous-dev"
    echo ""
    echo "Then restart Claude Code (Cmd+Q) and run this script again."
    exit 1
fi

echo "✅ Found plugin at: $PLUGIN_DIR"
echo ""

# Determine project directory (from args, env, or cwd)
if [ -n "$2" ]; then
    PROJECT_DIR="$2"
elif [ -n "$PROJECT_DIR" ]; then
    # Use environment variable if set
    :
elif [ -n "$CLAUDE_PROJECT_DIR" ]; then
    PROJECT_DIR="$CLAUDE_PROJECT_DIR"
else
    PROJECT_DIR="$(pwd)"
fi

echo "📁 Project directory: $PROJECT_DIR"
echo ""

# Use Python orchestrator for installation
# Note: Cannot use 'python3 -m plugins.autonomous_dev' because directory has hyphen
# Add plugin directory to PYTHONPATH for imports to work
export PYTHONPATH="$PLUGIN_DIR:${PYTHONPATH:-}"

python3 "$PLUGIN_DIR/lib/install_orchestrator.py" \
    --plugin-dir "$PLUGIN_DIR" \
    --project-dir "$PROJECT_DIR" \
    --fresh-install \
    --show-progress

echo ""
echo "🔄 Next Steps:"
echo ""
echo "1. Restart Claude Code:"
echo "   • Press Cmd+Q (Mac) or Ctrl+Q (Windows/Linux)"
echo "   • Wait for it to close completely"
echo "   • Reopen Claude Code"
echo ""
echo "2. Run setup wizard:"
echo "   /setup"
echo ""
echo "3. Verify installation:"
echo "   /health-check"
echo ""
echo "💡 To update plugin files later:"
echo "   /update-plugin"
echo ""
echo "Happy coding! 🚀"
echo ""
