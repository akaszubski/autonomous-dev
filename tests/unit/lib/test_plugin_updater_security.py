#!/usr/bin/env python3
"""
TDD Security Tests for Plugin Updater (FAILING - Red Phase)

This module contains FAILING security tests for plugin_updater.py to ensure
proper security controls for CWE-22, CWE-59, CWE-732, and CWE-778.

Security Requirements:
1. CWE-22: Path Traversal Prevention
   - Reject paths outside whitelist
   - Block directory traversal attempts (../)
   - Validate all user-provided paths

2. CWE-59: Symlink Resolution
   - Reject symlinks that point outside whitelist
   - Resolve symlinks before validation

3. CWE-732: File Permissions
   - Backup directories user-only (0o700)
   - Prevent unauthorized access to backups

4. CWE-778: Audit Logging
   - Log all update operations
   - Log backup creation/restoration
   - Log verification failures
   - Log security violations

Test Coverage Target: 100% of security-critical paths

Following TDD principles:
- Write tests FIRST (red phase)
- Tests describe security requirements
- Tests should FAIL until plugin_updater.py implements security
- Each test validates ONE security control

Author: test-master agent
Date: 2025-11-09
Issue: GitHub #50 Phase 2 - Interactive /update-plugin command
Related: Security hardening per docs/SECURITY.md
"""

import json
import os
import sys
import tempfile
from pathlib import Path
from unittest.mock import Mock, patch, call, MagicMock

import pytest

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

# This import will FAIL until plugin_updater.py is created
from plugins.autonomous_dev.lib.plugin_updater import (
    PluginUpdater,
    UpdateResult,
    UpdateError,
    BackupError,
)
from plugins.autonomous_dev.lib.version_detector import VersionComparison


class TestPathTraversalPrevention:
    """Test CWE-22: Path traversal prevention."""

    def test_reject_absolute_path_outside_whitelist(self):
        """Test rejection of absolute path outside whitelist.

        SECURITY: CWE-22 - Prevent access to sensitive directories.
        Expected: UpdateError raised for /etc/passwd.
        """
        with pytest.raises(UpdateError) as exc_info:
            PluginUpdater(project_root=Path("/etc"))

        assert "invalid" in str(exc_info.value).lower() or "not allowed" in str(exc_info.value).lower()

    def test_reject_parent_directory_traversal(self, tmp_path):
        """Test rejection of ../ directory traversal.

        SECURITY: CWE-22 - Prevent escaping project directory.
        Expected: UpdateError raised for ../../etc/passwd.
        """
        project_root = tmp_path / "test_project"
        project_root.mkdir()

        traversal_path = project_root / ".." / ".." / "etc" / "passwd"

        with pytest.raises(UpdateError) as exc_info:
            PluginUpdater(project_root=traversal_path)

        assert "invalid" in str(exc_info.value).lower() or "traversal" in str(exc_info.value).lower()

    def test_reject_system_directories(self):
        """Test rejection of system directories.

        SECURITY: CWE-22 - Block access to /bin, /usr, /var, etc.
        Expected: UpdateError raised for all system paths.
        """
        system_paths = [
            Path("/bin"),
            Path("/usr"),
            Path("/var"),
            Path("/tmp"),
            Path("/sys"),
            Path("/proc"),
        ]

        for path in system_paths:
            with pytest.raises(UpdateError) as exc_info:
                PluginUpdater(project_root=path)

            assert "invalid" in str(exc_info.value).lower()

    def test_reject_home_directory_escape(self, tmp_path):
        """Test rejection of ~/ home directory expansion.

        SECURITY: CWE-22 - Prevent unintended home directory access.
        Expected: UpdateError if path escapes allowed directories.
        """
        # Try to access user's home directory
        home_path = Path.home() / "sensitive_data"

        with pytest.raises(UpdateError) as exc_info:
            PluginUpdater(project_root=home_path)

        # Should reject unless home path is in whitelist
        assert "invalid" in str(exc_info.value).lower()

    @patch("plugins.autonomous_dev.lib.security_utils.validate_path")
    def test_all_paths_validated_via_security_utils(self, mock_validate, tmp_path):
        """Test all paths pass through security_utils.validate_path.

        SECURITY: CWE-22 - Centralized path validation.
        Expected: security_utils.validate_path called for all paths.
        """
        project_root = tmp_path / "test_project"
        project_root.mkdir()
        (project_root / ".claude").mkdir()

        mock_validate.return_value = project_root

        updater = PluginUpdater(project_root=project_root)

        # Should validate project_root
        mock_validate.assert_called()


class TestSymlinkResolution:
    """Test CWE-59: Symlink resolution and validation."""

    @pytest.fixture
    def temp_environment(self, tmp_path):
        """Create temp environment with symlinks."""
        allowed_dir = tmp_path / "allowed"
        allowed_dir.mkdir()
        (allowed_dir / ".claude").mkdir()

        forbidden_dir = tmp_path / "forbidden"
        forbidden_dir.mkdir()

        return {
            "allowed": allowed_dir,
            "forbidden": forbidden_dir,
            "tmp_path": tmp_path
        }

    def test_reject_symlink_to_forbidden_directory(self, temp_environment):
        """Test rejection of symlink pointing to forbidden directory.

        SECURITY: CWE-59 - Prevent symlink attack to sensitive files.
        Expected: UpdateError raised when symlink points outside whitelist.
        """
        allowed = temp_environment["allowed"]
        forbidden = temp_environment["forbidden"]

        # Create symlink from allowed to forbidden
        symlink_path = allowed / "link_to_forbidden"
        symlink_path.symlink_to(forbidden)

        with pytest.raises(UpdateError) as exc_info:
            PluginUpdater(project_root=symlink_path)

        assert "symlink" in str(exc_info.value).lower() or "invalid" in str(exc_info.value).lower()

    def test_reject_symlink_to_system_directory(self, temp_environment):
        """Test rejection of symlink to system directory.

        SECURITY: CWE-59 - Prevent symlink to /etc, /bin, etc.
        Expected: UpdateError raised.
        """
        allowed = temp_environment["allowed"]

        # Create symlink to /etc
        symlink_path = allowed / "link_to_etc"
        symlink_path.symlink_to(Path("/etc"))

        with pytest.raises(UpdateError) as exc_info:
            PluginUpdater(project_root=symlink_path)

        assert "invalid" in str(exc_info.value).lower()

    def test_resolve_symlinks_before_validation(self, temp_environment):
        """Test symlinks are resolved before path validation.

        SECURITY: CWE-59 - Resolve symlinks to check real path.
        Expected: Real path validated, not symlink path.
        """
        allowed = temp_environment["allowed"]
        real_project = temp_environment["tmp_path"] / "real_project"
        real_project.mkdir()
        (real_project / ".claude").mkdir()

        # Create symlink to allowed project
        symlink_path = allowed / "link_to_project"
        symlink_path.symlink_to(real_project)

        with patch("plugins.autonomous_dev.lib.security_utils.validate_path") as mock_validate:
            mock_validate.return_value = real_project.resolve()

            try:
                updater = PluginUpdater(project_root=symlink_path)
                # Should validate resolved path, not symlink
                call_args = mock_validate.call_args[0]
                # Path should be resolved
                assert call_args[0].resolve() == real_project.resolve()
            except UpdateError:
                # Expected if path outside whitelist
                pass


class TestBackupPermissions:
    """Test CWE-732: Secure file permissions for backups."""

    @pytest.fixture
    def temp_project(self, tmp_path):
        """Create temporary project with plugin files."""
        project_root = tmp_path / "test_project"
        project_root.mkdir()
        (project_root / ".claude").mkdir()
        plugin_dir = project_root / ".claude" / "plugins" / "autonomous-dev"
        plugin_dir.mkdir(parents=True)
        (plugin_dir / "plugin.json").write_text('{"version": "3.7.0"}')
        return project_root

    def test_backup_directory_user_only_permissions(self, temp_project):
        """Test backup directory has user-only permissions.

        SECURITY: CWE-732 - Prevent unauthorized access to backups.
        Expected: Backup directory has 0o700 (rwx------) permissions.
        """
        updater = PluginUpdater(project_root=temp_project)
        backup_path = updater._create_backup()

        stat_info = os.stat(backup_path)
        permissions = stat_info.st_mode & 0o777

        # Must be user-only (no group or other access)
        assert permissions == 0o700

    def test_backup_files_inherit_secure_permissions(self, temp_project):
        """Test backup files have secure permissions.

        SECURITY: CWE-732 - Prevent unauthorized file access.
        Expected: Files within backup are user-accessible only.
        """
        updater = PluginUpdater(project_root=temp_project)
        backup_path = updater._create_backup()

        # Check permissions on files within backup
        for item in backup_path.rglob("*"):
            if item.is_file():
                stat_info = os.stat(item)
                permissions = stat_info.st_mode & 0o777

                # Should be user-readable at minimum (0o600 or 0o700)
                assert (permissions & 0o400) != 0  # User read
                assert (permissions & 0o077) == 0  # No group/other access

    def test_backup_creation_umask_respected(self, temp_project):
        """Test backup respects umask for secure defaults.

        SECURITY: CWE-732 - Use umask for defense in depth.
        Expected: Backup created with restrictive umask.
        """
        updater = PluginUpdater(project_root=temp_project)

        # Set restrictive umask
        old_umask = os.umask(0o077)
        try:
            backup_path = updater._create_backup()

            stat_info = os.stat(backup_path)
            permissions = stat_info.st_mode & 0o777

            # Should respect umask (no group/other)
            assert (permissions & 0o077) == 0
        finally:
            os.umask(old_umask)


class TestAuditLogging:
    """Test CWE-778: Audit logging for security events."""

    @pytest.fixture
    def temp_project(self, tmp_path):
        """Create temporary project."""
        project_root = tmp_path / "test_project"
        project_root.mkdir()
        (project_root / ".claude").mkdir()
        plugin_dir = project_root / ".claude" / "plugins" / "autonomous-dev"
        plugin_dir.mkdir(parents=True)
        (plugin_dir / "plugin.json").write_text('{"version": "3.7.0"}')
        return project_root

    @patch("plugins.autonomous_dev.lib.security_utils.audit_log")
    def test_audit_log_update_start(self, mock_audit, temp_project):
        """Test update start is audit logged.

        SECURITY: CWE-778 - Log all update operations.
        Expected: audit_log called when update starts.
        """
        with patch("plugins.autonomous_dev.lib.plugin_updater.detect_version_mismatch") as mock_detect:
            mock_detect.return_value = VersionComparison(
                project_version="3.8.0",
                marketplace_version="3.8.0",
                status=VersionComparison.UP_TO_DATE,
                message="Versions are equal: 3.8.0"
            )

            updater = PluginUpdater(project_root=temp_project)
            updater.update()

            # Should log update attempt
            assert mock_audit.called

    @patch("plugins.autonomous_dev.lib.security_utils.audit_log")
    def test_audit_log_backup_creation(self, mock_audit, temp_project):
        """Test backup creation is audit logged.

        SECURITY: CWE-778 - Log backup operations.
        Expected: audit_log called with backup event.
        """
        updater = PluginUpdater(project_root=temp_project)
        backup_path = updater._create_backup()

        # Should log backup creation
        mock_audit.assert_called()
        call_args = mock_audit.call_args[1]
        assert call_args["event"] == "plugin_backup_created"
        assert "backup_path" in call_args

    @patch("plugins.autonomous_dev.lib.security_utils.audit_log")
    def test_audit_log_rollback(self, mock_audit, temp_project):
        """Test rollback is audit logged.

        SECURITY: CWE-778 - Log rollback operations.
        Expected: audit_log called with rollback event.
        """
        updater = PluginUpdater(project_root=temp_project)
        backup_path = updater._create_backup()

        # Reset mock to clear backup creation call
        mock_audit.reset_mock()

        updater._rollback(backup_path)

        # Should log rollback
        mock_audit.assert_called()
        call_args = mock_audit.call_args[1]
        assert call_args["event"] == "plugin_rollback"

    @patch("plugins.autonomous_dev.lib.security_utils.audit_log")
    def test_audit_log_verification_failure(self, mock_audit, temp_project):
        """Test verification failure is audit logged.

        SECURITY: CWE-778 - Log security-relevant failures.
        Expected: audit_log called with verification failure event.
        """
        plugin_dir = temp_project / ".claude" / "plugins" / "autonomous-dev"
        (plugin_dir / "plugin.json").write_text('{"version": "3.7.0"}')  # Wrong version

        updater = PluginUpdater(project_root=temp_project)

        try:
            updater._verify_update(expected_version="3.8.0")
        except Exception:
            pass

        # Should log verification failure
        assert mock_audit.called

    @patch("plugins.autonomous_dev.lib.security_utils.audit_log")
    def test_audit_log_path_validation_failure(self, mock_audit):
        """Test path validation failure is audit logged.

        SECURITY: CWE-778 - Log security violations.
        Expected: audit_log called when invalid path detected.
        """
        try:
            PluginUpdater(project_root=Path("/etc/passwd"))
        except UpdateError:
            pass

        # Should log security violation
        assert mock_audit.called

    @patch("plugins.autonomous_dev.lib.security_utils.audit_log")
    def test_audit_log_includes_user_context(self, mock_audit, temp_project):
        """Test audit log includes user context.

        SECURITY: CWE-778 - Log who performed operation.
        Expected: audit_log includes user information.
        """
        updater = PluginUpdater(project_root=temp_project)
        updater._create_backup()

        # Should log with user context
        mock_audit.assert_called()
        call_args = mock_audit.call_args[1]

        # Should include context like user, timestamp, etc.
        assert "event" in call_args

    @patch("plugins.autonomous_dev.lib.security_utils.audit_log")
    def test_audit_log_includes_operation_details(self, mock_audit, temp_project):
        """Test audit log includes operation details.

        SECURITY: CWE-778 - Log sufficient detail for forensics.
        Expected: audit_log includes paths, versions, etc.
        """
        updater = PluginUpdater(project_root=temp_project)
        backup_path = updater._create_backup()

        mock_audit.assert_called()
        call_args = mock_audit.call_args[1]

        # Should include details
        assert "backup_path" in call_args or "details" in call_args


class TestInputValidation:
    """Test input validation for security."""

    def test_validate_plugin_name_alphanumeric(self, tmp_path):
        """Test plugin name validation rejects special characters.

        SECURITY: Prevent injection attacks via plugin name.
        Expected: Reject plugin names with special characters.
        """
        project_root = tmp_path / "test_project"
        project_root.mkdir()
        (project_root / ".claude").mkdir()

        with pytest.raises(UpdateError) as exc_info:
            PluginUpdater(
                project_root=project_root,
                plugin_name="../../../etc/passwd"
            )

        assert "invalid" in str(exc_info.value).lower()

    def test_validate_plugin_name_length(self, tmp_path):
        """Test plugin name length validation.

        SECURITY: Prevent buffer overflow or DOS via long names.
        Expected: Reject excessively long plugin names.
        """
        project_root = tmp_path / "test_project"
        project_root.mkdir()
        (project_root / ".claude").mkdir()

        long_name = "a" * 1000  # Excessively long

        with pytest.raises(UpdateError) as exc_info:
            PluginUpdater(
                project_root=project_root,
                plugin_name=long_name
            )

        assert "invalid" in str(exc_info.value).lower() or "too long" in str(exc_info.value).lower()

    def test_reject_null_bytes_in_paths(self, tmp_path):
        """Test rejection of null bytes in paths.

        SECURITY: Prevent null byte injection attacks.
        Expected: UpdateError for paths with null bytes.
        """
        malicious_path = tmp_path / "test\x00project"

        with pytest.raises(UpdateError) as exc_info:
            PluginUpdater(project_root=malicious_path)

        assert "invalid" in str(exc_info.value).lower()


class TestErrorHandling:
    """Test security-relevant error handling."""

    def test_sanitize_error_messages_no_path_disclosure(self, tmp_path):
        """Test error messages don't disclose sensitive paths.

        SECURITY: Prevent information disclosure via errors.
        Expected: Error messages don't include full system paths.
        """
        sensitive_path = Path("/home/user/.ssh/id_rsa")

        try:
            PluginUpdater(project_root=sensitive_path)
        except UpdateError as e:
            error_msg = str(e)
            # Should not include full sensitive path
            assert "/home/user/.ssh" not in error_msg or "invalid" in error_msg.lower()

    def test_handle_race_conditions_safely(self, tmp_path):
        """Test handling of race conditions during backup.

        SECURITY: TOCTOU (Time-of-check to time-of-use) protection.
        Expected: Safe handling if directory deleted between check and use.
        """
        project_root = tmp_path / "test_project"
        project_root.mkdir()
        (project_root / ".claude").mkdir()
        plugin_dir = project_root / ".claude" / "plugins" / "autonomous-dev"
        plugin_dir.mkdir(parents=True)

        updater = PluginUpdater(project_root=project_root)

        # Simulate race condition - delete directory after init
        plugin_dir.rmdir()

        with pytest.raises(BackupError):
            updater._create_backup()

    @patch("plugins.autonomous_dev.lib.security_utils.audit_log")
    def test_log_all_exceptions(self, mock_audit, tmp_path):
        """Test all exceptions are logged for security monitoring.

        SECURITY: CWE-778 - Comprehensive audit trail.
        Expected: All exceptions logged with context.
        """
        project_root = tmp_path / "test_project"
        project_root.mkdir()

        try:
            PluginUpdater(project_root=project_root)  # Missing .claude directory
        except Exception:
            pass

        # Should log the error
        assert mock_audit.called
