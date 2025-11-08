#!/bin/bash
# UserPromptSubmit hook: Auto-track issues in background
#
# Runs automatically after each prompt in Claude Code
# Non-blocking (runs in background)
#
# Configuration (.env):
# GITHUB_AUTO_TRACK_ISSUES=true           # Enable
# GITHUB_TRACK_ON_PROMPT=true             # Run on each prompt
# GITHUB_TRACK_BACKGROUND=true            # Run in background

# Load .env
if [ -f .env ]; then
    set -a
    source .env
    set +a
fi

# Check if enabled
if [ "${GITHUB_AUTO_TRACK_ISSUES:-false}" != "true" ]; then
    exit 0
fi

if [ "${GITHUB_TRACK_ON_PROMPT:-false}" != "true" ]; then
    exit 0  # Disabled for prompts
fi

# Find hook script
HOOK_SCRIPT="plugins/autonomous-dev/hooks/auto_track_issues.py"

if [ ! -f "$HOOK_SCRIPT" ]; then
    if [ -f ".claude/hooks/auto_track_issues.py" ]; then
        HOOK_SCRIPT=".claude/hooks/auto_track_issues.py"
    else
        exit 0
    fi
fi

# Run in background if enabled
if [ "${GITHUB_TRACK_BACKGROUND:-true}" = "true" ]; then
    # Background mode (non-blocking)
    python3 "$HOOK_SCRIPT" > /dev/null 2>&1 &
else
    # Foreground mode (blocking)
    python3 "$HOOK_SCRIPT"
fi

exit 0
