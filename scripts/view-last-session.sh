#!/bin/bash
# View Last Session - Make autonomous workflow visible
# Usage: ./scripts/view-last-session.sh [agent-name]

set -e

SESSION_DIR="docs/sessions"

# Check if session directory exists
if [ ! -d "$SESSION_DIR" ]; then
    echo "❌ No sessions directory found at $SESSION_DIR"
    exit 1
fi

# Get filter if provided
FILTER="${1:-}"

if [ -n "$FILTER" ]; then
    # Filter by agent name
    LATEST=$(ls -t "$SESSION_DIR"/*${FILTER}*.md 2>/dev/null | head -1)
    if [ -z "$LATEST" ]; then
        echo "❌ No sessions found for agent: $FILTER"
        echo ""
        echo "Available agents:"
        ls "$SESSION_DIR"/*.md 2>/dev/null | xargs basename -a | cut -d'-' -f6 | cut -d'.' -f1 | sort -u
        exit 1
    fi
else
    # Get most recent session
    LATEST=$(ls -t "$SESSION_DIR"/*.md 2>/dev/null | head -1)
    if [ -z "$LATEST" ]; then
        echo "❌ No sessions found"
        exit 1
    fi
fi

# Extract metadata from filename
FILENAME=$(basename "$LATEST")
TIMESTAMP=$(echo "$FILENAME" | cut -d'-' -f1-5)
AGENT=$(echo "$FILENAME" | cut -d'-' -f6 | cut -d'.' -f1)

echo "════════════════════════════════════════════════════════════════"
echo "📋 SESSION VIEWER"
echo "════════════════════════════════════════════════════════════════"
echo ""
echo "Agent:     $AGENT"
echo "Timestamp: $TIMESTAMP"
echo "File:      $LATEST"
echo ""
echo "════════════════════════════════════════════════════════════════"
echo "📝 SESSION CONTENT"
echo "════════════════════════════════════════════════════════════════"
echo ""

cat "$LATEST"

echo ""
echo "════════════════════════════════════════════════════════════════"
echo "📊 SESSION STATS"
echo "════════════════════════════════════════════════════════════════"
echo ""

# Count lines
LINES=$(wc -l < "$LATEST")
echo "Lines: $LINES"

# Count words
WORDS=$(wc -w < "$LATEST")
echo "Words: $WORDS"

# Check for tool usage
if grep -q "Task tool\|Read tool\|Write tool\|Bash tool" "$LATEST"; then
    echo ""
    echo "Tools used:"
    grep -o "Task tool\|Read tool\|Write tool\|Bash tool\|Edit tool\|Grep tool\|Glob tool" "$LATEST" | sort | uniq -c | sort -rn
fi

# Check for agent invocations
if grep -qi "orchestrator\|researcher\|planner\|test-master\|implementer\|reviewer\|security-auditor\|doc-master" "$LATEST"; then
    echo ""
    echo "Agents mentioned:"
    grep -ioh "orchestrator\|researcher\|planner\|test-master\|implementer\|reviewer\|security-auditor\|doc-master" "$LATEST" | sort | uniq -c | sort -rn
fi

echo ""
echo "════════════════════════════════════════════════════════════════"
