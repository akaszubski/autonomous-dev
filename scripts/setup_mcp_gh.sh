#!/bin/bash
# Setup MCP with gh command enabled for Claude Desktop

set -e

echo "🔧 Setting up MCP with gh command for Claude Desktop"
echo ""

# Paths
MCP_CONFIG="$HOME/Library/Application Support/Claude/claude_desktop_config.json"
GITHUB_TOKEN_FILE=".env"

# Check if gh is installed
if ! command -v gh &> /dev/null; then
    echo "⚠️  GitHub CLI (gh) not found"
    echo ""
    echo "Install with:"
    echo "  brew install gh"
    echo ""
    exit 1
fi

echo "✅ GitHub CLI (gh) is installed"

# Check if already authenticated
if ! gh auth status &> /dev/null; then
    echo "⚠️  GitHub CLI not authenticated"
    echo ""
    echo "Authenticate with:"
    echo "  gh auth login"
    echo ""
    exit 1
fi

echo "✅ GitHub CLI is authenticated"

# Get GitHub token
GITHUB_TOKEN=$(grep "^GITHUB_TOKEN=" "$GITHUB_TOKEN_FILE" 2>/dev/null | cut -d'=' -f2)

if [ -z "$GITHUB_TOKEN" ] || [ "$GITHUB_TOKEN" = "ghp_your-token-here" ]; then
    echo "⚠️  No valid GITHUB_TOKEN found in .env"
    echo ""
    echo "Get a token at: https://github.com/settings/tokens"
    echo "Required scopes: repo, workflow, write:discussion"
    echo ""
    echo "Then add to .env:"
    echo "  GITHUB_TOKEN=ghp_your_token_here"
    echo ""
    exit 1
fi

echo "✅ GitHub token found in .env"

# Check if config already exists
if [ -f "$MCP_CONFIG" ]; then
    echo ""
    echo "⚠️  MCP config already exists at:"
    echo "  $MCP_CONFIG"
    echo ""
    echo "Backup will be created before modifying"

    # Create backup
    cp "$MCP_CONFIG" "$MCP_CONFIG.backup.$(date +%Y%m%d-%H%M%S)"
    echo "✅ Backup created"
fi

# Create MCP config directory if needed
mkdir -p "$(dirname "$MCP_CONFIG")"

# Create or update MCP config
cat > "$MCP_CONFIG" << EOF
{
  "mcpServers": {
    "shell": {
      "command": "npx",
      "args": [
        "-y",
        "@modelcontextprotocol/server-shell"
      ],
      "env": {
        "ALLOWED_COMMANDS": "ls,cat,grep,find,git,gh,pytest,black,isort,python3,npm,node"
      }
    },
    "github": {
      "command": "npx",
      "args": [
        "-y",
        "@modelcontextprotocol/server-github"
      ],
      "env": {
        "GITHUB_PERSONAL_ACCESS_TOKEN": "$GITHUB_TOKEN"
      }
    }
  }
}
EOF

echo "✅ MCP config created/updated"
echo ""
echo "Configuration includes:"
echo "  • Shell server with gh command enabled"
echo "  • GitHub MCP server with your token"
echo ""
echo "Allowed shell commands:"
echo "  ls, cat, grep, find, git, gh, pytest, black, isort, python3, npm, node"
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "⚠️  IMPORTANT: Restart Claude Desktop for changes to take effect"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "To restart:"
echo "  1. Quit Claude Desktop (Cmd+Q)"
echo "  2. Reopen Claude Desktop"
echo ""
echo "To test:"
echo "  Ask Claude: 'Run: gh --version'"
echo ""
echo "✅ Setup complete!"
