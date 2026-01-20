#!/usr/bin/env python3
"""
Sync Dispatcher - Main dispatcher class and helper methods

This module contains the SyncDispatcher class which coordinates sync operations.
Mode-specific dispatch functions are delegated to the modes module.

Classes:
- SyncDispatcher: Main dispatcher class with backup/rollback support

Design Patterns:
    See library-design-patterns skill for standardized design patterns.
"""

import json
import os
import tempfile
from pathlib import Path
from shutil import copy2, copytree
from typing import Optional

# Import dependencies
try:
    from plugins.autonomous_dev.lib.security_utils import validate_path, audit_log
    from plugins.autonomous_dev.lib.sync_mode_detector import SyncMode
    from plugins.autonomous_dev.lib.version_detector import detect_version_mismatch, VersionComparison
    from plugins.autonomous_dev.lib.orphan_file_cleaner import cleanup_orphans as cleanup_orphan_files, CleanupResult
    from plugins.autonomous_dev.lib.file_discovery import FileDiscovery
    from plugins.autonomous_dev.lib.settings_merger import SettingsMerger, MergeResult
    from plugins.autonomous_dev.lib.sync_validator import SyncValidator, SyncValidationResult
    from plugins.autonomous_dev.lib.protected_file_detector import ProtectedFileDetector
except ImportError:
    # Fallback for installed environment (.claude/lib/)
    from security_utils import validate_path, audit_log  # type: ignore
    from sync_mode_detector import SyncMode  # type: ignore
    from version_detector import detect_version_mismatch, VersionComparison  # type: ignore
    from orphan_file_cleaner import cleanup_orphans as cleanup_orphan_files, CleanupResult  # type: ignore
    from file_discovery import FileDiscovery  # type: ignore
    from settings_merger import SettingsMerger, MergeResult  # type: ignore
    try:
        from sync_validator import SyncValidator, SyncValidationResult  # type: ignore
    except ImportError:
        # Graceful degradation if sync_validator not available
        SyncValidator = None  # type: ignore
        SyncValidationResult = None  # type: ignore
    try:
        from protected_file_detector import ProtectedFileDetector  # type: ignore
    except ImportError:
        # Graceful degradation if protected_file_detector not available
        ProtectedFileDetector = None  # type: ignore

# Import from package modules
from .models import SyncResult, SyncDispatcherError


class SyncDispatcher:
    """Dispatcher for sync operations with backup and rollback support.

    Attributes:
        project_path: Validated project root path
        _backup_dir: Temporary directory for backup files
    """

    def __init__(self, project_path: Optional[str] = None, project_root: Optional[str] = None):
        """Initialize dispatcher with project path.

        Args:
            project_path: Path to project root directory (legacy parameter)
            project_root: Path to project root directory (preferred parameter)

        Raises:
            ValueError: If path fails security validation
            SyncDispatcherError: If project path is invalid

        Note:
            Either project_path or project_root must be provided.
            project_root takes precedence if both are provided.
        """
        # Accept both project_path and project_root for backwards compatibility
        path = project_root if project_root is not None else project_path
        if path is None:
            raise SyncDispatcherError(
                "Either project_path or project_root must be provided"
            )

        # Validate and resolve path
        try:
            validated_path = validate_path(path, "sync dispatcher")
            self.project_path = Path(validated_path).resolve()
        except ValueError as e:
            audit_log(
                "sync_dispatch",
                "failure",
                {
                    "operation": "init",
                    "project_path": path,
                    "error": str(e),
                },
            )
            raise

        # Verify path exists and is a directory
        if not self.project_path.exists():
            raise SyncDispatcherError(
                f"Project path does not exist: {self.project_path}\n"
                f"Expected: Valid directory path\n"
                f"See: docs/SYNC-COMMAND.md for usage"
            )

        if not self.project_path.is_dir():
            raise SyncDispatcherError(
                f"Project path is not a directory: {self.project_path}\n"
                f"Expected: Directory path, got file\n"
                f"See: docs/SYNC-COMMAND.md for usage"
            )

        self._backup_dir: Optional[Path] = None

    def sync(
        self,
        mode: SyncMode,
        force: bool = False,
        dry_run: bool = False,
        local_only: bool = False,
        create_backup: bool = True
    ) -> SyncResult:
        """Unified sync interface with support for all modes including uninstall.

        Args:
            mode: Sync mode to execute
            force: Force execution (required for UNINSTALL mode)
            dry_run: Preview only, don't make changes (UNINSTALL mode only)
            local_only: Skip global files (UNINSTALL mode only)
            create_backup: Whether to create backup before sync (default: True)

        Returns:
            SyncResult with operation outcome
        """
        # For UNINSTALL mode, delegate to uninstall_orchestrator
        if mode == SyncMode.UNINSTALL:
            try:
                from plugins.autonomous_dev.lib.uninstall_orchestrator import UninstallOrchestrator
            except ImportError:
                from uninstall_orchestrator import UninstallOrchestrator  # type: ignore

            orchestrator = UninstallOrchestrator(project_root=self.project_path)

            # If force=False and dry_run=False, treat as preview (dry-run)
            if not force and not dry_run:
                dry_run = True

            # Execute uninstall
            uninstall_result = orchestrator.execute(
                force=force,
                dry_run=dry_run,
                local_only=local_only
            )

            # Convert UninstallResult to SyncResult
            return SyncResult(
                success=uninstall_result.status == "success",
                mode=mode,
                message=f"Uninstall {uninstall_result.status}",
                files_removed=uninstall_result.files_removed,
                files_to_remove=uninstall_result.files_to_remove,
                total_size_bytes=uninstall_result.total_size_bytes,
                backup_path=uninstall_result.backup_path,
                dry_run=uninstall_result.dry_run,
                errors=uninstall_result.errors,
                error="; ".join(uninstall_result.errors) if uninstall_result.errors else None,
            )

        # For other modes, delegate to dispatch
        return self.dispatch(mode=mode, create_backup=create_backup)

    def dispatch(
        self, mode: SyncMode, create_backup: bool = True
    ) -> SyncResult:
        """Dispatch sync operation for specified mode.

        Args:
            mode: Sync mode to execute
            create_backup: Whether to create backup before sync (default: True)

        Returns:
            SyncResult with operation outcome

        Raises:
            ValueError: If mode is invalid
            SyncDispatcherError: If sync operation fails critically

        Security:
        - Creates backup before any modifications
        - Validates all paths before operations
        - Rolls back on failure (if backup enabled)
        - Logs all operations to audit log
        """
        # Import mode dispatch functions
        from . import modes

        # Validate mode
        if not isinstance(mode, SyncMode):
            raise ValueError(
                f"Invalid sync mode: {mode}\n"
                f"Expected: SyncMode enum value\n"
                f"Got: {type(mode).__name__}"
            )

        # Create backup if requested
        if create_backup:
            try:
                self._create_backup()
            except Exception as e:
                audit_log(
                    "sync_backup",
                    "failure",
                    {
                        "operation": "create_backup",
                        "project_path": str(self.project_path),
                        "error": str(e),
                    },
                )
                # Continue without backup (not critical)

        # Dispatch to appropriate handler
        try:
            if mode == SyncMode.GITHUB:
                result = modes.dispatch_github(self)
            elif mode == SyncMode.ENVIRONMENT:
                result = modes.dispatch_environment(self)
            elif mode == SyncMode.MARKETPLACE:
                result = modes.dispatch_marketplace(self)
            elif mode == SyncMode.PLUGIN_DEV:
                result = modes.dispatch_plugin_dev(self)
            elif mode == SyncMode.ALL:
                result = modes.dispatch_all(self)
            else:
                raise ValueError(f"Unknown sync mode: {mode}")

            # Log success
            audit_log(
                "sync_dispatch",
                "success",
                {
                    "operation": "dispatch",
                    "mode": mode.value,
                    "project_path": str(self.project_path),
                    "success": result.success,
                    "user": os.getenv("USER", "unknown"),
                },
            )

            # Post-sync validation (always runs, never blocks sync)
            if result.success and SyncValidator is not None:
                try:
                    result = self._post_sync_validation(result)
                except Exception as validation_error:
                    # Validation errors should never fail the sync
                    audit_log(
                        "sync_validation",
                        "error",
                        {
                            "operation": "post_sync_validation",
                            "error": str(validation_error),
                            "project_path": str(self.project_path),
                        },
                    )

            return result

        except Exception as e:
            # Rollback on failure
            if create_backup and self._backup_dir:
                try:
                    self._rollback()
                except Exception as rollback_error:
                    audit_log(
                        "sync_rollback",
                        "failure",
                        {
                            "operation": "rollback",
                            "project_path": str(self.project_path),
                            "original_error": str(e),
                            "rollback_error": str(rollback_error),
                        },
                    )

            # Log failure
            audit_log(
                "sync_dispatch",
                "failure",
                {
                    "operation": "dispatch",
                    "mode": mode.value,
                    "project_path": str(self.project_path),
                    "error": str(e),
                },
            )

            # Return failure result instead of raising
            return SyncResult(
                success=False,
                mode=mode,
                message=f"Sync failed: {str(e)}",
                error=str(e),
            )

    def _sync_directory(
        self,
        src: Path,
        dst: Path,
        pattern: str = "*",
        description: str = "files",
        delete_orphans: bool = False
    ) -> int:
        """Sync directory with per-file operations and optional orphan deletion.

        Replaces shutil.copytree() which silently fails to copy new files
        when destination directory already exists (dirs_exist_ok=True bug).

        This method uses FileDiscovery + per-file shutil.copy2() to ensure
        all files are copied, even when destination directory exists.

        When delete_orphans=True, performs TRUE SYNC by deleting files in
        destination that don't exist in source (rsync --delete behavior).

        Args:
            src: Source directory path
            dst: Destination directory path
            pattern: File pattern to match (e.g., "*.md", "*.py")
            description: Human-readable description for logging
            delete_orphans: If True, delete files in dst not in src (default: False)

        Returns:
            Number of files successfully copied

        Raises:
            ValueError: If src doesn't exist or path validation fails

        Example:
            >>> files_copied = self._sync_directory(
            ...     src=plugin_dir / "commands",
            ...     dst=claude_dir / "commands",
            ...     pattern="*.md",
            ...     description="command files",
            ...     delete_orphans=True  # True sync - mirror source
            ... )
        """
        # Validate source exists
        if not src.exists():
            audit_log(
                "sync_directory",
                "source_not_found",
                {
                    "src": str(src),
                    "dst": str(dst),
                    "pattern": pattern,
                }
            )
            return 0

        # Create destination directory if it doesn't exist
        dst.mkdir(parents=True, exist_ok=True)

        # Discover files matching pattern
        discovery = FileDiscovery(src)
        all_files = discovery.discover_all_files()

        # Filter by pattern using Path.match()
        import fnmatch
        matching_files = [
            f for f in all_files
            if fnmatch.fnmatch(f.name, pattern) or pattern == "*"
        ]

        # Copy files individually
        files_copied = 0
        errors = []

        for file_path in matching_files:
            try:
                # Get relative path to preserve directory structure
                relative = file_path.relative_to(src)
                dest_path = dst / relative

                # Create parent directories
                dest_path.parent.mkdir(parents=True, exist_ok=True)

                # Security: Validate file path (prevents CWE-22)
                validate_path(file_path, purpose="sync source file")

                # Copy file without following symlinks (prevents CWE-59)
                copy2(file_path, dest_path, follow_symlinks=False)

                files_copied += 1

            except Exception as e:
                error_msg = f"Error copying {file_path}: {e}"
                errors.append(error_msg)
                audit_log(
                    "sync_directory",
                    "file_copy_error",
                    {
                        "file": str(file_path),
                        "error": str(e),
                    }
                )
                # Continue on error (don't fail entire sync)
                continue

        # Delete orphaned files (TRUE SYNC behavior)
        orphans_deleted = 0
        if delete_orphans and dst.exists():
            # Initialize protected file detector (for .claude/local/ protection)
            protected_detector = ProtectedFileDetector() if ProtectedFileDetector else None

            # Get source file names (relative to src)
            source_names = {f.name for f in matching_files}

            # Find files in destination that don't exist in source
            import fnmatch as fn
            for dst_file in dst.iterdir():
                if dst_file.is_file() and fn.fnmatch(dst_file.name, pattern):
                    if dst_file.name not in source_names:
                        # Check if file is protected (e.g., .claude/local/)
                        if protected_detector:
                            try:
                                relative_path = dst_file.relative_to(self.project_path)
                                relative_str = str(relative_path).replace("\\", "/")
                                if protected_detector.matches_pattern(relative_str):
                                    # Skip protected files
                                    audit_log(
                                        "sync_directory",
                                        "orphan_protected",
                                        {
                                            "file": str(dst_file),
                                            "reason": "protected pattern",
                                        }
                                    )
                                    continue
                            except ValueError:
                                # File is outside project root - skip protection check
                                pass

                        try:
                            dst_file.unlink()
                            orphans_deleted += 1
                            audit_log(
                                "sync_directory",
                                "orphan_deleted",
                                {
                                    "file": str(dst_file),
                                    "reason": "not in source",
                                }
                            )
                        except Exception as e:
                            audit_log(
                                "sync_directory",
                                "orphan_delete_error",
                                {
                                    "file": str(dst_file),
                                    "error": str(e),
                                }
                            )

            # Delete orphaned subdirectories (TRUE SYNC for directories)
            # Get source subdirectory names
            source_subdirs = {d.name for d in src.iterdir() if d.is_dir()}

            # Find subdirectories in destination that don't exist in source
            for dst_subdir in dst.iterdir():
                if dst_subdir.is_dir() and dst_subdir.name not in source_subdirs:
                    # Skip special directories
                    if dst_subdir.name in {"__pycache__", ".git", "node_modules"}:
                        continue

                    # Check if directory is protected (e.g., .claude/local/)
                    if protected_detector:
                        try:
                            relative_path = dst_subdir.relative_to(self.project_path)
                            relative_str = str(relative_path).replace("\\", "/")
                            if protected_detector.matches_pattern(relative_str):
                                # Skip protected directories
                                audit_log(
                                    "sync_directory",
                                    "orphan_dir_protected",
                                    {
                                        "directory": str(dst_subdir),
                                        "reason": "protected pattern",
                                    }
                                )
                                continue
                        except ValueError:
                            # Directory is outside project root - skip protection check
                            pass

                    try:
                        # Safer deletion: remove files first, then directory
                        for f in dst_subdir.rglob("*"):
                            if f.is_file():
                                f.unlink()
                        # Remove empty directories bottom-up
                        for d in sorted(dst_subdir.rglob("*"), reverse=True):
                            if d.is_dir():
                                d.rmdir()
                        # Finally remove the top directory
                        dst_subdir.rmdir()
                        orphans_deleted += 1
                        audit_log(
                            "sync_directory",
                            "orphan_dir_deleted",
                            {
                                "directory": str(dst_subdir),
                                "reason": "not in source",
                            }
                        )
                    except Exception as e:
                        audit_log(
                            "sync_directory",
                            "orphan_dir_delete_error",
                            {
                                "directory": str(dst_subdir),
                                "error": str(e),
                            }
                        )

        # Audit log summary
        audit_log(
            "sync_directory",
            "completed",
            {
                "src": str(src),
                "dst": str(dst),
                "pattern": pattern,
                "files_copied": files_copied,
                "orphans_deleted": orphans_deleted,
                "errors": len(errors),
            }
        )

        return files_copied

    def _post_sync_validation(self, result: SyncResult) -> SyncResult:
        """Run post-sync validation with auto-fix and reporting.

        This method runs after a successful sync to:
        1. Validate settings files (JSON syntax, hook paths)
        2. Check hook integrity (syntax, imports, permissions)
        3. Run semantic validation (GenAI-powered pattern checks)
        4. Perform health check (component counts)

        Auto-fixes are applied silently. Manual fix guidance is printed.

        Args:
            result: The successful sync result to enhance with validation

        Returns:
            SyncResult with validation field populated

        Note:
            This method never fails - validation errors are captured
            in the result but don't affect sync success.
        """
        if SyncValidator is None:
            # Graceful degradation - no validation available
            return result

        try:
            validator = SyncValidator(self.project_path)
            validation_result = validator.validate_all()

            # Apply auto-fixes silently
            if validation_result.has_fixable_issues:
                fixes_applied = validator.apply_auto_fixes(validation_result)
                audit_log(
                    "sync_validation",
                    "auto_fix",
                    {
                        "fixes_applied": fixes_applied,
                        "project_path": str(self.project_path),
                    },
                )

            # Print validation report
            report = validator.generate_fix_report(validation_result)
            print(report)

            # Update result with validation
            result.validation = validation_result

            # Log validation outcome
            audit_log(
                "sync_validation",
                "complete",
                {
                    "passed": validation_result.overall_passed,
                    "errors": validation_result.total_errors,
                    "warnings": validation_result.total_warnings,
                    "auto_fixed": validation_result.total_auto_fixed,
                    "manual_fixes": validation_result.total_manual_fixes,
                    "project_path": str(self.project_path),
                },
            )

        except Exception as e:
            # Validation should never fail the sync
            audit_log(
                "sync_validation",
                "error",
                {
                    "error": str(e),
                    "project_path": str(self.project_path),
                },
            )
            print(f"\nValidation skipped due to error: {e}")

        return result

    def sync_marketplace(
        self,
        marketplace_plugins_file: Path,
        cleanup_orphans: bool = False,
        dry_run: bool = False,
    ) -> SyncResult:
        """Execute marketplace sync with version detection and orphan cleanup.

        This enhanced marketplace sync performs:
        1. Version detection (project vs marketplace)
        2. File copy (commands, hooks, agents)
        3. Orphan detection (always)
        4. Orphan cleanup (conditional, based on cleanup_orphans)

        All enhancements are non-blocking. Core sync succeeds even if
        version detection or orphan cleanup fails.

        Args:
            marketplace_plugins_file: Path to installed_plugins.json
            cleanup_orphans: Whether to cleanup orphaned files (default: False)
            dry_run: Whether to dry-run orphan cleanup (default: False)

        Returns:
            SyncResult with version_comparison and orphan_cleanup attributes

        Example:
            >>> dispatcher = SyncDispatcher("/path/to/project")
            >>> result = dispatcher.sync_marketplace(
            ...     marketplace_plugins_file=Path("~/.claude/plugins/installed_plugins.json"),
            ...     cleanup_orphans=True,
            ...     dry_run=False
            ... )
            >>> print(result.summary)
        """
        version_comparison = None
        orphan_cleanup_result = None
        files_updated = 0

        # Step 1: Version detection (non-blocking)
        try:
            version_comparison = detect_version_mismatch(
                project_root=str(self.project_path),
                marketplace_plugins_file=str(marketplace_plugins_file),
            )
            audit_log(
                "marketplace_sync",
                "version_detected",
                {
                    "project_path": str(self.project_path),
                    "project_version": version_comparison.project_version,
                    "marketplace_version": version_comparison.marketplace_version,
                    "status": version_comparison.status,
                },
            )
        except Exception as e:
            # Log error but continue sync
            audit_log(
                "marketplace_sync",
                "version_detection_failed",
                {
                    "project_path": str(self.project_path),
                    "error": str(e),
                },
            )
            # version_comparison stays None

        # Validate marketplace_plugins_file path (security)
        try:
            validated_marketplace_file = validate_path(
                str(marketplace_plugins_file),
                "marketplace plugins file"
            )
        except ValueError as e:
            # Security violations (path traversal, etc) - re-raise for security tests
            if "Path outside allowed directories" in str(e):
                raise
            # Other validation errors - return gracefully
            return SyncResult(
                success=False,
                mode=SyncMode.MARKETPLACE,
                message="Security validation failed",
                error=str(e),
                version_comparison=version_comparison,
                orphan_cleanup=orphan_cleanup_result,
            )

        # Check if file exists
        if not Path(validated_marketplace_file).exists():
            # File not found - return SyncResult (graceful error handling)
            return SyncResult(
                success=False,
                mode=SyncMode.MARKETPLACE,
                message="Marketplace plugins file not found",
                error=f"File not found: {validated_marketplace_file}",
                version_comparison=version_comparison,
                orphan_cleanup=orphan_cleanup_result,
            )

        marketplace_plugins_file = Path(validated_marketplace_file)

        # Step 2: Copy marketplace files (core sync - MUST succeed)
        try:

            # Read marketplace plugins
            try:
                plugins_data = json.loads(marketplace_plugins_file.read_text())
            except json.JSONDecodeError as e:
                return SyncResult(
                    success=False,
                    mode=SyncMode.MARKETPLACE,
                    message="Failed to parse marketplace plugins JSON",
                    error=f"JSON parse error: {e}",
                    version_comparison=version_comparison,
                    orphan_cleanup=orphan_cleanup_result,
                )

            # Find autonomous-dev plugin
            plugin_info = plugins_data.get("autonomous-dev")
            if not plugin_info:
                return SyncResult(
                    success=False,
                    mode=SyncMode.MARKETPLACE,
                    message="autonomous-dev not found in marketplace",
                    error="Plugin not installed in marketplace",
                    version_comparison=version_comparison,
                    orphan_cleanup=orphan_cleanup_result,
                )

            # Get plugin path and validate BEFORE existence check (CWE-59 protection)
            plugin_path = Path(plugin_info.get("path", ""))

            # Validate plugin path FIRST (prevents symlink TOCTOU attack)
            try:
                plugin_path = validate_path(str(plugin_path), "marketplace plugin directory")
            except ValueError as e:
                audit_log(
                    "security_violation",
                    "marketplace_path_invalid",
                    {
                        "path": str(plugin_path),
                        "error": str(e),
                    },
                )
                return SyncResult(
                    success=False,
                    mode=SyncMode.MARKETPLACE,
                    message="Security validation failed",
                    error=f"Invalid marketplace path: {e}",
                    version_comparison=version_comparison,
                    orphan_cleanup=orphan_cleanup_result,
                )

            # Now safe to check existence (after validation)
            if not plugin_path.exists():
                return SyncResult(
                    success=False,
                    mode=SyncMode.MARKETPLACE,
                    message="Marketplace plugin directory not found",
                    error=f"Directory not found: {plugin_path}",
                    version_comparison=version_comparison,
                    orphan_cleanup=orphan_cleanup_result,
                )

            # Ensure target .claude directory exists
            claude_dir = self.project_path / ".claude"
            claude_dir.mkdir(exist_ok=True)

            # Ensure plugins directory exists (for plugin.json)
            plugins_dir = claude_dir / "plugins" / "autonomous-dev"
            plugins_dir.mkdir(parents=True, exist_ok=True)

            # Copy plugin.json (needed for orphan detection)
            plugin_json_src = Path(plugin_path) / "plugin.json"
            plugin_json_dst = plugins_dir / "plugin.json"
            if plugin_json_src.exists():
                copy2(plugin_json_src, plugin_json_dst)
                files_updated += 1

            # Copy files (same logic as _dispatch_marketplace, using _sync_directory to fix Issue #97)
            # Copy commands
            commands_src = Path(plugin_path) / "commands"
            commands_dst = claude_dir / "commands"
            if commands_src.exists():
                files_updated += self._sync_directory(
                    commands_src, commands_dst, pattern="*.md", description="command files"
                )

            # Copy hooks
            hooks_src = Path(plugin_path) / "hooks"
            hooks_dst = claude_dir / "hooks"
            if hooks_src.exists():
                files_updated += self._sync_directory(
                    hooks_src, hooks_dst, pattern="*.py", description="hook files"
                )

            # Copy agents
            agents_src = Path(plugin_path) / "agents"
            agents_dst = claude_dir / "agents"
            if agents_src.exists():
                files_updated += self._sync_directory(
                    agents_src, agents_dst, pattern="*.md", description="agent files"
                )

            # Step 2.5: Merge settings.local.json (non-blocking enhancement)
            settings_merge_result = None
            try:
                template_path = Path(plugin_path) / "templates" / "settings.local.json"
                user_path = claude_dir / "settings.local.json"

                if template_path.exists():
                    merger = SettingsMerger(project_root=str(self.project_path))
                    settings_merge_result = merger.merge_settings(
                        template_path=template_path,
                        user_path=user_path,
                        write_result=True
                    )
                    audit_log(
                        "marketplace_sync",
                        "settings_merged",
                        {
                            "project_path": str(self.project_path),
                            "template_path": str(template_path),
                            "user_path": str(user_path),
                            "success": settings_merge_result.success,
                            "hooks_added": settings_merge_result.hooks_added,
                            "hooks_preserved": settings_merge_result.hooks_preserved,
                        },
                    )
                else:
                    audit_log(
                        "marketplace_sync",
                        "settings_template_missing",
                        {
                            "project_path": str(self.project_path),
                            "template_path": str(template_path),
                        },
                    )
            except Exception as e:
                # Log error but continue (non-blocking)
                audit_log(
                    "marketplace_sync",
                    "settings_merge_failed",
                    {
                        "project_path": str(self.project_path),
                        "error": str(e),
                    },
                )
                # settings_merge_result stays None - sync continues

            # Step 2.6: Migrate hooks from array format to object format (Issue #135)
            # This runs AFTER settings merge to catch any new hooks in array format
            try:
                from plugins.autonomous_dev.lib.hook_activator import migrate_hooks_to_object_format

                settings_path = Path.home() / ".claude" / "settings.json"
                if settings_path.exists():
                    migration_result = migrate_hooks_to_object_format(settings_path)

                    if migration_result['migrated']:
                        # Migration performed - log success
                        audit_log(
                            "marketplace_sync",
                            "hooks_migrated",
                            {
                                "project_path": str(self.project_path),
                                "settings_path": str(settings_path),
                                "backup_path": str(migration_result['backup_path']),
                                "format": migration_result['format'],
                            },
                        )
                        # Optionally notify user (this will be visible in sync result)
                        # Note: We don't print here since sync_dispatcher returns a result object
                    elif migration_result['error']:
                        # Migration failed - log but don't block sync
                        audit_log(
                            "marketplace_sync",
                            "hooks_migration_failed",
                            {
                                "project_path": str(self.project_path),
                                "settings_path": str(settings_path),
                                "error": migration_result['error'],
                            },
                        )
                    # else: No migration needed (already object format or missing)

            except Exception as e:
                # Migration failed - log but don't block sync (non-blocking enhancement)
                audit_log(
                    "marketplace_sync",
                    "hooks_migration_exception",
                    {
                        "project_path": str(self.project_path),
                        "error": str(e),
                    },
                )

        except Exception as e:
            # Core sync failed - return failure
            return SyncResult(
                success=False,
                mode=SyncMode.MARKETPLACE,
                message="Marketplace file copy failed",
                error=str(e),
                version_comparison=version_comparison,
                orphan_cleanup=orphan_cleanup_result,
            )

        # Step 3 & 4: Orphan detection and cleanup (non-blocking, only if cleanup enabled)
        if cleanup_orphans:
            try:
                # Use cleanup_orphan_files function which handles both detection and cleanup
                orphan_cleanup_result = cleanup_orphan_files(
                    project_root=str(self.project_path),
                    dry_run=dry_run,
                    confirm=False,  # Auto mode
                )
                audit_log(
                    "marketplace_sync",
                    "orphans_processed",
                    {
                        "project_path": str(self.project_path),
                        "orphans_detected": orphan_cleanup_result.orphans_detected,
                        "orphans_deleted": orphan_cleanup_result.orphans_deleted,
                        "dry_run": dry_run,
                    },
                )
            except Exception as e:
                # Log error but continue
                audit_log(
                    "marketplace_sync",
                    "orphan_processing_failed",
                    {
                        "project_path": str(self.project_path),
                        "error": str(e),
                    },
                )
                # orphan_cleanup_result stays None

        # Step 5: Build enriched message
        message_parts = [f"Marketplace sync completed: {files_updated} files updated"]

        if version_comparison and version_comparison.project_version and version_comparison.marketplace_version:
            if version_comparison.status == VersionComparison.UPGRADE_AVAILABLE:
                message_parts.append(
                    f"Upgraded from {version_comparison.project_version} to {version_comparison.marketplace_version}"
                )
            elif version_comparison.status == VersionComparison.DOWNGRADE_RISK:
                message_parts.append(
                    f"WARNING: Downgrade from {version_comparison.project_version} to {version_comparison.marketplace_version}"
                )
            elif version_comparison.status == VersionComparison.UP_TO_DATE:
                message_parts.append(f"Version {version_comparison.project_version} (up to date)")

        if orphan_cleanup_result:
            if orphan_cleanup_result.dry_run and orphan_cleanup_result.orphans_detected > 0:
                message_parts.append(
                    f"{orphan_cleanup_result.orphans_detected} orphaned files detected (dry-run)"
                )
            elif orphan_cleanup_result.orphans_deleted > 0:
                message_parts.append(f"{orphan_cleanup_result.orphans_deleted} orphaned files cleaned")
            elif orphan_cleanup_result.orphans_detected == 0:
                message_parts.append("No orphaned files")

        message = " | ".join(message_parts)

        # Return success with enriched data
        return SyncResult(
            success=True,
            mode=SyncMode.MARKETPLACE,
            message=message,
            details={
                "files_updated": files_updated,
                "source": str(plugin_path) if 'plugin_path' in locals() else "unknown",
            },
            version_comparison=version_comparison,
            orphan_cleanup=orphan_cleanup_result,
            settings_merged=settings_merge_result,
        )

    def _create_backup(self) -> None:
        """Create backup of .claude directory before sync.

        Raises:
            Exception: If backup creation fails
        """
        claude_dir = self.project_path / ".claude"
        if not claude_dir.exists():
            return  # Nothing to backup

        # Create temporary backup directory
        self._backup_dir = Path(
            tempfile.mkdtemp(prefix="claude_sync_backup_")
        )

        # Copy .claude directory to backup
        backup_claude = self._backup_dir / ".claude"
        copytree(claude_dir, backup_claude)

        audit_log(
            "sync_backup",
            "success",
            {
                "operation": "create_backup",
                "project_path": str(self.project_path),
                "backup_path": str(self._backup_dir),
            },
        )

    def _rollback(self) -> None:
        """Rollback changes by restoring from backup.

        Raises:
            Exception: If rollback fails
        """
        if not self._backup_dir or not self._backup_dir.exists():
            raise SyncDispatcherError("No backup available for rollback")

        claude_dir = self.project_path / ".claude"
        backup_claude = self._backup_dir / ".claude"

        # Remove current .claude directory
        if claude_dir.exists():
            from shutil import rmtree
            rmtree(claude_dir)

        # Restore from backup
        copytree(backup_claude, claude_dir)

        audit_log(
            "sync_rollback",
            "success",
            {
                "operation": "rollback",
                "project_path": str(self.project_path),
                "backup_path": str(self._backup_dir),
            },
        )


# Mock class for testing
class AgentInvoker:
    """Mock agent invoker for testing."""

    def __init__(self, project_path: str):
        self.project_path = project_path

    def invoke(self, agent_name: str, context: dict) -> dict:
        """Mock invoke method."""
        return {"status": "success", "files_updated": 0, "conflicts": 0}
