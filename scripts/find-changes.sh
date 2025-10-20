#!/bin/bash
# Find files that differ between plugin and local

echo "🔍 Finding differences between plugin and local..."
echo ""

FOUND_DIFF=0

# Check commands
for file in plugins/autonomous-dev/commands/*.md; do
    filename=$(basename "$file")
    if [ -f ".claude/commands/$filename" ]; then
        if ! diff -q "$file" ".claude/commands/$filename" >/dev/null 2>&1; then
            echo "⚠️  DIFFERENT: commands/$filename"
            FOUND_DIFF=1
        fi
    else
        echo "❌ MISSING in local: commands/$filename"
        FOUND_DIFF=1
    fi
done

# Check agents
for file in plugins/autonomous-dev/agents/*.md; do
    filename=$(basename "$file")
    if [ -f ".claude/agents/$filename" ]; then
        if ! diff -q "$file" ".claude/agents/$filename" >/dev/null 2>&1; then
            echo "⚠️  DIFFERENT: agents/$filename"
            FOUND_DIFF=1
        fi
    else
        echo "❌ MISSING in local: agents/$filename"
        FOUND_DIFF=1
    fi
done

# Check skills
for dir in plugins/autonomous-dev/skills/*/; do
    skillname=$(basename "$dir")
    if [ -d ".claude/skills/$skillname" ]; then
        # Check SKILL.md if exists
        if [ -f "plugins/autonomous-dev/skills/$skillname/SKILL.md" ] && \
           [ -f ".claude/skills/$skillname/SKILL.md" ]; then
            if ! diff -q "plugins/autonomous-dev/skills/$skillname/SKILL.md" \
                        ".claude/skills/$skillname/SKILL.md" >/dev/null 2>&1; then
                echo "⚠️  DIFFERENT: skills/$skillname/SKILL.md"
                FOUND_DIFF=1
            fi
        fi
    else
        echo "❌ MISSING in local: skills/$skillname/"
        FOUND_DIFF=1
    fi
done

# Check hooks
for file in plugins/autonomous-dev/hooks/*.py; do
    filename=$(basename "$file")
    if [ -f ".claude/hooks/$filename" ]; then
        if ! diff -q "$file" ".claude/hooks/$filename" >/dev/null 2>&1; then
            echo "⚠️  DIFFERENT: hooks/$filename"
            FOUND_DIFF=1
        fi
    else
        echo "❌ MISSING in local: hooks/$filename"
        FOUND_DIFF=1
    fi
done

echo ""
if [ $FOUND_DIFF -eq 0 ]; then
    echo "✅ No differences found - everything in sync!"
else
    echo "⚠️  Differences found"
    echo ""
    echo "To see specific changes:"
    echo "  diff .claude/commands/FILE plugins/autonomous-dev/commands/FILE"
    echo ""
    echo "To sync from plugin to local:"
    echo "  ./scripts/refresh-claude-settings.sh"
    echo ""
    echo "To copy local changes to plugin:"
    echo "  cp .claude/commands/FILE plugins/autonomous-dev/commands/FILE"
fi

exit $FOUND_DIFF
