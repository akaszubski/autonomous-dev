#!/usr/bin/env -S uv run --script --quiet --no-project
# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""
Validate Command Consistency - Pre-commit Hook

Ensures command references are consistent across all configuration files.
Catches drift when commands are added, removed, deprecated, or renamed.

Cross-validates:
- plugin.json commands list
- install_manifest.json commands list
- Actual .md files in commands/
- References in install.sh (user-facing messages)
- References in setup.md (examples)

Rules:
- Active commands must be in plugin.json AND have .md files
- install_manifest.json must include both active AND deprecated command files
- Deprecated commands should NOT appear in install.sh or setup.md
- Deprecated command references are allowed in: CHANGELOG, archived/, *-HISTORY.md, epic-*

Usage:
    python3 validate_command_consistency.py

Exit Codes:
    0 - All command references are consistent
    1 - Inconsistencies found (blocks commit)
"""

import json
import re
import sys
from pathlib import Path


def get_project_root() -> Path:
    """Find project root by looking for .git directory."""
    current = Path.cwd()
    while current != current.parent:
        if (current / ".git").exists():
            return current
        current = current.parent
    return Path.cwd()


def get_plugin_dir() -> Path:
    """Get the plugin directory."""
    root = get_project_root()
    return root / "plugins" / "autonomous-dev"


def get_active_command_files(plugin_dir: Path) -> set[str]:
    """Get command names from .md files in commands/ (excluding archived/).

    Uses non-recursive glob (*.md) which only finds files in commands/ directory,
    not in subdirectories like commands/archived/.
    """
    commands_dir = plugin_dir / "commands"
    if not commands_dir.exists():
        return set()

    commands = set()
    for f in commands_dir.glob("*.md"):
        commands.add(f.stem)  # filename without .md
    return commands


def get_archived_command_files(plugin_dir: Path) -> set[str]:
    """Get command names from archived commands directory."""
    archived_dir = plugin_dir / "commands" / "archived"
    if not archived_dir.exists():
        return set()

    commands = set()
    for f in archived_dir.glob("*.md"):
        commands.add(f.stem)
    return commands


def get_deprecated_commands(plugin_dir: Path) -> set[str]:
    """Get commands marked as deprecated in their frontmatter."""
    commands_dir = plugin_dir / "commands"
    deprecated = set()

    for f in commands_dir.glob("*.md"):
        try:
            content = f.read_text()
            # Check for deprecated: true in frontmatter
            if re.search(r'^deprecated:\s*true', content, re.MULTILINE):
                deprecated.add(f.stem)
        except Exception:
            continue

    return deprecated


def get_plugin_json_commands(plugin_dir: Path) -> set[str]:
    """Get commands from plugin.json."""
    plugin_json = plugin_dir / "plugin.json"
    if not plugin_json.exists():
        return set()

    try:
        data = json.loads(plugin_json.read_text())
        # Remove leading / from command names
        return {cmd.lstrip('/') for cmd in data.get("commands", [])}
    except Exception:
        return set()


def get_manifest_commands(plugin_dir: Path) -> set[str]:
    """Get commands list from install_manifest.json."""
    manifest = plugin_dir / "config" / "install_manifest.json"
    if not manifest.exists():
        return set()

    try:
        data = json.loads(manifest.read_text())
        return set(data.get("commands", []))
    except Exception:
        return set()


def get_manifest_command_files(plugin_dir: Path) -> set[str]:
    """Get command file paths from install_manifest.json."""
    manifest = plugin_dir / "config" / "install_manifest.json"
    if not manifest.exists():
        return set()

    try:
        data = json.loads(manifest.read_text())
        files = data.get("components", {}).get("commands", {}).get("files", [])
        # Extract command name from path like "plugins/autonomous-dev/commands/setup.md"
        commands = set()
        for f in files:
            name = Path(f).stem
            commands.add(name)
        return commands
    except Exception:
        return set()


def find_command_refs_in_file(filepath: Path, commands: set[str]) -> dict[str, list[int]]:
    """Find command references in a file.

    Returns:
        Dict mapping command name to list of line numbers where referenced
    """
    refs = {}
    if not filepath.exists():
        return refs

    try:
        lines = filepath.read_text().splitlines()
        for i, line in enumerate(lines, 1):
            for cmd in commands:
                # Match /command-name pattern
                pattern = rf'/{re.escape(cmd)}(?:\s|"|\'|$|,|\))'
                if re.search(pattern, line):
                    if cmd not in refs:
                        refs[cmd] = []
                    refs[cmd].append(i)
        return refs
    except Exception:
        return refs


def is_historical_file(filepath: Path) -> bool:
    """Check if file is a historical document that should preserve old refs."""
    path_str = str(filepath).lower()

    historical_patterns = [
        "changelog",
        "history",
        "epic-",
        "archived",
        "_results.md",  # Test results
    ]

    return any(p in path_str for p in historical_patterns)


def validate_command_consistency() -> tuple[bool, list[str]]:
    """Main validation function.

    Returns:
        Tuple of (is_valid, list of error messages)
    """
    errors = []
    plugin_dir = get_plugin_dir()
    root = get_project_root()

    if not plugin_dir.exists():
        return True, []  # Not in autonomous-dev repo

    # Get all command sets
    active_files = get_active_command_files(plugin_dir)
    archived_files = get_archived_command_files(plugin_dir)
    deprecated = get_deprecated_commands(plugin_dir)
    plugin_json_cmds = get_plugin_json_commands(plugin_dir)
    manifest_files = get_manifest_command_files(plugin_dir)

    all_command_files = active_files | archived_files

    # Validation 1: plugin.json should only list non-deprecated active commands
    deprecated_in_plugin_json = plugin_json_cmds & deprecated
    if deprecated_in_plugin_json:
        errors.append(
            f"plugin.json lists deprecated commands: {', '.join(sorted(deprecated_in_plugin_json))}"
        )

    # Validation 2: All plugin.json commands should have .md files
    missing_files = plugin_json_cmds - all_command_files
    if missing_files:
        errors.append(
            f"plugin.json references commands without .md files: {', '.join(sorted(missing_files))}"
        )

    # Validation 3: manifest should include all command files (active + deprecated shims)
    missing_from_manifest = all_command_files - manifest_files
    if missing_from_manifest:
        errors.append(
            f"install_manifest.json missing command files: {', '.join(sorted(missing_from_manifest))}"
        )

    # Validation 4: Check install.sh for deprecated command references
    install_sh = root / "install.sh"
    if install_sh.exists() and deprecated:
        refs = find_command_refs_in_file(install_sh, deprecated)
        if refs:
            for cmd, lines in refs.items():
                errors.append(
                    f"install.sh references deprecated /{cmd} at lines: {lines}"
                )

    # Validation 5: Check setup.md for deprecated command references
    setup_md = plugin_dir / "commands" / "setup.md"
    if setup_md.exists() and deprecated:
        refs = find_command_refs_in_file(setup_md, deprecated)
        if refs:
            for cmd, lines in refs.items():
                errors.append(
                    f"setup.md references deprecated /{cmd} at lines: {lines}"
                )

    # Validation 6: Check key docs for deprecated refs (non-historical only)
    docs_to_check = [
        plugin_dir / "README.md",
        plugin_dir / "docs" / "QUICKSTART.md",
        root / "CLAUDE.md",
    ]

    for doc in docs_to_check:
        if doc.exists() and not is_historical_file(doc) and deprecated:
            refs = find_command_refs_in_file(doc, deprecated)
            if refs:
                for cmd, lines in refs.items():
                    errors.append(
                        f"{doc.name} references deprecated /{cmd} at lines: {lines}"
                    )

    return len(errors) == 0, errors


def main():
    """Main entry point."""
    print("🔍 Validating command consistency...")

    is_valid, errors = validate_command_consistency()

    if is_valid:
        print("✅ All command references are consistent")
        return 0
    else:
        print("❌ Command consistency validation FAILED\n")
        for error in errors:
            print(f"  • {error}")
        print("\n" + "=" * 60)
        print("FIX: Update all locations when adding/removing/deprecating commands")
        print("SEE: doc-master.md 'Command Deprecation/Rename Handling' section")
        print("=" * 60)
        return 1


if __name__ == "__main__":
    sys.exit(main())
