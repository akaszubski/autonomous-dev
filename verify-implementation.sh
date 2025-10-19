#!/bin/bash
# verify-implementation.sh

echo "🔍 Verifying claude-code-bootstrap implementation..."
echo ""

# Color codes
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

PASSED=0
FAILED=0

# Function to check file exists
check_file() {
    if [ -f "$1" ]; then
        echo -e "${GREEN}✅${NC} $1"
        ((PASSED++))
        return 0
    else
        echo -e "${RED}❌${NC} $1 - MISSING"
        ((FAILED++))
        return 1
    fi
}

# Function to check content exists in file
check_content() {
    if grep -q "$2" "$1" 2>/dev/null; then
        echo -e "${GREEN}✅${NC} $1 contains '$2'"
        ((PASSED++))
        return 0
    else
        echo -e "${RED}❌${NC} $1 missing '$2'"
        ((FAILED++))
        return 1
    fi
}

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "📁 CRITICAL FILES"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
check_file "plugins/autonomous-dev/agents/orchestrator.md"
check_file "plugins/autonomous-dev/CLAUDE.md.template"
check_file "plugins/autonomous-dev/commands/auto-implement.md"
check_file "plugins/autonomous-dev/.claude-plugin/plugin.json"
check_file ".claude/PROJECT.md"
check_file "scripts/session_tracker.py"

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "🤖 ALL 8 AGENTS"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
check_file "plugins/autonomous-dev/agents/orchestrator.md"
check_file "plugins/autonomous-dev/agents/planner.md"
check_file "plugins/autonomous-dev/agents/researcher.md"
check_file "plugins/autonomous-dev/agents/test-master.md"
check_file "plugins/autonomous-dev/agents/implementer.md"
check_file "plugins/autonomous-dev/agents/reviewer.md"
check_file "plugins/autonomous-dev/agents/security-auditor.md"
check_file "plugins/autonomous-dev/agents/doc-master.md"

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "📝 ORCHESTRATOR CONTENT"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
if [ -f "plugins/autonomous-dev/agents/orchestrator.md" ]; then
    check_content "plugins/autonomous-dev/agents/orchestrator.md" "PROJECT.md Alignment"
    check_content "plugins/autonomous-dev/agents/orchestrator.md" "Stage 1: Research"
    check_content "plugins/autonomous-dev/agents/orchestrator.md" "Stage 2: TDD"
    check_content "plugins/autonomous-dev/agents/orchestrator.md" "Stage 3: Quality"
    check_content "plugins/autonomous-dev/agents/orchestrator.md" "/clear"
    check_content "plugins/autonomous-dev/agents/orchestrator.md" "session_tracker"
else
    echo -e "${RED}❌${NC} orchestrator.md doesn't exist - skipping content checks"
    ((FAILED+=6))
fi

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "🔧 PLUGIN.JSON"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
if [ -f "plugins/autonomous-dev/.claude-plugin/plugin.json" ]; then
    # Check if using directory auto-discovery or explicit list
    if grep -q '"agents": "./agents"' "plugins/autonomous-dev/.claude-plugin/plugin.json"; then
        echo -e "${GREEN}✅${NC} plugin.json uses directory auto-discovery (includes all agents)"
        ((PASSED++))
    elif grep -q "orchestrator" "plugins/autonomous-dev/.claude-plugin/plugin.json"; then
        echo -e "${GREEN}✅${NC} plugin.json explicitly lists orchestrator"
        ((PASSED++))
    else
        echo -e "${RED}❌${NC} plugin.json missing orchestrator"
        ((FAILED++))
    fi

    # Count agents if explicitly listed (skip if using auto-discovery)
    if ! grep -q '"agents": "./agents"' "plugins/autonomous-dev/.claude-plugin/plugin.json"; then
        AGENT_COUNT=$(grep -o "agents/" "plugins/autonomous-dev/.claude-plugin/plugin.json" | wc -l)
        if [ "$AGENT_COUNT" -eq 8 ]; then
            echo -e "${GREEN}✅${NC} plugin.json lists 8 agents"
            ((PASSED++))
        else
            echo -e "${RED}❌${NC} plugin.json lists $AGENT_COUNT agents (should be 8)"
            ((FAILED++))
        fi
    fi
else
    echo -e "${RED}❌${NC} plugin.json doesn't exist"
    ((FAILED+=2))
fi

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "📖 README UPDATES"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
check_content "README.md" "8 specialized agents"
check_content "README.md" "orchestrator"
check_content "README.md" "/clear"

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "🎯 TOOL RESTRICTIONS"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
for agent in plugins/autonomous-dev/agents/*.md; do
    if [ -f "$agent" ]; then
        if grep -q "tools:" "$agent" || grep -q "allowed-tools:" "$agent"; then
            echo -e "${GREEN}✅${NC} $(basename $agent) has tool restrictions"
            ((PASSED++))
        else
            echo -e "${RED}❌${NC} $(basename $agent) missing tool restrictions"
            ((FAILED++))
        fi
    fi
done

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "📊 SUMMARY"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo -e "Passed: ${GREEN}$PASSED${NC}"
echo -e "Failed: ${RED}$FAILED${NC}"
echo ""

if [ $FAILED -eq 0 ]; then
    echo -e "${GREEN}🎉 ALL CHECKS PASSED!${NC}"
    echo ""
    echo "Your system is production-ready with:"
    echo "  ✅ Orchestrator agent (master coordinator)"
    echo "  ✅ PROJECT.md validation"
    echo "  ✅ Session tracking (context management)"
    echo "  ✅ Tool restrictions (security)"
    echo "  ✅ /auto-implement command"
    echo "  ✅ All 8 agents configured"
    echo ""
    echo "Next steps:"
    echo "  1. Update README with '8 specialized agents' (if not done)"
    echo "  2. Test: /plugin install ./plugins/autonomous-dev"
    echo "  3. Test: /auto-implement health check endpoint"
    echo "  4. Tag release: git tag v1.0.0"
    exit 0
else
    echo -e "${RED}⚠️  ISSUES FOUND${NC}"
    echo ""
    echo "Please fix the failed checks above."
    echo "Most critical:"
    echo "  - orchestrator.md must exist"
    echo "  - plugin.json must list orchestrator"
    echo "  - README must mention 8 agents"
    exit 1
fi