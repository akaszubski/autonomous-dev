#!/bin/bash
# Sync plugin from source (plugins/autonomous-dev/) to local installation (.claude/)
# Use this during development to test changes immediately

set -e  # Exit on error

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
REPO_ROOT="$(dirname "$SCRIPT_DIR")"
PLUGIN_SOURCE="$REPO_ROOT/plugins/autonomous-dev"
PLUGIN_INSTALL="$REPO_ROOT/.claude"

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}Plugin Sync: Source → Local Install${NC}"
echo -e "${BLUE}========================================${NC}"
echo ""

# Check if source exists
if [ ! -d "$PLUGIN_SOURCE" ]; then
    echo -e "${YELLOW}❌ Plugin source not found: $PLUGIN_SOURCE${NC}"
    exit 1
fi

echo -e "${GREEN}📦 Source:${NC} $PLUGIN_SOURCE"
echo -e "${GREEN}📂 Target:${NC} $PLUGIN_INSTALL"
echo ""

# Sync agents
echo -e "${BLUE}Syncing agents...${NC}"
rm -rf "$PLUGIN_INSTALL/agents"
mkdir -p "$PLUGIN_INSTALL/agents"
cp -r "$PLUGIN_SOURCE/agents/"* "$PLUGIN_INSTALL/agents/"
AGENT_COUNT=$(ls "$PLUGIN_INSTALL/agents" | wc -l | xargs)
echo -e "${GREEN}✓${NC} Agents synced ($AGENT_COUNT files)"

# Sync skills
echo -e "${BLUE}Syncing skills...${NC}"
rm -rf "$PLUGIN_INSTALL/skills"
mkdir -p "$PLUGIN_INSTALL/skills"
cp -r "$PLUGIN_SOURCE/skills/"* "$PLUGIN_INSTALL/skills/"
SKILL_COUNT=$(ls "$PLUGIN_INSTALL/skills" | wc -l | xargs)
echo -e "${GREEN}✓${NC} Skills synced ($SKILL_COUNT directories)"

# Sync commands
echo -e "${BLUE}Syncing commands...${NC}"
rm -rf "$PLUGIN_INSTALL/commands"
mkdir -p "$PLUGIN_INSTALL/commands"
cp -r "$PLUGIN_SOURCE/commands/"* "$PLUGIN_INSTALL/commands/"
COMMAND_COUNT=$(ls "$PLUGIN_INSTALL/commands" | wc -l | xargs)
echo -e "${GREEN}✓${NC} Commands synced ($COMMAND_COUNT files)"

# Sync templates
echo -e "${BLUE}Syncing templates...${NC}"
rm -rf "$PLUGIN_INSTALL/templates"
mkdir -p "$PLUGIN_INSTALL/templates"
cp -r "$PLUGIN_SOURCE/templates/"* "$PLUGIN_INSTALL/templates/"
TEMPLATE_COUNT=$(ls "$PLUGIN_INSTALL/templates" | wc -l | xargs)
echo -e "${GREEN}✓${NC} Templates synced ($TEMPLATE_COUNT files)"

# Sync commands to global location (slash commands)
echo -e "${BLUE}Syncing commands to global ~/.claude/commands/ ...${NC}"
GLOBAL_COMMANDS="$HOME/.claude/commands"

if [ -d "$GLOBAL_COMMANDS" ]; then
    cp "$PLUGIN_SOURCE/commands/"* "$GLOBAL_COMMANDS/" 2>/dev/null && \
    echo -e "${GREEN}✓${NC} Commands synced to global location (slash commands available)" || \
    echo -e "${YELLOW}⚠${NC}  Could not sync to global commands (run manually: cp .claude/commands/* ~/.claude/commands/)"
else
    echo -e "${YELLOW}⚠${NC}  ~/.claude/commands/ not found (slash commands won't be available)"
    echo -e "   ${YELLOW}Run manually:${NC} mkdir -p ~/.claude/commands && cp .claude/commands/* ~/.claude/commands/"
fi

# Note about PROJECT.md and settings
echo ""
echo -e "${YELLOW}ℹ️  Note:${NC} PROJECT.md and settings.local.json NOT synced (local customizations preserved)"

echo ""
echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}✅ Plugin Synced Successfully${NC}"
echo -e "${GREEN}========================================${NC}"
echo ""
echo -e "${BLUE}Summary:${NC}"
echo "  - Agents: $AGENT_COUNT"
echo "  - Skills: $SKILL_COUNT"
echo "  - Commands: $COMMAND_COUNT"
echo "  - Templates: $TEMPLATE_COUNT"
echo ""
echo -e "${YELLOW}Next Steps:${NC}"
echo "  1. Test your changes in Claude Code"
echo "  2. When satisfied, commit source changes:"
echo "     git add plugins/autonomous-dev/"
echo "     git commit -m \"feat: your change\""
echo "     git push origin master"
echo "  3. Users will get updates via /plugin update autonomous-dev"
echo ""
