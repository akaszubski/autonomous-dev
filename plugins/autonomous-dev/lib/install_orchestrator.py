#!/usr/bin/env python3
"""
Install Orchestrator - Coordinates complete installation workflow

This module orchestrates the entire installation process, including:
- Fresh installations
- Upgrades with backup and rollback
- Marketplace directory detection
- Validation and reporting

Key Features:
- Comprehensive file discovery and copying
- Automatic backup before upgrades
- Rollback on failure
- Marketplace directory auto-detection
- Installation marker file tracking
- Validation and coverage reporting

Usage:
    from install_orchestrator import InstallOrchestrator

    # Fresh install
    orchestrator = InstallOrchestrator(plugin_dir, project_dir)
    result = orchestrator.fresh_install()

    # Upgrade install
    result = orchestrator.upgrade_install()

    # Rollback
    orchestrator.rollback(backup_dir)

    # Auto-detect marketplace
    orchestrator = InstallOrchestrator.auto_detect(project_dir)

Date: 2025-11-17
Issue: GitHub #80 (Bootstrap overhaul - Phase 4)
Agent: implementer

Design Patterns:
    See library-design-patterns skill for standardized design patterns.
    See error-handling-patterns skill for exception handling.
"""

import json
import shutil
import os
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any, Optional
from dataclasses import dataclass, asdict

from .file_discovery import FileDiscovery
from .copy_system import CopySystem
from .installation_validator import InstallationValidator, ValidationResult

# Security utilities for path validation and audit logging
try:
    from plugins.autonomous_dev.lib.security_utils import validate_path, audit_log
except ImportError:
    from security_utils import validate_path, audit_log


class InstallError(Exception):
    """Raised when installation encounters a critical error."""
    pass


@dataclass
class InstallResult:
    """Result of installation operation.

    Attributes:
        status: "success" or "failure"
        files_copied: Number of files copied
        coverage: Coverage percentage (0-100)
        errors: List of error messages
        backup_dir: Optional backup directory path
    """
    status: str
    files_copied: int
    coverage: float
    errors: List[str]
    backup_dir: Optional[Path] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        result = asdict(self)
        if result["backup_dir"]:
            result["backup_dir"] = str(result["backup_dir"])
        return result


class InstallOrchestrator:
    """Orchestrates plugin installation workflow.

    Coordinates file discovery, copying, validation, backup, and rollback.

    Attributes:
        plugin_dir: Path to plugin source directory
        project_dir: Path to project directory
        claude_dir: Path to .claude directory in project
        discovery: FileDiscovery instance
        copy_system: CopySystem instance

    Examples:
        >>> orchestrator = InstallOrchestrator(plugin_dir, project_dir)
        >>> result = orchestrator.fresh_install()
        >>> print(f"Installed {result.files_copied} files")
    """

    def __init__(self, plugin_dir: Path, project_dir: Path):
        """Initialize orchestrator with security validation.

        Args:
            plugin_dir: Plugin source directory
            project_dir: Project directory

        Raises:
            InstallError: If plugin directory doesn't exist
            ValueError: If path validation fails (path traversal, symlink)
        """
        # Validate paths (prevents CWE-22, CWE-59)
        self.plugin_dir = validate_path(
            Path(plugin_dir).resolve(),
            purpose="plugin directory",
            allow_missing=False
        )
        self.project_dir = validate_path(
            Path(project_dir).resolve(),
            purpose="project directory",
            allow_missing=False
        )
        self.claude_dir = self.project_dir / ".claude"

        # Audit log initialization
        audit_log("install_orchestrator", "initialized", {
            "plugin_dir": str(self.plugin_dir),
            "project_dir": str(self.project_dir)
        })

        self.discovery = FileDiscovery(self.plugin_dir)
        # CopySystem will be created per operation with specific source/dest
        self._copy_system_class = CopySystem

    @classmethod
    def from_marketplace(cls, marketplace_dir: Path, project_dir: Path) -> "InstallOrchestrator":
        """Create orchestrator from marketplace directory.

        Marketplace structure:
        ~/.claude/plugins/marketplaces/autonomous-dev/plugins/autonomous-dev/

        Args:
            marketplace_dir: Marketplace root directory
            project_dir: Project directory

        Returns:
            InstallOrchestrator instance

        Raises:
            InstallError: If marketplace directory structure is invalid
        """
        marketplace_dir = Path(marketplace_dir)
        plugin_dir = marketplace_dir / "plugins" / "autonomous-dev"

        if not plugin_dir.exists():
            raise InstallError(
                f"Invalid marketplace structure. Expected: {plugin_dir}"
            )

        return cls(plugin_dir, project_dir)

    @classmethod
    def auto_detect(cls, project_dir: Path) -> "InstallOrchestrator":
        """Auto-detect marketplace directory and create orchestrator.

        Checks common locations:
        - ~/.claude/plugins/marketplaces/autonomous-dev/
        - /usr/local/share/claude/plugins/marketplaces/autonomous-dev/

        Args:
            project_dir: Project directory

        Returns:
            InstallOrchestrator instance

        Raises:
            InstallError: If marketplace directory not found
        """
        home = Path.home()
        search_paths = [
            home / ".claude" / "plugins" / "marketplaces" / "autonomous-dev",
            Path("/usr/local/share/claude/plugins/marketplaces/autonomous-dev"),
        ]

        for marketplace_dir in search_paths:
            if marketplace_dir.exists():
                return cls.from_marketplace(marketplace_dir, project_dir)

        raise InstallError(
            "Could not auto-detect marketplace directory. "
            f"Searched: {', '.join(str(p) for p in search_paths)}"
        )

    def fresh_install(self) -> InstallResult:
        """Perform fresh installation.

        Workflow:
        1. Discover all files in plugin directory
        2. Copy all files to .claude directory
        3. Set executable permissions on scripts
        4. Create installation marker file
        5. Validate coverage

        Returns:
            InstallResult with status and metrics

        Raises:
            InstallError: If installation fails
        """
        errors = []

        try:
            # Step 1: Discover all files
            files = self.discovery.discover_all_files()
            total_files = len(files)

            if total_files == 0:
                raise InstallError("No files discovered in plugin directory")

            # Step 2: Ensure .claude directory exists
            self.claude_dir.mkdir(parents=True, exist_ok=True)

            # Step 3: Copy all files using CopySystem
            copy_system = CopySystem(self.plugin_dir, self.claude_dir)
            copy_result = copy_system.copy_all(
                files=files,
                overwrite=True,
                preserve_timestamps=True,
                continue_on_error=True
            )

            files_copied = copy_result["files_copied"]
            if copy_result["errors"] > 0:
                errors.extend(copy_result["error_list"])

            # Step 4: Set executable permissions on scripts
            self._set_executable_permissions()

            # Step 5: Create installation marker
            self._create_marker_file(files_copied)

            # Step 6: Validate coverage
            validator = InstallationValidator(self.plugin_dir, self.claude_dir)
            validation = validator.validate()

            status = "success" if validation.status == "complete" else "failure"

            if validation.status != "complete":
                errors.append(f"Incomplete installation: {validation.coverage}% coverage")

            return InstallResult(
                status=status,
                files_copied=files_copied,
                coverage=validation.coverage,
                errors=errors,
            )

        except Exception as e:
            raise InstallError(f"Fresh installation failed: {e}")

    def upgrade_install(self) -> InstallResult:
        """Perform upgrade installation with backup.

        Workflow:
        1. Create backup of existing installation
        2. Discover files
        3. Copy files (preserving user customizations if possible)
        4. Set permissions
        5. Update marker file
        6. Validate
        7. On failure: rollback

        Returns:
            InstallResult with backup directory

        Raises:
            InstallError: If upgrade fails and rollback fails
        """
        errors = []
        backup_dir = None

        try:
            # Step 1: Create backup
            backup_dir = self._create_backup()

            # Step 2: Discover files
            files = self.discovery.discover_all_files()
            total_files = len(files)

            # Step 3: Copy files (filter out preserved files)
            files_to_copy = []
            for source_file in files:
                rel_path = source_file.relative_to(self.plugin_dir)
                dest_file = self.claude_dir / rel_path

                # Only copy if not preserved or doesn't exist
                if not self._should_preserve(dest_file) or not dest_file.exists():
                    files_to_copy.append(source_file)

            # Use CopySystem for batch copy
            copy_system = CopySystem(self.plugin_dir, self.claude_dir)
            copy_result = copy_system.copy_all(
                files=files_to_copy,
                overwrite=True,
                preserve_timestamps=True,
                continue_on_error=True
            )

            files_copied = copy_result["files_copied"]
            if copy_result["errors"] > 0:
                errors.extend(copy_result["error_list"])

            # Step 4: Set permissions
            self._set_executable_permissions()

            # Step 5: Update marker
            self._create_marker_file(files_copied)

            # Step 6: Validate
            validator = InstallationValidator(self.plugin_dir, self.claude_dir)
            validation = validator.validate()

            if validation.status != "complete":
                # Rollback on incomplete installation
                errors.append(f"Validation failed: {validation.coverage}% coverage")
                self.rollback(backup_dir)
                return InstallResult(
                    status="failure",
                    files_copied=0,
                    coverage=0.0,
                    errors=errors,
                    backup_dir=backup_dir,
                )

            return InstallResult(
                status="success",
                files_copied=files_copied,
                coverage=validation.coverage,
                errors=errors,
                backup_dir=backup_dir,
            )

        except Exception as e:
            if backup_dir:
                try:
                    self.rollback(backup_dir)
                except Exception as rollback_error:
                    raise InstallError(
                        f"Upgrade failed and rollback failed: {e}, {rollback_error}"
                    )
            raise InstallError(f"Upgrade installation failed: {e}")

    def rollback(self, backup_dir: Path) -> bool:
        """Rollback installation from backup.

        Args:
            backup_dir: Path to backup directory

        Returns:
            True if rollback succeeded

        Raises:
            InstallError: If rollback fails
        """
        backup_dir = Path(backup_dir)

        if not backup_dir.exists():
            raise InstallError(f"Backup directory not found: {backup_dir}")

        try:
            # Remove current installation
            if self.claude_dir.exists():
                shutil.rmtree(self.claude_dir)

            # Restore from backup
            shutil.copytree(backup_dir, self.claude_dir)

            return True

        except Exception as e:
            raise InstallError(f"Rollback failed: {e}")

    def _create_backup(self) -> Path:
        """Create backup of existing installation.

        Returns:
            Path to backup directory
        """
        timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        backup_dir = self.claude_dir / f".backup-{timestamp}"

        if self.claude_dir.exists():
            # Copy existing installation to backup
            shutil.copytree(
                self.claude_dir,
                backup_dir,
                ignore=shutil.ignore_patterns(".backup-*")
            )

        return backup_dir

    def _set_executable_permissions(self):
        """Set executable permissions on scripts and hooks."""
        executable_patterns = [
            "scripts/*.py",
            "hooks/*.py",
        ]

        for pattern in executable_patterns:
            for file_path in self.claude_dir.glob(pattern):
                if file_path.is_file():
                    # Security: Set explicit permissions (fixes CWE-732)
                    # Use 0o755 (rwxr-xr-x) instead of bitwise OR to prevent
                    # world-writable files
                    file_path.chmod(0o755)

    def _create_marker_file(self, files_installed: int):
        """Create installation marker file.

        Args:
            files_installed: Number of files installed
        """
        marker_file = self.claude_dir / ".autonomous-dev-installed"

        metadata = {
            "version": "3.8.0",  # Should match plugin version
            "timestamp": datetime.now().isoformat(),
            "files_installed": files_installed,
            "plugin_dir": str(self.plugin_dir),
        }

        with open(marker_file, "w") as f:
            json.dump(metadata, f, indent=2)

    def _should_preserve(self, file_path: Path) -> bool:
        """Check if file should be preserved during upgrade.

        Preserves user customizations in:
        - .env files
        - settings.local.json
        - Custom hooks

        Args:
            file_path: File path to check

        Returns:
            True if file should be preserved
        """
        preserve_patterns = [
            ".env",
            "settings.local.json",
            "custom_hooks/",
        ]

        for pattern in preserve_patterns:
            if pattern in str(file_path):
                return True

        return False


# CLI interface for standalone usage
if __name__ == "__main__":
    import sys
    import argparse

    parser = argparse.ArgumentParser(description="Install autonomous-dev plugin")
    parser.add_argument("--source", type=Path, help="Source plugin directory")
    parser.add_argument("--dest", type=Path, required=True, help="Destination project directory")
    parser.add_argument("--mode", choices=["fresh", "upgrade"], default="fresh", help="Installation mode")
    parser.add_argument("--auto-detect", action="store_true", help="Auto-detect marketplace directory")

    args = parser.parse_args()

    try:
        if args.auto_detect:
            orchestrator = InstallOrchestrator.auto_detect(args.dest)
        elif args.source:
            orchestrator = InstallOrchestrator(args.source, args.dest)
        else:
            print("❌ Error: --source required unless --auto-detect is used", file=sys.stderr)
            sys.exit(1)

        if args.mode == "fresh":
            result = orchestrator.fresh_install()
        else:
            result = orchestrator.upgrade_install()

        print(f"{'✅' if result.status == 'success' else '❌'} Installation {result.status}")
        print(f"📊 Files copied: {result.files_copied}")
        print(f"📈 Coverage: {result.coverage}%")

        if result.errors:
            print("\n⚠️ Errors:")
            for error in result.errors:
                print(f"  - {error}")

        sys.exit(0 if result.status == "success" else 1)

    except InstallError as e:
        print(f"❌ Installation Error: {e}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"❌ Unexpected Error: {e}", file=sys.stderr)
        sys.exit(1)
