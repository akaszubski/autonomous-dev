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
        --help|-h)
            echo "autonomous-dev Plugin Installer"
            echo ""
            echo "One-liner install for both fresh installs and updates."
            echo ""
            echo "Usage: install.sh [OPTIONS]"
            echo ""
            echo "Options:"
            echo "  --verbose, -v   Show detailed output"
            echo "  --clean         Remove existing staging directory first"
            echo "  --help, -h      Show this help message"
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

# Main
main() {
    echo ""
    echo "╔══════════════════════════════════════════════════════════════╗"
    echo "║           autonomous-dev Plugin Bootstrap                    ║"
    echo "╚══════════════════════════════════════════════════════════════╝"
    echo ""

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

    # Bootstrap /setup command directly (enables fresh installs)
    local bootstrap_success=false
    if bootstrap_setup_command; then
        bootstrap_success=true
    else
        log_warning "Failed to bootstrap /setup command"
        log_info "You may need to manually copy it after restart:"
        log_info "  cp ${STAGING_DIR}/files/plugins/autonomous-dev/commands/setup.md .claude/commands/"
    fi

    # Configure global settings.json (non-blocking)
    local settings_success=false
    if configure_global_settings; then
        settings_success=true
    else
        log_warning "Settings configuration skipped (will use defaults)"
    fi

    # Print results
    echo ""
    log_success "Files staged to: ${STAGING_DIR}"
    if $bootstrap_success; then
        log_success "/setup command installed to .claude/commands/"
    else
        log_warning "/setup command not installed (see above for manual steps)"
    fi
    if $settings_success; then
        log_success "Global settings configured in ~/.claude/settings.json"
    else
        log_warning "Global settings not configured (will use Claude Code defaults)"
    fi
    echo ""

    if $bootstrap_success; then
        echo "╔══════════════════════════════════════════════════════════════╗"
        echo "║                     NEXT STEPS                               ║"
        echo "╠══════════════════════════════════════════════════════════════╣"
        echo "║                                                              ║"
        echo "║  1. Restart Claude Code (required to load /setup command)    ║"
        echo "║     Press Cmd+Q (Mac) or Ctrl+Q (Windows/Linux)              ║"
        echo "║                                                              ║"
        echo "║  2. Open your project and run:                               ║"
        echo "║     /setup                                                   ║"
        echo "║                                                              ║"
        echo "║  The /setup wizard will:                                     ║"
        echo "║  • Detect fresh install vs update                            ║"
        echo "║  • Install all plugin files                                  ║"
        echo "║  • Protect your PROJECT.md and custom files                  ║"
        echo "║  • Guide you through configuration                           ║"
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
        echo "║  Then restart Claude Code and run /setup                     ║"
        echo "║                                                              ║"
        echo "╚══════════════════════════════════════════════════════════════╝"
    fi
    echo ""
}

# Run main
main
