"""
Settings merger for merging settings.local.json with template configuration.

This module provides functionality to merge template settings (e.g., PreToolUse hooks)
with user's existing settings.local.json while preserving user customizations.

Security Features:
- Path validation (CWE-22: Path Traversal)
- Symlink rejection (CWE-59: Improper Link Resolution)
- Atomic writes with secure permissions (0o600)
- Audit logging for all operations

Design Pattern:
- Deep merge: Nested dictionaries are merged recursively
- Hooks merge by lifecycle event (PreToolUse, PostToolUse, etc.)
- User customizations preserved (permissions, custom config)
- Duplicate hooks avoided

Usage:
    merger = SettingsMerger(project_root="/path/to/project")
    result = merger.merge_settings(
        template_path=Path("templates/settings.local.json"),
        user_path=Path(".claude/settings.local.json"),
        write_result=True
    )

See Also:
    - docs/LIBRARIES.md section 29 for API documentation
    - tests/unit/lib/test_settings_merger.py for test cases
"""

import copy
import json
import os
import re
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

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


@dataclass
class MergeResult:
    """Result of settings merge operation.

    Attributes:
        success: Whether merge succeeded
        message: Human-readable result message
        settings_path: Path to merged settings file (None if merge failed)
        hooks_added: Number of hooks added from template
        hooks_preserved: Number of existing hooks preserved
        hooks_migrated: Number of old hooks removed during migration
        details: Additional result details (errors, warnings, etc.)
    """

    success: bool
    message: str
    settings_path: Optional[str] = None
    hooks_added: int = 0
    hooks_preserved: int = 0
    hooks_migrated: int = 0
    details: Dict[str, Any] = field(default_factory=dict)


class SettingsMerger:
    """Merge settings.local.json with template configuration.

    This class handles merging template settings (e.g., PreToolUse hooks) with
    user's existing settings while preserving user customizations.

    Security:
        - Validates all paths against project root
        - Rejects symlinks and path traversal attempts
        - Atomic writes with secure permissions (0o600)
        - Audit logging for all operations

    Attributes:
        project_root: Project root directory for path validation
    """

    def __init__(self, project_root: str):
        """Initialize settings merger.

        Args:
            project_root: Project root directory for path validation
        """
        self.project_root = Path(project_root)

    def merge_settings(
        self, template_path: Path, user_path: Path, write_result: bool = True
    ) -> MergeResult:
        """Merge template settings with user settings.

        This method performs a deep merge of template settings with existing
        user settings, with special handling for hooks:

        1. Read template and user settings (if exists)
        2. Deep merge dictionaries (nested objects preserved)
        3. Merge hooks by lifecycle event (avoid duplicates)
        4. Atomic write to user path (if write_result=True)

        Args:
            template_path: Path to template settings.local.json
            user_path: Path to user settings.local.json
            write_result: Whether to write merged settings (False for dry-run)

        Returns:
            MergeResult with success status, counts, and details

        Security:
            - Validates both paths against project root
            - Rejects symlinks and path traversal attempts
            - Audit logs all operations
        """
        try:
            # Step 1: Validate paths (security)
            # Validate template path
            try:
                validate_path(
                    template_path,
                    purpose="template settings",
                    allow_missing=False,
                )
            except ValueError as e:
                audit_log(
                    "settings_merge",
                    "template_validation_failed",
                    {
                        "template_path": str(template_path),
                        "error": str(e),
                    },
                )
                return MergeResult(
                    success=False,
                    message=f"Template path validation failed: {e}",
                    details={"error": str(e)},
                )

            # Check if template exists
            if not template_path.exists():
                audit_log(
                    "settings_merge",
                    "template_not_found",
                    {
                        "template_path": str(template_path),
                    },
                )
                return MergeResult(
                    success=False,
                    message=f"Template settings not found: {template_path}",
                    details={"error": "Template file does not exist"},
                )

            # Validate user path (allow missing since we may create it)
            try:
                validate_path(
                    user_path,
                    purpose="user settings",
                    allow_missing=True,
                )
            except ValueError as e:
                audit_log(
                    "settings_merge",
                    "user_path_validation_failed",
                    {
                        "user_path": str(user_path),
                        "error": str(e),
                    },
                )
                return MergeResult(
                    success=False,
                    message=f"User path validation failed: {e}",
                    details={"error": str(e)},
                )

            # Step 2: Read template settings
            template_data = self._read_json(template_path)
            if template_data is None:
                audit_log(
                    "settings_merge",
                    "template_parse_failed",
                    {
                        "template_path": str(template_path),
                    },
                )
                return MergeResult(
                    success=False,
                    message=f"Failed to parse template JSON: {template_path}",
                    details={"error": "Invalid JSON in template file"},
                )

            # Step 3: Read existing user settings (if exists)
            user_data = {}
            if user_path.exists():
                user_data = self._read_json(user_path)
                if user_data is None:
                    audit_log(
                        "settings_merge",
                        "user_settings_parse_failed",
                        {
                            "user_path": str(user_path),
                        },
                    )
                    return MergeResult(
                        success=False,
                        message=f"Failed to parse user settings JSON: {user_path}",
                        details={"error": "Invalid JSON in user settings file"},
                    )

            # Step 4: Merge dictionaries
            merged_data = self._merge_dicts(user_data, template_data)

            # Step 5: Merge hooks (track counts, migrate old hooks to unified)
            merged_hooks, hooks_added, hooks_preserved, hooks_migrated = self._merge_hooks(
                user_data.get("hooks", {}), template_data.get("hooks", {})
            )
            merged_data["hooks"] = merged_hooks

            # Step 6: Write result (if not dry-run)
            if write_result:
                self._atomic_write(user_path, merged_data)

            # Step 7: Audit log success
            audit_log(
                "settings_merge",
                "merge_completed",
                {
                    "user_path": str(user_path),
                    "template_path": str(template_path),
                    "hooks_added": hooks_added,
                    "hooks_preserved": hooks_preserved,
                    "hooks_migrated": hooks_migrated,
                    "write_result": write_result,
                },
            )

            # Step 8: Return success
            message = "Settings merged successfully"
            if not user_path.exists() or not user_data:
                message = "Settings created from template"
            elif hooks_migrated > 0:
                message = f"Settings merged successfully (migrated {hooks_migrated} hooks to unified)"

            return MergeResult(
                success=True,
                message=message,
                settings_path=str(user_path),
                hooks_added=hooks_added,
                hooks_preserved=hooks_preserved,
                hooks_migrated=hooks_migrated,
                details={
                    "template_path": str(template_path),
                    "write_result": write_result,
                },
            )

        except Exception as e:
            # Catch-all for unexpected errors
            audit_log(
                "settings_merge",
                "unexpected_error",
                {
                    "template_path": str(template_path),
                    "user_path": str(user_path),
                    "error": str(e),
                },
            )
            return MergeResult(
                success=False,
                message=f"Settings merge failed: {e}",
                details={"error": str(e)},
            )

    def _read_json(self, path: Path) -> Optional[Dict[str, Any]]:
        """Read and parse JSON file.

        Args:
            path: Path to JSON file

        Returns:
            Parsed JSON as dictionary, or None if parse fails
        """
        try:
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, OSError) as e:
            # Return None on parse error (caller handles)
            return None

    # Keys whose list values should be unioned (not replaced) during merge.
    # This prevents sync from clobbering user-added permissions entries.
    _UNION_LIST_KEYS = {"allow", "deny", "ask"}

    def _merge_dicts(self, base: Dict, updates: Dict) -> Dict:
        """Deep merge two dictionaries (updates override base).

        This performs a recursive deep merge where:
        - Nested dictionaries are merged recursively
        - Permission lists (allow, deny, ask) are unioned to preserve user entries
        - Other lists are replaced (not merged)
        - Scalar values from updates override base

        Args:
            base: Base dictionary (user settings)
            updates: Updates dictionary (template settings)

        Returns:
            Merged dictionary
        """
        merged = base.copy()

        for key, value in updates.items():
            if key in merged and isinstance(merged[key], dict) and isinstance(value, dict):
                # Recursively merge nested dictionaries
                # Special case: Don't deep merge "hooks" here (handled separately)
                if key == "hooks":
                    # Skip hooks - they're merged separately with duplicate detection
                    continue
                merged[key] = self._merge_dicts(merged[key], value)
            elif (
                key in self._UNION_LIST_KEYS
                and isinstance(value, list)
                and isinstance(merged.get(key), list)
            ):
                # Union permission lists — preserve user entries, add missing template entries
                existing_set = set(merged[key])
                for item in value:
                    if item not in existing_set:
                        merged[key].append(item)
                        existing_set.add(item)
            else:
                # Override with update value (lists, scalars, new keys)
                # But don't override "hooks" key here (handled separately)
                if key != "hooks":
                    merged[key] = value

        return merged

    def _merge_hooks(
        self, existing: Dict, new: Dict
    ) -> Tuple[Dict, int, int, int]:
        """Merge hooks by lifecycle event, avoiding duplicates.

        This merges hooks with special logic:
        - Merge by lifecycle event (PreToolUse, PostToolUse, etc.)
        - Avoid duplicate hooks (by exact dict comparison)
        - Preserve existing hooks (user customizations)
        - Issue #144: Migrate old hooks to unified hooks (remove replaced hooks)

        Args:
            existing: Existing hooks dictionary (user hooks)
            new: New hooks dictionary (template hooks)

        Returns:
            Tuple of (merged_hooks, hooks_added, hooks_preserved, hooks_migrated)
        """
        merged_hooks = {}
        hooks_added = 0
        hooks_preserved = 0
        hooks_migrated = 0

        # Issue #144: Build set of old hooks to remove (based on unified hooks in new)
        hooks_to_remove = set()
        for lifecycle, matcher_configs in new.items():
            for config in matcher_configs:
                if isinstance(config, dict):
                    # Handle nested structure: {"matcher": "*", "hooks": [...]}
                    inner_hooks = config.get("hooks", [config])  # Fallback to config itself if no nested hooks
                    for hook in inner_hooks:
                        if isinstance(hook, dict):
                            cmd = hook.get("command", "")
                            # Check if this is a unified hook
                            for unified_hook, replaced_hooks in UNIFIED_HOOK_REPLACEMENTS.items():
                                if unified_hook in cmd:
                                    # Mark old hooks for removal
                                    hooks_to_remove.update(replaced_hooks)

        # Start with existing hooks (preserve user customizations, migrate old hooks)
        for lifecycle, matcher_configs in existing.items():
            filtered_configs = []
            for config in matcher_configs:
                if isinstance(config, dict):
                    # Handle nested structure: {"matcher": "*", "hooks": [...]}
                    if "hooks" in config:
                        # Nested format - filter inner hooks
                        filtered_inner = []
                        for hook in config.get("hooks", []):
                            if isinstance(hook, dict):
                                cmd = hook.get("command", "")
                                should_remove = False
                                for old_hook in hooks_to_remove:
                                    if old_hook in cmd:
                                        should_remove = True
                                        hooks_migrated += 1
                                        break
                                if not should_remove:
                                    filtered_inner.append(hook)
                                    hooks_preserved += 1
                            else:
                                filtered_inner.append(hook)
                                hooks_preserved += 1
                        # Only add config if it still has hooks
                        if filtered_inner:
                            filtered_configs.append({**config, "hooks": filtered_inner})
                    else:
                        # Flat format - check command directly
                        cmd = config.get("command", "")
                        should_remove = False
                        for old_hook in hooks_to_remove:
                            if old_hook in cmd:
                                should_remove = True
                                hooks_migrated += 1
                                break
                        if not should_remove:
                            filtered_configs.append(config)
                            hooks_preserved += 1
                else:
                    filtered_configs.append(config)
                    hooks_preserved += 1
            merged_hooks[lifecycle] = filtered_configs

        # Add new hooks from template
        for lifecycle, hooks in new.items():
            if lifecycle not in merged_hooks:
                # New lifecycle event - add all hooks
                merged_hooks[lifecycle] = hooks.copy()
                hooks_added += len(hooks)
            else:
                # Existing lifecycle event - merge without duplicates
                existing_list = merged_hooks[lifecycle]
                for hook in hooks:
                    if hook not in existing_list:
                        existing_list.append(hook)
                        hooks_added += 1

        return merged_hooks, hooks_added, hooks_preserved, hooks_migrated

    def _atomic_write(self, path: Path, content: Dict) -> None:
        """Write JSON file atomically with secure permissions.

        This uses tempfile + rename for atomic writes:
        1. Create temp file in same directory
        2. Write JSON to temp file
        3. Set secure permissions (0o600)
        4. Atomic rename to target path

        Args:
            path: Target path for JSON file
            content: Dictionary to write as JSON

        Raises:
            OSError: If write fails
        """
        # Ensure parent directory exists
        path.parent.mkdir(parents=True, exist_ok=True)

        # Create temp file in same directory (for atomic rename)
        fd = None
        temp_path = None
        try:
            fd, temp_path = tempfile.mkstemp(
                dir=str(path.parent),
                prefix=".settings-",
                suffix=".json.tmp",
            )

            # Write JSON to temp file
            json_content = json.dumps(content, indent=2, sort_keys=True)
            os.write(fd, json_content.encode("utf-8"))
            os.close(fd)
            fd = None

            # Set secure permissions (user-only read/write)
            os.chmod(temp_path, 0o600)

            # Atomic rename
            os.rename(temp_path, path)

        except OSError as e:
            # Clean up temp file on error
            if fd is not None:
                try:
                    os.close(fd)
                except OSError:
                    pass

            if temp_path:
                try:
                    os.unlink(temp_path)
                except OSError:
                    pass

            # Re-raise with context
            raise OSError(f"Failed to write settings atomically: {e}") from e


def log_audit(event: str, context: Dict[str, Any]) -> None:
    """Alias for audit_log (backward compatibility with test mocks).

    Args:
        event: Event description
        context: Event context
    """
    audit_log("settings_merge", event, context)
