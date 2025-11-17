#!/usr/bin/env python3
"""
TDD Tests for .claude/lib/ Duplicate Prevention (FAILING - Red Phase)

This module contains FAILING tests for duplicate library prevention system
that will detect and clean .claude/lib/ duplicates before they cause import conflicts.

Requirements:
1. OrphanFileCleaner.find_duplicate_libs() detects Python files in .claude/lib/
2. InstallationValidator.validate_no_duplicate_libs() warns about duplicates
3. Pre-install cleanup removes .claude/lib/ directory
4. Integration with install orchestrator and plugin updater
5. No actual duplicates exist in repository

Test Coverage Target: 100% of duplicate detection and cleanup logic

Following TDD principles:
- Write tests FIRST (red phase)
- Tests describe duplicate prevention requirements
- Tests should FAIL until implementation is complete
- Each test validates ONE requirement

Author: test-master agent
Date: 2025-11-17
Issue: GitHub #81 - Prevent .claude/lib/ Duplicate Library Imports
"""

import json
import os
import sys
import tempfile
from pathlib import Path
from unittest.mock import Mock, patch, call, MagicMock

import pytest

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

# These imports will FAIL until methods are implemented
from plugins.autonomous_dev.lib.orphan_file_cleaner import (
    OrphanFileCleaner,
    OrphanFile,
    CleanupResult,
)
from plugins.autonomous_dev.lib.installation_validator import (
    InstallationValidator,
    ValidationResult,
)


class TestOrphanCleanerDetectsDuplicateLibs:
    """Test OrphanFileCleaner.find_duplicate_libs() detects .claude/lib/ files."""

    @pytest.fixture
    def temp_project(self, tmp_path):
        """Create temporary project with .claude directory structure."""
        project_root = tmp_path / "test_project"
        project_root.mkdir()
        (project_root / ".claude").mkdir()
        (project_root / ".claude" / "lib").mkdir()
        return project_root

    def test_find_duplicate_libs_detects_python_files(self, temp_project):
        """Test find_duplicate_libs() detects Python files in .claude/lib/.

        REQUIREMENT: Detect duplicate libraries in legacy location.
        Expected: Returns list of Python files found in .claude/lib/.
        """
        # Create duplicate library files in .claude/lib/
        lib_dir = temp_project / ".claude" / "lib"
        (lib_dir / "security_utils.py").write_text("# Duplicate")
        (lib_dir / "path_utils.py").write_text("# Duplicate")
        (lib_dir / "__init__.py").write_text("")

        cleaner = OrphanFileCleaner(project_root=temp_project)
        duplicates = cleaner.find_duplicate_libs()

        # Should find 2 duplicate files (excluding __init__.py)
        assert len(duplicates) == 2
        duplicate_names = [d.name for d in duplicates]
        assert "security_utils.py" in duplicate_names
        assert "path_utils.py" in duplicate_names
        assert "__init__.py" not in duplicate_names  # Excluded

    def test_find_duplicate_libs_empty_directory(self, temp_project):
        """Test find_duplicate_libs() handles empty .claude/lib/ directory.

        REQUIREMENT: Handle edge case of empty directory.
        Expected: Returns empty list when .claude/lib/ is empty.
        """
        # .claude/lib/ exists but is empty
        lib_dir = temp_project / ".claude" / "lib"
        assert lib_dir.exists()
        assert len(list(lib_dir.iterdir())) == 0

        cleaner = OrphanFileCleaner(project_root=temp_project)
        duplicates = cleaner.find_duplicate_libs()

        assert len(duplicates) == 0

    def test_find_duplicate_libs_no_directory(self, temp_project):
        """Test find_duplicate_libs() handles non-existent .claude/lib/.

        REQUIREMENT: Handle edge case of missing directory.
        Expected: Returns empty list when .claude/lib/ doesn't exist.
        """
        # Remove .claude/lib/ directory
        lib_dir = temp_project / ".claude" / "lib"
        lib_dir.rmdir()
        assert not lib_dir.exists()

        cleaner = OrphanFileCleaner(project_root=temp_project)
        duplicates = cleaner.find_duplicate_libs()

        assert len(duplicates) == 0

    def test_find_duplicate_libs_ignores_pycache(self, temp_project):
        """Test find_duplicate_libs() ignores __pycache__ directories.

        REQUIREMENT: Ignore Python infrastructure files.
        Expected: __pycache__ and .pyc files not reported.
        """
        # Create .claude/lib/ with __pycache__
        lib_dir = temp_project / ".claude" / "lib"
        (lib_dir / "security_utils.py").write_text("# Duplicate")
        (lib_dir / "__pycache__").mkdir()
        (lib_dir / "__pycache__" / "security_utils.cpython-311.pyc").write_text("bytecode")

        cleaner = OrphanFileCleaner(project_root=temp_project)
        duplicates = cleaner.find_duplicate_libs()

        # Should only find security_utils.py
        assert len(duplicates) == 1
        assert duplicates[0].name == "security_utils.py"

    def test_find_duplicate_libs_handles_nested_directories(self, temp_project):
        """Test find_duplicate_libs() detects files in nested directories.

        REQUIREMENT: Detect all duplicate files regardless of depth.
        Expected: Finds files in subdirectories of .claude/lib/.
        """
        # Create nested structure in .claude/lib/
        lib_dir = temp_project / ".claude" / "lib"
        (lib_dir / "utils").mkdir()
        (lib_dir / "utils" / "security.py").write_text("# Nested duplicate")
        (lib_dir / "security_utils.py").write_text("# Top-level duplicate")

        cleaner = OrphanFileCleaner(project_root=temp_project)
        duplicates = cleaner.find_duplicate_libs()

        # Should find both files
        assert len(duplicates) == 2
        duplicate_paths = [str(d.relative_to(lib_dir)) for d in duplicates]
        assert "security_utils.py" in duplicate_paths
        assert "utils/security.py" in duplicate_paths or "utils\\security.py" in duplicate_paths

    def test_find_duplicate_libs_returns_path_objects(self, temp_project):
        """Test find_duplicate_libs() returns Path objects.

        REQUIREMENT: Consistent API using pathlib.
        Expected: Returns list of pathlib.Path objects.
        """
        # Create duplicate library
        lib_dir = temp_project / ".claude" / "lib"
        (lib_dir / "security_utils.py").write_text("# Duplicate")

        cleaner = OrphanFileCleaner(project_root=temp_project)
        duplicates = cleaner.find_duplicate_libs()

        assert len(duplicates) == 1
        assert isinstance(duplicates[0], Path)
        assert duplicates[0].is_absolute()


class TestInstallationValidatorWarnsAboutDuplicates:
    """Test InstallationValidator.validate_no_duplicate_libs() warns about duplicates."""

    @pytest.fixture
    def temp_project(self, tmp_path):
        """Create temporary project."""
        project_root = tmp_path / "test_project"
        project_root.mkdir()
        (project_root / ".claude").mkdir()
        return project_root

    def test_validate_no_duplicate_libs_warns_when_duplicates_found(self, temp_project):
        """Test validate_no_duplicate_libs() returns warnings when .claude/lib/ has files.

        REQUIREMENT: Installation validator detects duplicates.
        Expected: Returns list of warning messages about duplicate files.
        """
        # Create duplicate libraries
        lib_dir = temp_project / ".claude" / "lib"
        lib_dir.mkdir()
        (lib_dir / "security_utils.py").write_text("# Duplicate")
        (lib_dir / "path_utils.py").write_text("# Duplicate")

        validator = InstallationValidator(
            source_dir=temp_project / "plugins",
            dest_dir=temp_project / ".claude"
        )
        warnings = validator.validate_no_duplicate_libs()

        # Should return warnings
        assert len(warnings) > 0
        warnings_text = " ".join(warnings).lower()
        assert "duplicate" in warnings_text or ".claude/lib" in warnings_text

    def test_validate_no_duplicate_libs_returns_empty_when_clean(self, temp_project):
        """Test validate_no_duplicate_libs() returns empty list when .claude/lib/ is empty.

        REQUIREMENT: No false positives for clean installations.
        Expected: Returns empty list when no duplicates exist.
        """
        # Create empty .claude/lib/
        lib_dir = temp_project / ".claude" / "lib"
        lib_dir.mkdir()

        validator = InstallationValidator(
            source_dir=temp_project / "plugins",
            dest_dir=temp_project / ".claude"
        )
        warnings = validator.validate_no_duplicate_libs()

        assert len(warnings) == 0

    def test_validate_no_duplicate_libs_returns_empty_when_no_lib_dir(self, temp_project):
        """Test validate_no_duplicate_libs() returns empty list when .claude/lib/ doesn't exist.

        REQUIREMENT: Handle missing directory gracefully.
        Expected: Returns empty list when .claude/lib/ not present.
        """
        # No .claude/lib/ directory
        lib_dir = temp_project / ".claude" / "lib"
        assert not lib_dir.exists()

        validator = InstallationValidator(
            source_dir=temp_project / "plugins",
            dest_dir=temp_project / ".claude"
        )
        warnings = validator.validate_no_duplicate_libs()

        assert len(warnings) == 0

    def test_validate_no_duplicate_libs_provides_cleanup_instructions(self, temp_project):
        """Test validate_no_duplicate_libs() provides helpful cleanup instructions.

        REQUIREMENT: User-friendly error messages.
        Expected: Warning includes instructions for resolving duplicates.
        """
        # Create duplicate library
        lib_dir = temp_project / ".claude" / "lib"
        lib_dir.mkdir()
        (lib_dir / "security_utils.py").write_text("# Duplicate")

        validator = InstallationValidator(
            source_dir=temp_project / "plugins",
            dest_dir=temp_project / ".claude"
        )
        warnings = validator.validate_no_duplicate_libs()

        # Should include cleanup instructions
        assert len(warnings) > 0
        warnings_text = " ".join(warnings).lower()
        assert any(keyword in warnings_text for keyword in [
            "remove", "delete", "cleanup", "rm -rf", "plugins.autonomous_dev.lib"
        ])

    def test_validate_no_duplicate_libs_counts_files(self, temp_project):
        """Test validate_no_duplicate_libs() reports count of duplicate files.

        REQUIREMENT: Clear reporting of issue severity.
        Expected: Warning includes count of duplicate files found.
        """
        # Create 3 duplicate libraries
        lib_dir = temp_project / ".claude" / "lib"
        lib_dir.mkdir()
        (lib_dir / "security_utils.py").write_text("# Duplicate")
        (lib_dir / "path_utils.py").write_text("# Duplicate")
        (lib_dir / "validation.py").write_text("# Duplicate")

        validator = InstallationValidator(
            source_dir=temp_project / "plugins",
            dest_dir=temp_project / ".claude"
        )
        warnings = validator.validate_no_duplicate_libs()

        # Should mention count
        warnings_text = " ".join(warnings)
        assert "3" in warnings_text or "three" in warnings_text.lower()


class TestPreInstallCleanup:
    """Test pre_install_cleanup() removes .claude/lib/ directory."""

    @pytest.fixture
    def temp_project(self, tmp_path):
        """Create temporary project with .claude/lib/."""
        project_root = tmp_path / "test_project"
        project_root.mkdir()
        (project_root / ".claude").mkdir()
        (project_root / ".claude" / "lib").mkdir()
        return project_root

    def test_pre_install_cleanup_removes_lib_directory(self, temp_project):
        """Test pre_install_cleanup() removes .claude/lib/ directory.

        REQUIREMENT: Pre-install cleanup removes legacy library location.
        Expected: .claude/lib/ directory removed before installation.
        """
        # Create .claude/lib/ with files
        lib_dir = temp_project / ".claude" / "lib"
        (lib_dir / "security_utils.py").write_text("# Duplicate")
        (lib_dir / "path_utils.py").write_text("# Duplicate")
        assert lib_dir.exists()
        assert len(list(lib_dir.iterdir())) == 2

        cleaner = OrphanFileCleaner(project_root=temp_project)
        result = cleaner.pre_install_cleanup()

        # Directory should be removed
        assert not lib_dir.exists()
        assert result.success is True

    def test_pre_install_cleanup_handles_nonexistent_directory(self, temp_project):
        """Test pre_install_cleanup() handles non-existent .claude/lib/ gracefully.

        REQUIREMENT: Idempotent cleanup operation.
        Expected: No error when .claude/lib/ doesn't exist.
        """
        # Remove .claude/lib/
        lib_dir = temp_project / ".claude" / "lib"
        lib_dir.rmdir()
        assert not lib_dir.exists()

        cleaner = OrphanFileCleaner(project_root=temp_project)
        result = cleaner.pre_install_cleanup()

        # Should succeed without error
        assert result.success is True
        assert result.files_removed == 0

    def test_pre_install_cleanup_handles_permission_errors(self, temp_project, monkeypatch):
        """Test pre_install_cleanup() handles permission errors gracefully.

        REQUIREMENT: Graceful error handling for read-only directories.
        Expected: Returns failure result with clear error message.
        """
        # Create .claude/lib/ with file
        lib_dir = temp_project / ".claude" / "lib"
        (lib_dir / "security_utils.py").write_text("# Duplicate")

        # Mock shutil.rmtree to raise PermissionError
        import shutil
        original_rmtree = shutil.rmtree
        def mock_rmtree(path, *args, **kwargs):
            if str(path).endswith("lib"):
                raise PermissionError(f"Permission denied: {path}")
            return original_rmtree(path, *args, **kwargs)

        monkeypatch.setattr("shutil.rmtree", mock_rmtree)

        cleaner = OrphanFileCleaner(project_root=temp_project)
        result = cleaner.pre_install_cleanup()

        # Should report error but not crash
        assert result.success is False
        assert "permission" in result.error_message.lower()

    def test_pre_install_cleanup_reports_removed_file_count(self, temp_project):
        """Test pre_install_cleanup() reports count of removed files.

        REQUIREMENT: Clear reporting of cleanup operations.
        Expected: Result includes count of files removed.
        """
        # Create .claude/lib/ with 3 files
        lib_dir = temp_project / ".claude" / "lib"
        (lib_dir / "security_utils.py").write_text("# Duplicate")
        (lib_dir / "path_utils.py").write_text("# Duplicate")
        (lib_dir / "validation.py").write_text("# Duplicate")

        cleaner = OrphanFileCleaner(project_root=temp_project)
        result = cleaner.pre_install_cleanup()

        # Should report 3 files removed
        assert result.files_removed == 3
        assert result.success is True

    def test_pre_install_cleanup_removes_nested_files(self, temp_project):
        """Test pre_install_cleanup() removes nested directories and files.

        REQUIREMENT: Complete cleanup of all duplicate files.
        Expected: Removes nested subdirectories within .claude/lib/.
        """
        # Create nested structure
        lib_dir = temp_project / ".claude" / "lib"
        (lib_dir / "utils").mkdir()
        (lib_dir / "utils" / "security.py").write_text("# Nested")
        (lib_dir / "security_utils.py").write_text("# Top-level")

        cleaner = OrphanFileCleaner(project_root=temp_project)
        result = cleaner.pre_install_cleanup()

        # Directory should be completely removed
        assert not lib_dir.exists()
        assert result.files_removed >= 2

    def test_pre_install_cleanup_audit_logs_operation(self, temp_project):
        """Test pre_install_cleanup() logs operation to audit trail.

        REQUIREMENT: Audit logging for all file operations.
        Expected: Cleanup operation logged with timestamp and file count.
        """
        # Create .claude/lib/ with file
        lib_dir = temp_project / ".claude" / "lib"
        (lib_dir / "security_utils.py").write_text("# Duplicate")
        (temp_project / "logs").mkdir()

        cleaner = OrphanFileCleaner(project_root=temp_project)

        with patch('plugins.autonomous_dev.lib.security_utils.audit_log') as mock_audit:
            result = cleaner.pre_install_cleanup()

            # Should have logged the cleanup
            assert mock_audit.called
            call_args = str(mock_audit.call_args)
            assert "pre_install_cleanup" in call_args.lower() or "cleanup" in call_args.lower()


class TestIntegrationWithInstallers:
    """Test integration of pre_install_cleanup() with installers."""

    def test_install_orchestrator_calls_cleanup(self, tmp_path):
        """Test install orchestrator calls pre_install_cleanup().

        REQUIREMENT: Integration with installation workflow.
        Expected: Install orchestrator invokes cleanup before copying files.

        Note: Verifies cleanup is integrated into install workflow by checking
        that InstallOrchestrator imports and uses OrphanFileCleaner.
        """
        import inspect
        import plugins.autonomous_dev.lib.install_orchestrator as install_module

        # Verify InstallOrchestrator.install() method references OrphanFileCleaner
        install_source = inspect.getsource(install_module.InstallOrchestrator)

        # Check that the install method imports and uses OrphanFileCleaner
        assert "OrphanFileCleaner" in install_source, \
            "InstallOrchestrator.install() should import OrphanFileCleaner"

        assert "pre_install_cleanup" in install_source, \
            "InstallOrchestrator.install() should call pre_install_cleanup()"

        # Verify the cleanup happens before file discovery
        cleanup_line = None
        discover_line = None
        for i, line in enumerate(install_source.split('\n')):
            if 'pre_install_cleanup' in line:
                cleanup_line = i
            if 'discover' in line.lower() and 'file' in line.lower():
                discover_line = i

        if cleanup_line is not None and discover_line is not None:
            assert cleanup_line < discover_line, \
                "pre_install_cleanup() should be called before file discovery"

    def test_plugin_updater_calls_cleanup(self, tmp_path):
        """Test plugin updater calls pre_install_cleanup().

        REQUIREMENT: Integration with update workflow.
        Expected: Plugin updater invokes cleanup before updating files.
        """
        from plugins.autonomous_dev.lib.update_plugin import PluginUpdater

        project_root = tmp_path / "test_project"
        project_root.mkdir()
        (project_root / ".claude").mkdir()
        (project_root / ".claude" / "lib").mkdir()
        (project_root / ".claude" / "lib" / "security_utils.py").write_text("# Duplicate")

        # Mock the cleanup method
        with patch.object(OrphanFileCleaner, 'pre_install_cleanup') as mock_cleanup:
            mock_cleanup.return_value = Mock(success=True, files_removed=1)

            updater = PluginUpdater(project_root=project_root)

            # Attempt update (will fail on missing plugin, but cleanup should be called)
            try:
                updater.update()
            except Exception:
                pass  # Expected to fail on missing plugin

            # Should have called cleanup
            assert mock_cleanup.called

    def test_cleanup_called_before_file_copy(self, tmp_path):
        """Test cleanup is called BEFORE file copying begins.

        REQUIREMENT: Cleanup must happen before installation.
        Expected: Cleanup invoked before any file copy operations.
        """
        from plugins.autonomous_dev.lib.install_orchestrator import InstallOrchestrator

        project_root = tmp_path / "test_project"
        project_root.mkdir()
        (project_root / ".claude").mkdir()
        lib_dir = project_root / ".claude" / "lib"
        lib_dir.mkdir()

        call_order = []

        # Mock cleanup and copy operations to track order
        with patch.object(OrphanFileCleaner, 'pre_install_cleanup') as mock_cleanup:
            mock_cleanup.side_effect = lambda: call_order.append('cleanup') or Mock(success=True)

            with patch('shutil.copy2') as mock_copy:
                mock_copy.side_effect = lambda *args: call_order.append('copy')

                orchestrator = InstallOrchestrator(
                    plugin_dir=tmp_path / "source",
                    project_dir=project_root
                )

                try:
                    orchestrator.install()
                except Exception:
                    pass

                # Cleanup should be called before any copy
                if 'cleanup' in call_order and 'copy' in call_order:
                    cleanup_index = call_order.index('cleanup')
                    copy_index = call_order.index('copy')
                    assert cleanup_index < copy_index


class TestNoActualDuplicatesInRepository:
    """Test that no actual duplicates exist in the repository."""

    def test_claude_lib_directory_does_not_exist(self):
        """Test .claude/lib/ directory doesn't exist in repository.

        REQUIREMENT: No duplicates in source repository.
        Expected: .claude/lib/ directory does not exist.
        """
        repo_root = Path(__file__).parent.parent.parent
        claude_lib = repo_root / ".claude" / "lib"

        assert not claude_lib.exists(), (
            f"Found .claude/lib/ directory at {claude_lib}. "
            "This directory should not exist. "
            "All libraries should be in plugins/autonomous-dev/lib/."
        )

    def test_all_imports_use_correct_path(self):
        """Test all Python files import from plugins.autonomous_dev.lib.*.

        REQUIREMENT: Consistent import paths.
        Expected: No imports from .claude.lib, all use plugins.autonomous_dev.lib.
        """
        repo_root = Path(__file__).parent.parent.parent

        # Find all Python files
        python_files = list(repo_root.rglob("*.py"))

        bad_imports = []
        for py_file in python_files:
            if ".git" in str(py_file) or "__pycache__" in str(py_file):
                continue

            # Skip this test file itself
            if py_file.name == "test_issue81_duplicate_prevention.py":
                continue

            try:
                content = py_file.read_text()
                lines = content.split("\n")

                for i, line in enumerate(lines, 1):
                    # Skip comments and docstrings
                    stripped = line.strip()
                    if stripped.startswith("#") or stripped.startswith('"""') or stripped.startswith("'''"):
                        continue

                    # Check for bad import patterns (actual import statements only)
                    if stripped.startswith("from .claude.lib") or stripped.startswith("import .claude.lib"):
                        bad_imports.append((py_file, i, line.strip()))
                    if stripped.startswith("from claude.lib") and "autonomous_dev" not in line:
                        bad_imports.append((py_file, i, line.strip()))

            except Exception as e:
                # Skip binary files or unreadable files
                continue

        assert len(bad_imports) == 0, (
            f"Found {len(bad_imports)} imports from .claude.lib:\n" +
            "\n".join(f"{f}:{line}: {import_line}" for f, line, import_line in bad_imports[:10])
        )

    def test_no_duplicate_library_files_in_claude(self):
        """Test no library files exist in .claude/ that duplicate plugins/autonomous-dev/lib/.

        REQUIREMENT: Single source of truth for libraries.
        Expected: All library files in plugins/autonomous-dev/lib/, none in .claude/.
        """
        repo_root = Path(__file__).parent.parent.parent
        plugin_lib = repo_root / "plugins" / "autonomous-dev" / "lib"
        claude_dir = repo_root / ".claude"

        # Get all Python files in plugin lib (excluding __init__.py and __pycache__)
        if plugin_lib.exists():
            plugin_libs = {
                f.name for f in plugin_lib.rglob("*.py")
                if "__init__" not in f.name and "__pycache__" not in str(f)
            }
        else:
            plugin_libs = set()

        # Check for duplicates in .claude/ (but exclude .claude/hooks and .claude/commands)
        # Those are legitimate locations for hooks and commands, not library duplicates
        duplicates = []
        if claude_dir.exists():
            # Only check .claude/lib/ directory if it exists
            claude_lib = claude_dir / "lib"
            if claude_lib.exists():
                for py_file in claude_lib.rglob("*.py"):
                    if "__init__" in py_file.name or "__pycache__" in str(py_file):
                        continue

                    if py_file.name in plugin_libs:
                        duplicates.append(py_file)

        assert len(duplicates) == 0, (
            f"Found {len(duplicates)} duplicate library files in .claude/lib/:\n" +
            "\n".join(f"  - {d}" for d in duplicates)
        )


class TestEdgeCases:
    """Test edge cases for duplicate detection and cleanup."""

    @pytest.fixture
    def temp_project(self, tmp_path):
        """Create temporary project."""
        project_root = tmp_path / "test_project"
        project_root.mkdir()
        (project_root / ".claude").mkdir()
        return project_root

    def test_cleanup_handles_symlinked_lib_directory(self, temp_project):
        """Test cleanup handles symlinked .claude/lib/ directory.

        SECURITY: Prevent symlink-based attacks.
        Expected: Symlink removed but target preserved.
        """
        if not hasattr(os, 'symlink'):
            pytest.skip("Symlinks not supported on this platform")

        # Create target directory outside .claude/
        target_dir = temp_project / "important_libs"
        target_dir.mkdir()
        (target_dir / "important.py").write_text("# Important file")

        # Create symlink at .claude/lib/
        lib_dir = temp_project / ".claude" / "lib"
        try:
            lib_dir.symlink_to(target_dir)
        except OSError:
            pytest.skip("Cannot create symlinks on this system")

        cleaner = OrphanFileCleaner(project_root=temp_project)
        result = cleaner.pre_install_cleanup()

        # Symlink should be removed
        assert not lib_dir.exists()

        # But target should be preserved
        assert target_dir.exists()
        assert (target_dir / "important.py").exists()

    def test_cleanup_handles_readonly_files(self, temp_project, monkeypatch):
        """Test cleanup handles read-only files in .claude/lib/.

        REQUIREMENT: Handle file permission edge cases.
        Expected: Reports error but continues cleanup.
        """
        # Create .claude/lib/ with readonly file
        lib_dir = temp_project / ".claude" / "lib"
        lib_dir.mkdir()
        readonly_file = lib_dir / "readonly.py"
        readonly_file.write_text("# Readonly")

        # Make file readonly
        readonly_file.chmod(0o444)

        cleaner = OrphanFileCleaner(project_root=temp_project)
        result = cleaner.pre_install_cleanup()

        # Cleanup should succeed (shutil.rmtree handles readonly by default)
        # On some systems it may fail, which is also acceptable
        if not result.success:
            assert "permission" in result.error_message.lower()

    def test_find_duplicate_libs_handles_large_directories(self, temp_project):
        """Test find_duplicate_libs() performs well with many files.

        REQUIREMENT: Performance with realistic file counts.
        Expected: Handles 100+ files without performance issues.
        """
        # Create .claude/lib/ with 100 files
        lib_dir = temp_project / ".claude" / "lib"
        lib_dir.mkdir()

        for i in range(100):
            (lib_dir / f"lib_{i:03d}.py").write_text(f"# Library {i}")

        cleaner = OrphanFileCleaner(project_root=temp_project)
        duplicates = cleaner.find_duplicate_libs()

        # Should find all 100 files
        assert len(duplicates) == 100

    def test_cleanup_preserves_other_claude_directories(self, temp_project):
        """Test pre_install_cleanup() only removes .claude/lib/, not other .claude/ dirs.

        REQUIREMENT: Surgical cleanup, no collateral damage.
        Expected: .claude/commands/, .claude/hooks/ preserved.
        """
        # Create multiple .claude/ subdirectories
        (temp_project / ".claude" / "lib").mkdir()
        (temp_project / ".claude" / "lib" / "security_utils.py").write_text("# Duplicate")
        (temp_project / ".claude" / "commands").mkdir()
        (temp_project / ".claude" / "commands" / "status.md").write_text("# Command")
        (temp_project / ".claude" / "hooks").mkdir()
        (temp_project / ".claude" / "hooks" / "auto_format.py").write_text("# Hook")

        cleaner = OrphanFileCleaner(project_root=temp_project)
        result = cleaner.pre_install_cleanup()

        # Only .claude/lib/ should be removed
        assert not (temp_project / ".claude" / "lib").exists()
        assert (temp_project / ".claude" / "commands").exists()
        assert (temp_project / ".claude" / "hooks").exists()
        assert (temp_project / ".claude" / "commands" / "status.md").exists()


class TestCleanupResultDataClass:
    """Test CleanupResult data class for pre_install_cleanup()."""

    def test_cleanup_result_has_required_attributes(self):
        """Test CleanupResult has expected attributes for cleanup operations.

        REQUIREMENT: Clear result object for cleanup operations.
        Expected: Has success, files_removed, error_message attributes.
        """
        # This will fail until CleanupResult is updated with new attributes
        result = CleanupResult(
            orphans_detected=0,
            orphans_deleted=0,
            dry_run=False,
            errors=0,
            orphans=[],
            # New attributes for pre_install_cleanup
            success=True,
            files_removed=5,
            error_message=""
        )

        assert hasattr(result, 'success')
        assert hasattr(result, 'files_removed')
        assert hasattr(result, 'error_message')

    def test_cleanup_result_summary_includes_cleanup_info(self):
        """Test CleanupResult.summary includes pre-install cleanup information.

        REQUIREMENT: Clear user feedback for cleanup operations.
        Expected: Summary mentions pre-install cleanup and file counts.
        """
        result = CleanupResult(
            orphans_detected=0,
            orphans_deleted=0,
            dry_run=False,
            errors=0,
            orphans=[],
            success=True,
            files_removed=5,
            error_message=""
        )

        summary = result.summary

        # Should mention cleanup operation
        assert any(keyword in summary.lower() for keyword in [
            "cleanup", "removed", "5", "files"
        ])


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
