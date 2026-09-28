"""
THE canonical owner of every settings.json mutation the toolkit performs.

One function — :func:`apply_owned_settings` — updates toolkit-owned entries in a
settings file and leaves everything else alone. Every writer routes through it:
``scripts/sync_settings_hooks.py`` (the entrypoint ``scripts/deploy-all.sh``
invokes), ``lib/sync_dispatcher/dispatcher.py`` and
``lib/sync_dispatcher/modes.py``.

Issue #1809 retired the three parallel writers this module used to enable:

* ``SettingsMerger.merge_settings`` / ``_merge_dicts`` / ``_merge_hooks`` /
  ``_atomic_write`` and ``MergeResult`` — DELETED (454 lines). The additive
  lifecycle merge is superseded by the ownership-aware projection in
  :func:`_project_hooks`, and the write transaction by :func:`_commit_settings`
  (which adds compare-before-write and guaranteed temp cleanup).
* ``sync_settings_hooks._replace_hooks``'s wholesale ``hooks`` /
  ``permissions.deny`` assignment — DELETED, now delegates here.
* ``sync_dispatcher.dispatcher``'s duplicate wholesale ``hooks`` assignment —
  DELETED, now delegates here.

Security:
- ``..`` traversal rejected in the target path (CWE-22)
- symlinked targets resolved to the real file before writing (CWE-59)
- atomic temp+rename with 0o600; an interrupted write leaves the target's bytes
  untouched and removes the temp file
- compare-before-write digest check; a concurrent modification is refused, never
  overwritten
- audit logging of every applied write and every refusal

Ownership:
- hook entries: owned iff the command references a hook-script basename declared
  by ``install_manifest.json``, the template, or the retirement registries in
  this module. Unrelated hooks on the SAME lifecycle event survive.
- ``permissions.deny``: owned iff the caller declares the entry. ``allow`` and
  ``ask`` are never touched.
- everything else (``env``, nested keys, foreign top-level keys): untouched.

Usage:
    from settings_merger import apply_owned_settings
    result = apply_owned_settings(
        Path(".claude/settings.json"),
        template_dict,
        manifest_path=Path("config/install_manifest.json"),
        owned_deny=DEFAULT_DENY_LIST,
    )
    if not result.success:
        raise SystemExit(f"{result.refusal_class}: {result.reason}")

See Also:
    - docs/LIBRARIES.md section 29 for API documentation
    - tests/regression/test_issue_1809_settings_ownership_preservation.py
    - tests/unit/lib/test_settings_merger_strip.py
"""

import copy
import fcntl
import hashlib
import json
import os
import re
import tempfile
import time
from contextlib import contextmanager
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Set, Tuple

# Import security utilities
try:
    from autonomous_dev.lib.security_utils import validate_path, audit_log
except ImportError:
    # Fallback for direct script execution
    import sys
    sys.path.insert(0, str(Path(__file__).parent))
    from security_utils import validate_path, audit_log

# Reuse ValidationIssue dataclass from sync_validator (no new dataclass per Issue #944)
try:
    from autonomous_dev.lib.sync_validator import ValidationIssue
except ImportError:
    try:
        from sync_validator import ValidationIssue
    except ImportError:
        # Last-resort fallback: define a compatible minimal dataclass.
        # This branch should not normally be hit because sync_validator.py
        # is co-located in lib/.
        @dataclass
        class ValidationIssue:  # type: ignore[no-redef]
            """Compatibility shim — see sync_validator.ValidationIssue."""
            severity: str
            category: str
            message: str
            file_path: Optional[str] = None
            line_number: Optional[int] = None
            auto_fixable: bool = False
            fix_action: Optional[str] = None


# Issue #944: Canonical global-hook commands that MUST NOT appear in per-repo
# settings.json templates (because they're already registered in
# ~/.claude/settings.json by configure_global_settings.py).
#
# These are the exact command strings (post-whitespace-strip). Variants with
# extra args (e.g., `&& echo ...` suffixes, custom env vars) are NOT
# considered canonical and are preserved by strip_global_duplicates.
CANONICAL_GLOBAL_HOOKS: Tuple[str, ...] = (
    "python3 ~/.claude/hooks/unified_prompt_validator.py",
    "python3 ~/.claude/hooks/plan_gate.py",
    "python3 ~/.claude/hooks/plan_mode_exit_detector.py",
    "python3 ~/.claude/hooks/stop_quality_gate.py",
    "python3 ~/.claude/hooks/task_completed_handler.py",
    "python3 ~/.claude/hooks/unified_session_tracker.py",
    "CONVERSATION_ARCHIVE=true python3 ~/.claude/hooks/conversation_archiver.py",
)


def extract_hook_refs(settings: Dict[str, Any]) -> set:
    """Extract all hook file references (basename .py only) from settings.

    Walks the settings["hooks"] tree and collects every command string that
    references a Python hook file. Returns the set of basenames, e.g.
    {"unified_prompt_validator.py", "plan_gate.py"}.

    Args:
        settings: Parsed settings.json content (dict).

    Returns:
        Set of hook filenames (basename only, with .py extension).
    """
    refs: set = set()
    hooks_section = settings.get("hooks", {})
    if not isinstance(hooks_section, dict):
        return refs

    pattern = re.compile(r"hooks/(\w+\.py)")

    for _lifecycle, matchers in hooks_section.items():
        if not isinstance(matchers, list):
            continue
        for matcher in matchers:
            if not isinstance(matcher, dict):
                continue
            hook_list = matcher.get("hooks", [])
            if not isinstance(hook_list, list):
                continue
            for hook in hook_list:
                if not isinstance(hook, dict):
                    continue
                command = hook.get("command", "")
                for match in pattern.finditer(command):
                    refs.add(match.group(1))
    return refs


def strip_global_duplicates(
    settings: Dict[str, Any],
    canonical_hooks: Iterable[str] = CANONICAL_GLOBAL_HOOKS,
    *,
    source_label: str = "<unknown>",
) -> Tuple[Dict[str, Any], List[ValidationIssue]]:
    """Strip global-hook duplicates from a settings dict.

    Per-repo settings.json files MUST NOT redeclare hooks that are already
    registered in the user's global ~/.claude/settings.json. This function
    removes those duplicates by exact-match string comparison on the hook
    command.

    Args:
        settings: Parsed settings.json content (dict). NOT mutated — a
            deep copy is returned.
        canonical_hooks: Iterable of exact command strings (post-whitespace
            strip) to remove. Defaults to CANONICAL_GLOBAL_HOOKS.
        source_label: Identifier (e.g., file path) for ValidationIssue
            file_path field. Default "<unknown>".

    Returns:
        Tuple of (modified_settings_deep_copy, [ValidationIssue]).
        The list is empty when nothing was stripped (idempotent re-call).

    Notes:
        - Match is exact on the whitespace-stripped command. A command like
          ``"python3 ~/.claude/hooks/foo.py && echo done"`` is NOT removed
          when ``"python3 ~/.claude/hooks/foo.py"`` is canonical.
        - When all hooks in a matcher are removed, the matcher group is
          removed. When all matcher groups in an event are removed, the
          event key is removed. When all events are removed, ``"hooks"``
          itself is removed.
        - Idempotent: a second call yields ``([], same dict)``.
    """
    canonical_set = {c.strip() for c in canonical_hooks}
    issues: List[ValidationIssue] = []

    result = copy.deepcopy(settings)
    hooks_section = result.get("hooks")

    if not isinstance(hooks_section, dict):
        return result, issues

    new_hooks_section: Dict[str, Any] = {}

    for event_name, matchers in hooks_section.items():
        if not isinstance(matchers, list):
            # Preserve unknown shapes verbatim.
            new_hooks_section[event_name] = matchers
            continue

        kept_matchers: List[Any] = []

        for matcher in matchers:
            if not isinstance(matcher, dict):
                kept_matchers.append(matcher)
                continue

            hook_entries = matcher.get("hooks")
            if not isinstance(hook_entries, list):
                # Matcher without "hooks" array — keep as-is.
                kept_matchers.append(matcher)
                continue

            kept_hooks: List[Any] = []
            for entry in hook_entries:
                if not isinstance(entry, dict):
                    kept_hooks.append(entry)
                    continue
                cmd = entry.get("command", "")
                if isinstance(cmd, str) and cmd.strip() in canonical_set:
                    issues.append(
                        ValidationIssue(
                            severity="info",
                            category="hook-dedup",
                            message=(
                                f"Stripped global duplicate "
                                f"{cmd.strip()!r} from {event_name}"
                            ),
                            file_path=source_label,
                            line_number=None,
                        )
                    )
                    continue
                kept_hooks.append(entry)

            if not kept_hooks:
                # All hooks in this matcher were canonical duplicates.
                # Drop the matcher group entirely.
                continue

            # Preserve all keys on the matcher (e.g., "matcher", custom keys)
            # but replace "hooks" with the filtered list.
            new_matcher = {**matcher, "hooks": kept_hooks}
            kept_matchers.append(new_matcher)

        if kept_matchers:
            new_hooks_section[event_name] = kept_matchers
        # else: all matchers for this event were dropped — omit event.

    if new_hooks_section:
        result["hooks"] = new_hooks_section
    else:
        # Entire hooks section is now empty — remove key.
        result.pop("hooks", None)

    return result, issues


# Issue #144: Migration mapping from unified hooks to replaced hooks
# When a unified hook is added, remove the old hooks it replaces
UNIFIED_HOOK_REPLACEMENTS = {
    "unified_pre_tool.py": [
        "pre_tool_use.py",
        "enforce_implementation_workflow.py",
        "batch_permission_approver.py",
    ],
    "unified_prompt_validator.py": [
        "detect_feature_request.py",
    ],
    "unified_post_tool.py": [
        "post_tool_use_error_capture.py",
    ],
    "unified_session_tracker.py": [
        "session_tracker.py",
        "log_agent_completion.py",
        "auto_update_project_progress.py",
    ],
    "unified_git_automation.py": [
        "auto_git_workflow.py",
    ],
}



def log_audit(event: str, context: Dict[str, Any]) -> None:
    """Alias for audit_log (backward compatibility with test mocks).

    Args:
        event: Event description
        context: Event context
    """
    audit_log("settings_merge", event, context)


# =============================================================================
# Ownership-aware canonical settings owner (Issue #1809)
# =============================================================================
#
# THE DEFECT THIS REPLACES
# ------------------------
# Three writers used to replace whole settings blocks:
#
#   sync_settings_hooks._replace_hooks   user_settings["hooks"] = template_hooks
#                                        permissions["deny"]   = canonical_deny
#   sync_dispatcher.dispatcher           user_data["hooks"]    = template_hooks
#   sync_dispatcher.modes                additive merge, success-on-error
#
# Replacing the whole `hooks` key deletes every hook a consumer registered
# themselves on an event the toolkit also uses (measured: a consumer's own
# SessionStart notifier and their own PostToolUse audit hook both destroyed).
# Replacing `permissions.deny` deletes every custom deny entry (measured: one
# custom entry replaced by 57 canonical ones).
#
# THE OWNERSHIP RULE
# ------------------
# A hook registration is TOOLKIT-OWNED iff its command references a hook script
# whose BASENAME is in the toolkit's declared set — derived mechanically from
# `config/install_manifest.json`, the template being applied, and the two
# retirement registries already in this module (UNIFIED_HOOK_REPLACEMENTS,
# CANONICAL_GLOBAL_HOOKS). Ownership is NEVER decided by position in a list and
# NEVER by owning the whole event key.
#
# A deny entry is TOOLKIT-OWNED iff the caller declares it (`owned_deny`), plus
# two classes that are removable regardless of who wrote them:
#   * syntactically invalid patterns (`:*` mid-string — Claude Code rejects)
#   * path-scoped rules for tools Claude Code accepts but never consults
#     (Write/NotebookEdit/Glob/MultiEdit — see settings_generator, Issue #1409)
#
# Everything else — env, custom nested keys, foreign top-level keys, allow/ask,
# custom deny entries, foreign hooks on owned events — is left untouched.


class RefusalClass(str, Enum):
    """Why the owner refused to mutate a settings file.

    A refusal is NEVER success. Each member is a durable, observable reason
    string suitable for a CLI exit message or an audit record.
    """

    ACTIVE_PIPELINE = "active_pipeline"
    SENTINEL_AMBIGUOUS = "sentinel_ambiguous"
    TARGET_PATH_REJECTED = "target_path_rejected"
    LOCK_UNAVAILABLE = "lock_unavailable"
    MALFORMED_TARGET = "malformed_target"
    MALFORMED_TEMPLATE = "malformed_template"
    AMBIGUOUS_OWNERSHIP = "ambiguous_ownership"
    DUPLICATE_OWNED_REGISTRATION = "duplicate_owned_registration"
    LEGACY_OWNED_OVERLAP = "legacy_owned_overlap"
    DIGEST_RACE = "digest_race"
    WRITE_FAILED = "write_failed"


@dataclass
class OwnedSettingsResult:
    """Outcome of one ownership-aware settings update.

    Attributes:
        success: True only when the update was applied (or was a verified
            no-op). A refusal is always False.
        refused: True when the owner declined to write. Mutually exclusive
            with success.
        refusal_class: A :class:`RefusalClass` value, or ``""`` on success.
        reason: Human-readable, durable refusal reason (``""`` on success).
        path: The target settings file.
        changed: Whether the projection differs from what is on disk. True in
            dry-run when a write WOULD have happened.
        owned_hooks_written: Count of toolkit-owned hook entries in the result.
        foreign_hooks_preserved: Count of non-owned hook entries carried over.
        permissions_synced: Whether ``permissions.deny`` changed.
        details: Supplementary data (dropped deny entries, owned basenames...).
    """

    success: bool
    refused: bool = False
    refusal_class: str = ""
    reason: str = ""
    path: str = ""
    changed: bool = False
    owned_hooks_written: int = 0
    foreign_hooks_preserved: int = 0
    permissions_synced: bool = False
    details: Dict[str, Any] = field(default_factory=dict)


# Liveness window for the per-repo pipeline sentinel. Mirrors
# `unified_pre_tool._PIPELINE_STATE_TTL_SECONDS` (30 min). The hook cannot be
# imported from here (it is a hook, not a lib), so the value is restated with
# this cross-reference rather than duplicated silently.
PIPELINE_LIVENESS_TTL_SECONDS = 1800

# Tool prefixes whose PATH-SCOPED permission rules Claude Code accepts but never
# consults (Issue #1409). A `Write(/etc/**)` deny entry is inert by
# construction, so removing it changes no behaviour — and removing the CLASS
# (rather than enumerating `Write(/etc/**)` as a retired instance) is what makes
# the #1409 self-heal durable. BARE `Write` (no parentheses) is a tool-level
# rule and IS consulted; the regex below requires parentheses, so bare tool
# rules are never touched.
INERT_PATH_RULE_TOOLS: Tuple[str, ...] = (
    "Write",
    "NotebookEdit",
    "Glob",
    "MultiEdit",
)

_PERMISSION_RULE_RE = re.compile(r"^(\w+)\((.*)\)$")


def settings_digest(path: Path) -> Optional[str]:
    """Return the sha256 hex digest of a settings file's bytes.

    Args:
        path: Settings file path.

    Returns:
        Hex digest, or None when the file is absent/unreadable. None is a
        legitimate value meaning "no file": it is compared for equality like
        any other digest, so an absent-then-created file registers as a change.
    """
    try:
        return hashlib.sha256(Path(path).read_bytes()).hexdigest()
    except OSError:
        return None


def _serialize_settings(data: Dict[str, Any]) -> str:
    """Serialize settings to the canonical on-disk form.

    Key order is NOT sorted: the projection is built from a deep copy of the
    consumer's own file, so preserving insertion order keeps the diff limited
    to the toolkit-owned entries.

    Args:
        data: Settings dict.

    Returns:
        JSON text with a trailing newline.
    """
    return json.dumps(data, indent=2) + "\n"


def hook_script_basenames(command: Any) -> Set[str]:
    """Extract referenced hook-script basenames (``.py``/``.sh``) from a command.

    Path-form agnostic by design: ``~/.claude/hooks/x.py``,
    ``${CLAUDE_PROJECT_DIR:-$(git rev-parse --show-toplevel)}/.claude/hooks/x.py``
    and ``/abs/path/x.sh`` all yield the same basename, so ownership does not
    depend on which path style a given template generation used.

    Args:
        command: A hook command string (non-strings yield an empty set).

    Returns:
        Set of basenames, e.g. ``{"unified_pre_tool.py"}``.
    """
    names: Set[str] = set()
    if not isinstance(command, str):
        return names
    for token in re.split(r"[\s;|&'\"()<>]+", command):
        if token.endswith(".py") or token.endswith(".sh"):
            base = token.rsplit("/", 1)[-1]
            if base not in ("", ".py", ".sh"):
                names.add(base)
    return names


def _iter_template_hook_entries(hooks: Any) -> Iterable[Dict[str, Any]]:
    """Yield every hook-entry dict in a hooks section, tolerating both shapes."""
    if not isinstance(hooks, dict):
        return
    for groups in hooks.values():
        if not isinstance(groups, list):
            continue
        for group in groups:
            if not isinstance(group, dict):
                continue
            entries = group.get("hooks")
            if isinstance(entries, list):
                for entry in entries:
                    if isinstance(entry, dict):
                        yield entry
            else:
                yield group


def resolve_owned_hook_basenames(
    template: Dict[str, Any],
    manifest_path: Optional[Path] = None,
) -> frozenset:
    """Derive the set of toolkit-owned hook-script basenames.

    Four mechanical sources, unioned — never positional:

    1. Hook commands in the template being applied (the current projection).
    2. ``components.hooks.files`` in ``install_manifest.json`` — the deployment
       manifest that already has force in every consumer repo. A toolkit hook
       that was dropped from the template but is still registered in a consumer
       file is therefore still OWNED, and so can be retired.
    3. :data:`UNIFIED_HOOK_REPLACEMENTS` — the existing retirement registry
       (both the unified hooks and the hooks they replaced).
    4. :data:`CANONICAL_GLOBAL_HOOKS` — the global-tier hook commands.

    Args:
        template: Template settings dict (the owned projection).
        manifest_path: Optional path to ``install_manifest.json``.

    Returns:
        Frozen set of basenames. A basename NOT in this set belongs to the
        consumer and must survive untouched.
    """
    names: Set[str] = set()

    for entry in _iter_template_hook_entries(
        template.get("hooks") if isinstance(template, dict) else None
    ):
        names |= hook_script_basenames(entry.get("command", ""))

    for unified, replaced in UNIFIED_HOOK_REPLACEMENTS.items():
        names.add(unified)
        names.update(replaced)

    for command in CANONICAL_GLOBAL_HOOKS:
        names |= hook_script_basenames(command)

    if manifest_path is not None:
        try:
            manifest = json.loads(Path(manifest_path).read_text(encoding="utf-8"))
            hook_files = (
                manifest.get("components", {}).get("hooks", {}).get("files", []) or []
            )
            for rel in hook_files:
                if isinstance(rel, str) and rel.endswith((".py", ".sh")):
                    names.add(rel.rsplit("/", 1)[-1])
        except (OSError, json.JSONDecodeError, AttributeError):
            # A missing/unreadable manifest narrows ownership (fewer entries
            # are claimed), which fails toward PRESERVING consumer config.
            pass

    return frozenset(names)


def _entry_is_owned(entry: Any, owned: frozenset) -> Tuple[bool, bool]:
    """Classify one hook entry.

    Args:
        entry: A hook entry (expected: dict with a string ``command``).
        owned: Owned basename set.

    Returns:
        ``(is_owned, is_ambiguous)``. Ambiguous means the shape makes ownership
        undecidable — the caller must refuse rather than guess.
    """
    if not isinstance(entry, dict):
        return False, True
    command = entry.get("command")
    if command is None:
        # A group-shaped dict with no command and no nested hooks: not a hook
        # registration we can attribute. Preserve it.
        return False, False
    if not isinstance(command, str):
        return False, True
    return bool(hook_script_basenames(command) & owned), False


def _project_hooks(
    existing: Any,
    template_hooks: Any,
    owned: frozenset,
) -> Tuple[Optional[Dict[str, Any]], int, int, int, str]:
    """Build the merged hooks section: strip owned entries, re-add the projection.

    Foreign entries keep their original relative order and come first; the
    template projection is appended. That ordering is what makes a repeat run
    byte-stable: run N+1 strips exactly what run N appended.

    Args:
        existing: Existing ``hooks`` value from the target file.
        template_hooks: ``hooks`` value from the template.
        owned: Owned basename set.

    Returns:
        ``(merged_hooks, owned_count, foreign_count, retired_count,
        ambiguity_reason)`` where ``retired_count`` is the number of
        toolkit-owned entries stripped from the existing file (the migration
        count the deleted ``_merge_hooks`` reported as ``hooks_migrated``).
        ``merged_hooks`` is None when ``ambiguity_reason`` is non-empty.
    """
    if existing is None:
        existing = {}
    if not isinstance(existing, dict):
        return None, 0, 0, 0, (
            f"target 'hooks' is {type(existing).__name__}, expected object — "
            "toolkit ownership cannot be determined"
        )

    merged: Dict[str, List[Any]] = {}
    foreign_count = 0
    retired_count = 0

    for event, groups in existing.items():
        if not isinstance(groups, list):
            return None, 0, 0, 0, (
                f"target hooks.{event} is {type(groups).__name__}, expected list of "
                "matcher groups — toolkit ownership cannot be determined"
            )
        kept_groups: List[Any] = []
        for group in groups:
            if not isinstance(group, dict):
                return None, 0, 0, 0, (
                    f"target hooks.{event} contains a {type(group).__name__} entry, "
                    "expected matcher-group objects — toolkit ownership cannot be "
                    "determined"
                )
            entries = group.get("hooks")
            if entries is None:
                is_owned, ambiguous = _entry_is_owned(group, owned)
                if ambiguous:
                    return None, 0, 0, 0, (
                        f"target hooks.{event} has a registration whose 'command' is "
                        "not a string — toolkit ownership cannot be determined"
                    )
                if is_owned:
                    retired_count += 1
                else:
                    kept_groups.append(group)
                    foreign_count += 1
                continue
            if not isinstance(entries, list):
                return None, 0, 0, 0, (
                    f"target hooks.{event} has a matcher group whose 'hooks' is "
                    f"{type(entries).__name__}, expected list — toolkit ownership "
                    "cannot be determined"
                )
            kept_entries: List[Any] = []
            for entry in entries:
                is_owned, ambiguous = _entry_is_owned(entry, owned)
                if ambiguous:
                    return None, 0, 0, 0, (
                        f"target hooks.{event} has an unattributable registration "
                        f"({type(entry).__name__}) — toolkit ownership cannot be "
                        "determined"
                    )
                if is_owned:
                    retired_count += 1
                else:
                    kept_entries.append(entry)
                    foreign_count += 1
            if kept_entries:
                kept_groups.append({**group, "hooks": kept_entries})
        if kept_groups:
            merged[event] = kept_groups

    owned_count = 0
    if template_hooks:
        if not isinstance(template_hooks, dict):
            return None, 0, 0, 0, (
                f"template 'hooks' is {type(template_hooks).__name__}, expected object"
            )
        for event, groups in template_hooks.items():
            if not isinstance(groups, list):
                return None, 0, 0, 0, (
                    f"template hooks.{event} is {type(groups).__name__}, expected list"
                )
            if not groups:
                continue
            merged.setdefault(event, [])
            for group in groups:
                merged[event].append(copy.deepcopy(group))
            owned_count += sum(
                1 for _ in _iter_template_hook_entries({event: groups})
            )

    return merged, owned_count, foreign_count, retired_count, ""


def _check_owned_conflicts(
    merged_hooks: Dict[str, Any], owned: frozenset
) -> Optional[Tuple[RefusalClass, str]]:
    """Refuse projections that would double-fire an owned hook.

    Two classes, both computed on the RESULT (so a stripping miss is caught as
    well as a bad template):

    * the same owned basename registered more than once for one lifecycle event
      via distinct registrations — an exact duplicate that fires twice;
    * a retired owned hook registered alongside the unified hook that supersedes
      it — semantic overlap between a legacy owned entry and a new owned entry.

    Args:
        merged_hooks: The hooks section about to be written.
        owned: Owned basename set.

    Returns:
        ``(refusal_class, reason)`` or None when the projection is clean.
    """
    for event, groups in merged_hooks.items():
        counts: Dict[str, int] = {}
        for group in groups:
            if not isinstance(group, dict):
                continue
            entries = group.get("hooks")
            entries = entries if isinstance(entries, list) else [group]
            for entry in entries:
                if not isinstance(entry, dict):
                    continue
                for base in hook_script_basenames(entry.get("command", "")) & owned:
                    counts[base] = counts.get(base, 0) + 1

        duplicates = sorted(b for b, n in counts.items() if n > 1)
        if duplicates:
            return RefusalClass.DUPLICATE_OWNED_REGISTRATION, (
                f"toolkit-owned hook(s) {duplicates} would be registered more than "
                f"once on lifecycle event '{event}' and fire twice per invocation; "
                "refusing to write"
            )

        present = set(counts)
        for unified, replaced in UNIFIED_HOOK_REPLACEMENTS.items():
            overlap = present & set(replaced)
            if unified in present and overlap:
                return RefusalClass.LEGACY_OWNED_OVERLAP, (
                    f"lifecycle event '{event}' would register both the unified hook "
                    f"'{unified}' and the retired hook(s) {sorted(overlap)} it "
                    "replaces; refusing to write overlapping owned entries"
                )
    return None


def _deny_entry_is_removable(entry: Any) -> bool:
    """Whether a deny entry may be dropped regardless of who authored it.

    Two classes only:

    * invalid syntax — ``:*`` anywhere other than the end of the rule body.
      Claude Code treats prefix-matching ``:*`` as terminal, so a mid-string
      occurrence never matches anything.
    * inert path-scoped rules for :data:`INERT_PATH_RULE_TOOLS`. Claude Code
      accepts them and never consults them (Issue #1409), so dropping one
      changes no behaviour while letting a corrected canonical rule land.

    Args:
        entry: A permission rule string.

    Returns:
        True when the entry is removable.
    """
    if not isinstance(entry, str):
        return False
    match = _PERMISSION_RULE_RE.match(entry)
    if not match:
        return False
    tool, body = match.group(1), match.group(2)
    if ":*" in body and not body.endswith(":*"):
        return True
    return tool in INERT_PATH_RULE_TOOLS


def _project_deny(
    existing_permissions: Any,
    owned_deny: Optional[Iterable[str]],
) -> Tuple[Optional[Dict[str, Any]], List[str], str]:
    """Build the merged ``permissions`` block.

    ``allow`` and ``ask`` are NEVER touched — they are consumer surface. Only
    ``deny`` is owned, and only the entries the caller declares.

    Args:
        existing_permissions: Existing ``permissions`` value (may be absent).
        owned_deny: The toolkit's declared deny entries, or None to leave
            ``permissions`` entirely alone.

    Returns:
        ``(permissions_or_None, dropped_entries, ambiguity_reason)``.
    """
    if owned_deny is None:
        return None, [], ""

    if existing_permissions is None:
        existing_permissions = {}
    if not isinstance(existing_permissions, dict):
        return None, [], (
            f"target 'permissions' is {type(existing_permissions).__name__}, "
            "expected object — toolkit ownership cannot be determined"
        )

    existing_deny = existing_permissions.get("deny", [])
    if existing_deny is None:
        existing_deny = []
    if not isinstance(existing_deny, list):
        return None, [], (
            f"target 'permissions.deny' is {type(existing_deny).__name__}, expected "
            "list — toolkit ownership cannot be determined"
        )

    owned_list: List[str] = []
    for entry in owned_deny:
        if entry not in owned_list:
            owned_list.append(entry)
    owned_set = set(owned_list)

    preserved: List[str] = []
    dropped: List[str] = []
    for entry in existing_deny:
        if entry in owned_set:
            continue  # re-added below in canonical order
        if _deny_entry_is_removable(entry):
            dropped.append(entry)
            continue
        if entry not in preserved:
            preserved.append(entry)

    permissions = copy.deepcopy(existing_permissions)
    permissions["deny"] = preserved + owned_list
    return permissions, dropped, ""


def _target_repo_root(target_path: Path) -> Path:
    """Resolve the repo root that owns a settings file.

    ``<root>/.claude/settings.json`` and ``<root>/.claude/settings.local.json``
    both resolve to ``<root>``; any other layout resolves to the file's own
    directory, which keeps sentinel resolution contained (it must never walk
    out of an explicit or temporary target directory).

    Args:
        target_path: Settings file path.

    Returns:
        The repo root for sentinel resolution.
    """
    parent = target_path.parent
    if parent.name == ".claude":
        return parent.parent
    return parent


# WHY THERE IS NO `allowed_root` PARAMETER (Issue #1809, review corrections 4 & 5)
# -------------------------------------------------------------------------------
# Two drafts of this module tried to widen `security_utils.validate_path`'s
# whitelist so the toolkit could write settings into OTHER repositories, as
# `scripts/deploy-all.sh` lines 377 and 614 do for `$HOME/Dev/$repo`. Both were
# withdrawn, and the reasoning is recorded here so a third attempt does not
# repeat it:
#
#   Draft 1 passed the root derived from the target path itself. That is
#   tautological — the caller self-approves whatever path it was handed, and
#   Layer 4 becomes a no-op on exactly the attack it exists for.
#
#   Draft 2 required `<root>/.git` to exist. Also insufficient: a `.git`
#   directory is a filesystem feature that whoever chose the target controls
#   (`mkdir -p /anywhere/.git` forges it). It grants nothing. The claim that it
#   made the grant "unforgeable" was FALSE and has been deleted rather than
#   softened.
#
# A legitimate grant needs a root selected from the INVOKING process's own
# trusted context BEFORE the target is parsed. No such source exists within this
# slice: `deploy-all.sh` runs with its cwd in the autonomous-dev repo, so the
# process's own root is never the consumer repo it is syncing, and the consumer
# root arrives only as argv from the same actor that chose the target.
#
# Therefore cross-repo writes FAIL CLOSED. See the support matrix in
# `apply_owned_settings`. Narrower and true beats broader and forgeable.


#: Sub-path from a repo root to its pipeline sentinel's directory.
#:
#: READ-ONLY PROJECTION — layout owner is ``pipeline_state.
#: get_legacy_sentinel_path``, which remains the canonical resolver for every
#: WRITER in the deployed stack. This is not a competing owner: it is the
#: side-effect-free projection used only for ADMISSION, and the file name itself
#: is imported from the owner (``LEGACY_SENTINEL_FILENAME``) rather than
#: restated.
#:
#: Why a projection is needed at all (Issue #1809 remediation, GAP 2):
#: ``get_legacy_sentinel_path`` does not merely resolve — at
#: ``pipeline_state.py:98-105`` it ``mkdir``s ``<repo>/.claude/local`` AND
#: ``chmod``s it to 0o700 even when it already exists. Calling it from an
#: admission check would therefore MUTATE the target (creating a directory, or
#: silently changing an existing directory's permissions) before deciding
#: whether mutation is allowed at all — inverting the guarantee the check
#: exists to provide. Its mkdir/chmod behaviour is relied on by writers across
#: the deployed stack, so it is deliberately NOT changed here.
_SENTINEL_DIR_PARTS: Tuple[str, str] = (".claude", "local")


def _resolve_sentinel_readonly(repo_root: Path) -> Path:
    """Resolve a repo's sentinel path with ZERO filesystem side effects.

    Pure path arithmetic: no ``mkdir``, no ``chmod``, no ``stat`` of parents.

    DERIVED PROJECTION, NOT A SECOND AUTHORITY
    ------------------------------------------
    ``pipeline_state.get_legacy_sentinel_path`` OWNS the sentinel layout. This
    function is its read-only projection for ADMISSION only, and it exists
    solely because the owner has write side effects (``mkdir`` +
    ``chmod`` 0o700, ``pipeline_state.py:98-105``) that an admission check must
    not perform — see :data:`_SENTINEL_DIR_PARTS`.

    The file NAME is imported from the owner. The directory layout cannot be:
    ``pipeline_state`` inlines ``.claude`` / ``local`` at line 98 and exports no
    constant for it, and this slice may not add one. That residual duplication
    is therefore held honest by a CONFORMANCE TEST asserting path equality
    against the canonical helper —
    ``test_readonly_sentinel_projection_conforms_to_canonical_owner``. **If that
    test fails, admission is checking the WRONG path and would PERMIT during a
    live run: the worst failure direction for this gate. It is
    release-blocking and must not be deleted as "flaky legacy".**

    Args:
        repo_root: The repository root whose sentinel is wanted.

    Returns:
        The sentinel path. Nothing is created; the path may not exist.
    """
    try:
        try:
            from .pipeline_state import LEGACY_SENTINEL_FILENAME  # type: ignore
        except ImportError:
            from pipeline_state import LEGACY_SENTINEL_FILENAME  # type: ignore
    except ImportError:
        # Cannot even learn the canonical file name: caller must treat this as
        # ambiguous rather than guess a name that may drift from the owner.
        raise

    return Path(repo_root).joinpath(*_SENTINEL_DIR_PARTS, LEGACY_SENTINEL_FILENAME)


def _pipeline_liveness(target_path: Path) -> Tuple[str, str]:
    """Classify pipeline activity for the repo that owns ``target_path``.

    Reuses the EXISTING three-state integrity classifier
    (``pipeline_completion_state.sentinel_integrity``) and the EXISTING sentinel
    location, resolved through the side-effect-free projection
    :func:`_resolve_sentinel_readonly`. No new lock manager, store or state file
    is introduced, and **nothing is created or chmod'd by this check** — an
    admission test that mutated the target would defeat its own purpose.

    Scope is deliberately the TARGET repo, not the calling process: the question
    is "would this write land under a live run of the repo being modified?".
    ``PIPELINE_STATE_FILE`` is therefore not consulted — it redirects the
    CALLER's sentinel, which is a different repo in the deploy case.

    Args:
        target_path: Settings file about to be mutated.

    Returns:
        ``(verdict, reason)`` with verdict in ``{"idle", "active", "ambiguous"}``.
    """
    try:
        try:
            from .pipeline_completion_state import (  # type: ignore
                SentinelIntegrity,
                sentinel_integrity,
            )
        except ImportError:
            from pipeline_completion_state import (  # type: ignore
                SentinelIntegrity,
                sentinel_integrity,
            )
        sentinel = _resolve_sentinel_readonly(_target_repo_root(target_path))
    except ImportError as exc:
        # The detector itself is unavailable: that is an ambiguous state, and
        # ambiguity fails toward refusal for a MUTATION.
        return "ambiguous", (
            f"pipeline sentinel detector unavailable ({exc}); cannot prove the "
            "target repo is idle"
        )

    integrity = sentinel_integrity(sentinel_path=str(sentinel))

    if integrity == SentinelIntegrity.ABSENT:
        return "idle", ""
    if integrity == SentinelIntegrity.CORRUPT:
        return "ambiguous", (
            f"pipeline sentinel {sentinel} exists but cannot be read as a JSON "
            "object; refusing to mutate settings on ambiguous run state"
        )

    try:
        age = time.time() - sentinel.stat().st_mtime
    except OSError as exc:
        return "ambiguous", f"cannot stat pipeline sentinel {sentinel}: {exc}"

    if age <= PIPELINE_LIVENESS_TTL_SECONDS:
        return "active", (
            f"an /implement run is live for {_target_repo_root(target_path)} "
            f"(sentinel {sentinel} touched {int(age)}s ago, within the "
            f"{PIPELINE_LIVENESS_TTL_SECONDS}s liveness window); refusing to mutate "
            "settings mid-run"
        )
    return "idle", ""


def check_mutation_admission(target: Path) -> Tuple[bool, str, str]:
    """THE single admission check for mutating a repo's Claude configuration.

    Issue #1809 (review correction 8). A refusal inside
    :func:`apply_owned_settings` fires only when the SETTINGS write is reached.
    Routes that copy files first — ``SyncDispatcher.sync_marketplace`` copies
    commands, hooks and agents before Step 2.5 — would already have mutated the
    installed tree by then, so "we refuse on a live run" would be a false claim
    for those routes.

    This function exists so the check can be hoisted to the START of such a
    route while there is still exactly ONE admission implementation: both
    :func:`apply_owned_settings` and the dispatcher call this, and it delegates
    to :func:`_pipeline_liveness`. It is not a copy.

    Args:
        target: Any path inside the repo about to be mutated (a settings file,
            or the ``.claude`` directory itself).

    Returns:
        ``(admitted, refusal_class, reason)``. ``admitted`` is True only when the
        target repo is provably idle. An ambiguous sentinel is NOT admitted:
        ambiguity fails toward refusal for a mutation.
    """
    verdict, reason = _pipeline_liveness(target)
    if verdict == "active":
        return False, RefusalClass.ACTIVE_PIPELINE.value, reason
    if verdict == "ambiguous":
        return False, RefusalClass.SENTINEL_AMBIGUOUS.value, reason
    return True, "", ""


@contextmanager
def _settings_transaction_lock(target_path: Path):
    """Serialize the whole read -> merge -> digest-check -> replace transaction.

    Follows the sidecar-lockfile pattern already used by
    ``pipeline_completion_state._locked_rmw`` (Issue #1170): a sibling lockfile
    opened ``"a+"`` so it auto-creates and is never truncated, held under
    ``fcntl.flock(LOCK_EX)`` for the entire critical section.

    That function itself is NOT reusable here, and the difference matters: it
    fails OPEN on a lock failure so a gate is never blocked. A settings MUTATION
    must fail toward REFUSAL instead, so this context manager yields False when
    the lock cannot be taken and the caller refuses.

    HONEST LIMITATION — this is NOT atomic compare-and-swap:
        The lock binds TOOLKIT writers only. An external, non-toolkit writer —
        the user's editor, Claude Code itself, another tool — does not take this
        lock and is therefore NOT serialized. The digest re-check performed
        inside the lock immediately before the rename NARROWS that external
        window to the interval between the check and ``os.replace``; it does not
        eliminate it. Do not describe this as a solved race. What IS guaranteed:
        two toolkit writers never interleave, and any external change observed
        by the re-check causes a refusal rather than an overwrite.

    Args:
        target_path: The settings file being mutated (the lockfile is a sibling).

    Yields:
        True when the exclusive lock is held, False when it could not be taken.
    """
    lock_path = target_path.parent / f".{target_path.name}.lock"
    handle = None
    acquired = False
    try:
        try:
            target_path.parent.mkdir(parents=True, exist_ok=True)
            handle = open(lock_path, "a+")
            fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
            acquired = True
        except (OSError, ValueError):
            acquired = False
        yield acquired
    finally:
        if handle is not None:
            if acquired:
                try:
                    fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
                except OSError:
                    pass
            try:
                handle.close()
            except OSError:
                pass


def _commit_settings(
    target_path: Path, text: str, digest_at_read: Optional[str]
) -> Optional[Tuple[RefusalClass, str]]:
    """Replace ``target_path`` with ``text``, refusing on any observed change.

    MUST be called with :func:`_settings_transaction_lock` held. The digest
    captured at read time is re-verified as late as possible — immediately
    before the rename — and any mismatch is a refusal, never an overwrite.

    An interrupted transaction leaves the target's bytes untouched: the payload
    goes to a sibling temp file and only ``os.replace`` (atomic on POSIX) makes
    it visible. The temp file is removed on every failure path, including
    ``KeyboardInterrupt`` (hence ``BaseException``, not ``Exception``, in the
    cleanup arm).

    Args:
        target_path: Destination settings file (already symlink-resolved).
        text: Serialized payload.
        digest_at_read: Digest observed when the target was read.

    Returns:
        None on success, else ``(refusal_class, reason)``.
    """
    try:
        target_path.parent.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        return RefusalClass.WRITE_FAILED, f"cannot create {target_path.parent}: {exc}"

    fd, tmp = tempfile.mkstemp(
        dir=str(target_path.parent), prefix=".settings-", suffix=".json.tmp"
    )
    committed = False
    try:
        try:
            os.write(fd, text.encode("utf-8"))
        finally:
            os.close(fd)
        os.chmod(tmp, 0o600)

        # LATEST POSSIBLE re-check: everything that could fail is already done,
        # so only the rename follows. A change here means an external writer
        # landed inside the lock's blind spot — refuse, do not overwrite it.
        current = settings_digest(target_path)
        if current != digest_at_read:
            return RefusalClass.DIGEST_RACE, (
                f"{target_path} changed between read and write (digest "
                f"{digest_at_read} -> {current}); refusing to overwrite a "
                "concurrent modification"
            )

        os.replace(tmp, str(target_path))
        committed = True
    except Exception as exc:
        return RefusalClass.WRITE_FAILED, (
            f"atomic write to {target_path} failed ({exc}); target left unchanged"
        )
    finally:
        if not committed:
            try:
                os.unlink(tmp)
            except OSError:
                pass
    return None


def apply_owned_settings(
    target_path: Path,
    template: Dict[str, Any],
    *,
    manifest_path: Optional[Path] = None,
    owned_deny: Optional[Iterable[str]] = None,
    dry_run: bool = False,
    expected_digest: Optional[str] = None,
) -> OwnedSettingsResult:
    """THE canonical ownership-aware settings mutation. One owner, all layers.

    Updates ONLY toolkit-owned entries in ``target_path``:

    * toolkit-owned hook registrations are retired and re-written from
      ``template``; unrelated hooks on the SAME lifecycle event survive;
    * ``permissions.deny`` gains every entry in ``owned_deny`` while custom
      entries survive; ``allow`` and ``ask`` are never touched;
    * ``env``, custom nested keys and foreign top-level keys are untouched.

    TARGET-PATH SUPPORT MATRIX — what is grounded, and what is refused
    -----------------------------------------------------------------
    Authorisation is whatever the EXISTING
    :func:`security_utils.validate_path` grants, unmodified. There is no
    widening parameter (see the module comment above for the two withdrawn
    drafts and why).

    * **user layer** — ``~/.claude/settings.json`` and anything else in the
      fixed ``~/.claude`` subtree. SUPPORTED.
    * **project layer** — ``<repo>/.claude/settings.json`` where ``<repo>`` is
      the repository the INVOKING process itself runs in (``PROJECT_ROOT``,
      resolved by ``security_utils`` from its own cwd). SUPPORTED.
    * **local layer** — ``<repo>/.claude/settings.local.json``, same repo.
      SUPPORTED.
    * **explicit path** — only inside ``PROJECT_ROOT`` or ``~/.claude`` (plus
      the system temp dir while pytest runs). SUPPORTED within that profile;
      anything outside it is REFUSED.
    * **cross-repo / out-of-profile writes** — e.g. ``deploy-all.sh`` lines 377
      and 614 syncing ``$HOME/Dev/$repo/.claude/settings.json`` while running
      from the autonomous-dev checkout. **REFUSED — FAIL CLOSED. This route is
      UNMEASURED and unsupported by this slice.** It needs a trusted root
      supplied from the invoking process's own context, which does not exist
      here; ``deploy-all.sh`` already treats a non-zero sync as a warning, so
      the refusal surfaces rather than corrupting a consumer repo.

    ``..`` traversal, over-long paths, external symlinks and out-of-profile
    targets are all refusals BEFORE the first write, with zero mutation.

    SYMLINKED TARGETS — two outcomes, both measured:
        * A symlink whose target escapes ``PROJECT_ROOT``/``~/.claude`` is
          REFUSED outright by ``validate_path``'s Layer 2, before any read.
          MEASURED: a temp-dir symlink pointing at a sibling temp file refuses
          with ``target_path_rejected`` and the LINK IS LEFT INTACT. This is the
          common case and it is the honest headline.
        * A symlink that validation accepts (target inside
          ``PROJECT_ROOT``/``~/.claude``) is followed: the transaction operates
          on the REAL file (``os.path.realpath``) and places its temp file in
          the RESOLVED parent, so the rename replaces the final target and the
          consumer's link keeps pointing at it. Writing to the link path
          directly would have had ``os.replace`` overwrite the LINK ITSELF with
          a regular file — a preservation violation in its own right.

    CONCURRENCY — a lock plus a late re-check, NOT atomic compare-and-swap:
        The whole read -> merge -> re-check -> rename runs under an exclusive
        ``flock`` on a sidecar lockfile (see
        :func:`_settings_transaction_lock`). Two toolkit writers can never
        interleave. An EXTERNAL writer (the user's editor, Claude Code itself)
        does not take the lock and is NOT serialized; the digest re-check
        immediately before the rename narrows that window and turns any change
        it observes into a refusal, but the interval between that re-check and
        ``os.replace`` remains undetectable. This is a narrowed race, not a
        solved one.

    Refuses BEFORE the first write, with zero mutation, when: the path is
    rejected by validation; the transaction lock cannot be taken; a run is live
    for the target repo; the sentinel is ambiguous; the target or template JSON
    is malformed; ownership cannot be determined; the projection would
    double-fire an owned hook; or the target changed during the transaction.

    Args:
        target_path: Settings file to update (may be absent — it is created).
        template: The toolkit projection (a settings-shaped dict).
        manifest_path: Optional ``install_manifest.json`` for ownership.
        owned_deny: Toolkit-declared deny entries. None leaves ``permissions``
            completely alone.
        dry_run: Compute the projection without writing.
        expected_digest: Refuse unless the target's current digest equals this.

    Returns:
        An :class:`OwnedSettingsResult`. ``success is False`` for every refusal.
    """
    target_path = Path(target_path)
    result_path = str(target_path)
    notes: List[str] = []

    def _refuse(cls: RefusalClass, reason: str) -> OwnedSettingsResult:
        audit_log(
            "settings_owner",
            "refused",
            {"path": result_path, "refusal_class": cls.value, "reason": reason},
        )
        return OwnedSettingsResult(
            success=False,
            refused=True,
            refusal_class=cls.value,
            reason=reason,
            path=result_path,
            details={"notes": notes},
        )

    # --- Step 0: path policy (refuses before anything is read or written).
    # The EXISTING validator, unmodified and unparameterised — a caller cannot
    # widen it, so an out-of-profile target is refused no matter what any
    # argument says. Layers enforced: traversal, length, symlink escape,
    # whitelist.
    try:
        validate_path(
            target_path,
            purpose="toolkit-owned settings target",
            allow_missing=True,
        )
    except ValueError as exc:
        return _refuse(
            RefusalClass.TARGET_PATH_REJECTED, str(exc).splitlines()[0]
        )

    # Symlink policy (a): operate on the REAL file so the link survives.
    if target_path.is_symlink():
        real_target = Path(os.path.realpath(target_path))
        notes.append(f"target is a symlink; writing through to {real_target}")
        target_path = real_target

    if not isinstance(template, dict):
        return _refuse(
            RefusalClass.MALFORMED_TEMPLATE,
            f"template is {type(template).__name__}, expected a settings object",
        )
    template_hooks = template.get("hooks", {})
    if template_hooks and not isinstance(template_hooks, dict):
        return _refuse(
            RefusalClass.MALFORMED_TEMPLATE,
            f"template 'hooks' is {type(template_hooks).__name__}, expected object",
        )

    # --- Steps 1-4 run inside the transaction lock so no other TOOLKIT
    # writer can interleave. See _settings_transaction_lock for the honest
    # limitation regarding external (non-toolkit) writers.
    def _transact() -> OwnedSettingsResult:
        # --- Step 1: read the target (digest first, so the CAS baseline is exact)
        digest_at_read = settings_digest(target_path)
        if expected_digest is not None and expected_digest != digest_at_read:
            return _refuse(
                RefusalClass.DIGEST_RACE,
                f"{target_path} digest {digest_at_read} does not match the expected "
                f"{expected_digest}; refusing to overwrite a concurrent modification",
            )

        existing: Dict[str, Any] = {}
        if digest_at_read is not None:
            raw = target_path.read_bytes()
            if raw.strip():
                try:
                    parsed = json.loads(raw.decode("utf-8"))
                except (json.JSONDecodeError, UnicodeDecodeError) as exc:
                    return _refuse(
                        RefusalClass.MALFORMED_TARGET,
                        f"{target_path} is not valid JSON ({exc}); refusing to guess at "
                        "its contents",
                    )
                if not isinstance(parsed, dict):
                    return _refuse(
                        RefusalClass.MALFORMED_TARGET,
                        f"{target_path} contains a JSON {type(parsed).__name__}, expected "
                        "an object",
                    )
                existing = parsed

        # --- Step 2: active-run / sentinel refusal (before any projection work).
        # Same admission owner the dispatcher hoists to the start of its route.
        admitted, admission_class, admission_reason = check_mutation_admission(
            target_path
        )
        if not admitted:
            return _refuse(RefusalClass(admission_class), admission_reason)

        # --- Step 3: ownership-aware projection
        owned = resolve_owned_hook_basenames(template, manifest_path=manifest_path)

        merged_hooks, owned_count, foreign_count, retired_count, hooks_reason = (
            _project_hooks(existing.get("hooks"), template_hooks, owned)
        )
        if hooks_reason:
            cls = (
                RefusalClass.MALFORMED_TEMPLATE
                if hooks_reason.startswith("template ")
                else RefusalClass.AMBIGUOUS_OWNERSHIP
            )
            return _refuse(cls, hooks_reason)

        conflict = _check_owned_conflicts(merged_hooks or {}, owned)
        if conflict is not None:
            return _refuse(*conflict)

        permissions, dropped_deny, perms_reason = _project_deny(
            existing.get("permissions"), owned_deny
        )
        if perms_reason:
            return _refuse(RefusalClass.AMBIGUOUS_OWNERSHIP, perms_reason)

        projected = copy.deepcopy(existing)
        if merged_hooks:
            projected["hooks"] = merged_hooks
        elif "hooks" in projected:
            projected["hooks"] = {}
        if permissions is not None:
            projected["permissions"] = permissions

        deny_changed = False
        if permissions is not None:
            existing_perms = existing.get("permissions")
            old_deny = (
                existing_perms.get("deny", [])
                if isinstance(existing_perms, dict)
                else []
            )
            deny_changed = old_deny != permissions.get("deny", [])

        changed = projected != existing or digest_at_read is None

        def _ok() -> OwnedSettingsResult:
            return OwnedSettingsResult(
                success=True,
                path=result_path,
                changed=changed,
                owned_hooks_written=owned_count,
                foreign_hooks_preserved=foreign_count,
                permissions_synced=bool(deny_changed),
                details={
                    "deny_dropped": dropped_deny,
                    "hooks_retired": retired_count,
                    "owned_basenames": sorted(owned),
                    "dry_run": dry_run,
                    "notes": notes,
                },
            )

        # --- Step 4: commit (skip entirely when nothing changed -> byte-stable)
        if dry_run or not changed:
            return _ok()

        failure = _commit_settings(
            target_path, _serialize_settings(projected), digest_at_read
        )
        if failure is not None:
            return _refuse(*failure)

        audit_log(
            "settings_owner",
            "applied",
            {
                "path": result_path,
                "owned_hooks_written": owned_count,
                "foreign_hooks_preserved": foreign_count,
                "deny_dropped": dropped_deny,
            },
        )
        return _ok()

    with _settings_transaction_lock(target_path) as locked:
        if not locked:
            return _refuse(
                RefusalClass.LOCK_UNAVAILABLE,
                f"could not acquire the exclusive settings transaction lock for "
                f"{target_path}; refusing rather than writing unserialized",
            )
        return _transact()
