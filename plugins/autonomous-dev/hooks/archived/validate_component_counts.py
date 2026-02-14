#!/usr/bin/env -S uv run --script --quiet --no-project
# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""
Validate Component Counts - Pre-commit Hook

Ensures component counts in CLAUDE.md match actual filesystem counts.
Detects drift between documented counts and implementation reality.

Counts:
- Hooks: plugins/autonomous-dev/hooks/*.py (excluding __init__.py)
- Libraries: plugins/autonomous-dev/lib/**/*.py (excluding __init__.py)
- Agents: plugins/autonomous-dev/agents/*.md
- Skills: plugins/autonomous-dev/skills/*/ (directories)
- Commands: plugins/autonomous-dev/commands/*.md

Usage:
    python3 validate_component_counts.py

Exit Codes:
    0 - All counts match
    2 - Count mismatch detected (blocks commit)

Environment Variables:
    VALIDATE_COMPONENT_COUNTS=false - Disable validation (allow mismatches)
"""

import os
import re
import sys
from pathlib import Path
from typing import Dict, List, Tuple


def is_running_under_uv() -> bool:
    """Detect if script is running under UV."""
    return "UV_PROJECT_ENVIRONMENT" in os.environ


# Fallback for non-UV environments
if not is_running_under_uv():
    from pathlib import Path
    import sys
    hook_dir = Path(__file__).parent
    lib_path = hook_dir.parent / "lib"
    if lib_path.exists():
        sys.path.insert(0, str(lib_path))


def get_project_root() -> Path:
    """Find project root by looking for .git directory."""
    current = Path.cwd()
    while current != current.parent:
        if (current / ".git").exists() or (current / ".claude").exists():
            return current
        current = current.parent
    return Path.cwd()


def count_components(project_root: Path) -> Dict[str, int]:
    """Count actual components in the filesystem.

    Returns:
        Dict mapping component type to count
    """
    plugin_dir = project_root / "plugins" / "autonomous-dev"

    counts = {
        "hooks": len([
            f for f in (plugin_dir / "hooks").glob("*.py")
            if f.name != "__init__.py"
        ]),
        "libraries": len([
            f for f in (plugin_dir / "lib").rglob("*.py")
            if f.name != "__init__.py"
        ]),
        "agents": len(list((plugin_dir / "agents").glob("*.md"))),
        "skills": len([
            d for d in (plugin_dir / "skills").iterdir()
            if d.is_dir() and not d.name.startswith(".")
        ]),
        "commands": len(list((plugin_dir / "commands").glob("*.md"))),
    }

    return counts


def parse_claude_md_counts(claude_md_path: Path) -> Dict[str, int]:
    """Parse component counts from CLAUDE.md.

    Looks for the Component Versions table:
    | Component | Count | Status |
    |-----------|-------|--------|
    | Skills | 28 | ✅ Compliant |
    | Commands | 24 | ✅ Compliant |
    | Agents | 22 | ✅ Compliant |
    | Hooks | 68 | ✅ Compliant |

    Also looks for Architecture section mentions like:
    - "22 Agents"
    - "143 Libraries"
    - "68 Hooks"

    Returns:
        Dict mapping component type (lowercase) to documented count
    """
    if not claude_md_path.exists():
        return {}

    content = claude_md_path.read_text()
    counts = {}

    # Pattern 1: Component Versions table (highest priority)
    # Extract table between "## Component Versions" and next "___"
    table_match = re.search(
        r"## Component Versions\s*\n\s*\|.*?\|.*?\|\s*\n\s*\|[-|]+\|\s*\n((?:\|.*?\|\s*\n)+)",
        content,
        re.MULTILINE
    )

    if table_match:
        table_content = table_match.group(1)
        # Parse each row: | Skills | 28 | ✅ Compliant |
        for line in table_content.split("\n"):
            if not line.strip() or not line.startswith("|"):
                continue
            parts = [p.strip() for p in line.split("|") if p.strip()]
            if len(parts) >= 2:
                component = parts[0].lower()
                try:
                    count = int(parts[1].split()[0])  # "28" or "5 templates" -> 28 or 5
                    counts[component] = count
                except (ValueError, IndexError):
                    pass

    # Pattern 2: Architecture section mentions (fallback)
    # "22 Agents", "143 Libraries", "68 Hooks"
    patterns = {
        "agents": r"(\d+)\s+Agents",
        "libraries": r"(\d+)\s+Libraries",
        "hooks": r"(\d+)\s+Hooks",
        "skills": r"(\d+)\s+Skills",
        "commands": r"(\d+)\s+(?:total\s+)?commands",
    }

    for component, pattern in patterns.items():
        if component not in counts:  # Only if not found in table
            match = re.search(pattern, content, re.IGNORECASE)
            if match:
                counts[component] = int(match.group(1))

    return counts


def compare_counts(
    actual: Dict[str, int],
    documented: Dict[str, int]
) -> Tuple[bool, List[str]]:
    """Compare actual vs documented counts.

    Returns:
        Tuple of (all_match, list of mismatch messages)
    """
    mismatches = []

    for component in ["skills", "commands", "agents", "hooks", "libraries"]:
        actual_count = actual.get(component, 0)
        doc_count = documented.get(component, 0)

        if actual_count != doc_count:
            # Special handling for settings (might be "5 templates")
            if component == "settings":
                continue  # Skip settings validation (has special format)

            mismatches.append(
                f"{component.capitalize()}: "
                f"CLAUDE.md says {doc_count}, but {actual_count} exist"
            )

    return len(mismatches) == 0, mismatches


def main() -> int:
    """Main entry point."""
    # Check if validation is disabled
    if os.environ.get("VALIDATE_COMPONENT_COUNTS", "true").lower() == "false":
        print("ℹ️  Component count validation disabled (VALIDATE_COMPONENT_COUNTS=false)")
        return 0

    project_root = get_project_root()
    claude_md_path = project_root / "CLAUDE.md"

    if not claude_md_path.exists():
        print("⚠️  CLAUDE.md not found, skipping component count validation")
        return 0

    # Count actual components
    actual_counts = count_components(project_root)

    # Parse documented counts from CLAUDE.md
    documented_counts = parse_claude_md_counts(claude_md_path)

    # Compare
    all_match, mismatches = compare_counts(actual_counts, documented_counts)

    if all_match:
        print("✅ Component counts in CLAUDE.md match filesystem")
        return 0

    # Print detailed error report
    print("=" * 70)
    print("❌ Component Count Mismatch Detected")
    print("=" * 70)
    print("")
    print("CLAUDE.md component counts are out of sync with actual filesystem:")
    print("")

    for mismatch in mismatches:
        print(f"  - {mismatch}")

    print("")
    print("Actual counts:")
    for component in ["skills", "commands", "agents", "hooks", "libraries"]:
        count = actual_counts.get(component, 0)
        print(f"  - {component.capitalize()}: {count}")

    print("")
    print("Fix:")
    print("  1. Update CLAUDE.md Component Versions table with actual counts")
    print("  2. Update Architecture section if it mentions component counts")
    print("  3. Commit: git add CLAUDE.md && git commit -m 'docs: update component counts'")
    print("")
    print("To temporarily bypass this check:")
    print("  VALIDATE_COMPONENT_COUNTS=false git commit -m '...'")
    print("=" * 70)

    return 2  # Exit 2 blocks commit


if __name__ == "__main__":
    sys.exit(main())
