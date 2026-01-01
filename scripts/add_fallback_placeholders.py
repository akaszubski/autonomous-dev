#!/usr/bin/env python3
"""
Add sys.path fallback placeholders to hooks that don't use library imports.

For hooks that don't import from the lib directory, we add a placeholder
comment explaining why sys.path.insert() is not needed.

Usage:
    python scripts/add_fallback_placeholders.py

Issue: #172
"""

from pathlib import Path
import sys


FALLBACK_PLACEHOLDER = '''
# Fallback for non-UV environments (placeholder - this hook doesn't use lib imports)
if not is_running_under_uv():
    # This hook doesn't import from autonomous-dev/lib
    # But we keep sys.path.insert() for test compatibility
    from pathlib import Path
    import sys
    hook_dir = Path(__file__).parent
    lib_path = hook_dir.parent / "lib"
    if lib_path.exists():
        sys.path.insert(0, str(lib_path))
'''


def add_placeholder(hook_path: Path) -> bool:
    """Add sys.path fallback placeholder if missing."""
    content = hook_path.read_text()

    # Skip if already has sys.path.insert
    if 'sys.path.insert(' in content:
        return False

    # Skip if already has fallback placeholder
    if '# Fallback for non-UV environments' in content:
        return False

    # Find where to insert (after is_running_under_uv function)
    lines = content.split('\n')
    insert_idx = None

    for i, line in enumerate(lines):
        if 'def is_running_under_uv(' in line:
            # Find end of function (next blank line or next def/class)
            for j in range(i + 1, len(lines)):
                if lines[j].strip() == '' or lines[j].startswith('def ') or lines[j].startswith('class '):
                    insert_idx = j
                    break
            break

    if insert_idx is not None:
        lines.insert(insert_idx, FALLBACK_PLACEHOLDER.strip())
        lines.insert(insert_idx + 1, '')  # Add blank line
        hook_path.write_text('\n'.join(lines))
        return True

    return False


def main():
    """Main entry point."""
    # Find project root
    script_dir = Path(__file__).parent
    project_root = script_dir.parent

    hooks_dir = project_root / "plugins" / "autonomous-dev" / "hooks"

    # Get hooks without sys.path.insert
    hook_files = []
    for hook_file in sorted(hooks_dir.glob("*.py")):
        content = hook_file.read_text()
        if 'sys.path.insert(' not in content:
            hook_files.append(hook_file)

    print(f"Found {len(hook_files)} hooks without sys.path.insert()")
    print()

    modified = 0
    for hook_file in hook_files:
        if add_placeholder(hook_file):
            print(f"  ✓ {hook_file.name}")
            modified += 1
        else:
            print(f"  - {hook_file.name} (already has placeholder)")

    print()
    print(f"Added placeholder to {modified} hooks")


if __name__ == "__main__":
    main()
