#!/bin/bash
# Deploy autonomous-dev plugin to all local repos + global hooks.
# Run after pushing changes to master.
#
# Usage: ./scripts/deploy_local.sh [--dry-run]

set -euo pipefail

PLUGIN_SRC="$(cd "$(dirname "$0")/.." && pwd)/plugins/autonomous-dev"
GLOBAL_DEST="$HOME/.claude"
DRY_RUN="${1:-}"

# Repos to deploy to (add/remove as needed)
REPOS=(
    "$HOME/Dev/realign"
    "$HOME/Dev/anyclaude"
    "$HOME/Dev/spektiv"
)

# Subdirs to sync
SUBDIRS=(hooks commands agents lib config skills scripts templates)

deploy_to() {
    local dest="$1/.claude"
    local name="$(basename "$1")"

    if [ ! -d "$1" ]; then
        echo "  SKIP $name (not found)"
        return
    fi

    echo "  → $name"
    for subdir in "${SUBDIRS[@]}"; do
        if [ -d "$PLUGIN_SRC/$subdir" ]; then
            if [ "$DRY_RUN" = "--dry-run" ]; then
                echo "    would sync $subdir/"
            else
                mkdir -p "$dest/$subdir"
                rsync -a --delete "$PLUGIN_SRC/$subdir/" "$dest/$subdir/"
            fi
        fi
    done
}

echo "=== autonomous-dev local deploy ==="
echo "Source: $PLUGIN_SRC"
echo ""

# 1. Global hooks + libs
echo "Global (~/.claude):"
if [ "$DRY_RUN" = "--dry-run" ]; then
    echo "  would sync hooks/ lib/ config/"
else
    for subdir in hooks lib config; do
        if [ -d "$PLUGIN_SRC/$subdir" ]; then
            mkdir -p "$GLOBAL_DEST/$subdir"
            rsync -a "$PLUGIN_SRC/$subdir/" "$GLOBAL_DEST/$subdir/"
        fi
    done
    echo "  → synced hooks, lib, config"
fi
echo ""

# 2. Local repos
echo "Repos:"
for repo in "${REPOS[@]}"; do
    deploy_to "$repo"
done
echo ""

if [ "$DRY_RUN" = "--dry-run" ]; then
    echo "DRY RUN — no files changed"
else
    echo "DONE — restart Claude Code (Cmd+Q) for hook changes to take effect"
fi
