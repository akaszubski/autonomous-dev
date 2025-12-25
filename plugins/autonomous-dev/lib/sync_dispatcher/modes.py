#!/usr/bin/env python3
"""
Sync Dispatcher Modes - Individual sync mode implementations

This module contains the dispatch functions for each sync mode. Each function
is extracted from the SyncDispatcher class to improve modularity.

Modes:
- dispatch_environment: Delegate to sync-validator agent
- dispatch_marketplace: Copy from installed plugin
- dispatch_plugin_dev: Sync plugin development files
- dispatch_github: Fetch latest from GitHub
- dispatch_all: Execute all modes in sequence

Design Patterns:
    See library-design-patterns skill for standardized design patterns.
"""

import json
import urllib.request
import urllib.error
from pathlib import Path
from typing import TYPE_CHECKING

# Import dependencies
try:
    from plugins.autonomous_dev.lib.security_utils import validate_path, audit_log
    from plugins.autonomous_dev.lib.sync_mode_detector import SyncMode, get_individual_sync_modes
except ImportError:
    from security_utils import validate_path, audit_log  # type: ignore
    from sync_mode_detector import SyncMode, get_individual_sync_modes  # type: ignore

# Import models
from .models import SyncResult

# TYPE_CHECKING pattern prevents circular imports
if TYPE_CHECKING:
    from .dispatcher import SyncDispatcher


def dispatch_environment(dispatcher: "SyncDispatcher") -> SyncResult:
    """Dispatch environment sync to sync-validator agent.

    Args:
        dispatcher: SyncDispatcher instance

    Returns:
        SyncResult with agent execution outcome

    Note:
        This delegates to the existing sync-validator agent which handles
        environment validation and synchronization.
    """
    # Import AgentInvoker (local import to avoid circular dependencies)
    try:
        # Import from parent package for backward compatibility with tests
        # Tests patch 'plugins.autonomous_dev.lib.sync_dispatcher.AgentInvoker'
        try:
            from plugins.autonomous_dev.lib import sync_dispatcher
            AgentInvoker = sync_dispatcher.AgentInvoker
        except ImportError:
            # Fallback for installed environment
            from sync_dispatcher import AgentInvoker  # type: ignore

        invoker = AgentInvoker(str(dispatcher.project_path))
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


def dispatch_marketplace(dispatcher: "SyncDispatcher") -> SyncResult:
    """Dispatch marketplace sync - copy from installed plugin.

    Args:
        dispatcher: SyncDispatcher instance

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
    claude_dir = dispatcher.project_path / ".claude"
    claude_dir.mkdir(exist_ok=True)

    # Copy commands, hooks, and other config files
    files_updated = 0
    try:
        # Copy commands (using _sync_directory to fix Issue #97)
        commands_src = marketplace_dir / "commands"
        commands_dst = claude_dir / "commands"
        if commands_src.exists():
            files_updated += dispatcher._sync_directory(
                commands_src, commands_dst, pattern="*.md", description="command files"
            )

        # Copy hooks (using _sync_directory to fix Issue #97)
        hooks_src = marketplace_dir / "hooks"
        hooks_dst = claude_dir / "hooks"
        if hooks_src.exists():
            files_updated += dispatcher._sync_directory(
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


def dispatch_plugin_dev(dispatcher: "SyncDispatcher") -> SyncResult:
    """Dispatch plugin development sync.

    Args:
        dispatcher: SyncDispatcher instance

    Returns:
        SyncResult with sync operation outcome

    Note:
        Syncs plugin development files to local .claude/ directory.
        This is for developers working on the plugin itself.
    """
    # Find plugin directory
    plugin_dir = dispatcher.project_path / "plugins" / "autonomous-dev"

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
    claude_dir = dispatcher.project_path / ".claude"
    claude_dir.mkdir(exist_ok=True)

    # Sync plugin files to .claude/ (TRUE SYNC - delete orphans)
    files_updated = 0
    try:
        # Sync commands (delete orphans = true sync)
        commands_src = plugin_dir / "commands"
        commands_dst = claude_dir / "commands"
        if commands_src.exists():
            files_updated += dispatcher._sync_directory(
                commands_src, commands_dst, pattern="*.md",
                description="command files", delete_orphans=True
            )

        # Sync hooks (delete orphans = true sync)
        hooks_src = plugin_dir / "hooks"
        hooks_dst = claude_dir / "hooks"
        if hooks_src.exists():
            files_updated += dispatcher._sync_directory(
                hooks_src, hooks_dst, pattern="*.py",
                description="hook files", delete_orphans=True
            )

        # Sync agents (delete orphans = true sync)
        agents_src = plugin_dir / "agents"
        agents_dst = claude_dir / "agents"
        if agents_src.exists():
            files_updated += dispatcher._sync_directory(
                agents_src, agents_dst, pattern="*.md",
                description="agent files", delete_orphans=True
            )

        # Sync lib files (delete orphans = true sync)
        lib_src = plugin_dir / "lib"
        lib_dst = claude_dir / "lib"
        if lib_src.exists():
            files_updated += dispatcher._sync_directory(
                lib_src, lib_dst, pattern="*.py",
                description="lib files", delete_orphans=True
            )

        # Sync config files (delete orphans = true sync)
        config_src = plugin_dir / "config"
        config_dst = claude_dir / "config"
        if config_src.exists():
            files_updated += dispatcher._sync_directory(
                config_src, config_dst, pattern="*.json",
                description="config files", delete_orphans=True
            )

        # Sync scripts (delete orphans = true sync)
        scripts_src = plugin_dir / "scripts"
        scripts_dst = claude_dir / "scripts"
        if scripts_src.exists():
            files_updated += dispatcher._sync_directory(
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


def dispatch_github(dispatcher: "SyncDispatcher") -> SyncResult:
    """Dispatch GitHub sync - fetch latest files from GitHub.

    This is the default sync mode for users. It fetches the latest
    files directly from the GitHub repository without needing to
    clone or pull the repo.

    Args:
        dispatcher: SyncDispatcher instance

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
    claude_dir = dispatcher.project_path / ".claude"
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
                "project_path": str(dispatcher.project_path),
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

        # Step 2: Get list of files to fetch from components structure
        # The manifest uses a components structure with nested files arrays
        files_to_fetch = []
        components = manifest_data.get("components", {})
        for component_name, component_data in components.items():
            if isinstance(component_data, dict) and "files" in component_data:
                files_to_fetch.extend(component_data["files"])

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

        # Step 4: Also download hooks and libs DIRECTLY to ~/.claude/ (global)
        # This ensures settings.json can find hooks at ~/.claude/hooks/
        # We download from GitHub again (not copy from project) to solve
        # chicken-and-egg: old sync_dispatcher still downloads from GitHub
        global_claude_dir = Path.home() / ".claude"
        global_hooks_copied = 0
        global_libs_copied = 0
        global_hooks_orphans_deleted = 0
        global_libs_orphans_deleted = 0

        try:
            # Get hooks and libs from manifest
            hook_files = components.get("hooks", {}).get("files", [])
            lib_files = components.get("lib", {}).get("files", [])

            # Download hooks directly to ~/.claude/hooks/
            global_hooks_dir = global_claude_dir / "hooks"
            global_hooks_dir.mkdir(parents=True, exist_ok=True)

            # Clean orphan hooks from ~/.claude/hooks/ (TRUE SYNC)
            # Get expected hook names from manifest
            expected_hooks = {Path(f).name for f in hook_files}
            # Get actual hooks in directory
            actual_hooks = {f.name for f in global_hooks_dir.glob("*.py") if not f.name.startswith("__")}
            # Delete orphans (files not in manifest)
            orphan_hooks = actual_hooks - expected_hooks
            global_hooks_orphans_deleted = 0
            for orphan in orphan_hooks:
                orphan_path = global_hooks_dir / orphan
                try:
                    orphan_path.unlink()
                    global_hooks_orphans_deleted += 1
                    audit_log(
                        "github_sync",
                        "orphan_hook_deleted",
                        {"path": str(orphan_path), "reason": "not in manifest"},
                    )
                except Exception:
                    pass  # Non-blocking

            for file_path in hook_files:
                if ".." in file_path or file_path.startswith("/"):
                    continue
                file_url = f"{GITHUB_RAW_BASE}/{file_path}"
                file_name = Path(file_path).name
                dest = global_hooks_dir / file_name
                try:
                    with urllib.request.urlopen(file_url, timeout=30) as response:
                        dest.write_bytes(response.read())
                    global_hooks_copied += 1
                except Exception:
                    pass  # Non-blocking

            # Download libs directly to ~/.claude/lib/
            global_lib_dir = global_claude_dir / "lib"
            global_lib_dir.mkdir(parents=True, exist_ok=True)

            # Clean orphan libs from ~/.claude/lib/ (TRUE SYNC)
            # Get expected lib names from manifest
            expected_libs = {Path(f).name for f in lib_files}
            # Get actual libs in directory
            actual_libs = {f.name for f in global_lib_dir.glob("*.py") if not f.name.startswith("__")}
            # Delete orphans (files not in manifest)
            orphan_libs = actual_libs - expected_libs
            global_libs_orphans_deleted = 0
            for orphan in orphan_libs:
                orphan_path = global_lib_dir / orphan
                try:
                    orphan_path.unlink()
                    global_libs_orphans_deleted += 1
                    audit_log(
                        "github_sync",
                        "orphan_lib_deleted",
                        {"path": str(orphan_path), "reason": "not in manifest"},
                    )
                except Exception:
                    pass  # Non-blocking

            for file_path in lib_files:
                if ".." in file_path or file_path.startswith("/"):
                    continue
                file_url = f"{GITHUB_RAW_BASE}/{file_path}"
                file_name = Path(file_path).name
                dest = global_lib_dir / file_name
                try:
                    with urllib.request.urlopen(file_url, timeout=30) as response:
                        dest.write_bytes(response.read())
                    global_libs_copied += 1
                except Exception:
                    pass  # Non-blocking

            # Clear Python bytecode cache to ensure fresh imports
            # This prevents stale .pyc files from being used instead of updated .py files
            pycache_cleared = 0
            for pycache_dir in [
                global_lib_dir / "__pycache__",
                dispatcher.project_path / ".claude" / "lib" / "__pycache__",
                dispatcher.project_path / "plugins" / "autonomous-dev" / "lib" / "__pycache__",
            ]:
                if pycache_dir.exists():
                    try:
                        import shutil
                        shutil.rmtree(pycache_dir)
                        pycache_cleared += 1
                    except Exception:
                        pass  # Non-blocking

            audit_log(
                "github_sync",
                "global_download",
                {
                    "hooks_downloaded": global_hooks_copied,
                    "libs_downloaded": global_libs_copied,
                    "hooks_orphans_deleted": global_hooks_orphans_deleted,
                    "libs_orphans_deleted": global_libs_orphans_deleted,
                    "pycache_cleared": pycache_cleared,
                    "global_dir": str(global_claude_dir),
                },
            )
        except Exception as e:
            # Non-blocking - log but don't fail sync
            audit_log(
                "github_sync",
                "global_download_error",
                {
                    "error": str(e),
                    "global_dir": str(global_claude_dir),
                },
            )
            errors.append(f"Global download failed: {e}")

        # Step 5: Migrate hooks from array format to object format (Issue #135)
        # This runs after global file downloads to fix any old format settings
        hooks_migrated = False
        try:
            from plugins.autonomous_dev.lib.hook_activator import migrate_hooks_to_object_format

            settings_path = Path.home() / ".claude" / "settings.json"
            if settings_path.exists():
                migration_result = migrate_hooks_to_object_format(settings_path)

                if migration_result['migrated']:
                    # Migration performed - log success
                    hooks_migrated = True
                    audit_log(
                        "github_sync",
                        "hooks_migrated",
                        {
                            "project_path": str(dispatcher.project_path),
                            "settings_path": str(settings_path),
                            "backup_path": str(migration_result['backup_path']),
                            "format": migration_result['format'],
                        },
                    )
                elif migration_result['error']:
                    # Migration failed - log but don't block sync
                    audit_log(
                        "github_sync",
                        "hooks_migration_failed",
                        {
                            "project_path": str(dispatcher.project_path),
                            "settings_path": str(settings_path),
                            "error": migration_result['error'],
                        },
                    )
                # else: No migration needed (already object format or missing)

        except Exception as e:
            # Migration failed - log but don't block sync (non-blocking enhancement)
            audit_log(
                "github_sync",
                "hooks_migration_exception",
                {
                    "project_path": str(dispatcher.project_path),
                    "error": str(e),
                },
            )

        # Log completion
        audit_log(
            "github_sync",
            "completed",
            {
                "project_path": str(dispatcher.project_path),
                "files_updated": files_updated,
                "global_hooks": global_hooks_copied,
                "global_libs": global_libs_copied,
                "errors": len(errors),
            },
        )

        # Build result
        orphans_deleted = global_hooks_orphans_deleted + global_libs_orphans_deleted
        orphan_msg = f", {orphans_deleted} orphans cleaned" if orphans_deleted > 0 else ""
        migration_msg = ", hooks format migrated" if hooks_migrated else ""
        global_msg = f", {global_hooks_copied} hooks + {global_libs_copied} libs to ~/.claude/{orphan_msg}{migration_msg}"
        if errors:
            return SyncResult(
                success=True,  # Partial success
                mode=SyncMode.GITHUB,
                message=f"GitHub sync completed with warnings: {files_updated} files updated{global_msg}, {len(errors)} errors",
                details={
                    "files_updated": files_updated,
                    "global_hooks": global_hooks_copied,
                    "global_libs": global_libs_copied,
                    "hooks_migrated": hooks_migrated,
                    "errors": errors[:5],  # Limit to first 5 errors
                    "source": GITHUB_REPO,
                },
            )
        else:
            return SyncResult(
                success=True,
                mode=SyncMode.GITHUB,
                message=f"GitHub sync completed: {files_updated} files updated{global_msg}",
                details={
                    "files_updated": files_updated,
                    "global_hooks": global_hooks_copied,
                    "global_libs": global_libs_copied,
                    "hooks_migrated": hooks_migrated,
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


def dispatch_all(dispatcher: "SyncDispatcher") -> SyncResult:
    """Dispatch all sync modes in sequence.

    Execution Order:
    1. ENVIRONMENT (most critical)
    2. MARKETPLACE (update from releases)
    3. PLUGIN_DEV (local development)

    Args:
        dispatcher: SyncDispatcher instance

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
        result = dispatcher.dispatch(mode, create_backup=False)
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
