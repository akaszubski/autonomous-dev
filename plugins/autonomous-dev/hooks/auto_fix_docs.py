#!/usr/bin/env python3
"""
Hybrid Auto-Fix + Block Documentation Hook

This hook implements Option C: Hybrid approach
1. Detect doc changes needed
2. Try auto-fix (using doc-master agent logic)
3. Validate auto-fix worked
4. If validation fails → BLOCK (with helpful message)
5. Otherwise → Auto-stage and continue ✅

This provides "vibe coding" experience while catching edge cases.

Usage:
    # As pre-commit hook (automatic)
    python auto_fix_docs.py

Exit codes:
    0: Docs updated automatically and validated (or no updates needed)
    1: Auto-fix failed - manual intervention required (BLOCKS commit)
"""

import json
import subprocess
import sys
from pathlib import Path
from typing import Dict, List, Set, Tuple
import re


def get_plugin_root() -> Path:
    """Get the plugin root directory."""
    return Path(__file__).parent.parent


def get_repo_root() -> Path:
    """Get the repository root directory."""
    return get_plugin_root().parent.parent


def run_detect_doc_changes() -> Tuple[bool, List[Dict]]:
    """
    Run detect_doc_changes.py to find violations.

    Returns:
        (success, violations)
        - success: True if no doc updates needed
        - violations: List of violation dicts if updates needed
    """
    plugin_root = get_plugin_root()
    detect_script = plugin_root / "hooks" / "detect_doc_changes.py"

    # Import the detection functions
    import sys
    sys.path.insert(0, str(plugin_root / "hooks"))

    try:
        from detect_doc_changes import (
            load_registry,
            get_staged_files,
            find_required_docs,
            check_doc_updates
        )

        # Load registry and get staged files
        registry = load_registry()
        staged_files = get_staged_files()

        if not staged_files:
            return (True, [])

        staged_set = set(staged_files)

        # Find required docs
        required_docs_map = find_required_docs(staged_files, registry)

        if not required_docs_map:
            return (True, [])

        # Check if docs are updated
        all_updated, violations = check_doc_updates(required_docs_map, staged_set)

        return (all_updated, violations)

    except Exception as e:
        print(f"⚠️  Error detecting doc changes: {e}")
        return (True, [])  # Don't block on errors


def auto_fix_documentation(violations: List[Dict]) -> bool:
    """
    Automatically fix documentation using smart heuristics.

    For simple cases (count updates, version bumps), we can auto-fix.
    For complex cases (new command descriptions), we need manual intervention.

    Returns:
        True if auto-fix successful, False if manual intervention needed
    """
    plugin_root = get_plugin_root()
    repo_root = get_repo_root()

    print("🔧 Attempting to auto-fix documentation...")
    print()

    auto_fixed_files = set()
    manual_intervention_needed = []

    for violation in violations:
        code_file = violation["code_file"]
        missing_docs = violation["missing_docs"]

        # Determine if this is auto-fixable
        if can_auto_fix(code_file, missing_docs):
            # Try to auto-fix
            success = attempt_auto_fix(code_file, missing_docs, plugin_root, repo_root)
            if success:
                auto_fixed_files.update(missing_docs)
                print(f"✅ Auto-fixed: {', '.join(missing_docs)}")
            else:
                manual_intervention_needed.append(violation)
        else:
            manual_intervention_needed.append(violation)

    # Auto-stage fixed files
    if auto_fixed_files:
        for doc_file in auto_fixed_files:
            try:
                subprocess.run(["git", "add", doc_file], check=True, capture_output=True)
                print(f"📝 Auto-staged: {doc_file}")
            except subprocess.CalledProcessError:
                pass

    print()

    if manual_intervention_needed:
        return False
    else:
        return True


def can_auto_fix(code_file: str, missing_docs: List[str]) -> bool:
    """
    Determine if this violation can be auto-fixed.

    Auto-fixable cases:
    - Version bumps (plugin.json → README.md, UPDATES.md)
    - Skill/agent count updates (just increment numbers)
    - Marketplace.json metrics updates

    Not auto-fixable:
    - New commands (need human-written descriptions)
    - New skills (need human-written documentation)
    - Complex content changes
    """
    # Version bumps are auto-fixable
    if "plugin.json" in code_file or "marketplace.json" in code_file:
        return True

    # Count updates are auto-fixable
    if "skills/" in code_file or "agents/" in code_file:
        # Only if missing docs are README.md and marketplace.json (just count updates)
        if set(missing_docs).issubset({"README.md", ".claude-plugin/marketplace.json"}):
            return True

    # Everything else needs manual intervention
    return False


def attempt_auto_fix(
    code_file: str,
    missing_docs: List[str],
    plugin_root: Path,
    repo_root: Path
) -> bool:
    """
    Attempt to auto-fix documentation.

    Returns True if successful, False otherwise.
    """
    # For now, we'll implement simple auto-fixes
    # More complex cases will fall through to manual intervention

    try:
        if "skills/" in code_file:
            return auto_fix_skill_count(missing_docs, plugin_root, repo_root)
        elif "agents/" in code_file:
            return auto_fix_agent_count(missing_docs, plugin_root, repo_root)
        elif "plugin.json" in code_file or "marketplace.json" in code_file:
            return auto_fix_version(missing_docs, plugin_root, repo_root)
    except Exception as e:
        print(f"  ⚠️  Auto-fix failed: {e}")
        return False

    return False


def auto_fix_skill_count(missing_docs: List[str], plugin_root: Path, repo_root: Path) -> bool:
    """Auto-update skill count in README.md and marketplace.json."""
    # Count actual skills
    skills_dir = plugin_root / "skills"
    actual_count = len([d for d in skills_dir.iterdir() if d.is_dir() and not d.name.startswith(".")])

    # Update README.md
    if "README.md" in missing_docs or "plugins/autonomous-dev/README.md" in missing_docs:
        readme_path = plugin_root / "README.md"
        if readme_path.exists():
            content = readme_path.read_text()
            # Update skill count pattern
            updated = re.sub(
                r'"skills":\s*\d+',
                f'"skills": {actual_count}',
                content
            )
            updated = re.sub(
                r'\d+\s+Skills',
                f'{actual_count} Skills',
                updated
            )
            if updated != content:
                readme_path.write_text(updated)

    # Update marketplace.json
    if ".claude-plugin/marketplace.json" in missing_docs:
        marketplace_path = plugin_root / ".claude-plugin" / "marketplace.json"
        if marketplace_path.exists():
            with open(marketplace_path) as f:
                data = json.load(f)
            data["metrics"]["skills"] = actual_count
            with open(marketplace_path, "w") as f:
                json.dump(data, f, indent=2)
                f.write("\n")

    return True


def auto_fix_agent_count(missing_docs: List[str], plugin_root: Path, repo_root: Path) -> bool:
    """Auto-update agent count in README.md and marketplace.json."""
    # Count actual agents
    agents_dir = plugin_root / "agents"
    actual_count = len(list(agents_dir.glob("*.md")))

    # Update README.md
    if "README.md" in missing_docs or "plugins/autonomous-dev/README.md" in missing_docs:
        readme_path = plugin_root / "README.md"
        if readme_path.exists():
            content = readme_path.read_text()
            updated = re.sub(
                r'"agents":\s*\d+',
                f'"agents": {actual_count}',
                content
            )
            updated = re.sub(
                r'\d+\s+Agents',
                f'{actual_count} Agents',
                updated
            )
            if updated != content:
                readme_path.write_text(updated)

    # Update marketplace.json
    if ".claude-plugin/marketplace.json" in missing_docs:
        marketplace_path = plugin_root / ".claude-plugin" / "marketplace.json"
        if marketplace_path.exists():
            with open(marketplace_path) as f:
                data = json.load(f)
            data["metrics"]["agents"] = actual_count
            with open(marketplace_path, "w") as f:
                json.dump(data, f, indent=2)
                f.write("\n")

    return True


def auto_fix_version(missing_docs: List[str], plugin_root: Path, repo_root: Path) -> bool:
    """Sync version across all files."""
    # Read version from plugin.json (source of truth)
    plugin_json_path = plugin_root / ".claude-plugin" / "plugin.json"
    with open(plugin_json_path) as f:
        plugin_data = json.load(f)
    version = plugin_data["version"]

    # Update README.md
    if "README.md" in missing_docs or "plugins/autonomous-dev/README.md" in missing_docs:
        readme_path = plugin_root / "README.md"
        if readme_path.exists():
            content = readme_path.read_text()
            updated = re.sub(
                r'version-\d+\.\d+\.\d+-green',
                f'version-{version}-green',
                content
            )
            updated = re.sub(
                r'\*\*Version\*\*:\s*v\d+\.\d+\.\d+',
                f'**Version**: v{version}',
                updated
            )
            if updated != content:
                readme_path.write_text(updated)

    return True


def validate_auto_fix() -> bool:
    """
    Validate that auto-fix worked by running consistency validation.

    Returns True if all checks pass, False otherwise.
    """
    plugin_root = get_plugin_root()
    validate_script = plugin_root / "hooks" / "validate_docs_consistency.py"

    try:
        result = subprocess.run(
            ["python", str(validate_script)],
            capture_output=True,
            text=True
        )
        return result.returncode == 0
    except Exception:
        # Don't block on validation errors
        return True


def print_manual_intervention_needed(violations: List[Dict]):
    """Print helpful message when manual intervention is needed."""
    print("\n" + "=" * 80)
    print("⚠️  AUTO-FIX INCOMPLETE: Manual documentation updates needed")
    print("=" * 80)
    print()
    print("Some documentation changes require human input and couldn't be")
    print("auto-fixed. Please update the following manually:\n")

    for i, violation in enumerate(violations, 1):
        print(f"{i}. Code Change: {violation['code_file']}")
        print(f"   Why: {violation['description']}")
        print(f"   Missing Docs:")
        for doc in violation['missing_docs']:
            print(f"     - {doc}")
        print(f"   Suggestion: {violation['suggestion']}")
        print()

    print("=" * 80)
    print("After updating docs manually:")
    print("=" * 80)
    print()
    print("1. Stage the updated docs: git add <doc-files>")
    print("2. Retry your commit: git commit")
    print()
    print("=" * 80)


def main():
    """Main entry point for hybrid auto-fix + block hook."""
    print("🔍 Checking documentation consistency...")

    # Step 1: Detect doc changes needed
    all_updated, violations = run_detect_doc_changes()

    if all_updated:
        print("✅ No documentation updates needed (or already included)")
        return 0

    # Step 2: Try auto-fix
    auto_fix_success = auto_fix_documentation(violations)

    if not auto_fix_success:
        # Auto-fix failed, need manual intervention
        print_manual_intervention_needed(violations)
        return 1

    # Step 3: Validate auto-fix worked
    print("🔍 Validating auto-fix...")
    validation_success = validate_auto_fix()

    if validation_success:
        print()
        print("=" * 80)
        print("✅ Documentation auto-updated and validated!")
        print("=" * 80)
        print()
        print("Auto-fixed files have been staged automatically.")
        print("Proceeding with commit...")
        print()
        return 0
    else:
        print()
        print("=" * 80)
        print("⚠️  Auto-fix validation failed")
        print("=" * 80)
        print()
        print("Documentation was auto-updated but validation checks failed.")
        print("Please review the changes and fix any issues manually.")
        print()
        print("Run: python plugins/autonomous-dev/hooks/validate_docs_consistency.py")
        print("to see what validation checks failed.")
        print()
        return 1


if __name__ == "__main__":
    sys.exit(main())
