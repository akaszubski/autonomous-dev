#!/usr/bin/env python3
"""
Unit tests for StagingManager (TDD Red Phase - Issue #106).

Tests for GenAI-first installation system staging management.

TDD Mode: These tests are written BEFORE implementation.
All tests should FAIL initially because StagingManager doesn't exist yet.

Test Strategy:
- Staging directory validation
- File listing with metadata
- Conflict detection
- Cleanup operations
- Security validation

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
import tempfile
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

# Import will FAIL until implementation exists
try:
    from staging_manager import StagingManager
except ImportError as e:
    pytest.skip(f"Implementation not found: {e}", allow_module_level=True)


class TestStagingManagerInitialization:
    """Test StagingManager initialization and validation."""

    def test_initialize_with_valid_staging_directory(self, tmp_path):
        """Test initialization with valid staging directory.

        Current: FAILS - StagingManager doesn't exist
        """
        staging_dir = tmp_path / ".claude-staging"
        staging_dir.mkdir()

        manager = StagingManager(staging_dir)

        assert manager.staging_dir == staging_dir
        assert staging_dir.exists()

    def test_initialize_creates_staging_directory_if_not_exists(self, tmp_path):
        """Test that initialization creates staging directory.

        Current: FAILS - StagingManager doesn't exist
        """
        staging_dir = tmp_path / ".claude-staging"

        manager = StagingManager(staging_dir)

        assert staging_dir.exists()
        assert staging_dir.is_dir()

    def test_initialize_validates_staging_directory_permissions(self, tmp_path):
        """Test that initialization validates directory permissions.

        Current: FAILS - StagingManager doesn't exist
        """
        staging_dir = tmp_path / ".claude-staging"
        staging_dir.mkdir()
        staging_dir.chmod(0o755)

        manager = StagingManager(staging_dir)

        assert manager.is_secure()

    def test_initialize_rejects_non_directory_path(self, tmp_path):
        """Test that initialization rejects file paths.

        Current: FAILS - StagingManager doesn't exist
        """
        staging_file = tmp_path / "not-a-directory.txt"
        staging_file.touch()

        with pytest.raises(ValueError, match="must be a directory"):
            StagingManager(staging_file)

    def test_initialize_with_string_path(self, tmp_path):
        """Test initialization with string path (not Path object).

        Current: FAILS - StagingManager doesn't exist
        """
        staging_dir = tmp_path / ".claude-staging"
        staging_dir.mkdir()

        manager = StagingManager(str(staging_dir))

        assert manager.staging_dir == staging_dir


class TestStagingFileOperations:
    """Test staging file listing and metadata."""

    def test_list_files_returns_all_files_in_staging(self, tmp_path):
        """Test listing all files in staging directory.

        Current: FAILS - StagingManager doesn't exist
        """
        staging_dir = tmp_path / ".claude-staging"
        staging_dir.mkdir()

        # Create test files
        (staging_dir / "file1.py").write_text("content1")
        (staging_dir / "file2.md").write_text("content2")
        (staging_dir / "subdir").mkdir()
        (staging_dir / "subdir" / "file3.txt").write_text("content3")

        manager = StagingManager(staging_dir)
        files = manager.list_files()

        assert len(files) == 3
        assert any(f["path"] == "file1.py" for f in files)
        assert any(f["path"] == "file2.md" for f in files)
        assert any(f["path"] == "subdir/file3.txt" for f in files)

    def test_list_files_includes_metadata(self, tmp_path):
        """Test that file listing includes metadata (size, hash).

        Current: FAILS - StagingManager doesn't exist
        """
        staging_dir = tmp_path / ".claude-staging"
        staging_dir.mkdir()

        test_file = staging_dir / "test.py"
        test_content = "print('hello')"
        test_file.write_text(test_content)

        manager = StagingManager(staging_dir)
        files = manager.list_files()

        assert len(files) == 1
        file_info = files[0]
        assert file_info["path"] == "test.py"
        assert file_info["size"] == len(test_content)
        assert "hash" in file_info
        assert file_info["hash"] is not None

    def test_list_files_excludes_hidden_files(self, tmp_path):
        """Test that hidden files are excluded from listing.

        Current: FAILS - StagingManager doesn't exist
        """
        staging_dir = tmp_path / ".claude-staging"
        staging_dir.mkdir()

        (staging_dir / "visible.py").write_text("content")
        (staging_dir / ".hidden").write_text("secret")
        (staging_dir / ".DS_Store").write_text("mac")

        manager = StagingManager(staging_dir)
        files = manager.list_files()

        assert len(files) == 1
        assert files[0]["path"] == "visible.py"

    def test_list_files_empty_staging_directory(self, tmp_path):
        """Test listing files in empty staging directory.

        Current: FAILS - StagingManager doesn't exist
        """
        staging_dir = tmp_path / ".claude-staging"
        staging_dir.mkdir()

        manager = StagingManager(staging_dir)
        files = manager.list_files()

        assert files == []

    def test_get_file_hash(self, tmp_path):
        """Test getting file hash.

        Current: FAILS - StagingManager doesn't exist
        """
        staging_dir = tmp_path / ".claude-staging"
        staging_dir.mkdir()

        test_file = staging_dir / "test.py"
        test_file.write_text("content")

        manager = StagingManager(staging_dir)
        file_hash = manager.get_file_hash("test.py")

        assert file_hash is not None
        assert len(file_hash) == 64  # SHA256 hex digest


class TestConflictDetection:
    """Test conflict detection between staging and existing files."""

    def test_detect_conflicts_no_existing_files(self, tmp_path):
        """Test conflict detection when no existing files present.

        Current: FAILS - StagingManager doesn't exist
        """
        staging_dir = tmp_path / ".claude-staging"
        staging_dir.mkdir()
        target_dir = tmp_path / "target"
        target_dir.mkdir()

        (staging_dir / "new_file.py").write_text("content")

        manager = StagingManager(staging_dir)
        conflicts = manager.detect_conflicts(target_dir)

        assert len(conflicts) == 0

    def test_detect_conflicts_with_matching_files(self, tmp_path):
        """Test conflict detection with matching content.

        Current: FAILS - StagingManager doesn't exist
        """
        staging_dir = tmp_path / ".claude-staging"
        staging_dir.mkdir()
        target_dir = tmp_path / "target"
        target_dir.mkdir()

        # Same content in both locations
        content = "same content"
        (staging_dir / "file.py").write_text(content)
        (target_dir / "file.py").write_text(content)

        manager = StagingManager(staging_dir)
        conflicts = manager.detect_conflicts(target_dir)

        assert len(conflicts) == 0  # No conflict if content matches

    def test_detect_conflicts_with_different_content(self, tmp_path):
        """Test conflict detection with different content.

        Current: FAILS - StagingManager doesn't exist
        """
        staging_dir = tmp_path / ".claude-staging"
        staging_dir.mkdir()
        target_dir = tmp_path / "target"
        target_dir.mkdir()

        (staging_dir / "file.py").write_text("new content")
        (target_dir / "file.py").write_text("old content")

        manager = StagingManager(staging_dir)
        conflicts = manager.detect_conflicts(target_dir)

        assert len(conflicts) == 1
        assert conflicts[0]["file"] == "file.py"
        assert conflicts[0]["reason"] == "content_differs"

    def test_detect_conflicts_includes_file_metadata(self, tmp_path):
        """Test that conflict report includes file metadata.

        Current: FAILS - StagingManager doesn't exist
        """
        staging_dir = tmp_path / ".claude-staging"
        staging_dir.mkdir()
        target_dir = tmp_path / "target"
        target_dir.mkdir()

        (staging_dir / "file.py").write_text("new")
        (target_dir / "file.py").write_text("old")

        manager = StagingManager(staging_dir)
        conflicts = manager.detect_conflicts(target_dir)

        assert len(conflicts) == 1
        conflict = conflicts[0]
        assert "file" in conflict
        assert "reason" in conflict
        assert "staging_hash" in conflict
        assert "target_hash" in conflict

    def test_detect_conflicts_nested_files(self, tmp_path):
        """Test conflict detection with nested directory structure.

        Current: FAILS - StagingManager doesn't exist
        """
        staging_dir = tmp_path / ".claude-staging"
        staging_dir.mkdir()
        target_dir = tmp_path / "target"
        target_dir.mkdir()

        # Create nested structure
        (staging_dir / "subdir").mkdir()
        (staging_dir / "subdir" / "deep").mkdir()
        (staging_dir / "subdir" / "deep" / "file.py").write_text("new")

        (target_dir / "subdir").mkdir()
        (target_dir / "subdir" / "deep").mkdir()
        (target_dir / "subdir" / "deep" / "file.py").write_text("old")

        manager = StagingManager(staging_dir)
        conflicts = manager.detect_conflicts(target_dir)

        assert len(conflicts) == 1
        assert conflicts[0]["file"] == "subdir/deep/file.py"


class TestCleanupOperations:
    """Test staging directory cleanup."""

    def test_cleanup_removes_all_files(self, tmp_path):
        """Test that cleanup removes all staging files.

        Current: FAILS - StagingManager doesn't exist
        """
        staging_dir = tmp_path / ".claude-staging"
        staging_dir.mkdir()

        # Create files
        (staging_dir / "file1.py").write_text("content1")
        (staging_dir / "file2.md").write_text("content2")
        (staging_dir / "subdir").mkdir()
        (staging_dir / "subdir" / "file3.txt").write_text("content3")

        manager = StagingManager(staging_dir)
        manager.cleanup()

        assert not staging_dir.exists()

    def test_cleanup_is_idempotent(self, tmp_path):
        """Test that cleanup can be called multiple times safely.

        Current: FAILS - StagingManager doesn't exist
        """
        staging_dir = tmp_path / ".claude-staging"
        staging_dir.mkdir()

        manager = StagingManager(staging_dir)
        manager.cleanup()
        manager.cleanup()  # Should not raise

        assert not staging_dir.exists()

    def test_cleanup_preserves_parent_directory(self, tmp_path):
        """Test that cleanup only removes staging directory, not parent.

        Current: FAILS - StagingManager doesn't exist
        """
        staging_dir = tmp_path / ".claude-staging"
        staging_dir.mkdir()

        # Create sibling file
        sibling = tmp_path / "important.txt"
        sibling.write_text("keep me")

        manager = StagingManager(staging_dir)
        manager.cleanup()

        assert not staging_dir.exists()
        assert sibling.exists()

    def test_partial_cleanup_specific_files(self, tmp_path):
        """Test cleaning up specific files (not entire directory).

        Current: FAILS - StagingManager doesn't exist
        """
        staging_dir = tmp_path / ".claude-staging"
        staging_dir.mkdir()

        (staging_dir / "keep.py").write_text("keep")
        (staging_dir / "remove.py").write_text("remove")

        manager = StagingManager(staging_dir)
        manager.cleanup_files(["remove.py"])

        assert (staging_dir / "keep.py").exists()
        assert not (staging_dir / "remove.py").exists()


class TestSecurityValidation:
    """Test security validation for staging operations."""

    def test_validates_staging_directory_within_bounds(self, tmp_path):
        """Test that staging directory path is validated (CWE-22).

        Current: FAILS - StagingManager doesn't exist
        """
        staging_dir = tmp_path / ".claude-staging"
        staging_dir.mkdir()

        manager = StagingManager(staging_dir)

        # Should reject path traversal
        with pytest.raises(ValueError, match="path traversal"):
            manager.validate_path("../../../etc/passwd")

    def test_rejects_absolute_paths_outside_staging(self, tmp_path):
        """Test rejection of absolute paths outside staging.

        Current: FAILS - StagingManager doesn't exist
        """
        staging_dir = tmp_path / ".claude-staging"
        staging_dir.mkdir()

        manager = StagingManager(staging_dir)

        with pytest.raises(ValueError, match="outside staging"):
            manager.validate_path("/etc/passwd")

    def test_rejects_symlinks_outside_staging(self, tmp_path):
        """Test rejection of symlinks pointing outside staging (CWE-59).

        Current: FAILS - StagingManager doesn't exist
        """
        staging_dir = tmp_path / ".claude-staging"
        staging_dir.mkdir()

        # Create symlink to outside target
        target = tmp_path / "outside.txt"
        target.write_text("sensitive")
        symlink = staging_dir / "link.txt"
        symlink.symlink_to(target)

        manager = StagingManager(staging_dir)

        with pytest.raises(ValueError, match="symlink outside staging"):
            manager.validate_path("link.txt")

    def test_validates_file_names_no_special_characters(self, tmp_path):
        """Test validation of file names (prevents injection).

        Current: FAILS - StagingManager doesn't exist
        """
        staging_dir = tmp_path / ".claude-staging"
        staging_dir.mkdir()

        manager = StagingManager(staging_dir)

        dangerous_names = [
            "file; rm -rf /",
            "file$(whoami)",
            "file`ls`",
            "file|cat /etc/passwd",
        ]

        for name in dangerous_names:
            with pytest.raises(ValueError, match="invalid filename"):
                manager.validate_path(name)


class TestStagingManagerEdgeCases:
    """Test edge cases and error handling."""

    def test_handles_large_files(self, tmp_path):
        """Test handling files larger than memory buffer.

        Current: FAILS - StagingManager doesn't exist
        """
        staging_dir = tmp_path / ".claude-staging"
        staging_dir.mkdir()

        # Create 10MB file
        large_file = staging_dir / "large.bin"
        large_file.write_bytes(b"x" * (10 * 1024 * 1024))

        manager = StagingManager(staging_dir)
        file_hash = manager.get_file_hash("large.bin")

        assert file_hash is not None

    def test_handles_unicode_filenames(self, tmp_path):
        """Test handling files with unicode names.

        Current: FAILS - StagingManager doesn't exist
        """
        staging_dir = tmp_path / ".claude-staging"
        staging_dir.mkdir()

        unicode_file = staging_dir / "テスト.py"
        unicode_file.write_text("content")

        manager = StagingManager(staging_dir)
        files = manager.list_files()

        assert len(files) == 1
        assert files[0]["path"] == "テスト.py"

    def test_handles_readonly_files(self, tmp_path):
        """Test handling readonly files in staging.

        Current: FAILS - StagingManager doesn't exist
        """
        staging_dir = tmp_path / ".claude-staging"
        staging_dir.mkdir()

        readonly_file = staging_dir / "readonly.txt"
        readonly_file.write_text("content")
        readonly_file.chmod(0o444)

        manager = StagingManager(staging_dir)
        manager.cleanup()

        assert not staging_dir.exists()

    def test_handles_permission_errors(self, tmp_path):
        """Test handling permission errors during operations.

        Current: FAILS - StagingManager doesn't exist
        """
        staging_dir = tmp_path / ".claude-staging"
        staging_dir.mkdir()
        staging_dir.chmod(0o000)

        with pytest.raises(PermissionError):
            manager = StagingManager(staging_dir)
            manager.list_files()

        # Cleanup
        staging_dir.chmod(0o755)

    def test_thread_safety_concurrent_operations(self, tmp_path):
        """Test thread safety for concurrent staging operations.

        Current: FAILS - StagingManager doesn't exist
        """
        import threading

        staging_dir = tmp_path / ".claude-staging"
        staging_dir.mkdir()

        manager = StagingManager(staging_dir)

        def create_file(name):
            (staging_dir / name).write_text(f"content-{name}")

        threads = [
            threading.Thread(target=create_file, args=(f"file{i}.txt",))
            for i in range(10)
        ]

        for t in threads:
            t.start()
        for t in threads:
            t.join()

        files = manager.list_files()
        assert len(files) == 10
