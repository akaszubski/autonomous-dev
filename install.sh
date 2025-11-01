#!/usr/bin/env bash
#
# Autonomous Dev Plugin - Bootstrap Installer
#
# Run this AFTER: /plugin install autonomous-dev
#
# Usage:
#   bash install.sh
#   OR
#   curl -sSL https://raw.githubusercontent.com/akaszubski/autonomous-dev/master/install.sh | bash
#

set -e  # Exit on error

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "🚀 Autonomous Dev Plugin - Bootstrap"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

# Detect plugin directory
PLUGIN_DIR="$HOME/.claude/plugins/marketplaces/autonomous-dev/plugins/autonomous-dev"

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

# Determine project directory
if [ -z "$CLAUDE_PROJECT_DIR" ]; then
    PROJECT_DIR="$(pwd)"
else
    PROJECT_DIR="$CLAUDE_PROJECT_DIR"
fi

CLAUDE_DIR="$PROJECT_DIR/.claude"

echo "📁 Project directory: $PROJECT_DIR"
echo "📁 Claude directory: $CLAUDE_DIR"
echo ""

# Create .claude directory structure
echo "📂 Creating directory structure..."
mkdir -p "$CLAUDE_DIR"/{commands,hooks,templates,agents,skills}

# Copy commands
echo "📋 Copying commands..."
if [ -d "$PLUGIN_DIR/commands" ]; then
    cp "$PLUGIN_DIR"/commands/*.md "$CLAUDE_DIR/commands/" 2>/dev/null || true
    CMD_COUNT=$(ls -1 "$CLAUDE_DIR/commands"/*.md 2>/dev/null | wc -l)
    echo "   ✅ Copied $CMD_COUNT command files"
else
    echo "   ⚠️  Commands directory not found in plugin"
fi

# Copy hooks
echo "🎣 Copying hooks..."
if [ -d "$PLUGIN_DIR/hooks" ]; then
    cp -r "$PLUGIN_DIR"/hooks/* "$CLAUDE_DIR/hooks/" 2>/dev/null || true
    HOOK_COUNT=$(find "$CLAUDE_DIR/hooks" -name "*.py" 2>/dev/null | wc -l)
    echo "   ✅ Copied $HOOK_COUNT hook files"
else
    echo "   ⚠️  Hooks directory not found in plugin"
fi

# Copy templates
echo "📄 Copying templates..."
if [ -d "$PLUGIN_DIR/templates" ]; then
    cp -r "$PLUGIN_DIR"/templates/* "$CLAUDE_DIR/templates/" 2>/dev/null || true
    TMPL_COUNT=$(find "$CLAUDE_DIR/templates" -type f 2>/dev/null | wc -l)
    echo "   ✅ Copied $TMPL_COUNT template files"
else
    echo "   ⚠️  Templates directory not found in plugin"
fi

# Optional: Copy agents and skills (if they want local copies)
echo ""
echo "📚 Copying agents and skills (optional)..."
if [ -d "$PLUGIN_DIR/agents" ]; then
    cp "$PLUGIN_DIR"/agents/*.md "$CLAUDE_DIR/agents/" 2>/dev/null || true
    AGENT_COUNT=$(ls -1 "$CLAUDE_DIR/agents"/*.md 2>/dev/null | wc -l)
    echo "   ✅ Copied $AGENT_COUNT agent files"
fi

if [ -d "$PLUGIN_DIR/skills" ]; then
    cp -r "$PLUGIN_DIR"/skills/* "$CLAUDE_DIR/skills/" 2>/dev/null || true
    SKILL_COUNT=$(find "$CLAUDE_DIR/skills" -type d -name "*.skill" 2>/dev/null | wc -l)
    echo "   ✅ Copied $SKILL_COUNT skill directories"
fi

# Create marker file
echo "autonomous-dev-plugin" > "$CLAUDE_DIR/.autonomous-dev-bootstrapped"

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "✅ Bootstrap Complete!"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "📋 What was installed:"
echo "   • Commands: .claude/commands/"
echo "   • Hooks: .claude/hooks/"
echo "   • Templates: .claude/templates/"
echo "   • Agents: .claude/agents/"
echo "   • Skills: .claude/skills/"
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
echo "   Or re-run this script:"
echo "   bash <(curl -sSL https://raw.githubusercontent.com/akaszubski/autonomous-dev/master/install.sh)"
echo ""
echo "Happy coding! 🚀"
echo ""
