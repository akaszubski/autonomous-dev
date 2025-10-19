#!/usr/bin/env python3
"""
Filesystem alignment hook.

Automatically organizes .md files into proper directories.
Enforces .claude/ structure and prevents documentation sprawl.

Rules:
- Only 4 .md files allowed in project root: README, CHANGELOG, LICENSE, CLAUDE
- All other .md files move to docs/ subdirectories
- Auto-categorizes by content and filename
"""

import re
import shutil
import sys
from pathlib import Path
from typing import Dict, List

# Allowed files in project root
ALLOWED_ROOT_FILES = {
    "README.md",
    "CHANGELOG.md",
    "LICENSE.md",
    "LICENSE",
    "CLAUDE.md",
}


def categorize_markdown_file(file_path: Path) -> Path:
    """Determine destination directory for .md file.

    Returns:
        Destination directory path
    """
    name = file_path.stem
    try:
        content = file_path.read_text()[:1000].lower()  # First 1000 chars
    except:
        content = ""

    # Pattern-based rules
    if name.endswith("_SUMMARY") or name.endswith("_AUDIT") or name.endswith("_ANALYSIS"):
        return Path("docs/archive")

    # Content-based rules
    if "architecture" in content or "system design" in content:
        return Path("docs/architecture")

    if "guide" in content or "how to" in content or "tutorial" in content:
        return Path("docs/guides")

    if "research" in content or "findings" in content or "investigation" in content:
        return Path("docs/research")

    if "api" in content or "reference" in content or "endpoint" in content:
        return Path("docs/api")

    if "feature" in content or "specification" in content:
        return Path("docs/features")

    # Default: archive
    return Path("docs/archive")


def find_misplaced_files() -> List[Path]:
    """Find .md files in project root (excluding allowed files)."""
    misplaced = []

    for file_path in Path(".").glob("*.md"):
        if file_path.name not in ALLOWED_ROOT_FILES:
            misplaced.append(file_path)

    return misplaced


def update_links_to_moved_file(old_path: str, new_path: str):
    """Update markdown links pointing to moved file."""
    # Find all markdown files
    md_files = []
    for pattern in ["**/*.md"]:
        md_files.extend(Path(".").glob(pattern))

    updated_count = 0

    for md_file in md_files:
        try:
            content = md_file.read_text()

            # Find links like [text](old_path)
            if old_path in content:
                # Calculate relative path from md_file to new_path
                # For simplicity, use absolute path from project root
                updated = content.replace(f"]({old_path})", f"]({new_path})")

                # Also update without ./ prefix
                updated = updated.replace(f"](./{old_path})", f"]({new_path})")

                if updated != content:
                    md_file.write_text(updated)
                    updated_count += 1

        except Exception as e:
            print(f"⚠️  Error updating links in {md_file}: {e}", file=sys.stderr)

    return updated_count


def move_file(file_path: Path, dest_dir: Path) -> bool:
    """Move file to destination directory.

    Returns:
        True if file was moved, False otherwise
    """
    try:
        # Create destination directory
        dest_dir.mkdir(parents=True, exist_ok=True)

        # Destination file path
        dest_path = dest_dir / file_path.name

        # Check if destination already exists
        if dest_path.exists():
            print(f"⚠️  {dest_path} already exists, skipping {file_path}")
            return False

        # Move file
        shutil.move(str(file_path), str(dest_path))

        # Update links in other markdown files
        old_path = file_path.name
        new_path = str(dest_path)
        updated = update_links_to_moved_file(old_path, new_path)

        print(f"   Moved: {file_path} → {dest_path}")
        if updated > 0:
            print(f"   Updated links in {updated} files")

        return True

    except Exception as e:
        print(f"❌ Error moving {file_path}: {e}", file=sys.stderr)
        return False


def check_claude_structure():
    """Ensure .claude/ directory has correct structure."""
    claude_dir = Path(".claude")

    if not claude_dir.exists():
        print("ℹ️  No .claude/ directory found")
        return

    required_files = ["PROJECT.md", "PATTERNS.md", "STATUS.md"]
    missing = [f for f in required_files if not (claude_dir / f).exists()]

    if missing:
        print(f"⚠️  Missing required .claude/ files: {', '.join(missing)}")


def main():
    """Run filesystem alignment."""
    print("📁 Checking filesystem alignment...")

    # Find misplaced files
    misplaced = find_misplaced_files()

    if not misplaced:
        print("✅ Filesystem aligned (only allowed .md files in root)")

        # Check .claude/ structure
        check_claude_structure()
        sys.exit(0)

    print(f"\n📋 Found {len(misplaced)} misplaced .md files:\n")

    moved_count = 0

    for file_path in misplaced:
        dest_dir = categorize_markdown_file(file_path)
        print(f"📄 {file_path} → {dest_dir}/")

        if move_file(file_path, dest_dir):
            moved_count += 1

    print(f"\n✅ Moved {moved_count} files to appropriate directories")
    print(f"   Root now contains {len(ALLOWED_ROOT_FILES)} allowed files")

    # Check .claude/ structure
    check_claude_structure()


if __name__ == "__main__":
    main()
