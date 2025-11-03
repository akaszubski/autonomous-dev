#!/bin/bash
# UAT Test for Autonomous Workflow
# Tests that the full /auto-implement workflow actually works
# Usage: ./scripts/test-autonomous-workflow.sh

set -e

echo "════════════════════════════════════════════════════════════════"
echo "🧪 AUTONOMOUS WORKFLOW UAT TEST"
echo "════════════════════════════════════════════════════════════════"
echo ""
echo "This will test that:"
echo "  1. orchestrator runs and validates PROJECT.md"
echo "  2. Agents are invoked in correct order"
echo "  3. TDD is enforced (test-master before implementer)"
echo "  4. Hooks validate correctly"
echo "  5. Session logs contain evidence"
echo ""
echo "════════════════════════════════════════════════════════════════"
echo ""

# Track test results
TESTS_PASSED=0
TESTS_FAILED=0
FAILURES=""

# Helper function for test assertions
assert_true() {
    local description="$1"
    local condition="$2"

    echo -n "Testing: $description ... "

    if eval "$condition"; then
        echo "✅ PASS"
        TESTS_PASSED=$((TESTS_PASSED + 1))
    else
        echo "❌ FAIL"
        TESTS_FAILED=$((TESTS_FAILED + 1))
        FAILURES="${FAILURES}\n  - $description"
    fi
}

# Helper to check session file exists
session_exists() {
    local agent="$1"
    local count=$(find docs/sessions -name "*${agent}*.md" -mmin -10 | wc -l)
    [ "$count" -gt 0 ]
}

# Helper to check agent order in sessions
agent_before() {
    local agent1="$1"
    local agent2="$2"

    # Find most recent sessions for each agent
    local session1=$(find docs/sessions -name "*${agent1}*.md" -mmin -10 | head -1)
    local session2=$(find docs/sessions -name "*${agent2}*.md" -mmin -10 | head -1)

    if [ -z "$session1" ] || [ -z "$session2" ]; then
        return 1
    fi

    # Compare modification times (agent1 should be older/earlier)
    [ "$session1" -ot "$session2" ]
}

echo "════════════════════════════════════════════════════════════════"
echo "📋 PRE-TEST CHECKS"
echo "════════════════════════════════════════════════════════════════"
echo ""

# Check PROJECT.md exists
assert_true "PROJECT.md exists" "[ -f .claude/PROJECT.md ]"

# Check orchestrator agent exists
assert_true "orchestrator agent exists" "[ -f plugins/autonomous-dev/agents/orchestrator.md ]"

# Check test-master agent exists
assert_true "test-master agent exists" "[ -f plugins/autonomous-dev/agents/test-master.md ]"

# Check implementer agent exists
assert_true "implementer agent exists" "[ -f plugins/autonomous-dev/agents/implementer.md ]"

# Check enforce_tdd hook exists
assert_true "enforce_tdd.py hook exists" "[ -f plugins/autonomous-dev/hooks/enforce_tdd.py ]"

# Check session directory exists
assert_true "Session directory exists" "[ -d docs/sessions ]"

echo ""
echo "════════════════════════════════════════════════════════════════"
echo "🔍 WORKFLOW EXECUTION TEST"
echo "════════════════════════════════════════════════════════════════"
echo ""

echo "NOTE: This requires manual execution of /auto-implement"
echo ""
echo "Please run the following in Claude Code:"
echo ""
echo "  /auto-implement \"add a /health endpoint that returns JSON with status: ok\""
echo ""
echo "Then check the results below..."
echo ""
read -p "Press Enter when /auto-implement has completed (or Ctrl+C to skip)..."

echo ""
echo "════════════════════════════════════════════════════════════════"
echo "📊 POST-EXECUTION VALIDATION"
echo "════════════════════════════════════════════════════════════════"
echo ""

# Check orchestrator ran
assert_true "orchestrator session created (last 10 min)" "session_exists orchestrator"

# Check test-master ran
assert_true "test-master session created (last 10 min)" "session_exists test-master"

# Check implementer ran
assert_true "implementer session created (last 10 min)" "session_exists implementer"

# Check TDD order (test-master before implementer)
assert_true "TDD enforced: test-master ran before implementer" "agent_before test-master implementer"

# Check session files are not empty
if session_exists orchestrator; then
    ORCHESTRATOR_SESSION=$(find docs/sessions -name "*orchestrator*.md" -mmin -10 | head -1)
    assert_true "orchestrator session not empty" "[ -s \"$ORCHESTRATOR_SESSION\" ]"

    # Check orchestrator validated PROJECT.md
    assert_true "orchestrator mentions PROJECT.md" "grep -qi 'PROJECT.md' \"$ORCHESTRATOR_SESSION\""
fi

# Check hooks directory exists
assert_true "Hooks directory exists" "[ -d plugins/autonomous-dev/hooks ]"

# Count recent sessions (should have multiple agents)
RECENT_SESSIONS=$(find docs/sessions -name "*.md" -mmin -10 | wc -l)
echo ""
echo "Recent sessions created (last 10 min): $RECENT_SESSIONS"
if [ "$RECENT_SESSIONS" -ge 3 ]; then
    echo "✅ Multiple agents invoked (good sign)"
    TESTS_PASSED=$((TESTS_PASSED + 1))
else
    echo "⚠️  Only $RECENT_SESSIONS sessions found (expected 3+)"
    TESTS_FAILED=$((TESTS_FAILED + 1))
    FAILURES="${FAILURES}\n  - Expected 3+ agent sessions, found $RECENT_SESSIONS"
fi

echo ""
echo "════════════════════════════════════════════════════════════════"
echo "📈 TEST SUMMARY"
echo "════════════════════════════════════════════════════════════════"
echo ""
echo "Tests Passed: $TESTS_PASSED"
echo "Tests Failed: $TESTS_FAILED"
echo ""

if [ $TESTS_FAILED -eq 0 ]; then
    echo "✅ ALL TESTS PASSED"
    echo ""
    echo "The autonomous workflow is functioning correctly!"
    echo ""
    echo "Next steps:"
    echo "  1. View session details: ./scripts/view-last-session.sh orchestrator"
    echo "  2. Check agent order: ls -lt docs/sessions/*.md | head -10"
    echo "  3. Use for real features!"
    exit 0
else
    echo "❌ SOME TESTS FAILED"
    echo ""
    echo "Failures:"
    echo -e "$FAILURES"
    echo ""
    echo "Debugging:"
    echo "  1. Check session logs: ls -lt docs/sessions/"
    echo "  2. View latest session: ./scripts/view-last-session.sh"
    echo "  3. Check if auto-orchestration enabled: cat .claude/settings.local.json"
    echo "  4. Check PROJECT.md: cat .claude/PROJECT.md | head -50"
    exit 1
fi
