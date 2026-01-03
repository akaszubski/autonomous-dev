#!/usr/bin/env python3
"""
CLAUDE.md Updater - Auto-inject autonomous-dev documentation into user's CLAUDE.md

This library provides safe, idempotent injection of autonomous-dev documentation
into user project CLAUDE.md files during install and setup. All operations include
security validation, atomic writes, and backup/rollback capabilities.

Problem:
- Users don't know plugin is installed (no CLAUDE.md reference)
- Manual documentation updates error-prone and forgotten
- No idempotent section injection mechanism
- install.sh and setup wizard don't modify CLAUDE.md

Solution:
- section_exists() - Check for BEGIN/END markers
- inject_section() - Add section idempotently (no duplicates)
- update_section() - Replace existing section content
- remove_section() - Remove section cleanly
- _create_backup() - Timestamped backups in ~/.autonomous-dev/backups/
- _atomic_write() - Safe write using mkstemp + rename pattern

Security Features (CWE-59, CWE-22):
- Symlink attack prevention
- Path traversal prevention
- Atomic write pattern (crash-safe)
- Backup before modification
- Path validation on init

Markers:
    <!-- BEGIN autonomous-dev -->
    ...content...
    <!-- END autonomous-dev -->

Usage:
    from claude_md_updater import ClaudeMdUpdater

    updater = ClaudeMdUpdater(Path("CLAUDE.md"))

    # Check if section exists
    if not updater.section_exists():
        updater.inject_section(template_content)

    # Update existing section
    if updater.section_exists():
        updater.update_section(new_content)

    # Remove section
    updater.remove_section()

Date: 2026-01-03
Feature: Auto-add autonomous-dev section to CLAUDE.md during install and setup
Agent: implementer
Phase: TDD GREEN (make tests pass)

Design Patterns:
    See library-design-patterns skill for two-tier CLI design pattern.
    See testing-guide skill for TDD methodology and test patterns.
    See error-handling-patterns skill for exception hierarchy.
    See security-patterns skill for security validation patterns.
"""

import os
import re
import sys
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Optional

# Import shared security utilities
# Handle both module import (from package) and direct script execution
try:
    from .security_utils import validate_path, audit_log
except ImportError:
    # Direct script execution - add lib dir to path
    lib_dir = Path(__file__).parent.resolve()
    sys.path.insert(0, str(lib_dir))
    from security_utils import validate_path, audit_log


# ============================================================================
# EXCEPTIONS
# ============================================================================


class ClaudeMdUpdaterError(Exception):
    """Base exception for ClaudeMdUpdater errors.

    See error-handling-patterns skill for exception hierarchy patterns.
    """
    pass


class SecurityValidationError(ClaudeMdUpdaterError):
    """Security validation failed (symlinks, path traversal, etc.).

    Raised when path validation fails due to security constraints:
    - Symlink detected (CWE-59)
    - Path traversal attempt (CWE-22)
    - Path outside allowed boundaries
    """
    pass


class MarkerCorruptionError(ClaudeMdUpdaterError):
    """BEGIN/END markers are corrupted or inconsistent.

    Raised when:
    - Multiple BEGIN markers found
    - BEGIN without END or END without BEGIN
    - Nested markers detected
    """
    pass


# ============================================================================
# CLAUDE.MD UPDATER CLASS
# ============================================================================


class ClaudeMdUpdater:
    """Safe, idempotent updater for CLAUDE.md autonomous-dev section.

    This class provides methods to inject, update, and remove autonomous-dev
    documentation sections in user CLAUDE.md files with security validation
    and atomic write guarantees.

    Security:
    - Path validation using shared security_utils
    - Symlink rejection (CWE-59)
    - Path traversal prevention (CWE-22)
    - Atomic writes (crash-safe)
    - Timestamped backups before modifications

    Attributes:
        claude_md_path: Validated absolute path to CLAUDE.md
        backup_file: Path to most recent backup (set after backup creation)
    """

    def __init__(self, claude_md_path: Path):
        """Initialize updater with security validation.

        Args:
            claude_md_path: Path to CLAUDE.md file

        Raises:
            SecurityValidationError: If path is symlink, outside project, or invalid

        Security:
            Uses shared security_utils.validate_path() for consistent validation.
            Creates empty CLAUDE.md if it doesn't exist (allows setup workflow).
        """
        # Convert to Path if string
        if isinstance(claude_md_path, str):
            claude_md_path = Path(claude_md_path)

        # SECURITY: Validate path using shared validation module
        # allow_missing=True because we'll create CLAUDE.md if it doesn't exist
        try:
            resolved_path = validate_path(
                claude_md_path,
                purpose="CLAUDE.md update",
                allow_missing=True
            )
        except ValueError as e:
            # Convert ValueError to SecurityValidationError for consistency
            raise SecurityValidationError(str(e)) from e

        self.claude_md_path = resolved_path
        # Keep original path's parent for mkstemp (avoids /var vs /private/var mismatch on macOS)
        self._mkstemp_dir = str(claude_md_path.parent)
        self.backup_file: Optional[Path] = None

        # Create empty CLAUDE.md if it doesn't exist
        if not self.claude_md_path.exists():
            self.claude_md_path.write_text("")
            audit_log("claude_md_updater", "success", {
                "operation": "create_empty_claude_md",
                "path": str(self.claude_md_path)
            })

        # Audit log initialization
        audit_log("claude_md_updater", "initialized", {
            "operation": "init",
            "claude_md_path": str(self.claude_md_path),
            "mkstemp_dir": self._mkstemp_dir
        })

    def section_exists(self, marker: str = "autonomous-dev") -> bool:
        """Check if autonomous-dev section exists via BEGIN/END markers.

        Args:
            marker: Section marker name (default: "autonomous-dev")

        Returns:
            True if both BEGIN and END markers present, False otherwise

        Note:
            Requires BOTH markers to return True. If only one marker present,
            returns False (incomplete/corrupted section).
        """
        content = self.claude_md_path.read_text()

        begin_marker = f"<!-- BEGIN {marker} -->"
        end_marker = f"<!-- END {marker} -->"

        has_begin = begin_marker in content
        has_end = end_marker in content

        # Both markers must be present for section to exist
        return has_begin and has_end

    def inject_section(self, content: str, marker: str = "autonomous-dev") -> bool:
        """Add section idempotently (no duplicates).

        Args:
            content: Section content to inject (without markers)
            marker: Section marker name (default: "autonomous-dev")

        Returns:
            True if section was added, False if already exists

        Behavior:
            - If section exists: Returns False, no changes made
            - If section missing: Appends section to end of file with markers
            - Creates backup before modification
            - Uses atomic write for crash-safety

        Section Format:
            <!-- BEGIN autonomous-dev -->
            {content}
            <!-- END autonomous-dev -->
        """
        # Check if section already exists (idempotent)
        if self.section_exists(marker):
            audit_log("claude_md_updater", "skip", {
                "operation": "inject_section",
                "reason": "section_already_exists",
                "marker": marker
            })
            return False

        # Create backup before modification
        self._create_backup()

        # Read current content
        current_content = self.claude_md_path.read_text()

        # Build section with markers
        begin_marker = f"<!-- BEGIN {marker} -->"
        end_marker = f"<!-- END {marker} -->"

        # If file is empty, start at beginning without leading newline
        if not current_content or current_content.isspace():
            new_content = f"{begin_marker}\n{content}\n{end_marker}\n"
        else:
            # Otherwise append with separator
            section = f"\n{begin_marker}\n{content}\n{end_marker}\n"
            new_content = current_content.rstrip() + "\n" + section

        # Atomic write
        self._atomic_write(new_content)

        audit_log("claude_md_updater", "success", {
            "operation": "inject_section",
            "marker": marker,
            "path": str(self.claude_md_path)
        })

        return True

    def update_section(self, content: str, marker: str = "autonomous-dev") -> bool:
        """Replace existing section content.

        Args:
            content: New section content (without markers)
            marker: Section marker name (default: "autonomous-dev")

        Returns:
            True if section was updated, False if section doesn't exist

        Raises:
            MarkerCorruptionError: If markers are corrupted (multiple BEGIN/END pairs)

        Behavior:
            - If section missing: Returns False, no changes made
            - If section exists: Replaces content between markers
            - Preserves surrounding content
            - Creates backup before modification
            - Uses atomic write for crash-safety
        """
        # Check if section exists
        if not self.section_exists(marker):
            audit_log("claude_md_updater", "skip", {
                "operation": "update_section",
                "reason": "section_not_found",
                "marker": marker
            })
            return False

        # Read current content
        current_content = self.claude_md_path.read_text()

        # Validate markers aren't corrupted (multiple pairs)
        begin_marker = f"<!-- BEGIN {marker} -->"
        end_marker = f"<!-- END {marker} -->"

        begin_count = current_content.count(begin_marker)
        end_count = current_content.count(end_marker)

        if begin_count > 1 or end_count > 1:
            audit_log("claude_md_updater", "failure", {
                "operation": "update_section",
                "reason": "corrupted_markers",
                "marker": marker,
                "begin_count": begin_count,
                "end_count": end_count
            })
            raise MarkerCorruptionError(
                f"Corrupted markers in CLAUDE.md: {self.claude_md_path}\n"
                f"Found {begin_count} BEGIN markers and {end_count} END markers\n"
                f"Expected: Exactly 1 of each\n"
                f"Manual intervention required to fix CLAUDE.md"
            )

        # Create backup before modification
        self._create_backup()

        # Replace content between markers using regex
        pattern = re.compile(
            f"{re.escape(begin_marker)}.*?{re.escape(end_marker)}",
            re.DOTALL
        )

        new_section = f"{begin_marker}\n{content}\n{end_marker}"
        new_content = pattern.sub(new_section, current_content)

        # Atomic write
        self._atomic_write(new_content)

        audit_log("claude_md_updater", "success", {
            "operation": "update_section",
            "marker": marker,
            "path": str(self.claude_md_path)
        })

        return True

    def remove_section(self, marker: str = "autonomous-dev") -> bool:
        """Remove section cleanly (including markers).

        Args:
            marker: Section marker name (default: "autonomous-dev")

        Returns:
            True if section was removed, False if section doesn't exist

        Behavior:
            - If section missing: Returns False, no changes made
            - If section exists: Removes entire section including markers
            - Preserves surrounding content
            - Cleans up excessive newlines (no triple blank lines)
            - Creates backup before modification
            - Uses atomic write for crash-safety
        """
        # Check if section exists
        if not self.section_exists(marker):
            audit_log("claude_md_updater", "skip", {
                "operation": "remove_section",
                "reason": "section_not_found",
                "marker": marker
            })
            return False

        # Create backup before modification
        self._create_backup()

        # Read current content
        current_content = self.claude_md_path.read_text()

        # Remove section using regex
        begin_marker = f"<!-- BEGIN {marker} -->"
        end_marker = f"<!-- END {marker} -->"

        pattern = re.compile(
            f"\n?{re.escape(begin_marker)}.*?{re.escape(end_marker)}\n?",
            re.DOTALL
        )

        new_content = pattern.sub("", current_content)

        # Clean up excessive newlines (no more than 3 consecutive)
        new_content = re.sub(r'\n{4,}', '\n\n\n', new_content)

        # Atomic write
        self._atomic_write(new_content)

        audit_log("claude_md_updater", "success", {
            "operation": "remove_section",
            "marker": marker,
            "path": str(self.claude_md_path)
        })

        return True

    def _create_backup(self) -> Path:
        """Create timestamped backup in ~/.autonomous-dev/backups/.

        Returns:
            Path to backup file

        Format:
            ~/.autonomous-dev/backups/CLAUDE.md.backup.YYYYMMDD-HHMMSS.MMMMMM

        Raises:
            FileNotFoundError: If CLAUDE.md doesn't exist
            ClaudeMdUpdaterError: If backup creation fails or file is read-only
        """
        if not self.claude_md_path.exists():
            raise FileNotFoundError(
                f"CLAUDE.md not found: {self.claude_md_path}\n"
                f"Cannot create backup of non-existent file"
            )

        # Check if file is writable (will fail later in atomic_write if not)
        if not os.access(self.claude_md_path, os.W_OK):
            raise ClaudeMdUpdaterError(
                f"Permission denied: CLAUDE.md is read-only\n"
                f"Path: {self.claude_md_path}\n"
                f"Cannot modify read-only file. Run: chmod u+w CLAUDE.md"
            )

        # Create backup directory
        backup_dir = Path.home() / ".autonomous-dev" / "backups"
        backup_dir.mkdir(parents=True, exist_ok=True)

        # Generate timestamped backup filename (with microseconds for uniqueness)
        now = datetime.now()
        timestamp = now.strftime("%Y%m%d-%H%M%S")
        microseconds = str(now.microsecond).zfill(6)
        backup_filename = f"CLAUDE.md.backup.{timestamp}.{microseconds}"
        backup_path = backup_dir / backup_filename

        # Copy content to backup
        try:
            content = self.claude_md_path.read_text()
            backup_path.write_text(content)
        except (OSError, IOError) as e:
            raise ClaudeMdUpdaterError(
                f"Failed to create backup: {backup_path}\n"
                f"Error: {e}"
            ) from e

        self.backup_file = backup_path

        audit_log("claude_md_updater", "success", {
            "operation": "create_backup",
            "source": str(self.claude_md_path),
            "backup": str(backup_path)
        })

        return backup_path

    def _atomic_write(self, content: str) -> None:
        """Atomically write content using mkstemp + rename pattern.

        Args:
            content: New content to write

        Raises:
            ClaudeMdUpdaterError: If write or rename fails

        Security Rationale:
        ==================
        Uses tempfile.mkstemp() instead of PID-based naming to prevent
        race condition vulnerabilities (see project_md_updater.py for details).

        Atomic Write Pattern:
        ====================
        1. CREATE: mkstemp() creates temp file with random name in same directory
        2. WRITE: Content written via os.write(fd, ...) for atomicity
        3. CLOSE: File descriptor closed before rename
        4. RENAME: temp_path.replace(target) atomically updates file

        Failure Safety:
        ==============
        - Process crash before rename: Original file unchanged
        - Write error: Temp file cleaned up, FD closed
        - Rename error: Temp file cleaned up
        """
        temp_fd = None
        temp_path = None

        try:
            # Get original permissions (or default to 0o644)
            try:
                original_mode = self.claude_md_path.stat().st_mode & 0o777
            except FileNotFoundError:
                original_mode = 0o644

            # Create temp file in same directory as target (ensures same filesystem)
            # mkstemp() returns (fd, path) with:
            # - Unique filename (includes random suffix)
            # - Exclusive access (fd is open, file exists)
            # - Mode 0600 (readable/writable by owner only)
            temp_fd, temp_path_str = tempfile.mkstemp(
                dir=self._mkstemp_dir,
                prefix='.CLAUDE.',
                suffix='.tmp',
                text=False  # Binary mode for cross-platform compatibility
            )
            temp_path = Path(temp_path_str)

            # Write content via file descriptor for atomic operation
            os.write(temp_fd, content.encode('utf-8'))

            # Close FD before rename (required for Windows, good practice for POSIX)
            os.close(temp_fd)
            temp_fd = None  # Mark as closed to prevent double-close

            # Set original permissions on temp file (only if file exists)
            if temp_path.exists():
                os.chmod(temp_path, original_mode)

            # Atomic rename (POSIX guarantees atomicity)
            temp_path.replace(self.claude_md_path)

            audit_log("claude_md_updater", "success", {
                "operation": "atomic_write",
                "target_file": str(self.claude_md_path),
                "temp_file": temp_path_str
            })

        except (OSError, IOError) as e:
            # Clean up temp file on error
            if temp_fd is not None:
                try:
                    os.close(temp_fd)
                except OSError:
                    pass  # Already closed or error closing

            if temp_path is not None and temp_path.exists():
                try:
                    temp_path.unlink()
                except OSError:
                    pass  # Couldn't delete temp file

            audit_log("claude_md_updater", "failure", {
                "operation": "atomic_write",
                "target_file": str(self.claude_md_path),
                "error": str(e)
            })

            # Provide user-friendly error message
            if "No space left on device" in str(e) or e.errno == 28:
                raise ClaudeMdUpdaterError(
                    f"Disk full: Cannot write to CLAUDE.md\n"
                    f"Path: {self.claude_md_path}\n"
                    f"Free up disk space and try again"
                ) from e
            elif "Permission denied" in str(e) or "Read-only" in str(e):
                raise ClaudeMdUpdaterError(
                    f"Permission denied: Cannot write to CLAUDE.md\n"
                    f"Path: {self.claude_md_path}\n"
                    f"Check file permissions (should be writable)"
                ) from e
            else:
                raise ClaudeMdUpdaterError(
                    f"Failed to write CLAUDE.md: {self.claude_md_path}\n"
                    f"Error: {e}"
                ) from e


# ============================================================================
# MAIN (for testing)
# ============================================================================


if __name__ == "__main__":
    import sys

    if len(sys.argv) < 2:
        print("Usage: python claude_md_updater.py <claude_md_path>")
        sys.exit(1)

    claude_md = Path(sys.argv[1])
    updater = ClaudeMdUpdater(claude_md)

    print(f"CLAUDE.md: {updater.claude_md_path}")
    print(f"Section exists: {updater.section_exists()}")
