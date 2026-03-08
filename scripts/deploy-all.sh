#!/usr/bin/env bash
#
# Deploy autonomous-dev plugin to all repos on both Macs.
# Combines deploy_local.sh (with validation) and deploy-to-repos.sh (with remote).
#
# Usage:
#   ./scripts/deploy-all.sh              # Deploy everywhere
#   ./scripts/deploy-all.sh --local      # Local machine only
#   ./scripts/deploy-all.sh --remote     # Mac Studio only
#   ./scripts/deploy-all.sh --dry-run    # Preview what would happen
#   ./scripts/deploy-all.sh --no-global  # Skip global ~/.claude/ sync
#   ./scripts/deploy-all.sh --skip-validate  # Skip post-deploy validation
#
# Configuration (override via env vars):
#   REMOTE_HOST  - SSH host (default: andrewkaszubski@10.55.0.2)
#   LOCAL_REPOS  - Space-separated local repo names (default: anyclaude realign spektiv)
#   REMOTE_REPOS - Space-separated remote repo names (default: anyclaude realign spektiv)
#
# What gets deployed:
#   Global (~/.claude/): hooks, lib, config (shared across all repos)
#   Per-repo (<repo>/.claude/): hooks, commands, agents, lib, config, skills, scripts, templates

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
PLUGIN_SRC="$REPO_DIR/plugins/autonomous-dev"
GLOBAL_DEST="$HOME/.claude"

REMOTE_HOST="${REMOTE_HOST:-andrewkaszubski@10.55.0.2}"
LOCAL_REPOS="${LOCAL_REPOS:-anyclaude realign spektiv}"
REMOTE_REPOS="${REMOTE_REPOS:-anyclaude realign spektiv}"
SUBDIRS="hooks commands agents lib templates config skills scripts"
GLOBAL_SUBDIRS="hooks lib config"

# Key files to validate after deploy
KEY_FILES="hooks/unified_pre_tool.py hooks/session_activity_logger.py lib/pipeline_intent_validator.py"
# Stale hooks that should have been removed in previous cleanup
STALE_HOOKS="pre_tool_use.py auto_approve_tool.py unified_pre_tool_use.py"

# Parse flags
DO_LOCAL=true
DO_REMOTE=true
DO_GLOBAL=true
DRY_RUN=false
SKIP_VALIDATE=false
ERRORS=0

for arg in "$@"; do
    case "$arg" in
        --local)  DO_REMOTE=false ;;
        --remote) DO_LOCAL=false; DO_GLOBAL=false ;;
        --dry-run) DRY_RUN=true ;;
        --no-global) DO_GLOBAL=false ;;
        --skip-validate) SKIP_VALIDATE=true ;;
        --help|-h)
            head -17 "$0" | tail -16
            exit 0
            ;;
        *) echo "Unknown flag: $arg"; exit 1 ;;
    esac
done

# --- Helpers ---

log_ok()   { echo "    ✓ $1"; }
log_fail() { echo "    ✗ $1"; ERRORS=$((ERRORS + 1)); }
log_warn() { echo "    ⚠ $1"; }

checksum() {
    md5 -q "$1" 2>/dev/null || md5sum "$1" 2>/dev/null | cut -d' ' -f1
}

# --- Deploy functions ---

fix_permissions() {
    local target="$1"
    # Hooks and scripts must be executable
    find "$target/hooks" -name "*.py" -exec chmod 755 {} \; 2>/dev/null || true
    find "$target/hooks" -name "*.sh" -exec chmod 755 {} \; 2>/dev/null || true
    find "$target/scripts" -name "*.py" -exec chmod 755 {} \; 2>/dev/null || true
    find "$target/scripts" -name "*.sh" -exec chmod 755 {} \; 2>/dev/null || true
    # Libraries should be readable (not executable)
    find "$target/lib" -name "*.py" -exec chmod 644 {} \; 2>/dev/null || true
}

deploy_global() {
    echo "Global (~/.claude):"
    if $DRY_RUN; then
        echo "  [dry-run] Would sync $GLOBAL_SUBDIRS"
        return
    fi

    for subdir in $GLOBAL_SUBDIRS; do
        if [ -d "$PLUGIN_SRC/$subdir" ]; then
            mkdir -p "$GLOBAL_DEST/$subdir"
            rsync -a "$PLUGIN_SRC/$subdir/" "$GLOBAL_DEST/$subdir/"
        fi
    done
    fix_permissions "$GLOBAL_DEST"
    echo "  Synced: $GLOBAL_SUBDIRS"
}

deploy_repo() {
    local repo_path="$1"
    local name="$(basename "$repo_path")"
    local target="$repo_path/.claude"

    if [ ! -d "$repo_path" ]; then
        echo "  SKIP $name (not found)"
        return
    fi
    if [ ! -d "$target" ]; then
        echo "  SKIP $name (no .claude/)"
        return
    fi

    if $DRY_RUN; then
        echo "  [dry-run] Would deploy to $name"
        return
    fi

    for subdir in $SUBDIRS; do
        if [ -d "$PLUGIN_SRC/$subdir" ]; then
            mkdir -p "$target/$subdir"
            rsync -a --delete "$PLUGIN_SRC/$subdir/" "$target/$subdir/"
        fi
    done
    fix_permissions "$target"
    echo "  Deployed: $name"
}

deploy_remote() {
    echo "=== Remote ($REMOTE_HOST) ==="

    # Check connectivity first
    if ! ssh -o ConnectTimeout=5 -o BatchMode=yes "$REMOTE_HOST" "echo ok" >/dev/null 2>&1; then
        echo "  SKIP (cannot connect to $REMOTE_HOST)"
        return
    fi

    if $DRY_RUN; then
        echo "  [dry-run] Would git pull + deploy to $REMOTE_REPOS"
        return
    fi

    # Build validation script for remote
    local validate_script=""
    if ! $SKIP_VALIDATE; then
        validate_script="
echo ''
echo '  Post-deploy validation:'
errors=0
for repo in $REMOTE_REPOS; do
    target=\"\$HOME/Dev/\$repo/.claude\"
    [ ! -d \"\$target\" ] && continue
    # Syntax check
    if python3 -c \"import ast; ast.parse(open('\$target/hooks/unified_pre_tool.py').read())\" 2>/dev/null; then
        echo \"    ✓ \$repo: unified_pre_tool.py parses cleanly\"
    else
        echo \"    ✗ \$repo: unified_pre_tool.py SYNTAX ERROR\"
        errors=\$((errors + 1))
    fi
    # NATIVE_TOOLS check
    if grep -q 'NATIVE_TOOLS' \"\$target/hooks/unified_pre_tool.py\" 2>/dev/null; then
        echo \"    ✓ \$repo: NATIVE_TOOLS fast path present\"
    else
        echo \"    ✗ \$repo: NATIVE_TOOLS fast path MISSING\"
        errors=\$((errors + 1))
    fi
    # Agent tool fix check (the observability fix we just made)
    if grep -q '\"Agent\"' \"\$target/hooks/session_activity_logger.py\" 2>/dev/null; then
        echo \"    ✓ \$repo: session_activity_logger handles Agent tool\"
    else
        echo \"    ✗ \$repo: session_activity_logger MISSING Agent tool handling\"
        errors=\$((errors + 1))
    fi
    # pipeline_intent_validator check
    if grep -q 'AGENT_TOOL_NAMES' \"\$target/lib/pipeline_intent_validator.py\" 2>/dev/null; then
        echo \"    ✓ \$repo: pipeline_intent_validator uses AGENT_TOOL_NAMES\"
    else
        echo \"    ✗ \$repo: pipeline_intent_validator MISSING AGENT_TOOL_NAMES\"
        errors=\$((errors + 1))
    fi
done
if [ \$errors -eq 0 ]; then
    echo '  All remote validations passed'
else
    echo \"  \$errors remote validation errors\"
fi
"
    fi

    ssh "$REMOTE_HOST" "$(cat <<REMOTE_EOF
set -euo pipefail
echo "  Pulling latest from master..."
cd ~/Dev/autonomous-dev && git pull --ff-only || { echo '  git pull failed'; exit 1; }

echo "  Deploying to repos..."
for repo in $REMOTE_REPOS; do
    target="\$HOME/Dev/\$repo/.claude"
    if [ ! -d "\$target" ]; then
        echo "  SKIP \$repo (no .claude/)"
        continue
    fi
    for subdir in $SUBDIRS; do
        if [ -d "plugins/autonomous-dev/\$subdir" ]; then
            mkdir -p "\$target/\$subdir"
            cp -rf plugins/autonomous-dev/\$subdir/* "\$target/\$subdir/" 2>/dev/null || true
        fi
    done
    # Fix permissions
    find "\$target/hooks" -name "*.py" -exec chmod 755 {} \; 2>/dev/null || true
    find "\$target/hooks" -name "*.sh" -exec chmod 755 {} \; 2>/dev/null || true
    find "\$target/scripts" -name "*.py" -exec chmod 755 {} \; 2>/dev/null || true
    find "\$target/scripts" -name "*.sh" -exec chmod 755 {} \; 2>/dev/null || true
    find "\$target/lib" -name "*.py" -exec chmod 644 {} \; 2>/dev/null || true
    echo "  Deployed: \$repo"
done

# Also deploy global hooks/lib/config
echo "  Deploying global (~/.claude)..."
for subdir in hooks lib config; do
    if [ -d "plugins/autonomous-dev/\$subdir" ]; then
        mkdir -p "\$HOME/.claude/\$subdir"
        cp -rf plugins/autonomous-dev/\$subdir/* "\$HOME/.claude/\$subdir/" 2>/dev/null || true
    fi
done
find "\$HOME/.claude/hooks" -name "*.py" -exec chmod 755 {} \; 2>/dev/null || true
find "\$HOME/.claude/hooks" -name "*.sh" -exec chmod 755 {} \; 2>/dev/null || true
find "\$HOME/.claude/lib" -name "*.py" -exec chmod 644 {} \; 2>/dev/null || true
echo "  Synced global: hooks lib config"
$validate_script
REMOTE_EOF
)"
}

validate_local() {
    local repo_path="$1"
    local name="$(basename "$repo_path")"
    local dest="$repo_path/.claude"

    [ ! -d "$repo_path" ] && return
    [ ! -d "$dest" ] && return

    echo "  $name:"

    # 1. Syntax check on key hooks
    if python3 -c "import ast; ast.parse(open('$dest/hooks/unified_pre_tool.py').read())" 2>/dev/null; then
        log_ok "unified_pre_tool.py parses cleanly"
    else
        log_fail "unified_pre_tool.py SYNTAX ERROR"
    fi

    # 2. NATIVE_TOOLS fast path
    if grep -q "NATIVE_TOOLS" "$dest/hooks/unified_pre_tool.py" 2>/dev/null; then
        log_ok "NATIVE_TOOLS fast path present"
    else
        log_fail "NATIVE_TOOLS fast path MISSING"
    fi

    # 3. No stale auto_approval_engine import
    if grep -q "from auto_approval_engine import" "$dest/hooks/unified_pre_tool.py" 2>/dev/null; then
        log_fail "still imports auto_approval_engine"
    else
        log_ok "no auto_approval_engine dependency"
    fi

    # 4. Agent tool fix (observability - issue #380)
    if grep -q '"Agent"' "$dest/hooks/session_activity_logger.py" 2>/dev/null; then
        log_ok "session_activity_logger handles Agent tool"
    else
        log_fail "session_activity_logger MISSING Agent tool handling"
    fi

    # 5. AGENT_TOOL_NAMES constant (pipeline_intent_validator)
    if grep -q "AGENT_TOOL_NAMES" "$dest/lib/pipeline_intent_validator.py" 2>/dev/null; then
        log_ok "pipeline_intent_validator uses AGENT_TOOL_NAMES"
    else
        log_fail "pipeline_intent_validator MISSING AGENT_TOOL_NAMES"
    fi

    # 6. Key files match source (checksum)
    for key_file in $KEY_FILES; do
        if [ -f "$dest/$key_file" ] && [ -f "$PLUGIN_SRC/$key_file" ]; then
            local src_hash dest_hash
            src_hash=$(checksum "$PLUGIN_SRC/$key_file")
            dest_hash=$(checksum "$dest/$key_file")
            if [ "$src_hash" = "$dest_hash" ]; then
                log_ok "$(basename "$key_file") matches source"
            else
                log_fail "$(basename "$key_file") DIFFERS from source"
            fi
        fi
    done

    # 7. Settings.json hooks exist on disk
    if [ -f "$dest/settings.json" ]; then
        local missing_hooks
        missing_hooks=$(python3 -c "
import json, os
with open('$dest/settings.json') as f:
    s = json.load(f)
missing = []
for event, matchers in s.get('hooks', {}).items():
    for matcher in matchers:
        for hook in matcher.get('hooks', []):
            cmd = hook.get('command', '')
            for word in cmd.split():
                if word.endswith('.py'):
                    path = os.path.join('$repo_path', word) if not word.startswith('/') else os.path.expanduser(word)
                    if not os.path.exists(path):
                        missing.append(word)
if missing:
    print(' '.join(missing))
" 2>/dev/null || true)
        if [ -z "$missing_hooks" ]; then
            log_ok "all settings.json hooks exist on disk"
        else
            log_fail "hooks missing on disk: $missing_hooks"
        fi
    fi

    # 8. Stale hooks
    local found_stale=""
    for stale in $STALE_HOOKS; do
        if [ -f "$dest/hooks/$stale" ]; then
            found_stale="$found_stale $stale"
        fi
    done
    if [ -n "$found_stale" ]; then
        log_warn "stale hooks found:$found_stale"
    fi
}

# --- Main ---

echo "=== autonomous-dev deploy-all ==="
echo "Source: $PLUGIN_SRC"
echo "Local repos: $LOCAL_REPOS"
echo "Remote repos: $REMOTE_REPOS ($REMOTE_HOST)"
echo ""

# 1. Global deploy
if $DO_GLOBAL; then
    deploy_global
    echo ""
fi

# 2. Local repos
if $DO_LOCAL; then
    echo "=== Local machine ==="
    for repo_name in $LOCAL_REPOS; do
        deploy_repo "$HOME/Dev/$repo_name"
    done
    echo ""
fi

# 3. Remote
if $DO_REMOTE; then
    deploy_remote
    echo ""
fi

# 4. Post-deploy validation (local)
if $DO_LOCAL && ! $DRY_RUN && ! $SKIP_VALIDATE; then
    echo "=== Post-deploy validation ==="
    echo ""

    # Validate global
    echo "  ~/.claude:"
    if python3 -c "import ast; ast.parse(open('$GLOBAL_DEST/hooks/unified_pre_tool.py').read())" 2>/dev/null; then
        log_ok "global hook parses cleanly"
    else
        log_fail "global hook SYNTAX ERROR"
    fi
    src_hash=$(checksum "$PLUGIN_SRC/hooks/unified_pre_tool.py")
    dest_hash=$(checksum "$GLOBAL_DEST/hooks/unified_pre_tool.py")
    if [ "$src_hash" = "$dest_hash" ]; then
        log_ok "global hook matches source"
    else
        log_fail "global hook DIFFERS from source"
    fi
    echo ""

    # Validate each local repo
    for repo_name in $LOCAL_REPOS; do
        validate_local "$HOME/Dev/$repo_name"
    done
    echo ""

    # Summary
    if [ $ERRORS -eq 0 ]; then
        echo "=== ALL VALIDATIONS PASSED ==="
    else
        echo "=== $ERRORS VALIDATION ERRORS ==="
        echo "Fix errors above before using Claude Code in affected repos."
    fi
fi

echo ""
echo "Done. Restart Claude Code (Cmd+Q) in affected repos to pick up changes."
