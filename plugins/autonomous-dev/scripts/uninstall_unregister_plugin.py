#!/usr/bin/env python3
"""Uninstall: Unregister autonomous-dev from Claude Code plugin/marketplace files - Issue #951.

Companion helper for ``install.sh --uninstall``. Removes
autonomous-dev's entries from two global Claude Code state files:

    1. ``~/.claude/plugins/installed_plugins.json`` (plugin registration)
    2. ``~/.claude/plugins/marketplaces.json``       (marketplace registration)

Both files are optional — many setups (including ones bootstrapped via
install.sh) never write to them. Missing files are treated as a valid
no-op: ``stripped=false, success=true``.

Like ``uninstall_strip_repo_hooks.py``, this script is intentionally
self-contained. The shell uninstall path may run when the regular
install is broken; cross imports from ``uninstall_orchestrator.py``
would defeat that purpose.

CLI contract:
    - ALWAYS print JSON to stdout.
    - ALWAYS exit 0 unless argparse rejects the args.
    - install.sh consumes the JSON via subprocess + json.loads.

Result JSON shape::

    {
      "success": true,
      "stripped": true,
      "plugins_file": "/home/user/.claude/plugins/installed_plugins.json",
      "marketplaces_file": "/home/user/.claude/plugins/marketplaces.json",
      "plugins_backup": "/home/.../backup/installed_plugins.json",
      "marketplaces_backup": null,
      "plugins_changed": true,
      "marketplaces_changed": false,
      "would_strip": false,
      "error": null
    }

Strip semantics:
    - In ``installed_plugins.json``: top-level may be a dict keyed by
      plugin id (``"autonomous-dev": {...}``) OR a list of plugin dicts
      with a ``name``/``id`` field. We handle both shapes.
    - In ``marketplaces.json``: top-level may be a dict keyed by
      marketplace name, OR a list of marketplace dicts. We strip any
      entry whose key/name/url references ``autonomous-dev``.

Idempotency rules:
    - Both files missing -> success=true, stripped=false, NO backup.
    - One file missing -> handle the other; report missing as "absent".
    - No autonomous-dev entries found -> success=true, stripped=false,
      NO backup created for that file.
    - Malformed JSON in a file -> that file is skipped with an error
      message; the other file is still processed. Overall success
      remains true as long as at least one file processed cleanly OR
      both were no-ops.

Usage:
    python3 uninstall_unregister_plugin.py \
        --plugins-file ~/.claude/plugins/installed_plugins.json \
        --marketplaces-file ~/.claude/plugins/marketplaces.json \
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
from typing import Any, Dict, List, Tuple


_AUTONOMOUS_DEV_KEYS = ("autonomous-dev", "autonomous_dev")


def _atomic_write_json(target: Path, content: Any) -> None:
    """Write JSON atomically via temp file + os.rename.

    Args:
        target: Destination path.
        content: JSON-serializable value (dict or list).

    Raises:
        OSError: On write or rename failure.
    """
    target.parent.mkdir(parents=True, exist_ok=True)
    fd = None
    temp_path = None
    try:
        fd, temp_path = tempfile.mkstemp(
            dir=str(target.parent),
            prefix=".uninstall-unregister-",
            suffix=".json.tmp",
        )
        payload = json.dumps(content, indent=2, sort_keys=False)
        os.write(fd, payload.encode("utf-8"))
        os.close(fd)
        fd = None
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


def _is_autonomous_dev_match(value: Any) -> bool:
    """Return True if a string value (key, name, url, path) references autonomous-dev.

    Args:
        value: The candidate string.
    """
    if not isinstance(value, str):
        return False
    lower = value.lower()
    return any(needle in lower for needle in _AUTONOMOUS_DEV_KEYS)


def _strip_entry_from_collection(collection: Any) -> Tuple[Any, bool]:
    """Strip autonomous-dev entries from a dict or list collection.

    Args:
        collection: Either a dict (keyed by plugin/marketplace id) or
            a list of dicts with name/id/url fields.

    Returns:
        (new_collection, removed). ``removed`` is True if any entry
        was dropped. If the input is neither dict nor list, the
        original value is returned with removed=False.
    """
    if isinstance(collection, dict):
        new: Dict[str, Any] = {}
        removed = False
        for key, value in collection.items():
            if _is_autonomous_dev_match(key):
                removed = True
                continue
            # Also inspect the value: if it's a dict with a name/id/url
            # field that matches, drop it.
            if isinstance(value, dict):
                if any(
                    _is_autonomous_dev_match(value.get(field))
                    for field in ("name", "id", "url", "path", "source")
                ):
                    removed = True
                    continue
            new[key] = value
        return new, removed

    if isinstance(collection, list):
        new_list: List[Any] = []
        removed = False
        for entry in collection:
            if isinstance(entry, dict):
                if any(
                    _is_autonomous_dev_match(entry.get(field))
                    for field in ("name", "id", "url", "path", "source")
                ):
                    removed = True
                    continue
            elif isinstance(entry, str):
                if _is_autonomous_dev_match(entry):
                    removed = True
                    continue
            new_list.append(entry)
        return new_list, removed

    return collection, False


def _make_backup(target: Path, backup_root: Path) -> Path:
    """Copy ``target`` into ``backup_root`` before mutation."""
    backup_root.mkdir(parents=True, exist_ok=True)
    backup_path = backup_root / target.name
    if backup_path.exists():
        backup_path = backup_root / f"{target.parent.name}__{target.name}"
    shutil.copy2(target, backup_path)
    return backup_path


def _process_file(
    target: Path,
    backup_root: Path,
    *,
    dry_run: bool,
) -> Tuple[bool, bool, Path | None, str | None]:
    """Process a single plugins/marketplaces JSON file.

    Args:
        target: The JSON file to strip.
        backup_root: Backup destination.
        dry_run: When True, no writes.

    Returns:
        (success, changed, backup_path_or_None, error_or_None).
            success: True if the file was successfully processed (or
                was a valid no-op like missing/empty).
            changed: True if entries were (or would be) removed.
            backup_path_or_None: Path to backup if we wrote one (real
                run + changes occurred), else None.
            error_or_None: Error message if processing failed.
    """
    # Missing file is a valid no-op.
    if not target.exists():
        return True, False, None, None

    try:
        raw = target.read_text(encoding="utf-8")
    except OSError as e:
        return False, False, None, f"Cannot read {target}: {e}"

    # Empty file is also a valid no-op.
    if not raw.strip():
        return True, False, None, None

    try:
        data = json.loads(raw)
    except json.JSONDecodeError as e:
        return (
            False,
            False,
            None,
            f"malformed JSON in {target}: line {e.lineno} col {e.colno}: {e.msg}",
        )

    new_data, removed = _strip_entry_from_collection(data)

    if not removed:
        return True, False, None, None

    if dry_run:
        return True, True, None, None

    # Real run: backup BEFORE mutate.
    try:
        backup_path = _make_backup(target, backup_root)
    except OSError as e:
        return False, False, None, f"Cannot backup {target}: {e}"

    try:
        _atomic_write_json(target, new_data)
    except OSError as e:
        return False, False, backup_path, f"Failed to write {target}: {e}"

    return True, True, backup_path, None


def unregister_plugin(
    plugins_file: Path,
    marketplaces_file: Path,
    backup_root: Path,
    *,
    dry_run: bool = False,
) -> Dict[str, Any]:
    """Strip autonomous-dev from plugins.json and marketplaces.json.

    Args:
        plugins_file: Path to ``installed_plugins.json``.
        marketplaces_file: Path to ``marketplaces.json``.
        backup_root: Backup destination directory.
        dry_run: When True, perform no writes.

    Returns:
        JSON-serializable result dict (see module docstring for shape).
    """
    result: Dict[str, Any] = {
        "success": True,
        "stripped": False,
        "plugins_file": str(plugins_file),
        "marketplaces_file": str(marketplaces_file),
        "plugins_backup": None,
        "marketplaces_backup": None,
        "plugins_changed": False,
        "marketplaces_changed": False,
        "would_strip": False,
        "error": None,
    }

    errors: List[str] = []

    p_success, p_changed, p_backup, p_err = _process_file(
        plugins_file, backup_root, dry_run=dry_run
    )
    if p_err:
        errors.append(p_err)
    if p_backup is not None:
        result["plugins_backup"] = str(p_backup)
    result["plugins_changed"] = bool(p_changed)

    m_success, m_changed, m_backup, m_err = _process_file(
        marketplaces_file, backup_root, dry_run=dry_run
    )
    if m_err:
        errors.append(m_err)
    if m_backup is not None:
        result["marketplaces_backup"] = str(m_backup)
    result["marketplaces_changed"] = bool(m_changed)

    any_change = bool(p_changed or m_changed)
    if dry_run:
        result["would_strip"] = any_change
    else:
        result["stripped"] = any_change

    # Overall success: only fail if BOTH files erred. One error +
    # one clean is still a partial success (we report the error in
    # the message but don't fail the whole unregister).
    if not p_success and not m_success:
        result["success"] = False

    if errors:
        result["error"] = "; ".join(errors)

    return result


def main() -> int:
    """CLI entry point - exits 0 always, callers parse JSON output."""
    parser = argparse.ArgumentParser(
        description=(
            "Unregister autonomous-dev from Claude Code plugin and "
            "marketplace registry files. Companion to install.sh "
            "--uninstall. Issue #951."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--plugins-file",
        type=Path,
        required=True,
        help="Path to installed_plugins.json.",
    )
    parser.add_argument(
        "--marketplaces-file",
        type=Path,
        required=True,
        help="Path to marketplaces.json.",
    )
    parser.add_argument(
        "--backup-root",
        type=Path,
        required=True,
        help=(
            "Directory under which backup copies are written before "
            "any mutation. Ignored when --dry-run is set."
        ),
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print what would be stripped; perform no writes.",
    )
    args = parser.parse_args()

    result = unregister_plugin(
        args.plugins_file,
        args.marketplaces_file,
        args.backup_root,
        dry_run=args.dry_run,
    )
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
