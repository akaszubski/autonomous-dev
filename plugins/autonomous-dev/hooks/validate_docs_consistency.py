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
- All commands in commands/ are documented in README
- No deprecated procedural instructions (e.g., 'python setup.py' → '/setup') across 6 docs
- Version consistency (plugin.json = marketplace.json)
- Read-only agent restrictions (planner, reviewer, security-auditor)
- Skill table completeness (all skills documented)
- Agent frontmatter schema (name, tools fields present)

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
    """Check for outdated procedural instructions across all documentation.

    This catches procedural drift like:
    - 'python setup.py' when we now use '/setup'
    - 'scripts/setup.py' references
    - Other workflow changes that numeric validation doesn't catch
    
    Checks multiple documentation files, not just README.md.
    """
    # Files to check for deprecated patterns
    files_to_check = [
        "README.md",
        "QUICKSTART.md",
        "INSTALL_TEMPLATE.md",
        "docs/UPDATES.md",
        "docs/SYNC-STATUS.md",
        "templates/knowledge/best-practices/claude-code-2.0.md",
    ]

    # Define deprecated patterns and their modern replacements
    deprecated_patterns = [
        (r"python\s+.*setup\.py", "Use /setup command instead of 'python setup.py'"),
        (r"scripts/setup\.py", "Use /setup command instead of 'scripts/setup.py'"),
        (r"python\s+plugins/.*setup\.py", "Use /setup command instead of Python script"),
        (r"\.claude/scripts/setup\.py", "Use /setup command instead of '.claude/scripts/setup.py'"),
    ]

    all_violations = []

    for file_path in files_to_check:
        full_path = plugin_root / file_path
        if not full_path.exists():
            continue  # Skip files that don't exist

        content = full_path.read_text()

        for pattern, fix_message in deprecated_patterns:
            matches = re.findall(pattern, content, re.IGNORECASE)
            if matches:
                all_violations.append(
                    f"{file_path}: Found deprecated pattern: {matches[0]}\n  → {fix_message}"
                )
                break  # Only report first match per file

    if all_violations:
        return False, (
            f"Deprecated procedural instructions found:\n"
            + "\n".join(f"  - {v}" for v in all_violations) +
            f"\n\nThese patterns suggest outdated workflow documentation."
        )

    files_checked = len([f for f in files_to_check if (plugin_root / f).exists()])
    return True, f"✅ No deprecated patterns found (checked {files_checked} files)"





def check_command_existence(plugin_root: Path) -> Tuple[bool, str]:
    """Check that all commands in commands/ are documented in README."""
    commands_dir = plugin_root / "commands"
    readme_path = plugin_root / "README.md"
    
    if not readme_path.exists():
        return True, "⚠️  README.md not found (skipping)"
    
    readme_content = readme_path.read_text()
    
    # Get all actual commands
    actual_commands = [
        f.stem for f in commands_dir.glob("*.md")
        if not f.name.startswith(".")
    ]
    
    # Check that each command is documented (mentioned somewhere in README)
    undocumented_commands = [
        cmd for cmd in actual_commands
        if f"/{cmd}" not in readme_content
    ]
    
    if undocumented_commands:
        return False, (
            f"Undocumented commands:\n"
            + "\n".join(f"  - /{cmd}" for cmd in sorted(undocumented_commands)) +
            f"\nFix: Add these commands to README.md documentation"
        )
    
    return True, f"✅ All {len(actual_commands)} commands documented in README"


def check_version_consistency(plugin_root: Path) -> Tuple[bool, str]:
    """Check plugin.json and marketplace.json have matching versions."""
    plugin_json_path = plugin_root / ".claude-plugin" / "plugin.json"
    marketplace_json_path = plugin_root / ".claude-plugin" / "marketplace.json"
    
    if not plugin_json_path.exists() or not marketplace_json_path.exists():
        return True, "⚠️  Version files not found (skipping)"
    
    try:
        plugin_data = json.loads(plugin_json_path.read_text())
        marketplace_data = json.loads(marketplace_json_path.read_text())
        
        plugin_version = plugin_data.get("version", "MISSING")
        marketplace_version = marketplace_data.get("version", "MISSING")
        
        if plugin_version != marketplace_version:
            return False, (
                f"VERSION MISMATCH:\n"
                f"  plugin.json: {plugin_version}\n"
                f"  marketplace.json: {marketplace_version}\n"
                f"Fix: Update both files to use the same version"
            )
        
        return True, f"✅ Version consistent: {plugin_version}"
    except json.JSONDecodeError as e:
        return False, f"JSON parsing error: {e}"


def check_readonly_agent_restrictions(plugin_root: Path) -> Tuple[bool, str]:
    """Check that read-only agents don't have Write/Edit tools."""
    readonly_agents = ["planner.md", "reviewer.md", "security-auditor.md"]
    agents_dir = plugin_root / "agents"
    
    violations = []
    
    for agent_file in readonly_agents:
        agent_path = agents_dir / agent_file
        if not agent_path.exists():
            violations.append(f"{agent_file} not found")
            continue
        
        content = agent_path.read_text()
        
        # Check frontmatter for Write/Edit tools
        frontmatter_match = re.search(r'---\n(.*?)\n---', content, re.DOTALL)
        if frontmatter_match:
            frontmatter = frontmatter_match.group(1)
            if 'Write' in frontmatter or 'Edit' in frontmatter:
                violations.append(f"{agent_file} has Write/Edit (should be read-only)")
    
    if violations:
        return False, (
            f"Read-only agent violations:\n"
            + "\n".join(f"  - {v}" for v in violations) +
            f"\nFix: Remove Write/Edit from planner, reviewer, security-auditor"
        )
    
    return True, f"✅ Read-only agents properly restricted ({len(readonly_agents)} checked)"


def check_skill_table_completeness(plugin_root: Path) -> Tuple[bool, str]:
    """Check that README.md skill table lists all actual skills."""
    skills_dir = plugin_root / "skills"
    readme_path = plugin_root / "README.md"
    
    if not readme_path.exists():
        return True, "⚠️  README.md not found (skipping)"
    
    # Get actual skills
    actual_skills = set(
        d.name for d in skills_dir.iterdir()
        if d.is_dir() and not d.name.startswith(".")
    )
    
    readme_content = readme_path.read_text()
    
    # Find skills mentioned in README
    missing_skills = []
    for skill in actual_skills:
        if skill not in readme_content:
            missing_skills.append(skill)
    
    if missing_skills:
        return False, (
            f"Skill table incomplete - missing skills:\n"
            + "\n".join(f"  - {s}" for s in missing_skills) +
            f"\nFix: Add these skills to README.md skill table"
        )
    
    return True, f"✅ All {len(actual_skills)} skills documented in README"


def check_agent_frontmatter_schema(plugin_root: Path) -> Tuple[bool, str]:
    """Check that all agents have required frontmatter fields."""
    agents_dir = plugin_root / "agents"
    required_fields = ["name", "tools"]  # Claude Code 2.0 uses 'name', not 'subagent_type'
    
    violations = []
    
    for agent_file in agents_dir.glob("*.md"):
        if agent_file.name.startswith("."):
            continue
        
        content = agent_file.read_text()
        
        # Check for frontmatter
        if not content.startswith("---"):
            violations.append(f"{agent_file.name}: Missing frontmatter")
            continue
        
        # Extract frontmatter
        frontmatter_match = re.search(r'---\n(.*?)\n---', content, re.DOTALL)
        if not frontmatter_match:
            violations.append(f"{agent_file.name}: Invalid frontmatter format")
            continue
        
        frontmatter = frontmatter_match.group(1)
        
        # Check required fields
        for field in required_fields:
            if f"{field}:" not in frontmatter:
                violations.append(f"{agent_file.name}: Missing '{field}' field")
    
    if violations:
        return False, (
            f"Agent frontmatter violations:\n"
            + "\n".join(f"  - {v}" for v in violations) +
            f"\nFix: Add required fields (name, tools) to all agents"
        )
    
    agent_count = len(list(agents_dir.glob("*.md")))
    return True, f"✅ All {agent_count} agents have valid frontmatter"


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
        # Numeric consistency
        ("README.md skill count", check_readme_skill_count(plugin_root, skill_count)),
        ("README.md agent count", check_readme_agent_count(plugin_root, agent_count)),
        ("README.md command count", check_readme_command_count(plugin_root, command_count)),
        ("marketplace.json metrics", check_marketplace_json(plugin_root, skill_count, agent_count, command_count)),
        
        # Reference integrity
        ("Broken skill references", check_no_broken_skill_references(plugin_root)),
        ("Cross-document consistency", check_cross_document_consistency(plugin_root, skill_count)),
        ("Command existence", check_command_existence(plugin_root)),
        
        # Procedural consistency
        ("Deprecated patterns", check_for_deprecated_patterns(plugin_root)),
        
        # Configuration consistency
        ("Version consistency", check_version_consistency(plugin_root)),
        ("Read-only agent restrictions", check_readonly_agent_restrictions(plugin_root)),
        ("Skill table completeness", check_skill_table_completeness(plugin_root)),
        ("Agent frontmatter schema", check_agent_frontmatter_schema(plugin_root)),
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
