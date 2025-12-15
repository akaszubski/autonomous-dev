#!/usr/bin/env python3
"""
Bulk add version field to skills missing it.

Issue #148 - Claude Code 2.0 Compliance
"""

import re
from pathlib import Path


def find_project_root() -> Path:
    """Find project root by looking for .git or .claude directory."""
    current = Path.cwd()
    while current != current.parent:
        if (current / ".git").exists() or (current / ".claude").exists():
            return current
        current = current.parent
    raise FileNotFoundError("Could not find project root")


def add_version_to_skill(skill_path: Path) -> bool:
    """Add version: 1.0.0 to skill frontmatter if missing.

    Returns True if file was modified, False if already has version.
    """
    content = skill_path.read_text()

    # Check if already has version
    if re.search(r'^version:\s*', content, re.MULTILINE):
        return False

    # Find the frontmatter section
    match = re.match(r'^---\n(.*?)\n---', content, re.DOTALL)
    if not match:
        print(f"  Warning: No frontmatter found in {skill_path.name}")
        return False

    frontmatter = match.group(1)

    # Add version after name field (or at end of frontmatter if no name)
    if 'name:' in frontmatter:
        # Add version after the name line
        new_frontmatter = re.sub(
            r'(name:\s*[^\n]+\n)',
            r'\1version: 1.0.0\n',
            frontmatter
        )
    else:
        # Add at end of frontmatter
        new_frontmatter = frontmatter.rstrip() + '\nversion: 1.0.0\n'

    # Replace frontmatter in content
    new_content = content.replace(
        f'---\n{frontmatter}\n---',
        f'---\n{new_frontmatter}---'
    )

    skill_path.write_text(new_content)
    return True


def main():
    """Add version field to all skills missing it."""
    project_root = find_project_root()
    skills_dir = project_root / "plugins/autonomous-dev/skills"

    if not skills_dir.exists():
        print(f"Error: Skills directory not found: {skills_dir}")
        return 1

    # Find all SKILL.md files
    skill_files = list(skills_dir.glob("*/SKILL.md"))
    print(f"Found {len(skill_files)} skills")

    modified = 0
    skipped = 0

    for skill_path in sorted(skill_files):
        skill_name = skill_path.parent.name
        if add_version_to_skill(skill_path):
            print(f"  + Added version to: {skill_name}")
            modified += 1
        else:
            print(f"  - Already has version: {skill_name}")
            skipped += 1

    print(f"\nSummary:")
    print(f"  Modified: {modified}")
    print(f"  Skipped: {skipped}")
    print(f"  Total: {len(skill_files)}")

    return 0


if __name__ == "__main__":
    exit(main())
