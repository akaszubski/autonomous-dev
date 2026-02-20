#!/usr/bin/env bash
#
# Deploy autonomous-dev plugin to all repos across local and remote machines.
#
# Usage:
#   ./scripts/deploy-to-repos.sh              # Deploy to all repos on all machines
#   ./scripts/deploy-to-repos.sh --local      # Local machine only
#   ./scripts/deploy-to-repos.sh --remote     # Remote (Mac Studio) only
#   ./scripts/deploy-to-repos.sh --dry-run    # Show what would be deployed
#
# Configuration:
#   REMOTE_HOST - SSH host for Mac Studio (default: andrewkaszubski@10.55.0.2)
#   REPOS       - Space-separated repo names under ~/Dev/ (default: anyclaude realign spektiv)
#
# IMPORTANT: Never use brace expansion with cp -rf to deploy.
#   BAD:  cp -rf plugins/autonomous-dev/{hooks,lib}/ "$repo/.claude/"   # dumps flat!
#   GOOD: per-subdir loop with mkdir -p + cp -rf subdir/* target/subdir/

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
PLUGIN_SRC="$REPO_DIR/plugins/autonomous-dev"

REMOTE_HOST="${REMOTE_HOST:-andrewkaszubski@10.55.0.2}"
REPOS="${REPOS:-anyclaude realign spektiv}"
SUBDIRS="hooks commands agents lib templates config skills scripts"

# Parse flags
LOCAL=true
REMOTE=true
DRY_RUN=false

for arg in "$@"; do
    case "$arg" in
        --local)  REMOTE=false ;;
        --remote) LOCAL=false ;;
        --dry-run) DRY_RUN=true ;;
        --help|-h)
            head -14 "$0" | tail -13
            exit 0
            ;;
        *) echo "Unknown flag: $arg"; exit 1 ;;
    esac
done

deploy_local() {
    local repo="$1"
    local target="$repo/.claude"

    if [ ! -d "$target" ]; then
        echo "  Skipping $(basename "$repo") (no .claude/)"
        return
    fi

    if $DRY_RUN; then
        echo "  [dry-run] Would deploy to $target"
        return
    fi

    for subdir in $SUBDIRS; do
        if [ -d "$PLUGIN_SRC/$subdir" ]; then
            mkdir -p "$target/$subdir"
            cp -rf "$PLUGIN_SRC/$subdir"/* "$target/$subdir/" 2>/dev/null || true
        fi
    done
    echo "  Deployed to $(basename "$repo")"
}

deploy_remote() {
    local host="$1"

    echo "Connecting to $host..."

    if $DRY_RUN; then
        echo "  [dry-run] Would git pull + deploy to $REPOS"
        return
    fi

    # Build remote script
    local remote_script="
cd ~/Dev/autonomous-dev && git pull --ff-only || { echo 'git pull failed'; exit 1; }
for repo in $REPOS; do
    target=\"\$HOME/Dev/\$repo/.claude\"
    if [ ! -d \"\$target\" ]; then
        echo \"  Skipping \$repo (no .claude/)\"
        continue
    fi
    for subdir in $SUBDIRS; do
        if [ -d \"plugins/autonomous-dev/\$subdir\" ]; then
            mkdir -p \"\$target/\$subdir\"
            cp -rf plugins/autonomous-dev/\$subdir/* \"\$target/\$subdir/\" 2>/dev/null || true
        fi
    done
    echo \"  Deployed to \$repo\"
done
"
    ssh "$host" "$remote_script"
}

echo "autonomous-dev deploy"
echo "  Source: $PLUGIN_SRC"
echo "  Repos: $REPOS"
echo "  Subdirs: $SUBDIRS"
echo ""

if $LOCAL; then
    echo "=== Local machine ==="
    for repo_name in $REPOS; do
        deploy_local "$HOME/Dev/$repo_name"
    done
    echo ""
fi

if $REMOTE; then
    echo "=== Remote ($REMOTE_HOST) ==="
    deploy_remote "$REMOTE_HOST"
    echo ""
fi

echo "Done. Restart Claude Code (Cmd+Q) in affected repos to pick up changes."
