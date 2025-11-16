#!/usr/bin/env python3
"""
Copy System - Structure-preserving file copying for installation

This module provides intelligent file copying that preserves directory structure,
handles permissions correctly, and provides progress reporting.

Key Features:
- Directory structure preservation (lib/foo.py → .claude/lib/foo.py)
- Executable permissions for scripts (scripts/*.py get +x)
- Progress reporting with callbacks
- Error handling with optional continuation
- Timestamp preservation
- Rollback support

Usage:
    from copy_system import CopySystem

    # Basic copy
    copier = CopySystem(source_dir, dest_dir)
    result = copier.copy_all()

    # Copy with progress
    def progress(current, total, file_path):
        print(f"[{current}/{total}] {file_path}")

    copier.copy_all(progress_callback=progress)

Date: 2025-11-17
Issue: GitHub #80 (Bootstrap overhaul - 100% file coverage)
Agent: implementer

Design Patterns:
    See library-design-patterns skill for standardized design patterns.
"""

import os
import shutil
import stat
from pathlib import Path
from typing import List, Dict, Any, Optional, Callable

# Security utilities for path validation and audit logging
try:
    from plugins.autonomous_dev.lib.security_utils import validate_path, audit_log
except ImportError:
    from security_utils import validate_path, audit_log


class CopyError(Exception):
    """Exception raised during copy operations."""
    pass


class CopySystem:
    """Intelligent file copying with structure preservation.

    This class is stateless - source and dest are provided per operation,
    not stored in the constructor. This allows one instance to handle
    multiple copy operations with different sources/destinations.

    Attributes:
        source: Source directory path
        dest: Destination directory path

    Examples:
        >>> copier = CopySystem(plugin_dir, project_dir / ".claude")
        >>> result = copier.copy_all()
        >>> print(f"Copied {result['files_copied']} files")
    """

    def __init__(self, source: Path, dest: Path):
        """Initialize copy system with security validation.

        Args:
            source: Source directory path
            dest: Destination directory path

        Raises:
            ValueError: If path validation fails (path traversal, symlink)
        """
        # Validate source path (prevents CWE-22, CWE-59)
        self.source = validate_path(
            Path(source).resolve(),
            purpose="source directory",
            allow_missing=False
        )

        # Validate destination path (can be missing, will be created)
        self.dest = validate_path(
            Path(dest).resolve(),
            purpose="destination directory",
            allow_missing=True
        )

        # Audit log initialization
        audit_log("copy_system", "initialized", {
            "source": str(self.source),
            "dest": str(self.dest)
        })

    def copy_all(
        self,
        files: Optional[List[Path]] = None,
        overwrite: bool = True,
        preserve_timestamps: bool = True,
        show_progress: bool = False,
        progress_callback: Optional[Callable[[int, int, str], None]] = None,
        continue_on_error: bool = False
    ) -> Dict[str, Any]:
        """Copy all files while preserving directory structure.

        Args:
            files: List of files to copy (absolute paths). If None, copies all files.
            overwrite: Allow overwriting existing files (default: True)
            preserve_timestamps: Preserve file modification times (default: True)
            show_progress: Display progress to stdout (default: False)
            progress_callback: Callback function(current, total, file_path)
            continue_on_error: Continue copying on errors (default: False)

        Returns:
            Dictionary with copy results:
            {
                "files_copied": 123,
                "errors": 0,
                "error_list": []
            }

        Raises:
            CopyError: If source doesn't exist or overwrite=False and file exists
        """
        # Validate source exists
        if not self.source.exists():
            raise CopyError(
                f"Source directory not found: {self.source}\n"
                f"Expected structure: plugins/autonomous-dev/"
            )

        # Discover files if not provided
        if files is None:
            from plugins.autonomous_dev.lib.file_discovery import FileDiscovery
            discovery = FileDiscovery(self.source)
            files = discovery.discover_all_files()

        # Create destination directory
        self.dest.mkdir(parents=True, exist_ok=True)

        # Copy files
        files_copied = 0
        errors = []

        for idx, file_path in enumerate(files, 1):
            try:
                # Get relative path
                relative = file_path.relative_to(self.source)
                dest_path = self.dest / relative

                # Check if file exists and overwrite not allowed
                if dest_path.exists() and not overwrite:
                    raise CopyError(
                        f"File already exists: {dest_path}\n"
                        f"Use overwrite=True to replace existing files"
                    )

                # Create parent directories
                dest_path.parent.mkdir(parents=True, exist_ok=True)

                # Security: Validate file path before copy (prevents CWE-22)
                validate_path(file_path, purpose="plugin file")

                # Copy file without following symlinks (prevents CWE-59)
                shutil.copy2(file_path, dest_path, follow_symlinks=False)

                # Set permissions
                is_script = self._is_script(file_path)
                self._set_permissions(dest_path, file_path, is_script)

                # Preserve timestamps if requested
                if not preserve_timestamps:
                    # Touch file to update timestamp
                    dest_path.touch()

                files_copied += 1

                # Progress reporting
                if progress_callback:
                    progress_callback(idx, len(files), str(relative))

                if show_progress:
                    percentage = (idx / len(files)) * 100
                    print(f"[{idx}/{len(files)}] Copying {relative}... ({percentage:.0f}%)")

            except Exception as e:
                error_msg = f"Error copying {file_path}: {e}"
                errors.append(error_msg)

                if not continue_on_error:
                    raise CopyError(error_msg)

        return {
            "files_copied": files_copied,
            "errors": len(errors),
            "error_list": errors
        }

    def _is_script(self, file_path: Path) -> bool:
        """Check if file is a script (should be executable).

        Args:
            file_path: Path to check

        Returns:
            True if file should be executable
        """
        # Scripts directory
        parts = file_path.relative_to(self.source).parts
        if len(parts) > 0 and parts[0] == "scripts":
            return file_path.suffix == ".py"

        # Files with shebang
        try:
            with open(file_path, "rb") as f:
                first_line = f.readline()
                return first_line.startswith(b"#!")
        except:
            return False

    def _set_permissions(self, dest_path: Path, source_path: Path, is_script: bool) -> None:
        """Set appropriate file permissions.

        Args:
            dest_path: Destination file path
            source_path: Source file path
            is_script: Whether file is a script (should be executable)
        """
        if is_script:
            # Scripts: rwxr-xr-x (0o755)
            dest_path.chmod(0o755)
        else:
            # Copy permissions from source
            source_mode = source_path.stat().st_mode
            dest_path.chmod(source_mode)


def rollback(backup_dir: Path, dest_dir: Path) -> bool:
    """Rollback installation by restoring from backup.

    Args:
        backup_dir: Path to backup directory
        dest_dir: Path to destination directory to restore

    Returns:
        True if rollback successful, False otherwise

    Examples:
        >>> success = rollback(backup_dir, project_dir / ".claude")
    """
    try:
        # Remove current installation
        if dest_dir.exists():
            shutil.rmtree(dest_dir)

        # Restore from backup
        if backup_dir.exists():
            shutil.copytree(backup_dir, dest_dir)
            return True
        else:
            # No backup to restore
            return False

    except Exception as e:
        print(f"Rollback failed: {e}")
        return False
