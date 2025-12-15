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
    log_step "Installing hook files to ~/.claude/hooks/..."

    # Clean orphan hooks first (TRUE SYNC - remove files not in manifest)
    clean_orphan_files "${HOME}/.claude/hooks" "hooks" ".py"

    local hook_source_dir="${STAGING_DIR}/files/plugins/autonomous-dev/hooks"
    local hook_target_dir="${HOME}/.claude/hooks"
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

    # Get list of .py files from hooks directory
    local hook_files
    hook_files=$(find "$hook_source_dir" -maxdepth 1 -type f -name "*.py")

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

    log_success "Installed ${installed} hook file(s) to ~/.claude/hooks/"
    return 0
}

# Install lib files to ~/.claude/lib/
install_lib_files() {
    log_step "Installing lib files to ~/.claude/lib/..."

    # Clean orphan libs first (TRUE SYNC - remove files not in manifest)
    clean_orphan_files "${HOME}/.claude/lib" "lib" ".py"

    local lib_source_dir="${STAGING_DIR}/files/plugins/autonomous-dev/lib"
    local lib_target_dir="${HOME}/.claude/lib"
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

    # Get list of .py files from lib directory
    local lib_files
    lib_files=$(find "$lib_source_dir" -maxdepth 1 -type f -name "*.py" ! -name "__init__.py")

    if [[ -z "$lib_files" ]]; then
        log_info "No lib files found to install"
        return 0
    fi

    # Count total files
    local total_files
    total_files=$(echo "$lib_files" | wc -l | tr -d ' ')
    log_info "Found ${total_files} lib files to install"

    # Copy each lib file
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
        log_info "Commands like /auto-implement, /batch-implement won't be available"
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
    if $settings_success; then
        log_success "Global settings configured in ~/.claude/settings.json"
    else
        log_warning "Global settings not configured (will use Claude Code defaults)"
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
        echo "║  1. Restart Claude Code (required to load commands)          ║"
        echo "║     Press Cmd+Q (Mac) or Ctrl+Q (Windows/Linux)              ║"
        echo "║                                                              ║"
        echo "║  2. All 7 commands and 22 agents are now available!          ║"
        echo "║                                                              ║"
        echo "║  Commands available after restart:                           ║"
        echo "║    /setup           - Interactive project setup              ║"
        echo "║    /auto-implement  - Full autonomous development workflow   ║"
        echo "║    /batch-implement - Process multiple features              ║"
        echo "║    /sync            - Update plugin from GitHub/marketplace  ║"
        echo "║    /align           - Fix PROJECT.md/doc alignment           ║"
        echo "║    /health-check    - Validate plugin integrity              ║"
        echo "║    /create-issue    - Create GitHub issues with research     ║"
        echo "║                                                              ║"
        echo "║  3. Run /setup in your project to begin                      ║"
        echo "║                                                              ║"
        echo "╚══════════════════════════════════════════════════════════════╝"
    elif $bootstrap_success; then
        echo "╔══════════════════════════════════════════════════════════════╗"
        echo "║                  PARTIAL INSTALLATION                        ║"
        echo "╠══════════════════════════════════════════════════════════════╣"
        echo "║                                                              ║"
        echo "║  /setup command installed, but some components failed.       ║"
        echo "║  Check warnings above for details.                           ║"
        echo "║                                                              ║"
        echo "║  1. Restart Claude Code (Cmd+Q / Ctrl+Q)                     ║"
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
        echo "║  Then restart Claude Code and run /setup                     ║"
        echo "║                                                              ║"
        echo "╚══════════════════════════════════════════════════════════════╝"
    fi
    echo ""
}

# Run main only when executed directly (not when sourced for testing)
if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
    main
fi
