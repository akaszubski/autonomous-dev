#!/usr/bin/env python3
"""
Script to add UV single-file script support to all Python hooks.

This script adds:
1. UV shebang: #!/usr/bin/env -S uv run --script --quiet --no-project
2. PEP 723 metadata block
3. is_running_under_uv() function
4. Conditional sys.path logic

Usage:
    python scripts/update_hooks_for_uv.py

Issue: #172
"""

from pathlib import Path
import sys


UV_SHEBANG = "#!/usr/bin/env -S uv run --script --quiet --no-project"
PEP723_METADATA = '''# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///'''

UV_DETECTION_FUNCTION = '''

def is_running_under_uv() -> bool:
    """Detect if script is running under UV."""
    return "UV_PROJECT_ENVIRONMENT" in os.environ
'''


def update_hook_file(hook_path: Path) -> bool:
    """
    Update a single hook file with UV support.

    Returns:
        True if file was modified, False if no changes needed
    """
    content = hook_path.read_text()
    lines = content.split('\n')

    # Check if already has UV shebang
    if lines[0].startswith("#!/usr/bin/env -S uv run"):
        print(f"  ✓ {hook_path.name} - Already has UV shebang, skipping")
        return False

    modified = False
    new_lines = []

    # Step 1: Replace shebang with UV shebang
    if lines[0].startswith("#!"):
        new_lines.append(UV_SHEBANG)
        modified = True
        i = 1
    else:
        # No shebang, add one
        new_lines.append(UV_SHEBANG)
        modified = True
        i = 0

    # Step 2: Add PEP 723 metadata block after shebang
    new_lines.append(PEP723_METADATA)

    # Step 3: Find and add rest of file (skip old shebang if replaced)
    # Find the docstring
    in_docstring = False
    docstring_start = -1

    for idx in range(i, len(lines)):
        line = lines[idx]
        if '"""' in line and not in_docstring:
            in_docstring = True
            docstring_start = idx
        elif '"""' in line and in_docstring:
            # End of docstring found
            in_docstring = False
            # Add all lines from docstring onwards
            new_lines.extend(lines[idx:])
            break

    # If no docstring found, just append everything
    if docstring_start == -1:
        new_lines.extend(lines[i:])

    # Step 4: Add is_running_under_uv() function if not present
    content_str = '\n'.join(new_lines)
    if 'def is_running_under_uv(' not in content_str:
        # Find where to insert (after imports, before main logic)
        # Look for first function definition or if __name__
        insert_pos = -1
        for idx, line in enumerate(new_lines):
            # Insert before first def or class that's not inside docstring
            if idx > 10 and (line.startswith('def ') or line.startswith('class ')):
                insert_pos = idx
                break
            # Or before if __name__
            if 'if __name__' in line:
                insert_pos = idx
                break

        if insert_pos > 0:
            new_lines.insert(insert_pos, UV_DETECTION_FUNCTION)
            modified = True
        else:
            # Couldn't find good insertion point, add after imports
            # Find last import
            last_import = -1
            for idx, line in enumerate(new_lines):
                if line.startswith('import ') or line.startswith('from '):
                    last_import = idx

            if last_import > 0:
                new_lines.insert(last_import + 1, UV_DETECTION_FUNCTION)
                modified = True

    # Step 5: Wrap sys.path.insert() in UV conditional
    final_lines = []
    for idx, line in enumerate(new_lines):
        if 'sys.path.insert(' in line and 'if not is_running_under_uv()' not in '\n'.join(new_lines[max(0, idx-5):idx]):
            # Check if we need to wrap this
            # Look backwards to see if it's already wrapped
            already_wrapped = False
            for prev_idx in range(max(0, idx - 5), idx):
                if 'is_running_under_uv' in new_lines[prev_idx]:
                    already_wrapped = True
                    break

            if not already_wrapped:
                # Check indentation
                indent = len(line) - len(line.lstrip())
                indent_str = ' ' * indent

                # Add conditional wrapper
                final_lines.append(f"{indent_str}if not is_running_under_uv():")
                final_lines.append(' ' * 4 + line)  # Add 4 spaces indentation
                modified = True
                continue

        final_lines.append(line)

    if modified:
        # Write updated content
        hook_path.write_text('\n'.join(final_lines))
        print(f"  ✓ {hook_path.name} - Updated with UV support")
        return True
    else:
        print(f"  ✓ {hook_path.name} - No changes needed")
        return False


def main():
    """Update all hooks in plugins/autonomous-dev/hooks/."""
    # Find project root
    current = Path(__file__).parent
    while current != current.parent:
        if (current / ".git").exists():
            project_root = current
            break
        current = current.parent
    else:
        project_root = Path.cwd()

    hooks_dir = project_root / "plugins" / "autonomous-dev" / "hooks"

    if not hooks_dir.exists():
        print(f"Error: Hooks directory not found: {hooks_dir}")
        sys.exit(1)

    print(f"Updating hooks in: {hooks_dir}")
    print()

    # Get all Python files
    hook_files = sorted(hooks_dir.glob("*.py"))

    if not hook_files:
        print("No Python hook files found")
        sys.exit(1)

    print(f"Found {len(hook_files)} hook files")
    print()

    modified_count = 0
    for hook_file in hook_files:
        if update_hook_file(hook_file):
            modified_count += 1

    print()
    print(f"Summary: Updated {modified_count}/{len(hook_files)} hooks")

    if modified_count > 0:
        print()
        print("Next steps:")
        print("1. Review changes: git diff plugins/autonomous-dev/hooks/")
        print("2. Run tests: pytest tests/unit/test_uv_hooks_validation.py tests/integration/test_uv_execution.py -v")
        print("3. Fix any issues manually if needed")


if __name__ == "__main__":
    main()
