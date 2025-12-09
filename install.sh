#!/usr/bin/env bash
#
# autonomous-dev Plugin Installer
#
# One-liner installation:
#   bash <(curl -sSL https://raw.githubusercontent.com/akaszubski/autonomous-dev/master/install.sh)
#
# With options:
#   bash <(curl -sSL .../install.sh) --update    # Update existing installation
#   bash <(curl -sSL .../install.sh) --sync      # Sync/repair installation
#   bash <(curl -sSL .../install.sh) --force     # Force reinstall (overwrites all)
#   bash <(curl -sSL .../install.sh) --check     # Check for updates only
#
# Requirements:
#   - Python 3.8+
#   - curl or wget
#   - Write access to current directory
#
# Security:
#   - Uses HTTPS with TLS 1.2+
#   - No sudo required
#   - Path validation (CWE-22, CWE-59 prevention)
#   - Rollback on failure
#

set -euo pipefail

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
GITHUB_REPO="akaszubski/autonomous-dev"
GITHUB_BRANCH="master"
GITHUB_RAW="https://raw.githubusercontent.com/${GITHUB_REPO}/${GITHUB_BRANCH}"
MIN_PYTHON_VERSION="3.8"
INSTALLER_SCRIPT="install.py"

# Parse arguments
MODE="install"
VERBOSE=false

while [[ $# -gt 0 ]]; do
    case $1 in
        --update|-u)
            MODE="update"
            shift
            ;;
        --sync|-s)
            MODE="sync"
            shift
            ;;
        --force|-f)
            MODE="force"
            shift
            ;;
        --check|-c)
            MODE="check"
            shift
            ;;
        --verbose|-v)
            VERBOSE=true
            shift
            ;;
        --help|-h)
            echo "autonomous-dev Plugin Installer"
            echo ""
            echo "Usage: install.sh [OPTIONS]"
            echo ""
            echo "Options:"
            echo "  --update, -u    Update existing installation (preserves customizations)"
            echo "  --sync, -s      Sync/repair installation (fixes missing files)"
            echo "  --force, -f     Force reinstall (overwrites everything)"
            echo "  --check, -c     Check for updates only (no changes)"
            echo "  --verbose, -v   Show detailed output"
            echo "  --help, -h      Show this help message"
            echo ""
            echo "Examples:"
            echo "  # Fresh install"
            echo "  bash <(curl -sSL ${GITHUB_RAW}/install.sh)"
            echo ""
            echo "  # Update existing installation"
            echo "  bash <(curl -sSL ${GITHUB_RAW}/install.sh) --update"
            echo ""
            echo "  # Repair broken installation"
            echo "  bash <(curl -sSL ${GITHUB_RAW}/install.sh) --sync"
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
    echo -e "${BLUE}→${NC} $1"
}

# Check Python version
check_python() {
    log_step "Checking Python version..."

    # Try python3 first, then python
    if command -v python3 &> /dev/null; then
        PYTHON_CMD="python3"
    elif command -v python &> /dev/null; then
        PYTHON_CMD="python"
    else
        log_error "Python not found. Please install Python ${MIN_PYTHON_VERSION}+"
        exit 1
    fi

    # Check version
    PYTHON_VERSION=$($PYTHON_CMD -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')
    PYTHON_MAJOR=$($PYTHON_CMD -c 'import sys; print(sys.version_info.major)')
    PYTHON_MINOR=$($PYTHON_CMD -c 'import sys; print(sys.version_info.minor)')

    if [[ $PYTHON_MAJOR -lt 3 ]] || [[ $PYTHON_MAJOR -eq 3 && $PYTHON_MINOR -lt 8 ]]; then
        log_error "Python ${MIN_PYTHON_VERSION}+ required. Found: ${PYTHON_VERSION}"
        exit 1
    fi

    log_success "Python ${PYTHON_VERSION} found"
}

# Check for curl or wget
check_downloader() {
    if command -v curl &> /dev/null; then
        DOWNLOADER="curl"
        DOWNLOAD_CMD="curl -sSL"
    elif command -v wget &> /dev/null; then
        DOWNLOADER="wget"
        DOWNLOAD_CMD="wget -qO-"
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

    if [[ "$DOWNLOADER" == "curl" ]]; then
        curl --proto '=https' --tlsv1.2 -sSL "$url" -o "$output"
    else
        wget --secure-protocol=TLSv1_2 -qO "$output" "$url"
    fi
}

# Main installation
main() {
    echo ""
    echo "╔══════════════════════════════════════════════════════════════╗"
    echo "║         autonomous-dev Plugin Installer                      ║"
    echo "║         Mode: ${MODE}                                             ║"
    echo "╚══════════════════════════════════════════════════════════════╝"
    echo ""

    # Pre-flight checks
    check_python
    check_downloader

    # Create temp directory
    TEMP_DIR=$(mktemp -d)
    trap "rm -rf $TEMP_DIR" EXIT

    log_step "Downloading installer from GitHub..."

    # Download the Python installer script
    INSTALLER_URL="${GITHUB_RAW}/plugins/autonomous-dev/scripts/${INSTALLER_SCRIPT}"
    INSTALLER_PATH="${TEMP_DIR}/${INSTALLER_SCRIPT}"

    if ! download_file "$INSTALLER_URL" "$INSTALLER_PATH" 2>/dev/null; then
        log_error "Failed to download installer from GitHub"
        log_info "URL: ${INSTALLER_URL}"
        log_info ""
        log_info "Troubleshooting:"
        log_info "  1. Check your internet connection"
        log_info "  2. Verify GitHub is accessible: https://github.com/${GITHUB_REPO}"
        log_info "  3. Try again in a few moments"
        exit 1
    fi

    log_success "Installer downloaded"

    # Run the Python installer with mode
    log_step "Running installation (mode: ${MODE})..."
    echo ""

    # Pass mode and options to Python installer
    INSTALLER_ARGS="--mode ${MODE}"
    if $VERBOSE; then
        INSTALLER_ARGS="${INSTALLER_ARGS} --verbose"
    fi

    if ! $PYTHON_CMD "$INSTALLER_PATH" $INSTALLER_ARGS; then
        log_error "Installation failed"
        log_info ""
        log_info "For help, see: https://github.com/${GITHUB_REPO}#troubleshooting"
        exit 1
    fi

    echo ""
    log_success "Installation complete!"
    echo ""

    # Post-install instructions
    echo "╔══════════════════════════════════════════════════════════════╗"
    echo "║                     NEXT STEPS                               ║"
    echo "╠══════════════════════════════════════════════════════════════╣"
    echo "║                                                              ║"
    echo "║  1. Restart Claude Code                                      ║"
    echo "║     Press Cmd+Q (Mac) or Ctrl+Q (Windows/Linux)              ║"
    echo "║                                                              ║"
    echo "║  2. Verify installation                                      ║"
    echo "║     Run: /health-check                                       ║"
    echo "║                                                              ║"
    echo "║  3. Start developing                                         ║"
    echo "║     Run: /auto-implement <your feature>                      ║"
    echo "║                                                              ║"
    echo "╚══════════════════════════════════════════════════════════════╝"
    echo ""
}

# Run main
main
