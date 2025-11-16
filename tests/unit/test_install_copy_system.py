"""
TDD Tests for Installation Copy System (Issue #80 - Phase 2)

Tests the intelligent copy system that preserves directory structure and
file permissions during installation.

Current State (RED PHASE):
- CopySystem class doesn't exist yet
- All tests should FAIL

Test Coverage:
- Directory structure preservation
- File permission handling
- Progress reporting
- Nested directory copying
"""

import pytest
from pathlib import Path
import os
import stat
import sys

# Add project root to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from plugins.autonomous_dev.lib.copy_system import CopySystem, CopyError, rollback


class TestCopySystemStructure:
    """Test directory structure preservation during copy."""

    def test_preserves_directory_structure(self, tmp_path):
        """Test that copy preserves source directory structure.

        Example:
        - Source: plugins/autonomous-dev/lib/foo.py
        - Dest: .claude/lib/foo.py (NOT .claude/foo.py)

        Current: FAILS - CopySystem doesn't exist
        """
        # Arrange: Create source structure
        source = tmp_path / "source" / "plugins" / "autonomous-dev"
        source.mkdir(parents=True)

        (source / "lib").mkdir()
        (source / "lib" / "utils.py").write_text("def util(): pass")

        (source / "lib" / "nested").mkdir()
        (source / "lib" / "nested" / "deep.py").write_text("def deep(): pass")

        dest = tmp_path / "dest" / ".claude"

        # Act: Copy with structure preservation
        copier = CopySystem(source, dest)
        copier.copy_all()

        # Assert: Structure preserved
        assert (dest / "lib" / "utils.py").exists()
        assert (dest / "lib" / "nested" / "deep.py").exists()

        # Verify content
        assert (dest / "lib" / "utils.py").read_text() == "def util(): pass"
        assert (dest / "lib" / "nested" / "deep.py").read_text() == "def deep(): pass"

    def test_creates_missing_directories(self, tmp_path):
        """Test that copy creates missing directories in destination.

        Current: FAILS - CopySystem doesn't exist
        """
        # Arrange: Source with nested structure
        source = tmp_path / "source"
        source.mkdir()

        (source / "a" / "b" / "c").mkdir(parents=True)
        (source / "a" / "b" / "c" / "file.txt").write_text("content")

        dest = tmp_path / "dest"
        # Dest doesn't exist yet

        # Act: Copy
        copier = CopySystem(source, dest)
        copier.copy_all()

        # Assert: Directories created
        assert dest.exists()
        assert (dest / "a").exists()
        assert (dest / "a" / "b").exists()
        assert (dest / "a" / "b" / "c").exists()
        assert (dest / "a" / "b" / "c" / "file.txt").exists()

    def test_handles_nested_skill_structure(self, tmp_path):
        """Test copying nested skill directory structure.

        Structure:
        - skills/testing-guide.skill/skill.md
        - skills/testing-guide.skill/docs/overview.md
        - skills/testing-guide.skill/examples/pytest.md

        Current: FAILS - CopySystem doesn't exist
        """
        # Arrange: Create skill structure
        source = tmp_path / "source"
        skill = source / "skills" / "testing-guide.skill"
        skill.mkdir(parents=True)

        (skill / "skill.md").write_text("# Testing Guide")

        (skill / "docs").mkdir()
        (skill / "docs" / "overview.md").write_text("# Overview")

        (skill / "examples").mkdir()
        (skill / "examples" / "pytest.md").write_text("# Pytest")

        dest = tmp_path / "dest"

        # Act: Copy
        copier = CopySystem(source, dest)
        copier.copy_all()

        # Assert: Full structure preserved
        assert (dest / "skills" / "testing-guide.skill" / "skill.md").exists()
        assert (dest / "skills" / "testing-guide.skill" / "docs" / "overview.md").exists()
        assert (dest / "skills" / "testing-guide.skill" / "examples" / "pytest.md").exists()


class TestCopySystemPermissions:
    """Test file permission handling during copy."""

    def test_sets_executable_permissions_on_scripts(self, tmp_path):
        """Test that script files get executable permissions.

        Scripts should be executable: scripts/*.py

        Current: FAILS - CopySystem doesn't exist
        """
        # Arrange: Create script file
        source = tmp_path / "source"
        source.mkdir()

        (source / "scripts").mkdir()
        script_file = source / "scripts" / "setup.py"
        script_file.write_text("#!/usr/bin/env python3\nprint('setup')")

        dest = tmp_path / "dest"

        # Act: Copy
        copier = CopySystem(source, dest)
        copier.copy_all()

        # Assert: Script is executable
        dest_script = dest / "scripts" / "setup.py"
        assert dest_script.exists()

        file_stat = dest_script.stat()
        assert file_stat.st_mode & stat.S_IXUSR, "Script should be executable by user"
        assert file_stat.st_mode & stat.S_IXGRP, "Script should be executable by group"
        assert file_stat.st_mode & stat.S_IXOTH, "Script should be executable by others"

    def test_preserves_readonly_permissions(self, tmp_path):
        """Test that readonly files remain readonly after copy.

        Current: FAILS - CopySystem doesn't exist
        """
        # Arrange: Create readonly file
        source = tmp_path / "source"
        source.mkdir()

        readonly_file = source / "config.json"
        readonly_file.write_text('{"readonly": true}')
        readonly_file.chmod(0o444)  # Read-only for all

        dest = tmp_path / "dest"

        # Act: Copy
        copier = CopySystem(source, dest)
        copier.copy_all()

        # Assert: Readonly preserved
        dest_file = dest / "config.json"
        file_stat = dest_file.stat()

        # Should be readable but not writable
        assert file_stat.st_mode & stat.S_IRUSR
        assert not file_stat.st_mode & stat.S_IWUSR

    def test_preserves_normal_file_permissions(self, tmp_path):
        """Test that normal files keep standard permissions.

        Current: FAILS - CopySystem doesn't exist
        """
        # Arrange: Create normal file
        source = tmp_path / "source"
        source.mkdir()

        normal_file = source / "README.md"
        normal_file.write_text("# README")

        dest = tmp_path / "dest"

        # Act: Copy
        copier = CopySystem(source, dest)
        copier.copy_all()

        # Assert: Normal permissions
        dest_file = dest / "README.md"
        file_stat = dest_file.stat()

        # Should be readable and writable by user
        assert file_stat.st_mode & stat.S_IRUSR
        assert file_stat.st_mode & stat.S_IWUSR


class TestCopySystemProgress:
    """Test progress reporting during copy operations."""

    def test_reports_copy_progress(self, tmp_path):
        """Test that copy system reports progress updates.

        Progress format:
        - Current file number
        - Total file count
        - Current file path
        - Percentage complete

        Current: FAILS - CopySystem doesn't exist
        """
        # Arrange: Create multiple files
        source = tmp_path / "source"
        source.mkdir()

        for i in range(10):
            (source / f"file{i}.txt").write_text(f"content{i}")

        dest = tmp_path / "dest"

        # Act: Copy with progress tracking
        copier = CopySystem(source, dest)
        progress_updates = []

        def progress_callback(current, total, file_path):
            progress_updates.append({
                "current": current,
                "total": total,
                "file": file_path,
                "percentage": (current / total) * 100
            })

        copier.copy_all(progress_callback=progress_callback)

        # Assert: Progress reported
        assert len(progress_updates) == 10

        # Verify progress increments
        assert progress_updates[0]["current"] == 1
        assert progress_updates[9]["current"] == 10
        assert all(update["total"] == 10 for update in progress_updates)

        # Verify percentages
        assert progress_updates[0]["percentage"] == 10.0
        assert progress_updates[9]["percentage"] == 100.0

    def test_displays_human_readable_progress(self, tmp_path, capsys):
        """Test that progress is displayed in human-readable format.

        Expected output:
        [1/10] Copying commands/auto-implement.md... (10%)
        [2/10] Copying lib/security_utils.py... (20%)

        Current: FAILS - CopySystem doesn't exist
        """
        # Arrange: Create files
        source = tmp_path / "source"
        source.mkdir()

        (source / "commands").mkdir()
        (source / "commands" / "test.md").write_text("test")

        (source / "lib").mkdir()
        (source / "lib" / "utils.py").write_text("utils")

        dest = tmp_path / "dest"

        # Act: Copy with display
        copier = CopySystem(source, dest)
        copier.copy_all(show_progress=True)

        # Assert: Progress displayed
        captured = capsys.readouterr()
        output = captured.out

        assert "[1/2]" in output
        assert "[2/2]" in output
        assert "commands/test.md" in output or "test.md" in output
        assert "lib/utils.py" in output or "utils.py" in output
        assert "50%" in output or "100%" in output


class TestCopySystemExclusions:
    """Test that copy system respects exclusion patterns."""

    def test_skips_excluded_patterns(self, tmp_path):
        """Test that excluded patterns are not copied.

        Exclusions:
        - __pycache__/
        - *.pyc
        - .pytest_cache/
        - .git/

        Current: FAILS - CopySystem doesn't exist
        """
        # Arrange: Create files with exclusions
        source = tmp_path / "source"
        source.mkdir()

        # Valid file
        (source / "utils.py").write_text("valid")

        # Excluded: cache
        (source / "__pycache__").mkdir()
        (source / "__pycache__" / "utils.cpython-39.pyc").write_text("cache")

        # Excluded: pytest cache
        (source / ".pytest_cache").mkdir()
        (source / ".pytest_cache" / "cache").write_text("pytest")

        # Excluded: git
        (source / ".git").mkdir()
        (source / ".git" / "config").write_text("git")

        dest = tmp_path / "dest"

        # Act: Copy
        copier = CopySystem(source, dest)
        copier.copy_all()

        # Assert: Only valid file copied
        assert (dest / "utils.py").exists()
        assert not (dest / "__pycache__").exists()
        assert not (dest / ".pytest_cache").exists()
        assert not (dest / ".git").exists()

    def test_includes_env_example(self, tmp_path):
        """Test that .env.example is included despite being hidden.

        Current: FAILS - CopySystem doesn't exist
        """
        # Arrange: Create .env.example
        source = tmp_path / "source"
        source.mkdir()

        (source / ".env.example").write_text("API_KEY=example")
        (source / ".gitignore").write_text("*.pyc")  # Should be excluded

        dest = tmp_path / "dest"

        # Act: Copy
        copier = CopySystem(source, dest)
        copier.copy_all()

        # Assert: .env.example included, .gitignore excluded
        assert (dest / ".env.example").exists()
        assert not (dest / ".gitignore").exists()


class TestCopySystemErrorHandling:
    """Test error handling during copy operations."""

    def test_handles_permission_denied_gracefully(self, tmp_path):
        """Test that permission errors are handled gracefully.

        Current: FAILS - CopySystem doesn't exist
        """
        # Arrange: Create file that can't be copied
        source = tmp_path / "source"
        source.mkdir()

        protected_dir = source / "protected"
        protected_dir.mkdir()
        protected_file = protected_dir / "secret.txt"
        protected_file.write_text("secret")

        # Make directory unreadable (on Unix)
        if os.name != 'nt':  # Skip on Windows
            protected_dir.chmod(0o000)

        dest = tmp_path / "dest"

        # Act: Copy with error handling
        copier = CopySystem(source, dest)

        try:
            result = copier.copy_all(continue_on_error=True)

            # Assert: Result structure is correct (even if no errors on some systems)
            # On systems where file owner can bypass permissions, error_list may be empty
            assert isinstance(result, dict)
            assert "error_list" in result
            assert "files_copied" in result
            assert "errors" in result

            # If errors occurred, they should be properly formatted
            if result["errors"] > 0:
                assert len(result["error_list"]) > 0
                assert any("protected" in str(e) for e in result["error_list"])
        finally:
            # Cleanup: Restore permissions
            if os.name != 'nt':
                protected_dir.chmod(0o755)

    def test_validates_source_exists(self, tmp_path):
        """Test that copy validates source directory exists.

        Current: FAILS - CopySystem doesn't exist
        """
        # Arrange: Nonexistent source
        source = tmp_path / "nonexistent"
        dest = tmp_path / "dest"

        # Act & Assert: Raises error
        with pytest.raises(CopyError) as exc_info:
            copier = CopySystem(source, dest)
            copier.copy_all()

        assert "Source directory not found" in str(exc_info.value)

    def test_prevents_overwriting_without_confirmation(self, tmp_path):
        """Test that copy prevents overwriting existing files without confirmation.

        Current: FAILS - CopySystem doesn't exist
        """
        # Arrange: Create existing file in destination
        source = tmp_path / "source"
        source.mkdir()
        (source / "file.txt").write_text("new content")

        dest = tmp_path / "dest"
        dest.mkdir()
        existing_file = dest / "file.txt"
        existing_file.write_text("existing content")

        # Act: Copy without overwrite permission

        copier = CopySystem(source, dest)

        with pytest.raises(CopyError) as exc_info:
            copier.copy_all(overwrite=False)

        assert "File already exists" in str(exc_info.value)
        assert existing_file.read_text() == "existing content"  # Unchanged

    def test_allows_overwriting_with_confirmation(self, tmp_path):
        """Test that copy allows overwriting when explicitly enabled.

        Current: FAILS - CopySystem doesn't exist
        """
        # Arrange: Create existing file
        source = tmp_path / "source"
        source.mkdir()
        (source / "file.txt").write_text("new content")

        dest = tmp_path / "dest"
        dest.mkdir()
        (dest / "file.txt").write_text("old content")

        # Act: Copy with overwrite enabled

        copier = CopySystem(source, dest)
        copier.copy_all(overwrite=True)

        # Assert: File overwritten
        assert (dest / "file.txt").read_text() == "new content"


class TestCopySystemTimestamps:
    """Test timestamp preservation during copy."""

    def test_preserves_file_timestamps(self, tmp_path):
        """Test that copy preserves file modification times.

        Current: FAILS - CopySystem doesn't exist
        """
        # Arrange: Create file with specific timestamp
        source = tmp_path / "source"
        source.mkdir()

        source_file = source / "file.txt"
        source_file.write_text("content")

        # Set specific timestamp (2024-01-01 12:00:00)
        timestamp = 1704110400
        os.utime(source_file, (timestamp, timestamp))

        dest = tmp_path / "dest"

        # Act: Copy
        copier = CopySystem(source, dest)
        copier.copy_all(preserve_timestamps=True)

        # Assert: Timestamp preserved
        dest_file = dest / "file.txt"
        assert dest_file.stat().st_mtime == timestamp

    def test_updates_timestamps_when_disabled(self, tmp_path):
        """Test that timestamps are updated when preservation is disabled.

        Current: FAILS - CopySystem doesn't exist
        """
        # Arrange: Create file with old timestamp
        source = tmp_path / "source"
        source.mkdir()

        source_file = source / "file.txt"
        source_file.write_text("content")

        old_timestamp = 1704110400  # 2024-01-01
        os.utime(source_file, (old_timestamp, old_timestamp))

        dest = tmp_path / "dest"

        # Act: Copy without preserving timestamps

        copier = CopySystem(source, dest)
        copier.copy_all(preserve_timestamps=False)

        # Assert: Timestamp is newer (current time)
        dest_file = dest / "file.txt"
        assert dest_file.stat().st_mtime > old_timestamp


class TestCopySystemIntegration:
    """Integration tests for copy system."""

    def test_copies_complete_plugin_structure(self, tmp_path):
        """Test copying complete plugin directory structure.

        Simulates real installation scenario.

        Current: FAILS - CopySystem doesn't exist
        """
        # Arrange: Create realistic plugin structure
        source = tmp_path / "plugins" / "autonomous-dev"
        source.mkdir(parents=True)

        # Commands
        (source / "commands").mkdir()
        (source / "commands" / "auto-implement.md").write_text("# Auto Implement")
        (source / "commands" / "setup.md").write_text("# Setup")

        # Hooks
        (source / "hooks").mkdir()
        (source / "hooks" / "auto_format.py").write_text("def format(): pass")

        # Agents
        (source / "agents").mkdir()
        (source / "agents" / "researcher.md").write_text("# Researcher")

        # Skills
        (source / "skills").mkdir()
        skill = source / "skills" / "testing-guide.skill"
        skill.mkdir()
        (skill / "skill.md").write_text("# Testing")
        (skill / "docs").mkdir()
        (skill / "docs" / "guide.md").write_text("# Guide")

        # Lib
        (source / "lib").mkdir()
        (source / "lib" / "security_utils.py").write_text("def secure(): pass")

        # Scripts
        (source / "scripts").mkdir()
        (source / "scripts" / "setup.py").write_text("#!/usr/bin/env python3")

        dest = tmp_path / ".claude"

        # Act: Copy complete structure

        copier = CopySystem(source, dest)
        result = copier.copy_all()

        # Assert: Complete structure copied
        assert (dest / "commands" / "auto-implement.md").exists()
        assert (dest / "commands" / "setup.md").exists()
        assert (dest / "hooks" / "auto_format.py").exists()
        assert (dest / "agents" / "researcher.md").exists()
        assert (dest / "skills" / "testing-guide.skill" / "skill.md").exists()
        assert (dest / "skills" / "testing-guide.skill" / "docs" / "guide.md").exists()
        assert (dest / "lib" / "security_utils.py").exists()
        assert (dest / "scripts" / "setup.py").exists()

        # Verify scripts are executable
        assert os.access(dest / "scripts" / "setup.py", os.X_OK)

        # Verify file count
        assert result["files_copied"] == 8
        assert result["errors"] == 0
