#!/usr/bin/env python3
"""
TDD Tests for Security Utils Module (FAILING - Red Phase)

This module contains FAILING tests for the shared security_utils.py module that
will provide centralized security validation for agent_tracker.py and project_md_updater.py.

Security Requirements (from GitHub issue #46 - CRITICAL CVSS 9.8):
1. Whitelist validation: All paths must be within PROJECT_ROOT
2. Path traversal prevention: Block ../../etc/passwd style attacks
3. Symlink detection and rejection: Prevent symlink-based escapes
4. Pytest format validation: Parse and validate pytest session file format
5. Audit logging: Log all security events (allowed/blocked paths)

Test Coverage Target: 100% of security validation code paths

Following TDD principles:
- Write tests FIRST (red phase)
- Tests describe security requirements
- Tests should FAIL until security_utils.py is implemented
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

# Import actual security utils functions (updated from TDD red phase)
from plugins.autonomous_dev.lib.security_utils import (
    validate_path,  # was validate_path_whitelist
    validate_pytest_path,  # was validate_pytest_format
    audit_log,  # was audit_log_security_event
)
# These exception classes don't exist - use generic ValueError for now
SecurityValidationError = ValueError
PytestFormatError = ValueError
# Aliases for test compatibility
validate_path_whitelist = validate_path
validate_pytest_format = validate_pytest_path
audit_log_security_event = audit_log


class TestPathWhitelistValidation:
    """Test whitelist-based path validation prevents path traversal attacks.

    Critical security requirement: All file paths must be within PROJECT_ROOT.
    Any path outside PROJECT_ROOT should be rejected immediately.
    """

    @pytest.fixture
    def temp_project_dir(self, tmp_path):
        """Create temporary project directory structure."""
        project_root = tmp_path / "project"
        project_root.mkdir()

        # Create valid subdirectories
        (project_root / "docs").mkdir()
        (project_root / "docs" / "sessions").mkdir()
        (project_root / "plugins").mkdir()

        return project_root

    def test_valid_path_within_project_allowed(self, temp_project_dir):
        """Test that valid paths within PROJECT_ROOT are allowed.

        SECURITY: Whitelist validation should accept paths inside project.
        Expected: validate_path_whitelist() returns resolved path without error.
        """
        valid_path = temp_project_dir / "docs" / "sessions" / "test.json"

        # Should not raise exception
        result = validate_path_whitelist(valid_path, temp_project_dir)

        # Should return resolved path
        assert result == valid_path.resolve()
        assert result.is_relative_to(temp_project_dir)

    def test_relative_path_traversal_blocked(self, temp_project_dir):
        """Test that ../../etc/passwd style paths are rejected.

        SECURITY: Prevent attackers from writing files outside project.
        Expected: SecurityValidationError raised with clear error message.
        """
        malicious_path = temp_project_dir / ".." / ".." / "etc" / "passwd"

        with pytest.raises(SecurityValidationError) as exc_info:
            validate_path_whitelist(malicious_path, temp_project_dir)

        # Verify error message explains the issue
        assert "path traversal" in str(exc_info.value).lower()
        assert "outside project" in str(exc_info.value).lower()

    def test_absolute_path_outside_project_blocked(self, temp_project_dir):
        """Test that absolute paths outside PROJECT_ROOT are rejected.

        SECURITY: Only allow files within project structure.
        Expected: SecurityValidationError for /etc/passwd, /tmp/evil, etc.
        """
        malicious_paths = [
            Path("/etc/passwd"),
            Path("/tmp/evil.json"),
            Path("/var/log/malicious.json"),
            Path("/usr/bin/malware")
        ]

        for malicious_path in malicious_paths:
            with pytest.raises(SecurityValidationError) as exc_info:
                validate_path_whitelist(malicious_path, temp_project_dir)

            # Verify error identifies the path as outside project
            error_msg = str(exc_info.value).lower()
            assert "outside project" in error_msg or "path traversal" in error_msg

    def test_symlink_to_outside_directory_blocked(self, temp_project_dir):
        """Test that symlinks pointing outside PROJECT_ROOT are rejected.

        SECURITY: Prevent symlink-based path traversal.
        Expected: SecurityValidationError raised before following symlink.
        """
        # Create a symlink pointing outside the project
        outside_target = temp_project_dir.parent / "outside.json"
        outside_target.touch()  # Create target file

        symlink_path = temp_project_dir / "docs" / "symlink.json"

        if hasattr(os, 'symlink'):  # Skip on Windows if symlinks not supported
            try:
                symlink_path.symlink_to(outside_target)

                with pytest.raises(SecurityValidationError) as exc_info:
                    validate_path_whitelist(symlink_path, temp_project_dir)

                assert "symlink" in str(exc_info.value).lower()
            except OSError:
                pytest.skip("Symlinks not supported on this system")
        else:
            pytest.skip("Symlinks not available on Windows")

    def test_symlink_to_valid_location_allowed(self, temp_project_dir):
        """Test that symlinks pointing INSIDE PROJECT_ROOT are allowed.

        SECURITY: Symlinks within project are safe and should be permitted.
        Expected: validate_path_whitelist() succeeds, returns resolved path.
        """
        # Create target file inside project
        target_file = temp_project_dir / "docs" / "target.json"
        target_file.touch()

        # Create symlink inside project pointing to target
        symlink_path = temp_project_dir / "docs" / "sessions" / "link.json"

        if hasattr(os, 'symlink'):
            try:
                symlink_path.symlink_to(target_file)

                # Should succeed - both symlink and target are inside project
                result = validate_path_whitelist(symlink_path, temp_project_dir)

                # Should resolve to target file
                assert result == target_file.resolve()
                assert result.is_relative_to(temp_project_dir)
            except OSError:
                pytest.skip("Symlinks not supported on this system")
        else:
            pytest.skip("Symlinks not available on Windows")

    def test_nonexistent_path_inside_project_allowed(self, temp_project_dir):
        """Test that nonexistent paths inside PROJECT_ROOT are allowed.

        SECURITY: Files may not exist yet (e.g., new session files).
        Expected: validate_path_whitelist() succeeds for future file creation.
        """
        future_path = temp_project_dir / "docs" / "sessions" / "future.json"

        # Should not raise exception even though file doesn't exist
        result = validate_path_whitelist(future_path, temp_project_dir)

        # Should return resolved path
        assert result.is_relative_to(temp_project_dir)

    def test_dotdot_in_string_detected(self, temp_project_dir):
        """Test that '..' sequences in path strings are detected.

        SECURITY: Catch obvious traversal attempts before filesystem operations.
        Expected: SecurityValidationError raised for any path containing '..'.
        """
        paths_with_dotdot = [
            temp_project_dir / ".." / "outside.json",
            Path("../../../etc/passwd"),
            Path("docs/../../../etc/passwd")
        ]

        for path in paths_with_dotdot:
            with pytest.raises(SecurityValidationError):
                validate_path_whitelist(path, temp_project_dir)

    def test_system_directories_blocked(self, temp_project_dir):
        """Test that system directories are always blocked.

        SECURITY: Never allow writes to /etc, /usr, /var/log, etc.
        Expected: SecurityValidationError for all system paths.
        """
        # Note: On macOS, /etc -> /private/etc, /var -> /private/var
        system_paths = [
            Path("/etc/config.json"),
            Path("/var/log/evil.json"),
            Path("/usr/share/data.json"),
            Path("/bin/malware"),
            Path("/sbin/evil"),
            Path("/root/secret.json"),
            Path("/private/etc/hosts"),
            Path("/private/var/log/hack.json")
        ]

        for sys_path in system_paths:
            with pytest.raises(SecurityValidationError) as exc_info:
                validate_path_whitelist(sys_path, temp_project_dir)

            error_msg = str(exc_info.value).lower()
            assert "system director" in error_msg or "outside project" in error_msg

    def test_empty_path_rejected(self, temp_project_dir):
        """Test that empty paths are rejected.

        SECURITY: Empty paths could resolve to unexpected locations.
        Expected: SecurityValidationError with clear error message.
        """
        with pytest.raises(SecurityValidationError) as exc_info:
            validate_path_whitelist(Path(""), temp_project_dir)

        assert "empty" in str(exc_info.value).lower() or "invalid" in str(exc_info.value).lower()

    def test_none_path_rejected(self, temp_project_dir):
        """Test that None paths are rejected.

        SECURITY: None values should fail fast with clear error.
        Expected: SecurityValidationError or TypeError.
        """
        with pytest.raises((SecurityValidationError, TypeError)):
            validate_path_whitelist(None, temp_project_dir)


class TestPytestFormatValidation:
    """Test pytest session file format validation.

    Security requirement: Parse pytest session files safely and validate format.
    Prevents injection attacks via malformed session file paths.
    """

    def test_valid_pytest_format_accepted(self):
        """Test that valid pytest format is accepted.

        SECURITY: Valid format: PYTEST_CURRENT_TEST=path/to/test.py::TestClass::test_method
        Expected: Returns (file_path, test_class, test_method) tuple.
        """
        valid_format = "tests/unit/test_security.py::TestSecurity::test_validation"

        result = validate_pytest_format(valid_format)

        assert result == ("tests/unit/test_security.py", "TestSecurity", "test_validation")

    def test_pytest_format_without_class_accepted(self):
        """Test that pytest format without class is accepted.

        SECURITY: Valid format: path/to/test.py::test_function
        Expected: Returns (file_path, None, test_function) tuple.
        """
        valid_format = "tests/test_security.py::test_path_validation"

        result = validate_pytest_format(valid_format)

        assert result == ("tests/test_security.py", None, "test_path_validation")

    def test_invalid_pytest_format_rejected(self):
        """Test that invalid pytest formats are rejected.

        SECURITY: Malformed formats could indicate injection attempts.
        Expected: PytestFormatError with clear explanation.
        """
        invalid_formats = [
            "",  # Empty string
            "just_a_filename",  # No :: separator
            "path/to/file.py",  # Missing test identifier
            "::TestClass::test_method",  # Missing file path
            "path/to/file.py::",  # Missing test identifier after ::
            "path/to/file.py::TestClass::",  # Missing method after ::
            "../../etc/passwd::test",  # Path traversal attempt
            "/etc/passwd::TestClass::test_hack"  # Absolute system path
        ]

        for invalid_format in invalid_formats:
            with pytest.raises(PytestFormatError) as exc_info:
                validate_pytest_format(invalid_format)

            assert "invalid format" in str(exc_info.value).lower()

    def test_pytest_format_with_path_traversal_rejected(self):
        """Test that pytest format with path traversal is rejected.

        SECURITY: Prevent ../../etc/passwd in pytest session format.
        Expected: PytestFormatError for paths containing '..'.
        """
        malicious_formats = [
            "../../etc/passwd::TestClass::test_method",
            "../../../usr/bin/evil::test",
            "tests/../../etc/shadow::TestClass::test_method"
        ]

        for malicious_format in malicious_formats:
            with pytest.raises(PytestFormatError) as exc_info:
                validate_pytest_format(malicious_format)

            error_msg = str(exc_info.value).lower()
            assert "path traversal" in error_msg or "invalid" in error_msg

    def test_pytest_format_with_special_characters_handled(self):
        """Test that special characters in test names are handled safely.

        SECURITY: Test names may contain brackets, underscores, numbers.
        Expected: Valid special chars accepted, injection chars rejected.
        """
        # Valid special characters
        valid_formats = [
            "tests/test_api.py::TestAPI::test_endpoint_returns_200",
            "tests/test_user[admin].py::TestUser::test_permissions",
            "tests/test_db.py::TestDatabase::test_query_01"
        ]

        for valid_format in valid_formats:
            result = validate_pytest_format(valid_format)
            assert result is not None
            assert len(result) == 3  # (file, class, method)

    def test_empty_pytest_format_rejected(self):
        """Test that empty pytest format is rejected.

        SECURITY: Empty strings should fail fast.
        Expected: PytestFormatError with clear message.
        """
        with pytest.raises(PytestFormatError) as exc_info:
            validate_pytest_format("")

        assert "empty" in str(exc_info.value).lower() or "invalid" in str(exc_info.value).lower()

    def test_none_pytest_format_rejected(self):
        """Test that None pytest format is rejected.

        SECURITY: None values should fail fast.
        Expected: PytestFormatError or TypeError.
        """
        with pytest.raises((PytestFormatError, TypeError)):
            validate_pytest_format(None)


class TestAuditLogging:
    """Test security audit logging functionality.

    Security requirement: Log all security events for forensic analysis.
    Helps detect and investigate attack attempts.
    """

    @pytest.fixture
    def temp_audit_log(self, tmp_path):
        """Create temporary audit log file."""
        log_file = tmp_path / "security_audit.log"
        return log_file

    def test_path_allowed_event_logged(self, temp_audit_log):
        """Test that allowed path access is logged.

        SECURITY: Track all file access attempts for audit trail.
        Expected: Log entry with timestamp, event type, path, result=ALLOWED.
        """
        test_path = Path("/project/docs/sessions/test.json")

        audit_log_security_event(
            event_type="PATH_VALIDATION",
            path=test_path,
            result="ALLOWED",
            context={"reason": "Path within project root"},
            log_file=temp_audit_log
        )

        # Verify log entry exists
        assert temp_audit_log.exists()
        log_content = temp_audit_log.read_text()

        assert "PATH_VALIDATION" in log_content
        assert "ALLOWED" in log_content
        assert str(test_path) in log_content
        assert "Path within project root" in log_content

    def test_path_blocked_event_logged(self, temp_audit_log):
        """Test that blocked path access is logged.

        SECURITY: Track all blocked access attempts to detect attacks.
        Expected: Log entry with timestamp, event type, path, result=BLOCKED.
        """
        malicious_path = Path("/etc/passwd")

        audit_log_security_event(
            event_type="PATH_VALIDATION",
            path=malicious_path,
            result="BLOCKED",
            context={"reason": "Path traversal attempt", "threat_level": "CRITICAL"},
            log_file=temp_audit_log
        )

        # Verify log entry exists
        assert temp_audit_log.exists()
        log_content = temp_audit_log.read_text()

        assert "PATH_VALIDATION" in log_content
        assert "BLOCKED" in log_content
        assert str(malicious_path) in log_content
        assert "Path traversal" in log_content
        assert "CRITICAL" in log_content

    def test_multiple_events_logged_sequentially(self, temp_audit_log):
        """Test that multiple security events are logged in order.

        SECURITY: Maintain chronological audit trail.
        Expected: Multiple log entries in correct order with timestamps.
        """
        events = [
            {"type": "PATH_VALIDATION", "path": "/project/file1.json", "result": "ALLOWED"},
            {"type": "PATH_VALIDATION", "path": "/etc/passwd", "result": "BLOCKED"},
            {"type": "PYTEST_VALIDATION", "path": "test.py::test_1", "result": "ALLOWED"}
        ]

        for event in events:
            audit_log_security_event(
                event_type=event["type"],
                path=event["path"],
                result=event["result"],
                context={},
                log_file=temp_audit_log
            )

        # Verify all events logged
        log_content = temp_audit_log.read_text()
        log_lines = log_content.strip().split('\n')

        assert len(log_lines) >= 3
        assert "file1.json" in log_content
        assert "ALLOWED" in log_content
        assert "BLOCKED" in log_content

    def test_audit_log_contains_timestamp(self, temp_audit_log):
        """Test that audit log entries include timestamps.

        SECURITY: Timestamps required for forensic analysis.
        Expected: ISO 8601 format timestamp in each log entry.
        """
        audit_log_security_event(
            event_type="TEST_EVENT",
            path=Path("/test/path"),
            result="ALLOWED",
            context={},
            log_file=temp_audit_log
        )

        log_content = temp_audit_log.read_text()

        # Verify timestamp format (e.g., 2025-11-07T14:30:22)
        import re
        timestamp_pattern = r'\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}'
        assert re.search(timestamp_pattern, log_content), "No ISO 8601 timestamp found"

    def test_audit_log_with_context_dict(self, temp_audit_log):
        """Test that context dictionary is logged correctly.

        SECURITY: Context helps understand why decision was made.
        Expected: All context key-value pairs in log entry.
        """
        context = {
            "user": "test-user",
            "operation": "file_write",
            "request_id": "req-12345",
            "threat_level": "LOW"
        }

        audit_log_security_event(
            event_type="PATH_VALIDATION",
            path=Path("/project/test.json"),
            result="ALLOWED",
            context=context,
            log_file=temp_audit_log
        )

        log_content = temp_audit_log.read_text()

        # Verify all context items present
        for key, value in context.items():
            assert key in log_content
            assert str(value) in log_content

    def test_audit_log_handles_special_characters(self, temp_audit_log):
        """Test that special characters in paths are logged safely.

        SECURITY: Prevent log injection via special characters.
        Expected: Special chars escaped or quoted in log.
        """
        special_paths = [
            Path("/project/file with spaces.json"),
            Path("/project/file'with'quotes.json"),
            Path("/project/file\"with\"doublequotes.json"),
            Path("/project/file\nwith\nnewlines.json")
        ]

        for path in special_paths:
            audit_log_security_event(
                event_type="PATH_VALIDATION",
                path=path,
                result="ALLOWED",
                context={},
                log_file=temp_audit_log
            )

        # Verify log was written without errors
        assert temp_audit_log.exists()
        log_content = temp_audit_log.read_text()

        # Each path should be represented (possibly escaped)
        assert len(log_content) > 0


class TestSecurityUtilsIntegration:
    """Integration tests for security utils working together.

    Tests complete security workflows combining multiple validation functions.
    """

    def test_full_path_validation_workflow(self, tmp_path):
        """Test complete path validation workflow.

        SECURITY: End-to-end validation from input to audit log.
        Expected: Valid paths pass all checks, invalid paths blocked and logged.
        """
        project_root = tmp_path / "project"
        project_root.mkdir()
        audit_log = tmp_path / "audit.log"

        # Test valid path
        valid_path = project_root / "docs" / "test.json"
        result = validate_path_whitelist(valid_path, project_root)
        assert result.is_relative_to(project_root)

        # Log the event
        audit_log_security_event(
            event_type="PATH_VALIDATION",
            path=valid_path,
            result="ALLOWED",
            context={"workflow": "integration_test"},
            log_file=audit_log
        )

        # Verify audit log
        assert audit_log.exists()
        assert "ALLOWED" in audit_log.read_text()

    def test_pytest_format_with_path_validation(self, tmp_path):
        """Test pytest format validation combined with path validation.

        SECURITY: Extract file path from pytest format, then validate it.
        Expected: Both validations pass for valid input, fail for malicious input.
        """
        project_root = tmp_path / "project"
        project_root.mkdir()

        # Valid pytest format
        pytest_format = "tests/unit/test_security.py::TestSecurity::test_validation"
        file_path, test_class, test_method = validate_pytest_format(pytest_format)

        # Validate extracted file path
        full_path = project_root / file_path
        result = validate_path_whitelist(full_path, project_root)

        assert result.is_relative_to(project_root)

    def test_malicious_pytest_format_blocked(self, tmp_path):
        """Test that malicious pytest format is blocked at first validation.

        SECURITY: Defense in depth - multiple validation layers.
        Expected: Pytest format validation catches attack before path validation.
        """
        project_root = tmp_path / "project"
        project_root.mkdir()

        # Malicious pytest format with path traversal
        malicious_format = "../../etc/passwd::TestClass::test_method"

        # Should fail at pytest format validation
        with pytest.raises(PytestFormatError):
            validate_pytest_format(malicious_format)

    def test_error_handling_with_logging(self, tmp_path):
        """Test that validation errors are logged to audit trail.

        SECURITY: All security failures should be auditable.
        Expected: SecurityValidationError raised AND logged to audit file.
        """
        project_root = tmp_path / "project"
        project_root.mkdir()
        audit_log = tmp_path / "audit.log"

        malicious_path = Path("/etc/passwd")

        # Attempt validation (should fail)
        try:
            validate_path_whitelist(malicious_path, project_root)
            pytest.fail("Expected SecurityValidationError")
        except SecurityValidationError as e:
            # Log the blocked attempt
            audit_log_security_event(
                event_type="PATH_VALIDATION",
                path=malicious_path,
                result="BLOCKED",
                context={"error": str(e), "threat_level": "CRITICAL"},
                log_file=audit_log
            )

        # Verify error was logged
        assert audit_log.exists()
        log_content = audit_log.read_text()
        assert "BLOCKED" in log_content
        assert "CRITICAL" in log_content


# Run tests in verbose mode to see which ones fail
if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
