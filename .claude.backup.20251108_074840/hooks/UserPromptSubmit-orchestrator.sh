#!/usr/bin/env bash
# UserPromptSubmit hook for autonomous-dev v2.0 orchestrator
# Detects implementation requests and triggers orchestrator subagent

set -euo pipefail

# Read user prompt from stdin
USER_PROMPT=$(cat)

# Detect implementation keywords
if echo "$USER_PROMPT" | grep -qiE "implement|build|create feature|add feature|develop|write code"; then

  # Check if PROJECT.md exists
  if [ -f ".claude/PROJECT.md" ]; then
    # Return JSON to trigger orchestrator
    cat <<EOF
{
  "continue": true,
  "additionalContext": "🤖 **Autonomous Mode Activated (v2.0)**\n\nDetected implementation request. Triggering orchestrator for PROJECT.md-aligned development..."
}
EOF
  else
    # PROJECT.md missing - warn user
    cat <<EOF
{
  "continue": true,
  "additionalContext": "⚠️  **Autonomous mode requires PROJECT.md**\n\nTo use autonomous implementation:\n1. Create .claude/PROJECT.md with GOALS, SCOPE, CONSTRAINTS\n2. See: plugins/autonomous-dev/docs/QUICKSTART.md"
}
EOF
  fi

else
  # No implementation keywords - pass through
  echo '{"continue": true}'
fi
