#!/usr/bin/env python3
"""
Sync settings.json hooks and permissions during deploy.

Replaces the hooks key in settings.json with the canonical template hooks,
and syncs permissions.deny from the generator's canonical DEFAULT_DENY_LIST
to prevent stale/invalid patterns from persisting across deploys.

Previous implementation used SettingsMerger.merge_settings() which did ADDITIVE
hook merging, causing duplicate hooks on each deploy run. This version does a
full REPLACE of the hooks key to ensure idempotency.

Usage:
    # Global mode: replace hooks in ~/.claude/settings.json from template
    python3 sync_settings_hooks.py --global

    # Per-repo mode: replace hooks in <repo>/.claude/settings.json from template
    python3 sync_settings_hooks.py --repo /path/to/repo

    # Dry-run (no writes)
    python3 sync_settings_hooks.py --global --dry-run

    # Count-only (output hook count)
    python3 sync_settings_hooks.py --repo /path/to/repo --count-only

Output:
    JSON to stdout: {"success": bool, "hooks_added": int, "hooks_preserved": int,
                     "hooks_migrated": int, "total_lifecycle_events": int, "message": str}
    Exit code: 0 on success, 1 on error

Issue: GitHub #648
Date: 2026-04-03
Agent: implementer
"""

import argparse
import json
import os
import sys
import tempfile
from pathlib import Path
from typing import Any, Dict


def _find_plugin_root() -> Path:
    """Find the plugin source directory relative to this script.

    Returns:
        Path to plugins/autonomous-dev/
    """
    return Path(__file__).resolve().parent.parent


def _setup_imports() -> None:
    """Add lib directory to sys.path for imports."""
    lib_path = _find_plugin_root() / "lib"
    if str(lib_path) not in sys.path:
        sys.path.insert(0, str(lib_path))


def _get_canonical_deny_list() -> list:
    """Get the canonical deny list from settings_generator.DEFAULT_DENY_LIST.

    Returns:
        List of deny patterns from the generator, or empty list if import fails.
    """
    _setup_imports()
    try:
        from settings_generator import DEFAULT_DENY_LIST
        return list(DEFAULT_DENY_LIST)
    except ImportError:
        return []


def _validate_permission_patterns(patterns: list) -> list:
    """Validate permission patterns for known syntax errors.

    Claude Code requires :* only at the end of a pattern (prefix matching).
    Patterns like Bash(brew:*install*) are invalid because :* is mid-string.

    Args:
        patterns: List of permission pattern strings

    Returns:
        List of invalid patterns with descriptions
    """
    errors = []
    import re
    for pattern in patterns:
        # Match Tool(content) patterns
        m = re.match(r'^(\w+)\((.+)\)$', pattern)
        if not m:
            continue
        content = m.group(2)
        # Check for :* not at the end — the actual invalid syntax
        # Valid: "sudo:*" (colon-star at end = prefix match)
        # Invalid: "brew:*install*" (colon-star in middle)
        if ':*' in content and not content.endswith(':*'):
            errors.append(pattern)
    return errors


def _count_lifecycle_events(settings_path: Path) -> int:
    """Count the number of lifecycle events with hooks in a settings file.

    Args:
        settings_path: Path to settings.json

    Returns:
        Number of lifecycle event keys in the hooks dict
    """
    if not settings_path.exists():
        return 0
    try:
        data = json.loads(settings_path.read_text(encoding="utf-8"))
        return len(data.get("hooks", {}))
    except (json.JSONDecodeError, OSError):
        return 0


def _detect_stale_local_warnings(
    user_path: Path, template_hooks: Dict[str, Any]
) -> list:
    """Detect hook refs in settings.local.json that duplicate template hooks.

    Both ``settings.json`` and ``settings.local.json`` are project-tier
    settings; Claude Code merges them, so any hook basename present in BOTH
    fires twice (Issue #1183, root-cause follow-up to #1176).

    The current ``templates/settings.local.json`` carries no hooks, so a
    legacy ``settings.local.json`` on an upgrading repo is the only way
    this warning fires.

    Args:
        user_path: Path to the user's ``settings.json``. Sibling
            ``settings.local.json`` is inspected next to it.
        template_hooks: The canonical hooks dict that will be written to
            ``settings.json`` (used to derive expected basenames).

    Returns:
        Sorted list of hook basenames present in BOTH ``settings.local.json``
        and the template's canonical hooks. Empty list when no overlap or
        when ``settings.local.json`` is missing/malformed.
    """
    local_path = user_path.parent / "settings.local.json"
    if not local_path.exists():
        return []

    _setup_imports()
    try:
        from settings_merger import extract_hook_refs
    except ImportError:
        return []

    try:
        local_data = json.loads(local_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return []

    if not isinstance(local_data, dict):
        return []

    canonical_settings = {"hooks": template_hooks}
    canonical_refs = extract_hook_refs(canonical_settings)
    local_refs = extract_hook_refs(local_data)
    return sorted(canonical_refs & local_refs)


def _replace_hooks(
    user_path: Path, template_path: Path, *, dry_run: bool = False
) -> Dict[str, Any]:
    """Replace hooks key in settings from template, preserving all other keys.

    This is the core fix for the duplicate hooks bug. Instead of additively
    merging hooks (which duplicates them on each run), we replace the entire
    hooks key with the template's canonical hooks.

    Args:
        user_path: Path to the user's settings.json
        template_path: Path to the template settings file
        dry_run: If True, compute changes but do not write

    Returns:
        Result dict with success status and hook counts

    Raises:
        json.JSONDecodeError: If template or existing settings contain invalid JSON
    """
    # Read template
    template = json.loads(template_path.read_text(encoding="utf-8"))
    template_hooks = template.get("hooks", {})

    # Read existing settings (or create empty)
    if user_path.exists():
        user_settings = json.loads(user_path.read_text(encoding="utf-8"))
    else:
        user_settings = {}

    # Count what's changing
    old_hooks = user_settings.get("hooks", {})
    old_events = set(old_hooks.keys())
    new_events = set(template_hooks.keys())

    # Replace hooks entirely
    user_settings["hooks"] = template_hooks

    # Sync permissions.deny from canonical generator list
    canonical_deny = _get_canonical_deny_list()
    deny_synced = False
    deny_errors_fixed = 0
    if canonical_deny:
        old_deny = user_settings.get("permissions", {}).get("deny", [])
        # Validate old deny list for known bad patterns
        bad_patterns = _validate_permission_patterns(old_deny)
        if bad_patterns or old_deny != canonical_deny:
            if "permissions" not in user_settings:
                user_settings["permissions"] = {}
            user_settings["permissions"]["deny"] = canonical_deny
            deny_synced = True
            deny_errors_fixed = len(bad_patterns)

    if not dry_run:
        # Atomic write
        user_path.parent.mkdir(parents=True, exist_ok=True)
        fd, tmp = tempfile.mkstemp(dir=str(user_path.parent), suffix=".tmp")
        try:
            with os.fdopen(fd, "w") as f:
                json.dump(user_settings, f, indent=2)
                f.write("\n")
            os.chmod(tmp, 0o600)
            os.replace(tmp, str(user_path))
        except Exception:
            try:
                os.unlink(tmp)
            except OSError:
                pass
            raise

    total_events = len(template_hooks)
    hooks_added = len(new_events - old_events)
    hooks_preserved = len(new_events & old_events)

    deny_msg = ""
    if deny_synced:
        deny_msg = f", deny list synced ({deny_errors_fixed} invalid patterns fixed)"

    # Issue #1183: detect legacy settings.local.json that still registers
    # canonical hooks → would cause same-tier duplicate firings.
    stale_local_warnings = _detect_stale_local_warnings(user_path, template_hooks)
    stale_msg = ""
    if stale_local_warnings:
        stale_msg = (
            f"; WARNING: settings.local.json still registers "
            f"{len(stale_local_warnings)} duplicate hooks — "
            f"re-run sync after upgrade"
        )

    return {
        "success": True,
        "hooks_added": hooks_added,
        "hooks_preserved": hooks_preserved,
        "hooks_migrated": 0,
        "total_lifecycle_events": total_events,
        "deny_synced": deny_synced,
        "deny_errors_fixed": deny_errors_fixed,
        "stale_local_warnings": stale_local_warnings,
        "message": (
            f"Hooks replaced: {total_events} lifecycle events "
            f"({hooks_added} added, {hooks_preserved} updated)"
            f"{deny_msg}"
            f"{stale_msg}"
        ),
    }


def sync_global(*, dry_run: bool = False, count_only: bool = False) -> Dict[str, Any]:
    """Sync global settings.json hook registrations.

    Replaces hooks in ~/.claude/settings.json from global_settings_template.json.

    Args:
        dry_run: If True, compute changes without writing
        count_only: If True, only return hook count

    Returns:
        Result dict with success status and hook counts
    """
    plugin_root = _find_plugin_root()
    template_path = plugin_root / "config" / "global_settings_template.json"
    user_path = Path.home() / ".claude" / "settings.json"

    if count_only:
        count = _count_lifecycle_events(user_path)
        return {
            "success": True,
            "hooks_added": 0,
            "hooks_preserved": 0,
            "hooks_migrated": 0,
            "total_lifecycle_events": count,
            "message": f"Hook count: {count} lifecycle events",
        }

    if not template_path.exists():
        return {
            "success": False,
            "hooks_added": 0,
            "hooks_preserved": 0,
            "hooks_migrated": 0,
            "total_lifecycle_events": 0,
            "message": f"Template not found: {template_path}",
        }

    return _replace_hooks(user_path, template_path, dry_run=dry_run)


def sync_repo(
    repo_path: str, *, dry_run: bool = False, count_only: bool = False
) -> Dict[str, Any]:
    """Sync per-repo settings.json hook registrations.

    Replaces hooks in <repo>/.claude/settings.json from settings.default.json.

    Args:
        repo_path: Path to the repository root
        dry_run: If True, compute changes without writing
        count_only: If True, only return hook count

    Returns:
        Result dict with success status and hook counts
    """
    plugin_root = _find_plugin_root()
    template_path = plugin_root / "config" / "global_settings_template.json"
    repo = Path(repo_path)
    user_path = repo / ".claude" / "settings.json"

    if count_only:
        count = _count_lifecycle_events(user_path)
        return {
            "success": True,
            "hooks_added": 0,
            "hooks_preserved": 0,
            "hooks_migrated": 0,
            "total_lifecycle_events": count,
            "message": f"Hook count: {count} lifecycle events",
        }

    if not template_path.exists():
        return {
            "success": False,
            "hooks_added": 0,
            "hooks_preserved": 0,
            "hooks_migrated": 0,
            "total_lifecycle_events": 0,
            "message": f"Template not found: {template_path}",
        }

    if not repo.is_dir():
        return {
            "success": False,
            "hooks_added": 0,
            "hooks_preserved": 0,
            "hooks_migrated": 0,
            "total_lifecycle_events": 0,
            "message": f"Repository path not found: {repo_path}",
        }

    return _replace_hooks(user_path, template_path, dry_run=dry_run)


def main() -> None:
    """Main entry point for CLI."""
    parser = argparse.ArgumentParser(
        description="Sync settings.json hook registrations during deploy",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )

    mode_group = parser.add_mutually_exclusive_group(required=True)
    mode_group.add_argument(
        "--global",
        dest="global_mode",
        action="store_true",
        help="Sync global ~/.claude/settings.json hooks",
    )
    mode_group.add_argument(
        "--repo",
        type=str,
        help="Sync per-repo <path>/.claude/settings.json hooks",
    )

    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Merge without writing (preview changes)",
    )
    parser.add_argument(
        "--count-only",
        action="store_true",
        help="Output registered hook count only",
    )

    args = parser.parse_args()

    try:
        if args.global_mode:
            result = sync_global(dry_run=args.dry_run, count_only=args.count_only)
        else:
            result = sync_repo(args.repo, dry_run=args.dry_run, count_only=args.count_only)

        print(json.dumps(result, indent=2))
        sys.exit(0 if result["success"] else 1)

    except Exception as e:
        error_result = {
            "success": False,
            "hooks_added": 0,
            "hooks_preserved": 0,
            "hooks_migrated": 0,
            "total_lifecycle_events": 0,
            "message": f"Unexpected error: {e}",
        }
        print(json.dumps(error_result, indent=2))
        sys.exit(1)


if __name__ == "__main__":
    main()
