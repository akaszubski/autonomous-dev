#!/usr/bin/env python3
"""
Sync local plugin changes to installed plugin location for testing.

This script copies the local plugin development files to the installed
plugin location so developers can test changes as users would see them.

Security Features (GitHub Issue #45 - v3.2.3):
- Symlink validation: Rejects symlinks in install path (Layer 1 & 2)
- Whitelist validation: Verifies path is within .claude/plugins/ (Layer 3)
- Null checks: Handles missing/empty installPath values safely
- Error gracefully: Returns None instead of crashing on invalid paths

See find_installed_plugin_path() docstring for detailed security design.

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
    """Find the installed plugin path from Claude's config with path traversal protection.

    Searches Claude's installed_plugins.json for the autonomous-dev plugin and
    returns its installation path after validating it with three security layers.

    Returns:
        Path: Validated canonical path to installed plugin directory
        None: If plugin not found, path invalid, or security checks failed

    Security Validation (GitHub Issue #45 - Path Traversal Prevention):
    ===================================================================

    This function implements THREE-LAYER path validation to prevent directory traversal
    attacks. An attacker could craft a malicious installPath in installed_plugins.json
    to escape the plugins directory and access system files.

    Example Attack Scenarios:
    - Relative traversal: installPath = "../../etc/passwd"
    - Symlink escape: installPath = "link_to_etc" -> symlink to /etc
    - Null path: installPath = None or "" (incomplete validation)

    Defense Layers:

    1. NULL VALIDATION (Early catch)
    --------------------------------
    Checks for missing "installPath" key or null/empty values.
    Rationale: Empty values would pass validation if skipped.

    2. SYMLINK DETECTION - Layer 1 (Pre-resolution)
    -----------------------------------------------
    Calls is_symlink() BEFORE resolve() to catch obvious symlink attacks.
    Rationale: Defense in depth. If resolve() follows symlink to /etc,
               symlink check fails first and prevents that code path.
    Example: installPath = "/home/user/.claude/plugins/link"
             If link -> /etc, is_symlink() catches it before resolve()

    3. PATH RESOLUTION (Canonicalization)
    -------------------------------------
    Calls resolve() to expand symlinks and normalize path.
    Rationale: Ensures we have the actual target, not an alias.
    Example: installPath = "plugins/../.." -> resolves to /Users/user

    4. SYMLINK DETECTION - Layer 2 (Post-resolution)
    ------------------------------------------------
    Calls is_symlink() AGAIN after resolve() to catch symlinks in parent dirs.
    Rationale: What if /usr/local is a symlink to /etc? resolve() might
               have followed it. This final check catches that.
    Example: installPath = "/home" where /home -> /etc
             Layer 1 passes (not a symlink yet)
             resolve() follows it
             Layer 2 catches is_symlink() = true

    5. WHITELIST VALIDATION (Containment)
    ------------------------------------
    Verifies canonical path is within .claude/plugins/ directory.
    Rationale: Even if symlinks are resolved, absolute paths might still
               escape (e.g., if installPath = "/usr/local/something").
    Uses relative_to() which raises ValueError if outside whitelist.
    Example: installPath = "/etc/passwd"
             Even without symlinks, relative_to(.claude/plugins/) fails

    6. DIRECTORY VERIFICATION (Type checking)
    ----------------------------------------
    Verifies path exists and is a directory (not a file or special file).
    Rationale: Prevents returning paths to files, devices, or sockets.

    Why This Order Matters:
    ======================
    1. Layer 1 (symlink check before resolve): Catches obvious symlink attacks early
    2. resolve() + Layer 2 (symlink check after): Catches symlinks in parent dirs
    3. Whitelist (relative_to): Catches absolute path escapes
    4. exists() + is_dir(): Ensures we have a real directory

    If we skipped Layer 1, a symlink at this path would be followed by resolve()
    and we'd depend entirely on Layer 2 to catch it. That works, but is_symlink()
    after resolve() is less clear than before.

    If we skipped Layer 2, symlinks in parent dirs would escape (e.g., /link/path
    where /link -> /etc would become /etc/path after resolve()).

    If we skipped whitelist, an installPath like "/etc/passwd.backup" would pass
    both symlink checks but escape the plugins directory.

    Test Coverage:
    - Path Traversal: 5 unit tests covering all attack scenarios
    - Symlink Detection: 3 tests (pre-resolve, post-resolve, parent dir)
    - Whitelist Validation: 2 tests (in/out of bounds)
    - Location: tests/unit/test_agent_tracker_security.py (adapted for sync_to_installed)
    """
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
                # SECURITY: Validate path before returning

                # Handle missing or null installPath
                if "installPath" not in plugin_info:
                    return None

                if plugin_info["installPath"] is None or plugin_info["installPath"] == "":
                    return None

                install_path = Path(plugin_info["installPath"])

                # SECURITY LAYER 1: Reject symlinks immediately (defense in depth)
                # Check before resolve() to catch symlink attacks early
                if install_path.is_symlink():
                    return None

                # Resolve to canonical path (prevents path traversal)
                try:
                    canonical_path = install_path.resolve()
                except (OSError, RuntimeError) as e:
                    return None

                # SECURITY LAYER 2: Check for symlinks in resolved path
                # This catches symlinks in parent directories
                if canonical_path.is_symlink():
                    return None

                # SECURITY LAYER 3: Verify it's within .claude/plugins/ (whitelist)
                plugins_dir = (Path.home() / ".claude" / "plugins").resolve()
                try:
                    canonical_path.relative_to(plugins_dir)
                except ValueError:
                    return None

                # Verify directory exists and is a directory (not a file)
                if not canonical_path.exists():
                    return None

                if not canonical_path.is_dir():
                    return None

                return canonical_path
    except json.JSONDecodeError as e:
        print(f"❌ Invalid JSON in plugin config: {e}")
        return None
    except PermissionError as e:
        print(f"❌ Permission denied reading plugin config: {e}")
        return None
    except Exception as e:
        print(f"❌ Error reading plugin config: {e}")
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
