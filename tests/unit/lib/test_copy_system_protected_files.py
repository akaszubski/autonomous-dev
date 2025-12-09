#!/usr/bin/env python3
"""
Unit tests for CopySystem protected file handling (TDD Red Phase - Issue #106).

Tests for enhanced CopySystem with protected file support.

TDD Mode: These tests are written BEFORE implementation.
All tests should FAIL initially because protected file features don't exist yet.

Test Strategy:
- Skip protected files during copy
- Create backups for conflicts
- Report skipped/backed-up files
- Preserve existing protected files

Date: 2025-12-09
Issue: #106 (GenAI-first installation system)
Agent: test-master
Phase: TDD Red (tests written BEFORE implementation)
"""

import os
import sys
import pytest
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock
import shutil

# Add lib directory to path for imports
sys.path.insert(
    0,
    str(
        Path(__file__).parent.parent.parent.parent
        / "plugins"
        / "autonomous-dev"
        / "lib"
    ),
)

# Import existing CopySystem
try:
    from copy_system import CopySystem
except ImportError as e:
    pytest.skip(f"CopySystem not found: {e}", allow_module_level=True)


class TestProtectedFileSkipping:
    """Test skipping protected files during copy."""

    def test_skip_protected_files_during_copy(self, tmp_path):
        """Test that protected files are skipped during copy.

        Current: FAILS - Protected file feature doesn't exist
        """
        source_dir = tmp_path / "source"
        source_dir.mkdir()
        dest_dir = tmp_path / "dest"
        dest_dir.mkdir()

        # Create files in source
        (source_dir / "copy_me.py").write_text("copy this")
        (source_dir / "PROJECT.md").write_text("plugin template")

        # Create existing protected file in dest
        (dest_dir / "PROJECT.md").write_text("user's project")

        # Mark PROJECT.md as protected
        protected_files = [".claude/PROJECT.md"]

        copier = CopySystem(source_dir, dest_dir)
        result = copier.copy_all(protected_files=protected_files)

        # Should copy copy_me.py but skip PROJECT.md
        assert (dest_dir / "copy_me.py").exists()
        assert (dest_dir / "PROJECT.md").read_text() == "user's project"
        assert result["files_skipped"] == 1

    def test_skip_multiple_protected_files(self, tmp_path):
        """Test skipping multiple protected files.

        Current: FAILS - Protected file feature doesn't exist
        """
        source_dir = tmp_path / "source"
        source_dir.mkdir()
        dest_dir = tmp_path / "dest"
        dest_dir.mkdir()

        # Create files
        (source_dir / "copy.py").write_text("copy")
        (source_dir / "PROJECT.md").write_text("template")
        (source_dir / ".env").write_text("template env")

        # Existing protected files
        (dest_dir / "PROJECT.md").write_text("user project")
        (dest_dir / ".env").write_text("user env")

        protected_files = ["PROJECT.md", ".env"]

        copier = CopySystem(source_dir, dest_dir)
        result = copier.copy_all(protected_files=protected_files)

        assert result["files_skipped"] == 2
        assert (dest_dir / ".env").read_text() == "user env"

    def test_skip_protected_files_in_subdirectories(self, tmp_path):
        """Test skipping protected files in nested directories.

        Current: FAILS - Protected file feature doesn't exist
        """
        source_dir = tmp_path / "source"
        source_dir.mkdir()
        dest_dir = tmp_path / "dest"
        dest_dir.mkdir()

        # Create nested structure
        (source_dir / "hooks").mkdir()
        (source_dir / "hooks" / "custom.py").write_text("plugin default")
        (source_dir / "hooks" / "auto_format.py").write_text("new version")

        (dest_dir / "hooks").mkdir()
        (dest_dir / "hooks" / "custom.py").write_text("user custom")

        protected_files = ["hooks/custom.py"]

        copier = CopySystem(source_dir, dest_dir)
        result = copier.copy_all(protected_files=protected_files)

        # custom.py should be preserved
        assert (dest_dir / "hooks" / "custom.py").read_text() == "user custom"
        # auto_format.py should be copied
        assert (dest_dir / "hooks" / "auto_format.py").exists()

    def test_report_skipped_files(self, tmp_path):
        """Test that skipped files are reported.

        Current: FAILS - Protected file feature doesn't exist
        """
        source_dir = tmp_path / "source"
        source_dir.mkdir()
        dest_dir = tmp_path / "dest"
        dest_dir.mkdir()

        (source_dir / "file.py").write_text("source")
        (dest_dir / "file.py").write_text("dest")

        protected_files = ["file.py"]

        copier = CopySystem(source_dir, dest_dir)
        result = copier.copy_all(protected_files=protected_files)

        assert "skipped_files" in result
        assert "file.py" in result["skipped_files"]


class TestBackupCreation:
    """Test backup creation for conflict resolution."""

    def test_create_backup_for_conflicting_file(self, tmp_path):
        """Test creating backup when file conflicts.

        Current: FAILS - Backup feature doesn't exist
        """
        source_dir = tmp_path / "source"
        source_dir.mkdir()
        dest_dir = tmp_path / "dest"
        dest_dir.mkdir()

        # Create conflicting file
        (source_dir / "file.py").write_text("new version")
        (dest_dir / "file.py").write_text("old version")

        copier = CopySystem(source_dir, dest_dir)
        result = copier.copy_all(backup_conflicts=True)

        # Original should be backed up
        backup_file = dest_dir / "file.py.backup"
        assert backup_file.exists()
        assert backup_file.read_text() == "old version"

        # New version should be copied
        assert (dest_dir / "file.py").read_text() == "new version"

    def test_backup_with_timestamp(self, tmp_path):
        """Test that backups include timestamp.

        Current: FAILS - Backup feature doesn't exist
        """
        source_dir = tmp_path / "source"
        source_dir.mkdir()
        dest_dir = tmp_path / "dest"
        dest_dir.mkdir()

        (source_dir / "file.py").write_text("new")
        (dest_dir / "file.py").write_text("old")

        copier = CopySystem(source_dir, dest_dir)
        result = copier.copy_all(backup_conflicts=True, backup_timestamp=True)

        # Should have backup with timestamp
        backups = list(dest_dir.glob("file.py.backup.*"))
        assert len(backups) == 1

    def test_create_multiple_backups(self, tmp_path):
        """Test creating backups for multiple conflicts.

        Current: FAILS - Backup feature doesn't exist
        """
        source_dir = tmp_path / "source"
        source_dir.mkdir()
        dest_dir = tmp_path / "dest"
        dest_dir.mkdir()

        # Create multiple conflicts
        for i in range(3):
            (source_dir / f"file{i}.py").write_text(f"new{i}")
            (dest_dir / f"file{i}.py").write_text(f"old{i}")

        copier = CopySystem(source_dir, dest_dir)
        result = copier.copy_all(backup_conflicts=True)

        # All should be backed up
        assert len(result["backed_up_files"]) == 3
        for i in range(3):
            backup = dest_dir / f"file{i}.py.backup"
            assert backup.exists()

    def test_backup_preserves_permissions(self, tmp_path):
        """Test that backups preserve file permissions.

        Current: FAILS - Backup feature doesn't exist
        """
        source_dir = tmp_path / "source"
        source_dir.mkdir()
        dest_dir = tmp_path / "dest"
        dest_dir.mkdir()

        # Create executable file
        orig_file = dest_dir / "script.py"
        orig_file.write_text("old")
        orig_file.chmod(0o755)

        (source_dir / "script.py").write_text("new")

        copier = CopySystem(source_dir, dest_dir)
        result = copier.copy_all(backup_conflicts=True)

        # Backup should preserve executable permission
        backup = dest_dir / "script.py.backup"
        assert backup.stat().st_mode & 0o111  # Check executable bit


class TestConflictResolutionStrategies:
    """Test different conflict resolution strategies."""

    def test_strategy_skip_conflicts(self, tmp_path):
        """Test skip strategy (don't overwrite, don't backup).

        Current: FAILS - Strategy feature doesn't exist
        """
        source_dir = tmp_path / "source"
        source_dir.mkdir()
        dest_dir = tmp_path / "dest"
        dest_dir.mkdir()

        (source_dir / "file.py").write_text("new")
        (dest_dir / "file.py").write_text("old")

        copier = CopySystem(source_dir, dest_dir)
        result = copier.copy_all(conflict_strategy="skip")

        # Original should be unchanged
        assert (dest_dir / "file.py").read_text() == "old"
        assert result["files_skipped"] == 1

    def test_strategy_overwrite_conflicts(self, tmp_path):
        """Test overwrite strategy (replace without backup).

        Current: FAILS - Strategy feature doesn't exist
        """
        source_dir = tmp_path / "source"
        source_dir.mkdir()
        dest_dir = tmp_path / "dest"
        dest_dir.mkdir()

        (source_dir / "file.py").write_text("new")
        (dest_dir / "file.py").write_text("old")

        copier = CopySystem(source_dir, dest_dir)
        result = copier.copy_all(conflict_strategy="overwrite")

        # Should overwrite without backup
        assert (dest_dir / "file.py").read_text() == "new"
        assert not (dest_dir / "file.py.backup").exists()

    def test_strategy_backup_conflicts(self, tmp_path):
        """Test backup strategy (backup then overwrite).

        Current: FAILS - Strategy feature doesn't exist
        """
        source_dir = tmp_path / "source"
        source_dir.mkdir()
        dest_dir = tmp_path / "dest"
        dest_dir.mkdir()

        (source_dir / "file.py").write_text("new")
        (dest_dir / "file.py").write_text("old")

        copier = CopySystem(source_dir, dest_dir)
        result = copier.copy_all(conflict_strategy="backup")

        # Should backup and overwrite
        assert (dest_dir / "file.py").read_text() == "new"
        assert (dest_dir / "file.py.backup").exists()


class TestProgressReporting:
    """Test progress reporting for protected file operations."""

    def test_progress_callback_includes_skipped_files(self, tmp_path):
        """Test that progress callback reports skipped files.

        Current: FAILS - Enhanced callback doesn't exist
        """
        source_dir = tmp_path / "source"
        source_dir.mkdir()
        dest_dir = tmp_path / "dest"
        dest_dir.mkdir()

        (source_dir / "file.py").write_text("source")
        (dest_dir / "file.py").write_text("dest")

        protected_files = ["file.py"]
        skipped = []

        def progress(current, total, file_path, action="copied"):
            if action == "skipped":
                skipped.append(file_path)

        copier = CopySystem(source_dir, dest_dir)
        result = copier.copy_all(
            protected_files=protected_files, progress_callback=progress
        )

        assert "file.py" in skipped

    def test_progress_callback_includes_backed_up_files(self, tmp_path):
        """Test that progress callback reports backed up files.

        Current: FAILS - Enhanced callback doesn't exist
        """
        source_dir = tmp_path / "source"
        source_dir.mkdir()
        dest_dir = tmp_path / "dest"
        dest_dir.mkdir()

        (source_dir / "file.py").write_text("new")
        (dest_dir / "file.py").write_text("old")

        backed_up = []

        def progress(current, total, file_path, action="copied"):
            if action == "backed_up":
                backed_up.append(file_path)

        copier = CopySystem(source_dir, dest_dir)
        result = copier.copy_all(
            backup_conflicts=True, progress_callback=progress
        )

        assert "file.py" in backed_up


class TestResultSummary:
    """Test comprehensive result summary."""

    def test_result_includes_all_statistics(self, tmp_path):
        """Test that result includes comprehensive statistics.

        Current: FAILS - Enhanced result doesn't exist
        """
        source_dir = tmp_path / "source"
        source_dir.mkdir()
        dest_dir = tmp_path / "dest"
        dest_dir.mkdir()

        # Create various scenarios
        (source_dir / "copied.py").write_text("copy")
        (source_dir / "skipped.py").write_text("skip")
        (source_dir / "backed_up.py").write_text("backup")

        (dest_dir / "skipped.py").write_text("existing")
        (dest_dir / "backed_up.py").write_text("old")

        protected_files = ["skipped.py"]

        copier = CopySystem(source_dir, dest_dir)
        result = copier.copy_all(
            protected_files=protected_files, backup_conflicts=True
        )

        # Check all statistics present
        assert "files_copied" in result
        assert "files_skipped" in result
        assert "files_backed_up" in result
        assert "skipped_files" in result
        assert "backed_up_files" in result

    def test_result_distinguishes_protected_vs_conflicted(self, tmp_path):
        """Test that result distinguishes protected vs conflicted files.

        Current: FAILS - Enhanced result doesn't exist
        """
        source_dir = tmp_path / "source"
        source_dir.mkdir()
        dest_dir = tmp_path / "dest"
        dest_dir.mkdir()

        # Protected file (user artifact)
        (source_dir / "PROJECT.md").write_text("template")
        (dest_dir / "PROJECT.md").write_text("user")

        # Conflicted file (modified plugin file)
        (source_dir / "hook.py").write_text("new")
        (dest_dir / "hook.py").write_text("modified")

        protected_files = ["PROJECT.md"]

        copier = CopySystem(source_dir, dest_dir)
        result = copier.copy_all(
            protected_files=protected_files, backup_conflicts=True
        )

        assert "PROJECT.md" in result["skipped_files"]
        assert "hook.py" in result["backed_up_files"]


class TestEdgeCases:
    """Test edge cases for protected file handling."""

    def test_handles_missing_protected_file_in_source(self, tmp_path):
        """Test handling when protected file doesn't exist in source.

        Current: FAILS - Enhanced handling doesn't exist
        """
        source_dir = tmp_path / "source"
        source_dir.mkdir()
        dest_dir = tmp_path / "dest"
        dest_dir.mkdir()

        # Protected file only in dest
        (dest_dir / "PROJECT.md").write_text("user")

        protected_files = ["PROJECT.md"]

        copier = CopySystem(source_dir, dest_dir)
        result = copier.copy_all(protected_files=protected_files)

        # Should not fail, just skip
        assert (dest_dir / "PROJECT.md").read_text() == "user"

    def test_handles_protected_directory(self, tmp_path):
        """Test handling protected directories.

        Current: FAILS - Directory protection doesn't exist
        """
        source_dir = tmp_path / "source"
        source_dir.mkdir()
        dest_dir = tmp_path / "dest"
        dest_dir.mkdir()

        # Create protected directory
        (source_dir / "custom").mkdir()
        (source_dir / "custom" / "file.py").write_text("source")

        (dest_dir / "custom").mkdir()
        (dest_dir / "custom" / "file.py").write_text("dest")

        protected_patterns = ["custom/**"]

        copier = CopySystem(source_dir, dest_dir)
        result = copier.copy_all(protected_patterns=protected_patterns)

        # Should preserve entire directory
        assert (dest_dir / "custom" / "file.py").read_text() == "dest"

    def test_handles_backup_name_collision(self, tmp_path):
        """Test handling when backup file name already exists.

        Current: FAILS - Collision handling doesn't exist
        """
        source_dir = tmp_path / "source"
        source_dir.mkdir()
        dest_dir = tmp_path / "dest"
        dest_dir.mkdir()

        (source_dir / "file.py").write_text("new")
        (dest_dir / "file.py").write_text("old")
        (dest_dir / "file.py.backup").write_text("previous backup")

        copier = CopySystem(source_dir, dest_dir)
        result = copier.copy_all(backup_conflicts=True)

        # Should create numbered backup
        backups = list(dest_dir.glob("file.py.backup*"))
        assert len(backups) >= 2

    def test_handles_readonly_protected_files(self, tmp_path):
        """Test handling readonly protected files.

        Current: FAILS - Permission handling doesn't exist
        """
        source_dir = tmp_path / "source"
        source_dir.mkdir()
        dest_dir = tmp_path / "dest"
        dest_dir.mkdir()

        (source_dir / "file.py").write_text("new")

        # Create readonly file
        readonly = dest_dir / "file.py"
        readonly.write_text("protected")
        readonly.chmod(0o444)

        protected_files = ["file.py"]

        copier = CopySystem(source_dir, dest_dir)
        result = copier.copy_all(protected_files=protected_files)

        # Should skip without error
        assert result["files_skipped"] == 1

        # Cleanup
        readonly.chmod(0o644)
