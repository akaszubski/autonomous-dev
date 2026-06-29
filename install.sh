#!/usr/bin/env bash
#
# autonomous-dev Plugin Installer - PRIMARY INSTALL METHOD
#
# Bootstrap-First Architecture: This is the REQUIRED install method for autonomous-dev.
# The marketplace alone is insufficient because it cannot configure global infrastructure.
# autonomous-dev is a development system, not a simple plugin.
#
# Usage:
#   bash <(curl -sSL https://raw.githubusercontent.com/akaszubski/autonomous-dev/master/install.sh)
#
# What this does (that the marketplace cannot):
#   1. Creates global infrastructure:
#      - ~/.claude/hooks/ (security validation, auto-approval)
#      - ~/.claude/lib/ (Python dependencies)
#      - ~/.claude/settings.json (permission patterns)
#   2. Downloads plugin files to ~/.autonomous-dev-staging/
#   3. Installs /setup command to .claude/commands/
#   4. You restart Claude Code and run /setup
#   5. /setup wizard intelligently handles:
#      - Fresh installs (copies all files, guides PROJECT.md creation)
#      - Brownfield (preserves existing .claude/ files)
#      - Upgrades (updates plugin, preserves customizations)
#
# Why not marketplace alone?
#   The marketplace can download files but CANNOT:
#   - Create directories in ~/.claude/
#   - Modify ~/.claude/settings.json
#   - Install global hooks for all projects
#   - Configure Bash tool permissions
#
# The marketplace is useful as an OPTIONAL supplement for updates after
# this script has run at least once.
#
# Requirements:
#   - curl or wget
#   - Python 3.9+
#   - Claude Code installed
#
# Security:
#   - HTTPS with TLS 1.2+
#   - No sudo required
#

set -euo pipefail

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

# Configuration
GITHUB_REPO="akaszubski/autonomous-dev"
GITHUB_BRANCH="master"
GITHUB_RAW="https://raw.githubusercontent.com/${GITHUB_REPO}/${GITHUB_BRANCH}"
STAGING_DIR="${HOME}/.autonomous-dev-staging"
MANIFEST_FILE="plugins/autonomous-dev/config/install_manifest.json"

# Parse arguments
VERBOSE=false
CLEAN=false
MIGRATE_MCP_REPO=""    # Issue #948: --migrate-mcp-to-repo <path>
MIGRATE_MCP_SERVER=""  # Issue #948: --server <name> (paired with above)
RESET_HOOKS=false      # Issue #949: --reset-hooks recovery mode
GLOBAL_SETTINGS=false  # Issue #995: opt-in to ~/.claude/settings.json hook registration
UNINSTALL=false        # Issue #951: --uninstall shell-only uninstall
DRY_RUN=false          # Issue #951: --dry-run for --uninstall
UNINSTALL_REPOS=""     # Issue #951: --repos <space-or-comma-separated list>
USER_SCOPE=false       # Issue #952: --scope=user for global install (opt-in)

while [[ $# -gt 0 ]]; do
    case $1 in
        --verbose|-v)
            VERBOSE=true
            shift
            ;;
        --clean)
            CLEAN=true
            shift
            ;;
        --migrate-mcp-to-repo)
            MIGRATE_MCP_REPO="$2"
            shift 2
            ;;
        --server)
            MIGRATE_MCP_SERVER="$2"
            shift 2
            ;;
        --reset-hooks)
            RESET_HOOKS=true
            shift
            ;;
        --global-settings)
            GLOBAL_SETTINGS=true
            shift
            ;;
        --uninstall)
            UNINSTALL=true
            shift
            ;;
        --dry-run)
            DRY_RUN=true
            shift
            ;;
        --repos)
            UNINSTALL_REPOS="$2"
            shift 2
            ;;
        --scope=user|--scope=global)
            USER_SCOPE=true
            shift
            ;;
        --help|-h)
            echo "autonomous-dev Plugin Installer"
            echo ""
            echo "One-liner install for both fresh installs and updates."
            echo ""
            echo "Usage: install.sh [OPTIONS]"
            echo ""
            echo "Options:"
            echo "  --verbose, -v                       Show detailed output"
            echo "  --clean                             Remove existing staging directory first"
            echo "  --migrate-mcp-to-repo <repo-path>   Standalone: migrate one MCP server"
            echo "                                      from ~/.claude/settings.json mcpServers"
            echo "                                      to <repo-path>/.mcp.json (Issue #948)."
            echo "                                      Requires --server <name>."
            echo "                                      Skips the normal install flow."
            echo "  --server <name>                     MCP server name to migrate (key under"
            echo "                                      mcpServers). Used with --migrate-mcp-to-repo."
            echo "  --reset-hooks                       Standalone: strip the hooks block from"
            echo "                                      ~/.claude/settings.json (Issue #949)."
            echo "                                      Backs up to settings.json.preglobal-hooks-strip."
            echo "                                      Preserves permissions, mcpServers, env, model."
            echo "                                      Use when global hooks brick Claude Code."
            echo "                                      Skips the normal install flow."
            echo "  --global-settings                   Opt-in: register autonomous-dev hooks in"
            echo "                                      ~/.claude/settings.json (Issue #995)."
            echo "                                      Default is project-local: hooks are only"
            echo "                                      registered in <repo>/.claude/settings.json."
            echo "                                      Hook FILES are still cached to ~/.claude/hooks/"
            echo "                                      either way (library cache for opt-in repos)."
            echo "  --uninstall                         Standalone: shell-only uninstall (Issue #951)."
            echo "                                      Removes manifest-owned files from"
            echo "                                      ~/.claude/{hooks,lib,commands,agents,scripts},"
            echo "                                      strips autonomous-dev hooks from"
            echo "                                      ~/.claude/settings.json, unregisters from"
            echo "                                      ~/.claude/plugins/installed_plugins.json."
            echo "                                      Backs up everything to"
            echo "                                      ~/.claude/backups/uninstall-YYYYMMDD-HHMMSS/."
            echo "                                      PRESERVES: PROJECT.md, CLAUDE.md, .env,"
            echo "                                      logs/, archive/, memory/, hooks/extensions/."
            echo "                                      Use --dry-run to preview, --repos to also"
            echo "                                      strip per-repo settings.json files."
            echo "                                      Companion to /sync --uninstall (Python path)."
            echo "                                      Skips the normal install flow."
            echo "  --dry-run                           With --uninstall: print the plan, do not"
            echo "                                      delete or modify anything."
            echo "  --repos <list>                      With --uninstall: comma- or space-separated"
            echo "                                      list of repo paths to also clean. Each must"
            echo "                                      exist and contain a .claude/ subdirectory."
            echo "                                      autonomous-dev hook entries in each repo's"
            echo "                                      .claude/settings.json are stripped (with"
            echo "                                      backup); user-added entries are preserved."
            echo "  --scope=user                        Install globally to ~/.claude/ (opt-in)."
            echo "                                      Default: per-repo install to ./.claude/."
            echo "  --help, -h                          Show this help message"
            echo ""
            echo "After running this script:"
            echo "  1. Restart Claude Code (Cmd+Q / Ctrl+Q)"
            echo "  2. Run /setup in your project"
            echo ""
            echo "The /setup wizard will:"
            echo "  - Detect fresh install vs update"
            echo "  - Install all plugin files"
            echo "  - Protect your PROJECT.md and .env"
            echo "  - Guide you through configuration"
            exit 0
            ;;
        *)
            echo -e "${RED}Unknown option: $1${NC}"
            echo "Use --help for usage information"
            exit 1
            ;;
    esac
done


# Issue #952: Determine installation directory based on scope
if [[ "$USER_SCOPE" == "true" ]]; then
    INSTALL_DIR="${HOME}/.claude"
    INSTALL_SCOPE="global"
else
    INSTALL_DIR="$(pwd)/.claude"
    INSTALL_SCOPE="per-repo"
fi
export INSTALL_DIR INSTALL_SCOPE
# Logging functions
log_info() {
    echo -e "${BLUE}ℹ${NC} $1"
}

log_success() {
    echo -e "${GREEN}✓${NC} $1"
}

log_warning() {
    echo -e "${YELLOW}⚠${NC} $1"
}

log_error() {
    echo -e "${RED}✗${NC} $1"
}

log_step() {
    echo -e "${CYAN}→${NC} $1"
}

# Check for curl or wget
check_downloader() {
    if command -v curl &> /dev/null; then
        DOWNLOADER="curl"
    elif command -v wget &> /dev/null; then
        DOWNLOADER="wget"
    else
        log_error "Neither curl nor wget found. Please install one of them."
        exit 1
    fi

    if $VERBOSE; then
        log_info "Using ${DOWNLOADER} for downloads"
    fi
}

# Download file from GitHub
download_file() {
    local url="$1"
    local output="$2"

    # Create parent directory if needed
    mkdir -p "$(dirname "$output")"

    if [[ "$DOWNLOADER" == "curl" ]]; then
        curl --proto '=https' --tlsv1.2 -sSL "$url" -o "$output" 2>/dev/null
    else
        wget --secure-protocol=TLSv1_2 -qO "$output" "$url" 2>/dev/null
    fi
}

# Download manifest and parse file list
download_manifest() {
    log_step "Downloading manifest..."

    local manifest_url="${GITHUB_RAW}/${MANIFEST_FILE}"
    local manifest_path="${STAGING_DIR}/manifest.json"

    if ! download_file "$manifest_url" "$manifest_path"; then
        log_error "Failed to download manifest"
        log_info "URL: ${manifest_url}"
        return 1
    fi

    # Verify it's valid JSON
    if ! python3 -c "import json; json.load(open('${manifest_path}'))" 2>/dev/null; then
        log_error "Invalid manifest (not valid JSON)"
        return 1
    fi

    log_success "Manifest downloaded"
    return 0
}

# Download all files from manifest
download_files() {
    log_step "Downloading plugin files..."

    local manifest_path="${STAGING_DIR}/manifest.json"
    local total_files=0
    local downloaded=0
    local failed=0

    # Use Python to parse manifest and get file list (with path traversal validation)
    local files
    files=$(python3 -c "
import json
import sys

with open('${manifest_path}') as f:
    manifest = json.load(f)

for component, config in manifest.get('components', {}).items():
    for file_path in config.get('files', []):
        # CWE-22: Validate paths to prevent directory traversal
        if '..' in file_path or file_path.startswith('/') or file_path.startswith('~'):
            print(f'SECURITY: Rejected malicious path: {file_path}', file=sys.stderr)
            continue
        # Reject paths with null bytes or other suspicious patterns
        if '\x00' in file_path or '\\\\' in file_path:
            print(f'SECURITY: Rejected suspicious path: {file_path}', file=sys.stderr)
            continue
        print(file_path)
")

    # Count total files
    total_files=$(echo "$files" | wc -l | tr -d ' ')
    log_info "Found ${total_files} files to download"

    # Download each file
    while IFS= read -r file_path; do
        if [[ -z "$file_path" ]]; then
            continue
        fi

        local url="${GITHUB_RAW}/${file_path}"
        local output="${STAGING_DIR}/files/${file_path}"

        if download_file "$url" "$output"; then
            ((downloaded++))
            if $VERBOSE; then
                log_success "  Downloaded: $(basename "$file_path")"
            fi
        else
            ((failed++))
            log_warning "  Failed: $(basename "$file_path")"
        fi

        # Progress indicator (every 20 files)
        if ! $VERBOSE && (( downloaded % 20 == 0 )); then
            echo -ne "\r${CYAN}→${NC} Downloaded ${downloaded}/${total_files} files..."
        fi
    done <<< "$files"

    if ! $VERBOSE; then
        echo ""  # New line after progress
    fi

    if [[ $failed -gt 0 ]]; then
        log_warning "Downloaded ${downloaded}/${total_files} files (${failed} failed)"
        return 1
    fi

    log_success "Downloaded ${downloaded} files"
    return 0
}

# Also download VERSION file
download_version() {
    local version_url="${GITHUB_RAW}/plugins/autonomous-dev/VERSION"
    local version_path="${STAGING_DIR}/VERSION"

    if download_file "$version_url" "$version_path"; then
        local version
        version=$(cat "$version_path")
        log_info "Plugin version: ${version}"
    fi
}

# Bootstrap the /setup command directly (enables fresh installs)
bootstrap_setup_command() {
    log_step "Bootstrapping /setup command..."

    local setup_source="${STAGING_DIR}/files/plugins/autonomous-dev/commands/setup.md"
    local setup_target=".claude/commands/setup.md"

    # Check if setup.md was downloaded
    if [[ ! -f "$setup_source" ]]; then
        log_warning "setup.md not found in staging - /setup command won't be available"
        return 1
    fi

    # CWE-73: Check if source is a symlink (security protection)
    if [[ -L "$setup_source" ]]; then
        log_warning "Security: setup.md is a symlink - skipping for safety"
        return 1
    fi

    # Create .claude/commands/ directory if needed (with error handling)
    if ! mkdir -p ".claude/commands" 2>/dev/null; then
        log_warning "Failed to create .claude/commands/ directory (permission denied?)"
        return 1
    fi

    # Backup existing file if present
    if [[ -f "$setup_target" ]]; then
        cp "$setup_target" "${setup_target}.backup" 2>/dev/null || true
    fi

    # Copy setup.md to enable /setup command (use -P to not follow symlinks)
    if cp -P "$setup_source" "$setup_target"; then
        return 0
    else
        log_warning "Failed to copy setup.md to .claude/commands/"
        return 1
    fi
}

# Register the plugin in ~/.claude/plugins/installed_plugins.json
register_plugin() {
    log_step "Registering autonomous-dev plugin..."
    
    local plugins_dir="${HOME}/.claude/plugins"
    local plugins_file="${plugins_dir}/installed_plugins.json"
    local marketplaces_file="${plugins_dir}/marketplaces.json"
    
    # Create plugins directory if it doesn't exist
    mkdir -p "$plugins_dir" 2>/dev/null || {
        log_warning "Failed to create plugins directory"
        return 1
    }
    
    # Read version from marketplace.json (prefer .claude-plugin/marketplace.json)
    local marketplace_json="${STAGING_DIR}/files/plugins/autonomous-dev/.claude-plugin/marketplace.json"
    if [[ ! -f "$marketplace_json" ]]; then
        # Fallback to plugin.json
        marketplace_json="${STAGING_DIR}/files/plugins/autonomous-dev/plugin.json"
    fi
    
    if [[ ! -f "$marketplace_json" ]]; then
        log_warning "No marketplace.json or plugin.json found - skipping plugin registration"
        return 1
    fi
    
    # Extract plugin info using Python for reliable JSON parsing
    local plugin_info
    plugin_info=$(python3 -c "
import json
import sys

try:
    with open('$marketplace_json') as f:
        data = json.load(f)
    
    # Extract key fields
    plugin = {
        'name': data.get('name', 'autonomous-dev'),
        'version': data.get('version', '3.40.0'),
        'displayName': data.get('displayName', 'Autonomous Development'),
        'source': 'local',
        'sourcePath': '$PROJECT_ROOT/plugins/autonomous-dev'
    }
    
    print(json.dumps(plugin))
except Exception as e:
    print(json.dumps({'error': str(e)}), file=sys.stderr)
    sys.exit(1)
" 2>&1) || {
        log_warning "Failed to parse marketplace.json"
        return 1
    }
    
    # Check if parsing failed
    if echo "$plugin_info" | grep -q '"error"'; then
        log_warning "Failed to extract plugin info from marketplace.json"
        return 1
    fi
    
    # Create or update installed_plugins.json
    if [[ -f "$plugins_file" ]]; then
        # Merge with existing plugins
        python3 -c "
import json
import sys

plugin_info = json.loads('$plugin_info')

try:
    with open('$plugins_file') as f:
        plugins = json.load(f)
    
    # Ensure plugins is a dict with 'plugins' array
    if not isinstance(plugins, dict):
        plugins = {'plugins': []}
    if 'plugins' not in plugins:
        plugins['plugins'] = []
    if not isinstance(plugins['plugins'], list):
        plugins['plugins'] = []
    
    # Remove existing autonomous-dev entry if present
    plugins['plugins'] = [p for p in plugins['plugins'] if p.get('name') != 'autonomous-dev']
    
    # Add our plugin
    plugins['plugins'].append(plugin_info)
    
    with open('$plugins_file', 'w') as f:
        json.dump(plugins, f, indent=2)
    
    print('success')
except Exception as e:
    print(f'error: {e}', file=sys.stderr)
    sys.exit(1)
" || {
            log_warning "Failed to update installed_plugins.json"
            return 1
        }
    else
        # Create new file
        echo "{\"plugins\": [$plugin_info]}" | python3 -m json.tool > "$plugins_file" || {
            log_warning "Failed to create installed_plugins.json"
            return 1
        }
    fi
    
    # Add marketplace entry if missing
    if [[ ! -f "$marketplaces_file" ]]; then
        # Create marketplaces.json with default entry
        cat > "$marketplaces_file" <<'INNER_EOF'
{
  "marketplaces": [
    {
      "name": "akaszubski",
      "url": "https://github.com/akaszubski",
      "description": "Autonomous Development Plugin Marketplace"
    }
  ]
}
INNER_EOF
        log_success "Created marketplaces.json"
    fi
    
    log_success "Plugin registered successfully"
    return 0
}

# Configure global settings.json with correct permission patterns
configure_global_settings() {
    log_step "Configuring global settings..."

    local template_path="${STAGING_DIR}/files/plugins/autonomous-dev/config/global_settings_template.json"
    local script_path="${STAGING_DIR}/files/plugins/autonomous-dev/scripts/configure_global_settings.py"
    local home_path="${HOME}/.claude"

    # Check if template was downloaded
    if [[ ! -f "$template_path" ]]; then
        log_warning "Template not found - skipping settings configuration"
        return 1
    fi

    # Check if script was downloaded
    if [[ ! -f "$script_path" ]]; then
        log_warning "Configure script not found - skipping settings configuration"
        return 1
    fi

    # Run configuration script (always exits 0, check JSON output)
    local result
    result=$(python3 "$script_path" --template "$template_path" --home "$home_path" 2>&1)

    # Parse result JSON
    local success
    success=$(echo "$result" | python3 -c "import json, sys; data=json.load(sys.stdin); print('true' if data.get('success') else 'false')" 2>/dev/null || echo "false")

    if [[ "$success" == "true" ]]; then
        local created
        created=$(echo "$result" | python3 -c "import json, sys; data=json.load(sys.stdin); print('true' if data.get('created') else 'false')" 2>/dev/null || echo "false")

        if [[ "$created" == "true" ]]; then
            log_success "Created ~/.claude/settings.json from template"
        else
            log_success "Updated ~/.claude/settings.json (preserved customizations)"
        fi
        return 0
    else
        local error_msg
        error_msg=$(echo "$result" | python3 -c "import json, sys; data=json.load(sys.stdin); print(data.get('message', 'Unknown error'))" 2>/dev/null || echo "Configuration failed")
        log_warning "Settings configuration: ${error_msg}"
        return 1
    fi
}

# Recovery mode: strip the entire hooks block from ~/.claude/settings.json
# Issue #949: When global hooks misbehave (missing scripts, infinite loops,
# rule errors), every Claude Code prompt is blocked. This function calls
# reset_global_hooks.py to remove the hooks block atomically while
# preserving permissions, mcpServers, env, model, etc. Backs up to
# settings.json.preglobal-hooks-strip. Standalone mode — runs only when
# --reset-hooks is passed; never as part of a normal install.
reset_global_hooks() {
    log_step "Resetting global hooks (Issue #949)..."

    # Resolve script path: developer/local-repo flow first, then staged flow.
    local script_path=""
    local local_path
    local_path="$(dirname "$0")/plugins/autonomous-dev/scripts/reset_global_hooks.py"
    if [[ -f "$local_path" ]]; then
        script_path="$local_path"
    elif [[ -f "${STAGING_DIR}/files/plugins/autonomous-dev/scripts/reset_global_hooks.py" ]]; then
        script_path="${STAGING_DIR}/files/plugins/autonomous-dev/scripts/reset_global_hooks.py"
    fi

    if [[ -z "$script_path" ]]; then
        log_error "reset_global_hooks.py helper not found"
        log_info "Manual recovery: see plugins/autonomous-dev/docs/TROUBLESHOOTING.md"
        log_info "  -> Recovery from Broken Hooks (python3 -c '...' one-liner)"
        return 1
    fi

    local target="${HOME}/.claude/settings.json"

    local result
    result=$(python3 "$script_path" --target "$target" 2>&1 \
        || echo '{"success":false,"stripped":false,"error":"helper_failed","message":"helper failed"}')

    local success
    success=$(echo "$result" | python3 -c \
        "import json,sys; d=json.load(sys.stdin); print('true' if d.get('success') else 'false')" \
        2>/dev/null || echo "false")

    local stripped
    stripped=$(echo "$result" | python3 -c \
        "import json,sys; d=json.load(sys.stdin); print('true' if d.get('stripped') else 'false')" \
        2>/dev/null || echo "false")

    local message
    message=$(echo "$result" | python3 -c \
        "import json,sys; d=json.load(sys.stdin); print(d.get('message','') or '')" \
        2>/dev/null || echo "")

    local backup_path
    backup_path=$(echo "$result" | python3 -c \
        "import json,sys; d=json.load(sys.stdin); print(d.get('backup_path','') or '')" \
        2>/dev/null || echo "")

    if [[ "$success" != "true" ]]; then
        log_error "Reset hooks failed: ${message:-unknown error}"
        log_info "See plugins/autonomous-dev/docs/TROUBLESHOOTING.md (Recovery from Broken Hooks)"
        return 1
    fi

    if [[ "$stripped" == "true" ]]; then
        log_success "Stripped hooks block from ${target}"
        if [[ -n "$backup_path" ]]; then
            log_info "Backup saved: ${backup_path}"
        fi
    else
        log_info "${message:-no hooks block to remove}"
    fi

    log_info "Restart Claude Code (Cmd+Q / Ctrl+Q) to pick up the change."
    return 0
}

# ─────────────────────────────────────────────────────────────────────────────
# UNINSTALL HELPERS (Issue #951)
# ─────────────────────────────────────────────────────────────────────────────
#
# These functions implement `install.sh --uninstall`, a shell-only uninstall
# path that coexists with `/sync --uninstall` (the Python orchestrator). The
# shell path serves the "broken state, no Claude CLI" use case — when
# uninstall_orchestrator.py is itself broken or the user cannot launch
# Claude Code at all.
#
# Design constraints (see Issue #951 plan):
#   - Manifest-driven. Files to remove come from install_manifest.json so
#     user-added files (e.g. ~/.claude/hooks/extensions/*) are preserved.
#   - Backup before mutate. Every removal/strip is preceded by a copy into
#     ~/.claude/backups/uninstall-YYYYMMDD-HHMMSS/<mirror-tree>/.
#   - Preserves PROJECT.md, CLAUDE.md, .env, logs/, archive/, memory/,
#     hooks/extensions/.
#   - Idempotent: re-running on a clean state is a no-op (exit 0, no error,
#     no new backup dir).
#   - --dry-run short-circuits ALL mutations.

# Module-scope state for the uninstall flow.
UNINSTALL_BACKUP_ROOT=""

# Compute manifest path used by uninstall. Order:
#   1. local repo (developer flow: install.sh next to plugins/...)
#   2. staged    (post-bootstrap: ~/.autonomous-dev-staging/files/...)
#   3. installed (post-install:   ~/.claude/config/install_manifest.json)
_uninstall_find_manifest() {
    local local_path
    local_path="$(dirname "$0")/${MANIFEST_FILE}"
    if [[ -f "$local_path" ]]; then
        echo "$local_path"
        return 0
    fi
    local staged_path="${STAGING_DIR}/files/${MANIFEST_FILE}"
    if [[ -f "$staged_path" ]]; then
        echo "$staged_path"
        return 0
    fi
    local installed_path="${HOME}/.claude/config/install_manifest.json"
    if [[ -f "$installed_path" ]]; then
        echo "$installed_path"
        return 0
    fi
    return 1
}

# Find a staged or local script (uninstall helpers).
_uninstall_find_script() {
    local script_name="$1"
    local local_path="$(dirname "$0")/plugins/autonomous-dev/scripts/${script_name}"
    if [[ -f "$local_path" ]]; then
        echo "$local_path"
        return 0
    fi
    local staged_path="${STAGING_DIR}/files/plugins/autonomous-dev/scripts/${script_name}"
    if [[ -f "$staged_path" ]]; then
        echo "$staged_path"
        return 0
    fi
    local installed_path="${HOME}/.claude/scripts/${script_name}"
    if [[ -f "$installed_path" ]]; then
        echo "$installed_path"
        return 0
    fi
    return 1
}

# Create a unique backup root for this uninstall run.
# Side effect: sets UNINSTALL_BACKUP_ROOT.
# DRY_RUN: no directory creation; UNINSTALL_BACKUP_ROOT is set for display only.
uninstall_create_backup_root() {
    local stamp
    stamp="$(date +%Y%m%d-%H%M%S)"
    UNINSTALL_BACKUP_ROOT="${HOME}/.claude/backups/uninstall-${stamp}"
    if [[ "$DRY_RUN" == "true" ]]; then
        log_info "[DRY RUN] Would create backup root: ${UNINSTALL_BACKUP_ROOT}"
        return 0
    fi
    if ! mkdir -p "$UNINSTALL_BACKUP_ROOT"; then
        log_error "Cannot create backup root: ${UNINSTALL_BACKUP_ROOT}"
        return 1
    fi
    log_info "Backup root: ${UNINSTALL_BACKUP_ROOT}"
    return 0
}

# Use Python (already a dep) to extract the list of manifest-owned files
# under a given top-level component key (e.g. "hooks", "lib", "commands",
# "agents", "scripts", "skills"). Output: one basename per line.
_uninstall_list_manifest_basenames() {
    local manifest="$1"
    local component="$2"
    python3 - "$manifest" "$component" <<'PYEOF'
import json
import os
import sys

manifest_path = sys.argv[1]
component = sys.argv[2]

try:
    with open(manifest_path, encoding="utf-8") as f:
        manifest = json.load(f)
except OSError:
    sys.exit(0)
except json.JSONDecodeError:
    sys.exit(0)

comp = manifest.get("components", {}).get(component, {})
files = comp.get("files", [])
if not isinstance(files, list):
    sys.exit(0)

for entry in files:
    if isinstance(entry, str):
        print(os.path.basename(entry))
PYEOF
}

# Remove manifest-owned files from a target directory, preserving any
# files NOT in the manifest (user-added). For each removal, copy the file
# to UNINSTALL_BACKUP_ROOT/<component>/ first.
#
# Arguments:
#   $1: component key in install_manifest.json (e.g. "hooks", "lib").
#   $2: target directory under HOME (e.g. ~/.claude/hooks).
#
# Globals: DRY_RUN, UNINSTALL_BACKUP_ROOT.
#
# Side effect when not DRY_RUN: backs up + deletes each manifest-owned
# file. Empty target directory is left alone (don't rmdir; the user may
# have an extensions/ subdir or just want the directory there).
uninstall_remove_global_files() {
    local component="$1"
    local target_dir="$2"
    local manifest
    manifest="$(_uninstall_find_manifest)" || {
        log_warning "No manifest found; cannot perform manifest-driven cleanup of ${target_dir}"
        return 1
    }

    if [[ ! -d "$target_dir" ]]; then
        log_info "${target_dir} does not exist - nothing to remove for ${component}"
        return 0
    fi

    local backup_subdir="${UNINSTALL_BACKUP_ROOT}/${component}"
    local removed=0
    local would_remove=0
    local basenames
    basenames="$(_uninstall_list_manifest_basenames "$manifest" "$component")"

    if [[ -z "$basenames" ]]; then
        log_info "Manifest has no ${component} files - skipping"
        return 0
    fi

    if [[ "$DRY_RUN" != "true" ]]; then
        mkdir -p "$backup_subdir"
    fi

    local name
    while IFS= read -r name; do
        [[ -z "$name" ]] && continue
        local file_path="${target_dir}/${name}"
        if [[ -e "$file_path" || -L "$file_path" ]]; then
            if [[ "$DRY_RUN" == "true" ]]; then
                ((would_remove++))
                if $VERBOSE; then
                    log_info "[DRY RUN]   Would remove: ${file_path}"
                fi
            else
                # Backup, then remove. Use -P to NOT follow symlinks.
                if cp -P "$file_path" "${backup_subdir}/${name}" 2>/dev/null \
                   && rm -f "$file_path"; then
                    ((removed++))
                    if $VERBOSE; then
                        log_success "  Removed: ${file_path}"
                    fi
                else
                    log_warning "  Failed to remove: ${file_path}"
                fi
            fi
        fi
    done <<< "$basenames"

    if [[ "$DRY_RUN" == "true" ]]; then
        log_info "[DRY RUN] ${component}: would remove ${would_remove} file(s) from ${target_dir}"
    else
        if [[ "$removed" -gt 0 ]]; then
            log_success "${component}: removed ${removed} file(s) from ${target_dir}"
        else
            log_info "${component}: nothing to remove in ${target_dir}"
        fi
    fi
    return 0
}

# Remove autonomous-dev core commands from ~/.claude/commands/.
# This is the small set installed by install_global_commands(): sync,
# setup, health-check. Plus any additional manifest commands that ended
# up there.
uninstall_remove_global_commands() {
    log_step "Cleaning ~/.claude/commands/..."
    uninstall_remove_global_files "commands" "${HOME}/.claude/commands"
}

# Strip autonomous-dev hooks from ~/.claude/settings.json.
# Delegates to the existing reset_global_hooks.py helper, which already
# implements the "strip hooks block, preserve everything else" contract
# (Issue #949). We use it here because the entire ~/.claude/settings.json
# hooks block IS autonomous-dev when installed via install.sh.
uninstall_strip_global_settings_hooks() {
    log_step "Stripping hooks from ~/.claude/settings.json..."
    local target="${HOME}/.claude/settings.json"

    if [[ ! -f "$target" ]]; then
        log_info "${target} does not exist - nothing to strip"
        return 0
    fi

    if [[ "$DRY_RUN" == "true" ]]; then
        # Use reset_global_hooks.py only to detect IF there's a hooks
        # block; we don't write anything in dry-run.
        local hooks_present
        hooks_present=$(python3 -c "
import json, sys
try:
    with open('$target', encoding='utf-8') as f:
        d = json.load(f)
    print('true' if 'hooks' in d else 'false')
except Exception:
    print('false')
" 2>/dev/null || echo "false")
        if [[ "$hooks_present" == "true" ]]; then
            log_info "[DRY RUN] Would strip hooks block from ${target}"
            log_info "[DRY RUN] Would back up to ${target}.preglobal-hooks-strip"
        else
            log_info "[DRY RUN] No hooks block to strip in ${target}"
        fi
        return 0
    fi

    local script_path
    script_path="$(_uninstall_find_script reset_global_hooks.py)" || {
        log_warning "reset_global_hooks.py not found - skipping global settings strip"
        return 0
    }

    local result
    result=$(python3 "$script_path" --target "$target" 2>&1 \
        || echo '{"success":false,"stripped":false,"error":"helper_failed"}')

    local stripped
    stripped=$(echo "$result" | python3 -c \
        "import json,sys; d=json.load(sys.stdin); print('true' if d.get('stripped') else 'false')" \
        2>/dev/null || echo "false")

    if [[ "$stripped" == "true" ]]; then
        log_success "Stripped hooks block from ${target}"
        # Also copy the .preglobal-hooks-strip backup into our uninstall
        # backup tree so it's all in one place.
        local pgh_backup="${target}.preglobal-hooks-strip"
        if [[ -f "$pgh_backup" ]]; then
            mkdir -p "${UNINSTALL_BACKUP_ROOT}/global-settings" 2>/dev/null || true
            cp -P "$pgh_backup" "${UNINSTALL_BACKUP_ROOT}/global-settings/" 2>/dev/null || true
        fi
    else
        log_info "No autonomous-dev hooks in ${target}"
    fi
    return 0
}

# Walk a list of repo paths and strip autonomous-dev hooks from each
# repo's .claude/settings.json. Rejects paths that don't exist or don't
# contain a .claude/ subdirectory.
#
# Globals: UNINSTALL_REPOS (comma- or space-separated), DRY_RUN,
# UNINSTALL_BACKUP_ROOT.
uninstall_walk_repos() {
    if [[ -z "$UNINSTALL_REPOS" ]]; then
        return 0
    fi

    log_step "Stripping autonomous-dev hooks from per-repo settings.json..."

    local script_path
    script_path="$(_uninstall_find_script uninstall_strip_repo_hooks.py)" || {
        log_warning "uninstall_strip_repo_hooks.py not found - skipping per-repo strip"
        return 0
    }

    # Accept comma OR whitespace separation.
    local normalized="${UNINSTALL_REPOS//,/ }"

    local repo
    for repo in $normalized; do
        [[ -z "$repo" ]] && continue

        # Validate: must exist as a directory.
        if [[ ! -d "$repo" ]]; then
            log_error "  --repos: path does not exist: ${repo}"
            continue
        fi
        # Validate: must contain a .claude/ subdirectory.
        if [[ ! -d "${repo}/.claude" ]]; then
            log_error "  --repos: missing .claude/ in: ${repo}"
            continue
        fi

        local repo_settings="${repo}/.claude/settings.json"
        if [[ ! -f "$repo_settings" ]]; then
            log_info "  No settings.json in ${repo}/.claude/"
            continue
        fi

        local backup_root_for_repo="${UNINSTALL_BACKUP_ROOT}/repo-$(basename "$repo")"
        local dry_flag=""
        if [[ "$DRY_RUN" == "true" ]]; then
            dry_flag="--dry-run"
        fi

        local result
        result=$(python3 "$script_path" \
            --target "$repo_settings" \
            --backup-root "$backup_root_for_repo" \
            $dry_flag 2>&1 \
            || echo '{"success":false,"stripped":false,"error":"helper_failed"}')

        local success stripped would_strip
        success=$(echo "$result" | python3 -c \
            "import json,sys; d=json.load(sys.stdin); print('true' if d.get('success') else 'false')" \
            2>/dev/null || echo "false")
        stripped=$(echo "$result" | python3 -c \
            "import json,sys; d=json.load(sys.stdin); print('true' if d.get('stripped') else 'false')" \
            2>/dev/null || echo "false")
        would_strip=$(echo "$result" | python3 -c \
            "import json,sys; d=json.load(sys.stdin); print('true' if d.get('would_strip') else 'false')" \
            2>/dev/null || echo "false")

        if [[ "$success" != "true" ]]; then
            log_warning "  Failed to process: ${repo_settings}"
        elif [[ "$DRY_RUN" == "true" ]]; then
            if [[ "$would_strip" == "true" ]]; then
                log_info "  [DRY RUN] Would strip autonomous-dev hooks from: ${repo_settings}"
            else
                log_info "  [DRY RUN] Nothing to strip in: ${repo_settings}"
            fi
        else
            if [[ "$stripped" == "true" ]]; then
                log_success "  Stripped autonomous-dev hooks: ${repo_settings}"
            else
                log_info "  No autonomous-dev hooks in: ${repo_settings}"
            fi
        fi
    done
    return 0
}

# Unregister autonomous-dev from Claude Code's plugin and marketplace
# registry files (if present).
uninstall_unregister_plugin() {
    log_step "Unregistering autonomous-dev plugin..."

    local plugins_file="${HOME}/.claude/plugins/installed_plugins.json"
    local marketplaces_file="${HOME}/.claude/plugins/marketplaces.json"

    if [[ ! -f "$plugins_file" && ! -f "$marketplaces_file" ]]; then
        log_info "No plugin registration files found - nothing to unregister"
        return 0
    fi

    local script_path
    script_path="$(_uninstall_find_script uninstall_unregister_plugin.py)" || {
        log_warning "uninstall_unregister_plugin.py not found - skipping unregister"
        return 0
    }

    local dry_flag=""
    if [[ "$DRY_RUN" == "true" ]]; then
        dry_flag="--dry-run"
    fi

    local result
    result=$(python3 "$script_path" \
        --plugins-file "$plugins_file" \
        --marketplaces-file "$marketplaces_file" \
        --backup-root "${UNINSTALL_BACKUP_ROOT}/registry" \
        $dry_flag 2>&1 \
        || echo '{"success":false,"stripped":false,"error":"helper_failed"}')

    local stripped would_strip
    stripped=$(echo "$result" | python3 -c \
        "import json,sys; d=json.load(sys.stdin); print('true' if d.get('stripped') else 'false')" \
        2>/dev/null || echo "false")
    would_strip=$(echo "$result" | python3 -c \
        "import json,sys; d=json.load(sys.stdin); print('true' if d.get('would_strip') else 'false')" \
        2>/dev/null || echo "false")

    if [[ "$DRY_RUN" == "true" ]]; then
        if [[ "$would_strip" == "true" ]]; then
            log_info "[DRY RUN] Would unregister autonomous-dev from plugin/marketplace registries"
        else
            log_info "[DRY RUN] No autonomous-dev entries found in plugin/marketplace registries"
        fi
    else
        if [[ "$stripped" == "true" ]]; then
            log_success "Unregistered autonomous-dev from plugin/marketplace registries"
        else
            log_info "No autonomous-dev entries in plugin/marketplace registries"
        fi
    fi
    return 0
}

# Print the uninstall plan (used in --dry-run header and at start of
# real run).
uninstall_print_plan() {
    echo ""
    if [[ "$DRY_RUN" == "true" ]]; then
        log_info "═══════════════════════════════════════════════════════════════"
        log_info "  UNINSTALL --dry-run  (no files will be modified)"
        log_info "═══════════════════════════════════════════════════════════════"
    else
        log_info "═══════════════════════════════════════════════════════════════"
        log_info "  UNINSTALL  (autonomous-dev will be removed)"
        log_info "═══════════════════════════════════════════════════════════════"
    fi
    echo ""
    log_info "Plan:"
    log_info "  1. Create backup root: ${UNINSTALL_BACKUP_ROOT}"
    log_info "  2. Remove manifest-owned files from:"
    log_info "       ~/.claude/hooks/        (preserves extensions/)"
    log_info "       ~/.claude/lib/"
    log_info "       ~/.claude/commands/"
    log_info "       ~/.claude/agents/"
    log_info "       ~/.claude/scripts/"
    log_info "  3. Strip autonomous-dev hooks from ~/.claude/settings.json"
    log_info "  4. Unregister from ~/.claude/plugins/installed_plugins.json"
    if [[ -n "$UNINSTALL_REPOS" ]]; then
        log_info "  5. Strip per-repo hooks from: ${UNINSTALL_REPOS}"
    fi
    log_info ""
    log_info "PRESERVED (never touched):"
    log_info "  ~/.claude/PROJECT.md, CLAUDE.md, .env"
    log_info "  ~/.claude/{logs,archive,memory}/"
    log_info "  ~/.claude/hooks/extensions/"
    echo ""
}

# Top-level entry point for --uninstall mode. Orchestrates all steps,
# always returns 0 to the shell (errors are surfaced via log_error).
uninstall_main() {
    if [[ "$DRY_RUN" == "true" ]]; then
        echo ""
        echo "╔══════════════════════════════════════════════════════════════╗"
        echo "║       autonomous-dev Uninstall (--dry-run)                  ║"
        echo "╚══════════════════════════════════════════════════════════════╝"
    else
        echo ""
        echo "╔══════════════════════════════════════════════════════════════╗"
        echo "║       autonomous-dev Uninstall                              ║"
        echo "╚══════════════════════════════════════════════════════════════╝"
    fi

    # Check for completely empty install (idempotent fast path).
    local has_anything=false
    if [[ -d "${HOME}/.claude/hooks" || -d "${HOME}/.claude/lib" \
        || -d "${HOME}/.claude/commands" || -d "${HOME}/.claude/agents" \
        || -d "${HOME}/.claude/scripts" \
        || -f "${HOME}/.claude/settings.json" ]]; then
        has_anything=true
    fi
    if [[ "$has_anything" == "false" && -z "$UNINSTALL_REPOS" ]]; then
        echo ""
        log_info "Nothing to remove (no ~/.claude/ install artifacts found)"
        return 0
    fi

    if ! uninstall_create_backup_root; then
        return 1
    fi

    uninstall_print_plan

    # Manifest-owned file removal.
    uninstall_remove_global_files "hooks"    "${HOME}/.claude/hooks"
    uninstall_remove_global_files "lib"      "${HOME}/.claude/lib"
    uninstall_remove_global_commands
    uninstall_remove_global_files "agents"   "${HOME}/.claude/agents"
    uninstall_remove_global_files "scripts"  "${HOME}/.claude/scripts"

    # Global settings hooks.
    uninstall_strip_global_settings_hooks

    # Plugin/marketplace registry.
    uninstall_unregister_plugin

    # Per-repo hooks (optional).
    uninstall_walk_repos

    echo ""
    if [[ "$DRY_RUN" == "true" ]]; then
        log_info "═══════════════════════════════════════════════════════════════"
        log_info "  --dry-run complete. No files were modified."
        log_info "  Re-run without --dry-run to apply the plan above."
        log_info "═══════════════════════════════════════════════════════════════"
    else
        log_success "═══════════════════════════════════════════════════════════════"
        log_success "  Uninstall complete."
        log_success "  Backup: ${UNINSTALL_BACKUP_ROOT}"
        log_success "═══════════════════════════════════════════════════════════════"
        log_info ""
        log_info "PRESERVED:"
        log_info "  ~/.claude/PROJECT.md, CLAUDE.md, .env"
        log_info "  ~/.claude/{logs,archive,memory}/"
        log_info "  ~/.claude/hooks/extensions/"
        log_info ""
        log_info "Restart Claude Code to fully detach autonomous-dev."
    fi
    return 0
}

# Migrate per-repo settings.json: strip duplicated global hooks (Issue #944)
# Existing user installs may have ~/.claude/settings.json (or per-repo
# .claude/settings.json) with hook entries that are also registered in the
# global settings file. This function calls strip_duplicate_hooks.py to
# remove the duplicates atomically. Non-blocking — install continues on
# any failure.
strip_duplicate_global_hooks() {
    log_step "Migrating duplicate global hooks (Issue #944)..."

    local script_path="${STAGING_DIR}/files/plugins/autonomous-dev/scripts/strip_duplicate_hooks.py"
    local home_settings="${HOME}/.claude/settings.json"
    local repo_settings=".claude/settings.json"

    # Skip if migration script not staged
    if [[ ! -f "$script_path" ]]; then
        log_info "strip_duplicate_hooks.py not staged - skipping migration"
        return 0
    fi

    local total_removed=0
    local target
    for target in "$home_settings" "$repo_settings"; do
        if [[ ! -f "$target" ]]; then
            continue
        fi

        # Run migration (always exits 0, parse JSON for status)
        local result
        result=$(python3 "$script_path" --target "$target" 2>/dev/null \
            || echo '{"success":false,"removed_count":0}')

        local removed
        removed=$(echo "$result" | python3 -c \
            "import json,sys; d=json.load(sys.stdin); print(d.get('removed_count',0))" \
            2>/dev/null || echo "0")

        if [[ "$removed" != "0" ]]; then
            log_success "Stripped ${removed} duplicate global hook(s) from ${target}"
            total_removed=$((total_removed + removed))
        fi
    done

    if [[ "$total_removed" == "0" ]]; then
        log_info "No duplicate global hooks found in settings.json files"
    fi

    return 0
}

# Migrate one MCP server from global ~/.claude/settings.json mcpServers
# to <repo>/.mcp.json (Issue #948). Standalone mode — does NOT run during
# the normal install flow. Triggered by:
#   install.sh --migrate-mcp-to-repo <repo-path> --server <name>
#
# Both flags are required. The helper script
# (plugins/autonomous-dev/scripts/migrate_mcp_to_repo.py) is read from the
# staging directory populated by download_files. Always returns 0 unless
# the args are missing or the helper script is absent — mirrors the
# JSON-return contract of strip_duplicate_global_hooks.
migrate_mcp_to_repo() {
    if [[ -z "$MIGRATE_MCP_REPO" ]] || [[ -z "$MIGRATE_MCP_SERVER" ]]; then
        log_error "--migrate-mcp-to-repo requires --server <name>"
        return 1
    fi

    local script_path="${STAGING_DIR}/files/plugins/autonomous-dev/scripts/migrate_mcp_to_repo.py"

    # If the staged copy is missing, try the local repo copy (developer flow).
    if [[ ! -f "$script_path" ]]; then
        local local_path
        local_path="$(dirname "$0")/plugins/autonomous-dev/scripts/migrate_mcp_to_repo.py"
        if [[ -f "$local_path" ]]; then
            script_path="$local_path"
        else
            log_error "migrate helper not found at $script_path"
            return 1
        fi
    fi

    log_step "Migrating MCP server '${MIGRATE_MCP_SERVER}' to ${MIGRATE_MCP_REPO}/.mcp.json (Issue #948)..."

    local result
    result=$(python3 "$script_path" \
        --server "$MIGRATE_MCP_SERVER" \
        --repo "$MIGRATE_MCP_REPO" 2>&1 \
        || echo '{"success":false,"error":"helper_failed"}')

    local success
    success=$(echo "$result" | python3 -c \
        "import json,sys; d=json.load(sys.stdin); print(d.get('success', False))" \
        2>/dev/null || echo "False")

    local secrets
    secrets=$(echo "$result" | python3 -c \
        "import json,sys; d=json.load(sys.stdin); print(d.get('secrets_detected', False))" \
        2>/dev/null || echo "False")

    local gitignored
    gitignored=$(echo "$result" | python3 -c \
        "import json,sys; d=json.load(sys.stdin); print(d.get('gitignored', False))" \
        2>/dev/null || echo "False")

    if [[ "$success" == "True" ]]; then
        log_success "Migrated MCP server '${MIGRATE_MCP_SERVER}' to ${MIGRATE_MCP_REPO}/.mcp.json"
        if [[ "$secrets" == "True" ]]; then
            log_warning "Inline secrets detected. .gitignore updated: ${gitignored}"
        fi
        return 0
    else
        log_error "MCP migration failed: ${result}"
        return 1
    fi
}

# Migrate hooks from array format to object format (Claude Code 2.0)
# Issue #156: Users with old settings.json need hooks migrated
migrate_hooks_format() {
    log_step "Checking hooks format..."

    # Issue #995 defense-in-depth: short-circuit when --global-settings is
    # not set. Even if a future code path calls this function without
    # checking $GLOBAL_SETTINGS at the call site, we must NEVER silently
    # mutate ~/.claude/settings.json's hooks block when the user opted out
    # of global hook registration.
    if ! $GLOBAL_SETTINGS; then
        log_info "Skipped hooks format migration (--global-settings not set, Issue #995)"
        return 0
    fi

    local lib_path="${STAGING_DIR}/files/plugins/autonomous-dev/lib"
    local settings_path="${HOME}/.claude/settings.json"

    # Check if settings.json exists
    if [[ ! -f "$settings_path" ]]; then
        log_info "No settings.json found - skipping hooks migration"
        return 0
    fi

    # Check if hook_activator.py was downloaded
    if [[ ! -f "${lib_path}/hook_activator.py" ]]; then
        log_warning "hook_activator.py not found - skipping hooks migration"
        return 1
    fi

    # Run migration (Python one-liner to call the function)
    local result
    result=$(PYTHONPATH="${lib_path}:${lib_path}/.." python3 -c "
import sys
sys.path.insert(0, '${STAGING_DIR}/files/plugins/autonomous-dev/lib')
sys.path.insert(0, '${STAGING_DIR}/files/plugins')
from pathlib import Path
try:
    from hook_activator import migrate_hooks_to_object_format
    result = migrate_hooks_to_object_format(Path('${settings_path}'))
    import json
    print(json.dumps(result, default=str))
except Exception as e:
    import json
    print(json.dumps({'migrated': False, 'error': str(e)}))
" 2>&1)

    # Parse result
    local migrated
    migrated=$(echo "$result" | python3 -c "import json, sys; data=json.load(sys.stdin); print('true' if data.get('migrated') else 'false')" 2>/dev/null || echo "false")

    if [[ "$migrated" == "true" ]]; then
        log_success "Migrated hooks to Claude Code 2.0 format"
        return 0
    else
        local format_type
        format_type=$(echo "$result" | python3 -c "import json, sys; data=json.load(sys.stdin); print(data.get('format', 'unknown'))" 2>/dev/null || echo "unknown")

        if [[ "$format_type" == "object" ]]; then
            log_info "Hooks already in correct format"
            return 0
        elif [[ "$format_type" == "missing" ]]; then
            log_info "No hooks to migrate"
            return 0
        else
            local error_msg
            error_msg=$(echo "$result" | python3 -c "import json, sys; data=json.load(sys.stdin); print(data.get('error', 'Unknown'))" 2>/dev/null || echo "Unknown")
            log_warning "Hooks migration: ${error_msg}"
            return 1
        fi
    fi
}

# Clean orphan files from a directory based on manifest
# Usage: clean_orphan_files <target_dir> <component_name> <file_extension>
clean_orphan_files() {
    local target_dir="$1"
    local component_name="$2"
    local file_ext="$3"
    local manifest_path="${STAGING_DIR}/manifest.json"
    local cleaned=0

    # Skip if target directory doesn't exist
    if [[ ! -d "$target_dir" ]]; then
        return 0
    fi

    # Get expected files from manifest
    local expected_files
    expected_files=$(python3 -c "
import json
import sys
from pathlib import Path

with open('${manifest_path}') as f:
    manifest = json.load(f)

component = manifest.get('components', {}).get('${component_name}', {})
for file_path in component.get('files', []):
    print(Path(file_path).name)
" 2>/dev/null)

    if [[ -z "$expected_files" ]]; then
        return 0
    fi

    # Find and remove orphan files (files in target but not in manifest)
    while IFS= read -r actual_file; do
        if [[ -z "$actual_file" ]]; then
            continue
        fi

        local file_name
        file_name=$(basename "$actual_file")

        # Skip __init__.py and __pycache__
        if [[ "$file_name" == "__init__.py" ]] || [[ "$file_name" == "__pycache__" ]]; then
            continue
        fi

        # Check if file is in expected list
        if ! echo "$expected_files" | grep -qx "$file_name"; then
            # File is orphan - remove it
            if rm "$actual_file" 2>/dev/null; then
                ((cleaned++))
                if $VERBOSE; then
                    log_warning "  Removed orphan: $file_name"
                fi
            fi
        fi
    done < <(find "$target_dir" -maxdepth 1 -type f -name "*${file_ext}" 2>/dev/null)

    if [[ $cleaned -gt 0 ]]; then
        log_info "Cleaned ${cleaned} orphan ${component_name} file(s)"
    fi

    return 0
}

# Install hook files to ~/.claude/hooks/
install_hook_files() {
    log_step "Installing hook files to ${INSTALL_DIR}/hooks/..."

    # Clean orphan hooks first (TRUE SYNC - remove files not in manifest)
    : "${INSTALL_DIR:=${HOME}/.claude}"
    clean_orphan_files "${INSTALL_DIR}/hooks" "hooks" ".py"

    local hook_source_dir="${STAGING_DIR}/files/plugins/autonomous-dev/hooks"
    : "${INSTALL_DIR:=${HOME}/.claude}"
    local hook_target_dir="${INSTALL_DIR}/hooks"
    local installed=0
    local failed=0

    # Check if hook source directory exists
    if [[ ! -d "$hook_source_dir" ]]; then
        log_warning "Hooks directory not found in staging - hook files won't be installed"
        return 1
    fi

    # Create target directory if it doesn't exist
    if ! mkdir -p "$hook_target_dir" 2>/dev/null; then
        log_error "Failed to create ~/.claude/hooks/ directory (permission denied?)"
        return 1
    fi

    # Get list of .py and .sh files from hooks directory
    local hook_files
    hook_files=$(find "$hook_source_dir" -maxdepth 1 -type f \( -name "*.py" -o -name "*.sh" \))

    if [[ -z "$hook_files" ]]; then
        log_info "No hook files found to install"
        return 0
    fi

    # Count total files
    local total_files
    total_files=$(echo "$hook_files" | wc -l | tr -d ' ')
    log_info "Found ${total_files} hook files to install"

    # Copy each hook file
    while IFS= read -r hook_file; do
        if [[ -z "$hook_file" ]]; then
            continue
        fi

        local file_name
        file_name=$(basename "$hook_file")

        # Security: Check if file is a symlink
        if [[ -L "$hook_file" ]]; then
            log_warning "  Skipping symlink: $file_name"
            ((failed++))
            continue
        fi

        # Copy file to target directory (use -P to not follow symlinks)
        if cp -P "$hook_file" "$hook_target_dir/$file_name"; then
            ((installed++))
            if $VERBOSE; then
                log_success "  Installed: $file_name"
            fi
        else
            ((failed++))
            log_warning "  Failed: $file_name"
        fi
    done <<< "$hook_files"

    # Report results
    if [[ $failed -gt 0 ]]; then
        log_warning "Installed ${installed}/${total_files} hook files (${failed} failed)"
        return 1
    fi

    # Ensure hooks are executable
    find "$hook_target_dir" -name "*.py" -exec chmod 755 {} \; 2>/dev/null || true
    find "$hook_target_dir" -name "*.sh" -exec chmod 755 {} \; 2>/dev/null || true

    # Create extensions directory (user-owned, survives updates)
    mkdir -p "${HOME}/.claude/hooks/extensions" 2>/dev/null || true

    log_success "Installed ${installed} hook file(s) to ~/.claude/hooks/"
    return 0
}

# Install core commands globally to ~/.claude/commands/ (sync.md, setup.md)
# These commands must be available in ALL repos for bootstrapping
install_global_commands() {
    log_step "Installing core commands to ${INSTALL_DIR}/commands/..."

    local command_source_dir="${STAGING_DIR}/files/plugins/autonomous-dev/commands"
    : "${INSTALL_DIR:=${HOME}/.claude}"
    local command_target_dir="${INSTALL_DIR}/commands"
    local installed=0
    local failed=0

    # Core commands that must be available globally for bootstrapping
    local core_commands=("sync.md" "setup.md" "health-check.md")

    # Check if command source directory exists
    if [[ ! -d "$command_source_dir" ]]; then
        log_warning "Commands directory not found in staging - global commands won't be installed"
        return 1
    fi

    # Create target directory if it doesn't exist
    if ! mkdir -p "$command_target_dir" 2>/dev/null; then
        log_error "Failed to create ~/.claude/commands/ directory (permission denied?)"
        return 1
    fi

    # Install each core command
    for cmd in "${core_commands[@]}"; do
        local source_file="$command_source_dir/$cmd"
        local target_file="$command_target_dir/$cmd"

        if [[ ! -f "$source_file" ]]; then
            log_warning "  Not found in staging: $cmd"
            ((failed++))
            continue
        fi

        # Security: Check if file is a symlink
        if [[ -L "$source_file" ]]; then
            log_warning "  Skipping symlink: $cmd"
            ((failed++))
            continue
        fi

        # Copy file to target directory
        if cp -P "$source_file" "$target_file"; then
            ((installed++))
            if $VERBOSE; then
                log_success "  Installed globally: $cmd"
            fi
        else
            ((failed++))
            log_warning "  Failed: $cmd"
        fi
    done

    # Report results
    if [[ $failed -gt 0 ]]; then
        log_warning "Installed ${installed}/${#core_commands[@]} core commands globally (${failed} failed)"
        return 1
    fi

    log_success "Installed ${installed} core command(s) to ~/.claude/commands/"
    return 0
}

# Install lib files to ~/.claude/lib/
install_lib_files() {
    log_step "Installing lib files to ${INSTALL_DIR}/lib/..."

    # Clean orphan libs first (TRUE SYNC - remove files not in manifest)
    : "${INSTALL_DIR:=${HOME}/.claude}"
    clean_orphan_files "${INSTALL_DIR}/lib" "lib" ".py"

    local lib_source_dir="${STAGING_DIR}/files/plugins/autonomous-dev/lib"
    : "${INSTALL_DIR:=${HOME}/.claude}"
    local lib_target_dir="${INSTALL_DIR}/lib"
    local installed=0
    local failed=0

    # Check if lib source directory exists
    if [[ ! -d "$lib_source_dir" ]]; then
        log_warning "Lib directory not found in staging - lib files won't be installed"
        return 1
    fi

    # Create target directory if it doesn't exist
    if ! mkdir -p "$lib_target_dir" 2>/dev/null; then
        log_error "Failed to create ~/.claude/lib/ directory (permission denied?)"
        return 1
    fi

    # Phase 1: Copy top-level .py files (exclude __init__.py)
    local lib_files
    lib_files=$(find "$lib_source_dir" -maxdepth 1 -type f -name "*.py" ! -name "__init__.py")

    local total_files=0
    if [[ -n "$lib_files" ]]; then
        total_files=$(echo "$lib_files" | wc -l | tr -d ' ')
    fi

    # Phase 2: Find package directories (directories containing __init__.py)
    local package_dirs
    package_dirs=$(find "$lib_source_dir" -maxdepth 1 -type d ! -path "$lib_source_dir" -exec test -f "{}/__init__.py" \; -print)

    local package_files=""
    if [[ -n "$package_dirs" ]]; then
        # For each package directory, find all .py files recursively
        while IFS= read -r pkg_dir; do
            if [[ -z "$pkg_dir" ]]; then
                continue
            fi
            local pkg_files
            pkg_files=$(find "$pkg_dir" -type f -name "*.py")
            if [[ -n "$pkg_files" ]]; then
                if [[ -z "$package_files" ]]; then
                    package_files="$pkg_files"
                else
                    package_files=$(printf "%s\n%s" "$package_files" "$pkg_files")
                fi
            fi
        done <<< "$package_dirs"
    fi

    # Count total files (single files + package files)
    if [[ -n "$package_files" ]]; then
        local package_count
        package_count=$(echo "$package_files" | wc -l | tr -d ' ')
        total_files=$((total_files + package_count))
    fi

    if [[ $total_files -eq 0 ]]; then
        log_info "No lib files found to install"
        return 0
    fi

    log_info "Found ${total_files} lib files to install"

    # Copy top-level .py files
    if [[ -n "$lib_files" ]]; then
        while IFS= read -r lib_file; do
            if [[ -z "$lib_file" ]]; then
                continue
            fi

            local file_name
            file_name=$(basename "$lib_file")

            # Security: Check if file is a symlink
            if [[ -L "$lib_file" ]]; then
                log_warning "  Skipping symlink: $file_name"
                ((failed++))
                continue
            fi

            # Copy file to target directory (use -P to not follow symlinks)
            if cp -P "$lib_file" "$lib_target_dir/$file_name"; then
                ((installed++))
                if $VERBOSE; then
                    log_success "  Installed: $file_name"
                fi
            else
                ((failed++))
                log_warning "  Failed: $file_name"
            fi
        done <<< "$lib_files"
    fi

    # Copy package directories with structure preservation
    if [[ -n "$package_files" ]]; then
        while IFS= read -r pkg_file; do
            if [[ -z "$pkg_file" ]]; then
                continue
            fi

            # Get relative path from lib_source_dir
            local relative_path="${pkg_file#$lib_source_dir/}"
            local target_file="$lib_target_dir/$relative_path"
            local target_dir
            target_dir=$(dirname "$target_file")

            # Security: Check if file is a symlink
            if [[ -L "$pkg_file" ]]; then
                log_warning "  Skipping symlink: $relative_path"
                ((failed++))
                continue
            fi

            # Create target subdirectory if needed
            if ! mkdir -p "$target_dir" 2>/dev/null; then
                log_warning "  Failed to create directory: $target_dir"
                ((failed++))
                continue
            fi

            # Copy file to target directory (use -P to not follow symlinks)
            if cp -P "$pkg_file" "$target_file"; then
                ((installed++))
                if $VERBOSE; then
                    log_success "  Installed: $relative_path"
                fi
            else
                ((failed++))
                log_warning "  Failed: $relative_path"
            fi
        done <<< "$package_files"
    fi

    # Report results
    if [[ $failed -gt 0 ]]; then
        log_warning "Installed ${installed}/${total_files} lib files (${failed} failed)"
        return 1
    fi

    log_success "Installed ${installed} lib file(s) to ~/.claude/lib/"
    return 0
}

# Install agent files to .claude/agents/
bootstrap_agents() {
    log_step "Installing agent files to .claude/agents/..."

    local agent_source_dir="${STAGING_DIR}/files/plugins/autonomous-dev/agents"
    local agent_target_dir=".claude/agents"
    local installed=0
    local failed=0

    # Check if agent source directory exists
    if [[ ! -d "$agent_source_dir" ]]; then
        log_warning "Agents directory not found in staging - agent files won't be installed"
        return 1
    fi

    # Create target directory if it doesn't exist
    if ! mkdir -p "$agent_target_dir" 2>/dev/null; then
        log_error "Failed to create .claude/agents/ directory (permission denied?)"
        return 1
    fi

    # Get list of .md files from agents directory
    local agent_files
    agent_files=$(find "$agent_source_dir" -maxdepth 1 -type f -name "*.md")

    if [[ -z "$agent_files" ]]; then
        log_info "No agent files found to install"
        return 0
    fi

    # Count total files
    local total_files
    total_files=$(echo "$agent_files" | wc -l | tr -d ' ')
    log_info "Found ${total_files} agent files to install"

    # Copy each agent file
    while IFS= read -r agent_file; do
        if [[ -z "$agent_file" ]]; then
            continue
        fi

        local file_name
        file_name=$(basename "$agent_file")

        # Security: Check if file is a symlink
        if [[ -L "$agent_file" ]]; then
            log_warning "  Skipping symlink: $file_name"
            ((failed++))
            continue
        fi

        # Copy file to target directory (use -P to not follow symlinks)
        if cp -P "$agent_file" "$agent_target_dir/$file_name"; then
            ((installed++))
            if $VERBOSE; then
                log_success "  Installed: $file_name"
            fi
        else
            ((failed++))
            log_warning "  Failed: $file_name"
        fi
    done <<< "$agent_files"

    # Report results
    if [[ $failed -gt 0 ]]; then
        log_warning "Installed ${installed}/${total_files} agent files (${failed} failed)"
        return 1
    fi

    log_success "Installed ${installed} agent file(s) to .claude/agents/"
    return 0
}

# Install command files to .claude/commands/ (excluding setup.md which is already bootstrapped)
bootstrap_commands() {
    log_step "Installing command files to .claude/commands/..."

    local command_source_dir="${STAGING_DIR}/files/plugins/autonomous-dev/commands"
    local command_target_dir=".claude/commands"
    local installed=0
    local failed=0

    # Check if command source directory exists
    if [[ ! -d "$command_source_dir" ]]; then
        log_warning "Commands directory not found in staging - command files won't be installed"
        return 1
    fi

    # Create target directory if it doesn't exist (should already exist from bootstrap_setup_command)
    if ! mkdir -p "$command_target_dir" 2>/dev/null; then
        log_error "Failed to create .claude/commands/ directory (permission denied?)"
        return 1
    fi

    # Get list of .md files from commands directory (exclude setup.md - already installed)
    local command_files
    command_files=$(find "$command_source_dir" -maxdepth 1 -type f -name "*.md" ! -name "setup.md")

    if [[ -z "$command_files" ]]; then
        log_info "No additional command files found to install"
        return 0
    fi

    # Count total files
    local total_files
    total_files=$(echo "$command_files" | wc -l | tr -d ' ')
    log_info "Found ${total_files} command files to install (setup.md already installed)"

    # Copy each command file
    while IFS= read -r command_file; do
        if [[ -z "$command_file" ]]; then
            continue
        fi

        local file_name
        file_name=$(basename "$command_file")

        # Security: Check if file is a symlink
        if [[ -L "$command_file" ]]; then
            log_warning "  Skipping symlink: $file_name"
            ((failed++))
            continue
        fi

        # Copy file to target directory (use -P to not follow symlinks)
        if cp -P "$command_file" "$command_target_dir/$file_name"; then
            ((installed++))
            if $VERBOSE; then
                log_success "  Installed: $file_name"
            fi
        else
            ((failed++))
            log_warning "  Failed: $file_name"
        fi
    done <<< "$command_files"

    # Report results
    if [[ $failed -gt 0 ]]; then
        log_warning "Installed ${installed}/${total_files} command files (${failed} failed)"
        return 1
    fi

    log_success "Installed ${installed} command file(s) to .claude/commands/"
    return 0
}

# Install script files to .claude/scripts/
bootstrap_scripts() {
    log_step "Installing script files to .claude/scripts/..."

    local script_source_dir="${STAGING_DIR}/files/plugins/autonomous-dev/scripts"
    local script_target_dir=".claude/scripts"
    local installed=0
    local failed=0

    # Check if script source directory exists
    if [[ ! -d "$script_source_dir" ]]; then
        log_warning "Scripts directory not found in staging - script files won't be installed"
        return 1
    fi

    # Create target directory if it doesn't exist
    if ! mkdir -p "$script_target_dir" 2>/dev/null; then
        log_error "Failed to create .claude/scripts/ directory (permission denied?)"
        return 1
    fi

    # Get list of .py files from scripts directory
    local script_files
    script_files=$(find "$script_source_dir" -maxdepth 1 -type f -name "*.py")

    if [[ -z "$script_files" ]]; then
        log_info "No script files found to install"
        return 0
    fi

    # Count total files
    local total_files
    total_files=$(echo "$script_files" | wc -l | tr -d ' ')
    log_info "Found ${total_files} script files to install"

    # Copy each script file
    while IFS= read -r script_file; do
        if [[ -z "$script_file" ]]; then
            continue
        fi

        local file_name
        file_name=$(basename "$script_file")

        # Security: Check if file is a symlink
        if [[ -L "$script_file" ]]; then
            log_warning "  Skipping symlink: $file_name"
            ((failed++))
            continue
        fi

        # Copy file to target directory (use -P to not follow symlinks)
        if cp -P "$script_file" "$script_target_dir/$file_name"; then
            ((installed++))
            if $VERBOSE; then
                log_success "  Installed: $file_name"
            fi
        else
            ((failed++))
            log_warning "  Failed: $file_name"
        fi
    done <<< "$script_files"

    # Report results
    if [[ $failed -gt 0 ]]; then
        log_warning "Installed ${installed}/${total_files} script files (${failed} failed)"
        return 1
    fi

    log_success "Installed ${installed} script file(s) to .claude/scripts/"
    return 0
}

# Install config files to .claude/config/
bootstrap_config() {
    log_step "Installing config files to .claude/config/..."

    local config_source_dir="${STAGING_DIR}/files/plugins/autonomous-dev/config"
    local config_target_dir=".claude/config"
    local installed=0
    local failed=0

    # Check if config source directory exists
    if [[ ! -d "$config_source_dir" ]]; then
        log_warning "Config directory not found in staging - config files won't be installed"
        return 1
    fi

    # Create target directory if it doesn't exist
    if ! mkdir -p "$config_target_dir" 2>/dev/null; then
        log_error "Failed to create .claude/config/ directory (permission denied?)"
        return 1
    fi

    # Get list of .json files from config directory
    local config_files
    config_files=$(find "$config_source_dir" -maxdepth 1 -type f -name "*.json")

    if [[ -z "$config_files" ]]; then
        log_info "No config files found to install"
        return 0
    fi

    # Count total files
    local total_files
    total_files=$(echo "$config_files" | wc -l | tr -d ' ')
    log_info "Found ${total_files} config files to install"

    # Copy each config file
    while IFS= read -r config_file; do
        if [[ -z "$config_file" ]]; then
            continue
        fi

        local file_name
        file_name=$(basename "$config_file")

        # Security: Check if file is a symlink
        if [[ -L "$config_file" ]]; then
            log_warning "  Skipping symlink: $file_name"
            ((failed++))
            continue
        fi

        # Copy file to target directory (use -P to not follow symlinks)
        if cp -P "$config_file" "$config_target_dir/$file_name"; then
            ((installed++))
            if $VERBOSE; then
                log_success "  Installed: $file_name"
            fi
        else
            ((failed++))
            log_warning "  Failed: $file_name"
        fi
    done <<< "$config_files"

    # Report results
    if [[ $failed -gt 0 ]]; then
        log_warning "Installed ${installed}/${total_files} config files (${failed} failed)"
        return 1
    fi

    log_success "Installed ${installed} config file(s) to .claude/config/"
    return 0
}

# Install template files to .claude/templates/
bootstrap_templates() {
    log_step "Installing template files to .claude/templates/..."

    local template_source_dir="${STAGING_DIR}/files/plugins/autonomous-dev/templates"
    local template_target_dir=".claude/templates"
    local installed=0
    local failed=0

    # Check if template source directory exists
    if [[ ! -d "$template_source_dir" ]]; then
        log_warning "Templates directory not found in staging - template files won't be installed"
        return 1
    fi

    # Create target directory if it doesn't exist
    if ! mkdir -p "$template_target_dir" 2>/dev/null; then
        log_error "Failed to create .claude/templates/ directory (permission denied?)"
        return 1
    fi

    # Get list of .json files from templates directory
    local template_files
    template_files=$(find "$template_source_dir" -maxdepth 1 -type f -name "*.json")

    if [[ -z "$template_files" ]]; then
        log_info "No template files found to install"
        return 0
    fi

    # Count total files
    local total_files
    total_files=$(echo "$template_files" | wc -l | tr -d ' ')
    log_info "Found ${total_files} template files to install"

    # Copy each template file
    while IFS= read -r template_file; do
        if [[ -z "$template_file" ]]; then
            continue
        fi

        local file_name
        file_name=$(basename "$template_file")

        # Security: Check if file is a symlink
        if [[ -L "$template_file" ]]; then
            log_warning "  Skipping symlink: $file_name"
            ((failed++))
            continue
        fi

        # Copy file to target directory (use -P to not follow symlinks)
        if cp -P "$template_file" "$template_target_dir/$file_name"; then
            ((installed++))
            if $VERBOSE; then
                log_success "  Installed: $file_name"
            fi
        else
            ((failed++))
            log_warning "  Failed: $file_name"
        fi
    done <<< "$template_files"

    # Report results
    if [[ $failed -gt 0 ]]; then
        log_warning "Installed ${installed}/${total_files} template files (${failed} failed)"
        return 1
    fi

    log_success "Installed ${installed} template file(s) to .claude/templates/"
    return 0
}

# Install skill files to .claude/skills/ (recursive - includes subdirectories)
bootstrap_skills() {
    log_step "Installing skill files to .claude/skills/..."

    local skill_source_dir="${STAGING_DIR}/files/plugins/autonomous-dev/skills"
    local skill_target_dir=".claude/skills"
    local installed=0
    local failed=0

    # Check if skill source directory exists
    if [[ ! -d "$skill_source_dir" ]]; then
        log_warning "Skills directory not found in staging - skill files won't be installed"
        return 1
    fi

    # Create target directory if it doesn't exist
    if ! mkdir -p "$skill_target_dir" 2>/dev/null; then
        log_error "Failed to create .claude/skills/ directory (permission denied?)"
        return 1
    fi

    # Skills have subdirectories (e.g., api-design/docs/, testing-guide/docs/)
    # We need to copy the entire directory structure
    # Use find to get all files recursively, then recreate directory structure

    local skill_files
    skill_files=$(find "$skill_source_dir" -type f \( -name "*.md" -o -name "*.json" \))

    if [[ -z "$skill_files" ]]; then
        log_info "No skill files found to install"
        return 0
    fi

    # Count total files
    local total_files
    total_files=$(echo "$skill_files" | wc -l | tr -d ' ')
    log_info "Found ${total_files} skill files to install"

    # Copy each skill file, preserving directory structure
    while IFS= read -r skill_file; do
        if [[ -z "$skill_file" ]]; then
            continue
        fi

        # Get relative path from skill_source_dir
        local relative_path="${skill_file#$skill_source_dir/}"
        local target_file="$skill_target_dir/$relative_path"
        local target_dir
        target_dir=$(dirname "$target_file")

        # Security: Check if file is a symlink
        if [[ -L "$skill_file" ]]; then
            log_warning "  Skipping symlink: $relative_path"
            ((failed++))
            continue
        fi

        # Create target subdirectory if needed
        if ! mkdir -p "$target_dir" 2>/dev/null; then
            log_warning "  Failed to create directory: $target_dir"
            ((failed++))
            continue
        fi

        # Copy file to target directory (use -P to not follow symlinks)
        if cp -P "$skill_file" "$target_file"; then
            ((installed++))
            if $VERBOSE; then
                log_success "  Installed: $relative_path"
            fi
        else
            ((failed++))
            log_warning "  Failed: $relative_path"
        fi
    done <<< "$skill_files"

    # Report results
    if [[ $failed -gt 0 ]]; then
        log_warning "Installed ${installed}/${total_files} skill files (${failed} failed)"
        return 1
    fi

    log_success "Installed ${installed} skill file(s) to .claude/skills/"
    return 0
}

# Bootstrap .claude/local/ directory with OPERATIONS.md template (Issue #244)
bootstrap_local_operations() {
    log_step "Installing .claude/local/ directory template..."

    local local_source_dir="${STAGING_DIR}/files/plugins/autonomous-dev/templates/local"
    local local_target_dir=".claude/local"

    # Check if local source directory exists
    if [[ ! -d "$local_source_dir" ]]; then
        log_warning "Local templates directory not found in staging - .claude/local/ won't be bootstrapped"
        return 1
    fi

    # Create .claude/local/ directory if it doesn't exist (idempotent)
    if ! mkdir -p "$local_target_dir" 2>/dev/null; then
        log_error "Failed to create .claude/local/ directory (permission denied?)"
        return 1
    fi

    # Only copy OPERATIONS.md if it doesn't already exist (preserve user customizations)
    local operations_template="${local_source_dir}/OPERATIONS.md"
    local operations_target="${local_target_dir}/OPERATIONS.md"

    local files_installed=0

    # Copy OPERATIONS.md if it doesn't exist (preserve user customizations)
    if [[ ! -f "$operations_target" ]]; then
        if [[ -f "$operations_template" ]]; then
            if cp -P "$operations_template" "$operations_target" 2>/dev/null; then
                log_success "Installed OPERATIONS.md template to .claude/local/"
                ((files_installed++))
            else
                log_warning "Failed to copy OPERATIONS.md template"
            fi
        fi
    else
        # OPERATIONS.md already exists - preserve it (Issue #244)
        if $VERBOSE; then
            log_info ".claude/local/OPERATIONS.md already exists - preserving user customizations"
        fi
    fi

    # Copy ACTIVE_WORK.md if it doesn't exist (Issue #247 - session state)
    local active_work_template="${local_source_dir}/ACTIVE_WORK.md"
    local active_work_target="${local_target_dir}/ACTIVE_WORK.md"

    if [[ ! -f "$active_work_target" ]]; then
        if [[ -f "$active_work_template" ]]; then
            if cp -P "$active_work_template" "$active_work_target" 2>/dev/null; then
                log_success "Installed ACTIVE_WORK.md template to .claude/local/"
                ((files_installed++))
            else
                log_warning "Failed to copy ACTIVE_WORK.md template"
            fi
        fi
    else
        if $VERBOSE; then
            log_info ".claude/local/ACTIVE_WORK.md already exists - preserving session state"
        fi
    fi

    # Return success if at least one file installed or all already exist
    return 0
}

# Add autonomous-dev section to project CLAUDE.md (if exists)
add_autonomous_dev_section() {
    local project_claude_md="$1"

    # Only add if CLAUDE.md exists in current directory
    if [[ ! -f "$project_claude_md" ]]; then
        if $VERBOSE; then
            log_info "No CLAUDE.md found in current directory - skipping section injection"
        fi
        return 0
    fi

    log_step "Adding autonomous-dev section to CLAUDE.md..."

    # Use Python library for safe injection
    python3 - "$project_claude_md" "$STAGING_DIR" <<'INJECT_SCRIPT'
import sys
from pathlib import Path

claude_md_path = Path(sys.argv[1])
staging_dir = Path(sys.argv[2])

# Add lib to path
lib_dir = staging_dir / "plugins/autonomous-dev/lib"
sys.path.insert(0, str(lib_dir))

try:
    from claude_md_updater import ClaudeMdUpdater

    updater = ClaudeMdUpdater(claude_md_path)

    # Check if section already exists
    if updater.section_exists("autonomous-dev"):
        print("Section already exists - skipping")
        sys.exit(0)

    # Get template content
    template_file = staging_dir / "plugins/autonomous-dev/templates/claude_md_section.md"
    if not template_file.exists():
        print(f"Template not found: {template_file}", file=sys.stderr)
        sys.exit(1)

    section_content = template_file.read_text()

    # Inject section
    if updater.inject_section(section_content, "autonomous-dev"):
        print("Added autonomous-dev section to CLAUDE.md")
        sys.exit(0)
    else:
        print("No changes needed")
        sys.exit(0)

except ImportError as e:
    print(f"Library import failed: {e}", file=sys.stderr)
    sys.exit(1)
except Exception as e:
    print(f"Failed to update CLAUDE.md: {e}", file=sys.stderr)
    sys.exit(1)
INJECT_SCRIPT

    local result=$?
    if [[ $result -eq 0 ]]; then
        log_success "CLAUDE.md updated with autonomous-dev section"
        return 0
    else
        log_warning "CLAUDE.md update failed (non-critical)"
        return 1
    fi
}

main() {
    echo ""
    echo "╔══════════════════════════════════════════════════════════════╗"
    echo "║           autonomous-dev Plugin Bootstrap                    ║"
    echo "╚══════════════════════════════════════════════════════════════╝"
    echo ""


    # Issue #952: Check for existing global install and offer migration
    if [[ "$USER_SCOPE" == "false" ]] && [[ -f "${HOME}/.claude/hooks/unified_pre_tool.py" ]]; then
        echo ""
        echo "================================================================"
        echo "  MIGRATION NOTICE"
        echo "================================================================"
        echo ""
        echo "Detected existing global installation in ~/.claude/"
        echo ""
        echo "autonomous-dev now installs per-repo by default (./.claude/)."
        echo "This is safer: failures in one repo do not cascade to others."
        echo ""
        echo "Options:"
        echo "  1. Continue per-repo install (RECOMMENDED) - global remains for other repos"
        echo "  2. Keep using global: re-run with 'bash install.sh --scope=user'"
        echo "  3. Remove global first: 'bash install.sh --uninstall --scope=user'"
        echo ""
        if [[ -t 0 ]]; then
            read -r -p "Continue with per-repo install? [Y/n] " REPLY
            if [[ -n "$REPLY" && ! "$REPLY" =~ ^[Yy]$ ]]; then
                echo "Installation cancelled. Re-run with --scope=user for global install."
                exit 0
            fi
        else
            echo "Non-interactive shell: proceeding with per-repo install."
        fi
        echo ""
    fi
    # Issue #948: Standalone MCP migration mode — short-circuit the normal
    # install flow. This is intentionally NOT mixed with regular installs:
    # users invoke `install.sh --migrate-mcp-to-repo <path> --server <name>`
    # explicitly when they want to move servers from global to per-repo.
    if [[ -n "$MIGRATE_MCP_REPO" ]]; then
        if ! command -v python3 &> /dev/null; then
            log_error "Python 3 required for MCP migration"
            exit 1
        fi
        if migrate_mcp_to_repo; then
            exit 0
        else
            exit 1
        fi
    fi

    # Issue #949: Standalone recovery mode — strip hooks from
    # ~/.claude/settings.json. Like --migrate-mcp-to-repo, this short-
    # circuits the normal install flow. Used when global hooks misbehave
    # and Claude Code refuses to accept any prompt.
    if [[ "$RESET_HOOKS" == "true" ]]; then
        if ! command -v python3 &> /dev/null; then
            log_error "Python 3 required for --reset-hooks"
            exit 1
        fi
        if reset_global_hooks; then
            exit 0
        else
            exit 1
        fi
    fi

    # Issue #951: Standalone uninstall mode — shell-only uninstall path.
    # Coexists with /sync --uninstall (the Python orchestrator). This
    # path serves the "broken state, no Claude CLI" use case. Short-
    # circuits the normal install flow.
    if [[ "$UNINSTALL" == "true" ]]; then
        if ! command -v python3 &> /dev/null; then
            log_error "Python 3 required for --uninstall (manifest parsing + JSON mutation)"
            exit 1
        fi
        if uninstall_main; then
            exit 0
        else
            exit 1
        fi
    fi

    # Check requirements
    check_downloader

    # Check Python for manifest parsing
    if ! command -v python3 &> /dev/null; then
        log_error "Python 3 required for manifest parsing"
        exit 1
    fi

    # Clean existing staging if requested
    if $CLEAN && [[ -d "$STAGING_DIR" ]]; then
        log_step "Cleaning existing staging directory..."
        rm -rf "$STAGING_DIR"
    fi

    # Create staging directory
    mkdir -p "$STAGING_DIR"

    # Download manifest
    if ! download_manifest; then
        log_error "Failed to download manifest"
        exit 1
    fi

    # Download version
    download_version

    # Download all files
    if ! download_files; then
        log_warning "Some files failed to download"
        log_info "You can retry with: bash <(curl -sSL ${GITHUB_RAW}/install.sh)"
    fi

    # Install hook files to ~/.claude/hooks/ (non-blocking)
    local hook_install_success=false
    if install_hook_files; then
        hook_install_success=true
    else
        log_warning "Failed to install hook files"
        log_info "Hook files enable auto-approval, security validation, and git automation"
    fi

    # Install lib files to ~/.claude/lib/ (non-blocking)
    local lib_install_success=false
    if install_lib_files; then
        lib_install_success=true
    else
        log_warning "Failed to install lib files"
        log_info "Lib files are used by hooks for auto-approval and security validation"
    fi

    # Install core commands globally to ~/.claude/commands/ (enables /sync in any repo)
    local global_commands_success=false
    if install_global_commands; then
        global_commands_success=true
    else
        log_warning "Failed to install global commands"
        log_info "/sync and /setup won't be available in new repos until you run install.sh in that repo"
    fi

    # Bootstrap /setup command directly (enables fresh installs)
    local bootstrap_success=false
    if bootstrap_setup_command; then
        bootstrap_success=true
    else
        log_warning "Failed to bootstrap /setup command"
        log_info "You may need to manually copy it after restart:"
        log_info "  cp ${STAGING_DIR}/files/plugins/autonomous-dev/commands/setup.md .claude/commands/"
    fi

    # Bootstrap remaining commands (non-blocking)
    local commands_success=false
    if bootstrap_commands; then
        commands_success=true
    else
        log_warning "Failed to bootstrap command files"
        log_info "Commands like /implement, /create-issue won't be available"
    fi

    # Bootstrap agents (non-blocking)
    local agents_success=false
    if bootstrap_agents; then
        agents_success=true
    else
        log_warning "Failed to bootstrap agent files"
        log_info "Autonomous development workflow won't work without agents"
    fi

    # Bootstrap scripts (non-blocking)
    local scripts_success=false
    if bootstrap_scripts; then
        scripts_success=true
    else
        log_warning "Failed to bootstrap script files"
        log_info "Some advanced features may not work correctly"
    fi

    # Bootstrap config (non-blocking)
    local config_success=false
    if bootstrap_config; then
        config_success=true
    else
        log_warning "Failed to bootstrap config files"
        log_info "Default configurations will be used"
    fi

    # Bootstrap templates (non-blocking)
    local templates_success=false
    if bootstrap_templates; then
        templates_success=true
    else
        log_warning "Failed to bootstrap template files"
        log_info "Project setup may require manual configuration"
    fi

    # Bootstrap skills (non-blocking) - 158 files with subdirectories
    local skills_success=false
    if bootstrap_skills; then
        skills_success=true
    else
        log_warning "Failed to bootstrap skill files"
        log_info "Skills provide context for agents - some features may be limited"
    fi

    # Bootstrap .claude/local/ directory with OPERATIONS.md template (Issue #244)
    local local_operations_success=false
    if bootstrap_local_operations; then
        local_operations_success=true
    else
        log_warning "Failed to bootstrap .claude/local/ directory"
        log_info "You can manually create .claude/local/OPERATIONS.md for repo-specific procedures"
    fi

    # Configure global settings.json (opt-in via --global-settings, Issue #995)
    # Default behavior: do NOT touch ~/.claude/settings.json. Per-repo settings
    # in <repo>/.claude/settings.json are unchanged and still register the
    # pipeline hooks for autonomous-dev itself. Hook FILES are still cached to
    # ~/.claude/hooks/ via install_hook_files() so foreign repos that opt in
    # later have the library available.
    local settings_success=false
    if $GLOBAL_SETTINGS; then
        if configure_global_settings; then
            settings_success=true
        else
            log_warning "Settings configuration skipped (will use defaults)"
        fi
    else
        log_info "Skipped global settings.json hook registration (use --global-settings to opt in, Issue #995)"
    fi

    # Register plugin in installed_plugins.json (Issue #945)
    local plugin_registered=false
    if register_plugin; then
        plugin_registered=true
    else
        log_warning "Plugin registration failed - slash commands may not work"
    fi

    # Migrate hooks from array to object format (Issue #156)
    # Gated by --global-settings (Issue #995): when global hooks registration is
    # opt-out, the hooks block in ~/.claude/settings.json should not exist —
    # there is nothing to migrate, and we must not silently mutate the user's
    # global settings file.
    local hooks_migrated=false
    if $GLOBAL_SETTINGS; then
        if migrate_hooks_format; then
            hooks_migrated=true
        fi
    fi

    # Strip duplicated global hooks from per-repo settings.json (Issue #944)
    strip_duplicate_global_hooks || true

    # Print results
    echo ""
    log_success "Files staged to: ${STAGING_DIR}"
    if $hook_install_success; then
        log_success "Hook files installed to ~/.claude/hooks/"
    else
        log_warning "Hook files not installed (auto-git, security, etc. won't work)"
    fi
    if $lib_install_success; then
        log_success "Lib files installed to ~/.claude/lib/"
    else
        log_warning "Lib files not installed (hooks may not work correctly)"
    fi
    if $global_commands_success; then
        log_success "Core commands installed to ~/.claude/commands/ (/sync, /setup available globally)"
    else
        log_warning "Global commands not installed (/sync won't work in new repos)"
    fi
    if $bootstrap_success; then
        log_success "/setup command installed to .claude/commands/"
    else
        log_warning "/setup command not installed (see above for manual steps)"
    fi
    if $commands_success; then
        log_success "Command files installed to .claude/commands/"
    else
        log_warning "Command files not installed (workflows won't be available)"
    fi
    if $agents_success; then
        log_success "Agent files installed to .claude/agents/"
    else
        log_warning "Agent files not installed (autonomous workflow won't work)"
    fi
    if $scripts_success; then
        log_success "Script files installed to .claude/scripts/"
    else
        log_warning "Script files not installed (some features may not work)"
    fi
    if $config_success; then
        log_success "Config files installed to .claude/config/"
    else
        log_warning "Config files not installed (using defaults)"
    fi
    if $templates_success; then
        log_success "Template files installed to .claude/templates/"
    else
        log_warning "Template files not installed (manual config may be needed)"
    fi
    if $skills_success; then
        log_success "Skill files installed to .claude/skills/"
    else
        log_warning "Skill files not installed (agent context may be limited)"
    fi
    if $local_operations_success; then
        log_success ".claude/local/ directory bootstrapped with OPERATIONS.md template"
    else
        log_warning ".claude/local/ directory not bootstrapped (manual setup may be needed)"
    fi
    if $settings_success; then
        log_success "Global settings configured in ~/.claude/settings.json"
    else
        log_warning "Global settings not configured (will use Claude Code defaults)"
    fi
    echo ""

    # Add autonomous-dev section to CLAUDE.md (if exists in current directory)
    if [[ -f "$(pwd)/CLAUDE.md" ]]; then
        add_autonomous_dev_section "$(pwd)/CLAUDE.md"
    fi
    echo ""

    # Calculate overall success
    local all_critical_success=false
    if $bootstrap_success && $commands_success && $agents_success; then
        all_critical_success=true
    fi

    if $all_critical_success; then
        echo "╔══════════════════════════════════════════════════════════════╗"
        echo "║               🎉 Installation Complete 🎉                    ║"
        echo "╠══════════════════════════════════════════════════════════════╣"
        echo "║                                                              ║"
        echo "║  1. First install: Restart Claude Code to load everything    ║"
        echo "║     Press Cmd+Q (Mac) or Ctrl+Q (Windows/Linux)              ║"
        echo "║     Future updates: /reload-plugins (reloads commands,       ║"
        echo "║     agents, skills without restart)                          ║"
        echo "║     Note: /reload-plugins does NOT reload hooks/settings     ║"
        echo "║                                                              ║"
        echo "║  2. Plugin registered successfully - commands ready!          ║"
        echo "║                                                              ║"
        echo "║  Commands available after restart:                           ║"
        echo "║    /setup           - Interactive project setup              ║"
        echo "║    /implement       - Full autonomous development workflow   ║"
        echo "║                       (--quick, --batch, --issues, --resume) ║"
        echo "║    /sync            - Update plugin from GitHub/marketplace  ║"
        echo "║    /align           - Fix PROJECT.md/doc alignment           ║"
        echo "║    /health-check    - Validate plugin integrity              ║"
        echo "║    /create-issue    - Create GitHub issues with research     ║"
        echo "║    /reload-plugins  - Reload commands/agents/skills          ║"
        echo "║                                                              ║"
        echo "║  3. Run /setup in your project to begin                      ║"
        echo "║                                                              ║"
        echo "╚══════════════════════════════════════════════════════════════╝"
        if [[ "$plugin_registered" != "true" ]]; then
            echo "║                                                              ║"
            echo "║  ⚠ MANUAL PLUGIN REGISTRATION REQUIRED:                     ║"
            echo "║    After restart, run these commands:                        ║"
            echo "║    /plugin marketplace add akaszubski/autonomous-dev         ║"
            echo "║    /plugin install autonomous-dev                            ║"
            echo "║                                                              ║"
        fi
    elif $bootstrap_success; then
        echo "╔══════════════════════════════════════════════════════════════╗"
        echo "║                  PARTIAL INSTALLATION                        ║"
        echo "╠══════════════════════════════════════════════════════════════╣"
        echo "║                                                              ║"
        echo "║  /setup command installed, but some components failed.       ║"
        echo "║  Check warnings above for details.                           ║"
        echo "║                                                              ║"
        echo "║  1. First install: Restart Claude Code (Cmd+Q / Ctrl+Q)        ║"
        echo "║     Updates: /reload-plugins (hooks/settings need restart)   ║"
        echo "║  2. Run /setup - it may help recover missing files           ║"
        echo "║                                                              ║"
        echo "╚══════════════════════════════════════════════════════════════╝"
    else
        echo "╔══════════════════════════════════════════════════════════════╗"
        echo "║                  MANUAL STEPS REQUIRED                       ║"
        echo "╠══════════════════════════════════════════════════════════════╣"
        echo "║                                                              ║"
        echo "║  The /setup command could not be auto-installed.             ║"
        echo "║  Please copy it manually:                                    ║"
        echo "║                                                              ║"
        echo "║  mkdir -p .claude/commands                                   ║"
        echo "║  cp ~/.autonomous-dev-staging/files/plugins/autonomous-dev/  ║"
        echo "║     commands/setup.md .claude/commands/                      ║"
        echo "║                                                              ║"
        echo "║  Then restart Claude Code (or /reload-plugins) and run /setup ║"
        echo "║                                                              ║"
        echo "╚══════════════════════════════════════════════════════════════╝"
    fi
    echo ""
}

# Run main only when executed directly (not when sourced for testing)
if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
    main
fi
