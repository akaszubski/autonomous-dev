#!/usr/bin/env python3
"""
Sync Dispatcher Models - Data structures and exceptions

This module contains the data models and exception hierarchy for sync operations.

Models:
- SyncResult: Result of a sync operation with detailed information
- SyncDispatcherError: Exception for sync dispatcher errors
- SyncError: Alias for SyncDispatcherError (test compatibility)

Design Patterns:
    See library-design-patterns skill for standardized design patterns.
"""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    # Import types for type hints without creating circular imports
    from plugins.autonomous_dev.lib.sync_mode_detector import SyncMode
    from plugins.autonomous_dev.lib.version_detector import VersionComparison
    from plugins.autonomous_dev.lib.orphan_file_cleaner import CleanupResult
    from plugins.autonomous_dev.lib.settings_merger import MergeResult
    from plugins.autonomous_dev.lib.sync_validator import SyncValidationResult
else:
    # Runtime imports with fallback
    try:
        from plugins.autonomous_dev.lib.sync_mode_detector import SyncMode
        from plugins.autonomous_dev.lib.version_detector import VersionComparison
        from plugins.autonomous_dev.lib.orphan_file_cleaner import CleanupResult
        from plugins.autonomous_dev.lib.settings_merger import MergeResult
        from plugins.autonomous_dev.lib.sync_validator import SyncValidationResult
    except ImportError:
        # Fallback for installed environment (.claude/lib/)
        from sync_mode_detector import SyncMode  # type: ignore
        from version_detector import VersionComparison  # type: ignore
        from orphan_file_cleaner import CleanupResult  # type: ignore
        from settings_merger import MergeResult  # type: ignore
        try:
            from sync_validator import SyncValidationResult  # type: ignore
        except ImportError:
            SyncValidationResult = None  # type: ignore


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
        files_removed: Number of files removed (uninstall mode only)
        files_to_remove: Number of files to remove (uninstall preview only)
        total_size_bytes: Total size of files removed/to remove (uninstall only)
        backup_path: Path to backup file (uninstall only)
        dry_run: Whether this was a dry-run preview (uninstall only)
        errors: List of errors (uninstall only)
    """

    success: bool
    mode: "SyncMode"
    message: str
    details: Dict[str, Any] = field(default_factory=dict)
    error: Optional[str] = None
    version_comparison: Optional["VersionComparison"] = None
    orphan_cleanup: Optional["CleanupResult"] = None
    settings_merged: Optional["MergeResult"] = None
    validation: Optional["SyncValidationResult"] = None  # Post-sync validation results
    # Uninstall-specific fields
    files_removed: int = 0
    files_to_remove: int = 0
    total_size_bytes: int = 0
    backup_path: Optional[Path] = None
    dry_run: bool = False
    errors: List[str] = field(default_factory=list)

    @property
    def status(self) -> str:
        """Map success boolean to status string for compatibility.

        Returns:
            "success" if operation succeeded, "failure" otherwise
        """
        return "success" if self.success else "failure"

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
                if vc.status == "UPGRADE_AVAILABLE":
                    parts.append(f"Version upgrade: {vc.project_version} → {vc.marketplace_version}")
                elif vc.status == "DOWNGRADE_RISK":
                    parts.append(f"Downgrade risk: {vc.project_version} → {vc.marketplace_version}")
                elif vc.status == "UP_TO_DATE":
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

        # Add validation information
        if self.validation:
            v = self.validation
            if v.overall_passed:
                parts.append("Validation: PASSED")
            else:
                parts.append(f"Validation: {v.total_errors} errors, {v.total_warnings} warnings")
            if v.total_auto_fixed > 0:
                parts.append(f"Auto-fixed: {v.total_auto_fixed}")

        return " | ".join(parts)


# Exception hierarchy pattern from error-handling-patterns skill:
# BaseException -> Exception -> AutonomousDevError -> DomainError(BaseException) -> SpecificError
class SyncDispatcherError(Exception):
    """Exception raised for sync dispatcher errors."""

    pass


# Alias for test compatibility
SyncError = SyncDispatcherError
