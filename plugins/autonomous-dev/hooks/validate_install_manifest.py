#!/usr/bin/env python3
"""
Validate and Auto-Update Install Manifest - Pre-commit Hook

Ensures install_manifest.json includes all files from source directories.
AUTOMATICALLY UPDATES the manifest if files are missing - no manual work needed.

Scans:
- hooks/*.py → manifest components.hooks.files
- lib/*.py → manifest components.lib.files
- agents/*.md → manifest components.agents.files
- commands/*.md → manifest components.commands.files (excludes archive/)
- scripts/*.py → manifest components.scripts.files
- config/*.json → manifest components.config.files
- templates/*.json → manifest components.templates.files

Usage:
    python3 validate_install_manifest.py [--check-only]

Flags:
    --check-only  Only validate, don't auto-update (for CI)

Exit Codes:
    0 - Manifest is in sync (or was auto-updated)
    1 - Check-only mode and files are missing
"""

import json
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


def scan_source_files(plugin_dir: Path) -> dict:
    """Scan source directories and return files by component.

    Returns:
        Dict mapping component name to list of file paths
    """
    components = {}

    # Define what to scan: (directory, pattern, component_name, recursive)
    scans = [
        ("hooks", "*.py", "hooks", False),
        ("lib", "*.py", "lib", False),
        ("agents", "*.md", "agents", False),
        ("commands", "*.md", "commands", False),  # Top level only, excludes archive/
        ("scripts", "*.py", "scripts", False),
        ("config", "*.json", "config", False),
        ("templates", "*.json", "templates", False),
    ]

    for dir_name, pattern, component_name, recursive in scans:
        source_dir = plugin_dir / dir_name
        if not source_dir.exists():
            continue

        files = []
        glob_method = source_dir.rglob if recursive else source_dir.glob

        for f in glob_method(pattern):
            if not f.is_file():
                continue
            # Skip pycache, test files
            if "__pycache__" in str(f):
                continue
            if f.name.startswith("test_"):
                continue

            # Build manifest path
            relative = f"plugins/autonomous-dev/{dir_name}/{f.name}"
            files.append(relative)

        components[component_name] = sorted(files)

    return components


def update_manifest(manifest_path: Path, scanned: dict) -> tuple[bool, list[str]]:
    """Update manifest with scanned files.

    Returns:
        Tuple of (was_updated, list of added files)
    """
    # Load existing manifest
    manifest = json.loads(manifest_path.read_text())

    added = []
    for component_name, scanned_files in scanned.items():
        if component_name not in manifest.get("components", {}):
            continue

        existing = set(manifest["components"][component_name].get("files", []))
        scanned_set = set(scanned_files)

        # Find new files
        new_files = scanned_set - existing
        if new_files:
            added.extend(new_files)
            # Update manifest
            manifest["components"][component_name]["files"] = sorted(
                existing | scanned_set
            )

    if added:
        # Write updated manifest
        manifest_path.write_text(json.dumps(manifest, indent=2) + "\n")
        return True, added

    return False, []


def validate_manifest(check_only: bool = False) -> tuple[bool, list[str]]:
    """Validate and optionally update manifest.

    Args:
        check_only: If True, only validate without updating

    Returns:
        Tuple of (success, list of missing/added files)
    """
    project_root = get_project_root()
    plugin_dir = project_root / "plugins" / "autonomous-dev"
    manifest_path = plugin_dir / "config" / "install_manifest.json"

    if not manifest_path.exists():
        return False, ["install_manifest.json not found"]

    # Scan source files
    scanned = scan_source_files(plugin_dir)

    # Load manifest and compare
    try:
        manifest = json.loads(manifest_path.read_text())
    except json.JSONDecodeError as e:
        return False, [f"Invalid JSON in manifest: {e}"]

    # Find missing files
    missing = []
    for component_name, scanned_files in scanned.items():
        if component_name not in manifest.get("components", {}):
            continue
        existing = set(manifest["components"][component_name].get("files", []))
        for f in scanned_files:
            if f not in existing:
                missing.append(f)

    if not missing:
        return True, []

    if check_only:
        return False, missing

    # Auto-update manifest
    updated, added = update_manifest(manifest_path, scanned)
    if updated:
        return True, added

    return True, []


def main() -> int:
    """Main entry point."""
    check_only = "--check-only" in sys.argv

    success, files = validate_manifest(check_only=check_only)

    if success:
        if files:
            print(f"✅ Auto-updated install_manifest.json (+{len(files)} files)")
            for f in sorted(files):
                print(f"  + {f}")
            print("")
            print("Manifest updated. Run: git add plugins/autonomous-dev/config/install_manifest.json")
        else:
            print("✅ install_manifest.json is in sync")
        return 0
    else:
        print("❌ install_manifest.json is OUT OF SYNC!")
        print("")
        print("Missing files:")
        for f in sorted(files):
            print(f"  - {f}")
        if check_only:
            print("")
            print("Run without --check-only to auto-update")
        return 1


if __name__ == "__main__":
    sys.exit(main())
