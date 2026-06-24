#!/usr/bin/env python3
"""
Validate repository structure - ensure dogfooding architecture.

This script enforces the DOGFOODING architecture:
- SOURCE: plugins/autonomous-dev/ (edit here, commit this)
- INSTALLED: .claude/ (installed from plugin, gitignored)
- DEV DOCS: docs/ (contributors only, not distributed)

Run: python scripts/validate_structure.py
"""

import re
import sys
from pathlib import Path
from typing import List, Tuple

# Root directory
ROOT = Path(__file__).parent.parent
PLUGIN = ROOT / "plugins" / "autonomous-dev"

# Issue #1140: paths and regex for component-count drift check
CLAUDE_MD = ROOT / "CLAUDE.md"
SUMMARY_RE = re.compile(
    r"Component counts:\s*"
    r"(?P<agents>\d+)\s+agents,\s*"
    r"(?P<skills>\d+)\s+skills,\s*"
    r"(?P<commands>\d+)\s+(?:user-facing\s+)?commands,\s*"
    r"(?P<hooks>\d+)\s+hooks,\s*"
    r"(?P<libraries>\d+)\s+libraries"
)

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
    'ARCHITECTURE-OVERVIEW.md',
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
        "PROJECT.md",  # Project-level strategic direction (not tool-specific)
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


def check_claude_not_tracked() -> List[str]:
    """Check that .claude/ automations are not tracked in git."""
    errors = []

    # These should be gitignored (installed, not source)
    should_be_gitignored = [
        '.claude/commands/',
        '.claude/agents/',
        '.claude/skills/',
        '.claude/hooks/',
        '.claude/templates/',
    ]

    import subprocess

    for path in should_be_gitignored:
        try:
            # Check if any files in this path are tracked
            result = subprocess.run(
                ['git', 'ls-files', path],
                capture_output=True,
                text=True,
                check=False
            )
            if result.stdout.strip():
                tracked_files = result.stdout.strip().split('\n')
                errors.append(
                    f"❌ .claude/ automation tracked in git: {path}\n"
                    f"   Found {len(tracked_files)} tracked files\n"
                    f"   → These should be gitignored (installed from plugin)\n"
                    f"   → Source is in plugins/autonomous-dev/"
                )
        except Exception:
            pass  # git command failed, skip

    return errors


def _count_agents() -> int:
    """Count agent markdown files (flat, no dotfiles)."""
    return len(
        [
            f
            for f in (PLUGIN / "agents").iterdir()
            if f.is_file() and f.suffix == ".md" and not f.name.startswith(".")
        ]
    )


def _count_commands() -> int:
    """Count command markdown files (flat, no dotfiles)."""
    return len(
        [
            f
            for f in (PLUGIN / "commands").iterdir()
            if f.is_file() and f.suffix == ".md" and not f.name.startswith(".")
        ]
    )


def _count_user_facing_commands() -> int:
    """Count command markdown files whose front-matter contains user_facing: true.

    Front-matter is the YAML block at the top between two --- lines. This counter
    matches the 'X user-facing commands' qualifier used in CLAUDE.md (added by
    master commit 5c88ef7 / #1159). Returns 0 on parse errors per file (tolerant).
    """
    commands_dir = PLUGIN / "commands"
    count = 0
    for f in commands_dir.iterdir():
        if not (f.is_file() and f.suffix == ".md" and not f.name.startswith(".")):
            continue
        try:
            content = f.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        if not content.startswith("---"):
            continue
        end = content.find("\n---", 3)
        if end <= 0:
            continue
        front_matter = content[3:end]
        if re.search(r"^user_facing:\s*true\s*$", front_matter, re.MULTILINE):
            count += 1
    return count


def _count_skills() -> int:
    """Count real skills: subdirectories with a SKILL.md sentinel, excluding 'archived/'."""
    skills_dir = PLUGIN / "skills"
    return sum(
        1
        for d in skills_dir.iterdir()
        if d.is_dir() and d.name != "archived" and (d / "SKILL.md").exists()
    )


def _count_hooks() -> int:
    """Count hook Python files (flat, excluding __init__.py)."""
    return len(
        [
            f
            for f in (PLUGIN / "hooks").iterdir()
            if f.is_file() and f.suffix == ".py" and f.name != "__init__.py"
        ]
    )


def _count_libraries() -> int:
    """Count library Python files recursively, excluding __pycache__, htmlcov, __init__.py."""
    lib_dir = PLUGIN / "lib"
    return sum(
        1
        for f in lib_dir.rglob("*.py")
        if f.is_file()
        and "__pycache__" not in f.parts
        and "htmlcov" not in f.parts
        and f.name != "__init__.py"
    )


def check_component_count_drift() -> List[str]:
    """Check CLAUDE.md prose component counts against live file counts (Issue #1140).

    Returns:
        List of error strings (empty if all counts match).
    """
    errors: List[str] = []
    if not CLAUDE_MD.exists():
        return ["❌ CLAUDE.md missing — cannot verify component counts"]
    text = CLAUDE_MD.read_text()
    m = SUMMARY_RE.search(text)
    if not m:
        return [
            "❌ Canonical 'Component counts:' summary line missing or malformed in CLAUDE.md"
        ]
    claimed = {k: int(m.group(k)) for k in ("agents", "skills", "commands", "hooks", "libraries")}
    # Detect whether CLAUDE.md uses the "user-facing" qualifier for commands (#1159).
    # When it does, compare against only files with user_facing: true in front-matter.
    uses_user_facing = "user-facing" in m.group(0)
    actual_commands = _count_user_facing_commands() if uses_user_facing else _count_commands()
    actual = {
        "agents": _count_agents(),
        "skills": _count_skills(),
        "commands": actual_commands,
        "hooks": _count_hooks(),
        "libraries": _count_libraries(),
    }
    for name in ("agents", "skills", "commands", "hooks", "libraries"):
        if claimed[name] != actual[name]:
            errors.append(
                f"❌ Component count drift: '{name}' claims {claimed[name]} in CLAUDE.md,"
                f" actual is {actual[name]}"
            )
    return errors


def main() -> int:
    """Run all structure validations."""
    print("🔍 Validating dogfooding architecture...\n")

    all_errors = []

    # Run checks
    all_errors.extend(check_doc_locations())
    all_errors.extend(check_no_duplicates())
    all_errors.extend(check_root_cleanliness())
    all_errors.extend(check_claude_not_tracked())
    all_errors.extend(check_component_count_drift())

    # Report results
    if all_errors:
        print("❌ Structure validation FAILED\n")
        print("=" * 70)
        for error in all_errors:
            print(error)
            print("-" * 70)
        print(f"\nTotal errors: {len(all_errors)}")
        print("\nSee docs/DOGFOODING-ARCHITECTURE.md for guidelines.")
        return 1
    else:
        print("✅ Structure validation PASSED")
        print("\nDogfooding architecture correct:")
        print("  ✓ Plugin source in plugins/autonomous-dev/")
        print("  ✓ User docs in plugins/autonomous-dev/docs/")
        print("  ✓ Dev docs in docs/")
        print("  ✓ .claude/ automations gitignored (installed)")
        print("  ✓ No duplicates")
        print("  ✓ Clean root directory")
        print("  ✓ Component counts in CLAUDE.md match live file counts")
        return 0


if __name__ == "__main__":
    sys.exit(main())
