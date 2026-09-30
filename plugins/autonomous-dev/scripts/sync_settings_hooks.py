#!/usr/bin/env python3
"""
Sync settings.json hooks and permissions during deploy.

Reconciles canonical hooks with existing consumer hooks and merges the
generator's canonical deny rules with valid consumer deny rules.

Exact legacy commands now owned by hooks/hooks.json are removed from global,
repo, and local settings. Other consumer hooks survive repeated deploys.

Usage:
    # Global mode: reconcile hooks in ~/.claude/settings.json from template
    python3 sync_settings_hooks.py --global

    # Per-repo mode: reconcile hooks in <repo>/.claude/settings.json from template
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
import re
import shlex
import sys
import tempfile
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


_PLUGIN_OWNED_CALLBACKS = {
    "native_run_origin.py", "session_activity_logger.py",
    "unified_session_tracker.py",
}


def _audit_hook_callbacks(path: Path, settings: Any) -> list[dict]:
    """Read directly executed Python hook paths, without executing commands."""
    if not isinstance(settings, dict) or not isinstance(settings.get("hooks", {}), dict):
        raise ValueError(f"Expected hooks object: {path}")
    callbacks = []
    for event, entries in settings.get("hooks", {}).items():
        if not isinstance(event, str) or not isinstance(entries, list):
            raise ValueError(f"Malformed hook event: {path}: {event}")
        for entry in entries:
            if not isinstance(entry, dict) or not isinstance(entry.get("hooks"), list):
                raise ValueError(f"Malformed hook entry: {path}: {event}")
            matcher = entry.get("matcher", "")
            if not isinstance(matcher, str):
                raise ValueError(f"Malformed hook matcher: {path}: {event}")
            for hook in entry["hooks"]:
                if not isinstance(hook, dict):
                    raise ValueError(f"Malformed callback: {path}: {event}")
                if hook.get("type") != "command":
                    continue
                command, args = hook.get("command"), hook.get("args", [])
                if not isinstance(command, str) or not isinstance(args, list) or not all(
                    isinstance(arg, str) for arg in args
                ):
                    raise ValueError(f"Malformed command callback: {path}: {event}")
                # A filename mentioned by echo, a Python -c string, or a
                # trailing argument is not the executable hook. Handle the
                # two shipped forms: env assignments + python path and the
                # plugin's command='python3', args=[path, ...]. Wrappers are
                # outside this declared-direct-path audit.
                try:
                    tokens = shlex.split(command) + args
                except ValueError as error:
                    raise ValueError(f"Malformed hook command: {path}: {event}") from error
                while tokens and re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*=\S+", tokens[0]):
                    tokens.pop(0)
                if tokens and tokens[0] == "env":
                    tokens.pop(0)
                if not tokens or not re.fullmatch(r"python(?:3(?:\.\d+)?)?", Path(tokens[0]).name):
                    continue
                targets = tokens[1:]
                while targets and targets[0] in {"-u", "-B", "-E", "-I"}:
                    targets.pop(0)
                if not targets or targets[0] in {"-c", "-m"}:
                    continue
                match = re.search(r"(?:^|/)hooks/([A-Za-z0-9_.-]+\.py)$", targets[0])
                if match:
                    callbacks.append({"source": str(path), "event": event,
                                      "matcher": matcher, "basename": match.group(1)})
    return callbacks


def _hook_matchers_overlap(left: str, right: str) -> bool:
    """Prove disjointness only for literal matcher alternatives.

    Regex-like or unknown matcher forms remain possible overlaps; a safety
    preflight must not certify them as disjoint by guessing.
    """
    if left == "*" or right == "*":
        return True
    literal = re.compile(r"[A-Za-z][A-Za-z0-9_]*")
    left_parts, right_parts = left.split("|"), right.split("|")
    if all(literal.fullmatch(part) for part in [*left_parts, *right_parts]):
        return bool(set(left_parts) & set(right_parts))
    return True


def audit_global_plugin(global_settings: Path | None = None) -> Dict[str, Any]:
    """Find declared direct-Python callback overlaps across user and plugin tiers.

    This is deliberately a read-only preflight, not a migration. The installer
    must not silently modify user-level settings to make plugin installation pass.
    A no-overlap result does not establish plugin activation or wrapper effects.
    """
    global_path = global_settings or Path.home() / ".claude" / "settings.json"
    plugin_path = _find_plugin_root() / "hooks" / "hooks.json"
    try:
        plugin = json.loads(plugin_path.read_text(encoding="utf-8"))
        if not isinstance(plugin, dict) or "hooks" not in plugin:
            raise ValueError(f"Expected plugin hooks object: {plugin_path}")
        plugin_callbacks = _audit_hook_callbacks(plugin_path, plugin)
        if not plugin_callbacks:
            raise ValueError(f"No command callbacks in plugin hooks: {plugin_path}")
        if global_path.exists():
            global_data = json.loads(global_path.read_text(encoding="utf-8"))
            global_callbacks = _audit_hook_callbacks(global_path, global_data)
        else:
            global_callbacks = []
    except (OSError, ValueError) as error:
        return {"success": False, "conflicts": [], "scope": "declared-direct-python-paths",
                "message": f"Hook audit cannot verify settings: {error}"}

    plugin_by_key: dict[tuple[str, str], list[dict]] = {}
    for item in plugin_callbacks:
        plugin_by_key.setdefault((item["event"], item["basename"]), []).append(item)
    conflicts = [
        {"event": item["event"], "basename": item["basename"],
         "global_source": item["source"], "plugin_source": plugin_path.as_posix(),
         "global_matcher": item["matcher"],
         "plugin_matcher": plugin_item["matcher"]}
        for item in global_callbacks
        for plugin_item in plugin_by_key.get((item["event"], item["basename"]), [])
        if _hook_matchers_overlap(item["matcher"], plugin_item["matcher"])
    ]
    return {
        "success": not conflicts,
        "conflicts": conflicts,
        "scope": "declared-direct-python-paths; plugin activation and wrappers unverified",
        "message": f"{len(conflicts)} declared user/plugin hook registration overlap(s)",
    }


def _owned_legacy_command(event: str, matcher: str, hook: Any) -> bool:
    """Recognize only the installed commands superseded by plugin hooks.json."""
    if not isinstance(hook, dict) or hook.get("type") != "command":
        return False
    command = hook.get("command", "")
    if not isinstance(command, str):
        return False
    basename = next((name for name in _PLUGIN_OWNED_CALLBACKS if name in command), "")
    if not basename:
        return False
    global_command = f"python3 ~/.claude/hooks/{basename}"
    project_command = (
        'python3 "${CLAUDE_PROJECT_DIR:-$(git rev-parse --show-toplevel)}'
        f'/.claude/hooks/{basename}"'
    )
    exact_commands = {global_command, project_command}
    if basename == "session_activity_logger.py":
        exact_commands |= {f"ACTIVITY_LOGGING=true {value}" for value in exact_commands}
    if command not in exact_commands:
        return False
    return (
        (event == "UserPromptExpansion" and basename == "native_run_origin.py")
        or (event == "PreToolUse" and matcher == "Skill" and basename == "native_run_origin.py")
        or (event == "PreToolUse" and basename == "session_activity_logger.py"
            and bool({"Task", "Agent"} & set(matcher.split("|"))))
        or (event == "PostToolUse" and basename == "session_activity_logger.py")
        or (event == "SubagentStop" and basename == "unified_session_tracker.py")
    )


def _strip_plugin_owned(hooks: Any) -> tuple[dict, int]:
    """Drop migrated callbacks, retaining unrelated hooks in shared matchers."""
    if not isinstance(hooks, dict):
        raise ValueError("Expected hooks object; refusing to replace malformed consumer hooks")
    cleaned: dict = {}
    removed = 0
    for event, entries in hooks.items():
        if not isinstance(entries, list):
            cleaned[event] = entries
            continue
        kept = []
        for entry in entries:
            if not isinstance(entry, dict) or not isinstance(entry.get("hooks"), list):
                kept.append(entry)
                continue
            matcher = entry.get("matcher", "")
            survivors = []
            for hook in entry["hooks"]:
                if _owned_legacy_command(event, matcher, hook):
                    removed += 1
                    # The repo template also logs Bash in this matcher. Keep
                    # that unrelated use, with Agent/Task removed from scope.
                    if event == "PreToolUse" and "Bash" in matcher.split("|"):
                        kept.append({**entry, "matcher": "Bash", "hooks": [hook]})
                    continue
                survivors.append(hook)
            if survivors:
                kept.append({**entry, "hooks": survivors})
        if kept:
            cleaned[event] = kept
    return cleaned, removed


def _merge_hook_entries(existing: dict, canonical: dict) -> dict:
    """Keep consumer entries and add missing canonical callbacks once."""
    merged = {event: list(entries) for event, entries in existing.items()}
    for event, entries in canonical.items():
        target = merged.setdefault(event, [])
        if not isinstance(target, list):
            target = merged[event] = []
        for entry in entries:
            if entry not in target:
                target.append(entry)
    return merged


def _write_settings_transaction(updates: dict[Path, dict]) -> None:
    """Stage all files, then replace them; restore originals on a failed replace.

    Cross-file rename is not atomic. A rollback failure is explicitly reported
    with retained private backups so an operator can recover the prior files.
    """
    staged: dict[Path, str] = {}
    backups: dict[Path, str | None] = {}
    replaced: list[Path] = []
    # The marker survives SIGKILL between renames. A later installer must
    # refuse that possibly mixed state instead of treating it as a baseline.
    marker = next(iter(updates)).parent / ".autonomous-dev-settings-transaction"
    marker.parent.mkdir(parents=True, exist_ok=True)
    try:
        marker_fd = os.open(marker, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    except FileExistsError as error:
        raise RuntimeError(
            f"PARTIAL or interrupted settings update: {marker}; inspect "
            "private .restore backups before retrying"
        ) from error
    with os.fdopen(marker_fd, "w", encoding="utf-8") as stream:
        stream.write("Settings update in progress; inspect .restore backups before retry.\n")
        stream.flush()
        os.fsync(stream.fileno())
    partial = False
    try:
        for path, data in updates.items():
            path.parent.mkdir(parents=True, exist_ok=True)
            fd, temporary = tempfile.mkstemp(dir=str(path.parent), prefix=f".{path.name}.")
            staged[path] = temporary
            with os.fdopen(fd, "w", encoding="utf-8") as stream:
                json.dump(data, stream, indent=2)
                stream.write("\n")
                stream.flush()
                os.fsync(stream.fileno())
            os.chmod(temporary, 0o600)
            if path.exists():
                fd, backup = tempfile.mkstemp(dir=str(path.parent), prefix=f".{path.name}.restore.")
                backups[path] = backup
                with os.fdopen(fd, "wb") as stream:
                    stream.write(path.read_bytes())
                    stream.flush()
                    os.fsync(stream.fileno())
                os.chmod(backup, 0o600)
            else:
                backups[path] = None
        for path, temporary in staged.items():
            os.replace(temporary, path)
            replaced.append(path)
    except Exception as error:
        rollback_errors = []
        for path in reversed(replaced):
            backup = backups[path]
            try:
                if backup is None:
                    path.unlink()
                else:
                    os.replace(backup, path)
            except OSError as rollback_error:
                rollback_errors.append(f"{path}: {rollback_error}")
        if rollback_errors:
            partial = True
            retained = [str(value) for value in backups.values() if value and os.path.exists(value)]
            raise RuntimeError(
                f"PARTIAL settings update; rollback failed: {rollback_errors}; "
                f"private recovery backups: {retained}"
            ) from error
        raise
    finally:
        for temporary in staged.values():
            if os.path.exists(temporary):
                os.unlink(temporary)
        # Preserve the marker/backups after a failed rollback or a process
        # death. Only a fully committed or successfully rolled-back run clears
        # the marker.
        if not partial:
            for backup in backups.values():
                if backup and os.path.exists(backup):
                    os.unlink(backup)
            marker.unlink()


def _replace_hooks(
    user_path: Path, template_path: Path, *, dry_run: bool = False
) -> Dict[str, Any]:
    """Reconcile template hooks and consumer hooks, migrating exact legacy ones.

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
    if not isinstance(template, dict):
        raise ValueError(f"Expected settings object: {template_path}")
    template_hooks, template_migrated = _strip_plugin_owned(template.get("hooks", {}))

    # Read existing settings (or create empty)
    if user_path.exists():
        user_settings = json.loads(user_path.read_text(encoding="utf-8"))
    else:
        user_settings = {}
    if not isinstance(user_settings, dict):
        raise ValueError(f"Expected settings object: {user_path}")

    # Capture the pre-migration warning for operators. The local legacy entry
    # is then removed below, so a post-write inspection would erase evidence.
    stale_local_warnings = _detect_stale_local_warnings(user_path, template_hooks)

    # Count what's changing
    old_hooks = user_settings.get("hooks", {})
    if not isinstance(old_hooks, dict):
        raise ValueError(f"Expected hooks object: {user_path}")
    old_events = set(old_hooks.keys())
    new_events = set(template_hooks.keys())

    # Scoped migration: preserve consumer callbacks and all unrelated keys.
    user_hooks, user_migrated = _strip_plugin_owned(old_hooks)
    user_settings["hooks"] = _merge_hook_entries(user_hooks, template_hooks)
    local_path = user_path.with_name("settings.local.json")
    local_settings = None
    local_migrated = 0
    if local_path.exists():
        local_settings = json.loads(local_path.read_text(encoding="utf-8"))
        if not isinstance(local_settings, dict):
            raise ValueError(f"Expected JSON object: {local_path}")
        local_hooks, local_migrated = _strip_plugin_owned(local_settings.get("hooks", {}))
        local_settings["hooks"] = local_hooks

    # Sync permissions.deny from canonical generator list
    canonical_deny = _get_canonical_deny_list()
    deny_synced = False
    deny_errors_fixed = 0
    if canonical_deny:
        old_deny = user_settings.get("permissions", {}).get("deny", [])
        # Validate old deny list for known bad patterns
        bad_patterns = _validate_permission_patterns(old_deny)
        merged_deny = list(dict.fromkeys(canonical_deny + [
            pattern for pattern in old_deny if pattern not in bad_patterns
        ]))
        if bad_patterns or old_deny != merged_deny:
            if "permissions" not in user_settings:
                user_settings["permissions"] = {}
            user_settings["permissions"]["deny"] = merged_deny
            deny_synced = True
            deny_errors_fixed = len(bad_patterns)

    if not dry_run:
        updates = {user_path: user_settings}
        if local_settings is not None and local_migrated:
            updates[local_path] = local_settings
        _write_settings_transaction(updates)

    total_events = len(user_settings["hooks"])
    hooks_added = len(new_events - old_events)
    hooks_preserved = len(new_events & old_events)

    deny_msg = ""
    if deny_synced:
        deny_msg = f", deny list synced ({deny_errors_fixed} invalid patterns fixed)"

    # Issue #1183: detect legacy settings.local.json that still registers
    # canonical hooks → would cause same-tier duplicate firings.
    stale_msg = ""
    if stale_local_warnings:
        stale_msg = (
            f"; settings.local.json previously registered "
            f"{len(stale_local_warnings)} duplicate hooks; migrated exact legacy commands"
        )

    return {
        "success": True,
        "hooks_added": hooks_added,
        "hooks_preserved": hooks_preserved,
        "hooks_migrated": user_migrated + local_migrated,
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
    mode_group.add_argument(
        "--audit-global-plugin",
        action="store_true",
        help="Read-only audit of global settings against plugin hook registrations",
    )
    parser.add_argument(
        "--global-settings",
        type=Path,
        help="Global settings path for --audit-global-plugin (default: ~/.claude/settings.json)",
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
    if args.global_settings is not None and not args.audit_global_plugin:
        parser.error("--global-settings requires --audit-global-plugin")
    if args.audit_global_plugin and (args.dry_run or args.count_only):
        parser.error("audit mode cannot be combined with sync options")

    try:
        if args.audit_global_plugin:
            result = audit_global_plugin(args.global_settings)
        elif args.global_mode:
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
