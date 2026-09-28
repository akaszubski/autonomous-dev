#!/usr/bin/env python3
"""
Sync TOOLKIT-OWNED settings.json hooks and permissions during deploy.

Updates only the entries the toolkit owns — hook registrations whose command
references a hook script declared by ``install_manifest.json`` or the template,
and the canonical ``permissions.deny`` entries. A consumer's own hooks on the
SAME lifecycle event, their custom deny/allow/ask entries, ``env``, and every
other key survive untouched.

History of this file's write strategy:

* v1 used ``SettingsMerger.merge_settings()`` — ADDITIVE hook merging, which
  duplicated hooks on every deploy run.
* v2 (#648) did a full REPLACE of the ``hooks`` key and of
  ``permissions.deny``. That fixed the duplication and introduced a worse
  defect: it DELETED every consumer hook on a shared lifecycle event and every
  custom deny entry. Measured against a populated consumer file: a user's own
  SessionStart notifier, their own PostToolUse audit hook, and their custom
  deny rule all destroyed, while the writer reported success.
* v3 (#1809, current) delegates the write to
  ``settings_merger.apply_owned_settings`` — the single canonical
  ownership-aware owner. Idempotent like v2, preserving like v1, and it REFUSES
  (rather than guessing) on a live pipeline run, malformed/ambiguous settings,
  or a concurrent modification.

The CLI contract ``scripts/deploy-all.sh`` depends on is unchanged; only the
write path moved. A refusal is reported as ``success: false`` with a
``refusal_class`` and exits non-zero — never as success.

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
import sys
from pathlib import Path
from typing import Any, Dict


# The 7 canonical global hooks (Issue #944) live in ~/.claude/settings.json.
# A copy in project-tier settings.local.json double-fires across tiers, so the
# stale-local detector must flag them even though the per-repo template
# (settings.default.json) intentionally omits them.
_CANONICAL_GLOBAL_HOOK_BASENAMES = frozenset({
    "unified_prompt_validator.py", "plan_gate.py", "plan_mode_exit_detector.py",
    "stop_quality_gate.py", "task_completed_handler.py",
    "unified_session_tracker.py", "conversation_archiver.py",
})


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

    The per-repo template (``settings.default.json``, Issue #944) intentionally
    OMITS the 7 canonical GLOBAL hooks — those live in the global tier
    (``~/.claude/settings.json``). So the flag set is the UNION of the per-repo
    template hooks AND the canonical global-hook basenames: a copy in
    ``settings.local.json`` of a canonical global hook double-fires across
    tiers even though it is absent from the per-repo template
    (Issue #1036 / #944).

    Args:
        user_path: Path to the user's ``settings.json``. Sibling
            ``settings.local.json`` is inspected next to it.
        template_hooks: The canonical hooks dict that will be written to
            ``settings.json`` (used to derive expected basenames).

    Returns:
        Sorted list of hook basenames present in ``settings.local.json`` that
        duplicate EITHER the per-repo template hooks OR a canonical global
        hook. Empty list when no overlap or when ``settings.local.json`` is
        missing/malformed.
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
    flaggable = extract_hook_refs(canonical_settings) | _CANONICAL_GLOBAL_HOOK_BASENAMES
    local_refs = extract_hook_refs(local_data)
    return sorted(flaggable & local_refs)


def _replace_hooks(
    user_path: Path, template_path: Path, *, dry_run: bool = False
) -> Dict[str, Any]:
    """Update TOOLKIT-OWNED settings entries from the template. Preserve the rest.

    Issue #1809: this function used to do ``user_settings["hooks"] =
    template_hooks`` plus ``permissions["deny"] = canonical_deny``, which
    destroyed a consumer's own hooks on any lifecycle event the toolkit also
    used, and every custom deny entry. Both wholesale-replacement blocks are
    RETIRED — not kept as a fallback. The write now delegates to the single
    canonical owner, ``settings_merger.apply_owned_settings``, which replaces
    only manifest-attributed toolkit-owned entries.

    The name and the return contract are unchanged so ``scripts/deploy-all.sh``
    and every existing caller keep working: the ROUTE stays, the WRITE moved.

    Args:
        user_path: Path to the user's settings.json
        template_path: Path to the template settings file
        dry_run: If True, compute changes but do not write

    Returns:
        Result dict with success status and hook counts. A refusal returns
        ``success: False`` with a ``refusal_class`` and a durable ``message`` —
        it is never reported as success.

    Raises:
        json.JSONDecodeError: If the TEMPLATE contains invalid JSON. A malformed
            TARGET is a structured refusal, not an exception (#1809): callers
            like deploy-all.sh swallow exceptions as warnings, so the refusal
            needs an observable reason in the result.
    """
    _setup_imports()
    from settings_merger import apply_owned_settings

    # Read template (a broken template is a deploy-artifact bug, not consumer
    # state — it still raises so the packaging error is loud).
    template = json.loads(template_path.read_text(encoding="utf-8"))
    template_hooks = template.get("hooks", {})

    old_events = set()
    if user_path.exists():
        try:
            existing = json.loads(user_path.read_text(encoding="utf-8"))
            if isinstance(existing, dict) and isinstance(existing.get("hooks"), dict):
                old_events = set(existing["hooks"].keys())
        except (OSError, json.JSONDecodeError):
            # Malformed target: apply_owned_settings refuses below with a reason.
            old_events = set()

    new_events = set(template_hooks.keys())

    canonical_deny = _get_canonical_deny_list()
    manifest_path = _find_plugin_root() / "config" / "install_manifest.json"

    outcome = apply_owned_settings(
        user_path,
        template,
        manifest_path=manifest_path if manifest_path.exists() else None,
        owned_deny=canonical_deny or None,
        dry_run=dry_run,
    )

    if not outcome.success:
        return {
            "success": False,
            "hooks_added": 0,
            "hooks_preserved": 0,
            "hooks_migrated": 0,
            "total_lifecycle_events": 0,
            "deny_synced": False,
            "deny_errors_fixed": 0,
            "refusal_class": outcome.refusal_class,
            "stale_local_warnings": [],
            "message": f"Refused ({outcome.refusal_class}): {outcome.reason}",
        }

    deny_synced = outcome.permissions_synced
    deny_errors_fixed = len(outcome.details.get("deny_dropped", []))

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
        "refusal_class": "",
        "foreign_hooks_preserved": outcome.foreign_hooks_preserved,
        "stale_local_warnings": stale_local_warnings,
        "message": (
            f"Owned hooks updated: {total_events} lifecycle events "
            f"({hooks_added} added, {hooks_preserved} updated), "
            f"{outcome.foreign_hooks_preserved} unrelated hooks preserved"
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
    # Per-repo deploy must emit the PROJECT-LOCAL canonical hook paths
    # (${CLAUDE_PROJECT_DIR:-$(git rev-parse --show-toplevel)}/.claude/hooks/...),
    # NOT the global ~/.claude/ paths. The global template is reserved for
    # sync_global(). (Issue #1036 / #996 AC7 / #648)
    template_path = plugin_root / "templates" / "settings.default.json"
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
