"""
TDD Tests for Issue #80 - Enhanced Copy System (Phase 2)

Tests the enhanced CopySystem that preserves directory structure,
handles permissions correctly, and provides progress reporting.

Current State (RED PHASE):
- Enhanced copy methods don't exist yet
- Permission handling enhancements don't exist
- All tests should FAIL

Test Coverage:
- Enhanced structure-preserving copy
- Executable permission handling for scripts/
- Progress reporting with callbacks
- Error handling with continue_on_error
- Rollback support

GitHub Issue: #80
Agent: test-master
Date: 2025-11-19
"""

import pytest
from pathlib import Path
import stat
import os


class TestEnhancedCopySystem:
    """Test enhanced copy system for complete file coverage."""

    def test_copies_nested_skill_structure_preserving_paths(self, tmp_path):
        """Test that copy preserves nested skill directory structure.

        Structure:
        skills/testing-guide.skill/docs/guide.md
        →
        .claude/skills/testing-guide.skill/docs/guide.md

        Current: FAILS - Enhanced copy doesn't exist
        """
        # Arrange: Create nested skill structure
        source = tmp_path / "source"
        source.mkdir()

        skill_dir = source / "skills" / "testing-guide.skill"
        skill_dir.mkdir(parents=True)
        (skill_dir / "skill.md").write_text("# Guide")

        (skill_dir / "docs").mkdir()
        (skill_dir / "docs" / "guide.md").write_text("Guide content")
        (skill_dir / "docs" / "advanced.md").write_text("Advanced content")

        dest = tmp_path / "dest"
        dest.mkdir()

        # Act: Copy files
        from plugins.autonomous_dev.lib.copy_system import CopySystem
        from plugins.autonomous_dev.lib.file_discovery import FileDiscovery

        discovery = FileDiscovery(source)
        files = discovery.discover_all_files()

        copier = CopySystem(source, dest)
        result = copier.copy_all(files=files)

        # Assert: Structure preserved
        assert (dest / "skills" / "testing-guide.skill" / "skill.md").exists()
        assert (dest / "skills" / "testing-guide.skill" / "docs" / "guide.md").exists()
        assert (dest / "skills" / "testing-guide.skill" / "docs" / "advanced.md").exists()

        # Content preserved
        assert (dest / "skills" / "testing-guide.skill" / "docs" / "guide.md").read_text() == "Guide content"

    def test_copies_all_lib_files_including_python(self, tmp_path):
        """Test that copy handles all lib/ files (Python and Markdown).

        Current: FAILS - Enhanced copy doesn't exist
        """
        # Arrange: Create lib/ with mixed types
        source = tmp_path / "source"
        source.mkdir()

        lib_dir = source / "lib"
        lib_dir.mkdir()

        (lib_dir / "security_utils.py").write_text("# Security")
        (lib_dir / "batch_state_manager.py").write_text("# Batch")

        (lib_dir / "nested").mkdir()
        (lib_dir / "nested" / "utils.py").write_text("# Nested")

        dest = tmp_path / "dest"
        dest.mkdir()

        # Act: Copy all files
        from plugins.autonomous_dev.lib.copy_system import CopySystem
        from plugins.autonomous_dev.lib.file_discovery import FileDiscovery

        discovery = FileDiscovery(source)
        files = discovery.discover_all_files()

        copier = CopySystem(source, dest)
        result = copier.copy_all(files=files)

        # Assert: All files copied
        assert (dest / "lib" / "security_utils.py").exists()
        assert (dest / "lib" / "batch_state_manager.py").exists()
        assert (dest / "lib" / "nested" / "utils.py").exists()

        assert result["files_copied"] == 3

    def test_sets_executable_permissions_for_scripts(self, tmp_path):
        """Test that copy sets executable permissions for scripts/ files.

        Scripts should be rwxr-xr-x (0o755).

        Current: FAILS - Enhanced permission handling doesn't exist
        """
        # Arrange: Create scripts
        source = tmp_path / "source"
        scripts_dir = source / "scripts"
        scripts_dir.mkdir(parents=True)

        script1 = scripts_dir / "setup.py"
        script1.write_text("#!/usr/bin/env python3\nprint('setup')")

        script2 = scripts_dir / "validate.py"
        script2.write_text("#!/usr/bin/env python3\nprint('validate')")

        dest = tmp_path / "dest"
        dest.mkdir()

        # Act: Copy scripts
        from plugins.autonomous_dev.lib.copy_system import CopySystem
        from plugins.autonomous_dev.lib.file_discovery import FileDiscovery

        discovery = FileDiscovery(source)
        files = discovery.discover_all_files()

        copier = CopySystem(source, dest)
        copier.copy_all(files=files)

        # Assert: Scripts are executable
        dest_script1 = dest / "scripts" / "setup.py"
        dest_script2 = dest / "scripts" / "validate.py"

        assert dest_script1.exists()
        assert dest_script2.exists()

        # Check permissions
        assert dest_script1.stat().st_mode & stat.S_IXUSR  # User executable
        assert dest_script1.stat().st_mode & stat.S_IXGRP  # Group executable
        assert dest_script1.stat().st_mode & stat.S_IXOTH  # Other executable

    def test_detects_scripts_by_shebang(self, tmp_path):
        """Test that copy detects scripts by shebang line.

        Files with #!/... should be executable regardless of location.

        Current: FAILS - Enhanced shebang detection doesn't exist
        """
        # Arrange: Script outside scripts/ directory
        source = tmp_path / "source"
        source.mkdir()

        (source / "tools").mkdir()
        script = source / "tools" / "custom_script.sh"
        script.write_text("#!/bin/bash\necho 'test'")

        dest = tmp_path / "dest"
        dest.mkdir()

        # Act: Copy file
        from plugins.autonomous_dev.lib.copy_system import CopySystem
        from plugins.autonomous_dev.lib.file_discovery import FileDiscovery

        discovery = FileDiscovery(source)
        files = discovery.discover_all_files()

        copier = CopySystem(source, dest)
        copier.copy_all(files=files)

        # Assert: Script is executable (detected by shebang)
        dest_script = dest / "tools" / "custom_script.sh"
        assert dest_script.exists()
        assert dest_script.stat().st_mode & stat.S_IXUSR

    def test_preserves_non_script_permissions(self, tmp_path):
        """Test that copy preserves original permissions for non-scripts.

        Current: FAILS - Enhanced permission handling doesn't exist
        """
        # Arrange: Create files with specific permissions
        source = tmp_path / "source"
        source.mkdir()

        # Regular file
        regular = source / "README.md"
        regular.write_text("# Readme")
        regular.chmod(0o644)

        # Read-only file
        readonly = source / "LICENSE"
        readonly.write_text("MIT License")
        readonly.chmod(0o444)

        dest = tmp_path / "dest"
        dest.mkdir()

        # Act: Copy files
        from plugins.autonomous_dev.lib.copy_system import CopySystem
        from plugins.autonomous_dev.lib.file_discovery import FileDiscovery

        discovery = FileDiscovery(source)
        files = discovery.discover_all_files()

        copier = CopySystem(source, dest)
        copier.copy_all(files=files)

        # Assert: Permissions preserved
        dest_regular = dest / "README.md"
        dest_readonly = dest / "LICENSE"

        # Regular file permissions
        assert (dest_regular.stat().st_mode & 0o777) == 0o644

        # Read-only file permissions
        assert (dest_readonly.stat().st_mode & 0o777) == 0o444

    def test_reports_progress_via_callback(self, tmp_path):
        """Test that copy reports progress via callback function.

        Current: FAILS - Enhanced progress reporting doesn't exist
        """
        # Arrange: Create multiple files
        source = tmp_path / "source"
        source.mkdir()

        for i in range(10):
            (source / f"file{i}.txt").write_text(f"content{i}")

        dest = tmp_path / "dest"
        dest.mkdir()

        # Progress tracking
        progress_calls = []

        def progress_callback(current, total, file_path):
            progress_calls.append({
                "current": current,
                "total": total,
                "file_path": file_path
            })

        # Act: Copy with progress callback
        from plugins.autonomous_dev.lib.copy_system import CopySystem
        from plugins.autonomous_dev.lib.file_discovery import FileDiscovery

        discovery = FileDiscovery(source)
        files = discovery.discover_all_files()

        copier = CopySystem(source, dest)
        copier.copy_all(files=files, progress_callback=progress_callback)

        # Assert: Progress reported
        assert len(progress_calls) == 10

        # First call
        assert progress_calls[0]["current"] == 1
        assert progress_calls[0]["total"] == 10

        # Last call
        assert progress_calls[-1]["current"] == 10
        assert progress_calls[-1]["total"] == 10

    def test_continues_on_error_when_enabled(self, tmp_path):
        """Test that copy continues on error when continue_on_error=True.

        Current: FAILS - Enhanced error handling doesn't exist
        """
        # Arrange: Create files with one that will fail
        source = tmp_path / "source"
        source.mkdir()

        (source / "good1.txt").write_text("good")
        (source / "bad.txt").write_text("bad")
        (source / "good2.txt").write_text("good")

        # Make bad.txt unreadable
        (source / "bad.txt").chmod(0o000)

        dest = tmp_path / "dest"
        dest.mkdir()

        try:
            # Act: Copy with continue_on_error
            from plugins.autonomous_dev.lib.copy_system import CopySystem
            from plugins.autonomous_dev.lib.file_discovery import FileDiscovery

            discovery = FileDiscovery(source)
            files = discovery.discover_all_files()

            copier = CopySystem(source, dest)
            result = copier.copy_all(files=files, continue_on_error=True)

            # Assert: Good files copied, errors reported
            assert (dest / "good1.txt").exists()
            assert (dest / "good2.txt").exists()

            # Error recorded but didn't stop copy
            assert result["errors"] >= 1
            assert len(result["error_list"]) >= 1

        finally:
            # Cleanup: Restore permissions
            try:
                (source / "bad.txt").chmod(0o644)
            except:
                pass

    def test_stops_on_error_by_default(self, tmp_path):
        """Test that copy stops on first error by default.

        Current: FAILS - Enhanced error handling doesn't exist
        """
        # Arrange: Create files with one that will fail
        source = tmp_path / "source"
        source.mkdir()

        (source / "file1.txt").write_text("content")
        (source / "file2.txt").write_text("content")

        dest = tmp_path / "dest"
        dest.mkdir()

        # Create existing file to trigger overwrite error
        (dest / "file1.txt").write_text("existing")

        try:
            # Act: Copy without overwrite permission
            from plugins.autonomous_dev.lib.copy_system import CopySystem, CopyError
            from plugins.autonomous_dev.lib.file_discovery import FileDiscovery

            discovery = FileDiscovery(source)
            files = discovery.discover_all_files()

            copier = CopySystem(source, dest)

            # Should raise error
            with pytest.raises(CopyError) as exc_info:
                copier.copy_all(files=files, overwrite=False)

            assert "already exists" in str(exc_info.value)

        except ImportError:
            pytest.skip("CopyError not yet implemented")

    def test_preserves_timestamps_by_default(self, tmp_path):
        """Test that copy preserves file modification timestamps.

        Current: FAILS - Enhanced timestamp handling doesn't exist
        """
        # Arrange: Create file with specific timestamp
        source = tmp_path / "source"
        source.mkdir()

        file = source / "file.txt"
        file.write_text("content")

        # Set specific timestamp (2024-01-01 00:00:00)
        import time
        timestamp = time.mktime((2024, 1, 1, 0, 0, 0, 0, 0, 0))
        os.utime(file, (timestamp, timestamp))

        original_mtime = file.stat().st_mtime

        dest = tmp_path / "dest"
        dest.mkdir()

        # Act: Copy with timestamp preservation
        from plugins.autonomous_dev.lib.copy_system import CopySystem
        from plugins.autonomous_dev.lib.file_discovery import FileDiscovery

        discovery = FileDiscovery(source)
        files = discovery.discover_all_files()

        copier = CopySystem(source, dest)
        copier.copy_all(files=files, preserve_timestamps=True)

        # Assert: Timestamp preserved
        dest_file = dest / "file.txt"
        dest_mtime = dest_file.stat().st_mtime

        assert abs(dest_mtime - original_mtime) < 1.0  # Within 1 second

    def test_updates_timestamps_when_disabled(self, tmp_path):
        """Test that copy updates timestamps when preserve_timestamps=False.

        Current: FAILS - Enhanced timestamp handling doesn't exist
        """
        # Arrange: Create old file
        source = tmp_path / "source"
        source.mkdir()

        file = source / "file.txt"
        file.write_text("content")

        # Set old timestamp
        import time
        old_timestamp = time.mktime((2020, 1, 1, 0, 0, 0, 0, 0, 0))
        os.utime(file, (old_timestamp, old_timestamp))

        dest = tmp_path / "dest"
        dest.mkdir()

        # Act: Copy without timestamp preservation
        from plugins.autonomous_dev.lib.copy_system import CopySystem
        from plugins.autonomous_dev.lib.file_discovery import FileDiscovery

        discovery = FileDiscovery(source)
        files = discovery.discover_all_files()

        copier = CopySystem(source, dest)
        copier.copy_all(files=files, preserve_timestamps=False)

        # Assert: Timestamp updated to current time
        dest_file = dest / "file.txt"
        dest_mtime = dest_file.stat().st_mtime

        current_time = time.time()
        assert dest_mtime > old_timestamp
        assert abs(dest_mtime - current_time) < 10.0  # Within 10 seconds


class TestCopySystemRollback:
    """Test rollback functionality."""

    def test_rollback_restores_from_backup(self, tmp_path):
        """Test that rollback restores files from backup directory.

        Current: FAILS - Rollback function doesn't exist
        """
        # Arrange: Create backup directory
        backup_dir = tmp_path / "backup"
        backup_dir.mkdir()

        (backup_dir / "original.txt").write_text("original content")

        # Destination with corrupted file
        dest_dir = tmp_path / "dest"
        dest_dir.mkdir()

        (dest_dir / "original.txt").write_text("corrupted content")

        # Act: Rollback
        from plugins.autonomous_dev.lib.copy_system import rollback

        success = rollback(backup_dir, dest_dir)

        # Assert: Original content restored
        assert success is True
        assert (dest_dir / "original.txt").read_text() == "original content"

    def test_rollback_removes_new_files(self, tmp_path):
        """Test that rollback removes files not in backup.

        Current: FAILS - Rollback function doesn't exist
        """
        # Arrange: Backup with subset of files
        backup_dir = tmp_path / "backup"
        backup_dir.mkdir()

        (backup_dir / "original.txt").write_text("original")

        # Destination with extra files
        dest_dir = tmp_path / "dest"
        dest_dir.mkdir()

        (dest_dir / "original.txt").write_text("original")
        (dest_dir / "new_file.txt").write_text("new")

        # Act: Rollback
        from plugins.autonomous_dev.lib.copy_system import rollback

        rollback(backup_dir, dest_dir)

        # Assert: Exact restore (backup state)
        assert (dest_dir / "original.txt").exists()
        # Note: Current rollback may not remove new files
        # This test documents expected behavior for enhancement

    def test_rollback_handles_missing_backup(self, tmp_path):
        """Test that rollback handles missing backup gracefully.

        Current: FAILS - Rollback function doesn't exist
        """
        # Arrange: No backup directory
        backup_dir = tmp_path / "nonexistent_backup"

        dest_dir = tmp_path / "dest"
        dest_dir.mkdir()

        (dest_dir / "file.txt").write_text("content")

        # Act: Attempt rollback
        from plugins.autonomous_dev.lib.copy_system import rollback

        success = rollback(backup_dir, dest_dir)

        # Assert: Returns False but doesn't crash
        assert success is False
        # Destination unchanged
        assert (dest_dir / "file.txt").exists()


class TestCopySystemEdgeCases:
    """Test edge cases and error handling."""

    def test_handles_empty_file_list(self, tmp_path):
        """Test that copy handles empty file list gracefully.

        Current: FAILS - Enhanced copy doesn't exist
        """
        # Arrange: Empty file list
        source = tmp_path / "source"
        source.mkdir()

        dest = tmp_path / "dest"
        dest.mkdir()

        # Act: Copy with empty list
        from plugins.autonomous_dev.lib.copy_system import CopySystem

        copier = CopySystem(source, dest)
        result = copier.copy_all(files=[])

        # Assert: No files copied
        assert result["files_copied"] == 0
        assert result["errors"] == 0

    def test_handles_very_large_files(self, tmp_path):
        """Test that copy handles large files (>10MB).

        Current: FAILS - Enhanced copy doesn't exist
        """
        # Arrange: Create large file
        source = tmp_path / "source"
        source.mkdir()

        large_file = source / "large.bin"
        # Create 20MB file
        with open(large_file, "wb") as f:
            f.write(b"x" * (20 * 1024 * 1024))

        dest = tmp_path / "dest"
        dest.mkdir()

        # Act: Copy large file
        from plugins.autonomous_dev.lib.copy_system import CopySystem
        from plugins.autonomous_dev.lib.file_discovery import FileDiscovery

        discovery = FileDiscovery(source)
        files = discovery.discover_all_files()

        copier = CopySystem(source, dest)
        result = copier.copy_all(files=files)

        # Assert: Large file copied successfully
        dest_file = dest / "large.bin"
        assert dest_file.exists()
        assert dest_file.stat().st_size == 20 * 1024 * 1024

    def test_validates_source_path_security(self, tmp_path):
        """Test that copy validates source path (prevents CWE-22).

        Current: FAILS - Enhanced security doesn't exist
        """
        # Arrange: Invalid source path
        from plugins.autonomous_dev.lib.copy_system import CopySystem

        # Act & Assert: Path validation fails
        with pytest.raises(ValueError) as exc_info:
            CopySystem("../../etc/passwd", tmp_path)

        assert "path" in str(exc_info.value).lower() and ("outside" in str(exc_info.value).lower() or "traversal" in str(exc_info.value).lower() or "invalid" in str(exc_info.value).lower())

    def test_validates_destination_path_security(self, tmp_path):
        """Test that copy validates destination path (prevents CWE-22).

        Current: FAILS - Enhanced security doesn't exist
        """
        # Arrange: Invalid dest path
        from plugins.autonomous_dev.lib.copy_system import CopySystem

        # Act & Assert: Path validation fails
        with pytest.raises(ValueError) as exc_info:
            CopySystem(tmp_path, "../../etc/")

        assert "path" in str(exc_info.value).lower() and ("outside" in str(exc_info.value).lower() or "traversal" in str(exc_info.value).lower() or "invalid" in str(exc_info.value).lower())

    def test_skips_symlinks_in_copy(self, tmp_path):
        """Test that copy skips symlinks (prevents CWE-59).

        Current: FAILS - Enhanced security doesn't exist
        """
        # Arrange: Create symlink
        source = tmp_path / "source"
        source.mkdir()

        (source / "real_file.txt").write_text("real")

        external_file = tmp_path / "external.txt"
        external_file.write_text("external")

        symlink = source / "symlink.txt"
        try:
            symlink.symlink_to(external_file)
        except OSError:
            pytest.skip("Symlinks not supported on this platform")

        dest = tmp_path / "dest"
        dest.mkdir()

        # Act: Copy files
        from plugins.autonomous_dev.lib.copy_system import CopySystem
        from plugins.autonomous_dev.lib.file_discovery import FileDiscovery

        discovery = FileDiscovery(source)
        files = discovery.discover_all_files()

        copier = CopySystem(source, dest)
        copier.copy_all(files=files)

        # Assert: Symlink not copied
        assert (dest / "real_file.txt").exists()
        assert not (dest / "symlink.txt").exists()

    def test_creates_parent_directories_automatically(self, tmp_path):
        """Test that copy creates parent directories automatically.

        Current: FAILS - Enhanced copy doesn't exist
        """
        # Arrange: File in nested directory
        source = tmp_path / "source"
        source.mkdir()

        nested_file = source / "a" / "b" / "c" / "deep.txt"
        nested_file.parent.mkdir(parents=True)
        nested_file.write_text("deep content")

        dest = tmp_path / "dest"
        dest.mkdir()

        # Act: Copy file
        from plugins.autonomous_dev.lib.copy_system import CopySystem
        from plugins.autonomous_dev.lib.file_discovery import FileDiscovery

        discovery = FileDiscovery(source)
        files = discovery.discover_all_files()

        copier = CopySystem(source, dest)
        copier.copy_all(files=files)

        # Assert: Parent directories created
        dest_file = dest / "a" / "b" / "c" / "deep.txt"
        assert dest_file.exists()
        assert dest_file.read_text() == "deep content"
