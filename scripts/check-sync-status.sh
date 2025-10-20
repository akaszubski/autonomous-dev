#!/bin/bash
# Check if local and plugin are in sync

echo "🔍 Checking sync status..."
echo ""

# Count files
PLUGIN_AGENTS=$(ls -1 plugins/autonomous-dev/agents/*.md 2>/dev/null | wc -l | tr -d ' ')
LOCAL_AGENTS=$(ls -1 .claude/agents/*.md 2>/dev/null | wc -l | tr -d ' ')

PLUGIN_COMMANDS=$(ls -1 plugins/autonomous-dev/commands/*.md 2>/dev/null | wc -l | tr -d ' ')
LOCAL_COMMANDS=$(ls -1 .claude/commands/*.md 2>/dev/null | wc -l | tr -d ' ')

PLUGIN_SKILLS=$(ls -1 plugins/autonomous-dev/skills/ 2>/dev/null | wc -l | tr -d ' ')
LOCAL_SKILLS=$(ls -1 .claude/skills/ 2>/dev/null | wc -l | tr -d ' ')

PLUGIN_HOOKS=$(ls -1 plugins/autonomous-dev/hooks/*.py 2>/dev/null | wc -l | tr -d ' ')
LOCAL_HOOKS=$(ls -1 .claude/hooks/*.py 2>/dev/null | wc -l | tr -d ' ')

# Compare
echo "Agents:   Plugin=$PLUGIN_AGENTS, Local=$LOCAL_AGENTS"
[ "$PLUGIN_AGENTS" -eq "$LOCAL_AGENTS" ] && echo "  ✅ In sync" || echo "  ⚠️  Out of sync"

echo "Commands: Plugin=$PLUGIN_COMMANDS, Local=$LOCAL_COMMANDS"
[ "$PLUGIN_COMMANDS" -eq "$LOCAL_COMMANDS" ] && echo "  ✅ In sync" || echo "  ⚠️  Out of sync"

echo "Skills:   Plugin=$PLUGIN_SKILLS, Local=$LOCAL_SKILLS"
[ "$PLUGIN_SKILLS" -eq "$LOCAL_SKILLS" ] && echo "  ✅ In sync" || echo "  ⚠️  Out of sync"

echo "Hooks:    Plugin=$PLUGIN_HOOKS, Local=$LOCAL_HOOKS"
[ "$PLUGIN_HOOKS" -eq "$LOCAL_HOOKS" ] && echo "  ✅ In sync" || echo "  ⚠️  Out of sync"

echo ""

# Overall status
if [ "$PLUGIN_AGENTS" -eq "$LOCAL_AGENTS" ] && \
   [ "$PLUGIN_COMMANDS" -eq "$LOCAL_COMMANDS" ] && \
   [ "$PLUGIN_SKILLS" -eq "$LOCAL_SKILLS" ] && \
   [ "$PLUGIN_HOOKS" -eq "$LOCAL_HOOKS" ]; then
    echo "✅ All components in sync!"
else
    echo "⚠️  Some components out of sync"
    echo ""
    echo "To sync: ./scripts/refresh-claude-settings.sh"
fi
