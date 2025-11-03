#!/usr/bin/env bash
#
# Dogfooding Bootstrap - For Plugin Developers
#
# This script installs the plugin from YOUR LOCAL REPO (not GitHub)
# Use this to test changes BEFORE pushing to GitHub
#
# Usage:
#   cd /path/to/autonomous-dev
#   ./scripts/dogfood-bootstrap.sh
#

set -e

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "🔧 DOGFOODING MODE - Local Bootstrap"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "This installs from YOUR LOCAL REPO, not GitHub"
echo ""

# Get repo directory (where this script lives)
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"

echo "📁 Repo directory: $REPO_DIR"
echo ""

# Verify we're in the right place
if [ ! -f "$REPO_DIR/plugins/autonomous-dev/README.md" ]; then
    echo "❌ Error: Can't find plugins/autonomous-dev/ in repo"
    echo "   Make sure you're running this from the autonomous-dev repo root"
    exit 1
fi

PLUGIN_SOURCE="$REPO_DIR/plugins/autonomous-dev"
echo "✅ Found plugin source at: $PLUGIN_SOURCE"
echo ""

# Determine project directory (current directory by default)
PROJECT_DIR="$(pwd)"
CLAUDE_DIR="$PROJECT_DIR/.claude"

# If we're IN the repo, use the repo's .claude directory
if [ "$PROJECT_DIR" = "$REPO_DIR" ]; then
    echo "📍 Dogfooding in repo itself"
    CLAUDE_DIR="$REPO_DIR/.claude"
else
    echo "📍 Installing to project: $PROJECT_DIR"
fi

echo "📁 Claude directory: $CLAUDE_DIR"
echo ""

# Create .claude directory structure
echo "📂 Creating directory structure..."
mkdir -p "$CLAUDE_DIR"/{commands,hooks,templates}

# Copy commands
echo "📋 Copying commands from LOCAL repo..."
if [ -d "$PLUGIN_SOURCE/commands" ]; then
    # Clear existing commands first
    rm -f "$CLAUDE_DIR/commands"/*.md 2>/dev/null || true

    cp "$PLUGIN_SOURCE"/commands/*.md "$CLAUDE_DIR/commands/" 2>/dev/null || true
    CMD_COUNT=$(ls -1 "$CLAUDE_DIR/commands"/*.md 2>/dev/null | wc -l | tr -d ' ')
    echo "   ✅ Copied $CMD_COUNT command files"
else
    echo "   ❌ Commands directory not found"
    exit 1
fi

# Copy hooks
echo "🎣 Copying hooks from LOCAL repo..."
if [ -d "$PLUGIN_SOURCE/hooks" ]; then
    # Clear existing hooks first
    rm -rf "$CLAUDE_DIR/hooks"/* 2>/dev/null || true

    cp -r "$PLUGIN_SOURCE"/hooks/* "$CLAUDE_DIR/hooks/" 2>/dev/null || true
    HOOK_COUNT=$(find "$CLAUDE_DIR/hooks" -name "*.py" 2>/dev/null | wc -l | tr -d ' ')
    echo "   ✅ Copied $HOOK_COUNT hook files"
else
    echo "   ❌ Hooks directory not found"
    exit 1
fi

# Make hooks executable
echo "🔧 Making hooks executable..."
find "$CLAUDE_DIR/hooks" -name "*.py" -exec chmod +x {} \; 2>/dev/null || true

# Copy templates
echo "📄 Copying templates from LOCAL repo..."
if [ -d "$PLUGIN_SOURCE/templates" ]; then
    cp -r "$PLUGIN_SOURCE"/templates/* "$CLAUDE_DIR/templates/" 2>/dev/null || true
    TMPL_COUNT=$(find "$CLAUDE_DIR/templates" -type f 2>/dev/null | wc -l | tr -d ' ')
    echo "   ✅ Copied $TMPL_COUNT template files"
fi

# Create or update settings.local.json for dogfooding
echo ""
echo "⚙️  Configuring dogfooding settings..."

if [ ! -f "$CLAUDE_DIR/settings.local.json" ]; then
    echo "   📝 Creating new settings.local.json"
    cat > "$CLAUDE_DIR/settings.local.json" << 'EOF'
{
  "description": "Dogfooding Mode - Testing autonomous-dev from local repo",
  "hooks": {
    "UserPromptSubmit": [
      {
        "description": "Display dogfooding status",
        "hooks": [
          {
            "type": "command",
            "command": "echo '🔧 DOGFOODING MODE - Using local repo version'"
          }
        ]
      },
      {
        "description": "Auto-detect feature requests and trigger orchestrator",
        "hooks": [
          {
            "type": "command",
            "command": "python .claude/hooks/detect_feature_request.py"
          }
        ]
      }
    ],
    "PreCommit": [
      {
        "description": "Validation pipeline",
        "hooks": [
          {
            "type": "command",
            "command": "python .claude/hooks/validate_project_alignment.py || exit 1"
          },
          {
            "type": "command",
            "command": "python .claude/hooks/security_scan.py || exit 1"
          }
        ]
      }
    ],
    "SubagentStop": [
      {
        "description": "Log agent completion to session",
        "hooks": [
          {
            "type": "command",
            "command": "python scripts/session_tracker.py subagent 'Subagent completed task' 2>/dev/null || true"
          }
        ]
      }
    ]
  }
}
EOF
    echo "   ✅ Created settings.local.json with auto-orchestration enabled"
else
    echo "   ℹ️  settings.local.json already exists (not overwriting)"
    echo "   💡 Review it manually to enable auto-orchestration if needed"
fi

# Create marker file
echo "autonomous-dev-local" > "$CLAUDE_DIR/.autonomous-dev-dogfooding"

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "✅ Dogfooding bootstrap complete!"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "📍 Installed from: $PLUGIN_SOURCE"
echo "📍 Installed to: $CLAUDE_DIR"
echo ""
echo "🎯 Next steps:"
echo ""
echo "1. Restart Claude Code (Cmd+Q or Ctrl+Q)"
echo ""
echo "2. Test auto-orchestration by typing:"
echo '   "Add a simple hello function"'
echo ""
echo "3. View session logs:"
echo "   ./scripts/view-last-session.sh"
echo ""
echo "4. Make changes in plugins/autonomous-dev/"
echo "   Then run this script again to reload"
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
