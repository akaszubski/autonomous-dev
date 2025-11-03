#!/usr/bin/env bash
#
# Test User Installation Flow
#
# Simulates a fresh user installing the plugin to verify:
# 1. Plugin install works
# 2. Bootstrap script works
# 3. All files copied correctly
# 4. Commands are available
# 5. Hooks are configured
#
# This tests the REAL user experience, not dogfooding
#
# Usage:
#   ./scripts/test-user-install.sh
#

set -e

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "🧪 Testing User Installation Flow"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "This simulates what a user experiences when installing"
echo "the plugin for the first time in a new project."
echo ""

# Get repo directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"

# Create test project directory
TEST_PROJECT="$REPO_DIR/test-user-project"

echo "📁 Test project: $TEST_PROJECT"
echo ""

# Clean up old test if exists
if [ -d "$TEST_PROJECT" ]; then
    echo "🧹 Cleaning up old test project..."
    rm -rf "$TEST_PROJECT"
fi

# Create fresh test project
echo "📂 Creating test project..."
mkdir -p "$TEST_PROJECT"
cd "$TEST_PROJECT"

# Initialize git (required for the plugin)
git init -q
echo "# Test Project" > README.md
git add README.md
git commit -q -m "Initial commit"

echo "✅ Test project created"
echo ""

# Check if plugin is installed
PLUGIN_DIR="$HOME/.claude/plugins/marketplaces/autonomous-dev/plugins/autonomous-dev"

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "Step 1: Verify Plugin Installation"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

if [ ! -d "$PLUGIN_DIR" ]; then
    echo "❌ Plugin not installed"
    echo ""
    echo "Please install first:"
    echo "  1. In Claude Code: /plugin marketplace add akaszubski/autonomous-dev"
    echo "  2. In Claude Code: /plugin install autonomous-dev"
    echo "  3. Exit and restart Claude Code"
    echo "  4. Run this script again"
    echo ""
    exit 1
fi

echo "✅ Plugin found at: $PLUGIN_DIR"
echo ""

# Check plugin version
VERSION=$(cat "$HOME/.claude/plugins/installed_plugins.json" | grep -A 5 "autonomous-dev" | grep version | head -1 | cut -d'"' -f4)
echo "📦 Installed version: $VERSION"
echo ""

# Check plugin structure
echo "🔍 Checking plugin structure..."
AGENT_COUNT=$(ls -1 "$PLUGIN_DIR/agents"/*.md 2>/dev/null | wc -l | tr -d ' ')
COMMAND_COUNT=$(ls -1 "$PLUGIN_DIR/commands"/*.md 2>/dev/null | wc -l | tr -d ' ')
HOOK_COUNT=$(find "$PLUGIN_DIR/hooks" -name "*.py" 2>/dev/null | wc -l | tr -d ' ')

echo "   📊 Agents: $AGENT_COUNT"
echo "   📋 Commands: $COMMAND_COUNT"
echo "   🎣 Hooks: $HOOK_COUNT"
echo ""

if [ "$AGENT_COUNT" -lt 15 ]; then
    echo "⚠️  Warning: Expected ~19 agents, found $AGENT_COUNT"
fi

if [ "$COMMAND_COUNT" -lt 5 ]; then
    echo "⚠️  Warning: Expected 7-8 commands, found $COMMAND_COUNT"
fi

if [ "$HOOK_COUNT" -lt 20 ]; then
    echo "⚠️  Warning: Expected ~28 hooks, found $HOOK_COUNT"
fi

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "Step 2: Run Bootstrap Script"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

# Run the actual bootstrap script from GitHub (simulating user experience)
echo "🚀 Running bootstrap (as user would)..."
echo ""

# Use local install.sh for testing (simulates what GitHub version does)
bash "$REPO_DIR/install.sh"

echo ""

# Verify bootstrap results
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "Step 3: Verify Bootstrap Results"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

ERRORS=0

# Check .claude directory created
if [ ! -d ".claude" ]; then
    echo "❌ .claude directory not created"
    ERRORS=$((ERRORS + 1))
else
    echo "✅ .claude directory created"
fi

# Check commands copied
if [ ! -d ".claude/commands" ]; then
    echo "❌ .claude/commands directory missing"
    ERRORS=$((ERRORS + 1))
else
    COPIED_COMMANDS=$(ls -1 .claude/commands/*.md 2>/dev/null | wc -l | tr -d ' ')
    if [ "$COPIED_COMMANDS" -ge 5 ]; then
        echo "✅ Commands copied: $COPIED_COMMANDS files"
    else
        echo "❌ Commands incomplete: only $COPIED_COMMANDS files"
        ERRORS=$((ERRORS + 1))
    fi
fi

# Check hooks copied
if [ ! -d ".claude/hooks" ]; then
    echo "❌ .claude/hooks directory missing"
    ERRORS=$((ERRORS + 1))
else
    COPIED_HOOKS=$(find .claude/hooks -name "*.py" 2>/dev/null | wc -l | tr -d ' ')
    if [ "$COPIED_HOOKS" -ge 20 ]; then
        echo "✅ Hooks copied: $COPIED_HOOKS files"
    else
        echo "❌ Hooks incomplete: only $COPIED_HOOKS files"
        ERRORS=$((ERRORS + 1))
    fi
fi

# Check templates copied
if [ ! -d ".claude/templates" ]; then
    echo "❌ .claude/templates directory missing"
    ERRORS=$((ERRORS + 1))
else
    COPIED_TEMPLATES=$(find .claude/templates -type f 2>/dev/null | wc -l | tr -d ' ')
    if [ "$COPIED_TEMPLATES" -ge 1 ]; then
        echo "✅ Templates copied: $COPIED_TEMPLATES files"
    else
        echo "⚠️  Templates: $COPIED_TEMPLATES files (may be okay)"
    fi
fi

# Check bootstrap marker
if [ ! -f ".claude/.autonomous-dev-bootstrapped" ]; then
    echo "⚠️  Bootstrap marker not created (minor issue)"
else
    echo "✅ Bootstrap marker created"
fi

echo ""

# Test specific critical files
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "Step 4: Verify Critical Files"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

CRITICAL_COMMANDS=(
    "auto-implement.md"
    "status.md"
    "setup.md"
    "health-check.md"
    "align-project.md"
)

echo "📋 Checking critical commands..."
for cmd in "${CRITICAL_COMMANDS[@]}"; do
    if [ -f ".claude/commands/$cmd" ]; then
        echo "   ✅ $cmd"
    else
        echo "   ❌ $cmd MISSING"
        ERRORS=$((ERRORS + 1))
    fi
done

echo ""

CRITICAL_HOOKS=(
    "detect_feature_request.py"
    "validate_project_alignment.py"
    "security_scan.py"
    "auto_format.py"
    "auto_test.py"
)

echo "🎣 Checking critical hooks..."
for hook in "${CRITICAL_HOOKS[@]}"; do
    if [ -f ".claude/hooks/$hook" ]; then
        echo "   ✅ $hook"
    else
        echo "   ❌ $hook MISSING"
        ERRORS=$((ERRORS + 1))
    fi
done

echo ""

# Test hook execution
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "Step 5: Test Hook Functionality"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

if [ -f ".claude/hooks/detect_feature_request.py" ]; then
    echo "🧪 Testing detect_feature_request hook..."

    # Test positive case
    if echo "implement user authentication" | python .claude/hooks/detect_feature_request.py 2>/dev/null; then
        echo "   ✅ Feature detection: PASS"
    else
        echo "   ❌ Feature detection: FAIL"
        ERRORS=$((ERRORS + 1))
    fi

    # Test negative case
    if ! echo "what is the weather" | python .claude/hooks/detect_feature_request.py 2>/dev/null; then
        echo "   ✅ Non-feature detection: PASS"
    else
        echo "   ❌ Non-feature detection: FAIL (false positive)"
        ERRORS=$((ERRORS + 1))
    fi
else
    echo "❌ Cannot test hooks - files missing"
    ERRORS=$((ERRORS + 1))
fi

echo ""

# Generate report
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "📊 Test Results"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

if [ $ERRORS -eq 0 ]; then
    echo "✅ ALL TESTS PASSED"
    echo ""
    echo "The user installation flow works correctly!"
    echo ""
    echo "Test project created at:"
    echo "  $TEST_PROJECT"
    echo ""
    echo "You can inspect the results or clean up:"
    echo "  cd $TEST_PROJECT"
    echo "  # OR"
    echo "  rm -rf $TEST_PROJECT"
    echo ""
    exit 0
else
    echo "❌ $ERRORS ERROR(S) FOUND"
    echo ""
    echo "The user installation flow has issues."
    echo ""
    echo "Test project preserved at:"
    echo "  $TEST_PROJECT"
    echo ""
    echo "Inspect the .claude/ directory to debug:"
    echo "  ls -la $TEST_PROJECT/.claude/"
    echo ""
    exit 1
fi
