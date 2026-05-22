#!/usr/bin/env python3
"""Uninstall: Strip autonomous-dev hooks from a per-repo settings.json - Issue #951.

Companion helper for ``install.sh --uninstall``. Removes autonomous-dev's
hook entries from ``<repo>/.claude/settings.json`` while preserving every
other top-level key (permissions, mcpServers, env, model, custom hook
extensions, etc.).

This is intentionally a single-file self-contained script. The shell
uninstall path is designed to survive a partially-broken install — cross
imports from ``plugins/.../lib/uninstall_orchestrator.py`` would introduce
failure modes (broken installs, missing sys.path entries) that defeat the
recovery purpose. We accept the duplication.

CLI contract (mirrors ``reset_global_hooks.py``):
    - ALWAYS print JSON to stdout.
    - ALWAYS exit 0 unless argparse rejects the args.
    - install.sh consumes the JSON via subprocess + json.loads.

Result JSON shape::

    {
      "success": true,
      "stripped": true,
      "target": "/path/to/repo/.claude/settings.json",
      "backup_path": "/home/user/.claude/backups/uninstall-.../.../settings.json",
      "would_strip": false,
      "hook_keys_removed": ["PreToolUse", "Stop"],
      "error": null
    }

Strip semantics:
    An entry is considered an autonomous-dev hook if its ``command``
    string references one of:
        - ``~/.claude/hooks/``  (or absolute equivalent under HOME)
        - ``.claude/hooks/``    (relative repo-local form)
        - ``plugins/autonomous-dev/hooks/``  (developer flow)
    The command-string match is conservative: when uncertain, we leave
    the entry alone. User-added entries that point to
    ``~/.claude/hooks/extensions/...`` are PRESERVED.

    A hook event (e.g. PreToolUse) is removed entirely only when ALL of
    its entries match autonomous-dev. If user-added entries remain, the
    event key is kept with the user entries in place.

Idempotency rules:
    - Target missing -> success=true, stripped=false, NO backup.
    - "hooks" key absent -> success=true, stripped=false, NO backup.
    - No autonomous-dev entries found -> success=true, stripped=false,
      NO backup.
    - Malformed JSON -> success=false, error message, file UNTOUCHED, NO
      backup. (Refuse to risk overwriting an unparseable user file.)

Dry-run mode (``--dry-run``):
    - NO file writes, NO backup writes.
    - ``would_strip`` reflects whether a real run WOULD strip anything.
    - ``hook_keys_removed`` is populated with what WOULD be removed.

Usage:
    python3 uninstall_strip_repo_hooks.py \
        --target /path/to/repo/.claude/settings.json \
        --backup-root ~/.claude/backups/uninstall-YYYYMMDD-HHMMSS \
        [--dry-run]
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import sys
import tempfile
from pathlib import Path
from typing import Any, Dict, List


# Marker fragments. If a hook command string contains any of these, we
# treat the entry as autonomous-dev owned and remove it. The
# ``extensions/`` substring is the explicit "user-owned" carve-out.
_AUTONOMOUS_DEV_FRAGMENTS = (
    ".claude/hooks/",
    "plugins/autonomous-dev/hooks/",
)
_USER_OWNED_FRAGMENT = ".claude/hooks/extensions/"


def _atomic_write_json(target: Path, content: Dict[str, Any]) -> None:
    """Write JSON atomically to ``target`` via temp file + os.rename.

    Duplicates the helper from ``reset_global_hooks.py`` by design (see
    module docstring).

    Args:
        target: Destination path.
        content: Dictionary to serialize.

    Raises:
        OSError: On write or rename failure.
    """
    target.parent.mkdir(parents=True, exist_ok=True)
    fd = None
    temp_path = None
    try:
        fd, temp_path = tempfile.mkstemp(
            dir=str(target.parent),
            prefix=".uninstall-strip-",
            suffix=".json.tmp",
        )
        payload = json.dumps(content, indent=2, sort_keys=False)
        os.write(fd, payload.encode("utf-8"))
        os.close(fd)
        fd = None
        # Match existing settings file mode (best effort).
        try:
            mode = target.stat().st_mode & 0o777
        except OSError:
            mode = 0o600
        os.chmod(temp_path, mode)
        os.rename(temp_path, target)
    except OSError:
        if fd is not None:
            try:
                os.close(fd)
            except OSError:
                pass
        if temp_path and os.path.exists(temp_path):
            try:
                os.unlink(temp_path)
            except OSError:
                pass
        raise


def _is_autonomous_dev_entry(entry: Any) -> bool:
    """Return True if a hook entry's command points to autonomous-dev.

    Args:
        entry: Hook entry dict, expected shape::
            {"type": "command", "command": "python3 ~/.claude/hooks/foo.py"}
            or an entry with a nested "hooks" list of such dicts.

    Returns:
        True if the entry (or any nested hook command) references an
        autonomous-dev hook path AND is NOT explicitly user-owned
        (``hooks/extensions/``).
    """
    if not isinstance(entry, dict):
        return False

    # Top-level command form.
    command = entry.get("command")
    if isinstance(command, str):
        if _USER_OWNED_FRAGMENT in command:
            return False
        for frag in _AUTONOMOUS_DEV_FRAGMENTS:
            if frag in command:
                return True

    # Nested hooks list form (Claude Code's structure).
    nested = entry.get("hooks")
    if isinstance(nested, list):
        for sub in nested:
            if not isinstance(sub, dict):
                continue
            sub_cmd = sub.get("command")
            if not isinstance(sub_cmd, str):
                continue
            if _USER_OWNED_FRAGMENT in sub_cmd:
                continue
            for frag in _AUTONOMOUS_DEV_FRAGMENTS:
                if frag in sub_cmd:
                    return True

    return False


def _strip_event_entries(event_list: Any) -> tuple[List[Any], int]:
    """Strip autonomous-dev entries from a single event's entry list.

    Args:
        event_list: The list value under e.g. settings["hooks"]["PreToolUse"].

    Returns:
        (filtered_list, removed_count). If event_list is not a list, the
        original value is returned unchanged with removed_count=0.
    """
    if not isinstance(event_list, list):
        return event_list, 0

    kept: List[Any] = []
    removed = 0
    for entry in event_list:
        if _is_autonomous_dev_entry(entry):
            removed += 1
        else:
            kept.append(entry)
    return kept, removed


def _compute_strip(settings: Dict[str, Any]) -> tuple[Dict[str, Any], List[str], int]:
    """Compute the post-strip settings dict.

    Args:
        settings: The parsed settings.json dict.

    Returns:
        (new_settings, hook_keys_removed, total_entries_removed).
        ``hook_keys_removed`` lists event keys that were fully removed
        (e.g. ``PreToolUse`` had no surviving entries).
        ``total_entries_removed`` is the total number of individual
        autonomous-dev entries removed across all events.
    """
    new_settings = dict(settings)  # Shallow copy; we'll replace "hooks".
    hooks = settings.get("hooks")
    if not isinstance(hooks, dict):
        return new_settings, [], 0

    new_hooks: Dict[str, Any] = {}
    hook_keys_removed: List[str] = []
    total_removed = 0

    for event_name, event_list in hooks.items():
        kept, removed = _strip_event_entries(event_list)
        total_removed += removed
        if isinstance(event_list, list) and len(kept) == 0:
            # All entries under this event were autonomous-dev; drop the
            # event entirely.
            if removed > 0:
                hook_keys_removed.append(event_name)
            # else: was already empty (no autonomous-dev entries either) — drop.
            if removed == 0 and len(event_list) == 0:
                # Empty list with nothing to remove — preserve original
                # behavior of keeping empty key out.
                continue
        else:
            new_hooks[event_name] = kept

    if new_hooks:
        new_settings["hooks"] = new_hooks
    else:
        # All events stripped; remove the hooks key entirely.
        new_settings.pop("hooks", None)

    return new_settings, hook_keys_removed, total_removed


def _make_backup(target: Path, backup_root: Path) -> Path:
    """Copy ``target`` into a mirrored tree under ``backup_root``.

    Mirroring rule: backup path = backup_root / target.name. Per-target
    name collisions across multiple repos are resolved by including a
    short hash of the parent directory in the filename. The shell
    orchestrator passes a unique backup_root for each repo to avoid this
    in practice.

    Args:
        target: The settings.json file being backed up.
        backup_root: Directory under which the backup is written.

    Returns:
        Absolute path to the backup file written.

    Raises:
        OSError: If the backup cannot be created.
    """
    backup_root.mkdir(parents=True, exist_ok=True)
    backup_path = backup_root / target.name
    if backup_path.exists():
        # Disambiguate by including parent dir name.
        backup_path = backup_root / f"{target.parent.name}__{target.name}"
    shutil.copy2(target, backup_path)
    return backup_path


def strip_repo_hooks(
    target: Path,
    backup_root: Path,
    *,
    dry_run: bool = False,
) -> Dict[str, Any]:
    """Strip autonomous-dev hook entries from a settings.json file.

    Args:
        target: Absolute path to the per-repo settings.json.
        backup_root: Directory under which a backup will be created
            (real-run only; ignored in dry-run).
        dry_run: When True, no file writes or backups are created.

    Returns:
        JSON-serializable result dict (see module docstring for shape).
    """
    result: Dict[str, Any] = {
        "success": True,
        "stripped": False,
        "target": str(target),
        "backup_path": None,
        "would_strip": False,
        "hook_keys_removed": [],
        "error": None,
    }

    # Edge case 1: target file does not exist (valid uninstall no-op).
    if not target.exists():
        return result

    # Read the file.
    try:
        raw = target.read_text(encoding="utf-8")
    except OSError as e:
        result["success"] = False
        result["error"] = f"Cannot read target: {e}"
        return result

    # Edge case: malformed JSON. Do NOT modify file. Do NOT create backup.
    try:
        settings = json.loads(raw)
    except json.JSONDecodeError as e:
        result["success"] = False
        result["error"] = (
            f"malformed JSON in {target}: line {e.lineno} col {e.colno}: {e.msg}"
        )
        return result

    if not isinstance(settings, dict):
        result["success"] = False
        result["error"] = "settings root is not a JSON object"
        return result

    # No hooks key -> nothing to do.
    if "hooks" not in settings:
        return result

    new_settings, hook_keys_removed, total_removed = _compute_strip(settings)

    # Nothing identified as autonomous-dev.
    if total_removed == 0:
        return result

    result["hook_keys_removed"] = hook_keys_removed
    # Backwards-compatible: a "strip" happens whenever we removed at
    # least one entry, even if the event key itself survived (because
    # user entries remained).
    if dry_run:
        result["would_strip"] = True
        return result

    # Real run: backup BEFORE mutate.
    try:
        backup_path = _make_backup(target, backup_root)
    except OSError as e:
        result["success"] = False
        result["error"] = f"Cannot write backup: {e}"
        return result

    try:
        _atomic_write_json(target, new_settings)
    except OSError as e:
        result["success"] = False
        result["error"] = f"Failed to write target: {e}"
        return result

    result["stripped"] = True
    result["backup_path"] = str(backup_path)
    return result


def main() -> int:
    """CLI entry point - exits 0 always, callers parse JSON output."""
    parser = argparse.ArgumentParser(
        description=(
            "Strip autonomous-dev hook entries from a per-repo "
            "settings.json file. Companion to install.sh --uninstall. "
            "Issue #951."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--target",
        type=Path,
        required=True,
        help="Path to settings.json file to strip.",
    )
    parser.add_argument(
        "--backup-root",
        type=Path,
        required=True,
        help=(
            "Directory under which a backup copy will be written before "
            "any mutation. Ignored when --dry-run is set."
        ),
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print what would be stripped; perform no writes.",
    )
    args = parser.parse_args()

    result = strip_repo_hooks(
        args.target,
        args.backup_root,
        dry_run=args.dry_run,
    )
    print(json.dumps(result, indent=2))
    # Always exit 0: this is a helper. Callers inspect "success".
    return 0


if __name__ == "__main__":
    sys.exit(main())
