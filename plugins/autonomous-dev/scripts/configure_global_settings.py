#!/usr/bin/env python3
"""
Configure Global Settings CLI - Fresh install permission configuration

Creates or updates ~/.claude/settings.json with correct permission patterns
for Claude Code 2.0. This script is called by install.sh during fresh install.

Features:
1. Fresh install: Create ~/.claude/settings.json from template
2. Upgrade: Preserve user customizations while fixing broken patterns
3. Broken patterns: Replace Bash(:*) with specific safe patterns
4. Non-blocking: Exit 0 even on errors (installation continues)
5. JSON output: Return structured data for install.sh consumption
6. Directory creation: Create ~/.claude/ if missing

Security:
- Path validation (CWE-22, CWE-59)
- Atomic writes with secure permissions
- Backup before modification
- No wildcards (Bash(git:*) NOT Bash(*))

Usage:
    # Fresh install (no existing settings)
    python3 configure_global_settings.py --template /path/to/template.json

    # Upgrade (existing settings, preserve customizations)
    python3 configure_global_settings.py --template /path/to/template.json --home ~/.claude

Output:
    JSON to stdout: {"success": bool, "created": bool, "message": str, ...}
    Exit code: Always 0 (non-blocking for install.sh)

See Also:
    - plugins/autonomous-dev/lib/settings_generator.py for merge logic
    - plugins/autonomous-dev/config/global_settings_template.json for template
    - tests/unit/scripts/test_configure_global_settings.py for test cases
    - GitHub Issue #116 for requirements

Date: 2025-12-13
Issue: GitHub #116
Agent: implementer
"""

import argparse
import json
import os
import sys
import tempfile
from pathlib import Path
from typing import Dict, Any

# Add lib to path for imports
try:
    # Try package import first
    from autonomous_dev.lib.settings_generator import SettingsGenerator, SettingsGeneratorError
except ImportError:
    # Fallback for direct script execution
    lib_path = Path(__file__).parent.parent / "lib"
    sys.path.insert(0, str(lib_path))
    from settings_generator import SettingsGenerator, SettingsGeneratorError


def _prepare_local_plugin_hooks(claude_dir: Path) -> tuple[dict | None, int]:
    """Read and validate local settings before either settings file changes."""
    local_path = claude_dir / "settings.local.json"
    if not local_path.exists():
        return None, 0
    from sync_settings_hooks import _strip_plugin_owned
    data = json.loads(local_path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"Expected settings object: {local_path}")
    hooks, removed = _strip_plugin_owned(data.get("hooks", {}))
    if removed:
        data["hooks"] = hooks
    return data, removed


def _save_global_backup(global_path: Path) -> None:
    """Preserve the historical upgrade backup before changing either tier."""
    fd, temporary = tempfile.mkstemp(dir=str(global_path.parent), prefix=".settings.backup.")
    try:
        with os.fdopen(fd, "wb") as stream:
            stream.write(global_path.read_bytes())
            stream.flush()
            os.fsync(stream.fileno())
        os.chmod(temporary, 0o600)
        os.replace(temporary, global_path.with_suffix(".json.backup"))
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def create_fresh_settings(template_path: Path, global_path: Path) -> Dict[str, Any]:
    """Create fresh settings.json from template.

    Args:
        template_path: Path to global_settings_template.json
        global_path: Path to ~/.claude/settings.json

    Returns:
        Result dict with success status and metadata
    """
    try:
        # Validate template exists
        if not template_path.exists():
            return {
                "success": False,
                "created": False,
                "message": f"Template file not found: {template_path}",
                "error": "template_not_found"
            }

        # Ensure ~/.claude/ directory exists
        claude_dir = global_path.parent
        if not ensure_claude_directory(claude_dir):
            return {
                "success": False,
                "created": False,
                "message": f"Failed to create directory: {claude_dir}",
                "error": "directory_creation_failed"
            }

        # Read template
        template_content = template_path.read_text()
        template_settings = json.loads(template_content)

        from sync_settings_hooks import _write_settings_transaction, _strip_plugin_owned
        if not isinstance(template_settings, dict):
            raise ValueError(f"Expected settings object: {template_path}")
        _strip_plugin_owned(template_settings.get("hooks", {}))
        local_settings, local_removed = _prepare_local_plugin_hooks(claude_dir)
        updates = {global_path: template_settings}
        if local_removed:
            updates[claude_dir / "settings.local.json"] = local_settings
        _write_settings_transaction(updates)

        return {
            "success": True,
            "created": True,
            "message": "Fresh install: Created settings.json from template",
            "path": str(global_path),
            "patterns_count": len(template_settings.get("permissions", {}).get("allow", []))
        }

    except PermissionError as e:
        return {
            "success": False,
            "created": False,
            "message": f"Permission denied: {e}",
            "error": "permission_denied"
        }
    except json.JSONDecodeError as e:
        return {
            "success": False,
            "created": False,
            "message": f"Invalid JSON in template: {e}",
            "error": "invalid_template_json"
        }
    except Exception as e:
        return {
            "success": False,
            "created": False,
            "message": f"Unexpected error: {e}",
            "error": "unexpected_error"
        }


def upgrade_existing_settings(global_path: Path, template_path: Path) -> Dict[str, Any]:
    """Upgrade existing settings while preserving user customizations.

    Args:
        global_path: Path to existing ~/.claude/settings.json
        template_path: Path to global_settings_template.json

    Returns:
        Result dict with success status and metadata
    """
    try:
        # Validate inputs
        if not global_path.exists():
            return {
                "success": False,
                "created": False,
                "message": f"Settings file not found: {global_path}",
                "error": "settings_not_found"
            }

        if not template_path.exists():
            return {
                "success": False,
                "created": False,
                "message": f"Template file not found: {template_path}",
                "error": "template_not_found"
            }

        from sync_settings_hooks import _write_settings_transaction, _strip_plugin_owned
        template_settings = json.loads(template_path.read_text(encoding="utf-8"))
        existing_settings = json.loads(global_path.read_text(encoding="utf-8"))
        if not isinstance(template_settings, dict) or not isinstance(existing_settings, dict):
            raise ValueError("Expected global settings objects")
        template_settings["hooks"], _ = _strip_plugin_owned(template_settings.get("hooks", {}))
        existing_settings["hooks"], _ = _strip_plugin_owned(existing_settings.get("hooks", {}))
        local_settings, local_removed = _prepare_local_plugin_hooks(global_path.parent)
        generator = SettingsGenerator(project_root=Path.home())
        merged_settings = generator._deep_merge_settings(template_settings, existing_settings, True)
        generator._validate_merged_settings(merged_settings)
        updates = {global_path: merged_settings}
        if local_removed:
            updates[global_path.with_name("settings.local.json")] = local_settings
        _save_global_backup(global_path)
        _write_settings_transaction(updates)

        # Count patterns fixed (check if Bash(:*) was in original)
        patterns_fixed = 0
        original_allow = existing_settings.get("permissions", {}).get("allow", [])
        patterns_fixed = sum(pattern in ["Bash(:*)", "Bash(*)"] for pattern in original_allow)

        # Build message based on patterns fixed
        if patterns_fixed > 0:
            message = f"Settings upgraded successfully (fixed {patterns_fixed} broken patterns, preserved customizations)"
        else:
            message = "Settings upgraded successfully (preserved customizations)"

        return {
            "success": True,
            "created": False,
            "message": message,
            "merged": True,
            "patterns_fixed": patterns_fixed,
            "path": str(global_path)
        }

    except SettingsGeneratorError as e:
        return {
            "success": False,
            "created": False,
            "message": f"Settings merge error: {e}",
            "error": "merge_failed"
        }

    except PermissionError as e:
        return {
            "success": False,
            "created": False,
            "message": f"Permission denied: {e}",
            "error": "permission_denied"
        }
    except Exception as e:
        return {
            "success": False,
            "created": False,
            "message": f"Unexpected error: {e}",
            "error": "unexpected_error"
        }


def ensure_claude_directory(claude_dir: Path) -> bool:
    """Ensure ~/.claude/ directory exists with correct permissions.

    Args:
        claude_dir: Path to ~/.claude/ directory

    Returns:
        True if directory exists/created, False on error
    """
    try:
        # Create directory if missing (mkdir -p behavior)
        claude_dir.mkdir(parents=True, exist_ok=True)

        # Set permissions (owner read/write/execute)
        claude_dir.chmod(0o700)

        return True

    except PermissionError:
        return False
    except Exception:
        return False


def main():
    """Main entry point for CLI."""
    parser = argparse.ArgumentParser(
        description="Configure ~/.claude/settings.json for autonomous-dev plugin",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    # Fresh install
    %(prog)s --template global_settings_template.json

    # Upgrade with custom home
    %(prog)s --template global_settings_template.json --home ~/.claude

Exit Code:
    Always exits 0 (non-blocking for install.sh)
    Check JSON output "success" field for actual status
        """
    )

    parser.add_argument(
        "--template",
        type=Path,
        required=True,
        help="Path to global_settings_template.json"
    )

    parser.add_argument(
        "--home",
        type=Path,
        default=Path.home() / ".claude",
        help="Path to .claude directory (default: ~/.claude)"
    )

    parser.add_argument(
        "--staging",
        type=Path,
        help="Path to staging directory (unused, for compatibility)"
    )

    args = parser.parse_args()

    # Determine global_path
    global_path = args.home / "settings.json"

    # Check if settings.json already exists
    if global_path.exists():
        # Upgrade scenario: merge with existing settings
        result = upgrade_existing_settings(global_path, args.template)
    else:
        # Fresh install scenario: create from template
        result = create_fresh_settings(args.template, global_path)

    # Output JSON to stdout
    print(json.dumps(result, indent=2))

    # Always exit 0 (non-blocking for install.sh)
    sys.exit(0)


if __name__ == "__main__":
    main()
