#!/usr/bin/env bash
# PreToolUseWrite hook for autonomous-dev v2.0
# Blocks writes to sensitive files (credentials, git internals, etc.)

set -euo pipefail

TOOL_USE=$(cat)
FILE_PATH=$(echo "$TOOL_USE" | jq -r '.parameters.file_path // empty')

# Block sensitive files
if echo "$FILE_PATH" | grep -qE "\.env$|\.env\..*|\.git/|credentials|secrets|private.*key|\.pem$|\.key$"; then
  cat <<EOF
{
  "permissionDecision": "deny",
  "reason": "🔒 Cannot write to sensitive file: $FILE_PATH\n\nProtected patterns: .env, .git/, credentials, secrets, private keys"
}
EOF
  exit 0
fi

# Block PROJECT.md from non-orchestrator agents (prevent drift)
if echo "$FILE_PATH" | grep -qE "PROJECT\.md$"; then
  cat <<EOF
{
  "permissionDecision": "deny",
  "reason": "🔒 PROJECT.md is protected\n\nTo update project goals/scope/constraints, edit PROJECT.md manually.\nAutomatic modifications would compromise alignment validation."
}
EOF
  exit 0
fi

# Allow other files
echo '{"permissionDecision": "allow"}'
