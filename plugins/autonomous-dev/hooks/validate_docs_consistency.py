#!/usr/bin/env python3
"""
Documentation Consistency Validation Hook - Layer 3 Defense

This pre-commit hook validates that documentation stays in sync with code.
It's OPTIONAL - can be annoying to block commits, but catches drift early.

Enable via:
    .claude/settings.local.json:
    {
      "hooks": {
        "PreCommit": {
          "*": ["python .claude/hooks/validate_docs_consistency.py"]
        }
      }
    }

Or via git pre-commit hook:
    ln -s ../../.claude/hooks/validate_docs_consistency.py .git/hooks/pre-commit

What it checks:
- README.md skill/agent/command counts match reality
- Cross-document consistency (SYNC-STATUS, UPDATES, marketplace.json)
- No references to non-existent skills
- marketplace.json metrics match actual counts
- No deprecated procedural instructions (e.g., 'python setup.py' → '/setup')

Exit codes:
- 0: All checks passed
- 1: Documentation inconsistency detected (blocks commit)
"""

import sys
import json
import re
from pathlib import Path
from typing import List, Tuple


def get_plugin_root() -> Path:
    """Find plugin root directory."""
    current = Path(__file__).parent.parent
    # Verify we're in the plugin directory
    if (current / "agents").exists() and (current / "skills").exists():
        return current
    # Try parent directory (if running from project)
    if (current.parent / "plugins" / "autonomous-dev").exists():
        return current.parent / "plugins" / "autonomous-dev"
    # Give up
    raise FileNotFoundError("Could not find plugin root directory")


def count_skills(plugin_root: Path) -> int:
    """Count actual skills in skills/ directory."""
    skills_dir = plugin_root / "skills"
    return len([
        d for d in skills_dir.iterdir()
        if d.is_dir() and not d.name.startswith(".")
    ])


def count_agents(plugin_root: Path) -> int:
    """Count actual agents in agents/ directory."""
    agents_dir = plugin_root / "agents"
    return len([
        f for f in agents_dir.iterdir()
        if f.is_file() and f.suffix == ".md" and not f.name.startswith(".")
    ])


def count_commands(plugin_root: Path) -> int:
    """Count actual commands in commands/ directory."""
    commands_dir = plugin_root / "commands"
    return len([
        f for f in commands_dir.iterdir()
        if f.is_file() and f.suffix == ".md" and not f.name.startswith(".")
    ])


def check_readme_skill_count(plugin_root: Path, actual_count: int) -> Tuple[bool, str]:
    """Check README.md skill count matches actual."""
    readme_path = plugin_root / "README.md"
    if not readme_path.exists():
        return False, "README.md not found"

    content = readme_path.read_text()
    pattern = rf"\b{actual_count}\s+[Ss]kills"

    if not re.search(pattern, content):
        return False, (
            f"README.md shows incorrect skill count (expected {actual_count})\n"
            f"Fix: Update README.md to show '{actual_count} Skills (Comprehensive SDLC Coverage)'"
        )

    return True, "✅ README.md skill count correct"


def check_readme_agent_count(plugin_root: Path, actual_count: int) -> Tuple[bool, str]:
    """Check README.md agent count matches actual."""
    readme_path = plugin_root / "README.md"
    content = readme_path.read_text()
    pattern = rf"\b{actual_count}\s+[Ss]pecialized\s+[Aa]gents|\b{actual_count}\s+[Aa]gents"

    if not re.search(pattern, content):
        return False, (
            f"README.md shows incorrect agent count (expected {actual_count})\n"
            f"Fix: Update README.md to show '{actual_count} Specialized Agents'"
        )

    return True, "✅ README.md agent count correct"


def check_readme_command_count(plugin_root: Path, actual_count: int) -> Tuple[bool, str]:
    """Check README.md command count matches actual."""
    readme_path = plugin_root / "README.md"
    content = readme_path.read_text()
    pattern = rf"\b{actual_count}\s+[Ss]lash\s+[Cc]ommands|\b{actual_count}\s+[Cc]ommands"

    if not re.search(pattern, content):
        return False, (
            f"README.md shows incorrect command count (expected {actual_count})\n"
            f"Fix: Update README.md to show '{actual_count} Slash Commands'"
        )

    return True, "✅ README.md command count correct"


def check_marketplace_json(plugin_root: Path, skill_count: int, agent_count: int, command_count: int) -> Tuple[bool, str]:
    """Check marketplace.json metrics match actual counts."""
    marketplace_path = plugin_root / ".claude-plugin" / "marketplace.json"
    if not marketplace_path.exists():
        return True, "⚠️  marketplace.json not found (skipping)"

    try:
        data = json.loads(marketplace_path.read_text())
        metrics = data.get("metrics", {})

        errors = []
        if metrics.get("skills") != skill_count:
            errors.append(f"skills: {metrics.get('skills')} (should be {skill_count})")
        if metrics.get("agents") != agent_count:
            errors.append(f"agents: {metrics.get('agents')} (should be {agent_count})")
        if metrics.get("commands") != command_count:
            errors.append(f"commands: {metrics.get('commands')} (should be {command_count})")

        if errors:
            return False, (
                f"marketplace.json metrics incorrect:\n"
                + "\n".join(f"  - {e}" for e in errors) +
                f"\nFix: Update .claude-plugin/marketplace.json metrics section"
            )

        return True, "✅ marketplace.json metrics correct"

    except json.JSONDecodeError:
        return False, "marketplace.json is invalid JSON"


def check_no_broken_skill_references(plugin_root: Path) -> Tuple[bool, str]:
    """Check for references to non-existent skills."""
    # Get actual skills
    skills_dir = plugin_root / "skills"
    actual_skills = set(
        d.name for d in skills_dir.iterdir()
        if d.is_dir() and not d.name.startswith(".")
    )

    # Known problematic skills that have been removed
    problematic_skills = ['engineering-standards']

    readme_path = plugin_root / "README.md"
    readme_content = readme_path.read_text()

    broken_references = []
    for skill in problematic_skills:
        if skill not in actual_skills and skill in readme_content:
            broken_references.append(skill)

    if broken_references:
        return False, (
            f"README.md references non-existent skills: {broken_references}\n"
            f"Fix: Remove or replace these skill references"
        )

    return True, "✅ No broken skill references"


def check_cross_document_consistency(plugin_root: Path, skill_count: int) -> Tuple[bool, str]:
    """Check all documentation files show same skill count."""
    files_to_check = [
        "README.md",
        "docs/SYNC-STATUS.md",
        "docs/UPDATES.md",
        "INSTALL_TEMPLATE.md",
    ]

    inconsistencies = []

    for file_path in files_to_check:
        full_path = plugin_root / file_path
        if not full_path.exists():
            continue

        content = full_path.read_text()
        # Look for skill count mentions
        if str(skill_count) not in content or "skills" not in content.lower():
            # Check if it mentions a different count
            skill_mentions = re.findall(r'(\d+)\s+[Ss]kills', content)
            if skill_mentions and int(skill_mentions[0]) != skill_count:
                inconsistencies.append(f"{file_path}: shows {skill_mentions[0]} skills (should be {skill_count})")

    if inconsistencies:
        return False, (
            f"Cross-document skill count inconsistency:\n"
            + "\n".join(f"  - {i}" for i in inconsistencies) +
            f"\nFix: Update all files to show {skill_count} skills"
        )

    return True, "✅ Cross-document consistency verified"


def check_for_deprecated_patterns(plugin_root: Path) -> Tuple[bool, str]:
    """Check for outdated procedural instructions in documentation.

    This catches procedural drift like:
    - 'python setup.py' when we now use '/setup'
    - 'scripts/setup.py' references
    - Other workflow changes that numeric validation doesn't catch
    """
    readme_path = plugin_root / "README.md"
    if not readme_path.exists():
        return True, "⚠️  README.md not found (skipping)"

    content = readme_path.read_text()

    # Define deprecated patterns and their modern replacements
    deprecated_patterns = [
        (r"python\s+.*setup\.py", "Use /setup command instead of 'python setup.py'"),
        (r"scripts/setup\.py", "Use /setup command instead of 'scripts/setup.py'"),
        (r"python\s+plugins/.*setup\.py", "Use /setup command instead of Python script"),
        (r"\.claude/scripts/setup\.py", "Use /setup command instead of '.claude/scripts/setup.py'"),
    ]

    violations = []

    for pattern, fix_message in deprecated_patterns:
        matches = re.findall(pattern, content, re.IGNORECASE)
        if matches:
            violations.append(f"Found deprecated pattern: {matches[0]}\n  → {fix_message}")

    if violations:
        return False, (
            f"Deprecated procedural instructions found in README.md:\n"
            + "\n".join(f"  - {v}" for v in violations) +
            f"\n\nThese patterns suggest outdated workflow documentation."
        )

    return True, "✅ No deprecated patterns found"


def main() -> int:
    """Run all documentation consistency checks.

    Returns:
        0 if all checks pass
        1 if any check fails
    """
    print("🔍 Validating documentation consistency...")
    print()

    try:
        plugin_root = get_plugin_root()
    except FileNotFoundError as e:
        print(f"❌ Error: {e}")
        return 1

    # Count actual resources
    skill_count = count_skills(plugin_root)
    agent_count = count_agents(plugin_root)
    command_count = count_commands(plugin_root)

    print(f"📊 Actual counts:")
    print(f"   - Skills: {skill_count}")
    print(f"   - Agents: {agent_count}")
    print(f"   - Commands: {command_count}")
    print()

    # Run all checks
    checks = [
        ("README.md skill count", check_readme_skill_count(plugin_root, skill_count)),
        ("README.md agent count", check_readme_agent_count(plugin_root, agent_count)),
        ("README.md command count", check_readme_command_count(plugin_root, command_count)),
        ("marketplace.json metrics", check_marketplace_json(plugin_root, skill_count, agent_count, command_count)),
        ("Broken skill references", check_no_broken_skill_references(plugin_root)),
        ("Cross-document consistency", check_cross_document_consistency(plugin_root, skill_count)),
        ("Deprecated patterns", check_for_deprecated_patterns(plugin_root)),
    ]

    all_passed = True

    for check_name, (passed, message) in checks:
        if passed:
            print(f"{message}")
        else:
            print(f"❌ {check_name} FAILED:")
            print(f"   {message}")
            print()
            all_passed = False

    print()

    if all_passed:
        print("✅ All documentation consistency checks passed!")
        return 0
    else:
        print("❌ Documentation consistency checks FAILED!")
        print()
        print("Fix the issues above before committing.")
        print("Or run: pytest tests/test_documentation_consistency.py -v")
        print()
        print("To skip this hook (NOT RECOMMENDED):")
        print("  git commit --no-verify")
        return 1


if __name__ == "__main__":
    sys.exit(main())
