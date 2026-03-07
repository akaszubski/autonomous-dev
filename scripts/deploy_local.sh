#!/bin/bash
# Deploy autonomous-dev plugin to all local repos + global hooks.
# Run after pushing changes to master.
#
# Usage: ./scripts/deploy_local.sh [--dry-run] [--skip-validate]

set -euo pipefail

PLUGIN_SRC="$(cd "$(dirname "$0")/.." && pwd)/plugins/autonomous-dev"
GLOBAL_DEST="$HOME/.claude"
DRY_RUN=""
SKIP_VALIDATE=""
ERRORS=0

for arg in "$@"; do
    case "$arg" in
        --dry-run) DRY_RUN=1 ;;
        --skip-validate) SKIP_VALIDATE=1 ;;
    esac
done

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
            if [ -n "$DRY_RUN" ]; then
                echo "    would sync $subdir/"
            else
                mkdir -p "$dest/$subdir"
                rsync -a --delete "$PLUGIN_SRC/$subdir/" "$dest/$subdir/"
            fi
        fi
    done
}

validate_repo() {
    local repo="$1"
    local name="$(basename "$repo")"
    local dest="$repo/.claude"
    local repo_errors=0

    if [ ! -d "$repo" ]; then
        return
    fi

    echo "  $name:"

    # 1. Check unified_pre_tool.py exists and has NATIVE_TOOLS fast path
    if [ -f "$dest/hooks/unified_pre_tool.py" ]; then
        if grep -q "NATIVE_TOOLS" "$dest/hooks/unified_pre_tool.py"; then
            echo "    ✓ unified_pre_tool.py has NATIVE_TOOLS fast path"
        else
            echo "    ✗ unified_pre_tool.py MISSING NATIVE_TOOLS fast path"
            repo_errors=$((repo_errors + 1))
        fi
        # Check no auto_approval_engine import
        if grep -q "from auto_approval_engine import" "$dest/hooks/unified_pre_tool.py"; then
            echo "    ✗ unified_pre_tool.py still imports auto_approval_engine"
            repo_errors=$((repo_errors + 1))
        else
            echo "    ✓ no auto_approval_engine dependency"
        fi
    else
        echo "    ✗ unified_pre_tool.py NOT FOUND"
        repo_errors=$((repo_errors + 1))
    fi

    # 2. Check hook can be parsed (no syntax errors)
    if python3 -c "import ast; ast.parse(open('$dest/hooks/unified_pre_tool.py').read())" 2>/dev/null; then
        echo "    ✓ unified_pre_tool.py parses cleanly"
    else
        echo "    ✗ unified_pre_tool.py has SYNTAX ERRORS"
        repo_errors=$((repo_errors + 1))
    fi

    # 3. Check settings.json references hooks that exist
    if [ -f "$dest/settings.json" ]; then
        local missing_hooks
        missing_hooks=$(python3 -c "
import json, os, sys
with open('$dest/settings.json') as f:
    s = json.load(f)
missing = []
for event, matchers in s.get('hooks', {}).items():
    for matcher in matchers:
        for hook in matcher.get('hooks', []):
            cmd = hook.get('command', '')
            # Extract the .py file path from the command
            for word in cmd.split():
                if word.endswith('.py'):
                    # Resolve relative to repo
                    path = os.path.join('$repo', word) if not word.startswith('/') else os.path.expanduser(word)
                    if not os.path.exists(path):
                        missing.append(f'{event}: {word}')
if missing:
    print('\n'.join(missing))
" 2>/dev/null)
        if [ -z "$missing_hooks" ]; then
            echo "    ✓ all hooks in settings.json exist on disk"
        else
            echo "    ✗ hooks in settings.json missing on disk:"
            echo "$missing_hooks" | while read -r line; do echo "      - $line"; done
            repo_errors=$((repo_errors + 1))
        fi
    fi

    # 4. Check for stale hooks that should have been removed
    local stale_hooks=""
    for stale in pre_tool_use.py auto_approve_tool.py unified_pre_tool_use.py; do
        if [ -f "$dest/hooks/$stale" ]; then
            stale_hooks="$stale_hooks $stale"
        fi
    done
    if [ -z "$stale_hooks" ]; then
        echo "    ✓ no stale hooks found"
    else
        echo "    ⚠ stale hooks found:$stale_hooks (consider removing)"
    fi

    # 5. Check key files match source (checksum)
    local key_file="hooks/unified_pre_tool.py"
    if [ -f "$dest/$key_file" ] && [ -f "$PLUGIN_SRC/$key_file" ]; then
        local src_hash dest_hash
        src_hash=$(md5 -q "$PLUGIN_SRC/$key_file" 2>/dev/null || md5sum "$PLUGIN_SRC/$key_file" | cut -d' ' -f1)
        dest_hash=$(md5 -q "$dest/$key_file" 2>/dev/null || md5sum "$dest/$key_file" | cut -d' ' -f1)
        if [ "$src_hash" = "$dest_hash" ]; then
            echo "    ✓ unified_pre_tool.py matches source"
        else
            echo "    ✗ unified_pre_tool.py DIFFERS from source (stale deploy?)"
            repo_errors=$((repo_errors + 1))
        fi
    fi

    ERRORS=$((ERRORS + repo_errors))
}

echo "=== autonomous-dev local deploy ==="
echo "Source: $PLUGIN_SRC"
echo ""

# 1. Global hooks + libs
echo "Global (~/.claude):"
if [ -n "$DRY_RUN" ]; then
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

# 3. Post-deploy validation
if [ -n "$DRY_RUN" ]; then
    echo "DRY RUN — no files changed"
elif [ -n "$SKIP_VALIDATE" ]; then
    echo "DONE (validation skipped)"
else
    echo "=== Post-deploy validation ==="
    echo ""

    # Validate global
    echo "  ~/.claude:"
    if python3 -c "import ast; ast.parse(open('$GLOBAL_DEST/hooks/unified_pre_tool.py').read())" 2>/dev/null; then
        echo "    ✓ global hook parses cleanly"
    else
        echo "    ✗ global hook has SYNTAX ERRORS"
        ERRORS=$((ERRORS + 1))
    fi
    src_hash=$(md5 -q "$PLUGIN_SRC/hooks/unified_pre_tool.py" 2>/dev/null)
    dest_hash=$(md5 -q "$GLOBAL_DEST/hooks/unified_pre_tool.py" 2>/dev/null)
    if [ "$src_hash" = "$dest_hash" ]; then
        echo "    ✓ global hook matches source"
    else
        echo "    ✗ global hook DIFFERS from source"
        ERRORS=$((ERRORS + 1))
    fi
    echo ""

    # Validate each repo
    for repo in "${REPOS[@]}"; do
        validate_repo "$repo"
    done
    echo ""

    # Summary
    if [ $ERRORS -eq 0 ]; then
        echo "=== ALL VALIDATIONS PASSED ==="
    else
        echo "=== $ERRORS VALIDATION ERRORS ==="
        echo "Fix errors above before using Claude Code in affected repos."
    fi
    echo ""
    echo "Restart Claude Code (Cmd+Q) for hook changes to take effect."
fi
