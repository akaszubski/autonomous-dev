#!/usr/bin/env python3
"""
Validate repository structure - ensure clean separation of dev vs user content.

This script enforces the ROOT vs PLUGIN architecture:
- ROOT: Development/contributor content
- PLUGIN: User/distribution content

Run: python scripts/validate_structure.py
"""

import sys
from pathlib import Path
from typing import List, Tuple

# Root directory
ROOT = Path(__file__).parent.parent
PLUGIN = ROOT / "plugins" / "autonomous-dev"

# User-facing files that MUST be in plugin docs (by filename)
USER_DOC_FILES = {
    'QUICKSTART.md',
    'COMMANDS.md',
    'TROUBLESHOOTING.md',
    'GITHUB_AUTH_SETUP.md',
    'CUSTOMIZATION.md',
    'TEAM-ONBOARDING.md',
    'GITHUB-ISSUES-INTEGRATION.md',
    'GITHUB-WORKFLOW.md',
    'PR-AUTOMATION.md',
    'TESTING_GUIDE.md',
    'UPDATES.md',
    'commit-workflow.md',
    'COMMIT-WORKFLOW-COMPLETE.md',
    'AUTO-ISSUE-TRACKING.md',
    'COVERAGE-GUIDE.md',
    'SYSTEM-PERFORMANCE-GUIDE.md',
}

# Dev-facing files that MUST be in root docs (by filename)
DEV_DOC_FILES = {
    'CONTRIBUTING.md',
    'DEVELOPMENT.md',
    'CODE-REVIEW-WORKFLOW.md',
    'IMPLEMENTATION-STATUS.md',
    'ARCHITECTURE.md',
    'SESSION-LOGS.md',
}


def check_doc_locations() -> List[str]:
    """Check that docs are in the right place based on filenames."""
    errors = []

    # Check root docs/ - should NOT have user-facing files
    root_docs = ROOT / "docs"
    if root_docs.exists():
        for doc in root_docs.glob("**/*.md"):
            if doc.name in USER_DOC_FILES:
                rel_path = doc.relative_to(ROOT)
                errors.append(
                    f"❌ User-facing doc in ROOT: {rel_path}\n"
                    f"   → Should be in: plugins/autonomous-dev/docs/"
                )

    # Check plugin docs/ - should NOT have dev-facing files
    plugin_docs = PLUGIN / "docs"
    if plugin_docs.exists():
        for doc in plugin_docs.glob("**/*.md"):
            if doc.name in DEV_DOC_FILES:
                rel_path = doc.relative_to(ROOT)
                errors.append(
                    f"❌ Dev-facing doc in PLUGIN: {rel_path}\n"
                    f"   → Should be in: docs/"
                )

    # Check root level - should NOT have QUICKSTART.md
    root_quickstart = ROOT / "QUICKSTART.md"
    if root_quickstart.exists():
        errors.append(
            f"❌ User-facing doc at ROOT: QUICKSTART.md\n"
            f"   → Should be in: plugins/autonomous-dev/QUICKSTART.md"
        )

    return errors


def check_no_duplicates() -> List[str]:
    """Check for duplicate files between root and plugin."""
    errors = []
    
    # Check for duplicate doc names (excluding README.md, CHANGELOG.md)
    root_docs = set()
    if (ROOT / "docs").exists():
        root_docs = {f.name for f in (ROOT / "docs").glob("*.md")}
    
    plugin_docs = set()
    if (PLUGIN / "docs").exists():
        plugin_docs = {f.name for f in (PLUGIN / "docs").glob("*.md")}
    
    duplicates = root_docs & plugin_docs
    duplicates.discard("README.md")  # README can exist in both
    
    if duplicates:
        for dup in duplicates:
            errors.append(
                f"❌ Duplicate doc found: {dup}\n"
                f"   Exists in both docs/ and plugins/autonomous-dev/docs/\n"
                f"   → Keep only one version (root for dev, plugin for user)"
            )
    
    return errors


def check_root_cleanliness() -> List[str]:
    """Check that root only has essential files."""
    errors = []
    
    # Check for unexpected .md files in root
    essential_root_mds = {
        "README.md",
        "CHANGELOG.md",
        "CLAUDE.md",
        "CONTRIBUTING.md",
    }
    
    root_mds = {f.name for f in ROOT.glob("*.md")}
    unexpected = root_mds - essential_root_mds
    
    if unexpected:
        for md in unexpected:
            errors.append(
                f"❌ Unexpected .md in root: {md}\n"
                f"   → Move to docs/ or plugins/autonomous-dev/docs/"
            )
    
    return errors


def main() -> int:
    """Run all structure validations."""
    print("🔍 Validating repository structure...\n")
    
    all_errors = []
    
    # Run checks
    all_errors.extend(check_doc_locations())
    all_errors.extend(check_no_duplicates())
    all_errors.extend(check_root_cleanliness())
    
    # Report results
    if all_errors:
        print("❌ Structure validation FAILED\n")
        print("=" * 70)
        for error in all_errors:
            print(error)
            print("-" * 70)
        print(f"\nTotal errors: {len(all_errors)}")
        print("\nSee CONTRIBUTING.md for file location guidelines.")
        return 1
    else:
        print("✅ Structure validation PASSED")
        print("\nAll files are in the correct locations:")
        print("  ✓ User docs in plugins/autonomous-dev/docs/")
        print("  ✓ Dev docs in docs/")
        print("  ✓ No duplicates")
        print("  ✓ Clean root directory")
        return 0


if __name__ == "__main__":
    sys.exit(main())
