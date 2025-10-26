#!/bin/bash
# Cleanup script - resets all test projects to initial state

echo "🧹 Cleaning up test projects..."

# Test 1: Remove generated PROJECT.md
if [ -f "test1-simple-api/PROJECT.md" ]; then
    echo "  Removing test1-simple-api/PROJECT.md"
    rm -f test1-simple-api/PROJECT.md
fi

# Test 2: No cleanup needed (PROJECT.md is part of test)
echo "  test2-translation-service: No cleanup needed"

# Test 3: Reset file organization (if files were moved)
cd test3-messy-project

# Move files back to root if they were organized
if [ -f "scripts/test/test-auth.sh" ]; then
    echo "  Moving files back to root in test3-messy-project"
    mv scripts/test/test-auth.sh . 2>/dev/null || true
    mv scripts/debug/debug-local.sh . 2>/dev/null || true
    mv docs/guides/user-guide.md ./USER-GUIDE.md 2>/dev/null || true
    mv docs/architecture/ARCHITECTURE.md . 2>/dev/null || true
    mv docs/debugging/debug-guide.md ./DEBUG-GUIDE.md 2>/dev/null || true
    mv docs/reference/api-reference.md ./API-REFERENCE.md 2>/dev/null || true
    mv src/helper.ts . 2>/dev/null || true
    mv src/utils.ts . 2>/dev/null || true

    # Remove empty directories
    rm -rf scripts docs src 2>/dev/null || true
fi

cd - > /dev/null

# Test 4: Reset documentation (if references were fixed)
cd test4-broken-refs

# Check if references were updated
if grep -q "scripts/debug/debug-local.sh" README.md 2>/dev/null; then
    echo "  Resetting references in test4-broken-refs"

    # Replace updated references back to broken ones
    find . -name "*.md" -type f -exec sed -i.bak 's|scripts/debug/debug-local\.sh|./debug-local.sh|g' {} \;
    find . -name "*.md" -type f -exec sed -i.bak 's|docs/debugging/DEBUG-GUIDE\.md|docs/DEBUG-GUIDE.md|g' {} \;

    # Remove backup files
    find . -name "*.bak" -delete
fi

cd - > /dev/null

# Remove git repos if created for testing
for dir in test1-simple-api test2-translation-service test3-messy-project test4-broken-refs; do
    if [ -d "$dir/.git" ]; then
        echo "  Removing .git from $dir"
        rm -rf "$dir/.git"
    fi
done

echo "✅ Cleanup complete"
echo ""
echo "Test projects reset to initial state"
echo "Ready for re-testing"
