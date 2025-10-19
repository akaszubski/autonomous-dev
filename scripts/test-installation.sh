#!/bin/bash
# Test script for PROJECT.md-first architecture installation
# Usage: ./scripts/test-installation.sh [test-project-path]

set -e  # Exit on error

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
REPO_ROOT="$(dirname "$SCRIPT_DIR")"
TEST_PROJECT="${1:-/tmp/test-autonomous-dev-$(date +%s)}"

echo "=========================================="
echo "Testing autonomous-dev Plugin Installation"
echo "=========================================="
echo ""
echo "Test project: $TEST_PROJECT"
echo ""

# Colors for output
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Test counter
TESTS_PASSED=0
TESTS_FAILED=0

# Test helper function
test_file_exists() {
    local file=$1
    local description=$2

    if [ -f "$file" ]; then
        echo -e "${GREEN}✅ PASS${NC}: $description"
        ((TESTS_PASSED++))
        return 0
    else
        echo -e "${RED}❌ FAIL${NC}: $description"
        echo "   Expected file: $file"
        ((TESTS_FAILED++))
        return 1
    fi
}

test_dir_exists() {
    local dir=$1
    local description=$2

    if [ -d "$dir" ]; then
        echo -e "${GREEN}✅ PASS${NC}: $description"
        ((TESTS_PASSED++))
        return 0
    else
        echo -e "${RED}❌ FAIL${NC}: $description"
        echo "   Expected directory: $dir"
        ((TESTS_FAILED++))
        return 1
    fi
}

test_content_exists() {
    local file=$1
    local pattern=$2
    local description=$3

    if grep -q "$pattern" "$file" 2>/dev/null; then
        echo -e "${GREEN}✅ PASS${NC}: $description"
        ((TESTS_PASSED++))
        return 0
    else
        echo -e "${RED}❌ FAIL${NC}: $description"
        echo "   File: $file"
        echo "   Pattern: $pattern"
        ((TESTS_FAILED++))
        return 1
    fi
}

# Step 1: Create test project
echo "=========================================="
echo "Step 1: Creating Test Project"
echo "=========================================="
echo ""

mkdir -p "$TEST_PROJECT"
cd "$TEST_PROJECT"
git init
echo "# Test Project" > README.md
git add README.md
git commit -m "Initial commit"

echo -e "${GREEN}✓${NC} Test project created"
echo ""

# Step 2: Simulate plugin installation
echo "=========================================="
echo "Step 2: Simulating Plugin Installation"
echo "=========================================="
echo ""

# Copy plugin files (simulate /plugin install autonomous-dev)
mkdir -p .claude/agents
mkdir -p .claude/skills
mkdir -p .claude/commands
mkdir -p .claude/templates
mkdir -p scripts/hooks

# Copy agents
cp -r "$REPO_ROOT/plugins/autonomous-dev/agents/"* .claude/agents/ 2>/dev/null || true

# Copy skills
cp -r "$REPO_ROOT/plugins/autonomous-dev/skills/"* .claude/skills/ 2>/dev/null || true

# Copy commands
cp -r "$REPO_ROOT/plugins/autonomous-dev/commands/"* .claude/commands/ 2>/dev/null || true

# Copy templates
cp -r "$REPO_ROOT/plugins/autonomous-dev/templates/"* .claude/templates/ 2>/dev/null || true

# Copy .env.example
cp "$REPO_ROOT/.env.example" .env.example 2>/dev/null || true

echo -e "${GREEN}✓${NC} Plugin files copied"
echo ""

# Step 3: Verify Core Files
echo "=========================================="
echo "Step 3: Verifying Core Files"
echo "=========================================="
echo ""

test_file_exists ".env.example" "GitHub auth template exists"
test_file_exists ".claude/templates/PROJECT.md" "PROJECT.md template exists"

# Step 4: Verify Agents
echo ""
echo "=========================================="
echo "Step 4: Verifying Agents (8 total)"
echo "=========================================="
echo ""

test_file_exists ".claude/agents/orchestrator.md" "orchestrator agent installed"
test_file_exists ".claude/agents/planner.md" "planner agent installed"
test_file_exists ".claude/agents/researcher.md" "researcher agent installed"
test_file_exists ".claude/agents/test-master.md" "test-master agent installed"
test_file_exists ".claude/agents/implementer.md" "implementer agent installed"
test_file_exists ".claude/agents/reviewer.md" "reviewer agent installed"
test_file_exists ".claude/agents/security-auditor.md" "security-auditor agent installed"
test_file_exists ".claude/agents/doc-master.md" "doc-master agent installed"

# Step 5: Verify Agent Configurations
echo ""
echo "=========================================="
echo "Step 5: Verifying Agent Configurations"
echo "=========================================="
echo ""

test_content_exists ".claude/agents/orchestrator.md" "PRIMARY MISSION" "orchestrator has PRIMARY MISSION"
test_content_exists ".claude/agents/orchestrator.md" "PROJECT.md" "orchestrator checks PROJECT.md"
test_content_exists ".claude/agents/planner.md" "model: opus" "planner uses opus model"
test_content_exists ".claude/agents/researcher.md" "model: sonnet" "researcher uses sonnet model"
test_content_exists ".claude/agents/security-auditor.md" "model: haiku" "security-auditor uses haiku model"

# Step 6: Verify Commands
echo ""
echo "=========================================="
echo "Step 6: Verifying Commands"
echo "=========================================="
echo ""

test_file_exists ".claude/commands/align-project.md" "/align-project command exists"
test_file_exists ".claude/commands/align-project-safe.md" "/align-project-safe command exists"

# Step 7: Verify Command Features
echo ""
echo "=========================================="
echo "Step 7: Verifying /align-project Workflow"
echo "=========================================="
echo ""

test_content_exists ".claude/commands/align-project-safe.md" "Phase 1" "3-phase safe approach exists"
test_content_exists ".claude/commands/align-project-safe.md" "Phase 2" "Generate PROJECT.md phase exists"
test_content_exists ".claude/commands/align-project-safe.md" "Phase 3" "Interactive alignment phase exists"
test_content_exists ".claude/commands/align-project-safe.md" "ANALYZE" "Analysis phase documented"
test_content_exists ".claude/commands/align-project-safe.md" "INTERACTIVE" "Interactive mode documented"
test_content_exists ".claude/commands/align-project-safe.md" "Safety Features" "Safety features section exists"

# Step 8: Verify PROJECT.md Template
echo ""
echo "=========================================="
echo "Step 8: Verifying PROJECT.md Template"
echo "=========================================="
echo ""

test_content_exists ".claude/templates/PROJECT.md" "## GOALS" "Template has GOALS section"
test_content_exists ".claude/templates/PROJECT.md" "## SCOPE" "Template has SCOPE section"
test_content_exists ".claude/templates/PROJECT.md" "## CONSTRAINTS" "Template has CONSTRAINTS section"
test_content_exists ".claude/templates/PROJECT.md" "## CURRENT SPRINT" "Template has CURRENT SPRINT section"
test_content_exists ".claude/templates/PROJECT.md" "## ARCHITECTURE" "Template has ARCHITECTURE section"

# Step 9: Verify .env Template
echo ""
echo "=========================================="
echo "Step 9: Verifying .env Template"
echo "=========================================="
echo ""

test_content_exists ".env.example" "GITHUB_TOKEN" ".env.example has GITHUB_TOKEN"

# Step 10: Test PROJECT.md Creation
echo ""
echo "=========================================="
echo "Step 10: Testing PROJECT.md Creation"
echo "=========================================="
echo ""

cp .claude/templates/PROJECT.md .claude/PROJECT.md
test_file_exists ".claude/PROJECT.md" "PROJECT.md can be created from template"

# Summary
echo ""
echo "=========================================="
echo "TEST SUMMARY"
echo "=========================================="
echo ""
echo -e "Tests Passed: ${GREEN}$TESTS_PASSED${NC}"
echo -e "Tests Failed: ${RED}$TESTS_FAILED${NC}"
echo ""

if [ $TESTS_FAILED -eq 0 ]; then
    echo -e "${GREEN}✅ ALL TESTS PASSED${NC}"
    echo ""
    echo "=========================================="
    echo "Next Steps for Manual Testing:"
    echo "=========================================="
    echo ""
    echo "1. Open Claude Code in this test project:"
    echo "   cd $TEST_PROJECT"
    echo ""
    echo "2. Test orchestrator coordination:"
    echo "   (In Claude Code) \"Create a simple hello world function\""
    echo "   - Verify orchestrator checks PROJECT.md"
    echo ""
    echo "3. Test /align-project command:"
    echo "   (In Claude Code) /align-project"
    echo "   - Should analyze project structure"
    echo ""
    echo "4. Test GitHub integration (optional):"
    echo "   cp .env.example .env"
    echo "   # Add your GITHUB_TOKEN"
    echo "   (In Claude Code) \"Check current sprint status\""
    echo ""
    echo "5. Cleanup when done:"
    echo "   rm -rf $TEST_PROJECT"
    echo ""
    exit 0
else
    echo -e "${RED}❌ SOME TESTS FAILED${NC}"
    echo ""
    echo "Please review the failed tests above and ensure all files are present."
    echo ""
    exit 1
fi
