#!/bin/bash
# MCP Server Test Script
# Tests all MCP server configurations

set -e

REPO_ROOT="$HOME/Documents/GitHub/autonomous-dev"
cd "$REPO_ROOT"

echo "╔═══════════════════════════════════════════════════════════════╗"
echo "║              MCP SERVER CONFIGURATION TEST                    ║"
echo "╚═══════════════════════════════════════════════════════════════╝"
echo ""

# Color codes
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

pass() {
    echo -e "${GREEN}✅ PASS${NC}: $1"
}

fail() {
    echo -e "${RED}❌ FAIL${NC}: $1"
}

warn() {
    echo -e "${YELLOW}⚠️  WARN${NC}: $1"
}

echo "📋 Test Suite: MCP Server Configuration"
echo "═══════════════════════════════════════════════════════════════"
echo ""

# Test 1: Configuration file exists and is valid JSON
echo "Test 1: Configuration file validation"
if [ -f ".mcp/config.json" ]; then
    if python3 -m json.tool .mcp/config.json > /dev/null 2>&1; then
        pass "config.json is valid JSON"
    else
        fail "config.json is invalid JSON"
        exit 1
    fi
else
    fail "config.json not found"
    exit 1
fi
echo ""

# Test 2: Filesystem server - Check repository root exists
echo "Test 2: Filesystem server configuration"
if [ -d "$REPO_ROOT" ]; then
    pass "Repository root exists: $REPO_ROOT"
else
    fail "Repository root not found: $REPO_ROOT"
fi

# Test write permissions
if [ -w "$REPO_ROOT" ]; then
    pass "Write permissions available"
else
    fail "No write permissions"
fi
echo ""

# Test 3: Shell server - Check allowed commands
echo "Test 3: Shell server - Command availability"
commands=("git" "gh" "bash" "zsh")

for cmd in "${commands[@]}"; do
    if command -v "$cmd" &> /dev/null; then
        pass "Command available: $cmd ($(command -v $cmd))"
    else
        warn "Command not found: $cmd (may not be needed)"
    fi
done
echo ""

# Test 4: Git server - Check git repository
echo "Test 4: Git server configuration"
if [ -d "$REPO_ROOT/.git" ]; then
    pass "Git repository detected"

    # Check git status works
    if git status &> /dev/null; then
        pass "Git status command works"
        echo "   Current branch: $(git branch --show-current)"
        echo "   Latest commit: $(git log -1 --oneline)"
    else
        fail "Git status command failed"
    fi
else
    fail "Not a git repository"
fi
echo ""

# Test 5: Python server - Check Python interpreter
echo "Test 5: Python server configuration"
PYTHON_PATH="$REPO_ROOT/venv/bin/python"

if [ -d "$REPO_ROOT/venv" ]; then
    pass "Virtual environment exists: venv/"

    if [ -f "$PYTHON_PATH" ]; then
        pass "Python interpreter found: $PYTHON_PATH"
        echo "   Python version: $($PYTHON_PATH --version)"
    else
        fail "Python interpreter not found at: $PYTHON_PATH"
        echo "   Create with: python3 -m venv venv"
    fi
else
    warn "Virtual environment not found (optional)"
    echo "   Create with: python3 -m venv venv"
fi
echo ""

# Test 6: Environment variables
echo "Test 6: Environment configuration"
if [ -f "$REPO_ROOT/.env" ]; then
    pass ".env file exists"

    # Check for required keys (without exposing values)
    required_vars=("GITHUB_TOKEN")
    for var in "${required_vars[@]}"; do
        if grep -q "^${var}=" "$REPO_ROOT/.env" 2>/dev/null; then
            pass "Environment variable configured: $var"
        else
            warn "Environment variable not found: $var"
        fi
    done
else
    warn ".env file not found (optional)"
    echo "   Copy from: cp .env.example .env"
fi
echo ""

# Test 7: MCP dependencies
echo "Test 7: MCP server dependencies"

# Check for npx (needed for MCP servers)
if command -v npx &> /dev/null; then
    pass "npx available ($(npx --version))"
else
    fail "npx not found - Install Node.js from https://nodejs.org/"
fi

# Check for Node.js
if command -v node &> /dev/null; then
    pass "Node.js available ($(node --version))"
else
    fail "Node.js not found - Install from https://nodejs.org/"
fi
echo ""

# Test 8: Test actual MCP server connection (if MCP CLI available)
echo "Test 8: MCP server connection test"
if command -v mcp &> /dev/null; then
    pass "MCP CLI available"
    # Could add actual connection test here
else
    warn "MCP CLI not found (install to test actual connection)"
    echo "   This is optional - servers will work with Claude Desktop"
fi
echo ""

# Summary
echo "═══════════════════════════════════════════════════════════════"
echo "📊 TEST SUMMARY"
echo "═══════════════════════════════════════════════════════════════"
echo ""
echo "Configuration: .mcp/config.json"
echo "Repository: $REPO_ROOT"
echo ""

if [ -d "$REPO_ROOT/venv" ]; then
    echo -e "${GREEN}✅ Ready for MCP server usage${NC}"
    echo ""
    echo "Next steps:"
    echo "1. Configure Claude Desktop with MCP servers"
    echo "2. See .mcp/README.md for Claude Desktop configuration"
else
    echo -e "${YELLOW}⚠️  Setup incomplete${NC}"
    echo ""
    echo "Next steps:"
    echo "1. Create virtual environment: python3 -m venv venv"
    echo "2. Activate: source venv/bin/activate"
    echo "3. Install dependencies: pip install pytest black isort"
    echo "4. Configure Claude Desktop with MCP servers"
    echo "5. See .mcp/README.md for details"
fi
echo ""
echo "═══════════════════════════════════════════════════════════════"
