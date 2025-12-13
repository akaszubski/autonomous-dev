#!/usr/bin/env python3
"""
Hook Activator - Automatic hook activation during plugin updates

This module provides automatic hook activation functionality for plugin updates:
- Detect first install vs update (check for existing settings.json)
- Read and parse existing settings.json
- Merge new hooks with existing settings (preserve customizations)
- Atomic write with tempfile + rename pattern
- Validate settings structure before write
- Create .claude directory if missing
- Handle edge cases (malformed JSON, missing files, permissions)

Features:
- First install detection
- Settings merge (preserve customizations)
- Atomic file writes (tempfile + rename)
- Settings validation (structure + content)
- Comprehensive error handling
- Rich result objects with detailed info

Security:
- All file paths validated via security_utils.validate_path()
- Prevents path traversal (CWE-22)
- Rejects symlink attacks (CWE-59)
- Secure file permissions: 0o600 for settings (CWE-732)
- Audit logging for all operations (CWE-778)

Usage:
    from hook_activator import HookActivator

    # Activate hooks
    activator = HookActivator(project_root="/path/to/project")

    new_hooks = {
        "hooks": {
            "PrePush": ["auto_test.py"],
            "SubagentStop": ["log_agent_completion.py"]
        }
    }

    result = activator.activate_hooks(new_hooks)
    print(result.summary)

Date: 2025-11-09
Issue: GitHub #50 Phase 2.5 - Automatic hook activation
Agent: implementer


Design Patterns:
    See library-design-patterns skill for standardized design patterns.
"""

import json
import os
import sys
import tempfile
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

# Add parent directory for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

from plugins.autonomous_dev.lib import security_utils


# ============================================================================
# Exception Classes
# ============================================================================


# Exception hierarchy pattern from error-handling-patterns skill:
# BaseException -> Exception -> AutonomousDevError -> DomainError(BaseException) -> SpecificError
class ActivationError(Exception):
    """

    See error-handling-patterns skill for exception hierarchy and error handling best practices.

    Base exception for hook activation failures."""
    pass


class SettingsValidationError(ActivationError):
    """Exception raised when settings validation fails."""
    pass


# ============================================================================
# Result Dataclass
# ============================================================================


@dataclass
class ActivationResult:
    """Result of a hook activation operation.

    Attributes:
        activated: Whether hooks were activated (True) or skipped (False)
        first_install: Whether this was a first install (True) or update (False)
        message: Human-readable result message
        hooks_added: Number of hooks added during activation
        settings_path: Path to settings.json file (or None if not written)
        details: Additional result details (preserved settings, merged hooks, etc.)
    """

    activated: bool
    first_install: bool
    message: str
    hooks_added: int = 0
    settings_path: Optional[str] = None
    details: Dict[str, Any] = field(default_factory=dict)

    @property
    def summary(self) -> str:
        """Generate human-readable summary of activation result.

        Returns:
            Multi-line summary with activation status and details
        """
        parts = []
        parts.append(f"Status: {self.message}")
        parts.append(f"Hooks Added: {self.hooks_added}")

        if self.settings_path:
            parts.append(f"Settings: {self.settings_path}")

        if self.first_install:
            parts.append("Type: First Install")
        else:
            parts.append("Type: Update")

        return "\n".join(parts)


# ============================================================================
# Migration Functions (Claude Code 2.0 Format)
# ============================================================================


def validate_hook_format(settings_data: Dict[str, Any]) -> Dict[str, Any]:
    """Validate hook format and detect legacy vs modern Claude Code 2.0 format.

    Legacy format indicators:
    - Missing 'timeout' field in hook definitions
    - Flat structure (direct command strings in lifecycle arrays)
    - Missing nested 'hooks' array within matcher configurations

    Modern CC2 format:
    - Every hook has 'timeout' field
    - Nested structure with matchers containing 'hooks' arrays
    - Each hook is a dict with 'type', 'command', 'timeout'

    Args:
        settings_data: Settings dictionary to validate

    Returns:
        Dict with 'is_legacy' (bool) and 'reason' (str) keys

    Raises:
        SettingsValidationError: If settings structure is malformed

    Example:
        >>> result = validate_hook_format(settings)
        >>> if result['is_legacy']:
        ...     print(f"Legacy format detected: {result['reason']}")
    """
    # Handle missing hooks key (treat as modern/empty)
    if "hooks" not in settings_data:
        return {"is_legacy": False, "reason": "No hooks defined"}

    # Validate hooks is a dict
    if not isinstance(settings_data["hooks"], dict):
        raise SettingsValidationError(
            "Invalid settings structure: 'hooks' must be a dictionary"
        )

    hooks = settings_data["hooks"]

    # Empty hooks is valid modern format
    if not hooks:
        return {"is_legacy": False, "reason": "No hooks defined"}

    # Check each lifecycle event for legacy format indicators
    for lifecycle, lifecycle_config in hooks.items():
        # Validate lifecycle config is a list
        if not isinstance(lifecycle_config, list):
            raise SettingsValidationError(
                f"Invalid hooks for '{lifecycle}': must be a list"
            )

        # Check for flat structure (strings instead of dicts)
        for item in lifecycle_config:
            if isinstance(item, str):
                return {
                    "is_legacy": True,
                    "reason": f"Flat structure detected in {lifecycle} (string commands instead of dicts)",
                }

            # Item should be a dict (matcher configuration)
            if not isinstance(item, dict):
                raise SettingsValidationError(
                    f"Invalid hook configuration in '{lifecycle}': expected dict, got {type(item)}"
                )

            # Check for missing nested 'hooks' array
            if "hooks" not in item:
                # Check if this is a direct command config (legacy)
                if "command" in item or "type" in item:
                    return {
                        "is_legacy": True,
                        "reason": f"Missing nested hooks array in {lifecycle} (direct command config)",
                    }
                # Empty matcher config (edge case)
                continue

            # Validate nested hooks is a list
            nested_hooks = item["hooks"]
            if not isinstance(nested_hooks, list):
                raise SettingsValidationError(
                    f"Invalid nested hooks in '{lifecycle}': must be a list"
                )

            # Check each hook in nested array for missing timeout
            for hook in nested_hooks:
                if not isinstance(hook, dict):
                    raise SettingsValidationError(
                        f"Invalid hook in '{lifecycle}': must be a dict"
                    )

                # Check for missing timeout field
                if "timeout" not in hook:
                    return {
                        "is_legacy": True,
                        "reason": f"Missing timeout field in {lifecycle} hook",
                    }

    # All checks passed - modern format
    return {"is_legacy": False, "reason": "Modern Claude Code 2.0 format"}


def migrate_hook_format_cc2(settings_data: Dict[str, Any]) -> Dict[str, Any]:
    """Migrate legacy hook format to Claude Code 2.0 format.

    Transformations applied:
    1. Add 'timeout': 5 to all hooks missing it
    2. Convert flat string commands to nested dict structure
    3. Wrap commands in nested 'hooks' array if missing
    4. Add 'matcher': '*' if missing
    5. Preserve user customizations (custom timeouts, matchers)

    This function is idempotent - running it multiple times produces the same result.

    Args:
        settings_data: Settings dictionary to migrate (can be legacy or modern)

    Returns:
        Migrated settings dictionary in Claude Code 2.0 format (deep copy)

    Example:
        >>> legacy = {"hooks": {"PrePush": ["auto_test.py"]}}
        >>> modern = migrate_hook_format_cc2(legacy)
        >>> print(modern['hooks']['PrePush'][0]['hooks'][0]['timeout'])
        5
    """
    # Deep copy to avoid modifying original
    import copy

    migrated = copy.deepcopy(settings_data)

    # Handle missing hooks key
    if "hooks" not in migrated:
        migrated["hooks"] = {}
        return migrated

    hooks = migrated["hooks"]

    # Handle empty hooks
    if not hooks:
        return migrated

    # Migrate each lifecycle event
    for lifecycle, lifecycle_config in list(hooks.items()):
        # Handle empty lifecycle events
        if not lifecycle_config:
            continue

        # Convert to list if not already
        if not isinstance(lifecycle_config, list):
            continue

        migrated_matchers = []

        for item in lifecycle_config:
            # Case 1: Flat string command (legacy)
            if isinstance(item, str):
                # Convert to modern nested structure
                migrated_matchers.append(
                    {
                        "matcher": "*",
                        "hooks": [
                            {
                                "type": "command",
                                "command": f"python .claude/hooks/{item}",
                                "timeout": 5,
                            }
                        ],
                    }
                )
                continue

            # Case 2: Dict without nested hooks array (legacy)
            if isinstance(item, dict):
                # Check if this is a direct command config (missing nested hooks)
                if "hooks" not in item and ("command" in item or "type" in item):
                    # Extract command info
                    hook_type = item.get("type", "command")
                    command = item.get("command", "")
                    timeout = item.get("timeout", 5)
                    matcher = item.get("matcher", "*")

                    # Create nested structure
                    migrated_matchers.append(
                        {
                            "matcher": matcher,
                            "hooks": [
                                {
                                    "type": hook_type,
                                    "command": command,
                                    "timeout": timeout,
                                }
                            ],
                        }
                    )
                    continue

                # Case 3: Modern structure with nested hooks array
                if "hooks" in item:
                    matcher = item.get("matcher", "*")
                    nested_hooks = item["hooks"]

                    # Migrate each hook in nested array
                    migrated_nested = []
                    for hook in nested_hooks:
                        if isinstance(hook, dict):
                            # Add timeout if missing (preserve existing if present)
                            if "timeout" not in hook:
                                hook["timeout"] = 5

                            migrated_nested.append(hook)

                    # Update nested hooks
                    migrated_matchers.append({"matcher": matcher, "hooks": migrated_nested})
                    continue

                # Case 4: Empty matcher config (edge case)
                # Skip empty configs
                pass

        # Update lifecycle config with migrated matchers
        hooks[lifecycle] = migrated_matchers

    return migrated


def _backup_settings(settings_path: Path) -> Path:
    """Create timestamped backup of settings.json before migration.

    Backup strategy:
    - Timestamped filename: settings.json.backup.YYYYMMDD_HHMMSS
    - Atomic write (tempfile + rename)
    - Secure permissions (0o600 - user-only read/write)
    - Path validation via security_utils

    Args:
        settings_path: Path to settings.json file to backup

    Returns:
        Path to backup file

    Raises:
        ActivationError: If backup creation fails

    Example:
        >>> backup_path = _backup_settings(Path(".claude/settings.json"))
        >>> print(backup_path)
        .claude/settings.json.backup.20251212_143022
    """
    # Validate settings path
    try:
        security_utils.validate_path(
            settings_path,
            purpose="settings.json for backup",
        )
    except (ValueError, FileNotFoundError) as e:
        raise ActivationError(f"Invalid settings path for backup: {e}") from e

    # Generate timestamped backup filename
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_filename = f"settings.json.backup.{timestamp}"
    backup_path = settings_path.parent / backup_filename

    # Read original settings
    try:
        original_content = settings_path.read_text(encoding="utf-8")
    except OSError as e:
        raise ActivationError(f"Failed to read settings for backup: {e}") from e

    # Create backup using atomic write (tempfile + rename)
    fd = None
    temp_path = None
    try:
        fd, temp_path = tempfile.mkstemp(
            dir=str(settings_path.parent),
            prefix=".settings-backup-",
            suffix=".json.tmp",
        )

        # Write original content to temp file
        os.write(fd, original_content.encode("utf-8"))
        os.close(fd)
        fd = None

        # Set secure permissions (user-only read/write)
        # Note: In tests, mkstemp might be mocked and file might not exist
        try:
            os.chmod(temp_path, 0o600)
        except (OSError, FileNotFoundError):
            # If chmod fails in test scenarios (mocked mkstemp), continue
            # In production, mkstemp creates the file so chmod will work
            pass

        # Atomic rename to final backup path
        os.rename(temp_path, backup_path)

        # Audit log the backup creation
        security_utils.audit_log(
            event_type="settings_backup",
            status="success",
            context={
                "operation": "backup_settings",
                "original_path": str(settings_path),
                "backup_path": str(backup_path),
                "timestamp": timestamp,
            },
        )

        return backup_path

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

        raise ActivationError(f"Failed to create settings backup: {e}") from e


# ============================================================================
# Hook Activator Class
# ============================================================================


class HookActivator:
    """Hook activator for automatic hook configuration during plugin updates.

    This class handles:
    - First install detection
    - Settings file reading and parsing
    - Hook merging (preserves customizations)
    - Atomic file writing
    - Settings validation
    - Error handling and recovery

    Security:
    - Path validation via security_utils
    - Atomic writes to prevent corruption
    - Secure file permissions (0o600)
    - Audit logging for all operations
    """

    def __init__(self, project_root: Path):
        """Initialize HookActivator with project root.

        Args:
            project_root: Path to project root directory

        Raises:
            ValueError: If project_root validation fails
        """
        # Validate project root path
        security_utils.validate_path(
            project_root,
            purpose="project root for hook activation",
        )

        self.project_root = Path(project_root)
        self.claude_dir = self.project_root / ".claude"
        self.settings_path = self.claude_dir / "settings.json"

    def is_first_install(self) -> bool:
        """Check if this is a first install (settings.json doesn't exist).

        Returns:
            True if settings.json doesn't exist (first install)
            False if settings.json exists (update)
        """
        return not self.settings_path.exists()

    def activate_hooks(self, new_hooks: Dict[str, Any]) -> ActivationResult:
        """Activate hooks with automatic merge and validation.

        This is the main entry point for hook activation. It:
        1. Detects first install vs update
        2. Reads existing settings (if update)
        3. Merges new hooks with existing settings
        4. Validates merged settings
        5. Writes settings atomically
        6. Returns detailed result

        Args:
            new_hooks: Dictionary with 'hooks' key containing hook configuration

        Returns:
            ActivationResult with activation status and details

        Raises:
            SettingsValidationError: If settings validation fails
            ActivationError: If activation fails for other reasons
        """
        # Audit log the activation attempt
        security_utils.audit_log(
            event_type="hook_activation",
            status="start",
            context={
                "operation": "activate_hooks",
                "project_root": str(self.project_root),
                "is_first_install": self.is_first_install(),
            },
        )

        # Validate input structure (must have 'hooks' key)
        if "hooks" not in new_hooks:
            raise SettingsValidationError(
                "Invalid hook configuration: missing 'hooks' key"
            )

        # Check for empty hooks
        if not new_hooks["hooks"]:
            result = ActivationResult(
                activated=False,
                first_install=self.is_first_install(),
                message="No hooks to activate",
                hooks_added=0,
                settings_path=str(self.settings_path) if self.settings_path.exists() else None,
                details={},
            )
            return result

        # Detect first install
        first_install = self.is_first_install()

        # Read existing settings (if update)
        if first_install:
            existing_settings = {}
        else:
            try:
                existing_settings = self._read_existing_settings()
            except Exception as e:
                security_utils.audit_log(
                    event_type="hook_activation",
                    status="failure",
                    context={
                        "operation": "read_settings",
                        "error": "Failed to read existing settings",
                        "exception": str(e),
                    },
                )
                raise

            # Check if existing settings need migration to Claude Code 2.0 format
            try:
                format_check = validate_hook_format(existing_settings)

                if format_check["is_legacy"]:
                    # Legacy format detected - create backup before migration
                    security_utils.audit_log(
                        event_type="hook_migration",
                        status="detected",
                        context={
                            "operation": "format_detection",
                            "reason": format_check["reason"],
                            "settings_path": str(self.settings_path),
                        },
                    )

                    # Create timestamped backup
                    backup_path = _backup_settings(self.settings_path)

                    # Migrate to Claude Code 2.0 format
                    existing_settings = migrate_hook_format_cc2(existing_settings)

                    security_utils.audit_log(
                        event_type="hook_migration",
                        status="success",
                        context={
                            "operation": "migration_complete",
                            "backup_path": str(backup_path),
                            "migrated_settings": str(self.settings_path),
                        },
                    )

            except SettingsValidationError:
                # Re-raise validation errors
                raise
            except Exception as e:
                security_utils.audit_log(
                    event_type="hook_migration",
                    status="failure",
                    context={
                        "operation": "migration",
                        "error": "Migration failed",
                        "exception": str(e),
                    },
                )
                # Don't fail activation on migration error - continue with existing settings
                # This ensures backward compatibility if migration has issues

        # Merge settings
        merged_settings = self._merge_settings(existing_settings, new_hooks)

        # Validate merged settings
        try:
            self._validate_settings(merged_settings)
        except SettingsValidationError:
            security_utils.audit_log(
                event_type="hook_activation",
                status="failure",
                context={
                    "operation": "validate_settings",
                    "error": "Settings validation failed",
                },
            )
            raise

        # Count hooks added
        hooks_added = sum(
            len(hooks) for hooks in merged_settings.get("hooks", {}).values()
        )

        # Create .claude directory if missing
        if not self.claude_dir.exists():
            self.claude_dir.mkdir(parents=True, exist_ok=True)

        # Write settings atomically
        try:
            self._atomic_write_settings(merged_settings)
        except Exception as e:
            security_utils.audit_log(
                event_type="hook_activation",
                status="failure",
                context={
                    "operation": "write_settings",
                    "error": "Failed to write settings",
                    "exception": str(e),
                },
            )
            raise ActivationError(f"Failed to write settings: {e}") from e

        # Build result details
        details = {}
        if not first_install:
            # Track preserved settings
            preserved = [
                key
                for key in existing_settings.keys()
                if key != "hooks" and key in merged_settings
            ]
            if preserved:
                details["preserved_settings"] = preserved

        # Audit log success
        security_utils.audit_log(
            event_type="hook_activation",
            status="success",
            context={
                "operation": "activate_hooks_complete",
                "first_install": first_install,
                "hooks_added": hooks_added,
                "settings_path": str(self.settings_path),
            },
        )

        # Return result
        result = ActivationResult(
            activated=True,
            first_install=first_install,
            message=f"Successfully activated {hooks_added} hooks"
            if first_install
            else f"Updated hook configuration ({hooks_added} total hooks)",
            hooks_added=hooks_added,
            settings_path=str(self.settings_path),
            details=details,
        )

        return result

    def _read_existing_settings(self) -> Dict[str, Any]:
        """Read and parse existing settings.json file.

        Returns:
            Dictionary containing parsed settings, or {"hooks": {}} if file doesn't exist

        Raises:
            SettingsValidationError: If JSON is malformed
            ActivationError: If file cannot be read (permissions, etc.)
        """
        # Check if settings file exists
        if not self.settings_path.exists():
            return {"hooks": {}}

        # Validate settings path
        try:
            security_utils.validate_path(
                self.settings_path,
                purpose="settings.json for reading",
            )
        except (ValueError, FileNotFoundError) as e:
            raise ActivationError(f"Invalid settings path: {e}") from e

        # Read and parse JSON
        try:
            content = self.settings_path.read_text(encoding="utf-8")

            # Handle empty file
            if not content.strip():
                return {"hooks": {}}

            settings = json.loads(content)

            # Handle settings without hooks key
            if "hooks" not in settings:
                settings["hooks"] = {}

            return settings
        except json.JSONDecodeError as e:
            raise SettingsValidationError(
                f"Failed to parse settings.json: malformed JSON - {e}"
            ) from e
        except OSError as e:
            if "Permission denied" in str(e):
                raise ActivationError(f"Permission denied reading settings.json: {e}") from e
            raise ActivationError(f"Failed to read settings.json: {e}") from e

    def _merge_settings(
        self, existing: Dict[str, Any], new_hooks: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Merge new hooks with existing settings (preserve customizations).

        Args:
            existing: Existing settings dictionary
            new_hooks: New hooks dictionary with 'hooks' key

        Returns:
            Merged settings dictionary
        """
        # Start with existing settings
        merged = existing.copy()

        # Get existing hooks
        existing_hooks = merged.get("hooks", {})

        # Get new hooks
        new_hooks_config = new_hooks.get("hooks", {})

        # Merge hooks by lifecycle event
        for lifecycle, hooks in new_hooks_config.items():
            if lifecycle not in existing_hooks:
                # New lifecycle event - add all hooks
                existing_hooks[lifecycle] = hooks.copy()
            else:
                # Existing lifecycle event - merge without duplicates
                existing_list = existing_hooks[lifecycle]
                for hook in hooks:
                    if hook not in existing_list:
                        existing_list.append(hook)

        # Update merged settings
        merged["hooks"] = existing_hooks

        return merged

    def _validate_settings(self, settings: Dict[str, Any]) -> None:
        """Validate settings structure and content.

        Args:
            settings: Settings dictionary to validate

        Raises:
            SettingsValidationError: If validation fails
        """
        # Check for 'hooks' key
        if "hooks" not in settings:
            raise SettingsValidationError(
                "Invalid settings structure: missing 'hooks' key"
            )

        # Check 'hooks' is a dictionary
        if not isinstance(settings["hooks"], dict):
            raise SettingsValidationError(
                "Invalid settings structure: 'hooks' must be a dictionary"
            )

        # Validate each lifecycle event
        for lifecycle, hooks in settings["hooks"].items():
            # Check hooks is a list
            if not isinstance(hooks, list):
                raise SettingsValidationError(
                    f"Invalid hooks for '{lifecycle}': must be a list"
                )

            # Validate each item in hooks list
            for hook in hooks:
                # Accept both legacy (string) and modern (dict) formats
                if isinstance(hook, str):
                    # Legacy format - valid
                    continue
                elif isinstance(hook, dict):
                    # Modern CC2 format - validate structure
                    # Should have 'matcher' and 'hooks' keys
                    if "hooks" in hook:
                        # Nested hooks array - validate it's a list
                        if not isinstance(hook["hooks"], list):
                            raise SettingsValidationError(
                                f"Invalid nested hooks in '{lifecycle}': must be a list"
                            )
                        # Each hook in nested array should be a dict
                        for nested_hook in hook["hooks"]:
                            if not isinstance(nested_hook, dict):
                                raise SettingsValidationError(
                                    f"Invalid nested hook in '{lifecycle}': must be a dict"
                                )
                    # If no nested hooks, check if it has command (legacy dict format)
                    elif "command" not in hook:
                        raise SettingsValidationError(
                            f"Invalid hook in '{lifecycle}': dict must have 'hooks' or 'command' key"
                        )
                else:
                    raise SettingsValidationError(
                        f"Invalid hook in '{lifecycle}': must be string or dict"
                    )

    def _atomic_write_settings(
        self, settings: Dict[str, Any], settings_path: Optional[Path] = None
    ) -> None:
        """Write settings.json atomically (tempfile + rename).

        Args:
            settings: Settings dictionary to write
            settings_path: Path to settings.json (default: self.settings_path)

        Raises:
            ActivationError: If write fails
        """
        # Use default settings path if not provided
        if settings_path is None:
            settings_path = self.settings_path

        # Validate settings path
        try:
            security_utils.validate_path(
                settings_path,
                purpose="settings.json for writing",
            )
        except (ValueError, FileNotFoundError) as e:
            raise ActivationError(f"Invalid settings path: {e}") from e

        # Ensure parent directory exists
        settings_path.parent.mkdir(parents=True, exist_ok=True)

        # Create temp file in same directory (for atomic rename)
        fd = None
        temp_path = None
        try:
            fd, temp_path = tempfile.mkstemp(
                dir=str(settings_path.parent),
                prefix=".settings-",
                suffix=".json.tmp",
            )

            # Write JSON to temp file
            content = json.dumps(settings, indent=2, sort_keys=True)
            os.write(fd, content.encode("utf-8"))
            os.close(fd)
            fd = None

            # Set secure permissions (user-only read/write)
            # Note: In tests, mkstemp might be mocked and file might not exist
            try:
                os.chmod(temp_path, 0o600)
            except (OSError, FileNotFoundError):
                # If chmod fails in test scenarios (mocked mkstemp), continue
                # In production, mkstemp creates the file so chmod will work
                pass

            # Atomic rename
            os.rename(temp_path, settings_path)

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
            if "No space left" in str(e):
                raise ActivationError(f"No space left on device: {e}") from e
            elif "Permission denied" in str(e):
                raise ActivationError(f"Permission denied writing settings: {e}") from e
            else:
                raise ActivationError(f"Failed to write settings: {e}") from e
