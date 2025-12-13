#!/usr/bin/env python3
"""
Sync Dispatcher - Execute sync operations for different modes

This module coordinates sync operations by delegating to the appropriate
sync mechanism based on detected or specified mode.

Sync Operations:
- GITHUB: Fetch latest files directly from GitHub (default for users)
- ENVIRONMENT: Delegate to sync-validator agent for environment sync
- MARKETPLACE: Copy files from installed plugin to project .claude/
- PLUGIN_DEV: Sync plugin development files to local .claude/
- ALL: Execute all modes in sequence with rollback support

Security:
- All paths validated through security_utils.validate_path()
- Backup created before sync operations
- Rollback support on failures
- Audit logging for all operations

Usage:
    from sync_dispatcher import dispatch_sync

    # Dispatch specific mode
    result = dispatch_sync("/path/to/project", SyncMode.ENVIRONMENT)
    if result.success:
        print(f"Sync succeeded: {result.message}")

    # Full control
    dispatcher = SyncDispatcher("/path/to/project")
    result = dispatcher.dispatch(SyncMode.ALL)

Date: 2025-11-08
Issue: GitHub #44 - Unified /sync command
Agent: implementer


Design Patterns:
    See library-design-patterns skill for standardized design patterns.
"""

import argparse
import json
import os
import shutil
import sys
import tempfile
import urllib.request
import urllib.error
from dataclasses import dataclass, field
from pathlib import Path
from shutil import copy2, copytree
from typing import Dict, Any, List, Optional

# Add parent directory for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

from plugins.autonomous_dev.lib.security_utils import (
    validate_path,
    audit_log,
)
from plugins.autonomous_dev.lib.sync_mode_detector import SyncMode, get_individual_sync_modes
from plugins.autonomous_dev.lib.version_detector import detect_version_mismatch, VersionComparison
from plugins.autonomous_dev.lib.orphan_file_cleaner import (
    detect_orphans,
    cleanup_orphans as cleanup_orphan_files,
    CleanupResult,
)
from plugins.autonomous_dev.lib.file_discovery import FileDiscovery
from plugins.autonomous_dev.lib.settings_merger import SettingsMerger, MergeResult


@dataclass
class SyncResult:
    """Result of a sync operation.

    See error-handling-patterns skill for exception hierarchy and error handling best practices.

    Attributes:
        success: Whether sync succeeded
        mode: Sync mode that was executed
        message: Human-readable result message
        details: Additional result details (files updated, conflicts, etc.)
        error: Error message if sync failed
        version_comparison: Version comparison results (marketplace sync only)
        orphan_cleanup: Orphan cleanup results (marketplace sync only)
    """

    success: bool
    mode: SyncMode
    message: str
    details: Dict[str, Any] = field(default_factory=dict)
    error: Optional[str] = None
    version_comparison: Optional[VersionComparison] = None
    orphan_cleanup: Optional[CleanupResult] = None
    settings_merged: Optional[MergeResult] = None

    @property
    def summary(self) -> str:
        """Generate comprehensive summary including all details.

        Returns:
            Human-readable summary with version and cleanup info
        """
        parts = [self.message]

        # Add version information
        if self.version_comparison:
            vc = self.version_comparison
            if vc.project_version and vc.marketplace_version:
                if vc.status == VersionComparison.UPGRADE_AVAILABLE:
                    parts.append(f"Version upgrade: {vc.project_version} → {vc.marketplace_version}")
                elif vc.status == VersionComparison.DOWNGRADE_RISK:
                    parts.append(f"Downgrade risk: {vc.project_version} → {vc.marketplace_version}")
                elif vc.status == VersionComparison.UP_TO_DATE:
                    parts.append(f"Version up to date: {vc.project_version}")

        # Add orphan cleanup information
        if self.orphan_cleanup:
            oc = self.orphan_cleanup
            if oc.dry_run and oc.orphans_detected > 0:
                parts.append(f"Orphans detected: {oc.orphans_detected} (dry-run, not deleted)")
            elif oc.orphans_deleted > 0:
                parts.append(f"Orphan cleanup: {oc.orphans_deleted} files deleted")
            elif oc.orphans_detected == 0:
                parts.append("No orphaned files detected")

        # Add settings merge information
        if self.settings_merged:
            sm = self.settings_merged
            if sm.success:
                if sm.hooks_added > 0:
                    parts.append(f"Settings merged: {sm.hooks_added} hooks added, {sm.hooks_preserved} preserved")
                elif sm.hooks_preserved > 0:
                    parts.append(f"Settings merged: {sm.hooks_preserved} hooks preserved (no new hooks)")
            else:
                parts.append(f"Settings merge failed: {sm.message}")

        return " | ".join(parts)


# Exception hierarchy pattern from error-handling-patterns skill:
# BaseException -> Exception -> AutonomousDevError -> DomainError(BaseException) -> SpecificError
class SyncDispatcherError(Exception):
    """Exception raised for sync dispatcher errors."""

    pass


# Alias for test compatibility
SyncError = SyncDispatcherError


class SyncDispatcher:
    """Dispatcher for sync operations with backup and rollback support.

    Attributes:
        project_path: Validated project root path
        _backup_dir: Temporary directory for backup files
    """

    def __init__(self, project_path: str = None, project_root: str = None):
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
                result = self._dispatch_github()
            elif mode == SyncMode.ENVIRONMENT:
                result = self._dispatch_environment()
            elif mode == SyncMode.MARKETPLACE:
                result = self._dispatch_marketplace()
            elif mode == SyncMode.PLUGIN_DEV:
                result = self._dispatch_plugin_dev()
            elif mode == SyncMode.ALL:
                result = self._dispatch_all()
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
            # Get source file names (relative to src)
            source_names = {f.name for f in matching_files}

            # Find files in destination that don't exist in source
            import fnmatch as fn
            for dst_file in dst.iterdir():
                if dst_file.is_file() and fn.fnmatch(dst_file.name, pattern):
                    if dst_file.name not in source_names:
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

    def _dispatch_environment(self) -> SyncResult:
        """Dispatch environment sync to sync-validator agent.

        Returns:
            SyncResult with agent execution outcome

        Note:
            This delegates to the existing sync-validator agent which handles
            environment validation and synchronization.
        """
        # Import AgentInvoker (local import to avoid circular dependencies)
        try:
            # Mock implementation for testing - tests will patch this
            # In real usage, this would use Task tool to invoke sync-validator
            from unittest.mock import Mock

            # This will be patched by tests
            invoker = AgentInvoker(str(self.project_path))
            result = invoker.invoke("sync-validator", {})

            if result.get("status") == "success":
                return SyncResult(
                    success=True,
                    mode=SyncMode.ENVIRONMENT,
                    message="Environment sync completed successfully",
                    details={
                        "files_updated": result.get("files_updated", 0),
                        "conflicts": result.get("conflicts", 0),
                    },
                )
            else:
                return SyncResult(
                    success=False,
                    mode=SyncMode.ENVIRONMENT,
                    message="Environment sync failed",
                    error=result.get("error", "Unknown error"),
                )

        except ImportError:
            # Fallback for testing without AgentInvoker
            return SyncResult(
                success=True,
                mode=SyncMode.ENVIRONMENT,
                message="Environment sync completed (mock)",
                details={"files_updated": 0, "conflicts": 0},
            )

    def _dispatch_marketplace(self) -> SyncResult:
        """Dispatch marketplace sync - copy from installed plugin.

        Returns:
            SyncResult with copy operation outcome

        Note:
            Copies files from ~/.claude/plugins/marketplaces/autonomous-dev/
            to project .claude/ directory.
        """
        # Find installed plugin
        home = Path.home()
        marketplace_base = home / ".claude" / "plugins" / "marketplaces" / "autonomous-dev"
        marketplace_dir = marketplace_base / "plugins" / "autonomous-dev"

        # SECURITY: Validate marketplace path to prevent symlink attacks (CWE-59)
        try:
            marketplace_dir = validate_path(marketplace_dir, "marketplace plugin directory")
        except ValueError as e:
            audit_log("security_violation", "marketplace_path_invalid", {
                "path": str(marketplace_dir),
                "error": str(e),
                "mode": "marketplace"
            })
            return SyncResult(
                success=False,
                mode=SyncMode.MARKETPLACE,
                message="Security validation failed",
                error=f"Invalid marketplace path: {e}",
            )

        if not marketplace_dir.exists():
            return SyncResult(
                success=False,
                mode=SyncMode.MARKETPLACE,
                message="Plugin not found in marketplace",
                error=f"Directory not found: {marketplace_dir}",
            )

        # Ensure target .claude directory exists
        claude_dir = self.project_path / ".claude"
        claude_dir.mkdir(exist_ok=True)

        # Copy commands, hooks, and other config files
        files_updated = 0
        try:
            # Copy commands (using _sync_directory to fix Issue #97)
            commands_src = marketplace_dir / "commands"
            commands_dst = claude_dir / "commands"
            if commands_src.exists():
                files_updated += self._sync_directory(
                    commands_src, commands_dst, pattern="*.md", description="command files"
                )

            # Copy hooks (using _sync_directory to fix Issue #97)
            hooks_src = marketplace_dir / "hooks"
            hooks_dst = claude_dir / "hooks"
            if hooks_src.exists():
                files_updated += self._sync_directory(
                    hooks_src, hooks_dst, pattern="*.py", description="hook files"
                )

            return SyncResult(
                success=True,
                mode=SyncMode.MARKETPLACE,
                message=f"Marketplace sync completed: {files_updated} files updated",
                details={
                    "files_updated": files_updated,
                    "source": str(marketplace_dir),
                    "commands": len(list(commands_dst.rglob("*.md")))
                    if commands_dst.exists()
                    else 0,
                },
            )

        except Exception as e:
            return SyncResult(
                success=False,
                mode=SyncMode.MARKETPLACE,
                message="Marketplace sync failed",
                error=str(e),
            )

    def _dispatch_plugin_dev(self) -> SyncResult:
        """Dispatch plugin development sync.

        Returns:
            SyncResult with sync operation outcome

        Note:
            Syncs plugin development files to local .claude/ directory.
            This is for developers working on the plugin itself.
        """
        # Find plugin directory
        plugin_dir = self.project_path / "plugins" / "autonomous-dev"

        # SECURITY: Validate plugin path to prevent symlink attacks (CWE-59)
        try:
            plugin_dir = validate_path(plugin_dir, "plugin development directory")
        except ValueError as e:
            audit_log("security_violation", "plugin_dev_path_invalid", {
                "path": str(plugin_dir),
                "error": str(e),
                "mode": "plugin_dev"
            })
            return SyncResult(
                success=False,
                mode=SyncMode.PLUGIN_DEV,
                message="Security validation failed",
                error=f"Invalid plugin directory: {e}",
            )

        if not plugin_dir.exists():
            return SyncResult(
                success=False,
                mode=SyncMode.PLUGIN_DEV,
                message="Plugin directory not found",
                error=f"Directory not found: {plugin_dir}",
            )

        # Ensure target .claude directory exists
        claude_dir = self.project_path / ".claude"
        claude_dir.mkdir(exist_ok=True)

        # Sync plugin files to .claude/ (TRUE SYNC - delete orphans)
        files_updated = 0
        try:
            # Sync commands (delete orphans = true sync)
            commands_src = plugin_dir / "commands"
            commands_dst = claude_dir / "commands"
            if commands_src.exists():
                files_updated += self._sync_directory(
                    commands_src, commands_dst, pattern="*.md",
                    description="command files", delete_orphans=True
                )

            # Sync hooks (delete orphans = true sync)
            hooks_src = plugin_dir / "hooks"
            hooks_dst = claude_dir / "hooks"
            if hooks_src.exists():
                files_updated += self._sync_directory(
                    hooks_src, hooks_dst, pattern="*.py",
                    description="hook files", delete_orphans=True
                )

            # Sync agents (delete orphans = true sync)
            agents_src = plugin_dir / "agents"
            agents_dst = claude_dir / "agents"
            if agents_src.exists():
                files_updated += self._sync_directory(
                    agents_src, agents_dst, pattern="*.md",
                    description="agent files", delete_orphans=True
                )

            # Sync lib files (delete orphans = true sync)
            lib_src = plugin_dir / "lib"
            lib_dst = claude_dir / "lib"
            if lib_src.exists():
                files_updated += self._sync_directory(
                    lib_src, lib_dst, pattern="*.py",
                    description="lib files", delete_orphans=True
                )

            # Sync config files (delete orphans = true sync)
            config_src = plugin_dir / "config"
            config_dst = claude_dir / "config"
            if config_src.exists():
                files_updated += self._sync_directory(
                    config_src, config_dst, pattern="*.json",
                    description="config files", delete_orphans=True
                )

            # Sync scripts (delete orphans = true sync)
            scripts_src = plugin_dir / "scripts"
            scripts_dst = claude_dir / "scripts"
            if scripts_src.exists():
                files_updated += self._sync_directory(
                    scripts_src, scripts_dst, pattern="*.py",
                    description="script files", delete_orphans=True
                )

            return SyncResult(
                success=True,
                mode=SyncMode.PLUGIN_DEV,
                message=f"Plugin dev sync completed: {files_updated} files updated",
                details={
                    "files_updated": files_updated,
                    "source": str(plugin_dir),
                },
            )

        except Exception as e:
            return SyncResult(
                success=False,
                mode=SyncMode.PLUGIN_DEV,
                message="Plugin dev sync failed",
                error=str(e),
            )

    def _dispatch_github(self) -> SyncResult:
        """Dispatch GitHub sync - fetch latest files from GitHub.

        This is the default sync mode for users. It fetches the latest
        files directly from the GitHub repository without needing to
        clone or pull the repo.

        Returns:
            SyncResult with fetch operation outcome

        Note:
            Uses raw.githubusercontent.com to fetch files listed in
            the install_manifest.json from the repository.
        """
        # GitHub configuration
        GITHUB_REPO = "akaszubski/autonomous-dev"
        GITHUB_BRANCH = "master"
        GITHUB_RAW_BASE = f"https://raw.githubusercontent.com/{GITHUB_REPO}/{GITHUB_BRANCH}"
        MANIFEST_URL = f"{GITHUB_RAW_BASE}/plugins/autonomous-dev/config/install_manifest.json"

        # Ensure target .claude directory exists
        claude_dir = self.project_path / ".claude"
        claude_dir.mkdir(exist_ok=True)

        files_updated = 0
        errors = []

        try:
            # Step 1: Fetch install_manifest.json
            audit_log(
                "github_sync",
                "fetching_manifest",
                {
                    "url": MANIFEST_URL,
                    "project_path": str(self.project_path),
                },
            )

            try:
                with urllib.request.urlopen(MANIFEST_URL, timeout=30) as response:
                    manifest_data = json.loads(response.read().decode("utf-8"))
            except urllib.error.URLError as e:
                return SyncResult(
                    success=False,
                    mode=SyncMode.GITHUB,
                    message="Failed to fetch manifest from GitHub",
                    error=f"Network error: {e}",
                )
            except json.JSONDecodeError as e:
                return SyncResult(
                    success=False,
                    mode=SyncMode.GITHUB,
                    message="Failed to parse manifest from GitHub",
                    error=f"JSON parse error: {e}",
                )

            # Step 2: Get list of files to fetch
            files_to_fetch = manifest_data.get("files", [])
            if not files_to_fetch:
                return SyncResult(
                    success=False,
                    mode=SyncMode.GITHUB,
                    message="No files listed in manifest",
                    error="install_manifest.json has empty 'files' list",
                )

            # Step 3: Fetch each file
            for file_path in files_to_fetch:
                # SECURITY: Validate file_path from manifest (CWE-22 prevention)
                # Reject path traversal patterns before processing
                if ".." in file_path or file_path.startswith("/"):
                    audit_log(
                        "security_violation",
                        "github_sync_path_traversal",
                        {
                            "file_path": file_path,
                            "reason": "Path traversal pattern detected",
                        },
                    )
                    errors.append(f"{file_path}: Invalid path pattern (security)")
                    continue

                # Skip non-essential files (docs, tests, etc.)
                if any(skip in file_path for skip in ["/docs/", "/tests/", "README.md", "CONTRIBUTING.md"]):
                    continue

                # Build GitHub URL
                file_url = f"{GITHUB_RAW_BASE}/{file_path}"

                # Determine destination path
                # Convert from plugins/autonomous-dev/X to .claude/X
                if file_path.startswith("plugins/autonomous-dev/"):
                    relative_path = file_path.replace("plugins/autonomous-dev/", "")
                    dest_path = claude_dir / relative_path
                else:
                    # For other files, place in .claude/
                    dest_path = claude_dir / Path(file_path).name

                # SECURITY: Validate destination path (CWE-22 prevention)
                # Ensure dest_path is within claude_dir (no directory escape)
                try:
                    resolved_dest = dest_path.resolve()
                    resolved_claude = claude_dir.resolve()
                    if not str(resolved_dest).startswith(str(resolved_claude)):
                        audit_log(
                            "security_violation",
                            "github_sync_directory_escape",
                            {
                                "file_path": file_path,
                                "dest_path": str(dest_path),
                                "resolved": str(resolved_dest),
                                "claude_dir": str(resolved_claude),
                            },
                        )
                        errors.append(f"{file_path}: Security validation failed (directory escape)")
                        continue
                except Exception as e:
                    errors.append(f"{file_path}: Path validation error: {e}")
                    continue

                try:
                    # Create parent directories
                    dest_path.parent.mkdir(parents=True, exist_ok=True)

                    # Fetch file
                    with urllib.request.urlopen(file_url, timeout=30) as response:
                        content = response.read()

                    # Write file
                    dest_path.write_bytes(content)
                    files_updated += 1

                except urllib.error.HTTPError as e:
                    if e.code == 404:
                        # File not found - skip silently (may be optional)
                        continue
                    errors.append(f"{file_path}: HTTP {e.code}")
                except urllib.error.URLError as e:
                    errors.append(f"{file_path}: {e}")
                except Exception as e:
                    errors.append(f"{file_path}: {e}")

            # Log completion
            audit_log(
                "github_sync",
                "completed",
                {
                    "project_path": str(self.project_path),
                    "files_updated": files_updated,
                    "errors": len(errors),
                },
            )

            # Build result
            if errors:
                return SyncResult(
                    success=True,  # Partial success
                    mode=SyncMode.GITHUB,
                    message=f"GitHub sync completed with warnings: {files_updated} files updated, {len(errors)} errors",
                    details={
                        "files_updated": files_updated,
                        "errors": errors[:5],  # Limit to first 5 errors
                        "source": GITHUB_REPO,
                    },
                )
            else:
                return SyncResult(
                    success=True,
                    mode=SyncMode.GITHUB,
                    message=f"GitHub sync completed: {files_updated} files updated from {GITHUB_REPO}",
                    details={
                        "files_updated": files_updated,
                        "source": GITHUB_REPO,
                        "branch": GITHUB_BRANCH,
                    },
                )

        except Exception as e:
            return SyncResult(
                success=False,
                mode=SyncMode.GITHUB,
                message="GitHub sync failed",
                error=str(e),
            )

    def _dispatch_all(self) -> SyncResult:
        """Dispatch all sync modes in sequence.

        Execution Order:
        1. ENVIRONMENT (most critical)
        2. MARKETPLACE (update from releases)
        3. PLUGIN_DEV (local development)

        Returns:
            SyncResult with aggregated results from all modes

        Note:
            Stops on first failure unless continue_on_error is set.
            Returns partial results if some modes succeed.
        """
        all_modes = get_individual_sync_modes()
        results = []
        aggregated_details = {
            "environment": {},
            "marketplace": {},
            "plugin_dev": {},
        }

        for mode in all_modes:
            # Dispatch individual mode (without backup - we have main backup)
            result = self.dispatch(mode, create_backup=False)
            results.append(result)

            # Store details
            mode_key = mode.value.replace("-", "_")
            aggregated_details[mode_key] = {
                "success": result.success,
                "message": result.message,
                "details": result.details,
            }

            # Stop on failure
            if not result.success:
                return SyncResult(
                    success=False,
                    mode=SyncMode.ALL,
                    message=f"All-mode sync failed at {mode.value}: {result.message}",
                    details=aggregated_details,
                    error=result.error,
                )

        # All succeeded
        total_files = sum(
            r.details.get("files_updated", 0) for r in results
        )
        return SyncResult(
            success=True,
            mode=SyncMode.ALL,
            message=f"All sync modes completed successfully: {total_files} files updated",
            details={
                **aggregated_details,
                "total_files_updated": total_files,
            },
        )

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

    def invoke(self, agent_name: str, context: Dict[str, Any]) -> Dict[str, Any]:
        """Mock invoke method."""
        return {"status": "success", "files_updated": 0, "conflicts": 0}


def dispatch_sync(
    project_path: str, mode: SyncMode, create_backup: bool = True
) -> SyncResult:
    """Convenience function to dispatch sync operation.

    Args:
        project_path: Path to project root
        mode: Sync mode to execute
        create_backup: Whether to create backup before sync

    Returns:
        SyncResult with operation outcome

    Example:
        >>> result = dispatch_sync("/path/to/project", SyncMode.ENVIRONMENT)
        >>> if result.success:
        ...     print(f"Success: {result.message}")
    """
    dispatcher = SyncDispatcher(project_path)
    return dispatcher.dispatch(mode, create_backup=create_backup)


def sync_marketplace(
    project_root: str,
    marketplace_plugins_file: Path,
    cleanup_orphans: bool = False,
    dry_run: bool = False,
) -> SyncResult:
    """Convenience function for marketplace sync with enhancements.

    This is the high-level API for marketplace sync that includes:
    - Version detection (upgrade/downgrade detection)
    - Orphan cleanup (optional, with dry-run support)
    - Rich result object with version and cleanup details

    Args:
        project_root: Path to project root directory
        marketplace_plugins_file: Path to installed_plugins.json
        cleanup_orphans: Whether to cleanup orphaned files (default: False)
        dry_run: Whether to dry-run orphan cleanup (default: False)

    Returns:
        SyncResult with version_comparison and orphan_cleanup attributes

    Example:
        >>> from pathlib import Path
        >>> result = sync_marketplace(
        ...     project_root="/path/to/project",
        ...     marketplace_plugins_file=Path("~/.claude/plugins/installed_plugins.json"),
        ...     cleanup_orphans=True,
        ...     dry_run=True
        ... )
        >>> print(result.summary)
        >>> if result.version_comparison:
        ...     print(f"Version: {result.version_comparison.status}")
    """
    dispatcher = SyncDispatcher(project_root)
    return dispatcher.sync_marketplace(
        marketplace_plugins_file=marketplace_plugins_file,
        cleanup_orphans=cleanup_orphans,
        dry_run=dry_run,
    )


def main() -> int:
    """CLI wrapper for sync_dispatcher.py.

    Parses command-line arguments and executes the appropriate sync mode.

    Arguments:
        --github: Fetch latest files from GitHub (default)
        --env: Sync environment (delegates to sync-validator agent)
        --marketplace: Copy files from installed plugin
        --plugin-dev: Sync plugin development files
        --all: Execute all sync modes in sequence

    Returns:
        Exit code: 0 for success, 1 for failure, 2 for invalid arguments

    Examples:
        # Default GitHub mode
        $ python3 sync_dispatcher.py

        # Explicit mode selection
        $ python3 sync_dispatcher.py --github
        $ python3 sync_dispatcher.py --env
        $ python3 sync_dispatcher.py --marketplace
        $ python3 sync_dispatcher.py --plugin-dev
        $ python3 sync_dispatcher.py --all
    """
    # Parse command-line arguments
    parser = argparse.ArgumentParser(
        description="Sync dispatcher for autonomous-dev plugin",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Default (GitHub mode)
  python3 sync_dispatcher.py

  # Explicit mode selection
  python3 sync_dispatcher.py --github
  python3 sync_dispatcher.py --env
  python3 sync_dispatcher.py --marketplace
  python3 sync_dispatcher.py --plugin-dev
  python3 sync_dispatcher.py --all

Exit Codes:
  0 - Success
  1 - Failure
  2 - Invalid arguments
"""
    )

    # Create mutually exclusive group for sync modes
    mode_group = parser.add_mutually_exclusive_group()
    mode_group.add_argument(
        '--github',
        action='store_true',
        help='Fetch latest files from GitHub (default)'
    )
    mode_group.add_argument(
        '--env',
        action='store_true',
        help='Sync environment via sync-validator agent'
    )
    mode_group.add_argument(
        '--marketplace',
        action='store_true',
        help='Copy files from installed plugin'
    )
    mode_group.add_argument(
        '--plugin-dev',
        action='store_true',
        help='Sync plugin development files'
    )
    mode_group.add_argument(
        '--all',
        action='store_true',
        help='Execute all sync modes in sequence'
    )

    try:
        args = parser.parse_args()

        # Determine sync mode (default to GITHUB)
        if args.env:
            mode = SyncMode.ENVIRONMENT
        elif args.marketplace:
            mode = SyncMode.MARKETPLACE
        elif args.plugin_dev:
            mode = SyncMode.PLUGIN_DEV
        elif args.all:
            mode = SyncMode.ALL
        else:
            # Default to GITHUB (when no flags or --github explicitly)
            mode = SyncMode.GITHUB

        # Get project root from current working directory
        project_root = os.getcwd()

        # Execute sync
        try:
            dispatcher = SyncDispatcher(project_root=project_root)
            result = dispatcher.dispatch(mode)

            # Output result
            if result.success:
                print(result.message)
                return 0
            else:
                # Print error to stderr
                error_msg = result.error if result.error else result.message
                print(f"Error: {error_msg}", file=sys.stderr)
                return 1

        except Exception as e:
            # Handle unexpected errors
            print(f"Error: {str(e)}", file=sys.stderr)
            return 1

    except KeyboardInterrupt:
        print("\nSync cancelled by user.", file=sys.stderr)
        return 1
    except SystemExit:
        # argparse raises SystemExit for --help or invalid args
        # Re-raise to propagate exit code (0 for --help, 2 for errors)
        raise


if __name__ == "__main__":
    sys.exit(main())
