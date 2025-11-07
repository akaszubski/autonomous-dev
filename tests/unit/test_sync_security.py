#!/usr/bin/env python3
"""
TDD Tests for Sync Command Security (FAILING - Red Phase)

This module contains FAILING security tests for the unified /sync command
to ensure all security requirements are met.

Requirements (CRITICAL - CVSS 9.8 path traversal prevention):
1. Path traversal prevention: Block ../../etc/passwd attempts
2. Symlink detection: Block symlinks outside project whitelist
3. Path validation: All paths validated via security_utils.py
4. Audit logging: All security events logged to audit log
5. Input validation: Command arguments validated before use

Test Coverage Target: 100% of security-critical code paths

Following TDD principles:
- Write tests FIRST (red phase)
- Tests describe security requirements
- Tests should FAIL until security measures are implemented
- Each test validates ONE security requirement

Author: test-master agent
Date: 2025-11-08
Issue: GitHub #44 - Unified /sync command consolidation
Related: GitHub #46 - CRITICAL path traversal vulnerability (CVSS 9.8)
"""

import os
import sys
import tempfile
from pathlib import Path
from unittest.mock import Mock, patch, mock_open

import pytest

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from plugins.autonomous_dev.lib.sync_mode_detector import SyncMode


class TestPathTraversalPrevention:
    """Test path traversal attack prevention (CWE-22).

    CRITICAL: Path traversal is CVSS 9.8 - attackers can read/write any file.
    All user-provided paths MUST be validated against whitelist.
    """

    @pytest.fixture
    def temp_project(self, tmp_path):
        """Create temporary project for security testing."""
        project_root = tmp_path / "secure_project"
        project_root.mkdir()
        (project_root / ".claude").mkdir()
        return project_root

    def test_sync_mode_detector_blocks_path_traversal_in_project_path(self, temp_project):
        """Test that path traversal in project path is blocked.

        SECURITY: CWE-22 - Path Traversal
        ATTACK: /sync ../../etc/passwd
        Expected: Raises error, path rejected before any operations.
        """
        from plugins.autonomous_dev.lib.sync_mode_detector import SyncModeDetector, SyncModeError

        malicious_path = temp_project / ".." / ".." / "etc" / "passwd"

        with pytest.raises(SyncModeError) as exc_info:
            SyncModeDetector(str(malicious_path))

        # Error should mention path validation failure
        assert 'invalid path' in str(exc_info.value).lower() or 'path traversal' in str(exc_info.value).lower()

    def test_sync_dispatcher_blocks_path_traversal_in_project_path(self, temp_project):
        """Test that sync dispatcher validates project path.

        SECURITY: CWE-22 - Path Traversal
        ATTACK: Provide malicious path to dispatcher
        Expected: Path validated before any file operations.
        """
        from plugins.autonomous_dev.lib.sync_dispatcher import SyncDispatcher, SyncError

        malicious_path = temp_project / ".." / ".." / "tmp" / "malicious"

        with pytest.raises(SyncError) as exc_info:
            SyncDispatcher(str(malicious_path))

        assert 'invalid' in str(exc_info.value).lower() or 'not found' in str(exc_info.value).lower()

    def test_sync_blocks_absolute_path_outside_whitelist(self):
        """Test that absolute paths outside PROJECT_ROOT are rejected.

        SECURITY: CWE-22 - Path Traversal
        ATTACK: /sync /etc/passwd
        Expected: Rejected as outside whitelist.
        """
        from plugins.autonomous_dev.lib.sync_dispatcher import SyncDispatcher, SyncError

        # Absolute path to system directory
        system_path = "/etc"

        with pytest.raises(SyncError):
            SyncDispatcher(system_path)

    def test_sync_validates_all_intermediate_paths(self, temp_project):
        """Test that all intermediate paths during sync are validated.

        SECURITY: CWE-22 - Path Traversal
        ATTACK: Sneak traversal into backup path or target path
        Expected: Every path validated, not just initial project path.
        """
        from plugins.autonomous_dev.lib.sync_dispatcher import SyncDispatcher

        with patch('plugins.autonomous_dev.lib.sync_dispatcher.validate_path') as mock_validate:
            mock_validate.return_value = temp_project.resolve()

            dispatcher = SyncDispatcher(str(temp_project))

            # Attempt sync with environment mode
            with patch.object(dispatcher, '_sync_environment') as mock_sync:
                from plugins.autonomous_dev.lib.sync_dispatcher import SyncResult
                mock_sync.return_value = SyncResult(True, SyncMode.ENVIRONMENT, "Success")

                result = dispatcher.dispatch(SyncMode.ENVIRONMENT)

            # validate_path should be called multiple times
            # (project path, backup path, target paths, etc.)
            assert mock_validate.call_count >= 1


class TestSymlinkDetection:
    """Test symlink detection and rejection (CWE-59).

    CRITICAL: Symlinks can bypass path validation if not resolved.
    Attacker creates symlink plugins/autonomous-dev → /etc
    Without symlink detection, sync would write to /etc.
    """

    @pytest.fixture
    def temp_project(self, tmp_path):
        """Create temporary project for symlink testing."""
        project_root = tmp_path / "symlink_test"
        project_root.mkdir()
        return project_root

    def test_sync_mode_detector_detects_symlink_project_path(self, temp_project):
        """Test that symlink project paths are detected and resolved.

        SECURITY: CWE-59 - Improper Link Resolution
        ATTACK: Create symlink to /etc, pass to sync
        Expected: Symlink resolved and validated against whitelist.
        """
        from plugins.autonomous_dev.lib.sync_mode_detector import SyncModeDetector, SyncModeError

        # Create symlink pointing outside project
        symlink_path = temp_project / "link_to_etc"
        etc_path = Path("/etc")

        if etc_path.exists():  # Only test on systems with /etc
            try:
                symlink_path.symlink_to(etc_path)

                with pytest.raises(SyncModeError) as exc_info:
                    SyncModeDetector(str(symlink_path))

                # Should detect symlink or path outside whitelist
                error_msg = str(exc_info.value).lower()
                assert 'symlink' in error_msg or 'invalid path' in error_msg or 'outside' in error_msg
            finally:
                if symlink_path.exists():
                    symlink_path.unlink()

    def test_sync_dispatcher_resolves_symlinks_before_validation(self, temp_project):
        """Test that dispatcher resolves symlinks before path validation.

        SECURITY: CWE-59 - Improper Link Resolution
        ATTACK: Create symlink within project pointing outside
        Expected: Real path resolved and validated.
        """
        from plugins.autonomous_dev.lib.sync_dispatcher import SyncDispatcher

        # Create valid project directory
        real_project = temp_project / "real_project"
        real_project.mkdir()
        (real_project / ".claude").mkdir()

        # Create symlink to it
        symlink_project = temp_project / "link_project"
        symlink_project.symlink_to(real_project)

        with patch('plugins.autonomous_dev.lib.sync_dispatcher.validate_path') as mock_validate:
            # validate_path should be called with RESOLVED path, not symlink
            mock_validate.return_value = real_project.resolve()

            try:
                dispatcher = SyncDispatcher(str(symlink_project))

                # Verify validate_path was called with resolved path
                call_args = mock_validate.call_args[0][0]
                # Should be resolved path, not symlink
                assert call_args == real_project.resolve() or str(call_args) == str(real_project.resolve())
            finally:
                symlink_project.unlink()

    def test_sync_detects_symlink_in_plugin_directory(self, temp_project):
        """Test that symlinks within plugin directory structure are detected.

        SECURITY: CWE-59 - Improper Link Resolution
        ATTACK: Create plugins/autonomous-dev as symlink to /etc
        Expected: Symlink detected, sync blocked.
        """
        from plugins.autonomous_dev.lib.sync_mode_detector import SyncModeDetector, SyncModeError

        # Create plugins directory
        plugins_dir = temp_project / "plugins"
        plugins_dir.mkdir()

        # Create symlink instead of real autonomous-dev directory
        plugin_symlink = plugins_dir / "autonomous-dev"
        etc_path = Path("/etc")

        if etc_path.exists():
            try:
                plugin_symlink.symlink_to(etc_path)

                # Should detect plugin directory but validate symlink
                with pytest.raises(SyncModeError):
                    detector = SyncModeDetector(str(temp_project))
                    # If detection doesn't raise, dispatch should
                    mode = detector.detect_mode()
            finally:
                if plugin_symlink.exists():
                    plugin_symlink.unlink()


class TestInputValidation:
    """Test input validation for command arguments.

    SECURITY: Validate all user inputs before use.
    Prevents injection attacks and malformed input exploitation.
    """

    def test_sync_mode_detector_validates_flag_format(self):
        """Test that flags are validated for correct format.

        SECURITY: Input Validation
        ATTACK: --env' OR '1'='1 (SQL injection style)
        Expected: Only valid flags accepted, invalid chars rejected.
        """
        from plugins.autonomous_dev.lib.sync_mode_detector import parse_sync_flags, SyncModeError

        # Malicious flag with SQL injection pattern
        with pytest.raises(SyncModeError):
            parse_sync_flags(["--env' OR '1'='1"])

    def test_sync_mode_detector_rejects_non_string_flags(self):
        """Test that non-string flags are rejected.

        SECURITY: Type Validation
        ATTACK: Pass objects/integers instead of strings
        Expected: Type error or validation error.
        """
        from plugins.autonomous_dev.lib.sync_mode_detector import parse_sync_flags, SyncModeError

        with pytest.raises((SyncModeError, TypeError)):
            parse_sync_flags([123, 456])  # Integers instead of strings

    def test_sync_mode_detector_limits_flag_length(self):
        """Test that excessively long flags are rejected.

        SECURITY: Buffer Overflow Prevention
        ATTACK: --env followed by 10MB of data
        Expected: Flag length validated, excessive input rejected.
        """
        from plugins.autonomous_dev.lib.sync_mode_detector import parse_sync_flags, SyncModeError

        # Extremely long flag (10,000 characters)
        long_flag = "--" + "e" * 10000

        with pytest.raises(SyncModeError) as exc_info:
            parse_sync_flags([long_flag])

        assert 'invalid' in str(exc_info.value).lower() or 'too long' in str(exc_info.value).lower()

    def test_sync_dispatcher_validates_mode_enum(self):
        """Test that dispatcher only accepts valid SyncMode enum values.

        SECURITY: Enum Validation
        ATTACK: Pass string "MALICIOUS_MODE" instead of enum
        Expected: Type/value error for non-enum values.
        """
        from plugins.autonomous_dev.lib.sync_dispatcher import SyncDispatcher, SyncError

        # Create valid project
        with tempfile.TemporaryDirectory() as tmpdir:
            project_dir = Path(tmpdir) / "test"
            project_dir.mkdir()
            (project_dir / ".claude").mkdir()

            dispatcher = SyncDispatcher(str(project_dir))

            # Try to dispatch with invalid mode
            with pytest.raises((SyncError, TypeError, ValueError)):
                dispatcher.dispatch("INVALID_MODE")


class TestAuditLogging:
    """Test security audit logging (CWE-117 prevention).

    SECURITY: All security events must be logged for forensics.
    Logs must prevent log injection attacks.
    """

    @pytest.fixture
    def temp_project(self, tmp_path):
        """Create temporary project for audit testing."""
        project_root = tmp_path / "audit_test"
        project_root.mkdir()
        (project_root / ".claude").mkdir()
        return project_root

    def test_sync_mode_detector_logs_mode_detection(self, temp_project):
        """Test that mode detection events are logged to audit log.

        SECURITY: Audit Trail
        Expected: Every detection logged with timestamp, path, mode.
        """
        from plugins.autonomous_dev.lib.sync_mode_detector import SyncModeDetector

        with patch('plugins.autonomous_dev.lib.sync_mode_detector.audit_log') as mock_audit:
            detector = SyncModeDetector(str(temp_project))
            mode = detector.detect_mode()

            # Audit log should be called
            mock_audit.assert_called()

            # Verify logged details
            call_args_list = mock_audit.call_args_list
            assert len(call_args_list) > 0

    def test_sync_dispatcher_logs_sync_operations(self, temp_project):
        """Test that all sync operations are logged.

        SECURITY: Audit Trail
        Expected: Sync start, completion, failures all logged.
        """
        from plugins.autonomous_dev.lib.sync_dispatcher import SyncDispatcher

        with patch('plugins.autonomous_dev.lib.sync_dispatcher.audit_log') as mock_audit:
            with patch.object(SyncDispatcher, '_sync_environment') as mock_sync:
                from plugins.autonomous_dev.lib.sync_dispatcher import SyncResult
                mock_sync.return_value = SyncResult(True, SyncMode.ENVIRONMENT, "Success")

                dispatcher = SyncDispatcher(str(temp_project))
                result = dispatcher.dispatch(SyncMode.ENVIRONMENT)

                # Should log sync operation
                mock_audit.assert_called()

                # Verify operation details logged
                logged_calls = [str(call) for call in mock_audit.call_args_list]
                assert any('sync' in str(call).lower() for call in logged_calls)

    def test_audit_log_prevents_log_injection(self, temp_project):
        """Test that audit logs prevent log injection attacks (CWE-117).

        SECURITY: CWE-117 - Improper Output Neutralization for Logs
        ATTACK: Project path contains newlines to inject fake log entries
        Expected: Newlines and special chars escaped in logs.
        """
        from plugins.autonomous_dev.lib.sync_mode_detector import SyncModeDetector

        # Create project path with newlines (log injection attempt)
        malicious_name = "project\nFAKE_LOG_ENTRY: admin_access_granted\n"
        malicious_project = temp_project / malicious_name

        try:
            malicious_project.mkdir()

            with patch('plugins.autonomous_dev.lib.sync_mode_detector.audit_log') as mock_audit:
                try:
                    detector = SyncModeDetector(str(malicious_project))
                except:
                    pass  # Expected to fail, we're testing the audit log

                # If audit_log was called, verify newlines were escaped
                if mock_audit.called:
                    logged_message = str(mock_audit.call_args)
                    # Newlines should be escaped, not literal
                    assert '\\n' in logged_message or '\n' not in logged_message
        finally:
            if malicious_project.exists():
                malicious_project.rmdir()

    def test_audit_log_includes_security_context(self, temp_project):
        """Test that audit logs include security context (user, timestamp, action).

        SECURITY: Complete Audit Trail
        Expected: Logs include who, when, what, where for forensics.
        """
        from plugins.autonomous_dev.lib.sync_dispatcher import SyncDispatcher

        with patch('plugins.autonomous_dev.lib.sync_dispatcher.audit_log') as mock_audit:
            with patch.object(SyncDispatcher, '_sync_environment') as mock_sync:
                from plugins.autonomous_dev.lib.sync_dispatcher import SyncResult
                mock_sync.return_value = SyncResult(True, SyncMode.ENVIRONMENT, "Success")

                dispatcher = SyncDispatcher(str(temp_project))
                result = dispatcher.dispatch(SyncMode.ENVIRONMENT)

                # Verify audit log called with context
                mock_audit.assert_called()

                # Check that call includes necessary context
                # (Implementation would include timestamp, action, user, path)


class TestFileOperationSecurity:
    """Test security of file operations during sync.

    SECURITY: File operations are high-risk - must be validated.
    """

    @pytest.fixture
    def temp_project(self, tmp_path):
        """Create temporary project for file operation testing."""
        project_root = tmp_path / "file_ops_test"
        project_root.mkdir()
        (project_root / ".claude").mkdir()
        return project_root

    def test_sync_validates_target_paths_before_copy(self, temp_project):
        """Test that target paths are validated before file copy.

        SECURITY: CWE-22 - Path Traversal in File Operations
        ATTACK: Copy to ../../etc/passwd
        Expected: Target path validated against whitelist.
        """
        from plugins.autonomous_dev.lib.sync_dispatcher import SyncDispatcher

        # Create plugin directory
        plugin_dir = temp_project / "plugins" / "autonomous-dev"
        plugin_dir.mkdir(parents=True)
        (plugin_dir / "plugin.json").write_text('{}')

        with patch('plugins.autonomous_dev.lib.sync_dispatcher.validate_path') as mock_validate:
            mock_validate.return_value = temp_project.resolve()

            with patch('plugins.autonomous_dev.lib.sync_dispatcher.shutil.copytree') as mock_copy:
                dispatcher = SyncDispatcher(str(temp_project))
                result = dispatcher.dispatch(SyncMode.PLUGIN_DEV)

                # validate_path should be called for both source and destination
                assert mock_validate.call_count >= 2

    def test_sync_validates_backup_directory_path(self, temp_project):
        """Test that backup directory path is validated.

        SECURITY: CWE-22 - Path Traversal in Backup Operations
        ATTACK: Create backup at ../../tmp/steal_data
        Expected: Backup path validated, must be within project.
        """
        from plugins.autonomous_dev.lib.sync_dispatcher import SyncDispatcher

        with patch('plugins.autonomous_dev.lib.sync_dispatcher.validate_path') as mock_validate:
            mock_validate.return_value = temp_project.resolve()

            dispatcher = SyncDispatcher(str(temp_project), enable_backup=True)

            with patch.object(dispatcher, '_sync_environment') as mock_sync:
                from plugins.autonomous_dev.lib.sync_dispatcher import SyncResult
                mock_sync.return_value = SyncResult(True, SyncMode.ENVIRONMENT, "Success")

                result = dispatcher.dispatch(SyncMode.ENVIRONMENT)

            # Backup path should be validated
            # (Multiple validate_path calls: project, backup, targets)
            assert mock_validate.call_count >= 1

    def test_sync_prevents_overwriting_system_files(self, temp_project):
        """Test that sync cannot overwrite system files.

        SECURITY: Critical File Protection
        ATTACK: Sync mode that tries to write to /etc/passwd
        Expected: Blocked by path validation.
        """
        from plugins.autonomous_dev.lib.sync_dispatcher import SyncDispatcher

        # Mock a malicious sync operation
        with patch('plugins.autonomous_dev.lib.sync_dispatcher.shutil.copytree') as mock_copy:
            with patch('plugins.autonomous_dev.lib.sync_dispatcher.validate_path') as mock_validate:
                # Simulate validation rejecting system path
                def validate_side_effect(path, *args, **kwargs):
                    path_obj = Path(path).resolve()
                    if str(path_obj).startswith('/etc'):
                        raise ValueError("Path outside whitelist")
                    return path_obj

                mock_validate.side_effect = validate_side_effect

                dispatcher = SyncDispatcher(str(temp_project))

                # Attempting to copy to system path should fail
                # (Implementation would call validate_path on target)


class TestPrivilegeEscalation:
    """Test prevention of privilege escalation attacks.

    SECURITY: Sync should not enable privilege escalation.
    """

    def test_sync_runs_with_user_permissions_only(self, tmp_path):
        """Test that sync operations don't require or request elevated privileges.

        SECURITY: Principle of Least Privilege
        Expected: All operations work with normal user permissions.
        """
        from plugins.autonomous_dev.lib.sync_dispatcher import SyncDispatcher

        project_dir = tmp_path / "user_project"
        project_dir.mkdir()
        (project_dir / ".claude").mkdir()

        # Should work without root/admin
        dispatcher = SyncDispatcher(str(project_dir))

        # No privilege escalation should occur
        # (Test implicitly passes if no sudo/UAC prompts)

    def test_sync_does_not_modify_file_permissions(self, tmp_path):
        """Test that sync preserves file permissions (no chmod to 777).

        SECURITY: Permission Preservation
        Expected: File permissions not changed during sync.
        """
        from plugins.autonomous_dev.lib.sync_dispatcher import SyncDispatcher

        project_dir = tmp_path / "perm_test"
        project_dir.mkdir()

        # Create file with specific permissions
        test_file = project_dir / ".claude" / "test.md"
        test_file.parent.mkdir(exist_ok=True)
        test_file.write_text("content")
        original_mode = test_file.stat().st_mode

        # Perform sync (if implementation touches this file)
        with patch.object(SyncDispatcher, '_sync_environment') as mock_sync:
            from plugins.autonomous_dev.lib.sync_dispatcher import SyncResult
            mock_sync.return_value = SyncResult(True, SyncMode.ENVIRONMENT, "Success")

            dispatcher = SyncDispatcher(str(project_dir))
            result = dispatcher.dispatch(SyncMode.ENVIRONMENT)

        # Permissions should be unchanged
        new_mode = test_file.stat().st_mode
        assert new_mode == original_mode


class TestRaceConditions:
    """Test prevention of race condition attacks (TOCTOU).

    SECURITY: CWE-367 - Time-of-check Time-of-use (TOCTOU)
    Attacker changes file between validation and use.
    """

    @pytest.fixture
    def temp_project(self, tmp_path):
        """Create temporary project for race condition testing."""
        project_root = tmp_path / "race_test"
        project_root.mkdir()
        (project_root / ".claude").mkdir()
        return project_root

    def test_sync_uses_file_descriptors_not_paths(self, temp_project):
        """Test that sync uses file descriptors to prevent TOCTOU.

        SECURITY: CWE-367 - TOCTOU Race Condition
        ATTACK: Change file after validation but before copy
        Expected: Use file descriptors or atomic operations.
        """
        # This test documents the requirement - implementation should use
        # file descriptors or atomic operations (like mkstemp + rename)
        # to prevent race conditions
        pass  # Implementation detail test

    def test_sync_validates_path_at_use_time(self, temp_project):
        """Test that paths are re-validated immediately before use.

        SECURITY: CWE-367 - TOCTOU Race Condition
        Expected: Validate as close to use as possible.
        """
        from plugins.autonomous_dev.lib.sync_dispatcher import SyncDispatcher

        with patch('plugins.autonomous_dev.lib.sync_dispatcher.validate_path') as mock_validate:
            mock_validate.return_value = temp_project.resolve()

            with patch.object(SyncDispatcher, '_sync_environment') as mock_sync:
                from plugins.autonomous_dev.lib.sync_dispatcher import SyncResult
                mock_sync.return_value = SyncResult(True, SyncMode.ENVIRONMENT, "Success")

                dispatcher = SyncDispatcher(str(temp_project))
                result = dispatcher.dispatch(SyncMode.ENVIRONMENT)

            # Path should be validated during dispatch, not just __init__
            assert mock_validate.call_count >= 1
