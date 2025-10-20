#!/bin/bash
# Sync Plugin - Ensures .claude/ and plugins/autonomous-dev/ stay in sync
# Usage: ./scripts/sync-plugin.sh

set -e

echo "🔄 Syncing Plugin Files..."
echo ""

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Sync commands (bidirectional check)
echo "📁 Syncing commands..."
rsync -av --checksum .claude/commands/ plugins/autonomous-dev/commands/
echo -e "${GREEN}✅ Commands synced${NC}"
echo ""

# Verify sync
CLAUDE_COUNT=$(ls -1 .claude/commands/*.md 2>/dev/null | wc -l)
PLUGIN_COUNT=$(ls -1 plugins/autonomous-dev/commands/*.md 2>/dev/null | wc -l)

echo "📊 Command count:"
echo "   .claude/commands/: $CLAUDE_COUNT"
echo "   plugins/autonomous-dev/commands/: $PLUGIN_COUNT"

if [ "$CLAUDE_COUNT" -eq "$PLUGIN_COUNT" ]; then
    echo -e "${GREEN}✅ Counts match!${NC}"
else
    echo -e "${YELLOW}⚠️  Counts don't match - please review${NC}"
fi
echo ""

# Check for uncommitted changes
echo "📝 Git status:"
if git diff --quiet .claude/ plugins/autonomous-dev/; then
    echo -e "${GREEN}✅ No uncommitted changes${NC}"
else
    echo -e "${YELLOW}⚠️  You have uncommitted changes:${NC}"
    git status --short .claude/ plugins/autonomous-dev/ | head -10
    echo ""
    echo "Run: git add . && git commit -m 'your message'"
fi
echo ""

echo "✨ Sync complete!"
echo ""
echo "Next steps:"
echo "1. Review changes: git status"
echo "2. Commit: git add . && git commit -m 'your message'"
echo "3. Push: git push"
echo "4. Test: /plugin uninstall autonomous-dev && /plugin install autonomous-dev"
