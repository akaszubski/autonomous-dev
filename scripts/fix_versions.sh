#!/bin/bash
# Fix all version inconsistencies to match VERSION file

set -e

echo "🔧 Fixing Version Inconsistencies"
echo "=================================="
echo ""

# Read target version from VERSION file
TARGET_VERSION=$(head -1 VERSION)
echo "Target version from VERSION file: $TARGET_VERSION"
echo ""

# Track what we fix
FIXED_COUNT=0

# Function to fix version in file
fix_version() {
    local file="$1"
    local pattern="$2"
    local replacement="$3"

    if grep -q "$pattern" "$file" 2>/dev/null; then
        echo "  Fixing: $file"
        sed -i.bak "s/$pattern/$replacement/g" "$file"
        rm "$file.bak"
        ((FIXED_COUNT++))
    fi
}

echo "1️⃣  Fixing agents (v2.0 → v$TARGET_VERSION)..."
echo "-------------------------------------------"
for agent in plugins/autonomous-dev/agents/*.md; do
    fix_version "$agent" "autonomous-dev v2\.0" "autonomous-dev v$TARGET_VERSION"
    fix_version "$agent" "(v2\.0)" "(v$TARGET_VERSION)"
    fix_version "$agent" "v2\.0 artifact" "v$TARGET_VERSION artifact"
done
echo ""

echo "2️⃣  Fixing README.md..."
echo "-------------------------------------------"
fix_version "plugins/autonomous-dev/README.md" "version-2\.3\.1" "version-$TARGET_VERSION"
fix_version "plugins/autonomous-dev/README.md" "v2\.3\.1" "v$TARGET_VERSION"
fix_version "plugins/autonomous-dev/README.md" "v2\.2\.0" "v$TARGET_VERSION"
fix_version "README.md" "version-2\.3\.1" "version-$TARGET_VERSION"
fix_version "README.md" "v2\.3\.1" "v$TARGET_VERSION"
fix_version "README.md" "v2\.2\.0" "v$TARGET_VERSION"
echo ""

echo "3️⃣  Fixing documentation..."
echo "-------------------------------------------"
fix_version "plugins/autonomous-dev/docs/GITHUB-WORKFLOW.md" "v2\.2\.0" "v$TARGET_VERSION"
fix_version "plugins/autonomous-dev/docs/TEAM-ONBOARDING.md" "v2\.2\.0" "v$TARGET_VERSION"
fix_version "plugins/autonomous-dev/docs/UPDATES.md" "v2\.3\.1" "v$TARGET_VERSION"
fix_version "plugins/autonomous-dev/docs/UPDATES.md" "v2\.3\.0" "v$TARGET_VERSION"
fix_version "plugins/autonomous-dev/docs/UPDATES.md" "v2\.2\.0" "v$TARGET_VERSION"
fix_version "plugins/autonomous-dev/INSTALL_TEMPLATE.md" "v2\.0\.0" "v$TARGET_VERSION"
echo ""

echo "4️⃣  Fixing doc-master agent (special case)..."
echo "-------------------------------------------"
fix_version "plugins/autonomous-dev/agents/doc-master.md" "v2\.3\.0" "v$TARGET_VERSION"
echo ""

echo "✅ Version Fix Summary"
echo "=================================="
echo "Target version: $TARGET_VERSION"
echo "Files updated: $FIXED_COUNT"
echo ""

# Verify
echo "🔍 Verification - Remaining version inconsistencies:"
echo "-------------------------------------------"
REMAINING=$(grep -r "v2\.[0-9]\+\.[0-9]\+" plugins/autonomous-dev/ README.md --include="*.md" 2>/dev/null | grep -v "v$TARGET_VERSION" | grep -v "example" | grep -v "1.2.0" | grep -v "2.8.0" || echo "None found!")
if [ "$REMAINING" = "None found!" ]; then
    echo "✅ All versions consistent!"
else
    echo "$REMAINING"
fi
echo ""

echo "Done! All plugin versions should now be v$TARGET_VERSION"
