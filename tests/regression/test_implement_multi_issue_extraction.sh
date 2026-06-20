#!/bin/bash
# Regression test for multi-issue body extraction logic in /implement STEP 0
# Issue #1231: Verifies that the bash extraction logic correctly handles both
# single-issue and multi-issue inputs.

set -e

echo "Testing multi-issue extraction logic..."

# Test function that emulates the extraction logic from implement.md
test_extraction() {
    local ARGUMENTS="$1"
    local EXPECTED_COUNT="$2"
    local EXPECTED_NUMBERS="$3"
    
    # Extract all issue numbers (up to 10) - same logic as implement.md
    ISSUE_NUMBERS=$(echo "$ARGUMENTS" | grep -oE '#?([0-9]+)' | head -10 | tr -d '#')
    ISSUE_COUNT=$(echo "$ISSUE_NUMBERS" | wc -w)
    
    # Export first issue number for downstream compatibility
    ISSUE_NUMBER=$(echo "$ISSUE_NUMBERS" | head -1)
    
    # Verify count
    if [ "$ISSUE_COUNT" -ne "$EXPECTED_COUNT" ]; then
        echo "FAIL: Expected count $EXPECTED_COUNT but got $ISSUE_COUNT for input: $ARGUMENTS"
        echo "  Extracted numbers: $ISSUE_NUMBERS"
        return 1
    fi
    
    # Convert newlines to spaces for comparison
    ISSUE_NUMBERS_NORMALIZED=$(echo "$ISSUE_NUMBERS" | tr '\n' ' ' | sed 's/ *$//')
    
    # Verify extracted numbers match expected
    if [ "$ISSUE_NUMBERS_NORMALIZED" != "$EXPECTED_NUMBERS" ]; then
        echo "FAIL: Expected numbers '$EXPECTED_NUMBERS' but got '$ISSUE_NUMBERS_NORMALIZED' for input: $ARGUMENTS"
        return 1
    fi
    
    echo "PASS: '$ARGUMENTS' → count=$ISSUE_COUNT, numbers='$ISSUE_NUMBERS_NORMALIZED', first=$ISSUE_NUMBER"
    return 0
}

# Test cases
FAILED=0

# Single issue cases
test_extraction "#1231" 1 "1231" || FAILED=$((FAILED + 1))
test_extraction "1231" 1 "1231" || FAILED=$((FAILED + 1))
test_extraction "Fix issue #42" 1 "42" || FAILED=$((FAILED + 1))
test_extraction "Issue 999: broken test" 1 "999" || FAILED=$((FAILED + 1))

# Multi-issue cases
test_extraction "#1333 #1334 #1335" 3 "1333 1334 1335" || FAILED=$((FAILED + 1))
test_extraction "1333 1334 1335" 3 "1333 1334 1335" || FAILED=$((FAILED + 1))
test_extraction "Fix issues #100, #200, and #300" 3 "100 200 300" || FAILED=$((FAILED + 1))
test_extraction "#1 #2 #3 #4 #5" 5 "1 2 3 4 5" || FAILED=$((FAILED + 1))

# Edge case: exactly 10 issues (limit)
test_extraction "#1 #2 #3 #4 #5 #6 #7 #8 #9 #10" 10 "1 2 3 4 5 6 7 8 9 10" || FAILED=$((FAILED + 1))

# Edge case: more than 10 issues (should truncate to 10)
test_extraction "#1 #2 #3 #4 #5 #6 #7 #8 #9 #10 #11 #12" 10 "1 2 3 4 5 6 7 8 9 10" || FAILED=$((FAILED + 1))

# Mixed format
test_extraction "Issues: #123, 456, and #789" 3 "123 456 789" || FAILED=$((FAILED + 1))

# No issues
test_extraction "No issue numbers here" 0 "" || FAILED=$((FAILED + 1))

# Summary
echo ""
if [ $FAILED -eq 0 ]; then
    echo "✅ All tests passed!"
    exit 0
else
    echo "❌ $FAILED test(s) failed"
    exit 1
fi