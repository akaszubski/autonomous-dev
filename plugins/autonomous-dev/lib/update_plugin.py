#!/usr/bin/env python3
"""
Update Plugin CLI - Interactive command-line interface for plugin updates

This module provides CLI for plugin updates with:
- Interactive confirmation prompts
- Check-only mode (dry-run)
- Non-interactive mode (--yes flag)
- JSON output for scripting
- Verbose logging
- Exit codes: 0=success, 1=error, 2=no update needed

Features:
- Parse CLI arguments (--check-only, --yes, --auto-backup, --verbose, --json)
- Display version comparison (project vs marketplace)
- Interactive confirmation prompts
- Display update summary
- Handle user consent (yes/no/cancel)

Usage:
    # Interactive update
    python update_plugin.py

    # Check for updates only
    python update_plugin.py --check-only

    # Non-interactive update
    python update_plugin.py --yes

    # JSON output for scripting
    python update_plugin.py --json

Exit Codes:
    0: Success (update performed or already up-to-date)
    1: Error (update failed)
    2: No update needed (when --check-only)

Date: 2025-11-09
Issue: GitHub #50 Phase 2 - Interactive /update-plugin command
Agent: implementer
"""

import argparse
import json
import sys
from pathlib import Path
from typing import Optional

# Add parent directory for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

from plugins.autonomous_dev.lib.plugin_updater import (
    PluginUpdater,
    UpdateResult,
    UpdateError,
)
from plugins.autonomous_dev.lib.version_detector import VersionComparison


def parse_args() -> argparse.Namespace:
    """Parse command-line arguments.

    Returns:
        argparse.Namespace with parsed arguments

    Arguments:
        --check-only: Check for updates without performing update
        --yes: Skip confirmation prompts (non-interactive mode)
        --auto-backup: Create backup before update (default: True)
        --no-backup: Skip backup creation (advanced users only)
        --verbose: Enable verbose logging
        --json: Output JSON for scripting
        --project-root: Path to project root (default: current directory)
        --plugin-name: Name of plugin to update (default: autonomous-dev)
    """
    parser = argparse.ArgumentParser(
        description="Update Claude Code plugin with version detection and backup",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Interactive update
  python update_plugin.py

  # Check for updates only
  python update_plugin.py --check-only

  # Non-interactive update
  python update_plugin.py --yes

  # Update without backup (advanced)
  python update_plugin.py --yes --no-backup

  # JSON output for scripting
  python update_plugin.py --json

Exit Codes:
  0: Success (update performed or already up-to-date)
  1: Error (update failed)
  2: No update needed (when --check-only)
        """,
    )

    parser.add_argument(
        "--check-only",
        action="store_true",
        help="Check for updates without performing update (dry-run mode)",
    )

    parser.add_argument(
        "--yes",
        "-y",
        action="store_true",
        help="Skip confirmation prompts (non-interactive mode)",
    )

    parser.add_argument(
        "--auto-backup",
        action="store_true",
        default=True,
        help="Create backup before update (default: enabled)",
    )

    parser.add_argument(
        "--no-backup",
        action="store_true",
        help="Skip backup creation (advanced users only, overrides --auto-backup)",
    )

    parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="Enable verbose logging",
    )

    parser.add_argument(
        "--json",
        action="store_true",
        help="Output JSON for scripting (machine-readable)",
    )

    parser.add_argument(
        "--project-root",
        type=str,
        default=None,
        help="Path to project root directory (default: current directory)",
    )

    parser.add_argument(
        "--plugin-name",
        type=str,
        default="autonomous-dev",
        help="Name of plugin to update (default: autonomous-dev)",
    )

    args = parser.parse_args()

    # Handle --no-backup override
    if args.no_backup:
        args.auto_backup = False

    return args


def confirm_update(version_comparison: VersionComparison) -> bool:
    """Interactive confirmation prompt for update.

    Args:
        version_comparison: VersionComparison object with version info

    Returns:
        True if user confirms, False otherwise
    """
    # Display version comparison
    print("\n" + "=" * 60)
    print("Plugin Update Available")
    print("=" * 60)
    print(f"Current version:  {version_comparison.project_version}")
    print(f"New version:      {version_comparison.marketplace_version}")
    print(f"Status:           {version_comparison.status.replace('_', ' ').title()}")
    print("=" * 60)

    # Prompt for confirmation
    while True:
        response = input("\nDo you want to proceed with the update? [y/N]: ").strip().lower()
        if response in ("y", "yes"):
            return True
        elif response in ("n", "no", ""):
            return False
        else:
            print("Invalid response. Please enter 'y' or 'n'.")


def display_version_comparison(
    version_comparison: VersionComparison,
    verbose: bool = False,
) -> None:
    """Display version comparison in human-readable format.

    Args:
        version_comparison: VersionComparison object
        verbose: Whether to show verbose details
    """
    print("\n" + "=" * 60)
    print("Version Check")
    print("=" * 60)
    print(f"Project version:     {version_comparison.project_version or 'N/A'}")
    print(f"Marketplace version: {version_comparison.marketplace_version or 'N/A'}")
    print(f"Status:              {version_comparison.status.replace('_', ' ').title()}")

    if verbose:
        print(f"Is upgrade:          {version_comparison.is_upgrade}")
        print(f"Is downgrade:        {version_comparison.is_downgrade}")
        if version_comparison.message:
            print(f"Message:             {version_comparison.message}")

    print("=" * 60 + "\n")


def display_update_summary(
    result: UpdateResult,
    json_output: bool = False,
) -> None:
    """Display update result summary.

    Args:
        result: UpdateResult object
        json_output: Whether to output JSON format
    """
    if json_output:
        # JSON output for scripting
        output = {
            "success": result.success,
            "updated": result.updated,
            "message": result.message,
            "old_version": result.old_version,
            "new_version": result.new_version,
            "backup_path": str(result.backup_path) if result.backup_path else None,
            "rollback_performed": result.rollback_performed,
            "details": result.details,
        }
        print(json.dumps(output, indent=2))
    else:
        # Human-readable output
        print("\n" + "=" * 60)
        print("Update Result")
        print("=" * 60)
        print(result.summary)
        print("=" * 60 + "\n")


def main() -> int:
    """Main CLI entry point.

    Returns:
        Exit code: 0=success, 1=error, 2=no update needed
    """
    try:
        # Parse arguments
        args = parse_args()

        # Determine project root
        project_root = Path(args.project_root) if args.project_root else Path.cwd()

        # Initialize updater
        try:
            updater = PluginUpdater(
                project_root=project_root,
                plugin_name=args.plugin_name,
            )
        except UpdateError as e:
            if args.json:
                print(json.dumps({"success": False, "error": str(e)}, indent=2))
            else:
                print(f"Error: {e}", file=sys.stderr)
            return 1

        # Check for updates
        try:
            version_comparison = updater.check_for_updates()
        except UpdateError as e:
            if args.json:
                print(json.dumps({"success": False, "error": str(e)}, indent=2))
            else:
                print(f"Error checking for updates: {e}", file=sys.stderr)
            return 1

        # Check-only mode
        if args.check_only:
            if not args.json:
                display_version_comparison(version_comparison, verbose=args.verbose)

                if version_comparison.status == VersionComparison.UP_TO_DATE:
                    print("Plugin is already up to date.")
                    return 0
                elif version_comparison.is_upgrade:
                    print("Update available.")
                    return 2
                elif version_comparison.is_downgrade:
                    print("Downgrade would occur (not recommended).")
                    return 2
                else:
                    print("Status: " + version_comparison.status)
                    return 2
            else:
                # JSON output for check-only
                output = {
                    "project_version": version_comparison.project_version,
                    "marketplace_version": version_comparison.marketplace_version,
                    "status": version_comparison.status,
                    "is_upgrade": version_comparison.is_upgrade,
                    "is_downgrade": version_comparison.is_downgrade,
                    "message": version_comparison.message,
                }
                print(json.dumps(output, indent=2))

                if version_comparison.status == VersionComparison.UP_TO_DATE:
                    return 0
                else:
                    return 2

        # Already up-to-date
        if version_comparison.status == VersionComparison.UP_TO_DATE:
            if not args.json:
                print("Plugin is already up to date.")
            else:
                print(json.dumps({
                    "success": True,
                    "updated": False,
                    "message": "Plugin is already up to date",
                    "version": version_comparison.project_version,
                }, indent=2))
            return 0

        # Interactive confirmation (unless --yes)
        if not args.yes and not args.json:
            if not confirm_update(version_comparison):
                print("Update cancelled by user.")
                return 0

        # Perform update
        if args.verbose and not args.json:
            print(f"\nUpdating {args.plugin_name}...")
            if args.auto_backup:
                print("Creating backup...")

        try:
            result = updater.update(
                auto_backup=args.auto_backup,
                skip_confirm=args.yes,
            )
        except UpdateError as e:
            if args.json:
                print(json.dumps({"success": False, "error": str(e)}, indent=2))
            else:
                print(f"Update failed: {e}", file=sys.stderr)
            return 1

        # Display result
        display_update_summary(result, json_output=args.json)

        # Return exit code
        if result.success:
            return 0
        else:
            return 1

    except KeyboardInterrupt:
        print("\nUpdate cancelled by user.", file=sys.stderr)
        return 1
    except Exception as e:
        if args.json if 'args' in locals() else False:
            print(json.dumps({"success": False, "error": str(e)}, indent=2))
        else:
            print(f"Unexpected error: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
