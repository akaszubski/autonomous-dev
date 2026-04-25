#!/usr/bin/env python3
"""
Reset Global Hooks CLI - Issue #949.

Recovery tool for users whose global hooks (~/.claude/settings.json) are
bricking Claude Code. Strips the entire ``hooks`` block from the target
settings.json while preserving every other top-level key (permissions,
mcpServers, env, model, etc.). Backs up to
``<target>.preglobal-hooks-strip`` before writing.

CLI contract (mirrors strip_duplicate_hooks.py):
    - ALWAYS print JSON to stdout.
    - ALWAYS exit 0 unless argparse rejects the args.
    - install.sh consumes the JSON via subprocess + json.loads.

Result JSON shape::

    {
      "success": true,
      "stripped": true,
      "target": "/home/user/.claude/settings.json",
      "backup_path": "/home/user/.claude/settings.json.preglobal-hooks-strip",
      "hook_keys_removed": ["PreToolUse", "Stop"],
      "message": "Removed 2 hook event(s); backup saved.",
      "error": null
    }

Idempotency rules:
    - Target missing -> success=true, stripped=false, NO backup.
    - "hooks" key absent -> success=true, stripped=false, NO backup.
    - Malformed JSON -> success=false, error message, file UNTOUCHED, NO
      backup. (Refuse to risk overwriting an unparseable user file.)
    - Backup file already present -> OVERWRITE it (documented behavior;
      no timestamp suffix logic — keeps the recovery path simple).
    - "hooks" value is non-dict (None, [], "x") -> still remove the key,
      hook_keys_removed=[].

NOTE: ``_atomic_write_json`` duplicates the helper from
strip_duplicate_hooks.py by design. A recovery tool runs when the system
is broken — cross-script imports add failure modes (parent dir missing,
lib path issues) that defeat the recovery purpose. The 40-line cost is
the price of self-containment. See Issue #949.

Usage:
    python3 reset_global_hooks.py --target /path/to/settings.json
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


def _atomic_write_json(target: Path, content: Dict[str, Any]) -> None:
    """Write JSON atomically to ``target`` via temp file + os.rename.

    NOTE: Duplicates _atomic_write_json from strip_duplicate_hooks.py by
    design. A recovery tool runs when the system is broken — cross-script
    imports add failure modes (parent dir missing, lib path issues) that
    defeat the recovery purpose. The 40-line cost is the price of
    self-containment. See Issue #949.

    Uses prefix=".reset-hooks-" to avoid clashing with concurrent strip
    operations (which use ".settings-strip-").

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
            prefix=".reset-hooks-",
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


def reset_file(target: Path) -> Dict[str, Any]:
    """Strip the ``hooks`` block from a settings.json file.

    Args:
        target: Absolute path to settings.json.

    Returns:
        JSON-serializable result dict (see module docstring for shape).
    """
    result: Dict[str, Any] = {
        "success": True,
        "stripped": False,
        "target": str(target),
        "backup_path": None,
        "hook_keys_removed": [],
        "message": "",
        "error": None,
    }

    # Edge case 1: target file does not exist.
    if not target.exists():
        result["message"] = f"settings.json not present at {target}"
        return result

    # Read the file.
    try:
        raw = target.read_text(encoding="utf-8")
    except OSError as e:
        result["success"] = False
        result["error"] = f"Cannot read target: {e}"
        result["message"] = (
            f"Failed to read {target}: {e}. "
            "See plugins/autonomous-dev/docs/TROUBLESHOOTING.md "
            "#recovery-from-broken-hooks for the manual one-liner."
        )
        return result

    # Edge case 4: malformed JSON. Do NOT modify file. Do NOT create backup.
    try:
        settings = json.loads(raw)
    except json.JSONDecodeError as e:
        result["success"] = False
        result["error"] = (
            f"malformed JSON: line {e.lineno} col {e.colno}: {e.msg}"
        )
        result["message"] = (
            f"settings.json at {target} is not valid JSON; refusing to "
            "modify. Fix the syntax error manually or restore from a "
            "backup, then re-run."
        )
        return result

    if not isinstance(settings, dict):
        result["success"] = False
        result["error"] = "settings root is not a JSON object"
        result["message"] = (
            f"Top-level value in {target} is not an object; cannot strip "
            "hooks block."
        )
        return result

    # Edge case 2: no hooks key. Idempotent — no backup, no write.
    if "hooks" not in settings:
        result["message"] = "no hooks block to remove"
        return result

    # Edge case 5: capture removed keys (handles non-dict hooks values
    # gracefully — None, [], "x" all yield an empty list).
    hooks_value = settings["hooks"]
    hook_keys_removed: List[str] = (
        list(hooks_value.keys()) if isinstance(hooks_value, dict) else []
    )

    # Edge case 3: backup exists -> overwrite. Recovery contract:
    # always reflect the most recent pre-strip state.
    backup_path = target.with_suffix(target.suffix + ".preglobal-hooks-strip")
    try:
        shutil.copy2(target, backup_path)
    except OSError as e:
        result["success"] = False
        result["error"] = f"Cannot write backup: {e}"
        result["message"] = (
            f"Failed to create backup at {backup_path}: {e}. "
            "Aborted — settings.json left unchanged."
        )
        return result

    # Strip and write atomically.
    del settings["hooks"]
    try:
        _atomic_write_json(target, settings)
    except OSError as e:
        result["success"] = False
        result["error"] = f"Failed to write target: {e}"
        result["message"] = (
            f"Backup at {backup_path} was created, but writing the "
            f"stripped settings.json failed: {e}. Restore from backup if "
            "the original file is now corrupted."
        )
        return result

    # Success.
    result["stripped"] = True
    result["backup_path"] = str(backup_path)
    result["hook_keys_removed"] = hook_keys_removed
    result["message"] = (
        f"Removed {len(hook_keys_removed)} hook event(s); "
        f"backup saved to {backup_path}."
    )
    return result


def main() -> int:
    """CLI entry point — exits 0 always, callers parse JSON output."""
    parser = argparse.ArgumentParser(
        description=(
            "Strip the hooks block from a Claude Code settings.json to "
            "recover from bricked global hooks. Issue #949."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--target",
        type=Path,
        required=True,
        help=(
            "Path to settings.json file to reset "
            "(typically ~/.claude/settings.json)."
        ),
    )
    args = parser.parse_args()

    result = reset_file(args.target)
    print(json.dumps(result, indent=2))
    # Always exit 0: this is a recovery helper. Callers inspect "success".
    return 0


if __name__ == "__main__":
    sys.exit(main())
