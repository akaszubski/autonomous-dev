#!/usr/bin/env python3
"""
TDD Security Tests for ProjectMdUpdater (FAILING - Red Phase)

This module contains FAILING tests for security enhancements to project_md_updater.py.
These tests describe the security requirements and will fail until implementation is complete.

Security Requirements (from GitHub issue #46 - CRITICAL CVSS 9.8):
1. Use shared security_utils.py for path validation (consistency with agent_tracker.py)
2. Whitelist validation: All paths must be within PROJECT_ROOT
3. Path traversal prevention: Block ../../etc/passwd style attacks
4. Symlink detection and rejection: Prevent symlink-based escapes
5. Test mode support: Allow temp directories in pytest but block system directories
6. Audit logging: Log all path validation attempts

Test Coverage Target: 100% of security-critical code paths

Following TDD principles:
- Write tests FIRST (red phase)
- Tests describe security requirements
- Tests should FAIL until security_utils.py integration is complete
- Each test validates ONE security requirement

Author: test-master agent
Date: 2025-11-07
Issue: #46
"""

import os
import sys
import tempfile
from pathlib import Path
from unittest.mock import Mock, patch, mock_open

import pytest

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

# This import should work (file exists) but uses OLD security implementation
from plugins.autonomous_dev.lib.project_md_updater import ProjectMdUpdater

# This import will FAIL until security_utils.py is created and integrated
from plugins.autonomous_dev.lib.security_utils import (
    validate_path_whitelist,
    audit_log_security_event,
    SecurityValidationError
)


class TestProjectMdUpdaterPathValidation:
    """Test that ProjectMdUpdater uses shared security_utils for path validation.

    Critical security requirement: Must use validate_path_whitelist() from security_utils
    instead of custom validation logic. This ensures consistent security across all modules.
    """

    @pytest.fixture
    def temp_project_dir(self, tmp_path):
        """Create temporary project directory with PROJECT.md file."""
        project_root = tmp_path / "project"
        project_root.mkdir()

        # Create .claude directory
        claude_dir = project_root / ".claude"
        claude_dir.mkdir()

        # Create PROJECT.md with sample goal
        project_file = claude_dir / "PROJECT.md"
        project_file.write_text("""
# Project Goals

## GOALS

### Goal 1: Implement Feature X (25%)
Description of goal 1.

### Goal 2: Fix Bug Y (0%)
Description of goal 2.
""")

        return project_root, project_file

    def test_uses_security_utils_for_validation(self, temp_project_dir):
        """Test that ProjectMdUpdater uses validate_path_whitelist() from security_utils.

        SECURITY: Centralized validation ensures consistent security across modules.
        Expected: validate_path_whitelist() called during initialization.
        """
        project_root, project_file = temp_project_dir

        # Mock validate_path_whitelist to verify it's called
        with patch('plugins.autonomous_dev.lib.project_md_updater.validate_path_whitelist') as mock_validate:
            mock_validate.return_value = project_file.resolve()

            # Initialize updater
            updater = ProjectMdUpdater(project_file)

            # Verify validate_path_whitelist was called
            mock_validate.assert_called_once()
            call_args = mock_validate.call_args
            assert call_args[0][0] == project_file  # First arg is path
            # Second arg should be PROJECT_ROOT

    def test_path_validation_with_audit_logging(self, temp_project_dir):
        """Test that path validation events are logged to audit trail.

        SECURITY: All path access attempts should be logged.
        Expected: audit_log_security_event() called for each validation.
        """
        project_root, project_file = temp_project_dir

        # Mock audit logging
        with patch('plugins.autonomous_dev.lib.project_md_updater.audit_log_security_event') as mock_audit:
            # Initialize updater
            updater = ProjectMdUpdater(project_file)

            # Verify audit log was called
            mock_audit.assert_called()
            call_args = mock_audit.call_args
            assert call_args[1]['event_type'] == 'PATH_VALIDATION'
            assert call_args[1]['result'] in ['ALLOWED', 'BLOCKED']

    def test_malicious_path_blocked_and_logged(self, temp_project_dir):
        """Test that malicious paths are blocked and logged.

        SECURITY: Path traversal attempts should be blocked AND logged.
        Expected: SecurityValidationError raised, audit log entry created.
        """
        project_root, project_file = temp_project_dir
        malicious_path = Path("/etc/passwd")

        # Mock audit logging to verify blocking is logged
        with patch('plugins.autonomous_dev.lib.project_md_updater.audit_log_security_event') as mock_audit:
            with pytest.raises(SecurityValidationError) as exc_info:
                updater = ProjectMdUpdater(malicious_path)

            # Verify error message
            assert "path traversal" in str(exc_info.value).lower() or "outside project" in str(exc_info.value).lower()

            # Verify blocking was logged
            mock_audit.assert_called()
            call_args = mock_audit.call_args
            assert call_args[1]['result'] == 'BLOCKED'
            assert call_args[1]['event_type'] == 'PATH_VALIDATION'


class TestProjectMdUpdaterSecurityIntegration:
    """Integration tests for ProjectMdUpdater security with security_utils.

    Tests complete security workflows using shared validation module.
    """

    @pytest.fixture
    def temp_project_dir(self, tmp_path):
        """Create temporary project directory with PROJECT.md file."""
        project_root = tmp_path / "project"
        project_root.mkdir()

        claude_dir = project_root / ".claude"
        claude_dir.mkdir()

        project_file = claude_dir / "PROJECT.md"
        project_file.write_text("""
# Project Goals

## GOALS

### Goal 1: Implement Feature X (25%)
Description of goal 1.

### Goal 2: Fix Bug Y (0%)
Description of goal 2.
""")

        return project_root, project_file

    def test_valid_project_md_path_allowed(self, temp_project_dir):
        """Test that valid PROJECT.md paths are allowed.

        SECURITY: Whitelist validation should accept valid project paths.
        Expected: ProjectMdUpdater initializes successfully.
        """
        project_root, project_file = temp_project_dir

        # Set PROJECT_ROOT environment variable for testing
        with patch('plugins.autonomous_dev.lib.project_md_updater.PROJECT_ROOT', project_root):
            # Should not raise exception
            updater = ProjectMdUpdater(project_file)
            assert updater is not None

    def test_relative_path_traversal_blocked(self, temp_project_dir):
        """Test that ../../etc/passwd style paths are blocked.

        SECURITY: Prevent path traversal attacks.
        Expected: SecurityValidationError raised.
        """
        project_root, _ = temp_project_dir
        malicious_path = project_root / ".." / ".." / "etc" / "passwd"

        with patch('plugins.autonomous_dev.lib.project_md_updater.PROJECT_ROOT', project_root):
            with pytest.raises(SecurityValidationError) as exc_info:
                updater = ProjectMdUpdater(malicious_path)

            assert "path traversal" in str(exc_info.value).lower()

    def test_absolute_system_path_blocked(self, temp_project_dir):
        """Test that absolute system paths are blocked.

        SECURITY: Never allow access to /etc, /var/log, /usr, etc.
        Expected: SecurityValidationError for all system paths.
        """
        project_root, _ = temp_project_dir
        system_paths = [
            Path("/etc/passwd"),
            Path("/var/log/auth.log"),
            Path("/usr/bin/evil"),
            Path("/private/etc/hosts")  # macOS symlink resolution
        ]

        with patch('plugins.autonomous_dev.lib.project_md_updater.PROJECT_ROOT', project_root):
            for sys_path in system_paths:
                with pytest.raises(SecurityValidationError):
                    updater = ProjectMdUpdater(sys_path)

    def test_symlink_outside_project_blocked(self, temp_project_dir):
        """Test that symlinks pointing outside project are blocked.

        SECURITY: Prevent symlink-based path traversal.
        Expected: SecurityValidationError raised.
        """
        project_root, _ = temp_project_dir

        # Create symlink pointing outside project
        outside_file = project_root.parent / "outside_PROJECT.md"
        outside_file.write_text("# Malicious content")

        symlink_path = project_root / ".claude" / "PROJECT.md"

        if hasattr(os, 'symlink'):
            try:
                symlink_path.symlink_to(outside_file)

                with patch('plugins.autonomous_dev.lib.project_md_updater.PROJECT_ROOT', project_root):
                    with pytest.raises(SecurityValidationError) as exc_info:
                        updater = ProjectMdUpdater(symlink_path)

                    assert "symlink" in str(exc_info.value).lower() or "outside project" in str(exc_info.value).lower()
            except OSError:
                pytest.skip("Symlinks not supported on this system")
        else:
            pytest.skip("Symlinks not available on Windows")

    def test_symlink_within_project_allowed(self, temp_project_dir):
        """Test that symlinks within project are allowed.

        SECURITY: Symlinks inside project are safe.
        Expected: ProjectMdUpdater initializes successfully.
        """
        project_root, project_file = temp_project_dir

        # Create symlink inside project pointing to PROJECT.md
        symlink_path = project_root / ".claude" / "PROJECT_LINK.md"

        if hasattr(os, 'symlink'):
            try:
                symlink_path.symlink_to(project_file)

                with patch('plugins.autonomous_dev.lib.project_md_updater.PROJECT_ROOT', project_root):
                    # Should succeed - both symlink and target inside project
                    updater = ProjectMdUpdater(symlink_path)
                    assert updater is not None
            except OSError:
                pytest.skip("Symlinks not supported on this system")
        else:
            pytest.skip("Symlinks not available on Windows")

    def test_nonexistent_file_allowed_for_creation(self, temp_project_dir):
        """Test that nonexistent files inside project are allowed.

        SECURITY: New files may not exist yet.
        Expected: ProjectMdUpdater initializes successfully.
        """
        project_root, _ = temp_project_dir
        future_file = project_root / ".claude" / "NEW_PROJECT.md"

        with patch('plugins.autonomous_dev.lib.project_md_updater.PROJECT_ROOT', project_root):
            # Should not raise exception
            updater = ProjectMdUpdater(future_file)
            assert updater is not None

    def test_empty_path_rejected(self, temp_project_dir):
        """Test that empty paths are rejected.

        SECURITY: Empty paths could resolve unpredictably.
        Expected: SecurityValidationError.
        """
        project_root, _ = temp_project_dir

        with patch('plugins.autonomous_dev.lib.project_md_updater.PROJECT_ROOT', project_root):
            with pytest.raises((SecurityValidationError, ValueError)):
                updater = ProjectMdUpdater(Path(""))

    def test_none_path_rejected(self, temp_project_dir):
        """Test that None paths are rejected.

        SECURITY: None should fail fast.
        Expected: SecurityValidationError or TypeError.
        """
        project_root, _ = temp_project_dir

        with patch('plugins.autonomous_dev.lib.project_md_updater.PROJECT_ROOT', project_root):
            with pytest.raises((SecurityValidationError, TypeError)):
                updater = ProjectMdUpdater(None)


class TestProjectMdUpdaterTestModeSupport:
    """Test that ProjectMdUpdater supports test mode correctly.

    Security requirement: Test mode should allow temp directories but still block system directories.
    This ensures tests can run without compromising security.
    """

    @pytest.fixture(autouse=True)
    def set_test_mode(self):
        """Enable test mode for these tests."""
        # pytest automatically sets PYTEST_CURRENT_TEST
        # We'll verify the implementation checks this
        yield

    def test_temp_directory_allowed_in_test_mode(self, tmp_path):
        """Test that temp directories are allowed when running in pytest.

        SECURITY: Test mode allows temp dirs but still validates they're not system dirs.
        Expected: ProjectMdUpdater works with tmp_path in test mode.
        """
        temp_project_file = tmp_path / "PROJECT.md"
        temp_project_file.write_text("# Test Project\n\n## GOALS\n")

        # Set test mode env var (pytest does this automatically)
        with patch.dict(os.environ, {'PYTEST_CURRENT_TEST': 'test_temp_directory_allowed_in_test_mode'}):
            # Should not raise exception in test mode
            updater = ProjectMdUpdater(temp_project_file)
            assert updater is not None

    def test_system_directories_still_blocked_in_test_mode(self, tmp_path):
        """Test that system directories are blocked even in test mode.

        SECURITY: Test mode should NOT weaken security for system directories.
        Expected: SecurityValidationError for /etc, /var/log, etc.
        """
        system_paths = [
            Path("/etc/passwd"),
            Path("/var/log/auth.log"),
            Path("/usr/share/evil"),
            Path("/private/etc/hosts")
        ]

        with patch.dict(os.environ, {'PYTEST_CURRENT_TEST': 'test_system_directories_still_blocked_in_test_mode'}):
            for sys_path in system_paths:
                with pytest.raises(SecurityValidationError):
                    updater = ProjectMdUpdater(sys_path)

    def test_path_traversal_blocked_in_test_mode(self, tmp_path):
        """Test that path traversal is blocked even in test mode.

        SECURITY: Test mode should NOT disable path traversal protection.
        Expected: SecurityValidationError for ../../etc/passwd.
        """
        # Try to traverse outside temp directory to system directory
        malicious_path = tmp_path / ".." / ".." / ".." / ".." / "etc" / "passwd"

        with patch.dict(os.environ, {'PYTEST_CURRENT_TEST': 'test_path_traversal_blocked_in_test_mode'}):
            with pytest.raises(SecurityValidationError):
                updater = ProjectMdUpdater(malicious_path)


class TestProjectMdUpdaterAtomicWrites:
    """Test that atomic write operations are maintained with new security.

    Security requirement: New validation should not break existing atomic write safety.
    """

    @pytest.fixture
    def temp_project_dir(self, tmp_path):
        """Create temporary project directory."""
        project_root = tmp_path / "project"
        project_root.mkdir()

        claude_dir = project_root / ".claude"
        claude_dir.mkdir()

        project_file = claude_dir / "PROJECT.md"
        project_file.write_text("""
# Project Goals

## GOALS

### Goal 1: Test Goal (25%)
Description
""")

        return project_root, project_file

    def test_atomic_write_with_security_validation(self, temp_project_dir):
        """Test that atomic writes work with new security validation.

        SECURITY: Security validation should not break atomic write guarantees.
        Expected: File updated atomically, no corruption if interrupted.
        """
        project_root, project_file = temp_project_dir

        with patch('plugins.autonomous_dev.lib.project_md_updater.PROJECT_ROOT', project_root):
            updater = ProjectMdUpdater(project_file)

            # Update goal progress
            updater.update_goal_progress("Goal 1", 50)

            # Verify file was updated
            content = project_file.read_text()
            assert "50%" in content

    def test_backup_created_before_update(self, temp_project_dir):
        """Test that backup is created before modifications.

        SECURITY: Backup ensures we can recover from failed updates.
        Expected: Backup file exists with original content.
        """
        project_root, project_file = temp_project_dir
        original_content = project_file.read_text()

        with patch('plugins.autonomous_dev.lib.project_md_updater.PROJECT_ROOT', project_root):
            updater = ProjectMdUpdater(project_file)
            updater.update_goal_progress("Goal 1", 75)

            # Verify backup was created
            backup_files = list(project_file.parent.glob("PROJECT.md.backup.*"))
            assert len(backup_files) > 0

            # Verify backup has original content
            backup_content = backup_files[0].read_text()
            assert "25%" in backup_content  # Original progress

    def test_temp_file_cleaned_up_on_success(self, temp_project_dir):
        """Test that temporary files are cleaned up after successful write.

        SECURITY: No orphaned temp files left behind.
        Expected: No .tmp files after successful update.
        """
        project_root, project_file = temp_project_dir

        with patch('plugins.autonomous_dev.lib.project_md_updater.PROJECT_ROOT', project_root):
            updater = ProjectMdUpdater(project_file)
            updater.update_goal_progress("Goal 1", 100)

            # Verify no temp files left
            temp_files = list(project_file.parent.glob("*.tmp"))
            assert len(temp_files) == 0

    def test_temp_file_cleaned_up_on_failure(self, temp_project_dir):
        """Test that temporary files are cleaned up even on failure.

        SECURITY: No temp file leakage on errors.
        Expected: No .tmp files after failed update.
        """
        project_root, project_file = temp_project_dir

        with patch('plugins.autonomous_dev.lib.project_md_updater.PROJECT_ROOT', project_root):
            updater = ProjectMdUpdater(project_file)

            # Simulate write failure
            with patch.object(Path, 'write_text', side_effect=IOError("Disk full")):
                try:
                    updater.update_goal_progress("Goal 1", 100)
                except IOError:
                    pass

            # Verify no temp files left
            temp_files = list(project_file.parent.glob("*.tmp"))
            assert len(temp_files) == 0


class TestProjectMdUpdaterRaceConditions:
    """Test that race condition protections are maintained with new security.

    Security requirement: New validation should not introduce race conditions.
    """

    @pytest.fixture
    def temp_project_dir(self, tmp_path):
        """Create temporary project directory."""
        project_root = tmp_path / "project"
        project_root.mkdir()

        claude_dir = project_root / ".claude"
        claude_dir.mkdir()

        project_file = claude_dir / "PROJECT.md"
        project_file.write_text("""
# Project Goals

## GOALS

### Goal 1: Test Goal (0%)
Description
""")

        return project_root, project_file

    def test_concurrent_updates_with_validation(self, temp_project_dir):
        """Test that concurrent updates work with security validation.

        SECURITY: Path validation should not introduce race conditions.
        Expected: All concurrent updates succeed, file not corrupted.
        """
        import threading

        project_root, project_file = temp_project_dir
        results = []

        def update_progress(progress_value):
            try:
                with patch('plugins.autonomous_dev.lib.project_md_updater.PROJECT_ROOT', project_root):
                    updater = ProjectMdUpdater(project_file)
                    updater.update_goal_progress("Goal 1", progress_value)
                    results.append(("success", progress_value))
            except Exception as e:
                results.append(("error", str(e)))

        # Create multiple threads
        threads = []
        for i in range(5):
            thread = threading.Thread(target=update_progress, args=(i * 20,))
            threads.append(thread)

        # Start all threads
        for thread in threads:
            thread.start()

        # Wait for completion
        for thread in threads:
            thread.join()

        # Verify all succeeded
        assert all(result[0] == "success" for result in results)

        # Verify file is valid JSON/markdown (not corrupted)
        content = project_file.read_text()
        assert "## GOALS" in content
        assert "Goal 1" in content


# Run tests in verbose mode to see which ones fail
if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
