#!/usr/bin/env python3
"""
Strip Duplicate Hooks CLI - Issue #944.

Removes global-hook duplicates from a per-repo settings.json. Mirrors the
JSON-return contract of scripts/configure_global_settings.py for install.sh
consumption (subprocess + json.loads).

Behavior:
    - Reads target settings.json
    - Identifies hook commands matching CANONICAL_GLOBAL_HOOKS (exact match)
    - Writes back atomically (temp file + os.rename)
    - Emits a JSON result on stdout

Dogfooding skip:
    - If target basename is "settings.autonomous-dev.json" OR the settings
      content has "_autonomous_dev_dogfooding": true at the top level, the
      file is NOT modified and the result is {"success": true,
      "removed_count": 0, "skipped_reason": "dogfooding"}.

Malformed JSON:
    - Returns {"success": false, "error": "..."} with exit code 0
      (lenient — install.sh should not abort on a single bad settings file).

Usage:
    python3 strip_duplicate_hooks.py --target /path/to/.claude/settings.json
    python3 strip_duplicate_hooks.py --target ... --dry-run

JSON return shape:
    {
      "success": true,
      "target": "/path/to/.claude/settings.json",
      "removed_count": 4,
      "events": [
        {"event": "UserPromptSubmit",
         "command": "python3 ~/.claude/hooks/unified_prompt_validator.py"}
      ],
      "skipped_reason": null,
      "error": null
    }

See Also:
    plugins/autonomous-dev/lib/settings_merger.py - strip primitive
    plugins/autonomous-dev/scripts/configure_global_settings.py - JSON pattern
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import tempfile
from pathlib import Path
from typing import Any, Dict, List

# Import the strip primitive — match sync_validator.py:31-42 fallback pattern.
try:
    from plugins.autonomous_dev.lib.settings_merger import (
        CANONICAL_GLOBAL_HOOKS,
        extract_hook_refs,
        strip_global_duplicates,
    )
except ImportError:
    try:
        from autonomous_dev.lib.settings_merger import (  # type: ignore[no-redef]
            CANONICAL_GLOBAL_HOOKS,
            extract_hook_refs,
            strip_global_duplicates,
        )
    except ImportError:
        # Last-resort: add lib/ to sys.path (script run directly from
        # plugins/autonomous-dev/scripts/).
        _LIB_DIR = Path(__file__).resolve().parent.parent / "lib"
        if str(_LIB_DIR) not in sys.path:
            sys.path.insert(0, str(_LIB_DIR))
        from settings_merger import (  # type: ignore[no-redef]
            CANONICAL_GLOBAL_HOOKS,
            extract_hook_refs,
            strip_global_duplicates,
        )


def _is_dogfooding(target: Path, settings: Dict[str, Any]) -> bool:
    """Return True if this settings file should NOT be modified.

    Skip rules:
        - Filename is exactly ``settings.autonomous-dev.json``
        - Top-level key ``_autonomous_dev_dogfooding`` is truthy

    Args:
        target: Path to the settings file.
        settings: Parsed settings content.

    Returns:
        True when the caller MUST skip stripping.
    """
    if target.name == "settings.autonomous-dev.json":
        return True
    return bool(settings.get("_autonomous_dev_dogfooding"))


def _atomic_write_json(target: Path, content: Dict[str, Any]) -> None:
    """Write JSON atomically to ``target`` via temp file + os.rename.

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
            prefix=".settings-strip-",
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


def strip_file(target: Path, *, dry_run: bool = False) -> Dict[str, Any]:
    """Strip global-hook duplicates from a single settings.json file.

    Args:
        target: Absolute path to settings.json.
        dry_run: If True, do not write changes — only report what would be
            stripped.

    Returns:
        JSON-serializable result dict (see module docstring for shape).
    """
    result: Dict[str, Any] = {
        "success": True,
        "target": str(target),
        "removed_count": 0,
        "events": [],
        "skipped_reason": None,
        "error": None,
    }

    if not target.exists():
        result["success"] = False
        result["error"] = f"Target file not found: {target}"
        return result

    try:
        raw = target.read_text(encoding="utf-8")
    except OSError as e:
        result["success"] = False
        result["error"] = f"Cannot read target: {e}"
        return result

    try:
        settings = json.loads(raw)
    except json.JSONDecodeError as e:
        result["success"] = False
        result["error"] = f"Invalid JSON: {e.msg} at line {e.lineno}"
        return result

    if not isinstance(settings, dict):
        result["success"] = False
        result["error"] = "Settings root is not a JSON object"
        return result

    if _is_dogfooding(target, settings):
        result["skipped_reason"] = "dogfooding"
        return result

    new_settings, issues = strip_global_duplicates(
        settings, source_label=str(target)
    )

    # Build events list — extract event name + command from issue messages.
    # Issue message format:
    #   "Stripped global duplicate '<command>' from <event_name>"
    msg_pattern = re.compile(
        r"^Stripped global duplicate '(?P<cmd>.+)' from (?P<event>\S+)$"
    )
    events: List[Dict[str, str]] = []
    for issue in issues:
        m = msg_pattern.match(issue.message)
        if m:
            events.append(
                {"event": m.group("event"), "command": m.group("cmd")}
            )

    result["removed_count"] = len(events)
    result["events"] = events

    if events and not dry_run:
        try:
            _atomic_write_json(target, new_settings)
        except OSError as e:
            result["success"] = False
            result["error"] = f"Failed to write target: {e}"
            return result

    return result


def audit_project(project_root: Path) -> Dict[str, Any]:
    """Audit a project's .claude/ for duplicate hook registrations.

    Detects hooks registered in BOTH ``settings.json`` and
    ``settings.local.json`` at the project tier — Claude Code merges
    same-tier settings, causing every hook in the intersection to fire
    twice (Issue #1183, root-cause follow-up to #1176).

    Args:
        project_root: Repository root containing a ``.claude/`` directory.

    Returns:
        JSON-serializable dict with shape::

            {
              "success": True,
              "project_root": "/abs/path",
              "duplicates_found": int,
              "duplicate_hook_refs": ["unified_session_tracker.py", ...],
              "settings_json_path": "/abs/path/.claude/settings.json",
              "settings_local_path": "/abs/path/.claude/settings.local.json",
              "skipped_reasons": ["dogfooding"|"no settings.json"|...],
              "error": None,
            }

    Behavior:
        - When ``settings.local.json`` is missing → no duplicates possible
          → returns ``duplicates_found=0`` with skipped_reasons noting
          the missing file.
        - When ``settings.json`` is missing → no duplicates possible →
          returns ``duplicates_found=0`` with ``skipped_reasons=["no settings.json"]``.
        - When dogfooding marker present on either file → returns
          ``skipped_reasons=["dogfooding"]`` with no duplicates.
        - Malformed JSON in either file → returns ``success=False`` with
          ``error`` populated.
    
    Race Condition Note:
        This function performs non-atomic sequential reads of settings.json
        and settings.local.json. A theoretical TOCTOU race exists if files
        are modified between reads. Given the controlled deploy-time
        execution context and read-only nature (no write-back), this poses
        no practical risk. (Issue #1186)
    """
    project_root = Path(project_root).resolve()
    claude_dir = project_root / ".claude"
    settings_json_path = claude_dir / "settings.json"
    settings_local_path = claude_dir / "settings.local.json"

    result: Dict[str, Any] = {
        "success": True,
        "project_root": str(project_root),
        "duplicates_found": 0,
        "duplicate_hook_refs": [],
        "settings_json_path": str(settings_json_path),
        "settings_local_path": str(settings_local_path),
        "skipped_reasons": [],
        "error": None,
    }

    # Missing settings.json — no project-tier hooks registered; nothing to audit.
    if not settings_json_path.exists():
        result["skipped_reasons"].append("no settings.json")
        return result

    # Read and parse settings.json.
    try:
        settings_json = json.loads(
            settings_json_path.read_text(encoding="utf-8")
        )
    except (OSError, json.JSONDecodeError) as e:
        result["success"] = False
        result["error"] = f"Cannot read/parse settings.json: {e}"
        return result

    if not isinstance(settings_json, dict):
        result["success"] = False
        result["error"] = "settings.json root is not a JSON object"
        return result

    # Dogfooding skip — applies to either file.
    if _is_dogfooding(settings_json_path, settings_json):
        result["skipped_reasons"].append("dogfooding")
        return result

    # Missing settings.local.json — no overlap possible.
    if not settings_local_path.exists():
        result["skipped_reasons"].append("no settings.local.json")
        return result

    # Read and parse settings.local.json.
    try:
        settings_local = json.loads(
            settings_local_path.read_text(encoding="utf-8")
        )
    except (OSError, json.JSONDecodeError) as e:
        result["success"] = False
        result["error"] = f"Cannot read/parse settings.local.json: {e}"
        return result

    if not isinstance(settings_local, dict):
        result["success"] = False
        result["error"] = "settings.local.json root is not a JSON object"
        return result

    if _is_dogfooding(settings_local_path, settings_local):
        result["skipped_reasons"].append("dogfooding")
        return result

    # Compute hook-ref intersection — basename .py only.
    json_refs = extract_hook_refs(settings_json)
    local_refs = extract_hook_refs(settings_local)
    duplicates = sorted(json_refs & local_refs)

    result["duplicates_found"] = len(duplicates)
    result["duplicate_hook_refs"] = duplicates

    return result


def main() -> int:
    """CLI entry point.

    Two modes:
        --target <settings.json>    Strip global-hook duplicates from a
                                    per-repo settings.json (Issue #944).
                                    Always exits 0; callers parse JSON.
        --audit <project_root>      Detect duplicate hook registrations
                                    between settings.json and
                                    settings.local.json (Issue #1183).
                                    Exits 1 when duplicates found, 0 otherwise.
    """
    parser = argparse.ArgumentParser(
        description=(
            "Strip and audit per-repo settings hook duplicates. "
            "Issues #944, #1183."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    mode_group = parser.add_mutually_exclusive_group(required=True)
    mode_group.add_argument(
        "--target",
        type=Path,
        help="Path to settings.json file to strip (Issue #944).",
    )
    mode_group.add_argument(
        "--audit",
        type=Path,
        help=(
            "Project root to audit for duplicate hook registrations "
            "between settings.json and settings.local.json (Issue #1183)."
        ),
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="(--target only) Report what would be stripped without writing.",
    )
    args = parser.parse_args()

    if args.audit is not None:
        result = audit_project(args.audit)
        print(json.dumps(result, indent=2))
        # Audit mode: exit 1 when duplicates found (so callers like
        # deploy-all.sh treat it as a deployment failure).
        if not result["success"]:
            return 1
        return 1 if result["duplicates_found"] > 0 else 0

    # --target (Issue #944 strip mode).
    result = strip_file(args.target, dry_run=args.dry_run)
    print(json.dumps(result, indent=2))
    # Always exit 0: this is a migration helper. Callers inspect "success".
    return 0


if __name__ == "__main__":
    sys.exit(main())
