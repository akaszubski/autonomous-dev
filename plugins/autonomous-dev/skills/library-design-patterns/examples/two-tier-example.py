#!/usr/bin/env python3
"""Two-tier design example from plugin_updater.py.

This example demonstrates the two-tier design pattern used in
autonomous-dev's plugin update functionality:
- Tier 1 (plugin_updater.py): Core business logic
- Tier 2 (update_plugin.py): CLI interface

See:
    - plugins/autonomous-dev/lib/plugin_updater.py (actual Tier 1)
    - plugins/autonomous-dev/lib/update_plugin.py (actual Tier 2)
    - skills/library-design-patterns/docs/two-tier-design.md
"""

from dataclasses import dataclass
from pathlib import Path
from typing import Optional
import subprocess


# ============================================================================
# TIER 1: CORE LIBRARY (plugin_updater.py pattern)
# ============================================================================

@dataclass
class UpdateResult:
    """Result of plugin update operation."""
    success: bool
    version_from: str
    version_to: str
    backup_path: Optional[Path] = None
    error_message: Optional[str] = None


class PluginUpdateError(Exception):
    """Raised when plugin update fails."""
    pass


def update_plugin(
    plugin_name: str,
    *,
    backup: bool = True,
    dry_run: bool = False
) -> UpdateResult:
    """Update plugin to latest version (TIER 1: Pure business logic).

    This function contains NO CLI assumptions:
    - No print() statements
    - No input() calls
    - Returns structured data (dataclass)
    - Raises semantic exceptions

    Benefits:
    - Can be imported and used in any context
    - Easy to unit test
    - Reusable across CLI, API, agents

    Args:
        plugin_name: Name of plugin to update
        backup: Whether to create backup before update (default: True)
        dry_run: Whether to simulate without changes (default: False)

    Returns:
        UpdateResult with operation details

    Raises:
        PluginUpdateError: If update fails
        FileNotFoundError: If plugin not found
    """
    # Detect current version (pure logic)
    current_version = _detect_plugin_version(plugin_name)

    # Fetch latest version (pure logic)
    latest_version = _fetch_latest_version(plugin_name)

    # Already at latest version
    if current_version == latest_version:
        return UpdateResult(
            success=True,
            version_from=current_version,
            version_to=latest_version,
            backup_path=None
        )

    # Dry run mode
    if dry_run:
        return UpdateResult(
            success=True,
            version_from=current_version,
            version_to=latest_version,
            backup_path=None
        )

    # Create backup if requested
    backup_path = None
    if backup:
        backup_path = _create_backup(plugin_name, current_version)

    # Perform update
    try:
        _perform_update(plugin_name, latest_version)
        return UpdateResult(
            success=True,
            version_from=current_version,
            version_to=latest_version,
            backup_path=backup_path
        )
    except Exception as e:
        # Restore from backup if update failed
        if backup_path:
            _restore_from_backup(plugin_name, backup_path)
        raise PluginUpdateError(f"Update failed: {e}")


def _detect_plugin_version(plugin_name: str) -> str:
    """Detect current plugin version."""
    # Simplified for example
    return "1.0.0"


def _fetch_latest_version(plugin_name: str) -> str:
    """Fetch latest version from marketplace."""
    # Simplified for example
    return "1.1.0"


def _create_backup(plugin_name: str, version: str) -> Path:
    """Create backup of current plugin version."""
    # Simplified for example
    backup_dir = Path(f"~/.autonomous-dev/backups/{plugin_name}").expanduser()
    backup_dir.mkdir(parents=True, exist_ok=True)
    backup_path = backup_dir / f"{plugin_name}-{version}.backup"
    # ... create backup ...
    return backup_path


def _restore_from_backup(plugin_name: str, backup_path: Path):
    """Restore plugin from backup."""
    # Simplified for example
    pass


def _perform_update(plugin_name: str, version: str):
    """Perform actual plugin update."""
    # Simplified for example
    subprocess.run(
        ["gh", "release", "download", f"v{version}"],
        check=True,
        capture_output=True
    )


# ============================================================================
# TIER 2: CLI INTERFACE (update_plugin.py pattern)
# ============================================================================

def main():
    """CLI interface for plugin updates (TIER 2: User interaction).

    This function handles:
    - Argument parsing (CLI-specific)
    - User interaction (prompts, confirmation)
    - Output formatting (pretty-printing)
    - Exit codes (terminal convention)

    All business logic delegated to Tier 1 (update_plugin function).
    """
    import argparse
    import sys

    # Argument parsing (CLI-specific)
    parser = argparse.ArgumentParser(description="Update autonomous-dev plugin")
    parser.add_argument("plugin_name", help="Plugin to update")
    parser.add_argument("--no-backup", action="store_true", help="Skip backup")
    parser.add_argument("--dry-run", action="store_true", help="Simulate update")
    parser.add_argument("--yes", action="store_true", help="Skip confirmation")

    args = parser.parse_args()

    # User interaction (CLI-specific)
    if not args.yes and not args.dry_run:
        confirm = input(f"Update {args.plugin_name}? [y/N]: ")
        if confirm.lower() != 'y':
            print("Update cancelled")
            return 0

    # Delegate to core library (Tier 1)
    try:
        result = update_plugin(
            args.plugin_name,
            backup=not args.no_backup,
            dry_run=args.dry_run
        )

        # Format output for CLI (CLI-specific)
        if result.success:
            if args.dry_run:
                print(f"✅ DRY RUN: Would update {args.plugin_name}")
                print(f"   {result.version_from} → {result.version_to}")
            else:
                print(f"✅ Updated {args.plugin_name}")
                print(f"   {result.version_from} → {result.version_to}")
                if result.backup_path:
                    print(f"   Backup: {result.backup_path}")
            return 0  # Success exit code

        else:
            print(f"❌ Update failed: {result.error_message}")
            return 1  # Error exit code

    except PluginUpdateError as e:
        print(f"❌ Update error: {e}", file=sys.stderr)
        return 1

    except FileNotFoundError as e:
        print(f"❌ Plugin not found: {e}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    import sys
    sys.exit(main())


# ============================================================================
# USAGE EXAMPLES
# ============================================================================

def example_usage():
    """Demonstrate reusability of Tier 1 library."""

    # Example 1: Use from CLI
    # $ python update_plugin.py autonomous-dev
    # ✅ Updated autonomous-dev
    #    1.0.0 → 1.1.0
    #    Backup: ~/.autonomous-dev/backups/autonomous-dev-1.0.0.backup

    # Example 2: Use from Python code
    result = update_plugin("autonomous-dev")
    if result.success:
        print(f"Updated to {result.version_to}")

    # Example 3: Use from tests
    def test_update_plugin():
        result = update_plugin("test-plugin", dry_run=True)
        assert result.success
        assert result.version_to > result.version_from

    # Example 4: Use from another agent/workflow
    def auto_update_plugins():
        plugins = ["plugin1", "plugin2", "plugin3"]
        for plugin in plugins:
            result = update_plugin(plugin, backup=True)
            if not result.success:
                print(f"Failed to update {plugin}: {result.error_message}")

    # All examples use the same Tier 1 library!
    # This is the power of two-tier design.
