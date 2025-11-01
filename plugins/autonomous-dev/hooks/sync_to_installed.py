#!/usr/bin/env python3
"""
Sync local plugin changes to installed plugin location for testing.

This script copies the local plugin development files to the installed
plugin location so developers can test changes as users would see them.

Usage:
    python scripts/sync_to_installed.py
    python scripts/sync_to_installed.py --dry-run
"""

import argparse
import os
import shutil
import sys
from pathlib import Path
import json


def find_installed_plugin_path():
    """Find the installed plugin path from Claude's config."""
    home = Path.home()
    installed_plugins_file = home / ".claude" / "plugins" / "installed_plugins.json"

    if not installed_plugins_file.exists():
        return None

    try:
        with open(installed_plugins_file) as f:
            config = json.load(f)

        # Look for autonomous-dev plugin
        for plugin_key, plugin_info in config.get("plugins", {}).items():
            if plugin_key.startswith("autonomous-dev@"):
                return Path(plugin_info["installPath"])
    except Exception as e:
        print(f"Error reading plugin config: {e}")
        return None

    return None


def sync_plugin(source_dir: Path, target_dir: Path, dry_run: bool = False):
    """Sync plugin files from source to target."""
    if not source_dir.exists():
        print(f"❌ Source directory not found: {source_dir}")
        return False

    if not target_dir.exists():
        print(f"❌ Target directory not found: {target_dir}")
        print("   Plugin may not be installed. Run: /plugin install autonomous-dev")
        return False

    print(f"📁 Source: {source_dir}")
    print(f"📁 Target: {target_dir}")
    print()

    # Directories to sync
    sync_dirs = ["agents", "skills", "commands", "hooks", "scripts", "templates", "docs"]

    # Files to sync
    sync_files = ["README.md", "CHANGELOG.md"]

    total_synced = 0

    for dir_name in sync_dirs:
        source_subdir = source_dir / dir_name
        target_subdir = target_dir / dir_name

        if not source_subdir.exists():
            continue

        if dry_run:
            print(f"[DRY RUN] Would sync: {dir_name}/")
            continue

        # Remove target directory if it exists
        if target_subdir.exists():
            shutil.rmtree(target_subdir)

        # Copy source to target
        shutil.copytree(source_subdir, target_subdir)

        # Count files
        file_count = sum(1 for _ in target_subdir.rglob("*") if _.is_file())
        total_synced += file_count
        print(f"✅ Synced {dir_name}/ ({file_count} files)")

    for file_name in sync_files:
        source_file = source_dir / file_name
        target_file = target_dir / file_name

        if not source_file.exists():
            continue

        if dry_run:
            print(f"[DRY RUN] Would sync: {file_name}")
            continue

        shutil.copy2(source_file, target_file)
        total_synced += 1
        print(f"✅ Synced {file_name}")

    if dry_run:
        print()
        print("🔍 DRY RUN - No files were actually synced")
        print("   Run without --dry-run to perform sync")
    else:
        print()
        print(f"✅ Successfully synced {total_synced} items to installed plugin")
        print()
        print("⚠️  RESTART REQUIRED")
        print("   Claude Code must be restarted to pick up changes:")
        print("   1. Save your work")
        print("   2. Quit Claude Code (Cmd+Q or Ctrl+Q)")
        print("   3. Restart Claude Code")

    return True


def main():
    parser = argparse.ArgumentParser(
        description="Sync local plugin changes to installed plugin for testing"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be synced without actually syncing"
    )
    args = parser.parse_args()

    # Find source directory (current repo)
    script_dir = Path(__file__).parent
    source_dir = script_dir.parent

    # Find installed plugin directory
    print("🔍 Finding installed plugin location...")
    target_dir = find_installed_plugin_path()

    if not target_dir:
        print("❌ Could not find installed autonomous-dev plugin")
        print()
        print("To install the plugin:")
        print("  1. /plugin marketplace add akaszubski/autonomous-dev")
        print("  2. /plugin install autonomous-dev")
        print("  3. Restart Claude Code")
        return 1

    print(f"✅ Found installed plugin at: {target_dir}")
    print()

    # Sync files
    success = sync_plugin(source_dir, target_dir, dry_run=args.dry_run)

    return 0 if success else 1


if __name__ == "__main__":
    sys.exit(main())
