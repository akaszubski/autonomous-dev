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
import sys
import tempfile
from pathlib import Path
from typing import Any, Dict, List, Tuple


def _atomic_write_json(
    target: Path, content: Dict[str, Any]
) -> Tuple[Path, bool, bool]:
    """Write JSON atomically to ``target`` via temp file + os.replace.

    Handles dotfiles-manager symlinks: resolves ``target`` to its real path
    so that the in-place rewrite preserves the symlink entry in the filesystem
    rather than replacing it with a plain file.

    Permission hardening:
    - Reads the existing file's mode and applies a floor of 0o600 (strips
      any group/other read/write/execute bits).
    - If the file is absent or unreadable, defaults to 0o600.

    NOTE: Duplicates _atomic_write_json from strip_duplicate_hooks.py by
    design. A recovery tool runs when the system is broken — cross-script
    imports add failure modes (parent dir missing, lib path issues) that
    defeat the recovery purpose. The 40-line cost is the price of
    self-containment. See Issue #949.

    Uses prefix=".reset-hooks-" to avoid clashing with concurrent strip
    operations (which use ".settings-strip-").

    Args:
        target: Destination path (may be a symlink).
        content: Dictionary to serialize.

    Returns:
        Tuple of (real_target, was_symlink, was_broken_symlink).
        ``real_target`` is the resolved real path (equals ``target`` when not
        a symlink). ``was_symlink`` is True when ``target`` is a symlink.
        ``was_broken_symlink`` is True when ``target`` is a symlink pointing
        to a nonexistent path (the broken symlink is replaced with a real file).

    Raises:
        OSError: On write or rename failure.
    """
    was_symlink = target.is_symlink()
    was_broken_symlink = False
    real_target = target

    if was_symlink:
        try:
            real_target = target.resolve(strict=True)
        except OSError:
            # Broken symlink — keep real_target == target so os.replace
            # overwrites the symlink entry with a real file.
            real_target = target
            was_broken_symlink = True

    real_target.parent.mkdir(parents=True, exist_ok=True)
    fd = None
    temp_path = None
    try:
        fd, temp_path = tempfile.mkstemp(
            dir=str(real_target.parent),
            prefix=".reset-hooks-",
            suffix=".json.tmp",
        )
        payload = json.dumps(content, indent=2, sort_keys=False)
        os.write(fd, payload.encode("utf-8"))
        os.close(fd)
        fd = None
        # Permission floor: read existing mode, then strip group/other bits.
        try:
            mode = real_target.stat().st_mode & 0o777
            if mode & 0o077:  # any group/other bits set
                mode = 0o600
        except OSError:
            mode = 0o600
        os.chmod(temp_path, mode)
        os.replace(temp_path, real_target)
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

    return real_target, was_symlink, was_broken_symlink


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

    # Read the file. Follow symlink so we get the real bytes.
    try:
        # Always read the symlink target's content (read_bytes follows symlinks).
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
    backup_source_is_symlink = target.is_symlink()
    try:
        # Read dereferenced bytes for backup — backup is always a real file.
        backup_path.write_bytes(target.read_bytes())
        os.chmod(str(backup_path), 0o600)
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
        real_target, was_symlink, was_broken_symlink = _atomic_write_json(
            target, settings
        )
    except OSError as e:
        result["success"] = False
        result["error"] = f"Failed to write target: {e}"
        result["message"] = (
            f"Backup at {backup_path} was created, but writing the "
            f"stripped settings.json failed: {e}. Restore from backup if "
            "the original file is now corrupted."
        )
        return result

    # Success — compose message with any symlink notes.
    result["stripped"] = True
    result["backup_path"] = str(backup_path)
    result["hook_keys_removed"] = hook_keys_removed
    msg = (
        f"Removed {len(hook_keys_removed)} hook event(s); "
        f"backup saved to {backup_path}."
    )
    if was_broken_symlink:
        msg += (
            " (settings.json was a broken symlink; replaced with a real file)"
        )
    elif was_symlink:
        msg += (
            f" (settings.json is a symlink; rewrote real target at"
            f" {real_target} to preserve dotfiles manager)"
        )
    if backup_source_is_symlink:
        msg += (
            " (backup source was a symlink; backed up dereferenced contents)"
        )
    result["message"] = msg
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
