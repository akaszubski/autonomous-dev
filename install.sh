#!/usr/bin/env bash
#
# autonomous-dev Plugin Bootstrap
#
# Downloads plugin files to staging area, then Claude Code handles intelligent installation.
#
# One-liner:
#   bash <(curl -sSL https://raw.githubusercontent.com/akaszubski/autonomous-dev/master/install.sh)
#
# What this does:
#   1. Downloads plugin files to ~/.autonomous-dev-staging/
#   2. Tells you to run /setup in Claude Code
#   3. Claude Code intelligently installs, handling:
#      - Fresh installs vs brownfield (existing .claude/)
#      - Protected files (PROJECT.md, .env - never touched)
#      - Customized hooks (preserved or backed up)
#      - Post-install validation
#
# Requirements:
#   - curl or wget
#   - Claude Code installed
#
# Security:
#   - HTTPS with TLS 1.2+
#   - No sudo required
#   - Files staged, not installed directly
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
            echo "autonomous-dev Plugin Bootstrap"
            echo ""
            echo "Downloads plugin files for Claude Code to install intelligently."
            echo ""
            echo "Usage: install.sh [OPTIONS]"
            echo ""
            echo "Options:"
            echo "  --verbose, -v   Show detailed output"
            echo "  --clean         Remove existing staging directory first"
            echo "  --help, -h      Show this help message"
            echo ""
            echo "After running this script:"
            echo "  1. Open your project in Claude Code"
            echo "  2. Run /setup to install"
            echo ""
            echo "Claude Code will handle:"
            echo "  - Fresh install vs update detection"
            echo "  - Protecting your PROJECT.md and .env"
            echo "  - Preserving customized hooks"
            echo "  - Post-install validation"
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

    # Use Python to parse manifest and get file list
    local files
    files=$(python3 -c "
import json
with open('${manifest_path}') as f:
    manifest = json.load(f)
for component, config in manifest.get('components', {}).items():
    for file_path in config.get('files', []):
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

    # Success - print next steps
    echo ""
    log_success "Files staged to: ${STAGING_DIR}"
    echo ""
    echo "╔══════════════════════════════════════════════════════════════╗"
    echo "║                     NEXT STEPS                               ║"
    echo "╠══════════════════════════════════════════════════════════════╣"
    echo "║                                                              ║"
    echo "║  1. Open your project folder in Claude Code                  ║"
    echo "║     cd /path/to/your/project && claude                       ║"
    echo "║                                                              ║"
    echo "║  2. Run the setup command                                    ║"
    echo "║     /setup                                                   ║"
    echo "║                                                              ║"
    echo "║  Claude Code will intelligently:                             ║"
    echo "║  • Detect fresh install vs existing installation             ║"
    echo "║  • Protect your PROJECT.md and custom files                  ║"
    echo "║  • Update outdated plugin files                              ║"
    echo "║  • Validate the installation works                           ║"
    echo "║                                                              ║"
    echo "╚══════════════════════════════════════════════════════════════╝"
    echo ""
}

# Run main
main
