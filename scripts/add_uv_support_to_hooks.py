#!/usr/bin/env python3
"""
Add UV single-file script support to all Python hooks.

This script intelligently updates hooks by:
1. Replacing shebang with UV shebang
2. Adding PEP 723 metadata block after shebang
3. Adding is_running_under_uv() detection function
4. Wrapping sys.path.insert() calls in UV conditional (preserving indentation)

Usage:
    python scripts/add_uv_support_to_hooks.py [--dry-run]

Issue: #172
"""

import argparse
import re
import sys
from pathlib import Path
from typing import List, Tuple


UV_SHEBANG = "#!/usr/bin/env -S uv run --script --quiet --no-project"

PEP723_METADATA = """# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///"""

UV_DETECTION_FUNCTION = '''

def is_running_under_uv() -> bool:
    """Detect if script is running under UV."""
    return "UV_PROJECT_ENVIRONMENT" in os.environ
'''


def process_hook_file(hook_path: Path, dry_run: bool = False) -> Tuple[bool, str]:
    """
    Update a single hook file with UV support.

    Args:
        hook_path: Path to hook file
        dry_run: If True, don't write changes

    Returns:
        (modified, message) tuple
    """
    content = hook_path.read_text()
    original_content = content

    # Check if already has UV shebang
    if content.startswith("#!/usr/bin/env -S uv run"):
        return (False, f"Already has UV shebang")

    lines = content.split('\n')
    modified = False

    # Step 1: Replace shebang with UV shebang + PEP 723 metadata
    if lines[0].startswith("#!/"):
        new_lines = [UV_SHEBANG, PEP723_METADATA.strip()] + lines[1:]
        modified = True
    else:
        new_lines = [UV_SHEBANG, PEP723_METADATA.strip()] + lines
        modified = True

    # Step 2: Add is_running_under_uv() function if not present
    content_str = '\n'.join(new_lines)
    if 'def is_running_under_uv(' not in content_str:
        # Find good insertion point - after imports, before first function/class
        in_docstring = False
        past_docstring = False
        insert_idx = None

        for i, line in enumerate(new_lines):
            # Track docstring (triple quotes)
            if '"""' in line or "'''" in line:
                if not in_docstring:
                    in_docstring = True
                else:
                    in_docstring = False
                    past_docstring = True
                continue

            # Skip if in docstring
            if in_docstring:
                continue

            # After docstring, find end of imports
            if past_docstring:
                # Skip blank lines and comments
                if line.strip() == '' or line.startswith('#'):
                    continue
                # Skip imports
                if line.startswith('import ') or line.startswith('from '):
                    continue
                # Found first non-import line - insert here
                insert_idx = i
                break

        if insert_idx is not None:
            new_lines.insert(insert_idx, UV_DETECTION_FUNCTION.strip())
            new_lines.insert(insert_idx + 1, '')  # Add blank line after
            modified = True

    # Step 3: Wrap sys.path.insert() in UV conditional (CAREFUL WITH INDENTATION!)
    result_lines = []
    i = 0

    while i < len(new_lines):
        line = new_lines[i]

        # Check if this line contains sys.path.insert
        if 'sys.path.insert(' in line and 'sys.path.insert(0' in line:
            # Check if already wrapped
            already_wrapped = False

            # Look back up to 10 lines for UV check
            for j in range(max(0, i-10), i):
                if 'is_running_under_uv()' in new_lines[j]:
                    already_wrapped = True
                    break

            if not already_wrapped:
                # Get current indentation
                indent = len(line) - len(line.lstrip())
                indent_str = ' ' * indent

                # Add conditional wrapper with proper indentation
                result_lines.append(f"{indent_str}if not is_running_under_uv():")
                result_lines.append(f"{indent_str}    {line.lstrip()}")
                modified = True
                i += 1
                continue

        result_lines.append(line)
        i += 1

    new_content = '\n'.join(result_lines)

    # Only write if changed
    if modified and new_content != original_content:
        if not dry_run:
            hook_path.write_text(new_content)
        return (True, "Updated with UV support")
    else:
        return (False, "No changes needed")


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(description="Add UV support to hook files")
    parser.add_argument('--dry-run', action='store_true', help="Show what would be changed without writing")
    args = parser.parse_args()

    # Find project root
    script_dir = Path(__file__).parent
    project_root = script_dir.parent

    if not (project_root / ".git").exists():
        print("Error: Not in project root")
        sys.exit(1)

    hooks_dir = project_root / "plugins" / "autonomous-dev" / "hooks"

    if not hooks_dir.exists():
        print(f"Error: Hooks directory not found: {hooks_dir}")
        sys.exit(1)

    # Get all Python files
    hook_files = sorted(hooks_dir.glob("*.py"))

    if not hook_files:
        print("No Python hook files found")
        sys.exit(1)

    print(f"{'DRY RUN: ' if args.dry_run else ''}Processing {len(hook_files)} hook files...")
    print()

    modified_count = 0
    skipped_count = 0

    for hook_file in hook_files:
        modified, message = process_hook_file(hook_file, args.dry_run)

        status = "✓" if modified else "-"
        print(f"  {status} {hook_file.name:50s} {message}")

        if modified:
            modified_count += 1
        else:
            skipped_count += 1

    print()
    print(f"Summary: {modified_count} updated, {skipped_count} skipped")

    if args.dry_run and modified_count > 0:
        print()
        print("Run without --dry-run to apply changes")
    elif modified_count > 0:
        print()
        print("Next steps:")
        print("1. Make all hooks executable: chmod +x plugins/autonomous-dev/hooks/*.py")
        print("2. Review changes: git diff plugins/autonomous-dev/hooks/ | head -200")
        print("3. Run tests: pytest tests/unit/test_uv_hooks_validation.py tests/integration/test_uv_execution.py -v")


if __name__ == "__main__":
    main()
